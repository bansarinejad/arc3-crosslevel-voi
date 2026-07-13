from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from arc3_voi.config import load_config
from arc3_voi.program import ExecutableHypothesis, candidate_points_from_source
from arc3_voi.provenance import GitProvenance
from arc3_voi.runtime.sandbox import validate_program
from arc3_voi.runtime_admission import ADMISSION_CONTRACT_VERSION
from arc3_voi.structured_templates import (
    SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256,
    SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION,
    STRUCTURED_PRIOR_CONTRACT_SHA256,
    STRUCTURED_PRIOR_CONTRACT_VERSION,
    STRUCTURED_PRIOR_ROLES,
    _scene_admission_overlay_reasons,
    instantiate_structured_priors,
    run_scene_topology_admission_audit,
)
from arc3_voi.topology_compiler import TOPOLOGY_COMPILER_CODE_SHA256
from arc3_voi.types import Action, ActionKind, GameState, History, Observation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "grounding" / "bp35_seed11_initial_history.json"
CONFIG = ROOT / "configs" / "template_v1_x.yaml"


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
        run_scene_topology_admission_audit(
            FIXTURE,
            load_config(CONFIG),
            config_path=CONFIG,
            require_clean_commit=True,
        )


def test_frozen_fixture_runs_shared_runtime_admission_v2_without_writing_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arc3_voi.structured_templates.inspect_git_provenance",
        lambda: GitProvenance(
            ROOT.as_posix(),
            "a" * 40,
            False,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
    )
    report = run_scene_topology_admission_audit(
        FIXTURE,
        load_config(CONFIG),
        config_path=CONFIG,
        require_clean_commit=False,
    )

    assert report["schema_version"] == 2
    assert report["contract_version"] == ADMISSION_CONTRACT_VERSION
    assert report["admission_overlay_version"] == (
        SCENE_TOPOLOGY_ADMISSION_OVERLAY_VERSION
    )
    assert SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256 == (
        "2992fa00f5e688bba4cef6f5be4f101528c25896d0bb74a28346fb1685822a12"
    )
    assert report["admission_overlay_sha256"] == (
        SCENE_TOPOLOGY_ADMISSION_OVERLAY_SHA256
    )
    assert report["scene_topology_compiler"]["contract_version"] == (
        STRUCTURED_PRIOR_CONTRACT_VERSION
    )
    assert report["producer"]["compiler_contract_sha256"] == (STRUCTURED_PRIOR_CONTRACT_SHA256)
    assert report["scene_topology_compiler"]["source_count"] == 4
    assert report["producer"]["producer_kind"] == ("deterministic_scene_topology_compiler")
    assert report["producer"]["model_id"] is None
    assert report["producer"]["model_calls"] == 0
    assert report["producer"]["generated_tokens"] == 0
    assert report["producer"]["backbone_used"] is False
    assert len(report["programs"]) == 4
    selected_ids = set(report["selection"]["selected_ids"])
    selected_memory = report["selection"]["selected_worker_memory"]
    assert {row["hypothesis_id"] for row in selected_memory} == selected_ids
    assert len(selected_memory) == len(selected_ids)
    assert all("grounding_worker_memory" in row for row in report["programs"])
    assert all(report_row["instantiation_bindings"] for report_row in report["programs"])
    assert all(report_row["binding_evidence"] for report_row in report["programs"])
    graded = [
        row
        for row in report["programs"]
        if row["compiler_role"] != "conservative_evidence"
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
    assert report["contract"]["minimum_eligible_graded_roles"] == 2
    assert report["planning"]["cross_level_multiplier"] == pytest.approx(23.0)
    assert report["inputs"]["hypothesis_source"] == "template_v1"
    assert report["inputs"]["controller_variant"] == "X"
    assert report["inputs"]["arm_label"] == "X-T"
    assert report["inputs"]["config_sha256"] == (
        "aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708"
    )
    assert "repository_root" not in report["git"]
    assert "instantiation_wall_seconds" not in report["producer"]
    assert report["scene_topology_compiler"]["history_conditioning"].startswith(
        "bindings compiled"
    )
    assert report["scene_topology_compiler"]["empirical_transition_grounding_claimed"] is False
    assert all(row["recorded_transition_scoring_used"] is False for row in report["programs"])
    assert report["status"] == "pilot_blocked"
    assert report["gate"]["passes"] is False

    repeated = run_scene_topology_admission_audit(
        FIXTURE,
        load_config(CONFIG),
        config_path=CONFIG,
        require_clean_commit=False,
    )
    assert repeated == report


def test_audit_rejects_tampered_canonical_history_digest(tmp_path: Path) -> None:
    alternate = tmp_path / "alternate.json"
    alternate.write_bytes(FIXTURE.read_bytes())

    with pytest.raises(ValueError, match="inside the repository"):
        run_scene_topology_admission_audit(
            alternate,
            load_config(CONFIG),
            config_path=CONFIG,
            require_clean_commit=False,
        )


def test_admission_rejects_qwen_labeled_config() -> None:
    qwen_config = ROOT / "configs" / "local_4b.yaml"
    with pytest.raises(ValueError, match="hypothesis_source=template_v1"):
        run_scene_topology_admission_audit(
            FIXTURE,
            load_config(qwen_config),
            config_path=qwen_config,
            require_clean_commit=False,
        )


def test_admission_rejects_altered_template_x_semantics() -> None:
    config = load_config(CONFIG)
    altered = replace(config, planning=replace(config.planning, depth=3))

    with pytest.raises(ValueError, match="does not match registered X-T"):
        run_scene_topology_admission_audit(
            FIXTURE,
            altered,
            config_path=CONFIG,
            require_clean_commit=False,
        )


def test_scene_overlay_fails_closed_on_roles_and_selected_worker_memory() -> None:
    reports = [
        {"candidate_index": 0, "assigned_role": "conservative", "eligibility": {"eligible": True}},
        {"candidate_index": 1, "assigned_role": "graded-a", "eligibility": {"eligible": True}},
    ]
    reasons, roles = _scene_admission_overlay_reasons(
        reports,
        selected_ids=("a", "b"),
        selected_memory=(
            {
                "hypothesis_id": "a",
                "hard_limit_enforced": True,
                "limit_kind": "wrong",
                "allocation_headroom_bytes": 256 * 1024 * 1024,
            },
        ),
        expected_headroom_bytes=256 * 1024 * 1024,
        require_linux_memory=True,
        execution_platform="linux",
    )

    assert roles == ["graded-a"]
    assert "fewer than two graded compiler roles are eligible" in reasons
    assert "selected worker memory evidence is incomplete or misaligned" in reasons
    assert "selected programs did not verify the exact hard allocation headroom" in reasons


def test_scene_overlay_accepts_exact_linux_persistent_worker_evidence() -> None:
    reports = [
        {"candidate_index": 1, "assigned_role": "graded-a", "eligibility": {"eligible": True}},
        {"candidate_index": 2, "assigned_role": "graded-b", "eligibility": {"eligible": True}},
    ]
    headroom = 256 * 1024 * 1024
    memory = tuple(
        {
            "hypothesis_id": identifier,
            "hard_limit_enforced": True,
            "limit_kind": "rlimit_data_baseline_plus_budget",
            "allocation_headroom_bytes": headroom,
        }
        for identifier in ("a", "b")
    )

    reasons, roles = _scene_admission_overlay_reasons(
        reports,
        selected_ids=("a", "b"),
        selected_memory=memory,
        expected_headroom_bytes=headroom,
        require_linux_memory=True,
        execution_platform="linux",
    )

    assert reasons == []
    assert roles == ["graded-a", "graded-b"]
