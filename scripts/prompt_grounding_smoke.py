"""Offline four-program grounding gate over a frozen replay history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from arc3_voi.agent import require_live_execution_admitted
from arc3_voi.config import load_config
from arc3_voi.experiment import stable_config_hash
from arc3_voi.grounding import (
    GOAL_ACTION_SPREAD_THRESHOLD,
    grounding_gate_reasons,
)
from arc3_voi.grounding_repair import (
    GroundedSource,
    generate_grounded_program_batches,
)
from arc3_voi.model import backend_from_config
from arc3_voi.preflight import detect_runtime
from arc3_voi.prompts import (
    HYPOTHESIS_DIVERSITY_ROLES,
    PROGRAM_SYSTEM_PROMPT,
    PROMPT_CONTRACT_SHA256,
    PROMPT_CONTRACT_VERSION,
    program_prompt,
)
from arc3_voi.provenance import inspect_git_provenance, inspect_model_artifact
from arc3_voi.rendering import (
    PERCEPTION_CONTRACT_SHA256,
    PERCEPTION_CONTRACT_VERSION,
    PERCEPTION_REFERENCE_RENDER_SHA256,
    render_grid_array,
)
from arc3_voi.replay import canonical_trace_hash, history_from_records, load_transitions
from arc3_voi.types import Action, ActionKind


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--trace", type=Path)
    source.add_argument("--fixture", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-canonical-trace-sha256")
    args = parser.parse_args()

    base_config = load_config(args.config)
    if base_config.model is None:
        raise ValueError("grounding smoke requires a model configuration")
    config = replace(
        base_config,
        experiment=replace(base_config.experiment, seed=args.seed),
        model=replace(base_config.model, offline=True),
    )
    require_live_execution_admitted(config)

    if args.trace is not None:
        trace_sha = canonical_trace_hash(args.trace)
        transitions = load_transitions(args.trace)
        if not transitions:
            raise ValueError("source trace contains no transitions")
        records = transitions[0].history
        history = transitions[0].domain_history()
        source_kind = "trace"
        source_path = args.trace
    else:
        assert args.fixture is not None
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        if fixture.get("schema_version") != 1:
            raise ValueError("unsupported history fixture schema")
        trace_sha = str(fixture["source_trace_canonical_sha256"])
        records = _fixture_history_records(fixture)
        history = history_from_records(records)
        declared_history_sha = fixture.get("history_canonical_sha256")
        if declared_history_sha != _history_sha256(records):
            raise ValueError("fixture history does not match its declared hash")
        source_kind = "history_fixture"
        source_path = args.fixture
    if args.expected_canonical_trace_sha256 and trace_sha != args.expected_canonical_trace_sha256:
        raise ValueError("source trace does not match the expected canonical hash")
    model_config = config.model
    assert model_config is not None
    backend = backend_from_config(config, model_path=args.model_path)
    try:
        grounded_generation = generate_grounded_program_batches(
            backend,
            history,
            variant=config.experiment.variant,
            target=config.hypotheses.max_hypotheses,
            initial_feedback=None,
            max_new_tokens_per_hypothesis=(config.generation.max_new_tokens_per_hypothesis),
            max_candidates=config.planning.max_candidates,
            timeout_seconds=config.sandbox.timeout_ms / 1000,
            memory_limit_mb=config.sandbox.memory_mb,
            rollout_depth=config.planning.depth,
            remaining_generated_tokens=config.experiment.max_generated_tokens,
            remaining_wall_seconds=config.experiment.max_wall_seconds,
            remaining_generation_batches=config.experiment.max_generation_batches,
        )
    finally:
        backend.close()

    grounded_sources = grounded_generation.programs
    programs = tuple(item.result for item in grounded_sources if item.result is not None)
    truncated = sum(sum(batch.generation.hit_token_limit) for batch in grounded_generation.batches)
    gate_reasons = list(
        grounding_gate_reasons(
            programs,
            truncated_sequences=truncated,
            peak_vram_gb=max(
                (
                    batch.generation.peak_vram_gb
                    for batch in grounded_generation.batches
                    if batch.generation.peak_vram_gb is not None
                ),
                default=None,
            ),
            tokens_per_second=(
                grounded_generation.output_tokens
                / sum(batch.generation.elapsed_seconds for batch in grounded_generation.batches)
                if sum(batch.generation.elapsed_seconds for batch in grounded_generation.batches)
                > 0
                else 0.0
            ),
            max_peak_vram_gb=model_config.max_peak_vram_gb or float("inf"),
            min_tokens_per_second=model_config.min_tokens_per_second or 0.0,
            require_hard_memory_limit=os.name == "posix",
        )
    )
    if len(programs) != len(grounded_sources):
        gate_reasons.append("one or more grounding evaluations raised an exception")
    reasons = tuple(gate_reasons)

    history_payload = json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    program_payloads = _program_payloads(grounded_sources)
    eligible = [program for program in programs if program.eligible]
    report: dict[str, Any] = {
        "schema_version": 5,
        "offline": True,
        "git": asdict(inspect_git_provenance()),
        "model_id": model_config.id,
        "expected_model_revision": model_config.expected_revision,
        "expected_weight_manifest_sha256": model_config.expected_weight_manifest_sha256,
        "model_artifact": asdict(inspect_model_artifact(args.model_path)),
        "seed": args.seed,
        "base_config_sha256": stable_config_hash(base_config),
        "effective_offline_config_sha256": stable_config_hash(config),
        "source_input_kind": source_kind,
        "source_input": _repo_relative_path(source_path),
        "source_input_sha256": _file_sha256(source_path),
        "source_trace_canonical_sha256": trace_sha,
        "history_canonical_sha256": hashlib.sha256(history_payload).hexdigest(),
        "latest_grid_uint8_sha256": hashlib.sha256(
            history.latest_grid.astype(np.uint8).tobytes(order="C")
        ).hexdigest(),
        "latest_grid_int16_sha256": hashlib.sha256(
            history.latest_grid.tobytes(order="C")
        ).hexdigest(),
        "latest_rendered_rgb_sha256": hashlib.sha256(
            render_grid_array(history.latest_grid).tobytes(order="C")
        ).hexdigest(),
        "history_frames": len(history.frames),
        "observed_palette_values": [int(value) for value in np.unique(history.latest_grid)],
        "evaluation_actions_by_batch": [
            [_action_label(action) for action in batch.actions]
            for batch in grounded_generation.batches
        ],
        "grounding_evaluation": {
            "rollout_depth": config.planning.depth,
            "rollout_paths": "repeat each root candidate action",
            "goal_action_spread_threshold": GOAL_ACTION_SPREAD_THRESHOLD,
            "goal_metric_scope": (
                "same-depth action-conditioned variation; not semantic alignment evidence"
            ),
            "terminal_policy": (
                "stop before goal_value after WIN, GAME_OVER, or positive level_delta"
            ),
            "candidate_roles": list(HYPOTHESIS_DIVERSITY_ROLES),
        },
        "system_prompt_sha256": hashlib.sha256(PROGRAM_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "user_prompt_sha256": [
            hashlib.sha256(
                program_prompt(
                    history,
                    feedback=batch.feedback,
                    candidate_index=index,
                    candidate_count=config.hypotheses.max_hypotheses,
                ).encode("utf-8")
            ).hexdigest()
            for batch in grounded_generation.batches
            for index in range(len(batch.generation.texts))
        ],
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "perception_contract_version": PERCEPTION_CONTRACT_VERSION,
        "prompt_contract_sha256": PROMPT_CONTRACT_SHA256,
        "perception_contract_sha256": PERCEPTION_CONTRACT_SHA256,
        "perception_reference_render_sha256": PERCEPTION_REFERENCE_RENDER_SHA256,
        "runtime": asdict(detect_runtime()),
        "generation": {
            "requested": config.hypotheses.max_hypotheses,
            "batches_used": len(grounded_generation.batches),
            "repair_attempts": grounded_generation.repair_attempts,
            "repair_feedback": grounded_generation.repair_feedback,
            "output_tokens": grounded_generation.output_tokens,
            "sequence_token_counts": tuple(
                value
                for batch in grounded_generation.batches
                for value in batch.generation.sequence_token_counts
            ),
            "elapsed_seconds": sum(
                batch.generation.elapsed_seconds for batch in grounded_generation.batches
            ),
            "tokens_per_second": (
                grounded_generation.output_tokens
                / sum(batch.generation.elapsed_seconds for batch in grounded_generation.batches)
                if sum(batch.generation.elapsed_seconds for batch in grounded_generation.batches)
                > 0
                else 0.0
            ),
            "peak_vram_gb": max(
                (
                    batch.generation.peak_vram_gb
                    for batch in grounded_generation.batches
                    if batch.generation.peak_vram_gb is not None
                ),
                default=None,
            ),
            "truncated_sequences": truncated,
            "batches": [
                {
                    "batch_index": batch.batch_index,
                    "requested": (
                        config.hypotheses.max_hypotheses
                        if batch.batch_index > 0
                        else min(
                            config.hypotheses.max_hypotheses,
                            config.experiment.max_generated_tokens,
                        )
                    ),
                    "returned": len(batch.generation.texts),
                    "feedback": batch.feedback,
                    "output_tokens": batch.generation.output_tokens,
                    "sequence_token_counts": batch.generation.sequence_token_counts,
                    "elapsed_seconds": batch.generation.elapsed_seconds,
                    "tokens_per_second": batch.generation.tokens_per_second,
                    "peak_vram_gb": batch.generation.peak_vram_gb,
                    "truncated_sequences": sum(batch.generation.hit_token_limit),
                }
                for batch in grounded_generation.batches
            ],
        },
        "programs": program_payloads,
        "summary": {
            "sandbox_valid_programs": sum(program.sandbox_valid for program in programs),
            "grounded_safe_programs": len(eligible),
            "distinct_behavior_classes": len(
                {
                    program.behavior_signature
                    for program in eligible
                    if program.behavior_signature is not None
                }
            ),
            "action_sensitive_programs": sum(program.action_sensitive for program in eligible),
            "goal_action_conditioned_programs": sum(
                program.goal_action_conditioned for program in eligible
            ),
            "graded_role_programs": sum(
                program.action_sensitivity_required
                and program.goal_conditioning_required
                and program.eligible
                for program in programs
            ),
            "unsafe_coordinate_programs": sum(
                program.unsafe_coordinate_use for program in programs
            ),
            "palette_conflict_programs": sum(
                bool(program.palette_conflicts) for program in programs
            ),
            "hard_memory_limit_required": os.name == "posix",
            "hard_memory_limit_enforced_programs": sum(
                program.hard_memory_limit_enforced is True for program in eligible
            ),
            "passes": not reasons,
            "gate_reasons": reasons,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if not reasons else 2


def _program_payloads(
    grounded_sources: tuple[GroundedSource, ...],
) -> list[dict[str, Any]]:
    """Serialize global order while preserving batch-local role indices."""

    payloads: list[dict[str, Any]] = []
    for index, grounded in enumerate(grounded_sources):
        program = grounded.result
        value: dict[str, Any]
        if program is None:
            value = {
                "source_sha256": hashlib.sha256(grounded.source.encode("utf-8")).hexdigest(),
                "evaluation_error": grounded.evaluation_error,
                "eligible": False,
            }
        else:
            value = asdict(program)
            value["palette_conflicts"] = len(program.palette_conflicts)
            value["eligible"] = program.eligible
        value["source"] = grounded.source
        value["candidate_index"] = index
        value["batch_index"] = grounded.batch_index
        value["batch_candidate_index"] = grounded.candidate_index
        value["assigned_role"] = grounded.assigned_role
        payloads.append(value)
    return payloads


def _action_label(action: Action) -> str:
    if action.kind is ActionKind.ACTION6:
        return f"ACTION6({action.row},{action.col})"
    return action.kind.name


def _fixture_history_records(fixture: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for raw in fixture.get("history", ()):
        rows = raw.get("grid_hex_rows", ())
        if len(rows) != 64 or any(len(row) != 64 for row in rows):
            raise ValueError("fixture grids must contain exactly 64 hexadecimal rows")
        try:
            grid = [[int(character, 16) for character in row] for row in rows]
        except ValueError as exc:
            raise ValueError("fixture grid contains a non-hexadecimal cell") from exc
        records.append(
            {
                "grid": grid,
                "action": raw.get("action"),
                "available_actions": list(raw["available_actions"]),
                "game_state": str(raw["game_state"]),
                "level_delta": int(raw["level_delta"]),
                "level": int(raw["level"]),
                "win_levels": int(raw["win_levels"]),
            }
        )
    if not records:
        raise ValueError("fixture history is empty")
    return tuple(records)


def _history_sha256(records: tuple[dict[str, Any], ...]) -> str:
    payload = json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative_path(path: Path) -> str:
    repository = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(repository).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
