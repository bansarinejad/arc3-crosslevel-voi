from __future__ import annotations

import json

import numpy as np
import pytest

from arc3_voi.metrics import load_run, write_run
from arc3_voi.replay import (
    canonical_trace_hash,
    load_transitions,
    replay_prequential_losses,
)
from arc3_voi.run_store import TRACE_ARTIFACT_KEY
from arc3_voi.runner import run_game
from arc3_voi.types import Action, GameState, History, Prediction

from .test_runner import FakeController, FakeSession


def test_trace_hash_is_json_key_order_invariant(tmp_path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    first.write_text(json.dumps({"b": 2, "a": 1}) + "\n")
    second.write_text(json.dumps({"a": 1, "b": 2}) + "\n")
    assert canonical_trace_hash(first) == canonical_trace_hash(second)


class PerfectReplayHypothesis:
    def predict(self, history: History, action: Action) -> Prediction:
        del action
        final = history.current_level == 2
        return Prediction(
            np.zeros_like(history.latest_grid),
            GameState.WIN if final else GameState.NOT_FINISHED,
            0 if final else 1,
        )


def test_runner_trace_round_trips_into_deterministic_replay(tmp_path) -> None:
    metrics = run_game(
        FakeSession(),
        FakeController(),
        run_id="roundtrip",
        seed=7,
        variant="D",
        model_profile="test",
        config_hash="abc",
    )
    summary, trace = write_run(metrics, tmp_path)
    transitions = load_transitions(trace)
    restored = load_run(summary)

    assert len(transitions) == 2
    assert len(restored.steps) == 2
    assert restored.steps[-1].observed_state == "WIN"
    assert transitions[-1].domain_observation().game_state is GameState.WIN
    assert replay_prequential_losses(PerfectReplayHypothesis(), transitions) == (0.0, 0.0)
    assert canonical_trace_hash(trace) == canonical_trace_hash(trace)


def test_load_run_rejects_mismatched_legacy_trace_pair(tmp_path) -> None:
    metrics = run_game(
        FakeSession(),
        FakeController(),
        run_id="legacy-mismatch",
        seed=7,
        variant="D",
        model_profile="test",
        config_hash="abc",
    )
    summary, trace = write_run(metrics, tmp_path)
    payload = json.loads(summary.read_text())
    payload.pop(TRACE_ARTIFACT_KEY)
    summary.write_text(json.dumps(payload), encoding="utf-8")
    trace.write_text(trace.read_text().splitlines()[0] + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        load_run(summary)
