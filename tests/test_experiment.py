from __future__ import annotations

import json

import pytest

from arc3_voi.experiment import (
    HyperparameterObservation,
    ScoreGateInput,
    build_confirmation_matrix,
    build_development_matrix,
    completed_run_ids,
    evaluate_score_gate,
    select_eta_lambda,
    validate_matrix,
)


def test_preregistered_matrix_sizes() -> None:
    hashes = {variant: character * 64 for variant, character in zip("DSMX", "abcd", strict=True)}
    versions = {f"g{i}": f"v{i}" for i in range(15)}
    development = build_development_matrix(
        tuple(f"g{i}" for i in range(15)),
        model_profile="p",
        config_hashes=hashes,
        game_versions=versions,
        snapshot_hash="a" * 64,
    )
    confirmation = build_confirmation_matrix(
        tuple(f"g{i}" for i in range(10)),
        comparator="M",
        model_profile="p",
        config_hashes=hashes,
        game_versions=versions,
        snapshot_hash="a" * 64,
    )
    assert len(development) == 180
    assert len(confirmation) == 100
    assert {run.config_hash for run in development if run.variant == "D"} == {"a" * 64}
    assert {run.config_hash for run in development if run.variant == "X"} == {"d" * 64}
    assert development[0].full_game_id == "g0-v0"
    validate_matrix(development)


def test_matrix_rejects_shared_variant_hash() -> None:
    matrix = build_development_matrix(
        ("g",),
        model_profile="p",
        config_hashes={variant: "a" * 64 for variant in "DSMX"},  # type: ignore[arg-type]
        game_versions={"g": "v1"},
        snapshot_hash="b" * 64,
    )
    with pytest.raises(ValueError, match="distinct"):
        validate_matrix(matrix)


def test_resume_requires_exact_clean_summary(tmp_path) -> None:
    matrix = build_confirmation_matrix(
        ("g",),
        comparator="M",
        model_profile="p",
        config_hashes={"M": "c" * 64, "X": "d" * 64},
        game_versions={"g": "v1"},
        snapshot_hash="b" * 64,
    )
    row = matrix[0]
    (tmp_path / f"{row.run_id}.json").write_text(
        json.dumps(
            {
                "run_id": row.run_id,
                "game_id": row.full_game_id,
                "seed": row.seed,
                "variant": row.variant,
                "model_profile": row.model_profile,
                "config_hash": row.config_hash,
                "error": None,
                "termination_reason": "win",
                "decision_points": 0,
                "total_actions": 0,
                "generated_tokens": 0,
                "direct_fallbacks": 0,
                "two_valid_decision_points": 0,
            }
        )
    )
    (tmp_path / f"{row.run_id}.jsonl").write_text("")
    assert completed_run_ids(matrix, tmp_path) == {row.run_id}


def test_eta_lambda_selection_uses_preregistered_tie_breaks() -> None:
    rows = []
    for eta in (2.0, 5.0, 10.0):
        for value in (0.0, 0.002, 0.01):
            rows.append(
                HyperparameterObservation(
                    "g", 11, eta, value, 0.5, 90 if eta == 5.0 else 100
                )
            )
    # Eta 5 wins the token tie-break; lambda 0 then wins the final declared tie-break.
    selected = select_eta_lambda(rows)
    assert (selected.eta, selected.complexity_lambda) == (5.0, 0.0)


def test_score_gate_passes_score_path() -> None:
    result = evaluate_score_gate(
        ScoreGateInput(0.11, 0.10, 3, 3, 20, 20, 0.7, 12.0, 10.0)
    )
    assert result.passed


def test_score_gate_fails_runtime() -> None:
    result = evaluate_score_gate(
        ScoreGateInput(0.11, 0.10, 3, 3, 20, 20, 0.7, 16.0, 10.0)
    )
    assert not result.passed
