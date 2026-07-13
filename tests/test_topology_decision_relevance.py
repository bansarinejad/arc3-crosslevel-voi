from __future__ import annotations

from contextlib import ExitStack
from math import isclose

import numpy as np
import pytest

from arc3_voi.candidates import candidates_from_history
from arc3_voi.config import load_config
from arc3_voi.hypothesis import HypothesisPool
from arc3_voi.planner import (
    BeamSearchPlanner,
    catastrophe_probability,
    committee_agreement,
    committee_indifference,
    level_multiplier,
    probe_utility,
    weighted_evsi,
)
from arc3_voi.program import ExecutableHypothesis, candidate_points_from_source
from arc3_voi.runtime_admission import (
    INITIAL_CROSS_LEVEL_PERSISTENCE,
    MATERIAL_EVSI_THRESHOLD,
    x_only_probe_actions,
)
from arc3_voi.structured_templates import STRUCTURED_PRIOR_ROLES, instantiate_structured_priors
from arc3_voi.types import Action, ActionKind, GameState, History, Observation, Prediction


def _synthetic_history() -> History:
    """Palette-neutral topology fixture; it encodes no game identity or transition evidence."""

    grid = np.zeros((18, 22), dtype=np.int16)
    grid[3:5, 3:5] = 2
    grid[3:5, 13:15] = 2
    grid[10:13, 8:11] = 3
    grid[11, 9] = 0
    return History.from_observation(
        Observation(
            grid,
            frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=9,
        )
    )


def _compiled_candidates(history: History) -> tuple[Action, ...]:
    compiled = instantiate_structured_priors(history)
    cached_points: list[tuple[int, int]] = []
    for item in compiled:
        for point in candidate_points_from_source(item.source):
            if point not in cached_points:
                cached_points.append(point)
    return candidates_from_history(history, cached_points=cached_points, max_candidates=12)


def _post_action_history(
    history: History,
    action: Action,
    prediction: Prediction,
) -> History:
    next_level = history.current_level + prediction.level_delta
    return history.append(
        Observation(
            prediction.next_grid,
            history.latest_action_set,
            prediction.game_state,
            level=next_level,
            win_levels=9,
        ),
        action=action,
        level_delta=prediction.level_delta,
    )


def _action_name(action: Action) -> str:
    if action.kind is ActionKind.ACTION6:
        return f"ACTION6({action.row},{action.col})"
    return action.kind.name


def test_scene_compiler_graded_roles_have_root_prediction_and_goal_variation() -> None:
    history = _synthetic_history()
    compiled = instantiate_structured_priors(history)
    actions = _compiled_candidates(history)

    assert tuple(item.role for item in compiled) == STRUCTURED_PRIOR_ROLES
    assert all(dict(item.bindings)["recorded_transition_used"] is False for item in compiled)
    assert Action(ActionKind.ACTION6, row=3, col=3) in actions
    assert Action(ActionKind.ACTION6, row=3, col=13) in actions
    assert Action(ActionKind.ACTION6, row=10, col=9) in actions

    with ExitStack() as stack:
        hypotheses = tuple(
            stack.enter_context(ExecutableHypothesis(item.source, timeout_seconds=0.5))
            for item in compiled
        )
        action_varying_predictions = 0
        composite_behaviors: list[tuple[tuple[object, ...], tuple[float, ...]]] = []
        for hypothesis in hypotheses[1:]:
            predictions = tuple(hypothesis.predict(history, action) for action in actions)
            goals = tuple(
                hypothesis.goal_value(_post_action_history(history, action, prediction))
                for action, prediction in zip(actions, predictions, strict=True)
            )

            signatures = tuple(prediction.signature() for prediction in predictions)
            action_varying_predictions += len(set(signatures)) >= 2
            assert max(goals) - min(goals) > 1e-12
            composite_behaviors.append((signatures, goals))
            assert all(
                prediction.game_state is GameState.NOT_FINISHED
                for prediction in predictions
            )
            assert all(prediction.level_delta == 0 for prediction in predictions)
            assert all(
                set(int(value) for value in np.unique(prediction.next_grid)) <= {0, 2, 3}
                for prediction in predictions
            )
        assert action_varying_predictions >= 2
        assert len(set(composite_behaviors)) == 3


def test_path_deficit_v2_fails_frozen_weighted_depth_four_bridge() -> None:
    """Preserve the preregistered synthetic failure without weakening its gate."""

    history = _synthetic_history()
    compiled = instantiate_structured_priors(history)
    actions = _compiled_candidates(history)
    config = load_config("configs/template_v1_path_deficit_v2_x.yaml")

    with ExitStack() as stack:
        hypotheses = tuple(
            stack.enter_context(ExecutableHypothesis(item.source, timeout_seconds=0.5))
            for item in compiled
        )
        pool = HypothesisPool.from_hypotheses(
            hypotheses,
            eta=config.hypotheses.eta,
            complexity_lambda=config.hypotheses.complexity_lambda,
            max_hypotheses=config.hypotheses.max_hypotheses,
        )
        planner = BeamSearchPlanner(
            depth=config.planning.depth,
            beam_width=config.planning.beam_width,
            completion_cost_policy=config.planning.completion_cost_policy_version,
        )
        snapshot = planner.evaluate(
            history,
            actions,
            pool.weighted_hypotheses,
            win_levels=9,
        )

    assert snapshot.hypothesis_ids == tuple(
        hypothesis.hypothesis_id for hypothesis in hypotheses
    )
    assert not snapshot.invalid_hypothesis_ids

    graded_action_varying = 0
    optimal_sets: list[frozenset[Action]] = []
    for hypothesis_index in range(1, 4):
        role_costs = tuple(snapshot.costs[action][hypothesis_index] for action in actions)
        if max(role_costs) - min(role_costs) > 1e-12:
            graded_action_varying += 1
        best = min(role_costs)
        optimal_sets.append(
            frozenset(
                action
                for action, cost in zip(actions, role_costs, strict=True)
                if isclose(cost, best, rel_tol=1e-12, abs_tol=1e-12)
            )
        )
    assert graded_action_varying >= 2
    assert len(set(optimal_sets)) >= 2

    agreement = committee_agreement(actions, snapshot.costs, snapshot.weights)
    assert snapshot.weights == pytest.approx(
        (0.4116174747, 0.2241004657, 0.2060449726, 0.1582370870)
    )
    assert agreement == pytest.approx(0.8417629130389278)
    assert agreement >= config.planning.agreement_threshold
    assert committee_indifference(actions, snapshot.costs, snapshot.weights) < 1.0

    cross_level_multiplier = level_multiplier(
        history.current_level,
        9,
        INITIAL_CROSS_LEVEL_PERSISTENCE,
    )
    assert cross_level_multiplier == 23.0
    rows: list[dict[str, object]] = []
    for action in actions:
        predictions = snapshot.predictions[action]
        evsi = weighted_evsi(predictions, actions, snapshot.costs, snapshot.weights)
        catastrophe = catastrophe_probability(predictions, snapshot.weights)
        rows.append(
            {
                "action": _action_name(action),
                "evsi": evsi,
                "myopic_utility": probe_utility(evsi, 1.0, catastrophe),
                "cross_level_utility": probe_utility(
                    evsi,
                    cross_level_multiplier,
                    catastrophe,
                ),
            }
        )

    assert max(float(row["evsi"]) for row in rows) == pytest.approx(
        0.048123650158264475
    )
    assert max(float(row["evsi"]) for row in rows) < MATERIAL_EVSI_THRESHOLD
    assert not x_only_probe_actions(
        rows,
        agreement=agreement,
        agreement_threshold=config.planning.agreement_threshold,
    )
