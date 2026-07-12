"""Core immutable domain types for ARC-AGI-3 interaction.

The controller uses row/column coordinates internally because that is the natural
indexing convention for NumPy grids.  The ARC-AGI-3 API expects mouse coordinates
as ``x``/``y``; :class:`Action` is the single conversion boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import IntEnum, StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any, ClassVar, TypeAlias

import numpy as np
import numpy.typing as npt

Grid: TypeAlias = npt.NDArray[np.int16]  # noqa: UP040 - current mypy lacks PEP 695
DiagnosticValue: TypeAlias = str | int | float | bool | None  # noqa: UP040


def freeze_grid(value: npt.ArrayLike) -> Grid:
    """Validate, copy, and make a grid read-only.

    ARC-AGI-3 frames occupy at most a 64 by 64 canvas.  Smaller grids are useful
    for deterministic unit tests and synthetic theory examples, so they remain
    valid domain values.
    """

    source = np.asarray(value)
    if source.ndim != 2:
        raise ValueError("a grid must be a two-dimensional array")
    if not source.size or source.shape[0] > 64 or source.shape[1] > 64:
        raise ValueError("grid dimensions must each be between 1 and 64")
    if not np.issubdtype(source.dtype, np.integer):
        raise TypeError("grid cells must have an integer dtype")
    if source.size and (int(source.min()) < np.iinfo(np.int16).min or int(source.max()) > 255):
        raise ValueError("grid cell values must be in the range [-32768, 255]")

    grid = np.array(source, dtype=np.int16, copy=True, order="C")
    grid.flags.writeable = False
    return grid


class ActionKind(IntEnum):
    """Official ARC-AGI-3 action identifiers."""

    RESET = 0
    ACTION1 = 1
    ACTION2 = 2
    ACTION3 = 3
    ACTION4 = 4
    ACTION5 = 5
    ACTION6 = 6
    ACTION7 = 7

    @classmethod
    def coerce(cls, value: ActionKind | int | str) -> ActionKind:
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise TypeError("an action kind cannot be boolean")
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized.isdecimal():
                return cls(int(normalized))
            try:
                return cls[normalized]
            except KeyError as exc:
                raise ValueError(f"unknown action kind: {value!r}") from exc
        if not isinstance(value, int):
            raise TypeError("an action kind must be an integer, name, or ActionKind")
        return cls(value)


class GameState(StrEnum):
    """Stable game states exposed by the ARC environment."""

    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"

    @classmethod
    def coerce(cls, value: GameState | str) -> GameState:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError as exc:
            raise ValueError(f"unknown game state: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class Action:
    """An immutable internal action using NumPy-style row/column coordinates."""

    kind: ActionKind
    row: int | None = None
    col: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ActionKind.coerce(self.kind))

        is_click = self.kind is ActionKind.ACTION6
        if is_click and (self.row is None or self.col is None):
            raise ValueError("ACTION6 requires both row and col")
        if not is_click and (self.row is not None or self.col is not None):
            raise ValueError("only ACTION6 accepts row and col")
        for name, coordinate in (("row", self.row), ("col", self.col)):
            if coordinate is not None:
                if isinstance(coordinate, bool) or not isinstance(coordinate, int):
                    raise TypeError(f"{name} must be an integer")
                if not 0 <= coordinate < 64:
                    raise ValueError(f"{name} must be in the range [0, 63]")

    def to_official_args(self) -> dict[str, int]:
        """Return official ARC API arguments, translating ``col,row`` to ``x,y``."""

        if self.kind is not ActionKind.ACTION6:
            return {}
        assert self.row is not None and self.col is not None
        return {"x": self.col, "y": self.row}

    def as_official(self) -> tuple[int, dict[str, int]]:
        """Return the numeric action identifier and its official argument mapping."""

        return int(self.kind), self.to_official_args()


def _freeze_action_set(values: Iterable[ActionKind]) -> frozenset[ActionKind]:
    return frozenset(ActionKind.coerce(value) for value in values)


@dataclass(frozen=True, slots=True, eq=False)
class Observation:
    """A stable environment observation and its exposed level metadata."""

    grid: Grid
    available_actions: frozenset[ActionKind]
    game_state: GameState
    level: int
    win_levels: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", freeze_grid(self.grid))
        object.__setattr__(self, "available_actions", _freeze_action_set(self.available_actions))
        object.__setattr__(self, "game_state", GameState.coerce(self.game_state))
        if isinstance(self.level, bool) or not isinstance(self.level, int) or self.level < 1:
            raise ValueError("level must be a positive integer")
        if (
            isinstance(self.win_levels, bool)
            or not isinstance(self.win_levels, int)
            or self.win_levels < self.level
        ):
            raise ValueError("win_levels must be an integer no smaller than level")


@dataclass(frozen=True, slots=True, eq=False)
class History:
    """The aligned, last-eight stable observations used by executable programs.

    ``actions[i]`` is the action whose result produced ``frames[i]``.  It is
    normally ``None`` for the first observed frame.  Keeping every field aligned
    avoids off-by-one ambiguity when a bounded-history program is serialized.
    """

    MAX_LENGTH: ClassVar[int] = 8

    frames: tuple[Grid, ...] = ()
    actions: tuple[Action | None, ...] = ()
    available_action_sets: tuple[frozenset[ActionKind], ...] = ()
    game_states: tuple[GameState, ...] = ()
    level_deltas: tuple[int, ...] = ()
    levels: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        lengths = {
            len(self.frames),
            len(self.actions),
            len(self.available_action_sets),
            len(self.game_states),
            len(self.level_deltas),
            len(self.levels),
        }
        if len(lengths) != 1:
            raise ValueError("all History fields must have the same length")
        if len(self.frames) > self.MAX_LENGTH:
            raise ValueError(f"History contains more than {self.MAX_LENGTH} frames")

        object.__setattr__(self, "frames", tuple(freeze_grid(frame) for frame in self.frames))
        object.__setattr__(
            self,
            "available_action_sets",
            tuple(_freeze_action_set(action_set) for action_set in self.available_action_sets),
        )
        object.__setattr__(
            self,
            "game_states",
            tuple(GameState.coerce(state) for state in self.game_states),
        )
        for delta in self.level_deltas:
            if isinstance(delta, bool) or not isinstance(delta, int):
                raise TypeError("level deltas must be integers")
        for level in self.levels:
            if isinstance(level, bool) or not isinstance(level, int) or level < 1:
                raise ValueError("history levels must be positive integers")

    @classmethod
    def empty(cls) -> History:
        return cls()

    @classmethod
    def from_observation(cls, observation: Observation) -> History:
        return cls().append(observation, action=None, level_delta=0)

    def append(
        self,
        observation: Observation,
        action: Action | None,
        level_delta: int,
    ) -> History:
        """Return a history with an observation appended and the oldest item trimmed."""

        if isinstance(level_delta, bool) or not isinstance(level_delta, int):
            raise TypeError("level_delta must be an integer")
        start = max(0, len(self.frames) + 1 - self.MAX_LENGTH)
        return History(
            frames=(*self.frames[start:], observation.grid),
            actions=(*self.actions[start:], action),
            available_action_sets=(
                *self.available_action_sets[start:],
                observation.available_actions,
            ),
            game_states=(*self.game_states[start:], observation.game_state),
            level_deltas=(*self.level_deltas[start:], level_delta),
            levels=(*self.levels[start:], observation.level),
        )

    @property
    def latest_grid(self) -> Grid:
        if not self.frames:
            raise IndexError("an empty History has no latest grid")
        return self.frames[-1]

    @property
    def latest_action_set(self) -> frozenset[ActionKind]:
        if not self.available_action_sets:
            raise IndexError("an empty History has no latest action set")
        return self.available_action_sets[-1]

    @property
    def action_sets(self) -> tuple[frozenset[ActionKind], ...]:
        """Concise controller alias for the canonical serialized field name."""

        return self.available_action_sets

    @property
    def latest_game_state(self) -> GameState:
        if not self.game_states:
            raise IndexError("an empty History has no latest game state")
        return self.game_states[-1]

    @property
    def current_level(self) -> int:
        if not self.levels:
            raise IndexError("an empty History has no current level")
        return self.levels[-1]


@dataclass(frozen=True, slots=True, eq=False)
class Prediction:
    """A hypothesis's pre-action transition prediction."""

    next_grid: Grid
    game_state: GameState
    level_delta: int
    memory: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "next_grid", freeze_grid(self.next_grid))
        object.__setattr__(self, "game_state", GameState.coerce(self.game_state))
        if isinstance(self.level_delta, bool) or not isinstance(self.level_delta, int):
            raise TypeError("level_delta must be an integer")
        object.__setattr__(self, "memory", MappingProxyType(dict(self.memory)))

    def signature(self) -> tuple[tuple[int, int], bytes, GameState, int]:
        """Return the exact observable signature used for committee clustering."""

        shape = (int(self.next_grid.shape[0]), int(self.next_grid.shape[1]))
        return shape, self.next_grid.tobytes(order="C"), self.game_state, self.level_delta


class DecisionMode(StrEnum):
    EXPLOIT = "exploit"
    PROBE = "probe"
    REFRESH = "refresh"
    DIRECT_FALLBACK = "direct_fallback"


@dataclass(frozen=True, slots=True)
class Decision:
    """A selected environment action plus an attributable decision mode."""

    action: Action
    mode: DecisionMode
    score: float
    diagnostics: Mapping[str, DiagnosticValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, DecisionMode):
            object.__setattr__(self, "mode", DecisionMode(self.mode))
        if not isfinite(self.score):
            raise ValueError("decision score must be finite")
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


@dataclass(frozen=True, slots=True)
class Budget:
    """Shared action, generation-token, and wall-time budget."""

    max_environment_actions: int = 256
    environment_actions_used: int = 0
    max_generated_tokens: int = 12_288
    generated_tokens_used: int = 0
    max_wall_seconds: float = 1_200.0
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        integer_fields = (
            ("max_environment_actions", self.max_environment_actions),
            ("environment_actions_used", self.environment_actions_used),
            ("max_generated_tokens", self.max_generated_tokens),
            ("generated_tokens_used", self.generated_tokens_used),
        )
        for name, value in integer_fields:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_environment_actions < 1 or self.max_generated_tokens < 1:
            raise ValueError("budget maxima must be positive")
        if self.environment_actions_used > self.max_environment_actions:
            raise ValueError("environment action usage exceeds its maximum")
        if self.generated_tokens_used > self.max_generated_tokens:
            raise ValueError("generated token usage exceeds its maximum")
        if not isfinite(self.max_wall_seconds) or self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be finite and positive")
        if not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and non-negative")

    @property
    def remaining_environment_actions(self) -> int:
        return self.max_environment_actions - self.environment_actions_used

    @property
    def remaining_generated_tokens(self) -> int:
        return self.max_generated_tokens - self.generated_tokens_used

    @property
    def remaining_wall_seconds(self) -> float:
        return max(0.0, self.max_wall_seconds - self.elapsed_seconds)

    @property
    def exhausted(self) -> bool:
        return (
            self.remaining_environment_actions == 0
            or self.remaining_generated_tokens == 0
            or self.remaining_wall_seconds == 0.0
        )

    def can_afford(
        self,
        *,
        environment_actions: int = 0,
        generated_tokens: int = 0,
        wall_seconds: float = 0.0,
    ) -> bool:
        if environment_actions < 0 or generated_tokens < 0 or wall_seconds < 0:
            raise ValueError("requested budget consumption cannot be negative")
        return (
            environment_actions <= self.remaining_environment_actions
            and generated_tokens <= self.remaining_generated_tokens
            and wall_seconds <= self.remaining_wall_seconds
        )

    def consume(
        self,
        *,
        environment_actions: int = 0,
        generated_tokens: int = 0,
        wall_seconds: float = 0.0,
    ) -> Budget:
        if not self.can_afford(
            environment_actions=environment_actions,
            generated_tokens=generated_tokens,
            wall_seconds=wall_seconds,
        ):
            raise ValueError("budget exhausted")
        return replace(
            self,
            environment_actions_used=self.environment_actions_used + environment_actions,
            generated_tokens_used=self.generated_tokens_used + generated_tokens,
            elapsed_seconds=self.elapsed_seconds + wall_seconds,
        )
