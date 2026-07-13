from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from arc3_voi.agent import TreatmentNotAdmittedError
from arc3_voi.competition import run_scorecard
from arc3_voi.config import ExperimentConfig, SystemConfig, load_config
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


def test_scorecard_rejects_failed_treatment_before_making_game(tmp_path) -> None:
    template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    config = replace(
        template,
        experiment=replace(template.experiment, hypothesis_source="qwen"),
    )
    client = Client()
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION1"})

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        run_scorecard(
            ("must-not-run",),
            backend,
            config,
            output_directory=tmp_path,
            client=client,  # type: ignore[arg-type]
        )

    assert client.made == []


def test_scorecard_resume_only_makes_the_missing_game(tmp_path) -> None:
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION1"})
    config = SystemConfig(experiment=ExperimentConfig(variant="D", max_wall_seconds=5))
    first_client = Client()
    run_scorecard(
        ("a",),
        backend,
        config,
        output_directory=tmp_path,
        client=first_client,  # type: ignore[arg-type]
    )

    resumed_client = Client()
    result = run_scorecard(
        ("a", "b"),
        backend,
        config,
        output_directory=tmp_path,
        client=resumed_client,  # type: ignore[arg-type]
    )

    assert first_client.made == ["a"]
    assert resumed_client.made == ["b"]
    assert [run.game_id for run in result.runs] == ["a", "b"]


def test_scorecard_rejects_corrupt_clean_pair_before_making_game(tmp_path) -> None:
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION1"})
    config = SystemConfig(experiment=ExperimentConfig(variant="D", max_wall_seconds=5))
    run_scorecard(
        ("a",),
        backend,
        config,
        output_directory=tmp_path,
        client=Client(),  # type: ignore[arg-type]
    )
    trace = next(tmp_path.glob("*.jsonl"))
    trace.write_bytes(trace.read_bytes()[:-10])

    resumed_client = Client()
    with pytest.raises(FileExistsError, match="clean completion claim"):
        run_scorecard(
            ("a",),
            backend,
            config,
            output_directory=tmp_path,
            client=resumed_client,  # type: ignore[arg-type]
        )
    assert resumed_client.made == []
