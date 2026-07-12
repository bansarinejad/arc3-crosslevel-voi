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
    STRUCTURED_PRIOR_CONTRACT_VERSION,
    instantiate_structured_priors,
    run_structured_prior_audit,
)
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


def test_library_emits_exactly_four_restricted_history_invariant_sources() -> None:
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
    unrelated_sources = instantiate_structured_priors(
        _history(np.zeros((3, 7), dtype=np.int16))
    )

    assert len(sources) == 4
    assert [item.role for item in sources] == [
        "conservative_no_effect",
        "local_action6_contact",
        "action6_component_selection",
        "action6_component_state",
    ]
    assert len({item.source for item in sources}) == 4
    assert sources == unrelated_sources
    for item in sources:
        validated = validate_program(item.source)
        assert validated.node_count <= 4096
        assert candidate_points_from_source(item.source) == ()
        tree = ast.parse(item.source)
        assert not any(
            isinstance(node, ast.Import | ast.ImportFrom) for node in ast.walk(tree)
        )
        assert '"WIN"' not in item.source
        assert '"GAME_OVER"' not in item.source
        assert '"level_delta": 0' in item.source


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
    assert report["structured_prior_library"]["source_count"] == 4
    assert report["producer"]["producer_kind"] == (
        "deterministic_structured_prior_library"
    )
    assert report["producer"]["model_id"] is None
    assert report["producer"]["model_calls"] == 0
    assert report["producer"]["generated_tokens"] == 0
    assert report["producer"]["backbone_used"] is False
    assert len(report["programs"]) == 4
    assert report["contract"]["planning_depth"] == 4
    assert report["planning"]["cross_level_multiplier"] == pytest.approx(23.0)
    assert len(report["selection"]["eligible_ids"]) == 4
    assert len(report["selection"]["selected_ids"]) == 4
    assert report["selection"]["distinct_selected_behavior_classes"] == 4
    assert report["planning"]["agreement"] >= 0.8
    assert report["planning"]["maximum_evsi"] < 0.05
    assert report["planning"]["x_only_probe_actions"] == []
    assert report["status"] == "pilot_blocked"
    assert report["gate"] == {
        "passes": False,
        "reasons": [
            "no X-only probe opportunity: require one action with low committee "
            "agreement, material EVSI, positive cross-level utility, and non-positive "
            "myopic utility"
        ],
    }


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
