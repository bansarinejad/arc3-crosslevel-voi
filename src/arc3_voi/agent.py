"""Composition root connecting one model backend to all controller variants."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .candidates import candidates_from_history
from .config import (
    PATH_DEFICIT_RUNTIME_VERSION,
    PROBE_DISAGREEMENT_POLICY_HASHES,
    SystemConfig,
)
from .controller import (
    Controller,
    ControllerConfig,
    DirectPolicyResult,
    RefreshResult,
    Variant,
)
from .grounding_repair import generate_grounded_program_batches
from .hypothesis import (
    HypothesisPool,
    WeightedHypothesis,
    behavioral_deduplicate,
    replay_cumulative_loss,
)
from .model import ModelBackend
from .program import ExecutableHypothesis
from .types import Action, ActionKind, Budget, History


class HypothesisSourceNotAdmittedError(ValueError):
    """Raised before live resources are created for a registration-only source."""


class TreatmentNotAdmittedError(ValueError):
    """Raised before live resources are created for a frozen treatment."""


LIVE_IMPLEMENTATION_CONTRACT_VERSION = "crosslevel-voi-runtime-v3"
LIVE_COMPLETION_COST_POLICY_IDENTITY = (
    "endpoint-v1",
    "c12daf008d7ee6792b3ade429dacb8a65a108b9d5eb8ea8d1f5e78552dd2e95a",
)
LIVE_PROBE_DISAGREEMENT_POLICY_IDENTITY = (
    "winning-action-agreement-v1",
    PROBE_DISAGREEMENT_POLICY_HASHES["winning-action-agreement-v1"],
)


def require_admitted_hypothesis_source(config: SystemConfig) -> None:
    """Fail closed until a non-Qwen live producer is explicitly admitted."""

    source = config.experiment.hypothesis_source
    if source != "qwen":
        raise HypothesisSourceNotAdmittedError(
            f"hypothesis_source={source!r} is registration-only; live producer wiring "
            "and admission are not authorized, and no Qwen backend may execute under "
            "this source label"
        )


def require_live_execution_admitted(config: SystemConfig) -> None:
    """Admit only the exact runtime-v3/Qwen/endpoint live contract."""

    runtime_version = config.experiment.implementation_contract_version
    if runtime_version == PATH_DEFICIT_RUNTIME_VERSION:
        raise TreatmentNotAdmittedError(
            "crosslevel-voi-runtime-v4/path-deficit-v2 failed its preregistered "
            "synthetic gate and is frozen; model preflight, live execution, and "
            "matrix execution are not authorized under any hypothesis source"
        )
    if runtime_version != LIVE_IMPLEMENTATION_CONTRACT_VERSION:
        raise TreatmentNotAdmittedError(
            f"implementation_contract_version={runtime_version!r} is not in the exact "
            "live-contract allowlist; model preflight, live execution, matrix execution, "
            "and live artifact output are not authorized under any hypothesis source"
        )

    configured_identity = (
        config.planning.completion_cost_policy_version,
        config.planning.completion_cost_policy_sha256,
    )
    if configured_identity != LIVE_COMPLETION_COST_POLICY_IDENTITY:
        raise TreatmentNotAdmittedError(
            "completion-cost policy identity is not the admitted endpoint-v1 contract; "
            "model preflight, live execution, matrix execution, and live artifact output "
            "are not authorized"
        )

    configured_probe_identity = (
        config.planning.probe_disagreement_policy_version,
        config.planning.probe_disagreement_policy_sha256,
    )
    if configured_probe_identity != LIVE_PROBE_DISAGREEMENT_POLICY_IDENTITY:
        raise TreatmentNotAdmittedError(
            "probe-disagreement policy identity is not the admitted "
            "winning-action-agreement-v1 contract; model preflight, live execution, "
            "matrix execution, and live artifact output are not authorized"
        )

    require_admitted_hypothesis_source(config)


def qwen_producer_contract_sha256(config: SystemConfig) -> str:
    """Hash the source-producing Qwen contract independently of controller variant/seed."""

    require_admitted_hypothesis_source(config)
    experiment = config.experiment
    payload = {
        "contract_version": "qwen-executable-program-producer-v1",
        "generation": asdict(config.generation),
        "implementation_contract_version": (
            "crosslevel-voi-runtime-v3"
            if experiment.implementation_contract_version == "crosslevel-voi-runtime-v4"
            else experiment.implementation_contract_version
        ),
        "max_generated_tokens": experiment.max_generated_tokens,
        "max_generation_batches": experiment.max_generation_batches,
        "model": None if config.model is None else asdict(config.model),
        "perception_contract_sha256": experiment.perception_contract_sha256,
        "perception_contract_version": experiment.perception_contract_version,
        "prompt_contract_sha256": experiment.prompt_contract_sha256,
        "prompt_contract_version": experiment.prompt_contract_version,
        "sandbox": asdict(config.sandbox),
        "source": "qwen",
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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
        batches_already_used = (
            0 if self.controller is None else self.controller.generation_batches_used
        )
        grounded_generation = generate_grounded_program_batches(
            self.backend,
            history,
            variant=variant,
            target=target,
            initial_feedback=feedback,
            max_new_tokens_per_hypothesis=(self.config.generation.max_new_tokens_per_hypothesis),
            max_candidates=self.config.planning.max_candidates,
            timeout_seconds=self.config.sandbox.timeout_ms / 1000,
            memory_limit_mb=self.config.sandbox.memory_mb,
            rollout_depth=self.config.planning.depth,
            remaining_generated_tokens=budget.remaining_generated_tokens,
            remaining_wall_seconds=budget.remaining_wall_seconds,
            remaining_generation_batches=(
                self.config.experiment.max_generation_batches - batches_already_used
            ),
        )
        evaluated = grounded_generation.programs

        generated: list[ExecutableHypothesis] = []
        invalid_programs = 0
        grounding_eligible_programs = 0
        grounding_rejected_programs = 0
        for item in evaluated:
            grounding = item.result
            if grounding is None or not grounding.eligible:
                grounding_rejected_programs += 1
                invalid_programs += 1
                continue
            grounding_eligible_programs += 1
            try:
                hypothesis = ExecutableHypothesis(
                    item.source,
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

        survivors = (
            []
            if current is None
            else [entry.hypothesis for entry in current.entries if entry.valid]
        )
        candidates = [*survivors, *generated]
        recorded_transitions = (
            () if self.controller is None else tuple(self.controller.recorded_transitions)
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

        existing = (
            {} if current is None else {entry.hypothesis_id: entry for entry in current.entries}
        )
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
                1.0 if target == 1 else self.config.hypotheses.effective_pool_refresh_threshold
            ),
            loss_refresh_threshold=self.config.hypotheses.loss_refresh_threshold,
            consecutive_loss_refreshes=self.config.hypotheses.consecutive_loss_refreshes,
            recent_weighted_losses=(() if current is None else current.recent_weighted_losses),
        )
        selected_ids = {entry.hypothesis_id for entry in entries}
        grounding_selected_hypothesis_ids = tuple(entry.hypothesis_id for entry in entries)
        for hypothesis_id in tuple(self._owned):
            if hypothesis_id not in selected_ids:
                self._retire(self._owned.pop(hypothesis_id))
        return RefreshResult(
            pool,
            grounded_generation.output_tokens,
            invalid_programs=invalid_programs,
            peak_vram_gb=max(
                (
                    batch.generation.peak_vram_gb
                    for batch in grounded_generation.batches
                    if batch.generation.peak_vram_gb is not None
                ),
                default=None,
            ),
            generated_sources=tuple(
                source for batch in grounded_generation.batches for source in batch.generation.texts
            ),
            grounding_eligible_programs=grounding_eligible_programs,
            grounding_rejected_programs=grounding_rejected_programs,
            grounding_selected_hypothesis_ids=grounding_selected_hypothesis_ids,
            generation_batches_used=len(grounded_generation.batches),
            generation_batch_output_tokens=tuple(
                batch.generation.output_tokens for batch in grounded_generation.batches
            ),
            generated_source_batches=tuple(
                batch.generation.texts for batch in grounded_generation.batches
            ),
            grounding_repair_attempts=grounded_generation.repair_attempts,
            grounding_repair_feedback=grounded_generation.repair_feedback,
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
                1.0 if target == 1 else self.config.hypotheses.effective_pool_refresh_threshold
            ),
            loss_refresh_threshold=self.config.hypotheses.loss_refresh_threshold,
            consecutive_loss_refreshes=self.config.hypotheses.consecutive_loss_refreshes,
        )

    def close(self) -> None:
        for hypothesis in self._owned.values():
            self._retire(hypothesis)
        self._owned.clear()
        close_backend = getattr(self.backend, "close", None)
        if callable(close_backend):
            close_backend()

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

    require_live_execution_admitted(config)
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
            completion_cost_policy_version=(
                config.planning.completion_cost_policy_version
            ),
            completion_cost_policy_sha256=(
                config.planning.completion_cost_policy_sha256
            ),
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
