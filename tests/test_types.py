from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from arc3_voi.config import ConfigError, config_from_mapping
from arc3_voi.types import (
    Action,
    ActionKind,
    Budget,
    Decision,
    DecisionMode,
    GameState,
    History,
    Observation,
    Prediction,
)


def observation(value: int, *, level: int = 1, win_levels: int = 3) -> Observation:
    return Observation(
        grid=np.full((4, 4), value, dtype=np.int8),
        available_actions=frozenset({ActionKind.ACTION1, ActionKind.ACTION6}),
        game_state=GameState.NOT_FINISHED,
        level=level,
        win_levels=win_levels,
    )


def test_action6_converts_row_col_to_official_xy() -> None:
    action = Action(ActionKind.ACTION6, row=11, col=29)

    assert action.to_official_args() == {"x": 29, "y": 11}
    assert action.as_official() == (6, {"x": 29, "y": 11})
    with pytest.raises(FrozenInstanceError):
        action.row = 3  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kind", "row", "col"),
    [
        (ActionKind.ACTION6, None, 1),
        (ActionKind.ACTION6, 1, None),
        (ActionKind.ACTION1, 1, 1),
        (ActionKind.ACTION6, -1, 1),
        (ActionKind.ACTION6, 1, 64),
    ],
)
def test_action_rejects_invalid_coordinate_shapes(
    kind: ActionKind,
    row: int | None,
    col: int | None,
) -> None:
    with pytest.raises(ValueError):
        Action(kind, row=row, col=col)


def test_simple_action_has_no_official_arguments() -> None:
    assert Action(ActionKind.ACTION2).as_official() == (2, {})


def test_observation_defensively_copies_and_freezes_grid() -> None:
    source = np.arange(16, dtype=np.uint8).reshape(4, 4)
    item = Observation(
        source,
        frozenset({ActionKind.ACTION1}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=1,
    )
    source[0, 0] = 99

    assert item.grid[0, 0] == 0
    assert not item.grid.flags.writeable
    with pytest.raises(ValueError):
        item.grid[0, 0] = 1


def test_history_keeps_aligned_last_eight_stable_frames() -> None:
    history = History.from_observation(observation(0))
    for value in range(1, 10):
        history = history.append(
            observation(value),
            action=Action(ActionKind.ACTION1),
            level_delta=0,
        )

    assert len(history.frames) == History.MAX_LENGTH == 8
    assert [int(frame[0, 0]) for frame in history.frames] == list(range(2, 10))
    assert len(history.actions) == len(history.action_sets) == len(history.game_states) == 8
    assert history.latest_grid[0, 0] == 9
    assert history.latest_game_state is GameState.NOT_FINISHED
    assert history.latest_action_set == frozenset({ActionKind.ACTION1, ActionKind.ACTION6})
    assert history.current_level == 1


def test_trusted_history_append_structurally_shares_frozen_frames() -> None:
    history = History.from_observation(observation(0))
    next_observation = observation(1)

    advanced = history._append_trusted_observation(
        next_observation,
        Action(ActionKind.ACTION1),
        0,
    )

    assert advanced.frames[0] is history.frames[0]
    assert advanced.frames[-1] is next_observation.grid
    assert advanced.frames[0].flags.owndata
    assert advanced.frames[-1].flags.owndata
    assert not advanced.frames[0].flags.writeable
    assert not advanced.frames[-1].flags.writeable
    with pytest.raises(ValueError):
        advanced.frames[-1][0, 0] = 7


def test_history_rejects_unaligned_fields() -> None:
    with pytest.raises(ValueError, match="same length"):
        History(frames=(np.zeros((2, 2), dtype=np.int8),))


def test_prediction_signature_ignores_memory_and_memory_is_read_only() -> None:
    first = Prediction(
        np.ones((2, 2), dtype=np.int8),
        GameState.WIN,
        level_delta=1,
        memory={"latent": 1},
    )
    second = Prediction(
        np.ones((2, 2), dtype=np.int8),
        GameState.WIN,
        level_delta=1,
        memory={"latent": 999},
    )

    assert first.signature() == second.signature()
    with pytest.raises(TypeError):
        first.memory["latent"] = 2  # type: ignore[index]


def test_budget_is_consumed_functionally_and_enforces_all_limits() -> None:
    original = Budget(max_environment_actions=2, max_generated_tokens=10, max_wall_seconds=5)
    consumed = original.consume(environment_actions=1, generated_tokens=4, wall_seconds=1.5)

    assert original.environment_actions_used == 0
    assert consumed.remaining_environment_actions == 1
    assert consumed.remaining_generated_tokens == 6
    assert consumed.remaining_wall_seconds == 3.5
    assert consumed.can_afford(environment_actions=1, generated_tokens=6, wall_seconds=3.5)
    with pytest.raises(ValueError, match="exhausted"):
        consumed.consume(environment_actions=2)


def test_decision_validates_mode_score_and_freezes_diagnostics() -> None:
    decision = Decision(
        Action(ActionKind.ACTION1),
        DecisionMode.EXPLOIT,
        score=1.25,
        diagnostics={"agreement": 0.9},
    )
    assert decision.mode is DecisionMode.EXPLOIT
    with pytest.raises(TypeError):
        decision.diagnostics["agreement"] = 0.1  # type: ignore[index]
    with pytest.raises(ValueError, match="finite"):
        Decision(Action(ActionKind.ACTION1), DecisionMode.PROBE, score=float("nan"))


def test_config_mapping_constructs_defaults_and_rejects_unknown_keys() -> None:
    config = config_from_mapping(
        {
            "experiment": {"variant": "M", "history_length": 8},
            "model": {"id": "Qwen/Qwen3.5-9B", "profile": "local-nf4"},
        }
    )
    assert config.experiment.variant == "M"
    assert config.hypotheses.max_hypotheses == 4
    assert config.model is not None and config.model.quantization == "none"

    with pytest.raises(ConfigError, match="unknown top-level"):
        config_from_mapping({"surprise": True})
