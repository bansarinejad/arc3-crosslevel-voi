"""Paired game-level analysis without pseudoreplication."""

from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class ScoreObservation:
    game_id: str
    seed: int
    variant: str
    rhae: float


@dataclass(frozen=True, slots=True)
class PairedSummary:
    games: int
    mean_delta: float
    wins: int
    losses: int
    ties: int
    interval_90: tuple[float, float]
    probability_positive: float
    exact_sign_pvalue: float
    permutation_pvalue: float


def paired_game_deltas(
    observations: Iterable[ScoreObservation], treatment: str, comparator: str
) -> dict[str, float]:
    return {
        game: mean(seed_values)
        for game, seed_values in paired_seed_deltas(
            observations, treatment, comparator
        ).items()
    }


def paired_seed_deltas(
    observations: Iterable[ScoreObservation], treatment: str, comparator: str
) -> dict[str, tuple[float, ...]]:
    """Pair by game *and seed*, rejecting missing, duplicate, or asymmetric cells."""

    values: dict[tuple[str, str, int], float] = {}
    seeds: dict[tuple[str, str], set[int]] = defaultdict(set)
    games: dict[str, set[str]] = {treatment: set(), comparator: set()}
    for row in observations:
        if row.variant not in {treatment, comparator}:
            continue
        key = (row.game_id, row.variant, row.seed)
        if key in values:
            raise ValueError(f"duplicate paired observation: {key}")
        values[key] = float(row.rhae)
        seeds[(row.game_id, row.variant)].add(row.seed)
        games[row.variant].add(row.game_id)
    if not games[treatment] or games[treatment] != games[comparator]:
        raise ValueError("treatment and comparator must cover identical non-empty game sets")

    expected_seeds: set[int] | None = None
    result: dict[str, tuple[float, ...]] = {}
    for game in sorted(games[treatment]):
        treatment_seeds = seeds[(game, treatment)]
        comparator_seeds = seeds[(game, comparator)]
        if treatment_seeds != comparator_seeds:
            raise ValueError(f"paired variants use different seed sets for {game}")
        if expected_seeds is None:
            expected_seeds = treatment_seeds
        elif treatment_seeds != expected_seeds:
            raise ValueError("paired games must use one identical frozen seed set")
        result[game] = tuple(
            values[(game, treatment, seed)] - values[(game, comparator, seed)]
            for seed in sorted(treatment_seeds)
        )
    return result


def summarize_paired(
    deltas: dict[str, float], *, bootstrap_samples: int = 20_000, seed: int = 20_260_712
) -> PairedSummary:
    values = tuple(deltas.values())
    if not values:
        raise ValueError("at least one paired game is required")
    rng = random.Random(seed)
    boot = [mean(rng.choices(values, k=len(values))) for _ in range(bootstrap_samples)]
    boot.sort()
    lower = _quantile(boot, 0.05)
    upper = _quantile(boot, 0.95)
    probability = sum(value > 0 for value in boot) / len(boot)
    return PairedSummary(
        games=len(values),
        mean_delta=mean(values),
        wins=sum(value > 0 for value in values),
        losses=sum(value < 0 for value in values),
        ties=sum(value == 0 for value in values),
        interval_90=(lower, upper),
        probability_positive=probability,
        exact_sign_pvalue=exact_sign_test(values),
        permutation_pvalue=paired_permutation_test(values),
    )


def summarize_paired_observations(
    observations: Iterable[ScoreObservation],
    treatment: str,
    comparator: str,
    *,
    bootstrap_samples: int = 20_000,
    seed: int = 20_260_712,
) -> PairedSummary:
    """Use paired game means for tests and a two-stage game/seed bootstrap interval."""

    seed_deltas = paired_seed_deltas(observations, treatment, comparator)
    game_deltas = {game: mean(values) for game, values in seed_deltas.items()}
    values = tuple(game_deltas.values())
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    boot = hierarchical_bootstrap_means(seed_deltas, samples=bootstrap_samples, seed=seed)
    return PairedSummary(
        games=len(values),
        mean_delta=mean(values),
        wins=sum(value > 0 for value in values),
        losses=sum(value < 0 for value in values),
        ties=sum(value == 0 for value in values),
        interval_90=(_quantile(boot, 0.05), _quantile(boot, 0.95)),
        probability_positive=sum(value > 0 for value in boot) / len(boot),
        exact_sign_pvalue=exact_sign_test(values),
        permutation_pvalue=paired_permutation_test(values),
    )


def hierarchical_bootstrap_means(
    paired_deltas: Mapping[str, Sequence[float]],
    *,
    samples: int = 20_000,
    seed: int = 20_260_712,
) -> list[float]:
    """Resample games, then paired seed replicates within each sampled game."""

    if samples < 1:
        raise ValueError("samples must be positive")
    games = tuple(sorted(paired_deltas))
    if not games or any(not paired_deltas[game] for game in games):
        raise ValueError("every game must contain at least one paired seed delta")
    rng = random.Random(seed)
    boot: list[float] = []
    for _ in range(samples):
        sampled_games = rng.choices(games, k=len(games))
        game_means = []
        for game in sampled_games:
            values = tuple(float(value) for value in paired_deltas[game])
            game_means.append(mean(rng.choices(values, k=len(values))))
        boot.append(mean(game_means))
    boot.sort()
    return boot


def exact_sign_test(values: Iterable[float]) -> float:
    nonzero = [value for value in values if value != 0]
    n = len(nonzero)
    if n == 0:
        return 1.0
    wins = sum(value > 0 for value in nonzero)
    tail = sum(math.comb(n, k) for k in range(wins, n + 1)) / (2**n)
    return float(min(1.0, tail))


def paired_permutation_test(values: Iterable[float]) -> float:
    data = tuple(float(value) for value in values)
    if not data:
        raise ValueError("at least one delta is required")
    observed = mean(data)
    if len(data) <= 20:
        permuted = (
            mean(tuple(sign * value for sign, value in zip(signs, data, strict=True)))
            for signs in itertools.product((-1.0, 1.0), repeat=len(data))
        )
        extreme = total = 0
        for candidate in permuted:
            total += 1
            if candidate >= observed - 1e-15:
                extreme += 1
        return extreme / total
    rng = random.Random(20_260_712)
    samples = 100_000
    extreme = 0
    for _ in range(samples):
        candidate = mean(value if rng.random() < 0.5 else -value for value in data)
        extreme += candidate >= observed - 1e-15
    return (extreme + 1) / (samples + 1)


def confirmation_claim_passes(summary: PairedSummary) -> bool:
    return summary.wins >= 6 and summary.probability_positive >= 0.90


def strongest_comparator(observations: Iterable[ScoreObservation]) -> str:
    rows = tuple(observations)
    values: dict[str, list[float]] = defaultdict(list)
    cells: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for row in rows:
        if row.variant in {"D", "S", "M"}:
            values[row.variant].append(row.rhae)
            cell = (row.game_id, row.seed)
            if cell in cells[row.variant]:
                raise ValueError(f"duplicate comparator observation: {row.variant}, {cell}")
            cells[row.variant].add(cell)
    if not values:
        raise ValueError("no comparator observations")
    if set(values) != {"D", "S", "M"} or len({frozenset(value) for value in cells.values()}) != 1:
        raise ValueError("D, S, and M must contain identical game/seed cells")
    # Stable tie order favours the simpler direct, single, then myopic systems.
    order = {"D": 0, "S": 1, "M": 2}
    return max(values, key=lambda key: (mean(values[key]), -order[key]))


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires values")
    position = probability * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    fraction = position - low
    return sorted_values[low] * (1 - fraction) + sorted_values[high] * fraction
