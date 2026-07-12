"""Crash-safe publication and validation of paired run artifacts.

Remaining limitations: publication assumes one writer per run ID; a future
cross-process claim/lock is required for concurrent writers.  Serialization and
validation intentionally buffer each bounded trace in memory; streaming output
and resume scans are deferred to a separate performance-focused redesign.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

TRACE_ARTIFACT_KEY = "_trace_artifact"
TRACE_ARTIFACT_SCHEMA_VERSION = 1
RUN_IDENTITY_KEYS = (
    "run_id",
    "game_id",
    "seed",
    "variant",
    "model_profile",
    "config_hash",
)
_PORTABLE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)

# These are the fields needed to reconstruct the current StepRecord.  Keeping
# validation here avoids importing metrics (and therefore a metrics/experiment
# import cycle) while still rejecting syntactically valid but incomplete rows.
_TRACE_RECORD_FIELDS = frozenset(
    {
        "step",
        "level",
        "history",
        "action",
        "available_actions",
        "decision_mode",
        "decision_score",
        "decision_diagnostics",
        "probe_utility",
        "agreement",
        "generated_tokens",
        "weighted_transition_loss",
        "best_hypothesis_transition_loss",
        "valid_hypotheses",
        "hypothesis_ids",
        "hypothesis_weights",
        "hypothesis_validity",
        "invalidated_hypotheses",
        "timeout_hypotheses",
        "persistence_estimate",
        "persistence_successes",
        "persistence_trials",
        "boundary_survival",
        "fallback",
        "elapsed_seconds",
        "observed_grid",
        "observed_available_actions",
        "observed_state",
        "observed_level",
        "observed_win_levels",
        "observed_level_delta",
    }
)


def publish_run_artifacts(
    summary: Mapping[str, Any],
    trace_records: Sequence[Mapping[str, Any]],
    directory: str | Path,
) -> tuple[Path, Path]:
    """Atomically publish a trace/summary pair, with the summary as commit record.

    A small pending marker is installed before either public output changes.  The
    fully fsynced trace is replaced first and the summary containing its exact
    checksum is replaced last.  Consequently a crash exposes either the old
    complete pair, an explicitly pending/inconsistent pair, or the new complete
    pair--never a new summary that vouches for an unfinished trace.
    """

    run_id = summary.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("run_id must be a string")
    validate_run_id(run_id)
    if TRACE_ARTIFACT_KEY in summary:
        raise ValueError(f"summary may not define reserved key {TRACE_ARTIFACT_KEY!r}")

    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / f"{run_id}.json"
    trace_path = destination / f"{run_id}.jsonl"
    pending_path = _pending_path(summary_path)

    trace_bytes = _serialize_trace(trace_records)
    parsed_trace = _parse_trace(trace_bytes)
    if parsed_trace is None or not _summary_matches_trace(summary, parsed_trace):
        raise ValueError("summary counters and trace records must be complete and consistent")
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    committed_summary = dict(summary)
    committed_summary[TRACE_ARTIFACT_KEY] = {
        "schema_version": TRACE_ARTIFACT_SCHEMA_VERSION,
        "trace_file": trace_path.name,
        "sha256": trace_sha256,
        "record_count": len(trace_records),
    }
    summary_bytes = (
        json.dumps(committed_summary, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    existing = read_complete_run(summary_path)
    if existing is not None:
        existing_summary, _existing_trace = existing
        comparable_summary = dict(existing_summary)
        comparable_summary.pop(TRACE_ARTIFACT_KEY, None)
        if comparable_summary == dict(summary) and trace_path.read_bytes() == trace_bytes:
            return summary_path, trace_path
        if (
            existing_summary.get("error") is None
            and existing_summary.get("termination_reason") is not None
        ):
            raise FileExistsError(
                f"refusing to overwrite complete historical run artifacts for {run_id!r}"
            )
        conflicts = [
            key
            for key in RUN_IDENTITY_KEYS
            if existing_summary.get(key) != summary.get(key)
        ]
        if conflicts:
            raise FileExistsError(
                f"retry identity conflicts for {run_id!r}: {', '.join(conflicts)}"
            )
    else:
        ensure_retryable_run_artifacts(summary_path, expected_summary=summary)

    transaction_id = uuid.uuid4().hex
    pending_bytes = (
        json.dumps(
            {
                "schema_version": TRACE_ARTIFACT_SCHEMA_VERSION,
                "run_id": run_id,
                "transaction_id": transaction_id,
                "trace_sha256": trace_sha256,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    # Publish intent before changing a possible legacy pair.  A validator will
    # not accept a legacy summary while this marker exists.
    _atomic_replace_bytes(pending_path, pending_bytes, transaction_id, "pending")

    trace_temp: Path | None = None
    summary_temp: Path | None = None
    try:
        trace_temp = _write_fsynced_temp(
            trace_path, trace_bytes, transaction_id, "trace"
        )
        summary_temp = _write_fsynced_temp(
            summary_path, summary_bytes, transaction_id, "summary"
        )
        os.replace(trace_temp, trace_path)
        trace_temp = None
        _fsync_directory(destination)
        os.replace(summary_temp, summary_path)
        summary_temp = None
        _fsync_directory(destination)
    finally:
        _unlink_owned_temp(trace_temp)
        _unlink_owned_temp(summary_temp)

    # The checksum-bearing summary is already a durable commit record.  Failure
    # to remove this advisory marker therefore cannot make a valid pair unsafe.
    try:
        pending_path.unlink(missing_ok=True)
        _fsync_directory(destination)
    except OSError:
        pass
    return summary_path, trace_path


def read_complete_run(
    summary_path: str | Path,
    trace_path: str | Path | None = None,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]] | None:
    """Return a fully valid, mutually consistent run pair or ``None``.

    Checksum-free legacy summaries are accepted only when there is no pending
    publication marker and their trace is structurally consistent.  New
    summaries are accepted solely when their checksum metadata matches the
    exact sibling trace bytes.
    """

    summary_source = Path(summary_path)
    trace_source = (
        Path(trace_path) if trace_path is not None else summary_source.with_suffix(".jsonl")
    )
    if trace_source.parent != summary_source.parent:
        return None
    try:
        summary_bytes = summary_source.read_bytes()
        trace_bytes = trace_source.read_bytes()
        summary_value = json.loads(summary_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(summary_value, dict):
        return None
    summary: dict[str, Any] = summary_value

    run_id = summary.get("run_id")
    try:
        if not isinstance(run_id, str):
            return None
        validate_run_id(run_id)
    except ValueError:
        return None
    if summary_source.name != f"{run_id}.json":
        return None
    if trace_source.name != f"{run_id}.jsonl":
        return None

    records = _parse_trace(trace_bytes)
    if records is None or not _summary_matches_trace(summary, records):
        return None

    metadata = summary.get(TRACE_ARTIFACT_KEY)
    if metadata is None:
        if _pending_path(summary_source).exists():
            return None
    elif not _metadata_matches_trace(metadata, trace_source, trace_bytes, len(records)):
        return None
    return summary, records


def ensure_retryable_run_artifacts(
    summary_path: str | Path,
    *,
    expected_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Fail closed on corrupt/clean evidence; return a retryable prior summary.

    A parseable summary explicitly recording an error or lacking a termination
    reason is a retryable failed attempt.  A summary claiming clean termination
    is historical evidence and may not be replaced merely because its sibling
    trace has gone missing or become corrupt.
    """

    summary_source = Path(summary_path)
    trace_source = summary_source.with_suffix(".jsonl")
    pending_source = _pending_path(summary_source)
    if not summary_source.exists():
        if trace_source.exists() and not pending_source.exists():
            raise FileExistsError(
                f"refusing to overwrite orphan trace without transaction marker: {trace_source}"
            )
        return None
    try:
        value = json.loads(summary_source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FileExistsError(
            f"refusing to overwrite corrupt or unreadable run summary: {summary_source}"
        ) from exc
    if not isinstance(value, dict):
        raise FileExistsError(
            f"refusing to overwrite non-object run summary: {summary_source}"
        )
    summary: dict[str, Any] = value
    run_id = summary.get("run_id")
    try:
        if not isinstance(run_id, str):
            raise ValueError("run_id must be a string")
        validate_run_id(run_id)
    except ValueError as exc:
        raise FileExistsError(
            f"refusing to overwrite run summary with invalid identity: {summary_source}"
        ) from exc
    if summary_source.name != f"{run_id}.json":
        raise FileExistsError(
            f"refusing to overwrite run summary whose run_id does not match its filename: "
            f"{summary_source}"
        )
    error = summary.get("error")
    termination_reason = summary.get("termination_reason")
    if error is not None and not isinstance(error, str):
        raise FileExistsError(f"run summary has invalid error status: {summary_source}")
    if termination_reason is not None and not isinstance(termination_reason, str):
        raise FileExistsError(f"run summary has invalid termination status: {summary_source}")
    if expected_summary is not None:
        conflicts = [
            key
            for key in RUN_IDENTITY_KEYS
            if summary.get(key) != expected_summary.get(key)
        ]
        if conflicts:
            raise FileExistsError(
                f"retry identity conflicts in {summary_source}: {', '.join(conflicts)}"
            )
    if read_complete_run(summary_source) is not None:
        if error is None and termination_reason is not None:
            raise FileExistsError(
                f"run artifacts became complete while preparing retry: {run_id!r}"
            )
        return summary
    if error is None and termination_reason is not None:
        raise FileExistsError(
            f"refusing to overwrite clean completion claim with missing/corrupt trace: "
            f"{summary_source}"
        )
    return summary


def validate_run_id(run_id: str) -> None:
    """Require one conservative filename on both Windows and Linux."""

    if (
        not run_id
        or len(run_id) > 200
        or _PORTABLE_RUN_ID.fullmatch(run_id) is None
        or run_id.endswith(".")
        or run_id.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(
            "run_id must be 1-200 portable ASCII filename characters and not a "
            "Windows reserved device name"
        )


def _serialize_trace(records: Sequence[Mapping[str, Any]]) -> bytes:
    chunks = [
        json.dumps(dict(record), separators=(",", ":"), sort_keys=True) + "\n"
        for record in records
    ]
    return "".join(chunks).encode("utf-8")


def _parse_trace(trace_bytes: bytes) -> tuple[dict[str, Any], ...] | None:
    try:
        text = trace_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict) or not _TRACE_RECORD_FIELDS.issubset(value):
            return None
        records.append(value)
    if any(record.get("step") != index for index, record in enumerate(records, start=1)):
        return None
    return tuple(records)


def _summary_matches_trace(
    summary: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> bool:
    count = len(records)
    generated_tokens = [_nonnegative_int(record.get("generated_tokens")) for record in records]
    valid_hypotheses = [
        _nonnegative_int(record.get("valid_hypotheses")) for record in records
    ]
    fallbacks = [record.get("fallback") for record in records]
    if (
        any(value is None for value in generated_tokens)
        or any(value is None for value in valid_hypotheses)
        or any(not isinstance(value, bool) for value in fallbacks)
    ):
        return False
    return (
        _nonnegative_int(summary.get("decision_points")) == count
        and _nonnegative_int(summary.get("total_actions")) == count
        and _nonnegative_int(summary.get("generated_tokens"))
        == sum(value for value in generated_tokens if value is not None)
        and _nonnegative_int(summary.get("direct_fallbacks"))
        == sum(value is True for value in fallbacks)
        and _nonnegative_int(summary.get("two_valid_decision_points"))
        == sum(value >= 2 for value in valid_hypotheses if value is not None)
    )


def _metadata_matches_trace(
    metadata: object,
    trace_path: Path,
    trace_bytes: bytes,
    record_count: int,
) -> bool:
    if not isinstance(metadata, dict):
        return False
    return (
        _nonnegative_int(metadata.get("schema_version")) == TRACE_ARTIFACT_SCHEMA_VERSION
        and metadata.get("trace_file") == trace_path.name
        and _nonnegative_int(metadata.get("record_count")) == record_count
        and metadata.get("sha256") == hashlib.sha256(trace_bytes).hexdigest()
    )


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _pending_path(summary_path: Path) -> Path:
    return summary_path.with_suffix(".pending")


def _atomic_replace_bytes(
    destination: Path,
    data: bytes,
    transaction_id: str,
    role: str,
) -> None:
    temp = _write_fsynced_temp(destination, data, transaction_id, role)
    cleanup: Path | None = temp
    try:
        os.replace(temp, destination)
        cleanup = None
        _fsync_directory(destination.parent)
    finally:
        _unlink_owned_temp(cleanup)


def _write_fsynced_temp(
    destination: Path,
    data: bytes,
    transaction_id: str,
    role: str,
) -> Path:
    temp = destination.with_name(
        f".{destination.name}.{transaction_id}.{role}.tmp"
    )
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        _unlink_owned_temp(temp)
        raise
    return temp


def _unlink_owned_temp(path: Path | None) -> None:
    if path is None:
        return
    with suppress(OSError):
        path.unlink(missing_ok=True)


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory sync (supported on Linux, not normal Windows handles)."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
