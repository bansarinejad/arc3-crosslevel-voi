from __future__ import annotations

from arc3_voi.config import ExperimentConfig, SystemConfig, load_config
from arc3_voi.experiment import stable_config_hash
from arc3_voi.prompts import PROMPT_CONTRACT_SHA256, PROMPT_CONTRACT_VERSION
from arc3_voi.rendering import PERCEPTION_CONTRACT_SHA256


def test_inherited_local_model_config_loads() -> None:
    config = load_config("configs/local_9b.yaml")
    assert config.experiment.max_environment_actions == 256
    assert (
        config.experiment.prompt_contract_version
        == "evidence-first-visible-causal-alternatives-v4"
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

    assert config.implementation_contract_version == "crosslevel-voi-runtime-v1"
    assert config.prompt_contract_version == PROMPT_CONTRACT_VERSION
    assert config.prompt_contract_sha256 == PROMPT_CONTRACT_SHA256


def test_implementation_contract_versions_change_the_config_hash() -> None:
    current = SystemConfig(experiment=ExperimentConfig())
    previous = SystemConfig(
        experiment=ExperimentConfig(implementation_contract_version="legacy-runtime")
    )

    assert stable_config_hash(current) != stable_config_hash(previous)


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
