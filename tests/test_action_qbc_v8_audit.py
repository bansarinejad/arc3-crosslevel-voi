from __future__ import annotations

import ast
import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

import arc3_voi.action_qbc_v7_audit as v7_audit
import arc3_voi.action_qbc_v8_audit as audit
from arc3_voi.types import Action, ActionKind

ROOT = Path(__file__).resolve().parents[1]
V7_AUDIT_PATH = ROOT / "src" / "arc3_voi" / "action_qbc_v7_audit.py"
V7_REFERENCE_PATH = ROOT / "src" / "arc3_voi" / "action_qbc_v7_reference.py"
V8_AUDIT_PATH = ROOT / "src" / "arc3_voi" / "action_qbc_v8_audit.py"
P8_DOCUMENT_PATH = (
    ROOT
    / "docs"
    / (
        "experiment_amendment_2026-08-18_"
        "action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
    )
)
V7_REGISTRATION_PATH = ROOT / "artifacts" / "action_qbc_v7_open_registration.json"

P8_COMMIT = "09f9caea346866a1acf35c20e0c9d937096b5ce3"
P8_DOCUMENT_GIT_BLOB_SHA1 = "7c0955a775af89dcfcde4796a9bbb4d470669d10"
P8_DOCUMENT_SHA256 = (
    "cc9d787a64700332a44f543e7a949ee5522c3663b6b0eb54e418840e560cfe6d"
)
V7_AUDIT_GIT_BLOB_SHA1 = "97adf13b9fcb753565a0197ece00ebef13312d5d"
V7_AUDIT_SHA256 = (
    "559db2774e213abd5bec9dd073c6bfae7ccd5fdefedb7dbecbf0f96499cd81cd"
)
V7_REFERENCE_GIT_BLOB_SHA1 = "2d019b3d28524c75fd1657048ca1b67c145f3b97"
V7_REFERENCE_SHA256 = (
    "34b24f96c5de4cad1026aa45ee388cf6dac1ee585ba42474a0a15ae216e46455"
)
V7_REGISTRATION_CONTENT_SHA256 = (
    "b09f9ee3b778222afd474645e64512ddc5abc3b6b326a2af9619ee016452a825"
)
V7_REGISTRATION_FILE_SHA256 = (
    "69520f0aa1eeb8ee38e744669a66e443c3e0637e4448200331f9ae6099ae499f"
)
V8_AUDIT_GIT_BLOB_SHA1 = "002f262ad23589647384bf73491094b80ca35cf4"
V8_AUDIT_SHA256 = (
    "59a6b2485fe5dc0293b483d98e0cbdc219fb7a07fb17e2ef8bd8bc8543424a47"
)
V8_AUDIT_BYTE_COUNT = 180_246

REPLACEMENTS: tuple[tuple[bytes, bytes, int], ...] = (
    (
        b"prereg-action-qbc-v7-open-failure-decomposition-v1",
        b"prereg-action-qbc-v8-open-bounded-remote-verification-v5",
        1,
    ),
    (
        b"action-qbc-v7-open-failure-decomposition-v1",
        b"action-qbc-v8-open-failure-decomposition-bounded-verification-v1",
        1,
    ),
    (
        b"crosslevel-voi-open-diagnostic-v7",
        b"crosslevel-voi-open-diagnostic-v8",
        1,
    ),
    (
        b"action-qbc-v7-boundary-compound-selector-decomposition-v1",
        b"action-qbc-v8-v7-mathematics-identity-replication-v1",
        1,
    ),
    (
        b"action-qbc-v7-open-registration-v1",
        b"action-qbc-v8-open-registration-v1",
        1,
    ),
    (
        b"action-qbc-v7-open-diagnostic-payload-v1",
        b"action-qbc-v8-open-diagnostic-payload-v1",
        1,
    ),
    (
        b"action-qbc-v7-open-diagnostic-freeze-v1",
        b"action-qbc-v8-open-diagnostic-freeze-v2",
        1,
    ),
    (
        b"f4a267757a7abbd72bc1aeb86e98811c521bf574",
        P8_COMMIT.encode("ascii"),
        1,
    ),
    (
        b"docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md",
        (
            b"docs/experiment_amendment_2026-08-18_"
            b"action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
        ),
        1,
    ),
    (
        b"fcd284ce499983fcc953f54a9f833e1b6d80a822384768f75cb18948d627a1a7",
        P8_DOCUMENT_SHA256.encode("ascii"),
        1,
    ),
    (
        b"artifacts/action_qbc_v7_open_registration.json",
        b"artifacts/action_qbc_v8_open_registration.json",
        4,
    ),
    (b"runtime_v7_enabled", b"runtime_v8_enabled", 1),
)

O8V1_TO_O8V2_ADMINISTRATIVE_REPLACEMENTS: tuple[tuple[bytes, bytes, int], ...] = (
    (
        b"prereg-action-qbc-v8-open-bounded-remote-verification-v4",
        b"prereg-action-qbc-v8-open-bounded-remote-verification-v5",
        1,
    ),
    (
        b"action-qbc-v8-open-diagnostic-freeze-v1",
        b"action-qbc-v8-open-diagnostic-freeze-v2",
        1,
    ),
    (
        b"e0bff9ffc185196cafa938c8f7c9a7186366258b",
        P8_COMMIT.encode("ascii"),
        1,
    ),
    (
        (
            b"docs/experiment_amendment_2026-08-11_"
            b"action_qbc_v8_open_bounded_remote_verification_v4_correction.md"
        ),
        (
            b"docs/experiment_amendment_2026-08-18_"
            b"action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
        ),
        1,
    ),
    (
        b"31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1",
        P8_DOCUMENT_SHA256.encode("ascii"),
        1,
    ),
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_blob_sha1(value: bytes) -> str:
    header = f"blob {len(value)}\0".encode("ascii")
    return hashlib.sha1(header + value, usedforsecurity=False).hexdigest()


def _apply_forward(source: bytes) -> bytes:
    transformed = source
    for old, new, expected_count in REPLACEMENTS:
        assert transformed.count(old) == expected_count
        transformed = transformed.replace(old, new)
    return transformed


def _apply_reverse(source: bytes) -> bytes:
    reversed_source = source
    for old, new, expected_count in reversed(REPLACEMENTS):
        assert reversed_source.count(new) == expected_count
        reversed_source = reversed_source.replace(new, old)
    return reversed_source


def _assert_exact_transformation(candidate: bytes) -> None:
    assert candidate == _apply_forward(V7_AUDIT_PATH.read_bytes())


def _function_inventory(tree: ast.AST) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (type(node).__name__, node.name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    )


def _fallback_registration() -> dict[str, Any]:
    kinds = (
        ("base_scene", 12),
        ("visual_transform", 48),
        ("order_transform", 60),
        ("control", 20),
    )
    rows: list[dict[str, Any]] = []
    for kind, count in kinds:
        for _ in range(count):
            index = len(rows)
            rows.append(
                {
                    "row_index": index,
                    "row_id": f"{kind}:{index}",
                    "kind": kind,
                    "registered_placeholder": True,
                }
            )
    return {"row_inventory": {"count": 140, "rows": rows}}


def _stub_payload_prefix(
    _registration: Mapping[str, Any],
    _repository_root: Any,
    counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": audit.SCIENTIFIC_SCHEMA_VERSION,
        "treatment_id": audit.TREATMENT_ID,
        "diagnostic_system_id": audit.DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": audit.COMPARISON_SEMANTICS_ID,
        "runtime_id": None,
        "preregistration_identity": {},
        "v6_negative_identity": {},
        "registration_identity": {},
        "execution_identity": {},
        "resource_counters": dict(counters),
    }


def test_frozen_input_p8_and_generated_module_anchors() -> None:
    v7_source = V7_AUDIT_PATH.read_bytes()
    reference_source = V7_REFERENCE_PATH.read_bytes()
    p8_document = P8_DOCUMENT_PATH.read_bytes()
    v8_source = V8_AUDIT_PATH.read_bytes()

    assert _git_blob_sha1(v7_source) == V7_AUDIT_GIT_BLOB_SHA1
    assert _sha256(v7_source) == V7_AUDIT_SHA256
    assert _git_blob_sha1(reference_source) == V7_REFERENCE_GIT_BLOB_SHA1
    assert _sha256(reference_source) == V7_REFERENCE_SHA256
    assert _git_blob_sha1(p8_document) == P8_DOCUMENT_GIT_BLOB_SHA1
    assert _sha256(p8_document) == P8_DOCUMENT_SHA256
    assert len(v8_source) == V8_AUDIT_BYTE_COUNT
    assert _git_blob_sha1(v8_source) == V8_AUDIT_GIT_BLOB_SHA1
    assert _sha256(v8_source) == V8_AUDIT_SHA256

    registration_bytes = V7_REGISTRATION_PATH.read_bytes()
    registration = json.loads(registration_bytes)
    assert _sha256(registration_bytes) == V7_REGISTRATION_FILE_SHA256
    assert registration["content_sha256"] == V7_REGISTRATION_CONTENT_SHA256


def test_section_4_ordered_transformation_and_reverse_are_byte_exact() -> None:
    v7_source = V7_AUDIT_PATH.read_bytes()
    v8_source = V8_AUDIT_PATH.read_bytes()

    assert _apply_forward(v7_source) == v8_source
    assert _apply_reverse(v8_source) == v7_source

    forward = v7_source
    for old, new, expected_count in REPLACEMENTS:
        assert forward.count(old) == expected_count
        forward = forward.replace(old, new)
    assert forward == v8_source

    reverse = v8_source
    for old, new, expected_count in reversed(REPLACEMENTS):
        assert reverse.count(new) == expected_count
        reverse = reverse.replace(new, old)
    assert reverse == v7_source


def test_o8v1_to_o8v2_audit_delta_is_exactly_five_administrative_replacements() -> None:
    current = V8_AUDIT_PATH.read_bytes()
    historical = current
    for old, new, expected_count in reversed(O8V1_TO_O8V2_ADMINISTRATIVE_REPLACEMENTS):
        assert historical.count(new) == expected_count
        historical = historical.replace(new, old)
    assert len(historical) == 180_230
    assert _sha256(historical) == (
        "130dcc271799f035b571e30cc41304c2c3046ddf866eb80b3bbe4b0428c21444"
    )
    replay = historical
    for old, new, expected_count in O8V1_TO_O8V2_ADMINISTRATIVE_REPLACEMENTS:
        assert replay.count(old) == expected_count
        replay = replay.replace(old, new)
    assert replay == current


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: b"#" + value,
        lambda value: value[:-1],
        lambda value: value[: len(value) // 2] + b" " + value[len(value) // 2 + 1 :],
        lambda value: value + b"\n",
    ),
)
def test_exact_transformation_rejects_every_extra_byte_change(
    mutation: Callable[[bytes], bytes],
) -> None:
    with pytest.raises(AssertionError):
        _assert_exact_transformation(mutation(V8_AUDIT_PATH.read_bytes()))


def test_reverse_ast_and_complete_function_inventory_equal_o7() -> None:
    v7_source = V7_AUDIT_PATH.read_bytes()
    reversed_v8 = _apply_reverse(V8_AUDIT_PATH.read_bytes())
    v7_tree = ast.parse(v7_source, filename=str(V7_AUDIT_PATH))
    v8_tree = ast.parse(reversed_v8, filename=str(V8_AUDIT_PATH))

    assert ast.dump(v8_tree, include_attributes=True) == ast.dump(
        v7_tree, include_attributes=True
    )
    assert _function_inventory(v8_tree) == _function_inventory(v7_tree)


def test_v8_identity_constants_are_truthful_and_scientific_names_stay_frozen() -> None:
    assert audit.PREREGISTRATION_TAG == (
        "prereg-action-qbc-v8-open-bounded-remote-verification-v5"
    )
    assert audit.TREATMENT_ID == (
        "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
    )
    assert audit.DIAGNOSTIC_SYSTEM_ID == "crosslevel-voi-open-diagnostic-v8"
    assert audit.COMPARISON_SEMANTICS_ID == (
        "action-qbc-v8-v7-mathematics-identity-replication-v1"
    )
    assert audit.REGISTRATION_SCHEMA_VERSION == "action-qbc-v8-open-registration-v1"
    assert audit.SCIENTIFIC_SCHEMA_VERSION == (
        "action-qbc-v8-open-diagnostic-payload-v1"
    )
    assert audit.OPEN_FREEZE_TAG == "action-qbc-v8-open-diagnostic-freeze-v2"
    assert audit.PREREGISTRATION_COMMIT == P8_COMMIT
    assert audit.PREREGISTRATION_DOCUMENT_SHA256 == P8_DOCUMENT_SHA256
    assert P8_DOCUMENT_PATH.relative_to(ROOT).as_posix() == audit.PREREGISTRATION_DOCUMENT
    assert audit.AUTHORIZATION == {
        "lockbox_generation_authorized": False,
        "sealed_execution_authorized": False,
        "runtime_admission_authorized": False,
        "runtime_v8_enabled": False,
        "final_admission_claimed": False,
    }

    assert audit.GRID_EVIDENCE_SCHEMA_VERSION == v7_audit.GRID_EVIDENCE_SCHEMA_VERSION
    assert audit.EXTERIOR_SUPPORT_SCHEMA_VERSION == (
        v7_audit.EXTERIOR_SUPPORT_SCHEMA_VERSION
    )
    assert audit.COMPOUND_SELECTOR_VERSION == v7_audit.COMPOUND_SELECTOR_VERSION
    assert audit.V7AuditError.__name__ == "V7AuditError"
    assert audit._reference.__name__ == "arc3_voi.action_qbc_v7_reference"
    assert audit.__all__ == v7_audit.__all__


def test_scientific_contract_vectors_and_pure_helpers_equal_v7() -> None:
    for name in (
        "ABSOLUTE_TOLERANCE",
        "RELATIVE_TOLERANCE",
        "FIXED_QUANTUM_NUMERATOR",
        "FIXED_QUANTUM_DENOMINATOR",
        "PAYLOAD_CAP_BYTES",
        "COMPUTE_DEADLINE_SECONDS",
        "WALL_TIME_SECONDS",
        "HARD_TIMEOUT_SECONDS",
        "ROLE_ORDER",
        "SCENE_FAMILIES",
        "VISUAL_TRANSFORMS",
        "ORDER_TRANSFORMS",
        "CONTROL_IDS",
        "REASON_ORDER",
        "GLOBAL_FALLBACK_STAGE_ORDER",
        "AGGREGATE_KEYS",
        "RESOURCE_COUNTER_NAMES",
        "EXPECTED_RESOURCE_COUNTS",
        "FORBIDDEN_RESOURCE_COUNTERS",
        "TOP_LEVEL_KEYS",
    ):
        assert getattr(audit, name) == getattr(v7_audit, name)

    value = {"z": ["caf\u00e9", 1], "a": {"b": False}}
    assert audit.canonical_json_bytes(value) == v7_audit.canonical_json_bytes(value)
    assert audit.canonical_sha256(value) == v7_audit.canonical_sha256(value)
    assert audit.tolerance_record(0.25, 0.25 + 5e-13) == v7_audit.tolerance_record(
        0.25, 0.25 + 5e-13
    )
    assert audit.binary64_equal(0.0, -0.0) is False
    assert audit.ordered_reasons(
        ("fixed_selector_decision_mismatch", "compiler_role_mismatch")
    ) == v7_audit.ordered_reasons(
        ("fixed_selector_decision_mismatch", "compiler_role_mismatch")
    )
    action = Action(ActionKind.ACTION6, row=7, col=11)
    assert audit.action_json(action) == v7_audit.action_json(action)


def test_v8_resource_ledger_is_the_exact_registered_31_field_vector() -> None:
    state = audit.ResourceCounterState()
    derived = {
        "pure_selector_calls",
        "total_worker_starts",
        "fixed_selector_control_calls",
    }
    for name, value in audit.EXPECTED_RESOURCE_COUNTS.items():
        if name not in derived:
            state.increment(name, value)
    state.set_compound_control_calls(
        audit.EXPECTED_RESOURCE_COUNTS["fixed_selector_control_calls"]
    )

    counters = state.snapshot()
    assert len(counters) == 31
    assert counters == dict(audit.EXPECTED_RESOURCE_COUNTS)
    assert audit.validate_resource_counters(counters) == counters
    assert audit.resource_contract_passes(counters)


def test_v8_fallback_payload_has_only_process_invariant_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registration = _fallback_registration()
    monkeypatch.setattr(audit, "_payload_prefix", _stub_payload_prefix)
    monkeypatch.setattr(audit, "_validate_identity_boundary", lambda *_args: None)
    counters = {name: 0 for name in audit.RESOURCE_COUNTER_NAMES}

    payload = audit.build_global_fallback(
        registration,
        "evaluator_internal_error",
        repository_root=tmp_path,
        resource_counters=counters,
    )

    assert tuple(payload) == audit.TOP_LEVEL_KEYS
    assert len(payload) == 19
    assert payload["schema_version"] == audit.SCIENTIFIC_SCHEMA_VERSION
    assert payload["treatment_id"] == audit.TREATMENT_ID
    assert payload["diagnostic_system_id"] == audit.DIAGNOSTIC_SYSTEM_ID
    assert payload["comparison_semantics_id"] == audit.COMPARISON_SEMANTICS_ID
    assert payload["runtime_id"] is None
    assert payload["authorization"] == dict(audit.AUTHORIZATION)
    assert payload["scientific_capability_passes"] is False
    assert len(payload["rows"]) == 140
    assert audit.validate_scientific_payload(payload, registration) == payload

    encoded = audit.canonical_json_bytes(payload)
    for forbidden in (
        b'"label"',
        b'"attempt"',
        b'"output_path"',
        b"process-a-output",
        str(tmp_path).encode(),
    ):
        assert forbidden not in encoded

    true_authorization = copy.deepcopy(payload)
    true_authorization["authorization"]["runtime_v8_enabled"] = True
    with pytest.raises(audit.V7AuditError, match="fixed identity"):
        audit.validate_scientific_payload(true_authorization, registration)

    wrong_key = copy.deepcopy(payload)
    wrong_key["authorization"]["runtime_v7_enabled"] = wrong_key["authorization"].pop(
        "runtime_v8_enabled"
    )
    with pytest.raises(audit.V7AuditError, match="fixed identity"):
        audit.validate_scientific_payload(wrong_key, registration)


def test_v8_fallback_precedence_and_payload_cap_boundary_are_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal = {"normal": True}
    observed: list[tuple[str, int | None]] = []
    monkeypatch.setattr(audit, "_finalize_candidate", lambda *_args: normal)

    def fallback(
        _registration: Mapping[str, Any],
        stage: str,
        *,
        candidate_payload_size_bytes: int | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        observed.append((stage, candidate_payload_size_bytes))
        return {"fallback": stage}

    monkeypatch.setattr(audit, "build_global_fallback", fallback)
    for measured in (audit.PAYLOAD_CAP_BYTES - 1, audit.PAYLOAD_CAP_BYTES):
        assert audit.finalize_scientific_payload(
            {"repository_root": "."}, {}, candidate_payload_size_bytes=measured
        ) is normal
    oversized = audit.PAYLOAD_CAP_BYTES + 1
    assert audit.finalize_scientific_payload(
        {"repository_root": "."}, {}, candidate_payload_size_bytes=oversized
    ) == {"fallback": "payload_size_limit_exceeded"}
    assert observed == [("payload_size_limit_exceeded", oversized)]

    def registered_failure(*_args: Any) -> None:
        raise audit.GlobalFallbackRequired("grid_evidence_table_invalid")

    monkeypatch.setattr(audit, "_finalize_candidate", registered_failure)
    assert audit.finalize_scientific_payload(
        {"repository_root": "."}, {}, candidate_payload_size_bytes=oversized
    ) == {"fallback": "grid_evidence_table_invalid"}
    assert observed[-1] == ("grid_evidence_table_invalid", None)
