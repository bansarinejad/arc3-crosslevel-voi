from __future__ import annotations

from dataclasses import replace

import pytest

from arc3_voi.candidates import CANDIDATE_POLICY_HASH, CANDIDATE_POLICY_VERSION
from arc3_voi.config import (
    PATH_DEFICIT_RUNTIME_VERSION,
    ConfigError,
    ExperimentConfig,
    PlanningConfig,
    SystemConfig,
    config_from_mapping,
    load_config,
)
from arc3_voi.experiment import stable_config_hash
from arc3_voi.planner import (
    COMPLETION_COST_POLICY_HASHES,
    ENDPOINT_COMPLETION_COST_POLICY,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
)
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


def test_runtime_v4_cross_validates_serialized_path_deficit_identity() -> None:
    path_planning = PlanningConfig(
        completion_cost_policy_version=PATH_DEFICIT_COMPLETION_COST_POLICY,
        completion_cost_policy_sha256=COMPLETION_COST_POLICY_HASHES[
            PATH_DEFICIT_COMPLETION_COST_POLICY
        ],
    )
    config = SystemConfig(
        experiment=ExperimentConfig(
            implementation_contract_version=PATH_DEFICIT_RUNTIME_VERSION
        ),
        planning=path_planning,
    )

    assert config.planning.completion_cost_policy_version == (
        PATH_DEFICIT_COMPLETION_COST_POLICY
    )
    with pytest.raises(ConfigError, match="does not match the implementation contract"):
        SystemConfig(
            experiment=ExperimentConfig(
                implementation_contract_version=PATH_DEFICIT_RUNTIME_VERSION
            )
        )
    with pytest.raises(ConfigError, match="does not match the implementation contract"):
        SystemConfig(planning=path_planning)
    with pytest.raises(ConfigError, match="policy identity"):
        PlanningConfig(completion_cost_policy_sha256="0" * 64)


def test_completion_cost_policy_hashes_are_frozen_content_identities() -> None:
    assert COMPLETION_COST_POLICY_HASHES == {
        ENDPOINT_COMPLETION_COST_POLICY: (
            "c12daf008d7ee6792b3ade429dacb8a65a108b9d5eb8ea8d1f5e78552dd2e95a"
        ),
        PATH_DEFICIT_COMPLETION_COST_POLICY: (
            "055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670"
        ),
    }


def test_v3_source_and_legacy_config_hashes_remain_byte_stable() -> None:
    config = load_config("configs/local_4b.yaml")
    source_hashes = {
        "D-Q": "18f6efe5ce4feab4b42ac67b917f4cb84c2ea9be603d4321d86bb00c230b1ee7",
        "S-Q": "a27b4a2bebd7a835d12f7ac8138f9cd04c10ee86c05df5a923423cab79e637ef",
        "M-Q": "d46dc6ce1b457a5d4ffeb3b9a5f99fdd6f17791ae23b0a848ad6a154c7dce3de",
        "X-Q": "9d099ba9c606e93fc44e9ee4801390bb0ca5e7496c03e76a2873e5606463455e",
        "S-T": "d41c6e726ffa2716d278e18ebfb2d14dabbc466ec63543612c297de85a10f3c7",
        "M-T": "79ad8a0332109f9e87fe095cf8eb47c35f588fdc3fa4d972520c8053fd2a2530",
        "X-T": "aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708",
    }
    legacy_hashes = {
        "D": "e56fe0e2a55e344edc53bd0d5f09c448305da3b07825c8d12798c935e51a68e6",
        "S": "e254bbf925180ac197696913250cbbbab1b454a3f163391b470912e270bb0ded",
        "M": "bd35d59f73baa0fe09d3e00aa6d4541c05505135da620fbe2556ccf1533bf13f",
        "X": "6e84fd03aea5012a8360410dc9386913d7767dd71377c2d5bdde6e374aa79c0e",
    }

    actual_source = {
        f"{variant}-Q": stable_config_hash(
            replace(
                config,
                experiment=replace(
                    config.experiment,
                    variant=variant,
                    hypothesis_source="qwen",
                ),
            )
        )
        for variant in "DSMX"
    }
    actual_source.update(
        {
            f"{variant}-T": stable_config_hash(
                replace(
                    config,
                    experiment=replace(
                        config.experiment,
                        variant=variant,
                        hypothesis_source="template_v1",
                    ),
                )
            )
            for variant in "SMX"
        }
    )
    actual_legacy = {
        variant: stable_config_hash(
            replace(
                config,
                experiment=replace(config.experiment, variant=variant),
            ),
            implicit_qwen_legacy=True,
        )
        for variant in "DSMX"
    }

    assert actual_source == source_hashes
    assert actual_legacy == legacy_hashes


def test_historical_hash_projection_rejects_invalid_explicit_policy_identity() -> None:
    endpoint_sha = COMPLETION_COST_POLICY_HASHES[ENDPOINT_COMPLETION_COST_POLICY]
    valid = {
        "experiment": {"implementation_contract_version": "crosslevel-voi-runtime-v3"},
        "planning": {
            "completion_cost_policy_version": ENDPOINT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": endpoint_sha,
        },
    }
    stripped = {
        "experiment": {"implementation_contract_version": "crosslevel-voi-runtime-v3"},
        "planning": {},
    }
    assert stable_config_hash(valid) == stable_config_hash(stripped)
    assert stable_config_hash(valid, implicit_qwen_legacy=True) == stable_config_hash(
        stripped, implicit_qwen_legacy=True
    )

    invalid_rows = (
        {
            "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
                PATH_DEFICIT_COMPLETION_COST_POLICY
            ],
        },
        {
            "completion_cost_policy_version": ENDPOINT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": "0" * 64,
        },
        {"completion_cost_policy_version": ENDPOINT_COMPLETION_COST_POLICY},
    )
    for planning in invalid_rows:
        mapping = {
            "experiment": {
                "implementation_contract_version": "crosslevel-voi-runtime-v3"
            },
            "planning": planning,
        }
        with pytest.raises(ValueError, match="historical completion-cost policy"):
            stable_config_hash(mapping)
        with pytest.raises(ValueError, match="historical completion-cost policy"):
            stable_config_hash(mapping, implicit_qwen_legacy=True)


def test_runtime_v4_hash_retains_serialized_policy_identity() -> None:
    base = {
        "experiment": {"implementation_contract_version": PATH_DEFICIT_RUNTIME_VERSION},
        "planning": {
            "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
            "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
                PATH_DEFICIT_COMPLETION_COST_POLICY
            ],
        },
    }
    changed = {
        **base,
        "planning": {**base["planning"], "completion_cost_policy_sha256": "0" * 64},
    }

    assert stable_config_hash(base) != stable_config_hash(changed)


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
