from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from arc3_voi.runtime_admission import (
    MATERIAL_EVSI_THRESHOLD,
    EvaluatedSource,
    admission_gate_reasons,
    construct_eligible_hypotheses,
    role_requirements,
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
        return Prediction(
            np.full_like(history.latest_grid, value), GameState.NOT_FINISHED, 0
        )

    def goal_value(self, history: History) -> float:
        del history
        return 0.0

    def close(self) -> None:
        self.closed = True


def test_role_requirements_reserve_only_candidate_zero_as_conservative() -> None:
    assert role_requirements(0) == (False, False)
    assert role_requirements(1) == (True, True)
    assert role_requirements(3) == (True, True)


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
        agreement=1.0,
        differing_optimal_sets=False,
        maximum_evsi=MATERIAL_EVSI_THRESHOLD - 1e-6,
        maximum_cross_level_utility=1.0,
        agreement_threshold=0.8,
    )

    assert reasons == (
        "no material decision diversity: require low agreement with positive "
        "cross-level utility, or differing optimal sets with material EVSI",
    )


def test_admission_gate_accepts_differing_optima_with_material_evsi() -> None:
    assert not admission_gate_reasons(
        selected_ids=("a", "b"),
        eligible_ids=("a", "b"),
        distinct_selected_behaviors=2,
        planner_invalid_ids=(),
        agreement=1.0,
        differing_optimal_sets=True,
        maximum_evsi=MATERIAL_EVSI_THRESHOLD,
        maximum_cross_level_utility=-0.5,
        agreement_threshold=0.8,
    )


def test_admission_gate_reports_grounding_selection_and_planner_failures() -> None:
    reasons = admission_gate_reasons(
        selected_ids=("a", "bad"),
        eligible_ids=("a",),
        distinct_selected_behaviors=1,
        planner_invalid_ids=("bad",),
        agreement=0.5,
        differing_optimal_sets=True,
        maximum_evsi=1.0,
        maximum_cross_level_utility=1.0,
        agreement_threshold=0.8,
    )

    assert "one or more selected programs failed role-specific grounding" in reasons
    assert "fewer than two distinct selected behavior classes" in reasons
    assert "one or more selected programs became invalid during depth-four planning" in reasons
