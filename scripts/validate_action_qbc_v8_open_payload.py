"""Validate one immutable action-QBC v8 payload without starting new science."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

_TREATMENT_ID = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_VALIDATOR_SCHEMA = "action-qbc-v8-payload-validator-claim-v1"
_VALIDATION_SCHEMA = "action-qbc-v8-payload-validation-receipt-v1"
_START_SCHEMA = "action-qbc-v8-scientific-start-claim-v1"
_OPEN_FREEZE_TAG = "action-qbc-v8-open-diagnostic-freeze-v4"
_PREREGISTRATION_COMMIT = "15059c482d9e463f01cb31fdfd33c96d1f60db0a"
_EXPECTED_SCRIPT = "scripts/validate_action_qbc_v8_open_payload.py"
_RUNNER_SCRIPT = "scripts/run_action_qbc_v8_open_diagnostic.py"
_EXPECTED_REGISTRATION = "artifacts/action_qbc_v8_open_registration.json"
_EXECUTION_ROOT = Path("/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4")
_ARM_RECEIPT = str(_EXECUTION_ROOT / "arm-receipt.json")
_DRIVER_CLAIM = str(_EXECUTION_ROOT / "lifecycle-driver-claim.json")
_PAYLOAD_CAP_BYTES = 67_108_864
_VALIDATOR_TIMEOUT_SECONDS = 300
_PROCESS = {
    "A": {
        "root": str(_EXECUTION_ROOT / "processes/process-a"),
        "start_claim": str(_EXECUTION_ROOT / "process-a-start-claim.json"),
        "validator_claim": str(_EXECUTION_ROOT / "process-a-validator-claim.json"),
        "validation_receipt": str(_EXECUTION_ROOT / "process-a-validation.json"),
        "payload": str(
            _EXECUTION_ROOT
            / "processes/process-a-output/open/action_qbc_v8_open_diagnostic.json"
        ),
    },
    "B": {
        "root": str(_EXECUTION_ROOT / "processes/process-b"),
        "start_claim": str(_EXECUTION_ROOT / "process-b-start-claim.json"),
        "validator_claim": str(_EXECUTION_ROOT / "process-b-validator-claim.json"),
        "validation_receipt": str(_EXECUTION_ROOT / "process-b-validation.json"),
        "payload": str(
            _EXECUTION_ROOT
            / "processes/process-b-output/open/action_qbc_v8_open_diagnostic.json"
        ),
    },
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
    """A failure before or around the one-shot validation observation."""


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


def _git(root: Path, *arguments: str) -> bytes:
    environment = {
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
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "--no-replace-objects", "-C", str(root), *arguments],
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=60,
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


def _require_direct_child(root: Path, child: str, parent: str) -> None:
    observed = _git(root, "rev-list", "--parents", "-n", "1", child)
    if observed != f"{child} {parent}\n".encode("ascii"):
        _fail("O8 is not a direct child of registered P8")


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


def _plain(path: Path, name: str, *, maximum: int) -> bytes:
    try:
        before_path = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _AdministrativeFailure(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(before_path, maximum):
        _fail(f"{name} is not a permitted plain file")
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


def _preverify_and_load_runner(root: Path) -> tuple[ModuleType, str]:
    _validate_local_git_sources(root)
    head = _git(root, "rev-parse", "HEAD").decode("ascii", "strict").strip()
    tag = _git(root, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}").decode(
        "ascii", "strict"
    ).strip()
    if (
        len(tag) != 40
        or any(character not in "0123456789abcdef" for character in tag)
        or head != tag
        or _git(root, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}") != b"commit\n"
    ):
        _fail("clone HEAD or lightweight O8 tag is invalid")
    _require_direct_child(root, tag, _PREREGISTRATION_COMMIT)
    for relative, name in (
        (_EXPECTED_SCRIPT, "payload validator"),
        (_RUNNER_SCRIPT, "runner helper"),
    ):
        raw = _plain(root / relative, name, maximum=2_000_000)
        if raw != _git(root, "show", f"{tag}:{relative}"):
            _fail(f"{name} raw bytes differ from the O8 Git blob")
    helper_path = root / _RUNNER_SCRIPT
    specification = importlib.util.spec_from_file_location(
        "_action_qbc_v8_runner_helper", helper_path
    )
    if specification is None or specification.loader is None:
        _fail("runner helper cannot be loaded")
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    return helper, tag


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one action-QBC v8 payload.")
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--driver-claim", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--start-claim", required=True)
    parser.add_argument("--validator-claim", required=True)
    parser.add_argument("--validation-receipt", required=True)
    parser.add_argument("--payload", required=True)
    return parser.parse_args(argv)


def _substitute_validator_argv(
    template: Sequence[Any], *, label: str, process: Mapping[str, str]
) -> list[str]:
    if not all(isinstance(item, str) for item in template):
        _fail("validator argv template is invalid")
    replacements = {
        "<LABEL>": label,
        "<START_CLAIM>": process["start_claim"],
        "<VALIDATOR_CLAIM>": process["validator_claim"],
        "<VALIDATION_RECEIPT>": process["validation_receipt"],
        "<OUTPUT_PATH>": process["payload"],
    }
    result = [replacements.get(item, item) for item in template]
    if any(item.startswith("<") and item.endswith(">") for item in result):
        _fail("validator argv has an unresolved placeholder")
    return result


def _require_contract(
    args: argparse.Namespace,
    helper: ModuleType,
    root: Path,
    registration: Mapping[str, Any],
) -> tuple[str, dict[str, str], list[str]]:
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("payload validator requires Python -I -B")
    if (
        args.repository_root != "."
        or args.registration != _EXPECTED_REGISTRATION
        or args.arm_receipt != _ARM_RECEIPT
        or args.driver_claim != _DRIVER_CLAIM
        or args.label not in _PROCESS
    ):
        _fail("payload-validator command differs from registration")
    label = str(args.label)
    process = _PROCESS[label]
    if any(
        (
            args.start_claim != process["start_claim"],
            args.validator_claim != process["validator_claim"],
            args.validation_receipt != process["validation_receipt"],
            args.payload != process["payload"],
        )
    ):
        _fail("payload-validator label/path binding is invalid")
    if root != Path(process["root"]).resolve(strict=True):
        _fail("payload validator is not running in the registered process clone")
    root_metadata = root.stat(follow_symlinks=False)
    if not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode):
        _fail("registered process clone is not a plain directory")
    if hasattr(os, "getuid") and root_metadata.st_uid != os.getuid():
        _fail("registered process clone has the wrong owner")
    if Path(sys.executable).absolute() != (root / ".venv/bin/python3").absolute():
        _fail("payload-validator interpreter differs from registration")
    if Path(sys.argv[0]).resolve(strict=True) != (root / _EXPECTED_SCRIPT).resolve(strict=True):
        _fail("payload-validator source origin differs from registration")
    execution = helper._validate_execution_contract(registration)
    lower = label.casefold()
    if (
        execution.get("registered_start_count") != 2
        or execution.get("process_labels") != ["A", "B"]
        or execution.get("third_start_allowed") is not False
        or execution.get("preparation_verification_receipt_path")
        != helper._PREPARATION_VERIFICATION_RECEIPT
        or execution.get("arm_receipt_path") != _ARM_RECEIPT
        or execution.get("lifecycle_driver_claim_path") != _DRIVER_CLAIM
        or execution.get("payload_validator_timeout_seconds")
        != _VALIDATOR_TIMEOUT_SECONDS
        or execution.get(f"process_{lower}_root") != process["root"]
        or execution.get(f"process_{lower}_start_claim") != process["start_claim"]
        or execution.get(f"process_{lower}_validator_claim")
        != process["validator_claim"]
        or execution.get(f"process_{lower}_validation_receipt")
        != process["validation_receipt"]
        or execution.get(f"process_{lower}_output") != process["payload"]
    ):
        _fail("registration payload-validator process contract is invalid")
    template = execution.get("payload_validator_argv_template")
    if not isinstance(template, list):
        _fail("validator argv template is invalid")
    full_argv = _substitute_validator_argv(template, label=label, process=process)
    try:
        script_index = full_argv.index(_EXPECTED_SCRIPT)
    except ValueError as exc:
        raise _AdministrativeFailure("validator argv lacks its script") from exc
    if list(sys.argv) != full_argv[script_index:]:
        _fail("observed validator argv differs from registration")
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping) or hashes.get("payload_validator") != _sha256(
        _canonical_json_bytes(template)
    ):
        _fail("registered validator argv hash is invalid")
    if Path(args.validator_claim).exists() or Path(args.validator_claim).is_symlink():
        _fail("payload-validator claim already exists")
    if Path(args.validation_receipt).exists() or Path(args.validation_receipt).is_symlink():
        _fail("payload-validation receipt already exists")
    # Accessing this helper performs no scientific import and verifies all tracked raw bytes.
    return label, process, full_argv


def _exclusive_json(helper: ModuleType, path: Path, value: Mapping[str, Any], name: str) -> bytes:
    raw = _canonical_json_bytes(value)
    try:
        observed = helper._exclusive_canonical(path, value)
    except Exception as exc:
        raise _AdministrativeFailure(f"exclusive {name} publication failed") from exc
    if observed != raw:
        _fail(f"{name} publication changed its canonical bytes")
    return raw


def _validate_start_claim(
    helper: ModuleType,
    path: Path,
    *,
    label: str,
    process: Mapping[str, str],
    registration: Mapping[str, Any],
    open_commit: str,
    arm_raw: bytes,
    driver_raw: bytes,
    prior_sha: str | None,
) -> tuple[dict[str, Any], bytes]:
    execution = registration.get("execution_contract")
    template = (
        execution.get("scientific_argv_template")
        if isinstance(execution, Mapping)
        else None
    )
    if not isinstance(template, list):
        _fail("registered scientific argv template is invalid")
    scientific_argv = helper._substituted_scientific_argv(
        template,
        label=label,
        process=helper._PROCESS[label],
    )
    start, raw = helper._validate_receipt(
        path,
        keys=helper._START_KEYS,
        schema=_START_SCHEMA,
        name=f"process {label} start claim",
    )
    if (
        start.get("label") != label
        or start.get("open_freeze_commit_sha") != open_commit
        or start.get("registration_content_sha256") != registration.get("content_sha256")
        or start.get("arm_receipt_sha256") != _sha256(arm_raw)
        or start.get("lifecycle_driver_claim_sha256") != _sha256(driver_raw)
        or start.get("scientific_argv_sha256") != _sha256(_canonical_json_bytes(scientific_argv))
        or start.get("prior_validation_receipt_sha256") != prior_sha
        or start.get("output_path") != process["payload"]
    ):
        _fail("scientific start claim does not match the validator process")
    for key in (
        "scientific_argv_sha256",
        "arm_receipt_sha256",
        "lifecycle_driver_claim_sha256",
    ):
        helper._require_sha(start.get(key), 64, f"start claim {key}")
    return start, raw


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    claimed = False
    receipt_written = False
    try:
        if argv is not None:
            _fail("programmatic argv is not permitted for the production validator")
        if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
            _fail("payload validator requires Python -I -B")
        root = Path.cwd().resolve(strict=True)
        helper, preverified_commit = _preverify_and_load_runner(root)
        registration, registration_raw = helper._load_registration(root, args.registration)
        label, process, full_argv = _require_contract(args, helper, root, registration)
        open_commit = helper._verify_repository(root, registration, registration_raw)
        if open_commit != preverified_commit:
            _fail("open-freeze identity changed during validation")
        arm_raw, driver_raw, prior_sha, _, _ = helper._validate_dependencies(
            registration,
            label=label,
            process=helper._PROCESS[label],
            open_commit=open_commit,
        )
        _, start_raw = _validate_start_claim(
            helper,
            Path(process["start_claim"]),
            label=label,
            process=process,
            registration=registration,
            open_commit=open_commit,
            arm_raw=arm_raw,
            driver_raw=driver_raw,
            prior_sha=prior_sha,
        )
        payload_raw = _plain(
            Path(process["payload"]),
            f"process {label} payload",
            maximum=_PAYLOAD_CAP_BYTES + 1,
        )
        validator_claim = {
            "schema_version": _VALIDATOR_SCHEMA,
            "treatment_id": _TREATMENT_ID,
            "label": label,
            "lifecycle_driver_claim_sha256": _sha256(driver_raw),
            "start_claim_sha256": _sha256(start_raw),
            "validator_argv_sha256": _sha256(_canonical_json_bytes(full_argv)),
            "payload_sha256": _sha256(payload_raw),
        }
        if set(validator_claim) != _VALIDATOR_KEYS:
            _fail("payload-validator claim schema is invalid")
        validator_claim_path = Path(process["validator_claim"])
        claim_publication_verified = True
        try:
            validator_raw = _exclusive_json(
                helper,
                validator_claim_path,
                validator_claim,
                "payload-validator claim",
            )
        except _AdministrativeFailure as publication_error:
            # The shared publisher creates the destination exclusively before its
            # durable reopen/round-trip checks.  If those later checks fail, the
            # acquired one-shot claim is still irreversible and must lead to one
            # invalid validation-receipt attempt rather than a preclaim exit.
            expected_validator_raw = _canonical_json_bytes(validator_claim)
            try:
                observed_validator_raw = _plain(
                    validator_claim_path,
                    "payload-validator claim after publication failure",
                    maximum=1 << 20,
                )
            except _AdministrativeFailure as recovery_error:
                raise publication_error from recovery_error
            if observed_validator_raw != expected_validator_raw:
                raise publication_error from None
            validator_raw = observed_validator_raw
            claim_publication_verified = False
        claimed = True

        status = "invalid"
        if claim_publication_verified:
            try:
                audit = importlib.import_module("arc3_voi.action_qbc_v8_audit")
                module_path = getattr(audit, "__file__", None)
                expected_module = (
                    root / "src/arc3_voi/action_qbc_v8_audit.py"
                ).resolve(strict=True)
                if not isinstance(module_path, str):
                    raise ValueError("v8 audit module has no source origin")
                if Path(module_path).resolve(strict=True) != expected_module:
                    raise ValueError("v8 audit module origin mismatch")
                payload = helper._parse_canonical(
                    payload_raw,
                    f"process {label} payload",
                    maximum=_PAYLOAD_CAP_BYTES + 1,
                )
                if len(payload_raw) <= _PAYLOAD_CAP_BYTES:
                    validated = audit.validate_scientific_payload(payload, registration)
                    current_payload_raw = _plain(
                        Path(process["payload"]),
                        f"process {label} payload after validation",
                        maximum=_PAYLOAD_CAP_BYTES + 1,
                    )
                    if (
                        audit.canonical_json_bytes(validated) == payload_raw
                        and current_payload_raw == payload_raw
                    ):
                        status = "valid"
            except Exception:
                status = "invalid"

        receipt = {
            "schema_version": _VALIDATION_SCHEMA,
            "treatment_id": _TREATMENT_ID,
            "label": label,
            "start_claim_sha256": _sha256(start_raw),
            "validator_claim_sha256": _sha256(validator_raw),
            "payload_path": process["payload"],
            "payload_sha256": _sha256(payload_raw),
            "payload_size_bytes": len(payload_raw),
            "status": status,
        }
        if set(receipt) != _VALIDATION_KEYS:
            _fail("payload-validation receipt schema is invalid")
        _exclusive_json(
            helper,
            Path(process["validation_receipt"]),
            receipt,
            "payload-validation receipt",
        )
        receipt_written = True
        return 0 if status == "valid" else 1
    except _AdministrativeFailure as exc:
        print(f"action-QBC v8 payload-validator administrative failure: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        phase = "after claim" if claimed else "before claim"
        receipt = "receipt written" if receipt_written else "no receipt"
        print(
            f"action-QBC v8 payload-validator failure {phase}, {receipt}: {exc}",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
