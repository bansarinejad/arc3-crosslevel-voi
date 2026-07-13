from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "template_v1_runtime_admission_v2_bp35_seed11.json"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _report() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_canonical_scene_topology_admission_artifact_is_frozen_negative_evidence() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == (
        "546cf508fa36e1d0ddd39b16e79c35f79fc597577609b3350add8f1c146e1033"
    )
    report = _report()

    assert report["schema_version"] == 2
    assert report["contract_version"] == "runtime-admission-v2"
    assert report["admission_overlay_version"] == "scene-topology-admission-v1"
    assert report["offline"] is True
    assert report["planner_error"] is None
    assert report["status"] == "pilot_blocked"
    assert report["gate"] == {
        "passes": False,
        "reasons": [
            "no X-only probe opportunity: require one action with low committee "
            "agreement, material EVSI, positive cross-level utility, and "
            "non-positive myopic utility"
        ],
    }

    assert report["git"] == {
        "commit": "46bf052cd9254a8837f27db9119ffdc34c46cb65",
        "dirty": False,
        "status_sha256": EMPTY_SHA256,
        "tracked_diff_sha256": EMPTY_SHA256,
    }
    inputs = report["inputs"]
    assert (inputs["hypothesis_source"], inputs["controller_variant"], inputs["arm_label"]) == (
        "template_v1",
        "X",
        "X-T",
    )
    assert inputs["config_sha256"] == (
        "aa33d464cc7cae07607689e351bcbc9aadba61c9990d5150441dc5f31e367708"
    )
    assert inputs["registered_matrix_sha256"] == (
        "6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b"
    )
    assert inputs["fixture_sha256"] == (
        "ecb67dbe088efcc79c7b786447bf81796a42a08417d64972042571d128258d75"
    )
    assert inputs["history_canonical_sha256"] == (
        "de73a63399b6618b7a127d69f2ea75c1b83cea4f597c1993a0267e1da17c3fb4"
    )
    assert inputs["candidate_policy_sha256"] == (
        "a9220009c5fd4b6da602580db439e25f9acaef74799de050a7a56e6c64bba82c"
    )
    assert inputs["candidate_set_sha256"] == (
        "27015da2bc051f4761c4f9d6764ace0520a9778719b40c74fe9cf498e5f8ed72"
    )
    assert report["admission_overlay_sha256"] == (
        "2992fa00f5e688bba4cef6f5be4f101528c25896d0bb74a28346fb1685822a12"
    )

    producer = report["producer"]
    assert producer["compiler_contract_sha256"] == (
        "eeccd86db3346fd15d2e3dbc8e82ee2bb60e23bc30c0490750a7a0fbaa9e14e5"
    )
    assert producer["producer_contract_sha256"] == (
        "9045ea2b450bc4d7c129e03b745afa5898c129d6d44739597012f24f32302b42"
    )
    assert producer["model_id"] is None
    assert producer["model_calls"] == producer["generated_tokens"] == 0
    assert producer["proposal_batches_charged"] == 0
    assert producer["backbone_used"] is False


def test_canonical_scene_topology_admission_passes_structure_but_not_decision_gate() -> None:
    report = _report()
    selection = report["selection"]
    programs = report["programs"]
    selected_ids = selection["selected_ids"]

    assert len(programs) == len(selected_ids) == len(selection["eligible_ids"]) == 4
    assert selected_ids == selection["eligible_ids"]
    assert selection["distinct_selected_behavior_classes"] == 4
    assert selection["behavioral_deduplicated_ids"] == []
    assert selection["ineligible_ids"] == selection["ineligible_selected_ids"] == []
    assert selection["filter_precedes_persistent_worker_construction"] is True
    assert [program["compiler_role"] for program in programs] == [
        "conservative_evidence",
        "topology_contact",
        "homology_alignment",
        "symmetry_completion",
    ]
    assert all(program["eligibility"]["eligible"] for program in programs)
    assert all(program["eligibility"]["sandbox_valid"] for program in programs)
    assert all(program["eligibility"]["all_actions_ok"] for program in programs)
    assert all(program["eligibility"]["goal_value_ok"] for program in programs)
    assert all(program["eligibility"]["palette_conflicts"] == 0 for program in programs)
    graded = programs[1:]
    assert all(program["eligibility"]["action_sensitive"] for program in graded)
    assert all(program["eligibility"]["goal_action_conditioned"] for program in graded)

    memory = selection["selected_worker_memory"]
    assert [row["hypothesis_id"] for row in memory] == selected_ids
    assert all(row["hard_limit_enforced"] is True for row in memory)
    assert all(row["limit_kind"] == "rlimit_data_baseline_plus_budget" for row in memory)
    assert all(row["allocation_headroom_bytes"] == 268_435_456 for row in memory)
    assert all(row["diagnostic"] is None for row in memory)

    planning = report["planning"]
    assert planning["invalid_hypothesis_ids"] == []
    assert planning["agreement"] == planning["indifference"] == 1.0
    assert planning["differing_optimal_sets"] is False
    assert planning["maximum_evsi"] == 0.0
    assert planning["maximum_myopic_utility"] == -1.0
    assert planning["maximum_cross_level_utility"] == -1.0
    assert planning["cross_level_multiplier"] == 23.0
    assert planning["x_only_probe_actions"] == []
    assert all(
        not row["action_varying"] and row["range"] == 0.0
        for row in planning["per_hypothesis_cost_variation"].values()
    )
