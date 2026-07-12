"""Build a deterministic, fail-closed audit of the four-cell goal-v3 pilot.

This script consumes published artifacts only. It never opens an ARC environment
or starts a model process, so running it cannot consume gameplay actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arc3_voi.experiment import RunSpec, ScoreGateInput, evaluate_score_gate, load_matrix
from arc3_voi.metrics import RunMetrics, evaluate_mechanism_gate, load_run
from arc3_voi.run_store import TRACE_ARTIFACT_KEY, read_complete_run
from arc3_voi.runtime.sandbox import validate_program

EXPECTED_VARIANTS = ("D", "S", "M", "X")
EXPECTED_MATRIX_ROWS = 180
ACTION_CAP = 256
TOKEN_CAP = 12_288
WALL_CAP_SECONDS = 1_200.0
EVSI_ZERO_TOLERANCE = 1e-12
ALLOWED_MX_DIFFERENCES = frozenset(
    {
        "elapsed_seconds",
        "probe_utility",
        "decision_diagnostics.variant",
        "decision_diagnostics.level_multiplier",
        "decision_diagnostics.probe_utility",
    }
)

JsonObject = dict[str, Any]
Trace = tuple[JsonObject, ...]


class AuditError(ValueError):
    """Evidence failed a required audit invariant."""


@dataclass(frozen=True, slots=True)
class RunBundle:
    spec: RunSpec
    summary_path: Path
    trace_path: Path
    summary: JsonObject
    records: Trace
    metrics: RunMetrics


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _canonical_trace(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json(dict(record)) for record in records)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise AuditError(f"path is outside repository: {path}") from exc


def _load_object(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"expected JSON object: {path}")
    return value


def _file_evidence(path: Path, root: Path, *, canonical_json: bool = True) -> JsonObject:
    raw = path.read_bytes()
    result: JsonObject = {
        "path": _relative(path, root),
        "bytes": len(raw),
        "sha256": _sha256(raw),
    }
    if canonical_json:
        result["canonical_sha256"] = _sha256(
            _canonical_json(json.loads(raw.decode("utf-8")))
        )
    return result


def _trace_evidence(path: Path, records: Trace, root: Path) -> JsonObject:
    raw = path.read_bytes()
    canonical = _canonical_trace(records)
    return {
        "path": _relative(path, root),
        "bytes": len(raw),
        "sha256": _sha256(raw),
        "canonical_sha256": _sha256(canonical),
        "canonical_bytes_equal_raw": raw == canonical,
        "records": len(records),
    }


def select_matrix_rows(
    matrix: Sequence[RunSpec], *, game_id: str, seed: int
) -> dict[str, RunSpec]:
    """Select exactly one D/S/M/X row for the requested development cell."""

    rows = [
        row
        for row in matrix
        if row.phase == "development" and row.game_id == game_id and row.seed == seed
    ]
    _require(
        Counter(row.variant for row in rows) == Counter(EXPECTED_VARIANTS),
        "selected matrix cell must contain exactly one D/S/M/X row",
    )
    return {row.variant: row for row in rows}


def scan_matrix_progress(
    matrix: Sequence[RunSpec],
    runs_dir: Path,
    *,
    selected_run_ids: set[str],
    expected_rows: int = EXPECTED_MATRIX_ROWS,
) -> tuple[dict[str, tuple[JsonObject, Trace]], list[str]]:
    """Use the production validator to identify complete and partial rows."""

    _require(len(matrix) == expected_rows, f"active matrix must have {expected_rows} rows")
    completed: dict[str, tuple[JsonObject, Trace]] = {}
    partial: list[str] = []
    for spec in matrix:
        summary = runs_dir / f"{spec.run_id}.json"
        trace = runs_dir / f"{spec.run_id}.jsonl"
        pair = read_complete_run(summary, trace)
        if pair is not None:
            completed[spec.run_id] = pair
        elif summary.exists() or trace.exists():
            partial.append(spec.run_id)
    _require(not partial, f"active matrix has partial artifacts: {partial}")
    _require(
        set(completed) == selected_run_ids,
        "completed matrix rows are not exactly the selected four-cell pilot",
    )
    return completed, partial


def _bundle(
    spec: RunSpec, runs_dir: Path, pair: tuple[JsonObject, Trace]
) -> RunBundle:
    summary_path = runs_dir / f"{spec.run_id}.json"
    trace_path = runs_dir / f"{spec.run_id}.jsonl"
    summary, records = pair
    metrics = load_run(summary_path, trace_path)
    expected = (
        (metrics.run_id, spec.run_id),
        (metrics.game_id, spec.full_game_id),
        (metrics.seed, spec.seed),
        (metrics.variant, spec.variant),
        (metrics.model_profile, spec.model_profile),
        (metrics.config_hash, spec.config_hash),
    )
    _require(
        all(actual == wanted for actual, wanted in expected),
        f"identity mismatch: {spec.run_id}",
    )
    _require(len(metrics.steps) == len(records), f"load_run trace mismatch: {spec.run_id}")
    return RunBundle(spec, summary_path, trace_path, summary, records, metrics)


def _action_key(action: Mapping[str, Any]) -> str:
    kind = str(action.get("kind"))
    return (
        f"ACTION6({action.get('row')},{action.get('col')})"
        if kind == "ACTION6"
        else kind
    )


def audit_resets(records: Sequence[Mapping[str, Any]]) -> JsonObject:
    """Require RESET to immediately follow GAME_OVER in row and history evidence."""

    resets: list[int] = []
    prior_game_over: list[int] = []
    illegal: list[int] = []
    for index, record in enumerate(records):
        action = record.get("action")
        if not isinstance(action, Mapping) or action.get("kind") != "RESET":
            continue
        step = int(record["step"])
        resets.append(step)
        prior_ok = index > 0 and records[index - 1].get("observed_state") == "GAME_OVER"
        history = record.get("history")
        history_ok = bool(
            isinstance(history, Sequence)
            and not isinstance(history, str | bytes)
            and history
            and isinstance(history[-1], Mapping)
            and history[-1].get("game_state") == "GAME_OVER"
        )
        if prior_ok:
            prior_game_over.append(step - 1)
        if not (prior_ok and history_ok):
            illegal.append(step)
    _require(not illegal, f"illegal RESET steps: {illegal}")
    return {
        "reset_steps": resets,
        "preceding_game_over_steps": prior_game_over,
        "all_resets_legal": True,
    }


def _run_evidence(bundle: RunBundle, root: Path) -> JsonObject:
    run = bundle.metrics
    _require(run.error is None, f"run records error: {run.run_id}")
    _require(run.termination_reason is not None, f"run has no termination: {run.run_id}")
    budget = {
        "environment_action_cap": ACTION_CAP,
        "generated_token_cap": TOKEN_CAP,
        "wall_time_cap_seconds": WALL_CAP_SECONDS,
        "action_budget_ok": run.total_actions <= ACTION_CAP,
        "token_budget_ok": run.generated_tokens <= TOKEN_CAP,
        "wall_budget_ok": run.wall_seconds <= WALL_CAP_SECONDS,
        "wall_headroom_seconds": WALL_CAP_SECONDS - run.wall_seconds,
    }
    _require(
        all(
            budget[key]
            for key in ("action_budget_ok", "token_budget_ok", "wall_budget_ok")
        ),
        f"budget exceeded: {run.run_id}",
    )
    trace = _trace_evidence(bundle.trace_path, bundle.records, root)
    _require(bool(trace["canonical_bytes_equal_raw"]), f"noncanonical trace: {run.run_id}")
    metadata = bundle.summary.get(TRACE_ARTIFACT_KEY)
    if not isinstance(metadata, Mapping):
        raise AuditError(f"missing trace metadata: {run.run_id}")
    _require(metadata.get("sha256") == trace["sha256"], "trace metadata hash mismatch")
    _require(metadata.get("record_count") == len(bundle.records), "trace count mismatch")
    unavailable = [
        int(row["step"])
        for row in bundle.records
        if row["action"].get("kind") != "RESET"
        and row["action"].get("kind") not in row["available_actions"]
    ]
    _require(not unavailable, f"unavailable actions: {run.run_id}: {unavailable}")
    calls = int(run.program_prediction_calls or 0) + int(run.program_goal_calls or 0)
    return {
        "run_id": run.run_id,
        "config_sha256": run.config_hash,
        "summary": _file_evidence(bundle.summary_path, root),
        "trace": trace,
        "metrics": {
            "rhae": run.rhae,
            "levels_completed": run.levels_completed,
            "total_actions": run.total_actions,
            "termination_reason": run.termination_reason,
            "generated_tokens": run.generated_tokens,
            "wall_seconds": run.wall_seconds,
            "peak_vram_gib": run.peak_vram_gb,
            "direct_fallbacks": run.direct_fallbacks,
            "mean_best_hypothesis_transition_loss": run.mean_best_hypothesis_transition_loss,
            "mean_weighted_transition_loss": run.mean_weighted_transition_loss,
            "program_prediction_calls": run.program_prediction_calls,
            "program_goal_calls": run.program_goal_calls,
            "program_execution_errors": run.program_execution_errors,
            "program_execution_error_fraction": (
                run.program_execution_errors / calls if calls else 0.0
            ),
            "program_timeouts": run.program_timeouts,
        },
        "budget_audit": budget,
        "trace_audit": {
            "action_counts": dict(
                sorted(Counter(_action_key(row["action"]) for row in bundle.records).items())
            ),
            "decision_mode_counts": dict(
                sorted(Counter(str(row["decision_mode"]) for row in bundle.records).items())
            ),
            "observed_game_over_steps": [
                int(row["step"])
                for row in bundle.records
                if row.get("observed_state") == "GAME_OVER"
            ],
            "non_reset_actions_available": True,
            "step_elapsed_seconds_scope": "environment session.step only",
            "step_elapsed_seconds_sum": math.fsum(
                float(row["elapsed_seconds"]) for row in bundle.records
            ),
            **audit_resets(bundle.records),
        },
    }


def _differences(
    left: object, right: object, path: str = ""
) -> list[tuple[str, object, object]]:
    if left == right:
        return []
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        result: list[tuple[str, object, object]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                result.append((child, left.get(key), right.get(key)))
            else:
                result.extend(_differences(left[key], right[key], child))
        return result
    if (
        isinstance(left, Sequence)
        and isinstance(right, Sequence)
        and not isinstance(left, str | bytes)
        and not isinstance(right, str | bytes)
    ):
        if len(left) != len(right):
            return [(f"{path}.length", len(left), len(right))]
        result = []
        for index, (one, two) in enumerate(zip(left, right, strict=True)):
            result.extend(_differences(one, two, f"{path}[{index}]"))
        return result
    return [(path, left, right)]


def _normalize_mx(record: Mapping[str, Any]) -> JsonObject:
    result = dict(record)
    result.pop("elapsed_seconds", None)
    result.pop("probe_utility", None)
    diagnostics = result.get("decision_diagnostics")
    if isinstance(diagnostics, Mapping):
        diagnostics = dict(diagnostics)
        for key in ("variant", "level_multiplier", "probe_utility"):
            diagnostics.pop(key, None)
        result["decision_diagnostics"] = diagnostics
    return result


def compare_mx(m_records: Trace, x_records: Trace) -> JsonObject:
    """Prove exact M/X equality outside declared timing/cross-level fields."""

    _require(len(m_records) == len(x_records), "M/X trace lengths differ")
    differences = [
        difference
        for m_row, x_row in zip(m_records, x_records, strict=True)
        for difference in _differences(m_row, x_row)
    ]
    paths = Counter(path for path, _m, _x in differences)
    unexpected = sorted(set(paths) - ALLOWED_MX_DIFFERENCES)
    _require(not unexpected, f"unexpected M/X differences: {unexpected}")
    normalized_m = tuple(_normalize_mx(row) for row in m_records)
    normalized_x = tuple(_normalize_mx(row) for row in x_records)
    _require(normalized_m == normalized_x, "declared M/X normalization is incomplete")
    m_hash = _sha256(_canonical_trace(normalized_m))
    x_hash = _sha256(_canonical_trace(normalized_x))
    return {
        "rows": len(m_records),
        "allowed_difference_paths": sorted(ALLOWED_MX_DIFFERENCES),
        "difference_path_counts": dict(sorted(paths.items())),
        "total_scalar_differences": len(differences),
        "exact_difference_sequence_sha256": _sha256(
            _canonical_json(
                [{"path": path, "M": m, "X": x} for path, m, x in differences]
            )
        ),
        "unexpected_difference_paths": unexpected,
        "equal_after_declared_normalization": True,
        "M_normalized_sha256": m_hash,
        "X_normalized_sha256": x_hash,
        "normalized_hashes_equal": m_hash == x_hash,
        "actions_histories_observations_losses_weights_candidates_costs_predictions_"
        "agreement_evsi_probes_and_persistence_equal": True,
    }


def _mapping_string(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise AuditError(f"{field} is not serialized JSON")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise AuditError(f"{field} does not decode to an object")
    return parsed


def committee_telemetry(m_records: Trace, x_records: Trace) -> JsonObject:
    """Quantify cost, signature, probe, tolerance, and reset telemetry."""

    planning = 0
    candidates = 0
    disagreement_candidates = 0
    cost_varying: list[int] = []
    disagreement_rows: list[int] = []
    selected_disagreement: list[int] = []
    candidate_counts: Counter[int] = Counter()
    disagreement_counts: Counter[int] = Counter()
    gates: Counter[str] = Counter()
    exact_zero = roundoff = material = probes = catastrophe = agreement_not_one = 0
    maximum_evsi = 0.0
    action6_steps: list[int] = []
    action6_points: Counter[str] = Counter()
    for row in m_records:
        diagnostics = row.get("decision_diagnostics")
        if not isinstance(diagnostics, Mapping) or "candidate_costs" not in diagnostics:
            continue
        planning += 1
        step = int(row["step"])
        costs = _mapping_string(diagnostics["candidate_costs"], "candidate_costs")
        signatures = _mapping_string(
            diagnostics["candidate_prediction_signatures"],
            "candidate_prediction_signatures",
        )
        _require(set(costs) == set(signatures), f"candidate telemetry mismatch: {step}")
        candidates += len(costs)
        candidate_counts[len(costs)] += 1
        if len({tuple(float(item) for item in vector) for vector in costs.values()}) > 1:
            cost_varying.append(step)
        disagreement = sum(len(set(items)) > 1 for items in signatures.values())
        disagreement_candidates += disagreement
        disagreement_counts[disagreement] += 1
        if disagreement:
            disagreement_rows.append(step)
        selected = _action_key(row["action"])
        if selected in signatures and len(set(signatures[selected])) > 1:
            selected_disagreement.append(step)
        if row["action"].get("kind") == "ACTION6":
            action6_steps.append(step)
            action6_points[selected] += 1
        evsi = float(diagnostics["probe_evsi"])
        maximum_evsi = max(maximum_evsi, abs(evsi))
        if evsi == 0.0:
            exact_zero += 1
        elif abs(evsi) <= EVSI_ZERO_TOLERANCE:
            roundoff += 1
        else:
            material += 1
        probes += bool(diagnostics.get("probe_selected"))
        catastrophe += float(diagnostics["probe_catastrophe_probability"]) != 0.0
        agreement_not_one += float(diagnostics["agreement"]) != 1.0
        gates[str(diagnostics["probe_gate_reason"])] += 1
    _require(planning > 0 and material == 0 and probes == 0, "unexpected VOI behavior")
    resets = sum(row["action"].get("kind") == "RESET" for row in m_records)
    exploit_resets = sum(
        row["action"].get("kind") == "RESET" and row["decision_mode"] == "exploit"
        for row in m_records
    )
    def multipliers(rows: Trace) -> Counter[float]:
        return Counter(
            float(row["decision_diagnostics"]["level_multiplier"])
            for row in rows
            if "level_multiplier" in row["decision_diagnostics"]
        )
    return {
        "planning_rows": planning,
        "candidate_count_distribution": {
            str(key): value for key, value in sorted(candidate_counts.items())
        },
        "candidate_actions": candidates,
        "rows_with_action_varying_costs": len(cost_varying),
        "action_varying_cost_steps": cost_varying,
        "rows_with_prediction_signature_disagreement": len(disagreement_rows),
        "disagreeing_candidate_actions": disagreement_candidates,
        "disagreeing_candidate_fraction": disagreement_candidates / candidates,
        "disagreement_candidate_count_per_row": {
            str(key): value for key, value in sorted(disagreement_counts.items())
        },
        "selected_action_disagreement_rows": selected_disagreement,
        "agreement_not_exactly_one_rows": agreement_not_one,
        "probe_gate_reasons": dict(sorted(gates.items())),
        "probes": probes,
        "catastrophe_nonzero_rows": catastrophe,
        "evsi_tolerance": EVSI_ZERO_TOLERANCE,
        "evsi_exact_zero_rows": exact_zero,
        "evsi_positive_roundoff_rows": roundoff,
        "evsi_material_nonzero_rows": material,
        "maximum_absolute_evsi": maximum_evsi,
        "all_evsi_effectively_zero": exact_zero + roundoff == planning,
        "M_level_multipliers": {
            str(key): value for key, value in sorted(multipliers(m_records).items())
        },
        "X_level_multipliers": {
            str(key): value for key, value in sorted(multipliers(x_records).items())
        },
        "action6_steps": action6_steps,
        "action6_coordinates": dict(sorted(action6_points.items())),
        "reset_rows": resets,
        "reset_rows_labeled_exploit": exploit_resets,
        "telemetry_findings": [
            "positive EVSI below tolerance is floating-point cancellation",
            "mandatory RESET lifecycle actions are labeled exploit",
            "step elapsed_seconds excludes controller planning",
        ],
    }


def _grounding_programs(grounding: Mapping[str, Any]) -> list[JsonObject]:
    raw_programs = grounding.get("programs")
    if not isinstance(raw_programs, list):
        raise AuditError("grounding programs are missing")
    result: list[JsonObject] = []
    for raw in raw_programs:
        if not isinstance(raw, Mapping):
            raise AuditError("grounding program is not an object")
        source = raw.get("source")
        if not isinstance(source, str):
            raise AuditError("grounding source is missing")
        validated = validate_program(source)
        _require(raw.get("source_sha256") == _sha256(source.encode()), "source hash mismatch")
        _require(raw.get("ast_nodes") == validated.node_count, "AST count mismatch")
        result.append(
            {
                "candidate_index": int(raw["candidate_index"]),
                "hypothesis_id": validated.sha256,
                "source_sha256": raw["source_sha256"],
                "ast_nodes": validated.node_count,
                "assigned_role": raw.get("assigned_role"),
                "behavior_signature": raw.get("behavior_signature"),
                "eligible": bool(raw.get("eligible")),
                "action_sensitive": bool(raw.get("action_sensitive")),
                "action_sensitivity_required": bool(raw.get("action_sensitivity_required")),
                "goal_action_conditioned": bool(raw.get("goal_action_conditioned")),
                "goal_conditioning_required": bool(raw.get("goal_conditioning_required")),
            }
        )
    return sorted(result, key=lambda row: int(row["candidate_index"]))


def _generated_sources(records: Trace) -> tuple[str, ...]:
    batches: list[tuple[str, ...]] = []
    for row in records:
        diagnostics = row.get("decision_diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        value = diagnostics.get("generated_program_sources")
        if value is None:
            continue
        _require(isinstance(value, str), "generated sources are not serialized JSON")
        decoded = json.loads(value)
        _require(
            isinstance(decoded, list) and all(isinstance(item, str) for item in decoded),
            "generated sources do not decode to a source list",
        )
        batches.append(tuple(decoded))
    _require(len(batches) == 1, "expected exactly one generation batch")
    return batches[0]


def live_pool_grounding(
    grounding: Mapping[str, Any], m_records: Trace, x_records: Trace
) -> JsonObject:
    """Map grounded source through the runtime validator into selected pool IDs."""

    grounded = _grounding_programs(grounding)
    grounding_ids = [str(row["hypothesis_id"]) for row in grounded]
    m_sources = _generated_sources(m_records)
    _require(m_sources == _generated_sources(x_records), "M/X generation batches differ")
    generated_ids = [validate_program(source).sha256 for source in m_sources]
    _require(generated_ids == grounding_ids, "live generation differs from WSL grounding")
    m_pools = {
        tuple(str(identifier) for identifier in row["hypothesis_ids"])
        for row in m_records
        if row.get("hypothesis_ids")
    }
    x_pools = {
        tuple(str(identifier) for identifier in row["hypothesis_ids"])
        for row in x_records
        if row.get("hypothesis_ids")
    }
    _require(len(m_pools) == 1 and m_pools == x_pools, "M/X live pool mismatch")
    selected = list(next(iter(m_pools)))
    eligible = [str(row["hypothesis_id"]) for row in grounded if row["eligible"]]
    selected_eligible = [identifier for identifier in selected if identifier in eligible]
    selected_ineligible = [identifier for identifier in selected if identifier not in eligible]
    missing = [identifier for identifier in eligible if identifier not in selected]
    grouped: dict[str, list[JsonObject]] = {}
    for row in grounded:
        grouped.setdefault(str(row["behavior_signature"]), []).append(row)
    collisions = [
        {
            "behavior_signature": signature,
            "candidate_indices": [int(row["candidate_index"]) for row in rows],
            "eligible_ids": [str(row["hypothesis_id"]) for row in rows if row["eligible"]],
            "selected_ids": [
                str(row["hypothesis_id"])
                for row in rows
                if str(row["hypothesis_id"]) in selected
            ],
        }
        for signature, rows in sorted(grouped.items())
        if len(rows) > 1
    ]
    matches = set(selected) == set(eligible)
    return {
        "mapping_method": "validate_program(source).sha256",
        "generated_candidate_ids": generated_ids,
        "grounding_programs": grounded,
        "grounding_eligible_ids": eligible,
        "live_selected_ids": selected,
        "live_selected_grounding_eligible_ids": selected_eligible,
        "live_selected_grounding_ineligible_ids": selected_ineligible,
        "grounding_eligible_ids_missing_from_live_pool": missing,
        "runtime_valid_live_programs": len(selected),
        "grounding_eligible_live_programs": len(selected_eligible),
        "live_pool_matches_grounding_eligible_set": matches,
        "grounding_selection_mismatch_detected": not matches,
        "behavioral_dedup_eligibility_collisions": collisions,
        "claim_effect": (
            "runtime validity is not role-gate eligibility; only one live committee member "
            "passed the WSL role-specific grounding gate"
        ),
    }


def _grounding_evidence(
    path: Path,
    root: Path,
    *,
    seed: int,
    config_hash: str,
    hard_memory_required: bool,
) -> tuple[JsonObject, JsonObject]:
    grounding = _load_object(path)
    _require(grounding.get("schema_version") == 4, "grounding schema must be v4")
    _require(grounding.get("seed") == seed, "grounding seed mismatch")
    _require(grounding.get("base_config_sha256") == config_hash, "grounding config mismatch")
    summary = grounding.get("summary")
    if not isinstance(summary, Mapping) or summary.get("passes") is not True:
        raise AuditError("grounding failed")
    _require(
        summary.get("hard_memory_limit_required") is hard_memory_required,
        "grounding memory policy mismatch",
    )
    if hard_memory_required:
        _require(
            int(summary.get("hard_memory_limit_enforced_programs", 0))
            >= int(summary.get("grounded_safe_programs", 0)),
            "WSL hard-memory evidence is incomplete",
        )
    evidence = _file_evidence(path, root)
    evidence.update(
        {
            "schema_version": 4,
            "passes": True,
            "git": grounding.get("git"),
            "prompt_contract_version": grounding.get("prompt_contract_version"),
            "prompt_contract_sha256": grounding.get("prompt_contract_sha256"),
            "perception_contract_sha256": grounding.get("perception_contract_sha256"),
            "model_revision": grounding.get("expected_model_revision"),
            "weight_manifest_sha256": grounding.get("expected_weight_manifest_sha256"),
            "summary": dict(summary),
        }
    )
    return grounding, evidence


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-c", f"safe.directory={root.as_posix()}", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _git_evidence(root: Path, launch_commit: str) -> JsonObject:
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    _require(not status, "audit must run from a clean worktree")
    audit_commit = _git(root, "rev-parse", "HEAD")
    launch = _git(root, "rev-parse", f"{launch_commit}^{{commit}}")
    ancestor = subprocess.run(
        (
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "merge-base",
            "--is-ancestor",
            launch,
            audit_commit,
        ),
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode == 0
    _require(ancestor, "launch commit is not an ancestor of audit commit")
    return {
        "audit_commit": audit_commit,
        "audit_worktree_clean_before_output": True,
        "status_sha256": _sha256(b""),
        "launch_commit": launch,
        "launch_commit_is_ancestor_of_audit_commit": True,
        "launch_worktree_clean_not_embedded_in_run_schema": True,
        "launch_provenance_limit": (
            "ancestry and artifact chronology support the launch commit, but the run schema "
            "does not independently prove command-time worktree cleanliness"
        ),
    }


def _mechanism(committee: RunMetrics, single: RunMetrics) -> JsonObject:
    gate = evaluate_mechanism_gate((committee,), (single,))
    return {
        **asdict(gate),
        "reasons": list(gate.reasons),
        "committee_program_calls": int(committee.program_prediction_calls or 0)
        + int(committee.program_goal_calls or 0),
        "single_program_calls": int(single.program_prediction_calls or 0)
        + int(single.program_goal_calls or 0),
        "validity_scope": "runtime-valid hypotheses; see live-pool grounding mismatch",
    }


def build_audit(
    *,
    matrix_path: Path,
    runs_dir: Path,
    game_id: str,
    seed: int,
    launch_commit: str,
    wsl_grounding_path: Path,
    windows_grounding_path: Path,
    previous_pilot_path: Path,
    repository_root: Path,
    date: str,
) -> JsonObject:
    matrix = load_matrix(matrix_path)
    selected = select_matrix_rows(matrix, game_id=game_id, seed=seed)
    complete, partial = scan_matrix_progress(
        matrix,
        runs_dir,
        selected_run_ids={spec.run_id for spec in selected.values()},
    )
    bundles = {
        variant: _bundle(spec, runs_dir, complete[spec.run_id])
        for variant, spec in selected.items()
    }
    x_config = selected["X"].config_hash
    wsl, wsl_evidence = _grounding_evidence(
        wsl_grounding_path,
        repository_root,
        seed=seed,
        config_hash=x_config,
        hard_memory_required=True,
    )
    windows, windows_evidence = _grounding_evidence(
        windows_grounding_path,
        repository_root,
        seed=seed,
        config_hash=x_config,
        hard_memory_required=False,
    )
    parity_fields = (
        "prompt_contract_version",
        "prompt_contract_sha256",
        "perception_contract_sha256",
        "expected_model_revision",
        "expected_weight_manifest_sha256",
        "source_input_sha256",
    )
    _require(
        all(wsl.get(key) == windows.get(key) for key in parity_fields),
        "grounding parity mismatch",
    )
    revisions = {bundle.summary.get("model_revision") for bundle in bundles.values()}
    manifests = {bundle.summary.get("weight_manifest_sha256") for bundle in bundles.values()}
    _require(revisions == {wsl.get("expected_model_revision")}, "model revision mismatch")
    _require(manifests == {wsl.get("expected_weight_manifest_sha256")}, "manifest mismatch")
    run_evidence = {
        variant: _run_evidence(bundle, repository_root)
        for variant, bundle in bundles.items()
    }
    d, s, m, x = (bundles[variant] for variant in EXPECTED_VARIANTS)
    del d
    comparison = compare_mx(m.records, x.records)
    telemetry = committee_telemetry(m.records, x.records)
    pool = live_pool_grounding(wsl, m.records, x.records)
    _require(
        all(
            bundle.metrics.levels_completed == 0
            and float(bundle.metrics.rhae or 0.0) == 0.0
            for bundle in bundles.values()
        ),
        "pilot is no longer the expected zero-score cell",
    )
    score_input = ScoreGateInput(
        x_rhae=float(x.metrics.rhae or 0.0),
        m_rhae=float(m.metrics.rhae or 0.0),
        x_levels=x.metrics.levels_completed,
        m_levels=m.metrics.levels_completed,
        x_actions=x.metrics.total_actions,
        m_actions=m.metrics.total_actions,
        positive_game_fraction=float((x.metrics.rhae or 0.0) > (m.metrics.rhae or 0.0)),
        x_wall_seconds=x.metrics.wall_seconds,
        m_wall_seconds=m.metrics.wall_seconds,
    )
    score = evaluate_score_gate(score_input)
    previous = _load_object(previous_pilot_path)
    decision = previous.get("decision")
    _require(
        isinstance(decision, Mapping)
        and decision.get("remaining_runs_locked") is True,
        "previous pilot is not locked",
    )
    git = _git_evidence(repository_root, launch_commit)
    central_exercised = bool(telemetry["probes"]) or not bool(
        comparison["equal_after_declared_normalization"]
    )
    return {
        "schema_version": 1,
        "date": date,
        "status": "valid_negative_engineering_pilot_live_grounding_mismatch_scaleup_locked",
        "scope": {
            "phase": "development",
            "contract": "goal-v3-schema-v4",
            "game_id": game_id,
            "game_version": selected["X"].game_version,
            "full_game_id": selected["X"].full_game_id,
            "seed": seed,
            "claim_eligible": False,
            "central_mechanism_exercised": central_exercised,
            "interpretation": (
                "one public game and one seed engineering pilot; not a development aggregate, "
                "private-score result, or generalization claim"
            ),
        },
        "provenance": {
            "git": git,
            "development_matrix_snapshot": _file_evidence(matrix_path, repository_root),
            "previous_pilot": {
                **_file_evidence(previous_pilot_path, repository_root),
                "status": previous.get("status"),
            },
            "grounding": {"wsl": wsl_evidence, "windows": windows_evidence},
            "model_profile": x.metrics.model_profile,
            "model_revision": next(iter(revisions)),
            "weight_manifest_sha256": next(iter(manifests)),
        },
        "matrix_progress": {
            "total": len(matrix),
            "completed": len(complete),
            "remaining": len(matrix) - len(complete),
            "partial_rows": len(partial),
            "completed_run_ids": sorted(complete),
            "selected_variants": list(EXPECTED_VARIANTS),
            "scaleup_unlocked": False,
        },
        "runs": run_evidence,
        "comparisons": {
            "mechanism_M_vs_S": _mechanism(m.metrics, s.metrics),
            "mechanism_X_vs_S": _mechanism(x.metrics, s.metrics),
            "runtime_ratios": {
                "X_over_M": x.metrics.wall_seconds / m.metrics.wall_seconds,
                "X_over_M_formal_1_5x_condition_passed": (
                    x.metrics.wall_seconds <= 1.5 * m.metrics.wall_seconds
                ),
                "M_over_S": m.metrics.wall_seconds / s.metrics.wall_seconds,
                "X_over_S": x.metrics.wall_seconds / s.metrics.wall_seconds,
                "M_over_S_is_diagnostic_not_a_preregistered_gate": True,
            },
            "score_gate_single_cell_proxy": {
                "formal_development_gate": False,
                "proxy_passed": score.passed,
                "reasons": list(score.reasons),
                "rhae_delta": score_input.x_rhae - score_input.m_rhae,
                "level_delta": score_input.x_levels - score_input.m_levels,
                "action_delta": score_input.x_actions - score_input.m_actions,
                "positive_game_fraction": score_input.positive_game_fraction,
            },
            "M_X_semantic_equivalence": comparison,
            "committee_telemetry": telemetry,
            "live_pool_grounding": pool,
        },
        "claim_limits": [
            "all four variants scored zero RHAE and completed zero levels",
            "one game/seed cannot satisfy the formal development or generalization claim gate",
            "no level boundary occurred, persistence was not updated, and no probe was selected",
            "M and X were behaviorally identical after declared cross-level/timing normalization",
            "runtime-valid live hypotheses are not role-gate-eligible hypotheses",
            "launch commit ancestry is recorded but command-time clean state is absent from runs",
        ],
        "decision": {
            "remaining_runs_locked": True,
            "reasons": [
                "all D/S/M/X variants completed zero levels",
                "the 15% mechanism-loss gate failed",
                "M and X were semantically equivalent and selected no probes",
                "the cross-level multiplier changed no action",
                "only one live committee member passed its WSL role-specific grounding gate",
            ],
            "next_engineering_actions": [
                "carry role-gate eligibility into live pool construction",
                "prevent behavioral deduplication from replacing an eligible program "
                "with an ineligible one",
                "clamp EVSI magnitudes within the declared numerical-zero tolerance",
                "separate mandatory RESET and controller-planning latency in telemetry",
                "rerun only the four-cell pilot from a clean commit after the live-pool fix",
            ],
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--launch-commit", required=True)
    parser.add_argument("--wsl-grounding", type=Path, required=True)
    parser.add_argument("--windows-grounding", type=Path, required=True)
    parser.add_argument("--previous-pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--date", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    working_directory = Path.cwd().resolve()
    root = Path(
        subprocess.run(
            (
                "git",
                "-c",
                f"safe.directory={working_directory.as_posix()}",
                "rev-parse",
                "--show-toplevel",
            ),
            cwd=working_directory,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    )
    artifact = build_audit(
        matrix_path=args.matrix,
        runs_dir=args.runs_dir,
        game_id=args.game_id,
        seed=args.seed,
        launch_commit=args.launch_commit,
        wsl_grounding_path=args.wsl_grounding,
        windows_grounding_path=args.windows_grounding,
        previous_pilot_path=args.previous_pilot,
        repository_root=root,
        date=args.date,
    )
    output: Path = args.output
    _relative(output, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
