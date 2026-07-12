"""Conditional ARC-AGI-2 substrate-transfer evaluation.

This module intentionally evaluates only executable version-space aggregation. It does
not present static ARC-AGI-2 tasks as evidence for active exploration.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class Arc2Task:
    task_id: str
    training: tuple[tuple[np.ndarray, np.ndarray], ...]
    tests: tuple[tuple[np.ndarray, np.ndarray | None], ...]


class GridTransform(Protocol):
    ast_nodes: int

    def apply(self, grid: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class Arc2Prediction:
    task_id: str
    test_index: int
    output: np.ndarray
    agreeing_weight: float
    committee_size: int


def load_arc2_task(path: str | Path) -> Arc2Task:
    source = Path(path)
    value = json.loads(source.read_text(encoding="utf-8"))
    training = tuple(
        (
            np.asarray(pair["input"], dtype=np.int8),
            np.asarray(pair["output"], dtype=np.int8),
        )
        for pair in value["train"]
    )
    tests = tuple(
        (
            np.asarray(pair["input"], dtype=np.int8),
            np.asarray(pair["output"], dtype=np.int8) if "output" in pair else None,
        )
        for pair in value["test"]
    )
    return Arc2Task(source.stem, training, tests)


def training_loss(transform: GridTransform, task: Arc2Task) -> float:
    losses = []
    for input_grid, expected in task.training:
        try:
            output = np.asarray(transform.apply(input_grid), dtype=np.int8)
        except Exception:
            return float("inf")
        if output.shape != expected.shape:
            losses.append(1.0)
        else:
            losses.append(float(np.mean(output != expected)))
    return float(np.mean(losses)) if losses else float("inf")


def committee_output(
    transforms: list[GridTransform],
    weights: list[float],
    input_grid: np.ndarray,
) -> tuple[np.ndarray, float]:
    if not transforms or len(transforms) != len(weights):
        raise ValueError("non-empty transforms and aligned weights are required")
    groups: dict[tuple[tuple[int, ...], bytes], list[tuple[np.ndarray, float]]] = defaultdict(list)
    for transform, weight in zip(transforms, weights, strict=True):
        output = np.asarray(transform.apply(input_grid), dtype=np.int8)
        groups[(output.shape, output.tobytes())].append((output, float(weight)))
    winning = max(groups.values(), key=lambda group: sum(item[1] for item in group))
    total = sum(weights)
    return winning[0][0], sum(item[1] for item in winning) / total


def exact_task_solved(task: Arc2Task, predictions: list[np.ndarray]) -> bool:
    if len(predictions) != len(task.tests):
        return False
    return all(
        expected is not None and np.array_equal(prediction, expected)
        for prediction, (_, expected) in zip(predictions, task.tests, strict=True)
    )


def exact_mcnemar(k4: list[bool], k1: list[bool]) -> float:
    """Two-sided exact McNemar p-value for paired task outcomes."""

    if len(k4) != len(k1):
        raise ValueError("paired result vectors must have the same length")
    only_k4 = sum(a and not b for a, b in zip(k4, k1, strict=True))
    only_k1 = sum(b and not a for a, b in zip(k4, k1, strict=True))
    discordant = only_k4 + only_k1
    if discordant == 0:
        return 1.0
    from math import comb

    tail = sum(comb(discordant, index) for index in range(0, min(only_k4, only_k1) + 1))
    return float(min(1.0, 2 * tail / (2**discordant)))
