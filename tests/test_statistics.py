from __future__ import annotations

import pytest

from arc3_voi.statistics import (
    ScoreObservation,
    confirmation_claim_passes,
    paired_game_deltas,
    paired_seed_deltas,
    summarize_paired,
    summarize_paired_observations,
)


def test_seed_replicates_are_averaged_within_game() -> None:
    rows = [
        ScoreObservation("a", 1, "X", 0.4),
        ScoreObservation("a", 2, "X", 0.6),
        ScoreObservation("a", 1, "M", 0.2),
        ScoreObservation("a", 2, "M", 0.4),
    ]
    assert paired_game_deltas(rows, "X", "M")["a"] == pytest.approx(0.2)


def test_confirmation_gate_uses_games_not_episodes() -> None:
    deltas = {f"g{i}": 0.1 for i in range(8)} | {"g8": -0.01, "g9": -0.02}
    summary = summarize_paired(deltas, bootstrap_samples=2_000)
    assert summary.games == 10
    assert summary.wins == 8
    assert confirmation_claim_passes(summary)


def test_pairing_rejects_different_seed_sets() -> None:
    rows = [
        ScoreObservation("a", 1, "X", 0.4),
        ScoreObservation("a", 2, "X", 0.6),
        ScoreObservation("a", 1, "M", 0.2),
    ]
    with pytest.raises(ValueError, match="different seed sets"):
        paired_seed_deltas(rows, "X", "M")


def test_hierarchical_summary_resamples_paired_seeds() -> None:
    rows = [
        ScoreObservation(game, seed, variant, score)
        for game, seed, variant, score in (
            ("a", 1, "X", 1.0),
            ("a", 2, "X", 0.0),
            ("a", 1, "M", 0.0),
            ("a", 2, "M", 0.0),
            ("b", 1, "X", 0.5),
            ("b", 2, "X", 0.5),
            ("b", 1, "M", 0.0),
            ("b", 2, "M", 0.0),
        )
    ]
    summary = summarize_paired_observations(rows, "X", "M", bootstrap_samples=1_000)
    assert summary.games == 2
    assert summary.mean_delta == pytest.approx(0.5)
    assert summary.interval_90[0] < summary.interval_90[1]
