from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from arc3_voi.controller import (
    Controller,
    ControllerBudgetExhausted,
    ControllerConfig,
    Variant,
)
from arc3_voi.hypothesis import HypothesisPool
from arc3_voi.planner import PlanningSnapshot
from arc3_voi.types import (
    Action,
    ActionKind,
    Budget,
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
        return Prediction(
            np.full_like(history.latest_grid, self.value),
            GameState.NOT_FINISHED,
            0,
        )

    def goal_value(self, history: History) -> float:
        return 0.0


class _SnapshotPlanner:
    def __init__(self, *, disagreement: bool) -> None:
        self.disagreement = disagreement

    def evaluate(
        self,
        history: History,
        actions: tuple[Action, ...],
        weighted_hypotheses: tuple[tuple[_Hypothesis, float], ...],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        del history, weighted_hypotheses, win_levels, deadline
        first, second = actions[:2]
        if self.disagreement:
            costs = {first: (1.0, 5.0), second: (5.0, 1.0)}
            first_predictions = (
                Prediction(np.zeros((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0),
                Prediction(np.ones((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0),
            )
            second_predictions = tuple(reversed(first_predictions))
        else:
            costs = {first: (1.0, 1.0), second: (5.0, 5.0)}
            first_predictions = (
                Prediction(np.zeros((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0),
                Prediction(np.zeros((2, 2), dtype=np.int16), GameState.NOT_FINISHED, 0),
            )
            second_predictions = first_predictions
        return PlanningSnapshot(
            actions=(first, second),
            hypothesis_ids=("h0", "h1"),
            weights=(0.5, 0.5),
            predictions={first: first_predictions, second: second_predictions},
            costs=costs,
        )


class _OneSurvivorPlanner(_SnapshotPlanner):
    def evaluate(
        self,
        history: History,
        actions: tuple[Action, ...],
        weighted_hypotheses: tuple[tuple[_Hypothesis, float], ...],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        snapshot = super().evaluate(
            history,
            actions,
            weighted_hypotheses,
            win_levels=win_levels,
            deadline=deadline,
        )
        return PlanningSnapshot(
            actions=snapshot.actions,
            hypothesis_ids=(snapshot.hypothesis_ids[0],),
            weights=(1.0,),
            predictions={
                action: (predictions[0],)
                for action, predictions in snapshot.predictions.items()
            },
            costs={action: (costs[0],) for action, costs in snapshot.costs.items()},
        )


def _observation(
    *, state: GameState = GameState.NOT_FINISHED, level: int = 1
) -> Observation:
    return Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        state,
        level=level,
        win_levels=3,
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


def test_insufficient_committee_uses_direct_fallback_callback() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(1),
        config=ControllerConfig(variant=Variant.CROSS_LEVEL),
    )
    decision = controller.act(_observation(), Budget())
    assert decision.mode is DecisionMode.DIRECT_FALLBACK
    assert decision.action.kind is ActionKind.ACTION2
    assert decision.diagnostics["reason"] == "insufficient_valid_hypotheses"


def test_planner_root_failures_trigger_direct_fallback() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=_OneSurvivorPlanner(disagreement=True),  # type: ignore[arg-type]
        config=ControllerConfig(variant=Variant.CROSS_LEVEL),
    )
    decision = controller.act(_observation(), Budget())
    assert decision.mode is DecisionMode.DIRECT_FALLBACK
    assert decision.diagnostics["reason"] == "planner_invalidated_hypotheses"


def test_cross_level_controller_probes_when_disagreement_has_positive_value() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=_SnapshotPlanner(disagreement=True),  # type: ignore[arg-type]
        config=ControllerConfig(variant=Variant.CROSS_LEVEL),
    )
    decision = controller.act(_observation(), Budget())
    assert decision.mode is DecisionMode.PROBE
    assert decision.diagnostics["probe_evsi"] == pytest.approx(2.0)
    assert decision.diagnostics["level_multiplier"] > 1.0


def test_controller_exploits_when_committee_agrees() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=_SnapshotPlanner(disagreement=False),  # type: ignore[arg-type]
        config=ControllerConfig(variant=Variant.CROSS_LEVEL),
    )
    decision = controller.act(_observation(), Budget())
    assert decision.mode is DecisionMode.EXPLOIT
    assert decision.action.kind is ActionKind.ACTION1


def test_probe_cap_is_enforced_per_level() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=_SnapshotPlanner(disagreement=True),  # type: ignore[arg-type]
        config=ControllerConfig(variant=Variant.CROSS_LEVEL, max_probes_per_level=3),
    )
    modes = []
    for _ in range(4):
        modes.append(controller.act(_observation(), Budget()).mode)
    assert modes == [
        DecisionMode.PROBE,
        DecisionMode.PROBE,
        DecisionMode.PROBE,
        DecisionMode.EXPLOIT,
    ]


def test_game_over_is_reset_only_and_active_play_never_resets() -> None:
    active = Controller(
        direct_policy=_direct_policy,
        config=ControllerConfig(variant=Variant.DIRECT),
    )
    assert active.act(_observation(), Budget()).action.kind is not ActionKind.RESET

    terminal = Controller(
        direct_policy=_direct_policy,
        config=ControllerConfig(variant=Variant.DIRECT),
    )
    decision = terminal.act(_observation(state=GameState.GAME_OVER), Budget())
    assert decision.action.kind is ActionKind.RESET


def test_environment_action_budget_is_enforced() -> None:
    controller = Controller(direct_policy=_direct_policy)
    budget = Budget(environment_actions_used=256)
    with pytest.raises(ControllerBudgetExhausted):
        controller.act(_observation(), budget)


def test_cross_level_persistence_updates_after_two_new_level_transitions() -> None:
    controller = Controller(
        direct_policy=_direct_policy,
        pool=_pool(),
        planner=_SnapshotPlanner(disagreement=False),  # type: ignore[arg-type]
        config=ControllerConfig(variant=Variant.CROSS_LEVEL),
    )
    controller.act(_observation(level=1), Budget())
    controller.act(_observation(level=2), Budget())  # boundary itself is excluded
    controller.act(_observation(level=2), Budget())
    controller.act(_observation(level=2), Budget())
    assert controller.persistence.trials == 1
    assert controller.persistence.successes == 1
