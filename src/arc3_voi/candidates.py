"""Deterministic, source-neutral ARC-AGI-3 action candidates.

The official interface exposes a small set of parameter-free actions and one
coordinate action (``ACTION6``).  Enumerating every pixel for the latter would
make model-based search intractable, so this module constructs a small set of
high-value click locations without ever dropping a currently valid simple
action.
"""

from __future__ import annotations

import inspect
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256

import numpy as np
from numpy.typing import NDArray

from arc3_voi.types import Action, ActionKind, GameState, History

Grid = NDArray[np.integer]
Point = tuple[int, int]

_CANDIDATE_POLICY_SPEC = """\
salience-frontier-v1
grid-evidence=change,colour-rarity,component-rarity,containment,holes,homology,border
representatives=component-medoid,top,bottom,left,right
structural-salience=palette:3,component:1,containment:250000x4,holes:150000x4,homology:100000x4,interior:300000,border:-200000
transition-component-salience=structural+3x-changed-ratio
change-region-salience=6000000-200000x-border-sides
containment-enclosures=exact-enclosed-complement-membership,cap-64,geometry-tie-break
visual-allocation=structural-first,alternating-structural-transition,deduplicate-while-advancing
family-diversity=translation-normalized-shape,round-robin-within-2000000-salience-window
proposal-treatment=opaque-coordinate-order
allocation=one-third-visual,one-third-proposal,alternating-rank-backfill
single-slot=visual-first-because-two-frontier-reservation-is-impossible
deduplication=clamp-then-coordinate
tie-break=salience-desc,role,area,row,col
fallback=display-centre-after-frontier-exhaustion
history-boundary=no-change-evidence-after-level-delta-or-reset
"""
CANDIDATE_POLICY_VERSION = "salience-frontier-v1"
_MAX_CONTAINMENT_ENCLOSURES = 64
_FAMILY_DIVERSITY_WINDOW = 2_000_000


@dataclass(frozen=True, slots=True)
class _Component:
    cells: NDArray[np.int64]
    shape: tuple[Point, ...]
    colour_count: int
    shape_count: int
    containment: int
    holes: int
    border_sides: int
    changed_cells: int


@dataclass(frozen=True, slots=True)
class _RankedPoint:
    """One visually grounded point with a total deterministic order."""

    point: Point
    salience: int
    role_rank: int
    area: int

    @property
    def sort_key(self) -> tuple[int, int, int, int, int]:
        row, col = self.point
        return (-self.salience, self.role_rank, self.area, row, col)


def _stable_grid(frame: NDArray[np.generic] | Sequence[object]) -> Grid:
    """Return the last stable 2-D grid from a frame or short frame sequence."""

    grid = np.asarray(frame)
    if grid.ndim == 3:
        grid = grid[-1]
    if grid.ndim != 2:
        raise ValueError(f"expected a 2-D grid (or frame sequence), got shape {grid.shape}")
    if grid.size == 0:
        raise ValueError("candidate generation requires a non-empty grid")
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


def _shape_signature(component: NDArray[np.int64]) -> tuple[Point, ...]:
    """Describe shape independently of absolute position and palette value."""

    origin = component.min(axis=0)
    normalized = component - origin
    return tuple(sorted((int(row), int(col)) for row, col in normalized))


def _bounds(component: NDArray[np.int64]) -> tuple[int, int, int, int]:
    return (
        int(component[:, 0].min()),
        int(component[:, 0].max()),
        int(component[:, 1].min()),
        int(component[:, 1].max()),
    )


def _strictly_contains(
    outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]
) -> bool:
    return (
        outer[0] < inner[0]
        and outer[1] > inner[1]
        and outer[2] < inner[2]
        and outer[3] > inner[3]
    )


def _enclosed_region_labels(component: NDArray[np.int64]) -> tuple[int, dict[Point, int]]:
    """Label exact complement regions enclosed by one four-connected component."""

    min_row, max_row, min_col, max_col = _bounds(component)
    local = np.zeros((max_row - min_row + 1, max_col - min_col + 1), dtype=bool)
    local[component[:, 0] - min_row, component[:, 1] - min_col] = True
    labels: dict[Point, int] = {}
    holes = 0
    for empty in _components(~local):
        touches_box = bool(
            np.any(empty[:, 0] == 0)
            or np.any(empty[:, 0] == local.shape[0] - 1)
            or np.any(empty[:, 1] == 0)
            or np.any(empty[:, 1] == local.shape[1] - 1)
        )
        if touches_box:
            continue
        holes += 1
        labels.update(
            {
                (int(row) + min_row, int(col) + min_col): holes
                for row, col in empty
            }
        )
    return holes, labels


def _is_enclosed(
    component: NDArray[np.int64], region_labels: dict[Point, int]
) -> bool:
    """Return whether every cell lies in one exact enclosed complement region."""

    first_row, first_col = component[0]
    region = region_labels.get((int(first_row), int(first_col)))
    return region is not None and all(
        region_labels.get((int(row), int(col))) == region for row, col in component
    )


def _border_sides(component: NDArray[np.int64], shape: tuple[int, int]) -> int:
    height, width = shape
    return sum(
        (
            bool(np.any(component[:, 0] == 0)),
            bool(np.any(component[:, 0] == height - 1)),
            bool(np.any(component[:, 1] == 0)),
            bool(np.any(component[:, 1] == width - 1)),
        )
    )


def _nearest_component_cell(component: NDArray[np.int64], target: tuple[float, float]) -> Point:
    """Choose the real component pixel nearest a possibly non-integral target."""

    delta = component.astype(np.float64) - np.asarray(target, dtype=np.float64)
    squared_distance = np.square(delta).sum(axis=1)
    # lexsort makes equal-distance choices stable across platforms.
    order = np.lexsort((component[:, 1], component[:, 0], squared_distance))
    row, col = component[int(order[0])]
    return int(row), int(col)


def _component_representatives(
    component: NDArray[np.int64],
) -> tuple[tuple[Point, int], ...]:
    """Return a real-cell medoid followed by top/bottom/left/right extrema."""

    center = tuple(component.mean(axis=0))
    center_row, center_col = center
    targets = (
        center,
        (float(component[:, 0].min()), center_col),
        (float(component[:, 0].max()), center_col),
        (center_row, float(component[:, 1].min())),
        (center_row, float(component[:, 1].max())),
    )
    return tuple(
        (_nearest_component_cell(component, target), role_rank)
        for role_rank, target in enumerate(targets)
    )


def _describe_components(current: Grid, previous: Grid | None) -> list[_Component]:
    """Describe colour components without assigning semantics to colour IDs."""

    raw: list[NDArray[np.int64]] = []
    colour_counts: list[int] = []
    _, inverse, counts = np.unique(current, return_inverse=True, return_counts=True)
    labels = inverse.reshape(current.shape)
    for label, count in enumerate(counts):
        for component in _components(labels == label):
            raw.append(component)
            colour_counts.append(int(count))

    shapes = [_shape_signature(component) for component in raw]
    signatures: defaultdict[tuple[Point, ...], int] = defaultdict(int)
    for shape in shapes:
        signatures[shape] += 1
    bounds = [_bounds(component) for component in raw]
    enclosed = [_enclosed_region_labels(component) for component in raw]
    holes = [item[0] for item in enclosed]
    # Only components with actual holes can enclose another object. Bound this
    # secondary index so even a 64x64 checkerboard avoids an O(C**2) scan.
    enclosure_indices = sorted(
        (index for index, hole_count in enumerate(holes) if hole_count > 0),
        key=lambda index: (
            -holes[index],
            (bounds[index][1] - bounds[index][0] + 1)
            * (bounds[index][3] - bounds[index][2] + 1),
            bounds[index],
            shapes[index],
        ),
    )[:_MAX_CONTAINMENT_ENCLOSURES]
    changed = (
        current != previous
        if previous is not None and previous.shape == current.shape
        else np.zeros(current.shape, dtype=bool)
    )

    result: list[_Component] = []
    for index, component in enumerate(raw):
        component_bounds = bounds[index]
        containment = sum(
            _strictly_contains(bounds[other_index], component_bounds)
            and _is_enclosed(component, enclosed[other_index][1])
            for other_index in enclosure_indices
            if other_index != index
        )
        result.append(
            _Component(
                cells=component,
                shape=shapes[index],
                colour_count=colour_counts[index],
                shape_count=signatures[shapes[index]],
                containment=containment,
                holes=holes[index],
                border_sides=_border_sides(component, current.shape),
                changed_cells=int(
                    np.count_nonzero(changed[component[:, 0], component[:, 1]])
                ),
            )
        )
    return result


def _structural_salience(component: _Component, grid_size: int) -> int:
    """Palette-neutral scene salience, deliberately independent of recent change."""

    area = int(component.cells.shape[0])
    palette_rarity = ((grid_size - component.colour_count) * 1_000_000) // grid_size
    component_rarity = (
        ((component.colour_count - area) * 1_000_000) // component.colour_count
    )
    return (
        3 * palette_rarity
        + component_rarity
        + 250_000 * min(component.containment, 4)
        + 150_000 * min(component.holes, 4)
        + 100_000 * min(max(component.shape_count - 1, 0), 4)
        + 300_000 * int(component.border_sides == 0)
        - 200_000 * component.border_sides
    )


def _ranked_representatives(
    component: NDArray[np.int64], salience: int
) -> list[_RankedPoint]:
    area = int(component.shape[0])
    return [
        _RankedPoint(point, salience, role_rank, area)
        for point, role_rank in _component_representatives(component)
    ]


def _family_round_robin(
    ranked: list[tuple[tuple[Point, ...], _RankedPoint]],
) -> list[Point]:
    """Diversify comparable normalized-shape families without erasing evidence rank."""

    grouped: defaultdict[tuple[Point, ...], list[_RankedPoint]] = defaultdict(list)
    for family, candidate in ranked:
        grouped[family].append(candidate)

    rows: dict[tuple[Point, ...], list[_RankedPoint]] = {}
    for family, candidates in grouped.items():
        best: dict[Point, _RankedPoint] = {}
        for candidate in candidates:
            incumbent = best.get(candidate.point)
            if incumbent is None or candidate.sort_key < incumbent.sort_key:
                best[candidate.point] = candidate
        rows[family] = sorted(best.values(), key=lambda item: item.sort_key)

    indices = {family: 0 for family in rows}
    result: list[Point] = []
    seen: set[Point] = set()
    while True:
        remaining = [
            family for family, index in indices.items() if index < len(rows[family])
        ]
        if not remaining:
            return result
        best_salience = max(rows[family][indices[family]].salience for family in remaining)
        active = sorted(
            (
                family
                for family in remaining
                if rows[family][indices[family]].salience
                >= best_salience - _FAMILY_DIVERSITY_WINDOW
            ),
            key=lambda family: (rows[family][indices[family]].sort_key, family),
        )
        for family in active:
            candidate = rows[family][indices[family]]
            indices[family] += 1
            if candidate.point not in seen:
                seen.add(candidate.point)
                result.append(candidate.point)


def _alternate_lanes(structural: list[Point], transition: list[Point]) -> list[Point]:
    """Alternate evidence lanes, advancing through cross-lane coordinate duplicates."""

    lanes = (structural, transition)
    indices = [0, 0]
    result: list[Point] = []
    seen: set[Point] = set()
    while indices[0] < len(structural) or indices[1] < len(transition):
        for lane_index, lane in enumerate(lanes):
            while indices[lane_index] < len(lane):
                point = lane[indices[lane_index]]
                indices[lane_index] += 1
                if point in seen:
                    continue
                seen.add(point)
                result.append(point)
                break
    return result


def _visual_points(current: Grid, previous: Grid | None) -> list[Point]:
    structural: list[tuple[tuple[Point, ...], _RankedPoint]] = []
    transition: list[tuple[tuple[Point, ...], _RankedPoint]] = []

    for component in _describe_components(current, previous):
        area = int(component.cells.shape[0])
        salience = _structural_salience(component, current.size)
        structural.extend(
            (component.shape, candidate)
            for candidate in _ranked_representatives(component.cells, salience)
        )
        if component.changed_cells:
            changed_ratio = (component.changed_cells * 1_000_000) // area
            transition.extend(
                (component.shape, candidate)
                for candidate in _ranked_representatives(
                    component.cells, salience + 3 * changed_ratio
                )
            )

    # Changed regions may cross colour boundaries. Their representatives are
    # useful discriminative probes, so include them as topology-neutral objects.
    if previous is not None and previous.shape == current.shape:
        for changed_component in _components(current != previous):
            border_sides = _border_sides(changed_component, current.shape)
            salience = 6_000_000 - 200_000 * border_sides
            family = _shape_signature(changed_component)
            transition.extend(
                (family, candidate)
                for candidate in _ranked_representatives(changed_component, salience)
            )

    return _alternate_lanes(
        _family_round_robin(structural),
        _family_round_robin(transition),
    )


def _clamped_points(points: Iterable[Point], shape: tuple[int, int]) -> list[Point]:
    height, width = shape
    result: list[Point] = []
    seen: set[Point] = set()
    for row, col in points:
        point = (
            min(max(int(row), 0), height - 1),
            min(max(int(col), 0), width - 1),
        )
        if point not in seen:
            seen.add(point)
            result.append(point)
    return result


def _allocate_clicks(visual: list[Point], proposals: list[Point], slots: int) -> list[Point]:
    """Reserve capacity symmetrically, then alternate within-source ranks."""

    if slots <= 0:
        return []
    selected: list[Point] = []
    seen: set[Point] = set()

    def take(frontier: list[Point], target: int) -> None:
        for point in frontier:
            if len(selected) >= slots or target <= 0:
                return
            if point not in seen:
                seen.add(point)
                selected.append(point)
                target -= 1

    if visual and proposals and slots >= 2:
        reserve = max(1, slots // 3)
        take(visual, reserve)
        take(proposals, reserve)

    visual_remaining = [point for point in visual if point not in seen]
    proposal_remaining = [point for point in proposals if point not in seen]
    cursor = 0
    while len(selected) < slots and (
        cursor < len(visual_remaining) or cursor < len(proposal_remaining)
    ):
        if cursor < len(visual_remaining):
            take([visual_remaining[cursor]], 1)
        if cursor < len(proposal_remaining):
            take([proposal_remaining[cursor]], 1)
        cursor += 1
    return selected


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
    """Build a capped, deterministic, source-neutral action frontier.

    All available parameter-free actions are retained. Of the remaining
    capacity, visual and cached/compiler proposals each receive one third when
    both exist; the remainder alternates their within-source ranks. Duplicate
    coordinates share capacity rather than being counted twice. If only one
    click slot exists, a two-source reservation is impossible and the top
    visual-evidence point wins; a proposal is used if no visual point exists.
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
    visual = _visual_points(current, previous)
    proposals = _clamped_points(cached_points, current.shape)
    slots = max_candidates - len(actions)
    points = _allocate_clicks(visual, proposals, slots)

    # The display centre is a fallback only; it cannot displace either frontier.
    if len(points) < slots:
        fallback = (current.shape[0] // 2, current.shape[1] // 2)
        if fallback not in points:
            points.append(fallback)
    actions.extend(
        Action(ActionKind.ACTION6, row=row, col=col) for row, col in points[:slots]
    )
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
    crosses_boundary = bool(
        history.level_deltas[-1] != 0
        or (
            history.actions[-1] is not None
            and history.actions[-1].kind is ActionKind.RESET
        )
    )
    previous = (
        history.frames[-2]
        if len(history.frames) >= 2 and not crosses_boundary
        else None
    )
    return generate_candidates(
        history.frames[-1],
        history.action_sets[-1],
        previous_grid=previous,
        cached_points=cached_points,
        game_state=history.game_states[-1],
        max_candidates=max_candidates,
    )


_HASHED_CANDIDATE_OBJECTS = (
    _Component,
    _RankedPoint,
    _stable_grid,
    _components,
    _shape_signature,
    _bounds,
    _strictly_contains,
    _enclosed_region_labels,
    _is_enclosed,
    _border_sides,
    _nearest_component_cell,
    _component_representatives,
    _describe_components,
    _structural_salience,
    _ranked_representatives,
    _family_round_robin,
    _alternate_lanes,
    _visual_points,
    _clamped_points,
    _allocate_clicks,
    _coerce_kind,
    generate_candidates,
    candidates_from_history,
)
CANDIDATE_POLICY_HASH = sha256(
    json.dumps(
        {
            "implementation": [
                inspect.getsource(item) for item in _HASHED_CANDIDATE_OBJECTS
            ],
            "policy_spec": _CANDIDATE_POLICY_SPEC,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


__all__ = [
    "CANDIDATE_POLICY_HASH",
    "CANDIDATE_POLICY_VERSION",
    "Point",
    "candidates_from_history",
    "generate_candidates",
]
