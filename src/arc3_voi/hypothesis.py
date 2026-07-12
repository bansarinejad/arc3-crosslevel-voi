"""Executable-hypothesis protocols and weighted version-space mechanics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from math import exp, inf, isfinite
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from arc3_voi.types import Action, GameState, History, Prediction, freeze_grid

GRID_LOSS_DENOMINATOR = 4096.0
MAX_PREQUENTIAL_LOSS = 2.0


@runtime_checkable
class Hypothesis(Protocol):
    """The stable interface implemented by executable transition-and-goal programs."""

    hypothesis_id: str
    ast_nodes: int

    def predict(self, history: History, action: Action) -> Prediction:
        """Predict the next stable observation before the real action is taken."""

    def goal_value(self, history: History) -> float:
        """Return a bounded estimate of progress toward the current level goal."""


@dataclass(frozen=True, slots=True)
class RecordedTransition:
    """One revealed transition paired with its exact pre-action bounded history."""

    history: History
    action: Action
    actual_grid: npt.ArrayLike
    actual_game_state: GameState
    actual_level_delta: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actual_grid", freeze_grid(self.actual_grid))
        object.__setattr__(
            self, "actual_game_state", GameState.coerce(self.actual_game_state)
        )
        if isinstance(self.actual_level_delta, bool) or not isinstance(
            self.actual_level_delta, int
        ):
            raise TypeError("actual_level_delta must be an integer")


def prequential_loss(
    prediction: Prediction,
    actual_grid: npt.ArrayLike,
    actual_game_state: GameState | str,
    actual_level_delta: int,
) -> float:
    """Compute the plan's exact prequential next-transition loss.

    A shape mismatch is a full-canvas error.  Otherwise the grid term is the
    number of unequal cells divided by 4096, even for synthetic smaller grids.
    """

    if isinstance(actual_level_delta, bool) or not isinstance(actual_level_delta, int):
        raise TypeError("actual_level_delta must be an integer")
    actual = freeze_grid(actual_grid)
    actual_state = GameState.coerce(actual_game_state)
    if prediction.next_grid.shape != actual.shape:
        grid_loss = 1.0
    else:
        grid_loss = float(np.count_nonzero(prediction.next_grid != actual)) / GRID_LOSS_DENOMINATOR
    state_loss = 0.5 if prediction.game_state is not actual_state else 0.0
    level_loss = 0.5 if prediction.level_delta != actual_level_delta else 0.0
    return grid_loss + state_loss + level_loss


def replay_cumulative_loss(
    hypothesis: Hypothesis, transitions: Sequence[RecordedTransition]
) -> tuple[float, float | None]:
    """Score a newly proposed program on every transition already revealed."""

    losses = [
        prequential_loss(
            hypothesis.predict(item.history, item.action),
            item.actual_grid,
            item.actual_game_state,
            item.actual_level_delta,
        )
        for item in transitions
    ]
    return sum(losses), (losses[-1] if losses else None)


@dataclass(frozen=True, slots=True)
class WeightedHypothesis:
    """A hypothesis together with data-dependent version-space state."""

    hypothesis: Hypothesis
    cumulative_loss: float = 0.0
    valid: bool = True
    latest_loss: float | None = None
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.hypothesis.hypothesis_id.strip():
            raise ValueError("hypothesis_id cannot be empty")
        if (
            isinstance(self.hypothesis.ast_nodes, bool)
            or not isinstance(self.hypothesis.ast_nodes, int)
            or self.hypothesis.ast_nodes < 0
        ):
            raise ValueError("ast_nodes must be a non-negative integer")
        if not isfinite(self.cumulative_loss) or self.cumulative_loss < 0:
            raise ValueError("cumulative_loss must be finite and non-negative")
        if self.latest_loss is not None and (
            not isfinite(self.latest_loss) or self.latest_loss < 0
        ):
            raise ValueError("latest_loss must be finite and non-negative")
        if self.valid and self.invalid_reason is not None:
            raise ValueError("a valid hypothesis cannot have an invalid_reason")

    @property
    def hypothesis_id(self) -> str:
        return self.hypothesis.hypothesis_id

    @property
    def ast_nodes(self) -> int:
        return self.hypothesis.ast_nodes


def _stable_softmax(log_weights: Sequence[float]) -> tuple[float, ...]:
    if not log_weights:
        return ()
    maximum = max(log_weights)
    if maximum == -inf:
        return tuple(0.0 for _ in log_weights)
    exponentials = [0.0 if value == -inf else exp(value - maximum) for value in log_weights]
    total = sum(exponentials)
    if not isfinite(total) or total <= 0:
        return tuple(0.0 for _ in log_weights)
    return tuple(value / total for value in exponentials)


@dataclass(frozen=True, slots=True)
class HypothesisPool:
    """A bounded MDL-regularized Gibbs-weighted executable version space."""

    entries: tuple[WeightedHypothesis, ...]
    eta: float = 5.0
    complexity_lambda: float = 0.002
    max_hypotheses: int = 4
    effective_pool_refresh_threshold: float = 1.5
    loss_refresh_threshold: float = 0.25
    consecutive_loss_refreshes: int = 2
    recent_weighted_losses: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.max_hypotheses, bool) or not 1 <= self.max_hypotheses <= 4:
            raise ValueError("max_hypotheses must be in the range [1, 4]")
        if len(self.entries) > self.max_hypotheses:
            raise ValueError("the pool exceeds max_hypotheses")
        ids = [entry.hypothesis_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("hypothesis identifiers must be unique within a pool")
        if not isfinite(self.eta) or self.eta <= 0:
            raise ValueError("eta must be finite and positive")
        if not isfinite(self.complexity_lambda) or self.complexity_lambda < 0:
            raise ValueError("complexity_lambda must be finite and non-negative")
        if (
            not isfinite(self.effective_pool_refresh_threshold)
            or self.effective_pool_refresh_threshold <= 0
        ):
            raise ValueError("effective_pool_refresh_threshold must be finite and positive")
        if not isfinite(self.loss_refresh_threshold) or self.loss_refresh_threshold < 0:
            raise ValueError("loss_refresh_threshold must be finite and non-negative")
        if isinstance(self.consecutive_loss_refreshes, bool) or self.consecutive_loss_refreshes < 1:
            raise ValueError("consecutive_loss_refreshes must be a positive integer")
        if len(self.recent_weighted_losses) > self.consecutive_loss_refreshes:
            raise ValueError("too many recent losses were retained")
        if any(not isfinite(loss) or loss < 0 for loss in self.recent_weighted_losses):
            raise ValueError("recent weighted losses must be finite and non-negative")

    @classmethod
    def from_hypotheses(
        cls,
        hypotheses: Sequence[Hypothesis],
        *,
        eta: float = 5.0,
        complexity_lambda: float = 0.002,
        max_hypotheses: int = 4,
        effective_pool_refresh_threshold: float = 1.5,
        loss_refresh_threshold: float = 0.25,
        consecutive_loss_refreshes: int = 2,
    ) -> HypothesisPool:
        if len(hypotheses) > max_hypotheses:
            raise ValueError("too many hypotheses for the configured pool")
        return cls(
            entries=tuple(WeightedHypothesis(hypothesis) for hypothesis in hypotheses),
            eta=eta,
            complexity_lambda=complexity_lambda,
            max_hypotheses=max_hypotheses,
            effective_pool_refresh_threshold=effective_pool_refresh_threshold,
            loss_refresh_threshold=loss_refresh_threshold,
            consecutive_loss_refreshes=consecutive_loss_refreshes,
        )

    @property
    def weights(self) -> tuple[float, ...]:
        """Return stable normalized MDL-Gibbs weights; invalid entries receive zero."""

        log_weights = tuple(
            -self.eta * entry.cumulative_loss
            - self.complexity_lambda * float(entry.ast_nodes)
            if entry.valid
            else -inf
            for entry in self.entries
        )
        return _stable_softmax(log_weights)

    @property
    def hypotheses(self) -> tuple[Hypothesis, ...]:
        """Return programs in the same stable order as :attr:`weights`."""

        return tuple(entry.hypothesis for entry in self.entries)

    @property
    def weighted_hypotheses(self) -> tuple[tuple[Hypothesis, float], ...]:
        """Pair valid programs with normalized weight, excluding zero-weight entries."""

        return tuple(
            (entry.hypothesis, weight)
            for entry, weight in zip(self.entries, self.weights, strict=True)
            if weight > 0.0
        )

    @property
    def effective_sample_size(self) -> float:
        squared_weight_sum = sum(weight * weight for weight in self.weights)
        return 0.0 if squared_weight_sum == 0.0 else 1.0 / squared_weight_sum

    @property
    def all_invalid(self) -> bool:
        return not self.entries or all(not entry.valid for entry in self.entries)

    @property
    def needs_refresh(self) -> bool:
        if self.all_invalid or self.effective_sample_size < self.effective_pool_refresh_threshold:
            return True
        return (
            len(self.recent_weighted_losses) == self.consecutive_loss_refreshes
            and all(loss > self.loss_refresh_threshold for loss in self.recent_weighted_losses)
        )

    def weighted_predictions(
        self,
        history: History,
        action: Action,
    ) -> dict[str, Prediction | None]:
        """Predict with every valid entry, mapping exceptions to invalid observations."""

        predictions: dict[str, Prediction | None] = {}
        for entry in self.entries:
            if not entry.valid:
                predictions[entry.hypothesis_id] = None
                continue
            try:
                prediction = entry.hypothesis.predict(history, action)
                if not isinstance(prediction, Prediction):
                    raise TypeError("predict() did not return Prediction")
                predictions[entry.hypothesis_id] = prediction
            except Exception:
                # Runtime workers report an invalid program by raising.  The pool
                # intentionally does not retain exception strings, which may leak
                # generated source or host details into experiment artifacts.
                predictions[entry.hypothesis_id] = None
        return predictions

    def invalidate(
        self, hypothesis_ids: Sequence[str], *, reason: str = "planning_failed"
    ) -> HypothesisPool:
        """Persistently remove programs that failed a required planning prediction."""

        identifiers = frozenset(hypothesis_ids)
        unknown = identifiers - {entry.hypothesis_id for entry in self.entries}
        if unknown:
            raise ValueError("cannot invalidate unknown hypotheses: " + ", ".join(sorted(unknown)))
        return replace(
            self,
            entries=tuple(
                replace(entry, valid=False, invalid_reason=reason)
                if entry.hypothesis_id in identifiers and entry.valid
                else entry
                for entry in self.entries
            ),
        )

    def update(
        self,
        predictions: Mapping[str, Prediction | None],
        actual_grid: npt.ArrayLike,
        actual_game_state: GameState | str,
        actual_level_delta: int,
    ) -> HypothesisPool:
        """Return the post-transition pool using predictions made pre-action."""

        unknown_ids = set(predictions) - {entry.hypothesis_id for entry in self.entries}
        if unknown_ids:
            raise ValueError(
                "predictions contain unknown hypothesis identifiers: "
                + ", ".join(sorted(unknown_ids))
            )
        prior_weights = self.weights
        updated_entries: list[WeightedHypothesis] = []
        current_losses: list[float] = []
        for entry in self.entries:
            prediction = predictions.get(entry.hypothesis_id)
            if not entry.valid:
                updated_entries.append(entry)
                current_losses.append(MAX_PREQUENTIAL_LOSS)
            elif prediction is None:
                updated_entries.append(
                    replace(
                        entry,
                        valid=False,
                        latest_loss=MAX_PREQUENTIAL_LOSS,
                        invalid_reason="prediction_failed",
                    )
                )
                current_losses.append(MAX_PREQUENTIAL_LOSS)
            else:
                loss = prequential_loss(
                    prediction,
                    actual_grid,
                    actual_game_state,
                    actual_level_delta,
                )
                updated_entries.append(
                    replace(
                        entry,
                        cumulative_loss=entry.cumulative_loss + loss,
                        latest_loss=loss,
                    )
                )
                current_losses.append(loss)

        if prior_weights and sum(prior_weights) > 0:
            weighted_loss = sum(
                weight * loss for weight, loss in zip(prior_weights, current_losses, strict=True)
            )
        else:
            weighted_loss = MAX_PREQUENTIAL_LOSS
        recent = (*self.recent_weighted_losses, weighted_loss)[
            -self.consecutive_loss_refreshes :
        ]
        return replace(
            self,
            entries=tuple(updated_entries),
            recent_weighted_losses=recent,
        )


def behavioral_deduplicate(
    hypotheses: Sequence[Hypothesis],
    history: History,
    actions: Sequence[Action],
    *,
    max_hypotheses: int = 4,
    recorded_transitions: Sequence[RecordedTransition] = (),
) -> tuple[Hypothesis, ...]:
    """Keep the smallest-AST program for every exact predicted behavior signature."""

    if not 1 <= max_hypotheses <= 4:
        raise ValueError("max_hypotheses must be in the range [1, 4]")
    if not actions:
        raise ValueError("at least one action is required for behavioral deduplication")

    recorded_queries: list[tuple[History, Action]] = [
        (item.history, item.action) for item in recorded_transitions
    ]
    if not recorded_queries:
        for index in range(1, len(history.frames)):
            recorded_action = history.actions[index]
            if recorded_action is None:
                continue
            recorded_queries.append(
                (
                    History(
                        frames=history.frames[:index],
                        actions=history.actions[:index],
                        available_action_sets=history.available_action_sets[:index],
                        game_states=history.game_states[:index],
                        level_deltas=history.level_deltas[:index],
                        levels=history.levels[:index],
                    ),
                    recorded_action,
                )
            )
    queries = (*recorded_queries, *((history, action) for action in actions))

    representatives: dict[
        tuple[tuple[tuple[int, int], bytes, GameState, int], ...],
        tuple[int, Hypothesis],
    ] = {}
    for index, hypothesis in enumerate(hypotheses):
        try:
            signature = tuple(
                hypothesis.predict(query_history, action).signature()
                for query_history, action in queries
            )
        except Exception:
            continue
        existing = representatives.get(signature)
        candidate_key = (hypothesis.ast_nodes, hypothesis.hypothesis_id)
        if existing is None:
            representatives[signature] = (index, hypothesis)
        else:
            _, incumbent = existing
            incumbent_key = (incumbent.ast_nodes, incumbent.hypothesis_id)
            if candidate_key < incumbent_key:
                representatives[signature] = (index, hypothesis)

    selected = sorted(representatives.values(), key=lambda item: item[0])
    return tuple(hypothesis for _, hypothesis in selected[:max_hypotheses])


@dataclass(frozen=True, slots=True)
class CrossLevelPersistence:
    """Beta(1,1)-regularized estimate of hypothesis survival across levels."""

    successes: int = 0
    trials: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.successes, bool)
            or isinstance(self.trials, bool)
            or self.successes < 0
            or self.trials < 0
            or self.successes > self.trials
        ):
            raise ValueError("persistence counts require 0 <= successes <= trials")

    @property
    def estimate(self) -> float:
        """Return ``(1 + successes) / (2 + trials)`` from the preregistered plan."""

        return (1.0 + self.successes) / (2.0 + self.trials)

    def observe(self, survived: bool) -> CrossLevelPersistence:
        if not isinstance(survived, bool):
            raise TypeError("survived must be boolean")
        return replace(
            self,
            successes=self.successes + int(survived),
            trials=self.trials + 1,
        )

    def observe_boundary(
        self,
        first_two_transition_mean_loss: float,
        *,
        threshold: float = 0.25,
    ) -> CrossLevelPersistence:
        if not isfinite(first_two_transition_mean_loss) or first_two_transition_mean_loss < 0:
            raise ValueError("boundary mean loss must be finite and non-negative")
        if not isfinite(threshold) or threshold < 0:
            raise ValueError("boundary threshold must be finite and non-negative")
        return self.observe(first_two_transition_mean_loss <= threshold)

    def multiplier(self, level: int, win_levels: int) -> float:
        """Return the remaining-level-weighted cross-level multiplier ``m_l``."""

        if (
            isinstance(level, bool)
            or isinstance(win_levels, bool)
            or not isinstance(level, int)
            or not isinstance(win_levels, int)
            or level < 1
            or win_levels < level
        ):
            raise ValueError("require integer levels satisfying 1 <= level <= win_levels")
        remaining_weight = sum(range(level + 1, win_levels + 1))
        return 1.0 + self.estimate * float(remaining_weight) / float(level)
