"""Offline-only executable priors over generic visual transformations.

This module is deliberately disconnected from the live controller.  It provides a
fixed deterministic source library for testing whether generic structured alternatives
can clear the existing grounding and cross-level value-of-information admission gates.
The sources are not inferred from transitions and are not evidence of model induction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

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
from .types import History

STRUCTURED_PRIOR_CONTRACT_VERSION = "generic-visual-priors-v1"
_INSTANTIATION_POLICY = (
    "emit the same four runtime-grounded generic priors for every non-empty 2-D history; "
    "embed no observed coordinate, palette value, game ID, or transition-derived binding"
)


@dataclass(frozen=True, slots=True)
class StructuredPriorSource:
    """One fixed generic-prior role and its restricted Python source."""

    role: str
    source: str


_CONSERVATIVE_SOURCE = '''\
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    return 0.0
'''


_LOCAL_CONTACT_SOURCE = '''\
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    kind = int(action.kind)
    if kind == 6:
        row = int(action.row)
        col = int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            value = grid[row, col]
            changed = 0
            limit = max(height, width)
            for distance in range(1, limit):
                points = (
                    (row - distance, col),
                    (row + distance, col),
                    (row, col - distance),
                    (row, col + distance),
                )
                for next_row, next_col in points:
                    in_bounds = 0 <= next_row < height and 0 <= next_col < width
                    if in_bounds and grid[next_row, next_col] != value:
                        grid[next_row, next_col] = value
                        changed += 1
                        if changed == 2:
                            break
                if changed == 2:
                    break
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    latest = history.actions[-1]
    if latest is None or int(latest.kind) != 6:
        return 0.0
    grid = np.array(history.frames[-1], dtype=np.int16)
    row = int(latest.row)
    col = int(latest.col)
    height, width = grid.shape
    if not (0 <= row < height and 0 <= col < width):
        return 0.0
    value = grid[row, col]
    row_matches = int(np.count_nonzero(grid[row, :] == value))
    col_matches = int(np.count_nonzero(grid[:, col] == value))
    return float(row_matches + col_matches - 1) / float(height + width - 1)
'''


_COMPONENT_HELPER = '''\
def component_mask(grid, row, col):
    same = grid == grid[row, col]
    mask = np.zeros_like(same, dtype=np.bool_)
    mask[row, col] = True
    height, width = grid.shape
    for step in range(height + width):
        expanded = mask.copy()
        expanded[1:, :] = np.logical_or(expanded[1:, :], mask[:-1, :])
        expanded[:-1, :] = np.logical_or(expanded[:-1, :], mask[1:, :])
        expanded[:, 1:] = np.logical_or(expanded[:, 1:], mask[:, :-1])
        expanded[:, :-1] = np.logical_or(expanded[:, :-1], mask[:, 1:])
        expanded = np.logical_and(expanded, same)
        if np.array_equal(expanded, mask):
            break
        mask = expanded
    return mask
'''


_COMPONENT_SELECTION_SOURCE = (
    _COMPONENT_HELPER
    + '''\

def palette_summary(grid):
    values, counts = np.unique(grid, return_counts=True)
    background_index = int(np.argmax(counts))
    background = values[background_index]
    foreground_values = values[values != background]
    foreground_counts = counts[values != background]
    if len(foreground_values) == 0:
        return background, background, 0
    target_index = int(np.argmax(foreground_counts))
    return background, foreground_values[target_index], int(np.sum(foreground_counts))

def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    kind = int(action.kind)
    if kind == 6:
        row = int(action.row)
        col = int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            background, target, foreground_total = palette_summary(grid)
            if foreground_total > 0 and grid[row, col] != background:
                selected = component_mask(grid, row, col)
                grid[selected] = target
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    grid = np.array(history.frames[-1], dtype=np.int16)
    background, target, foreground_total = palette_summary(grid)
    if foreground_total == 0:
        return 1.0
    target_total = int(np.count_nonzero(grid == target))
    return float(target_total) / float(foreground_total)
'''
)


_COMPONENT_STATE_SOURCE = (
    _COMPONENT_HELPER
    + '''\

def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    kind = int(action.kind)
    if kind == 6:
        row = int(action.row)
        col = int(action.col)
        height, width = grid.shape
        if 0 <= row < height and 0 <= col < width:
            values, counts = np.unique(grid, return_counts=True)
            order = np.argsort(counts)
            ordered_values = values[order]
            source = grid[row, col]
            source_positions = np.nonzero(ordered_values == source)[0]
            if len(source_positions) > 0:
                source_index = int(source_positions[0])
                target_index = min(source_index + 1, len(ordered_values) - 1)
                selected = component_mask(grid, row, col)
                grid[selected] = ordered_values[target_index]
    return {
        "next_grid": grid,
        "game_state": history.game_states[-1],
        "level_delta": 0,
        "memory": {},
    }

def goal_value(history):
    grid = np.array(history.frames[-1], dtype=np.int16)
    values, counts = np.unique(grid, return_counts=True)
    if len(values) == 0:
        return 0.0
    return float(np.max(counts)) / float(grid.size)
'''
)


def instantiate_structured_priors(history: History) -> tuple[StructuredPriorSource, ...]:
    """Return exactly four generic visual priors after validating ``history``.

    The history is only a validity boundary. Every call emits byte-identical sources;
    the programs derive coordinates and palette values from sanitized runtime inputs.
    """

    if not history.frames:
        raise ValueError("structured-prior instantiation requires a non-empty history")
    if history.latest_grid.ndim != 2 or not history.latest_grid.size:
        raise ValueError("structured-prior instantiation requires a non-empty 2-D grid")
    return (
        StructuredPriorSource("conservative_no_effect", _CONSERVATIVE_SOURCE),
        StructuredPriorSource("local_action6_contact", _LOCAL_CONTACT_SOURCE),
        StructuredPriorSource("action6_component_selection", _COMPONENT_SELECTION_SOURCE),
        StructuredPriorSource("action6_component_state", _COMPONENT_STATE_SOURCE),
    )


def run_structured_prior_audit(
    fixture_path: Path,
    config: SystemConfig,
    *,
    require_clean_commit: bool = True,
) -> dict[str, Any]:
    """Run the exact producer-neutral admission path against generic prior sources.

    This is a capability diagnostic, not an empirical transition-model evaluation.
    The sources still pass through the shared role checks, sandbox, behavioral
    deduplication, depth-four planner, and X-only-probe admission rule.
    """

    provenance = inspect_git_provenance()
    if require_clean_commit and (
        provenance.commit is None or provenance.dirty is not False
    ):
        raise RuntimeError(
            "structured-prior reports require a clean committed worktree"
        )
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
    actions = candidates_from_history(
        history,
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
        }
        for source, program in zip(sources, programs, strict=True)
    ]
    template_library_sha256 = _canonical_sha256(source_manifest)
    instantiation_policy_sha256 = hashlib.sha256(
        _INSTANTIATION_POLICY.encode("utf-8")
    ).hexdigest()
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
            "source_origin": "generic_structured_prior",
            "template_id": source.role,
            "template_version": 1,
            "template_family": source.role,
            "instantiation_bindings": {},
            "recorded_transition_count": max(0, len(history.frames) - 1),
            "recorded_transition_scoring_used": False,
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
            "producer_kind": "deterministic_structured_prior_library",
            "producer_id": "arc3_voi.structured_templates",
            "producer_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "producer_contract_sha256": prior_contract_sha256,
            "template_library_sha256": template_library_sha256,
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
            "candidate_policy": "source-neutral candidates_from_history; no cached points",
        },
        "structured_prior_library": {
            "contract_version": STRUCTURED_PRIOR_CONTRACT_VERSION,
            "admission_contract_version": ADMISSION_CONTRACT_VERSION,
            "offline_only": True,
            "source_count": len(sources),
            "roles": [source.role for source in sources],
            "source_manifest": source_manifest,
            "history_conditioning": "validity check only; emitted source is history-invariant",
            "coordinate_and_palette_policy": (
                "derive bounds, coordinates, four-connected components, and palette "
                "values from sanitized History and ACTION6 inputs"
            ),
            "simple_action_policy": "opaque simple actions preserve the current grid",
            "terminal_policy": (
                "preserve current game state and always predict zero level delta"
            ),
            "empirical_transition_grounding_claimed": False,
            "known_unverified_properties": [
                "palette-permutation equivariance under equal-frequency ties",
                "scale equivariance",
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
    "STRUCTURED_PRIOR_CONTRACT_VERSION",
    "StructuredPriorSource",
    "instantiate_structured_priors",
    "run_structured_prior_audit",
]
