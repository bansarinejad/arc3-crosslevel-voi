"""Stateful direct, single-program, myopic, and cross-level controllers."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from arc3_voi.candidates import Point, candidates_from_history
from arc3_voi.hypothesis import CrossLevelPersistence, HypothesisPool, RecordedTransition
from arc3_voi.planner import (
    BeamSearchPlanner,
    NoValidHypotheses,
    PlanningError,
    best_probe,
    committee_agreement,
    committee_indifference,
    robust_exploitation,
)
from arc3_voi.types import (
    Action,
    ActionKind,
    Budget,
    Decision,
    DecisionMode,
    DiagnosticValue,
    GameState,
    History,
    Observation,
    Prediction,
)


class Variant(StrEnum):
    """Preregistered controlled-experiment variants."""

    DIRECT = "D"
    SINGLE = "S"
    MYOPIC = "M"
    CROSS_LEVEL = "X"

    @classmethod
    def coerce(cls, value: Variant | str) -> Variant:
        return value if isinstance(value, cls) else cls(str(value).strip().upper())


class ControllerError(RuntimeError):
    """Base class for failures that must be handled by the episode runner."""


class ControllerBudgetExhausted(ControllerError):
    """Raised before selecting an action that the shared budget cannot afford."""


class EpisodeComplete(ControllerError):
    """Raised when ``act`` is called after the environment has already been won."""


@dataclass(frozen=True, slots=True)
class DirectPolicyResult:
    action: Action
    generated_tokens: int = 0
    peak_vram_gb: float | None = None
    invalid_output: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.generated_tokens, bool) or self.generated_tokens < 0:
            raise ValueError("generated_tokens must be a non-negative integer")
        if self.peak_vram_gb is not None and self.peak_vram_gb < 0:
            raise ValueError("peak_vram_gb must be non-negative")
        if not isinstance(self.invalid_output, bool):
            raise TypeError("invalid_output must be boolean")


@dataclass(frozen=True, slots=True)
class RefreshResult:
    pool: HypothesisPool
    generated_tokens: int = 0
    invalid_programs: int = 0
    peak_vram_gb: float | None = None
    generated_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.generated_tokens, bool) or self.generated_tokens < 0:
            raise ValueError("generated_tokens must be a non-negative integer")
        if isinstance(self.invalid_programs, bool) or self.invalid_programs < 0:
            raise ValueError("invalid_programs must be a non-negative integer")
        if self.peak_vram_gb is not None and self.peak_vram_gb < 0:
            raise ValueError("peak_vram_gb must be non-negative")
        if any(not isinstance(source, str) for source in self.generated_sources):
            raise TypeError("generated_sources must contain strings")


DirectPolicy: TypeAlias = Callable[  # noqa: UP040 - supported by the pinned mypy
    [History, tuple[Action, ...], Budget], Action | DirectPolicyResult
]
RefreshCallback: TypeAlias = Callable[  # noqa: UP040 - supported by the pinned mypy
    [History, Budget], HypothesisPool | RefreshResult
]
TelemetryCallback: TypeAlias = Callable[[], Mapping[str, DiagnosticValue]]  # noqa: UP040


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    variant: Variant = Variant.CROSS_LEVEL
    max_candidates: int = 12
    depth: int = 4
    beam_width: int = 8
    agreement_threshold: float = 0.8
    max_probes_per_level: int = 3
    risk_coefficient: float = 3.0
    robust_std_coefficient: float = 0.5
    max_refreshes_per_level: int = 1
    max_generation_batches: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "variant", Variant.coerce(self.variant))
        positive_integers = (
            ("max_candidates", self.max_candidates),
            ("depth", self.depth),
            ("beam_width", self.beam_width),
            ("max_probes_per_level", self.max_probes_per_level),
            ("max_refreshes_per_level", self.max_refreshes_per_level),
            ("max_generation_batches", self.max_generation_batches),
        )
        if any(isinstance(value, bool) or value < 1 for _, value in positive_integers):
            raise ValueError("controller integer limits must be positive")
        if not 0 <= self.agreement_threshold <= 1:
            raise ValueError("agreement_threshold must be in [0, 1]")
        if self.risk_coefficient < 0 or self.robust_std_coefficient < 0:
            raise ValueError("controller cost coefficients must be non-negative")


class Controller:
    """Select actions while preserving pre-action predictions for exact scoring.

    ``Budget`` is immutable and owned by the episode runner.  Every decision logs
    any generation-token cost in ``diagnostics['generated_tokens']``; callers
    consume that amount together with one environment action before the next call.
    """

    def __init__(
        self,
        *,
        direct_policy: DirectPolicy,
        pool: HypothesisPool | None = None,
        refresh_callback: RefreshCallback | None = None,
        config: ControllerConfig | None = None,
        persistence: CrossLevelPersistence | None = None,
        cached_points: Iterable[Point] = (),
        planner: BeamSearchPlanner | None = None,
        telemetry_callback: TelemetryCallback | None = None,
    ) -> None:
        self.config = config or ControllerConfig()
        self.direct_policy = direct_policy
        self.refresh_callback = refresh_callback
        self.pool = pool
        self.persistence = persistence or CrossLevelPersistence()
        self.cached_points = tuple(cached_points)
        self.planner = planner or BeamSearchPlanner(
            depth=self.config.depth, beam_width=self.config.beam_width
        )
        self.telemetry_callback = telemetry_callback

        self.history = History.empty()
        self._pending_action: Action | None = None
        self._pending_predictions: dict[str, Prediction | None] | None = None
        self._probes_by_level: dict[int, int] = {}
        self._refreshes_by_level: dict[int, int] = {}
        self._generation_batches = 0
        self.recorded_transitions: list[RecordedTransition] = []
        self._boundary_program_losses: dict[str, list[float]] | None = None
        self._boundary_transition_count = 0

    @property
    def probes_by_level(self) -> dict[int, int]:
        return dict(self._probes_by_level)

    def cache_points(self, points: Iterable[Point]) -> None:
        """Replace model-suggested click points for subsequent decisions."""

        self.cached_points = tuple(points)

    def observe_boundary_transfer(self, first_two_transition_mean_loss: float) -> None:
        """Record the preregistered cross-level survival event."""

        self.persistence = self.persistence.observe_boundary(first_two_transition_mean_loss)

    def act(self, observation: Observation, budget: Budget) -> Decision:
        """Ingest a stable observation and choose one attributable environment action."""

        deadline = time.monotonic() + budget.remaining_wall_seconds
        self._ingest(observation)
        if not budget.can_afford(environment_actions=1) or budget.remaining_wall_seconds <= 0:
            raise ControllerBudgetExhausted("no environment-action or wall-time budget remains")

        if observation.game_state is GameState.WIN:
            raise EpisodeComplete("the environment is already in the WIN state")
        if observation.game_state is GameState.GAME_OVER:
            # The ARC interface rejects every other action after GAME_OVER.
            return self._remember(
                Decision(
                    Action(ActionKind.RESET),
                    DecisionMode.EXPLOIT,
                    0.0,
                    {
                        "reason": "game_over_reset",
                        "generated_tokens": 0,
                        **self._telemetry(),
                    },
                ),
                predictions=None,
            )

        candidates = candidates_from_history(
            self.history,
            cached_points=self.cached_points,
            max_candidates=self.config.max_candidates,
        )
        if not candidates:
            raise ControllerError("the active observation exposes no valid actions")

        if self.config.variant is Variant.DIRECT:
            return self._direct(
                candidates, budget, reason="direct_variant", deadline=deadline
            )

        refresh_result = self._maybe_refresh(budget, deadline)
        refreshed = refresh_result is not None
        refresh_tokens = 0 if refresh_result is None else refresh_result.generated_tokens
        invalid_programs = 0 if refresh_result is None else refresh_result.invalid_programs
        peak_vram_gb = None if refresh_result is None else refresh_result.peak_vram_gb
        generated_sources = () if refresh_result is None else refresh_result.generated_sources
        required_hypotheses = 1 if self.config.variant is Variant.SINGLE else 2
        if self.pool is None or len(self.pool.weighted_hypotheses) < required_hypotheses:
            return self._direct(
                candidates,
                budget,
                reason="insufficient_valid_hypotheses",
                already_generated_tokens=refresh_tokens,
                already_invalid_programs=invalid_programs,
                prior_peak_vram_gb=peak_vram_gb,
                generated_sources=generated_sources,
                deadline=deadline,
            )

        weighted_hypotheses = self.pool.weighted_hypotheses
        if self.config.variant is Variant.SINGLE:
            # If a multi-program pool is supplied for an ablation, retain only its
            # highest-weight program and normalize within the single-program arm.
            winner = max(enumerate(weighted_hypotheses), key=lambda item: (item[1][1], -item[0]))
            weighted_hypotheses = ((winner[1][0], 1.0),)

        try:
            snapshot = self.planner.evaluate(
                self.history,
                candidates,
                weighted_hypotheses,
                win_levels=observation.win_levels,
                deadline=deadline,
            )
        except NoValidHypotheses as exc:
            if self.pool is not None and exc.invalid_hypothesis_ids:
                self.pool = self.pool.invalidate(
                    exc.invalid_hypothesis_ids,
                    reason="planner_evaluation_failed",
                )
                invalid_programs += len(exc.invalid_hypothesis_ids)
            return self._direct(
                candidates,
                budget,
                reason="planner_invalidated_hypotheses",
                already_generated_tokens=refresh_tokens,
                already_invalid_programs=invalid_programs,
                prior_peak_vram_gb=peak_vram_gb,
                generated_sources=generated_sources,
                deadline=deadline,
            )
        except PlanningError:
            return self._direct(
                candidates,
                budget,
                reason="planning_failed",
                already_generated_tokens=refresh_tokens,
                already_invalid_programs=invalid_programs,
                prior_peak_vram_gb=peak_vram_gb,
                generated_sources=generated_sources,
                deadline=deadline,
            )
        if snapshot.invalid_hypothesis_ids:
            assert self.pool is not None
            self.pool = self.pool.invalidate(
                snapshot.invalid_hypothesis_ids,
                reason="planner_evaluation_failed",
            )
            invalid_programs += len(snapshot.invalid_hypothesis_ids)
        if len(snapshot.weights) < required_hypotheses:
            return self._direct(
                candidates,
                budget,
                reason="planner_invalidated_hypotheses",
                already_generated_tokens=refresh_tokens,
                already_invalid_programs=invalid_programs,
                prior_peak_vram_gb=peak_vram_gb,
                generated_sources=generated_sources,
                deadline=deadline,
            )
        exploit = robust_exploitation(
            snapshot.actions,
            snapshot.costs,
            snapshot.weights,
            standard_deviation_coefficient=self.config.robust_std_coefficient,
        )
        agreement = committee_agreement(snapshot.actions, snapshot.costs, snapshot.weights)
        indifference = committee_indifference(
            snapshot.actions, snapshot.costs, snapshot.weights
        )

        selected_action = exploit.action
        selected_score = exploit.score
        strategy_mode = DecisionMode.EXPLOIT
        diagnostics: dict[str, str | int | float | bool | None] = {
            "variant": self.config.variant.value,
            "agreement": agreement,
            "committee_indifference": indifference,
            "mean_cost": exploit.mean_cost,
            "cost_std": exploit.standard_deviation,
            "generated_tokens": refresh_tokens,
            "invalid_programs": invalid_programs,
            "peak_vram_gb": peak_vram_gb,
            "hypothesis_weights": ",".join(
                f"{hypothesis_id}:{weight:.12g}"
                for hypothesis_id, weight in zip(
                    snapshot.hypothesis_ids, snapshot.weights, strict=True
                )
            ),
            "cross_level_persistence": self.persistence.estimate,
            "candidate_costs": json.dumps(
                {
                    self._action_key(action): list(snapshot.costs[action])
                    for action in snapshot.actions
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "candidate_prediction_signatures": json.dumps(
                {
                    self._action_key(action): [
                        self._prediction_digest(prediction)
                        for prediction in snapshot.predictions[action]
                    ]
                    for action in snapshot.actions
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "hypothesis_ast_nodes": json.dumps(
                {
                    entry.hypothesis_id: entry.ast_nodes
                    for entry in (() if self.pool is None else self.pool.entries)
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "generated_program_sources": (
                json.dumps(generated_sources, ensure_ascii=False)
                if generated_sources
                else None
            ),
            **self._telemetry(),
        }

        probe_count = self._probes_by_level.get(observation.level, 0)
        if self.config.variant in (Variant.MYOPIC, Variant.CROSS_LEVEL):
            multiplier = (
                1.0
                if self.config.variant is Variant.MYOPIC
                else self.persistence.multiplier(observation.level, observation.win_levels)
            )
            probe = best_probe(
                snapshot.actions,
                snapshot.predictions,
                snapshot.costs,
                snapshot.weights,
                multiplier=multiplier,
                risk_coefficient=self.config.risk_coefficient,
            )
            diagnostics.update(
                {
                    "level_multiplier": multiplier,
                    "probe_evsi": probe.evsi,
                    "probe_catastrophe_probability": probe.catastrophe_probability,
                    "probe_utility": probe.utility,
                    "probe_candidate_action": self._action_key(probe.action),
                    "probe_count_before": probe_count,
                    "probe_cap": self.config.max_probes_per_level,
                    "agreement_threshold": self.config.agreement_threshold,
                }
            )
            agreement_passed = agreement < self.config.agreement_threshold
            cap_passed = probe_count < self.config.max_probes_per_level
            utility_passed = probe.utility > 0
            if not agreement_passed:
                gate_reason = "agreement_at_or_above_threshold"
            elif not cap_passed:
                gate_reason = "level_probe_cap_reached"
            elif not utility_passed:
                gate_reason = "nonpositive_utility"
            else:
                gate_reason = "selected"
            probe_selected = agreement_passed and cap_passed and utility_passed
            diagnostics["probe_gate_reason"] = gate_reason
            diagnostics["probe_selected"] = probe_selected
            if probe_selected:
                selected_action = probe.action
                selected_score = probe.utility
                strategy_mode = DecisionMode.PROBE
                self._probes_by_level[observation.level] = probe_count + 1
            diagnostics["probe_count_after"] = self._probes_by_level.get(
                observation.level, 0
            )

        decision_mode = DecisionMode.REFRESH if refreshed else strategy_mode
        if refreshed:
            diagnostics["post_refresh_mode"] = strategy_mode.value
        selected_predictions = dict(
            zip(
                snapshot.hypothesis_ids,
                snapshot.predictions[selected_action],
                strict=True,
            )
        )
        if time.monotonic() >= deadline:
            raise ControllerBudgetExhausted("wall-time budget expired before action selection")
        return self._remember(
            Decision(selected_action, decision_mode, selected_score, diagnostics),
            predictions=selected_predictions,
        )

    def _ingest(self, observation: Observation) -> None:
        if not self.history.frames:
            self.history = History.from_observation(observation)
            return
        if self._pending_action is None:
            raise ControllerError("a new observation arrived without a pending action")

        level_delta = observation.level - self.history.current_level
        if self._pending_action.kind is not ActionKind.RESET:
            self.recorded_transitions.append(
                RecordedTransition(
                    self.history,
                    self._pending_action,
                    observation.grid,
                    observation.game_state,
                    level_delta,
                )
            )
        was_tracking_boundary = self._boundary_program_losses is not None
        if self.pool is not None and self._pending_predictions is not None:
            self.pool = self.pool.update(
                self._pending_predictions,
                observation.grid,
                observation.game_state,
                level_delta,
            )
            if was_tracking_boundary:
                assert self._boundary_program_losses is not None
                entries = {entry.hypothesis_id: entry for entry in self.pool.entries}
                for hypothesis_id, losses in self._boundary_program_losses.items():
                    entry = entries.get(hypothesis_id)
                    if entry is not None and entry.valid and entry.latest_loss is not None:
                        losses.append(entry.latest_loss)
                self._boundary_transition_count += 1
                if self._boundary_transition_count == 2:
                    survived = any(
                        len(losses) == 2 and sum(losses) / 2 <= 0.25
                        for losses in self._boundary_program_losses.values()
                    )
                    self.persistence = self.persistence.observe(survived)
                    self._boundary_program_losses = None
                    self._boundary_transition_count = 0
        self.history = self.history.append(observation, self._pending_action, level_delta)
        if level_delta > 0:
            # The completion transition itself crosses layouts. Persistence is
            # evaluated only for programs that existed before the boundary,
            # regardless of any refresh that follows in the new level.
            pre_boundary_ids = (
                ()
                if self.pool is None
                else (
                    entry.hypothesis_id
                    for entry in self.pool.entries
                    if entry.valid
                )
            )
            self._boundary_program_losses = {
                hypothesis_id: [] for hypothesis_id in pre_boundary_ids
            }
            self._boundary_transition_count = 0
        self._pending_action = None
        self._pending_predictions = None

    def _should_refresh(self) -> bool:
        if self.pool is None:
            return True
        if self.config.variant is not Variant.SINGLE:
            return self.pool.needs_refresh
        # ESS is necessarily one in the K=1 ablation and must not trigger an
        # unconditional refresh.  Preserve only invalidity/contradiction repair.
        losses = self.pool.recent_weighted_losses
        return self.pool.all_invalid or (
            len(losses) == self.pool.consecutive_loss_refreshes
            and all(loss > self.pool.loss_refresh_threshold for loss in losses)
        )

    def _maybe_refresh(self, budget: Budget, deadline: float) -> RefreshResult | None:
        if not self._should_refresh() or self.refresh_callback is None:
            return None
        level = self.history.current_level
        is_initial_batch = self.pool is None
        refreshes = self._refreshes_by_level.get(level, 0)
        if (
            (not is_initial_batch and refreshes >= self.config.max_refreshes_per_level)
            or self._generation_batches >= self.config.max_generation_batches
            or budget.remaining_generated_tokens <= 0
        ):
            return None

        raw_result = self.refresh_callback(
            self.history, self._budget_before_deadline(budget, deadline)
        )
        result = raw_result if isinstance(raw_result, RefreshResult) else RefreshResult(raw_result)
        if not budget.can_afford(generated_tokens=result.generated_tokens):
            raise ControllerBudgetExhausted("hypothesis refresh exceeded the token budget")
        self.pool = result.pool
        self._generation_batches += 1
        if not is_initial_batch:
            self._refreshes_by_level[level] = refreshes + 1
        if time.monotonic() >= deadline:
            raise ControllerBudgetExhausted("hypothesis refresh exhausted the wall-time budget")
        return result

    def _direct(
        self,
        candidates: tuple[Action, ...],
        budget: Budget,
        *,
        reason: str,
        already_generated_tokens: int = 0,
        already_invalid_programs: int = 0,
        prior_peak_vram_gb: float | None = None,
        generated_sources: tuple[str, ...] = (),
        deadline: float,
    ) -> Decision:
        remaining_budget = self._budget_before_deadline(
            budget.consume(generated_tokens=already_generated_tokens), deadline
        )
        if remaining_budget.remaining_generated_tokens <= 0:
            raise ControllerBudgetExhausted("no generated-token budget remains for direct policy")
        raw_result = self.direct_policy(self.history, candidates, remaining_budget)
        result = (
            raw_result
            if isinstance(raw_result, DirectPolicyResult)
            else DirectPolicyResult(raw_result)
        )
        total_tokens = already_generated_tokens + result.generated_tokens
        if not budget.can_afford(generated_tokens=total_tokens):
            raise ControllerBudgetExhausted("direct fallback exceeds the generation-token budget")
        action = result.action if result.action in candidates else candidates[0]
        invalid_action = result.invalid_output or action is not result.action
        peak_vram_gb = max(
            (value for value in (prior_peak_vram_gb, result.peak_vram_gb) if value is not None),
            default=None,
        )
        if time.monotonic() >= deadline:
            raise ControllerBudgetExhausted("direct policy exhausted the wall-time budget")

        predictions = self.pool.weighted_predictions(self.history, action) if self.pool else None
        diagnostics: dict[str, DiagnosticValue] = {
            "reason": reason,
            "invalid_direct_action_replaced": invalid_action,
            "generated_tokens": total_tokens,
            "invalid_programs": already_invalid_programs,
            "peak_vram_gb": peak_vram_gb,
            "generated_program_sources": (
                json.dumps(generated_sources, ensure_ascii=False)
                if generated_sources
                else None
            ),
            **self._telemetry(),
        }
        return self._remember(
            Decision(
                action,
                DecisionMode.DIRECT_FALLBACK,
                0.0,
                diagnostics,
            ),
            predictions=predictions,
        )

    def _remember(
        self,
        decision: Decision,
        *,
        predictions: dict[str, Prediction | None] | None,
    ) -> Decision:
        self._pending_action = decision.action
        self._pending_predictions = predictions
        return decision

    @staticmethod
    def _budget_before_deadline(budget: Budget, deadline: float) -> Budget:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ControllerBudgetExhausted("shared wall-time budget exhausted")
        elapsed_here = max(0.0, budget.remaining_wall_seconds - remaining)
        return budget.consume(wall_seconds=min(elapsed_here, budget.remaining_wall_seconds))

    def _telemetry(self) -> dict[str, DiagnosticValue]:
        if self.telemetry_callback is None:
            return {}
        return dict(self.telemetry_callback())

    @staticmethod
    def _action_key(action: Action) -> str:
        if action.kind is ActionKind.ACTION6:
            return f"ACTION6({action.row},{action.col})"
        return action.kind.name

    @staticmethod
    def _prediction_digest(prediction: Prediction | None) -> str:
        if prediction is None:
            return "INVALID"
        digest = hashlib.sha256()
        digest.update(prediction.next_grid.tobytes(order="C"))
        digest.update(prediction.game_state.value.encode("ascii"))
        digest.update(str(prediction.level_delta).encode("ascii"))
        return digest.hexdigest()


__all__ = [
    "Controller",
    "ControllerBudgetExhausted",
    "ControllerConfig",
    "ControllerError",
    "DirectPolicyResult",
    "EpisodeComplete",
    "RefreshResult",
    "Variant",
]
