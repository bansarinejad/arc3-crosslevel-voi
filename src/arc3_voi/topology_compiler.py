"""Deterministic scene analysis used by the offline structured compiler."""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, replace
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from .types import ActionKind, GameState, History

BindingValue: TypeAlias = (  # noqa: UP040 - current mypy lacks PEP 695 aliases
    bool | int | str | tuple[int, ...] | tuple[tuple[int, int], ...]
)

TOPOLOGY_COMPILER_ALGORITHM_VERSION = "observable-scene-topology-v1"
_TOPOLOGY_COMPILER_ALGORITHM_SPEC = (
    "finite latest-scene analysis; border-occupancy background; palette-neutral "
    "four-connected components; normalized-shape repetition; bounded observable "
    "containment; transition-overlap then topology/rarity/symmetry ranking; relative "
    "homology and bbox-edge reflection; latest representable transition has exact "
    "action-conditioned precedence; four restricted executable role bodies"
)


@dataclass(frozen=True, slots=True)
class CompiledTopologyProgram:
    role: str
    source: str
    bindings: tuple[tuple[str, BindingValue], ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Component:
    colour: int
    cells: tuple[tuple[int, int], ...]
    bbox: tuple[int, int, int, int]
    centre: tuple[int, int]
    shape: tuple[tuple[int, int], ...]
    touches_border: bool
    symmetries: tuple[int, int, int]
    contained_count: int = 0
    containment_depth: int = 0
    repeat_count: int = 1

    @property
    def area(self) -> int:
        return len(self.cells)


@dataclass(frozen=True, slots=True)
class _Transition:
    index: int
    kind: int
    anchor: tuple[int, int]
    top: int
    left: int
    old_rows: tuple[str, ...]
    new_rows: tuple[str, ...]
    mask_rows: tuple[str, ...]
    changed: int
    state: str
    level_delta: int


@dataclass(frozen=True, slots=True)
class _Scene:
    background: int
    primary: _Component
    secondary: _Component
    target_colour: int
    offset: tuple[int, int]
    axis: int
    axis_sum: int
    points: tuple[tuple[int, int], ...]
    component_count: int
    containment_pairs: int
    repeated_groups: int
    transition: _Transition | None
    evidence: tuple[str, ...]


def compile_topology_programs(history: History) -> tuple[CompiledTopologyProgram, ...]:
    """Compile four programs from finite observable topology and transition evidence."""

    scene = _analyse(history)
    bindings = _bindings(scene)
    roles = (
        "conservative_evidence",
        "topology_contact",
        "homology_alignment",
        "symmetry_completion",
    )
    return tuple(
        CompiledTopologyProgram(role, _render(role, scene), bindings, scene.evidence)
        for role in roles
    )


def _analyse(history: History) -> _Scene:
    grid = np.asarray(history.latest_grid, dtype=np.int16)
    height, width = grid.shape
    palette = [int(value) for value in np.unique(grid)]
    cells_by_colour = {
        colour: tuple((int(r), int(c)) for r, c in np.argwhere(grid == colour))
        for colour in palette
    }
    border_counts = {
        colour: sum(r in (0, height - 1) or c in (0, width - 1) for r, c in cells)
        for colour, cells in cells_by_colour.items()
    }
    # Spatial first-occurrence is the final tie breaker, so palette relabeling does
    # not alter the selected topology under equal counts.
    background = min(
        palette,
        key=lambda colour: (
            -border_counts[colour],
            -len(cells_by_colour[colour]),
            cells_by_colour[colour][0],
        ),
    )
    raw = [
        component
        for colour in palette
        if colour != background
        for component in _components(grid, colour)
    ]
    if not raw:
        all_cells = tuple((r, c) for r in range(height) for c in range(width))
        raw = [_make_component(all_cells, background, grid.shape)]
    components = _decorate(raw, grid.shape)
    transition = _latest_transition(history)
    changed_cells = set(_changed_cells(transition))
    anchor = None if transition is None else transition.anchor
    counts = {colour: len(cells) for colour, cells in cells_by_colour.items()}

    def rank(component: _Component) -> tuple[object, ...]:
        overlap = len(changed_cells.intersection(component.cells))
        anchor_hit = int(anchor is not None and anchor in component.cells)
        return (
            -overlap,
            -anchor_hit,
            -component.contained_count,
            -component.containment_depth,
            counts[component.colour],
            -component.repeat_count,
            -sum(component.symmetries),
            component.touches_border,
            component.shape,
            component.cells,
        )

    primary = min(components, key=rank)
    homologues = [
        item for item in components if item.cells != primary.cells and item.shape == primary.shape
    ]
    if homologues:
        secondary = min(
            homologues,
            key=lambda item: (_distance(primary.centre, item.centre), item.cells),
        )
        secondary_reason = "nearest normalized-shape homologue"
    else:
        others = [item for item in components if item.cells != primary.cells]
        if others:
            secondary = min(
                others,
                key=lambda item: (_distance(primary.centre, item.centre), rank(item)),
            )
            secondary_reason = "nearest topology-ranked relative object"
        else:
            secondary = primary
            secondary_reason = "single-component conservative fallback"
    offset = (
        secondary.centre[0] - primary.centre[0],
        secondary.centre[1] - primary.centre[1],
    )
    if abs(offset[0]) >= abs(offset[1]):
        axis = 0
        axis_sum = (
            primary.bbox[0] + secondary.bbox[2]
            if offset[0] >= 0
            else primary.bbox[2] + secondary.bbox[0]
        )
        axis_name = "row"
    else:
        axis = 1
        axis_sum = (
            primary.bbox[1] + secondary.bbox[3]
            if offset[1] >= 0
            else primary.bbox[3] + secondary.bbox[1]
        )
        axis_name = "column"
    rarity = sorted(palette, key=lambda colour: (counts[colour], cells_by_colour[colour][0]))
    alternatives = [colour for colour in rarity if colour != primary.colour]
    target = (
        secondary.colour
        if secondary.cells != primary.cells
        else (alternatives[0] if alternatives else primary.colour)
    )

    point_list: list[tuple[int, int]] = []
    if transition is not None and transition.kind == int(ActionKind.ACTION6):
        point_list.append(transition.anchor)
    if changed_cells:
        changed_tuple = tuple(sorted(changed_cells))
        point_list.append(_nearest(changed_tuple, _mean(changed_tuple)))
    point_list.extend((primary.centre, secondary.centre))
    for component in (primary, secondary):
        top, left, bottom, right = component.bbox
        for target_point in (
            (float(top), (left + right) / 2),
            (float(bottom), (left + right) / 2),
            ((top + bottom) / 2, float(left)),
            ((top + bottom) / 2, float(right)),
        ):
            point_list.append(_nearest(component.cells, target_point))
    points = tuple(
        dict.fromkeys(
            point for point in point_list if 0 <= point[0] < height and 0 <= point[1] < width
        )
    )[:12]
    groups: dict[tuple[tuple[int, int], ...], int] = {}
    for component in components:
        groups[component.shape] = groups.get(component.shape, 0) + 1
    transition_note = (
        "no representable transition; generic topology remains defeasible"
        if transition is None
        else (
            f"history[{transition.index}] action {transition.kind} overrides priors "
            f"({transition.changed} changes)"
        )
    )
    evidence = (
        f"background from border occupancy then area ({background})",
        (
            "primary ranked by transition overlap, topological enclosure, rarity, repetition, "
            "symmetry, and translation-invariant shape"
        ),
        f"secondary from {secondary_reason}",
        f"relative geometry selects {axis_name} midpoint axis",
        f"visible palette only ({len(palette)} values)",
        transition_note,
    )
    return _Scene(
        background,
        primary,
        secondary,
        target,
        offset,
        axis,
        axis_sum,
        points,
        len(components),
        sum(item.contained_count for item in components),
        sum(value > 1 for value in groups.values()),
        transition,
        evidence,
    )


def _components(grid: NDArray[np.int16], colour: int) -> list[_Component]:
    remaining = {(int(r), int(c)) for r, c in np.argwhere(grid == colour)}
    result: list[_Component] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack, cells = [seed], []
        while stack:
            row, col = stack.pop()
            cells.append((row, col))
            for neighbour in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    stack.append(neighbour)
        result.append(_make_component(tuple(sorted(cells)), colour, grid.shape))
    return result


def _make_component(
    cells: tuple[tuple[int, int], ...], colour: int, shape: tuple[int, int]
) -> _Component:
    rows, cols = zip(*cells, strict=True)
    top, left, bottom, right = min(rows), min(cols), max(rows), max(cols)
    normalized = tuple((row - top, col - left) for row, col in cells)
    normalized_set = set(normalized)
    object_height, object_width = bottom - top + 1, right - left + 1
    horizontal = {(object_height - 1 - r, c) for r, c in normalized} == normalized_set
    vertical = {(r, object_width - 1 - c) for r, c in normalized} == normalized_set
    rotational = {
        (object_height - 1 - r, object_width - 1 - c) for r, c in normalized
    } == normalized_set
    return _Component(
        colour,
        cells,
        (top, left, bottom, right),
        _nearest(cells, _mean(cells)),
        normalized,
        top == 0 or left == 0 or bottom == shape[0] - 1 or right == shape[1] - 1,
        (int(horizontal), int(vertical), int(rotational)),
    )


def _enclosed_cells(
    component: _Component, frame_shape: tuple[int, int]
) -> frozenset[tuple[int, int]]:
    """Return complement cells topologically enclosed by one component."""

    top, left, bottom, right = component.bbox
    local_height = bottom - top + 3
    local_width = right - left + 3
    wall = np.zeros((local_height, local_width), dtype=np.bool_)
    for row, col in component.cells:
        wall[row - top + 1, col - left + 1] = True
    reachable = np.zeros_like(wall)
    reachable[0, 0] = True
    for _ in range(local_height + local_width):
        expanded = reachable.copy()
        expanded[1:, :] |= reachable[:-1, :]
        expanded[:-1, :] |= reachable[1:, :]
        expanded[:, 1:] |= reachable[:, :-1]
        expanded[:, :-1] |= reachable[:, 1:]
        expanded &= ~wall
        if np.array_equal(expanded, reachable):
            break
        reachable = expanded
    enclosed = np.argwhere(~wall & ~reachable)
    return frozenset(
        (int(row) + top - 1, int(col) + left - 1)
        for row, col in enclosed
        if 0 <= int(row) + top - 1 < frame_shape[0]
        and 0 <= int(col) + left - 1 < frame_shape[1]
    )


def _decorate(
    components: list[_Component], frame_shape: tuple[int, int]
) -> tuple[_Component, ...]:
    """Attach repetition counts and observable topological enclosure relations."""

    repeats: dict[tuple[tuple[int, int], ...], int] = {}
    for item in components:
        repeats[item.shape] = repeats.get(item.shape, 0) + 1
    cell_owner = {
        cell: index
        for index, component in enumerate(components)
        for cell in component.cells
    }
    contained_by: list[set[int]] = [set() for _ in components]
    for outer_index, outer in enumerate(components):
        for cell in _enclosed_cells(outer, frame_shape):
            inner_index = cell_owner.get(cell)
            if inner_index is not None and inner_index != outer_index:
                contained_by[outer_index].add(inner_index)
    contains_counts = [len(indices) for indices in contained_by]
    depth_counts = [
        sum(index in indices for indices in contained_by)
        for index in range(len(components))
    ]
    result = []
    for index, item in enumerate(components):
        result.append(
            replace(
                item,
                contained_count=contains_counts[index],
                containment_depth=depth_counts[index],
                repeat_count=repeats[item.shape],
            )
        )
    return tuple(result)


def _latest_transition(history: History) -> _Transition | None:
    for index in range(len(history.frames) - 1, 0, -1):
        action = history.actions[index]
        if action is None:
            continue
        before = np.asarray(history.frames[index - 1], dtype=np.int16)
        after = np.asarray(history.frames[index], dtype=np.int16)
        outside_arc_palette = before.size and (
            int(before.min()) < 0
            or int(before.max()) > 15
            or int(after.min()) < 0
            or int(after.max()) > 15
        )
        if before.shape != after.shape or outside_arc_palette:
            continue
        changed = np.argwhere(before != after)
        if action.kind is ActionKind.ACTION6:
            assert action.row is not None and action.col is not None
            anchor = (action.row, action.col)
        else:
            anchor = (0, 0)
        if not len(changed):
            return _Transition(
                index,
                int(action.kind),
                anchor,
                0,
                0,
                (),
                (),
                (),
                0,
                str(history.game_states[index]),
                history.level_deltas[index],
            )
        top, left = map(int, np.min(changed, axis=0))
        bottom, right = map(int, np.max(changed, axis=0))
        old_rows = tuple(
            "".join(format(int(before[row, col]), "x") for col in range(left, right + 1))
            for row in range(top, bottom + 1)
        )
        new_rows = tuple(
            "".join(format(int(after[row, col]), "x") for col in range(left, right + 1))
            for row in range(top, bottom + 1)
        )
        mask_rows = tuple(
            "".join(
                "1" if before[row, col] != after[row, col] else "0"
                for col in range(left, right + 1)
            )
            for row in range(top, bottom + 1)
        )
        return _Transition(
            index,
            int(action.kind),
            anchor,
            top - anchor[0],
            left - anchor[1],
            old_rows,
            new_rows,
            mask_rows,
            len(changed),
            str(history.game_states[index]),
            history.level_deltas[index],
        )
    return None


def _changed_cells(transition: _Transition | None) -> tuple[tuple[int, int], ...]:
    if transition is None:
        return ()
    base_row = transition.anchor[0] + transition.top
    base_col = transition.anchor[1] + transition.left
    return tuple(
        (base_row + row, base_col + col)
        for row, mask_row in enumerate(transition.mask_rows)
        for col, marker in enumerate(mask_row)
        if marker == "1"
    )


def _mean(cells: tuple[tuple[int, int], ...]) -> tuple[float, float]:
    return sum(r for r, _ in cells) / len(cells), sum(c for _, c in cells) / len(cells)


def _nearest(cells: tuple[tuple[int, int], ...], target: tuple[float, float]) -> tuple[int, int]:
    return min(
        cells,
        key=lambda cell: (
            (cell[0] - target[0]) ** 2 + (cell[1] - target[1]) ** 2,
            cell,
        ),
    )


def _distance(first: tuple[int, int], second: tuple[int, int]) -> int:
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2


def _bindings(scene: _Scene) -> tuple[tuple[str, BindingValue], ...]:
    transition = scene.transition
    return (
        ("background_colour", scene.background),
        ("primary_colour", scene.primary.colour),
        ("primary_centre", scene.primary.centre),
        ("primary_bbox", scene.primary.bbox),
        ("primary_area", scene.primary.area),
        ("primary_repeat_count", scene.primary.repeat_count),
        ("primary_contained_count", scene.primary.contained_count),
        ("primary_containment_depth", scene.primary.containment_depth),
        ("primary_symmetry", scene.primary.symmetries),
        ("secondary_colour", scene.secondary.colour),
        ("secondary_centre", scene.secondary.centre),
        ("secondary_bbox", scene.secondary.bbox),
        ("target_colour", scene.target_colour),
        ("relative_offset", scene.offset),
        ("symmetry_axis", scene.axis),
        ("symmetry_axis_sum", scene.axis_sum),
        ("candidate_points", scene.points),
        ("component_count", scene.component_count),
        ("containment_pair_count", scene.containment_pairs),
        ("repeated_shape_group_count", scene.repeated_groups),
        ("recorded_transition_used", transition is not None),
        ("recorded_transition_index", -1 if transition is None else transition.index),
        ("recorded_action_kind", -1 if transition is None else transition.kind),
        ("recorded_changed_count", 0 if transition is None else transition.changed),
        (
            "recorded_patch_cells",
            0 if transition is None else sum(len(row) for row in transition.mask_rows),
        ),
    )


_HELPERS = """
def component_mask(grid, row, col):
    same = grid == grid[row, col]
    mask = np.zeros_like(same, dtype=np.bool_)
    mask[row, col] = True
    height, width = grid.shape
    for step in range(height + width):
        expanded = mask.copy()
        expanded[1:, :] = np.logical_or(expanded[1:, :], mask[:-1, :])
        expanded[:-1, :] = np.logical_or(expanded[:-1, :], mask[1:, :])
        expanded[:, 1:] = np.logical_or(expanded[:, 1:], mask[:, :-1])
        expanded[:, :-1] = np.logical_or(expanded[:, :-1], mask[:, 1:])
        expanded = np.logical_and(expanded, same)
        if np.array_equal(expanded, mask):
            break
        mask = expanded
    return mask

def apply_observed(grid, action):
    if int(action.kind) != OBSERVED_ACTION_KIND:
        return grid, False
    if OBSERVED_ACTION_KIND == 6:
        base_row = int(action.row) + OBSERVED_TOP
        base_col = int(action.col) + OBSERVED_LEFT
    else:
        base_row = OBSERVED_ANCHOR[0] + OBSERVED_TOP
        base_col = OBSERVED_ANCHOR[1] + OBSERVED_LEFT
    if len(OBSERVED_MASK_ROWS) == 0:
        if OBSERVED_ACTION_KIND == 6 and (
            int(action.row) != OBSERVED_ANCHOR[0]
            or int(action.col) != OBSERVED_ANCHOR[1]
        ):
            return grid, False
        return grid, True
    height, width = grid.shape
    candidate = grid.copy()
    matched = 0
    expected = 0
    for local_row, mask_row in enumerate(OBSERVED_MASK_ROWS):
        for local_col, marker in enumerate(mask_row):
            if marker == "1":
                expected += 1
                row = base_row + local_row
                col = base_col + local_col
                if 0 <= row < height and 0 <= col < width:
                    old_value = int(OBSERVED_OLD_ROWS[local_row][local_col], 16)
                    if int(grid[row, col]) == old_value:
                        candidate[row, col] = int(OBSERVED_NEW_ROWS[local_row][local_col], 16)
                        matched += 1
    if matched == expected:
        return candidate, True
    return grid, False

def observed_prediction(grid, action, current_state):
    candidate, observed = apply_observed(grid, action)
    if observed:
        return {
            "next_grid": candidate,
            "game_state": OBSERVED_GAME_STATE,
            "level_delta": OBSERVED_LEVEL_DELTA,
            "memory": {"evidence": 1},
        }
    return {
        "next_grid": grid,
        "game_state": current_state,
        "level_delta": 0,
        "memory": {"evidence": 0},
    }
"""


_BODIES = {
    "conservative_evidence": """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    return observed_prediction(grid, action, history.game_states[-1])

def goal_value(history):
    return 0.0
""",
    "topology_contact": """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    observed = observed_prediction(grid, action, history.game_states[-1])
    if observed["memory"]["evidence"] == 1:
        return observed
    if int(action.kind) == 6:
        row, col = int(action.row), int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            source = grid[row, col]
            target = TARGET_COLOUR
            if source == target:
                target = PRIMARY_COLOUR
            if source == target:
                target = BACKGROUND_COLOUR
            grid[component_mask(grid, row, col)] = target
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    latest = history.actions[-1]
    if latest is None or int(latest.kind) != 6:
        return 0.0
    grid = np.array(history.frames[-1], dtype=np.int16)
    row, col = int(latest.row), int(latest.col)
    height, width = grid.shape
    if not (0 <= row < height and 0 <= col < width):
        return 0.0
    area = int(np.count_nonzero(component_mask(grid, row, col)))
    return float(area) / float(area + PRIMARY_AREA)
""",
    "homology_alignment": """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    observed = observed_prediction(grid, action, history.game_states[-1])
    if observed["memory"]["evidence"] == 1:
        return observed
    if int(action.kind) == 6:
        row, col = int(action.row), int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            selected = component_mask(grid, row, col)
            points = np.argwhere(selected)
            source = grid[row, col]
            grid[selected] = BACKGROUND_COLOUR
            for point in points:
                next_row, next_col = int(point[0]) + RELATIVE_ROW, int(point[1]) + RELATIVE_COL
                if 0 <= next_row < height and 0 <= next_col < width:
                    grid[next_row, next_col] = source
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    grid = np.array(history.frames[-1], dtype=np.int16)
    source_region = grid[PRIMARY_TOP:PRIMARY_BOTTOM + 1, PRIMARY_LEFT:PRIMARY_RIGHT + 1]
    target_region = grid[SECONDARY_TOP:SECONDARY_BOTTOM + 1, SECONDARY_LEFT:SECONDARY_RIGHT + 1]
    cleared = float(np.count_nonzero(source_region == BACKGROUND_COLOUR)) / float(PRIMARY_AREA)
    aligned = float(np.count_nonzero(target_region == PRIMARY_COLOUR)) / float(SECONDARY_AREA)
    return min(1.0, 0.5 * (cleared + aligned))
""",
    "symmetry_completion": """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    observed = observed_prediction(grid, action, history.game_states[-1])
    if observed["memory"]["evidence"] == 1:
        return observed
    if int(action.kind) == 6:
        row, col = int(action.row), int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            source = grid[row, col]
            for point in np.argwhere(component_mask(grid, row, col)):
                next_row, next_col = int(point[0]), int(point[1])
                if SYMMETRY_AXIS == 0:
                    next_row = SYMMETRY_AXIS_SUM - next_row
                else:
                    next_col = SYMMETRY_AXIS_SUM - next_col
                if 0 <= next_row < height and 0 <= next_col < width:
                    grid[next_row, next_col] = source
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    latest = history.actions[-1]
    if latest is None or int(latest.kind) != 6:
        return 0.0
    grid = np.array(history.frames[-1], dtype=np.int16)
    row, col = int(latest.row), int(latest.col)
    height, width = grid.shape
    if not (0 <= row < height and 0 <= col < width):
        return 0.0
    source = grid[row, col]
    selected = component_mask(grid, row, col)
    area = int(np.count_nonzero(selected))
    matched = 0
    for point in np.argwhere(selected):
        next_row, next_col = int(point[0]), int(point[1])
        if SYMMETRY_AXIS == 0:
            next_row = SYMMETRY_AXIS_SUM - next_row
        else:
            next_col = SYMMETRY_AXIS_SUM - next_col
        if 0 <= next_row < height and 0 <= next_col < width:
            matched += int(grid[next_row, next_col] == source)
    return float(matched) / float(area + PRIMARY_AREA)
""",
}


def _render(role: str, scene: _Scene) -> str:
    transition = scene.transition
    constants = f"""CANDIDATE_POINTS = {scene.points!r}
PRIMARY_COLOUR = {scene.primary.colour}
TARGET_COLOUR = {scene.target_colour}
BACKGROUND_COLOUR = {scene.background}
PRIMARY_TOP = {scene.primary.bbox[0]}
PRIMARY_LEFT = {scene.primary.bbox[1]}
PRIMARY_BOTTOM = {scene.primary.bbox[2]}
PRIMARY_RIGHT = {scene.primary.bbox[3]}
PRIMARY_AREA = {scene.primary.area}
SECONDARY_TOP = {scene.secondary.bbox[0]}
SECONDARY_LEFT = {scene.secondary.bbox[1]}
SECONDARY_BOTTOM = {scene.secondary.bbox[2]}
SECONDARY_RIGHT = {scene.secondary.bbox[3]}
SECONDARY_AREA = {scene.secondary.area}
RELATIVE_ROW = {scene.offset[0]}
RELATIVE_COL = {scene.offset[1]}
SYMMETRY_AXIS = {scene.axis}
SYMMETRY_AXIS_SUM = {scene.axis_sum}
OBSERVED_ACTION_KIND = {-1 if transition is None else transition.kind}
OBSERVED_ANCHOR = {(0, 0) if transition is None else transition.anchor!r}
OBSERVED_TOP = {0 if transition is None else transition.top}
OBSERVED_LEFT = {0 if transition is None else transition.left}
OBSERVED_OLD_ROWS = {() if transition is None else transition.old_rows!r}
OBSERVED_NEW_ROWS = {() if transition is None else transition.new_rows!r}
OBSERVED_MASK_ROWS = {() if transition is None else transition.mask_rows!r}
OBSERVED_GAME_STATE = {str(GameState.NOT_FINISHED) if transition is None else transition.state!r}
OBSERVED_LEVEL_DELTA = {0 if transition is None else transition.level_delta}
"""
    return constants + _HELPERS + _BODIES[role]


_HASHED_COMPILER_CALLABLES = (
    compile_topology_programs,
    _analyse,
    _components,
    _make_component,
    _enclosed_cells,
    _decorate,
    _latest_transition,
    _changed_cells,
    _mean,
    _nearest,
    _distance,
    _bindings,
    _render,
)
TOPOLOGY_COMPILER_CODE_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "algorithm_spec": _TOPOLOGY_COMPILER_ALGORITHM_SPEC,
            "classes": [
                inspect.getsource(item)
                for item in (
                    CompiledTopologyProgram,
                    _Component,
                    _Transition,
                    _Scene,
                )
            ],
            "callables": [inspect.getsource(item) for item in _HASHED_COMPILER_CALLABLES],
            "helpers": _HELPERS,
            "role_bodies": _BODIES,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


__all__ = [
    "TOPOLOGY_COMPILER_ALGORITHM_VERSION",
    "TOPOLOGY_COMPILER_CODE_SHA256",
    "BindingValue",
    "CompiledTopologyProgram",
    "compile_topology_programs",
]
