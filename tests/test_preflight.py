from __future__ import annotations

import pytest

from arc3_voi.model import ScriptedBackend
from arc3_voi.preflight import empirical_quantile, run_model_preflight


def test_runtime_projection_enforces_twenty_percent_headroom() -> None:
    backend = ScriptedBackend(["def predict(): pass"])
    report = run_model_preflight(
        backend,
        model_id="test",
        min_tokens_per_second=0,
        observed_game_seconds=[1, 2, 3],
        hidden_game_count=10,
        runtime_limit_seconds=40,
    )
    assert report.projected_p95_seconds == pytest.approx(29)
    assert report.passes_runtime_gate
    assert report.statically_valid_programs == 0
    assert report.validation_failures["invalid_contract"] >= 1


def test_empirical_quantile_validation() -> None:
    with pytest.raises(ValueError):
        empirical_quantile([], 0.95)
