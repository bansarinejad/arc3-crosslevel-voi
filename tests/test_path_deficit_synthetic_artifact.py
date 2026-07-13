from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "template_v1_path_deficit_v2_synthetic_admission.json"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _report() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_path_deficit_synthetic_artifact_has_exact_clean_linux_provenance() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == (
        "0a81a4a9d42bba1a80b747838bb51d06fae86827909c792d2afe5a2d14aa880a"
    )
    report = _report()

    assert report["schema_version"] == 1
    assert report["contract_version"] == "path-deficit-synthetic-admission-v1"
    assert report["contract_sha256"] == (
        "d01f34cc2835a4a8b7f7257a6fc65e67c455d158356c69db744a6c50203b30ed"
    )
    assert report["status"] == "synthetic_blocked"
    assert report["offline"] is True
    assert report["git"] == {
        "commit": "989c3211044b7d004e43f7a84f8a4b77567568da",
        "dirty": False,
        "status_sha256": EMPTY_SHA256,
        "tracked_diff_sha256": EMPTY_SHA256,
    }
    assert report["execution"] == {
        "platform": "linux",
        "require_clean_commit": True,
        "require_linux": True,
    }

    registration = report["registration"]
    assert registration["amendment_sha256"] == (
        "72522d43c2069f58cc2478401c02602cfe3db557496268e1aad19bdbf9f5a0b7"
    )
    assert registration["config_file_sha256"] == (
        "26b02a26a7152597eb40164a3775e23f38750ea7891af9fa20b4c327af7cb090"
    )
    assert registration["config_sha256"] == (
        "de53f3dffe049ffa3a62eb49622c34f1233a0f86baf6622b42f006b9b1c1982a"
    )
    assert registration["matrix_sha256"] == (
        "949fe7a7455e3637acdeb2ec278ff9822e78a15284854fd730e47a3c84775d5e"
    )
    assert registration["matrix_rows"] == 180
    assert registration["prior_run_id_collisions"] == {"qwen": 0, "template_v1": 0}

    treatment = report["treatment"]
    assert treatment["pre_amendment_head_commit"] == (
        "9805e9e04f0e9d1a1fb7b6f0704697b1022bb736"
    )
    assert treatment["preregistration_commit"] == (
        "1302a05750f75d813fd3f84df13f0025e8050d9e"
    )
    assert treatment["preregistration_sha256"] == (
        "a253ef9e432e1fa59363a007c7dd00f7cdcc9507747b6096c94aa697961265e3"
    )
    assert treatment["historical_completion_cost_policy_sha256"] == (
        "c12daf008d7ee6792b3ade429dacb8a65a108b9d5eb8ea8d1f5e78552dd2e95a"
    )
    assert treatment["completion_cost_policy_sha256"] == (
        "055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670"
    )
    assert treatment["canonical_bp35_audit_authorized"] is False
    assert treatment["gameplay_authorized"] is False
    assert treatment["development_matrix_execution_authorized"] is False
    assert report["resource_usage"] == {
        "model_id": None,
        "model_calls": 0,
        "generated_tokens": 0,
        "gpu_used": False,
        "environment_actions": 0,
        "reward_observations": 0,
        "rhae_observations": 0,
    }


def test_path_deficit_synthetic_artifact_is_infrastructure_clean_but_gate_blocked() -> None:
    report = _report()
    assert report["planner_error"] is None
    assert report["infrastructure_gate"] == {
        "passes": True,
        "reasons": [],
        "require_linux_memory": True,
        "expected_limit_kind": "rlimit_data_baseline_plus_budget",
        "expected_allocation_headroom_bytes": 268_435_456,
        "grounding_workers_checked": 4,
        "persistent_workers_checked": 4,
        "resource_counters_checked": True,
    }
    assert len(report["programs"]) == 4
    for program in report["programs"]:
        assert program["eligibility"]["eligible"] is True
        assert program["eligibility"]["all_actions_ok"] is True
        assert program["eligibility"]["goal_value_ok"] is True
        assert program["grounding_worker_memory"] == {
            "hard_limit_enforced": True,
            "limit_kind": "rlimit_data_baseline_plus_budget",
            "allocation_headroom_bytes": 268_435_456,
            "diagnostic": None,
        }
    selected = report["selection"]
    assert len(selected["selected_ids"]) == 4
    assert selected["selected_ids"] == selected["eligible_ids"]
    assert selected["distinct_selected_behavior_classes"] == 4
    assert selected["behavioral_deduplicated_ids"] == []
    for worker in selected["selected_worker_memory"]:
        assert worker["hard_limit_enforced"] is True
        assert worker["limit_kind"] == "rlimit_data_baseline_plus_budget"
        assert worker["allocation_headroom_bytes"] == 268_435_456
        assert worker["diagnostic"] is None

    planning = report["planning"]
    assert planning["invalid_hypothesis_ids"] == []
    assert planning["differing_optimal_sets"] is True
    assert planning["weights"] == pytest.approx(
        (
            0.4116174747472121,
            0.22410046565918698,
            0.20604497263252872,
            0.1582370869610722,
        )
    )
    assert planning["agreement"] == pytest.approx(0.8417629130389278)
    assert planning["maximum_evsi"] == pytest.approx(0.048123650158264475)
    assert planning["maximum_myopic_utility"] == pytest.approx(-0.9518763498417355)
    assert planning["maximum_cross_level_utility"] == pytest.approx(0.10684395364008292)
    assert planning["x_only_probe_actions"] == []
    assert sum(
        row["action_varying"]
        for row in planning["per_hypothesis_cost_variation"].values()
    ) == 3
    assert report["runtime_admission_gate"]["passes"] is False
    assert report["acceptance_gate"] == {
        "passes": False,
        "reasons": [
            "committee agreement was not below 0.8",
            "maximum EVSI was below 0.05 actions",
            "no X-only action survived the unchanged admission rule",
        ],
        "requirements": {
            "valid_programs": 4,
            "distinct_selected_programs": 4,
            "minimum_graded_action_varying_programs": 2,
            "agreement_strictly_below": 0.8,
            "maximum_evsi_at_least_actions": 0.05,
            "minimum_x_only_actions": 1,
        },
        "observed": {
            "valid_programs": 4,
            "selected_programs": 4,
            "distinct_selected_programs": 4,
            "graded_action_varying_programs": 3,
            "weights": planning["weights"],
            "agreement": planning["agreement"],
            "maximum_evsi_actions": planning["maximum_evsi"],
            "x_only_probe_actions": [],
        },
    }

    scene = report["synthetic_scene"]
    assert scene["payload_sha256"] == (
        "dfa612dbc1215319d3d2de1b8b41c9462a9dcd822ccd3b9793c0e358d216383b"
    )
    assert scene["candidate_set_sha256"] == (
        "86e6f48fbe0056f0913b08c1daa1d54fc3147f163e1aece8177d50c02e6a6a69"
    )
    assert scene["source_manifest_sha256"] == (
        "7834f5a116c3d2e6e3b5725d9c17d982d76f8f947ebd6bc2d1ca9f405053d9d4"
    )
