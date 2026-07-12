from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

from arc3_voi.controller import Variant
from arc3_voi.grounding_repair import generate_grounded_program_batches
from arc3_voi.model import GenerationResult
from arc3_voi.types import ActionKind, GameState, History, Observation

INVALID_PROGRAM = """
import socket
def predict(history, action):
    return {}
def goal_value(history):
    return 0.0
"""

CONSERVATIVE = """
def predict(history, action):
    return {
        "next_grid": history.frames[-1].copy(),
        "game_state": "NOT_FINISHED",
        "level_delta": 0,
        "memory": {},
    }
def goal_value(history):
    return 0.0
"""

GRADED_FIRST = """
def predict(history, action):
    grid = history.frames[-1].copy()
    grid[0, 0] = int(action.kind) % 2
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return float(np.clip(history.frames[-1][0, 0], 0.0, 1.0))
"""

GRADED_SECOND = """
def predict(history, action):
    grid = history.frames[-1].copy()
    grid[0, 1] = (int(action.kind) + 1) % 2
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {}}
def goal_value(history):
    return float(np.clip(history.frames[-1][0, 1], 0.0, 1.0))
"""


class _QueuedBackend:
    def __init__(self, batches: Sequence[GenerationResult]) -> None:
        self.batches = list(batches)
        self.calls: list[dict[str, Any]] = []

    def generate_programs(
        self,
        history: Any,
        count: int,
        *,
        feedback: str | None = None,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult:
        del history
        self.calls.append(
            {
                "count": count,
                "feedback": feedback,
                "max_new_tokens": max_new_tokens,
                "max_wall_seconds": max_wall_seconds,
            }
        )
        return self.batches.pop(0)

    def direct_action(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("direct action is not part of this helper test")


def _history() -> History:
    return History.from_observation(
        Observation(
            np.zeros((4, 4), dtype=np.int8),
            frozenset({ActionKind.ACTION1, ActionKind.ACTION2}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=3,
        )
    )


def _result(programs: Sequence[str], tokens: int) -> GenerationResult:
    return GenerationResult(tuple(programs), tokens, 1.0)


def _generate(
    backend: _QueuedBackend,
    *,
    variant: Variant = Variant.CROSS_LEVEL,
    tokens: int = 100,
    wall: float = 100.0,
    batches: int = 3,
):
    return generate_grounded_program_batches(
        backend,
        _history(),
        variant=variant,
        target=1 if variant is Variant.SINGLE else 4,
        initial_feedback=None,
        max_new_tokens_per_hypothesis=20,
        max_candidates=12,
        timeout_seconds=1.0,
        memory_limit_mb=256,
        rollout_depth=4,
        remaining_generated_tokens=tokens,
        remaining_wall_seconds=wall,
        remaining_generation_batches=batches,
    )


def test_failed_initial_committee_gets_exactly_one_source_free_repair_batch() -> None:
    backend = _QueuedBackend(
        [
            _result([INVALID_PROGRAM] * 4, 20),
            _result([CONSERVATIVE, GRADED_FIRST, GRADED_SECOND, INVALID_PROGRAM], 30),
        ]
    )

    generated = _generate(backend)

    assert len(backend.calls) == 2
    feedback = backend.calls[1]["feedback"]
    assert isinstance(feedback, str)
    assert "sandbox_invalid=4" in feedback
    assert "History is an attribute-only record" in feedback
    assert "grid.shape" in feedback
    assert "import socket" not in feedback
    assert generated.output_tokens == 50
    assert generated.repair_attempts == 1
    assert [item.batch_index for item in generated.programs] == [0] * 4 + [1] * 4
    assert [item.candidate_index for item in generated.programs] == [0, 1, 2, 3] * 2
    assert [item.graded_role for item in generated.programs] == [
        False,
        True,
        True,
        True,
    ] * 2


@pytest.mark.parametrize(
    ("tokens", "wall", "batches"),
    [
        (23, 100.0, 3),  # The first batch uses 20; four repair slots cannot fit.
        (100, 100.0, 1),  # The global batch cap has no repair slot.
    ],
)
def test_repair_is_refused_when_token_or_batch_budget_cannot_fit(
    tokens: int, wall: float, batches: int
) -> None:
    backend = _QueuedBackend([_result([INVALID_PROGRAM] * 4, 20)])

    generated = _generate(backend, tokens=tokens, wall=wall, batches=batches)

    assert len(backend.calls) == 1
    assert generated.repair_attempts == 0
    assert generated.output_tokens == 20


def test_repair_is_refused_after_first_batch_exhausts_wall_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter((10.0, 16.0))
    monkeypatch.setattr("arc3_voi.grounding_repair.time.monotonic", lambda: next(ticks))
    backend = _QueuedBackend([_result([INVALID_PROGRAM] * 4, 20)])

    generated = _generate(backend, wall=5.0)

    assert len(backend.calls) == 1
    assert generated.repair_attempts == 0


def test_single_arm_repairs_only_candidate_zero_and_never_attempts_a_third_batch() -> None:
    backend = _QueuedBackend(
        [
            _result([INVALID_PROGRAM], 2),
            _result([INVALID_PROGRAM], 2),
        ]
    )

    generated = _generate(backend, variant=Variant.SINGLE)

    assert [call["count"] for call in backend.calls] == [1, 1]
    assert len(generated.batches) == 2
    assert [item.candidate_index for item in generated.programs] == [0, 0]
    assert all(not item.graded_role for item in generated.programs)


def test_complete_initial_committee_does_not_spend_repair_budget() -> None:
    backend = _QueuedBackend(
        [_result([CONSERVATIVE, GRADED_FIRST, GRADED_SECOND, INVALID_PROGRAM], 20)]
    )

    generated = _generate(backend)

    assert len(backend.calls) == 1
    assert generated.repair_attempts == 0
    assert generated.repair_feedback is None


def test_initial_backend_token_overreport_fails_closed() -> None:
    backend = _QueuedBackend([_result([INVALID_PROGRAM] * 4, 101)])

    with pytest.raises(ValueError, match="initial generation reported output"):
        _generate(backend, tokens=100)

    assert len(backend.calls) == 1


def test_cumulative_repair_backend_token_overreport_fails_closed() -> None:
    backend = _QueuedBackend(
        [
            _result([INVALID_PROGRAM] * 4, 20),
            _result([CONSERVATIVE, GRADED_FIRST, GRADED_SECOND, INVALID_PROGRAM], 81),
        ]
    )

    with pytest.raises(ValueError, match="repair generation reported output"):
        _generate(backend, tokens=100)

    assert len(backend.calls) == 2
