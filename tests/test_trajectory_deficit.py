from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

import scripts.audit_path_deficit_synthetic as audit_script
from arc3_voi.experiment import load_matrix
from arc3_voi.trajectory_deficit import (
    EXPECTED_WORKER_HEADROOM_BYTES,
    PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256,
    REGISTERED_AMENDMENT_SHA256,
    REGISTERED_ARM_HASHES,
    REGISTERED_CONFIG_FILE_SHA256,
    REGISTERED_CONFIG_SHA256,
    REGISTERED_MATRIX_SHA256,
    REGISTERED_SYNTHETIC_CANDIDATES_SHA256,
    REGISTERED_SYNTHETIC_CONTRACT_SHA256,
    REGISTERED_SYNTHETIC_SCENE_SHA256,
    REGISTERED_SYNTHETIC_SOURCE_MANIFEST_SHA256,
    registered_path_deficit_inputs,
    run_path_deficit_synthetic_audit,
)

CONFIG = Path("configs/template_v1_path_deficit_v2_x.yaml")
MATRIX = Path("artifacts/development_matrix_template_v1_path_deficit_v2.json")


def test_path_deficit_registration_is_exact_and_collision_free() -> None:
    registration = registered_path_deficit_inputs(CONFIG, MATRIX)
    matrix = load_matrix(MATRIX)
    prior = load_matrix("artifacts/development_matrix_template_v1.json")
    prior_qwen = load_matrix("artifacts/development_matrix.json")

    assert hashlib.sha256(CONFIG.read_bytes()).hexdigest() == (
        REGISTERED_CONFIG_FILE_SHA256
    )
    assert hashlib.sha256(MATRIX.read_bytes()).hexdigest() == REGISTERED_MATRIX_SHA256
    assert registration["config_sha256"] == REGISTERED_CONFIG_SHA256
    assert registration["amendment_sha256"] == REGISTERED_AMENDMENT_SHA256
    assert registration["arm_hashes"] == REGISTERED_ARM_HASHES
    assert registration["matrix_rows"] == 180
    assert registration["game_count"] == 15
    assert registration["seeds"] == [11, 23, 47]
    assert registration["first_run_id"] == (
        "development-bp35-0a0ad940-11-D-Q-qwen-0c91334b"
    )
    assert registration["last_run_id"] == (
        "development-wa30-ee6fef47-47-X-T-template_v1-de53f3df"
    )
    assert len({row.run_id for row in matrix}) == 180
    assert not {row.run_id for row in matrix}.intersection(row.run_id for row in prior)
    assert not {row.run_id for row in matrix}.intersection(
        row.run_id for row in prior_qwen
    )
    assert registration["prior_run_id_collisions"] == {"template_v1": 0, "qwen": 0}


def test_path_deficit_synthetic_audit_preserves_registered_failure() -> None:
    report = run_path_deficit_synthetic_audit(
        CONFIG,
        MATRIX,
        require_clean_commit=False,
        require_linux=False,
    )

    assert PATH_DEFICIT_SYNTHETIC_CONTRACT_SHA256 == (
        REGISTERED_SYNTHETIC_CONTRACT_SHA256
    )
    assert report["status"] == "synthetic_blocked"
    assert report["offline"] is True
    assert report["planner_error"] is None
    assert report["infrastructure_gate"] == {
        "passes": True,
        "reasons": [],
        "require_linux_memory": False,
        "expected_limit_kind": "rlimit_data_baseline_plus_budget",
        "expected_allocation_headroom_bytes": EXPECTED_WORKER_HEADROOM_BYTES,
        "grounding_workers_checked": 4,
        "persistent_workers_checked": 4,
        "resource_counters_checked": True,
    }
    assert report["acceptance_gate"]["passes"] is False
    assert report["acceptance_gate"]["reasons"] == [
        "committee agreement was not below 0.8",
        "maximum EVSI was below 0.05 actions",
        "no X-only action survived the unchanged admission rule",
    ]
    observed = report["acceptance_gate"]["observed"]
    assert observed["valid_programs"] == 4
    assert observed["selected_programs"] == 4
    assert observed["distinct_selected_programs"] == 4
    assert observed["graded_action_varying_programs"] >= 2
    assert observed["weights"] == pytest.approx(
        (0.4116174747, 0.2241004657, 0.2060449726, 0.1582370870)
    )
    assert observed["agreement"] == pytest.approx(0.8417629130389278)
    assert observed["maximum_evsi_actions"] == pytest.approx(
        0.048123650158264475
    )
    assert observed["x_only_probe_actions"] == []
    scene = report["synthetic_scene"]
    assert scene["payload_sha256"] == REGISTERED_SYNTHETIC_SCENE_SHA256
    assert scene["candidate_set_sha256"] == REGISTERED_SYNTHETIC_CANDIDATES_SHA256
    assert scene["source_manifest_sha256"] == (
        REGISTERED_SYNTHETIC_SOURCE_MANIFEST_SHA256
    )
    assert report["runtime_admission_gate"]["passes"] is False
    assert report["resource_usage"] == {
        "model_id": None,
        "model_calls": 0,
        "generated_tokens": 0,
        "gpu_used": False,
        "environment_actions": 0,
        "reward_observations": 0,
        "rhae_observations": 0,
    }
    assert report["treatment"]["canonical_bp35_audit_authorized"] is False
    assert report["treatment"]["gameplay_authorized"] is False
    assert report["treatment"]["development_matrix_execution_authorized"] is False


def test_negative_audit_wrapper_writes_once_and_exits_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "blocked.json"
    report = {
        "status": "synthetic_blocked",
        "acceptance_gate": {"passes": False, "reasons": ["registered failure"]},
    }
    monkeypatch.setattr(
        audit_script,
        "run_path_deficit_synthetic_audit",
        lambda *_args, **_kwargs: report,
    )
    monkeypatch.setattr(sys, "argv", ["audit_path_deficit_synthetic.py", "--output", str(output)])

    assert audit_script.main() == 2
    assert output.read_bytes() == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    with pytest.raises(FileExistsError, match="refusing to replace"):
        audit_script.main()
