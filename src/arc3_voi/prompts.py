"""Prompt construction and robust parsing for the single-backbone agent modes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from .rendering import ARC_PALETTE_LEGEND, GRID_LINE_RGB

PROMPT_CONTRACT_VERSION = "grounded-actions-palette-v1"
PROGRAM_ACTION_CONTRACT = """Action kinds are opaque numeric labels: RESET=0,
ACTION1=1, ACTION2=2, ACTION3=3, ACTION4=4, ACTION5=5, ACTION6=6, ACTION7=7.
Only ACTION6 carries coordinates. For ACTION6, row and col are integers in [0,63].
For every other kind, row and col are None. Branch on int(action.kind) == 6 before
reading or doing arithmetic with action.row/action.col. Never assume that ACTION1-5
or ACTION7 have universal arrow, key, or button meanings; infer each effect from history.
"""

DIRECT_ACTION_CONTRACT = """The valid_actions list is exhaustive. Return one listed
action exactly. If selecting ACTION6, copy one exact listed row/col pair; never invent
a coordinate or use enlarged-image pixels. Omit coordinates for ACTION1-5 and ACTION7.
Action names are opaque, so infer effects from history rather than assuming key meanings.
"""

VISUAL_GROUNDING_CONTRACT = (
    "Each rendered cell interior uses this exact symbolic palette: "
    + ARC_PALETTE_LEGEND
    + f". Grid separator lines are RGB{GRID_LINE_RGB} and are not cell values. "
    "Each history entry also lists the exact grid_values present in its image.\n"
)

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
History images are ordered oldest to newest; grid_image_index is zero based and the
final image is the latest frame.
""" + PROGRAM_ACTION_CONTRACT + VISUAL_GROUNDING_CONTRACT + """
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
    kind = int(action.kind)
    if kind == 6:
        row = int(action.row)
        col = int(action.col)
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}

def goal_value(history):
    return 0.0
"""

DIRECT_SYSTEM_PROMPT = """You control a novel ARC-AGI-3 grid game.
Choose exactly one currently valid action. Return only compact JSON:
{"kind":"ACTION1"} or {"kind":"ACTION6","row":12,"col":34}.
Rows and columns are zero based in [0, 63]. Do not include markdown.
History images are ordered oldest to newest; grid_image_index is zero based and the
final image is the latest frame.
""" + DIRECT_ACTION_CONTRACT + VISUAL_GROUNDING_CONTRACT

_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def grid_to_ascii(grid: Any) -> str:
    """Serialize a 2-D grid compactly without depending on NumPy."""

    rows = getattr(grid, "tolist", lambda: grid)()
    return "\n".join("".join(format(int(value), "x") for value in row) for row in rows)


def history_payload(
    history: Any, *, include_grid_ascii: bool = True
) -> list[dict[str, Any]]:
    """Convert history to stable metadata, optionally embedding exact ASCII grids.

    Model prompts use ordered image blocks and therefore disable the ASCII grids.
    Keeping the explicit option preserves a dependency-free exact serialization for
    diagnostics without paying for every 64x64 frame twice in the live prompt.
    """

    payload: list[dict[str, Any]] = []
    if hasattr(history, "frames") and hasattr(history, "available_action_sets"):
        entries = (
            _HistoryEntry(
                grid=grid,
                action=action,
                available_actions=actions,
                game_state=state,
                level_delta=delta,
                level=level,
            )
            for grid, action, actions, state, delta, level in zip(
                history.frames,
                history.actions,
                history.available_action_sets,
                history.game_states,
                history.level_deltas,
                history.levels,
                strict=True,
            )
        )
    else:
        entries = iter(history)
    bounded_entries = tuple(entries)[-8:]
    for image_index, entry in enumerate(bounded_entries):
        grid = getattr(entry, "grid", None)
        action = getattr(entry, "action", None)
        available_actions = sorted(
            getattr(entry, "available_actions", ()),
            key=_action_kind_sort_key,
        )
        entry_payload = {
            "action": None if action is None else _action_payload(action),
            "available_actions": [
                getattr(action_kind, "name", str(action_kind))
                for action_kind in available_actions
            ],
            "game_state": getattr(
                getattr(entry, "game_state", "NOT_FINISHED"),
                "value",
                str(getattr(entry, "game_state", "NOT_FINISHED")),
            ),
            "level_delta": int(getattr(entry, "level_delta", 0)),
            "level": int(getattr(entry, "level", 1)),
            "grid_values": _grid_values(grid),
        }
        if include_grid_ascii:
            entry_payload["grid"] = grid_to_ascii(grid)
        else:
            entry_payload["grid_image_index"] = image_index
        payload.append(entry_payload)
    return payload


def _action_kind_sort_key(action_kind: Any) -> tuple[int, str]:
    """Order the frozen ARC action vocabulary independently of set iteration."""

    name = str(getattr(action_kind, "name", action_kind))
    if name == "RESET":
        return (0, name)
    if name.startswith("ACTION") and name[6:].isdigit():
        return (int(name[6:]), name)
    return (2**31 - 1, name)


def _grid_values(grid: Any) -> list[int]:
    rows = getattr(grid, "tolist", lambda: grid)()
    return sorted({int(value) for row in rows for value in row})


def program_prompt(history: Any, *, feedback: str | None = None) -> str:
    request = {
        "frame_encoding": "grid_image_index refers to ordered images, oldest first",
        "history": history_payload(history, include_grid_ascii=False),
        "instruction": "Infer one behaviorally plausible transition-and-goal program.",
    }
    if feedback:
        request["contradiction_feedback"] = feedback
    return json.dumps(request, separators=(",", ":"), sort_keys=True)


def direct_prompt(history: Any, valid_actions: Iterable[str]) -> str:
    request = {
        "frame_encoding": "grid_image_index refers to ordered images, oldest first",
        "history": history_payload(history, include_grid_ascii=False),
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
        level: int,
    ) -> None:
        self.grid = grid
        self.action = action
        self.available_actions = available_actions
        self.game_state = game_state
        self.level_delta = level_delta
        self.level = level


class _ReferenceAction:
    def __init__(self, kind: str, row: int | None = None, col: int | None = None) -> None:
        self.kind = kind
        self.row = row
        self.col = col


_REFERENCE_HISTORY = tuple(
    _HistoryEntry(
        grid=((index % 16, 5), (10, 14)),
        action=(
            None
            if index == 0
            else _ReferenceAction("ACTION6", 12, 34)
            if index == 9
            else _ReferenceAction("ACTION3")
        ),
        available_actions=("ACTION7", "ACTION3", "ACTION6"),
        game_state="NOT_FINISHED",
        level_delta=index % 2,
        level=1 + index // 5,
    )
    for index in range(10)
)
PROMPT_REFERENCE_PROGRAM_SHA256 = hashlib.sha256(
    program_prompt(_REFERENCE_HISTORY).encode("utf-8")
).hexdigest()
PROMPT_REFERENCE_DIRECT_SHA256 = hashlib.sha256(
    direct_prompt(
        _REFERENCE_HISTORY,
        ("ACTION3", "ACTION7", "ACTION6(row=12,col=34)"),
    ).encode("utf-8")
).hexdigest()
PROMPT_CONTRACT_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "direct_reference_sha256": PROMPT_REFERENCE_DIRECT_SHA256,
            "direct_system_prompt": DIRECT_SYSTEM_PROMPT,
            "program_reference_sha256": PROMPT_REFERENCE_PROGRAM_SHA256,
            "program_system_prompt": PROGRAM_SYSTEM_PROMPT,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()
