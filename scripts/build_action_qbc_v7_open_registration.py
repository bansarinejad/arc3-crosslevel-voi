# ruff: noqa: E501
"""Build the zero-result registration for the preregistered v7 open diagnostic.

The producer is intentionally administrative.  It regenerates the twelve public scenes
through the one permitted data-only helper, reconstructs every registered action map and
row address, and binds the preregistration tree plus the nine non-registration additions.
It never invokes a compiler, planner, selector, controller, or scientific evaluator.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

from arc3_voi.action_qbc_audit import preregistered_control_contract_sha256
from arc3_voi.action_qbc_lockbox import generate_open_scene
from arc3_voi.action_qbc_policy import action_qbc_policy_sha256

SCHEMA_VERSION: Final = "action-qbc-v7-open-registration-v1"
STATUS: Final = "registered_zero_result"
TREATMENT_ID: Final = "action-qbc-v7-open-failure-decomposition-v1"
DIAGNOSTIC_SYSTEM_ID: Final = "crosslevel-voi-open-diagnostic-v7"
COMPARISON_SEMANTICS_ID: Final = (
    "action-qbc-v7-boundary-compound-selector-decomposition-v1"
)
PREREGISTRATION_TAG: Final = "prereg-action-qbc-v7-open-failure-decomposition-v1"
PREREGISTRATION_DOCUMENT: Final = (
    "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md"
)
V6_RESULT_COMMIT: Final = "6a7f6fb25b7e676d6aff5aecaaa26de63e436481"
V6_RESULT_JSON: Final = "artifacts/action_qbc_v6_open_gate_result.json"
V6_RESULT_DOCUMENT: Final = "docs/action_qbc_v6_open_gate_result.md"
V6_RESULT_JSON_SHA256: Final = (
    "853394f0b68bddaac9b5c1840e8afa51ffeba444920b132ad45b8d53740c751d"
)
V6_FAILURE_VECTOR_SHA256: Final = (
    "589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055"
)
V6_RESULT_DOCUMENT_SHA256: Final = (
    "a3bf5b20291d1b35f65b7fa20de7b9c6247ba918265eab588c6a34f66ff64c59"
)
RAW_POLICY_SHA256: Final = (
    "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
)
CONTROL_CONTRACT_SHA256: Final = (
    "44d08c5867f0c6842151e371263d2e25cdf550da7199c29801ed8c22f4afb9f7"
)
OUTPUT_PATH: Final = "artifacts/action_qbc_v7_open_registration.json"
OPEN_FREEZE_TAG: Final = "action-qbc-v7-open-diagnostic-freeze-v1"
EMPTY_SHA256: Final = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

FAMILIES: Final = ("homologue", "containment", "reflection")
VISUAL_TRANSFORMS: Final = (
    "palette_bijection",
    "translation_row_plus_3_col_plus_5",
    "translation_row_minus_3_col_minus_5",
    "scale_2_nearest_neighbor",
)
ORDER_TRANSFORMS: Final = (
    "candidate_list_reversal",
    "candidate_list_left_rotation_by_one",
    "hypothesis_list_reversal",
    "hypothesis_list_left_rotation_by_one",
    "serialized_outcome_cell_order_reversal",
)
ROLE_ORDER: Final = (
    "conservative_evidence",
    "topology_contact",
    "homology_alignment",
    "symmetry_completion",
)
CONTROL_IDS: Final = (
    "identical_signatures_A1",
    "dominant_mass_Aeq0_8_positive_JX",
    "A_lt_0_8_evsi0",
    "fragmented_cosmetic_evsi0",
    "evsi_0_049",
    "material_positive_JX_A_ge_0_8",
    "inverse_low_global_agreement_A_ge_0_8",
    "unused_rowwise_x_only_X_selects_other_probe",
    "M_positive_eligible_different_from_X",
    "exhausted_probe_cap",
    "catastrophe_makes_JX_nonpositive",
    "final_multiplier_1_M_equals_X",
    "invalid_program_structural_false",
    "timeout_program_structural_false",
    "fewer_than_two_eligible_graded_roles",
    "worker_memory_drift",
    "forbidden_resource_use",
    "boundary_evsi_eq_0_05",
    "cosmetic_refinement_pair",
    "candidate_tie_pair",
)
CONTROL_PREDICATES: Final = (
    "c00_identical_ineligible_exploit",
    "c01_strict_cutoff_ineligible_exploit",
    "c02_zero_evsi_nonpositive_exploit",
    "c03_cosmetic_no_decision_value",
    "c04_evsi_0049_below_materiality",
    "c05_high_agreement_blocks_probe",
    "c06_row_agreement_blocks_probe",
    "c07_unused_x_row_not_selected",
    "c08_m_positive_breaks_contrast",
    "c09_probe_cap_exploit",
    "c10_catastrophe_nonpositive_exploit",
    "c11_multiplier_one_equal",
    "c12_invalid_program_structural_false",
    "c13_timeout_program_structural_false",
    "c14_too_few_roles_structural_false",
    "c15_worker_memory_drift_false",
    "c16_forbidden_resource_false",
    "c17_evsi_005_material_boundary",
    "c18_cosmetic_refinement_invariant",
    "c19_tie_policy_split",
)
CONTROL_CALL_COUNTS: Final = (1,) * 14 + (0, 0, 0, 1, 2, 2)

# family, index, seed, scene hash, source background, forward palette
SCENE_SPECS: Final = (
    ("homologue", 0, "1020304050607080", "a4c6b8f30db80457d4f4491a7afbdcb21fc6e122b70c56359a404346c21142ad", 5, (4, 2, 3, 13, 1, 8, 10, 12, 5, 11, 14, 6, 9, 15, 0, 7)),
    ("homologue", 1, "82c9dc349d88e442", "738028f93692db779b6c4497c6cc5af43bfbfcce1d7062836c1224b5f46e00bb", 5, (5, 12, 11, 8, 3, 4, 10, 0, 14, 7, 6, 1, 13, 9, 15, 2)),
    ("homologue", 2, "9bec03c65cbeb80e", "d38946e2bb1a1e27ff4c907d1b3ebef0de2429d0754c3f206641164e610dd09e", 12, (9, 6, 12, 11, 15, 2, 10, 3, 5, 7, 14, 13, 0, 1, 8, 4)),
    ("homologue", 3, "e5105aa7430099e8", "610856638a35f9bd5f29c6ad04e72239f4bb63751f10cd2651a07619eefc7ccf", 14, (14, 12, 1, 3, 6, 13, 0, 15, 7, 10, 2, 4, 5, 8, 11, 9)),
    ("containment", 0, "2233445566778899", "5b175e279e42d13df3af915a585504e7fe3ccdd152ff6e460731a98f99ed9365", 13, (3, 12, 5, 10, 15, 4, 14, 0, 13, 6, 11, 7, 1, 2, 8, 9)),
    ("containment", 1, "94768a51dd5a7928", "1023edb7164487292196919ca5f97bddb93c025470801bcabfb4e031ebd4591e", 0, (12, 7, 1, 4, 9, 2, 0, 15, 8, 14, 13, 5, 11, 3, 6, 10)),
    ("containment", 2, "b416ef2617f85077", "fab3d56c35ae1ce566b0c86e1724d057e93a5b7e34d2fd95953e44faad07f62d", 13, (13, 11, 6, 1, 15, 9, 7, 2, 4, 8, 5, 14, 12, 3, 0, 10)),
    ("containment", 3, "a1af782e839e03cc", "1a4a02ef0a99163b712accae959707b51ba4437efe38c9dbeea0ad5d8b6b566e", 12, (7, 1, 4, 11, 0, 3, 14, 2, 5, 15, 9, 12, 6, 13, 8, 10)),
    ("reflection", 0, "3141592653589793", "c9c8ce0a18e605e8bfcbb8b87672620238dd7c3b5b8fee5c039b958a99abdc86", 1, (10, 11, 6, 7, 8, 1, 4, 9, 3, 14, 2, 13, 0, 12, 5, 15)),
    ("reflection", 1, "cb5c43f7f4f3d98b", "deb4ddb3ddc7e1910adf416d38ff43fd0b59971b5a296edf8a5d09f3cb5adf2e", 0, (9, 2, 4, 15, 7, 14, 3, 6, 11, 5, 12, 10, 1, 13, 8, 0)),
    ("reflection", 2, "c7812a3f9c726d1a", "05204179a556cf2acdf0579b2a89064c4efcc24de7c25217a61eeb6a2a976fac", 7, (2, 6, 14, 0, 8, 13, 5, 9, 1, 11, 4, 3, 15, 12, 10, 7)),
    ("reflection", 3, "cfceb4850da65599", "944dfc1f7a2d67aac00106284da290a78de78545e5bcc910bac7eda2d0638542", 5, (7, 6, 8, 5, 4, 13, 12, 1, 15, 3, 9, 0, 2, 10, 11, 14)),
)

NON_REGISTRATION_ADDITIONS: Final = (
    "docs/action_qbc_v7_open_diagnostic_runbook.md",
    "scripts/build_action_qbc_v7_open_registration.py",
    "scripts/finalize_action_qbc_v7_open_diagnostic.py",
    "scripts/reconstruct_action_qbc_v7_open_registration.py",
    "scripts/run_action_qbc_v7_open_diagnostic.py",
    "src/arc3_voi/action_qbc_v7_audit.py",
    "src/arc3_voi/action_qbc_v7_reference.py",
    "tests/test_action_qbc_v7_audit.py",
    "tests/test_action_qbc_v7_registration.py",
)
ALL_ADDITIONS: Final = tuple(sorted((*NON_REGISTRATION_ADDITIONS, OUTPUT_PATH)))

AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v7_enabled": False,
    "final_admission_claimed": False,
}

REASON_ORDER: Final = (
    "no_prepreregistered_observation", "base_pipeline_unavailable",
    "transformed_pipeline_unavailable", "pipeline_snapshot_invalid",
    "required_action_mapping_missing", "mapped_frontier_set_mismatch",
    "mapped_frontier_sequence_mismatch", "action_map_not_canonical_order_preserving",
    "compiler_role_mismatch", "gibbs_weight_nonfinite", "gibbs_weight_mismatch",
    "invalid_root_prediction", "prediction_label_outside_palette_domain",
    "scale_output_shape_outside_prediction_domain", "transformed_prediction_shape_mismatch",
    "observable_prediction_grid_mismatch", "expected_exterior_support_present",
    "prediction_game_state_mismatch", "prediction_level_delta_mismatch",
    "rolewise_cost_nonfinite", "rolewise_cost_mismatch", "raw_selector_numeric_mismatch",
    "raw_selector_eligibility_mismatch", "raw_selector_rank_mismatch",
    "raw_selector_set_mismatch", "raw_selector_gate_mismatch",
    "raw_selector_decision_mismatch", "fixed_selector_key_mismatch",
    "fixed_selector_numeric_mismatch", "fixed_selector_eligibility_mismatch",
    "fixed_selector_dense_rank_mismatch", "fixed_selector_set_mismatch",
    "fixed_selector_gate_mismatch", "fixed_selector_decision_mismatch",
    "isolated_action_map_not_bijective",
    "isolated_action_map_not_canonical_order_preserving",
    "isolated_signature_transform_not_injective", "v6_failure_vector_mismatch",
    "prepreregistered_base_observation_mismatch", "structural_gate_failed",
    "mechanism_gate_failed", "causal_diagnostic_false", "order_relation_mismatch",
    "control_expectation_mismatch", "resource_counter_mismatch",
    "forbidden_resource_use", "not_testable_due_upstream_mismatch",
)

AGGREGATE_KEYS: Final = (
    "v6_failure_vector_reproduced", "v6_failure_vector_observed_sha256",
    "prepreregistered_base_reproduced_count", "prepreregistered_base_denominator",
    "base_structural_pass_count", "base_structural_denominator",
    "base_mechanism_pass_count", "base_mechanism_denominator", "base_causal_true_count",
    "base_causal_denominator", "translation_prediction_pair_count",
    "translation_fully_equivariant_pair_count",
    "translation_boundary_consistent_censored_pair_count",
    "translation_interior_or_metadata_mismatch_pair_count",
    "translation_invalid_prediction_pair_count", "translation_expected_exterior_cell_count",
    "translation_boundary_consistent_exterior_cell_count",
    "translation_mixed_exterior_cell_count",
    "translation_invalid_prediction_exterior_cell_count",
    "frozen_positive_translation_exterior_cell_denominator",
    "frozen_positive_translation_observed_exterior_cell_count",
    "frozen_positive_translation_boundary_consistent_exterior_cell_count",
    "frozen_positive_translation_support_reproduced",
    "primary_compound_scale_reconciliation_count", "primary_compound_scale_denominator",
    "primary_compound_scale_reconciliation", "extension_compound_scale_reconciliation_count",
    "extension_compound_scale_denominator", "isolated_action_relabel_required_count",
    "isolated_action_relabel_pass_count", "isolated_signature_pushforward_required_count",
    "isolated_signature_pushforward_pass_count", "actual_raw_selector_evaluated_count",
    "actual_raw_selector_pass_count", "actual_raw_selector_precondition_failed_count",
    "actual_fixed_selector_evaluated_count", "actual_fixed_selector_pass_count",
    "actual_fixed_selector_precondition_failed_count", "order_raw_pass_count",
    "order_raw_denominator", "order_fixed_pass_count", "order_fixed_denominator",
    "control_raw_pass_count", "control_raw_denominator", "control_fixed_pass_count",
    "control_fixed_denominator", "resource_contract_passes", "reason_counts",
)

GLOBAL_FALLBACK_STAGES: Final = (
    "transform_action_map_invalid", "scientific_record_inventory_invalid",
    "grid_evidence_table_invalid", "expected_exterior_support_table_invalid",
    "evaluator_internal_error", "payload_size_limit_exceeded",
)

ADMINISTRATIVE_STAGES: Final = (
    "tag_verification_failed", "execution_root_setup_failed", "clone_a_failed",
    "clone_b_failed", "environment_a_failed", "environment_b_failed",
    "preflight_a_failed", "preflight_b_failed", "registration_invalid",
    "process_a_nonzero", "process_a_output_missing", "process_a_payload_invalid",
    "process_b_nonzero", "process_b_output_missing", "process_b_payload_invalid",
    "payload_byte_mismatch", "receipt_finalization_failed", "exclusive_publication_failed",
    "publication_rollback_failed",
)

ORDER_CONTRACTS: Final = (
    {"schema_version": "action-qbc-v7-order-transform-contract-v1", "name": "candidate_list_reversal", "target": "candidate_sequence", "rule": "reverse"},
    {"schema_version": "action-qbc-v7-order-transform-contract-v1", "name": "candidate_list_left_rotation_by_one", "target": "candidate_sequence", "rule": "left_rotate_one"},
    {"schema_version": "action-qbc-v7-order-transform-contract-v1", "name": "hypothesis_list_reversal", "target": "hypothesis_sequence", "rule": "reverse"},
    {"schema_version": "action-qbc-v7-order-transform-contract-v1", "name": "hypothesis_list_left_rotation_by_one", "target": "hypothesis_sequence", "rule": "left_rotate_one"},
    {"schema_version": "action-qbc-v7-order-transform-contract-v1", "name": "serialized_outcome_cell_order_reversal", "target": "per_action_serialized_outcome_cell_sequence", "rule": "reverse"},
)


class RegistrationError(RuntimeError):
    """Raised when a registration precondition or identity fails closed."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the sole compact, sorted, ASCII JSON representation."""

    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(root), *arguments),
        input=input_bytes,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RegistrationError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout


def _require_lower_hex(value: str, length: int, label: str) -> None:
    if len(value) != length or any(character not in "0123456789abcdef" for character in value):
        raise RegistrationError(f"{label} is not {length}-character lowercase hexadecimal")


def _resolve_preregistration(root: Path, tag: str) -> str:
    if tag != PREREGISTRATION_TAG:
        raise RegistrationError("the producer accepts only the frozen preregistration tag")
    if _git(root, "cat-file", "-t", tag).strip() != b"commit":
        raise RegistrationError("preregistration tag is not lightweight")
    commit = _git(root, "rev-parse", tag).decode("ascii").strip()
    _require_lower_hex(commit, 40, "preregistration commit")
    if _git(root, "rev-parse", f"{tag}^{{commit}}").decode("ascii").strip() != commit:
        raise RegistrationError("preregistration tag resolution is inconsistent")
    parent = _git(root, "rev-parse", f"{commit}^").decode("ascii").strip()
    if parent != V6_RESULT_COMMIT:
        raise RegistrationError("preregistration is not a direct child of the v6 result")
    delta = _git(root, "diff", "--name-status", "-z", V6_RESULT_COMMIT, commit)
    if delta != b"A\0" + PREREGISTRATION_DOCUMENT.encode("utf-8") + b"\0":
        raise RegistrationError("P contains changes other than the preregistration document")
    return commit


def _tree_entries(root: Path, commit: str) -> list[tuple[str, str, int]]:
    raw = _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit)
    result: list[tuple[str, str, int]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_raw = record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 4 or fields[1] != b"blob":
            raise RegistrationError("P tree contains a malformed or non-blob entry")
        path = path_raw.decode("utf-8")
        oid = fields[2].decode("ascii")
        size = int(fields[3])
        _require_lower_hex(oid, 40, f"Git blob for {path}")
        result.append((path, oid, size))
    result.sort(key=lambda item: item[0])
    if not result or len({path for path, _, _ in result}) != len(result):
        raise RegistrationError("P tree inventory is empty or duplicated")
    return result


def _batch_blob_bytes(root: Path, entries: Sequence[tuple[str, str, int]]) -> list[bytes]:
    request = b"".join(oid.encode("ascii") + b"\n" for _, oid, _ in entries)
    raw = _git(root, "cat-file", "--batch", input_bytes=request)
    offset = 0
    blobs: list[bytes] = []
    for path, expected_oid, expected_size in entries:
        newline = raw.find(b"\n", offset)
        if newline < 0:
            raise RegistrationError("git cat-file batch response ended before its header")
        header = raw[offset:newline].split()
        if len(header) != 3 or header[0].decode("ascii") != expected_oid or header[1] != b"blob":
            raise RegistrationError(f"unexpected Git batch header for {path}")
        size = int(header[2])
        if size != expected_size:
            raise RegistrationError(f"Git tree/blob size mismatch for {path}")
        start = newline + 1
        end = start + size
        if end >= len(raw) or raw[end : end + 1] != b"\n":
            raise RegistrationError(f"malformed Git batch payload for {path}")
        blobs.append(raw[start:end])
        offset = end + 1
    if offset != len(raw):
        raise RegistrationError("Git batch response has trailing bytes")
    return blobs


def _preregistration_manifest(root: Path, commit: str) -> list[dict[str, object]]:
    entries = _tree_entries(root, commit)
    blobs = _batch_blob_bytes(root, entries)
    rows = []
    for (path, oid, size), raw in zip(entries, blobs, strict=True):
        calculated = hashlib.sha1(
            f"blob {len(raw)}\0".encode("ascii") + raw, usedforsecurity=False
        ).hexdigest()
        if calculated != oid or len(raw) != size:
            raise RegistrationError(f"Git blob identity failed for {path}")
        rows.append(
            {"path": path, "git_blob_sha1": oid, "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": size}
        )
    return rows


def _plain_file_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise RegistrationError(f"required plain file is absent: {relative}")
    return path.read_bytes()


def _added_manifest(root: Path) -> list[dict[str, object]]:
    rows = []
    for relative in sorted(NON_REGISTRATION_ADDITIONS):
        raw = _plain_file_bytes(root, relative)
        oid = hashlib.sha1(
            f"blob {len(raw)}\0".encode("ascii") + raw, usedforsecurity=False
        ).hexdigest()
        observed = _git(root, "hash-object", "--no-filters", relative).decode("ascii").strip()
        if observed != oid:
            raise RegistrationError(f"worktree changed while hashing {relative}")
        rows.append(
            {"path": relative, "git_blob_sha1": oid, "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}
        )
    return rows


def _verify_repository_delta(root: Path, preregistration_commit: str) -> None:
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if head == preregistration_commit:
        paths: set[str] = set()
        for record in status.split(b"\0"):
            if not record:
                continue
            if len(record) < 4 or record[2:3] != b" ":
                raise RegistrationError("noncanonical Git status record before O")
            code = record[:2]
            path = record[3:].decode("utf-8")
            if code != b"A " or path not in ALL_ADDITIONS:
                raise RegistrationError(f"non-allowlisted pre-O worktree change: {path}")
            paths.add(path)
        required = set(NON_REGISTRATION_ADDITIONS)
        if not required.issubset(paths):
            missing = sorted(required - paths)
            raise RegistrationError(f"missing pre-O additions: {missing}")
        if paths - required not in (set(), {OUTPUT_PATH}):
            raise RegistrationError("pre-O delta is not the nine files plus optional registration")
        if _git(root, "diff", "--name-status", "-z") != b"":
            raise RegistrationError("pre-O additions have unstaged byte changes")
        cached = _git(
            root,
            "diff",
            "--cached",
            "--name-status",
            "--no-renames",
            "-z",
            preregistration_commit,
        )
        expected_cached = b"".join(
            b"A\0" + path.encode("utf-8") + b"\0" for path in sorted(paths)
        )
        if cached != expected_cached:
            raise RegistrationError("index does not contain the exact staged pre-O additions")
        tracked = _git(root, "diff", "--name-status", "--no-renames", "-z", preregistration_commit)
        # Untracked additions do not appear; any tracked record must still be an allowed add.
        tokens = tracked.split(b"\0")
        for offset in range(0, len(tokens) - 1, 2):
            if tokens[offset] != b"A" or tokens[offset + 1].decode("utf-8") not in ALL_ADDITIONS:
                raise RegistrationError("P existing content was modified before O")
        return
    if status != b"":
        raise RegistrationError("post-P reconstruction requires a byte-clean worktree")
    if _git(root, "rev-parse", f"{head}^").decode("ascii").strip() != preregistration_commit:
        raise RegistrationError("open freeze must be a direct child of P")
    delta = _git(root, "diff", "--name-status", "--no-renames", "-z", preregistration_commit, head)
    expected = b"".join(b"A\0" + path.encode("utf-8") + b"\0" for path in ALL_ADDITIONS)
    if delta != expected:
        raise RegistrationError("P..O delta is not the exact ten-path allowlist")


def _verify_v6_anchors(root: Path) -> dict[str, object]:
    result_raw = _git(root, "cat-file", "blob", f"{V6_RESULT_COMMIT}:{V6_RESULT_JSON}")
    document_raw = _git(root, "cat-file", "blob", f"{V6_RESULT_COMMIT}:{V6_RESULT_DOCUMENT}")
    if hashlib.sha256(result_raw).hexdigest() != V6_RESULT_JSON_SHA256:
        raise RegistrationError("v6 result JSON anchor differs")
    if hashlib.sha256(document_raw).hexdigest() != V6_RESULT_DOCUMENT_SHA256:
        raise RegistrationError("v6 result document anchor differs")
    try:
        value = json.loads(result_raw)
        failure_vector = value["failing_visuals"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RegistrationError("v6 result JSON cannot rederive its failure vector") from error
    if canonical_sha256(failure_vector) != V6_FAILURE_VECTOR_SHA256:
        raise RegistrationError("v6 failure-vector anchor differs")
    return {
        "result_commit_sha": V6_RESULT_COMMIT,
        "result_json_path": V6_RESULT_JSON,
        "result_json_sha256": V6_RESULT_JSON_SHA256,
        "failure_vector_sha256": V6_FAILURE_VECTOR_SHA256,
        "result_document_sha256": V6_RESULT_DOCUMENT_SHA256,
    }


def _scene_inventory() -> tuple[dict[str, object], list[dict[str, object]]]:
    scenes: list[dict[str, object]] = []
    generated_rows: list[dict[str, object]] = []
    for family, index, seed_hex, expected_sha, background, palette in SCENE_SPECS:
        scene = generate_open_scene(family, int(seed_hex, 16))
        generated_rows.append(scene)
        if set(scene) == set() or scene.get("content_sha256") != expected_sha:
            raise RegistrationError(f"public scene identity mismatch: {family}/{index}")
        unhashed = dict(scene)
        unhashed.pop("content_sha256", None)
        if canonical_sha256(unhashed) != expected_sha:
            raise RegistrationError(f"public scene self-hash mismatch: {family}/{index}")
        if scene.get("family") != family or scene.get("seed_hex") != seed_hex:
            raise RegistrationError(f"public scene address mismatch: {family}/{index}")
        base = scene.get("base_scene")
        transforms = scene.get("visual_transforms")
        if not isinstance(base, Mapping) or not isinstance(transforms, list):
            raise RegistrationError(f"public scene structure mismatch: {family}/{index}")
        palette_rows = [
            row for row in transforms
            if isinstance(row, Mapping) and row.get("name") == "palette_bijection"
        ]
        if len(palette_rows) != 1 or not isinstance(palette_rows[0].get("parameters"), Mapping):
            raise RegistrationError(f"public scene palette transform mismatch: {family}/{index}")
        observed_palette = palette_rows[0]["parameters"].get("forward_palette")
        if (
            base.get("background_label") != background
            or base.get("grid_shape") != [32, 32]
            or base.get("available_actions") != ["ACTION3", "ACTION6"]
            or observed_palette != list(palette)
            or palette_rows[0].get("background_label") != palette[background]
        ):
            raise RegistrationError(f"public scene registered metadata mismatch: {family}/{index}")
        scenes.append(
            {
                "family": family,
                "scene_index": index,
                "seed_hex": seed_hex,
                "scene_sha256": expected_sha,
                "background_label": background,
                "source_shape": [32, 32],
                "available_actions": ["ACTION3", "ACTION6"],
                "palette_forward": list(palette),
            }
        )
    return {"count": 12, "scenes": scenes}, generated_rows


def _transform_contract(scene: Mapping[str, object], name: str) -> dict[str, object]:
    family = cast(str, scene["family"])
    index = cast(int, scene["scene_index"])
    background = cast(int, scene["background_label"])
    palette = cast(list[int], scene["palette_forward"])
    if name == "palette_bijection":
        actual_shape = isolated_shape = [32, 32]
        destination_background = palette[background]
        parameters: dict[str, object] = {"forward_palette": palette}
    elif name == "translation_row_plus_3_col_plus_5":
        actual_shape, isolated_shape = [32, 32], [38, 42]
        destination_background = background
        parameters = {"delta_row": 3, "delta_col": 5}
    elif name == "translation_row_minus_3_col_minus_5":
        actual_shape, isolated_shape = [32, 32], [38, 42]
        destination_background = background
        parameters = {"delta_row": -3, "delta_col": -5}
    elif name == "scale_2_nearest_neighbor":
        actual_shape = isolated_shape = [64, 64]
        destination_background = background
        parameters = {"factor": 2}
    else:
        raise RegistrationError(f"unknown visual transform: {name}")
    preimage = {
        "schema_version": "action-qbc-v7-transform-contract-v1",
        "family": family,
        "scene_index": index,
        "transform_name": name,
        "source_shape": [32, 32],
        "actual_destination_shape": actual_shape,
        "isolated_destination_shape": isolated_shape,
        "source_background_label": background,
        "destination_background_label": destination_background,
        "parameters": parameters,
    }
    contract_hash = canonical_sha256(preimage)
    actual_hash = _action_map_hash(name, "actual", contract_hash, actual_shape)
    isolated_hash = _action_map_hash(name, "isolated", contract_hash, isolated_shape)
    return {
        key: value for key, value in preimage.items() if key != "schema_version"
    } | {
        "contract_sha256": contract_hash,
        "actual_action_map_sha256": actual_hash,
        "isolated_action_map_sha256": isolated_hash,
    }


def _action_map_hash(
    transform_name: str, map_kind: str, contract_hash: str, destination_shape: list[int]
) -> str:
    action6: list[list[list[int]]] = []
    for row in range(32):
        for col in range(32):
            if transform_name == "palette_bijection":
                destination = [row, col]
            elif transform_name.startswith("translation_row_"):
                delta_row = 3 if "plus" in transform_name else -3
                delta_col = 5 if "plus" in transform_name else -5
                if map_kind == "actual":
                    destination = [row + delta_row, col + delta_col]
                    if not (0 <= destination[0] < 32 and 0 <= destination[1] < 32):
                        continue
                else:
                    destination = [
                        row + abs(delta_row) + delta_row,
                        col + abs(delta_col) + delta_col,
                    ]
            elif transform_name == "scale_2_nearest_neighbor":
                destination = [2 * row, 2 * col]
            else:
                raise RegistrationError(f"unknown map transform: {transform_name}")
            action6.append([[row, col], destination])
    preimage = {
        "schema_version": "action-qbc-v7-action-map-v1",
        "map_kind": map_kind,
        "transform_contract_sha256": contract_hash,
        "source_shape": [32, 32],
        "destination_shape": destination_shape,
        "simple_actions": ["ACTION3"],
        "action6_forward": action6,
    }
    return canonical_sha256(preimage)


def _transforms_and_rows(
    scene_inventory: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    scenes = cast(list[dict[str, object]], scene_inventory["scenes"])
    transforms: list[dict[str, object]] = []
    lookup: dict[tuple[str, int, str], dict[str, object]] = {}
    for scene in scenes:
        for name in VISUAL_TRANSFORMS:
            contract = _transform_contract(scene, name)
            transforms.append(contract)
            lookup[(cast(str, scene["family"]), cast(int, scene["scene_index"]), name)] = contract
    rows: list[dict[str, object]] = []
    for scene in scenes:
        family = cast(str, scene["family"])
        index = cast(int, scene["scene_index"])
        rows.append(
            {
                "row_index": len(rows), "row_id": f"base:{family}:{index}",
                "kind": "base_scene", "registered_placeholder": True,
                "family": family, "scene_index": index, "seed_hex": scene["seed_hex"],
                "scene_sha256": scene["scene_sha256"],
            }
        )
    for scene in scenes:
        family = cast(str, scene["family"])
        index = cast(int, scene["scene_index"])
        for name in VISUAL_TRANSFORMS:
            contract = lookup[(family, index, name)]
            rows.append(
                {
                    "row_index": len(rows), "row_id": f"visual:{family}:{index}:{name}",
                    "kind": "visual_transform", "registered_placeholder": True,
                    "family": family, "scene_index": index, "seed_hex": scene["seed_hex"],
                    "scene_sha256": scene["scene_sha256"], "transform_name": name,
                    "transform_contract_sha256": contract["contract_sha256"],
                    "actual_action_map_sha256": contract["actual_action_map_sha256"],
                    "isolated_action_map_sha256": contract["isolated_action_map_sha256"],
                }
            )
    order_hashes = {cast(str, item["name"]): canonical_sha256(item) for item in ORDER_CONTRACTS}
    for scene in scenes:
        family = cast(str, scene["family"])
        index = cast(int, scene["scene_index"])
        for name in ORDER_TRANSFORMS:
            rows.append(
                {
                    "row_index": len(rows), "row_id": f"order:{family}:{index}:{name}",
                    "kind": "order_transform", "registered_placeholder": True,
                    "family": family, "scene_index": index, "seed_hex": scene["seed_hex"],
                    "scene_sha256": scene["scene_sha256"], "transform_name": name,
                    "order_contract_sha256": order_hashes[name],
                }
            )
    for control_index, (control_id, predicate, calls) in enumerate(
        zip(CONTROL_IDS, CONTROL_PREDICATES, CONTROL_CALL_COUNTS, strict=True)
    ):
        fixed_predicate = (
            f"{predicate}:compound_canonical_invariant"
            if control_index == 19
            else f"{predicate}:legacy_record_pass"
        )
        rows.append(
            {
                "row_index": len(rows), "row_id": f"control:{control_id}",
                "kind": "control", "registered_placeholder": True,
                "control_id": control_id, "control_index": control_index,
                "raw_selector_call_count": calls, "fixed_selector_call_count": calls,
                "control_contract_sha256": CONTROL_CONTRACT_SHA256,
                "raw_predicate_id": f"{predicate}:legacy_record_pass",
                "fixed_predicate_id": fixed_predicate,
            }
        )
    if len(rows) != 140 or [row["row_index"] for row in rows] != list(range(140)):
        raise RegistrationError("row plan failed to reconstruct exactly 140 contiguous rows")
    return transforms, {
        "count": 140,
        "order": "base-all-scenes_then-visual-all-scenes_then-order-all-scenes_then-controls-v1",
        "rows": rows,
    }


def _raw_selector_identity() -> dict[str, object]:
    return {
        "module": "arc3_voi.action_qbc_policy",
        "callable": "select_action_conditional_qbc",
        "policy_version": "action-conditional-outcome-qbc-v1",
        "runtime_version": "crosslevel-voi-runtime-v5",
        "source_bundle_sha256": RAW_POLICY_SHA256,
    }


def _scientific_contract() -> dict[str, object]:
    raw = _raw_selector_identity()
    fixed = {
        "version": "action-qbc-v7-compound-selector-2^-40-dense-canonical-v1",
        "raw_selector_identity": raw,
        "quantum_numerator": 1,
        "quantum_denominator": 1099511627776,
        "rank_policy": "dense_by_integer_key",
        "tie_set_policy": "complete_integer_key_ties",
        "singleton_tie_break": "canonical_action_order",
        "positive_utility_gate": "integer_key_strictly_greater_than_zero",
    }
    return {
        "role_order": list(ROLE_ORDER), "raw_selector_identity": raw,
        "fixed_selector_identity": fixed, "absolute_tolerance": 1e-12,
        "relative_tolerance": 1e-12, "fixed_quantum_numerator": 1,
        "fixed_quantum_denominator": 1099511627776, "reason_order": list(REASON_ORDER),
        "grid_evidence_schema": "action-qbc-v7-grid-evidence-table-v1",
        "expected_exterior_support_schema": "action-qbc-v7-expected-exterior-support-table-v1",
        "aggregate_keys": list(AGGREGATE_KEYS),
        "global_fallback_stage_order": list(GLOBAL_FALLBACK_STAGES),
        "payload_cap_bytes": 67108864, "order_contracts": [dict(row) for row in ORDER_CONTRACTS],
    }


def _expected_counts() -> dict[str, int]:
    scene_count = len(SCENE_SPECS)
    pipelines = scene_count * (1 + len(VISUAL_TRANSFORMS))
    candidate_pipelines = scene_count * 4
    order_rows = scene_count * len(ORDER_TRANSFORMS)
    raw_scene = candidate_pipelines * 3 + scene_count + order_rows
    fixed_scene = pipelines + order_rows
    isolated_each = scene_count * len(VISUAL_TRANSFORMS) * 2
    control_calls = sum(CONTROL_CALL_COUNTS)
    result = {
        "public_scene_generations": scene_count, "registered_scene_file_reads": 0,
        "candidate_builder_calls": candidate_pipelines, "compiler_calls": pipelines,
        "compiled_programs": pipelines * 4, "grounding_evaluations": pipelines * 4,
        "hypothesis_pool_constructions": pipelines, "persistent_worker_starts": pipelines * 4,
        "transient_worker_starts": pipelines * 4, "total_worker_starts": pipelines * 8,
        "planner_calls": pipelines, "completed_planning_snapshots": pipelines,
        "controller_calls": candidate_pipelines * 2,
        "controller_snapshot_replays": candidate_pipelines * 2,
        "v4_counterfactual_calls": scene_count, "raw_selector_scene_order_calls": raw_scene,
        "raw_selector_control_calls": control_calls,
        "fixed_selector_scene_order_calls": fixed_scene,
        "fixed_selector_control_calls": control_calls,
        "isolated_raw_selector_calls": isolated_each,
        "isolated_fixed_selector_calls": isolated_each,
        "pure_selector_calls": raw_scene + control_calls + fixed_scene + control_calls + 2 * isolated_each,
        "model_calls": 0, "generated_tokens": 0, "gpu_operations": 0, "network_calls": 0,
        "environment_actions": 0, "reward_observations": 0, "rhae_observations": 0,
        "lockbox_path_operations": 0, "lockbox_bytes_read": 0,
    }
    if len(result) != 31 or result["pure_selector_calls"] != 566:
        raise RegistrationError("resource call graph did not reconstruct the 31-counter vector")
    return result


def _resource_contract() -> dict[str, object]:
    ledger = [
        {"control_id": control_id, "raw_selector_call_count": calls, "fixed_selector_call_count": calls}
        for control_id, calls in zip(CONTROL_IDS, CONTROL_CALL_COUNTS, strict=True)
    ]
    increment = {
        "before_attempt": ["candidate_builder_calls", "compiler_calls", "controller_calls", "environment_actions", "fixed_selector_scene_order_calls", "gpu_operations", "grounding_evaluations", "isolated_fixed_selector_calls", "isolated_raw_selector_calls", "lockbox_path_operations", "model_calls", "network_calls", "planner_calls", "public_scene_generations", "raw_selector_control_calls", "raw_selector_scene_order_calls", "transient_worker_starts", "v4_counterfactual_calls"],
        "after_success": ["compiled_programs", "completed_planning_snapshots", "controller_snapshot_replays", "hypothesis_pool_constructions", "persistent_worker_starts", "registered_scene_file_reads"],
        "on_observation": ["generated_tokens", "lockbox_bytes_read", "reward_observations", "rhae_observations"],
        "derived": {
            "fixed_selector_control_calls": "compound_control_legacy.pure_selector_control_calls",
            "pure_selector_calls": "raw_selector_scene_order_calls+raw_selector_control_calls+fixed_selector_scene_order_calls+fixed_selector_control_calls+isolated_raw_selector_calls+isolated_fixed_selector_calls",
            "total_worker_starts": "persistent_worker_starts+transient_worker_starts",
        },
        "legacy_adapter": {
            "field_map": {
                "candidate_builder_calls": "candidate_builder_calls", "compiler_calls": "compiler_calls",
                "compiled_programs": "compiled_programs", "completed_planning_snapshots": "completed_planning_snapshots",
                "controller_calls": "controller_calls", "controller_snapshot_replays": "controller_snapshot_replays",
                "environment_actions": "environment_actions", "generated_tokens": "generated_tokens",
                "grounding_evaluations": "grounding_evaluations", "gpu_operations": "gpu_operations",
                "hypothesis_pool_constructions": "hypothesis_pool_constructions", "lockbox_bytes_read": "lockbox_bytes_read",
                "lockbox_path_operations": "lockbox_path_operations", "model_calls": "model_calls",
                "network_calls": "network_calls", "persistent_worker_starts": "persistent_worker_starts",
                "planner_calls": "planner_calls", "pure_selector_control_calls": "raw_selector_control_calls",
                "pure_selector_scene_order_calls": "raw_selector_scene_order_calls",
                "registered_scenes_read": "registered_scene_file_reads", "reward_observations": "reward_observations",
                "rhae_observations": "rhae_observations", "transient_worker_starts": "transient_worker_starts",
                "v4_counterfactual_calls": "v4_counterfactual_calls",
            },
            "ignored_fields": ["pure_selector_calls", "total_worker_starts"],
            "required_equations": [
                "legacy.pure_selector_calls=legacy.pure_selector_scene_order_calls+legacy.pure_selector_control_calls",
                "legacy.total_worker_starts=legacy.persistent_worker_starts+legacy.transient_worker_starts",
            ],
            "copy_policy": "copy_each_mapped_legacy_final_value_once_after_all_borrowed_calls",
            "v7_owned": ["fixed_selector_scene_order_calls", "isolated_fixed_selector_calls", "isolated_raw_selector_calls", "public_scene_generations"],
            "compound_control_adapter": {
                "counter_state": "fresh_isolated",
                "required_equal": {"pure_selector_calls": 19, "pure_selector_control_calls": 19, "pure_selector_scene_order_calls": 0},
                "required_zero": "all_other_AUDIT_RESOURCE_COUNTER_FIELDS",
                "destination": "fixed_selector_control_calls", "copy_policy": "copy_once",
            },
        },
        "zero_forbidden": ["environment_actions", "generated_tokens", "gpu_operations", "lockbox_bytes_read", "lockbox_path_operations", "model_calls", "network_calls", "reward_observations", "rhae_observations"],
    }
    classes = [
        *cast(list[str], increment["before_attempt"]),
        *cast(list[str], increment["after_success"]),
        *cast(list[str], increment["on_observation"]),
        *cast(dict[str, str], increment["derived"]).keys(),
    ]
    if len(classes) != len(set(classes)) or set(classes) != set(_expected_counts()):
        raise RegistrationError("increment contract is not an exact counter partition")
    return {
        "expected_counts": _expected_counts(), "control_call_ledger": ledger,
        "control_contract_sha256": CONTROL_CONTRACT_SHA256, "increment_contract": increment,
    }


def _execution_contract() -> dict[str, object]:
    execution_root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open"
    a_root = f"{execution_root}/process-a"
    b_root = f"{execution_root}/process-b"
    a_output = f"{execution_root}/process-a-output/open/action_qbc_v7_open_diagnostic.json"
    b_output = f"{execution_root}/process-b-output/open/action_qbc_v7_open_diagnostic.json"
    producer = ["uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B", "scripts/build_action_qbc_v7_open_registration.py", "--repository-root", ".", "--preregistration-tag", PREREGISTRATION_TAG, "--output", OUTPUT_PATH]
    reconstructor = ["uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B", "scripts/reconstruct_action_qbc_v7_open_registration.py", "--repository-root", ".", "--registration", OUTPUT_PATH]
    tag_step = {
        "argv": ["git", "ls-remote", "--tags", "https://github.com/bansarinejad/arc3-crosslevel-voi.git", f"refs/tags/{OPEN_FREEZE_TAG}"],
        "cwd": "/var/tmp", "expected_exit_code": 0,
        "expected_stdout": f"<O_COMMIT>\trefs/tags/{OPEN_FREEZE_TAG}\n",
    }
    setup = [
        {"argv": ["/usr/bin/test", "!", "-e", execution_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["install", "-d", "-m", "700", execution_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "clone", "--branch", OPEN_FREEZE_TAG, "--single-branch", "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi", a_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "clone", "--branch", OPEN_FREEZE_TAG, "--single-branch", "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi", b_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "-C", a_root, "rev-parse", "HEAD"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": "<O_COMMIT>\n"},
        {"argv": ["git", "-C", b_root, "rev-parse", "HEAD"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": "<O_COMMIT>\n"},
        {"argv": ["install", "-d", "-m", "700", f"{execution_root}/process-a-output/open"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["install", "-d", "-m", "700", f"{execution_root}/process-b-output/open"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
    ]
    environment = ["/usr/bin/env", "UV_OFFLINE=1", "uv", "sync", "--python", "3.12.13", "--frozen", "--no-dev", "--offline"]
    preflight = [
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        ["git", "rev-parse", "HEAD"], [".venv/bin/python3", "--version"],
        ["uv", "--version"],
        [".venv/bin/python3", "-I", "-B", "scripts/reconstruct_action_qbc_v7_open_registration.py", "--repository-root", ".", "--registration", OUTPUT_PATH],
    ]
    scientific = ["/usr/bin/timeout", "--foreground", "--signal=TERM", "--kill-after=15s", "2700s", ".venv/bin/python3", "-I", "-B", "scripts/run_action_qbc_v7_open_diagnostic.py", "--repository-root", ".", "--registration", OUTPUT_PATH, "--compute-deadline-seconds", "2100", "--wall-time-seconds", "2400", "--output", "<OUTPUT_PATH>"]
    tests = [
        ["uv", "run", "--frozen", "--extra", "dev", "pytest", "-q", "tests/test_action_qbc_v7_audit.py", "tests/test_action_qbc_v7_registration.py"],
        ["uv", "run", "--frozen", "--extra", "dev", "ruff", "check", "src/arc3_voi/action_qbc_v7_reference.py", "src/arc3_voi/action_qbc_v7_audit.py", "scripts/build_action_qbc_v7_open_registration.py", "scripts/finalize_action_qbc_v7_open_diagnostic.py", "scripts/reconstruct_action_qbc_v7_open_registration.py", "scripts/run_action_qbc_v7_open_diagnostic.py", "tests/test_action_qbc_v7_audit.py", "tests/test_action_qbc_v7_registration.py"],
        ["uv", "run", "--frozen", "--extra", "dev", "mypy", "src/arc3_voi/action_qbc_v7_reference.py", "src/arc3_voi/action_qbc_v7_audit.py"],
    ]
    finalizer = ["/usr/bin/python3", "-I", "-B", "scripts/finalize_action_qbc_v7_open_diagnostic.py", "--repository-root", ".", "--registration", OUTPUT_PATH, "--process-a", a_output, "--process-b", b_output, "--process-a-exit-code", "<A_EXIT_CODE>", "--process-b-exit-code", "<B_EXIT_CODE_OR_NULL>", "--lifecycle-stage", "<STAGE_OR_NULL>", "--publish", "artifacts/action_qbc_v7_open_diagnostic.json", "--receipt", "artifacts/action_qbc_v7_open_diagnostic_receipt.json", "--administrative-terminal", "artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"]
    hashes = {
        "producer": canonical_sha256(producer), "reconstructor": canonical_sha256(reconstructor),
        "tag_verification": canonical_sha256(tag_step), "setup": canonical_sha256(setup),
        "environment_build": canonical_sha256(environment), "preflight": canonical_sha256(preflight),
        "scientific": canonical_sha256(scientific), "tests": canonical_sha256(tests),
        "finalizer": canonical_sha256(finalizer),
    }
    return {
        "compute_deadline_seconds": 2100, "wall_time_seconds": 2400,
        "hard_timeout_seconds": 2700, "registered_start_count": 2,
        "process_labels": ["A", "B"], "execution_root": execution_root,
        "process_a_root": a_root, "process_b_root": b_root,
        "process_a_output": a_output, "process_b_output": b_output,
        "producer_argv": producer, "reconstructor_argv": reconstructor,
        "tag_verification_step": tag_step, "setup_steps": setup,
        "environment_build_argv": environment, "preflight_argvs": preflight,
        "scientific_argv_template": scientific, "test_argvs": tests,
        "finalizer_argv_template": finalizer,
        "finalizer_cwd": "/mnt/d/kaggle competitions/arc3-crosslevel-voi",
        "argv_hashes": hashes, "administrative_stage_order": list(ADMINISTRATIVE_STAGES),
        "third_start_allowed": False,
    }


def build_registration(
    repository_root: str | Path,
    preregistration_tag: str = PREREGISTRATION_TAG,
) -> dict[str, object]:
    """Reconstruct the complete zero-result registration in memory."""

    root = Path(repository_root).resolve(strict=True)
    preregistration_commit = _resolve_preregistration(root, preregistration_tag)
    _verify_repository_delta(root, preregistration_commit)
    if action_qbc_policy_sha256() != RAW_POLICY_SHA256:
        raise RegistrationError("raw selector source bundle identity drifted")
    if preregistered_control_contract_sha256() != CONTROL_CONTRACT_SHA256:
        raise RegistrationError("control fixture contract identity drifted")
    prereg_tree = _preregistration_manifest(root, preregistration_commit)
    added = _added_manifest(root)
    document = next(
        (row for row in prereg_tree if row["path"] == PREREGISTRATION_DOCUMENT), None
    )
    if document is None:
        raise RegistrationError("preregistration document is absent from P")
    source_manifest = {
        "preregistration_tree": prereg_tree,
        "open_freeze_added_files": added,
    }
    source_manifest["manifest_sha256"] = canonical_sha256(source_manifest)
    scene_inventory, _generated = _scene_inventory()
    transforms, row_inventory = _transforms_and_rows(scene_inventory)
    without_content: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "treatment_id": TREATMENT_ID,
        "diagnostic_system_id": DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": COMPARISON_SEMANTICS_ID,
        "runtime_id": None,
        "preregistration": {
            "commit_sha": preregistration_commit, "tag": preregistration_tag,
            "document_path": PREREGISTRATION_DOCUMENT,
            "document_git_blob_sha1": document["git_blob_sha1"],
            "document_sha256": document["sha256"],
        },
        "v6_negative": _verify_v6_anchors(root),
        "platform": {
            "python_version": "3.12.13", "python_implementation": "CPython",
            "platform_system": "Linux", "platform_machine": "x86_64", "uv_version": "0.11.28",
        },
        "dependencies": [
            {"name": "arc3-crosslevel-voi", "version": "0.1.0", "editable": True},
            {"name": "numpy", "version": "2.5.1", "editable": False},
            {"name": "PyYAML", "version": "6.0.3", "editable": False},
        ],
        "source_manifest": source_manifest,
        "scene_inventory": scene_inventory,
        "row_inventory": row_inventory,
        "transform_contracts": transforms,
        "scientific_contract": _scientific_contract(),
        "resource_contract": _resource_contract(),
        "execution_contract": _execution_contract(),
        "authorization": dict(AUTHORIZATION),
    }
    if len(without_content) != 18:
        raise RegistrationError("registration preimage does not have exactly eighteen keys")
    registration = dict(without_content)
    registration["content_sha256"] = canonical_sha256(without_content)
    return registration


def _exclusive_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        with contextlib.suppress(OSError):
            path.unlink()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--preregistration-tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repository_root.resolve(strict=True)
    output = (root / args.output).resolve()
    expected = (root / OUTPUT_PATH).resolve()
    if output != expected:
        raise RegistrationError("registration has one canonical repository output path")
    if output.exists() or output.is_symlink():
        raise RegistrationError("registration output already exists; it is never overwritten")
    registration = build_registration(root, args.preregistration_tag)
    raw = canonical_json_bytes(registration)
    _exclusive_write(output, raw)
    print(
        json.dumps(
            {
                "content_sha256": registration["content_sha256"],
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                "output": OUTPUT_PATH,
                "row_count": 140,
                "status": STATUS,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegistrationError as error:
        print(json.dumps({"error": str(error), "status": "refused"}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from error
