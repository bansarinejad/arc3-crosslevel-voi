from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import os
import stat
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from arc3_voi import action_qbc_lockbox as lockbox
from scripts import freeze_action_qbc_lockbox as freeze_script

OPEN_SEEDS = {
    "homologue": 0x1020304050607080,
    "containment": 0x2233445566778899,
    "reflection": 0x3141592653589793,
}


@pytest.fixture(scope="module")
def open_scenes() -> dict[str, dict[str, lockbox.JsonValue]]:
    return {
        family: lockbox.generate_open_scene(family, seed)
        for family, seed in OPEN_SEEDS.items()
    }


def _component_map(scene: dict[str, lockbox.JsonValue]) -> dict[str, dict[str, Any]]:
    base = scene["base_scene"]
    assert isinstance(base, dict)
    components = base["components"]
    assert isinstance(components, list)
    return {component["role"]: component for component in components}


def _cells(component: dict[str, Any]) -> set[tuple[int, int]]:
    return {tuple(cell) for cell in component["cells"]}


def _reflect(
    cells: set[tuple[int, int]], axis: str, axis_sum: int
) -> set[tuple[int, int]]:
    if axis == "vertical":
        return {(row, axis_sum - col) for row, col in cells}
    return {(axis_sum - row, col) for row, col in cells}


def _normalized(cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    min_row = min(row for row, _ in cells)
    min_col = min(col for _, col in cells)
    return {(row - min_row, col - min_col) for row, col in cells}


def _refresh_content_hash(value: dict[str, Any]) -> None:
    unhashed = dict(value)
    unhashed.pop("content_sha256", None)
    value["content_sha256"] = lockbox.canonical_sha256(unhashed)


def _fake_registration_provenance(
    *, head: str = "a" * 40, source_sha256: str = "b" * 64
) -> dict[str, str]:
    return {
        "preregistration_commit": freeze_script.PREREGISTRATION_COMMIT,
        "preregistration_file_sha256": freeze_script.PREREGISTRATION_FILE_SHA256,
        "preregistration_git_blob_oid": freeze_script.PREREGISTRATION_GIT_BLOB_OID,
        "reviewed_generator_commit": head,
        "generator_source_sha256": source_sha256,
    }


def test_splitmix64_known_answer_vector() -> None:
    stream = lockbox.SplitMix64(0)

    assert [stream.next_u64() for _ in range(5)] == [
        0xE220A8397B1DCDAF,
        0x6E789E6AA1B965F4,
        0x06C45D188009454F,
        0xF88BB8A8724C81EC,
        0x1B39896A51A8749B,
    ]


def test_splitmix64_randbelow_rejects_biased_tail() -> None:
    class FixedDraws(lockbox.SplitMix64):
        def __init__(self) -> None:
            self.draws = iter((lockbox.MASK64, 17))

        def next_u64(self) -> int:
            return next(self.draws)

    stream = FixedDraws()

    assert stream.randbelow(10) == 7


def test_registered_seed_derivation_matches_frozen_table_without_scene_evaluation() -> None:
    derived = {
        family: tuple(f"{lockbox.derive_registered_seed(family, index):016x}" for index in range(4))
        for family in lockbox.FAMILIES
    }

    assert derived == lockbox.REGISTERED_SEED_HEX
    registered = {int(value, 16) for values in derived.values() for value in values}
    assert len(registered) == 12
    assert registered.isdisjoint(OPEN_SEEDS.values())


def test_open_api_rejects_registered_seed_before_generator_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_call(*args: object, **kwargs: object) -> dict[str, lockbox.JsonValue]:
        raise AssertionError("registered scene was evaluated")

    monkeypatch.setattr(lockbox, "_generate_scene_record", forbidden_call)
    registered_seed = int(lockbox.REGISTERED_SEED_HEX["homologue"][0], 16)

    with pytest.raises(PermissionError, match="registered lockbox seeds"):
        lockbox.generate_open_scene("homologue", registered_seed)


def test_forced_open_seed_exhaustion_is_deterministic_and_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = "homologue_panel_placement_unavailable"

    def reject(_family: str, _rng: lockbox.SplitMix64) -> object:
        _rng.next_u64()
        return lockbox._RejectedAttempt(reason)

    monkeypatch.setattr(lockbox, "_try_build_family", reject)
    first = lockbox.generate_open_scene("homologue", OPEN_SEEDS["homologue"])
    second = lockbox.generate_open_scene("homologue", OPEN_SEEDS["homologue"])

    assert first == second
    assert first["generation_status"] == "open_generation_exhausted"
    assert first["last_rejection_reason"] == reason
    assert first["rejection_reason_counts"] == {reason: lockbox.REJECTION_ATTEMPT_CAP}
    assert first["splitmix64_draw_count_at_exhaustion"] == lockbox.REJECTION_ATTEMPT_CAP
    expected_state = (
        OPEN_SEEDS["homologue"]
        + lockbox.REJECTION_ATTEMPT_CAP * lockbox.SPLITMIX64_INCREMENT
    ) & lockbox.MASK64
    assert first["splitmix64_state_at_exhaustion_hex"] == (
        f"{expected_state:016x}"
    )
    lockbox.validate_scene_record(first)


@pytest.mark.parametrize(
    "field",
    [
        "hypotheses",
        "candidate_list",
        "costs",
        "signatures",
        "expected_diagnostics",
        "pass_label",
        "model_calls",
        "environment_actions",
        "game_id",
        "recorded_transition",
    ],
)
def test_data_only_schema_rejects_forbidden_fields_recursively(field: str) -> None:
    with pytest.raises(lockbox.LockboxSchemaError, match="forbidden data-only field"):
        lockbox.assert_data_only_schema({"scene": [{"nested": {field: 0}}]})


def test_data_only_schema_rejects_non_string_object_keys() -> None:
    with pytest.raises(lockbox.LockboxSchemaError, match="non-string JSON object key"):
        lockbox.assert_data_only_schema({"scene": [{1: "would be coerced by json"}]})  # type: ignore[dict-item]


@pytest.mark.parametrize("field", ["level", "win_levels"])
def test_closed_scene_metadata_rejects_boolean_integer_aliases(
    field: str,
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = copy.deepcopy(open_scenes["homologue"])
    base = scene["base_scene"]
    base[field] = True
    _refresh_content_hash(base)
    _refresh_content_hash(scene)

    with pytest.raises(lockbox.LockboxSchemaError, match="level/persistence metadata"):
        lockbox.validate_scene_record(scene)


@pytest.mark.parametrize("location", ["attempt", "visual_forward", "visual_inverse"])
def test_mixed_type_palette_tampering_raises_schema_error_not_type_error(
    location: str,
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = copy.deepcopy(open_scenes["homologue"])
    base = scene["base_scene"]
    if location == "attempt":
        base["generation_parameters"]["attempt_palette_order"][0] = "0"
        _refresh_content_hash(base)
    else:
        palette = scene["visual_transforms"][0]
        key = "forward_palette" if location == "visual_forward" else "inverse_palette"
        palette["parameters"][key][0] = "0"
        _refresh_content_hash(palette)
    _refresh_content_hash(scene)

    with pytest.raises(lockbox.LockboxSchemaError, match="palette"):
        lockbox.validate_scene_record(scene)


def test_direct_content_tamper_is_rejected(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = copy.deepcopy(open_scenes["homologue"])
    scene["accepted_attempt_index"] = 1

    with pytest.raises(lockbox.LockboxSchemaError, match="content hash mismatch"):
        lockbox.validate_scene_record(scene)


def test_splitmix_draw_count_rejects_modulo_alias(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = copy.deepcopy(open_scenes["homologue"])
    scene["splitmix64_draw_count_after_transforms"] += 1 << 64
    _refresh_content_hash(scene)

    with pytest.raises(lockbox.LockboxSchemaError, match="draw/state telemetry"):
        lockbox.validate_scene_record(scene)


@pytest.mark.parametrize("map_name", ["cell_map", "action_map"])
def test_semantic_map_tamper_fails_after_public_hashes_are_recomputed(
    map_name: str,
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    # The JSON round trip ensures no in-memory list alias can make expected data drift with
    # the tampered map.
    scene = json.loads(json.dumps(open_scenes["homologue"]))
    transform = scene["visual_transforms"][1]
    mapping = transform[map_name]
    if map_name == "cell_map":
        mapping["forward"][0][1][0][0] += 1
    else:
        mapping["action6_forward"][0][1][0] += 1
    _refresh_content_hash(mapping)
    _refresh_content_hash(transform)
    _refresh_content_hash(scene)

    with pytest.raises(lockbox.LockboxSchemaError, match="map mismatch"):
        lockbox.validate_scene_record(scene)


def test_query_geometry_tamper_fails_after_public_hashes_are_recomputed(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = json.loads(json.dumps(open_scenes["reflection"]))
    base = scene["base_scene"]
    parameters = base["generation_parameters"]
    parameters["query_reflected_destination"][0] += 1
    _refresh_content_hash(base)
    _refresh_content_hash(scene)

    with pytest.raises(lockbox.LockboxSchemaError, match="query reflected destination"):
        lockbox.validate_scene_record(scene)


def test_attempt_telemetry_authority_does_not_claim_seed_replay() -> None:
    authority = lockbox.GENERATOR_CONTRACT["rejection"]["attempt_telemetry_authority"]

    assert "exact reviewed generator source" in authority
    assert "never resamples a seed" in authority


@pytest.mark.parametrize("family", tuple(OPEN_SEEDS))
def test_open_scene_common_geometry_is_independently_closed(
    family: str,
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = open_scenes[family]
    assert scene["generation_status"] == "complete"
    assert scene["scope"] == "open_design"
    assert scene["family"] == family
    lockbox.validate_scene_record(scene)
    components = _component_map(scene)
    base = scene["base_scene"]
    assert isinstance(base, dict)
    parameters = base["generation_parameters"]
    assert isinstance(parameters, dict)
    axis = parameters["axis_orientation"]
    axis_sum = parameters["axis_coordinate_twice"]
    assert isinstance(axis, str)
    assert isinstance(axis_sum, int)

    occupied: set[tuple[int, int]] = set()
    for component in components.values():
        component_cells = _cells(component)
        assert component_cells
        assert not occupied.intersection(component_cells)
        assert all(6 <= row <= 25 and 6 <= col <= 25 for row, col in component_cells)
        occupied.update(component_cells)
    query = _cells(components["off_axis_query"])
    non_query = occupied - query
    assert _reflect(non_query, axis, axis_sum) == non_query

    query_cell = tuple(parameters["query_cell"])
    reflected = tuple(parameters["query_reflected_destination"])
    translated = tuple(parameters["query_translated_destination"])
    offset = tuple(parameters["relative_translation_offset"])
    assert query == {query_cell}
    assert reflected == next(iter(_reflect(query, axis, axis_sum)))
    assert translated == (query_cell[0] + offset[0], query_cell[1] + offset[1])
    assert reflected != translated
    assert reflected not in occupied
    assert translated not in occupied
    assert all(6 <= value <= 25 for cell in (reflected, translated) for value in cell)


def test_homologue_open_scene_has_exact_reflected_panels_and_larger_target(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = open_scenes["homologue"]
    components = _component_map(scene)
    parameters = scene["base_scene"]["generation_parameters"]
    first = _cells(components["panel_prototype_a"])
    second = _cells(components["panel_prototype_b"])
    target = _cells(components["separate_central_target"])
    query = components["off_axis_query"]
    axis = parameters["axis_orientation"]
    axis_sum = parameters["axis_coordinate_twice"]

    assert second == _reflect(first, axis, axis_sum)
    assert _normalized(first) == _normalized(second)
    assert target == _reflect(target, axis, axis_sum)
    assert len(target) > len(first) + len(second)
    assert components["panel_prototype_a"]["palette_label"] == (
        components["panel_prototype_b"]["palette_label"]
    )
    assert query["palette_label"] == components["separate_central_target"]["palette_label"]
    assert query["palette_label"] != components["panel_prototype_a"]["palette_label"]


def test_containment_open_scene_has_equal_perimeter_reflected_rings_and_moats(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = open_scenes["containment"]
    components = _component_map(scene)
    parameters = scene["base_scene"]["generation_parameters"]
    first_ring = _cells(components["hollow_panel_a"])
    second_ring = _cells(components["hollow_panel_b"])
    first_inner = _cells(components["contained_component_a"])
    second_inner = _cells(components["contained_component_b"])
    context = _cells(components["external_axis_symmetric_context"])
    query = next(iter(_cells(components["off_axis_query"])))
    axis = parameters["axis_orientation"]
    axis_sum = parameters["axis_coordinate_twice"]

    assert (parameters["ring_height"], parameters["ring_width"]) in {
        (7, 7),
        (6, 8),
        (8, 6),
    }
    assert len(first_ring) == len(second_ring) == 24
    assert second_ring == _reflect(first_ring, axis, axis_sum)
    assert second_inner == _reflect(first_inner, axis, axis_sum)
    assert context == _reflect(context, axis, axis_sum)
    assert len(context) > len(first_ring)
    for ring, inner in ((first_ring, first_inner), (second_ring, second_inner)):
        rows = [row for row, _ in ring]
        cols = [col for _, col in ring]
        bounds = min(rows), max(rows), min(cols), max(cols)
        assert all(
            bounds[0] + 1 < row < bounds[1] - 1
            and bounds[2] + 1 < col < bounds[3] - 1
            for row, col in inner
        )
        assert not (
            bounds[0] - 1 <= query[0] <= bounds[1] + 1
            and bounds[2] - 1 <= query[1] <= bounds[3] + 1
        )


def test_reflection_open_scene_is_complete_minus_one_seeded_protrusion(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    scene = open_scenes["reflection"]
    components = _component_map(scene)
    parameters = scene["base_scene"]["generation_parameters"]
    first_anchor = _cells(components["auxiliary_anchor_a"])
    second_anchor = _cells(components["auxiliary_anchor_b"])
    first_core = _cells(components["asymmetric_core_a"])
    second_core = _cells(components["reflected_core_b"])
    incomplete = _cells(components["incomplete_axis_symmetric_core"])
    axis = parameters["axis_orientation"]
    axis_sum = parameters["axis_coordinate_twice"]

    assert second_anchor == _reflect(first_anchor, axis, axis_sum)
    assert second_core == _reflect(first_core, axis, axis_sum)
    assert incomplete == _reflect(incomplete, axis, axis_sum)
    complete_shape = {tuple(cell) for cell in parameters["complete_core_shape"]}
    symmetric_shape = {tuple(cell) for cell in parameters["symmetric_core_shape"]}
    assert len(complete_shape) == len(symmetric_shape) + 1
    assert any(
        _normalized(complete_shape - {protrusion}) == symmetric_shape
        for protrusion in complete_shape
    )
    assert components["off_axis_query"]["palette_label"] == (
        components["incomplete_axis_symmetric_core"]["palette_label"]
    )
    assert components["off_axis_query"]["palette_label"] != (
        components["auxiliary_anchor_a"]["palette_label"]
    )


def test_order_maps_are_parametric_only_and_define_empty_sequences() -> None:
    maps = lockbox.build_order_transform_maps()

    assert [mapping["name"] for mapping in maps] == list(lockbox.ORDER_TRANSFORM_ORDER)
    candidate_reverse = maps[0]
    candidate_rotate = maps[1]
    assert [row["length"] for row in candidate_reverse["maps_by_length"]] == list(range(13))
    assert [row["length"] for row in candidate_rotate["maps_by_length"]] == list(range(13))
    assert candidate_reverse["maps_by_length"][0]["forward_output_to_input"] == []
    assert candidate_reverse["maps_by_length"][12]["forward_output_to_input"] == list(
        reversed(range(12))
    )
    assert candidate_rotate["maps_by_length"][0]["forward_output_to_input"] == []
    assert candidate_rotate["maps_by_length"][4]["forward_output_to_input"] == [1, 2, 3, 0]
    assert maps[2]["maps_by_length"] == [
        {
            "length": 4,
            "forward_output_to_input": [3, 2, 1, 0],
            "inverse_output_to_input": [3, 2, 1, 0],
        }
    ]
    assert maps[0]["correspondence_semantics"] == (
        "exact serialized action identity; positions only reordered"
    )
    assert maps[2]["correspondence_semantics"] == (
        "committee input index given by forward_output_to_input"
    )
    assert maps[4]["correspondence_semantics"] == "exact cell identity; serialization only"
    assert [row["length"] for row in maps[4]["maps_by_length"]] == list(range(5))
    serialized = lockbox.canonical_json_bytes(maps)
    for forbidden_key in (b'"candidates":', b'"hypotheses":', b'"signatures":'):
        assert forbidden_key not in serialized
    assert not serialized.endswith(b"\n")


def test_visual_palette_bijection_covers_all_labels_and_round_trips(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    for scene in open_scenes.values():
        transform = scene["visual_transforms"][0]
        parameters = transform["parameters"]
        forward = parameters["forward_palette"]
        inverse = parameters["inverse_palette"]
        assert sorted(forward) == list(range(16))
        assert sorted(inverse) == list(range(16))
        assert all(inverse[destination] == source for source, destination in enumerate(forward))
        assert len(transform["cell_map"]["forward"]) == 32 * 32
        assert len(transform["action_map"]["action6_forward"]) == 32 * 32
        assert transform["action_map"]["simple_forward"] == [["ACTION3", "ACTION3"]]
        assert transform["action_map"]["simple_inverse"] == [["ACTION3", "ACTION3"]]


def test_visual_transform_grids_are_independently_reconstructed(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    for scene in open_scenes.values():
        base = scene["base_scene"]
        base_grid = base["grid"]
        background = base["background_label"]
        transforms = scene["visual_transforms"]

        palette_forward = transforms[0]["parameters"]["forward_palette"]
        assert transforms[0]["grid"] == [
            [palette_forward[value] for value in row] for row in base_grid
        ]

        for transform in transforms[1:3]:
            row_delta = transform["parameters"]["row_delta"]
            col_delta = transform["parameters"]["col_delta"]
            expected = [[background for _ in range(32)] for _ in range(32)]
            for row, values in enumerate(base_grid):
                for col, value in enumerate(values):
                    if value != background:
                        expected[row + row_delta][col + col_delta] = value
            assert transform["grid"] == expected

        expected_scale = [
            [value for value in row for _ in range(2)]
            for row in base_grid
            for _ in range(2)
        ]
        assert transforms[3]["grid"] == expected_scale
        for transform in transforms:
            assert transform["grid_sha256"] == lockbox.canonical_sha256(transform["grid"])
            for map_name in ("cell_map", "action_map"):
                mapping = transform[map_name]
                unhashed = dict(mapping)
                digest = unhashed.pop("content_sha256")
                assert digest == lockbox.canonical_sha256(unhashed)


@pytest.mark.parametrize(
    ("name", "row_delta", "col_delta"),
    [
        ("translation_row_plus_3_col_plus_5", 3, 5),
        ("translation_row_minus_3_col_minus_5", -3, -5),
    ],
)
def test_translation_maps_have_exact_partial_domains_and_round_trip(
    name: str,
    row_delta: int,
    col_delta: int,
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    transforms = open_scenes["homologue"]["visual_transforms"]
    transform = next(item for item in transforms if item["name"] == name)
    forward_entries = transform["cell_map"]["forward"]
    inverse_entries = transform["cell_map"]["inverse"]
    forward = {tuple(source): tuple(destinations[0]) for source, destinations in forward_entries}
    inverse = {tuple(destination): tuple(source) for destination, source in inverse_entries}
    expected = {
        (row, col): (row + row_delta, col + col_delta)
        for row in range(32)
        for col in range(32)
        if 0 <= row + row_delta < 32 and 0 <= col + col_delta < 32
    }
    assert forward == expected
    assert inverse == {destination: source for source, destination in expected.items()}
    assert [tuple(entry[0]) for entry in forward_entries] == sorted(expected)
    assert [tuple(entry[0]) for entry in inverse_entries] == sorted(inverse)
    assert transform["action_map"]["action6_forward"] == [
        [list(source), list(destination)] for source, destination in expected.items()
    ]


def test_scale_maps_pin_block_order_destination_order_and_actions(
    open_scenes: dict[str, dict[str, lockbox.JsonValue]],
) -> None:
    transform = open_scenes["homologue"]["visual_transforms"][3]
    forward_entries = transform["cell_map"]["forward"]
    inverse_entries = transform["cell_map"]["inverse"]
    assert len(forward_entries) == 32 * 32
    assert len(inverse_entries) == 64 * 64
    inverse = {tuple(destination): tuple(source) for destination, source in inverse_entries}
    assert [tuple(entry[0]) for entry in inverse_entries] == [
        (row, col) for row in range(64) for col in range(64)
    ]
    for source, destinations in forward_entries:
        row, col = source
        expected = [
            [2 * row, 2 * col],
            [2 * row, 2 * col + 1],
            [2 * row + 1, 2 * col],
            [2 * row + 1, 2 * col + 1],
        ]
        assert destinations == expected
        assert all(inverse[tuple(destination)] == tuple(source) for destination in destinations)
    assert transform["action_map"]["action6_forward"] == [
        [[row, col], [2 * row, 2 * col]] for row in range(32) for col in range(32)
    ]
    assert transform["action_map"]["action6_inverse"] == [
        [[2 * row, 2 * col], [row, col]] for row in range(32) for col in range(32)
    ]


def test_generator_imports_are_standard_library_only() -> None:
    source_path = Path("src/arc3_voi/action_qbc_lockbox.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    forbidden_calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "open", "__import__"}
        ):
            forbidden_calls.add(node.func.id)

    assert imports <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "hashlib",
        "json",
        "math",
        "typing",
    }
    assert forbidden_calls == set()


def test_freeze_wrapper_has_zero_project_imports() -> None:
    tree = ast.parse(
        Path("scripts/freeze_action_qbc_lockbox.py").read_text(encoding="utf-8")
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    assert imports <= {
        "__future__",
        "argparse",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "stat",
        "subprocess",
        "sys",
        "types",
        "typing",
    }
    assert not any(name == "arc3_voi" or name.startswith("arc3_voi.") for name in imports)


@pytest.mark.parametrize("hash_seed", ["0", "1", "4294967295"])
def test_fresh_interpreter_imports_only_the_data_module_and_is_hashseed_stable(
    hash_seed: str,
) -> None:
    source = """
import json
import sys
sys.path.insert(0, 'src')
before = set(sys.modules)
from arc3_voi import action_qbc_lockbox as module
seeds = {
    'homologue': 0x1020304050607080,
    'containment': 0x2233445566778899,
    'reflection': 0x3141592653589793,
}
scenes = [module.generate_open_scene(family, seed) for family, seed in seeds.items()]
project = sorted(
    name for name in set(sys.modules) - before
    if name == 'arc3_voi' or name.startswith('arc3_voi.')
)
print(json.dumps({
    'project': project,
    'contract': module.GENERATOR_CONTRACT_SHA256,
    'scene_hashes': [scene['content_sha256'] for scene in scenes],
    'order_hash': module.canonical_sha256(module.build_order_transform_maps()),
}, sort_keys=True))
"""
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        [sys.executable, "-S", "-B", "-c", source],
        check=True,
        capture_output=True,
        cwd=Path.cwd(),
        env=environment,
        text=True,
    )
    observed = json.loads(result.stdout)
    expected_hashes = [
        lockbox.generate_open_scene(family, seed)["content_sha256"]
        for family, seed in OPEN_SEEDS.items()
    ]
    assert observed["project"] == ["arc3_voi", "arc3_voi.action_qbc_lockbox"]
    assert observed["contract"] == lockbox.GENERATOR_CONTRACT_SHA256
    assert observed["scene_hashes"] == expected_hashes
    assert observed["order_hash"] == lockbox.canonical_sha256(
        lockbox.build_order_transform_maps()
    )


def test_isolated_wrapper_loads_only_exact_data_source_bytes() -> None:
    root_literal = json.dumps(os.fspath(Path.cwd()))
    source = f"""
import hashlib
import importlib.util
import json
import pathlib
import sys
root = pathlib.Path({root_literal})
wrapper_path = root / 'scripts' / 'freeze_action_qbc_lockbox.py'
spec = importlib.util.spec_from_file_location('_freeze_wrapper_isolation_test', wrapper_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
generator_raw = (root / module.CANONICAL_GENERATOR_SOURCE).read_bytes()
wrapper_raw = wrapper_path.read_bytes()
before = set(sys.modules)
verified = module.VerifiedSource(
    generator_raw,
    'a' * 40,
    hashlib.sha256(generator_raw).hexdigest(),
    hashlib.sha256(wrapper_raw).hexdigest(),
)
lockbox_module = module.load_reviewed_generator(verified, root=root)
added = set(sys.modules) - before
forbidden_prefixes = (
    'arc3_voi.candidates',
    'arc3_voi.controller',
    'arc3_voi.planner',
    'arc3_voi.topology_compiler',
    'numpy',
    'torch',
    'transformers',
)
print(json.dumps({{
    'contract': lockbox_module.GENERATOR_CONTRACT_SHA256,
    'project': sorted(name for name in added if name == 'arc3_voi' or name.startswith('arc3_voi.')),
    'forbidden': sorted(name for name in added if name.startswith(forbidden_prefixes)),
}}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", source],
        check=True,
        capture_output=True,
        cwd=Path.cwd(),
        text=True,
    )

    observed = json.loads(result.stdout)
    assert observed == {
        "contract": lockbox.GENERATOR_CONTRACT_SHA256,
        "forbidden": [],
        "project": [],
    }


def test_canonical_output_rejects_other_paths_and_working_directories(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "artifacts").mkdir()

    assert freeze_script.require_canonical_output(
        freeze_script.CANONICAL_RELATIVE_OUTPUT,
        root=root,
        working_directory=root,
    ) == root / freeze_script.CANONICAL_RELATIVE_OUTPUT
    with pytest.raises(freeze_script.FreezePreconditionError, match="noncanonical"):
        freeze_script.require_canonical_output(
            Path("artifacts/alternate.json"), root=root, working_directory=root
        )
    with pytest.raises(freeze_script.FreezePreconditionError, match="repository root"):
        freeze_script.require_canonical_output(
            freeze_script.CANONICAL_RELATIVE_OUTPUT,
            root=root,
            working_directory=tmp_path,
        )


def test_freeze_refuses_existing_target_before_registered_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    output = artifacts / "action_conditional_qbc_v1_lockbox.json"
    output.write_bytes(b"existing\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(freeze_script, "ROOT", tmp_path)
    monkeypatch.setattr(freeze_script, "_require_isolated_runtime", lambda: None)
    monkeypatch.setattr(
        freeze_script, "require_canonical_invocation", lambda **_kwargs: None
    )

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("registered generation/provenance ran after replacement refusal")

    monkeypatch.setattr(freeze_script, "require_reviewed_clean_source", forbidden)
    monkeypatch.setattr(freeze_script, "load_reviewed_generator", forbidden)

    with pytest.raises(FileExistsError, match="refusing to replace"):
        freeze_script.freeze(
            reviewed_head="a" * 40,
            reviewed_generator_source_sha256="b" * 64,
        )
    assert output.read_bytes() == b"existing\n"


def test_freeze_generation_error_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "artifacts").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(freeze_script, "ROOT", tmp_path)
    monkeypatch.setattr(freeze_script, "_require_isolated_runtime", lambda: None)
    monkeypatch.setattr(
        freeze_script, "require_canonical_invocation", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        freeze_script,
        "require_reviewed_clean_source",
        lambda **_kwargs: freeze_script.VerifiedSource(b"x", "a" * 40, "b" * 64, "c" * 64),
    )
    capability = object()

    def fail(_capability: object) -> dict[str, Any]:
        raise RuntimeError("synthetic validation failure")

    fake_module = types.SimpleNamespace(
        _make_registered_freeze_capability=lambda **_kwargs: capability,
        _build_registered_lockbox_manifest=fail,
    )
    monkeypatch.setattr(
        freeze_script,
        "load_reviewed_generator",
        lambda _verified, **_kwargs: fake_module,
    )

    with pytest.raises(RuntimeError, match="synthetic validation failure"):
        freeze_script.freeze(
            reviewed_head="a" * 40,
            reviewed_generator_source_sha256="b" * 64,
        )
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_exclusive_writer_never_replaces_racing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "artifacts").mkdir()
    output = tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    reservation = freeze_script.reserve_publication(output, root=tmp_path)
    real_link = freeze_script.os.link

    def racing_link(source: Path, destination: Path) -> None:
        destination.write_bytes(b"racer\n")
        real_link(source, destination)

    monkeypatch.setattr(freeze_script.os, "link", racing_link)

    with pytest.raises(FileExistsError):
        freeze_script.publish_reserved_artifact(reservation, b"payload\n", root=tmp_path)
    freeze_script.abort_publication(reservation)
    assert output.read_bytes() == b"racer\n"
    assert not (tmp_path / freeze_script.CANONICAL_STAGING_OUTPUT).exists()
    assert not (tmp_path / freeze_script.CANONICAL_PROBE_OUTPUT).exists()


def test_post_link_staging_mutation_is_detected_and_canonical_link_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "artifacts").mkdir()
    output = tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    reservation = freeze_script.reserve_publication(output, root=tmp_path)
    real_link = freeze_script.os.link

    def mutating_link(source: Path, destination: Path) -> None:
        source.write_bytes(b"wrong-payload\n")
        real_link(source, destination)

    monkeypatch.setattr(freeze_script.os, "link", mutating_link)

    with pytest.raises(freeze_script.FreezePreconditionError, match="canonical output bytes"):
        freeze_script.publish_reserved_artifact(reservation, b"expected-payload\n", root=tmp_path)
    assert not os.path.lexists(output)
    freeze_script.abort_publication(reservation)
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_completed_link_interrupted_before_return_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "artifacts").mkdir()
    output = tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    reservation = freeze_script.reserve_publication(output, root=tmp_path)
    real_link = freeze_script.os.link

    def interrupted_link(source: Path, destination: Path) -> None:
        real_link(source, destination)
        raise KeyboardInterrupt

    monkeypatch.setattr(freeze_script.os, "link", interrupted_link)

    with pytest.raises(KeyboardInterrupt):
        freeze_script.publish_reserved_artifact(reservation, b"payload\n", root=tmp_path)
    assert not os.path.lexists(output)
    assert not reservation.published
    freeze_script.abort_publication(reservation)
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_interruption_at_publication_commit_point_is_rolled_back(
    tmp_path: Path,
) -> None:
    (tmp_path / "artifacts").mkdir()
    output = tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    reservation = freeze_script.reserve_publication(output, root=tmp_path)
    source_lines, start_line = inspect.getsourcelines(
        freeze_script.publish_reserved_artifact
    )
    commit_line = next(
        start_line + offset
        for offset, source_line in enumerate(source_lines)
        if source_line.strip() == "reservation.published = True"
    )

    def interrupt_before_commit(
        frame: types.FrameType, event: str, _argument: object
    ) -> Any:
        if (
            event == "line"
            and frame.f_code is freeze_script.publish_reserved_artifact.__code__
            and frame.f_lineno == commit_line
        ):
            raise KeyboardInterrupt
        return interrupt_before_commit

    sys.settrace(interrupt_before_commit)
    try:
        with pytest.raises(KeyboardInterrupt):
            freeze_script.publish_reserved_artifact(
                reservation, b"payload\n", root=tmp_path
            )
    finally:
        sys.settrace(None)

    assert not os.path.lexists(output)
    assert not reservation.published
    freeze_script.abort_publication(reservation)
    assert list((tmp_path / "artifacts").iterdir()) == []


@pytest.mark.parametrize(
    "relative",
    [freeze_script.CANONICAL_STAGING_OUTPUT, freeze_script.CANONICAL_PROBE_OUTPUT],
)
def test_stale_publication_paths_block_before_generator_load(
    relative: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "artifacts").mkdir()
    stale = tmp_path / relative
    stale.write_bytes(b"stale\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(freeze_script, "ROOT", tmp_path)
    monkeypatch.setattr(freeze_script, "_require_isolated_runtime", lambda: None)
    monkeypatch.setattr(
        freeze_script, "require_canonical_invocation", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        freeze_script,
        "require_reviewed_clean_source",
        lambda **_kwargs: freeze_script.VerifiedSource(b"x", "a" * 40, "b" * 64, "c" * 64),
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("generator loaded before publication reservation")

    monkeypatch.setattr(freeze_script, "load_reviewed_generator", forbidden)
    with pytest.raises(FileExistsError, match="publication path already exists"):
        freeze_script.freeze(
            reviewed_head="a" * 40,
            reviewed_generator_source_sha256="b" * 64,
        )
    assert stale.read_bytes() == b"stale\n"


def test_failed_hard_link_probe_cleans_reservation_without_loading_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "artifacts").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(freeze_script, "ROOT", tmp_path)
    monkeypatch.setattr(freeze_script, "_require_isolated_runtime", lambda: None)
    monkeypatch.setattr(
        freeze_script, "require_canonical_invocation", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        freeze_script,
        "require_reviewed_clean_source",
        lambda **_kwargs: freeze_script.VerifiedSource(b"x", "a" * 40, "b" * 64, "c" * 64),
    )
    monkeypatch.setattr(
        freeze_script.os,
        "link",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no hard links")),
    )
    monkeypatch.setattr(
        freeze_script,
        "load_reviewed_generator",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generator loaded after failed publication preflight")
        ),
    )

    with pytest.raises(OSError, match="no hard links"):
        freeze_script.freeze(
            reviewed_head="a" * 40,
            reviewed_generator_source_sha256="b" * 64,
        )
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_deterministic_exhaustion_manifest_is_pretty_frozen_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "artifacts").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(freeze_script, "ROOT", tmp_path)
    monkeypatch.setattr(freeze_script, "_require_isolated_runtime", lambda: None)
    monkeypatch.setattr(
        freeze_script, "require_canonical_invocation", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        freeze_script,
        "require_reviewed_clean_source",
        lambda **_kwargs: freeze_script.VerifiedSource(b"x", "a" * 40, "b" * 64, "c" * 64),
    )
    events: list[str] = []
    manifest = {
        "content_sha256": "d" * 64,
        "generation_status": "registered_generation_exhausted",
        "registration_provenance": _fake_registration_provenance(),
        "scenes": [],
    }

    def build(_capability: object) -> dict[str, Any]:
        events.append("build")
        return manifest

    fake_module = types.SimpleNamespace(
        _make_registered_freeze_capability=lambda **_kwargs: events.append("capability")
        or object(),
        _build_registered_lockbox_manifest=build,
        validate_registered_manifest=lambda _manifest: events.append("validate"),
    )

    def load(_verified: object, **_kwargs: object) -> object:
        staging = tmp_path / freeze_script.CANONICAL_STAGING_OUTPUT
        assert staging.exists()
        events.append("load")
        return fake_module

    monkeypatch.setattr(freeze_script, "load_reviewed_generator", load)
    output, frozen = freeze_script.freeze(
        reviewed_head="a" * 40,
        reviewed_generator_source_sha256="b" * 64,
    )

    assert frozen == manifest
    expected = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    assert output == tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    assert output.read_bytes() == expected
    assert events == ["load", "capability", "build", "validate"]
    assert not (tmp_path / freeze_script.CANONICAL_STAGING_OUTPUT).exists()
    assert not (tmp_path / freeze_script.CANONICAL_PROBE_OUTPUT).exists()


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("reviewed_generator_commit", "f" * 40),
        ("generator_source_sha256", "e" * 64),
        ("preregistration_commit", "d" * 40),
        ("preregistration_file_sha256", "c" * 64),
        ("preregistration_git_blob_oid", "b" * 40),
    ],
)
def test_wrapper_independently_binds_manifest_provenance(
    field: str, replacement: str
) -> None:
    verified = freeze_script.VerifiedSource(b"source", "a" * 40, "b" * 64, "c" * 64)
    manifest: dict[str, Any] = {
        "registration_provenance": _fake_registration_provenance()
    }
    manifest["registration_provenance"][field] = replacement

    with pytest.raises(freeze_script.FreezePreconditionError, match="manifest provenance"):
        freeze_script.require_manifest_provenance(manifest, verified)


def test_main_returns_two_for_frozen_deterministic_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = {
        "content_sha256": "d" * 64,
        "generation_status": "registered_generation_exhausted",
    }
    monkeypatch.setattr(
        freeze_script,
        "freeze",
        lambda **_kwargs: (Path("unused"), manifest),
    )
    exit_code = freeze_script.main(
        [
            "--reviewed-head",
            "a" * 40,
            "--reviewed-generator-source-sha256",
            "b" * 64,
        ]
    )

    assert exit_code == 2
    summary = json.loads(capsys.readouterr().out)
    assert summary["generation_status"] == "registered_generation_exhausted"
    assert summary["output"] == freeze_script.CANONICAL_RELATIVE_OUTPUT.as_posix()


def test_freeze_requires_isolated_no_site_no_bytecode_runtime() -> None:
    with pytest.raises(freeze_script.FreezePreconditionError, match="python -I -S -B"):
        freeze_script._require_isolated_runtime()


def test_reviewed_generator_load_uses_exact_verified_bytes_and_private_name() -> None:
    root = Path.cwd()
    generator_raw = (root / freeze_script.CANONICAL_GENERATOR_SOURCE).read_bytes()
    wrapper_raw = (root / freeze_script.CANONICAL_WRAPPER_SOURCE).read_bytes()
    verified = freeze_script.VerifiedSource(
        raw=generator_raw,
        head="a" * 40,
        source_sha256=hashlib.sha256(generator_raw).hexdigest(),
        wrapper_sha256=hashlib.sha256(wrapper_raw).hexdigest(),
    )
    private_name = "_arc3_voi_action_qbc_lockbox_reviewed"
    sys.modules.pop(private_name, None)
    try:
        module = freeze_script.load_reviewed_generator(verified, root=root)
        assert module.GENERATOR_CONTRACT_SHA256 == lockbox.GENERATOR_CONTRACT_SHA256
        assert sys.modules[private_name] is module
    finally:
        sys.modules.pop(private_name, None)

    sys.modules[private_name] = types.ModuleType(private_name)
    try:
        with pytest.raises(freeze_script.FreezePreconditionError, match="already occupied"):
            freeze_script.load_reviewed_generator(verified, root=root)
    finally:
        sys.modules.pop(private_name, None)


def test_dangling_canonical_output_symlink_is_treated_as_existing(
    tmp_path: Path,
) -> None:
    (tmp_path / "artifacts").mkdir()
    output = tmp_path / freeze_script.CANONICAL_RELATIVE_OUTPUT
    try:
        output.symlink_to(tmp_path / "missing-target.json")
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    with pytest.raises(FileExistsError, match="refusing to replace"):
        freeze_script.require_canonical_output(
            freeze_script.CANONICAL_RELATIVE_OUTPUT,
            root=tmp_path,
            working_directory=tmp_path,
        )


def test_symlinked_artifact_parent_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    real_artifacts = tmp_path / "real-artifacts"
    real_artifacts.mkdir()
    try:
        (root / "artifacts").symlink_to(real_artifacts, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink creation is unavailable: {error}")

    with pytest.raises(freeze_script.FreezePreconditionError, match="reparse"):
        freeze_script.require_canonical_output(
            freeze_script.CANONICAL_RELATIVE_OUTPUT,
            root=root,
            working_directory=root,
        )


def test_windows_reparse_attribute_is_rejected_even_without_symlink_mode() -> None:
    fake_stat = types.SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
    )

    assert freeze_script._is_reparse(fake_stat)


def test_reviewed_source_provenance_binds_head_tag_and_all_three_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_raw = b"reviewed generator\n"
    preregistration_raw = b"frozen preregistration\n"
    wrapper_raw = b"reviewed wrapper\n"
    for relative, raw in (
        (freeze_script.CANONICAL_GENERATOR_SOURCE, source_raw),
        (freeze_script.CANONICAL_PREREGISTRATION, preregistration_raw),
        (freeze_script.CANONICAL_WRAPPER_SOURCE, wrapper_raw),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    head = "a" * 40
    source_sha = hashlib.sha256(source_raw).hexdigest()
    monkeypatch.setattr(
        freeze_script,
        "PREREGISTRATION_FILE_SHA256",
        hashlib.sha256(preregistration_raw).hexdigest(),
    )

    def fake_git(
        *arguments: str,
        root: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        del root, check
        if arguments[:2] == ("status", "--porcelain=v1"):
            payload = b""
        elif arguments == ("rev-parse", "HEAD"):
            payload = f"{head}\n".encode()
        elif arguments == (
            "rev-parse",
            f"{freeze_script.PREREGISTRATION_TAG}^{{commit}}",
        ):
            payload = f"{freeze_script.PREREGISTRATION_COMMIT}\n".encode()
        elif arguments == (
            "rev-parse",
            f"{freeze_script.PREREGISTRATION_TAG}:"
            f"{freeze_script.CANONICAL_PREREGISTRATION.as_posix()}",
        ):
            payload = f"{freeze_script.PREREGISTRATION_GIT_BLOB_OID}\n".encode()
        elif arguments[0:2] == ("merge-base", "--is-ancestor"):
            return subprocess.CompletedProcess(arguments, 0, b"")
        elif arguments == (
            "show",
            f"{head}:{freeze_script.CANONICAL_GENERATOR_SOURCE.as_posix()}",
        ):
            payload = source_raw
        elif arguments == (
            "show",
            f"{head}:{freeze_script.CANONICAL_PREREGISTRATION.as_posix()}",
        ):
            payload = preregistration_raw
        elif arguments == (
            "show",
            f"{head}:{freeze_script.CANONICAL_WRAPPER_SOURCE.as_posix()}",
        ):
            payload = wrapper_raw
        else:  # pragma: no cover - makes unexpected provenance commands loud
            raise AssertionError(f"unexpected git command: {arguments}")
        return subprocess.CompletedProcess(arguments, 0, payload)

    monkeypatch.setattr(freeze_script, "_git", fake_git)
    verified = freeze_script.require_reviewed_clean_source(
        reviewed_head=head,
        reviewed_generator_source_sha256=source_sha,
        root=tmp_path,
    )

    assert verified.raw == source_raw
    assert verified.head == head
    assert verified.source_sha256 == source_sha
    assert verified.wrapper_sha256 == hashlib.sha256(wrapper_raw).hexdigest()


def test_dirty_worktree_stops_provenance_before_any_source_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        freeze_script,
        "_git",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            (), 0, b"?? unreviewed.py\n"
        ),
    )
    with pytest.raises(freeze_script.FreezePreconditionError, match="clean worktree"):
        freeze_script.require_reviewed_clean_source(
            reviewed_head="a" * 40,
            reviewed_generator_source_sha256="b" * 64,
            root=tmp_path,
        )


def test_source_hash_helper_uses_raw_bytes() -> None:
    raw = b"generator\r\nsource\n"
    assert freeze_script._sha256(raw) == hashlib.sha256(raw).hexdigest()
    assert os.linesep in {"\n", "\r\n"}
