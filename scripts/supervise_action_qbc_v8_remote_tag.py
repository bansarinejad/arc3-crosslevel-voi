"""One-shot Windows supervisor for bounded action-QBC v8 remote-tag verification."""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import ctypes
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Final, NoReturn

_SUPERVISOR_RECEIPT_SCHEMA: Final = (
    "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1"
)
_REMOTE_RECEIPT_SCHEMA: Final = "action-qbc-v8-remote-tag-verification-receipt-v1"
_START_CLAIM_SCHEMA: Final = "action-qbc-v8-remote-tag-verifier-start-claim-v1"
_LIFECYCLE_CLAIM_SCHEMA: Final = "action-qbc-v8-remote-tag-verification-claim-v1"
_REGISTRATION_SCHEMA: Final = "action-qbc-v8-open-registration-v1"
_TREATMENT_ID: Final = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_OPEN_FREEZE_TAG: Final = "action-qbc-v8-open-diagnostic-freeze-v3"
_REMOTE_URL: Final = "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
_REMOTE_REF: Final = f"refs/tags/{_OPEN_FREEZE_TAG}"
_PREREGISTRATION_TAG: Final = (
    "prereg-action-qbc-v8-open-bounded-remote-verification-v6"
)
_PREREGISTRATION_COMMIT: Final = "61cebe90a2f4f7c78ec45119de53a482ed13a655"
_PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-18_"
    "action_qbc_v8_open_bounded_remote_verification_v6_runner_manifest_key_recovery.md"
)
_PREREGISTRATION_DOCUMENT_BLOB: Final = "5e870ed0bbbff6fcb4352f6e914d870254773f68"
_PREREGISTRATION_DOCUMENT_SHA256: Final = (
    "0ba4cc55ca2b31433bc458972ffc32d87f84b610673fa22ed2b4dd4a8bfc1a41"
)

_REPOSITORY_ROOT: Final = r"D:\kaggle competitions\arc3-crosslevel-voi"
_NEUTRAL_GIT_CWD: Final = r"D:\kaggle competitions"
_NONEXISTENT_HOME: Final = r"D:\kaggle competitions\arc3-v8-nonexistent-home"
_REGISTRATION_PATH: Final = "artifacts/action_qbc_v8_open_registration.json"
_SUPERVISOR_SCRIPT: Final = "scripts/supervise_action_qbc_v8_remote_tag.py"
_VERIFIER_SCRIPT: Final = "scripts/verify_action_qbc_v8_remote_tag.py"
_REGISTRATION_ARGV_PATH: Final = r"artifacts\action_qbc_v8_open_registration.json"
_SUPERVISOR_ARGV_SCRIPT: Final = r"scripts\supervise_action_qbc_v8_remote_tag.py"
_VERIFIER_ARGV_SCRIPT: Final = r"scripts\verify_action_qbc_v8_remote_tag.py"
_CLAIM_PATH: Final = (
    r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json"
)
_START_CLAIM_PATH: Final = (
    r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim.json"
)
_REMOTE_RECEIPT_PATH: Final = (
    r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification.json"
)
_SUPERVISOR_RECEIPT_PATH: Final = (
    r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-"
    "supervisor.json"
)

_PYTHON_PATH: Final = r"C:\Users\User\anaconda3\python.exe"
_PYTHON_VERSION: Final = "CPython 3.12.3"
_PYTHON_SHA256: Final = "62c225fb9cdc41b139c7024581c233644f975ffc35314558c60ebefa6b88be01"
_GIT_PATH: Final = r"C:\Users\User\anaconda3\Library\bin\git.exe"
_GIT_VERSION: Final = "2.45.2.windows.1"
_GIT_SHA256: Final = "5385ff9ae361ca41e7a31b335fc0d81f2de9c35fc62a165c5e34850d837b59cc"
_TASKKILL_PATH: Final = r"C:\Windows\System32\taskkill.exe"
_TASKKILL_VERSION: Final = "file/product version 10.0.26100.8457"
_TASKKILL_SHA256: Final = (
    "1249717315fc8f4d2df17d5db9da0444795fdb9fb83dfb1f763c3f39282244f7"
)

_MAX_ATTEMPTS: Final = 3
_ATTEMPT_TIMEOUT_SECONDS: Final = 120
_RETRY_DELAY_SECONDS: Final = 15
_OVERALL_DEADLINE_SECONDS: Final = 390
_VERIFIER_CHILD_DEADLINE_SECONDS: Final = 430
_SUPERVISOR_DEADLINE_SECONDS: Final = 480
_SUPERVISOR_RECEIPT_RESERVE_SECONDS: Final = 20
_STDOUT_CAP_BYTES: Final = 4_096
_STDERR_CAP_BYTES: Final = 16_384
_CHILD_CLEANUP_TIMEOUT_SECONDS: Final = 30
_REGISTERED_LOCAL_GIT_TIMEOUT_SECONDS: Final = 60
_WINDOWS_GIT_CHILD_TIMEOUT_SECONDS: Final = 60
_LOCAL_GIT_STDOUT_CAP_BYTES: Final = 134_217_728
_SYNTHETIC_TIMEOUT_EXIT: Final = 124

_CREATE_SUSPENDED: Final = 0x00000004
_CREATE_NEW_PROCESS_GROUP: Final = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS: Final = 9
_JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS: Final = 1

_REGISTRATION_KEYS: Final = {
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
_EXECUTION_KEYS: Final = {
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
_AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v8_enabled": False,
    "final_admission_claimed": False,
}
_ARGV_HASH_KEYS: Final = {
    "arm",
    "bootstrap",
    "environment_build",
    "finalizer",
    "lifecycle_driver",
    "linux_host_launcher",
    "payload_validator",
    "post_preparation_validation",
    "preflight",
    "preparation",
    "producer",
    "reconstructor",
    "remote_supervisor",
    "remote_verifier",
    "result_publisher",
    "result_ref_transaction",
    "scientific",
    "tests",
}
_CLAIM_KEYS: Final = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "supervisor_argv_sha256",
    "supervisor_script_git_blob_sha1",
    "supervisor_script_sha256",
    "verifier_script_git_blob_sha1",
    "verifier_script_sha256",
}
_START_CLAIM_KEYS: Final = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "verifier_argv_sha256",
}
_REMOTE_RECEIPT_KEYS: Final = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "verifier_start_claim_sha256",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "remote_url",
    "ref",
    "python",
    "git",
    "taskkill",
    "policy",
    "attempts",
    "status",
    "selected_attempt",
    "total_duration_milliseconds",
}
_ATTEMPT_KEYS: Final = {
    "attempt_index",
    "exit_code",
    "classification",
    "timed_out",
    "duration_milliseconds",
    "stdout_size_bytes",
    "stdout_sha256",
    "stdout_base64",
    "stderr_size_bytes",
    "stderr_sha256",
    "stderr_base64",
    "child_cleanup_passes",
}
_SUPERVISOR_RECEIPT_KEYS: Final = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "verifier_start_claim_sha256",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "verifier_argv_sha256",
    "verifier_exit_code",
    "classification",
    "timed_out",
    "duration_milliseconds",
    "stdout_size_bytes",
    "stdout_sha256",
    "stdout_base64",
    "stderr_size_bytes",
    "stderr_sha256",
    "stderr_base64",
    "child_cleanup_passes",
    "remote_receipt_sha256",
    "status",
}
_SUPERVISOR_CLASSIFICATIONS: Final = {
    "verifier_completed",
    "verifier_timeout_124",
    "stdout_limit",
    "stderr_limit",
    "child_cleanup_failed",
    "spawn_error",
    "remote_receipt_missing",
    "remote_receipt_invalid",
    "post_spawn_initialization_failed",
    "stream_capture_failed",
}
_ATTEMPT_CLASSIFICATIONS: Final = {
    "verified",
    "retryable_empty_exit_0",
    "retryable_timeout_124",
    "retryable_git_128",
    "unexpected_output",
    "unexpected_exit",
    "stdout_limit",
    "stderr_limit",
    "child_cleanup_failed",
    "spawn_error",
    "overall_deadline",
    "post_spawn_initialization_failed",
    "stream_capture_failed",
}
_RETRYABLE_CLASSIFICATIONS: Final = {
    "retryable_empty_exit_0",
    "retryable_timeout_124",
    "retryable_git_128",
}

_WINDOWS_REPOSITORY_CONTRACT_KEYS: Final = {
    "active_hooks_allowed",
    "common_directory",
    "forbidden_admin_relative_paths",
    "forbidden_pack_suffixes",
    "forbidden_ref_prefixes",
    "git_config_byte_count",
    "git_config_sha256",
    "git_directory",
    "index_path",
    "info_exclude_byte_count",
    "info_exclude_sha256",
    "local_config",
    "plain_admin_relative_directories",
    "repository_ancestor_chain",
    "repository_root",
}


def _windows_repository_contract() -> dict[str, Any]:
    return {
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

_O8_ADDITIONS: Final = {
    "artifacts/action_qbc_v8_open_registration.json",
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
}


def _repository_metadata_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int, int]:
    changed = _file_change_identity(metadata)
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        stat.S_IMODE(metadata.st_mode),
        metadata.st_size,
        int(getattr(metadata, "st_file_attributes", 0)),
        changed[0],
        changed[1],
    )


def _contract_relative(root: Path, relative: str) -> Path:
    return root.joinpath(*relative.split("\\"))


def _plain_directory_metadata(path: Path, name: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"{name} is unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or _is_reparse_point(metadata)
    ):
        _fail(f"{name} is not a plain non-reparse directory")
    return metadata


def _plain_file_metadata(path: Path, name: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(metadata, 1 << 40):
        _fail(f"{name} is not a plain non-reparse regular file")
    return metadata


def _snapshot_tree(
    root: Path,
    relative: str,
    entries: dict[str, tuple[int, int, int, int, int, int, int, int]],
) -> None:
    base = _contract_relative(root, relative)
    _plain_directory_metadata(base, relative)
    pending: list[tuple[Path, str]] = [(base, relative)]
    while pending:
        directory, prefix = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise _ProtocolFailure(f"cannot enumerate {prefix}") from exc
        for child in children:
            child_relative = f"{prefix}\\{child.name}"
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise _ProtocolFailure(f"cannot inspect {child_relative}") from exc
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse_point(metadata):
                _fail(f"{child_relative} is a symlink or reparse point")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((Path(child.path), child_relative))
            elif not stat.S_ISREG(metadata.st_mode):
                _fail(f"{child_relative} is not a plain file or directory")
            entries[child_relative] = _repository_metadata_identity(metadata)


def _parse_git_index(data: bytes) -> dict[str, tuple[str, str]]:
    if len(data) < 32 or data[:4] != b"DIRC":
        _fail("Git index header is invalid")
    if hashlib.sha1(data[:-20], usedforsecurity=False).digest() != data[-20:]:
        _fail("Git index checksum is invalid")
    version = int.from_bytes(data[4:8], "big")
    if version not in {2, 3}:
        _fail("Git index version is not the supported ordinary form")
    count = int.from_bytes(data[8:12], "big")
    offset = 12
    entries: dict[str, tuple[str, str]] = {}
    for _index in range(count):
        start = offset
        if offset + 62 > len(data) - 20:
            _fail("Git index entry is truncated")
        mode = int.from_bytes(data[offset + 24 : offset + 28], "big")
        oid = data[offset + 40 : offset + 60].hex()
        flags = int.from_bytes(data[offset + 60 : offset + 62], "big")
        if flags & 0xF000:
            _fail("Git index entry has a nonordinary cache flag or stage")
        name_start = offset + 62
        name_end = data.find(b"\0", name_start, len(data) - 20)
        if name_end < 0:
            _fail("Git index pathname is unterminated")
        raw_name = data[name_start:name_end]
        try:
            path = raw_name.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure("Git index pathname is not UTF-8") from exc
        parts = path.split("/")
        if (
            not path
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in parts)
            or path in entries
        ):
            _fail("Git index pathname is invalid or duplicated")
        encoded_length = flags & 0x0FFF
        if encoded_length != 0x0FFF and encoded_length != len(raw_name):
            _fail("Git index pathname length flag is invalid")
        entries[path] = (f"{mode:o}", oid)
        consumed = name_end + 1 - start
        offset = start + ((consumed + 7) // 8) * 8
    extension_end = len(data) - 20
    while offset < extension_end:
        if offset + 8 > extension_end:
            _fail("Git index extension header is truncated")
        signature = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "big")
        offset += 8
        if offset + size > extension_end:
            _fail("Git index extension is truncated")
        if signature in {b"link", b"sdir"}:
            _fail("split or sparse Git index extension is forbidden")
        offset += size
    if offset != extension_end:
        _fail("Git index trailing structure is invalid")
    return entries


def _parse_ls_tree(data: bytes) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    records = data.split(b"\0")
    if not records or records[-1] != b"":
        _fail("Git ls-tree output is malformed")
    for record in records[:-1]:
        metadata, separator, raw_path = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[1] != b"blob":
            _fail("Git ls-tree entry is not an ordinary blob")
        try:
            path = raw_path.decode("utf-8", errors="strict")
            mode = fields[0].decode("ascii", errors="strict")
            oid = fields[2].decode("ascii", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise _ProtocolFailure("Git ls-tree output is not strict text") from exc
        _require_lower_hex(oid, 40, "Git tree blob")
        if path in result:
            _fail("Git ls-tree contains a duplicate path")
        result[path] = (mode, oid)
    return result


def _parse_ls_files_stage(data: bytes) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    records = data.split(b"\0")
    if not records or records[-1] != b"":
        _fail("Git ls-files stage output is malformed")
    for record in records[:-1]:
        metadata, separator, raw_path = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[2] != b"0":
            _fail("Git index contains an unmerged or non-stage-zero entry")
        try:
            path = raw_path.decode("utf-8", errors="strict")
            mode = fields[0].decode("ascii", errors="strict")
            oid = fields[1].decode("ascii", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise _ProtocolFailure("Git ls-files output is not strict text") from exc
        _require_lower_hex(oid, 40, "Git index blob")
        if path in result:
            _fail("Git ls-files contains a duplicate path")
        result[path] = (mode, oid)
    return result


def _parse_local_config(data: bytes) -> dict[str, str]:
    records = data.split(b"\0")
    if not records or records[-1] != b"":
        _fail("local Git config output is malformed")
    result: dict[str, str] = {}
    for record in records[:-1]:
        raw_key, separator, raw_value = record.partition(b"\n")
        if not separator:
            _fail("local Git config record lacks its key/value separator")
        try:
            key = raw_key.decode("utf-8", errors="strict").lower()
            value = raw_value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure("local Git config is not strict UTF-8") from exc
        if not key or key in result:
            _fail("local Git config contains an empty or duplicate key")
        result[key] = value
    return result


def _capture_repository_snapshot(
    contract: Mapping[str, Any],
) -> _RepositorySnapshot:
    if dict(contract) != _windows_repository_contract():
        _fail("Windows repository contract differs from the frozen object")
    root = Path(str(contract["repository_root"]))
    entries: dict[str, tuple[int, int, int, int, int, int, int, int]] = {}
    chain = contract["repository_ancestor_chain"]
    if not isinstance(chain, list):
        _fail("repository ancestor chain is invalid")
    prior: Path | None = None
    for index, raw_path in enumerate(chain):
        if not isinstance(raw_path, str):
            _fail("repository ancestor chain member is invalid")
        path = Path(raw_path)
        metadata = _plain_directory_metadata(path, f"repository ancestor {index}")
        lexical = os.path.normcase(os.path.abspath(str(path)))
        if lexical != os.path.normcase(raw_path):
            _fail("repository ancestor is not its registered lexical absolute path")
        if prior is not None and os.path.normcase(str(path.parent)) != os.path.normcase(
            str(prior)
        ):
            _fail("repository ancestor chain is not component-wise contiguous")
        entries[f"ancestor:{index}:{raw_path}"] = _repository_metadata_identity(metadata)
        prior = path
    if prior is None or os.path.normcase(str(prior)) != os.path.normcase(str(root)):
        _fail("repository ancestor chain does not terminate at repository root")

    directories = contract["plain_admin_relative_directories"]
    if not isinstance(directories, list):
        _fail("plain administrative directory inventory is invalid")
    for relative in directories:
        if not isinstance(relative, str):
            _fail("plain administrative directory path is invalid")
        metadata = _plain_directory_metadata(
            _contract_relative(root, relative), relative
        )
        entries[f"directory:{relative}"] = _repository_metadata_identity(metadata)

    for relative in contract["forbidden_admin_relative_paths"]:
        forbidden = _contract_relative(root, str(relative))
        try:
            forbidden.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise _ProtocolFailure(f"cannot inspect forbidden path {relative}") from exc
        else:
            _fail(f"forbidden administrative source exists: {relative}")

    git_root = _contract_relative(root, ".git")
    for child in os.scandir(git_root):
        if child.name.casefold().startswith("sharedindex."):
            _fail("shared Git index is forbidden")

    hooks = _contract_relative(root, r".git\hooks")
    for child in os.scandir(hooks):
        metadata = child.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or _is_reparse_point(metadata)
            or not child.name.endswith(".sample")
        ):
            _fail("active or unsafe Git hook is forbidden")

    pack = _contract_relative(root, r".git\objects\pack")
    suffixes = tuple(str(item).casefold() for item in contract["forbidden_pack_suffixes"])
    for child in os.scandir(pack):
        if child.name.casefold().endswith(suffixes):
            _fail("promisor object-pack sidecar is forbidden")

    for relative in (r".git\objects", r".git\refs", r".git\hooks", r".git\info"):
        _snapshot_tree(root, relative, entries)

    packed_refs = _contract_relative(root, r".git\packed-refs")
    try:
        packed_refs.lstat()
    except FileNotFoundError:
        packed_present = False
        packed_data = b""
    except OSError as exc:
        raise _ProtocolFailure("cannot inspect packed refs") from exc
    else:
        packed_present = True
        packed_data = _read_plain_file(packed_refs, "packed refs")
    forbidden_prefixes = tuple(
        str(item).encode("ascii") for item in contract["forbidden_ref_prefixes"]
    )
    for line in packed_data.splitlines():
        if not line or line.startswith((b"#", b"^")):
            continue
        oid, separator, reference = line.partition(b" ")
        if not separator:
            _fail("packed refs contains a malformed record")
        try:
            _require_lower_hex(oid.decode("ascii"), 40, "packed-ref object")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure("packed-ref object is not ASCII") from exc
        if reference.startswith(forbidden_prefixes):
            _fail("packed replacement ref is forbidden")

    for relative in (r".git\HEAD", r".git\config", r".git\info\exclude"):
        path = _contract_relative(root, relative)
        entries[f"file:{relative}"] = _repository_metadata_identity(
            _plain_file_metadata(path, relative)
        )
    if packed_present:
        entries[r"file:.git\packed-refs"] = _repository_metadata_identity(
            _plain_file_metadata(packed_refs, "packed refs")
        )

    config = _read_plain_file(_contract_relative(root, r".git\config"), "Git config")
    exclude = _read_plain_file(
        _contract_relative(root, r".git\info\exclude"), "Git info/exclude"
    )
    index_path = Path(str(contract["index_path"]))
    index_metadata = _plain_file_metadata(index_path, "Git index")
    entries["file:index"] = _repository_metadata_identity(index_metadata)
    index = _read_plain_file(index_path, "Git index", maximum=134_217_728)
    _parse_git_index(index)
    if (
        len(config) != contract["git_config_byte_count"]
        or hashlib.sha256(config).hexdigest() != contract["git_config_sha256"]
    ):
        _fail("Git config bytes differ from the registered identity")
    if (
        len(exclude) != contract["info_exclude_byte_count"]
        or hashlib.sha256(exclude).hexdigest() != contract["info_exclude_sha256"]
    ):
        _fail("Git info/exclude bytes differ from the registered identity")
    return _RepositorySnapshot(
        tuple(sorted(entries.items())),
        hashlib.sha256(index).hexdigest(),
        hashlib.sha256(config).hexdigest(),
        hashlib.sha256(exclude).hexdigest(),
    )


def _validate_repository_git_contract(
    commit: str,
    contract: Mapping[str, Any],
    *,
    overall_deadline_ns: int,
) -> None:
    root = str(contract["repository_root"])
    absolute_git = _run_git_command(
        ["-C", root, "rev-parse", "--absolute-git-dir"],
        overall_deadline_ns=overall_deadline_ns,
    )
    absolute_common = _run_git_command(
        ["-C", root, "rev-parse", "--path-format=absolute", "--git-common-dir"],
        overall_deadline_ns=overall_deadline_ns,
    )
    for observed, expected, name in (
        (absolute_git, contract["git_directory"], "Git directory"),
        (absolute_common, contract["common_directory"], "Git common directory"),
    ):
        try:
            text = observed.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure(f"{name} output is not UTF-8") from exc
        if not text.endswith("\n") or text.count("\n") != 1:
            _fail(f"{name} output is malformed")
        normalized = os.path.normcase(os.path.abspath(os.path.normpath(text[:-1])))
        if normalized != os.path.normcase(str(expected)):
            _fail(f"{name} differs from the registered path")

    config = _parse_local_config(
        _run_git_command(
            ["-C", root, "config", "--local", "--null", "--list"],
            overall_deadline_ns=overall_deadline_ns,
        )
    )
    if config != contract["local_config"]:
        _fail("local Git config differs from the exact registered mapping")

    tree = _parse_ls_tree(
        _run_git_command(
            ["-C", root, "ls-tree", "-r", "-z", commit],
            overall_deadline_ns=overall_deadline_ns,
        )
    )
    staged = _parse_ls_files_stage(
        _run_git_command(
            ["-C", root, "ls-files", "--stage", "-z"],
            overall_deadline_ns=overall_deadline_ns,
        )
    )
    index_data = _read_plain_file(
        Path(str(contract["index_path"])), "Git index", maximum=134_217_728
    )
    parsed_index = _parse_git_index(index_data)
    if tree != staged or tree != parsed_index:
        _fail("Git index is not the exact ordinary stage-zero O8 tree")
    flags = _run_git_command(
        ["-C", root, "ls-files", "-v", "-z"],
        overall_deadline_ns=overall_deadline_ns,
    )
    records = flags.split(b"\0")
    if not records or records[-1] != b"":
        _fail("Git cache-flag output is malformed")
    ordinary_paths: set[str] = set()
    for record in records[:-1]:
        if not record.startswith(b"H "):
            _fail("Git index contains a nonordinary cache-entry flag")
        try:
            path = record[2:].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure("Git cache-flag path is not UTF-8") from exc
        if path in ordinary_paths:
            _fail("Git cache-flag output contains a duplicate path")
        ordinary_paths.add(path)
    if ordinary_paths != set(tree):
        _fail("Git cache-flag inventory differs from the O8 tree")


def _require_repository_snapshot_unchanged(
    before: _RepositorySnapshot,
    contract: Mapping[str, Any],
) -> None:
    after = _capture_repository_snapshot(contract)
    if after != before:
        _fail("Windows repository administrative state changed during evidence reads")


class _ProtocolFailure(RuntimeError):
    """A supervisor identity or one-shot lifecycle invariant failed closed."""


def _fail(message: str) -> NoReturn:
    raise _ProtocolFailure(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise _ProtocolFailure("value is not canonical-JSON encodable") from exc


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
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ProtocolFailure(f"{name} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != data:
        _fail(f"{name} is not an exact canonical JSON object")
    return value


def _require_keys(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        _fail(f"{name} has an invalid key set")


def _require_lower_hex(value: Any, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{name} is not {length}-character lowercase hexadecimal")
    return value


def _require_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(f"{name} is not a non-negative integer")
    return value


def _require_exit_code(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{name} is not an integer")
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


def _read_plain_file(path: Path, name: str, *, maximum: int = 134_217_728) -> bytes:
    try:
        before_path = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(before_path, maximum):
        _fail(f"{name} is not a plain file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _ProtocolFailure(f"{name} cannot be safely opened") from exc
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
        raise _ProtocolFailure(f"{name} cannot be read") from exc
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"{name} changed while being read") from exc
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


def _sha256_file(path: Path, name: str) -> str:
    return hashlib.sha256(_read_plain_file(path, name)).hexdigest()


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("ascii") + data,
        usedforsecurity=False,
    ).hexdigest()


def _git_environment() -> dict[str, str]:
    return {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "COMSPEC": r"C:\Windows\System32\cmd.exe",
        "TEMP": r"C:\Users\User\AppData\Local\Temp",
        "TMP": r"C:\Users\User\AppData\Local\Temp",
        "PATH": (
            r"C:\Users\User\anaconda3\Library\mingw64\bin;"
            r"C:\Users\User\anaconda3\Library\usr\bin;"
            r"C:\Users\User\anaconda3\Library\bin;"
            r"C:\Windows\System32;C:\Windows"
        ),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "HOME": _NONEXISTENT_HOME,
        "XDG_CONFIG_HOME": _NONEXISTENT_HOME,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "NUL",
        "GIT_CONFIG_COUNT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "NUL",
        "SSH_ASKPASS": "NUL",
    }


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
        "git_child_cwd": _NEUTRAL_GIT_CWD,
        "git_environment": _git_environment(),
    }


def _expected_verifier_argv() -> list[str]:
    return [
        _PYTHON_PATH,
        "-I",
        "-B",
        _VERIFIER_ARGV_SCRIPT,
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION_ARGV_PATH,
        "--claim",
        _CLAIM_PATH,
        "--verifier-start-claim",
        _START_CLAIM_PATH,
        "--receipt",
        _REMOTE_RECEIPT_PATH,
        "--git-executable",
        _GIT_PATH,
        "--taskkill-executable",
        _TASKKILL_PATH,
        "--max-attempts",
        str(_MAX_ATTEMPTS),
        "--attempt-timeout-seconds",
        str(_ATTEMPT_TIMEOUT_SECONDS),
        "--retry-delay-seconds",
        str(_RETRY_DELAY_SECONDS),
        "--overall-deadline-seconds",
        str(_OVERALL_DEADLINE_SECONDS),
    ]


def _expected_supervisor_argv() -> list[str]:
    return [
        _PYTHON_PATH,
        "-I",
        "-B",
        _SUPERVISOR_ARGV_SCRIPT,
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION_ARGV_PATH,
        "--claim",
        _CLAIM_PATH,
        "--verifier-start-claim",
        _START_CLAIM_PATH,
        "--remote-receipt",
        _REMOTE_RECEIPT_PATH,
        "--supervisor-receipt",
        _SUPERVISOR_RECEIPT_PATH,
        "--verifier-python",
        _PYTHON_PATH,
        "--git-executable",
        _GIT_PATH,
        "--taskkill-executable",
        _TASKKILL_PATH,
        "--verifier-child-deadline-seconds",
        str(_VERIFIER_CHILD_DEADLINE_SECONDS),
        "--supervisor-deadline-seconds",
        str(_SUPERVISOR_DEADLINE_SECONDS),
        "--child-cleanup-timeout-seconds",
        str(_CHILD_CLEANUP_TIMEOUT_SECONDS),
    ]


@dataclass(frozen=True, slots=True)
class _Registration:
    value: dict[str, Any]
    execution: dict[str, Any]
    supervisor_manifest: dict[str, Any]
    verifier_manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ManagedResult:
    spawned: bool
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    duration_milliseconds: int
    reason: str | None
    timed_out: bool
    cleanup_passes: bool | None


@dataclass(frozen=True, slots=True)
class _SpawnedState:
    process: subprocess.Popen[bytes]
    job: _WindowsJob
    initialization_failed: bool
    job_assigned: bool


@dataclass(frozen=True, slots=True)
class _RepositorySnapshot:
    entries: tuple[
        tuple[str, tuple[int, int, int, int, int, int, int, int]], ...
    ]
    index_sha256: str
    config_sha256: str
    exclude_sha256: str


def _manifest_entry(registration: Mapping[str, Any], path: str) -> dict[str, Any]:
    manifest = registration.get("source_manifest")
    if not isinstance(manifest, dict):
        _fail("registration source_manifest is invalid")
    _require_keys(
        manifest,
        {"preregistration_tree", "open_freeze_added_files", "manifest_sha256"},
        "source_manifest",
    )
    preimage = {
        "preregistration_tree": manifest["preregistration_tree"],
        "open_freeze_added_files": manifest["open_freeze_added_files"],
    }
    if manifest["manifest_sha256"] != canonical_sha256(preimage):
        _fail("source manifest digest is invalid")
    validated: dict[str, list[dict[str, Any]]] = {}
    for collection_name in ("preregistration_tree", "open_freeze_added_files"):
        rows = manifest[collection_name]
        if not isinstance(rows, list):
            _fail(f"{collection_name} manifest is not a list")
        checked: list[dict[str, Any]] = []
        paths: list[str] = []
        for value in rows:
            if not isinstance(value, dict):
                _fail(f"{collection_name} manifest row is not an object")
            _require_keys(
                value,
                {"mode", "path", "git_blob_sha1", "sha256", "byte_count"},
                f"{collection_name} manifest row",
            )
            row_path = value["path"]
            if value["mode"] != "100644" or not isinstance(row_path, str) or not row_path:
                _fail(f"{collection_name} manifest path is invalid")
            paths.append(row_path)
            _require_lower_hex(value["git_blob_sha1"], 40, "manifest Git blob")
            _require_lower_hex(value["sha256"], 64, "manifest SHA-256")
            _require_int(value["byte_count"], "manifest byte count")
            checked.append(value)
        if paths != sorted(
            paths,
            key=lambda item: item.encode("utf-8"),
        ) or len(set(paths)) != len(paths):
            _fail(f"{collection_name} manifest is not uniquely path sorted")
        validated[collection_name] = checked
    matches = [
        value
        for value in validated["open_freeze_added_files"]
        if value["path"] == path
    ]
    if len(matches) != 1:
        _fail("open-freeze manifest path identity is invalid")
    return dict(matches[0])


def _load_registration(root: Path) -> _Registration:
    data = _read_plain_file(root / Path(_REGISTRATION_PATH), "registration")
    value = _parse_canonical_object(data, "registration")
    _require_keys(value, _REGISTRATION_KEYS, "registration")
    if (
        value["schema_version"] != _REGISTRATION_SCHEMA
        or value["status"] != "registered_zero_result"
        or value["treatment_id"] != _TREATMENT_ID
        or value["runtime_id"] is not None
        or value["authorization"] != _AUTHORIZATION
    ):
        _fail("registration fixed identity is invalid")
    if value["preregistration"] != {
        "commit_sha": _PREREGISTRATION_COMMIT,
        "tag": _PREREGISTRATION_TAG,
        "document_path": _PREREGISTRATION_DOCUMENT,
        "document_git_blob_sha1": _PREREGISTRATION_DOCUMENT_BLOB,
        "document_sha256": _PREREGISTRATION_DOCUMENT_SHA256,
    }:
        _fail("registration P8v5 preregistration identity is invalid")
    content = {key: item for key, item in value.items() if key != "content_sha256"}
    if value["content_sha256"] != canonical_sha256(content):
        _fail("registration content digest is invalid")
    execution_value = value["execution_contract"]
    if not isinstance(execution_value, dict):
        _fail("execution contract is invalid")
    execution = execution_value
    _require_keys(execution, _EXECUTION_KEYS, "execution_contract")
    windows_contract = execution["windows_repository_contract"]
    if not isinstance(windows_contract, dict):
        _fail("registration Windows repository contract is invalid")
    _require_keys(
        windows_contract,
        _WINDOWS_REPOSITORY_CONTRACT_KEYS,
        "windows_repository_contract",
    )
    if windows_contract != _windows_repository_contract():
        _fail("registration Windows repository contract is invalid")
    if (
        execution.get("remote_policy") != _remote_policy()
        or execution.get("local_git_timeout_seconds")
        != _REGISTERED_LOCAL_GIT_TIMEOUT_SECONDS
        or execution.get("remote_supervisor_argv") != _expected_supervisor_argv()
        or execution.get("remote_verifier_argv") != _expected_verifier_argv()
        or execution.get("remote_claim_windows_path") != _CLAIM_PATH
        or execution.get("remote_verifier_claim_windows_path") != _START_CLAIM_PATH
        or execution.get("remote_receipt_windows_path") != _REMOTE_RECEIPT_PATH
        or execution.get("remote_supervisor_receipt_windows_path")
        != _SUPERVISOR_RECEIPT_PATH
    ):
        _fail("registration remote execution contract is invalid")
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, dict):
        _fail("registration argv hashes are invalid")
    _require_keys(hashes, _ARGV_HASH_KEYS, "argv_hashes")
    for name, digest in hashes.items():
        _require_lower_hex(digest, 64, f"argv_hashes.{name}")
    if (
        hashes["remote_supervisor"] != canonical_sha256(_expected_supervisor_argv())
        or hashes["remote_verifier"] != canonical_sha256(_expected_verifier_argv())
    ):
        _fail("registered remote argv hash is invalid")
    supervisor = _manifest_entry(value, _SUPERVISOR_SCRIPT)
    verifier = _manifest_entry(value, _VERIFIER_SCRIPT)
    for path, entry in ((_SUPERVISOR_SCRIPT, supervisor), (_VERIFIER_SCRIPT, verifier)):
        raw = _read_plain_file(root / Path(path), path)
        if (
            len(raw) != entry["byte_count"]
            or hashlib.sha256(raw).hexdigest() != entry["sha256"]
            or _git_blob_sha1(raw) != entry["git_blob_sha1"]
        ):
            _fail(f"raw script identity differs from registration: {path}")
    return _Registration(value, execution, supervisor, verifier)


def _tool_object(path_text: str, version: str, digest: str, name: str) -> dict[str, str]:
    if _sha256_file(Path(path_text), name) != digest:
        _fail(f"{name} executable SHA-256 is invalid")
    return {"path": path_text, "version": version, "sha256": digest}


def _validate_tools() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    if os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(_PYTHON_PATH):
        _fail("supervisor Python executable differs from registration")
    if sys.implementation.name != "cpython" or sys.version_info[:3] != (3, 12, 3):
        _fail("supervisor Python version differs from registration")
    return (
        _tool_object(_PYTHON_PATH, _PYTHON_VERSION, _PYTHON_SHA256, "Python"),
        _tool_object(_GIT_PATH, _GIT_VERSION, _GIT_SHA256, "Git"),
        _tool_object(_TASKKILL_PATH, _TASKKILL_VERSION, _TASKKILL_SHA256, "taskkill"),
    )


def _claim_object(registration: _Registration, commit: str) -> dict[str, Any]:
    return {
        "schema_version": _LIFECYCLE_CLAIM_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": registration.value["content_sha256"],
        "supervisor_argv_sha256": registration.execution["argv_hashes"]["remote_supervisor"],
        "supervisor_script_git_blob_sha1": registration.supervisor_manifest["git_blob_sha1"],
        "supervisor_script_sha256": registration.supervisor_manifest["sha256"],
        "verifier_script_git_blob_sha1": registration.verifier_manifest["git_blob_sha1"],
        "verifier_script_sha256": registration.verifier_manifest["sha256"],
    }


def _validate_claim(value: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    _require_keys(value, _CLAIM_KEYS, "lifecycle claim")
    _require_lower_hex(value["open_freeze_commit_sha"], 40, "open-freeze commit")
    if value != expected:
        _fail("lifecycle claim is invalid")


def _validate_start_claim(
    data: bytes,
    *,
    registration: _Registration,
    claim: Mapping[str, Any],
    claim_sha256: str,
) -> dict[str, Any]:
    value = _parse_canonical_object(data, "verifier-start claim")
    _require_keys(value, _START_CLAIM_KEYS, "verifier-start claim")
    expected = {
        "schema_version": _START_CLAIM_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "claim_sha256": claim_sha256,
        "open_freeze_commit_sha": claim["open_freeze_commit_sha"],
        "registration_content_sha256": registration.value["content_sha256"],
        "verifier_argv_sha256": registration.execution["argv_hashes"]["remote_verifier"],
    }
    if value != expected:
        _fail("verifier-start claim is invalid")
    return value


def _publish_canonical(
    path: Path,
    value: Mapping[str, Any],
    validator: Callable[[Mapping[str, Any]], None],
    purpose: str,
) -> bytes:
    data = canonical_json_bytes(value)
    parent = path.parent
    parent_meta = parent.lstat()
    if not stat.S_ISDIR(parent_meta.st_mode) or stat.S_ISLNK(parent_meta.st_mode):
        _fail(f"{purpose} parent is not a plain directory")
    stage = path.with_name(f".{path.name}.{purpose}-stage-{os.getpid()}")
    descriptor: int | None = None
    identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            stage,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = stage.stat(follow_symlinks=False)
        identity = (metadata.st_dev, metadata.st_ino)
        observed = _read_plain_file(stage, f"staged {purpose}")
        if observed != data or hashlib.sha256(observed).digest() != hashlib.sha256(data).digest():
            _fail(f"staged {purpose} bytes changed")
        validator(_parse_canonical_object(observed, f"staged {purpose}"))
        try:
            os.link(stage, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise _ProtocolFailure(f"{purpose} already exists") from exc
        except OSError as exc:
            raise _ProtocolFailure(f"{purpose} cannot be published exclusively") from exc
        final_meta = path.stat(follow_symlinks=False)
        final_data = _read_plain_file(path, f"published {purpose}")
        if (
            (final_meta.st_dev, final_meta.st_ino) != identity
            or final_data != data
            or hashlib.sha256(final_data).digest() != hashlib.sha256(data).digest()
        ):
            _fail(f"published {purpose} identity changed")
        validator(_parse_canonical_object(final_data, f"published {purpose}"))
        return data
    finally:
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if identity is not None:
            with contextlib.suppress(OSError):
                metadata = stage.stat(follow_symlinks=False)
                if (metadata.st_dev, metadata.st_ino) == identity:
                    stage.unlink()


class _WindowsJob:
    """A private kill-on-close Windows Job Object for one suspended child tree."""

    def __init__(self) -> None:
        if os.name != "nt":
            _fail("Windows Job Objects are available only on Windows")
        from ctypes import wintypes

        class _BasicLimitInformation(ctypes.Structure):
            _fields_: ClassVar[list[tuple[str, Any]]] = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_: ClassVar[list[tuple[str, Any]]] = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_: ClassVar[list[tuple[str, Any]]] = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class _BasicAccountingInformation(ctypes.Structure):
            _fields_: ClassVar[list[tuple[str, Any]]] = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            _fail(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
        information = _ExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            _fail(f"SetInformationJobObject failed: {error}")
        self._kernel32 = kernel32
        self._ntdll = ntdll
        self._accounting_type = _BasicAccountingInformation
        self._handle = handle
        self._closed = False

    def assign(self, process: subprocess.Popen[bytes]) -> None:
        process_handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            _fail(f"AssignProcessToJobObject failed: {ctypes.get_last_error()}")

    def resume(self, process: subprocess.Popen[bytes]) -> None:
        process_handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
        status = self._ntdll.NtResumeProcess(process_handle)
        if status != 0:
            _fail(f"NtResumeProcess failed: {status}")

    def assign_and_resume(self, process: subprocess.Popen[bytes]) -> None:
        self.assign(process)
        self.resume(process)

    def active_processes(self) -> int:
        from ctypes import wintypes

        information = self._accounting_type()
        returned = wintypes.DWORD()
        if not self._kernel32.QueryInformationJobObject(
            self._handle,
            _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
            ctypes.byref(returned),
        ):
            _fail(f"QueryInformationJobObject failed: {ctypes.get_last_error()}")
        return int(information.ActiveProcesses)

    def terminate(self) -> bool:
        return bool(self._kernel32.TerminateJobObject(self._handle, 1))

    def close(self) -> bool:
        if not self._closed:
            passed = bool(self._kernel32.CloseHandle(self._handle))
            self._closed = True
            return passed
        return True


@dataclass(slots=True)
class _Capture:
    cap: int
    data: bytearray
    overflow: threading.Event
    failed: threading.Event


def _capture_stream(stream: Any, capture: _Capture) -> None:
    try:
        while True:
            chunk = stream.read(4_096)
            if not chunk:
                return
            remaining = capture.cap - len(capture.data)
            if len(chunk) > remaining:
                if remaining > 0:
                    capture.data.extend(chunk[:remaining])
                capture.overflow.set()
                return
            capture.data.extend(chunk)
    except (OSError, ValueError):
        capture.failed.set()


def _spawn_suspended(
    argv: Sequence[str],
    *,
    cwd: str,
    environment: Mapping[str, str],
) -> _SpawnedState:
    job = _WindowsJob()
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_CREATE_SUSPENDED | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            bufsize=0,
        )
    except Exception:
        job.close()
        raise
    assigned = False
    try:
        job.assign(process)
        assigned = True
        job.resume(process)
    except Exception:
        return _SpawnedState(process, job, True, assigned)
    return _SpawnedState(process, job, False, True)


def _run_taskkill(pid: int, deadline_ns: int) -> bool:
    remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        return False
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [_TASKKILL_PATH, "/PID", str(pid), "/T", "/F"],
            cwd=_NEUTRAL_GIT_CWD,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        process.wait(timeout=remaining)
        return True
    except (OSError, subprocess.TimeoutExpired):
        if process is not None and process.poll() is None:
            with contextlib.suppress(OSError):
                process.kill()
            remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
            if remaining > 0:
                with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                    process.wait(timeout=remaining)
        return process is not None and process.poll() is not None


def _cleanup_tree(
    process: subprocess.Popen[bytes],
    job: _WindowsJob,
    *,
    deadline_ns: int,
) -> bool:
    taskkill_passes = True
    if process.poll() is None:
        taskkill_passes = _run_taskkill(process.pid, deadline_ns)
    try:
        active = job.active_processes()
    except _ProtocolFailure:
        active = 1
    if process.poll() is None or active != 0:
        job.terminate()
    remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
    if remaining > 0:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            process.wait(timeout=remaining)
    while time.monotonic_ns() < deadline_ns:
        try:
            if process.poll() is not None and job.active_processes() == 0:
                return taskkill_passes
        except _ProtocolFailure:
            return False
        time.sleep(0.01)
    try:
        return (
            taskkill_passes
            and process.poll() is not None
            and job.active_processes() == 0
        )
    except _ProtocolFailure:
        return False


def _cleanup_initialization_failure(
    state: _SpawnedState,
    *,
    deadline_ns: int,
) -> bool:
    process = state.process
    passed = False
    if state.job_assigned:
        passed = _cleanup_tree(process, state.job, deadline_ns=deadline_ns)
    else:
        with contextlib.suppress(OSError):
            process.kill()
        remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
        if remaining > 0:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=remaining)
        passed = process.poll() is not None
    streams_closed = True
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                streams_closed = False
    close_result = state.job.close()
    return (
        passed
        and streams_closed
        and close_result is not False
        and process.poll() is not None
    )


def _run_bounded_process(
    argv: Sequence[str],
    *,
    cwd: str,
    environment: Mapping[str, str],
    live_deadline_ns: int,
    cleanup_deadline_ns: int,
    stdout_cap: int,
    stderr_cap: int,
    deadline_reason: str,
) -> _ManagedResult:
    started_ns = time.monotonic_ns()
    if started_ns >= live_deadline_ns:
        return _ManagedResult(
            False, None, b"", b"", 0, "spawn_error", False, None
        )
    try:
        spawned_state = _spawn_suspended(argv, cwd=cwd, environment=environment)
    except Exception:
        duration = max(0, (time.monotonic_ns() - started_ns) // 1_000_000)
        return _ManagedResult(
            False, None, b"", b"", duration, "spawn_error", False, None
        )

    if isinstance(spawned_state, tuple):
        process, job = spawned_state
        state = _SpawnedState(process, job, False, True)
    else:
        state = spawned_state
        process = state.process
        job = state.job

    if state.initialization_failed:
        bounded_cleanup_deadline_ns = min(
            cleanup_deadline_ns,
            time.monotonic_ns()
            + _CHILD_CLEANUP_TIMEOUT_SECONDS * 1_000_000_000,
        )
        cleanup_passes = _cleanup_initialization_failure(
            state,
            deadline_ns=bounded_cleanup_deadline_ns,
        )
        exit_code = process.poll()
        if exit_code is None:
            cleanup_passes = False
        duration = max(0, (time.monotonic_ns() - started_ns) // 1_000_000)
        return _ManagedResult(
            True,
            None if exit_code is None else int(exit_code),
            b"",
            b"",
            duration,
            (
                "post_spawn_initialization_failed"
                if cleanup_passes
                else "child_cleanup_failed"
            ),
            False,
            bool(cleanup_passes),
        )

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_capture = _Capture(stdout_cap, bytearray(), threading.Event(), threading.Event())
    stderr_capture = _Capture(stderr_cap, bytearray(), threading.Event(), threading.Event())
    stdout_thread = threading.Thread(
        target=_capture_stream,
        args=(process.stdout, stdout_capture),
        name="arc3-v8-supervisor-stdout-capture",
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_capture_stream,
        args=(process.stderr, stderr_capture),
        name="arc3-v8-supervisor-stderr-capture",
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timeout_initiated = False
    while process.poll() is None:
        if time.monotonic_ns() >= live_deadline_ns:
            timeout_initiated = True
        if (
            stdout_capture.overflow.is_set()
            or stderr_capture.overflow.is_set()
            or stdout_capture.failed.is_set()
            or stderr_capture.failed.is_set()
            or timeout_initiated
        ):
            break
        time.sleep(0.01)

    cleanup_passes: bool | None = None
    cleanup_start_ns = time.monotonic_ns()
    operation_deadline_ns = min(
        cleanup_deadline_ns,
        cleanup_start_ns + _CHILD_CLEANUP_TIMEOUT_SECONDS * 1_000_000_000,
    )
    controller_triggered = (
        timeout_initiated
        or stdout_capture.overflow.is_set()
        or stderr_capture.overflow.is_set()
        or stdout_capture.failed.is_set()
        or stderr_capture.failed.is_set()
    )
    if controller_triggered:
        cleanup_passes = _cleanup_tree(
            process,
            job,
            deadline_ns=operation_deadline_ns,
        )
    else:
        try:
            active = job.active_processes()
        except _ProtocolFailure:
            active = 1
        if active != 0:
            cleanup_passes = _cleanup_tree(
                process,
                job,
                deadline_ns=operation_deadline_ns,
            )

    for thread in (stdout_thread, stderr_thread):
        remaining = max(
            0.0,
            (operation_deadline_ns - time.monotonic_ns()) / 1_000_000_000,
        )
        thread.join(timeout=remaining)
    stream_close_failed = False
    try:
        process.stdout.close()
    except OSError:
        stream_close_failed = True
    try:
        process.stderr.close()
    except OSError:
        stream_close_failed = True
    for thread in (stdout_thread, stderr_thread):
        remaining = max(
            0.0,
            (operation_deadline_ns - time.monotonic_ns()) / 1_000_000_000,
        )
        thread.join(timeout=remaining)
    capture_failed = (
        stream_close_failed
        or stdout_thread.is_alive()
        or stderr_thread.is_alive()
        or stdout_capture.failed.is_set()
        or stderr_capture.failed.is_set()
    )
    requires_cleanup_evidence = (
        controller_triggered
        or capture_failed
        or stdout_capture.overflow.is_set()
        or stderr_capture.overflow.is_set()
        or cleanup_passes is not None
    )
    if requires_cleanup_evidence and cleanup_passes is None:
        try:
            cleanup_passes = process.poll() is not None and job.active_processes() == 0
        except _ProtocolFailure:
            cleanup_passes = False
    if capture_failed and (stdout_thread.is_alive() or stderr_thread.is_alive()):
        cleanup_passes = False
    close_result = job.close()
    if close_result is False:
        cleanup_passes = False
    exit_code = process.poll()
    if requires_cleanup_evidence and exit_code is None:
        cleanup_passes = False

    if cleanup_passes is False:
        reason: str | None = "child_cleanup_failed"
    elif capture_failed:
        reason = "stream_capture_failed"
        cleanup_passes = True
    elif stdout_capture.overflow.is_set():
        reason = "stdout_limit"
        cleanup_passes = True
    elif stderr_capture.overflow.is_set():
        reason = "stderr_limit"
        cleanup_passes = True
    elif timeout_initiated:
        reason = deadline_reason
        cleanup_passes = True
    else:
        reason = None

    if timeout_initiated and cleanup_passes is True:
        exit_code = _SYNTHETIC_TIMEOUT_EXIT
    duration = max(0, (time.monotonic_ns() - started_ns) // 1_000_000)
    return _ManagedResult(
        True,
        None if exit_code is None else int(exit_code),
        bytes(stdout_capture.data),
        bytes(stderr_capture.data),
        duration,
        reason,
        timeout_initiated,
        cleanup_passes,
    )


def _stream_fields(prefix: str, data: bytes) -> dict[str, Any]:
    return {
        f"{prefix}_size_bytes": len(data),
        f"{prefix}_sha256": hashlib.sha256(data).hexdigest(),
        f"{prefix}_base64": base64.b64encode(data).decode("ascii"),
    }


def _run_git_command(arguments: Sequence[str], *, overall_deadline_ns: int) -> bytes:
    now = time.monotonic_ns()
    full_bound = (
        _WINDOWS_GIT_CHILD_TIMEOUT_SECONDS + _CHILD_CLEANUP_TIMEOUT_SECONDS
    ) * 1_000_000_000
    if now + full_bound > overall_deadline_ns:
        _fail("insufficient supervisor budget for local Git identity validation")
    result = _run_bounded_process(
        [_GIT_PATH, "--no-replace-objects", "--no-optional-locks", *arguments],
        cwd=_NEUTRAL_GIT_CWD,
        environment=_git_environment(),
        live_deadline_ns=now + _WINDOWS_GIT_CHILD_TIMEOUT_SECONDS * 1_000_000_000,
        cleanup_deadline_ns=now + full_bound,
        stdout_cap=_LOCAL_GIT_STDOUT_CAP_BYTES,
        stderr_cap=_STDERR_CAP_BYTES,
        deadline_reason="timeout",
    )
    if result.reason is not None or result.exit_code != 0:
        _fail("local Git identity command failed")
    return result.stdout


def _parse_commit_line(data: bytes, name: str) -> str:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _ProtocolFailure(f"{name} output is not ASCII") from exc
    if not text.endswith("\n") or text.count("\n") != 1:
        _fail(f"{name} output is malformed")
    return _require_lower_hex(text[:-1], 40, name)


def _parse_name_status(data: bytes) -> set[str]:
    fields = data.split(b"\0")
    if not fields or fields[-1] != b"":
        _fail("Git name-status output is malformed")
    fields.pop()
    if len(fields) % 2:
        _fail("Git name-status output has an incomplete record")
    paths: set[str] = set()
    for index in range(0, len(fields), 2):
        if fields[index] != b"A":
            _fail("O8 contains a non-addition delta")
        try:
            path = fields[index + 1].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ProtocolFailure("O8 delta path is not UTF-8") from exc
        if path in paths:
            _fail("O8 delta contains a duplicate path")
        paths.add(path)
    return paths


def _require_direct_child(
    child: str,
    parent: str,
    *,
    overall_deadline_ns: int,
) -> None:
    """Require the O8 commit to have exactly the registered P8 parent."""

    observed = _run_git_command(
        [
            "-C",
            _REPOSITORY_ROOT,
            "rev-list",
            "--parents",
            "-n",
            "1",
            child,
        ],
        overall_deadline_ns=overall_deadline_ns,
    )
    if observed != f"{child} {parent}\n".encode("ascii"):
        _fail("O8 is not a direct child of registered P8")


def _tree_blob_oid(path: str, commit: str, *, overall_deadline_ns: int) -> str:
    data = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "ls-tree", "-z", commit, "--", path],
        overall_deadline_ns=overall_deadline_ns,
    )
    records = [record for record in data.split(b"\0") if record]
    if len(records) != 1:
        _fail(f"Git tree does not contain exactly one {path}")
    metadata, separator, raw_path = records[0].partition(b"\t")
    fields = metadata.split()
    if (
        not separator
        or raw_path.decode("utf-8", errors="strict") != path
        or len(fields) != 3
        or fields[0] != b"100644"
        or fields[1] != b"blob"
    ):
        _fail(f"Git tree entry is invalid for {path}")
    return _require_lower_hex(fields[2].decode("ascii"), 40, f"Git blob for {path}")


def _validate_repository_identity(
    root: Path,
    registration: _Registration,
    *,
    overall_deadline_ns: int,
    repository_snapshot: _RepositorySnapshot | None = None,
) -> str:
    commit = _parse_commit_line(
        _run_git_command(
            ["-C", _REPOSITORY_ROOT, "rev-parse", "HEAD"],
            overall_deadline_ns=overall_deadline_ns,
        ),
        "local HEAD",
    )
    contract = registration.execution["windows_repository_contract"]
    if not isinstance(contract, dict):
        _fail("registration Windows repository contract is invalid")
    _validate_repository_git_contract(
        commit,
        contract,
        overall_deadline_ns=overall_deadline_ns,
    )
    tag_type = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "cat-file", "-t", _OPEN_FREEZE_TAG],
        overall_deadline_ns=overall_deadline_ns,
    )
    tag_commit = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "rev-parse", _OPEN_FREEZE_TAG],
        overall_deadline_ns=overall_deadline_ns,
    )
    peeled_commit = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "rev-parse", f"{_OPEN_FREEZE_TAG}^{{commit}}"],
        overall_deadline_ns=overall_deadline_ns,
    )
    if (
        tag_type != b"commit\n"
        or tag_commit != f"{commit}\n".encode("ascii")
        or peeled_commit != tag_commit
    ):
        _fail("local open-freeze tag is not the HEAD lightweight tag")

    preregistration = registration.value["preregistration"]
    if not isinstance(preregistration, dict):
        _fail("registration preregistration identity is invalid")
    parent = _require_lower_hex(preregistration.get("commit_sha"), 40, "P8 commit")
    _require_direct_child(commit, parent, overall_deadline_ns=overall_deadline_ns)
    delta = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "diff", "--name-status", "-z", parent, commit],
        overall_deadline_ns=overall_deadline_ns,
    )
    if _parse_name_status(delta) != _O8_ADDITIONS:
        _fail("O8 path delta differs from the preregistered allowlist")
    status = _run_git_command(
        ["-C", _REPOSITORY_ROOT, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        overall_deadline_ns=overall_deadline_ns,
    )
    if status:
        _fail("the original Windows O8 checkout is not Git-clean")

    manifest_by_path = {
        _SUPERVISOR_SCRIPT: registration.supervisor_manifest,
        _VERIFIER_SCRIPT: registration.verifier_manifest,
    }
    for path in (_SUPERVISOR_SCRIPT, _VERIFIER_SCRIPT, _REGISTRATION_PATH):
        raw = _read_plain_file(root / Path(path), path)
        tree_oid = _tree_blob_oid(path, commit, overall_deadline_ns=overall_deadline_ns)
        if _git_blob_sha1(raw) != tree_oid:
            _fail(f"raw Windows bytes differ from the O8 blob: {path}")
        entry = manifest_by_path.get(path)
        if entry is not None and (
            tree_oid != entry["git_blob_sha1"]
            or hashlib.sha256(raw).hexdigest() != entry["sha256"]
            or len(raw) != entry["byte_count"]
        ):
            _fail(f"O8 script identity differs from registration: {path}")
    if repository_snapshot is None:
        _fail("pre-Git Windows repository snapshot is missing")
    _require_repository_snapshot_unchanged(repository_snapshot, contract)
    return commit


def _decode_stream(record: Mapping[str, Any], prefix: str, cap: int) -> bytes:
    size = _require_int(record[f"{prefix}_size_bytes"], f"{prefix} size")
    if size > cap:
        _fail(f"{prefix} exceeds its registered cap")
    digest = _require_lower_hex(record[f"{prefix}_sha256"], 64, f"{prefix} SHA-256")
    encoded = record[f"{prefix}_base64"]
    if not isinstance(encoded, str) or any(ord(character) > 127 for character in encoded):
        _fail(f"{prefix} Base64 is invalid")
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _ProtocolFailure(f"{prefix} Base64 is invalid") from exc
    if base64.b64encode(data).decode("ascii") != encoded:
        _fail(f"{prefix} Base64 is not canonical")
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        _fail(f"{prefix} metadata does not match its bytes")
    return data


def _validate_tool_object(value: Any, expected: Mapping[str, str], name: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{name} tool identity is not an object")
    _require_keys(value, {"path", "version", "sha256"}, f"{name} tool identity")
    if value != expected:
        _fail(f"{name} tool identity is invalid")


def _validate_attempt(
    value: Any,
    index: int,
    expected_stdout: bytes,
) -> tuple[str, int]:
    if not isinstance(value, dict):
        _fail(f"attempt {index} is not an object")
    _require_keys(value, _ATTEMPT_KEYS, f"attempt {index}")
    if value["attempt_index"] != index:
        _fail("attempt indices are not contiguous and one-based")
    classification = value["classification"]
    if classification not in _ATTEMPT_CLASSIFICATIONS:
        _fail(f"attempt {index} classification is invalid")
    exit_code = value["exit_code"]
    if classification == "spawn_error":
        if exit_code is not None:
            _fail("spawn-error exit code must be null")
    elif classification == "child_cleanup_failed" and exit_code is None:
        pass
    else:
        _require_exit_code(exit_code, f"attempt {index} exit code")
    if not isinstance(value["timed_out"], bool):
        _fail("attempt timed_out is not Boolean")
    duration = _require_int(value["duration_milliseconds"], "attempt duration")
    stdout = _decode_stream(value, "stdout", _STDOUT_CAP_BYTES)
    stderr = _decode_stream(value, "stderr", _STDERR_CAP_BYTES)
    cleanup = value["child_cleanup_passes"]
    if classification == "spawn_error":
        if cleanup is not None:
            _fail("spawn-error cleanup must be null")
    elif classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("cleanup-failure classification must record false cleanup")
    elif classification in {
        "retryable_timeout_124",
        "overall_deadline",
        "stdout_limit",
        "stderr_limit",
        "post_spawn_initialization_failed",
        "stream_capture_failed",
    }:
        if cleanup is not True:
            _fail("managed failure lacks a passing cleanup predicate")
    elif cleanup is not None and cleanup is not True:
        _fail("normal attempt cleanup must be null or true")

    timed_out = value["timed_out"]
    if classification == "verified":
        if exit_code != 0 or stdout != expected_stdout or timed_out:
            _fail("verified attempt evidence is invalid")
    elif classification == "retryable_empty_exit_0":
        if exit_code != 0 or stdout or timed_out:
            _fail("empty-exit-zero attempt evidence is invalid")
    elif classification == "retryable_timeout_124":
        if (
            exit_code != _SYNTHETIC_TIMEOUT_EXIT
            or not timed_out
            or duration < _ATTEMPT_TIMEOUT_SECONDS * 1_000
        ):
            _fail("timeout attempt evidence is invalid")
    elif classification == "retryable_git_128":
        if exit_code != 128 or stdout or timed_out:
            _fail("Git-128 attempt evidence is invalid")
    elif classification == "unexpected_output":
        if not stdout or (exit_code == 0 and stdout == expected_stdout) or timed_out:
            _fail("unexpected-output attempt evidence is invalid")
    elif classification == "unexpected_exit":
        if exit_code in {0, 128} or stdout or timed_out:
            _fail("unexpected-exit attempt evidence is invalid")
    elif classification == "stdout_limit":
        if len(stdout) != _STDOUT_CAP_BYTES:
            _fail("stdout-limit attempt evidence is invalid")
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("stdout-limit timeout/exit evidence is invalid")
    elif classification == "stderr_limit":
        if len(stderr) != _STDERR_CAP_BYTES:
            _fail("stderr-limit attempt evidence is invalid")
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("stderr-limit timeout/exit evidence is invalid")
    elif classification == "spawn_error":
        if stdout or stderr or timed_out:
            _fail("spawn-error attempt evidence is invalid")
    elif classification == "post_spawn_initialization_failed":
        if stdout or stderr or timed_out:
            _fail("post-spawn initialization evidence is invalid")
    elif classification == "stream_capture_failed":
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("stream-capture timeout/exit evidence is invalid")
    elif classification == "child_cleanup_failed":
        pass
    elif classification == "overall_deadline" and (
        exit_code != _SYNTHETIC_TIMEOUT_EXIT
        or not timed_out
        or duration < _ATTEMPT_TIMEOUT_SECONDS * 1_000
    ):
        _fail("overall-deadline attempt evidence is invalid")
    return str(classification), duration


def _validate_remote_receipt(
    value: Mapping[str, Any],
    *,
    registration: _Registration,
    lifecycle_claim: Mapping[str, Any],
    lifecycle_claim_sha256: str,
    start_claim_sha256: str,
    python: Mapping[str, str],
    git: Mapping[str, str],
    taskkill: Mapping[str, str],
) -> str:
    _require_keys(value, _REMOTE_RECEIPT_KEYS, "remote receipt")
    expected_stdout = (
        f"{lifecycle_claim['open_freeze_commit_sha']}\t{_REMOTE_REF}\n".encode("ascii")
    )
    if (
        value["schema_version"] != _REMOTE_RECEIPT_SCHEMA
        or value["treatment_id"] != _TREATMENT_ID
        or value["claim_sha256"] != lifecycle_claim_sha256
        or value["verifier_start_claim_sha256"] != start_claim_sha256
        or value["open_freeze_commit_sha"] != lifecycle_claim["open_freeze_commit_sha"]
        or value["open_freeze_tag"] != _OPEN_FREEZE_TAG
        or value["registration_content_sha256"]
        != registration.value["content_sha256"]
        or value["remote_url"] != _REMOTE_URL
        or value["ref"] != _REMOTE_REF
        or value["policy"] != _remote_policy()
    ):
        _fail("remote receipt fixed identity is invalid")
    _validate_tool_object(value["python"], python, "Python")
    _validate_tool_object(value["git"], git, "Git")
    _validate_tool_object(value["taskkill"], taskkill, "taskkill")

    attempts = value["attempts"]
    if not isinstance(attempts, list) or len(attempts) > _MAX_ATTEMPTS:
        _fail("remote receipt attempt inventory is invalid")
    classifications: list[str] = []
    durations: list[int] = []
    for index, attempt in enumerate(attempts, start=1):
        classification, duration = _validate_attempt(attempt, index, expected_stdout)
        classifications.append(classification)
        durations.append(duration)
        if index < len(attempts) and classification not in _RETRYABLE_CLASSIFICATIONS:
            _fail("an attempt follows a terminal classification")

    status = value["status"]
    selected = value["selected_attempt"]
    if status == "verified":
        if not attempts or classifications[-1] != "verified" or selected != len(attempts):
            _fail("verified receipt selection is invalid")
    elif status == "failed":
        if selected is not None or "verified" in classifications:
            _fail("failed receipt selection is invalid")
    else:
        _fail("remote receipt status is invalid")
    total = _require_int(value["total_duration_milliseconds"], "total duration")
    retry_gaps = max(0, len(attempts) - 1) * (_RETRY_DELAY_SECONDS * 1_000)
    if total < sum(durations) + retry_gaps:
        _fail("remote receipt total duration is shorter than its attempt ledger")
    return str(status)


def _read_optional_raw(path: Path, name: str) -> tuple[bytes | None, str | None]:
    try:
        before_path = path.lstat()
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        raise _ProtocolFailure(f"existing {name} is unavailable") from exc
    try:
        data = _read_plain_file(path, name)
        after_path = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"existing {name} bytes cannot be read") from exc
    if (
        _file_identity(before_path) != _file_identity(after_path)
        or _file_change_identity(before_path) != _file_change_identity(after_path)
    ):
        _fail(f"existing {name} changed while being read")
    return data, hashlib.sha256(data).hexdigest()


def _validate_supervisor_receipt(
    value: Mapping[str, Any],
    *,
    registration: _Registration,
    lifecycle_claim: Mapping[str, Any],
    lifecycle_claim_sha256: str,
    start_claim_sha256: str | None,
    remote_receipt_sha256: str | None,
    remote_status: str | None,
) -> None:
    _require_keys(value, _SUPERVISOR_RECEIPT_KEYS, "supervisor receipt")
    if (
        value["schema_version"] != _SUPERVISOR_RECEIPT_SCHEMA
        or value["treatment_id"] != _TREATMENT_ID
        or value["claim_sha256"] != lifecycle_claim_sha256
        or value["verifier_start_claim_sha256"] != start_claim_sha256
        or value["open_freeze_commit_sha"] != lifecycle_claim["open_freeze_commit_sha"]
        or value["registration_content_sha256"]
        != registration.value["content_sha256"]
        or value["verifier_argv_sha256"]
        != registration.execution["argv_hashes"]["remote_verifier"]
        or value["remote_receipt_sha256"] != remote_receipt_sha256
    ):
        _fail("supervisor receipt fixed identity is invalid")
    _require_lower_hex(value["claim_sha256"], 64, "lifecycle claim SHA-256")
    for field in ("verifier_start_claim_sha256", "remote_receipt_sha256"):
        if value[field] is not None:
            _require_lower_hex(value[field], 64, field)

    classification = value["classification"]
    if classification not in _SUPERVISOR_CLASSIFICATIONS:
        _fail("supervisor classification is invalid")
    exit_code = value["verifier_exit_code"]
    if classification == "spawn_error":
        if exit_code is not None:
            _fail("spawn-error verifier exit code must be null")
    elif classification == "child_cleanup_failed" and exit_code is None:
        pass
    else:
        _require_exit_code(exit_code, "verifier exit code")
    timed_out = value["timed_out"]
    if not isinstance(timed_out, bool):
        _fail("supervisor timed_out is not Boolean")
    _require_int(value["duration_milliseconds"], "supervisor duration")
    stdout = _decode_stream(value, "stdout", _STDOUT_CAP_BYTES)
    stderr = _decode_stream(value, "stderr", _STDERR_CAP_BYTES)
    cleanup = value["child_cleanup_passes"]
    if classification == "spawn_error":
        if cleanup is not None:
            _fail("supervisor spawn-error cleanup must be null")
    elif classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("supervisor cleanup-failure must record false cleanup")
    elif classification in {
        "verifier_timeout_124",
        "stdout_limit",
        "stderr_limit",
        "post_spawn_initialization_failed",
        "stream_capture_failed",
    }:
        if cleanup is not True:
            _fail("supervisor managed failure lacks passing cleanup")
    elif cleanup is not None and cleanup is not True:
        _fail("normal supervisor cleanup must be null or true")

    status = value["status"]
    if status not in {"completed", "failed"}:
        _fail("supervisor status is invalid")
    if (classification == "verifier_completed") != (status == "completed"):
        _fail("supervisor status and classification disagree")
    if classification == "verifier_completed":
        expected_exit = 0 if remote_status == "verified" else 1
        if (
            remote_status not in {"verified", "failed"}
            or exit_code != expected_exit
            or timed_out
            or stdout
            or stderr
            or start_claim_sha256 is None
            or remote_receipt_sha256 is None
        ):
            _fail("completed verifier evidence is invalid")
    elif classification == "verifier_timeout_124":
        if exit_code != _SYNTHETIC_TIMEOUT_EXIT or not timed_out:
            _fail("verifier-timeout evidence is invalid")
    elif classification == "stdout_limit":
        if len(stdout) != _STDOUT_CAP_BYTES:
            _fail("supervisor stdout-limit evidence is invalid")
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("supervisor stdout-limit timeout/exit evidence is invalid")
    elif classification == "stderr_limit":
        if len(stderr) != _STDERR_CAP_BYTES:
            _fail("supervisor stderr-limit evidence is invalid")
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("supervisor stderr-limit timeout/exit evidence is invalid")
    elif classification == "spawn_error":
        if stdout or stderr or timed_out:
            _fail("supervisor spawn-error evidence is invalid")
    elif classification == "post_spawn_initialization_failed":
        if stdout or stderr or timed_out:
            _fail("supervisor post-spawn initialization evidence is invalid")
    elif classification == "stream_capture_failed":
        if timed_out and exit_code != _SYNTHETIC_TIMEOUT_EXIT:
            _fail("supervisor stream-capture timeout/exit evidence is invalid")
    elif classification == "child_cleanup_failed":
        pass
    elif classification == "remote_receipt_missing":
        if remote_receipt_sha256 is not None or timed_out:
            _fail("missing-receipt evidence is invalid")
    elif classification == "remote_receipt_invalid":
        if remote_receipt_sha256 is None or timed_out:
            _fail("invalid-receipt evidence is invalid")


def _supervisor_receipt_object(
    *,
    registration: _Registration,
    lifecycle_claim: Mapping[str, Any],
    lifecycle_claim_sha256: str,
    start_claim_sha256: str | None,
    remote_receipt_sha256: str | None,
    result: _ManagedResult,
    classification: str,
    status: str,
) -> dict[str, Any]:
    cleanup = result.cleanup_passes
    return {
        "schema_version": _SUPERVISOR_RECEIPT_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "claim_sha256": lifecycle_claim_sha256,
        "verifier_start_claim_sha256": start_claim_sha256,
        "open_freeze_commit_sha": lifecycle_claim["open_freeze_commit_sha"],
        "registration_content_sha256": registration.value["content_sha256"],
        "verifier_argv_sha256": registration.execution["argv_hashes"]["remote_verifier"],
        "verifier_exit_code": result.exit_code,
        "classification": classification,
        "timed_out": result.timed_out,
        "duration_milliseconds": result.duration_milliseconds,
        **_stream_fields("stdout", result.stdout),
        **_stream_fields("stderr", result.stderr),
        "child_cleanup_passes": cleanup,
        "remote_receipt_sha256": remote_receipt_sha256,
        "status": status,
    }


def _require_plain_artifact(path: Path, name: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ProtocolFailure(f"{name} is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        _fail(f"{name} is not a plain file")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--verifier-start-claim", required=True)
    parser.add_argument("--remote-receipt", required=True)
    parser.add_argument("--supervisor-receipt", required=True)
    parser.add_argument("--verifier-python", required=True)
    parser.add_argument("--git-executable", required=True)
    parser.add_argument("--taskkill-executable", required=True)
    parser.add_argument("--verifier-child-deadline-seconds", required=True, type=int)
    parser.add_argument("--supervisor-deadline-seconds", required=True, type=int)
    parser.add_argument("--child-cleanup-timeout-seconds", required=True, type=int)
    return parser


def _validate_invocation(args: argparse.Namespace, observed_argv: Sequence[str]) -> Path:
    if os.name != "nt":
        _fail("remote verification supervision requires Windows")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("remote verification supervision requires Python -I -B")
    if [sys.executable, "-I", "-B", *observed_argv] != _expected_supervisor_argv():
        _fail("supervisor argv differs from the registered command")
    if (
        args.repository_root != "."
        or args.registration != _REGISTRATION_ARGV_PATH
        or args.claim != _CLAIM_PATH
        or args.verifier_start_claim != _START_CLAIM_PATH
        or args.remote_receipt != _REMOTE_RECEIPT_PATH
        or args.supervisor_receipt != _SUPERVISOR_RECEIPT_PATH
        or args.verifier_python != _PYTHON_PATH
        or args.git_executable != _GIT_PATH
        or args.taskkill_executable != _TASKKILL_PATH
        or args.verifier_child_deadline_seconds != _VERIFIER_CHILD_DEADLINE_SECONDS
        or args.supervisor_deadline_seconds != _SUPERVISOR_DEADLINE_SECONDS
        or args.child_cleanup_timeout_seconds != _CHILD_CLEANUP_TIMEOUT_SECONDS
    ):
        _fail("supervisor arguments differ from registration")
    root = Path(os.path.abspath(os.getcwd()))
    if os.path.normcase(str(root)) != os.path.normcase(_REPOSITORY_ROOT):
        _fail("supervisor cwd differs from the registered repository")
    expected_script = root / Path(_SUPERVISOR_SCRIPT)
    if os.path.normcase(os.path.abspath(sys.argv[0])) != os.path.normcase(
        str(expected_script)
    ):
        _fail("supervisor script origin differs from registration")
    neutral = Path(_NEUTRAL_GIT_CWD)
    neutral_meta = neutral.lstat()
    if not stat.S_ISDIR(neutral_meta.st_mode) or stat.S_ISLNK(neutral_meta.st_mode):
        _fail("neutral Git cwd is not a plain directory")
    if (neutral / ".git").exists() or (neutral / ".git").is_symlink():
        _fail("neutral Git cwd contains .git")
    fake_home = Path(_NONEXISTENT_HOME)
    if fake_home.exists() or fake_home.is_symlink():
        _fail("registered nonexistent Git home exists")
    return root


def _require_artifacts_absent() -> None:
    for path_text, name in (
        (_CLAIM_PATH, "lifecycle claim"),
        (_START_CLAIM_PATH, "verifier-start claim"),
        (_REMOTE_RECEIPT_PATH, "remote receipt"),
        (_SUPERVISOR_RECEIPT_PATH, "supervisor receipt"),
    ):
        path = Path(path_text)
        if path.exists() or path.is_symlink():
            _fail(f"{name} already exists")


def main(argv: Sequence[str] | None = None) -> int:
    started_ns = time.monotonic_ns()
    args = _parser().parse_args(argv)
    observed_argv = list(sys.argv) if argv is None else [_SUPERVISOR_ARGV_SCRIPT, *argv]
    root = _validate_invocation(args, observed_argv)
    repository_snapshot = _capture_repository_snapshot(
        _windows_repository_contract()
    )
    registration = _load_registration(root)
    python, git, taskkill = _validate_tools()
    _require_artifacts_absent()

    child_live_deadline_ns = (
        started_ns + _VERIFIER_CHILD_DEADLINE_SECONDS * 1_000_000_000
    )
    cleanup_deadline_ns = started_ns + (
        _SUPERVISOR_DEADLINE_SECONDS - _SUPERVISOR_RECEIPT_RESERVE_SECONDS
    ) * 1_000_000_000
    receipt_deadline_ns = (
        started_ns + _SUPERVISOR_DEADLINE_SECONDS * 1_000_000_000
    )
    commit = _validate_repository_identity(
        root,
        registration,
        overall_deadline_ns=child_live_deadline_ns,
        repository_snapshot=repository_snapshot,
    )
    if time.monotonic_ns() >= child_live_deadline_ns:
        _fail("supervisor pre-claim validation exhausted the verifier deadline")

    lifecycle_claim = _claim_object(registration, commit)
    claim_data = _publish_canonical(
        Path(_CLAIM_PATH),
        lifecycle_claim,
        lambda value: _validate_claim(value, lifecycle_claim),
        "lifecycle-claim",
    )
    lifecycle_claim_sha256 = hashlib.sha256(claim_data).hexdigest()

    result = _run_bounded_process(
        _expected_verifier_argv(),
        cwd=_REPOSITORY_ROOT,
        environment=_git_environment(),
        live_deadline_ns=child_live_deadline_ns,
        cleanup_deadline_ns=cleanup_deadline_ns,
        stdout_cap=_STDOUT_CAP_BYTES,
        stderr_cap=_STDERR_CAP_BYTES,
        deadline_reason="timeout",
    )

    if time.monotonic_ns() >= receipt_deadline_ns:
        _fail("supervisor receipt endpoint elapsed before evidence validation")

    start_path = Path(_START_CLAIM_PATH)
    remote_path = Path(_REMOTE_RECEIPT_PATH)
    start_data, start_claim_sha256 = _read_optional_raw(
        start_path,
        "verifier-start claim",
    )
    remote_data, remote_receipt_sha256 = _read_optional_raw(
        remote_path,
        "remote receipt",
    )
    classification = "child_cleanup_failed"
    status = "failed"
    remote_status: str | None = None
    if not result.spawned:
        classification = "spawn_error"
    elif result.reason == "timeout":
        classification = "verifier_timeout_124"
    elif result.reason in {
        "stdout_limit",
        "stderr_limit",
        "child_cleanup_failed",
        "post_spawn_initialization_failed",
        "stream_capture_failed",
    }:
        classification = result.reason
    elif remote_data is None:
        classification = "remote_receipt_missing"
    else:
        classification = "remote_receipt_invalid"
        try:
            if start_data is None or start_claim_sha256 is None:
                _fail("verifier-start claim is missing")
            _require_plain_artifact(start_path, "verifier-start claim")
            _require_plain_artifact(remote_path, "remote receipt")
            _validate_start_claim(
                start_data,
                registration=registration,
                claim=lifecycle_claim,
                claim_sha256=lifecycle_claim_sha256,
            )
            remote_value = _parse_canonical_object(remote_data, "remote receipt")
            remote_status = _validate_remote_receipt(
                remote_value,
                registration=registration,
                lifecycle_claim=lifecycle_claim,
                lifecycle_claim_sha256=lifecycle_claim_sha256,
                start_claim_sha256=start_claim_sha256,
                python=python,
                git=git,
                taskkill=taskkill,
            )
            expected_exit = 0 if remote_status == "verified" else 1
            if result.exit_code != expected_exit or result.stdout or result.stderr:
                _fail("verifier process evidence and remote receipt status disagree")
            classification = "verifier_completed"
            status = "completed"
        except _ProtocolFailure:
            remote_status = None

    receipt = _supervisor_receipt_object(
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256=lifecycle_claim_sha256,
        start_claim_sha256=start_claim_sha256,
        remote_receipt_sha256=remote_receipt_sha256,
        result=result,
        classification=classification,
        status=status,
    )
    _publish_canonical(
        Path(_SUPERVISOR_RECEIPT_PATH),
        receipt,
        lambda value: _validate_supervisor_receipt(
            value,
            registration=registration,
            lifecycle_claim=lifecycle_claim,
            lifecycle_claim_sha256=lifecycle_claim_sha256,
            start_claim_sha256=start_claim_sha256,
            remote_receipt_sha256=remote_receipt_sha256,
            remote_status=remote_status,
        ),
        "supervisor-receipt",
    )
    if time.monotonic_ns() >= receipt_deadline_ns:
        _fail("supervisor receipt publication exceeded its fixed endpoint")
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except _ProtocolFailure as error:
        print(
            json.dumps({"error": str(error), "status": "refused"}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(2) from error
