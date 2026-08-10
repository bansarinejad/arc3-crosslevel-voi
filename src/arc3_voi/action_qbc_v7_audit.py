"""Authoritative action-QBC v7 open diagnostic assembler.

The module is deliberately an overlay.  It borrows the immutable v5 compiler/planner
pipeline and the v6 finite-grid evidence substrate, but owns the v7 primitive boundary,
compound selector accounting, authoritative row derivation, aggregate derivation, and
fail-closed payload construction.  Nothing here is a runtime controller or a capability
gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, TypeAlias, cast

from . import action_qbc_audit as _v5
from . import action_qbc_policy as _policy_module
from . import action_qbc_v6_audit as _v6
from . import action_qbc_v7_reference as _reference
from .action_qbc_lockbox import generate_open_scene
from .action_qbc_policy import (
    ActionQBCSelection,
    action_qbc_policy_sha256,
    select_action_conditional_qbc,
)
from .config import load_config
from .planner import PlanningSnapshot
from .types import Action, ActionKind, Prediction

JsonScalar: TypeAlias = str | int | float | bool | None  # noqa: UP040
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]  # noqa: UP040

TREATMENT_ID: Final = "action-qbc-v7-open-failure-decomposition-v1"
DIAGNOSTIC_SYSTEM_ID: Final = "crosslevel-voi-open-diagnostic-v7"
COMPARISON_SEMANTICS_ID: Final = (
    "action-qbc-v7-boundary-compound-selector-decomposition-v1"
)
REGISTRATION_SCHEMA_VERSION: Final = "action-qbc-v7-open-registration-v1"
SCIENTIFIC_SCHEMA_VERSION: Final = "action-qbc-v7-open-diagnostic-payload-v1"
GRID_EVIDENCE_SCHEMA_VERSION: Final = "action-qbc-v7-grid-evidence-table-v1"
EXTERIOR_SUPPORT_SCHEMA_VERSION: Final = (
    "action-qbc-v7-expected-exterior-support-table-v1"
)
COMPOUND_SELECTOR_VERSION: Final = (
    "action-qbc-v7-compound-selector-2^-40-dense-canonical-v1"
)
PREREGISTRATION_TAG: Final = "prereg-action-qbc-v7-open-failure-decomposition-v1"
OPEN_FREEZE_TAG: Final = "action-qbc-v7-open-diagnostic-freeze-v1"
PREREGISTRATION_COMMIT: Final = "f4a267757a7abbd72bc1aeb86e98811c521bf574"
PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md"
)
PREREGISTRATION_DOCUMENT_SHA256: Final = (
    "fcd284ce499983fcc953f54a9f833e1b6d80a822384768f75cb18948d627a1a7"
)
V6_RESULT_COMMIT: Final = "6a7f6fb25b7e676d6aff5aecaaa26de63e436481"
V6_RESULT_PATH: Final = "artifacts/action_qbc_v6_open_gate_result.json"
V6_RESULT_SHA256: Final = (
    "853394f0b68bddaac9b5c1840e8afa51ffeba444920b132ad45b8d53740c751d"
)
V6_FAILURE_VECTOR_SHA256: Final = (
    "589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055"
)
V6_RESULT_DOCUMENT_SHA256: Final = (
    "a3bf5b20291d1b35f65b7fa20de7b9c6247ba918265eab588c6a34f66ff64c59"
)
RAW_POLICY_SHA256: Final = (
    "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
)
CONTROL_CONTRACT_SHA256: Final = (
    "44d08c5867f0c6842151e371263d2e25cdf550da7199c29801ed8c22f4afb9f7"
)

PAYLOAD_CAP_BYTES: Final = 67_108_864
ABSOLUTE_TOLERANCE: Final = 1e-12
RELATIVE_TOLERANCE: Final = 1e-12
FIXED_QUANTUM_NUMERATOR: Final = 1
FIXED_QUANTUM_DENOMINATOR: Final = 1_099_511_627_776
COMPUTE_DEADLINE_SECONDS: Final = 2_100
WALL_TIME_SECONDS: Final = 2_400
HARD_TIMEOUT_SECONDS: Final = 2_700

ROLE_ORDER: Final = (
    "conservative_evidence",
    "topology_contact",
    "homology_alignment",
    "symmetry_completion",
)
SCENE_FAMILIES: Final = ("homologue", "containment", "reflection")
VISUAL_TRANSFORMS: Final = (
    "palette_bijection",
    "translation_row_plus_3_col_plus_5",
    "translation_row_minus_3_col_minus_5",
    "scale_2_nearest_neighbor",
)
ORDER_TRANSFORMS: Final = (
    "candidate_list_reversal",
    "candidate_list_left_rotation_by_one",
    "hypothesis_list_reversal",
    "hypothesis_list_left_rotation_by_one",
    "serialized_outcome_cell_order_reversal",
)
CONTROL_IDS: Final = (
    "identical_signatures_A1",
    "dominant_mass_Aeq0_8_positive_JX",
    "A_lt_0_8_evsi0",
    "fragmented_cosmetic_evsi0",
    "evsi_0_049",
    "material_positive_JX_A_ge_0_8",
    "inverse_low_global_agreement_A_ge_0_8",
    "unused_rowwise_x_only_X_selects_other_probe",
    "M_positive_eligible_different_from_X",
    "exhausted_probe_cap",
    "catastrophe_makes_JX_nonpositive",
    "final_multiplier_1_M_equals_X",
    "invalid_program_structural_false",
    "timeout_program_structural_false",
    "fewer_than_two_eligible_graded_roles",
    "worker_memory_drift",
    "forbidden_resource_use",
    "boundary_evsi_eq_0_05",
    "cosmetic_refinement_pair",
    "candidate_tie_pair",
)

REASON_ORDER: Final = (
    "no_prepreregistered_observation",
    "base_pipeline_unavailable",
    "transformed_pipeline_unavailable",
    "pipeline_snapshot_invalid",
    "required_action_mapping_missing",
    "mapped_frontier_set_mismatch",
    "mapped_frontier_sequence_mismatch",
    "action_map_not_canonical_order_preserving",
    "compiler_role_mismatch",
    "gibbs_weight_nonfinite",
    "gibbs_weight_mismatch",
    "invalid_root_prediction",
    "prediction_label_outside_palette_domain",
    "scale_output_shape_outside_prediction_domain",
    "transformed_prediction_shape_mismatch",
    "observable_prediction_grid_mismatch",
    "expected_exterior_support_present",
    "prediction_game_state_mismatch",
    "prediction_level_delta_mismatch",
    "rolewise_cost_nonfinite",
    "rolewise_cost_mismatch",
    "raw_selector_numeric_mismatch",
    "raw_selector_eligibility_mismatch",
    "raw_selector_rank_mismatch",
    "raw_selector_set_mismatch",
    "raw_selector_gate_mismatch",
    "raw_selector_decision_mismatch",
    "fixed_selector_key_mismatch",
    "fixed_selector_numeric_mismatch",
    "fixed_selector_eligibility_mismatch",
    "fixed_selector_dense_rank_mismatch",
    "fixed_selector_set_mismatch",
    "fixed_selector_gate_mismatch",
    "fixed_selector_decision_mismatch",
    "isolated_action_map_not_bijective",
    "isolated_action_map_not_canonical_order_preserving",
    "isolated_signature_transform_not_injective",
    "v6_failure_vector_mismatch",
    "prepreregistered_base_observation_mismatch",
    "structural_gate_failed",
    "mechanism_gate_failed",
    "causal_diagnostic_false",
    "order_relation_mismatch",
    "control_expectation_mismatch",
    "resource_counter_mismatch",
    "forbidden_resource_use",
    "not_testable_due_upstream_mismatch",
)
REASON_INDEX: Final = MappingProxyType({name: index for index, name in enumerate(REASON_ORDER)})

GLOBAL_FALLBACK_STAGE_ORDER: Final = (
    "transform_action_map_invalid",
    "scientific_record_inventory_invalid",
    "grid_evidence_table_invalid",
    "expected_exterior_support_table_invalid",
    "evaluator_internal_error",
    "payload_size_limit_exceeded",
)

AGGREGATE_KEYS: Final = (
    "v6_failure_vector_reproduced",
    "v6_failure_vector_observed_sha256",
    "prepreregistered_base_reproduced_count",
    "prepreregistered_base_denominator",
    "base_structural_pass_count",
    "base_structural_denominator",
    "base_mechanism_pass_count",
    "base_mechanism_denominator",
    "base_causal_true_count",
    "base_causal_denominator",
    "translation_prediction_pair_count",
    "translation_fully_equivariant_pair_count",
    "translation_boundary_consistent_censored_pair_count",
    "translation_interior_or_metadata_mismatch_pair_count",
    "translation_invalid_prediction_pair_count",
    "translation_expected_exterior_cell_count",
    "translation_boundary_consistent_exterior_cell_count",
    "translation_mixed_exterior_cell_count",
    "translation_invalid_prediction_exterior_cell_count",
    "frozen_positive_translation_exterior_cell_denominator",
    "frozen_positive_translation_observed_exterior_cell_count",
    "frozen_positive_translation_boundary_consistent_exterior_cell_count",
    "frozen_positive_translation_support_reproduced",
    "primary_compound_scale_reconciliation_count",
    "primary_compound_scale_denominator",
    "primary_compound_scale_reconciliation",
    "extension_compound_scale_reconciliation_count",
    "extension_compound_scale_denominator",
    "isolated_action_relabel_required_count",
    "isolated_action_relabel_pass_count",
    "isolated_signature_pushforward_required_count",
    "isolated_signature_pushforward_pass_count",
    "actual_raw_selector_evaluated_count",
    "actual_raw_selector_pass_count",
    "actual_raw_selector_precondition_failed_count",
    "actual_fixed_selector_evaluated_count",
    "actual_fixed_selector_pass_count",
    "actual_fixed_selector_precondition_failed_count",
    "order_raw_pass_count",
    "order_raw_denominator",
    "order_fixed_pass_count",
    "order_fixed_denominator",
    "control_raw_pass_count",
    "control_raw_denominator",
    "control_fixed_pass_count",
    "control_fixed_denominator",
    "resource_contract_passes",
    "reason_counts",
)

RESOURCE_COUNTER_NAMES: Final = (
    "public_scene_generations",
    "registered_scene_file_reads",
    "candidate_builder_calls",
    "compiler_calls",
    "compiled_programs",
    "grounding_evaluations",
    "hypothesis_pool_constructions",
    "persistent_worker_starts",
    "transient_worker_starts",
    "total_worker_starts",
    "planner_calls",
    "completed_planning_snapshots",
    "controller_calls",
    "controller_snapshot_replays",
    "v4_counterfactual_calls",
    "raw_selector_scene_order_calls",
    "raw_selector_control_calls",
    "fixed_selector_scene_order_calls",
    "fixed_selector_control_calls",
    "isolated_raw_selector_calls",
    "isolated_fixed_selector_calls",
    "pure_selector_calls",
    "model_calls",
    "generated_tokens",
    "gpu_operations",
    "network_calls",
    "environment_actions",
    "reward_observations",
    "rhae_observations",
    "lockbox_path_operations",
    "lockbox_bytes_read",
)
EXPECTED_RESOURCE_COUNTS: Final = MappingProxyType(
    dict(
        zip(
            RESOURCE_COUNTER_NAMES,
            (
                12, 0, 48, 60, 240, 240, 60, 240, 240, 480, 60, 60, 96, 96,
                12, 216, 19, 120, 19, 96, 96, 566, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            ),
            strict=True,
        )
    )
)
FORBIDDEN_RESOURCE_COUNTERS: Final = (
    "environment_actions",
    "generated_tokens",
    "gpu_operations",
    "lockbox_bytes_read",
    "lockbox_path_operations",
    "model_calls",
    "network_calls",
    "reward_observations",
    "rhae_observations",
)

AUTHORIZATION: Final = MappingProxyType(
    {
        "lockbox_generation_authorized": False,
        "sealed_execution_authorized": False,
        "runtime_admission_authorized": False,
        "runtime_v7_enabled": False,
        "final_admission_claimed": False,
    }
)

TOP_LEVEL_KEYS: Final = (
    "schema_version",
    "treatment_id",
    "diagnostic_system_id",
    "comparison_semantics_id",
    "runtime_id",
    "preregistration_identity",
    "v6_negative_identity",
    "registration_identity",
    "execution_identity",
    "resource_counters",
    "grid_evidence",
    "expected_exterior_support",
    "rows",
    "aggregates",
    "diagnostic_complete",
    "scientific_capability_passes",
    "authorization",
    "terminal_fallback_stage",
    "candidate_payload_size_bytes",
)


class V7AuditError(RuntimeError):
    """A deterministic v7 contract violation."""


class GlobalFallbackRequired(V7AuditError):
    """A failure whose frozen disposition replaces all 140 rows."""

    def __init__(self, stage: str, *, candidate_payload_size_bytes: int | None = None) -> None:
        if stage not in GLOBAL_FALLBACK_STAGE_ORDER:
            raise ValueError(f"unregistered global fallback stage: {stage}")
        super().__init__(stage)
        self.stage = stage
        self.candidate_payload_size_bytes = candidate_payload_size_bytes


class AddressableRecordError(V7AuditError):
    """A schema defect localized to one already-valid registered address."""


def canonical_json_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_exact_keys(value: Mapping[str, Any], expected: Iterable[str], name: str) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        raise V7AuditError(f"{name} key mismatch; missing={missing}, extra={extra}")


def _require_json_integer(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise V7AuditError(f"{name} must be a JSON integer")
    if minimum is not None and value < minimum:
        raise V7AuditError(f"{name} must be at least {minimum}")
    return value


def _require_finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V7AuditError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise V7AuditError(f"{name} must be finite")
    return result


def action_json(action: Action | None) -> JsonValue:
    if action is None:
        return None
    return {
        "kind": action.kind.name,
        "row": action.row if action.kind is ActionKind.ACTION6 else None,
        "col": action.col if action.kind is ActionKind.ACTION6 else None,
    }


def action_from_json(value: object, *, shape: tuple[int, int] | None = None) -> Action:
    if not isinstance(value, Mapping):
        raise V7AuditError("action must be an object")
    _require_exact_keys(value, ("kind", "row", "col"), "action")
    kind_value = value.get("kind")
    if not isinstance(kind_value, str) or kind_value not in ActionKind.__members__:
        raise V7AuditError("action kind must be an official uppercase name")
    kind = ActionKind[kind_value]
    if kind is ActionKind.RESET:
        raise V7AuditError("RESET is excluded from v7 scientific actions")
    row = value.get("row")
    col = value.get("col")
    if kind is not ActionKind.ACTION6:
        if row is not None or col is not None:
            raise V7AuditError("simple actions require null coordinates")
        return Action(kind)
    parsed_row = _require_json_integer(row, "action.row", minimum=0)
    parsed_col = _require_json_integer(col, "action.col", minimum=0)
    if shape is not None and not (parsed_row < shape[0] and parsed_col < shape[1]):
        raise V7AuditError("ACTION6 coordinate lies outside the registered grid")
    return Action(kind, row=parsed_row, col=parsed_col)


def tolerance_record(left: object, right: object) -> dict[str, JsonValue]:
    x = _require_finite_number(left, "left value")
    y = _require_finite_number(right, "right value")
    delta = abs(x - y)
    bound = max(ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * max(abs(x), abs(y)))
    return {
        "left": x,
        "right": y,
        "abs_delta": delta,
        "tolerance_bound": bound,
        "passes": delta <= bound,
    }


def binary64_equal(left: object, right: object) -> bool:
    x = _require_finite_number(left, "left binary64 value")
    y = _require_finite_number(right, "right binary64 value")
    return struct.pack(">d", x) == struct.pack(">d", y)


def ordered_reasons(reasons: Iterable[str]) -> list[str]:
    unique = set(reasons)
    unknown = unique - set(REASON_ORDER)
    if unknown:
        raise V7AuditError(f"unknown scientific reason(s): {sorted(unknown)}")
    return [reason for reason in REASON_ORDER if reason in unique]


def layer(
    details: Mapping[str, JsonValue],
    *,
    status: Literal["evaluated", "precondition_failed"] = "evaluated",
    reasons: Iterable[str] = (),
) -> dict[str, JsonValue]:
    selected = ordered_reasons(reasons)
    if status == "precondition_failed" and selected not in (
        ["not_testable_due_upstream_mismatch"],
        ["no_prepreregistered_observation"],
    ):
        raise V7AuditError("precondition-failed layer has a noncanonical reason")
    passes = status == "evaluated" and not selected
    return {
        "status": status,
        "passes": passes,
        "reasons": cast(JsonValue, selected),
        "details": copy.deepcopy(dict(details)),
    }


def default_details(keys: Sequence[str]) -> dict[str, JsonValue]:
    """Return a caller-overridable canonical null default.

    Count/list/Boolean specializations are applied by explicit schemas below; using this
    helper directly is appropriate only for fields whose default is JSON null.
    """

    return {key: None for key in keys}


@dataclass(slots=True)
class ResourceCounterState:
    """One process-local, exact 31-counter ledger."""

    _values: MutableMapping[str, int] = field(
        default_factory=lambda: {name: 0 for name in RESOURCE_COUNTER_NAMES}
    )

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._values:
            raise V7AuditError(f"unknown v7 resource counter: {name}")
        parsed = _require_json_integer(amount, "counter increment", minimum=0)
        if name in {"pure_selector_calls", "total_worker_starts", "fixed_selector_control_calls"}:
            raise V7AuditError(f"derived counter cannot be incremented directly: {name}")
        self._values[name] += parsed

    def observe(self, name: str, amount: int) -> None:
        self.increment(name, amount)

    def set_compound_control_calls(self, value: int) -> None:
        parsed = _require_json_integer(value, "compound control calls", minimum=0)
        self._values["fixed_selector_control_calls"] = parsed

    def merge_legacy(self, legacy: Mapping[str, object]) -> None:
        field_map = {
            "candidate_builder_calls": "candidate_builder_calls",
            "compiler_calls": "compiler_calls",
            "compiled_programs": "compiled_programs",
            "completed_planning_snapshots": "completed_planning_snapshots",
            "controller_calls": "controller_calls",
            "controller_snapshot_replays": "controller_snapshot_replays",
            "environment_actions": "environment_actions",
            "generated_tokens": "generated_tokens",
            "grounding_evaluations": "grounding_evaluations",
            "gpu_operations": "gpu_operations",
            "hypothesis_pool_constructions": "hypothesis_pool_constructions",
            "lockbox_bytes_read": "lockbox_bytes_read",
            "lockbox_path_operations": "lockbox_path_operations",
            "model_calls": "model_calls",
            "network_calls": "network_calls",
            "persistent_worker_starts": "persistent_worker_starts",
            "planner_calls": "planner_calls",
            "pure_selector_control_calls": "raw_selector_control_calls",
            "pure_selector_scene_order_calls": "raw_selector_scene_order_calls",
            "registered_scenes_read": "registered_scene_file_reads",
            "reward_observations": "reward_observations",
            "rhae_observations": "rhae_observations",
            "transient_worker_starts": "transient_worker_starts",
            "v4_counterfactual_calls": "v4_counterfactual_calls",
        }
        required = set(field_map) | {"pure_selector_calls", "total_worker_starts"}
        if set(legacy) != required:
            raise V7AuditError("legacy counter schema differs from the registered adapter")
        parsed = {
            name: _require_json_integer(value, f"legacy.{name}", minimum=0)
            for name, value in legacy.items()
        }
        if parsed["pure_selector_calls"] != (
            parsed["pure_selector_scene_order_calls"] + parsed["pure_selector_control_calls"]
        ):
            raise V7AuditError("legacy pure-selector equation failed")
        if parsed["total_worker_starts"] != (
            parsed["persistent_worker_starts"] + parsed["transient_worker_starts"]
        ):
            raise V7AuditError("legacy worker-start equation failed")
        for source, destination in field_map.items():
            if self._values[destination] != 0:
                raise V7AuditError(f"legacy destination was already populated: {destination}")
            self._values[destination] = parsed[source]

    def snapshot(self) -> dict[str, int]:
        result = dict(self._values)
        result["total_worker_starts"] = (
            result["persistent_worker_starts"] + result["transient_worker_starts"]
        )
        result["pure_selector_calls"] = sum(
            result[name]
            for name in (
                "raw_selector_scene_order_calls",
                "raw_selector_control_calls",
                "fixed_selector_scene_order_calls",
                "fixed_selector_control_calls",
                "isolated_raw_selector_calls",
                "isolated_fixed_selector_calls",
            )
        )
        return {name: result[name] for name in RESOURCE_COUNTER_NAMES}


def validate_resource_counters(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise V7AuditError("resource counters must be an object")
    _require_exact_keys(value, RESOURCE_COUNTER_NAMES, "resource counters")
    parsed = {
        name: _require_json_integer(value[name], f"resource_counters.{name}", minimum=0)
        for name in RESOURCE_COUNTER_NAMES
    }
    if parsed["total_worker_starts"] != (
        parsed["persistent_worker_starts"] + parsed["transient_worker_starts"]
    ):
        raise V7AuditError("total_worker_starts derivation failed")
    if parsed["pure_selector_calls"] != sum(
        parsed[name]
        for name in (
            "raw_selector_scene_order_calls",
            "raw_selector_control_calls",
            "fixed_selector_scene_order_calls",
            "fixed_selector_control_calls",
            "isolated_raw_selector_calls",
            "isolated_fixed_selector_calls",
        )
    ):
        raise V7AuditError("pure_selector_calls derivation failed")
    return parsed


def resource_contract_passes(counters: Mapping[str, int]) -> bool:
    return dict(counters) == dict(EXPECTED_RESOURCE_COUNTS) and all(
        counters[name] == 0 for name in FORBIDDEN_RESOURCE_COUNTERS
    )


_CONTROL_SUBSTITUTION_LOCK: Final = threading.Lock()
_ACTIVE_RESOURCE_STATE: ResourceCounterState | None = None
_ACTIVE_LEGACY_STATE: _v5.AuditCounterState | None = None
_ACTIVE_COMPUTE_DEADLINE: float | None = None


def _begin_resource_accounting() -> tuple[ResourceCounterState, _v5.AuditCounterState]:
    global _ACTIVE_RESOURCE_STATE, _ACTIVE_LEGACY_STATE
    if _ACTIVE_RESOURCE_STATE is not None or _ACTIVE_LEGACY_STATE is not None:
        raise V7AuditError("v7 resource accounting is already active")
    _ACTIVE_RESOURCE_STATE = ResourceCounterState()
    _ACTIVE_LEGACY_STATE = _v5.AuditCounterState()
    return _ACTIVE_RESOURCE_STATE, _ACTIVE_LEGACY_STATE


def _combined_active_resource_snapshot() -> dict[str, int]:
    if _ACTIVE_RESOURCE_STATE is None:
        return {name: 0 for name in RESOURCE_COUNTER_NAMES}
    clone = ResourceCounterState(dict(_ACTIVE_RESOURCE_STATE._values))
    if _ACTIVE_LEGACY_STATE is not None:
        clone.merge_legacy(_ACTIVE_LEGACY_STATE.snapshot())
    return clone.snapshot()


def _end_resource_accounting() -> None:
    global _ACTIVE_COMPUTE_DEADLINE, _ACTIVE_RESOURCE_STATE, _ACTIVE_LEGACY_STATE
    _ACTIVE_RESOURCE_STATE = None
    _ACTIVE_LEGACY_STATE = None
    _ACTIVE_COMPUTE_DEADLINE = None

REGISTRATION_TOP_LEVEL_KEYS: Final = (
    "schema_version",
    "status",
    "treatment_id",
    "diagnostic_system_id",
    "comparison_semantics_id",
    "runtime_id",
    "preregistration",
    "v6_negative",
    "platform",
    "dependencies",
    "source_manifest",
    "scene_inventory",
    "row_inventory",
    "transform_contracts",
    "scientific_contract",
    "resource_contract",
    "execution_contract",
    "authorization",
    "content_sha256",
)


def _resolved_member(root: Path, path: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    candidate = path if path.is_absolute() else resolved_root / path
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise V7AuditError("path escapes the repository root") from error
    return resolved


def load_registration(
    repository_root: Path | str, registration_path: Path | str
) -> dict[str, JsonValue]:
    """Load and byte-validate the independently reconstructible registration."""

    root = Path(repository_root)
    supplied = Path(registration_path)
    path = _resolved_member(root, supplied)
    if path.is_symlink() or not path.is_file():
        raise V7AuditError("registration must be one plain file")
    raw = path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        raise V7AuditError("registration is empty or has a final line feed")
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise V7AuditError("registration is not canonical UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise V7AuditError("registration must be a JSON object")
    typed = cast(dict[str, JsonValue], parsed)
    _require_exact_keys(typed, REGISTRATION_TOP_LEVEL_KEYS, "registration")
    if canonical_json_bytes(typed) != raw:
        raise V7AuditError("registration bytes are not canonical JSON")
    content = dict(typed)
    claimed = content.pop("content_sha256")
    if not isinstance(claimed, str) or claimed != canonical_sha256(cast(JsonValue, content)):
        raise V7AuditError("registration content hash mismatch")
    if typed["schema_version"] != REGISTRATION_SCHEMA_VERSION:
        raise V7AuditError("registration schema version mismatch")
    if typed["status"] != "registered_zero_result":
        raise V7AuditError("registration is not a zero-result freeze")
    if typed["treatment_id"] != TREATMENT_ID:
        raise V7AuditError("registration treatment mismatch")
    if typed["diagnostic_system_id"] != DIAGNOSTIC_SYSTEM_ID:
        raise V7AuditError("registration diagnostic-system mismatch")
    if typed["comparison_semantics_id"] != COMPARISON_SEMANTICS_ID:
        raise V7AuditError("registration comparison-semantics mismatch")
    if typed["runtime_id"] is not None:
        raise V7AuditError("v7 registration must have null runtime identity")
    if typed["authorization"] != dict(AUTHORIZATION):
        raise V7AuditError("registration authorization boundary mismatch")
    _validate_registration_contracts(typed)
    return typed


def _validate_registration_contracts(registration: Mapping[str, JsonValue]) -> None:
    scientific = registration.get("scientific_contract")
    resource = registration.get("resource_contract")
    rows = registration.get("row_inventory")
    if not isinstance(scientific, Mapping):
        raise V7AuditError("registration lacks scientific contract")
    if scientific.get("role_order") != list(ROLE_ORDER):
        raise V7AuditError("registered role order mismatch")
    if scientific.get("reason_order") != list(REASON_ORDER):
        raise V7AuditError("registered reason order mismatch")
    if scientific.get("aggregate_keys") != list(AGGREGATE_KEYS):
        raise V7AuditError("registered aggregate-key order mismatch")
    if scientific.get("global_fallback_stage_order") != list(GLOBAL_FALLBACK_STAGE_ORDER):
        raise V7AuditError("registered fallback precedence mismatch")
    if scientific.get("payload_cap_bytes") != PAYLOAD_CAP_BYTES:
        raise V7AuditError("registered payload cap mismatch")
    if scientific.get("fixed_quantum_numerator") != FIXED_QUANTUM_NUMERATOR or scientific.get(
        "fixed_quantum_denominator"
    ) != FIXED_QUANTUM_DENOMINATOR:
        raise V7AuditError("registered compound quantum mismatch")
    if not isinstance(resource, Mapping):
        raise V7AuditError("registration lacks resource contract")
    if resource.get("expected_counts") != dict(EXPECTED_RESOURCE_COUNTS):
        raise V7AuditError("registered resource-count vector mismatch")
    if resource.get("control_contract_sha256") != CONTROL_CONTRACT_SHA256:
        raise V7AuditError("registered control contract mismatch")
    if not isinstance(rows, Mapping) or rows.get("count") != 140:
        raise V7AuditError("registration row inventory must contain 140 rows")
    _registered_rows(registration)


def _registered_rows(registration: Mapping[str, JsonValue]) -> tuple[dict[str, JsonValue], ...]:
    inventory = registration.get("row_inventory")
    if not isinstance(inventory, Mapping):
        raise V7AuditError("row inventory is not an object")
    raw_rows = inventory.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != 140:
        raise V7AuditError("row inventory length mismatch")
    result: list[dict[str, JsonValue]] = []
    seen_ids: set[str] = set()
    expected_kinds = (
        ("base_scene", 12),
        ("visual_transform", 48),
        ("order_transform", 60),
        ("control", 20),
    )
    flattened_kinds = tuple(kind for kind, count in expected_kinds for _ in range(count))
    for index, value in enumerate(raw_rows):
        if not isinstance(value, dict):
            raise V7AuditError("registered row is not an object")
        row: dict[str, JsonValue] = value
        if row.get("row_index") != index or row.get("kind") != flattened_kinds[index]:
            raise V7AuditError("registered row index/kind order mismatch")
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or not row_id or row_id in seen_ids:
            raise V7AuditError("registered row ID is missing or duplicated")
        if row.get("registered_placeholder") is not True:
            raise V7AuditError("registered row lacks its zero-result placeholder")
        seen_ids.add(row_id)
        result.append(copy.deepcopy(row))
    return tuple(result)


def _row_address(registered_row: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "row_index": cast(int, registered_row["row_index"]),
        "row_id": cast(str, registered_row["row_id"]),
        "kind": cast(str, registered_row["kind"]),
    }


def _validate_address(value: object, registered_row: Mapping[str, JsonValue]) -> None:
    if not isinstance(value, Mapping):
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")
    try:
        _require_exact_keys(value, ("row_index", "row_id", "kind"), "row address")
    except V7AuditError as error:
        raise GlobalFallbackRequired("scientific_record_inventory_invalid") from error
    if dict(value) != _row_address(registered_row):
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")


def _registration_file_sha256(repository_root: Path, registration: Mapping[str, JsonValue]) -> str:
    execution = registration.get("execution_contract")
    path_value: object = "artifacts/action_qbc_v7_open_registration.json"
    if isinstance(execution, Mapping):
        # The canonical path is fixed even though execution_contract does not carry a
        # dedicated path member.  Keeping the local variable makes this boundary explicit.
        path_value = "artifacts/action_qbc_v7_open_registration.json"
    path = _resolved_member(repository_root, Path(cast(str, path_value)))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity_objects(
    registration: Mapping[str, JsonValue], repository_root: Path
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]]:
    preregistration = registration.get("preregistration")
    v6_negative = registration.get("v6_negative")
    source_manifest = registration.get("source_manifest")
    execution_contract = registration.get("execution_contract")
    platform_contract = registration.get("platform")
    if not all(
        isinstance(value, Mapping)
        for value in (
            preregistration,
            v6_negative,
            source_manifest,
            execution_contract,
            platform_contract,
        )
    ):
        raise V7AuditError("registration identity contract is malformed")
    prereg = copy.deepcopy(dict(cast(Mapping[str, JsonValue], preregistration)))
    v6 = copy.deepcopy(dict(cast(Mapping[str, JsonValue], v6_negative)))
    content_hash = registration.get("content_sha256")
    if not isinstance(content_hash, str):
        raise V7AuditError("registration content hash is malformed")
    registration_identity: dict[str, JsonValue] = {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "path": "artifacts/action_qbc_v7_open_registration.json",
        "content_sha256": content_hash,
        "file_sha256": _registration_file_sha256(repository_root, registration),
    }
    manifest_hash = cast(Mapping[str, JsonValue], source_manifest).get("manifest_sha256")
    argv_hashes = cast(Mapping[str, JsonValue], execution_contract).get("argv_hashes")
    if not isinstance(manifest_hash, str) or not isinstance(argv_hashes, Mapping):
        raise V7AuditError("registration execution identity is malformed")
    canonical_command = argv_hashes.get("scientific")
    if not isinstance(canonical_command, str):
        raise V7AuditError("scientific command hash is malformed")
    execution_identity: dict[str, JsonValue] = {
        "open_freeze_commit_sha": _git_head(repository_root),
        "open_freeze_tag": OPEN_FREEZE_TAG,
        "source_manifest_sha256": manifest_hash,
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "uv_version": "0.11.28",
        "uv_lock_sha256": hashlib.sha256((repository_root / "uv.lock").read_bytes()).hexdigest(),
        "canonical_command_sha256": canonical_command,
    }
    return prereg, v6, registration_identity, execution_identity


def _git_head(repository_root: Path) -> str:
    head_file = repository_root / ".git" / "HEAD"
    if not head_file.is_file():
        raise V7AuditError("repository HEAD is unavailable")
    head = head_file.read_text(encoding="ascii").strip()
    if head.startswith("ref: "):
        ref = repository_root / ".git" / head[5:]
        if ref.is_file():
            head = ref.read_text(encoding="ascii").strip()
        else:
            packed = repository_root / ".git" / "packed-refs"
            match = None
            if packed.is_file():
                for line in packed.read_text(encoding="ascii").splitlines():
                    if line and not line.startswith(("#", "^")):
                        sha, name = line.split(" ", 1)
                        if name == head[5:]:
                            match = sha
                            break
            if match is None:
                raise V7AuditError("repository HEAD ref cannot be resolved")
            head = match
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise V7AuditError("repository HEAD is not a lowercase commit SHA")
    return head


def _empty_grid_table() -> dict[str, JsonValue]:
    return {"schema_version": GRID_EVIDENCE_SCHEMA_VERSION, "blobs": []}


def _empty_exterior_table() -> dict[str, JsonValue]:
    return {"schema_version": EXTERIOR_SUPPORT_SCHEMA_VERSION, "blobs": []}


def _empty_aggregates(counters: Mapping[str, int]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {name: 0 for name in AGGREGATE_KEYS}
    for name in (
        "v6_failure_vector_reproduced",
        "frozen_positive_translation_support_reproduced",
        "primary_compound_scale_reconciliation",
        "resource_contract_passes",
    ):
        result[name] = False
    result["v6_failure_vector_observed_sha256"] = None
    result.update(
        {
            "prepreregistered_base_denominator": 3,
            "base_structural_denominator": 12,
            "base_mechanism_denominator": 12,
            "base_causal_denominator": 12,
            "frozen_positive_translation_exterior_cell_denominator": 107,
            "primary_compound_scale_denominator": 3,
            "extension_compound_scale_denominator": 9,
            "isolated_action_relabel_required_count": 48,
            "isolated_signature_pushforward_required_count": 48,
            "order_raw_denominator": 60,
            "order_fixed_denominator": 60,
            "control_raw_denominator": 20,
            "control_fixed_denominator": 20,
        }
    )
    reasons = {reason: 0 for reason in REASON_ORDER}
    contract_pass = resource_contract_passes(counters)
    result["resource_contract_passes"] = contract_pass
    if dict(counters) != dict(EXPECTED_RESOURCE_COUNTS):
        reasons["resource_counter_mismatch"] = 1
    if any(counters[name] != 0 for name in FORBIDDEN_RESOURCE_COUNTERS):
        reasons["forbidden_resource_use"] = 1
    result["reason_counts"] = cast(JsonValue, reasons)
    return {name: result[name] for name in AGGREGATE_KEYS}


def _payload_prefix(
    registration: Mapping[str, JsonValue],
    repository_root: Path,
    counters: Mapping[str, int],
) -> dict[str, JsonValue]:
    prereg, v6, registration_identity, execution_identity = _identity_objects(
        registration, repository_root
    )
    return {
        "schema_version": SCIENTIFIC_SCHEMA_VERSION,
        "treatment_id": TREATMENT_ID,
        "diagnostic_system_id": DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": COMPARISON_SEMANTICS_ID,
        "runtime_id": None,
        "preregistration_identity": prereg,
        "v6_negative_identity": v6,
        "registration_identity": registration_identity,
        "execution_identity": execution_identity,
        "resource_counters": cast(JsonValue, dict(counters)),
    }


def build_global_fallback(
    registration: Mapping[str, JsonValue],
    stage: str,
    *,
    candidate_payload_size_bytes: int | None = None,
    repository_root: Path | str = ".",
    resource_counters: Mapping[str, int] | None = None,
) -> dict[str, JsonValue]:
    """Construct and independently validate the exact 140-row global fallback."""

    if stage not in GLOBAL_FALLBACK_STAGE_ORDER:
        raise V7AuditError("unregistered global fallback stage")
    if stage == "payload_size_limit_exceeded":
        if (
            candidate_payload_size_bytes is None
            or candidate_payload_size_bytes <= PAYLOAD_CAP_BYTES
        ):
            raise V7AuditError("size fallback requires the exact oversized candidate size")
    elif candidate_payload_size_bytes is not None:
        raise V7AuditError("candidate size is null outside the size fallback")
    root = Path(repository_root).resolve(strict=True)
    observed = (
        dict(resource_counters)
        if resource_counters is not None
        else _combined_active_resource_snapshot()
    )
    counters = validate_resource_counters(observed)
    status = (
        "evaluator_internal_error"
        if stage == "evaluator_internal_error"
        else "payload_size_limit_exceeded"
        if stage == "payload_size_limit_exceeded"
        else "authoritative_derivation_error"
    )
    rows = [
        {
            "address": _row_address(registered),
            "registered_row": registered,
            "disposition": "terminal_global_negative",
            "evidence": {},
            "terminal": {"status": status, "stage": stage},
        }
        for registered in _registered_rows(registration)
    ]
    payload = {
        **_payload_prefix(registration, root, counters),
        "grid_evidence": _empty_grid_table(),
        "expected_exterior_support": _empty_exterior_table(),
        "rows": rows,
        "aggregates": _empty_aggregates(counters),
        "diagnostic_complete": False,
        "scientific_capability_passes": False,
        "authorization": dict(AUTHORIZATION),
        "terminal_fallback_stage": stage,
        "candidate_payload_size_bytes": candidate_payload_size_bytes,
    }
    typed = cast(dict[str, JsonValue], payload)
    _require_exact_keys(typed, TOP_LEVEL_KEYS, "global fallback")
    if len(canonical_json_bytes(typed)) > PAYLOAD_CAP_BYTES:
        raise V7AuditError("global fallback exceeds the registered payload cap")
    return typed


RAW_SELECTOR_IDENTITY: Final[dict[str, JsonValue]] = {
    "module": "arc3_voi.action_qbc_policy",
    "callable": "select_action_conditional_qbc",
    "policy_version": "action-conditional-outcome-qbc-v1",
    "runtime_version": "crosslevel-voi-runtime-v5",
    "source_bundle_sha256": RAW_POLICY_SHA256,
}
FIXED_SELECTOR_IDENTITY: Final[dict[str, JsonValue]] = {
    "version": COMPOUND_SELECTOR_VERSION,
    "raw_selector_identity": RAW_SELECTOR_IDENTITY,
    "quantum_numerator": FIXED_QUANTUM_NUMERATOR,
    "quantum_denominator": FIXED_QUANTUM_DENOMINATOR,
    "rank_policy": "dense_by_integer_key",
    "tie_set_policy": "complete_integer_key_ties",
    "singleton_tie_break": "canonical_action_order",
    "positive_utility_gate": "integer_key_strictly_greater_than_zero",
}

SCALAR_KEYS: Final = (
    "outcome_concentration",
    "outcome_cell_count",
    "evsi",
    "catastrophe_mass",
    "m_utility",
    "x_utility",
    "eligible",
    "m_rank",
    "x_rank",
    "m_selected",
    "x_selected",
    "exploit_mean_cost",
    "exploit_standard_deviation",
    "exploit_score",
    "m_key",
    "x_key",
    "exploit_key",
)
NUMERIC_COMPARISON_KEYS: Final = (
    "outcome_concentration",
    "outcome_cell_count",
    "evsi",
    "catastrophe_mass",
    "m_utility",
    "x_utility",
    "exploit_mean_cost",
    "exploit_standard_deviation",
    "exploit_score",
)
DECISION_KEYS: Final = ("action", "mode", "score", "gate_reason", "probe_candidate")
SELECTION_DETAIL_KEYS: Final = (
    "selection_sha256",
    "candidate_records",
    "exploit_set",
    "m_maximizer_set",
    "x_maximizer_set",
    "m_decision",
    "x_decision",
)
SELECTOR_RELATION_DETAIL_KEYS: Final = (
    "candidate_records",
    "compared_candidate_count",
    "numeric_mismatch_count",
    "eligibility_mismatch_count",
    "rank_mismatch_count",
    "selected_membership_mismatch_count",
    "set_mismatch_count",
    "gate_mismatch_count",
    "decision_mismatch_count",
    "key_mismatch_count",
    "left_exploit_set",
    "right_exploit_set",
    "left_m_maximizer_set",
    "right_m_maximizer_set",
    "left_x_maximizer_set",
    "right_x_maximizer_set",
    "left_m_decision",
    "right_m_decision",
    "left_x_decision",
    "right_x_decision",
)


def _canonical_actions(actions: Iterable[Action]) -> tuple[Action, ...]:
    return tuple(sorted(set(actions), key=_reference.canonical_action_key))


def _decision_details(decision: object) -> dict[str, JsonValue]:
    action = getattr(decision, "action", None)
    probe_candidate = getattr(decision, "probe_candidate", None)
    mode = getattr(decision, "mode", None)
    gate_reason = getattr(decision, "gate_reason", None)
    score = getattr(decision, "score", None)
    if not isinstance(action, Action) or (
        probe_candidate is not None and not isinstance(probe_candidate, Action)
    ):
        raise V7AuditError("selector decision contains invalid action values")
    if mode not in {"exploit", "probe"} or not isinstance(gate_reason, str):
        raise V7AuditError("selector decision contains invalid mode or gate")
    return {
        "action": action_json(action),
        "mode": mode,
        "score": _require_finite_number(score, "decision score"),
        "gate_reason": gate_reason,
        "probe_candidate": action_json(probe_candidate),
    }


def raw_selection_details(selection: ActionQBCSelection) -> dict[str, JsonValue]:
    """Serialize the immutable raw selector into the exact v7 selection schema."""

    if action_qbc_policy_sha256() != RAW_POLICY_SHA256:
        raise V7AuditError("raw selector source bundle identity drifted")
    details = _reference.selection_details(selection)
    validate_selection_details(details, fixed=False)
    return details


def validate_selection_details(value: object, *, fixed: bool) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise V7AuditError("selection details must be an object")
    _require_exact_keys(value, SELECTION_DETAIL_KEYS, "selection details")
    rows = value.get("candidate_records")
    if not isinstance(rows, list) or not rows:
        raise V7AuditError("selection requires candidate records")
    actions: list[Action] = []
    for raw_record in rows:
        if not isinstance(raw_record, Mapping):
            raise V7AuditError("selection candidate record must be an object")
        _require_exact_keys(raw_record, ("action", "scalars"), "selection candidate")
        action = action_from_json(raw_record.get("action"))
        if action in actions:
            raise V7AuditError("selection candidate action is duplicated")
        actions.append(action)
        scalars = raw_record.get("scalars")
        if not isinstance(scalars, Mapping):
            raise V7AuditError("selection scalar record must be an object")
        _require_exact_keys(scalars, SCALAR_KEYS, "selection scalars")
        for name in NUMERIC_COMPARISON_KEYS:
            if name == "outcome_cell_count":
                _require_json_integer(scalars[name], name, minimum=1)
            else:
                _require_finite_number(scalars[name], name)
        for name in ("eligible", "m_selected", "x_selected"):
            if not isinstance(scalars[name], bool):
                raise V7AuditError(f"{name} must be Boolean")
        for name in ("m_rank", "x_rank"):
            if scalars[name] is not None:
                _require_json_integer(scalars[name], name, minimum=1)
        for name in ("m_key", "x_key", "exploit_key"):
            if fixed:
                _require_json_integer(scalars[name], name)
            elif scalars[name] is not None:
                raise V7AuditError("raw selector comparison keys must be null")
    action_set = set(actions)
    for name in ("exploit_set", "m_maximizer_set", "x_maximizer_set"):
        raw_actions = value.get(name)
        if not isinstance(raw_actions, list):
            raise V7AuditError(f"{name} must be a list")
        decoded = tuple(action_from_json(item) for item in raw_actions)
        if decoded != _canonical_actions(decoded) or not set(decoded) <= action_set:
            raise V7AuditError(f"{name} is not a canonical subset")
    for name in ("m_decision", "x_decision"):
        decision = value.get(name)
        if not isinstance(decision, Mapping):
            raise V7AuditError(f"{name} must be an object")
        _require_exact_keys(decision, DECISION_KEYS, name)
        action = action_from_json(decision.get("action"))
        if action not in action_set or decision.get("mode") not in {"exploit", "probe"}:
            raise V7AuditError(f"{name} is inconsistent with candidate actions")
        _require_finite_number(decision.get("score"), f"{name}.score")
        if not isinstance(decision.get("gate_reason"), str):
            raise V7AuditError(f"{name}.gate_reason must be a string")
        probe = decision.get("probe_candidate")
        if probe is not None and action_from_json(probe) not in action_set:
            raise V7AuditError(f"{name}.probe_candidate is not a candidate")
    selector_identity = FIXED_SELECTOR_IDENTITY if fixed else RAW_SELECTOR_IDENTITY
    core = {
        name: copy.deepcopy(value[name])
        for name in SELECTION_DETAIL_KEYS
        if name != "selection_sha256"
    }
    preimage: dict[str, JsonValue] = {
        "schema_version": "action-qbc-v7-selection-digest-v1",
        "selector_identity": selector_identity,
        **cast(dict[str, JsonValue], core),
    }
    if value.get("selection_sha256") != canonical_sha256(preimage):
        raise V7AuditError("selection digest mismatch")
    return copy.deepcopy(cast(dict[str, JsonValue], dict(value)))


def _action_lookup(records: Sequence[Mapping[str, Any]]) -> dict[Action, Mapping[str, Any]]:
    result: dict[Action, Mapping[str, Any]] = {}
    for record in records:
        action = action_from_json(record.get("action"))
        if action in result:
            raise V7AuditError("selector relation has duplicate candidate action")
        result[action] = record
    return result


def _mapped_action_json(value: JsonValue, action_map: Mapping[Action, Action]) -> JsonValue:
    action = action_from_json(value)
    try:
        return action_json(action_map[action])
    except KeyError as error:
        raise V7AuditError("selector relation action map is incomplete") from error


def _mapped_action_list(value: object, action_map: Mapping[Action, Action]) -> list[JsonValue]:
    if not isinstance(value, list):
        raise V7AuditError("selector action set must be a list")
    return [action_json(action_map[action_from_json(item)]) for item in value]


def selector_relation(
    left: Mapping[str, JsonValue],
    right: Mapping[str, JsonValue],
    *,
    action_map: Mapping[Action, Action],
    fixed: bool,
    exact_binary64: bool,
) -> dict[str, JsonValue]:
    """Compare two independently selected snapshots under one registered action map."""

    left_valid = validate_selection_details(left, fixed=fixed)
    right_valid = validate_selection_details(right, fixed=fixed)
    left_records = cast(list[Mapping[str, Any]], left_valid["candidate_records"])
    right_records = cast(list[Mapping[str, Any]], right_valid["candidate_records"])
    right_by_action = _action_lookup(right_records)
    comparisons: list[dict[str, JsonValue]] = []
    counts = Counter[str]()
    for left_record in left_records:
        action = action_from_json(left_record["action"])
        if action not in action_map or action_map[action] not in right_by_action:
            raise V7AuditError("selector relation candidate map is incomplete")
        mapped = action_map[action]
        right_record = right_by_action[mapped]
        left_scalars = cast(Mapping[str, Any], left_record["scalars"])
        right_scalars = cast(Mapping[str, Any], right_record["scalars"])
        numeric_failures: list[str] = []
        exact_failures: list[str] = []
        for name in NUMERIC_COMPARISON_KEYS:
            if name == "outcome_cell_count":
                passed = left_scalars[name] == right_scalars[name]
            elif exact_binary64:
                passed = binary64_equal(left_scalars[name], right_scalars[name])
            else:
                passed = cast(
                    bool,
                    tolerance_record(left_scalars[name], right_scalars[name])["passes"],
                )
            if not passed:
                numeric_failures.append(name)
        if numeric_failures:
            counts["numeric"] += len(numeric_failures)
        for name in ("eligible",):
            if left_scalars[name] != right_scalars[name]:
                exact_failures.append(name)
                counts["eligibility"] += 1
        for name in ("m_rank", "x_rank"):
            if left_scalars[name] != right_scalars[name]:
                exact_failures.append(name)
                counts["rank"] += 1
        for name in ("m_selected", "x_selected"):
            if left_scalars[name] != right_scalars[name]:
                exact_failures.append(name)
                counts["selected"] += 1
        for name in ("m_key", "x_key", "exploit_key"):
            if left_scalars[name] != right_scalars[name]:
                exact_failures.append(name)
                counts["key"] += 1
        comparisons.append(
            {
                "action": action_json(action),
                "mapped_action": action_json(mapped),
                "left": copy.deepcopy(cast(dict[str, JsonValue], dict(left_scalars))),
                "right": copy.deepcopy(cast(dict[str, JsonValue], dict(right_scalars))),
                "numeric_relation": "exact_binary64" if exact_binary64 else "tolerance",
                "numeric_failures": cast(JsonValue, numeric_failures),
                "exact_failures": cast(JsonValue, exact_failures),
            }
        )
    if len(right_by_action) != len(comparisons):
        raise V7AuditError("selector relation has an extra right candidate")
    set_pairs = (
        ("exploit_set", "left_exploit_set", "right_exploit_set"),
        ("m_maximizer_set", "left_m_maximizer_set", "right_m_maximizer_set"),
        ("x_maximizer_set", "left_x_maximizer_set", "right_x_maximizer_set"),
    )
    details: dict[str, JsonValue] = {
        "candidate_records": cast(JsonValue, comparisons),
        "compared_candidate_count": len(comparisons),
        "numeric_mismatch_count": counts["numeric"],
        "eligibility_mismatch_count": counts["eligibility"],
        "rank_mismatch_count": counts["rank"],
        "selected_membership_mismatch_count": counts["selected"],
        "set_mismatch_count": 0,
        "gate_mismatch_count": 0,
        "decision_mismatch_count": 0,
        "key_mismatch_count": counts["key"],
    }
    for source_name, left_name, right_name in set_pairs:
        left_set = cast(list[JsonValue], left_valid[source_name])
        right_set = cast(list[JsonValue], right_valid[source_name])
        mapped_left = _mapped_action_list(left_set, action_map)
        details[left_name] = copy.deepcopy(left_set)
        details[right_name] = copy.deepcopy(right_set)
        if mapped_left != right_set:
            details["set_mismatch_count"] = cast(int, details["set_mismatch_count"]) + 1
    for variant in ("m", "x"):
        left_name = f"{variant}_decision"
        left_decision = cast(dict[str, JsonValue], left_valid[left_name])
        right_decision = cast(dict[str, JsonValue], right_valid[left_name])
        details[f"left_{variant}_decision"] = copy.deepcopy(left_decision)
        details[f"right_{variant}_decision"] = copy.deepcopy(right_decision)
        if left_decision["gate_reason"] != right_decision["gate_reason"]:
            details["gate_mismatch_count"] = cast(int, details["gate_mismatch_count"]) + 1
        left_probe = left_decision["probe_candidate"]
        mapped_probe = None if left_probe is None else _mapped_action_json(left_probe, action_map)
        score_passes = (
            binary64_equal(left_decision["score"], right_decision["score"])
            if exact_binary64
            else cast(
                bool,
                tolerance_record(left_decision["score"], right_decision["score"])[
                    "passes"
                ],
            )
        )
        if (
            _mapped_action_json(left_decision["action"], action_map) != right_decision["action"]
            or left_decision["mode"] != right_decision["mode"]
            or mapped_probe != right_decision["probe_candidate"]
            or not score_passes
        ):
            details["decision_mismatch_count"] = cast(int, details["decision_mismatch_count"]) + 1
    _require_exact_keys(details, SELECTOR_RELATION_DETAIL_KEYS, "selector relation details")
    reasons: list[str] = []
    prefix = "fixed" if fixed else "raw"
    reason_by_count = (
        ("key_mismatch_count", f"{prefix}_selector_key_mismatch" if fixed else None),
        ("numeric_mismatch_count", f"{prefix}_selector_numeric_mismatch"),
        ("eligibility_mismatch_count", f"{prefix}_selector_eligibility_mismatch"),
        (
            "rank_mismatch_count",
            (
                f"{prefix}_selector_dense_rank_mismatch"
                if fixed
                else "raw_selector_rank_mismatch"
            ),
        ),
        ("selected_membership_mismatch_count", f"{prefix}_selector_set_mismatch"),
        ("set_mismatch_count", f"{prefix}_selector_set_mismatch"),
        ("gate_mismatch_count", f"{prefix}_selector_gate_mismatch"),
        ("decision_mismatch_count", f"{prefix}_selector_decision_mismatch"),
    )
    for count_name, reason in reason_by_count:
        if reason is not None and cast(int, details[count_name]) > 0:
            reasons.append(reason)
    return layer(details, reasons=reasons)


@dataclass(frozen=True, slots=True)
class PipelinePrimitive:
    """One borrowed pipeline result plus its independently computed compound selection."""

    result: _v5.PipelineAuditResult | None
    fixed_selection: _reference.CompoundActionQBCSelection | None
    failure_kind: Literal["unavailable", "invalid"] | None = None

    def __post_init__(self) -> None:
        if self.result is None:
            if self.fixed_selection is not None or self.failure_kind is None:
                raise V7AuditError("failed pipeline primitive is internally inconsistent")
        elif self.fixed_selection is None or self.failure_kind is not None:
            raise V7AuditError("completed pipeline primitive is internally inconsistent")


def _prediction_digest_fields(prediction: Prediction | None) -> dict[str, JsonValue]:
    if prediction is None:
        return {
            "grid_sha256": None,
            "grid_shape": None,
            "game_state": None,
            "level_delta": None,
        }
    try:
        _shape, grid = _reference.canonical_grid_bytes(prediction.next_grid)
    except (AttributeError, TypeError, ValueError, _reference.V7ReferenceError):
        return {
            "grid_sha256": None,
            "grid_shape": None,
            "game_state": None,
            "level_delta": None,
        }
    return {
        "grid_sha256": hashlib.sha256(grid).hexdigest(),
        "grid_shape": [
            int(prediction.next_grid.shape[0]),
            int(prediction.next_grid.shape[1]),
        ],
        "game_state": str(prediction.game_state),
        "level_delta": prediction.level_delta,
    }


def _finite_or_sentinel(value: float) -> JsonValue:
    numeric = float(value)
    if math.isnan(numeric):
        return "nan"
    if numeric == math.inf:
        return "+inf"
    if numeric == -math.inf:
        return "-inf"
    return numeric


def _pipeline_role_index(result: _v5.PipelineAuditResult) -> dict[str, int]:
    role_by_hypothesis: dict[str, str] = {}
    for row in result.program_rows:
        if row.get("selected") is not True:
            continue
        hypothesis_id = row.get("hypothesis_id")
        role = row.get("assigned_role")
        if (
            not isinstance(hypothesis_id, str)
            or not isinstance(role, str)
            or hypothesis_id in role_by_hypothesis
        ):
            raise AddressableRecordError("selected compiler role identity is malformed")
        role_by_hypothesis[hypothesis_id] = role
    if set(role_by_hypothesis) != set(result.snapshot.hypothesis_ids):
        raise AddressableRecordError("selected role map does not cover snapshot hypotheses")
    role_to_index: dict[str, int] = {}
    for index, hypothesis_id in enumerate(result.snapshot.hypothesis_ids):
        role = role_by_hypothesis[hypothesis_id]
        if role not in ROLE_ORDER or role in role_to_index:
            raise AddressableRecordError("pipeline compiler roles are missing or duplicated")
        role_to_index[role] = index
    if set(role_to_index) != set(ROLE_ORDER):
        raise AddressableRecordError("pipeline compiler roles differ from registration")
    return role_to_index


def snapshot_digest_details(result: _v5.PipelineAuditResult) -> dict[str, JsonValue]:
    role_index = _pipeline_role_index(result)
    snapshot = result.snapshot
    if snapshot.actions != result.actions or not snapshot.actions or len(snapshot.actions) > 12:
        raise AddressableRecordError("pipeline candidate sequence is malformed")
    if len(set(snapshot.actions)) != len(snapshot.actions):
        raise AddressableRecordError("pipeline candidate sequence is duplicated")
    if len(result.persistent_worker_rows) != 4:
        raise AddressableRecordError("pipeline does not retain exactly four workers")
    manifest_by_role: dict[str, Mapping[str, Any]] = {}
    for item in result.source_manifest:
        role = item.get("role")
        if not isinstance(role, str) or role in manifest_by_role:
            raise AddressableRecordError("pipeline source manifest has invalid roles")
        manifest_by_role[role] = item
    if set(manifest_by_role) != set(ROLE_ORDER):
        raise AddressableRecordError("pipeline source manifest role set mismatch")
    hypothesis_roles = {
        hypothesis_id: role
        for role, index in role_index.items()
        for hypothesis_id in (snapshot.hypothesis_ids[index],)
    }
    source_sha256_by_role: dict[str, str] = {}
    for role in ROLE_ORDER:
        source_hash = manifest_by_role[role].get("source_sha256")
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            raise AddressableRecordError("pipeline source hash is malformed")
        source_sha256_by_role[role] = source_hash
    try:
        preimage = _reference.build_snapshot_digest_preimage(
            snapshot,
            hypothesis_roles=hypothesis_roles,
            source_sha256_by_role=source_sha256_by_role,
        )
    except _reference.V7ReferenceError as error:
        raise AddressableRecordError("pipeline snapshot digest preimage is invalid") from error
    return {
        "snapshot_sha256": canonical_sha256(preimage),
        "source_roles": preimage["source_roles"],
        "action_count": len(snapshot.actions),
        "role_count": 4,
        "worker_count": len(result.persistent_worker_rows),
    }


def _precondition_details(schema: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return copy.deepcopy(dict(schema))


PIPELINE_DEFAULT: Final[dict[str, JsonValue]] = {
    "snapshot_sha256": None,
    "source_roles": [],
    "action_count": 0,
    "role_count": 0,
    "worker_count": 0,
}
SELECTION_DEFAULT: Final[dict[str, JsonValue]] = {
    "selection_sha256": None,
    "candidate_records": [],
    "exploit_set": [],
    "m_maximizer_set": [],
    "x_maximizer_set": [],
    "m_decision": None,
    "x_decision": None,
}
STRUCTURAL_DEFAULT: Final[dict[str, JsonValue]] = {
    "safe_valid_program_count": 0,
    "behaviorally_distinct_program_count": 0,
    "graded_action_varying_role_count": 0,
    "worker_limit_pass_count": 0,
    "worker_count": 0,
}
MECHANISM_DEFAULT: Final[dict[str, JsonValue]] = {
    "max_evsi": None,
    "max_x_utility": None,
    "required_evsi": None,
    "evsi_shortfall": None,
    "m_mode": None,
    "x_mode": None,
    "m_action": None,
    "x_action": None,
    "exploit_action": None,
}
V4_DEFAULT: Final[dict[str, JsonValue]] = {
    "causal_exercise": False,
    "selected_action": None,
    "selected_evsi": None,
    "selected_x_utility": None,
    "historical_agreement": None,
}
PREOBSERVED_DEFAULT: Final[dict[str, JsonValue]] = {
    "expected": None,
    "observed": None,
    "comparison_passes": False,
}

PREOBSERVED_BASES: Final[dict[str, dict[str, JsonValue]]] = {
    "homologue": {
        "family": "homologue",
        "structural_pass": True,
        "mechanism_pass": False,
        "causal_exercise": False,
        "max_evsi": 0.03546693328437911,
        "max_x_utility": -0.18426053445928048,
        "m_mode": "exploit",
        "x_mode": "exploit",
        "exploit_action": {"kind": "ACTION6", "row": 18, "col": 9},
    },
    "containment": {
        "family": "containment",
        "structural_pass": True,
        "mechanism_pass": False,
        "causal_exercise": False,
        "max_evsi": 0.004654031969443473,
        "max_x_utility": -0.8929572647028001,
        "m_mode": "exploit",
        "x_mode": "exploit",
        "exploit_action": {"kind": "ACTION6", "row": 9, "col": 6},
    },
    "reflection": {
        "family": "reflection",
        "structural_pass": True,
        "mechanism_pass": False,
        "causal_exercise": False,
        "max_evsi": 0.01977963587013498,
        "max_x_utility": -0.5450683749868954,
        "m_mode": "exploit",
        "x_mode": "exploit",
        "exploit_action": {"kind": "ACTION6", "row": 11, "col": 6},
    },
}


def _structural_details(result: _v5.PipelineAuditResult) -> tuple[dict[str, JsonValue], bool]:
    safe = tuple(row for row in result.program_rows if row.get("eligible") is True)
    selected = tuple(row for row in result.program_rows if row.get("selected") is True)
    behavior = {
        canonical_sha256(cast(JsonValue, row.get("behavior_signature"))) for row in selected
    }
    role_index = _pipeline_role_index(result)
    varying = 0
    for role in ROLE_ORDER:
        index = role_index[role]
        values = [float(result.snapshot.costs[action][index]) for action in result.snapshot.actions]
        if (
            values
            and all(math.isfinite(value) for value in values)
            and max(values) - min(values) > 1e-12
        ):
            varying += 1
    transient_rows = [
        cast(Mapping[str, Any], row.get("grounding_worker_memory"))
        for row in result.program_rows
        if isinstance(row.get("grounding_worker_memory"), Mapping)
    ]
    persistent_rows = [
        cast(Mapping[str, Any], row) for row in result.persistent_worker_rows
    ]
    worker_rows = transient_rows + persistent_rows
    worker_passes = sum(1 for row in worker_rows if _v5._worker_memory_valid(row))
    details: dict[str, JsonValue] = {
        "safe_valid_program_count": len(safe),
        "behaviorally_distinct_program_count": len(behavior),
        "graded_action_varying_role_count": varying,
        "worker_limit_pass_count": worker_passes,
        "worker_count": len(worker_rows),
    }
    passed = (
        len(safe) == 4
        and len(selected) == 4
        and len(behavior) == 4
        and varying >= 2
        and not result.snapshot.invalid_hypothesis_ids
        and len(worker_rows) == 8
        and worker_passes == 8
    )
    return details, passed


def _mechanism_details(
    selection: ActionQBCSelection,
) -> tuple[dict[str, JsonValue], bool]:
    rows = tuple(selection.rows)
    max_evsi = max(float(row.evsi) for row in rows)
    max_x = max(float(row.x_utility) for row in rows)
    required = 1.0 / 23.0
    details: dict[str, JsonValue] = {
        "max_evsi": max_evsi,
        "max_x_utility": max_x,
        "required_evsi": required,
        "evsi_shortfall": max(0.0, required - max_evsi),
        "m_mode": selection.m_decision.mode,
        "x_mode": selection.x_decision.mode,
        "m_action": action_json(selection.m_decision.action),
        "x_action": action_json(selection.x_decision.action),
        "exploit_action": action_json(selection.exploit.action),
    }
    passed = (
        selection.m_decision.mode == "exploit"
        and selection.x_decision.mode == "probe"
        and selection.x_decision.score > 0.0
        and any(
            row.x_selected and row.eligible and row.evsi >= 0.05
            for row in rows
        )
    )
    return details, passed


def _v4_details(raw: Mapping[str, Any]) -> tuple[dict[str, JsonValue], bool]:
    selected_action = raw.get("selected_action")
    if isinstance(selected_action, Mapping) and isinstance(selected_action.get("kind"), int):
        raw_kind = cast(int, selected_action.get("kind"))
        kind = ActionKind.coerce(raw_kind)
        action = Action(
            kind,
            row=cast(int | None, selected_action.get("row")),
            col=cast(int | None, selected_action.get("col")),
        )
        selected_action = action_json(action)
    details: dict[str, JsonValue] = {
        "causal_exercise": raw.get("causal_exercise") is True,
        "selected_action": cast(JsonValue, selected_action),
        "selected_evsi": cast(JsonValue, raw.get("selected_evsi")),
        "selected_x_utility": cast(JsonValue, raw.get("selected_x_utility")),
        "historical_agreement": cast(JsonValue, raw.get("agreement")),
    }
    return details, details["causal_exercise"] is True


def _observed_base_record(
    family: str,
    structural_pass: bool,
    mechanism_pass: bool,
    v4_pass: bool,
    mechanism: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    return {
        "family": family,
        "structural_pass": structural_pass,
        "mechanism_pass": mechanism_pass,
        "causal_exercise": v4_pass,
        "max_evsi": mechanism["max_evsi"],
        "max_x_utility": mechanism["max_x_utility"],
        "m_mode": mechanism["m_mode"],
        "x_mode": mechanism["x_mode"],
        "exploit_action": mechanism["exploit_action"],
    }


def _base_preobserved_layer(
    family: str,
    scene_index: int,
    *,
    structural_pass: bool,
    mechanism_pass: bool,
    v4_pass: bool,
    mechanism: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    if scene_index != 0:
        return layer(
            PREOBSERVED_DEFAULT,
            status="precondition_failed",
            reasons=("no_prepreregistered_observation",),
        )
    expected = PREOBSERVED_BASES[family]
    observed = _observed_base_record(
        family, structural_pass, mechanism_pass, v4_pass, mechanism
    )
    passed = True
    for name in ("max_evsi", "max_x_utility"):
        passed = passed and cast(bool, tolerance_record(expected[name], observed[name])["passes"])
    for name in (
        "family",
        "structural_pass",
        "mechanism_pass",
        "causal_exercise",
        "m_mode",
        "x_mode",
        "exploit_action",
    ):
        passed = passed and expected[name] == observed[name]
    details: dict[str, JsonValue] = {
        "expected": copy.deepcopy(expected),
        "observed": observed,
        "comparison_passes": passed,
    }
    return layer(
        details,
        reasons=() if passed else ("prepreregistered_base_observation_mismatch",),
    )


def derive_base_evidence(
    primitive: PipelinePrimitive,
    *,
    family: str,
    scene_index: int,
    legacy_counters: _v5.AuditCounterState | None = None,
) -> dict[str, JsonValue]:
    """Authoritatively derive the seven exact base-row layers."""

    def failed_layers(pipeline_reason: str) -> dict[str, JsonValue]:
        pipeline_layer = layer(PIPELINE_DEFAULT, reasons=(pipeline_reason,))
        precondition_selection = layer(
            SELECTION_DEFAULT,
            status="precondition_failed",
            reasons=("not_testable_due_upstream_mismatch",),
        )
        precondition_structural = layer(
            STRUCTURAL_DEFAULT,
            status="precondition_failed",
            reasons=("not_testable_due_upstream_mismatch",),
        )
        precondition_mechanism = layer(
            MECHANISM_DEFAULT,
            status="precondition_failed",
            reasons=("not_testable_due_upstream_mismatch",),
        )
        precondition_v4 = layer(
            V4_DEFAULT,
            status="precondition_failed",
            reasons=("not_testable_due_upstream_mismatch",),
        )
        precondition_preobserved = layer(
            PREOBSERVED_DEFAULT,
            status="precondition_failed",
            reasons=(
                "not_testable_due_upstream_mismatch"
                if scene_index == 0
                else "no_prepreregistered_observation",
            ),
        )
        return {
            "pipeline": pipeline_layer,
            "raw_selector": precondition_selection,
            "fixed_selector": copy.deepcopy(precondition_selection),
            "structural": precondition_structural,
            "mechanism": precondition_mechanism,
            "v4_counterfactual": precondition_v4,
            "prepreregistered_reproduction": precondition_preobserved,
        }

    if primitive.result is None:
        return failed_layers(
            "base_pipeline_unavailable"
            if primitive.failure_kind == "unavailable"
            else "pipeline_snapshot_invalid"
        )
    result = primitive.result
    try:
        pipeline_details = snapshot_digest_details(result)
    except (AddressableRecordError, _reference.V7ReferenceError):
        return failed_layers("pipeline_snapshot_invalid")
    raw_details = raw_selection_details(result.selection)
    assert primitive.fixed_selection is not None
    fixed_details = _reference.selection_details(primitive.fixed_selection)
    structural_details, structural_pass = _structural_details(result)
    mechanism_details, mechanism_pass = _mechanism_details(result.selection)
    del legacy_counters
    # The counted immutable v4 call occurs in the compute phase.  Finalization performs
    # only this pure authoritative rederivation from the retained snapshot evidence.
    v4_raw = _v5._v4_counterfactual_from_evidence(
        result.snapshot,
        result.selection,
        structural_passes=structural_pass,
        probe_cap_available=True,
    )
    v4_details, v4_pass = _v4_details(v4_raw)
    return {
        "pipeline": layer(pipeline_details),
        "raw_selector": layer(raw_details),
        "fixed_selector": layer(fixed_details),
        "structural": layer(
            structural_details,
            reasons=() if structural_pass else ("structural_gate_failed",),
        ),
        "mechanism": layer(
            mechanism_details,
            reasons=() if mechanism_pass else ("mechanism_gate_failed",),
        ),
        "v4_counterfactual": layer(
            v4_details,
            reasons=() if v4_pass else ("causal_diagnostic_false",),
        ),
        "prepreregistered_reproduction": _base_preobserved_layer(
            family,
            scene_index,
            structural_pass=structural_pass,
            mechanism_pass=mechanism_pass,
            v4_pass=v4_pass,
            mechanism=mechanism_details,
        ),
    }


@dataclass(frozen=True, slots=True)
class TransportPrimitive:
    """One independently selected isolated transport, or its construction defect."""

    snapshot: PlanningSnapshot | None
    raw_selection: ActionQBCSelection | None
    fixed_selection: _reference.CompoundActionQBCSelection | None
    construction_reason: str | None = None


@dataclass(frozen=True, slots=True)
class VisualPrimitive:
    """Primitive inputs from which the authoritative visual layers are derived."""

    base: PipelinePrimitive
    transformed: PipelinePrimitive
    contract: _reference.TransformContract
    actual_action_map: _reference.ReconstructedActionMap
    isolated_action_map: _reference.ReconstructedActionMap
    action_relabel: TransportPrimitive
    signature_pushforward: TransportPrimitive
    raw_transform: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OrderPrimitive:
    """One registered order transformation and its independently selected snapshot."""

    base: PipelinePrimitive
    transform_name: str
    target: str
    order_contract_sha256: str
    permutation_records: tuple[dict[str, JsonValue], ...]
    raw_selection: ActionQBCSelection | None
    fixed_selection: _reference.CompoundActionQBCSelection | None
    construction_error: bool = False


@dataclass(frozen=True, slots=True)
class ControlPrimitive:
    """Opaque source-bound raw and compound control observations."""

    control_id: str
    raw_record: Mapping[str, Any]
    fixed_record: Mapping[str, Any]
    raw_selector_call_count: int
    fixed_selector_call_count: int


PIPELINE_INTEGRITY_DEFAULT: Final[dict[str, JsonValue]] = {
    "base_snapshot_sha256": None,
    "transformed_snapshot_sha256": None,
    "base_available": False,
    "transformed_available": False,
    "base_prediction_occurrence_count": 0,
    "transformed_prediction_occurrence_count": 0,
    "compiler_manifest": [],
}
FRONTIER_DEFAULT: Final[dict[str, JsonValue]] = {
    "action_map_sha256": None,
    "base_action_count": 0,
    "transformed_action_count": 0,
    "mapped_action_count": 0,
    "unmapped_base_action_count": 0,
    "extra_transformed_action_count": 0,
    "set_equal": False,
    "sequence_equal": False,
    "canonical_order_preserving": False,
}
ROLE_WEIGHT_DEFAULT: Final[dict[str, JsonValue]] = {
    "role_records": [],
    "role_count": 0,
    "nonfinite_count": 0,
    "tolerance_mismatch_count": 0,
    "max_abs_delta": None,
}
ROOT_TRANSITION_DEFAULT: Final[dict[str, JsonValue]] = {
    "pair_records": [],
    "prediction_pair_count": 0,
    "valid_prediction_pair_count": 0,
    "fully_equivariant_pair_count": 0,
    "boundary_consistent_censored_pair_count": 0,
    "interior_or_metadata_mismatch_pair_count": 0,
    "invalid_prediction_pair_count": 0,
    "expected_exterior_nonbackground_count": 0,
    "observable_mismatch_cell_count": 0,
    "state_mismatch_count": 0,
    "level_delta_mismatch_count": 0,
}
PLANNER_COST_DEFAULT: Final[dict[str, JsonValue]] = {
    "pair_records": [],
    "cost_pair_count": 0,
    "nonfinite_count": 0,
    "tolerance_mismatch_count": 0,
    "max_abs_delta": None,
}
SELECTOR_RELATION_DEFAULT: Final[dict[str, JsonValue]] = {
    "candidate_records": [],
    "compared_candidate_count": 0,
    "numeric_mismatch_count": 0,
    "eligibility_mismatch_count": 0,
    "rank_mismatch_count": 0,
    "selected_membership_mismatch_count": 0,
    "set_mismatch_count": 0,
    "gate_mismatch_count": 0,
    "decision_mismatch_count": 0,
    "key_mismatch_count": 0,
    "left_exploit_set": [],
    "right_exploit_set": [],
    "left_m_maximizer_set": [],
    "right_m_maximizer_set": [],
    "left_x_maximizer_set": [],
    "right_x_maximizer_set": [],
    "left_m_decision": None,
    "right_m_decision": None,
    "left_x_decision": None,
    "right_x_decision": None,
}
V6_REPRODUCTION_DEFAULT: Final[dict[str, JsonValue]] = {
    "applicable": False,
    "expected_comparison": None,
    "observed_comparison": None,
    "expected_comparison_sha256": None,
    "observed_comparison_sha256": None,
    "comparison_reproduced": False,
    "expected_failure_vector_sha256": None,
    "observed_failure_vector_sha256": None,
}
ORDER_TRANSFORM_DEFAULT: Final[dict[str, JsonValue]] = {
    "order_contract_sha256": None,
    "target": None,
    "permutation_records": [],
}
CONTROL_DEFAULT: Final[dict[str, JsonValue]] = {
    "control_id": None,
    "control_contract_sha256": None,
    "predicate_id": None,
    "selector_call_count": 0,
    "observed": None,
    "observed_sha256": None,
    "predicate_passes": False,
}


def _pipeline_snapshot_details(
    primitive: PipelinePrimitive,
) -> tuple[dict[str, JsonValue] | None, str | None]:
    if primitive.result is None:
        return None, primitive.failure_kind or "invalid"
    try:
        return snapshot_digest_details(primitive.result), None
    except (AddressableRecordError, _reference.V7ReferenceError):
        return None, "invalid"


def _role_source_rows(result: _v5.PipelineAuditResult) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in result.source_manifest:
        role, digest = item.get("role"), item.get("source_sha256")
        if not isinstance(role, str) or not isinstance(digest, str):
            raise AddressableRecordError("compiler source manifest is malformed")
        rows.append({"role": role, "source_sha256": digest})
    return tuple(rows)


def _derive_pipeline_integrity(
    visual: VisualPrimitive,
) -> tuple[dict[str, JsonValue], bool]:
    base_details, base_failure = _pipeline_snapshot_details(visual.base)
    transformed_details, transformed_failure = _pipeline_snapshot_details(visual.transformed)
    reasons: list[str] = []
    if visual.base.result is None:
        reasons.append("base_pipeline_unavailable")
    if visual.transformed.result is None:
        reasons.append("transformed_pipeline_unavailable")
    if base_failure == "invalid" or transformed_failure == "invalid":
        reasons.append("pipeline_snapshot_invalid")
    manifest: list[JsonValue] = []
    if visual.base.result is not None and visual.transformed.result is not None:
        try:
            manifest = list(
                _reference.pair_compiler_roles(
                    _role_source_rows(visual.base.result),
                    _role_source_rows(visual.transformed.result),
                )
            )
        except _reference.V7ReferenceError:
            reasons.append("pipeline_snapshot_invalid")
    details: dict[str, JsonValue] = {
        "base_snapshot_sha256": None if base_details is None else base_details["snapshot_sha256"],
        "transformed_snapshot_sha256": (
            None if transformed_details is None else transformed_details["snapshot_sha256"]
        ),
        "base_available": visual.base.result is not None,
        "transformed_available": visual.transformed.result is not None,
        "base_prediction_occurrence_count": (
            0
            if visual.base.result is None
            else len(visual.base.result.snapshot.actions)
            * len(visual.base.result.snapshot.hypothesis_ids)
        ),
        "transformed_prediction_occurrence_count": (
            0
            if visual.transformed.result is None
            else len(visual.transformed.result.snapshot.actions)
            * len(visual.transformed.result.snapshot.hypothesis_ids)
        ),
        "compiler_manifest": manifest,
    }
    return layer(details, reasons=reasons), not ordered_reasons(reasons)


def _derive_frontier(
    visual: VisualPrimitive,
    *,
    addressable: bool,
) -> tuple[dict[str, JsonValue], _reference.FrontierRelation | None]:
    if not addressable or visual.base.result is None or visual.transformed.result is None:
        return (
            layer(
                FRONTIER_DEFAULT,
                status="precondition_failed",
                reasons=("not_testable_due_upstream_mismatch",),
            ),
            None,
        )
    relation = _reference.compare_frontiers(
        visual.base.result.snapshot.actions,
        visual.transformed.result.snapshot.actions,
        visual.actual_action_map,
    )
    details: dict[str, JsonValue] = {
        "action_map_sha256": visual.actual_action_map.sha256,
        "base_action_count": len(visual.base.result.snapshot.actions),
        "transformed_action_count": len(visual.transformed.result.snapshot.actions),
        "mapped_action_count": len(relation.mapped_actions),
        "unmapped_base_action_count": len(relation.unmapped_base_actions),
        "extra_transformed_action_count": len(relation.extra_transformed_actions),
        "set_equal": relation.set_equal,
        "sequence_equal": relation.sequence_equal,
        "canonical_order_preserving": relation.canonical_order_preserving,
    }
    return layer(details, reasons=relation.reasons), relation


def _derive_role_weights(
    visual: VisualPrimitive,
    *,
    addressable: bool,
) -> tuple[dict[str, JsonValue], bool]:
    if not addressable or visual.base.result is None or visual.transformed.result is None:
        return (
            layer(
                ROLE_WEIGHT_DEFAULT,
                status="precondition_failed",
                reasons=("not_testable_due_upstream_mismatch",),
            ),
            False,
        )
    base, transformed = visual.base.result, visual.transformed.result
    try:
        manifest = _reference.pair_compiler_roles(
            _role_source_rows(base), _role_source_rows(transformed)
        )
        base_index = _pipeline_role_index(base)
        transformed_index = _pipeline_role_index(transformed)
    except (AddressableRecordError, _reference.V7ReferenceError):
        details = copy.deepcopy(ROLE_WEIGHT_DEFAULT)
        return layer(details, reasons=("compiler_role_mismatch",)), False
    records: list[JsonValue] = []
    nonfinite = tolerance_failures = 0
    finite_deltas: list[float] = []
    for manifest_row in manifest:
        role = cast(str, manifest_row["role"])
        left = float(base.snapshot.weights[base_index[role]])
        right = float(transformed.snapshot.weights[transformed_index[role]])
        passes, delta, bound = _reference.tolerance_comparison(left, right)
        finite = math.isfinite(left) and math.isfinite(right)
        nonfinite += int(not finite)
        tolerance_failures += int(finite and not passes)
        if finite:
            finite_deltas.append(delta)
        records.append(
            {
                **manifest_row,
                "base_weight": _reference.numeric_sentinel(left),
                "transformed_weight": _reference.numeric_sentinel(right),
                "abs_delta": delta if finite else None,
                "tolerance_bound": bound if finite else None,
                "passes": passes,
            }
        )
    base_weight_values = tuple(float(value) for value in base.snapshot.weights)
    transformed_weight_values = tuple(float(value) for value in transformed.snapshot.weights)
    normalized = (
        all(value >= 0.0 and math.isfinite(value) for value in base_weight_values)
        and all(
            value >= 0.0 and math.isfinite(value)
            for value in transformed_weight_values
        )
        and _reference.tolerance_comparison(math.fsum(base_weight_values), 1.0)[0]
        and _reference.tolerance_comparison(
            math.fsum(transformed_weight_values), 1.0
        )[0]
    )
    normalization_failure = not normalized
    reasons: list[str] = []
    if nonfinite:
        reasons.append("gibbs_weight_nonfinite")
    if tolerance_failures or normalization_failure:
        reasons.append("gibbs_weight_mismatch")
    details = {
        "role_records": records,
        "role_count": len(records),
        "nonfinite_count": nonfinite,
        "tolerance_mismatch_count": tolerance_failures,
        "max_abs_delta": max(finite_deltas) if finite_deltas else None,
    }
    return layer(details, reasons=reasons), not reasons


def _derive_root_transition(
    visual: VisualPrimitive,
    *,
    addressable: bool,
    grid_registry: _reference.GridEvidenceRegistry,
    support_registry: _reference.ExteriorSupportRegistry,
) -> tuple[dict[str, JsonValue], bool]:
    if not addressable or visual.base.result is None or visual.transformed.result is None:
        return (
            layer(
                ROOT_TRANSITION_DEFAULT,
                status="precondition_failed",
                reasons=("not_testable_due_upstream_mismatch",),
            ),
            False,
        )
    base, transformed = visual.base.result, visual.transformed.result
    try:
        base_index = _pipeline_role_index(base)
        transformed_index = _pipeline_role_index(transformed)
    except AddressableRecordError:
        return layer(ROOT_TRANSITION_DEFAULT, reasons=("compiler_role_mismatch",)), False
    records: list[dict[str, JsonValue]] = []
    reasons: list[str] = []
    transformed_actions = set(transformed.snapshot.actions)
    for action in base.snapshot.actions:
        try:
            mapped = _reference.map_action(action, visual.actual_action_map)
        except _reference.ActionMapError:
            reasons.append("required_action_mapping_missing")
            continue
        if mapped not in transformed_actions:
            reasons.append("required_action_mapping_missing")
            continue
        transformed_position = transformed.snapshot.actions.index(mapped)
        del transformed_position
        for role in ROLE_ORDER:
            pair = _reference.compare_prediction_pair(
                action=action,
                mapped_action=mapped,
                role=role,
                base=base.snapshot.predictions[action][base_index[role]],
                transformed=transformed.snapshot.predictions[mapped][transformed_index[role]],
                contract=visual.contract,
                grid_registry=grid_registry,
                support_registry=support_registry,
            )
            records.append(dict(pair.record))
            reasons.extend(pair.reasons)
    categories = Counter(cast(str, record["category"]) for record in records)
    details: dict[str, JsonValue] = {
        "pair_records": cast(JsonValue, records),
        "prediction_pair_count": len(records),
        "valid_prediction_pair_count": len(records) - categories["invalid_prediction"],
        "fully_equivariant_pair_count": categories["fully_equivariant"],
        "boundary_consistent_censored_pair_count": categories[
            "boundary_consistent_censored"
        ],
        "interior_or_metadata_mismatch_pair_count": categories[
            "interior_or_metadata_mismatch"
        ],
        "invalid_prediction_pair_count": categories["invalid_prediction"],
        "expected_exterior_nonbackground_count": sum(
            cast(int, record["expected_exterior_nonbackground_count"]) for record in records
        ),
        "observable_mismatch_cell_count": sum(
            cast(int, record["observable_mismatch_cell_count"]) for record in records
        ),
        "state_mismatch_count": sum(
            not cast(bool, record["game_state_equal"]) for record in records
        ),
        "level_delta_mismatch_count": sum(
            not cast(bool, record["level_delta_equal"]) for record in records
        ),
    }
    canonical_reasons = ordered_reasons(reasons)
    return layer(details, reasons=canonical_reasons), not canonical_reasons


def _derive_planner_cost(
    visual: VisualPrimitive,
    *,
    addressable: bool,
) -> tuple[dict[str, JsonValue], bool]:
    if not addressable or visual.base.result is None or visual.transformed.result is None:
        return (
            layer(
                PLANNER_COST_DEFAULT,
                status="precondition_failed",
                reasons=("not_testable_due_upstream_mismatch",),
            ),
            False,
        )
    base, transformed = visual.base.result, visual.transformed.result
    try:
        base_index = _pipeline_role_index(base)
        transformed_index = _pipeline_role_index(transformed)
    except AddressableRecordError:
        return layer(PLANNER_COST_DEFAULT, reasons=("compiler_role_mismatch",)), False
    records: list[JsonValue] = []
    reasons: list[str] = []
    nonfinite = mismatches = 0
    deltas: list[float] = []
    for action in base.snapshot.actions:
        try:
            mapped = _reference.map_action(action, visual.actual_action_map)
        except _reference.ActionMapError:
            reasons.append("required_action_mapping_missing")
            continue
        if mapped not in transformed.snapshot.costs:
            reasons.append("required_action_mapping_missing")
            continue
        for role in ROLE_ORDER:
            left = float(base.snapshot.costs[action][base_index[role]])
            right = float(transformed.snapshot.costs[mapped][transformed_index[role]])
            passes, delta, bound = _reference.tolerance_comparison(left, right)
            finite = math.isfinite(left) and math.isfinite(right)
            nonfinite += int(not finite)
            mismatches += int(finite and not passes)
            if finite:
                deltas.append(delta)
            records.append(
                {
                    "action": action_json(action),
                    "mapped_action": action_json(mapped),
                    "role": role,
                    "base_cost": _reference.numeric_sentinel(left),
                    "transformed_cost": _reference.numeric_sentinel(right),
                    "abs_delta": delta if finite else None,
                    "tolerance_bound": bound if finite else None,
                    "passes": passes,
                }
            )
    if nonfinite:
        reasons.append("rolewise_cost_nonfinite")
    if mismatches:
        reasons.append("rolewise_cost_mismatch")
    details: dict[str, JsonValue] = {
        "pair_records": records,
        "cost_pair_count": len(records),
        "nonfinite_count": nonfinite,
        "tolerance_mismatch_count": mismatches,
        "max_abs_delta": max(deltas) if deltas else None,
    }
    canonical_reasons = ordered_reasons(reasons)
    return layer(details, reasons=canonical_reasons), not canonical_reasons


def _selector_relation_layer(
    left: ActionQBCSelection | _reference.CompoundActionQBCSelection,
    right: ActionQBCSelection | _reference.CompoundActionQBCSelection,
    *,
    numeric_relation: Literal["tolerance", "exact_binary64"],
    action_map: _reference.ReconstructedActionMap | None,
) -> dict[str, JsonValue]:
    relation = _reference.compare_selector_selections(
        left,
        right,
        numeric_relation=numeric_relation,
        action_map=action_map,
    )
    return layer(dict(relation.details), reasons=relation.reasons)


def _precondition_selector_relation() -> dict[str, JsonValue]:
    return layer(
        SELECTOR_RELATION_DEFAULT,
        status="precondition_failed",
        reasons=("not_testable_due_upstream_mismatch",),
    )


def _isolated_relation_layer(
    base: PipelinePrimitive,
    transported: TransportPrimitive,
    *,
    fixed: bool,
    action_map: _reference.ReconstructedActionMap,
) -> dict[str, JsonValue]:
    _base_details, base_failure = _pipeline_snapshot_details(base)
    if base.result is None or base_failure is not None:
        return _precondition_selector_relation()
    if transported.construction_reason is not None:
        return layer(
            SELECTOR_RELATION_DEFAULT,
            reasons=(transported.construction_reason,),
        )
    left = base.fixed_selection if fixed else base.result.selection
    right = transported.fixed_selection if fixed else transported.raw_selection
    if left is None or right is None:
        raise V7AuditError("isolated selector primitive is incomplete")
    return _selector_relation_layer(
        left,
        right,
        numeric_relation="exact_binary64",
        action_map=action_map,
    )


def _v6_expected_comparison(
    v6_result: Mapping[str, Any],
    *,
    family: str,
    transform_name: str,
) -> dict[str, JsonValue]:
    failures = v6_result.get("failing_visuals")
    if not isinstance(failures, list):
        raise V7AuditError("frozen v6 failure vector is malformed")
    matches = [
        item
        for item in failures
        if isinstance(item, Mapping)
        and item.get("family") == family
        and item.get("transform_name") == transform_name
    ]
    if len(matches) == 1:
        comparison = matches[0].get("comparison")
        if not isinstance(comparison, Mapping):
            raise V7AuditError("frozen v6 comparison is malformed")
        return copy.deepcopy(cast(dict[str, JsonValue], dict(comparison)))
    if matches:
        raise V7AuditError("frozen v6 comparison is duplicated")
    if transform_name != "palette_bijection":
        raise V7AuditError("frozen v6 result lacks a required failed comparison")
    return {
        "status": "evaluated",
        "semantics_id": "action-qbc-v6-padded-finite-grid-v1",
        "mapped_action_count": 12,
        "unmapped_action_count": 0,
        "prediction_pair_count": 48,
        "overflow_nonbackground_count": 0,
        "reasons": [],
        "passes": True,
        "parity": None,
    }


def _derive_v6_comparison(visual: VisualPrimitive) -> dict[str, JsonValue]:
    if visual.base.result is None or visual.transformed.result is None:
        return {
            "status": "failed",
            "semantics_id": "action-qbc-v6-padded-finite-grid-v1",
            "mapped_action_count": 0,
            "unmapped_action_count": 0,
            "prediction_pair_count": 0,
            "overflow_nonbackground_count": 0,
            "reasons": ["base_pipeline_unavailable"],
            "passes": False,
            "parity": None,
        }
    contract, action_map, _contract_json = _v6._prepare_transform(
        visual.raw_transform,
        source_shape=(32, 32),
    )
    return _v6._compare_visual_pipelines(
        visual.base.result,
        visual.transformed.result,
        contract=contract,
        action_map=action_map,
    )


def derive_visual_evidence(
    visual: VisualPrimitive,
    *,
    family: str,
    scene_index: int,
    transform_name: str,
    v6_result: Mapping[str, Any],
    grid_registry: _reference.GridEvidenceRegistry,
    support_registry: _reference.ExteriorSupportRegistry,
) -> dict[str, JsonValue]:
    """Authoritatively derive all twelve visual-row layers."""

    pipeline_layer, pipeline_pass = _derive_pipeline_integrity(visual)
    addressable = visual.base.result is not None and visual.transformed.result is not None
    frontier_layer, frontier = _derive_frontier(visual, addressable=addressable)
    weight_layer, weight_pass = _derive_role_weights(visual, addressable=addressable)
    root_layer, root_pass = _derive_root_transition(
        visual,
        addressable=addressable,
        grid_registry=grid_registry,
        support_registry=support_registry,
    )
    cost_layer, cost_pass = _derive_planner_cost(visual, addressable=addressable)
    upstream = (
        pipeline_pass
        and frontier is not None
        and frontier.passes
        and weight_pass
        and root_pass
        and cost_pass
    )
    if upstream:
        assert visual.base.result is not None and visual.transformed.result is not None
        assert visual.base.fixed_selection is not None
        assert visual.transformed.fixed_selection is not None
        raw_actual = _selector_relation_layer(
            visual.base.result.selection,
            visual.transformed.result.selection,
            numeric_relation="tolerance",
            action_map=visual.actual_action_map,
        )
        fixed_actual = _selector_relation_layer(
            visual.base.fixed_selection,
            visual.transformed.fixed_selection,
            numeric_relation="tolerance",
            action_map=visual.actual_action_map,
        )
    else:
        raw_actual = _precondition_selector_relation()
        fixed_actual = _precondition_selector_relation()
    action_relabel_raw = _isolated_relation_layer(
        visual.base,
        visual.action_relabel,
        fixed=False,
        action_map=visual.isolated_action_map,
    )
    action_relabel_fixed = _isolated_relation_layer(
        visual.base,
        visual.action_relabel,
        fixed=True,
        action_map=visual.isolated_action_map,
    )
    signature_raw = _isolated_relation_layer(
        visual.base,
        visual.signature_pushforward,
        fixed=False,
        action_map=visual.isolated_action_map,
    )
    signature_fixed = _isolated_relation_layer(
        visual.base,
        visual.signature_pushforward,
        fixed=True,
        action_map=visual.isolated_action_map,
    )
    if scene_index == 0:
        expected = _v6_expected_comparison(
            v6_result, family=family, transform_name=transform_name
        )
        observed = _derive_v6_comparison(visual)
        reproduced = canonical_json_bytes(expected) == canonical_json_bytes(observed)
        v6_details: dict[str, JsonValue] = {
            "applicable": True,
            "expected_comparison": expected,
            "observed_comparison": observed,
            "expected_comparison_sha256": canonical_sha256(expected),
            "observed_comparison_sha256": canonical_sha256(observed),
            "comparison_reproduced": reproduced,
            "expected_failure_vector_sha256": V6_FAILURE_VECTOR_SHA256,
            "observed_failure_vector_sha256": None,
        }
        v6_layer = layer(
            v6_details,
            reasons=() if reproduced else ("v6_failure_vector_mismatch",),
        )
    else:
        v6_details = copy.deepcopy(V6_REPRODUCTION_DEFAULT)
        v6_details["comparison_reproduced"] = True
        v6_layer = layer(v6_details)
    return {
        "pipeline_integrity": pipeline_layer,
        "frontier_relation": frontier_layer,
        "role_weight_relation": weight_layer,
        "root_transition": root_layer,
        "planner_cost": cost_layer,
        "actual_raw_selector": raw_actual,
        "actual_fixed_selector": fixed_actual,
        "isolated_action_relabel_raw": action_relabel_raw,
        "isolated_action_relabel_fixed": action_relabel_fixed,
        "isolated_signature_pushforward_raw": signature_raw,
        "isolated_signature_pushforward_fixed": signature_fixed,
        "v6_reproduction": v6_layer,
    }


def _permutation(rule: str, length: int) -> tuple[int, ...]:
    if length < 0:
        raise V7AuditError("order sequence length cannot be negative")
    if rule == "reverse":
        return tuple(range(length - 1, -1, -1))
    if rule == "left_rotate_one":
        return () if length == 0 else (*tuple(range(1, length)), 0)
    raise V7AuditError("unregistered order permutation rule")


def _derive_order_evidence(
    order: OrderPrimitive,
    registered_row: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    if order.base.result is None:
        failed = layer(
            ORDER_TRANSFORM_DEFAULT,
            status="precondition_failed",
            reasons=("not_testable_due_upstream_mismatch",),
        )
        relation = _precondition_selector_relation()
        return {
            "order_transform": failed,
            "raw_selector_relation": relation,
            "fixed_selector_relation": copy.deepcopy(relation),
        }
    transform_reasons: list[str] = []
    expected_contract = {
        "candidate_list_reversal": ("candidate_sequence", "reverse"),
        "candidate_list_left_rotation_by_one": (
            "candidate_sequence",
            "left_rotate_one",
        ),
        "hypothesis_list_reversal": ("hypothesis_sequence", "reverse"),
        "hypothesis_list_left_rotation_by_one": (
            "hypothesis_sequence",
            "left_rotate_one",
        ),
        "serialized_outcome_cell_order_reversal": (
            "per_action_serialized_outcome_cell_sequence",
            "reverse",
        ),
    }
    registered_name = registered_row.get("transform_name")
    registered_sha = registered_row.get("order_contract_sha256")
    contract_tuple = expected_contract.get(order.transform_name)
    if (
        registered_row.get("kind") != "order_transform"
        or registered_name != order.transform_name
        or not isinstance(registered_sha, str)
        or registered_sha != order.order_contract_sha256
        or contract_tuple is None
        or order.target != contract_tuple[0]
    ):
        transform_reasons.append("order_relation_mismatch")
    if order.construction_error:
        transform_reasons.append("order_relation_mismatch")
    for record in order.permutation_records:
        try:
            _require_exact_keys(
                record,
                ("action", "sequence_length", "output_to_input_permutation"),
                "order permutation record",
            )
            length = _require_json_integer(
                record["sequence_length"], "order sequence length", minimum=0
            )
            permutation = record["output_to_input_permutation"]
            rule = "reverse" if contract_tuple is None else contract_tuple[1]
            if not isinstance(permutation, list) or permutation != list(
                _permutation(rule, length)
            ):
                transform_reasons.append("order_relation_mismatch")
        except V7AuditError:
            transform_reasons.append("order_relation_mismatch")
    expected_record_count = (
        len(order.base.result.snapshot.actions)
        if order.transform_name == "serialized_outcome_cell_order_reversal"
        else 1
    )
    if len(order.permutation_records) != expected_record_count:
        transform_reasons.append("order_relation_mismatch")
    if order.transform_name in {
        "candidate_list_reversal",
        "candidate_list_left_rotation_by_one",
    }:
        expected_actions: list[JsonValue] = [None]
        expected_lengths = [len(order.base.result.snapshot.actions)]
    elif order.transform_name in {
        "hypothesis_list_reversal",
        "hypothesis_list_left_rotation_by_one",
    }:
        expected_actions = [None]
        expected_lengths = [len(order.base.result.snapshot.hypothesis_ids)]
    else:
        expected_actions = [
            action_json(action) for action in order.base.result.snapshot.actions
        ]
        counts_by_action = {
            row.action: row.outcome_cell_count for row in order.base.result.selection.rows
        }
        expected_lengths = [
            counts_by_action[action] for action in order.base.result.snapshot.actions
        ]
    observed_actions = [record.get("action") for record in order.permutation_records]
    observed_lengths = [
        record.get("sequence_length") for record in order.permutation_records
    ]
    if observed_actions != expected_actions or observed_lengths != expected_lengths:
        transform_reasons.append("order_relation_mismatch")
    transform_details: dict[str, JsonValue] = {
        "order_contract_sha256": order.order_contract_sha256,
        "target": order.target,
        "permutation_records": list(order.permutation_records),
    }
    transform_layer = layer(transform_details, reasons=transform_reasons)
    if transform_reasons:
        raw_relation = fixed_relation = _precondition_selector_relation()
    else:
        if order.raw_selection is None or order.fixed_selection is None:
            raise V7AuditError("completed order primitive lacks selector observations")
        assert order.base.fixed_selection is not None
        raw_relation = _selector_relation_layer(
            order.base.result.selection,
            order.raw_selection,
            numeric_relation="exact_binary64",
            action_map=None,
        )
        fixed_relation = _selector_relation_layer(
            order.base.fixed_selection,
            order.fixed_selection,
            numeric_relation="exact_binary64",
            action_map=None,
        )
        if raw_relation["passes"] is not True:
            raw_relation = layer(
                cast(Mapping[str, JsonValue], raw_relation["details"]),
                reasons=("order_relation_mismatch",),
            )
        if fixed_relation["passes"] is not True:
            fixed_relation = layer(
                cast(Mapping[str, JsonValue], fixed_relation["details"]),
                reasons=("order_relation_mismatch",),
            )
    return {
        "order_transform": transform_layer,
        "raw_selector_relation": raw_relation,
        "fixed_selector_relation": fixed_relation,
    }


def _compound_control_19_passes(record: Mapping[str, Any]) -> bool:
    observed = record.get("observed")
    if not isinstance(observed, Mapping) or set(observed) != {"forward", "reversed"}:
        return False
    forward, reversed_selection = observed["forward"], observed["reversed"]
    if not isinstance(forward, Mapping) or not isinstance(reversed_selection, Mapping):
        return False
    for variant in ("m_decision", "x_decision"):
        left, right = forward.get(variant), reversed_selection.get(variant)
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return False
        for key in ("mode", "action", "probe_candidate", "utility_maximizers"):
            if left.get(key) != right.get(key):
                return False
        if not binary64_equal(left.get("score"), right.get("score")):
            return False
    left_rows, right_rows = forward.get("rows"), reversed_selection.get("rows")
    if not isinstance(left_rows, list) or not isinstance(right_rows, list):
        return False

    def index(rows: list[Any]) -> dict[bytes, Mapping[str, Any]] | None:
        result: dict[bytes, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                return None
            try:
                action_key = canonical_json_bytes(cast(JsonValue, row.get("action")))
            except (TypeError, ValueError):
                return None
            if action_key in result:
                return None
            result[action_key] = row
        return result

    left_index, right_index = index(left_rows), index(right_rows)
    if left_index is None or right_index is None or set(left_index) != set(right_index):
        return False
    for row_key, left in left_index.items():
        right = right_index[row_key]
        if any(
            left.get(field_name) != right.get(field_name)
            for field_name in ("m_rank", "x_rank", "m_selected", "x_selected")
        ):
            return False
    return True


def _derive_control_layer(
    primitive: ControlPrimitive,
    registered_row: Mapping[str, JsonValue],
    *,
    fixed: bool,
) -> dict[str, JsonValue]:
    record = primitive.fixed_record if fixed else primitive.raw_record
    predicate_key = "fixed_predicate_id" if fixed else "raw_predicate_id"
    calls = (
        primitive.fixed_selector_call_count
        if fixed
        else primitive.raw_selector_call_count
    )
    predicate_id = registered_row[predicate_key]
    if not isinstance(predicate_id, str):
        raise AddressableRecordError("registered control predicate identity is malformed")
    if fixed and primitive.control_id == "candidate_tie_pair":
        predicate_passes = _compound_control_19_passes(record)
    else:
        predicate_passes = (
            record.get("name") == primitive.control_id and record.get("passes") is True
        )
    observed = copy.deepcopy(cast(JsonValue, dict(record)))
    details: dict[str, JsonValue] = {
        "control_id": primitive.control_id,
        "control_contract_sha256": CONTROL_CONTRACT_SHA256,
        "predicate_id": predicate_id,
        "selector_call_count": calls,
        "observed": observed,
        "observed_sha256": canonical_sha256(observed),
        "predicate_passes": predicate_passes,
    }
    expected_calls = registered_row[
        "fixed_selector_call_count" if fixed else "raw_selector_call_count"
    ]
    passed = (
        registered_row.get("control_contract_sha256") == CONTROL_CONTRACT_SHA256
        and calls == expected_calls
        and predicate_passes
    )
    return layer(
        details,
        reasons=() if passed else ("control_expectation_mismatch",),
    )


def _select_fixed_counted(
    snapshot: PlanningSnapshot,
    counters: ResourceCounterState,
    *,
    category: Literal["scene_order", "isolated"],
) -> _reference.CompoundActionQBCSelection:
    _require_active_compute_time()
    counter = (
        "fixed_selector_scene_order_calls"
        if category == "scene_order"
        else "isolated_fixed_selector_calls"
    )
    counters.increment(counter)
    return _reference.select_compound_action_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )


def _select_raw_isolated(
    snapshot: PlanningSnapshot,
    counters: ResourceCounterState,
) -> ActionQBCSelection:
    _require_active_compute_time()
    counters.increment("isolated_raw_selector_calls")
    return select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )


def _pipeline_primitive(
    result: _v5.PipelineAuditResult,
    counters: ResourceCounterState,
) -> PipelinePrimitive:
    fixed = _select_fixed_counted(result.snapshot, counters, category="scene_order")
    return PipelinePrimitive(result=result, fixed_selection=fixed)


def _mapped_snapshot(
    snapshot: PlanningSnapshot,
    action_map: _reference.ReconstructedActionMap,
    *,
    transform_predictions: Callable[[Prediction], Prediction] | None = None,
) -> PlanningSnapshot:
    mapped_actions = tuple(
        _reference.map_action(action, action_map) for action in snapshot.actions
    )
    if len(set(mapped_actions)) != len(mapped_actions):
        raise _reference.ActionMapError("isolated action map is not bijective on frontier")
    predictions: dict[Action, tuple[Prediction | None, ...]] = {}
    costs: dict[Action, tuple[float, ...]] = {}
    for source_action, destination_action in zip(
        snapshot.actions, mapped_actions, strict=True
    ):
        source_predictions = snapshot.predictions[source_action]
        predictions[destination_action] = tuple(
            prediction
            if prediction is None or transform_predictions is None
            else cast(Any, transform_predictions)(prediction)
            for prediction in source_predictions
        )
        costs[destination_action] = tuple(snapshot.costs[source_action])
    return PlanningSnapshot(
        actions=mapped_actions,
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions=predictions,
        costs=costs,
        invalid_hypothesis_ids=snapshot.invalid_hypothesis_ids,
    )


def _prediction_transform(
    prediction: Prediction,
    contract: _reference.TransformContract,
) -> Prediction:
    if contract.transform_name == "palette_bijection":
        grid = _reference.palette_transform_grid(prediction.next_grid, contract)
    elif contract.transform_name == "scale_2_nearest_neighbor":
        grid = _reference.scale_transform_grid(prediction.next_grid, contract)
    else:
        grid, _origin = _reference.translation_transform_grid(
            prediction.next_grid, contract
        )
    return Prediction(grid, prediction.game_state, prediction.level_delta, prediction.memory)


def _transport_primitive(
    base: PipelinePrimitive,
    contract: _reference.TransformContract,
    action_map: _reference.ReconstructedActionMap,
    counters: ResourceCounterState,
    *,
    signature_pushforward: bool,
) -> TransportPrimitive:
    if base.result is None:
        return TransportPrimitive(None, None, None)
    try:
        base_actions = base.result.snapshot.actions
        mapped_actions = tuple(
            _reference.map_action(action, action_map) for action in base_actions
        )
        if len(set(mapped_actions)) != len(mapped_actions):
            return TransportPrimitive(
                None,
                None,
                None,
                "isolated_action_map_not_bijective",
            )
        canonical_before = sorted(base_actions, key=_reference.canonical_action_key)
        canonical_after = sorted(mapped_actions, key=_reference.canonical_action_key)
        mapped_canonical = [
            _reference.map_action(action, action_map) for action in canonical_before
        ]
        if mapped_canonical != canonical_after:
            return TransportPrimitive(
                None,
                None,
                None,
                "isolated_action_map_not_canonical_order_preserving",
            )
        transform = (
            (lambda prediction: _prediction_transform(prediction, contract))
            if signature_pushforward
            else None
        )
        snapshot = _mapped_snapshot(
            base.result.snapshot,
            action_map,
            transform_predictions=transform,
        )
        if signature_pushforward:
            signature_map: dict[tuple[Any, ...], tuple[Any, ...]] = {}
            for action in base.result.snapshot.actions:
                mapped = _reference.map_action(action, action_map)
                for left, right in zip(
                    base.result.snapshot.predictions[action],
                    snapshot.predictions[mapped],
                    strict=True,
                ):
                    if left is None or right is None:
                        continue
                    previous = signature_map.setdefault(left.signature(), right.signature())
                    if previous != right.signature():
                        return TransportPrimitive(
                            None,
                            None,
                            None,
                            "isolated_signature_transform_not_injective",
                        )
            if len(set(signature_map.values())) != len(signature_map):
                return TransportPrimitive(
                    None,
                    None,
                    None,
                    "isolated_signature_transform_not_injective",
                )
    except (_reference.V7ReferenceError, TypeError, ValueError):
        reason = (
            "isolated_signature_transform_not_injective"
            if signature_pushforward
            else "isolated_action_map_not_bijective"
        )
        return TransportPrimitive(None, None, None, reason)
    # Selection faults are evaluator faults, not evidence about a transport premise.
    raw = _select_raw_isolated(snapshot, counters)
    fixed = _select_fixed_counted(snapshot, counters, category="isolated")
    return TransportPrimitive(snapshot, raw, fixed)


def _order_primitive(
    base: PipelinePrimitive,
    contract: Mapping[str, Any],
    legacy: _v5.AuditCounterState,
    counters: ResourceCounterState,
) -> OrderPrimitive:
    name = contract.get("name")
    target = contract.get("target")
    rule = contract.get("rule")
    if not all(isinstance(value, str) for value in (name, target, rule)):
        raise V7AuditError("order contract is malformed")
    contract_json = cast(JsonValue, dict(contract))
    contract_sha = canonical_sha256(contract_json)
    if base.result is None:
        return OrderPrimitive(
            base,
            cast(str, name),
            cast(str, target),
            contract_sha,
            (),
            None,
            None,
        )
    snapshot = base.result.snapshot
    records: list[dict[str, JsonValue]] = []
    if target == "candidate_sequence":
        permutation = _permutation(cast(str, rule), len(snapshot.actions))
        transformed = _v5._candidate_permutation(snapshot, permutation)
        records.append(
            {
                "action": None,
                "sequence_length": len(snapshot.actions),
                "output_to_input_permutation": list(permutation),
            }
        )
        patch_outcomes = False
    elif target == "hypothesis_sequence":
        permutation = _permutation(cast(str, rule), len(snapshot.hypothesis_ids))
        transformed = _v5._permute_hypotheses(snapshot, permutation)
        records.append(
            {
                "action": None,
                "sequence_length": len(snapshot.hypothesis_ids),
                "output_to_input_permutation": list(permutation),
            }
        )
        patch_outcomes = False
    elif target == "per_action_serialized_outcome_cell_sequence":
        transformed = snapshot
        for row in base.result.selection.rows:
            permutation = _permutation(cast(str, rule), row.outcome_cell_count)
            records.append(
                {
                    "action": action_json(row.action),
                    "sequence_length": row.outcome_cell_count,
                    "output_to_input_permutation": list(permutation),
                }
            )
        patch_outcomes = True
    else:
        raise V7AuditError("order target is not registered")

    def selections() -> tuple[ActionQBCSelection, _reference.CompoundActionQBCSelection]:
        _require_active_compute_time()
        legacy.increment("pure_selector_calls")
        legacy.increment("pure_selector_scene_order_calls")
        raw = select_action_conditional_qbc(
            transformed,
            cross_level_multiplier=23.0,
            probes_used=0,
            probe_cap=3,
        )
        fixed = _select_fixed_counted(transformed, counters, category="scene_order")
        return raw, fixed

    if not patch_outcomes:
        raw, fixed = selections()
    else:
        original = _policy_module._partition_normalized_outcomes

        def reverse_cells(
            predictions: Sequence[Prediction],
            normalized_weights: Sequence[float],
        ) -> tuple[Any, ...]:
            return tuple(reversed(original(predictions, normalized_weights)))

        with _v5._OUTCOME_CELL_TRANSFORM_LOCK:
            _policy_module._partition_normalized_outcomes = reverse_cells
            try:
                raw, fixed = selections()
            finally:
                _policy_module._partition_normalized_outcomes = original
    return OrderPrimitive(
        base,
        cast(str, name),
        cast(str, target),
        contract_sha,
        tuple(records),
        raw,
        fixed,
    )


def _control_primitives(
    legacy: _v5.AuditCounterState,
    counters: ResourceCounterState,
) -> tuple[ControlPrimitive, ...]:
    _require_active_compute_time()
    if _v5.preregistered_control_contract_sha256() != CONTROL_CONTRACT_SHA256:
        raise V7AuditError("control contract source digest drifted")
    with _CONTROL_SUBSTITUTION_LOCK:
        saved = _v5.ACTION_QBC_AUDIT_SELECTOR
        if saved is not select_action_conditional_qbc:
            raise V7AuditError("raw control selector identity drifted")
        raw_records = _v5.evaluate_preregistered_controls(
            legacy, continue_after_failure=False
        )
        compound_legacy = _v5.AuditCounterState()
        try:
            _require_active_compute_time()
            _v5.ACTION_QBC_AUDIT_SELECTOR = _reference.select_compound_action_qbc  # type: ignore[assignment,misc]
            fixed_records = _v5.evaluate_preregistered_controls(
                compound_legacy, continue_after_failure=False
            )
        finally:
            _v5.ACTION_QBC_AUDIT_SELECTOR = saved  # type: ignore[misc]
            if _v5.ACTION_QBC_AUDIT_SELECTOR is not saved:
                raise V7AuditError("control selector restoration failed")
    compound_snapshot = compound_legacy.snapshot()
    if (
        compound_snapshot["pure_selector_calls"] != 19
        or compound_snapshot["pure_selector_control_calls"] != 19
        or compound_snapshot["pure_selector_scene_order_calls"] != 0
        or any(
            value != 0
            for name, value in compound_snapshot.items()
            if name
            not in {
                "pure_selector_calls",
                "pure_selector_control_calls",
                "pure_selector_scene_order_calls",
            }
        )
    ):
        raise V7AuditError("compound control counter routing failed")
    counters.set_compound_control_calls(19)
    ledger = _v5.PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER
    return tuple(
        ControlPrimitive(
            control_id=control_id,
            raw_record=raw,
            fixed_record=fixed,
            raw_selector_call_count=ledger[control_id],
            fixed_selector_call_count=ledger[control_id],
        )
        for control_id, raw, fixed in zip(
            CONTROL_IDS, raw_records, fixed_records, strict=True
        )
    )


def _registration_transform_contract(
    registration: Mapping[str, JsonValue],
    *,
    family: str,
    scene_index: int,
    transform_name: str,
) -> tuple[
    _reference.TransformContract,
    _reference.ReconstructedActionMap,
    _reference.ReconstructedActionMap,
]:
    rows = registration.get("transform_contracts")
    if not isinstance(rows, list):
        raise GlobalFallbackRequired("transform_action_map_invalid")
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("family") == family
        and row.get("scene_index") == scene_index
        and row.get("transform_name") == transform_name
    ]
    if len(matches) != 1:
        raise GlobalFallbackRequired("transform_action_map_invalid")
    registered = matches[0]
    core = {
        "schema_version": "action-qbc-v7-transform-contract-v1",
        "family": registered.get("family"),
        "scene_index": registered.get("scene_index"),
        "transform_name": registered.get("transform_name"),
        "source_shape": registered.get("source_shape"),
        "actual_destination_shape": registered.get("actual_destination_shape"),
        "isolated_destination_shape": registered.get("isolated_destination_shape"),
        "source_background_label": registered.get("source_background_label"),
        "destination_background_label": registered.get("destination_background_label"),
        "parameters": registered.get("parameters"),
    }
    try:
        contract = _reference.validate_transform_contract(
            core, expected_sha256=cast(str, registered.get("contract_sha256"))
        )
        actual = _reference.reconstruct_action_map(contract, map_kind="actual")
        isolated = _reference.reconstruct_action_map(contract, map_kind="isolated")
        if (
            actual.sha256 != registered.get("actual_action_map_sha256")
            or isolated.sha256 != registered.get("isolated_action_map_sha256")
        ):
            raise _reference.ActionMapError("registered action-map digest mismatch")
    except _reference.V7ReferenceError as error:
        raise GlobalFallbackRequired("transform_action_map_invalid") from error
    return contract, actual, isolated


def _require_compute_time(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("v7 scientific compute deadline elapsed")


def _require_active_compute_time() -> None:
    if _ACTIVE_COMPUTE_DEADLINE is not None:
        _require_compute_time(_ACTIVE_COMPUTE_DEADLINE)


def produce_scientific_candidate(
    repository_root: Path | str,
    registration: Mapping[str, JsonValue],
    *,
    compute_deadline: float,
) -> dict[str, Any]:
    """Execute the frozen primitive ledger without constructing scientific conclusions."""

    global _ACTIVE_COMPUTE_DEADLINE
    root = Path(repository_root).resolve(strict=True)
    if action_qbc_policy_sha256() != RAW_POLICY_SHA256:
        raise V7AuditError("raw selector source identity drifted")
    counters, legacy = _begin_resource_accounting()
    _ACTIVE_COMPUTE_DEADLINE = compute_deadline
    try:
        config = load_config(root / _v5.AUDIT_CONFIG_RELATIVE_PATH)
        scene_inventory = registration.get("scene_inventory")
        if not isinstance(scene_inventory, Mapping) or not isinstance(
            scene_inventory.get("scenes"), list
        ):
            raise V7AuditError("registration scene inventory is malformed")
        registered_scenes = cast(list[Mapping[str, Any]], scene_inventory["scenes"])
        scenes: dict[tuple[str, int], Mapping[str, Any]] = {}
        for registered_scene in registered_scenes:
            _require_compute_time(compute_deadline)
            family = registered_scene.get("family")
            scene_index = registered_scene.get("scene_index")
            seed_hex = registered_scene.get("seed_hex")
            if (
                not isinstance(family, str)
                or not isinstance(scene_index, int)
                or isinstance(scene_index, bool)
                or not isinstance(seed_hex, str)
            ):
                raise V7AuditError("registered public scene identity is malformed")
            counters.increment("public_scene_generations")
            scene = generate_open_scene(family, int(seed_hex, 16))
            if scene.get("content_sha256") != registered_scene.get("scene_sha256"):
                raise V7AuditError("generated public scene hash differs from registration")
            scenes[(family, scene_index)] = scene
        if tuple(scenes) != tuple(
            (family, index) for family in SCENE_FAMILIES for index in range(4)
        ):
            raise V7AuditError("public scene order differs from registration")

        # Admit every registered transform/map before the first compiler call so the
        # highest-precedence global map failure cannot follow partial scientific exposure.
        prepared_transforms: dict[
            tuple[str, int, str],
            tuple[
                _reference.TransformContract,
                _reference.ReconstructedActionMap,
                _reference.ReconstructedActionMap,
            ],
        ] = {}
        for family in SCENE_FAMILIES:
            for scene_index in range(4):
                for transform_name in VISUAL_TRANSFORMS:
                    prepared_transforms[(family, scene_index, transform_name)] = (
                        _registration_transform_contract(
                            registration,
                            family=family,
                            scene_index=scene_index,
                            transform_name=transform_name,
                        )
                    )

        base_by_scene: dict[tuple[str, int], PipelinePrimitive] = {}
        visual_by_id: dict[str, VisualPrimitive] = {}
        order_by_id: dict[str, OrderPrimitive] = {}
        scientific_contract = registration.get("scientific_contract")
        if not isinstance(scientific_contract, Mapping) or not isinstance(
            scientific_contract.get("order_contracts"), list
        ):
            raise V7AuditError("registration scientific contract is malformed")
        order_contracts = cast(list[Mapping[str, Any]], scientific_contract["order_contracts"])
        for family in SCENE_FAMILIES:
            for scene_index in range(4):
                scene_record: Mapping[str, Any] = scenes[(family, scene_index)]
                base_scene = scene_record.get("base_scene")
                raw_visuals = scene_record.get("visual_transforms")
                if not isinstance(base_scene, Mapping) or not isinstance(raw_visuals, list):
                    raise V7AuditError("generated scene lacks public transform records")
                _require_compute_time(compute_deadline)
                completed_before = legacy.snapshot()["completed_planning_snapshots"]
                try:
                    base_result = _v5.evaluate_compiler_planner_snapshot(
                        _v5._scene_history(base_scene, base_scene),
                        config=config,
                        counters=legacy,
                        exercise_controllers=True,
                    )
                except Exception:
                    if (
                        legacy.snapshot()["completed_planning_snapshots"]
                        > completed_before
                    ):
                        raise
                    if not legacy.scientific_exposure_started:
                        raise
                    base = PipelinePrimitive(None, None, "unavailable")
                else:
                    # Compound-selector and v4 faults are evaluator faults and must escape.
                    base = _pipeline_primitive(base_result, counters)
                    _require_active_compute_time()
                    _structural_observation, structural_passes = _structural_details(
                        base_result
                    )
                    _v5._v4_counterfactual(
                        base_result,
                        structural_passes=structural_passes,
                        probe_cap_available=True,
                        counters=legacy,
                    )
                base_by_scene[(family, scene_index)] = base
                raw_by_name = {
                    item.get("name"): item
                    for item in raw_visuals
                    if isinstance(item, Mapping)
                }
                for transform_name in VISUAL_TRANSFORMS:
                    raw_transform = raw_by_name.get(transform_name)
                    if not isinstance(raw_transform, Mapping):
                        raise V7AuditError("generated visual transform inventory drifted")
                    contract, actual_map, isolated_map = prepared_transforms[
                        (family, scene_index, transform_name)
                    ]
                    _require_compute_time(compute_deadline)
                    if transform_name == "scale_2_nearest_neighbor" and base.result is None:
                        transformed = PipelinePrimitive(None, None, "unavailable")
                    else:
                        completed_before = legacy.snapshot()[
                            "completed_planning_snapshots"
                        ]
                        try:
                            supplied = (
                                tuple(
                                    _reference.map_action(action, actual_map)
                                    for action in cast(
                                        _v5.PipelineAuditResult, base.result
                                    ).snapshot.actions
                                )
                                if transform_name == "scale_2_nearest_neighbor"
                                else None
                            )
                            result = _v5.evaluate_compiler_planner_snapshot(
                                _v5._scene_history(raw_transform, base_scene),
                                config=config,
                                counters=legacy,
                                supplied_actions=supplied,
                                exercise_controllers=(
                                    transform_name != "scale_2_nearest_neighbor"
                                ),
                            )
                        except Exception:
                            if (
                                legacy.snapshot()["completed_planning_snapshots"]
                                > completed_before
                            ):
                                raise
                            if not legacy.scientific_exposure_started:
                                raise
                            transformed = PipelinePrimitive(None, None, "unavailable")
                        else:
                            # A completed snapshot's compound selector is authoritative work;
                            # inability to execute it is not a pipeline-availability result.
                            transformed = _pipeline_primitive(result, counters)
                    action_transport = _transport_primitive(
                        base,
                        contract,
                        isolated_map,
                        counters,
                        signature_pushforward=False,
                    )
                    signature_transport = _transport_primitive(
                        base,
                        contract,
                        isolated_map,
                        counters,
                        signature_pushforward=True,
                    )
                    row_id = f"visual:{family}:{scene_index}:{transform_name}"
                    visual_by_id[row_id] = VisualPrimitive(
                        base,
                        transformed,
                        contract,
                        actual_map,
                        isolated_map,
                        action_transport,
                        signature_transport,
                        raw_transform,
                    )
                for order_contract in order_contracts:
                    _require_compute_time(compute_deadline)
                    order = _order_primitive(base, order_contract, legacy, counters)
                    row_id = f"order:{family}:{scene_index}:{order.transform_name}"
                    order_by_id[row_id] = order

        controls = _control_primitives(legacy, counters)
        controls_by_id = {
            f"control:{control.control_id}": control for control in controls
        }
        v6_bytes = (root / V6_RESULT_PATH).read_bytes()
        if hashlib.sha256(v6_bytes).hexdigest() != V6_RESULT_SHA256:
            raise V7AuditError("frozen v6 result bytes drifted")
        v6_result = json.loads(v6_bytes)
        records: list[dict[str, Any]] = []
        for registered_row in _registered_rows(registration):
            address = _row_address(registered_row)
            row_id = cast(str, address["row_id"])
            kind = address["kind"]
            if kind == "base_scene":
                primitive: Any = base_by_scene[
                    (
                        cast(str, registered_row["family"]),
                        cast(int, registered_row["scene_index"]),
                    )
                ]
            elif kind == "visual_transform":
                primitive = visual_by_id[row_id]
            elif kind == "order_transform":
                primitive = order_by_id[row_id]
            elif kind == "control":
                primitive = controls_by_id[row_id]
            else:
                raise V7AuditError("registered row kind is unknown")
            records.append({"address": address, "primitive": primitive})
        return {
            "repository_root": root,
            "records": tuple(records),
            "v6_result": v6_result,
            "resource_state": counters,
            "legacy_state": legacy,
        }
    except BaseException:
        # Active state is intentionally retained so the runner's fail-closed branch records
        # exact observed work rather than substituting the expected vector.
        raise


BASE_EVIDENCE_KEYS: Final = (
    "pipeline",
    "raw_selector",
    "fixed_selector",
    "structural",
    "mechanism",
    "v4_counterfactual",
    "prepreregistered_reproduction",
)
VISUAL_EVIDENCE_KEYS: Final = (
    "pipeline_integrity",
    "frontier_relation",
    "role_weight_relation",
    "root_transition",
    "planner_cost",
    "actual_raw_selector",
    "actual_fixed_selector",
    "isolated_action_relabel_raw",
    "isolated_action_relabel_fixed",
    "isolated_signature_pushforward_raw",
    "isolated_signature_pushforward_fixed",
    "v6_reproduction",
)
ORDER_EVIDENCE_KEYS: Final = (
    "order_transform",
    "raw_selector_relation",
    "fixed_selector_relation",
)
CONTROL_EVIDENCE_KEYS: Final = ("raw_control", "fixed_control")

LAYER_DETAIL_KEYS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "pipeline": tuple(PIPELINE_DEFAULT),
        "raw_selector": tuple(SELECTION_DEFAULT),
        "fixed_selector": tuple(SELECTION_DEFAULT),
        "structural": tuple(STRUCTURAL_DEFAULT),
        "mechanism": tuple(MECHANISM_DEFAULT),
        "v4_counterfactual": tuple(V4_DEFAULT),
        "prepreregistered_reproduction": tuple(PREOBSERVED_DEFAULT),
        "pipeline_integrity": tuple(PIPELINE_INTEGRITY_DEFAULT),
        "frontier_relation": tuple(FRONTIER_DEFAULT),
        "role_weight_relation": tuple(ROLE_WEIGHT_DEFAULT),
        "root_transition": tuple(ROOT_TRANSITION_DEFAULT),
        "planner_cost": tuple(PLANNER_COST_DEFAULT),
        "actual_raw_selector": tuple(SELECTOR_RELATION_DEFAULT),
        "actual_fixed_selector": tuple(SELECTOR_RELATION_DEFAULT),
        "isolated_action_relabel_raw": tuple(SELECTOR_RELATION_DEFAULT),
        "isolated_action_relabel_fixed": tuple(SELECTOR_RELATION_DEFAULT),
        "isolated_signature_pushforward_raw": tuple(SELECTOR_RELATION_DEFAULT),
        "isolated_signature_pushforward_fixed": tuple(SELECTOR_RELATION_DEFAULT),
        "v6_reproduction": tuple(V6_REPRODUCTION_DEFAULT),
        "order_transform": tuple(ORDER_TRANSFORM_DEFAULT),
        "raw_selector_relation": tuple(SELECTOR_RELATION_DEFAULT),
        "fixed_selector_relation": tuple(SELECTOR_RELATION_DEFAULT),
        "raw_control": tuple(CONTROL_DEFAULT),
        "fixed_control": tuple(CONTROL_DEFAULT),
    }
)


def _candidate_inventory(
    candidate: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
) -> tuple[tuple[Mapping[str, JsonValue], Any, bool], ...]:
    if set(candidate) != {
        "repository_root",
        "records",
        "v6_result",
        "resource_state",
        "legacy_state",
    }:
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")
    raw_records = candidate.get("records")
    if not isinstance(raw_records, (tuple, list)):
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")
    registered = _registered_rows(registration)
    if len(raw_records) != len(registered):
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")
    result: list[tuple[Mapping[str, JsonValue], Any, bool]] = []
    seen: set[tuple[int, str, str]] = set()
    for record, expected in zip(raw_records, registered, strict=True):
        if not isinstance(record, Mapping) or "address" not in record:
            raise GlobalFallbackRequired("scientific_record_inventory_invalid")
        _validate_address(record["address"], expected)
        address = cast(Mapping[str, JsonValue], record["address"])
        identity = (
            cast(int, address["row_index"]),
            cast(str, address["row_id"]),
            cast(str, address["kind"]),
        )
        if identity in seen:
            raise GlobalFallbackRequired("scientific_record_inventory_invalid")
        seen.add(identity)
        schema_error = set(record) != {"address", "primitive"}
        result.append((expected, record.get("primitive"), schema_error))
    return tuple(result)


def _addressable_terminal_row(
    registered: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    return {
        "address": _row_address(registered),
        "registered_row": copy.deepcopy(dict(registered)),
        "disposition": "terminal_addressable_negative",
        "evidence": {},
        "terminal": {
            "status": "authoritative_derivation_error",
            "stage": "scientific_record_schema_invalid",
        },
    }


def _completed_row(
    registered: Mapping[str, JsonValue],
    evidence: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    return {
        "address": _row_address(registered),
        "registered_row": copy.deepcopy(dict(registered)),
        "disposition": "completed",
        "evidence": copy.deepcopy(dict(evidence)),
        "terminal": None,
    }


def _patch_v6_failure_vector(rows: Sequence[MutableMapping[str, JsonValue]]) -> str | None:
    applicable: list[
        tuple[MutableMapping[str, JsonValue], MutableMapping[str, JsonValue]]
    ] = []
    failing: list[JsonValue] = []
    for row in rows:
        if row.get("disposition") != "completed":
            continue
        registered = row.get("registered_row")
        evidence = row.get("evidence")
        if (
            not isinstance(registered, Mapping)
            or registered.get("kind") != "visual_transform"
            or registered.get("scene_index") != 0
            or not isinstance(evidence, MutableMapping)
        ):
            continue
        layer_value = evidence.get("v6_reproduction")
        if not isinstance(layer_value, MutableMapping):
            continue
        details = layer_value.get("details")
        if not isinstance(details, MutableMapping):
            continue
        observed = details.get("observed_comparison")
        if not isinstance(observed, Mapping):
            continue
        applicable.append((layer_value, details))
        if observed.get("passes") is not True:
            failing.append(
                {
                    "family": registered.get("family"),
                    "transform_name": registered.get("transform_name"),
                    "comparison": copy.deepcopy(dict(observed)),
                }
            )
    if len(applicable) != 12:
        return None
    observed_sha = canonical_sha256(failing)
    vector_pass = observed_sha == V6_FAILURE_VECTOR_SHA256
    for envelope, mutable_details in applicable:
        mutable_details["observed_failure_vector_sha256"] = observed_sha
        comparison_pass = mutable_details.get("comparison_reproduced") is True
        reasons = () if vector_pass and comparison_pass else ("v6_failure_vector_mismatch",)
        envelope.clear()
        envelope.update(
            layer(cast(Mapping[str, JsonValue], mutable_details), reasons=reasons)
        )
    return observed_sha


def _layer_pass(row: Mapping[str, Any], name: str) -> bool:
    evidence = row.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    value = evidence.get(name)
    return isinstance(value, Mapping) and value.get("passes") is True


def _layer_status(row: Mapping[str, Any], name: str) -> str | None:
    evidence = row.get("evidence")
    value = evidence.get(name) if isinstance(evidence, Mapping) else None
    return cast(str | None, value.get("status")) if isinstance(value, Mapping) else None


def _fixed_relation_raw_numeric_passes(row: Mapping[str, Any]) -> bool:
    evidence = row.get("evidence")
    envelope = (
        evidence.get("actual_fixed_selector")
        if isinstance(evidence, Mapping)
        else None
    )
    details = envelope.get("details") if isinstance(envelope, Mapping) else None
    if (
        not isinstance(envelope, Mapping)
        or not isinstance(details, Mapping)
        or envelope.get("status") != "evaluated"
        or details.get("numeric_mismatch_count") != 0
    ):
        return False
    records = details.get("candidate_records")
    if not isinstance(records, list) or not records:
        return False
    numeric_names = (
        "outcome_concentration",
        "outcome_cell_count",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    for record in records:
        if not isinstance(record, Mapping):
            return False
        for side in ("left", "right"):
            scalars = record.get(side)
            if not isinstance(scalars, Mapping):
                return False
            for name in numeric_names:
                value = scalars.get(name)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    return False
    return True


def _compound_scale_reconciled(row: Mapping[str, Any], *, primary: bool) -> bool:
    required = (
        "pipeline_integrity",
        "frontier_relation",
        "role_weight_relation",
        "root_transition",
        "planner_cost",
        "actual_fixed_selector",
    )
    return (
        all(_layer_pass(row, name) for name in required)
        and _fixed_relation_raw_numeric_passes(row)
        and (not primary or _layer_pass(row, "v6_reproduction"))
    )


def _derive_aggregates(
    rows: Sequence[Mapping[str, Any]],
    counters: Mapping[str, int],
    *,
    observed_v6_sha: str | None,
) -> dict[str, JsonValue]:
    result = _empty_aggregates(counters)
    bases = [
        row
        for row in rows
        if isinstance(row.get("registered_row"), Mapping)
        and cast(Mapping[str, Any], row["registered_row"]).get("kind") == "base_scene"
    ]
    visuals = [
        row
        for row in rows
        if isinstance(row.get("registered_row"), Mapping)
        and cast(Mapping[str, Any], row["registered_row"]).get("kind")
        == "visual_transform"
    ]
    orders = [
        row
        for row in rows
        if isinstance(row.get("registered_row"), Mapping)
        and cast(Mapping[str, Any], row["registered_row"]).get("kind")
        == "order_transform"
    ]
    controls = [
        row
        for row in rows
        if isinstance(row.get("registered_row"), Mapping)
        and cast(Mapping[str, Any], row["registered_row"]).get("kind") == "control"
    ]
    result["prepreregistered_base_reproduced_count"] = sum(
        _layer_pass(row, "prepreregistered_reproduction") for row in bases
    )
    result["base_structural_pass_count"] = sum(
        _layer_pass(row, "structural") for row in bases
    )
    result["base_mechanism_pass_count"] = sum(
        _layer_pass(row, "mechanism") for row in bases
    )
    result["base_causal_true_count"] = sum(
        _layer_pass(row, "v4_counterfactual") for row in bases
    )
    applicable_v6 = [
        row
        for row in visuals
        if cast(Mapping[str, Any], row["registered_row"]).get("scene_index") == 0
    ]
    result["v6_failure_vector_observed_sha256"] = observed_v6_sha
    result["v6_failure_vector_reproduced"] = (
        len(applicable_v6) == 12
        and observed_v6_sha == V6_FAILURE_VECTOR_SHA256
        and all(_layer_pass(row, "v6_reproduction") for row in applicable_v6)
    )
    translations = [
        row
        for row in visuals
        if str(cast(Mapping[str, Any], row["registered_row"]).get("transform_name", ""))
        .startswith("translation_")
    ]
    category_to_key = {
        "fully_equivariant": "translation_fully_equivariant_pair_count",
        "boundary_consistent_censored": (
            "translation_boundary_consistent_censored_pair_count"
        ),
        "interior_or_metadata_mismatch": (
            "translation_interior_or_metadata_mismatch_pair_count"
        ),
        "invalid_prediction": "translation_invalid_prediction_pair_count",
    }
    positive_zero_exterior = positive_zero_boundary = 0
    for row in translations:
        evidence = row.get("evidence")
        root = evidence.get("root_transition") if isinstance(evidence, Mapping) else None
        details = root.get("details") if isinstance(root, Mapping) else None
        if not isinstance(details, Mapping):
            continue
        pair_records = details.get("pair_records")
        if not isinstance(pair_records, list):
            continue
        for pair in pair_records:
            if not isinstance(pair, Mapping):
                continue
            result["translation_prediction_pair_count"] = cast(
                int, result["translation_prediction_pair_count"]
            ) + 1
            category = pair.get("category")
            if category in category_to_key:
                key = category_to_key[cast(str, category)]
                result[key] = cast(int, result[key]) + 1
            exterior = pair.get("expected_exterior_nonbackground_count")
            exterior_count = exterior if isinstance(exterior, int) else 0
            result["translation_expected_exterior_cell_count"] = cast(
                int, result["translation_expected_exterior_cell_count"]
            ) + exterior_count
            if category == "boundary_consistent_censored":
                result["translation_boundary_consistent_exterior_cell_count"] = cast(
                    int,
                    result["translation_boundary_consistent_exterior_cell_count"],
                ) + exterior_count
            elif category == "interior_or_metadata_mismatch":
                result["translation_mixed_exterior_cell_count"] = cast(
                    int, result["translation_mixed_exterior_cell_count"]
                ) + exterior_count
            elif category == "invalid_prediction":
                result["translation_invalid_prediction_exterior_cell_count"] = cast(
                    int, result["translation_invalid_prediction_exterior_cell_count"]
                ) + exterior_count
            registered = cast(Mapping[str, Any], row["registered_row"])
            if (
                registered.get("scene_index") == 0
                and registered.get("transform_name")
                == "translation_row_plus_3_col_plus_5"
            ):
                positive_zero_exterior += exterior_count
                if category == "boundary_consistent_censored":
                    positive_zero_boundary += exterior_count
    result["frozen_positive_translation_observed_exterior_cell_count"] = (
        positive_zero_exterior
    )
    result["frozen_positive_translation_boundary_consistent_exterior_cell_count"] = (
        positive_zero_boundary
    )
    result["frozen_positive_translation_support_reproduced"] = (
        result["v6_failure_vector_reproduced"] is True and positive_zero_exterior == 107
    )
    primary_scales = [
        row
        for row in visuals
        if cast(Mapping[str, Any], row["registered_row"]).get("transform_name")
        == "scale_2_nearest_neighbor"
        and cast(Mapping[str, Any], row["registered_row"]).get("scene_index") == 0
    ]
    extension_scales = [
        row
        for row in visuals
        if cast(Mapping[str, Any], row["registered_row"]).get("transform_name")
        == "scale_2_nearest_neighbor"
        and cast(Mapping[str, Any], row["registered_row"]).get("scene_index") != 0
    ]
    result["primary_compound_scale_reconciliation_count"] = sum(
        _compound_scale_reconciled(row, primary=True) for row in primary_scales
    )
    result["primary_compound_scale_reconciliation"] = (
        result["primary_compound_scale_reconciliation_count"] == 3
    )
    result["extension_compound_scale_reconciliation_count"] = sum(
        _compound_scale_reconciled(row, primary=False) for row in extension_scales
    )
    result["isolated_action_relabel_pass_count"] = sum(
        _layer_pass(row, "isolated_action_relabel_raw")
        and _layer_pass(row, "isolated_action_relabel_fixed")
        for row in visuals
    )
    result["isolated_signature_pushforward_pass_count"] = sum(
        _layer_pass(row, "isolated_signature_pushforward_raw")
        and _layer_pass(row, "isolated_signature_pushforward_fixed")
        for row in visuals
    )
    for prefix, layer_name in (
        ("actual_raw_selector", "actual_raw_selector"),
        ("actual_fixed_selector", "actual_fixed_selector"),
    ):
        result[f"{prefix}_evaluated_count"] = sum(
            _layer_status(row, layer_name) == "evaluated" for row in visuals
        )
        result[f"{prefix}_pass_count"] = sum(
            _layer_pass(row, layer_name) for row in visuals
        )
        result[f"{prefix}_precondition_failed_count"] = sum(
            _layer_status(row, layer_name) == "precondition_failed" for row in visuals
        )
    result["order_raw_pass_count"] = sum(
        _layer_pass(row, "raw_selector_relation") for row in orders
    )
    result["order_fixed_pass_count"] = sum(
        _layer_pass(row, "fixed_selector_relation") for row in orders
    )
    result["control_raw_pass_count"] = sum(
        _layer_pass(row, "raw_control") for row in controls
    )
    result["control_fixed_pass_count"] = sum(
        _layer_pass(row, "fixed_control") for row in controls
    )
    reason_counts = {reason: 0 for reason in REASON_ORDER}
    for row in rows:
        evidence = row.get("evidence")
        if not isinstance(evidence, Mapping):
            continue
        for envelope in evidence.values():
            reasons = envelope.get("reasons") if isinstance(envelope, Mapping) else None
            if isinstance(reasons, list):
                for reason in reasons:
                    if reason in reason_counts:
                        reason_counts[cast(str, reason)] += 1
    if dict(counters) != dict(EXPECTED_RESOURCE_COUNTS):
        reason_counts["resource_counter_mismatch"] += 1
    if any(counters[name] != 0 for name in FORBIDDEN_RESOURCE_COUNTERS):
        reason_counts["forbidden_resource_use"] += 1
    result["reason_counts"] = cast(JsonValue, reason_counts)
    result["resource_contract_passes"] = resource_contract_passes(counters)
    return {name: result[name] for name in AGGREGATE_KEYS}


def _reference_occurrences(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[str | None], list[str | None]]:
    grids: list[str | None] = []
    supports: list[str | None] = []
    for row in rows:
        evidence = row.get("evidence")
        root = evidence.get("root_transition") if isinstance(evidence, Mapping) else None
        details = root.get("details") if isinstance(root, Mapping) else None
        pairs = details.get("pair_records") if isinstance(details, Mapping) else None
        if not isinstance(pairs, list):
            continue
        for pair in pairs:
            if not isinstance(pair, Mapping):
                continue
            grids.extend(
                cast(str | None, pair.get(name))
                for name in (
                    "base_prediction_ref",
                    "transformed_prediction_ref",
                    "expected_prediction_ref",
                    "observable_mismatch_mask_ref",
                )
            )
            supports.append(cast(str | None, pair.get("expected_exterior_support_ref")))
    return grids, supports


def _finalize_candidate(
    candidate: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    inventory = _candidate_inventory(candidate, registration)
    root_value = candidate.get("repository_root")
    root = (
        Path(root_value).resolve(strict=True)
        if isinstance(root_value, (str, Path))
        else Path(".").resolve(strict=True)
    )
    v6_result = candidate.get("v6_result")
    counters = candidate.get("resource_state")
    legacy = candidate.get("legacy_state")
    if (
        not isinstance(v6_result, Mapping)
        or not isinstance(counters, ResourceCounterState)
        or not isinstance(legacy, _v5.AuditCounterState)
    ):
        raise GlobalFallbackRequired("scientific_record_inventory_invalid")
    grid_registry = _reference.GridEvidenceRegistry()
    support_registry = _reference.ExteriorSupportRegistry()
    final_rows: list[dict[str, JsonValue]] = []
    for registered, primitive, schema_error in inventory:
        if schema_error:
            final_rows.append(_addressable_terminal_row(registered))
            continue
        try:
            kind = registered["kind"]
            if kind == "base_scene":
                if not isinstance(primitive, PipelinePrimitive):
                    raise AddressableRecordError("base primitive type is invalid")
                evidence = derive_base_evidence(
                    primitive,
                    family=cast(str, registered["family"]),
                    scene_index=cast(int, registered["scene_index"]),
                    legacy_counters=legacy,
                )
            elif kind == "visual_transform":
                if not isinstance(primitive, VisualPrimitive):
                    raise AddressableRecordError("visual primitive type is invalid")
                evidence = derive_visual_evidence(
                    primitive,
                    family=cast(str, registered["family"]),
                    scene_index=cast(int, registered["scene_index"]),
                    transform_name=cast(str, registered["transform_name"]),
                    v6_result=v6_result,
                    grid_registry=grid_registry,
                    support_registry=support_registry,
                )
            elif kind == "order_transform":
                if not isinstance(primitive, OrderPrimitive):
                    raise AddressableRecordError("order primitive type is invalid")
                evidence = _derive_order_evidence(primitive, registered)
            elif kind == "control":
                if not isinstance(primitive, ControlPrimitive):
                    raise AddressableRecordError("control primitive type is invalid")
                evidence = {
                    "raw_control": _derive_control_layer(
                        primitive, registered, fixed=False
                    ),
                    "fixed_control": _derive_control_layer(
                        primitive, registered, fixed=True
                    ),
                }
            else:
                raise AddressableRecordError("registered row kind is invalid")
            final_rows.append(_completed_row(registered, evidence))
        except AddressableRecordError:
            final_rows.append(_addressable_terminal_row(registered))
    observed_v6_sha = _patch_v6_failure_vector(
        cast(Sequence[MutableMapping[str, JsonValue]], final_rows)
    )
    combined = ResourceCounterState(dict(counters._values))
    combined.merge_legacy(legacy.snapshot())
    observed_counters = combined.snapshot()
    grids, supports = _reference_occurrences(final_rows)
    grid_table = grid_registry.as_json()
    support_table = support_registry.as_json()
    try:
        _reference.validate_grid_evidence_table(
            grid_table, expected_references=grids
        )
    except _reference.GridEvidenceTableError as error:
        raise GlobalFallbackRequired("grid_evidence_table_invalid") from error
    try:
        _reference.validate_expected_exterior_support_table(
            support_table, expected_references=supports
        )
    except _reference.ExteriorSupportTableError as error:
        raise GlobalFallbackRequired("expected_exterior_support_table_invalid") from error
    aggregates = _derive_aggregates(
        final_rows, observed_counters, observed_v6_sha=observed_v6_sha
    )
    construction_defects = {
        "base_pipeline_unavailable",
        "transformed_pipeline_unavailable",
        "pipeline_snapshot_invalid",
        "isolated_action_map_not_bijective",
        "isolated_action_map_not_canonical_order_preserving",
        "isolated_signature_transform_not_injective",
        "resource_counter_mismatch",
        "forbidden_resource_use",
    }
    reason_counts = cast(Mapping[str, int], aggregates["reason_counts"])
    diagnostic_complete = (
        len(final_rows) == 140
        and all(row["disposition"] == "completed" for row in final_rows)
        and aggregates["resource_contract_passes"] is True
        and all(reason_counts[reason] == 0 for reason in construction_defects)
    )
    payload: dict[str, JsonValue] = {
        **_payload_prefix(registration, root, observed_counters),
        "grid_evidence": grid_table,
        "expected_exterior_support": support_table,
        "rows": cast(JsonValue, final_rows),
        "aggregates": aggregates,
        "diagnostic_complete": diagnostic_complete,
        "scientific_capability_passes": False,
        "authorization": dict(AUTHORIZATION),
        "terminal_fallback_stage": None,
        "candidate_payload_size_bytes": None,
    }
    _require_exact_keys(payload, TOP_LEVEL_KEYS, "scientific payload")
    return payload


def finalize_scientific_payload(
    candidate: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
    *,
    candidate_payload_size_bytes: int | None = None,
) -> dict[str, JsonValue]:
    """Build all conclusions in one authority and apply the frozen fallback precedence."""

    root_value = candidate.get("repository_root") if isinstance(candidate, Mapping) else None
    root: Path | str = root_value if isinstance(root_value, (str, Path)) else "."
    try:
        payload = _finalize_candidate(candidate, registration)
    except GlobalFallbackRequired as error:
        return build_global_fallback(
            registration,
            error.stage,
            repository_root=root,
        )
    except Exception:
        return build_global_fallback(
            registration,
            "evaluator_internal_error",
            repository_root=root,
        )
    measured = (
        candidate_payload_size_bytes
        if candidate_payload_size_bytes is not None
        else len(canonical_json_bytes(payload))
    )
    if isinstance(measured, bool) or not isinstance(measured, int) or measured < 0:
        return build_global_fallback(
            registration,
            "evaluator_internal_error",
            repository_root=root,
        )
    if measured > PAYLOAD_CAP_BYTES:
        return build_global_fallback(
            registration,
            "payload_size_limit_exceeded",
            candidate_payload_size_bytes=measured,
            repository_root=root,
        )
    return payload


def _validate_layer_envelope(value: object, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise V7AuditError(f"{name} layer is not an object")
    _require_exact_keys(value, ("status", "passes", "reasons", "details"), name)
    status = value.get("status")
    passes = value.get("passes")
    reasons = value.get("reasons")
    details = value.get("details")
    if status not in {"evaluated", "precondition_failed"} or not isinstance(passes, bool):
        raise V7AuditError(f"{name} layer status/pass is invalid")
    if (
        not isinstance(reasons, list)
        or any(not isinstance(reason, str) or reason not in REASON_INDEX for reason in reasons)
        or reasons != list(ordered_reasons(cast(Iterable[str], reasons)))
    ):
        raise V7AuditError(f"{name} layer reasons are invalid")
    if passes is not (status == "evaluated" and not reasons):
        raise V7AuditError(f"{name} layer pass equation failed")
    if not isinstance(details, Mapping):
        raise V7AuditError(f"{name} layer details are not an object")
    expected_keys = LAYER_DETAIL_KEYS.get(name)
    if expected_keys is None:
        raise V7AuditError(f"unknown scientific layer: {name}")
    _require_exact_keys(details, expected_keys, f"{name}.details")
    return copy.deepcopy(cast(dict[str, JsonValue], dict(value)))


def _validate_evidence(value: object, kind: str) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise V7AuditError("completed row evidence is not an object")
    expected = (
        BASE_EVIDENCE_KEYS
        if kind == "base_scene"
        else VISUAL_EVIDENCE_KEYS
        if kind == "visual_transform"
        else ORDER_EVIDENCE_KEYS
        if kind == "order_transform"
        else CONTROL_EVIDENCE_KEYS
        if kind == "control"
        else ()
    )
    if not expected:
        raise V7AuditError("row kind has no registered evidence schema")
    _require_exact_keys(value, expected, f"{kind} evidence")
    return {
        name: _validate_layer_envelope(value[name], name) for name in expected
    }


def _expected_v6_hash_from_rows(rows: Sequence[Mapping[str, Any]]) -> str | None:
    applicable: list[Mapping[str, Any]] = []
    failing: list[JsonValue] = []
    for row in rows:
        registered = row.get("registered_row")
        evidence = row.get("evidence")
        if (
            row.get("disposition") != "completed"
            or not isinstance(registered, Mapping)
            or registered.get("kind") != "visual_transform"
            or registered.get("scene_index") != 0
            or not isinstance(evidence, Mapping)
        ):
            continue
        reproduction = evidence.get("v6_reproduction")
        details = reproduction.get("details") if isinstance(reproduction, Mapping) else None
        observed = details.get("observed_comparison") if isinstance(details, Mapping) else None
        if not isinstance(observed, Mapping):
            continue
        applicable.append(cast(Mapping[str, Any], details))
        if observed.get("passes") is not True:
            failing.append(
                {
                    "family": registered.get("family"),
                    "transform_name": registered.get("transform_name"),
                    "comparison": copy.deepcopy(dict(observed)),
                }
            )
    if len(applicable) != 12:
        return None
    digest = canonical_sha256(failing)
    if any(details.get("observed_failure_vector_sha256") != digest for details in applicable):
        raise V7AuditError("rowwise observed v6 vector hashes disagree")
    return digest


def _validate_identity_boundary(
    payload: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
    counters: Mapping[str, int],
) -> None:
    if payload.get("preregistration_identity") != registration.get("preregistration"):
        raise V7AuditError("payload preregistration identity differs from registration")
    if payload.get("v6_negative_identity") != registration.get("v6_negative"):
        raise V7AuditError("payload v6 identity differs from registration")
    registration_identity = payload.get("registration_identity")
    execution_identity = payload.get("execution_identity")
    if not isinstance(registration_identity, Mapping) or not isinstance(
        execution_identity, Mapping
    ):
        raise V7AuditError("payload execution identities are malformed")
    _require_exact_keys(
        registration_identity,
        ("schema_version", "path", "content_sha256", "file_sha256"),
        "registration identity",
    )
    _require_exact_keys(
        execution_identity,
        (
            "open_freeze_commit_sha",
            "open_freeze_tag",
            "source_manifest_sha256",
            "python_version",
            "python_implementation",
            "platform_system",
            "platform_machine",
            "uv_version",
            "uv_lock_sha256",
            "canonical_command_sha256",
        ),
        "execution identity",
    )
    if (
        registration_identity.get("schema_version") != REGISTRATION_SCHEMA_VERSION
        or registration_identity.get("path")
        != "artifacts/action_qbc_v7_open_registration.json"
        or registration_identity.get("content_sha256")
        != registration.get("content_sha256")
    ):
        raise V7AuditError("registration identity constants differ")
    platform_registration = registration.get("platform")
    source_manifest = registration.get("source_manifest")
    execution_contract = registration.get("execution_contract")
    if not all(
        isinstance(value, Mapping)
        for value in (platform_registration, source_manifest, execution_contract)
    ):
        raise V7AuditError("registration execution boundary is malformed")
    argv_hashes = cast(Mapping[str, Any], execution_contract).get("argv_hashes")
    if not isinstance(argv_hashes, Mapping):
        raise V7AuditError("registration command hashes are malformed")
    root = Path.cwd().resolve(strict=True)
    expected_file_sha256 = _registration_file_sha256(root, registration)
    expected_head = _git_head(root)
    expected_uv_lock_sha256 = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    if registration_identity.get("file_sha256") != expected_file_sha256:
        raise V7AuditError("registration file identity differs from observed bytes")
    expected_values = {
        "open_freeze_commit_sha": expected_head,
        "open_freeze_tag": OPEN_FREEZE_TAG,
        "source_manifest_sha256": cast(Mapping[str, Any], source_manifest).get(
            "manifest_sha256"
        ),
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "uv_version": "0.11.28",
        "uv_lock_sha256": expected_uv_lock_sha256,
        "canonical_command_sha256": argv_hashes.get("scientific"),
    }
    if any(execution_identity.get(key) != value for key, value in expected_values.items()):
        raise V7AuditError("execution identity constants differ from registration")
    del counters


def _validate_global_fallback(
    payload: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
    counters: Mapping[str, int],
) -> None:
    stage = payload.get("terminal_fallback_stage")
    if stage not in GLOBAL_FALLBACK_STAGE_ORDER:
        raise V7AuditError("fallback stage is not registered")
    size = payload.get("candidate_payload_size_bytes")
    if stage == "payload_size_limit_exceeded":
        if isinstance(size, bool) or not isinstance(size, int) or size <= PAYLOAD_CAP_BYTES:
            raise V7AuditError("size fallback does not retain its oversized byte count")
    elif size is not None:
        raise V7AuditError("non-size fallback retained a candidate byte count")
    if payload.get("grid_evidence") != _empty_grid_table() or payload.get(
        "expected_exterior_support"
    ) != _empty_exterior_table():
        raise V7AuditError("global fallback evidence tables are not empty")
    rows = payload.get("rows")
    registered_rows = _registered_rows(registration)
    if not isinstance(rows, list) or len(rows) != len(registered_rows):
        raise V7AuditError("global fallback row inventory is invalid")
    expected_status = (
        "evaluator_internal_error"
        if stage == "evaluator_internal_error"
        else "payload_size_limit_exceeded"
        if stage == "payload_size_limit_exceeded"
        else "authoritative_derivation_error"
    )
    for row, registered in zip(rows, registered_rows, strict=True):
        if not isinstance(row, Mapping):
            raise V7AuditError("global fallback row is malformed")
        _require_exact_keys(
            row,
            ("address", "registered_row", "disposition", "evidence", "terminal"),
            "global fallback row",
        )
        _validate_address(row["address"], registered)
        if (
            row.get("registered_row") != registered
            or row.get("disposition") != "terminal_global_negative"
            or row.get("evidence") != {}
            or row.get("terminal") != {"status": expected_status, "stage": stage}
        ):
            raise V7AuditError("global fallback row disposition differs")
    if payload.get("aggregates") != _empty_aggregates(counters):
        raise V7AuditError("global fallback aggregates differ from the frozen object")
    if payload.get("diagnostic_complete") is not False:
        raise V7AuditError("global fallback cannot be diagnostically complete")


def _validate_normal_rows(
    payload: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
    counters: Mapping[str, int],
) -> None:
    if payload.get("terminal_fallback_stage") is not None or payload.get(
        "candidate_payload_size_bytes"
    ) is not None:
        raise V7AuditError("normal payload contains fallback metadata")
    rows_value = payload.get("rows")
    registered_rows = _registered_rows(registration)
    if not isinstance(rows_value, list) or len(rows_value) != len(registered_rows):
        raise V7AuditError("normal row inventory differs from registration")
    validated_rows: list[dict[str, JsonValue]] = []
    for row, registered in zip(rows_value, registered_rows, strict=True):
        if not isinstance(row, Mapping):
            raise V7AuditError("normal row is not an object")
        _require_exact_keys(
            row,
            ("address", "registered_row", "disposition", "evidence", "terminal"),
            "normal row",
        )
        _validate_address(row["address"], registered)
        if row.get("registered_row") != registered:
            raise V7AuditError("normal row registration injection differs")
        disposition = row.get("disposition")
        if disposition == "completed":
            if row.get("terminal") is not None:
                raise V7AuditError("completed row has a terminal object")
            evidence = _validate_evidence(row.get("evidence"), cast(str, registered["kind"]))
        elif disposition == "terminal_addressable_negative":
            if (
                row.get("evidence") != {}
                or row.get("terminal")
                != {
                    "status": "authoritative_derivation_error",
                    "stage": "scientific_record_schema_invalid",
                }
            ):
                raise V7AuditError("addressable terminal row differs")
            evidence = {}
        else:
            raise V7AuditError("normal row has an invalid disposition")
        validated_rows.append(
            {
                "address": copy.deepcopy(cast(dict[str, JsonValue], dict(row["address"]))),
                "registered_row": copy.deepcopy(dict(registered)),
                "disposition": cast(str, disposition),
                "evidence": evidence,
                "terminal": cast(JsonValue, copy.deepcopy(row.get("terminal"))),
            }
        )
    grids, supports = _reference_occurrences(validated_rows)
    try:
        _reference.validate_grid_evidence_table(
            payload.get("grid_evidence"), expected_references=grids
        )
    except _reference.GridEvidenceTableError as error:
        raise V7AuditError("normal grid-evidence table is invalid") from error
    try:
        _reference.validate_expected_exterior_support_table(
            payload.get("expected_exterior_support"), expected_references=supports
        )
    except _reference.ExteriorSupportTableError as error:
        raise V7AuditError("normal exterior-support table is invalid") from error
    observed_v6 = _expected_v6_hash_from_rows(validated_rows)
    expected_aggregates = _derive_aggregates(
        validated_rows, counters, observed_v6_sha=observed_v6
    )
    if payload.get("aggregates") != expected_aggregates:
        raise V7AuditError("normal aggregate object does not rederive")
    reason_counts = cast(Mapping[str, int], expected_aggregates["reason_counts"])
    defect_reasons = (
        "base_pipeline_unavailable",
        "transformed_pipeline_unavailable",
        "pipeline_snapshot_invalid",
        "isolated_action_map_not_bijective",
        "isolated_action_map_not_canonical_order_preserving",
        "isolated_signature_transform_not_injective",
        "resource_counter_mismatch",
        "forbidden_resource_use",
    )
    expected_complete = (
        all(row["disposition"] == "completed" for row in validated_rows)
        and expected_aggregates["resource_contract_passes"] is True
        and all(reason_counts[reason] == 0 for reason in defect_reasons)
    )
    if payload.get("diagnostic_complete") is not expected_complete:
        raise V7AuditError("diagnostic completeness does not rederive")


def validate_scientific_payload(
    payload: Mapping[str, Any],
    registration: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    """Strictly validate and canonically replay a complete normal or fallback payload."""

    if not isinstance(payload, Mapping):
        raise V7AuditError("scientific payload is not an object")
    _require_exact_keys(payload, TOP_LEVEL_KEYS, "scientific payload")
    if (
        payload.get("schema_version") != SCIENTIFIC_SCHEMA_VERSION
        or payload.get("treatment_id") != TREATMENT_ID
        or payload.get("diagnostic_system_id") != DIAGNOSTIC_SYSTEM_ID
        or payload.get("comparison_semantics_id") != COMPARISON_SEMANTICS_ID
        or payload.get("runtime_id") is not None
        or payload.get("scientific_capability_passes") is not False
        or payload.get("authorization") != dict(AUTHORIZATION)
    ):
        raise V7AuditError("scientific payload fixed identity differs")
    counters = validate_resource_counters(payload.get("resource_counters"))
    _validate_identity_boundary(payload, registration, counters)
    if payload.get("terminal_fallback_stage") is None:
        _validate_normal_rows(payload, registration, counters)
    else:
        _validate_global_fallback(payload, registration, counters)
    try:
        encoded = canonical_json_bytes(cast(JsonValue, dict(payload)))
        replay = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise V7AuditError("scientific payload cannot be canonically replayed") from error
    if len(encoded) > PAYLOAD_CAP_BYTES:
        raise V7AuditError("scientific payload exceeds the registered cap")
    return cast(dict[str, JsonValue], replay)


__all__ = [
    "ABSOLUTE_TOLERANCE",
    "AGGREGATE_KEYS",
    "AUTHORIZATION",
    "COMPARISON_SEMANTICS_ID",
    "CONTROL_IDS",
    "DIAGNOSTIC_SYSTEM_ID",
    "EXPECTED_RESOURCE_COUNTS",
    "GLOBAL_FALLBACK_STAGE_ORDER",
    "PAYLOAD_CAP_BYTES",
    "PREREGISTRATION_COMMIT",
    "PREREGISTRATION_TAG",
    "REASON_ORDER",
    "RESOURCE_COUNTER_NAMES",
    "SCIENTIFIC_SCHEMA_VERSION",
    "TREATMENT_ID",
    "VISUAL_TRANSFORMS",
    "AddressableRecordError",
    "ControlPrimitive",
    "GlobalFallbackRequired",
    "OrderPrimitive",
    "PipelinePrimitive",
    "ResourceCounterState",
    "TransportPrimitive",
    "V7AuditError",
    "VisualPrimitive",
    "build_global_fallback",
    "canonical_json_bytes",
    "canonical_sha256",
    "derive_base_evidence",
    "derive_visual_evidence",
    "finalize_scientific_payload",
    "load_registration",
    "produce_scientific_candidate",
    "resource_contract_passes",
    "validate_resource_counters",
    "validate_scientific_payload",
]
