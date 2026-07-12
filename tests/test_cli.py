from __future__ import annotations

import json

from arc3_voi.cli import main


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
