"""Command-line entry points for reproducible local and Kaggle workflows."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .agent import build_agent
from .arc_adapter import ArcCompetitionClient
from .config import SystemConfig, load_config
from .experiment import (
    HyperparameterObservation,
    RunSpec,
    Variant,
    build_confirmation_matrix,
    build_development_matrix,
    build_kaggle_transfer_matrix,
    load_matrix,
    pending_runs,
    save_matrix,
    select_eta_lambda,
    stable_config_hash,
)
from .metrics import write_run
from .model import TransformersQwenBackend, backend_from_config
from .preflight import run_model_preflight
from .provenance import inspect_model_artifact
from .rendering import PERCEPTION_REFERENCE_RENDER_SHA256
from .runner import run_game
from .splitting import (
    SplitManifest,
    load_metadata,
    metadata_hash,
    save_snapshot,
    stratified_split,
)
from .statistics import (
    ScoreObservation,
    paired_game_deltas,
    summarize_paired_observations,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arc3-voi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config-check")
    config_parser.add_argument("config", type=Path)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--out", type=Path, required=True)

    split_parser = subparsers.add_parser("split")
    split_parser.add_argument("--metadata", type=Path, required=True)
    split_parser.add_argument("--out", type=Path, required=True)
    split_parser.add_argument("--development-size", type=int, default=15)

    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("phase", choices=("development", "confirmation", "kaggle-transfer"))
    matrix_parser.add_argument("--split", type=Path, required=True)
    matrix_parser.add_argument("--config", type=Path, required=True)
    matrix_parser.add_argument("--out", type=Path, required=True)
    matrix_parser.add_argument("--comparator", choices=("D", "S", "M"), default="M")
    matrix_parser.add_argument("--fallback", action="store_true")

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--config", type=Path, required=True)
    preflight_parser.add_argument("--model-path", type=Path)
    preflight_parser.add_argument("--durations", type=Path)
    preflight_parser.add_argument("--hidden-game-count", type=int)
    preflight_parser.add_argument("--runtime-limit-seconds", type=float)
    preflight_parser.add_argument("--out", type=Path)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", type=Path, required=True)
    run_parser.add_argument("--game", required=True)
    run_parser.add_argument("--seed", type=int, required=True)
    run_parser.add_argument("--variant", choices=("D", "S", "M", "X"))
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--model-path", type=Path)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--baseline-actions")

    matrix_run_parser = subparsers.add_parser("run-matrix")
    matrix_run_parser.add_argument("--matrix", type=Path, required=True)
    matrix_run_parser.add_argument("--config", type=Path, required=True)
    matrix_run_parser.add_argument("--metadata", type=Path, required=True)
    matrix_run_parser.add_argument("--model-path", type=Path)
    matrix_run_parser.add_argument("--output", type=Path, required=True)
    matrix_run_parser.add_argument("--limit", type=int)
    matrix_run_parser.add_argument("--dry-run", action="store_true")

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--input", type=Path, required=True)
    analyze_parser.add_argument("--treatment", default="X")
    analyze_parser.add_argument("--comparator", default="M")
    analyze_parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    analyze_parser.add_argument("--out", type=Path)

    select_parser = subparsers.add_parser("select-hyperparameters")
    select_parser.add_argument("--input", type=Path, required=True)
    select_parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "config-check":
        config = load_config(args.config)
        _emit({"config": asdict(config), "sha256": stable_config_hash(config)})
        return 0
    if args.command == "snapshot":
        save_snapshot(ArcCompetitionClient().public_metadata(), args.out)
        _emit({"snapshot": str(args.out)})
        return 0
    if args.command == "split":
        manifest = stratified_split(
            load_metadata(args.metadata), development_size=args.development_size
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(manifest.to_json(), encoding="utf-8", newline="\n")
        _emit(asdict(manifest))
        return 0
    if args.command == "matrix":
        _matrix_command(args)
        return 0
    if args.command == "preflight":
        _preflight_command(args)
        return 0
    if args.command == "run":
        return _run_command(args)
    if args.command == "run-matrix":
        return _run_matrix_command(args)
    if args.command == "analyze":
        _analyze_command(args)
        return 0
    if args.command == "select-hyperparameters":
        _select_hyperparameters_command(args)
        return 0
    raise AssertionError(f"unhandled command {args.command}")


def _model_backend(config: SystemConfig, model_path: Path | None) -> TransformersQwenBackend:
    return backend_from_config(config, model_path=model_path)


def _matrix_command(args: argparse.Namespace) -> None:
    split = _load_split(args.split)
    config = load_config(args.config)
    profile = config.model.profile if config.model else "no-model"
    if args.phase == "development":
        variants: tuple[Variant, ...] = ("D", "S", "M", "X")
        digests = _variant_hashes(config, variants)
        matrix = build_development_matrix(
            split.development,
            model_profile=profile,
            config_hashes=digests,
            game_versions=split.game_versions,
            snapshot_hash=split.metadata_hash,
            fallback=args.fallback,
        )
    elif args.phase == "confirmation":
        variants = (args.comparator, "X")
        digests = _variant_hashes(config, variants)
        matrix = build_confirmation_matrix(
            split.confirmation,
            comparator=args.comparator,
            model_profile=profile,
            config_hashes=digests,
            game_versions=split.game_versions,
            snapshot_hash=split.metadata_hash,
            fallback=args.fallback,
        )
    else:
        variants = (args.comparator, "X")
        digests = _variant_hashes(config, variants)
        matrix = build_kaggle_transfer_matrix(
            split.confirmation,
            comparator=args.comparator,
            config_hashes=digests,
            game_versions=split.game_versions,
            snapshot_hash=split.metadata_hash,
        )
    save_matrix(matrix, args.out)
    _emit({"runs": len(matrix), "path": str(args.out), "config_hashes": digests})


def _variant_hashes(
    config: SystemConfig, variants: tuple[Variant, ...]
) -> dict[Variant, str]:
    return {
        variant: stable_config_hash(
            replace(config, experiment=replace(config.experiment, variant=variant))
        )
        for variant in variants
    }


def _preflight_command(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if config.model is None:
        raise ValueError("preflight requires a model profile")
    durations = None
    if args.durations:
        value = json.loads(args.durations.read_text(encoding="utf-8"))
        durations = [float(item) for item in value]
    backend = _model_backend(config, args.model_path)
    try:
        report = run_model_preflight(
            backend,
            model_id=config.model.id,
            max_peak_vram_gb=config.model.max_peak_vram_gb or float("inf"),
            min_tokens_per_second=config.model.min_tokens_per_second or 0.0,
            observed_game_seconds=durations,
            hidden_game_count=args.hidden_game_count,
            runtime_limit_seconds=args.runtime_limit_seconds,
            program_count=config.hypotheses.max_hypotheses,
            config_sha256=stable_config_hash(config),
            prompt_contract_version=config.experiment.prompt_contract_version,
            perception_contract_version=config.experiment.perception_contract_version,
            prompt_contract_sha256=config.experiment.prompt_contract_sha256,
            perception_contract_sha256=config.experiment.perception_contract_sha256,
            perception_reference_render_sha256=PERCEPTION_REFERENCE_RENDER_SHA256,
            model_artifact=inspect_model_artifact(args.model_path),
            expected_model_revision=config.model.expected_revision,
            expected_weight_manifest_sha256=(
                config.model.expected_weight_manifest_sha256
            ),
        )
    finally:
        backend.close()
    _emit(report.as_dict(), args.out)


def _run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    experiment = replace(config.experiment, seed=args.seed)
    if args.variant:
        experiment = replace(experiment, variant=args.variant)
    config = replace(config, experiment=experiment)
    backend = _model_backend(config, args.model_path)
    client = ArcCompetitionClient()
    session = client.make(args.game, seed=args.seed)
    baselines = (
        tuple(int(value) for value in args.baseline_actions.split(","))
        if args.baseline_actions
        else None
    )
    with build_agent(backend, config) as agent:
        metrics = run_game(
            session,
            agent.controller,
            run_id=args.run_id,
            seed=args.seed,
            variant=config.experiment.variant,
            model_profile=config.model.profile if config.model else "no-model",
            config_hash=stable_config_hash(config),
            model_revision=config.model.expected_revision if config.model else None,
            weight_manifest_sha256=(
                config.model.expected_weight_manifest_sha256 if config.model else None
            ),
            max_environment_actions=config.experiment.max_environment_actions,
            max_generated_tokens=config.experiment.max_generated_tokens,
            max_wall_seconds=config.experiment.max_wall_seconds,
            baseline_actions=baselines,
        )
    paths = write_run(metrics, args.output)
    _emit({"summary": str(paths[0]), "trace": str(paths[1]), **metrics.summary()})
    return 2 if metrics.error is not None or metrics.termination_reason is None else 0


def _run_matrix_command(args: argparse.Namespace) -> int:
    matrix = load_matrix(args.matrix)
    config = load_config(args.config)
    metadata = load_metadata(args.metadata)
    actual_snapshot_hash = metadata_hash(metadata)
    manifest_snapshot_hash = matrix[0].snapshot_hash
    if actual_snapshot_hash != manifest_snapshot_hash:
        raise ValueError("metadata snapshot does not match the matrix snapshot hash")
    versions = {game.game_id: game.version for game in metadata}
    baselines = {game.game_id: game.baseline_actions for game in metadata}
    for row in matrix:
        if versions.get(row.game_id) != row.game_version:
            raise ValueError(f"frozen version mismatch for {row.game_id}")

    variants: tuple[Variant, ...] = tuple(sorted({row.variant for row in matrix}))
    expected_hashes = _variant_hashes(config, variants)
    for row in matrix:
        if row.config_hash != expected_hashes[row.variant]:
            raise ValueError(f"config hash mismatch for {row.run_id}")
    expected_profile = config.model.profile if config.model else "no-model"
    if any(row.model_profile != expected_profile for row in matrix):
        raise ValueError("matrix model profile does not match the supplied config")

    pending = pending_runs(matrix, args.output)
    if args.limit is not None:
        if args.limit < 0:
            raise ValueError("limit must be non-negative")
        pending = pending[: args.limit]
    if args.dry_run:
        _emit(
            {
                "total": len(matrix),
                "pending": len(pending),
                "run_ids": [row.run_id for row in pending],
            }
        )
        return 0
    failures: list[dict[str, str]] = []
    completed = 0
    for row in pending:
        try:
            _execute_manifest_row(row, config, args.model_path, baselines, args.output)
            completed += 1
        except Exception as exc:
            failure = {"run_id": row.run_id, "type": type(exc).__name__, "error": str(exc)}
            failures.append(failure)
            failure_dir = args.output / "failures"
            failure_dir.mkdir(parents=True, exist_ok=True)
            (failure_dir / f"{row.run_id}.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    _emit(
        {
            "manifest_runs": len(matrix),
            "attempted": len(pending),
            "completed": completed,
            "failures": failures,
            "remaining": len(pending_runs(matrix, args.output)),
        }
    )
    return 2 if failures else 0


def _execute_manifest_row(
    row: RunSpec,
    base_config: SystemConfig,
    model_path: Path | None,
    baselines: dict[str, tuple[int, ...]],
    output: Path,
) -> None:
    config = replace(
        base_config,
        experiment=replace(base_config.experiment, variant=row.variant, seed=row.seed),
    )
    backend = _model_backend(config, model_path)
    session = ArcCompetitionClient().make(row.full_game_id, seed=row.seed)
    with build_agent(backend, config) as agent:
        metrics = run_game(
            session,
            agent.controller,
            run_id=row.run_id,
            seed=row.seed,
            variant=row.variant,
            model_profile=row.model_profile,
            config_hash=row.config_hash,
            model_revision=config.model.expected_revision if config.model else None,
            weight_manifest_sha256=(
                config.model.expected_weight_manifest_sha256 if config.model else None
            ),
            max_environment_actions=config.experiment.max_environment_actions,
            max_generated_tokens=config.experiment.max_generated_tokens,
            max_wall_seconds=config.experiment.max_wall_seconds,
            baseline_actions=baselines[row.game_id],
        )
    write_run(metrics, output)
    if metrics.error is not None or metrics.termination_reason is None:
        detail = metrics.error or "missing termination reason"
        raise RuntimeError(f"run did not complete cleanly: {detail}")


def _analyze_command(args: argparse.Namespace) -> None:
    raw = _load_json_records(args.input)
    observations = [
        ScoreObservation(
            str(item["game_id"]),
            int(item["seed"]),
            str(item["variant"]),
            float(item["rhae"]),
        )
        for item in raw
        if item.get("rhae") is not None
    ]
    deltas = paired_game_deltas(observations, args.treatment, args.comparator)
    summary = summarize_paired_observations(
        observations,
        args.treatment,
        args.comparator,
        bootstrap_samples=args.bootstrap_samples,
    )
    _emit({"deltas": deltas, "summary": asdict(summary)}, args.out)


def _select_hyperparameters_command(args: argparse.Namespace) -> None:
    raw = _load_json_records(args.input)
    observations = [
        HyperparameterObservation(
            game_id=str(item["game_id"]),
            seed=int(item["seed"]),
            eta=float(item["eta"]),
            complexity_lambda=float(item["complexity_lambda"]),
            rhae=float(item["rhae"]),
            generated_tokens=int(item["generated_tokens"]),
        )
        for item in raw
    ]
    _emit(asdict(select_eta_lambda(observations)), args.out)


def _load_split(path: Path) -> SplitManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SplitManifest(
        seed=int(raw["seed"]),
        development=tuple(raw["development"]),
        confirmation=tuple(raw["confirmation"]),
        metadata_hash=str(raw["metadata_hash"]),
        game_versions={str(key): str(value) for key, value in raw.get("game_versions", {}).items()},
        algorithm=str(raw.get("algorithm", "legacy-unknown")),
        supersedes_manifest_hash=(
            str(raw["supersedes_manifest_hash"])
            if raw.get("supersedes_manifest_hash") is not None
            else None
        ),
    )


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else list(value.get("runs", ()))


def _emit(value: Any, path: Path | None = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
