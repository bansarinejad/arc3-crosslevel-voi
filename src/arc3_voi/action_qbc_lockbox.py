"""Data-only sealed-scene generator for action-conditional outcome QBC.

This module intentionally uses only the Python standard library.  It does not import the
compiler, candidate builder, planner, controller, model, or any environment interface.
The registered seeds are inaccessible through the ordinary open-design API; the freeze
wrapper must construct the private, provenance-bound capability explicitly.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

JsonValue = Any
Cell = tuple[int, int]
Shape = tuple[Cell, ...]
Component = tuple[str, int, Shape]

MASK64: Final = (1 << 64) - 1
SPLITMIX64_INCREMENT: Final = 0x9E3779B97F4A7C15
GRID_SIZE: Final = 32
SCALE_FACTOR: Final = 2
PALETTE_SIZE: Final = 16
INNER_MIN: Final = 6
INNER_MAX: Final = 25
REJECTION_ATTEMPT_CAP: Final = 4096
POLICY_VERSION: Final = "action-conditional-outcome-qbc-v1"
GENERATOR_VERSION: Final = "action-qbc-lockbox-generator-v1"
SCHEMA_VERSION: Final = "action-qbc-lockbox-manifest-v1"
PUBLIC_SPLIT_SHA256: Final = (
    "0edf4f937be4ed391eb477343fd4fdee32cf6cd255092ae4f1ea617872ab1614"
)
PREREGISTRATION_COMMIT: Final = "1477f8a04ab17adf0bd78b4e98accee3c846aa36"
PREREGISTRATION_FILE_SHA256: Final = (
    "aba4f9639242922a5be53fecb2e9a1833eec353a84ffc1c1476aad9bad5725ce"
)
PREREGISTRATION_GIT_BLOB_OID: Final = "d1b23227ab44f619c89545e6453946efc3c1c3f9"
FAMILIES: Final = ("homologue", "containment", "reflection")
VISUAL_TRANSFORM_ORDER: Final = (
    "palette_bijection",
    "translation_row_plus_3_col_plus_5",
    "translation_row_minus_3_col_minus_5",
    "scale_2_nearest_neighbor",
)
ORDER_TRANSFORM_ORDER: Final = (
    "candidate_list_reversal",
    "candidate_list_left_rotation_by_one",
    "hypothesis_list_reversal",
    "hypothesis_list_left_rotation_by_one",
    "serialized_outcome_cell_order_reversal",
)
REJECTION_REASONS: Final = (
    "homologue_panel_placement_unavailable",
    "homologue_query_placement_unavailable",
    "containment_panel_placement_unavailable",
    "containment_query_placement_unavailable",
    "reflection_panel_placement_unavailable",
    "reflection_query_placement_unavailable",
)

REGISTERED_SEED_HEX: Final[dict[str, tuple[str, str, str, str]]] = {
    "homologue": (
        "a6eecedee22d2645",
        "68620ddc81520133",
        "e98ab12bef9e01ec",
        "3c03b39042f011e4",
    ),
    "containment": (
        "550e3657aac91e86",
        "7fd12591ea73ce88",
        "a957290ff6df8e67",
        "9a4897ce5e703365",
    ),
    "reflection": (
        "bb2215d4d6f787ec",
        "40e8287ce4331712",
        "ed9659c3935c6429",
        "343710325836c643",
    ),
}

# These names are rejected recursively.  Order-transform *values* may name their target
# sequence, but the generator can never serialize behavior-bearing fields under such keys.
FORBIDDEN_FIELD_NAMES: Final = frozenset(
    {
        "acceptance",
        "candidate",
        "candidate_actions",
        "candidate_builder_calls",
        "candidate_list",
        "candidates",
        "completion_cost",
        "completion_costs",
        "controller_calls",
        "cost",
        "costs",
        "diagnostic",
        "diagnostics",
        "environment_actions",
        "expected_diagnostics",
        "game_id",
        "game_version",
        "gate",
        "generated_tokens",
        "gpu_use",
        "gpu_uses",
        "hypothesis",
        "hypothesis_id",
        "hypotheses",
        "model_calls",
        "pass",
        "pass_label",
        "passes",
        "planner_calls",
        "prediction",
        "predictions",
        "program",
        "programs",
        "recorded_transition",
        "reward",
        "reward_observations",
        "rhae",
        "rhae_observations",
        "signature",
        "signatures",
        "transition",
        "transitions",
        "worker_starts",
    }
)

# The contract is declared before any payload-building function.  It is copied into the
# frozen manifest, so every sampling, geometry, ordering, and map convention is addressed.
GENERATOR_CONTRACT: Final[dict[str, JsonValue]] = {
    "generator_version": GENERATOR_VERSION,
    "schema_version": SCHEMA_VERSION,
    "data_boundary": {
        "allowed_output": ["scenes", "visual_transforms", "order_transform_maps"],
        "forbidden_behavior_data": sorted(FORBIDDEN_FIELD_NAMES),
        "project_runtime_imports": [],
    },
    "scene_grammar": {
        "grid_shape": [GRID_SIZE, GRID_SIZE],
        "palette_labels": list(range(PALETTE_SIZE)),
        "background_label": "first label of a per-attempt 16-label Fisher-Yates permutation",
        "boundary_margin_cells": INNER_MIN,
        "non_background_coordinate_bounds_inclusive": [INNER_MIN, INNER_MAX],
        "component_connectivity": "four_neighbor",
        "cross_component_four_neighbor_contact": "forbidden",
        "available_actions": ["ACTION3", "ACTION6"],
        "level": 1,
        "win_levels": 9,
        "initial_persistence": 0.5,
        "game_identifier": "omitted",
        "recorded_transition_field_policy": "omitted",
    },
    "splitmix64": {
        "state_width_bits": 64,
        "initial_state": "validated unsigned 64-bit seed (no reduction)",
        "draw_count": (
            "starts at zero, increments exactly once per next_u64 call, and serialized "
            "telemetry is restricted to [1,2^64-1] so state/count binding is injective"
        ),
        "increment_hex": f"{SPLITMIX64_INCREMENT:016x}",
        "mix_steps": [
            "z=(z^(z>>30))*0xbf58476d1ce4e5b9 mod 2^64",
            "z=(z^(z>>27))*0x94d049bb133111eb mod 2^64",
            "z=z^(z>>31)",
        ],
        "randbelow": (
            "draw unsigned 64-bit values until value < "
            "2^64-(2^64 mod bound), then return value mod bound"
        ),
        "shuffle": "descending Fisher-Yates using randbelow(i+1)",
    },
    "seed_derivation": {
        "utf8_template": (
            "<public_split_sha256>|action-conditional-outcome-qbc-v1|<family>|<index>"
        ),
        "digest": "SHA-256",
        "selection": "first eight digest bytes as unsigned big-endian integer",
        "public_split_sha256": PUBLIC_SPLIT_SHA256,
    },
    "rejection": {
        "attempt_cap": REJECTION_ATTEMPT_CAP,
        "attempt_numbering": "zero_based",
        "state_progression": (
            "one continuing SplitMix64 stream; no reseeding between attempts; after an attempt "
            "is accepted, the separate visual-transform bijection shuffle continues from that "
            "accepted attempt's stream state"
        ),
        "attempt_palette": (
            "shuffle labels 0..15 once at the start of each whole-scene attempt; first is "
            "background and subsequent labels are assigned in declared component-role order"
        ),
        "attempt_telemetry_authority": (
            "authored by the exact reviewed generator source; closed validation checks the "
            "frozen taxonomy and count/index relations but never resamples a seed"
        ),
        "exhaustion_result": "registered_generation_exhausted",
        "reason_taxonomy": list(REJECTION_REASONS),
        "replacement_seed": "forbidden",
        "post_seed_geometry_replacement": "forbidden",
    },
    "family_grammars": {
        "homologue": (
            "two same-colour exact translated copies of one seeded nontrivial axis-symmetric "
            "polyomino form reflected panels; one larger non-homologous central component is "
            "globally axis-symmetric; one unmatched off-axis singleton query shares target colour"
        ),
        "containment": (
            "two same-colour exact hollow rings selected from the seeded equal-perimeter "
            "(7x7,6x8,8x6) catalogue form reflected panels; the negative-side "
            "ring and its partner contain matching seeded visible components; one external "
            "central axis-symmetric connected context component exceeds each ring's area; an "
            "unmatched off-axis singleton query outside both rings shares the context colour"
        ),
        "reflection": (
            "two same-colour seeded 2x3-or-2x4 rectangular homologous anchors define the panel "
            "axis; an asymmetric "
            "core and its reflected partner preexist in a second colour; removing the seeded "
            "protrusion yields a connected central axis-symmetric incomplete core; one unmatched "
            "off-axis singleton query shares the core colour"
        ),
    },
    "visual_transforms": [
        {
            "name": "palette_bijection",
            "parameter": "seeded Fisher-Yates bijection of all sixteen labels",
            "cell_domain": "all 32x32 coordinates",
            "action6_domain": "all 32x32 coordinates",
        },
        {
            "name": "translation_row_plus_3_col_plus_5",
            "row_delta": 3,
            "col_delta": 5,
            "cell_domain": "exact in-bounds partial coordinate domain",
            "action6_domain": "same exact in-bounds partial coordinate domain",
        },
        {
            "name": "translation_row_minus_3_col_minus_5",
            "row_delta": -3,
            "col_delta": -5,
            "cell_domain": "exact in-bounds partial coordinate domain",
            "action6_domain": "same exact in-bounds partial coordinate domain",
        },
        {
            "name": "scale_2_nearest_neighbor",
            "factor": SCALE_FACTOR,
            "cell_domain": "all base cells, each mapping to its 2x2 output block",
            "action6_domain": "all base cells mapped to top-left scaled cell",
            "frontier_claim": "none; mapped base actions only",
        },
    ],
    "map_encoding": {
        "coordinate": "[row,col]",
        "cell_forward_entry": "[source_coordinate,[destination_coordinate,...]]",
        "cell_inverse_entry": "[destination_coordinate,source_coordinate]",
        "action6_entry": "[source_coordinate,destination_coordinate]",
        "palette_array_direction": (
            "forward[source_label]=destination_label; "
            "inverse[destination_label]=source_label"
        ),
        "map_order": (
            "forward/action maps: source coordinates in row-major order; inverse maps: "
            "destination coordinates in row-major order"
        ),
        "scale_cell_destination_order": (
            "top-left, top-right, bottom-left, bottom-right (row-major within each 2x2 block)"
        ),
        "simple_action_map": [["ACTION3", "ACTION3"]],
    },
    "sampling_orders": {
        "four_neighbour_order": ["north", "south", "west", "east"],
        "reflection_axis_order": ["horizontal", "vertical"],
        "d4_orientation_order": [
            "(row,col)",
            "(row,-col)",
            "(-row,col)",
            "(-row,-col)",
            "(col,row)",
            "(col,-row)",
            "(-col,row)",
            "(-col,-row)",
        ],
        "placement_enumeration": "row-major legal origins followed by one randbelow draw",
        "component_separation": "no overlap and no cross-component four-neighbour contact",
        "query_rule": (
            "one off-axis singleton; its reflected and relative-translation cells are in-bounds "
            "background cells before action; query colour differs from panel-anchor colour"
        ),
        "later_audit_boundary": (
            "stdlib validation independently encodes only the no-transition structural rank/axis "
            "precondition; it never imports or calls the frozen compiler and makes no actual "
            "compiler, candidate-frontier, outcome-signature, EVSI, utility, unique-winner, or "
            "background-exclusion claim; all remain post-freeze gates"
        ),
        "frontier_rule": (
            "generator emits no frontier; palette and translations are later regenerated by "
            "the frozen candidate builder, while scale consumes only mapped base actions"
        ),
    },
    "order_transforms": {
        "names_in_order": list(ORDER_TRANSFORM_ORDER),
        "index_semantics": "output_position_to_input_position",
        "forward_direction": (
            "forward_output_to_input maps transformed output position to original input position"
        ),
        "inverse_direction": (
            "inverse_output_to_input maps restored output position to transformed input position"
        ),
        "correspondence_semantics": {
            "candidate_sequence": "exact serialized action identity; positions only reordered",
            "hypothesis_sequence": (
                "committee input index given by forward_output_to_input"
            ),
            "serialized_outcome_cell_sequence": (
                "exact cell identity; serialization only"
            ),
        },
        "candidate_lengths": list(range(0, 13)),
        "hypothesis_length": 4,
        "outcome_cell_lengths": list(range(0, 5)),
        "empty_sequence_behavior": "reverse and left rotation both map [] to []",
    },
    "canonical_json": {
        "encoding": "UTF-8",
        "sort_keys": True,
        "separators": [",", ":"],
        "ensure_ascii": True,
        "allow_nan": False,
        "terminal_lf": False,
    },
}


class LockboxSchemaError(ValueError):
    """Raised when generated data violates the frozen data-only schema."""


@dataclass(frozen=True, slots=True)
class _RegisteredFreezeCapability:
    preregistration_commit: str
    preregistration_file_sha256: str
    preregistration_git_blob_oid: str
    reviewed_head: str
    generator_source_sha256: str


@dataclass(frozen=True, slots=True)
class _RejectedAttempt:
    reason: str


class SplitMix64:
    """Frozen SplitMix64 stream with unbiased bounded sampling."""

    __slots__ = ("draw_count", "state")

    def __init__(self, seed: int) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("SplitMix64 seed must be an integer")
        if not 0 <= seed <= MASK64:
            raise ValueError("SplitMix64 seed must be an unsigned 64-bit integer")
        self.state = seed
        self.draw_count = 0

    def next_u64(self) -> int:
        self.state = (self.state + SPLITMIX64_INCREMENT) & MASK64
        self.draw_count += 1
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
        return (value ^ (value >> 31)) & MASK64

    def randbelow(self, bound: int) -> int:
        if not isinstance(bound, int) or isinstance(bound, bool) or bound <= 0:
            raise ValueError("bound must be a positive integer")
        if bound > 1 << 64:
            raise ValueError("bound must be at most 2^64")
        limit = (1 << 64) - ((1 << 64) % bound)
        while True:
            value = self.next_u64()
            if value < limit:
                return value % bound

    def choice(self, values: Sequence[Cell] | Sequence[Shape] | Sequence[str]) -> object:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self.randbelow(len(values))]

    def shuffle(self, values: list[int]) -> None:
        for index in range(len(values) - 1, 0, -1):
            other = self.randbelow(index + 1)
            values[index], values[other] = values[other], values[index]


_PANEL_ANCHOR_SHAPES: Final[tuple[Shape, ...]] = (
    tuple((row, col) for row in range(2) for col in range(3)),
    ((0, 1), (1, 0), (1, 1), (1, 2), (2, 1)),
    tuple(
        (row, col)
        for row in range(3)
        for col in range(3)
        if row in {0, 2} or col in {0, 2}
    ),
)

_REFLECTION_ANCHOR_SHAPES: Final[tuple[Shape, ...]] = (
    tuple((row, col) for row in range(2) for col in range(3)),
    tuple((row, col) for row in range(2) for col in range(4)),
)

_CENTRAL_TARGET_SHAPES: Final[tuple[Shape, ...]] = (
    tuple((row, col) for row in range(5) for col in range(5)),
    tuple(
        (row, col)
        for row in range(5)
        for col in range(5)
        if (row, col) not in {(0, 0), (0, 4), (4, 0), (4, 4)}
    ),
)


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Return the one canonical JSON representation used for every content hash."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    ).encode("utf-8")


def canonical_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


GENERATOR_CONTRACT_SHA256: Final = canonical_sha256(GENERATOR_CONTRACT)


def derive_registered_seed(family: str, index: int) -> int:
    """Derive a registered seed without evaluating its scene."""

    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 4:
        raise ValueError("registered family index must be an integer in [0,3]")
    source = f"{PUBLIC_SPLIT_SHA256}|{POLICY_VERSION}|{family}|{index}".encode()
    return int.from_bytes(hashlib.sha256(source).digest()[:8], "big", signed=False)


def _registered_seed_values() -> frozenset[int]:
    return frozenset(int(value, 16) for values in REGISTERED_SEED_HEX.values() for value in values)


def _normalise(shape: Iterable[Cell]) -> Shape:
    cells = tuple(shape)
    if not cells:
        raise LockboxSchemaError("component shape must not be empty")
    min_row = min(row for row, _ in cells)
    min_col = min(col for _, col in cells)
    return tuple(sorted((row - min_row, col - min_col) for row, col in cells))


def _orient(shape: Shape, orientation: int) -> Shape:
    if not 0 <= orientation < 8:
        raise ValueError("orientation must be in [0,7]")

    def transform(row: int, col: int) -> Cell:
        operations = (
            (row, col),
            (row, -col),
            (-row, col),
            (-row, -col),
            (col, row),
            (col, -row),
            (-col, row),
            (-col, -row),
        )
        return operations[orientation]

    return _normalise(transform(row, col) for row, col in shape)


def _flip(shape: Shape, axis: str) -> Shape:
    if axis == "horizontal":
        return _normalise((-row, col) for row, col in shape)
    if axis == "vertical":
        return _normalise((row, -col) for row, col in shape)
    raise ValueError(f"unknown reflection axis: {axis}")


def _shape_height(shape: Shape) -> int:
    return max(row for row, _ in shape) + 1


def _shape_width(shape: Shape) -> int:
    return max(col for _, col in shape) + 1


def _translate(shape: Shape, origin: Cell) -> Shape:
    return tuple(sorted((origin[0] + row, origin[1] + col) for row, col in shape))


def _four_neighbours(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    row, col = cell
    return ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))


def _is_connected(cells: Iterable[Cell]) -> bool:
    remaining = set(cells)
    if not remaining:
        return False
    frontier = [next(iter(remaining))]
    visited: set[Cell] = set()
    while frontier:
        cell = frontier.pop()
        if cell in visited:
            continue
        visited.add(cell)
        frontier.extend(neighbour for neighbour in _four_neighbours(cell) if neighbour in remaining)
    return visited == remaining


def _is_separated(cells: Iterable[Cell], occupied: set[Cell]) -> bool:
    proposed = set(cells)
    return not proposed.intersection(occupied) and all(
        neighbour not in occupied for cell in proposed for neighbour in _four_neighbours(cell)
    )


def _valid_origins(shape: Shape) -> tuple[Cell, ...]:
    height = _shape_height(shape)
    width = _shape_width(shape)
    return tuple(
        (row, col)
        for row in range(INNER_MIN, INNER_MAX - height + 2)
        for col in range(INNER_MIN, INNER_MAX - width + 2)
    )


def _sample_attempt_palette(rng: SplitMix64) -> tuple[int, ...]:
    labels = list(range(PALETTE_SIZE))
    rng.shuffle(labels)
    return tuple(labels)


def _sample_shape(rng: SplitMix64, catalogue: Sequence[Shape]) -> tuple[Shape, int, int]:
    catalogue_index = rng.randbelow(len(catalogue))
    orientation = rng.randbelow(8)
    return _orient(catalogue[catalogue_index], orientation), catalogue_index, orientation


def _component_record(component: Component) -> dict[str, JsonValue]:
    role, palette_label, cells = component
    return {
        "role": role,
        "palette_label": palette_label,
        "cells": [[row, col] for row, col in cells],
    }


def _reflect_cell(cell: Cell, axis: str, axis_sum: int) -> Cell:
    if axis == "horizontal":
        return axis_sum - cell[0], cell[1]
    if axis == "vertical":
        return cell[0], axis_sum - cell[1]
    raise ValueError(f"unknown reflection axis: {axis}")


def _reflect_cells(cells: Shape, axis: str, axis_sum: int) -> Shape:
    return tuple(sorted(_reflect_cell(cell, axis, axis_sum) for cell in cells))


def _negative_of_central(cells: Shape, central: Shape, axis: str) -> bool:
    if axis == "horizontal":
        return max(row for row, _ in cells) <= min(row for row, _ in central) - 2
    return max(col for _, col in cells) <= min(col for _, col in central) - 2


def _negative_of_component(cells: Shape, other: Shape, axis: str) -> bool:
    if axis == "horizontal":
        return max(row for row, _ in cells) <= min(row for row, _ in other) - 2
    return max(col for _, col in cells) <= min(col for _, col in other) - 2


def _translation_offset(source: Shape, destination: Shape) -> Cell:
    return (
        min(row for row, _ in destination) - min(row for row, _ in source),
        min(col for _, col in destination) - min(col for _, col in source),
    )


def _query_positions(
    occupied: set[Cell],
    *,
    axis: str,
    axis_sum: int,
    relative_offset: Cell,
    allowed_sources: Iterable[Cell] | None = None,
    require_distinct_destinations: bool,
) -> tuple[Cell, ...]:
    sources = (
        tuple(allowed_sources)
        if allowed_sources is not None
        else tuple(
            (row, col)
            for row in range(INNER_MIN, INNER_MAX + 1)
            for col in range(INNER_MIN, INNER_MAX + 1)
        )
    )
    result: list[Cell] = []
    for source in sources:
        if source in occupied or any(
            neighbour in occupied for neighbour in _four_neighbours(source)
        ):
            continue
        reflected = _reflect_cell(source, axis, axis_sum)
        translated = (
            source[0] + relative_offset[0],
            source[1] + relative_offset[1],
        )
        mapped = (reflected, translated)
        if not all(
            INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
            for row, col in mapped
        ):
            continue
        if source in mapped or any(destination in occupied for destination in mapped):
            continue
        if require_distinct_destinations and reflected == translated:
            continue
        result.append(source)
    return tuple(result)


def _try_homologue(
    rng: SplitMix64, role_colours: Sequence[int]
) -> tuple[tuple[Component, ...], dict[str, JsonValue]] | _RejectedAttempt:
    prototype, prototype_index, prototype_orientation = _sample_shape(
        rng, _PANEL_ANCHOR_SHAPES
    )
    target, target_index, target_orientation = _sample_shape(rng, _CENTRAL_TARGET_SHAPES)
    axis = ("horizontal", "vertical")[rng.randbelow(2)]
    if _flip(prototype, axis) != prototype or _flip(target, axis) != target:
        raise LockboxSchemaError("panel catalogues must be symmetric on either selected axis")
    if len(target) <= 2 * len(prototype):
        raise LockboxSchemaError("central homologue target must exceed total anchor-colour area")

    layouts: list[tuple[Shape, Shape, Shape, int]] = []
    for target_origin in _valid_origins(target):
        target_cells = _translate(target, target_origin)
        target_centre2 = _centre_twice(target_cells)
        axis_sum = target_centre2[0] if axis == "horizontal" else target_centre2[1]
        if _reflect_cells(target_cells, axis, axis_sum) != target_cells:
            continue
        for prototype_origin in _valid_origins(prototype):
            first = _translate(prototype, prototype_origin)
            if not _negative_of_central(first, target_cells, axis):
                continue
            second = _reflect_cells(first, axis, axis_sum)
            if (
                _normalise(second) == prototype
                and all(
                    INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
                    for row, col in second
                )
                and _is_separated(first, set(target_cells))
                and _is_separated(second, set(target_cells) | set(first))
            ):
                layouts.append((first, second, target_cells, axis_sum))
    if not layouts:
        return _RejectedAttempt("homologue_panel_placement_unavailable")
    first, second, target_cells, axis_sum = layouts[rng.randbelow(len(layouts))]
    offset = _translation_offset(first, second)
    occupied = set(first) | set(second) | set(target_cells)
    queries = _query_positions(
        occupied,
        axis=axis,
        axis_sum=axis_sum,
        relative_offset=offset,
        require_distinct_destinations=True,
    )
    if not queries:
        return _RejectedAttempt("homologue_query_placement_unavailable")
    query = queries[rng.randbelow(len(queries))]
    colours = tuple(role_colours[:2])
    components: tuple[Component, ...] = (
        ("panel_prototype_a", colours[0], first),
        ("panel_prototype_b", colours[0], second),
        ("separate_central_target", colours[1], target_cells),
        ("off_axis_query", colours[1], (query,)),
    )
    parameters: dict[str, JsonValue] = {
        "prototype_catalogue_index": prototype_index,
        "prototype_orientation": prototype_orientation,
        "prototype_shape": [[row, col] for row, col in prototype],
        "target_catalogue_index": target_index,
        "target_orientation": target_orientation,
        "target_shape": [[row, col] for row, col in target],
        "axis_orientation": axis,
        "axis_coordinate_twice": axis_sum,
        "relative_translation_offset": [offset[0], offset[1]],
        "query_cell": [query[0], query[1]],
        "query_reflected_destination": list(_reflect_cell(query, axis, axis_sum)),
        "query_translated_destination": [query[0] + offset[0], query[1] + offset[1]],
        "palette_labels_in_component_order": [colours[0], colours[0], colours[1], colours[1]],
    }
    return components, parameters


def _ring_shape(height: int, width: int) -> Shape:
    return tuple(
        sorted(
            {
                (row, col)
                for row in range(height)
                for col in range(width)
                if row in {0, height - 1} or col in {0, width - 1}
            }
        )
    )


def _centre_twice(cells: Shape) -> Cell:
    return (
        min(row for row, _ in cells) + max(row for row, _ in cells),
        min(col for _, col in cells) + max(col for _, col in cells),
    )


def _try_containment(
    rng: SplitMix64, role_colours: Sequence[int]
) -> tuple[tuple[Component, ...], dict[str, JsonValue]] | _RejectedAttempt:
    ring_dimensions = ((7, 7), (6, 8), (8, 6))
    ring_catalogue_index = rng.randbelow(len(ring_dimensions))
    ring_height, ring_width = ring_dimensions[ring_catalogue_index]
    ring = _ring_shape(ring_height, ring_width)
    axis = ("horizontal", "vertical")[rng.randbelow(2)]
    context_variant = rng.randbelow(2)
    context_horizontal = tuple(
        (row, col)
        for row in range(3)
        for col in range(9)
        if not (context_variant == 1 and (row, col) == (1, 4))
    )
    context = context_horizontal if axis == "horizontal" else _orient(context_horizontal, 4)
    if len(context) <= len(ring) or _flip(context, axis) != context:
        raise LockboxSchemaError("containment context must be larger, connected, and symmetric")

    layouts: list[tuple[Shape, Shape, Shape, int]] = []
    for context_origin in _valid_origins(context):
        context_cells = _translate(context, context_origin)
        context_centre2 = _centre_twice(context_cells)
        axis_sum = context_centre2[0] if axis == "horizontal" else context_centre2[1]
        if _reflect_cells(context_cells, axis, axis_sum) != context_cells:
            continue
        for ring_origin in _valid_origins(ring):
            first_ring = _translate(ring, ring_origin)
            if not _negative_of_central(first_ring, context_cells, axis):
                continue
            second_ring = _reflect_cells(first_ring, axis, axis_sum)
            if (
                _normalise(second_ring) == ring
                and all(
                    INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
                    for row, col in second_ring
                )
                and _is_separated(first_ring, set(context_cells))
                and _is_separated(second_ring, set(context_cells) | set(first_ring))
            ):
                layouts.append((first_ring, second_ring, context_cells, axis_sum))
    if not layouts:
        return _RejectedAttempt("containment_panel_placement_unavailable")
    first_ring, second_ring, context_cells, axis_sum = layouts[rng.randbelow(len(layouts))]
    offset = _translation_offset(first_ring, second_ring)
    ring_top = min(row for row, _ in first_ring)
    ring_bottom = max(row for row, _ in first_ring)
    ring_left = min(col for _, col in first_ring)
    ring_right = max(col for _, col in first_ring)
    contained_sources = tuple(
        (row, col)
        for row in range(ring_top + 2, ring_bottom - 1)
        for col in range(ring_left + 2, ring_right - 1)
        if (row, col) != ((ring_top + ring_bottom) // 2, (ring_left + ring_right) // 2)
    )
    contained_a = contained_sources[rng.randbelow(len(contained_sources))]
    contained_b = _reflect_cell(contained_a, axis, axis_sum)
    occupied = (
        set(first_ring)
        | set(second_ring)
        | set(context_cells)
        | {contained_a, contained_b}
    )
    first_bbox = (ring_top, ring_bottom, ring_left, ring_right)
    second_bbox = (
        min(row for row, _ in second_ring),
        max(row for row, _ in second_ring),
        min(col for _, col in second_ring),
        max(col for _, col in second_ring),
    )
    allowed_queries = (
        (row, col)
        for row in range(INNER_MIN, INNER_MAX + 1)
        for col in range(INNER_MIN, INNER_MAX + 1)
        if not (
            first_bbox[0] < row < first_bbox[1] and first_bbox[2] < col < first_bbox[3]
        )
        and not (
            second_bbox[0] < row < second_bbox[1] and second_bbox[2] < col < second_bbox[3]
        )
    )
    queries = _query_positions(
        occupied,
        axis=axis,
        axis_sum=axis_sum,
        relative_offset=offset,
        allowed_sources=allowed_queries,
        require_distinct_destinations=True,
    )
    if not queries:
        return _RejectedAttempt("containment_query_placement_unavailable")
    query = queries[rng.randbelow(len(queries))]
    colours = tuple(role_colours[:3])
    components: tuple[Component, ...] = (
        ("hollow_panel_a", colours[0], first_ring),
        ("hollow_panel_b", colours[0], second_ring),
        ("contained_component_a", colours[1], (contained_a,)),
        ("contained_component_b", colours[1], (contained_b,)),
        ("external_axis_symmetric_context", colours[2], context_cells),
        ("off_axis_query", colours[2], (query,)),
    )
    parameters: dict[str, JsonValue] = {
        "ring_catalogue_index": ring_catalogue_index,
        "ring_height": ring_height,
        "ring_width": ring_width,
        "ring_shape": [[row, col] for row, col in ring],
        "context_variant": context_variant,
        "context_shape": [[row, col] for row, col in context],
        "axis_orientation": axis,
        "axis_coordinate_twice": axis_sum,
        "relative_translation_offset": [offset[0], offset[1]],
        "contained_cell_a": [contained_a[0], contained_a[1]],
        "contained_cell_b": [contained_b[0], contained_b[1]],
        "query_cell": [query[0], query[1]],
        "query_reflected_destination": list(_reflect_cell(query, axis, axis_sum)),
        "query_translated_destination": [query[0] + offset[0], query[1] + offset[1]],
        "palette_labels_in_component_order": [
            colours[0],
            colours[0],
            colours[1],
            colours[1],
            colours[2],
            colours[2],
        ],
    }
    return components, parameters


def _try_reflection(
    rng: SplitMix64, role_colours: Sequence[int]
) -> tuple[tuple[Component, ...], dict[str, JsonValue]] | _RejectedAttempt:
    axis = ("horizontal", "vertical")[rng.randbelow(2)]
    anchor_index = rng.randbelow(len(_REFLECTION_ANCHOR_SHAPES))
    anchor_orientation = 0 if axis == "horizontal" else 4
    anchor = _orient(_REFLECTION_ANCHOR_SHAPES[anchor_index], anchor_orientation)
    protrusion_position = rng.randbelow(3)
    symmetric_core = tuple((row, col) for row in range(3) for col in range(3))
    horizontal_core = _normalise(
        (*((row + 1, col) for row, col in symmetric_core), (0, protrusion_position))
    )
    complete_core = horizontal_core if axis == "horizontal" else _orient(horizontal_core, 4)
    incomplete_core = symmetric_core
    if axis == "vertical":
        incomplete_core = _orient(incomplete_core, 4)
    if _flip(anchor, axis) != anchor or _flip(incomplete_core, axis) != incomplete_core:
        raise LockboxSchemaError("reflection anchors/incomplete core must be axis-symmetric")
    if _flip(complete_core, axis) == complete_core:
        raise LockboxSchemaError("complete reflection core must retain one asymmetric protrusion")

    incomplete_origins = tuple(
        origin
        for origin in _valid_origins(incomplete_core)
        if (
            origin[0] >= INNER_MIN + 8
            and origin[0] + _shape_height(incomplete_core) - 1 <= INNER_MAX - 8
            if axis == "horizontal"
            else origin[1] >= INNER_MIN + 8
            and origin[1] + _shape_width(incomplete_core) - 1 <= INNER_MAX - 8
        )
    )
    if not incomplete_origins:
        raise LockboxSchemaError("reflection central-origin filter has no legal panel span")
    incomplete_origin = incomplete_origins[rng.randbelow(len(incomplete_origins))]
    incomplete_cells = _translate(incomplete_core, incomplete_origin)
    centre2 = _centre_twice(incomplete_cells)
    axis_sum = centre2[0] if axis == "horizontal" else centre2[1]
    if _reflect_cells(incomplete_cells, axis, axis_sum) != incomplete_cells:
        raise LockboxSchemaError("reflection incomplete core lost global symmetry")
    core_layouts: list[tuple[Shape, Shape]] = []
    for core_origin in _valid_origins(complete_core):
        first_core = _translate(complete_core, core_origin)
        if not _negative_of_central(first_core, incomplete_cells, axis):
            continue
        second_core = _reflect_cells(first_core, axis, axis_sum)
        if (
            all(
                INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
                for row, col in second_core
            )
            and _normalise(second_core) == _flip(complete_core, axis)
            and _is_separated(first_core, set(incomplete_cells))
            and _is_separated(second_core, set(incomplete_cells) | set(first_core))
        ):
            core_layouts.append((first_core, second_core))
    if not core_layouts:
        return _RejectedAttempt("reflection_panel_placement_unavailable")
    first_core, second_core = core_layouts[rng.randbelow(len(core_layouts))]
    occupied_core = set(incomplete_cells) | set(first_core) | set(second_core)
    anchor_layouts: list[tuple[Shape, Shape]] = []
    for anchor_origin in _valid_origins(anchor):
        first_anchor = _translate(anchor, anchor_origin)
        if not _negative_of_component(first_anchor, first_core, axis):
            continue
        second_anchor = _reflect_cells(first_anchor, axis, axis_sum)
        if (
            _normalise(second_anchor) == anchor
            and all(
                INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
                for row, col in second_anchor
            )
            and _is_separated(first_anchor, occupied_core)
            and _is_separated(second_anchor, occupied_core | set(first_anchor))
        ):
            anchor_layouts.append((first_anchor, second_anchor))
    if not anchor_layouts:
        return _RejectedAttempt("reflection_panel_placement_unavailable")
    first_anchor, second_anchor = anchor_layouts[rng.randbelow(len(anchor_layouts))]
    offset = _translation_offset(first_anchor, second_anchor)
    occupied = (
        set(first_anchor)
        | set(second_anchor)
        | set(first_core)
        | set(second_core)
        | set(incomplete_cells)
    )
    queries = _query_positions(
        occupied,
        axis=axis,
        axis_sum=axis_sum,
        relative_offset=offset,
        require_distinct_destinations=True,
    )
    if not queries:
        return _RejectedAttempt("reflection_query_placement_unavailable")
    query = queries[rng.randbelow(len(queries))]
    colours = tuple(role_colours[:2])
    components: tuple[Component, ...] = (
        ("auxiliary_anchor_a", colours[0], first_anchor),
        ("auxiliary_anchor_b", colours[0], second_anchor),
        ("asymmetric_core_a", colours[1], first_core),
        ("reflected_core_b", colours[1], second_core),
        ("incomplete_axis_symmetric_core", colours[1], incomplete_cells),
        ("off_axis_query", colours[1], (query,)),
    )
    parameters: dict[str, JsonValue] = {
        "anchor_catalogue_index": anchor_index,
        "anchor_orientation": anchor_orientation,
        "anchor_shape": [[row, col] for row, col in anchor],
        "symmetric_core_shape": [[row, col] for row, col in incomplete_core],
        "complete_core_shape": [[row, col] for row, col in complete_core],
        "seeded_protrusion_position": protrusion_position,
        "axis_orientation": axis,
        "axis_coordinate_twice": axis_sum,
        "relative_translation_offset": [offset[0], offset[1]],
        "query_cell": [query[0], query[1]],
        "query_reflected_destination": list(_reflect_cell(query, axis, axis_sum)),
        "query_translated_destination": [query[0] + offset[0], query[1] + offset[1]],
        "palette_labels_in_component_order": [
            colours[0],
            colours[0],
            colours[1],
            colours[1],
            colours[1],
            colours[1],
        ],
    }
    return components, parameters


def _try_build_family(
    family: str, rng: SplitMix64
) -> tuple[tuple[Component, ...], dict[str, JsonValue], int] | _RejectedAttempt:
    palette = _sample_attempt_palette(rng)
    background_label = palette[0]
    if family == "homologue":
        result = _try_homologue(rng, palette[1:])
    elif family == "containment":
        result = _try_containment(rng, palette[1:])
    elif family == "reflection":
        result = _try_reflection(rng, palette[1:])
    else:
        raise ValueError(f"unknown family: {family}")
    if isinstance(result, _RejectedAttempt):
        return result
    components, parameters = result
    parameters["attempt_palette_order"] = list(palette)
    return components, parameters, background_label


def _grid_from_components(
    components: Sequence[Component], background_label: int
) -> list[JsonValue]:
    grid = [[background_label for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for _, palette_label, cells in components:
        for row, col in cells:
            if grid[row][col] != background_label:
                raise LockboxSchemaError("generated components overlap")
            grid[row][col] = palette_label
    return grid


def _coordinate(row: int, col: int) -> list[JsonValue]:
    return [row, col]


def _attach_content_hash(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if "content_sha256" in payload:
        raise LockboxSchemaError("content_sha256 cannot be supplied before hashing")
    result = dict(payload)
    result["content_sha256"] = canonical_sha256(payload)
    return result


def _identity_pairs(size: int) -> list[JsonValue]:
    return [
        [_coordinate(row, col), _coordinate(row, col)]
        for row in range(size)
        for col in range(size)
    ]


def _translation_pairs(row_delta: int, col_delta: int) -> list[JsonValue]:
    return [
        [_coordinate(row, col), _coordinate(row + row_delta, col + col_delta)]
        for row in range(GRID_SIZE)
        for col in range(GRID_SIZE)
        if 0 <= row + row_delta < GRID_SIZE and 0 <= col + col_delta < GRID_SIZE
    ]


def _one_to_one_cell_map(pairs: list[JsonValue], domain: str) -> dict[str, JsonValue]:
    forward = [[pair[0], [pair[1]]] for pair in pairs]
    inverse_pairs = sorted(
        ((pair[1], pair[0]) for pair in pairs),
        key=lambda pair: tuple(pair[0]),
    )
    inverse = [[destination, source] for destination, source in inverse_pairs]
    return _attach_content_hash(
        {
            "domain": domain,
            "forward": forward,
            "inverse": inverse,
        }
    )


def _one_to_one_action_map(pairs: list[JsonValue], domain: str) -> dict[str, JsonValue]:
    inverse = sorted(
        ([pair[1], pair[0]] for pair in pairs),
        key=lambda pair: tuple(pair[0]),
    )
    return _attach_content_hash(
        {
            "domain": domain,
            "simple_forward": [["ACTION3", "ACTION3"]],
            "simple_inverse": [["ACTION3", "ACTION3"]],
            "action6_forward": pairs,
            "action6_inverse": inverse,
        }
    )


def _scale_cell_map() -> dict[str, JsonValue]:
    forward: list[JsonValue] = []
    inverse: list[JsonValue] = []
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            source = _coordinate(row, col)
            targets = [
                _coordinate(SCALE_FACTOR * row + row_offset, SCALE_FACTOR * col + col_offset)
                for row_offset in range(SCALE_FACTOR)
                for col_offset in range(SCALE_FACTOR)
            ]
            forward.append([source, targets])
            inverse.extend([[target, source] for target in targets])
    inverse.sort(key=lambda entry: tuple(entry[0]))
    return _attach_content_hash(
        {
            "domain": "all_base_cells_to_complete_2x2_blocks",
            "forward": forward,
            "inverse": inverse,
        }
    )


def _scale_action_map() -> dict[str, JsonValue]:
    pairs = [
        [_coordinate(row, col), _coordinate(SCALE_FACTOR * row, SCALE_FACTOR * col)]
        for row in range(GRID_SIZE)
        for col in range(GRID_SIZE)
    ]
    return _one_to_one_action_map(pairs, "all_base_action6_cells_to_top_left_scaled_cells")


def _palette_bijection(rng: SplitMix64) -> tuple[list[int], list[int]]:
    forward = list(range(PALETTE_SIZE))
    rng.shuffle(forward)
    inverse = [0 for _ in range(PALETTE_SIZE)]
    for source, destination in enumerate(forward):
        inverse[destination] = source
    return forward, inverse


def _palette_grid(grid: list[JsonValue], forward: Sequence[int]) -> list[JsonValue]:
    return [
        [forward[int(value)] for value in row]
        for row in grid
    ]


def _translated_grid(
    grid: list[JsonValue], background_label: int, row_delta: int, col_delta: int
) -> list[JsonValue]:
    translated = [[background_label for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for row, values in enumerate(grid):
        for col, value in enumerate(values):
            label = int(value)
            if label != background_label:
                destination_row = row + row_delta
                destination_col = col + col_delta
                if not (
                    0 <= destination_row < GRID_SIZE and 0 <= destination_col < GRID_SIZE
                ):
                    raise LockboxSchemaError("translation clipped a non-background cell")
                translated[destination_row][destination_col] = label
    return translated


def _scaled_grid(grid: list[JsonValue]) -> list[JsonValue]:
    scaled: list[JsonValue] = []
    for row in grid:
        expanded = [value for value in row for _ in range(SCALE_FACTOR)]
        for _ in range(SCALE_FACTOR):
            scaled.append(list(expanded))
    return scaled


def _visual_transforms(
    grid: list[JsonValue], background_label: int, rng: SplitMix64
) -> list[JsonValue]:
    identity_pairs = _identity_pairs(GRID_SIZE)
    palette_stream_state = rng.state
    palette_forward, palette_inverse = _palette_bijection(rng)
    palette = _attach_content_hash(
        {
            "name": "palette_bijection",
            "parameters": {
                "splitmix64_state_before_shuffle_hex": f"{palette_stream_state:016x}",
                "forward_palette": palette_forward,
                "inverse_palette": palette_inverse,
            },
            "grid_shape": [GRID_SIZE, GRID_SIZE],
            "background_label": palette_forward[background_label],
            "grid": _palette_grid(grid, palette_forward),
            "grid_sha256": canonical_sha256(_palette_grid(grid, palette_forward)),
            "cell_map": _one_to_one_cell_map(identity_pairs, "all_32x32_coordinates"),
            "action_map": _one_to_one_action_map(identity_pairs, "all_32x32_action6_cells"),
            "frontier_mode": "regenerate_complete_frontier",
        }
    )

    translations: list[JsonValue] = []
    for name, row_delta, col_delta in (
        ("translation_row_plus_3_col_plus_5", 3, 5),
        ("translation_row_minus_3_col_minus_5", -3, -5),
    ):
        pairs = _translation_pairs(row_delta, col_delta)
        transformed_grid = _translated_grid(grid, background_label, row_delta, col_delta)
        translations.append(
            _attach_content_hash(
                {
                    "name": name,
                    "parameters": {"row_delta": row_delta, "col_delta": col_delta},
                    "grid_shape": [GRID_SIZE, GRID_SIZE],
                    "background_label": background_label,
                    "grid": transformed_grid,
                    "grid_sha256": canonical_sha256(transformed_grid),
                    "cell_map": _one_to_one_cell_map(
                        pairs, "exact_in_bounds_partial_coordinate_domain"
                    ),
                    "action_map": _one_to_one_action_map(
                        pairs, "exact_in_bounds_partial_action6_domain"
                    ),
                    "frontier_mode": "regenerate_complete_frontier",
                }
            )
        )

    scaled_grid = _scaled_grid(grid)
    scale = _attach_content_hash(
        {
            "name": "scale_2_nearest_neighbor",
            "parameters": {
                "factor": SCALE_FACTOR,
                "action6_destination_cell": "top_left_of_scaled_2x2_block",
            },
            "grid_shape": [GRID_SIZE * SCALE_FACTOR, GRID_SIZE * SCALE_FACTOR],
            "background_label": background_label,
            "grid": scaled_grid,
            "grid_sha256": canonical_sha256(scaled_grid),
            "cell_map": _scale_cell_map(),
            "action_map": _scale_action_map(),
            "frontier_mode": "fixed_mapped_base_action_list_only",
        }
    )
    result = [palette, *translations, scale]
    if tuple(transform["name"] for transform in result) != VISUAL_TRANSFORM_ORDER:
        raise LockboxSchemaError("visual transform order drifted")
    return result


def _inverse_output_to_input(permutation: list[int]) -> list[int]:
    inverse = [0] * len(permutation)
    for output_position, input_position in enumerate(permutation):
        inverse[input_position] = output_position
    return inverse


def _order_table(lengths: Iterable[int], operation: str) -> list[JsonValue]:
    table: list[JsonValue] = []
    for length in lengths:
        if operation == "reverse":
            forward = list(reversed(range(length)))
        elif operation == "left_rotation_by_one":
            forward = list(range(1, length)) + ([0] if length else [])
        else:
            raise ValueError(f"unknown order operation: {operation}")
        table.append(
            {
                "length": length,
                "forward_output_to_input": forward,
                "inverse_output_to_input": _inverse_output_to_input(forward),
            }
        )
    return table


def build_order_transform_maps() -> list[JsonValue]:
    """Build length-parametric index maps without instantiating behavior data."""

    definitions = (
        (
            "candidate_list_reversal",
            "candidate_sequence",
            "reverse",
            range(0, 13),
        ),
        (
            "candidate_list_left_rotation_by_one",
            "candidate_sequence",
            "left_rotation_by_one",
            range(0, 13),
        ),
        (
            "hypothesis_list_reversal",
            "hypothesis_sequence",
            "reverse",
            (4,),
        ),
        (
            "hypothesis_list_left_rotation_by_one",
            "hypothesis_sequence",
            "left_rotation_by_one",
            (4,),
        ),
        (
            "serialized_outcome_cell_order_reversal",
            "serialized_outcome_cell_sequence",
            "reverse",
            range(0, 5),
        ),
    )
    maps: list[JsonValue] = []
    for name, target, operation, lengths in definitions:
        if target == "candidate_sequence":
            correspondence = "exact serialized action identity; positions only reordered"
        elif target == "hypothesis_sequence":
            correspondence = "committee input index given by forward_output_to_input"
        else:
            correspondence = "exact cell identity; serialization only"
        maps.append(
            _attach_content_hash(
                {
                    "name": name,
                    "target_sequence": target,
                    "operation": operation,
                    "index_semantics": "output_position_to_input_position",
                    "correspondence_semantics": correspondence,
                    "maps_by_length": _order_table(lengths, operation),
                }
            )
        )
    if tuple(item["name"] for item in maps) != ORDER_TRANSFORM_ORDER:
        raise LockboxSchemaError("order transform set or order drifted")
    return maps


def assert_data_only_schema(value: JsonValue, *, path: str = "$") -> None:
    """Reject behavior, game, diagnostic, and resource fields recursively."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise LockboxSchemaError(
                    f"non-string JSON object key at {path}: {type(key).__name__}"
                )
            if key in FORBIDDEN_FIELD_NAMES:
                raise LockboxSchemaError(f"forbidden data-only field at {path}.{key}")
            assert_data_only_schema(nested, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            assert_data_only_schema(nested, path=f"{path}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise LockboxSchemaError(f"non-finite number at {path}")
    if not isinstance(value, (type(None), bool, int, float, str)):
        raise LockboxSchemaError(f"non-JSON value at {path}: {type(value).__name__}")


def _verify_content_hash(value: Mapping[str, JsonValue], *, path: str) -> None:
    digest = value.get("content_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise LockboxSchemaError(f"missing canonical content hash at {path}")
    unhashed = dict(value)
    del unhashed["content_sha256"]
    if canonical_sha256(unhashed) != digest:
        raise LockboxSchemaError(f"canonical content hash mismatch at {path}")


def _require_exact_keys(
    value: Mapping[str, JsonValue], expected: set[str], *, path: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise LockboxSchemaError(
            f"closed schema mismatch at {path}: missing={missing}, unknown={unknown}"
        )


def _components_from_records(records: JsonValue) -> tuple[Component, ...]:
    if not isinstance(records, list):
        raise LockboxSchemaError("components must be a list")
    result: list[Component] = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {"role", "palette_label", "cells"}:
            raise LockboxSchemaError("component record schema mismatch")
        role = record["role"]
        palette_label = record["palette_label"]
        raw_cells = record["cells"]
        if (
            not isinstance(role, str)
            or not isinstance(palette_label, int)
            or isinstance(palette_label, bool)
        ):
            raise LockboxSchemaError("component role/label types are invalid")
        if not isinstance(raw_cells, list):
            raise LockboxSchemaError("component cells must be a list")
        cells: list[Cell] = []
        for raw_cell in raw_cells:
            if (
                not isinstance(raw_cell, list)
                or len(raw_cell) != 2
                or any(
                    not isinstance(value, int) or isinstance(value, bool) for value in raw_cell
                )
            ):
                raise LockboxSchemaError("component coordinate is invalid")
            cells.append((raw_cell[0], raw_cell[1]))
        result.append((role, palette_label, tuple(cells)))
    return tuple(result)


def _validate_components(
    family: str, components: Sequence[Component], background_label: int
) -> None:
    expected_roles = {
        "homologue": (
            "panel_prototype_a",
            "panel_prototype_b",
            "separate_central_target",
            "off_axis_query",
        ),
        "containment": (
            "hollow_panel_a",
            "hollow_panel_b",
            "contained_component_a",
            "contained_component_b",
            "external_axis_symmetric_context",
            "off_axis_query",
        ),
        "reflection": (
            "auxiliary_anchor_a",
            "auxiliary_anchor_b",
            "asymmetric_core_a",
            "reflected_core_b",
            "incomplete_axis_symmetric_core",
            "off_axis_query",
        ),
    }
    if tuple(component[0] for component in components) != expected_roles[family]:
        raise LockboxSchemaError(f"{family} component roles drifted")
    occupied: set[Cell] = set()
    for role, palette_label, cells in components:
        if not 0 <= palette_label < PALETTE_SIZE or palette_label == background_label:
            raise LockboxSchemaError(f"invalid visible palette label for {role}")
        if tuple(sorted(set(cells))) != cells:
            raise LockboxSchemaError(f"component cells are not unique row-major data: {role}")
        if not _is_connected(cells):
            raise LockboxSchemaError(f"component is not four-neighbour connected: {role}")
        if not all(
            INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
            for row, col in cells
        ):
            raise LockboxSchemaError(f"component violates the six-cell base margin: {role}")
        if not _is_separated(cells, occupied):
            raise LockboxSchemaError(f"components overlap or touch: {role}")
        occupied.update(cells)

    if family == "homologue":
        first, second, target, query = components
        if _normalise(first[2]) != _normalise(second[2]) or first[1] != second[1]:
            raise LockboxSchemaError("homologue panel prototypes must be same-colour exact copies")
        if target[1] != query[1] or target[1] == first[1] or len(query[2]) != 1:
            raise LockboxSchemaError("homologue target/query colour scheme drifted")
        if len(target[2]) <= len(first[2]) + len(second[2]):
            raise LockboxSchemaError("homologue target must exceed total prototype colour area")
    elif family == "containment":
        first_ring, second_ring, first_inner, second_inner, external, query = components
        for ring in (first_ring, second_ring):
            ring_top = min(row for row, _ in ring[2])
            ring_bottom = max(row for row, _ in ring[2])
            ring_left = min(col for _, col in ring[2])
            ring_right = max(col for _, col in ring[2])
            expected_ring = {
                (row, col)
                for row in range(ring_top, ring_bottom + 1)
                for col in range(ring_left, ring_right + 1)
                if row in {ring_top, ring_bottom} or col in {ring_left, ring_right}
            }
            if set(ring[2]) != expected_ring:
                raise LockboxSchemaError("containment panel is not the exact hollow rectangle")
        if (
            _normalise(first_ring[2]) != _normalise(second_ring[2])
            or first_ring[1] != second_ring[1]
        ):
            raise LockboxSchemaError("containment rings must be same-colour exact homologues")
        for ring, inner in ((first_ring, first_inner), (second_ring, second_inner)):
            if not all(
                min(row for row, _ in ring[2]) < row < max(row for row, _ in ring[2])
                and min(col for _, col in ring[2]) < col < max(col for _, col in ring[2])
                for row, col in inner[2]
            ):
                raise LockboxSchemaError("matching contained component escaped its ring")
        if first_inner[1] != second_inner[1] or _normalise(first_inner[2]) != _normalise(
            second_inner[2]
        ):
            raise LockboxSchemaError("contained panel components are not matching homologues")
        if len(external[2]) <= len(first_ring[2]):
            raise LockboxSchemaError("external component area must exceed hollow ring area")
        if external[1] != query[1] or len(query[2]) != 1:
            raise LockboxSchemaError("containment context/query colour scheme drifted")
        if len({first_ring[1], first_inner[1], external[1]}) != 3:
            raise LockboxSchemaError("containment role groups must use three colours")
    else:
        first_anchor, second_anchor, first_core, second_core, incomplete, query = components
        if (
            first_anchor[1] != second_anchor[1]
            or _normalise(first_anchor[2]) != _normalise(second_anchor[2])
        ):
            raise LockboxSchemaError("reflection auxiliary anchors are not exact homologues")
        core_colour = first_core[1]
        if any(component[1] != core_colour for component in components[2:]):
            raise LockboxSchemaError("reflection core/context/query colours drifted")
        if core_colour == first_anchor[1] or len(query[2]) != 1:
            raise LockboxSchemaError("reflection anchor/query colour scheme drifted")
        if (
            len(second_core[2]) != len(first_core[2])
            or len(incomplete[2]) != len(first_core[2]) - 1
        ):
            raise LockboxSchemaError("reflection complete/incomplete areas drifted")


def _parameter_cell(parameters: Mapping[str, JsonValue], name: str) -> Cell:
    value = parameters.get(name)
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise LockboxSchemaError(f"invalid generation parameter coordinate: {name}")
    return value[0], value[1]


def _parameter_shape(parameters: Mapping[str, JsonValue], name: str) -> Shape:
    value = parameters.get(name)
    if not isinstance(value, list):
        raise LockboxSchemaError(f"invalid generation parameter shape: {name}")
    cells: list[Cell] = []
    for raw_cell in value:
        if (
            not isinstance(raw_cell, list)
            or len(raw_cell) != 2
            or any(
                not isinstance(item, int) or isinstance(item, bool) for item in raw_cell
            )
        ):
            raise LockboxSchemaError(f"invalid generation parameter shape cell: {name}")
        cells.append((raw_cell[0], raw_cell[1]))
    shape = tuple(cells)
    if shape != _normalise(shape) or not _is_connected(shape):
        raise LockboxSchemaError(f"generation parameter shape is not canonical/connected: {name}")
    return shape


def _reference_enclosed_cells(cells: Shape) -> frozenset[Cell]:
    top = min(row for row, _ in cells)
    bottom = max(row for row, _ in cells)
    left = min(col for _, col in cells)
    right = max(col for _, col in cells)
    wall = set(cells)
    local = {
        (row, col)
        for row in range(top - 1, bottom + 2)
        for col in range(left - 1, right + 2)
    }
    reachable = {(top - 1, left - 1)}
    frontier = [(top - 1, left - 1)]
    while frontier:
        cell = frontier.pop()
        for neighbour in _four_neighbours(cell):
            if neighbour in local and neighbour not in wall and neighbour not in reachable:
                reachable.add(neighbour)
                frontier.append(neighbour)
    return frozenset(local - wall - reachable)


def _reference_component_centre(cells: Shape) -> Cell:
    count = len(cells)
    row_sum = sum(row for row, _ in cells)
    col_sum = sum(col for _, col in cells)
    return min(
        cells,
        key=lambda cell: (
            (cell[0] * count - row_sum) ** 2 + (cell[1] * count - col_sum) ** 2,
            cell,
        ),
    )


def _reference_compiler_binding(
    components: Sequence[Component],
) -> tuple[Shape, Shape, str, int]:
    """Recompute the no-transition compiler rank/secondary/axis using stdlib only."""

    shapes = [_normalise(component[2]) for component in components]
    colour_counts = {
        colour: sum(
            len(cells)
            for _, candidate_colour, cells in components
            if candidate_colour == colour
        )
        for _, colour, _ in components
    }
    repeats = {shape: shapes.count(shape) for shape in set(shapes)}
    cell_owner = {
        cell: index for index, component in enumerate(components) for cell in component[2]
    }
    contained_by: list[set[int]] = [set() for _ in components]
    for outer_index, component in enumerate(components):
        for cell in _reference_enclosed_cells(component[2]):
            inner_index = cell_owner.get(cell)
            if inner_index is not None and inner_index != outer_index:
                contained_by[outer_index].add(inner_index)
    containment_depth = [
        sum(index in enclosed for enclosed in contained_by) for index in range(len(components))
    ]

    def symmetry_count(shape: Shape) -> int:
        height = _shape_height(shape)
        width = _shape_width(shape)
        cells = set(shape)
        horizontal = {(height - 1 - row, col) for row, col in shape} == cells
        vertical = {(row, width - 1 - col) for row, col in shape} == cells
        rotational = {
            (height - 1 - row, width - 1 - col) for row, col in shape
        } == cells
        return int(horizontal) + int(vertical) + int(rotational)

    def rank(index: int) -> tuple[JsonValue, ...]:
        _, colour, cells = components[index]
        return (
            -len(contained_by[index]),
            -containment_depth[index],
            colour_counts[colour],
            -repeats[shapes[index]],
            -symmetry_count(shapes[index]),
            False,
            shapes[index],
            cells,
        )

    primary_index = min(range(len(components)), key=rank)
    primary_cells = components[primary_index][2]
    homologues = [
        index
        for index in range(len(components))
        if index != primary_index and shapes[index] == shapes[primary_index]
    ]
    if not homologues:
        raise LockboxSchemaError("panel grammar failed to supply a primary homologue")
    primary_centre = _reference_component_centre(primary_cells)
    secondary_index = min(
        homologues,
        key=lambda index: (
            (primary_centre[0] - _reference_component_centre(components[index][2])[0]) ** 2
            + (primary_centre[1] - _reference_component_centre(components[index][2])[1]) ** 2,
            components[index][2],
        ),
    )
    secondary_cells = components[secondary_index][2]
    secondary_centre = _reference_component_centre(secondary_cells)
    offset = (
        secondary_centre[0] - primary_centre[0],
        secondary_centre[1] - primary_centre[1],
    )
    primary_bbox = (
        min(row for row, _ in primary_cells),
        min(col for _, col in primary_cells),
        max(row for row, _ in primary_cells),
        max(col for _, col in primary_cells),
    )
    secondary_bbox = (
        min(row for row, _ in secondary_cells),
        min(col for _, col in secondary_cells),
        max(row for row, _ in secondary_cells),
        max(col for _, col in secondary_cells),
    )
    if abs(offset[0]) >= abs(offset[1]):
        axis = "horizontal"
        axis_sum = (
            primary_bbox[0] + secondary_bbox[2]
            if offset[0] >= 0
            else primary_bbox[2] + secondary_bbox[0]
        )
    else:
        axis = "vertical"
        axis_sum = (
            primary_bbox[1] + secondary_bbox[3]
            if offset[1] >= 0
            else primary_bbox[3] + secondary_bbox[1]
        )
    return primary_cells, secondary_cells, axis, axis_sum


def _validate_family_geometry(
    family: str,
    components: Sequence[Component],
    parameters: Mapping[str, JsonValue],
) -> None:
    common = {
        "attempt_palette_order",
        "axis_orientation",
        "axis_coordinate_twice",
        "relative_translation_offset",
        "query_cell",
        "query_reflected_destination",
        "query_translated_destination",
        "palette_labels_in_component_order",
    }
    family_keys = {
        "homologue": {
            "prototype_catalogue_index",
            "prototype_orientation",
            "prototype_shape",
            "target_catalogue_index",
            "target_orientation",
            "target_shape",
        },
        "containment": {
            "ring_catalogue_index",
            "ring_height",
            "ring_width",
            "ring_shape",
            "context_variant",
            "context_shape",
            "contained_cell_a",
            "contained_cell_b",
        },
        "reflection": {
            "anchor_catalogue_index",
            "anchor_orientation",
            "anchor_shape",
            "symmetric_core_shape",
            "complete_core_shape",
            "seeded_protrusion_position",
        },
    }
    _require_exact_keys(parameters, common | family_keys[family], path="generation_parameters")
    axis = parameters.get("axis_orientation")
    axis_sum = parameters.get("axis_coordinate_twice")
    if (
        axis not in {"horizontal", "vertical"}
        or not isinstance(axis_sum, int)
        or isinstance(axis_sum, bool)
    ):
        raise LockboxSchemaError("family panel axis parameters are invalid")
    offset = _parameter_cell(parameters, "relative_translation_offset")
    query = _parameter_cell(parameters, "query_cell")
    reflected_destination = _parameter_cell(parameters, "query_reflected_destination")
    translated_destination = _parameter_cell(parameters, "query_translated_destination")
    if query != components[-1][2][0] or len(components[-1][2]) != 1:
        raise LockboxSchemaError("query parameter does not identify the singleton query")
    if reflected_destination != _reflect_cell(query, str(axis), axis_sum):
        raise LockboxSchemaError("query reflected destination parameter drifted")
    if translated_destination != (query[0] + offset[0], query[1] + offset[1]):
        raise LockboxSchemaError("query translated destination parameter drifted")
    if query in (reflected_destination, translated_destination):
        raise LockboxSchemaError("query must be off-axis and move under both mapped roles")
    if reflected_destination == translated_destination:
        raise LockboxSchemaError("query reflection/translation destinations must be distinct")
    if not all(
        INNER_MIN <= row <= INNER_MAX and INNER_MIN <= col <= INNER_MAX
        for row, col in (reflected_destination, translated_destination)
    ):
        raise LockboxSchemaError("query mapped destination violates the registered inner domain")
    occupied_without_query = {cell for component in components[:-1] for cell in component[2]}
    if (
        reflected_destination in occupied_without_query
        or translated_destination in occupied_without_query
    ):
        raise LockboxSchemaError("query mapped destination is not background")

    paired: tuple[tuple[Component, Component], ...]
    self_symmetric: tuple[Component, ...]
    if family == "homologue":
        paired = ((components[0], components[1]),)
        self_symmetric = (components[2],)
    elif family == "containment":
        paired = ((components[0], components[1]), (components[2], components[3]))
        self_symmetric = (components[4],)
    else:
        paired = ((components[0], components[1]), (components[2], components[3]))
        self_symmetric = (components[4],)
    for first, second in paired:
        if first[1] != second[1] or _reflect_cells(first[2], str(axis), axis_sum) != second[2]:
            raise LockboxSchemaError("paired component is not the registered global reflection")
    for component in self_symmetric:
        if _reflect_cells(component[2], str(axis), axis_sum) != component[2]:
            raise LockboxSchemaError("central component is not globally axis-symmetric")
    if offset != _translation_offset(components[0][2], components[1][2]):
        raise LockboxSchemaError("relative translation offset does not bind the panel anchors")
    expected_colours = [component[1] for component in components]
    if parameters.get("palette_labels_in_component_order") != expected_colours:
        raise LockboxSchemaError("component colour parameter order drifted")
    attempt_palette = parameters.get("attempt_palette_order")
    if not isinstance(attempt_palette, list):
        raise LockboxSchemaError("attempt palette parameter is missing")
    expected_role_colours = {
        "homologue": [
            attempt_palette[1],
            attempt_palette[1],
            attempt_palette[2],
            attempt_palette[2],
        ],
        "containment": [
            attempt_palette[1],
            attempt_palette[1],
            attempt_palette[2],
            attempt_palette[2],
            attempt_palette[3],
            attempt_palette[3],
        ],
        "reflection": [
            attempt_palette[1],
            attempt_palette[1],
            attempt_palette[2],
            attempt_palette[2],
            attempt_palette[2],
            attempt_palette[2],
        ],
    }
    if expected_colours != expected_role_colours[family]:
        raise LockboxSchemaError("component roles do not use the registered attempt palette slots")

    if family == "homologue":
        prototype_index = parameters.get("prototype_catalogue_index")
        prototype_orientation = parameters.get("prototype_orientation")
        target_index = parameters.get("target_catalogue_index")
        target_orientation = parameters.get("target_orientation")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (
                prototype_index,
                prototype_orientation,
                target_index,
                target_orientation,
            )
        ):
            raise LockboxSchemaError("homologue catalogue/orientation parameters are invalid")
        prototype_index = cast(int, prototype_index)
        prototype_orientation = cast(int, prototype_orientation)
        target_index = cast(int, target_index)
        target_orientation = cast(int, target_orientation)
        if (
            not 0 <= prototype_orientation < 8
            or not 0 <= target_orientation < 8
        ):
            raise LockboxSchemaError("homologue orientation is out of range")
        if not 0 <= prototype_index < len(_PANEL_ANCHOR_SHAPES) or not 0 <= target_index < len(
            _CENTRAL_TARGET_SHAPES
        ):
            raise LockboxSchemaError("homologue catalogue index is out of range")
        prototype_shape = _parameter_shape(parameters, "prototype_shape")
        target_shape = _parameter_shape(parameters, "target_shape")
        if prototype_shape != _orient(
            _PANEL_ANCHOR_SHAPES[prototype_index], prototype_orientation
        ) or target_shape != _orient(_CENTRAL_TARGET_SHAPES[target_index], target_orientation):
            raise LockboxSchemaError("homologue shape does not match catalogue/orientation")
        if _normalise(components[0][2]) != prototype_shape or _normalise(
            components[2][2]
        ) != target_shape:
            raise LockboxSchemaError("homologue component shapes differ from parameters")
    elif family == "containment":
        ring_dimensions = ((7, 7), (6, 8), (8, 6))
        ring_index = parameters.get("ring_catalogue_index")
        if (
            not isinstance(ring_index, int)
            or isinstance(ring_index, bool)
            or not 0 <= ring_index < 3
        ):
            raise LockboxSchemaError("containment ring catalogue index is invalid")
        ring_height, ring_width = ring_dimensions[ring_index]
        if (
            parameters.get("ring_height") != ring_height
            or parameters.get("ring_width") != ring_width
        ):
            raise LockboxSchemaError("containment ring dimensions differ from catalogue")
        if _parameter_shape(parameters, "ring_shape") != _ring_shape(ring_height, ring_width):
            raise LockboxSchemaError("containment ring shape differs from catalogue")
        registered_ring_shape = _ring_shape(ring_height, ring_width)
        if any(
            _normalise(component[2]) != registered_ring_shape for component in components[:2]
        ):
            raise LockboxSchemaError("containment panel cells differ from the selected ring")
        context_variant = parameters.get("context_variant")
        if (
            not isinstance(context_variant, int)
            or isinstance(context_variant, bool)
            or context_variant not in {0, 1}
        ):
            raise LockboxSchemaError("containment context variant is invalid")
        horizontal_context = tuple(
            (row, col)
            for row in range(3)
            for col in range(9)
            if not (context_variant == 1 and (row, col) == (1, 4))
        )
        expected_context = (
            horizontal_context if axis == "horizontal" else _orient(horizontal_context, 4)
        )
        if _parameter_shape(parameters, "context_shape") != expected_context:
            raise LockboxSchemaError("containment context shape differs from seeded variant")
        if _normalise(components[4][2]) != expected_context:
            raise LockboxSchemaError("containment context component differs from parameters")
        if (
            _parameter_cell(parameters, "contained_cell_a") != components[2][2][0]
            or _parameter_cell(parameters, "contained_cell_b") != components[3][2][0]
        ):
            raise LockboxSchemaError("containment contained-cell parameters drifted")
        for ring, contained in ((components[0], components[2]), (components[1], components[3])):
            top = min(row for row, _ in ring[2])
            bottom = max(row for row, _ in ring[2])
            left = min(col for _, col in ring[2])
            right = max(col for _, col in ring[2])
            row, col = contained[2][0]
            if not (top + 2 <= row <= bottom - 2 and left + 2 <= col <= right - 2):
                raise LockboxSchemaError("contained component lacks a one-cell interior moat")
            query_row, query_col = query
            if top < query_row < bottom and left < query_col < right:
                raise LockboxSchemaError(
                    "unmatched containment query must remain outside both rings"
                )
    else:
        anchor_index = parameters.get("anchor_catalogue_index")
        anchor_orientation = parameters.get("anchor_orientation")
        protrusion_position = parameters.get("seeded_protrusion_position")
        if (
            not isinstance(anchor_index, int)
            or isinstance(anchor_index, bool)
            or not 0 <= anchor_index < len(_REFLECTION_ANCHOR_SHAPES)
            or not isinstance(anchor_orientation, int)
            or isinstance(anchor_orientation, bool)
            or not 0 <= anchor_orientation < 8
            or not isinstance(protrusion_position, int)
            or isinstance(protrusion_position, bool)
            or protrusion_position not in {0, 1, 2}
        ):
            raise LockboxSchemaError("reflection catalogue/orientation parameters are invalid")
        expected_orientation = 0 if axis == "horizontal" else 4
        if anchor_orientation != expected_orientation:
            raise LockboxSchemaError("reflection anchor orientation differs from seeded axis")
        expected_anchor = _orient(
            _REFLECTION_ANCHOR_SHAPES[anchor_index], anchor_orientation
        )
        if _parameter_shape(parameters, "anchor_shape") != expected_anchor:
            raise LockboxSchemaError("reflection anchor shape differs from catalogue")
        symmetric_core = tuple((row, col) for row in range(3) for col in range(3))
        horizontal_complete = _normalise(
            (*((row + 1, col) for row, col in symmetric_core), (0, protrusion_position))
        )
        expected_complete = (
            horizontal_complete if axis == "horizontal" else _orient(horizontal_complete, 4)
        )
        expected_incomplete = symmetric_core if axis == "horizontal" else _orient(symmetric_core, 4)
        complete_parameter = _parameter_shape(parameters, "complete_core_shape")
        incomplete_parameter = _parameter_shape(parameters, "symmetric_core_shape")
        if complete_parameter != expected_complete or incomplete_parameter != expected_incomplete:
            raise LockboxSchemaError("reflection core shapes differ from seeded protrusion")
        if len(complete_parameter) != len(incomplete_parameter) + 1 or not any(
            _normalise(set(complete_parameter) - {cell}) == incomplete_parameter
            for cell in complete_parameter
            if _is_connected(set(complete_parameter) - {cell})
        ):
            raise LockboxSchemaError("reflection complete core is not core plus one protrusion")
        if _normalise(components[0][2]) != expected_anchor:
            raise LockboxSchemaError("reflection anchor component differs from parameters")
        if _normalise(components[2][2]) != expected_complete or _normalise(
            components[4][2]
        ) != expected_incomplete:
            raise LockboxSchemaError("reflection core components differ from parameters")
    primary_cells, secondary_cells, reference_axis, reference_axis_sum = (
        _reference_compiler_binding(components)
    )
    if primary_cells != components[0][2] or secondary_cells != components[1][2]:
        raise LockboxSchemaError("reference compiler did not bind the registered panel anchors")
    if reference_axis != axis or reference_axis_sum != axis_sum:
        raise LockboxSchemaError("reference compiler axis differs from the registered panel axis")


def _validate_grid(grid: JsonValue, *, size: int, background_label: int) -> None:
    if not isinstance(grid, list) or len(grid) != size:
        raise LockboxSchemaError("grid row count mismatch")
    for row in grid:
        if not isinstance(row, list) or len(row) != size:
            raise LockboxSchemaError("grid column count mismatch")
        for label in row:
            if (
                not isinstance(label, int)
                or isinstance(label, bool)
                or not 0 <= label < PALETTE_SIZE
            ):
                raise LockboxSchemaError("grid palette label is invalid")
    if any(grid[0][col] != background_label for col in range(size)):
        raise LockboxSchemaError("top border is not background")
    if any(grid[size - 1][col] != background_label for col in range(size)):
        raise LockboxSchemaError("bottom border is not background")
    if any(grid[row][0] != background_label for row in range(size)):
        raise LockboxSchemaError("left border is not background")
    if any(grid[row][size - 1] != background_label for row in range(size)):
        raise LockboxSchemaError("right border is not background")


def _require_map_hashes(transform: Mapping[str, JsonValue], *, path: str) -> None:
    for map_name in ("cell_map", "action_map"):
        value = transform.get(map_name)
        if not isinstance(value, dict):
            raise LockboxSchemaError(f"missing {map_name} at {path}")
        expected_keys = (
            {"domain", "forward", "inverse", "content_sha256"}
            if map_name == "cell_map"
            else {
                "domain",
                "simple_forward",
                "simple_inverse",
                "action6_forward",
                "action6_inverse",
                "content_sha256",
            }
        )
        _require_exact_keys(value, expected_keys, path=f"{path}.{map_name}")
        _verify_content_hash(value, path=f"{path}.{map_name}")


def _validate_visual_transforms(
    base_grid: list[JsonValue], base_background_label: int, transforms: JsonValue
) -> int:
    if not isinstance(transforms, list) or len(transforms) != 4:
        raise LockboxSchemaError("every complete scene must carry exactly four visual transforms")
    if tuple(transform.get("name") for transform in transforms if isinstance(transform, dict)) != (
        VISUAL_TRANSFORM_ORDER
    ):
        raise LockboxSchemaError("visual transform names/order mismatch")
    identity_pairs = _identity_pairs(GRID_SIZE)
    palette_final_state: int | None = None
    for index, transform in enumerate(transforms):
        if not isinstance(transform, dict):
            raise LockboxSchemaError("visual transform must be a mapping")
        path = f"visual_transforms[{index}]"
        _require_exact_keys(
            transform,
            {
                "name",
                "parameters",
                "grid_shape",
                "background_label",
                "grid",
                "grid_sha256",
                "cell_map",
                "action_map",
                "frontier_mode",
                "content_sha256",
            },
            path=path,
        )
        _verify_content_hash(transform, path=path)
        _require_map_hashes(transform, path=path)
        name = transform["name"]
        grid = transform.get("grid")
        grid_hash = transform.get("grid_sha256")
        if not isinstance(grid, list) or grid_hash != canonical_sha256(grid):
            raise LockboxSchemaError(f"transformed grid hash mismatch at {path}")
        if name == "palette_bijection":
            parameters = transform.get("parameters")
            if not isinstance(parameters, dict):
                raise LockboxSchemaError("palette parameters are missing")
            _require_exact_keys(
                parameters,
                {
                    "splitmix64_state_before_shuffle_hex",
                    "forward_palette",
                    "inverse_palette",
                },
                path=f"{path}.parameters",
            )
            forward = parameters.get("forward_palette")
            inverse = parameters.get("inverse_palette")
            stream_state = parameters.get("splitmix64_state_before_shuffle_hex")
            if (
                not isinstance(forward, list)
                or not isinstance(inverse, list)
                or len(forward) != PALETTE_SIZE
                or len(inverse) != PALETTE_SIZE
                or any(
                    isinstance(label, bool)
                    or not isinstance(label, int)
                    or not 0 <= label < PALETTE_SIZE
                    for label in forward
                )
                or any(
                    isinstance(label, bool)
                    or not isinstance(label, int)
                    or not 0 <= label < PALETTE_SIZE
                    for label in inverse
                )
                or set(forward) != set(range(PALETTE_SIZE))
                or set(inverse) != set(range(PALETTE_SIZE))
            ):
                raise LockboxSchemaError("palette maps are not full sixteen-label bijections")
            for source, destination in enumerate(forward):
                if inverse[destination] != source:
                    raise LockboxSchemaError("palette inverse does not invert forward map")
            if (
                not isinstance(stream_state, str)
                or len(stream_state) != 16
                or any(character not in "0123456789abcdef" for character in stream_state)
            ):
                raise LockboxSchemaError("palette SplitMix64 state is invalid")
            replay = SplitMix64(int(stream_state, 16))
            replay_forward, replay_inverse = _palette_bijection(replay)
            if forward != replay_forward or inverse != replay_inverse:
                raise LockboxSchemaError("palette bijection does not replay from pinned state")
            palette_final_state = replay.state
            expected_grid = _palette_grid(base_grid, forward)
            expected_pairs = identity_pairs
            expected_shape = [GRID_SIZE, GRID_SIZE]
            expected_background = forward[base_background_label]
        elif name in {
            "translation_row_plus_3_col_plus_5",
            "translation_row_minus_3_col_minus_5",
        }:
            parameters = transform.get("parameters")
            if not isinstance(parameters, dict):
                raise LockboxSchemaError("translation parameters are missing")
            _require_exact_keys(
                parameters,
                {"row_delta", "col_delta"},
                path=f"{path}.parameters",
            )
            row_delta = parameters.get("row_delta")
            col_delta = parameters.get("col_delta")
            if not isinstance(row_delta, int) or not isinstance(col_delta, int):
                raise LockboxSchemaError("translation deltas are invalid")
            expected_delta = (
                (3, 5)
                if name == "translation_row_plus_3_col_plus_5"
                else (-3, -5)
            )
            if (row_delta, col_delta) != expected_delta:
                raise LockboxSchemaError("translation name/delta contract mismatch")
            expected_grid = _translated_grid(
                base_grid, base_background_label, row_delta, col_delta
            )
            expected_pairs = _translation_pairs(row_delta, col_delta)
            expected_shape = [GRID_SIZE, GRID_SIZE]
            expected_background = base_background_label
        else:
            parameters = transform.get("parameters")
            if not isinstance(parameters, dict):
                raise LockboxSchemaError("scale parameters are missing")
            _require_exact_keys(
                parameters,
                {"factor", "action6_destination_cell"},
                path=f"{path}.parameters",
            )
            if parameters != {
                "factor": SCALE_FACTOR,
                "action6_destination_cell": "top_left_of_scaled_2x2_block",
            }:
                raise LockboxSchemaError("scale parameters drifted")
            expected_grid = _scaled_grid(base_grid)
            expected_pairs = []
            expected_shape = [GRID_SIZE * SCALE_FACTOR, GRID_SIZE * SCALE_FACTOR]
            expected_background = base_background_label
        if grid != expected_grid or transform.get("grid_shape") != expected_shape:
            raise LockboxSchemaError(f"visual grid transform mismatch at {path}")
        if transform.get("background_label") != expected_background:
            raise LockboxSchemaError(f"visual background label mismatch at {path}")
        expected_frontier_mode = (
            "fixed_mapped_base_action_list_only"
            if name == "scale_2_nearest_neighbor"
            else "regenerate_complete_frontier"
        )
        if transform.get("frontier_mode") != expected_frontier_mode:
            raise LockboxSchemaError(f"frontier-mode metadata mismatch at {path}")
        if name != "scale_2_nearest_neighbor":
            expected_cell_map = _one_to_one_cell_map(
                expected_pairs,
                (
                    "all_32x32_coordinates"
                    if name == "palette_bijection"
                    else "exact_in_bounds_partial_coordinate_domain"
                ),
            )
            expected_action_map = _one_to_one_action_map(
                expected_pairs,
                (
                    "all_32x32_action6_cells"
                    if name == "palette_bijection"
                    else "exact_in_bounds_partial_action6_domain"
                ),
            )
        else:
            expected_cell_map = _scale_cell_map()
            expected_action_map = _scale_action_map()
        if transform.get("cell_map") != expected_cell_map:
            raise LockboxSchemaError(f"cell map mismatch at {path}")
        if transform.get("action_map") != expected_action_map:
            raise LockboxSchemaError(f"action map mismatch at {path}")
    if palette_final_state is None:
        raise LockboxSchemaError("palette transform did not expose a replayable final state")
    return palette_final_state


def _validate_splitmix_telemetry(
    draw_count: JsonValue,
    state_hex: JsonValue,
    *,
    seed_hex: JsonValue,
    path: str,
) -> None:
    if (
        not isinstance(draw_count, int)
        or isinstance(draw_count, bool)
        or draw_count <= 0
        or draw_count > MASK64
        or not isinstance(state_hex, str)
        or len(state_hex) != 16
        or any(character not in "0123456789abcdef" for character in state_hex)
        or not isinstance(seed_hex, str)
        or len(seed_hex) != 16
        or any(character not in "0123456789abcdef" for character in seed_hex)
    ):
        raise LockboxSchemaError(f"invalid SplitMix64 draw/state telemetry at {path}")
    expected_state = (int(seed_hex, 16) + draw_count * SPLITMIX64_INCREMENT) & MASK64
    if int(state_hex, 16) != expected_state:
        raise LockboxSchemaError(f"SplitMix64 state does not match seed/draw count at {path}")


def validate_scene_record(scene: Mapping[str, JsonValue]) -> None:
    """Validate a generated open or registered scene without runtime imports."""

    assert_data_only_schema(dict(scene))
    _verify_content_hash(scene, path="scene")
    status = scene.get("generation_status")
    family = scene.get("family")
    if family not in FAMILIES:
        raise LockboxSchemaError("scene family is invalid")
    scope = scene.get("scope")
    if scope not in {"registered", "open_design"}:
        raise LockboxSchemaError("scene scope is invalid")
    family_index = scene.get("family_index")
    if scope == "registered":
        if (
            not isinstance(family_index, int)
            or isinstance(family_index, bool)
            or not 0 <= family_index < 4
        ):
            raise LockboxSchemaError("registered scene family index is invalid")
    elif "family_index" in scene:
        raise LockboxSchemaError("open-design scene must not carry a family index")
    expected_statuses = (
        {"complete", "registered_generation_exhausted"}
        if scope == "registered"
        else {"complete", "open_generation_exhausted"}
    )
    if status not in expected_statuses:
        raise LockboxSchemaError("scene scope/generation status pair is invalid")
    if status == "registered_generation_exhausted" or status == "open_generation_exhausted":
        expected = {
            "generation_status",
            "scope",
            "family",
            "seed_hex",
            "attempt_count",
            "rejection_reason_counts",
            "last_rejection_reason",
            "splitmix64_draw_count_at_exhaustion",
            "splitmix64_state_at_exhaustion_hex",
            "content_sha256",
        }
        if scene.get("scope") == "registered":
            expected.add("family_index")
        _require_exact_keys(scene, expected, path="scene")
        if scene.get("attempt_count") != REJECTION_ATTEMPT_CAP:
            raise LockboxSchemaError("exhaustion did not consume the fixed attempt cap")
        counts = scene.get("rejection_reason_counts")
        if (
            not isinstance(counts, dict)
            or not set(counts).issubset(REJECTION_REASONS)
            or any(not reason.startswith(f"{family}_") for reason in counts)
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count <= 0
                for count in counts.values()
            )
            or sum(counts.values()) != REJECTION_ATTEMPT_CAP
            or scene.get("last_rejection_reason") not in counts
        ):
            raise LockboxSchemaError("exhaustion rejection counts do not sum to the cap")
        _validate_splitmix_telemetry(
            scene.get("splitmix64_draw_count_at_exhaustion"),
            scene.get("splitmix64_state_at_exhaustion_hex"),
            seed_hex=scene.get("seed_hex"),
            path="scene exhaustion",
        )
        return
    if status != "complete":
        raise LockboxSchemaError("unknown generation status")
    expected_scene_keys = {
        "generation_status",
        "scope",
        "family",
        "seed_hex",
        "accepted_attempt_index",
        "rejection_reason_counts_before_acceptance",
        "base_scene",
        "visual_transforms",
        "splitmix64_draw_count_after_transforms",
        "splitmix64_state_after_transforms_hex",
        "content_sha256",
    }
    if scene.get("scope") == "registered":
        expected_scene_keys.add("family_index")
    _require_exact_keys(scene, expected_scene_keys, path="scene")
    attempt_index = scene.get("accepted_attempt_index")
    rejection_counts = scene.get("rejection_reason_counts_before_acceptance")
    if (
        not isinstance(attempt_index, int)
        or isinstance(attempt_index, bool)
        or not 0 <= attempt_index < REJECTION_ATTEMPT_CAP
        or not isinstance(rejection_counts, dict)
        or not set(rejection_counts).issubset(REJECTION_REASONS)
        or any(not reason.startswith(f"{family}_") for reason in rejection_counts)
        or any(
            not isinstance(count, int) or isinstance(count, bool) or count <= 0
            for count in rejection_counts.values()
        )
        or sum(rejection_counts.values()) != attempt_index
    ):
        raise LockboxSchemaError("accepted attempt/rejection-count telemetry is invalid")
    _validate_splitmix_telemetry(
        scene.get("splitmix64_draw_count_after_transforms"),
        scene.get("splitmix64_state_after_transforms_hex"),
        seed_hex=scene.get("seed_hex"),
        path="complete scene",
    )
    base_scene = scene.get("base_scene")
    if not isinstance(base_scene, dict):
        raise LockboxSchemaError("complete scene lacks base_scene")
    _require_exact_keys(
        base_scene,
        {
            "grid_shape",
            "background_label",
            "palette_labels",
            "grid",
            "grid_sha256",
            "components",
            "generation_parameters",
            "available_actions",
            "level",
            "win_levels",
            "initial_persistence",
            "content_sha256",
        },
        path="base_scene",
    )
    _verify_content_hash(base_scene, path="base_scene")
    if base_scene.get("grid_shape") != [GRID_SIZE, GRID_SIZE]:
        raise LockboxSchemaError("base grid shape drifted")
    background_label = base_scene.get("background_label")
    if (
        not isinstance(background_label, int)
        or isinstance(background_label, bool)
        or not 0 <= background_label < PALETTE_SIZE
    ):
        raise LockboxSchemaError("base background label is invalid")
    if base_scene.get("palette_labels") != list(range(PALETTE_SIZE)):
        raise LockboxSchemaError("base palette drifted")
    if base_scene.get("available_actions") != ["ACTION3", "ACTION6"]:
        raise LockboxSchemaError("available action metadata drifted")
    level = base_scene.get("level")
    win_levels = base_scene.get("win_levels")
    initial_persistence = base_scene.get("initial_persistence")
    if (
        not isinstance(level, int)
        or isinstance(level, bool)
        or level != 1
        or not isinstance(win_levels, int)
        or isinstance(win_levels, bool)
        or win_levels != 9
        or not isinstance(initial_persistence, float)
        or not math.isfinite(initial_persistence)
        or initial_persistence != 0.5
    ):
        raise LockboxSchemaError("level/persistence metadata drifted")
    parameters = base_scene.get("generation_parameters")
    if not isinstance(parameters, dict):
        raise LockboxSchemaError("generation parameters must be a mapping")
    attempt_palette = parameters.get("attempt_palette_order")
    if (
        not isinstance(attempt_palette, list)
        or len(attempt_palette) != PALETTE_SIZE
        or any(
            isinstance(label, bool)
            or not isinstance(label, int)
            or not 0 <= label < PALETTE_SIZE
            for label in attempt_palette
        )
        or set(attempt_palette) != set(range(PALETTE_SIZE))
        or attempt_palette[0] != background_label
    ):
        raise LockboxSchemaError("attempt palette is not the registered full seeded permutation")
    grid = base_scene.get("grid")
    _validate_grid(grid, size=GRID_SIZE, background_label=background_label)
    if not isinstance(grid, list) or base_scene.get("grid_sha256") != canonical_sha256(grid):
        raise LockboxSchemaError("base grid hash mismatch")
    components = _components_from_records(base_scene.get("components"))
    _validate_components(str(family), components, background_label)
    _validate_family_geometry(str(family), components, parameters)
    if grid != _grid_from_components(components, background_label):
        raise LockboxSchemaError("base grid does not exactly encode component records")
    transforms = scene.get("visual_transforms")
    palette_final_state = _validate_visual_transforms(grid, background_label, transforms)
    if scene.get("splitmix64_state_after_transforms_hex") != f"{palette_final_state:016x}":
        raise LockboxSchemaError("scene final SplitMix64 state differs from palette replay")


def _failure_scene_record(
    family: str,
    seed: int,
    *,
    scope: str,
    family_index: int | None,
    reason_counts: Mapping[str, int],
    last_reason: str,
    splitmix64_draw_count: int,
    splitmix64_state: int,
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "generation_status": (
            "registered_generation_exhausted"
            if scope == "registered"
            else "open_generation_exhausted"
        ),
        "scope": scope,
        "family": family,
        "seed_hex": f"{seed:016x}",
        "attempt_count": REJECTION_ATTEMPT_CAP,
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "last_rejection_reason": last_reason,
        "splitmix64_draw_count_at_exhaustion": splitmix64_draw_count,
        "splitmix64_state_at_exhaustion_hex": f"{splitmix64_state:016x}",
    }
    if family_index is not None:
        payload["family_index"] = family_index
    return _attach_content_hash(payload)


def _generate_scene_record(
    family: str,
    seed: int,
    *,
    scope: str,
    family_index: int | None,
) -> dict[str, JsonValue]:
    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= MASK64:
        raise ValueError("scene seed must be an unsigned 64-bit integer")
    rng = SplitMix64(seed)
    reason_counts: dict[str, int] = {}
    last_reason = ""
    for attempt_index in range(REJECTION_ATTEMPT_CAP):
        result = _try_build_family(family, rng)
        if isinstance(result, _RejectedAttempt):
            reason_counts[result.reason] = reason_counts.get(result.reason, 0) + 1
            last_reason = result.reason
            continue
        components, family_parameters, background_label = result
        _validate_components(family, components, background_label)
        grid = _grid_from_components(components, background_label)
        base_scene = _attach_content_hash(
            {
                "grid_shape": [GRID_SIZE, GRID_SIZE],
                "background_label": background_label,
                "palette_labels": list(range(PALETTE_SIZE)),
                "grid": grid,
                "grid_sha256": canonical_sha256(grid),
                "components": [_component_record(component) for component in components],
                "generation_parameters": family_parameters,
                "available_actions": ["ACTION3", "ACTION6"],
                "level": 1,
                "win_levels": 9,
                "initial_persistence": 0.5,
            }
        )
        payload: dict[str, JsonValue] = {
            "generation_status": "complete",
            "scope": scope,
            "family": family,
            "seed_hex": f"{seed:016x}",
            "accepted_attempt_index": attempt_index,
            "rejection_reason_counts_before_acceptance": dict(sorted(reason_counts.items())),
            "base_scene": base_scene,
            "visual_transforms": _visual_transforms(grid, background_label, rng),
        }
        payload["splitmix64_draw_count_after_transforms"] = rng.draw_count
        payload["splitmix64_state_after_transforms_hex"] = f"{rng.state:016x}"
        if family_index is not None:
            payload["family_index"] = family_index
        scene = _attach_content_hash(payload)
        validate_scene_record(scene)
        return scene
    return _failure_scene_record(
        family,
        seed,
        scope=scope,
        family_index=family_index,
        reason_counts=reason_counts,
        last_reason=last_reason,
        splitmix64_draw_count=rng.draw_count,
        splitmix64_state=rng.state,
    )


def generate_open_scene(family: str, seed: int) -> dict[str, JsonValue]:
    """Generate a disjoint open-design scene; registered seeds fail before evaluation."""

    if seed in _registered_seed_values():
        raise PermissionError("registered lockbox seeds require the reviewed freeze capability")
    return _generate_scene_record(family, seed, scope="open_design", family_index=None)


def _make_registered_freeze_capability(
    *,
    preregistration_commit: str,
    preregistration_file_sha256: str,
    preregistration_git_blob_oid: str,
    reviewed_head: str,
    generator_source_sha256: str,
) -> _RegisteredFreezeCapability:
    """Construct the explicit capability after the wrapper verifies repository provenance."""

    if preregistration_commit != PREREGISTRATION_COMMIT:
        raise PermissionError("preregistration commit identity mismatch")
    if preregistration_file_sha256 != PREREGISTRATION_FILE_SHA256:
        raise PermissionError("preregistration file SHA-256 identity mismatch")
    if preregistration_git_blob_oid != PREREGISTRATION_GIT_BLOB_OID:
        raise PermissionError("preregistration Git blob identity mismatch")
    if len(reviewed_head) != 40 or any(
        character not in "0123456789abcdef" for character in reviewed_head
    ):
        raise PermissionError("reviewed HEAD must be a lowercase Git commit digest")
    if len(generator_source_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in generator_source_sha256
    ):
        raise PermissionError("reviewed generator source must be a lowercase SHA-256 digest")
    return _RegisteredFreezeCapability(
        preregistration_commit=preregistration_commit,
        preregistration_file_sha256=preregistration_file_sha256,
        preregistration_git_blob_oid=preregistration_git_blob_oid,
        reviewed_head=reviewed_head,
        generator_source_sha256=generator_source_sha256,
    )


def _validate_seed_registration() -> None:
    if set(REGISTERED_SEED_HEX) != set(FAMILIES):
        raise LockboxSchemaError("registered seed families drifted")
    for family in FAMILIES:
        values = REGISTERED_SEED_HEX[family]
        if len(values) != 4:
            raise LockboxSchemaError("registered seed count drifted")
        for index, expected in enumerate(values):
            if f"{derive_registered_seed(family, index):016x}" != expected:
                raise LockboxSchemaError(f"registered seed derivation mismatch: {family}/{index}")
    if len(_registered_seed_values()) != 12:
        raise LockboxSchemaError("registered seeds are not globally unique")


def validate_registered_manifest(manifest: Mapping[str, JsonValue]) -> None:
    """Fully validate the data-only registered manifest in memory before publication."""

    assert_data_only_schema(dict(manifest))
    _require_exact_keys(
        manifest,
        {
            "schema_version",
            "generation_status",
            "generator_contract",
            "registration_provenance",
            "registered_seed_hex",
            "order_transform_maps",
            "scenes",
            "content_sha256",
        },
        path="manifest",
    )
    _verify_content_hash(manifest, path="manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise LockboxSchemaError("manifest schema version mismatch")
    if manifest.get("generator_contract") != GENERATOR_CONTRACT:
        raise LockboxSchemaError("manifest generator contract mismatch")
    provenance = manifest.get("registration_provenance")
    if not isinstance(provenance, dict):
        raise LockboxSchemaError("manifest registration provenance is missing")
    _require_exact_keys(
        provenance,
        {
            "policy_version",
            "public_split_sha256",
            "preregistration_commit",
            "preregistration_file_sha256",
            "preregistration_git_blob_oid",
            "reviewed_generator_commit",
            "generator_source_sha256",
            "generator_contract_sha256",
        },
        path="manifest.registration_provenance",
    )
    if (
        provenance.get("policy_version") != POLICY_VERSION
        or provenance.get("public_split_sha256") != PUBLIC_SPLIT_SHA256
        or provenance.get("preregistration_commit") != PREREGISTRATION_COMMIT
        or provenance.get("preregistration_file_sha256") != PREREGISTRATION_FILE_SHA256
        or provenance.get("preregistration_git_blob_oid") != PREREGISTRATION_GIT_BLOB_OID
        or provenance.get("generator_contract_sha256") != GENERATOR_CONTRACT_SHA256
        or canonical_sha256(GENERATOR_CONTRACT) != GENERATOR_CONTRACT_SHA256
    ):
        raise LockboxSchemaError("manifest registration provenance identity mismatch")
    reviewed_commit = provenance.get("reviewed_generator_commit")
    source_sha256 = provenance.get("generator_source_sha256")
    if (
        not isinstance(reviewed_commit, str)
        or len(reviewed_commit) != 40
        or any(character not in "0123456789abcdef" for character in reviewed_commit)
        or not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_sha256)
    ):
        raise LockboxSchemaError("reviewed generator commit/source identities are malformed")
    seed_table = manifest.get("registered_seed_hex")
    expected_seed_table: JsonValue = {
        family: list(REGISTERED_SEED_HEX[family]) for family in FAMILIES
    }
    if seed_table != expected_seed_table:
        raise LockboxSchemaError("manifest registered seed table mismatch")
    order_maps = manifest.get("order_transform_maps")
    if order_maps != build_order_transform_maps():
        raise LockboxSchemaError("manifest order transform maps mismatch")
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 12:
        raise LockboxSchemaError("manifest must contain all twelve registered results")
    seen: set[tuple[str, int]] = set()
    expected_order = [(family, index) for family in FAMILIES for index in range(4)]
    actual_order: list[tuple[str, int]] = []
    exhausted = False
    for scene in scenes:
        if not isinstance(scene, dict):
            raise LockboxSchemaError("manifest scene entry must be a mapping")
        validate_scene_record(scene)
        family = scene.get("family")
        family_index = scene.get("family_index")
        if (
            not isinstance(family, str)
            or not isinstance(family_index, int)
            or isinstance(family_index, bool)
        ):
            raise LockboxSchemaError("registered scene family/index is invalid")
        key = (family, family_index)
        actual_order.append(key)
        if key in seen:
            raise LockboxSchemaError("duplicate registered family/index")
        seen.add(key)
        if scene.get("seed_hex") != REGISTERED_SEED_HEX[family][family_index]:
            raise LockboxSchemaError("registered scene seed identity mismatch")
        exhausted = exhausted or scene.get("generation_status") == "registered_generation_exhausted"
    expected_keys = {(family, index) for family in FAMILIES for index in range(4)}
    if seen != expected_keys:
        raise LockboxSchemaError("registered scene coverage mismatch")
    if actual_order != expected_order:
        raise LockboxSchemaError("registered scenes are not in frozen family-major/index order")
    expected_status = "registered_generation_exhausted" if exhausted else "complete"
    if manifest.get("generation_status") != expected_status:
        raise LockboxSchemaError("manifest aggregate generation status mismatch")


def _build_registered_lockbox_manifest(
    capability: _RegisteredFreezeCapability,
) -> dict[str, JsonValue]:
    """Evaluate all registered seeds only for the provenance-checked freeze wrapper."""

    if not isinstance(capability, _RegisteredFreezeCapability):
        raise PermissionError("registered lockbox generation requires an explicit capability")
    if (
        capability.preregistration_commit != PREREGISTRATION_COMMIT
        or capability.preregistration_file_sha256 != PREREGISTRATION_FILE_SHA256
        or capability.preregistration_git_blob_oid != PREREGISTRATION_GIT_BLOB_OID
    ):
        raise PermissionError("registered lockbox capability is not bound to this preregistration")
    _validate_seed_registration()
    scenes: list[JsonValue] = []
    for family in FAMILIES:
        for family_index, seed_hex in enumerate(REGISTERED_SEED_HEX[family]):
            scenes.append(
                _generate_scene_record(
                    family,
                    int(seed_hex, 16),
                    scope="registered",
                    family_index=family_index,
                )
            )
    exhausted = any(
        isinstance(scene, dict)
        and scene.get("generation_status") == "registered_generation_exhausted"
        for scene in scenes
    )
    payload: dict[str, JsonValue] = {
        "schema_version": SCHEMA_VERSION,
        "generation_status": "registered_generation_exhausted" if exhausted else "complete",
        "generator_contract": GENERATOR_CONTRACT,
        "registration_provenance": {
            "policy_version": POLICY_VERSION,
            "public_split_sha256": PUBLIC_SPLIT_SHA256,
            "preregistration_commit": capability.preregistration_commit,
            "preregistration_file_sha256": capability.preregistration_file_sha256,
            "preregistration_git_blob_oid": capability.preregistration_git_blob_oid,
            "reviewed_generator_commit": capability.reviewed_head,
            "generator_source_sha256": capability.generator_source_sha256,
            "generator_contract_sha256": GENERATOR_CONTRACT_SHA256,
        },
        "registered_seed_hex": {
            family: list(REGISTERED_SEED_HEX[family]) for family in FAMILIES
        },
        "order_transform_maps": build_order_transform_maps(),
        "scenes": scenes,
    }
    manifest = _attach_content_hash(payload)
    validate_registered_manifest(manifest)
    return manifest
