"""Hardware/model preflight and hidden-workload runtime projection."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np

from .model import GenerationResult, ModelBackend


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    cuda_available: bool
    device_name: str | None
    total_vram_gb: float | None


@dataclass(frozen=True, slots=True)
class PreflightReport:
    hardware: HardwareInfo
    model_id: str
    output_tokens: int
    elapsed_seconds: float
    tokens_per_second: float
    peak_vram_gb: float | None
    fits_vram_gate: bool
    passes_throughput_gate: bool
    requested_sequences: int
    syntactically_valid_programs: int
    statically_valid_programs: int
    validation_failures: dict[str, int]
    program_source_sha256: tuple[str, ...]
    program_source_lengths: tuple[int, ...]
    truncated_sequences: int
    projected_p95_seconds: float | None = None
    runtime_fraction: float | None = None
    passes_runtime_gate: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_hardware() -> HardwareInfo:
    try:
        import torch
    except ImportError:
        return HardwareInfo(False, None, None)
    if not torch.cuda.is_available():
        return HardwareInfo(False, None, None)
    properties = torch.cuda.get_device_properties(0)
    return HardwareInfo(
        True,
        str(properties.name),
        float(properties.total_memory / 1024**3),
    )


def run_model_preflight(
    backend: ModelBackend,
    *,
    model_id: str,
    max_peak_vram_gb: float = 14.5,
    min_tokens_per_second: float = 12.0,
    observed_game_seconds: list[float] | None = None,
    hidden_game_count: int | None = None,
    runtime_limit_seconds: float | None = None,
    program_count: int = 1,
) -> PreflightReport:
    history = []
    for index in range(8):
        grid = np.zeros((64, 64), dtype=np.int8)
        grid[index * 8 : (index + 1) * 8, :] = index % 10
        history.append(
            SimpleNamespace(
                grid=grid,
                action=None if index == 0 else SimpleNamespace(kind="ACTION1"),
                available_actions=("ACTION1", "ACTION2"),
                game_state="NOT_FINISHED",
                level_delta=0,
                level=1,
            )
        )
    if program_count < 1:
        raise ValueError("program_count must be positive")
    result: GenerationResult = backend.generate_programs(history, program_count)
    from .runtime.sandbox import SandboxValidationError, validate_program

    valid_programs = 0
    validation_failures: Counter[str] = Counter()
    for source in result.texts:
        try:
            validate_program(source)
        except SandboxValidationError as exc:
            validation_failures.update(issue.code.value for issue in exc.issues)
            continue
        valid_programs += 1
    projected = fraction = None
    runtime_pass: bool | None = None
    if observed_game_seconds and hidden_game_count and runtime_limit_seconds:
        p95 = empirical_quantile(observed_game_seconds, 0.95)
        projected = p95 * hidden_game_count
        fraction = projected / runtime_limit_seconds
        runtime_pass = fraction <= 0.8
    peak = result.peak_vram_gb
    return PreflightReport(
        hardware=detect_hardware(),
        model_id=model_id,
        output_tokens=result.output_tokens,
        elapsed_seconds=result.elapsed_seconds,
        tokens_per_second=result.tokens_per_second,
        peak_vram_gb=peak,
        fits_vram_gate=peak is not None and peak <= max_peak_vram_gb,
        passes_throughput_gate=result.tokens_per_second >= min_tokens_per_second,
        requested_sequences=program_count,
        syntactically_valid_programs=valid_programs,
        statically_valid_programs=valid_programs,
        validation_failures=dict(sorted(validation_failures.items())),
        program_source_sha256=tuple(
            hashlib.sha256(source.encode("utf-8")).hexdigest() for source in result.texts
        ),
        program_source_lengths=tuple(len(source) for source in result.texts),
        truncated_sequences=sum(result.hit_token_limit),
        projected_p95_seconds=projected,
        runtime_fraction=fraction,
        passes_runtime_gate=runtime_pass,
    )


def empirical_quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one observation")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = probability * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)
