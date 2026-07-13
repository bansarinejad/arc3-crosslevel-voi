"""Offline-only scene-conditioned executable topology hypotheses.

This module remains disconnected from the live controller. It compiles inspectable
bindings from finite observable history and evaluates them through the shared admission
path. The deterministic sources are not evidence of model-generated induction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from .candidates import candidates_from_history
from .config import SystemConfig
from .experiment import stable_config_hash
from .provenance import inspect_git_provenance
from .replay import history_from_records
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


def run_structured_prior_audit(
    fixture_path: Path,
    config: SystemConfig,
    *,
    require_clean_commit: bool = True,
) -> dict[str, Any]:
    """Run producer-neutral admission against compiled topology sources.

    This is a capability diagnostic, not an empirical transition-model evaluation.
    The sources still pass through the shared role checks, sandbox, behavioral
    deduplication, depth-four planner, and X-only-probe admission rule.
    """

    provenance = inspect_git_provenance()
    if require_clean_commit and (provenance.commit is None or provenance.dirty is not False):
        raise RuntimeError("structured-prior reports require a clean committed worktree")
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes)
    if not isinstance(fixture, dict) or fixture.get("schema_version") != 1:
        raise ValueError("structured-prior audit requires a schema-v1 fixture")
    records = _fixture_records(fixture)
    history_payload = json.dumps(
        records,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    history_sha256 = hashlib.sha256(history_payload).hexdigest()
    if fixture.get("history_canonical_sha256") != history_sha256:
        raise ValueError("structured-prior fixture does not match its declared digest")
    history = history_from_records(records)
    instantiation_started = perf_counter()
    sources = instantiate_structured_priors(history)
    instantiation_wall_seconds = perf_counter() - instantiation_started
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
            "template_id": source.role,
            "template_version": 1,
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
            "instantiation_policy_sha256": instantiation_policy_sha256,
            "prior_contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "template_library_sha256": template_library_sha256,
        }
    )
    batch_programs = batch["programs"]
    if not isinstance(batch_programs, list) or len(batch_programs) != len(sources):
        raise TypeError("source-batch audit returned malformed program reports")
    enriched_programs = [
        {
            **report,
            "source_origin": "scene_conditioned_topology_compiler",
            "template_id": source.role,
            "template_version": 1,
            "template_family": source.role,
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
    return {
        "schema_version": 1,
        "contract_version": ADMISSION_CONTRACT_VERSION,
        "status": "pilot_admitted" if batch["gate"]["passes"] else "pilot_blocked",
        "offline": True,
        "git": asdict(provenance),
        "producer": {
            "producer_kind": "deterministic_scene_topology_compiler",
            "producer_id": "arc3_voi.structured_templates",
            "producer_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "producer_contract_sha256": prior_contract_sha256,
            "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
            "compiler_code_sha256": TOPOLOGY_COMPILER_CODE_SHA256,
            "template_library_sha256": template_library_sha256,
            "instantiation_sha256": instantiation_sha256,
            "instantiation_policy_sha256": instantiation_policy_sha256,
            "instantiation_policy": _INSTANTIATION_POLICY,
            "model_id": None,
            "model_calls": 0,
            "generated_tokens": 0,
            "backbone_used": False,
            "producer_invocations": 1,
            "proposal_batches_charged": 0,
            "instantiation_wall_seconds": instantiation_wall_seconds,
            "budget_scope": "offline capability audit; not a live controller run",
        },
        "inputs": {
            "fixture": _repo_relative_path(fixture_path, provenance.repository_root),
            "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "history_canonical_sha256": history_sha256,
            "latest_grid_sha256": _grid_sha256(history),
            "planning_config_sha256": stable_config_hash(config),
            "candidate_set": action_rows,
            "candidate_set_sha256": _canonical_sha256(action_rows),
            "candidate_policy": (
                "source-neutral candidates_from_history with scene-compiler points as "
                "the proposal frontier"
            ),
        },
        "structured_prior_library": {
            "contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "compiler_contract_sha256": STRUCTURED_PRIOR_CONTRACT_SHA256,
            "admission_contract_version": ADMISSION_CONTRACT_VERSION,
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
            "admission_rule": (
                "shared runtime-admission-v2 role checks, behavioral deduplication, "
                "depth-four planning, and X-only probe opportunity"
            ),
            "interpretation": (
                "counterfactual capability diagnostic only; not transition accuracy, "
                "gameplay readiness, or evidence of model-generated induction"
            ),
        },
        **batch,
    }


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


def _repo_relative_path(path: Path, repository_root: str) -> str:
    try:
        return path.resolve().relative_to(Path(repository_root).resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


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


__all__ = [
    "STRUCTURED_PRIOR_CONTRACT_SHA256",
    "STRUCTURED_PRIOR_CONTRACT_VERSION",
    "STRUCTURED_PRIOR_ROLES",
    "TOPOLOGY_COMPILER_ALGORITHM_VERSION",
    "TOPOLOGY_COMPILER_CODE_SHA256",
    "StructuredPriorSource",
    "instantiate_structured_priors",
    "run_structured_prior_audit",
]
