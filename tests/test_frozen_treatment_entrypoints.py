from __future__ import annotations

import sys
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import arc3_voi.config as config_module
import arc3_voi.model as model_module
import kaggle.entrypoint as kaggle_entrypoint
import scripts.model_smoke as model_smoke
import scripts.official_smoke as official_smoke
import scripts.offline_startup_smoke as offline_startup_smoke
import scripts.prompt_grounding_smoke as grounding_smoke
from arc3_voi.agent import TreatmentNotAdmittedError
from arc3_voi.config import HypothesisSource, load_config


def _qwen_path_deficit_config():
    template = load_config("configs/template_v1_path_deficit_v2_x.yaml")
    return replace(
        template,
        experiment=replace(template.experiment, hypothesis_source="qwen"),
    )


def _unadmitted_runtime_config(
    runtime_version: str,
    hypothesis_source: HypothesisSource,
):
    local = load_config("configs/local_4b.yaml")
    base = (
        replace(
            load_config("configs/template_v1_action_conditional_qbc_v1_x.yaml"),
            model=local.model,
        )
        if runtime_version == "crosslevel-voi-runtime-v5"
        else local
    )
    return replace(
        base,
        experiment=replace(
            base.experiment,
            variant="X",
            hypothesis_source=hypothesis_source,
            implementation_contract_version=runtime_version,
        ),
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


def test_model_smoke_passes_complete_source_identity_to_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_config("configs/local_4b.yaml")
    controller = object()
    captured: dict[str, object] = {}
    metrics = SimpleNamespace(
        total_actions=1,
        error=None,
        summary=lambda: {},
    )
    monkeypatch.setattr(model_smoke, "load_config", lambda _path: config)
    monkeypatch.setattr(model_smoke, "backend_from_config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        model_smoke,
        "ArcCompetitionClient",
        lambda: SimpleNamespace(make=lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(
        model_smoke,
        "build_agent",
        lambda *_args, **_kwargs: nullcontext(SimpleNamespace(controller=controller)),
    )

    def capture_run(_session: object, observed_controller: object, **kwargs: object):
        assert observed_controller is controller
        captured.update(kwargs)
        return metrics

    monkeypatch.setattr(model_smoke, "run_game", capture_run)
    monkeypatch.setattr(sys, "argv", ["model_smoke.py"])

    assert model_smoke.main() == 0
    assert captured["hypothesis_source"] == "qwen"
    assert captured["arm_label"] == "X-Q"
    assert captured["identity_version"] == "source-v2"
    assert isinstance(captured["producer_contract_sha256"], str)
    assert len(captured["producer_contract_sha256"]) == 64


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


@pytest.mark.parametrize(
    "runtime_version",
    ["crosslevel-voi-runtime-v5", "unregistered-runtime"],
)
@pytest.mark.parametrize(
    "hypothesis_source",
    ["qwen", "template_v1", "qwen_then_template_v1"],
)
def test_model_smoke_rejects_unlisted_runtime_before_backend_or_session(
    runtime_version: str,
    hypothesis_source: HypothesisSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _unadmitted_runtime_config(runtime_version, hypothesis_source)
    monkeypatch.setattr(model_smoke, "load_config", lambda _path: config)
    monkeypatch.setattr(model_smoke, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(model_smoke, "ArcCompetitionClient", _must_not_construct)
    monkeypatch.setattr(
        sys,
        "argv",
        ["model_smoke.py", "--config", "ignored.yaml", "--game", "must-not-open"],
    )

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        model_smoke.main()


@pytest.mark.parametrize(
    "runtime_version",
    ["crosslevel-voi-runtime-v5", "unregistered-runtime"],
)
@pytest.mark.parametrize(
    "hypothesis_source",
    ["qwen", "template_v1", "qwen_then_template_v1"],
)
def test_grounding_smoke_rejects_unlisted_runtime_before_fixture_backend_or_output(
    runtime_version: str,
    hypothesis_source: HypothesisSource,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _unadmitted_runtime_config(runtime_version, hypothesis_source)
    output = tmp_path / "must-not-write.json"
    monkeypatch.setattr(grounding_smoke, "load_config", lambda _path: config)
    monkeypatch.setattr(grounding_smoke, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prompt_grounding_smoke.py",
            "--fixture",
            str(tmp_path / "must-not-read.json"),
            "--config",
            "ignored.yaml",
            "--model-path",
            str(tmp_path / "must-not-load"),
            "--seed",
            "11",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        grounding_smoke.main()

    assert not output.exists()


@pytest.mark.parametrize(
    "runtime_version",
    ["crosslevel-voi-runtime-v5", "unregistered-runtime"],
)
@pytest.mark.parametrize(
    "hypothesis_source",
    ["qwen", "template_v1", "qwen_then_template_v1"],
)
def test_kaggle_entrypoint_rejects_unlisted_runtime_before_backend_client_or_output(
    runtime_version: str,
    hypothesis_source: HypothesisSource,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _unadmitted_runtime_config(runtime_version, hypothesis_source)
    output = tmp_path / "must-not-write"
    monkeypatch.setenv("ARC3_GAME_IDS", '["must-not-open"]')
    monkeypatch.setenv("ARC3_OUTPUT", str(output))
    monkeypatch.setattr(kaggle_entrypoint, "load_config", lambda _path: config)
    monkeypatch.setattr(kaggle_entrypoint, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(kaggle_entrypoint, "ArcCompetitionClient", _must_not_construct)

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        kaggle_entrypoint.main()

    assert not output.exists()


def test_official_smoke_rejects_before_scripted_backend_or_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _unadmitted_runtime_config("crosslevel-voi-runtime-v5", "template_v1")
    monkeypatch.setattr(official_smoke, "SystemConfig", lambda **_kwargs: config)
    monkeypatch.setattr(official_smoke, "ScriptedBackend", _must_not_construct)
    monkeypatch.setattr(official_smoke, "ArcCompetitionClient", _must_not_construct)

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        official_smoke.main()


def test_official_smoke_passes_complete_source_identity_to_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = object()
    captured: dict[str, object] = {}
    metrics = SimpleNamespace(total_actions=1, summary=lambda: {})
    monkeypatch.setattr(official_smoke, "ScriptedBackend", lambda **_kwargs: object())
    monkeypatch.setattr(
        official_smoke,
        "ArcCompetitionClient",
        lambda: SimpleNamespace(make=lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(
        official_smoke,
        "build_agent",
        lambda *_args, **_kwargs: nullcontext(SimpleNamespace(controller=controller)),
    )

    def capture_run(_session: object, observed_controller: object, **kwargs: object):
        assert observed_controller is controller
        captured.update(kwargs)
        return metrics

    monkeypatch.setattr(official_smoke, "run_game", capture_run)

    assert official_smoke.main() == 0
    assert captured["hypothesis_source"] == "qwen"
    assert captured["arm_label"] == "D-Q"
    assert captured["identity_version"] == "source-v2"
    assert isinstance(captured["producer_contract_sha256"], str)
    assert len(captured["producer_contract_sha256"]) == 64


def test_offline_startup_rejects_before_backend_or_entrypoint_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bundle"
    wheel = bundle / "code" / "project.whl"
    wheel.parent.mkdir(parents=True)
    wheel.touch()
    config = _unadmitted_runtime_config("crosslevel-voi-runtime-v5", "template_v1")
    assert config.model is not None
    config = replace(config, model=replace(config.model, offline=True))
    monkeypatch.setattr(
        offline_startup_smoke,
        "verify_manifest",
        lambda _bundle: {"provenance": {"selected_config": "config.yaml"}},
    )
    monkeypatch.setattr(offline_startup_smoke, "disable_python_network", lambda: None)
    monkeypatch.setattr(config_module, "load_config", lambda _path: config)
    monkeypatch.setattr(model_module, "backend_from_config", _must_not_construct)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    with pytest.raises(
        TreatmentNotAdmittedError,
        match="not in the exact live-contract allowlist",
    ):
        offline_startup_smoke.smoke(bundle, load_model_config=False)
