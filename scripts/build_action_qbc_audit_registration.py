"""Build and administer the frozen runtime-v5 sealed-audit registration.

This module never resolves, stats, opens, or reads the registered lockbox.  It binds
already-published lockbox identities as inert strings and prepares two external one-shot
start permits only after the registration has been committed at the reviewed tag.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import inspect
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Final, TextIO, cast

from arc3_voi.action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    OUTCOME_CONCENTRATION_THRESHOLD,
    action_qbc_policy_sha256,
)
from arc3_voi.action_qbc_zero_run import (
    REGISTERED_ARM_CONFIG_SHA256,
    REGISTERED_COMPLETION_POLICY_SHA256,
    REGISTERED_COMPLETION_POLICY_VERSION,
    REGISTERED_CONFIG_FILE_SHA256,
    REGISTERED_CONFIG_PATH,
    REGISTERED_MANIFEST_PATH,
    REGISTERED_MANIFEST_SHA256,
    REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD,
    REGISTERED_POLICY_SHA256,
    REGISTERED_POLICY_VERSION,
    REGISTERED_RUNTIME_VERSION,
    serialize_zero_run_registration,
    validate_zero_run_registration,
)
from arc3_voi.action_qbc_zero_run import (
    REGISTRATION_SCHEMA_VERSION as ZERO_RUN_SCHEMA_VERSION,
)
from arc3_voi.run_store import V5_REGISTERED_CONFIG_SHA256_BY_ARM

AUDIT_REGISTRATION_SCHEMA_VERSION: Final = "action-qbc-v5-audit-registration-v1"
AUDIT_REGISTRATION_PATH: Final = Path("artifacts/action_qbc_v5_audit_registration.json")
AUDIT_FREEZE_TAG: Final = "action-qbc-v5-audit-freeze-v1"
PERMIT_SCHEMA_VERSION: Final = "action-qbc-v5-audit-start-permit-v1"
EXPOSURE_SCHEMA_VERSION: Final = "action-qbc-v5-audit-permit-exposure-v1"
LEDGER_SCHEMA_VERSION: Final = "action-qbc-v5-audit-execution-ledger-v2"
PAIR_ATTESTATION_SCHEMA_VERSION: Final = "action-qbc-v5-audit-pair-attestation-v1"
PAIR_POSITIVE_DISPOSITION: Final = "verified-positive-byte-identical-pair"
PAIR_FROZEN_NEGATIVE_DISPOSITION: Final = "frozen-negative-no-third-start"
PERMIT_ISSUANCE_SCHEMA_VERSION: Final = "action-qbc-v5-audit-permit-issuance-v1"
PROMOTION_RECEIPT_SCHEMA_VERSION: Final = "action-qbc-v5-audit-promotion-receipt-v1"
CANONICAL_EXTERNAL_PERMIT_DIRECTORY: Final = Path(
    "/var/tmp/arc3-crosslevel-voi/action-qbc-v5-audit-permits-v1"
)
TRUSTED_ADMIN_INTEGRITY_BOUNDARY: Final = (
    "from common-root creation through receipt validation, one continuously trusted Linux "
    "administrator allows only opaque Git ref advertisement, object transport, and checkout "
    "through the exact registered preflight and two canonical clone commands, which may "
    "mechanically materialize committed bytes without direct path-oriented operator/tool "
    "inspection, stat, independent hashing, search, parsing, execution, or semantic access; "
    "outside that narrow transport exception and the two permit-and-capability-bound starts, "
    "the administrator prevents all registered-lockbox content access; and prevents deletion, "
    "rollback, modification, forgery, replacement, repair, time-of-check/time-of-use swap, "
    "mount or path-namespace substitution, and same-process injection affecting either frozen "
    "worktree; either virtual environment; the base interpreter; uv or Git; registered source, "
    "tag, or configuration; permits or markers; ledger rows; capabilities, attestations, or "
    "launcher proofs; raw outputs or their parent directories; promoted artifacts; or receipts"
)
PROMOTION_STAGING_TEMPORARY_POLICY: Final = (
    "exact registered promotion staging temporaries are non-evidentiary internal "
    "publication state cleaned only by the trusted administrator; operators must not "
    "delete them"
)
SEALED_AUDIT_REPOSITORY_COPY_PATH: Final = Path("artifacts/action_qbc_v5_sealed_audit.json")
SEALED_AUDIT_REPOSITORY_RECEIPT_PATH: Final = Path(
    "artifacts/action_qbc_v5_sealed_audit_receipt.json"
)
SCIENTIFIC_OUTPUT_RELATIVE_PATH: Final = "sealed/action_qbc_v5_scientific_payload.json"
SCIENTIFIC_OUTPUT_ROOT_NAMES: Final[Mapping[str, str]] = {
    "primary": "action-qbc-v5-primary-output",
    "replica": "action-qbc-v5-replica-output",
}
LAUNCHER_DISTRIBUTION_VERSIONS: Final[Mapping[str, str]] = {
    "arc3-crosslevel-voi": "0.1.0",
    "numpy": "2.5.1",
    "pyyaml": "6.0.3",
}
LAUNCHER_UV_VERSION: Final = "0.11.28"
AUDIT_COMMAND_TEMPLATE: Final = (
    "uv",
    "run",
    "--frozen",
    "--no-sync",
    "python3",
    "-I",
    "-B",
    "scripts/audit_action_qbc_lockbox.py",
    "--repository-root",
    ".",
    "--registration",
    AUDIT_REGISTRATION_PATH.as_posix(),
    "--permit-record",
    "<PERMIT_RECORD>",
    "--permit-marker",
    "<AVAILABLE_MARKER>",
    "--output",
    "<OUTPUT_PATH>",
)
REGISTERED_START_LABELS: Final = ("primary", "replica")
LAUNCHER_ATTESTATION_PROOF_KEYS: Final[frozenset[str]] = frozenset(
    {
        "attestation_sha256",
        "capability_issued",
        "code_commit",
        "command_sha256",
        "consumed_permit_sha256",
        "issuance_id",
        "launcher_distribution_versions",
        "launcher_environment_sha256",
        "launcher_uv_version",
        "output_path_sha256",
        "parent_process_id",
        "parent_start_time_ticks",
        "permit_directory_sha256",
        "permit_marker_path_sha256",
        "permit_record_path_sha256",
        "phase",
        "process_id",
        "process_start_time_ticks",
        "read_authorization_consumed",
        "registration_sha256",
        "repository_root_sha256",
        "run_label",
        "source_manifest_sha256",
        "valid",
    }
)
REGISTERED_START_PURPOSES: Final[Mapping[str, str]] = {
    "primary": "fix-scientific-disposition",
    "replica": "verify-byte-identity-only",
}

LOCKBOX_ARTIFACT_RELATIVE_PATH: Final = "artifacts/action_conditional_qbc_v1_lockbox.json"
LOCKBOX_ARTIFACT_SIZE_BYTES: Final = 47_241_363
LOCKBOX_ARTIFACT_SHA256: Final = "d2e84af6527b1dfe686d3113000e0e0b72925c0a8735228da0d3f3c094975953"
LOCKBOX_CONTENT_SHA256: Final = "64ede8fcefaeff061f313d79021ad5188a63170aa63d9d0ab824187860e6760b"
GENERATOR_VERSION: Final = "action-qbc-lockbox-generator-v1"
GENERATOR_CONTRACT_SHA256: Final = (
    "fbaa4663ea3d2b47bc6ec2e2ba1f68b4c717f63f19e6538b270a4c77339a0b74"
)
GENERATOR_SOURCE_COMMIT: Final = "4aae43d2dda05b2b4b9ef2670ef83e3b6a52eb37"
GENERATOR_SOURCE_SHA256: Final = "7b27e1d06ae26e354edd41aaa9e9889ea80a28b0d3a206aeb7158282d067e72a"
GENERATOR_WRAPPER_SHA256: Final = "48cf89a2ee978a1ccc3100daa5ed9d50fd4e8a5680395b5172ef27c2969a89b0"
AMENDMENT_PATH: Final = Path("docs/experiment_amendment_2026-07-13_action_conditional_qbc_v1.md")
AMENDMENT_SHA256: Final = "aba4f9639242922a5be53fecb2e9a1833eec353a84ffc1c1476aad9bad5725ce"
PREREGISTRATION_COMMIT: Final = "1477f8a04ab17adf0bd78b4e98accee3c846aa36"
AMENDMENT_GIT_BLOB_OID: Final = "d1b23227ab44f619c89545e6453946efc3c1c3f9"
PRE_AMENDMENT_HEAD: Final = "15a8200fc898d37772939b9e84c2394c6cbc3ba2"
EMPTY_GIT_OUTPUT_SHA256: Final = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
PROTOCOL_PATH: Final = Path("docs/experiment_protocol.md")
PROTOCOL_SHA256: Final = "46de36c7e0d838ab97c6252776f101f7e9b0dfbcdfc8736e30e0b934daca71e9"

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
SCENE_IDENTITIES: Final = (
    (
        "homologue",
        0,
        "a6eecedee22d2645",
        "26f7cb5b3ce50ab49981455f0f7e45004ceaa463263d09cb0d17df147297cf5c",
    ),
    (
        "homologue",
        1,
        "68620ddc81520133",
        "914ce456ce4f071a8650537fe39332fbe17c078006a909cd26360e8069cab596",
    ),
    (
        "homologue",
        2,
        "e98ab12bef9e01ec",
        "c53e1f83a31df8506c77a7fd3fcb3014738cdeecbc75d3830ff1596b49904a95",
    ),
    (
        "homologue",
        3,
        "3c03b39042f011e4",
        "9bd4d200c2c475ab306b6df86e62255129ca1b85018f2a484c1fae48744561a4",
    ),
    (
        "containment",
        0,
        "550e3657aac91e86",
        "8907e639b690a20baabc650ffc2e24e4688fe3e50b418a9d52675673ba4ee702",
    ),
    (
        "containment",
        1,
        "7fd12591ea73ce88",
        "101016c2c897873b16cca7069f8453b5630f7ce6a499ae12674b661f133ec6a6",
    ),
    (
        "containment",
        2,
        "a957290ff6df8e67",
        "b273835ef0d558099d261462167c26e65d80d5ac84e4032d09d7b9e805161da0",
    ),
    (
        "containment",
        3,
        "9a4897ce5e703365",
        "0cc350ac3d0734f52c6b2cf42d760069cfcbfa1192f52c1746c0b27be0a7237c",
    ),
    (
        "reflection",
        0,
        "bb2215d4d6f787ec",
        "34d4911cca4bbbbdd16468c8244f6c779e15232aebdc57d2d6ee8d2205f257bd",
    ),
    (
        "reflection",
        1,
        "40e8287ce4331712",
        "57cce7ab8c518b70db36369e795333160aee039e2a178562f69ab9848dd9d7b0",
    ),
    (
        "reflection",
        2,
        "ed9659c3935c6429",
        "fac77cdd7243537670ab805e4b71ce9a36c69f4bd6552844da0ed12c4fa0c209",
    ),
    (
        "reflection",
        3,
        "343710325836c643",
        "1b4b3c20020ffd61a20f592fb4e5c2f4728eb3b275afe1eaf7bc1cc12107b3e3",
    ),
)

REGISTERED_SCRIPT_PATHS: Final = (
    "scripts/audit_action_qbc_lockbox.py",
    "scripts/build_action_qbc_audit_registration.py",
    "scripts/build_action_qbc_zero_run_manifest.py",
)
REGISTERED_NON_SOURCE_INPUT_PATHS: Final = (
    "pyproject.toml",
    "uv.lock",
    REGISTERED_CONFIG_PATH.as_posix(),
    REGISTERED_MANIFEST_PATH.as_posix(),
    AMENDMENT_PATH.as_posix(),
    PROTOCOL_PATH.as_posix(),
)
EXPECTED_PACKAGE_SOURCE_COUNT: Final = 39
EXPECTED_FROZEN_FILE_COUNT: Final = 48
EXPECTED_AUDIT_ROW_COUNT: Final = 140


class AuditRegistrationError(RuntimeError):
    """Raised when a registration or external start permit fails closed."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the sole compact registration/permit representation (without LF)."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def registration_payload_sha256(registration: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(registration))).hexdigest()


def _content_identity(registration_without_identity: Mapping[str, object]) -> str:
    return canonical_sha256(dict(registration_without_identity))


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _audit_module() -> ModuleType:
    return importlib.import_module("arc3_voi.action_qbc_audit")


def _lockbox_generator_module() -> ModuleType:
    return importlib.import_module("arc3_voi.action_qbc_lockbox")


def _forbid_lockbox_path(relative: str) -> None:
    if relative == LOCKBOX_ARTIFACT_RELATIVE_PATH:
        raise AuditRegistrationError("registration code must never access the lockbox path")


def _read_repository_file(root: Path, relative: str) -> bytes:
    _forbid_lockbox_path(relative)
    path = Path(relative)
    if (
        path.is_absolute()
        or path.as_posix() != relative
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise AuditRegistrationError(f"noncanonical repository path: {relative!r}")
    target = root / path
    if target.is_symlink() or not target.is_file():
        raise AuditRegistrationError(f"registered input is not a plain file: {relative}")
    return target.read_bytes()


def _file_sha256(root: Path, relative: str) -> str:
    return hashlib.sha256(_read_repository_file(root, relative)).hexdigest()


def _strict_json_object(raw: bytes) -> dict[str, object]:
    def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AuditRegistrationError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise AuditRegistrationError(f"non-finite JSON number: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditRegistrationError("registration is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise AuditRegistrationError("registration must be a JSON object")
    return value


def _load_canonical_object(path: Path) -> tuple[dict[str, object], bytes]:
    if path.is_symlink() or not path.is_file():
        raise AuditRegistrationError(f"expected a plain JSON file: {path}")
    raw = path.read_bytes()
    value = _strict_json_object(raw)
    if canonical_json_bytes(value) != raw:
        raise AuditRegistrationError("JSON bytes are not canonical compact ASCII")
    return value, raw


def _discover_frozen_file_paths(root: Path) -> tuple[str, ...]:
    source_root = root / "src" / "arc3_voi"
    if source_root.is_symlink() or not source_root.is_dir():
        raise AuditRegistrationError("src/arc3_voi must be a plain directory")
    source_paths = tuple(
        sorted(path.relative_to(root).as_posix() for path in source_root.rglob("*.py"))
    )
    if len(source_paths) != EXPECTED_PACKAGE_SOURCE_COUNT:
        raise AuditRegistrationError(
            "package source inventory must contain exactly "
            f"{EXPECTED_PACKAGE_SOURCE_COUNT} files, found {len(source_paths)}"
        )
    paths = tuple(
        sorted(
            (
                *source_paths,
                *REGISTERED_SCRIPT_PATHS,
                *REGISTERED_NON_SOURCE_INPUT_PATHS,
            )
        )
    )
    if len(paths) != EXPECTED_FROZEN_FILE_COUNT or len(set(paths)) != len(paths):
        raise AuditRegistrationError("frozen file inventory is not the reviewed 48-file set")
    return paths


def _frozen_file_inventory(root: Path) -> tuple[list[dict[str, object]], str]:
    rows: list[dict[str, object]] = [
        {"path": relative, "sha256": _file_sha256(root, relative)}
        for relative in _discover_frozen_file_paths(root)
    ]
    return rows, canonical_sha256(rows)


def _require_implementation_identities(root: Path) -> tuple[ModuleType, ModuleType]:
    audit = _audit_module()
    generator = _lockbox_generator_module()
    expected_pairs = (
        (ACTION_QBC_RUNTIME_VERSION, REGISTERED_RUNTIME_VERSION, "runtime version"),
        (ACTION_QBC_POLICY_VERSION, REGISTERED_POLICY_VERSION, "policy version"),
        (ACTION_QBC_POLICY_SHA256, REGISTERED_POLICY_SHA256, "policy SHA-256"),
        (
            OUTCOME_CONCENTRATION_THRESHOLD,
            REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD,
            "outcome concentration threshold",
        ),
        (
            audit.AUDIT_CONFIG_FILE_SHA256,
            REGISTERED_CONFIG_FILE_SHA256,
            "audit config SHA-256",
        ),
        (
            audit.AUDIT_MATRIX_FILE_SHA256,
            REGISTERED_MANIFEST_SHA256,
            "audit matrix SHA-256",
        ),
        (
            audit.ACTION_QBC_POLICY_SHA256,
            REGISTERED_POLICY_SHA256,
            "audit policy SHA-256",
        ),
        (audit.GENERATOR_VERSION, GENERATOR_VERSION, "generator version"),
        (
            audit.GENERATOR_CONTRACT_SHA256,
            GENERATOR_CONTRACT_SHA256,
            "generator contract SHA-256",
        ),
        (
            audit.GENERATOR_SOURCE_COMMIT,
            GENERATOR_SOURCE_COMMIT,
            "generator source commit",
        ),
        (
            audit.GENERATOR_SOURCE_SHA256,
            GENERATOR_SOURCE_SHA256,
            "generator source SHA-256",
        ),
        (
            audit.LOCKBOX_ARTIFACT_RELATIVE_PATH,
            LOCKBOX_ARTIFACT_RELATIVE_PATH,
            "lockbox path string",
        ),
        (
            audit.LOCKBOX_ARTIFACT_SIZE_BYTES,
            LOCKBOX_ARTIFACT_SIZE_BYTES,
            "lockbox size identity",
        ),
        (
            audit.LOCKBOX_ARTIFACT_SHA256,
            LOCKBOX_ARTIFACT_SHA256,
            "lockbox artifact identity",
        ),
        (
            audit.LOCKBOX_CONTENT_SHA256,
            LOCKBOX_CONTENT_SHA256,
            "lockbox content identity",
        ),
        (
            audit.CANDIDATE_POLICY_SHA256,
            audit.CANDIDATE_POLICY_HASH,
            "implemented candidate policy SHA-256",
        ),
        (
            audit.CANDIDATE_POLICY_VERSION,
            audit.IMPLEMENTED_CANDIDATE_POLICY_VERSION,
            "implemented candidate policy version",
        ),
        (
            audit.COMPILER_CONTRACT_SHA256,
            audit.STRUCTURED_PRIOR_CONTRACT_SHA256,
            "implemented compiler contract SHA-256",
        ),
        (
            audit.COMPILER_CONTRACT_VERSION,
            audit.STRUCTURED_PRIOR_CONTRACT_VERSION,
            "implemented compiler contract version",
        ),
        (
            generator.GENERATOR_VERSION,
            GENERATOR_VERSION,
            "implemented generator version",
        ),
        (
            generator.GENERATOR_CONTRACT_SHA256,
            GENERATOR_CONTRACT_SHA256,
            "implemented generator contract",
        ),
        (tuple(generator.FAMILIES), FAMILIES, "generator family order"),
        (
            tuple(generator.VISUAL_TRANSFORM_ORDER),
            VISUAL_TRANSFORMS,
            "visual transform order",
        ),
        (
            tuple(generator.ORDER_TRANSFORM_ORDER),
            ORDER_TRANSFORMS,
            "order transform order",
        ),
    )
    for actual, expected, label in expected_pairs:
        if actual != expected:
            raise AuditRegistrationError(f"{label} differs from the reviewed registration")
    if action_qbc_policy_sha256() != ACTION_QBC_POLICY_SHA256:
        raise AuditRegistrationError("action-QBC implementation source digest drifted")
    if dict(V5_REGISTERED_CONFIG_SHA256_BY_ARM) != dict(REGISTERED_ARM_CONFIG_SHA256):
        raise AuditRegistrationError(
            "run-store v5 arm identities differ from zero-run registration"
        )
    if _file_sha256(root, REGISTERED_CONFIG_PATH.as_posix()) != REGISTERED_CONFIG_FILE_SHA256:
        raise AuditRegistrationError("runtime-v5 configuration bytes drifted")
    if _file_sha256(root, REGISTERED_MANIFEST_PATH.as_posix()) != REGISTERED_MANIFEST_SHA256:
        raise AuditRegistrationError("runtime-v5 zero-run matrix bytes drifted")
    amendment_raw = _read_repository_file(root, AMENDMENT_PATH.as_posix())
    if hashlib.sha256(amendment_raw).hexdigest() != AMENDMENT_SHA256:
        raise AuditRegistrationError("action-QBC amendment bytes drifted")
    git_blob_raw = f"blob {len(amendment_raw)}\0".encode("ascii") + amendment_raw
    if hashlib.sha1(git_blob_raw, usedforsecurity=False).hexdigest() != AMENDMENT_GIT_BLOB_OID:
        raise AuditRegistrationError("action-QBC amendment Git blob identity drifted")
    preregistration_parent = (
        _git(root, "rev-parse", f"{PREREGISTRATION_COMMIT}^").decode("ascii").strip()
    )
    preregistration_blob = (
        _git(
            root,
            "rev-parse",
            f"{PREREGISTRATION_COMMIT}:{AMENDMENT_PATH.as_posix()}",
        )
        .decode("ascii")
        .strip()
    )
    _git(root, "merge-base", "--is-ancestor", PREREGISTRATION_COMMIT, "HEAD")
    if (
        preregistration_parent != PRE_AMENDMENT_HEAD
        or preregistration_blob != AMENDMENT_GIT_BLOB_OID
    ):
        raise AuditRegistrationError("amendment Git ancestry differs from preregistration")
    if _file_sha256(root, "src/arc3_voi/action_qbc_lockbox.py") != GENERATOR_SOURCE_SHA256:
        raise AuditRegistrationError("reviewed generator source bytes drifted")
    if _file_sha256(root, PROTOCOL_PATH.as_posix()) != PROTOCOL_SHA256:
        raise AuditRegistrationError("frozen experiment protocol bytes drifted")
    return audit, generator


def _validate_zero_run(root: Path) -> dict[str, object]:
    raw = _read_repository_file(root, REGISTERED_MANIFEST_PATH.as_posix())
    value = _strict_json_object(raw)
    if hashlib.sha256(raw).hexdigest() != REGISTERED_MANIFEST_SHA256:
        raise AuditRegistrationError("zero-run matrix raw digest differs from registration")
    if serialize_zero_run_registration(value).encode("utf-8") != raw:
        raise AuditRegistrationError("zero-run matrix bytes differ from its canonical format")
    validate_zero_run_registration(value, root)
    runs = value.get("runs")
    if not isinstance(runs, list) or len(runs) != 180:
        raise AuditRegistrationError("zero-run matrix must retain exactly 180 rows")
    return value


def _control_contract(audit: ModuleType) -> tuple[list[dict[str, object]], str, str, int]:
    order = tuple(cast(Sequence[str], audit.PREREGISTERED_CONTROL_ORDER))
    ledger = cast(
        Mapping[str, int],
        audit.PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER,
    )
    helper = audit.preregistered_control_contract_sha256
    evaluator = audit.evaluate_preregistered_controls
    evaluator_helper = audit._evaluate_preregistered_control
    if len(order) != 20 or len(set(order)) != 20 or tuple(ledger) != order:
        raise AuditRegistrationError("audit must expose the exact ordered 20-control ledger")
    if any(type(ledger[name]) is not int or ledger[name] < 0 for name in order):
        raise AuditRegistrationError("control selector call ledger is malformed")
    selector_calls = sum(ledger.values())
    if selector_calls != 19:
        raise AuditRegistrationError("control selector call ledger must total exactly 19")
    evaluator_source_sha256 = hashlib.sha256(
        (inspect.getsource(evaluator_helper) + inspect.getsource(evaluator)).encode("utf-8")
    ).hexdigest()
    contract_sha256 = helper()
    expected_contract = canonical_sha256(
        {
            "control_order": list(order),
            "evaluator_source_sha256": evaluator_source_sha256,
            "schema_version": 1,
            "selector_call_ledger": dict(ledger),
        }
    )
    if contract_sha256 != expected_contract:
        raise AuditRegistrationError("control contract helper differs from its exact inputs")
    rows = []
    for index, control_id in enumerate(order):
        fixture = {
            "control_contract_sha256": contract_sha256,
            "control_id": control_id,
            "control_index": index,
            "evaluator_source_sha256": evaluator_source_sha256,
            "selector_call_count": ledger[control_id],
        }
        rows.append(fixture | {"fixture_sha256": canonical_sha256(fixture)})
    return rows, contract_sha256, evaluator_source_sha256, selector_calls


def _build_row_inventory(
    control_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family, index, seed_hex, scene_sha256 in SCENE_IDENTITIES:
        rows.append(
            {
                "family": family,
                "fixture_sha256": scene_sha256,
                "kind": "base_scene",
                "row_id": f"base:{family}:{index}",
                "scene_index": index,
                "seed_hex": seed_hex,
            }
        )
    for family, index, seed_hex, scene_sha256 in SCENE_IDENTITIES:
        for transform in VISUAL_TRANSFORMS:
            address = {
                "lockbox_content_sha256": LOCKBOX_CONTENT_SHA256,
                "scene_sha256": scene_sha256,
                "transform": transform,
            }
            rows.append(
                {
                    "family": family,
                    "fixture_address_sha256": canonical_sha256(address),
                    "kind": "visual_transform",
                    "row_id": f"visual:{family}:{index}:{transform}",
                    "scene_index": index,
                    "seed_hex": seed_hex,
                    "transform": transform,
                }
            )
    for family, index, seed_hex, scene_sha256 in SCENE_IDENTITIES:
        for transform in ORDER_TRANSFORMS:
            address = {
                "lockbox_content_sha256": LOCKBOX_CONTENT_SHA256,
                "scene_sha256": scene_sha256,
                "transform": transform,
            }
            rows.append(
                {
                    "family": family,
                    "fixture_address_sha256": canonical_sha256(address),
                    "kind": "order_transform",
                    "row_id": f"order:{family}:{index}:{transform}",
                    "scene_index": index,
                    "seed_hex": seed_hex,
                    "transform": transform,
                }
            )
    for control in control_rows:
        rows.append(
            {
                **dict(control),
                "kind": "control",
                "row_id": f"control:{control['control_id']}",
            }
        )
    for row_index, row in enumerate(rows):
        row["row_index"] = row_index
    kind_counts = {
        kind: sum(row["kind"] == kind for row in rows)
        for kind in ("base_scene", "visual_transform", "order_transform", "control")
    }
    if kind_counts != {
        "base_scene": 12,
        "visual_transform": 48,
        "order_transform": 60,
        "control": 20,
    }:
        raise AuditRegistrationError("audit inventory kind counts differ from registration")
    if len(rows) != EXPECTED_AUDIT_ROW_COUNT:
        raise AuditRegistrationError("audit inventory must contain exactly 140 rows")
    if len({cast(str, row["row_id"]) for row in rows}) != len(rows):
        raise AuditRegistrationError("audit row IDs must be unique")
    return rows


def _derive_expected_resource_counts(
    audit: ModuleType,
    rows: Sequence[Mapping[str, object]],
    control_selector_calls: int,
) -> tuple[dict[str, str], dict[str, int], str]:
    inventory = dict(cast(Mapping[str, str], audit.AUDIT_RESOURCE_COUNTER_INVENTORY))
    fields = tuple(sorted(inventory))
    schema_sha256 = canonical_sha256(
        {
            "fields": list(fields),
            "increment_contract": inventory,
            "schema_version": 1,
        }
    )
    if schema_sha256 != audit.AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256:
        raise AuditRegistrationError("resource counter schema helper drifted")
    kind_counts = {
        kind: sum(row["kind"] == kind for row in rows)
        for kind in ("base_scene", "visual_transform", "order_transform")
    }
    scenes = kind_counts["base_scene"]
    pipeline_snapshots = scenes + kind_counts["visual_transform"]
    live_frontier_pipelines = scenes * 4  # base, palette, and two translations
    controller_calls = live_frontier_pipelines * 2  # paired M/X replay
    scene_order_selector_calls = (
        pipeline_snapshots + controller_calls + kind_counts["order_transform"]
    )
    programs = pipeline_snapshots * 4
    derived = {
        "candidate_builder_calls": live_frontier_pipelines,
        "compiler_calls": pipeline_snapshots,
        "compiled_programs": programs,
        "completed_planning_snapshots": pipeline_snapshots,
        "controller_calls": controller_calls,
        "controller_snapshot_replays": controller_calls,
        "environment_actions": 0,
        "generated_tokens": 0,
        "grounding_evaluations": programs,
        "gpu_operations": 0,
        "hypothesis_pool_constructions": pipeline_snapshots,
        "lockbox_bytes_read": LOCKBOX_ARTIFACT_SIZE_BYTES,
        "lockbox_path_operations": 4,
        "model_calls": 0,
        "network_calls": 0,
        "persistent_worker_starts": programs,
        "planner_calls": pipeline_snapshots,
        "pure_selector_calls": scene_order_selector_calls + control_selector_calls,
        "pure_selector_control_calls": control_selector_calls,
        "pure_selector_scene_order_calls": scene_order_selector_calls,
        "registered_scenes_read": scenes,
        "reward_observations": 0,
        "rhae_observations": 0,
        "total_worker_starts": programs * 2,
        "transient_worker_starts": programs,
        "v4_counterfactual_calls": scenes,
    }
    if set(derived) != set(fields):
        raise AuditRegistrationError("derived resource counts do not cover the exact schema")
    implemented = dict(cast(Mapping[str, int], audit.EXPECTED_SEALED_RESOURCE_COUNTS))
    if implemented != derived:
        raise AuditRegistrationError("implemented expected counters differ from row-derived counts")
    return inventory, derived, schema_sha256


def build_audit_registration(repository_root: str | Path) -> dict[str, object]:
    """Build the self-cycle-free registration without accessing the lockbox path."""

    root = Path(repository_root).resolve()
    audit, generator = _require_implementation_identities(root)
    zero_run = _validate_zero_run(root)
    control_rows, control_contract, evaluator_sha256, control_calls = _control_contract(audit)
    rows = _build_row_inventory(control_rows)
    counter_contract, expected_counters, counter_schema_sha256 = _derive_expected_resource_counts(
        audit, rows, control_calls
    )
    frozen_files, source_manifest_sha256 = _frozen_file_inventory(root)
    frozen_paths = tuple(cast(str, row["path"]) for row in frozen_files)
    if {
        SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
        SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix(),
    } & set(frozen_paths):
        raise AuditRegistrationError(
            "post-pair repository outputs cannot be in the pre-run source manifest"
        )
    if tuple(audit.AUDIT_SOURCE_FILE_ORDER) != frozen_paths:
        raise AuditRegistrationError(
            "audit capability source order differs from the sorted 48-file manifest"
        )

    generator_seed_map = cast(Mapping[str, Sequence[str]], generator.REGISTERED_SEED_HEX)
    expected_seed_map = {
        family: [
            seed for row_family, _index, seed, _sha in SCENE_IDENTITIES if row_family == family
        ]
        for family in FAMILIES
    }
    if {key: list(value) for key, value in generator_seed_map.items()} != expected_seed_map:
        raise AuditRegistrationError("generator registered seeds differ from scene inventory")

    zero_runs = cast(list[object], zero_run["runs"])
    body: dict[str, object] = {
        "authorization": {
            "development_matrix_execution_authorized": False,
            "general_runtime_v5_authorized": False,
            "registration_alone_authorizes_sealed_execution": False,
            "sealed_execution_requires_clean_tag_and_external_permit": True,
        },
        "canonical_command_template": list(AUDIT_COMMAND_TEMPLATE),
        "configuration": {
            "arm_config_sha256": dict(REGISTERED_ARM_CONFIG_SHA256),
            "file_sha256": REGISTERED_CONFIG_FILE_SHA256,
            "m_arm_sha256": REGISTERED_ARM_CONFIG_SHA256["M-T"],
            "path": REGISTERED_CONFIG_PATH.as_posix(),
            "x_arm_sha256": REGISTERED_ARM_CONFIG_SHA256["X-T"],
        },
        "controls": {
            "control_contract_sha256": control_contract,
            "evaluator_source_sha256": evaluator_sha256,
            "fixture_count": len(control_rows),
            "fixtures": control_rows,
            "selector_call_count": control_calls,
        },
        "execution_contract": {
            "audit_wall_time_seconds": 1200,
            "byte_identical_scientific_payloads_required": True,
            "canonical_external_permit_directory": (CANONICAL_EXTERNAL_PERMIT_DIRECTORY.as_posix()),
            "clean_isolated_linux_worktrees_required": True,
            "distinct_worktree_roots_frozen_at_issuance": True,
            "issuance_schema_version": PERMIT_ISSUANCE_SCHEMA_VERSION,
            "pair_integrity_separate_from_evaluator_disposition": True,
            "promotion_retry_recovers_exact_payload_only": True,
            "promotion_staging_temporary_policy": PROMOTION_STAGING_TEMPORARY_POLICY,
            "repository_copy_only_after_positive_pair": True,
            "repository_copy_path": SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
            "repository_outputs_absent_at_issuance": True,
            "repository_receipt_path": (SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()),
            "registered_start_count": 2,
            "registered_start_labels": list(REGISTERED_START_LABELS),
            "replica_is_independent_observation": False,
            "scientific_output_relative_path": SCIENTIFIC_OUTPUT_RELATIVE_PATH,
            "third_start_allowed": False,
            "trusted_admin_integrity_boundary": TRUSTED_ADMIN_INTEGRITY_BOUNDARY,
            "trusted_admin_no_delete_or_rollback_boundary": True,
        },
        "frozen_files": {
            "count": len(frozen_files),
            "files": frozen_files,
            "manifest_sha256": source_manifest_sha256,
        },
        "lockbox_identity_without_access": {
            "artifact_path": LOCKBOX_ARTIFACT_RELATIVE_PATH,
            "artifact_sha256": LOCKBOX_ARTIFACT_SHA256,
            "artifact_size_bytes": LOCKBOX_ARTIFACT_SIZE_BYTES,
            "content_sha256": LOCKBOX_CONTENT_SHA256,
            "generator_contract_sha256": GENERATOR_CONTRACT_SHA256,
            "generator_source_commit": GENERATOR_SOURCE_COMMIT,
            "generator_source_sha256": GENERATOR_SOURCE_SHA256,
            "generator_version": GENERATOR_VERSION,
            "generator_wrapper_sha256": GENERATOR_WRAPPER_SHA256,
            "registered_scene_identities": [
                {
                    "family": family,
                    "family_index": index,
                    "scene_content_sha256": scene_sha256,
                    "seed_hex": seed_hex,
                }
                for family, index, seed_hex, scene_sha256 in SCENE_IDENTITIES
            ],
        },
        "preregistration": {
            "amendment_git_blob_oid": AMENDMENT_GIT_BLOB_OID,
            "amendment_path": AMENDMENT_PATH.as_posix(),
            "amendment_sha256": AMENDMENT_SHA256,
            "expected_clean_status_porcelain_sha256": EMPTY_GIT_OUTPUT_SHA256,
            "expected_index_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
            "expected_working_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
            "freeze_tag": AUDIT_FREEZE_TAG,
            "pre_amendment_head": PRE_AMENDMENT_HEAD,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "protocol_path": PROTOCOL_PATH.as_posix(),
            "protocol_sha256": PROTOCOL_SHA256,
        },
        "resource_contract": {
            "expected_counts": expected_counters,
            "increment_contract": counter_contract,
            "schema_sha256": counter_schema_sha256,
        },
        "row_inventory": {
            "count": len(rows),
            "order": "all-base-then-all-visual-then-all-order-then-all-control",
            "rows": rows,
        },
        "schema_version": AUDIT_REGISTRATION_SCHEMA_VERSION,
        "scientific_contract": {
            "audit_contract_version": audit.ACTION_QBC_AUDIT_CONTRACT_VERSION,
            "candidate_policy_sha256": audit.CANDIDATE_POLICY_SHA256,
            "candidate_policy_version": audit.CANDIDATE_POLICY_VERSION,
            "compiler_code_sha256": audit.TOPOLOGY_COMPILER_CODE_SHA256,
            "compiler_contract_sha256": audit.COMPILER_CONTRACT_SHA256,
            "compiler_contract_version": audit.COMPILER_CONTRACT_VERSION,
            "completion_cost_policy_sha256": REGISTERED_COMPLETION_POLICY_SHA256,
            "completion_cost_policy_version": REGISTERED_COMPLETION_POLICY_VERSION,
            "outcome_concentration_threshold": REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD,
            "probe_policy_sha256": REGISTERED_POLICY_SHA256,
            "probe_policy_version": REGISTERED_POLICY_VERSION,
            "runtime_version": REGISTERED_RUNTIME_VERSION,
            "scientific_schema_version": audit.ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION,
        },
        "status": "registered-pre-execution",
        "zero_run_matrix": {
            "execution_count": 0,
            "output_count": 0,
            "path": REGISTERED_MANIFEST_PATH.as_posix(),
            "row_count": len(zero_runs),
            "schema_version": ZERO_RUN_SCHEMA_VERSION,
            "sha256": REGISTERED_MANIFEST_SHA256,
        },
    }
    return body | {"content_sha256": _content_identity(body)}


def validate_audit_registration(
    registration: Mapping[str, object], repository_root: str | Path
) -> None:
    """Strictly reconstruct every byte-addressed field without lockbox access."""

    supplied = dict(registration)
    content_sha256 = supplied.pop("content_sha256", None)
    if not _is_lower_hex(content_sha256, 64):
        raise AuditRegistrationError("registration content identity is malformed")
    if _content_identity(supplied) != content_sha256:
        raise AuditRegistrationError("registration content identity mismatch")
    expected = build_audit_registration(repository_root)
    if dict(registration) != expected:
        raise AuditRegistrationError("registration differs from exact reconstruction")


def load_validated_registration(
    repository_root: str | Path,
    registration_path: str | Path = AUDIT_REGISTRATION_PATH,
) -> tuple[dict[str, object], bytes]:
    root = Path(repository_root).resolve()
    supplied = Path(registration_path)
    if supplied.is_absolute() or supplied.as_posix() != AUDIT_REGISTRATION_PATH.as_posix():
        raise AuditRegistrationError("only the canonical audit registration path is accepted")
    value, raw = _load_canonical_object(root / supplied)
    validate_audit_registration(value, root)
    return value, raw


def _git(root: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ("git", "-c", "core.quotepath=false", *arguments),
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise AuditRegistrationError(
            f"audit registration Git check failed: {' '.join(arguments)}"
        ) from error


def _promotion_staging_pathspecs() -> tuple[str, ...]:
    return tuple(
        f":(exclude,glob){path.parent.as_posix()}/.{path.name}.*.tmp"
        for path in (
            SEALED_AUDIT_REPOSITORY_COPY_PATH,
            SEALED_AUDIT_REPOSITORY_RECEIPT_PATH,
        )
    )


def _clean_tagged_registration_context(
    root: Path, *, allow_promoted_outputs: bool = False
) -> dict[str, str]:
    exclusions = [f":(exclude){LOCKBOX_ARTIFACT_RELATIVE_PATH}"]
    if allow_promoted_outputs:
        exclusions.extend(
            (
                f":(exclude){SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix()}",
                f":(exclude){SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()}",
                *_promotion_staging_pathspecs(),
            )
        )
    pathspec = ("--", ".", *exclusions)
    status = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        *pathspec,
    )
    if status:
        raise AuditRegistrationError("audit permits require a completely clean worktree")
    working_diff = _git(root, "diff", "--no-ext-diff", "--binary", *pathspec)
    index_diff = _git(
        root,
        "diff",
        "--cached",
        "--no-ext-diff",
        "--binary",
        *pathspec,
    )
    git_output_hashes = {
        "clean_status_porcelain_sha256": hashlib.sha256(status).hexdigest(),
        "index_diff_sha256": hashlib.sha256(index_diff).hexdigest(),
        "working_diff_sha256": hashlib.sha256(working_diff).hexdigest(),
    }
    if set(git_output_hashes.values()) != {EMPTY_GIT_OUTPUT_SHA256}:
        raise AuditRegistrationError("audit permits require a completely clean worktree")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tag = _git(root, "rev-parse", f"{AUDIT_FREEZE_TAG}^{{commit}}").decode("ascii").strip()
    if not _is_lower_hex(head, 40) or tag != head:
        raise AuditRegistrationError("clean HEAD is not the frozen audit registration tag")
    registration, raw = load_validated_registration(root)
    committed = _git(root, "show", f"{head}:{AUDIT_REGISTRATION_PATH.as_posix()}")
    if committed != raw:
        raise AuditRegistrationError("registration bytes differ from frozen HEAD")
    frozen_files = cast(Mapping[str, object], registration["frozen_files"])
    return {
        "code_commit": head,
        **git_output_hashes,
        "registration_content_sha256": cast(str, registration["content_sha256"]),
        "registration_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_sha256": cast(str, frozen_files["manifest_sha256"]),
    }


def _fsync_directory(directory: Path) -> None:
    if sys.platform != "linux":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_write(path: Path, raw: bytes) -> None:
    """Durably publish complete bytes without exposing a partial final path."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    linked = False
    durable = False
    try:
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("exclusive write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(temporary, path, follow_symlinks=False)
        linked = True
        _fsync_directory(path.parent)
        durable = True
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            if not (linked and durable):
                raise
        if linked and durable:
            with contextlib.suppress(OSError):
                _fsync_directory(path.parent)


def _remove_registered_promotion_staging_temporaries(repository: Path) -> None:
    """Clean only non-evidentiary temp namespaces while holding the promotion lock."""

    removed = False
    for relative_final in (
        SEALED_AUDIT_REPOSITORY_COPY_PATH,
        SEALED_AUDIT_REPOSITORY_RECEIPT_PATH,
    ):
        final_path = repository / relative_final
        for candidate in final_path.parent.glob(f".{final_path.name}.*.tmp"):
            metadata = candidate.lstat()
            if candidate.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                raise AuditRegistrationError(
                    "registered promotion staging entry is not a plain regular file"
                )
            if sys.platform == "linux" and (
                metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                raise AuditRegistrationError(
                    "registered promotion staging entry has invalid ownership or mode"
                )
            candidate.unlink()
            removed = True
    if removed:
        _fsync_directory(repository / SEALED_AUDIT_REPOSITORY_COPY_PATH.parent)


def _require_repository_promotion_outputs_absent(repository: Path) -> None:
    """Reject every pre-issuance payload/receipt entry, including broken symlinks."""

    for relative_path in (
        SEALED_AUDIT_REPOSITORY_COPY_PATH,
        SEALED_AUDIT_REPOSITORY_RECEIPT_PATH,
    ):
        candidate = repository / relative_path
        if candidate.is_symlink() or os.path.lexists(candidate):
            raise AuditRegistrationError(
                "repository audit payload/receipt must be absent before permit issuance"
            )


def _repository_promotion_output_presence(
    artifact_path: Path,
    receipt_path: Path,
) -> tuple[bool, bool]:
    """Return regular-file presence while rejecting aliases and special entries."""

    for path in (artifact_path, receipt_path):
        if path.is_symlink():
            raise AuditRegistrationError("repository audit outputs cannot be symbolic links")
        if os.path.lexists(path) and not path.is_file():
            raise AuditRegistrationError("repository audit outputs must be absent or regular files")
    return os.path.lexists(artifact_path), os.path.lexists(receipt_path)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _linux_posix_admin_platform_fact() -> bool:
    """Return the immutable production platform fact used by permit administration."""

    return os.name == "posix" and sys.platform == "linux"


def _require_linux_posix_admin_platform() -> None:
    """Fail before caller-supplied path access outside canonical Linux/POSIX."""

    if not _linux_posix_admin_platform_fact():
        raise AuditRegistrationError(
            "external audit permit administration requires Linux/POSIX before path access"
        )


def _require_canonical_permit_directory(path: str | Path) -> Path:
    directory = Path(path).resolve(strict=False)
    canonical = CANONICAL_EXTERNAL_PERMIT_DIRECTORY.resolve(strict=False)
    if directory != canonical:
        raise AuditRegistrationError(
            "permit directory differs from the preregistered absolute singleton"
        )
    return directory


def _registered_scientific_output_paths(
    permit_directory: str | Path,
) -> dict[str, str]:
    directory = _require_canonical_permit_directory(permit_directory)
    common_parent = directory.parent
    return {
        label: str(
            common_parent
            / SCIENTIFIC_OUTPUT_ROOT_NAMES[label]
            / SCIENTIFIC_OUTPUT_RELATIVE_PATH
        )
        for label in REGISTERED_START_LABELS
    }


def _require_registered_output_directories_and_absence(
    permit_directory: Path,
    *,
    labels: Sequence[str],
) -> dict[str, str]:
    """Validate exact output parents and final absence before irreversible consumption."""

    if not labels or any(label not in REGISTERED_START_LABELS for label in labels):
        raise AuditRegistrationError("registered output label inventory is invalid")
    output_paths = _registered_scientific_output_paths(permit_directory)
    directories = {permit_directory.parent}
    for label in labels:
        output_path = Path(output_paths[label])
        directories.update((output_path.parent.parent, output_path.parent))
    for directory in directories:
        if directory.is_symlink() or not os.path.lexists(directory):
            raise AuditRegistrationError("registered output parent is missing or symbolic")
        metadata = directory.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or directory.resolve(strict=True) != directory
        ):
            raise AuditRegistrationError("registered output parent is not a plain directory")
        if sys.platform == "linux" and (
            metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise AuditRegistrationError(
                "registered output parent is not administrator-owned mode-0700"
            )
    for label in labels:
        output_path = Path(output_paths[label])
        if output_path.is_symlink() or os.path.lexists(output_path):
            raise AuditRegistrationError("registered scientific output must be lexically absent")
    return output_paths


def _issuance_id(
    *,
    context: Mapping[str, str],
    scientific_output_paths: Mapping[str, str],
    worktree_roots: Mapping[str, str],
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "canonical_external_permit_directory": str(
                    CANONICAL_EXTERNAL_PERMIT_DIRECTORY.resolve(strict=False)
                ),
                "code_commit": context["code_commit"],
                "registered_start_labels": list(REGISTERED_START_LABELS),
                "registration_sha256": context["registration_sha256"],
                "schema_version": PERMIT_ISSUANCE_SCHEMA_VERSION,
                "scientific_output_paths": dict(scientific_output_paths),
                "source_manifest_sha256": context["source_manifest_sha256"],
                "worktree_roots": dict(worktree_roots),
            }
        )
    ).hexdigest()


def _permit_record(
    *,
    label: str,
    ordinal: int,
    context: Mapping[str, str],
    issuance_id: str,
    scientific_output_paths: Mapping[str, str],
    worktree_roots: Mapping[str, str],
) -> dict[str, object]:
    return {
        "canonical_command_template": list(AUDIT_COMMAND_TEMPLATE),
        "execution_contract": {
            "byte_identical_pair_required": True,
            "canonical_external_permit_directory": str(
                CANONICAL_EXTERNAL_PERMIT_DIRECTORY.resolve(strict=False)
            ),
            "distinct_worktree_roots_required": True,
            "no_replacement_start": True,
            "pair_integrity_separate_from_evaluator_disposition": True,
            "promotion_retry_recovers_exact_payload_only": True,
            "promotion_staging_temporary_policy": PROMOTION_STAGING_TEMPORARY_POLICY,
            "repository_copy_only_after_positive_pair": True,
            "repository_copy_path": SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
            "repository_outputs_absent_at_issuance": True,
            "repository_receipt_path": (SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()),
            "registered_start_count": 2,
            "scientific_output_relative_path": SCIENTIFIC_OUTPUT_RELATIVE_PATH,
            "scientific_output_paths": dict(scientific_output_paths),
            "third_start_allowed": False,
            "trusted_admin_integrity_boundary": TRUSTED_ADMIN_INTEGRITY_BOUNDARY,
            "trusted_admin_no_delete_or_rollback_boundary": True,
        },
        "freeze": {
            "clean_status_porcelain_sha256": context["clean_status_porcelain_sha256"],
            "code_commit": context["code_commit"],
            "index_diff_sha256": context["index_diff_sha256"],
            "tag": AUDIT_FREEZE_TAG,
            "working_diff_sha256": context["working_diff_sha256"],
        },
        "issuance": {
            "canonical_external_permit_directory": str(
                CANONICAL_EXTERNAL_PERMIT_DIRECTORY.resolve(strict=False)
            ),
            "issuance_id": issuance_id,
            "schema_version": PERMIT_ISSUANCE_SCHEMA_VERSION,
            "scientific_output_paths": dict(scientific_output_paths),
            "worktree_roots": dict(worktree_roots),
        },
        "purpose": REGISTERED_START_PURPOSES[label],
        "registration": {
            "content_sha256": context["registration_content_sha256"],
            "path": AUDIT_REGISTRATION_PATH.as_posix(),
            "sha256": context["registration_sha256"],
            "source_manifest_sha256": context["source_manifest_sha256"],
        },
        "run_label": label,
        "run_ordinal": ordinal,
        "schema_version": PERMIT_SCHEMA_VERSION,
        "scientific_output_path": scientific_output_paths[label],
        "worktree_root": worktree_roots[label],
    }


def prepare_external_audit_permits(
    repository_root: str | Path,
    external_directory: str | Path,
    *,
    replica_repository_root: str | Path,
) -> dict[str, object]:
    """Publish exactly two one-shot permits outside the repository, durably and once."""

    _require_linux_posix_admin_platform()
    root = Path(repository_root).resolve()
    replica_root = Path(replica_repository_root).resolve()
    if root == replica_root:
        raise AuditRegistrationError("primary and replica worktree roots must be distinct")
    destination = _require_canonical_permit_directory(external_directory)
    scientific_output_paths = _require_registered_output_directories_and_absence(
        destination,
        labels=REGISTERED_START_LABELS,
    )
    for worktree_root in (root, replica_root):
        if _is_within(destination, worktree_root) or _is_within(worktree_root, destination):
            raise AuditRegistrationError(
                "permit directory must be outside both repository worktrees"
            )
        if any(
            _is_within(Path(output_path), worktree_root)
            or Path(output_path) == worktree_root
            for output_path in scientific_output_paths.values()
        ):
            raise AuditRegistrationError(
                "registered scientific outputs must remain outside both worktrees"
            )
    context = _clean_tagged_registration_context(root)
    replica_context = _clean_tagged_registration_context(replica_root)
    if replica_context != context:
        raise AuditRegistrationError(
            "primary and replica worktrees differ from the same frozen registration"
        )
    for worktree_root in (root, replica_root):
        _require_repository_promotion_outputs_absent(worktree_root)
    worktree_roots = {
        "primary": str(root),
        "replica": str(replica_root),
    }
    issuance_id = _issuance_id(
        context=context,
        scientific_output_paths=scientific_output_paths,
        worktree_roots=worktree_roots,
    )
    destination.parent.mkdir(mode=0o700, parents=False, exist_ok=True)
    _fsync_directory(destination.parent.parent)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    _fsync_directory(destination.parent)
    try:
        permit_hashes: dict[str, str] = {}
        for ordinal, label in enumerate(REGISTERED_START_LABELS, start=1):
            record = _permit_record(
                label=label,
                ordinal=ordinal,
                context=context,
                issuance_id=issuance_id,
                scientific_output_paths=scientific_output_paths,
                worktree_roots=worktree_roots,
            )
            record_raw = canonical_json_bytes(record)
            record_sha256 = hashlib.sha256(record_raw).hexdigest()
            marker = {
                "issuance_id": issuance_id,
                "permit_record_sha256": record_sha256,
                "run_label": label,
                "state": "available",
            }
            _exclusive_write(destination / f"{label}.permit.json", record_raw)
            _exclusive_write(destination / f"{label}.available", canonical_json_bytes(marker))
            permit_hashes[label] = record_sha256
        _fsync_directory(destination)
        exposure = {
            "canonical_external_permit_directory": str(destination),
            "issuance_id": issuance_id,
            "permit_record_sha256": permit_hashes,
            "registered_start_labels": list(REGISTERED_START_LABELS),
            "registration_sha256": context["registration_sha256"],
            "schema_version": EXPOSURE_SCHEMA_VERSION,
            "scientific_output_paths": scientific_output_paths,
            "state": "durably_exposed",
            "promotion_staging_temporary_policy": PROMOTION_STAGING_TEMPORARY_POLICY,
            "trusted_admin_integrity_boundary": TRUSTED_ADMIN_INTEGRITY_BOUNDARY,
            "trusted_admin_no_delete_or_rollback_boundary": True,
            "worktree_roots": worktree_roots,
        }
        _exclusive_write(destination / "audit_runs.exposed.json", canonical_json_bytes(exposure))
        _fsync_directory(destination)
    except BaseException:
        # The new directory was exclusively created by this call.  A partial publication
        # is never usable because the final exposure marker is absent; leave it in place as
        # durable evidence rather than silently recreating permits.
        _fsync_directory(destination)
        raise
    expected_names = {
        "primary.permit.json",
        "primary.available",
        "replica.permit.json",
        "replica.available",
        "audit_runs.exposed.json",
    }
    if {path.name for path in destination.iterdir()} != expected_names:
        raise AuditRegistrationError("external permit publication has unexpected entries")
    return {
        "directory": str(destination),
        "exposure": exposure,
        "issuance_id": issuance_id,
        "registration_sha256": context["registration_sha256"],
        "scientific_output_paths": scientific_output_paths,
    }


def _validate_permit_paths(record_path: Path, marker_path: Path) -> str:
    if record_path.parent != marker_path.parent:
        raise AuditRegistrationError("permit record and marker must share one directory")
    suffix = ".permit.json"
    if not record_path.name.endswith(suffix):
        raise AuditRegistrationError("permit record has a noncanonical name")
    label = record_path.name[: -len(suffix)]
    if label not in REGISTERED_START_LABELS or marker_path.name != f"{label}.available":
        raise AuditRegistrationError("permit record/marker label mismatch")
    return label


@dataclass(frozen=True, slots=True)
class _PermitPublication:
    context: Mapping[str, str]
    directory: Path
    exposure: Mapping[str, object]
    issuance_id: str
    record_raw: Mapping[str, bytes]
    record_sha256: Mapping[str, str]
    records: Mapping[str, Mapping[str, object]]
    scientific_output_paths: Mapping[str, str]
    worktree_roots: Mapping[str, str]


def _validate_permit_publication(
    directory: str | Path,
    *,
    context: Mapping[str, str],
) -> _PermitPublication:
    canonical_directory = _require_canonical_permit_directory(directory)
    exposure, _exposure_raw = _load_canonical_object(
        canonical_directory / "audit_runs.exposed.json"
    )
    roots_value = exposure.get("worktree_roots")
    if not isinstance(roots_value, Mapping) or set(roots_value) != set(REGISTERED_START_LABELS):
        raise AuditRegistrationError("permit exposure worktree roots are malformed")
    worktree_roots: dict[str, str] = {}
    for label in REGISTERED_START_LABELS:
        value = roots_value.get(label)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise AuditRegistrationError("permit worktree root is not canonical absolute")
        resolved = str(Path(value).resolve(strict=False))
        if resolved != value:
            raise AuditRegistrationError("permit worktree root is not resolved")
        worktree_roots[label] = value
    if len(set(worktree_roots.values())) != len(REGISTERED_START_LABELS):
        raise AuditRegistrationError("permit worktree roots are not distinct")
    scientific_output_paths = _registered_scientific_output_paths(canonical_directory)
    if exposure.get("scientific_output_paths") != scientific_output_paths:
        raise AuditRegistrationError("permit exposure scientific output paths are malformed")
    issuance_id = _issuance_id(
        context=context,
        scientific_output_paths=scientific_output_paths,
        worktree_roots=worktree_roots,
    )
    records: dict[str, Mapping[str, object]] = {}
    record_raw: dict[str, bytes] = {}
    record_sha256: dict[str, str] = {}
    for ordinal, label in enumerate(REGISTERED_START_LABELS, start=1):
        record, raw = _load_canonical_object(canonical_directory / f"{label}.permit.json")
        expected_record = _permit_record(
            label=label,
            ordinal=ordinal,
            context=context,
            issuance_id=issuance_id,
            scientific_output_paths=scientific_output_paths,
            worktree_roots=worktree_roots,
        )
        if record != expected_record:
            raise AuditRegistrationError("external permit record identity mismatch")
        records[label] = record
        record_raw[label] = raw
        record_sha256[label] = hashlib.sha256(raw).hexdigest()
    expected_exposure = {
        "canonical_external_permit_directory": str(canonical_directory),
        "issuance_id": issuance_id,
        "permit_record_sha256": record_sha256,
        "registered_start_labels": list(REGISTERED_START_LABELS),
        "registration_sha256": context["registration_sha256"],
        "schema_version": EXPOSURE_SCHEMA_VERSION,
        "scientific_output_paths": scientific_output_paths,
        "state": "durably_exposed",
        "promotion_staging_temporary_policy": PROMOTION_STAGING_TEMPORARY_POLICY,
        "trusted_admin_integrity_boundary": TRUSTED_ADMIN_INTEGRITY_BOUNDARY,
        "trusted_admin_no_delete_or_rollback_boundary": True,
        "worktree_roots": worktree_roots,
    }
    if exposure != expected_exposure:
        raise AuditRegistrationError("durable exposure marker does not bind the issuance")
    return _PermitPublication(
        context=dict(context),
        directory=canonical_directory,
        exposure=exposure,
        issuance_id=issuance_id,
        record_raw=record_raw,
        record_sha256=record_sha256,
        records=records,
        scientific_output_paths=scientific_output_paths,
        worktree_roots=worktree_roots,
    )


def _validate_consumed_marker(
    publication: _PermitPublication,
    label: str,
) -> None:
    if label not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("consumed marker label is not registered")
    if (publication.directory / f"{label}.available").exists():
        raise AuditRegistrationError("consumed permit still has an available marker")
    claim, _claim_raw = _load_canonical_object(publication.directory / f"{label}.consumed")
    if claim != {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "registration_sha256": cast(str, publication.exposure["registration_sha256"]),
        "run_label": label,
        "scientific_output_path": publication.scientific_output_paths[label],
        "state": "consumed",
    }:
        raise AuditRegistrationError("consumed marker does not bind the permit issuance")


def _validate_scientific_exposure_marker(
    publication: _PermitPublication,
    label: str,
) -> bool:
    marker_path = publication.directory / f"{label}.scientific-exposure-started"
    if not marker_path.exists():
        return False
    marker, _marker_raw = _load_canonical_object(marker_path)
    if marker != {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "registration_sha256": publication.context["registration_sha256"],
        "run_label": label,
        "source_manifest_sha256": publication.context["source_manifest_sha256"],
        "state": "scientific_exposure_started",
    }:
        raise AuditRegistrationError("scientific exposure marker does not bind the permit issuance")
    return True


def _validate_lockbox_read_claim_marker(
    publication: _PermitPublication,
    label: str,
) -> bool:
    marker_path = publication.directory / f"{label}.lockbox-read-claimed"
    if not marker_path.exists():
        return False
    marker, _marker_raw = _load_canonical_object(marker_path)
    if marker != {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "registration_sha256": publication.context["registration_sha256"],
        "run_label": label,
        "source_manifest_sha256": publication.context["source_manifest_sha256"],
        "state": "lockbox_read_claimed",
    }:
        raise AuditRegistrationError("lockbox-read claim does not bind the permit issuance")
    return True


def consume_audit_start_permit(
    *,
    repository_root: str | Path,
    permit_record_path: str | Path,
    available_marker_path: str | Path,
    output_path: str | Path,
    expected_code_commit: str,
    expected_registration_sha256: str,
    expected_source_manifest_sha256: str,
) -> dict[str, object]:
    """Permanently consume one O_EXCL marker before any registered-payload access."""

    _require_linux_posix_admin_platform()
    repository = Path(repository_root).resolve()
    record_path = Path(permit_record_path).resolve()
    marker_path = Path(available_marker_path).resolve()
    if _is_within(record_path, repository) or _is_within(marker_path, repository):
        raise AuditRegistrationError("audit permits must remain outside the repository")
    label = _validate_permit_paths(record_path, marker_path)
    context = _clean_tagged_registration_context(repository)
    if (
        context["code_commit"] != expected_code_commit
        or context["registration_sha256"] != expected_registration_sha256
        or context["source_manifest_sha256"] != expected_source_manifest_sha256
    ):
        raise AuditRegistrationError("current worktree differs from expected permit identity")
    publication = _validate_permit_publication(record_path.parent, context=context)
    registered_output = Path(publication.scientific_output_paths[label])
    supplied_output = Path(output_path).resolve(strict=False)
    if (
        record_path != publication.directory / f"{label}.permit.json"
        or marker_path != publication.directory / f"{label}.available"
        or publication.worktree_roots[label] != str(repository)
        or supplied_output != registered_output
    ):
        raise AuditRegistrationError(
            "permit path/worktree/output differs from frozen issuance"
        )
    revalidated_outputs = _require_registered_output_directories_and_absence(
        publication.directory,
        labels=(label,),
    )
    if revalidated_outputs != dict(publication.scientific_output_paths):
        raise AuditRegistrationError("permit scientific output binding changed")
    record = publication.records[label]
    marker, _marker_raw = _load_canonical_object(marker_path)
    if marker != {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "run_label": label,
        "state": "available",
    }:
        raise AuditRegistrationError("available marker does not bind the permit record")
    _require_ledger_state_before_consumption(publication, label)
    claim = {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "registration_sha256": expected_registration_sha256,
        "run_label": label,
        "scientific_output_path": str(registered_output),
        "state": "consumed",
    }
    claim_path = record_path.parent / f"{label}.consumed"
    _exclusive_write(claim_path, canonical_json_bytes(claim))
    _fsync_directory(record_path.parent)
    try:
        marker_path.unlink()
    except OSError as error:
        raise AuditRegistrationError(
            "permit is permanently consumed but available-marker removal failed"
        ) from error
    _fsync_directory(record_path.parent)
    consumed_permit = {
        "code_commit": expected_code_commit,
        "clean_status_porcelain_sha256": EMPTY_GIT_OUTPUT_SHA256,
        "consumed": True,
        "consumed_marker_path": str(claim_path),
        "index_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
        "issuance_id": publication.issuance_id,
        "lockbox_read_claim_marker_path": str(record_path.parent / f"{label}.lockbox-read-claimed"),
        "permit_directory": str(record_path.parent),
        "permit_record_sha256": publication.record_sha256[label],
        "registration_content_sha256": cast(
            str, cast(Mapping[str, object], record["registration"])["content_sha256"]
        ),
        "registration_sha256": expected_registration_sha256,
        "repository_root": str(repository),
        "run_label": label,
        "scientific_output_path": str(registered_output),
        "scientific_output_paths": dict(publication.scientific_output_paths),
        "scientific_exposure_marker_path": str(
            record_path.parent / f"{label}.scientific-exposure-started"
        ),
        "source_manifest_sha256": expected_source_manifest_sha256,
        "worktree_roots": dict(publication.worktree_roots),
        "working_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
    }
    validate_consumed_audit_start_permit(
        consumed_permit,
        expected_code_commit=expected_code_commit,
        expected_repository_root=repository,
        expected_registration_sha256=expected_registration_sha256,
        expected_source_manifest_sha256=expected_source_manifest_sha256,
    )
    return consumed_permit


def validate_consumed_audit_start_permit(
    consumed_permit: Mapping[str, object],
    *,
    expected_code_commit: str,
    expected_repository_root: str | Path,
    expected_registration_sha256: str,
    expected_source_manifest_sha256: str,
) -> None:
    """Revalidate a consumed external permit before sealing an audit capability."""

    _require_linux_posix_admin_platform()
    expected_keys = {
        "code_commit",
        "clean_status_porcelain_sha256",
        "consumed",
        "consumed_marker_path",
        "index_diff_sha256",
        "issuance_id",
        "lockbox_read_claim_marker_path",
        "permit_directory",
        "permit_record_sha256",
        "registration_content_sha256",
        "registration_sha256",
        "repository_root",
        "run_label",
        "scientific_output_path",
        "scientific_output_paths",
        "scientific_exposure_marker_path",
        "source_manifest_sha256",
        "worktree_roots",
        "working_diff_sha256",
    }
    if set(consumed_permit) != expected_keys or consumed_permit.get("consumed") is not True:
        raise AuditRegistrationError("consumed permit mapping is malformed")
    label_value = consumed_permit.get("run_label")
    if not isinstance(label_value, str) or label_value not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("consumed permit label is not registered")
    label = label_value
    repository = Path(expected_repository_root).resolve()
    context = _clean_tagged_registration_context(repository)
    if (
        consumed_permit.get("code_commit") != expected_code_commit
        or consumed_permit.get("registration_sha256") != expected_registration_sha256
        or consumed_permit.get("source_manifest_sha256") != expected_source_manifest_sha256
        or consumed_permit.get("repository_root") != str(repository)
        or consumed_permit.get("clean_status_porcelain_sha256") != EMPTY_GIT_OUTPUT_SHA256
        or consumed_permit.get("index_diff_sha256") != EMPTY_GIT_OUTPUT_SHA256
        or consumed_permit.get("working_diff_sha256") != EMPTY_GIT_OUTPUT_SHA256
        or context["code_commit"] != expected_code_commit
        or context["registration_sha256"] != expected_registration_sha256
        or context["source_manifest_sha256"] != expected_source_manifest_sha256
    ):
        raise AuditRegistrationError("consumed permit frozen identity mismatch")
    if (
        not _is_lower_hex(expected_code_commit, 40)
        or not _is_lower_hex(expected_registration_sha256, 64)
        or not _is_lower_hex(expected_source_manifest_sha256, 64)
        or not _is_lower_hex(consumed_permit.get("registration_content_sha256"), 64)
    ):
        raise AuditRegistrationError("consumed permit frozen identity is malformed")
    directory_value = consumed_permit.get("permit_directory")
    claim_value = consumed_permit.get("consumed_marker_path")
    exposure_value = consumed_permit.get("scientific_exposure_marker_path")
    lockbox_claim_value = consumed_permit.get("lockbox_read_claim_marker_path")
    if not all(
        isinstance(value, str)
        for value in (directory_value, claim_value, exposure_value, lockbox_claim_value)
    ):
        raise AuditRegistrationError("consumed permit paths are malformed")
    directory = Path(cast(str, directory_value)).resolve()
    claim_path = Path(cast(str, claim_value)).resolve()
    scientific_exposure_path = Path(cast(str, exposure_value)).resolve()
    lockbox_claim_path = Path(cast(str, lockbox_claim_value)).resolve()
    if (
        _is_within(directory, repository)
        or directory == repository
        or claim_path != directory / f"{label}.consumed"
        or scientific_exposure_path != directory / f"{label}.scientific-exposure-started"
        or lockbox_claim_path != directory / f"{label}.lockbox-read-claimed"
        or (directory / f"{label}.available").exists()
    ):
        raise AuditRegistrationError("consumed permit path state is invalid")
    publication = _validate_permit_publication(directory, context=context)
    record = publication.records[label]
    if (
        publication.worktree_roots[label] != str(repository)
        or consumed_permit.get("issuance_id") != publication.issuance_id
        or consumed_permit.get("permit_record_sha256") != publication.record_sha256[label]
        or consumed_permit.get("scientific_output_path")
        != publication.scientific_output_paths[label]
        or consumed_permit.get("scientific_output_paths")
        != dict(publication.scientific_output_paths)
        or consumed_permit.get("worktree_roots") != dict(publication.worktree_roots)
        or consumed_permit.get("registration_content_sha256")
        != cast(Mapping[str, object], record["registration"])["content_sha256"]
    ):
        raise AuditRegistrationError("consumed permit differs from frozen issuance")
    _validate_consumed_marker(publication, label)


def mark_scientific_exposure_started(
    consumed_permit: Mapping[str, object],
) -> dict[str, object]:
    """Durably mark first diagnostic exposure; this one-shot marker is never removed."""

    _require_linux_posix_admin_platform()
    label = consumed_permit.get("run_label")
    if consumed_permit.get("consumed") is not True or label not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("scientific exposure requires a verified consumed permit")
    directory_value = consumed_permit.get("permit_directory")
    marker_value = consumed_permit.get("scientific_exposure_marker_path")
    if not isinstance(directory_value, str) or not isinstance(marker_value, str):
        raise AuditRegistrationError("consumed permit paths are malformed")
    directory = Path(directory_value).resolve()
    marker_path = Path(marker_value).resolve()
    expected_marker = directory / f"{label}.scientific-exposure-started"
    if marker_path != expected_marker:
        raise AuditRegistrationError("scientific exposure marker path is noncanonical")
    consumed_path = directory / f"{label}.consumed"
    consumed_record, _raw = _load_canonical_object(consumed_path)
    if consumed_record != {
        "issuance_id": consumed_permit.get("issuance_id"),
        "permit_record_sha256": consumed_permit.get("permit_record_sha256"),
        "registration_sha256": consumed_permit.get("registration_sha256"),
        "run_label": label,
        "scientific_output_path": consumed_permit.get("scientific_output_path"),
        "state": "consumed",
    }:
        raise AuditRegistrationError("consumed-permit marker is invalid")
    exposure = {
        "issuance_id": consumed_permit.get("issuance_id"),
        "permit_record_sha256": consumed_permit.get("permit_record_sha256"),
        "registration_sha256": consumed_permit.get("registration_sha256"),
        "run_label": label,
        "source_manifest_sha256": consumed_permit.get("source_manifest_sha256"),
        "state": "scientific_exposure_started",
    }
    if (
        not _is_lower_hex(exposure["issuance_id"], 64)
        or not _is_lower_hex(exposure["permit_record_sha256"], 64)
        or not _is_lower_hex(exposure["registration_sha256"], 64)
        or not _is_lower_hex(exposure["source_manifest_sha256"], 64)
    ):
        raise AuditRegistrationError("scientific exposure identities are malformed")
    _exclusive_write(marker_path, canonical_json_bytes(exposure))
    _fsync_directory(directory)
    return exposure


def claim_registered_lockbox_read_once(
    consumed_permit: Mapping[str, object],
    *,
    expected_code_commit: str,
    expected_repository_root: str | Path,
    expected_registration_sha256: str,
    expected_source_manifest_sha256: str,
) -> dict[str, object]:
    """Durably consume the one lockbox-read claim bound to this start permit."""

    _require_linux_posix_admin_platform()
    validate_consumed_audit_start_permit(
        consumed_permit,
        expected_code_commit=expected_code_commit,
        expected_repository_root=expected_repository_root,
        expected_registration_sha256=expected_registration_sha256,
        expected_source_manifest_sha256=expected_source_manifest_sha256,
    )
    label = cast(str, consumed_permit["run_label"])
    repository = Path(expected_repository_root).resolve()
    context = _clean_tagged_registration_context(repository)
    publication = _validate_permit_publication(
        cast(str, consumed_permit["permit_directory"]),
        context=context,
    )
    _validate_consumed_marker(publication, label)
    marker_path = Path(cast(str, consumed_permit["lockbox_read_claim_marker_path"])).resolve()
    if marker_path != publication.directory / f"{label}.lockbox-read-claimed":
        raise AuditRegistrationError("lockbox-read claim path is noncanonical")
    claim: dict[str, object] = {
        "issuance_id": publication.issuance_id,
        "permit_record_sha256": publication.record_sha256[label],
        "registration_sha256": context["registration_sha256"],
        "run_label": label,
        "source_manifest_sha256": context["source_manifest_sha256"],
        "state": "lockbox_read_claimed",
    }
    _exclusive_write(marker_path, canonical_json_bytes(claim))
    _fsync_directory(publication.directory)
    if not _validate_lockbox_read_claim_marker(publication, label):
        raise AuditRegistrationError("durable lockbox-read claim publication failed")
    return claim


def realized_audit_command(
    permit_directory: str | Path,
    run_label: str,
    output_path: str | Path,
) -> tuple[str, ...]:
    """Substitute external administration paths into the frozen command template."""

    if run_label not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("command run label is not registered")
    directory = _require_canonical_permit_directory(permit_directory)
    destination = Path(output_path).resolve(strict=False)
    registered_destination = Path(_registered_scientific_output_paths(directory)[run_label])
    if destination != registered_destination:
        raise AuditRegistrationError("output path differs from its registered run label")
    suffix = Path(SCIENTIFIC_OUTPUT_RELATIVE_PATH).parts
    if tuple(destination.parts[-len(suffix) :]) != suffix:
        raise AuditRegistrationError("output path lacks the fixed scientific suffix")
    substitutions = {
        "<AVAILABLE_MARKER>": str(directory / f"{run_label}.available"),
        "<OUTPUT_PATH>": str(destination),
        "<PERMIT_RECORD>": str(directory / f"{run_label}.permit.json"),
    }
    return tuple(substitutions.get(token, token) for token in AUDIT_COMMAND_TEMPLATE)


def require_external_scientific_output_path(
    repository_root: str | Path, output_path: str | Path
) -> Path:
    """Reject in-repository destinations and symlink-resolved escapes."""

    repository = Path(repository_root).resolve(strict=True)
    destination = Path(output_path).resolve(strict=False)
    suffix = Path(SCIENTIFIC_OUTPUT_RELATIVE_PATH).parts
    if tuple(destination.parts[-len(suffix) :]) != suffix:
        raise AuditRegistrationError("output path lacks the fixed scientific suffix")
    if _is_within(destination, repository) or destination == repository:
        raise AuditRegistrationError("scientific output must remain outside the repository")
    if destination.is_symlink():
        raise AuditRegistrationError("scientific output cannot be a symbolic link")
    return destination


@contextlib.contextmanager
def _locked_file(handle: TextIO) -> Iterator[None]:
    if os.name == "nt":
        import msvcrt

        locking = cast(Callable[[int, int, int], object], vars(msvcrt)["locking"])
        lock = cast(int, vars(msvcrt)["LK_LOCK"])
        unlock = cast(int, vars(msvcrt)["LK_UNLCK"])
        handle.seek(0)
        if handle.read(1) == "":
            handle.seek(0)
            handle.write("\0")
        handle.flush()
        os.fsync(handle.fileno())
        handle.seek(0)
        locking(handle.fileno(), lock, 1)
        try:
            yield
        finally:
            handle.seek(0)
            locking(handle.fileno(), unlock, 1)
    else:
        import fcntl

        flock = cast(Callable[[int, int], object], vars(fcntl)["flock"])
        exclusive = cast(int, vars(fcntl)["LOCK_EX"])
        release = cast(int, vars(fcntl)["LOCK_UN"])
        flock(handle.fileno(), exclusive)
        try:
            yield
        finally:
            flock(handle.fileno(), release)


def _inspect_scientific_output(
    output_path: Path, declared_sha256: str | None
) -> tuple[dict[str, object], bytes | None]:
    """Return stable canonical-output evidence without treating failure as rerunnable."""

    evidence: dict[str, object] = {
        "output_complete": False,
        "output_sha256_observed": None,
        "output_size_bytes": None,
    }
    try:
        if output_path.is_symlink() or not output_path.is_file():
            return evidence, None
        before = output_path.stat()
        raw = output_path.read_bytes()
        after = output_path.stat()
    except OSError:
        return evidence, None
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    evidence["output_sha256_observed"] = observed_sha256
    evidence["output_size_bytes"] = len(raw)
    stable = (
        before.st_dev == after.st_dev
        and before.st_ino == after.st_ino
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_size == after.st_size == len(raw)
    )
    canonical = False
    try:
        parsed = _strict_json_object(raw)
        canonical = canonical_json_bytes(parsed) == raw
    except AuditRegistrationError:
        pass
    complete = (
        stable and canonical and declared_sha256 is not None and observed_sha256 == declared_sha256
    )
    evidence["output_complete"] = complete
    return evidence, raw if complete else None


def _expected_scientific_provenance(
    registration: Mapping[str, object],
    context: Mapping[str, str],
) -> dict[str, object]:
    audit = _audit_module()
    expected = dict(cast(Mapping[str, object], audit.EXPECTED_AUDIT_PROVENANCE.as_json()))
    frozen = cast(Mapping[str, object], registration["frozen_files"])
    expected.update(
        {
            "code_commit": context["code_commit"],
            "git_clean_status_sha256": context["clean_status_porcelain_sha256"],
            "git_index_diff_sha256": context["index_diff_sha256"],
            "git_worktree_diff_sha256": context["working_diff_sha256"],
            "registration_sha256": context["registration_sha256"],
            "source_files": frozen["files"],
            "source_manifest_sha256": context["source_manifest_sha256"],
        }
    )
    return expected


def _validate_registered_scientific_payload(
    raw: bytes,
    *,
    registration: Mapping[str, object],
    context: Mapping[str, str],
) -> dict[str, object]:
    """Validate a complete scientific payload against its frozen registration."""

    payload = _strict_json_object(raw)
    expected_keys = {
        "acceptance",
        "canonical_command_template",
        "deterministic_environment",
        "disposition",
        "duplicate_execution_is_independent_evidence",
        "finalization_failures",
        "lockbox_content_sha256",
        "provenance",
        "records",
        "registration_preregistration",
        "registration_sha256",
        "resource_counter_schema_sha256",
        "resource_counters",
        "schema_version",
    }
    if set(payload) != expected_keys:
        raise AuditRegistrationError("scientific payload has a noncanonical top-level schema")
    audit = _audit_module()
    if (
        payload.get("schema_version") != audit.ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION
        or payload.get("registration_sha256") != context["registration_sha256"]
        or payload.get("canonical_command_template") != list(AUDIT_COMMAND_TEMPLATE)
        or payload.get("duplicate_execution_is_independent_evidence") is not False
        or payload.get("resource_counter_schema_sha256")
        != audit.AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256
        or payload.get("provenance") != _expected_scientific_provenance(registration, context)
        or payload.get("registration_preregistration") != registration["preregistration"]
    ):
        raise AuditRegistrationError(
            "scientific payload differs from frozen schema/provenance/registration"
        )
    lockbox = cast(Mapping[str, object], registration["lockbox_identity_without_access"])
    if payload.get("lockbox_content_sha256") != lockbox["content_sha256"]:
        raise AuditRegistrationError("scientific payload lockbox identity mismatch")
    finalization_failures_value = payload.get("finalization_failures")
    if not isinstance(finalization_failures_value, list) or any(
        not isinstance(failure, Mapping)
        or set(failure) != {"error_type", "stage"}
        or not isinstance(failure.get("stage"), str)
        or not cast(str, failure["stage"])
        or (
            failure.get("error_type") is not None and not isinstance(failure.get("error_type"), str)
        )
        for failure in finalization_failures_value
    ):
        raise AuditRegistrationError("scientific finalization failures are malformed")
    finalization_complete = not finalization_failures_value
    environment = payload.get("deterministic_environment")
    environment_keys = {
        "dependency_file_sha256",
        "machine",
        "numpy_version",
        "platform_release",
        "platform_system",
        "python_implementation",
        "python_version",
    }
    if not isinstance(environment, Mapping) or set(environment) != environment_keys:
        raise AuditRegistrationError("scientific environment identity is malformed")
    frozen = cast(Mapping[str, object], registration["frozen_files"])
    source_rows = cast(Sequence[Mapping[str, object]], frozen["files"])
    expected_dependencies = {
        row["path"]: cast(str, row["sha256"])
        for row in source_rows
        if row["path"] in {"pyproject.toml", "uv.lock"}
    }
    if (
        environment.get("dependency_file_sha256") != expected_dependencies
        or environment.get("platform_system") != "Linux"
        or any(
            not isinstance(environment.get(name), str) or not environment.get(name)
            for name in environment_keys - {"dependency_file_sha256"}
        )
    ):
        raise AuditRegistrationError("scientific environment differs from frozen Linux contract")
    records_value = payload.get("records")
    inventory = cast(Mapping[str, object], registration["row_inventory"])
    registration_rows = cast(Sequence[Mapping[str, object]], inventory["rows"])
    if (
        not isinstance(records_value, list)
        or len(records_value) != 140
        or not all(isinstance(record, Mapping) for record in records_value)
    ):
        raise AuditRegistrationError("scientific record inventory is malformed")
    records = [cast(dict[str, object], record) for record in records_value]
    try:
        rederived = audit.validate_and_rederive_scientific_records(
            records,
            registration_rows,
        )
    except Exception as error:
        raise AuditRegistrationError(
            "scientific row evidence fails exact validation/re-derivation"
        ) from error
    if rederived != records:
        raise AuditRegistrationError("scientific records differ from authoritative re-derivation")
    counters_value = payload.get("resource_counters")
    counter_fields = tuple(cast(Sequence[str], audit.AUDIT_RESOURCE_COUNTER_FIELDS))
    if (
        not isinstance(counters_value, Mapping)
        or set(counters_value) != set(counter_fields)
        or any(
            isinstance(counters_value[name], bool)
            or not isinstance(counters_value[name], int)
            or cast(int, counters_value[name]) < 0
            for name in counter_fields
        )
    ):
        raise AuditRegistrationError("scientific resource counters are malformed")
    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, Mapping):
        raise AuditRegistrationError("scientific acceptance mapping is malformed")
    checks = acceptance.get("checks")
    if (
        not isinstance(checks, Mapping)
        or checks.get("scientific_exposure_recorded") is not True
        or not isinstance(checks.get("within_wall_time"), bool)
    ):
        raise AuditRegistrationError("scientific acceptance checks are malformed")
    counter_state = audit.AuditCounterState(
        _values={name: cast(int, counters_value[name]) for name in counter_fields},
        _scientific_exposure_started=True,
    )
    try:
        aggregation_failed = any(
            failure.get("stage") == "acceptance_aggregation_failed"
            for failure in finalization_failures_value
        )
        if aggregation_failed:
            recomputed_acceptance = audit._negative_aggregate_acceptance(
                counter_state,
                within_deadline=cast(bool, checks["within_wall_time"]),
            )
        else:
            recomputed_acceptance = audit._aggregate_acceptance(
                records,
                counter_state,
                finalization_complete=finalization_complete,
                within_deadline=cast(bool, checks["within_wall_time"]),
            )
    except Exception as error:
        raise AuditRegistrationError("scientific acceptance cannot be recomputed") from error
    expected_disposition = (
        "mechanism_capability_pass_pair_attestation_pending"
        if recomputed_acceptance["acceptance_passes"] is True
        else "mechanism_capability_failed_runtime_v5_frozen"
    )
    if acceptance != recomputed_acceptance or payload.get("disposition") != expected_disposition:
        raise AuditRegistrationError("scientific acceptance/disposition is inconsistent")
    return payload


def _validate_pair_party(value: object, recorded_row: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "exit_status",
        "observed_output_complete",
        "observed_output_sha256",
        "observed_output_size_bytes",
        "output_path",
        "payload_sha256",
        "recorded_output_complete",
        "run_label",
    }:
        raise AuditRegistrationError("pair attestation party is malformed")
    if (
        value.get("exit_status") != recorded_row.get("exit_status")
        or value.get("output_path") != recorded_row.get("output_path")
        or value.get("payload_sha256") != recorded_row.get("payload_sha256")
        or value.get("recorded_output_complete") != recorded_row.get("output_complete")
        or value.get("run_label") != recorded_row.get("run_label")
        or not isinstance(value.get("observed_output_complete"), bool)
    ):
        raise AuditRegistrationError("pair attestation party does not bind its ledger row")
    observed_sha256 = value.get("observed_output_sha256")
    observed_size = value.get("observed_output_size_bytes")
    if observed_sha256 is not None and not _is_lower_hex(observed_sha256, 64):
        raise AuditRegistrationError("pair attestation observed SHA-256 is malformed")
    if observed_size is not None and (
        isinstance(observed_size, bool) or not isinstance(observed_size, int) or observed_size < 0
    ):
        raise AuditRegistrationError("pair attestation observed size is malformed")
    if value.get("observed_output_complete") is True and (
        observed_sha256 != value.get("payload_sha256") or observed_size is None
    ):
        raise AuditRegistrationError("complete pair output lacks matching byte evidence")


def _validate_pair_attestation(
    value: object,
    *,
    primary_row: Mapping[str, object],
    replica_row: Mapping[str, object],
) -> None:
    expected_keys = {
        "both_exit_zero",
        "both_outputs_complete",
        "disposition",
        "exact_bytes_equal",
        "payload_sha256_matches",
        "positive_pair_eligible",
        "positive_pair_eligibility_scope",
        "primary",
        "registered_start_count",
        "replica",
        "schema_version",
        "start_allowance_state",
        "third_start_allowed",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise AuditRegistrationError("replica pair attestation is malformed")
    _validate_pair_party(value["primary"], primary_row)
    _validate_pair_party(value["replica"], replica_row)
    primary = cast(Mapping[str, object], value["primary"])
    replica = cast(Mapping[str, object], value["replica"])
    both_exit_zero = primary_row.get("exit_status") == 0 and replica_row.get("exit_status") == 0
    primary_payload_sha256 = primary_row.get("payload_sha256")
    replica_payload_sha256 = replica_row.get("payload_sha256")
    payload_sha256_matches = (
        isinstance(primary_payload_sha256, str)
        and isinstance(replica_payload_sha256, str)
        and primary_payload_sha256 == replica_payload_sha256
    )
    both_outputs_complete = all(
        party.get(field) is True
        for party in (primary, replica)
        for field in ("recorded_output_complete", "observed_output_complete")
    )
    exact_bytes_equal = value.get("exact_bytes_equal")
    if not isinstance(exact_bytes_equal, bool):
        raise AuditRegistrationError("pair byte-equality result is malformed")
    if exact_bytes_equal and not both_outputs_complete:
        raise AuditRegistrationError("pair cannot claim exact byte equality for incomplete outputs")
    positive = (
        both_exit_zero and payload_sha256_matches and both_outputs_complete and exact_bytes_equal
    )
    expected_disposition = (
        PAIR_POSITIVE_DISPOSITION if positive else PAIR_FROZEN_NEGATIVE_DISPOSITION
    )
    if (
        value.get("both_exit_zero") is not both_exit_zero
        or value.get("both_outputs_complete") is not both_outputs_complete
        or value.get("payload_sha256_matches") is not payload_sha256_matches
        or value.get("positive_pair_eligible") is not positive
        or value.get("positive_pair_eligibility_scope") != "pair-integrity-only"
        or value.get("disposition") != expected_disposition
        or value.get("registered_start_count") != 2
        or value.get("schema_version") != PAIR_ATTESTATION_SCHEMA_VERSION
        or value.get("start_allowance_state") != "exhausted-permanently"
        or value.get("third_start_allowed") is not False
    ):
        raise AuditRegistrationError("pair attestation conclusion is inconsistent")


def _validate_launcher_attestation_proof(
    value: object,
    *,
    row: Mapping[str, object],
    directory: Path,
    publication: _PermitPublication,
    exact_command: Sequence[str],
    output_path: Path,
) -> None:
    if not isinstance(value, Mapping) or set(value) != LAUNCHER_ATTESTATION_PROOF_KEYS:
        raise AuditRegistrationError("launcher attestation proof has a noncanonical schema")
    proof = cast(Mapping[str, object], value)
    if proof.get("valid") is not True or proof.get("phase") != "ledger":
        raise AuditRegistrationError("launcher attestation proof is not valid for the ledger")
    if proof.get("launcher_distribution_versions") != dict(
        LAUNCHER_DISTRIBUTION_VERSIONS
    ):
        raise AuditRegistrationError(
            "launcher attestation distribution versions differ from the frozen allowlist"
        )
    if proof.get("launcher_uv_version") != LAUNCHER_UV_VERSION:
        raise AuditRegistrationError("launcher attestation uv version is not frozen")
    for field in ("capability_issued", "read_authorization_consumed"):
        if not isinstance(proof.get(field), bool):
            raise AuditRegistrationError(f"launcher attestation {field} is malformed")
    for field in (
        "attestation_sha256",
        "command_sha256",
        "consumed_permit_sha256",
        "issuance_id",
        "launcher_environment_sha256",
        "output_path_sha256",
        "permit_directory_sha256",
        "permit_marker_path_sha256",
        "permit_record_path_sha256",
        "registration_sha256",
        "repository_root_sha256",
        "source_manifest_sha256",
    ):
        if not _is_lower_hex(proof.get(field), 64):
            raise AuditRegistrationError(f"launcher attestation {field} is malformed")
    if not _is_lower_hex(proof.get("code_commit"), 40):
        raise AuditRegistrationError("launcher attestation code commit is malformed")
    for field in (
        "process_id",
        "parent_process_id",
        "process_start_time_ticks",
        "parent_start_time_ticks",
    ):
        number = proof.get(field)
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise AuditRegistrationError(f"launcher attestation {field} is malformed")
    successful_evidence = row.get("exit_status") == 0 or row.get("payload_sha256") is not None
    if successful_evidence and (
        proof.get("capability_issued") is not True
        or proof.get("read_authorization_consumed") is not True
    ):
        raise AuditRegistrationError(
            "successful ledger evidence lacks issued and consumed read authorization"
        )
    run_label = row.get("run_label")
    repository_root = Path(cast(str, row.get("repository_root")))
    expected_record = directory / f"{run_label}.permit.json"
    expected_marker = directory / f"{run_label}.available"
    expected_hashes = {
        "command_sha256": canonical_sha256(list(exact_command)),
        "output_path_sha256": hashlib.sha256(output_path.as_posix().encode("utf-8")).hexdigest(),
        "permit_directory_sha256": hashlib.sha256(directory.as_posix().encode("utf-8")).hexdigest(),
        "permit_marker_path_sha256": hashlib.sha256(
            expected_marker.as_posix().encode("utf-8")
        ).hexdigest(),
        "permit_record_path_sha256": hashlib.sha256(
            expected_record.as_posix().encode("utf-8")
        ).hexdigest(),
        "repository_root_sha256": hashlib.sha256(
            repository_root.as_posix().encode("utf-8")
        ).hexdigest(),
    }
    if any(proof.get(field) != expected for field, expected in expected_hashes.items()):
        raise AuditRegistrationError("launcher attestation path/command binding differs")
    for field in (
        "code_commit",
        "issuance_id",
        "registration_sha256",
        "run_label",
        "source_manifest_sha256",
    ):
        if proof.get(field) != row.get(field):
            raise AuditRegistrationError(
                f"launcher attestation {field} differs from permit issuance"
            )
    consumed_permit = {
        "code_commit": row["code_commit"],
        "clean_status_porcelain_sha256": EMPTY_GIT_OUTPUT_SHA256,
        "consumed": True,
        "consumed_marker_path": str(directory / f"{run_label}.consumed"),
        "index_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
        "issuance_id": row["issuance_id"],
        "lockbox_read_claim_marker_path": str(directory / f"{run_label}.lockbox-read-claimed"),
        "permit_directory": str(directory),
        "permit_record_sha256": row["permit_record_sha256"],
        "registration_content_sha256": row["registration_content_sha256"],
        "registration_sha256": row["registration_sha256"],
        "repository_root": row["repository_root"],
        "run_label": run_label,
        "scientific_output_path": publication.scientific_output_paths[cast(str, run_label)],
        "scientific_output_paths": dict(publication.scientific_output_paths),
        "scientific_exposure_marker_path": str(
            directory / f"{run_label}.scientific-exposure-started"
        ),
        "source_manifest_sha256": row["source_manifest_sha256"],
        "worktree_roots": dict(publication.worktree_roots),
        "working_diff_sha256": EMPTY_GIT_OUTPUT_SHA256,
    }
    expected_consumed_sha256 = canonical_sha256(consumed_permit)
    if proof.get("consumed_permit_sha256") != expected_consumed_sha256:
        raise AuditRegistrationError("launcher attestation consumed-permit binding differs")
    identity_keys = LAUNCHER_ATTESTATION_PROOF_KEYS - {
        "attestation_sha256",
        "capability_issued",
        "permit_directory_sha256",
        "phase",
        "read_authorization_consumed",
        "valid",
    }
    identity = {key: proof[key] for key in identity_keys}
    if proof.get("attestation_sha256") != canonical_sha256(identity):
        raise AuditRegistrationError("launcher attestation identity digest differs")


def _validate_execution_ledger_row(
    row: Mapping[str, object],
    *,
    directory: Path,
    publication: _PermitPublication,
    primary_row: Mapping[str, object] | None,
) -> None:
    expected_keys = {
        "code_commit",
        "disposition",
        "exact_command",
        "exit_status",
        "hostname",
        "issuance_id",
        "launcher_attestation",
        "lockbox_read_claimed",
        "output_complete",
        "output_path",
        "output_sha256_observed",
        "output_size_bytes",
        "pair_attestation",
        "payload_sha256",
        "permit_record_sha256",
        "registration_content_sha256",
        "registration_sha256",
        "repository_root",
        "run_label",
        "schema_version",
        "scientific_payload_schema_valid",
        "source_manifest_sha256",
        "utc",
    }
    if set(row) != expected_keys:
        raise AuditRegistrationError("execution ledger row has a noncanonical schema")
    label_value = row.get("run_label")
    exit_status = row.get("exit_status")
    payload_sha256 = row.get("payload_sha256")
    observed_sha256 = row.get("output_sha256_observed")
    output_size = row.get("output_size_bytes")
    if not isinstance(label_value, str) or label_value not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("execution ledger row label is not registered")
    label = label_value
    record = publication.records[label]
    registration_identity = cast(Mapping[str, object], record["registration"])
    if (
        row.get("code_commit") != publication.context["code_commit"]
        or row.get("issuance_id") != publication.issuance_id
        or row.get("permit_record_sha256") != publication.record_sha256[label]
        or row.get("registration_content_sha256") != registration_identity["content_sha256"]
        or row.get("registration_sha256") != publication.context["registration_sha256"]
        or row.get("repository_root") != publication.worktree_roots[label]
        or row.get("source_manifest_sha256") != publication.context["source_manifest_sha256"]
    ):
        raise AuditRegistrationError("execution ledger row differs from permit issuance")
    if isinstance(exit_status, bool) or not isinstance(exit_status, int):
        raise AuditRegistrationError("execution ledger exit status is malformed")
    if payload_sha256 is not None and not _is_lower_hex(payload_sha256, 64):
        raise AuditRegistrationError("execution ledger payload SHA-256 is malformed")
    if observed_sha256 is not None and not _is_lower_hex(observed_sha256, 64):
        raise AuditRegistrationError("execution ledger observed SHA-256 is malformed")
    if output_size is not None and (
        isinstance(output_size, bool) or not isinstance(output_size, int) or output_size < 0
    ):
        raise AuditRegistrationError("execution ledger output size is malformed")
    if not isinstance(row.get("output_complete"), bool):
        raise AuditRegistrationError("execution ledger output completeness is malformed")
    if not isinstance(row.get("scientific_payload_schema_valid"), bool) or row.get(
        "scientific_payload_schema_valid"
    ) is not row.get("output_complete"):
        raise AuditRegistrationError("scientific payload validation state is malformed")
    if not isinstance(row.get("lockbox_read_claimed"), bool):
        raise AuditRegistrationError("ledger lockbox-read claim state is malformed")
    if row.get("output_complete") is True and row.get("lockbox_read_claimed") is not True:
        raise AuditRegistrationError("complete output lacks its one-shot lockbox-read claim")
    if row.get("output_complete") is True and (
        observed_sha256 != payload_sha256 or output_size is None
    ):
        raise AuditRegistrationError("complete ledger output lacks matching byte evidence")
    for field in ("disposition", "hostname", "output_path", "utc"):
        if not isinstance(row.get(field), str) or not cast(str, row[field]):
            raise AuditRegistrationError(f"execution ledger {field} is malformed")
    output_path = Path(cast(str, row["output_path"]))
    if not output_path.is_absolute() or str(output_path.resolve()) != row["output_path"]:
        raise AuditRegistrationError("execution ledger output path is noncanonical")
    repository_root = Path(cast(str, row["repository_root"]))
    if _is_within(output_path, repository_root) or output_path == repository_root:
        raise AuditRegistrationError("ledger scientific output is inside its worktree")
    command = row.get("exact_command")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(token, str) or not token for token in command)
        or tuple(command) != realized_audit_command(directory, label, output_path)
    ):
        raise AuditRegistrationError("execution ledger command is noncanonical")
    _validate_launcher_attestation_proof(
        row.get("launcher_attestation"),
        row=row,
        directory=directory,
        publication=publication,
        exact_command=cast(list[str], command),
        output_path=output_path,
    )
    if row.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise AuditRegistrationError("execution ledger schema version is incorrect")
    if label == "primary":
        if primary_row is not None or row.get("pair_attestation") is not None:
            raise AuditRegistrationError("primary ledger row has invalid pair state")
    else:
        if primary_row is None:
            raise AuditRegistrationError("replica ledger row lacks its primary row")
        if row["output_path"] == primary_row["output_path"]:
            raise AuditRegistrationError("primary and replica output paths are not distinct")
        _validate_pair_attestation(
            row.get("pair_attestation"),
            primary_row=primary_row,
            replica_row=row,
        )


def _read_execution_ledger_rows(
    publication: _PermitPublication,
) -> tuple[dict[str, object], ...]:
    directory = publication.directory
    ledger_path = directory / "execution_ledger.jsonl"
    if ledger_path.is_symlink():
        raise AuditRegistrationError("execution ledger cannot be a symbolic link")
    if not ledger_path.exists():
        return ()
    raw = ledger_path.read_bytes()
    if not raw:
        return ()
    if not raw.endswith(b"\n"):
        raise AuditRegistrationError("execution ledger lacks its final newline")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise AuditRegistrationError("execution ledger is not canonical ASCII") from error
    lines = text.splitlines()
    if not lines or any(not line for line in lines):
        raise AuditRegistrationError("execution ledger contains blank rows")
    rows = tuple(_strict_json_object(line.encode("ascii")) for line in lines)
    if any(
        canonical_json_bytes(row) != line.encode("ascii")
        for row, line in zip(rows, lines, strict=True)
    ):
        raise AuditRegistrationError("execution ledger contains noncanonical rows")
    if (
        len(rows) > len(REGISTERED_START_LABELS)
        or tuple(row.get("run_label") for row in rows) != REGISTERED_START_LABELS[: len(rows)]
    ):
        raise AuditRegistrationError("execution ledger rows are out of registered order")
    primary_row: Mapping[str, object] | None = None
    for row in rows:
        _validate_execution_ledger_row(
            row,
            directory=directory,
            publication=publication,
            primary_row=primary_row,
        )
        if row["run_label"] == "primary":
            primary_row = row
    return rows


def _require_ledger_state_before_consumption(
    publication: _PermitPublication, run_label: str
) -> None:
    """Serialize starts and require a complete durable primary row before replica."""

    ledger_path = publication.directory / "execution_ledger.jsonl"
    lock_path = publication.directory / "execution_ledger.lock"
    if ledger_path.is_symlink() or lock_path.is_symlink():
        raise AuditRegistrationError("execution ledger paths cannot be symbolic links")
    with (
        lock_path.open("a+", encoding="ascii", newline="") as lock_handle,
        _locked_file(lock_handle),
    ):
        rows = _read_execution_ledger_rows(publication)
        if run_label == "primary" and rows:
            raise AuditRegistrationError("primary start requires an empty execution ledger")
        if run_label == "replica":
            primary = rows[0] if len(rows) == 1 else None
            payload_sha256 = None if primary is None else primary.get("payload_sha256")
            if (
                primary is None
                or primary.get("run_label") != "primary"
                or primary.get("exit_status") != 0
                or primary.get("output_complete") is not True
                or primary.get("scientific_payload_schema_valid") is not True
                or primary.get("lockbox_read_claimed") is not True
                or not _is_lower_hex(payload_sha256, 64)
                or primary.get("output_sha256_observed") != payload_sha256
                or isinstance(primary.get("output_size_bytes"), bool)
                or not isinstance(primary.get("output_size_bytes"), int)
                or cast(int, primary["output_size_bytes"]) <= 0
            ):
                raise AuditRegistrationError(
                    "replica start requires one successful complete durable primary ledger row"
                )


def _pair_party(row: Mapping[str, object], evidence: Mapping[str, object]) -> dict[str, object]:
    return {
        "exit_status": row["exit_status"],
        "observed_output_complete": evidence["output_complete"],
        "observed_output_sha256": evidence["output_sha256_observed"],
        "observed_output_size_bytes": evidence["output_size_bytes"],
        "output_path": row["output_path"],
        "payload_sha256": row["payload_sha256"],
        "recorded_output_complete": row["output_complete"],
        "run_label": row["run_label"],
    }


def _build_pair_attestation(
    primary_row: Mapping[str, object],
    replica_row: Mapping[str, object],
    *,
    replica_raw: bytes | None,
) -> dict[str, object]:
    primary_evidence, primary_raw = _inspect_scientific_output(
        Path(cast(str, primary_row["output_path"])),
        cast(str | None, primary_row["payload_sha256"]),
    )
    replica_evidence = {
        "output_complete": replica_row["output_complete"],
        "output_sha256_observed": replica_row["output_sha256_observed"],
        "output_size_bytes": replica_row["output_size_bytes"],
    }
    primary = _pair_party(primary_row, primary_evidence)
    replica = _pair_party(replica_row, replica_evidence)
    both_exit_zero = primary_row["exit_status"] == 0 and replica_row["exit_status"] == 0
    primary_payload_sha256 = primary_row["payload_sha256"]
    replica_payload_sha256 = replica_row["payload_sha256"]
    payload_sha256_matches = (
        isinstance(primary_payload_sha256, str)
        and isinstance(replica_payload_sha256, str)
        and primary_payload_sha256 == replica_payload_sha256
    )
    both_outputs_complete = all(
        party[field] is True
        for party in (primary, replica)
        for field in ("recorded_output_complete", "observed_output_complete")
    )
    exact_bytes_equal = (
        both_outputs_complete
        and primary_raw is not None
        and replica_raw is not None
        and primary_raw == replica_raw
    )
    positive = (
        both_exit_zero and payload_sha256_matches and both_outputs_complete and exact_bytes_equal
    )
    return {
        "both_exit_zero": both_exit_zero,
        "both_outputs_complete": both_outputs_complete,
        "disposition": (
            PAIR_POSITIVE_DISPOSITION if positive else PAIR_FROZEN_NEGATIVE_DISPOSITION
        ),
        "exact_bytes_equal": exact_bytes_equal,
        "payload_sha256_matches": payload_sha256_matches,
        "positive_pair_eligible": positive,
        "positive_pair_eligibility_scope": "pair-integrity-only",
        "primary": primary,
        "registered_start_count": 2,
        "replica": replica,
        "schema_version": PAIR_ATTESTATION_SCHEMA_VERSION,
        "start_allowance_state": "exhausted-permanently",
        "third_start_allowed": False,
    }


def append_execution_ledger(
    *,
    capability: object | None = None,
    launch_attestation: object | None = None,
    repository_root: str | Path,
    permit_directory: str | Path,
    run_label: str,
    exact_command: Sequence[str],
    output_path: str | Path,
    exit_status: int,
    payload_sha256: str | None,
    disposition: str,
    utc: str | None = None,
    hostname: str | None = None,
) -> dict[str, object]:
    """Append one locked, fsynced row and freeze the replica pair conclusion."""

    _require_linux_posix_admin_platform()
    try:
        launcher_proof = _audit_module().consume_registered_audit_capability_for_ledger(
            capability,
            launch_attestation,
            repository_root=repository_root,
            exact_command=exact_command,
            exit_status=exit_status,
            payload_sha256=payload_sha256,
        )
    except Exception as error:
        raise AuditRegistrationError(
            "ledger append lacks a valid one-shot launcher/capability attestation"
        ) from error
    repository = Path(repository_root).resolve(strict=True)
    directory = _require_canonical_permit_directory(permit_directory)
    if run_label not in REGISTERED_START_LABELS:
        raise AuditRegistrationError("ledger run label is not registered")
    context = _clean_tagged_registration_context(repository)
    publication = _validate_permit_publication(directory, context=context)
    if publication.worktree_roots[run_label] != str(repository):
        raise AuditRegistrationError("ledger worktree differs from frozen permit issuance")
    _validate_consumed_marker(publication, run_label)
    _validate_scientific_exposure_marker(publication, run_label)
    lockbox_read_claimed = _validate_lockbox_read_claim_marker(publication, run_label)
    if isinstance(exit_status, bool) or not isinstance(exit_status, int):
        raise AuditRegistrationError("exit status must be an integer")
    if payload_sha256 is not None and not _is_lower_hex(payload_sha256, 64):
        raise AuditRegistrationError("payload SHA-256 is malformed")
    if not isinstance(disposition, str) or not disposition:
        raise AuditRegistrationError("disposition must be a non-empty string")
    if not exact_command or any(not isinstance(token, str) or not token for token in exact_command):
        raise AuditRegistrationError("exact command must be a non-empty string-token list")
    resolved_output = require_external_scientific_output_path(repository, output_path)
    if tuple(exact_command) != realized_audit_command(directory, run_label, resolved_output):
        raise AuditRegistrationError("exact command differs from the frozen template")
    authorization_row: dict[str, object] = {
        "code_commit": context["code_commit"],
        "exit_status": exit_status,
        "issuance_id": publication.issuance_id,
        "payload_sha256": payload_sha256,
        "permit_record_sha256": publication.record_sha256[run_label],
        "registration_content_sha256": cast(
            Mapping[str, object], publication.records[run_label]["registration"]
        )["content_sha256"],
        "registration_sha256": context["registration_sha256"],
        "repository_root": str(repository),
        "run_label": run_label,
        "source_manifest_sha256": context["source_manifest_sha256"],
    }
    _validate_launcher_attestation_proof(
        launcher_proof,
        row=authorization_row,
        directory=directory,
        publication=publication,
        exact_command=exact_command,
        output_path=resolved_output,
    )
    registration_value, registration_raw = load_validated_registration(repository)
    if hashlib.sha256(registration_raw).hexdigest() != context["registration_sha256"]:
        raise AuditRegistrationError("ledger registration bytes changed after clean admission")
    ledger_path = directory / "execution_ledger.jsonl"
    lock_path = directory / "execution_ledger.lock"
    if ledger_path.is_symlink() or lock_path.is_symlink():
        raise AuditRegistrationError("execution ledger paths cannot be symbolic links")
    with (
        lock_path.open("a+", encoding="ascii", newline="") as lock_handle,
        _locked_file(lock_handle),
    ):
        _validate_consumed_marker(publication, run_label)
        lockbox_read_claimed = _validate_lockbox_read_claim_marker(publication, run_label)
        existing_rows = _read_execution_ledger_rows(publication)
        if any(row.get("run_label") == run_label for row in existing_rows):
            raise AuditRegistrationError("execution ledger already contains this run label")
        if (
            len(existing_rows) >= len(REGISTERED_START_LABELS)
            or run_label != (REGISTERED_START_LABELS[len(existing_rows)])
        ):
            raise AuditRegistrationError("execution ledger append is out of registered order")
        evidence, output_raw = _inspect_scientific_output(resolved_output, payload_sha256)
        scientific_payload_schema_valid = False
        if evidence["output_complete"] is True and output_raw is not None:
            try:
                payload = _validate_registered_scientific_payload(
                    output_raw,
                    registration=registration_value,
                    context=context,
                )
                scientific_payload_schema_valid = (
                    payload["disposition"] == disposition and lockbox_read_claimed
                )
            except AuditRegistrationError:
                scientific_payload_schema_valid = False
        if not scientific_payload_schema_valid:
            evidence["output_complete"] = False
            output_raw = None
        registration_identity = cast(
            Mapping[str, object], publication.records[run_label]["registration"]
        )
        row: dict[str, object] = {
            "code_commit": context["code_commit"],
            "disposition": disposition,
            "exact_command": list(exact_command),
            "exit_status": exit_status,
            "hostname": hostname if hostname is not None else socket.gethostname(),
            "issuance_id": publication.issuance_id,
            "launcher_attestation": launcher_proof,
            "lockbox_read_claimed": lockbox_read_claimed,
            "output_complete": evidence["output_complete"],
            "output_path": str(resolved_output),
            "output_sha256_observed": evidence["output_sha256_observed"],
            "output_size_bytes": evidence["output_size_bytes"],
            "pair_attestation": None,
            "payload_sha256": payload_sha256,
            "permit_record_sha256": publication.record_sha256[run_label],
            "registration_content_sha256": registration_identity["content_sha256"],
            "registration_sha256": context["registration_sha256"],
            "repository_root": str(repository),
            "run_label": run_label,
            "schema_version": LEDGER_SCHEMA_VERSION,
            "scientific_payload_schema_valid": scientific_payload_schema_valid,
            "source_manifest_sha256": context["source_manifest_sha256"],
            "utc": utc if utc is not None else datetime.now(UTC).isoformat(),
        }
        if run_label == "replica":
            primary_row = existing_rows[0]
            row["pair_attestation"] = _build_pair_attestation(
                primary_row,
                row,
                replica_raw=output_raw,
            )
        _validate_execution_ledger_row(
            row,
            directory=directory,
            publication=publication,
            primary_row=existing_rows[0] if existing_rows else None,
        )
        line = canonical_json_bytes(row) + b"\n"
        descriptor = os.open(
            ledger_path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        try:
            if os.write(descriptor, line) != len(line):
                raise OSError("execution ledger append was partial")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(directory)
    return row


def _build_promotion_receipt(
    *,
    publication: _PermitPublication,
    rows: Sequence[Mapping[str, object]],
    attestation: Mapping[str, object],
    primary_raw: bytes,
) -> dict[str, object]:
    ledger_rows_sha256 = {
        cast(str, row["run_label"]): hashlib.sha256(canonical_json_bytes(row)).hexdigest()
        for row in rows
    }
    ledger_raw = b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    artifact_sha256 = hashlib.sha256(primary_raw).hexdigest()
    return {
        "artifact": {
            "path": SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
            "sha256": artifact_sha256,
            "size_bytes": len(primary_raw),
        },
        "code_commit": publication.context["code_commit"],
        "exact_bytes_equal": True,
        "issuance_id": publication.issuance_id,
        "ledger_rows_sha256": ledger_rows_sha256,
        "ledger_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "pair_disposition": attestation["disposition"],
        "payload_sha256": {cast(str, row["run_label"]): row["payload_sha256"] for row in rows},
        "permit_record_sha256": dict(publication.record_sha256),
        "positive_pair_eligible": attestation["positive_pair_eligible"],
        "positive_pair_eligibility_scope": attestation["positive_pair_eligibility_scope"],
        "registration_content_sha256": publication.context["registration_content_sha256"],
        "registration_sha256": publication.context["registration_sha256"],
        "schema_version": PROMOTION_RECEIPT_SCHEMA_VERSION,
        "source_manifest_sha256": publication.context["source_manifest_sha256"],
        "worktree_roots": dict(publication.worktree_roots),
    }


def promote_verified_audit_pair(
    *,
    repository_root: str | Path,
    permit_directory: str | Path,
) -> dict[str, object]:
    """Publish, or safely finish publishing, one fully revalidated positive pair."""

    _require_linux_posix_admin_platform()
    repository = Path(repository_root).resolve(strict=True)
    directory = _require_canonical_permit_directory(permit_directory)
    if _is_within(directory, repository) or directory == repository:
        raise AuditRegistrationError("permit directory must remain outside the repository")
    context = _clean_tagged_registration_context(
        repository,
        allow_promoted_outputs=True,
    )
    registration_value, registration_raw = load_validated_registration(repository)
    if hashlib.sha256(registration_raw).hexdigest() != context["registration_sha256"]:
        raise AuditRegistrationError("promotion registration bytes changed after admission")
    publication = _validate_permit_publication(directory, context=context)
    if Path(publication.worktree_roots["primary"]) != repository:
        raise AuditRegistrationError("repository promotion must target the frozen primary worktree")
    for label in REGISTERED_START_LABELS:
        worktree_root = Path(publication.worktree_roots[label])
        worktree_context = _clean_tagged_registration_context(
            worktree_root,
            allow_promoted_outputs=True,
        )
        if worktree_context != context:
            raise AuditRegistrationError(
                "promotion worktree differs from the frozen permit issuance"
            )
        if worktree_root != repository:
            _require_repository_promotion_outputs_absent(worktree_root)
        _validate_consumed_marker(publication, label)
        if not _validate_lockbox_read_claim_marker(publication, label):
            raise AuditRegistrationError(
                "promotion requires one durable lockbox-read claim per start"
            )
        if not _validate_scientific_exposure_marker(publication, label):
            raise AuditRegistrationError(
                "promotion requires scientific exposure from both registered starts"
            )
    destination = repository / SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_destination = repository / SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    if (
        destination.parent.resolve(strict=True) != destination.parent
        or receipt_destination.parent != destination.parent
    ):
        raise AuditRegistrationError("repository artifact directory cannot be redirected")
    _repository_promotion_output_presence(destination, receipt_destination)
    ledger_path = directory / "execution_ledger.jsonl"
    lock_path = directory / "execution_ledger.lock"
    if ledger_path.is_symlink() or lock_path.is_symlink():
        raise AuditRegistrationError("execution ledger paths cannot be symbolic links")
    with (
        lock_path.open("a+", encoding="ascii", newline="") as lock_handle,
        _locked_file(lock_handle),
    ):
        _remove_registered_promotion_staging_temporaries(repository)
        rows = _read_execution_ledger_rows(publication)
        if len(rows) != 2:
            raise AuditRegistrationError(
                "repository promotion requires the complete registered pair"
            )
        primary_row, replica_row = rows
        attestation = replica_row.get("pair_attestation")
        if (
            not isinstance(attestation, Mapping)
            or attestation.get("positive_pair_eligible") is not True
            or attestation.get("exact_bytes_equal") is not True
            or attestation.get("disposition") != PAIR_POSITIVE_DISPOSITION
            or attestation.get("third_start_allowed") is not False
            or attestation.get("start_allowance_state") != "exhausted-permanently"
        ):
            raise AuditRegistrationError(
                "repository promotion requires a positive byte-identical pair"
            )
        primary_path = Path(cast(str, primary_row["output_path"])).resolve()
        replica_path = Path(cast(str, replica_row["output_path"])).resolve()
        all_repository_roots = {
            repository,
            *(Path(value) for value in publication.worktree_roots.values()),
        }
        if primary_path == replica_path or any(
            _is_within(path, root) or path == root
            for path in (primary_path, replica_path)
            for root in all_repository_roots
        ):
            raise AuditRegistrationError("scientific pair outputs must remain external")
        primary_evidence, primary_raw = _inspect_scientific_output(
            primary_path,
            cast(str | None, primary_row["payload_sha256"]),
        )
        replica_evidence, replica_raw = _inspect_scientific_output(
            replica_path,
            cast(str | None, replica_row["payload_sha256"]),
        )
        if (
            primary_evidence["output_complete"] is not True
            or replica_evidence["output_complete"] is not True
            or primary_raw is None
            or replica_raw is None
            or primary_raw != replica_raw
            or hashlib.sha256(primary_raw).hexdigest() != primary_row["payload_sha256"]
            or primary_row["payload_sha256"] != replica_row["payload_sha256"]
        ):
            raise AuditRegistrationError(
                "scientific pair bytes no longer match the positive attestation"
            )
        for row, raw in ((primary_row, primary_raw), (replica_row, replica_raw)):
            payload = _validate_registered_scientific_payload(
                raw,
                registration=registration_value,
                context=context,
            )
            if payload["disposition"] != row["disposition"]:
                raise AuditRegistrationError(
                    "ledger disposition differs from its scientific payload"
                )
        artifact_sha256 = hashlib.sha256(primary_raw).hexdigest()
        receipt = _build_promotion_receipt(
            publication=publication,
            rows=rows,
            attestation=attestation,
            primary_raw=primary_raw,
        )
        receipt_raw = canonical_json_bytes(receipt)
        artifact_present, receipt_present = _repository_promotion_output_presence(
            destination,
            receipt_destination,
        )
        if receipt_present and not artifact_present:
            raise AuditRegistrationError(
                "repository audit receipt exists without its verified payload"
            )
        if artifact_present and destination.read_bytes() != primary_raw:
            raise AuditRegistrationError(
                "existing repository audit payload differs from the verified pair"
            )
        if receipt_present:
            if receipt_destination.read_bytes() != receipt_raw:
                raise AuditRegistrationError("existing repository audit receipt identity mismatch")
        elif artifact_present:
            _exclusive_write(receipt_destination, receipt_raw)
        else:
            _exclusive_write(destination, primary_raw)
            # Make the only recoverable half-publication durable before the receipt.
            _fsync_directory(destination.parent)
            _exclusive_write(receipt_destination, receipt_raw)
        _fsync_directory(destination.parent)
    validated_receipt, validated_receipt_raw = load_validated_promotion_receipt(
        repository,
        directory,
    )
    if validated_receipt != receipt or validated_receipt_raw != receipt_raw:
        raise AuditRegistrationError("post-publication receipt validation failed")
    return {
        "evaluator_dispositions": {
            "primary": primary_row["disposition"],
            "replica": replica_row["disposition"],
        },
        "pair_disposition": attestation["disposition"],
        "payload_sha256": artifact_sha256,
        "positive_pair_eligible": attestation["positive_pair_eligible"],
        "positive_pair_eligibility_scope": attestation["positive_pair_eligibility_scope"],
        "repository_copy_path": SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
        "repository_receipt_path": (SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()),
        "repository_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "size_bytes": len(primary_raw),
        "state": "repository-copy-published",
    }


def load_validated_promotion_receipt(
    repository_root: str | Path,
    permit_directory: str | Path = CANONICAL_EXTERNAL_PERMIT_DIRECTORY,
) -> tuple[dict[str, object], bytes]:
    """Revalidate the repository payload/receipt against the frozen external pair."""

    _require_linux_posix_admin_platform()
    repository = Path(repository_root).resolve(strict=True)
    context = _clean_tagged_registration_context(
        repository,
        allow_promoted_outputs=True,
    )
    registration_value, registration_raw = load_validated_registration(repository)
    if hashlib.sha256(registration_raw).hexdigest() != context["registration_sha256"]:
        raise AuditRegistrationError("receipt registration bytes differ from frozen HEAD")
    publication = _validate_permit_publication(permit_directory, context=context)
    if Path(publication.worktree_roots["primary"]) != repository:
        raise AuditRegistrationError("promotion receipt must belong to the frozen primary worktree")
    for label in REGISTERED_START_LABELS:
        worktree_root = Path(publication.worktree_roots[label])
        worktree_context = _clean_tagged_registration_context(
            worktree_root,
            allow_promoted_outputs=True,
        )
        if worktree_context != context:
            raise AuditRegistrationError("receipt worktree differs from frozen issuance")
        if worktree_root != repository:
            _require_repository_promotion_outputs_absent(worktree_root)
        _validate_consumed_marker(publication, label)
        if not _validate_lockbox_read_claim_marker(publication, label):
            raise AuditRegistrationError("receipt lacks a durable lockbox-read claim")
        if not _validate_scientific_exposure_marker(publication, label):
            raise AuditRegistrationError("receipt lacks durable scientific exposure")
    rows = _read_execution_ledger_rows(publication)
    if len(rows) != 2:
        raise AuditRegistrationError("receipt requires the complete two-row ledger")
    attestation = rows[1].get("pair_attestation")
    if (
        not isinstance(attestation, Mapping)
        or attestation.get("positive_pair_eligible") is not True
    ):
        raise AuditRegistrationError("receipt pair attestation is not promotable")
    artifact_path = repository / SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    artifact_present, receipt_present = _repository_promotion_output_presence(
        artifact_path,
        receipt_path,
    )
    if not artifact_present or not receipt_present:
        raise AuditRegistrationError("repository payload/receipt path state is invalid")
    primary_row, replica_row = rows
    primary_sha256 = cast(str, primary_row["payload_sha256"])
    replica_sha256 = cast(str, replica_row["payload_sha256"])
    primary_evidence, primary_raw = _inspect_scientific_output(
        Path(cast(str, primary_row["output_path"])),
        primary_sha256,
    )
    replica_evidence, replica_raw = _inspect_scientific_output(
        Path(cast(str, replica_row["output_path"])),
        replica_sha256,
    )
    if (
        primary_evidence["output_complete"] is not True
        or replica_evidence["output_complete"] is not True
        or primary_raw is None
        or replica_raw is None
    ):
        raise AuditRegistrationError(
            "receipt external pair is missing stable bytes bound to its ledger hashes"
        )
    primary_size = primary_evidence["output_size_bytes"]
    replica_size = replica_evidence["output_size_bytes"]
    current_sha256 = hashlib.sha256(primary_raw).hexdigest()
    if (
        primary_sha256 != replica_sha256
        or primary_evidence["output_sha256_observed"] != primary_sha256
        or primary_evidence["output_sha256_observed"] != primary_row["output_sha256_observed"]
        or replica_evidence["output_sha256_observed"] != replica_sha256
        or replica_evidence["output_sha256_observed"] != replica_row["output_sha256_observed"]
        or isinstance(primary_size, bool)
        or not isinstance(primary_size, int)
        or primary_size != len(primary_raw)
        or primary_size != primary_row["output_size_bytes"]
        or isinstance(replica_size, bool)
        or not isinstance(replica_size, int)
        or replica_size != len(replica_raw)
        or replica_size != replica_row["output_size_bytes"]
        or primary_raw != replica_raw
        or current_sha256 != primary_sha256
        or current_sha256 != replica_sha256
    ):
        raise AuditRegistrationError(
            "receipt external pair bytes differ from immutable ledger payload hashes"
        )
    artifact_evidence, artifact_raw = _inspect_scientific_output(
        artifact_path,
        primary_sha256,
    )
    artifact_size = artifact_evidence["output_size_bytes"]
    if (
        artifact_evidence["output_complete"] is not True
        or artifact_raw is None
        or artifact_evidence["output_sha256_observed"] != primary_sha256
        or isinstance(artifact_size, bool)
        or not isinstance(artifact_size, int)
        or artifact_size != len(artifact_raw)
        or artifact_raw != primary_raw
    ):
        raise AuditRegistrationError(
            "repository payload differs from immutable external pair bytes"
        )
    for row, output_raw in (
        (primary_row, primary_raw),
        (replica_row, replica_raw),
    ):
        payload = _validate_registered_scientific_payload(
            output_raw,
            registration=registration_value,
            context=context,
        )
        if payload["disposition"] != row["disposition"]:
            raise AuditRegistrationError("receipt ledger/payload disposition mismatch")
    receipt, receipt_raw = _load_canonical_object(receipt_path)
    expected_receipt = _build_promotion_receipt(
        publication=publication,
        rows=rows,
        attestation=attestation,
        primary_raw=primary_raw,
    )
    if receipt != expected_receipt:
        raise AuditRegistrationError("repository audit receipt identity mismatch")
    return receipt, receipt_raw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).parent.parent,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--prepare-permits",
        type=Path,
        default=None,
        metavar="EXTERNAL_DIRECTORY",
    )
    mode.add_argument(
        "--promote-pair",
        action="store_true",
        help="promote the verified pair from the canonical external permit directory",
    )
    parser.add_argument(
        "--replica-repository-root",
        type=Path,
        default=None,
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.prepare_permits is not None or args.promote_pair:
        _require_linux_posix_admin_platform()
    root = args.repository_root.resolve()
    if args.prepare_permits is not None:
        if args.output is not None:
            raise AuditRegistrationError("--output cannot accompany --prepare-permits")
        if args.replica_repository_root is None:
            raise AuditRegistrationError(
                "--replica-repository-root is required with --prepare-permits"
            )
        result = prepare_external_audit_permits(
            root,
            args.prepare_permits,
            replica_repository_root=args.replica_repository_root,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.promote_pair:
        if args.output is not None or args.replica_repository_root is not None:
            raise AuditRegistrationError(
                "--promote-pair cannot accompany build/prepare-only arguments"
            )
        result = promote_verified_audit_pair(
            repository_root=root,
            permit_directory=CANONICAL_EXTERNAL_PERMIT_DIRECTORY,
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    if args.replica_repository_root is not None:
        raise AuditRegistrationError("--replica-repository-root requires --prepare-permits")
    destination = (
        args.output.resolve() if args.output is not None else root / AUDIT_REGISTRATION_PATH
    )
    if destination != root / AUDIT_REGISTRATION_PATH:
        raise AuditRegistrationError("audit registration has one canonical output path")
    registration = build_audit_registration(root)
    validate_audit_registration(registration, root)
    raw = canonical_json_bytes(registration)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _exclusive_write(destination, raw)
    _fsync_directory(destination.parent)
    print(
        json.dumps(
            {
                "content_sha256": registration["content_sha256"],
                "output": str(destination),
                "payload_sha256": hashlib.sha256(raw).hexdigest(),
                "row_count": EXPECTED_AUDIT_ROW_COUNT,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditRegistrationError as error:
        print(
            json.dumps({"error": str(error), "status": "refused"}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(2) from error
