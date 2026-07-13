"""Finite-committee planning and value-of-information calculations."""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from collections import defaultdict
from collections.abc import Hashable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from math import fsum, isclose, sqrt
from typing import Literal, TypeAlias

import numpy as np

from arc3_voi.hypothesis import Hypothesis
from arc3_voi.types import Action, GameState, History, Observation, Prediction

PredictionSignature: TypeAlias = tuple[object, ...]  # noqa: UP040 - pinned mypy
CompletionCostPolicy: TypeAlias = Literal[  # noqa: UP040 - pinned mypy
    "endpoint-v1", "path-deficit-v2"
]
ENDPOINT_COMPLETION_COST_POLICY: CompletionCostPolicy = "endpoint-v1"
PATH_DEFICIT_COMPLETION_COST_POLICY: CompletionCostPolicy = "path-deficit-v2"


class PlanningError(RuntimeError):
    """Raised when executable programs cannot produce a usable search state."""


class NoValidHypotheses(PlanningError):
    """Raised when every weighted program fails on the root candidate set."""

    def __init__(
        self, message: str, *, invalid_hypothesis_ids: Sequence[str] = ()
    ) -> None:
        super().__init__(message)
        self.invalid_hypothesis_ids = tuple(invalid_hypothesis_ids)


class _InvalidHypothesis(PlanningError):
    """Internal signal that a generated program is not total on planner states."""


def _state_name(state: GameState | str) -> str:
    if isinstance(state, GameState):
        return state.value
    return str(state).upper().split(".")[-1]


def prediction_signature(prediction: Prediction | None) -> PredictionSignature:
    """Return the exact observable outcome used to partition the committee."""

    if prediction is None:
        return ("INVALID",)
    # Prediction.signature is the source of truth when available, but wrap it so
    # the invalid sentinel can never collide with a valid outcome.
    signature = prediction.signature()
    if isinstance(signature, tuple):
        return ("VALID", *signature)
    return ("VALID", signature)


def _normalise_weights(weights: Sequence[float]) -> tuple[float, ...]:
    if not weights:
        raise ValueError("at least one hypothesis weight is required")
    if any(not np.isfinite(weight) or weight < 0 for weight in weights):
        raise ValueError("weights must be finite and non-negative")
    total = fsum(weights)
    if total <= 0:
        raise ValueError("hypothesis weights must have positive mass")
    return tuple(float(weight / total) for weight in weights)


def weighted_mean_std(values: Sequence[float], weights: Sequence[float]) -> tuple[float, float]:
    """Population mean and standard deviation under normalized committee mass."""

    if len(values) != len(weights):
        raise ValueError("values and weights must have equal length")
    normalised = _normalise_weights(weights)
    if any(not np.isfinite(value) for value in values):
        raise ValueError("costs must be finite")
    mean = fsum(weight * float(value) for value, weight in zip(values, normalised, strict=True))
    variance = fsum(
        weight * (float(value) - mean) ** 2
        for value, weight in zip(values, normalised, strict=True)
    )
    return mean, sqrt(max(0.0, variance))


@dataclass(frozen=True, slots=True)
class ExploitChoice:
    action: Action
    score: float
    mean_cost: float
    standard_deviation: float


def robust_exploitation(
    actions: Sequence[Action],
    costs: Mapping[Action, Sequence[float]],
    weights: Sequence[float],
    *,
    standard_deviation_coefficient: float = 0.5,
) -> ExploitChoice:
    """Choose the minimum weighted mean cost plus an uncertainty penalty."""

    if not actions:
        raise ValueError("at least one action is required")
    if standard_deviation_coefficient < 0:
        raise ValueError("standard_deviation_coefficient must be non-negative")
    choices: list[ExploitChoice] = []
    for action in actions:
        mean, standard_deviation = weighted_mean_std(costs[action], weights)
        choices.append(
            ExploitChoice(
                action=action,
                score=mean + standard_deviation_coefficient * standard_deviation,
                mean_cost=mean,
                standard_deviation=standard_deviation,
            )
        )
    # Candidate order is the deterministic tie-break, so do not sort by Action.
    return min(enumerate(choices), key=lambda indexed: (indexed[1].score, indexed[0]))[1]


def committee_agreement(
    actions: Sequence[Action],
    costs: Mapping[Action, Sequence[float]],
    weights: Sequence[float],
) -> float:
    """Maximum committee mass that regards one action as cost-optimal.

    A hypothesis votes for every exactly or numerically tied optimum. This makes
    agreement invariant to candidate ordering without misclassifying within-model
    indifference as between-model disagreement.
    """

    if not actions:
        raise ValueError("at least one action is required")
    normalised = _normalise_weights(weights)
    if any(len(costs[action]) != len(normalised) for action in actions):
        raise ValueError("every cost vector must match the number of weights")
    if any(not np.isfinite(cost) for action in actions for cost in costs[action]):
        raise ValueError("costs must be finite")
    optimal_mass = []
    for action in actions:
        optimal_mass.append(
            fsum(
                weight
                for hypothesis_index, weight in enumerate(normalised)
                if isclose(
                    float(costs[action][hypothesis_index]),
                    min(float(costs[candidate][hypothesis_index]) for candidate in actions),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            )
        )
    return min(1.0, max(0.0, max(optimal_mass)))


def committee_indifference(
    actions: Sequence[Action],
    costs: Mapping[Action, Sequence[float]],
    weights: Sequence[float],
) -> float:
    """Weighted fraction of extra actions tied for optimum, normalized to [0, 1]."""

    if not actions:
        raise ValueError("at least one action is required")
    normalised = _normalise_weights(weights)
    if any(len(costs[action]) != len(normalised) for action in actions):
        raise ValueError("every cost vector must match the number of weights")
    if any(not np.isfinite(cost) for action in actions for cost in costs[action]):
        raise ValueError("costs must be finite")
    if len(actions) == 1:
        return 0.0
    value = fsum(
        weight
        * (
            sum(
                isclose(
                    float(costs[action][hypothesis_index]),
                    min(float(costs[candidate][hypothesis_index]) for candidate in actions),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
                for action in actions
            )
            - 1
        )
        / (len(actions) - 1)
        for hypothesis_index, weight in enumerate(normalised)
    )
    return min(1.0, max(0.0, value))


def weighted_evsi(
    probe_predictions: Sequence[Prediction | None],
    exploitation_actions: Sequence[Action],
    costs: Mapping[Action, Sequence[float]],
    weights: Sequence[float],
) -> float:
    """Expected value of sample information for an exact predicted partition.

    This is the reduction in optimal expected completion cost after observing a
    probe outcome.  Invalid predictions form their own explicit outcome cluster;
    they are not silently discarded or allowed to renormalize the evidence.
    """

    if not exploitation_actions:
        raise ValueError("at least one exploitation action is required")
    if len(probe_predictions) != len(weights):
        raise ValueError("predictions and weights must have equal length")
    normalised = _normalise_weights(weights)
    if any(len(costs[action]) != len(normalised) for action in exploitation_actions):
        raise ValueError("every cost vector must match the number of hypotheses")

    prior_best = min(
        fsum(
            weight * float(cost)
            for weight, cost in zip(normalised, costs[action], strict=True)
        )
        for action in exploitation_actions
    )
    clusters: dict[PredictionSignature, list[int]] = defaultdict(list)
    for index, prediction in enumerate(probe_predictions):
        clusters[prediction_signature(prediction)].append(index)

    posterior_best = 0.0
    for indices in clusters.values():
        cluster_mass = fsum(normalised[index] for index in indices)
        if cluster_mass <= 0:
            continue
        conditional_best = min(
            fsum(
                normalised[index] * float(costs[action][index])
                for index in indices
            )
            / cluster_mass
            for action in exploitation_actions
        )
        posterior_best += cluster_mass * conditional_best

    # Information cannot hurt when the post-observation policy may ignore it.
    # Canonicalize numerically meaningless positive residue here, before EVSI
    # reaches probe utility or trace diagnostics.
    evsi = max(0.0, prior_best - posterior_best)
    return 0.0 if evsi <= 1e-12 else evsi


def level_multiplier(level: int, win_levels: int, persistence: float) -> float:
    """Scale current information by the remaining RHAE level weight."""

    if level < 1:
        raise ValueError("level must be at least one")
    if win_levels < level:
        raise ValueError("win_levels cannot be lower than the current level")
    if not 0.0 <= persistence <= 1.0:
        raise ValueError("persistence must be in [0, 1]")
    remaining_weight = sum(range(level + 1, win_levels + 1))
    return 1.0 + persistence * remaining_weight / level


def catastrophe_probability(
    predictions: Sequence[Prediction | None], weights: Sequence[float]
) -> float:
    if len(predictions) != len(weights):
        raise ValueError("predictions and weights must have equal length")
    normalised = _normalise_weights(weights)
    return fsum(
        weight
        for prediction, weight in zip(predictions, normalised, strict=True)
        if prediction is not None
        and _state_name(prediction.game_state) == GameState.GAME_OVER.value
    )


def probe_utility(
    evsi: float,
    multiplier: float,
    catastrophe_risk: float,
    *,
    action_cost: float = 1.0,
    risk_coefficient: float = 3.0,
) -> float:
    if evsi < 0 or multiplier < 1 or not 0 <= catastrophe_risk <= 1:
        raise ValueError("invalid EVSI, multiplier, or catastrophe probability")
    if action_cost < 0 or risk_coefficient < 0:
        raise ValueError("cost coefficients must be non-negative")
    return multiplier * evsi - action_cost - risk_coefficient * catastrophe_risk


@dataclass(frozen=True, slots=True)
class ProbeChoice:
    action: Action
    utility: float
    evsi: float
    catastrophe_probability: float


def best_probe(
    actions: Sequence[Action],
    predictions: Mapping[Action, Sequence[Prediction | None]],
    costs: Mapping[Action, Sequence[float]],
    weights: Sequence[float],
    *,
    multiplier: float,
    risk_coefficient: float = 3.0,
) -> ProbeChoice:
    """Find the action with maximum risk-adjusted query-by-committee value."""

    if not actions:
        raise ValueError("at least one candidate action is required")
    choices: list[ProbeChoice] = []
    for action in actions:
        evsi = weighted_evsi(predictions[action], actions, costs, weights)
        catastrophe = catastrophe_probability(predictions[action], weights)
        choices.append(
            ProbeChoice(
                action=action,
                utility=probe_utility(
                    evsi,
                    multiplier,
                    catastrophe,
                    risk_coefficient=risk_coefficient,
                ),
                evsi=evsi,
                catastrophe_probability=catastrophe,
            )
        )
    return max(enumerate(choices), key=lambda indexed: (indexed[1].utility, -indexed[0]))[1]


@dataclass(frozen=True, slots=True)
class PlanningSnapshot:
    actions: tuple[Action, ...]
    hypothesis_ids: tuple[str, ...]
    weights: tuple[float, ...]
    predictions: Mapping[Action, tuple[Prediction | None, ...]]
    costs: Mapping[Action, tuple[float, ...]]
    invalid_hypothesis_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _BeamNode:
    history: History
    goal_value: float
    cumulative_deficit: float


@dataclass(frozen=True, slots=True)
class _HypothesisPlanningResult:
    predictions: tuple[Prediction | None, ...]
    costs: tuple[float, ...]
    invalid: bool


class BeamSearchPlanner:
    """Depth-limited, program-specific search with a shared action frontier."""

    def __init__(
        self,
        *,
        depth: int = 4,
        beam_width: int = 8,
        parallel_hypotheses: bool = False,
        completion_cost_policy: CompletionCostPolicy = ENDPOINT_COMPLETION_COST_POLICY,
    ) -> None:
        if depth < 1 or beam_width < 1:
            raise ValueError("depth and beam_width must be positive")
        self.depth = depth
        self.beam_width = beam_width
        self.parallel_hypotheses = parallel_hypotheses
        if completion_cost_policy not in COMPLETION_COST_POLICY_HASHES:
            raise ValueError("unsupported completion-cost policy")
        self.completion_cost_policy = completion_cost_policy

    @property
    def completion_cost_policy_sha256(self) -> str:
        """Return the content identity of the selected unresolved-cost policy."""

        return COMPLETION_COST_POLICY_HASHES[self.completion_cost_policy]

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        if not history.frames:
            raise ValueError("planning requires a non-empty history")
        if not actions:
            raise ValueError("planning requires at least one action")
        if not weighted_hypotheses:
            raise ValueError("planning requires at least one valid hypothesis")

        hypotheses = tuple(item[0] for item in weighted_hypotheses)
        weights = _normalise_weights(tuple(float(item[1]) for item in weighted_hypotheses))
        prediction_rows: dict[Action, list[Prediction | None]] = {action: [] for action in actions}
        cost_rows: dict[Action, list[float]] = {action: [] for action in actions}

        action_tuple = tuple(actions)
        if self.parallel_hypotheses and len(hypotheses) > 1:
            with ThreadPoolExecutor(
                max_workers=len(hypotheses),
                thread_name_prefix="arc3-plan",
            ) as executor:
                futures = tuple(
                    executor.submit(
                        self._evaluate_hypothesis,
                        hypothesis,
                        history,
                        action_tuple,
                        win_levels,
                        deadline,
                    )
                    for hypothesis in hypotheses
                )
                results = tuple(future.result() for future in futures)
        else:
            results = tuple(
                self._evaluate_hypothesis(
                    hypothesis,
                    history,
                    action_tuple,
                    win_levels,
                    deadline,
                )
                for hypothesis in hypotheses
            )

        invalid_indices = {
            index for index, result in enumerate(results) if result.invalid
        }
        for result in results:
            for action_index, action in enumerate(action_tuple):
                prediction_rows[action].append(result.predictions[action_index])
                cost_rows[action].append(result.costs[action_index])

        # A generated program that cannot predict every root action is invalid,
        # rather than an extra observable outcome the real environment might
        # reveal.  Give it zero planning mass exactly as the version-space spec
        # requires and let the controller fall back if fewer than K remain.
        valid_indices = tuple(
            index
            for index in range(len(hypotheses))
            if index not in invalid_indices
            and all(prediction_rows[action][index] is not None for action in actions)
        )
        if not valid_indices:
            raise NoValidHypotheses(
                "every hypothesis failed during planning",
                invalid_hypothesis_ids=tuple(
                    hypothesis.hypothesis_id for hypothesis in hypotheses
                ),
            )
        filtered_weights = _normalise_weights(tuple(weights[index] for index in valid_indices))
        return PlanningSnapshot(
            actions=tuple(actions),
            hypothesis_ids=tuple(hypotheses[index].hypothesis_id for index in valid_indices),
            weights=filtered_weights,
            predictions={
                action: tuple(row[index] for index in valid_indices)
                for action, row in prediction_rows.items()
            },
            costs={
                action: tuple(row[index] for index in valid_indices)
                for action, row in cost_rows.items()
            },
            invalid_hypothesis_ids=tuple(
                hypotheses[index].hypothesis_id
                for index in range(len(hypotheses))
                if index not in valid_indices
            ),
        )

    def _evaluate_hypothesis(
        self,
        hypothesis: Hypothesis,
        history: History,
        actions: tuple[Action, ...],
        win_levels: int,
        deadline: float | None,
    ) -> _HypothesisPlanningResult:
        cache: dict[tuple[str, Hashable, Action], Prediction | None] = {}
        signature_cache: dict[History, Hashable] = {}
        predictions: list[Prediction | None] = []
        for action in actions:
            self._check_deadline(deadline)
            predictions.append(
                self._predict(
                    hypothesis,
                    history,
                    action,
                    cache,
                    signature_cache,
                )
            )
        if any(prediction is None for prediction in predictions):
            return _HypothesisPlanningResult(
                tuple(predictions),
                (8.0,) * len(actions),
                True,
            )

        costs: list[float] = []
        invalid = False
        for action, prediction in zip(actions, predictions, strict=True):
            self._check_deadline(deadline)
            assert prediction is not None
            try:
                costs.append(
                    self._completion_cost(
                        hypothesis,
                        history,
                        action,
                        prediction,
                        actions,
                        win_levels,
                        cache,
                        signature_cache,
                        deadline,
                    )
                )
            except _InvalidHypothesis:
                invalid = True
                break
        costs.extend([8.0] * (len(actions) - len(costs)))
        return _HypothesisPlanningResult(tuple(predictions), tuple(costs), invalid)

    def _completion_cost(
        self,
        hypothesis: Hypothesis,
        history: History,
        first_action: Action,
        first_prediction: Prediction | None,
        actions: tuple[Action, ...],
        win_levels: int,
        cache: dict[tuple[str, Hashable, Action], Prediction | None],
        signature_cache: dict[History, Hashable],
        deadline: float | None,
    ) -> float:
        if first_prediction is None:
            return 8.0
        if self._completed(first_prediction):
            return 1.0
        if self._catastrophe(first_prediction):
            return 8.0

        first_history = self._advance(
            history, first_action, actions, first_prediction, win_levels
        )
        first_goal = self._goal_value(hypothesis, first_history)
        beam = [_BeamNode(first_history, first_goal, 1.0 - first_goal)]
        if self.depth == 1:
            return 8.0 - 4.0 * beam[0].goal_value

        for step in range(2, self.depth + 1):
            self._check_deadline(deadline)
            next_beam: list[_BeamNode] = []
            for node in beam:
                for action in actions:
                    self._check_deadline(deadline)
                    prediction = self._predict(
                        hypothesis,
                        node.history,
                        action,
                        cache,
                        signature_cache,
                    )
                    if prediction is None or self._catastrophe(prediction):
                        continue
                    if self._completed(prediction):
                        return float(step)
                    advanced = self._advance(
                        node.history, action, actions, prediction, win_levels
                    )
                    goal = self._goal_value(hypothesis, advanced)
                    next_beam.append(
                        _BeamNode(
                            advanced,
                            goal,
                            node.cumulative_deficit + 1.0 - goal,
                        )
                    )
            if not next_beam:
                return 8.0
            # Python's stable sort keeps deterministic action/beam insertion
            # order for exact ties under either frozen policy.
            if self.completion_cost_policy == ENDPOINT_COMPLETION_COST_POLICY:
                next_beam.sort(key=lambda node: -node.goal_value)
            else:
                next_beam.sort(
                    key=lambda node: (node.cumulative_deficit, -node.goal_value)
                )
            beam = next_beam[: self.beam_width]

        if self.completion_cost_policy == ENDPOINT_COMPLETION_COST_POLICY:
            best_goal = max(node.goal_value for node in beam)
            return 8.0 - 4.0 * best_goal
        best_deficit = min(node.cumulative_deficit for node in beam)
        return 4.0 + 4.0 * best_deficit / self.depth

    @staticmethod
    def _check_deadline(deadline: float | None) -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise PlanningError("planning exceeded the shared wall-time budget")

    @staticmethod
    def _completed(prediction: Prediction) -> bool:
        return (
            prediction.level_delta > 0
            or _state_name(prediction.game_state) == GameState.WIN.value
        )

    @staticmethod
    def _catastrophe(prediction: Prediction) -> bool:
        return _state_name(prediction.game_state) == GameState.GAME_OVER.value

    @staticmethod
    def _goal_value(hypothesis: Hypothesis, history: History) -> float:
        try:
            value = float(hypothesis.goal_value(history))
        except Exception as exc:  # generated programs are untrusted and may fail
            raise _InvalidHypothesis(
                f"goal_value failed for hypothesis {hypothesis.hypothesis_id}"
            ) from exc
        if not np.isfinite(value) or not 0.0 <= value <= 1.0:
            raise _InvalidHypothesis(
                f"goal_value left [0, 1] for hypothesis {hypothesis.hypothesis_id}"
            )
        return value

    def _predict(
        self,
        hypothesis: Hypothesis,
        history: History,
        action: Action,
        cache: dict[tuple[str, Hashable, Action], Prediction | None],
        signature_cache: dict[History, Hashable],
    ) -> Prediction | None:
        key = (
            hypothesis.hypothesis_id,
            self._history_signature(history, signature_cache),
            action,
        )
        if key not in cache:
            try:
                cache[key] = hypothesis.predict(history, action)
            except Exception:  # invalid/timeout programs receive worst-case cost
                cache[key] = None
        return cache[key]

    @staticmethod
    def _history_signature(
        history: History,
        cache: dict[History, Hashable] | None = None,
    ) -> Hashable:
        if cache is not None and history in cache:
            return cache[history]
        frames = tuple(
            (frame.shape, frame.dtype.str, memoryview(np.ascontiguousarray(frame)).tobytes())
            for frame in history.frames
        )
        actions = tuple(
            None if action is None else (int(action.kind), action.row, action.col)
            for action in history.actions
        )
        action_sets = tuple(
            tuple(sorted(int(kind) for kind in action_set))
            for action_set in history.available_action_sets
        )
        states = tuple(_state_name(state) for state in history.game_states)
        signature = (
            frames,
            actions,
            action_sets,
            states,
            history.level_deltas,
            history.levels,
        )
        if cache is not None:
            cache[history] = signature
        return signature

    @staticmethod
    def _advance(
        history: History,
        action: Action,
        actions: Sequence[Action],
        prediction: Prediction,
        win_levels: int,
    ) -> History:
        level = max(1, history.current_level + max(0, prediction.level_delta))
        observation = Observation(
            grid=prediction.next_grid,
            available_actions=frozenset(action.kind for action in actions),
            game_state=prediction.game_state,
            level=level,
            win_levels=max(win_levels, level),
        )
        return history._append_trusted_observation(
            observation,
            action,
            prediction.level_delta,
        )


def _completion_cost_policy_sha256(policy: CompletionCostPolicy) -> str:
    payload = json.dumps(
        {
            "beam_node": inspect.getsource(_BeamNode),
            "hypothesis_result": inspect.getsource(_HypothesisPlanningResult),
            "planner": inspect.getsource(BeamSearchPlanner),
            "policy": policy,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


COMPLETION_COST_POLICY_HASHES: Mapping[CompletionCostPolicy, str] = {
    policy: _completion_cost_policy_sha256(policy)
    for policy in (
        ENDPOINT_COMPLETION_COST_POLICY,
        PATH_DEFICIT_COMPLETION_COST_POLICY,
    )
}


__all__ = [
    "COMPLETION_COST_POLICY_HASHES",
    "ENDPOINT_COMPLETION_COST_POLICY",
    "PATH_DEFICIT_COMPLETION_COST_POLICY",
    "BeamSearchPlanner",
    "CompletionCostPolicy",
    "ExploitChoice",
    "NoValidHypotheses",
    "PlanningError",
    "PlanningSnapshot",
    "ProbeChoice",
    "best_probe",
    "catastrophe_probability",
    "committee_agreement",
    "committee_indifference",
    "level_multiplier",
    "prediction_signature",
    "probe_utility",
    "robust_exploitation",
    "weighted_evsi",
    "weighted_mean_std",
]
