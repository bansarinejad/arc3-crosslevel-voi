from __future__ import annotations

import numpy as np
import pytest

from arc3_voi.planner import (
    committee_agreement,
    level_multiplier,
    probe_utility,
    weighted_evsi,
)
from arc3_voi.runtime_admission import x_only_probe_actions
from arc3_voi.types import Action, ActionKind, GameState, Prediction


def _prediction(value: int) -> Prediction:
    return Prediction(
        np.full((2, 2), value, dtype=np.int16),
        GameState.NOT_FINISHED,
        0,
    )


def test_hand_calculated_x_only_probe_is_order_invariant() -> None:
    first = Action(ActionKind.ACTION1)
    second = Action(ActionKind.ACTION2)
    weights = (0.5, 0.5)
    base_predictions = (_prediction(0), _prediction(1))
    base_costs = {first: (0.0, 0.1), second: (0.1, 0.0)}
    swapped_costs = {first: (0.1, 0.0), second: (0.0, 0.1)}
    cases = (
        ((first, second), base_predictions, base_costs),
        ((second, first), base_predictions, base_costs),
        ((first, second), tuple(reversed(base_predictions)), swapped_costs),
        ((second, first), tuple(reversed(base_predictions)), swapped_costs),
    )
    diagnostics = []
    for actions, predictions, costs in cases:
        evsi = weighted_evsi(predictions, actions, costs, weights)
        agreement = committee_agreement(actions, costs, weights)
        myopic_utility = probe_utility(evsi, 1.0, 0.0)
        multiplier = level_multiplier(level=1, win_levels=9, persistence=0.5)
        cross_level_utility = probe_utility(evsi, multiplier, 0.0)
        x_only = x_only_probe_actions(
            (
                {
                    "action": "PROBE",
                    "evsi": evsi,
                    "myopic_utility": myopic_utility,
                    "cross_level_utility": cross_level_utility,
                },
            ),
            agreement=agreement,
            agreement_threshold=0.8,
        )
        diagnostics.append(
            (evsi, agreement, myopic_utility, multiplier, cross_level_utility, x_only)
        )

    for evsi, agreement, myopic, multiplier, cross_level, x_only in diagnostics:
        assert evsi == pytest.approx(0.05)
        assert agreement == pytest.approx(0.5)
        assert myopic == pytest.approx(-0.95)
        assert multiplier == pytest.approx(23.0)
        assert cross_level == pytest.approx(0.15)
        assert x_only == ("PROBE",)
