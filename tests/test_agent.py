from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest

from arc3_voi.agent import (
    HypothesisSourceNotAdmittedError,
    TreatmentNotAdmittedError,
    build_agent,
    qwen_producer_contract_sha256,
    require_live_execution_admitted,
)
from arc3_voi.config import ExperimentConfig, SandboxConfig, SystemConfig, load_config
from arc3_voi.hypothesis import Hypothesis, behavioral_deduplicate
from arc3_voi.model import GenerationResult, ScriptedBackend
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

INVALID_IMPORT = """
import socket
def predict(history, action):
    return {}
def goal_value(history):
    return 0.0
"""


class _QueuedScriptedBackend(ScriptedBackend):
    def __init__(self, batches: Sequence[GenerationResult]) -> None:
        super().__init__()
        self.batches = list(batches)
        self.generation_calls: list[dict[str, Any]] = []

    def generate_programs(
        self,
        history: Any,
        count: int,
        *,
        feedback: str | None = None,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult:
        del history
        self.generation_calls.append(
            {
                "count": count,
                "feedback": feedback,
                "max_new_tokens": max_new_tokens,
                "max_wall_seconds": max_wall_seconds,
            }
        )
        return self.batches.pop(0)


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


def test_build_agent_rejects_registration_only_source_before_backend_use() -> None:
    backend = ScriptedBackend([PROGRAM_A])
    config = SystemConfig(
        experiment=ExperimentConfig(variant="X", hypothesis_source="template_v1")
    )

    with pytest.raises(
        HypothesisSourceNotAdmittedError,
        match="registration-only; live producer wiring",
    ):
        build_agent(backend, config)

    assert not backend.closed


@pytest.mark.parametrize(
    "runtime_version",
    ["crosslevel-voi-runtime-v5", "unregistered-runtime"],
)
@pytest.mark.parametrize(
    "hypothesis_source",
    ["qwen", "template_v1", "qwen_then_template_v1"],
)
def test_live_guard_rejects_unknown_runtime_before_source(
    runtime_version: str,
    hypothesis_source: str,
) -> None:
    config = SystemConfig(
        experiment=ExperimentConfig(
            variant="X",
            hypothesis_source=cast(Any, hypothesis_source),
            implementation_contract_version=runtime_version,
        )
    )

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        require_live_execution_admitted(config)


@pytest.mark.parametrize(
    "hypothesis_source",
    ["qwen", "template_v1", "qwen_then_template_v1"],
)
def test_live_guard_preserves_permanent_v4_failure_before_source(
    hypothesis_source: str,
) -> None:
    template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    config = replace(
        template,
        experiment=replace(
            template.experiment,
            hypothesis_source=cast(Any, hypothesis_source),
        ),
    )

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        require_live_execution_admitted(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completion_cost_policy_version", "path-deficit-v2"),
        ("completion_cost_policy_sha256", "0" * 64),
    ],
)
def test_live_guard_rejects_completion_policy_identity_drift(
    field: str,
    value: str,
) -> None:
    config = SystemConfig(
        experiment=ExperimentConfig(variant="X", hypothesis_source="template_v1")
    )
    object.__setattr__(config.planning, field, value)

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not the admitted endpoint-v1 contract",
    ):
        require_live_execution_admitted(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("probe_disagreement_policy_version", "unregistered-policy"),
        ("probe_disagreement_policy_sha256", "0" * 64),
    ],
)
def test_live_guard_rejects_probe_policy_identity_drift_before_source(
    field: str,
    value: str,
) -> None:
    config = SystemConfig(
        experiment=ExperimentConfig(variant="X", hypothesis_source="template_v1")
    )
    object.__setattr__(config.planning, field, value)

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not the admitted winning-action-agreement-v1 contract",
    ):
        require_live_execution_admitted(config)


def test_qwen_producer_contract_is_controller_and_seed_independent() -> None:
    first = SystemConfig(experiment=ExperimentConfig(variant="M", seed=11))
    second = SystemConfig(experiment=ExperimentConfig(variant="X", seed=23))

    assert qwen_producer_contract_sha256(first) == qwen_producer_contract_sha256(second)
    assert len(qwen_producer_contract_sha256(first)) == 64


def test_qwen_producer_identity_is_neutral_to_path_deficit_planning() -> None:
    endpoint = load_config("configs/local_4b.yaml")
    path_template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    path_qwen = replace(
        path_template,
        experiment=replace(path_template.experiment, hypothesis_source="qwen"),
    )

    assert qwen_producer_contract_sha256(path_qwen) == qwen_producer_contract_sha256(
        endpoint
    )

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        require_live_execution_admitted(path_qwen)


def test_build_agent_rejects_failed_treatment_before_backend_use() -> None:
    template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    config = replace(
        template,
        experiment=replace(template.experiment, hypothesis_source="qwen"),
    )
    backend = ScriptedBackend([PROGRAM_A])

    with pytest.raises(TreatmentNotAdmittedError, match="under any hypothesis source"):
        build_agent(backend, config)

    assert not backend.closed


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


def test_runtime_repair_preserves_all_batch_sources_tokens_and_attempt_count() -> None:
    initial_sources = (INVALID_IMPORT,) * 4
    repair_sources = (
        CONSERVATIVE_LARGE,
        SENSITIVE_FIRST_CELL,
        SENSITIVE_SECOND_CELL,
        INVALID_IMPORT,
    )
    backend = _QueuedScriptedBackend(
        (
            GenerationResult(initial_sources, 6, 0.01),
            GenerationResult(repair_sources, 8, 0.01),
        )
    )
    config = SystemConfig(sandbox=SandboxConfig(timeout_ms=1_000))

    with build_agent(backend, config) as agent:
        decision = agent.controller.act(
            _observation(), Budget(max_generated_tokens=100, max_wall_seconds=30)
        )

        assert len(backend.generation_calls) == 2
        feedback = backend.generation_calls[1]["feedback"]
        assert isinstance(feedback, str)
        assert "import socket" not in feedback
        assert decision.diagnostics["generated_tokens"] == 14
        assert decision.diagnostics["generation_batches_used"] == 2
        assert json.loads(str(decision.diagnostics["generation_batch_output_tokens"])) == [6, 8]
        assert json.loads(str(decision.diagnostics["generated_program_batches"])) == [
            list(initial_sources),
            list(repair_sources),
        ]
        assert decision.diagnostics["grounding_repair_attempts"] == 1
        assert decision.diagnostics["grounding_repair_feedback"] == feedback
        assert decision.diagnostics["grounding_eligible_programs"] == 3
        assert decision.diagnostics["grounding_rejected_programs"] == 5
        assert agent.controller.generation_batches_used == 2
