from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from arc3_voi.program import ExecutableHypothesis
from arc3_voi.structured_templates import instantiate_structured_priors
from arc3_voi.types import Action, ActionKind, GameState, History, Observation


def _history(grid: np.ndarray) -> History:
    return History.from_observation(
        Observation(
            grid,
            frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=4,
        )
    )


def _scene() -> np.ndarray:
    grid = np.zeros((14, 16), dtype=np.int16)
    grid[3:5, 3:5] = 2
    grid[3:5, 10:12] = 2
    grid[8:11, 6:9] = 3
    grid[9, 7] = 0
    return grid


def _predict(
    source: str,
    history: History,
    action: Action,
) -> tuple[np.ndarray, float]:
    with ExecutableHypothesis(source, timeout_seconds=0.5) as hypothesis:
        prediction = hypothesis.predict(history, action)
        next_level = history.current_level + prediction.level_delta
        post_history = history.append(
            Observation(
                prediction.next_grid,
                history.latest_action_set,
                prediction.game_state,
                level=next_level,
                win_levels=max(next_level, history.current_level),
            ),
            action=action,
            level_delta=prediction.level_delta,
        )
        goal = hypothesis.goal_value(post_history)
    return prediction.next_grid, goal


def _primary_action(bindings: tuple[tuple[str, object], ...]) -> Action:
    row, col = dict(bindings)["primary_centre"]  # type: ignore[misc]
    return Action(ActionKind.ACTION6, row=int(row), col=int(col))


def _assert_rolewise_equivariance(
    original_grid: np.ndarray,
    transformed_grid: np.ndarray,
    transform_prediction: Callable[[np.ndarray], np.ndarray],
) -> None:
    original = instantiate_structured_priors(_history(original_grid))
    transformed = instantiate_structured_priors(_history(transformed_grid))
    assert [item.role for item in transformed] == [item.role for item in original]

    for before, after in zip(original, transformed, strict=True):
        before_grid, before_goal = _predict(
            before.source,
            _history(original_grid),
            _primary_action(before.bindings),
        )
        after_grid, after_goal = _predict(
            after.source,
            _history(transformed_grid),
            _primary_action(after.bindings),
        )
        np.testing.assert_array_equal(after_grid, transform_prediction(before_grid))
        assert after_goal == pytest.approx(before_goal)


def test_compiler_is_equivariant_to_palette_permutation() -> None:
    grid = _scene()
    mapping = np.arange(16, dtype=np.int16)
    mapping[0], mapping[2], mapping[3] = 7, 11, 5

    _assert_rolewise_equivariance(
        grid,
        mapping[grid],
        lambda prediction: mapping[prediction],
    )


def test_compiler_is_equivariant_to_interior_translation() -> None:
    grid = _scene()
    row_delta, col_delta = 1, 2

    def translate(value: np.ndarray) -> np.ndarray:
        result = np.zeros_like(value)
        result[row_delta:, col_delta:] = value[:-row_delta, :-col_delta]
        return result

    _assert_rolewise_equivariance(grid, translate(grid), translate)


def test_compiler_is_equivariant_to_uniform_integer_scaling() -> None:
    grid = _scene()
    factor = 2

    def scale(value: np.ndarray) -> np.ndarray:
        return np.repeat(np.repeat(value, factor, axis=0), factor, axis=1)

    _assert_rolewise_equivariance(grid, scale(grid), scale)
