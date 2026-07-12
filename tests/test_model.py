from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.model import (
    ScriptedBackend,
    _count_generated_tokens,
    _cuda_memory_fraction,
    _history_grids,
    _multimodal_content,
    _sequence_token_counts,
    _validate_context_budget,
)


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
