from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.arc_adapter import (
    ArcAdapterError,
    ArcCompetitionClient,
    ArcEnvironmentSession,
    observation_from_raw,
)
from arc3_voi.types import Action, ActionKind, GameState


def _raw(*, state: str = "NOT_FINISHED", levels: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        frame=np.zeros((1, 64, 64), dtype=np.int8),
        available_actions=(1, 6),
        state=state,
        levels_completed=levels,
        win_levels=3,
    )


class FakeEnvironment:
    def __init__(self, raw: SimpleNamespace) -> None:
        self.observation_space = raw
        self.reset_calls = 0
        self.steps: list[tuple[object, dict[str, int]]] = []

    def step(self, action: object, data: dict[str, int], reasoning: object) -> SimpleNamespace:
        del reasoning
        self.steps.append((action, data))
        return _raw()

    def reset(self) -> SimpleNamespace:
        self.reset_calls += 1
        return _raw()


def test_observation_uses_last_animation_frame() -> None:
    raw = _raw(levels=1)
    raw.frame = np.stack((np.zeros((64, 64)), np.ones((64, 64))))
    observation = observation_from_raw(raw)
    assert observation.level == 2
    assert np.all(observation.grid == 1)


def test_action6_coordinate_conversion_at_adapter_boundary() -> None:
    environment = FakeEnvironment(_raw())
    session = ArcEnvironmentSession("g", environment)
    session.step(Action(ActionKind.ACTION6, row=7, col=9))
    assert environment.steps[0][1] == {"x": 9, "y": 7}


def test_installed_arcengine_action_identity_is_selected_by_name() -> None:
    pytest.importorskip("arcengine")
    from arcengine import GameAction

    from arc3_voi.arc_adapter import _official_game_action

    assert _official_game_action(ActionKind.ACTION1) is GameAction.ACTION1


def test_reset_is_only_allowed_after_game_over() -> None:
    environment = FakeEnvironment(_raw())
    session = ArcEnvironmentSession("g", environment)
    with pytest.raises(ArcAdapterError):
        session.step(Action(ActionKind.RESET))


def test_competition_client_makes_each_game_once() -> None:
    class FakeArcade:
        def make(self, game_id: str, **kwargs: object) -> FakeEnvironment:
            del game_id, kwargs
            return FakeEnvironment(_raw())

    client = ArcCompetitionClient(FakeArcade())
    client.make("abcd-v1")
    with pytest.raises(ArcAdapterError):
        client.make("abcd-v2")
    with pytest.raises(ArcAdapterError):
        client.get_scorecard()


def test_not_started_requires_reset() -> None:
    assert observation_from_raw(_raw(state="NOT_STARTED")).game_state is GameState.GAME_OVER
