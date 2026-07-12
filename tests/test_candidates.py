from __future__ import annotations

import numpy as np

from arc3_voi.candidates import generate_candidates
from arc3_voi.types import ActionKind, GameState


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


def test_click_points_are_deduplicated_clamped_and_capped() -> None:
    grid = np.zeros((4, 4), dtype=np.int16)
    candidates = generate_candidates(
        grid,
        {ActionKind.ACTION6},
        cached_points=[(-3, 99), (-3, 99), (3, 0)],
        max_candidates=2,
    )
    assert len(candidates) == 2
    assert candidates[0].row == 0 and candidates[0].col == 3
    assert candidates[1].row == 3 and candidates[1].col == 0


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
