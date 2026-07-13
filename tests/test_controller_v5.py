from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

import arc3_voi.controller_v5 as controller_v5_module
from arc3_voi.action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    OUTCOME_CONCENTRATION_THRESHOLD,
)
from arc3_voi.action_qbc_policy import (
    select_action_conditional_qbc as pure_action_qbc_selector,
)
from arc3_voi.controller import Variant
from arc3_voi.controller_v5 import V5Controller, V5ControllerConfig
from arc3_voi.hypothesis import Hypothesis, HypothesisPool
from arc3_voi.planner import (
    COMPLETION_COST_POLICY_HASHES,
    ENDPOINT_COMPLETION_COST_POLICY,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
    PlanningSnapshot,
)
from arc3_voi.types import (
    Action,
    ActionKind,
    Budget,
    Decision,
    DecisionMode,
    GameState,
    History,
    Observation,
    Prediction,
)


@dataclass
class _Hypothesis:
    hypothesis_id: str
    value: int
    ast_nodes: int = 1

    def predict(self, history: History, action: Action) -> Prediction:
        del action
        return Prediction(
            np.full_like(history.latest_grid, self.value),
            GameState.NOT_FINISHED,
            0,
        )

    def goal_value(self, history: History) -> float:
        del history
        return 0.0


class _XOnlyPlanner:
    """The registered X-only mechanism region, expressed as an open fixture."""

    completion_cost_policy = PATH_DEFICIT_COMPLETION_COST_POLICY
    completion_cost_policy_sha256 = COMPLETION_COST_POLICY_HASHES[
        PATH_DEFICIT_COMPLETION_COST_POLICY
    ]

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        del history, win_levels, deadline
        assert len(weighted_hypotheses) == 2
        action1 = Action(ActionKind.ACTION1)
        action2 = Action(ActionKind.ACTION2)
        action3 = Action(ActionKind.ACTION3)
        assert all(action in actions for action in (action1, action2, action3))
        first = Prediction(
            np.zeros((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0
        )
        second = Prediction(
            np.ones((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0
        )
        return PlanningSnapshot(
            actions=(action1, action2, action3),
            hypothesis_ids=("h0", "h1"),
            weights=(0.5, 0.5),
            predictions={
                action1: (first, first),
                action2: (second, second),
                action3: (first, second),
            },
            costs={
                action1: (0.0, 2.0),
                action2: (2.0, 0.0),
                action3: (4.0, 4.0),
            },
        )


class _SinglePlanner:
    completion_cost_policy = PATH_DEFICIT_COMPLETION_COST_POLICY
    completion_cost_policy_sha256 = COMPLETION_COST_POLICY_HASHES[
        PATH_DEFICIT_COMPLETION_COST_POLICY
    ]

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        del history, win_levels, deadline
        assert len(weighted_hypotheses) == 1
        action = actions[0]
        prediction = Prediction(
            np.zeros((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0
        )
        return PlanningSnapshot(
            actions=(action,),
            hypothesis_ids=("h0",),
            weights=(1.0,),
            predictions={action: (prediction,)},
            costs={action: (0.0,)},
        )


def _observation(
    *,
    state: GameState = GameState.NOT_FINISHED,
    level: int = 1,
    win_levels: int = 9,
) -> Observation:
    return Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset(
            {ActionKind.ACTION1, ActionKind.ACTION2, ActionKind.ACTION3}
        ),
        state,
        level=level,
        win_levels=win_levels,
    )


def _pool(size: int = 2) -> HypothesisPool:
    return HypothesisPool.from_hypotheses(
        [_Hypothesis(f"h{index}", index) for index in range(size)],
        effective_pool_refresh_threshold=1.0,
    )


def _direct_policy(
    history: History, candidates: tuple[Action, ...], budget: Budget
) -> Action:
    del history, budget
    return candidates[-1]


def _assert_policy_identity(decision: Decision) -> None:
    assert (
        decision.diagnostics["implementation_contract_version"]
        == ACTION_QBC_RUNTIME_VERSION
    )
    assert (
        decision.diagnostics["probe_disagreement_policy_version"]
        == ACTION_QBC_POLICY_VERSION
    )
    assert (
        decision.diagnostics["probe_disagreement_policy_sha256"]
        == ACTION_QBC_POLICY_SHA256
    )
    assert (
        decision.diagnostics["outcome_concentration_threshold"]
        == OUTCOME_CONCENTRATION_THRESHOLD
    )


def _controller(variant: Variant, *, pool: HypothesisPool | None = None) -> V5Controller:
    return V5Controller(
        direct_policy=_direct_policy,
        pool=_pool() if pool is None else pool,
        planner=_XOnlyPlanner(),
        config=V5ControllerConfig(variant=variant),
    )


def test_injected_planner_must_attest_the_frozen_completion_policy() -> None:
    planner = _XOnlyPlanner()
    planner.completion_cost_policy = ENDPOINT_COMPLETION_COST_POLICY
    planner.completion_cost_policy_sha256 = COMPLETION_COST_POLICY_HASHES[
        ENDPOINT_COMPLETION_COST_POLICY
    ]

    with pytest.raises(ValueError, match="planner delegate lacks the frozen"):
        V5Controller(
            direct_policy=_direct_policy,
            pool=_pool(),
            planner=planner,
        )


def test_m_and_x_decisions_come_from_the_same_x_only_snapshot() -> None:
    myopic = _controller(Variant.MYOPIC)
    cross_level = _controller(Variant.CROSS_LEVEL)

    m_decision = myopic.act(_observation(), Budget())
    x_decision = cross_level.act(_observation(), Budget())

    assert m_decision.mode is DecisionMode.EXPLOIT
    assert m_decision.action == Action(ActionKind.ACTION1)
    assert x_decision.mode is DecisionMode.PROBE
    assert x_decision.action == Action(ActionKind.ACTION3)
    assert m_decision.diagnostics["x_level_multiplier"] == pytest.approx(23.0)
    assert x_decision.diagnostics["x_level_multiplier"] == pytest.approx(23.0)
    assert (
        m_decision.diagnostics["action_qbc_candidate_rows"]
        == x_decision.diagnostics["action_qbc_candidate_rows"]
    )

    rows = json.loads(str(x_decision.diagnostics["action_qbc_candidate_rows"]))
    assert [row["action"]["kind"] for row in rows] == [
        "ACTION1",
        "ACTION2",
        "ACTION3",
    ]
    assert [row["outcome_concentration"] for row in rows] == [1.0, 1.0, 0.5]
    assert [row["eligible"] for row in rows] == [False, False, True]
    assert [row["m_selected"] for row in rows] == [False, False, False]
    assert [row["x_selected"] for row in rows] == [False, False, True]
    assert rows[2]["evsi"] == pytest.approx(1.0)
    assert rows[2]["m_utility"] == pytest.approx(0.0)
    assert rows[2]["x_utility"] == pytest.approx(22.0)
    assert m_decision.diagnostics["m_decision_action"] == "ACTION1"
    assert m_decision.diagnostics["m_decision_mode"] == "exploit"
    assert x_decision.diagnostics["x_decision_action"] == "ACTION3"
    assert x_decision.diagnostics["x_decision_mode"] == "probe"
    _assert_policy_identity(m_decision)
    _assert_policy_identity(x_decision)


def test_successful_committee_decision_calls_pure_selector_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pure_action_qbc_selector
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(controller_v5_module, "select_action_conditional_qbc", spy)
    decision = _controller(Variant.CROSS_LEVEL).act(_observation(), Budget())

    assert decision.mode is DecisionMode.PROBE
    assert len(calls) == 1


@pytest.mark.parametrize("variant", [Variant.DIRECT, Variant.SINGLE])
def test_d_and_s_carry_policy_identity_without_candidate_rows(variant: Variant) -> None:
    planner = _SinglePlanner() if variant is Variant.SINGLE else _XOnlyPlanner()
    controller = V5Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=planner,
        config=V5ControllerConfig(variant=variant),
    )

    decision = controller.act(_observation(), Budget())

    _assert_policy_identity(decision)
    assert "action_qbc_candidate_rows" not in decision.diagnostics


def test_direct_fallback_carries_policy_identity_without_candidate_rows() -> None:
    controller = V5Controller(
        direct_policy=_direct_policy,
        pool=_pool(1),
        planner=_XOnlyPlanner(),
        config=V5ControllerConfig(variant=Variant.CROSS_LEVEL),
    )

    decision = controller.act(_observation(), Budget())

    assert decision.mode is DecisionMode.DIRECT_FALLBACK
    assert decision.diagnostics["reason"] == "insufficient_valid_hypotheses"
    _assert_policy_identity(decision)
    assert "action_qbc_candidate_rows" not in decision.diagnostics


def test_game_over_lifecycle_carries_policy_identity_without_candidate_rows() -> None:
    controller = _controller(Variant.CROSS_LEVEL)

    decision = controller.act(_observation(state=GameState.GAME_OVER), Budget())

    assert decision.mode is DecisionMode.LIFECYCLE
    assert decision.action == Action(ActionKind.RESET)
    assert decision.diagnostics["reason"] == "game_over_reset"
    _assert_policy_identity(decision)
    assert "action_qbc_candidate_rows" not in decision.diagnostics


def test_refresh_preserves_mode_and_counts_only_post_refresh_probe_once() -> None:
    refresh_calls = 0

    def refresh(history: History, budget: Budget) -> HypothesisPool:
        nonlocal refresh_calls
        del history, budget
        refresh_calls += 1
        return _pool()

    controller = V5Controller(
        direct_policy=_direct_policy,
        refresh_callback=refresh,
        planner=_XOnlyPlanner(),
        config=V5ControllerConfig(variant=Variant.CROSS_LEVEL),
    )

    decision = controller.act(_observation(), Budget())

    assert refresh_calls == 1
    assert decision.mode is DecisionMode.REFRESH
    assert decision.action == Action(ActionKind.ACTION3)
    assert decision.diagnostics["post_refresh_mode"] == "probe"
    assert decision.diagnostics["probe_count_before"] == 0
    assert decision.diagnostics["probe_count_after"] == 1
    assert controller.probes_by_level == {1: 1}


def test_probe_cap_is_enforced_without_double_counting_parent_selection() -> None:
    controller = _controller(Variant.CROSS_LEVEL)

    decisions = [controller.act(_observation(), Budget()) for _ in range(4)]

    assert [decision.mode for decision in decisions] == [
        DecisionMode.PROBE,
        DecisionMode.PROBE,
        DecisionMode.PROBE,
        DecisionMode.EXPLOIT,
    ]
    assert [decision.diagnostics["probe_count_after"] for decision in decisions] == [
        1,
        2,
        3,
        3,
    ]
    assert decisions[-1].diagnostics["probe_gate_reason"] == "level_probe_cap_reached"
    assert controller.probes_by_level == {1: 3}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation_contract_version", "runtime-drift"),
        ("max_candidates", 11),
        ("depth", 3),
        ("beam_width", 7),
        ("max_probes_per_level", 2),
        ("risk_coefficient", 2.0),
        ("robust_std_coefficient", 0.25),
        ("max_refreshes_per_level", 2),
        ("max_generation_batches", 2),
        ("completion_cost_policy_version", "completion-drift"),
        ("completion_cost_policy_sha256", "0" * 64),
        ("probe_disagreement_policy_version", "probe-drift"),
        ("probe_disagreement_policy_sha256", "0" * 64),
        ("outcome_concentration_threshold", 0.7),
    ],
)
def test_v5_controller_config_rejects_contract_drift(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=rf"runtime-v5 controller contract drift: {field}"):
        V5ControllerConfig(**{field: value})  # type: ignore[arg-type]
