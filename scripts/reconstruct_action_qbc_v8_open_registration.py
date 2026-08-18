# ruff: noqa: E501
"""Independently reconstruct and verify the action-QBC v8 open registration.

The module is deliberately standard-library-only.  Registration identities are read from
Git tree or stage-zero index objects, never from unfiltered worktree bytes.  No scientific
module is imported or executed.
"""

from __future__ import annotations

import argparse
import base64
import csv
import email.policy
import hashlib
import io
import json
import os
import platform
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Final, cast

SCHEMA_VERSION: Final = "action-qbc-v8-open-registration-v1"
STATUS: Final = "registered_zero_result"
TREATMENT_ID: Final = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
DIAGNOSTIC_SYSTEM_ID: Final = "crosslevel-voi-open-diagnostic-v8"
COMPARISON_SEMANTICS_ID: Final = "action-qbc-v8-v7-mathematics-identity-replication-v1"
PREREGISTRATION_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
PREREGISTRATION_COMMIT: Final = "e0bff9ffc185196cafa938c8f7c9a7186366258b"
PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_"
    "action_qbc_v8_open_bounded_remote_verification_v4_correction.md"
)
PREREGISTRATION_DOCUMENT_BLOB: Final = "29c991b7e23209f2c38d5e9a11a15bca51753d8e"
PREREGISTRATION_DOCUMENT_SHA256: Final = (
    "31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1"
)
PREREGISTRATION_DOCUMENT_BYTE_COUNT: Final = 33_215

PREREGISTRATION_V3_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
PREREGISTRATION_V3_COMMIT: Final = "996ab2bb5a24143a110673977f63e7d111cf2060"
PREREGISTRATION_V3_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_"
    "action_qbc_v8_open_bounded_remote_verification_v3_correction.md"
)
PREREGISTRATION_V3_DOCUMENT_BLOB: Final = "9f014e243a6bfe4ea35636a5de0d9bde598d4130"
PREREGISTRATION_V3_DOCUMENT_SHA256: Final = (
    "b2dafb5d41ab27a63f516c102f295395f32e825a5f66a90bd5fa95dbd414dbe9"
)
PREREGISTRATION_V3_DOCUMENT_BYTE_COUNT: Final = 58_656

PREREGISTRATION_V2_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
PREREGISTRATION_V2_COMMIT: Final = "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
PREREGISTRATION_V2_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification.md"
)
PREREGISTRATION_V2_DOCUMENT_BLOB: Final = "b3a639da07a92672adfd4976861a58608702a7f3"
PREREGISTRATION_V2_DOCUMENT_SHA256: Final = (
    "f5c3c7be6221cdefc789d73f140a24b289a4edc849d48c1fb9249bc258308344"
)
PREREGISTRATION_V2_DOCUMENT_BYTE_COUNT: Final = 92_798

PREREGISTRATION_V1_TAG: Final = "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
PREREGISTRATION_V1_COMMIT: Final = "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
PREREGISTRATION_V1_DOCUMENT_BLOB: Final = "9d5f00ea4fdb4ca6ff3cdb8c51ba0105efb1e046"
PREREGISTRATION_V1_DOCUMENT_SHA256: Final = "2e0ad4415d7f230f12f48db01aae9210797aa1da7f3a4ace6723e81be7bbb254"
PREREGISTRATION_V1_DOCUMENT: Final = PREREGISTRATION_V2_DOCUMENT

R7_COMMIT: Final = "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
R7_TAG: Final = "action-qbc-v7-open-diagnostic-result-v1"
O7_COMMIT: Final = "851fb6dadc851d17ba9540165f48570ee4203ded"
O7_TAG: Final = "action-qbc-v7-open-diagnostic-freeze-v1"
V7_PREREGISTRATION_COMMIT: Final = "f4a267757a7abbd72bc1aeb86e98811c521bf574"
V7_REGISTRATION_PATH: Final = "artifacts/action_qbc_v7_open_registration.json"
V7_REGISTRATION_CONTENT_SHA256: Final = "b09f9ee3b778222afd474645e64512ddc5abc3b6b326a2af9619ee016452a825"
V7_REGISTRATION_FILE_SHA256: Final = "69520f0aa1eeb8ee38e744669a66e443c3e0637e4448200331f9ae6099ae499f"
V7_TERMINAL_PATH: Final = "artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"
V7_TERMINAL_SHA256: Final = "90826498333079cfe7640c21b618fc03f0ee32e53ea5e80ba1b8b72f542792ba"
V7_AUDIT_PATH: Final = "src/arc3_voi/action_qbc_v7_audit.py"
V7_AUDIT_BLOB: Final = "97adf13b9fcb753565a0197ece00ebef13312d5d"
V7_AUDIT_SHA256: Final = "559db2774e213abd5bec9dd073c6bfae7ccd5fdefedb7dbecbf0f96499cd81cd"
V7_REFERENCE_PATH: Final = "src/arc3_voi/action_qbc_v7_reference.py"
V7_REFERENCE_BLOB: Final = "2d019b3d28524c75fd1657048ca1b67c145f3b97"
V7_REFERENCE_SHA256: Final = "34b24f96c5de4cad1026aa45ee388cf6dac1ee585ba42474a0a15ae216e46455"
V7_RUNNER_PATH: Final = "scripts/run_action_qbc_v7_open_diagnostic.py"
V7_RUNNER_BLOB: Final = "0b133eaad4169015e08533c6b78a0797f71a0825"
V7_RUNNER_SHA256: Final = "c25b11532a9e22943c452d1c51f54c27b197345840821ed9c343a1b0e9e248ac"

REGISTRATION_PATH: Final = "artifacts/action_qbc_v8_open_registration.json"
OUTPUT_PATH: Final = REGISTRATION_PATH
V8_AUDIT_PATH: Final = "src/arc3_voi/action_qbc_v8_audit.py"
OPEN_FREEZE_TAG: Final = "action-qbc-v8-open-diagnostic-freeze-v1"
RESULT_TAG: Final = "action-qbc-v8-open-diagnostic-result-v1"
RESULT_BRANCH: Final = "action-qbc-v8-open-diagnostic-result"

NON_REGISTRATION_ADDITIONS: Final = (
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
    V8_AUDIT_PATH,
    "tests/test_action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_lifecycle.py",
    "tests/test_action_qbc_v8_registration.py",
)
ALL_ADDITIONS: Final = tuple(sorted((*NON_REGISTRATION_ADDITIONS, REGISTRATION_PATH)))

TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schema_version", "status", "treatment_id", "diagnostic_system_id",
        "comparison_semantics_id", "runtime_id", "preregistration", "v6_negative",
        "platform", "dependencies", "source_manifest", "scene_inventory", "row_inventory",
        "transform_contracts", "scientific_contract", "resource_contract",
        "execution_contract", "authorization", "content_sha256",
    }
)
AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v8_enabled": False,
    "final_admission_claimed": False,
}

PREPARATION_COMMAND_ENVIRONMENT: Final = {
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
PREPARATION_COMMAND_POLICY: Final = {
    "default_timeout_seconds": 60,
    "environment_timeout_seconds": 600,
    "term_grace_seconds": 5,
    "kill_grace_seconds": 5,
    "stdin_cap_bytes": 1_048_576,
    "stdout_cap_bytes": 134_217_728,
    "stderr_cap_bytes": 1_048_576,
}
PREPARATION_SOURCE_URL: Final = (
    "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi"
)

WINDOWS_REPOSITORY_CONTRACT: Final = {
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

AUDIT_REPLACEMENTS: Final = (
    (1, "prereg-action-qbc-v7-open-failure-decomposition-v1", PREREGISTRATION_TAG),
    (1, "action-qbc-v7-open-failure-decomposition-v1", TREATMENT_ID),
    (1, "crosslevel-voi-open-diagnostic-v7", DIAGNOSTIC_SYSTEM_ID),
    (1, "action-qbc-v7-boundary-compound-selector-decomposition-v1", COMPARISON_SEMANTICS_ID),
    (1, "action-qbc-v7-open-registration-v1", SCHEMA_VERSION),
    (1, "action-qbc-v7-open-diagnostic-payload-v1", "action-qbc-v8-open-diagnostic-payload-v1"),
    (1, "action-qbc-v7-open-diagnostic-freeze-v1", OPEN_FREEZE_TAG),
    (1, V7_PREREGISTRATION_COMMIT, PREREGISTRATION_COMMIT),
    (1, "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md", PREREGISTRATION_DOCUMENT),
    (1, "fcd284ce499983fcc953f54a9f833e1b6d80a822384768f75cb18948d627a1a7", PREREGISTRATION_DOCUMENT_SHA256),
    (4, V7_REGISTRATION_PATH, REGISTRATION_PATH),
    (1, "runtime_v7_enabled", "runtime_v8_enabled"),
)


class ReconstructionError(RuntimeError):
    """Raised when exact registration reconstruction cannot be proved."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the one registered compact sorted-key ASCII JSON encoding."""

    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def strict_object(raw: bytes, label: str = "JSON object") -> dict[str, object]:
    """Parse a canonical JSON object while rejecting duplicate keys and non-finite numbers."""

    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ReconstructionError(f"{label} has duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ReconstructionError(f"{label} has non-finite JSON number: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs_hook, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReconstructionError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ReconstructionError(f"{label} must be a JSON object")
    if canonical_json_bytes(value) != raw:
        raise ReconstructionError(f"{label} bytes are not canonical compact ASCII JSON")
    return value


_strict_object = strict_object


def _read_regular_nofollow(
    path: Path,
    label: str,
    *,
    maximum: int = 134_217_728,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ReconstructionError(f"{label} is unavailable as a no-follow file") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > maximum:
            raise ReconstructionError(f"{label} is not a bounded regular file")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            stat.S_IMODE(before.st_mode),
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            stat.S_IMODE(after.st_mode),
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(raw) != before.st_size:
            raise ReconstructionError(f"{label} changed during its no-follow read")
        if len(raw) > maximum:
            raise ReconstructionError(f"{label} exceeds its byte cap")
        return raw
    finally:
        os.close(descriptor)


def _hex(value: object, length: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ReconstructionError(f"{label} is not lowercase {length}-hex")
    return value


def _git_executable() -> str:
    # Linux lifecycle code is bound to the literal executable.  Windows pre-O construction
    # necessarily uses the frozen caller's PATH-resolved Git.
    return "/usr/bin/git" if os.name == "posix" else "git"


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    supplied_input = b"" if input_bytes is None else input_bytes
    if len(supplied_input) > PREPARATION_COMMAND_POLICY["stdin_cap_bytes"]:
        raise ReconstructionError("local Git query exceeds the registered stdin cap")
    global_options = (
        ("--no-replace-objects", "--no-optional-locks")
        if os.name == "nt"
        else ("--no-replace-objects",)
    )
    argv = (_git_executable(), *global_options, "-C", str(root), *arguments)
    try:
        completed = subprocess.run(
            argv,
            input=input_bytes,
            check=False,
            capture_output=True,
            env=dict(PREPARATION_COMMAND_ENVIRONMENT) if os.name == "posix" else None,
            timeout=PREPARATION_COMMAND_POLICY["default_timeout_seconds"],
        )
    except subprocess.TimeoutExpired as error:
        raise ReconstructionError(
            f"local Git query exceeded 60 seconds ({' '.join(arguments)})"
        ) from error
    if len(completed.stdout) > PREPARATION_COMMAND_POLICY["stdout_cap_bytes"]:
        raise ReconstructionError("local Git query exceeds the registered stdout cap")
    if len(completed.stderr) > PREPARATION_COMMAND_POLICY["stderr_cap_bytes"]:
        raise ReconstructionError("local Git query exceeds the registered stderr cap")
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReconstructionError(f"local Git query failed ({' '.join(arguments)}): {detail}")
    return completed.stdout


def _tag_commit(root: Path, tag: str, expected: str, label: str) -> str:
    if _git(root, "cat-file", "-t", tag).strip() != b"commit":
        raise ReconstructionError(f"{label} tag is absent or annotated")
    commit = _git(root, "rev-parse", tag).decode("ascii").strip()
    if commit != expected:
        raise ReconstructionError(f"{label} tag does not resolve to its frozen commit")
    return commit


def _require_direct_child(
    root: Path,
    child: str,
    parent: str,
    label: str,
) -> None:
    """Require one and only one commit parent, equal to the frozen parent."""

    expected = f"{child} {parent}\n".encode("ascii")
    observed = _git(root, "rev-list", "--parents", "-n", "1", child)
    if observed != expected:
        raise ReconstructionError(f"{label} is not a direct child of its frozen parent")


def _parse_tree_entries(raw: bytes, label: str) -> list[tuple[str, str, str, int | None]]:
    rows: list[tuple[str, str, str, int | None]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, tab, path_bytes = record.partition(b"\t")
        fields = metadata.split()
        if not tab or len(fields) not in {3, 4}:
            raise ReconstructionError(f"malformed {label} entry")
        mode = fields[0].decode("ascii")
        if len(fields) == 4:
            object_type, oid, size_raw = fields[1:]
            if object_type != b"blob":
                raise ReconstructionError(f"non-blob {label} entry")
            size: int | None = int(size_raw)
        else:
            oid_raw, stage_raw = fields[1:]
            if stage_raw != b"0":
                raise ReconstructionError(f"non-stage-zero {label} entry")
            oid, size = oid_raw, None
        if mode != "100644":
            raise ReconstructionError(f"non-regular mode in {label}: {mode}")
        path = path_bytes.decode("utf-8")
        oid_text = _hex(oid.decode("ascii"), 40, f"{label} blob {path}")
        rows.append((path, mode, oid_text, size))
    rows.sort(key=lambda row: row[0].encode("utf-8"))
    if not rows or len({row[0] for row in rows}) != len(rows):
        raise ReconstructionError(f"{label} is empty or has duplicate paths")
    return rows


def _tree_entries(root: Path, commit: str) -> list[tuple[str, str, str, int | None]]:
    return _parse_tree_entries(
        _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit),
        f"tree {commit}",
    )


def _index_entries(root: Path) -> list[tuple[str, str, str, int | None]]:
    return _parse_tree_entries(_git(root, "ls-files", "--stage", "-z"), "stage-zero index")


def _batch_blobs(
    root: Path, entries: Sequence[tuple[str, str, str, int | None]]
) -> list[bytes]:
    request = b"".join(oid.encode("ascii") + b"\n" for _, _, oid, _ in entries)
    response = _git(root, "cat-file", "--batch", input_bytes=request)
    offset = 0
    result: list[bytes] = []
    for path, _mode, oid, declared_size in entries:
        newline = response.find(b"\n", offset)
        if newline < 0:
            raise ReconstructionError("truncated cat-file batch header")
        fields = response[offset:newline].split()
        if len(fields) != 3 or fields[:2] != [oid.encode("ascii"), b"blob"]:
            raise ReconstructionError(f"unexpected cat-file header for {path}")
        size = int(fields[2])
        if declared_size is not None and declared_size != size:
            raise ReconstructionError(f"tree size differs from cat-file size: {path}")
        start, end = newline + 1, newline + 1 + size
        if end >= len(response) or response[end : end + 1] != b"\n":
            raise ReconstructionError(f"truncated cat-file blob for {path}")
        raw = response[start:end]
        calculated = hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
            usedforsecurity=False,
        ).hexdigest()
        if calculated != oid:
            raise ReconstructionError(f"Git blob identity mismatch: {path}")
        result.append(raw)
        offset = end + 1
    if offset != len(response):
        raise ReconstructionError("cat-file batch response has trailing bytes")
    return result


def _manifest_and_blobs(
    root: Path, entries: Sequence[tuple[str, str, str, int | None]]
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    blobs = _batch_blobs(root, entries)
    manifest: list[dict[str, object]] = []
    by_path: dict[str, bytes] = {}
    for (path, mode, oid, _declared), raw in zip(entries, blobs, strict=True):
        by_path[path] = raw
        manifest.append(
            {
                "mode": mode,
                "path": path,
                "git_blob_sha1": oid,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        )
    return manifest, by_path


def _manifest_for_paths(
    root: Path,
    entries: Sequence[tuple[str, str, str, int | None]],
    paths: Sequence[str],
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    lookup = {row[0]: row for row in entries}
    if set(paths) - set(lookup):
        raise ReconstructionError(f"registered paths absent from Git objects: {sorted(set(paths) - set(lookup))}")
    selected = [lookup[path] for path in sorted(paths, key=lambda value: value.encode("utf-8"))]
    return _manifest_and_blobs(root, selected)


def _blob_at(root: Path, commit: str, path: str) -> tuple[dict[str, object], bytes]:
    entries = [entry for entry in _tree_entries(root, commit) if entry[0] == path]
    if len(entries) != 1:
        raise ReconstructionError(f"frozen blob absent or duplicated: {commit}:{path}")
    manifest, blobs = _manifest_and_blobs(root, entries)
    return manifest[0], blobs[path]


def _expected_name_status(paths: Sequence[str]) -> bytes:
    return b"".join(b"A\0" + path.encode("utf-8") + b"\0" for path in sorted(paths))


def _resolve_phase(root: Path) -> tuple[str, str, list[tuple[str, str, str, int | None]]]:
    """Validate the P8/O8 boundary and return phase, HEAD, and authoritative entries."""

    _tag_commit(
        root,
        PREREGISTRATION_V1_TAG,
        PREREGISTRATION_V1_COMMIT,
        "superseded preregistration v1",
    )
    _tag_commit(
        root,
        PREREGISTRATION_V2_TAG,
        PREREGISTRATION_V2_COMMIT,
        "superseded preregistration v2",
    )
    _tag_commit(
        root,
        PREREGISTRATION_V3_TAG,
        PREREGISTRATION_V3_COMMIT,
        "superseded preregistration v3",
    )
    _tag_commit(root, PREREGISTRATION_TAG, PREREGISTRATION_COMMIT, "preregistration")
    _require_direct_child(
        root,
        PREREGISTRATION_V1_COMMIT,
        R7_COMMIT,
        "P8v1",
    )
    v1_delta = _git(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        R7_COMMIT,
        PREREGISTRATION_V1_COMMIT,
    )
    expected_addition = b"A\0" + PREREGISTRATION_V1_DOCUMENT.encode("utf-8") + b"\0"
    if v1_delta != expected_addition:
        raise ReconstructionError("R7..P8v1 is not the one-document preregistration addition")
    _require_direct_child(
        root,
        PREREGISTRATION_V2_COMMIT,
        PREREGISTRATION_V1_COMMIT,
        "P8v2",
    )
    binding_delta = _git(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        PREREGISTRATION_V1_COMMIT,
        PREREGISTRATION_V2_COMMIT,
    )
    expected_modification = b"M\0" + PREREGISTRATION_V2_DOCUMENT.encode("utf-8") + b"\0"
    if binding_delta != expected_modification:
        raise ReconstructionError("P8v1..P8v2 is not the one-document binding correction")
    v1_entry, v1_raw = _blob_at(
        root,
        PREREGISTRATION_V1_COMMIT,
        PREREGISTRATION_V1_DOCUMENT,
    )
    if (
        v1_entry.get("git_blob_sha1") != PREREGISTRATION_V1_DOCUMENT_BLOB
        or hashlib.sha256(v1_raw).hexdigest() != PREREGISTRATION_V1_DOCUMENT_SHA256
    ):
        raise ReconstructionError("P8v1 document identity differs from the immutable original")
    binding_entry, binding_raw = _blob_at(
        root,
        PREREGISTRATION_V2_COMMIT,
        PREREGISTRATION_V2_DOCUMENT,
    )
    if (
        binding_entry.get("git_blob_sha1") != PREREGISTRATION_V2_DOCUMENT_BLOB
        or hashlib.sha256(binding_raw).hexdigest() != PREREGISTRATION_V2_DOCUMENT_SHA256
        or len(binding_raw) != PREREGISTRATION_V2_DOCUMENT_BYTE_COUNT
    ):
        raise ReconstructionError("P8v2 document identity differs from the binding correction")
    _require_direct_child(
        root,
        PREREGISTRATION_V3_COMMIT,
        PREREGISTRATION_V2_COMMIT,
        "P8v3",
    )
    v3_delta = _git(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        PREREGISTRATION_V2_COMMIT,
        PREREGISTRATION_V3_COMMIT,
    )
    v3_expected_addition = b"A\0" + PREREGISTRATION_V3_DOCUMENT.encode("utf-8") + b"\0"
    if v3_delta != v3_expected_addition:
        raise ReconstructionError("P8v2..P8v3 is not the one-document administrative correction")
    v3_entry, v3_raw = _blob_at(
        root,
        PREREGISTRATION_V3_COMMIT,
        PREREGISTRATION_V3_DOCUMENT,
    )
    if (
        v3_entry.get("git_blob_sha1") != PREREGISTRATION_V3_DOCUMENT_BLOB
        or hashlib.sha256(v3_raw).hexdigest() != PREREGISTRATION_V3_DOCUMENT_SHA256
        or len(v3_raw) != PREREGISTRATION_V3_DOCUMENT_BYTE_COUNT
    ):
        raise ReconstructionError("P8v3 document identity differs from the frozen correction")
    _require_direct_child(
        root,
        PREREGISTRATION_COMMIT,
        PREREGISTRATION_V3_COMMIT,
        "P8v4",
    )
    v4_delta = _git(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        PREREGISTRATION_V3_COMMIT,
        PREREGISTRATION_COMMIT,
    )
    v4_expected_addition = b"A\0" + PREREGISTRATION_DOCUMENT.encode("utf-8") + b"\0"
    if v4_delta != v4_expected_addition:
        raise ReconstructionError("P8v3..P8v4 is not the one-document administrative correction")
    v4_entry, v4_raw = _blob_at(
        root,
        PREREGISTRATION_COMMIT,
        PREREGISTRATION_DOCUMENT,
    )
    if (
        v4_entry.get("git_blob_sha1") != PREREGISTRATION_DOCUMENT_BLOB
        or hashlib.sha256(v4_raw).hexdigest() != PREREGISTRATION_DOCUMENT_SHA256
        or len(v4_raw) != PREREGISTRATION_DOCUMENT_BYTE_COUNT
    ):
        raise ReconstructionError("P8v4 document identity differs from the frozen correction")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    _hex(head, 40, "HEAD")
    if head == PREREGISTRATION_COMMIT:
        if _git(root, "diff", "--name-status", "--no-renames", "-z") != b"":
            raise ReconstructionError("pre-O8 worktree has filtered changes to staged/tracked bytes")
        cached = _git(
            root, "diff", "--cached", "--name-status", "--no-renames", "-z", PREREGISTRATION_COMMIT
        )
        if cached not in {
            _expected_name_status(NON_REGISTRATION_ADDITIONS),
            _expected_name_status(ALL_ADDITIONS),
        }:
            raise ReconstructionError("pre-O8 index is not the exact fourteen- or fifteen-addition allowlist")
        status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        allowed = set(ALL_ADDITIONS)
        seen: set[str] = set()
        for record in status.split(b"\0"):
            if not record:
                continue
            if len(record) < 4 or record[2:3] != b" ":
                raise ReconstructionError("malformed pre-O8 Git status")
            code = record[:2]
            path = record[3:].decode("utf-8")
            if path not in allowed or code not in {b"A ", b"??"}:
                raise ReconstructionError(f"non-allowlisted pre-O8 state: {code!r} {path}")
            seen.add(path)
        if not set(NON_REGISTRATION_ADDITIONS) <= seen:
            raise ReconstructionError("pre-O8 status lacks one of the fourteen staged additions")
        return "pre_open_freeze", head, _index_entries(root)
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") != b"":
        raise ReconstructionError("open-freeze checkout is not Git-clean")
    _require_direct_child(root, head, PREREGISTRATION_COMMIT, "O8")
    delta = _git(root, "diff", "--name-status", "--no-renames", "-z", PREREGISTRATION_COMMIT, head)
    if delta != _expected_name_status(ALL_ADDITIONS):
        raise ReconstructionError("P8v4..O8 is not the exact fifteen-addition allowlist")
    _tag_commit(root, OPEN_FREEZE_TAG, head, "open-freeze")
    index = _index_entries(root)
    tree = _tree_entries(root, head)
    if [(p, m, o) for p, m, o, _ in index] != [(p, m, o) for p, m, o, _ in tree]:
        raise ReconstructionError("clean O8 stage-zero index differs from its tree")
    return "open_freeze", head, index


def _verify_frozen_anchors(root: Path) -> dict[str, object]:
    _tag_commit(root, R7_TAG, R7_COMMIT, "v7 result")
    _tag_commit(root, O7_TAG, O7_COMMIT, "v7 open-freeze")
    _require_direct_child(root, R7_COMMIT, O7_COMMIT, "R7")
    registration_entry, registration_raw = _blob_at(root, R7_COMMIT, V7_REGISTRATION_PATH)
    if hashlib.sha256(registration_raw).hexdigest() != V7_REGISTRATION_FILE_SHA256:
        raise ReconstructionError("frozen v7 registration file SHA-256 mismatch")
    registration = strict_object(registration_raw, "frozen v7 registration")
    if registration.get("content_sha256") != V7_REGISTRATION_CONTENT_SHA256:
        raise ReconstructionError("frozen v7 registration content identity mismatch")
    preimage = dict(registration)
    preimage.pop("content_sha256", None)
    if canonical_sha256(preimage) != V7_REGISTRATION_CONTENT_SHA256:
        raise ReconstructionError("frozen v7 registration content hash is invalid")
    terminal_entry, terminal_raw = _blob_at(root, R7_COMMIT, V7_TERMINAL_PATH)
    if hashlib.sha256(terminal_raw).hexdigest() != V7_TERMINAL_SHA256:
        raise ReconstructionError("frozen v7 administrative terminal mismatch")
    audit_entry, audit_raw = _blob_at(root, O7_COMMIT, V7_AUDIT_PATH)
    reference_entry, reference_raw = _blob_at(root, O7_COMMIT, V7_REFERENCE_PATH)
    runner_entry, runner_raw = _blob_at(root, O7_COMMIT, V7_RUNNER_PATH)
    expected = (
        (audit_entry, audit_raw, V7_AUDIT_BLOB, V7_AUDIT_SHA256, "v7 audit"),
        (reference_entry, reference_raw, V7_REFERENCE_BLOB, V7_REFERENCE_SHA256, "v7 reference"),
        (runner_entry, runner_raw, V7_RUNNER_BLOB, V7_RUNNER_SHA256, "v7 runner"),
    )
    for entry, raw, oid, digest, label in expected:
        if entry["git_blob_sha1"] != oid or hashlib.sha256(raw).hexdigest() != digest:
            raise ReconstructionError(f"frozen {label} identity mismatch")
    return {
        "v7_registration": registration,
        "v7_registration_entry": registration_entry,
        "v7_terminal_entry": terminal_entry,
        "v7_audit_entry": audit_entry,
        "v7_audit_raw": audit_raw,
        "v7_reference_entry": reference_entry,
        "v7_runner_entry": runner_entry,
    }


def _audit_transformation(
    anchors: Mapping[str, object],
    added_manifest: Sequence[Mapping[str, object]],
    added_blobs: Mapping[str, bytes],
) -> dict[str, object]:
    source = cast(bytes, anchors["v7_audit_raw"])
    transformed = source
    rows: list[dict[str, object]] = []
    for count, old, new in AUDIT_REPLACEMENTS:
        old_bytes, new_bytes = old.encode("ascii"), new.encode("ascii")
        observed = transformed.count(old_bytes)
        if observed != count:
            raise ReconstructionError(
                f"audit replacement count mismatch for {old!r}: expected {count}, observed {observed}"
            )
        transformed = transformed.replace(old_bytes, new_bytes)
        rows.append({"count": count, "old_ascii": old, "new_ascii": new})
    actual = added_blobs.get(V8_AUDIT_PATH)
    if actual is None or actual != transformed:
        raise ReconstructionError("staged v8 audit is not the exact ordered section-4 transformation")
    generated = next((dict(row) for row in added_manifest if row.get("path") == V8_AUDIT_PATH), None)
    if generated is None:
        raise ReconstructionError("v8 audit identity is absent from the added-files manifest")
    input_modules = []
    for key, commit in (("v7_audit_entry", O7_COMMIT), ("v7_reference_entry", O7_COMMIT)):
        entry = cast(Mapping[str, object], anchors[key])
        input_modules.append(
            {
                "commit_sha": commit,
                "path": entry["path"],
                "git_blob_sha1": entry["git_blob_sha1"],
                "sha256": entry["sha256"],
                "byte_count": entry["byte_count"],
            }
        )
    return {
        "schema_version": "action-qbc-v8-audit-source-transformation-v1",
        "replacements": rows,
        "input_modules": input_modules,
        "generated_module": generated,
    }


def _result_document_contract(
    added_manifest: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    renderer_path = "scripts/finalize_action_qbc_v8_open_diagnostic.py"
    renderer_entry = next((dict(row) for row in added_manifest if row.get("path") == renderer_path), None)
    if renderer_entry is None:
        raise ReconstructionError("result-document renderer is absent from the staged manifest")
    renderer = {
        "path": renderer_entry["path"], "mode": renderer_entry["mode"],
        "git_blob_sha1": renderer_entry["git_blob_sha1"], "sha256": renderer_entry["sha256"],
        "size_bytes": renderer_entry["byte_count"],
    }
    normal_template = (
        "# action-QBC v8 open diagnostic result\n\n"
        "- disposition: `{disposition}`\n"
        "- stage: `{stage}`\n"
        "- underlying stage: `{underlying_stage}`\n"
        f"- treatment: `{TREATMENT_ID}`\n"
        "- open-freeze commit: `{open_freeze_commit_sha}`\n"
        "- registration content SHA-256: `{registration_content_sha256}`\n"
        "- authorization: all false\n"
    )
    emergency_template = (
        normal_template
        + "- finalizer classification: `{finalizer_classification}`\n"
        + "- finalizer exit code: `{finalizer_exit_code}`\n"
        + "- finalizer timed out: `{finalizer_timed_out}`\n"
        + "- finalizer child cleanup passes: `{finalizer_child_cleanup_passes}`\n"
        + "- finalization bundle: `{finalization_bundle_exists}` / `{finalization_bundle_sha256}`\n"
        + "- lifecycle ledger: `{lifecycle_ledger_exists}` / `{lifecycle_ledger_sha256}`\n"
        + "- preparation receipt: `{preparation_receipt_exists}` / "
        + "`{preparation_receipt_read_status}` / `{preparation_receipt_sha256}`\n"
        + "- preparation verification receipt: "
        + "`{preparation_verification_receipt_exists}` / "
        + "`{preparation_verification_receipt_read_status}` / "
        + "`{preparation_verification_receipt_sha256}`\n"
    )
    normal_inputs = sorted(
        ["disposition", "stage", "underlying_stage", "open_freeze_commit_sha", "registration_content_sha256"]
    )
    emergency_inputs = sorted(
        [
            *normal_inputs, "finalizer_classification", "finalizer_exit_code",
            "finalizer_timed_out", "finalizer_child_cleanup_passes",
            "finalization_bundle_exists", "finalization_bundle_sha256",
            "lifecycle_ledger_exists", "lifecycle_ledger_sha256",
            "preparation_receipt_exists", "preparation_receipt_read_status",
            "preparation_receipt_sha256", "preparation_verification_receipt_exists",
            "preparation_verification_receipt_read_status",
            "preparation_verification_receipt_sha256",
        ]
    )
    case_names = [
        None,
        "remote_verification_failed", "remote_receipt_invalid", "arm_receipt_invalid",
        "registration_invalid", "authority_identity_invalid", "lifecycle_ledger_invalid",
        "lifecycle_driver_failed", "process_a_nonzero", "process_a_output_missing",
        "process_a_validation_failed", "process_b_nonzero", "process_b_output_missing",
        "process_b_validation_failed", "payload_byte_mismatch", "receipt_finalization_failed",
    ]
    normal_cases: list[dict[str, object]] = []
    for case in case_names:
        if case is None:
            disposition, stage, underlying = "scientific_result", None, None
        elif case == "receipt_finalization_failed":
            disposition, stage, underlying = "administrative_terminal", case, "<UNDERLYING_STAGE_OR_NULL>"
        else:
            disposition = "administrative_terminal"
            stage = underlying = case
        rendered = normal_template.format(
            disposition=disposition,
            stage="null" if stage is None else stage,
            underlying_stage="null" if underlying is None else underlying,
            open_freeze_commit_sha="<O8_COMMIT>",
            registration_content_sha256="<REGISTRATION_CONTENT_SHA256>",
        ).encode("ascii")
        normal_cases.append(
            {
                "disposition": disposition, "stage": stage, "underlying_stage": underlying,
                "content_base64": base64.b64encode(rendered).decode("ascii"),
                "sha256": hashlib.sha256(rendered).hexdigest(), "size_bytes": len(rendered),
            }
        )
    return {
        "schema_version": "action-qbc-v8-result-document-contract-v1",
        "renderer_source": renderer,
        "normal_template": {"text": normal_template, "sha256": hashlib.sha256(normal_template.encode("ascii")).hexdigest()},
        "emergency_template": {"text": emergency_template, "sha256": hashlib.sha256(emergency_template.encode("ascii")).hexdigest()},
        "normal_input_names": normal_inputs,
        "emergency_input_names": emergency_inputs,
        "normal_cases": normal_cases,
    }


def _execution_contract(added_manifest: Sequence[Mapping[str, object]]) -> dict[str, object]:
    root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"
    authority = f"{root}/authority"
    processes = f"{root}/processes"
    a_root, b_root = f"{processes}/process-a", f"{processes}/process-b"
    a_output = f"{processes}/process-a-output/open/action_qbc_v8_open_diagnostic.json"
    b_output = f"{processes}/process-b-output/open/action_qbc_v8_open_diagnostic.json"
    preparation_receipt = f"{root}/preparation-receipt.json"
    preparation_verification_receipt = f"{root}/preparation-verification.json"
    remote_claim = f"{root}/remote-verification-claim.json"
    remote_verifier_claim = f"{root}/remote-verifier-start-claim.json"
    remote_receipt = f"{root}/remote-verification.json"
    remote_supervisor_receipt = f"{root}/remote-verification-supervisor.json"
    arm_receipt = f"{root}/arm-receipt.json"
    driver_claim = f"{root}/lifecycle-driver-claim.json"
    ledger = f"{root}/lifecycle-ledger.json"
    a_start = f"{root}/process-a-start-claim.json"
    b_start = f"{root}/process-b-start-claim.json"
    a_validator = f"{root}/process-a-validator-claim.json"
    b_validator = f"{root}/process-b-validator-claim.json"
    a_validation = f"{root}/process-a-validation.json"
    b_validation = f"{root}/process-b-validation.json"
    win_claim = r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json"
    win_verifier_claim = r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim.json"
    win_receipt = r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification.json"
    win_supervisor_receipt = r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor.json"
    linux_claim = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim.json"
    linux_verifier_claim = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim.json"
    linux_receipt = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification.json"
    linux_supervisor_receipt = "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor.json"

    producer = [
        "uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B",
        "scripts/build_action_qbc_v8_open_registration.py", "--repository-root", ".",
        "--preregistration-tag", PREREGISTRATION_TAG, "--output", REGISTRATION_PATH,
    ]
    reconstructor = [
        "uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B",
        "scripts/reconstruct_action_qbc_v8_open_registration.py", "--repository-root", ".",
        "--registration", REGISTRATION_PATH,
    ]
    linux_host_launcher = [
        r"C:\Windows\System32\wsl.exe", "-d", "Ubuntu", "--cd",
        "<REGISTERED_LINUX_CWD>", "--", "<INNER_ARGV...>",
    ]
    bootstrap = [
        ["/usr/bin/test", "!", "-e", root],
        ["/usr/bin/install", "-d", "-m", "700", root],
        ["/usr/bin/install", "-d", "-m", "700", authority],
        ["/usr/bin/git", "--no-replace-objects", "clone", "--no-local", "--no-checkout", "--branch", OPEN_FREEZE_TAG, "--single-branch", "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi", authority],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "config", "--local", "core.autocrlf", "false"],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "config", "--local", "core.eol", "lf"],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "config", "--local", "core.safecrlf", "true"],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "checkout", "--detach", "<O8_COMMIT>"],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "remote", "remove", "origin"],
        ["/usr/bin/git", "--no-replace-objects", "-C", authority, "rev-parse", "HEAD"],
    ]
    preparation = [
        "/usr/bin/python3", "-I", "-B", "scripts/prepare_action_qbc_v8_open.py", "prepare",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--execution-root", root, "--receipt", preparation_receipt,
    ]
    environment = [
        "/usr/bin/env", "UV_OFFLINE=1", "/usr/local/bin/uv", "sync", "--python",
        "3.12.13", "--frozen", "--no-dev", "--offline",
    ]
    preflight = [
        ["/usr/bin/git", "--no-replace-objects", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        ["/usr/bin/git", "--no-replace-objects", "rev-parse", "HEAD"],
        [".venv/bin/python3", "--version"],
        ["/usr/local/bin/uv", "--version"],
        ["/usr/bin/python3", "-I", "-B", "scripts/reconstruct_action_qbc_v8_open_registration.py", "--repository-root", ".", "--registration", REGISTRATION_PATH, "--verify-open-freeze"],
    ]
    post_preparation = [
        "/usr/bin/python3", "-I", "-B", "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--verify-preparation", "--preparation-receipt", preparation_receipt,
        "--verification-receipt", preparation_verification_receipt,
    ]
    remote_supervisor = [
        r"C:\Users\User\anaconda3\python.exe", "-I", "-B",
        r"scripts\supervise_action_qbc_v8_remote_tag.py", "--repository-root", ".",
        "--registration", r"artifacts\action_qbc_v8_open_registration.json",
        "--claim", win_claim, "--verifier-start-claim", win_verifier_claim,
        "--remote-receipt", win_receipt, "--supervisor-receipt", win_supervisor_receipt,
        "--verifier-python", r"C:\Users\User\anaconda3\python.exe",
        "--git-executable", r"C:\Users\User\anaconda3\Library\bin\git.exe",
        "--taskkill-executable", r"C:\Windows\System32\taskkill.exe",
        "--verifier-child-deadline-seconds", "430", "--supervisor-deadline-seconds", "480",
        "--child-cleanup-timeout-seconds", "30",
    ]
    remote_verifier = [
        r"C:\Users\User\anaconda3\python.exe", "-I", "-B",
        r"scripts\verify_action_qbc_v8_remote_tag.py", "--repository-root", ".",
        "--registration", r"artifacts\action_qbc_v8_open_registration.json",
        "--claim", win_claim, "--verifier-start-claim", win_verifier_claim,
        "--receipt", win_receipt,
        "--git-executable", r"C:\Users\User\anaconda3\Library\bin\git.exe",
        "--taskkill-executable", r"C:\Windows\System32\taskkill.exe",
        "--max-attempts", "3", "--attempt-timeout-seconds", "120",
        "--retry-delay-seconds", "15", "--overall-deadline-seconds", "390",
    ]
    arm = [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "120s",
        "/usr/bin/python3", "-I", "-B", "scripts/prepare_action_qbc_v8_open.py", "arm",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--execution-root", root, "--preparation-receipt", preparation_receipt,
        "--preparation-verification-receipt", preparation_verification_receipt,
        "--windows-claim", linux_claim, "--windows-verifier-start-claim", linux_verifier_claim,
        "--windows-remote-receipt", linux_receipt,
        "--windows-supervisor-receipt", linux_supervisor_receipt,
        "--arm-receipt", arm_receipt,
    ]
    lifecycle = [
        "/usr/bin/python3", "-I", "-B", "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "execute", "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--execution-root", root, "--preparation-receipt", preparation_receipt,
        "--preparation-verification-receipt", preparation_verification_receipt,
        "--windows-claim", linux_claim, "--remote-claim", remote_claim,
        "--remote-verifier-claim", remote_verifier_claim, "--remote-receipt", remote_receipt,
        "--remote-supervisor-receipt", remote_supervisor_receipt, "--arm-receipt", arm_receipt,
        "--driver-claim", driver_claim, "--ledger", ledger,
    ]
    scientific = [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=15s", "2700s",
        ".venv/bin/python3", "-I", "-B", "scripts/run_action_qbc_v8_open_diagnostic.py",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--preparation-verification-receipt", preparation_verification_receipt,
        "--arm-receipt", arm_receipt, "--driver-claim", driver_claim, "--label", "<LABEL>",
        "--start-claim", "<START_CLAIM>", "--prior-validation-receipt",
        "<PRIOR_VALIDATION_OR_NULL>", "--compute-deadline-seconds", "2100",
        "--wall-time-seconds", "2400", "--output", "<OUTPUT_PATH>",
    ]
    validator = [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "300s",
        ".venv/bin/python3", "-I", "-B", "scripts/validate_action_qbc_v8_open_payload.py",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--arm-receipt", arm_receipt, "--driver-claim", driver_claim, "--label", "<LABEL>",
        "--start-claim", "<START_CLAIM>", "--validator-claim", "<VALIDATOR_CLAIM>",
        "--validation-receipt", "<VALIDATION_RECEIPT>", "--payload", "<OUTPUT_PATH>",
    ]
    finalization_bundle = f"{root}/finalization-bundle.json"
    emergency_bundle = f"{root}/emergency-result-bundle.json"
    finalizer = [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "300s",
        "/usr/bin/python3", "-I", "-B", "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--preparation-receipt", preparation_receipt,
        "--preparation-verification-receipt", preparation_verification_receipt,
        "--remote-claim", remote_claim,
        "--remote-verifier-claim", remote_verifier_claim, "--remote-receipt", remote_receipt,
        "--remote-supervisor-receipt", remote_supervisor_receipt, "--arm-receipt", arm_receipt,
        "--driver-claim", driver_claim, "--lifecycle-ledger", ledger,
        "--process-a-start-claim", a_start, "--process-a-validator-claim", a_validator,
        "--process-a-validation-receipt", a_validation, "--process-a", a_output,
        "--process-b-start-claim", b_start, "--process-b-validator-claim", b_validator,
        "--process-b-validation-receipt", b_validation, "--process-b", b_output,
        "--bundle", finalization_bundle,
    ]
    publisher = [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "600s",
        "/usr/bin/python3", "-I", "-B", "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "publish", "--repository-root", ".", "--registration", REGISTRATION_PATH,
        "--driver-claim", driver_claim, "--lifecycle-ledger", ledger,
        "--finalization-bundle", finalization_bundle, "--emergency-bundle", emergency_bundle,
        "--control-time-seconds", "570",
    ]
    tests = [
        ["uv", "run", "--frozen", "--extra", "dev", "pytest", "-q", "tests/test_action_qbc_v7_audit.py", "tests/test_action_qbc_v8_audit.py", "tests/test_action_qbc_v8_lifecycle.py", "tests/test_action_qbc_v8_registration.py"],
        ["uv", "run", "--frozen", "--extra", "dev", "ruff", "check", "src/arc3_voi/action_qbc_v8_audit.py", "scripts/build_action_qbc_v8_open_registration.py", "scripts/execute_action_qbc_v8_open_lifecycle.py", "scripts/finalize_action_qbc_v8_open_diagnostic.py", "scripts/prepare_action_qbc_v8_open.py", "scripts/reconstruct_action_qbc_v8_open_registration.py", "scripts/run_action_qbc_v8_open_diagnostic.py", "scripts/supervise_action_qbc_v8_remote_tag.py", "scripts/validate_action_qbc_v8_open_payload.py", "scripts/verify_action_qbc_v8_remote_tag.py", "tests/test_action_qbc_v8_audit.py", "tests/test_action_qbc_v8_lifecycle.py", "tests/test_action_qbc_v8_registration.py"],
        ["uv", "run", "--frozen", "--extra", "dev", "mypy", "--strict", "src/arc3_voi/action_qbc_v8_audit.py"],
    ]
    result_git_environment = {
        "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C", "LC_ALL": "C", "TZ": "UTC", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_DIR": f"{authority}/.git", "GIT_WORK_TREE": authority,
        "GIT_INDEX_FILE": f"{root}/result-git-work/index-<i>",
        "GIT_AUTHOR_NAME": "ARC3 v8 Result Bot", "GIT_AUTHOR_EMAIL": "arc3-v8-result@invalid.example",
        "GIT_AUTHOR_DATE": "2026-08-11T00:00:00+10:00",
        "GIT_COMMITTER_NAME": "ARC3 v8 Result Bot", "GIT_COMMITTER_EMAIL": "arc3-v8-result@invalid.example",
        "GIT_COMMITTER_DATE": "2026-08-11T00:00:00+10:00",
    }
    result_ref_transaction = {
        "authoritative_tag": f"refs/tags/{RESULT_TAG}",
        "forbidden_authority_branch": f"refs/heads/{RESULT_BRANCH}",
        "commit_message": "Record action-QBC v8 open diagnostic result\n",
        "git_plumbing_argvs": [
            ["/usr/bin/git", "--no-replace-objects", "read-tree", "<O8_COMMIT>"],
            ["/usr/bin/git", "--no-replace-objects", "hash-object", "-w", "--stdin"],
            ["/usr/bin/git", "--no-replace-objects", "update-index", "--add", "--cacheinfo", "100644,<FILE_BLOB>,<FILE_PATH>"],
            ["/usr/bin/git", "--no-replace-objects", "write-tree"],
            ["/usr/bin/git", "--no-replace-objects", "-c", "commit.gpgSign=false", "-c", "i18n.commitEncoding=UTF-8", "commit-tree", "<RESULT_TREE>", "-p", "<O8_COMMIT>"],
            ["/usr/bin/git", "--no-replace-objects", "diff-tree", "--no-commit-id", "--name-status", "-r", "-z", "<O8_COMMIT>", "<R8_COMMIT>"],
            ["/usr/bin/git", "--no-replace-objects", "cat-file", "-p", "<R8_COMMIT>"],
        ],
        "scratch_index_path": f"{root}/result-git-work/index-<i>",
        "scratch_lock_path": f"{root}/result-git-work/index-<i>.lock",
        "scratch_tag_path": f"{root}/result-git-work/result-tag-<i>",
        "scratch_tag_bytes": "<R8_COMMIT>\n",
        "scratch_tag_mode": "0444",
        "result_path_sets": {
            "scientific_result": ["artifacts/action_qbc_v8_open_diagnostic.json", "artifacts/action_qbc_v8_open_diagnostic_receipt.json", "docs/action_qbc_v8_open_diagnostic_result.md"],
            "administrative_terminal": ["artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json", "docs/action_qbc_v8_open_diagnostic_result.md"],
            "receipt_finalization_failed": ["docs/action_qbc_v8_open_diagnostic_result.md"],
            "finalizer_process_failed": ["docs/action_qbc_v8_open_diagnostic_result.md"],
        },
        "local_transfer_argvs": [
            ["/usr/bin/git", "--no-replace-objects", "-C", "/mnt/d/kaggle competitions/arc3-crosslevel-voi", "fetch", "--no-tags", f"file://{authority}", f"refs/tags/{RESULT_TAG}:refs/heads/{RESULT_BRANCH}"],
            ["/usr/bin/git", "--no-replace-objects", "-C", "/mnt/d/kaggle competitions/arc3-crosslevel-voi", "fetch", "--no-tags", f"file://{authority}", f"refs/tags/{RESULT_TAG}:refs/tags/{RESULT_TAG}"],
        ],
        "windows_publication_argvs": [
            [r"C:\Users\User\anaconda3\Library\bin\git.exe", "--no-replace-objects", "--no-optional-locks", "push", "origin", f"refs/heads/{RESULT_BRANCH}:refs/heads/{RESULT_BRANCH}"],
            [r"C:\Users\User\anaconda3\Library\bin\git.exe", "--no-replace-objects", "--no-optional-locks", "push", "origin", f"refs/tags/{RESULT_TAG}:refs/tags/{RESULT_TAG}"],
            [r"C:\Users\User\anaconda3\Library\bin\git.exe", "--no-replace-objects", "--no-optional-locks", "-c", "credential.interactive=never", "ls-remote", "--refs", "origin", f"refs/heads/{RESULT_BRANCH}", f"refs/tags/{RESULT_TAG}"],
        ],
    }
    windows_environment = {
        "SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows",
        "COMSPEC": r"C:\Windows\System32\cmd.exe",
        "TEMP": r"C:\Users\User\AppData\Local\Temp", "TMP": r"C:\Users\User\AppData\Local\Temp",
        "PATH": r"C:\Users\User\anaconda3\Library\mingw64\bin;C:\Users\User\anaconda3\Library\usr\bin;C:\Users\User\anaconda3\Library\bin;C:\Windows\System32;C:\Windows",
        "PATHEXT": ".COM;.EXE;.BAT;.CMD", "HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
        "XDG_CONFIG_HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "NUL", "GIT_CONFIG_COUNT": "0",
        "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never", "GIT_ASKPASS": "NUL",
        "SSH_ASKPASS": "NUL",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    remote_policy = {
        "max_attempts": 3, "attempt_timeout_seconds": 120, "retry_delay_seconds": 15,
        "overall_deadline_seconds": 390, "verifier_child_deadline_seconds": 430,
        "supervisor_deadline_seconds": 480, "supervisor_receipt_reserve_seconds": 20,
        "stdout_cap_bytes": 4096, "stderr_cap_bytes": 16384,
        "child_cleanup_timeout_seconds": 30, "windows_job_kill_on_close": True,
        "git_child_cwd": r"D:\kaggle competitions", "git_environment": windows_environment,
    }
    command_values = {
        "arm": arm, "bootstrap": bootstrap, "environment_build": environment,
        "finalizer": finalizer, "lifecycle_driver": lifecycle,
        "linux_host_launcher": linux_host_launcher, "payload_validator": validator,
        "post_preparation_validation": post_preparation, "preflight": preflight,
        "preparation": preparation, "producer": producer, "reconstructor": reconstructor,
        "remote_supervisor": remote_supervisor, "remote_verifier": remote_verifier,
        "result_publisher": publisher, "result_ref_transaction": result_ref_transaction,
        "scientific": scientific, "tests": tests,
    }
    hashes = {key: canonical_sha256(value) for key, value in command_values.items()}
    contract = {
        "administrative_stage_order": {
            "underlying_order": ["preparation_receipt_invalid", "preparation_verification_invalid", "remote_verification_failed", "remote_receipt_invalid", "arm_receipt_invalid", "registration_invalid", "authority_identity_invalid", "lifecycle_ledger_invalid", "lifecycle_driver_failed", "process_a_nonzero", "process_a_output_missing", "process_a_validation_failed", "process_b_nonzero", "process_b_output_missing", "process_b_validation_failed", "payload_byte_mismatch"],
            "disposition_overrides": ["receipt_finalization_failed", "finalizer_process_failed"],
        },
        "argv_hashes": hashes,
        "arm_argv": arm, "arm_receipt_path": arm_receipt, "arm_timeout_seconds": 120,
        "authority_root": authority, "bootstrap_steps": bootstrap,
        "compute_deadline_seconds": 2100, "environment_build_argv": environment,
        "emergency_bundle_path": emergency_bundle, "execution_root": root,
        "finalization_bundle_path": finalization_bundle,
        "linux_host_launcher": linux_host_launcher,
        "linux_platform": {
            "distribution": "Ubuntu", "release": "24.04.1 LTS", "codename": "noble",
            "kernel": "5.15.167.4-microsoft-standard-WSL2", "machine": "x86_64",
            "wsl_version": 2,
            "windows_host_launcher_identity": {
                "path": r"C:\Windows\System32\wsl.exe",
                "product_version": "10.0.26100.8737",
                "sha256": "7e9f5cee6d641481e5a942f0e08563bae9c17ee55f0aad888f9aa0be9a5d4757",
            },
        },
        "linux_tool_identities": [
            {"path": "/usr/bin/env", "version": "GNU coreutils 9.4", "sha256": "1490a663e7312c4347987b2e12d7d73950ed1e9a322449daf8e4836660396e31"},
            {"path": "/usr/bin/git", "version": "2.43.0", "sha256": "953577d782b6a4dada93cdb924a1261266c7b98aae6676e4ddeeddfc9a848e8e"},
            {"path": "/usr/bin/install", "version": "GNU coreutils 9.4", "sha256": "b4663b43190ea551f682cfac9500f3f4f6e94890d8ce8822bb81a819f15dab00"},
            {"path": "/usr/bin/python3", "version": "CPython 3.12.3", "sha256": "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118"},
            {"path": "/usr/bin/test", "version": "GNU coreutils 9.4", "sha256": "52b0ca5cef7e104ad5e0a8a29bd1522c205cc8404e46e153e5afc54605857c4d"},
            {"path": "/usr/bin/timeout", "version": "GNU coreutils 9.4", "sha256": "2ee918a5358c0388719e710134bc32cffb934f4bd2a8fb9beb86ef4d6ec8bd8a"},
            {"path": "/usr/local/bin/uv", "version": "0.11.28", "sha256": "1cb9cd0a1749debf6049d7d2bb933882cc52d81016326ee6d99a786d6c988b03"},
        ],
        "lifecycle_driver_argv": lifecycle, "lifecycle_driver_claim_path": driver_claim,
        "driver_deadline_seconds": 8400, "lifecycle_ledger_path": ledger,
        "local_git_timeout_seconds": 60, "finalizer_argv_template": finalizer,
        "finalizer_cwd": authority, "finalizer_timeout_seconds": 300,
        "hard_timeout_seconds": 2700, "payload_validator_argv_template": validator,
        "payload_validator_timeout_seconds": 300, "preflight_argvs": preflight,
        "post_preparation_validation_argv": post_preparation, "preparation_argv": preparation,
        "preparation_receipt_path": preparation_receipt,
        "preparation_verification_receipt_path": preparation_verification_receipt,
        "preparation_command_environment": dict(PREPARATION_COMMAND_ENVIRONMENT),
        "preparation_command_policy": dict(PREPARATION_COMMAND_POLICY),
        "process_a_output": a_output, "process_a_root": a_root,
        "process_a_start_claim": a_start, "process_a_validation_receipt": a_validation,
        "process_a_validator_claim": a_validator, "process_b_output": b_output,
        "process_b_root": b_root, "process_b_start_claim": b_start,
        "process_b_validation_receipt": b_validation, "process_b_validator_claim": b_validator,
        "process_labels": ["A", "B"], "producer_argv": producer,
        "reconstructor_argv": reconstructor, "registered_start_count": 2,
        "remote_claim_linux_path": linux_claim, "remote_claim_windows_path": win_claim,
        "remote_policy": remote_policy, "remote_receipt_linux_path": linux_receipt,
        "remote_receipt_windows_path": win_receipt, "remote_supervisor_argv": remote_supervisor,
        "remote_supervisor_receipt_linux_path": linux_supervisor_receipt,
        "remote_supervisor_receipt_windows_path": win_supervisor_receipt,
        "remote_verifier_claim_linux_path": linux_verifier_claim,
        "remote_verifier_claim_windows_path": win_verifier_claim,
        "remote_verifier_argv": remote_verifier,
        "result_document_contract": _result_document_contract(added_manifest),
        "result_git_environment": result_git_environment, "result_git_max_attempts": 3,
        "result_git_owner_path": f"{root}/result-git-owner.json",
        "result_git_work_root": f"{root}/result-git-work",
        "result_publisher_argv": publisher, "result_ref_transaction": result_ref_transaction,
        "scientific_argv_template": scientific, "test_argvs": tests,
        "third_start_allowed": False, "wall_time_seconds": 2400,
        "windows_repository_contract": json.loads(
            canonical_json_bytes(WINDOWS_REPOSITORY_CONTRACT)
        ),
    }
    expected_keys = {
        "administrative_stage_order", "argv_hashes", "arm_argv", "arm_receipt_path",
        "arm_timeout_seconds", "authority_root", "bootstrap_steps", "compute_deadline_seconds",
        "environment_build_argv", "emergency_bundle_path", "execution_root",
        "finalization_bundle_path", "linux_host_launcher", "linux_platform",
        "linux_tool_identities", "lifecycle_driver_argv", "lifecycle_driver_claim_path",
        "driver_deadline_seconds", "lifecycle_ledger_path", "local_git_timeout_seconds",
        "finalizer_argv_template", "finalizer_cwd", "finalizer_timeout_seconds",
        "hard_timeout_seconds", "payload_validator_argv_template",
        "payload_validator_timeout_seconds", "preflight_argvs",
        "post_preparation_validation_argv", "preparation_argv", "preparation_receipt_path",
        "preparation_verification_receipt_path", "preparation_command_environment",
        "preparation_command_policy",
        "process_a_output", "process_a_root", "process_a_start_claim",
        "process_a_validation_receipt", "process_a_validator_claim", "process_b_output",
        "process_b_root", "process_b_start_claim", "process_b_validation_receipt",
        "process_b_validator_claim", "process_labels", "producer_argv", "reconstructor_argv",
        "registered_start_count", "remote_claim_linux_path", "remote_claim_windows_path",
        "remote_policy", "remote_receipt_linux_path", "remote_receipt_windows_path",
        "remote_supervisor_argv", "remote_supervisor_receipt_linux_path",
        "remote_supervisor_receipt_windows_path", "remote_verifier_claim_linux_path",
        "remote_verifier_claim_windows_path", "remote_verifier_argv",
        "result_document_contract", "result_git_environment", "result_git_max_attempts",
        "result_git_owner_path", "result_git_work_root", "result_publisher_argv",
        "result_ref_transaction", "scientific_argv_template", "test_argvs",
        "third_start_allowed", "wall_time_seconds", "windows_repository_contract",
    }
    if set(contract) != expected_keys:
        raise ReconstructionError("execution contract does not have the exact frozen key set")
    return contract


def _copy_json(value: object) -> object:
    return json.loads(canonical_json_bytes(value))


def _assemble_registration(
    preregistration_tree: list[dict[str, object]],
    added_manifest: list[dict[str, object]],
    added_blobs: Mapping[str, bytes],
    anchors: Mapping[str, object],
) -> dict[str, object]:
    document = next(
        (entry for entry in preregistration_tree if entry.get("path") == PREREGISTRATION_DOCUMENT),
        None,
    )
    if document is None:
        raise ReconstructionError("P8 document is absent from its tree manifest")
    if (
        document.get("git_blob_sha1") != PREREGISTRATION_DOCUMENT_BLOB
        or document.get("sha256") != PREREGISTRATION_DOCUMENT_SHA256
        or document.get("byte_count") != PREREGISTRATION_DOCUMENT_BYTE_COUNT
    ):
        raise ReconstructionError("P8 document identity differs from the frozen amendment")
    source_manifest: dict[str, object] = {
        "preregistration_tree": preregistration_tree,
        "open_freeze_added_files": added_manifest,
    }
    source_manifest["manifest_sha256"] = canonical_sha256(source_manifest)
    v7 = cast(Mapping[str, object], anchors["v7_registration"])
    required_v7 = {
        "v6_negative", "platform", "dependencies", "scene_inventory", "row_inventory",
        "transform_contracts", "scientific_contract", "resource_contract",
    }
    if not required_v7 <= set(v7):
        raise ReconstructionError("frozen v7 registration lacks an inherited contract")
    platform_contract = _copy_json(v7["platform"])
    dependencies = _copy_json(v7["dependencies"])
    scene_inventory = _copy_json(v7["scene_inventory"])
    row_inventory = _copy_json(v7["row_inventory"])
    transforms = _copy_json(v7["transform_contracts"])
    resource = _copy_json(v7["resource_contract"])
    scientific_value = _copy_json(v7["scientific_contract"])
    if not isinstance(scientific_value, dict) or "audit_source_transformation" in scientific_value:
        raise ReconstructionError("frozen v7 scientific contract is not the expected base object")
    scientific_value["audit_source_transformation"] = _audit_transformation(
        anchors, added_manifest, added_blobs
    )
    without: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "treatment_id": TREATMENT_ID,
        "diagnostic_system_id": DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": COMPARISON_SEMANTICS_ID,
        "runtime_id": None,
        "preregistration": {
            "commit_sha": PREREGISTRATION_COMMIT,
            "tag": PREREGISTRATION_TAG,
            "document_path": PREREGISTRATION_DOCUMENT,
            "document_git_blob_sha1": PREREGISTRATION_DOCUMENT_BLOB,
            "document_sha256": PREREGISTRATION_DOCUMENT_SHA256,
        },
        "v6_negative": _copy_json(v7["v6_negative"]),
        "platform": platform_contract,
        "dependencies": dependencies,
        "source_manifest": source_manifest,
        "scene_inventory": scene_inventory,
        "row_inventory": row_inventory,
        "transform_contracts": transforms,
        "scientific_contract": scientific_value,
        "resource_contract": resource,
        "execution_contract": _execution_contract(added_manifest),
        "authorization": dict(AUTHORIZATION),
    }
    if len(without) != 18 or set(without) != TOP_LEVEL_KEYS - {"content_sha256"}:
        raise ReconstructionError("registration preimage does not have exactly the frozen eighteen keys")
    result = dict(without)
    result["content_sha256"] = canonical_sha256(without)
    return result


def _reconstruct_with_identity(
    repository_root: str | Path,
) -> tuple[dict[str, object], str, str]:
    root = Path(repository_root).resolve(strict=True)
    phase, head, authoritative_entries = _resolve_phase(root)
    p_entries = _tree_entries(root, PREREGISTRATION_COMMIT)
    p_manifest, _p_blobs = _manifest_and_blobs(root, p_entries)
    added_manifest, added_blobs = _manifest_for_paths(
        root, authoritative_entries, NON_REGISTRATION_ADDITIONS
    )
    anchors = _verify_frozen_anchors(root)
    registration = _assemble_registration(p_manifest, added_manifest, added_blobs, anchors)
    return registration, phase, head


def reconstruct_registration(repository_root: str | Path) -> tuple[dict[str, object], bool]:
    """Reconstruct the expected registration and report a clean O8 phase."""

    registration, phase, _head = _reconstruct_with_identity(repository_root)
    return registration, phase == "open_freeze"


def build_registration(repository_root: str | Path) -> dict[str, object]:
    """Build in memory only while the exact fourteen pre-registration additions are staged."""

    root = Path(repository_root).resolve(strict=True)
    registration, phase, _head = _reconstruct_with_identity(root)
    if phase != "pre_open_freeze":
        raise ReconstructionError("registration production is allowed only before O8")
    cached = _git(
        root, "diff", "--cached", "--name-status", "--no-renames", "-z", PREREGISTRATION_COMMIT
    )
    if cached != _expected_name_status(NON_REGISTRATION_ADDITIONS):
        raise ReconstructionError("registration must be generated after exactly the other fourteen additions are staged")
    output = root / REGISTRATION_PATH
    if output.exists() or output.is_symlink():
        raise ReconstructionError("registration output already exists and is never overwritten")
    return registration


def _canonical_registration_file(
    root: Path, registration_path: str | Path
) -> tuple[dict[str, object], bytes, str, str]:
    supplied_path = Path(registration_path)
    if supplied_path.is_absolute() or supplied_path.as_posix() != REGISTRATION_PATH:
        raise ReconstructionError("registration path is not the canonical plain repository file")
    candidate = root / REGISTRATION_PATH
    raw = _read_regular_nofollow(candidate, "registration", maximum=67_108_864)
    supplied = strict_object(raw, "registration")
    if set(supplied) != TOP_LEVEL_KEYS:
        raise ReconstructionError("registration does not have exactly nineteen top-level keys")
    content = _hex(supplied.get("content_sha256"), 64, "registration content SHA-256")
    preimage = dict(supplied)
    preimage.pop("content_sha256")
    if canonical_sha256(preimage) != content:
        raise ReconstructionError("registration content hash does not bind the other eighteen keys")
    return supplied, raw, content, hashlib.sha256(raw).hexdigest()


def verify_registration(
    repository_root: str | Path, registration_path: str | Path
) -> dict[str, object]:
    root = Path(repository_root).resolve(strict=True)
    supplied, raw, _content, _file_sha = _canonical_registration_file(root, registration_path)
    expected, phase, head = _reconstruct_with_identity(root)
    if raw != canonical_json_bytes(expected) or supplied != expected:
        raise ReconstructionError("registration bytes differ from independent reconstruction")
    entries = _index_entries(root)
    lookup = {entry[0]: entry for entry in entries}
    registration_entry = lookup.get(REGISTRATION_PATH)
    if registration_entry is not None:
        _manifest, blobs = _manifest_for_paths(root, entries, (REGISTRATION_PATH,))
        if blobs[REGISTRATION_PATH] != raw:
            raise ReconstructionError("registration worktree bytes differ from its stage-zero Git blob")
    if phase == "open_freeze":
        tree_entry, blob = _blob_at(root, head, REGISTRATION_PATH)
        if blob != raw or tree_entry.get("sha256") != hashlib.sha256(raw).hexdigest():
            raise ReconstructionError("registration bytes differ from the O8 tree object")
    return supplied


def verification_record(
    registration: Mapping[str, object], open_freeze_commit_sha: str
) -> dict[str, object]:
    raw = canonical_json_bytes(registration)
    return {
        "schema_version": "action-qbc-v8-open-registration-verification-v1",
        "status": "verified",
        "open_freeze_commit_sha": _hex(open_freeze_commit_sha, 40, "O8 commit"),
        "open_freeze_tag": OPEN_FREEZE_TAG,
        "registration_content_sha256": _hex(
            registration.get("content_sha256"), 64, "registration content SHA-256"
        ),
        "registration_file_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_sha256": _hex(
            cast(Mapping[str, object], registration["source_manifest"]).get("manifest_sha256"),
            64,
            "source manifest SHA-256",
        ),
    }


def _raw_tree_audit(root: Path, commit: str) -> tuple[str, str]:
    entries = _tree_entries(root, commit)
    tree_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    for (path_text, mode, oid, _size), blob in zip(entries, _batch_blobs(root, entries), strict=True):
        path = root / Path(path_text)
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ReconstructionError(f"tracked checkout path is absent: {path_text}") from error
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise ReconstructionError(f"tracked checkout path is not a plain file: {path_text}")
        actual = _read_regular_nofollow(path, f"tracked checkout path {path_text}")
        if actual != blob:
            raise ReconstructionError(f"raw checkout bytes differ from Git blob: {path_text}")
        tree_row: dict[str, object] = {
            "mode": mode,
            "path": path_text,
            "git_blob_sha1": oid,
        }
        tree_rows.append(tree_row)
        raw_rows.append(
            {
                **tree_row,
                "sha256": hashlib.sha256(actual).hexdigest(),
                "size_bytes": len(actual),
            }
        )
    return canonical_sha256(tree_rows), canonical_sha256(raw_rows)


def _verify_linux_host(registration: Mapping[str, object]) -> None:
    if os.name != "posix" or platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ReconstructionError("open-freeze verification requires registered Linux x86_64")
    execution = cast(Mapping[str, object], registration["execution_contract"])
    linux = cast(Mapping[str, object], execution["linux_platform"])
    if platform.release() != linux.get("kernel"):
        raise ReconstructionError("Linux kernel differs from the registered WSL identity")
    tools = cast(Sequence[Mapping[str, object]], execution["linux_tool_identities"])
    for tool in tools:
        path = Path(cast(str, tool["path"]))
        try:
            resolved = path.resolve(strict=True)
            raw = _read_regular_nofollow(resolved, f"registered Linux tool {path}")
        except OSError as error:
            raise ReconstructionError(f"registered Linux tool is absent: {path}") from error
        if hashlib.sha256(raw).hexdigest() != tool.get("sha256"):
            raise ReconstructionError(f"registered Linux tool identity mismatch: {path}")


def verify_open_freeze(
    repository_root: str | Path, registration_path: str | Path
) -> dict[str, object]:
    root = Path(repository_root).resolve(strict=True)
    registration = verify_registration(root, registration_path)
    _expected, phase, head = _reconstruct_with_identity(root)
    if phase != "open_freeze":
        raise ReconstructionError("--verify-open-freeze requires the clean tagged O8 checkout")
    _raw_tree_audit(root, head)
    _verify_linux_host(registration)
    return verification_record(registration, head)


_PREPARATION_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "attempts", "authority", "process_a", "process_b",
        "command_ledger", "commands_sha256", "command_environment_sha256", "status",
    }
)
_CLONE_KEYS: Final = frozenset(
    {
        "root", "root_device", "root_inode", "root_owner_uid", "root_mode", "head_sha",
        "tree_sha256", "raw_materialization_sha256", "git_status_sha256", "python_version",
        "uv_version", "environment_inventory", "environment_inventory_sha256",
        "venv_materialization_sha256", "venv_python_sha256", "passes",
    }
)
_VERIFICATION_CLONE_KEYS: Final = _CLONE_KEYS - {"environment_inventory"}
_COMMAND_LEDGER_KEYS: Final = frozenset(
    {
        "sequence_index", "attempt_index", "label", "phase", "cwd", "argv",
        "argv_sha256", "stdin_size_bytes", "stdin_sha256", "started", "exit_code",
        "outcome", "timed_out", "duration_milliseconds", "stdout_size_bytes",
        "stdout_sha256", "stderr_size_bytes", "stderr_sha256", "child_cleanup_passes",
    }
)
_VERIFICATION_RECEIPT_KEYS: Final = frozenset(
    {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "preparation_receipt_sha256",
        "verification_argv_sha256", "authority", "process_a", "process_b", "status",
        "content_sha256",
    }
)
_ATTEMPT_KEYS: Final = frozenset(
    {"attempt_index", "process_a_stage", "process_b_stage", "cleanup", "promotion", "passes"}
)
_CLEANUP_KEYS: Final = frozenset({"owned_paths", "removed", "passes"})
_PROMOTION_KEYS: Final = frozenset(
    {"source_path", "destination_path", "source_device", "source_inode", "passes"}
)
_PROCESS_STAGES: Final = frozenset(
    {"not_started", "clone_failed", "raw_audit_failed", "environment_failed", "preflight_failed", "completed"}
)
_COMMAND_PHASES: Final = frozenset(
    {"clone", "git_config", "checkout", "raw_audit", "environment_build", "preflight"}
)
_COMMAND_OUTCOMES: Final = frozenset(
    {"completed", "nonzero", "timeout", "stdout_limit", "stderr_limit", "spawn_error", "stdin_limit"}
)
_EXPECTED_DISTRIBUTIONS: Final = {
    "arc3-crosslevel-voi": "0.1.0",
    "numpy": "2.5.1",
    "pyyaml": "6.0.3",
}


def _exact_keys(value: object, expected: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReconstructionError(f"{label} does not have its exact key set")
    return cast(Mapping[str, object], value)


def _nonnegative_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReconstructionError(f"{label} is not a nonnegative integer")
    return value


def _strict_utf8(value: str, label: str) -> bytes:
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ReconstructionError(f"{label} is not strict UTF-8") from error


def _directory_identity(path: Path, label: str, *, empty: bool = False) -> dict[str, int]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ReconstructionError(f"{label} is not an openable no-follow directory") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise ReconstructionError(f"{label} is not an owner-controlled mode-0700 directory")
        if empty and os.listdir(descriptor):
            raise ReconstructionError(f"{label} is not empty")
        return {
            "root_device": metadata.st_dev,
            "root_inode": metadata.st_ino,
            "root_owner_uid": metadata.st_uid,
            "root_mode": stat.S_IMODE(metadata.st_mode),
        }
    finally:
        os.close(descriptor)


def _open_directory_beneath(root_descriptor: int, parts: Sequence[str], label: str) -> int:
    descriptor = os.dup(root_descriptor)
    try:
        for part in parts:
            if not part or part in {".", ".."} or "/" in part or "\\" in part or "\x00" in part:
                raise ReconstructionError(f"{label} has an unsafe path component")
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_beneath(
    root_descriptor: int,
    parts: Sequence[str],
    label: str,
    *,
    maximum: int = 536_870_912,
) -> bytes:
    if not parts:
        raise ReconstructionError(f"{label} has no file component")
    parent = _open_directory_beneath(root_descriptor, parts[:-1], label)
    try:
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
    except BaseException:
        os.close(parent)
        raise
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > maximum:
            raise ReconstructionError(f"{label} is not a bounded regular file")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino, before.st_uid, before.st_mode, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_uid, after.st_mode, after.st_size, after.st_mtime_ns)
            or len(raw) != before.st_size
            or len(raw) > maximum
        ):
            raise ReconstructionError(f"{label} changed during its bounded read")
        return raw
    finally:
        os.close(descriptor)
        os.close(parent)


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _normalized_record_parts(raw_name: str, label: str) -> tuple[str, ...]:
    _strict_utf8(raw_name, label)
    if not raw_name or "\\" in raw_name or "\x00" in raw_name or raw_name.startswith("/"):
        raise ReconstructionError(f"{label} is not a safe relative RECORD name")
    raw_parts = raw_name.split("/")
    if any(part in {"", "."} for part in raw_parts):
        raise ReconstructionError(f"{label} has an empty or dot component")
    normalized = ["lib", "python3.12", "site-packages"]
    for part in raw_parts:
        if part == "..":
            if not normalized:
                raise ReconstructionError(f"{label} escapes the virtual environment")
            normalized.pop()
        else:
            normalized.append(part)
    if not normalized or any(part in {"", ".", ".."} for part in normalized):
        raise ReconstructionError(f"{label} has an invalid normalized path")
    normalized_text = "/".join(normalized)
    if PurePosixPath(normalized_text).is_absolute() or "\\" in normalized_text:
        raise ReconstructionError(f"{label} has an invalid normalized path")
    _strict_utf8(normalized_text, f"normalized {label}")
    return tuple(normalized)


def _environment_inventory(root: Path) -> list[dict[str, object]]:
    venv_path = root / ".venv"
    try:
        venv_descriptor = os.open(
            venv_path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as error:
        raise ReconstructionError("virtual environment is not a no-follow directory") from error
    try:
        site_descriptor = _open_directory_beneath(
            venv_descriptor,
            ("lib", "python3.12", "site-packages"),
            "virtual-environment site-packages",
        )
        try:
            entries = sorted(
                os.scandir(site_descriptor),
                key=lambda entry: _strict_utf8(entry.name, "site-packages entry"),
            )
            dist_names: list[str] = []
            for entry in entries:
                _strict_utf8(entry.name, "site-packages entry")
                if not entry.name.endswith(".dist-info"):
                    continue
                metadata = entry.stat(follow_symlinks=False)
                if not stat.S_ISDIR(metadata.st_mode) or entry.is_symlink():
                    raise ReconstructionError("distribution metadata is not a plain directory")
                dist_names.append(entry.name)
        finally:
            os.close(site_descriptor)

        compact: list[dict[str, object]] = []
        seen_names: set[str] = set()
        seen_paths: set[str] = set()
        for dist_name in dist_names:
            prefix = ("lib", "python3.12", "site-packages", dist_name)
            metadata_raw = _read_regular_beneath(
                venv_descriptor,
                (*prefix, "METADATA"),
                f"{dist_name}/METADATA",
            )
            try:
                metadata_message = BytesParser(policy=email.policy.compat32).parsebytes(metadata_raw)
            except (TypeError, ValueError) as error:
                raise ReconstructionError(f"cannot parse {dist_name}/METADATA") from error
            name_header = metadata_message.get("Name")
            version_header = metadata_message.get("Version")
            if not isinstance(name_header, str) or not isinstance(version_header, str):
                raise ReconstructionError(f"distribution metadata lacks Name/Version: {dist_name}")
            normalized_name = _normalize_distribution_name(name_header.strip())
            version = version_header.strip()
            if (
                not normalized_name
                or not version
                or any(ord(character) > 127 for character in normalized_name + version)
                or normalized_name in seen_names
            ):
                raise ReconstructionError(f"distribution name/version is invalid: {dist_name}")
            seen_names.add(normalized_name)
            record_raw = _read_regular_beneath(
                venv_descriptor,
                (*prefix, "RECORD"),
                f"{dist_name}/RECORD",
            )
            try:
                rows = list(csv.reader(io.StringIO(record_raw.decode("utf-8", errors="strict"), newline="")))
            except (UnicodeDecodeError, csv.Error) as error:
                raise ReconstructionError(f"cannot parse {dist_name}/RECORD") from error
            file_rows: list[dict[str, object]] = []
            distribution_paths: set[str] = set()
            for index, row in enumerate(rows):
                if len(row) != 3 or not row[0]:
                    raise ReconstructionError(f"invalid RECORD row {index} for {dist_name}")
                parts = _normalized_record_parts(row[0], f"{dist_name} RECORD row {index}")
                path_text = "/".join(parts)
                if path_text in distribution_paths or path_text in seen_paths:
                    raise ReconstructionError(f"duplicate normalized RECORD path: {path_text}")
                distribution_paths.add(path_text)
                seen_paths.add(path_text)
                raw = _read_regular_beneath(
                    venv_descriptor,
                    parts,
                    f"RECORD target {path_text}",
                )
                file_rows.append(
                    {
                        "path": path_text,
                        "size_bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
            file_rows.sort(key=lambda row: _strict_utf8(cast(str, row["path"]), "RECORD path"))
            compact.append(
                {
                    "normalized_name": normalized_name,
                    "version": version,
                    "file_count": len(file_rows),
                    "files_sha256": canonical_sha256(file_rows),
                }
            )
        compact.sort(
            key=lambda row: _strict_utf8(cast(str, row["normalized_name"]), "distribution name")
        )
        if {cast(str, row["normalized_name"]): row["version"] for row in compact} != _EXPECTED_DISTRIBUTIONS:
            raise ReconstructionError("installed distributions differ from the frozen runtime lock")
        return compact
    finally:
        os.close(venv_descriptor)


def _venv_materialization_sha256(root: Path) -> str:
    venv_path = root / ".venv"
    try:
        root_descriptor = os.open(
            venv_path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as error:
        raise ReconstructionError("virtual environment is not a no-follow directory") from error
    rows: list[dict[str, object]] = []

    def visit(descriptor: int, prefix: str) -> None:
        entries = sorted(
            os.scandir(descriptor),
            key=lambda entry: _strict_utf8(entry.name, "venv entry"),
        )
        for entry in entries:
            name = entry.name
            _strict_utf8(name, "venv entry")
            if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
                raise ReconstructionError("virtual environment contains an unsafe entry name")
            relative = f"{prefix}/{name}" if prefix else name
            metadata = entry.stat(follow_symlinks=False)
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISDIR(metadata.st_mode):
                rows.append(
                    {
                        "path": relative,
                        "type": "directory",
                        "mode": mode,
                        "size_bytes": None,
                        "sha256": None,
                        "symlink_target": None,
                    }
                )
                child = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=descriptor,
                )
                try:
                    visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                raw = _read_regular_beneath(descriptor, (name,), f"venv entry {relative}")
                rows.append(
                    {
                        "path": relative,
                        "type": "regular",
                        "mode": mode,
                        "size_bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "symlink_target": None,
                    }
                )
            elif stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(name, dir_fd=descriptor)
                _strict_utf8(target, f"venv symlink target {relative}")
                rows.append(
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
                raise ReconstructionError(f"virtual environment contains a special file: {relative}")

    try:
        visit(root_descriptor, "")
    finally:
        os.close(root_descriptor)
    rows.sort(key=lambda row: _strict_utf8(cast(str, row["path"]), "venv path"))
    if len({cast(str, row["path"]) for row in rows}) != len(rows):
        raise ReconstructionError("virtual environment inventory has duplicate paths")
    return canonical_sha256(rows)


def _resolved_venv_python_sha256(root: Path) -> str:
    candidate = root / ".venv" / "bin" / "python3"
    seen: set[Path] = set()
    for _ in range(40):
        absolute = Path(os.path.abspath(candidate))
        if absolute in seen:
            raise ReconstructionError("virtual-environment Python symlink chain loops")
        seen.add(absolute)
        try:
            metadata = absolute.lstat()
        except OSError as error:
            raise ReconstructionError("virtual-environment Python link chain is absent") from error
        if stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(absolute)
            _strict_utf8(target, "virtual-environment Python symlink target")
            candidate = Path(target) if os.path.isabs(target) else absolute.parent / target
            continue
        if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o111:
            raise ReconstructionError("resolved virtual-environment Python is not regular")
        raw = _read_regular_nofollow(absolute, "resolved virtual-environment Python", maximum=1 << 30)
        return hashlib.sha256(raw).hexdigest()
    raise ReconstructionError("virtual-environment Python symlink chain is too deep")


def _run_identity_command(argv: Sequence[str], cwd: Path, label: str) -> bytes:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(PREPARATION_COMMAND_ENVIRONMENT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=PREPARATION_COMMAND_POLICY["default_timeout_seconds"],
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReconstructionError(f"{label} command could not complete") from error
    if completed.returncode != 0 or completed.stderr:
        raise ReconstructionError(f"{label} command returned nonzero output")
    if len(completed.stdout) > PREPARATION_COMMAND_POLICY["stdout_cap_bytes"]:
        raise ReconstructionError(f"{label} stdout exceeds the registered cap")
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
        except OSError as error:
            raise ReconstructionError(
                "clone object-pack directory is unavailable as a no-follow directory"
            ) from error

        for descriptor in descriptors:
            try:
                metadata = os.fstat(descriptor)
            except OSError as error:
                raise ReconstructionError(
                    "cannot inspect clone object-pack directory ancestry"
                ) from error
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                raise ReconstructionError(
                    "clone object-pack directory ancestry is not owner-controlled"
                )

        try:
            with os.scandir(pack_descriptor) as entries:
                for entry in entries:
                    if entry.name.endswith(".promisor"):
                        raise ReconstructionError(
                            "clone contains a forbidden promisor object-pack sidecar"
                        )
        except OSError as error:
            raise ReconstructionError(
                "cannot inspect clone object-pack directory"
            ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _validate_git_isolation(root: Path, open_commit: str) -> None:
    _validate_object_pack_sources(root)
    if _git(root, "cat-file", "-t", f"refs/tags/{OPEN_FREEZE_TAG}") != b"commit\n":
        raise ReconstructionError("clone O8 tag is absent or annotated")
    if _git(root, "rev-parse", f"refs/tags/{OPEN_FREEZE_TAG}") != f"{open_commit}\n".encode("ascii"):
        raise ReconstructionError("clone O8 tag resolves to the wrong commit")
    if _git(root, "rev-parse", "HEAD") != f"{open_commit}\n".encode("ascii"):
        raise ReconstructionError("clone HEAD differs from O8")
    names_raw = _git(root, "config", "--local", "--name-only", "--null", "--list")
    names = [item.decode("utf-8", errors="strict") for item in names_raw.split(b"\0") if item]
    expected = {
        "core.repositoryformatversion": "0",
        "core.filemode": "true",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "core.autocrlf": "false",
        "core.eol": "lf",
        "core.safecrlf": "true",
    }
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise ReconstructionError("clone local Git configuration has an extra or duplicate key")
    for key, expected_value in expected.items():
        raw = _git(root, "config", "--local", "--null", "--get-all", key)
        values = [item.decode("utf-8", errors="strict") for item in raw.split(b"\0") if item]
        if values != [expected_value]:
            raise ReconstructionError(f"clone local Git configuration differs: {key}")
    git_path = root / ".git"
    try:
        git_descriptor = os.open(
            git_path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as error:
        raise ReconstructionError("clone .git is not a no-follow directory") from error
    try:
        metadata = os.fstat(git_descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise ReconstructionError("clone .git is not owner-controlled")
    finally:
        os.close(git_descriptor)
    forbidden = (
        ".git/objects/info/alternates",
        ".git/objects/info/http-alternates",
        ".git/info/grafts",
        ".git/shallow",
    )
    for relative in forbidden:
        candidate = root / relative
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ReconstructionError(f"cannot establish absence of {relative}") from error
        raise ReconstructionError(f"clone contains forbidden Git state: {relative}")
    if _git(root, "for-each-ref", "--format=%(refname)", "refs/replace/"):
        raise ReconstructionError("clone contains replacement refs")
    hooks = root / ".git" / "hooks"
    try:
        hook_entries = list(os.scandir(hooks))
    except FileNotFoundError:
        hook_entries = []
    except OSError as error:
        raise ReconstructionError("cannot inspect clone hooks directory") from error
    for entry in hook_entries:
        metadata = entry.stat(follow_symlinks=False)
        if entry.is_symlink() or not stat.S_ISREG(metadata.st_mode) or not entry.name.endswith(".sample"):
            raise ReconstructionError("clone contains an active or unsafe Git hook")


def _plain_directory(path: Path, label: str, *, empty: bool = False) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReconstructionError(f"{label} directory is absent") from error
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise ReconstructionError(f"{label} is not a plain directory")
    current_uid = Path("/proc/self").stat().st_uid if os.name == "posix" else -1
    if os.name == "posix" and (
        stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != current_uid
    ):
        raise ReconstructionError(f"{label} is not owner-controlled mode 0700")
    if empty and any(path.iterdir()):
        raise ReconstructionError(f"{label} is not empty")
    return metadata


_COMMAND_IDENTITY_KEYS: Final = frozenset(
    {
        "attempt_index", "label", "phase", "cwd", "argv", "argv_sha256",
        "stdin_size_bytes", "stdin_sha256",
    }
)


def _command_identity(
    *,
    attempt_index: int | None,
    label: str,
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
    entries: Sequence[tuple[str, str, str, int | None]],
    *,
    attempt_index: int,
    label: str,
) -> list[dict[str, object]]:
    git_prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(root)]
    request = b"".join(entry[2].encode("ascii") + b"\n" for entry in entries)
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
    execution: Mapping[str, object],
    execution_root: Path,
    attempt_index: int,
    open_commit: str,
    entries: Sequence[tuple[str, str, str, int | None]],
) -> list[dict[str, object]]:
    source = execution_root / f".prepare-attempt-{attempt_index}"
    environment_argv = execution.get("environment_build_argv")
    preflight_argvs = execution.get("preflight_argvs")
    if (
        not isinstance(environment_argv, list)
        or not all(isinstance(item, str) for item in environment_argv)
        or not isinstance(preflight_argvs, list)
        or len(preflight_argvs) != 5
        or not all(
            isinstance(argv, list)
            and argv
            and all(isinstance(item, str) for item in argv)
            for argv in preflight_argvs
        )
    ):
        raise ReconstructionError("registered preparation command arrays are invalid")
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
                    "--no-checkout", "--branch", OPEN_FREEZE_TAG, "--single-branch",
                    PREPARATION_SOURCE_URL, str(root),
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
            [*git_prefix, "cat-file", "-t", f"refs/tags/{OPEN_FREEZE_TAG}"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*git_prefix, "rev-parse", f"refs/tags/{OPEN_FREEZE_TAG}"],
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
        append(label, "environment_build", root, cast(list[str], environment_argv))
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
        for argv in cast(list[list[str]], preflight_argvs):
            append(label, "preflight", root, argv)
    if len(result) != 54:
        raise ReconstructionError("internal preparation command plan is not 54 rows")
    return result


def _expected_authority_identities(
    authority_root: Path,
    open_commit: str,
    entries: Sequence[tuple[str, str, str, int | None]],
) -> list[dict[str, object]]:
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(authority_root)]
    commands: list[tuple[str, list[str], bytes]] = []

    def append(phase: str, arguments: Sequence[str], stdin_bytes: bytes = b"") -> None:
        commands.append((phase, [*prefix, *arguments], stdin_bytes))

    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{PREREGISTRATION_V1_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{PREREGISTRATION_V1_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", PREREGISTRATION_V1_COMMIT])
    append(
        "raw_audit",
        ["diff", "--name-status", "--no-renames", "-z", R7_COMMIT, PREREGISTRATION_V1_COMMIT],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{PREREGISTRATION_V2_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{PREREGISTRATION_V2_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", PREREGISTRATION_V2_COMMIT])
    append(
        "raw_audit",
        [
            "diff", "--name-status", "--no-renames", "-z",
            PREREGISTRATION_V1_COMMIT, PREREGISTRATION_V2_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{PREREGISTRATION_V3_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{PREREGISTRATION_V3_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", PREREGISTRATION_V3_COMMIT])
    append(
        "raw_audit",
        [
            "diff", "--name-status", "--no-renames", "-z",
            PREREGISTRATION_V2_COMMIT, PREREGISTRATION_V3_COMMIT,
        ],
    )
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{PREREGISTRATION_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{PREREGISTRATION_TAG}"])
    append("raw_audit", ["rev-list", "--parents", "-n", "1", PREREGISTRATION_COMMIT])
    append(
        "raw_audit",
        [
            "diff", "--name-status", "--no-renames", "-z",
            PREREGISTRATION_V3_COMMIT, PREREGISTRATION_COMMIT,
        ],
    )
    append(
        "raw_audit",
        ["ls-tree", "-z", PREREGISTRATION_COMMIT, "--", PREREGISTRATION_DOCUMENT],
    )
    append(
        "raw_audit",
        ["cat-file", "blob", f"{PREREGISTRATION_COMMIT}:{PREREGISTRATION_DOCUMENT}"],
    )
    append("raw_audit", ["rev-list", "--parents", "-n", "1", open_commit])
    append(
        "raw_audit",
        ["diff", "--name-status", "--no-renames", "-z", PREREGISTRATION_COMMIT, open_commit],
    )
    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append(
        "raw_audit",
        ["ls-tree", "-r", "-l", "-z", "--full-tree", open_commit],
    )
    request = b"".join(entry[2].encode("ascii") + b"\n" for entry in entries)
    append("raw_audit", ["cat-file", "--batch"], request)
    append("raw_audit", ["ls-files", "--stage", "-z"])
    append(
        "raw_audit",
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )
    return [
        _command_identity(
            attempt_index=None,
            label="authority",
            phase=phase,
            cwd=authority_root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _git_subcommand(argv: Sequence[str]) -> str | None:
    if len(argv) < 3 or argv[:2] != ["/usr/bin/git", "--no-replace-objects"]:
        return None
    offset = 2
    if len(argv) > offset + 1 and argv[offset] == "-C":
        offset += 2
    if offset >= len(argv):
        return None
    while offset + 1 < len(argv) and argv[offset] == "-c":
        offset += 2
    return argv[offset] if offset < len(argv) else None


def _validate_ledger_argv(
    row: Mapping[str, object],
    execution: Mapping[str, object],
    execution_root: Path,
) -> None:
    argv_value = row.get("argv")
    if (
        not isinstance(argv_value, list)
        or not argv_value
        or not all(isinstance(item, str) and item for item in argv_value)
    ):
        raise ReconstructionError("preparation command ledger argv is not a nonempty string array")
    argv = cast(list[str], argv_value)
    if row.get("argv_sha256") != canonical_sha256(argv):
        raise ReconstructionError("preparation command ledger argv hash mismatch")
    phase = row.get("phase")
    label = row.get("label")
    attempt_index = row.get("attempt_index")
    subcommand = _git_subcommand(argv)
    allowed_raw_git = {
        "cat-file", "config", "diff", "for-each-ref", "ls-files", "ls-tree", "rev-list",
        "rev-parse", "status",
    }
    if phase == "clone":
        if subcommand != "clone" or label not in {"A", "B"}:
            raise ReconstructionError("preparation clone ledger row has an invented argv")
    elif phase == "git_config":
        if subcommand not in {"config", "remote"} or label not in {"A", "B", "authority"}:
            raise ReconstructionError("preparation Git-config ledger row has an invented argv")
    elif phase == "checkout":
        if subcommand != "checkout" or label not in {"A", "B"}:
            raise ReconstructionError("preparation checkout ledger row has an invented argv")
    elif phase == "raw_audit":
        if subcommand not in allowed_raw_git:
            raise ReconstructionError("preparation raw-audit ledger row has an invented argv")
    elif phase == "environment_build":
        if argv != execution.get("environment_build_argv") or label not in {"A", "B"}:
            raise ReconstructionError("preparation environment-build ledger row has an invented argv")
    elif phase == "preflight":
        preflights = execution.get("preflight_argvs")
        if not isinstance(preflights, list) or argv not in preflights or label not in {"A", "B"}:
            raise ReconstructionError("preparation preflight ledger row has an invented argv")
    else:
        raise ReconstructionError("preparation command ledger has an unknown phase")
    cwd = row.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise ReconstructionError("preparation command ledger cwd is not absolute")
    if attempt_index is None:
        if label not in {"authority", None} or Path(cwd) != Path(cast(str, execution["authority_root"])):
            raise ReconstructionError("authority-wide command ledger row has the wrong label/cwd")
    else:
        attempt = _nonnegative_integer(attempt_index, "preparation ledger attempt index")
        if attempt not in {1, 2} or label not in {"A", "B"}:
            raise ReconstructionError("attempt-owned command ledger row has the wrong label")
        expected_stage = execution_root / f".prepare-attempt-{attempt}"
        try:
            Path(cwd).relative_to(expected_stage)
        except ValueError as error:
            raise ReconstructionError("attempt-owned command ledger cwd escapes its stage") from error


def _validate_command_ledger(
    receipt: Mapping[str, object],
    execution: Mapping[str, object],
    execution_root: Path,
    attempt_count: int,
) -> None:
    ledger_value = receipt.get("command_ledger")
    if not isinstance(ledger_value, list) or not ledger_value:
        raise ReconstructionError("preparation command ledger is not a nonempty array")
    if receipt.get("commands_sha256") != canonical_sha256(ledger_value):
        raise ReconstructionError("preparation command ledger SHA-256 mismatch")
    environment = execution.get("preparation_command_environment")
    if environment != PREPARATION_COMMAND_ENVIRONMENT:
        raise ReconstructionError("registered preparation command environment differs")
    if receipt.get("command_environment_sha256") != canonical_sha256(environment):
        raise ReconstructionError("preparation command environment SHA-256 mismatch")
    previous_attempt = 0
    terminal_attempts: set[int] = set()
    attempt_shapes: dict[int, list[tuple[object, object]]] = {
        index: [] for index in range(1, attempt_count + 1)
    }
    attempt_rows: dict[int, list[Mapping[str, object]]] = {
        index: [] for index in range(1, attempt_count + 1)
    }
    authority_rows: list[Mapping[str, object]] = []
    for sequence_index, item in enumerate(ledger_value):
        row = _exact_keys(item, _COMMAND_LEDGER_KEYS, f"preparation command {sequence_index}")
        if row.get("sequence_index") != sequence_index:
            raise ReconstructionError("preparation command indices are not contiguous from zero")
        attempt_raw = row.get("attempt_index")
        if attempt_raw is None:
            if previous_attempt:
                raise ReconstructionError("authority-wide command appears after an attempt command")
            authority_rows.append(row)
        else:
            attempt = _nonnegative_integer(attempt_raw, "preparation command attempt index")
            if (
                attempt < previous_attempt
                or attempt > previous_attempt + 1
                or attempt < 1
                or attempt > attempt_count
            ):
                raise ReconstructionError("preparation command attempts are out of order")
            if attempt in terminal_attempts:
                raise ReconstructionError("preparation command appears after a terminal command outcome")
            previous_attempt = attempt
            attempt_shapes[attempt].append((row.get("label"), row.get("phase")))
            attempt_rows[attempt].append(row)
        if row.get("phase") not in _COMMAND_PHASES:
            raise ReconstructionError("preparation command has an unknown phase")
        _validate_ledger_argv(row, execution, execution_root)
        stdin_size = _nonnegative_integer(row.get("stdin_size_bytes"), "command stdin size")
        stdout_size = _nonnegative_integer(row.get("stdout_size_bytes"), "command stdout size")
        stderr_size = _nonnegative_integer(row.get("stderr_size_bytes"), "command stderr size")
        duration = _nonnegative_integer(row.get("duration_milliseconds"), "command duration")
        _hex(row.get("stdin_sha256"), 64, "command stdin SHA-256")
        _hex(row.get("stdout_sha256"), 64, "command stdout SHA-256")
        _hex(row.get("stderr_sha256"), 64, "command stderr SHA-256")
        outcome = row.get("outcome")
        started = row.get("started")
        timed_out = row.get("timed_out")
        exit_code = row.get("exit_code")
        cleanup = row.get("child_cleanup_passes")
        if outcome not in _COMMAND_OUTCOMES or not isinstance(started, bool) or not isinstance(timed_out, bool):
            raise ReconstructionError("preparation command outcome flags are invalid")
        empty_sha = hashlib.sha256(b"").hexdigest()
        if stdin_size > PREPARATION_COMMAND_POLICY["stdin_cap_bytes"]:
            if outcome != "stdin_limit" or started or exit_code is not None or timed_out:
                raise ReconstructionError("preparation stdin-limit command classification is invalid")
        elif outcome == "stdin_limit":
            raise ReconstructionError("preparation command invents an stdin-limit outcome")
        if not started:
            if outcome not in {"spawn_error", "stdin_limit"} or exit_code is not None or timed_out or cleanup is not None:
                raise ReconstructionError("unstarted preparation command has an impossible outcome")
            if stdout_size or stderr_size or row.get("stdout_sha256") != empty_sha or row.get("stderr_sha256") != empty_sha:
                raise ReconstructionError("unstarted preparation command invents output")
        else:
            if outcome in {"spawn_error", "stdin_limit"}:
                raise ReconstructionError("started preparation command has an unstarted outcome")
            if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
                raise ReconstructionError("preparation command exit code is not an integer or null")
            if cleanup is not None and not isinstance(cleanup, bool):
                raise ReconstructionError("preparation command cleanup field is invalid")
            if outcome == "completed" and (exit_code != 0 or timed_out):
                raise ReconstructionError("completed preparation command evidence is inconsistent")
            if outcome == "nonzero" and (
                not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0 or timed_out
            ):
                raise ReconstructionError("nonzero preparation command evidence is inconsistent")
            if outcome == "timeout" and not timed_out:
                raise ReconstructionError("timeout preparation command lacks its timeout fact")
            forced = outcome in {"timeout", "stdout_limit", "stderr_limit"}
            if forced and not isinstance(cleanup, bool):
                raise ReconstructionError("forced preparation command lacks cleanup evidence")
            if receipt.get("status") == "prepared" and cleanup is False:
                raise ReconstructionError("prepared receipt records failed child cleanup")
        stdout_cap = PREPARATION_COMMAND_POLICY["stdout_cap_bytes"]
        stderr_cap = PREPARATION_COMMAND_POLICY["stderr_cap_bytes"]
        if stdout_size > stdout_cap + 1 or stderr_size > stderr_cap + 1:
            raise ReconstructionError("preparation command stream evidence exceeds cap+1")
        if outcome == "stdout_limit":
            if stdout_size != stdout_cap + 1:
                raise ReconstructionError("stdout-limit command does not bind the exact cap+1 prefix")
        elif stdout_size > stdout_cap:
            raise ReconstructionError("non-stdout-limit command exceeds the stdout cap")
        if outcome == "stderr_limit":
            if stderr_size != stderr_cap + 1 or stdout_size > stdout_cap:
                raise ReconstructionError("stderr-limit command does not bind its collision precedence")
        elif outcome == "stdout_limit":
            if stderr_size > stderr_cap + 1:
                raise ReconstructionError("stdout-limit stderr evidence exceeds cap+1")
        elif stderr_size > stderr_cap:
            raise ReconstructionError("non-stderr-limit command exceeds the stderr cap")
        if outcome == "timeout" and (stdout_size > stdout_cap or stderr_size > stderr_cap):
            raise ReconstructionError("timeout command contradicts stream-limit precedence")
        timeout_seconds = (
            PREPARATION_COMMAND_POLICY["environment_timeout_seconds"]
            if row.get("phase") == "environment_build"
            else PREPARATION_COMMAND_POLICY["default_timeout_seconds"]
        )
        if timed_out and duration < timeout_seconds * 1000:
            raise ReconstructionError("timed-out command duration precedes its registered threshold")
        if attempt_raw is None and outcome != "completed":
            raise ReconstructionError("prepared receipt has a failing authority command")
        if attempt_raw is not None and outcome != "completed":
            terminal_attempts.add(cast(int, attempt_raw))
    if previous_attempt != attempt_count:
        raise ReconstructionError("preparation command ledger omits the final attempt")
    if attempt_count in terminal_attempts:
        raise ReconstructionError("passing final preparation attempt has a terminal command outcome")
    open_commit = _hex(
        receipt.get("open_freeze_commit_sha"),
        40,
        "preparation open-freeze commit",
    )
    authority_root = Path(cast(str, execution["authority_root"]))
    entries = _tree_entries(authority_root, open_commit)
    observed_authority_identities = [
        {key: row[key] for key in _COMMAND_IDENTITY_KEYS}
        for row in authority_rows
    ]
    expected_authority_identities = _expected_authority_identities(
        authority_root,
        open_commit,
        entries,
    )
    if observed_authority_identities != expected_authority_identities:
        raise ReconstructionError(
            "preparation authority command ledger differs from exact reconstruction"
        )
    clone_plan = [
        "clone", "git_config", "git_config", "git_config", "checkout",
        "git_config", "git_config", "raw_audit", "raw_audit",
    ]
    audit_plan = ["git_config", *(["raw_audit"] * 5)]
    expected_plan = [
        *(("A", phase) for phase in clone_plan),
        *(("B", phase) for phase in clone_plan),
        *(("A", phase) for phase in audit_plan),
        *(("B", phase) for phase in audit_plan),
        ("A", "environment_build"),
        ("B", "environment_build"),
        *(("A", phase) for phase in audit_plan),
        *(("B", phase) for phase in audit_plan),
        *(("A", "preflight") for _ in range(5)),
        *(("B", "preflight") for _ in range(5)),
    ]
    for attempt, observed in attempt_shapes.items():
        if observed != expected_plan[: len(observed)]:
            raise ReconstructionError("preparation command ledger is not an allowed attempt-plan prefix")
        if attempt == attempt_count and observed != expected_plan:
            raise ReconstructionError("passing preparation attempt lacks its complete command plan")
        for label in ("A", "B"):
            registered_preflight = execution.get("preflight_argvs")
            actual_preflight = [
                row.get("argv")
                for row in attempt_rows[attempt]
                if row.get("label") == label and row.get("phase") == "preflight"
            ]
            if (
                actual_preflight
                and isinstance(registered_preflight, list)
                and actual_preflight != registered_preflight[: len(actual_preflight)]
            ):
                raise ReconstructionError("preparation preflight command order differs from registration")
        expected_rows = _expected_attempt_identities(
            execution,
            execution_root,
            attempt,
            open_commit,
            entries,
        )
        observed_identities = [
            {key: row[key] for key in _COMMAND_IDENTITY_KEYS}
            for row in attempt_rows[attempt]
        ]
        if observed_identities != expected_rows[: len(observed_identities)]:
            raise ReconstructionError(
                f"preparation attempt {attempt} contains an invented command"
            )
        if attempt == attempt_count and observed_identities != expected_rows:
            raise ReconstructionError(
                "passing preparation attempt lacks the exact complete argv plan"
            )


def _validate_clone_receipt(
    value: object,
    label: str,
    expected_root: Path,
    open_commit: str,
    *,
    environment_expected: bool,
) -> dict[str, object]:
    clone = _exact_keys(value, _CLONE_KEYS, f"preparation {label}")
    if clone.get("root") != str(expected_root) or clone.get("head_sha") != open_commit:
        raise ReconstructionError(f"preparation {label} path/HEAD identity mismatch")
    if clone.get("passes") is not True:
        raise ReconstructionError(f"preparation {label} is not passing")
    identity = _directory_identity(expected_root, f"preparation {label}")
    if any(clone.get(key) != actual for key, actual in identity.items()):
        raise ReconstructionError(f"preparation {label} root identity mismatch")
    _validate_git_isolation(expected_root, open_commit)
    tree_sha, raw_sha = _raw_tree_audit(expected_root, open_commit)
    if clone.get("tree_sha256") != tree_sha or clone.get("raw_materialization_sha256") != raw_sha:
        raise ReconstructionError(f"preparation {label} raw/tree identity mismatch")
    status_raw = _git(expected_root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status_raw != b"" or clone.get("git_status_sha256") != hashlib.sha256(status_raw).hexdigest():
        raise ReconstructionError(f"preparation {label} Git status identity mismatch")
    environment_fields = (
        "python_version", "uv_version", "environment_inventory",
        "environment_inventory_sha256", "venv_materialization_sha256", "venv_python_sha256",
    )
    verification: dict[str, object] = {
        "root": str(expected_root),
        **identity,
        "head_sha": open_commit,
        "tree_sha256": tree_sha,
        "raw_materialization_sha256": raw_sha,
        "git_status_sha256": hashlib.sha256(status_raw).hexdigest(),
        "python_version": None,
        "uv_version": None,
        "environment_inventory_sha256": None,
        "venv_materialization_sha256": None,
        "venv_python_sha256": None,
        "passes": True,
    }
    if environment_expected:
        if clone.get("python_version") != "3.12.13":
            raise ReconstructionError(f"preparation {label} Python identity mismatch")
        if clone.get("uv_version") != "0.11.28":
            raise ReconstructionError(f"preparation {label} uv identity mismatch")
        inventory = _environment_inventory(expected_root)
        inventory_sha = canonical_sha256(inventory)
        if clone.get("environment_inventory") != inventory or clone.get("environment_inventory_sha256") != inventory_sha:
            raise ReconstructionError(f"preparation {label} distribution inventory mismatch")
        materialization_sha = _venv_materialization_sha256(expected_root)
        if clone.get("venv_materialization_sha256") != materialization_sha:
            raise ReconstructionError(f"preparation {label} venv materialization mismatch")
        python_sha = _resolved_venv_python_sha256(expected_root)
        if clone.get("venv_python_sha256") != python_sha:
            raise ReconstructionError(f"preparation {label} venv Python mismatch")
        if _run_identity_command((".venv/bin/python3", "--version"), expected_root, f"{label} Python") != b"Python 3.12.13\n":
            raise ReconstructionError(f"preparation {label} Python stdout mismatch")
        if _run_identity_command(("/usr/local/bin/uv", "--version"), expected_root, f"{label} uv") != b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n":
            raise ReconstructionError(f"preparation {label} uv stdout mismatch")
        verification.update(
            {
                "python_version": "3.12.13",
                "uv_version": "0.11.28",
                "environment_inventory_sha256": inventory_sha,
                "venv_materialization_sha256": materialization_sha,
                "venv_python_sha256": python_sha,
            }
        )
    elif any(clone.get(field) is not None for field in environment_fields):
        raise ReconstructionError("authority preparation receipt invents environment fields")
    elif (expected_root / ".venv").exists() or (expected_root / ".venv").is_symlink():
        raise ReconstructionError("authority clone unexpectedly contains a virtual environment")
    _exact_keys(verification, _VERIFICATION_CLONE_KEYS, f"verification {label}")
    return verification


def _validate_attempts(attempts_value: object, execution_root: Path) -> int:
    if not isinstance(attempts_value, list) or not 1 <= len(attempts_value) <= 2:
        raise ReconstructionError("prepared receipt must contain one or two attempts")
    for offset, item in enumerate(attempts_value, start=1):
        attempt = _exact_keys(item, _ATTEMPT_KEYS, f"preparation attempt {offset}")
        if attempt.get("attempt_index") != offset:
            raise ReconstructionError("preparation attempt indices are not contiguous one-based integers")
        if attempt.get("process_a_stage") not in _PROCESS_STAGES or attempt.get("process_b_stage") not in _PROCESS_STAGES:
            raise ReconstructionError("preparation attempt has an unknown process stage")
        cleanup = _exact_keys(attempt.get("cleanup"), _CLEANUP_KEYS, f"attempt {offset} cleanup")
        promotion = _exact_keys(attempt.get("promotion"), _PROMOTION_KEYS, f"attempt {offset} promotion")
        source = execution_root / f".prepare-attempt-{offset}"
        destination = execution_root / "processes"
        if promotion.get("source_path") != str(source) or promotion.get("destination_path") != str(destination):
            raise ReconstructionError("preparation promotion paths differ from the registered attempt paths")
        owned = cleanup.get("owned_paths")
        removed = cleanup.get("removed")
        if (
            not isinstance(owned, list) or not isinstance(removed, list)
            or not all(isinstance(path, str) for path in [*owned, *removed])
            or owned != sorted(owned) or removed != sorted(removed)
            or not set(removed) <= set(owned)
        ):
            raise ReconstructionError("preparation cleanup path ledger is not canonical")
        final_attempt = offset == len(attempts_value)
        if final_attempt:
            if (
                attempt.get("passes") is not True
                or attempt.get("process_a_stage") != "completed"
                or attempt.get("process_b_stage") != "completed"
                or promotion.get("passes") is not True
                or cleanup.get("passes") is not True
                or owned != [str(source)]
                or removed != []
            ):
                raise ReconstructionError("final preparation attempt does not encode one passing atomic promotion")
            device, inode = promotion.get("source_device"), promotion.get("source_inode")
            if not isinstance(device, int) or isinstance(device, bool) or device < 0 or not isinstance(inode, int) or isinstance(inode, bool) or inode < 0:
                raise ReconstructionError("passing preparation promotion lacks nonnegative device/inode")
            if source.exists() or source.is_symlink():
                raise ReconstructionError("passing preparation staging source still exists")
            metadata = _plain_directory(destination, "promoted processes")
            if metadata.st_dev != device or metadata.st_ino != inode:
                raise ReconstructionError("promoted processes directory does not preserve source identity")
        else:
            if attempt.get("passes") is not False or promotion.get("passes") is not False or cleanup.get("passes") is not True:
                raise ReconstructionError("retry follows an attempt without a complete failed-cleanup record")
            if source.exists() or source.is_symlink():
                raise ReconstructionError("failed preparation staging source remains before retry")
            device, inode = promotion.get("source_device"), promotion.get("source_inode")
            if (device is None) != (inode is None):
                raise ReconstructionError("failed preparation promotion has partial source identity")
            if device is not None:
                _nonnegative_integer(device, "failed preparation source device")
                _nonnegative_integer(inode, "failed preparation source inode")
            if owned not in ([], [str(source)]):
                raise ReconstructionError("failed preparation cleanup claims an unregistered owned path")
            if removed not in ([], [str(source)]):
                raise ReconstructionError("failed preparation cleanup claims an unregistered removal")
    return len(attempts_value)


def _exclusive_verification_write(path: Path, raw: bytes) -> None:
    parent = path.parent
    parent_identity = _directory_identity(parent, "preparation-verification parent")
    parent_descriptor = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    descriptor: int | None = None
    created_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_descriptor,
        )
        created = os.fstat(descriptor)
        if not stat.S_ISREG(created.st_mode) or stat.S_IMODE(created.st_mode) != 0o600:
            raise ReconstructionError("preparation-verification destination is not mode-0600 regular")
        created_identity = (created.st_dev, created.st_ino)
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise ReconstructionError("preparation-verification receipt write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        reopened = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_descriptor,
        )
        try:
            metadata = os.fstat(reopened)
            if (
                created_identity != (metadata.st_dev, metadata.st_ino)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != len(raw)
            ):
                raise ReconstructionError("preparation-verification destination changed")
            chunks: list[bytes] = []
            remaining = len(raw) + 1
            while remaining:
                chunk = os.read(reopened, min(1 << 20, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if b"".join(chunks) != raw:
                raise ReconstructionError("preparation-verification bytes did not round-trip")
        finally:
            os.close(reopened)
        os.fsync(parent_descriptor)
        after = os.fstat(parent_descriptor)
        if any(
            parent_identity[key] != actual
            for key, actual in {
                "root_device": after.st_dev,
                "root_inode": after.st_ino,
                "root_owner_uid": after.st_uid,
                "root_mode": stat.S_IMODE(after.st_mode),
            }.items()
        ):
            raise ReconstructionError("preparation-verification parent changed during publication")
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if created_identity is not None:
            try:
                candidate = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
                if stat.S_ISREG(candidate.st_mode) and (candidate.st_dev, candidate.st_ino) == created_identity:
                    os.unlink(path.name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
            except OSError:
                pass
        raise
    finally:
        os.close(parent_descriptor)


def _validate_verification_record(value: object) -> Mapping[str, object]:
    receipt = _exact_keys(value, _VERIFICATION_RECEIPT_KEYS, "preparation-verification receipt")
    if (
        receipt.get("schema_version") != "action-qbc-v8-preparation-verification-receipt-v1"
        or receipt.get("treatment_id") != TREATMENT_ID
        or receipt.get("open_freeze_tag") != OPEN_FREEZE_TAG
        or receipt.get("status") != "verified"
    ):
        raise ReconstructionError("preparation-verification receipt fixed identity/status mismatch")
    _hex(receipt.get("open_freeze_commit_sha"), 40, "preparation-verification O8 commit")
    _hex(receipt.get("registration_content_sha256"), 64, "preparation-verification registration")
    _hex(receipt.get("preparation_receipt_sha256"), 64, "preparation receipt bytes")
    _hex(receipt.get("verification_argv_sha256"), 64, "preparation-verification argv")
    for name in ("authority", "process_a", "process_b"):
        clone = _exact_keys(receipt.get(name), _VERIFICATION_CLONE_KEYS, f"verification {name}")
        if clone.get("passes") is not True:
            raise ReconstructionError(f"verification {name} is not passing")
    content = _hex(receipt.get("content_sha256"), 64, "preparation-verification content")
    preimage = dict(receipt)
    preimage.pop("content_sha256")
    if canonical_sha256(preimage) != content:
        raise ReconstructionError("preparation-verification content hash mismatch")
    return receipt


def verify_preparation(
    repository_root: str | Path,
    registration_path: str | Path,
    preparation_receipt_path: str | Path,
    verification_receipt_path: str | Path,
) -> dict[str, object]:
    root = Path(repository_root).resolve(strict=True)
    registration = verify_registration(root, registration_path)
    _expected, phase, head = _reconstruct_with_identity(root)
    if phase != "open_freeze":
        raise ReconstructionError("--verify-preparation requires the clean tagged O8 authority clone")
    _verify_linux_host(registration)
    execution = cast(Mapping[str, object], registration["execution_contract"])
    execution_root = Path(cast(str, execution["execution_root"]))
    receipt_path = Path(preparation_receipt_path)
    expected_receipt_path = Path(cast(str, execution["preparation_receipt_path"]))
    verification_path = Path(verification_receipt_path)
    expected_verification_path = Path(cast(str, execution["preparation_verification_receipt_path"]))
    if receipt_path != expected_receipt_path:
        raise ReconstructionError("preparation receipt path differs from the registered plain path")
    if verification_path != expected_verification_path:
        raise ReconstructionError("preparation-verification receipt path differs from the registered path")
    try:
        verification_path.lstat()
    except FileNotFoundError:
        pass
    except OSError as error:
        raise ReconstructionError("cannot establish preparation-verification receipt absence") from error
    else:
        raise ReconstructionError("preparation-verification receipt already exists")
    if receipt_path.parent != execution_root or verification_path.parent != execution_root:
        raise ReconstructionError("preparation evidence paths escape the execution root")
    execution_descriptor = os.open(
        execution_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        receipt_raw = _read_regular_beneath(
            execution_descriptor,
            (receipt_path.name,),
            "preparation receipt",
            maximum=67_108_864,
        )
    finally:
        os.close(execution_descriptor)
    receipt = strict_object(receipt_raw, "preparation receipt")
    _exact_keys(receipt, _PREPARATION_KEYS, "preparation receipt")
    if (
        receipt.get("schema_version") != "action-qbc-v8-preparation-receipt-v2"
        or receipt.get("treatment_id") != TREATMENT_ID
        or receipt.get("open_freeze_commit_sha") != head
        or receipt.get("open_freeze_tag") != OPEN_FREEZE_TAG
        or receipt.get("registration_content_sha256") != registration.get("content_sha256")
        or receipt.get("status") != "prepared"
    ):
        raise ReconstructionError("preparation receipt fixed identity/status mismatch")
    authority = Path(cast(str, execution["authority_root"]))
    process_a = Path(cast(str, execution["process_a_root"]))
    process_b = Path(cast(str, execution["process_b_root"]))
    if root != authority:
        raise ReconstructionError("preparation gate is not running from the registered authority clone")
    _directory_identity(execution_root, "execution root")
    attempt_count = _validate_attempts(receipt.get("attempts"), execution_root)
    _validate_command_ledger(receipt, execution, execution_root, attempt_count)
    authority_record = _validate_clone_receipt(
        receipt.get("authority"), "authority", authority, head, environment_expected=False
    )
    process_a_record = _validate_clone_receipt(
        receipt.get("process_a"), "process A", process_a, head, environment_expected=True
    )
    process_b_record = _validate_clone_receipt(
        receipt.get("process_b"), "process B", process_b, head, environment_expected=True
    )
    if process_a_record["venv_python_sha256"] != process_b_record["venv_python_sha256"]:
        raise ReconstructionError("process A/B resolved Python executable hashes differ")
    _directory_identity(
        Path(cast(str, execution["process_a_output"])).parent,
        "process A output parent",
        empty=True,
    )
    _directory_identity(
        Path(cast(str, execution["process_b_output"])).parent,
        "process B output parent",
        empty=True,
    )
    verification_argv = execution.get("post_preparation_validation_argv")
    if not isinstance(verification_argv, list):
        raise ReconstructionError("registered preparation-verification argv is absent")
    record: dict[str, object] = {
        "schema_version": "action-qbc-v8-preparation-verification-receipt-v1",
        "treatment_id": TREATMENT_ID,
        "open_freeze_commit_sha": head,
        "open_freeze_tag": OPEN_FREEZE_TAG,
        "registration_content_sha256": registration["content_sha256"],
        "preparation_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "verification_argv_sha256": canonical_sha256(verification_argv),
        "authority": authority_record,
        "process_a": process_a_record,
        "process_b": process_b_record,
        "status": "verified",
    }
    record["content_sha256"] = canonical_sha256(record)
    _validate_verification_record(record)
    raw = canonical_json_bytes(record)
    _exclusive_verification_write(verification_path, raw)
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--verify-open-freeze", action="store_true")
    modes.add_argument("--verify-preparation", action="store_true")
    parser.add_argument("--preparation-receipt", type=Path)
    parser.add_argument("--verification-receipt", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    supplied_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(supplied_argv)
    if args.verify_preparation:
        if args.preparation_receipt is None or args.verification_receipt is None:
            raise ReconstructionError(
                "--verify-preparation requires --preparation-receipt and --verification-receipt"
            )
        root = Path(args.repository_root).resolve(strict=True)
        registration = verify_registration(root, args.registration)
        execution = cast(Mapping[str, object], registration["execution_contract"])
        invoked = [
            "/usr/bin/python3", "-I", "-B",
            "scripts/reconstruct_action_qbc_v8_open_registration.py",
            *supplied_argv,
        ]
        if invoked != execution.get("post_preparation_validation_argv"):
            raise ReconstructionError("preparation-verification invocation differs from registered argv")
        record = verify_preparation(
            root,
            args.registration,
            args.preparation_receipt,
            args.verification_receipt,
        )
        sys.stdout.buffer.write(canonical_json_bytes(record) + b"\n")
        return 0
    if args.preparation_receipt is not None or args.verification_receipt is not None:
        raise ReconstructionError(
            "--preparation-receipt/--verification-receipt require --verify-preparation"
        )
    if args.verify_open_freeze:
        record = verify_open_freeze(args.repository_root, args.registration)
        sys.stdout.buffer.write(canonical_json_bytes(record) + b"\n")
        return 0
    registration = verify_registration(args.repository_root, args.registration)
    raw = canonical_json_bytes(registration)
    summary = {
        "content_sha256": registration["content_sha256"],
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "row_count": cast(Mapping[str, object], registration["row_inventory"])["count"],
        "status": "verified",
    }
    sys.stdout.buffer.write(canonical_json_bytes(summary) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReconstructionError, OSError, ValueError, json.JSONDecodeError) as error:
        sys.stderr.buffer.write(
            canonical_json_bytes({"error": str(error), "status": "refused"}) + b"\n"
        )
        raise SystemExit(2) from error
