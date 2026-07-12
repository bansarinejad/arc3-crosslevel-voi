"""Offline Kaggle entrypoint; preserve the official starter's gateway cell around it."""

from __future__ import annotations

import json
import os
from pathlib import Path

from arc3_voi.arc_adapter import ArcCompetitionClient
from arc3_voi.competition import run_scorecard
from arc3_voi.config import load_config
from arc3_voi.model import backend_from_config


def main() -> int:
    config_path = Path(os.environ.get("ARC3_CONFIG", "configs/kaggle_27b.yaml"))
    model_path_value = os.environ.get("ARC3_MODEL_PATH")
    output = Path(os.environ.get("ARC3_OUTPUT", "/kaggle/working/arc3-voi-runs"))
    global_wall = os.environ.get("ARC3_GLOBAL_WALL_SECONDS")
    client = ArcCompetitionClient()
    encoded_ids = os.environ.get("ARC3_GAME_IDS")
    if not encoded_ids:
        raise RuntimeError(
            "ARC3_GAME_IDS is required from the copied official gateway; refusing "
            "to substitute the public metadata catalogue for a hidden workload"
        )
    game_ids = tuple(str(value) for value in json.loads(encoded_ids))
    if not game_ids:
        raise RuntimeError("ARC3_GAME_IDS contains an empty manifest")
    config = load_config(config_path)
    backend = backend_from_config(
        config,
        model_path=None if model_path_value is None else Path(model_path_value),
    )
    result = run_scorecard(
        game_ids,
        backend,
        config,
        output_directory=output,
        global_wall_seconds=None if global_wall is None else float(global_wall),
        client=client,
    )
    print(
        json.dumps(
            {
                "games_run": len(result.runs),
                "elapsed_seconds": result.elapsed_seconds,
                "stopped_early": result.stopped_early,
            },
            sort_keys=True,
        )
    )
    return int(result.stopped_early)


if __name__ == "__main__":
    raise SystemExit(main())
