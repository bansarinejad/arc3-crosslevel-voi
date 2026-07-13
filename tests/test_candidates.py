from __future__ import annotations

import re
from collections.abc import Sequence
from time import perf_counter

import numpy as np
import pytest

from arc3_voi.candidates import (
    CANDIDATE_POLICY_HASH,
    CANDIDATE_POLICY_VERSION,
    _describe_components,
    candidates_from_history,
    generate_candidates,
)
from arc3_voi.types import Action, ActionKind, GameState, History, Observation


def _clicks(candidates: Sequence[Action]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate.kind is ActionKind.ACTION6:
            assert candidate.row is not None and candidate.col is not None
            result.append((candidate.row, candidate.col))
    return result


def test_preserves_simple_actions_and_maps_click_coordinates() -> None:
    previous = np.zeros((6, 7), dtype=np.int16)
    current = previous.copy()
    current[1:3, 4:6] = 2

    candidates = generate_candidates(
        current,
        {ActionKind.ACTION1, ActionKind.ACTION5, ActionKind.ACTION6, ActionKind.ACTION7},
        previous_grid=previous,
        max_candidates=6,
    )

    assert tuple(action.kind for action in candidates[:3]) == (
        ActionKind.ACTION1,
        ActionKind.ACTION5,
        ActionKind.ACTION7,
    )
    first_click = candidates[3]
    assert first_click.kind is ActionKind.ACTION6
    assert first_click.row in (1, 2)
    assert first_click.col in (4, 5)
    assert first_click.to_official_args() == {"x": first_click.col, "y": first_click.row}


def test_visual_and_proposal_frontiers_receive_reserved_capacity() -> None:
    grid = np.zeros((10, 10), dtype=np.int16)
    grid[4, 4] = 7
    proposals = [(0, 1), (0, 2), (0, 3), (-4, 99)]

    clicks = _clicks(
        generate_candidates(
            grid,
            {ActionKind.ACTION6},
            cached_points=proposals,
            max_candidates=6,
        )
    )

    assert (4, 4) in clicks[:2]
    assert {(0, 1), (0, 2)}.issubset(clicks)
    assert len(clicks) == len(set(clicks)) == 6


def test_single_click_slot_is_explicitly_visual_first() -> None:
    grid = np.zeros((8, 8), dtype=np.int16)
    grid[4, 5] = 7

    clicks = _clicks(
        generate_candidates(
            grid,
            {ActionKind.ACTION6},
            cached_points=[(0, 0)],
            max_candidates=1,
        )
    )

    assert clicks == [(4, 5)]


def test_click_points_are_clamped_deduplicated_and_capped() -> None:
    grid = np.zeros((4, 4), dtype=np.int16)
    candidates = generate_candidates(
        grid,
        {ActionKind.ACTION6},
        cached_points=[(-3, 99), (-3, 99), (3, 0)],
        max_candidates=4,
    )
    clicks = _clicks(candidates)
    assert len(clicks) == len(set(clicks)) == 4
    assert (0, 3) in clicks
    assert (3, 0) in clicks


def test_rare_interior_object_survives_footer_and_proposal_pressure() -> None:
    grid = np.zeros((12, 12), dtype=np.int16)
    grid[-2:, :] = 4
    grid[3, 8] = 9
    proposals = [(0, col) for col in range(8)]

    clicks = _clicks(
        generate_candidates(
            grid,
            {ActionKind.ACTION6},
            cached_points=proposals,
            max_candidates=6,
        )
    )

    assert clicks[0] == (3, 8)
    assert (3, 8) in clicks
    assert sum(row >= 10 for row, _ in clicks) < sum(row == 0 for row, _ in clicks)


def test_changing_footer_cannot_monopolize_visual_slots_under_proposal_pressure() -> None:
    previous = np.zeros((12, 12), dtype=np.int16)
    previous[-2:, :] = 3
    previous[3, 8] = 9
    current = previous.copy()
    current[-2:, :] = 4

    clicks = _clicks(
        generate_candidates(
            current,
            {ActionKind.ACTION6},
            previous_grid=previous,
            cached_points=[(0, col) for col in range(8)],
            max_candidates=6,
        )
    )

    assert clicks[:2] == [(3, 8), (10, 5)]
    assert (3, 8) in clicks
    assert sum(row >= 10 for row, _ in clicks) < 3


def test_normalized_shape_families_share_comparable_structural_capacity() -> None:
    grid = np.zeros((20, 20), dtype=np.int16)
    singleton_points = ((3, 3), (3, 6), (3, 9), (6, 3), (6, 6), (6, 9))
    for point in singleton_points:
        grid[point] = 1
    grid[12:14, 12:14] = 2

    clicks = _clicks(
        generate_candidates(grid, {ActionKind.ACTION6}, max_candidates=4)
    )

    assert clicks[0] in singleton_points
    assert clicks[1] in {(12, 12), (12, 13), (13, 12), (13, 13)}
    assert sum(point in singleton_points for point in clicks) == 2


def test_border_footer_is_penalized_below_equally_sized_interior_object() -> None:
    grid = np.zeros((12, 12), dtype=np.int16)
    grid[-1, 2:5] = 3
    grid[4, 7:10] = 8

    clicks = _clicks(
        generate_candidates(grid, {ActionKind.ACTION6}, max_candidates=2)
    )

    assert all(row == 4 for row, _ in clicks)


def test_containment_requires_exact_enclosed_complement_membership() -> None:
    grid = np.zeros((10, 12), dtype=np.int16)
    # A closed 3x3 ring has an arm that widens its bounding box. The point at
    # (3, 7) lies inside that box but remains connected to the exterior.
    grid[2, 2:9] = 1
    grid[3, 2] = grid[3, 4] = 1
    grid[4, 2:5] = 1
    grid[3, 7] = 2

    components = _describe_components(grid, None)
    enclosed = next(
        item for item in components if item.cells.tolist() == [[3, 3]]
    )
    external = next(
        item for item in components if item.cells.tolist() == [[3, 7]]
    )

    assert enclosed.containment == 2
    assert external.containment == 1


@pytest.mark.parametrize(
    ("action", "level_delta", "next_level"),
    (
        (Action(ActionKind.ACTION6, row=0, col=0), 1, 2),
        (Action(ActionKind.RESET), 0, 1),
    ),
)
def test_history_boundaries_suppress_cross_layout_change_evidence(
    action: Action, level_delta: int, next_level: int
) -> None:
    rows, cols = np.indices((16, 16))
    previous = ((rows + cols) % 2).astype(np.int16)
    current = np.zeros_like(previous)
    current[5, 11] = 7
    available = frozenset({ActionKind.ACTION6})
    history = History.from_observation(
        Observation(previous, available, GameState.NOT_FINISHED, 1, 2)
    ).append(
        Observation(current, available, GameState.NOT_FINISHED, next_level, 2),
        action,
        level_delta,
    )

    actual = candidates_from_history(history, max_candidates=6)
    without_previous = generate_candidates(
        current, available, previous_grid=None, max_candidates=6
    )
    with_previous = generate_candidates(
        current, available, previous_grid=previous, max_candidates=6
    )

    assert actual == without_previous
    assert actual != with_previous


def test_palette_permutation_preserves_complete_frontier() -> None:
    grid = np.zeros((14, 14), dtype=np.int16)
    grid[2:4, 2:4] = 1
    grid[2:4, 9:11] = 1
    grid[7:10, 6:9] = 2
    grid[8, 7] = 0
    grid[-1, :] = 3
    palette = np.asarray([7, 4, 9, 2], dtype=np.int16)

    original = _clicks(
        generate_candidates(grid, {ActionKind.ACTION6}, max_candidates=12)
    )
    permuted = _clicks(
        generate_candidates(palette[grid], {ActionKind.ACTION6}, max_candidates=12)
    )

    assert permuted == original


def test_translation_equivariance_when_border_relations_are_preserved() -> None:
    original = np.zeros((16, 16), dtype=np.int16)
    original[3:5, 4:6] = 5
    translated = np.zeros_like(original)
    translated[6:8, 6:8] = 5

    before = _clicks(
        generate_candidates(original, {ActionKind.ACTION6}, max_candidates=3)
    )
    after = _clicks(
        generate_candidates(translated, {ActionKind.ACTION6}, max_candidates=3)
    )

    assert after == [(row + 3, col + 2) for row, col in before]


def test_uniform_scaling_maps_representatives_into_corresponding_cells() -> None:
    grid = np.zeros((8, 8), dtype=np.int16)
    grid[2:4, 4:6] = 6
    scaled = np.repeat(np.repeat(grid, 3, axis=0), 3, axis=1)

    before = _clicks(
        generate_candidates(grid, {ActionKind.ACTION6}, max_candidates=1)
    )
    after = _clicks(
        generate_candidates(scaled, {ActionKind.ACTION6}, max_candidates=1)
    )

    assert [(row // 3, col // 3) for row, col in after] == before


def test_checkerboard_component_frontier_has_bounded_runtime() -> None:
    rows, cols = np.indices((64, 64))
    checkerboard = ((rows + cols) % 2).astype(np.int16)

    started = perf_counter()
    candidates = generate_candidates(
        checkerboard,
        {ActionKind.ACTION6},
        max_candidates=12,
    )
    elapsed = perf_counter() - started

    assert len(candidates) == 12
    assert elapsed < 2.0


def test_policy_is_deterministic_and_contract_identity_is_stable() -> None:
    grid = np.zeros((9, 11), dtype=np.int16)
    grid[2:5, 7:9] = 2
    previous = np.ones_like(grid)
    cached = [(8, 1), (0, 10), (8, 1)]
    first = generate_candidates(
        grid,
        {ActionKind.ACTION2, ActionKind.ACTION6},
        previous_grid=previous,
        cached_points=cached,
        max_candidates=9,
    )
    for _ in range(10):
        assert (
            generate_candidates(
                grid,
                {ActionKind.ACTION6, ActionKind.ACTION2},
                previous_grid=previous,
                cached_points=cached,
                max_candidates=9,
            )
            == first
        )
    assert CANDIDATE_POLICY_VERSION == "salience-frontier-v1"
    assert re.fullmatch(r"[0-9a-f]{64}", CANDIDATE_POLICY_HASH)
    assert CANDIDATE_POLICY_HASH == (
        "a9220009c5fd4b6da602580db439e25f9acaef74799de050a7a56e6c64bba82c"
    )


def test_game_over_returns_reset_only() -> None:
    candidates = generate_candidates(
        np.zeros((2, 2), dtype=np.int16),
        {ActionKind.ACTION1, ActionKind.ACTION6},
        game_state=GameState.GAME_OVER,
    )
    assert len(candidates) == 1
    assert candidates[0].kind is ActionKind.RESET


def test_reset_is_never_a_speculative_active_candidate() -> None:
    candidates = generate_candidates(
        np.zeros((2, 2), dtype=np.int16),
        {ActionKind.RESET, ActionKind.ACTION2},
    )
    assert [action.kind for action in candidates] == [ActionKind.ACTION2]


def test_refuses_to_drop_simple_actions_when_cap_is_too_small() -> None:
    with pytest.raises(ValueError, match="refusing to silently discard"):
        generate_candidates(
            np.zeros((2, 2), dtype=np.int16),
            {ActionKind.ACTION1, ActionKind.ACTION2, ActionKind.ACTION6},
            max_candidates=1,
        )
