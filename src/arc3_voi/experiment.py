"""Preregistered experiment matrices, config hashes, and decision gates."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal

Variant = Literal["D", "S", "M", "X"]

DEVELOPMENT_SEEDS = (11, 23, 47)
CONFIRMATION_SEEDS = (101, 211, 307, 401, 503)
KAGGLE_TRANSFER_SEEDS = (701,)
FALLBACK_DEVELOPMENT_SEEDS = DEVELOPMENT_SEEDS[:2]
FALLBACK_CONFIRMATION_SEEDS = CONFIRMATION_SEEDS[:3]
ETA_GRID = (2.0, 5.0, 10.0)
LAMBDA_GRID = (0.0, 0.002, 0.01)


@dataclass(frozen=True, slots=True)
class RunSpec:
    phase: Literal["development", "confirmation", "kaggle-transfer"]
    game_id: str
    seed: int
    variant: Variant
    model_profile: str
    config_hash: str
    game_version: str = "unknown"
    snapshot_hash: str = ""

    @property
    def full_game_id(self) -> str:
        if not self.game_version or self.game_version == "unknown":
            return self.game_id
        return f"{self.game_id}-{self.game_version}"

    @property
    def run_id(self) -> str:
        return (
            f"{self.phase}-{self.full_game_id}-{self.seed}-{self.variant}-"
            f"{self.config_hash[:8]}"
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunSpec:
        """Load both current manifests and pre-version legacy manifests safely."""

        return cls(
            phase=str(value["phase"]),  # type: ignore[arg-type]
            game_id=str(value["game_id"]),
            seed=int(value["seed"]),
            variant=str(value["variant"]),  # type: ignore[arg-type]
            model_profile=str(value["model_profile"]),
            config_hash=str(value["config_hash"]),
            game_version=str(value.get("game_version", "unknown")),
            snapshot_hash=str(value.get("snapshot_hash", "")),
        )


@dataclass(frozen=True, slots=True)
class HyperparameterObservation:
    game_id: str
    seed: int
    eta: float
    complexity_lambda: float
    rhae: float
    generated_tokens: int


@dataclass(frozen=True, slots=True)
class HyperparameterSelection:
    eta: float
    complexity_lambda: float
    mean_rhae: float
    mean_generated_tokens: float
    observations: int


@dataclass(frozen=True, slots=True)
class ScoreGateInput:
    x_rhae: float
    m_rhae: float
    x_levels: int
    m_levels: int
    x_actions: int
    m_actions: int
    positive_game_fraction: float
    x_wall_seconds: float
    m_wall_seconds: float


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]


def stable_config_hash(config: object) -> str:
    payload = json.dumps(
        config,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def build_development_matrix(
    games: tuple[str, ...],
    *,
    model_profile: str,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
    fallback: bool = False,
) -> tuple[RunSpec, ...]:
    seeds = FALLBACK_DEVELOPMENT_SEEDS if fallback else DEVELOPMENT_SEEDS
    variants: tuple[Variant, ...] = ("D", "S", "M", "X")
    return tuple(
        RunSpec(
            "development",
            game,
            seed,
            variant,
            model_profile,
            config_hashes[variant],
            _game_version(game, game_versions),
            snapshot_hash,
        )
        for game in games
        for seed in seeds
        for variant in variants
    )


def build_confirmation_matrix(
    games: tuple[str, ...],
    *,
    comparator: Variant,
    model_profile: str,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
    fallback: bool = False,
) -> tuple[RunSpec, ...]:
    if comparator == "X":
        raise ValueError("confirmation comparator must differ from X")
    seeds = FALLBACK_CONFIRMATION_SEEDS if fallback else CONFIRMATION_SEEDS
    variants: tuple[Variant, ...] = (comparator, "X")
    return tuple(
        RunSpec(
            "confirmation",
            game,
            seed,
            variant,
            model_profile,
            config_hashes[variant],
            _game_version(game, game_versions),
            snapshot_hash,
        )
        for game in games
        for seed in seeds
        for variant in variants
    )


def build_kaggle_transfer_matrix(
    games: tuple[str, ...],
    *,
    comparator: Variant,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
) -> tuple[RunSpec, ...]:
    return tuple(
        RunSpec(
            "kaggle-transfer",
            game,
            seed,
            variant,
            "kaggle-fp8",
            config_hashes[variant],
            _game_version(game, game_versions),
            snapshot_hash,
        )
        for game in games
        for seed in KAGGLE_TRANSFER_SEEDS
        for variant in (comparator, "X")
    )


def evaluate_score_gate(value: ScoreGateInput) -> GateResult:
    delta_points = 100.0 * (value.x_rhae - value.m_rhae)
    score_improved = delta_points >= 0.5
    level_improved = value.x_levels > value.m_levels and value.x_actions <= value.m_actions
    reasons = []
    if not (score_improved or level_improved):
        reasons.append("neither +0.5 RHAE points nor an action-neutral extra level")
    if value.positive_game_fraction < 0.60:
        reasons.append("positive on fewer than 60% of development games")
    if value.m_wall_seconds <= 0 or value.x_wall_seconds > 1.5 * value.m_wall_seconds:
        reasons.append("wall time exceeds 1.5x the myopic controller")
    return GateResult(not reasons, tuple(reasons))


def projected_gpu_hours(run_count: int, median_run_seconds: float) -> float:
    if run_count < 0 or median_run_seconds < 0:
        raise ValueError("run count and duration must be non-negative")
    return run_count * median_run_seconds / 3600.0


def save_matrix(matrix: tuple[RunSpec, ...], path: str | Path) -> None:
    validate_matrix(matrix, require_frozen_identity=True)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps([asdict(item) | {"run_id": item.run_id} for item in matrix], indent=2)
        + "\n",
        encoding="utf-8",
    )


def load_matrix(path: str | Path, *, require_frozen_identity: bool = True) -> tuple[RunSpec, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("runs", ())
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes):
        raise ValueError("matrix must be a JSON list or an object containing a runs list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("every matrix row must be a JSON object")
    matrix = tuple(RunSpec.from_mapping(row) for row in rows)
    for source, row in zip(rows, matrix, strict=True):
        declared_run_id = source.get("run_id")
        if declared_run_id is not None and declared_run_id != row.run_id:
            raise ValueError(f"declared run ID does not match row fields: {declared_run_id}")
    validate_matrix(matrix, require_frozen_identity=require_frozen_identity)
    return matrix


def validate_matrix(
    matrix: Sequence[RunSpec], *, require_frozen_identity: bool = True
) -> None:
    """Reject incomplete, unpaired, mutable, or hash-ambiguous run manifests."""

    if not matrix:
        raise ValueError("matrix cannot be empty")
    if len({row.run_id for row in matrix}) != len(matrix):
        raise ValueError("matrix run IDs must be unique")
    phases = {row.phase for row in matrix}
    if len(phases) != 1:
        raise ValueError("a matrix must contain exactly one phase")
    if not phases <= {"development", "confirmation", "kaggle-transfer"}:
        raise ValueError("matrix contains an invalid phase")
    if any(row.variant not in {"D", "S", "M", "X"} for row in matrix):
        raise ValueError("matrix contains an invalid variant")
    if any(not row.game_id or not row.model_profile for row in matrix):
        raise ValueError("matrix game IDs and model profiles cannot be empty")
    if require_frozen_identity:
        snapshots = {row.snapshot_hash for row in matrix}
        if len(snapshots) != 1 or not _is_sha256(next(iter(snapshots))):
            raise ValueError("matrix must carry one valid frozen snapshot hash")
        if any(not row.game_version or row.game_version == "unknown" for row in matrix):
            raise ValueError("every matrix row must carry a frozen game version")

    variant_hashes: dict[Variant, set[str]] = defaultdict(set)
    cells: dict[tuple[str, Variant], set[int]] = defaultdict(set)
    variants = {row.variant for row in matrix}
    games_by_variant: dict[Variant, set[str]] = defaultdict(set)
    for row in matrix:
        if not _is_sha256(row.config_hash):
            raise ValueError(f"invalid config hash for {row.run_id}")
        variant_hashes[row.variant].add(row.config_hash)
        cell = (row.full_game_id, row.variant)
        if row.seed in cells[cell]:
            raise ValueError(f"duplicate game/seed/variant cell: {cell}, seed={row.seed}")
        cells[cell].add(row.seed)
        games_by_variant[row.variant].add(row.full_game_id)
    if any(len(hashes) != 1 for hashes in variant_hashes.values()):
        raise ValueError("each variant must have exactly one config hash")
    hashes = {next(iter(values)) for values in variant_hashes.values()}
    if len(hashes) != len(variant_hashes):
        raise ValueError("variant config hashes must be distinct")
    reference_games = games_by_variant[next(iter(variants))]
    if any(games != reference_games for games in games_by_variant.values()):
        raise ValueError("variants must cover identical game sets")
    expected_seeds: set[int] | None = None
    for game in sorted(reference_games):
        per_variant = [cells[(game, variant)] for variant in variants]
        if any(seeds != per_variant[0] for seeds in per_variant[1:]):
            raise ValueError(f"variants have non-identical paired seed sets for {game}")
        if expected_seeds is None:
            expected_seeds = per_variant[0]
        elif per_variant[0] != expected_seeds:
            raise ValueError("all games must use the same frozen seed set")


def completed_run_ids(matrix: Sequence[RunSpec], output: str | Path) -> frozenset[str]:
    """Return only summaries that exactly match their manifest row and completed cleanly."""

    destination = Path(output)
    completed: set[str] = set()
    for row in matrix:
        path = destination / f"{row.run_id}.json"
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        expected = {
            "run_id": row.run_id,
            "game_id": row.full_game_id,
            "seed": row.seed,
            "variant": row.variant,
            "model_profile": row.model_profile,
            "config_hash": row.config_hash,
        }
        if (
            all(value.get(key) == expected_value for key, expected_value in expected.items())
            and value.get("error") is None
            and value.get("termination_reason") is not None
        ):
            completed.add(row.run_id)
    return frozenset(completed)


def pending_runs(matrix: Sequence[RunSpec], output: str | Path) -> tuple[RunSpec, ...]:
    completed = completed_run_ids(matrix, output)
    return tuple(row for row in matrix if row.run_id not in completed)


def select_eta_lambda(
    observations: Iterable[HyperparameterObservation],
) -> HyperparameterSelection:
    """Select the preregistered 3x3 grid by RHAE, tokens, lambda, then eta."""

    buckets: dict[tuple[float, float], list[HyperparameterObservation]] = defaultdict(list)
    for row in observations:
        key = (float(row.eta), float(row.complexity_lambda))
        if key not in {(eta, value) for eta in ETA_GRID for value in LAMBDA_GRID}:
            raise ValueError(f"observation outside preregistered eta/lambda grid: {key}")
        buckets[key].append(row)
    expected = {(eta, value) for eta in ETA_GRID for value in LAMBDA_GRID}
    if set(buckets) != expected:
        missing = sorted(expected - set(buckets))
        raise ValueError(f"missing eta/lambda grid cells: {missing}")
    reference_cells: set[tuple[str, int]] | None = None
    candidates: list[HyperparameterSelection] = []
    for (eta, value), rows in sorted(buckets.items()):
        cells = {(row.game_id, row.seed) for row in rows}
        if len(cells) != len(rows):
            raise ValueError(f"duplicate observations in eta/lambda cell {(eta, value)}")
        if reference_cells is None:
            reference_cells = cells
        elif cells != reference_cells:
            raise ValueError("eta/lambda cells must contain identical game/seed observations")
        candidates.append(
            HyperparameterSelection(
                eta=eta,
                complexity_lambda=value,
                mean_rhae=mean(row.rhae for row in rows),
                mean_generated_tokens=mean(row.generated_tokens for row in rows),
                observations=len(rows),
            )
        )
    return max(
        candidates,
        key=lambda row: (
            row.mean_rhae,
            -row.mean_generated_tokens,
            -row.complexity_lambda,
            -row.eta,
        ),
    )


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _game_version(game: str, versions: Mapping[str, str] | None) -> str:
    if versions is not None:
        return str(versions.get(game, "unknown"))
    _, separator, version = game.partition("-")
    return version if separator else "unknown"


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
