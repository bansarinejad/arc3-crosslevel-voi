"""Deterministic, visually grounded ARC-AGI-3 action candidates.

The official interface exposes a small set of parameter-free actions and one
coordinate action (``ACTION6``).  Enumerating every pixel for the latter would
make model-based search intractable, so this module constructs a small set of
high-value click locations without ever dropping a currently valid simple
action.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from arc3_voi.types import Action, ActionKind, GameState, History

Grid = NDArray[np.integer]
Point = tuple[int, int]


@dataclass(frozen=True, order=True, slots=True)
class _RankedPoint:
    """A click point ordered by source priority, salience, then coordinates."""

    priority: int
    negative_area: int
    row: int
    col: int


def _stable_grid(frame: NDArray[np.generic] | Sequence[object]) -> Grid:
    """Return the last stable 2-D grid from a frame or short frame sequence."""

    grid = np.asarray(frame)
    if grid.ndim == 3:
        grid = grid[-1]
    if grid.ndim != 2:
        raise ValueError(f"expected a 2-D grid (or frame sequence), got shape {grid.shape}")
    return grid


def _components(mask: NDArray[np.bool_]) -> list[NDArray[np.int64]]:
    """Find deterministic four-connected components in a boolean mask."""

    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    result: list[NDArray[np.int64]] = []
    for start_row, start_col in np.argwhere(mask):
        row = int(start_row)
        col = int(start_col)
        if seen[row, col]:
            continue
        seen[row, col] = True
        stack = [(row, col)]
        cells: list[Point] = []
        while stack:
            cell_row, cell_col = stack.pop()
            cells.append((cell_row, cell_col))
            for next_row, next_col in (
                (cell_row - 1, cell_col),
                (cell_row + 1, cell_col),
                (cell_row, cell_col - 1),
                (cell_row, cell_col + 1),
            ):
                if (
                    0 <= next_row < height
                    and 0 <= next_col < width
                    and mask[next_row, next_col]
                    and not seen[next_row, next_col]
                ):
                    seen[next_row, next_col] = True
                    stack.append((next_row, next_col))
        result.append(np.asarray(cells, dtype=np.int64))
    return result


def _nearest_component_cell(component: NDArray[np.int64], target: tuple[float, float]) -> Point:
    """Choose the real component pixel nearest a possibly non-integral target."""

    delta = component.astype(np.float64) - np.asarray(target, dtype=np.float64)
    squared_distance = np.square(delta).sum(axis=1)
    # lexsort makes equal-distance choices stable across platforms.
    order = np.lexsort((component[:, 1], component[:, 0], squared_distance))
    row, col = component[int(order[0])]
    return int(row), int(col)


def _component_points(
    component: NDArray[np.int64], *, center_priority: int, extrema_priority: int
) -> list[_RankedPoint]:
    area = int(component.shape[0])
    center = tuple(component.mean(axis=0))
    points = [
        _RankedPoint(center_priority, -area, *_nearest_component_cell(component, center))
    ]

    center_row, center_col = center
    extrema_targets = (
        (float(component[:, 0].min()), center_col),
        (float(component[:, 0].max()), center_col),
        (center_row, float(component[:, 1].min())),
        (center_row, float(component[:, 1].max())),
    )
    points.extend(
        _RankedPoint(
            extrema_priority,
            -area,
            *_nearest_component_cell(component, target),
        )
        for target in extrema_targets
    )
    return points


def _visual_points(current: Grid, previous: Grid | None) -> list[_RankedPoint]:
    ranked: list[_RankedPoint] = []

    if previous is not None and previous.shape == current.shape:
        changed = current != previous
        for component in _components(changed):
            ranked.extend(
                _component_points(component, center_priority=0, extrema_priority=1)
            )

    values, counts = np.unique(current, return_counts=True)
    if values.size:
        background = values[int(np.argmax(counts))]
        foreground = current != background
        # Split by colour as well as connectivity: adjacent objects of different
        # colours often have different interaction semantics.
        for colour in values:
            if colour == background:
                continue
            for component in _components(foreground & (current == colour)):
                ranked.extend(
                    _component_points(component, center_priority=2, extrema_priority=3)
                )
    return ranked


def _coerce_kind(value: Action | ActionKind | int | str) -> ActionKind:
    if isinstance(value, Action):
        return value.kind
    if isinstance(value, ActionKind):
        return value
    if isinstance(value, str):
        name = value.upper()
        if name.isdigit():
            return ActionKind(int(name))
        return ActionKind[name]
    return ActionKind(int(value))


def generate_candidates(
    current_grid: NDArray[np.generic] | Sequence[object],
    available_actions: Iterable[Action | ActionKind | int | str],
    *,
    previous_grid: NDArray[np.generic] | Sequence[object] | None = None,
    cached_points: Iterable[Point] = (),
    game_state: GameState | str = GameState.NOT_FINISHED,
    max_candidates: int = 12,
) -> tuple[Action, ...]:
    """Build a capped, deterministic action set for one stable observation.

    All available simple actions are retained.  Remaining slots are assigned to
    visually grounded ``ACTION6`` locations in this order: changed-component
    centres, changed extrema, foreground-component centres/extrema, cached model
    suggestions, and finally the display centre.
    """

    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    state_name = game_state.value if isinstance(game_state, GameState) else str(game_state)
    if state_name.upper().split(".")[-1] == GameState.GAME_OVER.value:
        return (Action(ActionKind.RESET),)

    kinds = {_coerce_kind(action) for action in available_actions}
    # RESET starts or restarts a terminated session.  It is never a speculative
    # in-game action, even if a wrapper accidentally leaves it in action_space.
    kinds.discard(ActionKind.RESET)
    simple_kinds = sorted((kind for kind in kinds if kind != ActionKind.ACTION6), key=int)
    if len(simple_kinds) > max_candidates:
        raise ValueError(
            "max_candidates is smaller than the number of valid simple actions; "
            "refusing to silently discard an official action"
        )
    actions = [Action(kind) for kind in simple_kinds]
    if ActionKind.ACTION6 not in kinds or len(actions) == max_candidates:
        return tuple(actions)

    current = _stable_grid(current_grid)
    previous = _stable_grid(previous_grid) if previous_grid is not None else None
    height, width = current.shape
    ranked = _visual_points(current, previous)
    ranked.extend(
        _RankedPoint(4, 0, int(row), int(col)) for row, col in cached_points
    )
    ranked.append(_RankedPoint(5, 0, height // 2, width // 2))

    seen: set[Point] = set()
    for point in sorted(ranked):
        row = min(max(point.row, 0), height - 1)
        col = min(max(point.col, 0), width - 1)
        if (row, col) in seen:
            continue
        seen.add((row, col))
        actions.append(Action(ActionKind.ACTION6, row=row, col=col))
        if len(actions) == max_candidates:
            break
    return tuple(actions)


def candidates_from_history(
    history: History,
    *,
    cached_points: Iterable[Point] = (),
    max_candidates: int = 12,
) -> tuple[Action, ...]:
    """Convenience adapter from the shared bounded :class:`History` type."""

    if not history.frames:
        raise ValueError("cannot generate candidates from empty history")
    previous = history.frames[-2] if len(history.frames) >= 2 else None
    return generate_candidates(
        history.frames[-1],
        history.action_sets[-1],
        previous_grid=previous,
        cached_points=cached_points,
        game_state=history.game_states[-1],
        max_candidates=max_candidates,
    )


__all__ = ["Point", "candidates_from_history", "generate_candidates"]
