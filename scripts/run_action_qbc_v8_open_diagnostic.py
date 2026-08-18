"""Run one frozen ARC action-QBC v8 open diagnostic observation.

This entry point deliberately performs every administrative check and acquires the
one-shot scientific-start claim before importing the v8 scientific audit module.
"""

from __future__ import annotations

import argparse
import csv
import email.policy
import hashlib
import importlib
import importlib.util
import io
import json
import os
import posixpath
import re
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, NoReturn

_TREATMENT_ID = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_REGISTRATION_SCHEMA = "action-qbc-v8-open-registration-v1"
_PREPARATION_SCHEMA = "action-qbc-v8-preparation-receipt-v2"
_PREPARATION_VERIFICATION_SCHEMA = (
    "action-qbc-v8-preparation-verification-receipt-v1"
)
_ARM_SCHEMA = "action-qbc-v8-arm-receipt-v2"
_DRIVER_SCHEMA = "action-qbc-v8-lifecycle-driver-claim-v1"
_START_SCHEMA = "action-qbc-v8-scientific-start-claim-v1"
_VALIDATOR_SCHEMA = "action-qbc-v8-payload-validator-claim-v1"
_VALIDATION_SCHEMA = "action-qbc-v8-payload-validation-receipt-v1"
_OPEN_FREEZE_TAG = "action-qbc-v8-open-diagnostic-freeze-v3"
_PREREGISTRATION_COMMIT = "61cebe90a2f4f7c78ec45119de53a482ed13a655"
_PREREGISTRATION_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v6"
_P8V4_COMMIT = "e0bff9ffc185196cafa938c8f7c9a7186366258b"
_P8V4_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
_O8V1_COMMIT = "7685fbdccd41702216b3a3f06d2a0ac699aca7ec"
_O8V1_TAG = "action-qbc-v8-open-diagnostic-freeze-v1"
_O8V1_TREE = "9b9ad5ba986afacbcdb1fde3cd69e0f1c94efdf2"
_P8V5_COMMIT = "09f9caea346866a1acf35c20e0c9d937096b5ce3"
_P8V5_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v5"
_P8V5_DOCUMENT = (
    "docs/experiment_amendment_2026-08-18_"
    "action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
)
_P8V5_DOCUMENT_BLOB = "7c0955a775af89dcfcde4796a9bbb4d470669d10"
_P8V5_DOCUMENT_SHA256 = (
    "cc9d787a64700332a44f543e7a949ee5522c3663b6b0eb54e418840e560cfe6d"
)
_P8V5_DOCUMENT_BYTE_COUNT = 25_872
_P8V5_TREE = "47a978cdd887fd6dc1cb5e80e36aa3e0a5a29253"
_O8V2_COMMIT = "8da637a47de0c88f917f222e52e54b342d729be9"
_O8V2_TAG = "action-qbc-v8-open-diagnostic-freeze-v2"
_O8V2_TREE = "247eba59e1e2ac9b0611c0e361de945dae0f2dc8"
_PREREGISTRATION_V3_COMMIT = "996ab2bb5a24143a110673977f63e7d111cf2060"
_PREREGISTRATION_V3_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
_PREREGISTRATION_V2_COMMIT = "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
_PREREGISTRATION_V2_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
_PREREGISTRATION_V1_COMMIT = "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
_PREREGISTRATION_V1_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
_PREREGISTRATION_DOCUMENT = (
    "docs/experiment_amendment_2026-08-18_"
    "action_qbc_v8_open_bounded_remote_verification_v6_runner_manifest_key_recovery.md"
)
_PREREGISTRATION_DOCUMENT_BLOB = "5e870ed0bbbff6fcb4352f6e914d870254773f68"
_PREREGISTRATION_DOCUMENT_SHA256 = (
    "0ba4cc55ca2b31433bc458972ffc32d87f84b610673fa22ed2b4dd4a8bfc1a41"
)
_PREREGISTRATION_DOCUMENT_BYTE_COUNT = 32_370
_PREREGISTRATION_TREE = "65695876c44eeb8cac5437149384071f88ff6018"
_R7_COMMIT = "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
_PREPARATION_SOURCE_URL = (
    "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi"
)
_COMPUTE_SECONDS = 2100
_WALL_SECONDS = 2400
_HARD_SECONDS = 2700
_PAYLOAD_CAP_BYTES = 67_108_864
_MAX_ADMIN_BYTES = 67_108_864
_GIT_TIMEOUT_SECONDS = 60
_EXPECTED_SCRIPT = "scripts/run_action_qbc_v8_open_diagnostic.py"
_EXPECTED_REGISTRATION = "artifacts/action_qbc_v8_open_registration.json"
_O8_ADDITIONS = {
    _EXPECTED_REGISTRATION,
    "docs/action_qbc_v8_open_diagnostic_runbook.md",
    "scripts/build_action_qbc_v8_open_registration.py",
    "scripts/execute_action_qbc_v8_open_lifecycle.py",
    "scripts/finalize_action_qbc_v8_open_diagnostic.py",
    "scripts/prepare_action_qbc_v8_open.py",
    "scripts/reconstruct_action_qbc_v8_open_registration.py",
    _EXPECTED_SCRIPT,
    "scripts/supervise_action_qbc_v8_remote_tag.py",
    "scripts/validate_action_qbc_v8_open_payload.py",
    "scripts/verify_action_qbc_v8_remote_tag.py",
    "src/arc3_voi/action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_lifecycle.py",
    "tests/test_action_qbc_v8_registration.py",
}
_EXECUTION_ROOT_TEXT = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"
_EXECUTION_ROOT = Path(_EXECUTION_ROOT_TEXT)
_PREPARATION_RECEIPT = f"{_EXECUTION_ROOT_TEXT}/preparation-receipt.json"
_PREPARATION_VERIFICATION_RECEIPT = (
    f"{_EXECUTION_ROOT_TEXT}/preparation-verification.json"
)
_ARM_RECEIPT = f"{_EXECUTION_ROOT_TEXT}/arm-receipt.json"
_DRIVER_CLAIM = f"{_EXECUTION_ROOT_TEXT}/lifecycle-driver-claim.json"
_PROCESS = {
    "A": {
        "root": f"{_EXECUTION_ROOT_TEXT}/processes/process-a",
        "output": (
            f"{_EXECUTION_ROOT_TEXT}/processes/process-a-output/open/"
            "action_qbc_v8_open_diagnostic.json"
        ),
        "start_claim": f"{_EXECUTION_ROOT_TEXT}/process-a-start-claim.json",
        "validator_claim": f"{_EXECUTION_ROOT_TEXT}/process-a-validator-claim.json",
        "validation_receipt": f"{_EXECUTION_ROOT_TEXT}/process-a-validation.json",
        "prior": "null",
    },
    "B": {
        "root": f"{_EXECUTION_ROOT_TEXT}/processes/process-b",
        "output": (
            f"{_EXECUTION_ROOT_TEXT}/processes/process-b-output/open/"
            "action_qbc_v8_open_diagnostic.json"
        ),
        "start_claim": f"{_EXECUTION_ROOT_TEXT}/process-b-start-claim.json",
        "validator_claim": f"{_EXECUTION_ROOT_TEXT}/process-b-validator-claim.json",
        "validation_receipt": f"{_EXECUTION_ROOT_TEXT}/process-b-validation.json",
        "prior": f"{_EXECUTION_ROOT_TEXT}/process-a-validation.json",
    },
}
_WINDOWS_REPOSITORY_CONTRACT = {
    "active_hooks_allowed": False,
    "common_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "forbidden_admin_relative_paths": [
        r".git\commondir",
        r".git\config.worktree",
        r".git\index.lock",
        r".git\info\attributes",
        r".git\info\grafts",
        r".git\info\sparse-checkout",
        r".git\objects\info\alternates",
        r".git\objects\info\http-alternates",
        r".git\refs\replace",
        r".git\shallow",
    ],
    "forbidden_pack_suffixes": [".promisor"],
    "forbidden_ref_prefixes": ["refs/replace/"],
    "git_config_byte_count": 846,
    "git_config_sha256": (
        "a78fd50c029f9b0755a7fceac2b77a39479c30becb2eff1794d77df5d185f702"
    ),
    "git_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "index_path": r"D:\kaggle competitions\arc3-crosslevel-voi\.git\index",
    "info_exclude_byte_count": 240,
    "info_exclude_sha256": (
        "6671fe83b7a07c8932ee89164d1f2793b2318058eb8b98dc5c06ee0a5a3b0ec1"
    ),
    "local_config": {
        "branch.action-qbc-v6-prereg.merge": "refs/heads/action-qbc-v6-prereg",
        "branch.action-qbc-v6-prereg.remote": "origin",
        "branch.action-qbc-v7-open-diagnostic.merge": (
            "refs/heads/action-qbc-v7-open-diagnostic"
        ),
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
        "core.sshcommand": (
            "ssh -i .git/arc3_crosslevel_voi_deploy_key -o IdentitiesOnly=yes "
            "-o UserKnownHostsFile=.git/github_known_hosts "
            "-o StrictHostKeyChecking=yes"
        ),
        "core.symlinks": "false",
        "remote.origin.fetch": "+refs/heads/*:refs/remotes/origin/*",
        "remote.origin.url": (
            "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
        ),
    },
    "plain_admin_relative_directories": [
        ".git",
        r".git\hooks",
        r".git\info",
        r".git\objects",
        r".git\objects\info",
        r".git\objects\pack",
        r".git\refs",
    ],
    "repository_ancestor_chain": [
        "D:\\",
        r"D:\kaggle competitions",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
    ],
    "repository_root": r"D:\kaggle competitions\arc3-crosslevel-voi",
}
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
_ARM_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "preparation_receipt_exists",
    "preparation_receipt_read_status",
    "preparation_receipt_sha256",
    "preparation_verification_receipt_exists",
    "preparation_verification_receipt_read_status",
    "preparation_verification_receipt_sha256",
    "remote_claim_sha256",
    "remote_verifier_claim_sha256",
    "remote_receipt_sha256",
    "remote_supervisor_receipt_sha256",
    "status",
}
_PREPARATION_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "attempts",
    "authority",
    "process_a",
    "process_b",
    "command_ledger",
    "commands_sha256",
    "command_environment_sha256",
    "status",
}
_PREPARATION_VERIFICATION_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "preparation_receipt_sha256",
    "verification_argv_sha256",
    "authority",
    "process_a",
    "process_b",
    "status",
    "content_sha256",
}
_PREPARATION_CLONE_KEYS = {
    "root",
    "root_device",
    "root_inode",
    "root_owner_uid",
    "root_mode",
    "head_sha",
    "tree_sha256",
    "raw_materialization_sha256",
    "git_status_sha256",
    "python_version",
    "uv_version",
    "environment_inventory",
    "environment_inventory_sha256",
    "venv_materialization_sha256",
    "venv_python_sha256",
    "passes",
}
_VERIFICATION_CLONE_KEYS = _PREPARATION_CLONE_KEYS - {"environment_inventory"}
_COMMAND_LEDGER_KEYS = {
    "sequence_index",
    "attempt_index",
    "label",
    "phase",
    "cwd",
    "argv",
    "argv_sha256",
    "stdin_size_bytes",
    "stdin_sha256",
    "started",
    "exit_code",
    "outcome",
    "timed_out",
    "duration_milliseconds",
    "stdout_size_bytes",
    "stdout_sha256",
    "stderr_size_bytes",
    "stderr_sha256",
    "child_cleanup_passes",
}
_COMMAND_IDENTITY_KEYS = {
    "attempt_index",
    "label",
    "phase",
    "cwd",
    "argv",
    "argv_sha256",
    "stdin_size_bytes",
    "stdin_sha256",
}
_ATTEMPT_KEYS = {
    "attempt_index",
    "process_a_stage",
    "process_b_stage",
    "cleanup",
    "promotion",
    "passes",
}
_CLEANUP_KEYS = {"owned_paths", "removed", "passes"}
_PROMOTION_KEYS = {
    "source_path",
    "destination_path",
    "source_device",
    "source_inode",
    "passes",
}
_PROCESS_STAGES = {
    "not_started",
    "clone_failed",
    "raw_audit_failed",
    "environment_failed",
    "preflight_failed",
    "completed",
}
_EXECUTION_KEYS = {
    "administrative_stage_order",
    "argv_hashes",
    "arm_argv",
    "arm_receipt_path",
    "arm_timeout_seconds",
    "authority_root",
    "bootstrap_steps",
    "compute_deadline_seconds",
    "environment_build_argv",
    "emergency_bundle_path",
    "execution_root",
    "finalization_bundle_path",
    "linux_host_launcher",
    "linux_platform",
    "linux_tool_identities",
    "lifecycle_driver_argv",
    "lifecycle_driver_claim_path",
    "driver_deadline_seconds",
    "lifecycle_ledger_path",
    "local_git_timeout_seconds",
    "finalizer_argv_template",
    "finalizer_cwd",
    "finalizer_timeout_seconds",
    "hard_timeout_seconds",
    "payload_validator_argv_template",
    "payload_validator_timeout_seconds",
    "preflight_argvs",
    "post_preparation_validation_argv",
    "preparation_argv",
    "preparation_receipt_path",
    "preparation_verification_receipt_path",
    "preparation_command_environment",
    "preparation_command_policy",
    "process_a_output",
    "process_a_root",
    "process_a_start_claim",
    "process_a_validation_receipt",
    "process_a_validator_claim",
    "process_b_output",
    "process_b_root",
    "process_b_start_claim",
    "process_b_validation_receipt",
    "process_b_validator_claim",
    "process_labels",
    "producer_argv",
    "reconstructor_argv",
    "registered_start_count",
    "remote_claim_linux_path",
    "remote_claim_windows_path",
    "remote_policy",
    "remote_receipt_linux_path",
    "remote_receipt_windows_path",
    "remote_supervisor_argv",
    "remote_supervisor_receipt_linux_path",
    "remote_supervisor_receipt_windows_path",
    "remote_verifier_claim_linux_path",
    "remote_verifier_claim_windows_path",
    "remote_verifier_argv",
    "result_document_contract",
    "result_git_environment",
    "result_git_max_attempts",
    "result_git_owner_path",
    "result_git_work_root",
    "result_publisher_argv",
    "result_ref_transaction",
    "scientific_argv_template",
    "test_argvs",
    "third_start_allowed",
    "wall_time_seconds",
    "windows_repository_contract",
}
_ARGV_HASH_FIELDS = {
    "arm": "arm_argv",
    "bootstrap": "bootstrap_steps",
    "environment_build": "environment_build_argv",
    "finalizer": "finalizer_argv_template",
    "lifecycle_driver": "lifecycle_driver_argv",
    "linux_host_launcher": "linux_host_launcher",
    "payload_validator": "payload_validator_argv_template",
    "post_preparation_validation": "post_preparation_validation_argv",
    "preflight": "preflight_argvs",
    "preparation": "preparation_argv",
    "producer": "producer_argv",
    "reconstructor": "reconstructor_argv",
    "remote_supervisor": "remote_supervisor_argv",
    "remote_verifier": "remote_verifier_argv",
    "result_publisher": "result_publisher_argv",
    "result_ref_transaction": "result_ref_transaction",
    "scientific": "scientific_argv_template",
    "tests": "test_argvs",
}
_DISTRIBUTION_KEYS = {
    "normalized_name",
    "version",
    "file_count",
    "files_sha256",
}
_DRIVER_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "remote_claim_sha256",
    "driver_argv_sha256",
}
_START_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "arm_receipt_sha256",
    "lifecycle_driver_claim_sha256",
    "scientific_argv_sha256",
    "prior_validation_receipt_sha256",
    "output_path",
}
_VALIDATOR_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "lifecycle_driver_claim_sha256",
    "start_claim_sha256",
    "validator_argv_sha256",
    "payload_sha256",
}
_VALIDATION_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "start_claim_sha256",
    "validator_claim_sha256",
    "payload_path",
    "payload_sha256",
    "payload_size_bytes",
    "status",
}


class _AdministrativeFailure(RuntimeError):
    """A failure that must not be converted into scientific evidence."""


@dataclass(frozen=True)
class _DirectoryAnchor:
    path: Path
    descriptor: int
    device: int
    inode: int
    owner_uid: int
    mode: int
    name: str


@dataclass(frozen=True)
class _OwnedFileIdentity:
    device: int
    inode: int
    owner_uid: int
    mode: int
    size: int


def _fail(message: str) -> NoReturn:
    raise _AdministrativeFailure(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_canonical(data: bytes, name: str, *, maximum: int = _MAX_ADMIN_BYTES) -> dict[str, Any]:
    if len(data) > maximum:
        _fail(f"{name} exceeds its byte limit")
    try:
        value = json.loads(
            data.decode("ascii"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise _AdministrativeFailure(f"{name} is not strict ASCII JSON") from exc
    if not isinstance(value, dict) or _canonical_json_bytes(value) != data:
        _fail(f"{name} is not a canonical JSON object")
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


def _permitted_plain_metadata(
    metadata: os.stat_result, maximum: int
) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_point(metadata)
        and 0 <= metadata.st_size <= maximum
    )


def _bounded_descriptor_bytes(descriptor: int, maximum: int, name: str) -> bytes:
    data = bytearray()
    while True:
        allowance = maximum + 1 - len(data)
        if allowance <= 0:
            _fail(f"{name} exceeds its byte limit")
        chunk = os.read(descriptor, min(1 << 20, allowance))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > maximum:
            _fail(f"{name} exceeds its byte limit")


def _plain_file_bytes(path: Path, name: str, *, maximum: int = _MAX_ADMIN_BYTES) -> bytes:
    try:
        before_path = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(before_path, maximum):
        _fail(f"{name} is not a plain file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be safely opened") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not _permitted_plain_metadata(opened, maximum)
            or _file_identity(before_path) != _file_identity(opened)
            or _file_change_identity(before_path) != _file_change_identity(opened)
        ):
            _fail(f"{name} changed before it was opened")
        data = _bounded_descriptor_bytes(descriptor, maximum, name)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _bounded_descriptor_bytes(descriptor, maximum, name) != data:
            _fail(f"{name} changed between descriptor reads")
        after_descriptor = os.fstat(descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be read") from exc
    finally:
        os.close(descriptor)
    try:
        after_path = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} changed while being read") from exc
    if (
        not _permitted_plain_metadata(after_descriptor, maximum)
        or not _permitted_plain_metadata(after_path, maximum)
        or _file_identity(opened) != _file_identity(after_descriptor)
        or _file_identity(after_descriptor) != _file_identity(after_path)
        or _file_change_identity(opened) != _file_change_identity(after_descriptor)
        or _file_change_identity(after_descriptor) != _file_change_identity(after_path)
        or len(data) != after_descriptor.st_size
    ):
        _fail(f"{name} changed while being read")
    return data


def _single_component(value: str, name: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        _fail(f"{name} is not a safe single path component")
    return value


def _open_absolute_directory(path: Path, name: str) -> int:
    if not path.is_absolute():
        _fail(f"{name} is not absolute")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    if os.name == "nt":
        try:
            return os.open(path, flags)
        except OSError as exc:
            raise _AdministrativeFailure(f"{name} cannot be safely opened") from exc
    try:
        descriptor = os.open("/", flags)
    except OSError as exc:
        raise _AdministrativeFailure("filesystem root cannot be safely opened") from exc
    try:
        for raw_component in path.parts[1:]:
            component = _single_component(raw_component, name)
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            _fail(f"{name} is not a plain directory")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _directory_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        getattr(metadata, "st_uid", -1),
        stat.S_IMODE(metadata.st_mode),
    )


def _open_directory_anchor(
    path: Path,
    name: str,
    *,
    empty: bool = False,
) -> _DirectoryAnchor:
    descriptor = _open_absolute_directory(path, name)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or (os.name != "nt" and stat.S_IMODE(metadata.st_mode) != 0o700)
            or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
            or (empty and os.listdir(descriptor))
        ):
            _fail(f"{name} is not an owner-controlled mode-0700 directory")
        anchor = _DirectoryAnchor(
            path=path,
            descriptor=descriptor,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            owner_uid=getattr(metadata, "st_uid", -1),
            mode=stat.S_IMODE(metadata.st_mode),
            name=name,
        )
        _revalidate_directory_anchor(anchor, empty=empty)
        return anchor
    except Exception:
        os.close(descriptor)
        raise


def _revalidate_directory_anchor(
    anchor: _DirectoryAnchor,
    *,
    empty: bool = False,
) -> None:
    expected = (anchor.device, anchor.inode, anchor.owner_uid, anchor.mode)
    try:
        held = os.fstat(anchor.descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{anchor.name} anchor is unavailable") from exc
    if (
        not stat.S_ISDIR(held.st_mode)
        or stat.S_ISLNK(held.st_mode)
        or _directory_identity(held) != expected
        or (empty and os.listdir(anchor.descriptor))
    ):
        _fail(f"{anchor.name} retained directory identity changed")
    reopened = _open_absolute_directory(anchor.path, f"{anchor.name} fixed path")
    try:
        current = os.fstat(reopened)
        if (
            not stat.S_ISDIR(current.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or _directory_identity(current) != expected
        ):
            _fail(f"{anchor.name} fixed path no longer names the retained directory")
    finally:
        os.close(reopened)


def _owned_file_identity(metadata: os.stat_result) -> _OwnedFileIdentity:
    return _OwnedFileIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        owner_uid=getattr(metadata, "st_uid", -1),
        mode=stat.S_IMODE(metadata.st_mode),
        size=metadata.st_size,
    )


def _matches_owned_file(
    metadata: os.stat_result,
    identity: _OwnedFileIdentity,
    *,
    links: int,
) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_point(metadata)
        and _owned_file_identity(metadata) == identity
        and metadata.st_nlink == links
        and (os.name == "nt" or identity.mode == 0o600)
        and (not hasattr(os, "getuid") or identity.owner_uid == os.getuid())
    )


def _plain_file_bytes_at(
    parent_descriptor: int,
    component: str,
    name: str,
    *,
    maximum: int = _MAX_ADMIN_BYTES,
) -> bytes:
    component = _single_component(component, name)
    try:
        before = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(before, maximum):
        _fail(f"{name} is not a plain file")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(component, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be safely opened") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not _permitted_plain_metadata(opened, maximum)
            or _file_identity(before) != _file_identity(opened)
            or _file_change_identity(before) != _file_change_identity(opened)
        ):
            _fail(f"{name} changed before it was opened")
        data = _bounded_descriptor_bytes(descriptor, maximum, name)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _bounded_descriptor_bytes(descriptor, maximum, name) != data:
            _fail(f"{name} changed between descriptor reads")
        after_descriptor = os.fstat(descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be read") from exc
    finally:
        os.close(descriptor)
    try:
        after = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} changed while being read") from exc
    if (
        not _permitted_plain_metadata(after_descriptor, maximum)
        or not _permitted_plain_metadata(after, maximum)
        or _file_identity(opened) != _file_identity(after_descriptor)
        or _file_identity(after_descriptor) != _file_identity(after)
        or _file_change_identity(opened) != _file_change_identity(after_descriptor)
        or _file_change_identity(after_descriptor) != _file_change_identity(after)
        or len(data) != after_descriptor.st_size
    ):
        _fail(f"{name} changed while being read")
    return data


def _plain_file_identity_at(
    parent_descriptor: int,
    component: str,
    name: str,
) -> tuple[int, str]:
    component = _single_component(component, name)
    try:
        before = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} is unavailable") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or _is_reparse_point(before)
    ):
        _fail(f"{name} is not a plain file")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(component, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be safely opened") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_ISLNK(opened.st_mode)
            or _is_reparse_point(opened)
            or _file_identity(before) != _file_identity(opened)
            or _file_change_identity(before) != _file_change_identity(opened)
        ):
            _fail(f"{name} changed before it was opened")
        observations: list[tuple[int, str]] = []
        for _ in range(2):
            count = 0
            digest = hashlib.sha256()
            while True:
                chunk = os.read(descriptor, 1 << 20)
                if not chunk:
                    break
                count += len(chunk)
                if count > opened.st_size:
                    _fail(f"{name} grew while being hashed")
                digest.update(chunk)
            observations.append((count, digest.hexdigest()))
            os.lseek(descriptor, 0, os.SEEK_SET)
        after_descriptor = os.fstat(descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be hashed") from exc
    finally:
        os.close(descriptor)
    try:
        after = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} changed while being hashed") from exc
    if (
        observations[0] != observations[1]
        or observations[0][0] != opened.st_size
        or _file_identity(opened) != _file_identity(after_descriptor)
        or _file_identity(after_descriptor) != _file_identity(after)
        or _file_change_identity(opened) != _file_change_identity(after_descriptor)
        or _file_change_identity(after_descriptor) != _file_change_identity(after)
    ):
        _fail(f"{name} changed while being hashed")
    return observations[0]


def _open_child_directory(parent_descriptor: int, component: str, name: str) -> int:
    component = _single_component(component, name)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(component, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} cannot be safely opened") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        os.close(descriptor)
        _fail(f"{name} is not a plain directory")
    return descriptor


def _strict_utf8_component(value: str, name: str) -> bytes:
    _single_component(value, name)
    try:
        return value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise _AdministrativeFailure(f"{name} is not strict UTF-8") from exc


def _open_relative_directory(root_descriptor: int, components: Sequence[str], name: str) -> int:
    descriptor = os.dup(root_descriptor)
    try:
        for component in components:
            next_descriptor = _open_child_directory(descriptor, component, name)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _normalize_record_path(raw: str) -> tuple[str, ...]:
    try:
        raw.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise _AdministrativeFailure("RECORD path is not strict UTF-8") from exc
    if not raw or raw.startswith("/") or "\\" in raw or "\x00" in raw:
        _fail("RECORD path is not a safe relative path")
    normalized = posixpath.normpath(
        posixpath.join("lib/python3.12/site-packages", raw)
    )
    components = tuple(normalized.split("/"))
    if (
        normalized.startswith("../")
        or not components
        or any(component in {"", ".", ".."} for component in components)
    ):
        _fail("RECORD path escapes the virtual environment")
    for component in components:
        _strict_utf8_component(component, "RECORD path component")
    return components


def _read_relative_plain_identity(
    root_descriptor: int,
    components: Sequence[str],
    name: str,
) -> tuple[int, str]:
    if not components:
        _fail(f"{name} has no final component")
    parent = _open_relative_directory(root_descriptor, components[:-1], name)
    try:
        return _plain_file_identity_at(parent, components[-1], name)
    finally:
        os.close(parent)


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _compact_environment_inventory(root: Path) -> tuple[list[dict[str, Any]], str]:
    root_descriptor = _open_absolute_directory(root, "process root")
    try:
        venv_descriptor = _open_child_directory(
            root_descriptor, ".venv", "virtual environment"
        )
    finally:
        os.close(root_descriptor)
    try:
        site_descriptor = _open_relative_directory(
            venv_descriptor,
            ("lib", "python3.12", "site-packages"),
            "site-packages",
        )
        try:
            try:
                dist_names = sorted(
                    (
                        entry.name
                        for entry in os.scandir(site_descriptor)
                        if entry.name.endswith(".dist-info")
                    ),
                    key=lambda item: _strict_utf8_component(
                        item, "distribution metadata name"
                    ),
                )
            except OSError as exc:
                raise _AdministrativeFailure(
                    "installed distributions cannot be enumerated"
                ) from exc
            inventory: list[dict[str, Any]] = []
            observed_names: set[str] = set()
            observed_paths: set[str] = set()
            for dist_name in dist_names:
                dist_descriptor = _open_child_directory(
                    site_descriptor,
                    dist_name,
                    f"distribution metadata {dist_name}",
                )
                try:
                    metadata_raw = _plain_file_bytes_at(
                        dist_descriptor,
                        "METADATA",
                        f"{dist_name}/METADATA",
                    )
                    record_raw = _plain_file_bytes_at(
                        dist_descriptor,
                        "RECORD",
                        f"{dist_name}/RECORD",
                    )
                finally:
                    os.close(dist_descriptor)
                try:
                    metadata = BytesParser(policy=email.policy.compat32).parsebytes(
                        metadata_raw
                    )
                    record_text = record_raw.decode("utf-8", "strict")
                    rows = list(csv.reader(io.StringIO(record_text, newline="")))
                except (TypeError, ValueError, UnicodeDecodeError, csv.Error) as exc:
                    raise _AdministrativeFailure(
                        f"distribution metadata is invalid: {dist_name}"
                    ) from exc
                raw_name = metadata.get("Name")
                raw_version = metadata.get("Version")
                if not isinstance(raw_name, str) or not isinstance(raw_version, str):
                    _fail(f"distribution lacks Name/Version: {dist_name}")
                normalized_name = _normalize_distribution_name(raw_name)
                version = raw_version.strip()
                try:
                    (normalized_name + version).encode("ascii", "strict")
                except UnicodeEncodeError as exc:
                    raise _AdministrativeFailure(
                        f"distribution identity is not ASCII: {dist_name}"
                    ) from exc
                if (
                    not normalized_name
                    or not version
                    or normalized_name in observed_names
                ):
                    _fail(f"distribution identity is invalid: {dist_name}")
                observed_names.add(normalized_name)
                files: list[dict[str, Any]] = []
                for index, row in enumerate(rows):
                    if len(row) != 3 or not row[0]:
                        _fail(f"invalid RECORD row {index} for {dist_name}")
                    components = _normalize_record_path(row[0])
                    relative = "/".join(components)
                    if relative in observed_paths:
                        _fail(f"duplicate normalized RECORD path: {relative}")
                    observed_paths.add(relative)
                    size, digest = _read_relative_plain_identity(
                        venv_descriptor,
                        components,
                        f"RECORD path {relative}",
                    )
                    files.append(
                        {"path": relative, "size_bytes": size, "sha256": digest}
                    )
                files.sort(key=lambda row: str(row["path"]).encode("utf-8"))
                inventory.append(
                    {
                        "normalized_name": normalized_name,
                        "version": version,
                        "file_count": len(files),
                        "files_sha256": _sha256(_canonical_json_bytes(files)),
                    }
                )
        finally:
            os.close(site_descriptor)
    finally:
        os.close(venv_descriptor)
    inventory.sort(key=lambda row: str(row["normalized_name"]).encode("utf-8"))
    expected = {
        "arc3-crosslevel-voi": "0.1.0",
        "numpy": "2.5.1",
        "pyyaml": "6.0.3",
    }
    if {row["normalized_name"]: row["version"] for row in inventory} != expected:
        _fail("installed distributions differ from the frozen runtime lock")
    return inventory, _sha256(_canonical_json_bytes(inventory))


def _venv_materialization_sha256(root: Path) -> str:
    root_descriptor = _open_absolute_directory(root, "process root")
    try:
        venv_descriptor = _open_child_directory(
            root_descriptor, ".venv", "virtual environment"
        )
    finally:
        os.close(root_descriptor)
    entries: list[dict[str, Any]] = []

    def visit(directory_descriptor: int, prefix: tuple[str, ...]) -> None:
        try:
            children = sorted(
                list(os.scandir(directory_descriptor)),
                key=lambda entry: _strict_utf8_component(
                    entry.name, "virtual-environment entry"
                ),
            )
        except OSError as exc:
            raise _AdministrativeFailure(
                "virtual environment cannot be enumerated"
            ) from exc
        for child in children:
            component = child.name
            encoded = _strict_utf8_component(component, "virtual-environment entry")
            del encoded
            components = (*prefix, component)
            relative = "/".join(components)
            try:
                metadata = os.stat(
                    component,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise _AdministrativeFailure(
                    f"virtual-environment entry is unavailable: {relative}"
                ) from exc
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                entries.append(
                    {
                        "path": relative,
                        "type": "directory",
                        "mode": mode,
                        "size_bytes": None,
                        "sha256": None,
                        "symlink_target": None,
                    }
                )
                child_descriptor = _open_child_directory(
                    directory_descriptor,
                    component,
                    f"virtual-environment directory {relative}",
                )
                try:
                    visit(child_descriptor, components)
                finally:
                    os.close(child_descriptor)
            elif stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                size, digest = _plain_file_identity_at(
                    directory_descriptor,
                    component,
                    f"virtual-environment file {relative}",
                )
                entries.append(
                    {
                        "path": relative,
                        "type": "regular",
                        "mode": mode,
                        "size_bytes": size,
                        "sha256": digest,
                        "symlink_target": None,
                    }
                )
            elif stat.S_ISLNK(metadata.st_mode):
                try:
                    target = os.readlink(component, dir_fd=directory_descriptor)
                    target.encode("utf-8", "strict")
                except (OSError, UnicodeEncodeError) as exc:
                    raise _AdministrativeFailure(
                        f"virtual-environment symlink is invalid: {relative}"
                    ) from exc
                entries.append(
                    {
                        "path": relative,
                        "type": "symlink",
                        "mode": mode,
                        "size_bytes": None,
                        "sha256": None,
                        "symlink_target": target,
                    }
                )
            else:
                _fail(f"virtual environment has an unsafe entry: {relative}")

    try:
        visit(venv_descriptor, ())
    finally:
        os.close(venv_descriptor)
    entries.sort(key=lambda row: str(row["path"]).encode("utf-8"))
    paths = [str(row["path"]) for row in entries]
    if len(paths) != len(set(paths)):
        _fail("virtual-environment materialization has duplicate paths")
    return _sha256(_canonical_json_bytes(entries))


def _venv_python_sha256(root: Path) -> str:
    current = Path(os.path.abspath(root / ".venv/bin/python3"))
    visited: set[str] = set()
    for _ in range(41):
        identity = os.fspath(current)
        if identity in visited:
            _fail("venv Python link chain contains a cycle")
        visited.add(identity)
        try:
            metadata = current.stat(follow_symlinks=False)
        except OSError as exc:
            raise _AdministrativeFailure("venv Python link chain is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(current)
                target.encode("utf-8", "strict")
            except (OSError, UnicodeEncodeError) as exc:
                raise _AdministrativeFailure("venv Python link target is invalid") from exc
            current = Path(
                os.path.abspath(
                    target if os.path.isabs(target) else current.parent / target
                )
            )
            continue
        if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o111:
            _fail("resolved venv Python is not a regular executable")
        return _sha256(_plain_file_bytes(current, "resolved venv Python executable"))
    _fail("venv Python link chain exceeds forty links")


def _require_keys(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        _fail(f"{name} has an invalid key set")


def _require_sha(value: Any, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{name} is not lowercase hexadecimal")
    return value


def _validate_execution_contract(registration: Mapping[str, Any]) -> Mapping[str, Any]:
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping) or set(execution) != _EXECUTION_KEYS:
        _fail("registration execution contract does not have its exact P8v4 key set")
    argv_hashes = execution.get("argv_hashes")
    if not isinstance(argv_hashes, Mapping) or set(argv_hashes) != set(
        _ARGV_HASH_FIELDS
    ):
        _fail("registration argv-hash contract does not have its exact 18-key set")
    for hash_key, field in _ARGV_HASH_FIELDS.items():
        expected = _sha256(_canonical_json_bytes(execution.get(field)))
        if argv_hashes.get(hash_key) != expected:
            _fail(f"registration {hash_key} argv hash is invalid")

    root = _EXECUTION_ROOT_TEXT
    exact_values: dict[str, Any] = {
        "execution_root": root,
        "authority_root": f"{root}/authority",
        "preparation_receipt_path": _PREPARATION_RECEIPT,
        "preparation_verification_receipt_path": _PREPARATION_VERIFICATION_RECEIPT,
        "arm_receipt_path": _ARM_RECEIPT,
        "lifecycle_driver_claim_path": _DRIVER_CLAIM,
        "process_a_root": _PROCESS["A"]["root"],
        "process_a_output": _PROCESS["A"]["output"],
        "process_a_start_claim": _PROCESS["A"]["start_claim"],
        "process_a_validator_claim": _PROCESS["A"]["validator_claim"],
        "process_a_validation_receipt": _PROCESS["A"]["validation_receipt"],
        "process_b_root": _PROCESS["B"]["root"],
        "process_b_output": _PROCESS["B"]["output"],
        "process_b_start_claim": _PROCESS["B"]["start_claim"],
        "process_b_validator_claim": _PROCESS["B"]["validator_claim"],
        "process_b_validation_receipt": _PROCESS["B"]["validation_receipt"],
        "compute_deadline_seconds": _COMPUTE_SECONDS,
        "wall_time_seconds": _WALL_SECONDS,
        "hard_timeout_seconds": _HARD_SECONDS,
        "registered_start_count": 2,
        "process_labels": ["A", "B"],
        "third_start_allowed": False,
        "windows_repository_contract": _WINDOWS_REPOSITORY_CONTRACT,
        "arm_timeout_seconds": 120,
        "payload_validator_timeout_seconds": 300,
        "local_git_timeout_seconds": 60,
        "environment_build_argv": [
            "/usr/bin/env",
            "UV_OFFLINE=1",
            "/usr/local/bin/uv",
            "sync",
            "--python",
            "3.12.13",
            "--frozen",
            "--no-dev",
            "--offline",
        ],
        "preflight_argvs": [
            [
                "/usr/bin/git",
                "--no-replace-objects",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ],
            ["/usr/bin/git", "--no-replace-objects", "rev-parse", "HEAD"],
            [".venv/bin/python3", "--version"],
            ["/usr/local/bin/uv", "--version"],
            [
                "/usr/bin/python3",
                "-I",
                "-B",
                "scripts/reconstruct_action_qbc_v8_open_registration.py",
                "--repository-root",
                ".",
                "--registration",
                _EXPECTED_REGISTRATION,
                "--verify-open-freeze",
            ],
        ],
        "preparation_argv": [
            "/usr/bin/python3",
            "-I",
            "-B",
            "scripts/prepare_action_qbc_v8_open.py",
            "prepare",
            "--repository-root",
            ".",
            "--registration",
            _EXPECTED_REGISTRATION,
            "--execution-root",
            root,
            "--receipt",
            _PREPARATION_RECEIPT,
        ],
        "post_preparation_validation_argv": [
            "/usr/bin/python3",
            "-I",
            "-B",
            "scripts/reconstruct_action_qbc_v8_open_registration.py",
            "--repository-root",
            ".",
            "--registration",
            _EXPECTED_REGISTRATION,
            "--verify-preparation",
            "--preparation-receipt",
            _PREPARATION_RECEIPT,
            "--verification-receipt",
            _PREPARATION_VERIFICATION_RECEIPT,
        ],
        "scientific_argv_template": [
            "/usr/bin/timeout",
            "--signal=TERM",
            "--kill-after=15s",
            "2700s",
            ".venv/bin/python3",
            "-I",
            "-B",
            _EXPECTED_SCRIPT,
            "--repository-root",
            ".",
            "--registration",
            _EXPECTED_REGISTRATION,
            "--preparation-verification-receipt",
            _PREPARATION_VERIFICATION_RECEIPT,
            "--arm-receipt",
            _ARM_RECEIPT,
            "--driver-claim",
            _DRIVER_CLAIM,
            "--label",
            "<LABEL>",
            "--start-claim",
            "<START_CLAIM>",
            "--prior-validation-receipt",
            "<PRIOR_VALIDATION_OR_NULL>",
            "--compute-deadline-seconds",
            "2100",
            "--wall-time-seconds",
            "2400",
            "--output",
            "<OUTPUT_PATH>",
        ],
        "payload_validator_argv_template": [
            "/usr/bin/timeout",
            "--signal=TERM",
            "--kill-after=5s",
            "300s",
            ".venv/bin/python3",
            "-I",
            "-B",
            "scripts/validate_action_qbc_v8_open_payload.py",
            "--repository-root",
            ".",
            "--registration",
            _EXPECTED_REGISTRATION,
            "--arm-receipt",
            _ARM_RECEIPT,
            "--driver-claim",
            _DRIVER_CLAIM,
            "--label",
            "<LABEL>",
            "--start-claim",
            "<START_CLAIM>",
            "--validator-claim",
            "<VALIDATOR_CLAIM>",
            "--validation-receipt",
            "<VALIDATION_RECEIPT>",
            "--payload",
            "<OUTPUT_PATH>",
        ],
    }
    for field, expected in exact_values.items():
        if execution.get(field) != expected:
            _fail(f"registration execution field differs from P8v4: {field}")
    return execution


def _fixed_git_environment(root: Path) -> dict[str, str]:
    del root
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


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "--no-replace-objects", "-C", str(root), *arguments],
            cwd=root,
            env=_fixed_git_environment(root),
            input=input_bytes,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _AdministrativeFailure("registered local Git plumbing failed") from exc
    if completed.returncode != 0:
        _fail("registered local Git plumbing returned nonzero")
    return completed.stdout


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
        except OSError as exc:
            raise _AdministrativeFailure(
                "local Git object-pack directory is unavailable as a no-follow directory"
            ) from exc

        for descriptor in descriptors:
            try:
                metadata = os.fstat(descriptor)
            except OSError as exc:
                raise _AdministrativeFailure(
                    "cannot inspect local Git object-pack directory ancestry"
                ) from exc
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
        except OSError as exc:
            raise _AdministrativeFailure(
                "cannot inspect local Git object-pack directory"
            ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _validate_local_git_sources(root: Path) -> None:
    _validate_object_pack_sources(root)
    raw_config = _git(root, "config", "--local", "--null", "--list")
    records = raw_config.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    if all(b"\n" in record for record in records):
        raw_pairs = [record.split(b"\n", 1) for record in records]
    else:
        if len(records) % 2:
            _fail("local Git config NUL stream has an odd field count")
        raw_pairs = [list(pair) for pair in zip(records[0::2], records[1::2], strict=True)]
    observed: dict[str, str] = {}
    for raw_key, raw_value in raw_pairs:
        try:
            key = raw_key.decode("utf-8", "strict")
            value = raw_value.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise _AdministrativeFailure("local Git config is not UTF-8") from exc
        if not key or key in observed:
            _fail("local Git config has an empty or duplicate key")
        observed[key] = value
    expected = {
        "core.repositoryformatversion": "0",
        "core.filemode": "true",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "core.autocrlf": "false",
        "core.eol": "lf",
        "core.safecrlf": "true",
    }
    if observed != expected:
        _fail("local Git config differs from the closed P8v4 mapping")
    try:
        git_metadata = (root / ".git").stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure("Git administration directory is unavailable") from exc
    if (
        not stat.S_ISDIR(git_metadata.st_mode)
        or stat.S_ISLNK(git_metadata.st_mode)
        or (hasattr(os, "getuid") and git_metadata.st_uid != os.getuid())
    ):
        _fail("Git administration directory is unsafe")
    forbidden = (
        root / ".git/objects/info/alternates",
        root / ".git/objects/info/http-alternates",
        root / ".git/info/grafts",
        root / ".git/shallow",
    )
    if any(path.exists() or path.is_symlink() for path in forbidden):
        _fail("local Git repository has an alternate, graft, or shallow source")
    if _git(root, "for-each-ref", "--format=%(refname)", "refs/replace") != b"":
        _fail("local Git repository has replacement refs")


def _require_direct_child(
    root: Path,
    child: str,
    parent: str,
    *,
    name: str = "O8",
) -> None:
    observed = _git(root, "rev-list", "--parents", "-n", "1", child)
    if observed != f"{child} {parent}\n".encode("ascii"):
        _fail(f"{name} is not the required one-parent direct child")


def _require_lightweight_tag(root: Path, tag: str, commit: str, *, name: str) -> None:
    ref = f"refs/tags/{tag}"
    if _git(root, "cat-file", "-t", ref) != b"commit\n":
        _fail(f"{name} is not a lightweight commit tag")
    observed = _git(root, "rev-parse", ref)
    if observed != f"{commit}\n".encode("ascii"):
        _fail(f"{name} does not resolve to its registered commit")


def _parse_name_status(raw: bytes, *, name: str) -> set[tuple[str, str]]:
    fields = raw.split(b"\0")
    if not fields or fields[-1] != b"" or len(fields) % 2 != 1:
        _fail(f"{name} name-status stream is malformed")
    result: set[tuple[str, str]] = set()
    for index in range(0, len(fields) - 1, 2):
        try:
            status = fields[index].decode("ascii", "strict")
            path = fields[index + 1].decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise _AdministrativeFailure(
                f"{name} name-status stream has invalid encoding"
            ) from exc
        record = (status, path)
        if status not in {"A", "D", "M"} or not path or record in result:
            _fail(f"{name} name-status stream is invalid")
        result.add(record)
    return result


def _require_delta(
    root: Path,
    before: str,
    after: str,
    expected: set[tuple[str, str]],
    *,
    name: str,
) -> None:
    raw = _git(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        before,
        after,
    )
    if _parse_name_status(raw, name=name) != expected:
        _fail(f"{name} does not have its exact registered path delta")


def _validate_recovery_lineage(root: Path, open_commit: str) -> None:
    _require_lightweight_tag(root, _P8V4_TAG, _P8V4_COMMIT, name="P8v4 tag")
    _require_lightweight_tag(root, _O8V1_TAG, _O8V1_COMMIT, name="O8v1 tag")
    _require_direct_child(root, _O8V1_COMMIT, _P8V4_COMMIT, name="O8v1")
    if (
        _git(root, "rev-parse", f"{_O8V1_COMMIT}^{{tree}}")
        != f"{_O8V1_TREE}\n".encode("ascii")
    ):
        _fail("O8v1 tree differs from its immutable historical identity")
    _require_delta(
        root,
        _P8V4_COMMIT,
        _O8V1_COMMIT,
        {("A", path) for path in _O8_ADDITIONS},
        name="P8v4-to-O8v1",
    )

    _require_lightweight_tag(root, _P8V5_TAG, _P8V5_COMMIT, name="P8v5 tag")
    _require_direct_child(root, _P8V5_COMMIT, _O8V1_COMMIT, name="P8v5")
    if (
        _git(root, "rev-parse", f"{_P8V5_COMMIT}^{{tree}}")
        != f"{_P8V5_TREE}\n".encode("ascii")
    ):
        _fail("P8v5 tree differs from its immutable historical identity")
    p8v5_reset_delta = {("D", path) for path in _O8_ADDITIONS}
    p8v5_reset_delta.add(("A", _P8V5_DOCUMENT))
    _require_delta(
        root,
        _O8V1_COMMIT,
        _P8V5_COMMIT,
        p8v5_reset_delta,
        name="O8v1-to-P8v5",
    )
    _require_delta(
        root,
        _P8V4_COMMIT,
        _P8V5_COMMIT,
        {("A", _P8V5_DOCUMENT)},
        name="P8v4-to-P8v5",
    )

    _require_lightweight_tag(root, _O8V2_TAG, _O8V2_COMMIT, name="O8v2 tag")
    _require_direct_child(root, _O8V2_COMMIT, _P8V5_COMMIT, name="O8v2")
    if (
        _git(root, "rev-parse", f"{_O8V2_COMMIT}^{{tree}}")
        != f"{_O8V2_TREE}\n".encode("ascii")
    ):
        _fail("O8v2 tree differs from its immutable historical identity")
    _require_delta(
        root,
        _P8V5_COMMIT,
        _O8V2_COMMIT,
        {("A", path) for path in _O8_ADDITIONS},
        name="P8v5-to-O8v2",
    )

    _require_lightweight_tag(
        root,
        _PREREGISTRATION_TAG,
        _PREREGISTRATION_COMMIT,
        name="P8v6 tag",
    )
    _require_direct_child(
        root,
        _PREREGISTRATION_COMMIT,
        _O8V2_COMMIT,
        name="P8v6",
    )
    if (
        _git(root, "rev-parse", f"{_PREREGISTRATION_COMMIT}^{{tree}}")
        != f"{_PREREGISTRATION_TREE}\n".encode("ascii")
    ):
        _fail("P8v6 tree differs from its immutable registered identity")
    p8v6_reset_delta = {("D", path) for path in _O8_ADDITIONS}
    p8v6_reset_delta.add(("A", _PREREGISTRATION_DOCUMENT))
    _require_delta(
        root,
        _O8V2_COMMIT,
        _PREREGISTRATION_COMMIT,
        p8v6_reset_delta,
        name="O8v2-to-P8v6",
    )
    _require_delta(
        root,
        _P8V5_COMMIT,
        _PREREGISTRATION_COMMIT,
        {("A", _PREREGISTRATION_DOCUMENT)},
        name="P8v5-to-P8v6",
    )

    expected_listing = (
        f"100644 blob {_PREREGISTRATION_DOCUMENT_BLOB}\t"
        f"{_PREREGISTRATION_DOCUMENT}\0"
    ).encode()
    listing = _git(
        root,
        "ls-tree",
        "-z",
        _PREREGISTRATION_COMMIT,
        "--",
        _PREREGISTRATION_DOCUMENT,
    )
    if listing != expected_listing:
        _fail("P8v6 recovery document Git identity is invalid")
    document_raw = _git(
        root,
        "cat-file",
        "blob",
        f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}",
    )
    if (
        len(document_raw) != _PREREGISTRATION_DOCUMENT_BYTE_COUNT
        or _sha256(document_raw) != _PREREGISTRATION_DOCUMENT_SHA256
    ):
        _fail("P8v6 recovery document raw identity is invalid")

    _require_direct_child(
        root,
        open_commit,
        _PREREGISTRATION_COMMIT,
        name="O8v3",
    )
    _require_delta(
        root,
        _PREREGISTRATION_COMMIT,
        open_commit,
        {("A", path) for path in _O8_ADDITIONS},
        name="P8v6-to-O8v3",
    )


def _validate_worktree_entry_set(root: Path, registered_paths: set[str]) -> None:
    registered_directories = {
        parent.as_posix()
        for relative in registered_paths
        for parent in PurePosixPath(relative).parents
        if parent.as_posix() != "."
    }
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(names):
            candidate = current / name
            relative = candidate.relative_to(root).as_posix()
            metadata = candidate.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                _fail(f"process clone contains an unsafe directory entry: {relative}")
            if current == root and name in {".git", ".venv"}:
                names.remove(name)
            elif relative not in registered_directories:
                _fail(f"process clone contains an unregistered directory: {relative}")
        for name in files:
            candidate = current / name
            relative = candidate.relative_to(root).as_posix()
            if relative not in registered_paths:
                _fail(f"process clone contains an unregistered file: {relative}")


def _validate_reconstructed_execution(
    root: Path,
    registration: Mapping[str, Any],
) -> None:
    source_manifest = registration.get("source_manifest")
    if not isinstance(source_manifest, Mapping):
        _fail("registration source manifest is invalid")
    additions = source_manifest.get("open_freeze_added_files")
    if not isinstance(additions, list):
        _fail("registration open-freeze additions are invalid")
    reconstructor_path = root / "scripts/reconstruct_action_qbc_v8_open_registration.py"
    specification = importlib.util.spec_from_file_location(
        "_arc3_p8v4_execution_reconstructor",
        reconstructor_path,
    )
    if specification is None or specification.loader is None:
        _fail("verified execution reconstructor cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    try:
        specification.loader.exec_module(module)
        builder = getattr(module, "_execution_contract", None)
        if not callable(builder):
            _fail("verified execution reconstructor lacks its frozen builder")
        expected = builder(additions)
    except _AdministrativeFailure:
        raise
    except Exception as exc:
        raise _AdministrativeFailure(
            "verified execution contract cannot be independently reconstructed"
        ) from exc
    if registration.get("execution_contract") != expected:
        _fail("registration execution contract differs from exact reconstruction")


def _load_registration(root: Path, relative: str) -> tuple[dict[str, Any], bytes]:
    path = root / relative
    raw = _plain_file_bytes(path, "registration")
    registration = _parse_canonical(raw, "registration")
    _require_keys(registration, _REGISTRATION_KEYS, "registration")
    if (
        registration.get("schema_version") != _REGISTRATION_SCHEMA
        or registration.get("status") != "registered_zero_result"
        or registration.get("treatment_id") != _TREATMENT_ID
        or registration.get("runtime_id") is not None
    ):
        _fail("registration fixed identity is invalid")
    content_sha = _require_sha(registration.get("content_sha256"), 64, "registration content")
    unsigned = dict(registration)
    del unsigned["content_sha256"]
    if _sha256(_canonical_json_bytes(unsigned)) != content_sha:
        _fail("registration content hash is invalid")
    _validate_execution_contract(registration)
    return registration, raw


def _verify_repository(
    root: Path,
    registration: Mapping[str, Any],
    registration_raw: bytes,
) -> str:
    _validate_local_git_sources(root)
    head = _git(root, "rev-parse", "HEAD").decode("ascii", "strict").strip()
    tag = _git(root, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}").decode(
        "ascii", "strict"
    ).strip()
    tag_type = _git(root, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}")
    commit = _require_sha(tag, 40, "open-freeze commit")
    if head != commit or tag_type != b"commit\n":
        _fail("clone HEAD or lightweight open-freeze tag is invalid")
    _validate_recovery_lineage(root, commit)

    registration_blob = _git(root, "show", f"{commit}:{_EXPECTED_REGISTRATION}")
    if registration_blob != registration_raw:
        _fail("registration raw bytes differ from the O8 Git blob")
    script_raw = _plain_file_bytes(root / _EXPECTED_SCRIPT, "scientific runner")
    script_blob = _git(root, "show", f"{commit}:{_EXPECTED_SCRIPT}")
    if script_raw != script_blob:
        _fail("scientific runner raw bytes differ from the O8 Git blob")

    listing = _git(root, "ls-tree", "-rz", "--full-tree", commit)
    registered_paths: set[str] = set()
    for record in listing.split(b"\0"):
        if not record:
            continue
        try:
            identity, raw_path = record.split(b"\t", 1)
            mode, kind, blob = identity.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise _AdministrativeFailure("Git tree inventory is malformed") from exc
        if kind != "blob" or mode not in {"100644", "100755"}:
            _fail("Git tree contains a forbidden entry type")
        if relative.startswith("/") or ".." in Path(relative).parts:
            _fail("Git tree contains an unsafe path")
        expected = _git(root, "cat-file", "blob", blob)
        observed_path = root / relative
        observed = _plain_file_bytes(observed_path, f"tracked file {relative}")
        if observed != expected:
            _fail(f"tracked file {relative} differs from its Git blob")
        observed_mode = stat.S_IMODE(observed_path.stat(follow_symlinks=False).st_mode)
        expected_mode = 0o755 if mode == "100755" else 0o644
        if observed_mode != expected_mode:
            _fail(f"tracked file {relative} has the wrong materialized mode")
        registered_paths.add(relative)
    _validate_worktree_entry_set(root, registered_paths)
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") != b"":
        _fail("process clone is not Git-clean")
    _validate_reconstructed_execution(root, registration)
    return commit


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one registered action-QBC v8 open diagnostic process."
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--preparation-verification-receipt", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--driver-claim", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--start-claim", required=True)
    parser.add_argument("--prior-validation-receipt", required=True)
    parser.add_argument("--compute-deadline-seconds", required=True, type=int)
    parser.add_argument("--wall-time-seconds", required=True, type=int)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def _validate_receipt(
    path: Path,
    *,
    keys: set[str],
    schema: str,
    name: str,
) -> tuple[dict[str, Any], bytes]:
    raw = _plain_file_bytes(path, name)
    value = _parse_canonical(raw, name)
    _require_keys(value, keys, name)
    if value.get("schema_version") != schema or value.get("treatment_id") != _TREATMENT_ID:
        _fail(f"{name} fixed identity is invalid")
    return value, raw


def _immutable_linux_evidence(path: Path, name: str) -> bytes:
    raw = _plain_file_bytes(path, name)
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} identity is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o444
        or metadata.st_nlink != 1
        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
        or metadata.st_size != len(raw)
    ):
        _fail(f"{name} is not an owner-bound immutable mode-0444 file")
    return raw


def _substituted_scientific_argv(
    template: Sequence[Any], *, label: str, process: Mapping[str, str]
) -> list[str]:
    if not all(isinstance(item, str) for item in template):
        _fail("scientific argv template is invalid")
    replacements = {
        "<LABEL>": label,
        "<START_CLAIM>": process["start_claim"],
        "<PRIOR_VALIDATION_OR_NULL>": process["prior"],
        "<OUTPUT_PATH>": process["output"],
    }
    result = [replacements.get(item, item) for item in template]
    if any(item.startswith("<") and item.endswith(">") for item in result):
        _fail("scientific argv template contains an unresolved placeholder")
    return result


def _substituted_validator_argv(
    template: Sequence[Any], *, label: str, process: Mapping[str, str]
) -> list[str]:
    if not all(isinstance(item, str) for item in template):
        _fail("payload-validator argv template is invalid")
    replacements = {
        "<LABEL>": label,
        "<START_CLAIM>": process["start_claim"],
        "<VALIDATOR_CLAIM>": process["validator_claim"],
        "<VALIDATION_RECEIPT>": process["validation_receipt"],
        "<OUTPUT_PATH>": process["output"],
    }
    result = [replacements.get(item, item) for item in template]
    if any(item.startswith("<") and item.endswith(">") for item in result):
        _fail("payload-validator argv template contains an unresolved placeholder")
    return result


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _tree_entries(root: Path, commit: str) -> list[tuple[str, str, str, int]]:
    raw = _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit)
    rows: list[tuple[str, str, str, int]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, tab, path_raw = record.partition(b"\t")
        fields = metadata.split()
        try:
            mode, object_type, object_id, size_raw = fields
            path = path_raw.decode("utf-8", "strict")
            size = int(size_raw)
            object_id_text = object_id.decode("ascii", "strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise _AdministrativeFailure("Git tree ledger inventory is malformed") from exc
        if (
            not tab
            or mode != b"100644"
            or object_type != b"blob"
            or size < 0
            or _require_sha(object_id_text, 40, "Git tree blob") != object_id_text
            or not path
            or path.startswith("/")
            or ".." in PurePosixPath(path).parts
        ):
            _fail("Git tree ledger inventory has a forbidden entry")
        rows.append((path, "100644", object_id_text, size))
    rows.sort(key=lambda row: row[0].encode("utf-8"))
    if not rows or len({row[0] for row in rows}) != len(rows):
        _fail("Git tree ledger inventory is empty or has duplicate paths")
    return rows


def _command_identity(
    *,
    attempt_index: int | None,
    label: str,
    phase: str,
    cwd: Path,
    argv: Sequence[str],
    stdin_bytes: bytes = b"",
) -> dict[str, Any]:
    argv_list = list(argv)
    return {
        "attempt_index": attempt_index,
        "label": label,
        "phase": phase,
        "cwd": str(cwd),
        "argv": argv_list,
        "argv_sha256": _sha256(_canonical_json_bytes(argv_list)),
        "stdin_size_bytes": len(stdin_bytes),
        "stdin_sha256": _sha256(stdin_bytes),
    }


def _expected_raw_audit_identities(
    root: Path,
    open_commit: str,
    entries: Sequence[tuple[str, str, str, int]],
    *,
    attempt_index: int,
    label: str,
) -> list[dict[str, Any]]:
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(root)]
    request = b"".join(entry[2].encode("ascii") + b"\n" for entry in entries)
    commands: list[tuple[str, list[str], bytes]] = [
        ("git_config", [*prefix, "config", "--local", "--null", "--list"], b""),
        ("raw_audit", [*prefix, "rev-parse", "HEAD"], b""),
        (
            "raw_audit",
            [*prefix, "ls-tree", "-r", "-l", "-z", "--full-tree", open_commit],
            b"",
        ),
        ("raw_audit", [*prefix, "cat-file", "--batch"], request),
        ("raw_audit", [*prefix, "ls-files", "--stage", "-z"], b""),
        (
            "raw_audit",
            [*prefix, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
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
            stdin_bytes=stdin,
        )
        for phase, argv, stdin in commands
    ]


def _expected_attempt_identities(
    execution: Mapping[str, Any],
    execution_root: Path,
    attempt_index: int,
    open_commit: str,
    entries: Sequence[tuple[str, str, str, int]],
) -> list[dict[str, Any]]:
    environment = execution.get("environment_build_argv")
    preflights = execution.get("preflight_argvs")
    if (
        not isinstance(environment, list)
        or not all(isinstance(item, str) for item in environment)
        or not isinstance(preflights, list)
        or len(preflights) != 5
        or not all(
            isinstance(command, list)
            and command
            and all(isinstance(item, str) for item in command)
            for command in preflights
        )
    ):
        _fail("registered preparation command arrays are invalid")
    source = execution_root / f".prepare-attempt-{attempt_index}"
    roots = {"A": source / "process-a", "B": source / "process-b"}
    result: list[dict[str, Any]] = []

    def append(label: str, phase: str, cwd: Path, argv: Sequence[str]) -> None:
        result.append(
            _command_identity(
                attempt_index=attempt_index,
                label=label,
                phase=phase,
                cwd=cwd,
                argv=argv,
            )
        )

    for label, root in roots.items():
        commands = [
            (
                "clone",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "clone",
                    "--no-local",
                    "--no-checkout",
                    "--branch",
                    _OPEN_FREEZE_TAG,
                    "--single-branch",
                    _PREPARATION_SOURCE_URL,
                    str(root),
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "config",
                    "--local",
                    "core.autocrlf",
                    "false",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "config",
                    "--local",
                    "core.eol",
                    "lf",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "config",
                    "--local",
                    "core.safecrlf",
                    "true",
                ],
            ),
            (
                "checkout",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "checkout",
                    "--detach",
                    open_commit,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "remote",
                    "remove",
                    "origin",
                ],
            ),
        ]
        for phase, argv in commands:
            append(label, phase, source, argv)
        prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(root)]
        append(label, "git_config", root, [*prefix, "config", "--local", "--null", "--list"])
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
            _expected_raw_audit_identities(
                root,
                open_commit,
                entries,
                attempt_index=attempt_index,
                label=label,
            )
        )
    for label, root in roots.items():
        append(label, "environment_build", root, environment)
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
        for argv in preflights:
            append(label, "preflight", root, argv)
    if len(result) != 54:
        _fail("internal preparation command plan is not 54 rows")
    return result


def _expected_authority_identities(
    authority_root: Path,
    open_commit: str,
    entries: Sequence[tuple[str, str, str, int]],
) -> list[dict[str, Any]]:
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(authority_root)]
    commands: list[tuple[str, list[str], bytes]] = []

    def append(phase: str, arguments: Sequence[str], stdin: bytes = b"") -> None:
        commands.append((phase, [*prefix, *arguments], stdin))

    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V1_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_PREREGISTRATION_V1_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _PREREGISTRATION_V1_COMMIT])
    append(
        "raw_audit",
        ["diff", "--name-status", "--no-renames", "-z", _R7_COMMIT, _PREREGISTRATION_V1_COMMIT],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V2_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_PREREGISTRATION_V2_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _PREREGISTRATION_V2_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _PREREGISTRATION_V1_COMMIT,
            _PREREGISTRATION_V2_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_PREREGISTRATION_V3_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_PREREGISTRATION_V3_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _PREREGISTRATION_V3_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _PREREGISTRATION_V2_COMMIT,
            _PREREGISTRATION_V3_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_P8V4_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_P8V4_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _P8V4_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _PREREGISTRATION_V3_COMMIT,
            _P8V4_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_O8V1_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_O8V1_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _O8V1_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V4_COMMIT,
            _O8V1_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_P8V5_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_P8V5_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _P8V5_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _O8V1_COMMIT,
            _P8V5_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_O8V2_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_O8V2_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _O8V2_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V5_COMMIT,
            _O8V2_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_PREREGISTRATION_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_PREREGISTRATION_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", _PREREGISTRATION_COMMIT])
    append(
        "raw_audit",
        [
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _O8V2_COMMIT,
            _PREREGISTRATION_COMMIT,
        ],
    )
    append(
        "raw_audit",
        ["ls-tree", "-z", _PREREGISTRATION_COMMIT, "--", _PREREGISTRATION_DOCUMENT],
    )
    append(
        "raw_audit",
        ["cat-file", "blob", f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}"],
    )
    append("raw_audit", ["rev-list", "--parents", "-n", "1", open_commit])
    append(
        "raw_audit",
        ["diff", "--name-status", "--no-renames", "-z", _PREREGISTRATION_COMMIT, open_commit],
    )
    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append("raw_audit", ["ls-tree", "-r", "-l", "-z", "--full-tree", open_commit])
    request = b"".join(entry[2].encode("ascii") + b"\n" for entry in entries)
    append("raw_audit", ["cat-file", "--batch"], request)
    append("raw_audit", ["ls-files", "--stage", "-z"])
    append("raw_audit", ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    if len(commands) != 46:
        _fail("internal authority command plan is not 46 rows")
    return [
        _command_identity(
            attempt_index=None,
            label="authority",
            phase=phase,
            cwd=authority_root,
            argv=argv,
            stdin_bytes=stdin,
        )
        for phase, argv, stdin in commands
    ]


def _validate_preparation_attempts(value: Any, execution_root: Path) -> int:
    if not isinstance(value, list) or not 1 <= len(value) <= 2:
        _fail("prepared receipt must contain one or two exact attempts")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            _fail("preparation attempt is not an object")
        _require_keys(item, _ATTEMPT_KEYS, f"preparation attempt {index}")
        cleanup = item.get("cleanup")
        promotion = item.get("promotion")
        if not isinstance(cleanup, Mapping) or not isinstance(promotion, Mapping):
            _fail("preparation attempt cleanup/promotion is not an object")
        _require_keys(cleanup, _CLEANUP_KEYS, f"preparation attempt {index} cleanup")
        _require_keys(
            promotion,
            _PROMOTION_KEYS,
            f"preparation attempt {index} promotion",
        )
        source = execution_root / f".prepare-attempt-{index}"
        destination = execution_root / "processes"
        owned = cleanup.get("owned_paths")
        removed = cleanup.get("removed")
        if (
            not _is_plain_int(item.get("attempt_index"))
            or item.get("attempt_index") != index
            or not isinstance(item.get("process_a_stage"), str)
            or item.get("process_a_stage") not in _PROCESS_STAGES
            or not isinstance(item.get("process_b_stage"), str)
            or item.get("process_b_stage") not in _PROCESS_STAGES
            or promotion.get("source_path") != str(source)
            or promotion.get("destination_path") != str(destination)
            or not isinstance(owned, list)
            or not isinstance(removed, list)
            or not all(isinstance(path, str) for path in [*owned, *removed])
            or owned != sorted(owned)
            or removed != sorted(removed)
            or not set(removed) <= set(owned)
        ):
            _fail("preparation attempt identity is invalid")
        final = index == len(value)
        if final:
            device = promotion.get("source_device")
            inode = promotion.get("source_inode")
            if (
                item.get("passes") is not True
                or item.get("process_a_stage") != "completed"
                or item.get("process_b_stage") != "completed"
                or promotion.get("passes") is not True
                or cleanup.get("passes") is not True
                or owned != [str(source)]
                or removed != []
                or not _is_plain_int(device)
                or device < 0
                or not _is_plain_int(inode)
                or inode < 0
                or source.exists()
                or source.is_symlink()
            ):
                _fail("final preparation attempt is not one passing atomic promotion")
            try:
                metadata = destination.stat(follow_symlinks=False)
            except OSError as exc:
                raise _AdministrativeFailure("promoted processes directory is absent") from exc
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o700
                or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
                or metadata.st_dev != device
                or metadata.st_ino != inode
            ):
                _fail("promoted processes directory lost its staged identity")
        else:
            device = promotion.get("source_device")
            inode = promotion.get("source_inode")
            if (
                item.get("passes") is not False
                or promotion.get("passes") is not False
                or cleanup.get("passes") is not True
                or source.exists()
                or source.is_symlink()
                or (device is None) != (inode is None)
                or owned not in ([], [str(source)])
                or removed not in ([], [str(source)])
            ):
                _fail("failed preparation attempt lacks complete cleanup evidence")
            if device is not None and (
                not _is_plain_int(device)
                or device < 0
                or not _is_plain_int(inode)
                or inode < 0
            ):
                _fail("failed preparation attempt source identity is invalid")
    return len(value)


def _validate_command_ledger(
    preparation: Mapping[str, Any],
    execution: Mapping[str, Any],
    execution_root: Path,
    attempt_count: int,
    open_commit: str,
) -> list[dict[str, Any]]:
    value = preparation.get("command_ledger")
    if not isinstance(value, list) or not value:
        _fail("preparation command ledger is not a nonempty array")
    if preparation.get("commands_sha256") != _sha256(_canonical_json_bytes(value)):
        _fail("preparation command ledger hash is invalid")
    environment = execution.get("preparation_command_environment")
    policy = execution.get("preparation_command_policy")
    if preparation.get("command_environment_sha256") != _sha256(
        _canonical_json_bytes(environment)
    ):
        _fail("preparation command environment hash is invalid")
    if not isinstance(policy, Mapping):
        _fail("preparation command policy is invalid")
    empty_sha = _sha256(b"")
    authority_rows: list[dict[str, Any]] = []
    attempt_rows: dict[int, list[dict[str, Any]]] = {
        index: [] for index in range(1, attempt_count + 1)
    }
    previous_attempt = 0
    terminal_attempts: set[int] = set()
    phases = {
        "clone",
        "git_config",
        "checkout",
        "raw_audit",
        "environment_build",
        "preflight",
    }
    outcomes = {
        "completed",
        "nonzero",
        "timeout",
        "stdout_limit",
        "stderr_limit",
        "spawn_error",
        "stdin_limit",
    }
    for sequence_index, item in enumerate(value):
        if not isinstance(item, dict):
            _fail("preparation command-ledger row is not an object")
        _require_keys(item, _COMMAND_LEDGER_KEYS, "preparation command-ledger row")
        row = item
        argv = row.get("argv")
        cwd = row.get("cwd")
        attempt_raw = row.get("attempt_index")
        if (
            not _is_plain_int(row.get("sequence_index"))
            or row.get("sequence_index") != sequence_index
            or not isinstance(row.get("phase"), str)
            or row.get("phase") not in phases
            or not isinstance(cwd, str)
            or not PurePosixPath(cwd).is_absolute()
            or "\x00" in cwd
            or not isinstance(argv, list)
            or not argv
            or not all(
                isinstance(argument, str) and argument and "\x00" not in argument
                for argument in argv
            )
            or row.get("argv_sha256") != _sha256(_canonical_json_bytes(argv))
        ):
            _fail("preparation command-ledger identity is invalid")
        if attempt_raw is None:
            if previous_attempt or row.get("label") != "authority":
                _fail("authority preparation command is out of order")
            authority_rows.append(row)
        else:
            if not _is_plain_int(attempt_raw):
                _fail("preparation attempt command has a non-integer attempt")
            attempt = int(attempt_raw)
            if (
                attempt < previous_attempt
                or attempt > previous_attempt + 1
                or attempt < 1
                or attempt > attempt_count
                or attempt in terminal_attempts
                or row.get("label") not in {"A", "B"}
            ):
                _fail("preparation command attempts are out of order")
            expected_stage = execution_root / f".prepare-attempt-{attempt}"
            try:
                PurePosixPath(cwd).relative_to(PurePosixPath(str(expected_stage)))
            except ValueError as exc:
                raise _AdministrativeFailure(
                    "attempt-owned preparation command cwd escapes its stage"
                ) from exc
            previous_attempt = attempt
            attempt_rows[attempt].append(row)

        for size_key, digest_key in (
            ("stdin_size_bytes", "stdin_sha256"),
            ("stdout_size_bytes", "stdout_sha256"),
            ("stderr_size_bytes", "stderr_sha256"),
        ):
            if not _is_plain_int(row.get(size_key)) or row[size_key] < 0:
                _fail("preparation command stream size is invalid")
            _require_sha(row.get(digest_key), 64, "preparation command stream")
        duration = row.get("duration_milliseconds")
        started = row.get("started")
        timed_out = row.get("timed_out")
        outcome = row.get("outcome")
        exit_code = row.get("exit_code")
        cleanup = row.get("child_cleanup_passes")
        if (
            not _is_plain_int(duration)
            or duration < 0
            or not isinstance(started, bool)
            or not isinstance(timed_out, bool)
            or not isinstance(outcome, str)
            or outcome not in outcomes
            or (cleanup is not None and not isinstance(cleanup, bool))
            or (exit_code is not None and not _is_plain_int(exit_code))
        ):
            _fail("preparation command outcome evidence is invalid")
        stdin_size = int(row["stdin_size_bytes"])
        stdout_size = int(row["stdout_size_bytes"])
        stderr_size = int(row["stderr_size_bytes"])
        stdin_cap = int(policy["stdin_cap_bytes"])
        stdout_cap = int(policy["stdout_cap_bytes"])
        stderr_cap = int(policy["stderr_cap_bytes"])
        if stdin_size > stdin_cap:
            if outcome != "stdin_limit" or started or exit_code is not None or timed_out:
                _fail("preparation stdin-limit classification is invalid")
        elif outcome == "stdin_limit":
            _fail("preparation command invents an stdin-limit outcome")
        if not started:
            if (
                outcome not in {"spawn_error", "stdin_limit"}
                or exit_code is not None
                or timed_out
                or cleanup is not None
                or stdout_size
                or stderr_size
                or row.get("stdout_sha256") != empty_sha
                or row.get("stderr_sha256") != empty_sha
            ):
                _fail("unstarted preparation command has impossible evidence")
        else:
            if outcome in {"spawn_error", "stdin_limit"}:
                _fail("started preparation command has a pre-spawn outcome")
            if outcome == "completed" and (exit_code != 0 or timed_out):
                _fail("completed preparation command evidence is inconsistent")
            if outcome == "nonzero" and (
                not _is_plain_int(exit_code) or exit_code == 0 or timed_out
            ):
                _fail("nonzero preparation command evidence is inconsistent")
            if outcome == "timeout" and not timed_out:
                _fail("timeout preparation command lacks its timeout fact")
            if outcome in {"timeout", "stdout_limit", "stderr_limit"} and not isinstance(
                cleanup, bool
            ):
                _fail("forced preparation command lacks cleanup evidence")
            if cleanup is False:
                _fail("prepared receipt records failed child cleanup")
        if stdout_size > stdout_cap + 1 or stderr_size > stderr_cap + 1:
            _fail("preparation command stream evidence exceeds cap+1")
        if outcome == "stdout_limit":
            if stdout_size != stdout_cap + 1:
                _fail("stdout-limit command does not bind cap+1")
        elif stdout_size > stdout_cap:
            _fail("non-stdout-limit command exceeds the stdout cap")
        if outcome == "stderr_limit":
            if stderr_size != stderr_cap + 1 or stdout_size > stdout_cap:
                _fail("stderr-limit command does not bind collision precedence")
        elif outcome == "stdout_limit":
            if stderr_size > stderr_cap + 1:
                _fail("stdout-limit stderr evidence exceeds cap+1")
        elif stderr_size > stderr_cap:
            _fail("non-stderr-limit command exceeds the stderr cap")
        if outcome == "timeout" and (stdout_size > stdout_cap or stderr_size > stderr_cap):
            _fail("timeout command contradicts stream-limit precedence")
        timeout_seconds = int(
            policy[
                "environment_timeout_seconds"
                if row.get("phase") == "environment_build"
                else "default_timeout_seconds"
            ]
        )
        if timed_out and duration < timeout_seconds * 1000:
            _fail("timed-out preparation command precedes its threshold")
        if attempt_raw is None and outcome != "completed":
            _fail("prepared receipt has a failing authority command")
        if attempt_raw is not None and outcome != "completed":
            terminal_attempts.add(int(attempt_raw))

    if previous_attempt != attempt_count or attempt_count in terminal_attempts:
        _fail("preparation ledger omits a complete passing final attempt")
    entries = _tree_entries(Path(str(execution["authority_root"])), open_commit)
    observed_authority = [
        {key: row[key] for key in _COMMAND_IDENTITY_KEYS} for row in authority_rows
    ]
    if observed_authority != _expected_authority_identities(
        Path(str(execution["authority_root"])), open_commit, entries
    ):
        _fail("preparation authority command ledger differs from exact reconstruction")
    expected_shape = [
        *(label_phase for label_phase in [("A", phase) for phase in (
            "clone", "git_config", "git_config", "git_config", "checkout",
            "git_config", "git_config", "raw_audit", "raw_audit",
        )]),
        *(label_phase for label_phase in [("B", phase) for phase in (
            "clone", "git_config", "git_config", "git_config", "checkout",
            "git_config", "git_config", "raw_audit", "raw_audit",
        )]),
        *(("A", phase) for phase in ("git_config", *("raw_audit" for _ in range(5)))),
        *(("B", phase) for phase in ("git_config", *("raw_audit" for _ in range(5)))),
        ("A", "environment_build"),
        ("B", "environment_build"),
        *(("A", phase) for phase in ("git_config", *("raw_audit" for _ in range(5)))),
        *(("B", phase) for phase in ("git_config", *("raw_audit" for _ in range(5)))),
        *(("A", "preflight") for _ in range(5)),
        *(("B", "preflight") for _ in range(5)),
    ]
    for attempt, rows in attempt_rows.items():
        observed_shape = [(row.get("label"), row.get("phase")) for row in rows]
        if observed_shape != expected_shape[: len(observed_shape)]:
            _fail("preparation command ledger is not an allowed attempt-plan prefix")
        expected_rows = _expected_attempt_identities(
            execution,
            execution_root,
            attempt,
            open_commit,
            entries,
        )
        observed = [{key: row[key] for key in _COMMAND_IDENTITY_KEYS} for row in rows]
        if observed != expected_rows[: len(observed)]:
            _fail(f"preparation attempt {attempt} contains an invented command")
        if attempt == attempt_count and (
            observed_shape != expected_shape or observed != expected_rows
        ):
            _fail("passing preparation attempt lacks its exact 54-command plan")
    return value


def _validate_clone_record(
    value: Any,
    *,
    keys: set[str],
    name: str,
    expected_root: str,
    open_commit: str,
    authority: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{name} is not an object")
    _require_keys(value, keys, name)
    if (
        value.get("root") != expected_root
        or any(
            not _is_plain_int(value.get(key))
            for key in ("root_device", "root_inode", "root_owner_uid", "root_mode")
        )
        or any(
            value[key] < 0 for key in ("root_device", "root_inode", "root_owner_uid")
        )
        or value.get("root_mode") != 0o700
        or (
            hasattr(os, "getuid")
            and value.get("root_owner_uid") != os.getuid()
        )
        or value.get("head_sha") != open_commit
        or value.get("passes") is not True
        or value.get("git_status_sha256") != _sha256(b"")
    ):
        _fail(f"{name} fixed identity is invalid")
    for key in (
        "tree_sha256",
        "raw_materialization_sha256",
        "git_status_sha256",
    ):
        _require_sha(value.get(key), 64, f"{name} {key}")
    environment_keys = (
        "python_version",
        "uv_version",
        "environment_inventory_sha256",
        "venv_materialization_sha256",
        "venv_python_sha256",
    )
    if authority:
        if any(value.get(key) is not None for key in environment_keys):
            _fail(f"{name} authority environment fields are not null")
        if "environment_inventory" in keys and value.get("environment_inventory") is not None:
            _fail(f"{name} authority inventory is not null")
        return value
    if value.get("python_version") != "3.12.13" or value.get("uv_version") != "0.11.28":
        _fail(f"{name} version identity is invalid")
    for key in environment_keys[2:]:
        _require_sha(value.get(key), 64, f"{name} {key}")
    if "environment_inventory" in keys:
        inventory = value.get("environment_inventory")
        if not isinstance(inventory, list):
            _fail(f"{name} distribution inventory is not an array")
        observed_names: list[str] = []
        for distribution in inventory:
            if not isinstance(distribution, dict):
                _fail(f"{name} distribution inventory row is not an object")
            _require_keys(distribution, _DISTRIBUTION_KEYS, f"{name} distribution")
            normalized_name = distribution.get("normalized_name")
            if (
                not isinstance(normalized_name, str)
                or not isinstance(distribution.get("version"), str)
                or not _is_plain_int(distribution.get("file_count"))
                or distribution["file_count"] < 0
            ):
                _fail(f"{name} distribution identity is invalid")
            _require_sha(distribution.get("files_sha256"), 64, f"{name} distribution files")
            observed_names.append(normalized_name)
        if observed_names != sorted(observed_names, key=lambda item: item.encode("utf-8")):
            _fail(f"{name} distribution inventory is not name-sorted")
        if len(observed_names) != len(set(observed_names)):
            _fail(f"{name} distribution inventory has duplicate names")
        if {
            distribution["normalized_name"]: distribution["version"]
            for distribution in inventory
        } != {
            "arc3-crosslevel-voi": "0.1.0",
            "numpy": "2.5.1",
            "pyyaml": "6.0.3",
        }:
            _fail(f"{name} distributions differ from the frozen runtime lock")
        if value.get("environment_inventory_sha256") != _sha256(
            _canonical_json_bytes(inventory)
        ):
            _fail(f"{name} distribution inventory digest is invalid")
    return value


def _validate_preparation_chain(
    registration: Mapping[str, Any], *, open_commit: str
) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes]:
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    registration_sha = _require_sha(
        registration.get("content_sha256"), 64, "registration content"
    )
    preparation, preparation_raw = _validate_receipt(
        Path(_PREPARATION_RECEIPT),
        keys=_PREPARATION_KEYS,
        schema=_PREPARATION_SCHEMA,
        name="preparation receipt",
    )
    environment = execution.get("preparation_command_environment")
    policy = execution.get("preparation_command_policy")
    expected_policy = {
        "default_timeout_seconds": 60,
        "environment_timeout_seconds": 600,
        "term_grace_seconds": 5,
        "kill_grace_seconds": 5,
        "stdin_cap_bytes": 1_048_576,
        "stdout_cap_bytes": 134_217_728,
        "stderr_cap_bytes": 1_048_576,
    }
    if environment != _fixed_git_environment(Path("/")) or policy != expected_policy:
        _fail("registration preparation command policy differs from P8v4")
    execution_root_value = execution.get("execution_root")
    if execution_root_value != str(_EXECUTION_ROOT):
        _fail("registration preparation execution root differs from P8v4")
    attempt_count = _validate_preparation_attempts(
        preparation.get("attempts"), Path(str(execution_root_value))
    )
    ledger = _validate_command_ledger(
        preparation,
        execution,
        Path(str(execution_root_value)),
        attempt_count,
        open_commit,
    )
    if (
        preparation.get("status") != "prepared"
        or preparation.get("open_freeze_commit_sha") != open_commit
        or preparation.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or preparation.get("registration_content_sha256") != registration_sha
        or preparation.get("commands_sha256") != _sha256(_canonical_json_bytes(ledger))
        or preparation.get("command_environment_sha256")
        != _sha256(_canonical_json_bytes(environment))
        or not ledger
    ):
        _fail("preparation receipt is not a matching prepared receipt")
    roots = {
        "authority": execution.get("authority_root"),
        "process_a": execution.get("process_a_root"),
        "process_b": execution.get("process_b_root"),
    }
    if not all(isinstance(value, str) for value in roots.values()):
        _fail("registration preparation roots are invalid")
    preparation_clones: dict[str, dict[str, Any]] = {}
    for key in ("authority", "process_a", "process_b"):
        preparation_clones[key] = _validate_clone_record(
            preparation.get(key),
            keys=_PREPARATION_CLONE_KEYS,
            name=f"preparation {key}",
            expected_root=str(roots[key]),
            open_commit=open_commit,
            authority=key == "authority",
        )
    if (
        preparation_clones["process_a"]["venv_python_sha256"]
        != preparation_clones["process_b"]["venv_python_sha256"]
    ):
        _fail("prepared process interpreters differ")

    verification, verification_raw = _validate_receipt(
        Path(_PREPARATION_VERIFICATION_RECEIPT),
        keys=_PREPARATION_VERIFICATION_KEYS,
        schema=_PREPARATION_VERIFICATION_SCHEMA,
        name="preparation verification receipt",
    )
    unsigned_verification = dict(verification)
    verification_content = unsigned_verification.pop("content_sha256", None)
    verification_argv = execution.get("post_preparation_validation_argv")
    expected_verification_argv = [
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "--repository-root",
        ".",
        "--registration",
        _EXPECTED_REGISTRATION,
        "--verify-preparation",
        "--preparation-receipt",
        _PREPARATION_RECEIPT,
        "--verification-receipt",
        _PREPARATION_VERIFICATION_RECEIPT,
    ]
    if (
        verification.get("status") != "verified"
        or verification.get("open_freeze_commit_sha") != open_commit
        or verification.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or verification.get("registration_content_sha256") != registration_sha
        or verification.get("preparation_receipt_sha256") != _sha256(preparation_raw)
        or verification_argv != expected_verification_argv
        or verification.get("verification_argv_sha256")
        != _sha256(_canonical_json_bytes(verification_argv))
        or verification_content != _sha256(_canonical_json_bytes(unsigned_verification))
    ):
        _fail("preparation verification receipt binding is invalid")
    for key in ("authority", "process_a", "process_b"):
        verified_clone = _validate_clone_record(
            verification.get(key),
            keys=_VERIFICATION_CLONE_KEYS,
            name=f"preparation verification {key}",
            expected_root=str(roots[key]),
            open_commit=open_commit,
            authority=key == "authority",
        )
        projected = dict(preparation_clones[key])
        del projected["environment_inventory"]
        if verified_clone != projected:
            _fail(f"preparation verification {key} differs from preparation")
    return preparation, preparation_raw, verification, verification_raw


def _run_identity_command(argv: Sequence[str], *, cwd: Path, name: str) -> bytes:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=_fixed_git_environment(cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _AdministrativeFailure(f"{name} identity command failed") from exc
    if completed.returncode != 0 or completed.stderr != b"":
        _fail(f"{name} identity command returned unexpected evidence")
    return completed.stdout


def _open_live_output_parent(output: Path) -> _DirectoryAnchor:
    return _open_directory_anchor(
        output.parent,
        "scientific output parent",
        empty=True,
    )


def _validate_live_process_gate(
    root: Path,
    output: Path,
    registration: Mapping[str, Any],
    *,
    label: str,
    open_commit: str,
    preparation: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> tuple[_DirectoryAnchor, _DirectoryAnchor]:
    key = "process_a" if label == "A" else "process_b"
    prepared_clone = preparation.get(key)
    verified_clone = verification.get(key)
    if not isinstance(prepared_clone, Mapping) or not isinstance(
        verified_clone, Mapping
    ):
        _fail("selected process preparation evidence is invalid")
    root_anchor = _open_directory_anchor(root, "selected process root")
    output_anchor: _DirectoryAnchor | None = None
    try:
        metadata = os.fstat(root_anchor.descriptor)
        if (
            metadata.st_dev != verified_clone.get("root_device")
            or metadata.st_ino != verified_clone.get("root_inode")
            or getattr(metadata, "st_uid", None) != verified_clone.get("root_owner_uid")
            or stat.S_IMODE(metadata.st_mode) != verified_clone.get("root_mode")
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
        ):
            _fail("selected process root differs from independent verification")

        # This is deliberately a second live repository pass after receipt validation.
        registration_raw = _plain_file_bytes(root / _EXPECTED_REGISTRATION, "registration")
        if _verify_repository(root, registration, registration_raw) != open_commit:
            _fail("selected process repository changed during its live gate")
        _revalidate_directory_anchor(root_anchor)

        inventory, inventory_sha = _compact_environment_inventory(root)
        if (
            inventory != prepared_clone.get("environment_inventory")
            or inventory_sha != prepared_clone.get("environment_inventory_sha256")
            or inventory_sha != verified_clone.get("environment_inventory_sha256")
        ):
            _fail("installed-distribution inventory changed after verification")
        venv_sha = _venv_materialization_sha256(root)
        if (
            venv_sha != prepared_clone.get("venv_materialization_sha256")
            or venv_sha != verified_clone.get("venv_materialization_sha256")
        ):
            _fail("complete venv materialization changed after verification")
        _revalidate_directory_anchor(root_anchor)

        interpreter = root / ".venv/bin/python3"
        interpreter_sha = _venv_python_sha256(root)
        if (
            interpreter_sha != prepared_clone.get("venv_python_sha256")
            or prepared_clone.get("venv_python_sha256")
            != verified_clone.get("venv_python_sha256")
        ):
            _fail("resolved venv Python identity changed")
        if _run_identity_command(
            [str(interpreter), "--version"],
            cwd=root,
            name="venv Python",
        ) != b"Python 3.12.13\n":
            _fail("venv Python version changed")
        if _run_identity_command(
            ["/usr/local/bin/uv", "--version"],
            cwd=root,
            name="uv",
        ) != b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n":
            _fail("uv version changed")
        _revalidate_directory_anchor(root_anchor)
        output_anchor = _open_live_output_parent(output)
        _revalidate_directory_anchor(root_anchor)
        return root_anchor, output_anchor
    except Exception:
        if output_anchor is not None:
            os.close(output_anchor.descriptor)
        os.close(root_anchor.descriptor)
        raise


def _require_runtime_contract(
    args: argparse.Namespace,
    registration: Mapping[str, Any],
    *,
    root: Path,
    started: float,
) -> tuple[str, dict[str, str], Path, float, float, list[str]]:
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("scientific runner requires Python -I -B")
    if (
        args.repository_root != "."
        or args.registration != _EXPECTED_REGISTRATION
        or args.preparation_verification_receipt
        != _PREPARATION_VERIFICATION_RECEIPT
        or args.arm_receipt != _ARM_RECEIPT
        or args.driver_claim != _DRIVER_CLAIM
        or args.label not in _PROCESS
        or args.compute_deadline_seconds != _COMPUTE_SECONDS
        or args.wall_time_seconds != _WALL_SECONDS
    ):
        _fail("scientific runner command differs from registration")
    label = str(args.label)
    process = _PROCESS[label]
    if (
        args.start_claim != process["start_claim"]
        or args.prior_validation_receipt != process["prior"]
        or args.output != process["output"]
    ):
        _fail("scientific runner label/path binding is invalid")
    try:
        expected_root = Path(process["root"]).resolve(strict=True)
        root_real = root.resolve(strict=True)
    except OSError as exc:
        raise _AdministrativeFailure("registered process root is unavailable") from exc
    if root_real != expected_root:
        _fail("current directory is not the registered process clone")
    root_metadata = root_real.stat(follow_symlinks=False)
    if not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode):
        _fail("registered process clone is not a plain directory")
    if hasattr(os, "getuid") and root_metadata.st_uid != os.getuid():
        _fail("registered process clone has the wrong owner")
    try:
        observed_script = Path(sys.argv[0]).resolve(strict=True)
        expected_script = (root_real / _EXPECTED_SCRIPT).resolve(strict=True)
        if observed_script != expected_script:
            _fail("scientific runner origin differs from registration")
    except OSError as exc:
        raise _AdministrativeFailure("scientific runner origin is unavailable") from exc
    if Path(sys.executable).absolute() != (root_real / ".venv/bin/python3").absolute():
        _fail("scientific interpreter differs from registration")

    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    if (
        execution.get("compute_deadline_seconds") != _COMPUTE_SECONDS
        or execution.get("wall_time_seconds") != _WALL_SECONDS
        or execution.get("hard_timeout_seconds") != _HARD_SECONDS
        or execution.get("registered_start_count") != 2
        or execution.get("process_labels") != ["A", "B"]
        or execution.get("third_start_allowed") is not False
        or execution.get("preparation_verification_receipt_path")
        != _PREPARATION_VERIFICATION_RECEIPT
        or execution.get("arm_receipt_path") != _ARM_RECEIPT
        or execution.get("lifecycle_driver_claim_path") != _DRIVER_CLAIM
    ):
        _fail("registration execution constants are invalid")
    expected_root_key = "process_a_root" if label == "A" else "process_b_root"
    expected_output_key = "process_a_output" if label == "A" else "process_b_output"
    lower = label.casefold()
    if (
        execution.get(expected_root_key) != process["root"]
        or execution.get(expected_output_key) != process["output"]
        or execution.get(f"process_{lower}_start_claim") != process["start_claim"]
        or execution.get(f"process_{lower}_validator_claim")
        != process["validator_claim"]
        or execution.get(f"process_{lower}_validation_receipt")
        != process["validation_receipt"]
    ):
        _fail("registration does not bind the selected process")
    template = execution.get("scientific_argv_template")
    if not isinstance(template, list):
        _fail("scientific argv template is invalid")
    full_argv = _substituted_scientific_argv(template, label=label, process=process)
    try:
        script_index = full_argv.index(_EXPECTED_SCRIPT)
    except ValueError as exc:
        raise _AdministrativeFailure("scientific argv lacks its script") from exc
    if list(sys.argv) != full_argv[script_index:]:
        _fail("observed scientific argv differs from registration")
    argv_hashes = execution.get("argv_hashes")
    if not isinstance(argv_hashes, Mapping) or argv_hashes.get("scientific") != _sha256(
        _canonical_json_bytes(template)
    ):
        _fail("scientific argv template hash is invalid")

    output = Path(process["output"])
    parent = output.parent
    try:
        parent_metadata = parent.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure("scientific output parent is unavailable") from exc
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_ISLNK(parent_metadata.st_mode)
        or stat.S_IMODE(parent_metadata.st_mode) != 0o700
        or parent.resolve(strict=True) != parent.absolute()
    ):
        _fail("scientific output parent is unsafe")
    if hasattr(os, "getuid") and parent_metadata.st_uid != os.getuid():
        _fail("scientific output parent has the wrong owner")
    if output.exists() or output.is_symlink() or any(parent.iterdir()):
        _fail("scientific output destination is not empty")
    start_claim = Path(process["start_claim"])
    if start_claim.exists() or start_claim.is_symlink():
        _fail("scientific start claim already exists")
    return (
        label,
        process,
        output,
        started + _COMPUTE_SECONDS,
        started + _WALL_SECONDS,
        full_argv,
    )


def _validate_dependencies(
    registration: Mapping[str, Any],
    *,
    label: str,
    process: Mapping[str, str],
    open_commit: str,
) -> tuple[
    bytes,
    bytes,
    str | None,
    dict[str, Any],
    dict[str, Any],
]:
    registration_sha = _require_sha(
        registration.get("content_sha256"), 64, "registration content"
    )
    preparation, preparation_raw, verification, verification_raw = (
        _validate_preparation_chain(registration, open_commit=open_commit)
    )
    arm, arm_raw = _validate_receipt(
        Path(_ARM_RECEIPT), keys=_ARM_KEYS, schema=_ARM_SCHEMA, name="arm receipt"
    )
    if (
        arm.get("status") != "armed"
        or arm.get("open_freeze_commit_sha") != open_commit
        or arm.get("registration_content_sha256") != registration_sha
        or arm.get("preparation_receipt_exists") is not True
        or arm.get("preparation_receipt_read_status") != "readable"
        or arm.get("preparation_receipt_sha256") != _sha256(preparation_raw)
        or arm.get("preparation_verification_receipt_exists") is not True
        or arm.get("preparation_verification_receipt_read_status") != "readable"
        or arm.get("preparation_verification_receipt_sha256")
        != _sha256(verification_raw)
    ):
        _fail("arm receipt is not a matching armed receipt")
    for key in (
        "remote_claim_sha256",
        "remote_verifier_claim_sha256",
        "remote_receipt_sha256",
        "remote_supervisor_receipt_sha256",
    ):
        _require_sha(arm.get(key), 64, f"arm receipt {key}")
    immutable_remote_files = {
        "remote_claim_sha256": _EXECUTION_ROOT / "remote-verification-claim.json",
        "remote_verifier_claim_sha256": (
            _EXECUTION_ROOT / "remote-verifier-start-claim.json"
        ),
        "remote_receipt_sha256": _EXECUTION_ROOT / "remote-verification.json",
        "remote_supervisor_receipt_sha256": (
            _EXECUTION_ROOT / "remote-verification-supervisor.json"
        ),
    }
    for digest_key, path in immutable_remote_files.items():
        raw = _immutable_linux_evidence(path, f"immutable Linux {digest_key}")
        if _sha256(raw) != arm.get(digest_key):
            _fail(f"immutable Linux {digest_key} differs from the arm receipt")
    remote_claim_sha = str(arm["remote_claim_sha256"])

    driver, driver_raw = _validate_receipt(
        Path(_DRIVER_CLAIM), keys=_DRIVER_KEYS, schema=_DRIVER_SCHEMA, name="driver claim"
    )
    if (
        driver.get("open_freeze_commit_sha") != open_commit
        or driver.get("registration_content_sha256") != registration_sha
        or driver.get("remote_claim_sha256") != remote_claim_sha
    ):
        _fail("driver claim does not match the arm receipt")
    execution = registration.get("execution_contract")
    driver_argv = (
        execution.get("lifecycle_driver_argv")
        if isinstance(execution, Mapping)
        else None
    )
    if not isinstance(driver_argv, list) or not all(isinstance(item, str) for item in driver_argv):
        _fail("registered lifecycle-driver argv is invalid")
    if driver.get("driver_argv_sha256") != _sha256(_canonical_json_bytes(driver_argv)):
        _fail("driver claim argv digest is invalid")

    prior_sha: str | None = None
    if label == "A":
        if process["prior"] != "null":
            _fail("process A prior-validation binding is invalid")
    else:
        a_process = _PROCESS["A"]
        if process["prior"] != a_process["validation_receipt"]:
            _fail("process B prior-validation path is invalid")
        a_start, a_start_raw = _validate_receipt(
            Path(a_process["start_claim"]),
            keys=_START_KEYS,
            schema=_START_SCHEMA,
            name="process A start claim",
        )
        a_payload_raw = _plain_file_bytes(
            Path(a_process["output"]),
            "process A payload",
            maximum=_PAYLOAD_CAP_BYTES,
        )
        a_validator, a_validator_raw = _validate_receipt(
            Path(a_process["validator_claim"]),
            keys=_VALIDATOR_KEYS,
            schema=_VALIDATOR_SCHEMA,
            name="process A validator claim",
        )
        prior, prior_raw = _validate_receipt(
            Path(a_process["validation_receipt"]),
            keys=_VALIDATION_KEYS,
            schema=_VALIDATION_SCHEMA,
            name="process A validation receipt",
        )
        execution = registration.get("execution_contract")
        if not isinstance(execution, Mapping):
            _fail("registration execution contract is invalid")
        scientific_template = execution.get("scientific_argv_template")
        validator_template = execution.get("payload_validator_argv_template")
        if not isinstance(scientific_template, list) or not isinstance(
            validator_template,
            list,
        ):
            _fail("registered process argv templates are invalid")
        if (
            execution.get("process_a_root") != a_process["root"]
            or execution.get("process_a_output") != a_process["output"]
            or execution.get("process_a_start_claim") != a_process["start_claim"]
            or execution.get("process_a_validator_claim")
            != a_process["validator_claim"]
            or execution.get("process_a_validation_receipt")
            != a_process["validation_receipt"]
        ):
            _fail("registration process A dependency paths are invalid")
        a_scientific_argv = _substituted_scientific_argv(
            scientific_template,
            label="A",
            process=a_process,
        )
        a_validator_argv = _substituted_validator_argv(
            validator_template,
            label="A",
            process=a_process,
        )
        if (
            a_start.get("label") != "A"
            or a_start.get("open_freeze_commit_sha") != open_commit
            or a_start.get("registration_content_sha256") != registration_sha
            or a_start.get("arm_receipt_sha256") != _sha256(arm_raw)
            or a_start.get("lifecycle_driver_claim_sha256") != _sha256(driver_raw)
            or a_start.get("scientific_argv_sha256")
            != _sha256(_canonical_json_bytes(a_scientific_argv))
            or a_start.get("prior_validation_receipt_sha256") is not None
            or a_start.get("output_path") != a_process["output"]
            or a_validator.get("label") != "A"
            or a_validator.get("lifecycle_driver_claim_sha256")
            != _sha256(driver_raw)
            or a_validator.get("start_claim_sha256") != _sha256(a_start_raw)
            or a_validator.get("validator_argv_sha256")
            != _sha256(_canonical_json_bytes(a_validator_argv))
            or a_validator.get("payload_sha256") != _sha256(a_payload_raw)
            or prior.get("label") != "A"
            or prior.get("start_claim_sha256") != _sha256(a_start_raw)
            or prior.get("validator_claim_sha256") != _sha256(a_validator_raw)
            or prior.get("payload_path") != a_process["output"]
            or prior.get("payload_sha256") != _sha256(a_payload_raw)
            or prior.get("payload_size_bytes") != len(a_payload_raw)
            or prior.get("status") != "valid"
        ):
            _fail("process B lacks a fully bound valid process A dependency")
        prior_sha = _sha256(prior_raw)
    return arm_raw, driver_raw, prior_sha, preparation, verification


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # The frozen runner executes on Linux; Windows only hosts the static/unit gate.
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_canonical_windows(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = _canonical_json_bytes(value)
    try:
        parent_before = path.parent.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure("claim parent is unavailable") from exc
    if not stat.S_ISDIR(parent_before.st_mode) or _is_reparse_point(parent_before):
        _fail("claim parent is not a plain Windows directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise _AdministrativeFailure(
            "exclusive scientific start claim creation failed"
        ) from exc
    try:
        created = os.fstat(descriptor)
        if not stat.S_ISREG(created.st_mode) or _is_reparse_point(created):
            _fail("exclusive Windows claim is not a regular file")
        created_inode = (created.st_dev, created.st_ino)
        stream = os.fdopen(descriptor, "wb", closefd=True)
        descriptor = None
        with stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            written = os.fstat(stream.fileno())
            identity = _owned_file_identity(written)
            if (written.st_dev, written.st_ino) != created_inode:
                _fail("exclusive Windows claim identity changed while being written")
        observed = _plain_file_bytes(path, "scientific start claim")
        reopened = path.stat(follow_symlinks=False)
        parent_after = path.parent.stat(follow_symlinks=False)
        if (
            observed != raw
            or _parse_canonical(observed, "scientific start claim") != dict(value)
            or _owned_file_identity(reopened) != identity
            or (parent_after.st_dev, parent_after.st_ino)
            != (parent_before.st_dev, parent_before.st_ino)
        ):
            _fail("scientific start claim failed durable Windows validation")
    except Exception:
        # An acquired claim is irreversible. Never remove it after creation.
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return raw


def _exclusive_canonical(path: Path, value: Mapping[str, Any]) -> bytes:
    if os.name == "nt":
        return _exclusive_canonical_windows(path, value)
    raw = _canonical_json_bytes(value)
    parent_anchor = _open_directory_anchor(path.parent, "claim parent")
    descriptor: int | None = None
    try:
        _revalidate_directory_anchor(parent_anchor)
        component = _single_component(path.name, "scientific start claim basename")
        try:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = (
                os.open(path, flags, 0o600)
                if os.name == "nt"
                else os.open(component, flags, 0o600, dir_fd=parent_anchor.descriptor)
            )
        except OSError as exc:
            raise _AdministrativeFailure(
                "exclusive scientific start claim creation failed"
            ) from exc
        try:
            created = os.fstat(descriptor)
            if (
                not stat.S_ISREG(created.st_mode)
                or stat.S_ISLNK(created.st_mode)
                or created.st_nlink != 1
                or (os.name != "nt" and stat.S_IMODE(created.st_mode) != 0o600)
                or (hasattr(os, "getuid") and created.st_uid != os.getuid())
            ):
                _fail("exclusive claim is not an owned mode-0600 single-link file")
            created_inode = (created.st_dev, created.st_ino)
            stream = os.fdopen(descriptor, "wb", closefd=True)
            descriptor = None
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
                written = os.fstat(stream.fileno())
                identity = _owned_file_identity(written)
                if (
                    (written.st_dev, written.st_ino) != created_inode
                    or written.st_size != len(raw)
                    or not _matches_owned_file(written, identity, links=1)
                ):
                    _fail("exclusive claim identity changed while being written")
            if os.name != "nt":
                os.fsync(parent_anchor.descriptor)
            _revalidate_directory_anchor(parent_anchor)
            observed = (
                _plain_file_bytes(path, "scientific start claim")
                if os.name == "nt"
                else _plain_file_bytes_at(
                    parent_anchor.descriptor,
                    component,
                    "scientific start claim",
                )
            )
            reopened = (
                path.stat(follow_symlinks=False)
                if os.name == "nt"
                else os.stat(
                    component,
                    dir_fd=parent_anchor.descriptor,
                    follow_symlinks=False,
                )
            )
            if observed != raw or _parse_canonical(
                observed, "scientific start claim"
            ) != dict(value) or not _matches_owned_file(reopened, identity, links=1):
                _fail("scientific start claim failed durable validation")
            _revalidate_directory_anchor(parent_anchor)
        except Exception:
            # An acquired claim is irreversible. Never remove it on a later validation error.
            raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_anchor.descriptor)
    return raw


def _acquire_start_claim(
    registration: Mapping[str, Any],
    *,
    label: str,
    process: Mapping[str, str],
    arm_raw: bytes,
    driver_raw: bytes,
    prior_sha: str | None,
    full_argv: Sequence[str],
    open_commit: str,
) -> bytes:
    claim = {
        "schema_version": _START_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "label": label,
        "open_freeze_commit_sha": open_commit,
        "registration_content_sha256": registration.get("content_sha256"),
        "arm_receipt_sha256": _sha256(arm_raw),
        "lifecycle_driver_claim_sha256": _sha256(driver_raw),
        "scientific_argv_sha256": _sha256(_canonical_json_bytes(list(full_argv))),
        "prior_validation_receipt_sha256": prior_sha,
        "output_path": process["output"],
    }
    _require_keys(claim, _START_KEYS, "scientific start claim")
    return _exclusive_canonical(Path(process["start_claim"]), claim)


def _require_before(deadline: float, operation: str) -> None:
    if time.monotonic() >= deadline:
        _fail(f"scientific runner wall deadline elapsed before {operation}")


def _build_valid_fallback(
    audit: ModuleType,
    registration: Mapping[str, Any],
    *,
    stage: str,
    candidate_payload_size_bytes: int | None = None,
) -> tuple[dict[str, Any], bytes]:
    payload = audit.build_global_fallback(
        registration,
        stage,
        candidate_payload_size_bytes=candidate_payload_size_bytes,
    )
    validated = audit.validate_scientific_payload(payload, registration)
    encoded = audit.canonical_json_bytes(validated)
    if len(encoded) > _PAYLOAD_CAP_BYTES:
        _fail("registered global fallback exceeds the payload cap")
    return validated, encoded


def _evaluate(
    audit: ModuleType,
    root: Path,
    registration: Mapping[str, Any],
    *,
    compute_deadline: float,
) -> tuple[dict[str, Any], bytes]:
    # Keep this try boundary operation-for-operation identical to the frozen v7 runner.
    try:
        if time.monotonic() >= compute_deadline:
            raise TimeoutError("compute deadline reached before scientific work")
        candidate = audit.produce_scientific_candidate(
            root,
            registration,
            compute_deadline=compute_deadline,
        )
        if time.monotonic() >= compute_deadline:
            raise TimeoutError("scientific producer returned after the compute deadline")
        payload = audit.finalize_scientific_payload(candidate, registration)
        validated = audit.validate_scientific_payload(payload, registration)
        encoded = audit.canonical_json_bytes(validated)
    except audit.GlobalFallbackRequired as exc:
        return _build_valid_fallback(
            audit,
            registration,
            stage=exc.stage,
            candidate_payload_size_bytes=exc.candidate_payload_size_bytes,
        )
    except Exception:
        return _build_valid_fallback(audit, registration, stage="evaluator_internal_error")

    if len(encoded) <= _PAYLOAD_CAP_BYTES:
        return validated, encoded
    return _build_valid_fallback(
        audit,
        registration,
        stage="payload_size_limit_exceeded",
        candidate_payload_size_bytes=len(encoded),
    )


def _entry_exists_at(parent_descriptor: int, component: str) -> bool:
    try:
        os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise _AdministrativeFailure("output entry cannot be safely inspected") from exc
    return True


def _unlink_owned_output(
    parent_descriptor: int,
    output_component: str,
    staging_component: str,
    digest: str,
) -> None:
    try:
        output_raw = _plain_file_bytes_at(
            parent_descriptor,
            output_component,
            "owned published output",
        )
        output_metadata = os.stat(
            output_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        staging_metadata = os.stat(
            staging_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not _permitted_plain_metadata(output_metadata, _MAX_ADMIN_BYTES)
            or not _permitted_plain_metadata(staging_metadata, _MAX_ADMIN_BYTES)
            or _file_identity(output_metadata) != _file_identity(staging_metadata)
            or _file_change_identity(output_metadata)
            != _file_change_identity(staging_metadata)
            or _sha256(output_raw) != digest
        ):
            return
        os.unlink(output_component, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    except (OSError, _AdministrativeFailure):
        return


def _borrow_output_anchor(
    output: Path,
    value: int | _DirectoryAnchor,
) -> _DirectoryAnchor:
    if isinstance(value, _DirectoryAnchor):
        if value.path != output.parent:
            _fail("scientific output anchor is bound to the wrong fixed path")
        _revalidate_directory_anchor(value)
        return value
    metadata = os.fstat(value)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or (os.name != "nt" and stat.S_IMODE(metadata.st_mode) != 0o700)
        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
    ):
        _fail("borrowed scientific output parent is not owner-controlled mode 0700")
    anchor = _DirectoryAnchor(
        path=output.parent,
        descriptor=value,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        owner_uid=getattr(metadata, "st_uid", -1),
        mode=stat.S_IMODE(metadata.st_mode),
        name="scientific output parent",
    )
    _revalidate_directory_anchor(anchor)
    return anchor


def _unlink_exact_owned_component(
    parent_descriptor: int,
    component: str,
    identity: _OwnedFileIdentity,
    encoded: bytes,
    *,
    allowed_links: set[int],
) -> bool:
    try:
        before = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
        if before.st_nlink not in allowed_links or not _matches_owned_file(
            before,
            identity,
            links=before.st_nlink,
        ):
            return False
        observed = _plain_file_bytes_at(
            parent_descriptor,
            component,
            "owned publication cleanup candidate",
            maximum=max(len(encoded), 1),
        )
        after = os.stat(component, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            observed != encoded
            or after.st_nlink != before.st_nlink
            or not _matches_owned_file(after, identity, links=before.st_nlink)
        ):
            return False
        os.unlink(component, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
        return True
    except (FileNotFoundError, OSError, _AdministrativeFailure):
        return False


def _publish(
    output: Path,
    output_parent_descriptor: int | _DirectoryAnchor,
    payload: Mapping[str, Any],
    encoded: bytes,
    *,
    wall_deadline: float,
    registration: Mapping[str, Any],
    audit: ModuleType,
) -> None:
    _require_before(wall_deadline, "scientific output staging")
    parent_anchor = _borrow_output_anchor(output, output_parent_descriptor)
    _revalidate_directory_anchor(parent_anchor, empty=True)
    parent_descriptor = parent_anchor.descriptor
    output_component = _single_component(output.name, "scientific output basename")
    staging_component = _single_component(
        f".{output.name}.stage-{os.getpid()}",
        "scientific staging basename",
    )
    if _entry_exists_at(parent_descriptor, staging_component):
        _fail("scientific staging path already exists")
    created = False
    published = False
    staging_identity: _OwnedFileIdentity | None = None
    descriptor: int | None = None
    digest = _sha256(encoded)
    try:
        descriptor = os.open(
            staging_component,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        created = True
        initial = os.fstat(descriptor)
        if (
            not stat.S_ISREG(initial.st_mode)
            or stat.S_ISLNK(initial.st_mode)
            or stat.S_IMODE(initial.st_mode) != 0o600
            or initial.st_nlink != 1
            or (hasattr(os, "getuid") and initial.st_uid != os.getuid())
        ):
            _fail("scientific staging file is not owned mode-0600 link-count one")
        initial_inode = (initial.st_dev, initial.st_ino)
        stream = os.fdopen(descriptor, "wb", closefd=True)
        descriptor = None
        with stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
            created_metadata = os.fstat(stream.fileno())
            staging_identity = _owned_file_identity(created_metadata)
            if (
                (created_metadata.st_dev, created_metadata.st_ino) != initial_inode
                or created_metadata.st_size != len(encoded)
                or not _matches_owned_file(
                    created_metadata,
                    staging_identity,
                    links=1,
                )
            ):
                _fail("scientific staging identity changed while being written")

        _require_before(wall_deadline, "scientific output verification")
        _revalidate_directory_anchor(parent_anchor)
        observed = _plain_file_bytes_at(
            parent_descriptor,
            staging_component,
            "staged scientific output",
        )
        if observed != encoded or _sha256(observed) != digest:
            _fail("staged scientific output changed")
        # This validation is intentionally outside the scientific fallback boundary.
        reparsed = audit.validate_scientific_payload(payload, registration)
        if audit.canonical_json_bytes(reparsed) != observed:
            _fail("staged scientific output failed canonical validation")
        staging_metadata = os.stat(
            staging_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if not _matches_owned_file(staging_metadata, staging_identity, links=1):
            _fail("staged scientific output lost its owned identity")
        if sorted(os.listdir(parent_descriptor)) != [staging_component]:
            _fail("scientific output parent acquired an unregistered entry")

        _require_before(wall_deadline, "scientific output publication")
        _revalidate_directory_anchor(parent_anchor)
        os.link(
            staging_component,
            output_component,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        os.fsync(parent_descriptor)
        _revalidate_directory_anchor(parent_anchor)
        output_metadata = os.stat(
            output_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        linked_staging_metadata = os.stat(
            staging_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        published_raw = _plain_file_bytes_at(
            parent_descriptor,
            output_component,
            "published scientific output",
        )
        if (
            not _matches_owned_file(output_metadata, staging_identity, links=2)
            or not _matches_owned_file(
                linked_staging_metadata,
                staging_identity,
                links=2,
            )
            or published_raw != encoded
            or _sha256(published_raw) != digest
        ):
            _fail("published scientific output identity changed")
        if time.monotonic() >= wall_deadline:
            _fail("scientific runner wall deadline elapsed during publication")
        if not _unlink_exact_owned_component(
            parent_descriptor,
            staging_component,
            staging_identity,
            encoded,
            allowed_links={2},
        ):
            _fail("scientific staging link could not be safely removed")
        created = False
        _revalidate_directory_anchor(parent_anchor)
        final_metadata = os.stat(
            output_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        final_raw = _plain_file_bytes_at(
            parent_descriptor,
            output_component,
            "final published scientific output",
        )
        if (
            not _matches_owned_file(final_metadata, staging_identity, links=1)
            or final_raw != encoded
            or _sha256(final_raw) != digest
            or sorted(os.listdir(parent_descriptor)) != [output_component]
        ):
            _fail("final scientific output reopen failed")
        reparsed_final = audit.validate_scientific_payload(payload, registration)
        if audit.canonical_json_bytes(reparsed_final) != final_raw:
            _fail("final scientific output failed canonical validation")
        _revalidate_directory_anchor(parent_anchor)
        durable_raw = _plain_file_bytes_at(
            parent_descriptor,
            output_component,
            "durable final scientific output",
        )
        durable_metadata = os.stat(
            output_component,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            durable_raw != encoded
            or not _matches_owned_file(durable_metadata, staging_identity, links=1)
            or sorted(os.listdir(parent_descriptor)) != [output_component]
        ):
            _fail("durable final scientific output reopen failed")
        _revalidate_directory_anchor(parent_anchor)
        published = True
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if not published and staging_identity is not None:
            _unlink_exact_owned_component(
                parent_descriptor,
                output_component,
                staging_identity,
                encoded,
                allowed_links={1, 2},
            )
        if created and staging_identity is not None:
            _unlink_exact_owned_component(
                parent_descriptor,
                staging_component,
                staging_identity,
                encoded,
                allowed_links={1, 2},
            )
    if not published:
        _fail("scientific output was not published")


def main(argv: Sequence[str] | None = None) -> int:
    started = time.monotonic()
    args = _parse_args(argv)
    process_root_anchor: _DirectoryAnchor | None = None
    output_parent_anchor: _DirectoryAnchor | None = None
    try:
        if argv is not None:
            _fail("programmatic argv is not permitted for the production runner")
        root = Path.cwd().resolve(strict=True)
        registration, registration_raw = _load_registration(root, args.registration)
        label, process, output, compute_deadline, wall_deadline, full_argv = (
            _require_runtime_contract(args, registration, root=root, started=started)
        )
        open_commit = _verify_repository(root, registration, registration_raw)
        arm_raw, driver_raw, prior_sha, preparation, verification = _validate_dependencies(
            registration,
            label=label,
            process=process,
            open_commit=open_commit,
        )
        process_root_anchor, output_parent_anchor = _validate_live_process_gate(
            root,
            output,
            registration,
            label=label,
            open_commit=open_commit,
            preparation=preparation,
            verification=verification,
        )
        _revalidate_directory_anchor(process_root_anchor)
        _revalidate_directory_anchor(output_parent_anchor, empty=True)
        _acquire_start_claim(
            registration,
            label=label,
            process=process,
            arm_raw=arm_raw,
            driver_raw=driver_raw,
            prior_sha=prior_sha,
            full_argv=full_argv,
            open_commit=open_commit,
        )
        _revalidate_directory_anchor(process_root_anchor)
        _revalidate_directory_anchor(output_parent_anchor, empty=True)

        # The import is the first scientific-module access and occurs after the claim.
        audit = importlib.import_module("arc3_voi.action_qbc_v8_audit")
        module_path = getattr(audit, "__file__", None)
        expected_module = (root / "src/arc3_voi/action_qbc_v8_audit.py").resolve(strict=True)
        if not isinstance(module_path, str):
            _fail("imported v8 audit module has no source origin")
        if Path(module_path).resolve(strict=True) != expected_module:
            _fail("imported v8 audit module origin differs from the registered source")
        payload, encoded = _evaluate(
            audit,
            root,
            registration,
            compute_deadline=compute_deadline,
        )
        _revalidate_directory_anchor(process_root_anchor)
        _revalidate_directory_anchor(output_parent_anchor, empty=True)
        _publish(
            output,
            output_parent_anchor,
            payload,
            encoded,
            wall_deadline=wall_deadline,
            registration=registration,
            audit=audit,
        )
    except _AdministrativeFailure as exc:
        print(f"action-QBC v8 administrative failure: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"action-QBC v8 unpublished failure: {exc}", file=sys.stderr)
        return 3
    finally:
        if output_parent_anchor is not None:
            os.close(output_parent_anchor.descriptor)
        if process_root_anchor is not None:
            os.close(process_root_anchor.descriptor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
