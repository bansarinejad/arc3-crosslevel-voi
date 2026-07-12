from __future__ import annotations

import numpy as np

from arc3_voi.competition import run_scorecard
from arc3_voi.config import ExperimentConfig, SystemConfig
from arc3_voi.model import ScriptedBackend
from arc3_voi.types import Action, ActionKind, GameState, Observation


class Session:
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id

    def initial_observation(self) -> Observation:
        return self._observation(GameState.NOT_FINISHED)

    def step(self, action: Action, *, reasoning: object = None) -> Observation:
        del action, reasoning
        return self._observation(GameState.WIN)

    def _observation(self, state: GameState) -> Observation:
        return Observation(
            np.zeros((2, 2), dtype=np.int8),
            frozenset({ActionKind.ACTION1}),
            state,
            1,
            1,
        )


class Client:
    def __init__(self) -> None:
        self.made: list[str] = []

    def make(self, game_id: str, *, seed: int = 0) -> Session:
        del seed
        self.made.append(game_id)
        return Session(game_id)


def test_scorecard_reuses_backend_and_makes_each_game_once(tmp_path) -> None:
    client = Client()
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION1"})
    config = SystemConfig(experiment=ExperimentConfig(variant="D", max_wall_seconds=5))
    result = run_scorecard(
        ("a", "b"),
        backend,
        config,
        output_directory=tmp_path,
        client=client,  # type: ignore[arg-type]
    )
    assert client.made == ["a", "b"]
    assert len(result.runs) == 2
    assert not result.stopped_early

