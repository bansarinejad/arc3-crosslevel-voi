from __future__ import annotations

import numpy as np

from arc3_voi.planner import BeamSearchPlanner
from arc3_voi.program import ExecutableHypothesis
from arc3_voi.types import Action, ActionKind, GameState, History, Observation

SOURCE = """
CANDIDATE_POINTS = [(1, 2), (99, 2), (1, 2)]
def predict(history, action):
    return {
        "next_grid": history.frames[-1].copy(),
        "game_state": "NOT_FINISHED",
        "level_delta": 0,
        "memory": {"last_action": action.kind},
    }

def goal_value(history):
    return 0.25
"""


def test_executable_hypothesis_adapts_worker_output() -> None:
    observation = Observation(
        np.zeros((4, 4), dtype=np.int8),
        frozenset({ActionKind.ACTION1}),
        GameState.NOT_FINISHED,
        1,
        2,
    )
    history = History.from_observation(observation)
    with ExecutableHypothesis(SOURCE, timeout_seconds=1.0) as hypothesis:
        prediction = hypothesis.predict(history, Action(ActionKind.ACTION1))
        assert prediction.next_grid.shape == (4, 4)
        assert hypothesis.goal_value(history) == 0.25
        assert hypothesis.candidate_points == ((1, 2),)
        assert hypothesis.prediction_calls == 1
        assert hypothesis.goal_calls == 1


def test_parallel_planner_uses_independent_persistent_workers() -> None:
    observation = Observation(
        np.zeros((4, 4), dtype=np.int8),
        frozenset({ActionKind.ACTION1}),
        GameState.NOT_FINISHED,
        1,
        2,
    )
    history = History.from_observation(observation)
    action = Action(ActionKind.ACTION1)
    with (
        ExecutableHypothesis(SOURCE, timeout_seconds=1.0) as first,
        ExecutableHypothesis(
            SOURCE.replace("return 0.25", "return 0.5"),
            timeout_seconds=1.0,
        ) as second,
    ):
        snapshot = BeamSearchPlanner(
            depth=1,
            beam_width=1,
            parallel_hypotheses=True,
        ).evaluate(
            history,
            (action,),
            ((first, 0.5), (second, 0.5)),
            win_levels=2,
        )

    assert snapshot.hypothesis_ids == (first.hypothesis_id, second.hypothesis_id)
    assert snapshot.costs[action] == (7.0, 6.0)
    assert first.prediction_calls == first.goal_calls == 1
    assert second.prediction_calls == second.goal_calls == 1
