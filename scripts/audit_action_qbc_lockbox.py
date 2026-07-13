"""Two-start, permit-gated sealed evaluator for the registered action-QBC audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from arc3_voi.action_qbc_audit import (
    AUDIT_CONFIG_RELATIVE_PATH,
    AUDIT_REGISTRATION_RELATIVE_PATH,
    AuditCounterState,
    AuditWallTimeExceeded,
    RegisteredAuditCapability,
    RegisteredAuditLaunchAttestation,
    RegisteredEvaluationContext,
    build_emergency_negative_payload,
    build_registered_evaluation_fallback,
    canonical_json_bytes,
    evaluate_registered_manifest,
    issue_registered_audit_capability,
    issue_registered_audit_launch_attestation,
    load_audit_registration_admin,
    prepare_registered_evaluation_context,
    prepare_registered_fallback_context_from_registration,
    read_authorized_registered_manifest,
    require_registered_audit_authorized,
    require_registered_launcher_environment,
)
from arc3_voi.config import load_config


@dataclass(frozen=True, slots=True)
class _PythonRuntimeIdentity:
    isolated: int
    dont_write_bytecode_flag: int
    dont_write_bytecode_global: bool
    executable: Path
    script_origin: Path
    argv0: Path
    current_directory: Path
    project_module_origins: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True, slots=True)
class _ParentProcessIdentity:
    executable: Path
    current_directory: Path
    argv: tuple[str, ...]


class _ExposureState(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    UNKNOWN = "unknown"


def _capture_python_runtime_identity() -> _PythonRuntimeIdentity:
    origins: list[tuple[str, str | None]] = []
    for name in sorted(sys.modules):
        if name == "arc3_voi" or name.startswith("arc3_voi."):
            module = sys.modules[name]
            origins.append((name, getattr(module, "__file__", None)))
    return _PythonRuntimeIdentity(
        isolated=sys.flags.isolated,
        dont_write_bytecode_flag=sys.flags.dont_write_bytecode,
        dont_write_bytecode_global=sys.dont_write_bytecode,
        executable=Path(sys.executable),
        script_origin=Path(__file__),
        argv0=Path(sys.argv[0]),
        current_directory=Path.cwd(),
        project_module_origins=tuple(origins),
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_source_only_worktree(repository: Path) -> None:
    """Reject cached bytecode before any permit is consumed."""

    roots = (
        repository / "src" / "arc3_voi",
        repository / "scripts",
    )
    for source_root in roots:
        if not source_root.is_dir() or source_root.is_symlink():
            raise RuntimeError("sealed audit source root is missing or symbolic")
        for directory, directory_names, file_names in os.walk(
            source_root,
            followlinks=False,
        ):
            current = Path(directory)
            if current.name == "__pycache__" or "__pycache__" in directory_names:
                raise RuntimeError("sealed audit worktree contains cached Python bytecode")
            if any(name.endswith((".pyc", ".pyo")) for name in file_names):
                raise RuntimeError("sealed audit worktree contains cached Python bytecode")
            for name in directory_names:
                if (current / name).is_symlink():
                    raise RuntimeError("sealed audit source tree contains a symbolic directory")


def _require_python_runtime_identity(
    repository: Path,
    *,
    identity: _PythonRuntimeIdentity | None = None,
) -> _PythonRuntimeIdentity:
    """Reject direct/stale Python starts before permit administration."""

    root = repository.resolve(strict=True)
    observed = identity if identity is not None else _capture_python_runtime_identity()
    if (
        observed.isolated != 1
        or observed.dont_write_bytecode_flag != 1
        or observed.dont_write_bytecode_global is not True
    ):
        raise RuntimeError("sealed audit requires Python isolated mode with -I -B")
    _require_source_only_worktree(root)
    expected_executable = root / ".venv" / "bin" / "python3"
    if (
        not observed.executable.is_absolute()
        or observed.executable != expected_executable
        or not expected_executable.exists()
    ):
        raise RuntimeError("sealed audit interpreter launcher is outside the worktree")
    expected_script = (root / "scripts" / "audit_action_qbc_lockbox.py").resolve(
        strict=True
    )
    if (
        observed.script_origin.resolve(strict=True) != expected_script
        or observed.argv0.resolve(strict=True) != expected_script
        or observed.current_directory.resolve(strict=True) != root
    ):
        raise RuntimeError("sealed audit script/cwd origin differs from the worktree")
    required_modules = {
        "arc3_voi",
        "arc3_voi.action_qbc_audit",
        "arc3_voi.config",
    }
    by_name = dict(observed.project_module_origins)
    if len(by_name) != len(observed.project_module_origins) or not required_modules.issubset(
        by_name
    ):
        raise RuntimeError("sealed audit project-module origin inventory is incomplete")
    expected_source_root = (root / "src" / "arc3_voi").resolve(strict=True)
    for name, raw_origin in observed.project_module_origins:
        if raw_origin is None:
            raise RuntimeError(f"sealed audit project module lacks an origin: {name}")
        origin = Path(raw_origin).resolve(strict=True)
        if not _is_within(origin, expected_source_root):
            raise RuntimeError(
                f"sealed audit project module is outside the worktree source: {name}"
            )
    return observed


def _require_module_origin(module: ModuleType, expected: Path) -> None:
    raw_origin = getattr(module, "__file__", None)
    if not isinstance(raw_origin, str) or Path(raw_origin).resolve(strict=True) != (
        expected.resolve(strict=True)
    ):
        raise RuntimeError("administrative module origin differs from the worktree")


def _capture_parent_process_identity() -> _ParentProcessIdentity:
    process = Path("/proc") / str(os.getppid())
    raw = (process / "cmdline").read_bytes()
    if not raw.endswith(b"\0"):
        raise RuntimeError("uv parent command line is unavailable or malformed")
    argv = tuple(token.decode("utf-8") for token in raw[:-1].split(b"\0"))
    return _ParentProcessIdentity(
        executable=(process / "exe").resolve(strict=True),
        current_directory=(process / "cwd").resolve(strict=True),
        argv=argv,
    )


def _require_uv_parent_attestation(
    repository: Path,
    realized_command: Sequence[str],
    *,
    identity: _ParentProcessIdentity | None = None,
) -> _ParentProcessIdentity:
    """Prove that the immediate Linux parent launched the frozen uv command."""

    expected = tuple(realized_command)
    required_prefix = (
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python3",
        "-I",
        "-B",
        "scripts/audit_action_qbc_lockbox.py",
    )
    if expected[: len(required_prefix)] != required_prefix:
        raise RuntimeError("registered command lacks the canonical uv/Python prefix")
    observed = identity if identity is not None else _capture_parent_process_identity()
    if observed.executable.name != "uv":
        raise RuntimeError("sealed audit was not launched by the uv executable")
    if (
        not observed.argv
        or Path(observed.argv[0]).name != "uv"
        or observed.argv[1:] != expected[1:]
    ):
        raise RuntimeError("uv parent argv differs from the exact registered command")
    if observed.current_directory.resolve(strict=True) != repository.resolve(strict=True):
        raise RuntimeError("uv parent working directory differs from the worktree")
    return observed


def _classify_exposure(
    consumed: Mapping[str, object] | None,
    counters: AuditCounterState | None,
) -> _ExposureState:
    """Conservatively classify exposure without collapsing marker I/O errors."""

    if counters is not None and counters.scientific_exposure_started:
        return _ExposureState.AFTER
    if consumed is None:
        return _ExposureState.BEFORE
    marker = consumed.get("scientific_exposure_marker_path")
    if not isinstance(marker, str):
        return _ExposureState.UNKNOWN
    try:
        metadata = Path(marker).lstat()
    except FileNotFoundError:
        return (
            _ExposureState.BEFORE
            if counters is not None and not counters.scientific_exposure_started
            else _ExposureState.UNKNOWN
        )
    except OSError:
        return _ExposureState.UNKNOWN
    return (
        _ExposureState.AFTER
        if stat.S_ISREG(metadata.st_mode)
        else _ExposureState.UNKNOWN
    )


def _cli_failure_record(
    error: Exception,
    *,
    exposure_state: _ExposureState,
) -> dict[str, str]:
    failure = {
        "error_type": type(error).__name__,
        "stage": (
            "sealed_audit_post_exposure"
            if exposure_state is _ExposureState.AFTER
            else (
                "sealed_audit_exposure_unknown"
                if exposure_state is _ExposureState.UNKNOWN
                else "sealed_audit_pre_exposure"
            )
        ),
    }
    if exposure_state is _ExposureState.BEFORE:
        failure["message"] = str(error)
    return failure


def _ledger_failure_record(error: Exception) -> dict[str, str]:
    """Never expose ledger exception messages or worktree/output paths."""

    return {
        "error_type": type(error).__name__,
        "stage": "execution_ledger_append_failed",
    }


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", "-c", "core.quotepath=false", *arguments),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _clean_tagged_head(root: Path, registration: ModuleType) -> str:
    lockbox = "artifacts/action_conditional_qbc_v1_lockbox.json"
    pathspec = ("--", ".", f":(exclude){lockbox}")
    if _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        *pathspec,
    ):
        raise RuntimeError("sealed audit requires a clean non-lockbox worktree")
    if _git(root, "diff", "--no-ext-diff", "--binary", "--no-color", *pathspec):
        raise RuntimeError("sealed audit worktree diff is nonempty")
    if _git(
        root,
        "diff",
        "--cached",
        "--no-ext-diff",
        "--binary",
        "--no-color",
        *pathspec,
    ):
        raise RuntimeError("sealed audit index diff is nonempty")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tag = _git(root, "rev-parse", f"{registration.AUDIT_FREEZE_TAG}^{{commit}}").decode(
        "ascii"
    ).strip()
    if head != tag:
        raise RuntimeError("sealed audit HEAD is not the exact registered freeze tag")
    return head


def _write_exclusive(path: Path, raw: bytes) -> None:
    """Durably publish complete bytes without ever exposing a partial final path."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    linked = False
    durable = False
    try:
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("scientific payload write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(temporary, path, follow_symlinks=False)
        linked = True
        _fsync_parent_directory(path.parent)
        durable = True
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # Once the final hard link is durable, temporary-name cleanup is not part
            # of the scientific publication contract. Before that point, a leftover
            # uniquely named temporary file cannot block the one fallback publication.
            if not (linked and durable):
                raise
        if linked and durable:
            with suppress(OSError):
                _fsync_parent_directory(path.parent)


def _fsync_parent_directory(directory_path: Path) -> None:
    """Fsync a publication directory on the canonical Linux execution path."""

    if platform.system() != "Linux":
        return
    directory = os.open(
        directory_path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _install_hard_deadline(started_monotonic: float) -> None:
    remaining = 1_200.0 - (time.monotonic() - started_monotonic)
    if remaining <= 0:
        raise AuditWallTimeExceeded("sealed audit expired before registered-payload read")

    def expire(_signum: int, _frame: object) -> None:
        raise AuditWallTimeExceeded("sealed audit exceeded the hard 1,200-second deadline")

    alarm = cast(signal.Signals, vars(signal)["SIGALRM"])
    signal.signal(alarm, expire)
    _set_linux_real_timer(remaining)


def _set_linux_real_timer(seconds: float) -> None:
    """Set the Linux interval timer without exposing platform-specific stubs."""

    set_timer = cast(
        Callable[[int, float], object],
        vars(signal)["setitimer"],
    )
    timer_kind = cast(int, vars(signal)["ITIMER_REAL"])
    set_timer(timer_kind, seconds)


def _registration_rows(value: Mapping[str, object]) -> tuple[Mapping[str, Any], ...]:
    inventory = cast(Mapping[str, object], value["row_inventory"])
    rows = cast(Sequence[object], inventory["rows"])
    return tuple(cast(Mapping[str, Any], row) for row in rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--registration", default=AUDIT_REGISTRATION_RELATIVE_PATH)
    parser.add_argument("--permit-record", required=True)
    parser.add_argument("--permit-marker", required=True)
    parser.add_argument("--output", required=True)
    return parser


def _require_canonical_invocation(
    argv: Sequence[str] | None,
    *,
    registration: ModuleType,
    permit_record: str | Path,
    permit_marker: str | Path,
    output: Path,
) -> tuple[str, ...]:
    """Require the exact registered command tail before consuming a permit."""

    record = Path(permit_record).resolve(strict=False)
    marker = Path(permit_marker).resolve(strict=False)
    suffix = ".permit.json"
    if not record.name.endswith(suffix):
        raise RuntimeError("permit record does not encode a registered run label")
    run_label = record.name[: -len(suffix)]
    if marker != record.parent / f"{run_label}.available":
        raise RuntimeError("permit marker does not match the permit record")
    realized = tuple(
        registration.realized_audit_command(record.parent, run_label, output)
    )
    script_token = "scripts/audit_action_qbc_lockbox.py"
    try:
        script_index = realized.index(script_token)
    except ValueError as error:
        raise RuntimeError("registered command omits the sealed evaluator") from error
    expected_tail = realized[script_index + 1 :]
    actual_tail = tuple(sys.argv[1:] if argv is None else argv)
    if actual_tail != expected_tail:
        raise RuntimeError("invocation differs from the exact registered command")
    return realized


def main(argv: Sequence[str] | None = None) -> int:
    started_monotonic = time.monotonic()
    args = _parser().parse_args(argv)
    repository = Path(args.repository_root)
    consumed: Mapping[str, object] | None = None
    registration: ModuleType | None = None
    output = Path(args.output)
    realized_command: tuple[str, ...] | None = None
    payload_sha256: str | None = None
    counters: AuditCounterState | None = None
    evaluation_context: RegisteredEvaluationContext | None = None
    capability: RegisteredAuditCapability | None = None
    launch_attestation: RegisteredAuditLaunchAttestation | None = None
    disposition = "start_not_consumed"
    exit_status = 1
    try:
        if platform.system() != "Linux":
            raise RuntimeError("canonical sealed audit execution requires Linux")
        _install_hard_deadline(started_monotonic)
        repository = repository.resolve(strict=True)
        _require_python_runtime_identity(repository)
        registration = load_audit_registration_admin(repository)
        _require_module_origin(
            registration,
            repository / "scripts" / "build_action_qbc_audit_registration.py",
        )
        output = registration.require_external_scientific_output_path(repository, output)
        realized_command = _require_canonical_invocation(
            argv,
            registration=registration,
            permit_record=args.permit_record,
            permit_marker=args.permit_marker,
            output=output,
        )
        _require_uv_parent_attestation(repository, realized_command)
        require_registered_launcher_environment(repository, realized_command)
        registration_value, registration_raw = registration.load_validated_registration(
            repository,
            args.registration,
        )
        head = _clean_tagged_head(repository, registration)
        frozen_files = cast(Mapping[str, object], registration_value["frozen_files"])
        registration_sha256 = hashlib.sha256(registration_raw).hexdigest()
        source_manifest_sha256 = cast(str, frozen_files["manifest_sha256"])
        consumed = registration.consume_audit_start_permit(
            repository_root=repository,
            permit_record_path=args.permit_record,
            available_marker_path=args.permit_marker,
            output_path=output,
            expected_code_commit=head,
            expected_registration_sha256=registration_sha256,
            expected_source_manifest_sha256=source_manifest_sha256,
        )
        counters = AuditCounterState(
            _exposure_callback=lambda: registration.mark_scientific_exposure_started(
                cast(Mapping[str, object], consumed)
            )
        )
        launch_attestation = issue_registered_audit_launch_attestation(
            root=repository,
            exact_command=realized_command,
            consumed_permit=consumed,
        )
        capability = issue_registered_audit_capability(
            root=repository,
            launch_attestation=launch_attestation,
            registration_path=args.registration,
            consumed_permit=consumed,
        )
        provenance = require_registered_audit_authorized(capability)
        config = load_config(repository / AUDIT_CONFIG_RELATIVE_PATH)
        preregistration = cast(Mapping[str, Any], registration_value["preregistration"])
        registration_rows = _registration_rows(registration_value)
        evaluation_context = prepare_registered_fallback_context_from_registration(
            config=config,
            provenance=provenance,
            canonical_command_template=registration.AUDIT_COMMAND_TEMPLATE,
            registration_rows=registration_rows,
            registration_preregistration=preregistration,
            registration_sha256=registration_sha256,
            started_monotonic=started_monotonic,
        )
        manifest = read_authorized_registered_manifest(capability, counters=counters)
        evaluation_context = prepare_registered_evaluation_context(
            manifest,
            config=config,
            provenance=provenance,
            canonical_command_template=registration.AUDIT_COMMAND_TEMPLATE,
            registration_rows=registration_rows,
            registration_preregistration=preregistration,
            registration_sha256=registration_sha256,
            started_monotonic=started_monotonic,
        )
        payload = evaluate_registered_manifest(
            manifest,
            config=config,
            counters=counters,
            provenance=provenance,
            canonical_command_template=registration.AUDIT_COMMAND_TEMPLATE,
            registration_rows=registration_rows,
            registration_preregistration=preregistration,
            registration_sha256=registration_sha256,
            started_monotonic=started_monotonic,
            prepared_context=evaluation_context,
        )
        try:
            raw = canonical_json_bytes(payload)
        except Exception as error:
            if not counters.scientific_exposure_started:
                raise
            payload = build_emergency_negative_payload(payload, error)
            raw = canonical_json_bytes(payload)
        _set_linux_real_timer(0.0)
        _write_exclusive(output, raw)
        payload_sha256 = hashlib.sha256(raw).hexdigest()
        disposition = cast(str, payload["disposition"])
        exit_status = 0
    except Exception as error:
        if platform.system() == "Linux":
            _set_linux_real_timer(0.0)
        exposure_state = _classify_exposure(consumed, counters)
        fallback_written = False
        if (
            counters is not None
            and counters.scientific_exposure_started
            and evaluation_context is not None
        ):
            try:
                payload = build_registered_evaluation_fallback(
                    evaluation_context,
                    counters,
                    error,
                    stage="cli_evaluator_escape",
                )
                raw = canonical_json_bytes(payload)
                _write_exclusive(output, raw)
                payload_sha256 = hashlib.sha256(raw).hexdigest()
                disposition = cast(str, payload["disposition"])
                exit_status = 0
                fallback_written = True
            except Exception as fallback_error:
                error = fallback_error
        disposition = (
            "scientific_failure_after_exposure_runtime_v5_frozen"
            if exposure_state is _ExposureState.AFTER
            else (
                "scientific_exposure_indeterminate_runtime_v5_frozen"
                if exposure_state is _ExposureState.UNKNOWN
                else "infrastructure_failure_before_exposure_runtime_v5_frozen"
            )
        ) if not fallback_written else disposition
        if not fallback_written:
            failure = _cli_failure_record(error, exposure_state=exposure_state)
            print(
                json.dumps(
                    {
                        "disposition": disposition,
                        "failure": failure,
                        "status": "sealed_audit_failed",
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
    finally:
        if platform.system() == "Linux":
            _set_linux_real_timer(0.0)
        if consumed is not None and registration is not None:
            try:
                if realized_command is None:
                    raise RuntimeError("consumed audit lacks a canonical realized command")
                registration.append_execution_ledger(
                    capability=capability,
                    launch_attestation=launch_attestation,
                    repository_root=repository,
                    permit_directory=cast(str, consumed["permit_directory"]),
                    run_label=cast(str, consumed["run_label"]),
                    exact_command=realized_command,
                    output_path=output,
                    exit_status=exit_status,
                    payload_sha256=payload_sha256,
                    disposition=disposition,
                )
            except Exception as ledger_error:
                print(
                    json.dumps(
                        {
                            "failure": _ledger_failure_record(ledger_error),
                            "status": "sealed_audit_ledger_failed",
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
                exit_status = 1
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
