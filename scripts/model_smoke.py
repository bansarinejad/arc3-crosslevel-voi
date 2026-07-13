"""One-action end-to-end smoke using the selected local model and official endpoint."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from arc3_voi.agent import build_agent, require_live_execution_admitted
from arc3_voi.arc_adapter import ArcCompetitionClient
from arc3_voi.config import load_config
from arc3_voi.experiment import stable_config_hash
from arc3_voi.model import backend_from_config
from arc3_voi.runner import run_game


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default="ls20-9607627b")
    parser.add_argument("--config", type=Path, default=Path("configs/local_4b.yaml"))
    parser.add_argument("--model-path", type=Path, default=Path("models/Qwen3.5-4B"))
    parser.add_argument("--seed", type=int, default=20_260_712)
    args = parser.parse_args()

    config = load_config(args.config)
    config = replace(
        config,
        experiment=replace(
            config.experiment,
            seed=args.seed,
            max_environment_actions=1,
        ),
    )
    require_live_execution_admitted(config)
    backend = backend_from_config(config, model_path=args.model_path)
    session = ArcCompetitionClient().make(args.game, seed=args.seed)
    with build_agent(backend, config) as agent:
        metrics = run_game(
            session,
            agent.controller,
            run_id="selected-model-official-smoke",
            seed=args.seed,
            variant=config.experiment.variant,
            model_profile=config.model.profile if config.model else "no-model",
            config_hash=stable_config_hash(config),
            max_environment_actions=1,
            max_generated_tokens=config.experiment.max_generated_tokens,
            max_wall_seconds=config.experiment.max_wall_seconds,
        )
    print(json.dumps(metrics.summary(), indent=2, sort_keys=True))
    return 0 if metrics.total_actions == 1 and metrics.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
