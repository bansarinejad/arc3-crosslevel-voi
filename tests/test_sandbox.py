from __future__ import annotations

import ast
import os
import textwrap
from dataclasses import dataclass

import numpy as np
import pytest

import arc3_voi.runtime.worker as worker_runtime
from arc3_voi.runtime.sandbox import (
    SandboxValidationError,
    ValidationCode,
    validate_program,
)
from arc3_voi.runtime.worker import (
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_TIMEOUT_SECONDS,
    RLIMIT_DATA_HEADROOM_KIND,
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


def test_transport_reuses_only_immutable_contiguous_arrays() -> None:
    immutable = np.zeros((4, 4), dtype=np.int16)
    immutable.flags.writeable = False
    writable = np.arange(16, dtype=np.int16).reshape(4, 4)
    aliased = np.arange(16, dtype=np.int16).reshape(4, 4)
    aliased.flags.writeable = False

    assert worker_runtime._transport_value(immutable, path="history.frames[0]") is immutable
    writable_copy = worker_runtime._transport_value(
        writable,
        path="history.frames[0]",
    )
    assert writable_copy is not writable
    assert np.array_equal(writable_copy, writable)
    assert worker_runtime._transport_value(aliased, path="history.frames[0]") is not aliased


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


def test_pure_numeric_divmod_builtin_is_available() -> None:
    source = """
def predict(history, action):
    quotient, remainder = divmod(int(action.row), 2)
    grid = np.array(history.frames[-1], dtype=np.int8)
    grid[0, 0] = quotient + remainder
    return {"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0}

def goal_value(history):
    return 0.0
"""
    validate_program(source)
    history = ExampleHistory(frames=(np.zeros((2, 2), dtype=np.int16),))
    with ProgramWorker(source, timeout_seconds=0.5) as worker:
        result = worker.predict(
            history,
            ExampleAction(kind="ACTION6", row=3, col=0),
        )

    assert result.ok
    assert result.value is not None
    assert result.value["next_grid"][0, 0] == 2


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
        ("pass\n    return {}", ValidationCode.DISALLOWED_NODE),
        ("while True:\n        value = 0\n    return {}", None),
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


def test_validator_rejects_mutable_helper_defaults() -> None:
    source = """
def helper(state=[0]):
    state[0] += 1
    return state[0]

def predict(history, action):
    helper()
    return {"next_grid": history.frames[-1], "game_state": "NOT_FINISHED", "level_delta": 0}

def goal_value(history):
    return 0.0
"""
    with pytest.raises(SandboxValidationError) as captured:
        validate_program(source)

    assert any(
        "function defaults must be immutable literals" in issue.message
        for issue in captured.value.issues
    )


def test_worker_freezes_top_level_literal_state() -> None:
    source = """
STATE = [0]

def predict(history, action):
    STATE[0] += 1
    return {"next_grid": history.frames[-1], "game_state": "NOT_FINISHED", "level_delta": 0}

def goal_value(history):
    return 0.0
"""
    history = ExampleHistory(frames=(np.zeros((2, 2), dtype=np.int16),))
    with ProgramWorker(source, timeout_seconds=0.5) as worker:
        result = worker.predict(history, ExampleAction(kind="ACTION1"))

    assert not result.ok
    assert result.error is not None
    assert result.error.kind is WorkerErrorKind.EXECUTION


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
            assert startup.value.memory_limit_kind is None
            assert startup.value.memory_baseline_bytes is None
            assert startup.value.memory_ceiling_bytes is None
        elif os.path.exists("/proc/self/status"):
            assert startup.value.hard_memory_limit_enforced
            assert startup.value.memory_limit_kind == RLIMIT_DATA_HEADROOM_KIND
            assert startup.value.memory_baseline_bytes is not None
            assert startup.value.memory_ceiling_bytes is not None
            assert (
                startup.value.memory_ceiling_bytes - startup.value.memory_baseline_bytes
                == DEFAULT_MEMORY_LIMIT_MB * 1024 * 1024
            )
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


def test_worker_accepts_full_bounded_history_with_audited_memory_headroom() -> None:
    history = ExampleHistory(
        frames=tuple(np.zeros((64, 64), dtype=np.int16) for _ in range(8)),
        actions=("ACTION1",) * 8,
        available_action_sets=(frozenset({1, 2, 6}),) * 8,
    )
    action = ExampleAction(kind="ACTION6", row=63, col=63)

    with ProgramWorker(VALID_PROGRAM, timeout_seconds=1.0) as worker:
        prediction = worker.predict(history, action)
        assert prediction.ok, prediction.error
        assert prediction.value["memory"]["observations"] == 8
        assert prediction.value["next_grid"].shape == (64, 64)
        assert prediction.value["next_grid"][63, 63] == 7

        metadata = worker.metadata
        assert metadata is not None
        if os.path.exists("/proc/self/status"):
            assert metadata.hard_memory_limit_enforced
            assert metadata.memory_baseline_bytes is not None
            assert metadata.memory_ceiling_bytes is not None
            assert (
                metadata.memory_ceiling_bytes - metadata.memory_baseline_bytes
                == DEFAULT_MEMORY_LIMIT_MB * 1024 * 1024
            )


@pytest.mark.skipif(
    not os.path.exists("/proc/self/status"),
    reason="the hard RLIMIT_DATA headroom implementation is Linux-specific",
)
def test_worker_rejects_allocation_larger_than_memory_headroom() -> None:
    source = """
def predict(history, action):
    return np.zeros((300 * 1024 * 1024,), dtype=np.uint8)
def goal_value(history):
    return 0.0
"""
    with ProgramWorker(source, timeout_seconds=3.0) as worker:
        startup = worker.start()
        assert startup.ok, startup.error
        assert startup.value is not None
        assert startup.value.hard_memory_limit_enforced
        assert startup.value.memory_limit_kind == RLIMIT_DATA_HEADROOM_KIND
        assert startup.value.memory_baseline_bytes is not None
        assert startup.value.memory_ceiling_bytes is not None
        assert (
            startup.value.memory_ceiling_bytes - startup.value.memory_baseline_bytes
            == DEFAULT_MEMORY_LIMIT_MB * 1024 * 1024
        )

        result = worker.predict({}, {})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind is WorkerErrorKind.MEMORY

        recovered = worker.goal_value({})
        assert recovered.ok, recovered.error
        assert recovered.value == pytest.approx(0.0)


@pytest.mark.skipif(os.name != "posix", reason="Linux competition workers require RLIMIT_DATA")
def test_posix_worker_startup_fails_closed_without_memory_enforcement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingConnection:
        def __init__(self) -> None:
            self.responses: list[dict[str, object]] = []
            self.closed = False

        def send(self, response: dict[str, object]) -> None:
            self.responses.append(response)

        def close(self) -> None:
            self.closed = True

    connection = RecordingConnection()
    monkeypatch.setattr(
        worker_runtime,
        "_apply_memory_limit",
        lambda _memory_limit_mb: worker_runtime._MemoryLimitStatus(
            False,
            diagnostic="injected enforcement failure",
        ),
    )

    worker_runtime._worker_main(  # type: ignore[arg-type]
        connection,
        validate_program(VALID_PROGRAM).canonical_source,
        DEFAULT_MEMORY_LIMIT_MB,
    )

    assert connection.closed
    assert len(connection.responses) == 1
    response = connection.responses[0]
    assert response["ok"] is False
    assert response["kind"] == WorkerErrorKind.STARTUP.value
    assert response["detail"] == "injected enforcement failure"


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
        value = 0
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
    assert ValidationCode.DISALLOWED_ATTRIBUTE in {issue.code for issue in captured.value.issues}
