"""One-model, one-scorecard execution across an ARC-AGI-3 game manifest."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .agent import build_agent
from .arc_adapter import ArcCompetitionClient
from .config import SystemConfig
from .experiment import stable_config_hash
from .metrics import RunMetrics, write_run
from .model import ModelBackend
from .runner import run_game


@dataclass(frozen=True, slots=True)
class CompetitionResult:
    runs: tuple[RunMetrics, ...]
    elapsed_seconds: float
    stopped_early: bool


def run_scorecard(
    game_ids: tuple[str, ...],
    backend: ModelBackend,
    config: SystemConfig,
    *,
    output_directory: str | Path,
    seed: int = 0,
    global_wall_seconds: float | None = None,
    client: ArcCompetitionClient | None = None,
) -> CompetitionResult:
    """Run each environment once without requesting an inflight score."""

    if len(game_ids) != len(set(game_id.split("-", 1)[0] for game_id in game_ids)):
        raise ValueError("game manifest contains duplicate stable IDs")
    arcade = client or ArcCompetitionClient()
    destination = Path(output_directory)
    digest = stable_config_hash(config)
    model_profile = config.model.profile if config.model else "no-model"
    started = time.perf_counter()
    results: list[RunMetrics] = []
    stopped = False
    for index, game_id in enumerate(game_ids):
        elapsed = time.perf_counter() - started
        if global_wall_seconds is not None and elapsed >= global_wall_seconds:
            stopped = True
            break
        remaining_global = (
            config.experiment.max_wall_seconds
            if global_wall_seconds is None
            else max(0.001, global_wall_seconds - elapsed)
        )
        per_game_wall = min(config.experiment.max_wall_seconds, remaining_global)
        session = arcade.make(game_id, seed=seed)
        with build_agent(backend, config) as agent:
            metrics = run_game(
                session,
                agent.controller,
                run_id=f"scorecard-{index:03d}-{game_id}-{config.experiment.variant}",
                seed=seed,
                variant=config.experiment.variant,
                model_profile=model_profile,
                config_hash=digest,
                max_environment_actions=config.experiment.max_environment_actions,
                max_generated_tokens=config.experiment.max_generated_tokens,
                max_wall_seconds=per_game_wall,
            )
        write_run(metrics, destination)
        results.append(metrics)
    return CompetitionResult(tuple(results), time.perf_counter() - started, stopped)

