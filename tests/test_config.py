from __future__ import annotations

from dataclasses import replace

import pytest

from arc3_voi.candidates import CANDIDATE_POLICY_HASH, CANDIDATE_POLICY_VERSION
from arc3_voi.config import (
    ConfigError,
    ExperimentConfig,
    SystemConfig,
    config_from_mapping,
    load_config,
)
from arc3_voi.experiment import stable_config_hash
from arc3_voi.prompts import PROMPT_CONTRACT_SHA256, PROMPT_CONTRACT_VERSION
from arc3_voi.rendering import PERCEPTION_CONTRACT_SHA256
from arc3_voi.structured_templates import (
    STRUCTURED_PRIOR_CONTRACT_SHA256,
    STRUCTURED_PRIOR_CONTRACT_VERSION,
)


def test_inherited_local_model_config_loads() -> None:
    config = load_config("configs/local_9b.yaml")
    assert config.experiment.max_environment_actions == 256
    assert (
        config.experiment.prompt_contract_version == "evidence-first-visible-causal-alternatives-v5"
    )
    assert config.experiment.perception_contract_version == "arc-agi-0.9.9-color-map-scale8-grid-v1"
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

    assert config.implementation_contract_version == "crosslevel-voi-runtime-v3"
    assert config.prompt_contract_version == PROMPT_CONTRACT_VERSION
    assert config.prompt_contract_sha256 == PROMPT_CONTRACT_SHA256
    assert config.candidate_policy_version == CANDIDATE_POLICY_VERSION
    assert config.candidate_policy_sha256 == CANDIDATE_POLICY_HASH
    assert config.compiler_contract_version == STRUCTURED_PRIOR_CONTRACT_VERSION
    assert config.compiler_contract_sha256 == STRUCTURED_PRIOR_CONTRACT_SHA256


def test_implementation_contract_versions_change_the_config_hash() -> None:
    current = SystemConfig(experiment=ExperimentConfig())
    previous = SystemConfig(
        experiment=ExperimentConfig(implementation_contract_version="legacy-runtime")
    )

    assert stable_config_hash(current) != stable_config_hash(previous)


def test_candidate_and_compiler_contracts_are_validated_and_content_addressed() -> None:
    current = SystemConfig(experiment=ExperimentConfig())
    with pytest.raises(ConfigError, match="candidate policy identity"):
        ExperimentConfig(candidate_policy_sha256="0" * 64)
    with pytest.raises(ConfigError, match="compiler contract identity"):
        ExperimentConfig(compiler_contract_sha256="0" * 64)

    assert stable_config_hash(current) != stable_config_hash(
        {"experiment": {"implementation_contract_version": "crosslevel-voi-runtime-v3"}}
    )


def test_hypothesis_source_is_validated_and_content_addressed() -> None:
    qwen = SystemConfig(experiment=ExperimentConfig(hypothesis_source="qwen"))
    template = SystemConfig(experiment=ExperimentConfig(hypothesis_source="template_v1"))
    hybrid = SystemConfig(
        experiment=ExperimentConfig(hypothesis_source="qwen_then_template_v1")
    )

    assert len(
        {stable_config_hash(qwen), stable_config_hash(template), stable_config_hash(hybrid)}
    ) == 3
    with pytest.raises(ConfigError, match="hypothesis_source"):
        config_from_mapping({"experiment": {"hypothesis_source": "untracked"}})
    with pytest.raises(ConfigError, match="only for S, M, or X"):
        ExperimentConfig(variant="D", hypothesis_source="template_v1")
    with pytest.raises(ConfigError, match="only for M or X"):
        ExperimentConfig(variant="S", hypothesis_source="qwen_then_template_v1")


def test_legacy_qwen_projection_preserves_locked_matrix_hashes() -> None:
    config = load_config("configs/local_4b.yaml")
    d_config = replace(config, experiment=replace(config.experiment, variant="D"))

    assert stable_config_hash(d_config, implicit_qwen_legacy=True) == (
        "e56fe0e2a55e344edc53bd0d5f09c448305da3b07825c8d12798c935e51a68e6"
    )
    assert stable_config_hash(d_config) != stable_config_hash(
        d_config, implicit_qwen_legacy=True
    )
    with pytest.raises(ValueError, match="only Qwen"):
        stable_config_hash(
            replace(
                config,
                experiment=replace(config.experiment, hypothesis_source="template_v1"),
            ),
            implicit_qwen_legacy=True,
        )


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
