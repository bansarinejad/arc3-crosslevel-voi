"""Budgeted game runner with attributable, replayable immutable traces."""

from __future__ import annotations

import importlib
import time
from dataclasses import replace
from typing import Any, Protocol

from .arc_adapter import EnvironmentSession
from .controller import ControllerBudgetExhausted, EpisodeComplete
from .metrics import RunMetrics, StepRecord
from .replay import action_to_record, history_to_records
from .run_store import (
    V5_POLICY_IDENTITY_KEYS,
    parse_action_qbc_candidate_rows_json,
    validate_action_qbc_attribution,
    validate_v5_policy_identity,
)
from .types import Budget, Decision, DecisionMode, GameState, History, Observation


class ActingController(Protocol):
    @property
    def pool(self) -> object | None: ...

    def act(self, observation: Observation, budget: Budget) -> Decision: ...


def run_game(
    session: EnvironmentSession,
    controller: ActingController,
    *,
    run_id: str,
    seed: int,
    variant: str,
    model_profile: str,
    config_hash: str,
    model_revision: str | None = None,
    weight_manifest_sha256: str | None = None,
    hypothesis_source: str,
    arm_label: str,
    identity_version: str,
    producer_contract_sha256: str | None,
    implementation_contract_version: str | None = None,
    completion_cost_policy_version: str | None = None,
    completion_cost_policy_sha256: str | None = None,
    probe_disagreement_policy_version: str | None = None,
    probe_disagreement_policy_sha256: str | None = None,
    outcome_concentration_threshold: float | None = None,
    max_environment_actions: int = 256,
    max_generated_tokens: int = 12_288,
    max_wall_seconds: float = 1_200.0,
    baseline_actions: tuple[int, ...] | None = None,
) -> RunMetrics:
    metrics = RunMetrics(
        run_id,
        session.game_id,
        seed,
        variant,
        model_profile,
        config_hash,
        model_revision=model_revision,
        weight_manifest_sha256=weight_manifest_sha256,
        hypothesis_source=hypothesis_source,
        arm_label=arm_label,
        identity_version=identity_version,
        producer_contract_sha256=producer_contract_sha256,
        implementation_contract_version=implementation_contract_version,
        completion_cost_policy_version=completion_cost_policy_version,
        completion_cost_policy_sha256=completion_cost_policy_sha256,
        probe_disagreement_policy_version=probe_disagreement_policy_version,
        probe_disagreement_policy_sha256=probe_disagreement_policy_sha256,
        outcome_concentration_threshold=outcome_concentration_threshold,
        controller_decision_seconds=0.0,
        environment_step_seconds=0.0,
    )
    budget = Budget(
        max_environment_actions=max_environment_actions,
        max_generated_tokens=max_generated_tokens,
        max_wall_seconds=max_wall_seconds,
    )
    vram_backend = _start_vram_tracking()
    observation = session.initial_observation()
    trace_history = History.from_observation(observation)
    metrics.win_levels = observation.win_levels
    current_level = observation.level
    actions_in_level = 0
    started = time.perf_counter()

    try:
        while observation.game_state is not GameState.WIN:
            elapsed = time.perf_counter() - started
            budget = replace(budget, elapsed_seconds=min(elapsed, budget.max_wall_seconds))
            decision_started = time.perf_counter()
            decision = controller.act(observation, budget)
            decision_elapsed = time.perf_counter() - decision_started
            # act() first ingests the previous revealed observation.  Backfill
            # that transition before logging the new pre-action pool snapshot.
            _backfill_latest_transition(metrics, controller)
            generated_tokens = int(decision.diagnostics.get("generated_tokens", 0) or 0)
            (
                hypothesis_ids,
                hypothesis_weights,
                hypothesis_validity,
                valid_hypotheses,
            ) = _pool_snapshot(controller)
            _consume_decision_diagnostics(metrics, decision)
            persistence_estimate, persistence_successes, persistence_trials = (
                _persistence_snapshot(controller)
            )
            candidate_rows, post_refresh_mode = _v5_step_attribution(metrics, decision)
            environment_step_started = time.perf_counter()
            environment_diagnostics = {
                key: value
                for key, value in decision.diagnostics.items()
                if key != "generated_program_sources"
            }
            next_observation = session.step(
                decision.action,
                reasoning={
                    "mode": decision.mode.value,
                    "score": decision.score,
                    "diagnostics": environment_diagnostics,
                },
            )
            environment_step_elapsed = time.perf_counter() - environment_step_started
            budget = budget.consume(
                environment_actions=1,
                generated_tokens=generated_tokens,
                wall_seconds=min(environment_step_elapsed, budget.remaining_wall_seconds),
            )
            metrics.total_actions += 1
            metrics.generated_tokens += generated_tokens
            metrics.controller_decision_seconds = float(
                metrics.controller_decision_seconds or 0.0
            ) + decision_elapsed
            metrics.environment_step_seconds = float(
                metrics.environment_step_seconds or 0.0
            ) + environment_step_elapsed
            actions_in_level += 1
            level_delta = next_observation.level - observation.level
            metrics.steps.append(
                StepRecord(
                    step=metrics.total_actions,
                    level=current_level,
                    history=history_to_records(trace_history, win_levels=observation.win_levels),
                    action=action_to_record(decision.action),
                    available_actions=tuple(
                        action.name for action in sorted(observation.available_actions, key=int)
                    ),
                    decision_mode=decision.mode.value,
                    decision_score=decision.score,
                    decision_diagnostics=dict(decision.diagnostics),
                    probe_utility=_diagnostic_float(decision, "probe_utility"),
                    agreement=_diagnostic_float(decision, "agreement"),
                    generated_tokens=generated_tokens,
                    weighted_transition_loss=None,
                    best_hypothesis_transition_loss=None,
                    valid_hypotheses=valid_hypotheses,
                    hypothesis_ids=hypothesis_ids,
                    hypothesis_weights=hypothesis_weights,
                    hypothesis_validity=hypothesis_validity,
                    invalidated_hypotheses=(),
                    timeout_hypotheses=(),
                    persistence_estimate=persistence_estimate,
                    persistence_successes=persistence_successes,
                    persistence_trials=persistence_trials,
                    boundary_survival=None,
                    fallback=decision.mode is DecisionMode.DIRECT_FALLBACK,
                    # Retain the legacy alias while emitting explicit latency
                    # components for all newly written traces.
                    elapsed_seconds=environment_step_elapsed,
                    observed_grid=next_observation.grid.tolist(),
                    observed_available_actions=tuple(
                        action.name
                        for action in sorted(next_observation.available_actions, key=int)
                    ),
                    observed_state=next_observation.game_state.value,
                    observed_level=next_observation.level,
                    observed_win_levels=next_observation.win_levels,
                    observed_level_delta=level_delta,
                    controller_decision_seconds=decision_elapsed,
                    environment_step_seconds=environment_step_elapsed,
                    implementation_contract_version=(
                        metrics.implementation_contract_version
                    ),
                    completion_cost_policy_version=(
                        metrics.completion_cost_policy_version
                    ),
                    completion_cost_policy_sha256=(
                        metrics.completion_cost_policy_sha256
                    ),
                    probe_disagreement_policy_version=(
                        metrics.probe_disagreement_policy_version
                    ),
                    probe_disagreement_policy_sha256=(
                        metrics.probe_disagreement_policy_sha256
                    ),
                    outcome_concentration_threshold=(
                        metrics.outcome_concentration_threshold
                    ),
                    action_qbc_candidate_rows=candidate_rows,
                    post_refresh_mode=post_refresh_mode,
                )
            )
            metrics.direct_fallbacks += decision.mode is DecisionMode.DIRECT_FALLBACK

            advanced = next_observation.level > current_level
            won = next_observation.game_state is GameState.WIN
            if advanced or won:
                metrics.per_level_actions.append(actions_in_level)
                actions_in_level = 0
                current_level = next_observation.level
            metrics.levels_completed = max(
                metrics.levels_completed,
                next_observation.win_levels if won else next_observation.level - 1,
            )
            trace_history = trace_history.append(
                next_observation, decision.action, level_delta
            )
            observation = next_observation
            if won:
                # The main loop exits on WIN, so there is no next act() call to
                # ingest and score the final pre-action prediction.  Invoke the
                # controller's ingestion boundary without selecting another
                # environment action, then persist its loss in the final row.
                _ingest_terminal_observation(controller, next_observation)
                _backfill_latest_transition(metrics, controller)
        metrics.termination_reason = "win"
    except ControllerBudgetExhausted:
        metrics.termination_reason = "budget_exhausted"
    except EpisodeComplete:
        metrics.termination_reason = "episode_complete"
    except ValueError as exc:
        metrics.error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # environment/runtime failure remains in the artifact
        metrics.error = f"{type(exc).__name__}: {exc}"
    finally:
        _backfill_latest_transition(metrics, controller)
        metrics.wall_seconds = time.perf_counter() - started
        measured_peak = _peak_vram_gb(vram_backend)
        if measured_peak is not None:
            metrics.peak_vram_gb = max(metrics.peak_vram_gb or 0.0, measured_peak)
        metrics.finalize(baseline_actions)
    return metrics


def _ingest_terminal_observation(
    controller: ActingController, observation: Observation
) -> None:
    ingest = getattr(controller, "_ingest", None)
    if callable(ingest):
        ingest(observation)


def _backfill_latest_transition(metrics: RunMetrics, controller: ActingController) -> None:
    if not metrics.steps:
        return
    previous = metrics.steps[-1]
    # A non-None loss is the normal scored marker.  Direct mode has no pool, so
    # observed_state plus an empty hypothesis set is necessarily already final;
    # repeated calls are harmless because all event counters are derived below
    # only when the immutable row changes.
    if previous.weighted_transition_loss is not None:
        return

    pool = getattr(controller, "pool", None)
    losses = getattr(pool, "recent_weighted_losses", ()) if pool is not None else ()
    weighted_loss = float(losses[-1]) if losses else None
    entries = tuple(getattr(pool, "entries", ())) if pool is not None else ()
    prior_validity = dict(
        zip(previous.hypothesis_ids, previous.hypothesis_validity, strict=True)
    )
    prior_ids = set(prior_validity)
    relevant_entries = [
        entry for entry in entries if getattr(entry, "hypothesis_id", None) in prior_ids
    ]
    latest_losses = [
        float(entry.latest_loss)
        for entry in relevant_entries
        if getattr(entry, "latest_loss", None) is not None
        and bool(getattr(entry, "valid", False))
    ]
    invalidated = tuple(
        str(entry.hypothesis_id)
        for entry in relevant_entries
        if prior_validity[str(entry.hypothesis_id)]
        and not bool(getattr(entry, "valid", True))
    )
    timed_out = tuple(
        str(entry.hypothesis_id)
        for entry in relevant_entries
        if prior_validity[str(entry.hypothesis_id)]
        and not bool(getattr(entry, "valid", True))
        and _entry_timed_out(entry)
    )

    _estimate, successes, trials = _persistence_snapshot(controller)
    boundary_survival: bool | None = None
    if (
        previous.persistence_trials is not None
        and previous.persistence_successes is not None
        and trials is not None
        and successes is not None
        and trials > previous.persistence_trials
    ):
        boundary_survival = successes > previous.persistence_successes

    updated = replace(
        previous,
        weighted_transition_loss=weighted_loss,
        best_hypothesis_transition_loss=min(latest_losses) if latest_losses else None,
        invalidated_hypotheses=invalidated,
        timeout_hypotheses=timed_out,
        boundary_survival=boundary_survival,
    )
    if updated != previous:
        metrics.invalid_programs += len(invalidated)
        if boundary_survival is not None:
            metrics.boundary_survival_trials += 1
            metrics.boundary_survival_successes += int(boundary_survival)
        metrics.steps[-1] = updated


def _entry_timed_out(entry: object) -> bool:
    """Classify a retained worker timeout without serializing private errors."""

    hypothesis = getattr(entry, "hypothesis", None)
    worker = getattr(hypothesis, "_worker", None)
    error = getattr(worker, "_terminal_error", None)
    kind = str(getattr(error, "kind", "")).lower()
    message = str(getattr(error, "message", "")).lower()
    return "timeout" in kind or "timeout" in message


def _pool_snapshot(
    controller: ActingController,
) -> tuple[tuple[str, ...], tuple[float, ...], tuple[bool, ...], int]:
    pool = getattr(controller, "pool", None)
    if pool is None:
        return (), (), (), 0
    entries = tuple(getattr(pool, "entries", ()))
    weights = tuple(float(value) for value in getattr(pool, "weights", ()))
    ids = tuple(str(entry.hypothesis_id) for entry in entries)
    validity = tuple(bool(getattr(entry, "valid", False)) for entry in entries)
    return ids, weights, validity, sum(validity)


def _consume_decision_diagnostics(metrics: RunMetrics, decision: Decision) -> None:
    """Merge per-decision deltas and monotone controller telemetry exactly once."""

    invalid = _diagnostic_int(decision, "invalid_programs")
    if invalid is not None:
        metrics.invalid_programs += invalid
    peak = _diagnostic_float(decision, "peak_vram_gb")
    if peak is not None:
        metrics.peak_vram_gb = max(metrics.peak_vram_gb or 0.0, peak)

    prediction_calls = _diagnostic_int(decision, "program_prediction_calls")
    if prediction_calls is not None:
        metrics.program_prediction_calls = max(
            metrics.program_prediction_calls or 0, prediction_calls
        )
    goal_calls = _diagnostic_int(decision, "program_goal_calls")
    if goal_calls is not None:
        metrics.program_goal_calls = max(metrics.program_goal_calls or 0, goal_calls)
    timeouts = _diagnostic_int(decision, "program_timeouts")
    if timeouts is not None:
        metrics.program_timeouts = max(metrics.program_timeouts, timeouts)
    execution_errors = _diagnostic_int(decision, "program_execution_errors")
    if execution_errors is not None:
        metrics.program_execution_errors = max(
            metrics.program_execution_errors, execution_errors
        )
    complete = decision.diagnostics.get("timeout_instrumentation_complete")
    if isinstance(complete, bool):
        metrics.timeout_instrumentation_complete = (
            metrics.timeout_instrumentation_complete or complete
        )


def _v5_step_attribution(
    metrics: RunMetrics, decision: Decision
) -> tuple[tuple[dict[str, Any], ...] | None, str | None]:
    expected = {
        key: getattr(metrics, key)
        for key in V5_POLICY_IDENTITY_KEYS
        if getattr(metrics, key) is not None
    }
    expected_is_v5 = validate_v5_policy_identity(
        expected, context="runner policy identity"
    )
    observed = {
        key: decision.diagnostics[key]
        for key in V5_POLICY_IDENTITY_KEYS
        if key in decision.diagnostics
    }
    observed_is_v5 = validate_v5_policy_identity(
        observed, context="decision diagnostics"
    )
    if expected_is_v5 != observed_is_v5 or (
        expected_is_v5
        and tuple(expected[key] for key in V5_POLICY_IDENTITY_KEYS)
        != tuple(observed[key] for key in V5_POLICY_IDENTITY_KEYS)
    ):
        raise ValueError("summary and decision runtime-v5 identities do not match")
    if not expected_is_v5:
        return None, None

    post_refresh_mode = decision.diagnostics.get("post_refresh_mode")
    raw_rows = decision.diagnostics.get("action_qbc_candidate_rows")
    structured_rows = (
        None
        if raw_rows is None
        else parse_action_qbc_candidate_rows_json(
            raw_rows, context="runtime-v5 decision diagnostics"
        )
    )
    candidate_rows = validate_action_qbc_attribution(
        structured_rows,
        variant=metrics.variant,
        decision_mode=decision.mode.value,
        decision_score=decision.score,
        post_refresh_mode=post_refresh_mode,
        action=action_to_record(decision.action),
        decision_diagnostics=decision.diagnostics,
        context="runtime-v5 decision diagnostics",
    )
    return candidate_rows, (
        str(post_refresh_mode) if post_refresh_mode is not None else None
    )


def _persistence_snapshot(
    controller: ActingController,
) -> tuple[float | None, int | None, int | None]:
    persistence = getattr(controller, "persistence", None)
    if persistence is None:
        return None, None, None
    try:
        return (
            float(persistence.estimate),
            int(persistence.successes),
            int(persistence.trials),
        )
    except (AttributeError, TypeError, ValueError):
        return None, None, None


def _diagnostic_float(decision: Decision, key: str) -> float | None:
    value = decision.diagnostics.get(key)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _diagnostic_int(decision: Decision, key: str) -> int | None:
    value = decision.diagnostics.get(key)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _start_vram_tracking() -> Any | None:
    try:
        torch = importlib.import_module("torch")
        if bool(torch.cuda.is_available()):
            torch.cuda.reset_peak_memory_stats()
            return torch
    except (ImportError, RuntimeError, AttributeError):
        pass
    return None


def _peak_vram_gb(torch: Any | None) -> float | None:
    if torch is None:
        return None
    try:
        return float(torch.cuda.max_memory_allocated()) / (1024**3)
    except (RuntimeError, AttributeError):
        return None
