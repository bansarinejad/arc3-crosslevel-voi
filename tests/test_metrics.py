from __future__ import annotations

import pytest

from arc3_voi.metrics import game_rhae, level_rhae


def test_level_rhae_formula_and_cap() -> None:
    assert level_rhae(10, 20) == pytest.approx(0.25)
    assert level_rhae(20, 1) == pytest.approx(1.15)


def test_game_rhae_weights_later_levels_and_incomplete_as_zero() -> None:
    score = game_rhae([10, 10, 10], [10, 20], total_levels=3)
    assert score == pytest.approx((1 * 1.0 + 2 * 0.25) / 6)


def test_game_rhae_applies_official_completion_ceiling() -> None:
    assert game_rhae([20, 20, 20], [1], total_levels=3) == pytest.approx(1 / 6)
    assert game_rhae([20, 20], [1, 1], total_levels=2) == pytest.approx(1.0)
