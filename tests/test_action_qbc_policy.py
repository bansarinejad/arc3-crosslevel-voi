from __future__ import annotations

import hashlib
import inspect
from collections.abc import Mapping, Sequence
from math import fsum
from types import MappingProxyType

import numpy as np
import pytest

from arc3_voi.action_qbc_policy import (
    ACTION_QBC_POLICY_CONTRACT,
    ACTION_QBC_POLICY_SHA256,
    OUTCOME_CONCENTRATION_THRESHOLD,
    ActionQBCSelection,
    action_qbc_policy_sha256,
    clamp_outcome_concentration,
    normalise_gibbs_weights,
    outcome_concentration,
    partition_exact_outcomes,
    select_action_conditional_qbc,
)
from arc3_voi.planner import (
    PlanningSnapshot,
    committee_agreement,
    prediction_signature,
)
from arc3_voi.types import Action, ActionKind, GameState, Prediction

A1 = Action(ActionKind.ACTION1)
A2 = Action(ActionKind.ACTION2)
A3 = Action(ActionKind.ACTION3)
A4 = Action(ActionKind.ACTION4)


def _prediction(
    label: int,
    *,
    state: GameState = GameState.NOT_FINISHED,
    level_delta: int = 0,
    memory: Mapping[str, object] | None = None,
) -> Prediction:
    return Prediction(
        np.asarray([[label]], dtype=np.int16),
        state,
        level_delta,
        {} if memory is None else memory,
    )


def _snapshot(
    actions: Sequence[Action],
    weights: Sequence[float],
    predictions: Mapping[Action, Sequence[Prediction | None]],
    costs: Mapping[Action, Sequence[float]],
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=tuple(actions),
        hypothesis_ids=tuple(f"h{index}" for index in range(len(weights))),
        weights=tuple(weights),
        predictions={action: tuple(predictions[action]) for action in actions},
        costs={action: tuple(costs[action]) for action in actions},
    )


def _x_only_snapshot() -> PlanningSnapshot:
    first = _prediction(1)
    second = _prediction(2)
    return _snapshot(
        (A1, A2, A3),
        (0.5, 0.5),
        {
            A1: (first, first),
            A2: (second, second),
            A3: (first, second),
        },
        {
            A1: (0.0, 2.0),
            A2: (2.0, 0.0),
            A3: (4.0, 4.0),
        },
    )


def _four_hypothesis_snapshot() -> PlanningSnapshot:
    first = _prediction(1)
    second = _prediction(2)
    third = _prediction(3)
    return _snapshot(
        (A1, A2, A3, A4),
        (0.4, 0.3, 0.2, 0.1),
        {
            A1: (first, first, first, first),
            A2: (second, second, second, second),
            A3: (first, first, second, second),
            A4: (first, second, first, third),
        },
        {
            A1: (0.0, 0.0, 4.0, 4.0),
            A2: (4.0, 4.0, 0.0, 0.0),
            A3: (8.0, 8.0, 8.0, 8.0),
            A4: (9.0, 9.0, 9.0, 9.0),
        },
    )


def _permute_hypotheses(
    snapshot: PlanningSnapshot, permutation: Sequence[int]
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=snapshot.actions,
        hypothesis_ids=tuple(snapshot.hypothesis_ids[index] for index in permutation),
        weights=tuple(snapshot.weights[index] for index in permutation),
        predictions={
            action: tuple(snapshot.predictions[action][index] for index in permutation)
            for action in snapshot.actions
        },
        costs={
            action: tuple(snapshot.costs[action][index] for index in permutation)
            for action in snapshot.actions
        },
    )


def _reorder_candidates(
    snapshot: PlanningSnapshot, actions: Sequence[Action]
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=tuple(actions),
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions={action: snapshot.predictions[action] for action in actions},
        costs={action: snapshot.costs[action] for action in actions},
    )


def _assert_selection_equivalent_by_action(
    left: ActionQBCSelection, right: ActionQBCSelection
) -> None:
    left_selection = left
    right_selection = right
    assert left_selection.normalized_weights == pytest.approx(
        right_selection.normalized_weights, rel=1e-12, abs=1e-12
    )
    for variant in ("m_decision", "x_decision"):
        left_decision = getattr(left_selection, variant)
        right_decision = getattr(right_selection, variant)
        assert (
            left_decision.action,
            left_decision.mode,
            left_decision.gate_reason,
            left_decision.probe_candidate,
        ) == (
            right_decision.action,
            right_decision.mode,
            right_decision.gate_reason,
            right_decision.probe_candidate,
        )
        assert left_decision.score == pytest.approx(
            right_decision.score, rel=1e-12, abs=1e-12
        )
    assert set(left_selection.m_utility_maximizers) == set(
        right_selection.m_utility_maximizers
    )
    assert set(left_selection.x_utility_maximizers) == set(
        right_selection.x_utility_maximizers
    )
    assert left_selection.historical_agreement == pytest.approx(
        right_selection.historical_agreement, rel=1e-12, abs=1e-12
    )
    assert left_selection.historical_indifference == pytest.approx(
        right_selection.historical_indifference, rel=1e-12, abs=1e-12
    )
    left_rows = {row.action: row for row in left_selection.rows}
    right_rows = {row.action: row for row in right_selection.rows}
    assert set(left_rows) == set(right_rows)
    numeric_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    exact_fields = (
        "outcome_cell_count",
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
    )
    for action in left_rows:
        for field in numeric_fields:
            assert getattr(left_rows[action], field) == pytest.approx(
                getattr(right_rows[action], field), rel=1e-12, abs=1e-12
            )
        assert tuple(getattr(left_rows[action], field) for field in exact_fields) == tuple(
            getattr(right_rows[action], field) for field in exact_fields
        )


def test_exact_outcome_cells_use_fsum_weights_and_exclude_memory() -> None:
    same_a = _prediction(1, memory={"private": "a"})
    same_b = _prediction(1, memory={"private": "b"})
    distinct_a = _prediction(2)
    distinct_b = _prediction(3)

    cells = partition_exact_outcomes(
        (same_a, same_b, distinct_a, distinct_b),
        (4.0, 3.0, 2.0, 1.0),
    )

    assert tuple(cell.hypothesis_indices for cell in cells) == ((0, 1), (2,), (3,))
    assert tuple(cell.mass for cell in cells) == pytest.approx((0.7, 0.2, 0.1))
    assert cells[0].signature == prediction_signature(same_a)
    assert prediction_signature(same_a) == prediction_signature(same_b)
    assert outcome_concentration(
        (same_a, same_b, distinct_a, distinct_b),
        (4.0, 3.0, 2.0, 1.0),
    ) == pytest.approx(0.7)


def test_grid_state_and_level_delta_each_change_the_exact_cell() -> None:
    predictions = (
        _prediction(1),
        _prediction(2),
        _prediction(1, state=GameState.GAME_OVER),
        _prediction(1, level_delta=1),
    )
    cells = partition_exact_outcomes(predictions, (1.0, 1.0, 1.0, 1.0))

    assert len(cells) == 4
    assert outcome_concentration(predictions, (1.0,) * 4) == 0.25


def test_outcome_cell_order_is_first_occurrence_but_concentration_is_order_invariant() -> None:
    first = _prediction(1)
    second = _prediction(2)
    original = partition_exact_outcomes((first, second, first), (0.2, 0.3, 0.5))
    reversed_order = partition_exact_outcomes(
        (second, first, first), (0.3, 0.2, 0.5)
    )

    assert original[0].signature == prediction_signature(first)
    assert reversed_order[0].signature == prediction_signature(second)
    assert max(cell.mass for cell in original) == pytest.approx(0.7)
    assert max(cell.mass for cell in reversed_order) == pytest.approx(0.7)


def test_concentration_clamps_only_tolerated_boundary_residue() -> None:
    assert clamp_outcome_concentration(-5e-13) == 0.0
    assert clamp_outcome_concentration(1.0 + 5e-13) == 1.0
    assert clamp_outcome_concentration(1e-15) == 1e-15
    with pytest.raises(ValueError, match="tolerated range"):
        clamp_outcome_concentration(-2e-12)
    with pytest.raises(ValueError, match="tolerated range"):
        clamp_outcome_concentration(1.0 + 2e-12)
    with pytest.raises(ValueError, match="finite"):
        clamp_outcome_concentration(float("nan"))


@pytest.mark.parametrize(
    "weights",
    [(), (0.0, 0.0), (-1.0, 2.0), (float("inf"), 1.0)],
)
def test_invalid_committee_weights_fail_closed(weights: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        normalise_gibbs_weights(weights)


def test_every_policy_quantity_uses_one_shared_normalized_weight_vector() -> None:
    # This normalized planner output lies on a two-value floating-point cycle:
    # normalizing it once changes the tuple, and normalizing that result again
    # changes it back.  It therefore catches accidental double normalization.
    planner_weights = (
        0.12849875032836816,
        0.066438652198944,
        0.30410034239428413,
        0.5009622550784036,
    )
    shared_weights = normalise_gibbs_weights(planner_weights)
    assert normalise_gibbs_weights(shared_weights) != shared_weights
    predictions = (
        _prediction(1),
        _prediction(2),
        _prediction(3),
        _prediction(4, state=GameState.GAME_OVER),
    )
    selection = select_action_conditional_qbc(
        _snapshot(
            (A1,),
            planner_weights,
            {A1: predictions},
            {A1: (0.0, 1.0, 2.0, 3.0)},
        ),
        cross_level_multiplier=2.0,
        probes_used=0,
        probe_cap=3,
    )
    row = selection.rows[0]

    assert selection.normalized_weights == shared_weights
    assert row.outcome_concentration == shared_weights[3]
    assert row.catastrophe_mass == shared_weights[3]
    assert row.exploit_mean_cost == fsum(
        weight * cost
        for weight, cost in zip(shared_weights, (0.0, 1.0, 2.0, 3.0), strict=True)
    )


def test_partition_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="equal length"):
        partition_exact_outcomes((_prediction(1),), (0.5, 0.5))


def test_selector_filters_by_action_specific_concentration_before_ranking() -> None:
    selection = select_action_conditional_qbc(
        _x_only_snapshot(),
        cross_level_multiplier=2.0,
        probes_used=0,
        probe_cap=3,
    )
    rows = {row.action: row for row in selection.rows}

    assert rows[A1].outcome_concentration == 1.0
    assert rows[A2].outcome_concentration == 1.0
    assert rows[A3].outcome_concentration == 0.5
    assert not rows[A1].eligible and not rows[A2].eligible
    assert rows[A3].eligible
    assert rows[A3].evsi == pytest.approx(1.0)
    assert rows[A3].m_utility == pytest.approx(0.0)
    assert rows[A3].x_utility == pytest.approx(1.0)
    assert rows[A3].m_rank == rows[A3].x_rank == 1
    assert not rows[A3].m_selected
    assert rows[A3].x_selected
    assert selection.m_decision.mode == "exploit"
    assert selection.m_decision.action == A1
    assert selection.x_decision.mode == "probe"
    assert selection.x_decision.action == A3


def test_exact_threshold_equality_blocks_even_material_x_utility() -> None:
    first = _prediction(1)
    second = _prediction(2)
    snapshot = _snapshot(
        (A1, A2, A3),
        (0.8, 0.2),
        {A1: (first, first), A2: (second, second), A3: (first, second)},
        {A1: (0.0, 10.0), A2: (10.0, 0.0), A3: (20.0, 20.0)},
    )

    selection = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
        outcome_concentration_threshold=OUTCOME_CONCENTRATION_THRESHOLD,
    )
    row = next(row for row in selection.rows if row.action == A3)

    assert row.outcome_concentration == 0.8
    assert row.x_utility > 0.0
    assert not row.eligible
    assert row.m_rank is None and row.x_rank is None
    assert selection.x_decision.mode == "exploit"
    assert selection.x_decision.gate_reason == "no_disagreement_eligible_action"


def test_live_selector_has_no_admission_only_evsi_materiality_cutoff() -> None:
    first = _prediction(1)
    second = _prediction(2)
    snapshot = _snapshot(
        (A1, A2, A3),
        (0.5, 0.5),
        {A1: (first, first), A2: (second, second), A3: (first, second)},
        {A1: (0.0, 0.098), A2: (0.098, 0.0), A3: (1.0, 1.0)},
    )

    selection = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )
    row = next(row for row in selection.rows if row.action == A3)

    assert row.evsi == pytest.approx(0.049)
    assert row.evsi < 0.05
    assert row.x_utility > 0.0
    assert row.x_selected
    assert selection.x_decision.mode == "probe"


def test_probe_cap_exhaustion_forces_both_variants_to_exploit() -> None:
    selection = select_action_conditional_qbc(
        _x_only_snapshot(),
        cross_level_multiplier=23.0,
        probes_used=3,
        probe_cap=3,
    )

    assert selection.m_decision.mode == "exploit"
    assert selection.x_decision.mode == "exploit"
    assert selection.x_decision.gate_reason == "level_probe_cap_reached"
    assert not any(row.m_selected or row.x_selected for row in selection.rows)


def test_final_level_multiplier_makes_m_and_x_identical() -> None:
    first = _prediction(1)
    second = _prediction(2)
    snapshot = _snapshot(
        (A1, A2, A3),
        (0.5, 0.5),
        {A1: (first, first), A2: (second, second), A3: (first, second)},
        {A1: (0.0, 4.0), A2: (4.0, 0.0), A3: (8.0, 8.0)},
    )

    selection = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=1.0,
        probes_used=0,
        probe_cap=3,
    )

    assert selection.m_decision == selection.x_decision
    assert all(row.m_utility == row.x_utility for row in selection.rows)
    assert all(row.m_rank == row.x_rank for row in selection.rows)
    assert all(row.m_selected == row.x_selected for row in selection.rows)


def test_candidate_ties_use_original_order_and_retain_maximizer_set() -> None:
    first = _prediction(1)
    second = _prediction(2)
    predictions = {
        A1: (first, first),
        A2: (second, second),
        A3: (first, second),
        A4: (first, second),
    }
    costs = {
        A1: (0.0, 4.0),
        A2: (4.0, 0.0),
        A3: (8.0, 8.0),
        A4: (8.0, 8.0),
    }
    forward = select_action_conditional_qbc(
        _snapshot((A1, A2, A3, A4), (0.5, 0.5), predictions, costs),
        cross_level_multiplier=1.0,
        probes_used=0,
        probe_cap=3,
    )
    reversed_candidates = select_action_conditional_qbc(
        _snapshot((A4, A3, A2, A1), (0.5, 0.5), predictions, costs),
        cross_level_multiplier=1.0,
        probes_used=0,
        probe_cap=3,
    )

    assert forward.m_decision.action == A3
    assert reversed_candidates.m_decision.action == A4
    assert set(forward.m_utility_maximizers) == {A3, A4}
    assert set(reversed_candidates.m_utility_maximizers) == {A3, A4}
    assert next(row for row in forward.rows if row.action == A3).m_rank == 1
    assert next(row for row in forward.rows if row.action == A4).m_rank == 2


def test_joint_hypothesis_permutation_preserves_diagnostics_and_decisions() -> None:
    snapshot = _four_hypothesis_snapshot()
    first = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )
    for permutation in ((3, 2, 1, 0), (1, 2, 3, 0)):
        permuted = _permute_hypotheses(snapshot, permutation)
        second = select_action_conditional_qbc(
            permuted,
            cross_level_multiplier=23.0,
            probes_used=0,
            probe_cap=3,
        )
        expected_weights = tuple(first.normalized_weights[index] for index in permutation)
        assert second.normalized_weights == pytest.approx(
            expected_weights, rel=1e-12, abs=1e-12
        )
        # Restore weight order only for the complete by-action comparison.
        second_in_original_weight_order = second
        assert first.m_decision.action == second_in_original_weight_order.m_decision.action
        assert first.x_decision.action == second_in_original_weight_order.x_decision.action
        left_rows = {row.action: row for row in first.rows}
        right_rows = {row.action: row for row in second.rows}
        for action in left_rows:
            for field in (
                "outcome_concentration",
                "evsi",
                "catastrophe_mass",
                "m_utility",
                "x_utility",
                "exploit_mean_cost",
                "exploit_standard_deviation",
                "exploit_score",
            ):
                assert getattr(left_rows[action], field) == pytest.approx(
                    getattr(right_rows[action], field), rel=1e-12, abs=1e-12
                )
            assert (
                left_rows[action].eligible,
                left_rows[action].m_rank,
                left_rows[action].x_rank,
                left_rows[action].m_selected,
                left_rows[action].x_selected,
            ) == (
                right_rows[action].eligible,
                right_rows[action].m_rank,
                right_rows[action].x_rank,
                right_rows[action].m_selected,
                right_rows[action].x_selected,
            )
        assert set(first.m_utility_maximizers) == set(second.m_utility_maximizers)
        assert set(first.x_utility_maximizers) == set(second.x_utility_maximizers)
        assert first.historical_agreement == pytest.approx(
            second.historical_agreement, rel=1e-12, abs=1e-12
        )
        assert first.historical_indifference == pytest.approx(
            second.historical_indifference, rel=1e-12, abs=1e-12
        )


def test_unique_candidate_winner_survives_reversal_and_left_rotation() -> None:
    snapshot = _four_hypothesis_snapshot()
    first = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )
    assert sum(row.eligible for row in first.rows) >= 2
    assert first.x_decision.action == A3

    for actions in ((A4, A3, A2, A1), (A2, A3, A4, A1)):
        permuted = select_action_conditional_qbc(
            _reorder_candidates(snapshot, actions),
            cross_level_multiplier=23.0,
            probes_used=0,
            probe_cap=3,
        )
        _assert_selection_equivalent_by_action(first, permuted)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"probe_cap": 2}, "probe_cap"),
        ({"outcome_concentration_threshold": 0.7}, "outcome_concentration_threshold"),
        ({"risk_coefficient": 2.0}, "risk_coefficient"),
        ({"robust_std_coefficient": 0.25}, "robust_std_coefficient"),
        ({"risk_coefficient": True}, "risk_coefficient"),
    ],
)
def test_selector_rejects_fixed_policy_factor_drift(
    overrides: dict[str, object], message: str
) -> None:
    arguments: dict[str, object] = {
        "cross_level_multiplier": 23.0,
        "probes_used": 0,
        "probe_cap": 3,
        **overrides,
    }
    with pytest.raises(ValueError, match=message):
        select_action_conditional_qbc(_x_only_snapshot(), **arguments)  # type: ignore[arg-type]


def test_selector_rejects_empty_action_snapshot() -> None:
    snapshot = PlanningSnapshot(
        actions=(),
        hypothesis_ids=("h0",),
        weights=(1.0,),
        predictions={},
        costs={},
    )
    with pytest.raises(ValueError, match="at least one candidate"):
        select_action_conditional_qbc(
            snapshot,
            cross_level_multiplier=1.0,
            probes_used=0,
            probe_cap=3,
        )


def test_catastrophe_cost_can_block_an_otherwise_positive_x_probe() -> None:
    safe = _prediction(1)
    catastrophe = _prediction(2, state=GameState.GAME_OVER)
    snapshot = _snapshot(
        (A1, A2, A3),
        (0.5, 0.5),
        {A1: (safe, safe), A2: (catastrophe, catastrophe), A3: (safe, catastrophe)},
        {A1: (0.0, 2.0), A2: (2.0, 0.0), A3: (4.0, 4.0)},
    )

    selection = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=2.0,
        probes_used=0,
        probe_cap=3,
    )
    row = next(row for row in selection.rows if row.action == A3)

    assert row.evsi == pytest.approx(1.0)
    assert row.catastrophe_mass == pytest.approx(0.5)
    assert row.x_utility == pytest.approx(-0.5)
    assert selection.x_decision.mode == "exploit"


def test_selector_rejects_unfiltered_root_failure_and_duplicate_actions() -> None:
    snapshot = _x_only_snapshot()
    failed = PlanningSnapshot(
        actions=snapshot.actions,
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions={**snapshot.predictions, A3: (snapshot.predictions[A3][0], None)},
        costs=snapshot.costs,
    )
    with pytest.raises(ValueError, match="whole-hypothesis filtering"):
        select_action_conditional_qbc(
            failed,
            cross_level_multiplier=2.0,
            probes_used=0,
            probe_cap=3,
        )

    duplicate = PlanningSnapshot(
        actions=(A1, A1),
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions={A1: snapshot.predictions[A1]},
        costs={A1: snapshot.costs[A1]},
    )
    with pytest.raises(ValueError, match="unique"):
        select_action_conditional_qbc(
            duplicate,
            cross_level_multiplier=2.0,
            probes_used=0,
            probe_cap=3,
        )


def test_policy_hash_is_reproducible_and_historical_agreement_source_is_unchanged() -> None:
    assert isinstance(ACTION_QBC_POLICY_CONTRACT, MappingProxyType)
    with pytest.raises(TypeError):
        ACTION_QBC_POLICY_CONTRACT["risk_coefficient"] = 2.0  # type: ignore[index]
    assert action_qbc_policy_sha256() == ACTION_QBC_POLICY_SHA256
    assert len(ACTION_QBC_POLICY_SHA256) == 64
    assert set(ACTION_QBC_POLICY_SHA256) <= set("0123456789abcdef")
    assert hashlib.sha256(inspect.getsource(committee_agreement).encode()).hexdigest() == (
        "5e659e6ad3a3f6e50dd4bfe709b901e29999b031ac5565c5469f0d66a216aa8a"
    )
