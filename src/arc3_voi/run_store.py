"""Crash-safe publication and validation of paired run artifacts.

Remaining limitations: publication assumes one writer per run ID; a future
cross-process claim/lock is required for concurrent writers.  Serialization and
validation intentionally buffer each bounded trace in memory; streaming output
and resume scans are deferred to a separate performance-focused redesign.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .action_qbc_policy import (
    ACTION_COST,
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    OUTCOME_CONCENTRATION_THRESHOLD,
    RISK_COEFFICIENT,
    ROBUST_STD_COEFFICIENT,
)
from .planner import (
    COMPLETION_COST_POLICY_HASHES,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
)

TRACE_ARTIFACT_KEY = "_trace_artifact"
TRACE_ARTIFACT_SCHEMA_VERSION = 1
V5_IMPLEMENTATION_CONTRACT_VERSION = ACTION_QBC_RUNTIME_VERSION
V5_POLICY_IDENTITY_KEYS = (
    "implementation_contract_version",
    "completion_cost_policy_version",
    "completion_cost_policy_sha256",
    "probe_disagreement_policy_version",
    "probe_disagreement_policy_sha256",
    "outcome_concentration_threshold",
)
V5_REGISTERED_POLICY_IDENTITY = MappingProxyType({
    "implementation_contract_version": ACTION_QBC_RUNTIME_VERSION,
    "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
    "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
        PATH_DEFICIT_COMPLETION_COST_POLICY
    ],
    "probe_disagreement_policy_version": ACTION_QBC_POLICY_VERSION,
    "probe_disagreement_policy_sha256": ACTION_QBC_POLICY_SHA256,
    "outcome_concentration_threshold": OUTCOME_CONCENTRATION_THRESHOLD,
})
# These four complete semantic hashes were frozen in the zero-execution v5
# matrix before any registered scene was evaluated.  A record carrying one of
# them cannot be reclassified as historical merely by deleting its explicit
# policy fields and recomputing the artifact checksum.
V5_REGISTERED_CONFIG_SHA256_BY_ARM = MappingProxyType(
    {
        "D-Q": "8247eb92b176d471bba365856e28d441b186ddf0396b6fccd9a79b7636f22381",
        "S-T": "0c4dee3abaec89b6b42c75e60fee823099e3a95e49dffda84206fac7079a1094",
        "M-T": "2981a4d4209a7de924e16278eea180d2e4ab1c9b58359733f8c6be1900e4a3fa",
        "X-T": "e612be62a2cebca81062c5791f07af9b5b5c088f565b5cf25852aa41f859d60a",
    }
)
V5_REGISTERED_CONFIG_SHA256 = frozenset(V5_REGISTERED_CONFIG_SHA256_BY_ARM.values())
RUN_IDENTITY_KEYS = (
    "run_id",
    "game_id",
    "seed",
    "variant",
    "model_profile",
    "config_hash",
    "hypothesis_source",
    "arm_label",
    "identity_version",
    "producer_contract_sha256",
    *V5_POLICY_IDENTITY_KEYS,
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
            if (
                key in expected_summary
                or (key in V5_POLICY_IDENTITY_KEYS and key in summary)
            )
            and summary.get(key) != expected_summary.get(key)
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
    try:
        summary_is_v5 = validate_config_bound_v5_policy_identity(
            summary, context="run summary"
        )
    except ValueError:
        return False
    if not _v5_trace_attribution_matches(summary, records, summary_is_v5=summary_is_v5):
        return False
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


def validate_v5_policy_identity(
    value: Mapping[str, Any], *, context: str
) -> bool:
    """Validate an optional, complete runtime-v5 policy identity.

    The attribution tuple is deliberately all-or-nothing.  Returning ``False``
    denotes a historical record with no v5 fields; any partial, malformed, or
    non-v5 tuple raises so callers can fail closed.
    """

    present = set(V5_POLICY_IDENTITY_KEYS).intersection(value)
    if not present:
        return False
    if present != set(V5_POLICY_IDENTITY_KEYS):
        missing = ", ".join(sorted(set(V5_POLICY_IDENTITY_KEYS) - present))
        raise ValueError(f"{context} has incomplete runtime-v5 identity: {missing}")
    if any(value[key] is None for key in V5_POLICY_IDENTITY_KEYS):
        raise ValueError(f"{context} has null fields in its runtime-v5 identity")
    for key, registered in V5_REGISTERED_POLICY_IDENTITY.items():
        observed = value[key]
        if (
            isinstance(registered, float)
            and (
                isinstance(observed, bool)
                or not isinstance(observed, int | float)
                or not math.isfinite(float(observed))
            )
        ) or observed != registered:
            raise ValueError(
                f"{context} {key} does not match the exact registered runtime-v5 tuple"
            )
    return True


def validate_config_bound_v5_policy_identity(
    value: Mapping[str, Any], *, context: str
) -> bool:
    """Require the exact v5 tuple whenever a frozen v5 config hash is present."""

    is_v5 = validate_v5_policy_identity(value, context=context)
    if value.get("config_hash") in V5_REGISTERED_CONFIG_SHA256 and not is_v5:
        raise ValueError(
            f"{context} uses a registered runtime-v5 config hash without its policy identity"
        )
    return is_v5


_ACTION_QBC_ROW_FIELDS = frozenset(
    {
        "action",
        "outcome_concentration",
        "outcome_cell_count",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    }
)
_CANDIDATE_ACTION_KINDS = frozenset(f"ACTION{index}" for index in range(1, 8))


def parse_action_qbc_candidate_rows_json(
    value: object, *, context: str
) -> tuple[dict[str, Any], ...]:
    """Parse bounded controller diagnostics and apply the shared row contract."""

    if not isinstance(value, str) or not value or len(value) > 1_000_000:
        raise ValueError(f"{context} requires bounded candidate-row JSON")
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{context} candidate rows are malformed JSON") from exc
    return validate_action_qbc_candidate_rows(parsed, context=context)


def validate_action_qbc_candidate_rows(
    value: object, *, context: str
) -> tuple[dict[str, Any], ...]:
    """Validate exact row schema and policy-internal ranking semantics."""

    if not isinstance(value, list | tuple) or not 1 <= len(value) <= 12:
        raise ValueError(f"{context} requires 1-12 structured candidate rows")
    rows: list[dict[str, Any]] = []
    action_keys: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != _ACTION_QBC_ROW_FIELDS:
            raise ValueError(f"{context} candidate row {index} has an invalid schema")
        row = dict(item)
        action_key = _candidate_action_key(row["action"], context=context, index=index)
        if action_key in action_keys:
            raise ValueError(f"{context} candidate rows contain duplicate actions")
        action_keys.add(action_key)
        concentration = _bounded_float(
            row["outcome_concentration"],
            lower=0.0,
            upper=1.0,
            context=f"{context} candidate row {index} outcome_concentration",
        )
        _bounded_float(
            row["catastrophe_mass"],
            lower=0.0,
            upper=1.0,
            context=f"{context} candidate row {index} catastrophe_mass",
        )
        _bounded_float(
            row["evsi"],
            lower=0.0,
            context=f"{context} candidate row {index} evsi",
        )
        for key in ("m_utility", "x_utility"):
            _finite_float(
                row[key], context=f"{context} candidate row {index} {key}"
            )
        for key in (
            "exploit_mean_cost",
            "exploit_standard_deviation",
            "exploit_score",
        ):
            _bounded_float(
                row[key],
                lower=0.0,
                context=f"{context} candidate row {index} {key}",
            )
        cell_count = row["outcome_cell_count"]
        if (
            isinstance(cell_count, bool)
            or not isinstance(cell_count, int)
            or not 1 <= cell_count <= 4
        ):
            raise ValueError(
                f"{context} candidate row {index} has invalid outcome_cell_count"
            )
        for key in ("eligible", "m_selected", "x_selected"):
            if not isinstance(row[key], bool):
                raise ValueError(f"{context} candidate row {index} has invalid {key}")
        expected_eligibility = concentration < OUTCOME_CONCENTRATION_THRESHOLD
        if row["eligible"] is not expected_eligibility:
            raise ValueError(
                f"{context} candidate row {index} eligibility disagrees with A < 0.8"
            )
        for key in ("m_rank", "x_rank"):
            rank = row[key]
            if row["eligible"]:
                if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
                    raise ValueError(
                        f"{context} eligible candidate row {index} requires {key}"
                    )
            elif rank is not None:
                raise ValueError(
                    f"{context} ineligible candidate row {index} requires null {key}"
                )
        if (row["m_selected"] or row["x_selected"]) and not row["eligible"]:
            raise ValueError(f"{context} selected candidate rows must be eligible")
        for arm in ("m", "x"):
            if row[f"{arm}_selected"] and (
                row[f"{arm}_rank"] != 1 or float(row[f"{arm}_utility"]) <= 0.0
            ):
                raise ValueError(
                    f"{context} selected {arm.upper()} row must be rank one with "
                    "positive utility"
                )
        rows.append(row)

    eligible_count = sum(bool(row["eligible"]) for row in rows)
    expected_ranks = set(range(1, eligible_count + 1))
    for arm in ("m", "x"):
        key = f"{arm}_rank"
        observed_ranks = {row[key] for row in rows if row["eligible"]}
        if observed_ranks != expected_ranks:
            raise ValueError(
                f"{context} {key} values must be unique and sequential over eligible rows"
            )
        expected_order = tuple(
            sorted(
                (index for index, row in enumerate(rows) if row["eligible"]),
                key=lambda index: (-float(rows[index][f"{arm}_utility"]), index),
            )
        )
        for rank, index in enumerate(expected_order, start=1):
            if rows[index][key] != rank:
                raise ValueError(
                    f"{context} {key} disagrees with utility and candidate-order ranking"
                )
    if sum(bool(row["m_selected"]) for row in rows) > 1 or sum(
        bool(row["x_selected"]) for row in rows
    ) > 1:
        raise ValueError(f"{context} has multiple M or X selected candidate rows")
    return tuple(rows)


def validate_action_qbc_attribution(
    value: object,
    *,
    variant: object,
    decision_mode: object,
    decision_score: object,
    post_refresh_mode: object,
    action: object,
    decision_diagnostics: object,
    context: str,
) -> tuple[dict[str, Any], ...] | None:
    """Validate candidate presence and paired M/X decision attribution."""

    strategy_mode: object
    if decision_mode == "refresh":
        if post_refresh_mode not in {"exploit", "probe"}:
            raise ValueError(f"{context} refresh decision requires post_refresh_mode")
        strategy_mode = post_refresh_mode
    else:
        if post_refresh_mode is not None:
            raise ValueError(f"{context} post_refresh_mode is valid only for refresh")
        strategy_mode = decision_mode
    successful = variant in {"M", "X"} and strategy_mode in {"exploit", "probe"}
    if not successful:
        if value is not None:
            raise ValueError(
                f"{context} candidate rows are valid only for successful M/X planning"
            )
        return None
    rows = validate_action_qbc_candidate_rows(value, context=context)
    if not isinstance(decision_diagnostics, Mapping):
        raise ValueError(f"{context} requires structured decision diagnostics")
    diagnostic_identity = {
        key: decision_diagnostics[key]
        for key in V5_POLICY_IDENTITY_KEYS
        if key in decision_diagnostics
    }
    if not validate_v5_policy_identity(
        diagnostic_identity, context=f"{context} decision diagnostics"
    ):
        raise ValueError(f"{context} decision diagnostics lack runtime-v5 identity")
    if decision_diagnostics.get("post_refresh_mode") != post_refresh_mode:
        raise ValueError(f"{context} post-refresh attribution is inconsistent")
    diagnostic_rows = parse_action_qbc_candidate_rows_json(
        decision_diagnostics.get("action_qbc_candidate_rows"),
        context=f"{context} decision diagnostics",
    )
    if diagnostic_rows != rows:
        raise ValueError(f"{context} structured and diagnostic candidate rows differ")
    _validate_action_qbc_row_equations(
        rows, decision_diagnostics=decision_diagnostics, context=context
    )
    row_actions = {
        _candidate_action_key(row["action"], context=context, index=index): row
        for index, row in enumerate(rows)
    }
    exploit_index = min(
        range(len(rows)),
        key=lambda index: (float(rows[index]["exploit_score"]), index),
    )
    exploit_action = _candidate_action_key(
        rows[exploit_index]["action"], context=context, index=exploit_index
    )
    probe_cap = decision_diagnostics.get("probe_cap")
    probe_count_before = decision_diagnostics.get("probe_count_before")
    probe_count_after = decision_diagnostics.get("probe_count_after")
    if probe_cap != 3 or isinstance(probe_count_before, bool) or not isinstance(
        probe_count_before, int
    ) or probe_count_before < 0:
        raise ValueError(f"{context} has invalid probe-cap accounting")
    if isinstance(probe_count_after, bool) or not isinstance(probe_count_after, int):
        raise ValueError(f"{context} has invalid post-decision probe count")

    expected_by_arm: dict[str, tuple[str, str, str | None, float]] = {}
    for arm, selected_key in (("m", "m_selected"), ("x", "x_selected")):
        paired_mode = decision_diagnostics.get(f"{arm}_decision_mode")
        paired_action = decision_diagnostics.get(f"{arm}_decision_action")
        if paired_mode not in {"exploit", "probe"} or not isinstance(
            paired_action, str
        ):
            raise ValueError(f"{context} lacks the paired {arm.upper()} decision")
        if paired_action not in row_actions:
            raise ValueError(
                f"{context} paired {arm.upper()} decision action is not a candidate"
            )
        utility_key = f"{arm}_utility"
        eligible_indices = [
            index for index, row in enumerate(rows) if bool(row["eligible"])
        ]
        best_index = (
            None
            if not eligible_indices
            else min(
                eligible_indices,
                key=lambda index: (-float(rows[index][utility_key]), index),
            )
        )
        if best_index is None:
            expected_mode = "exploit"
            expected_gate = "no_disagreement_eligible_action"
            probe_candidate = None
            expected_score = float(rows[exploit_index]["exploit_score"])
        else:
            probe_candidate = _candidate_action_key(
                rows[best_index]["action"], context=context, index=best_index
            )
            best_utility = float(rows[best_index][utility_key])
            if probe_count_before >= probe_cap:
                expected_mode = "exploit"
                expected_gate = "level_probe_cap_reached"
                expected_score = float(rows[exploit_index]["exploit_score"])
            elif best_utility <= 0.0:
                expected_mode = "exploit"
                expected_gate = "nonpositive_utility"
                expected_score = float(rows[exploit_index]["exploit_score"])
            else:
                expected_mode = "probe"
                expected_gate = "selected"
                expected_score = best_utility
        expected_action = probe_candidate if expected_mode == "probe" else exploit_action
        if paired_mode != expected_mode or paired_action != expected_action:
            raise ValueError(
                f"{context} paired {arm.upper()} decision disagrees with its gate inputs"
            )
        expected_by_arm[arm] = (
            expected_mode,
            expected_gate,
            probe_candidate,
            expected_score,
        )

        selected = [row for row in rows if bool(row[selected_key])]
        if expected_mode == "probe":
            if len(selected) != 1:
                raise ValueError(
                    f"{context} paired {arm.upper()} probe requires one selected row"
                )
            selected_action = _candidate_action_key(
                selected[0]["action"], context=context, index=0
            )
            if selected_action != paired_action:
                raise ValueError(
                    f"{context} paired {arm.upper()} probe action disagrees with its row"
                )
        else:
            if selected:
                raise ValueError(
                    f"{context} paired {arm.upper()} exploit must have no selected row"
                )
    for arm in ("m", "x"):
        utility_key = f"{arm}_utility"
        eligible = [row for row in rows if bool(row["eligible"])]
        maximum = max((float(row[utility_key]) for row in eligible), default=None)
        expected_maximizers = tuple(
            _candidate_action_key(row["action"], context=context, index=index)
            for index, row in enumerate(rows)
            if row["eligible"] and float(row[utility_key]) == maximum
        )
        observed_maximizers = _parse_diagnostic_action_list(
            decision_diagnostics.get(f"{arm}_utility_maximizer_actions"),
            context=f"{context} {arm.upper()} utility maximizers",
        )
        if observed_maximizers != expected_maximizers:
            raise ValueError(
                f"{context} {arm.upper()} utility-maximizer telemetry is inconsistent"
            )

    authoritative_arm = str(variant).lower()
    authoritative_mode, authoritative_gate, probe_candidate, expected_score = (
        expected_by_arm[authoritative_arm]
    )
    if authoritative_mode != strategy_mode:
        raise ValueError(f"{context} authoritative mode disagrees with the trace")
    actual_action = _trace_action_key(action, context=context)
    if decision_diagnostics[f"{authoritative_arm}_decision_action"] != actual_action:
        raise ValueError(f"{context} authoritative action disagrees with the trace")
    if _finite_float(decision_score, context=f"{context} decision score") != expected_score:
        raise ValueError(f"{context} authoritative decision score is inconsistent")
    selected_probe = authoritative_mode == "probe"
    if (
        decision_diagnostics.get("probe_gate_reason") != authoritative_gate
        or decision_diagnostics.get("probe_selected") is not selected_probe
        or decision_diagnostics.get("probe_candidate_action") != probe_candidate
        or probe_count_after != probe_count_before + int(selected_probe)
    ):
        raise ValueError(f"{context} authoritative probe gate/accounting is inconsistent")
    expected_probe_row = (
        None
        if probe_candidate is None
        else row_actions[probe_candidate]
    )
    expected_probe_values = (
        None if expected_probe_row is None else expected_probe_row["evsi"],
        None if expected_probe_row is None else expected_probe_row["catastrophe_mass"],
        None
        if expected_probe_row is None
        else expected_probe_row[f"{authoritative_arm}_utility"],
    )
    if (
        decision_diagnostics.get("probe_evsi"),
        decision_diagnostics.get("probe_catastrophe_probability"),
        decision_diagnostics.get("probe_utility"),
    ) != expected_probe_values:
        raise ValueError(f"{context} authoritative probe headline telemetry is inconsistent")
    m_multiplier = decision_diagnostics.get("m_level_multiplier")
    x_multiplier = decision_diagnostics.get("x_level_multiplier")
    expected_level_multiplier = m_multiplier if authoritative_arm == "m" else x_multiplier
    if decision_diagnostics.get("level_multiplier") != expected_level_multiplier:
        raise ValueError(f"{context} authoritative level multiplier is inconsistent")
    return rows


def _parse_diagnostic_action_list(value: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or len(value) > 100_000:
        raise ValueError(f"{context} must be bounded JSON")
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{context} is malformed JSON") from error
    if not isinstance(parsed, list):
        raise ValueError(f"{context} must be a JSON list")
    return tuple(
        _candidate_action_key(action, context=context, index=index)
        for index, action in enumerate(parsed)
    )


def _validate_action_qbc_row_equations(
    rows: Sequence[Mapping[str, Any]],
    *,
    decision_diagnostics: Mapping[str, Any],
    context: str,
) -> None:
    m_multiplier = _finite_float(
        decision_diagnostics.get("m_level_multiplier"),
        context=f"{context} m_level_multiplier",
    )
    x_multiplier = _finite_float(
        decision_diagnostics.get("x_level_multiplier"),
        context=f"{context} x_level_multiplier",
    )
    if m_multiplier != 1.0 or x_multiplier < 1.0:
        raise ValueError(f"{context} has invalid paired level multipliers")
    for index, row in enumerate(rows):
        evsi = float(row["evsi"])
        risk = float(row["catastrophe_mass"])
        expected_m = m_multiplier * evsi - ACTION_COST - RISK_COEFFICIENT * risk
        expected_x = x_multiplier * evsi - ACTION_COST - RISK_COEFFICIENT * risk
        expected_exploit = float(row["exploit_mean_cost"]) + (
            ROBUST_STD_COEFFICIENT * float(row["exploit_standard_deviation"])
        )
        if row["m_utility"] != expected_m or row["x_utility"] != expected_x:
            raise ValueError(
                f"{context} candidate row {index} utility equation is inconsistent"
            )
        if row["exploit_score"] != expected_exploit:
            raise ValueError(
                f"{context} candidate row {index} exploit equation is inconsistent"
            )


def _candidate_action_key(value: object, *, context: str, index: int) -> str:
    if not isinstance(value, dict) or set(value) != {"kind", "row", "col"}:
        raise ValueError(f"{context} candidate row {index} has an invalid action")
    kind = value["kind"]
    row = value["row"]
    col = value["col"]
    if not isinstance(kind, str) or kind not in _CANDIDATE_ACTION_KINDS:
        raise ValueError(f"{context} candidate row {index} has an invalid action kind")
    if kind == "ACTION6":
        if not _valid_coordinate(row) or not _valid_coordinate(col):
            raise ValueError(f"{context} candidate row {index} has invalid click coordinates")
        return f"ACTION6({row},{col})"
    if row is not None or col is not None:
        raise ValueError(
            f"{context} candidate row {index} gives coordinates to a simple action"
        )
    return kind


def _trace_action_key(value: object, *, context: str) -> str:
    if not isinstance(value, Mapping) or "kind" not in value:
        raise ValueError(f"{context} has an invalid authoritative action")
    kind = value["kind"]
    if not isinstance(kind, str) or kind not in _CANDIDATE_ACTION_KINDS:
        raise ValueError(f"{context} has an invalid authoritative action kind")
    if kind == "ACTION6":
        if set(value) != {"kind", "row", "col"}:
            raise ValueError(f"{context} authoritative click action lacks coordinates")
        row, col = value["row"], value["col"]
        if not _valid_coordinate(row) or not _valid_coordinate(col):
            raise ValueError(f"{context} authoritative click coordinates are invalid")
        return f"ACTION6({row},{col})"
    if set(value) not in ({"kind"}, {"kind", "row", "col"}):
        raise ValueError(f"{context} authoritative simple action has invalid fields")
    if ("row" in value and value["row"] is not None) or (
        "col" in value and value["col"] is not None
    ):
        raise ValueError(f"{context} authoritative simple action has coordinates")
    return kind


def _valid_coordinate(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 64


def _finite_float(value: object, *, context: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"{context} must be finite")
    return float(value)


def _bounded_float(
    value: object,
    *,
    lower: float,
    context: str,
    upper: float | None = None,
) -> float:
    numeric = _finite_float(value, context=context)
    if numeric < lower or (upper is not None and numeric > upper):
        raise ValueError(f"{context} is outside its registered range")
    return numeric


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _v5_trace_attribution_matches(
    summary: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    summary_is_v5: bool,
) -> bool:
    expected = tuple(summary.get(key) for key in V5_POLICY_IDENTITY_KEYS)
    variant = summary.get("variant")
    for record in records:
        try:
            row_is_v5 = validate_v5_policy_identity(record, context="trace row")
        except ValueError:
            return False
        if row_is_v5 != summary_is_v5:
            return False
        if row_is_v5 and tuple(record.get(key) for key in V5_POLICY_IDENTITY_KEYS) != expected:
            return False
        if not row_is_v5:
            diagnostics = record.get("decision_diagnostics")
            nested_v5 = isinstance(diagnostics, Mapping) and bool(
                set(V5_POLICY_IDENTITY_KEYS).intersection(diagnostics)
                or {
                    "action_qbc_candidate_rows",
                    "m_decision_action",
                    "m_decision_mode",
                    "x_decision_action",
                    "x_decision_mode",
                }.intersection(diagnostics)
            )
            if (
                "action_qbc_candidate_rows" in record
                or "post_refresh_mode" in record
                or nested_v5
            ):
                return False
            continue
        if "post_refresh_mode" not in record or "action_qbc_candidate_rows" not in record:
            return False
        try:
            validate_action_qbc_attribution(
                record.get("action_qbc_candidate_rows"),
                variant=variant,
                decision_mode=record.get("decision_mode"),
                decision_score=record.get("decision_score"),
                post_refresh_mode=record.get("post_refresh_mode"),
                action=record.get("action"),
                decision_diagnostics=record.get("decision_diagnostics"),
                context="trace row",
            )
        except ValueError:
            return False
    return True


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
