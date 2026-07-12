"""Frozen public-game snapshot and deterministic stratified split utilities."""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True, slots=True)
class GameMetadata:
    game_id: str
    version: str
    tags: tuple[str, ...]
    win_levels: int
    baseline_actions: tuple[int, ...]

    @property
    def modality(self) -> str:
        lowered = " ".join(self.tags).lower()
        has_click = "click" in lowered or "mouse" in lowered
        has_keyboard = "keyboard" in lowered or not has_click
        if has_click and has_keyboard and "keyboard" in lowered:
            return "mixed"
        return "click" if has_click else "simple"

    @property
    def baseline_median(self) -> float:
        return float(median(self.baseline_actions)) if self.baseline_actions else 0.0


@dataclass(frozen=True, slots=True)
class SplitManifest:
    seed: int
    development: tuple[str, ...]
    confirmation: tuple[str, ...]
    metadata_hash: str
    game_versions: dict[str, str] = field(default_factory=dict)
    algorithm: str = "iterative-multilabel-v1"
    supersedes_manifest_hash: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def metadata_hash(games: list[GameMetadata]) -> str:
    payload = json.dumps(
        [asdict(game) for game in sorted(games, key=lambda item: item.game_id)],
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def stratified_split(
    games: list[GameMetadata], *, development_size: int = 15, seed: int = 20_260_712
) -> SplitManifest:
    """Apply iterative multilabel stratification to the frozen game snapshot.

    This is the two-fold Sechidis-style algorithm: repeatedly choose the rarest
    remaining label and assign its samples to the fold with the largest unmet demand
    for that label. It is deterministic for an order-independent snapshot and seed.
    """

    if not 0 < development_size < len(games):
        raise ValueError("development_size must leave at least one confirmation game")
    if len({game.game_id for game in games}) != len(games):
        raise ValueError("game IDs must be unique")

    ordered_games = sorted(games, key=lambda game: game.game_id)
    baseline_bins = _quartile_bins([game.baseline_median for game in ordered_games])
    labels = {
        game.game_id: frozenset(
            (
                f"modality:{game.modality}",
                f"levels:{game.win_levels}",
                f"baseline:q{baseline_bins[index]}",
            )
        )
        for index, game in enumerate(ordered_games)
    }
    development, confirmation = _iterative_two_fold_assignment(
        labels,
        first_size=development_size,
        seed=seed,
    )

    return SplitManifest(
        seed=seed,
        development=tuple(sorted(development)),
        confirmation=tuple(sorted(confirmation)),
        metadata_hash=metadata_hash(games),
        game_versions={game.game_id: game.version for game in ordered_games},
    )


def load_metadata(path: str | Path) -> list[GameMetadata]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = raw["games"] if isinstance(raw, dict) else raw
    return [
        GameMetadata(
            game_id=str(item["game_id"]).split("-", 1)[0],
            version=str(item.get("version") or _version_from_id(str(item["game_id"]))),
            tags=tuple(str(tag) for tag in item.get("tags", ())),
            win_levels=int(item.get("win_levels") or len(item.get("baseline_actions", ()))),
            baseline_actions=tuple(int(x) for x in item.get("baseline_actions", ())),
        )
        for item in entries
    ]


def save_snapshot(games: list[GameMetadata], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "metadata_hash": metadata_hash(games),
        "games": [asdict(game) for game in sorted(games, key=lambda item: item.game_id)],
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _quartile_bins(values: list[float]) -> list[int]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    bins = [0] * len(values)
    for rank, index in enumerate(order):
        bins[index] = min(3, (4 * rank) // max(1, len(values)))
    return bins


def _iterative_two_fold_assignment(
    labels: dict[str, frozenset[str]], *, first_size: int, seed: int
) -> tuple[set[str], set[str]]:
    """Faithful dependency-free implementation of iterative multilabel assignment."""

    sample_count = len(labels)
    fold_sizes = (first_size, sample_count - first_size)
    proportions = (fold_sizes[0] / sample_count, fold_sizes[1] / sample_count)
    remaining_capacity = [fold_sizes[0], fold_sizes[1]]
    desired_samples = [float(fold_sizes[0]), float(fold_sizes[1])]
    by_label: dict[str, set[str]] = defaultdict(set)
    for sample, sample_labels in labels.items():
        for label in sample_labels:
            by_label[label].add(sample)
    desired_labels = {
        label: [len(samples) * proportions[0], len(samples) * proportions[1]]
        for label, samples in by_label.items()
    }
    remaining = set(labels)
    folds: tuple[set[str], set[str]] = (set(), set())
    rng = random.Random(seed)

    while remaining:
        active = [(len(samples & remaining), label) for label, samples in by_label.items()]
        active = [(count, label) for count, label in active if count > 0]
        if not active:
            samples = sorted(remaining)
            rng.shuffle(samples)
        else:
            minimum = min(count for count, _ in active)
            rarest = sorted(label for count, label in active if count == minimum)
            label = rarest[rng.randrange(len(rarest))]
            samples = sorted(by_label[label] & remaining)
            rng.shuffle(samples)

        for sample in samples:
            if sample not in remaining:
                continue
            candidates = [index for index, capacity in enumerate(remaining_capacity) if capacity]
            if not candidates:  # pragma: no cover - guarded by exact capacities
                raise AssertionError("iterative assignment exhausted fold capacity")
            if active:
                best_label_demand = max(desired_labels[label][index] for index in candidates)
                candidates = [
                    index
                    for index in candidates
                    if desired_labels[label][index] == best_label_demand
                ]
            best_sample_demand = max(desired_samples[index] for index in candidates)
            candidates = [
                index for index in candidates if desired_samples[index] == best_sample_demand
            ]
            fold = candidates[rng.randrange(len(candidates))]
            folds[fold].add(sample)
            remaining.remove(sample)
            remaining_capacity[fold] -= 1
            desired_samples[fold] -= 1.0
            for sample_label in labels[sample]:
                desired_labels[sample_label][fold] -= 1.0

    return folds


def _version_from_id(game_id: str) -> str:
    return game_id.split("-", 1)[1] if "-" in game_id else "unknown"
