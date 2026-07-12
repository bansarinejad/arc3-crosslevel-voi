"""One-model, one-scorecard execution across an ARC-AGI-3 game manifest."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .agent import build_agent
from .arc_adapter import ArcCompetitionClient
from .config import SystemConfig
from .experiment import stable_config_hash
from .metrics import RunMetrics, load_run, write_run
from .model import ModelBackend
from .run_store import (
    ensure_retryable_run_artifacts,
    read_complete_run,
    validate_run_id,
)
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
        run_id = f"scorecard-{index:03d}-{game_id}-{config.experiment.variant}"
        validate_run_id(run_id)
        summary_path = destination / f"{run_id}.json"
        expected_identity = {
            "run_id": run_id,
            "game_id": game_id,
            "seed": seed,
            "variant": config.experiment.variant,
            "model_profile": model_profile,
            "config_hash": digest,
        }
        existing = read_complete_run(summary_path)
        if existing is not None:
            prior = load_run(summary_path)
            _validate_scorecard_identity(prior, expected_identity)
            if prior.error is None and prior.termination_reason is not None:
                results.append(prior)
                continue
        else:
            ensure_retryable_run_artifacts(
                summary_path,
                expected_summary=expected_identity,
            )

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
                run_id=run_id,
                seed=seed,
                variant=config.experiment.variant,
                model_profile=model_profile,
                config_hash=digest,
                model_revision=(config.model.expected_revision if config.model else None),
                weight_manifest_sha256=(
                    config.model.expected_weight_manifest_sha256 if config.model else None
                ),
                max_environment_actions=config.experiment.max_environment_actions,
                max_generated_tokens=config.experiment.max_generated_tokens,
                max_wall_seconds=per_game_wall,
            )
        write_run(metrics, destination)
        results.append(metrics)
    return CompetitionResult(tuple(results), time.perf_counter() - started, stopped)


def _validate_scorecard_identity(
    metrics: RunMetrics, expected: dict[str, object]
) -> None:
    actual = {
        "run_id": metrics.run_id,
        "game_id": metrics.game_id,
        "seed": metrics.seed,
        "variant": metrics.variant,
        "model_profile": metrics.model_profile,
        "config_hash": metrics.config_hash,
    }
    conflicts = [key for key, value in expected.items() if actual[key] != value]
    if conflicts:
        raise ValueError(
            f"scorecard artifact identity conflict: {', '.join(conflicts)}"
        )
