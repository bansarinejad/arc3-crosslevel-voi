"""Benchmark serial and concurrent committee planning on a maximum-shape history."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from arc3_voi.planner import BeamSearchPlanner, PlanningSnapshot
from arc3_voi.program import ExecutableHypothesis
from arc3_voi.types import Action, ActionKind, GameState, History, Observation

PROGRAM_TEMPLATE = """
def predict(history, action):
    grid = np.array(history.frames[-1], dtype=np.int16)
    if int(action.kind) == 6:
        row = int(action.row)
        col = int(action.col)
        grid[row, col] = (int(grid[row, col]) + {offset}) % 16
    return {{"next_grid": grid, "game_state": "NOT_FINISHED", "level_delta": 0, "memory": {{}}}}

def goal_value(history):
    grid = np.array(history.frames[-1], dtype=np.int16)
    return float(np.count_nonzero(grid == {target})) / 4096.0
"""


def _actions() -> tuple[Action, ...]:
    return (
        Action(ActionKind.ACTION1),
        Action(ActionKind.ACTION2),
        Action(ActionKind.ACTION3),
        Action(ActionKind.ACTION4),
        Action(ActionKind.ACTION5),
        Action(ActionKind.ACTION7),
        *(Action(ActionKind.ACTION6, row=8 * index, col=63 - 8 * index) for index in range(6)),
    )


def _history(actions: tuple[Action, ...]) -> History:
    action_kinds = frozenset(action.kind for action in actions)
    history = History.from_observation(
        Observation(
            np.arange(4096, dtype=np.int16).reshape(64, 64) % 16,
            action_kinds,
            GameState.NOT_FINISHED,
            level=1,
            win_levels=9,
        )
    )
    for index in range(1, History.MAX_LENGTH):
        history = history.append(
            Observation(
                (np.arange(4096, dtype=np.int16).reshape(64, 64) + index) % 16,
                action_kinds,
                GameState.NOT_FINISHED,
                level=1,
                win_levels=9,
            ),
            actions[index % len(actions)],
            0,
        )
    return history


def _snapshot_digest(snapshot: PlanningSnapshot) -> str:
    predictions: dict[str, list[str]] = {}
    for action in snapshot.actions:
        labels = []
        for prediction in snapshot.predictions[action]:
            assert prediction is not None
            digest = hashlib.sha256()
            digest.update(prediction.next_grid.tobytes(order="C"))
            digest.update(prediction.game_state.value.encode("ascii"))
            digest.update(str(prediction.level_delta).encode("ascii"))
            labels.append(digest.hexdigest())
        predictions[repr(action)] = labels
    payload = {
        "actions": [repr(action) for action in snapshot.actions],
        "hypothesis_ids": snapshot.hypothesis_ids,
        "weights": snapshot.weights,
        "costs": {
            repr(action): snapshot.costs[action] for action in snapshot.actions
        },
        "predictions": predictions,
        "invalid_hypothesis_ids": snapshot.invalid_hypothesis_ids,
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _counters(
    hypotheses: tuple[ExecutableHypothesis, ...],
) -> tuple[tuple[int, int, int, int], ...]:
    return tuple(
        (
            hypothesis.prediction_calls,
            hypothesis.goal_calls,
            hypothesis.timeout_count,
            hypothesis.execution_error_count,
        )
        for hypothesis in hypotheses
    )


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _parent_peak_rss_bytes() -> int | None:
    if not sys.platform.startswith("linux"):
        return None
    with Path("/proc/self/status").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.startswith("VmHWM:"):
                continue
            fields = line.split()
            if len(fields) == 3 and fields[2] == "kB":
                return int(fields[1]) * 1024
    return None


def run_benchmark(*, trials: int = 3) -> dict[str, Any]:
    if trials < 2:
        raise ValueError("at least two trials are required to alternate execution order")
    actions = _actions()
    history = _history(actions)
    sources = tuple(
        PROGRAM_TEMPLATE.format(offset=index + 1, target=9 + index)
        for index in range(4)
    )
    with ExitStack() as stack:
        hypotheses = tuple(
            stack.enter_context(
                ExecutableHypothesis(
                    source,
                    timeout_seconds=0.1,
                    memory_limit_mb=256,
                )
            )
            for source in sources
        )
        for hypothesis in hypotheses:
            hypothesis.goal_value(history)
        weighted = tuple((hypothesis, 0.25) for hypothesis in hypotheses)
        benchmark_start_counters = _counters(hypotheses)
        phases: list[dict[str, Any]] = []
        for trial in range(trials):
            order = ("serial", "parallel") if trial % 2 == 0 else ("parallel", "serial")
            for order_index, mode in enumerate(order):
                before = _counters(hypotheses)
                started = time.perf_counter()
                snapshot = BeamSearchPlanner(
                    depth=4,
                    beam_width=8,
                    parallel_hypotheses=mode == "parallel",
                ).evaluate(history, actions, weighted, win_levels=9)
                seconds = time.perf_counter() - started
                after = _counters(hypotheses)
                phases.append(
                    {
                        "trial": trial + 1,
                        "order_index": order_index,
                        "mode": mode,
                        "seconds": seconds,
                        "snapshot_sha256": _snapshot_digest(snapshot),
                        "per_hypothesis_counter_deltas": [
                            {
                                "prediction_calls": end[0] - start[0],
                                "goal_calls": end[1] - start[1],
                                "timeouts": end[2] - start[2],
                                "execution_errors": end[3] - start[3],
                            }
                            for start, end in zip(before, after, strict=True)
                        ],
                    }
                )

        serial_seconds = [
            float(phase["seconds"]) for phase in phases if phase["mode"] == "serial"
        ]
        parallel_seconds = [
            float(phase["seconds"]) for phase in phases if phase["mode"] == "parallel"
        ]
        paired_speedups = [
            next(
                float(phase["seconds"])
                for phase in phases
                if phase["trial"] == trial and phase["mode"] == "serial"
            )
            / next(
                float(phase["seconds"])
                for phase in phases
                if phase["trial"] == trial and phase["mode"] == "parallel"
            )
            for trial in range(1, trials + 1)
        ]
        benchmark_end_counters = _counters(hypotheses)
        snapshot_digests = {
            str(phase["snapshot_sha256"]) for phase in phases
        }
        return {
            "schema_version": 1,
            "platform": platform.platform(),
            "python": sys.version,
            "shape": {
                "history_frames": len(history.frames),
                "grid": [64, 64],
                "hypotheses": len(hypotheses),
                "actions": len(actions),
                "depth": 4,
                "beam_width": 8,
            },
            "trials": trials,
            "execution_order_alternated": True,
            "phases": phases,
            "summary": {
                "serial_median_seconds": median(serial_seconds),
                "serial_p95_seconds": _quantile(serial_seconds, 0.95),
                "parallel_median_seconds": median(parallel_seconds),
                "parallel_p95_seconds": _quantile(parallel_seconds, 0.95),
                "median_paired_speedup": median(paired_speedups),
                "paired_speedups": paired_speedups,
                "all_snapshot_sha256": sorted(snapshot_digests),
                "snapshots_equal": len(snapshot_digests) == 1,
                "parent_peak_rss_bytes": _parent_peak_rss_bytes(),
                "child_peak_rss_bytes": None,
                "child_peak_rss_note": (
                    "Not observable without adding a benchmark-only process dependency"
                ),
                "per_hypothesis_counter_deltas": [
                    {
                        "prediction_calls": end[0] - start[0],
                        "goal_calls": end[1] - start[1],
                        "timeouts": end[2] - start[2],
                        "execution_errors": end[3] - start[3],
                    }
                    for start, end in zip(
                        benchmark_start_counters,
                        benchmark_end_counters,
                        strict=True,
                    )
                ],
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    result = run_benchmark(trials=args.trials)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
