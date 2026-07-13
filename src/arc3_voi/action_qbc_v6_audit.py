"""Copy-on-write v6 finite-grid scientific-audit overlay.

The runtime-v5 compiler, grounding, planner, selector, and controller are deliberately
reused without mutation.  This module owns only the revised scientific evidence boundary:
prediction grids are serialized once into a content-addressed table, visual relations are
computed by :mod:`arc3_voi.action_qbc_v6_reference`, and completed rows are revalidated
without calling the frozen v5 visual validator.

Nothing in this module authorizes a sealed run.  Registration, permit, launcher, lockbox,
and publication administration live in separately frozen v6 files.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isclose
from types import MappingProxyType
from typing import Any, Final, TypeAlias, cast

from . import action_qbc_audit as _v5
from . import action_qbc_v6_reference as _reference
from .config import SystemConfig
from .planner import PlanningSnapshot
from .types import Action, GameState, Prediction

JsonScalar: TypeAlias = str | int | float | bool | None  # noqa: UP040
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]  # noqa: UP040
ScientificRecordAddress: TypeAlias = tuple[str | int, ...]  # noqa: UP040

ACTION_QBC_V6_TREATMENT_ID: Final = "action-qbc-v6-finite-grid-evidence-v1"
ACTION_QBC_V6_RUNTIME_ID: Final = "crosslevel-voi-runtime-v6"
ACTION_QBC_V6_SCIENTIFIC_SCHEMA_VERSION: Final = "action-qbc-v6-scientific-payload-v1"
V6_VISUAL_SEMANTICS_ID: Final = _reference.FINITE_GRID_SEMANTICS_ID
V6_GRID_EVIDENCE_SCHEMA_VERSION: Final = _reference.GRID_EVIDENCE_SCHEMA_VERSION
V6_PAYLOAD_CAP_BYTES: Final = _reference.PAYLOAD_CAP_BYTES

GridEvidenceRegistry = _reference.GridEvidenceRegistry
AuditCounterState = _v5.AuditCounterState
PipelineAuditResult = _v5.PipelineAuditResult


class V6AuditError(RuntimeError):
    """Base class for deterministic v6 scientific-evidence failures."""


class V6GlobalFallbackRequired(V6AuditError):
    """A defect whose registered disposition is the complete 140-row fallback."""

    def __init__(self, stage: str, *, candidate_payload_size_bytes: int | None = None) -> None:
        super().__init__(stage)
        self.stage = stage
        self.candidate_payload_size_bytes = candidate_payload_size_bytes


@dataclass(frozen=True, slots=True)
class RevalidatedPipeline:
    """V5-derived non-grid evidence plus independently decoded prediction grids."""

    v5: Any
    predictions: Mapping[Action, tuple[Prediction | None, ...]]


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Use the reference module's sole canonical representation."""

    return _reference.canonical_json_bytes(value)


def canonical_sha256(value: JsonValue) -> str:
    return _reference.canonical_sha256(value)


def _action_json(action: Action | None) -> JsonValue:
    return _v5._action_json(action)


def _pipeline_json(
    result: PipelineAuditResult,
    *,
    grid_registry: GridEvidenceRegistry,
) -> dict[str, JsonValue]:
    """Serialize one pipeline while registering every prediction grid exactly once."""

    payload = _v5._pipeline_json(result)
    planning = payload.get("planning")
    if not isinstance(planning, dict):
        raise V6AuditError("v5 pipeline serialization omitted planning evidence")
    rows = planning.get("rows")
    if not isinstance(rows, list) or len(rows) != len(result.snapshot.actions):
        raise V6AuditError("v5 planning rows differ from the snapshot action inventory")
    for action, raw_row in zip(result.snapshot.actions, rows, strict=True):
        if not isinstance(raw_row, dict):
            raise V6AuditError("v5 planning row is not a mapping")
        serialized = raw_row.get("predictions")
        predictions = result.snapshot.predictions[action]
        if not isinstance(serialized, list) or len(serialized) != len(predictions):
            raise V6AuditError("v5 prediction serialization differs from the snapshot")
        enriched: list[JsonValue] = []
        for prediction, raw_prediction in zip(predictions, serialized, strict=True):
            reference = grid_registry.add_prediction(prediction)
            if prediction is None:
                if raw_prediction is not None or reference is not None:
                    raise V6AuditError("null prediction acquired non-null grid evidence")
                enriched.append(None)
                continue
            if not isinstance(raw_prediction, dict) or reference is None:
                raise V6AuditError("non-null prediction lacks primitive evidence")
            enriched.append({**raw_prediction, "grid_evidence_ref": reference})
        raw_row["predictions"] = enriched
    return payload


def _strip_grid_references(value: object) -> object:
    """Return the exact frozen-v5 pipeline shape without mutating v6 evidence."""

    copied = copy.deepcopy(value)
    if not isinstance(copied, dict):
        return copied
    planning = copied.get("planning")
    if not isinstance(planning, dict):
        return copied
    rows = planning.get("rows")
    if not isinstance(rows, list):
        return copied
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue
        predictions = raw_row.get("predictions")
        if not isinstance(predictions, list):
            continue
        stripped: list[object] = []
        for prediction in predictions:
            if isinstance(prediction, dict):
                item = dict(prediction)
                item.pop("grid_evidence_ref", None)
                stripped.append(item)
            else:
                stripped.append(prediction)
        raw_row["predictions"] = stripped
    return copied


def _prediction_references(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    planning = value.get("planning")
    if not isinstance(planning, Mapping):
        return ()
    rows = planning.get("rows")
    if not isinstance(rows, list):
        raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
    references: list[str] = []
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
        predictions = raw_row.get("predictions")
        if not isinstance(predictions, list):
            raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
        for prediction in predictions:
            if prediction is None:
                continue
            if not isinstance(prediction, Mapping):
                raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
            reference = prediction.get("grid_evidence_ref")
            if not isinstance(reference, str):
                raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
            references.append(reference)
    return tuple(references)


def _pipeline_error_comparison(stage: str) -> dict[str, JsonValue]:
    try:
        return _reference.pipeline_error_comparison(stage)
    except _reference.V6ReferenceError as error:
        raise V6AuditError("reference module rejected a registered pipeline stage") from error


def _scene_grid_shape(value: Mapping[str, Any]) -> tuple[int, int]:
    shape = value.get("grid_shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in shape)
    ):
        raise V6AuditError("scene grid shape is malformed")
    rows, columns = cast(tuple[int, int], tuple(shape))
    if not (1 <= rows <= 64 and 1 <= columns <= 64):
        raise V6AuditError("scene grid shape lies outside the prediction domain")
    return rows, columns


def _prepare_transform(
    transform: Mapping[str, Any],
    *,
    source_shape: tuple[int, int],
) -> tuple[Any, Any, dict[str, JsonValue]]:
    """Build the compact contract and prove the manifest map before pipelines run."""

    try:
        contract = _reference.make_transform_contract(transform)
        validated_contract = _reference.validate_transform_contract(contract.as_json())
    except (_reference.TransformContractError, TypeError, ValueError) as error:
        # At this point no registered scientific row exists: this is malformed producer
        # manifest input, not corruption of an address-bound compact row contract.
        raise V6GlobalFallbackRequired("transform_action_map_invalid") from error
    try:
        action_map = _reference.reconstruct_action_map(validated_contract, source_shape)
        _reference.validate_manifest_action_map(
            transform.get("action_map"),
            action_map,
        )
    except (_reference.ActionMapError, TypeError, ValueError) as error:
        raise V6GlobalFallbackRequired("transform_action_map_invalid") from error
    raw_contract = validated_contract.as_json()
    return validated_contract, action_map, raw_contract


def _map_action(action: Action, action_map: Any) -> Action:
    try:
        return _reference.map_action(action, action_map)
    except _reference.ActionMapError as error:
        raise V6AuditError("required action is absent from the registered partial map") from error


def _pair_result_fields(value: Any) -> tuple[list[str], int]:
    if hasattr(value, "reasons") and hasattr(value, "overflow_nonbackground_count"):
        reasons = list(cast(Sequence[str], value.reasons))
        overflow = int(value.overflow_nonbackground_count)
        return reasons, overflow
    if isinstance(value, Mapping):
        raw_reasons = value.get("reasons")
        raw_overflow = value.get("overflow_nonbackground_count")
        if (
            isinstance(raw_reasons, Sequence)
            and not isinstance(raw_reasons, str)
            and (isinstance(raw_overflow, int) and not isinstance(raw_overflow, bool))
        ):
            return [str(item) for item in raw_reasons], raw_overflow
    raise V6AuditError("reference prediction-pair result has an unknown schema")


def _mapped_or_none(action: Action, action_map: Any) -> Action | None:
    try:
        return _reference.map_action(action, action_map)
    except _reference.ActionMapError:
        return None


def _compare_visual_pipelines(
    base: PipelineAuditResult,
    transformed: PipelineAuditResult,
    *,
    contract: Any,
    action_map: Any,
) -> dict[str, JsonValue]:
    """Build the producer's claimed v6 core from live pipeline objects."""

    mapped_pairs = tuple((action, _mapped_or_none(action, action_map)) for action in base.actions)
    mapped_actions = tuple(mapped for _base, mapped in mapped_pairs if mapped is not None)
    unmapped_count = len(mapped_pairs) - len(mapped_actions)
    reasons: list[str] = []
    if unmapped_count:
        reasons.append("required_action_mapping_missing")
    if mapped_actions != transformed.actions:
        reasons.append("mapped_action_frontier_mismatch")
    if base.source_roles != transformed.source_roles:
        reasons.append("compiler_role_mismatch")
    if len(base.snapshot.weights) != len(transformed.snapshot.weights) or any(
        not isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(
            base.snapshot.weights,
            transformed.snapshot.weights,
            strict=False,
        )
    ):
        reasons.append("gibbs_weight_mismatch")

    prediction_pair_count = 0
    overflow_count = 0
    rolewise_cost_mismatch = False
    for base_action, mapped_action in mapped_pairs:
        if mapped_action is None or mapped_action not in transformed.snapshot.costs:
            continue
        base_costs = base.snapshot.costs[base_action]
        transformed_costs = transformed.snapshot.costs[mapped_action]
        if len(base_costs) != len(transformed_costs):
            rolewise_cost_mismatch = True
        base_predictions = base.snapshot.predictions[base_action]
        transformed_predictions = transformed.snapshot.predictions[mapped_action]
        for index in range(min(len(base_costs), len(transformed_costs))):
            if not isclose(
                float(base_costs[index]),
                float(transformed_costs[index]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                rolewise_cost_mismatch = True
            prediction_pair_count += 1
            pair = _reference.compare_prediction_pair(
                base_predictions[index],
                transformed_predictions[index],
                contract,
            )
            pair_reasons, pair_overflow = _pair_result_fields(pair)
            reasons.extend(pair_reasons)
            overflow_count += pair_overflow
    if rolewise_cost_mismatch:
        reasons.append("rolewise_cost_mismatch")

    base_rows = _v5._selection_by_action(base.selection)
    transformed_rows = _v5._selection_by_action(transformed.selection)
    numeric_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    exact_fields = (
        "outcome_cell_count",
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
    )
    numeric_mismatch = False
    disposition_mismatch = False
    for base_action, mapped_action in mapped_pairs:
        if mapped_action is None or mapped_action not in transformed_rows:
            continue
        left = base_rows[base_action]
        right = transformed_rows[mapped_action]
        numeric_mismatch = numeric_mismatch or any(
            not isclose(
                float(getattr(left, field_name)),
                float(getattr(right, field_name)),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for field_name in numeric_fields
        )
        disposition_mismatch = disposition_mismatch or any(
            getattr(left, field_name) != getattr(right, field_name) for field_name in exact_fields
        )
    if numeric_mismatch:
        reasons.append("selector_numeric_diagnostic_mismatch")
    if disposition_mismatch:
        reasons.append("selector_disposition_or_rank_mismatch")

    decision_mismatch = False
    for left, right in (
        (base.selection.m_decision, transformed.selection.m_decision),
        (base.selection.x_decision, transformed.selection.x_decision),
    ):
        mapped_decision = _mapped_or_none(left.action, action_map)
        mapped_probe = (
            None
            if left.probe_candidate is None
            else _mapped_or_none(left.probe_candidate, action_map)
        )
        if (
            mapped_decision != right.action
            or mapped_probe != right.probe_candidate
            or left.mode != right.mode
            or left.gate_reason != right.gate_reason
            or not isclose(left.score, right.score, rel_tol=1e-12, abs_tol=1e-12)
        ):
            decision_mismatch = True
    if decision_mismatch:
        reasons.append("mapped_controller_decision_mismatch")

    action_sets = (
        (
            "mapped_robust_exploitation_set_mismatch",
            _v5._exploit_minimizers(base.selection),
            _v5._exploit_minimizers(transformed.selection),
        ),
        (
            "mapped_myopic_utility_set_mismatch",
            base.selection.m_utility_maximizers,
            transformed.selection.m_utility_maximizers,
        ),
        (
            "mapped_cross_level_utility_set_mismatch",
            base.selection.x_utility_maximizers,
            transformed.selection.x_utility_maximizers,
        ),
    )
    for reason, left_actions, right_actions in action_sets:
        mapped_set = {
            mapped
            for action in left_actions
            if (mapped := _mapped_or_none(action, action_map)) is not None
        }
        if mapped_set != set(right_actions):
            reasons.append(reason)

    mapped_exploit = _mapped_or_none(base.selection.exploit.action, action_map)
    if (
        mapped_exploit != transformed.selection.exploit.action
        or not isclose(
            base.selection.exploit.mean_cost,
            transformed.selection.exploit.mean_cost,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.standard_deviation,
            transformed.selection.exploit.standard_deviation,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.score,
            transformed.selection.exploit.score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    ):
        reasons.append("mapped_robust_exploitation_result_mismatch")

    ordered_reasons = [reason for reason in _reference.REASON_ORDER if reason in reasons]
    core = _reference.make_comparison_core(
        mapped_action_count=len(mapped_actions),
        unmapped_action_count=unmapped_count,
        prediction_pair_count=prediction_pair_count,
        overflow_nonbackground_count=overflow_count,
        reasons=ordered_reasons,
    )
    return _reference.finalize_evaluated_comparison(core, core)


def evaluate_scene_record(
    scene: Mapping[str, Any],
    *,
    config: SystemConfig,
    counters: AuditCounterState,
    order_transform_maps: Sequence[Mapping[str, Any]],
    require_linux_memory: bool,
    deadline: float,
    grid_registry: GridEvidenceRegistry,
) -> tuple[dict[str, JsonValue], ...]:
    """Produce one v6 base row, four visual rows, and five order rows.

    All transform contracts and full manifest action maps are admitted before the first
    compiler call.  A defect therefore has the preregistered global-fallback disposition
    and cannot leave a partially evaluated scene.
    """

    family, family_index, scene_id = _v5._scene_identity(scene)
    if scene.get("generation_status") != "complete" or scene.get("scope") not in {
        "registered",
        "open_design",
    }:
        raise ValueError("v6 audit requires a complete registered or open-gate scene")
    base_scene = scene.get("base_scene")
    visual_transforms = scene.get("visual_transforms")
    if not isinstance(base_scene, Mapping) or not isinstance(visual_transforms, list):
        raise ValueError("complete scene lacks base/visual records")
    if (
        tuple(
            transform.get("name") if isinstance(transform, Mapping) else None
            for transform in visual_transforms
        )
        != _v5.SEALED_VISUAL_TRANSFORM_NAMES
    ):
        raise ValueError("visual transform set/order differs from preregistration")
    source_shape = _scene_grid_shape(base_scene)
    prepared_transforms: list[tuple[Mapping[str, Any], Any, Any, dict[str, JsonValue]]] = []
    for raw_transform in visual_transforms:
        if not isinstance(raw_transform, Mapping):
            raise V6GlobalFallbackRequired("transform_action_map_invalid")
        contract, action_map, contract_json = _prepare_transform(
            raw_transform,
            source_shape=source_shape,
        )
        prepared_transforms.append((raw_transform, contract, action_map, contract_json))

    base: PipelineAuditResult | None = None
    base_pipeline_payload: dict[str, JsonValue] | None = None
    base_pipeline_failure: Exception | None = None
    try:
        _v5._require_before_deadline(deadline)
        completed_base = _v5.evaluate_compiler_planner_snapshot(
            _v5._scene_history(base_scene, base_scene),
            config=config,
            counters=counters,
            exercise_controllers=True,
        )
        base_pipeline_payload = _pipeline_json(
            completed_base,
            grid_registry=grid_registry,
        )
        base = completed_base
    except Exception as error:
        if not counters.scientific_exposure_started:
            raise
        base_pipeline_failure = error

    if base is None:
        structural = _v5._failed_scientific_gate("base_pipeline_failed", base_pipeline_failure)
        mechanism = _v5._failed_scientific_gate("base_pipeline_failed", base_pipeline_failure)
        v4: dict[str, JsonValue] = {
            "causal_exercise": False,
            "failure": _v5._deterministic_stage_failure(
                "base_pipeline_failed", base_pipeline_failure
            ),
            "passes": False,
        }
    else:
        try:
            structural = _v5._structural_gate(
                base,
                require_linux_memory=require_linux_memory,
            )
        except Exception as error:
            structural = _v5._failed_scientific_gate("base_structural_gate_failed", error)
        try:
            mechanism = _v5._mechanism_gate(base.selection, probe_cap_available=True)
        except Exception as error:
            mechanism = _v5._failed_scientific_gate("base_mechanism_gate_failed", error)
        try:
            v4 = _v5._v4_counterfactual(
                base,
                structural_passes=structural["passes"] is True,
                probe_cap_available=True,
                counters=counters,
            )
        except Exception as error:
            v4 = {
                "causal_exercise": False,
                "failure": _v5._deterministic_stage_failure("v4_counterfactual_failed", error),
                "passes": False,
            }
    positive = structural["passes"] is True and mechanism["passes"] is True
    causal = positive and v4["causal_exercise"] is True
    scene_sha256 = cast(str, scene.get("content_sha256"))
    records: list[dict[str, JsonValue]] = [
        {
            "causal_exercise": causal,
            "family": family,
            "family_index": family_index,
            "kind": "base_scene",
            "mechanism_gate": mechanism,
            "pipeline": (
                base_pipeline_payload
                if base_pipeline_payload is not None
                else {
                    "failure": _v5._deterministic_stage_failure(
                        "base_pipeline_failed", base_pipeline_failure
                    ),
                    "status": "failed",
                }
            ),
            "positive_mechanism": positive,
            "scene_content_sha256": scene_sha256,
            "scene_id": scene_id,
            "structural_gate": structural,
            "v4_counterfactual": v4,
        }
    ]

    for transform_index, (
        raw_transform,
        contract,
        action_map,
        contract_json,
    ) in enumerate(prepared_transforms):
        is_scale = transform_index == 3
        transformed: PipelineAuditResult | None = None
        transformed_pipeline_payload: dict[str, JsonValue] | None = None
        transformed_failure: Exception | None = None
        visual_failure_stage = (
            "base_pipeline_unavailable" if is_scale and base is None else ("visual_pipeline_failed")
        )
        if not (is_scale and base is None):
            try:
                supplied_actions = (
                    tuple(_map_action(action, action_map) for action in base.actions)
                    if is_scale and base is not None
                    else None
                )
                _v5._require_before_deadline(deadline)
                completed_transformed = _v5.evaluate_compiler_planner_snapshot(
                    _v5._scene_history(raw_transform, base_scene),
                    config=config,
                    counters=counters,
                    supplied_actions=supplied_actions,
                    exercise_controllers=not is_scale,
                )
                transformed_pipeline_payload = _pipeline_json(
                    completed_transformed,
                    grid_registry=grid_registry,
                )
                transformed = completed_transformed
            except Exception as error:
                if not counters.scientific_exposure_started:
                    raise
                transformed_failure = error
        if transformed is None:
            transformed_structural = _v5._failed_scientific_gate(
                visual_failure_stage,
                transformed_failure,
            )
            comparison = _pipeline_error_comparison(visual_failure_stage)
        else:
            try:
                transformed_structural = _v5._structural_gate(
                    transformed,
                    require_linux_memory=require_linux_memory,
                )
            except Exception as error:
                transformed_structural = _v5._failed_scientific_gate(
                    "visual_structural_gate_failed",
                    error,
                )
            if base is None:
                comparison = _pipeline_error_comparison("base_pipeline_unavailable")
            else:
                comparison = _compare_visual_pipelines(
                    base,
                    transformed,
                    contract=contract,
                    action_map=action_map,
                )
        records.append(
            {
                "comparison": comparison,
                "family": family,
                "family_index": family_index,
                "grid_sha256": cast(str, raw_transform.get("grid_sha256")),
                "kind": "visual_transform",
                "pipeline": (
                    transformed_pipeline_payload
                    if transformed_pipeline_payload is not None
                    else {
                        "failure": _v5._deterministic_stage_failure(
                            visual_failure_stage,
                            transformed_failure,
                        ),
                        "status": "failed",
                    }
                ),
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
                "source_grid_shape": [source_shape[0], source_shape[1]],
                "structural_gate": transformed_structural,
                "transform_content_sha256": cast(
                    str,
                    raw_transform.get("content_sha256"),
                ),
                "transform_contract": contract_json,
                "transform_index": transform_index,
                "transform_name": cast(str, raw_transform.get("name")),
            }
        )

    if base is None:
        order_records = _v5._failed_order_records("base_pipeline_unavailable")
    else:
        try:
            _v5._require_before_deadline(deadline)
            order_records = _v5.evaluate_order_transforms(
                base,
                counters=counters,
                order_transform_maps=order_transform_maps,
                base_positive=positive,
                continue_after_failure=True,
                deadline=deadline,
            )
        except Exception as error:
            if not counters.scientific_exposure_started:
                raise
            order_records = _v5._failed_order_records(
                "order_transform_suite_failed",
                error,
            )
    for order_index, order_record in enumerate(order_records):
        records.append(
            {
                **order_record,
                "family": family,
                "family_index": family_index,
                "order_index": order_index,
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
            }
        )
    if len(records) != 10:
        raise RuntimeError("v6 scene evaluator did not emit exactly ten rows")
    return tuple(records)


def _registered_row_id(record: Mapping[str, Any]) -> str:
    kind = record.get("kind")
    if kind == "control":
        return f"control:{record.get('name')}"
    family = record.get("family")
    family_index = record.get("family_index")
    if kind == "base_scene":
        return f"base:{family}:{family_index}"
    if kind == "visual_transform":
        return f"visual:{family}:{family_index}:{record.get('transform_name')}"
    if kind == "order_transform":
        return f"order:{family}:{family_index}:{record.get('name')}"
    raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")


def _bind_registered_row_inventory(
    records: Sequence[Mapping[str, Any]],
    registration_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, JsonValue]]:
    if len(records) != 140 or len(registration_rows) != 140:
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
    known_kinds = {"base_scene", "visual_transform", "order_transform", "control"}
    if any(record.get("kind") not in known_kinds for record in records):
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
    ordered = [
        *(record for record in records if record.get("kind") == "base_scene"),
        *(record for record in records if record.get("kind") == "visual_transform"),
        *(record for record in records if record.get("kind") == "order_transform"),
        *(record for record in records if record.get("kind") == "control"),
    ]
    if len(ordered) != 140:
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
    bound: list[dict[str, JsonValue]] = []
    seen: set[str] = set()
    for row_index, (raw_record, registered) in enumerate(
        zip(ordered, registration_rows, strict=True)
    ):
        record = dict(raw_record)
        expected_row_id = _registered_row_id(record)
        registered_row_id = registered.get("row_id")
        if (
            registered.get("row_index") != row_index
            or registered.get("kind") != record.get("kind")
            or registered_row_id != expected_row_id
            or expected_row_id in seen
        ):
            raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
        kind = record["kind"]
        if kind == "control":
            matches = registered.get("control_id") == record.get("name")
        elif kind == "base_scene":
            matches = (
                registered.get("family") == record.get("family")
                and registered.get("scene_index") == record.get("family_index")
                and registered.get("fixture_sha256") == record.get("scene_content_sha256")
            )
        else:
            transform_name = (
                record.get("transform_name") if kind == "visual_transform" else record.get("name")
            )
            if kind == "visual_transform":
                registered_shape = registered.get("source_grid_shape")
                if (
                    not isinstance(registered_shape, list)
                    or len(registered_shape) != 2
                    or any(
                        isinstance(item, bool) or not isinstance(item, int)
                        for item in registered_shape
                    )
                    or not all(1 <= cast(int, item) <= 64 for item in registered_shape)
                ):
                    raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
                if (
                    record.get("source_grid_shape") is None
                    and _v5._failed_pipeline_stage(record.get("pipeline")) == "not_completed"
                ):
                    record["source_grid_shape"] = cast(
                        JsonValue,
                        list(cast(list[int], registered_shape)),
                    )
            matches = (
                registered.get("family") == record.get("family")
                and registered.get("scene_index") == record.get("family_index")
                and registered.get("transform") == transform_name
            )
        if not matches:
            raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
        seen.add(expected_row_id)
        existing_registration = record.get("registered_row")
        if existing_registration is not None and existing_registration != dict(registered):
            raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
        if record.get("row_id") not in {None, expected_row_id} or record.get("row_index") not in {
            None,
            row_index,
        }:
            raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
        bound.append(
            {
                **cast(dict[str, JsonValue], record),
                "registered_row": cast(JsonValue, dict(registered)),
                "row_id": expected_row_id,
                "row_index": row_index,
            }
        )
    return bound


def _grid_evidence_json(grid_evidence: object) -> Mapping[str, Any]:
    if isinstance(grid_evidence, GridEvidenceRegistry):
        return cast(Mapping[str, Any], grid_evidence.as_json())
    if not isinstance(grid_evidence, Mapping):
        raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
    return cast(Mapping[str, Any], grid_evidence)


def _all_prediction_references(records: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    references: list[str] = []
    for record in records:
        pipeline = record.get("pipeline")
        if _v5._failed_pipeline_stage(pipeline) is None:
            references.extend(_prediction_references(pipeline))
    return tuple(references)


def _validate_grid_table(
    records: Sequence[Mapping[str, Any]],
    grid_evidence: object,
) -> Mapping[str, Any]:
    references = _all_prediction_references(records)
    try:
        return cast(
            Mapping[str, Any],
            _reference.validate_grid_evidence_table(
                _grid_evidence_json(grid_evidence),
                expected_references=frozenset(references),
            ),
        )
    except (_reference.GridEvidenceTableError, TypeError, ValueError) as error:
        raise V6GlobalFallbackRequired("grid_evidence_table_invalid") from error


def _decode_pipeline_predictions(
    pipeline: Mapping[str, Any],
    grids: Mapping[str, Any],
) -> Mapping[Action, tuple[Prediction | None, ...]]:
    stripped = _strip_grid_references(pipeline)
    v5_evidence = _v5._validate_pipeline_evidence(
        stripped,
        expect_controller_rows=bool(pipeline.get("controller_rows")),
    )
    planning = cast(Mapping[str, Any], pipeline["planning"])
    rows = cast(list[Mapping[str, Any]], planning["rows"])
    predictions: dict[Action, tuple[Prediction | None, ...]] = {}
    for action, row in zip(v5_evidence.actions, rows, strict=True):
        decoded: list[Prediction | None] = []
        raw_predictions = cast(list[object], row["predictions"])
        for raw_prediction in raw_predictions:
            if raw_prediction is None:
                decoded.append(None)
                continue
            if not isinstance(raw_prediction, Mapping):
                raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
            reference = raw_prediction.get("grid_evidence_ref")
            if not isinstance(reference, str) or reference not in grids:
                raise V6GlobalFallbackRequired("grid_evidence_table_invalid")
            try:
                _reference.validate_prediction_grid_reference(
                    reference,
                    grid_bytes_sha256=raw_prediction.get("grid_bytes_sha256"),
                    grid_shape=raw_prediction.get("grid_shape"),
                )
                state = GameState(cast(str, raw_prediction["game_state"]))
                level_delta = cast(int, raw_prediction["level_delta"])
                decoded.append(Prediction(grids[reference], state, level_delta, {}))
            except (
                _reference.GridEvidenceTableError,
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                raise V6GlobalFallbackRequired("grid_evidence_table_invalid") from error
        predictions[action] = tuple(decoded)
    return MappingProxyType(predictions)


def _pipeline_view(
    pipeline: Mapping[str, Any],
    grids: Mapping[str, Any],
    *,
    expect_controller_rows: bool,
) -> Any:
    stripped = _strip_grid_references(pipeline)
    evidence = _v5._validate_pipeline_evidence(
        stripped,
        expect_controller_rows=expect_controller_rows,
    )
    predictions = _decode_pipeline_predictions(pipeline, grids)
    snapshot = PlanningSnapshot(
        actions=evidence.actions,
        hypothesis_ids=evidence.snapshot.hypothesis_ids,
        weights=evidence.snapshot.weights,
        predictions=predictions,
        costs=evidence.snapshot.costs,
        invalid_hypothesis_ids=evidence.snapshot.invalid_hypothesis_ids,
    )

    @dataclass(frozen=True, slots=True)
    class _View:
        actions: tuple[Action, ...]
        source_roles: tuple[str, ...]
        snapshot: PlanningSnapshot
        selection: Any

    return _View(
        actions=evidence.actions,
        source_roles=evidence.source_roles,
        snapshot=snapshot,
        selection=evidence.selection,
    )


_COMPARISON_CORE_KEYS: Final = (
    "mapped_action_count",
    "unmapped_action_count",
    "prediction_pair_count",
    "overflow_nonbackground_count",
    "reasons",
    "passes",
)
_FINAL_COMPARISON_KEYS: Final = frozenset(
    {
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
)


def _comparison_core(value: Mapping[str, Any]) -> dict[str, JsonValue]:
    if not all(key in value for key in _COMPARISON_CORE_KEYS):
        raise _reference.ComparisonSchemaError("comparison core is incomplete")
    return cast(
        dict[str, JsonValue],
        {key: value[key] for key in _COMPARISON_CORE_KEYS},
    )


def _claimed_comparison_core(value: object) -> dict[str, JsonValue]:
    """Recover the producer claim from an exact evaluated or parity-terminal row."""

    if not isinstance(value, Mapping) or set(value) != _FINAL_COMPARISON_KEYS:
        raise _reference.ComparisonSchemaError("final comparison schema is not exact")
    if value.get("semantics_id") != V6_VISUAL_SEMANTICS_ID:
        raise _reference.ComparisonSchemaError("final comparison semantics identity differs")
    if value.get("status") == "evaluated" and value.get("parity") is None:
        return _reference.validate_comparison_core(_comparison_core(value))
    parity = value.get("parity")
    if (
        value.get("status") == "authoritative_derivation_error"
        and value.get("reasons") == ["comparison_parity_mismatch"]
        and isinstance(parity, Mapping)
        and set(parity)
        == {
            "claimed",
            "authoritative",
            "claimed_sha256",
            "authoritative_sha256",
        }
    ):
        claimed = _reference.validate_comparison_core(parity["claimed"])
        authoritative = _reference.validate_comparison_core(parity["authoritative"])
        expected = _reference.finalize_evaluated_comparison(authoritative, claimed)
        if cast(object, dict(value)) != expected:
            raise _reference.ComparisonSchemaError(
                "parity terminal row differs from its preserved comparison cores"
            )
        return claimed
    raise _reference.ComparisonSchemaError(
        "producer comparison is neither evaluated nor a canonical parity terminal"
    )


def _comparison_derivation_error(reason: str) -> dict[str, JsonValue]:
    try:
        return _reference.derivation_error_comparison(reason)
    except _reference.ComparisonSchemaError as error:
        raise V6AuditError("reference rejected a registered derivation reason") from error


def _registered_transform_contract_sha256(row: Mapping[str, Any]) -> str | None:
    registered = row.get("registered_row")
    if not isinstance(registered, Mapping):
        return None
    value = registered.get("transform_contract_sha256")
    if value is None:
        return None
    if not isinstance(value, str):
        raise _reference.TransformContractError(
            "registered transform-contract digest is not a string"
        )
    return value


def _registered_source_grid_shape(row: Mapping[str, Any]) -> tuple[int, int]:
    """Read the observation-frame shape, never an arbitrary predicted-grid shape."""

    raw_shape = row.get("source_grid_shape")
    if (
        not isinstance(raw_shape, list)
        or len(raw_shape) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in raw_shape)
    ):
        raise _reference.TransformContractError("visual row source-grid shape is malformed")
    rows, columns = cast(tuple[int, int], tuple(raw_shape))
    if not 1 <= rows <= 64 or not 1 <= columns <= 64:
        raise _reference.TransformContractError(
            "visual row source-grid shape lies outside the finite domain"
        )
    registered = row.get("registered_row")
    if not isinstance(registered, Mapping):
        raise _reference.TransformContractError(
            "visual row lacks its registered source-grid shape binding"
        )
    registered_shape = registered.get("source_grid_shape")
    if registered_shape != raw_shape:
        raise _reference.TransformContractError(
            "visual row source-grid shape differs from registration"
        )
    return rows, columns


def _authoritative_visual_comparison(
    base_view: Any,
    transformed_view: Any,
    *,
    row: Mapping[str, Any],
) -> dict[str, JsonValue]:
    """Rederive a finalized comparison solely from serialized primitive evidence."""

    contract = _reference.validate_transform_contract(
        row.get("transform_contract"),
        expected_sha256=_registered_transform_contract_sha256(row),
    )
    action_map = _reference.reconstruct_action_map(
        contract,
        _registered_source_grid_shape(row),
    )
    return _compare_visual_pipelines(
        base_view,
        transformed_view,
        contract=contract,
        action_map=action_map,
    )


def _validate_completed_visual(
    row: dict[str, JsonValue],
    *,
    base_v5: Any | None,
    base_view: Any | None,
    grids: Mapping[str, Any],
) -> Any | None:
    pipeline = row.get("pipeline")
    pipeline_stage = _v5._failed_pipeline_stage(pipeline)
    if pipeline_stage is not None:
        if pipeline_stage == "not_completed":
            # The pristine 130-row remainder is deliberately the frozen v5-shaped
            # registration-only inventory.  It contains neither prediction grids nor a
            # compact transform contract.  V6 carries the registered source-frame shape,
            # which is stripped only for this frozen-v5 placeholder revalidation seam.
            legacy_placeholder = dict(row)
            legacy_placeholder.pop("source_grid_shape", None)
            _v5._validate_visual_record_evidence(
                legacy_placeholder,
                base=base_v5,
            )
            return None
        expected = _pipeline_error_comparison(pipeline_stage)
        if row.get("comparison") != expected:
            row["comparison"] = expected
        return None
    if not isinstance(pipeline, Mapping):
        raise ValueError("visual pipeline is malformed")
    transform_index = row.get("transform_index")
    transform_name = row.get("transform_name")
    if (
        isinstance(transform_index, bool)
        or not isinstance(transform_index, int)
        or not 0 <= transform_index < 4
        or transform_name != _v5.SEALED_VISUAL_TRANSFORM_NAMES[transform_index]
    ):
        raise ValueError("visual identity is malformed")
    view = _pipeline_view(
        pipeline,
        grids,
        expect_controller_rows=transform_index != 3,
    )
    structural = _v5._structural_gate_from_evidence(
        _v5._validate_pipeline_evidence(
            _strip_grid_references(pipeline),
            expect_controller_rows=transform_index != 3,
        )
    )
    if row.get("structural_gate") != structural:
        raise ValueError("visual structural gate differs from rederivation")
    if base_view is None:
        expected = _pipeline_error_comparison("base_pipeline_unavailable")
    else:
        try:
            authoritative = _authoritative_visual_comparison(
                base_view,
                view,
                row=row,
            )
        except (_reference.TransformContractError, _reference.ActionMapError):
            row["comparison"] = _comparison_derivation_error("transform_contract_invalid")
            return view
        observed = row.get("comparison")
        authoritative_core = _comparison_core(authoritative)
        try:
            claimed_core = _claimed_comparison_core(observed)
        except _reference.ComparisonSchemaError:
            expected = _comparison_derivation_error("claimed_comparison_schema_invalid")
        else:
            expected = _reference.finalize_evaluated_comparison(
                authoritative_core,
                claimed_core,
            )
    row["comparison"] = cast(JsonValue, expected)
    return view


def validate_and_rederive_scientific_records(
    records: Sequence[Mapping[str, Any]],
    registration_rows: Sequence[Mapping[str, Any]],
    *,
    grid_evidence: object,
) -> list[dict[str, JsonValue]]:
    """Bind and independently rederive the complete v6 scientific inventory."""

    bound = _bind_registered_row_inventory(records, registration_rows)
    grids = _validate_grid_table(bound, grid_evidence)
    bases = [row for row in bound if row["kind"] == "base_scene"]
    visuals = [row for row in bound if row["kind"] == "visual_transform"]
    orders = [row for row in bound if row["kind"] == "order_transform"]
    controls = [row for row in bound if row["kind"] == "control"]
    base_v5: dict[tuple[str, int], Any | None] = {}
    base_views: dict[tuple[str, int], Any | None] = {}
    base_positive: dict[tuple[str, int], bool] = {}
    for row in bases:
        stripped = copy.deepcopy(row)
        stripped["pipeline"] = cast(JsonValue, _strip_grid_references(row["pipeline"]))
        try:
            evidence = _v5._validate_base_record_evidence(stripped)
        except Exception:
            # Addressable schema defects are retained as deterministic terminal rows by
            # higher-level fallback construction; do not roll back sibling scenes here.
            raise
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        base_v5[key] = evidence
        base_positive[key] = row.get("positive_mechanism") is True
        if evidence is None or _v5._failed_pipeline_stage(row["pipeline"]) is not None:
            base_views[key] = None
        else:
            base_views[key] = _pipeline_view(
                cast(Mapping[str, Any], row["pipeline"]),
                grids,
                expect_controller_rows=True,
            )
    for row in visuals:
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        _validate_completed_visual(
            row,
            base_v5=base_v5[key],
            base_view=base_views[key],
            grids=grids,
        )
    for row in orders:
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        _v5._validate_order_record_evidence(
            row,
            base=base_v5[key],
            base_positive=base_positive[key],
        )
    for index, row in enumerate(controls):
        _v5._validate_control_record_evidence(row, control_index=index)
    return bound


def _accumulator_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[ScientificRecordAddress, int]:
    """Build the frozen 140-row address index without introducing v6 global state."""

    try:
        return _v5._accumulator_index(records)
    except (TypeError, ValueError) as error:
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid") from error


def _accumulate_completed_records(
    accumulator: list[dict[str, JsonValue]],
    records: Sequence[Mapping[str, Any]],
    *,
    index: Mapping[ScientificRecordAddress, int],
    completed_indices: set[int],
    grid_evidence: object,
) -> tuple[dict[str, JsonValue], ...]:
    """Atomically retain one v6 batch after full independent grid revalidation.

    Address/inventory and global grid-table defects retain their preregistered global
    disposition and are intentionally raised for the payload layer to materialize the
    complete 140-row fallback.  Addressable scientific failures are finalized by
    :func:`validate_and_rederive_scientific_records` without changing frozen v5 globals.
    """

    if len(accumulator) != 140 or len(index) != 140:
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
    authoritative_index = _accumulator_index(accumulator)
    if dict(index) != authoritative_index or any(
        isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 140
        for value in completed_indices
    ):
        raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")

    staged = [dict(record) for record in accumulator]
    staged_indices: set[int] = set()
    try:
        for raw_record in records:
            try:
                address = _v5._scientific_record_address(raw_record)
            except (TypeError, ValueError) as error:
                raise V6GlobalFallbackRequired("scientific_record_inventory_invalid") from error
            row_index = index.get(address)
            if row_index is None or row_index in completed_indices or row_index in staged_indices:
                raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
            placeholder = accumulator[row_index]
            candidate: dict[str, JsonValue] = {
                **cast(dict[str, JsonValue], dict(raw_record)),
                "registered_row": placeholder["registered_row"],
                "row_id": cast(str, placeholder["row_id"]),
                "row_index": row_index,
            }
            try:
                placeholder_address = _v5._scientific_record_address(placeholder)
                candidate_address = _v5._scientific_record_address(candidate)
            except (TypeError, ValueError) as error:
                raise V6GlobalFallbackRequired("scientific_record_inventory_invalid") from error
            if candidate_address != placeholder_address:
                raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
            candidate_value = json.loads(canonical_json_bytes(candidate))
            if not isinstance(candidate_value, dict):
                raise ValueError("scientific record did not round-trip as a mapping")
            staged[row_index] = cast(dict[str, JsonValue], candidate_value)
            staged_indices.add(row_index)

        registration_rows: list[Mapping[str, Any]] = []
        for row in staged:
            registered_row = row.get("registered_row")
            if not isinstance(registered_row, Mapping):
                raise V6GlobalFallbackRequired("scientific_record_inventory_invalid")
            registration_rows.append(cast(Mapping[str, Any], registered_row))
        validated = validate_and_rederive_scientific_records(
            cast(Sequence[Mapping[str, Any]], staged),
            registration_rows,
            grid_evidence=grid_evidence,
        )
        for row_index in staged_indices:
            accumulator[row_index] = validated[row_index]
        completed_indices.update(staged_indices)
    except V6GlobalFallbackRequired:
        raise
    except Exception as error:
        return (
            _v5._deterministic_finalization_failure(
                "scientific_record_finalization_failed",
                error,
            ),
        )
    return ()
