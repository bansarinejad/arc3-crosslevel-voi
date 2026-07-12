from __future__ import annotations

import numpy as np
import pytest

import arc3_voi.runner as runner_module
from arc3_voi.controller import Controller, ControllerConfig, Variant
from arc3_voi.hypothesis import HypothesisPool
from arc3_voi.runner import run_game
from arc3_voi.types import (
    Action,
    ActionKind,
    Decision,
    DecisionMode,
    GameState,
    History,
    Observation,
    Prediction,
)


class FakeSession:
    game_id = "fake"

    def __init__(self) -> None:
        self.level = 1

    def initial_observation(self) -> Observation:
        return self._observation(GameState.NOT_FINISHED)

    def step(self, action: Action, *, reasoning: object = None) -> Observation:
        del action, reasoning
        if self.level == 1:
            self.level = 2
            return self._observation(GameState.NOT_FINISHED)
        return self._observation(GameState.WIN)

    def _observation(self, state: GameState) -> Observation:
        return Observation(
            np.zeros((4, 4), dtype=np.int8),
            frozenset({ActionKind.ACTION1}),
            state,
            self.level,
            2,
        )


class FakeController:
    pool = None

    def act(self, observation: Observation, budget: object) -> Decision:
        del observation, budget
        return Decision(
            Action(ActionKind.ACTION1),
            DecisionMode.EXPLOIT,
            0,
            {"generated_tokens": 2},
        )


class TelemetryController(FakeController):
    def __init__(self) -> None:
        self.calls = 0

    def act(self, observation: Observation, budget: object) -> Decision:
        del observation, budget
        self.calls += 5
        return Decision(
            Action(ActionKind.ACTION1),
            DecisionMode.EXPLOIT,
            0,
            {
                "generated_tokens": 0,
                "invalid_programs": 1,
                "peak_vram_gb": 2.5,
                "program_prediction_calls": self.calls,
                "program_goal_calls": self.calls + 1,
                "program_timeouts": 1,
                "program_execution_errors": 2,
                "timeout_instrumentation_complete": True,
            },
        )


def test_runner_records_levels_actions_tokens_and_rhae() -> None:
    result = run_game(
        FakeSession(),
        FakeController(),
        run_id="r",
        seed=1,
        variant="X",
        model_profile="test",
        config_hash="h",
        baseline_actions=(2, 2),
    )
    assert result.error is None
    assert result.termination_reason == "win"
    assert result.levels_completed == 2
    assert result.per_level_actions == [1, 1]
    assert result.generated_tokens == 4
    assert result.rhae == 1.0
    assert result.steps[-1].observed_state == "WIN"
    assert result.steps[-1].history[-1]["level"] == 2


def test_runner_separates_controller_and_environment_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Clock:
        now = 0.0

        def perf_counter(self) -> float:
            return self.now

    clock = Clock()

    class TimedController(FakeController):
        def act(self, observation: Observation, budget: object) -> Decision:
            clock.now += 0.25
            return super().act(observation, budget)

    class TimedSession(FakeSession):
        def step(self, action: Action, *, reasoning: object = None) -> Observation:
            clock.now += 0.5
            return super().step(action, reasoning=reasoning)

    monkeypatch.setattr(runner_module, "time", clock)
    result = run_game(
        TimedSession(),
        TimedController(),
        run_id="latency",
        seed=1,
        variant="D",
        model_profile="test",
        config_hash="h",
    )

    assert result.controller_decision_seconds == pytest.approx(0.5)
    assert result.environment_step_seconds == pytest.approx(1.0)
    assert result.wall_seconds == pytest.approx(1.5)
    assert [step.controller_decision_seconds for step in result.steps] == [0.25, 0.25]
    assert [step.environment_step_seconds for step in result.steps] == [0.5, 0.5]
    assert all(
        step.elapsed_seconds == step.environment_step_seconds for step in result.steps
    )


class PerfectHypothesis:
    hypothesis_id = "perfect"
    ast_nodes = 1

    def predict(self, history: History, action: Action) -> Prediction:
        del action
        final = history.current_level == 2
        return Prediction(
            np.zeros_like(history.latest_grid),
            GameState.WIN if final else GameState.NOT_FINISHED,
            0 if final else 1,
        )

    def goal_value(self, history: History) -> float:
        return float(history.current_level == 2)


def test_runner_ingests_and_scores_the_final_win_transition() -> None:
    hypothesis = PerfectHypothesis()
    pool = HypothesisPool.from_hypotheses(
        (hypothesis,), max_hypotheses=1, effective_pool_refresh_threshold=1.0
    )
    controller = Controller(
        direct_policy=lambda _history, candidates, _budget: candidates[0],
        pool=pool,
        config=ControllerConfig(variant=Variant.SINGLE),
    )
    result = run_game(
        FakeSession(),
        controller,
        run_id="scored-final",
        seed=1,
        variant="S",
        model_profile="test",
        config_hash="h",
    )
    assert result.error is None
    assert result.steps[-1].weighted_transition_loss == 0.0
    assert result.steps[-1].best_hypothesis_transition_loss == 0.0
    assert controller.pool is not None
    assert controller.pool.entries[0].cumulative_loss == 0.0


def test_runner_merges_delta_and_cumulative_controller_telemetry_once() -> None:
    result = run_game(
        FakeSession(),
        TelemetryController(),
        run_id="telemetry",
        seed=1,
        variant="X",
        model_profile="test",
        config_hash="h",
    )
    assert result.invalid_programs == 2
    assert result.program_prediction_calls == 10
    assert result.program_goal_calls == 11
    assert result.program_timeouts == 1
    assert result.program_execution_errors == 2
    assert result.timeout_instrumentation_complete
    assert result.peak_vram_gb is not None and result.peak_vram_gb >= 2.5
