from __future__ import annotations

import ast
import os
import textwrap
from dataclasses import dataclass

import numpy as np
import pytest

from arc3_voi.runtime.sandbox import (
    SandboxValidationError,
    ValidationCode,
    validate_program,
)
from arc3_voi.runtime.worker import (
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TIMEOUT_SECONDS,
    ProgramWorker,
    WorkerErrorKind,
)

VALID_PROGRAM = """
def predict(history, action):
    grid = np.asarray(history.frames[-1])
    result = np.copy(grid)
    if action.get("kind") == "ACTION6":
        result[action.row, action.col] = 7
    return {
        "next_grid": result,
        "game_state": "PLAYING",
        "level_delta": 0,
        "memory": {"observations": len(history.frames)},
    }

def goal_value(history):
    return min(1.0, len(history.frames) / 8.0)
"""


@dataclass(frozen=True)
class ExampleHistory:
    frames: tuple[np.ndarray, ...]
    actions: tuple[str, ...] = ()
    available_action_sets: tuple[frozenset[int], ...] = ()


@dataclass(frozen=True)
class ExampleAction:
    kind: str
    row: int | None = None
    col: int | None = None


def test_validation_canonicalizes_source_and_counts_ast_nodes() -> None:
    compact = validate_program(VALID_PROGRAM)
    reformatted = validate_program("\n\n" + textwrap.dedent(VALID_PROGRAM).replace("    ", "  "))

    assert compact.canonical_source.endswith("\n")
    assert compact.canonical_ast == reformatted.canonical_ast
    assert compact.sha256 == reformatted.sha256
    assert compact.node_count == sum(
        1 for _ in ast.walk(ast.parse(compact.canonical_source, mode="exec"))
    )
    assert compact.node_count > 0


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ("import os", ValidationCode.DISALLOWED_NODE),
        ("return open('secret.txt').read()", ValidationCode.DISALLOWED_CALL),
        ("return eval('1 + 1')", ValidationCode.DISALLOWED_CALL),
        ("return exec('x = 1')", ValidationCode.DISALLOWED_CALL),
        ("return history.__class__", ValidationCode.DISALLOWED_ATTRIBUTE),
        ("np.save('grid.npy', history.frames[-1])\n    return {}", ValidationCode.DISALLOWED_CALL),
        ("return history.system('whoami')", ValidationCode.DISALLOWED_CALL),
        ("helper = lambda: 1\n    return helper()", ValidationCode.DISALLOWED_NODE),
        ("while True:\n        pass\n    return {}", None),
    ],
)
def test_validator_rejects_unsafe_constructs(
    payload: str, expected_code: ValidationCode | None
) -> None:
    source = f"""
def predict(history, action):
    {payload}

def goal_value(history):
    return 0.0
"""
    if expected_code is None:
        # Infinite but otherwise ordinary computation is admitted statically and
        # stopped by the process deadline, rather than by fragile source heuristics.
        validate_program(source)
        return
    with pytest.raises(SandboxValidationError) as captured:
        validate_program(source)
    assert expected_code in {issue.code for issue in captured.value.issues}


def test_validator_requires_exact_public_contract() -> None:
    with pytest.raises(SandboxValidationError) as captured:
        validate_program(
            """
def predict(history):
    return {}
"""
        )

    messages = " ".join(issue.message for issue in captured.value.issues)
    assert "predict(history, action)" in messages
    assert "goal_value" in messages


def test_validator_rejects_top_level_execution_and_shadowing() -> None:
    with pytest.raises(SandboxValidationError) as captured:
        validate_program(
            """
x = np.zeros((2, 2))
def predict(history, action):
    len = 4
    return len
def goal_value(history):
    return 0.0
"""
        )

    codes = {issue.code for issue in captured.value.issues}
    assert ValidationCode.INVALID_TOP_LEVEL in codes
    assert ValidationCode.DISALLOWED_NAME in codes


def test_persistent_worker_executes_numpy_program_with_sanitized_dataclasses() -> None:
    history = ExampleHistory(
        frames=(np.zeros((3, 3), dtype=np.uint8),),
        available_action_sets=(frozenset({1, 2, 6}),),
    )
    action = ExampleAction(kind="ACTION6", row=1, col=2)

    with ProgramWorker(VALID_PROGRAM, timeout_seconds=0.5) as worker:
        startup = worker.start()
        assert startup.ok, startup.error
        assert startup.value is not None
        assert startup.value.memory_limit_mb == DEFAULT_MEMORY_LIMIT_MB
        if os.name == "nt":
            assert not startup.value.hard_memory_limit_enforced
        else:
            assert isinstance(startup.value.hard_memory_limit_enforced, bool)
        first_pid = worker.pid

        prediction = worker.predict(history, action)
        assert prediction.ok, prediction.error
        assert prediction.value["game_state"] == "PLAYING"
        assert prediction.value["memory"]["observations"] == 1
        np.testing.assert_array_equal(
            prediction.value["next_grid"],
            np.array([[0, 0, 0], [0, 0, 7], [0, 0, 0]], dtype=np.uint8),
        )

        goal = worker.goal_value(history)
        assert goal.ok, goal.error
        assert goal.value == pytest.approx(0.125)
        assert worker.pid == first_pid
        assert worker.alive


def test_default_deadline_is_one_hundred_milliseconds() -> None:
    worker = ProgramWorker(VALID_PROGRAM)
    try:
        assert worker.timeout_seconds == pytest.approx(DEFAULT_TIMEOUT_SECONDS)
        assert pytest.approx(0.1) == DEFAULT_TIMEOUT_SECONDS
    finally:
        worker.close()


def test_validation_failure_is_returned_without_spawning_or_raising() -> None:
    worker = ProgramWorker("import subprocess")
    try:
        result = worker.predict({}, {})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind is WorkerErrorKind.VALIDATION
        assert worker.pid is None
    finally:
        worker.close()


def test_generated_exception_is_typed_and_worker_remains_usable() -> None:
    source = """
def predict(history, action):
    return 1 // 0
def goal_value(history):
    return 0.4
"""
    with ProgramWorker(source, timeout_seconds=0.5) as worker:
        failed = worker.predict({}, {})
        assert not failed.ok
        assert failed.error is not None
        assert failed.error.kind is WorkerErrorKind.EXECUTION
        assert "ZeroDivisionError" in failed.error.message

        recovered = worker.goal_value({})
        assert recovered.ok
        assert recovered.value == pytest.approx(0.4)


def test_goal_value_contract_violation_is_output_error() -> None:
    source = """
def predict(history, action):
    return {}
def goal_value(history):
    return 1.5
"""
    with ProgramWorker(source, timeout_seconds=0.5) as worker:
        result = worker.goal_value({})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind is WorkerErrorKind.OUTPUT
        assert "[0, 1]" in result.error.message


def test_unsupported_input_is_typed_and_does_not_reach_child() -> None:
    with ProgramWorker(VALID_PROGRAM, timeout_seconds=0.5) as worker:
        result = worker.predict(object(), {})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind is WorkerErrorKind.INPUT
        assert worker.alive


def test_infinite_generated_code_times_out_and_worker_is_retired() -> None:
    source = """
def predict(history, action):
    while True:
        pass
def goal_value(history):
    return 0.0
"""
    with ProgramWorker(source, timeout_seconds=0.05) as worker:
        timed_out = worker.predict({}, {})
        assert not timed_out.ok
        assert timed_out.error is not None
        assert timed_out.error.kind is WorkerErrorKind.TIMEOUT
        assert not worker.alive

        unavailable = worker.goal_value({})
        assert not unavailable.ok
        assert unavailable.error is not None
        assert unavailable.error.kind is WorkerErrorKind.UNAVAILABLE


def test_numpy_file_api_is_absent_even_when_obfuscated_through_assignment() -> None:
    source = """
def predict(history, action):
    writer = np.save
    return writer("grid.npy", history.frames[-1])
def goal_value(history):
    return 0.0
"""
    with pytest.raises(SandboxValidationError) as captured:
        validate_program(source)
    assert ValidationCode.DISALLOWED_ATTRIBUTE in {
        issue.code for issue in captured.value.issues
    }
