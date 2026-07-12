from __future__ import annotations

import numpy as np

from arc3_voi.agent import build_agent
from arc3_voi.config import ExperimentConfig, SandboxConfig, SystemConfig
from arc3_voi.model import ScriptedBackend
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
    return 0.2
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
