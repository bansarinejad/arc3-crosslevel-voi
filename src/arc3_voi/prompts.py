"""Prompt construction and robust parsing for the single-backbone agent modes."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

PROGRAM_SYSTEM_PROMPT = """You infer compact executable rules for a novel ARC-AGI-3 game.
Return only one Python program. The runtime preloads numpy as np. Do not import anything.
The program must define exactly:

def predict(history, action):
    # Return a dict with keys next_grid, game_state, level_delta, memory.

def goal_value(history):
    # Return a float in [0, 1].

history is a read-only record with aligned tuple fields: frames, actions,
available_action_sets, game_states, level_deltas, and levels. The newest frame is
history.frames[-1]. action is a read-only record with integer kind and optional row/col.
Copy a frame before changing it. Return a grid with the same shape and values in [0,15].
game_state must be exactly "NOT_FINISHED", "WIN", or "GAME_OVER". Available NumPy
operations include array/asarray, copy, zeros_like/ones_like/full_like, where, nonzero,
argwhere, unique, roll/flip/rot90, concatenate/stack, min/max/sum/mean, count_nonzero,
clip, and basic arithmetic/comparisons. Safe array methods include copy, astype, reshape,
flatten, tolist, nonzero, argmin/argmax, min/max/sum/mean/std. Local lists/sets may use
append, extend, add, and discard. Prefer short, general rules.
Never read files, use the network, or execute code. Do not use imports, classes,
decorators, type annotations, exceptions, context managers, or markdown. Keep the
whole program below 120 logical lines and define both required functions completely
before the token limit. You may optionally add a top-level literal
CANDIDATE_POINTS = [(row, col), ...] with promising ACTION6 coordinates from the
latest frame. A minimal contract-valid shape is:

def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int8)
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}

def goal_value(history):
    return 0.0
"""

DIRECT_SYSTEM_PROMPT = """You control a novel ARC-AGI-3 grid game.
Choose exactly one currently valid action. Return only compact JSON:
{"kind":"ACTION1"} or {"kind":"ACTION6","row":12,"col":34}.
Rows and columns are zero based in [0, 63]. Do not include markdown.
"""

_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def grid_to_ascii(grid: Any) -> str:
    """Serialize a 2-D grid compactly without depending on NumPy."""

    rows = getattr(grid, "tolist", lambda: grid)()
    return "\n".join("".join(format(int(value), "x") for value in row) for row in rows)


def history_payload(history: Any) -> list[dict[str, Any]]:
    """Convert domain history entries to a stable JSON-compatible prompt payload."""

    payload: list[dict[str, Any]] = []
    if hasattr(history, "frames") and hasattr(history, "available_action_sets"):
        entries = (
            _HistoryEntry(
                grid=grid,
                action=action,
                available_actions=actions,
                game_state=state,
                level_delta=delta,
            )
            for grid, action, actions, state, delta in zip(
                history.frames,
                history.actions,
                history.available_action_sets,
                history.game_states,
                history.level_deltas,
                strict=True,
            )
        )
    else:
        entries = iter(history)
    for entry in entries:
        grid = getattr(entry, "grid", None)
        action = getattr(entry, "action", None)
        payload.append(
            {
                "grid": grid_to_ascii(grid),
                "action": None if action is None else _action_payload(action),
                "available_actions": [
                    getattr(action_kind, "name", str(action_kind))
                    for action_kind in getattr(entry, "available_actions", ())
                ],
                "game_state": getattr(
                    getattr(entry, "game_state", "NOT_FINISHED"),
                    "value",
                    str(getattr(entry, "game_state", "NOT_FINISHED")),
                ),
                "level_delta": int(getattr(entry, "level_delta", 0)),
            }
        )
    return payload


def program_prompt(history: Any, *, feedback: str | None = None) -> str:
    request = {
        "history": history_payload(history),
        "instruction": "Infer one behaviorally plausible transition-and-goal program.",
    }
    if feedback:
        request["contradiction_feedback"] = feedback
    return json.dumps(request, separators=(",", ":"), sort_keys=True)


def direct_prompt(history: Any, valid_actions: Iterable[str]) -> str:
    request = {
        "history": history_payload(history),
        "valid_actions": list(valid_actions),
        "instruction": "Choose the safest action that advances or disambiguates the goal.",
    }
    return json.dumps(request, separators=(",", ":"), sort_keys=True)


def extract_python(text: str) -> str:
    """Extract a generated program while preserving plain-code responses."""

    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    fenced = [match.group(1) for match in _FENCE_RE.finditer(text)]
    complete = [
        block for block in fenced if "def predict" in block and "def goal_value" in block
    ]
    candidate = complete[-1] if complete else (fenced[-1] if fenced else text)
    if "def predict" in candidate:
        candidate = candidate[candidate.index("def predict") :]
    candidate = candidate.strip()
    if candidate.startswith("python\n"):
        candidate = candidate[7:]
    candidate = candidate.removesuffix("```").rstrip()
    return candidate.strip()


def parse_action_json(text: str) -> dict[str, Any]:
    """Parse the first valid action-shaped JSON object from model output."""

    candidates = [text.strip(), *[match.group(0) for match in _JSON_RE.finditer(text)]]
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict) and isinstance(value.get("kind"), str):
            return value
    raise ValueError("model output did not contain an action JSON object")


def _action_payload(action: Any) -> dict[str, Any]:
    kind = getattr(action, "kind", action)
    payload: dict[str, Any] = {"kind": getattr(kind, "name", str(kind))}
    row = getattr(action, "row", None)
    col = getattr(action, "col", None)
    if row is not None:
        payload["row"] = int(row)
    if col is not None:
        payload["col"] = int(col)
    return payload


class _HistoryEntry:
    """Small internal adapter for the canonical aligned History representation."""

    def __init__(
        self,
        *,
        grid: Any,
        action: Any,
        available_actions: Any,
        game_state: Any,
        level_delta: int,
    ) -> None:
        self.grid = grid
        self.action = action
        self.available_actions = available_actions
        self.game_state = game_state
        self.level_delta = level_delta
