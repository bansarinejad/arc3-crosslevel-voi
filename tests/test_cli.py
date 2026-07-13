from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import arc3_voi.cli as cli_module
from arc3_voi.cli import (
    _archive_resolved_failure,
    _validate_existing_manifest_artifacts,
    _validate_pending_artifacts,
    main,
)
from arc3_voi.experiment import RunSpec

PRODUCER_CONTRACT_SHA256 = "b" * 64


def test_config_check(capsys) -> None:
    assert main(["config-check", "configs/local_9b.yaml"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["config"]["model"]["id"] == "Qwen/Qwen3.5-9B"


def test_matrix_command(tmp_path) -> None:
    split = tmp_path / "split.json"
    split.write_text(
        json.dumps(
            {
                "seed": 20260712,
                "development": [f"d{i}" for i in range(15)],
                "confirmation": [f"c{i}" for i in range(10)],
                "metadata_hash": "a" * 64,
                "game_versions": {
                    **{f"d{i}": f"v{i}" for i in range(15)},
                    **{f"c{i}": f"v{i}" for i in range(10)},
                },
            }
        )
    )
    output = tmp_path / "matrix.json"
    assert (
        main(
            [
                "matrix",
                "development",
                "--split",
                str(split),
                "--config",
                "configs/local_9b.yaml",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    matrix = json.loads(output.read_text())
    assert len(matrix) == 180
    assert len({row["config_hash"] for row in matrix}) == 4
    assert matrix[0]["game_version"] == "v0"
    assert matrix[0]["snapshot_hash"] == "a" * 64
    assert matrix[0]["arm_label"] == "D-Q"
    assert matrix[0]["hypothesis_source"] == "qwen"
    assert matrix[0]["identity_version"] == "source-v2"


def test_template_matrix_command_creates_separate_source_aware_arms(tmp_path) -> None:
    split = tmp_path / "split.json"
    split.write_text(
        json.dumps(
            {
                "seed": 20260712,
                "development": [f"d{i}" for i in range(15)],
                "confirmation": [f"c{i}" for i in range(10)],
                "metadata_hash": "a" * 64,
                "game_versions": {
                    **{f"d{i}": f"v{i}" for i in range(15)},
                    **{f"c{i}": f"v{i}" for i in range(10)},
                },
            }
        )
    )
    output = tmp_path / "development_matrix_template_v1.json"

    assert main(
        [
            "matrix",
            "development",
            "--split",
            str(split),
            "--config",
            "configs/local_4b.yaml",
            "--hypothesis-source",
            "template_v1",
            "--out",
            str(output),
        ]
    ) == 0
    rows = json.loads(output.read_text(encoding="utf-8"))

    assert len(rows) == 180
    assert {row["arm_label"] for row in rows} == {"D-Q", "S-T", "M-T", "X-T"}
    assert {row["hypothesis_source"] for row in rows} == {"qwen", "template_v1"}
    assert len({row["config_hash"] for row in rows}) == 4
    assert all(row["identity_version"] == "source-v2" for row in rows)

    with pytest.raises(ValueError, match="registration-only; run-matrix execution remains"):
        main(
            [
                "run-matrix",
                "--matrix",
                str(output),
                "--config",
                "configs/local_4b.yaml",
                "--metadata",
                str(tmp_path / "not-read-before-source-guard.json"),
                "--output",
                str(tmp_path / "runs"),
                "--dry-run",
            ]
        )


def test_locked_qwen_matrix_bytes_remain_frozen() -> None:
    digest = hashlib.sha256(
        (Path("artifacts") / "development_matrix.json").read_bytes()
    ).hexdigest()

    assert digest == "ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147"

    with pytest.raises(ValueError, match="legacy-v1 matrices are audit-only"):
        main(
            [
                "run-matrix",
                "--matrix",
                "artifacts/development_matrix.json",
                "--config",
                "configs/local_4b.yaml",
                "--metadata",
                "not-read-before-identity-guard.json",
                "--output",
                "not-created",
                "--dry-run",
            ]
        )


def test_blocked_template_artifact_does_not_unlock_checked_in_matrix(tmp_path: Path) -> None:
    artifact = Path("artifacts/template_v1_runtime_admission_v2_bp35_seed11.json")
    assert json.loads(artifact.read_text(encoding="utf-8"))["status"] == "pilot_blocked"

    with pytest.raises(ValueError, match="registration-only; run-matrix execution remains"):
        main(
            [
                "run-matrix",
                "--matrix",
                "artifacts/development_matrix_template_v1.json",
                "--config",
                "configs/local_4b.yaml",
                "--metadata",
                str(tmp_path / "must-not-be-read.json"),
                "--output",
                str(tmp_path / "must-not-be-created"),
                "--dry-run",
            ]
        )

    assert not (tmp_path / "must-not-be-created").exists()


def test_select_hyperparameters_command(tmp_path, capsys) -> None:
    observations = [
        {
            "game_id": "g",
            "seed": 11,
            "eta": eta,
            "complexity_lambda": value,
            "rhae": 0.5,
            "generated_tokens": 10 if (eta, value) == (5.0, 0.002) else 20,
        }
        for eta in (2.0, 5.0, 10.0)
        for value in (0.0, 0.002, 0.01)
    ]
    source = tmp_path / "grid.json"
    source.write_text(json.dumps(observations))
    assert main(["select-hyperparameters", "--input", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["complexity_lambda"] == 0.002


def test_run_rejects_template_source_before_backend_or_environment_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "template.yaml"
    config.write_text(
        Path("configs/base.yaml")
        .read_text(encoding="utf-8")
        .replace("hypothesis_source: qwen", "hypothesis_source: template_v1"),
        encoding="utf-8",
    )
    calls: list[str] = []

    def unexpected_backend(*args, **kwargs):
        del args, kwargs
        calls.append("backend")
        raise AssertionError("backend must not be created")

    class UnexpectedClient:
        def __init__(self) -> None:
            calls.append("environment")
            raise AssertionError("environment client must not be created")

    monkeypatch.setattr(cli_module, "_model_backend", unexpected_backend)
    monkeypatch.setattr(cli_module, "ArcCompetitionClient", UnexpectedClient)

    with pytest.raises(ValueError, match="registration-only; live producer wiring"):
        main(
            [
                "run",
                "--config",
                str(config),
                "--game",
                "g",
                "--seed",
                "11",
                "--run-id",
                "blocked-template",
                "--output",
                str(tmp_path / "runs"),
            ]
        )

    assert calls == []


def test_analyze_rejects_implicit_pooling_of_qwen_and_template_arms(
    tmp_path: Path,
) -> None:
    rows = [
        {
            "game_id": "g",
            "seed": 11,
            "variant": variant,
            "rhae": score,
            "hypothesis_source": source,
            "arm_label": arm,
            "identity_version": "source-v2",
            "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
            "model_profile": "test",
            "config_hash": arm.lower(),
        }
        for source, arm, variant, score in (
            ("qwen", "X-Q", "X", 0.5),
            ("qwen", "M-Q", "M", 0.4),
            ("template_v1", "X-T", "X", 0.6),
            ("template_v1", "M-T", "M", 0.5),
        )
    ]
    source = tmp_path / "mixed.json"
    source.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="mixes hypothesis sources"):
        main(["analyze", "--input", str(source)])


def test_analyze_filters_one_explicit_source_and_exact_arm_pair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [
        {
            "game_id": "g",
            "seed": 11,
            "variant": variant,
            "rhae": score,
            "hypothesis_source": source,
            "arm_label": arm,
            "identity_version": "source-v2",
            "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
            "model_profile": "test",
            "config_hash": arm.lower(),
        }
        for source, arm, variant, score in (
            ("qwen", "X-Q", "X", 0.1),
            ("qwen", "M-Q", "M", 0.9),
            ("template_v1", "X-T", "X", 0.6),
            ("template_v1", "M-T", "M", 0.5),
        )
    ]
    source = tmp_path / "mixed.json"
    source.write_text(json.dumps(rows), encoding="utf-8")

    assert main(
        [
            "analyze",
            "--input",
            str(source),
            "--hypothesis-source",
            "template_v1",
            "--treatment-arm",
            "X-T",
            "--comparator-arm",
            "M-T",
            "--bootstrap-samples",
            "100",
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["comparison_identity"] == {
        "hypothesis_source": "template_v1",
        "treatment_arm": "X-T",
        "comparator_arm": "M-T",
    }
    assert result["deltas"] == {"g": pytest.approx(0.1)}


def test_analyze_rejects_multiple_config_hashes_within_one_arm(tmp_path: Path) -> None:
    rows = [
        {
            "game_id": game,
            "seed": 11,
            "variant": variant,
            "rhae": score,
            "hypothesis_source": "template_v1",
            "arm_label": f"{variant}-T",
            "identity_version": "source-v2",
            "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
            "model_profile": "test",
            "config_hash": config_hash,
        }
        for game, variant, score, config_hash in (
            ("a", "X", 0.6, "x1"),
            ("b", "X", 0.6, "x2"),
            ("a", "M", 0.5, "m"),
            ("b", "M", 0.5, "m"),
        )
    ]
    source = tmp_path / "mixed-configs.json"
    source.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="config hashes within an arm"):
        main(
            [
                "analyze",
                "--input",
                str(source),
                "--hypothesis-source",
                "template_v1",
            ]
        )


def test_successful_retry_archives_stale_failure_by_content_hash(tmp_path) -> None:
    run_id = "development-game-11-X-deadbeef"
    failure = tmp_path / "failures" / f"{run_id}.json"
    failure.parent.mkdir()
    content = b'{"error":"old attempt"}\n'
    failure.write_bytes(content)

    resolved = _archive_resolved_failure(tmp_path, run_id)

    assert resolved is not None
    assert not failure.exists()
    assert resolved.read_bytes() == content
    assert len(resolved.stem.rsplit(".", 1)[-1]) == 64


def test_matrix_preflight_rejects_corrupt_clean_claim_before_execution(tmp_path) -> None:
    row = RunSpec(
        phase="development",
        game_id="game",
        seed=11,
        variant="X",
        model_profile="test",
        config_hash="abc",
        game_version="v1",
    )
    summary = tmp_path / f"{row.run_id}.json"
    summary.write_text(
        json.dumps(
            {
                "run_id": row.run_id,
                "game_id": row.full_game_id,
                "seed": row.seed,
                "variant": row.variant,
                "model_profile": row.model_profile,
                "config_hash": row.config_hash,
                "hypothesis_source": row.hypothesis_source,
                "arm_label": row.arm_label,
                "identity_version": row.identity_version,
                "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
                "error": None,
                "termination_reason": "win",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError, match="clean completion claim"):
        _validate_pending_artifacts(
            (row,), tmp_path, producer_contract_sha256=PRODUCER_CONTRACT_SHA256
        )


def test_matrix_preflight_allows_matching_failed_pair_to_retry(tmp_path) -> None:
    row = RunSpec(
        phase="development",
        game_id="game",
        seed=11,
        variant="X",
        model_profile="test",
        config_hash="abc",
        game_version="v1",
    )
    summary = tmp_path / f"{row.run_id}.json"
    summary.write_text(
        json.dumps(
            {
                "run_id": row.run_id,
                "game_id": row.full_game_id,
                "seed": row.seed,
                "variant": row.variant,
                "model_profile": row.model_profile,
                "config_hash": row.config_hash,
                "hypothesis_source": row.hypothesis_source,
                "arm_label": row.arm_label,
                "identity_version": row.identity_version,
                "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
                "error": "simulated failure",
                "termination_reason": None,
                "decision_points": 0,
                "total_actions": 0,
                "generated_tokens": 0,
                "direct_fallbacks": 0,
                "two_valid_decision_points": 0,
            }
        ),
        encoding="utf-8",
    )
    summary.with_suffix(".jsonl").write_text("", encoding="utf-8")

    _validate_pending_artifacts(
        (row,), tmp_path, producer_contract_sha256=PRODUCER_CONTRACT_SHA256
    )


def test_matrix_preflight_rejects_retry_with_different_producer_contract(tmp_path) -> None:
    row = RunSpec(
        phase="development",
        game_id="game",
        seed=11,
        variant="X",
        model_profile="test",
        config_hash="abc",
        game_version="v1",
    )
    summary = tmp_path / f"{row.run_id}.json"
    summary.write_text(
        json.dumps(
            {
                "run_id": row.run_id,
                "game_id": row.full_game_id,
                "seed": row.seed,
                "variant": row.variant,
                "model_profile": row.model_profile,
                "config_hash": row.config_hash,
                "hypothesis_source": row.hypothesis_source,
                "arm_label": row.arm_label,
                "identity_version": row.identity_version,
                "producer_contract_sha256": "c" * 64,
                "error": "simulated failure",
                "termination_reason": None,
                "decision_points": 0,
                "total_actions": 0,
                "generated_tokens": 0,
                "direct_fallbacks": 0,
                "two_valid_decision_points": 0,
            }
        ),
        encoding="utf-8",
    )
    summary.with_suffix(".jsonl").write_text("", encoding="utf-8")

    with pytest.raises(FileExistsError, match="producer_contract_sha256"):
        _validate_pending_artifacts(
            (row,), tmp_path, producer_contract_sha256=PRODUCER_CONTRACT_SHA256
        )


def test_matrix_preflight_rejects_complete_artifact_with_wrong_source_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = RunSpec(
        phase="development",
        game_id="game",
        seed=11,
        variant="X",
        model_profile="test",
        config_hash="abc",
        game_version="v1",
    )
    summary = {
        "run_id": row.run_id,
        "game_id": row.full_game_id,
        "seed": row.seed,
        "variant": row.variant,
        "model_profile": row.model_profile,
        "config_hash": row.config_hash,
        "hypothesis_source": "template_v1",
        "arm_label": "X-T",
        "identity_version": "source-v2",
        "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
    }
    monkeypatch.setattr(cli_module, "read_complete_run", lambda _path: (summary, ()))

    with pytest.raises(ValueError, match="hypothesis_source, arm_label"):
        _validate_existing_manifest_artifacts(
            (row,), tmp_path, producer_contract_sha256=PRODUCER_CONTRACT_SHA256
        )
