"""Frozen synthetic admission evidence for the path-deficit-v2 treatment.

This module deliberately stops before the canonical bp35 audit.  Its only purpose is
to reproduce the preregistered generic synthetic bridge with the registered Gibbs/MDL
weights and to preserve its already-disposed negative outcome without invoking a model
or an environment. Dependency drift fails closed instead of re-admitting the treatment.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from dataclasses import asdict
from math import isclose
from pathlib import Path
from typing import Any, cast

import numpy as np

from .candidates import (
    CANDIDATE_POLICY_HASH,
    CANDIDATE_POLICY_VERSION,
    candidates_from_history,
)
from .config import PATH_DEFICIT_RUNTIME_VERSION, SystemConfig, load_config
from .experiment import DEVELOPMENT_SEEDS, load_matrix, stable_config_hash
from .planner import (
    COMPLETION_COST_POLICY_HASHES,
    ENDPOINT_COMPLETION_COST_POLICY,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
)
from .program import candidate_points_from_source
from .provenance import inspect_git_provenance
from .runtime.worker import RLIMIT_DATA_HEADROOM_KIND
from .runtime_admission import (
    ADMISSION_CONTRACT_VERSION,
    INITIAL_CROSS_LEVEL_PERSISTENCE,
    MATERIAL_EVSI_THRESHOLD,
    audit_source_batch,
)
from .structured_templates import (
    FROZEN_BP35_FIXTURE_SHA256,
    FROZEN_BP35_HISTORY_SHA256,
    SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256,
    STRUCTURED_PRIOR_CONTRACT_SHA256,
    STRUCTURED_PRIOR_CONTRACT_VERSION,
    STRUCTURED_PRIOR_ROLES,
    StructuredPriorSource,
    instantiate_structured_priors,
)
from .topology_compiler import TOPOLOGY_COMPILER_CODE_SHA256
from .types import Action, ActionKind, GameState, History, Observation

PATH_DEFICIT_SYNTHETIC_CONTRACT_VERSION = "path-deficit-synthetic-admission-v1"
PRE_AMENDMENT_HEAD_COMMIT = "9805e9e04f0e9d1a1fb7b6f0704697b1022bb736"
PREREGISTRATION_COMMIT = "1302a05750f75d813fd3f84df13f0025e8050d9e"
PREREGISTRATION_SHA256 = (
    "a253ef9e432e1fa59363a007c7dd00f7cdcc9507747b6096c94aa697961265e3"
)
REGISTERED_CONFIG_PATH = "configs/template_v1_path_deficit_v2_x.yaml"
REGISTERED_MATRIX_PATH = "artifacts/development_matrix_template_v1_path_deficit_v2.json"
REGISTERED_AMENDMENT_PATH = (
    "docs/experiment_amendment_2026-07-13_trajectory_deficit_v2.md"
)
REGISTERED_AMENDMENT_SHA256 = (
    "72522d43c2069f58cc2478401c02602cfe3db557496268e1aad19bdbf9f5a0b7"
)
REGISTERED_CONFIG_FILE_SHA256 = (
    "26b02a26a7152597eb40164a3775e23f38750ea7891af9fa20b4c327af7cb090"
)
REGISTERED_CONFIG_SHA256 = (
    "de53f3dffe049ffa3a62eb49622c34f1233a0f86baf6622b42f006b9b1c1982a"
)
REGISTERED_MATRIX_SHA256 = (
    "949fe7a7455e3637acdeb2ec278ff9822e78a15284854fd730e47a3c84775d5e"
)
REGISTERED_ARM_HASHES = {
    "D-Q": "0c91334b067b82d3e5196d8f2802918ec5227e673365eaa9eca1cca158317a34",
    "S-T": "a2f2e298d28ef4d17b41a117a473133c9ed5628554a66c6d10cd80bda5b1b50d",
    "M-T": "5f0bb945c65cb1c7db015eaea2602cc07fd2976b0dc86ab9738ae26302f4251a",
    "X-T": REGISTERED_CONFIG_SHA256,
}
REGISTERED_NEGATIVE_WEIGHTS = (
    0.4116174747472121,
    0.22410046565918698,
    0.20604497263252872,
    0.1582370869610722,
)
REGISTERED_NEGATIVE_AGREEMENT = 0.8417629130389278
REGISTERED_NEGATIVE_MAXIMUM_EVSI = 0.048123650158264475
REGISTERED_SYNTHETIC_SCENE_SHA256 = (
    "dfa612dbc1215319d3d2de1b8b41c9462a9dcd822ccd3b9793c0e358d216383b"
)
REGISTERED_SYNTHETIC_CANDIDATES_SHA256 = (
    "86e6f48fbe0056f0913b08c1daa1d54fc3147f163e1aece8177d50c02e6a6a69"
)
REGISTERED_SYNTHETIC_SOURCE_MANIFEST_SHA256 = (
    "7834f5a116c3d2e6e3b5725d9c17d982d76f8f947ebd6bc2d1ca9f405053d9d4"
)
REGISTERED_SYNTHETIC_CONTRACT_SHA256 = (
    "d01f34cc2835a4a8b7f7257a6fc65e67c455d158356c69db744a6c50203b30ed"
)
EXPECTED_WORKER_HEADROOM_BYTES = 256 * 1024 * 1024
FROZEN_PRIOR_FILES = {
    "artifacts/template_v1_runtime_admission_v2_bp35_seed11.json": (
        "546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033"
    ),
    "artifacts/development_matrix_template_v1.json": (
        "6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b"
    ),
    "artifacts/development_matrix.json": (
        "ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147"
    ),
    "configs/template_v1_x.yaml": (
        "0ec730e8bd56752da905070e56d4c36dea062db4b126ca9a97e897d1f98a215a"
    ),
}


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_registered_path(path: Path, root: Path, expected: str) -> Path:
    resolved = path.resolve()
    expected_path = (root / expected).resolve()
    if resolved != expected_path:
        raise ValueError(f"registered input must be {expected}, got {resolved}")
    return resolved


def _synthetic_history() -> History:
    """Build the exact palette-neutral homologous/enclosed-object bridge."""

    grid = np.zeros((18, 22), dtype=np.int16)
    grid[3:5, 3:5] = 2
    grid[3:5, 13:15] = 2
    grid[10:13, 8:11] = 3
    grid[11, 9] = 0
    return History.from_observation(
        Observation(
            grid,
            frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=9,
        )
    )


def _compiled_candidates(
    history: History,
    sources: tuple[StructuredPriorSource, ...],
    *,
    max_candidates: int,
) -> tuple[Action, ...]:
    cached_points: list[tuple[int, int]] = []
    for source in sources:
        for point in candidate_points_from_source(source.source):
            if point not in cached_points:
                cached_points.append(point)
    return candidates_from_history(
        history,
        cached_points=cached_points,
        max_candidates=max_candidates,
    )


def _action_row(action: Action) -> dict[str, int | None]:
    return {"kind": int(action.kind), "row": action.row, "col": action.col}


def _acceptance_gate(
    batch: dict[str, Any],
    *,
    agreement_threshold: float,
) -> dict[str, Any]:
    programs = cast(list[dict[str, Any]], batch["programs"])
    selection = cast(dict[str, Any], batch["selection"])
    planning = cast(dict[str, Any], batch["planning"])
    variation = cast(dict[str, dict[str, Any]], planning["per_hypothesis_cost_variation"])

    valid_programs = sum(bool(row["eligibility"]["eligible"]) for row in programs)
    selected_ids = tuple(str(value) for value in selection["selected_ids"])
    graded_varying = 0
    for row in programs:
        if int(row["candidate_index"]) == 0 or row["hypothesis_id"] is None:
            continue
        if bool(variation[str(row["hypothesis_id"])]["action_varying"]):
            graded_varying += 1

    agreement = float(planning["agreement"])
    maximum_evsi = float(planning["maximum_evsi"])
    x_only_actions = tuple(str(value) for value in planning["x_only_probe_actions"])
    reasons: list[str] = []
    if valid_programs != 4:
        reasons.append("generic bridge did not produce exactly four valid programs")
    if len(selected_ids) != 4 or int(selection["distinct_selected_behavior_classes"]) != 4:
        reasons.append("four distinct valid programs did not survive selection")
    if graded_varying < 2:
        reasons.append("fewer than two graded programs had action-varying depth-four costs")
    if agreement >= agreement_threshold:
        reasons.append("committee agreement was not below 0.8")
    if maximum_evsi < MATERIAL_EVSI_THRESHOLD:
        reasons.append("maximum EVSI was below 0.05 actions")
    if not x_only_actions:
        reasons.append("no X-only action survived the unchanged admission rule")

    return {
        "passes": not reasons,
        "reasons": reasons,
        "requirements": {
            "valid_programs": 4,
            "distinct_selected_programs": 4,
            "minimum_graded_action_varying_programs": 2,
            "agreement_strictly_below": agreement_threshold,
            "maximum_evsi_at_least_actions": MATERIAL_EVSI_THRESHOLD,
            "minimum_x_only_actions": 1,
        },
        "observed": {
            "valid_programs": valid_programs,
            "selected_programs": len(selected_ids),
            "distinct_selected_programs": int(
                selection["distinct_selected_behavior_classes"]
            ),
            "graded_action_varying_programs": graded_varying,
            "weights": list(planning["weights"]),
            "agreement": agreement,
            "maximum_evsi_actions": maximum_evsi,
            "x_only_probe_actions": list(x_only_actions),
        },
    }


def _require_registered_negative_result(
    acceptance: dict[str, Any],
    *,
    scene_sha256: str,
    candidates_sha256: str,
    source_manifest_sha256: str,
) -> None:
    """Reject dependency drift instead of turning a frozen failure into admission."""

    if PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256 != REGISTERED_SYNTHETIC_CONTRACT_SHA256:
        raise RuntimeError("synthetic audit contract differs from its registered digest")
    if (
        scene_sha256 != REGISTERED_SYNTHETIC_SCENE_SHA256
        or candidates_sha256 != REGISTERED_SYNTHETIC_CANDIDATES_SHA256
        or source_manifest_sha256 != REGISTERED_SYNTHETIC_SOURCE_MANIFEST_SHA256
    ):
        raise RuntimeError("synthetic bridge inputs differ from their registered digests")
    expected_reasons = [
        "committee agreement was not below 0.8",
        "maximum EVSI was below 0.05 actions",
        "no X-only action survived the unchanged admission rule",
    ]
    if acceptance["passes"] is not False or acceptance["reasons"] != expected_reasons:
        raise RuntimeError("synthetic bridge disposition differs from the frozen failure")
    observed = cast(dict[str, Any], acceptance["observed"])
    exact_counts = {
        "valid_programs": 4,
        "selected_programs": 4,
        "distinct_selected_programs": 4,
        "graded_action_varying_programs": 3,
    }
    if any(observed[key] != value for key, value in exact_counts.items()):
        raise RuntimeError("synthetic bridge structural observations changed")
    weights = tuple(float(value) for value in observed["weights"])
    if len(weights) != len(REGISTERED_NEGATIVE_WEIGHTS) or any(
        not isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        for actual, expected in zip(weights, REGISTERED_NEGATIVE_WEIGHTS, strict=True)
    ):
        raise RuntimeError("synthetic bridge registered Gibbs weights changed")
    if not isclose(
        float(observed["agreement"]),
        REGISTERED_NEGATIVE_AGREEMENT,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError("synthetic bridge agreement changed")
    if not isclose(
        float(observed["maximum_evsi_actions"]),
        REGISTERED_NEGATIVE_MAXIMUM_EVSI,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError("synthetic bridge maximum EVSI changed")
    if observed["x_only_probe_actions"] != []:
        raise RuntimeError("synthetic bridge unexpectedly produced an X-only action")


def _infrastructure_gate(
    batch: dict[str, Any],
    *,
    require_linux_memory: bool,
    resource_usage: dict[str, Any],
) -> dict[str, Any]:
    """Separate retryable worker failures from the disposed scientific gate."""

    reasons: list[str] = []
    programs = cast(list[dict[str, Any]], batch["programs"])
    selection = cast(dict[str, Any], batch["selection"])
    planning = cast(dict[str, Any], batch["planning"])
    if batch["planner_error"] is not None:
        reasons.append("depth-four planner returned an error")
    expected_resources = {
        "model_id": None,
        "model_calls": 0,
        "generated_tokens": 0,
        "gpu_used": False,
        "environment_actions": 0,
        "reward_observations": 0,
        "rhae_observations": 0,
    }
    if resource_usage != expected_resources:
        reasons.append("offline synthetic audit reported forbidden resource usage")
    if len(programs) != 4 or [row["candidate_index"] for row in programs] != list(
        range(4)
    ):
        reasons.append("expected four contiguous source programs")
    if [row["assigned_role"] for row in programs] != list(STRUCTURED_PRIOR_ROLES):
        reasons.append("source roles differ from the registered compiler contract")
    for row in programs:
        eligibility = cast(dict[str, Any], row["eligibility"])
        if not all(
            eligibility[key]
            for key in ("eligible", "sandbox_valid", "goal_value_ok", "all_actions_ok")
        ):
            reasons.append(f"program {row['candidate_index']} did not execute cleanly")
        if eligibility["palette_conflicts"] != 0 or row["hypothesis_id"] is None:
            reasons.append(f"program {row['candidate_index']} failed identity/palette checks")

    selected_ids = [str(value) for value in selection["selected_ids"]]
    if (
        len(selected_ids) != 4
        or selected_ids != [str(value) for value in selection["eligible_ids"]]
        or selection["ineligible_ids"]
        or selection["ineligible_selected_ids"]
        or selection["behavioral_deduplicated_ids"]
        or int(selection["distinct_selected_behavior_classes"]) != 4
    ):
        reasons.append("selection did not preserve four exact eligible behavior classes")
    if planning["invalid_hypothesis_ids"]:
        reasons.append("one or more programs became invalid during planning")

    memory_rows = [
        cast(dict[str, Any], row["grounding_worker_memory"]) for row in programs
    ]
    persistent_memory = [
        cast(dict[str, Any], row) for row in selection["selected_worker_memory"]
    ]
    if [row.get("hypothesis_id") for row in persistent_memory] != selected_ids:
        reasons.append("persistent worker identities differ from selection")
    if require_linux_memory:
        for stage, rows in (
            ("grounding", memory_rows),
            ("persistent", persistent_memory),
        ):
            for index, row in enumerate(rows):
                if (
                    row["hard_limit_enforced"] is not True
                    or row["limit_kind"] != RLIMIT_DATA_HEADROOM_KIND
                    or row["allocation_headroom_bytes"]
                    != EXPECTED_WORKER_HEADROOM_BYTES
                    or row["diagnostic"] is not None
                ):
                    reasons.append(
                        f"{stage} worker {index} did not enforce exact +256 MiB RLIMIT_DATA"
                    )

    return {
        "passes": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "require_linux_memory": require_linux_memory,
        "expected_limit_kind": RLIMIT_DATA_HEADROOM_KIND,
        "expected_allocation_headroom_bytes": EXPECTED_WORKER_HEADROOM_BYTES,
        "grounding_workers_checked": len(memory_rows),
        "persistent_workers_checked": len(persistent_memory),
        "resource_counters_checked": True,
    }


def registered_path_deficit_inputs(
    config_path: Path,
    matrix_path: Path,
) -> dict[str, Any]:
    """Validate and summarize the exact zero-run registration inputs."""

    root = _repo_root()
    config_path = _require_registered_path(config_path, root, REGISTERED_CONFIG_PATH)
    matrix_path = _require_registered_path(matrix_path, root, REGISTERED_MATRIX_PATH)
    amendment_path = root / REGISTERED_AMENDMENT_PATH
    if _file_sha256(config_path) != REGISTERED_CONFIG_FILE_SHA256:
        raise ValueError("path-deficit config file differs from its frozen digest")
    if _file_sha256(matrix_path) != REGISTERED_MATRIX_SHA256:
        raise ValueError("path-deficit matrix differs from its frozen digest")
    if _file_sha256(amendment_path) != REGISTERED_AMENDMENT_SHA256:
        raise ValueError("path-deficit amendment differs from its frozen digest")

    config = load_config(config_path)
    if stable_config_hash(config) != REGISTERED_CONFIG_SHA256:
        raise ValueError("path-deficit X-T config semantics differ from registration")
    if config.experiment.implementation_contract_version != PATH_DEFICIT_RUNTIME_VERSION:
        raise ValueError("path-deficit config does not use runtime-v4")
    if (
        config.planning.completion_cost_policy_version
        != PATH_DEFICIT_COMPLETION_COST_POLICY
    ):
        raise ValueError("path-deficit config does not select path-deficit-v2")

    matrix = load_matrix(matrix_path)
    arms = {str(row.arm_label) for row in matrix}
    games = {row.full_game_id for row in matrix}
    arm_hashes = {
        arm: {row.config_hash for row in matrix if row.arm_label == arm}
        for arm in REGISTERED_ARM_HASHES
    }
    if len(matrix) != 180 or len(games) != 15:
        raise ValueError("path-deficit matrix does not have frozen 15x3x4 coverage")
    if {row.seed for row in matrix} != set(DEVELOPMENT_SEEDS):
        raise ValueError("path-deficit matrix seeds differ from registration")
    if arms != set(REGISTERED_ARM_HASHES):
        raise ValueError("path-deficit matrix arms differ from registration")
    if arm_hashes != {
        arm: {digest} for arm, digest in REGISTERED_ARM_HASHES.items()
    }:
        raise ValueError("path-deficit matrix arm hashes differ from registration")

    run_ids = {row.run_id for row in matrix}
    prior_matrices = {
        "template_v1": load_matrix(
            root / "artifacts/development_matrix_template_v1.json"
        ),
        "qwen": load_matrix(root / "artifacts/development_matrix.json"),
    }
    collisions = {
        name: len(run_ids.intersection(row.run_id for row in prior))
        for name, prior in prior_matrices.items()
    }
    if any(collisions.values()):
        raise ValueError("path-deficit matrix collides with a frozen prior matrix")
    for relative, digest in FROZEN_PRIOR_FILES.items():
        if _file_sha256(root / relative) != digest:
            raise ValueError(f"frozen prior evidence changed: {relative}")

    return {
        "amendment": REGISTERED_AMENDMENT_PATH,
        "amendment_sha256": REGISTERED_AMENDMENT_SHA256,
        "config": REGISTERED_CONFIG_PATH,
        "config_file_sha256": REGISTERED_CONFIG_FILE_SHA256,
        "config_sha256": REGISTERED_CONFIG_SHA256,
        "matrix": REGISTERED_MATRIX_PATH,
        "matrix_sha256": REGISTERED_MATRIX_SHA256,
        "matrix_rows": len(matrix),
        "game_count": len(games),
        "seeds": list(DEVELOPMENT_SEEDS),
        "arm_hashes": REGISTERED_ARM_HASHES,
        "first_run_id": matrix[0].run_id,
        "last_run_id": matrix[-1].run_id,
        "prior_run_id_collisions": collisions,
        "execution_status": "registration-only; hard-disabled",
        "frozen_prior_files": FROZEN_PRIOR_FILES,
    }


def run_path_deficit_synthetic_audit(
    config_path: Path,
    matrix_path: Path,
    *,
    require_clean_commit: bool = True,
    require_linux: bool = True,
) -> dict[str, Any]:
    """Run the frozen synthetic bridge and stop regardless of its outcome."""

    root = _repo_root()
    registration = registered_path_deficit_inputs(config_path, matrix_path)
    config: SystemConfig = load_config(config_path)
    provenance = inspect_git_provenance(root)
    if require_clean_commit and (provenance.commit is None or provenance.dirty is not False):
        raise RuntimeError("synthetic admission evidence requires a clean committed worktree")
    if require_linux and sys.platform != "linux":
        raise RuntimeError("canonical synthetic admission evidence must run on Linux")

    history = _synthetic_history()
    sources = instantiate_structured_priors(history)
    if tuple(source.role for source in sources) != STRUCTURED_PRIOR_ROLES:
        raise RuntimeError("compiled roles differ from the frozen compiler contract")
    actions = _compiled_candidates(
        history,
        sources,
        max_candidates=config.planning.max_candidates,
    )
    programs = [
        {
            "candidate_index": index,
            "assigned_role": source.role,
            "source": source.source,
            "source_sha256": hashlib.sha256(source.source.encode("utf-8")).hexdigest(),
        }
        for index, source in enumerate(sources)
    ]
    batch = audit_source_batch(
        programs,
        history,
        actions,
        config=config,
        win_levels=9,
    )
    resource_usage = {
        "model_id": None,
        "model_calls": 0,
        "generated_tokens": 0,
        "gpu_used": False,
        "environment_actions": 0,
        "reward_observations": 0,
        "rhae_observations": 0,
    }
    infrastructure = _infrastructure_gate(
        batch,
        require_linux_memory=require_linux,
        resource_usage=resource_usage,
    )
    if not infrastructure["passes"]:
        reasons = "; ".join(str(value) for value in infrastructure["reasons"])
        raise RuntimeError(f"synthetic audit infrastructure failed: {reasons}")
    acceptance = _acceptance_gate(
        batch,
        agreement_threshold=config.planning.agreement_threshold,
    )
    scene_payload = {
        "grid": history.latest_grid.tolist(),
        "available_actions": sorted(int(kind) for kind in history.latest_action_set),
        "game_state": history.latest_game_state.value,
        "level": history.current_level,
        "win_levels": 9,
    }
    action_rows = [_action_row(action) for action in actions]
    source_manifest = [
        {
            "role": source.role,
            "source_sha256": program["source_sha256"],
            "bindings_sha256": _canonical_sha256(dict(source.bindings)),
            "evidence_sha256": _canonical_sha256(source.evidence),
        }
        for source, program in zip(sources, programs, strict=True)
    ]
    scene_sha256 = _canonical_sha256(scene_payload)
    candidates_sha256 = _canonical_sha256(action_rows)
    source_manifest_sha256 = _canonical_sha256(source_manifest)
    _require_registered_negative_result(
        acceptance,
        scene_sha256=scene_sha256,
        candidates_sha256=candidates_sha256,
        source_manifest_sha256=source_manifest_sha256,
    )
    return {
        "schema_version": 1,
        "contract_version": PATH_DEFICIT_SYNTHETIC_CONTRACT_VERSION,
        "contract_sha256": PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256,
        "status": "synthetic_blocked",
        "offline": True,
        "git": {
            key: value
            for key, value in asdict(provenance).items()
            if key != "repository_root"
        },
        "registration": registration,
        "treatment": {
            "pre_amendment_head_commit": PRE_AMENDMENT_HEAD_COMMIT,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "preregistration_sha256": PREREGISTRATION_SHA256,
            "implementation_contract_version": PATH_DEFICIT_RUNTIME_VERSION,
            "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
                PATH_DEFICIT_COMPLETION_COST_POLICY
            ],
            "historical_completion_cost_policy_version": (
                ENDPOINT_COMPLETION_COST_POLICY
            ),
            "historical_completion_cost_policy_sha256": (
                COMPLETION_COST_POLICY_HASHES[ENDPOINT_COMPLETION_COST_POLICY]
            ),
            "admission_contract_version": ADMISSION_CONTRACT_VERSION,
            "candidate_policy_version": CANDIDATE_POLICY_VERSION,
            "candidate_policy_sha256": CANDIDATE_POLICY_HASH,
            "compiler_contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
            "compiler_code_sha256": TOPOLOGY_COMPILER_CODE_SHA256,
            "scene_topology_admission_overlay_sha256": (
                SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256
            ),
            "frozen_bp35_fixture_sha256": FROZEN_BP35_FIXTURE_SHA256,
            "frozen_bp35_history_sha256": FROZEN_BP35_HISTORY_SHA256,
            "audit_module_sha256": _file_sha256(Path(__file__)),
            "initial_cross_level_persistence": INITIAL_CROSS_LEVEL_PERSISTENCE,
            "canonical_bp35_audit_authorized": False,
            "gameplay_authorized": False,
            "development_matrix_execution_authorized": False,
        },
        "resource_usage": resource_usage,
        "execution": {
            "platform": sys.platform,
            "require_clean_commit": require_clean_commit,
            "require_linux": require_linux,
        },
        "synthetic_scene": {
            "description": (
                "18x22 palette-neutral scene with two homologous 2x2 components and "
                "one enclosed 3x3 ring; no game identity or transition evidence"
            ),
            "payload": scene_payload,
            "payload_sha256": scene_sha256,
            "candidate_set": action_rows,
            "candidate_set_sha256": candidates_sha256,
            "source_manifest": source_manifest,
            "source_manifest_sha256": source_manifest_sha256,
        },
        "programs": batch["programs"],
        "selection": batch["selection"],
        "planning": batch["planning"],
        "planner_error": batch["planner_error"],
        "runtime_admission_gate": batch["gate"],
        "infrastructure_gate": infrastructure,
        "acceptance_gate": acceptance,
        "interpretation": (
            "preregistered synthetic capability test only; a failure freezes this "
            "treatment before canonical audit, model inference, or gameplay"
        ),
    }


def _contract_sha256() -> str:
    dependencies = {
        "audit_source_batch": inspect.getsource(audit_source_batch),
        "candidate_builder": inspect.getsource(candidates_from_history),
        "compiled_candidates": inspect.getsource(_compiled_candidates),
        "acceptance_gate": inspect.getsource(_acceptance_gate),
        "infrastructure_gate": inspect.getsource(_infrastructure_gate),
        "negative_disposition": inspect.getsource(_require_registered_negative_result),
        "run_audit": inspect.getsource(run_path_deficit_synthetic_audit),
        "synthetic_history": inspect.getsource(_synthetic_history),
        "instantiate_structured_priors": inspect.getsource(instantiate_structured_priors),
        "admission_contract_version": ADMISSION_CONTRACT_VERSION,
        "material_evsi_threshold": MATERIAL_EVSI_THRESHOLD,
        "policy_sha256": COMPLETION_COST_POLICY_HASHES[
            PATH_DEFICIT_COMPLETION_COST_POLICY
        ],
    }
    return _canonical_sha256(dependencies)


PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256 = _contract_sha256()


__all__ = [
    "EXPECTED_WORKER_HEADROOM_BYTES",
    "PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256",
    "PATH_DEFICIT_SYNTHETIC_CONTRACT_VERSION",
    "PREREGISTRATION_COMMIT",
    "PREREGISTRATION_SHA256",
    "PRE_AMENDMENT_HEAD_COMMIT",
    "REGISTERED_AMENDMENT_PATH",
    "REGISTERED_AMENDMENT_SHA256",
    "REGISTERED_ARM_HASHES",
    "REGISTERED_CONFIG_FILE_SHA256",
    "REGISTERED_CONFIG_PATH",
    "REGISTERED_CONFIG_SHA256",
    "REGISTERED_MATRIX_PATH",
    "REGISTERED_MATRIX_SHA256",
    "REGISTERED_NEGATIVE_AGREEMENT",
    "REGISTERED_NEGATIVE_MAXIMUM_EVSI",
    "REGISTERED_NEGATIVE_WEIGHTS",
    "REGISTERED_SYNTHETIC_CANDIDATES_SHA256",
    "REGISTERED_SYNTHETIC_CONTRACT_SHA256",
    "REGISTERED_SYNTHETIC_SCENE_SHA256",
    "REGISTERED_SYNTHETIC_SOURCE_MANIFEST_SHA256",
    "registered_path_deficit_inputs",
    "run_path_deficit_synthetic_audit",
]
