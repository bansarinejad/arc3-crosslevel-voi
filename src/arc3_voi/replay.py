"""Canonical trace hashing and deterministic transition replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .hypothesis import prequential_loss
from .types import Action, ActionKind, GameState, History, Observation


@dataclass(frozen=True, slots=True)
class ReplayTransition:
    """A pre-action finite history paired with the revealed transition."""

    history: tuple[dict[str, Any], ...]
    action: dict[str, Any]
    observed_grid: np.ndarray
    observed_available_actions: tuple[str, ...]
    observed_state: str
    observed_level: int
    observed_win_levels: int
    observed_level_delta: int

    def domain_history(self) -> History:
        return history_from_records(self.history)

    def domain_action(self) -> Action:
        return action_from_record(self.action)

    def domain_observation(self) -> Observation:
        return Observation(
            self.observed_grid,
            frozenset(ActionKind.coerce(item) for item in self.observed_available_actions),
            GameState.coerce(self.observed_state),
            self.observed_level,
            self.observed_win_levels,
        )


class ReplayHypothesis(Protocol):
    def predict(self, history: History, action: Action) -> Any: ...


def canonical_trace_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            value = json.loads(line)
            digest.update(
                json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest()


def load_transitions(path: str | Path) -> tuple[ReplayTransition, ...]:
    """Load the transition subset of runner JSONL records.

    Unknown decision diagnostics are intentionally ignored so trace schemas can
    grow without invalidating deterministic replay.
    """

    transitions = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            required = {
                "history",
                "action",
                "observed_grid",
                "observed_state",
                "observed_level_delta",
            }
            missing = required - set(value)
            if missing:
                raise ValueError(
                    f"trace line {line_number} is missing replay fields {sorted(missing)}"
                )
            history = tuple(value["history"])
            if not history:
                raise ValueError(f"trace line {line_number} contains an empty history")
            latest = history[-1]
            observed_level = int(
                value.get(
                    "observed_level",
                    int(latest["level"]) + int(value["observed_level_delta"]),
                )
            )
            observed_win_levels = int(
                value.get("observed_win_levels", latest.get("win_levels", observed_level))
            )
            transitions.append(
                ReplayTransition(
                    history=history,
                    action=dict(value["action"]),
                    observed_grid=np.asarray(value["observed_grid"], dtype=np.int16),
                    observed_available_actions=tuple(
                        str(item)
                        for item in value.get(
                            "observed_available_actions", latest["available_actions"]
                        )
                    ),
                    observed_state=str(value["observed_state"]),
                    observed_level=observed_level,
                    observed_win_levels=observed_win_levels,
                    observed_level_delta=int(value["observed_level_delta"]),
                )
            )
    return tuple(transitions)


def dump_transitions(transitions: tuple[ReplayTransition, ...], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        for item in transitions:
            payload = {
                "history": item.history,
                "action": item.action,
                "observed_grid": item.observed_grid.tolist(),
                "observed_available_actions": item.observed_available_actions,
                "observed_state": item.observed_state,
                "observed_level": item.observed_level,
                "observed_win_levels": item.observed_win_levels,
                "observed_level_delta": item.observed_level_delta,
            }
            stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            stream.write("\n")


def replay_prequential_losses(
    hypothesis: ReplayHypothesis,
    transitions: tuple[ReplayTransition, ...],
) -> tuple[float, ...]:
    """Replay exact pre-action inputs and return deterministic revealed losses."""

    losses = []
    for transition in transitions:
        prediction = hypothesis.predict(
            transition.domain_history(), transition.domain_action()
        )
        losses.append(
            prequential_loss(
                prediction,
                transition.observed_grid,
                transition.observed_state,
                transition.observed_level_delta,
            )
        )
    return tuple(losses)


def history_to_records(history: History, *, win_levels: int) -> tuple[dict[str, Any], ...]:
    """Serialize a bounded domain history into the trace's inert value language."""

    records: list[dict[str, Any]] = []
    for index, grid in enumerate(history.frames):
        action = history.actions[index]
        records.append(
            {
                "grid": grid.tolist(),
                "action": None if action is None else action_to_record(action),
                "available_actions": tuple(
                    action_kind.name
                    for action_kind in sorted(history.available_action_sets[index], key=int)
                ),
                "game_state": history.game_states[index].value,
                "level_delta": history.level_deltas[index],
                "level": history.levels[index],
                "win_levels": win_levels,
            }
        )
    return tuple(records)


def history_from_records(records: tuple[dict[str, Any], ...]) -> History:
    frames = []
    actions = []
    available_action_sets = []
    game_states = []
    level_deltas = []
    levels = []
    for record in records:
        frames.append(np.asarray(record["grid"], dtype=np.int16))
        raw_action = record.get("action")
        actions.append(None if raw_action is None else action_from_record(raw_action))
        available_action_sets.append(
            frozenset(ActionKind.coerce(item) for item in record["available_actions"])
        )
        game_states.append(GameState.coerce(record["game_state"]))
        level_deltas.append(int(record["level_delta"]))
        levels.append(int(record["level"]))
    return History(
        frames=tuple(frames),
        actions=tuple(actions),
        available_action_sets=tuple(available_action_sets),
        game_states=tuple(game_states),
        level_deltas=tuple(level_deltas),
        levels=tuple(levels),
    )


def action_to_record(action: Action) -> dict[str, Any]:
    value: dict[str, Any] = {"kind": action.kind.name}
    if action.kind is ActionKind.ACTION6:
        value.update({"row": action.row, "col": action.col})
    return value


def action_from_record(value: dict[str, Any]) -> Action:
    kind = ActionKind.coerce(value["kind"])
    return Action(
        kind,
        row=int(value["row"]) if kind is ActionKind.ACTION6 else None,
        col=int(value["col"]) if kind is ActionKind.ACTION6 else None,
    )


__all__ = [
    "ReplayTransition",
    "action_from_record",
    "action_to_record",
    "canonical_trace_hash",
    "dump_transitions",
    "history_from_records",
    "history_to_records",
    "load_transitions",
    "replay_prequential_losses",
]
