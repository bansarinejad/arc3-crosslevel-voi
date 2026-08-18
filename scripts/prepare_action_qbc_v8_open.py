# ruff: noqa: E501
"""Prepare two frozen O8 clones and arm immutable remote-verification evidence.

This entry point is intentionally standard-library-only.  It neither imports project
modules nor performs scientific work.  ``prepare`` materializes the two offline execution
clones in one atomic promotion; ``arm`` validates and immutably copies the one-shot Windows
remote-verification evidence.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import ctypes
import email.policy
import hashlib
import io
import json
import os
import platform
import posixpath
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, Final, NoReturn

_REGISTRATION_SCHEMA: Final = "action-qbc-v8-open-registration-v1"
_PREPARATION_SCHEMA: Final = "action-qbc-v8-preparation-receipt-v2"
_PREPARATION_VERIFICATION_SCHEMA: Final = (
    "action-qbc-v8-preparation-verification-receipt-v1"
)
_ARM_SCHEMA: Final = "action-qbc-v8-arm-receipt-v2"
_CLAIM_SCHEMA: Final = "action-qbc-v8-remote-tag-verification-claim-v1"
_START_CLAIM_SCHEMA: Final = "action-qbc-v8-remote-tag-verifier-start-claim-v1"
_REMOTE_RECEIPT_SCHEMA: Final = "action-qbc-v8-remote-tag-verification-receipt-v1"
_SUPERVISOR_SCHEMA: Final = "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1"
_OWNER_SCHEMA: Final = "action-qbc-v8-preparation-owner-v1"

_TREATMENT_ID: Final = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_OPEN_FREEZE_TAG: Final = "action-qbc-v8-open-diagnostic-freeze-v2"
_O8V1_TAG: Final = "action-qbc-v8-open-diagnostic-freeze-v1"
_O8V1_COMMIT: Final = "7685fbdccd41702216b3a3f06d2a0ac699aca7ec"
_O8V1_TREE: Final = "9b9ad5ba986afacbcdb1fde3cd69e0f1c94efdf2"
_PREREGISTRATION_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v5"
_PREREGISTRATION_COMMIT: Final = "09f9caea346866a1acf35c20e0c9d937096b5ce3"
_P8V4_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
_P8V4_COMMIT: Final = "e0bff9ffc185196cafa938c8f7c9a7186366258b"
_PREREGISTRATION_V3_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
_PREREGISTRATION_V3_COMMIT: Final = "996ab2bb5a24143a110673977f63e7d111cf2060"
_PREREGISTRATION_V2_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
_PREREGISTRATION_V2_COMMIT: Final = "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
_PREREGISTRATION_V1_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
_PREREGISTRATION_V1_COMMIT: Final = "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
_PREREGISTRATION_V1_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification.md"
)
_PREREGISTRATION_V3_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v3_correction.md"
)
_P8V4_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md"
)
_P8V4_DOCUMENT_GIT_BLOB_SHA1: Final = (
    "29c991b7e23209f2c38d5e9a11a15bca51753d8e"
)
_P8V4_DOCUMENT_SHA256: Final = (
    "31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1"
)
_P8V4_DOCUMENT_BYTE_COUNT: Final = 33_215
_PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
)
_PREREGISTRATION_DOCUMENT_GIT_BLOB_SHA1: Final = (
    "7c0955a775af89dcfcde4796a9bbb4d470669d10"
)
_PREREGISTRATION_DOCUMENT_SHA256: Final = (
    "cc9d787a64700332a44f543e7a949ee5522c3663b6b0eb54e418840e560cfe6d"
)
_PREREGISTRATION_DOCUMENT_BYTE_COUNT: Final = 25_872
_R7_COMMIT: Final = "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
_REGISTRATION_PATH: Final = "artifacts/action_qbc_v8_open_registration.json"
_RECONSTRUCTOR_PATH: Final = "scripts/reconstruct_action_qbc_v8_open_registration.py"
_SUPERVISOR_SCRIPT: Final = "scripts/supervise_action_qbc_v8_remote_tag.py"
_VERIFIER_SCRIPT: Final = "scripts/verify_action_qbc_v8_remote_tag.py"
_SOURCE_URL: Final = "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi"
_REMOTE_URL: Final = "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
_REMOTE_REF: Final = f"refs/tags/{_OPEN_FREEZE_TAG}"
_EXECUTION_ROOT: Final = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"
_AUTHORITY_ROOT: Final = f"{_EXECUTION_ROOT}/authority"
_PREPARATION_RECEIPT: Final = f"{_EXECUTION_ROOT}/preparation-receipt.json"
_PREPARATION_VERIFICATION_RECEIPT: Final = (
    f"{_EXECUTION_ROOT}/preparation-verification.json"
)
_ARM_RECEIPT: Final = f"{_EXECUTION_ROOT}/arm-receipt.json"
_WINDOWS_CLAIM: Final = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json"
_WINDOWS_START_CLAIM: Final = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim.json"
_WINDOWS_REMOTE_RECEIPT: Final = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification.json"
_WINDOWS_SUPERVISOR_RECEIPT: Final = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor.json"
_UV_VERSION_STDOUT: Final = b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n"

_PYTHON_PATH: Final = r"C:\Users\User\anaconda3\python.exe"
_PYTHON_VERSION: Final = "CPython 3.12.3"
_PYTHON_SHA256: Final = "62c225fb9cdc41b139c7024581c233644f975ffc35314558c60ebefa6b88be01"
_GIT_PATH: Final = r"C:\Users\User\anaconda3\Library\bin\git.exe"
_GIT_VERSION: Final = "2.45.2.windows.1"
_GIT_SHA256: Final = "5385ff9ae361ca41e7a31b335fc0d81f2de9c35fc62a165c5e34850d837b59cc"
_TASKKILL_PATH: Final = r"C:\Windows\System32\taskkill.exe"
_TASKKILL_VERSION: Final = "file/product version 10.0.26100.8457"
_TASKKILL_SHA256: Final = "1249717315fc8f4d2df17d5db9da0444795fdb9fb83dfb1f763c3f39282244f7"

_MAX_ATTEMPTS: Final = 3
_ATTEMPT_TIMEOUT_SECONDS: Final = 120
_RETRY_DELAY_SECONDS: Final = 15
_OVERALL_DEADLINE_SECONDS: Final = 390
_VERIFIER_CHILD_DEADLINE_SECONDS: Final = 430
_SUPERVISOR_DEADLINE_SECONDS: Final = 480
_SUPERVISOR_RECEIPT_RESERVE_SECONDS: Final = 20
_STDOUT_CAP_BYTES: Final = 4096
_STDERR_CAP_BYTES: Final = 16384
_CHILD_CLEANUP_TIMEOUT_SECONDS: Final = 30
_LOCAL_GIT_TIMEOUT_SECONDS: Final = 60
_REMOTE_ARTIFACT_LIMIT: Final = 1 << 20
_ADMINISTRATIVE_EVIDENCE_LIMIT: Final = 67_108_864
_PREPARATION_STDIN_CAP_BYTES: Final = 1_048_576
_PREPARATION_STDOUT_CAP_BYTES: Final = 134_217_728
_PREPARATION_STDERR_CAP_BYTES: Final = 1_048_576
_PREPARATION_DEFAULT_TIMEOUT_SECONDS: Final = 60
_PREPARATION_ENVIRONMENT_TIMEOUT_SECONDS: Final = 600
_PREPARATION_TERM_GRACE_SECONDS: Final = 5
_PREPARATION_KILL_GRACE_SECONDS: Final = 5

_PREPARATION_COMMAND_ENVIRONMENT: Final = {
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
_PREPARATION_COMMAND_POLICY: Final = {
    "default_timeout_seconds": _PREPARATION_DEFAULT_TIMEOUT_SECONDS,
    "environment_timeout_seconds": _PREPARATION_ENVIRONMENT_TIMEOUT_SECONDS,
    "term_grace_seconds": _PREPARATION_TERM_GRACE_SECONDS,
    "kill_grace_seconds": _PREPARATION_KILL_GRACE_SECONDS,
    "stdin_cap_bytes": _PREPARATION_STDIN_CAP_BYTES,
    "stdout_cap_bytes": _PREPARATION_STDOUT_CAP_BYTES,
    "stderr_cap_bytes": _PREPARATION_STDERR_CAP_BYTES,
}
_LOCAL_GIT_CONFIG: Final = {
    "core.repositoryformatversion": "0",
    "core.filemode": "true",
    "core.bare": "false",
    "core.logallrefupdates": "true",
    "core.autocrlf": "false",
    "core.eol": "lf",
    "core.safecrlf": "true",
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
        "core.bare": "false",
        "core.filemode": "false",
        "core.ignorecase": "true",
        "core.logallrefupdates": "true",
        "core.repositoryformatversion": "0",
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

_AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v8_enabled": False,
    "final_admission_claimed": False,
}
_REGISTRATION_KEYS: Final = {
    "schema_version", "status", "treatment_id", "diagnostic_system_id",
    "comparison_semantics_id", "runtime_id", "preregistration", "v6_negative",
    "platform", "dependencies", "source_manifest", "scene_inventory", "row_inventory",
    "transform_contracts", "scientific_contract", "resource_contract",
    "execution_contract", "authorization", "content_sha256",
}
_EXECUTION_KEYS: Final = {
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
_PREPARATION_KEYS: Final = {
    "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
    "registration_content_sha256", "attempts", "authority", "process_a", "process_b",
    "command_ledger", "commands_sha256", "command_environment_sha256", "status",
}
_CLONE_KEYS: Final = {
    "root", "root_device", "root_inode", "root_owner_uid", "root_mode", "head_sha",
    "tree_sha256", "raw_materialization_sha256", "git_status_sha256", "python_version",
    "uv_version", "environment_inventory", "environment_inventory_sha256",
    "venv_materialization_sha256", "venv_python_sha256", "passes",
}
_VERIFICATION_CLONE_KEYS: Final = _CLONE_KEYS - {"environment_inventory"}
_COMMAND_LEDGER_KEYS: Final = {
    "sequence_index", "attempt_index", "label", "phase", "cwd", "argv", "argv_sha256",
    "stdin_size_bytes", "stdin_sha256", "started", "exit_code", "outcome", "timed_out",
    "duration_milliseconds", "stdout_size_bytes", "stdout_sha256", "stderr_size_bytes",
    "stderr_sha256", "child_cleanup_passes",
}
_ATTEMPT_RECORD_KEYS: Final = {
    "attempt_index", "process_a_stage", "process_b_stage", "cleanup", "promotion", "passes",
}
_CLEANUP_KEYS: Final = {"owned_paths", "removed", "passes"}
_PROMOTION_KEYS: Final = {
    "source_path", "destination_path", "source_device", "source_inode", "passes",
}
_PROCESS_STAGES: Final = {
    "not_started", "clone_failed", "raw_audit_failed", "environment_failed",
    "preflight_failed", "completed",
}
_ARM_KEYS: Final = {
    "schema_version", "treatment_id", "open_freeze_commit_sha",
    "registration_content_sha256", "preparation_receipt_exists",
    "preparation_receipt_read_status", "preparation_receipt_sha256",
    "preparation_verification_receipt_exists", "preparation_verification_receipt_read_status",
    "preparation_verification_receipt_sha256", "remote_claim_sha256",
    "remote_verifier_claim_sha256", "remote_receipt_sha256",
    "remote_supervisor_receipt_sha256", "status",
}
_PREPARATION_VERIFICATION_KEYS: Final = {
    "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
    "registration_content_sha256", "preparation_receipt_sha256",
    "verification_argv_sha256", "authority", "process_a", "process_b", "status",
    "content_sha256",
}
_CLAIM_KEYS: Final = {
    "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
    "registration_content_sha256", "supervisor_argv_sha256",
    "supervisor_script_git_blob_sha1", "supervisor_script_sha256",
    "verifier_script_git_blob_sha1", "verifier_script_sha256",
}
_START_CLAIM_KEYS: Final = {
    "schema_version", "treatment_id", "claim_sha256", "open_freeze_commit_sha",
    "registration_content_sha256", "verifier_argv_sha256",
}
_REMOTE_RECEIPT_KEYS: Final = {
    "schema_version", "treatment_id", "claim_sha256", "verifier_start_claim_sha256",
    "open_freeze_commit_sha", "open_freeze_tag", "registration_content_sha256",
    "remote_url", "ref", "python", "git", "taskkill", "policy", "attempts", "status",
    "selected_attempt", "total_duration_milliseconds",
}
_REMOTE_ATTEMPT_KEYS: Final = {
    "attempt_index", "exit_code", "classification", "timed_out", "duration_milliseconds",
    "stdout_size_bytes", "stdout_sha256", "stdout_base64", "stderr_size_bytes",
    "stderr_sha256", "stderr_base64", "child_cleanup_passes",
}
_REMOTE_CLASSIFICATIONS: Final = {
    "verified", "retryable_empty_exit_0", "retryable_timeout_124", "retryable_git_128",
    "unexpected_output", "unexpected_exit", "stdout_limit", "stderr_limit",
    "child_cleanup_failed", "spawn_error", "overall_deadline",
    "post_spawn_initialization_failed", "stream_capture_failed",
}
_RETRYABLE_CLASSIFICATIONS: Final = {
    "retryable_empty_exit_0", "retryable_timeout_124", "retryable_git_128",
}
_SUPERVISOR_KEYS: Final = {
    "schema_version", "treatment_id", "claim_sha256", "verifier_start_claim_sha256",
    "open_freeze_commit_sha", "registration_content_sha256", "verifier_argv_sha256",
    "verifier_exit_code", "classification", "timed_out", "duration_milliseconds",
    "stdout_size_bytes", "stdout_sha256", "stdout_base64", "stderr_size_bytes",
    "stderr_sha256", "stderr_base64", "child_cleanup_passes",
    "remote_receipt_sha256", "status",
}
_SUPERVISOR_CLASSIFICATIONS: Final = {
    "verifier_completed", "verifier_timeout_124", "stdout_limit", "stderr_limit",
    "child_cleanup_failed", "spawn_error", "remote_receipt_missing", "remote_receipt_invalid",
    "post_spawn_initialization_failed", "stream_capture_failed",
}


class ProtocolError(RuntimeError):
    """A frozen preparation or arm invariant failed closed."""


def _fail(message: str) -> NoReturn:
    raise ProtocolError(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise ProtocolError("value is not canonical-JSON encodable") from error


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_canonical_object(data: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"{name} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        _fail(f"{name} is not an object")
    if canonical_json_bytes(value) != data:
        _fail(f"{name} is not the exact canonical JSON byte sequence")
    return value


def _require_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        _fail(f"{name} has an invalid key set")


def _require_hex(value: Any, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{name} is not {length}-character lowercase hexadecimal")
    return value


def _require_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fail(f"{name} is not an integer at least {minimum}")
    return value


def _read_plain_file(path: Path, name: str, *, maximum: int = 134_217_728) -> bytes:
    try:
        path_metadata = path.lstat()
    except OSError as error:
        raise ProtocolError(f"{name} is unavailable") from error
    if not stat.S_ISREG(path_metadata.st_mode) or stat.S_ISLNK(path_metadata.st_mode):
        _fail(f"{name} is not a plain file")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != path_metadata.st_dev
            or opened.st_ino != path_metadata.st_ino
        ):
            _fail(f"{name} identity changed while opening")
        if opened.st_size > maximum:
            _fail(f"{name} exceeds its byte limit")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, min(1 << 20, maximum + 1)):
            chunks.append(chunk)
            if sum(map(len, chunks)) > maximum:
                _fail(f"{name} grew beyond its byte limit")
        final = os.fstat(descriptor)
        data = b"".join(chunks)
        if (
            final.st_dev != opened.st_dev
            or final.st_ino != opened.st_ino
            or final.st_size != opened.st_size
            or len(data) != opened.st_size
        ):
            _fail(f"{name} changed while reading")
        return data
    except OSError as error:
        raise ProtocolError(f"{name} cannot be read") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _plain_directory(
    path: Path,
    name: str,
    *,
    mode: int | None = None,
    owner: bool = False,
    empty: bool = False,
) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ProtocolError(f"{name} is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        _fail(f"{name} is not a plain directory")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        _fail(f"{name} does not have mode {mode:04o}")
    if owner and hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        _fail(f"{name} is not owned by the invoking uid")
    if empty and any(path.iterdir()):
        _fail(f"{name} is not empty")
    return metadata


def _assert_absent(path: Path, name: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise ProtocolError(f"cannot establish absence of {name}") from error
    _fail(f"{name} already exists")


def _no_symlink_ancestors(path: Path, name: str) -> None:
    if not path.is_absolute():
        _fail(f"{name} is not absolute")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except OSError as error:
            raise ProtocolError(f"{name} ancestor is unavailable: {current}") from error
        if stat.S_ISLNK(metadata.st_mode):
            _fail(f"{name} has a symlink ancestor: {current}")


def _sha256_file(path: Path, name: str) -> str:
    data = _read_plain_file(path, name)
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()


@dataclass(slots=True)
class _CommandLedger:
    entries: list[dict[str, object]]

    def __init__(self) -> None:
        self.entries = []

    def record(
        self,
        *,
        attempt_index: int | None,
        label: str | None,
        phase: str,
        cwd: Path,
        argv: Sequence[str],
        stdin_bytes: bytes,
        started: bool,
        exit_code: int | None,
        outcome: str,
        timed_out: bool,
        duration_milliseconds: int,
        stdout: bytes,
        stderr: bytes,
        child_cleanup_passes: bool | None,
    ) -> None:
        argv_list = list(argv)
        record: dict[str, object] = {
            "sequence_index": len(self.entries),
            "attempt_index": attempt_index,
            "label": label,
            "phase": phase,
            "cwd": os.path.abspath(cwd),
            "argv": argv_list,
            "argv_sha256": canonical_sha256(argv_list),
            "stdin_size_bytes": len(stdin_bytes),
            "stdin_sha256": hashlib.sha256(stdin_bytes).hexdigest(),
            "started": started,
            "exit_code": exit_code,
            "outcome": outcome,
            "timed_out": timed_out,
            "duration_milliseconds": duration_milliseconds,
            "stdout_size_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_size_bytes": len(stderr),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "child_cleanup_passes": child_cleanup_passes,
        }
        _require_keys(record, _COMMAND_LEDGER_KEYS, "constructed command-ledger record")
        self.entries.append(record)

    def digest(self) -> str:
        return canonical_sha256(self.entries)


def _command_environment() -> dict[str, str]:
    return dict(_PREPARATION_COMMAND_ENVIRONMENT)


class _FatalPreparationError(ProtocolError):
    """An internal capture failure for which no canonical receipt can be emitted."""


class _ChildCleanupFailure(ProtocolError):
    """A child group survived; its staging tree must not be adopted or removed."""


def _process_group_exists(process_group: int) -> bool:
    killpg: Any = getattr(os, "killpg", None)
    if killpg is None:
        _fail("POSIX process-group signaling is unavailable")
    try:
        killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_empty(
    process: subprocess.Popen[bytes],
    deadline_ns: int,
) -> bool:
    while True:
        process.poll()
        if not _process_group_exists(process.pid):
            process.poll()
            return True
        now = time.monotonic_ns()
        if now >= deadline_ns:
            return False
        time.sleep(min(0.01, (deadline_ns - now) / 1_000_000_000))


def _terminate_process_group(process: subprocess.Popen[bytes]) -> bool:
    cleanup_start = time.monotonic_ns()
    term_deadline = cleanup_start + _PREPARATION_TERM_GRACE_SECONDS * 1_000_000_000
    kill_deadline = (
        cleanup_start
        + (_PREPARATION_TERM_GRACE_SECONDS + _PREPARATION_KILL_GRACE_SECONDS)
        * 1_000_000_000
    )
    if not _process_group_exists(process.pid):
        process.poll()
        return True
    killpg: Any = getattr(os, "killpg", None)
    if killpg is None:
        _fail("POSIX process-group signaling is unavailable")
    try:
        killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.poll()
        return True
    if _wait_for_process_group_empty(process, term_deadline):
        return True
    try:
        killpg(process.pid, getattr(signal, "SIGKILL", 9))
    except ProcessLookupError:
        process.poll()
        return True
    return _wait_for_process_group_empty(process, kill_deadline)


@dataclass(slots=True)
class _StreamCapture:
    data: bytearray
    overflow: bool = False
    error: BaseException | None = None


def _capture_stream(
    stream: Any,
    cap: int,
    capture: _StreamCapture,
    overflow_event: threading.Event,
) -> None:
    try:
        while len(capture.data) < cap + 1:
            chunk = stream.read(min(65_536, cap + 1 - len(capture.data)))
            if not chunk:
                break
            capture.data.extend(chunk)
        if len(capture.data) == cap + 1:
            capture.overflow = True
            overflow_event.set()
    except BaseException as error:  # recorded and converted to a fatal no-receipt failure
        capture.error = error
        overflow_event.set()
    finally:
        with suppress(OSError):
            stream.close()


def _run_command(
    ledger: _CommandLedger,
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    input_bytes: bytes | None = None,
    attempt_index: int | None = None,
    label: str | None = "authority",
    phase: str = "raw_audit",
) -> bytes:
    argv_list = list(argv)
    intended_stdin = b"" if input_bytes is None else bytes(input_bytes)
    start_ns = time.monotonic_ns()
    if len(intended_stdin) > _PREPARATION_STDIN_CAP_BYTES:
        duration = (time.monotonic_ns() - start_ns) // 1_000_000
        ledger.record(
            attempt_index=attempt_index,
            label=label,
            phase=phase,
            cwd=cwd,
            argv=argv_list,
            stdin_bytes=intended_stdin,
            started=False,
            exit_code=None,
            outcome="stdin_limit",
            timed_out=False,
            duration_milliseconds=duration,
            stdout=b"",
            stderr=b"",
            child_cleanup_passes=None,
        )
        _fail(f"command stdin exceeds its registered cap: {argv_list}")

    try:
        with tempfile.TemporaryFile(mode="w+b") as stdin_file:
            stdin_file.write(intended_stdin)
            stdin_file.flush()
            stdin_file.seek(0)
            process = subprocess.Popen(
                argv_list,
                cwd=cwd,
                env=_command_environment(),
                stdin=stdin_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            child_start_ns = time.monotonic_ns()
    except OSError as error:
        duration = (time.monotonic_ns() - start_ns) // 1_000_000
        ledger.record(
            attempt_index=attempt_index,
            label=label,
            phase=phase,
            cwd=cwd,
            argv=argv_list,
            stdin_bytes=intended_stdin,
            started=False,
            exit_code=None,
            outcome="spawn_error",
            timed_out=False,
            duration_milliseconds=duration,
            stdout=b"",
            stderr=b"",
            child_cleanup_passes=None,
        )
        raise ProtocolError(f"command could not start: {argv_list[0]}") from error
    if process.stdout is None or process.stderr is None:
        raise _FatalPreparationError("command capture pipes were not created")
    stdout_capture = _StreamCapture(bytearray())
    stderr_capture = _StreamCapture(bytearray())
    overflow_event = threading.Event()
    readers = [
        threading.Thread(
            target=_capture_stream,
            args=(
                process.stdout,
                _PREPARATION_STDOUT_CAP_BYTES,
                stdout_capture,
                overflow_event,
            ),
            daemon=True,
        ),
        threading.Thread(
            target=_capture_stream,
            args=(
                process.stderr,
                _PREPARATION_STDERR_CAP_BYTES,
                stderr_capture,
                overflow_event,
            ),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    deadline_ns = child_start_ns + timeout * 1_000_000_000
    timeout_initiated = False
    forced_cleanup = False
    while process.poll() is None:
        if overflow_event.is_set():
            forced_cleanup = True
            break
        now = time.monotonic_ns()
        if now >= deadline_ns:
            timeout_initiated = True
            forced_cleanup = True
            break
        time.sleep(min(0.01, (deadline_ns - now) / 1_000_000_000))

    if process.poll() is not None and _process_group_exists(process.pid):
        forced_cleanup = True
    cleanup_passes: bool | None = None
    if forced_cleanup:
        cleanup_passes = _terminate_process_group(process)
    process.poll()
    for reader in readers:
        reader.join(timeout=1)
    if (
        cleanup_passes is None
        and (stdout_capture.overflow or stderr_capture.overflow or timeout_initiated)
    ):
        cleanup_passes = _terminate_process_group(process)
    if any(reader.is_alive() for reader in readers):
        raise _FatalPreparationError(
            "command stream capture did not finish; no receipt is safe"
        )
    stdout = bytes(stdout_capture.data)
    stderr = bytes(stderr_capture.data)
    exit_code = process.returncode
    if stdout_capture.overflow:
        outcome = "stdout_limit"
    elif stderr_capture.overflow:
        outcome = "stderr_limit"
    elif timeout_initiated:
        outcome = "timeout"
    elif exit_code == 0:
        outcome = "completed"
    else:
        outcome = "nonzero"
    duration = (time.monotonic_ns() - start_ns) // 1_000_000
    ledger.record(
        attempt_index=attempt_index,
        label=label,
        phase=phase,
        cwd=cwd,
        argv=argv_list,
        stdin_bytes=intended_stdin,
        started=True,
        exit_code=exit_code,
        outcome=outcome,
        timed_out=timeout_initiated,
        duration_milliseconds=duration,
        stdout=stdout,
        stderr=stderr,
        child_cleanup_passes=cleanup_passes,
    )
    if stdout_capture.error is not None or stderr_capture.error is not None:
        raise _FatalPreparationError("command stream capture failed; no receipt is safe")
    if cleanup_passes is False:
        raise _ChildCleanupFailure(
            f"command process group survived fixed cleanup: {argv_list}"
        )
    if outcome == "stdout_limit":
        _fail(f"command stdout exceeds its registered cap: {argv_list}")
    if outcome == "stderr_limit":
        _fail(f"command stderr exceeds its registered cap: {argv_list}")
    if outcome == "timeout":
        _fail(f"command timed out: {argv_list}")
    if outcome != "completed":
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise ProtocolError(f"command failed ({exit_code}): {argv_list}: {detail}")
    return stdout


def _git(
    ledger: _CommandLedger,
    root: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
    attempt_index: int | None = None,
    label: str | None = "authority",
    phase: str = "raw_audit",
) -> bytes:
    return _run_command(
        ledger,
        ["/usr/bin/git", "--no-replace-objects", "-C", str(root), *arguments],
        cwd=root,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
        input_bytes=input_bytes,
        attempt_index=attempt_index,
        label=label,
        phase=phase,
    )


def _parse_local_git_config(raw: bytes) -> dict[str, str]:
    records = raw.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    pairs: list[tuple[bytes, bytes]] = []
    if all(b"\n" in record for record in records):
        for record in records:
            key, value = record.split(b"\n", 1)
            pairs.append((key, value))
    else:
        if len(records) % 2:
            _fail("local Git config NUL stream has an odd field count")
        pairs = list(zip(records[0::2], records[1::2], strict=True))
    result: dict[str, str] = {}
    for key_raw, value_raw in pairs:
        try:
            decoded_key = key_raw.decode("utf-8", errors="strict")
            decoded_value = value_raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ProtocolError("local Git config is not strict UTF-8") from error
        if not decoded_key or decoded_key in result:
            _fail("local Git config contains an empty or duplicate key")
        result[decoded_key] = decoded_value
    return result


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
            raise ProtocolError(
                "local Git object-pack directory is unavailable as a no-follow directory"
            ) from error

        for descriptor in descriptors:
            try:
                metadata = os.fstat(descriptor)
            except OSError as error:
                raise ProtocolError(
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
            raise ProtocolError(
                "cannot inspect local Git object-pack directory"
            ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _validate_git_administration(root: Path) -> None:
    git_directory = root / ".git"
    _plain_directory(git_directory, "Git administration directory", owner=True)
    for relative in (
        "objects/info/alternates",
        "objects/info/http-alternates",
        "info/grafts",
        "shallow",
    ):
        _assert_absent(git_directory / relative, f"forbidden Git administration path {relative}")
    replace_root = git_directory / "refs/replace"
    try:
        metadata = replace_root.lstat()
    except FileNotFoundError:
        pass
    except OSError as error:
        raise ProtocolError("cannot inspect loose replacement refs") from error
    else:
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            _fail("loose replacement-ref root is not a plain directory")
        if any(os.scandir(replace_root)):
            _fail("loose replacement refs are forbidden")
    packed_refs = git_directory / "packed-refs"
    try:
        packed_metadata = packed_refs.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise ProtocolError("cannot inspect packed refs") from error
    if not stat.S_ISREG(packed_metadata.st_mode) or stat.S_ISLNK(packed_metadata.st_mode):
        _fail("packed-refs is not a plain file")
    packed = _read_plain_file(packed_refs, "packed refs")
    if any(
        line and not line.startswith((b"#", b"^")) and line.split(maxsplit=1)[-1].startswith(b"refs/replace/")
        for line in packed.splitlines()
    ):
        _fail("packed replacement refs are forbidden")


def _validate_git_repository_policy(
    ledger: _CommandLedger,
    root: Path,
    *,
    attempt_index: int | None = None,
    label: str | None = "authority",
) -> None:
    _validate_object_pack_sources(root)
    config_raw = _git(
        ledger,
        root,
        "config",
        "--local",
        "--null",
        "--list",
        attempt_index=attempt_index,
        label=label,
        phase="git_config",
    )
    if _parse_local_git_config(config_raw) != _LOCAL_GIT_CONFIG:
        _fail(f"local Git config differs from the closed P8v4 mapping: {root}")
    _validate_git_administration(root)


@dataclass(frozen=True, slots=True)
class _TreeEntry:
    mode: str
    path: str
    oid: str
    size: int


@dataclass(frozen=True, slots=True)
class _RawAudit:
    tree_sha256: str
    raw_sha256: str
    status_sha256: str
    entries: tuple[_TreeEntry, ...]
    blobs: Mapping[str, bytes]


@dataclass(frozen=True, slots=True)
class _Registration:
    value: Mapping[str, Any]
    raw: bytes
    content_sha256: str
    file_sha256: str
    source_manifest_sha256: str
    execution: Mapping[str, Any]


_NON_REGISTRATION_ADDITIONS: Final = (
    "docs/action_qbc_v8_open_diagnostic_runbook.md",
    "scripts/build_action_qbc_v8_open_registration.py",
    "scripts/execute_action_qbc_v8_open_lifecycle.py",
    "scripts/finalize_action_qbc_v8_open_diagnostic.py",
    "scripts/prepare_action_qbc_v8_open.py",
    "scripts/reconstruct_action_qbc_v8_open_registration.py",
    "scripts/run_action_qbc_v8_open_diagnostic.py",
    "scripts/supervise_action_qbc_v8_remote_tag.py",
    "scripts/validate_action_qbc_v8_open_payload.py",
    "scripts/verify_action_qbc_v8_remote_tag.py",
    "src/arc3_voi/action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_lifecycle.py",
    "tests/test_action_qbc_v8_registration.py",
)
_ALL_ADDITIONS: Final = tuple(sorted((*_NON_REGISTRATION_ADDITIONS, _REGISTRATION_PATH)))
_EXPECTED_LINUX_TOOLS: Final = [
    {"path": "/usr/bin/env", "version": "GNU coreutils 9.4", "sha256": "1490a663e7312c4347987b2e12d7d73950ed1e9a322449daf8e4836660396e31"},
    {"path": "/usr/bin/git", "version": "2.43.0", "sha256": "953577d782b6a4dada93cdb924a1261266c7b98aae6676e4ddeeddfc9a848e8e"},
    {"path": "/usr/bin/install", "version": "GNU coreutils 9.4", "sha256": "b4663b43190ea551f682cfac9500f3f4f6e94890d8ce8822bb81a819f15dab00"},
    {"path": "/usr/bin/python3", "version": "CPython 3.12.3", "sha256": "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118"},
    {"path": "/usr/bin/test", "version": "GNU coreutils 9.4", "sha256": "52b0ca5cef7e104ad5e0a8a29bd1522c205cc8404e46e153e5afc54605857c4d"},
    {"path": "/usr/bin/timeout", "version": "GNU coreutils 9.4", "sha256": "2ee918a5358c0388719e710134bc32cffb934f4bd2a8fb9beb86ef4d6ec8bd8a"},
    {"path": "/usr/local/bin/uv", "version": "0.11.28", "sha256": "1cb9cd0a1749debf6049d7d2bb933882cc52d81016326ee6d99a786d6c988b03"},
]


def _parse_tree(raw: bytes) -> tuple[_TreeEntry, ...]:
    entries: list[_TreeEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_raw = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 4 or fields[1] != b"blob":
            _fail("O8 tree contains a malformed or non-blob entry")
        try:
            mode = fields[0].decode("ascii")
            oid = fields[2].decode("ascii")
            size = int(fields[3])
            path = path_raw.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError) as error:
            raise ProtocolError("O8 tree entry encoding is invalid") from error
        if mode != "100644":
            _fail(f"O8 tree path is not a regular non-executable blob: {path}")
        _require_hex(oid, 40, f"O8 blob for {path}")
        if size < 0:
            _fail(f"O8 tree has a negative blob size: {path}")
        pure = PurePosixPath(path)
        if (
            not path
            or pure.is_absolute()
            or ".." in pure.parts
            or "." in pure.parts
            or "\\" in path
            or "\x00" in path
        ):
            _fail(f"O8 tree path is unsafe: {path!r}")
        entries.append(_TreeEntry(mode=mode, path=path, oid=oid, size=size))
    entries.sort(key=lambda entry: entry.path.encode("utf-8"))
    if not entries or len({entry.path for entry in entries}) != len(entries):
        _fail("O8 tree is empty or contains duplicate paths")
    return tuple(entries)


def _read_blobs(
    ledger: _CommandLedger,
    root: Path,
    entries: Sequence[_TreeEntry],
    *,
    attempt_index: int | None = None,
    label: str | None = "authority",
) -> dict[str, bytes]:
    request = b"".join(entry.oid.encode("ascii") + b"\n" for entry in entries)
    response = _git(
        ledger,
        root,
        "cat-file",
        "--batch",
        input_bytes=request,
        attempt_index=attempt_index,
        label=label,
    )
    offset = 0
    blobs: dict[str, bytes] = {}
    for entry in entries:
        newline = response.find(b"\n", offset)
        if newline < 0:
            _fail("Git cat-file batch response has a truncated header")
        fields = response[offset:newline].split()
        if len(fields) != 3 or fields[:2] != [entry.oid.encode("ascii"), b"blob"]:
            _fail(f"Git cat-file returned the wrong object for {entry.path}")
        try:
            size = int(fields[2])
        except ValueError as error:
            raise ProtocolError("Git cat-file returned a noninteger size") from error
        start = newline + 1
        end = start + size
        if end >= len(response) or response[end : end + 1] != b"\n":
            _fail(f"Git cat-file returned a truncated blob for {entry.path}")
        blob = response[start:end]
        if size != entry.size or len(blob) != entry.size:
            _fail(f"Git tree/cat-file length mismatch for {entry.path}")
        if _git_blob_sha1(blob) != entry.oid:
            _fail(f"recomputed Git SHA-1 mismatch for {entry.path}")
        hashlib.sha256(blob).hexdigest()
        blobs[entry.path] = blob
        offset = end + 1
    if offset != len(response):
        _fail("Git cat-file batch response has trailing bytes")
    return blobs


def _tracked_directories(entries: Sequence[_TreeEntry]) -> set[str]:
    result: set[str] = set()
    for entry in entries:
        parent = PurePosixPath(entry.path).parent
        while str(parent) != ".":
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def _audit_filesystem_shape(
    root: Path,
    entries: Sequence[_TreeEntry],
    *,
    allow_venv: bool,
) -> None:
    tracked_files = {entry.path for entry in entries}
    tracked_directories = _tracked_directories(entries)

    def visit(directory: Path, prefix: str = "") -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: os.fsencode(item.name))
        except OSError as error:
            raise ProtocolError(f"cannot enumerate clone directory: {directory}") from error
        for child in children:
            relative = f"{prefix}/{child.name}" if prefix else child.name
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as error:
                raise ProtocolError(f"cannot stat clone path: {relative}") from error
            if stat.S_ISLNK(metadata.st_mode):
                _fail(f"clone contains a symlink: {relative}")
            if not prefix and relative == ".git":
                if not stat.S_ISDIR(metadata.st_mode):
                    _fail("clone .git administration path is not a plain directory")
                continue
            if not prefix and relative == ".venv" and allow_venv:
                if not stat.S_ISDIR(metadata.st_mode):
                    _fail("clone .venv is not a plain directory")
                continue
            if stat.S_ISDIR(metadata.st_mode):
                if relative not in tracked_directories:
                    _fail(f"clone contains an untracked directory: {relative}")
                visit(Path(child.path), relative)
            elif stat.S_ISREG(metadata.st_mode):
                if relative not in tracked_files:
                    _fail(f"clone contains an untracked file: {relative}")
            else:
                _fail(f"clone contains a non-plain filesystem object: {relative}")

    visit(root)


def _parse_index(raw: bytes) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_raw = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[2] != b"0":
            _fail("clone index contains a malformed or non-stage-zero entry")
        try:
            mode = fields[0].decode("ascii")
            oid = fields[1].decode("ascii")
            path = path_raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ProtocolError("clone index path is not UTF-8") from error
        result.append((path, mode, oid))
    result.sort(key=lambda row: row[0].encode("utf-8"))
    return result


def _raw_tree_audit(
    ledger: _CommandLedger,
    root: Path,
    commit: str,
    *,
    allow_venv: bool,
    attempt_index: int | None = None,
    label: str | None = "authority",
) -> _RawAudit:
    _validate_git_repository_policy(
        ledger,
        root,
        attempt_index=attempt_index,
        label=label,
    )
    head = _git(
        ledger,
        root,
        "rev-parse",
        "HEAD",
        attempt_index=attempt_index,
        label=label,
    )
    if head != f"{commit}\n".encode("ascii"):
        _fail(f"clone HEAD differs from O8: {root}")
    tree_raw = _git(
        ledger,
        root,
        "ls-tree",
        "-r",
        "-l",
        "-z",
        "--full-tree",
        commit,
        attempt_index=attempt_index,
        label=label,
    )
    entries = _parse_tree(tree_raw)
    blobs = _read_blobs(
        ledger,
        root,
        entries,
        attempt_index=attempt_index,
        label=label,
    )
    expected_index = [(entry.path, entry.mode, entry.oid) for entry in entries]
    actual_index = _parse_index(
        _git(
            ledger,
            root,
            "ls-files",
            "--stage",
            "-z",
            attempt_index=attempt_index,
            label=label,
        )
    )
    if actual_index != expected_index:
        _fail(f"clone stage-zero index differs from O8 tree: {root}")
    _audit_filesystem_shape(root, entries, allow_venv=allow_venv)
    tree_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    for entry in entries:
        path = root.joinpath(*PurePosixPath(entry.path).parts)
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ProtocolError(f"tracked checkout path is absent: {entry.path}") from error
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            _fail(f"tracked checkout path is not a plain file: {entry.path}")
        if metadata.st_mode & 0o111:
            _fail(f"tracked non-executable path has executable mode bits: {entry.path}")
        actual = _read_plain_file(path, f"tracked checkout path {entry.path}")
        blob = blobs[entry.path]
        if actual != blob or len(actual) != entry.size:
            _fail(f"raw checkout bytes differ from Git blob: {entry.path}")
        if _git_blob_sha1(actual) != entry.oid:
            _fail(f"raw checkout Git SHA-1 differs: {entry.path}")
        row: dict[str, object] = {
            "mode": entry.mode,
            "path": entry.path,
            "git_blob_sha1": entry.oid,
        }
        tree_rows.append(row)
        raw_rows.append(
            {
                **row,
                "sha256": hashlib.sha256(actual).hexdigest(),
                "size_bytes": len(actual),
            }
        )
    status = _git(
        ledger,
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        attempt_index=attempt_index,
        label=label,
    )
    if status:
        _fail(f"clone has nonempty exact Git status: {root}")
    return _RawAudit(
        tree_sha256=canonical_sha256(tree_rows),
        raw_sha256=canonical_sha256(raw_rows),
        status_sha256=hashlib.sha256(status).hexdigest(),
        entries=entries,
        blobs=blobs,
    )


def _expected_name_status(paths: Sequence[str]) -> bytes:
    return b"".join(
        b"A\0" + path.encode("utf-8") + b"\0"
        for path in sorted(paths, key=lambda item: item.encode("utf-8"))
    )


def _expected_forward_reset_name_status(paths: Sequence[str], document: str) -> bytes:
    changes = [("D", path) for path in paths]
    changes.append(("A", document))
    return b"".join(
        status.encode("ascii") + b"\0" + path.encode("utf-8") + b"\0"
        for status, path in sorted(changes, key=lambda item: item[1].encode("utf-8"))
    )


def _require_direct_child(
    ledger: _CommandLedger,
    authority: Path,
    child: str,
    parent: str,
    message: str,
    *,
    attempt_index: int | None = None,
    label: str | None = "authority",
) -> None:
    """Reject roots and merges as well as commits with the wrong first parent."""

    expected = f"{child} {parent}\n".encode("ascii")
    observed = _git(
        ledger,
        authority,
        "rev-list",
        "--parents",
        "-n",
        "1",
        child,
        attempt_index=attempt_index,
        label=label,
    )
    if observed != expected:
        _fail(message)


def _derive_open_freeze(
    ledger: _CommandLedger,
    authority: Path,
) -> str:
    _validate_git_repository_policy(ledger, authority)
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}") != b"commit\n":
        _fail("O8 tag is absent or annotated")
    commit_raw = _git(ledger, authority, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}")
    try:
        commit = commit_raw.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ProtocolError("O8 tag resolution is not ASCII") from error
    _require_hex(commit, 40, "O8 commit")
    if _git(ledger, authority, "rev-parse", "HEAD") != f"{commit}\n".encode("ascii"):
        _fail("authority HEAD does not equal its lightweight O8 tag")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V1_TAG}") != b"commit\n":
        _fail("P8v1 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_PREREGISTRATION_V1_TAG}") != f"{_PREREGISTRATION_V1_COMMIT}\n".encode("ascii"):
        _fail("P8v1 tag differs from the frozen original preregistration commit")
    _require_direct_child(
        ledger,
        authority,
        _PREREGISTRATION_V1_COMMIT,
        _R7_COMMIT,
        "P8v1 is not a direct child of frozen R7",
    )
    v1_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _R7_COMMIT,
        _PREREGISTRATION_V1_COMMIT,
    )
    if v1_delta != b"A\0" + _PREREGISTRATION_V1_DOCUMENT.encode("utf-8") + b"\0":
        _fail("R7..P8v1 is not the one-document preregistration addition")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V2_TAG}") != b"commit\n":
        _fail("P8v2 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_PREREGISTRATION_V2_TAG}") != f"{_PREREGISTRATION_V2_COMMIT}\n".encode("ascii"):
        _fail("P8v2 tag differs from the frozen binding-correction commit")
    _require_direct_child(
        ledger,
        authority,
        _PREREGISTRATION_V2_COMMIT,
        _PREREGISTRATION_V1_COMMIT,
        "P8v2 is not a direct child of P8v1",
    )
    v2_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _PREREGISTRATION_V1_COMMIT,
        _PREREGISTRATION_V2_COMMIT,
    )
    if v2_delta != b"M\0" + _PREREGISTRATION_V1_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v1..P8v2 is not the one-document binding correction")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V3_TAG}") != b"commit\n":
        _fail("P8v3 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_PREREGISTRATION_V3_TAG}") != f"{_PREREGISTRATION_V3_COMMIT}\n".encode("ascii"):
        _fail("P8v3 tag differs from the frozen minimal-honest correction commit")
    _require_direct_child(
        ledger,
        authority,
        _PREREGISTRATION_V3_COMMIT,
        _PREREGISTRATION_V2_COMMIT,
        "P8v3 is not a direct child of P8v2",
    )
    v3_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _PREREGISTRATION_V2_COMMIT,
        _PREREGISTRATION_V3_COMMIT,
    )
    if v3_delta != b"A\0" + _PREREGISTRATION_V3_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v2..P8v3 is not the one-document administrative correction")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_P8V4_TAG}") != b"commit\n":
        _fail("P8v4 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_P8V4_TAG}") != f"{_P8V4_COMMIT}\n".encode("ascii"):
        _fail("P8v4 tag differs from the frozen minimal-honest correction commit")
    _require_direct_child(
        ledger,
        authority,
        _P8V4_COMMIT,
        _PREREGISTRATION_V3_COMMIT,
        "P8v4 is not a direct child of P8v3",
    )
    v4_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _PREREGISTRATION_V3_COMMIT,
        _P8V4_COMMIT,
    )
    if v4_delta != b"A\0" + _P8V4_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v3..P8v4 is not the one-document administrative correction")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_O8V1_TAG}") != b"commit\n":
        _fail("O8v1 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_O8V1_TAG}") != f"{_O8V1_COMMIT}\n".encode("ascii"):
        _fail("O8v1 tag differs from the immutable first open freeze")
    _require_direct_child(
        ledger,
        authority,
        _O8V1_COMMIT,
        _P8V4_COMMIT,
        "O8v1 is not a direct child of P8v4",
    )
    o8v1_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _P8V4_COMMIT,
        _O8V1_COMMIT,
    )
    if o8v1_delta != _expected_name_status(_ALL_ADDITIONS):
        _fail("P8v4..O8v1 is not the exact fifteen-path historical open-freeze delta")
    if _git(ledger, authority, "cat-file", "-t", f"refs/tags/{_PREREGISTRATION_TAG}") != b"commit\n":
        _fail("P8v5 tag is absent or annotated")
    if _git(ledger, authority, "rev-parse", f"refs/tags/{_PREREGISTRATION_TAG}") != f"{_PREREGISTRATION_COMMIT}\n".encode("ascii"):
        _fail("P8v5 tag differs from the frozen public-visibility recovery commit")
    _require_direct_child(
        ledger,
        authority,
        _PREREGISTRATION_COMMIT,
        _O8V1_COMMIT,
        "P8v5 is not a direct child of O8v1",
    )
    reset_delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _O8V1_COMMIT,
        _PREREGISTRATION_COMMIT,
    )
    if reset_delta != _expected_forward_reset_name_status(
        _ALL_ADDITIONS, _PREREGISTRATION_DOCUMENT
    ):
        _fail("O8v1..P8v5 is not the exact forward-reset delta")
    document_tree = _git(
        ledger,
        authority,
        "ls-tree",
        "-z",
        _PREREGISTRATION_COMMIT,
        "--",
        _PREREGISTRATION_DOCUMENT,
    )
    expected_tree = (
        f"100644 blob {_PREREGISTRATION_DOCUMENT_GIT_BLOB_SHA1}\t"
        f"{_PREREGISTRATION_DOCUMENT}\0"
    ).encode()
    if document_tree != expected_tree:
        _fail("P8v5 recovery document Git object identity is invalid")
    document_bytes = _git(
        ledger,
        authority,
        "cat-file",
        "blob",
        f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}",
    )
    if (
        len(document_bytes) != _PREREGISTRATION_DOCUMENT_BYTE_COUNT
        or hashlib.sha256(document_bytes).hexdigest() != _PREREGISTRATION_DOCUMENT_SHA256
        or _git_blob_sha1(document_bytes) != _PREREGISTRATION_DOCUMENT_GIT_BLOB_SHA1
    ):
        _fail("P8v5 recovery document raw bytes are invalid")
    _require_direct_child(
        ledger,
        authority,
        commit,
        _PREREGISTRATION_COMMIT,
        "O8v2 is not a direct child of P8v5",
    )
    delta = _git(
        ledger,
        authority,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        _PREREGISTRATION_COMMIT,
        commit,
    )
    if delta != _expected_name_status(_ALL_ADDITIONS):
        _fail("P8v5..O8v2 is not the exact fifteen-path open-freeze delta")
    return commit


def _manifest_rows(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail(f"{name} is not a nonempty array")
    result: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            _fail(f"{name}[{index}] is not an object")
        _require_keys(item, {"mode", "path", "git_blob_sha1", "sha256", "byte_count"}, f"{name}[{index}]")
        if item["mode"] != "100644" or not isinstance(item["path"], str):
            _fail(f"{name}[{index}] has an invalid mode/path")
        _require_hex(item["git_blob_sha1"], 40, f"{name}[{index}] Git blob")
        _require_hex(item["sha256"], 64, f"{name}[{index}] SHA-256")
        _require_int(item["byte_count"], f"{name}[{index}] byte_count")
        paths.append(item["path"])
        result.append(dict(item))
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")) or len(set(paths)) != len(paths):
        _fail(f"{name} is not uniquely UTF-8-path sorted")
    return result


def _remote_policy() -> dict[str, Any]:
    return {
        "max_attempts": _MAX_ATTEMPTS,
        "attempt_timeout_seconds": _ATTEMPT_TIMEOUT_SECONDS,
        "retry_delay_seconds": _RETRY_DELAY_SECONDS,
        "overall_deadline_seconds": _OVERALL_DEADLINE_SECONDS,
        "verifier_child_deadline_seconds": _VERIFIER_CHILD_DEADLINE_SECONDS,
        "supervisor_deadline_seconds": _SUPERVISOR_DEADLINE_SECONDS,
        "supervisor_receipt_reserve_seconds": _SUPERVISOR_RECEIPT_RESERVE_SECONDS,
        "stdout_cap_bytes": _STDOUT_CAP_BYTES,
        "stderr_cap_bytes": _STDERR_CAP_BYTES,
        "child_cleanup_timeout_seconds": _CHILD_CLEANUP_TIMEOUT_SECONDS,
        "windows_job_kill_on_close": True,
        "git_child_cwd": r"D:\kaggle competitions",
        "git_environment": {
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
            "COMSPEC": r"C:\Windows\System32\cmd.exe",
            "TEMP": r"C:\Users\User\AppData\Local\Temp",
            "TMP": r"C:\Users\User\AppData\Local\Temp",
            "PATH": r"C:\Users\User\anaconda3\Library\mingw64\bin;C:\Users\User\anaconda3\Library\usr\bin;C:\Users\User\anaconda3\Library\bin;C:\Windows\System32;C:\Windows",
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
            "XDG_CONFIG_HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "NUL",
            "GIT_CONFIG_COUNT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_ASKPASS": "NUL",
            "SSH_ASKPASS": "NUL",
        },
    }


def _verification_record(registration: _Registration, commit: str) -> dict[str, Any]:
    return {
        "schema_version": "action-qbc-v8-open-registration-verification-v1",
        "status": "verified",
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": registration.content_sha256,
        "registration_file_sha256": registration.file_sha256,
        "source_manifest_sha256": registration.source_manifest_sha256,
    }


def _expected_environment_argv() -> list[str]:
    return [
        "/usr/bin/env", "UV_OFFLINE=1", "/usr/local/bin/uv", "sync", "--python",
        "3.12.13", "--frozen", "--no-dev", "--offline",
    ]


def _expected_preflight_argvs() -> list[list[str]]:
    return [
        [
            "/usr/bin/git", "--no-replace-objects", "status", "--porcelain=v1", "-z",
            "--untracked-files=all",
        ],
        ["/usr/bin/git", "--no-replace-objects", "rev-parse", "HEAD"],
        [".venv/bin/python3", "--version"],
        ["/usr/local/bin/uv", "--version"],
        [
            "/usr/bin/python3", "-I", "-B", _RECONSTRUCTOR_PATH,
            "--repository-root", ".", "--registration", _REGISTRATION_PATH,
            "--verify-open-freeze",
        ],
    ]


def _expected_preparation_argv() -> list[str]:
    return [
        "/usr/bin/python3", "-I", "-B", "scripts/prepare_action_qbc_v8_open.py", "prepare",
        "--repository-root", ".", "--registration", _REGISTRATION_PATH,
        "--execution-root", _EXECUTION_ROOT, "--receipt", _PREPARATION_RECEIPT,
    ]


def _expected_arm_argv() -> list[str]:
    return [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "120s",
        "/usr/bin/python3", "-I", "-B", "scripts/prepare_action_qbc_v8_open.py", "arm",
        "--repository-root", ".", "--registration", _REGISTRATION_PATH,
        "--execution-root", _EXECUTION_ROOT,
        "--preparation-receipt", _PREPARATION_RECEIPT,
        "--preparation-verification-receipt", _PREPARATION_VERIFICATION_RECEIPT,
        "--windows-claim", _WINDOWS_CLAIM,
        "--windows-verifier-start-claim", _WINDOWS_START_CLAIM,
        "--windows-remote-receipt", _WINDOWS_REMOTE_RECEIPT,
        "--windows-supervisor-receipt", _WINDOWS_SUPERVISOR_RECEIPT,
        "--arm-receipt", _ARM_RECEIPT,
    ]


def _expected_preparation_verification_argv() -> list[str]:
    return [
        "/usr/bin/python3", "-I", "-B", _RECONSTRUCTOR_PATH,
        "--repository-root", ".", "--registration", _REGISTRATION_PATH,
        "--verify-preparation", "--preparation-receipt", _PREPARATION_RECEIPT,
        "--verification-receipt", _PREPARATION_VERIFICATION_RECEIPT,
    ]


def _validate_execution_contract(execution: Mapping[str, Any]) -> None:
    if set(execution) != _EXECUTION_KEYS:
        _fail("registration execution contract does not have exactly the P8v4 70-key schema")
    if execution.get("windows_repository_contract") != _WINDOWS_REPOSITORY_CONTRACT:
        _fail("registration Windows repository contract differs from P8v4")
    fixed_paths = {
        "execution_root": _EXECUTION_ROOT,
        "authority_root": _AUTHORITY_ROOT,
        "preparation_receipt_path": _PREPARATION_RECEIPT,
        "preparation_verification_receipt_path": _PREPARATION_VERIFICATION_RECEIPT,
        "arm_receipt_path": _ARM_RECEIPT,
        "process_a_root": f"{_EXECUTION_ROOT}/processes/process-a",
        "process_b_root": f"{_EXECUTION_ROOT}/processes/process-b",
        "process_a_output": f"{_EXECUTION_ROOT}/processes/process-a-output/open/action_qbc_v8_open_diagnostic.json",
        "process_b_output": f"{_EXECUTION_ROOT}/processes/process-b-output/open/action_qbc_v8_open_diagnostic.json",
        "remote_claim_linux_path": _WINDOWS_CLAIM,
        "remote_verifier_claim_linux_path": _WINDOWS_START_CLAIM,
        "remote_receipt_linux_path": _WINDOWS_REMOTE_RECEIPT,
        "remote_supervisor_receipt_linux_path": _WINDOWS_SUPERVISOR_RECEIPT,
    }
    for key, expected in fixed_paths.items():
        if execution.get(key) != expected:
            _fail(f"registration execution contract has the wrong {key}")
    if execution.get("environment_build_argv") != _expected_environment_argv():
        _fail("registration environment argv differs from P8")
    if execution.get("preflight_argvs") != _expected_preflight_argvs():
        _fail("registration preflight argv arrays differ from P8")
    if execution.get("preparation_argv") != _expected_preparation_argv():
        _fail("registration preparation argv differs from P8")
    if (
        execution.get("post_preparation_validation_argv")
        != _expected_preparation_verification_argv()
    ):
        _fail("registration preparation-verification argv differs from P8v4")
    if execution.get("arm_argv") != _expected_arm_argv():
        _fail("registration arm argv differs from P8")
    if execution.get("preparation_command_environment") != _PREPARATION_COMMAND_ENVIRONMENT:
        _fail("registration preparation command environment differs from P8v4")
    if execution.get("preparation_command_policy") != _PREPARATION_COMMAND_POLICY:
        _fail("registration preparation command policy differs from P8v4")
    if execution.get("remote_policy") != _remote_policy():
        _fail("registration remote policy differs from P8")
    if execution.get("linux_tool_identities") != _EXPECTED_LINUX_TOOLS:
        _fail("registration Linux tool identities differ from P8")
    if execution.get("linux_platform") != {
        "distribution": "Ubuntu",
        "release": "24.04.1 LTS",
        "codename": "noble",
        "kernel": "5.15.167.4-microsoft-standard-WSL2",
        "machine": "x86_64",
        "wsl_version": 2,
        "windows_host_launcher_identity": {
            "path": r"C:\Windows\System32\wsl.exe",
            "product_version": "10.0.26100.8737",
            "sha256": "7e9f5cee6d641481e5a942f0e08563bae9c17ee55f0aad888f9aa0be9a5d4757",
        },
    }:
        _fail("registration Linux platform differs from P8")
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, dict):
        _fail("registration argv hashes are absent")
    required_hashes = {
        "environment_build": canonical_sha256(_expected_environment_argv()),
        "preflight": canonical_sha256(_expected_preflight_argvs()),
        "preparation": canonical_sha256(_expected_preparation_argv()),
        "post_preparation_validation": canonical_sha256(
            _expected_preparation_verification_argv()
        ),
        "arm": canonical_sha256(_expected_arm_argv()),
    }
    for key, expected in required_hashes.items():
        if hashes.get(key) != expected:
            _fail(f"registration {key} argv hash differs from its exact argv")


def _load_registration(
    root: Path,
    path: Path,
    audit: _RawAudit,
    open_commit: str,
) -> _Registration:
    expected_path = root / _REGISTRATION_PATH
    if path != expected_path:
        _fail("registration argument does not name the canonical repository path")
    raw = _read_plain_file(path, "registration")
    if audit.blobs.get(_REGISTRATION_PATH) != raw:
        _fail("registration raw bytes differ from the O8 Git blob")
    value = _parse_canonical_object(raw, "registration")
    _require_keys(value, _REGISTRATION_KEYS, "registration")
    if (
        value["schema_version"] != _REGISTRATION_SCHEMA
        or value["status"] != "registered_zero_result"
        or value["treatment_id"] != _TREATMENT_ID
        or value["runtime_id"] is not None
        or value["authorization"] != _AUTHORIZATION
    ):
        _fail("registration fixed identity is invalid")
    content_preimage = {key: item for key, item in value.items() if key != "content_sha256"}
    content_sha = canonical_sha256(content_preimage)
    if value["content_sha256"] != content_sha:
        _fail("registration content SHA-256 does not bind its other eighteen keys")
    preregistration = value.get("preregistration")
    if not isinstance(preregistration, dict):
        _fail("registration preregistration anchor is invalid")
    if (
        preregistration.get("commit_sha") != _PREREGISTRATION_COMMIT
        or preregistration.get("tag") != _PREREGISTRATION_TAG
        or preregistration.get("document_path") != _PREREGISTRATION_DOCUMENT
        or preregistration.get("document_git_blob_sha1")
        != _PREREGISTRATION_DOCUMENT_GIT_BLOB_SHA1
        or preregistration.get("document_sha256") != _PREREGISTRATION_DOCUMENT_SHA256
    ):
        _fail("registration P8 anchor differs from the frozen boundary")
    source_manifest = value.get("source_manifest")
    if not isinstance(source_manifest, dict):
        _fail("registration source manifest is invalid")
    _require_keys(
        source_manifest,
        {"preregistration_tree", "open_freeze_added_files", "manifest_sha256"},
        "registration source manifest",
    )
    prereg_rows = _manifest_rows(source_manifest["preregistration_tree"], "preregistration tree")
    addition_rows = _manifest_rows(source_manifest["open_freeze_added_files"], "open-freeze additions")
    manifest_preimage = {
        "preregistration_tree": prereg_rows,
        "open_freeze_added_files": addition_rows,
    }
    source_manifest_sha = canonical_sha256(manifest_preimage)
    if source_manifest["manifest_sha256"] != source_manifest_sha:
        _fail("registration source-manifest SHA-256 is invalid")
    if [row["path"] for row in addition_rows] != list(_NON_REGISTRATION_ADDITIONS):
        _fail("registration open-freeze addition manifest has the wrong paths")

    row_by_path = {row["path"]: row for row in [*prereg_rows, *addition_rows]}
    if set(row_by_path) != {entry.path for entry in audit.entries} - {_REGISTRATION_PATH}:
        _fail("registration source manifest does not cover exactly the non-registration O8 tree")
    for entry in audit.entries:
        blob = audit.blobs[entry.path]
        if entry.path == _REGISTRATION_PATH:
            expected_row = {
                "mode": "100644",
                "path": _REGISTRATION_PATH,
                "git_blob_sha1": _git_blob_sha1(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        else:
            expected_row = row_by_path[entry.path]
        observed_row = {
            "mode": entry.mode,
            "path": entry.path,
            "git_blob_sha1": entry.oid,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "byte_count": len(blob),
        }
        if observed_row != expected_row:
            _fail(f"registration source manifest differs from O8 object: {entry.path}")

    execution = value.get("execution_contract")
    if not isinstance(execution, dict):
        _fail("registration execution contract is invalid")
    _validate_execution_contract(execution)
    registration = _Registration(
        value=value,
        raw=raw,
        content_sha256=content_sha,
        file_sha256=hashlib.sha256(raw).hexdigest(),
        source_manifest_sha256=source_manifest_sha,
        execution=execution,
    )
    expected_record = canonical_json_bytes(_verification_record(registration, open_commit)) + b"\n"
    if not expected_record.endswith(b"\n"):
        _fail("internal verification-record construction failed")
    return registration


def _validate_linux_host(registration: _Registration) -> None:
    if os.name != "posix" or platform.system() != "Linux" or platform.machine() != "x86_64":
        _fail("preparation requires registered Linux x86_64")
    linux = registration.execution["linux_platform"]
    if not isinstance(linux, dict) or platform.release() != linux["kernel"]:
        _fail("Linux kernel differs from the registered WSL identity")
    try:
        os_release = {}
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, separator, raw_value = line.partition("=")
            if separator:
                os_release[key] = raw_value.strip().strip('"')
    except OSError as error:
        raise ProtocolError("cannot read /etc/os-release") from error
    if (
        os_release.get("ID") != "ubuntu"
        or os_release.get("VERSION_ID") != "24.04"
        or os_release.get("VERSION") != "24.04.1 LTS (Noble Numbat)"
        or os_release.get("VERSION_CODENAME") != "noble"
    ):
        _fail("Linux distribution differs from registered Ubuntu noble")
    for tool in _EXPECTED_LINUX_TOOLS:
        path = Path(tool["path"])
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise ProtocolError(f"registered Linux tool is unavailable: {path}") from error
        if hashlib.sha256(_read_plain_file(resolved, f"Linux tool {path}")).hexdigest() != tool["sha256"]:
            _fail(f"registered Linux tool SHA-256 mismatch: {path}")


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _strict_utf8(value: str, name: str) -> bytes:
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ProtocolError(f"{name} is not strict UTF-8") from error
    if not value or "\x00" in value:
        _fail(f"{name} is empty or contains NUL")
    return encoded


def _open_relative_regular_nofollow(
    root_descriptor: int,
    parts: Sequence[str],
    name: str,
) -> tuple[int, os.stat_result]:
    if not parts:
        _fail(f"{name} has an empty relative path")
    current = os.dup(root_descriptor)
    try:
        for component in parts[:-1]:
            if component in {"", ".", ".."} or "/" in component or "\\" in component:
                _fail(f"{name} has an unsafe path component")
            child = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current,
            )
            os.close(current)
            current = child
        final_name = parts[-1]
        if final_name in {"", ".", ".."} or "/" in final_name or "\\" in final_name:
            _fail(f"{name} has an unsafe final component")
        descriptor = os.open(
            final_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current,
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            os.close(descriptor)
            _fail(f"{name} is not a regular file")
        return descriptor, metadata
    except OSError as error:
        raise ProtocolError(f"{name} cannot be opened component-wise without symlinks") from error
    finally:
        os.close(current)


def _read_open_regular(
    descriptor: int,
    initial: os.stat_result,
    name: str,
    *,
    maximum: int = 134_217_728,
) -> bytes:
    if initial.st_size > maximum:
        _fail(f"{name} exceeds its byte limit")
    chunks: list[bytes] = []
    total = 0
    try:
        while chunk := os.read(descriptor, min(1 << 20, maximum + 1 - total)):
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                _fail(f"{name} grew beyond its byte limit")
        final = os.fstat(descriptor)
    except OSError as error:
        raise ProtocolError(f"{name} cannot be read") from error
    identity_fields = (
        "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_size", "st_mtime_ns",
        "st_ctime_ns",
    )
    if any(getattr(final, field) != getattr(initial, field) for field in identity_fields):
        _fail(f"{name} changed while reading")
    data = b"".join(chunks)
    if len(data) != initial.st_size:
        _fail(f"{name} byte count differs from its stable size")
    return data


def _environment_inventory(root: Path) -> tuple[list[dict[str, object]], str]:
    venv = root / ".venv"
    _plain_directory(venv, "offline virtual environment")
    site_packages = venv / "lib/python3.12/site-packages"
    _plain_directory(site_packages, "offline site-packages")
    venv_descriptor = os.open(
        venv,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        dist_infos: list[Path] = []
        for entry in os.scandir(site_packages):
            _strict_utf8(entry.name, "distribution metadata entry name")
            if entry.name.endswith(".dist-info"):
                dist_infos.append(Path(entry.path))
        dist_infos.sort(key=lambda path: _strict_utf8(path.name, "distribution metadata name"))
    except OSError as error:
        os.close(venv_descriptor)
        raise ProtocolError("cannot enumerate offline distributions") from error
    inventory: list[dict[str, object]] = []
    observed_names: set[str] = set()
    observed_paths: set[str] = set()
    try:
        for dist_info in dist_infos:
            _plain_directory(dist_info, f"distribution metadata {dist_info.name}")
            metadata_relative = f"lib/python3.12/site-packages/{dist_info.name}/METADATA"
            metadata_descriptor, metadata_stat = _open_relative_regular_nofollow(
                venv_descriptor,
                PurePosixPath(metadata_relative).parts,
                f"{dist_info.name}/METADATA",
            )
            try:
                metadata_raw = _read_open_regular(
                    metadata_descriptor,
                    metadata_stat,
                    f"{dist_info.name}/METADATA",
                )
            finally:
                os.close(metadata_descriptor)
            try:
                metadata = BytesParser(policy=email.policy.compat32).parsebytes(metadata_raw)
            except (TypeError, ValueError) as error:
                raise ProtocolError(f"cannot parse {dist_info.name}/METADATA") from error
            name_header = metadata.get("Name")
            version_header = metadata.get("Version")
            if not isinstance(name_header, str) or not isinstance(version_header, str):
                _fail(f"distribution metadata lacks Name/Version: {dist_info.name}")
            name = _normalize_distribution_name(name_header)
            version = version_header.strip()
            if not name or not version or any(ord(character) > 127 for character in name + version):
                _fail(f"distribution name/version is invalid: {dist_info.name}")
            if name in observed_names:
                _fail(f"duplicate installed distribution: {name}")
            observed_names.add(name)
            record_relative = f"lib/python3.12/site-packages/{dist_info.name}/RECORD"
            record_descriptor, record_stat = _open_relative_regular_nofollow(
                venv_descriptor,
                PurePosixPath(record_relative).parts,
                f"{dist_info.name}/RECORD",
            )
            try:
                record_raw = _read_open_regular(
                    record_descriptor,
                    record_stat,
                    f"{dist_info.name}/RECORD",
                )
            finally:
                os.close(record_descriptor)
            try:
                record_text = record_raw.decode("utf-8", errors="strict")
                rows = list(csv.reader(io.StringIO(record_text, newline="")))
            except (UnicodeDecodeError, csv.Error) as error:
                raise ProtocolError(f"cannot parse {dist_info.name}/RECORD") from error
            file_records: list[dict[str, object]] = []
            for index, row in enumerate(rows):
                if len(row) != 3 or not row[0]:
                    _fail(f"invalid RECORD row {index} for {dist_info.name}")
                raw_name = row[0]
                _strict_utf8(raw_name, f"RECORD path for {dist_info.name}")
                if "\\" in raw_name or PurePosixPath(raw_name).is_absolute():
                    _fail(f"noncanonical RECORD filename for {dist_info.name}: {raw_name!r}")
                normalized = posixpath.normpath(
                    posixpath.join("lib/python3.12/site-packages", raw_name)
                )
                pure = PurePosixPath(normalized)
                if (
                    pure.is_absolute()
                    or not pure.parts
                    or any(part in {"", ".", ".."} for part in pure.parts)
                    or normalized.startswith("../")
                ):
                    _fail(f"RECORD path escapes .venv: {raw_name!r}")
                stored_path = pure.as_posix()
                if stored_path in observed_paths:
                    _fail(f"duplicate normalized RECORD path: {stored_path}")
                observed_paths.add(stored_path)
                descriptor, candidate_metadata = _open_relative_regular_nofollow(
                    venv_descriptor,
                    pure.parts,
                    f"RECORD path {raw_name}",
                )
                try:
                    data = _read_open_regular(
                        descriptor,
                        candidate_metadata,
                        f"RECORD path {raw_name}",
                    )
                finally:
                    os.close(descriptor)
                file_records.append(
                    {
                        "path": stored_path,
                        "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
            file_records.sort(key=lambda row: _strict_utf8(str(row["path"]), "RECORD path"))
            inventory.append(
                {
                    "normalized_name": name,
                    "version": version,
                    "file_count": len(file_records),
                    "files_sha256": canonical_sha256(file_records),
                }
            )
    finally:
        os.close(venv_descriptor)
    inventory.sort(
        key=lambda row: _strict_utf8(str(row["normalized_name"]), "distribution name")
    )
    expected = {
        "arc3-crosslevel-voi": "0.1.0",
        "numpy": "2.5.1",
        "pyyaml": "6.0.3",
    }
    if {str(row["normalized_name"]): row["version"] for row in inventory} != expected:
        _fail("offline environment contains distributions outside the frozen runtime lock")
    return inventory, canonical_sha256(inventory)


def _hash_open_regular(descriptor: int, initial: os.stat_result, name: str) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        while chunk := os.read(descriptor, 1 << 20):
            digest.update(chunk)
            total += len(chunk)
        final = os.fstat(descriptor)
    except OSError as error:
        raise ProtocolError(f"{name} cannot be hashed") from error
    identity_fields = (
        "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_size", "st_mtime_ns",
        "st_ctime_ns",
    )
    if (
        total != initial.st_size
        or any(getattr(final, field) != getattr(initial, field) for field in identity_fields)
    ):
        _fail(f"{name} changed while hashing")
    return digest.hexdigest()


def _venv_materialization_sha256(root: Path) -> str:
    venv = root / ".venv"
    _plain_directory(venv, "offline virtual environment")
    root_descriptor = os.open(
        venv,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    rows: list[dict[str, object]] = []

    def visit(directory_descriptor: int, prefix: str = "") -> None:
        try:
            names = os.listdir(directory_descriptor)
        except OSError as error:
            raise ProtocolError("cannot enumerate virtual environment") from error
        names.sort(key=lambda item: _strict_utf8(item, "virtual-environment entry name"))
        for entry_name in names:
            _strict_utf8(entry_name, "virtual-environment entry name")
            if entry_name in {".", ".."} or "/" in entry_name or "\\" in entry_name:
                _fail("virtual-environment entry name is unsafe")
            relative = f"{prefix}/{entry_name}" if prefix else entry_name
            try:
                metadata = os.stat(entry_name, dir_fd=directory_descriptor, follow_symlinks=False)
            except OSError as error:
                raise ProtocolError(f"cannot stat virtual-environment entry: {relative}") from error
            common: dict[str, object] = {
                "path": relative,
                "type": None,
                "mode": stat.S_IMODE(metadata.st_mode),
                "size_bytes": None,
                "sha256": None,
                "symlink_target": None,
            }
            if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                common["type"] = "directory"
                rows.append(common)
                child_descriptor = os.open(
                    entry_name,
                    os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    visit(child_descriptor, relative)
                finally:
                    os.close(child_descriptor)
            elif stat.S_ISREG(metadata.st_mode):
                descriptor = os.open(
                    entry_name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    opened = os.fstat(descriptor)
                    if opened.st_dev != metadata.st_dev or opened.st_ino != metadata.st_ino:
                        _fail(f"virtual-environment entry changed while opening: {relative}")
                    common["type"] = "regular"
                    common["size_bytes"] = opened.st_size
                    common["sha256"] = _hash_open_regular(
                        descriptor,
                        opened,
                        f"virtual-environment file {relative}",
                    )
                finally:
                    os.close(descriptor)
                rows.append(common)
            elif stat.S_ISLNK(metadata.st_mode):
                try:
                    target = os.readlink(entry_name, dir_fd=directory_descriptor)
                except OSError as error:
                    raise ProtocolError(f"cannot read virtual-environment link: {relative}") from error
                _strict_utf8(target, f"virtual-environment link target {relative}")
                common["type"] = "symlink"
                common["symlink_target"] = target
                rows.append(common)
            else:
                _fail(f"virtual environment contains a special entry: {relative}")

    try:
        visit(root_descriptor)
    finally:
        os.close(root_descriptor)
    rows.sort(key=lambda row: _strict_utf8(str(row["path"]), "virtual-environment path"))
    if len({str(row["path"]) for row in rows}) != len(rows):
        _fail("virtual-environment inventory contains duplicate paths")
    return canonical_sha256(rows)


def _venv_python_sha256(root: Path) -> str:
    current = Path(os.path.abspath(root / ".venv/bin/python3"))
    visited: set[str] = set()
    for _ in range(41):
        identity = os.fspath(current)
        if identity in visited:
            _fail("virtual-environment Python link chain contains a cycle")
        visited.add(identity)
        try:
            metadata = current.lstat()
        except OSError as error:
            raise ProtocolError("virtual-environment Python link chain is unavailable") from error
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(current)
            except OSError as error:
                raise ProtocolError("cannot read virtual-environment Python link") from error
            _strict_utf8(target, "virtual-environment Python link target")
            next_path = Path(target) if os.path.isabs(target) else current.parent / target
            current = Path(os.path.abspath(next_path))
            continue
        if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o111:
            _fail("resolved virtual-environment Python is not a regular executable")
        return _sha256_file(current, "resolved virtual-environment Python")
    _fail("virtual-environment Python link chain exceeds forty links")


def _directory_identity(path: Path, name: str) -> tuple[int, int, int, int]:
    metadata = _plain_directory(path, name, owner=True)
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        opened.st_dev != metadata.st_dev
        or opened.st_ino != metadata.st_ino
        or opened.st_uid != metadata.st_uid
        or opened.st_mode != metadata.st_mode
    ):
        _fail(f"{name} changed while opening")
    return opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode)


def _run_preflight(
    ledger: _CommandLedger,
    root: Path,
    registration: _Registration,
    open_commit: str,
    *,
    attempt_index: int | None,
    label: str,
) -> str:
    expected_outputs = [
        b"",
        f"{open_commit}\n".encode("ascii"),
        b"Python 3.12.13\n",
        _UV_VERSION_STDOUT,
        canonical_json_bytes(_verification_record(registration, open_commit)) + b"\n",
    ]
    outputs: list[bytes] = []
    for argv in _expected_preflight_argvs():
        outputs.append(
            _run_command(
                ledger,
                argv,
                cwd=root,
                timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
                attempt_index=attempt_index,
                label=label,
                phase="preflight",
            )
        )
    if outputs != expected_outputs:
        _fail(f"offline preflight stdout differs from P8 in {root}")
    return hashlib.sha256(outputs[0]).hexdigest()


@dataclass(frozen=True, slots=True)
class _OwnedStage:
    path: Path
    device: int
    inode: int
    uid: int
    marker_bytes: bytes


class _StageCreationFailure(ProtocolError):
    """Staging exists with known identity but marker creation did not complete."""

    def __init__(self, message: str, owned: _OwnedStage) -> None:
        super().__init__(message)
        self.owned = owned


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            _fail("exclusive file write made no progress")
        offset += written


def _create_owned_stage(path: Path, attempt_index: int) -> _OwnedStage:
    _assert_absent(path, f"preparation attempt {attempt_index} staging parent")
    os.mkdir(path, 0o700)
    metadata = _plain_directory(path, "preparation staging parent", mode=0o700, owner=True)
    marker_object = {
        "schema_version": _OWNER_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "attempt_index": attempt_index,
        "path": str(path),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
    }
    marker_bytes = canonical_json_bytes(marker_object)
    owned = _OwnedStage(
        path=path,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        uid=metadata.st_uid,
        marker_bytes=marker_bytes,
    )
    marker = path / ".owner"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(marker, flags, 0o600)
        try:
            _write_all(descriptor, marker_bytes)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if _read_plain_file(marker, "preparation owner marker") != marker_bytes:
            _fail("preparation owner marker did not round-trip")
    except (ProtocolError, OSError) as error:
        raise _StageCreationFailure("preparation owner marker creation failed", owned) from error
    return owned


def _create_stage_children(owned: _OwnedStage) -> None:
    descriptor = _validate_owned_stage(owned)
    os.close(descriptor)
    for child in ("process-a", "process-b", "process-a-output", "process-b-output"):
        os.mkdir(owned.path / child, 0o700)
    os.mkdir(owned.path / "process-a-output/open", 0o700)
    os.mkdir(owned.path / "process-b-output/open", 0o700)
    for child in ("process-a", "process-b", "process-a-output/open", "process-b-output/open"):
        _plain_directory(
            owned.path / child,
            f"staging {child}",
            mode=0o700,
            owner=True,
            empty=True,
        )
    for child in ("process-a-output", "process-b-output"):
        _plain_directory(
            owned.path / child,
            f"staging {child}",
            mode=0o700,
            owner=True,
        )
    _fsync_directory(owned.path)


def _validate_owned_stage(owned: _OwnedStage, *, require_marker: bool = True) -> int:
    metadata = _plain_directory(
        owned.path,
        "owned preparation staging parent",
        mode=0o700,
        owner=True,
    )
    if (
        metadata.st_dev != owned.device
        or metadata.st_ino != owned.inode
        or metadata.st_uid != owned.uid
    ):
        _fail("preparation staging parent identity changed")
    descriptor = os.open(
        owned.path,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    opened = os.fstat(descriptor)
    if opened.st_dev != owned.device or opened.st_ino != owned.inode:
        os.close(descriptor)
        _fail("opened preparation staging parent identity changed")
    if require_marker:
        try:
            marker_descriptor = os.open(
                ".owner",
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
        except OSError as error:
            os.close(descriptor)
            raise ProtocolError("owned preparation marker is unavailable") from error
        try:
            marker_metadata = os.fstat(marker_descriptor)
            marker_bytes = b""
            while chunk := os.read(marker_descriptor, 65_536):
                marker_bytes += chunk
        finally:
            os.close(marker_descriptor)
        if not stat.S_ISREG(marker_metadata.st_mode) or marker_bytes != owned.marker_bytes:
            os.close(descriptor)
            _fail("owned preparation marker identity changed")
    return descriptor


def _remove_tree_contents(descriptor: int) -> None:
    for name in os.listdir(descriptor):
        metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            try:
                _remove_tree_contents(child)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=descriptor)
        else:
            os.unlink(name, dir_fd=descriptor)


def _cleanup_owned_stage(owned: _OwnedStage) -> bool:
    descriptor = _validate_owned_stage(owned)
    try:
        _remove_tree_contents(descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.rmdir(owned.path)
    try:
        owned.path.lstat()
    except FileNotFoundError:
        _fsync_directory(owned.path.parent)
        return True
    return False


def _remove_owner_marker(owned: _OwnedStage) -> None:
    descriptor = _validate_owned_stage(owned)
    try:
        os.unlink(".owner", dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _restore_owner_marker(owned: _OwnedStage) -> None:
    descriptor = _validate_owned_stage(owned, require_marker=False)
    marker_descriptor: int | None = None
    try:
        marker_descriptor = os.open(
            ".owner",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=descriptor,
        )
        _write_all(marker_descriptor, owned.marker_bytes)
        os.fsync(marker_descriptor)
        os.fsync(descriptor)
    finally:
        if marker_descriptor is not None:
            os.close(marker_descriptor)
        os.close(descriptor)


def _rename_noreplace(source: Path, destination: Path) -> None:
    if source.parent != destination.parent:
        _fail("atomic promotion paths do not share a parent")
    if source.name in {"", ".", ".."} or destination.name in {"", ".", ".."}:
        _fail("atomic promotion basenames are unsafe")
    parent_metadata = _plain_directory(
        source.parent,
        "atomic promotion parent",
        owner=True,
    )
    parent_descriptor = os.open(
        source.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        os.close(parent_descriptor)
        _fail("Linux renameat2 is unavailable for exclusive atomic promotion")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    try:
        opened_parent = os.fstat(parent_descriptor)
        if (
            opened_parent.st_dev != parent_metadata.st_dev
            or opened_parent.st_ino != parent_metadata.st_ino
        ):
            _fail("atomic promotion parent changed while opening")
        result = renameat2(
            parent_descriptor,
            os.fsencode(source.name),
            parent_descriptor,
            os.fsencode(destination.name),
            1,
        )
        if result != 0:
            error_number = ctypes.get_errno()
            raise ProtocolError(
                f"exclusive same-device atomic promotion failed: {os.strerror(error_number)}"
            )
        final_parent = os.fstat(parent_descriptor)
        if (
            final_parent.st_dev != opened_parent.st_dev
            or final_parent.st_ino != opened_parent.st_ino
            or final_parent.st_uid != opened_parent.st_uid
            or stat.S_IMODE(final_parent.st_mode) != stat.S_IMODE(opened_parent.st_mode)
        ):
            _fail("atomic promotion parent identity changed")
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def _read_regular_at(
    parent_descriptor: int,
    basename: str,
    name: str,
    *,
    maximum: int,
) -> tuple[bytes, os.stat_result]:
    try:
        descriptor = os.open(
            basename,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_descriptor,
        )
    except OSError as error:
        raise ProtocolError(f"{name} cannot be opened from its parent descriptor") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            _fail(f"{name} is not a regular file")
        return _read_open_regular(descriptor, metadata, name, maximum=maximum), metadata
    finally:
        os.close(descriptor)


def _publish_bytes_exclusive(path: Path, data: bytes, name: str) -> None:
    parent = path.parent
    parent_metadata = _plain_directory(parent, f"{name} parent", owner=True)
    if path.name in {"", ".", ".."} or "/" in path.name or "\\" in path.name:
        _fail(f"{name} destination basename is unsafe")
    stage_name = f".{path.name}.{name}-stage-{os.getpid()}"
    parent_descriptor = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    descriptor: int | None = None
    stage_identity: tuple[int, int] | None = None
    try:
        opened_parent = os.fstat(parent_descriptor)
        if (
            opened_parent.st_dev != parent_metadata.st_dev
            or opened_parent.st_ino != parent_metadata.st_ino
        ):
            _fail(f"{name} parent identity changed while opening")
        for basename, description in ((path.name, name), (stage_name, f"{name} staging file")):
            try:
                os.stat(basename, dir_fd=parent_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise ProtocolError(f"cannot establish absence of {description}") from error
            else:
                _fail(f"{description} already exists")
        descriptor = os.open(
            stage_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        metadata = os.fstat(descriptor)
        stage_identity = (metadata.st_dev, metadata.st_ino)
        _write_all(descriptor, data)
        os.fsync(descriptor)
        fchmod: Any = getattr(os, "fchmod", None)
        if fchmod is None:
            _fail("POSIX descriptor chmod is unavailable")
        fchmod(descriptor, 0o444)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        staged, staged_metadata = _read_regular_at(
            parent_descriptor,
            stage_name,
            f"{name} staged bytes",
            maximum=max(len(data), 1),
        )
        if (
            staged != data
            or (staged_metadata.st_dev, staged_metadata.st_ino) != stage_identity
            or stat.S_IMODE(staged_metadata.st_mode) != 0o444
            or staged_metadata.st_uid != opened_parent.st_uid
        ):
            _fail(f"{name} staged bytes did not round-trip")
        os.link(
            stage_name,
            path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        os.fsync(parent_descriptor)
        published, published_metadata = _read_regular_at(
            parent_descriptor,
            path.name,
            name,
            maximum=max(len(data), 1),
        )
        if (
            published != data
            or (published_metadata.st_dev, published_metadata.st_ino) != stage_identity
            or published_metadata.st_nlink != 2
            or stat.S_IMODE(published_metadata.st_mode) != 0o444
            or published_metadata.st_uid != opened_parent.st_uid
        ):
            _fail(f"{name} destination bytes did not round-trip")
        os.unlink(stage_name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
        final, final_metadata = _read_regular_at(
            parent_descriptor,
            path.name,
            name,
            maximum=max(len(data), 1),
        )
        if (
            final != data
            or final_metadata.st_nlink != 1
            or stat.S_IMODE(final_metadata.st_mode) != 0o444
            or final_metadata.st_uid != opened_parent.st_uid
        ):
            _fail(f"{name} final link state is invalid")
        final_parent = os.fstat(parent_descriptor)
        if (
            final_parent.st_dev != opened_parent.st_dev
            or final_parent.st_ino != opened_parent.st_ino
            or final_parent.st_uid != opened_parent.st_uid
            or stat.S_IMODE(final_parent.st_mode) != stat.S_IMODE(opened_parent.st_mode)
        ):
            _fail(f"{name} parent identity changed during publication")
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if stage_identity is not None:
            try:
                metadata = os.stat(
                    stage_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    stat.S_ISREG(metadata.st_mode)
                    and not stat.S_ISLNK(metadata.st_mode)
                    and (metadata.st_dev, metadata.st_ino) == stage_identity
                ):
                    os.unlink(stage_name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
            except FileNotFoundError:
                pass
        raise
    finally:
        os.close(parent_descriptor)


def _clone_checkout(
    ledger: _CommandLedger,
    destination: Path,
    open_commit: str,
    *,
    attempt_index: int,
    label: str,
) -> None:
    _plain_directory(destination, "empty clone destination", mode=0o700, owner=True, empty=True)
    commands: list[tuple[str, list[str]]] = [
        (
            "clone",
            [
                "/usr/bin/git", "--no-replace-objects", "clone", "--no-local",
                "--no-checkout", "--branch", _OPEN_FREEZE_TAG, "--single-branch",
                _SOURCE_URL, str(destination),
            ],
        ),
        (
            "git_config",
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(destination),
                "config", "--local", "core.autocrlf", "false",
            ],
        ),
        (
            "git_config",
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(destination),
                "config", "--local", "core.eol", "lf",
            ],
        ),
        (
            "git_config",
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(destination),
                "config", "--local", "core.safecrlf", "true",
            ],
        ),
        (
            "checkout",
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(destination),
                "checkout", "--detach", open_commit,
            ],
        ),
        (
            "git_config",
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(destination),
                "remote", "remove", "origin",
            ],
        ),
    ]
    for phase, argv in commands:
        stdout = _run_command(
            ledger,
            argv,
            cwd=destination.parent,
            timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
            attempt_index=attempt_index,
            label=label,
            phase=phase,
        )
        if stdout:
            _fail(f"clone/config/checkout command produced unexpected stdout: {argv}")
    _plain_directory(destination, "materialized clone destination", mode=0o700, owner=True)
    _validate_git_repository_policy(
        ledger,
        destination,
        attempt_index=attempt_index,
        label=label,
    )
    if _git(
        ledger,
        destination,
        "cat-file",
        "-t",
        f"refs/tags/{_OPEN_FREEZE_TAG}",
        attempt_index=attempt_index,
        label=label,
    ) != b"commit\n":
        _fail("process clone O8 tag is absent or annotated")
    if _git(
        ledger,
        destination,
        "rev-parse",
        f"refs/tags/{_OPEN_FREEZE_TAG}",
        attempt_index=attempt_index,
        label=label,
    ) != f"{open_commit}\n".encode("ascii"):
        _fail("process clone O8 tag resolves to the wrong commit")


def _clone_receipt(
    root: Path,
    open_commit: str,
    audit: _RawAudit,
    inventory: list[dict[str, object]] | None,
    inventory_sha256: str | None,
    venv_materialization_sha256: str | None,
    venv_python_sha256: str | None,
    *,
    environment: bool,
) -> dict[str, Any]:
    root_device, root_inode, root_uid, root_mode = _directory_identity(root, "clone root")
    return {
        "root": str(root),
        "root_device": root_device,
        "root_inode": root_inode,
        "root_owner_uid": root_uid,
        "root_mode": root_mode,
        "head_sha": open_commit,
        "tree_sha256": audit.tree_sha256,
        "raw_materialization_sha256": audit.raw_sha256,
        "git_status_sha256": audit.status_sha256,
        "python_version": "3.12.13" if environment else None,
        "uv_version": "0.11.28" if environment else None,
        "environment_inventory": inventory if environment else None,
        "environment_inventory_sha256": inventory_sha256 if environment else None,
        "venv_materialization_sha256": (
            venv_materialization_sha256 if environment else None
        ),
        "venv_python_sha256": venv_python_sha256 if environment else None,
        "passes": True,
    }


def _failure_attempt_record(
    attempt_index: int,
    stages: Mapping[str, str],
    source: Path,
    destination: Path,
    owned: _OwnedStage | None,
    cleanup_removed: bool,
    cleanup_passes: bool,
) -> dict[str, Any]:
    owned_paths = [str(source)] if owned is not None else []
    removed = [str(source)] if owned is not None and cleanup_removed else []
    return {
        "attempt_index": attempt_index,
        "process_a_stage": stages["a"],
        "process_b_stage": stages["b"],
        "cleanup": {
            "owned_paths": sorted(owned_paths),
            "removed": sorted(removed),
            "passes": cleanup_passes,
        },
        "promotion": {
            "source_path": str(source),
            "destination_path": str(destination),
            "source_device": owned.device if owned is not None else None,
            "source_inode": owned.inode if owned is not None else None,
            "passes": False,
        },
        "passes": False,
    }


@dataclass(frozen=True, slots=True)
class _AttemptOutcome:
    record: Mapping[str, Any]
    process_a: Mapping[str, Any] | None
    process_b: Mapping[str, Any] | None
    cleanup_passes: bool
    error: str | None


def _prepare_attempt(
    ledger: _CommandLedger,
    execution_root: Path,
    attempt_index: int,
    registration: _Registration,
    open_commit: str,
    authority_audit: _RawAudit,
) -> _AttemptOutcome:
    source = execution_root / f".prepare-attempt-{attempt_index}"
    destination = execution_root / "processes"
    stages = {"a": "not_started", "b": "not_started"}
    owned: _OwnedStage | None = None
    marker_removed = False
    promoted = False
    try:
        try:
            owned = _create_owned_stage(source, attempt_index)
        except _StageCreationFailure as error:
            owned = error.owned
            raise
        _create_stage_children(owned)
        clone_roots = {
            "a": source / "process-a",
            "b": source / "process-b",
        }
        for label in ("a", "b"):
            try:
                _clone_checkout(
                    ledger,
                    clone_roots[label],
                    open_commit,
                    attempt_index=attempt_index,
                    label=label.upper(),
                )
            except (ProtocolError, OSError):
                stages[label] = "clone_failed"
                raise

        before_audits: dict[str, _RawAudit] = {}
        for label in ("a", "b"):
            try:
                before_audits[label] = _raw_tree_audit(
                    ledger,
                    clone_roots[label],
                    open_commit,
                    allow_venv=False,
                    attempt_index=attempt_index,
                    label=label.upper(),
                )
                if (
                    before_audits[label].tree_sha256 != authority_audit.tree_sha256
                    or before_audits[label].raw_sha256 != authority_audit.raw_sha256
                ):
                    _fail(f"process {label.upper()} raw O8 audit differs from authority")
            except (ProtocolError, OSError):
                stages[label] = "raw_audit_failed"
                raise

        for label in ("a", "b"):
            try:
                output = _run_command(
                    ledger,
                    _expected_environment_argv(),
                    cwd=clone_roots[label],
                    timeout=_PREPARATION_ENVIRONMENT_TIMEOUT_SECONDS,
                    attempt_index=attempt_index,
                    label=label.upper(),
                    phase="environment_build",
                )
                if output:
                    _fail(f"offline uv environment build produced unexpected stdout for {label}")
            except (ProtocolError, OSError):
                stages[label] = "environment_failed"
                raise

        inventories: dict[str, list[dict[str, object]]] = {}
        inventory_digests: dict[str, str] = {}
        venv_materializations: dict[str, str] = {}
        venv_python_digests: dict[str, str] = {}
        after_audits: dict[str, _RawAudit] = {}
        for label in ("a", "b"):
            try:
                inventories[label], inventory_digests[label] = _environment_inventory(
                    clone_roots[label]
                )
                venv_materializations[label] = _venv_materialization_sha256(
                    clone_roots[label]
                )
                venv_python_digests[label] = _venv_python_sha256(clone_roots[label])
                after_audits[label] = _raw_tree_audit(
                    ledger,
                    clone_roots[label],
                    open_commit,
                    allow_venv=True,
                    attempt_index=attempt_index,
                    label=label.upper(),
                )
                if (
                    after_audits[label].tree_sha256 != authority_audit.tree_sha256
                    or after_audits[label].raw_sha256 != authority_audit.raw_sha256
                ):
                    _fail(f"process {label.upper()} post-environment raw audit differs from authority")
            except (ProtocolError, OSError):
                stages[label] = "raw_audit_failed"
                raise
        if venv_python_digests["a"] != venv_python_digests["b"]:
            _fail("process A/B resolved virtual-environment Python bytes differ")

        preflight_statuses: dict[str, str] = {}
        for label in ("a", "b"):
            try:
                preflight_statuses[label] = _run_preflight(
                    ledger,
                    clone_roots[label],
                    registration,
                    open_commit,
                    attempt_index=attempt_index,
                    label=label.upper(),
                )
                if preflight_statuses[label] != after_audits[label].status_sha256:
                    _fail(f"process {label.upper()} preflight status hash changed")
                stages[label] = "completed"
            except (ProtocolError, OSError):
                stages[label] = "preflight_failed"
                raise

        for label in ("a", "b"):
            final_inventory, final_inventory_sha = _environment_inventory(clone_roots[label])
            final_venv_sha = _venv_materialization_sha256(clone_roots[label])
            final_python_sha = _venv_python_sha256(clone_roots[label])
            if (
                final_inventory != inventories[label]
                or final_inventory_sha != inventory_digests[label]
                or final_venv_sha != venv_materializations[label]
                or final_python_sha != venv_python_digests[label]
            ):
                _fail(f"process {label.upper()} environment changed during preflight")

        for label in ("a", "b"):
            _plain_directory(
                source / f"process-{label}-output/open",
                f"process {label.upper()} output parent",
                mode=0o700,
                owner=True,
                empty=True,
            )
        _assert_absent(destination, "final processes root")
        parent_metadata = _plain_directory(execution_root, "execution root", mode=0o700, owner=True)
        if parent_metadata.st_dev != owned.device:
            _fail("staging parent is not on the execution-root device")
        _remove_owner_marker(owned)
        marker_removed = True
        try:
            _rename_noreplace(source, destination)
            promoted = True
        except BaseException:
            _restore_owner_marker(owned)
            marker_removed = False
            raise
        _fsync_directory(execution_root)
        promoted_metadata = _plain_directory(
            destination,
            "promoted processes",
            mode=0o700,
            owner=True,
        )
        if (
            promoted_metadata.st_dev != owned.device
            or promoted_metadata.st_ino != owned.inode
        ):
            _fail("atomic promotion did not preserve staging device/inode")
        _assert_absent(source, "promoted staging source")
        final_roots = {
            "a": destination / "process-a",
            "b": destination / "process-b",
        }
        for label in ("a", "b"):
            _plain_directory(final_roots[label], f"final process {label.upper()}", mode=0o700, owner=True)
            _plain_directory(
                destination / f"process-{label}-output/open",
                f"final process {label.upper()} output parent",
                mode=0o700,
                owner=True,
                empty=True,
            )
        process_a = _clone_receipt(
            final_roots["a"],
            open_commit,
            after_audits["a"],
            inventories["a"],
            inventory_digests["a"],
            venv_materializations["a"],
            venv_python_digests["a"],
            environment=True,
        )
        process_b = _clone_receipt(
            final_roots["b"],
            open_commit,
            after_audits["b"],
            inventories["b"],
            inventory_digests["b"],
            venv_materializations["b"],
            venv_python_digests["b"],
            environment=True,
        )
        record = {
            "attempt_index": attempt_index,
            "process_a_stage": "completed",
            "process_b_stage": "completed",
            "cleanup": {
                "owned_paths": [str(source)],
                "removed": [],
                "passes": True,
            },
            "promotion": {
                "source_path": str(source),
                "destination_path": str(destination),
                "source_device": owned.device,
                "source_inode": owned.inode,
                "passes": True,
            },
            "passes": True,
        }
        return _AttemptOutcome(record, process_a, process_b, True, None)
    except _FatalPreparationError:
        raise
    except _ChildCleanupFailure as error:
        record = _failure_attempt_record(
            attempt_index,
            stages,
            source,
            destination,
            owned,
            False,
            False,
        )
        return _AttemptOutcome(record, None, None, False, str(error))
    except (ProtocolError, OSError) as error:
        if promoted:
            raise
        cleanup_removed = False
        cleanup_passes = owned is None and not source.exists() and not source.is_symlink()
        if owned is not None:
            try:
                if marker_removed:
                    _restore_owner_marker(owned)
                    marker_removed = False
                cleanup_removed = _cleanup_owned_stage(owned)
                cleanup_passes = cleanup_removed
            except (ProtocolError, OSError):
                cleanup_passes = False
        record = _failure_attempt_record(
            attempt_index,
            stages,
            source,
            destination,
            owned,
            cleanup_removed,
            cleanup_passes,
        )
        return _AttemptOutcome(record, None, None, cleanup_passes, str(error))


def _validate_prepare_invocation(args: argparse.Namespace, registration: _Registration) -> None:
    if str(args.repository_root) != "." or str(args.registration) != _REGISTRATION_PATH:
        _fail("prepare repository/registration argv differs from the registered relative argv")
    if str(args.execution_root) != _EXECUTION_ROOT or str(args.receipt) != _PREPARATION_RECEIPT:
        _fail("prepare execution-root/receipt argv differs from P8")
    if registration.execution["preparation_argv"] != _expected_preparation_argv():
        _fail("registered preparation argv changed after registration validation")


def _validate_preparation_root(root: Path, authority: Path, receipt: Path) -> None:
    _no_symlink_ancestors(root, "execution root")
    _plain_directory(root, "execution root", mode=0o700, owner=True)
    _no_symlink_ancestors(authority, "authority root")
    _plain_directory(authority, "authority root", mode=0o700, owner=True)
    _assert_absent(receipt, "preparation receipt")
    _assert_absent(
        root / "preparation-verification.json",
        "preparation verification receipt",
    )
    _assert_absent(root / "processes", "final processes root")
    _assert_absent(root / "arm-receipt.json", "arm receipt")
    for path in (
        "remote-verification-claim.json",
        "remote-verifier-start-claim.json",
        "remote-verification.json",
        "remote-verification-supervisor.json",
        "lifecycle-driver-claim.json",
        "lifecycle-ledger.json",
        "result-git-owner.json",
        "result-git-work",
    ):
        _assert_absent(root / path, f"downstream path {path}")
    allowed = {"authority"}
    observed = {entry.name for entry in os.scandir(root)}
    if observed != allowed:
        _fail("execution root contains paths outside the sole authority clone before preparation")


def _prepare(args: argparse.Namespace) -> int:
    if os.name != "posix":
        _fail("prepare is available only in registered Linux")
    execution_root = Path(args.execution_root)
    authority = Path(_AUTHORITY_ROOT)
    receipt_path = Path(args.receipt)
    _validate_preparation_root(execution_root, authority, receipt_path)
    repository_root = Path(args.repository_root).resolve(strict=True)
    if repository_root != authority:
        _fail("prepare is not running from the registered authority clone")
    ledger = _CommandLedger()
    open_commit = _derive_open_freeze(ledger, authority)
    authority_audit = _raw_tree_audit(
        ledger,
        authority,
        open_commit,
        allow_venv=False,
    )
    registration_path = repository_root / args.registration
    registration = _load_registration(
        repository_root,
        registration_path,
        authority_audit,
        open_commit,
    )
    _validate_prepare_invocation(args, registration)
    _validate_linux_host(registration)
    authority_receipt = _clone_receipt(
        authority,
        open_commit,
        authority_audit,
        None,
        None,
        None,
        None,
        environment=False,
    )
    attempts: list[Mapping[str, Any]] = []
    process_a: Mapping[str, Any] | None = None
    process_b: Mapping[str, Any] | None = None
    errors: list[str] = []
    for attempt_index in (1, 2):
        outcome = _prepare_attempt(
            ledger,
            execution_root,
            attempt_index,
            registration,
            open_commit,
            authority_audit,
        )
        attempts.append(outcome.record)
        if outcome.error is not None:
            errors.append(f"attempt {attempt_index}: {outcome.error}")
        if outcome.process_a is not None and outcome.process_b is not None:
            process_a = outcome.process_a
            process_b = outcome.process_b
            break
        if not outcome.cleanup_passes:
            _fail(
                "preparation cleanup failed; no canonical failed receipt may be published"
            )
    prepared = process_a is not None and process_b is not None
    receipt = {
        "schema_version": _PREPARATION_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": open_commit,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": registration.content_sha256,
        "attempts": [dict(attempt) for attempt in attempts],
        "authority": authority_receipt,
        "process_a": process_a if prepared else None,
        "process_b": process_b if prepared else None,
        "command_ledger": [dict(entry) for entry in ledger.entries],
        "commands_sha256": ledger.digest(),
        "command_environment_sha256": canonical_sha256(_command_environment()),
        "status": "prepared" if prepared else "failed",
    }
    _require_keys(receipt, _PREPARATION_KEYS, "constructed preparation receipt")
    _publish_bytes_exclusive(
        receipt_path,
        canonical_json_bytes(receipt),
        "preparation-receipt",
    )
    if not prepared:
        sys.stderr.buffer.write(
            canonical_json_bytes({"errors": errors, "status": "preparation_failed"}) + b"\n"
        )
        return 1
    return 0


def _attempt_phase_plan() -> tuple[tuple[str, str], ...]:
    clone = (
        ("clone",)
        + ("git_config",) * 3
        + ("checkout",)
        + ("git_config",) * 2
        + ("raw_audit",) * 2
    )
    raw_audit = ("git_config",) + ("raw_audit",) * 5
    result: list[tuple[str, str]] = []
    for label in ("A", "B"):
        result.extend((label, phase) for phase in clone)
    for label in ("A", "B"):
        result.extend((label, phase) for phase in raw_audit)
    for label in ("A", "B"):
        result.append((label, "environment_build"))
    for label in ("A", "B"):
        result.extend((label, phase) for phase in raw_audit)
    for label in ("A", "B"):
        result.extend((label, "preflight") for _ in range(5))
    return tuple(result)


_COMMAND_IDENTITY_KEYS: Final = {
    "attempt_index", "label", "phase", "cwd", "argv", "argv_sha256",
    "stdin_size_bytes", "stdin_sha256",
}


def _command_identity(
    *,
    attempt_index: int | None,
    label: str | None,
    phase: str,
    cwd: Path,
    argv: Sequence[str],
    stdin_bytes: bytes = b"",
) -> dict[str, object]:
    argv_list = list(argv)
    return {
        "attempt_index": attempt_index,
        "label": label,
        "phase": phase,
        "cwd": os.path.abspath(cwd),
        "argv": argv_list,
        "argv_sha256": canonical_sha256(argv_list),
        "stdin_size_bytes": len(stdin_bytes),
        "stdin_sha256": hashlib.sha256(stdin_bytes).hexdigest(),
    }


def _expected_raw_audit_identities(
    root: Path,
    open_commit: str,
    entries: Sequence[_TreeEntry],
    *,
    attempt_index: int,
    label: str,
) -> list[dict[str, object]]:
    git_prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(root)]
    request = b"".join(entry.oid.encode("ascii") + b"\n" for entry in entries)
    commands: list[tuple[str, list[str], bytes]] = [
        ("git_config", [*git_prefix, "config", "--local", "--null", "--list"], b""),
        ("raw_audit", [*git_prefix, "rev-parse", "HEAD"], b""),
        (
            "raw_audit",
            [*git_prefix, "ls-tree", "-r", "-l", "-z", "--full-tree", open_commit],
            b"",
        ),
        ("raw_audit", [*git_prefix, "cat-file", "--batch"], request),
        ("raw_audit", [*git_prefix, "ls-files", "--stage", "-z"], b""),
        (
            "raw_audit",
            [*git_prefix, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            b"",
        ),
    ]
    return [
        _command_identity(
            attempt_index=attempt_index,
            label=label,
            phase=phase,
            cwd=root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _expected_attempt_identities(
    execution_root: Path,
    attempt_index: int,
    open_commit: str,
    entries: Sequence[_TreeEntry],
) -> list[dict[str, object]]:
    source = execution_root / f".prepare-attempt-{attempt_index}"
    result: list[dict[str, object]] = []

    def append(
        label: str,
        phase: str,
        cwd: Path,
        argv: Sequence[str],
        stdin_bytes: bytes = b"",
    ) -> None:
        result.append(
            _command_identity(
                attempt_index=attempt_index,
                label=label,
                phase=phase,
                cwd=cwd,
                argv=argv,
                stdin_bytes=stdin_bytes,
            )
        )

    roots = {"A": source / "process-a", "B": source / "process-b"}
    for label, root in roots.items():
        clone_commands: list[tuple[str, list[str]]] = [
            (
                "clone",
                [
                    "/usr/bin/git", "--no-replace-objects", "clone", "--no-local",
                    "--no-checkout", "--branch", _OPEN_FREEZE_TAG, "--single-branch",
                    _SOURCE_URL, str(root),
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", str(root), "config",
                    "--local", "core.autocrlf", "false",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", str(root), "config",
                    "--local", "core.eol", "lf",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", str(root), "config",
                    "--local", "core.safecrlf", "true",
                ],
            ),
            (
                "checkout",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", str(root), "checkout",
                    "--detach", open_commit,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", str(root), "remote",
                    "remove", "origin",
                ],
            ),
        ]
        for phase, argv in clone_commands:
            append(label, phase, source, argv)
        git_prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(root)]
        append(
            label,
            "git_config",
            root,
            [*git_prefix, "config", "--local", "--null", "--list"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*git_prefix, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*git_prefix, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
    for label, root in roots.items():
        result.extend(
            _expected_raw_audit_identities(
                root,
                open_commit,
                entries,
                attempt_index=attempt_index,
                label=label,
            )
        )
    for label, root in roots.items():
        append(label, "environment_build", root, _expected_environment_argv())
    for label, root in roots.items():
        result.extend(
            _expected_raw_audit_identities(
                root,
                open_commit,
                entries,
                attempt_index=attempt_index,
                label=label,
            )
        )
    for label, root in roots.items():
        for argv in _expected_preflight_argvs():
            append(label, "preflight", root, argv)
    if len(result) != 54:
        _fail("internal preparation command plan does not contain exactly 54 rows")
    return result


def _validate_command_ledger(
    value: Any,
    *,
    commands_sha256: Any,
    command_environment_sha256: Any,
    attempts: Any,
    receipt_status: Any,
    execution_root: Path,
    open_commit: str,
    entries: Sequence[_TreeEntry],
    expected_authority_rows: Sequence[Mapping[str, object]],
) -> None:
    if not isinstance(value, list) or not value:
        _fail("preparation command ledger is not a nonempty array")
    expected_environment_sha = canonical_sha256(_command_environment())
    if command_environment_sha256 != expected_environment_sha:
        _fail("preparation command environment SHA-256 is invalid")
    if commands_sha256 != canonical_sha256(value):
        _fail("preparation command ledger SHA-256 is invalid")
    empty_sha = hashlib.sha256(b"").hexdigest()
    observed_attempt_phases: dict[int, list[tuple[str, str]]] = {1: [], 2: []}
    observed_attempt_rows: dict[int, list[Mapping[str, Any]]] = {1: [], 2: []}
    observed_authority_rows: list[Mapping[str, Any]] = []
    last_attempt = 0
    for sequence_index, item in enumerate(value):
        if not isinstance(item, dict):
            _fail(f"preparation command ledger row {sequence_index} is not an object")
        _require_keys(item, _COMMAND_LEDGER_KEYS, f"preparation command row {sequence_index}")
        if item["sequence_index"] != sequence_index:
            _fail("preparation command sequence indices are not contiguous from zero")
        attempt_index = item["attempt_index"]
        label = item["label"]
        if attempt_index is None:
            if last_attempt or label != "authority":
                _fail("authority command occurs after an attempt or has the wrong label")
            observed_authority_rows.append(item)
        else:
            if attempt_index not in {1, 2} or isinstance(attempt_index, bool):
                _fail("preparation command attempt index is invalid")
            if attempt_index < last_attempt or attempt_index > last_attempt + 1:
                _fail("preparation command attempt groups are not contiguous")
            last_attempt = attempt_index
            if label not in {"A", "B"}:
                _fail("attempt command label is invalid")
        phase = item["phase"]
        if phase not in {
            "clone", "git_config", "checkout", "raw_audit", "environment_build",
            "preflight",
        }:
            _fail("preparation command phase is invalid")
        if attempt_index is None and phase not in {"git_config", "raw_audit"}:
            _fail("authority command has an impossible phase")
        if attempt_index is not None:
            observed_attempt_phases[attempt_index].append((str(label), str(phase)))
            observed_attempt_rows[attempt_index].append(item)
        cwd = item["cwd"]
        argv = item["argv"]
        if (
            not isinstance(cwd, str)
            or not PurePosixPath(cwd).is_absolute()
            or "\x00" in cwd
            or not isinstance(argv, list)
            or not argv
            or not all(isinstance(argument, str) and "\x00" not in argument for argument in argv)
        ):
            _fail("preparation command cwd/argv is invalid")
        if item["argv_sha256"] != canonical_sha256(argv):
            _fail("preparation command argv SHA-256 is invalid")
        if argv[0] == "/usr/bin/git" and (
            len(argv) < 2 or argv[1] != "--no-replace-objects"
        ):
            _fail("preparation Git command lacks --no-replace-objects")
        stdin_size = _require_int(item["stdin_size_bytes"], "preparation stdin size")
        stdout_size = _require_int(item["stdout_size_bytes"], "preparation stdout size")
        stderr_size = _require_int(item["stderr_size_bytes"], "preparation stderr size")
        _require_hex(item["stdin_sha256"], 64, "preparation stdin SHA-256")
        _require_hex(item["stdout_sha256"], 64, "preparation stdout SHA-256")
        _require_hex(item["stderr_sha256"], 64, "preparation stderr SHA-256")
        _require_int(item["duration_milliseconds"], "preparation command duration")
        started = item["started"]
        timed_out = item["timed_out"]
        cleanup = item["child_cleanup_passes"]
        exit_code = item["exit_code"]
        outcome = item["outcome"]
        if not isinstance(started, bool) or not isinstance(timed_out, bool):
            _fail("preparation command start/timeout flags are not Boolean")
        if cleanup is not None and not isinstance(cleanup, bool):
            _fail("preparation command cleanup field is invalid")
        if exit_code is not None and (
            not isinstance(exit_code, int) or isinstance(exit_code, bool)
        ):
            _fail("preparation command actual exit is invalid")
        if not started:
            if (
                exit_code is not None
                or timed_out
                or cleanup is not None
                or outcome not in {"stdin_limit", "spawn_error"}
                or stdout_size != 0
                or stderr_size != 0
                or item["stdout_sha256"] != empty_sha
                or item["stderr_sha256"] != empty_sha
            ):
                _fail("pre-spawn command evidence is inconsistent")
            if (outcome == "stdin_limit") != (stdin_size > _PREPARATION_STDIN_CAP_BYTES):
                _fail("stdin-limit classification is inconsistent with intended input size")
            if outcome == "spawn_error" and stdin_size > _PREPARATION_STDIN_CAP_BYTES:
                _fail("spawn-error input exceeds the pre-spawn cap")
            continue
        if stdin_size > _PREPARATION_STDIN_CAP_BYTES:
            _fail("spawned preparation command has over-cap stdin")
        if outcome not in {"completed", "nonzero", "timeout", "stdout_limit", "stderr_limit"}:
            _fail("spawned preparation command outcome is invalid")
        if outcome == "completed" and (exit_code != 0 or timed_out):
            _fail("completed command does not have actual exit zero")
        if outcome == "nonzero" and (
            exit_code is None or exit_code == 0 or timed_out
        ):
            _fail("nonzero command lacks an actual nonzero exit")
        if outcome == "timeout" and not timed_out:
            _fail("timeout command is not marked timed out")
        if outcome == "stdout_limit":
            if stdout_size != _PREPARATION_STDOUT_CAP_BYTES + 1:
                _fail("stdout-limit evidence is not the exact cap+1 prefix")
        elif stdout_size > _PREPARATION_STDOUT_CAP_BYTES:
            _fail("non-stdout-limit evidence exceeds the stdout cap")
        if outcome == "stderr_limit":
            if (
                stdout_size > _PREPARATION_STDOUT_CAP_BYTES
                or stderr_size != _PREPARATION_STDERR_CAP_BYTES + 1
            ):
                _fail("stderr-limit evidence violates precedence or cap+1")
        elif outcome == "stdout_limit":
            if stderr_size > _PREPARATION_STDERR_CAP_BYTES + 1:
                _fail("stdout-limit stderr evidence exceeds cap+1")
        elif stderr_size > _PREPARATION_STDERR_CAP_BYTES:
            _fail("non-stream-limit evidence exceeds the stderr cap")
        if outcome in {"timeout", "stdout_limit", "stderr_limit"} and cleanup is None:
            _fail("forced command control lacks cleanup evidence")
        if cleanup is False:
            _fail("preparation receipt contains failed child cleanup")

    if not isinstance(attempts, list):
        _fail("preparation attempts are not an array")
    expected_authority_identities = [
        {key: row[key] for key in _COMMAND_IDENTITY_KEYS}
        for row in expected_authority_rows
    ]
    observed_authority_identities = [
        {key: row[key] for key in _COMMAND_IDENTITY_KEYS}
        for row in observed_authority_rows
    ]
    if observed_authority_identities != expected_authority_identities:
        _fail("preparation authority command ledger differs from live exact reconstruction")
    if any(row["outcome"] != "completed" for row in observed_authority_rows):
        _fail("preparation authority command ledger contains a non-completed row")
    plan = _attempt_phase_plan()
    for attempt_index in range(1, len(attempts) + 1):
        observed = observed_attempt_phases[attempt_index]
        if tuple(observed) != plan[: len(observed)]:
            _fail(f"preparation attempt {attempt_index} command phases are not a plan prefix")
        attempt = attempts[attempt_index - 1]
        if isinstance(attempt, dict) and attempt.get("passes") is True and tuple(observed) != plan:
            _fail("passing preparation attempt lacks the complete command plan")
        if (
            isinstance(attempt, dict)
            and attempt.get("passes") is True
            and any(row["outcome"] != "completed" for row in observed_attempt_rows[attempt_index])
        ):
            _fail("passing preparation attempt contains a non-completed command")
        expected_rows = _expected_attempt_identities(
            execution_root,
            attempt_index,
            open_commit,
            entries,
        )
        observed_identities = [
            {key: row[key] for key in _COMMAND_IDENTITY_KEYS}
            for row in observed_attempt_rows[attempt_index]
        ]
        if observed_identities != expected_rows[: len(observed_identities)]:
            _fail(f"preparation attempt {attempt_index} contains an invented command")
        if (
            isinstance(attempt, dict)
            and attempt.get("passes") is True
            and observed_identities != expected_rows
        ):
            _fail("passing preparation attempt lacks the exact complete argv plan")
    if observed_attempt_phases[2] and len(attempts) < 2:
        _fail("command ledger contains an unregistered second attempt")


def _validate_preparation_attempts(value: Any, execution_root: Path) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 2:
        _fail("prepared receipt attempt inventory is invalid")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            _fail(f"preparation attempt {index} is not an object")
        _require_keys(item, _ATTEMPT_RECORD_KEYS, f"preparation attempt {index}")
        if item["attempt_index"] != index:
            _fail("preparation attempt indices are not contiguous one-based integers")
        if item["process_a_stage"] not in _PROCESS_STAGES or item["process_b_stage"] not in _PROCESS_STAGES:
            _fail("preparation attempt contains an unknown process stage")
        cleanup = item["cleanup"]
        promotion = item["promotion"]
        if not isinstance(cleanup, dict) or not isinstance(promotion, dict):
            _fail("preparation attempt cleanup/promotion is not an object")
        _require_keys(cleanup, _CLEANUP_KEYS, f"preparation attempt {index} cleanup")
        _require_keys(promotion, _PROMOTION_KEYS, f"preparation attempt {index} promotion")
        source = execution_root / f".prepare-attempt-{index}"
        destination = execution_root / "processes"
        if promotion["source_path"] != str(source) or promotion["destination_path"] != str(destination):
            _fail("preparation attempt promotion paths differ from P8")
        owned = cleanup["owned_paths"]
        removed = cleanup["removed"]
        if (
            not isinstance(owned, list)
            or not isinstance(removed, list)
            or not all(isinstance(path, str) for path in [*owned, *removed])
            or owned != sorted(owned)
            or removed != sorted(removed)
            or not set(removed) <= set(owned)
        ):
            _fail("preparation cleanup ledger is not canonical")
        final = index == len(value)
        if final:
            if (
                item["passes"] is not True
                or item["process_a_stage"] != "completed"
                or item["process_b_stage"] != "completed"
                or promotion["passes"] is not True
                or cleanup["passes"] is not True
                or owned != [str(source)]
                or removed != []
            ):
                _fail("final preparation attempt is not one passing atomic promotion")
            device = _require_int(promotion["source_device"], "promotion source device")
            inode = _require_int(promotion["source_inode"], "promotion source inode")
            _assert_absent(source, "passing preparation staging source")
            metadata = _plain_directory(destination, "promoted processes", mode=0o700, owner=True)
            if metadata.st_dev != device or metadata.st_ino != inode:
                _fail("promoted processes identity differs from preparation receipt")
        else:
            if item["passes"] is not False or promotion["passes"] is not False or cleanup["passes"] is not True:
                _fail("preparation retry follows a failed or incomplete cleanup")
            _assert_absent(source, "cleaned failed preparation staging source")


def _validate_clone_record(
    value: Any,
    expected_root: Path,
    open_commit: str,
    audit: _RawAudit,
    inventory: list[dict[str, object]] | None,
    inventory_sha256: str | None,
    venv_materialization_sha256: str | None,
    venv_python_sha256: str | None,
    *,
    environment: bool,
    name: str,
) -> None:
    if not isinstance(value, dict):
        _fail(f"{name} clone record is not an object")
    _require_keys(value, _CLONE_KEYS, f"{name} clone record")
    expected = _clone_receipt(
        expected_root,
        open_commit,
        audit,
        inventory,
        inventory_sha256,
        venv_materialization_sha256,
        venv_python_sha256,
        environment=environment,
    )
    if value != expected:
        _fail(f"{name} clone record differs from independently observed state")


@dataclass(frozen=True, slots=True)
class _ArtifactState:
    path: Path
    exists: bool
    read_status: str
    raw: bytes | None
    sha256: str | None


def _artifact_state(path: Path, name: str, *, maximum: int) -> _ArtifactState:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _ArtifactState(path, False, "absent", None, None)
    except OSError:
        return _ArtifactState(path, True, "read_error", None, None)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        return _ArtifactState(path, True, "unsafe_type", None, None)
    if metadata.st_size > maximum:
        return _ArtifactState(path, True, "oversized", None, None)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return _ArtifactState(path, True, "read_error", None, None)
    try:
        opened = os.fstat(descriptor)
        identity_fields = (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_size", "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(getattr(opened, field) != getattr(metadata, field) for field in identity_fields):
            return _ArtifactState(path, True, "changed_during_read", None, None)
        if opened.st_size > maximum:
            return _ArtifactState(path, True, "oversized", None, None)
        data = bytearray()
        try:
            while len(data) <= maximum:
                chunk = os.read(descriptor, min(1 << 20, maximum + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
        except OSError:
            return _ArtifactState(path, True, "read_error", None, None)
        if len(data) > maximum:
            return _ArtifactState(path, True, "oversized", None, None)
        final = os.fstat(descriptor)
        if (
            len(data) != opened.st_size
            or any(getattr(final, field) != getattr(opened, field) for field in identity_fields)
        ):
            return _ArtifactState(path, True, "changed_during_read", None, None)
    finally:
        os.close(descriptor)
    raw = bytes(data)
    return _ArtifactState(path, True, "readable", raw, hashlib.sha256(raw).hexdigest())


def _verification_clone_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    del result["environment_inventory"]
    _require_keys(result, _VERIFICATION_CLONE_KEYS, "verification clone record")
    return result


@dataclass(frozen=True, slots=True)
class _ArmContext:
    execution_root: Path
    authority: Path
    open_commit: str
    registration: _Registration
    preparation: _ArtifactState
    preparation_verification: _ArtifactState
    preparation_valid: bool
    preparation_verification_valid: bool
    evidence_errors: tuple[str, ...]


def _validate_prepared_state(args: argparse.Namespace) -> _ArmContext:
    if os.name != "posix":
        _fail("arm is available only in registered Linux")
    if (
        str(args.repository_root) != "."
        or str(args.registration) != _REGISTRATION_PATH
        or str(args.execution_root) != _EXECUTION_ROOT
        or str(args.preparation_receipt) != _PREPARATION_RECEIPT
        or str(args.preparation_verification_receipt)
        != _PREPARATION_VERIFICATION_RECEIPT
    ):
        _fail("arm preparation arguments differ from P8")
    execution_root = Path(args.execution_root)
    authority = Path(_AUTHORITY_ROOT)
    _no_symlink_ancestors(execution_root, "execution root")
    _plain_directory(execution_root, "execution root", mode=0o700, owner=True)
    _no_symlink_ancestors(authority, "authority root")
    _plain_directory(authority, "authority root", mode=0o700, owner=True)
    repository_root = Path(args.repository_root).resolve(strict=True)
    if repository_root != authority:
        _fail("arm is not running from the registered authority clone")
    ledger = _CommandLedger()
    open_commit = _derive_open_freeze(ledger, authority)
    authority_audit = _raw_tree_audit(
        ledger,
        authority,
        open_commit,
        allow_venv=False,
    )
    registration = _load_registration(
        authority,
        authority / args.registration,
        authority_audit,
        open_commit,
    )
    _validate_linux_host(registration)
    if registration.execution["arm_argv"] != _expected_arm_argv():
        _fail("registered arm argv changed after registration validation")
    preparation_state = _artifact_state(
        Path(args.preparation_receipt),
        "preparation receipt",
        maximum=_ADMINISTRATIVE_EVIDENCE_LIMIT,
    )
    verification_state = _artifact_state(
        Path(args.preparation_verification_receipt),
        "preparation verification receipt",
        maximum=_ADMINISTRATIVE_EVIDENCE_LIMIT,
    )
    errors: list[str] = []
    preparation_valid = False
    verification_valid = False
    process_a = execution_root / "processes/process-a"
    process_b = execution_root / "processes/process-b"
    expected_authority = _clone_receipt(
        authority,
        open_commit,
        authority_audit,
        None,
        None,
        None,
        None,
        environment=False,
    )
    expected_process_a: dict[str, Any] | None = None
    expected_process_b: dict[str, Any] | None = None
    if preparation_state.raw is None:
        errors.append(f"preparation receipt: {preparation_state.read_status}")
    else:
        try:
            preparation = _parse_canonical_object(
                preparation_state.raw,
                "preparation receipt",
            )
            _require_keys(preparation, _PREPARATION_KEYS, "preparation receipt")
            if (
                preparation["schema_version"] != _PREPARATION_SCHEMA
                or preparation["treatment_id"] != _TREATMENT_ID
                or preparation["open_freeze_commit_sha"] != open_commit
                or preparation["open_freeze_tag"] != _OPEN_FREEZE_TAG
                or preparation["registration_content_sha256"] != registration.content_sha256
                or preparation["status"] != "prepared"
            ):
                _fail("preparation receipt fixed identity/status is invalid")
            _require_hex(
                preparation["commands_sha256"],
                64,
                "preparation command ledger SHA-256",
            )
            _require_hex(
                preparation["command_environment_sha256"],
                64,
                "preparation command environment SHA-256",
            )
            _validate_command_ledger(
                preparation["command_ledger"],
                commands_sha256=preparation["commands_sha256"],
                command_environment_sha256=preparation["command_environment_sha256"],
                attempts=preparation["attempts"],
                receipt_status=preparation["status"],
                execution_root=execution_root,
                open_commit=open_commit,
                entries=authority_audit.entries,
                expected_authority_rows=tuple(ledger.entries),
            )
            _validate_preparation_attempts(preparation["attempts"], execution_root)
            if preparation["authority"] != expected_authority:
                _fail("authority clone record differs from independently observed state")
            process_a_audit = _raw_tree_audit(
                ledger,
                process_a,
                open_commit,
                allow_venv=True,
                label="A",
            )
            process_b_audit = _raw_tree_audit(
                ledger,
                process_b,
                open_commit,
                allow_venv=True,
                label="B",
            )
            if _run_preflight(
                ledger,
                process_a,
                registration,
                open_commit,
                attempt_index=None,
                label="A",
            ) != process_a_audit.status_sha256:
                _fail("process A live preflight status differs from raw audit")
            if _run_preflight(
                ledger,
                process_b,
                registration,
                open_commit,
                attempt_index=None,
                label="B",
            ) != process_b_audit.status_sha256:
                _fail("process B live preflight status differs from raw audit")
            inventory_a, inventory_a_sha = _environment_inventory(process_a)
            inventory_b, inventory_b_sha = _environment_inventory(process_b)
            venv_a = _venv_materialization_sha256(process_a)
            venv_b = _venv_materialization_sha256(process_b)
            python_a = _venv_python_sha256(process_a)
            python_b = _venv_python_sha256(process_b)
            if python_a != python_b:
                _fail("process A/B resolved virtual-environment Python bytes differ")
            expected_process_a = _clone_receipt(
                process_a,
                open_commit,
                process_a_audit,
                inventory_a,
                inventory_a_sha,
                venv_a,
                python_a,
                environment=True,
            )
            expected_process_b = _clone_receipt(
                process_b,
                open_commit,
                process_b_audit,
                inventory_b,
                inventory_b_sha,
                venv_b,
                python_b,
                environment=True,
            )
            if preparation["process_a"] != expected_process_a:
                _fail("process A clone record differs from independently observed state")
            if preparation["process_b"] != expected_process_b:
                _fail("process B clone record differs from independently observed state")
            for label in ("a", "b"):
                _plain_directory(
                    execution_root / f"processes/process-{label}-output/open",
                    f"process {label.upper()} output parent",
                    mode=0o700,
                    owner=True,
                    empty=True,
                )
            preparation_valid = True
        except (ProtocolError, OSError) as error:
            errors.append(f"preparation receipt: {error}")

    if verification_state.raw is None:
        errors.append(f"preparation verification receipt: {verification_state.read_status}")
    elif (
        preparation_valid
        and preparation_state.sha256 is not None
        and expected_process_a is not None
        and expected_process_b is not None
    ):
        try:
            verification = _parse_canonical_object(
                verification_state.raw,
                "preparation verification receipt",
            )
            _require_keys(
                verification,
                _PREPARATION_VERIFICATION_KEYS,
                "preparation verification receipt",
            )
            content_preimage = {
                key: item for key, item in verification.items() if key != "content_sha256"
            }
            if (
                verification["schema_version"] != _PREPARATION_VERIFICATION_SCHEMA
                or verification["treatment_id"] != _TREATMENT_ID
                or verification["open_freeze_commit_sha"] != open_commit
                or verification["open_freeze_tag"] != _OPEN_FREEZE_TAG
                or verification["registration_content_sha256"]
                != registration.content_sha256
                or verification["preparation_receipt_sha256"]
                != preparation_state.sha256
                or verification["verification_argv_sha256"]
                != canonical_sha256(_expected_preparation_verification_argv())
                or verification["authority"]
                != _verification_clone_record(expected_authority)
                or verification["process_a"]
                != _verification_clone_record(expected_process_a)
                or verification["process_b"]
                != _verification_clone_record(expected_process_b)
                or verification["status"] != "verified"
                or verification["content_sha256"] != canonical_sha256(content_preimage)
            ):
                _fail("preparation verification receipt does not match live P8v4 state")
            verification_valid = True
        except (ProtocolError, OSError) as error:
            errors.append(f"preparation verification receipt: {error}")
    else:
        errors.append("preparation verification receipt: lacks a valid preparation receipt")
    return _ArmContext(
        execution_root=execution_root,
        authority=authority,
        open_commit=open_commit,
        registration=registration,
        preparation=preparation_state,
        preparation_verification=verification_state,
        preparation_valid=preparation_valid,
        preparation_verification_valid=verification_valid,
        evidence_errors=tuple(errors),
    )


def _source_manifest_entry(registration: _Registration, path: str) -> Mapping[str, Any]:
    source_manifest = registration.value["source_manifest"]
    if not isinstance(source_manifest, dict):
        _fail("registration source manifest is invalid")
    rows = source_manifest["open_freeze_added_files"]
    if not isinstance(rows, list):
        _fail("registration open-freeze manifest is invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("path") == path]
    if len(matches) != 1:
        _fail(f"registration does not bind exactly one source path: {path}")
    return matches[0]


def _validate_lifecycle_claim(
    data: bytes,
    context: _ArmContext,
) -> tuple[Mapping[str, Any], str]:
    value = _parse_canonical_object(data, "lifecycle claim")
    _require_keys(value, _CLAIM_KEYS, "lifecycle claim")
    supervisor = _source_manifest_entry(context.registration, _SUPERVISOR_SCRIPT)
    verifier = _source_manifest_entry(context.registration, _VERIFIER_SCRIPT)
    argv_hashes = context.registration.execution.get("argv_hashes")
    if not isinstance(argv_hashes, dict):
        _fail("registration argv hashes are invalid")
    expected = {
        "schema_version": _CLAIM_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": context.open_commit,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": context.registration.content_sha256,
        "supervisor_argv_sha256": argv_hashes["remote_supervisor"],
        "supervisor_script_git_blob_sha1": supervisor["git_blob_sha1"],
        "supervisor_script_sha256": supervisor["sha256"],
        "verifier_script_git_blob_sha1": verifier["git_blob_sha1"],
        "verifier_script_sha256": verifier["sha256"],
    }
    if value != expected:
        _fail("lifecycle claim does not match O8 registration")
    return value, hashlib.sha256(data).hexdigest()


def _validate_start_claim(
    data: bytes,
    context: _ArmContext,
    claim_sha256: str,
) -> tuple[Mapping[str, Any], str]:
    value = _parse_canonical_object(data, "verifier-start claim")
    _require_keys(value, _START_CLAIM_KEYS, "verifier-start claim")
    argv_hashes = context.registration.execution.get("argv_hashes")
    if not isinstance(argv_hashes, dict):
        _fail("registration argv hashes are invalid")
    expected = {
        "schema_version": _START_CLAIM_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "claim_sha256": claim_sha256,
        "open_freeze_commit_sha": context.open_commit,
        "registration_content_sha256": context.registration.content_sha256,
        "verifier_argv_sha256": argv_hashes["remote_verifier"],
    }
    if value != expected:
        _fail("verifier-start claim does not match lifecycle claim/O8")
    return value, hashlib.sha256(data).hexdigest()


def _decode_stream(record: Mapping[str, Any], prefix: str, cap: int) -> bytes:
    size = _require_int(record[f"{prefix}_size_bytes"], f"{prefix} size")
    if size > cap:
        _fail(f"{prefix} exceeds its registered cap")
    digest = _require_hex(record[f"{prefix}_sha256"], 64, f"{prefix} SHA-256")
    encoded = record[f"{prefix}_base64"]
    if not isinstance(encoded, str) or any(ord(character) > 127 for character in encoded):
        _fail(f"{prefix} Base64 is invalid")
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as error:
        raise ProtocolError(f"{prefix} Base64 is invalid") from error
    if base64.b64encode(data).decode("ascii") != encoded:
        _fail(f"{prefix} Base64 is not canonical")
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        _fail(f"{prefix} metadata does not match its bytes")
    return data


def _expected_tool(path: str, version: str, sha256: str) -> dict[str, str]:
    return {"path": path, "version": version, "sha256": sha256}


def _actual_exit(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{name} is not an actual integer return")
    return value


def _validate_remote_attempt(
    value: Any,
    index: int,
    expected_stdout: bytes,
) -> tuple[str, int]:
    if not isinstance(value, dict):
        _fail(f"remote attempt {index} is not an object")
    _require_keys(value, _REMOTE_ATTEMPT_KEYS, f"remote attempt {index}")
    if value["attempt_index"] != index:
        _fail("remote attempt indices are not contiguous one-based integers")
    classification = value["classification"]
    if classification not in _REMOTE_CLASSIFICATIONS:
        _fail(f"remote attempt {index} classification is invalid")
    exit_code = value["exit_code"]
    if classification in {"spawn_error", "child_cleanup_failed"}:
        if exit_code is not None:
            _actual_exit(exit_code, f"remote attempt {index} exit code")
    else:
        _actual_exit(exit_code, f"remote attempt {index} exit code")
    timed_out = value["timed_out"]
    if not isinstance(timed_out, bool):
        _fail("remote attempt timed_out is not Boolean")
    duration = _require_int(value["duration_milliseconds"], "remote attempt duration")
    stdout = _decode_stream(value, "stdout", _STDOUT_CAP_BYTES)
    stderr = _decode_stream(value, "stderr", _STDERR_CAP_BYTES)
    cleanup = value["child_cleanup_passes"]
    always_cleaned = {
        "post_spawn_initialization_failed", "stream_capture_failed",
        "retryable_timeout_124", "stdout_limit", "stderr_limit", "overall_deadline",
    }
    if classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("cleanup-failure remote attempt must record false cleanup")
    elif classification in always_cleaned:
        if cleanup is not True:
            _fail("controlled remote attempt lacks passing cleanup")
    elif classification == "spawn_error":
        if cleanup is not None:
            _fail("pre-child spawn error has non-null cleanup")
    elif cleanup not in {None, True}:
        _fail("normal remote attempt cleanup is not null or true")
    if classification == "verified":
        if exit_code != 0 or stdout != expected_stdout or timed_out is not False:
            _fail("verified remote attempt evidence is invalid")
    elif classification == "retryable_empty_exit_0":
        if exit_code != 0 or stdout or timed_out is not False:
            _fail("empty-exit-zero remote attempt evidence is invalid")
    elif classification == "retryable_timeout_124":
        if (
            exit_code != 124
            or timed_out is not True
            or duration < _ATTEMPT_TIMEOUT_SECONDS * 1000
        ):
            _fail("timeout remote attempt evidence is invalid")
    elif classification == "retryable_git_128":
        if exit_code != 128 or stdout or timed_out is not False:
            _fail("Git-128 remote attempt evidence is invalid")
    elif classification == "unexpected_output":
        if not stdout or (exit_code == 0 and stdout == expected_stdout) or timed_out is not False:
            _fail("unexpected-output remote attempt evidence is invalid")
    elif classification == "unexpected_exit":
        if exit_code in {0, 128} or stdout or timed_out is not False:
            _fail("unexpected-exit remote attempt evidence is invalid")
    elif classification == "stdout_limit":
        if len(stdout) != _STDOUT_CAP_BYTES or (timed_out and exit_code != 124):
            _fail("stdout-limit remote attempt evidence is invalid")
    elif classification == "stderr_limit":
        if len(stderr) != _STDERR_CAP_BYTES or (timed_out and exit_code != 124):
            _fail("stderr-limit remote attempt evidence is invalid")
    elif classification == "spawn_error":
        if exit_code is not None or stdout or stderr or timed_out is not False:
            _fail("spawn-error remote attempt evidence is invalid")
    elif classification == "post_spawn_initialization_failed":
        if stdout or stderr or timed_out is not False:
            _fail("post-spawn initialization evidence is invalid")
    elif classification == "stream_capture_failed":
        if (timed_out and exit_code != 124) or (not timed_out and exit_code is None):
            _fail("stream-capture failure evidence is invalid")
    elif classification == "overall_deadline":
        if (
            exit_code != 124
            or timed_out is not True
            or duration < _ATTEMPT_TIMEOUT_SECONDS * 1000
        ):
            _fail("overall-deadline remote attempt evidence is invalid")
    elif classification == "child_cleanup_failed":
        pass
    return classification, duration


def _validate_tool_object(value: Any, expected: Mapping[str, str], name: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{name} tool identity is not an object")
    _require_keys(value, {"path", "version", "sha256"}, f"{name} tool identity")
    if value != expected:
        _fail(f"{name} tool identity differs from P8")


def _validate_remote_receipt(
    data: bytes,
    context: _ArmContext,
    claim_sha256: str,
    start_claim_sha256: str,
) -> tuple[Mapping[str, Any], str]:
    value = _parse_canonical_object(data, "remote receipt")
    _require_keys(value, _REMOTE_RECEIPT_KEYS, "remote receipt")
    if (
        value["schema_version"] != _REMOTE_RECEIPT_SCHEMA
        or value["treatment_id"] != _TREATMENT_ID
        or value["claim_sha256"] != claim_sha256
        or value["verifier_start_claim_sha256"] != start_claim_sha256
        or value["open_freeze_commit_sha"] != context.open_commit
        or value["open_freeze_tag"] != _OPEN_FREEZE_TAG
        or value["registration_content_sha256"] != context.registration.content_sha256
        or value["remote_url"] != _REMOTE_URL
        or value["ref"] != _REMOTE_REF
        or value["policy"] != _remote_policy()
    ):
        _fail("remote receipt fixed identity differs from P8/O8 claims")
    _validate_tool_object(
        value["python"],
        _expected_tool(_PYTHON_PATH, _PYTHON_VERSION, _PYTHON_SHA256),
        "Python",
    )
    _validate_tool_object(
        value["git"],
        _expected_tool(_GIT_PATH, _GIT_VERSION, _GIT_SHA256),
        "Git",
    )
    _validate_tool_object(
        value["taskkill"],
        _expected_tool(_TASKKILL_PATH, _TASKKILL_VERSION, _TASKKILL_SHA256),
        "taskkill",
    )
    attempts = value["attempts"]
    if not isinstance(attempts, list) or len(attempts) > _MAX_ATTEMPTS:
        _fail("remote receipt attempt inventory is invalid")
    expected_stdout = f"{context.open_commit}\t{_REMOTE_REF}\n".encode("ascii")
    classifications: list[str] = []
    durations: list[int] = []
    for index, attempt in enumerate(attempts, start=1):
        classification, duration = _validate_remote_attempt(attempt, index, expected_stdout)
        classifications.append(classification)
        durations.append(duration)
        if index < len(attempts) and classification not in _RETRYABLE_CLASSIFICATIONS:
            _fail("remote attempt follows a terminal classification")
    status = value["status"]
    selected = value["selected_attempt"]
    if status == "verified":
        if not attempts or classifications[-1] != "verified" or selected != len(attempts):
            _fail("verified remote receipt selection is invalid")
    elif status == "failed":
        if selected is not None or "verified" in classifications:
            _fail("failed remote receipt selection is invalid")
    else:
        _fail("remote receipt status is invalid")
    total = _require_int(value["total_duration_milliseconds"], "remote total duration")
    retry_gaps = max(0, len(attempts) - 1) * _RETRY_DELAY_SECONDS * 1000
    if total < sum(durations) + retry_gaps:
        _fail("remote total duration is shorter than its attempt ledger")
    return value, hashlib.sha256(data).hexdigest()


def _validate_supervisor_receipt(
    data: bytes,
    context: _ArmContext,
    *,
    claim_sha256: str,
    start_raw_sha256: str | None,
    remote_raw_sha256: str | None,
    start_valid: bool,
    remote_value: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], str]:
    value = _parse_canonical_object(data, "remote supervisor receipt")
    _require_keys(value, _SUPERVISOR_KEYS, "remote supervisor receipt")
    argv_hashes = context.registration.execution.get("argv_hashes")
    if not isinstance(argv_hashes, dict):
        _fail("registration argv hashes are invalid")
    if (
        value["schema_version"] != _SUPERVISOR_SCHEMA
        or value["treatment_id"] != _TREATMENT_ID
        or value["claim_sha256"] != claim_sha256
        or value["verifier_start_claim_sha256"] != start_raw_sha256
        or value["open_freeze_commit_sha"] != context.open_commit
        or value["registration_content_sha256"] != context.registration.content_sha256
        or value["verifier_argv_sha256"] != argv_hashes["remote_verifier"]
        or value["remote_receipt_sha256"] != remote_raw_sha256
    ):
        _fail("remote supervisor receipt fixed identity/hash fields are invalid")
    classification = value["classification"]
    if classification not in _SUPERVISOR_CLASSIFICATIONS:
        _fail("remote supervisor classification is invalid")
    exit_code = value["verifier_exit_code"]
    if classification in {"spawn_error", "child_cleanup_failed"}:
        if exit_code is not None:
            _actual_exit(exit_code, "supervisor verifier exit code")
    else:
        _actual_exit(exit_code, "supervisor verifier exit code")
    timed_out = value["timed_out"]
    if not isinstance(timed_out, bool):
        _fail("supervisor timed_out is not Boolean")
    _require_int(value["duration_milliseconds"], "supervisor duration")
    stdout = _decode_stream(value, "stdout", _STDOUT_CAP_BYTES)
    stderr = _decode_stream(value, "stderr", _STDERR_CAP_BYTES)
    cleanup = value["child_cleanup_passes"]
    always_cleaned = {
        "post_spawn_initialization_failed", "stream_capture_failed",
        "verifier_timeout_124", "stdout_limit", "stderr_limit",
    }
    if classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("supervisor cleanup failure must record false cleanup")
    elif classification in always_cleaned:
        if cleanup is not True:
            _fail("controlled supervisor child lacks passing cleanup")
    elif classification == "spawn_error":
        if cleanup is not None:
            _fail("supervisor pre-child spawn error has non-null cleanup")
    elif cleanup not in {None, True}:
        _fail("normal supervisor cleanup is not null or true")
    if classification == "verifier_timeout_124":
        if exit_code != 124 or timed_out is not True:
            _fail("supervisor timeout evidence is invalid")
    elif classification == "stdout_limit":
        if len(stdout) != _STDOUT_CAP_BYTES or (timed_out and exit_code != 124):
            _fail("supervisor stdout-limit evidence is invalid")
    elif classification == "stderr_limit":
        if len(stderr) != _STDERR_CAP_BYTES or (timed_out and exit_code != 124):
            _fail("supervisor stderr-limit evidence is invalid")
    elif classification == "spawn_error":
        if exit_code is not None or stdout or stderr or timed_out is not False:
            _fail("supervisor spawn-error evidence is invalid")
    elif classification == "post_spawn_initialization_failed":
        if stdout or stderr or timed_out is not False:
            _fail("supervisor post-spawn initialization evidence is invalid")
    elif classification == "stream_capture_failed":
        if (timed_out and exit_code != 124) or (not timed_out and exit_code is None):
            _fail("supervisor stream-capture evidence is invalid")
    elif classification == "child_cleanup_failed":
        pass
    elif timed_out is not False:
        _fail("non-timeout supervisor classification is marked timed out")
    if classification == "remote_receipt_missing" and remote_raw_sha256 is not None:
        _fail("supervisor classifies an existing remote receipt as missing")
    status = value["status"]
    if status == "completed":
        if (
            classification != "verifier_completed"
            or not start_valid
            or remote_value is None
            or stdout
            or stderr
        ):
            _fail("completed supervisor receipt lacks complete matching child evidence")
        remote_status = remote_value["status"]
        if not (
            (exit_code == 0 and remote_status == "verified")
            or (exit_code == 1 and remote_status == "failed")
        ):
            _fail("completed supervisor exit does not correspond to remote status")
    elif status == "failed":
        if classification == "verifier_completed":
            _fail("failed supervisor receipt uses completed classification")
    else:
        _fail("remote supervisor status is invalid")
    return value, hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class _SourceArtifact:
    path: Path
    exists: bool
    read_status: str
    raw: bytes | None
    sha256: str | None


def _source_artifact(path: Path, name: str) -> _SourceArtifact:
    state = _artifact_state(path, name, maximum=_REMOTE_ARTIFACT_LIMIT)
    return _SourceArtifact(
        path=path,
        exists=state.exists,
        read_status=state.read_status,
        raw=state.raw,
        sha256=state.sha256,
    )


def _validate_arm_invocation(args: argparse.Namespace, context: _ArmContext) -> None:
    if (
        str(args.windows_claim) != _WINDOWS_CLAIM
        or str(args.windows_verifier_start_claim) != _WINDOWS_START_CLAIM
        or str(args.windows_remote_receipt) != _WINDOWS_REMOTE_RECEIPT
        or str(args.windows_supervisor_receipt) != _WINDOWS_SUPERVISOR_RECEIPT
        or str(args.arm_receipt) != _ARM_RECEIPT
    ):
        _fail("arm remote-source/destination argv differs from P8")
    if context.registration.execution["arm_argv"] != _expected_arm_argv():
        _fail("registered arm argv differs from P8")


def _arm(args: argparse.Namespace) -> int:
    context = _validate_prepared_state(args)
    _validate_arm_invocation(args, context)
    destination_paths = {
        "claim": context.execution_root / "remote-verification-claim.json",
        "start": context.execution_root / "remote-verifier-start-claim.json",
        "remote": context.execution_root / "remote-verification.json",
        "supervisor": context.execution_root / "remote-verification-supervisor.json",
    }
    arm_receipt_path = Path(args.arm_receipt)
    _assert_absent(arm_receipt_path, "arm receipt")
    for name, path in destination_paths.items():
        _assert_absent(path, f"immutable Linux {name} artifact")

    sources = {
        "claim": _source_artifact(Path(args.windows_claim), "Windows lifecycle claim"),
        "start": _source_artifact(Path(args.windows_verifier_start_claim), "Windows verifier-start claim"),
        "remote": _source_artifact(Path(args.windows_remote_receipt), "Windows remote receipt"),
        "supervisor": _source_artifact(Path(args.windows_supervisor_receipt), "Windows supervisor receipt"),
    }
    # Preserve every complete, readable, in-cap Windows artifact before applying
    # semantic validity.  Downstream consumers must observe the immutable raw
    # evidence even when that evidence is malformed or cross-mismatched.
    available_raw = {
        name: artifact.raw
        for name, artifact in sources.items()
        if artifact.raw is not None
    }
    errors: list[str] = list(context.evidence_errors)
    claim_value: Mapping[str, Any] | None = None
    claim_sha: str | None = None
    if sources["claim"].raw is not None:
        try:
            claim_value, claim_sha = _validate_lifecycle_claim(sources["claim"].raw, context)
        except ProtocolError as error:
            errors.append(f"claim: {error}")
    elif sources["claim"].exists:
        errors.append(f"claim: {sources['claim'].read_status}")
    else:
        errors.append("claim: absent")

    start_value: Mapping[str, Any] | None = None
    start_sha: str | None = None
    if claim_sha is not None and sources["start"].raw is not None:
        try:
            start_value, start_sha = _validate_start_claim(
                sources["start"].raw,
                context,
                claim_sha,
            )
        except ProtocolError as error:
            errors.append(f"verifier-start claim: {error}")
    elif sources["start"].exists:
        errors.append(
            f"verifier-start claim: {sources['start'].read_status} or lacks a valid claim"
        )

    remote_value: Mapping[str, Any] | None = None
    remote_sha: str | None = None
    if claim_sha is not None and start_sha is not None and sources["remote"].raw is not None:
        try:
            remote_value, remote_sha = _validate_remote_receipt(
                sources["remote"].raw,
                context,
                claim_sha,
                start_sha,
            )
        except ProtocolError as error:
            errors.append(f"remote receipt: {error}")
    elif sources["remote"].exists:
        errors.append(
            f"remote receipt: {sources['remote'].read_status} or lacks valid claims"
        )

    supervisor_value: Mapping[str, Any] | None = None
    supervisor_sha: str | None = None
    if claim_sha is not None and sources["supervisor"].raw is not None:
        try:
            supervisor_value, supervisor_sha = _validate_supervisor_receipt(
                sources["supervisor"].raw,
                context,
                claim_sha256=claim_sha,
                start_raw_sha256=sources["start"].sha256,
                remote_raw_sha256=sources["remote"].sha256,
                start_valid=start_value is not None,
                remote_value=remote_value,
            )
        except ProtocolError as error:
            errors.append(f"supervisor receipt: {error}")
    elif sources["supervisor"].exists:
        errors.append(
            f"supervisor receipt: {sources['supervisor'].read_status} or lacks a valid claim"
        )
    else:
        errors.append("supervisor receipt: absent")

    for name in ("claim", "start", "remote", "supervisor"):
        raw = available_raw.get(name)
        if raw is not None:
            _publish_bytes_exclusive(
                destination_paths[name],
                raw,
                f"remote-{name}",
            )
    armed = (
        context.preparation_valid
        and context.preparation_verification_valid
        and claim_value is not None
        and start_value is not None
        and remote_value is not None
        and supervisor_value is not None
        and remote_value["status"] == "verified"
        and supervisor_value["status"] == "completed"
        and supervisor_sha == sources["supervisor"].sha256
        and remote_sha == sources["remote"].sha256
    )
    receipt = {
        "schema_version": _ARM_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": context.open_commit,
        "registration_content_sha256": context.registration.content_sha256,
        "preparation_receipt_exists": context.preparation.exists,
        "preparation_receipt_read_status": context.preparation.read_status,
        "preparation_receipt_sha256": context.preparation.sha256,
        "preparation_verification_receipt_exists": context.preparation_verification.exists,
        "preparation_verification_receipt_read_status": (
            context.preparation_verification.read_status
        ),
        "preparation_verification_receipt_sha256": (
            context.preparation_verification.sha256
        ),
        "remote_claim_sha256": sources["claim"].sha256,
        "remote_verifier_claim_sha256": sources["start"].sha256,
        "remote_receipt_sha256": sources["remote"].sha256,
        "remote_supervisor_receipt_sha256": sources["supervisor"].sha256,
        "status": "armed" if armed else "failed",
    }
    _require_keys(receipt, _ARM_KEYS, "constructed arm receipt")
    _publish_bytes_exclusive(
        arm_receipt_path,
        canonical_json_bytes(receipt),
        "arm-receipt",
    )
    if not armed:
        sys.stderr.buffer.write(
            canonical_json_bytes({"errors": errors, "status": "arm_failed"}) + b"\n"
        )
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    prepare = subparsers.add_parser("prepare", help="materialize and atomically promote A/B")
    prepare.add_argument("--repository-root", type=Path, required=True)
    prepare.add_argument("--registration", type=Path, required=True)
    prepare.add_argument("--execution-root", type=Path, required=True)
    prepare.add_argument("--receipt", type=Path, required=True)

    arm = subparsers.add_parser("arm", help="validate/copy Windows evidence and publish arm receipt")
    arm.add_argument("--repository-root", type=Path, required=True)
    arm.add_argument("--registration", type=Path, required=True)
    arm.add_argument("--execution-root", type=Path, required=True)
    arm.add_argument("--preparation-receipt", type=Path, required=True)
    arm.add_argument("--preparation-verification-receipt", type=Path, required=True)
    arm.add_argument("--windows-claim", type=Path, required=True)
    arm.add_argument("--windows-verifier-start-claim", type=Path, required=True)
    arm.add_argument("--windows-remote-receipt", type=Path, required=True)
    arm.add_argument("--windows-supervisor-receipt", type=Path, required=True)
    arm.add_argument("--arm-receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode == "prepare":
        return _prepare(args)
    if args.mode == "arm":
        return _arm(args)
    _fail("unknown preparation mode")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProtocolError, OSError, ValueError, json.JSONDecodeError) as error:
        sys.stderr.buffer.write(
            canonical_json_bytes({"error": str(error), "status": "refused"}) + b"\n"
        )
        raise SystemExit(2) from error
