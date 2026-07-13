from __future__ import annotations

from dataclasses import replace

import pytest

from arc3_voi.metrics import (
    RunMetrics,
    evaluate_confirmation_gate,
    evaluate_development_score_gate,
    evaluate_mechanism_gate,
)
from arc3_voi.runner import run_game

from .test_runner import FakeController, FakeSession


def _traced_run(
    *,
    variant: str,
    loss: float,
    valid: int,
    source: str = "qwen",
    producer_contract: str | None = None,
    config_hash: str = "h",
) -> RunMetrics:
    identity_version = "legacy-v1" if producer_contract is None else "source-v2"
    result = run_game(
        FakeSession(),
        FakeController(),
        run_id=f"trace-{variant}",
        seed=1,
        variant=variant,
        model_profile="test",
        config_hash=config_hash,
        hypothesis_source=source,
        arm_label=f"{variant}-{'Q' if source == 'qwen' else 'T'}",
        identity_version=identity_version,
        producer_contract_sha256=producer_contract,
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


def test_mechanism_gate_rejects_mixed_sources_and_arm_contracts() -> None:
    with pytest.raises(ValueError, match="mixes hypothesis sources"):
        evaluate_mechanism_gate(
            (
                _traced_run(
                    variant="M",
                    loss=0.1,
                    valid=2,
                    source="template_v1",
                    producer_contract="c" * 64,
                ),
            ),
            (_traced_run(variant="S", loss=0.2, valid=1),),
        )

    with pytest.raises(ValueError, match="config hashes within an arm"):
        evaluate_mechanism_gate(
            (
                _traced_run(variant="M", loss=0.1, valid=2, config_hash="a"),
                _traced_run(variant="M", loss=0.1, valid=2, config_hash="b"),
            ),
            (_traced_run(variant="S", loss=0.2, valid=1),),
        )


def _summary_run(
    game: str,
    variant: str,
    rhae: float,
    *,
    levels: int = 1,
    actions: int = 10,
    wall: float = 10,
    source: str = "qwen",
    producer_contract: str | None = None,
    config_hash: str = "h",
) -> RunMetrics:
    effective_producer_contract = (
        producer_contract
        if producer_contract is not None
        else None
        if source == "qwen"
        else "c" * 64
    )
    result = RunMetrics(
        game + variant + source,
        game,
        1,
        variant,
        "test",
        config_hash,
        hypothesis_source=source,
        arm_label=f"{variant}-{'Q' if source == 'qwen' else 'T'}",
        identity_version=(
            "legacy-v1" if source == "qwen" and producer_contract is None else "source-v2"
        ),
        producer_contract_sha256=effective_producer_contract,
    )
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


def test_development_gate_rejects_mixed_sources_without_exact_selection() -> None:
    runs = (
        _summary_run("a", "X", 0.10),
        _summary_run("a", "M", 0.90),
        _summary_run("a", "X", 0.61, source="template_v1"),
        _summary_run("a", "M", 0.60, source="template_v1"),
    )

    with pytest.raises(ValueError, match="mixes hypothesis sources"):
        evaluate_development_score_gate(runs)

    selected = evaluate_development_score_gate(
        runs,
        hypothesis_source="template_v1",
        treatment_arm="X-T",
        comparator_arm="M-T",
    )
    assert selected.x_mean_rhae == 0.61
    assert selected.m_mean_rhae == 0.60


def test_development_gate_rejects_mixed_producer_contracts_within_qwen() -> None:
    runs = (
        _summary_run("a", "X", 0.61, producer_contract="d" * 64),
        _summary_run("a", "M", 0.60, producer_contract="e" * 64),
    )

    with pytest.raises(ValueError, match="distinct producer contract identities"):
        evaluate_development_score_gate(runs, hypothesis_source="qwen")


def test_development_gate_rejects_multiple_config_hashes_within_one_arm() -> None:
    runs = (
        _summary_run("a", "X", 0.61, config_hash="x1"),
        _summary_run("b", "X", 0.62, config_hash="x2"),
        _summary_run("a", "M", 0.60, config_hash="m"),
        _summary_run("b", "M", 0.60, config_hash="m"),
    )

    with pytest.raises(ValueError, match="config hashes within an arm"):
        evaluate_development_score_gate(runs)


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


def test_confirmation_gate_rejects_mixed_sources_without_exact_selection() -> None:
    runs = (
        _summary_run("a", "X", 0.6),
        _summary_run("a", "M", 0.5),
        _summary_run("a", "X", 0.7, source="template_v1"),
        _summary_run("a", "M", 0.4, source="template_v1"),
    )

    with pytest.raises(ValueError, match="mixes hypothesis sources"):
        evaluate_confirmation_gate(runs, comparator="M", bootstrap_samples=100)

    result = evaluate_confirmation_gate(
        runs,
        comparator="M",
        bootstrap_samples=100,
        hypothesis_source="template_v1",
        treatment_arm="X-T",
        comparator_arm="M-T",
    )
    assert result.summary.mean_delta == pytest.approx(0.3)
