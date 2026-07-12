"""Adapter from validated generated source to the public Hypothesis protocol."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from math import isfinite
from typing import Any

import numpy as np

from .runtime.sandbox import ValidatedProgram, validate_program
from .runtime.worker import ProgramWorker
from .types import Action, GameState, History, Prediction


class ProgramExecutionError(RuntimeError):
    """A generated program failed at a typed controller boundary."""


class ExecutableHypothesis:
    """Persistent restricted worker implementing transition and goal prediction."""

    def __init__(
        self,
        source: str,
        *,
        timeout_seconds: float = 0.100,
        memory_limit_mb: int = 256,
    ) -> None:
        self.source = source
        self.validated: ValidatedProgram = validate_program(source)
        self.hypothesis_id = self.validated.sha256
        self.ast_nodes = self.validated.node_count
        self.candidate_points = _candidate_points(self.validated.canonical_source)
        self.prediction_calls = 0
        self.goal_calls = 0
        self.timeout_count = 0
        self.execution_error_count = 0
        self._worker = ProgramWorker(
            source,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
        )

    def predict(self, history: History, action: Action) -> Prediction:
        self.prediction_calls += 1
        result = self._worker.predict(history, action)
        if not result.ok:
            assert result.error is not None
            if result.error.kind.value == "timeout":
                self.timeout_count += 1
            else:
                self.execution_error_count += 1
            raise ProgramExecutionError(f"{result.error.kind}: {result.error.message}")
        value = result.value
        if not isinstance(value, Mapping):
            raise ProgramExecutionError("predict must return a mapping")
        missing = {"next_grid", "game_state", "level_delta"} - set(value)
        if missing:
            raise ProgramExecutionError(f"predict result is missing {sorted(missing)}")
        grid = np.asarray(value["next_grid"])
        if grid.shape != history.latest_grid.shape:
            raise ProgramExecutionError(
                f"next_grid shape {grid.shape} does not match current {history.latest_grid.shape}"
            )
        if grid.ndim != 2 or not np.issubdtype(grid.dtype, np.integer):
            raise ProgramExecutionError("next_grid must be a two-dimensional integer grid")
        if grid.size and (int(grid.min()) < 0 or int(grid.max()) > 15):
            raise ProgramExecutionError("next_grid values must be in [0, 15]")
        memory = value.get("memory", {})
        if not isinstance(memory, Mapping):
            raise ProgramExecutionError("memory must be a mapping")
        try:
            return Prediction(
                next_grid=grid,
                game_state=GameState.coerce(value["game_state"]),
                level_delta=int(value["level_delta"]),
                memory=dict(memory),
            )
        except (TypeError, ValueError) as exc:
            raise ProgramExecutionError(f"invalid prediction result: {exc}") from exc

    def goal_value(self, history: History) -> float:
        self.goal_calls += 1
        result = self._worker.goal_value(history)
        if not result.ok:
            assert result.error is not None
            if result.error.kind.value == "timeout":
                self.timeout_count += 1
            else:
                self.execution_error_count += 1
            raise ProgramExecutionError(f"{result.error.kind}: {result.error.message}")
        assert result.value is not None
        value = float(result.value)
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            self.execution_error_count += 1
            raise ProgramExecutionError("goal_value must be finite and in [0, 1]")
        return value

    @property
    def alive(self) -> bool:
        return self._worker.alive

    def close(self) -> None:
        self._worker.close()

    def __enter__(self) -> ExecutableHypothesis:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()


def _candidate_points(source: str) -> tuple[tuple[int, int], ...]:
    """Read the optional literal CANDIDATE_POINTS declaration without executing it."""

    tree = ast.parse(source, mode="exec")
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "CANDIDATE_POINTS"
            for target in statement.targets
        ):
            continue
        try:
            value = ast.literal_eval(statement.value)
        except (ValueError, TypeError, SyntaxError):
            return ()
        points: list[tuple[int, int]] = []
        if not isinstance(value, list | tuple):
            return ()
        for item in value[:32]:
            if (
                isinstance(item, list | tuple)
                and len(item) == 2
                and all(
                    isinstance(coordinate, int) and not isinstance(coordinate, bool)
                    for coordinate in item
                )
            ):
                row, col = int(item[0]), int(item[1])
                if 0 <= row < 64 and 0 <= col < 64:
                    points.append((row, col))
        return tuple(dict.fromkeys(points))
    return ()
