"""One-action anonymous smoke test against the official ARC endpoint."""

from __future__ import annotations

import json
from typing import cast

from arc3_voi.agent import (
    build_agent,
    qwen_producer_contract_sha256,
    require_live_execution_admitted,
)
from arc3_voi.arc_adapter import ArcCompetitionClient
from arc3_voi.config import ExperimentConfig, SystemConfig
from arc3_voi.experiment import Variant, arm_label_for
from arc3_voi.model import ScriptedBackend
from arc3_voi.runner import run_game


def main() -> int:
    config = SystemConfig(
        experiment=ExperimentConfig(
            variant="D",
            max_environment_actions=1,
            max_generated_tokens=16,
            max_wall_seconds=20,
        )
    )
    require_live_execution_admitted(config)
    producer_contract_sha256 = qwen_producer_contract_sha256(config)
    backend = ScriptedBackend(
        action_policy=lambda _history, valid: {"kind": valid[0].split("(", 1)[0]}
    )
    session = ArcCompetitionClient().make("ls20", seed=0)
    with build_agent(backend, config) as agent:
        metrics = run_game(
            session,
            agent.controller,
            run_id="official-anonymous-smoke",
            seed=0,
            variant="D",
            model_profile="scripted-smoke",
            config_hash="smoke",
            hypothesis_source=config.experiment.hypothesis_source,
            arm_label=arm_label_for(
                cast(Variant, config.experiment.variant),
                config.experiment.hypothesis_source,
            ),
            identity_version="source-v2",
            producer_contract_sha256=producer_contract_sha256,
            max_environment_actions=1,
            max_generated_tokens=16,
            max_wall_seconds=20,
        )
    print(json.dumps(metrics.summary(), indent=2, sort_keys=True))
    return 0 if metrics.total_actions == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
