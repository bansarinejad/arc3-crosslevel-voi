from __future__ import annotations

import json

import pytest

from arc3_voi.cli import _archive_resolved_failure, _validate_pending_artifacts, main
from arc3_voi.experiment import RunSpec


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
                "error": None,
                "termination_reason": "win",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError, match="clean completion claim"):
        _validate_pending_artifacts((row,), tmp_path)


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

    _validate_pending_artifacts((row,), tmp_path)
