"""Pure action-conditional exact-outcome QBC policy for dormant runtime-v5.

This module operates only on an already filtered :class:`PlanningSnapshot`.  It
does not construct candidates, run programs, or expose a live entrypoint.  The
same typed selector is intended for the dormant v5 controller and the later
separately authorized synthetic audit.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import fsum, isfinite
from types import MappingProxyType
from typing import Any, Final, Literal, TypeAlias, cast

from . import planner as _planner
from .planner import ExploitChoice, PlanningSnapshot, PredictionSignature
from .types import Action, GameState, Prediction, freeze_grid

ACTION_QBC_POLICY_VERSION: Final = "action-conditional-outcome-qbc-v1"
ACTION_QBC_RUNTIME_VERSION: Final = "crosslevel-voi-runtime-v5"
OUTCOME_CONCENTRATION_THRESHOLD: Final = 0.8
OUTCOME_CONCENTRATION_TOLERANCE: Final = 1e-12
ACTION_COST: Final = 1.0
RISK_COEFFICIENT: Final = 3.0
ROBUST_STD_COEFFICIENT: Final = 0.5
MAX_PROBES_PER_LEVEL: Final = 3

PolicyMode: TypeAlias = Literal["probe", "exploit"]  # noqa: UP040 - pinned mypy


ACTION_QBC_POLICY_CONTRACT: Final[Mapping[str, object]] = MappingProxyType({
    "action_cost": ACTION_COST,
    "candidate_order": (
        "stable ordinal ranks after sorting eligible actions by descending utility; "
        "original candidate index breaks exact ties"
    ),
    "catastrophe_mass": "frozen catastrophe_probability over the shared weights",
    "concentration": (
        "ordinary maximum of math.fsum exact-signature cell masses; reject outside "
        "[-1e-12,1+1e-12], otherwise clamp only boundary residue"
    ),
    "eligibility": "recorded_outcome_concentration < 0.8",
    "evsi": "frozen weighted_evsi including its <=1e-12 zero canonicalization",
    "exploit": "minimum weighted mean cost + 0.5 * weighted population std",
    "invalid_root_prediction": (
        "error: BeamSearchPlanner.evaluate must remove the hypothesis from the whole "
        "snapshot before policy evaluation"
    ),
    "m_utility": "EVSI - 1 - 3 * catastrophe_mass",
    "outcome_cell_serialization": "first exact-signature occurrence in committee order",
    "outcome_concentration_threshold": OUTCOME_CONCENTRATION_THRESHOLD,
    "policy_version": ACTION_QBC_POLICY_VERSION,
    "probe_cap": MAX_PROBES_PER_LEVEL,
    "probe_selection": "eligible maximum utility > 0; equality blocks",
    "risk_coefficient": RISK_COEFFICIENT,
    "runtime_version": ACTION_QBC_RUNTIME_VERSION,
    "signature": (
        "existing planner.prediction_signature wrapping Prediction.signature; program "
        "memory excluded"
    ),
    "weight_normalization": (
        "one shared nonnegative positive-mass vector normalized with math.fsum; no "
        "action-specific removal"
    ),
    "x_utility": "cross_level_multiplier * EVSI - 1 - 3 * catastrophe_mass",
})


@dataclass(frozen=True, slots=True)
class OutcomeCell:
    """One exact observable-signature cell in first-occurrence order."""

    signature: PredictionSignature
    hypothesis_indices: tuple[int, ...]
    mass: float


@dataclass(frozen=True, slots=True)
class ActionQBCRow:
    """All policy quantities for one candidate action on one shared snapshot."""

    action: Action
    outcome_concentration: float
    outcome_cell_count: int
    evsi: float
    catastrophe_mass: float
    m_utility: float
    x_utility: float
    eligible: bool
    m_rank: int | None
    x_rank: int | None
    m_selected: bool
    x_selected: bool
    exploit_mean_cost: float
    exploit_standard_deviation: float
    exploit_score: float


@dataclass(frozen=True, slots=True)
class VariantPolicyDecision:
    """One variant's authoritative probe-or-exploit decision."""

    action: Action
    mode: PolicyMode
    score: float
    gate_reason: str
    probe_candidate: Action | None


@dataclass(frozen=True, slots=True)
class ActionQBCSelection:
    """Paired M/X decisions and candidate diagnostics from one computation."""

    rows: tuple[ActionQBCRow, ...]
    exploit: ExploitChoice
    m_decision: VariantPolicyDecision
    x_decision: VariantPolicyDecision
    m_utility_maximizers: tuple[Action, ...]
    x_utility_maximizers: tuple[Action, ...]
    historical_agreement: float
    historical_indifference: float
    normalized_weights: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _UnrankedRow:
    action: Action
    outcome_concentration: float
    outcome_cell_count: int
    evsi: float
    catastrophe_mass: float
    m_utility: float
    x_utility: float
    eligible: bool
    exploit_mean_cost: float
    exploit_standard_deviation: float
    exploit_score: float


def normalise_gibbs_weights(weights: Sequence[float]) -> tuple[float, ...]:
    """Use the frozen planner normalization for the one shared committee vector."""

    return _planner._normalise_weights(weights)


def _partition_normalized_outcomes(
    predictions: Sequence[Prediction], normalized_weights: Sequence[float]
) -> tuple[OutcomeCell, ...]:
    if len(predictions) != len(normalized_weights):
        raise ValueError("predictions and weights must have equal length")
    grouped: dict[PredictionSignature, list[int]] = defaultdict(list)
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, Prediction):
            raise TypeError("filtered outcome partitions require Prediction values")
        grouped[_planner.prediction_signature(prediction)].append(index)
    return tuple(
        OutcomeCell(
            signature=signature,
            hypothesis_indices=tuple(indices),
            mass=fsum(normalized_weights[index] for index in indices),
        )
        for signature, indices in grouped.items()
    )


def partition_exact_outcomes(
    predictions: Sequence[Prediction], weights: Sequence[float]
) -> tuple[OutcomeCell, ...]:
    """Partition predictions by the exact signature already used by EVSI."""

    normalized = normalise_gibbs_weights(weights)
    return _partition_normalized_outcomes(predictions, normalized)


def clamp_outcome_concentration(raw: float) -> float:
    """Validate raw concentration and clamp boundary residue only."""

    value = float(raw)
    if not isfinite(value):
        raise ValueError("outcome concentration must be finite")
    if (
        value < -OUTCOME_CONCENTRATION_TOLERANCE
        or value > 1.0 + OUTCOME_CONCENTRATION_TOLERANCE
    ):
        raise ValueError("raw outcome concentration lies outside its tolerated range")
    return min(1.0, max(0.0, value))


def outcome_concentration(
    predictions: Sequence[Prediction], weights: Sequence[float]
) -> float:
    """Return maximum normalized Gibbs mass in one exact outcome cell."""

    cells = partition_exact_outcomes(predictions, weights)
    if not cells:
        raise ValueError("at least one exact outcome cell is required")
    return clamp_outcome_concentration(max(cell.mass for cell in cells))


def _validate_snapshot(snapshot: PlanningSnapshot) -> tuple[float, ...]:
    if not snapshot.actions:
        raise ValueError("action-QBC selection requires at least one candidate")
    if len(set(snapshot.actions)) != len(snapshot.actions):
        raise ValueError("candidate actions must be unique")
    normalized = normalise_gibbs_weights(snapshot.weights)
    if len(snapshot.hypothesis_ids) != len(normalized):
        raise ValueError("hypothesis IDs and weights must have equal length")
    if len(set(snapshot.hypothesis_ids)) != len(snapshot.hypothesis_ids):
        raise ValueError("hypothesis IDs must be unique")
    if set(snapshot.predictions) != set(snapshot.actions):
        raise ValueError("prediction rows must exactly cover the candidate actions")
    if set(snapshot.costs) != set(snapshot.actions):
        raise ValueError("cost rows must exactly cover the candidate actions")
    for action in snapshot.actions:
        predictions = snapshot.predictions[action]
        costs = snapshot.costs[action]
        if len(predictions) != len(normalized) or len(costs) != len(normalized):
            raise ValueError("every prediction and cost row must match the committee")
        if any(prediction is None for prediction in predictions):
            raise ValueError(
                "root prediction failure reached action-QBC policy instead of whole-"
                "hypothesis filtering"
            )
    return normalized


def _rank_eligible(
    rows: Sequence[_UnrankedRow], attribute: Literal["m_utility", "x_utility"]
) -> tuple[int, ...]:
    eligible = (index for index, row in enumerate(rows) if row.eligible)
    return tuple(
        sorted(
            eligible,
            key=lambda index: (-float(getattr(rows[index], attribute)), index),
        )
    )


def _variant_decision(
    rows: Sequence[_UnrankedRow],
    ranking: Sequence[int],
    *,
    utility_attribute: Literal["m_utility", "x_utility"],
    exploit: ExploitChoice,
    cap_available: bool,
) -> tuple[VariantPolicyDecision, int | None, tuple[Action, ...]]:
    if not ranking:
        return (
            VariantPolicyDecision(
                exploit.action,
                "exploit",
                exploit.score,
                "no_disagreement_eligible_action",
                None,
            ),
            None,
            (),
        )
    first = ranking[0]
    best_utility = float(getattr(rows[first], utility_attribute))
    maximizers = tuple(
        row.action
        for row in rows
        if row.eligible and float(getattr(row, utility_attribute)) == best_utility
    )
    if not cap_available:
        return (
            VariantPolicyDecision(
                exploit.action,
                "exploit",
                exploit.score,
                "level_probe_cap_reached",
                rows[first].action,
            ),
            None,
            maximizers,
        )
    if best_utility <= 0.0:
        return (
            VariantPolicyDecision(
                exploit.action,
                "exploit",
                exploit.score,
                "nonpositive_utility",
                rows[first].action,
            ),
            None,
            maximizers,
        )
    return (
        VariantPolicyDecision(
            rows[first].action,
            "probe",
            best_utility,
            "selected",
            rows[first].action,
        ),
        first,
        maximizers,
    )


def _require_fixed_numeric_factor(
    name: str,
    value: float,
    expected: float,
) -> float:
    """Reject unregistered factor drift before computing policy quantities."""

    if isinstance(value, bool):
        raise ValueError(f"{name} must be the registered numeric value {expected}")
    numeric = float(value)
    if not isfinite(numeric) or numeric != expected:
        raise ValueError(f"{name} must equal the registered value {expected}")
    return numeric


def _require_finite_policy_values(**values: float) -> None:
    if any(not isfinite(float(value)) for value in values.values()):
        names = ", ".join(sorted(values))
        raise ValueError(f"derived action-QBC values must be finite: {names}")


def select_action_conditional_qbc(
    snapshot: PlanningSnapshot,
    *,
    cross_level_multiplier: float,
    probes_used: int,
    probe_cap: int,
    outcome_concentration_threshold: float = OUTCOME_CONCENTRATION_THRESHOLD,
    risk_coefficient: float = RISK_COEFFICIENT,
    robust_std_coefficient: float = ROBUST_STD_COEFFICIENT,
) -> ActionQBCSelection:
    """Compute authoritative paired M/X decisions from one filtered snapshot."""

    normalized = _validate_snapshot(snapshot)
    multiplier = float(cross_level_multiplier)
    threshold = _require_fixed_numeric_factor(
        "outcome_concentration_threshold",
        outcome_concentration_threshold,
        OUTCOME_CONCENTRATION_THRESHOLD,
    )
    risk = _require_fixed_numeric_factor(
        "risk_coefficient", risk_coefficient, RISK_COEFFICIENT
    )
    robust_coefficient = _require_fixed_numeric_factor(
        "robust_std_coefficient",
        robust_std_coefficient,
        ROBUST_STD_COEFFICIENT,
    )
    if not isfinite(multiplier) or multiplier < 1.0:
        raise ValueError("cross-level multiplier must be finite and at least one")
    if isinstance(probes_used, bool) or not isinstance(probes_used, int) or probes_used < 0:
        raise ValueError("probes_used must be a non-negative integer")
    if (
        isinstance(probe_cap, bool)
        or not isinstance(probe_cap, int)
        or probe_cap != MAX_PROBES_PER_LEVEL
    ):
        raise ValueError(
            f"probe_cap must equal the registered value {MAX_PROBES_PER_LEVEL}"
        )

    exploit = _planner.robust_exploitation(
        snapshot.actions,
        snapshot.costs,
        snapshot.weights,
        standard_deviation_coefficient=robust_coefficient,
    )
    _require_finite_policy_values(
        exploit_mean_cost=exploit.mean_cost,
        exploit_standard_deviation=exploit.standard_deviation,
        exploit_score=exploit.score,
    )
    unranked: list[_UnrankedRow] = []
    for action in snapshot.actions:
        predictions = tuple(snapshot.predictions[action])
        assert all(prediction is not None for prediction in predictions)
        valid_predictions = tuple(
            prediction for prediction in predictions if prediction is not None
        )
        cells = _partition_normalized_outcomes(valid_predictions, normalized)
        concentration = clamp_outcome_concentration(max(cell.mass for cell in cells))
        evsi = _planner.weighted_evsi(
            valid_predictions,
            snapshot.actions,
            snapshot.costs,
            snapshot.weights,
        )
        catastrophe = _planner.catastrophe_probability(
            valid_predictions, snapshot.weights
        )
        mean_cost, standard_deviation = _planner.weighted_mean_std(
            snapshot.costs[action], snapshot.weights
        )
        m_utility = _planner.probe_utility(
            evsi,
            1.0,
            catastrophe,
            action_cost=ACTION_COST,
            risk_coefficient=risk,
        )
        x_utility = _planner.probe_utility(
            evsi,
            multiplier,
            catastrophe,
            action_cost=ACTION_COST,
            risk_coefficient=risk,
        )
        exploit_score = mean_cost + robust_coefficient * standard_deviation
        _require_finite_policy_values(
            evsi=evsi,
            catastrophe_mass=catastrophe,
            m_utility=m_utility,
            x_utility=x_utility,
            exploit_mean_cost=mean_cost,
            exploit_standard_deviation=standard_deviation,
            exploit_score=exploit_score,
        )
        unranked.append(
            _UnrankedRow(
                action=action,
                outcome_concentration=concentration,
                outcome_cell_count=len(cells),
                evsi=evsi,
                catastrophe_mass=catastrophe,
                m_utility=m_utility,
                x_utility=x_utility,
                eligible=concentration < threshold,
                exploit_mean_cost=mean_cost,
                exploit_standard_deviation=standard_deviation,
                exploit_score=exploit_score,
            )
        )

    m_ranking = _rank_eligible(unranked, "m_utility")
    x_ranking = _rank_eligible(unranked, "x_utility")
    cap_available = probes_used < probe_cap
    m_decision, m_selected_index, m_maximizers = _variant_decision(
        unranked,
        m_ranking,
        utility_attribute="m_utility",
        exploit=exploit,
        cap_available=cap_available,
    )
    x_decision, x_selected_index, x_maximizers = _variant_decision(
        unranked,
        x_ranking,
        utility_attribute="x_utility",
        exploit=exploit,
        cap_available=cap_available,
    )
    m_ranks = {candidate_index: rank for rank, candidate_index in enumerate(m_ranking, 1)}
    x_ranks = {candidate_index: rank for rank, candidate_index in enumerate(x_ranking, 1)}
    rows = tuple(
        ActionQBCRow(
            action=row.action,
            outcome_concentration=row.outcome_concentration,
            outcome_cell_count=row.outcome_cell_count,
            evsi=row.evsi,
            catastrophe_mass=row.catastrophe_mass,
            m_utility=row.m_utility,
            x_utility=row.x_utility,
            eligible=row.eligible,
            m_rank=m_ranks.get(index),
            x_rank=x_ranks.get(index),
            m_selected=index == m_selected_index,
            x_selected=index == x_selected_index,
            exploit_mean_cost=row.exploit_mean_cost,
            exploit_standard_deviation=row.exploit_standard_deviation,
            exploit_score=row.exploit_score,
        )
        for index, row in enumerate(unranked)
    )
    historical_agreement = _planner.committee_agreement(
        snapshot.actions, snapshot.costs, snapshot.weights
    )
    historical_indifference = _planner.committee_indifference(
        snapshot.actions, snapshot.costs, snapshot.weights
    )
    _require_finite_policy_values(
        historical_agreement=historical_agreement,
        historical_indifference=historical_indifference,
    )
    return ActionQBCSelection(
        rows=rows,
        exploit=exploit,
        m_decision=m_decision,
        x_decision=x_decision,
        m_utility_maximizers=m_maximizers,
        x_utility_maximizers=x_maximizers,
        historical_agreement=historical_agreement,
        historical_indifference=historical_indifference,
        normalized_weights=normalized,
    )


def _source_text(value: object) -> str:
    return inspect.getsource(cast(Any, value))


def _policy_source_bundle() -> dict[str, object]:
    implementation_objects = (
        OutcomeCell,
        ActionQBCRow,
        VariantPolicyDecision,
        ActionQBCSelection,
        _UnrankedRow,
        normalise_gibbs_weights,
        _partition_normalized_outcomes,
        partition_exact_outcomes,
        clamp_outcome_concentration,
        outcome_concentration,
        _validate_snapshot,
        _rank_eligible,
        _variant_decision,
        _require_fixed_numeric_factor,
        _require_finite_policy_values,
        select_action_conditional_qbc,
    )
    dependency_objects = {
        "BeamSearchPlanner.evaluate": _planner.BeamSearchPlanner.evaluate,
        "GameState": GameState,
        "Prediction": Prediction,
        "Prediction.signature": Prediction.signature,
        "catastrophe_probability": _planner.catastrophe_probability,
        "committee_agreement": _planner.committee_agreement,
        "committee_indifference": _planner.committee_indifference,
        "freeze_grid": freeze_grid,
        "planner._normalise_weights": _planner._normalise_weights,
        "prediction_signature": _planner.prediction_signature,
        "probe_utility": _planner.probe_utility,
        "robust_exploitation": _planner.robust_exploitation,
        "state_name": _planner._state_name,
        "weighted_evsi": _planner.weighted_evsi,
        "weighted_mean_std": _planner.weighted_mean_std,
    }
    return {
        "constants": {
            "action_cost": ACTION_COST,
            "max_probes_per_level": MAX_PROBES_PER_LEVEL,
            "outcome_concentration_threshold": OUTCOME_CONCENTRATION_THRESHOLD,
            "outcome_concentration_tolerance": OUTCOME_CONCENTRATION_TOLERANCE,
            "policy_version": ACTION_QBC_POLICY_VERSION,
            "risk_coefficient": RISK_COEFFICIENT,
            "robust_std_coefficient": ROBUST_STD_COEFFICIENT,
            "runtime_version": ACTION_QBC_RUNTIME_VERSION,
        },
        "contract": dict(ACTION_QBC_POLICY_CONTRACT),
        "dependency_sources": {
            name: _source_text(value)
            for name, value in sorted(dependency_objects.items())
        },
        "implementation_sources": {
            value.__name__: _source_text(value) for value in implementation_objects
        },
        "source_bundle_schema_version": 1,
    }


def action_qbc_policy_sha256() -> str:
    payload = json.dumps(
        _policy_source_bundle(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


ACTION_QBC_POLICY_SHA256: Final = (
    "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
)
if action_qbc_policy_sha256() != ACTION_QBC_POLICY_SHA256:
    raise RuntimeError("action-QBC policy source differs from its reviewed digest")


__all__ = [
    "ACTION_QBC_POLICY_CONTRACT",
    "ACTION_QBC_POLICY_SHA256",
    "ACTION_QBC_POLICY_VERSION",
    "ACTION_QBC_RUNTIME_VERSION",
    "MAX_PROBES_PER_LEVEL",
    "OUTCOME_CONCENTRATION_THRESHOLD",
    "ActionQBCRow",
    "ActionQBCSelection",
    "OutcomeCell",
    "VariantPolicyDecision",
    "action_qbc_policy_sha256",
    "clamp_outcome_concentration",
    "normalise_gibbs_weights",
    "outcome_concentration",
    "partition_exact_outcomes",
    "select_action_conditional_qbc",
]
