from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.config import load_config
from arc3_voi.model import (
    ScriptedBackend,
    _count_generated_tokens,
    _cuda_memory_fraction,
    _history_grids,
    _multimodal_content,
    _sequence_token_counts,
    _validate_context_budget,
    backend_from_config,
)
from arc3_voi.provenance import inspect_model_artifact


def test_scripted_backend_is_deterministic() -> None:
    backend = ScriptedBackend(["program_a", "program_b"])
    result = backend.generate_programs([], 3)
    assert result.texts == ("program_a", "program_b", "program_a")
    assert result.tokens_per_second > 0


def test_scripted_direct_policy() -> None:
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION2"})
    action, result = backend.direct_action([], ["ACTION1", "ACTION2"])
    assert action == {"kind": "ACTION2"}
    assert result.output_tokens == 1


def test_count_generated_tokens_stops_at_eos_or_padding() -> None:
    generated = np.array([[10, 11, 2, 0, 0], [20, 21, 22, 0, 0]])

    assert _count_generated_tokens(generated, eos_token_id=2, pad_token_id=0) == 6


def test_sequence_token_counts_flag_only_unterminated_limit() -> None:
    generated = np.array([[10, 11, 2], [20, 21, 22]])

    assert _sequence_token_counts(
        generated, eos_token_id=2, pad_token_id=0, max_new_tokens=3
    ) == ((3, 3), (False, True))


def test_history_grids_preserve_the_latest_eight_in_order() -> None:
    grids = tuple(np.full((2, 2), index, dtype=np.int8) for index in range(10))

    canonical = _history_grids(SimpleNamespace(frames=grids))
    legacy = _history_grids([SimpleNamespace(grid=grid) for grid in grids])

    assert len(canonical) == len(legacy) == 8
    assert all(left is right for left, right in zip(canonical, grids[-8:], strict=True))
    assert all(left is right for left, right in zip(legacy, grids[-8:], strict=True))


def test_multimodal_content_matches_ordered_history_images(monkeypatch) -> None:
    grids = tuple(np.full((2, 2), index, dtype=np.int8) for index in range(8))
    monkeypatch.setattr("arc3_voi.model.render_grid_pil", lambda grid: grid)

    content = _multimodal_content(SimpleNamespace(frames=grids), "request")

    assert [item["type"] for item in content] == [*(["image"] * 8), "text"]
    assert all(
        content[index]["image"] is grid for index, grid in enumerate(grids)
    )
    assert content[-1] == {"type": "text", "text": "request"}


def test_context_budget_accepts_boundary_and_rejects_overflow() -> None:
    _validate_context_budget(14_848, 1_536, 16_384)
    with pytest.raises(RuntimeError, match="exceeds context budget"):
        _validate_context_budget(14_849, 1_536, 16_384)


def test_cuda_memory_fraction_enforces_explicit_gib_cap() -> None:
    total = 16 * 1024**3
    assert _cuda_memory_fraction(14.5, total) == pytest.approx(14.5 / 16)
    assert _cuda_memory_fraction(None, total) is None


def test_backend_rejects_unversioned_prompt_or_perception_contract() -> None:
    config = load_config("configs/local_4b.yaml")
    bad_prompt = replace(
        config,
        experiment=replace(config.experiment, prompt_contract_version="stale"),
    )
    with pytest.raises(ValueError, match="prompt contract"):
        backend_from_config(bad_prompt)
    bad_perception = replace(
        config,
        experiment=replace(config.experiment, perception_contract_version="stale"),
    )
    with pytest.raises(ValueError, match="perception contract"):
        backend_from_config(bad_perception)
    bad_prompt_hash = replace(
        config,
        experiment=replace(config.experiment, prompt_contract_sha256="0" * 64),
    )
    with pytest.raises(ValueError, match="prompt contract fingerprint"):
        backend_from_config(bad_prompt_hash)
    bad_perception_hash = replace(
        config,
        experiment=replace(config.experiment, perception_contract_sha256="0" * 64),
    )
    with pytest.raises(ValueError, match="perception contract fingerprint"):
        backend_from_config(bad_perception_hash)


def test_backend_enforces_frozen_local_model_identity(tmp_path) -> None:
    weight = tmp_path / "model.safetensors"
    weight.write_bytes(b"test-weights")
    metadata = tmp_path / ".cache" / "huggingface" / "download"
    metadata.mkdir(parents=True)
    (metadata / "model.safetensors.metadata").write_text(
        f"{'a' * 40}\n{'b' * 64}\n0\n",
        encoding="utf-8",
        newline="\n",
    )
    artifact = inspect_model_artifact(tmp_path)
    config = load_config("configs/local_4b.yaml")
    assert config.model is not None

    missing = replace(
        config,
        model=replace(
            config.model,
            expected_revision=None,
            expected_weight_manifest_sha256=None,
        ),
    )
    with pytest.raises(ValueError, match="must freeze revision"):
        backend_from_config(missing, model_path=tmp_path)
    with pytest.raises(ValueError, match="revision"):
        backend_from_config(config, model_path=tmp_path)

    matching = replace(
        config,
        model=replace(
            config.model,
            expected_revision=artifact.revision,
            expected_weight_manifest_sha256=artifact.weight_manifest_sha256,
        ),
    )
    backend = backend_from_config(matching, model_path=tmp_path)
    assert backend.profile.model_id == config.model.id
    backend.close()
