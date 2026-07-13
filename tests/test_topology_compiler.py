from __future__ import annotations

import hashlib

import numpy as np

from arc3_voi.program import ExecutableHypothesis, candidate_points_from_source
from arc3_voi.runtime.sandbox import MAX_AST_NODES, validate_program
from arc3_voi.structured_templates import instantiate_structured_priors
from arc3_voi.types import Action, ActionKind, GameState, History, Observation


def _observation(grid: np.ndarray) -> Observation:
    return Observation(
        grid,
        frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=4,
    )


def _history(grid: np.ndarray) -> History:
    return History.from_observation(_observation(grid))


def _transition_history(
    before: np.ndarray,
    after: np.ndarray,
    action: Action,
) -> History:
    return _history(before).append(_observation(after), action=action, level_delta=0)


def test_scene_bindings_are_deterministic_and_cover_topological_evidence() -> None:
    grid = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0],
            [0, 2, 2, 2, 2, 2, 0],
            [0, 2, 0, 0, 0, 2, 0],
            [0, 2, 0, 7, 0, 2, 0],
            [0, 2, 0, 0, 0, 2, 0],
            [0, 2, 2, 2, 2, 2, 0],
            [0, 0, 0, 0, 0, 0, 0],
        ],
        dtype=np.int16,
    )

    first = instantiate_structured_priors(_history(grid))
    second = instantiate_structured_priors(_history(grid.copy()))

    assert first == second
    assert [hashlib.sha256(item.source.encode()).hexdigest() for item in first] == [
        hashlib.sha256(item.source.encode()).hexdigest() for item in second
    ]
    bindings = dict(first[0].bindings)
    assert bindings["component_count"] == 2
    assert bindings["containment_pair_count"] >= 1
    assert bindings["primary_contained_count"] >= 1
    assert bindings["primary_symmetry"] == (1, 1, 1)
    assert bindings["recorded_transition_used"] is False


def test_open_bbox_does_not_count_as_topological_enclosure() -> None:
    grid = np.zeros((8, 8), dtype=np.int16)
    grid[1:6, 1] = 2
    grid[1:6, 5] = 2
    grid[5, 1:6] = 2
    grid[3, 3] = 7

    bindings = dict(instantiate_structured_priors(_history(grid))[0].bindings)

    assert bindings["containment_pair_count"] == 0
    assert bindings["primary_contained_count"] == 0


def test_same_latest_scene_with_different_evidence_compiles_different_sources() -> None:
    latest = np.zeros((5, 5), dtype=np.int16)
    latest[2, 2] = 4
    before_zero = latest.copy()
    before_zero[2, 2] = 0
    before_one = latest.copy()
    before_one[2, 2] = 1
    action = Action(ActionKind.ACTION6, row=2, col=2)

    zero_evidence = instantiate_structured_priors(_transition_history(before_zero, latest, action))
    one_evidence = instantiate_structured_priors(_transition_history(before_one, latest, action))

    assert zero_evidence != one_evidence
    assert {dict(item.bindings)["recorded_transition_index"] for item in zero_evidence} == {1}
    assert all("OBSERVED_OLD_ROWS = ('0',)" in item.source for item in zero_evidence)
    assert all("OBSERVED_OLD_ROWS = ('1',)" in item.source for item in one_evidence)


def test_recorded_action6_transition_precedes_every_generic_role() -> None:
    before = np.zeros((6, 6), dtype=np.int16)
    before[2:4, 2:4] = 3
    after = before.copy()
    after[1, 2] = 7
    after[1, 3] = 7
    action = Action(ActionKind.ACTION6, row=2, col=2)
    evidence_history = _transition_history(before, after, action)
    replay_history = _history(before)

    for item in instantiate_structured_priors(evidence_history):
        assert dict(item.bindings)["recorded_changed_count"] == 2
        with ExecutableHypothesis(item.source, timeout_seconds=0.5) as hypothesis:
            prediction = hypothesis.predict(replay_history, action)
        np.testing.assert_array_equal(prediction.next_grid, after)
        assert prediction.memory["evidence"] == 1


def test_most_recent_representable_transition_has_deterministic_precedence() -> None:
    first = np.zeros((6, 6), dtype=np.int16)
    second = first.copy()
    second[1, 1] = 2
    latest = second.copy()
    latest[4, 4] = 7
    first_action = Action(ActionKind.ACTION6, row=1, col=1)
    latest_action = Action(ActionKind.ACTION6, row=4, col=4)
    history = _history(first)
    history = history.append(_observation(second), first_action, level_delta=0)
    history = history.append(_observation(latest), latest_action, level_delta=0)

    compiled = instantiate_structured_priors(history)

    assert {dict(item.bindings)["recorded_transition_index"] for item in compiled} == {2}
    with ExecutableHypothesis(compiled[0].source) as hypothesis:
        prediction = hypothesis.predict(_history(second), latest_action)
    np.testing.assert_array_equal(prediction.next_grid, latest)
    assert prediction.memory["evidence"] == 1


def test_unrelated_scenes_have_unrelated_bindings_without_game_identity() -> None:
    first_grid = np.zeros((5, 7), dtype=np.int16)
    first_grid[1:3, 1:3] = 2
    first_grid[1:3, 5:7] = 2
    second_grid = np.full((7, 5), 9, dtype=np.int16)
    second_grid[3, 2] = 6

    first = instantiate_structured_priors(_history(first_grid))
    second = instantiate_structured_priors(_history(second_grid))

    assert first[0].bindings != second[0].bindings
    assert first[0].source != second[0].source
    for item in (*first, *second):
        lowered = item.source.lower()
        assert "game_id" not in lowered
        assert "bp35" not in lowered
        points = candidate_points_from_source(item.source)
        assert points
        shape = first_grid.shape if item in first else second_grid.shape
        assert all(0 <= row < shape[0] and 0 <= col < shape[1] for row, col in points)


def test_compiled_programs_are_sandboxed_bounded_and_palette_preserving() -> None:
    grid = np.zeros((16, 16), dtype=np.int16)
    grid[1:4, 1:4] = 5
    grid[12:15, 12:15] = 5
    history = _history(grid)
    palette = set(int(value) for value in np.unique(grid))

    for item in instantiate_structured_priors(history):
        validated = validate_program(item.source)
        assert validated.node_count < MAX_AST_NODES
        with ExecutableHypothesis(item.source, timeout_seconds=0.5) as hypothesis:
            prediction = hypothesis.predict(
                history,
                Action(ActionKind.ACTION6, row=15, col=15),
            )
            goal = hypothesis.goal_value(history)
        assert prediction.next_grid.shape == grid.shape
        assert set(int(value) for value in np.unique(prediction.next_grid)) <= palette
        assert 0.0 <= goal <= 1.0
        assert "float(grid.size)" not in item.source


def test_full_canvas_recorded_patch_stays_inside_ast_and_prediction_limits() -> None:
    before = np.zeros((64, 64), dtype=np.int16)
    after = np.ones((64, 64), dtype=np.int16)
    action = Action(ActionKind.ACTION6, row=32, col=32)
    compiled = instantiate_structured_priors(_transition_history(before, after, action))
    replay = _history(before)

    for item in compiled:
        bindings = dict(item.bindings)
        assert bindings["recorded_patch_cells"] == 4096
        assert bindings["recorded_changed_count"] == 4096
        assert validate_program(item.source).node_count < MAX_AST_NODES
        with ExecutableHypothesis(item.source) as hypothesis:
            prediction = hypothesis.predict(replay, action)
        np.testing.assert_array_equal(prediction.next_grid, after)


def test_transition_encoding_rejects_values_outside_visible_arc_palette() -> None:
    valid = np.zeros((3, 3), dtype=np.int16)
    high_before = valid.copy()
    high_before[1, 1] = 16
    low_after = valid.copy()
    low_after[1, 1] = -1
    action = Action(ActionKind.ACTION6, row=1, col=1)

    high = instantiate_structured_priors(_transition_history(high_before, valid, action))
    low = instantiate_structured_priors(_transition_history(valid, low_after, action))

    assert dict(high[0].bindings)["recorded_transition_used"] is False
    assert dict(low[0].bindings)["recorded_transition_used"] is False
