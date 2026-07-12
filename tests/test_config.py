from __future__ import annotations

from arc3_voi.config import load_config


def test_inherited_local_model_config_loads() -> None:
    config = load_config("configs/local_9b.yaml")
    assert config.experiment.max_environment_actions == 256
    assert config.model is not None
    assert config.model.id == "Qwen/Qwen3.5-9B"
    assert config.model.quantization == "nf4"


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


def test_local_4b_fallback_microbatches_the_logical_four_candidate_batch() -> None:
    config = load_config("configs/local_4b.yaml")

    assert config.model is not None
    assert config.model.max_batch_sequences == 1
