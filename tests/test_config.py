from __future__ import annotations

from arc3_voi.config import ExperimentConfig, load_config
from arc3_voi.prompts import PROMPT_CONTRACT_SHA256, PROMPT_CONTRACT_VERSION
from arc3_voi.rendering import PERCEPTION_CONTRACT_SHA256


def test_inherited_local_model_config_loads() -> None:
    config = load_config("configs/local_9b.yaml")
    assert config.experiment.max_environment_actions == 256
    assert (
        config.experiment.prompt_contract_version
        == "grounded-actions-palette-graded-goals-v3"
    )
    assert (
        config.experiment.perception_contract_version
        == "arc-agi-0.9.9-color-map-scale8-grid-v1"
    )
    assert config.experiment.prompt_contract_sha256 == PROMPT_CONTRACT_SHA256
    assert config.experiment.perception_contract_sha256 == PERCEPTION_CONTRACT_SHA256
    assert config.model is not None
    assert config.model.id == "Qwen/Qwen3.5-9B"
    assert config.model.quantization == "nf4"
    assert config.model.expected_revision == "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
    assert (
        config.model.expected_weight_manifest_sha256
        == "7d241f65e84063d41e959e31cbaf0ea50b7a0b43faf49f5ef3ff62d005c0f655"
    )


def test_bare_experiment_defaults_match_implemented_prompt_contract() -> None:
    config = ExperimentConfig()

    assert config.prompt_contract_version == PROMPT_CONTRACT_VERSION
    assert config.prompt_contract_sha256 == PROMPT_CONTRACT_SHA256


def test_kaggle_offline_fields_load() -> None:
    config = load_config("configs/kaggle_27b.yaml")
    assert config.model is not None
    assert config.model.offline
    assert config.model.max_runtime_fraction == 0.8


def test_kaggle_bf16_fallback_is_offline_and_unquantized() -> None:
    config = load_config("configs/kaggle_9b_bf16.yaml")

    assert config.model is not None
    assert config.model.id == "Qwen/Qwen3.5-9B"
    assert config.model.quantization == "none"
    assert config.model.compute_dtype == "bfloat16"
    assert config.model.offline
