from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from arc3_voi.action_qbc_zero_run import (
    FROZEN_PREDECESSOR_MATRICES,
    GLOBAL_ZERO_COUNTERS,
    REGISTERED_ARMS,
    REGISTERED_DEVELOPMENT_GAMES,
    REGISTERED_DEVELOPMENT_SEEDS,
    REGISTERED_MANIFEST_PATH,
    REGISTERED_MANIFEST_SHA256,
    REGISTERED_POLICY_SHA256,
    REGISTERED_SPLIT_FILE_SHA256,
    build_zero_run_registration,
    registration_payload_sha256,
    serialize_zero_run_registration,
    validate_arm_config_hashes,
    validate_zero_run_registration,
)
from arc3_voi.experiment import load_matrix

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / REGISTERED_MANIFEST_PATH

EXPECTED_ARM_HASHES = {
    "D-Q": "8247eb92b176d471bba365856e28d441b186ddf0396b6fccd9a79b7636f22381",
    "S-T": "0c4dee3abaec89b6b42c75e60fee823099e3a95e49dffda84206fac7079a1094",
    "M-T": "2981a4d4209a7de924e16278eea180d2e4ab1c9b58359733f8c6be1900e4a3fa",
    "X-T": "e612be62a2cebca81062c5791f07af9b5b5c088f565b5cf25852aa41f859d60a",
}


def test_registered_builder_is_canonical_and_matches_checked_in_artifact() -> None:
    registration = build_zero_run_registration(ROOT)
    validate_zero_run_registration(registration, ROOT)
    expected_bytes = serialize_zero_run_registration(registration).encode("utf-8")

    assert ARTIFACT.read_bytes() == expected_bytes
    assert hashlib.sha256(expected_bytes).hexdigest() == REGISTERED_MANIFEST_SHA256
    assert registration_payload_sha256(registration) == REGISTERED_MANIFEST_SHA256
    assert len(load_matrix(ARTIFACT)) == 180


def test_registration_freezes_exact_v5_identity_and_four_full_hashes() -> None:
    registration = build_zero_run_registration(ROOT)

    assert registration["schema_version"] == "action-qbc-zero-run-registration-v1"
    assert registration["status"] == "registered-zero-run"
    assert registration["development_matrix_execution_authorized"] is False
    assert registration["identity_version"] == "source-v2"
    assert registration["treatment_identity"] == {
        "implementation_contract_version": "crosslevel-voi-runtime-v5",
        "probe_disagreement_policy_version": "action-conditional-outcome-qbc-v1",
        "probe_disagreement_policy_sha256": REGISTERED_POLICY_SHA256,
        "outcome_concentration_threshold": 0.8,
        "completion_cost_policy_version": "path-deficit-v2",
        "completion_cost_policy_sha256": (
            "055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670"
        ),
    }
    hashes = registration["configuration"]["arm_config_sha256"]
    assert hashes == EXPECTED_ARM_HASHES
    assert len(set(hashes.values())) == 4
    assert len({digest[:8] for digest in hashes.values()}) == 4


def test_registration_has_exact_source_v2_cells_and_no_outputs() -> None:
    registration = build_zero_run_registration(ROOT)
    rows = registration["runs"]

    assert len(rows) == 15 * 3 * 4 == 180
    assert registration["global_zero_counters"] == dict(GLOBAL_ZERO_COUNTERS)
    assert all(type(value) is int and value == 0 for value in GLOBAL_ZERO_COUNTERS.values())
    assert all(row["execution_count"] == row["output_count"] == 0 for row in rows)
    assert {row["game_id"] for row in rows} == set(REGISTERED_DEVELOPMENT_GAMES)
    assert {row["seed"] for row in rows} == set(REGISTERED_DEVELOPMENT_SEEDS)
    assert Counter(row["arm_label"] for row in rows) == {
        label: 45 for label, _variant, _source in REGISTERED_ARMS
    }
    assert {
        (
            row["arm_label"],
            row["variant"],
            row["hypothesis_source"],
            row["identity_version"],
        )
        for row in rows
    } == {
        (label, variant, source, "source-v2")
        for label, variant, source in REGISTERED_ARMS
    }
    assert len({row["run_id"] for row in rows}) == 180
    assert all(
        row["run_id"].endswith(row["config_hash"][:8])
        and row["config_hash"] == EXPECTED_ARM_HASHES[row["arm_label"]]
        for row in rows
    )


def test_predecessor_list_is_complete_content_addressed_and_collision_free() -> None:
    registration = build_zero_run_registration(ROOT)
    predecessor_paths = {row.path for row in FROZEN_PREDECESSOR_MATRICES}
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "artifacts").glob("development_matrix*.json")
        if path.relative_to(ROOT) != REGISTERED_MANIFEST_PATH
    }

    assert discovered == predecessor_paths
    assert registration["frozen_predecessors"] == [
        {"path": row.path, "sha256": row.sha256, "run_count": 180}
        for row in FROZEN_PREDECESSOR_MATRICES
    ]
    new_ids = {row["run_id"] for row in registration["runs"]}
    for predecessor in FROZEN_PREDECESSOR_MATRICES:
        prior = json.loads((ROOT / predecessor.path).read_text(encoding="utf-8"))
        assert new_ids.isdisjoint(row["run_id"] for row in prior)
    assert (
        hashlib.sha256((ROOT / "artifacts/public_split.json").read_bytes()).hexdigest()
        == REGISTERED_SPLIT_FILE_SHA256
    )


def test_prefix_collision_is_rejected_before_row_registration() -> None:
    shared_prefix = "12345678"
    hashes = dict(EXPECTED_ARM_HASHES)
    hashes["D-Q"] = shared_prefix + "0" * 56
    hashes["S-T"] = shared_prefix + "1" * 56

    with pytest.raises(ValueError, match="distinct eight-hex prefixes"):
        validate_arm_config_hashes(hashes)


def test_duplicate_full_hash_is_rejected_before_row_registration() -> None:
    hashes = dict(EXPECTED_ARM_HASHES)
    hashes["S-T"] = hashes["D-Q"]

    with pytest.raises(ValueError, match="full semantic config hashes"):
        validate_arm_config_hashes(hashes)


@pytest.mark.parametrize("counter", tuple(GLOBAL_ZERO_COUNTERS))
def test_temporary_nonzero_global_counter_is_rejected(
    tmp_path: Path, counter: str
) -> None:
    registration = copy.deepcopy(build_zero_run_registration(ROOT))
    registration["global_zero_counters"][counter] = 1
    path = tmp_path / "nonzero-registration.json"
    path.write_text(json.dumps(registration), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="immutable integer zero"):
        validate_zero_run_registration(reloaded, ROOT)


@pytest.mark.parametrize("counter", ("execution_count", "output_count"))
def test_temporary_nonzero_per_run_counter_is_rejected(
    tmp_path: Path, counter: str
) -> None:
    registration = copy.deepcopy(build_zero_run_registration(ROOT))
    registration["runs"][0][counter] = 1
    path = tmp_path / "executed-registration.json"
    path.write_text(json.dumps(registration), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="immutable integer zero"):
        validate_zero_run_registration(reloaded, ROOT)


def test_boolean_false_is_not_accepted_as_an_integer_zero() -> None:
    registration = copy.deepcopy(build_zero_run_registration(ROOT))
    registration["global_zero_counters"]["matrix_starts"] = False

    with pytest.raises(ValueError, match="immutable integer zero"):
        validate_zero_run_registration(registration, ROOT)
