"""Persistent process isolation for validated generated programs.

Each :class:`ProgramWorker` owns one spawned child process.  The child imports no
generated modules, receives sanitized data over a pipe, and executes only source
accepted by :func:`arc3_voi.runtime.sandbox.validate_program`.  Calls have a
100 ms wall-clock deadline by default; a timed-out process is terminated instead
of being reused.

On POSIX, the child attempts to enforce a 256 MiB ``RLIMIT_DATA`` hard limit.
Unlike an address-space limit, this does not count NumPy/OpenBLAS shared-library
mappings against generated allocations.  The standard library does not expose
an equivalent safe per-process primitive on Windows, so the same value remains a
documented target there and caller-visible metadata reports that hard enforcement
is unavailable.  The timeout remains hard-enforced by process termination on
both platforms.
"""

from __future__ import annotations
import __future__

import builtins
import contextlib
import dataclasses
import math
import multiprocessing as mp
import os
import threading
import time
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from multiprocessing.connection import Connection
from types import MappingProxyType
from typing import Any, cast

import numpy as np

from arc3_voi.runtime.sandbox import (
    SAFE_BUILTIN_CALLS,
    SAFE_NUMPY_ATTRIBUTES,
    SandboxValidationError,
    ValidatedProgram,
    validate_program,
)

DEFAULT_TIMEOUT_SECONDS = 0.100
DEFAULT_STARTUP_TIMEOUT_SECONDS = 10.0
DEFAULT_MEMORY_LIMIT_MB = 256
_MAX_TRANSPORT_ITEMS = 131_072
_MAX_TRANSPORT_DEPTH = 32

class WorkerErrorKind(StrEnum):
    """Stable error categories returned to the controller."""

    VALIDATION = "validation"
    INPUT = "input"
    STARTUP = "startup"
    COMPILE = "compile"
    EXECUTION = "execution"
    OUTPUT = "output"
    TIMEOUT = "timeout"
    CRASHED = "crashed"
    PROTOCOL = "protocol"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WorkerError:
    """A generated-program failure represented as data, not an exception."""

    kind: WorkerErrorKind
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult[T]:
    """Result of starting or invoking a restricted program."""

    value: T | None = None
    error: WorkerError | None = None
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None

    def unwrap(self) -> T:
        """Return the value or raise a normal RuntimeError at an explicit boundary."""

        if self.error is not None:
            raise RuntimeError(f"{self.error.kind}: {self.error.message}")
        return self.value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class WorkerMetadata:
    """Immutable metadata for a successfully started worker."""

    pid: int
    program_sha256: str
    ast_node_count: int
    timeout_seconds: float
    memory_limit_mb: int
    hard_memory_limit_enforced: bool


class _TransportError(ValueError):
    pass


class _SafeRecord(Mapping[str | int | float | bool, Any]):
    """Inert mapping with public-field attribute reads for generated code."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str | int | float | bool, Any]):
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getitem__(self, key: str | int | float | bool) -> Any:
        return self._values[key]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        del value
        raise AttributeError(f"{type(self).__name__} is read-only: {name}")


class _NumpyFacade:
    """Defense-in-depth facade matching the statically allowed NumPy names."""

    __slots__ = ()

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_") or name not in SAFE_NUMPY_ATTRIBUTES:
            raise AttributeError(f"numpy attribute {name!r} is not available")
        return getattr(np, name)


def _safe_builtins() -> dict[str, Any]:
    allowed = {name: getattr(builtins, name) for name in SAFE_BUILTIN_CALLS}
    # isinstance needs inert types to be useful but receives no general-purpose
    # reflection helpers such as type/getattr/vars.
    allowed.update(
        {
            "None": None,
            "False": False,
            "True": True,
        }
    )
    return allowed


def _transport_value(
    value: Any,
    *,
    path: str,
    depth: int = 0,
    counter: list[int] | None = None,
) -> Any:
    """Copy trusted application data into a narrow, pickle-safe value language."""

    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > _MAX_TRANSPORT_ITEMS:
        raise _TransportError(f"{path} exceeds {_MAX_TRANSPORT_ITEMS} transport items")
    if depth > _MAX_TRANSPORT_DEPTH:
        raise _TransportError(f"{path} exceeds transport nesting depth {_MAX_TRANSPORT_DEPTH}")

    if isinstance(value, Enum):
        return _transport_value(value.value, path=path, depth=depth + 1, counter=counter)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise _TransportError(f"{path} contains an object-dtype array")
        return np.array(value, copy=True)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _transport_value(
                getattr(value, field.name),
                path=f"{path}.{field.name}",
                depth=depth + 1,
                counter=counter,
            )
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        output: dict[str | int | float | bool, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str | int | float | bool):
                raise _TransportError(f"{path} has unsupported mapping key {type(key).__name__}")
            output[key] = _transport_value(
                item,
                path=f"{path}[{key!r}]",
                depth=depth + 1,
                counter=counter,
            )
        return output
    if isinstance(value, list | tuple):
        items = [
            _transport_value(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                counter=counter,
            )
            for index, item in enumerate(value)
        ]
        return tuple(items) if isinstance(value, tuple) else items
    if isinstance(value, set | frozenset):
        items = [
            _transport_value(
                item,
                path=f"{path}[set-item]",
                depth=depth + 1,
                counter=counter,
            )
            for item in value
        ]
        try:
            return frozenset(items) if isinstance(value, frozenset) else set(items)
        except TypeError as exc:
            raise _TransportError(f"{path} contains an unhashable set item") from exc
    raise _TransportError(f"{path} has unsupported value type {type(value).__name__}")


def _wrap_input(value: Any) -> Any:
    if isinstance(value, dict):
        return _SafeRecord({key: _wrap_input(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_wrap_input(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_wrap_input(item) for item in value)
    if isinstance(value, set):
        return {_wrap_input(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(_wrap_input(item) for item in value)
    if isinstance(value, np.ndarray):
        value.setflags(write=False)
    return value


def _serialize_output(value: Any, *, operation: str) -> Any:
    if isinstance(value, _SafeRecord):
        value = dict(value)
    transported = _transport_value(value, path=f"{operation} result")
    if operation == "goal_value":
        if isinstance(transported, bool) or not isinstance(transported, int | float):
            raise _TransportError("goal_value must return a finite number in [0, 1]")
        normalized = float(transported)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise _TransportError("goal_value must return a finite number in [0, 1]")
        return normalized
    return transported


def _apply_memory_limit(memory_limit_mb: int) -> tuple[bool, str | None]:
    """Apply the POSIX data-segment ceiling; return enforcement and diagnostic."""

    if os.name != "posix":
        return False, "hard per-process memory limits are unavailable on this platform"
    try:
        import resource

        limit_bytes = memory_limit_mb * 1024 * 1024
        setrlimit = vars(resource)["setrlimit"]
        rlimit_data = vars(resource)["RLIMIT_DATA"]
        setrlimit(rlimit_data, (limit_bytes, limit_bytes))
        return True, None
    except (ImportError, OSError, ValueError) as exc:
        return False, f"could not apply RLIMIT_DATA: {type(exc).__name__}: {exc}"


def _send_response(connection: Connection, response: dict[str, Any]) -> bool:
    try:
        connection.send(response)
        return True
    except (BrokenPipeError, EOFError, OSError, ValueError, TypeError):
        return False


def _worker_main(
    connection: Connection,
    canonical_source: str,
    memory_limit_mb: int,
) -> None:
    """Child entry point.  Must remain top-level so Windows spawn can import it."""

    memory_enforced, memory_diagnostic = _apply_memory_limit(memory_limit_mb)
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(),
        "np": _NumpyFacade(),
        "__name__": "generated_hypothesis",
    }
    try:
        tree = compile(
            canonical_source,
            filename="<generated-hypothesis>",
            mode="exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        )
        # This is trusted runtime machinery executing statically validated source;
        # generated programs themselves cannot reference exec or compile.
        exec(tree, namespace, namespace)
        predict = namespace.get("predict")
        goal_value = namespace.get("goal_value")
        if not callable(predict) or not callable(goal_value):
            raise TypeError("validated program did not initialize required callables")
    except BaseException as exc:  # child must report initialization failure as data
        _send_response(
            connection,
            {
                "request_id": 0,
                "ok": False,
                "kind": WorkerErrorKind.COMPILE.value,
                "message": f"{type(exc).__name__}: {exc}",
                "detail": traceback.format_exc(limit=3),
            },
        )
        connection.close()
        return

    if not _send_response(
        connection,
        {
            "request_id": 0,
            "ok": True,
            "value": {
                "hard_memory_limit_enforced": memory_enforced,
                "memory_limit_diagnostic": memory_diagnostic,
            },
        },
    ):
        connection.close()
        return

    while True:
        try:
            request = connection.recv()
        except (EOFError, OSError, BrokenPipeError):
            break
        if not isinstance(request, dict):
            if not _send_response(
                connection,
                {
                    "request_id": -1,
                    "ok": False,
                    "kind": WorkerErrorKind.PROTOCOL.value,
                    "message": "worker received a malformed request",
                },
            ):
                break
            continue
        request_id = request.get("request_id", -1)
        operation = request.get("operation")
        if operation == "shutdown":
            break
        started = time.perf_counter()
        try:
            if operation == "predict":
                result = predict(
                    _wrap_input(request["history"]),
                    _wrap_input(request["action"]),
                )
            elif operation == "goal_value":
                result = goal_value(_wrap_input(request["history"]))
            else:
                raise ValueError(f"unsupported operation {operation!r}")
            result = _serialize_output(result, operation=str(operation))
            response = {
                "request_id": request_id,
                "ok": True,
                "value": result,
                "elapsed_ms": (time.perf_counter() - started) * 1_000,
            }
        except _TransportError as exc:
            response = {
                "request_id": request_id,
                "ok": False,
                "kind": WorkerErrorKind.OUTPUT.value,
                "message": str(exc),
                "elapsed_ms": (time.perf_counter() - started) * 1_000,
            }
        except BaseException as exc:  # isolate all generated-code failures
            response = {
                "request_id": request_id,
                "ok": False,
                "kind": WorkerErrorKind.EXECUTION.value,
                "message": f"{type(exc).__name__}: {exc}",
                "detail": traceback.format_exc(limit=3),
                "elapsed_ms": (time.perf_counter() - started) * 1_000,
            }
        if not _send_response(connection, response):
            break
    connection.close()


class ProgramWorker:
    """Persistent restricted worker for one generated hypothesis program.

    Construction and calls do not propagate validation or generated-code
    exceptions.  Inspect :class:`ExecutionResult` and its ``error.kind`` instead.
    A worker starts lazily on its first invocation, or explicitly via ``start``.
    """

    def __init__(
        self,
        source: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
        start_method: str = "spawn",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if startup_timeout_seconds <= 0:
            raise ValueError("startup_timeout_seconds must be positive")
        if memory_limit_mb <= 0:
            raise ValueError("memory_limit_mb must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.startup_timeout_seconds = float(startup_timeout_seconds)
        self.memory_limit_mb = int(memory_limit_mb)
        self._context: Any = mp.get_context(start_method)
        self._process: mp.Process | None = None
        self._connection: Connection | None = None
        self._metadata: WorkerMetadata | None = None
        self._request_id = 0
        self._lock = threading.RLock()
        self._terminal_error: WorkerError | None = None
        try:
            self._program: ValidatedProgram | None = validate_program(source)
        except SandboxValidationError as exc:
            self._program = None
            detail = "\n".join(
                f"{issue.code.value} at {issue.line}:{issue.column}: {issue.message}"
                for issue in exc.issues
            )
            self._terminal_error = WorkerError(
                WorkerErrorKind.VALIDATION,
                str(exc),
                detail=detail,
            )

    @property
    def program(self) -> ValidatedProgram | None:
        return self._program

    @property
    def metadata(self) -> WorkerMetadata | None:
        return self._metadata

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def _error_result(self, error: WorkerError, elapsed_ms: float = 0.0) -> ExecutionResult[Any]:
        return ExecutionResult(error=error, elapsed_ms=elapsed_ms)

    def start(self) -> ExecutionResult[WorkerMetadata]:
        with self._lock:
            started = time.perf_counter()
            if self._metadata is not None and self.alive:
                return ExecutionResult(value=self._metadata)
            if self._terminal_error is not None:
                return self._error_result(self._terminal_error)
            if self._program is None:
                return self._error_result(
                    WorkerError(WorkerErrorKind.VALIDATION, "program was not validated")
                )

            parent_connection, child_connection = self._context.Pipe(duplex=True)
            process = self._context.Process(
                target=_worker_main,
                args=(child_connection, self._program.canonical_source, self.memory_limit_mb),
                daemon=True,
                name=f"arc3-hypothesis-{self._program.sha256[:8]}",
            )
            try:
                process.start()
                child_connection.close()
            except (OSError, RuntimeError, ValueError) as exc:
                parent_connection.close()
                child_connection.close()
                error = WorkerError(
                    WorkerErrorKind.STARTUP,
                    f"could not start worker: {type(exc).__name__}: {exc}",
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)

            self._process = process
            self._connection = cast(Connection, parent_connection)
            if not parent_connection.poll(self.startup_timeout_seconds):
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind.STARTUP,
                    f"worker did not initialize within {self.startup_timeout_seconds:.3f}s",
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)
            try:
                response = parent_connection.recv()
            except (EOFError, OSError, BrokenPipeError) as exc:
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind.CRASHED,
                    f"worker exited during initialization: {type(exc).__name__}: {exc}",
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)
            if not isinstance(response, dict) or response.get("request_id") != 0:
                self._terminate_process()
                error = WorkerError(WorkerErrorKind.PROTOCOL, "invalid worker startup response")
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)
            if not response.get("ok"):
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind(response.get("kind", WorkerErrorKind.COMPILE.value)),
                    str(response.get("message", "worker compilation failed")),
                    detail=response.get("detail"),
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)

            metadata_payload = response.get("value", {})
            self._metadata = WorkerMetadata(
                pid=process.pid or -1,
                program_sha256=self._program.sha256,
                ast_node_count=self._program.node_count,
                timeout_seconds=self.timeout_seconds,
                memory_limit_mb=self.memory_limit_mb,
                hard_memory_limit_enforced=bool(
                    metadata_payload.get("hard_memory_limit_enforced", False)
                ),
            )
            return ExecutionResult(
                value=self._metadata,
                elapsed_ms=(time.perf_counter() - started) * 1_000,
            )

    def _call(self, operation: str, *, history: Any, action: Any = None) -> ExecutionResult[Any]:
        with self._lock:
            start_result = self.start()
            if not start_result.ok:
                return ExecutionResult(error=start_result.error, elapsed_ms=start_result.elapsed_ms)
            if self._process is None or self._connection is None or not self._process.is_alive():
                error = self._terminal_error or WorkerError(
                    WorkerErrorKind.UNAVAILABLE, "worker is not available"
                )
                return self._error_result(error)

            try:
                safe_history = _transport_value(history, path="history")
                safe_action = (
                    _transport_value(action, path="action") if operation == "predict" else None
                )
            except _TransportError as exc:
                return self._error_result(WorkerError(WorkerErrorKind.INPUT, str(exc)))

            self._request_id += 1
            request_id = self._request_id
            request = {
                "request_id": request_id,
                "operation": operation,
                "history": safe_history,
            }
            if operation == "predict":
                request["action"] = safe_action
            started = time.perf_counter()
            try:
                self._connection.send(request)
            except (BrokenPipeError, EOFError, OSError, TypeError, ValueError) as exc:
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind.CRASHED,
                    f"could not send request to worker: {type(exc).__name__}: {exc}",
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)

            if not self._connection.poll(self.timeout_seconds):
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind.TIMEOUT,
                    f"{operation} exceeded {self.timeout_seconds * 1_000:.0f} ms",
                )
                self._terminal_error = WorkerError(
                    WorkerErrorKind.UNAVAILABLE,
                    "worker was terminated after a generated-program timeout",
                )
                return self._error_result(error, (time.perf_counter() - started) * 1_000)
            try:
                response = self._connection.recv()
            except (BrokenPipeError, EOFError, OSError) as exc:
                self._terminate_process()
                error = WorkerError(
                    WorkerErrorKind.CRASHED,
                    f"worker exited while returning a result: {type(exc).__name__}: {exc}",
                )
                self._terminal_error = error
                return self._error_result(error, (time.perf_counter() - started) * 1_000)

            elapsed_ms = (time.perf_counter() - started) * 1_000
            if not isinstance(response, dict) or response.get("request_id") != request_id:
                self._terminate_process()
                error = WorkerError(WorkerErrorKind.PROTOCOL, "mismatched worker response")
                self._terminal_error = error
                return self._error_result(error, elapsed_ms)
            child_elapsed_ms = float(response.get("elapsed_ms", elapsed_ms))
            if response.get("ok"):
                return ExecutionResult(value=response.get("value"), elapsed_ms=child_elapsed_ms)
            try:
                kind = WorkerErrorKind(response.get("kind", WorkerErrorKind.EXECUTION.value))
            except ValueError:
                kind = WorkerErrorKind.PROTOCOL
            return self._error_result(
                WorkerError(
                    kind=kind,
                    message=str(response.get("message", "generated-program execution failed")),
                    detail=response.get("detail"),
                ),
                child_elapsed_ms,
            )

    def predict(self, history: Any, action: Any) -> ExecutionResult[Any]:
        return self._call("predict", history=history, action=action)

    def goal_value(self, history: Any) -> ExecutionResult[float]:
        result = self._call("goal_value", history=history)
        return ExecutionResult(value=result.value, error=result.error, elapsed_ms=result.elapsed_ms)

    def _terminate_process(self) -> None:
        process, connection = self._process, self._connection
        self._process = None
        self._connection = None
        self._metadata = None
        if connection is not None:
            with contextlib.suppress(OSError):
                connection.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1.0)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(timeout=1.0)
            process.close()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None and self.alive:
                try:
                    self._connection.send({"request_id": -1, "operation": "shutdown"})
                    if self._process is not None:
                        self._process.join(timeout=0.25)
                except (BrokenPipeError, EOFError, OSError):
                    pass
            self._terminate_process()

    def __enter__(self) -> ProgramWorker:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb
        self.close()

    def __del__(self) -> None:
        # Interpreter shutdown may have dismantled multiprocessing globals; make
        # cleanup best-effort and never leak a destructor exception.
        with contextlib.suppress(BaseException):
            self.close()


__all__ = [
    "DEFAULT_MEMORY_LIMIT_MB",
    "DEFAULT_STARTUP_TIMEOUT_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "ExecutionResult",
    "ProgramWorker",
    "WorkerError",
    "WorkerErrorKind",
    "WorkerMetadata",
]
