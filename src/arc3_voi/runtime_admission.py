"""Deterministic, fail-closed admission audit for costly gameplay pilots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from math import isclose
from pathlib import Path
from typing import Any, cast

from .candidates import candidates_from_history
from .config import SystemConfig
from .experiment import stable_config_hash
from .grounding import ProgramGroundingResult, evaluate_program_grounding
from .hypothesis import HypothesisPool, behavioral_deduplicate
from .planner import (
    BeamSearchPlanner,
    NoValidHypotheses,
    PlanningError,
    PlanningSnapshot,
    catastrophe_probability,
    committee_agreement,
    committee_indifference,
    level_multiplier,
    probe_utility,
    weighted_evsi,
)
from .program import ExecutableHypothesis, candidate_points_from_source
from .provenance import inspect_git_provenance
from .replay import history_from_records
from .runtime.sandbox import validate_program
from .types import Action, ActionKind, History, Prediction

ADMISSION_CONTRACT_VERSION = "runtime-admission-v1"
MATERIAL_EVSI_THRESHOLD = 0.05
INITIAL_CROSS_LEVEL_PERSISTENCE = 0.5


@dataclass(frozen=True, slots=True)
class EvaluatedSource:
    """One source program and its current-code role-specific grounding result."""

    candidate_index: int
    assigned_role: str
    source: str
    hypothesis_id: str | None
    result: ProgramGroundingResult


HypothesisFactory = Callable[..., ExecutableHypothesis]


def role_requirements(candidate_index: int) -> tuple[bool, bool]:
    """Return action-sensitivity and goal-conditioning requirements by source role."""

    if isinstance(candidate_index, bool) or candidate_index < 0:
        raise ValueError("candidate_index must be a non-negative integer")
    discriminative_role = candidate_index > 0
    return discriminative_role, discriminative_role


def evaluate_source_programs(
    source_rows: Sequence[Mapping[str, Any]],
    history: History,
    actions: Sequence[Action],
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
    rollout_depth: int,
) -> tuple[EvaluatedSource, ...]:
    """Re-evaluate artifact sources under current role requirements.

    ``evaluate_program_grounding`` owns only transient workers. Persistent workers
    are deliberately constructed later, after this eligibility boundary.
    """

    evaluated: list[EvaluatedSource] = []
    for expected_index, row in enumerate(source_rows):
        index = row.get("candidate_index")
        if index != expected_index:
            raise ValueError("source candidate indices must be contiguous and ordered")
        source = row.get("source")
        role = row.get("assigned_role")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"candidate {expected_index} has no source program")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"candidate {expected_index} has no assigned role")
        declared_sha = row.get("source_sha256")
        actual_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if declared_sha != actual_sha:
            raise ValueError(f"candidate {expected_index} source digest mismatch")
        require_sensitivity, require_goal = role_requirements(expected_index)
        try:
            hypothesis_id = validate_program(source).sha256
        except Exception:
            hypothesis_id = None
        result = evaluate_program_grounding(
            source,
            history,
            actions,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            rollout_depth=rollout_depth,
            require_action_sensitivity=require_sensitivity,
            require_goal_conditioning=require_goal,
        )
        evaluated.append(
            EvaluatedSource(expected_index, role, source, hypothesis_id, result)
        )
    return tuple(evaluated)


def construct_eligible_hypotheses(
    evaluated: Sequence[EvaluatedSource],
    history: History,
    actions: Sequence[Action],
    *,
    timeout_seconds: float,
    memory_limit_mb: int,
    max_hypotheses: int,
    hypothesis_factory: HypothesisFactory = ExecutableHypothesis,
) -> tuple[tuple[ExecutableHypothesis, ...], tuple[str, ...]]:
    """Construct persistent workers only for eligible sources, then deduplicate.

    The caller owns the returned hypotheses. Workers excluded by behavioral
    deduplication are closed here.
    """

    constructed: list[ExecutableHypothesis] = []
    for item in evaluated:
        if not item.result.eligible:
            continue
        if item.hypothesis_id is None:
            raise ValueError("eligible grounding result has no canonical hypothesis ID")
        hypothesis = hypothesis_factory(
            item.source,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
        )
        if hypothesis.hypothesis_id != item.hypothesis_id:
            hypothesis.close()
            raise ValueError("persistent hypothesis digest differs from grounding result")
        constructed.append(hypothesis)
    try:
        selected = cast(
            tuple[ExecutableHypothesis, ...],
            behavioral_deduplicate(
                constructed,
                history,
                actions,
                max_hypotheses=max_hypotheses,
            ),
        )
    except Exception:
        for hypothesis in constructed:
            hypothesis.close()
        raise
    selected_objects = {id(hypothesis) for hypothesis in selected}
    removed_ids: list[str] = []
    for hypothesis in constructed:
        if id(hypothesis) not in selected_objects:
            removed_ids.append(hypothesis.hypothesis_id)
            hypothesis.close()
    return tuple(selected), tuple(removed_ids)


def admission_gate_reasons(
    *,
    selected_ids: Sequence[str],
    eligible_ids: Sequence[str],
    distinct_selected_behaviors: int,
    planner_invalid_ids: Sequence[str],
    agreement: float | None,
    differing_optimal_sets: bool,
    maximum_evsi: float,
    maximum_cross_level_utility: float,
    agreement_threshold: float,
    material_evsi_threshold: float = MATERIAL_EVSI_THRESHOLD,
) -> tuple[str, ...]:
    """Apply the conservative admission gate without any runtime side effects."""

    reasons: list[str] = []
    ineligible_selected = sorted(set(selected_ids) - set(eligible_ids))
    if len(selected_ids) < 2:
        reasons.append("fewer than two eligible programs survived behavioral deduplication")
    if ineligible_selected:
        reasons.append("one or more selected programs failed role-specific grounding")
    if distinct_selected_behaviors < 2:
        reasons.append("fewer than two distinct selected behavior classes")
    if planner_invalid_ids:
        reasons.append("one or more selected programs became invalid during depth-four planning")

    low_agreement_with_positive_utility = (
        agreement is not None
        and agreement < agreement_threshold
        and maximum_evsi >= material_evsi_threshold
        and maximum_cross_level_utility > 0.0
    )
    differing_decisions_with_information = (
        differing_optimal_sets and maximum_evsi >= material_evsi_threshold
    )
    if not (
        low_agreement_with_positive_utility or differing_decisions_with_information
    ):
        reasons.append(
            "no material decision diversity: require low agreement with positive "
            "cross-level utility, or differing optimal sets with material EVSI"
        )
    return tuple(reasons)


def run_runtime_admission_audit(
    *,
    grounding_artifact_path: Path,
    fixture_path: Path,
    config: SystemConfig,
) -> dict[str, Any]:
    """Re-run grounding, selection, and planning without model or environment calls."""

    grounding_artifact = _load_json_object(grounding_artifact_path)
    fixture = _load_json_object(fixture_path)
    if grounding_artifact.get("schema_version") != 4:
        raise ValueError("runtime admission requires a schema-v4 grounding artifact")
    if fixture.get("schema_version") != 1:
        raise ValueError("runtime admission requires a schema-v1 history fixture")
    _validate_contract_identity(grounding_artifact, config)

    fixture_sha = _file_sha256(fixture_path)
    declared_fixture_sha = grounding_artifact.get("source_input_sha256")
    if declared_fixture_sha != fixture_sha:
        raise ValueError("grounding artifact and history fixture digests differ")
    records = _fixture_history_records(fixture)
    history_payload = json.dumps(records, separators=(",", ":"), sort_keys=True).encode()
    history_sha = hashlib.sha256(history_payload).hexdigest()
    if fixture.get("history_canonical_sha256") != history_sha:
        raise ValueError("history fixture does not match its declared digest")
    if grounding_artifact.get("history_canonical_sha256") != history_sha:
        raise ValueError("grounding artifact was produced from a different history")
    history = history_from_records(records)

    raw_programs = grounding_artifact.get("programs")
    if not isinstance(raw_programs, list) or not raw_programs:
        raise ValueError("grounding artifact has no source programs")
    source_rows: tuple[Mapping[str, Any], ...] = tuple(
        _require_mapping(row, "program") for row in raw_programs
    )
    cached_points = tuple(
        point
        for row in source_rows
        for point in candidate_points_from_source(str(row["source"]))
    )
    actions = candidates_from_history(
        history,
        cached_points=cached_points,
        max_candidates=config.planning.max_candidates,
    )
    timeout_seconds = config.sandbox.timeout_ms / 1000.0
    evaluated = evaluate_source_programs(
        source_rows,
        history,
        actions,
        timeout_seconds=timeout_seconds,
        memory_limit_mb=config.sandbox.memory_mb,
        rollout_depth=config.planning.depth,
    )
    eligible_ids = tuple(
        item.hypothesis_id
        for item in evaluated
        if item.result.eligible and item.hypothesis_id is not None
    )
    selected: tuple[ExecutableHypothesis, ...] = ()
    deduplicated_ids: tuple[str, ...] = ()
    snapshot: PlanningSnapshot | None = None
    planner_error: str | None = None
    try:
        selected, deduplicated_ids = construct_eligible_hypotheses(
            evaluated,
            history,
            actions,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=config.sandbox.memory_mb,
            max_hypotheses=config.hypotheses.max_hypotheses,
        )
        if selected:
            pool = HypothesisPool.from_hypotheses(
                selected,
                eta=config.hypotheses.eta,
                complexity_lambda=config.hypotheses.complexity_lambda,
                max_hypotheses=config.hypotheses.max_hypotheses,
            )
            try:
                snapshot = BeamSearchPlanner(
                    depth=config.planning.depth,
                    beam_width=config.planning.beam_width,
                    parallel_hypotheses=False,
                ).evaluate(
                    history,
                    actions,
                    pool.weighted_hypotheses,
                    win_levels=int(records[-1]["win_levels"]),
                )
            except NoValidHypotheses as exc:
                planner_error = str(exc)
                snapshot = None
                planner_invalid_ids = tuple(exc.invalid_hypothesis_ids)
            except PlanningError as exc:
                planner_error = str(exc)
                snapshot = None
                planner_invalid_ids = tuple(
                    hypothesis.hypothesis_id for hypothesis in selected
                )
            else:
                planner_invalid_ids = snapshot.invalid_hypothesis_ids
        else:
            planner_invalid_ids = ()

        planning = _planning_report(
            snapshot,
            level=history.current_level,
            win_levels=int(records[-1]["win_levels"]),
            persistence=INITIAL_CROSS_LEVEL_PERSISTENCE,
            risk_coefficient=config.planning.risk_coefficient,
        )
        selected_ids = tuple(hypothesis.hypothesis_id for hypothesis in selected)
        selected_behavior_signatures = {
            item.result.behavior_signature
            for item in evaluated
            if item.hypothesis_id in selected_ids
            and item.result.behavior_signature is not None
        }
        reasons = admission_gate_reasons(
            selected_ids=selected_ids,
            eligible_ids=eligible_ids,
            distinct_selected_behaviors=len(selected_behavior_signatures),
            planner_invalid_ids=planner_invalid_ids,
            agreement=planning["agreement"],
            differing_optimal_sets=planning["differing_optimal_sets"],
            maximum_evsi=planning["maximum_evsi"],
            maximum_cross_level_utility=planning["maximum_cross_level_utility"],
            agreement_threshold=config.planning.agreement_threshold,
        )
        ineligible_selected = sorted(set(selected_ids) - set(eligible_ids))
        return {
            "schema_version": 1,
            "contract_version": ADMISSION_CONTRACT_VERSION,
            "status": "pilot_admitted" if not reasons else "pilot_blocked",
            "offline": True,
            "git": asdict(inspect_git_provenance()),
            "inputs": {
                "grounding_artifact": _repo_relative_path(grounding_artifact_path),
                "grounding_artifact_sha256": _file_sha256(grounding_artifact_path),
                "grounding_artifact_schema": grounding_artifact["schema_version"],
                "fixture": _repo_relative_path(fixture_path),
                "fixture_sha256": fixture_sha,
                "history_canonical_sha256": history_sha,
                "source_base_config_sha256": grounding_artifact.get(
                    "base_config_sha256"
                ),
                "current_config_sha256": stable_config_hash(config),
                "source_prompt_contract_version": grounding_artifact.get(
                    "prompt_contract_version"
                ),
            },
            "contract": {
                "planning_depth": config.planning.depth,
                "beam_width": config.planning.beam_width,
                "agreement_threshold": config.planning.agreement_threshold,
                "material_evsi_threshold_actions": MATERIAL_EVSI_THRESHOLD,
                "initial_cross_level_persistence": INITIAL_CROSS_LEVEL_PERSISTENCE,
                "role_policy": (
                    "candidate 0 is conservative; every later candidate must be "
                    "action-sensitive and goal-conditioned"
                ),
                "admission_rule": (
                    "at least two eligible distinct selected programs, no selected "
                    "grounding failures or planner invalids, and either agreement below "
                    "threshold with material EVSI and positive cross-level utility, or "
                    "differing optimal action sets with material EVSI"
                ),
            },
            "history": {
                "frames": len(history.frames),
                "level": history.current_level,
                "win_levels": int(records[-1]["win_levels"]),
                "actions": [_action_label(action) for action in actions],
            },
            "programs": [_program_report(item) for item in evaluated],
            "selection": {
                "eligible_ids": list(eligible_ids),
                "ineligible_ids": [
                    item.hypothesis_id or f"raw-source:{item.result.source_sha256}"
                    for item in evaluated
                    if not item.result.eligible
                ],
                "selected_ids": list(selected_ids),
                "ineligible_selected_ids": ineligible_selected,
                "behavioral_deduplicated_ids": list(deduplicated_ids),
                "distinct_selected_behavior_classes": len(
                    selected_behavior_signatures
                ),
                "filter_precedes_persistent_worker_construction": True,
            },
            "planning": planning,
            "planner_error": planner_error,
            "gate": {"passes": not reasons, "reasons": list(reasons)},
        }
    finally:
        for hypothesis in selected:
            hypothesis.close()


def _planning_report(
    snapshot: PlanningSnapshot | None,
    *,
    level: int,
    win_levels: int,
    persistence: float,
    risk_coefficient: float,
) -> dict[str, Any]:
    m_multiplier = 1.0
    x_multiplier = level_multiplier(level, win_levels, persistence)
    if snapshot is None:
        return {
            "hypothesis_ids": [],
            "invalid_hypothesis_ids": [],
            "weights": [],
            "agreement": None,
            "indifference": None,
            "optimal_action_sets": {},
            "differing_optimal_sets": False,
            "per_hypothesis_cost_variation": {},
            "actions": [],
            "myopic_multiplier": m_multiplier,
            "cross_level_multiplier": x_multiplier,
            "maximum_evsi": 0.0,
            "maximum_myopic_utility": -1.0,
            "maximum_cross_level_utility": -1.0,
        }

    agreement = committee_agreement(snapshot.actions, snapshot.costs, snapshot.weights)
    indifference = committee_indifference(
        snapshot.actions, snapshot.costs, snapshot.weights
    )
    optimal_sets = _optimal_action_sets(snapshot)
    differing_optimal_sets = len({tuple(value) for value in optimal_sets.values()}) > 1
    probe_rows: list[dict[str, Any]] = []
    for action in snapshot.actions:
        predictions = snapshot.predictions[action]
        evsi = weighted_evsi(
            predictions, snapshot.actions, snapshot.costs, snapshot.weights
        )
        catastrophe = catastrophe_probability(predictions, snapshot.weights)
        probe_rows.append(
            {
                "action": _action_label(action),
                "costs": [float(value) for value in snapshot.costs[action]],
                "prediction_signatures": [
                    _prediction_signature_sha(value) for value in predictions
                ],
                "evsi": evsi,
                "catastrophe_probability": catastrophe,
                "myopic_utility": probe_utility(
                    evsi,
                    m_multiplier,
                    catastrophe,
                    risk_coefficient=risk_coefficient,
                ),
                "cross_level_utility": probe_utility(
                    evsi,
                    x_multiplier,
                    catastrophe,
                    risk_coefficient=risk_coefficient,
                ),
            }
        )
    cost_variation: dict[str, Any] = {}
    for index, hypothesis_id in enumerate(snapshot.hypothesis_ids):
        values = [float(snapshot.costs[action][index]) for action in snapshot.actions]
        minimum = min(values)
        maximum = max(values)
        cost_variation[hypothesis_id] = {
            "minimum": minimum,
            "maximum": maximum,
            "range": maximum - minimum,
            "action_varying": not isclose(
                minimum, maximum, rel_tol=1e-12, abs_tol=1e-12
            ),
            "distinct_costs": len(
                {
                    round(value, 12)
                    for value in values
                }
            ),
        }
    return {
        "hypothesis_ids": list(snapshot.hypothesis_ids),
        "invalid_hypothesis_ids": list(snapshot.invalid_hypothesis_ids),
        "weights": list(snapshot.weights),
        "agreement": agreement,
        "indifference": indifference,
        "optimal_action_sets": optimal_sets,
        "differing_optimal_sets": differing_optimal_sets,
        "per_hypothesis_cost_variation": cost_variation,
        "actions": probe_rows,
        "myopic_multiplier": m_multiplier,
        "cross_level_multiplier": x_multiplier,
        "maximum_evsi": max(row["evsi"] for row in probe_rows),
        "maximum_myopic_utility": max(row["myopic_utility"] for row in probe_rows),
        "maximum_cross_level_utility": max(
            row["cross_level_utility"] for row in probe_rows
        ),
    }


def _optimal_action_sets(snapshot: PlanningSnapshot) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for index, hypothesis_id in enumerate(snapshot.hypothesis_ids):
        minimum = min(float(snapshot.costs[action][index]) for action in snapshot.actions)
        result[hypothesis_id] = [
            _action_label(action)
            for action in snapshot.actions
            if isclose(
                float(snapshot.costs[action][index]),
                minimum,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ]
    return result


def _program_report(item: EvaluatedSource) -> dict[str, Any]:
    result = item.result
    return {
        "candidate_index": item.candidate_index,
        "assigned_role": item.assigned_role,
        "raw_source_sha256": result.source_sha256,
        "hypothesis_id": item.hypothesis_id,
        "requirements": {
            "action_sensitivity": result.action_sensitivity_required,
            "goal_conditioning": result.goal_conditioning_required,
        },
        "eligibility": {
            "eligible": result.eligible,
            "sandbox_valid": result.sandbox_valid,
            "goal_value_ok": result.goal_value_ok,
            "all_actions_ok": result.all_actions_ok,
            "palette_conflicts": len(result.palette_conflicts),
            "action_sensitive": result.action_sensitive,
            "goal_action_conditioned": result.goal_action_conditioned,
        },
        "ast_nodes": result.ast_nodes,
        "behavior_signature": result.behavior_signature,
    }


def _prediction_signature_sha(prediction: Prediction | None) -> str:
    digest = hashlib.sha256()
    if prediction is None:
        digest.update(b"INVALID")
        return digest.hexdigest()
    digest.update(b"VALID\0")
    digest.update(int(prediction.next_grid.shape[0]).to_bytes(4, "big"))
    digest.update(int(prediction.next_grid.shape[1]).to_bytes(4, "big"))
    digest.update(prediction.next_grid.tobytes(order="C"))
    digest.update(prediction.game_state.value.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(prediction.level_delta).encode("ascii"))
    return digest.hexdigest()


def _fixture_history_records(fixture: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    raw_history = fixture.get("history")
    if not isinstance(raw_history, list) or not raw_history:
        raise ValueError("fixture history is empty")
    for raw_value in raw_history:
        raw = _require_mapping(raw_value, "fixture history row")
        rows = raw.get("grid_hex_rows")
        if not isinstance(rows, list) or len(rows) != 64 or any(
            not isinstance(row, str) or len(row) != 64 for row in rows
        ):
            raise ValueError("fixture grids must contain 64 hexadecimal rows")
        try:
            grid = [[int(character, 16) for character in row] for row in rows]
        except ValueError as exc:
            raise ValueError("fixture grid contains a non-hexadecimal cell") from exc
        records.append(
            {
                "grid": grid,
                "action": raw.get("action"),
                "available_actions": list(raw["available_actions"]),
                "game_state": str(raw["game_state"]),
                "level_delta": int(raw["level_delta"]),
                "level": int(raw["level"]),
                "win_levels": int(raw["win_levels"]),
            }
        )
    return tuple(records)


def _validate_contract_identity(
    grounding_artifact: Mapping[str, Any], config: SystemConfig
) -> None:
    expected: tuple[tuple[str, Any], ...] = (
        ("prompt_contract_version", config.experiment.prompt_contract_version),
        ("prompt_contract_sha256", config.experiment.prompt_contract_sha256),
        ("perception_contract_version", config.experiment.perception_contract_version),
        ("perception_contract_sha256", config.experiment.perception_contract_sha256),
    )
    if config.model is None:
        raise ValueError("runtime admission config must identify the source model")
    expected += (
        ("model_id", config.model.id),
        ("expected_model_revision", config.model.expected_revision),
        (
            "expected_weight_manifest_sha256",
            config.model.expected_weight_manifest_sha256,
        ),
    )
    mismatches = [
        name
        for name, expected_value in expected
        if grounding_artifact.get(name) != expected_value
    ]
    if mismatches:
        raise ValueError(
            "grounding artifact contract identity differs from current config: "
            + ", ".join(mismatches)
        )


def _action_label(action: Action) -> str:
    if action.kind is ActionKind.ACTION6:
        return f"ACTION6({action.row},{action.col})"
    return action.kind.name


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative_path(path: Path) -> str:
    repository = Path(__file__).resolve().parents[2]
    try:
        return path.resolve().relative_to(repository).as_posix()
    except ValueError:
        return path.resolve().as_posix()


__all__ = [
    "ADMISSION_CONTRACT_VERSION",
    "INITIAL_CROSS_LEVEL_PERSISTENCE",
    "MATERIAL_EVSI_THRESHOLD",
    "EvaluatedSource",
    "admission_gate_reasons",
    "construct_eligible_hypotheses",
    "evaluate_source_programs",
    "role_requirements",
    "run_runtime_admission_audit",
]
