from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest

import arc3_voi.action_qbc_audit as v5_audit
import arc3_voi.action_qbc_v7_audit as audit
import arc3_voi.action_qbc_v7_reference as reference
from arc3_voi.action_qbc_policy import select_action_conditional_qbc
from arc3_voi.planner import PlanningSnapshot
from arc3_voi.types import Action, ActionKind, GameState, History, Prediction

A1 = Action(ActionKind.ACTION1)
A2 = Action(ActionKind.ACTION2)
A3 = Action(ActionKind.ACTION3)
A4 = Action(ActionKind.ACTION4)


def _prediction(
    value: int | Sequence[Sequence[int]] | np.ndarray,
    *,
    state: GameState = GameState.NOT_FINISHED,
    level_delta: int = 0,
) -> Prediction:
    grid = (
        np.asarray([[value]], dtype=np.int16)
        if isinstance(value, int)
        else np.asarray(value, dtype=np.int16)
    )
    return Prediction(grid, state, level_delta, {})


def _snapshot(
    actions: Sequence[Action],
    weights: Sequence[float],
    predictions: Mapping[Action, Sequence[Prediction | None]],
    costs: Mapping[Action, Sequence[float]],
    *,
    hypothesis_ids: Sequence[str] | None = None,
) -> PlanningSnapshot:
    identifiers = (
        tuple(f"h{index}" for index in range(len(weights)))
        if hypothesis_ids is None
        else tuple(hypothesis_ids)
    )
    return PlanningSnapshot(
        actions=tuple(actions),
        hypothesis_ids=identifiers,
        weights=tuple(weights),
        predictions={action: tuple(predictions[action]) for action in actions},
        costs={action: tuple(costs[action]) for action in actions},
    )


def _split_snapshot(
    *,
    actions: Sequence[Action] = (A1, A2, A3),
    probe_actions: Sequence[Action] = (A3,),
    weights: tuple[float, float] = (0.5, 0.5),
    cross_cost: float = 2.0,
    probe_cost: float = 4.0,
) -> PlanningSnapshot:
    first = _prediction(1)
    second = _prediction(2)
    predictions: dict[Action, tuple[Prediction, Prediction]] = {}
    costs: dict[Action, tuple[float, float]] = {}
    for action in actions:
        if action == actions[0]:
            predictions[action] = (first, first)
            costs[action] = (0.0, cross_cost)
        elif action == actions[1]:
            predictions[action] = (second, second)
            costs[action] = (cross_cost, 0.0)
        elif action in probe_actions:
            predictions[action] = (first, second)
            costs[action] = (probe_cost, probe_cost)
        else:  # pragma: no cover - fixture misuse is intentionally loud
            raise AssertionError(f"unclassified fixture action: {action}")
    return _snapshot(actions, weights, predictions, costs)


def _four_role_snapshot(
    *,
    hypothesis_ids: Sequence[str] = ("h0", "h1", "h2", "h3"),
    weights: Sequence[float] = (0.1, 0.2, 0.3, 0.4),
    costs: Sequence[float] = (1.0, 2.0, 3.0, 4.0),
) -> PlanningSnapshot:
    action = Action(ActionKind.ACTION6, 2, 3)
    return _snapshot(
        (action,),
        weights,
        {action: tuple(_prediction(index + 1) for index in range(4))},
        {action: tuple(costs)},
        hypothesis_ids=hypothesis_ids,
    )


def _contract(
    transform_name: str,
    *,
    source_background: int = 0,
) -> reference.TransformContract:
    if transform_name == reference.PALETTE_TRANSFORM_NAME:
        palette = list(reversed(range(16)))
        destination_background = palette[source_background]
        parameters: dict[str, object] = {"forward_palette": palette}
    elif transform_name in reference.TRANSLATION_DELTAS:
        delta_row, delta_col = reference.TRANSLATION_DELTAS[transform_name]
        destination_background = source_background
        parameters = {"delta_row": delta_row, "delta_col": delta_col}
    elif transform_name == reference.SCALE_TRANSFORM_NAME:
        destination_background = source_background
        parameters = {"factor": 2}
    else:  # pragma: no cover - fixture misuse is intentionally loud
        raise AssertionError(transform_name)
    return reference.make_transform_contract(
        family="homologue",
        scene_index=0,
        transform_name=transform_name,
        source_background_label=source_background,
        destination_background_label=destination_background,
        parameters=parameters,
    )


def _pair(
    base: Prediction | None,
    transformed: Prediction | None,
    contract: reference.TransformContract,
) -> tuple[
    reference.PredictionPairRecord,
    reference.GridEvidenceRegistry,
    reference.ExteriorSupportRegistry,
]:
    action = Action(ActionKind.ACTION6, 7, 7)
    action_map = reference.reconstruct_action_map(contract, map_kind="actual")
    mapped_action = reference.map_action(action, action_map)
    grids = reference.GridEvidenceRegistry()
    support = reference.ExteriorSupportRegistry()
    result = reference.compare_prediction_pair(
        action=action,
        mapped_action=mapped_action,
        role=reference.ROLE_ORDER[0],
        base=base,
        transformed=transformed,
        contract=contract,
        grid_registry=grids,
        support_registry=support,
    )
    return result, grids, support


def _permuted_snapshot(
    snapshot: PlanningSnapshot,
    permutation: Sequence[int],
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=snapshot.actions,
        hypothesis_ids=tuple(snapshot.hypothesis_ids[index] for index in permutation),
        weights=tuple(snapshot.weights[index] for index in permutation),
        predictions={
            action: tuple(snapshot.predictions[action][index] for index in permutation)
            for action in snapshot.actions
        },
        costs={
            action: tuple(snapshot.costs[action][index] for index in permutation)
            for action in snapshot.actions
        },
    )


def _mapped_split_snapshots() -> tuple[
    PlanningSnapshot,
    PlanningSnapshot,
    reference.ReconstructedActionMap,
]:
    contract = _contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    action_map = reference.reconstruct_action_map(contract, map_kind="actual")
    left_actions = tuple(Action(ActionKind.ACTION6, index, index) for index in (1, 2, 3))
    right_actions = tuple(reference.map_action(action, action_map) for action in left_actions)
    left = _split_snapshot(actions=left_actions, probe_actions=(left_actions[2],))
    right = _snapshot(
        right_actions,
        left.weights,
        {
            right_action: left.predictions[left_action]
            for left_action, right_action in zip(left_actions, right_actions, strict=True)
        },
        {
            right_action: left.costs[left_action]
            for left_action, right_action in zip(left_actions, right_actions, strict=True)
        },
        hypothesis_ids=left.hypothesis_ids,
    )
    return left, right, action_map


def _pipeline_primitive(snapshot: PlanningSnapshot) -> audit.PipelinePrimitive:
    raw = select_action_conditional_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    fixed = reference.select_compound_action_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    role_by_hypothesis = dict(
        zip(snapshot.hypothesis_ids, reference.ROLE_ORDER, strict=True)
    )
    program_rows = tuple(
        {
            "hypothesis_id": hypothesis_id,
            "assigned_role": role_by_hypothesis[hypothesis_id],
            "selected": True,
            "eligible": True,
        }
        for hypothesis_id in snapshot.hypothesis_ids
    )
    source_manifest = tuple(
        {"role": role, "source_sha256": f"{index + 1:064x}"}
        for index, role in enumerate(reference.ROLE_ORDER)
    )
    worker_memory = {
        "hard_limit_enforced": True,
        "limit_kind": v5_audit.RLIMIT_DATA_HEADROOM_KIND,
        "allocation_headroom_bytes": 268_435_456,
        "diagnostic": None,
    }
    result = v5_audit.PipelineAuditResult(
        history=History.empty(),
        actions=snapshot.actions,
        cached_points=(),
        source_roles=reference.ROLE_ORDER,
        source_manifest=source_manifest,
        program_rows=program_rows,
        persistent_worker_rows=tuple(dict(worker_memory) for _ in range(4)),
        snapshot=snapshot,
        selection=raw,
        controller_rows=(),
    )
    return audit.PipelinePrimitive(result, fixed)


def _palette_visual_primitives(
    *,
    weights: tuple[float, float, float, float] = (0.1, 0.2, 0.3, 0.4),
    transformed_weight_delta: float = 0.0,
    transformed_cost_delta: float = 0.0,
) -> audit.VisualPrimitive:
    contract = _contract(reference.PALETTE_TRANSFORM_NAME)
    action = A3
    base_predictions: list[Prediction] = []
    transformed_predictions: list[Prediction] = []
    for role_index in range(4):
        grid = np.zeros((32, 32), dtype=np.int16)
        grid[role_index, role_index] = role_index + 1
        base_predictions.append(_prediction(grid))
        transformed_predictions.append(
            _prediction(reference.palette_transform_grid(grid, contract))
        )
    base = _snapshot(
        (action,),
        weights,
        {action: tuple(base_predictions)},
        {action: (1.0, 2.0, 3.0, 4.0)},
    )
    transformed = _snapshot(
        (action,),
        (weights[0] + transformed_weight_delta, *weights[1:]),
        {action: tuple(transformed_predictions)},
        {
            action: (
                1.0 + transformed_cost_delta,
                2.0,
                3.0,
                4.0,
            )
        },
        hypothesis_ids=base.hypothesis_ids,
    )
    return audit.VisualPrimitive(
        base=_pipeline_primitive(base),
        transformed=_pipeline_primitive(transformed),
        contract=contract,
        actual_action_map=reference.reconstruct_action_map(contract, map_kind="actual"),
        isolated_action_map=reference.reconstruct_action_map(
            contract, map_kind="isolated"
        ),
        action_relabel=audit.TransportPrimitive(
            None, None, None, "isolated_action_map_not_bijective"
        ),
        signature_pushforward=audit.TransportPrimitive(
            None, None, None, "isolated_signature_transform_not_injective"
        ),
        raw_transform={},
    )


def _fallback_registration() -> dict[str, Any]:
    kinds = (
        ("base_scene", 12),
        ("visual_transform", 48),
        ("order_transform", 60),
        ("control", 20),
    )
    rows: list[dict[str, Any]] = []
    for kind, count in kinds:
        for _ in range(count):
            index = len(rows)
            rows.append(
                {
                    "row_index": index,
                    "row_id": f"{kind}:{index}",
                    "kind": kind,
                    "registered_placeholder": True,
                }
            )
    return {"row_inventory": {"count": 140, "rows": rows}}


def _stub_payload_prefix(
    _registration: Mapping[str, Any],
    _repository_root: Any,
    counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": audit.SCIENTIFIC_SCHEMA_VERSION,
        "treatment_id": audit.TREATMENT_ID,
        "diagnostic_system_id": audit.DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": audit.COMPARISON_SEMANTICS_ID,
        "runtime_id": None,
        "preregistration_identity": {},
        "v6_negative_identity": {},
        "registration_identity": {},
        "execution_identity": {},
        "resource_counters": dict(counters),
    }


def _v6_comparison(
    *,
    passes: bool,
    reasons: Sequence[str] = (),
    overflow: int = 0,
) -> dict[str, Any]:
    return {
        "status": "evaluated",
        "semantics_id": "action-qbc-v6-padded-finite-grid-v1",
        "mapped_action_count": 12,
        "unmapped_action_count": 0,
        "prediction_pair_count": 48,
        "overflow_nonbackground_count": overflow,
        "reasons": list(reasons),
        "passes": passes,
        "parity": None,
    }


def _frozen_miniature_v6_rows() -> list[dict[str, Any]]:
    failure_specs: dict[tuple[str, str], tuple[int, tuple[str, ...]]] = {
        ("homologue", reference.TRANSLATION_PLUS_TRANSFORM_NAME): (
            54,
            ("translation_prediction_overflow", "mapped_prediction_grid_mismatch"),
        ),
        ("homologue", reference.TRANSLATION_MINUS_TRANSFORM_NAME): (
            0,
            (
                "mapped_prediction_grid_mismatch",
                "selector_disposition_or_rank_mismatch",
                "mapped_myopic_utility_set_mismatch",
                "mapped_cross_level_utility_set_mismatch",
            ),
        ),
        ("homologue", reference.SCALE_TRANSFORM_NAME): (
            0,
            (
                "selector_disposition_or_rank_mismatch",
                "mapped_myopic_utility_set_mismatch",
                "mapped_cross_level_utility_set_mismatch",
            ),
        ),
        ("containment", reference.TRANSLATION_PLUS_TRANSFORM_NAME): (
            29,
            (
                "translation_prediction_overflow",
                "mapped_prediction_grid_mismatch",
                "selector_disposition_or_rank_mismatch",
            ),
        ),
        ("containment", reference.TRANSLATION_MINUS_TRANSFORM_NAME): (
            0,
            ("mapped_prediction_grid_mismatch",),
        ),
        ("containment", reference.SCALE_TRANSFORM_NAME): (
            0,
            (
                "selector_disposition_or_rank_mismatch",
                "mapped_myopic_utility_set_mismatch",
                "mapped_cross_level_utility_set_mismatch",
            ),
        ),
        ("reflection", reference.TRANSLATION_PLUS_TRANSFORM_NAME): (
            24,
            ("translation_prediction_overflow", "mapped_prediction_grid_mismatch"),
        ),
        ("reflection", reference.TRANSLATION_MINUS_TRANSFORM_NAME): (
            0,
            ("mapped_prediction_grid_mismatch",),
        ),
        ("reflection", reference.SCALE_TRANSFORM_NAME): (
            0,
            (
                "mapped_myopic_utility_set_mismatch",
                "mapped_cross_level_utility_set_mismatch",
            ),
        ),
    }
    rows: list[dict[str, Any]] = []
    for family in ("homologue", "containment", "reflection"):
        for transform_name in reference.VISUAL_TRANSFORM_NAMES:
            spec = failure_specs.get((family, transform_name))
            observed = (
                _v6_comparison(passes=True)
                if spec is None
                else _v6_comparison(passes=False, overflow=spec[0], reasons=spec[1])
            )
            details = {
                "applicable": True,
                "expected_comparison": copy.deepcopy(observed),
                "observed_comparison": observed,
                "expected_comparison_sha256": audit.canonical_sha256(observed),
                "observed_comparison_sha256": audit.canonical_sha256(observed),
                "comparison_reproduced": True,
                "expected_failure_vector_sha256": audit.V6_FAILURE_VECTOR_SHA256,
                "observed_failure_vector_sha256": None,
            }
            rows.append(
                {
                    "registered_row": {
                        "kind": "visual_transform",
                        "scene_index": 0,
                        "family": family,
                        "transform_name": transform_name,
                    },
                    "disposition": "completed",
                    "evidence": {"v6_reproduction": audit.layer(details)},
                }
            )
    return rows


def test_action_coordinate_conversion_and_exact_json_boundary() -> None:
    action = Action(ActionKind.ACTION6, row=7, col=11)
    encoded = {"kind": "ACTION6", "row": 7, "col": 11}

    assert action.to_official_args() == {"x": 11, "y": 7}
    assert reference.action_to_json(action) == encoded
    assert reference.action_from_json(encoded, shape=(32, 32)) == action
    assert audit.action_json(action) == encoded
    assert audit.action_from_json(encoded, shape=(32, 32)) == action
    assert reference.action_to_json(A3) == {"kind": "ACTION3", "row": None, "col": None}

    with pytest.raises(reference.ActionMapError):
        reference.action_from_json({"kind": "ACTION6", "row": 7, "col": 32}, shape=(32, 32))
    with pytest.raises(audit.V7AuditError):
        audit.action_from_json({"kind": "ACTION3", "row": 0, "col": None})


@pytest.mark.parametrize(
    ("name", "actual_total", "actual_count", "destination"),
    (
        (reference.PALETTE_TRANSFORM_NAME, True, 1_024, (7, 11)),
        (reference.TRANSLATION_PLUS_TRANSFORM_NAME, False, 783, (10, 16)),
        (reference.TRANSLATION_MINUS_TRANSFORM_NAME, False, 783, (4, 6)),
        (reference.SCALE_TRANSFORM_NAME, True, 1_024, (14, 22)),
    ),
)
def test_complete_and_partial_action_map_reconstruction(
    name: str,
    actual_total: bool,
    actual_count: int,
    destination: tuple[int, int],
) -> None:
    contract = _contract(name)
    actual = reference.reconstruct_action_map(contract, map_kind="actual")
    isolated = reference.reconstruct_action_map(contract, map_kind="isolated")
    source = Action(ActionKind.ACTION6, 7, 11)

    assert actual.total is actual_total
    assert len(actual.forward) == actual_count
    assert isolated.total
    assert len(isolated.forward) == 1_024
    assert reference.map_action(A3, actual) == A3
    assert reference.map_action(source, actual) == Action(
        ActionKind.ACTION6, destination[0], destination[1]
    )
    assert reference.validate_action_map(
        actual.as_json(), contract, map_kind="actual", expected_sha256=actual.sha256
    ) == actual

    tampered = copy.deepcopy(actual.as_json())
    assert isinstance(tampered["action6_forward"], list)
    tampered["action6_forward"].pop()
    with pytest.raises(reference.ActionMapError, match="differs from exact reconstruction"):
        reference.validate_action_map(tampered, contract, map_kind="actual")


def test_partial_action_map_rejects_required_unmapped_action() -> None:
    contract = _contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    action_map = reference.reconstruct_action_map(contract, map_kind="actual")
    unmapped = Action(ActionKind.ACTION6, 31, 31)

    with pytest.raises(reference.ActionMapError, match="absent from the partial map"):
        reference.map_action(unmapped, action_map)

    relation = reference.compare_frontiers(
        [Action(ActionKind.ACTION6, 0, 0), unmapped],
        [Action(ActionKind.ACTION6, 3, 5)],
        action_map,
    )
    assert not relation.passes
    assert relation.unmapped_base_actions == (unmapped,)
    assert relation.reasons == (
        "required_action_mapping_missing",
        "mapped_frontier_set_mismatch",
        "mapped_frontier_sequence_mismatch",
    )


def test_frontier_relation_separates_set_sequence_and_canonical_order() -> None:
    contract = _contract(reference.PALETTE_TRANSFORM_NAME)
    action_map = reference.reconstruct_action_map(contract, map_kind="actual")
    actions = [A3, Action(ActionKind.ACTION6, 0, 0), Action(ActionKind.ACTION6, 1, 1)]

    passing = reference.compare_frontiers(actions, actions, action_map)
    reordered = reference.compare_frontiers(actions, list(reversed(actions)), action_map)

    assert passing.passes
    assert passing.set_equal and passing.sequence_equal and passing.canonical_order_preserving
    assert reordered.set_equal
    assert not reordered.sequence_equal
    assert reordered.canonical_order_preserving
    assert reordered.reasons == ("mapped_frontier_sequence_mismatch",)


def test_frontier_relation_detects_noncanonical_bijective_action_relabeling() -> None:
    first = Action(ActionKind.ACTION6, 0, 0)
    second = Action(ActionKind.ACTION6, 0, 1)
    swapped = reference.ReconstructedActionMap(
        map_kind="isolated",
        transform_contract_sha256="0" * 64,
        source_shape=(1, 2),
        destination_shape=(1, 2),
        forward=MappingProxyType({(0, 0): (0, 1), (0, 1): (0, 0)}),
    )

    relation = reference.compare_frontiers(
        [first, second],
        [second, first],
        swapped,
    )

    assert relation.set_equal and relation.sequence_equal
    assert not relation.canonical_order_preserving
    assert relation.reasons == ("action_map_not_canonical_order_preserving",)


def test_role_pairing_uses_unique_roles_not_source_or_list_position() -> None:
    base = [
        {"role": role, "source_sha256": f"{index + 1:064x}"}
        for index, role in enumerate(reference.ROLE_ORDER)
    ]
    transformed = [
        {"role": role, "source_sha256": f"{index + 101:064x}"}
        for index, role in enumerate(reversed(reference.ROLE_ORDER))
    ]

    pairs = reference.pair_compiler_roles(list(reversed(base)), transformed)

    assert tuple(pair["role"] for pair in pairs) == reference.ROLE_ORDER
    assert pairs[0] == {
        "role": reference.ROLE_ORDER[0],
        "base_source_sha256": f"{1:064x}",
        "transformed_source_sha256": f"{104:064x}",
    }
    duplicate = [*base[:-1], dict(base[0])]
    with pytest.raises(reference.SnapshotSchemaError, match="missing/duplicate/unknown"):
        reference.pair_compiler_roles(duplicate, transformed)


def test_snapshot_digest_is_role_ordered_under_hypothesis_permutation() -> None:
    roles = dict(zip(("h0", "h1", "h2", "h3"), reference.ROLE_ORDER, strict=True))
    source_hashes = {role: f"{index + 9:064x}" for index, role in enumerate(reference.ROLE_ORDER)}
    snapshot = _four_role_snapshot()
    permutation = (3, 1, 0, 2)
    permuted = _permuted_snapshot(snapshot, permutation)

    left = reference.build_snapshot_digest_preimage(
        snapshot,
        hypothesis_roles=roles,
        source_sha256_by_role=source_hashes,
    )
    right = reference.build_snapshot_digest_preimage(
        permuted,
        hypothesis_roles=roles,
        source_sha256_by_role=source_hashes,
    )

    assert left == right
    assert reference.snapshot_digest(left) == reference.snapshot_digest(right)
    assert [row["role"] for row in left["normalized_weights"]] == list(reference.ROLE_ORDER)


def test_snapshot_digest_preserves_nonfinite_primitive_sentinels() -> None:
    roles = dict(zip(("h0", "h1", "h2", "h3"), reference.ROLE_ORDER, strict=True))
    source_hashes = {role: f"{index + 1:064x}" for index, role in enumerate(reference.ROLE_ORDER)}
    snapshot = _four_role_snapshot(
        weights=(math.nan, 0.2, 0.3, 0.5),
        costs=(math.inf, -math.inf, math.nan, 4.0),
    )

    preimage = reference.build_snapshot_digest_preimage(
        snapshot,
        hypothesis_roles=roles,
        source_sha256_by_role=source_hashes,
    )

    assert preimage["normalized_weights"][0]["value"] == "nan"
    assert [row["cost"] for row in preimage["rolewise_costs"]] == [
        "+inf",
        "-inf",
        "nan",
        4.0,
    ]
    assert reference.validate_snapshot_digest_preimage(preimage) == preimage


def test_gibbs_weights_and_costs_have_distinct_exact_and_tolerance_relations() -> None:
    epsilon = 5e-13
    assert reference.tolerance_comparison(0.25, 0.25 + epsilon)[0]
    assert not reference.binary64_equal(0.25, 0.25 + epsilon)
    assert reference.compare_numeric(3.0, 3.0 + epsilon, "tolerance")
    assert not reference.compare_numeric(3.0, 3.0 + epsilon, "exact_binary64")
    assert not reference.binary64_equal(0.0, -0.0)


def test_palette_and_scale_grid_transforms_are_exact() -> None:
    palette_contract = _contract(reference.PALETTE_TRANSFORM_NAME)
    source = np.asarray([[0, 1], [14, 15]], dtype=np.int16)
    transformed = reference.palette_transform_grid(source, palette_contract)
    assert transformed.tolist() == [[15, 14], [1, 0]]
    with pytest.raises(reference.PredictionPairError, match="outside palette domain"):
        reference.palette_transform_grid(np.asarray([[16]], dtype=np.int16), palette_contract)

    scale_contract = _contract(reference.SCALE_TRANSFORM_NAME)
    scaled = reference.scale_transform_grid(np.asarray([[1, 2], [3, 4]]), scale_contract)
    assert scaled.tolist() == [
        [1, 1, 2, 2],
        [1, 1, 2, 2],
        [3, 3, 4, 4],
        [3, 3, 4, 4],
    ]
    with pytest.raises(reference.PredictionPairError, match="outside Prediction domain"):
        reference.scale_transform_grid(np.zeros((33, 1), dtype=np.int16), scale_contract)


@pytest.mark.parametrize(
    ("transform_name", "source_cell", "world_cell", "exterior_count"),
    (
        (reference.TRANSLATION_PLUS_TRANSFORM_NAME, (0, 0), (3, 5), 0),
        (reference.TRANSLATION_PLUS_TRANSFORM_NAME, (31, 31), (34, 36), 1),
        (reference.TRANSLATION_MINUS_TRANSFORM_NAME, (31, 31), (28, 26), 0),
        (reference.TRANSLATION_MINUS_TRANSFORM_NAME, (0, 0), (-3, -5), 1),
    ),
)
def test_translation_augmented_plane_known_window_and_exterior_manifest(
    transform_name: str,
    source_cell: tuple[int, int],
    world_cell: tuple[int, int],
    exterior_count: int,
) -> None:
    contract = _contract(transform_name)
    source = np.zeros((32, 32), dtype=np.int16)
    source[source_cell] = 7

    augmented, origin = reference.translation_transform_grid(source, contract)
    known = reference.translation_known_viewport(
        augmented, origin=origin, viewport_shape=(32, 32)
    )
    support = reference.translation_exterior_support(
        augmented,
        origin=origin,
        viewport_shape=(32, 32),
        background_label=0,
    )

    if exterior_count:
        assert not np.any(known == 7)
        assert support == ((*world_cell, 7),)
    else:
        assert known[world_cell] == 7
        assert support == ()
    assert origin == (-3, -5)


def test_prediction_pair_palette_and_scale_fully_equivariant() -> None:
    base_grid = np.zeros((32, 32), dtype=np.int16)
    base_grid[4, 7] = 3
    for transform_name in (
        reference.PALETTE_TRANSFORM_NAME,
        reference.SCALE_TRANSFORM_NAME,
    ):
        contract = _contract(transform_name)
        transformed_grid = (
            reference.palette_transform_grid(base_grid, contract)
            if transform_name == reference.PALETTE_TRANSFORM_NAME
            else reference.scale_transform_grid(base_grid, contract)
        )
        pair, grids, support = _pair(
            _prediction(base_grid), _prediction(transformed_grid), contract
        )

        assert pair.passes
        assert pair.category == "fully_equivariant"
        assert pair.reasons == ()
        assert pair.record["observable_mismatch_cell_count"] == 0
        reference.validate_grid_evidence_table(
            grids.as_json(), expected_references=grids.references
        )
        reference.validate_expected_exterior_support_table(
            support.as_json(), expected_references=support.references
        )


def test_prediction_pair_boundary_consistent_censored_and_mixed() -> None:
    contract = _contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    base_grid = np.zeros((32, 32), dtype=np.int16)
    base_grid[31, 31] = 9
    transformed_grid = np.zeros((32, 32), dtype=np.int16)

    censored, grids, support = _pair(
        _prediction(base_grid), _prediction(transformed_grid), contract
    )
    mixed_grid = transformed_grid.copy()
    mixed_grid[0, 0] = 8
    mixed, _, _ = _pair(_prediction(base_grid), _prediction(mixed_grid), contract)

    assert censored.category == "boundary_consistent_censored"
    assert not censored.passes
    assert censored.record["expected_exterior_nonbackground_count"] == 1
    assert censored.record["observable_mismatch_cell_count"] == 0
    assert censored.reasons == ("expected_exterior_support_present",)
    assert censored.record["expected_origin_row"] == -3
    assert censored.record["expected_origin_col"] == -5
    reference.validate_grid_evidence_table(
        grids.as_json(), expected_references=grids.references
    )
    reference.validate_expected_exterior_support_table(
        support.as_json(), expected_references=support.references
    )

    assert mixed.category == "interior_or_metadata_mismatch"
    assert mixed.record["observable_mismatch_cell_count"] == 1
    assert mixed.record["expected_exterior_nonbackground_count"] == 1
    assert mixed.reasons == (
        "observable_prediction_grid_mismatch",
        "expected_exterior_support_present",
    )


def test_prediction_pair_zero_overflow_metadata_mismatch_and_invalid_cases() -> None:
    contract = _contract(reference.TRANSLATION_MINUS_TRANSFORM_NAME)
    base_grid = np.zeros((32, 32), dtype=np.int16)
    base_grid[31, 31] = 4
    augmented, origin = reference.translation_transform_grid(base_grid, contract)
    transformed = reference.translation_known_viewport(
        augmented, origin=origin, viewport_shape=(32, 32)
    )

    passing, _, _ = _pair(_prediction(base_grid), _prediction(transformed), contract)
    metadata, _, _ = _pair(
        _prediction(base_grid),
        _prediction(transformed, state=GameState.WIN, level_delta=1),
        contract,
    )
    invalid, _, _ = _pair(None, _prediction(transformed), contract)
    wrong_shape, _, _ = _pair(_prediction(base_grid), _prediction([[0]]), contract)

    assert passing.passes and passing.category == "fully_equivariant"
    assert passing.record["expected_exterior_nonbackground_count"] == 0
    assert metadata.category == "interior_or_metadata_mismatch"
    assert metadata.reasons == (
        "prediction_game_state_mismatch",
        "prediction_level_delta_mismatch",
    )
    assert invalid.category == "invalid_prediction"
    assert invalid.reasons == ("invalid_root_prediction",)
    assert wrong_shape.category == "invalid_prediction"
    assert wrong_shape.reasons == ("transformed_prediction_shape_mismatch",)
    assert wrong_shape.record["expected_prediction_ref"] is None
    assert wrong_shape.record["expected_origin_row"] is None


def test_grid_evidence_registry_shares_blobs_and_requires_exact_coverage() -> None:
    first = np.asarray([[1, 2], [3, 4]], dtype=np.int16)
    second = np.asarray([[5, 6]], dtype=np.int16)
    registry = reference.GridEvidenceRegistry()
    first_ref = registry.add_grid(first)
    assert registry.add_grid(first.copy()) == first_ref
    second_ref = registry.add_grid(second)
    assert len(registry.as_json()["blobs"]) == 2

    decoded = reference.validate_grid_evidence_table(
        registry.as_json(), expected_references=(first_ref, first_ref, second_ref, None)
    )
    assert set(decoded) == {first_ref, second_ref}
    assert np.array_equal(decoded[first_ref], first)

    with pytest.raises(reference.GridEvidenceTableError, match="reference set is not exact"):
        reference.validate_grid_evidence_table(
            registry.as_json(), expected_references=(first_ref,)
        )
    absent = reference.grid_evidence_reference(np.asarray([[99]], dtype=np.int16))
    with pytest.raises(reference.GridEvidenceTableError, match="reference set is not exact"):
        reference.validate_grid_evidence_table(
            registry.as_json(), expected_references=(first_ref, second_ref, absent)
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("data_base64", "!!!"),
        ("shape", [1, 4]),
        ("byte_count", 99),
        ("sha256", "0" * 64),
        ("reference", "0" * 64 + ":2:2:int16-le-c-v1"),
    ),
)
def test_grid_evidence_rejects_blob_identity_tampering(
    field: str,
    replacement: Any,
) -> None:
    registry = reference.GridEvidenceRegistry()
    expected = registry.add_grid(np.asarray([[1, 2], [3, 4]], dtype=np.int16))
    table = copy.deepcopy(registry.as_json())
    table["blobs"][0][field] = replacement

    with pytest.raises(reference.GridEvidenceTableError):
        reference.validate_grid_evidence_table(table, expected_references=(expected,))


def test_grid_evidence_rejects_duplicate_and_nonlexical_blobs() -> None:
    registry = reference.GridEvidenceRegistry()
    references = (
        registry.add_grid(np.asarray([[1]], dtype=np.int16)),
        registry.add_grid(np.asarray([[2]], dtype=np.int16)),
    )
    duplicate = copy.deepcopy(registry.as_json())
    duplicate["blobs"].append(copy.deepcopy(duplicate["blobs"][0]))
    with pytest.raises(reference.GridEvidenceTableError, match="duplicate blob"):
        reference.validate_grid_evidence_table(duplicate, expected_references=references)

    reversed_table = copy.deepcopy(registry.as_json())
    reversed_table["blobs"].reverse()
    with pytest.raises(reference.GridEvidenceTableError, match="lexically sorted"):
        reference.validate_grid_evidence_table(reversed_table, expected_references=references)


def test_exterior_support_registry_canonicalizes_shares_and_retains_empty_manifest() -> None:
    entries = [(40, -2, 7), (-3, 5, 2)]
    registry = reference.ExteriorSupportRegistry()
    populated_ref = registry.add(entries)
    assert registry.add(list(reversed(entries))) == populated_ref
    empty_ref = registry.add([])
    assert populated_ref != empty_ref
    assert len(registry.as_json()["blobs"]) == 2

    decoded = reference.validate_expected_exterior_support_table(
        registry.as_json(),
        expected_references=(populated_ref, empty_ref, populated_ref, None),
    )
    assert decoded[populated_ref] == ((-3, 5, 2), (40, -2, 7))
    assert decoded[empty_ref] == ()
    with pytest.raises(reference.ExteriorSupportTableError, match="not distinct"):
        reference.canonical_support_entries([entries[0], entries[0]])


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("data_base64", "!!!"),
        ("entry_count", 99),
        ("byte_count", 1),
        ("sha256", "0" * 64),
        (
            "reference",
            "0" * 64 + ":1:signed-coordinate-label-json-utf8-v1",
        ),
    ),
)
def test_exterior_support_rejects_blob_identity_tampering(
    field: str,
    replacement: Any,
) -> None:
    registry = reference.ExteriorSupportRegistry()
    expected = registry.add([(40, -2, 7)])
    table = copy.deepcopy(registry.as_json())
    table["blobs"][0][field] = replacement

    with pytest.raises(reference.ExteriorSupportTableError):
        reference.validate_expected_exterior_support_table(
            table, expected_references=(expected,)
        )


def test_exterior_support_rejects_duplicate_or_inexact_reference_sets() -> None:
    registry = reference.ExteriorSupportRegistry()
    first = registry.add([(40, -2, 7)])
    second = registry.add([])
    duplicate = copy.deepcopy(registry.as_json())
    duplicate["blobs"].append(copy.deepcopy(duplicate["blobs"][0]))
    with pytest.raises(reference.ExteriorSupportTableError, match="duplicate blob"):
        reference.validate_expected_exterior_support_table(
            duplicate, expected_references=(first, second)
        )

    with pytest.raises(reference.ExteriorSupportTableError, match="reference set is not exact"):
        reference.validate_expected_exterior_support_table(
            registry.as_json(), expected_references=(first,)
        )


def test_fixed_key_exact_ratios_and_half_quantum_ties_to_even() -> None:
    quantum = math.ldexp(1.0, -40)
    assert reference.fixed_key(quantum) == 1
    assert reference.fixed_key(quantum / 2.0) == 0
    assert reference.fixed_key(1.5 * quantum) == 2
    assert reference.fixed_key(2.5 * quantum) == 2
    assert reference.fixed_key(-quantum / 2.0) == 0
    assert reference.fixed_key(-1.5 * quantum) == -2
    assert reference.fixed_key(-2.5 * quantum) == -2
    assert reference.fixed_key(math.nextafter(quantum / 2.0, math.inf)) == 1
    assert reference.fixed_key(math.nextafter(quantum / 2.0, -math.inf)) == 0
    assert reference.fixed_key(100.0 * quantum) != reference.fixed_key(102.0 * quantum)


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_fixed_key_rejects_nonfinite_values(value: float) -> None:
    with pytest.raises(reference.SelectionSchemaError, match="finite binary64"):
        reference.fixed_key(value)


def test_compound_selector_uses_dense_ranks_complete_ties_and_canonical_choice() -> None:
    snapshot = _split_snapshot(
        actions=(A1, A2, A4, A3),
        probe_actions=(A4, A3),
    )
    raw = select_action_conditional_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    fixed = reference.select_compound_action_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    rows = {row.action: row for row in fixed.rows}

    assert raw.x_decision.action == A4
    assert fixed.x_decision.action == A3
    assert fixed.x_utility_maximizers == (A3, A4)
    assert rows[A3].x_rank == rows[A4].x_rank == 1
    assert rows[A3].x_selected and not rows[A4].x_selected
    assert fixed.exploit_set == (A1, A2)
    assert fixed.m_decision.action == A1
    assert reference.validate_selection_digest_preimage(
        reference.build_selection_digest_preimage(fixed)
    ) == reference.build_selection_digest_preimage(fixed)


def test_compound_selector_zero_key_gate_and_material_separation() -> None:
    snapshot = _split_snapshot(cross_cost=2.0, probe_cost=4.0)
    final_level = reference.select_compound_action_qbc(
        snapshot, cross_level_multiplier=1.0, probes_used=0, probe_cap=3
    )
    cross_level = reference.select_compound_action_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    raw = select_action_conditional_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )

    assert final_level.m_decision.mode == final_level.x_decision.mode == "exploit"
    assert final_level.m_decision.gate_reason == "nonpositive_fixed_utility"
    assert final_level.x_decision.gate_reason == "nonpositive_fixed_utility"
    assert cross_level.x_decision.mode == "probe"
    assert cross_level.x_decision.action == raw.x_decision.action == A3
    assert reference.fixed_key(next(row for row in raw.rows if row.action == A3).x_utility) > 0


def test_raw_and_compound_selection_digest_tampering_is_rejected() -> None:
    snapshot = _split_snapshot()
    raw = select_action_conditional_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    fixed = reference.select_compound_action_qbc(
        snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    for selection in (raw, fixed):
        preimage = reference.build_selection_digest_preimage(selection)
        tampered = copy.deepcopy(preimage)
        tampered["candidate_records"][0]["scalars"]["m_selected"] = True
        with pytest.raises(reference.SelectionSchemaError):
            reference.validate_selection_digest_preimage(tampered)


@pytest.mark.parametrize("fixed", (False, True))
def test_isolated_action_relabeling_commutes_under_bijective_map(fixed: bool) -> None:
    left_snapshot, right_snapshot, action_map = _mapped_split_snapshots()
    selector = reference.select_compound_action_qbc if fixed else select_action_conditional_qbc
    left = selector(
        left_snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    right = selector(
        right_snapshot, cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )

    relation = reference.compare_selector_selections(
        left,
        right,
        numeric_relation="exact_binary64",
        action_map=action_map,
    )

    assert relation.passes
    assert relation.reasons == ()
    assert relation.details["compared_candidate_count"] == 3
    assert all(
        relation.details[name] == 0
        for name in (
            "numeric_mismatch_count",
            "eligibility_mismatch_count",
            "rank_mismatch_count",
            "selected_membership_mismatch_count",
            "set_mismatch_count",
            "gate_mismatch_count",
            "decision_mismatch_count",
            "key_mismatch_count",
        )
    )


@pytest.mark.parametrize("fixed", (False, True))
def test_isolated_injective_signature_pushforward_commutes(fixed: bool) -> None:
    base = _split_snapshot()
    pushed = PlanningSnapshot(
        actions=base.actions,
        hypothesis_ids=base.hypothesis_ids,
        weights=base.weights,
        predictions={
            action: tuple(
                Prediction(
                    prediction.next_grid + np.int16(10),
                    prediction.game_state,
                    prediction.level_delta,
                    {},
                )
                for prediction in base.predictions[action]
                if prediction is not None
            )
            for action in base.actions
        },
        costs=base.costs,
    )
    selector = reference.select_compound_action_qbc if fixed else select_action_conditional_qbc
    left = selector(base, cross_level_multiplier=23.0, probes_used=0, probe_cap=3)
    right = selector(pushed, cross_level_multiplier=23.0, probes_used=0, probe_cap=3)

    relation = reference.compare_selector_selections(
        left, right, numeric_relation="exact_binary64"
    )

    assert relation.passes
    assert relation.reasons == ()


@pytest.mark.parametrize("fixed", (False, True))
def test_noninjective_signature_pushforward_cannot_pass_selector_relation(fixed: bool) -> None:
    base = _split_snapshot()
    collapsed = PlanningSnapshot(
        actions=base.actions,
        hypothesis_ids=base.hypothesis_ids,
        weights=base.weights,
        predictions={
            action: tuple(_prediction(9) for _ in base.predictions[action])
            for action in base.actions
        },
        costs=base.costs,
    )
    selector = reference.select_compound_action_qbc if fixed else select_action_conditional_qbc
    left = selector(base, cross_level_multiplier=23.0, probes_used=0, probe_cap=3)
    right = selector(collapsed, cross_level_multiplier=23.0, probes_used=0, probe_cap=3)

    relation = reference.compare_selector_selections(
        left, right, numeric_relation="exact_binary64"
    )

    assert not relation.passes
    assert relation.details["numeric_mismatch_count"] > 0


@pytest.mark.parametrize(
    "selector_name",
    ("_select_raw_isolated", "_select_fixed_counted"),
)
def test_transport_selector_exception_propagates_as_global_evaluator_fault(
    selector_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visual = _palette_visual_primitives()

    def fail_selector(*_args: Any, **_kwargs: Any) -> Any:
        raise reference.SelectionSchemaError("selector fixture fault")

    monkeypatch.setattr(audit, selector_name, fail_selector)
    with pytest.raises(reference.SelectionSchemaError, match="selector fixture fault"):
        audit._transport_primitive(
            visual.base,
            visual.contract,
            visual.isolated_action_map,
            audit.ResourceCounterState(),
            signature_pushforward=False,
        )


def test_visual_actual_selector_layers_evaluate_only_after_every_upstream_layer() -> None:
    visual = _palette_visual_primitives(
        transformed_weight_delta=1e-13,
        transformed_cost_delta=5e-13,
    )

    evidence = audit.derive_visual_evidence(
        visual,
        family="homologue",
        scene_index=3,
        transform_name=reference.PALETTE_TRANSFORM_NAME,
        v6_result={},
        grid_registry=reference.GridEvidenceRegistry(),
        support_registry=reference.ExteriorSupportRegistry(),
    )

    for name in (
        "pipeline_integrity",
        "frontier_relation",
        "role_weight_relation",
        "root_transition",
        "planner_cost",
        "actual_raw_selector",
        "actual_fixed_selector",
    ):
        assert evidence[name]["status"] == "evaluated"
        assert evidence[name]["passes"] is True
        assert evidence[name]["reasons"] == []
    assert evidence["role_weight_relation"]["details"]["max_abs_delta"] == pytest.approx(
        1e-13
    )
    assert evidence["planner_cost"]["details"]["max_abs_delta"] == pytest.approx(5e-13)

    failed = _palette_visual_primitives(transformed_cost_delta=2e-9)
    failed_evidence = audit.derive_visual_evidence(
        failed,
        family="homologue",
        scene_index=3,
        transform_name=reference.PALETTE_TRANSFORM_NAME,
        v6_result={},
        grid_registry=reference.GridEvidenceRegistry(),
        support_registry=reference.ExteriorSupportRegistry(),
    )
    assert failed_evidence["planner_cost"]["reasons"] == ["rolewise_cost_mismatch"]
    for name in ("actual_raw_selector", "actual_fixed_selector"):
        assert failed_evidence[name]["status"] == "precondition_failed"
        assert failed_evidence[name]["passes"] is False
        assert failed_evidence[name]["reasons"] == [
            "not_testable_due_upstream_mismatch"
        ]


def test_visual_role_weight_relation_requires_raw_vectors_to_be_normalized() -> None:
    visual = _palette_visual_primitives(weights=(0.2, 0.2, 0.2, 0.2))

    evidence = audit.derive_visual_evidence(
        visual,
        family="homologue",
        scene_index=3,
        transform_name=reference.PALETTE_TRANSFORM_NAME,
        v6_result={},
        grid_registry=reference.GridEvidenceRegistry(),
        support_registry=reference.ExteriorSupportRegistry(),
    )

    assert evidence["pipeline_integrity"]["passes"] is True
    weights = evidence["role_weight_relation"]
    assert weights["status"] == "evaluated"
    assert weights["passes"] is False
    assert weights["reasons"] == ["gibbs_weight_mismatch"]
    assert weights["details"]["nonfinite_count"] == 0
    # Vector normalization is a separate conjunction; every paired role record still
    # passes its own pairwise tolerance and therefore must not inflate this record count.
    assert weights["details"]["tolerance_mismatch_count"] == 0
    assert all(record["passes"] is True for record in weights["details"]["role_records"])
    for name in ("actual_raw_selector", "actual_fixed_selector"):
        assert evidence[name]["status"] == "precondition_failed"
        assert evidence[name]["reasons"] == ["not_testable_due_upstream_mismatch"]


def test_compound_scale_reconciliation_checks_fixed_relation_raw_numeric_payload() -> None:
    visual = _palette_visual_primitives()
    evidence = audit.derive_visual_evidence(
        visual,
        family="homologue",
        scene_index=3,
        transform_name=reference.PALETTE_TRANSFORM_NAME,
        v6_result={},
        grid_registry=reference.GridEvidenceRegistry(),
        support_registry=reference.ExteriorSupportRegistry(),
    )
    row = {"evidence": evidence}

    assert audit._compound_scale_reconciled(row, primary=False)

    mismatched = copy.deepcopy(row)
    fixed_details = mismatched["evidence"]["actual_fixed_selector"]["details"]
    fixed_details["numeric_mismatch_count"] = 1
    # The aggregate predicate must derive the conjunction from details rather than trust
    # a producer-controlled envelope pass bit.
    assert mismatched["evidence"]["actual_fixed_selector"]["passes"] is True
    assert not audit._compound_scale_reconciled(mismatched, primary=False)

    nonfinite = copy.deepcopy(row)
    record = nonfinite["evidence"]["actual_fixed_selector"]["details"][
        "candidate_records"
    ][0]
    record["left"]["evsi"] = math.nan
    assert not audit._compound_scale_reconciled(nonfinite, primary=False)


@pytest.mark.parametrize(
    ("field", "reason", "layers"),
    (
        (
            "action_relabel",
            "isolated_action_map_not_bijective",
            ("isolated_action_relabel_raw", "isolated_action_relabel_fixed"),
        ),
        (
            "action_relabel",
            "isolated_action_map_not_canonical_order_preserving",
            ("isolated_action_relabel_raw", "isolated_action_relabel_fixed"),
        ),
        (
            "signature_pushforward",
            "isolated_signature_transform_not_injective",
            (
                "isolated_signature_pushforward_raw",
                "isolated_signature_pushforward_fixed",
            ),
        ),
    ),
)
def test_isolated_premise_rejections_have_only_their_named_reason(
    field: str,
    reason: str,
    layers: tuple[str, str],
) -> None:
    visual = _palette_visual_primitives()
    replacement = audit.TransportPrimitive(None, None, None, reason)
    visual = audit.VisualPrimitive(
        base=visual.base,
        transformed=audit.PipelinePrimitive(None, None, "unavailable"),
        contract=visual.contract,
        actual_action_map=visual.actual_action_map,
        isolated_action_map=visual.isolated_action_map,
        action_relabel=(replacement if field == "action_relabel" else visual.action_relabel),
        signature_pushforward=(
            replacement if field == "signature_pushforward" else visual.signature_pushforward
        ),
        raw_transform={},
    )

    evidence = audit.derive_visual_evidence(
        visual,
        family="homologue",
        scene_index=3,
        transform_name=reference.PALETTE_TRANSFORM_NAME,
        v6_result={},
        grid_registry=reference.GridEvidenceRegistry(),
        support_registry=reference.ExteriorSupportRegistry(),
    )

    for name in layers:
        assert evidence[name]["status"] == "evaluated"
        assert evidence[name]["passes"] is False
        assert evidence[name]["reasons"] == [reason]
    for name in ("actual_raw_selector", "actual_fixed_selector"):
        assert evidence[name]["status"] == "precondition_failed"
        assert evidence[name]["reasons"] == ["not_testable_due_upstream_mismatch"]


def test_actual_selector_tolerance_and_isolated_binary64_are_distinct() -> None:
    selection = reference.select_compound_action_qbc(
        _split_snapshot(), cross_level_multiplier=23.0, probes_used=0, probe_cap=3
    )
    right = copy.deepcopy(reference.selection_details(selection))
    right["candidate_records"][0]["scalars"]["evsi"] += 5e-13
    core = {
        key: copy.deepcopy(value)
        for key, value in right.items()
        if key != "selection_sha256"
    }
    right["selection_sha256"] = reference.canonical_sha256(
        {
            "schema_version": reference.SELECTION_DIGEST_SCHEMA_VERSION,
            "selector_identity": dict(reference.FIXED_SELECTOR_IDENTITY),
            **core,
        }
    )
    left = reference.selection_details(selection)
    identity_map = {
        row.action: row.action for row in selection.rows
    }

    tolerance = audit.selector_relation(
        left,
        right,
        action_map=identity_map,
        fixed=True,
        exact_binary64=False,
    )
    exact = audit.selector_relation(
        left,
        right,
        action_map=identity_map,
        fixed=True,
        exact_binary64=True,
    )

    assert tolerance["passes"] is True
    assert exact["passes"] is False
    assert exact["reasons"] == ["fixed_selector_numeric_mismatch"]


def test_base_pipeline_failure_retains_all_sibling_layers_with_exact_upstream_reason() -> None:
    evidence = audit.derive_base_evidence(
        audit.PipelinePrimitive(None, None, "unavailable"),
        family="homologue",
        scene_index=0,
    )

    assert tuple(evidence) == (
        "pipeline",
        "raw_selector",
        "fixed_selector",
        "structural",
        "mechanism",
        "v4_counterfactual",
        "prepreregistered_reproduction",
    )
    assert evidence["pipeline"]["status"] == "evaluated"
    assert evidence["pipeline"]["reasons"] == ["base_pipeline_unavailable"]
    for name in tuple(evidence)[1:]:
        assert evidence[name]["status"] == "precondition_failed"
        assert evidence[name]["passes"] is False
        assert evidence[name]["reasons"] == ["not_testable_due_upstream_mismatch"]


@pytest.mark.parametrize("scene_index", (1, 2, 3))
def test_failed_extension_base_has_no_prepreregistered_observation_reason(
    scene_index: int,
) -> None:
    evidence = audit.derive_base_evidence(
        audit.PipelinePrimitive(None, None, "unavailable"),
        family="homologue",
        scene_index=scene_index,
    )

    assert evidence["prepreregistered_reproduction"] == audit.layer(
        audit.PREOBSERVED_DEFAULT,
        status="precondition_failed",
        reasons=("no_prepreregistered_observation",),
    )
    for name in (
        "raw_selector",
        "fixed_selector",
        "structural",
        "mechanism",
        "v4_counterfactual",
    ):
        assert evidence[name]["reasons"] == ["not_testable_due_upstream_mismatch"]


def test_prepreregistered_base_observation_reproduction_logic_is_exact() -> None:
    expected = audit.PREOBSERVED_BASES["homologue"]
    mechanism = {
        "max_evsi": expected["max_evsi"],
        "max_x_utility": expected["max_x_utility"],
        "m_mode": expected["m_mode"],
        "x_mode": expected["x_mode"],
        "exploit_action": expected["exploit_action"],
    }
    passing = audit._base_preobserved_layer(
        "homologue",
        0,
        structural_pass=True,
        mechanism_pass=False,
        v4_pass=False,
        mechanism=mechanism,
    )
    mismatch_mechanism = dict(mechanism)
    mismatch_mechanism["max_evsi"] = float(expected["max_evsi"]) + 1e-6
    failing = audit._base_preobserved_layer(
        "homologue",
        0,
        structural_pass=True,
        mechanism_pass=False,
        v4_pass=False,
        mechanism=mismatch_mechanism,
    )
    extension = audit._base_preobserved_layer(
        "homologue",
        1,
        structural_pass=True,
        mechanism_pass=False,
        v4_pass=False,
        mechanism=mechanism,
    )

    assert passing["passes"] is True
    assert passing["details"]["comparison_passes"] is True
    assert failing["passes"] is False
    assert failing["reasons"] == ["prepreregistered_base_observation_mismatch"]
    assert extension == audit.layer(
        audit.PREOBSERVED_DEFAULT,
        status="precondition_failed",
        reasons=("no_prepreregistered_observation",),
    )


def test_frozen_v6_failure_vector_reproduction_and_one_cell_drift() -> None:
    rows = _frozen_miniature_v6_rows()

    observed = audit._patch_v6_failure_vector(rows)

    assert observed == audit.V6_FAILURE_VECTOR_SHA256
    assert all(
        row["evidence"]["v6_reproduction"]["passes"] is True for row in rows
    )
    assert all(
        row["evidence"]["v6_reproduction"]["details"][
            "observed_failure_vector_sha256"
        ]
        == audit.V6_FAILURE_VECTOR_SHA256
        for row in rows
    )

    drifted = _frozen_miniature_v6_rows()
    drifted[1]["evidence"]["v6_reproduction"]["details"]["observed_comparison"][
        "overflow_nonbackground_count"
    ] -= 1
    drifted_sha = audit._patch_v6_failure_vector(drifted)
    assert drifted_sha != audit.V6_FAILURE_VECTOR_SHA256
    assert all(
        row["evidence"]["v6_reproduction"]["reasons"]
        == ["v6_failure_vector_mismatch"]
        for row in drifted
    )


def test_reason_order_and_precondition_reason_vocabulary_are_fail_closed() -> None:
    value = audit.layer(
        {"fixture": 1},
        reasons=("fixed_selector_decision_mismatch", "compiler_role_mismatch"),
    )
    assert value["reasons"] == [
        "compiler_role_mismatch",
        "fixed_selector_decision_mismatch",
    ]
    with pytest.raises(audit.V7AuditError, match="unknown scientific reason"):
        audit.layer({}, reasons=("not_registered",))
    with pytest.raises(audit.V7AuditError, match="noncanonical reason"):
        audit.layer(
            {},
            status="precondition_failed",
            reasons=("compiler_role_mismatch",),
        )


def test_compute_deadline_is_inclusive_and_precedes_selector_counting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit.time, "monotonic", lambda: 100.0)
    audit._require_compute_time(100.000_001)
    with pytest.raises(TimeoutError, match="compute deadline elapsed"):
        audit._require_compute_time(100.0)

    counters = audit.ResourceCounterState()
    monkeypatch.setattr(audit, "_ACTIVE_COMPUTE_DEADLINE", 100.0)
    with pytest.raises(TimeoutError, match="compute deadline elapsed"):
        audit._select_raw_isolated(_split_snapshot(), counters)
    assert counters.snapshot()["isolated_raw_selector_calls"] == 0


def test_v4_primitive_normalizes_legacy_action_and_uses_historical_agreement() -> None:
    raw = {
        "causal_exercise": True,
        "selected_action": {"kind": 6, "row": 7, "col": 11},
        "selected_evsi": 0.25,
        "selected_x_utility": 1.5,
        "agreement": 0.75,
    }

    details, passed = audit._v4_details(raw)

    assert passed is True
    assert details == {
        "causal_exercise": True,
        "selected_action": {"kind": "ACTION6", "row": 7, "col": 11},
        "selected_evsi": 0.25,
        "selected_x_utility": 1.5,
        "historical_agreement": 0.75,
    }
    raw["causal_exercise"] = False
    _failed_details, failed = audit._v4_details(raw)
    assert failed is False


def test_exact_resource_counter_vector_and_derived_equations() -> None:
    state = audit.ResourceCounterState()
    for name, value in audit.EXPECTED_RESOURCE_COUNTS.items():
        if name in {"pure_selector_calls", "total_worker_starts", "fixed_selector_control_calls"}:
            continue
        state.increment(name, value)
    state.set_compound_control_calls(audit.EXPECTED_RESOURCE_COUNTS["fixed_selector_control_calls"])

    counters = state.snapshot()
    assert counters == dict(audit.EXPECTED_RESOURCE_COUNTS)
    assert audit.validate_resource_counters(counters) == counters
    assert audit.resource_contract_passes(counters)
    assert counters["total_worker_starts"] == (
        counters["persistent_worker_starts"] + counters["transient_worker_starts"]
    )
    assert counters["pure_selector_calls"] == 566


def test_resource_counter_forbidden_use_and_derivation_drift_fail_closed() -> None:
    counters = dict(audit.EXPECTED_RESOURCE_COUNTS)
    counters["model_calls"] = 1
    assert not audit.resource_contract_passes(counters)

    drift = dict(counters)
    drift["total_worker_starts"] += 1
    with pytest.raises(audit.V7AuditError, match="worker_starts derivation"):
        audit.validate_resource_counters(drift)
    drift = dict(counters)
    drift["pure_selector_calls"] += 1
    with pytest.raises(audit.V7AuditError, match="pure_selector_calls derivation"):
        audit.validate_resource_counters(drift)
    with pytest.raises(audit.V7AuditError, match="derived counter"):
        audit.ResourceCounterState().increment("pure_selector_calls")
    with pytest.raises(audit.V7AuditError, match="JSON integer"):
        audit.ResourceCounterState().increment("model_calls", True)


def test_timeout_worker_memory_and_forbidden_resource_gates_are_exact() -> None:
    timeout = v5_audit._admission_resource_gate(
        v5_audit.AdmissionResourceSignals(timeout_programs=1)
    )
    memory = v5_audit._admission_resource_gate(
        v5_audit.AdmissionResourceSignals(worker_memory_ok=False)
    )
    forbidden_counts = {
        name: 0 for name in v5_audit.FORBIDDEN_AUDIT_RESOURCE_FIELDS
    }
    forbidden_counts["model_calls"] = 1
    forbidden = v5_audit._admission_resource_gate(
        v5_audit.AdmissionResourceSignals(
            forbidden_resource_counts=forbidden_counts
        )
    )

    assert timeout["passes"] is False and timeout["reasons"] == ["timeout_program"]
    assert memory["passes"] is False and memory["reasons"] == ["worker_memory_drift"]
    assert forbidden["passes"] is False
    assert forbidden["reasons"] == ["forbidden_resource_use"]
    assert forbidden["forbidden_resources_used"] == ["model_calls"]
    valid_memory = {
        "hard_limit_enforced": True,
        "limit_kind": v5_audit.RLIMIT_DATA_HEADROOM_KIND,
        "allocation_headroom_bytes": 268_435_456,
        "diagnostic": None,
    }
    assert v5_audit._worker_memory_valid(valid_memory)
    drifted_memory = dict(valid_memory)
    drifted_memory["allocation_headroom_bytes"] -= 1
    assert not v5_audit._worker_memory_valid(drifted_memory)


@pytest.mark.parametrize(
    ("transform_name", "target", "length", "permutation"),
    (
        ("candidate_list_reversal", "candidate_sequence", 1, [0]),
        ("hypothesis_list_reversal", "hypothesis_sequence", 4, [3, 2, 1, 0]),
        (
            "serialized_outcome_cell_order_reversal",
            "per_action_serialized_outcome_cell_sequence",
            4,
            [3, 2, 1, 0],
        ),
    ),
)
def test_order_evidence_exact_permutations_and_selector_relations(
    transform_name: str,
    target: str,
    length: int,
    permutation: list[int],
) -> None:
    base = _palette_visual_primitives().base
    assert base.result is not None and base.fixed_selection is not None
    rule = "left_rotate_one" if "left_rotation" in transform_name else "reverse"
    contract = {
        "schema_version": "action-qbc-v7-order-transform-contract-v1",
        "name": transform_name,
        "target": target,
        "rule": rule,
    }
    contract_sha = audit.canonical_sha256(contract)
    registered = {
        "kind": "order_transform",
        "transform_name": transform_name,
        "order_contract_sha256": contract_sha,
    }
    record = {
        "action": (
            audit.action_json(base.result.snapshot.actions[0])
            if transform_name == "serialized_outcome_cell_order_reversal"
            else None
        ),
        "sequence_length": length,
        "output_to_input_permutation": permutation,
    }
    primitive = audit.OrderPrimitive(
        base=base,
        transform_name=transform_name,
        target=target,
        order_contract_sha256=contract_sha,
        permutation_records=(record,),
        raw_selection=base.result.selection,
        fixed_selection=base.fixed_selection,
    )

    evidence = audit._derive_order_evidence(primitive, registered)

    assert tuple(evidence) == audit.ORDER_EVIDENCE_KEYS
    assert all(envelope["passes"] is True for envelope in evidence.values())
    assert all(envelope["reasons"] == [] for envelope in evidence.values())

    malformed = audit.OrderPrimitive(
        base=base,
        transform_name=transform_name,
        target=target,
        order_contract_sha256=contract_sha,
        permutation_records=(
            {
                **record,
                "output_to_input_permutation": [1] if length == 1 else [0] * length,
            },
        ),
        raw_selection=base.result.selection,
        fixed_selection=base.fixed_selection,
    )
    failed = audit._derive_order_evidence(malformed, registered)
    assert failed["order_transform"]["reasons"] == ["order_relation_mismatch"]
    for name in ("raw_selector_relation", "fixed_selector_relation"):
        assert failed[name]["status"] == "precondition_failed"
        assert failed[name]["reasons"] == ["not_testable_due_upstream_mismatch"]

    for drifted_registration in (
        {**registered, "transform_name": f"{transform_name}_drift"},
        {**registered, "order_contract_sha256": "f" * 64},
    ):
        drifted = audit._derive_order_evidence(primitive, drifted_registration)
        assert drifted["order_transform"]["reasons"] == [
            "order_relation_mismatch"
        ]
        assert drifted["raw_selector_relation"]["status"] == "precondition_failed"

    wrong_target = audit.OrderPrimitive(
        base=base,
        transform_name=transform_name,
        target=f"{target}_drift",
        order_contract_sha256=contract_sha,
        permutation_records=(record,),
        raw_selection=base.result.selection,
        fixed_selection=base.fixed_selection,
    )
    target_drift = audit._derive_order_evidence(wrong_target, registered)
    assert target_drift["order_transform"]["reasons"] == [
        "order_relation_mismatch"
    ]


def test_control_layer_checks_exact_contract_calls_predicate_and_observation_hash() -> None:
    control_id = "worker_memory_drift"
    record = {"name": control_id, "passes": True, "observed": {"drift": True}}
    primitive = audit.ControlPrimitive(control_id, record, record, 0, 0)
    registered = {
        "control_contract_sha256": audit.CONTROL_CONTRACT_SHA256,
        "raw_predicate_id": "raw:worker_memory_drift",
        "fixed_predicate_id": "fixed:worker_memory_drift",
        "raw_selector_call_count": 0,
        "fixed_selector_call_count": 0,
    }

    raw = audit._derive_control_layer(primitive, registered, fixed=False)
    fixed = audit._derive_control_layer(primitive, registered, fixed=True)

    assert raw["passes"] is True and fixed["passes"] is True
    assert raw["details"]["observed_sha256"] == audit.canonical_sha256(record)
    wrong_calls = dict(registered)
    wrong_calls["raw_selector_call_count"] = 1
    failed = audit._derive_control_layer(primitive, wrong_calls, fixed=False)
    assert failed["passes"] is False
    assert failed["reasons"] == ["control_expectation_mismatch"]


def test_identity_boundary_rechecks_registration_file_head_and_uv_lock_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    artifact_directory = tmp_path / "artifacts"
    git_directory = tmp_path / ".git"
    artifact_directory.mkdir()
    git_directory.mkdir()
    registration_path = artifact_directory / "action_qbc_v7_open_registration.json"
    head_path = git_directory / "HEAD"
    uv_lock_path = tmp_path / "uv.lock"
    registration_bytes = b'{"fixture":"registration"}\n'
    uv_lock_bytes = b"fixture-lock\n"
    registration_path.write_bytes(registration_bytes)
    head_path.write_text("a" * 40 + "\n", encoding="ascii")
    uv_lock_path.write_bytes(uv_lock_bytes)
    registration: dict[str, Any] = {
        "preregistration": {"fixture": "preregistered"},
        "v6_negative": {"fixture": "negative"},
        "content_sha256": "c" * 64,
        "source_manifest": {"manifest_sha256": "d" * 64},
        "execution_contract": {"argv_hashes": {"scientific": "e" * 64}},
        "platform": {},
    }
    prereg, v6_negative, registration_identity, execution_identity = (
        audit._identity_objects(registration, tmp_path)
    )
    payload = {
        "preregistration_identity": prereg,
        "v6_negative_identity": v6_negative,
        "registration_identity": registration_identity,
        "execution_identity": execution_identity,
    }
    counters = {name: 0 for name in audit.RESOURCE_COUNTER_NAMES}
    monkeypatch.chdir(tmp_path)

    audit._validate_identity_boundary(payload, registration, counters)

    registration_path.write_bytes(b'{"fixture":"tampered"}\n')
    with pytest.raises(audit.V7AuditError, match="registration file identity"):
        audit._validate_identity_boundary(payload, registration, counters)
    registration_path.write_bytes(registration_bytes)

    head_path.write_text("b" * 40 + "\n", encoding="ascii")
    with pytest.raises(audit.V7AuditError, match="execution identity constants"):
        audit._validate_identity_boundary(payload, registration, counters)
    head_path.write_text("a" * 40 + "\n", encoding="ascii")

    uv_lock_path.write_bytes(b"tampered-lock\n")
    with pytest.raises(audit.V7AuditError, match="execution identity constants"):
        audit._validate_identity_boundary(payload, registration, counters)


@pytest.mark.parametrize("stage", audit.GLOBAL_FALLBACK_STAGE_ORDER)
def test_every_global_fallback_retains_exact_inventory_and_false_authorization(
    stage: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(audit, "_payload_prefix", _stub_payload_prefix)
    monkeypatch.setattr(audit, "_validate_identity_boundary", lambda *_args: None)
    candidate_size = (
        audit.PAYLOAD_CAP_BYTES + 1
        if stage == "payload_size_limit_exceeded"
        else None
    )

    payload = audit.build_global_fallback(
        _fallback_registration(),
        stage,
        candidate_payload_size_bytes=candidate_size,
        repository_root=tmp_path,
        resource_counters={name: 0 for name in audit.RESOURCE_COUNTER_NAMES},
    )

    assert tuple(payload) == audit.TOP_LEVEL_KEYS
    assert payload["terminal_fallback_stage"] == stage
    assert payload["candidate_payload_size_bytes"] == candidate_size
    assert payload["diagnostic_complete"] is False
    assert payload["scientific_capability_passes"] is False
    assert payload["authorization"] == dict(audit.AUTHORIZATION)
    assert len(payload["rows"]) == 140
    assert [row["address"]["row_index"] for row in payload["rows"]] == list(range(140))
    assert all(row["disposition"] == "terminal_global_negative" for row in payload["rows"])
    assert all(row["terminal"]["stage"] == stage for row in payload["rows"])
    assert len(audit.canonical_json_bytes(payload)) <= audit.PAYLOAD_CAP_BYTES
    assert audit.validate_scientific_payload(payload, _fallback_registration()) == payload


def test_global_fallback_stage_precedence_is_exact_and_size_contract_is_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    assert audit.GLOBAL_FALLBACK_STAGE_ORDER == (
        "transform_action_map_invalid",
        "scientific_record_inventory_invalid",
        "grid_evidence_table_invalid",
        "expected_exterior_support_table_invalid",
        "evaluator_internal_error",
        "payload_size_limit_exceeded",
    )
    monkeypatch.setattr(audit, "_payload_prefix", _stub_payload_prefix)
    common = {
        "repository_root": tmp_path,
        "resource_counters": {name: 0 for name in audit.RESOURCE_COUNTER_NAMES},
    }
    with pytest.raises(audit.V7AuditError, match="exact oversized"):
        audit.build_global_fallback(
            _fallback_registration(),
            "payload_size_limit_exceeded",
            candidate_payload_size_bytes=audit.PAYLOAD_CAP_BYTES,
            **common,
        )
    with pytest.raises(audit.V7AuditError, match="null outside"):
        audit.build_global_fallback(
            _fallback_registration(),
            "evaluator_internal_error",
            candidate_payload_size_bytes=audit.PAYLOAD_CAP_BYTES + 1,
            **common,
        )


@pytest.mark.parametrize(
    ("measured", "falls_back"),
    (
        (audit.PAYLOAD_CAP_BYTES - 1, False),
        (audit.PAYLOAD_CAP_BYTES, False),
        (audit.PAYLOAD_CAP_BYTES + 1, True),
    ),
)
def test_production_cap_finalization_at_exact_boundary(
    measured: int,
    falls_back: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal = {"normal": True}
    observed: list[tuple[str, int | None]] = []

    monkeypatch.setattr(audit, "_finalize_candidate", lambda *_args: normal)

    def fallback(
        _registration: Mapping[str, Any],
        stage: str,
        *,
        candidate_payload_size_bytes: int | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        observed.append((stage, candidate_payload_size_bytes))
        return {"fallback": stage}

    monkeypatch.setattr(audit, "build_global_fallback", fallback)
    result = audit.finalize_scientific_payload(
        {"repository_root": "."},
        {},
        candidate_payload_size_bytes=measured,
    )

    if falls_back:
        assert result == {"fallback": "payload_size_limit_exceeded"}
        assert observed == [("payload_size_limit_exceeded", measured)]
    else:
        assert result is normal
        assert observed == []


def test_scientific_fallback_precedes_size_measurement_and_unexpected_error_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    def fallback(
        _registration: Mapping[str, Any],
        stage: str,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        observed.append(stage)
        return {"fallback": stage}

    monkeypatch.setattr(audit, "build_global_fallback", fallback)

    def registered_failure(*_args: Any) -> None:
        raise audit.GlobalFallbackRequired("grid_evidence_table_invalid")

    monkeypatch.setattr(audit, "_finalize_candidate", registered_failure)
    assert audit.finalize_scientific_payload(
        {"repository_root": "."},
        {},
        candidate_payload_size_bytes=audit.PAYLOAD_CAP_BYTES + 1,
    ) == {"fallback": "grid_evidence_table_invalid"}

    def unexpected_failure(*_args: Any) -> None:
        raise RuntimeError("synthetic evaluator defect")

    monkeypatch.setattr(audit, "_finalize_candidate", unexpected_failure)
    assert audit.finalize_scientific_payload(
        {"repository_root": "."}, {}
    ) == {"fallback": "evaluator_internal_error"}
    assert observed == ["grid_evidence_table_invalid", "evaluator_internal_error"]


def test_candidate_inventory_localizes_one_schema_error_and_retains_all_siblings() -> None:
    registration = _fallback_registration()
    registered_rows = registration["row_inventory"]["rows"]
    records = [
        {
            "address": {
                "row_index": row["row_index"],
                "row_id": row["row_id"],
                "kind": row["kind"],
            },
            "primitive": None,
        }
        for row in registered_rows
    ]
    records[37]["unexpected_producer_conclusion"] = True
    candidate = {
        "repository_root": ".",
        "records": records,
        "v6_result": {},
        "resource_state": audit.ResourceCounterState(),
        "legacy_state": v5_audit.AuditCounterState(),
    }

    inventory = audit._candidate_inventory(candidate, registration)

    assert len(inventory) == 140
    assert [index for index, (_row, _primitive, error) in enumerate(inventory) if error] == [
        37
    ]
    assert all(inventory[index][0] == registered_rows[index] for index in range(140))


def test_exact_addressable_terminal_row_schema_validates_as_one_normal_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _fallback_registration()
    registered_rows = registration["row_inventory"]["rows"]
    counters = {name: 0 for name in audit.RESOURCE_COUNTER_NAMES}
    rows = [audit._addressable_terminal_row(row) for row in registered_rows]
    payload = {
        **_stub_payload_prefix(registration, ".", counters),
        "grid_evidence": reference.empty_grid_evidence_table(),
        "expected_exterior_support": reference.empty_expected_exterior_support_table(),
        "rows": rows,
        "aggregates": audit._derive_aggregates(
            rows,
            counters,
            observed_v6_sha=None,
        ),
        "diagnostic_complete": False,
        "scientific_capability_passes": False,
        "authorization": dict(audit.AUTHORIZATION),
        "terminal_fallback_stage": None,
        "candidate_payload_size_bytes": None,
    }
    monkeypatch.setattr(audit, "_validate_identity_boundary", lambda *_args: None)

    validated = audit.validate_scientific_payload(payload, registration)

    assert len(validated["rows"]) == 140
    assert all(
        row["disposition"] == "terminal_addressable_negative"
        and set(row)
        == {
            "address",
            "registered_row",
            "disposition",
            "evidence",
            "terminal",
        }
        for row in validated["rows"]
    )
    malformed = copy.deepcopy(payload)
    malformed["rows"][37]["extra"] = None
    with pytest.raises(audit.V7AuditError, match="normal row key mismatch"):
        audit.validate_scientific_payload(malformed, registration)


def test_scientific_payload_validation_rejects_authorization_and_address_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    registration = _fallback_registration()
    monkeypatch.setattr(audit, "_payload_prefix", _stub_payload_prefix)
    monkeypatch.setattr(audit, "_validate_identity_boundary", lambda *_args: None)
    payload = audit.build_global_fallback(
        registration,
        "evaluator_internal_error",
        repository_root=tmp_path,
        resource_counters={name: 0 for name in audit.RESOURCE_COUNTER_NAMES},
    )

    authorization = copy.deepcopy(payload)
    authorization["authorization"]["runtime_v7_enabled"] = True
    with pytest.raises(audit.V7AuditError, match="fixed identity"):
        audit.validate_scientific_payload(authorization, registration)

    address = copy.deepcopy(payload)
    address["rows"][12]["address"]["row_id"] = "wrong"
    with pytest.raises(audit.GlobalFallbackRequired) as raised:
        audit.validate_scientific_payload(address, registration)
    assert raised.value.stage == "scientific_record_inventory_invalid"


def test_canonical_json_replay_is_deterministic_ascii_and_newline_free() -> None:
    first = {"z": ["caf\u00e9", 1], "a": {"b": False}}
    second = {"a": {"b": False}, "z": ["caf\u00e9", 1]}

    encoded = reference.canonical_json_bytes(first)

    assert encoded == reference.canonical_json_bytes(second)
    assert encoded == audit.canonical_json_bytes(second)
    assert encoded.isascii()
    assert not encoded.endswith(b"\n")
    assert reference.canonical_sha256(first) == reference.canonical_sha256(second)


def test_transform_contract_and_action_map_are_deterministically_reconstructible() -> None:
    contract = _contract(reference.TRANSLATION_PLUS_TRANSFORM_NAME)
    reconstructed = reference.validate_transform_contract(
        contract.core_json(), expected_sha256=contract.contract_sha256
    )
    first = reference.reconstruct_action_map(reconstructed, map_kind="isolated")
    second = reference.reconstruct_action_map(reconstructed, map_kind="isolated")

    assert first.as_json() == second.as_json()
    assert first.sha256 == second.sha256
    assert reference.canonical_json_bytes(first.as_json()) == reference.canonical_json_bytes(
        second.as_json()
    )
