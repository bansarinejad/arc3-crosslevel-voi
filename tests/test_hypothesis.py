from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from arc3_voi.hypothesis import (
    CrossLevelPersistence,
    HypothesisPool,
    RecordedTransition,
    behavioral_deduplicate,
    prequential_loss,
    replay_cumulative_loss,
)
from arc3_voi.types import Action, ActionKind, GameState, History, Observation, Prediction


@dataclass
class FixedHypothesis:
    hypothesis_id: str
    ast_nodes: int
    value: int = 0
    predicted_state: GameState = GameState.NOT_FINISHED
    predicted_delta: int = 0
    fail: bool = False

    def predict(self, history: History, action: Action) -> Prediction:
        del action
        if self.fail:
            raise RuntimeError("generated program failed")
        return Prediction(
            np.full(history.latest_grid.shape, self.value, dtype=np.int16),
            self.predicted_state,
            self.predicted_delta,
        )

    def goal_value(self, history: History) -> float:
        del history
        return 0.5


def history() -> History:
    item = Observation(
        np.zeros((64, 64), dtype=np.int8),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=3,
    )
    return History.from_observation(item)


def test_prequential_loss_uses_fixed_4096_denominator_and_two_half_penalties() -> None:
    predicted = np.zeros((64, 64), dtype=np.int8)
    actual = predicted.copy()
    actual[3, 7] = 1
    prediction = Prediction(predicted, GameState.NOT_FINISHED, level_delta=0)

    loss = prequential_loss(prediction, actual, GameState.WIN, actual_level_delta=1)

    assert loss == pytest.approx((1 / 4096) + 0.5 + 0.5)


def test_new_hypothesis_is_replay_scored_on_recorded_evidence() -> None:
    item = RecordedTransition(
        history(),
        Action(ActionKind.ACTION1),
        np.ones((64, 64), dtype=np.int8),
        GameState.NOT_FINISHED,
        0,
    )

    cumulative, latest = replay_cumulative_loss(
        FixedHypothesis("zero", 1, value=0), (item,)
    )

    assert cumulative == pytest.approx(1.0)
    assert latest == pytest.approx(1.0)


def test_shape_mismatch_is_a_full_grid_loss() -> None:
    prediction = Prediction(np.zeros((2, 2), dtype=np.int8), GameState.WIN, level_delta=1)
    assert prequential_loss(
        prediction,
        np.zeros((3, 3), dtype=np.int8),
        GameState.WIN,
        1,
    ) == 1.0


def test_mdl_gibbs_weights_are_normalized_stably_and_prefer_simple_programs() -> None:
    pool = HypothesisPool.from_hypotheses(
        [FixedHypothesis("small", 10), FixedHypothesis("large", 1000)],
        eta=10.0,
        complexity_lambda=1.0,
        effective_pool_refresh_threshold=0.5,
    )

    assert sum(pool.weights) == pytest.approx(1.0)
    assert pool.weights[0] > 0.999
    assert pool.weights[1] >= 0.0
    assert pool.hypotheses[0].hypothesis_id == "small"


def test_update_uses_pre_action_weights_and_invalid_predictions_get_zero_weight() -> None:
    pool = HypothesisPool.from_hypotheses(
        [FixedHypothesis("good", 10), FixedHypothesis("failed", 10, fail=True)],
        effective_pool_refresh_threshold=0.5,
    )
    predictions = pool.weighted_predictions(history(), Action(ActionKind.ACTION1))
    updated = pool.update(
        predictions,
        np.zeros((64, 64), dtype=np.int8),
        GameState.NOT_FINISHED,
        0,
    )

    assert updated.entries[0].valid
    assert not updated.entries[1].valid
    assert updated.entries[1].invalid_reason == "prediction_failed"
    assert updated.weights == pytest.approx((1.0, 0.0))
    assert updated.effective_sample_size == pytest.approx(1.0)


def test_refresh_conditions_cover_low_ess_all_invalid_and_consecutive_high_losses() -> None:
    hypotheses = [FixedHypothesis(str(index), 10) for index in range(4)]
    pool = HypothesisPool.from_hypotheses(hypotheses)
    assert pool.effective_sample_size == pytest.approx(4.0)
    assert not pool.needs_refresh

    bad_predictions = {
        item.hypothesis_id: Prediction(
            np.zeros((64, 64), dtype=np.int8),
            GameState.GAME_OVER,
            level_delta=-1,
        )
        for item in hypotheses
    }
    once = pool.update(
        bad_predictions,
        np.zeros((64, 64), dtype=np.int8),
        GameState.NOT_FINISHED,
        0,
    )
    twice = once.update(
        bad_predictions,
        np.zeros((64, 64), dtype=np.int8),
        GameState.NOT_FINISHED,
        0,
    )
    assert not once.needs_refresh
    assert twice.recent_weighted_losses == pytest.approx((1.0, 1.0))
    assert twice.needs_refresh

    failed_pool = HypothesisPool.from_hypotheses(
        [FixedHypothesis("broken", 1, fail=True)],
        effective_pool_refresh_threshold=0.5,
    )
    failed = failed_pool.update(
        failed_pool.weighted_predictions(history(), Action(ActionKind.ACTION1)),
        np.zeros((64, 64), dtype=np.int8),
        GameState.NOT_FINISHED,
        0,
    )
    assert failed.all_invalid
    assert failed.needs_refresh


def test_behavioral_dedupe_keeps_smaller_ast_and_skips_failed_programs() -> None:
    large = FixedHypothesis("large", ast_nodes=50, value=3)
    small = FixedHypothesis("small", ast_nodes=12, value=3)
    distinct = FixedHypothesis("distinct", ast_nodes=20, value=7)
    broken = FixedHypothesis("broken", ast_nodes=1, value=9, fail=True)

    selected = behavioral_deduplicate(
        [large, small, distinct, broken],
        history(),
        [Action(ActionKind.ACTION1), Action(ActionKind.ACTION2)],
    )

    assert {item.hypothesis_id for item in selected} == {"small", "distinct"}


def test_behavioral_dedupe_includes_recorded_transition_queries() -> None:
    class RecordedOnlyDifference(FixedHypothesis):
        def predict(self, history: History, action: Action) -> Prediction:
            del action
            value = 1 if len(history.frames) == 1 else 0
            return Prediction(
                np.full(history.latest_grid.shape, value, dtype=np.int16),
                GameState.NOT_FINISHED,
                0,
            )

    initial = history()
    next_observation = Observation(
        np.ones((64, 64), dtype=np.int8),
        frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=3,
    )
    recorded = initial.append(next_observation, Action(ActionKind.ACTION1), 0)
    always_zero = FixedHypothesis("always-zero", 5, value=0)
    differs_only_on_recorded = RecordedOnlyDifference("recorded", 5)

    selected = behavioral_deduplicate(
        (always_zero, differs_only_on_recorded),
        recorded,
        (Action(ActionKind.ACTION2),),
    )

    assert {item.hypothesis_id for item in selected} == {"always-zero", "recorded"}


def test_cross_level_persistence_matches_beta_bernoulli_plan_and_multiplier() -> None:
    persistence = CrossLevelPersistence()
    assert persistence.estimate == 0.5
    assert persistence.multiplier(level=3, win_levels=3) == 1.0
    assert persistence.multiplier(level=1, win_levels=3) == pytest.approx(3.5)

    persistence = persistence.observe_boundary(0.1).observe_boundary(0.4)
    assert persistence.successes == 1
    assert persistence.trials == 2
    assert persistence.estimate == 0.5


def test_pool_invalidation_is_persistent_and_zero_weighted() -> None:
    pool = HypothesisPool.from_hypotheses(
        (FixedHypothesis("a", 1, 0), FixedHypothesis("b", 1, 1))
    )

    invalidated = pool.invalidate(("b",), reason="root_prediction_failed")

    assert invalidated.weights == pytest.approx((1.0, 0.0))
    assert invalidated.entries[1].invalid_reason == "root_prediction_failed"


def test_pool_rejects_duplicate_identifiers() -> None:
    with pytest.raises(ValueError, match="unique"):
        HypothesisPool.from_hypotheses(
            [FixedHypothesis("same", 1), FixedHypothesis("same", 2)]
        )
