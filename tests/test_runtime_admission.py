from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.config import (
    PATH_DEFICIT_RUNTIME_VERSION,
    ExperimentConfig,
    PlanningConfig,
    SystemConfig,
)
from arc3_voi.planner import (
    COMPLETION_COST_POLICY_HASHES,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
)
from arc3_voi.runtime_admission import (
    EvaluatedSource,
    _completion_cost_policy_metadata,
    _grounding_schema_version,
    admission_gate_reasons,
    construct_eligible_hypotheses,
    evaluate_source_programs,
    role_requirements,
    x_only_probe_actions,
)
from arc3_voi.types import Action, ActionKind, GameState, History, Observation, Prediction


@dataclass
class _FakeHypothesis:
    source: str
    timeout_seconds: float
    memory_limit_mb: int
    closed: bool = False

    def __post_init__(self) -> None:
        self.hypothesis_id = hashlib.sha256(self.source.encode()).hexdigest()
        self.ast_nodes = len(self.source)

    def predict(self, history: History, action: Action) -> Prediction:
        del action
        value = 1 if self.source == "eligible" else 2
        return Prediction(np.full_like(history.latest_grid, value), GameState.NOT_FINISHED, 0)

    def goal_value(self, history: History) -> float:
        del history
        return 0.0

    def close(self) -> None:
        self.closed = True


def test_role_requirements_reserve_only_candidate_zero_as_conservative() -> None:
    assert role_requirements(0) == (False, False)
    assert role_requirements(1) == (True, True)
    assert role_requirements(3) == (True, True)


def test_runtime_admission_accepts_historical_v4_and_multibatch_v5_schemas() -> None:
    assert _grounding_schema_version({"schema_version": 4}) == 4
    assert _grounding_schema_version({"schema_version": 5}) == 5
    with pytest.raises(ValueError, match="schema-v4 or schema-v5"):
        _grounding_schema_version({"schema_version": 6})


def test_endpoint_admission_omits_policy_identity_but_runtime_v4_emits_it() -> None:
    assert _completion_cost_policy_metadata(SystemConfig()) == {}
    path = PlanningConfig(
        completion_cost_policy_version=PATH_DEFICIT_COMPLETION_COST_POLICY,
        completion_cost_policy_sha256=COMPLETION_COST_POLICY_HASHES[
            PATH_DEFICIT_COMPLETION_COST_POLICY
        ],
    )
    config = SystemConfig(
        experiment=ExperimentConfig(
            implementation_contract_version=PATH_DEFICIT_RUNTIME_VERSION
        ),
        planning=path,
    )

    assert _completion_cost_policy_metadata(config) == {
        "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
        "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
            PATH_DEFICIT_COMPLETION_COST_POLICY
        ],
    }


def test_schema_v5_batch_local_role_index_resets_candidate_zero() -> None:
    source = """
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
    digest = hashlib.sha256(source.encode()).hexdigest()
    rows = (
        {
            "candidate_index": 0,
            "batch_index": 0,
            "batch_candidate_index": 0,
            "assigned_role": "conservative",
            "source": source,
            "source_sha256": digest,
        },
        {
            "candidate_index": 1,
            "batch_index": 1,
            "batch_candidate_index": 0,
            "assigned_role": "conservative repair",
            "source": source,
            "source_sha256": digest,
        },
    )
    history = History.from_observation(
        Observation(
            np.zeros((2, 2), dtype=np.int16),
            frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=2,
        )
    )

    evaluated = evaluate_source_programs(
        rows,
        history,
        (Action(ActionKind.ACTION1), Action(ActionKind.ACTION2)),
        timeout_seconds=1.0,
        memory_limit_mb=256,
        rollout_depth=2,
    )

    assert [item.result.action_sensitivity_required for item in evaluated] == [
        False,
        False,
    ]
    assert all(item.result.eligible for item in evaluated)


@pytest.mark.parametrize(
    "rows",
    [
        (
            {"candidate_index": 0, "batch_index": 0, "batch_candidate_index": 0},
            {"candidate_index": 1},
        ),
        ({"candidate_index": 0, "batch_index": 0},),
    ],
)
def test_schema_v5_rejects_mixed_or_incomplete_batch_metadata(rows: tuple[dict, ...]) -> None:
    history = History.from_observation(
        Observation(
            np.zeros((2, 2), dtype=np.int16),
            frozenset({ActionKind.ACTION1}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=2,
        )
    )

    with pytest.raises(ValueError, match="batch"):
        evaluate_source_programs(
            rows,
            history,
            (Action(ActionKind.ACTION1),),
            timeout_seconds=1.0,
            memory_limit_mb=256,
            rollout_depth=2,
        )


def test_ineligible_source_is_filtered_before_persistent_worker_construction() -> None:
    history = History.from_observation(
        Observation(
            np.zeros((2, 2), dtype=np.int16),
            frozenset({ActionKind.ACTION1}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=2,
        )
    )
    calls: list[str] = []

    def factory(source: str, **kwargs: object) -> _FakeHypothesis:
        calls.append(source)
        return _FakeHypothesis(
            source,
            float(kwargs["timeout_seconds"]),
            int(kwargs["memory_limit_mb"]),
        )

    eligible = SimpleNamespace(
        eligible=True,
        source_sha256=hashlib.sha256(b"eligible").hexdigest(),
    )
    rejected = SimpleNamespace(
        eligible=False,
        source_sha256=hashlib.sha256(b"rejected").hexdigest(),
    )
    selected, removed = construct_eligible_hypotheses(
        (
            EvaluatedSource(
                0,
                "baseline",
                "eligible",
                hashlib.sha256(b"eligible").hexdigest(),
                eligible,  # type: ignore[arg-type]
            ),
            EvaluatedSource(
                1,
                "graded",
                "rejected",
                hashlib.sha256(b"rejected").hexdigest(),
                rejected,  # type: ignore[arg-type]
            ),
        ),
        history,
        (Action(ActionKind.ACTION1),),
        timeout_seconds=0.1,
        memory_limit_mb=256,
        max_hypotheses=4,
        hypothesis_factory=factory,  # type: ignore[arg-type]
    )
    try:
        assert calls == ["eligible"]
        assert len(selected) == 1
        assert removed == ()
    finally:
        for hypothesis in selected:
            hypothesis.close()


def test_admission_gate_fails_closed_without_material_decision_diversity() -> None:
    reasons = admission_gate_reasons(
        selected_ids=("a", "b"),
        eligible_ids=("a", "b"),
        distinct_selected_behaviors=2,
        planner_invalid_ids=(),
        x_only_probe_actions=(),
    )

    assert reasons == (
        "no X-only probe opportunity: require one action with low committee agreement, "
        "material EVSI, positive cross-level utility, and non-positive myopic utility",
    )


def test_admission_gate_accepts_an_x_only_probe_opportunity() -> None:
    assert not admission_gate_reasons(
        selected_ids=("a", "b"),
        eligible_ids=("a", "b"),
        distinct_selected_behaviors=2,
        planner_invalid_ids=(),
        x_only_probe_actions=("ACTION6(1,2)",),
    )


def test_x_only_probe_requires_every_controller_condition_on_the_same_action() -> None:
    rows = (
        {
            "action": "ACTION6(1,2)",
            "evsi": 0.05,
            "myopic_utility": -0.95,
            "cross_level_utility": 0.15,
        },
        {
            "action": "ACTION6(2,3)",
            "evsi": 0.049,
            "myopic_utility": -0.951,
            "cross_level_utility": 0.127,
        },
        {
            "action": "ACTION6(3,4)",
            "evsi": 0.1,
            "myopic_utility": 0.1,
            "cross_level_utility": 1.3,
        },
    )

    assert x_only_probe_actions(
        rows,
        agreement=0.79,
        agreement_threshold=0.8,
    ) == ("ACTION6(1,2)",)
    assert not x_only_probe_actions(
        rows,
        agreement=0.8,
        agreement_threshold=0.8,
    )


def test_admission_gate_reports_grounding_selection_and_planner_failures() -> None:
    reasons = admission_gate_reasons(
        selected_ids=("a", "bad"),
        eligible_ids=("a",),
        distinct_selected_behaviors=1,
        planner_invalid_ids=("bad",),
        x_only_probe_actions=("ACTION6(1,2)",),
    )

    assert "one or more selected programs failed role-specific grounding" in reasons
    assert "fewer than two distinct selected behavior classes" in reasons
    assert "one or more selected programs became invalid during depth-four planning" in reasons
