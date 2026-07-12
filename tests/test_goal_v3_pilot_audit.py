from __future__ import annotations

import hashlib
import json

import pytest

from arc3_voi.runtime.sandbox import validate_program
from scripts.audit_goal_v3_pilot import (
    EVSI_ZERO_TOLERANCE,
    AuditError,
    audit_resets,
    committee_telemetry,
    compare_mx,
    live_pool_grounding,
)

CONSERVATIVE_PROGRAM = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}

def goal_value(history):
    return 0.25
"""

ACTION_PROGRAM = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    if int(action.kind) == 6:
        grid[int(action.row), int(action.col)] = 1
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}

def goal_value(history):
    return float(np.count_nonzero(history.frames[-1] == 1)) / 4096.0
"""


def _mx_row(*, variant: str, multiplier: float, utility: float) -> dict[str, object]:
    return {
        "step": 1,
        "action": {"kind": "ACTION3"},
        "history": [{"game_state": "NOT_FINISHED", "grid": [[0]]}],
        "observed_grid": [[0]],
        "weighted_transition_loss": 0.1,
        "hypothesis_weights": [0.5, 0.5],
        "elapsed_seconds": 0.2 if variant == "M" else 0.3,
        "probe_utility": utility,
        "decision_diagnostics": {
            "variant": variant,
            "level_multiplier": multiplier,
            "probe_utility": utility,
            "probe_evsi": 0.0,
        },
    }


def test_mx_comparison_removes_only_declared_fields() -> None:
    m = (_mx_row(variant="M", multiplier=1.0, utility=-1.0),)
    x = (_mx_row(variant="X", multiplier=23.0, utility=-0.99999999999998),)

    result = compare_mx(m, x)

    assert result["equal_after_declared_normalization"] is True
    assert result["M_normalized_sha256"] == result["X_normalized_sha256"]
    assert result["difference_path_counts"] == {
        "decision_diagnostics.level_multiplier": 1,
        "decision_diagnostics.probe_utility": 1,
        "decision_diagnostics.variant": 1,
        "elapsed_seconds": 1,
        "probe_utility": 1,
    }


def test_mx_comparison_rejects_substantive_action_difference() -> None:
    m = (_mx_row(variant="M", multiplier=1.0, utility=-1.0),)
    changed = _mx_row(variant="X", multiplier=23.0, utility=-1.0)
    changed["action"] = {"kind": "ACTION4"}

    with pytest.raises(AuditError, match="unexpected M/X differences"):
        compare_mx(m, (changed,))


def test_reset_audit_requires_immediate_game_over_in_trace_and_history() -> None:
    legal = (
        {"step": 1, "action": {"kind": "ACTION3"}, "observed_state": "GAME_OVER"},
        {
            "step": 2,
            "action": {"kind": "RESET"},
            "history": [{"game_state": "GAME_OVER"}],
            "observed_state": "NOT_FINISHED",
        },
    )
    assert audit_resets(legal)["all_resets_legal"] is True

    illegal = (legal[0], {**legal[1], "history": [{"game_state": "NOT_FINISHED"}]})
    with pytest.raises(AuditError, match="illegal RESET"):
        audit_resets(illegal)


def _planning_row(*, variant: str, multiplier: float, evsi: float) -> dict[str, object]:
    return {
        "step": 1,
        "action": {"kind": "ACTION3"},
        "decision_mode": "exploit",
        "decision_diagnostics": {
            "candidate_costs": json.dumps(
                {"ACTION3": [4.0, 5.0], "ACTION6(1,1)": [4.0, 5.0]}
            ),
            "candidate_prediction_signatures": json.dumps(
                {"ACTION3": ["a", "a"], "ACTION6(1,1)": ["b", "c"]}
            ),
            "probe_evsi": evsi,
            "probe_selected": False,
            "probe_catastrophe_probability": 0.0,
            "agreement": 1.0,
            "probe_gate_reason": "agreement_at_or_above_threshold",
            "level_multiplier": multiplier,
            "variant": variant,
        },
    }


def test_committee_telemetry_treats_machine_epsilon_evsi_as_zero() -> None:
    m = (_planning_row(variant="M", multiplier=1.0, evsi=8.881784197001252e-16),)
    x = (_planning_row(variant="X", multiplier=23.0, evsi=8.881784197001252e-16),)

    result = committee_telemetry(m, x)

    assert EVSI_ZERO_TOLERANCE == 1e-12
    assert result["evsi_positive_roundoff_rows"] == 1
    assert result["evsi_material_nonzero_rows"] == 0
    assert result["all_evsi_effectively_zero"] is True
    assert result["rows_with_prediction_signature_disagreement"] == 1


def _grounding_program(
    source: str, *, index: int, eligible: bool, signature: str
) -> dict[str, object]:
    validated = validate_program(source)
    return {
        "candidate_index": index,
        "source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "ast_nodes": validated.node_count,
        "assigned_role": f"role-{index}",
        "behavior_signature": signature,
        "eligible": eligible,
        "action_sensitive": index == 1,
        "action_sensitivity_required": index == 1,
        "goal_action_conditioned": index == 1,
        "goal_conditioning_required": index == 1,
    }


def test_live_pool_grounding_detects_selected_ineligible_program() -> None:
    grounding = {
        "programs": [
            _grounding_program(
                CONSERVATIVE_PROGRAM,
                index=0,
                eligible=True,
                signature="shared",
            ),
            _grounding_program(
                ACTION_PROGRAM,
                index=1,
                eligible=False,
                signature="distinct",
            ),
        ]
    }
    generated = json.dumps([CONSERVATIVE_PROGRAM, ACTION_PROGRAM])
    selected = validate_program(ACTION_PROGRAM).sha256
    row = {
        "hypothesis_ids": [selected],
        "decision_diagnostics": {"generated_program_sources": generated},
    }

    result = live_pool_grounding(grounding, (row,), (row,))

    assert result["grounding_selection_mismatch_detected"] is True
    assert result["grounding_eligible_live_programs"] == 0
    assert result["live_selected_grounding_ineligible_ids"] == [selected]
