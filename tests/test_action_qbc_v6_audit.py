from __future__ import annotations

import base64
import copy
import hashlib
import sys
import time
from collections.abc import Mapping
from typing import Any, cast

import numpy as np
import pytest

from arc3_voi import action_qbc_audit as v5_audit
from arc3_voi import action_qbc_v6_audit as audit
from arc3_voi import action_qbc_v6_reference as reference
from arc3_voi.action_qbc_lockbox import build_order_transform_maps, generate_open_scene
from arc3_voi.config import load_config
from arc3_voi.types import Action, ActionKind, GameState, Prediction

_OPEN_SCENE_SEEDS = {
    "homologue": 0x1020304050607080,
    "containment": 0x2233445566778899,
    "reflection": 0x3141592653589793,
}


def _prediction(
    grid: list[list[int]] | np.ndarray,
    *,
    state: GameState = GameState.NOT_FINISHED,
    level_delta: int = 0,
) -> Prediction:
    return Prediction(np.asarray(grid, dtype=np.int16), state, level_delta, {})


def _filled_prediction(
    rows: int,
    columns: int,
    *,
    background: int = 0,
    cells: Mapping[tuple[int, int], int] | None = None,
    state: GameState = GameState.NOT_FINISHED,
    level_delta: int = 0,
) -> Prediction:
    grid = np.full((rows, columns), background, dtype=np.int16)
    for (row, column), label in (cells or {}).items():
        grid[row, column] = label
    return _prediction(grid, state=state, level_delta=level_delta)


def _translation_contract(name: str, *, background: int = 0) -> reference.TransformContract:
    row_delta, column_delta = reference.TRANSLATION_DELTAS[name]
    return reference.make_transform_contract(
        name,
        background_label=background,
        parameters={"row_delta": row_delta, "col_delta": column_delta},
    )


def _translated_prediction(
    base: Prediction,
    *,
    row_delta: int,
    column_delta: int,
    background: int,
) -> Prediction:
    rows, columns = base.next_grid.shape
    transformed = np.full((rows, columns), background, dtype=np.int16)
    source_rows, source_columns = np.nonzero(base.next_grid != background)
    for source_row, source_column in zip(source_rows, source_columns, strict=True):
        destination_row = int(source_row) + row_delta
        destination_column = int(source_column) + column_delta
        if not (0 <= destination_row < rows and 0 <= destination_column < columns):
            raise ValueError("test fixture translation leaves the finite frame")
        transformed[destination_row, destination_column] = base.next_grid[source_row, source_column]
    return _prediction(
        transformed,
        state=base.game_state,
        level_delta=base.level_delta,
    )


def _synthetic_open_inventory() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    """Build public registered addresses without consulting either sealed lockbox."""

    templates = {
        family: cast(
            dict[str, Any],
            generate_open_scene(family, seed),
        )
        for family, seed in _OPEN_SCENE_SEEDS.items()
    }
    scenes: list[dict[str, Any]] = []
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for family in v5_audit.SEALED_SCENE_FAMILIES:
        for family_index in range(4):
            scene = copy.deepcopy(templates[family])
            scene["family_index"] = family_index
            if family_index:
                scene["content_sha256"] = reference.canonical_sha256(
                    {
                        "family": family,
                        "family_index": family_index,
                        "scope": "v6-open-test-placeholder",
                    }
                )
            scenes.append(scene)
            by_key[(family, family_index)] = scene

    registration_rows: list[dict[str, Any]] = []
    for scene in scenes:
        family = cast(str, scene["family"])
        family_index = cast(int, scene["family_index"])
        registration_rows.append(
            {
                "family": family,
                "fixture_sha256": scene["content_sha256"],
                "kind": "base_scene",
                "row_id": f"base:{family}:{family_index}",
                "scene_index": family_index,
            }
        )
    for scene in scenes:
        family = cast(str, scene["family"])
        family_index = cast(int, scene["family_index"])
        for transform in cast(list[dict[str, Any]], scene["visual_transforms"]):
            contract = reference.make_transform_contract(transform)
            name = cast(str, transform["name"])
            registration_rows.append(
                {
                    "family": family,
                    "kind": "visual_transform",
                    "row_id": f"visual:{family}:{family_index}:{name}",
                    "scene_index": family_index,
                    "source_grid_shape": list(
                        cast(dict[str, Any], scene["base_scene"])["grid_shape"]
                    ),
                    "transform": name,
                    "transform_contract_sha256": contract.contract_sha256,
                }
            )
    for scene in scenes:
        family = cast(str, scene["family"])
        family_index = cast(int, scene["family_index"])
        for name in v5_audit.ORDER_TRANSFORM_NAMES:
            registration_rows.append(
                {
                    "family": family,
                    "kind": "order_transform",
                    "row_id": f"order:{family}:{family_index}:{name}",
                    "scene_index": family_index,
                    "transform": name,
                }
            )
    registration_rows.extend(
        {
            "control_id": name,
            "kind": "control",
            "row_id": f"control:{name}",
        }
        for name in v5_audit.PREREGISTERED_CONTROL_ORDER
    )
    for row_index, row in enumerate(registration_rows):
        row["row_index"] = row_index

    raw_placeholders = v5_audit._not_completed_record_inventory(scenes)
    for row in raw_placeholders:
        if row["kind"] == "visual_transform":
            row["source_grid_shape"] = list(
                cast(
                    dict[str, Any],
                    by_key[(cast(str, row["family"]), cast(int, row["family_index"]))][
                        "base_scene"
                    ],
                )["grid_shape"]
            )
    accumulator = audit._bind_registered_row_inventory(
        raw_placeholders,
        registration_rows,
    )
    assert len(accumulator) == len(registration_rows) == 140
    return accumulator, registration_rows, by_key


def test_v6_reference_identities_and_reason_order_are_frozen() -> None:
    assert reference.GRID_EVIDENCE_SCHEMA_VERSION == ("action-qbc-v6-grid-evidence-table-v1")
    assert reference.GRID_EVIDENCE_ENCODING == "int16-le-c-v1"
    assert reference.FINITE_GRID_SEMANTICS_ID == ("action-qbc-v6-padded-finite-grid-v1")
    assert reference.PAYLOAD_CAP_BYTES == 67_108_864
    assert reference.VISUAL_TRANSFORM_NAMES == (
        "palette_bijection",
        "translation_row_plus_3_col_plus_5",
        "translation_row_minus_3_col_minus_5",
        "scale_2_nearest_neighbor",
    )
    assert len(reference.REASON_ORDER) == len(set(reference.REASON_ORDER)) == 26
    assert reference.canonicalize_reasons(
        (
            "mapped_prediction_grid_mismatch",
            "translation_prediction_overflow",
            "mapped_prediction_grid_mismatch",
        )
    ) == (
        "translation_prediction_overflow",
        "mapped_prediction_grid_mismatch",
    )
    with pytest.raises(reference.V6ReferenceError, match="unknown"):
        reference.canonicalize_reasons(("not-registered",))


def test_grid_blob_is_exact_little_endian_canonical_evidence() -> None:
    prediction = _prediction([[-1, 0], [15, 255]])
    raw = np.asarray([[-1, 0], [15, 255]], dtype=np.dtype("<i2")).tobytes(order="C")
    digest = hashlib.sha256(raw).hexdigest()
    expected_reference = f"{digest}:2:2:int16-le-c-v1"

    blob = reference.build_grid_blob(prediction)

    assert set(blob) == {
        "reference",
        "encoding",
        "shape",
        "byte_count",
        "data_base64",
        "sha256",
    }
    assert blob == {
        "reference": expected_reference,
        "encoding": "int16-le-c-v1",
        "shape": [2, 2],
        "byte_count": 8,
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": digest,
    }
    assert reference.grid_evidence_reference(prediction) == expected_reference
    assert reference.parse_grid_evidence_reference(expected_reference) == (
        digest,
        (2, 2),
        "int16-le-c-v1",
    )
    assert (
        reference.validate_prediction_grid_reference(
            expected_reference,
            grid_bytes_sha256=digest,
            grid_shape=[2, 2],
        )
        == expected_reference
    )


@pytest.mark.parametrize(
    "invalid_reference",
    [
        "0" * 64 + ":02:2:int16-le-c-v1",
        "0" * 64 + ":2:+2:int16-le-c-v1",
        "0" * 64 + ":0:2:int16-le-c-v1",
        "0" * 64 + ":65:2:int16-le-c-v1",
        "0" * 64 + ":2:2:int16-native-c-v1",
        "A" * 64 + ":2:2:int16-le-c-v1",
    ],
)
def test_grid_reference_rejects_noncanonical_domains(invalid_reference: str) -> None:
    with pytest.raises(reference.GridEvidenceTableError):
        reference.parse_grid_evidence_reference(invalid_reference)


def test_grid_registry_deduplicates_many_to_one_prediction_occurrences() -> None:
    first = _prediction([[1, 2], [3, 4]])
    same_grid_different_metadata = _prediction([[1, 2], [3, 4]], state=GameState.WIN, level_delta=1)
    second = _prediction([[4, 3], [2, 1]])
    registry = reference.GridEvidenceRegistry()

    occurrences = registry.add_predictions(
        (first, same_grid_different_metadata, None, second, first)
    )
    table = registry.as_json()

    assert occurrences[0] == occurrences[1] == occurrences[4]
    assert occurrences[2] is None
    assert occurrences[3] != occurrences[0]
    assert len(cast(list[object], table["blobs"])) == 2
    assert registry.references == tuple(sorted(cast(tuple[str, ...], registry.references)))
    decoded = reference.validate_grid_evidence_table(
        table,
        expected_references=occurrences,
    )
    assert tuple(decoded) == registry.references
    assert np.array_equal(decoded[cast(str, occurrences[0])], first.next_grid)
    assert np.array_equal(decoded[cast(str, occurrences[3])], second.next_grid)
    assert decoded[cast(str, occurrences[0])].flags.writeable is False


def test_grid_table_rejects_duplicate_orphan_missing_and_noncanonical_blobs() -> None:
    first = _prediction([[1, 2]])
    second = _prediction([[3, 4]])
    registry = reference.GridEvidenceRegistry()
    first_reference, second_reference = registry.add_predictions((first, second))
    table = registry.as_json()
    blobs = cast(list[dict[str, Any]], table["blobs"])

    invalid_tables: list[tuple[dict[str, Any], tuple[str | None, ...]]] = []

    duplicate = copy.deepcopy(table)
    cast(list[object], duplicate["blobs"]).append(copy.deepcopy(blobs[0]))
    invalid_tables.append((duplicate, (first_reference, second_reference)))

    reversed_order = copy.deepcopy(table)
    cast(list[object], reversed_order["blobs"]).reverse()
    invalid_tables.append((reversed_order, (first_reference, second_reference)))

    missing = copy.deepcopy(table)
    cast(list[object], missing["blobs"]).pop()
    invalid_tables.append((missing, (first_reference, second_reference)))

    orphan = copy.deepcopy(table)
    invalid_tables.append((orphan, (first_reference,)))

    extra_table_key = copy.deepcopy(table)
    extra_table_key["unexpected"] = True
    invalid_tables.append((extra_table_key, (first_reference, second_reference)))

    wrong_schema = copy.deepcopy(table)
    wrong_schema["schema_version"] = "wrong"
    invalid_tables.append((wrong_schema, (first_reference, second_reference)))

    for key, replacement in (
        ("encoding", "int16-native-c-v1"),
        ("shape", [1, 3]),
        ("byte_count", 3),
        ("data_base64", cast(str, blobs[0]["data_base64"]).rstrip("=")),
        ("sha256", "0" * 64),
        ("reference", "0" * 64 + ":1:2:int16-le-c-v1"),
    ):
        tampered = copy.deepcopy(table)
        cast(list[dict[str, Any]], tampered["blobs"])[0][key] = replacement
        invalid_tables.append((tampered, (first_reference, second_reference)))

    for invalid, expected_references in invalid_tables:
        with pytest.raises(reference.GridEvidenceTableError):
            reference.validate_grid_evidence_table(
                invalid,
                expected_references=expected_references,
            )


def test_empty_grid_table_is_exact_and_valid_only_for_no_references() -> None:
    table = reference.empty_grid_evidence_table()
    assert table == {
        "schema_version": "action-qbc-v6-grid-evidence-table-v1",
        "blobs": [],
    }
    assert not reference.validate_grid_evidence_table(table, expected_references=(None, None))
    prediction = _prediction([[0]])
    with pytest.raises(reference.GridEvidenceTableError, match="referenced set"):
        reference.validate_grid_evidence_table(
            table,
            expected_references=(reference.grid_evidence_reference(prediction),),
        )


def test_transform_contracts_have_exact_registered_fields_and_binding() -> None:
    palette = reference.make_transform_contract(
        reference.PALETTE_TRANSFORM_NAME,
        background_label=7,
        parameters={"forward_palette": list(reversed(range(16)))},
    )
    plus = _translation_contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    minus = _translation_contract(reference.TRANSLATION_MINUS_TRANSFORM_NAME)
    scale = reference.make_transform_contract(
        reference.SCALE_TRANSFORM_NAME,
        background_label=0,
        parameters={
            "factor": 2,
            "action6_destination_cell": "top_left_of_scaled_2x2_block",
        },
    )

    for contract in (palette, plus, minus, scale):
        serialized = contract.as_json()
        assert set(serialized) == {
            "name",
            "background_label",
            "parameters",
            "contract_sha256",
        }
        assert contract.contract_sha256 == reference.canonical_sha256(
            cast(reference.JsonValue, contract.core_json())
        )
        assert (
            reference.validate_transform_contract(
                serialized,
                expected_sha256=contract.contract_sha256,
            )
            == contract
        )


def test_transform_contract_rejects_field_value_digest_and_registration_tampering() -> None:
    contract = _translation_contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    valid = contract.as_json()
    invalid_values: list[dict[str, Any]] = []

    extra = copy.deepcopy(valid)
    extra["unexpected"] = 1
    invalid_values.append(extra)

    wrong_delta = copy.deepcopy(valid)
    cast(dict[str, Any], wrong_delta["parameters"])["row_delta"] = 4
    invalid_values.append(wrong_delta)

    boolean_background = copy.deepcopy(valid)
    boolean_background["background_label"] = True
    invalid_values.append(boolean_background)

    wrong_digest = copy.deepcopy(valid)
    wrong_digest["contract_sha256"] = "0" * 64
    invalid_values.append(wrong_digest)

    for invalid in invalid_values:
        with pytest.raises(reference.TransformContractError):
            reference.validate_transform_contract(
                invalid,
                expected_sha256=contract.contract_sha256,
            )
    with pytest.raises(reference.TransformContractError, match="binding"):
        reference.validate_transform_contract(valid, expected_sha256="f" * 64)


@pytest.mark.parametrize(
    ("name", "valid_sources", "invalid_sources"),
    [
        (
            reference.TRANSLATION_PLUS_TRANSFORM_NAME,
            ((0, 0), (4, 4)),
            ((5, 4), (4, 5)),
        ),
        (
            reference.TRANSLATION_MINUS_TRANSFORM_NAME,
            ((3, 5), (7, 9)),
            ((2, 5), (3, 4)),
        ),
    ],
)
def test_translation_action_map_has_exact_partial_domain_boundaries(
    name: str,
    valid_sources: tuple[tuple[int, int], ...],
    invalid_sources: tuple[tuple[int, int], ...],
) -> None:
    contract = _translation_contract(name)
    row_delta, column_delta = reference.TRANSLATION_DELTAS[name]
    action_map = reference.reconstruct_action_map(contract, (8, 10))

    assert action_map.domain == "exact_in_bounds_partial_action6_domain"
    assert action_map.source_shape == action_map.destination_shape == (8, 10)
    assert len(action_map.forward) == (8 - abs(row_delta)) * (10 - abs(column_delta))
    for row, column in valid_sources:
        assert reference.map_action(Action(ActionKind.ACTION6, row, column), action_map) == Action(
            ActionKind.ACTION6, row + row_delta, column + column_delta
        )
    for row, column in invalid_sources:
        with pytest.raises(reference.ActionMapError, match="outside"):
            reference.map_action(Action(ActionKind.ACTION6, row, column), action_map)

    simple = Action(ActionKind.ACTION3)
    assert reference.map_action(simple, action_map) is simple


def test_palette_and_scale_action_maps_are_exact_bijections() -> None:
    palette_contract = reference.make_transform_contract(
        reference.PALETTE_TRANSFORM_NAME,
        background_label=0,
        parameters={"forward_palette": list(range(16))},
    )
    palette_map = reference.reconstruct_action_map(palette_contract, (2, 3))
    assert dict(palette_map.forward) == {
        (0, 0): (0, 0),
        (0, 1): (0, 1),
        (0, 2): (0, 2),
        (1, 0): (1, 0),
        (1, 1): (1, 1),
        (1, 2): (1, 2),
    }

    scale_contract = reference.make_transform_contract(
        reference.SCALE_TRANSFORM_NAME,
        background_label=0,
        parameters={
            "factor": 2,
            "action6_destination_cell": "top_left_of_scaled_2x2_block",
        },
    )
    scale_map = reference.reconstruct_action_map(scale_contract, (2, 3))
    assert scale_map.destination_shape == (4, 6)
    assert dict(scale_map.forward) == {
        (0, 0): (0, 0),
        (0, 1): (0, 2),
        (0, 2): (0, 4),
        (1, 0): (2, 0),
        (1, 1): (2, 2),
        (1, 2): (2, 4),
    }
    assert len(scale_map.forward) == len(set(scale_map.forward.values()))
    with pytest.raises(reference.ActionMapError, match="destination"):
        reference.reconstruct_action_map(scale_contract, (33, 32))


def test_manifest_action_map_rejects_every_full_map_defect_class() -> None:
    expected = reference.reconstruct_action_map(
        _translation_contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME),
        (8, 10),
    )
    manifest = expected.as_json()
    reference.validate_manifest_action_map(manifest, expected)
    assert cast(str, manifest["content_sha256"]) == reference.canonical_sha256(
        cast(
            reference.JsonValue,
            {key: value for key, value in manifest.items() if key != "content_sha256"},
        )
    )

    invalid_maps: list[object] = [None, [], {**manifest, "unexpected": True}]

    missing = copy.deepcopy(manifest)
    cast(list[object], missing["action6_forward"]).pop()
    invalid_maps.append(missing)

    duplicate_source = copy.deepcopy(manifest)
    forward = cast(list[list[list[int]]], duplicate_source["action6_forward"])
    forward[1][0] = list(forward[0][0])
    invalid_maps.append(duplicate_source)

    duplicate_destination = copy.deepcopy(manifest)
    forward = cast(list[list[list[int]]], duplicate_destination["action6_forward"])
    forward[1][1] = list(forward[0][1])
    invalid_maps.append(duplicate_destination)

    out_of_range = copy.deepcopy(manifest)
    cast(list[list[list[int]]], out_of_range["action6_forward"])[0][0][0] = 64
    invalid_maps.append(out_of_range)

    non_bijective_inverse = copy.deepcopy(manifest)
    cast(list[list[list[int]]], non_bijective_inverse["action6_inverse"])[0][1] = [7, 9]
    invalid_maps.append(non_bijective_inverse)

    malformed_coordinate = copy.deepcopy(manifest)
    cast(list[list[list[int]]], malformed_coordinate["action6_forward"])[0][0] = [0]
    invalid_maps.append(malformed_coordinate)

    extra_mapping = copy.deepcopy(manifest)
    cast(list[object], extra_mapping["action6_forward"]).append([[7, 9], [7, 9]])
    invalid_maps.append(extra_mapping)

    wrong_simple = copy.deepcopy(manifest)
    wrong_simple["simple_forward"] = [["ACTION3", "ACTION2"]]
    invalid_maps.append(wrong_simple)

    stale_digest = copy.deepcopy(manifest)
    stale_digest["content_sha256"] = "0" * 64
    invalid_maps.append(stale_digest)

    for invalid in invalid_maps:
        with pytest.raises(reference.ActionMapError):
            reference.validate_manifest_action_map(invalid, expected)


@pytest.mark.parametrize("shape", [(0, 1), (1, 0), (65, 1), (1, 65), (True, 1)])
def test_action_map_rejects_source_shapes_outside_finite_grid_domain(
    shape: tuple[int, int],
) -> None:
    with pytest.raises(reference.ActionMapError, match="source shape"):
        reference.reconstruct_action_map(
            _translation_contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME),
            shape,
        )


def test_global_defect_routes_are_exact_and_preserve_candidate_size() -> None:
    with pytest.raises(audit.V6GlobalFallbackRequired) as inventory_error:
        audit._bind_registered_row_inventory([], [])
    assert inventory_error.value.stage == "scientific_record_inventory_invalid"
    assert inventory_error.value.candidate_payload_size_bytes is None

    with pytest.raises(audit.V6GlobalFallbackRequired) as grid_error:
        audit._validate_grid_table(
            [],
            {"schema_version": "wrong", "blobs": []},
        )
    assert grid_error.value.stage == "grid_evidence_table_invalid"
    assert grid_error.value.candidate_payload_size_bytes is None

    missing_reference = {
        "pipeline": {
            "planning": {
                "rows": [
                    {
                        "predictions": [
                            {
                                "grid_bytes_sha256": "0" * 64,
                                "grid_shape": [1, 1],
                            }
                        ]
                    }
                ]
            }
        }
    }
    with pytest.raises(audit.V6GlobalFallbackRequired) as occurrence_error:
        audit._validate_grid_table(
            [missing_reference],
            reference.empty_grid_evidence_table(),
        )
    assert occurrence_error.value.stage == "grid_evidence_table_invalid"

    payload_error = audit.V6GlobalFallbackRequired(
        "payload_size_limit_exceeded",
        candidate_payload_size_bytes=reference.PAYLOAD_CAP_BYTES + 1,
    )
    assert payload_error.stage == "payload_size_limit_exceeded"
    assert payload_error.candidate_payload_size_bytes == 67_108_865


def test_full_manifest_map_defect_routes_to_global_fallback_before_evaluation() -> None:
    contract = _translation_contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    expected = reference.reconstruct_action_map(contract, (8, 10))
    transform: dict[str, Any] = {
        **contract.core_json(),
        "action_map": expected.as_json(),
    }
    prepared_contract, prepared_map, prepared_json = audit._prepare_transform(
        transform,
        source_shape=(8, 10),
    )
    assert prepared_contract == contract
    assert prepared_map == expected
    assert prepared_json == contract.as_json()

    invalid = copy.deepcopy(transform)
    cast(list[object], cast(dict[str, Any], invalid["action_map"])["action6_forward"]).pop()
    with pytest.raises(audit.V6GlobalFallbackRequired) as error:
        audit._prepare_transform(invalid, source_shape=(8, 10))
    assert error.value.stage == "transform_action_map_invalid"
    assert error.value.candidate_payload_size_bytes is None


def test_failed_pipeline_scene_accumulates_atomically_without_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accumulator, registration_rows, scenes = _synthetic_open_inventory()
    index = audit._accumulator_index(accumulator)
    completed_indices: set[int] = set()
    before = [reference.canonical_json_bytes(row) for row in accumulator]
    scene = scenes[("homologue", 0)]
    counters = audit.AuditCounterState()
    calls = 0

    def fail_without_worker_start(*_args: object, **_kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        counters.mark_scientific_exposure_started()
        raise RuntimeError("injected worker-free pipeline failure")

    monkeypatch.setattr(
        audit._v5,
        "evaluate_compiler_planner_snapshot",
        fail_without_worker_start,
    )
    grid_registry = reference.GridEvidenceRegistry()
    records = audit.evaluate_scene_record(
        scene,
        config=load_config(v5_audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=counters,
        order_transform_maps=tuple(
            cast(Mapping[str, Any], row) for row in build_order_transform_maps()
        ),
        require_linux_memory=False,
        deadline=time.monotonic() + 60.0,
        grid_registry=grid_registry,
    )

    assert calls == 4
    assert len(records) == 10
    assert len([row for row in records if row["kind"] == "base_scene"]) == 1
    assert len([row for row in records if row["kind"] == "visual_transform"]) == 4
    assert len([row for row in records if row["kind"] == "order_transform"]) == 5
    assert grid_registry.as_json() == reference.empty_grid_evidence_table()
    assert counters.snapshot()["total_worker_starts"] == 0

    failures = audit._accumulate_completed_records(
        accumulator,
        records,
        index=index,
        completed_indices=completed_indices,
        grid_evidence=grid_registry.as_json(),
    )

    expected_indices = {
        index[cast(audit.ScientificRecordAddress, v5_audit._scientific_record_address(row))]
        for row in records
    }
    assert failures == ()
    assert completed_indices == expected_indices
    assert len(completed_indices) == 10
    assert all(
        reference.canonical_json_bytes(accumulator[row_index]) == before[row_index]
        for row_index in range(140)
        if row_index not in completed_indices
    )
    revalidated = audit.validate_and_rederive_scientific_records(
        accumulator,
        registration_rows,
        grid_evidence=grid_registry.as_json(),
    )
    assert revalidated == accumulator
    visual_rows = [
        row
        for row in accumulator
        if row["kind"] == "visual_transform"
        and row["family"] == "homologue"
        and row["family_index"] == 0
    ]
    assert [cast(dict[str, Any], row["comparison"])["status"] for row in visual_rows] == [
        "pipeline_error",
        "pipeline_error",
        "pipeline_error",
        "pipeline_error",
    ]


@pytest.mark.skipif(sys.platform != "linux", reason="canonical real-worker gate is Linux-only")
def test_linux_three_family_completed_batch_matrix() -> None:
    accumulator, registration_rows, scenes = _synthetic_open_inventory()
    index = audit._accumulator_index(accumulator)
    completed_indices: set[int] = set()
    counters = audit.AuditCounterState()
    grid_registry = reference.GridEvidenceRegistry()
    config = load_config(v5_audit.AUDIT_CONFIG_RELATIVE_PATH)
    order_maps = tuple(cast(Mapping[str, Any], row) for row in build_order_transform_maps())

    completed_scene_records: list[dict[str, Any]] = []
    for family in v5_audit.SEALED_SCENE_FAMILIES:
        before_snapshot_count = counters.snapshot()["completed_planning_snapshots"]
        before_completed = set(completed_indices)
        before_rows = [reference.canonical_json_bytes(row) for row in accumulator]
        counters.increment("registered_scenes_read")
        records = audit.evaluate_scene_record(
            scenes[(family, 0)],
            config=config,
            counters=counters,
            order_transform_maps=order_maps,
            require_linux_memory=True,
            deadline=time.monotonic() + 300.0,
            grid_registry=grid_registry,
        )
        assert len(records) == 10
        assert counters.snapshot()["completed_planning_snapshots"] - before_snapshot_count == 5

        failures = audit._accumulate_completed_records(
            accumulator,
            records,
            index=index,
            completed_indices=completed_indices,
            grid_evidence=grid_registry.as_json(),
        )
        new_indices = completed_indices - before_completed
        assert failures == ()
        assert len(new_indices) == 10
        assert all(
            reference.canonical_json_bytes(accumulator[row_index]) == before_rows[row_index]
            for row_index in range(140)
            if row_index not in new_indices
        )
        assert (
            audit.validate_and_rederive_scientific_records(
                accumulator,
                registration_rows,
                grid_evidence=grid_registry.as_json(),
            )
            == accumulator
        )
        completed_scene_records.extend(accumulator[row_index] for row_index in sorted(new_indices))

    controls = tuple(
        {"kind": "control", **record}
        for record in v5_audit.evaluate_preregistered_controls(counters)
    )
    assert len(controls) == 20
    assert (
        audit._accumulate_completed_records(
            accumulator,
            controls,
            index=index,
            completed_indices=completed_indices,
            grid_evidence=grid_registry.as_json(),
        )
        == ()
    )
    assert len(completed_indices) == 50
    assert (
        audit.validate_and_rederive_scientific_records(
            accumulator,
            registration_rows,
            grid_evidence=grid_registry.as_json(),
        )
        == accumulator
    )

    visual_rows = [row for row in completed_scene_records if row["kind"] == "visual_transform"]
    assert len(visual_rows) == 12
    failing_visuals = [
        {
            "family": row["family"],
            "transform_name": row["transform_name"],
            "comparison": row["comparison"],
        }
        for row in visual_rows
        if cast(Mapping[str, Any], row["comparison"])["status"] != "evaluated"
        or cast(Mapping[str, Any], row["comparison"])["passes"] is not True
    ]
    if failing_visuals:
        print(reference.canonical_json_bytes(cast(reference.JsonValue, failing_visuals)).decode())
    assert not failing_visuals, failing_visuals
    assert all(
        cast(Mapping[str, Any], row["comparison"])["overflow_nonbackground_count"] == 0
        for row in visual_rows
        if "translation" in cast(str, row["transform_name"])
    )
    assert all("failure" not in row for row in (*completed_scene_records, *controls))

    expected_counters = {
        "candidate_builder_calls": 12,
        "compiled_programs": 60,
        "compiler_calls": 15,
        "completed_planning_snapshots": 15,
        "controller_calls": 24,
        "controller_snapshot_replays": 24,
        "environment_actions": 0,
        "generated_tokens": 0,
        "gpu_operations": 0,
        "grounding_evaluations": 60,
        "hypothesis_pool_constructions": 15,
        "lockbox_bytes_read": 0,
        "lockbox_path_operations": 0,
        "model_calls": 0,
        "network_calls": 0,
        "persistent_worker_starts": 60,
        "planner_calls": 15,
        "pure_selector_calls": 73,
        "pure_selector_control_calls": 19,
        "pure_selector_scene_order_calls": 54,
        "registered_scenes_read": 3,
        "reward_observations": 0,
        "rhae_observations": 0,
        "total_worker_starts": 120,
        "transient_worker_starts": 60,
        "v4_counterfactual_calls": 3,
    }
    assert counters.snapshot() == expected_counters


@pytest.mark.parametrize(
    ("name", "valid_cell", "destination", "overflow_cell"),
    [
        (
            reference.TRANSLATION_PLUS_TRANSFORM_NAME,
            (4, 4),
            (7, 9),
            (5, 4),
        ),
        (
            reference.TRANSLATION_MINUS_TRANSFORM_NAME,
            (3, 5),
            (0, 0),
            (2, 5),
        ),
    ],
)
def test_translation_exact_boundaries_padding_and_overflow(
    name: str,
    valid_cell: tuple[int, int],
    destination: tuple[int, int],
    overflow_cell: tuple[int, int],
) -> None:
    contract = _translation_contract(name)
    row_delta, column_delta = reference.TRANSLATION_DELTAS[name]
    base = _filled_prediction(8, 10, cells={valid_cell: 9})
    transformed = _translated_prediction(
        base,
        row_delta=row_delta,
        column_delta=column_delta,
        background=0,
    )

    passing = reference.compare_prediction_pair(base, transformed, contract)
    assert passing.passes is True
    assert passing.reasons == ()
    assert passing.overflow_nonbackground_count == 0
    assert transformed.next_grid[destination] == 9

    overflowing = _filled_prediction(8, 10, cells={overflow_cell: 9})
    empty = _filled_prediction(8, 10)
    failed = reference.compare_prediction_pair(overflowing, empty, contract)
    assert failed.passes is False
    assert failed.overflow_nonbackground_count == 1
    assert failed.reasons == (
        "translation_prediction_overflow",
        "mapped_prediction_grid_mismatch",
    )

    wrapped = np.zeros((8, 10), dtype=np.int16)
    wrapped[
        (overflow_cell[0] + row_delta) % 8,
        (overflow_cell[1] + column_delta) % 10,
    ] = 9
    wrapped_result = reference.compare_prediction_pair(overflowing, _prediction(wrapped), contract)
    assert "translation_prediction_overflow" in wrapped_result.reasons
    assert "mapped_prediction_grid_mismatch" in wrapped_result.reasons


@pytest.mark.parametrize(
    "name",
    [
        reference.TRANSLATION_PLUS_TRANSFORM_NAME,
        reference.TRANSLATION_MINUS_TRANSFORM_NAME,
    ],
)
def test_translation_background_only_null_shape_state_and_delta_cases(name: str) -> None:
    contract = _translation_contract(name, background=3)
    background = _filled_prediction(6, 7, background=3)
    assert reference.compare_prediction_pair(background, background, contract).passes

    null_result = reference.compare_prediction_pair(None, background, contract)
    assert null_result.reasons == ("invalid_root_prediction",)
    assert null_result.overflow_nonbackground_count == 0

    shape_mismatch = reference.compare_prediction_pair(
        background,
        _filled_prediction(6, 6, background=3),
        contract,
    )
    assert shape_mismatch.reasons == ("transformed_prediction_shape_mismatch",)

    metadata_mismatch = reference.compare_prediction_pair(
        background,
        _filled_prediction(
            6,
            7,
            background=3,
            state=GameState.WIN,
            level_delta=1,
        ),
        contract,
    )
    assert metadata_mismatch.reasons == (
        "mapped_prediction_state_mismatch",
        "mapped_prediction_level_delta_mismatch",
    )


def test_palette_reference_covers_domain_boundaries_shape_and_metadata() -> None:
    palette = list(reversed(range(16)))
    contract = reference.make_transform_contract(
        reference.PALETTE_TRANSFORM_NAME,
        background_label=palette[0],
        parameters={"forward_palette": palette},
    )
    base = _prediction([[0, 15], [1, 14]])
    transformed = _prediction([[15, 0], [14, 1]])
    assert reference.compare_prediction_pair(base, transformed, contract).passes

    for invalid_label in (-1, 16):
        result = reference.compare_prediction_pair(
            _prediction([[invalid_label]]),
            _prediction([[0]]),
            contract,
        )
        assert result.reasons == ("prediction_label_outside_palette_domain",)

    mismatch = reference.compare_prediction_pair(base, _prediction([[15, 0]]), contract)
    assert mismatch.reasons == ("transformed_prediction_shape_mismatch",)

    wrong_grid = reference.compare_prediction_pair(base, base, contract)
    assert wrong_grid.reasons == ("mapped_prediction_grid_mismatch",)


@pytest.mark.parametrize(("rows", "columns"), [(31, 32), (32, 32)])
def test_scale_reference_passes_immediately_below_and_at_domain_boundary(
    rows: int, columns: int
) -> None:
    contract = reference.make_transform_contract(
        reference.SCALE_TRANSFORM_NAME,
        background_label=0,
        parameters={
            "factor": 2,
            "action6_destination_cell": "top_left_of_scaled_2x2_block",
        },
    )
    base_grid = np.zeros((rows, columns), dtype=np.int16)
    base_grid[-1, -1] = 7
    base = _prediction(base_grid)
    transformed = _prediction(np.repeat(np.repeat(base_grid, 2, axis=0), 2, axis=1))
    assert reference.compare_prediction_pair(base, transformed, contract).passes


def test_scale_reference_fails_above_domain_and_on_shape_mismatch() -> None:
    contract = reference.make_transform_contract(
        reference.SCALE_TRANSFORM_NAME,
        background_label=0,
        parameters={
            "factor": 2,
            "action6_destination_cell": "top_left_of_scaled_2x2_block",
        },
    )
    above = reference.compare_prediction_pair(
        _filled_prediction(33, 32),
        _filled_prediction(64, 64),
        contract,
    )
    assert above.reasons == (
        "scale_output_shape_outside_prediction_domain",
        "transformed_prediction_shape_mismatch",
    )

    wrong_shape = reference.compare_prediction_pair(
        _filled_prediction(2, 2),
        _filled_prediction(3, 4),
        contract,
    )
    assert wrong_shape.reasons == ("transformed_prediction_shape_mismatch",)


def test_prediction_pair_multi_failure_reasons_use_exact_precedence() -> None:
    contract = reference.make_transform_contract(
        reference.PALETTE_TRANSFORM_NAME,
        background_label=0,
        parameters={"forward_palette": list(range(16))},
    )
    result = reference.compare_prediction_pair(
        _prediction([[-1, 0]], state=GameState.NOT_FINISHED, level_delta=0),
        _prediction([[16], [0]], state=GameState.GAME_OVER, level_delta=1),
        contract,
    )
    assert result.reasons == (
        "prediction_label_outside_palette_domain",
        "transformed_prediction_shape_mismatch",
        "mapped_prediction_state_mismatch",
        "mapped_prediction_level_delta_mismatch",
    )


def test_comparison_core_and_final_status_schemas_are_exact() -> None:
    positive = reference.make_comparison_core(
        mapped_action_count=3,
        unmapped_action_count=0,
        prediction_pair_count=12,
        overflow_nonbackground_count=0,
        reasons=(),
    )
    negative = reference.make_comparison_core(
        mapped_action_count=2,
        unmapped_action_count=1,
        prediction_pair_count=8,
        overflow_nonbackground_count=3,
        reasons=(
            "mapped_prediction_grid_mismatch",
            "required_action_mapping_missing",
            "translation_prediction_overflow",
            "mapped_prediction_grid_mismatch",
        ),
    )
    assert set(positive) == {
        "mapped_action_count",
        "unmapped_action_count",
        "prediction_pair_count",
        "overflow_nonbackground_count",
        "reasons",
        "passes",
    }
    assert positive["passes"] is True
    assert negative["reasons"] == [
        "required_action_mapping_missing",
        "translation_prediction_overflow",
        "mapped_prediction_grid_mismatch",
    ]
    assert negative["passes"] is False
    assert reference.validate_comparison_core(positive) == positive
    assert reference.validate_comparison_core(negative) == negative

    evaluated = reference.finalize_evaluated_comparison(negative, negative)
    assert set(evaluated) == {
        "status",
        "semantics_id",
        "mapped_action_count",
        "unmapped_action_count",
        "prediction_pair_count",
        "overflow_nonbackground_count",
        "reasons",
        "passes",
        "parity",
    }
    assert evaluated == {
        "status": "evaluated",
        "semantics_id": reference.FINITE_GRID_SEMANTICS_ID,
        **negative,
        "parity": None,
    }

    pipeline = reference.pipeline_error_comparison("visual_pipeline_failed")
    derivation = reference.derivation_error_comparison("transform_contract_invalid")
    assert pipeline["status"] == "pipeline_error"
    assert pipeline["reasons"] == ["visual_pipeline_failed"]
    assert derivation["status"] == "authoritative_derivation_error"
    assert derivation["reasons"] == ["transform_contract_invalid"]
    for terminal in (pipeline, derivation):
        assert terminal["mapped_action_count"] == 0
        assert terminal["unmapped_action_count"] == 0
        assert terminal["prediction_pair_count"] == 0
        assert terminal["overflow_nonbackground_count"] == 0
        assert terminal["passes"] is False
        assert terminal["parity"] is None


def test_comparison_core_rejects_noncanonical_and_malformed_claims() -> None:
    valid = reference.make_comparison_core(
        mapped_action_count=1,
        unmapped_action_count=0,
        prediction_pair_count=4,
        overflow_nonbackground_count=0,
        reasons=("mapped_prediction_grid_mismatch",),
    )
    invalid: list[object] = [None, [], {**valid, "unexpected": 1}]

    missing = copy.deepcopy(valid)
    missing.pop("passes")
    invalid.append(missing)

    negative_count = copy.deepcopy(valid)
    negative_count["mapped_action_count"] = -1
    invalid.append(negative_count)

    boolean_count = copy.deepcopy(valid)
    boolean_count["prediction_pair_count"] = True
    invalid.append(boolean_count)

    wrong_passes = copy.deepcopy(valid)
    wrong_passes["passes"] = True
    invalid.append(wrong_passes)

    duplicate_reason = copy.deepcopy(valid)
    duplicate_reason["reasons"] = [
        "mapped_prediction_grid_mismatch",
        "mapped_prediction_grid_mismatch",
    ]
    invalid.append(duplicate_reason)

    out_of_order = copy.deepcopy(valid)
    out_of_order["reasons"] = [
        "mapped_prediction_grid_mismatch",
        "required_action_mapping_missing",
    ]
    invalid.append(out_of_order)

    non_evaluated_reason = copy.deepcopy(valid)
    non_evaluated_reason["reasons"] = ["transform_contract_invalid"]
    invalid.append(non_evaluated_reason)

    for claim in invalid:
        with pytest.raises(reference.ComparisonSchemaError):
            reference.validate_comparison_core(claim)

    for kwargs in (
        {"mapped_action_count": -1},
        {"unmapped_action_count": True},
        {"reasons": ("visual_pipeline_failed",)},
    ):
        arguments: dict[str, Any] = {
            "mapped_action_count": 1,
            "unmapped_action_count": 0,
            "prediction_pair_count": 4,
            "overflow_nonbackground_count": 0,
            "reasons": (),
        }
        arguments.update(kwargs)
        with pytest.raises(reference.ComparisonSchemaError):
            reference.make_comparison_core(**arguments)

    with pytest.raises(reference.ComparisonSchemaError):
        reference.pipeline_error_comparison("transform_contract_invalid")
    with pytest.raises(reference.ComparisonSchemaError):
        reference.derivation_error_comparison("mapped_prediction_grid_mismatch")


def test_comparison_parity_mismatch_preserves_both_exact_cores_and_hashes() -> None:
    authoritative = reference.make_comparison_core(
        mapped_action_count=3,
        unmapped_action_count=0,
        prediction_pair_count=12,
        overflow_nonbackground_count=0,
        reasons=(),
    )
    claimed = reference.make_comparison_core(
        mapped_action_count=2,
        unmapped_action_count=1,
        prediction_pair_count=8,
        overflow_nonbackground_count=1,
        reasons=(
            "required_action_mapping_missing",
            "translation_prediction_overflow",
        ),
    )

    result = reference.finalize_evaluated_comparison(authoritative, claimed)

    assert result["status"] == "authoritative_derivation_error"
    assert result["semantics_id"] == reference.FINITE_GRID_SEMANTICS_ID
    assert result["mapped_action_count"] == 0
    assert result["unmapped_action_count"] == 0
    assert result["prediction_pair_count"] == 0
    assert result["overflow_nonbackground_count"] == 0
    assert result["reasons"] == ["comparison_parity_mismatch"]
    assert result["passes"] is False
    parity = cast(dict[str, Any], result["parity"])
    assert set(parity) == {
        "claimed",
        "authoritative",
        "claimed_sha256",
        "authoritative_sha256",
    }
    assert parity["claimed"] == claimed
    assert parity["authoritative"] == authoritative
    assert parity["claimed_sha256"] == reference.canonical_sha256(claimed)
    assert parity["authoritative_sha256"] == reference.canonical_sha256(authoritative)


def test_audit_recovers_only_exact_evaluated_or_parity_preserved_claims() -> None:
    authoritative = reference.make_comparison_core(
        mapped_action_count=3,
        unmapped_action_count=0,
        prediction_pair_count=12,
        overflow_nonbackground_count=0,
        reasons=(),
    )
    claimed = reference.make_comparison_core(
        mapped_action_count=2,
        unmapped_action_count=1,
        prediction_pair_count=8,
        overflow_nonbackground_count=1,
        reasons=("required_action_mapping_missing",),
    )
    evaluated = reference.finalize_evaluated_comparison(claimed, claimed)
    parity = reference.finalize_evaluated_comparison(authoritative, claimed)

    assert audit._claimed_comparison_core(evaluated) == claimed
    assert audit._claimed_comparison_core(parity) == claimed

    invalid_values: list[object] = [None, claimed, {**evaluated, "unexpected": 1}]
    corrupt_parity = copy.deepcopy(parity)
    cast(dict[str, Any], corrupt_parity["parity"])["claimed_sha256"] = "0" * 64
    invalid_values.append(corrupt_parity)
    wrong_semantics = copy.deepcopy(evaluated)
    wrong_semantics["semantics_id"] = "wrong"
    invalid_values.append(wrong_semantics)
    for invalid in invalid_values:
        with pytest.raises(reference.ComparisonSchemaError):
            audit._claimed_comparison_core(invalid)


def test_reference_module_is_platform_pure_except_registered_little_endian_guard() -> None:
    assert sys.byteorder == "little"
    payload: reference.JsonValue = {"b": [2, 1], "a": True}
    assert reference.canonical_json_bytes(payload) == b'{"a":true,"b":[2,1]}'
    assert (
        reference.canonical_sha256(payload)
        == hashlib.sha256(reference.canonical_json_bytes(payload)).hexdigest()
    )
