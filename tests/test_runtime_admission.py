from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from arc3_voi.runtime_admission import (
    EvaluatedSource,
    admission_gate_reasons,
    construct_eligible_hypotheses,
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
