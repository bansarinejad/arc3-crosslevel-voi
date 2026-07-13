"""Pre-generation administrative invariants for the preregistered v6 audit.

These tests are deliberately read-only.  In particular, the seed helper computes test
vectors in memory and never imports or invokes a lockbox generator.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from arc3_voi import action_qbc_v6_audit as v6_audit

ROOT = Path(__file__).resolve().parents[1]
PREREG_COMMIT = "a7f4da2d1e4773c3396243b12e983df910941c0c"
PREREG_TAG = "prereg-action-qbc-v6-finite-grid-evidence-v1"
PREREG_DOCUMENT = Path("docs/experiment_amendment_2026-07-14_action_qbc_v6_finite_grid.md")
OPEN_GATE_RESULT = Path("artifacts/action_qbc_v6_open_gate_result.json")

V2_SEED_DOMAIN = "arc3-action-qbc-v2-seed-v1"
V2_FAMILIES = ("homologue", "containment", "reflection")
V2_TEST_COMMIT = "0123456789abcdef0123456789abcdef01234567"
V2_EXPECTED_SEED_HEX = (
    "4e238becdb7deb75",
    "448dc0ce6754e65f",
    "012ef3ba534456dc",
    "23bd853ba8907fb2",
    "1058bb9ac1cf6fa1",
    "e259f3a28b4e6ca7",
    "524739d8870eabe1",
    "a5c8f189080e00fd",
    "52900ab992422305",
    "937dc21f69ac0475",
    "ada10504d8e1bdd3",
    "b5f04f241ee786f3",
)


def _git_bytes(*arguments: str) -> bytes:
    """Run one local, read-only Git query without a shell or network access."""

    completed = subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(f"local Git query failed: {detail}")
    return completed.stdout


def _v2_seed(commit: str, family: str, family_index: int) -> int:
    """Pure reference for the exact preregistered v2 seed formula."""

    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("mechanism-freeze commit must be forty lowercase hexadecimal characters")
    if family not in V2_FAMILIES:
        raise ValueError("family is outside the preregistered v2 family set")
    if isinstance(family_index, bool) or not isinstance(family_index, int):
        raise TypeError("family index must be an integer")
    if not 0 <= family_index <= 3:
        raise ValueError("family index must be the single digit 0 through 3")
    seed_material = f"{V2_SEED_DOMAIN}|{commit}|{family}|{family_index}".encode()
    return int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big", signed=False)


def test_v6_downstream_and_runtime_identities_are_exact() -> None:
    assert v6_audit.ACTION_QBC_V6_TREATMENT_ID == "action-qbc-v6-finite-grid-evidence-v1"
    assert v6_audit.ACTION_QBC_V6_RUNTIME_ID == "crosslevel-voi-runtime-v6"


def test_preregistration_tag_is_lightweight_and_resolves_to_exact_commit() -> None:
    expected = PREREG_COMMIT.encode("ascii")
    assert _git_bytes("rev-parse", PREREG_TAG).strip() == expected
    assert _git_bytes("rev-parse", f"{PREREG_TAG}^{{commit}}").strip() == expected
    assert _git_bytes("cat-file", "-t", PREREG_TAG).strip() == b"commit"


def test_preregistration_document_bytes_are_unchanged_from_frozen_commit() -> None:
    working_document = ROOT / PREREG_DOCUMENT
    committed_document = _git_bytes(
        "cat-file",
        "blob",
        f"{PREREG_COMMIT}:{PREREG_DOCUMENT.as_posix()}",
    )
    assert working_document.read_bytes() == committed_document


def test_v2_seed_formula_matches_exact_twelve_seed_vector() -> None:
    actual = tuple(
        f"{_v2_seed(V2_TEST_COMMIT, family, family_index):016x}"
        for family in V2_FAMILIES
        for family_index in range(4)
    )
    assert actual == V2_EXPECTED_SEED_HEX
    assert len(set(actual)) == 12


@pytest.mark.parametrize(
    ("commit", "family", "family_index", "error_type"),
    [
        ("A" * 40, "homologue", 0, ValueError),
        (V2_TEST_COMMIT, "unknown", 0, ValueError),
        (V2_TEST_COMMIT, "homologue", True, TypeError),
        (V2_TEST_COMMIT, "homologue", 4, ValueError),
    ],
)
def test_v2_seed_formula_rejects_nonregistered_inputs(
    commit: str,
    family: str,
    family_index: int,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        _v2_seed(commit, family, family_index)


def test_no_v2_lockbox_or_v6_permit_artifact_exists_before_freeze() -> None:
    artifact_directory = ROOT / "artifacts"
    forbidden: list[Path] = []
    for path in artifact_directory.iterdir():
        name = path.name.casefold()
        is_v2_lockbox = name.startswith("action_conditional_qbc_v2_lockbox")
        is_v6_permit = "action_qbc_v6" in name and "permit" in name
        if is_v2_lockbox or is_v6_permit:
            forbidden.append(path)
    assert forbidden == []


def test_negative_open_gate_result_is_exact_and_cancels_v2() -> None:
    result = json.loads((ROOT / OPEN_GATE_RESULT).read_text(encoding="utf-8"))
    assert result["schema_version"] == "action-qbc-v6-open-gate-result-v1"
    assert result["treatment_id"] == v6_audit.ACTION_QBC_V6_TREATMENT_ID
    assert result["runtime_id"] == v6_audit.ACTION_QBC_V6_RUNTIME_ID
    assert result["preregistration_commit"] == PREREG_COMMIT
    assert result["preregistration_tag"] == PREREG_TAG
    assert result["disposition"] == "negative_open_gate"
    assert result["implementation_freeze_authorized"] is False
    assert result["v2_generation_authorized"] is False
    assert result["sealed_execution_authorized"] is False

    matrix = result["authoritative_matrix"]
    assert matrix["visual_rows"] == 12
    assert matrix["passing_visual_rows"] == 3
    assert matrix["failing_visual_rows"] == 9
    assert matrix["translation_overflow_nonbackground_total"] == 107
    assert matrix["passing_rows"] == [
        "homologue/palette_bijection",
        "containment/palette_bijection",
        "reflection/palette_bijection",
    ]

    failing_visuals = result["failing_visuals"]
    assert len(failing_visuals) == 9
    assert all(
        row["comparison"]["status"] == "evaluated" and row["comparison"]["passes"] is False
        for row in failing_visuals
    )
    canonical = json.dumps(
        failing_visuals,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    expected_digest = "589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055"
    assert result["failure_vector_sha256"] == expected_digest
    assert hashlib.sha256(canonical).hexdigest() == expected_digest
