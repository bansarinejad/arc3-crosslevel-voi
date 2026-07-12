"""Shared, bounded policy for grounding-triggered program repair."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .candidates import candidates_from_history
from .controller import Variant
from .grounding import ProgramGroundingResult, evaluate_program_grounding
from .model import GenerationResult, ModelBackend
from .program import candidate_points_from_source
from .prompts import HYPOTHESIS_DIVERSITY_ROLES
from .types import Action, History


@dataclass(frozen=True, slots=True)
class GroundedSource:
    """One generated source and its batch-local grounding role/result."""

    batch_index: int
    candidate_index: int
    source: str
    result: ProgramGroundingResult | None
    evaluation_error: str | None = None

    @property
    def assigned_role(self) -> str:
        return HYPOTHESIS_DIVERSITY_ROLES[self.candidate_index % len(HYPOTHESIS_DIVERSITY_ROLES)]

    @property
    def graded_role(self) -> bool:
        return self.candidate_index % len(HYPOTHESIS_DIVERSITY_ROLES) != 0

    @property
    def eligible(self) -> bool:
        return self.result is not None and self.result.eligible


@dataclass(frozen=True, slots=True)
class GroundingBatch:
    """One backend call and the grounding evaluation of every returned source."""

    batch_index: int
    feedback: str | None
    generation: GenerationResult
    actions: tuple[Action, ...]
    programs: tuple[GroundedSource, ...]


@dataclass(frozen=True, slots=True)
class GroundingGeneration:
    """At most one initial and one grounding-repair batch."""

    batches: tuple[GroundingBatch, ...]

    @property
    def programs(self) -> tuple[GroundedSource, ...]:
        return tuple(program for batch in self.batches for program in batch.programs)

    @property
    def output_tokens(self) -> int:
        return sum(batch.generation.output_tokens for batch in self.batches)

    @property
    def repair_attempts(self) -> int:
        return max(0, len(self.batches) - 1)

    @property
    def repair_feedback(self) -> str | None:
        return None if len(self.batches) < 2 else self.batches[1].feedback


def generate_grounded_program_batches(
    backend: ModelBackend,
    history: History,
    *,
    variant: Variant | str,
    target: int,
    initial_feedback: str | None,
    max_new_tokens_per_hypothesis: int,
    max_candidates: int,
    timeout_seconds: float,
    memory_limit_mb: int,
    rollout_depth: int,
    remaining_generated_tokens: int,
    remaining_wall_seconds: float,
    remaining_generation_batches: int,
) -> GroundingGeneration:
    """Generate, ground, and optionally repair once within all shared budgets."""

    if target < 1:
        raise ValueError("target must be positive")
    if remaining_generated_tokens < 1:
        raise ValueError("no generated-token budget remains")
    if remaining_wall_seconds <= 0:
        raise ValueError("no wall-time budget remains")
    if remaining_generation_batches < 1:
        raise ValueError("no generation-batch budget remains")

    started = time.monotonic()
    initial_count = min(target, remaining_generated_tokens)
    initial_limit = min(
        max_new_tokens_per_hypothesis,
        remaining_generated_tokens // initial_count,
    )
    initial = backend.generate_programs(
        history,
        initial_count,
        feedback=initial_feedback,
        max_new_tokens=initial_limit,
        max_wall_seconds=remaining_wall_seconds,
    )
    if (
        isinstance(initial.output_tokens, bool)
        or initial.output_tokens < 0
        or initial.output_tokens > remaining_generated_tokens
    ):
        raise ValueError("initial generation reported output outside the token budget")
    initial_programs, initial_actions = _ground_generation(
        initial,
        history,
        batch_index=0,
        max_candidates=max_candidates,
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
        rollout_depth=rollout_depth,
    )
    batches = [GroundingBatch(0, initial_feedback, initial, initial_actions, initial_programs)]

    remaining_tokens = remaining_generated_tokens - initial.output_tokens
    remaining_wall = remaining_wall_seconds - (time.monotonic() - started)
    needs_repair = repair_needed(initial_programs, variant)
    if (
        needs_repair
        and remaining_generation_batches >= 2
        and remaining_tokens >= target
        and remaining_wall > 0
    ):
        feedback = grounding_repair_feedback(initial_programs, variant)
        repair_limit = min(
            max_new_tokens_per_hypothesis,
            remaining_tokens // target,
        )
        repair = backend.generate_programs(
            history,
            target,
            feedback=feedback,
            max_new_tokens=repair_limit,
            max_wall_seconds=remaining_wall,
        )
        if (
            isinstance(repair.output_tokens, bool)
            or repair.output_tokens < 0
            or repair.output_tokens > remaining_tokens
        ):
            raise ValueError("repair generation reported output outside the token budget")
        repair_programs, repair_actions = _ground_generation(
            repair,
            history,
            batch_index=1,
            max_candidates=max_candidates,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            rollout_depth=rollout_depth,
        )
        batches.append(GroundingBatch(1, feedback, repair, repair_actions, repair_programs))
    return GroundingGeneration(tuple(batches))


def _ground_generation(
    generation: GenerationResult,
    history: History,
    *,
    batch_index: int,
    max_candidates: int,
    timeout_seconds: float,
    memory_limit_mb: int,
    rollout_depth: int,
) -> tuple[tuple[GroundedSource, ...], tuple[Action, ...]]:
    points = tuple(
        point for source in generation.texts for point in candidate_points_from_source(source)
    )
    actions = candidates_from_history(
        history,
        cached_points=points,
        max_candidates=max_candidates,
    )
    return (
        evaluate_grounding_batch(
            generation.texts,
            history,
            actions,
            batch_index=batch_index,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            rollout_depth=rollout_depth,
        ),
        actions,
    )


def evaluate_grounding_batch(
    sources: Sequence[str],
    history: History,
    actions: Sequence[Action],
    *,
    batch_index: int,
    timeout_seconds: float,
    memory_limit_mb: int,
    rollout_depth: int,
) -> tuple[GroundedSource, ...]:
    """Evaluate batch-local roles before any persistent workers are constructed."""

    if isinstance(batch_index, bool) or batch_index < 0:
        raise ValueError("batch_index must be a non-negative integer")
    evaluated: list[GroundedSource] = []
    for candidate_index, source in enumerate(sources):
        graded_role = candidate_index % len(HYPOTHESIS_DIVERSITY_ROLES) != 0
        try:
            result = evaluate_program_grounding(
                source,
                history,
                actions,
                timeout_seconds=timeout_seconds,
                memory_limit_mb=memory_limit_mb,
                rollout_depth=rollout_depth,
                require_action_sensitivity=graded_role,
                require_goal_conditioning=graded_role,
            )
        except Exception as exc:  # fail closed around diagnostic infrastructure
            evaluated.append(
                GroundedSource(
                    batch_index,
                    candidate_index,
                    source,
                    None,
                    f"{type(exc).__name__}",
                )
            )
        else:
            evaluated.append(GroundedSource(batch_index, candidate_index, source, result))
    return tuple(evaluated)


def repair_needed(evaluated: Sequence[GroundedSource], variant: Variant | str) -> bool:
    """Return whether one additional generation batch is contract-justified."""

    arm = Variant.coerce(variant)
    if arm is Variant.DIRECT:
        return False
    conservative = sum(item.eligible and not item.graded_role for item in evaluated)
    if arm is Variant.SINGLE:
        return conservative < 1
    graded = sum(item.eligible and item.graded_role for item in evaluated)
    return conservative < 1 or graded < 2


def grounding_repair_feedback(evaluated: Sequence[GroundedSource], variant: Variant | str) -> str:
    """Build concise contract feedback without echoing any generated source text."""

    arm = Variant.coerce(variant)
    if arm is Variant.DIRECT:
        raise ValueError("the direct arm has no program-grounding repair")
    conservative = sum(item.eligible and not item.graded_role for item in evaluated)
    graded = sum(item.eligible and item.graded_role for item in evaluated)
    categories: Counter[str] = Counter()
    for item in evaluated:
        if item.eligible:
            continue
        result = item.result
        if result is None:
            categories["evaluation_error"] += 1
            continue
        if not result.sandbox_valid:
            categories["sandbox_invalid"] += 1
        if result.palette_conflicts:
            categories["palette_conflict"] += 1
        if result.unsafe_coordinate_use:
            categories["unsafe_coordinate_use"] += 1
        if not result.all_actions_ok:
            categories["prediction_contract"] += 1
        if not result.goal_value_ok:
            categories["goal_execution"] += 1
        if result.action_sensitivity_required and not result.action_sensitive:
            categories["action_insensitive"] += 1
        if result.goal_conditioning_required and not result.goal_action_conditioned:
            categories["goal_unconditioned"] += 1
    failures = (
        ", ".join(f"{name}={categories[name]}" for name in sorted(categories))
        or "none_classified=1"
    )
    target = (
        "one eligible conservative candidate-0 program"
        if arm is Variant.SINGLE
        else "one eligible conservative candidate-0 plus two eligible graded-role programs"
    )
    return (
        "Grounding repair: the prior batch had "
        f"eligible_conservative={conservative}, eligible_graded={graded}; "
        f"contract_failures: {failures}. Generate fresh assigned-role programs targeting "
        f"{target}. History is an attribute-only record: use len(history.frames), "
        "history.frames[i], history.actions[i], and the other documented tuple fields; never "
        "use history[i], history.get, frame.get, or model-only grid_values. Use grid.shape and "
        "visible components/geometry; no hasattr or pass, and no arbitrary fixed coordinates, "
        "dimensions, denominators, or synthesized palette values. Preserve recorded transitions. "
        "Align each graded goal with its predicted "
        "local effect and normalize by a visible component or target extent so same-depth spread "
        "is at least 0.0125; do not normalize sparse effects by grid.size or 100. Do not copy "
        "prior programs."
    )


__all__ = [
    "GroundedSource",
    "GroundingBatch",
    "GroundingGeneration",
    "evaluate_grounding_batch",
    "generate_grounded_program_batches",
    "grounding_repair_feedback",
    "repair_needed",
]
