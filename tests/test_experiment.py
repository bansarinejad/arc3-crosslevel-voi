from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from arc3_voi.experiment import (
    HyperparameterObservation,
    RunSpec,
    ScoreGateInput,
    build_confirmation_matrix,
    build_development_matrix,
    build_source_development_matrix,
    completed_run_ids,
    development_arms,
    evaluate_score_gate,
    load_matrix,
    select_eta_lambda,
    validate_matrix,
)

ROOT = Path(__file__).resolve().parents[1]


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
    assert development[0].arm_label == "D-Q"
    assert "-D-Q-qwen-" in development[0].run_id
    validate_matrix(development)


def test_template_development_matrix_freezes_explicit_arms_and_sources() -> None:
    labels = ("D-Q", "S-T", "M-T", "X-T")
    hashes = {
        label: character * 64
        for label, character in zip(labels, "abcd", strict=True)
    }
    versions = {f"g{i}": f"v{i}" for i in range(15)}

    matrix = build_source_development_matrix(
        tuple(f"g{i}" for i in range(15)),
        hypothesis_source="template_v1",
        model_profile="p",
        config_hashes=hashes,  # type: ignore[arg-type]
        game_versions=versions,
        snapshot_hash="e" * 64,
    )

    assert len(matrix) == 180
    assert {row.arm_label for row in matrix} == set(labels)
    assert {
        (row.arm_label, row.variant, row.hypothesis_source) for row in matrix
    } == {
        ("D-Q", "D", "qwen"),
        ("S-T", "S", "template_v1"),
        ("M-T", "M", "template_v1"),
        ("X-T", "X", "template_v1"),
    }
    assert all(row.identity_version == "source-v2" for row in matrix)
    assert all(f"-{row.arm_label}-{row.hypothesis_source}-" in row.run_id for row in matrix)
    validate_matrix(matrix)


def test_hybrid_source_is_typed_but_not_preregistered_as_an_arm_set() -> None:
    with pytest.raises(ValueError, match="not preregistered"):
        development_arms("qwen_then_template_v1")


def test_run_spec_rejects_inconsistent_arm_label() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        RunSpec(
            phase="development",
            game_id="g",
            seed=11,
            variant="M",
            model_profile="p",
            config_hash="a" * 64,
            hypothesis_source="template_v1",
            arm_label="M-Q",
        )


@pytest.mark.parametrize("missing", ["hypothesis_source", "arm_label", "identity_version"])
def test_run_spec_rejects_partial_source_identity(missing: str) -> None:
    row = {
        "phase": "development",
        "game_id": "g",
        "seed": 11,
        "variant": "M",
        "model_profile": "p",
        "config_hash": "a" * 64,
        "hypothesis_source": "template_v1",
        "arm_label": "M-T",
        "identity_version": "source-v2",
    }
    row.pop(missing)

    with pytest.raises(ValueError, match="incomplete source identity"):
        RunSpec.from_mapping(row)


def test_run_spec_rejects_null_arm_in_source_v2_mapping() -> None:
    with pytest.raises(ValueError, match="explicit arm_label"):
        RunSpec.from_mapping(
            {
                "phase": "development",
                "game_id": "g",
                "seed": 11,
                "variant": "M",
                "model_profile": "p",
                "config_hash": "a" * 64,
                "hypothesis_source": "template_v1",
                "arm_label": None,
                "identity_version": "source-v2",
            }
        )


def test_locked_qwen_matrix_loads_with_legacy_identity_and_run_ids() -> None:
    matrix = load_matrix("artifacts/development_matrix.json")

    assert len(matrix) == 180
    assert {row.identity_version for row in matrix} == {"legacy-v1"}
    assert {row.hypothesis_source for row in matrix} == {"qwen"}
    assert matrix[0].run_id == "development-bp35-0a0ad940-11-D-e56fe0e2"


def test_checked_in_source_manifests_match_the_frozen_registrations() -> None:
    locked = ROOT / "artifacts" / "development_matrix.json"
    registered = ROOT / "artifacts" / "development_matrix_template_v1.json"

    assert hashlib.sha256(locked.read_bytes()).hexdigest() == (
        "ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147"
    )
    assert hashlib.sha256(registered.read_bytes()).hexdigest() == (
        "6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b"
    )
    matrix = load_matrix(registered)
    assert len(matrix) == 180
    assert Counter(row.arm_label for row in matrix) == {
        "D-Q": 45,
        "S-T": 45,
        "M-T": 45,
        "X-T": 45,
    }
    assert {row.seed for row in matrix} == {11, 23, 47}
    assert len({row.full_game_id for row in matrix}) == 15


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


def test_matrix_rejects_distinct_full_hashes_with_same_run_id_prefix() -> None:
    matrix = build_development_matrix(
        ("g",),
        model_profile="p",
        config_hashes={
            "D": "12345678" + "a" * 56,
            "S": "12345678" + "b" * 56,
            "M": "c" * 64,
            "X": "d" * 64,
        },
        game_versions={"g": "v1"},
        snapshot_hash="b" * 64,
    )
    with pytest.raises(ValueError, match="eight-hex prefix"):
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
                "hypothesis_source": row.hypothesis_source,
                "arm_label": row.arm_label,
                "identity_version": row.identity_version,
                "producer_contract_sha256": "e" * 64,
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

    payload = json.loads((tmp_path / f"{row.run_id}.json").read_text())
    payload["hypothesis_source"] = "template_v1"
    (tmp_path / f"{row.run_id}.json").write_text(json.dumps(payload))
    assert completed_run_ids(matrix, tmp_path) == frozenset()


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
