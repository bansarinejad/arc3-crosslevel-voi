"""Stdlib-only pair validation and publication for the action-QBC v7 diagnostic."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import platform
import stat
import struct
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

_REGISTRATION_SCHEMA = "action-qbc-v7-open-registration-v1"
_PAYLOAD_SCHEMA = "action-qbc-v7-open-diagnostic-payload-v1"
_RECEIPT_SCHEMA = "action-qbc-v7-open-diagnostic-receipt-v1"
_ADMIN_SCHEMA = "action-qbc-v7-open-diagnostic-administrative-terminal-v1"
_TREATMENT_ID = "action-qbc-v7-open-failure-decomposition-v1"
_DIAGNOSTIC_SYSTEM_ID = "crosslevel-voi-open-diagnostic-v7"
_COMPARISON_ID = "action-qbc-v7-boundary-compound-selector-decomposition-v1"
_OPEN_FREEZE_TAG = "action-qbc-v7-open-diagnostic-freeze-v1"
_FINALIZER_CWD = "/mnt/d/kaggle competitions/arc3-crosslevel-voi"
_PAYLOAD_CAP_BYTES = 67_108_864
_EXPECTED_REGISTRATION = "artifacts/action_qbc_v7_open_registration.json"
_EXPECTED_PROCESS_A = (
    "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/"
    "action_qbc_v7_open_diagnostic.json"
)
_EXPECTED_PROCESS_B = (
    "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/"
    "action_qbc_v7_open_diagnostic.json"
)
_EXPECTED_PUBLISH = "artifacts/action_qbc_v7_open_diagnostic.json"
_EXPECTED_RECEIPT = "artifacts/action_qbc_v7_open_diagnostic_receipt.json"
_EXPECTED_ADMIN = "artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"
_PREREGISTRATION_COMMIT = "f4a267757a7abbd72bc1aeb86e98811c521bf574"
_PREREGISTRATION_TAG = "prereg-action-qbc-v7-open-failure-decomposition-v1"
_PREREGISTRATION_DOCUMENT = (
    "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md"
)
_PREREGISTRATION_DOCUMENT_SHA256 = (
    "fcd284ce499983fcc953f54a9f833e1b6d80a822384768f75cb18948d627a1a7"
)
_V6_RESULT_COMMIT = "6a7f6fb25b7e676d6aff5aecaaa26de63e436481"
_V6_RESULT_PATH = "artifacts/action_qbc_v6_open_gate_result.json"
_V6_RESULT_SHA256 = "853394f0b68bddaac9b5c1840e8afa51ffeba444920b132ad45b8d53740c751d"
_V6_FAILURE_SHA256 = "589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055"
_V6_DOCUMENT_SHA256 = "a3bf5b20291d1b35f65b7fa20de7b9c6247ba918265eab588c6a34f66ff64c59"
_OPEN_ADDED_PATHS = {
    "docs/action_qbc_v7_open_diagnostic_runbook.md",
    "scripts/build_action_qbc_v7_open_registration.py",
    "scripts/finalize_action_qbc_v7_open_diagnostic.py",
    "scripts/reconstruct_action_qbc_v7_open_registration.py",
    "scripts/run_action_qbc_v7_open_diagnostic.py",
    "src/arc3_voi/action_qbc_v7_audit.py",
    "src/arc3_voi/action_qbc_v7_reference.py",
    "tests/test_action_qbc_v7_audit.py",
    "tests/test_action_qbc_v7_registration.py",
}
_EXPECTED_RESOURCE_COUNTS = {
    "public_scene_generations": 12,
    "registered_scene_file_reads": 0,
    "candidate_builder_calls": 48,
    "compiler_calls": 60,
    "compiled_programs": 240,
    "grounding_evaluations": 240,
    "hypothesis_pool_constructions": 60,
    "persistent_worker_starts": 240,
    "transient_worker_starts": 240,
    "total_worker_starts": 480,
    "planner_calls": 60,
    "completed_planning_snapshots": 60,
    "controller_calls": 96,
    "controller_snapshot_replays": 96,
    "v4_counterfactual_calls": 12,
    "raw_selector_scene_order_calls": 216,
    "raw_selector_control_calls": 19,
    "fixed_selector_scene_order_calls": 120,
    "fixed_selector_control_calls": 19,
    "isolated_raw_selector_calls": 96,
    "isolated_fixed_selector_calls": 96,
    "pure_selector_calls": 566,
    "model_calls": 0,
    "generated_tokens": 0,
    "gpu_operations": 0,
    "network_calls": 0,
    "environment_actions": 0,
    "reward_observations": 0,
    "rhae_observations": 0,
    "lockbox_path_operations": 0,
    "lockbox_bytes_read": 0,
}

_AUTHORIZATION = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v7_enabled": False,
    "final_admission_claimed": False,
}
_ADMIN_STAGES = [
    "tag_verification_failed",
    "execution_root_setup_failed",
    "clone_a_failed",
    "clone_b_failed",
    "environment_a_failed",
    "environment_b_failed",
    "preflight_a_failed",
    "preflight_b_failed",
    "registration_invalid",
    "process_a_nonzero",
    "process_a_output_missing",
    "process_a_payload_invalid",
    "process_b_nonzero",
    "process_b_output_missing",
    "process_b_payload_invalid",
    "payload_byte_mismatch",
    "receipt_finalization_failed",
    "exclusive_publication_failed",
    "publication_rollback_failed",
]
_GLOBAL_STAGES = [
    "transform_action_map_invalid",
    "scientific_record_inventory_invalid",
    "grid_evidence_table_invalid",
    "expected_exterior_support_table_invalid",
    "evaluator_internal_error",
    "payload_size_limit_exceeded",
]

_REGISTRATION_KEYS = {
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
}
_EXECUTION_KEYS = {
    "compute_deadline_seconds",
    "wall_time_seconds",
    "hard_timeout_seconds",
    "registered_start_count",
    "process_labels",
    "execution_root",
    "process_a_root",
    "process_b_root",
    "process_a_output",
    "process_b_output",
    "producer_argv",
    "reconstructor_argv",
    "tag_verification_step",
    "setup_steps",
    "environment_build_argv",
    "preflight_argvs",
    "scientific_argv_template",
    "test_argvs",
    "finalizer_argv_template",
    "finalizer_cwd",
    "argv_hashes",
    "administrative_stage_order",
    "third_start_allowed",
}
_PAYLOAD_KEYS = {
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
}
_PROCESS_KEYS = {
    "label",
    "output_path",
    "exit_code",
    "payload_exists",
    "payload_valid",
    "payload_sha256",
    "payload_size_bytes",
}
_RECEIPT_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "process_a",
    "process_b",
    "payloads_byte_identical",
    "published_payload_path",
    "published_payload_sha256",
    "authorization",
}
_ADMIN_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "stage",
    "process_a",
    "process_b",
    "payloads_byte_identical",
    "authorization",
}
_PREREGISTRATION_KEYS = {
    "commit_sha",
    "tag",
    "document_path",
    "document_git_blob_sha1",
    "document_sha256",
}
_V6_KEYS = {
    "result_commit_sha",
    "result_json_path",
    "result_json_sha256",
    "failure_vector_sha256",
    "result_document_sha256",
}
_REGISTRATION_IDENTITY_KEYS = {"schema_version", "path", "content_sha256", "file_sha256"}
_EXECUTION_IDENTITY_KEYS = {
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
}
_ROW_KEYS = {"address", "registered_row", "disposition", "evidence", "terminal"}
_ADDRESS_KEYS = {"row_index", "row_id", "kind"}
_LAYER_KEYS = {"status", "passes", "reasons", "details"}
_TERMINAL_KEYS = {"status", "stage"}
_GRID_BLOB_KEYS = {"reference", "encoding", "shape", "byte_count", "data_base64", "sha256"}
_SUPPORT_BLOB_KEYS = {
    "reference",
    "encoding",
    "entry_count",
    "byte_count",
    "data_base64",
    "sha256",
}

_EVIDENCE_KEYS = {
    "base_scene": {
        "pipeline",
        "raw_selector",
        "fixed_selector",
        "structural",
        "mechanism",
        "v4_counterfactual",
        "prepreregistered_reproduction",
    },
    "visual_transform": {
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
    },
    "order_transform": {
        "order_transform",
        "raw_selector_relation",
        "fixed_selector_relation",
    },
    "control": {"raw_control", "fixed_control"},
}


class _ValidationError(ValueError):
    """Canonical registration, payload, or receipt validation failed."""


class _PublicationError(RuntimeError):
    """A transactional publication operation failed."""


@dataclass(frozen=True, slots=True)
class _Registration:
    value: dict[str, Any]
    data: bytes
    file_sha256: str
    path_text: str


@dataclass(frozen=True, slots=True)
class _RepositoryIdentity:
    commit_sha: str
    tag_valid: bool


@dataclass(frozen=True, slots=True)
class _ProcessObservation:
    record: dict[str, Any]
    data: bytes | None


@dataclass(frozen=True, slots=True)
class _StagedFile:
    path: Path
    data: bytes
    sha256: str
    device: int
    inode: int


def _raise(message: str) -> NoReturn:
    raise _ValidationError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise _ValidationError("value is not canonical-JSON encodable") from exc


def _reject_constant(value: str) -> NoReturn:
    raise _ValidationError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _raise(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _parse_canonical_json(data: bytes, name: str) -> Any:
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ValidationError(f"{name} is not strict UTF-8 JSON") from exc
    if _canonical_json_bytes(value) != data:
        _raise(f"{name} is not the exact canonical JSON byte sequence")
    return value


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise(f"{name} is not an object")
    return value


def _require_keys(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        _raise(f"{name} has an invalid key set")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_nonnegative_int(value: Any, name: str) -> int:
    if not _is_int(value) or value < 0:
        _raise(f"{name} is not a non-negative integer")
    return value


def _require_sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _raise(f"{name} is not a lowercase SHA-256")
    return value


def _require_sha1(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _raise(f"{name} is not a lowercase Git SHA-1")
    return value


def _read_plain_file(path: Path, name: str, *, maximum: int | None = None) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ValidationError(f"{name} is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        _raise(f"{name} is not a plain file")
    if maximum is not None and metadata.st_size > maximum:
        _raise(f"{name} exceeds its byte limit")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise _ValidationError(f"{name} cannot be read") from exc


def _validate_argv_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        _raise(f"{name} is not a non-empty argv list")
    return value


def _validate_registration(path: Path, path_text: str) -> _Registration:
    data = _read_plain_file(path, "registration")
    registration = _require_mapping(_parse_canonical_json(data, "registration"), "registration")
    _require_keys(registration, _REGISTRATION_KEYS, "registration")
    if (
        registration["schema_version"] != _REGISTRATION_SCHEMA
        or registration["status"] != "registered_zero_result"
        or registration["treatment_id"] != _TREATMENT_ID
        or registration["diagnostic_system_id"] != _DIAGNOSTIC_SYSTEM_ID
        or registration["comparison_semantics_id"] != _COMPARISON_ID
        or registration["runtime_id"] is not None
        or registration["authorization"] != _AUTHORIZATION
    ):
        _raise("registration fixed identity is invalid")
    content = {key: value for key, value in registration.items() if key != "content_sha256"}
    expected_content_sha = _sha256(_canonical_json_bytes(content))
    if registration["content_sha256"] != expected_content_sha:
        _raise("registration content_sha256 is invalid")

    preregistration = _require_mapping(registration["preregistration"], "preregistration")
    _require_keys(preregistration, _PREREGISTRATION_KEYS, "preregistration")
    _require_sha1(preregistration["commit_sha"], "preregistration.commit_sha")
    _require_sha1(preregistration["document_git_blob_sha1"], "document_git_blob_sha1")
    _require_sha256(preregistration["document_sha256"], "document_sha256")
    if (
        preregistration["commit_sha"] != _PREREGISTRATION_COMMIT
        or preregistration["tag"] != _PREREGISTRATION_TAG
        or preregistration["document_path"] != _PREREGISTRATION_DOCUMENT
        or preregistration["document_sha256"] != _PREREGISTRATION_DOCUMENT_SHA256
    ):
        _raise("registration preregistration anchor is invalid")
    v6 = _require_mapping(registration["v6_negative"], "v6_negative")
    _require_keys(v6, _V6_KEYS, "v6_negative")
    _require_sha1(v6["result_commit_sha"], "v6 result commit")
    for key in ("result_json_sha256", "failure_vector_sha256", "result_document_sha256"):
        _require_sha256(v6[key], f"v6_negative.{key}")
    if v6 != {
        "result_commit_sha": _V6_RESULT_COMMIT,
        "result_json_path": _V6_RESULT_PATH,
        "result_json_sha256": _V6_RESULT_SHA256,
        "failure_vector_sha256": _V6_FAILURE_SHA256,
        "result_document_sha256": _V6_DOCUMENT_SHA256,
    }:
        _raise("registration v6 anchor is invalid")

    expected_platform = {
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "uv_version": "0.11.28",
    }
    if registration["platform"] != expected_platform:
        _raise("registration platform is invalid")
    expected_dependencies = [
        {"name": "arc3-crosslevel-voi", "version": "0.1.0", "editable": True},
        {"name": "numpy", "version": "2.5.1", "editable": False},
        {"name": "PyYAML", "version": "6.0.3", "editable": False},
    ]
    if registration["dependencies"] != expected_dependencies:
        _raise("registration dependency inventory is invalid")

    manifest = _require_mapping(registration["source_manifest"], "source_manifest")
    _require_keys(
        manifest,
        {"preregistration_tree", "open_freeze_added_files", "manifest_sha256"},
        "source_manifest",
    )
    manifest_preimage = {
        "preregistration_tree": manifest["preregistration_tree"],
        "open_freeze_added_files": manifest["open_freeze_added_files"],
    }
    if manifest["manifest_sha256"] != _sha256(_canonical_json_bytes(manifest_preimage)):
        _raise("source manifest digest is invalid")
    seen_paths: set[str] = set()
    for inventory_name in ("preregistration_tree", "open_freeze_added_files"):
        inventory = manifest[inventory_name]
        if not isinstance(inventory, list):
            _raise(f"source_manifest.{inventory_name} is not a list")
        paths: list[str] = []
        for index, entry_value in enumerate(inventory):
            entry = _require_mapping(entry_value, f"{inventory_name}[{index}]")
            _require_keys(entry, {"path", "git_blob_sha1", "sha256", "byte_count"}, "manifest row")
            path_value = entry["path"]
            if not isinstance(path_value, str) or not path_value or path_value.startswith("/"):
                _raise("source manifest path is invalid")
            if path_value in seen_paths:
                _raise("source manifest contains a duplicate path")
            seen_paths.add(path_value)
            paths.append(path_value)
            _require_sha1(entry["git_blob_sha1"], "manifest git blob")
            _require_sha256(entry["sha256"], "manifest SHA-256")
            _require_nonnegative_int(entry["byte_count"], "manifest byte_count")
        if paths != sorted(paths):
            _raise(f"source_manifest.{inventory_name} is not path sorted")
    if {
        entry["path"] for entry in manifest["open_freeze_added_files"]
    } != _OPEN_ADDED_PATHS:
        _raise("source manifest open-freeze path inventory is invalid")
    document_entries = [
        entry
        for entry in manifest["preregistration_tree"]
        if entry["path"] == _PREREGISTRATION_DOCUMENT
    ]
    if (
        len(document_entries) != 1
        or document_entries[0]["sha256"] != _PREREGISTRATION_DOCUMENT_SHA256
        or document_entries[0]["git_blob_sha1"]
        != preregistration["document_git_blob_sha1"]
    ):
        _raise("source manifest does not bind the preregistration document")

    scene_inventory = _require_mapping(registration["scene_inventory"], "scene_inventory")
    _require_keys(scene_inventory, {"count", "scenes"}, "scene_inventory")
    if (
        scene_inventory["count"] != 12
        or not isinstance(scene_inventory["scenes"], list)
        or len(scene_inventory["scenes"]) != 12
    ):
        _raise("registered scene inventory is invalid")
    if not isinstance(registration["transform_contracts"], list) or len(
        registration["transform_contracts"]
    ) != 48:
        _raise("registered transform-contract inventory is invalid")

    row_inventory = _require_mapping(registration["row_inventory"], "row_inventory")
    _require_keys(row_inventory, {"count", "order", "rows"}, "row_inventory")
    rows = row_inventory["rows"]
    if (
        row_inventory["count"] != 140
        or row_inventory["order"]
        != "base-all-scenes_then-visual-all-scenes_then-order-all-scenes_then-controls-v1"
        or not isinstance(rows, list)
        or len(rows) != 140
    ):
        _raise("registered row inventory is invalid")
    row_ids: set[str] = set()
    kind_keys = {
        "base_scene": {"family", "scene_index", "seed_hex", "scene_sha256"},
        "visual_transform": {
            "family",
            "scene_index",
            "seed_hex",
            "scene_sha256",
            "transform_name",
            "transform_contract_sha256",
            "actual_action_map_sha256",
            "isolated_action_map_sha256",
        },
        "order_transform": {
            "family",
            "scene_index",
            "seed_hex",
            "scene_sha256",
            "transform_name",
            "order_contract_sha256",
        },
        "control": {
            "control_id",
            "control_index",
            "raw_selector_call_count",
            "fixed_selector_call_count",
            "control_contract_sha256",
            "raw_predicate_id",
            "fixed_predicate_id",
        },
    }
    for index, row_value in enumerate(rows):
        row = _require_mapping(row_value, f"registered row {index}")
        kind = row.get("kind")
        if kind not in kind_keys:
            _raise("registered row kind is invalid")
        expected_keys = {
            "row_index",
            "row_id",
            "kind",
            "registered_placeholder",
        } | kind_keys[kind]
        _require_keys(row, expected_keys, f"registered row {index}")
        if row["row_index"] != index or row["registered_placeholder"] is not True:
            _raise("registered row index/placeholder is invalid")
        row_id = row["row_id"]
        if not isinstance(row_id, str) or row_id in row_ids:
            _raise("registered row ID is invalid or duplicated")
        row_ids.add(row_id)

    scientific = _require_mapping(registration["scientific_contract"], "scientific_contract")
    required_scientific = {
        "role_order",
        "raw_selector_identity",
        "fixed_selector_identity",
        "absolute_tolerance",
        "relative_tolerance",
        "fixed_quantum_numerator",
        "fixed_quantum_denominator",
        "reason_order",
        "grid_evidence_schema",
        "expected_exterior_support_schema",
        "aggregate_keys",
        "global_fallback_stage_order",
        "payload_cap_bytes",
        "order_contracts",
    }
    _require_keys(scientific, required_scientific, "scientific_contract")
    if (
        scientific["payload_cap_bytes"] != _PAYLOAD_CAP_BYTES
        or scientific["global_fallback_stage_order"] != _GLOBAL_STAGES
        or scientific["grid_evidence_schema"] != "action-qbc-v7-grid-evidence-table-v1"
        or scientific["expected_exterior_support_schema"]
        != "action-qbc-v7-expected-exterior-support-table-v1"
    ):
        _raise("scientific contract constants are invalid")
    reason_order = scientific["reason_order"]
    if not isinstance(reason_order, list) or len(set(reason_order)) != len(reason_order):
        _raise("scientific reason order is invalid")
    if not isinstance(scientific["aggregate_keys"], list) or len(
        set(scientific["aggregate_keys"])
    ) != len(scientific["aggregate_keys"]):
        _raise("scientific aggregate key list is invalid")

    resource = _require_mapping(registration["resource_contract"], "resource_contract")
    _require_keys(
        resource,
        {"expected_counts", "control_call_ledger", "control_contract_sha256", "increment_contract"},
        "resource_contract",
    )
    expected_counts = _require_mapping(resource["expected_counts"], "expected_counts")
    if expected_counts != _EXPECTED_RESOURCE_COUNTS:
        _raise("expected resource counter inventory is invalid")
    for key, value in expected_counts.items():
        if not isinstance(key, str):
            _raise("resource counter name is invalid")
        _require_nonnegative_int(value, f"expected_counts.{key}")

    execution = _require_mapping(registration["execution_contract"], "execution_contract")
    _require_keys(execution, _EXECUTION_KEYS, "execution_contract")
    if (
        execution["compute_deadline_seconds"] != 2100
        or execution["wall_time_seconds"] != 2400
        or execution["hard_timeout_seconds"] != 2700
        or execution["registered_start_count"] != 2
        or execution["process_labels"] != ["A", "B"]
        or execution["process_a_output"] != _EXPECTED_PROCESS_A
        or execution["process_b_output"] != _EXPECTED_PROCESS_B
        or execution["finalizer_cwd"] != _FINALIZER_CWD
        or execution["administrative_stage_order"] != _ADMIN_STAGES
        or execution["third_start_allowed"] is not False
    ):
        _raise("execution contract constants are invalid")
    execution_root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open"
    process_a_root = f"{execution_root}/process-a"
    process_b_root = f"{execution_root}/process-b"
    if (
        execution["execution_root"] != execution_root
        or execution["process_a_root"] != process_a_root
        or execution["process_b_root"] != process_b_root
    ):
        _raise("execution root contract is invalid")
    expected_tag_step = {
        "argv": [
            "git",
            "ls-remote",
            "--tags",
            "https://github.com/bansarinejad/arc3-crosslevel-voi.git",
            f"refs/tags/{_OPEN_FREEZE_TAG}",
        ],
        "cwd": "/var/tmp",
        "expected_exit_code": 0,
        "expected_stdout": f"<O_COMMIT>\trefs/tags/{_OPEN_FREEZE_TAG}\n",
    }
    expected_setup = [
        {
            "argv": ["/usr/bin/test", "!", "-e", execution_root],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
        {
            "argv": ["install", "-d", "-m", "700", execution_root],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
        {
            "argv": [
                "git",
                "clone",
                "--branch",
                _OPEN_FREEZE_TAG,
                "--single-branch",
                "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi",
                process_a_root,
            ],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
        {
            "argv": [
                "git",
                "clone",
                "--branch",
                _OPEN_FREEZE_TAG,
                "--single-branch",
                "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi",
                process_b_root,
            ],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
        {
            "argv": ["git", "-C", process_a_root, "rev-parse", "HEAD"],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "<O_COMMIT>\n",
        },
        {
            "argv": ["git", "-C", process_b_root, "rev-parse", "HEAD"],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "<O_COMMIT>\n",
        },
        {
            "argv": ["install", "-d", "-m", "700", f"{execution_root}/process-a-output/open"],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
        {
            "argv": ["install", "-d", "-m", "700", f"{execution_root}/process-b-output/open"],
            "cwd": "/var/tmp",
            "expected_exit_code": 0,
            "expected_stdout": "",
        },
    ]
    expected_environment = [
        "/usr/bin/env",
        "UV_OFFLINE=1",
        "uv",
        "sync",
        "--python",
        "3.12.13",
        "--frozen",
        "--no-dev",
        "--offline",
    ]
    expected_preflight = [
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        ["git", "rev-parse", "HEAD"],
        [".venv/bin/python3", "--version"],
        ["uv", "--version"],
        [
            ".venv/bin/python3",
            "-I",
            "-B",
            "scripts/reconstruct_action_qbc_v7_open_registration.py",
            "--repository-root",
            ".",
            "--registration",
            _EXPECTED_REGISTRATION,
        ],
    ]
    expected_scientific = [
        "/usr/bin/timeout",
        "--foreground",
        "--signal=TERM",
        "--kill-after=15s",
        "2700s",
        ".venv/bin/python3",
        "-I",
        "-B",
        "scripts/run_action_qbc_v7_open_diagnostic.py",
        "--repository-root",
        ".",
        "--registration",
        _EXPECTED_REGISTRATION,
        "--compute-deadline-seconds",
        "2100",
        "--wall-time-seconds",
        "2400",
        "--output",
        "<OUTPUT_PATH>",
    ]
    expected_finalizer = [
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/finalize_action_qbc_v7_open_diagnostic.py",
        "--repository-root",
        ".",
        "--registration",
        _EXPECTED_REGISTRATION,
        "--process-a",
        _EXPECTED_PROCESS_A,
        "--process-b",
        _EXPECTED_PROCESS_B,
        "--process-a-exit-code",
        "<A_EXIT_CODE>",
        "--process-b-exit-code",
        "<B_EXIT_CODE_OR_NULL>",
        "--lifecycle-stage",
        "<STAGE_OR_NULL>",
        "--publish",
        _EXPECTED_PUBLISH,
        "--receipt",
        _EXPECTED_RECEIPT,
        "--administrative-terminal",
        _EXPECTED_ADMIN,
    ]
    if (
        execution["tag_verification_step"] != expected_tag_step
        or execution["setup_steps"] != expected_setup
        or execution["environment_build_argv"] != expected_environment
        or execution["preflight_argvs"] != expected_preflight
        or execution["scientific_argv_template"] != expected_scientific
        or execution["finalizer_argv_template"] != expected_finalizer
    ):
        _raise("execution command contract is invalid")
    argv_fields = (
        "producer_argv",
        "reconstructor_argv",
        "environment_build_argv",
        "scientific_argv_template",
        "finalizer_argv_template",
    )
    for field in argv_fields:
        _validate_argv_list(execution[field], f"execution_contract.{field}")
    for field in ("preflight_argvs", "test_argvs"):
        outer = execution[field]
        if not isinstance(outer, list) or not outer:
            _raise(f"execution_contract.{field} is invalid")
        for index, command in enumerate(outer):
            _validate_argv_list(command, f"{field}[{index}]")
    hashes = _require_mapping(execution["argv_hashes"], "argv_hashes")
    hash_preimages = {
        "producer": execution["producer_argv"],
        "reconstructor": execution["reconstructor_argv"],
        "tag_verification": execution["tag_verification_step"],
        "setup": execution["setup_steps"],
        "environment_build": execution["environment_build_argv"],
        "preflight": execution["preflight_argvs"],
        "scientific": execution["scientific_argv_template"],
        "tests": execution["test_argvs"],
        "finalizer": execution["finalizer_argv_template"],
    }
    _require_keys(hashes, set(hash_preimages), "argv_hashes")
    for key, preimage in hash_preimages.items():
        if hashes[key] != _sha256(_canonical_json_bytes(preimage)):
            _raise(f"registered {key} argv hash is invalid")

    return _Registration(
        value=registration,
        data=data,
        file_sha256=_sha256(data),
        path_text=path_text,
    )


def _run_git(root: Path, *arguments: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", *arguments], cwd=root, check=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise _ValidationError("Git identity validation failed") from exc
    return process.stdout


def _validate_repository(
    root: Path,
    registration: _Registration,
) -> _RepositoryIdentity:
    commit = _run_git(root, "rev-parse", "HEAD").decode("ascii").strip()
    _require_sha1(commit, "open-freeze commit")
    tag_valid = False
    try:
        tag_commit = _run_git(root, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}^{{commit}}")
        tag_type = _run_git(root, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}")
        tag_valid = tag_commit.decode("ascii").strip() == commit and tag_type == b"commit\n"
    except _ValidationError:
        tag_valid = False
    if _run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") != b"":
        _raise("the original open-freeze checkout is not clean")

    manifest = registration.value["source_manifest"]
    for inventory_name in ("preregistration_tree", "open_freeze_added_files"):
        for entry in manifest[inventory_name]:
            path = root / entry["path"]
            data = _read_plain_file(path, f"source manifest path {entry['path']}")
            if len(data) != entry["byte_count"] or _sha256(data) != entry["sha256"]:
                _raise("a source-manifest file differs from registration")
            observed_blob = _run_git(root, "hash-object", "--no-filters", entry["path"])
            if observed_blob.decode("ascii").strip() != entry["git_blob_sha1"]:
                _raise("a source-manifest Git blob differs from registration")
    return _RepositoryIdentity(commit_sha=commit, tag_valid=tag_valid)


def _validate_layer(
    value: Any,
    *,
    reason_order: list[str],
    name: str,
) -> dict[str, Any]:
    layer = _require_mapping(value, name)
    _require_keys(layer, _LAYER_KEYS, name)
    if layer["status"] not in {"evaluated", "precondition_failed"}:
        _raise(f"{name} has an invalid status")
    if not isinstance(layer["passes"], bool):
        _raise(f"{name}.passes is not Boolean")
    reasons = layer["reasons"]
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        _raise(f"{name}.reasons is invalid")
    positions = {reason: index for index, reason in enumerate(reason_order)}
    if (
        len(set(reasons)) != len(reasons)
        or any(reason not in positions for reason in reasons)
        or reasons != sorted(reasons, key=positions.__getitem__)
    ):
        _raise(f"{name}.reasons is not unique canonical vocabulary order")
    if layer["passes"] is not (layer["status"] == "evaluated" and not reasons):
        _raise(f"{name} violates the layer pass equivalence")
    if not isinstance(layer["details"], dict):
        _raise(f"{name}.details is not an object")
    return layer


def _validate_grid_table(value: Any) -> set[str]:
    table = _require_mapping(value, "grid_evidence")
    _require_keys(table, {"schema_version", "blobs"}, "grid_evidence")
    if table["schema_version"] != "action-qbc-v7-grid-evidence-table-v1":
        _raise("grid evidence schema is invalid")
    blobs = table["blobs"]
    if not isinstance(blobs, list):
        _raise("grid evidence blobs are not a list")
    references: list[str] = []
    for index, blob_value in enumerate(blobs):
        blob = _require_mapping(blob_value, f"grid blob {index}")
        _require_keys(blob, _GRID_BLOB_KEYS, "grid blob")
        if blob["encoding"] != "int16-le-c-v1":
            _raise("grid blob encoding is invalid")
        shape = blob["shape"]
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or any(not _is_int(size) or size < 1 or size > 64 for size in shape)
        ):
            _raise("grid blob shape is invalid")
        try:
            decoded = base64.b64decode(blob["data_base64"], validate=True)
        except (TypeError, binascii.Error) as exc:
            raise _ValidationError("grid blob base64 is invalid") from exc
        expected_count = shape[0] * shape[1] * 2
        digest = _sha256(decoded)
        reference = f"{digest}:{shape[0]}:{shape[1]}:int16-le-c-v1"
        if (
            len(decoded) != expected_count
            or blob["byte_count"] != expected_count
            or blob["sha256"] != digest
            or blob["reference"] != reference
            or base64.b64encode(decoded).decode("ascii") != blob["data_base64"]
        ):
            _raise("grid blob content identity is invalid")
        # Unpacking proves a complete signed little-endian int16 stream.
        struct.unpack(f"<{shape[0] * shape[1]}h", decoded)
        references.append(reference)
    if references != sorted(set(references)):
        _raise("grid blob references are not sorted and unique")
    return set(references)


def _validate_support_table(value: Any) -> set[str]:
    table = _require_mapping(value, "expected_exterior_support")
    _require_keys(table, {"schema_version", "blobs"}, "expected_exterior_support")
    if table["schema_version"] != "action-qbc-v7-expected-exterior-support-table-v1":
        _raise("expected exterior support schema is invalid")
    blobs = table["blobs"]
    if not isinstance(blobs, list):
        _raise("expected exterior support blobs are not a list")
    references: list[str] = []
    for index, blob_value in enumerate(blobs):
        blob = _require_mapping(blob_value, f"support blob {index}")
        _require_keys(blob, _SUPPORT_BLOB_KEYS, "support blob")
        if blob["encoding"] != "signed-coordinate-label-json-utf8-v1":
            _raise("support blob encoding is invalid")
        try:
            decoded = base64.b64decode(blob["data_base64"], validate=True)
        except (TypeError, binascii.Error) as exc:
            raise _ValidationError("support blob base64 is invalid") from exc
        entries = _parse_canonical_json(decoded, "support blob data")
        if not isinstance(entries, list):
            _raise("support blob data is not a list")
        for entry in entries:
            if (
                not isinstance(entry, list)
                or len(entry) != 3
                or any(not _is_int(item) for item in entry)
                or entry[2] < -32768
                or entry[2] > 32767
            ):
                _raise("support blob entry is invalid")
        if entries != sorted(entries) or len({tuple(entry) for entry in entries}) != len(entries):
            _raise("support blob entries are not sorted and distinct")
        digest = _sha256(decoded)
        reference = f"{digest}:{len(entries)}:signed-coordinate-label-json-utf8-v1"
        if (
            blob["entry_count"] != len(entries)
            or blob["byte_count"] != len(decoded)
            or blob["sha256"] != digest
            or blob["reference"] != reference
            or base64.b64encode(decoded).decode("ascii") != blob["data_base64"]
        ):
            _raise("support blob content identity is invalid")
        references.append(reference)
    if references != sorted(set(references)):
        _raise("support blob references are not sorted and unique")
    return set(references)


def _collect_references(rows: list[Any]) -> tuple[set[str], set[str]]:
    grid: set[str] = set()
    support: set[str] = set()
    grid_names = {
        "base_prediction_ref",
        "transformed_prediction_ref",
        "expected_prediction_ref",
        "observable_mismatch_mask_ref",
    }
    for row_value in rows:
        if not isinstance(row_value, dict) or row_value.get("disposition") != "completed":
            continue
        evidence = row_value.get("evidence")
        if not isinstance(evidence, dict):
            continue
        root = evidence.get("root_transition")
        if not isinstance(root, dict):
            continue
        details = root.get("details")
        if not isinstance(details, dict):
            continue
        records = details.get("pair_records")
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            for name in grid_names:
                reference = record.get(name)
                if isinstance(reference, str):
                    grid.add(reference)
            reference = record.get("expected_exterior_support_ref")
            if isinstance(reference, str):
                support.add(reference)
    return grid, support


def _expected_execution_identity(
    registration: _Registration,
    repository: _RepositoryIdentity,
) -> dict[str, Any]:
    value = registration.value
    manifest_entries = [
        *value["source_manifest"]["preregistration_tree"],
        *value["source_manifest"]["open_freeze_added_files"],
    ]
    uv_entries = [entry for entry in manifest_entries if entry["path"] == "uv.lock"]
    if len(uv_entries) != 1:
        _raise("registration does not bind exactly one uv.lock")
    registered_platform = value["platform"]
    return {
        "open_freeze_commit_sha": repository.commit_sha,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "source_manifest_sha256": value["source_manifest"]["manifest_sha256"],
        "python_version": registered_platform["python_version"],
        "python_implementation": registered_platform["python_implementation"],
        "platform_system": registered_platform["platform_system"],
        "platform_machine": registered_platform["platform_machine"],
        "uv_version": registered_platform["uv_version"],
        "uv_lock_sha256": uv_entries[0]["sha256"],
        "canonical_command_sha256": value["execution_contract"]["argv_hashes"]["scientific"],
    }


def _validate_payload_bytes(
    data: bytes,
    registration: _Registration,
    repository: _RepositoryIdentity,
) -> dict[str, Any]:
    if len(data) > _PAYLOAD_CAP_BYTES:
        _raise("scientific payload exceeds the registered cap")
    payload = _require_mapping(_parse_canonical_json(data, "scientific payload"), "payload")
    _require_keys(payload, _PAYLOAD_KEYS, "scientific payload")
    if (
        payload["schema_version"] != _PAYLOAD_SCHEMA
        or payload["treatment_id"] != _TREATMENT_ID
        or payload["diagnostic_system_id"] != _DIAGNOSTIC_SYSTEM_ID
        or payload["comparison_semantics_id"] != _COMPARISON_ID
        or payload["runtime_id"] is not None
        or payload["authorization"] != _AUTHORIZATION
        or payload["scientific_capability_passes"] is not False
        or not isinstance(payload["diagnostic_complete"], bool)
    ):
        _raise("scientific payload fixed identity is invalid")
    if payload["preregistration_identity"] != registration.value["preregistration"]:
        _raise("payload preregistration identity differs from registration")
    if payload["v6_negative_identity"] != registration.value["v6_negative"]:
        _raise("payload v6 identity differs from registration")
    registration_identity = _require_mapping(
        payload["registration_identity"], "registration_identity"
    )
    _require_keys(registration_identity, _REGISTRATION_IDENTITY_KEYS, "registration_identity")
    expected_registration_identity = {
        "schema_version": _REGISTRATION_SCHEMA,
        "path": registration.path_text,
        "content_sha256": registration.value["content_sha256"],
        "file_sha256": registration.file_sha256,
    }
    if registration_identity != expected_registration_identity:
        _raise("payload registration identity is invalid")
    execution_identity = _require_mapping(payload["execution_identity"], "execution_identity")
    _require_keys(execution_identity, _EXECUTION_IDENTITY_KEYS, "execution_identity")
    if execution_identity != _expected_execution_identity(registration, repository):
        _raise("payload execution identity is invalid")

    expected_counts = registration.value["resource_contract"]["expected_counts"]
    counters = _require_mapping(payload["resource_counters"], "resource_counters")
    _require_keys(counters, set(expected_counts), "resource_counters")
    for key, value in counters.items():
        _require_nonnegative_int(value, f"resource_counters.{key}")

    grid_references = _validate_grid_table(payload["grid_evidence"])
    support_references = _validate_support_table(payload["expected_exterior_support"])

    rows = payload["rows"]
    registered_rows = registration.value["row_inventory"]["rows"]
    if not isinstance(rows, list) or len(rows) != len(registered_rows):
        _raise("payload row inventory length is invalid")
    reason_order = registration.value["scientific_contract"]["reason_order"]
    has_terminal = False
    has_global_terminal = False
    for index, (row_value, registered_row) in enumerate(zip(rows, registered_rows, strict=True)):
        row = _require_mapping(row_value, f"payload row {index}")
        _require_keys(row, _ROW_KEYS, f"payload row {index}")
        address = _require_mapping(row["address"], f"payload row {index} address")
        _require_keys(address, _ADDRESS_KEYS, "row address")
        expected_address = {
            "row_index": registered_row["row_index"],
            "row_id": registered_row["row_id"],
            "kind": registered_row["kind"],
        }
        if address != expected_address or row["registered_row"] != registered_row:
            _raise("payload row registration binding is invalid")
        disposition = row["disposition"]
        if disposition not in {
            "completed",
            "terminal_addressable_negative",
            "terminal_global_negative",
        }:
            _raise("payload row disposition is invalid")
        if disposition == "completed":
            if row["terminal"] is not None:
                _raise("a completed row has a terminal")
            evidence = _require_mapping(row["evidence"], "completed row evidence")
            _require_keys(evidence, _EVIDENCE_KEYS[address["kind"]], "completed row evidence")
            for layer_name, layer in evidence.items():
                _validate_layer(layer, reason_order=reason_order, name=layer_name)
        else:
            has_terminal = True
            has_global_terminal = has_global_terminal or disposition == "terminal_global_negative"
            if row["evidence"] != {}:
                _raise("a terminal row has non-empty evidence")
            terminal = _require_mapping(row["terminal"], "row terminal")
            _require_keys(terminal, _TERMINAL_KEYS, "row terminal")
            if disposition == "terminal_addressable_negative" and terminal != {
                "status": "authoritative_derivation_error",
                "stage": "scientific_record_schema_invalid",
            }:
                _raise("addressable terminal identity is invalid")

    used_grid, used_support = _collect_references(rows)
    if used_grid != grid_references or used_support != support_references:
        _raise("payload evidence-table reference inventory is not exact")

    aggregates = _require_mapping(payload["aggregates"], "aggregates")
    aggregate_keys = set(registration.value["scientific_contract"]["aggregate_keys"])
    _require_keys(aggregates, aggregate_keys, "aggregates")
    reasons = _require_mapping(aggregates.get("reason_counts"), "reason_counts")
    _require_keys(reasons, set(reason_order), "reason_counts")
    for key, value in reasons.items():
        _require_nonnegative_int(value, f"reason_counts.{key}")
    expected_resource_pass = counters == expected_counts
    zero_forbidden = registration.value["resource_contract"]["increment_contract"][
        "zero_forbidden"
    ]
    expected_resource_pass = expected_resource_pass and all(
        counters[name] == 0 for name in zero_forbidden
    )
    if aggregates.get("resource_contract_passes") is not expected_resource_pass:
        _raise("resource_contract_passes violates its defining equivalence")

    fallback_stage = payload["terminal_fallback_stage"]
    candidate_size = payload["candidate_payload_size_bytes"]
    if fallback_stage is None:
        if candidate_size is not None or has_global_terminal:
            _raise("normal payload fallback fields are invalid")
    else:
        if fallback_stage not in _GLOBAL_STAGES or not has_global_terminal:
            _raise("payload global fallback stage is invalid")
        if any(row["disposition"] != "terminal_global_negative" for row in rows):
            _raise("global fallback does not terminalize every row")
        if payload["diagnostic_complete"] is not False:
            _raise("global fallback claims diagnostic completeness")
        if fallback_stage == "payload_size_limit_exceeded":
            if not _is_int(candidate_size) or candidate_size <= _PAYLOAD_CAP_BYTES:
                _raise("size fallback candidate byte count is invalid")
        elif candidate_size is not None:
            _raise("non-size fallback has a candidate byte count")
        if payload["grid_evidence"] != {
            "schema_version": "action-qbc-v7-grid-evidence-table-v1",
            "blobs": [],
        } or payload["expected_exterior_support"] != {
            "schema_version": "action-qbc-v7-expected-exterior-support-table-v1",
            "blobs": [],
        }:
            _raise("global fallback evidence tables are not canonical empty tables")
        for row in rows:
            terminal = row["terminal"]
            expected_status = (
                "evaluator_internal_error"
                if fallback_stage == "evaluator_internal_error"
                else "payload_size_limit_exceeded"
                if fallback_stage == "payload_size_limit_exceeded"
                else "authoritative_derivation_error"
            )
            if terminal != {"status": expected_status, "stage": fallback_stage}:
                _raise("global fallback row terminal identity is invalid")
    if has_terminal and payload["diagnostic_complete"] is not False:
        _raise("terminal payload claims diagnostic completeness")
    if payload["diagnostic_complete"] and not expected_resource_pass:
        _raise("complete payload violates the resource contract")
    return payload


def _parse_exit_code(value: str) -> int | None:
    if value == "null":
        return None
    if not value.isascii() or not value.isdecimal():
        raise argparse.ArgumentTypeError("exit code must be a non-negative decimal integer or null")
    return int(value)


def _parse_stage(value: str) -> str | None:
    if value == "null":
        return None
    if value not in _ADMIN_STAGES:
        raise argparse.ArgumentTypeError("lifecycle stage is not registered")
    return value


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and transactionally publish the action-QBC v7 result pair."
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--process-a", required=True)
    parser.add_argument("--process-b", required=True)
    parser.add_argument("--process-a-exit-code", required=True, type=_parse_exit_code)
    parser.add_argument("--process-b-exit-code", required=True, type=_parse_exit_code)
    parser.add_argument("--lifecycle-stage", required=True, type=_parse_stage)
    parser.add_argument("--publish", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--administrative-terminal", required=True)
    return parser.parse_args(argv)


def _require_main_contract(args: argparse.Namespace, registration: _Registration | None) -> Path:
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _raise("the finalizer requires Python -I -B")
    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 12):
        _raise("the finalizer requires CPython 3.12")
    if (
        args.repository_root != "."
        or args.registration != _EXPECTED_REGISTRATION
        or args.process_a != _EXPECTED_PROCESS_A
        or args.process_b != _EXPECTED_PROCESS_B
        or args.publish != _EXPECTED_PUBLISH
        or args.receipt != _EXPECTED_RECEIPT
        or args.administrative_terminal != _EXPECTED_ADMIN
    ):
        _raise("the finalizer arguments differ from the registered command")
    root = Path.cwd().resolve(strict=True)
    if str(root) != _FINALIZER_CWD:
        _raise("the finalizer cwd differs from registration")
    if registration is not None:
        template = registration.value["execution_contract"]["finalizer_argv_template"]
        replacements = {
            "<A_EXIT_CODE>": "null"
            if args.process_a_exit_code is None
            else str(args.process_a_exit_code),
            "<B_EXIT_CODE_OR_NULL>": "null"
            if args.process_b_exit_code is None
            else str(args.process_b_exit_code),
            "<STAGE_OR_NULL>": "null" if args.lifecycle_stage is None else args.lifecycle_stage,
        }
        expected = [replacements.get(token, token) for token in template]
        try:
            script_index = expected.index("scripts/finalize_action_qbc_v7_open_diagnostic.py")
        except ValueError as exc:
            raise _ValidationError("registered finalizer template lacks its script") from exc
        if list(sys.argv) != expected[script_index:]:
            _raise("observed finalizer argv differs from registration")
    return root


def _observe_process(
    label: str,
    path_text: str,
    exit_code: int | None,
    registration: _Registration | None,
    repository: _RepositoryIdentity | None,
) -> _ProcessObservation:
    path = Path(path_text)
    exists = False
    valid = False
    data: bytes | None = None
    try:
        metadata = path.lstat()
        exists = True
        if stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            candidate = _read_plain_file(
                path,
                f"process {label} payload",
                maximum=_PAYLOAD_CAP_BYTES,
            )
            if registration is not None and repository is not None:
                _validate_payload_bytes(candidate, registration, repository)
                valid = True
                data = candidate
    except (OSError, _ValidationError):
        valid = False
        data = None
    record = {
        "label": label,
        "output_path": path_text,
        "exit_code": exit_code,
        "payload_exists": exists,
        "payload_valid": valid,
        "payload_sha256": _sha256(data) if data is not None else None,
        "payload_size_bytes": len(data) if data is not None else None,
    }
    return _ProcessObservation(record=record, data=data)


def _first_stage(stages: Sequence[str]) -> str | None:
    if not stages:
        return None
    positions = {stage: index for index, stage in enumerate(_ADMIN_STAGES)}
    return min(stages, key=positions.__getitem__)


def _administrative_object(
    *,
    stage: str,
    registration: _Registration | None,
    repository: _RepositoryIdentity | None,
    process_a: _ProcessObservation,
    process_b: _ProcessObservation,
    identical: bool | None,
) -> dict[str, Any]:
    return {
        "schema_version": _ADMIN_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": repository.commit_sha if repository is not None else None,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": (
            registration.value["content_sha256"] if registration is not None else None
        ),
        "stage": stage,
        "process_a": process_a.record,
        "process_b": process_b.record,
        "payloads_byte_identical": identical,
        "authorization": _AUTHORIZATION,
    }


def _receipt_object(
    *,
    registration: _Registration,
    repository: _RepositoryIdentity,
    process_a: _ProcessObservation,
    process_b: _ProcessObservation,
    publish_text: str,
) -> dict[str, Any]:
    if process_a.data is None or process_b.data is None or process_a.data != process_b.data:
        _raise("a receipt requires two valid byte-identical payloads")
    return {
        "schema_version": _RECEIPT_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": repository.commit_sha,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": registration.value["content_sha256"],
        "process_a": process_a.record,
        "process_b": process_b.record,
        "payloads_byte_identical": True,
        "published_payload_path": publish_text,
        "published_payload_sha256": _sha256(process_a.data),
        "authorization": _AUTHORIZATION,
    }


def _validate_process_record(value: Any, label: str, path: str) -> None:
    record = _require_mapping(value, f"process {label} receipt record")
    _require_keys(record, _PROCESS_KEYS, f"process {label} receipt record")
    if record["label"] != label or record["output_path"] != path:
        _raise("receipt process identity is invalid")
    exit_code = record["exit_code"]
    if exit_code is not None:
        _require_nonnegative_int(exit_code, "receipt process exit code")
    if not isinstance(record["payload_exists"], bool) or not isinstance(
        record["payload_valid"], bool
    ):
        _raise("receipt process validity fields are invalid")
    if record["payload_valid"]:
        if not record["payload_exists"]:
            _raise("valid process payload is marked absent")
        _require_sha256(record["payload_sha256"], "receipt process payload SHA-256")
        _require_nonnegative_int(record["payload_size_bytes"], "receipt payload size")
    elif record["payload_sha256"] is not None or record["payload_size_bytes"] is not None:
        _raise("invalid/absent process payload retains a hash or size")


def _validate_receipt_bytes(data: bytes, payload_data: bytes) -> dict[str, Any]:
    receipt = _require_mapping(_parse_canonical_json(data, "receipt"), "receipt")
    _require_keys(receipt, _RECEIPT_KEYS, "receipt")
    if (
        receipt["schema_version"] != _RECEIPT_SCHEMA
        or receipt["treatment_id"] != _TREATMENT_ID
        or receipt["open_freeze_tag"] != _OPEN_FREEZE_TAG
        or receipt["payloads_byte_identical"] is not True
        or receipt["published_payload_path"] != _EXPECTED_PUBLISH
        or receipt["published_payload_sha256"] != _sha256(payload_data)
        or receipt["authorization"] != _AUTHORIZATION
    ):
        _raise("receipt fixed identity is invalid")
    _require_sha1(receipt["open_freeze_commit_sha"], "receipt open-freeze commit")
    _require_sha256(receipt["registration_content_sha256"], "receipt registration digest")
    _validate_process_record(receipt["process_a"], "A", _EXPECTED_PROCESS_A)
    _validate_process_record(receipt["process_b"], "B", _EXPECTED_PROCESS_B)
    return receipt


def _validate_admin_bytes(data: bytes, expected: Mapping[str, Any]) -> None:
    observed = _require_mapping(_parse_canonical_json(data, "administrative terminal"), "admin")
    _require_keys(observed, _ADMIN_KEYS, "administrative terminal")
    if observed != expected:
        _raise("administrative terminal differs from the selected outcome")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stage_file(
    final: Path,
    data: bytes,
    purpose: str,
    validator: Callable[[bytes], None],
) -> _StagedFile:
    parent = final.parent
    try:
        parent_meta = parent.lstat()
    except OSError as exc:
        raise _PublicationError("publication parent is unavailable") from exc
    if not stat.S_ISDIR(parent_meta.st_mode) or stat.S_ISLNK(parent_meta.st_mode):
        raise _PublicationError("publication parent is not a plain directory")
    stage = final.with_name(f".{final.name}.{purpose}-stage-{os.getpid()}")
    descriptor: int | None = None
    try:
        descriptor = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        observed = _read_plain_file(stage, f"{purpose} staging file")
        if observed != data:
            raise _PublicationError(f"{purpose} staging bytes changed")
        validator(observed)
        metadata = stage.stat(follow_symlinks=False)
        return _StagedFile(
            path=stage,
            data=data,
            sha256=_sha256(data),
            device=metadata.st_dev,
            inode=metadata.st_ino,
        )
    except Exception:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        with suppress(OSError):
            stage.unlink()
        raise


def _remove_stage(staged: _StagedFile | None) -> None:
    if staged is None:
        return
    try:
        metadata = staged.path.stat(follow_symlinks=False)
        if metadata.st_dev == staged.device and metadata.st_ino == staged.inode:
            staged.path.unlink()
    except FileNotFoundError:
        pass


def _exclusive_link(staged: _StagedFile, final: Path) -> None:
    os.link(staged.path, final, follow_symlinks=False)


def _owned_final(final: Path, staged: _StagedFile) -> bool:
    try:
        final_meta = final.stat(follow_symlinks=False)
        stage_meta = staged.path.stat(follow_symlinks=False)
        data = _read_plain_file(final, "published payload")
    except (OSError, _ValidationError):
        return False
    return (
        final_meta.st_dev == stage_meta.st_dev == staged.device
        and final_meta.st_ino == stage_meta.st_ino == staged.inode
        and _sha256(data) == staged.sha256
    )


def _publish_admin(final: Path, value: dict[str, Any]) -> bool:
    if final.exists() or final.is_symlink():
        return False
    data = _canonical_json_bytes(value)
    staged: _StagedFile | None = None
    try:
        staged = _stage_file(
            final,
            data,
            "administrative",
            lambda observed: _validate_admin_bytes(observed, value),
        )
        _exclusive_link(staged, final)
        return True
    except Exception:
        return False
    finally:
        _remove_stage(staged)


def _publish_success(
    *,
    payload_final: Path,
    receipt_final: Path,
    administrative_final: Path,
    payload_data: bytes,
    receipt: dict[str, Any],
    registration: _Registration,
    repository: _RepositoryIdentity,
    process_a: _ProcessObservation,
    process_b: _ProcessObservation,
) -> tuple[bool, str | None]:
    if administrative_final.exists() or administrative_final.is_symlink():
        return False, "exclusive_publication_failed"
    if (
        payload_final.exists()
        or payload_final.is_symlink()
        or receipt_final.exists()
        or receipt_final.is_symlink()
    ):
        admin = _administrative_object(
            stage="exclusive_publication_failed",
            registration=registration,
            repository=repository,
            process_a=process_a,
            process_b=process_b,
            identical=True,
        )
        return _publish_admin(administrative_final, admin), "exclusive_publication_failed"

    receipt_data = _canonical_json_bytes(receipt)
    payload_stage: _StagedFile | None = None
    receipt_stage: _StagedFile | None = None
    payload_linked = False
    try:
        payload_stage = _stage_file(
            payload_final,
            payload_data,
            "payload",
            lambda data: _validate_payload_bytes(data, registration, repository),
        )
        receipt_stage = _stage_file(
            receipt_final,
            receipt_data,
            "receipt",
            lambda data: _validate_receipt_bytes(data, payload_data),
        )
    except Exception:
        _remove_stage(payload_stage)
        _remove_stage(receipt_stage)
        admin = _administrative_object(
            stage="receipt_finalization_failed",
            registration=registration,
            repository=repository,
            process_a=process_a,
            process_b=process_b,
            identical=True,
        )
        return _publish_admin(administrative_final, admin), "receipt_finalization_failed"

    try:
        _exclusive_link(payload_stage, payload_final)
        payload_linked = True
    except Exception:
        admin = _administrative_object(
            stage="exclusive_publication_failed",
            registration=registration,
            repository=repository,
            process_a=process_a,
            process_b=process_b,
            identical=True,
        )
        _remove_stage(payload_stage)
        _remove_stage(receipt_stage)
        return _publish_admin(administrative_final, admin), "exclusive_publication_failed"

    try:
        _exclusive_link(receipt_stage, receipt_final)
    except Exception:
        rollback_ok = False
        if _owned_final(payload_final, payload_stage):
            try:
                payload_final.unlink()
                _fsync_directory(payload_final.parent)
                rollback_ok = not payload_final.exists() and not payload_final.is_symlink()
            except OSError:
                rollback_ok = False
        stage = "exclusive_publication_failed" if rollback_ok else "publication_rollback_failed"
        admin = _administrative_object(
            stage=stage,
            registration=registration,
            repository=repository,
            process_a=process_a,
            process_b=process_b,
            identical=True,
        )
        _remove_stage(payload_stage)
        _remove_stage(receipt_stage)
        return _publish_admin(administrative_final, admin), stage
    finally:
        if not payload_linked:
            _remove_stage(payload_stage)

    _remove_stage(payload_stage)
    _remove_stage(receipt_stage)
    return True, None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    registration: _Registration | None = None
    repository: _RepositoryIdentity | None = None
    registration_error = False
    contract_error = False
    try:
        root_guess = Path.cwd().resolve(strict=True)
        registration = _validate_registration(root_guess / args.registration, args.registration)
    except (OSError, _ValidationError):
        registration_error = True
    try:
        root = _require_main_contract(args, registration)
    except (OSError, _ValidationError):
        contract_error = True
        root = Path.cwd().resolve()
    if registration is not None and not contract_error:
        try:
            repository = _validate_repository(root, registration)
        except _ValidationError:
            registration_error = True
            registration = None

    process_a = _observe_process(
        "A", args.process_a, args.process_a_exit_code, registration, repository
    )
    process_b = _observe_process(
        "B", args.process_b, args.process_b_exit_code, registration, repository
    )
    identical = (
        process_a.data == process_b.data
        if process_a.data is not None and process_b.data is not None
        else None
    )
    candidates: list[str] = []
    if args.lifecycle_stage is not None:
        candidates.append(args.lifecycle_stage)
    if repository is not None and not repository.tag_valid:
        candidates.append("tag_verification_failed")
    if registration_error or contract_error or registration is None or repository is None:
        candidates.append("registration_invalid")
    if args.process_a_exit_code is None or args.process_a_exit_code != 0:
        candidates.append("process_a_nonzero")
    elif not process_a.record["payload_exists"]:
        candidates.append("process_a_output_missing")
    elif not process_a.record["payload_valid"]:
        candidates.append("process_a_payload_invalid")
    if args.process_b_exit_code is None or args.process_b_exit_code != 0:
        candidates.append("process_b_nonzero")
    elif not process_b.record["payload_exists"]:
        candidates.append("process_b_output_missing")
    elif not process_b.record["payload_valid"]:
        candidates.append("process_b_payload_invalid")
    if identical is False:
        candidates.append("payload_byte_mismatch")
    selected = _first_stage(candidates)

    publish = root / args.publish
    receipt_path = root / args.receipt
    admin_path = root / args.administrative_terminal
    if admin_path.exists() or admin_path.is_symlink():
        print(
            "action-QBC v7 result-document-only terminal: exclusive_publication_failed; "
            "the pre-existing administrative destination was not adopted",
            file=sys.stderr,
        )
        return 4
    if publish.parent != receipt_path.parent or publish.parent != admin_path.parent:
        print(
            "action-QBC v7 result-document-only terminal: receipt_finalization_failed; "
            "publication parents differ",
            file=sys.stderr,
        )
        return 4
    if (
        publish.exists()
        or publish.is_symlink()
        or receipt_path.exists()
        or receipt_path.is_symlink()
    ):
        selected = "exclusive_publication_failed"

    if selected is not None:
        admin = _administrative_object(
            stage=selected,
            registration=registration,
            repository=repository,
            process_a=process_a,
            process_b=process_b,
            identical=identical,
        )
        if _publish_admin(admin_path, admin):
            return 0
        print(
            "action-QBC v7 result-document-only terminal: receipt_finalization_failed; "
            "no machine-readable administrative artifact could be created",
            file=sys.stderr,
        )
        return 4

    assert registration is not None
    assert repository is not None
    assert process_a.data is not None
    receipt = _receipt_object(
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
        publish_text=args.publish,
    )
    succeeded, failure_stage = _publish_success(
        payload_final=publish,
        receipt_final=receipt_path,
        administrative_final=admin_path,
        payload_data=process_a.data,
        receipt=receipt,
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
    )
    if succeeded:
        return 0
    print(
        "action-QBC v7 result-document-only terminal: "
        f"{failure_stage or 'receipt_finalization_failed'}; publication did not complete",
        file=sys.stderr,
    )
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
