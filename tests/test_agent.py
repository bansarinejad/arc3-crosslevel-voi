from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, cast

import numpy as np
import pytest

from arc3_voi.agent import build_agent
from arc3_voi.config import ExperimentConfig, SandboxConfig, SystemConfig
from arc3_voi.hypothesis import Hypothesis, behavioral_deduplicate
from arc3_voi.model import ScriptedBackend
from arc3_voi.program import ExecutableHypothesis
from arc3_voi.runtime.sandbox import validate_program
from arc3_voi.types import ActionKind, Budget, GameState, Observation

PROGRAM_A = """
def predict(history, action):
    return {
        "next_grid": history.frames[-1].copy(),
        "game_state": "NOT_FINISHED",
        "level_delta": 0,
        "memory": {},
    }
def goal_value(history):
    return 0.1
"""

PROGRAM_B = """
def predict(history, action):
    grid = history.frames[-1].copy()
    grid[0, 0] = (grid[0, 0] + int(action.kind)) % 2
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return float(np.clip(history.frames[-1][0, 0], 0.0, 1.0))
"""

CONSERVATIVE_LARGE = """
def predict(history, action):
    grid = history.frames[-1].copy()
    occupied = np.count_nonzero(grid)
    unchanged = occupied + 0
    return {
        "next_grid": grid,
        "game_state": "NOT_FINISHED",
        "level_delta": 0,
        "memory": {"unchanged": unchanged},
    }
def goal_value(history):
    grid = history.frames[-1]
    return float(np.clip(np.count_nonzero(grid) / max(1, grid.size), 0.0, 1.0))
"""

SENSITIVE_FIRST_CELL = """
def predict(history, action):
    grid = history.frames[-1].copy()
    grid[0, 0] = int(action.kind) % 2
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return float(np.clip(history.frames[-1][0, 0], 0.0, 1.0))
"""

SENSITIVE_SECOND_CELL = """
def predict(history, action):
    grid = history.frames[-1].copy()
    grid[0, 1] = (int(action.kind) + 1) % 2
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return float(np.clip(history.frames[-1][0, 1], 0.0, 1.0))
"""

CONSERVATIVE_SMALL = """
def predict(history, action):
    return {
        "next_grid": history.frames[-1].copy(),
        "game_state": "NOT_FINISHED",
        "level_delta": 0,
        "memory": {},
    }
def goal_value(history):
    return 0.0
"""


def _observation() -> Observation:
    return Observation(
        np.zeros((4, 4), dtype=np.int8),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        1,
        3,
    )


def test_build_agent_wires_generation_pool_planner_and_controller() -> None:
    backend = ScriptedBackend([PROGRAM_A, PROGRAM_B])
    config = SystemConfig(sandbox=SandboxConfig(timeout_ms=1_000))
    with build_agent(backend, config) as agent:
        decision = agent.controller.act(_observation(), Budget(max_wall_seconds=10))
        assert decision.action.kind in {ActionKind.ACTION1, ActionKind.ACTION2}
        assert agent.controller.pool is not None
        assert len(agent.controller.pool.weighted_hypotheses) == 2
    assert backend.closed


def test_direct_variant_uses_same_backend_without_program_generation() -> None:
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION2"})
    config = SystemConfig(experiment=ExperimentConfig(variant="D"))
    with build_agent(backend, config) as agent:
        decision = agent.controller.act(_observation(), Budget(max_wall_seconds=10))
        assert decision.action.kind is ActionKind.ACTION2
        assert agent.controller.pool is None


def test_live_grounding_rejects_ineligible_smaller_duplicate_before_dedup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        validate_program(CONSERVATIVE_SMALL).node_count
        < validate_program(CONSERVATIVE_LARGE).node_count
    )
    sources_reaching_dedup: list[str] = []

    def capture_deduplicate(
        hypotheses: Sequence[Hypothesis], *args: Any, **kwargs: Any
    ) -> tuple[Hypothesis, ...]:
        sources_reaching_dedup.extend(
            cast(ExecutableHypothesis, hypothesis).source for hypothesis in hypotheses
        )
        return behavioral_deduplicate(hypotheses, *args, **kwargs)

    monkeypatch.setattr("arc3_voi.agent.behavioral_deduplicate", capture_deduplicate)
    backend = ScriptedBackend(
        [
            CONSERVATIVE_LARGE,
            SENSITIVE_FIRST_CELL,
            SENSITIVE_SECOND_CELL,
            CONSERVATIVE_SMALL,
        ]
    )
    config = SystemConfig(sandbox=SandboxConfig(timeout_ms=1_000))

    with build_agent(backend, config) as agent:
        decision = agent.controller.act(_observation(), Budget(max_wall_seconds=30))
        assert agent.controller.pool is not None
        selected_entries = agent.controller.pool.entries
        selected_sources = {
            cast(ExecutableHypothesis, entry.hypothesis).source for entry in selected_entries
        }
        selected_ids = [entry.hypothesis_id for entry in selected_entries]

        assert CONSERVATIVE_LARGE in selected_sources
        assert CONSERVATIVE_SMALL not in selected_sources
        assert CONSERVATIVE_SMALL not in sources_reaching_dedup
        assert set(sources_reaching_dedup) == {
            CONSERVATIVE_LARGE,
            SENSITIVE_FIRST_CELL,
            SENSITIVE_SECOND_CELL,
        }
        assert decision.diagnostics["grounding_eligible_programs"] == 3
        assert decision.diagnostics["grounding_rejected_programs"] == 1
        assert decision.diagnostics["invalid_programs"] == 1
        assert (
            json.loads(str(decision.diagnostics["grounding_selected_hypothesis_ids"]))
            == selected_ids
        )


def test_single_program_variant_allows_total_conservative_index_zero() -> None:
    backend = ScriptedBackend([PROGRAM_A])
    config = SystemConfig(
        experiment=ExperimentConfig(variant="S"),
        sandbox=SandboxConfig(timeout_ms=1_000),
    )

    with build_agent(backend, config) as agent:
        decision = agent.controller.act(_observation(), Budget(max_wall_seconds=30))
        assert agent.controller.pool is not None
        assert len(agent.controller.pool.entries) == 1
        selected_id = agent.controller.pool.entries[0].hypothesis_id
        assert decision.diagnostics["grounding_eligible_programs"] == 1
        assert decision.diagnostics["grounding_rejected_programs"] == 0
        assert json.loads(str(decision.diagnostics["grounding_selected_hypothesis_ids"])) == [
            selected_id
        ]
