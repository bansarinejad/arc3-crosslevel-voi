# ruff: noqa: E501
"""One-shot action-QBC v8 lifecycle driver and repeatable Git-only result publisher.

This program is standard-library-only.  ``execute`` owns the registered arm/scientific/
validation/finalization sequence after acquiring the irreversible driver claim.  ``publish``
can repeat only the immutable bundle-to-Git transaction; it cannot start scientific or
network work.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

_TREATMENT_ID: Final = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_REGISTRATION_SCHEMA: Final = "action-qbc-v8-open-registration-v1"
_OPEN_FREEZE_TAG: Final = "action-qbc-v8-open-diagnostic-freeze-v1"
_PREREGISTRATION_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
_PREREGISTRATION_COMMIT: Final = "e0bff9ffc185196cafa938c8f7c9a7186366258b"
_PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md"
)
_PREREGISTRATION_DOCUMENT_BLOB: Final = "29c991b7e23209f2c38d5e9a11a15bca51753d8e"
_PREREGISTRATION_DOCUMENT_SHA256: Final = (
    "31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1"
)
_PREREGISTRATION_DOCUMENT_BYTE_COUNT: Final = 33_215
_P8V3_COMMIT: Final = "996ab2bb5a24143a110673977f63e7d111cf2060"
_P8V3_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
_P8V3_DOCUMENT: Final = "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v3_correction.md"
_P8V3_DOCUMENT_BLOB: Final = "9f014e243a6bfe4ea35636a5de0d9bde598d4130"
_P8V3_DOCUMENT_SHA256: Final = "b2dafb5d41ab27a63f516c102f295395f32e825a5f66a90bd5fa95dbd414dbe9"
_P8V3_DOCUMENT_BYTE_COUNT: Final = 58_656
_P8V2_COMMIT: Final = "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
_P8V2_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
_P8V2_DOCUMENT: Final = "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification.md"
_P8V2_DOCUMENT_BLOB: Final = "b3a639da07a92672adfd4976861a58608702a7f3"
_P8V2_DOCUMENT_SHA256: Final = "f5c3c7be6221cdefc789d73f140a24b289a4edc849d48c1fb9249bc258308344"
_P8V2_DOCUMENT_BYTE_COUNT: Final = 92_798
_P8V1_COMMIT: Final = "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
_P8V1_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
_P8V1_DOCUMENT_BLOB: Final = "9d5f00ea4fdb4ca6ff3cdb8c51ba0105efb1e046"
_P8V1_DOCUMENT_SHA256: Final = "2e0ad4415d7f230f12f48db01aae9210797aa1da7f3a4ace6723e81be7bbb254"
_R7_COMMIT: Final = "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
_DRIVER_SCHEMA: Final = "action-qbc-v8-lifecycle-driver-claim-v1"
_LEDGER_SCHEMA: Final = "action-qbc-v8-lifecycle-ledger-v1"
_BUNDLE_SCHEMA: Final = "action-qbc-v8-finalization-bundle-v1"
_EMERGENCY_SCHEMA: Final = "action-qbc-v8-emergency-result-bundle-v2"
_RECEIPT_SCHEMA: Final = "action-qbc-v8-open-diagnostic-receipt-v2"
_ADMIN_SCHEMA: Final = "action-qbc-v8-open-diagnostic-administrative-terminal-v2"
_OWNER_SCHEMA: Final = "action-qbc-v8-result-git-owner-claim-v1"
_RESULT_DOCUMENT_SCHEMA: Final = "action-qbc-v8-result-document-contract-v1"
_ARM_SCHEMA: Final = "action-qbc-v8-arm-receipt-v2"
_VALIDATION_SCHEMA: Final = "action-qbc-v8-payload-validation-receipt-v1"
_REGISTRATION_PATH: Final = "artifacts/action_qbc_v8_open_registration.json"
_SCRIPT_PATH: Final = "scripts/execute_action_qbc_v8_open_lifecycle.py"
_EXECUTION_ROOT: Final = Path("/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open")
_PREPARATION_SOURCE_URL: Final = (
    "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi"
)
_AUTHORITY_ROOT: Final = _EXECUTION_ROOT / "authority"
_PROCESSES_ROOT: Final = _EXECUTION_ROOT / "processes"
_A_ROOT: Final = _PROCESSES_ROOT / "process-a"
_B_ROOT: Final = _PROCESSES_ROOT / "process-b"
_A_OUTPUT: Final = _PROCESSES_ROOT / "process-a-output/open/action_qbc_v8_open_diagnostic.json"
_B_OUTPUT: Final = _PROCESSES_ROOT / "process-b-output/open/action_qbc_v8_open_diagnostic.json"
_PREPARATION: Final = _EXECUTION_ROOT / "preparation-receipt.json"
_PREPARATION_VERIFICATION: Final = _EXECUTION_ROOT / "preparation-verification.json"
_WINDOWS_CLAIM: Final = Path("/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json")
_REMOTE_CLAIM: Final = _EXECUTION_ROOT / "remote-verification-claim.json"
_REMOTE_VERIFIER: Final = _EXECUTION_ROOT / "remote-verifier-start-claim.json"
_REMOTE_RECEIPT: Final = _EXECUTION_ROOT / "remote-verification.json"
_REMOTE_SUPERVISOR: Final = _EXECUTION_ROOT / "remote-verification-supervisor.json"
_ARM: Final = _EXECUTION_ROOT / "arm-receipt.json"
_DRIVER: Final = _EXECUTION_ROOT / "lifecycle-driver-claim.json"
_LEDGER: Final = _EXECUTION_ROOT / "lifecycle-ledger.json"
_A_START: Final = _EXECUTION_ROOT / "process-a-start-claim.json"
_A_VALIDATOR: Final = _EXECUTION_ROOT / "process-a-validator-claim.json"
_A_VALIDATION: Final = _EXECUTION_ROOT / "process-a-validation.json"
_B_START: Final = _EXECUTION_ROOT / "process-b-start-claim.json"
_B_VALIDATOR: Final = _EXECUTION_ROOT / "process-b-validator-claim.json"
_B_VALIDATION: Final = _EXECUTION_ROOT / "process-b-validation.json"
_FINAL_BUNDLE: Final = _EXECUTION_ROOT / "finalization-bundle.json"
_EMERGENCY_BUNDLE: Final = _EXECUTION_ROOT / "emergency-result-bundle.json"
_OWNER_CLAIM: Final = _EXECUTION_ROOT / "result-git-owner.json"
_WORK_ROOT: Final = _EXECUTION_ROOT / "result-git-work"
_RESULT_TAG: Final = "action-qbc-v8-open-diagnostic-result-v1"
_RESULT_TAG_REF: Final = f"refs/tags/{_RESULT_TAG}"
_RESULT_BRANCH_REF: Final = "refs/heads/action-qbc-v8-open-diagnostic-result"
_GIT: str = "/usr/bin/git"
_LOCAL_GIT_TIMEOUT: Final = 60
_DRIVER_DEADLINE: Final = 8400
_DRIVER_RESERVE: Final = 1200
_DRIVER_CLEANUP_SECONDS: Final = 10
_PUBLISHER_WRAPPER_SECONDS: Final = 600
_PUBLISHER_CONTROL_SECONDS: Final = 570
_PUBLISHER_CLEANUP_SECONDS: Final = 10
_EVIDENCE_CAP: Final = 67_108_864
_GIT_CONTROL_DEADLINE: float | None = None
_AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v8_enabled": False,
    "final_admission_claimed": False,
}
_WINDOWS_REPOSITORY_CONTRACT: Final = {
    "active_hooks_allowed": False,
    "common_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "forbidden_admin_relative_paths": [
        r".git\commondir", r".git\config.worktree", r".git\index.lock",
        r".git\info\attributes", r".git\info\grafts", r".git\info\sparse-checkout",
        r".git\objects\info\alternates", r".git\objects\info\http-alternates",
        r".git\refs\replace", r".git\shallow",
    ],
    "forbidden_pack_suffixes": [".promisor"],
    "forbidden_ref_prefixes": ["refs/replace/"],
    "git_config_byte_count": 846,
    "git_config_sha256": "a78fd50c029f9b0755a7fceac2b77a39479c30becb2eff1794d77df5d185f702",
    "git_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "index_path": r"D:\kaggle competitions\arc3-crosslevel-voi\.git\index",
    "info_exclude_byte_count": 240,
    "info_exclude_sha256": "6671fe83b7a07c8932ee89164d1f2793b2318058eb8b98dc5c06ee0a5a3b0ec1",
    "local_config": {
        "branch.action-qbc-v6-prereg.merge": "refs/heads/action-qbc-v6-prereg",
        "branch.action-qbc-v6-prereg.remote": "origin",
        "branch.action-qbc-v7-open-diagnostic.merge": "refs/heads/action-qbc-v7-open-diagnostic",
        "branch.action-qbc-v7-open-diagnostic.remote": "origin",
        "branch.action-qbc-v7-prereg.merge": "refs/heads/action-qbc-v7-prereg",
        "branch.action-qbc-v7-prereg.remote": "origin",
        "branch.action-qbc-v8-prereg.merge": "refs/heads/action-qbc-v8-prereg",
        "branch.action-qbc-v8-prereg.remote": "origin",
        "branch.main.merge": "refs/heads/main",
        "branch.main.remote": "origin",
        "core.bare": "false", "core.filemode": "false", "core.ignorecase": "true",
        "core.logallrefupdates": "true", "core.repositoryformatversion": "0",
        "core.sshcommand": "ssh -i .git/arc3_crosslevel_voi_deploy_key -o IdentitiesOnly=yes -o UserKnownHostsFile=.git/github_known_hosts -o StrictHostKeyChecking=yes",
        "core.symlinks": "false",
        "remote.origin.fetch": "+refs/heads/*:refs/remotes/origin/*",
        "remote.origin.url": "https://github.com/bansarinejad/arc3-crosslevel-voi.git",
    },
    "plain_admin_relative_directories": [
        ".git", r".git\hooks", r".git\info", r".git\objects",
        r".git\objects\info", r".git\objects\pack", r".git\refs",
    ],
    "repository_ancestor_chain": [
        "D:\\", r"D:\kaggle competitions",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
    ],
    "repository_root": r"D:\kaggle competitions\arc3-crosslevel-voi",
}
_UNDERLYING_ORDER: Final = (
    "preparation_receipt_invalid", "preparation_verification_invalid",
    "remote_verification_failed", "remote_receipt_invalid", "arm_receipt_invalid",
    "registration_invalid", "authority_identity_invalid", "lifecycle_ledger_invalid",
    "lifecycle_driver_failed", "process_a_nonzero", "process_a_output_missing",
    "process_a_validation_failed", "process_b_nonzero", "process_b_output_missing",
    "process_b_validation_failed", "payload_byte_mismatch",
)
_SEQUENCE: Final = (
    "arm_returned", "process_a_runner_returned", "process_a_validator_returned",
    "process_b_runner_returned", "process_b_validator_returned",
)
_REGISTRATION_KEYS: Final = frozenset(
    {
        "schema_version", "status", "treatment_id", "diagnostic_system_id",
        "comparison_semantics_id", "runtime_id", "preregistration", "v6_negative",
        "platform", "dependencies", "source_manifest", "scene_inventory", "row_inventory",
        "transform_contracts", "scientific_contract", "resource_contract",
        "execution_contract", "authorization", "content_sha256",
    }
)
_EXECUTION_KEYS: Final = frozenset(
    {
        "administrative_stage_order", "argv_hashes", "arm_argv", "arm_receipt_path",
        "arm_timeout_seconds", "authority_root", "bootstrap_steps",
        "compute_deadline_seconds", "driver_deadline_seconds", "emergency_bundle_path",
        "environment_build_argv", "execution_root", "finalization_bundle_path",
        "finalizer_argv_template", "finalizer_cwd", "finalizer_timeout_seconds",
        "hard_timeout_seconds", "lifecycle_driver_argv", "lifecycle_driver_claim_path",
        "lifecycle_ledger_path", "linux_host_launcher", "linux_platform",
        "linux_tool_identities", "local_git_timeout_seconds",
        "payload_validator_argv_template", "payload_validator_timeout_seconds",
        "post_preparation_validation_argv", "preflight_argvs", "preparation_argv",
        "preparation_command_environment", "preparation_command_policy",
        "preparation_receipt_path", "preparation_verification_receipt_path",
        "process_a_output", "process_a_root", "process_a_start_claim",
        "process_a_validation_receipt", "process_a_validator_claim", "process_b_output",
        "process_b_root", "process_b_start_claim", "process_b_validation_receipt",
        "process_b_validator_claim", "process_labels", "producer_argv",
        "reconstructor_argv", "registered_start_count", "remote_claim_linux_path",
        "remote_claim_windows_path", "remote_policy", "remote_receipt_linux_path",
        "remote_receipt_windows_path", "remote_supervisor_argv",
        "remote_supervisor_receipt_linux_path", "remote_supervisor_receipt_windows_path",
        "remote_verifier_argv", "remote_verifier_claim_linux_path",
        "remote_verifier_claim_windows_path", "result_document_contract",
        "result_git_environment", "result_git_max_attempts", "result_git_owner_path",
        "result_git_work_root", "result_publisher_argv", "result_ref_transaction",
        "scientific_argv_template", "test_argvs", "third_start_allowed",
        "wall_time_seconds", "windows_repository_contract",
    }
)
_DRIVER_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "open_freeze_commit_sha", "registration_content_sha256", "remote_claim_sha256", "driver_argv_sha256"}
)
_LEDGER_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "open_freeze_commit_sha", "registration_content_sha256", "driver_claim_sha256", "arm_exit_code", "arm_receipt_sha256", "sequence", "process_a", "process_b", "stage"}
)
_LEDGER_PROCESS_KEYS: Final = frozenset(
    {"label", "cwd", "runner_argv_sha256", "runner_exit_code", "validator_argv_sha256", "validator_exit_code", "start_claim_sha256", "validator_claim_sha256", "validation_receipt_sha256", "output_sha256"}
)
_ARM_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha",
        "registration_content_sha256", "preparation_receipt_exists",
        "preparation_receipt_read_status", "preparation_receipt_sha256",
        "preparation_verification_receipt_exists",
        "preparation_verification_receipt_read_status",
        "preparation_verification_receipt_sha256", "remote_claim_sha256",
        "remote_verifier_claim_sha256", "remote_receipt_sha256",
        "remote_supervisor_receipt_sha256", "status",
    }
)
_VALIDATION_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "label", "start_claim_sha256", "validator_claim_sha256", "payload_path", "payload_sha256", "payload_size_bytes", "status"}
)
_PREPARATION_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "attempts", "authority", "process_a",
        "process_b", "command_ledger", "commands_sha256",
        "command_environment_sha256", "status",
    }
)
_PREPARATION_CLONE_KEYS: Final = frozenset(
    {
        "root", "root_device", "root_inode", "root_owner_uid", "root_mode",
        "head_sha", "tree_sha256", "raw_materialization_sha256",
        "git_status_sha256", "python_version", "uv_version",
        "environment_inventory", "environment_inventory_sha256",
        "venv_materialization_sha256", "venv_python_sha256", "passes",
    }
)
_PREPARATION_VERIFICATION_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "preparation_receipt_sha256",
        "verification_argv_sha256", "authority", "process_a", "process_b", "status",
        "content_sha256",
    }
)
_PREPARATION_VERIFICATION_CLONE_KEYS: Final = _PREPARATION_CLONE_KEYS - frozenset(
    {"environment_inventory"}
)
_PREPARATION_ATTEMPT_KEYS: Final = frozenset(
    {"attempt_index", "process_a_stage", "process_b_stage", "cleanup", "promotion", "passes"}
)
_PREPARATION_CLEANUP_KEYS: Final = frozenset({"owned_paths", "removed", "passes"})
_PREPARATION_PROMOTION_KEYS: Final = frozenset(
    {"source_path", "destination_path", "source_device", "source_inode", "passes"}
)
_PREPARATION_PROCESS_STAGES: Final = frozenset(
    {"not_started", "clone_failed", "raw_audit_failed", "environment_failed", "preflight_failed", "completed"}
)
_PREPARATION_COMMAND_KEYS: Final = frozenset(
    {
        "sequence_index", "attempt_index", "label", "phase", "cwd", "argv",
        "argv_sha256", "stdin_size_bytes", "stdin_sha256", "started", "exit_code",
        "outcome", "timed_out", "duration_milliseconds", "stdout_size_bytes",
        "stdout_sha256", "stderr_size_bytes", "stderr_sha256", "child_cleanup_passes",
    }
)
_PREPARATION_PHASES: Final = frozenset(
    {"clone", "git_config", "checkout", "raw_audit", "environment_build", "preflight"}
)
_PREPARATION_OUTCOMES: Final = frozenset(
    {"completed", "nonzero", "timeout", "stdin_limit", "stdout_limit", "stderr_limit", "spawn_error"}
)
_DISTRIBUTION_KEYS: Final = frozenset(
    {"normalized_name", "version", "file_count", "files_sha256"}
)
_START_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "label", "open_freeze_commit_sha", "registration_content_sha256", "arm_receipt_sha256", "lifecycle_driver_claim_sha256", "scientific_argv_sha256", "prior_validation_receipt_sha256", "output_path"}
)
_VALIDATOR_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "label", "lifecycle_driver_claim_sha256", "start_claim_sha256", "validator_argv_sha256", "payload_sha256"}
)
_PROCESS_KEYS: Final = frozenset(
    {"label", "output_path", "exit_code", "validator_exit_code", "start_claim", "start_claim_sha256", "validator_claim", "validator_claim_sha256", "validation_receipt", "validation_receipt_sha256", "payload_exists", "payload_valid", "payload_sha256", "payload_size_bytes"}
)
_COMMON_RESULT_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "preparation_receipt",
        "preparation_receipt_exists", "preparation_receipt_read_status",
        "preparation_receipt_sha256", "preparation_verification_receipt",
        "preparation_verification_receipt_exists",
        "preparation_verification_receipt_read_status",
        "preparation_verification_receipt_sha256", "remote_verification_claim",
        "remote_verifier_claim", "remote_verification_receipt",
        "remote_supervisor_receipt", "arm_receipt", "lifecycle_driver_claim",
        "lifecycle_ledger", "process_a", "process_b", "payloads_byte_identical",
    }
)
_RECEIPT_KEYS: Final = _COMMON_RESULT_KEYS | frozenset(
    {"published_payload_path", "published_payload_sha256", "authorization"}
)
_ADMIN_KEYS: Final = _COMMON_RESULT_KEYS | frozenset({"stage", "authorization"})
_REMOTE_CLAIM_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag", "registration_content_sha256", "supervisor_argv_sha256", "supervisor_script_git_blob_sha1", "supervisor_script_sha256", "verifier_script_git_blob_sha1", "verifier_script_sha256"}
)
_REMOTE_VERIFIER_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "claim_sha256", "open_freeze_commit_sha", "registration_content_sha256", "verifier_argv_sha256"}
)
_REMOTE_RECEIPT_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "claim_sha256", "verifier_start_claim_sha256", "open_freeze_commit_sha", "open_freeze_tag", "registration_content_sha256", "remote_url", "ref", "python", "git", "taskkill", "policy", "attempts", "status", "selected_attempt", "total_duration_milliseconds"}
)
_REMOTE_SUPERVISOR_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "claim_sha256", "verifier_start_claim_sha256", "open_freeze_commit_sha", "registration_content_sha256", "verifier_argv_sha256", "verifier_exit_code", "classification", "timed_out", "duration_milliseconds", "stdout_size_bytes", "stdout_sha256", "stdout_base64", "stderr_size_bytes", "stderr_sha256", "stderr_base64", "child_cleanup_passes", "remote_receipt_sha256", "status"}
)
_REMOTE_ATTEMPT_KEYS: Final = frozenset(
    {"attempt_index", "exit_code", "classification", "timed_out", "duration_milliseconds", "stdout_size_bytes", "stdout_sha256", "stdout_base64", "stderr_size_bytes", "stderr_sha256", "stderr_base64", "child_cleanup_passes"}
)
_REMOTE_RETRYABLE: Final = frozenset(
    {"retryable_empty_exit_0", "retryable_timeout_124", "retryable_git_128"}
)
_NORMAL_BUNDLE_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "open_freeze_commit_sha", "registration_content_sha256", "disposition", "stage", "underlying_stage", "files", "authorization", "content_sha256"}
)
_EMERGENCY_BUNDLE_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha",
        "registration_content_sha256", "disposition", "stage", "underlying_stage",
        "finalizer_classification", "finalizer_exit_code", "finalizer_timed_out",
        "finalizer_child_cleanup_passes", "finalization_bundle_exists",
        "finalization_bundle_sha256", "lifecycle_ledger_exists",
        "lifecycle_ledger_sha256", "preparation_receipt_exists",
        "preparation_receipt_read_status", "preparation_receipt_sha256",
        "preparation_verification_receipt_exists",
        "preparation_verification_receipt_read_status",
        "preparation_verification_receipt_sha256", "files", "authorization",
        "content_sha256",
    }
)
_FILE_KEYS: Final = frozenset({"path", "mode", "size_bytes", "sha256", "content_base64"})
_OWNER_KEYS: Final = frozenset(
    {"schema_version", "treatment_id", "open_freeze_commit_sha", "registration_content_sha256", "driver_claim_sha256", "work_root", "owner_nonce"}
)


class LifecycleError(RuntimeError):
    """Fail-closed lifecycle or publication error."""


class _AttemptError(LifecycleError):
    """A publication-attempt failure that may advance to the next registered attempt."""


@dataclass(frozen=True, slots=True)
class _EvidenceState:
    exists: bool
    read_status: str
    raw: bytes | None
    sha256: str | None
    value: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class _ChildResult:
    spawned: bool
    exit_code: int | None
    timed_out: bool | None
    child_cleanup_passes: bool | None
    classification: str


class _LifecycleChildCleanupFailure(LifecycleError):
    """Terminal outer-PGID cleanup failure with its truthful child evidence."""

    def __init__(self, child: str, result: _ChildResult) -> None:
        if (
            result.classification != "child_cleanup_failed"
            or result.child_cleanup_passes is not False
        ):
            raise ValueError("cleanup-failure exception requires false cleanup evidence")
        self.child = child
        self.result = result
        super().__init__(
            "lifecycle child cleanup failed: "
            f"child={child}; exit_code={result.exit_code!r}; "
            f"timed_out={result.timed_out!r}; child_cleanup_passes=false"
        )


def _fail(message: str) -> NoReturn:
    raise LifecycleError(message)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_oid(kind: str, raw: bytes) -> str:
    return hashlib.sha1(
        kind.encode("ascii") + b" " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_canonical(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("ascii"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, ValueError, TypeError) as error:
        raise LifecycleError(f"{label} is not strict ASCII JSON") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        _fail(f"{label} is not one canonical JSON object")
    return value


def _hex(value: object, length: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(
        character not in "0123456789abcdef" for character in value
    ):
        _fail(f"{label} is not lowercase {length}-hex")
    return value


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
    )


def _file_change_identity(metadata: os.stat_result) -> tuple[int, int]:
    # Windows ctime is not a stable mutation clock across path-stat and fstat.  NTFS
    # mtime is 100 ns resolution, so retain that clock after exact normalization.
    if os.name == "nt":
        return (metadata.st_mtime_ns // 100, 0)
    return (metadata.st_mtime_ns, metadata.st_ctime_ns)


def _is_reparse_point(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _permitted_plain_metadata(metadata: os.stat_result, maximum: int) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_point(metadata)
        and 0 <= metadata.st_size <= maximum
    )


def _bounded_descriptor_bytes(descriptor: int, maximum: int, label: str) -> bytes:
    raw = bytearray()
    while True:
        allowance = maximum + 1 - len(raw)
        if allowance <= 0:
            _fail(f"{label} exceeds its byte limit")
        chunk = os.read(descriptor, min(1 << 20, allowance))
        if not chunk:
            return bytes(raw)
        raw.extend(chunk)
        if len(raw) > maximum:
            _fail(f"{label} exceeds its byte limit")


def _plain_bytes(path: Path, label: str, *, maximum: int = 134_217_728) -> bytes:
    try:
        before_path = path.stat(follow_symlinks=False)
    except OSError as error:
        raise LifecycleError(f"{label} is unavailable") from error
    if not _permitted_plain_metadata(before_path, maximum):
        _fail(f"{label} is not a permitted plain file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise LifecycleError(f"{label} cannot be safely opened") from error
    try:
        opened = os.fstat(descriptor)
        if (
            not _permitted_plain_metadata(opened, maximum)
            or _file_identity(before_path) != _file_identity(opened)
            or _file_change_identity(before_path) != _file_change_identity(opened)
        ):
            _fail(f"{label} changed before it was opened")
        raw = _bounded_descriptor_bytes(descriptor, maximum, label)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _bounded_descriptor_bytes(descriptor, maximum, label) != raw:
            _fail(f"{label} changed between descriptor reads")
        after_descriptor = os.fstat(descriptor)
    except OSError as error:
        raise LifecycleError(f"{label} cannot be read") from error
    finally:
        os.close(descriptor)
    try:
        after_path = path.stat(follow_symlinks=False)
    except OSError as error:
        raise LifecycleError(f"{label} changed while being read") from error
    if (
        not _permitted_plain_metadata(after_descriptor, maximum)
        or not _permitted_plain_metadata(after_path, maximum)
        or _file_identity(opened) != _file_identity(after_descriptor)
        or _file_identity(after_descriptor) != _file_identity(after_path)
        or _file_change_identity(opened) != _file_change_identity(after_descriptor)
        or _file_change_identity(after_descriptor) != _file_change_identity(after_path)
        or len(raw) != after_descriptor.st_size
    ):
        _fail(f"{label} changed while being read")
    return raw


def _evidence_state(
    path: Path,
    label: str,
    *,
    maximum: int = _EVIDENCE_CAP,
) -> _EvidenceState:
    """Capture one fixed evidence basename without hiding unsafe existing entries."""

    if not path.is_absolute() or path.name in {"", ".", ".."}:
        _fail(f"{label} path is not one fixed absolute basename")
    parent = _open_directory_nofollow(path.parent, f"{label} parent")
    descriptor: int | None = None
    try:
        try:
            names = os.listdir(parent)
        except OSError:
            return _EvidenceState(True, "read_error", None, None, None)
        if path.name not in names:
            return _EvidenceState(False, "absent", None, None, None)
        try:
            before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except OSError:
            return _EvidenceState(True, "read_error", None, None, None)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or (os.name == "posix" and before.st_uid != _owner_uid())
            or (os.name == "posix" and stat.S_IMODE(before.st_mode) != 0o600)
        ):
            return _EvidenceState(True, "unsafe_type", None, None, None)
        if before.st_size < 0 or before.st_size > maximum:
            return _EvidenceState(True, "oversized", None, None, None)
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(path.name, flags, dir_fd=parent)
            opened = os.fstat(descriptor)
            raw = _bounded_descriptor_bytes(descriptor, maximum, label)
            after = os.fstat(descriptor)
            after_path = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except OSError:
            return _EvidenceState(True, "read_error", None, None, None)
        def identity(value: os.stat_result) -> tuple[int, int, int, int, int, int, int, int]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_uid,
                stat.S_IFMT(value.st_mode),
                stat.S_IMODE(value.st_mode),
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )
        if (
            identity(before) != identity(opened)
            or identity(opened) != identity(after)
            or identity(after) != identity(after_path)
            or len(raw) != after.st_size
        ):
            return _EvidenceState(True, "changed_during_read", None, None, None)
        try:
            value = _parse_canonical(raw, label)
        except LifecycleError:
            value = None
        digest = _sha256(raw)
        return _EvidenceState(True, "readable", raw, digest, value)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _optional_raw(path: Path) -> bytes | None:
    return _evidence_state(path, str(path)).raw


def _strict_optional_raw(path: Path, label: str) -> bytes | None:
    """Return absent or exact plain-file bytes; never disguise an unsafe path as absence."""

    try:
        return _plain_bytes(path, label)
    except LifecycleError as error:
        if not isinstance(error.__cause__, FileNotFoundError):
            raise
        # Linearize an absent result only after a second no-follow lookup.  If an
        # entry appeared between lookups, treating it as absent would hide evidence.
        try:
            path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as second_error:
            raise LifecycleError(f"{label} absence cannot be verified") from second_error
        _fail(f"{label} appeared while absence was checked")


def _raw_sha_or_none(path: Path) -> str | None:
    raw = _optional_raw(path)
    return _sha256(raw) if raw is not None else None


def _require_absent(path: Path, label: str) -> None:
    if path.exists() or path.is_symlink():
        _fail(f"{label} must be absent")


def _owner_uid() -> int:
    return Path("/proc/self").stat().st_uid if os.name == "posix" else -1


def _plain_directory(
    path: Path,
    label: str,
    *,
    mode: int | None = None,
    owner: bool = True,
) -> os.stat_result:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise LifecycleError(f"{label} is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        _fail(f"{label} is not a plain directory")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        _fail(f"{label} has the wrong mode")
    if owner and os.name == "posix" and metadata.st_uid != _owner_uid():
        _fail(f"{label} has the wrong owner")
    return metadata


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_bytes(path: Path, raw: bytes, *, mode: int = 0o600) -> None:
    parent = _open_directory_nofollow(path.parent, f"{path} parent")
    parent_before = os.fstat(parent)
    if os.name == "posix" and (
        parent_before.st_uid != _owner_uid()
        or stat.S_IMODE(parent_before.st_mode) != 0o700
    ):
        os.close(parent)
        _fail(f"{path} parent has the wrong owner or mode")
    if path.name in os.listdir(parent):
        os.close(parent)
        _fail(f"{path} already exists")
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=parent,
        )
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
        reopened = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
        try:
            metadata = os.fstat(reopened)
            observed_buffer = bytearray()
            while len(observed_buffer) <= len(raw):
                chunk = os.read(
                    reopened,
                    min(1 << 20, len(raw) + 1 - len(observed_buffer)),
                )
                if not chunk:
                    break
                observed_buffer.extend(chunk)
            observed = bytes(observed_buffer)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != mode
                or metadata.st_size != len(raw)
                or observed != raw
            ):
                _fail(f"exclusive publication changed bytes: {path}")
        finally:
            os.close(reopened)
        parent_after = os.fstat(parent)
        if (
            parent_before.st_dev,
            parent_before.st_ino,
            parent_before.st_uid,
            stat.S_IFMT(parent_before.st_mode),
            stat.S_IMODE(parent_before.st_mode),
        ) != (
            parent_after.st_dev,
            parent_after.st_ino,
            parent_after.st_uid,
            stat.S_IFMT(parent_after.st_mode),
            stat.S_IMODE(parent_after.st_mode),
        ):
            _fail(f"{path} parent identity changed during publication")
    finally:
        os.close(parent)


def _exclusive_json(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = canonical_json_bytes(value)
    _exclusive_bytes(path, raw)
    reopened = _evidence_state(path, str(path))
    if reopened.raw != raw or reopened.value != value:
        _fail(f"exclusive canonical publication failed: {path}")
    return raw


def _base_git_environment(authority: Path, index_path: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_DIR": str(authority / ".git"),
        "GIT_WORK_TREE": str(authority),
        "GIT_INDEX_FILE": str(index_path),
        "GIT_AUTHOR_NAME": "ARC3 v8 Result Bot",
        "GIT_AUTHOR_EMAIL": "arc3-v8-result@invalid.example",
        "GIT_AUTHOR_DATE": "2026-08-11T00:00:00+10:00",
        "GIT_COMMITTER_NAME": "ARC3 v8 Result Bot",
        "GIT_COMMITTER_EMAIL": "arc3-v8-result@invalid.example",
        "GIT_COMMITTER_DATE": "2026-08-11T00:00:00+10:00",
    }


def _preparation_command_environment() -> dict[str, str]:
    """Return the exact empty-built nonpublisher Linux command environment."""
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/bansarinejad",
        "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_COUNT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_CACHE_DIR": "/home/bansarinejad/.cache/uv",
        "UV_NO_PROGRESS": "1",
        "UV_PYTHON_DOWNLOADS": "never",
    }


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _wait_group_empty(pgid: int, endpoint: float) -> bool:
    while time.monotonic() < endpoint:
        if not _process_group_exists(pgid):
            return True
        time.sleep(min(0.01, max(0.0, endpoint - time.monotonic())))
    return not _process_group_exists(pgid)


def _terminate_group(
    process: subprocess.Popen[bytes], *, cleanup_deadline: float
) -> bool:
    """TERM/KILL one owned PGID against a single fixed ten-second endpoint."""
    if not hasattr(os, "killpg"):
        return False
    pgid = process.pid
    cleanup_start = time.monotonic()
    cleanup_deadline = min(cleanup_deadline, cleanup_start + _DRIVER_CLEANUP_SECONDS)
    term_endpoint = min(cleanup_start + 5.0, cleanup_deadline)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    if _wait_group_empty(pgid, term_endpoint):
        with contextlib.suppress(subprocess.TimeoutExpired, ChildProcessError):
            process.wait(timeout=0)
        return True
    try:
        os.killpg(pgid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except ProcessLookupError:
        return True
    except OSError:
        return False
    passed = _wait_group_empty(pgid, cleanup_deadline)
    try:
        process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
    except (subprocess.TimeoutExpired, ChildProcessError):
        passed = False
    return passed and not _process_group_exists(pgid)


def _git_process(
    authority: Path,
    environment: Mapping[str, str],
    argv: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    allow_nonzero: bool = False,
) -> tuple[int, bytes, bytes]:
    if len(argv) < 2 or argv[:2] != [_GIT, "--no-replace-objects"]:
        _fail("Git child does not use the literal no-replacement executable prefix")
    if _GIT_CONTROL_DEADLINE is None:
        _fail("Git child has no active absolute control deadline")
    started = time.monotonic()
    cleanup_deadline = started + _LOCAL_GIT_TIMEOUT + 10
    if cleanup_deadline > _GIT_CONTROL_DEADLINE:
        _fail("complete local Git allowance does not fit its absolute control deadline")
    process = subprocess.Popen(
        list(argv), cwd=authority, env=dict(environment),
        stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(
            input=input_bytes,
            timeout=max(0.0, started + _LOCAL_GIT_TIMEOUT - time.monotonic()),
        )
    except subprocess.TimeoutExpired as error:
        process.terminate()
        try:
            process.wait(timeout=max(0.0, started + 65 - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
            except subprocess.TimeoutExpired as cleanup_error:
                raise _AttemptError("registered local Git child cleanup failed") from cleanup_error
        raise _AttemptError("registered local Git child timed out") from error
    if process.returncode != 0 and not allow_nonzero:
        raise _AttemptError(
            f"registered local Git child returned {process.returncode}: "
            + stderr.decode("utf-8", errors="replace")[:512]
        )
    return cast(int, process.returncode), stdout, stderr


def _git(
    authority: Path,
    environment: Mapping[str, str],
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    _code, stdout, _stderr = _git_process(
        authority,
        environment,
        [_GIT, "--no-replace-objects", *arguments],
        input_bytes=input_bytes,
    )
    return stdout


def _validate_object_pack_sources(root: Path) -> None:
    """Reject unsafe object-pack paths and every promisor sidecar without following links."""

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptors: list[int] = []
    try:
        try:
            git_descriptor = os.open(root / ".git", flags)
            descriptors.append(git_descriptor)
            objects_descriptor = os.open("objects", flags, dir_fd=git_descriptor)
            descriptors.append(objects_descriptor)
            pack_descriptor = os.open("pack", flags, dir_fd=objects_descriptor)
            descriptors.append(pack_descriptor)
        except OSError as error:
            raise LifecycleError(
                "local Git object-pack directory is unavailable as a no-follow directory"
            ) from error

        for descriptor in descriptors:
            try:
                metadata = os.fstat(descriptor)
            except OSError as error:
                raise LifecycleError(
                    "cannot inspect local Git object-pack directory ancestry"
                ) from error
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                _fail("local Git object-pack directory ancestry is not owner-controlled")

        try:
            with os.scandir(pack_descriptor) as entries:
                for entry in entries:
                    if entry.name.endswith(".promisor"):
                        _fail("promisor object-pack sidecar is forbidden")
        except OSError as error:
            raise LifecycleError(
                "cannot inspect local Git object-pack directory"
            ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _derive_o8(authority: Path, environment: Mapping[str, str]) -> str:
    _validate_object_pack_sources(authority)
    for tag, expected, label in (
        (_P8V1_TAG, _P8V1_COMMIT, "P8v1"),
        (_P8V2_TAG, _P8V2_COMMIT, "P8v2"),
        (_P8V3_TAG, _P8V3_COMMIT, "P8v3"),
        (_PREREGISTRATION_TAG, _PREREGISTRATION_COMMIT, "P8v4"),
    ):
        ref = f"refs/tags/{tag}"
        if (
            _git(authority, environment, "cat-file", "-t", ref) != b"commit\n"
            or _git(authority, environment, "rev-parse", ref)
            != f"{expected}\n".encode("ascii")
        ):
            _fail(f"{label} lightweight tag identity is invalid")
    for child, parent, label in (
        (_P8V1_COMMIT, _R7_COMMIT, "P8v1"),
        (_P8V2_COMMIT, _P8V1_COMMIT, "P8v2"),
        (_P8V3_COMMIT, _P8V2_COMMIT, "P8v3"),
        (_PREREGISTRATION_COMMIT, _P8V3_COMMIT, "P8v4"),
    ):
        if _git(authority, environment, "rev-list", "--parents", "-n", "1", child) != (
            f"{child} {parent}\n".encode("ascii")
        ):
            _fail(f"{label} is not the exact registered direct child")
    if _git(
        authority, environment, "diff", "--name-status", "--no-renames", "-z",
        _R7_COMMIT, _P8V1_COMMIT,
    ) != b"A\0" + _P8V2_DOCUMENT.encode("utf-8") + b"\0":
        _fail("R7..P8v1 is not the one-document addition")
    if _git(
        authority, environment, "diff", "--name-status", "--no-renames", "-z",
        _P8V1_COMMIT, _P8V2_COMMIT,
    ) != b"M\0" + _P8V2_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v1..P8v2 is not the one-document correction")
    if _git(
        authority, environment, "diff", "--name-status", "--no-renames", "-z",
        _P8V2_COMMIT, _P8V3_COMMIT,
    ) != b"A\0" + _P8V3_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v2..P8v3 is not the one-document correction")
    if _git(
        authority, environment, "diff", "--name-status", "--no-renames", "-z",
        _P8V3_COMMIT, _PREREGISTRATION_COMMIT,
    ) != b"A\0" + _PREREGISTRATION_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v3..P8v4 is not the one-document correction")
    for commit_id, path, blob, digest, count, label in (
        (_P8V1_COMMIT, _P8V2_DOCUMENT, _P8V1_DOCUMENT_BLOB, _P8V1_DOCUMENT_SHA256, None, "P8v1"),
        (_P8V2_COMMIT, _P8V2_DOCUMENT, _P8V2_DOCUMENT_BLOB, _P8V2_DOCUMENT_SHA256, _P8V2_DOCUMENT_BYTE_COUNT, "P8v2"),
        (_P8V3_COMMIT, _P8V3_DOCUMENT, _P8V3_DOCUMENT_BLOB, _P8V3_DOCUMENT_SHA256, _P8V3_DOCUMENT_BYTE_COUNT, "P8v3"),
        (_PREREGISTRATION_COMMIT, _PREREGISTRATION_DOCUMENT, _PREREGISTRATION_DOCUMENT_BLOB, _PREREGISTRATION_DOCUMENT_SHA256, _PREREGISTRATION_DOCUMENT_BYTE_COUNT, "P8v4"),
    ):
        raw = _git(authority, environment, "cat-file", "blob", f"{commit_id}:{path}")
        if (
            _git_oid("blob", raw) != blob
            or _sha256(raw) != digest
            or (count is not None and len(raw) != count)
        ):
            _fail(f"{label} document byte identity is invalid")
    tag_ref = f"refs/tags/{_OPEN_FREEZE_TAG}"
    if _git(authority, environment, "cat-file", "-t", tag_ref) != b"commit\n":
        _fail("O8 tag is absent or annotated")
    commit = _git(authority, environment, "rev-parse", tag_ref).decode("ascii", "strict").strip()
    _hex(commit, 40, "O8 commit")
    raw = _git(authority, environment, "cat-file", "-p", commit)
    if _git_oid("commit", raw) != commit:
        _fail("O8 commit bytes do not reproduce its object ID")
    header, separator, _message = raw.partition(b"\n\n")
    if not separator:
        _fail("O8 commit object has no header/message separator")
    parents = [
        _hex(line[7:].decode("ascii", "strict"), 40, "O8 parent")
        for line in header.splitlines()
        if line.startswith(b"parent ")
    ]
    if parents != [_PREREGISTRATION_COMMIT]:
        _fail("O8 is not an exact one-parent direct child of P8")
    if _git(authority, environment, "rev-parse", "HEAD").decode("ascii", "strict").strip() != commit:
        _fail("authority HEAD differs from O8")
    return commit


def _load_registration(
    authority: Path,
    registration_relative: str,
    commit: str,
    environment: Mapping[str, str],
) -> tuple[dict[str, Any], bytes]:
    if registration_relative != _REGISTRATION_PATH:
        _fail("registration argument differs from the registered path")
    raw = _plain_bytes(authority / registration_relative, "registration")
    if _git(authority, environment, "cat-file", "blob", f"{commit}:{registration_relative}") != raw:
        _fail("registration raw bytes differ from the O8 blob")
    value = _parse_canonical(raw, "registration")
    if set(value) != _REGISTRATION_KEYS:
        _fail("registration does not have exactly nineteen keys")
    preimage = dict(value)
    claimed = preimage.pop("content_sha256", None)
    if (
        value.get("schema_version") != _REGISTRATION_SCHEMA
        or value.get("status") != "registered_zero_result"
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("runtime_id") is not None
        or value.get("authorization") != _AUTHORIZATION
        or claimed != canonical_sha256(preimage)
    ):
        _fail("registration fixed/content identity is invalid")
    execution = value.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is absent")
    return value, raw


def _verify_own_source(
    authority: Path, commit: str, environment: Mapping[str, str]
) -> None:
    expected = (authority / _SCRIPT_PATH).resolve(strict=True)
    observed = Path(sys.argv[0]).resolve(strict=True)
    if expected != observed:
        _fail("lifecycle-driver source origin differs from O8")
    raw = _plain_bytes(expected, "lifecycle-driver source")
    if _git(authority, environment, "cat-file", "blob", f"{commit}:{_SCRIPT_PATH}") != raw:
        _fail("lifecycle-driver raw source differs from its O8 blob")


def _execution(registration: Mapping[str, Any]) -> Mapping[str, Any]:
    value = registration.get("execution_contract")
    if not isinstance(value, Mapping):
        _fail("registration execution contract is invalid")
    return value


def _command_hash(execution: Mapping[str, Any], name: str, value: object) -> str:
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping):
        _fail("registration argv hashes are absent")
    digest = canonical_sha256(value)
    if hashes.get(name) != digest:
        _fail(f"registered {name} command hash is invalid")
    return digest


def _require_string_argv(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(f"{label} is not an ordered string argv")
    return cast(list[str], value)


def _substitute(template: object, replacements: Mapping[str, str], label: str) -> list[str]:
    argv = _require_string_argv(template, label)
    result = [replacements.get(item, item) for item in argv]
    if any(item.startswith("<") and item.endswith(">") for item in result):
        _fail(f"{label} retains an unresolved placeholder")
    return result


def _require_registered_execution(
    registration: Mapping[str, Any],
    *,
    execute_argv: Sequence[str] | None = None,
    publish_argv: Sequence[str] | None = None,
) -> Mapping[str, Any]:
    execution = _execution(registration)
    if set(execution) != _EXECUTION_KEYS:
        _fail("registration execution contract does not have exactly the P8v4 70-key schema")
    if execution.get("windows_repository_contract") != _WINDOWS_REPOSITORY_CONTRACT:
        _fail("registered Windows repository contract differs from P8v4")
    fixed_paths = {
        "execution_root": str(_EXECUTION_ROOT), "authority_root": str(_AUTHORITY_ROOT),
        "preparation_receipt_path": str(_PREPARATION),
        "preparation_verification_receipt_path": str(_PREPARATION_VERIFICATION),
        "arm_receipt_path": str(_ARM),
        "process_a_root": str(_A_ROOT), "process_b_root": str(_B_ROOT),
        "process_a_output": str(_A_OUTPUT), "process_b_output": str(_B_OUTPUT),
        "process_a_start_claim": str(_A_START), "process_b_start_claim": str(_B_START),
        "process_a_validator_claim": str(_A_VALIDATOR), "process_b_validator_claim": str(_B_VALIDATOR),
        "process_a_validation_receipt": str(_A_VALIDATION), "process_b_validation_receipt": str(_B_VALIDATION),
        "lifecycle_driver_claim_path": str(_DRIVER), "lifecycle_ledger_path": str(_LEDGER),
        "finalization_bundle_path": str(_FINAL_BUNDLE), "emergency_bundle_path": str(_EMERGENCY_BUNDLE),
        "result_git_owner_path": str(_OWNER_CLAIM), "result_git_work_root": str(_WORK_ROOT),
    }
    if any(execution.get(key) != value for key, value in fixed_paths.items()):
        _fail("registration lifecycle path binding is invalid")
    if (
        execution.get("driver_deadline_seconds") != _DRIVER_DEADLINE
        or execution.get("local_git_timeout_seconds") != _LOCAL_GIT_TIMEOUT
        or execution.get("result_git_max_attempts") != 3
        or execution.get("registered_start_count") != 2
        or execution.get("process_labels") != ["A", "B"]
        or execution.get("third_start_allowed") is not False
        or execution.get("arm_timeout_seconds") != 120
        or execution.get("payload_validator_timeout_seconds") != 300
        or execution.get("finalizer_timeout_seconds") != 300
        or execution.get("hard_timeout_seconds") != 2700
        or execution.get("compute_deadline_seconds") != 2100
        or execution.get("wall_time_seconds") != 2400
        or execution.get("finalizer_cwd") != str(_AUTHORITY_ROOT)
        or execution.get("administrative_stage_order") != {
            "underlying_order": list(_UNDERLYING_ORDER),
            "disposition_overrides": [
                "receipt_finalization_failed", "finalizer_process_failed"
            ],
        }
    ):
        _fail("registration lifecycle bounds are invalid")
    if execution.get("preparation_command_environment") != _preparation_command_environment():
        _fail("registered preparation command environment is invalid")
    if execution.get("preparation_command_policy") != {
        "default_timeout_seconds": 60,
        "environment_timeout_seconds": 600,
        "term_grace_seconds": 5,
        "kill_grace_seconds": 5,
        "stdin_cap_bytes": 1_048_576,
        "stdout_cap_bytes": 134_217_728,
        "stderr_cap_bytes": 1_048_576,
    }:
        _fail("registered preparation command policy is invalid")
    command_fields = {
        "arm": "arm_argv", "lifecycle_driver": "lifecycle_driver_argv",
        "scientific": "scientific_argv_template", "payload_validator": "payload_validator_argv_template",
        "finalizer": "finalizer_argv_template", "result_publisher": "result_publisher_argv",
        "result_ref_transaction": "result_ref_transaction",
    }
    for name, field in command_fields.items():
        _command_hash(execution, name, execution.get(field))

    def require_pair_after(
        argv_value: object,
        *,
        pair: tuple[str, str],
        anchor: tuple[str, str],
        label: str,
    ) -> list[str]:
        argv = _require_string_argv(argv_value, label)
        if argv.count(pair[0]) != 1 or argv.count(anchor[0]) != 1:
            _fail(f"registered {label} has duplicated or absent fixed anchors")
        anchor_at = argv.index(anchor[0])
        pair_at = argv.index(pair[0])
        if (
            argv[anchor_at : anchor_at + 2] != list(anchor)
            or argv[pair_at : pair_at + 2] != list(pair)
            or pair_at != anchor_at + 2
        ):
            _fail(f"registered {label} preparation-verification pair is misplaced")
        return argv

    verification_pair = (
        "--preparation-verification-receipt", str(_PREPARATION_VERIFICATION)
    )
    arm_argv = require_pair_after(
        execution.get("arm_argv"),
        pair=verification_pair,
        anchor=("--preparation-receipt", str(_PREPARATION)),
        label="arm command",
    )
    require_pair_after(
        execution.get("lifecycle_driver_argv"),
        pair=verification_pair,
        anchor=("--preparation-receipt", str(_PREPARATION)),
        label="lifecycle-driver command",
    )
    scientific_argv = require_pair_after(
        execution.get("scientific_argv_template"),
        pair=verification_pair,
        anchor=("--registration", _REGISTRATION_PATH),
        label="scientific command",
    )
    finalizer_argv = require_pair_after(
        execution.get("finalizer_argv_template"),
        pair=verification_pair,
        anchor=("--preparation-receipt", str(_PREPARATION)),
        label="finalizer command",
    )
    validator_argv = _require_string_argv(
        execution.get("payload_validator_argv_template"), "payload-validator command"
    )
    publisher_argv = _require_string_argv(
        execution.get("result_publisher_argv"), "result-publisher command"
    )
    for label, argv, duration, kill_after in (
        ("arm", arm_argv, "120s", "--kill-after=5s"),
        ("scientific", scientific_argv, "2700s", "--kill-after=15s"),
        ("payload validator", validator_argv, "300s", "--kill-after=5s"),
        ("finalizer", finalizer_argv, "300s", "--kill-after=5s"),
        ("result publisher", publisher_argv, "600s", "--kill-after=5s"),
    ):
        if argv[:4] != ["/usr/bin/timeout", "--signal=TERM", kill_after, duration] or "--foreground" in argv:
            _fail(f"registered {label} wrapper is not the corrected non-foreground command")
    if verification_pair[0] in validator_argv:
        _fail("payload-validator command must not receive preparation verification directly")
    if publisher_argv[-2:] != ["--control-time-seconds", str(_PUBLISHER_CONTROL_SECONDS)]:
        _fail("result-publisher inner control anchor is invalid")
    if execute_argv is not None and list(execute_argv) != execution.get("lifecycle_driver_argv"):
        _fail("observed execute argv differs from registration")
    if publish_argv is not None and list(publish_argv) != execution.get("result_publisher_argv"):
        _fail("observed publish argv differs from registration")
    expected_environment = _base_git_environment(_AUTHORITY_ROOT, _WORK_ROOT / "index-<i>")
    if execution.get("result_git_environment") != expected_environment:
        _fail("registered result Git environment differs from P8")
    return execution


def _read_canonical(
    path: Path,
    label: str,
    *,
    keys: frozenset[str] | None = None,
    schema: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    raw = _plain_bytes(path, label)
    value = _parse_canonical(raw, label)
    if keys is not None and set(value) != keys:
        _fail(f"{label} has an invalid key set")
    if schema is not None and value.get("schema_version") != schema:
        _fail(f"{label} has an invalid schema")
    if value.get("treatment_id") != _TREATMENT_ID:
        _fail(f"{label} has an invalid treatment")
    return value, raw


def _validate_windows_claim(
    path: Path,
    *,
    commit: str,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    if path != _WINDOWS_CLAIM:
        _fail("Windows lifecycle claim path differs from P8")
    claim, raw = _read_canonical(
        path, "raw Windows lifecycle claim", keys=_REMOTE_CLAIM_KEYS,
        schema="action-qbc-v8-remote-tag-verification-claim-v1",
    )
    if (
        claim.get("open_freeze_commit_sha") != commit
        or claim.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or claim.get("registration_content_sha256") != registration.get("content_sha256")
        or claim.get("supervisor_argv_sha256") != cast(Mapping[str, Any], execution["argv_hashes"]).get("remote_supervisor")
    ):
        _fail("raw Windows lifecycle claim identity is invalid")
    for key, length in (
        ("supervisor_script_git_blob_sha1", 40), ("supervisor_script_sha256", 64),
        ("verifier_script_git_blob_sha1", 40), ("verifier_script_sha256", 64),
    ):
        _hex(claim.get(key), length, f"Windows claim {key}")
    return claim, raw


def _acquire_driver_claim(
    *,
    commit: str,
    registration: Mapping[str, Any],
    windows_claim_raw: bytes,
    execution: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    _plain_directory(_EXECUTION_ROOT, "execution root", mode=0o700)
    _require_absent(_DRIVER, "lifecycle driver claim")
    for path in (_REMOTE_CLAIM, _REMOTE_VERIFIER, _REMOTE_RECEIPT, _REMOTE_SUPERVISOR):
        _require_absent(path, f"pre-arm Linux remote copy {path.name}")
    claim = {
        "schema_version": _DRIVER_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "remote_claim_sha256": _sha256(windows_claim_raw),
        "driver_argv_sha256": cast(Mapping[str, Any], execution["argv_hashes"])["lifecycle_driver"],
    }
    if set(claim) != _DRIVER_KEYS:
        _fail("internal driver claim schema is invalid")
    raw = _exclusive_json(_DRIVER, claim)
    return claim, raw


def _artifact_hash(path: Path) -> str | None:
    raw = _optional_raw(path)
    return _sha256(raw) if raw is not None else None


def _process_record(
    label: str,
    root: Path,
) -> dict[str, Any]:
    result = {
        "label": label,
        "cwd": str(root),
        "runner_argv_sha256": None,
        "runner_exit_code": None,
        "validator_argv_sha256": None,
        "validator_exit_code": None,
        "start_claim_sha256": None,
        "validator_claim_sha256": None,
        "validation_receipt_sha256": None,
        "output_sha256": None,
    }
    if set(result) != _LEDGER_PROCESS_KEYS:
        _fail("internal ledger process schema is invalid")
    return result


def _update_process_artifacts(
    record: dict[str, Any],
    *,
    start: Path,
    validator: Path,
    validation: Path,
    output: Path,
) -> None:
    record["start_claim_sha256"] = _artifact_hash(start)
    record["validator_claim_sha256"] = _artifact_hash(validator)
    record["validation_receipt_sha256"] = _artifact_hash(validation)
    record["output_sha256"] = _artifact_hash(output)


def _child_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C", "LC_ALL": "C", "TZ": "UTC", "PYTHONNOUSERSITE": "1",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def _require_child_start_window(
    *, deadline: float, allowance_seconds: int, reserve_seconds: int
) -> None:
    if time.monotonic() + allowance_seconds > deadline - reserve_seconds:
        raise LifecycleError("registered driver reserve prevents another child start")


def _run_child_evidence(
    argv: Sequence[str],
    cwd: Path,
    *,
    wrapper_seconds: int,
    deadline: float,
    reserve_seconds: int,
) -> _ChildResult:
    if (
        len(argv) < 4
        or argv[0] != "/usr/bin/timeout"
        or argv[1] != "--signal=TERM"
        or not argv[2].startswith("--kill-after=")
        or not argv[2].endswith("s")
        or argv[3] != f"{wrapper_seconds}s"
        or "--foreground" in argv
    ):
        _fail("registered lifecycle child is not one exact non-foreground GNU-timeout wrapper")
    try:
        kill_after_seconds = int(argv[2][len("--kill-after=") : -1])
    except ValueError as error:
        raise LifecycleError("GNU-timeout kill-after is not an integer duration") from error
    if kill_after_seconds not in {5, 15}:
        _fail("GNU-timeout kill-after differs from the registered lifecycle allowances")
    allowance = wrapper_seconds + kill_after_seconds + _DRIVER_CLEANUP_SECONDS
    try:
        _require_child_start_window(
            deadline=deadline,
            allowance_seconds=allowance,
            reserve_seconds=reserve_seconds,
        )
    except LifecycleError:
        return _ChildResult(False, None, None, None, "deadline_admission_failed")
    child_started = time.monotonic()
    cleanup_deadline = min(
        child_started + allowance,
        deadline - reserve_seconds,
    )
    try:
        process = subprocess.Popen(
            list(argv), cwd=cwd, env=_child_environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return _ChildResult(False, None, None, None, "spawn_error")
    timeout_initiated = False
    try:
        process.wait(
            timeout=max(
                0.0,
                child_started + wrapper_seconds + kill_after_seconds - time.monotonic(),
            )
        )
    except subprocess.TimeoutExpired:
        timeout_initiated = True
    cleanup: bool | None = None
    if timeout_initiated or _process_group_exists(process.pid):
        cleanup = _terminate_group(process, cleanup_deadline=cleanup_deadline)
    exit_code = process.poll()
    timed_out = timeout_initiated or exit_code == 124
    if cleanup is False:
        classification = "child_cleanup_failed"
    elif timed_out:
        classification = "timeout"
    elif exit_code is None:
        classification = "spawned_no_return"
    elif exit_code != 0:
        classification = "nonzero"
    else:
        classification = "completed"
    return _ChildResult(True, exit_code, timed_out, cleanup, classification)


def _run_child(
    argv: Sequence[str],
    cwd: Path,
    *,
    wrapper_seconds: int,
    deadline: float,
    reserve_seconds: int,
) -> int | None:
    result = _run_child_evidence(
        argv,
        cwd,
        wrapper_seconds=wrapper_seconds,
        deadline=deadline,
        reserve_seconds=reserve_seconds,
    )
    if result.classification == "child_cleanup_failed":
        raise _LifecycleChildCleanupFailure("unidentified", result)
    if result.classification in {
        "deadline_admission_failed", "spawn_error", "spawned_no_return",
    } or result.exit_code is None:
        raise LifecycleError(f"lifecycle child failed: {result.classification}")
    return result.exit_code


def _run_named_child(
    child: str,
    argv: Sequence[str],
    cwd: Path,
    *,
    wrapper_seconds: int,
    deadline: float,
    reserve_seconds: int,
) -> int | None:
    """Run one registered child and attach its fixed lifecycle identity on failure."""

    try:
        return _run_child(
            argv,
            cwd,
            wrapper_seconds=wrapper_seconds,
            deadline=deadline,
            reserve_seconds=reserve_seconds,
        )
    except _LifecycleChildCleanupFailure as error:
        raise _LifecycleChildCleanupFailure(child, error.result) from error


def _valid_receipt(
    path: Path,
    *,
    keys: frozenset[str],
    schema: str,
    commit: str,
    registration_sha: str,
) -> tuple[dict[str, Any] | None, bytes | None]:
    raw = _optional_raw(path)
    if raw is None:
        return None, None
    try:
        value = _parse_canonical(raw, str(path))
    except LifecycleError:
        return None, raw
    if (
        set(value) != keys
        or value.get("schema_version") != schema
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
    ):
        return None, raw
    return value, raw


def _remote_and_arm_stage(
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> str | None:
    preparation_state = _evidence_state(_PREPARATION, "preparation receipt")
    if (
        preparation_state.read_status != "readable"
        or preparation_state.value is None
    ):
        return "preparation_receipt_invalid"
    try:
        _validate_embedded_preparation_success(
            preparation_state.value,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
            execution=execution,
        )
    except (LifecycleError, OSError, ValueError):
        return "preparation_receipt_invalid"
    verification_state = _evidence_state(
        _PREPARATION_VERIFICATION, "preparation verification receipt"
    )
    if verification_state.read_status != "readable" or verification_state.value is None:
        return "preparation_verification_invalid"
    try:
        _validate_embedded_preparation_verification(
            verification_state.value,
            preparation=preparation_state.value,
            commit=commit,
            registration_sha=registration_sha,
            execution=execution,
        )
    except (LifecycleError, OSError, ValueError):
        return "preparation_verification_invalid"
    claim, claim_raw = _valid_receipt(
        _REMOTE_CLAIM, keys=_REMOTE_CLAIM_KEYS,
        schema="action-qbc-v8-remote-tag-verification-claim-v1",
        commit=commit, registration_sha=registration_sha,
    )
    verifier, verifier_raw = _valid_receipt(
        _REMOTE_VERIFIER, keys=_REMOTE_VERIFIER_KEYS,
        schema="action-qbc-v8-remote-tag-verifier-start-claim-v1",
        commit=commit, registration_sha=registration_sha,
    )
    receipt, receipt_raw = _valid_receipt(
        _REMOTE_RECEIPT, keys=_REMOTE_RECEIPT_KEYS,
        schema="action-qbc-v8-remote-tag-verification-receipt-v1",
        commit=commit, registration_sha=registration_sha,
    )
    supervisor, supervisor_raw = _valid_receipt(
        _REMOTE_SUPERVISOR, keys=_REMOTE_SUPERVISOR_KEYS,
        schema="action-qbc-v8-remote-tag-verification-supervisor-receipt-v1",
        commit=commit, registration_sha=registration_sha,
    )
    claim_sha = _sha256(claim_raw) if claim_raw is not None else None
    verifier_sha = _sha256(verifier_raw) if verifier_raw is not None else None
    receipt_sha = _sha256(receipt_raw) if receipt_raw is not None else None
    claim_valid = claim is not None and claim.get("open_freeze_tag") == _OPEN_FREEZE_TAG
    verifier_valid = verifier is not None and verifier.get("claim_sha256") == claim_sha
    receipt_valid = bool(
        receipt is not None
        and receipt.get("claim_sha256") == claim_sha
        and receipt.get("verifier_start_claim_sha256") == verifier_sha
        and receipt.get("open_freeze_tag") == _OPEN_FREEZE_TAG
        and receipt.get("status") in {"verified", "failed"}
    )
    supervisor_valid = bool(
        supervisor is not None
        and supervisor.get("claim_sha256") == claim_sha
        and supervisor.get("verifier_start_claim_sha256") == verifier_sha
        and supervisor.get("remote_receipt_sha256") == receipt_sha
        and supervisor.get("status") in {"completed", "failed"}
    )
    supervisor_status = supervisor.get("status") if supervisor is not None else None
    receipt_status = receipt.get("status") if receipt is not None else None
    remote_failed = bool(
        claim_valid and supervisor_valid
        and (supervisor_status == "failed" or (receipt_valid and receipt_status == "failed"))
    )
    remote_success = bool(
        claim_valid and verifier_valid and receipt_valid and supervisor_valid
        and receipt_status == "verified" and supervisor_status == "completed"
    )
    if remote_failed:
        return "remote_verification_failed"
    if not remote_success:
        return "remote_receipt_invalid"
    arm, arm_raw = _valid_receipt(
        _ARM, keys=_ARM_KEYS, schema=_ARM_SCHEMA, commit=commit,
        registration_sha=registration_sha,
    )
    if not (
        arm is not None and arm_raw is not None and arm.get("status") == "armed"
        and arm.get("preparation_receipt_exists") is True
        and arm.get("preparation_receipt_read_status") == "readable"
        and arm.get("preparation_receipt_sha256") == preparation_state.sha256
        and arm.get("preparation_verification_receipt_exists") is True
        and arm.get("preparation_verification_receipt_read_status") == "readable"
        and arm.get("preparation_verification_receipt_sha256") == verification_state.sha256
        and arm.get("remote_claim_sha256") == claim_sha
        and arm.get("remote_verifier_claim_sha256") == verifier_sha
        and arm.get("remote_receipt_sha256") == receipt_sha
        and arm.get("remote_supervisor_receipt_sha256") == (_sha256(supervisor_raw) if supervisor_raw is not None else None)
    ):
        return "arm_receipt_invalid"
    return None


def _validation_is_valid(
    path: Path,
    *,
    label: str,
    output: Path,
) -> bool:
    raw = _optional_raw(path)
    payload = _optional_raw(output)
    start_path = _A_START if label == "A" else _B_START
    validator_path = _A_VALIDATOR if label == "A" else _B_VALIDATOR
    start_raw = _optional_raw(start_path)
    validator_raw = _optional_raw(validator_path)
    if raw is None or payload is None or start_raw is None or validator_raw is None:
        return False
    try:
        value = _parse_canonical(raw, f"process {label} validation receipt")
    except LifecycleError:
        return False
    return bool(
        set(value) == _VALIDATION_KEYS
        and value.get("schema_version") == _VALIDATION_SCHEMA
        and value.get("treatment_id") == _TREATMENT_ID
        and value.get("label") == label
        and value.get("start_claim_sha256") == _sha256(start_raw)
        and value.get("validator_claim_sha256") == _sha256(validator_raw)
        and value.get("payload_path") == str(output)
        and value.get("payload_sha256") == _sha256(payload)
        and value.get("payload_size_bytes") == len(payload)
        and value.get("status") == "valid"
    )


def _ledger_value(
    *,
    commit: str,
    registration_sha: str,
    driver_raw: bytes,
    arm_exit: int | None,
    sequence: Sequence[str],
    process_a: Mapping[str, Any],
    process_b: Mapping[str, Any],
    stage: str | None,
) -> dict[str, Any]:
    result = {
        "schema_version": _LEDGER_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "driver_claim_sha256": _sha256(driver_raw),
        "arm_exit_code": arm_exit,
        "arm_receipt_sha256": _artifact_hash(_ARM),
        "sequence": list(sequence),
        "process_a": dict(process_a),
        "process_b": dict(process_b),
        "stage": stage,
    }
    if set(result) != _LEDGER_KEYS:
        _fail("internal lifecycle ledger schema is invalid")
    if result["sequence"] != list(_SEQUENCE[: len(sequence)]):
        _fail("internal lifecycle sequence is not a registered prefix")
    return result


def _decode_file_object(value: object) -> tuple[str, bytes]:
    if not isinstance(value, Mapping) or set(value) != _FILE_KEYS:
        _fail("bundle file object has an invalid key set")
    path = value.get("path")
    if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts:
        _fail("bundle file path is not a canonical repository-relative path")
    if value.get("mode") != "100644":
        _fail("bundle file mode is not 100644")
    encoded = value.get("content_base64")
    if not isinstance(encoded, str):
        _fail("bundle file Base64 is not a string")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise LifecycleError("bundle file Base64 is invalid") from error
    if value.get("size_bytes") != len(raw) or value.get("sha256") != _sha256(raw):
        _fail("bundle file size/SHA-256 identity is invalid")
    return path, raw


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(f"{label} is not a nonnegative integer")
    return value


def _actual_exit(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{label} is not an actual integer return")
    return value


def _optional_sha(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _hex(value, 64, label)


def _embedded_machine_object(
    value: object,
    *,
    keys: frozenset[str],
    schema: str,
    commit: str,
    registration_sha: str,
    label: str,
) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or value.get("schema_version") != schema
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
    ):
        _fail(f"embedded {label} identity/schema is invalid")
    return value


def _validate_result_process(
    value: object,
    *,
    label: str,
    commit: str,
    registration_sha: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PROCESS_KEYS:
        _fail(f"result process {label} schema is invalid")
    expected_output = str(_A_OUTPUT if label == "A" else _B_OUTPUT)
    if value.get("label") != label or value.get("output_path") != expected_output:
        _fail(f"result process {label} identity is invalid")
    for member in ("exit_code", "validator_exit_code"):
        observed = value.get(member)
        if observed is not None:
            _nonnegative_int(observed, f"result process {label} {member}")
    if value.get("validator_exit_code") is not None and value.get("exit_code") != 0:
        _fail(f"result process {label} validator order is invalid")
    for member in (
        "start_claim_sha256",
        "validator_claim_sha256",
        "validation_receipt_sha256",
        "payload_sha256",
    ):
        _optional_sha(value.get(member), f"result process {label} {member}")

    start = value.get("start_claim")
    if start is not None:
        if (
            not isinstance(start, Mapping)
            or set(start) != _START_KEYS
            or start.get("schema_version") != "action-qbc-v8-scientific-start-claim-v1"
            or start.get("treatment_id") != _TREATMENT_ID
            or start.get("label") != label
            or start.get("open_freeze_commit_sha") != commit
            or start.get("registration_content_sha256") != registration_sha
            or start.get("output_path") != expected_output
            or value.get("start_claim_sha256") != canonical_sha256(start)
        ):
            _fail(f"result process {label} embedded start claim is invalid")
        for member in (
            "arm_receipt_sha256",
            "lifecycle_driver_claim_sha256",
            "scientific_argv_sha256",
        ):
            _hex(start.get(member), 64, f"process {label} start {member}")
        _optional_sha(
            start.get("prior_validation_receipt_sha256"),
            f"process {label} prior validation SHA-256",
        )

    validator_claim = value.get("validator_claim")
    if validator_claim is not None:
        if (
            not isinstance(validator_claim, Mapping)
            or set(validator_claim) != _VALIDATOR_KEYS
            or validator_claim.get("schema_version")
            != "action-qbc-v8-payload-validator-claim-v1"
            or validator_claim.get("treatment_id") != _TREATMENT_ID
            or validator_claim.get("label") != label
            or value.get("validator_claim_sha256") != canonical_sha256(validator_claim)
        ):
            _fail(f"result process {label} embedded validator claim is invalid")
        for member in (
            "lifecycle_driver_claim_sha256",
            "start_claim_sha256",
            "validator_argv_sha256",
            "payload_sha256",
        ):
            _hex(validator_claim.get(member), 64, f"process {label} validator {member}")

    validation = value.get("validation_receipt")
    if validation is not None:
        if (
            not isinstance(validation, Mapping)
            or set(validation) != _VALIDATION_KEYS
            or validation.get("schema_version") != _VALIDATION_SCHEMA
            or validation.get("treatment_id") != _TREATMENT_ID
            or validation.get("label") != label
            or validation.get("payload_path") != expected_output
            or validation.get("status") != "valid"
            or value.get("validation_receipt_sha256") != canonical_sha256(validation)
        ):
            _fail(f"result process {label} embedded validation receipt is invalid")
        _hex(
            validation.get("start_claim_sha256"),
            64,
            f"process {label} validation start SHA-256",
        )
        _hex(
            validation.get("validator_claim_sha256"),
            64,
            f"process {label} validation claim SHA-256",
        )
        _hex(
            validation.get("payload_sha256"),
            64,
            f"process {label} validation payload SHA-256",
        )
        _nonnegative_int(
            validation.get("payload_size_bytes"),
            f"process {label} validation payload size",
        )

    payload_exists = value.get("payload_exists")
    payload_valid = value.get("payload_valid")
    payload_sha = value.get("payload_sha256")
    payload_size = value.get("payload_size_bytes")
    if not isinstance(payload_exists, bool) or not isinstance(payload_valid, bool):
        _fail(f"result process {label} payload flags are invalid")
    if payload_exists:
        if payload_sha is None:
            _fail(f"result process {label} existing payload lacks raw identity")
        _nonnegative_int(payload_size, f"result process {label} payload size")
    elif payload_sha is not None or payload_size is not None or payload_valid:
        _fail(f"result process {label} absent payload evidence is inconsistent")
    if payload_valid and (
        value.get("exit_code") != 0
        or value.get("validator_exit_code") != 0
        or start is None
        or validator_claim is None
        or validation is None
        or validator_claim.get("start_claim_sha256") != value.get("start_claim_sha256")
        or validator_claim.get("payload_sha256") != payload_sha
        or validation.get("start_claim_sha256") != value.get("start_claim_sha256")
        or validation.get("validator_claim_sha256")
        != value.get("validator_claim_sha256")
        or validation.get("payload_sha256") != payload_sha
        or validation.get("payload_size_bytes") != payload_size
    ):
        _fail(f"result process {label} valid-payload evidence is inconsistent")
    return value


def _decode_machine_stream(value: Mapping[str, Any], prefix: str, cap: int) -> bytes:
    size = _nonnegative_int(value.get(f"{prefix}_size_bytes"), f"{prefix} size")
    if size > cap:
        _fail(f"{prefix} exceeds its registered cap")
    digest = _hex(value.get(f"{prefix}_sha256"), 64, f"{prefix} SHA-256")
    encoded = value.get(f"{prefix}_base64")
    if not isinstance(encoded, str) or any(ord(character) > 127 for character in encoded):
        _fail(f"{prefix} Base64 is invalid")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (TypeError, ValueError) as exc:
        raise LifecycleError(f"{prefix} Base64 is invalid") from exc
    if (
        base64.b64encode(raw).decode("ascii") != encoded
        or len(raw) != size
        or _sha256(raw) != digest
    ):
        _fail(f"{prefix} byte identity is invalid")
    return raw


def _preparation_attempt_plan() -> tuple[tuple[str, str, str | None, bool], ...]:
    clone = (
        ("clone", "clone", True),
        ("git_config", "config", True),
        ("git_config", "config", True),
        ("git_config", "config", True),
        ("checkout", "checkout", True),
        ("git_config", "remote", True),
        ("git_config", "config", False),
        ("raw_audit", "cat-file", False),
        ("raw_audit", "rev-parse", False),
    )
    raw_audit = (
        ("git_config", "config", False),
        ("raw_audit", "rev-parse", False),
        ("raw_audit", "ls-tree", False),
        ("raw_audit", "cat-file", False),
        ("raw_audit", "ls-files", False),
        ("raw_audit", "status", False),
    )
    result: list[tuple[str, str, str | None, bool]] = []
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in clone)
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in raw_audit)
    for label in ("A", "B"):
        result.append((label, "environment_build", None, False))
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in raw_audit)
    for label in ("A", "B"):
        result.extend((label, "preflight", None, False) for _ in range(5))
    if len(result) != 54:
        _fail("internal preparation command plan is not exactly 54 rows")
    return tuple(result)


def _preparation_git_subcommand(argv: Sequence[str]) -> str | None:
    if len(argv) < 3 or argv[:2] != ["/usr/bin/git", "--no-replace-objects"]:
        return None
    if argv[2] == "-C":
        return argv[4] if len(argv) >= 5 else None
    return argv[2]


def _preparation_manifest_request(registration: Mapping[str, Any]) -> bytes:
    manifest = registration.get("source_manifest")
    if not isinstance(manifest, Mapping):
        _fail("registered preparation source manifest is invalid")
    rows: list[tuple[str, str]] = []
    for member in ("preregistration_tree", "open_freeze_added_files"):
        values = manifest.get(member)
        if not isinstance(values, list):
            _fail("registered preparation source-manifest rows are invalid")
        for value in values:
            if not isinstance(value, Mapping):
                _fail("registered preparation source-manifest row is invalid")
            path = value.get("path")
            oid = value.get("git_blob_sha1")
            if not isinstance(path, str) or not path or "\x00" in path:
                _fail("registered preparation source-manifest path is invalid")
            rows.append((path, _hex(oid, 40, "registered source blob SHA-1")))
    registration_raw = canonical_json_bytes(registration)
    registration_oid = hashlib.sha1(
        b"blob "
        + str(len(registration_raw)).encode("ascii")
        + b"\0"
        + registration_raw,
        usedforsecurity=False,
    ).hexdigest()
    rows.append((_REGISTRATION_PATH, registration_oid))
    rows.sort(key=lambda item: item[0].encode("utf-8"))
    if len(rows) != len({path for path, _oid in rows}):
        _fail("registered preparation source-manifest paths are duplicated")
    return b"".join(oid.encode("ascii") + b"\n" for _path, oid in rows)


def _preparation_command_identity(
    *,
    attempt_index: int | None,
    label: str,
    phase: str,
    cwd: str,
    argv: Sequence[str],
    stdin_bytes: bytes = b"",
) -> dict[str, Any]:
    arguments = list(argv)
    return {
        "attempt_index": attempt_index,
        "label": label,
        "phase": phase,
        "cwd": cwd,
        "argv": arguments,
        "argv_sha256": canonical_sha256(arguments),
        "stdin_size_bytes": len(stdin_bytes),
        "stdin_sha256": _sha256(stdin_bytes),
    }


def _preparation_expected_raw_audit_identities(
    *,
    attempt_index: int,
    label: str,
    root: str,
    commit: str,
    request: bytes,
) -> list[dict[str, Any]]:
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", root]
    commands: tuple[tuple[str, list[str], bytes], ...] = (
        ("git_config", [*prefix, "config", "--local", "--null", "--list"], b""),
        ("raw_audit", [*prefix, "rev-parse", "HEAD"], b""),
        (
            "raw_audit",
            [*prefix, "ls-tree", "-r", "-l", "-z", "--full-tree", commit],
            b"",
        ),
        ("raw_audit", [*prefix, "cat-file", "--batch"], request),
        ("raw_audit", [*prefix, "ls-files", "--stage", "-z"], b""),
        (
            "raw_audit",
            [*prefix, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            b"",
        ),
    )
    return [
        _preparation_command_identity(
            attempt_index=attempt_index,
            label=label,
            phase=phase,
            cwd=root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _preparation_expected_attempt_identities(
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    attempt_index: int,
    commit: str,
) -> list[dict[str, Any]]:
    execution_root_value = execution.get("execution_root")
    environment_argv = execution.get("environment_build_argv")
    preflight_argvs = execution.get("preflight_argvs")
    if (
        not isinstance(execution_root_value, str)
        or not execution_root_value.startswith("/")
        or not isinstance(environment_argv, list)
        or not environment_argv
        or not all(isinstance(item, str) and item for item in environment_argv)
        or not isinstance(preflight_argvs, list)
        or len(preflight_argvs) != 5
        or not all(
            isinstance(argv, list)
            and argv
            and all(isinstance(item, str) and item for item in argv)
            for argv in preflight_argvs
        )
    ):
        _fail("registered preparation command arrays are invalid")
    source = f"{execution_root_value.rstrip('/')}/.prepare-attempt-{attempt_index}"
    roots = {"A": f"{source}/process-a", "B": f"{source}/process-b"}
    request = _preparation_manifest_request(registration)
    result: list[dict[str, Any]] = []

    def append(
        label: str,
        phase: str,
        cwd: str,
        argv: Sequence[str],
        stdin_bytes: bytes = b"",
    ) -> None:
        result.append(
            _preparation_command_identity(
                attempt_index=attempt_index,
                label=label,
                phase=phase,
                cwd=cwd,
                argv=argv,
                stdin_bytes=stdin_bytes,
            )
        )

    for label, root in roots.items():
        clone_commands: tuple[tuple[str, list[str]], ...] = (
            (
                "clone",
                [
                    "/usr/bin/git", "--no-replace-objects", "clone", "--no-local",
                    "--no-checkout", "--branch", _OPEN_FREEZE_TAG, "--single-branch",
                    _PREPARATION_SOURCE_URL, root,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.autocrlf", "false",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.eol", "lf",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.safecrlf", "true",
                ],
            ),
            (
                "checkout",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "checkout",
                    "--detach", commit,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "remote",
                    "remove", "origin",
                ],
            ),
        )
        for phase, argv in clone_commands:
            append(label, phase, source, argv)
        prefix = ["/usr/bin/git", "--no-replace-objects", "-C", root]
        append(
            label,
            "git_config",
            root,
            [*prefix, "config", "--local", "--null", "--list"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*prefix, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*prefix, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
    for label, root in roots.items():
        result.extend(
            _preparation_expected_raw_audit_identities(
                attempt_index=attempt_index,
                label=label,
                root=root,
                commit=commit,
                request=request,
            )
        )
    for label, root in roots.items():
        append(label, "environment_build", root, environment_argv)
    for label, root in roots.items():
        result.extend(
            _preparation_expected_raw_audit_identities(
                attempt_index=attempt_index,
                label=label,
                root=root,
                commit=commit,
                request=request,
            )
        )
    for label, root in roots.items():
        for argv in preflight_argvs:
            append(label, "preflight", root, argv)
    if len(result) != 54:
        _fail("internal preparation command identity plan is not exactly 54 rows")
    return result


def _preparation_expected_authority_identities(
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    commit: str,
) -> list[dict[str, Any]]:
    authority_root = execution.get("authority_root")
    if not isinstance(authority_root, str) or not authority_root.startswith("/"):
        _fail("registered authority root is invalid")
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", authority_root]
    commands: list[tuple[str, list[str], bytes]] = []

    def append(phase: str, arguments: Sequence[str], stdin_bytes: bytes = b"") -> None:
        commands.append((phase, [*prefix, *arguments], stdin_bytes))

    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", "HEAD"])
    for prior_tag, prior_commit, parent_commit in (
        (_P8V1_TAG, _P8V1_COMMIT, _R7_COMMIT),
        (_P8V2_TAG, _P8V2_COMMIT, _P8V1_COMMIT),
        (_P8V3_TAG, _P8V3_COMMIT, _P8V2_COMMIT),
        (_PREREGISTRATION_TAG, _PREREGISTRATION_COMMIT, _P8V3_COMMIT),
    ):
        append("raw_audit", ["cat-file", "-t", f"refs/tags/{prior_tag}"])
        append("raw_audit", ["rev-parse", f"refs/tags/{prior_tag}"])
        append("raw_audit", ["rev-list", "--parents", "-n", "1", prior_commit])
        append(
            "raw_audit",
            [
                "diff", "--name-status", "--no-renames", "-z", parent_commit,
                prior_commit,
            ],
        )
    append(
        "raw_audit",
        ["ls-tree", "-z", _PREREGISTRATION_COMMIT, "--", _PREREGISTRATION_DOCUMENT],
    )
    append(
        "raw_audit",
        [
            "cat-file", "blob",
            f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}",
        ],
    )
    append("raw_audit", ["rev-list", "--parents", "-n", "1", commit])
    append(
        "raw_audit",
        [
            "diff", "--name-status", "--no-renames", "-z",
            _PREREGISTRATION_COMMIT, commit,
        ],
    )
    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append("raw_audit", ["ls-tree", "-r", "-l", "-z", "--full-tree", commit])
    append(
        "raw_audit",
        ["cat-file", "--batch"],
        _preparation_manifest_request(registration),
    )
    append("raw_audit", ["ls-files", "--stage", "-z"])
    append(
        "raw_audit",
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )
    return [
        _preparation_command_identity(
            attempt_index=None,
            label="authority",
            phase=phase,
            cwd=authority_root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _validate_preparation_clone_semantics(
    value: Any,
    *,
    name: str,
    expected_root: Any,
    commit: str,
    environment: bool,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PREPARATION_CLONE_KEYS:
        _fail(f"embedded preparation {name} clone schema is invalid")
    if (
        not isinstance(expected_root, str)
        or value.get("root") != expected_root
        or value.get("head_sha") != commit
        or value.get("passes") is not True
    ):
        _fail(f"embedded preparation {name} clone identity is invalid")
    for member in ("root_device", "root_inode", "root_owner_uid", "root_mode"):
        _nonnegative_int(value.get(member), f"preparation {name} {member}")
    for member in ("tree_sha256", "raw_materialization_sha256", "git_status_sha256"):
        _hex(value.get(member), 64, f"preparation {name} {member}")
    if value.get("git_status_sha256") != _sha256(b""):
        _fail(f"embedded preparation {name} clone is not Git-clean")
    environment_members = (
        "python_version",
        "uv_version",
        "environment_inventory",
        "environment_inventory_sha256",
        "venv_materialization_sha256",
        "venv_python_sha256",
    )
    if not environment:
        if any(value.get(member) is not None for member in environment_members):
            _fail("embedded authority preparation environment is not null")
        return value
    if value.get("python_version") != "3.12.13" or value.get("uv_version") != "0.11.28":
        _fail(f"embedded preparation {name} environment version is invalid")
    inventory = value.get("environment_inventory")
    if not isinstance(inventory, list):
        _fail(f"embedded preparation {name} compact inventory is invalid")
    names: list[str] = []
    for distribution in inventory:
        if not isinstance(distribution, Mapping) or set(distribution) != _DISTRIBUTION_KEYS:
            _fail("embedded preparation distribution schema is invalid")
        normalized_name = distribution.get("normalized_name")
        version = distribution.get("version")
        if (
            not isinstance(normalized_name, str)
            or not normalized_name
            or not normalized_name.isascii()
            or normalized_name != normalized_name.lower()
            or normalized_name.startswith("-")
            or normalized_name.endswith("-")
            or "--" in normalized_name
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in normalized_name)
            or not isinstance(version, str)
            or not version
            or not version.isascii()
        ):
            _fail("embedded preparation distribution identity is invalid")
        names.append(normalized_name)
        _nonnegative_int(distribution.get("file_count"), "distribution file count")
        _hex(distribution.get("files_sha256"), 64, "distribution files SHA-256")
    if names != sorted(names, key=lambda item: item.encode("utf-8")) or len(names) != len(
        set(names)
    ):
        _fail("embedded preparation distribution order is invalid")
    if value.get("environment_inventory_sha256") != canonical_sha256(inventory):
        _fail("embedded preparation environment inventory digest is invalid")
    _hex(value.get("venv_materialization_sha256"), 64, "venv materialization SHA-256")
    _hex(value.get("venv_python_sha256"), 64, "venv Python SHA-256")
    return value


def _validate_embedded_preparation_receipt(
    value: Mapping[str, Any],
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> str:
    status = value.get("status")
    if (
        set(value) != _PREPARATION_KEYS
        or value.get("schema_version") != "action-qbc-v8-preparation-receipt-v2"
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or value.get("registration_content_sha256") != registration_sha
        or status not in {"prepared", "failed"}
    ):
        _fail("embedded preparation receipt fixed identity/status is invalid")

    execution_root_value = execution.get("execution_root")
    if not isinstance(execution_root_value, str) or not execution_root_value.startswith("/"):
        _fail("registered preparation execution root is invalid")
    execution_root = execution_root_value.rstrip("/")
    authority = _validate_preparation_clone_semantics(
        value.get("authority"),
        name="authority",
        expected_root=execution.get("authority_root"),
        commit=commit,
        environment=False,
    )
    clones: dict[str, Mapping[str, Any]] = {"authority": authority}
    if status == "prepared":
        for name, root_name in (
            ("process_a", "process_a_root"),
            ("process_b", "process_b_root"),
        ):
            clones[name] = _validate_preparation_clone_semantics(
                value.get(name),
                name=name,
                expected_root=execution.get(root_name),
                commit=commit,
                environment=True,
            )
        for clone in clones.values():
            if (
                clone.get("tree_sha256") != authority.get("tree_sha256")
                or clone.get("raw_materialization_sha256")
                != authority.get("raw_materialization_sha256")
            ):
                _fail("embedded preparation clone materializations differ")
        if clones["process_a"].get("venv_python_sha256") != clones["process_b"].get(
            "venv_python_sha256"
        ):
            _fail("embedded preparation process Python identities differ")
    elif value.get("process_a") is not None or value.get("process_b") is not None:
        _fail("failed preparation receipt embeds promoted process clones")

    attempts_value = value.get("attempts")
    if not isinstance(attempts_value, list) or not 1 <= len(attempts_value) <= 2:
        _fail("embedded preparation attempts are invalid")
    attempts: list[Mapping[str, Any]] = []
    destination = f"{execution_root}/processes"
    for index, attempt_value in enumerate(attempts_value, start=1):
        if not isinstance(attempt_value, Mapping) or set(attempt_value) != _PREPARATION_ATTEMPT_KEYS:
            _fail("embedded preparation attempt schema is invalid")
        attempt = attempt_value
        if (
            attempt.get("attempt_index") != index
            or isinstance(attempt.get("attempt_index"), bool)
            or attempt.get("process_a_stage") not in _PREPARATION_PROCESS_STAGES
            or attempt.get("process_b_stage") not in _PREPARATION_PROCESS_STAGES
        ):
            _fail("embedded preparation attempt identity is invalid")
        cleanup = attempt.get("cleanup")
        promotion = attempt.get("promotion")
        if (
            not isinstance(cleanup, Mapping)
            or set(cleanup) != _PREPARATION_CLEANUP_KEYS
            or not isinstance(promotion, Mapping)
            or set(promotion) != _PREPARATION_PROMOTION_KEYS
            or not isinstance(cleanup.get("passes"), bool)
            or not isinstance(promotion.get("passes"), bool)
            or not isinstance(attempt.get("passes"), bool)
        ):
            _fail("embedded preparation cleanup/promotion schema is invalid")
        source = f"{execution_root}/.prepare-attempt-{index}"
        owned = cleanup.get("owned_paths")
        removed = cleanup.get("removed")
        if (
            promotion.get("source_path") != source
            or promotion.get("destination_path") != destination
            or owned not in ([], [source])
            or removed not in ([], [source])
        ):
            _fail("embedded preparation cleanup/promotion paths are invalid")
        device = promotion.get("source_device")
        inode = promotion.get("source_inode")
        if owned:
            _nonnegative_int(device, "preparation source device")
            _nonnegative_int(inode, "preparation source inode")
        elif device is not None or inode is not None:
            _fail("unowned preparation attempt has source identity")
        final = index == len(attempts_value)
        passing = status == "prepared" and final
        if passing:
            if (
                attempt.get("passes") is not True
                or attempt.get("process_a_stage") != "completed"
                or attempt.get("process_b_stage") != "completed"
                or cleanup.get("passes") is not True
                or promotion.get("passes") is not True
                or owned != [source]
                or removed != []
            ):
                _fail("embedded final preparation attempt is not successful")
        elif (
            attempt.get("passes") is not False
            or promotion.get("passes") is not False
            or cleanup.get("passes") is not True
            or removed != owned
        ):
            _fail("embedded failed preparation attempt is inconsistent")
        attempts.append(attempt)

    command_ledger = value.get("command_ledger")
    if (
        not isinstance(command_ledger, list)
        or not command_ledger
        or value.get("commands_sha256") != canonical_sha256(command_ledger)
        or value.get("command_environment_sha256")
        != canonical_sha256(execution.get("preparation_command_environment"))
    ):
        _fail("embedded preparation command evidence is invalid")
    policy = execution.get("preparation_command_policy")
    if not isinstance(policy, Mapping):
        _fail("registered preparation command policy is invalid")
    stdin_cap = _nonnegative_int(policy.get("stdin_cap_bytes"), "preparation stdin cap")
    stdout_cap = _nonnegative_int(policy.get("stdout_cap_bytes"), "preparation stdout cap")
    stderr_cap = _nonnegative_int(policy.get("stderr_cap_bytes"), "preparation stderr cap")
    default_timeout = _nonnegative_int(
        policy.get("default_timeout_seconds"), "preparation default timeout"
    )
    environment_timeout = _nonnegative_int(
        policy.get("environment_timeout_seconds"), "preparation environment timeout"
    )
    empty_sha = _sha256(b"")
    plan = _preparation_attempt_plan()
    attempt_rows: dict[int, list[Mapping[str, Any]]] = {
        index: [] for index in range(1, len(attempts) + 1)
    }
    terminal_attempts: set[int] = set()
    authority_rows: list[Mapping[str, Any]] = []
    seen_attempt = False
    last_attempt = 0
    preflight_offsets = {index: {"A": 0, "B": 0} for index in attempt_rows}
    for sequence_index, command_value in enumerate(command_ledger):
        if not isinstance(command_value, Mapping) or set(command_value) != _PREPARATION_COMMAND_KEYS:
            _fail("embedded preparation command row schema is invalid")
        command = command_value
        argv = command.get("argv")
        attempt_raw = command.get("attempt_index")
        label = command.get("label")
        phase = command.get("phase")
        cwd = command.get("cwd")
        outcome = command.get("outcome")
        if (
            command.get("sequence_index") != sequence_index
            or not isinstance(cwd, str)
            or not cwd.startswith("/")
            or "\x00" in cwd
            or not isinstance(argv, list)
            or not argv
            or not all(isinstance(argument, str) and argument and "\x00" not in argument for argument in argv)
            or command.get("argv_sha256") != canonical_sha256(argv)
            or phase not in _PREPARATION_PHASES
            or outcome not in _PREPARATION_OUTCOMES
        ):
            _fail("embedded preparation command row identity is invalid")
        if attempt_raw is None:
            if seen_attempt or label != "authority" or cwd != execution.get("authority_root"):
                _fail("embedded authority preparation command order/path is invalid")
            if _preparation_git_subcommand(argv) not in {
                "cat-file", "config", "diff", "for-each-ref", "ls-files", "ls-tree",
                "rev-list", "rev-parse", "status",
            }:
                _fail("embedded authority preparation command is invented")
            authority_rows.append(command)
        else:
            seen_attempt = True
            if (
                not isinstance(attempt_raw, int)
                or isinstance(attempt_raw, bool)
                or attempt_raw < 1
                or attempt_raw > len(attempts)
                or attempt_raw < last_attempt
                or attempt_raw in terminal_attempts
            ):
                _fail("embedded preparation command attempt order is invalid")
            last_attempt = attempt_raw
            rows = attempt_rows[attempt_raw]
            if len(rows) >= len(plan):
                _fail("embedded preparation attempt has too many commands")
            expected_label, expected_phase, expected_subcommand, staging_cwd = plan[len(rows)]
            source = f"{execution_root}/.prepare-attempt-{attempt_raw}"
            process_root = f"{source}/process-{expected_label.lower()}"
            expected_cwd = source if staging_cwd else process_root
            if label != expected_label or phase != expected_phase or cwd != expected_cwd:
                _fail("embedded preparation command is not an allowed attempt-plan prefix")
            if expected_subcommand is not None and _preparation_git_subcommand(argv) != expected_subcommand:
                _fail("embedded preparation Git subcommand is invented")
            if expected_subcommand == "clone" and argv[-1] != process_root:
                _fail("embedded preparation clone destination is invalid")
            if len(argv) >= 4 and argv[2] == "-C" and argv[3] != process_root:
                _fail("embedded preparation Git root is invalid")
            if phase == "environment_build" and argv != execution.get("environment_build_argv"):
                _fail("embedded preparation environment command differs from registration")
            if phase == "preflight":
                preflights = execution.get("preflight_argvs")
                offset = preflight_offsets[attempt_raw][expected_label]
                if not isinstance(preflights, list) or offset >= len(preflights) or argv != preflights[offset]:
                    _fail("embedded preparation preflight command differs from registration")
                preflight_offsets[attempt_raw][expected_label] += 1
            rows.append(command)

        stdin_size = _nonnegative_int(command.get("stdin_size_bytes"), "command stdin size")
        stdout_size = _nonnegative_int(command.get("stdout_size_bytes"), "command stdout size")
        stderr_size = _nonnegative_int(command.get("stderr_size_bytes"), "command stderr size")
        duration = _nonnegative_int(command.get("duration_milliseconds"), "command duration")
        for digest_key in ("stdin_sha256", "stdout_sha256", "stderr_sha256"):
            _hex(command.get(digest_key), 64, f"preparation command {digest_key}")
        started = command.get("started")
        exit_code = command.get("exit_code")
        timed_out = command.get("timed_out")
        cleanup = command.get("child_cleanup_passes")
        if not isinstance(started, bool) or not isinstance(timed_out, bool) or cleanup not in {
            None,
            True,
            False,
        }:
            _fail("embedded preparation command control evidence is invalid")
        if not started:
            if (
                outcome not in {"stdin_limit", "spawn_error"}
                or exit_code is not None
                or timed_out
                or cleanup is not None
                or stdout_size != 0
                or stderr_size != 0
                or command.get("stdout_sha256") != empty_sha
                or command.get("stderr_sha256") != empty_sha
                or (outcome == "stdin_limit") != (stdin_size > stdin_cap)
            ):
                _fail("embedded unstarted preparation command evidence is inconsistent")
        else:
            if (
                stdin_size > stdin_cap
                or outcome in {"stdin_limit", "spawn_error"}
                or (
                    exit_code is not None
                    and (not isinstance(exit_code, int) or isinstance(exit_code, bool))
                )
                or (outcome == "completed" and (exit_code != 0 or timed_out))
                or (
                    outcome == "nonzero"
                    and (exit_code is None or exit_code == 0 or timed_out)
                )
                or (outcome == "timeout" and not timed_out)
                or (
                    (timed_out or outcome in {"stdout_limit", "stderr_limit"})
                    and not isinstance(cleanup, bool)
                )
            ):
                _fail("embedded started preparation command evidence is inconsistent")
        if stdout_size > stdout_cap + 1 or stderr_size > stderr_cap + 1:
            _fail("embedded preparation stream evidence exceeds cap+1")
        if outcome == "stdout_limit":
            if stdout_size != stdout_cap + 1:
                _fail("embedded stdout-limit evidence is not exact cap+1")
        elif stdout_size > stdout_cap:
            _fail("embedded non-stdout-limit evidence exceeds its cap")
        if outcome == "stderr_limit":
            if stderr_size != stderr_cap + 1 or stdout_size > stdout_cap:
                _fail("embedded stderr-limit evidence violates collision precedence")
        elif outcome == "stdout_limit":
            if stderr_size > stderr_cap + 1:
                _fail("embedded stdout-limit stderr evidence exceeds cap+1")
        elif stderr_size > stderr_cap:
            _fail("embedded non-stderr-limit evidence exceeds its cap")
        if outcome == "timeout" and (stdout_size > stdout_cap or stderr_size > stderr_cap):
            _fail("embedded timeout evidence violates stream precedence")
        threshold = environment_timeout if phase == "environment_build" else default_timeout
        if timed_out and duration < threshold * 1000:
            _fail("embedded preparation timeout precedes its registered threshold")
        if attempt_raw is None and (outcome != "completed" or cleanup is False):
            _fail("embedded authority preparation command is terminal")
        if attempt_raw is not None and (outcome != "completed" or cleanup is False):
            terminal_attempts.add(attempt_raw)
        if cleanup is False:
            _fail("preparation receipt records failed child cleanup")

    for index, attempt in enumerate(attempts, start=1):
        rows = attempt_rows[index]
        if attempt.get("passes") is True and len(rows) != len(plan):
            _fail("passing preparation attempt lacks its exact command plan")
        if attempt.get("passes") is True and any(
            row.get("outcome") != "completed" or row.get("child_cleanup_passes") is False
            for row in rows
        ):
            _fail("passing preparation attempt contains a terminal command")
    identity_keys = (
        "attempt_index",
        "label",
        "phase",
        "cwd",
        "argv",
        "argv_sha256",
        "stdin_size_bytes",
        "stdin_sha256",
    )
    observed_authority = [
        {key: row[key] for key in identity_keys} for row in authority_rows
    ]
    expected_authority = _preparation_expected_authority_identities(
        registration,
        execution,
        commit=commit,
    )
    if observed_authority != expected_authority:
        _fail("embedded preparation authority command identities are not exact")
    for index in range(1, len(attempts) + 1):
        observed = [
            {key: row[key] for key in identity_keys} for row in attempt_rows[index]
        ]
        expected = _preparation_expected_attempt_identities(
            registration,
            execution,
            attempt_index=index,
            commit=commit,
        )
        if observed != expected[: len(observed)]:
            _fail("embedded preparation attempt command identities are not exact")
    return str(status)


def _validate_embedded_preparation_success(
    value: Mapping[str, Any],
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> None:
    if _validate_embedded_preparation_receipt(
        value,
        commit=commit,
        registration_sha=registration_sha,
        registration=registration,
        execution=execution,
    ) != "prepared":
        _fail("successful path embeds a non-prepared preparation receipt")


def _validate_embedded_remote_attempt(
    value: Any,
    *,
    index: int,
    expected_stdout: bytes,
) -> tuple[str, int]:
    if not isinstance(value, Mapping) or set(value) != _REMOTE_ATTEMPT_KEYS:
        _fail(f"embedded remote attempt {index} schema is invalid")
    if value.get("attempt_index") != index or isinstance(value.get("attempt_index"), bool):
        _fail("embedded remote attempt indices are invalid")
    classification = value.get("classification")
    allowed = {
        "verified", "retryable_empty_exit_0", "retryable_timeout_124",
        "retryable_git_128", "unexpected_output", "unexpected_exit",
        "stdout_limit", "stderr_limit", "child_cleanup_failed", "spawn_error",
        "overall_deadline", "post_spawn_initialization_failed",
        "stream_capture_failed",
    }
    if classification not in allowed:
        _fail("embedded remote attempt classification is invalid")
    exit_code = value.get("exit_code")
    if classification in {"spawn_error", "child_cleanup_failed"}:
        if exit_code is not None:
            _actual_exit(exit_code, "embedded remote attempt exit code")
    else:
        _actual_exit(exit_code, "embedded remote attempt exit code")
    timed_out = value.get("timed_out")
    if not isinstance(timed_out, bool):
        _fail("embedded remote attempt timeout flag is invalid")
    duration = _nonnegative_int(value.get("duration_milliseconds"), "remote attempt duration")
    stdout = _decode_machine_stream(value, "stdout", 4_096)
    stderr = _decode_machine_stream(value, "stderr", 16_384)
    cleanup = value.get("child_cleanup_passes")
    always_cleaned = {
        "post_spawn_initialization_failed", "stream_capture_failed",
        "retryable_timeout_124", "stdout_limit", "stderr_limit", "overall_deadline",
    }
    if classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("embedded remote cleanup failure must record false cleanup")
    elif classification in always_cleaned:
        if cleanup is not True:
            _fail("embedded controlled remote attempt lacks passing cleanup")
    elif classification == "spawn_error":
        if cleanup is not None:
            _fail("embedded pre-child spawn error has non-null cleanup")
    elif cleanup not in {None, True}:
        _fail("embedded normal remote cleanup is not null or true")
    valid = False
    if classification == "verified":
        valid = exit_code == 0 and stdout == expected_stdout and not timed_out
    elif classification == "retryable_empty_exit_0":
        valid = exit_code == 0 and not stdout and not timed_out
    elif classification == "retryable_timeout_124":
        valid = exit_code == 124 and timed_out and duration >= 120_000
    elif classification == "retryable_git_128":
        valid = exit_code == 128 and not stdout and not timed_out
    elif classification == "unexpected_output":
        valid = bool(stdout) and not (exit_code == 0 and stdout == expected_stdout) and not timed_out
    elif classification == "unexpected_exit":
        valid = exit_code not in {0, 128} and not stdout and not timed_out
    elif classification == "stdout_limit":
        valid = len(stdout) == 4_096 and (not timed_out or exit_code == 124)
    elif classification == "stderr_limit":
        valid = len(stderr) == 16_384 and (not timed_out or exit_code == 124)
    elif classification == "spawn_error":
        valid = exit_code is None and not stdout and not stderr and not timed_out
    elif classification == "post_spawn_initialization_failed":
        valid = not stdout and not stderr and not timed_out
    elif classification == "stream_capture_failed":
        valid = (timed_out and exit_code == 124) or (
            not timed_out and exit_code is not None
        )
    elif classification == "overall_deadline":
        valid = exit_code == 124 and timed_out and duration >= 120_000
    else:
        valid = classification == "child_cleanup_failed"
    if not valid:
        _fail("embedded remote attempt evidence is invalid")
    return str(classification), duration


def _validate_embedded_remote_receipt_common(
    receipt: Mapping[str, Any],
    *,
    commit: str,
    claim: Mapping[str, Any],
    verifier: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> str:
    expected_tools = {
        "python": {
            "path": r"C:\Users\User\anaconda3\python.exe",
            "version": "CPython 3.12.3",
            "sha256": "62c225fb9cdc41b139c7024581c233644f975ffc35314558c60ebefa6b88be01",
        },
        "git": {
            "path": r"C:\Users\User\anaconda3\Library\bin\git.exe",
            "version": "2.45.2.windows.1",
            "sha256": "5385ff9ae361ca41e7a31b335fc0d81f2de9c35fc62a165c5e34850d837b59cc",
        },
        "taskkill": {
            "path": r"C:\Windows\System32\taskkill.exe",
            "version": "file/product version 10.0.26100.8457",
            "sha256": "1249717315fc8f4d2df17d5db9da0444795fdb9fb83dfb1f763c3f39282244f7",
        },
    }
    if (
        receipt.get("claim_sha256") != canonical_sha256(claim)
        or receipt.get("verifier_start_claim_sha256") != canonical_sha256(verifier)
        or receipt.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or receipt.get("remote_url")
        != "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
        or receipt.get("ref") != f"refs/tags/{_OPEN_FREEZE_TAG}"
        or receipt.get("policy") != execution.get("remote_policy")
        or any(receipt.get(name) != expected for name, expected in expected_tools.items())
    ):
        _fail("embedded remote receipt fixed identity is invalid")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or len(attempts) > 3:
        _fail("embedded remote receipt attempt inventory is invalid")
    expected_stdout = f"{commit}\trefs/tags/{_OPEN_FREEZE_TAG}\n".encode("ascii")
    classifications: list[str] = []
    durations: list[int] = []
    for index, attempt in enumerate(attempts, start=1):
        classification, duration = _validate_embedded_remote_attempt(
            attempt, index=index, expected_stdout=expected_stdout
        )
        classifications.append(classification)
        durations.append(duration)
        if index < len(attempts) and classification not in _REMOTE_RETRYABLE:
            _fail("embedded remote attempt follows a terminal classification")
    status = receipt.get("status")
    selected = receipt.get("selected_attempt")
    if status == "verified":
        if not attempts or classifications[-1] != "verified" or selected != len(attempts):
            _fail("embedded verified remote receipt selection is invalid")
    elif status == "failed":
        if selected is not None or "verified" in classifications:
            _fail("embedded failed remote receipt selection is invalid")
    else:
        _fail("embedded remote receipt status is invalid")
    policy = execution.get("remote_policy")
    if not isinstance(policy, Mapping):
        _fail("registered remote policy is invalid")
    total = _nonnegative_int(receipt.get("total_duration_milliseconds"), "remote duration")
    retry_delay = _nonnegative_int(policy.get("retry_delay_seconds"), "retry delay") * 1_000
    if total < sum(durations) + retry_delay * max(0, len(attempts) - 1):
        _fail("embedded remote duration violates the exact P8v4 lower bound")
    return str(status)


def _validate_embedded_supervisor_common(
    supervisor: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any] | None,
    execution: Mapping[str, Any],
) -> str:
    classification = supervisor.get("classification")
    allowed = {
        "verifier_completed", "verifier_timeout_124", "stdout_limit", "stderr_limit",
        "child_cleanup_failed", "spawn_error", "remote_receipt_missing",
        "remote_receipt_invalid", "post_spawn_initialization_failed",
        "stream_capture_failed",
    }
    if classification not in allowed:
        _fail("embedded supervisor classification is invalid")
    exit_code = supervisor.get("verifier_exit_code")
    if classification in {"spawn_error", "child_cleanup_failed"}:
        if exit_code is not None:
            _actual_exit(exit_code, "embedded supervisor exit code")
    else:
        _actual_exit(exit_code, "embedded supervisor exit code")
    timed_out = supervisor.get("timed_out")
    if not isinstance(timed_out, bool):
        _fail("embedded supervisor timeout flag is invalid")
    _nonnegative_int(supervisor.get("duration_milliseconds"), "supervisor duration")
    stdout = _decode_machine_stream(supervisor, "stdout", 4_096)
    stderr = _decode_machine_stream(supervisor, "stderr", 16_384)
    cleanup = supervisor.get("child_cleanup_passes")
    always_cleaned = {
        "post_spawn_initialization_failed", "stream_capture_failed",
        "verifier_timeout_124", "stdout_limit", "stderr_limit",
    }
    if classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("embedded supervisor cleanup failure must record false cleanup")
    elif classification in always_cleaned:
        if cleanup is not True:
            _fail("embedded controlled supervisor child lacks passing cleanup")
    elif classification == "spawn_error":
        if cleanup is not None:
            _fail("embedded supervisor spawn error has non-null cleanup")
    elif cleanup not in {None, True}:
        _fail("embedded normal supervisor cleanup is not null or true")
    valid = False
    if classification == "verifier_completed":
        valid = (
            receipt is not None
            and exit_code == (0 if receipt.get("status") == "verified" else 1)
            and not timed_out and not stdout and not stderr
        )
    elif classification == "verifier_timeout_124":
        valid = exit_code == 124 and timed_out
    elif classification == "stdout_limit":
        valid = len(stdout) == 4_096 and (not timed_out or exit_code == 124)
    elif classification == "stderr_limit":
        valid = len(stderr) == 16_384 and (not timed_out or exit_code == 124)
    elif classification == "spawn_error":
        valid = exit_code is None and not timed_out and not stdout and not stderr
    elif classification == "post_spawn_initialization_failed":
        valid = not timed_out and not stdout and not stderr
    elif classification == "stream_capture_failed":
        valid = (timed_out and exit_code == 124) or (
            not timed_out and exit_code is not None
        )
    elif classification in {"remote_receipt_missing", "remote_receipt_invalid"}:
        valid = receipt is None and not timed_out
    else:
        valid = classification == "child_cleanup_failed"
    status = supervisor.get("status")
    if not valid or status not in {"completed", "failed"}:
        _fail("embedded supervisor evidence/status is invalid")
    if (classification == "verifier_completed") != (status == "completed"):
        _fail("embedded supervisor layer status propagation is invalid")
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping) or (
        supervisor.get("verifier_argv_sha256") != hashes.get("remote_verifier")
    ):
        _fail("embedded supervisor verifier argv identity is invalid")
    return str(status)


def _validate_embedded_preparation_verification(
    value: Mapping[str, Any],
    *,
    preparation: Mapping[str, Any],
    commit: str,
    registration_sha: str,
    execution: Mapping[str, Any],
) -> None:
    if (
        set(value) != _PREPARATION_VERIFICATION_KEYS
        or value.get("schema_version")
        != "action-qbc-v8-preparation-verification-receipt-v1"
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or value.get("registration_content_sha256") != registration_sha
        or value.get("status") != "verified"
        or preparation.get("status") != "prepared"
        or value.get("preparation_receipt_sha256") != canonical_sha256(preparation)
        or value.get("verification_argv_sha256")
        != canonical_sha256(execution.get("post_preparation_validation_argv"))
    ):
        _fail("embedded preparation-verification fixed evidence is invalid")
    preimage = dict(value)
    content_sha = preimage.pop("content_sha256", None)
    if content_sha != canonical_sha256(preimage):
        _fail("embedded preparation-verification content digest is invalid")
    for name in ("authority", "process_a", "process_b"):
        clone = value.get(name)
        preparation_clone = preparation.get(name)
        if (
            not isinstance(clone, Mapping)
            or set(clone) != _PREPARATION_VERIFICATION_CLONE_KEYS
            or not isinstance(preparation_clone, Mapping)
            or clone
            != {key: item for key, item in preparation_clone.items() if key != "environment_inventory"}
        ):
            _fail("embedded preparation-verification clone differs from preparation")


def _registered_addition(registration: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    source = registration.get("source_manifest")
    rows = source.get("open_freeze_added_files") if isinstance(source, Mapping) else None
    matches = (
        [row for row in rows if isinstance(row, Mapping) and row.get("path") == path]
        if isinstance(rows, list)
        else []
    )
    if len(matches) != 1:
        _fail(f"registration does not bind exactly one {path}")
    return matches[0]


def _validate_embedded_success_evidence(
    embedded: Mapping[str, Mapping[str, Any] | None],
    *,
    commit: str,
    registration: Mapping[str, Any],
) -> None:
    registration_sha = str(registration.get("content_sha256"))
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    preparation = embedded.get("preparation_receipt")
    preparation_verification = embedded.get("preparation_verification_receipt")
    claim = embedded.get("remote_verification_claim")
    verifier = embedded.get("remote_verifier_claim")
    receipt = embedded.get("remote_verification_receipt")
    supervisor = embedded.get("remote_supervisor_receipt")
    arm = embedded.get("arm_receipt")
    if any(
        item is None
        for item in (
            preparation, preparation_verification, claim, verifier, receipt, supervisor, arm
        )
    ):
        _fail("successful receipt lacks complete administrative evidence")
    assert preparation is not None
    assert preparation_verification is not None
    assert claim is not None
    assert verifier is not None
    assert receipt is not None
    assert supervisor is not None
    assert arm is not None
    _validate_embedded_preparation_success(
        preparation,
        commit=commit,
        registration_sha=registration_sha,
        registration=registration,
        execution=execution,
    )
    _validate_embedded_preparation_verification(
        preparation_verification,
        preparation=preparation,
        commit=commit,
        registration_sha=registration_sha,
        execution=execution,
    )

    supervisor_manifest = _registered_addition(
        registration, "scripts/supervise_action_qbc_v8_remote_tag.py"
    )
    verifier_manifest = _registered_addition(
        registration, "scripts/verify_action_qbc_v8_remote_tag.py"
    )
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping):
        _fail("registration argv hashes are invalid")
    if (
        claim.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or claim.get("supervisor_argv_sha256") != hashes.get("remote_supervisor")
        or claim.get("supervisor_script_git_blob_sha1") != supervisor_manifest.get("git_blob_sha1")
        or claim.get("supervisor_script_sha256") != supervisor_manifest.get("sha256")
        or claim.get("verifier_script_git_blob_sha1") != verifier_manifest.get("git_blob_sha1")
        or claim.get("verifier_script_sha256") != verifier_manifest.get("sha256")
    ):
        _fail("successful receipt remote claim is invalid")
    claim_sha = canonical_sha256(claim)
    if (
        verifier.get("claim_sha256") != claim_sha
        or verifier.get("verifier_argv_sha256") != hashes.get("remote_verifier")
    ):
        _fail("successful receipt verifier claim is invalid")
    verifier_sha = canonical_sha256(verifier)
    expected_tools = {
        "python": {
            "path": r"C:\Users\User\anaconda3\python.exe",
            "version": "CPython 3.12.3",
            "sha256": "62c225fb9cdc41b139c7024581c233644f975ffc35314558c60ebefa6b88be01",
        },
        "git": {
            "path": r"C:\Users\User\anaconda3\Library\bin\git.exe",
            "version": "2.45.2.windows.1",
            "sha256": "5385ff9ae361ca41e7a31b335fc0d81f2de9c35fc62a165c5e34850d837b59cc",
        },
        "taskkill": {
            "path": r"C:\Windows\System32\taskkill.exe",
            "version": "file/product version 10.0.26100.8457",
            "sha256": "1249717315fc8f4d2df17d5db9da0444795fdb9fb83dfb1f763c3f39282244f7",
        },
    }
    if (
        receipt.get("claim_sha256") != claim_sha
        or receipt.get("verifier_start_claim_sha256") != verifier_sha
        or receipt.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or receipt.get("remote_url") != "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
        or receipt.get("ref") != f"refs/tags/{_OPEN_FREEZE_TAG}"
        or receipt.get("policy") != execution.get("remote_policy")
        or any(receipt.get(name) != expected for name, expected in expected_tools.items())
        or receipt.get("status") != "verified"
    ):
        _fail("successful receipt remote verification evidence is invalid")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 3:
        _fail("successful receipt remote attempts are invalid")
    expected_stdout = f"{commit}\trefs/tags/{_OPEN_FREEZE_TAG}\n".encode("ascii")
    classifications: list[str] = []
    durations: list[int] = []
    for index, attempt in enumerate(attempts, start=1):
        classification, duration = _validate_embedded_remote_attempt(
            attempt, index=index, expected_stdout=expected_stdout
        )
        classifications.append(classification)
        durations.append(duration)
        if index < len(attempts) and classification not in _REMOTE_RETRYABLE:
            _fail("successful receipt has an attempt after a terminal result")
    if classifications[-1] != "verified" or receipt.get("selected_attempt") != len(attempts):
        _fail("successful receipt has no selected verified attempt")
    policy = execution.get("remote_policy")
    if not isinstance(policy, Mapping):
        _fail("registered remote policy is invalid")
    total = _nonnegative_int(receipt.get("total_duration_milliseconds"), "remote duration")
    retry_delay = _nonnegative_int(policy.get("retry_delay_seconds"), "retry delay") * 1_000
    _nonnegative_int(policy.get("overall_deadline_seconds"), "remote deadline")
    _nonnegative_int(policy.get("child_cleanup_timeout_seconds"), "remote cleanup allowance")
    if total < sum(durations) + retry_delay * (len(attempts) - 1):
        _fail("successful receipt remote duration is invalid")

    receipt_sha = canonical_sha256(receipt)
    stdout = _decode_machine_stream(supervisor, "stdout", 4_096)
    stderr = _decode_machine_stream(supervisor, "stderr", 16_384)
    supervisor_deadline = _nonnegative_int(
        policy.get("supervisor_deadline_seconds"), "supervisor deadline"
    )
    reserve = _nonnegative_int(
        policy.get("supervisor_receipt_reserve_seconds"), "supervisor reserve"
    )
    _nonnegative_int(supervisor.get("duration_milliseconds"), "supervisor duration")
    if (
        reserve > supervisor_deadline
        or supervisor.get("claim_sha256") != claim_sha
        or supervisor.get("verifier_start_claim_sha256") != verifier_sha
        or supervisor.get("remote_receipt_sha256") != receipt_sha
        or supervisor.get("verifier_argv_sha256") != hashes.get("remote_verifier")
        or supervisor.get("classification") != "verifier_completed"
        or supervisor.get("verifier_exit_code") != 0
        or supervisor.get("timed_out") is not False
        or stdout
        or stderr
        or supervisor.get("child_cleanup_passes") not in {None, True}
        or supervisor.get("status") != "completed"
    ):
        _fail("successful receipt supervisor evidence is invalid")
    if (
        arm.get("status") != "armed"
        or arm.get("preparation_receipt_exists") is not True
        or arm.get("preparation_receipt_read_status") != "readable"
        or arm.get("preparation_receipt_sha256") != canonical_sha256(preparation)
        or arm.get("preparation_verification_receipt_exists") is not True
        or arm.get("preparation_verification_receipt_read_status") != "readable"
        or arm.get("preparation_verification_receipt_sha256")
        != canonical_sha256(preparation_verification)
        or arm.get("remote_claim_sha256") != claim_sha
        or arm.get("remote_verifier_claim_sha256") != verifier_sha
        or arm.get("remote_receipt_sha256") != receipt_sha
        or arm.get("remote_supervisor_receipt_sha256") != canonical_sha256(supervisor)
    ):
        _fail("successful receipt arm evidence is invalid")


def _validate_machine_result(
    value: Mapping[str, Any],
    *,
    schema: str,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
) -> None:
    expected_keys = _RECEIPT_KEYS if schema == _RECEIPT_SCHEMA else _ADMIN_KEYS
    if (
        set(value) != expected_keys
        or value.get("schema_version") != schema
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or value.get("registration_content_sha256") != registration_sha
        or value.get("authorization") != _AUTHORIZATION
    ):
        _fail("machine result fixed identity/schema is invalid")

    embedded_specs = (
        (
            "preparation_receipt",
            _PREPARATION_KEYS,
            "action-qbc-v8-preparation-receipt-v2",
        ),
        (
            "preparation_verification_receipt",
            _PREPARATION_VERIFICATION_KEYS,
            "action-qbc-v8-preparation-verification-receipt-v1",
        ),
        (
            "remote_verification_claim",
            _REMOTE_CLAIM_KEYS,
            "action-qbc-v8-remote-tag-verification-claim-v1",
        ),
        (
            "remote_verifier_claim",
            _REMOTE_VERIFIER_KEYS,
            "action-qbc-v8-remote-tag-verifier-start-claim-v1",
        ),
        (
            "remote_verification_receipt",
            _REMOTE_RECEIPT_KEYS,
            "action-qbc-v8-remote-tag-verification-receipt-v1",
        ),
        (
            "remote_supervisor_receipt",
            _REMOTE_SUPERVISOR_KEYS,
            "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1",
        ),
        ("arm_receipt", _ARM_KEYS, _ARM_SCHEMA),
        ("lifecycle_driver_claim", _DRIVER_KEYS, _DRIVER_SCHEMA),
        ("lifecycle_ledger", _LEDGER_KEYS, _LEDGER_SCHEMA),
    )
    embedded: dict[str, Mapping[str, Any] | None] = {}
    for name, keys, identity in embedded_specs:
        embedded[name] = _embedded_machine_object(
            value.get(name),
            keys=keys,
            schema=identity,
            commit=commit,
            registration_sha=registration_sha,
            label=name,
        )

    preparation = embedded["preparation_receipt"]
    preparation_verification = embedded["preparation_verification_receipt"]
    remote_claim = embedded["remote_verification_claim"]
    remote_verifier = embedded["remote_verifier_claim"]
    remote_receipt = embedded["remote_verification_receipt"]
    remote_supervisor = embedded["remote_supervisor_receipt"]
    arm = embedded["arm_receipt"]
    driver = embedded["lifecycle_driver_claim"]
    for prefix, object_name in (
        ("preparation_receipt", "preparation_receipt"),
        ("preparation_verification_receipt", "preparation_verification_receipt"),
    ):
        exists = value.get(f"{prefix}_exists")
        read_status = value.get(f"{prefix}_read_status")
        digest = value.get(f"{prefix}_sha256")
        embedded_object = embedded[object_name]
        if not isinstance(exists, bool) or read_status not in {
            "absent", "readable", "unsafe_type", "oversized", "read_error",
            "changed_during_read",
        }:
            _fail("machine result preparation read-state is invalid")
        if (
            (read_status == "absent" and (exists or digest is not None))
            or (read_status == "readable" and (not exists or digest is None))
            or (read_status not in {"absent", "readable"} and (not exists or digest is not None))
        ):
            _fail("machine result preparation read-state nullability is invalid")
        if digest is not None:
            _hex(digest, 64, f"{prefix} SHA-256")
        if embedded_object is not None and (
            read_status != "readable" or digest != canonical_sha256(embedded_object)
        ):
            _fail("machine result embedded preparation object differs from raw evidence")
    if preparation is not None and (
        preparation.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or preparation.get("status") not in {"prepared", "failed"}
    ):
        _fail("embedded preparation receipt status is invalid")
    if preparation_verification is not None and (
        preparation is None
        or preparation_verification.get("status") != "verified"
        or preparation_verification.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or preparation_verification.get("preparation_receipt_sha256")
        != canonical_sha256(preparation)
    ):
        _fail("embedded preparation-verification dependency/status is invalid")
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    preparation_ready = False
    if preparation is not None:
        preparation_ready = (
            _validate_embedded_preparation_receipt(
                preparation,
                commit=commit,
                registration_sha=registration_sha,
                registration=registration,
                execution=execution,
            )
            == "prepared"
        )
    preparation_verification_ready = False
    if preparation_verification is not None:
        if preparation is None:
            _fail("embedded preparation verification lacks its preparation receipt")
        _validate_embedded_preparation_verification(
            preparation_verification,
            preparation=preparation,
            commit=commit,
            registration_sha=registration_sha,
            execution=execution,
        )
        preparation_verification_ready = preparation_ready
    if remote_claim is not None and remote_claim.get("open_freeze_tag") != _OPEN_FREEZE_TAG:
        _fail("embedded remote claim tag is invalid")
    if remote_verifier is not None and (
        remote_claim is None
        or remote_verifier.get("claim_sha256") != canonical_sha256(remote_claim)
    ):
        _fail("embedded remote verifier dependency is invalid")
    if remote_receipt is not None and (
        remote_claim is None
        or remote_verifier is None
        or remote_receipt.get("claim_sha256") != canonical_sha256(remote_claim)
        or remote_receipt.get("verifier_start_claim_sha256")
        != canonical_sha256(remote_verifier)
        or remote_receipt.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or remote_receipt.get("status") not in {"verified", "failed"}
    ):
        _fail("embedded remote receipt dependency/status is invalid")
    if remote_supervisor is not None and (
        remote_claim is None
        or remote_supervisor.get("claim_sha256") != canonical_sha256(remote_claim)
        or remote_supervisor.get("status") not in {"completed", "failed"}
        or (
            remote_verifier is not None
            and remote_supervisor.get("verifier_start_claim_sha256")
            != canonical_sha256(remote_verifier)
        )
        or (
            remote_receipt is not None
            and remote_supervisor.get("remote_receipt_sha256")
            != canonical_sha256(remote_receipt)
        )
    ):
        _fail("embedded remote supervisor dependency/status is invalid")
    if remote_receipt is not None:
        if remote_claim is None or remote_verifier is None:
            _fail("embedded remote receipt lacks its claim chain")
        _validate_embedded_remote_receipt_common(
            remote_receipt,
            commit=commit,
            claim=remote_claim,
            verifier=remote_verifier,
            execution=execution,
        )
    if remote_supervisor is not None:
        _validate_embedded_supervisor_common(
            remote_supervisor,
            receipt=remote_receipt,
            execution=execution,
        )
    if arm is not None:
        if arm.get("status") not in {"armed", "failed"}:
            _fail("embedded arm status is invalid")
        arm_dependencies = (
            ("remote_claim_sha256", remote_claim),
            ("remote_verifier_claim_sha256", remote_verifier),
            ("remote_receipt_sha256", remote_receipt),
            ("remote_supervisor_receipt_sha256", remote_supervisor),
        )
        if (
            arm.get("preparation_receipt_exists")
            != value.get("preparation_receipt_exists")
            or arm.get("preparation_receipt_read_status")
            != value.get("preparation_receipt_read_status")
            or arm.get("preparation_receipt_sha256")
            != value.get("preparation_receipt_sha256")
            or arm.get("preparation_verification_receipt_exists")
            != value.get("preparation_verification_receipt_exists")
            or arm.get("preparation_verification_receipt_read_status")
            != value.get("preparation_verification_receipt_read_status")
            or arm.get("preparation_verification_receipt_sha256")
            != value.get("preparation_verification_receipt_sha256")
        ):
            _fail("embedded arm preparation read-state differs from machine evidence")
        for member, dependency in arm_dependencies:
            if dependency is not None and arm.get(member) != canonical_sha256(dependency):
                _fail("embedded arm dependency hash is invalid")
        if arm.get("status") == "armed" and (
            any(dependency is None for _member, dependency in arm_dependencies)
            or preparation is None
            or preparation_verification is None
        ):
            _fail("armed receipt lacks a complete embedded dependency set")
    if driver is not None and (
        remote_claim is None
        or driver.get("remote_claim_sha256") != canonical_sha256(remote_claim)
    ):
        _fail("embedded lifecycle-driver dependency is invalid")

    process_a = _validate_result_process(
        value.get("process_a"),
        label="A",
        commit=commit,
        registration_sha=registration_sha,
    )
    process_b = _validate_result_process(
        value.get("process_b"),
        label="B",
        commit=commit,
        registration_sha=registration_sha,
    )
    for label, process, prior in (
        ("A", process_a, None),
        ("B", process_b, process_a.get("validation_receipt")),
    ):
        start = process.get("start_claim")
        validator_claim = process.get("validator_claim")
        validation = process.get("validation_receipt")
        if start is not None and (
            arm is None
            or driver is None
            or start.get("arm_receipt_sha256") != canonical_sha256(arm)
            or start.get("lifecycle_driver_claim_sha256") != canonical_sha256(driver)
            or start.get("prior_validation_receipt_sha256")
            != (canonical_sha256(prior) if prior is not None else None)
        ):
            _fail(f"result process {label} start dependencies are invalid")
        if validator_claim is not None and (
            driver is None
            or start is None
            or validator_claim.get("lifecycle_driver_claim_sha256")
            != canonical_sha256(driver)
            or validator_claim.get("start_claim_sha256")
            != process.get("start_claim_sha256")
            or validator_claim.get("payload_sha256") != process.get("payload_sha256")
        ):
            _fail(f"result process {label} validator dependencies are invalid")
        if validation is not None and (
            start is None
            or validator_claim is None
            or validation.get("start_claim_sha256") != process.get("start_claim_sha256")
            or validation.get("validator_claim_sha256")
            != process.get("validator_claim_sha256")
        ):
            _fail(f"result process {label} validation dependencies are invalid")
    pair = value.get("payloads_byte_identical")
    both_valid = process_a.get("payload_valid") is True and process_b.get(
        "payload_valid"
    ) is True
    expected_pair = (
        process_a.get("payload_sha256") == process_b.get("payload_sha256")
        if both_valid
        else None
    )
    if pair is not expected_pair:
        _fail("machine result payload-pair evidence is inconsistent")

    ledger = embedded["lifecycle_ledger"]
    if ledger is not None:
        _optional_sha(ledger.get("driver_claim_sha256"), "embedded ledger driver SHA-256")
        _optional_sha(ledger.get("arm_receipt_sha256"), "embedded ledger arm SHA-256")
        sequence = ledger.get("sequence")
        if (
            not isinstance(sequence, list)
            or sequence != list(_SEQUENCE[: len(sequence)])
            or ledger.get("stage") not in {*_UNDERLYING_ORDER, None}
            or ledger.get("driver_claim_sha256")
            != (
                canonical_sha256(embedded["lifecycle_driver_claim"])
                if embedded["lifecycle_driver_claim"] is not None
                else ledger.get("driver_claim_sha256")
            )
            or ledger.get("arm_receipt_sha256")
            != (
                canonical_sha256(embedded["arm_receipt"])
                if embedded["arm_receipt"] is not None
                else ledger.get("arm_receipt_sha256")
            )
        ):
            _fail("machine result embedded ledger dependency is invalid")
        for ledger_name, process in (("process_a", process_a), ("process_b", process_b)):
            ledger_process = ledger.get(ledger_name)
            if not isinstance(ledger_process, Mapping) or set(
                ledger_process
            ) != _LEDGER_PROCESS_KEYS:
                _fail("machine result embedded ledger process is invalid")
            for ledger_key, result_key in (
                ("runner_exit_code", "exit_code"),
                ("validator_exit_code", "validator_exit_code"),
                ("start_claim_sha256", "start_claim_sha256"),
                ("validator_claim_sha256", "validator_claim_sha256"),
                ("validation_receipt_sha256", "validation_receipt_sha256"),
                ("output_sha256", "payload_sha256"),
            ):
                if ledger_process.get(ledger_key) != process.get(result_key):
                    _fail("machine result process/ledger evidence differs")

    if schema == _RECEIPT_SCHEMA:
        _validate_embedded_success_evidence(
            embedded,
            commit=commit,
            registration=registration,
        )
        if (
            any(embedded[name] is None for name in embedded)
            or ledger is None
            or ledger.get("sequence") != list(_SEQUENCE)
            or ledger.get("stage") is not None
            or process_a.get("payload_valid") is not True
            or process_b.get("payload_valid") is not True
            or pair is not True
            or value.get("published_payload_path")
            != "artifacts/action_qbc_v8_open_diagnostic.json"
            or value.get("published_payload_sha256") != process_a.get("payload_sha256")
        ):
            _fail("successful receipt does not contain complete successful evidence")
    else:
        stage = value.get("stage")
        if stage not in _UNDERLYING_ORDER:
            _fail("administrative terminal stage is invalid")
        if (
            driver is not None
            and not preparation_ready
            and stage != "preparation_receipt_invalid"
        ):
            _fail("administrative terminal does not expose preparation failure precedence")
        if (
            driver is not None
            and preparation_ready
            and not preparation_verification_ready
            and stage
            not in {
                "preparation_receipt_invalid",
                "preparation_verification_invalid",
            }
        ):
            _fail("administrative terminal does not expose preparation-verification precedence")
        if ledger is not None and ledger.get("stage") != stage:
            _fail("administrative terminal and ledger stages differ")


def _validate_bundled_machine_result(
    value: Mapping[str, Any],
    files: Sequence[tuple[str, bytes]],
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
) -> None:
    by_path = dict(files)
    disposition = value.get("disposition")
    stage = value.get("stage")
    if disposition == "scientific_result":
        payload = by_path["artifacts/action_qbc_v8_open_diagnostic.json"]
        payload_a = _evidence_state(_A_OUTPUT, "reopened process-A payload").raw
        payload_b = _evidence_state(_B_OUTPUT, "reopened process-B payload").raw
        if (
            payload_a is None
            or payload_b is None
            or len(payload_a) != len(payload_b)
            or _sha256(payload_a) != _sha256(payload_b)
            or payload_a != payload_b
            or payload != payload_a
        ):
            _fail("bundled scientific result lacks complete payload-byte parity")
        receipt = _parse_canonical(
            by_path["artifacts/action_qbc_v8_open_diagnostic_receipt.json"],
            "bundled successful receipt",
        )
        _validate_machine_result(
            receipt,
            schema=_RECEIPT_SCHEMA,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
        if (
            receipt.get("published_payload_path")
            != "artifacts/action_qbc_v8_open_diagnostic.json"
            or receipt.get("published_payload_sha256") != _sha256(payload)
        ):
            _fail("bundled successful receipt payload identity is invalid")
    elif disposition == "administrative_terminal" and stage in _UNDERLYING_ORDER:
        terminal = _parse_canonical(
            by_path["artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json"],
            "bundled administrative terminal",
        )
        _validate_machine_result(
            terminal,
            schema=_ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
        if terminal.get("stage") != stage:
            _fail("bundled administrative terminal stage differs from its bundle")


def _validate_bundle_bytes(
    raw: bytes,
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
    emergency: bool,
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    label = "emergency result bundle" if emergency else "normal finalization bundle"
    value = _parse_canonical(raw, label)
    expected_keys = _EMERGENCY_BUNDLE_KEYS if emergency else _NORMAL_BUNDLE_KEYS
    expected_schema = _EMERGENCY_SCHEMA if emergency else _BUNDLE_SCHEMA
    if set(value) != expected_keys or value.get("schema_version") != expected_schema:
        _fail(f"{label} key/schema identity is invalid")
    preimage = dict(value)
    claimed = preimage.pop("content_sha256", None)
    if (
        value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
        or value.get("authorization") != _AUTHORIZATION
        or claimed != canonical_sha256(preimage)
    ):
        _fail(f"{label} fixed/content identity is invalid")
    files_value = value.get("files")
    if not isinstance(files_value, list) or not files_value:
        _fail(f"{label} file list is empty or invalid")
    files = [_decode_file_object(item) for item in files_value]
    paths = [path for path, _raw in files]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        _fail(f"{label} files are not unique and path-sorted")
    disposition = value.get("disposition")
    stage = value.get("stage")
    underlying = value.get("underlying_stage")
    if emergency:
        classification = value.get("finalizer_classification")
        finalizer_exit = value.get("finalizer_exit_code")
        timed_out = value.get("finalizer_timed_out")
        cleanup = value.get("finalizer_child_cleanup_passes")
        actual_exit = finalizer_exit is None or (
            isinstance(finalizer_exit, int) and not isinstance(finalizer_exit, bool)
        )
        classification_valid = False
        if classification in {"deadline_admission_failed", "spawn_error"}:
            classification_valid = (
                finalizer_exit is None and timed_out is None and cleanup is None
            )
        elif classification == "timeout":
            classification_valid = (
                actual_exit and timed_out is True and cleanup in {None, True}
            )
        elif classification == "nonzero":
            classification_valid = (
                actual_exit and finalizer_exit not in {None, 0, 124}
                and timed_out is False and cleanup in {None, True}
            )
        elif classification == "bundle_invalid":
            classification_valid = (
                finalizer_exit == 0 and timed_out is False and cleanup in {None, True}
            )
        elif classification == "spawned_no_return":
            classification_valid = (
                finalizer_exit is None and timed_out is False and cleanup is True
            )
        elif classification == "child_cleanup_failed":
            classification_valid = actual_exit and isinstance(timed_out, bool) and cleanup is False

        finalization_state = _evidence_state(_FINAL_BUNDLE, "finalization-bundle evidence")
        ledger_state = _evidence_state(_LEDGER, "lifecycle-ledger evidence")
        preparation_state = _evidence_state(_PREPARATION, "preparation-receipt evidence")
        verification_state = _evidence_state(
            _PREPARATION_VERIFICATION, "preparation-verification evidence"
        )
        if (
            disposition != "administrative_terminal"
            or stage != "finalizer_process_failed"
            or underlying not in {*_UNDERLYING_ORDER, None}
            or paths != ["docs/action_qbc_v8_open_diagnostic_result.md"]
            or not classification_valid
            or value.get("finalization_bundle_exists") != finalization_state.exists
            or value.get("finalization_bundle_sha256") != finalization_state.sha256
            or value.get("lifecycle_ledger_exists") != ledger_state.exists
            or value.get("lifecycle_ledger_sha256") != ledger_state.sha256
            or value.get("preparation_receipt_exists") != preparation_state.exists
            or value.get("preparation_receipt_read_status") != preparation_state.read_status
            or value.get("preparation_receipt_sha256") != preparation_state.sha256
            or value.get("preparation_verification_receipt_exists")
            != verification_state.exists
            or value.get("preparation_verification_receipt_read_status")
            != verification_state.read_status
            or value.get("preparation_verification_receipt_sha256")
            != verification_state.sha256
        ):
            _fail("emergency bundle disposition/path set is invalid")
    elif disposition == "scientific_result":
        if stage is not None or underlying is not None or paths != [
            "artifacts/action_qbc_v8_open_diagnostic.json",
            "artifacts/action_qbc_v8_open_diagnostic_receipt.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ]:
            _fail("scientific result bundle disposition/path set is invalid")
    elif disposition == "administrative_terminal":
        if stage == "receipt_finalization_failed":
            if underlying not in {*_UNDERLYING_ORDER, None} or paths != [
                "docs/action_qbc_v8_open_diagnostic_result.md"
            ]:
                _fail("receipt-finalization bundle path/stage is invalid")
        elif stage in _UNDERLYING_ORDER:
            if underlying != stage or paths != [
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                "docs/action_qbc_v8_open_diagnostic_result.md",
            ]:
                _fail("administrative bundle path/stage is invalid")
        else:
            _fail("normal bundle has an unknown administrative stage")
    else:
        _fail("normal bundle disposition is invalid")
    if not emergency:
        _validate_bundled_machine_result(
            value,
            files,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
    return value, files


def _selected_bundle(
    *,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
) -> tuple[Path, bytes, dict[str, Any], list[tuple[str, bytes]], bool]:
    emergency_state = _evidence_state(_EMERGENCY_BUNDLE, "emergency result bundle")
    if emergency_state.exists and emergency_state.read_status != "readable":
        _fail("emergency result bundle exists but is not safely readable")
    normal_state = _evidence_state(_FINAL_BUNDLE, "normal finalization bundle")
    emergency_raw = emergency_state.raw
    if emergency_raw is not None:
        value, files = _validate_bundle_bytes(
            emergency_raw,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
            emergency=True,
        )
        if normal_state.exists:
            if normal_state.read_status != "readable" or normal_state.raw is None:
                _fail("normal/emergency coexistence has an unreadable normal bundle")
            normal_value, normal_files = _validate_bundle_bytes(
                normal_state.raw,
                commit=commit,
                registration_sha=registration_sha,
                registration=registration,
                emergency=False,
            )
            _validate_selected_document(
                registration,
                commit=commit,
                bundle=normal_value,
                files=normal_files,
                emergency=False,
            )
            if (
                value.get("finalizer_classification") != "child_cleanup_failed"
                or value.get("finalizer_exit_code") != 0
                or value.get("finalizer_timed_out") is not False
                or value.get("finalizer_child_cleanup_passes") is not False
                or value.get("finalization_bundle_exists") is not True
                or value.get("finalization_bundle_sha256") != _sha256(normal_state.raw)
            ):
                _fail("normal/emergency coexistence is not the sole P8v4 cleanup override")
        return _EMERGENCY_BUNDLE, emergency_raw, value, files, True
    if normal_state.read_status != "readable" or normal_state.raw is None:
        _fail("normal finalization bundle is not safely readable")
    normal_raw = normal_state.raw
    value, files = _validate_bundle_bytes(
        normal_raw,
        commit=commit,
        registration_sha=registration_sha,
        registration=registration,
        emergency=False,
    )
    return _FINAL_BUNDLE, normal_raw, value, files, False


def _format_template_value(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _emergency_document(
    registration: Mapping[str, Any],
    *,
    commit: str,
    underlying_stage: str | None,
    finalizer: _ChildResult,
    finalization: _EvidenceState,
    ledger: _EvidenceState,
    preparation: _EvidenceState,
    preparation_verification: _EvidenceState,
) -> bytes:
    execution = _execution(registration)
    contract = execution.get("result_document_contract")
    if not isinstance(contract, Mapping) or set(contract) != {
        "schema_version", "renderer_source", "normal_template", "emergency_template",
        "normal_input_names", "emergency_input_names", "normal_cases",
    } or contract.get("schema_version") != _RESULT_DOCUMENT_SCHEMA:
        _fail("registered result-document contract is invalid")
    template = contract.get("emergency_template")
    if not isinstance(template, Mapping) or set(template) != {"text", "sha256"}:
        _fail("registered emergency template object is invalid")
    text = template.get("text")
    if not isinstance(text, str) or template.get("sha256") != _sha256(text.encode("ascii")):
        _fail("registered emergency template text/hash is invalid")
    inputs = {
        "disposition": "administrative_terminal",
        "finalization_bundle_exists": finalization.exists,
        "finalization_bundle_sha256": finalization.sha256,
        "finalizer_classification": finalizer.classification,
        "finalizer_exit_code": finalizer.exit_code,
        "finalizer_timed_out": finalizer.timed_out,
        "finalizer_child_cleanup_passes": finalizer.child_cleanup_passes,
        "lifecycle_ledger_exists": ledger.exists,
        "lifecycle_ledger_sha256": ledger.sha256,
        "open_freeze_commit_sha": commit,
        "preparation_receipt_exists": preparation.exists,
        "preparation_receipt_read_status": preparation.read_status,
        "preparation_receipt_sha256": preparation.sha256,
        "preparation_verification_receipt_exists": preparation_verification.exists,
        "preparation_verification_receipt_read_status": preparation_verification.read_status,
        "preparation_verification_receipt_sha256": preparation_verification.sha256,
        "registration_content_sha256": registration["content_sha256"],
        "stage": "finalizer_process_failed",
        "underlying_stage": underlying_stage,
    }
    if contract.get("emergency_input_names") != sorted(inputs):
        _fail("registered emergency template input names are invalid")
    rendered = text
    for key, value in inputs.items():
        placeholder = "{" + key + "}"
        if rendered.count(placeholder) != 1:
            _fail(f"emergency template placeholder count is invalid: {key}")
        rendered = rendered.replace(placeholder, _format_template_value(value))
    if "{" in rendered or "}" in rendered:
        _fail("emergency result document retains a placeholder")
    return rendered.encode("ascii")


def _file_object(path: str, raw: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "mode": "100644",
        "size_bytes": len(raw),
        "sha256": _sha256(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }


def _publish_emergency_bundle(
    registration: Mapping[str, Any],
    *,
    commit: str,
    underlying_stage: str | None,
    finalizer: _ChildResult,
) -> tuple[dict[str, Any], bytes]:
    finalization = _evidence_state(_FINAL_BUNDLE, "raw finalization-bundle evidence")
    ledger = _evidence_state(_LEDGER, "raw lifecycle-ledger evidence")
    preparation = _evidence_state(_PREPARATION, "raw preparation-receipt evidence")
    preparation_verification = _evidence_state(
        _PREPARATION_VERIFICATION, "raw preparation-verification evidence"
    )
    document = _emergency_document(
        registration,
        commit=commit,
        underlying_stage=underlying_stage,
        finalizer=finalizer,
        finalization=finalization,
        ledger=ledger,
        preparation=preparation,
        preparation_verification=preparation_verification,
    )
    without = {
        "schema_version": _EMERGENCY_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "disposition": "administrative_terminal",
        "stage": "finalizer_process_failed",
        "underlying_stage": underlying_stage,
        "finalizer_classification": finalizer.classification,
        "finalizer_exit_code": finalizer.exit_code,
        "finalizer_timed_out": finalizer.timed_out,
        "finalizer_child_cleanup_passes": finalizer.child_cleanup_passes,
        "finalization_bundle_exists": finalization.exists,
        "finalization_bundle_sha256": finalization.sha256,
        "lifecycle_ledger_exists": ledger.exists,
        "lifecycle_ledger_sha256": ledger.sha256,
        "preparation_receipt_exists": preparation.exists,
        "preparation_receipt_read_status": preparation.read_status,
        "preparation_receipt_sha256": preparation.sha256,
        "preparation_verification_receipt_exists": preparation_verification.exists,
        "preparation_verification_receipt_read_status": preparation_verification.read_status,
        "preparation_verification_receipt_sha256": preparation_verification.sha256,
        "files": [_file_object("docs/action_qbc_v8_open_diagnostic_result.md", document)],
        "authorization": dict(_AUTHORIZATION),
    }
    bundle = dict(without)
    bundle["content_sha256"] = canonical_sha256(without)
    if set(bundle) != _EMERGENCY_BUNDLE_KEYS:
        _fail("internal emergency bundle schema is invalid")
    raw = _exclusive_json(_EMERGENCY_BUNDLE, bundle)
    _validate_bundle_bytes(
        raw,
        commit=commit,
        registration_sha=cast(str, registration["content_sha256"]),
        registration=registration,
        emergency=True,
    )
    return bundle, raw


def _validate_ledger_for_publish(
    raw: bytes | None,
    *,
    commit: str,
    registration_sha: str,
    driver_raw: bytes,
) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        value = _parse_canonical(raw, "lifecycle ledger")
    except LifecycleError:
        return None
    if (
        set(value) != _LEDGER_KEYS
        or value.get("schema_version") != _LEDGER_SCHEMA
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
        or value.get("driver_claim_sha256") != _sha256(driver_raw)
        or not isinstance(value.get("sequence"), list)
        or value.get("sequence") != list(_SEQUENCE[: len(value.get("sequence", []))])
        or value.get("stage") not in {*_UNDERLYING_ORDER, None}
    ):
        return None
    sequence = cast(list[Any], value["sequence"])
    arm_returned = len(sequence) >= 1
    arm_exit = value.get("arm_exit_code")
    if arm_returned != (
        isinstance(arm_exit, int) and not isinstance(arm_exit, bool)
    ):
        return None
    process_specs = (
        ("process_a", "A", str(_A_ROOT), 2, 3),
        ("process_b", "B", str(_B_ROOT), 4, 5),
    )
    for name, label, cwd, runner_returned_at, validator_returned_at in process_specs:
        process = value.get(name)
        if (
            not isinstance(process, Mapping)
            or set(process) != _LEDGER_PROCESS_KEYS
            or process.get("label") != label
            or process.get("cwd") != cwd
        ):
            return None
        for key in (
            "runner_argv_sha256", "validator_argv_sha256", "start_claim_sha256",
            "validator_claim_sha256", "validation_receipt_sha256", "output_sha256",
        ):
            member = process.get(key)
            if member is not None and (
                not isinstance(member, str)
                or len(member) != 64
                or any(character not in "0123456789abcdef" for character in member)
            ):
                return None
        runner_returned = len(sequence) >= runner_returned_at
        validator_returned = len(sequence) >= validator_returned_at
        runner_exit = process.get("runner_exit_code")
        validator_exit = process.get("validator_exit_code")
        if runner_returned != (
            isinstance(runner_exit, int) and not isinstance(runner_exit, bool)
        ) or validator_returned != (
            isinstance(validator_exit, int) and not isinstance(validator_exit, bool)
        ):
            return None
        if runner_returned and process.get("runner_argv_sha256") is None:
            return None
        if validator_returned and process.get("validator_argv_sha256") is None:
            return None
        if validator_returned and not runner_returned:
            return None
    if value.get("stage") is None:
        exits = [
            arm_exit,
            cast(Mapping[str, Any], value["process_a"]).get("runner_exit_code"),
            cast(Mapping[str, Any], value["process_a"]).get("validator_exit_code"),
            cast(Mapping[str, Any], value["process_b"]).get("runner_exit_code"),
            cast(Mapping[str, Any], value["process_b"]).get("validator_exit_code"),
        ]
        if sequence != list(_SEQUENCE) or exits != [0, 0, 0, 0, 0]:
            return None
    return value


def _require_ledger_or_bypass(
    *,
    ledger_raw: bytes | None,
    ledger_value: Mapping[str, Any] | None,
    bundle: Mapping[str, Any],
    emergency: bool,
) -> None:
    if ledger_value is not None:
        return
    if not emergency:
        if bundle.get("underlying_stage") == "lifecycle_ledger_invalid":
            return
        _fail("normal bundle cannot bypass an absent/invalid lifecycle ledger")
    state = _evidence_state(_LEDGER, "raw lifecycle-ledger evidence")
    if (
        bundle.get("lifecycle_ledger_exists") != state.exists
        or bundle.get("lifecycle_ledger_sha256") != state.sha256
    ):
        _fail("emergency bundle does not exactly describe the raw lifecycle-ledger path")


def _publisher_environment(
    execution: Mapping[str, Any], authority: Path, index_path: Path
) -> dict[str, str]:
    registered = execution.get("result_git_environment")
    expected_template = _base_git_environment(authority, _WORK_ROOT / "index-<i>")
    if registered != expected_template:
        _fail("registered result Git environment is invalid")
    result = dict(expected_template)
    result["GIT_INDEX_FILE"] = str(index_path)
    if set(result) != set(expected_template) or any(not isinstance(value, str) for value in result.values()):
        _fail("result Git child environment is not the exact fixed mapping")
    return result


def _parse_local_config(raw: bytes) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        key_raw, separator, value_raw = record.partition(b"\n")
        if not separator:
            _fail("authority local Git config output is malformed")
        key = key_raw.decode("utf-8", "strict").casefold()
        value = value_raw.decode("utf-8", "strict")
        result.setdefault(key, []).append(value)
    return result


def _validate_authority_config(
    authority: Path, environment: Mapping[str, str]
) -> None:
    _validate_object_pack_sources(authority)
    config = _parse_local_config(_git(authority, environment, "config", "--local", "--null", "--list"))
    singleton = {
        "core.repositoryformatversion": "0", "core.filemode": "true", "core.bare": "false",
        "core.logallrefupdates": "true", "core.autocrlf": "false", "core.eol": "lf",
        "core.safecrlf": "true",
    }
    for key, expected in singleton.items():
        if config.get(key) != [expected]:
            _fail(f"authority clone-local config mismatch: {key}")
    if set(config) != set(singleton):
        _fail("authority clone-local config contains a nonregistered member")
    forbidden = (
        authority / ".git/objects/info/alternates",
        authority / ".git/objects/info/http-alternates",
        authority / ".git/info/grafts",
        authority / ".git/shallow",
        authority / ".git/refs/replace",
    )
    if any(path.exists() or path.is_symlink() for path in forbidden):
        _fail("authority repository has a forbidden alternate/replacement source")
    packed = authority / ".git/packed-refs"
    if packed.exists() and b"refs/replace/" in _plain_bytes(
        packed, "authority packed refs", maximum=16_777_216
    ):
        _fail("authority packed refs contains a replacement ref")


def _owner_claim_value(
    *,
    commit: str,
    registration_sha: str,
    driver_raw: bytes,
) -> dict[str, Any]:
    preimage = {
        "schema_version": _OWNER_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "driver_claim_sha256": _sha256(driver_raw),
        "work_root": str(_WORK_ROOT),
    }
    result = dict(preimage)
    result["owner_nonce"] = canonical_sha256(preimage)
    if set(result) != _OWNER_KEYS:
        _fail("internal result-Git owner claim schema is invalid")
    return result


def _ensure_owner(
    *,
    commit: str,
    registration_sha: str,
    driver_raw: bytes,
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    parent = _plain_directory(_EXECUTION_ROOT, "execution root", mode=0o700)
    expected = _owner_claim_value(
        commit=commit, registration_sha=registration_sha, driver_raw=driver_raw
    )
    if _OWNER_CLAIM.exists() or _OWNER_CLAIM.is_symlink():
        observed, raw = _read_canonical(
            _OWNER_CLAIM, "result-Git owner claim", keys=_OWNER_KEYS, schema=_OWNER_SCHEMA
        )
        if observed != expected:
            _fail("existing result-Git owner claim differs from the registered identity")
    else:
        raw = _exclusive_json(_OWNER_CLAIM, expected)
    claim_metadata = _OWNER_CLAIM.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(claim_metadata.st_mode)
        or stat.S_ISLNK(claim_metadata.st_mode)
        or claim_metadata.st_dev != parent.st_dev
        or claim_metadata.st_uid != parent.st_uid
        or claim_metadata.st_nlink != 1
        or stat.S_IMODE(claim_metadata.st_mode) != 0o600
    ):
        _fail("result-Git owner claim metadata is invalid")
    claim_sha = _sha256(raw)
    if not _WORK_ROOT.exists() and not _WORK_ROOT.is_symlink():
        os.mkdir(_WORK_ROOT, 0o700)
        _fsync_directory(_EXECUTION_ROOT)
    work = _plain_directory(_WORK_ROOT, "result-Git work root", mode=0o700)
    if work.st_dev != parent.st_dev:
        _fail("result-Git work root is not on the execution-root device")
    marker = _WORK_ROOT / ".owner"
    if marker.exists() or marker.is_symlink():
        if _plain_bytes(marker, "result-Git owner marker", maximum=64) != claim_sha.encode("ascii"):
            _fail("result-Git owner marker differs from its claim SHA")
    else:
        if any(_WORK_ROOT.iterdir()):
            _fail("uninitialized result-Git work root is not empty")
        _exclusive_bytes(marker, claim_sha.encode("ascii"), mode=0o400)
    marker_meta = marker.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(marker_meta.st_mode) or stat.S_ISLNK(marker_meta.st_mode)
        or marker_meta.st_dev != work.st_dev or marker_meta.st_uid != work.st_uid
        or marker_meta.st_nlink != 1 or stat.S_IMODE(marker_meta.st_mode) != 0o400
    ):
        _fail("result-Git owner marker metadata is invalid")
    allowed = {".owner"}
    for attempt in range(1, 4):
        allowed.update({f"index-{attempt}", f"index-{attempt}.lock", f"result-tag-{attempt}"})
    if any(path.name not in allowed for path in _WORK_ROOT.iterdir()):
        _fail("result-Git work root contains an unexpected name")
    return expected, raw, work


def _ref_oid(
    authority: Path,
    environment: Mapping[str, str],
    ref: str,
) -> str | None:
    code, stdout, stderr = _git_process(
        authority,
        environment,
        [_GIT, "--no-replace-objects", "rev-parse", "--verify", "--quiet", ref],
        allow_nonzero=True,
    )
    if code != 0:
        if code != 1 or stdout != b"" or stderr != b"":
            _fail(f"failed ref lookup was not a clean absent ref: {ref}")
        return None
    oid = stdout.decode("ascii", "strict").strip()
    return _hex(oid, 40, f"ref {ref}")


def _expected_delta(paths: Sequence[str]) -> bytes:
    return b"".join(b"A\0" + path.encode("utf-8") + b"\0" for path in sorted(paths))


def _validate_result_commit(
    authority: Path,
    environment: Mapping[str, str],
    *,
    commit: str,
    parent: str,
    files: Sequence[tuple[str, bytes]],
    expected_tree: str | None = None,
) -> str:
    _hex(commit, 40, "R8 commit")
    if _git(authority, environment, "cat-file", "-t", commit) != b"commit\n":
        _fail("R8 object is not a commit")
    raw = _git(authority, environment, "cat-file", "-p", commit)
    if _git_oid("commit", raw) != commit:
        _fail("R8 commit bytes do not reproduce its object ID")
    header, separator, message = raw.partition(b"\n\n")
    lines = header.splitlines()
    if not separator or len(lines) != 4 or message != b"Record action-QBC v8 open diagnostic result\n":
        _fail("R8 commit headers/message are not the deterministic contract")
    tree_line, parent_line, author_line, committer_line = lines
    if not tree_line.startswith(b"tree ") or parent_line != f"parent {parent}".encode("ascii"):
        _fail("R8 tree/parent identity is invalid")
    tree = _hex(tree_line[5:].decode("ascii"), 40, "R8 tree")
    if expected_tree is not None and tree != expected_tree:
        _fail("R8 commit tree differs from write-tree")
    expected_actor = (
        b"ARC3 v8 Result Bot <arc3-v8-result@invalid.example> 1786370400 +1000"
    )
    if author_line != b"author " + expected_actor:
        _fail("R8 author identity/date is invalid")
    if committer_line != b"committer " + expected_actor:
        _fail("R8 committer identity/date is invalid")
    delta = _git(
        authority, environment, "diff-tree", "--no-commit-id", "--name-status", "-r", "-z",
        parent, commit,
    )
    if delta != _expected_delta([path for path, _raw in files]):
        _fail("O8..R8 is not the selected addition-only path set")
    for path, expected_raw in files:
        if _git(authority, environment, "cat-file", "blob", f"{commit}:{path}") != expected_raw:
            _fail(f"R8 file blob differs from immutable bundle: {path}")
    return tree


def _final_tag_path(authority: Path) -> Path:
    return authority / ".git/refs/tags" / _RESULT_TAG


def _require_branch_absent(
    authority: Path, environment: Mapping[str, str]
) -> None:
    if _ref_oid(authority, environment, _RESULT_BRANCH_REF) is not None:
        _fail("authority result branch must remain absent")
    loose = authority / ".git/refs/heads/action-qbc-v8-open-diagnostic-result"
    if loose.exists() or loose.is_symlink():
        _fail("authority result branch path exists")
    lock = authority / ".git/refs/heads/action-qbc-v8-open-diagnostic-result.lock"
    if lock.exists() or lock.is_symlink():
        _fail("authority result branch lock exists")


def _existing_final_tag(
    authority: Path,
    environment: Mapping[str, str],
    *,
    parent: str,
    files: Sequence[tuple[str, bytes]],
) -> str | None:
    work = _plain_directory(_WORK_ROOT, "result-Git work root", mode=0o700)
    tags_descriptor, tags = _open_tags_directory(authority)
    try:
        if tags.st_dev != work.st_dev:
            _fail("authority tags and result-Git work roots are on different devices")
        _require_no_entry(
            tags_descriptor, f"{_RESULT_TAG}.lock", "authority result-tag lock"
        )
        resolved = _ref_oid(authority, environment, _RESULT_TAG_REF)
        metadata = _entry_metadata(tags_descriptor, _RESULT_TAG)
        if metadata is None:
            if resolved is not None:
                _fail("result tag resolves without the registered loose tag file")
            return None
        raw, metadata = _read_entry(
            tags_descriptor, _RESULT_TAG, "authoritative result tag", 41
        )
        if (
            len(raw) != 41
            or not raw.endswith(b"\n")
            or stat.S_IMODE(metadata.st_mode) != 0o444
            or metadata.st_dev != work.st_dev
            or metadata.st_uid != work.st_uid
            or metadata.st_nlink != 2
        ):
            _fail("authoritative result tag metadata/bytes are invalid")
        os.fsync(tags_descriptor)
    finally:
        os.close(tags_descriptor)
    commit = _hex(raw[:-1].decode("ascii", "strict"), 40, "authoritative result tag commit")
    if resolved != commit:
        _fail("authoritative result tag filesystem/Git resolution differs")
    _require_branch_absent(authority, environment)
    _validate_result_commit(authority, environment, commit=commit, parent=parent, files=files)
    return commit


def _validate_owned_scratch(
    path: Path,
    *,
    work: os.stat_result,
    kind: str,
    authority: Path,
    environment: Mapping[str, str],
    parent: str,
    files: Sequence[tuple[str, bytes]],
) -> None:
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != work.st_uid or metadata.st_dev != work.st_dev
        or metadata.st_nlink != 1
    ):
        _fail(f"owned scratch metadata is unsafe: {path.name}")
    if kind == "tag":
        raw = _plain_bytes(path, "owned scratch tag", maximum=41)
        if len(raw) != 41 or not raw.endswith(b"\n") or stat.S_IMODE(metadata.st_mode) != 0o444:
            _fail("owned scratch tag bytes/mode are invalid")
        commit = _hex(raw[:-1].decode("ascii", "strict"), 40, "owned scratch tag commit")
        _validate_result_commit(
            authority, environment, commit=commit, parent=parent, files=files
        )


def _cleanup_attempt_scratch(
    attempt: int,
    *,
    work: os.stat_result,
    authority: Path,
    environment: Mapping[str, str],
    parent: str,
    files: Sequence[tuple[str, bytes]],
) -> None:
    if _existing_final_tag(
        authority, environment, parent=parent, files=files
    ) is not None:
        return
    descriptor = _open_directory_nofollow(_WORK_ROOT, "result-Git work root")
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_uid) != (
            work.st_dev, work.st_ino, work.st_uid
        ):
            _fail("result-Git work root changed before scratch cleanup")
        for name, kind in (
            (f"index-{attempt}.lock", "lock"),
            (f"index-{attempt}", "index"),
            (f"result-tag-{attempt}", "tag"),
        ):
            metadata = _entry_metadata(descriptor, name)
            if metadata is None:
                continue
            path = _WORK_ROOT / name
            _validate_owned_scratch(
                path, work=work, kind=kind, authority=authority, environment=environment,
                parent=parent, files=files,
            )
            current = _entry_metadata(descriptor, name)
            if current is None or (current.st_dev, current.st_ino) != (
                metadata.st_dev, metadata.st_ino
            ):
                _fail(f"owned scratch changed before removal: {name}")
            os.unlink(name, dir_fd=descriptor)
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _result_transaction(execution: Mapping[str, Any]) -> Mapping[str, Any]:
    value = execution.get("result_ref_transaction")
    expected_keys = {
        "authoritative_tag", "forbidden_authority_branch", "commit_message",
        "git_plumbing_argvs", "scratch_index_path", "scratch_lock_path",
        "scratch_tag_path", "scratch_tag_bytes", "scratch_tag_mode",
        "result_path_sets", "local_transfer_argvs", "windows_publication_argvs",
    }
    expected_plumbing = [
        [_GIT, "--no-replace-objects", "read-tree", "<O8_COMMIT>"],
        [_GIT, "--no-replace-objects", "hash-object", "-w", "--stdin"],
        [_GIT, "--no-replace-objects", "update-index", "--add", "--cacheinfo", "100644,<FILE_BLOB>,<FILE_PATH>"],
        [_GIT, "--no-replace-objects", "write-tree"],
        [
            _GIT, "--no-replace-objects", "-c", "commit.gpgSign=false", "-c", "i18n.commitEncoding=UTF-8",
            "commit-tree", "<RESULT_TREE>", "-p", "<O8_COMMIT>",
        ],
        [
            _GIT, "--no-replace-objects", "diff-tree", "--no-commit-id", "--name-status", "-r", "-z",
            "<O8_COMMIT>", "<R8_COMMIT>",
        ],
        [_GIT, "--no-replace-objects", "cat-file", "-p", "<R8_COMMIT>"],
    ]
    expected_path_sets = {
        "scientific_result": [
            "artifacts/action_qbc_v8_open_diagnostic.json",
            "artifacts/action_qbc_v8_open_diagnostic_receipt.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ],
        "administrative_terminal": [
            "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ],
        "receipt_finalization_failed": ["docs/action_qbc_v8_open_diagnostic_result.md"],
        "finalizer_process_failed": ["docs/action_qbc_v8_open_diagnostic_result.md"],
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("authoritative_tag") != _RESULT_TAG_REF
        or value.get("forbidden_authority_branch") != _RESULT_BRANCH_REF
        or value.get("commit_message") != "Record action-QBC v8 open diagnostic result\n"
        or value.get("git_plumbing_argvs") != expected_plumbing
        or value.get("scratch_index_path") != str(_WORK_ROOT / "index-<i>")
        or value.get("scratch_lock_path") != str(_WORK_ROOT / "index-<i>.lock")
        or value.get("scratch_tag_path") != str(_WORK_ROOT / "result-tag-<i>")
        or value.get("scratch_tag_bytes") != "<R8_COMMIT>\n"
        or value.get("scratch_tag_mode") != "0444"
        or value.get("result_path_sets") != expected_path_sets
    ):
        _fail("registered result-ref transaction differs from P8")
    return value


def _replace_argv(
    template: object,
    replacements: Mapping[str, str],
    label: str,
) -> list[str]:
    result: list[str] = []
    for argument in _require_string_argv(template, label):
        replaced = argument
        for old, new in replacements.items():
            replaced = replaced.replace(old, new)
        if "<" in replaced or ">" in replaced:
            _fail(f"{label} retains a placeholder")
        result.append(replaced)
    return result


def _open_directory_nofollow(path: Path, label: str) -> int:
    if not path.is_absolute():
        _fail(f"{label} path is not absolute")
    components = path.parts[1:]
    if any(
        not component or component in {".", ".."} or "/" in component or "\x00" in component
        for component in components
    ):
        _fail(f"{label} path has an unsafe component")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path.anchor, flags)
        for component in components:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except OSError as error:
        if "descriptor" in locals():
            os.close(descriptor)
        raise LifecycleError(f"cannot open {label} without following links") from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        _fail(f"{label} is not a directory")
    return descriptor


def _open_child_directory_nofollow(parent: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            # The descriptor is never inherited by a protocol child.
            dir_fd=parent,
        )
    except OSError as error:
        raise LifecycleError(f"cannot open {label} without following links") from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        _fail(f"{label} is not a directory")
    return descriptor


def _open_tags_directory(authority: Path) -> tuple[int, os.stat_result]:
    descriptors: list[int] = []
    try:
        descriptors.append(_open_directory_nofollow(authority, "authority root"))
        for name, label in ((".git", "authority Git directory"), ("refs", "authority refs directory"), ("tags", "authority tags directory")):
            descriptors.append(_open_child_directory_nofollow(descriptors[-1], name, label))
        result = descriptors.pop()
        metadata = os.fstat(result)
        if os.name == "posix" and metadata.st_uid != _owner_uid():
            os.close(result)
            _fail("authority tags directory has the wrong owner")
        return result, metadata
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _entry_metadata(parent: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise LifecycleError(f"cannot inspect directory entry: {name}") from error


def _read_entry(parent: int, name: str, label: str, maximum: int) -> tuple[bytes, os.stat_result]:
    before = _entry_metadata(parent, name)
    if before is None or not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        _fail(f"{label} is not a plain regular file")
    if before.st_size > maximum:
        _fail(f"{label} exceeds its byte cap")
    try:
        descriptor = os.open(
            name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent
        )
    except OSError as error:
        raise LifecycleError(f"cannot reopen {label}") from error
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            _fail(f"{label} changed before reopen")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(raw) != before.st_size or len(raw) > maximum:
        _fail(f"{label} changed while being read")
    current = _entry_metadata(parent, name)
    if current is None or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
        _fail(f"{label} changed after reopen")
    return raw, current


def _require_no_entry(parent: int, name: str, label: str) -> None:
    if _entry_metadata(parent, name) is not None:
        _fail(f"{label} must be absent")


def _exclusive_scratch_tag(parent: int, name: str, raw: bytes) -> os.stat_result:
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o444,
            dir_fd=parent,
        )
    except OSError as error:
        raise _AttemptError("could not exclusively create the attempt tag") from error
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o444)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(parent)
    return metadata


def _validate_tag_entry(
    parent: int,
    name: str,
    *,
    expected_raw: bytes,
    expected_device: int,
    expected_owner: int,
    expected_links: int,
    label: str,
) -> os.stat_result:
    raw, metadata = _read_entry(parent, name, label, 41)
    if (
        raw != expected_raw
        or _sha256(raw) != _sha256(expected_raw)
        or stat.S_IMODE(metadata.st_mode) != 0o444
        or metadata.st_dev != expected_device
        or metadata.st_uid != expected_owner
        or metadata.st_nlink != expected_links
    ):
        _fail(f"{label} metadata or bytes are invalid")
    return metadata


def _link_authoritative_tag(
    authority: Path,
    environment: Mapping[str, str],
    *,
    work: os.stat_result,
    attempt: int,
    commit: str,
    parent: str,
    files: Sequence[tuple[str, bytes]],
) -> str:
    expected_raw = f"{commit}\n".encode("ascii")
    work_descriptor = _open_directory_nofollow(_WORK_ROOT, "result-Git work root")
    tags_descriptor = -1
    try:
        current_work = os.fstat(work_descriptor)
        if (
            (current_work.st_dev, current_work.st_ino, current_work.st_uid)
            != (work.st_dev, work.st_ino, work.st_uid)
            or stat.S_IMODE(current_work.st_mode) != 0o700
        ):
            _fail("result-Git work root changed during publication")
        scratch_name = f"result-tag-{attempt}"
        _validate_tag_entry(
            work_descriptor,
            scratch_name,
            expected_raw=expected_raw,
            expected_device=work.st_dev,
            expected_owner=work.st_uid,
            expected_links=1,
            label="attempt result tag",
        )
        tags_descriptor, tags = _open_tags_directory(authority)
        if tags.st_dev != work.st_dev:
            _fail("authority tags and result-Git work roots are on different devices")
        _require_no_entry(tags_descriptor, f"{_RESULT_TAG}.lock", "authority result-tag lock")
        _require_branch_absent(authority, environment)
        existing = _entry_metadata(tags_descriptor, _RESULT_TAG)
        linked_ours = False
        if existing is not None:
            _validate_tag_entry(
                tags_descriptor,
                _RESULT_TAG,
                expected_raw=expected_raw,
                expected_device=work.st_dev,
                expected_owner=work.st_uid,
                expected_links=2,
                label="authoritative result tag",
            )
        else:
            try:
                os.link(
                    scratch_name,
                    _RESULT_TAG,
                    src_dir_fd=work_descriptor,
                    dst_dir_fd=tags_descriptor,
                    follow_symlinks=False,
                )
                linked_ours = True
            except FileExistsError:
                _validate_tag_entry(
                    tags_descriptor,
                    _RESULT_TAG,
                    expected_raw=expected_raw,
                    expected_device=work.st_dev,
                    expected_owner=work.st_uid,
                    expected_links=2,
                    label="racing authoritative result tag",
                )
            except OSError as error:
                raise _AttemptError("atomic authoritative-tag link failed") from error
        os.fsync(tags_descriptor)
        final_after = _validate_tag_entry(
            tags_descriptor,
            _RESULT_TAG,
            expected_raw=expected_raw,
            expected_device=work.st_dev,
            expected_owner=work.st_uid,
            expected_links=2,
            label="linked authoritative result tag",
        )
        if linked_ours:
            scratch_after = _validate_tag_entry(
                work_descriptor,
                scratch_name,
                expected_raw=expected_raw,
                expected_device=work.st_dev,
                expected_owner=work.st_uid,
                expected_links=2,
                label="linked attempt result tag",
            )
            if (scratch_after.st_dev, scratch_after.st_ino) != (
                final_after.st_dev, final_after.st_ino
            ):
                _fail("authoritative and attempt tags are not hard links")
    finally:
        if tags_descriptor >= 0:
            os.close(tags_descriptor)
        os.close(work_descriptor)
    if _ref_oid(authority, environment, _RESULT_TAG_REF) != commit:
        _fail("authoritative result tag does not resolve to R8")
    if _git(authority, environment, "cat-file", "-t", commit) != b"commit\n":
        _fail("authoritative result tag does not name a commit")
    _require_branch_absent(authority, environment)
    _validate_result_commit(authority, environment, commit=commit, parent=parent, files=files)
    return commit


def _normal_document(
    registration: Mapping[str, Any],
    *,
    commit: str,
    disposition: object,
    stage: object,
    underlying_stage: object,
) -> bytes:
    contract = _execution(registration).get("result_document_contract")
    if not isinstance(contract, Mapping) or set(contract) != {
        "schema_version", "renderer_source", "normal_template", "emergency_template",
        "normal_input_names", "emergency_input_names", "normal_cases",
    } or contract.get("schema_version") != _RESULT_DOCUMENT_SCHEMA:
        _fail("registered result-document contract is invalid")
    template = contract.get("normal_template")
    if not isinstance(template, Mapping) or set(template) != {"text", "sha256"}:
        _fail("registered normal result template object is invalid")
    text = template.get("text")
    if not isinstance(text, str) or template.get("sha256") != _sha256(text.encode("ascii")):
        _fail("registered normal result template text/hash is invalid")
    inputs = {
        "disposition": disposition,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "stage": stage,
        "underlying_stage": underlying_stage,
    }
    if contract.get("normal_input_names") != sorted(inputs):
        _fail("registered normal result template input names are invalid")
    rendered = text
    for key, value in inputs.items():
        placeholder = "{" + key + "}"
        if rendered.count(placeholder) != 1:
            _fail(f"normal result template placeholder count is invalid: {key}")
        rendered = rendered.replace(placeholder, _format_template_value(value))
    if "{" in rendered or "}" in rendered:
        _fail("normal result document retains a placeholder")
    return rendered.encode("ascii")


def _validate_selected_document(
    registration: Mapping[str, Any],
    *,
    commit: str,
    bundle: Mapping[str, Any],
    files: Sequence[tuple[str, bytes]],
    emergency: bool,
) -> None:
    by_path = dict(files)
    document_path = "docs/action_qbc_v8_open_diagnostic_result.md"
    if emergency:
        finalizer_exit = bundle.get("finalizer_exit_code")
        if finalizer_exit is not None and (
            not isinstance(finalizer_exit, int) or isinstance(finalizer_exit, bool)
        ):
            _fail("emergency finalizer exit code is invalid")
        final_exists = bundle.get("finalization_bundle_exists")
        ledger_exists = bundle.get("lifecycle_ledger_exists")
        final_sha = bundle.get("finalization_bundle_sha256")
        ledger_sha = bundle.get("lifecycle_ledger_sha256")
        if (
            not isinstance(final_exists, bool)
            or not isinstance(ledger_exists, bool)
            or (
                final_exists and final_sha is not None
                and _hex(final_sha, 64, "emergency finalization SHA") != final_sha
            )
            or (not final_exists and final_sha is not None)
            or (
                ledger_exists and ledger_sha is not None
                and _hex(ledger_sha, 64, "emergency ledger SHA") != ledger_sha
            )
            or (not ledger_exists and ledger_sha is not None)
        ):
            _fail("emergency evidence existence/hash fields are invalid")
        finalizer = _ChildResult(
            bundle.get("finalizer_classification") not in {
                "deadline_admission_failed", "spawn_error"
            },
            cast(int | None, finalizer_exit),
            cast(bool | None, bundle.get("finalizer_timed_out")),
            cast(bool | None, bundle.get("finalizer_child_cleanup_passes")),
            cast(str, bundle.get("finalizer_classification")),
        )
        expected = _emergency_document(
            registration,
            commit=commit,
            underlying_stage=cast(str | None, bundle.get("underlying_stage")),
            finalizer=finalizer,
            finalization=_evidence_state(_FINAL_BUNDLE, "finalization-bundle evidence"),
            ledger=_evidence_state(_LEDGER, "lifecycle-ledger evidence"),
            preparation=_evidence_state(_PREPARATION, "preparation-receipt evidence"),
            preparation_verification=_evidence_state(
                _PREPARATION_VERIFICATION, "preparation-verification evidence"
            ),
        )
    else:
        expected = _normal_document(
            registration,
            commit=commit,
            disposition=bundle.get("disposition"),
            stage=bundle.get("stage"),
            underlying_stage=bundle.get("underlying_stage"),
        )
    if by_path.get(document_path) != expected:
        _fail("selected bundle result document differs from the registered renderer")


def _load_driver_claim(
    *,
    commit: str,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    value, raw = _read_canonical(
        _DRIVER, "lifecycle driver claim", keys=_DRIVER_KEYS, schema=_DRIVER_SCHEMA
    )
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping):
        _fail("registration argv hashes are absent")
    if (
        value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration.get("content_sha256")
        or value.get("driver_argv_sha256") != hashes.get("lifecycle_driver")
    ):
        _fail("lifecycle driver claim identity is invalid")
    _hex(value.get("remote_claim_sha256"), 64, "driver remote-claim SHA")
    return value, raw


def _publication_attempt(
    authority: Path,
    execution: Mapping[str, Any],
    *,
    attempt: int,
    parent: str,
    bundle_path: Path,
    bundle_raw: bytes,
    files: Sequence[tuple[str, bytes]],
    work: os.stat_result,
) -> str:
    transaction = _result_transaction(execution)
    templates = transaction.get("git_plumbing_argvs")
    if not isinstance(templates, list) or len(templates) != 7:
        _fail("registered Git plumbing list is invalid")
    index_path = _WORK_ROOT / f"index-{attempt}"
    environment = _publisher_environment(execution, authority, index_path)
    if _evidence_state(bundle_path, "selected immutable bundle").raw != bundle_raw:
        _fail("selected bundle changed before the publication attempt")
    _cleanup_attempt_scratch(
        attempt,
        work=work,
        authority=authority,
        environment=environment,
        parent=parent,
        files=files,
    )
    existing = _existing_final_tag(
        authority, environment, parent=parent, files=files
    )
    if existing is not None:
        return existing
    _require_branch_absent(authority, environment)
    read_tree = _replace_argv(
        templates[0], {"<O8_COMMIT>": parent}, "registered read-tree command"
    )
    _git_process(authority, environment, read_tree)
    _validate_owned_scratch(
        index_path,
        work=work,
        kind="index",
        authority=authority,
        environment=environment,
        parent=parent,
        files=files,
    )
    for path, raw in files:
        hash_object = _replace_argv(
            templates[1], {}, "registered hash-object command"
        )
        _code, stdout, _stderr = _git_process(
            authority, environment, hash_object, input_bytes=raw
        )
        if len(stdout) != 41 or not stdout.endswith(b"\n"):
            _fail("hash-object returned malformed object identity")
        blob = _hex(stdout[:-1].decode("ascii", "strict"), 40, "result file blob")
        if blob != _git_oid("blob", raw):
            _fail("hash-object returned an unexpected object identity")
        update_index = _replace_argv(
            templates[2],
            {"<FILE_BLOB>": blob, "<FILE_PATH>": path},
            "registered update-index command",
        )
        _git_process(authority, environment, update_index)
    write_tree = _replace_argv(templates[3], {}, "registered write-tree command")
    _code, stdout, _stderr = _git_process(authority, environment, write_tree)
    if len(stdout) != 41 or not stdout.endswith(b"\n"):
        _fail("write-tree returned malformed tree identity")
    tree = _hex(stdout[:-1].decode("ascii", "strict"), 40, "result tree")
    commit_tree = _replace_argv(
        templates[4],
        {"<RESULT_TREE>": tree, "<O8_COMMIT>": parent},
        "registered commit-tree command",
    )
    message = cast(str, transaction["commit_message"]).encode("ascii")
    _code, stdout, _stderr = _git_process(
        authority, environment, commit_tree, input_bytes=message
    )
    if len(stdout) != 41 or not stdout.endswith(b"\n"):
        _fail("commit-tree returned malformed commit identity")
    commit = _hex(stdout[:-1].decode("ascii", "strict"), 40, "R8 commit")
    _validate_result_commit(
        authority,
        environment,
        commit=commit,
        parent=parent,
        files=files,
        expected_tree=tree,
    )
    if _evidence_state(bundle_path, "selected immutable bundle").raw != bundle_raw:
        _fail("selected bundle changed while Git objects were constructed")
    work_descriptor = _open_directory_nofollow(_WORK_ROOT, "result-Git work root")
    try:
        current = os.fstat(work_descriptor)
        if (current.st_dev, current.st_ino, current.st_uid) != (
            work.st_dev, work.st_ino, work.st_uid
        ):
            _fail("result-Git work root changed before attempt-tag publication")
        scratch_raw = f"{commit}\n".encode("ascii")
        _exclusive_scratch_tag(work_descriptor, f"result-tag-{attempt}", scratch_raw)
        _validate_tag_entry(
            work_descriptor,
            f"result-tag-{attempt}",
            expected_raw=scratch_raw,
            expected_device=work.st_dev,
            expected_owner=work.st_uid,
            expected_links=1,
            label="attempt result tag",
        )
    finally:
        os.close(work_descriptor)
    return _link_authoritative_tag(
        authority,
        environment,
        work=work,
        attempt=attempt,
        commit=commit,
        parent=parent,
        files=files,
    )


def _publish_result(
    *,
    authority: Path,
    registration_relative: str,
    observed_argv: Sequence[str],
) -> str:
    bootstrap_environment = _base_git_environment(
        authority, _WORK_ROOT / "index-bootstrap"
    )
    parent = _derive_o8(authority, bootstrap_environment)
    registration, _registration_raw = _load_registration(
        authority, registration_relative, parent, bootstrap_environment
    )
    _verify_own_source(authority, parent, bootstrap_environment)
    execution = _require_registered_execution(
        registration, publish_argv=observed_argv
    )
    _result_transaction(execution)
    _driver, driver_raw = _load_driver_claim(
        commit=parent, registration=registration, execution=execution
    )
    registration_sha = cast(str, registration["content_sha256"])
    bundle_path, bundle_raw, bundle, files, emergency = _selected_bundle(
        commit=parent,
        registration_sha=registration_sha,
        registration=registration,
    )
    _validate_selected_document(
        registration,
        commit=parent,
        bundle=bundle,
        files=files,
        emergency=emergency,
    )
    ledger_raw = _evidence_state(_LEDGER, "raw lifecycle-ledger evidence").raw
    ledger = _validate_ledger_for_publish(
        ledger_raw,
        commit=parent,
        registration_sha=registration_sha,
        driver_raw=driver_raw,
    )
    _require_ledger_or_bypass(
        ledger_raw=ledger_raw,
        ledger_value=ledger,
        bundle=bundle,
        emergency=emergency,
    )
    if _evidence_state(bundle_path, "selected immutable bundle").raw != bundle_raw:
        _fail("selected bundle changed before result-Git ownership")
    _owner, _owner_raw, initial_work = _ensure_owner(
        commit=parent, registration_sha=registration_sha, driver_raw=driver_raw
    )
    initial_identity = (
        initial_work.st_dev, initial_work.st_ino, initial_work.st_uid,
        stat.S_IMODE(initial_work.st_mode),
    )
    precheck_environment = _publisher_environment(
        execution, authority, _WORK_ROOT / "index-1"
    )
    _validate_authority_config(authority, precheck_environment)
    _require_branch_absent(authority, precheck_environment)
    existing = _existing_final_tag(
        authority, precheck_environment, parent=parent, files=files
    )
    if existing is not None:
        return existing
    last_error: _AttemptError | None = None
    for attempt in range(1, 4):
        _owner, _owner_raw, work = _ensure_owner(
            commit=parent, registration_sha=registration_sha, driver_raw=driver_raw
        )
        if (
            work.st_dev, work.st_ino, work.st_uid, stat.S_IMODE(work.st_mode)
        ) != initial_identity:
            _fail("result-Git work root identity changed between attempts")
        environment = _publisher_environment(
            execution, authority, _WORK_ROOT / f"index-{attempt}"
        )
        existing = _existing_final_tag(
            authority, environment, parent=parent, files=files
        )
        if existing is not None:
            return existing
        try:
            return _publication_attempt(
                authority,
                execution,
                attempt=attempt,
                parent=parent,
                bundle_path=bundle_path,
                bundle_raw=bundle_raw,
                files=files,
                work=work,
            )
        except _AttemptError as error:
            last_error = error
            existing = _existing_final_tag(
                authority, environment, parent=parent, files=files
            )
            if existing is not None:
                return existing
            _cleanup_attempt_scratch(
                attempt,
                work=work,
                authority=authority,
                environment=environment,
                parent=parent,
                files=files,
            )
    if last_error is not None:
        raise LifecycleError("all three registered result-Git attempts failed") from last_error
    _fail("result-Git publication made no registered attempt")


def _earlier_stage(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    if current not in _UNDERLYING_ORDER or candidate not in _UNDERLYING_ORDER:
        _fail("cannot compare an unregistered underlying stage")
    return current if _UNDERLYING_ORDER.index(current) <= _UNDERLYING_ORDER.index(candidate) else candidate


def _process_commands(
    execution: Mapping[str, Any],
) -> tuple[list[str], list[str], list[str], list[str]]:
    scientific = execution.get("scientific_argv_template")
    validator = execution.get("payload_validator_argv_template")
    a_runner = _substitute(
        scientific,
        {
            "<LABEL>": "A",
            "<START_CLAIM>": str(_A_START),
            "<PRIOR_VALIDATION_OR_NULL>": "null",
            "<OUTPUT_PATH>": str(_A_OUTPUT),
        },
        "process-A scientific command",
    )
    b_runner = _substitute(
        scientific,
        {
            "<LABEL>": "B",
            "<START_CLAIM>": str(_B_START),
            "<PRIOR_VALIDATION_OR_NULL>": str(_A_VALIDATION),
            "<OUTPUT_PATH>": str(_B_OUTPUT),
        },
        "process-B scientific command",
    )
    a_validator = _substitute(
        validator,
        {
            "<LABEL>": "A",
            "<START_CLAIM>": str(_A_START),
            "<VALIDATOR_CLAIM>": str(_A_VALIDATOR),
            "<VALIDATION_RECEIPT>": str(_A_VALIDATION),
            "<OUTPUT_PATH>": str(_A_OUTPUT),
        },
        "process-A validator command",
    )
    b_validator = _substitute(
        validator,
        {
            "<LABEL>": "B",
            "<START_CLAIM>": str(_B_START),
            "<VALIDATOR_CLAIM>": str(_B_VALIDATOR),
            "<VALIDATION_RECEIPT>": str(_B_VALIDATION),
            "<OUTPUT_PATH>": str(_B_OUTPUT),
        },
        "process-B validator command",
    )
    return a_runner, a_validator, b_runner, b_validator


def _run_registered_lifecycle(
    *,
    authority: Path,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    commit: str,
    driver_raw: bytes,
    deadline: float,
) -> tuple[str | None, int | None, list[str], dict[str, Any], dict[str, Any]]:
    a_runner, a_validator, b_runner, b_validator = _process_commands(execution)
    process_a = _process_record("A", _A_ROOT)
    process_b = _process_record("B", _B_ROOT)
    sequence: list[str] = []
    stage: str | None = None
    arm_exit: int | None = None
    registration_sha = cast(str, registration["content_sha256"])
    try:
        arm_argv = _require_string_argv(execution.get("arm_argv"), "registered arm command")
        arm_exit = _run_named_child(
            "arm",
            arm_argv,
            authority,
            wrapper_seconds=120,
            deadline=deadline,
            reserve_seconds=_DRIVER_RESERVE,
        )
        sequence.append("arm_returned")
        stage = _remote_and_arm_stage(
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
            execution=execution,
        )
        if arm_exit != 0 and stage is None:
            stage = "arm_receipt_invalid"
        if stage is None:
            environment = _preparation_command_environment()
            try:
                _validate_authority_config(authority, environment)
            except (LifecycleError, OSError, subprocess.SubprocessError):
                stage = "authority_identity_invalid"
        if stage is None:
            _require_child_start_window(
                deadline=deadline,
                allowance_seconds=2725,
                reserve_seconds=_DRIVER_RESERVE,
            )
            process_a["runner_argv_sha256"] = canonical_sha256(a_runner)
            process_a["runner_exit_code"] = _run_named_child(
                "process_a_runner",
                a_runner,
                _A_ROOT,
                wrapper_seconds=2700,
                deadline=deadline,
                reserve_seconds=_DRIVER_RESERVE,
            )
            sequence.append("process_a_runner_returned")
            _update_process_artifacts(
                process_a,
                start=_A_START,
                validator=_A_VALIDATOR,
                validation=_A_VALIDATION,
                output=_A_OUTPUT,
            )
            if process_a["runner_exit_code"] != 0:
                stage = "process_a_nonzero"
            elif _optional_raw(_A_OUTPUT) is None:
                stage = "process_a_output_missing"
        if stage is None:
            _require_child_start_window(
                deadline=deadline,
                allowance_seconds=315,
                reserve_seconds=_DRIVER_RESERVE,
            )
            process_a["validator_argv_sha256"] = canonical_sha256(a_validator)
            process_a["validator_exit_code"] = _run_named_child(
                "process_a_validator",
                a_validator,
                _A_ROOT,
                wrapper_seconds=300,
                deadline=deadline,
                reserve_seconds=_DRIVER_RESERVE,
            )
            sequence.append("process_a_validator_returned")
            _update_process_artifacts(
                process_a,
                start=_A_START,
                validator=_A_VALIDATOR,
                validation=_A_VALIDATION,
                output=_A_OUTPUT,
            )
            if process_a["validator_exit_code"] != 0 or not _validation_is_valid(
                _A_VALIDATION, label="A", output=_A_OUTPUT
            ):
                stage = "process_a_validation_failed"
        if stage is None:
            _require_child_start_window(
                deadline=deadline,
                allowance_seconds=2725,
                reserve_seconds=_DRIVER_RESERVE,
            )
            process_b["runner_argv_sha256"] = canonical_sha256(b_runner)
            process_b["runner_exit_code"] = _run_named_child(
                "process_b_runner",
                b_runner,
                _B_ROOT,
                wrapper_seconds=2700,
                deadline=deadline,
                reserve_seconds=_DRIVER_RESERVE,
            )
            sequence.append("process_b_runner_returned")
            _update_process_artifacts(
                process_b,
                start=_B_START,
                validator=_B_VALIDATOR,
                validation=_B_VALIDATION,
                output=_B_OUTPUT,
            )
            if process_b["runner_exit_code"] != 0:
                stage = "process_b_nonzero"
            elif _optional_raw(_B_OUTPUT) is None:
                stage = "process_b_output_missing"
        if stage is None:
            _require_child_start_window(
                deadline=deadline,
                allowance_seconds=315,
                reserve_seconds=_DRIVER_RESERVE,
            )
            process_b["validator_argv_sha256"] = canonical_sha256(b_validator)
            process_b["validator_exit_code"] = _run_named_child(
                "process_b_validator",
                b_validator,
                _B_ROOT,
                wrapper_seconds=300,
                deadline=deadline,
                reserve_seconds=_DRIVER_RESERVE,
            )
            sequence.append("process_b_validator_returned")
            _update_process_artifacts(
                process_b,
                start=_B_START,
                validator=_B_VALIDATOR,
                validation=_B_VALIDATION,
                output=_B_OUTPUT,
            )
            if process_b["validator_exit_code"] != 0 or not _validation_is_valid(
                _B_VALIDATION, label="B", output=_B_OUTPUT
            ):
                stage = "process_b_validation_failed"
        if stage is None and _plain_bytes(
            _A_OUTPUT, "validated process-A payload"
        ) != _plain_bytes(_B_OUTPUT, "validated process-B payload"):
            stage = "payload_byte_mismatch"
    except _LifecycleChildCleanupFailure:
        raise
    except Exception:
        stage = _earlier_stage(stage, "lifecycle_driver_failed")
    _update_process_artifacts(
        process_a,
        start=_A_START,
        validator=_A_VALIDATOR,
        validation=_A_VALIDATION,
        output=_A_OUTPUT,
    )
    _update_process_artifacts(
        process_b,
        start=_B_START,
        validator=_B_VALIDATOR,
        validation=_B_VALIDATION,
        output=_B_OUTPUT,
    )
    if sequence != list(_SEQUENCE[: len(sequence)]):
        stage = _earlier_stage(stage, "lifecycle_driver_failed")
    return stage, arm_exit, sequence, process_a, process_b


def _publish_lifecycle_ledger(
    *,
    commit: str,
    registration_sha: str,
    driver_raw: bytes,
    arm_exit: int | None,
    sequence: Sequence[str],
    process_a: Mapping[str, Any],
    process_b: Mapping[str, Any],
    stage: str | None,
) -> tuple[bytes | None, bool]:
    normal = _ledger_value(
        commit=commit,
        registration_sha=registration_sha,
        driver_raw=driver_raw,
        arm_exit=arm_exit,
        sequence=sequence,
        process_a=process_a,
        process_b=process_b,
        stage=stage,
    )
    try:
        raw = _exclusive_json(_LEDGER, normal)
        if _validate_ledger_for_publish(
            raw,
            commit=commit,
            registration_sha=registration_sha,
            driver_raw=driver_raw,
        ) != normal:
            _fail("published lifecycle ledger did not revalidate")
        return raw, True
    except Exception:
        if not _LEDGER.exists() and not _LEDGER.is_symlink():
            minimal = _ledger_value(
                commit=commit,
                registration_sha=registration_sha,
                driver_raw=driver_raw,
                arm_exit=arm_exit,
                sequence=sequence,
                process_a=process_a,
                process_b=process_b,
                stage="lifecycle_ledger_invalid",
            )
            try:
                raw = _exclusive_json(_LEDGER, minimal)
                return raw, False
            except Exception:
                pass
        return _optional_raw(_LEDGER), False


def _run_publisher_once(
    argv: Sequence[str], authority: Path, *, deadline: float
) -> int:
    result = _run_child_evidence(
        argv,
        authority,
        wrapper_seconds=_PUBLISHER_WRAPPER_SECONDS,
        deadline=deadline,
        reserve_seconds=0,
    )
    if result.classification != "completed" or result.exit_code != 0:
        raise LifecycleError(f"registered result publisher failed: {result.classification}")
    return result.exit_code


def _finish_lifecycle(
    *,
    authority: Path,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    commit: str,
    driver_raw: bytes,
    deadline: float,
    stage: str | None,
    arm_exit: int | None,
    sequence: Sequence[str],
    process_a: Mapping[str, Any],
    process_b: Mapping[str, Any],
) -> int:
    registration_sha = cast(str, registration["content_sha256"])
    try:
        ledger_raw, ledger_normal = _publish_lifecycle_ledger(
            commit=commit,
            registration_sha=registration_sha,
            driver_raw=driver_raw,
            arm_exit=arm_exit,
            sequence=sequence,
            process_a=process_a,
            process_b=process_b,
            stage=stage,
        )
    except Exception:
        ledger_raw, ledger_normal = _optional_raw(_LEDGER), False
    finalizer = _ChildResult(False, None, None, None, "spawn_error")
    # The finalizer start attempt immediately follows the sole ledger publication attempt.
    # Evidence validation for emergency rendering happens only after that child returns.
    try:
        finalizer_argv = _require_string_argv(
            execution.get("finalizer_argv_template"), "registered finalizer command"
        )
        finalizer = _run_child_evidence(
            finalizer_argv,
            authority,
            wrapper_seconds=300,
            deadline=deadline,
            reserve_seconds=0,
        )
    except Exception:
        finalizer = _ChildResult(False, None, None, None, "spawn_error")
    try:
        ledger_value = _validate_ledger_for_publish(
            ledger_raw,
            commit=commit,
            registration_sha=registration_sha,
            driver_raw=driver_raw,
        )
    except Exception:
        ledger_value = None
    underlying = stage
    if not ledger_normal or ledger_value is None:
        try:
            underlying = _earlier_stage(underlying, "lifecycle_ledger_invalid")
        except Exception:
            underlying = "lifecycle_ledger_invalid"
    normal_valid = False
    if (
        finalizer.classification == "completed"
        and finalizer.exit_code == 0
        and not _EMERGENCY_BUNDLE.exists()
        and not _EMERGENCY_BUNDLE.is_symlink()
    ):
        try:
            normal_state = _evidence_state(_FINAL_BUNDLE, "normal finalization bundle")
            if normal_state.raw is None:
                _fail("normal finalization bundle is not safely readable")
            normal_raw = normal_state.raw
            normal_bundle, normal_files = _validate_bundle_bytes(
                normal_raw,
                commit=commit,
                registration_sha=registration_sha,
                registration=registration,
                emergency=False,
            )
            _validate_selected_document(
                registration,
                commit=commit,
                bundle=normal_bundle,
                files=normal_files,
                emergency=False,
            )
            normal_valid = True
        except Exception:
            normal_valid = False
    if not normal_valid:
        if finalizer.classification == "completed" and finalizer.exit_code == 0:
            finalizer = _ChildResult(
                True,
                0,
                False,
                finalizer.child_cleanup_passes,
                "bundle_invalid",
            )
        _publish_emergency_bundle(
            registration,
            commit=commit,
            underlying_stage=underlying,
            finalizer=finalizer,
        )
    _selected_bundle(
        commit=commit,
        registration_sha=registration_sha,
        registration=registration,
    )
    if finalizer.classification == "child_cleanup_failed":
        # P8v4 makes failed outer PGID cleanup terminal.  Local emergency evidence is
        # retained and selected, but no publisher or other later child may start.
        return 1
    publisher_argv = _require_string_argv(
        execution.get("result_publisher_argv"), "registered result publisher command"
    )
    return _run_publisher_once(publisher_argv, authority, deadline=deadline)


def _execute_lifecycle(
    *,
    authority: Path,
    registration_relative: str,
    observed_argv: Sequence[str],
    deadline: float,
) -> int:
    bootstrap_environment = _preparation_command_environment()
    commit = _derive_o8(authority, bootstrap_environment)
    registration, _registration_raw = _load_registration(
        authority, registration_relative, commit, bootstrap_environment
    )
    _verify_own_source(authority, commit, bootstrap_environment)
    execution = _execution(registration)
    if list(observed_argv) != execution.get("lifecycle_driver_argv"):
        _fail("observed execute argv differs from registration")
    _command_hash(
        execution, "lifecycle_driver", execution.get("lifecycle_driver_argv")
    )
    _windows_claim, windows_claim_raw = _validate_windows_claim(
        _WINDOWS_CLAIM,
        commit=commit,
        registration=registration,
        execution=execution,
    )
    _driver, driver_raw = _acquire_driver_claim(
        commit=commit,
        registration=registration,
        windows_claim_raw=windows_claim_raw,
        execution=execution,
    )
    stage: str | None
    arm_exit: int | None
    sequence: list[str]
    process_a: dict[str, Any]
    process_b: dict[str, Any]
    try:
        execution = _require_registered_execution(
            registration, execute_argv=observed_argv
        )
        _result_transaction(execution)
        _process_commands(execution)
    except Exception:
        stage = "registration_invalid"
        arm_exit = None
        sequence = []
        process_a = _process_record("A", _A_ROOT)
        process_b = _process_record("B", _B_ROOT)
    else:
        try:
            stage, arm_exit, sequence, process_a, process_b = _run_registered_lifecycle(
                authority=authority,
                registration=registration,
                execution=execution,
                commit=commit,
                driver_raw=driver_raw,
                deadline=deadline,
            )
        except _LifecycleChildCleanupFailure:
            raise
        except Exception:
            stage = "lifecycle_driver_failed"
            arm_exit = None
            sequence = []
            process_a = _process_record("A", _A_ROOT)
            process_b = _process_record("B", _B_ROOT)
    return _finish_lifecycle(
        authority=authority,
        registration=registration,
        execution=execution,
        commit=commit,
        driver_raw=driver_raw,
        deadline=deadline,
        stage=stage,
        arm_exit=arm_exit,
        sequence=sequence,
        process_a=process_a,
        process_b=process_b,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser(
        "execute", help="run the irreversible one-shot lifecycle after the Windows claim"
    )
    execute.add_argument("--repository-root", required=True)
    execute.add_argument("--registration", required=True)
    execute.add_argument("--execution-root", required=True)
    execute.add_argument("--preparation-receipt", required=True)
    execute.add_argument("--preparation-verification-receipt", required=True)
    execute.add_argument("--windows-claim", required=True)
    execute.add_argument("--remote-claim", required=True)
    execute.add_argument("--remote-verifier-claim", required=True)
    execute.add_argument("--remote-receipt", required=True)
    execute.add_argument("--remote-supervisor-receipt", required=True)
    execute.add_argument("--arm-receipt", required=True)
    execute.add_argument("--driver-claim", required=True)
    execute.add_argument("--ledger", required=True)
    publish = subparsers.add_parser(
        "publish", help="repeat only the immutable bundle-to-Git transaction"
    )
    publish.add_argument("--repository-root", required=True)
    publish.add_argument("--registration", required=True)
    publish.add_argument("--driver-claim", required=True)
    publish.add_argument("--lifecycle-ledger", required=True)
    publish.add_argument("--finalization-bundle", required=True)
    publish.add_argument("--emergency-bundle", required=True)
    publish.add_argument("--control-time-seconds", required=True, type=int)
    return parser


def _require_isolated_runtime() -> None:
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("lifecycle entry point requires the registered -I -B runtime")


def _require_fixed_arguments(args: argparse.Namespace) -> None:
    common = {
        "repository_root": ".",
        "registration": _REGISTRATION_PATH,
        "driver_claim": str(_DRIVER),
    }
    if any(getattr(args, name) != expected for name, expected in common.items()):
        _fail("common lifecycle arguments differ from P8")
    if args.command == "execute":
        expected = {
            "execution_root": str(_EXECUTION_ROOT),
            "preparation_receipt": str(_PREPARATION),
            "preparation_verification_receipt": str(_PREPARATION_VERIFICATION),
            "windows_claim": str(_WINDOWS_CLAIM),
            "remote_claim": str(_REMOTE_CLAIM),
            "remote_verifier_claim": str(_REMOTE_VERIFIER),
            "remote_receipt": str(_REMOTE_RECEIPT),
            "remote_supervisor_receipt": str(_REMOTE_SUPERVISOR),
            "arm_receipt": str(_ARM),
            "ledger": str(_LEDGER),
        }
    elif args.command == "publish":
        expected = {
            "lifecycle_ledger": str(_LEDGER),
            "finalization_bundle": str(_FINAL_BUNDLE),
            "emergency_bundle": str(_EMERGENCY_BUNDLE),
            "control_time_seconds": _PUBLISHER_CONTROL_SECONDS,
        }
    else:
        _fail("unknown lifecycle subcommand")
    if any(getattr(args, name) != value for name, value in expected.items()):
        _fail(f"{args.command} lifecycle arguments differ from P8")


def main(argv: Sequence[str] | None = None) -> int:
    global _GIT_CONTROL_DEADLINE
    entry_epoch = time.monotonic()
    tokens = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(tokens)
    _require_isolated_runtime()
    _require_fixed_arguments(args)
    authority = Path(args.repository_root).resolve(strict=True)
    if authority != _AUTHORITY_ROOT.resolve(strict=True) or Path.cwd().resolve(strict=True) != authority:
        _fail("lifecycle command must run from the registered authority root")
    observed = ["/usr/bin/python3", "-I", "-B", sys.argv[0], *tokens]
    if observed[:4] != ["/usr/bin/python3", "-I", "-B", _SCRIPT_PATH]:
        _fail("lifecycle interpreter/source argv prefix differs from P8")
    if args.command == "execute":
        deadline = entry_epoch + _DRIVER_DEADLINE
        _GIT_CONTROL_DEADLINE = entry_epoch + (_DRIVER_DEADLINE - _DRIVER_RESERVE)
        code = _execute_lifecycle(
            authority=authority,
            registration_relative=args.registration,
            observed_argv=observed,
            deadline=deadline,
        )
        if code == 0:
            sys.stdout.buffer.write(
                canonical_json_bytes({"status": "lifecycle_complete"}) + b"\n"
            )
        return code
    _GIT_CONTROL_DEADLINE = entry_epoch + _PUBLISHER_CONTROL_SECONDS
    commit = _publish_result(
        authority=authority,
        registration_relative=args.registration,
        observed_argv=observed,
    )
    sys.stdout.buffer.write(
        canonical_json_bytes({"result_commit_sha": commit, "status": "published"}) + b"\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LifecycleError, OSError, ValueError, subprocess.SubprocessError) as error:
        sys.stderr.buffer.write(
            canonical_json_bytes({"error": str(error), "status": "refused"}) + b"\n"
        )
        raise SystemExit(2) from error
