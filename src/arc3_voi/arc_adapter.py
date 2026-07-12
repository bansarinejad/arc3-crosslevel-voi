"""ARC toolkit boundary with competition-mode lifecycle guards."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

import numpy as np

from .splitting import GameMetadata
from .types import Action, ActionKind, GameState, Observation


class ArcAdapterError(RuntimeError):
    pass


class EnvironmentSession(Protocol):
    game_id: str

    def initial_observation(self) -> Observation: ...

    def step(self, action: Action, *, reasoning: dict[str, Any] | None = None) -> Observation: ...


class ArcEnvironmentSession:
    """Wrap one already-created ARC environment."""

    def __init__(self, game_id: str, environment: Any, initial_raw: Any | None = None) -> None:
        self.game_id = game_id
        self._environment = environment
        self._latest_raw = initial_raw or getattr(environment, "observation_space", None)
        if self._latest_raw is None:
            raise ArcAdapterError(f"environment {game_id} has no initial observation")

    def initial_observation(self) -> Observation:
        return observation_from_raw(self._latest_raw)

    def step(
        self, action: Action, *, reasoning: dict[str, Any] | None = None
    ) -> Observation:
        if action.kind is ActionKind.RESET:
            current = observation_from_raw(self._latest_raw)
            if current.game_state is not GameState.GAME_OVER:
                raise ArcAdapterError("speculative resets are forbidden")
            raw = self._environment.reset()
        else:
            game_action = _official_game_action(action.kind)
            raw = self._environment.step(
                game_action,
                data=action.to_official_args(),
                reasoning=reasoning,
            )
        if raw is None:
            raise ArcAdapterError(f"{self.game_id} returned no frame for {action.kind.name}")
        self._latest_raw = raw
        return observation_from_raw(raw)


class ArcCompetitionClient:
    """Open one competition-mode client and make every environment at most once."""

    def __init__(self, arcade: Any | None = None) -> None:
        self._arcade = arcade or _build_competition_arcade()
        self._made: set[str] = set()

    def make(self, game_id: str, *, seed: int = 0) -> ArcEnvironmentSession:
        stable_id = game_id.split("-", 1)[0]
        if stable_id in self._made:
            raise ArcAdapterError(f"competition mode permits make only once for {stable_id}")
        environment = self._arcade.make(
            game_id,
            seed=seed,
            include_frame_data=True,
        )
        if environment is None:
            raise ArcAdapterError(f"could not create environment {game_id}")
        self._made.add(stable_id)
        return ArcEnvironmentSession(game_id, environment)

    def public_metadata(self) -> list[GameMetadata]:
        result = []
        for info in self._arcade.get_environments():
            full_id = str(_field(info, "game_id", ""))
            stable, _, version = full_id.partition("-")
            baselines = tuple(
                int(value) for value in (_field(info, "baseline_actions", ()) or ())
            )
            tags = tuple(str(value) for value in (_field(info, "tags", ()) or ()))
            win_levels = int(_field(info, "win_levels", len(baselines) or 1))
            result.append(GameMetadata(stable, version or "unknown", tags, win_levels, baselines))
        return result

    def get_scorecard(self) -> None:
        raise ArcAdapterError("inflight scorecard access is forbidden in competition mode")


def observation_from_raw(raw: Any) -> Observation:
    frame = np.asarray(_field(raw, "frame", raw))
    if frame.ndim == 3:
        frame = frame[-1]
    if frame.ndim != 2:
        raise ArcAdapterError(f"expected one or more 2-D frames, got shape {frame.shape}")
    if not np.all(np.isfinite(frame)) or not np.all(frame == np.floor(frame)):
        raise ArcAdapterError("frame cells must be finite integers")
    frame = frame.astype(np.int16, copy=False)
    available = frozenset(
        ActionKind.coerce(getattr(value, "value", value))
        for value in _field(raw, "available_actions", ())
    )
    state_name = getattr(_field(raw, "state", "NOT_FINISHED"), "name", None)
    if state_name is None:
        state_name = str(_field(raw, "state", "NOT_FINISHED")).split(".")[-1]
    if state_name == "NOT_STARTED":
        state_name = "GAME_OVER"
    levels_completed = int(_field(raw, "levels_completed", 0))
    win_levels = max(1, int(_field(raw, "win_levels", levels_completed + 1)))
    level = min(win_levels, levels_completed + 1)
    return Observation(frame, available, GameState.coerce(state_name), level, win_levels)


def _build_competition_arcade() -> Any:
    # On managed Windows machines Requests' bundled CA file may not contain the
    # enterprise proxy root. truststore uses the OS certificate store without
    # disabling verification; Kaggle/Linux works normally when it is absent.
    try:  # pragma: no cover - platform/environment dependent
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    try:
        from arc_agi import Arcade, OperationMode
    except ImportError as exc:  # pragma: no cover - optional ARC dependency
        raise ArcAdapterError("install the 'arc' optional dependency") from exc
    return Arcade(operation_mode=OperationMode.COMPETITION)


def _official_game_action(kind: ActionKind) -> Any:
    try:
        from arcengine import GameAction
    except ImportError:  # pragma: no cover - optional ARC dependency
        return int(kind)
    # arcengine encodes action class as part of Enum identity, so constructing
    # from the displayed integer value is invalid even though `.value` is int.
    return GameAction[kind.name]


def _field(value: Any, name: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def action_names(values: Iterable[ActionKind]) -> tuple[str, ...]:
    return tuple(value.name for value in values)
