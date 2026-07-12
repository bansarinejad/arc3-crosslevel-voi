from __future__ import annotations

import time
from collections.abc import Hashable
from dataclasses import dataclass

import numpy as np
import pytest

from arc3_voi.planner import (
    BeamSearchPlanner,
    NoValidHypotheses,
    PlanningError,
    committee_agreement,
    committee_indifference,
    level_multiplier,
    prediction_signature,
    robust_exploitation,
    weighted_evsi,
)
from arc3_voi.types import (
    Action,
    ActionKind,
    GameState,
    History,
    Observation,
    Prediction,
)


def _prediction(value: int, *, state: GameState = GameState.NOT_FINISHED) -> Prediction:
    return Prediction(np.full((2, 2), value, dtype=np.int16), state, 0)


def test_hand_calculated_evsi() -> None:
    action_1 = Action(ActionKind.ACTION1)
    action_2 = Action(ActionKind.ACTION2)
    actions = (action_1, action_2)
    costs = {action_1: (1.0, 5.0), action_2: (5.0, 1.0)}
    weights = (0.5, 0.5)

    split_evsi = weighted_evsi((_prediction(0), _prediction(1)), actions, costs, weights)
    no_information = weighted_evsi((_prediction(0), _prediction(0)), actions, costs, weights)

    assert split_evsi == pytest.approx(2.0)
    assert no_information == pytest.approx(0.0)


def test_prediction_signature_is_exact_and_ignores_private_memory() -> None:
    first = Prediction(np.array([[1, 2]], dtype=np.int16), GameState.NOT_FINISHED, 0, {"x": 1})
    same_observable = Prediction(
        np.array([[1, 2]], dtype=np.int16), GameState.NOT_FINISHED, 0, {"x": 999}
    )
    changed = Prediction(np.array([[1, 3]], dtype=np.int16), GameState.NOT_FINISHED, 0)
    assert prediction_signature(first) == prediction_signature(same_observable)
    assert prediction_signature(first) != prediction_signature(changed)


def test_level_multiplier_decreases_to_myopic_on_final_level() -> None:
    multipliers = [level_multiplier(level, 4, 0.5) for level in range(1, 5)]
    assert multipliers == sorted(multipliers, reverse=True)
    assert multipliers[-1] == 1.0
    assert level_multiplier(2, 4, 1.0) > level_multiplier(2, 4, 0.25)


def test_robust_exploitation_and_agreement() -> None:
    action_1 = Action(ActionKind.ACTION1)
    action_2 = Action(ActionKind.ACTION2)
    costs = {action_1: (2.0, 2.0), action_2: (1.0, 5.0)}
    choice = robust_exploitation((action_1, action_2), costs, (0.5, 0.5))
    assert choice.action == action_1
    assert committee_agreement((action_1, action_2), costs, (0.5, 0.5)) == 0.5


def test_agreement_is_bounded_and_order_invariant_under_ties() -> None:
    action_1 = Action(ActionKind.ACTION1)
    action_2 = Action(ActionKind.ACTION2)
    costs = {action_1: (1.0, 2.0), action_2: (1.0, 3.0)}
    weights = (0.4, 0.6)

    assert committee_agreement((action_1, action_2), costs, weights) == 1.0
    assert committee_agreement((action_2, action_1), costs, weights) == 1.0
    assert committee_indifference((action_1, action_2), costs, weights) == pytest.approx(0.4)


def test_all_actions_tied_is_indifference_not_disagreement() -> None:
    action_1 = Action(ActionKind.ACTION1)
    action_2 = Action(ActionKind.ACTION2)
    costs = {action_1: (2.0, 4.0), action_2: (2.0, 4.0)}

    assert committee_agreement((action_1, action_2), costs, (0.5, 0.5)) == 1.0
    assert committee_indifference((action_1, action_2), costs, (0.5, 0.5)) == 1.0


@dataclass
class _OneStepHypothesis:
    hypothesis_id: str = "one-step"
    ast_nodes: int = 3

    def predict(self, history: History, action: Action) -> Prediction:
        if action.kind is ActionKind.ACTION1:
            return Prediction(history.latest_grid, GameState.NOT_FINISHED, 1)
        return Prediction(history.latest_grid, GameState.NOT_FINISHED, 0)

    def goal_value(self, history: History) -> float:
        return 0.0


@dataclass
class _RootFailureHypothesis(_OneStepHypothesis):
    hypothesis_id: str = "root-failure"

    def predict(self, history: History, action: Action) -> Prediction:
        if action.kind is ActionKind.ACTION2:
            raise RuntimeError("invalid generated program")
        return super().predict(history, action)


@dataclass
class _GoalFailureHypothesis(_OneStepHypothesis):
    hypothesis_id: str = "goal-failure"

    def goal_value(self, history: History) -> float:
        del history
        raise RuntimeError("goal function is not total")


@dataclass
class _CountingHypothesis:
    hypothesis_id: str
    ast_nodes: int = 1
    prediction_calls: int = 0
    goal_calls: int = 0

    def predict(self, history: History, action: Action) -> Prediction:
        del action
        self.prediction_calls += 1
        return Prediction(history.latest_grid, GameState.NOT_FINISHED, 0)

    def goal_value(self, history: History) -> float:
        del history
        self.goal_calls += 1
        return 0.0


@dataclass
class _LateRootFailureHypothesis(_CountingHypothesis):
    def predict(self, history: History, action: Action) -> Prediction:
        self.prediction_calls += 1
        if action == _twelve_actions()[-1]:
            raise RuntimeError("last root action fails")
        return Prediction(history.latest_grid, GameState.NOT_FINISHED, 0)


def _twelve_actions() -> tuple[Action, ...]:
    return (
        Action(ActionKind.ACTION1),
        Action(ActionKind.ACTION2),
        Action(ActionKind.ACTION3),
        Action(ActionKind.ACTION4),
        Action(ActionKind.ACTION5),
        Action(ActionKind.ACTION7),
        *(Action(ActionKind.ACTION6, row=index, col=index) for index in range(6)),
    )


def test_beam_planner_assigns_one_to_immediate_completion() -> None:
    observation = Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    history = History.from_observation(observation)
    actions = (Action(ActionKind.ACTION1), Action(ActionKind.ACTION2))
    snapshot = BeamSearchPlanner(depth=4, beam_width=8).evaluate(
        history,
        actions,
        ((_OneStepHypothesis(), 1.0),),
        win_levels=2,
    )
    assert snapshot.costs[actions[0]] == (1.0,)
    # The depth-four search sees that ACTION2 can be followed by ACTION1.
    assert snapshot.costs[actions[1]] == (2.0,)


def test_root_prediction_failure_receives_zero_planning_mass() -> None:
    observation = Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    history = History.from_observation(observation)
    actions = (Action(ActionKind.ACTION1), Action(ActionKind.ACTION2))
    snapshot = BeamSearchPlanner().evaluate(
        history,
        actions,
        ((_OneStepHypothesis(), 0.5), (_RootFailureHypothesis(), 0.5)),
        win_levels=2,
    )
    assert snapshot.hypothesis_ids == ("one-step",)
    assert snapshot.weights == (1.0,)
    assert snapshot.invalid_hypothesis_ids == ("root-failure",)


def test_goal_failure_invalidates_hypothesis_instead_of_substituting_zero() -> None:
    observation = Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    history = History.from_observation(observation)
    actions = (Action(ActionKind.ACTION1), Action(ActionKind.ACTION2))
    snapshot = BeamSearchPlanner().evaluate(
        history,
        actions,
        ((_OneStepHypothesis(), 0.5), (_GoalFailureHypothesis(), 0.5)),
        win_levels=2,
    )

    assert snapshot.hypothesis_ids == ("one-step",)
    assert snapshot.invalid_hypothesis_ids == ("goal-failure",)
    assert snapshot.weights == (1.0,)


def test_goal_failure_with_no_survivor_fails_closed() -> None:
    observation = Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    history = History.from_observation(observation)
    actions = (Action(ActionKind.ACTION1), Action(ActionKind.ACTION2))

    with pytest.raises(NoValidHypotheses) as raised:
        BeamSearchPlanner().evaluate(
            history,
            actions,
            ((_GoalFailureHypothesis(), 1.0),),
            win_levels=2,
        )
    assert raised.value.invalid_hypothesis_ids == ("goal-failure",)


def test_depth_four_beam_eight_has_frozen_worst_case_call_complexity() -> None:
    actions = _twelve_actions()
    observation = Observation(
        np.zeros((4, 4), dtype=np.int16),
        frozenset(action.kind for action in actions),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    hypothesis = _CountingHypothesis("counting")

    BeamSearchPlanner(
        depth=4,
        beam_width=8,
        parallel_hypotheses=False,
    ).evaluate(
        History.from_observation(observation),
        actions,
        ((hypothesis, 1.0),),
        win_levels=2,
    )

    assert hypothesis.prediction_calls == 2460
    assert hypothesis.goal_calls == 2460


def test_all_root_predictions_are_preflighted_before_deep_search() -> None:
    actions = _twelve_actions()
    observation = Observation(
        np.zeros((4, 4), dtype=np.int16),
        frozenset(action.kind for action in actions),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    hypothesis = _LateRootFailureHypothesis("late-root-failure")

    with pytest.raises(NoValidHypotheses):
        BeamSearchPlanner(parallel_hypotheses=False).evaluate(
            History.from_observation(observation),
            actions,
            ((hypothesis, 1.0),),
            win_levels=2,
        )

    assert hypothesis.prediction_calls == len(actions)
    assert hypothesis.goal_calls == 0


def test_parallel_planner_honors_an_expired_shared_deadline() -> None:
    action = Action(ActionKind.ACTION1)
    observation = Observation(
        np.zeros((2, 2), dtype=np.int16),
        frozenset({action.kind}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    hypotheses = (_CountingHypothesis("h0"), _CountingHypothesis("h1"))

    with pytest.raises(PlanningError, match="shared wall-time budget"):
        BeamSearchPlanner(parallel_hypotheses=True).evaluate(
            History.from_observation(observation),
            (action,),
            tuple((hypothesis, 0.5) for hypothesis in hypotheses),
            win_levels=2,
            deadline=time.monotonic() - 1.0,
        )

    assert all(hypothesis.prediction_calls == 0 for hypothesis in hypotheses)


def test_parallel_and_serial_hypothesis_evaluation_are_semantically_equal() -> None:
    actions = _twelve_actions()[:3]
    observation = Observation(
        np.zeros((4, 4), dtype=np.int16),
        frozenset(action.kind for action in actions),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=2,
    )
    history = History.from_observation(observation)
    serial = BeamSearchPlanner(depth=3, beam_width=2, parallel_hypotheses=False).evaluate(
        history,
        actions,
        ((_CountingHypothesis("h0"), 0.4), (_CountingHypothesis("h1"), 0.6)),
        win_levels=2,
    )
    parallel = BeamSearchPlanner(depth=3, beam_width=2, parallel_hypotheses=True).evaluate(
        history,
        actions,
        ((_CountingHypothesis("h0"), 0.4), (_CountingHypothesis("h1"), 0.6)),
        win_levels=2,
    )

    assert parallel.hypothesis_ids == serial.hypothesis_ids
    assert parallel.weights == serial.weights
    assert parallel.costs == serial.costs
    assert {
        action: tuple(prediction_signature(value) for value in predictions)
        for action, predictions in parallel.predictions.items()
    } == {
        action: tuple(prediction_signature(value) for value in predictions)
        for action, predictions in serial.predictions.items()
    }


def test_history_signature_is_memoized_and_includes_available_actions() -> None:
    frame = np.zeros((2, 2), dtype=np.int16)
    common = {
        "frames": (frame,),
        "actions": (None,),
        "game_states": (GameState.NOT_FINISHED,),
        "level_deltas": (0,),
        "levels": (1,),
    }
    first = History(
        **common,
        available_action_sets=(frozenset({ActionKind.ACTION1}),),
    )
    second = History(
        **common,
        available_action_sets=(frozenset({ActionKind.ACTION2}),),
    )
    cache: dict[History, Hashable] = {}

    first_signature = BeamSearchPlanner._history_signature(first, cache)

    assert (
        BeamSearchPlanner._history_signature(first, cache)
        is first_signature
    )
    assert len(cache) == 1
    assert first_signature != BeamSearchPlanner._history_signature(
        second,
        cache,
    )
