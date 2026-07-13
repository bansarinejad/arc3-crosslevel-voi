from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from arc3_voi.config import load_config
from arc3_voi.program import ExecutableHypothesis, candidate_points_from_source
from arc3_voi.provenance import GitProvenance
from arc3_voi.runtime.sandbox import validate_program
from arc3_voi.runtime_admission import ADMISSION_CONTRACT_VERSION
from arc3_voi.structured_templates import (
    STRUCTURED_PRIOR_CONTRACT_SHA256,
    STRUCTURED_PRIOR_CONTRACT_VERSION,
    STRUCTURED_PRIOR_ROLES,
    instantiate_structured_priors,
    run_structured_prior_audit,
)
from arc3_voi.topology_compiler import TOPOLOGY_COMPILER_CODE_SHA256
from arc3_voi.types import Action, ActionKind, GameState, History, Observation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "grounding" / "bp35_seed11_initial_history.json"
CONFIG = ROOT / "configs" / "local_4b.yaml"


def _history(grid: np.ndarray) -> History:
    return History.from_observation(
        Observation(
            grid,
            frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
            GameState.NOT_FINISHED,
            level=1,
            win_levels=9,
        )
    )


def test_compiler_emits_four_restricted_scene_conditioned_sources() -> None:
    history = _history(
        np.array(
            [
                [8, 8, 8, 8, 8],
                [8, 2, 2, 6, 8],
                [8, 2, 8, 6, 8],
                [8, 4, 4, 6, 8],
                [8, 8, 8, 8, 8],
            ],
            dtype=np.int16,
        )
    )
    sources = instantiate_structured_priors(history)
    unrelated_sources = instantiate_structured_priors(_history(np.zeros((3, 7), dtype=np.int16)))

    assert len(sources) == 4
    assert (
        tuple(item.role for item in sources)
        == STRUCTURED_PRIOR_ROLES
        == (
            "conservative_evidence",
            "topology_contact",
            "homology_alignment",
            "symmetry_completion",
        )
    )
    assert len(STRUCTURED_PRIOR_CONTRACT_SHA256) == 64
    assert TOPOLOGY_COMPILER_CODE_SHA256 == (
        "e77e4db0ad743f5ed5f076f716806c342c4bf8c4a5953747dc332b7097ed299f"
    )
    assert STRUCTURED_PRIOR_CONTRACT_SHA256 == (
        "eeccd86db3346fd15d2e3dbc8e82ee2bb60e23bc30c0490750a7a0fbaa9e14e5"
    )
    assert len({item.source for item in sources}) == 4
    assert sources != unrelated_sources
    for item in sources:
        validated = validate_program(item.source)
        assert validated.node_count <= 4096
        assert candidate_points_from_source(item.source)
        assert dict(item.bindings)["component_count"] >= 1
        assert len(item.evidence) >= 6
        tree = ast.parse(item.source)
        assert not any(isinstance(node, ast.Import | ast.ImportFrom) for node in ast.walk(tree))
        assert "bp35" not in item.source.lower()


def test_structured_sources_preserve_simple_actions_and_existing_palette() -> None:
    grid = np.array(
        [
            [13, 13, 13, 13, 13],
            [13, 2, 2, 7, 13],
            [13, 2, 13, 7, 13],
            [13, 4, 4, 7, 13],
            [13, 13, 13, 13, 13],
        ],
        dtype=np.int16,
    )
    history = _history(grid)
    palette = set(int(value) for value in np.unique(grid))
    for item in instantiate_structured_priors(history):
        with ExecutableHypothesis(item.source) as hypothesis:
            simple = hypothesis.predict(history, Action(ActionKind.ACTION3))
            click = hypothesis.predict(
                history,
                Action(ActionKind.ACTION6, row=1, col=1),
            )
        np.testing.assert_array_equal(simple.next_grid, grid)
        assert set(int(value) for value in np.unique(click.next_grid)) <= palette
        assert simple.game_state is GameState.NOT_FINISHED
        assert click.game_state is GameState.NOT_FINISHED
        assert simple.level_delta == click.level_delta == 0


def test_clean_commit_guard_precedes_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "arc3_voi.structured_templates.inspect_git_provenance",
        lambda: GitProvenance("repo", "abc", True, "status", "diff"),
    )
    with pytest.raises(RuntimeError, match="clean committed worktree"):
        run_structured_prior_audit(
            FIXTURE,
            load_config(CONFIG),
            require_clean_commit=True,
        )


def test_frozen_fixture_runs_shared_runtime_admission_v2_without_writing_artifact() -> None:
    report = run_structured_prior_audit(
        FIXTURE,
        load_config(CONFIG),
        require_clean_commit=False,
    )

    assert report["contract_version"] == ADMISSION_CONTRACT_VERSION
    assert report["structured_prior_library"]["contract_version"] == (
        STRUCTURED_PRIOR_CONTRACT_VERSION
    )
    assert report["producer"]["compiler_contract_sha256"] == (STRUCTURED_PRIOR_CONTRACT_SHA256)
    assert report["structured_prior_library"]["source_count"] == 4
    assert report["producer"]["producer_kind"] == ("deterministic_scene_topology_compiler")
    assert report["producer"]["model_id"] is None
    assert report["producer"]["model_calls"] == 0
    assert report["producer"]["generated_tokens"] == 0
    assert report["producer"]["backbone_used"] is False
    assert len(report["programs"]) == 4
    assert all(report_row["instantiation_bindings"] for report_row in report["programs"])
    assert all(report_row["binding_evidence"] for report_row in report["programs"])
    graded = [
        row
        for row in report["programs"]
        if row["template_id"] != "conservative_evidence"
    ]
    assert sum(row["eligibility"]["eligible"] for row in graded) >= 2
    compiled_points = {
        tuple(point)
        for point in report["programs"][0]["instantiation_bindings"]["candidate_points"]
    }
    frontier_points = {
        (row["row"], row["col"])
        for row in report["inputs"]["candidate_set"]
        if row["kind"] == int(ActionKind.ACTION6)
    }
    assert compiled_points.intersection(frontier_points)
    assert report["contract"]["planning_depth"] == 4
    assert report["planning"]["cross_level_multiplier"] == pytest.approx(23.0)
    assert report["structured_prior_library"]["history_conditioning"].startswith(
        "bindings compiled"
    )
    assert report["structured_prior_library"]["empirical_transition_grounding_claimed"] is False
    assert all(row["recorded_transition_scoring_used"] is False for row in report["programs"])
    assert report["status"] in {"pilot_admitted", "pilot_blocked"}


def test_audit_rejects_tampered_canonical_history_digest(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["history_canonical_sha256"] = "0" * 64
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its declared digest"):
        run_structured_prior_audit(
            tampered,
            load_config(CONFIG),
            require_clean_commit=False,
        )
