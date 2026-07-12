from __future__ import annotations

from dataclasses import replace

from arc3_voi.metrics import (
    RunMetrics,
    evaluate_confirmation_gate,
    evaluate_development_score_gate,
    evaluate_mechanism_gate,
)
from arc3_voi.runner import run_game

from .test_runner import FakeController, FakeSession


def _traced_run(*, variant: str, loss: float, valid: int) -> RunMetrics:
    result = run_game(
        FakeSession(),
        FakeController(),
        run_id=f"trace-{variant}",
        seed=1,
        variant=variant,
        model_profile="test",
        config_hash="h",
    )
    result.steps = [
        replace(
            step,
            valid_hypotheses=valid,
            weighted_transition_loss=loss,
            best_hypothesis_transition_loss=loss,
        )
        for step in result.steps
    ]
    result.timeout_instrumentation_complete = True
    result.program_prediction_calls = 100
    result.program_goal_calls = 0
    return result


def test_mechanism_gate_uses_decisions_timeout_calls_and_losses() -> None:
    x = _traced_run(variant="X", loss=0.10, valid=2)
    s = _traced_run(variant="S", loss=0.20, valid=1)
    result = evaluate_mechanism_gate((x,), (s,))
    assert result.passed
    assert result.two_valid_fraction == 1.0
    assert result.relative_loss_improvement == 0.5


def test_mechanism_gate_fails_closed_without_exact_timeout_counts() -> None:
    x = _traced_run(variant="X", loss=0.10, valid=2)
    x.timeout_instrumentation_complete = False
    result = evaluate_mechanism_gate((x,), (_traced_run(variant="S", loss=0.2, valid=1),))
    assert not result.passed
    assert result.timeout_rate is None


def _summary_run(
    game: str,
    variant: str,
    rhae: float,
    *,
    levels: int = 1,
    actions: int = 10,
    wall: float = 10,
) -> RunMetrics:
    result = RunMetrics(game + variant, game, 1, variant, "test", "h")
    result.rhae = rhae
    result.levels_completed = levels
    result.total_actions = actions
    result.wall_seconds = wall
    return result


def test_development_gate_averages_paired_games() -> None:
    runs = (
        _summary_run("a", "X", 0.61),
        _summary_run("a", "M", 0.60),
        _summary_run("b", "X", 0.62),
        _summary_run("b", "M", 0.60),
    )
    result = evaluate_development_score_gate(runs)
    assert result.gate.passed
    assert set(result.game_deltas) == {"a", "b"}


def test_confirmation_gate_requires_all_ten_games() -> None:
    complete = []
    for index in range(10):
        complete.append(_summary_run(str(index), "X", 0.6 if index < 6 else 0.5))
        complete.append(_summary_run(str(index), "M", 0.5))
    assert evaluate_confirmation_gate(complete, comparator="M", bootstrap_samples=1_000).passed
    incomplete = evaluate_confirmation_gate(
        complete[:-2], comparator="M", bootstrap_samples=100
    )
    assert not incomplete.passed
    assert "exactly 10" in incomplete.reasons[0]
