"""Offline-only scene-conditioned executable topology hypotheses.

This module remains disconnected from the live controller. It compiles inspectable
bindings from finite observable history and evaluates them through the shared admission
path. The deterministic sources are not evidence of model-generated induction.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from .candidates import (
    CANDIDATE_POLICY_HASH,
    CANDIDATE_POLICY_VERSION,
    candidates_from_history,
)
from .config import SystemConfig, load_config
from .experiment import load_matrix, stable_config_hash
from .provenance import inspect_git_provenance
from .replay import history_from_records
from .runtime.worker import RLIMIT_DATA_HEADROOM_KIND
from .runtime_admission import (
    ADMISSION_CONTRACT_VERSION,
    INITIAL_CROSS_LEVEL_PERSISTENCE,
    MATERIAL_EVSI_THRESHOLD,
    audit_source_batch,
)
from .topology_compiler import (
    TOPOLOGY_COMPILER_ALGORITHM_VERSION,
    TOPOLOGY_COMPILER_CODE_SHA256,
    BindingValue,
    compile_topology_programs,
)
from .types import History

STRUCTURED_PRIOR_CONTRACT_VERSION = "scene-topology-compiler-v1"
SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION = "scene-topology-admission-v1"
REGISTERED_X_T_CONFIG_SHA256 = (
    "aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708"
)
FROZEN_BP35_FIXTURE_SHA256 = (
    "ecb67dbe088efcc79c7b786447bf81796a42a08417d64972042571d128258d75"
)
FROZEN_BP35_HISTORY_SHA256 = (
    "de73a63399b6618b7a127d69f2ea75c1b83cea4f597c1993a0267e1da17c3fb4"
)
REGISTERED_TEMPLATE_MATRIX_SHA256 = (
    "6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b"
)
_INSTANTIATION_POLICY = (
    "compile four deterministic restricted programs from the latest observable scene; "
    "bind palette-relative four-connected topology, containment, rarity, homologous "
    "shape repetition, symmetry, and relative geometry; install the most recent "
    "representable recorded transition ahead of every generic prior"
)
STRUCTURED_PRIOR_ROLES = (
    "conservative_evidence",
    "topology_contact",
    "homology_alignment",
    "symmetry_completion",
)
STRUCTURED_PRIOR_CONTRACT_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "compiler_contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "instantiation_policy": _INSTANTIATION_POLICY,
            "roles": STRUCTURED_PRIOR_ROLES,
            "template_version": 1,
            "topology_algorithm_version": TOPOLOGY_COMPILER_ALGORITHM_VERSION,
            "topology_compiler_code_sha256": TOPOLOGY_COMPILER_CODE_SHA256,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuredPriorSource:
    """One compiled role, its source, and auditable scene bindings."""

    role: str
    source: str
    bindings: tuple[tuple[str, BindingValue], ...] = ()
    evidence: tuple[str, ...] = ()


def instantiate_structured_priors(history: History) -> tuple[StructuredPriorSource, ...]:
    """Compile exactly four deterministic, scene-conditioned programs."""

    if not history.frames:
        raise ValueError("structured-prior instantiation requires a non-empty history")
    if history.latest_grid.ndim != 2 or not history.latest_grid.size:
        raise ValueError("structured-prior instantiation requires a non-empty 2-D grid")
    return tuple(
        StructuredPriorSource(
            role=program.role,
            source=program.source,
            bindings=program.bindings,
            evidence=program.evidence,
        )
        for program in compile_topology_programs(history)
    )


def run_scene_topology_admission_audit(
    fixture_path: Path,
    config: SystemConfig,
    *,
    config_path: Path,
    require_clean_commit: bool = True,
    require_linux_memory: bool = True,
) -> dict[str, Any]:
    """Run deterministic admission against scene-compiled topology sources.

    This is a capability diagnostic, not an empirical transition-model evaluation.
    The sources still pass through the shared role checks, sandbox, behavioral
    deduplication, depth-four planner, and X-only-probe admission rule.
    """

    if config.experiment.hypothesis_source != "template_v1":
        raise ValueError("scene-topology admission requires hypothesis_source=template_v1")
    if config.experiment.variant != "X":
        raise ValueError("scene-topology admission requires the registered X-T arm")
    config_sha256 = stable_config_hash(config)
    if config_sha256 != REGISTERED_X_T_CONFIG_SHA256:
        raise ValueError("scene-topology admission config does not match registered X-T")
    loaded_config = load_config(config_path)
    if loaded_config != config:
        raise ValueError("config_path does not resolve to the supplied admission config")

    provenance = inspect_git_provenance()
    if require_clean_commit and (provenance.commit is None or provenance.dirty is not False):
        raise RuntimeError("scene-topology reports require a clean committed worktree")
    config_relative = _require_canonical_repo_path(
        config_path,
        provenance.repository_root,
        "configs/template_v1_x.yaml",
    )
    fixture_relative = _require_canonical_repo_path(
        fixture_path,
        provenance.repository_root,
        "fixtures/grounding/bp35_seed11_initial_history.json",
    )
    matrix_path = Path(provenance.repository_root) / "artifacts/development_matrix_template_v1.json"
    matrix_relative = _require_canonical_repo_path(
        matrix_path,
        provenance.repository_root,
        "artifacts/development_matrix_template_v1.json",
    )
    matrix_bytes = matrix_path.read_bytes()
    if hashlib.sha256(matrix_bytes).hexdigest() != REGISTERED_TEMPLATE_MATRIX_SHA256:
        raise ValueError("registered template matrix digest does not match its frozen value")
    matrix = load_matrix(matrix_path)
    if {row.config_hash for row in matrix if row.arm_label == "X-T"} != {
        REGISTERED_X_T_CONFIG_SHA256
    }:
        raise ValueError("registered template matrix does not contain the frozen X-T config")
    config_bytes = config_path.read_bytes()
    fixture_bytes = fixture_path.read_bytes()
    fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
    if fixture_sha256 != FROZEN_BP35_FIXTURE_SHA256:
        raise ValueError("scene-topology fixture does not match the frozen bp35 input")
    fixture = json.loads(fixture_bytes)
    if not isinstance(fixture, dict) or fixture.get("schema_version") != 1:
        raise ValueError("scene-topology audit requires a schema-v1 fixture")
    records = _fixture_records(fixture)
    history_payload = json.dumps(
        records,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    history_sha256 = hashlib.sha256(history_payload).hexdigest()
    if history_sha256 != FROZEN_BP35_HISTORY_SHA256:
        raise ValueError("scene-topology history does not match the frozen bp35 input")
    if fixture.get("history_canonical_sha256") != history_sha256:
        raise ValueError("scene-topology fixture does not match its declared digest")
    history = history_from_records(records)
    sources = instantiate_structured_priors(history)
    programs = [
        {
            "candidate_index": index,
            "assigned_role": source.role,
            "source": source.source,
            "source_sha256": hashlib.sha256(source.source.encode("utf-8")).hexdigest(),
        }
        for index, source in enumerate(sources)
    ]
    compiled_points = cast(
        tuple[tuple[int, int], ...],
        dict(sources[0].bindings)["candidate_points"],
    )
    actions = candidates_from_history(
        history,
        cached_points=compiled_points,
        max_candidates=config.planning.max_candidates,
    )
    action_rows = [
        {
            "kind": int(action.kind),
            "row": action.row,
            "col": action.col,
        }
        for action in actions
    ]
    batch = audit_source_batch(
        programs,
        history,
        actions,
        config=config,
        win_levels=int(records[-1]["win_levels"]),
    )
    source_manifest = [
        {
            "compiler_role": source.role,
            "role_version": 1,
            "source_sha256": program["source_sha256"],
            "bindings_sha256": _canonical_sha256(dict(source.bindings)),
            "evidence_sha256": _canonical_sha256(source.evidence),
        }
        for source, program in zip(sources, programs, strict=True)
    ]
    if tuple(source.role for source in sources) != STRUCTURED_PRIOR_ROLES:
        raise RuntimeError("topology compiler roles do not match its public contract")
    template_library_sha256 = STRUCTURED_PRIOR_CONTRACT_SHA256
    instantiation_sha256 = _canonical_sha256(source_manifest)
    instantiation_policy_sha256 = hashlib.sha256(_INSTANTIATION_POLICY.encode("utf-8")).hexdigest()
    prior_contract_sha256 = _canonical_sha256(
        {
            "admission_contract_version": ADMISSION_CONTRACT_VERSION,
            "admission_overlay_version": SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION,
            "admission_overlay_sha256": SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256,
            "instantiation_policy_sha256": instantiation_policy_sha256,
            "compiler_contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "compiler_contract_sha256": template_library_sha256,
        }
    )
    batch_programs = batch["programs"]
    if not isinstance(batch_programs, list) or len(batch_programs) != len(sources):
        raise TypeError("source-batch audit returned malformed program reports")
    enriched_programs = [
        {
            **report,
            "source_origin": "scene_conditioned_topology_compiler",
            "compiler_role": source.role,
            "role_version": 1,
            "instantiation_bindings": dict(source.bindings),
            "binding_evidence": list(source.evidence),
            "recorded_transition_count": max(0, len(history.frames) - 1),
            "recorded_transition_scoring_used": False,
            "recorded_transition_precedence_used": dict(source.bindings)[
                "recorded_transition_used"
            ],
        }
        for report, source in zip(batch_programs, sources, strict=True)
    ]
    batch["programs"] = enriched_programs
    selection = batch.get("selection")
    gate = batch.get("gate")
    if not isinstance(selection, dict) or not isinstance(gate, dict):
        raise TypeError("source-batch audit returned malformed gate metadata")
    raw_selected_ids = selection.get("selected_ids")
    raw_selected_memory = selection.get("selected_worker_memory")
    raw_reasons = gate.get("reasons")
    if (
        not isinstance(raw_selected_ids, list)
        or not isinstance(raw_selected_memory, list)
        or not isinstance(raw_reasons, list)
    ):
        raise TypeError("source-batch audit returned malformed selection metadata")
    selected_ids = tuple(str(value) for value in raw_selected_ids)
    selected_memory = [
        cast(dict[str, Any], value)
        for value in raw_selected_memory
        if isinstance(value, dict)
    ]
    expected_headroom_bytes = config.sandbox.memory_mb * 1024 * 1024
    overlay_reasons, graded_eligible_roles = _scene_admission_overlay_reasons(
        batch_programs,
        selected_ids=selected_ids,
        selected_memory=selected_memory,
        expected_headroom_bytes=expected_headroom_bytes,
        require_linux_memory=require_linux_memory,
        execution_platform=sys.platform,
    )
    combined_reasons = list(
        dict.fromkeys([*(str(reason) for reason in raw_reasons), *overlay_reasons])
    )
    batch["gate"] = {"passes": not combined_reasons, "reasons": combined_reasons}
    return {
        "schema_version": 2,
        "contract_version": ADMISSION_CONTRACT_VERSION,
        "admission_overlay_version": SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION,
        "admission_overlay_sha256": SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256,
        "status": "pilot_admitted" if not combined_reasons else "pilot_blocked",
        "offline": True,
        "git": {
            key: value
            for key, value in asdict(provenance).items()
            if key != "repository_root"
        },
        "producer": {
            "producer_kind": "deterministic_scene_topology_compiler",
            "producer_id": "arc3_voi.topology_compiler.compile_topology_programs",
            "producer_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "producer_contract_sha256": prior_contract_sha256,
            "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
            "compiler_code_sha256": TOPOLOGY_COMPILER_CODE_SHA256,
            "instantiation_sha256": instantiation_sha256,
            "instantiation_policy_sha256": instantiation_policy_sha256,
            "instantiation_policy": _INSTANTIATION_POLICY,
            "model_id": None,
            "model_calls": 0,
            "generated_tokens": 0,
            "backbone_used": False,
            "producer_invocations": 1,
            "proposal_batches_charged": 0,
            "budget_scope": "offline capability audit; not a live controller run",
        },
        "inputs": {
            "fixture": fixture_relative,
            "fixture_sha256": fixture_sha256,
            "config": config_relative,
            "config_file_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "config_sha256": config_sha256,
            "registered_matrix": matrix_relative,
            "registered_matrix_sha256": REGISTERED_TEMPLATE_MATRIX_SHA256,
            "hypothesis_source": config.experiment.hypothesis_source,
            "controller_variant": config.experiment.variant,
            "arm_label": "X-T",
            "history_canonical_sha256": history_sha256,
            "latest_grid_sha256": _grid_sha256(history),
            "candidate_set": action_rows,
            "candidate_set_sha256": _canonical_sha256(action_rows),
            "candidate_policy_version": CANDIDATE_POLICY_VERSION,
            "candidate_policy_sha256": CANDIDATE_POLICY_HASH,
            "candidate_policy": (
                "source-neutral candidates_from_history with scene-compiler points as "
                "the proposal frontier"
            ),
        },
        "scene_topology_compiler": {
            "contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
            "admission_contract_version": ADMISSION_CONTRACT_VERSION,
            "admission_overlay_sha256": SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256,
            "offline_only": True,
            "source_count": len(sources),
            "roles": [source.role for source in sources],
            "source_manifest": source_manifest,
            "instantiation_sha256": instantiation_sha256,
            "history_conditioning": (
                "bindings compiled from latest scene topology and the most recent "
                "representable recorded transition"
            ),
            "coordinate_and_palette_policy": (
                "derive all target coordinates and colours from History; no game IDs, "
                "hand-authored coordinates, or hand-authored palette identities"
            ),
            "simple_action_policy": (
                "opaque simple actions preserve the grid unless directly supported by "
                "a recorded transition"
            ),
            "terminal_policy": (
                "preserve current state generically; replay terminal state only when "
                "direct recorded-transition evidence applies"
            ),
            "empirical_transition_grounding_claimed": False,
            "tested_properties": [
                "deterministic same-history compilation",
                "recorded-transition precedence",
                "restricted-AST and bounded-grid execution",
                "visible-palette permutation equivariance on synthetic scenes",
                "interior translation equivariance without clipping on synthetic scenes",
                "uniform integer-scale equivariance on synthetic scenes",
            ],
            "known_unverified_properties": [
                "palette-permutation equivariance under every structural tie",
                "translation equivariance at frame boundaries",
                "integer-scale equivariance when topology or clipping changes",
            ],
            "report_requires_clean_commit": require_clean_commit,
        },
        "contract": {
            "planning_depth": config.planning.depth,
            "beam_width": config.planning.beam_width,
            "agreement_threshold": config.planning.agreement_threshold,
            "material_evsi_threshold_actions": MATERIAL_EVSI_THRESHOLD,
            "initial_cross_level_persistence": INITIAL_CROSS_LEVEL_PERSISTENCE,
            "minimum_eligible_graded_roles": 2,
            "eligible_graded_roles": graded_eligible_roles,
            "require_linux_memory": require_linux_memory,
            "expected_allocation_headroom_bytes": expected_headroom_bytes,
            "required_memory_limit_kind": RLIMIT_DATA_HEADROOM_KIND,
            "execution_platform": sys.platform,
            "admission_rule": (
                "shared runtime-admission-v2 role checks, behavioral deduplication, "
                "depth-four planning, and X-only probe opportunity"
            ),
            "overlay_rule": (
                "registered X-T config and frozen bp35 fixture; at least two eligible "
                "graded roles; selected persistent workers exactly identified and, for "
                "canonical evidence, Linux RLIMIT_DATA hard headroom exactly equal to the "
                "configured 256 MiB allocation budget"
            ),
            "interpretation": (
                "counterfactual capability diagnostic only; not transition accuracy, "
                "gameplay readiness, or evidence of model-generated induction"
            ),
        },
        **batch,
    }


def _scene_admission_overlay_reasons(
    program_reports: Sequence[Mapping[str, Any]],
    *,
    selected_ids: Sequence[str],
    selected_memory: Sequence[Mapping[str, Any]],
    expected_headroom_bytes: int,
    require_linux_memory: bool,
    execution_platform: str,
) -> tuple[list[str], list[str]]:
    graded_eligible_roles = [
        str(report["assigned_role"])
        for report in program_reports
        if int(report["candidate_index"]) > 0
        and bool(cast(Mapping[str, Any], report["eligibility"])["eligible"])
    ]
    reasons: list[str] = []
    if len(graded_eligible_roles) < 2:
        reasons.append("fewer than two graded compiler roles are eligible")
    memory_ids = {str(memory.get("hypothesis_id")) for memory in selected_memory}
    if len(selected_memory) != len(selected_ids) or memory_ids != set(selected_ids):
        reasons.append("selected worker memory evidence is incomplete or misaligned")
    if require_linux_memory and execution_platform != "linux":
        reasons.append("canonical admission requires Linux hard memory enforcement")
    elif require_linux_memory and any(
        memory.get("hard_limit_enforced") is not True
        or memory.get("limit_kind") != RLIMIT_DATA_HEADROOM_KIND
        or memory.get("allocation_headroom_bytes") != expected_headroom_bytes
        for memory in selected_memory
    ):
        reasons.append("selected programs did not verify the exact hard allocation headroom")
    return reasons, graded_eligible_roles


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _grid_sha256(history: History) -> str:
    grid = history.latest_grid
    digest = hashlib.sha256()
    digest.update(int(grid.shape[0]).to_bytes(4, "big"))
    digest.update(int(grid.shape[1]).to_bytes(4, "big"))
    digest.update(grid.tobytes(order="C"))
    return digest.hexdigest()


def _require_canonical_repo_path(
    path: Path, repository_root: str, expected_relative: str
) -> str:
    root = Path(repository_root).resolve()
    try:
        relative = path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("admission inputs must resolve inside the repository") from exc
    if relative != expected_relative:
        raise ValueError(f"admission input must be {expected_relative}, got {relative}")
    return relative


def _fixture_records(fixture: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_history = fixture.get("history")
    if not isinstance(raw_history, list) or not raw_history:
        raise ValueError("structured-prior fixture history is empty")
    records: list[dict[str, Any]] = []
    for raw in raw_history:
        if not isinstance(raw, dict):
            raise ValueError("structured-prior fixture history row is not an object")
        rows = raw.get("grid_hex_rows")
        if (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(row, str) or len(row) != len(rows[0]) for row in rows)
        ):
            raise ValueError("structured-prior fixture has malformed hexadecimal rows")
        try:
            grid = [[int(character, 16) for character in row] for row in rows]
        except ValueError as exc:
            raise ValueError("structured-prior fixture has a non-hexadecimal cell") from exc
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


SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "external_contracts": {
                "admission_contract_version": ADMISSION_CONTRACT_VERSION,
                "candidate_policy_sha256": CANDIDATE_POLICY_HASH,
                "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
                "fixture_sha256": FROZEN_BP35_FIXTURE_SHA256,
                "history_sha256": FROZEN_BP35_HISTORY_SHA256,
                "initial_cross_level_persistence": INITIAL_CROSS_LEVEL_PERSISTENCE,
                "material_evsi_threshold": MATERIAL_EVSI_THRESHOLD,
                "memory_limit_kind": RLIMIT_DATA_HEADROOM_KIND,
                "registered_config_sha256": REGISTERED_X_T_CONFIG_SHA256,
                "registered_matrix_sha256": REGISTERED_TEMPLATE_MATRIX_SHA256,
            },
            "implementation": [
                inspect.getsource(item)
                for item in (
                    run_scene_topology_admission_audit,
                    _scene_admission_overlay_reasons,
                    _require_canonical_repo_path,
                    _fixture_records,
                )
            ],
            "version": SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


# Compatibility alias for historical callers; new evidence must use topology terminology.
run_structured_prior_audit = run_scene_topology_admission_audit


__all__ = [
    "SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256",
    "SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION",
    "STRUCTURED_PRIOR_CONTRACT_SHA256",
    "STRUCTURED_PRIOR_CONTRACT_VERSION",
    "STRUCTURED_PRIOR_ROLES",
    "TOPOLOGY_COMPILER_ALGORITHM_VERSION",
    "TOPOLOGY_COMPILER_CODE_SHA256",
    "StructuredPriorSource",
    "instantiate_structured_priors",
    "run_scene_topology_admission_audit",
    "run_structured_prior_audit",
]
