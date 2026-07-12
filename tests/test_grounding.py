from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from arc3_voi.grounding import (
    audit_palette_claims,
    evaluate_program_grounding,
    grounding_gate_reasons,
)
from arc3_voi.types import Action, ActionKind, GameState, History, Observation

SAFE_PROGRAM = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int8)
    kind = int(action.kind)
    if kind == 6:
        grid[int(action.row), int(action.col)] = 1
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    grid = np.array(history.frames[-1], dtype=np.int8)
    return float(np.count_nonzero(grid == 1)) / float(grid.size)
"""

SECOND_SAFE_PROGRAM = SAFE_PROGRAM.replace("= 1", "= 2")

CONSTANT_GOAL_PROGRAM = SAFE_PROGRAM.replace(
    "grid = np.array(history.frames[-1], dtype=np.int8)\n"
    "    return float(np.count_nonzero(grid == 1)) / float(grid.size)",
    "return 0.0",
)

UNREACHABLE_GOAL_PROGRAM = SAFE_PROGRAM.replace(
    "return float(np.count_nonzero(grid == 1)) / float(grid.size)",
    "return 1.0 if np.count_nonzero(grid == 1) > 100 else 0.0",
)

TIME_ONLY_GOAL_PROGRAM = SAFE_PROGRAM.replace(
    "grid = np.array(history.frames[-1], dtype=np.int8)\n"
    "    return float(np.count_nonzero(grid == 1)) / float(grid.size)",
    "return min(1.0, float(len(history.frames)) / 8.0)",
)

UNSAFE_PROGRAM = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int8)
    row = action.row + 1
    grid[row % grid.shape[0], 0] = 1
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return 0.0
"""

BROKEN_FOR_EVERY_ACTION_PROGRAM = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int8)
    if int(action.kind) == 6:
        row = int(action.row)
        col = int(action.col)
    value = history.levels[-1].get("missing", 0)
    grid[0, 0] = value
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return 0.0
"""


def _history() -> History:
    return History.from_observation(
        Observation(
            np.zeros((4, 4), dtype=np.int8),
            frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
            GameState.NOT_FINISHED,
            1,
            2,
        )
    )


def test_action_matrix_catches_unconditional_coordinate_arithmetic() -> None:
    result = evaluate_program_grounding(
        UNSAFE_PROGRAM,
        _history(),
        (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2)),
        timeout_seconds=1.0,
    )
    assert result.sandbox_valid
    assert result.coordinate_read_lines
    assert not result.simple_action_contract_ok
    assert result.unsafe_coordinate_use


def test_general_execution_failure_is_not_mislabeled_as_coordinate_use() -> None:
    result = evaluate_program_grounding(
        BROKEN_FOR_EVERY_ACTION_PROGRAM,
        _history(),
        (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2)),
        timeout_seconds=1.0,
    )

    assert result.coordinate_read_lines
    assert not result.all_actions_ok
    assert not result.unsafe_coordinate_use


def test_action_matrix_accepts_action6_guard_and_distinct_gate() -> None:
    actions = (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2))
    first = evaluate_program_grounding(SAFE_PROGRAM, _history(), actions, timeout_seconds=1.0)
    second = evaluate_program_grounding(
        SECOND_SAFE_PROGRAM, _history(), actions, timeout_seconds=1.0
    )
    assert first.eligible and second.eligible
    assert first.action_sensitive and second.action_sensitive
    assert first.goal_sensitive and second.goal_sensitive
    assert not grounding_gate_reasons(
        (first, second),
        truncated_sequences=0,
        peak_vram_gb=10.0,
        tokens_per_second=20.0,
    )
    enforced = (
        replace(first, hard_memory_limit_enforced=True),
        replace(second, hard_memory_limit_enforced=True),
    )
    assert not grounding_gate_reasons(
        enforced,
        truncated_sequences=0,
        peak_vram_gb=10.0,
        tokens_per_second=20.0,
        require_hard_memory_limit=True,
    )
    assert "hard sandbox memory limit" in grounding_gate_reasons(
        (replace(first, hard_memory_limit_enforced=False), enforced[1]),
        truncated_sequences=0,
        peak_vram_gb=10.0,
        tokens_per_second=20.0,
        require_hard_memory_limit=True,
    )[0]


def test_action_sensitive_role_requires_graded_counterfactual_goal() -> None:
    actions = (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2))
    result = evaluate_program_grounding(
        SAFE_PROGRAM,
        _history(),
        actions,
        timeout_seconds=1.0,
        rollout_depth=4,
        require_action_sensitivity=True,
        require_goal_sensitivity=True,
    )

    assert result.eligible
    assert result.goal_value_ok
    assert result.goal_sensitive
    assert result.goal_value_range == 1 / 16
    assert result.max_action_goal_spread == 1 / 16
    assert len(result.goal_results) == len(actions) * 4
    assert all(item.ok for item in result.goal_results)


@pytest.mark.parametrize("source", [CONSTANT_GOAL_PROGRAM, UNREACHABLE_GOAL_PROGRAM])
def test_constant_or_unreachable_goal_fails_graded_role_gate(source: str) -> None:
    actions = (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2))
    result = evaluate_program_grounding(
        source,
        _history(),
        actions,
        timeout_seconds=1.0,
        rollout_depth=4,
        require_action_sensitivity=True,
        require_goal_sensitivity=True,
    )

    assert result.sandbox_valid
    assert result.all_actions_ok
    assert result.action_sensitive
    assert result.goal_value_ok
    assert not result.goal_sensitive
    assert result.goal_value_range == 0.0
    assert not result.eligible


def test_depth_only_goal_does_not_count_as_action_sensitive_progress() -> None:
    actions = (Action(ActionKind.ACTION3), Action(ActionKind.ACTION6, row=1, col=2))
    result = evaluate_program_grounding(
        TIME_ONLY_GOAL_PROGRAM,
        _history(),
        actions,
        timeout_seconds=1.0,
        rollout_depth=4,
        require_action_sensitivity=True,
        require_goal_sensitivity=True,
    )

    assert result.goal_value_ok
    assert result.goal_value_range is not None and result.goal_value_range > 0
    assert result.max_action_goal_spread == 0.0
    assert not result.goal_sensitive
    assert not result.eligible


def test_palette_audit_flags_explicit_conflicts_only() -> None:
    conflicts = audit_palette_claims(
        "# red is 7, green is 3, brown is 10\n"
        "red_locs = np.argwhere(grid == 7)\n"
        "value = 10\n"
    )
    assert {(claim.color, claim.claimed_value) for claim in conflicts} >= {
        ("red", 7),
        ("green", 3),
        ("brown", 10),
    }
    assert all(claim.conflict for claim in conflicts)
    accepted = audit_palette_claims(
        "red_locs = np.argwhere(grid == 8)\n"
        "green_locs = np.argwhere(grid == 14)\n"
    )
    assert accepted and not any(claim.conflict for claim in accepted)


def test_palette_audit_ignores_counts_coordinates_and_unrelated_comment_numbers() -> None:
    claims = audit_palette_claims(
        "red_count = 3\n"
        "red_col = 7\n"
        "if int(action.kind) == 6:  # red player\n"
        "    value = 10\n"
    )
    assert not claims


def test_palette_audit_accepts_off_white_and_off_black_value_bindings() -> None:
    claims = audit_palette_claims("off_white = 1\noff_black_value = 4\n")
    assert {(claim.color, claim.claimed_value) for claim in claims} == {
        ("off white", 1),
        ("off black", 4),
    }
    assert not any(claim.conflict for claim in claims)
