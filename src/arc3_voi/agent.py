"""Composition root connecting one model backend to all controller variants."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .candidates import candidates_from_history
from .config import SystemConfig
from .controller import (
    Controller,
    ControllerConfig,
    DirectPolicyResult,
    RefreshResult,
    Variant,
)
from .hypothesis import (
    HypothesisPool,
    WeightedHypothesis,
    behavioral_deduplicate,
    replay_cumulative_loss,
)
from .model import ModelBackend
from .program import ExecutableHypothesis
from .types import Action, ActionKind, Budget, History


@dataclass(slots=True)
class GeneratedAgent:
    """Own a controller and every persistent generated-program worker."""

    controller: Controller
    _generator: _HypothesisGenerator

    def close(self) -> None:
        self._generator.close()

    def __enter__(self) -> GeneratedAgent:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()


class _HypothesisGenerator:
    def __init__(self, backend: ModelBackend, config: SystemConfig) -> None:
        self.backend = backend
        self.config = config
        self.controller: Controller | None = None
        self._owned: dict[str, ExecutableHypothesis] = {}
        self._retired_prediction_calls = 0
        self._retired_goal_calls = 0
        self._retired_timeouts = 0
        self._retired_execution_errors = 0

    def __call__(self, history: History, budget: Budget) -> RefreshResult:
        variant = Variant.coerce(self.config.experiment.variant)
        target = 1 if variant is Variant.SINGLE else self.config.hypotheses.max_hypotheses
        if budget.remaining_generated_tokens <= 0:
            return RefreshResult(self._current_or_empty(target), 0)

        current = self.controller.pool if self.controller is not None else None
        feedback = None
        if current is not None and current.recent_weighted_losses:
            feedback = (
                "Recent weighted transition losses: "
                + ", ".join(f"{value:.4f}" for value in current.recent_weighted_losses)
                + ". Propose materially different rules that explain the contradiction."
            )
        generation_count = min(target, budget.remaining_generated_tokens)
        if generation_count <= 0:
            return RefreshResult(self._current_or_empty(target), 0)
        per_sequence_limit = min(
            self.config.generation.max_new_tokens_per_hypothesis,
            budget.remaining_generated_tokens // generation_count,
        )
        result = self.backend.generate_programs(
            history,
            generation_count,
            feedback=feedback,
            max_new_tokens=per_sequence_limit,
            max_wall_seconds=budget.remaining_wall_seconds,
        )

        generated: list[ExecutableHypothesis] = []
        invalid_programs = 0
        for source in result.texts:
            try:
                hypothesis = ExecutableHypothesis(
                    source,
                    timeout_seconds=self.config.sandbox.timeout_ms / 1000,
                    memory_limit_mb=self.config.sandbox.memory_mb,
                )
            except Exception:
                invalid_programs += 1
                continue
            if hypothesis.hypothesis_id in self._owned:
                hypothesis.close()
                continue
            generated.append(hypothesis)
            self._owned[hypothesis.hypothesis_id] = hypothesis

        model_points = tuple(
            point for hypothesis in generated for point in hypothesis.candidate_points
        )
        if self.controller is not None:
            self.controller.cache_points(model_points)

        survivors = [] if current is None else [
            entry.hypothesis for entry in current.entries if entry.valid
        ]
        candidates = [*survivors, *generated]
        recorded_transitions = (
            ()
            if self.controller is None
            else tuple(self.controller.recorded_transitions)
        )
        actions = candidates_from_history(
            history,
            cached_points=model_points,
            max_candidates=self.config.planning.max_candidates,
        )
        if actions and candidates:
            selected = behavioral_deduplicate(
                candidates,
                history,
                actions,
                max_hypotheses=target,
                recorded_transitions=recorded_transitions,
            )
        else:
            selected = tuple(candidates[:target])

        existing = {} if current is None else {
            entry.hypothesis_id: entry for entry in current.entries
        }
        replayed: dict[str, WeightedHypothesis] = {}
        for hypothesis in generated:
            try:
                cumulative_loss, latest_loss = replay_cumulative_loss(
                    hypothesis, recorded_transitions
                )
            except Exception:
                invalid_programs += 1
                continue
            replayed[hypothesis.hypothesis_id] = WeightedHypothesis(
                hypothesis,
                cumulative_loss=cumulative_loss,
                latest_loss=latest_loss,
            )
        entries = tuple(
            existing.get(
                hypothesis.hypothesis_id,
                replayed.get(hypothesis.hypothesis_id, WeightedHypothesis(hypothesis)),
            )
            for hypothesis in selected
            if hypothesis.hypothesis_id in existing or hypothesis.hypothesis_id in replayed
        )
        pool = HypothesisPool(
            entries=entries,
            eta=self.config.hypotheses.eta,
            complexity_lambda=self.config.hypotheses.complexity_lambda,
            max_hypotheses=target,
            effective_pool_refresh_threshold=(
                1.0
                if target == 1
                else self.config.hypotheses.effective_pool_refresh_threshold
            ),
            loss_refresh_threshold=self.config.hypotheses.loss_refresh_threshold,
            consecutive_loss_refreshes=self.config.hypotheses.consecutive_loss_refreshes,
            recent_weighted_losses=(
                () if current is None else current.recent_weighted_losses
            ),
        )
        selected_ids = {entry.hypothesis_id for entry in entries}
        for hypothesis_id in tuple(self._owned):
            if hypothesis_id not in selected_ids:
                self._retire(self._owned.pop(hypothesis_id))
        return RefreshResult(
            pool,
            result.output_tokens,
            invalid_programs=invalid_programs,
            peak_vram_gb=result.peak_vram_gb,
            generated_sources=result.texts,
        )

    def _current_or_empty(self, target: int) -> HypothesisPool:
        if self.controller is not None and self.controller.pool is not None:
            return self.controller.pool
        return HypothesisPool.from_hypotheses(
            (),
            eta=self.config.hypotheses.eta,
            complexity_lambda=self.config.hypotheses.complexity_lambda,
            max_hypotheses=target,
            effective_pool_refresh_threshold=(
                1.0
                if target == 1
                else self.config.hypotheses.effective_pool_refresh_threshold
            ),
            loss_refresh_threshold=self.config.hypotheses.loss_refresh_threshold,
            consecutive_loss_refreshes=self.config.hypotheses.consecutive_loss_refreshes,
        )

    def close(self) -> None:
        for hypothesis in self._owned.values():
            self._retire(hypothesis)
        self._owned.clear()

    def telemetry(self) -> dict[str, int | bool]:
        return {
            "program_prediction_calls": self._retired_prediction_calls
            + sum(item.prediction_calls for item in self._owned.values()),
            "program_goal_calls": self._retired_goal_calls
            + sum(item.goal_calls for item in self._owned.values()),
            "program_timeouts": self._retired_timeouts
            + sum(item.timeout_count for item in self._owned.values()),
            "program_execution_errors": self._retired_execution_errors
            + sum(item.execution_error_count for item in self._owned.values()),
            "timeout_instrumentation_complete": True,
        }

    def _retire(self, hypothesis: ExecutableHypothesis) -> None:
        self._retired_prediction_calls += hypothesis.prediction_calls
        self._retired_goal_calls += hypothesis.goal_calls
        self._retired_timeouts += hypothesis.timeout_count
        self._retired_execution_errors += hypothesis.execution_error_count
        hypothesis.close()


def build_agent(backend: ModelBackend, config: SystemConfig) -> GeneratedAgent:
    """Build D/S/M/X using the same model and resource contract."""

    generator = _HypothesisGenerator(backend, config)

    def direct_policy(
        history: History, candidates: tuple[Action, ...], budget: Budget
    ) -> DirectPolicyResult:
        valid = tuple(
            action.kind.name
            if action.kind is not ActionKind.ACTION6
            else f"ACTION6(row={action.row},col={action.col})"
            for action in candidates
        )
        raw, result = backend.direct_action(
            history,
            valid,
            max_new_tokens=min(256, budget.remaining_generated_tokens),
            max_wall_seconds=budget.remaining_wall_seconds,
        )
        invalid_output = False
        try:
            action = Action(
                ActionKind.coerce(raw["kind"]),
                row=None if raw.get("row") is None else int(raw["row"]),
                col=None if raw.get("col") is None else int(raw["col"]),
            )
        except (KeyError, TypeError, ValueError):
            action = candidates[0]
            invalid_output = True
        return DirectPolicyResult(
            action,
            result.output_tokens,
            result.peak_vram_gb,
            invalid_output,
        )

    controller = Controller(
        direct_policy=direct_policy,
        refresh_callback=generator,
        config=ControllerConfig(
            variant=Variant.coerce(config.experiment.variant),
            max_candidates=config.planning.max_candidates,
            depth=config.planning.depth,
            beam_width=config.planning.beam_width,
            agreement_threshold=config.planning.agreement_threshold,
            max_probes_per_level=config.planning.max_probes_per_level,
            risk_coefficient=config.planning.risk_coefficient,
            robust_std_coefficient=config.planning.robust_std_coefficient,
            max_refreshes_per_level=config.hypotheses.max_refreshes_per_level,
            max_generation_batches=config.experiment.max_generation_batches,
        ),
        telemetry_callback=generator.telemetry,
    )
    generator.controller = controller
    return GeneratedAgent(controller, generator)


def close_hypotheses(hypotheses: Sequence[Any]) -> None:
    """Best-effort helper for experiment teardown."""

    for hypothesis in hypotheses:
        close = getattr(hypothesis, "close", None)
        if callable(close):
            close()
