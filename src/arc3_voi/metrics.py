"""Official-score-compatible metrics, trace records, and preregistered gates."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, cast

from .config import HypothesisSource
from .experiment import GateResult, ScoreGateInput, arm_label_for, evaluate_score_gate
from .experiment import Variant as ExperimentVariant
from .run_store import TRACE_ARTIFACT_KEY, publish_run_artifacts, read_complete_run
from .statistics import (
    PairedSummary,
    ScoreObservation,
    paired_seed_deltas,
    summarize_paired_observations,
)


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One action and its fully replayable pre-action and resulting observations."""

    step: int
    level: int
    history: tuple[dict[str, Any], ...]
    action: dict[str, Any]
    available_actions: tuple[str, ...]
    decision_mode: str
    decision_score: float
    decision_diagnostics: dict[str, Any]
    probe_utility: float | None
    agreement: float | None
    generated_tokens: int
    weighted_transition_loss: float | None
    best_hypothesis_transition_loss: float | None
    valid_hypotheses: int
    hypothesis_ids: tuple[str, ...]
    hypothesis_weights: tuple[float, ...]
    hypothesis_validity: tuple[bool, ...]
    invalidated_hypotheses: tuple[str, ...]
    timeout_hypotheses: tuple[str, ...]
    persistence_estimate: float | None
    persistence_successes: int | None
    persistence_trials: int | None
    boundary_survival: bool | None
    fallback: bool
    elapsed_seconds: float
    observed_grid: list[list[int]]
    observed_available_actions: tuple[str, ...]
    observed_state: str
    observed_level: int
    observed_win_levels: int
    observed_level_delta: int
    # Added as optional trailing fields so schema-v1 traces remain loadable.
    # ``elapsed_seconds`` retains its legacy environment-step meaning.
    controller_decision_seconds: float | None = None
    environment_step_seconds: float | None = None


@dataclass(slots=True)
class RunMetrics:
    run_id: str
    game_id: str
    seed: int
    variant: str
    model_profile: str
    config_hash: str
    hypothesis_source: str
    arm_label: str | None
    identity_version: str
    producer_contract_sha256: str | None
    model_revision: str | None = None
    weight_manifest_sha256: str | None = None
    levels_completed: int = 0
    win_levels: int = 0
    total_actions: int = 0
    generated_tokens: int = 0
    wall_seconds: float = 0.0
    controller_decision_seconds: float | None = None
    environment_step_seconds: float | None = None
    peak_vram_gb: float | None = None
    invalid_programs: int = 0
    program_timeouts: int = 0
    # The current controller exposes invalid pool entries but not every nested
    # beam-search worker invocation.  Keep this flag false unless an execution
    # backend supplies exact call counters; gates then fail closed rather than
    # interpreting an unobserved timeout count as zero.
    timeout_instrumentation_complete: bool = False
    program_prediction_calls: int | None = None
    program_goal_calls: int | None = None
    program_execution_errors: int = 0
    direct_fallbacks: int = 0
    boundary_survival_successes: int = 0
    boundary_survival_trials: int = 0
    decision_points: int = 0
    two_valid_decision_points: int = 0
    mean_weighted_transition_loss: float | None = None
    mean_best_hypothesis_transition_loss: float | None = None
    per_level_actions: list[int] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)
    rhae: float | None = None
    termination_reason: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.variant not in {"D", "S", "M", "X"}:
            raise ValueError("invalid controller variant in run identity")
        if self.hypothesis_source not in {
            "qwen",
            "template_v1",
            "qwen_then_template_v1",
        }:
            raise ValueError("invalid hypothesis source in run identity")
        expected_arm = arm_label_for(
            cast(ExperimentVariant, self.variant),
            cast(HypothesisSource, self.hypothesis_source),
        )
        if self.arm_label is None:
            if self.identity_version == "source-v2":
                raise ValueError("source-v2 run identity requires an explicit arm_label")
            self.arm_label = expected_arm
        elif self.arm_label != expected_arm:
            raise ValueError(
                f"arm {self.arm_label} is inconsistent with variant {self.variant} "
                f"and source {self.hypothesis_source}"
            )
        if self.identity_version not in {"legacy-v1", "source-v2"}:
            raise ValueError("invalid run identity version")
        if self.identity_version == "legacy-v1" and self.hypothesis_source != "qwen":
            raise ValueError("legacy-v1 run identity is valid only for Qwen")
        if self.identity_version == "legacy-v1" and self.producer_contract_sha256 is not None:
            raise ValueError("legacy-v1 run identity cannot carry a producer contract")
        if self.producer_contract_sha256 is None:
            if self.identity_version != "legacy-v1":
                raise ValueError(
                    "producer_contract_sha256 is required for source-v2 run identity"
                )
        elif not _is_sha256(self.producer_contract_sha256):
            raise ValueError("producer_contract_sha256 must be a lowercase SHA-256 digest")

    def finalize(self, baseline_actions: list[int] | tuple[int, ...] | None = None) -> None:
        self.decision_points = len(self.steps)
        self.two_valid_decision_points = sum(
            step.valid_hypotheses >= 2 for step in self.steps
        )
        weighted_losses = [
            step.weighted_transition_loss
            for step in self.steps
            if step.weighted_transition_loss is not None
        ]
        best_losses = [
            step.best_hypothesis_transition_loss
            for step in self.steps
            if step.best_hypothesis_transition_loss is not None
        ]
        self.mean_weighted_transition_loss = (
            mean(weighted_losses) if weighted_losses else None
        )
        self.mean_best_hypothesis_transition_loss = (
            mean(best_losses) if best_losses else None
        )
        if baseline_actions and self.win_levels:
            self.rhae = game_rhae(
                baseline_actions,
                self.per_level_actions,
                total_levels=self.win_levels,
            )

    def summary(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("steps")
        return value


def level_rhae(human_actions: int, agent_actions: int) -> float:
    if human_actions <= 0:
        raise ValueError("human action baseline must be positive")
    if agent_actions <= 0:
        raise ValueError("agent actions must be positive for a completed level")
    return min(1.15, (human_actions / agent_actions) ** 2)


def game_rhae(
    human_baselines: list[int] | tuple[int, ...],
    completed_level_actions: list[int] | tuple[int, ...],
    *,
    total_levels: int | None = None,
) -> float:
    """Return official weighted RHAE, including the completion-fraction ceiling."""

    total = total_levels or len(human_baselines)
    if total <= 0:
        raise ValueError("total_levels must be positive")
    if len(human_baselines) < min(total, len(completed_level_actions)):
        raise ValueError("missing human baseline for a completed level")
    denominator = total * (total + 1) / 2
    weighted = 0.0
    completed = completed_level_actions[:total]
    for index, actions in enumerate(completed, start=1):
        weighted += index * level_rhae(int(human_baselines[index - 1]), int(actions))
    # The official methodology caps a game by its weighted completed-level
    # fraction.  Thus even a per-level 1.15 shortcut bonus cannot raise a
    # partially or fully completed game above its completion ceiling.
    completion_ceiling = sum(range(1, len(completed) + 1)) / denominator
    return min(weighted / denominator, completion_ceiling)


def write_run(metrics: RunMetrics, directory: str | Path) -> tuple[Path, Path]:
    return publish_run_artifacts(
        metrics.summary(),
        tuple(asdict(record) for record in metrics.steps),
        directory,
    )


def load_run(summary_path: str | Path, trace_path: str | Path | None = None) -> RunMetrics:
    """Load a summary and its detailed trace back into the gate-analysis model."""

    summary_source = Path(summary_path)
    source = Path(trace_path) if trace_path is not None else summary_source.with_suffix(".jsonl")
    records: tuple[dict[str, Any], ...] = ()
    if source.exists():
        artifacts = read_complete_run(summary_source, source)
        if artifacts is None:
            raise ValueError("run summary and trace are incomplete or inconsistent")
        payload, records = artifacts
        payload = dict(payload)
    else:
        payload = json.loads(summary_source.read_text(encoding="utf-8"))
        if TRACE_ARTIFACT_KEY in payload:
            raise ValueError("run summary and trace are incomplete or inconsistent")
    payload.pop(TRACE_ARTIFACT_KEY, None)
    source_identity_keys = {
        "hypothesis_source",
        "arm_label",
        "identity_version",
        "producer_contract_sha256",
    }
    present_identity_keys = source_identity_keys.intersection(payload)
    if not present_identity_keys:
        # Historical summaries predate explicit producer identity. They are
        # defensibly interpretable only as implicit-Qwen legacy evidence.
        payload.update(
            {
                "hypothesis_source": "qwen",
                "arm_label": None,
                "identity_version": "legacy-v1",
                "producer_contract_sha256": None,
            }
        )
    elif present_identity_keys != source_identity_keys:
        missing = ", ".join(sorted(source_identity_keys - present_identity_keys))
        raise ValueError(f"run summary has incomplete source identity: {missing}")
    metrics = RunMetrics(**payload)
    for record in records:
        value = dict(record)
        for key in (
            "history",
            "available_actions",
            "hypothesis_ids",
            "hypothesis_weights",
            "hypothesis_validity",
            "invalidated_hypotheses",
            "timeout_hypotheses",
            "observed_available_actions",
        ):
            value[key] = tuple(value[key])
        # Legacy schema-v1 rows recorded only ``elapsed_seconds``, whose
        # historical meaning was the environment/session step duration.
        value.setdefault("controller_decision_seconds", None)
        value.setdefault("environment_step_seconds", value["elapsed_seconds"])
        metrics.steps.append(StepRecord(**value))
    return metrics


@dataclass(frozen=True, slots=True)
class MechanismGateAnalysis:
    passed: bool
    reasons: tuple[str, ...]
    decision_points: int
    two_valid_fraction: float
    timeout_rate: float | None
    committee_best_loss: float | None
    single_program_loss: float | None
    relative_loss_improvement: float | None


def evaluate_mechanism_gate(
    committee_runs: Iterable[RunMetrics],
    single_runs: Iterable[RunMetrics],
) -> MechanismGateAnalysis:
    """Evaluate the mechanism gate from recorded decision-level evidence.

    Timeout evidence deliberately fails closed when the controller/backend did
    not expose exact prediction-call counters.
    """

    committee = tuple(committee_runs)
    single = tuple(single_runs)
    _validate_analysis_cohort((*committee, *single))
    committee_steps = tuple(step for run in committee for step in run.steps)
    single_steps = tuple(step for run in single for step in run.steps)
    decisions = len(committee_steps)
    two_valid_fraction = (
        sum(step.valid_hypotheses >= 2 for step in committee_steps) / decisions
        if decisions
        else 0.0
    )

    complete_timeout_data = bool(committee) and all(
        run.timeout_instrumentation_complete
        and run.program_prediction_calls is not None
        and run.program_goal_calls is not None
        for run in committee
    )
    program_calls = (
        sum(
            int(run.program_prediction_calls or 0) + int(run.program_goal_calls or 0)
            for run in committee
        )
        if complete_timeout_data
        else 0
    )
    timeout_rate = (
        sum(run.program_timeouts for run in committee) / program_calls
        if complete_timeout_data and program_calls > 0
        else None
    )
    committee_losses = [
        step.best_hypothesis_transition_loss
        for step in committee_steps
        if step.best_hypothesis_transition_loss is not None
    ]
    single_losses = [
        step.weighted_transition_loss
        for step in single_steps
        if step.weighted_transition_loss is not None
    ]
    committee_loss = mean(committee_losses) if committee_losses else None
    single_loss = mean(single_losses) if single_losses else None
    relative_improvement = (
        (single_loss - committee_loss) / single_loss
        if single_loss is not None and single_loss > 0 and committee_loss is not None
        else None
    )

    reasons: list[str] = []
    if decisions == 0:
        reasons.append("no committee decision points were recorded")
    elif two_valid_fraction < 0.80:
        reasons.append("fewer than two valid distinct programs at 80% of decisions")
    if timeout_rate is None:
        reasons.append("exact program timeout instrumentation is unavailable")
    elif timeout_rate >= 0.01:
        reasons.append("program timeout rate is not below 1%")
    if relative_improvement is None:
        reasons.append("committee and single-program prequential losses are incomplete")
    elif relative_improvement < 0.15:
        reasons.append("best-committee prequential loss is not 15% below S")
    return MechanismGateAnalysis(
        passed=not reasons,
        reasons=tuple(reasons),
        decision_points=decisions,
        two_valid_fraction=two_valid_fraction,
        timeout_rate=timeout_rate,
        committee_best_loss=committee_loss,
        single_program_loss=single_loss,
        relative_loss_improvement=relative_improvement,
    )


@dataclass(frozen=True, slots=True)
class DevelopmentGateAnalysis:
    gate: GateResult
    game_deltas: Mapping[str, float]
    x_mean_rhae: float
    m_mean_rhae: float


def evaluate_development_score_gate(
    runs: Iterable[RunMetrics],
    *,
    hypothesis_source: str | None = None,
    treatment_arm: str | None = None,
    comparator_arm: str | None = None,
) -> DevelopmentGateAnalysis:
    """Average seeds within games and evaluate the preregistered X-versus-M gate."""

    rows = _exact_comparison_runs(
        tuple(runs),
        treatment_variant="X",
        comparator_variant="M",
        hypothesis_source=hypothesis_source,
        treatment_arm=treatment_arm,
        comparator_arm=comparator_arm,
    )
    paired_seed_deltas(
        (
            ScoreObservation(run.game_id, run.seed, run.variant, float(run.rhae))
            for run in rows
            if run.variant in {"X", "M"} and run.rhae is not None
        ),
        "X",
        "M",
    )
    grouped = _complete_game_variant_runs(rows, variants=("X", "M"))
    games = sorted({game for game, variant in grouped if variant == "X"})
    if not games:
        raise ValueError("no complete paired X/M games with RHAE were recorded")
    game_rhae_means = {
        (game, variant): mean(run.rhae for run in grouped[(game, variant)] if run.rhae is not None)
        for game in games
        for variant in ("X", "M")
    }
    deltas = {game: game_rhae_means[(game, "X")] - game_rhae_means[(game, "M")] for game in games}

    def average_field(variant: str, field_name: str) -> float:
        per_game = [
            mean(float(getattr(run, field_name)) for run in grouped[(game, variant)])
            for game in games
        ]
        return mean(per_game)

    x_rhae = mean(game_rhae_means[(game, "X")] for game in games)
    m_rhae = mean(game_rhae_means[(game, "M")] for game in games)
    gate = evaluate_score_gate(
        ScoreGateInput(
            x_rhae=x_rhae,
            m_rhae=m_rhae,
            x_levels=average_field("X", "levels_completed"),  # type: ignore[arg-type]
            m_levels=average_field("M", "levels_completed"),  # type: ignore[arg-type]
            x_actions=average_field("X", "total_actions"),  # type: ignore[arg-type]
            m_actions=average_field("M", "total_actions"),  # type: ignore[arg-type]
            positive_game_fraction=sum(value > 0 for value in deltas.values()) / len(deltas),
            x_wall_seconds=average_field("X", "wall_seconds"),
            m_wall_seconds=average_field("M", "wall_seconds"),
        )
    )
    return DevelopmentGateAnalysis(gate, deltas, x_rhae, m_rhae)


@dataclass(frozen=True, slots=True)
class ConfirmationGateAnalysis:
    passed: bool
    reasons: tuple[str, ...]
    comparator: str
    summary: PairedSummary


def evaluate_confirmation_gate(
    runs: Iterable[RunMetrics],
    *,
    comparator: str,
    bootstrap_samples: int = 20_000,
    hypothesis_source: str | None = None,
    treatment_arm: str | None = None,
    comparator_arm: str | None = None,
) -> ConfirmationGateAnalysis:
    """Evaluate the locked 10-game claim gate after averaging seeds per game."""

    if comparator == "X":
        raise ValueError("confirmation comparator must differ from X")
    rows = _exact_comparison_runs(
        tuple(runs),
        treatment_variant="X",
        comparator_variant=comparator,
        hypothesis_source=hypothesis_source,
        treatment_arm=treatment_arm,
        comparator_arm=comparator_arm,
    )
    observations = [
        ScoreObservation(run.game_id, run.seed, run.variant, float(run.rhae))
        for run in rows
        if run.variant in {"X", comparator} and run.rhae is not None
    ]
    summary = summarize_paired_observations(
        observations,
        "X",
        comparator,
        bootstrap_samples=bootstrap_samples,
    )
    reasons: list[str] = []
    if summary.games != 10:
        reasons.append("confirmation requires exactly 10 complete paired games")
    if summary.wins < 6:
        reasons.append("X wins fewer than 6 of 10 games")
    if summary.probability_positive < 0.90:
        reasons.append("bootstrap probability of a positive mean is below 0.90")
    return ConfirmationGateAnalysis(not reasons, tuple(reasons), comparator, summary)


def _complete_game_variant_runs(
    runs: Iterable[RunMetrics], *, variants: tuple[str, str]
) -> dict[tuple[str, str], list[RunMetrics]]:
    grouped: dict[tuple[str, str], list[RunMetrics]] = defaultdict(list)
    for run in runs:
        if run.variant in variants and run.rhae is not None:
            grouped[(run.game_id, run.variant)].append(run)
    complete = {
        game
        for game, variant in grouped
        if variant == variants[0] and (game, variants[1]) in grouped
    }
    return {key: value for key, value in grouped.items() if key[0] in complete}


def _exact_comparison_runs(
    runs: tuple[RunMetrics, ...],
    *,
    treatment_variant: str,
    comparator_variant: str,
    hypothesis_source: str | None,
    treatment_arm: str | None,
    comparator_arm: str | None,
) -> tuple[RunMetrics, ...]:
    """Select one exact arm/source contrast and reject ambiguous mixed-source input."""

    relevant = tuple(
        run
        for run in runs
        if run.variant in {treatment_variant, comparator_variant} and run.rhae is not None
    )
    if not relevant:
        return ()
    if treatment_variant not in {"D", "S", "M", "X"} or comparator_variant not in {
        "D",
        "S",
        "M",
        "X",
    }:
        raise ValueError("invalid controller variant for analysis")
    observed_sources = {run.hypothesis_source for run in relevant}
    if hypothesis_source is None:
        if len(observed_sources) != 1:
            raise ValueError(
                "analysis input mixes hypothesis sources; select one exact source and arm pair"
            )
        source = next(iter(observed_sources))
    else:
        source = hypothesis_source
        if source not in {"qwen", "template_v1", "qwen_then_template_v1"}:
            raise ValueError("invalid hypothesis source for analysis")
    try:
        expected_treatment_arm = arm_label_for(
            cast(ExperimentVariant, treatment_variant), cast(HypothesisSource, source)
        )
        expected_comparator_arm = arm_label_for(
            cast(ExperimentVariant, comparator_variant), cast(HypothesisSource, source)
        )
    except ValueError as exc:
        raise ValueError("controller variants do not define a same-source comparison") from exc
    selected_treatment_arm = treatment_arm or expected_treatment_arm
    selected_comparator_arm = comparator_arm or expected_comparator_arm
    if selected_treatment_arm != expected_treatment_arm:
        raise ValueError("treatment arm is inconsistent with treatment variant and source")
    if selected_comparator_arm != expected_comparator_arm:
        raise ValueError("comparator arm is inconsistent with comparator variant and source")
    selected = tuple(
        run
        for run in relevant
        if run.hypothesis_source == source
        and (
            (run.variant == treatment_variant and run.arm_label == selected_treatment_arm)
            or (run.variant == comparator_variant and run.arm_label == selected_comparator_arm)
        )
    )
    producer_identities = {
        (run.identity_version, run.producer_contract_sha256) for run in selected
    }
    if len(producer_identities) > 1:
        raise ValueError(
            "analysis input mixes legacy/current or distinct producer contract identities"
        )
    _validate_analysis_cohort(selected)
    return selected


def _validate_analysis_cohort(runs: tuple[RunMetrics, ...]) -> None:
    """Reject source, producer, model, or per-arm contract pooling."""

    if not runs:
        return
    if len({run.hypothesis_source for run in runs}) != 1:
        raise ValueError("analysis input mixes hypothesis sources")
    if len({(run.identity_version, run.producer_contract_sha256) for run in runs}) != 1:
        raise ValueError(
            "analysis input mixes legacy/current or distinct producer contract identities"
        )
    if len({run.model_profile for run in runs}) != 1:
        raise ValueError("analysis input mixes model profiles")
    config_hashes_by_arm: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        assert run.arm_label is not None
        config_hashes_by_arm[run.arm_label].add(run.config_hash)
    if any(len(hashes) != 1 for hashes in config_hashes_by_arm.values()):
        raise ValueError("analysis input mixes config hashes within an arm")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
