"""Run one frozen ARC action-QBC v7 open diagnostic process."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

from arc3_voi.action_qbc_v7_audit import (
    GlobalFallbackRequired,
    build_global_fallback,
    canonical_json_bytes,
    finalize_scientific_payload,
    load_registration,
    produce_scientific_candidate,
    validate_scientific_payload,
)

_TREATMENT_ID = "action-qbc-v7-open-failure-decomposition-v1"
_REGISTRATION_SCHEMA = "action-qbc-v7-open-registration-v1"
_OPEN_FREEZE_TAG = "action-qbc-v7-open-diagnostic-freeze-v1"
_COMPUTE_SECONDS = 2100
_WALL_SECONDS = 2400
_HARD_SECONDS = 2700
_PAYLOAD_CAP_BYTES = 67_108_864
_EXPECTED_SCRIPT = "scripts/run_action_qbc_v7_open_diagnostic.py"
_EXPECTED_REGISTRATION = "artifacts/action_qbc_v7_open_registration.json"
_EXPECTED_OUTPUTS = {
    "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a-output/open/"
    "action_qbc_v7_open_diagnostic.json": (
        "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-a"
    ),
    "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b-output/open/"
    "action_qbc_v7_open_diagnostic.json": (
        "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open/process-b"
    ),
}


class _AdministrativeFailure(RuntimeError):
    """A failure that must not be converted into scientific evidence."""


def _fail(message: str) -> NoReturn:
    raise _AdministrativeFailure(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_exact_keys(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        _fail(f"{name} has an invalid key set")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one registered action-QBC v7 open diagnostic process."
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--compute-deadline-seconds", required=True, type=int)
    parser.add_argument("--wall-time-seconds", required=True, type=int)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def _require_runtime_contract(
    args: argparse.Namespace,
    registration: Mapping[str, Any],
    *,
    started: float,
) -> tuple[Path, Path, float, float]:
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("the scientific runner requires Python -I -B")
    if args.repository_root != "." or args.registration != _EXPECTED_REGISTRATION:
        _fail("the scientific runner command differs from the registered command")
    if (
        args.compute_deadline_seconds != _COMPUTE_SECONDS
        or args.wall_time_seconds != _WALL_SECONDS
    ):
        _fail("the scientific runner deadlines differ from registration")

    output_text = args.output
    if output_text not in _EXPECTED_OUTPUTS:
        _fail("the scientific output is not one of the two registered paths")
    output = Path(output_text)
    if not output.is_absolute():
        _fail("the scientific output path is not absolute")

    root = Path.cwd()
    expected_root = Path(_EXPECTED_OUTPUTS[output_text])
    try:
        root_real = root.resolve(strict=True)
        expected_root_real = expected_root.resolve(strict=True)
    except OSError as exc:
        raise _AdministrativeFailure("the registered process root is unavailable") from exc
    if root_real != expected_root_real:
        _fail("the current directory is not the registered process clone")
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode):
        _fail("the registered process clone is not a plain directory")

    expected_script = root_real / _EXPECTED_SCRIPT
    try:
        if Path(sys.argv[0]).resolve(strict=True) != expected_script.resolve(strict=True):
            _fail("the scientific script origin differs from registration")
    except OSError as exc:
        raise _AdministrativeFailure("the scientific script origin is unavailable") from exc

    executable = Path(sys.executable).absolute()
    if executable != (root_real / ".venv/bin/python3").absolute():
        _fail("the scientific interpreter path differs from registration")

    if registration.get("schema_version") != _REGISTRATION_SCHEMA:
        _fail("the registration schema is invalid")
    if registration.get("status") != "registered_zero_result":
        _fail("the registration status is invalid")
    if registration.get("treatment_id") != _TREATMENT_ID:
        _fail("the registration treatment is invalid")
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("the registration execution contract is invalid")
    if (
        execution.get("compute_deadline_seconds") != _COMPUTE_SECONDS
        or execution.get("wall_time_seconds") != _WALL_SECONDS
        or execution.get("hard_timeout_seconds") != _HARD_SECONDS
        or execution.get("registered_start_count") != 2
        or execution.get("process_labels") != ["A", "B"]
        or execution.get("third_start_allowed") is not False
        or execution.get("open_freeze_tag", _OPEN_FREEZE_TAG) != _OPEN_FREEZE_TAG
    ):
        _fail("the registration execution constants are invalid")
    if output_text not in {
        execution.get("process_a_output"),
        execution.get("process_b_output"),
    }:
        _fail("the registration does not bind the selected output")
    expected_registered_root = (
        execution.get("process_a_root")
        if output_text == execution.get("process_a_output")
        else execution.get("process_b_root")
    )
    if expected_registered_root != str(expected_root):
        _fail("the registration does not bind the selected process clone")

    template = execution.get("scientific_argv_template")
    if not isinstance(template, list) or not all(isinstance(item, str) for item in template):
        _fail("the registered scientific command template is invalid")
    expected_template = list(template)
    try:
        output_index = expected_template.index("<OUTPUT_PATH>")
    except ValueError as exc:
        raise _AdministrativeFailure("the command template lacks its output placeholder") from exc
    expected_template[output_index] = output_text
    try:
        script_index = expected_template.index(_EXPECTED_SCRIPT)
    except ValueError as exc:
        raise _AdministrativeFailure("the command template lacks the runner path") from exc
    if list(sys.argv) != expected_template[script_index:]:
        _fail("the observed scientific argv differs from registration")
    argv_hashes = execution.get("argv_hashes")
    if not isinstance(argv_hashes, Mapping):
        _fail("the registered command hashes are invalid")
    if argv_hashes.get("scientific") != _sha256(canonical_json_bytes(template)):
        _fail("the registered scientific command hash is invalid")

    parent = output.parent
    try:
        parent_stat = parent.lstat()
    except OSError as exc:
        raise _AdministrativeFailure("the registered output parent is unavailable") from exc
    if not stat.S_ISDIR(parent_stat.st_mode) or stat.S_ISLNK(parent_stat.st_mode):
        _fail("the registered output parent is not a plain directory")
    if parent.resolve(strict=True) != parent.absolute():
        _fail("the registered output parent has a redirected ancestor")
    if stat.S_IMODE(parent_stat.st_mode) != 0o700:
        _fail("the registered output parent mode is not 0700")
    if hasattr(os, "getuid") and parent_stat.st_uid != os.getuid():
        _fail("the registered output parent is not owned by this uid")
    if output.exists() or output.is_symlink():
        _fail("the registered scientific output already exists")
    try:
        if any(parent.iterdir()):
            _fail("the registered scientific output parent is not empty")
    except OSError as exc:
        raise _AdministrativeFailure("the output parent cannot be enumerated") from exc

    return root_real, output, started + _COMPUTE_SECONDS, started + _WALL_SECONDS


def _require_before(deadline: float, operation: str) -> None:
    if time.monotonic() >= deadline:
        _fail(f"the CLI wall deadline elapsed before {operation}")


def _build_valid_fallback(
    registration: Mapping[str, Any],
    *,
    stage: str,
    candidate_payload_size_bytes: int | None = None,
) -> tuple[dict[str, Any], bytes]:
    payload = build_global_fallback(
        registration,
        stage,
        candidate_payload_size_bytes=candidate_payload_size_bytes,
    )
    validated = validate_scientific_payload(payload, registration)
    encoded = canonical_json_bytes(validated)
    if len(encoded) > _PAYLOAD_CAP_BYTES:
        _fail("the registered global fallback exceeds the payload cap")
    return validated, encoded


def _evaluate(
    root: Path,
    registration: Mapping[str, Any],
    *,
    compute_deadline: float,
) -> tuple[dict[str, Any], bytes]:
    try:
        if time.monotonic() >= compute_deadline:
            raise TimeoutError("compute deadline reached before scientific work")
        candidate = produce_scientific_candidate(
            root,
            registration,
            compute_deadline=compute_deadline,
        )
        if time.monotonic() >= compute_deadline:
            raise TimeoutError("scientific producer returned after the compute deadline")
        payload = finalize_scientific_payload(candidate, registration)
        validated = validate_scientific_payload(payload, registration)
        encoded = canonical_json_bytes(validated)
    except GlobalFallbackRequired as exc:
        return _build_valid_fallback(
            registration,
            stage=exc.stage,
            candidate_payload_size_bytes=exc.candidate_payload_size_bytes,
        )
    except Exception:
        return _build_valid_fallback(registration, stage="evaluator_internal_error")

    if len(encoded) <= _PAYLOAD_CAP_BYTES:
        return validated, encoded
    return _build_valid_fallback(
        registration,
        stage="payload_size_limit_exceeded",
        candidate_payload_size_bytes=len(encoded),
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _unlink_owned_output(output: Path, staging: Path, digest: str) -> None:
    try:
        output_stat = output.stat(follow_symlinks=False)
        staging_stat = staging.stat(follow_symlinks=False)
        if (
            output_stat.st_dev != staging_stat.st_dev
            or output_stat.st_ino != staging_stat.st_ino
            or _sha256(output.read_bytes()) != digest
        ):
            return
        output.unlink()
        _fsync_directory(output.parent)
    except OSError:
        return


def _publish(
    output: Path,
    payload: Mapping[str, Any],
    encoded: bytes,
    *,
    wall_deadline: float,
    registration: Mapping[str, Any],
) -> None:
    _require_before(wall_deadline, "scientific output staging")
    staging = output.with_name(f".{output.name}.stage-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        _fail("the scientific staging path already exists")
    created = False
    published = False
    digest = _sha256(encoded)
    try:
        descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

        _require_before(wall_deadline, "scientific output verification")
        observed = staging.read_bytes()
        if observed != encoded or _sha256(observed) != digest:
            _fail("the staged scientific output changed")
        reparsed = validate_scientific_payload(payload, registration)
        if canonical_json_bytes(reparsed) != observed:
            _fail("the staged scientific output failed canonical validation")

        _require_before(wall_deadline, "scientific output publication")
        os.link(staging, output, follow_symlinks=False)
        published = True
        _fsync_directory(output.parent)
        if time.monotonic() >= wall_deadline:
            _unlink_owned_output(output, staging, digest)
            published = output.exists() or output.is_symlink()
            _fail("the CLI wall deadline elapsed during publication")
    finally:
        if created:
            try:
                staging.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                if not published:
                    raise
    if not published:
        _fail("the scientific output was not published")


def main(argv: Sequence[str] | None = None) -> int:
    started = time.monotonic()
    args = _parse_args(argv)
    try:
        if argv is not None:
            _fail("programmatic argv is not permitted for the production runner")
        preliminary_root = Path.cwd().resolve(strict=True)
        registration_path = preliminary_root / args.registration
        registration = load_registration(preliminary_root, registration_path)
        root, output, compute_deadline, wall_deadline = _require_runtime_contract(
            args,
            registration,
            started=started,
        )
        payload, encoded = _evaluate(
            root,
            registration,
            compute_deadline=compute_deadline,
        )
        _publish(
            output,
            payload,
            encoded,
            wall_deadline=wall_deadline,
            registration=registration,
        )
    except _AdministrativeFailure as exc:
        print(f"action-QBC v7 administrative failure: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"action-QBC v7 unpublished failure: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
