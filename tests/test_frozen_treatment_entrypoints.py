from __future__ import annotations

import sys
from dataclasses import replace

import pytest

import kaggle.entrypoint as kaggle_entrypoint
import scripts.model_smoke as model_smoke
import scripts.prompt_grounding_smoke as grounding_smoke
from arc3_voi.agent import TreatmentNotAdmittedError
from arc3_voi.config import load_config


def _qwen_path_deficit_config():
    template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    return replace(
        template,
        experiment=replace(template.experiment, hypothesis_source="qwen"),
    )


def _must_not_construct(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("resource construction must follow treatment admission")


def test_model_smoke_rejects_frozen_treatment_before_backend_or_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_smoke, "load_config", lambda _path: _qwen_path_deficit_config())
    monkeypatch.setattr(model_smoke, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(model_smoke, "ArcCompetitionClient", _must_not_construct)
    monkeypatch.setattr(
        sys,
        "argv",
        ["model_smoke.py", "--config", "ignored.yaml", "--game", "must-not-open"],
    )

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        model_smoke.main()


def test_grounding_smoke_rejects_frozen_treatment_before_fixture_or_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        grounding_smoke,
        "load_config",
        lambda _path: _qwen_path_deficit_config(),
    )
    monkeypatch.setattr(grounding_smoke, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prompt_grounding_smoke.py",
            "--fixture",
            "must-not-be-read.json",
            "--config",
            "ignored.yaml",
            "--model-path",
            "must-not-load",
            "--seed",
            "11",
            "--output",
            "must-not-write.json",
        ],
    )

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        grounding_smoke.main()


def test_kaggle_entrypoint_rejects_frozen_treatment_before_backend_or_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARC3_GAME_IDS", '["must-not-open"]')
    monkeypatch.setattr(
        kaggle_entrypoint,
        "load_config",
        lambda _path: _qwen_path_deficit_config(),
    )
    monkeypatch.setattr(kaggle_entrypoint, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(kaggle_entrypoint, "ArcCompetitionClient", _must_not_construct)

    with pytest.raises(TreatmentNotAdmittedError, match="failed its preregistered"):
        kaggle_entrypoint.main()
