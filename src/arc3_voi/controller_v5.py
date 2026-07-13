"""Dormant runtime-v5 controller using the shared action-QBC pure selector.

The historical controller remains unchanged.  This subclass reuses its ingestion,
refresh, fallback, planning, persistence, and budget lifecycle, then replaces only
successful M/X committee selection with the content-addressed v5 policy.  It is
not wired into any shipped live composition root.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    OUTCOME_CONCENTRATION_THRESHOLD,
    ActionQBCRow,
    ActionQBCSelection,
    VariantPolicyDecision,
    select_action_conditional_qbc,
)
from .candidates import Point
from .controller import (
    Controller,
    ControllerBudgetExhausted,
    ControllerConfig,
    DirectPolicy,
    RefreshCallback,
    TelemetryCallback,
    Variant,
)
from .hypothesis import CrossLevelPersistence, Hypothesis, HypothesisPool
from .planner import (
    COMPLETION_COST_POLICY_HASHES,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
    BeamSearchPlanner,
    PlanningSnapshot,
)
from .types import (
    Action,
    Budget,
    Decision,
    DecisionMode,
    DiagnosticValue,
    History,
    Observation,
)


class _PlannerProtocol(Protocol):
    @property
    def completion_cost_policy(self) -> str: ...

    @property
    def completion_cost_policy_sha256(self) -> str: ...

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot: ...


class _SnapshotCapturingPlanner(BeamSearchPlanner):
    """Capture the exact snapshot returned to the unchanged controller lifecycle."""

    def __init__(
        self,
        delegate: _PlannerProtocol,
        *,
        depth: int,
        beam_width: int,
    ) -> None:
        super().__init__(
            depth=depth,
            beam_width=beam_width,
            completion_cost_policy=PATH_DEFICIT_COMPLETION_COST_POLICY,
        )
        self.delegate = delegate
        self.latest_snapshot: PlanningSnapshot | None = None

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        snapshot = self.delegate.evaluate(
            history,
            actions,
            weighted_hypotheses,
            win_levels=win_levels,
            deadline=deadline,
        )
        self.latest_snapshot = snapshot
        return snapshot

    def reset_capture(self) -> None:
        self.latest_snapshot = None


@dataclass(frozen=True, slots=True)
class V5ControllerConfig:
    """Exact dormant action-QBC controller contract."""

    variant: Variant = Variant.CROSS_LEVEL
    implementation_contract_version: str = ACTION_QBC_RUNTIME_VERSION
    max_candidates: int = 12
    depth: int = 4
    beam_width: int = 8
    max_probes_per_level: int = 3
    risk_coefficient: float = 3.0
    robust_std_coefficient: float = 0.5
    max_refreshes_per_level: int = 1
    max_generation_batches: int = 3
    completion_cost_policy_version: str = PATH_DEFICIT_COMPLETION_COST_POLICY
    completion_cost_policy_sha256: str = COMPLETION_COST_POLICY_HASHES[
        PATH_DEFICIT_COMPLETION_COST_POLICY
    ]
    probe_disagreement_policy_version: str = ACTION_QBC_POLICY_VERSION
    probe_disagreement_policy_sha256: str = ACTION_QBC_POLICY_SHA256
    outcome_concentration_threshold: float = OUTCOME_CONCENTRATION_THRESHOLD

    def __post_init__(self) -> None:
        object.__setattr__(self, "variant", Variant.coerce(self.variant))
        expected = {
            "implementation_contract_version": ACTION_QBC_RUNTIME_VERSION,
            "max_candidates": 12,
            "depth": 4,
            "beam_width": 8,
            "max_probes_per_level": 3,
            "risk_coefficient": 3.0,
            "robust_std_coefficient": 0.5,
            "max_refreshes_per_level": 1,
            "max_generation_batches": 3,
            "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
                PATH_DEFICIT_COMPLETION_COST_POLICY
            ],
            "probe_disagreement_policy_version": ACTION_QBC_POLICY_VERSION,
            "probe_disagreement_policy_sha256": ACTION_QBC_POLICY_SHA256,
            "outcome_concentration_threshold": OUTCOME_CONCENTRATION_THRESHOLD,
        }
        drift = [name for name, value in expected.items() if getattr(self, name) != value]
        if drift:
            raise ValueError("runtime-v5 controller contract drift: " + ", ".join(drift))


class V5Controller(Controller):
    """Dormant controller whose M/X selection is defined by one pure v5 call."""

    def __init__(
        self,
        *,
        direct_policy: DirectPolicy,
        pool: HypothesisPool | None = None,
        refresh_callback: RefreshCallback | None = None,
        config: V5ControllerConfig | None = None,
        persistence: CrossLevelPersistence | None = None,
        cached_points: Iterable[Point] = (),
        planner: _PlannerProtocol | None = None,
        telemetry_callback: TelemetryCallback | None = None,
    ) -> None:
        self.v5_config = config or V5ControllerConfig()
        delegate: _PlannerProtocol = planner or BeamSearchPlanner(
            depth=self.v5_config.depth,
            beam_width=self.v5_config.beam_width,
            completion_cost_policy=PATH_DEFICIT_COMPLETION_COST_POLICY,
        )
        if (
            delegate.completion_cost_policy != PATH_DEFICIT_COMPLETION_COST_POLICY
            or delegate.completion_cost_policy_sha256
            != self.v5_config.completion_cost_policy_sha256
        ):
            raise ValueError(
                "runtime-v5 planner delegate lacks the frozen path-deficit identity"
            )
        self._capturing_planner = _SnapshotCapturingPlanner(
            delegate,
            depth=self.v5_config.depth,
            beam_width=self.v5_config.beam_width,
        )
        super().__init__(
            direct_policy=direct_policy,
            pool=pool,
            refresh_callback=refresh_callback,
            config=ControllerConfig(
                variant=self.v5_config.variant,
                max_candidates=self.v5_config.max_candidates,
                depth=self.v5_config.depth,
                beam_width=self.v5_config.beam_width,
                agreement_threshold=0.8,
                max_probes_per_level=self.v5_config.max_probes_per_level,
                risk_coefficient=self.v5_config.risk_coefficient,
                robust_std_coefficient=self.v5_config.robust_std_coefficient,
                max_refreshes_per_level=self.v5_config.max_refreshes_per_level,
                max_generation_batches=self.v5_config.max_generation_batches,
                completion_cost_policy_version=PATH_DEFICIT_COMPLETION_COST_POLICY,
                completion_cost_policy_sha256=(
                    self.v5_config.completion_cost_policy_sha256
                ),
            ),
            persistence=persistence,
            cached_points=cached_points,
            planner=self._capturing_planner,
            telemetry_callback=telemetry_callback,
        )

    def act(self, observation: Observation, budget: Budget) -> Decision:
        deadline = time.monotonic() + budget.remaining_wall_seconds
        probes_before = self._probes_by_level.get(observation.level, 0)
        self._capturing_planner.reset_capture()
        historical = super().act(observation, budget)
        diagnostics = dict(historical.diagnostics)
        diagnostics.update(self._policy_identity_diagnostics())

        if (
            self.v5_config.variant not in (Variant.MYOPIC, Variant.CROSS_LEVEL)
            or historical.mode
            not in {DecisionMode.EXPLOIT, DecisionMode.PROBE, DecisionMode.REFRESH}
            or self._capturing_planner.latest_snapshot is None
        ):
            return Decision(
                historical.action,
                historical.mode,
                historical.score,
                diagnostics,
            )

        snapshot = self._capturing_planner.latest_snapshot
        cross_level_multiplier = self.persistence.multiplier(
            observation.level, observation.win_levels
        )
        selection = select_action_conditional_qbc(
            snapshot,
            cross_level_multiplier=cross_level_multiplier,
            probes_used=probes_before,
            probe_cap=self.v5_config.max_probes_per_level,
            outcome_concentration_threshold=(
                self.v5_config.outcome_concentration_threshold
            ),
            risk_coefficient=self.v5_config.risk_coefficient,
            robust_std_coefficient=self.v5_config.robust_std_coefficient,
        )
        authoritative = (
            selection.m_decision
            if self.v5_config.variant is Variant.MYOPIC
            else selection.x_decision
        )
        self._set_probe_count(
            observation.level,
            probes_before + (authoritative.mode == "probe"),
        )
        self._pending_action = authoritative.action
        self._pending_predictions = dict(
            zip(
                snapshot.hypothesis_ids,
                snapshot.predictions[authoritative.action],
                strict=True,
            )
        )
        diagnostics = self._v5_planning_diagnostics(
            diagnostics,
            selection,
            authoritative,
            probes_before=probes_before,
            cross_level_multiplier=cross_level_multiplier,
        )
        strategy_mode = (
            DecisionMode.PROBE
            if authoritative.mode == "probe"
            else DecisionMode.EXPLOIT
        )
        decision_mode = (
            DecisionMode.REFRESH
            if historical.mode is DecisionMode.REFRESH
            else strategy_mode
        )
        if decision_mode is DecisionMode.REFRESH:
            diagnostics["post_refresh_mode"] = strategy_mode.value
        else:
            diagnostics.pop("post_refresh_mode", None)
        if time.monotonic() >= deadline:
            raise ControllerBudgetExhausted(
                "wall-time budget expired during action-QBC selection"
            )
        return Decision(
            authoritative.action,
            decision_mode,
            authoritative.score,
            diagnostics,
        )

    def _policy_identity_diagnostics(self) -> dict[str, DiagnosticValue]:
        return {
            "implementation_contract_version": (
                self.v5_config.implementation_contract_version
            ),
            "completion_cost_policy_version": (
                self.v5_config.completion_cost_policy_version
            ),
            "completion_cost_policy_sha256": (
                self.v5_config.completion_cost_policy_sha256
            ),
            "probe_disagreement_policy_version": (
                self.v5_config.probe_disagreement_policy_version
            ),
            "probe_disagreement_policy_sha256": (
                self.v5_config.probe_disagreement_policy_sha256
            ),
            "outcome_concentration_threshold": (
                self.v5_config.outcome_concentration_threshold
            ),
        }

    def _v5_planning_diagnostics(
        self,
        diagnostics: dict[str, DiagnosticValue],
        selection: ActionQBCSelection,
        authoritative: VariantPolicyDecision,
        *,
        probes_before: int,
        cross_level_multiplier: float,
    ) -> dict[str, DiagnosticValue]:
        for historical_key in (
            "agreement_threshold",
            "probe_candidate_action",
            "probe_catastrophe_probability",
            "probe_evsi",
            "probe_gate_reason",
            "probe_selected",
            "probe_utility",
        ):
            diagnostics.pop(historical_key, None)
        rows_by_action = {row.action: row for row in selection.rows}
        probe_row = (
            None
            if authoritative.probe_candidate is None
            else rows_by_action[authoritative.probe_candidate]
        )
        actual_utility = (
            None
            if probe_row is None
            else (
                probe_row.m_utility
                if self.v5_config.variant is Variant.MYOPIC
                else probe_row.x_utility
            )
        )
        diagnostics.update(
            {
                "agreement": selection.historical_agreement,
                "committee_indifference": selection.historical_indifference,
                "level_multiplier": (
                    1.0
                    if self.v5_config.variant is Variant.MYOPIC
                    else cross_level_multiplier
                ),
                "m_level_multiplier": 1.0,
                "x_level_multiplier": cross_level_multiplier,
                "probe_evsi": None if probe_row is None else probe_row.evsi,
                "probe_catastrophe_probability": (
                    None if probe_row is None else probe_row.catastrophe_mass
                ),
                "probe_utility": actual_utility,
                "probe_candidate_action": (
                    None
                    if authoritative.probe_candidate is None
                    else self._action_key(authoritative.probe_candidate)
                ),
                "probe_count_before": probes_before,
                "probe_count_after": self._probes_by_level.get(
                    self.history.current_level, 0
                ),
                "probe_cap": self.v5_config.max_probes_per_level,
                "probe_gate_reason": authoritative.gate_reason,
                "probe_selected": authoritative.mode == "probe",
                "action_qbc_candidate_rows": self._serialize_candidate_rows(
                    selection.rows
                ),
                "m_utility_maximizer_actions": self._serialize_actions(
                    selection.m_utility_maximizers
                ),
                "x_utility_maximizer_actions": self._serialize_actions(
                    selection.x_utility_maximizers
                ),
                "m_decision_action": self._action_key(selection.m_decision.action),
                "m_decision_mode": selection.m_decision.mode,
                "x_decision_action": self._action_key(selection.x_decision.action),
                "x_decision_mode": selection.x_decision.mode,
                **self._policy_identity_diagnostics(),
            }
        )
        return diagnostics

    def _set_probe_count(self, level: int, count: int) -> None:
        if count:
            self._probes_by_level[level] = count
        else:
            self._probes_by_level.pop(level, None)

    @classmethod
    def _serialize_candidate_rows(cls, rows: Sequence[ActionQBCRow]) -> str:
        return json.dumps(
            [
                {
                    "action": cls._action_record(row.action),
                    "outcome_concentration": row.outcome_concentration,
                    "outcome_cell_count": row.outcome_cell_count,
                    "evsi": row.evsi,
                    "catastrophe_mass": row.catastrophe_mass,
                    "m_utility": row.m_utility,
                    "x_utility": row.x_utility,
                    "eligible": row.eligible,
                    "m_rank": row.m_rank,
                    "x_rank": row.x_rank,
                    "m_selected": row.m_selected,
                    "x_selected": row.x_selected,
                    "exploit_mean_cost": row.exploit_mean_cost,
                    "exploit_standard_deviation": (
                        row.exploit_standard_deviation
                    ),
                    "exploit_score": row.exploit_score,
                }
                for row in rows
            ],
            allow_nan=False,
            separators=(",", ":"),
        )

    @classmethod
    def _serialize_actions(cls, actions: Sequence[Action]) -> str:
        return json.dumps(
            [cls._action_record(action) for action in actions],
            separators=(",", ":"),
        )

    @staticmethod
    def _action_record(action: Action) -> dict[str, str | int | None]:
        return {
            "kind": action.kind.name,
            "row": action.row,
            "col": action.col,
        }


__all__ = ["V5Controller", "V5ControllerConfig"]
