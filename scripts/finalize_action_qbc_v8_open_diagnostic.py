"""Stdlib-only evidence finalizer for the action-QBC v8 open diagnostic."""

from __future__ import annotations

import argparse
import base64
import csv
import email.policy
import hashlib
import io
import json
import os
import platform
import re
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import Any, NoReturn

_TREATMENT_ID = "action-qbc-v8-open-failure-decomposition-bounded-verification-v1"
_DIAGNOSTIC_ID = "crosslevel-voi-open-diagnostic-v8"
_COMPARISON_ID = "action-qbc-v8-v7-mathematics-identity-replication-v1"
_REGISTRATION_SCHEMA = "action-qbc-v8-open-registration-v1"
_PAYLOAD_SCHEMA = "action-qbc-v8-open-diagnostic-payload-v1"
_RECEIPT_SCHEMA = "action-qbc-v8-open-diagnostic-receipt-v2"
_ADMIN_SCHEMA = "action-qbc-v8-open-diagnostic-administrative-terminal-v2"
_BUNDLE_SCHEMA = "action-qbc-v8-finalization-bundle-v1"
_OPEN_FREEZE_TAG = "action-qbc-v8-open-diagnostic-freeze-v4"
_O8V1_TAG = "action-qbc-v8-open-diagnostic-freeze-v1"
_O8V1_COMMIT = "7685fbdccd41702216b3a3f06d2a0ac699aca7ec"
_O8V1_TREE = "9b9ad5ba986afacbcdb1fde3cd69e0f1c94efdf2"
_P8V5_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v5"
_P8V5_COMMIT = "09f9caea346866a1acf35c20e0c9d937096b5ce3"
_P8V5_TREE = "47a978cdd887fd6dc1cb5e80e36aa3e0a5a29253"
_O8V2_TAG = "action-qbc-v8-open-diagnostic-freeze-v2"
_O8V2_COMMIT = "8da637a47de0c88f917f222e52e54b342d729be9"
_O8V2_TREE = "247eba59e1e2ac9b0611c0e361de945dae0f2dc8"
_P8V6_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v6"
_P8V6_COMMIT = "61cebe90a2f4f7c78ec45119de53a482ed13a655"
_P8V6_TREE = "65695876c44eeb8cac5437149384071f88ff6018"
_O8V3_TAG = "action-qbc-v8-open-diagnostic-freeze-v3"
_O8V3_COMMIT = "5725395a850627fae10e8bb8b27083ccf63b6ec7"
_O8V3_TREE = "7d38de8f5cec16cab92c9d3b757a218e8e490272"
_PREREGISTRATION_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v7"
_PREREGISTRATION_COMMIT = "15059c482d9e463f01cb31fdfd33c96d1f60db0a"
_PREREGISTRATION_TREE = "96469ca9ee018cd32f99955df1ded57af12a8abc"
_P8V5_DOCUMENT = (
    "docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v5_public_visibility_recovery.md"
)
_P8V5_DOCUMENT_BLOB = "7c0955a775af89dcfcde4796a9bbb4d470669d10"
_P8V5_DOCUMENT_SHA256 = (
    "cc9d787a64700332a44f543e7a949ee5522c3663b6b0eb54e418840e560cfe6d"
)
_P8V5_DOCUMENT_BYTE_COUNT = 25_872
_P8V6_DOCUMENT = (
    "docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v6_runner_manifest_key_recovery.md"
)
_P8V6_DOCUMENT_BLOB = "5e870ed0bbbff6fcb4352f6e914d870254773f68"
_P8V6_DOCUMENT_SHA256 = (
    "0ba4cc55ca2b31433bc458972ffc32d87f84b610673fa22ed2b4dd4a8bfc1a41"
)
_P8V6_DOCUMENT_BYTE_COUNT = 32_370
_PREREGISTRATION_DOCUMENT = (
    "docs/experiment_amendment_2026-08-18_action_qbc_v8_open_bounded_remote_verification_v7_consumed_lifecycle_recovery.md"
)
_PREREGISTRATION_DOCUMENT_BLOB = "c0cda2417bd98a42b76e8e1bbdee4cec01dd68f9"
_PREREGISTRATION_DOCUMENT_SHA256 = (
    "f729904367dd7a2664ecd3fdfe4893841326668fbe892b3b733926ad7840745d"
)
_PREREGISTRATION_DOCUMENT_BYTE_COUNT = 37_552
_P8V4_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
_P8V4_COMMIT = "e0bff9ffc185196cafa938c8f7c9a7186366258b"
_P8V4_DOCUMENT = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v4_correction.md"
)
_P8V4_DOCUMENT_BLOB = "29c991b7e23209f2c38d5e9a11a15bca51753d8e"
_P8V4_DOCUMENT_SHA256 = (
    "31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1"
)
_P8V4_DOCUMENT_BYTE_COUNT = 33_215
_P8V3_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
_P8V3_COMMIT = "996ab2bb5a24143a110673977f63e7d111cf2060"
_P8V3_DOCUMENT = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification_v3_correction.md"
)
_P8V3_DOCUMENT_BLOB = "9f014e243a6bfe4ea35636a5de0d9bde598d4130"
_P8V3_DOCUMENT_SHA256 = "b2dafb5d41ab27a63f516c102f295395f32e825a5f66a90bd5fa95dbd414dbe9"
_P8V3_DOCUMENT_BYTE_COUNT = 58_656
_P8V2_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
_P8V2_COMMIT = "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
_P8V2_DOCUMENT = (
    "docs/experiment_amendment_2026-08-11_action_qbc_v8_open_bounded_remote_verification.md"
)
_P8V2_DOCUMENT_BLOB = "b3a639da07a92672adfd4976861a58608702a7f3"
_P8V2_DOCUMENT_SHA256 = "f5c3c7be6221cdefc789d73f140a24b289a4edc849d48c1fb9249bc258308344"
_P8V2_DOCUMENT_BYTE_COUNT = 92_798
_P8V1_TAG = "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
_P8V1_COMMIT = "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
_P8V1_DOCUMENT_BLOB = "9d5f00ea4fdb4ca6ff3cdb8c51ba0105efb1e046"
_P8V1_DOCUMENT_SHA256 = "2e0ad4415d7f230f12f48db01aae9210797aa1da7f3a4ace6723e81be7bbb254"
_R7_COMMIT = "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
_RESULT_DOCUMENT_SCHEMA = "action-qbc-v8-result-document-contract-v1"
_AUTHORITY_ROOT = Path("/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/authority")
_EXECUTION_ROOT = Path("/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4")
_PREPARATION_SOURCE_URL = (
    "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi"
)
_REGISTRATION = "artifacts/action_qbc_v8_open_registration.json"
_PREPARATION = str(_EXECUTION_ROOT / "preparation-receipt.json")
_PREPARATION_VERIFICATION = str(_EXECUTION_ROOT / "preparation-verification.json")
_REMOTE_CLAIM = str(_EXECUTION_ROOT / "remote-verification-claim.json")
_REMOTE_VERIFIER_CLAIM = str(_EXECUTION_ROOT / "remote-verifier-start-claim.json")
_REMOTE_RECEIPT = str(_EXECUTION_ROOT / "remote-verification.json")
_REMOTE_SUPERVISOR = str(_EXECUTION_ROOT / "remote-verification-supervisor.json")
_ARM = str(_EXECUTION_ROOT / "arm-receipt.json")
_DRIVER = str(_EXECUTION_ROOT / "lifecycle-driver-claim.json")
_LEDGER = str(_EXECUTION_ROOT / "lifecycle-ledger.json")
_PROCESS_A_START = str(_EXECUTION_ROOT / "process-a-start-claim.json")
_PROCESS_A_VALIDATOR = str(_EXECUTION_ROOT / "process-a-validator-claim.json")
_PROCESS_A_VALIDATION = str(_EXECUTION_ROOT / "process-a-validation.json")
_PROCESS_A = str(
    _EXECUTION_ROOT / "processes/process-a-output/open/action_qbc_v8_open_diagnostic.json"
)
_PROCESS_B_START = str(_EXECUTION_ROOT / "process-b-start-claim.json")
_PROCESS_B_VALIDATOR = str(_EXECUTION_ROOT / "process-b-validator-claim.json")
_PROCESS_B_VALIDATION = str(_EXECUTION_ROOT / "process-b-validation.json")
_PROCESS_B = str(
    _EXECUTION_ROOT / "processes/process-b-output/open/action_qbc_v8_open_diagnostic.json"
)
_BUNDLE = str(_EXECUTION_ROOT / "finalization-bundle.json")
_EMERGENCY_BUNDLE = str(_EXECUTION_ROOT / "emergency-result-bundle.json")
_OWNER_CLAIM = str(_EXECUTION_ROOT / "result-git-owner.json")
_EVIDENCE_EXPECTED_MODES = {
    "preparation_receipt": 0o444,
    "remote_claim": 0o444,
    "remote_verifier_claim": 0o444,
    "remote_receipt": 0o444,
    "remote_supervisor_receipt": 0o444,
    "arm_receipt": 0o444,
    "preparation_verification_receipt": 0o600,
    "lifecycle_driver_claim": 0o600,
    "lifecycle_ledger": 0o600,
    "process_a_start_claim": 0o600,
    "process_b_start_claim": 0o600,
    "process_a_validator_claim": 0o600,
    "process_b_validator_claim": 0o600,
    "process_a_validation_receipt": 0o600,
    "process_b_validation_receipt": 0o600,
    "process_a_payload": 0o600,
    "process_b_payload": 0o600,
    "normal_finalization_bundle": 0o600,
    "emergency_result_bundle": 0o600,
    "result_git_owner_claim": 0o600,
}
_EVIDENCE_PATHS_BY_ROLE = {
    "preparation_receipt": Path(_PREPARATION),
    "remote_claim": Path(_REMOTE_CLAIM),
    "remote_verifier_claim": Path(_REMOTE_VERIFIER_CLAIM),
    "remote_receipt": Path(_REMOTE_RECEIPT),
    "remote_supervisor_receipt": Path(_REMOTE_SUPERVISOR),
    "arm_receipt": Path(_ARM),
    "preparation_verification_receipt": Path(_PREPARATION_VERIFICATION),
    "lifecycle_driver_claim": Path(_DRIVER),
    "lifecycle_ledger": Path(_LEDGER),
    "process_a_start_claim": Path(_PROCESS_A_START),
    "process_b_start_claim": Path(_PROCESS_B_START),
    "process_a_validator_claim": Path(_PROCESS_A_VALIDATOR),
    "process_b_validator_claim": Path(_PROCESS_B_VALIDATOR),
    "process_a_validation_receipt": Path(_PROCESS_A_VALIDATION),
    "process_b_validation_receipt": Path(_PROCESS_B_VALIDATION),
    "process_a_payload": Path(_PROCESS_A),
    "process_b_payload": Path(_PROCESS_B),
    "normal_finalization_bundle": Path(_BUNDLE),
    "emergency_result_bundle": Path(_EMERGENCY_BUNDLE),
    "result_git_owner_claim": Path(_OWNER_CLAIM),
}
_PAYLOAD_CAP = 67_108_864
_MAX_JSON = _PAYLOAD_CAP + 1
_GIT_TIMEOUT = 60
_NORMAL_TEMPLATE = (
    "# action-QBC v8 open diagnostic result\n\n"
    "- disposition: `{disposition}`\n"
    "- stage: `{stage}`\n"
    "- underlying stage: `{underlying_stage}`\n"
    "- treatment: `action-qbc-v8-open-failure-decomposition-bounded-verification-v1`\n"
    "- open-freeze commit: `{open_freeze_commit_sha}`\n"
    "- registration content SHA-256: `{registration_content_sha256}`\n"
    "- authorization: all false\n"
)
_EMERGENCY_SUFFIX = (
    "- finalizer classification: `{finalizer_classification}`\n"
    "- finalizer exit code: `{finalizer_exit_code}`\n"
    "- finalizer timed out: `{finalizer_timed_out}`\n"
    "- finalizer child cleanup passes: `{finalizer_child_cleanup_passes}`\n"
    "- finalization bundle: `{finalization_bundle_exists}` / "
    "`{finalization_bundle_sha256}`\n"
    "- lifecycle ledger: `{lifecycle_ledger_exists}` / `{lifecycle_ledger_sha256}`\n"
    "- preparation receipt: `{preparation_receipt_exists}` / "
    "`{preparation_receipt_read_status}` / `{preparation_receipt_sha256}`\n"
    "- preparation verification receipt: "
    "`{preparation_verification_receipt_exists}` / "
    "`{preparation_verification_receipt_read_status}` / "
    "`{preparation_verification_receipt_sha256}`\n"
)
_UNDERLYING_ORDER = [
    "preparation_receipt_invalid",
    "preparation_verification_invalid",
    "remote_verification_failed",
    "remote_receipt_invalid",
    "arm_receipt_invalid",
    "registration_invalid",
    "authority_identity_invalid",
    "lifecycle_ledger_invalid",
    "lifecycle_driver_failed",
    "process_a_nonzero",
    "process_a_output_missing",
    "process_a_validation_failed",
    "process_b_nonzero",
    "process_b_output_missing",
    "process_b_validation_failed",
    "payload_byte_mismatch",
]
_AUTHORIZATION = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v8_enabled": False,
    "final_admission_claimed": False,
}
_WINDOWS_REPOSITORY_CONTRACT = {
    "active_hooks_allowed": False,
    "common_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "forbidden_admin_relative_paths": [
        r".git\commondir", r".git\config.worktree", r".git\index.lock",
        r".git\info\attributes", r".git\info\grafts", r".git\info\sparse-checkout",
        r".git\objects\info\alternates", r".git\objects\info\http-alternates",
        r".git\refs\replace", r".git\shallow",
    ],
    "forbidden_pack_suffixes": [".promisor"],
    "forbidden_ref_prefixes": ["refs/replace/"],
    "git_config_byte_count": 846,
    "git_config_sha256": "a78fd50c029f9b0755a7fceac2b77a39479c30becb2eff1794d77df5d185f702",
    "git_directory": r"D:\kaggle competitions\arc3-crosslevel-voi\.git",
    "index_path": r"D:\kaggle competitions\arc3-crosslevel-voi\.git\index",
    "info_exclude_byte_count": 240,
    "info_exclude_sha256": "6671fe83b7a07c8932ee89164d1f2793b2318058eb8b98dc5c06ee0a5a3b0ec1",
    "local_config": {
        "branch.action-qbc-v6-prereg.merge": "refs/heads/action-qbc-v6-prereg",
        "branch.action-qbc-v6-prereg.remote": "origin",
        "branch.action-qbc-v7-open-diagnostic.merge": "refs/heads/action-qbc-v7-open-diagnostic",
        "branch.action-qbc-v7-open-diagnostic.remote": "origin",
        "branch.action-qbc-v7-prereg.merge": "refs/heads/action-qbc-v7-prereg",
        "branch.action-qbc-v7-prereg.remote": "origin",
        "branch.action-qbc-v8-prereg.merge": "refs/heads/action-qbc-v8-prereg",
        "branch.action-qbc-v8-prereg.remote": "origin",
        "branch.main.merge": "refs/heads/main", "branch.main.remote": "origin",
        "core.bare": "false", "core.filemode": "false", "core.ignorecase": "true",
        "core.logallrefupdates": "true", "core.repositoryformatversion": "0",
        "core.sshcommand": (
            "ssh -i .git/arc3_crosslevel_voi_deploy_key -o IdentitiesOnly=yes "
            "-o UserKnownHostsFile=.git/github_known_hosts "
            "-o StrictHostKeyChecking=yes"
        ),
        "core.symlinks": "false",
        "remote.origin.fetch": "+refs/heads/*:refs/remotes/origin/*",
        "remote.origin.url": "https://github.com/bansarinejad/arc3-crosslevel-voi.git",
    },
    "plain_admin_relative_directories": [
        ".git", r".git\hooks", r".git\info", r".git\objects",
        r".git\objects\info", r".git\objects\pack", r".git\refs",
    ],
    "repository_ancestor_chain": [
        "D:\\", r"D:\kaggle competitions",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
    ],
    "repository_root": r"D:\kaggle competitions\arc3-crosslevel-voi",
}
_REGISTRATION_KEYS = {
    "schema_version",
    "status",
    "treatment_id",
    "diagnostic_system_id",
    "comparison_semantics_id",
    "runtime_id",
    "preregistration",
    "v6_negative",
    "platform",
    "dependencies",
    "source_manifest",
    "scene_inventory",
    "row_inventory",
    "transform_contracts",
    "scientific_contract",
    "resource_contract",
    "execution_contract",
    "authorization",
    "content_sha256",
}
_EXECUTION_KEYS = {
    "administrative_stage_order",
    "argv_hashes",
    "arm_argv",
    "arm_receipt_path",
    "arm_timeout_seconds",
    "authority_root",
    "bootstrap_steps",
    "compute_deadline_seconds",
    "environment_build_argv",
    "emergency_bundle_path",
    "execution_root",
    "finalization_bundle_path",
    "linux_host_launcher",
    "linux_platform",
    "linux_tool_identities",
    "lifecycle_driver_argv",
    "lifecycle_driver_claim_path",
    "driver_deadline_seconds",
    "lifecycle_ledger_path",
    "local_git_timeout_seconds",
    "finalizer_argv_template",
    "finalizer_cwd",
    "finalizer_timeout_seconds",
    "hard_timeout_seconds",
    "payload_validator_argv_template",
    "payload_validator_timeout_seconds",
    "preflight_argvs",
    "post_preparation_validation_argv",
    "preparation_argv",
    "preparation_command_environment",
    "preparation_command_policy",
    "preparation_receipt_path",
    "preparation_verification_receipt_path",
    "process_a_output",
    "process_a_root",
    "process_a_start_claim",
    "process_a_validation_receipt",
    "process_a_validator_claim",
    "process_b_output",
    "process_b_root",
    "process_b_start_claim",
    "process_b_validation_receipt",
    "process_b_validator_claim",
    "process_labels",
    "producer_argv",
    "reconstructor_argv",
    "registered_start_count",
    "remote_claim_linux_path",
    "remote_claim_windows_path",
    "remote_policy",
    "remote_receipt_linux_path",
    "remote_receipt_windows_path",
    "remote_supervisor_argv",
    "remote_supervisor_receipt_linux_path",
    "remote_supervisor_receipt_windows_path",
    "remote_verifier_claim_linux_path",
    "remote_verifier_claim_windows_path",
    "remote_verifier_argv",
    "result_document_contract",
    "result_git_environment",
    "result_git_max_attempts",
    "result_git_owner_path",
    "result_git_work_root",
    "result_publisher_argv",
    "result_ref_transaction",
    "scientific_argv_template",
    "test_argvs",
    "third_start_allowed",
    "wall_time_seconds",
    "windows_repository_contract",
}
_ARGV_HASH_KEYS = {
    "arm",
    "bootstrap",
    "environment_build",
    "finalizer",
    "lifecycle_driver",
    "linux_host_launcher",
    "payload_validator",
    "post_preparation_validation",
    "preflight",
    "preparation",
    "producer",
    "reconstructor",
    "remote_supervisor",
    "remote_verifier",
    "result_publisher",
    "result_ref_transaction",
    "scientific",
    "tests",
}
_O8_ADDITIONS = {
    "artifacts/action_qbc_v8_open_registration.json",
    "docs/action_qbc_v8_open_diagnostic_runbook.md",
    "scripts/build_action_qbc_v8_open_registration.py",
    "scripts/execute_action_qbc_v8_open_lifecycle.py",
    "scripts/finalize_action_qbc_v8_open_diagnostic.py",
    "scripts/prepare_action_qbc_v8_open.py",
    "scripts/reconstruct_action_qbc_v8_open_registration.py",
    "scripts/run_action_qbc_v8_open_diagnostic.py",
    "scripts/supervise_action_qbc_v8_remote_tag.py",
    "scripts/validate_action_qbc_v8_open_payload.py",
    "scripts/verify_action_qbc_v8_remote_tag.py",
    "src/arc3_voi/action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_audit.py",
    "tests/test_action_qbc_v8_lifecycle.py",
    "tests/test_action_qbc_v8_registration.py",
}
_PAYLOAD_KEYS = {
    "schema_version",
    "treatment_id",
    "diagnostic_system_id",
    "comparison_semantics_id",
    "runtime_id",
    "preregistration_identity",
    "v6_negative_identity",
    "registration_identity",
    "execution_identity",
    "resource_counters",
    "grid_evidence",
    "expected_exterior_support",
    "rows",
    "aggregates",
    "diagnostic_complete",
    "scientific_capability_passes",
    "authorization",
    "terminal_fallback_stage",
    "candidate_payload_size_bytes",
}
_GLOBAL_STAGES = [
    "transform_action_map_invalid",
    "scientific_record_inventory_invalid",
    "grid_evidence_table_invalid",
    "expected_exterior_support_table_invalid",
    "evaluator_internal_error",
    "payload_size_limit_exceeded",
]
_ROW_KEYS = {"address", "registered_row", "disposition", "evidence", "terminal"}
_ADDRESS_KEYS = {"row_index", "row_id", "kind"}
_LAYER_KEYS = {"status", "passes", "reasons", "details"}
_TERMINAL_KEYS = {"status", "stage"}
_GRID_BLOB_KEYS = {
    "reference",
    "encoding",
    "shape",
    "byte_count",
    "data_base64",
    "sha256",
}
_SUPPORT_BLOB_KEYS = {
    "reference",
    "encoding",
    "entry_count",
    "byte_count",
    "data_base64",
    "sha256",
}
_EVIDENCE_KEYS = {
    "base_scene": {
        "pipeline",
        "raw_selector",
        "fixed_selector",
        "structural",
        "mechanism",
        "v4_counterfactual",
        "prepreregistered_reproduction",
    },
    "visual_transform": {
        "pipeline_integrity",
        "frontier_relation",
        "role_weight_relation",
        "root_transition",
        "planner_cost",
        "actual_raw_selector",
        "actual_fixed_selector",
        "isolated_action_relabel_raw",
        "isolated_action_relabel_fixed",
        "isolated_signature_pushforward_raw",
        "isolated_signature_pushforward_fixed",
        "v6_reproduction",
    },
    "order_transform": {
        "order_transform",
        "raw_selector_relation",
        "fixed_selector_relation",
    },
    "control": {"raw_control", "fixed_control"},
}
_PROCESS_KEYS = {
    "label",
    "output_path",
    "exit_code",
    "validator_exit_code",
    "start_claim",
    "start_claim_sha256",
    "validator_claim",
    "validator_claim_sha256",
    "validation_receipt",
    "validation_receipt_sha256",
    "payload_exists",
    "payload_valid",
    "payload_sha256",
    "payload_size_bytes",
}
_COMMON_RESULT_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "preparation_receipt",
    "preparation_receipt_exists",
    "preparation_receipt_read_status",
    "preparation_receipt_sha256",
    "preparation_verification_receipt",
    "preparation_verification_receipt_exists",
    "preparation_verification_receipt_read_status",
    "preparation_verification_receipt_sha256",
    "remote_verification_claim",
    "remote_verifier_claim",
    "remote_verification_receipt",
    "remote_supervisor_receipt",
    "arm_receipt",
    "lifecycle_driver_claim",
    "lifecycle_ledger",
    "process_a",
    "process_b",
    "payloads_byte_identical",
}
_RECEIPT_KEYS = _COMMON_RESULT_KEYS | {
    "published_payload_path",
    "published_payload_sha256",
    "authorization",
}
_ADMIN_KEYS = _COMMON_RESULT_KEYS | {"stage", "authorization"}
_BUNDLE_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "disposition",
    "stage",
    "underlying_stage",
    "files",
    "authorization",
    "content_sha256",
}
_FILE_KEYS = {"path", "mode", "size_bytes", "sha256", "content_base64"}
_START_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "arm_receipt_sha256",
    "lifecycle_driver_claim_sha256",
    "scientific_argv_sha256",
    "prior_validation_receipt_sha256",
    "output_path",
}
_VALIDATOR_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "lifecycle_driver_claim_sha256",
    "start_claim_sha256",
    "validator_argv_sha256",
    "payload_sha256",
}
_VALIDATION_KEYS = {
    "schema_version",
    "treatment_id",
    "label",
    "start_claim_sha256",
    "validator_claim_sha256",
    "payload_path",
    "payload_sha256",
    "payload_size_bytes",
    "status",
}
_LEDGER_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "driver_claim_sha256",
    "arm_exit_code",
    "arm_receipt_sha256",
    "sequence",
    "process_a",
    "process_b",
    "stage",
}
_LEDGER_PROCESS_KEYS = {
    "label",
    "cwd",
    "runner_argv_sha256",
    "runner_exit_code",
    "validator_argv_sha256",
    "validator_exit_code",
    "start_claim_sha256",
    "validator_claim_sha256",
    "validation_receipt_sha256",
    "output_sha256",
}
_SEQUENCE = [
    "arm_returned",
    "process_a_runner_returned",
    "process_a_validator_returned",
    "process_b_runner_returned",
    "process_b_validator_returned",
]
_PREPARATION_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "attempts",
    "authority",
    "process_a",
    "process_b",
    "command_ledger",
    "commands_sha256",
    "command_environment_sha256",
    "status",
}
_CLONE_KEYS = {
    "root",
    "root_device",
    "root_inode",
    "root_owner_uid",
    "root_mode",
    "head_sha",
    "tree_sha256",
    "raw_materialization_sha256",
    "git_status_sha256",
    "python_version",
    "uv_version",
    "environment_inventory",
    "environment_inventory_sha256",
    "venv_materialization_sha256",
    "venv_python_sha256",
    "passes",
}
_PREPARATION_VERIFICATION_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "preparation_receipt_sha256",
    "verification_argv_sha256",
    "authority",
    "process_a",
    "process_b",
    "status",
    "content_sha256",
}
_PREPARATION_VERIFICATION_CLONE_KEYS = _CLONE_KEYS - {"environment_inventory"}
_PREPARATION_COMMAND_KEYS = {
    "sequence_index", "attempt_index", "label", "phase", "cwd", "argv",
    "argv_sha256", "stdin_size_bytes", "stdin_sha256", "started", "exit_code",
    "outcome", "timed_out", "duration_milliseconds", "stdout_size_bytes",
    "stdout_sha256", "stderr_size_bytes", "stderr_sha256", "child_cleanup_passes",
}
_PREPARATION_PHASES = {
    "clone", "git_config", "checkout", "raw_audit", "environment_build", "preflight"
}
_PREPARATION_OUTCOMES = {
    "completed", "nonzero", "timeout", "stdin_limit", "stdout_limit",
    "stderr_limit", "spawn_error",
}
_DISTRIBUTION_KEYS = {"normalized_name", "version", "file_count", "files_sha256"}
_PREPARATION_ATTEMPT_KEYS = {
    "attempt_index",
    "process_a_stage",
    "process_b_stage",
    "cleanup",
    "promotion",
    "passes",
}
_PREPARATION_CLEANUP_KEYS = {"owned_paths", "removed", "passes"}
_PREPARATION_PROMOTION_KEYS = {
    "source_path",
    "destination_path",
    "source_device",
    "source_inode",
    "passes",
}
_PREPARATION_PROCESS_STAGES = {
    "not_started",
    "clone_failed",
    "raw_audit_failed",
    "environment_failed",
    "preflight_failed",
    "completed",
}
_REMOTE_CLAIM_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "supervisor_argv_sha256",
    "supervisor_script_git_blob_sha1",
    "supervisor_script_sha256",
    "verifier_script_git_blob_sha1",
    "verifier_script_sha256",
}
_REMOTE_VERIFIER_KEYS = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "verifier_argv_sha256",
}
_REMOTE_RECEIPT_KEYS = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "verifier_start_claim_sha256",
    "open_freeze_commit_sha",
    "open_freeze_tag",
    "registration_content_sha256",
    "remote_url",
    "ref",
    "python",
    "git",
    "taskkill",
    "policy",
    "attempts",
    "status",
    "selected_attempt",
    "total_duration_milliseconds",
}
_REMOTE_SUPERVISOR_KEYS = {
    "schema_version",
    "treatment_id",
    "claim_sha256",
    "verifier_start_claim_sha256",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "verifier_argv_sha256",
    "verifier_exit_code",
    "classification",
    "timed_out",
    "duration_milliseconds",
    "stdout_size_bytes",
    "stdout_sha256",
    "stdout_base64",
    "stderr_size_bytes",
    "stderr_sha256",
    "stderr_base64",
    "child_cleanup_passes",
    "remote_receipt_sha256",
    "status",
}
_REMOTE_ATTEMPT_KEYS = {
    "attempt_index",
    "exit_code",
    "classification",
    "timed_out",
    "duration_milliseconds",
    "stdout_size_bytes",
    "stdout_sha256",
    "stdout_base64",
    "stderr_size_bytes",
    "stderr_sha256",
    "stderr_base64",
    "child_cleanup_passes",
}
_REMOTE_CLASSIFICATIONS = {
    "verified",
    "retryable_empty_exit_0",
    "retryable_timeout_124",
    "retryable_git_128",
    "unexpected_output",
    "unexpected_exit",
    "stdout_limit",
    "stderr_limit",
    "child_cleanup_failed",
    "spawn_error",
    "overall_deadline",
    "post_spawn_initialization_failed",
    "stream_capture_failed",
}
_REMOTE_RETRYABLE = {
    "retryable_empty_exit_0",
    "retryable_timeout_124",
    "retryable_git_128",
}
_SUPERVISOR_CLASSIFICATIONS = {
    "verifier_completed",
    "verifier_timeout_124",
    "stdout_limit",
    "stderr_limit",
    "child_cleanup_failed",
    "spawn_error",
    "remote_receipt_missing",
    "remote_receipt_invalid",
    "post_spawn_initialization_failed",
    "stream_capture_failed",
}
_ARM_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "preparation_receipt_exists",
    "preparation_receipt_read_status",
    "preparation_receipt_sha256",
    "preparation_verification_receipt_exists",
    "preparation_verification_receipt_read_status",
    "preparation_verification_receipt_sha256",
    "remote_claim_sha256",
    "remote_verifier_claim_sha256",
    "remote_receipt_sha256",
    "remote_supervisor_receipt_sha256",
    "status",
}
_DRIVER_KEYS = {
    "schema_version",
    "treatment_id",
    "open_freeze_commit_sha",
    "registration_content_sha256",
    "remote_claim_sha256",
    "driver_argv_sha256",
}


class _FinalizationError(RuntimeError):
    """A fail-closed finalization error."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    exists: bool
    read_status: str
    raw: bytes | None
    sha256: str | None
    value: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class _Process:
    record: dict[str, Any]
    raw: bytes | None
    machine_recordable: bool = True


def _fail(message: str) -> NoReturn:
    raise _FinalizationError(message)


def _expected_evidence_mode(path: Path | str, role: str) -> int:
    if (
        set(_EVIDENCE_EXPECTED_MODES) != set(_EVIDENCE_PATHS_BY_ROLE)
        or len(set(_EVIDENCE_PATHS_BY_ROLE.values()))
        != len(_EVIDENCE_PATHS_BY_ROLE)
    ):
        _fail("evidence role/path mode registration is internally inconsistent")
    expected_path = _EVIDENCE_PATHS_BY_ROLE.get(role)
    expected_mode = _EVIDENCE_EXPECTED_MODES.get(role)
    if expected_path is None or expected_mode is None:
        _fail(f"unknown evidence role: {role}")
    if Path(path) != expected_path:
        _fail(f"{role} evidence path differs from registration")
    return expected_mode


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lower_hex(value: Any, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{name} is not {length}-character lowercase hexadecimal")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(f"{name} is not a non-negative integer")
    return value


def _actual_exit(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{name} is not an actual integer return")
    return value


def _git_blob_sha1(data: bytes) -> str:
    preimage = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(preimage, usedforsecurity=False).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_value(raw: bytes, name: str) -> Any:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise _FinalizationError(f"{name} is not strict ASCII JSON") from exc
    if _canonical(value) != raw:
        _fail(f"{name} is not one canonical JSON value")
    return value


def _parse(raw: bytes, name: str) -> dict[str, Any]:
    value = _parse_value(raw, name)
    if not isinstance(value, dict):
        _fail(f"{name} is not one canonical JSON object")
    return value


def _manifest_rows(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail(f"{name} is not a nonempty array")
    rows: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {
            "mode",
            "path",
            "git_blob_sha1",
            "sha256",
            "byte_count",
        }:
            _fail(f"{name}[{index}] has an invalid schema")
        path = item["path"]
        if (
            item["mode"] not in {"100644", "100755"}
            or not isinstance(path, str)
            or not path
        ):
            _fail(f"{name}[{index}] has an invalid mode/path")
        _lower_hex(item["git_blob_sha1"], 40, f"{name}[{index}] Git blob")
        _lower_hex(item["sha256"], 64, f"{name}[{index}] SHA-256")
        _nonnegative_int(item["byte_count"], f"{name}[{index}] byte_count")
        paths.append(path)
        rows.append(item)
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")) or len(set(paths)) != len(
        paths
    ):
        _fail(f"{name} is not uniquely bytewise path sorted")
    return rows


def _validate_source_manifest(registration: Mapping[str, Any]) -> None:
    source = registration.get("source_manifest")
    if not isinstance(source, Mapping) or set(source) != {
        "preregistration_tree",
        "open_freeze_added_files",
        "manifest_sha256",
    }:
        _fail("registration source manifest schema is invalid")
    _manifest_rows(source["preregistration_tree"], "preregistration tree")
    additions = _manifest_rows(source["open_freeze_added_files"], "open-freeze additions")
    if {row["path"] for row in additions} != _O8_ADDITIONS - {_REGISTRATION}:
        _fail("registration open-freeze manifest path set is invalid")
    preimage = {
        "preregistration_tree": source["preregistration_tree"],
        "open_freeze_added_files": source["open_freeze_added_files"],
    }
    if source["manifest_sha256"] != _sha256(_canonical(preimage)):
        _fail("registration source manifest digest is invalid")


def _validate_manifest_against_tree(
    root: Path,
    commit: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    exact_tree: bool,
) -> None:
    entries: dict[str, tuple[str, str]] = {}
    listing = _git(root, "ls-tree", "-rz", "--full-tree", commit)
    for record in listing.split(b"\0"):
        if not record:
            continue
        identity, raw_path = record.split(b"\t", 1)
        mode, kind, oid = identity.decode("ascii").split(" ")
        path = raw_path.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"} or path in entries:
            _fail("registered source commit tree is not an ordinary unique blob tree")
        entries[path] = (mode, oid)
    paths = [str(row["path"]) for row in rows]
    if exact_tree and set(paths) != set(entries):
        _fail("preregistration manifest path set differs from its Git tree")
    for row in rows:
        path = str(row["path"])
        identity = entries.get(path)
        if identity != (row["mode"], row["git_blob_sha1"]):
            _fail(f"source manifest Git identity differs at {path}")
        raw = _git(root, "cat-file", "blob", row["git_blob_sha1"])
        if len(raw) != row["byte_count"] or _sha256(raw) != row["sha256"]:
            _fail(f"source manifest byte identity differs at {path}")


def _expected_finalizer_argv() -> list[str]:
    return [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "300s",
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION,
        "--preparation-receipt",
        _PREPARATION,
        "--preparation-verification-receipt",
        _PREPARATION_VERIFICATION,
        "--remote-claim",
        _REMOTE_CLAIM,
        "--remote-verifier-claim",
        _REMOTE_VERIFIER_CLAIM,
        "--remote-receipt",
        _REMOTE_RECEIPT,
        "--remote-supervisor-receipt",
        _REMOTE_SUPERVISOR,
        "--arm-receipt",
        _ARM,
        "--driver-claim",
        _DRIVER,
        "--lifecycle-ledger",
        _LEDGER,
        "--process-a-start-claim",
        _PROCESS_A_START,
        "--process-a-validator-claim",
        _PROCESS_A_VALIDATOR,
        "--process-a-validation-receipt",
        _PROCESS_A_VALIDATION,
        "--process-a",
        _PROCESS_A,
        "--process-b-start-claim",
        _PROCESS_B_START,
        "--process-b-validator-claim",
        _PROCESS_B_VALIDATOR,
        "--process-b-validation-receipt",
        _PROCESS_B_VALIDATION,
        "--process-b",
        _PROCESS_B,
        "--bundle",
        _BUNDLE,
    ]


def _expected_arm_argv() -> list[str]:
    return [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "120s",
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/prepare_action_qbc_v8_open.py",
        "arm",
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION,
        "--execution-root",
        str(_EXECUTION_ROOT),
        "--preparation-receipt",
        _PREPARATION,
        "--preparation-verification-receipt",
        _PREPARATION_VERIFICATION,
        "--windows-claim",
        "/mnt/d/kaggle competitions/"
        "arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim-v4.json",
        "--windows-verifier-start-claim",
        "/mnt/d/kaggle competitions/"
        "arc3-crosslevel-voi-action-qbc-v8-remote-verifier-start-claim-v4.json",
        "--windows-remote-receipt",
        "/mnt/d/kaggle competitions/arc3-crosslevel-voi-action-qbc-v8-remote-verification-v4.json",
        "--windows-supervisor-receipt",
        "/mnt/d/kaggle competitions/"
        "arc3-crosslevel-voi-action-qbc-v8-remote-verification-supervisor-v4.json",
        "--arm-receipt",
        _ARM,
    ]


def _expected_lifecycle_argv() -> list[str]:
    return [
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "execute",
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION,
        "--execution-root",
        str(_EXECUTION_ROOT),
        "--preparation-receipt",
        _PREPARATION,
        "--preparation-verification-receipt",
        _PREPARATION_VERIFICATION,
        "--windows-claim",
        "/mnt/d/kaggle competitions/"
        "arc3-crosslevel-voi-action-qbc-v8-remote-verification-claim-v4.json",
        "--remote-claim",
        _REMOTE_CLAIM,
        "--remote-verifier-claim",
        _REMOTE_VERIFIER_CLAIM,
        "--remote-receipt",
        _REMOTE_RECEIPT,
        "--remote-supervisor-receipt",
        _REMOTE_SUPERVISOR,
        "--arm-receipt",
        _ARM,
        "--driver-claim",
        _DRIVER,
        "--ledger",
        _LEDGER,
    ]


def _expected_scientific_argv() -> list[str]:
    return [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=15s",
        "2700s",
        ".venv/bin/python3",
        "-I",
        "-B",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION,
        "--preparation-verification-receipt",
        _PREPARATION_VERIFICATION,
        "--arm-receipt",
        _ARM,
        "--driver-claim",
        _DRIVER,
        "--label",
        "<LABEL>",
        "--start-claim",
        "<START_CLAIM>",
        "--prior-validation-receipt",
        "<PRIOR_VALIDATION_OR_NULL>",
        "--compute-deadline-seconds",
        "2100",
        "--wall-time-seconds",
        "2400",
        "--output",
        "<OUTPUT_PATH>",
    ]


def _expected_validator_argv() -> list[str]:
    return [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "300s",
        ".venv/bin/python3",
        "-I",
        "-B",
        "scripts/validate_action_qbc_v8_open_payload.py",
        "--repository-root",
        ".",
        "--registration",
        _REGISTRATION,
        "--arm-receipt",
        _ARM,
        "--driver-claim",
        _DRIVER,
        "--label",
        "<LABEL>",
        "--start-claim",
        "<START_CLAIM>",
        "--validator-claim",
        "<VALIDATOR_CLAIM>",
        "--validation-receipt",
        "<VALIDATION_RECEIPT>",
        "--payload",
        "<OUTPUT_PATH>",
    ]


def _expected_post_preparation_argv() -> list[str]:
    return [
        "/usr/bin/python3", "-I", "-B",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "--repository-root", ".", "--registration", _REGISTRATION,
        "--verify-preparation", "--preparation-receipt", _PREPARATION,
        "--verification-receipt", _PREPARATION_VERIFICATION,
    ]


def _expected_result_publisher_argv() -> list[str]:
    return [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "600s",
        "/usr/bin/python3", "-I", "-B",
        "scripts/execute_action_qbc_v8_open_lifecycle.py", "publish",
        "--repository-root", ".", "--registration", _REGISTRATION,
        "--driver-claim", _DRIVER,
        "--lifecycle-ledger", _LEDGER,
        "--finalization-bundle", _BUNDLE,
        "--emergency-bundle", str(_EXECUTION_ROOT / "emergency-result-bundle.json"),
        "--control-time-seconds", "570",
    ]


def _expected_remote_policy() -> dict[str, Any]:
    environment = {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "COMSPEC": r"C:\Windows\System32\cmd.exe",
        "TEMP": r"C:\Users\User\AppData\Local\Temp",
        "TMP": r"C:\Users\User\AppData\Local\Temp",
        "PATH": (
            r"C:\Users\User\anaconda3\Library\mingw64\bin;"
            r"C:\Users\User\anaconda3\Library\usr\bin;"
            r"C:\Users\User\anaconda3\Library\bin;"
            r"C:\Windows\System32;C:\Windows"
        ),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
        "XDG_CONFIG_HOME": r"D:\kaggle competitions\arc3-v8-nonexistent-home",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "NUL",
        "GIT_CONFIG_COUNT": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "NUL",
        "SSH_ASKPASS": "NUL",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    return {
        "max_attempts": 3,
        "attempt_timeout_seconds": 120,
        "retry_delay_seconds": 15,
        "overall_deadline_seconds": 390,
        "verifier_child_deadline_seconds": 430,
        "supervisor_deadline_seconds": 480,
        "supervisor_receipt_reserve_seconds": 20,
        "stdout_cap_bytes": 4_096,
        "stderr_cap_bytes": 16_384,
        "child_cleanup_timeout_seconds": 30,
        "windows_job_kill_on_close": True,
        "git_child_cwd": r"D:\kaggle competitions",
        "git_environment": environment,
    }


def _validate_execution_contract(registration: Mapping[str, Any]) -> Mapping[str, Any]:
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping) or set(execution) != _EXECUTION_KEYS:
        _fail("registration execution contract schema is invalid")
    if execution.get("windows_repository_contract") != _WINDOWS_REPOSITORY_CONTRACT:
        _fail("registration Windows repository contract differs from P8v7")
    expected_paths = {
        "authority_root": str(_AUTHORITY_ROOT),
        "execution_root": str(_EXECUTION_ROOT),
        "finalization_bundle_path": _BUNDLE,
        "preparation_receipt_path": _PREPARATION,
        "preparation_verification_receipt_path": _PREPARATION_VERIFICATION,
        "arm_receipt_path": _ARM,
        "lifecycle_driver_claim_path": _DRIVER,
        "lifecycle_ledger_path": _LEDGER,
        "process_a_root": str(_EXECUTION_ROOT / "processes/process-a"),
        "process_a_output": _PROCESS_A,
        "process_a_start_claim": _PROCESS_A_START,
        "process_a_validator_claim": _PROCESS_A_VALIDATOR,
        "process_a_validation_receipt": _PROCESS_A_VALIDATION,
        "process_b_root": str(_EXECUTION_ROOT / "processes/process-b"),
        "process_b_output": _PROCESS_B,
        "process_b_start_claim": _PROCESS_B_START,
        "process_b_validator_claim": _PROCESS_B_VALIDATOR,
        "process_b_validation_receipt": _PROCESS_B_VALIDATION,
    }
    if any(execution.get(key) != value for key, value in expected_paths.items()):
        _fail("registration execution paths differ from the finalizer contract")
    if (
        execution.get("administrative_stage_order")
        != {
            "underlying_order": _UNDERLYING_ORDER,
            "disposition_overrides": [
                "receipt_finalization_failed",
                "finalizer_process_failed",
            ],
        }
        or execution.get("process_labels") != ["A", "B"]
        or execution.get("registered_start_count") != 2
        or execution.get("third_start_allowed") is not False
        or execution.get("local_git_timeout_seconds") != _GIT_TIMEOUT
        or execution.get("compute_deadline_seconds") != 2_100
        or execution.get("wall_time_seconds") != 2_400
        or execution.get("hard_timeout_seconds") != 2_700
        or execution.get("arm_timeout_seconds") != 120
        or execution.get("driver_deadline_seconds") != 8_400
        or execution.get("finalizer_timeout_seconds") != 300
        or execution.get("payload_validator_timeout_seconds") != 300
        or execution.get("remote_policy") != _expected_remote_policy()
        or execution.get("preparation_command_environment")
        != {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/bansarinejad",
            "XDG_CONFIG_HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_COUNT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_CACHE_DIR": "/home/bansarinejad/.cache/uv",
            "UV_NO_PROGRESS": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
        or execution.get("preparation_command_policy")
        != {
            "default_timeout_seconds": 60,
            "environment_timeout_seconds": 600,
            "term_grace_seconds": 5,
            "kill_grace_seconds": 5,
            "stdin_cap_bytes": 1_048_576,
            "stdout_cap_bytes": 134_217_728,
            "stderr_cap_bytes": 1_048_576,
        }
        or execution.get("arm_argv") != _expected_arm_argv()
        or execution.get("lifecycle_driver_argv") != _expected_lifecycle_argv()
        or execution.get("scientific_argv_template") != _expected_scientific_argv()
        or execution.get("payload_validator_argv_template") != _expected_validator_argv()
        or execution.get("finalizer_argv_template") != _expected_finalizer_argv()
        or execution.get("post_preparation_validation_argv")
        != _expected_post_preparation_argv()
        or execution.get("result_publisher_argv") != _expected_result_publisher_argv()
        or execution.get("finalizer_cwd") != str(_AUTHORITY_ROOT)
    ):
        _fail("registration fixed execution semantics are invalid")
    hashes = execution.get("argv_hashes")
    if not isinstance(hashes, Mapping) or set(hashes) != _ARGV_HASH_KEYS:
        _fail("registration argv hash schema is invalid")
    preimages = {
        "arm": execution.get("arm_argv"),
        "bootstrap": execution.get("bootstrap_steps"),
        "environment_build": execution.get("environment_build_argv"),
        "finalizer": execution.get("finalizer_argv_template"),
        "lifecycle_driver": execution.get("lifecycle_driver_argv"),
        "linux_host_launcher": execution.get("linux_host_launcher"),
        "payload_validator": execution.get("payload_validator_argv_template"),
        "post_preparation_validation": execution.get("post_preparation_validation_argv"),
        "preflight": execution.get("preflight_argvs"),
        "preparation": execution.get("preparation_argv"),
        "producer": execution.get("producer_argv"),
        "reconstructor": execution.get("reconstructor_argv"),
        "remote_supervisor": execution.get("remote_supervisor_argv"),
        "remote_verifier": execution.get("remote_verifier_argv"),
        "result_publisher": execution.get("result_publisher_argv"),
        "result_ref_transaction": execution.get("result_ref_transaction"),
        "scientific": execution.get("scientific_argv_template"),
        "tests": execution.get("test_argvs"),
    }
    for key, preimage in preimages.items():
        _lower_hex(hashes[key], 64, f"argv_hashes.{key}")
        if hashes[key] != _sha256(_canonical(preimage)):
            _fail(f"registration {key} argv hash is invalid")
    return execution


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
    )


def _file_change_identity(metadata: os.stat_result) -> tuple[int, int]:
    # Windows ctime is not a stable mutation clock across path-stat and fstat.  NTFS
    # mtime is 100 ns resolution, so retain that clock after exact normalization.
    if os.name == "nt":
        return (metadata.st_mtime_ns // 100, 0)
    return (metadata.st_mtime_ns, metadata.st_ctime_ns)


def _is_reparse_point(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _permitted_plain_metadata(metadata: os.stat_result, maximum: int) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_point(metadata)
        and 0 <= metadata.st_size <= maximum
    )


def _bounded_descriptor_bytes(descriptor: int, maximum: int, name: str) -> bytes:
    data = bytearray()
    while True:
        allowance = maximum + 1 - len(data)
        if allowance <= 0:
            _fail(f"{name} exceeds its byte limit")
        chunk = os.read(descriptor, min(1 << 20, allowance))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > maximum:
            _fail(f"{name} exceeds its byte limit")


def _plain(path: Path, name: str, *, maximum: int = _MAX_JSON) -> bytes:
    candidate = path if path.is_absolute() else Path.cwd() / path
    parent = _open_directory_nofollow(candidate.parent, f"{name} parent")
    try:
        before_path = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
    except OSError as exc:
        os.close(parent)
        raise _FinalizationError(f"{name} is unavailable") from exc
    if not _permitted_plain_metadata(before_path, maximum):
        os.close(parent)
        _fail(f"{name} is not a permitted plain file")
    flags = (
        os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(candidate.name, flags, dir_fd=parent)
    except OSError as exc:
        os.close(parent)
        raise _FinalizationError(f"{name} cannot be safely opened") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not _permitted_plain_metadata(opened, maximum)
            or _file_identity(before_path) != _file_identity(opened)
            or _file_change_identity(before_path) != _file_change_identity(opened)
        ):
            _fail(f"{name} changed before it was opened")
        data = _bounded_descriptor_bytes(descriptor, maximum, name)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _bounded_descriptor_bytes(descriptor, maximum, name) != data:
            _fail(f"{name} changed between descriptor reads")
        after_descriptor = os.fstat(descriptor)
    except OSError as exc:
        os.close(parent)
        raise _FinalizationError(f"{name} cannot be read") from exc
    except _FinalizationError:
        os.close(parent)
        raise
    finally:
        os.close(descriptor)
    try:
        after_path = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
    except OSError as exc:
        os.close(parent)
        raise _FinalizationError(f"{name} changed while being read") from exc
    try:
        if (
            not _permitted_plain_metadata(after_descriptor, maximum)
            or not _permitted_plain_metadata(after_path, maximum)
            or _file_identity(opened) != _file_identity(after_descriptor)
            or _file_identity(after_descriptor) != _file_identity(after_path)
            or _file_change_identity(opened) != _file_change_identity(after_descriptor)
            or _file_change_identity(after_descriptor) != _file_change_identity(after_path)
            or len(data) != after_descriptor.st_size
        ):
            _fail(f"{name} changed while being read")
        return data
    finally:
        os.close(parent)


def _open_directory_nofollow(path: Path, name: str) -> int:
    if not path.is_absolute():
        _fail(f"{name} path is not absolute")
    components = path.parts[1:]
    if any(
        not component or component in {".", ".."} or "/" in component or "\x00" in component
        for component in components
    ):
        _fail(f"{name} path has an unsafe component")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path.anchor, flags)
        for component in components:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise _FinalizationError(f"cannot open {name} without following links") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        _fail(f"{name} is not a directory")
    return descriptor


def _artifact(
    path: str,
    *,
    role: str,
    name: str,
    keys: set[str] | None = None,
    schema: str | None = None,
) -> _Artifact:
    candidate = Path(path)
    expected_mode = _expected_evidence_mode(candidate, role)
    if not candidate.is_absolute() or candidate.name in {"", ".", ".."}:
        _fail(f"{name} path is not one fixed absolute basename")
    try:
        parent = _open_directory_nofollow(candidate.parent, f"{name} parent")
    except _FinalizationError:
        return _Artifact(True, "read_error", None, None, None)
    descriptor: int | None = None
    try:
        try:
            names = os.listdir(parent)
        except OSError:
            return _Artifact(True, "read_error", None, None, None)
        if candidate.name not in names:
            return _Artifact(False, "absent", None, None, None)
        try:
            before = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
        except OSError:
            return _Artifact(True, "read_error", None, None, None)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or (os.name == "posix" and before.st_uid != os.getuid())
            or (os.name == "posix" and stat.S_IMODE(before.st_mode) != expected_mode)
        ):
            return _Artifact(True, "unsafe_type", None, None, None)
        if before.st_size < 0 or before.st_size > _PAYLOAD_CAP:
            return _Artifact(True, "oversized", None, None, None)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(candidate.name, flags, dir_fd=parent)
            opened = os.fstat(descriptor)
            raw = _bounded_descriptor_bytes(descriptor, _PAYLOAD_CAP, name)
            after = os.fstat(descriptor)
            after_path = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
        except (_FinalizationError, OSError):
            return _Artifact(True, "read_error", None, None, None)
        def identity(
            value: os.stat_result,
        ) -> tuple[int, int, int, int, int, int, int, int, int]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_uid,
                value.st_nlink,
                stat.S_IFMT(value.st_mode),
                stat.S_IMODE(value.st_mode),
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )
        if (
            identity(before) != identity(opened)
            or identity(opened) != identity(after)
            or identity(after) != identity(after_path)
            or len(raw) != after.st_size
        ):
            return _Artifact(True, "changed_during_read", None, None, None)
        digest = _sha256(raw)
        try:
            value = _parse(raw, name)
            if keys is not None and set(value) != keys:
                value = None
            if value is not None and schema is not None and value.get("schema_version") != schema:
                value = None
            if value is not None and value.get("treatment_id") != _TREATMENT_ID:
                value = None
        except _FinalizationError:
            value = None
        return _Artifact(True, "readable", raw, digest, value)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _git_environment(root: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/bansarinejad",
        "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_COUNT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_CACHE_DIR": "/home/bansarinejad/.cache/uv",
        "UV_NO_PROGRESS": "1",
        "UV_PYTHON_DOWNLOADS": "never",
    }


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            ["/usr/bin/git", "--no-replace-objects", *arguments],
            cwd=root,
            env=_git_environment(root),
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _stderr = process.communicate(
            input=input_bytes,
            timeout=max(0.0, started + _GIT_TIMEOUT - time.monotonic()),
        )
    except subprocess.TimeoutExpired as exc:
        assert process is not None
        cleanup_started = time.monotonic()
        term_deadline = cleanup_started + 5
        kill_deadline = cleanup_started + 10
        process.terminate()
        try:
            process.wait(timeout=max(0.0, term_deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=max(0.0, kill_deadline - time.monotonic()))
            except subprocess.TimeoutExpired as cleanup_exc:
                raise _FinalizationError(
                    "registered local Git child cleanup failed"
                ) from cleanup_exc
        raise _FinalizationError("registered local Git plumbing timed out") from exc
    except OSError as exc:
        raise _FinalizationError("registered local Git plumbing failed") from exc
    if process.returncode != 0:
        _fail("registered local Git plumbing returned nonzero")
    return stdout


def _validate_object_pack_sources(root: Path) -> None:
    """Reject unsafe object-pack paths and every promisor sidecar without following links."""

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptors: list[int] = []
    try:
        try:
            git_descriptor = os.open(root / ".git", flags)
            descriptors.append(git_descriptor)
            objects_descriptor = os.open("objects", flags, dir_fd=git_descriptor)
            descriptors.append(objects_descriptor)
            pack_descriptor = os.open("pack", flags, dir_fd=objects_descriptor)
            descriptors.append(pack_descriptor)
        except OSError as exc:
            raise _FinalizationError(
                "local Git object-pack directory is unavailable as a no-follow directory"
            ) from exc

        for descriptor in descriptors:
            try:
                metadata = os.fstat(descriptor)
            except OSError as exc:
                raise _FinalizationError(
                    "cannot inspect local Git object-pack directory ancestry"
                ) from exc
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                _fail("local Git object-pack directory ancestry is not owner-controlled")

        try:
            with os.scandir(pack_descriptor) as entries:
                for entry in entries:
                    if entry.name.endswith(".promisor"):
                        _fail("promisor object-pack sidecar is forbidden")
        except OSError as exc:
            raise _FinalizationError(
                "cannot inspect local Git object-pack directory"
            ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _git_repository_controls(root: Path) -> bool:
    expected = {
        "core.repositoryformatversion": "0",
        "core.filemode": "true",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "core.autocrlf": "false",
        "core.eol": "lf",
        "core.safecrlf": "true",
    }
    try:
        _validate_object_pack_sources(root)
        raw = _git(root, "config", "--local", "--null", "--list")
        observed: dict[str, str] = {}
        for record in raw.split(b"\0"):
            if not record:
                continue
            key_raw, separator, value_raw = record.partition(b"\n")
            if not separator:
                return False
            key = key_raw.decode("utf-8", "strict")
            value = value_raw.decode("utf-8", "strict")
            if key in observed:
                return False
            observed[key] = value
        if observed != expected:
            return False
        forbidden = (
            root / ".git/objects/info/alternates",
            root / ".git/objects/info/http-alternates",
            root / ".git/info/grafts",
            root / ".git/shallow",
            root / ".git/refs/replace",
        )
        if any(path.exists() or path.is_symlink() for path in forbidden):
            return False
        packed = root / ".git/packed-refs"
        return not (
            packed.exists()
            and b"refs/replace/" in _plain(packed, "packed refs", maximum=16_777_216)
        )
    except (OSError, UnicodeError, _FinalizationError):
        return False


def _strict_relative_parts(value: str, name: str) -> tuple[str, ...]:
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise _FinalizationError(f"{name} is not strict UTF-8") from exc
    if not value or value.startswith("/") or "\\" in value or "\x00" in value:
        _fail(f"{name} is not a safe relative path")
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        _fail(f"{name} has a noncanonical component")
    return parts


def _read_relative_regular(root_descriptor: int, parts: Sequence[str], name: str) -> bytes:
    if not parts:
        _fail(f"{name} has no path components")
    descriptors: list[int] = []
    try:
        parent = os.dup(root_descriptor)
        descriptors.append(parent)
        directory_flags = (
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        for component in parts[:-1]:
            parent = os.open(component, directory_flags, dir_fd=parent)
            descriptors.append(parent)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent
        )
        descriptors.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _PAYLOAD_CAP:
            _fail(f"{name} is not a bounded regular file")
        raw = _bounded_descriptor_bytes(descriptor, _PAYLOAD_CAP, name)
        if os.fstat(descriptor).st_size != len(raw):
            _fail(f"{name} changed while read")
        return raw
    except OSError as exc:
        raise _FinalizationError(f"{name} cannot be opened without following links") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _venv_materialization_sha256(root: Path) -> str:
    venv = root / ".venv"
    rows: list[dict[str, Any]] = []
    try:
        for directory, names, files in os.walk(venv, topdown=True, followlinks=False):
            current = Path(directory)
            entries = sorted([*names, *files], key=lambda item: item.encode("utf-8", "strict"))
            traversable: list[str] = []
            for entry in entries:
                entry.encode("utf-8", "strict")
                path = current / entry
                relative = path.relative_to(venv).as_posix()
                _strict_relative_parts(relative, "venv inventory path")
                metadata = path.stat(follow_symlinks=False)
                mode = stat.S_IMODE(metadata.st_mode)
                if stat.S_ISLNK(metadata.st_mode):
                    target = os.readlink(path)
                    target.encode("utf-8", "strict")
                    rows.append(
                        {"path": relative, "type": "symlink", "mode": mode,
                         "size_bytes": None, "sha256": None, "symlink_target": target}
                    )
                elif stat.S_ISDIR(metadata.st_mode):
                    rows.append(
                        {"path": relative, "type": "directory", "mode": mode,
                         "size_bytes": None, "sha256": None, "symlink_target": None}
                    )
                    if entry in names:
                        traversable.append(entry)
                elif stat.S_ISREG(metadata.st_mode):
                    raw = _plain(path, f"venv entry {relative}")
                    rows.append(
                        {"path": relative, "type": "regular", "mode": mode,
                         "size_bytes": len(raw), "sha256": _sha256(raw),
                         "symlink_target": None}
                    )
                else:
                    _fail(f"venv contains special entry {relative}")
            names[:] = traversable
    except (OSError, UnicodeError, ValueError) as exc:
        raise _FinalizationError("cannot enumerate the complete venv materialization") from exc
    rows.sort(key=lambda row: str(row["path"]).encode("utf-8"))
    if len({row["path"] for row in rows}) != len(rows):
        _fail("venv inventory contains duplicate paths")
    return _sha256(_canonical(rows))


def _venv_python_sha256(root: Path) -> str:
    candidate = root / ".venv/bin/python3"
    seen: set[str] = set()
    for _ in range(32):
        marker = str(candidate)
        if marker in seen:
            _fail("venv Python link chain loops")
        seen.add(marker)
        metadata = candidate.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(candidate)
            target.encode("utf-8", "strict")
            target_path = Path(target)
            candidate = target_path if target_path.is_absolute() else candidate.parent / target_path
            continue
        if not stat.S_ISREG(metadata.st_mode):
            _fail("venv Python does not resolve to a regular executable")
        return _sha256(_plain(candidate, "resolved venv Python"))
    _fail("venv Python link chain is too deep")


def _environment_inventory(root: Path) -> tuple[list[dict[str, Any]], str]:
    venv = root / ".venv"
    venv_descriptor = _open_directory_nofollow(venv, "venv root")
    site_prefix = ("lib", "python3.12", "site-packages")
    site_descriptor = os.dup(venv_descriptor)
    try:
        for component in site_prefix:
            child = os.open(
                component,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=site_descriptor,
            )
            os.close(site_descriptor)
            site_descriptor = child
        dist_infos = sorted(
            [name for name in os.listdir(site_descriptor) if name.endswith(".dist-info")],
            key=lambda item: item.encode("utf-8", "strict"),
        )
        result: list[dict[str, Any]] = []
        global_paths: set[str] = set()
        normalized_names: set[str] = set()
        for dist_info in dist_infos:
            dist_info.encode("utf-8", "strict")
            dist_descriptor = os.open(
                dist_info,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=site_descriptor,
            )
            try:
                metadata_raw = _read_relative_regular(dist_descriptor, ("METADATA",), "METADATA")
                record_raw = _read_relative_regular(dist_descriptor, ("RECORD",), "RECORD")
            finally:
                os.close(dist_descriptor)
            metadata = BytesParser(policy=email.policy.compat32).parsebytes(metadata_raw)
            raw_name = metadata.get("Name")
            raw_version = metadata.get("Version")
            if not isinstance(raw_name, str) or not isinstance(raw_version, str):
                _fail("distribution metadata lacks Name/Version")
            normalized_name = re.sub(r"[-_.]+", "-", raw_name).lower()
            version = raw_version.strip()
            if (
                not normalized_name or not normalized_name.isascii()
                or not version or not version.isascii()
                or normalized_name in normalized_names
            ):
                _fail("distribution identity is invalid or duplicated")
            normalized_names.add(normalized_name)
            rows = csv.reader(io.StringIO(record_raw.decode("utf-8", "strict"), newline=""))
            files: list[dict[str, Any]] = []
            for row in rows:
                if len(row) != 3 or not row[0] or "\\" in row[0] or row[0].startswith("/"):
                    _fail("distribution RECORD row is invalid")
                components = [*site_prefix]
                for component in row[0].split("/"):
                    if component in {"", "."}:
                        continue
                    if component == "..":
                        if not components:
                            _fail("distribution RECORD escapes the venv")
                        components.pop()
                    else:
                        component.encode("utf-8", "strict")
                        components.append(component)
                relative = "/".join(components)
                parts = _strict_relative_parts(relative, "normalized RECORD path")
                if relative in global_paths:
                    _fail("duplicate normalized RECORD path")
                global_paths.add(relative)
                raw = _read_relative_regular(venv_descriptor, parts, f"RECORD file {relative}")
                files.append({"path": relative, "size_bytes": len(raw), "sha256": _sha256(raw)})
            files.sort(key=lambda row: str(row["path"]).encode("utf-8"))
            result.append(
                {"normalized_name": normalized_name, "version": version,
                 "file_count": len(files), "files_sha256": _sha256(_canonical(files))}
            )
        result.sort(key=lambda row: str(row["normalized_name"]).encode("utf-8"))
        return result, _sha256(_canonical(result))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        raise _FinalizationError("cannot recompute the installed-distribution inventory") from exc
    finally:
        os.close(site_descriptor)
        os.close(venv_descriptor)


def _run_identity_tool(root: Path, argv: Sequence[str], name: str) -> bytes:
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            list(argv), cwd=root, env=_git_environment(root), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, _stderr = process.communicate(
            timeout=max(0.0, started + _GIT_TIMEOUT - time.monotonic())
        )
    except subprocess.TimeoutExpired as exc:
        assert process is not None
        cleanup_started = time.monotonic()
        term_deadline = cleanup_started + 5
        kill_deadline = cleanup_started + 10
        process.terminate()
        try:
            process.wait(timeout=max(0.0, term_deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=max(0.0, kill_deadline - time.monotonic()))
        raise _FinalizationError(f"{name} timed out") from exc
    except OSError as exc:
        raise _FinalizationError(f"{name} could not start") from exc
    if process.returncode != 0:
        _fail(f"{name} returned nonzero")
    return stdout


def _live_clone_matches_receipt(
    root: Path,
    clone: Mapping[str, Any],
    *,
    commit: str,
    environment: bool,
) -> bool:
    try:
        if not _git_repository_controls(root):
            return False
        if _git(root, "rev-parse", "HEAD") != f"{commit}\n".encode("ascii"):
            return False
        tag_ref = f"refs/tags/{_OPEN_FREEZE_TAG}"
        if _git(root, "cat-file", "-t", tag_ref) != b"commit\n":
            return False
        if _git(root, "rev-parse", tag_ref) != f"{commit}\n".encode("ascii"):
            return False
        tree_rows: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        tracked: set[str] = set()
        listing = _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit)
        for record in listing.split(b"\0"):
            if not record:
                continue
            identity, separator, path_raw = record.partition(b"\t")
            fields = identity.split()
            if not separator or len(fields) != 4 or fields[1] != b"blob":
                return False
            mode = fields[0].decode("ascii")
            oid = fields[2].decode("ascii")
            size = int(fields[3])
            relative = path_raw.decode("utf-8", "strict")
            _strict_relative_parts(relative, "tracked path")
            path = root.joinpath(*relative.split("/"))
            raw = _plain(path, f"tracked file {relative}")
            if len(raw) != size or _git(root, "cat-file", "blob", oid) != raw:
                return False
            row = {"mode": mode, "path": relative, "git_blob_sha1": oid}
            tree_rows.append(row)
            raw_rows.append({**row, "sha256": _sha256(raw), "size_bytes": len(raw)})
            tracked.add(relative)
        tree_rows.sort(key=lambda row: str(row["path"]).encode("utf-8"))
        raw_rows.sort(key=lambda row: str(row["path"]).encode("utf-8"))
        status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if status:
            return False
        if (
            clone.get("tree_sha256") != _sha256(_canonical(tree_rows))
            or clone.get("raw_materialization_sha256") != _sha256(_canonical(raw_rows))
            or clone.get("git_status_sha256") != _sha256(status)
        ):
            return False
        for directory, names, files in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            for name in list(names):
                path = current / name
                relative = path.relative_to(root).as_posix()
                metadata = path.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    return False
                if current == root and name in ({".git", ".venv"} if environment else {".git"}):
                    names.remove(name)
                    continue
                if not any(item.startswith(relative + "/") for item in tracked):
                    return False
            for name in files:
                if (current / name).relative_to(root).as_posix() not in tracked:
                    return False
        if not environment:
            return True
        inventory, inventory_sha = _environment_inventory(root)
        return not (
            clone.get("environment_inventory") != inventory
            or clone.get("environment_inventory_sha256") != inventory_sha
            or clone.get("venv_materialization_sha256") != _venv_materialization_sha256(root)
            or clone.get("venv_python_sha256") != _venv_python_sha256(root)
            or _run_identity_tool(root, [".venv/bin/python3", "--version"], "venv Python")
            != b"Python 3.12.13\n"
            or _run_identity_tool(root, ["/usr/local/bin/uv", "--version"], "uv")
            != b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n"
        )
    except (OSError, UnicodeError, ValueError, _FinalizationError):
        return False


def _commit_line(raw: bytes, name: str) -> str:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _FinalizationError(f"{name} is not ASCII") from exc
    if not text.endswith("\n") or text.count("\n") != 1:
        _fail(f"{name} is not one exact commit line")
    return _lower_hex(text[:-1], 40, name)


def _expected_name_status(paths: Sequence[str]) -> bytes:
    return b"".join(
        b"A\0" + path.encode("utf-8") + b"\0"
        for path in sorted(paths, key=lambda item: item.encode("utf-8"))
    )


def _expected_forward_reset_name_status(paths: Sequence[str], document: str) -> bytes:
    changes = [("D", path) for path in paths]
    changes.append(("A", document))
    return b"".join(
        status.encode("ascii") + b"\0" + path.encode("utf-8") + b"\0"
        for status, path in sorted(changes, key=lambda item: item[1].encode("utf-8"))
    )


def _has_exact_parent(root: Path, commit: str, parent: str) -> bool:
    return _git(root, "rev-list", "--parents", "-n", "1", commit) == (
        f"{commit} {parent}\n".encode("ascii")
    )


def _repository_and_registration(root: Path) -> tuple[str, dict[str, Any], bytes]:
    _validate_object_pack_sources(root)
    for tag, expected, name in (
        (_P8V1_TAG, _P8V1_COMMIT, "P8v1"),
        (_P8V2_TAG, _P8V2_COMMIT, "P8v2"),
        (_P8V3_TAG, _P8V3_COMMIT, "P8v3"),
        (_P8V4_TAG, _P8V4_COMMIT, "P8v4"),
    ):
        ref = f"refs/tags/{tag}"
        if (
            _git(root, "cat-file", "-t", ref) != b"commit\n"
            or _git(root, "rev-parse", ref) != f"{expected}\n".encode("ascii")
        ):
            _fail(f"{name} lightweight tag identity is invalid")
    for child, parent, name in (
        (_P8V1_COMMIT, _R7_COMMIT, "P8v1"),
        (_P8V2_COMMIT, _P8V1_COMMIT, "P8v2"),
        (_P8V3_COMMIT, _P8V2_COMMIT, "P8v3"),
        (_P8V4_COMMIT, _P8V3_COMMIT, "P8v4"),
    ):
        if not _has_exact_parent(root, child, parent):
            _fail(f"{name} is not the exact registered direct child")
    if _git(
        root, "diff", "--name-status", "--no-renames", "-z", _R7_COMMIT, _P8V1_COMMIT
    ) != b"A\0" + _P8V2_DOCUMENT.encode("utf-8") + b"\0":
        _fail("R7..P8v1 is not the one-document addition")
    if _git(
        root, "diff", "--name-status", "--no-renames", "-z", _P8V1_COMMIT, _P8V2_COMMIT
    ) != b"M\0" + _P8V2_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v1..P8v2 is not the one-document correction")
    if _git(
        root, "diff", "--name-status", "--no-renames", "-z",
        _P8V2_COMMIT, _P8V3_COMMIT,
    ) != b"A\0" + _P8V3_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v2..P8v3 is not the one-document correction")
    if _git(
        root, "diff", "--name-status", "--no-renames", "-z",
        _P8V3_COMMIT, _P8V4_COMMIT,
    ) != b"A\0" + _P8V4_DOCUMENT.encode("utf-8") + b"\0":
        _fail("P8v3..P8v4 is not the one-document correction")
    for commit_id, path, blob, digest, count, name in (
        (
            _P8V1_COMMIT, _P8V2_DOCUMENT, _P8V1_DOCUMENT_BLOB,
            _P8V1_DOCUMENT_SHA256, None, "P8v1",
        ),
        (
            _P8V2_COMMIT, _P8V2_DOCUMENT, _P8V2_DOCUMENT_BLOB,
            _P8V2_DOCUMENT_SHA256, _P8V2_DOCUMENT_BYTE_COUNT, "P8v2",
        ),
        (
            _P8V3_COMMIT, _P8V3_DOCUMENT,
            _P8V3_DOCUMENT_BLOB, _P8V3_DOCUMENT_SHA256,
            _P8V3_DOCUMENT_BYTE_COUNT, "P8v3",
        ),
        (
            _P8V4_COMMIT, _P8V4_DOCUMENT,
            _P8V4_DOCUMENT_BLOB, _P8V4_DOCUMENT_SHA256,
            _P8V4_DOCUMENT_BYTE_COUNT, "P8v4",
        ),
    ):
        raw = _git(root, "cat-file", "blob", f"{commit_id}:{path}")
        if (
            _git_blob_sha1(raw) != blob
            or _sha256(raw) != digest
            or (count is not None and len(raw) != count)
        ):
            _fail(f"{name} document byte identity is invalid")
    o8v1_ref = f"refs/tags/{_O8V1_TAG}"
    if (
        _git(root, "cat-file", "-t", o8v1_ref) != b"commit\n"
        or _git(root, "rev-parse", o8v1_ref)
        != f"{_O8V1_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _O8V1_COMMIT, _P8V4_COMMIT)
        or _git(root, "rev-parse", f"{_O8V1_COMMIT}^{{tree}}")
        != f"{_O8V1_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V4_COMMIT,
            _O8V1_COMMIT,
        )
        != _expected_name_status(tuple(_O8_ADDITIONS))
    ):
        _fail("P8v4/O8v1 historical freeze identity is invalid")
    p8v5_ref = f"refs/tags/{_P8V5_TAG}"
    if (
        _git(root, "cat-file", "-t", p8v5_ref) != b"commit\n"
        or _git(root, "rev-parse", p8v5_ref)
        != f"{_P8V5_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _P8V5_COMMIT, _O8V1_COMMIT)
        or _git(root, "rev-parse", f"{_P8V5_COMMIT}^{{tree}}")
        != f"{_P8V5_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _O8V1_COMMIT,
            _P8V5_COMMIT,
        )
        != _expected_forward_reset_name_status(
            tuple(_O8_ADDITIONS), _P8V5_DOCUMENT
        )
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V4_COMMIT,
            _P8V5_COMMIT,
        )
        != _expected_name_status((_P8V5_DOCUMENT,))
    ):
        _fail("O8v1/P8v5 forward-reset identity is invalid")
    p8v5_document_raw = _git(
        root, "cat-file", "blob", f"{_P8V5_COMMIT}:{_P8V5_DOCUMENT}"
    )
    if (
        _git_blob_sha1(p8v5_document_raw) != _P8V5_DOCUMENT_BLOB
        or _sha256(p8v5_document_raw) != _P8V5_DOCUMENT_SHA256
        or len(p8v5_document_raw) != _P8V5_DOCUMENT_BYTE_COUNT
    ):
        _fail("P8v5 recovery document byte identity is invalid")
    o8v2_ref = f"refs/tags/{_O8V2_TAG}"
    if (
        _git(root, "cat-file", "-t", o8v2_ref) != b"commit\n"
        or _git(root, "rev-parse", o8v2_ref)
        != f"{_O8V2_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _O8V2_COMMIT, _P8V5_COMMIT)
        or _git(root, "rev-parse", f"{_O8V2_COMMIT}^{{tree}}")
        != f"{_O8V2_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V5_COMMIT,
            _O8V2_COMMIT,
        )
        != _expected_name_status(tuple(_O8_ADDITIONS))
    ):
        _fail("P8v5/O8v2 historical freeze identity is invalid")
    p8v6_ref = f"refs/tags/{_P8V6_TAG}"
    if (
        _git(root, "cat-file", "-t", p8v6_ref) != b"commit\n"
        or _git(root, "rev-parse", p8v6_ref)
        != f"{_P8V6_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _P8V6_COMMIT, _O8V2_COMMIT)
        or _git(root, "rev-parse", f"{_P8V6_COMMIT}^{{tree}}")
        != f"{_P8V6_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _O8V2_COMMIT,
            _P8V6_COMMIT,
        )
        != _expected_forward_reset_name_status(
            tuple(_O8_ADDITIONS), _P8V6_DOCUMENT
        )
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V5_COMMIT,
            _P8V6_COMMIT,
        )
        != _expected_name_status((_P8V6_DOCUMENT,))
    ):
        _fail("O8v2/P8v6 forward-reset identity is invalid")
    p8v6_document_raw = _git(root, "cat-file", "blob", f"{_P8V6_COMMIT}:{_P8V6_DOCUMENT}")
    if (
        _git_blob_sha1(p8v6_document_raw) != _P8V6_DOCUMENT_BLOB
        or _sha256(p8v6_document_raw) != _P8V6_DOCUMENT_SHA256
        or len(p8v6_document_raw) != _P8V6_DOCUMENT_BYTE_COUNT
    ):
        _fail("P8v6 recovery document byte identity is invalid")

    o8v3_ref = f"refs/tags/{_O8V3_TAG}"
    if (
        _git(root, "cat-file", "-t", o8v3_ref) != b"commit\n"
        or _git(root, "rev-parse", o8v3_ref)
        != f"{_O8V3_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _O8V3_COMMIT, _P8V6_COMMIT)
        or _git(root, "rev-parse", f"{_O8V3_COMMIT}^{{tree}}")
        != f"{_O8V3_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V6_COMMIT,
            _O8V3_COMMIT,
        )
        != _expected_name_status(tuple(_O8_ADDITIONS))
    ):
        _fail("P8v6/O8v3 historical freeze identity is invalid")

    preregistration_ref = f"refs/tags/{_PREREGISTRATION_TAG}"
    if (
        _git(root, "cat-file", "-t", preregistration_ref) != b"commit\n"
        or _git(root, "rev-parse", preregistration_ref)
        != f"{_PREREGISTRATION_COMMIT}\n".encode("ascii")
        or not _has_exact_parent(root, _PREREGISTRATION_COMMIT, _O8V3_COMMIT)
        or _git(root, "rev-parse", f"{_PREREGISTRATION_COMMIT}^{{tree}}")
        != f"{_PREREGISTRATION_TREE}\n".encode("ascii")
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _O8V3_COMMIT,
            _PREREGISTRATION_COMMIT,
        )
        != _expected_forward_reset_name_status(
            tuple(_O8_ADDITIONS), _PREREGISTRATION_DOCUMENT
        )
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            _P8V6_COMMIT,
            _PREREGISTRATION_COMMIT,
        )
        != _expected_name_status((_PREREGISTRATION_DOCUMENT,))
    ):
        _fail("O8v3/P8v7 consumed-lifecycle recovery identity is invalid")
    preregistration_document_raw = _git(
        root,
        "cat-file",
        "blob",
        f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}",
    )
    if (
        _git_blob_sha1(preregistration_document_raw) != _PREREGISTRATION_DOCUMENT_BLOB
        or _sha256(preregistration_document_raw) != _PREREGISTRATION_DOCUMENT_SHA256
        or len(preregistration_document_raw) != _PREREGISTRATION_DOCUMENT_BYTE_COUNT
    ):
        _fail("P8v7 recovery document byte identity is invalid")
    tag_ref = f"refs/tags/{_OPEN_FREEZE_TAG}"
    commit = _commit_line(_git(root, "rev-parse", tag_ref), "O8 commit")
    if _git(root, "cat-file", "-t", tag_ref) != b"commit\n":
        _fail("O8 tag is not one lightweight commit ref")
    registration_raw = _git(root, "cat-file", "blob", f"{commit}:{_REGISTRATION}")
    registration = _parse(registration_raw, "O8 registration blob")
    if set(registration) != _REGISTRATION_KEYS:
        _fail("registration top-level key set is invalid")
    unsigned = dict(registration)
    claimed = unsigned.pop("content_sha256", None)
    if (
        registration.get("schema_version") != _REGISTRATION_SCHEMA
        or registration.get("status") != "registered_zero_result"
        or registration.get("treatment_id") != _TREATMENT_ID
        or registration.get("diagnostic_system_id") != _DIAGNOSTIC_ID
        or registration.get("comparison_semantics_id") != _COMPARISON_ID
        or registration.get("runtime_id") is not None
        or registration.get("authorization") != _AUTHORIZATION
        or claimed != _sha256(_canonical(unsigned))
    ):
        _fail("registration fixed identity or content hash is invalid")
    _validate_source_manifest(registration)
    execution = _validate_execution_contract(registration)
    preregistration = registration.get("preregistration")
    if not isinstance(preregistration, Mapping) or set(preregistration) != {
        "commit_sha",
        "tag",
        "document_path",
        "document_git_blob_sha1",
        "document_sha256",
    }:
        _fail("registration preregistration identity is invalid")
    parent = _lower_hex(preregistration["commit_sha"], 40, "P8 commit")
    parent_tag = preregistration["tag"]
    if (
        parent != _PREREGISTRATION_COMMIT
        or parent_tag != _PREREGISTRATION_TAG
        or preregistration.get("document_path") != _PREREGISTRATION_DOCUMENT
        or preregistration.get("document_git_blob_sha1")
        != _PREREGISTRATION_DOCUMENT_BLOB
        or preregistration.get("document_sha256") != _PREREGISTRATION_DOCUMENT_SHA256
        or _git(root, "cat-file", "-t", f"refs/tags/{parent_tag}") != b"commit\n"
        or _git(root, "rev-parse", f"refs/tags/{parent_tag}")
        != f"{parent}\n".encode("ascii")
        or not _has_exact_parent(root, commit, parent)
        or _git(
            root,
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            parent,
            commit,
        )
        != _expected_name_status(tuple(_O8_ADDITIONS))
    ):
        _fail("P8/O8 ancestry, tag, or addition allowlist is invalid")
    source = registration["source_manifest"]
    _validate_manifest_against_tree(
        root,
        parent,
        source["preregistration_tree"],
        exact_tree=True,
    )
    _validate_manifest_against_tree(
        root,
        commit,
        source["open_freeze_added_files"],
        exact_tree=False,
    )
    document_path = preregistration.get("document_path")
    if not isinstance(document_path, str) or not document_path:
        _fail("P8 document path is invalid")
    document_raw = _git(root, "cat-file", "blob", f"{parent}:{document_path}")
    if (
        preregistration.get("document_git_blob_sha1") != _git_blob_sha1(document_raw)
        or preregistration.get("document_sha256") != _sha256(document_raw)
        or len(document_raw) != _PREREGISTRATION_DOCUMENT_BYTE_COUNT
    ):
        _fail("P8 document byte identity is invalid")
    document_contract = (
        execution.get("result_document_contract") if isinstance(execution, Mapping) else None
    )
    renderer = (
        document_contract.get("renderer_source")
        if isinstance(document_contract, Mapping)
        else None
    )
    renderer_path = "scripts/finalize_action_qbc_v8_open_diagnostic.py"
    renderer_raw = _git(root, "cat-file", "blob", f"{commit}:{renderer_path}")
    renderer_tree = _git(root, "ls-tree", commit, "--", renderer_path)
    if not isinstance(renderer, Mapping) or renderer != {
        "path": renderer_path,
        "mode": "100644",
        "git_blob_sha1": _git_blob_sha1(renderer_raw),
        "sha256": _sha256(renderer_raw),
        "size_bytes": len(renderer_raw),
    }:
        _fail("registered result renderer identity is invalid")
    if renderer_tree != (
        f"100644 blob {_git_blob_sha1(renderer_raw)}\t{renderer_path}\n".encode("ascii")
    ):
        _fail("O8 result renderer tree identity is invalid")
    return commit, registration, registration_raw


def _authority_raw_audit(root: Path, commit: str, registration_raw: bytes) -> bool:
    try:
        _validate_object_pack_sources(root)
        root_meta = root.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(root_meta.st_mode)
            or stat.S_ISLNK(root_meta.st_mode)
            or stat.S_IMODE(root_meta.st_mode) != 0o700
            or (hasattr(os, "getuid") and root_meta.st_uid != os.getuid())
            or _git(root, "rev-parse", "HEAD") != f"{commit}\n".encode("ascii")
        ):
            return False
        listing = _git(root, "ls-tree", "-rz", "--full-tree", commit)
        tracked: set[str] = set()
        tracked_directories: set[str] = set()
        for record in listing.split(b"\0"):
            if not record:
                continue
            identity, raw_path = record.split(b"\t", 1)
            mode, kind, blob = identity.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            if kind != "blob" or mode not in {"100644", "100755"}:
                return False
            path = root / relative
            raw = _plain(path, f"authority tracked file {relative}")
            if raw != _git(root, "cat-file", "blob", blob):
                return False
            expected_mode = 0o755 if mode == "100755" else 0o644
            if stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) != expected_mode:
                return False
            tracked.add(relative)
            parent = Path(relative).parent
            while str(parent) != ".":
                tracked_directories.add(parent.as_posix())
                parent = parent.parent
        if _plain(root / _REGISTRATION, "authority registration") != registration_raw:
            return False
        for directory, names, files in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            for name in list(names):
                candidate = current / name
                metadata = candidate.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    return False
                if current == root and name == ".git":
                    names.remove(name)
                    continue
                if candidate.relative_to(root).as_posix() not in tracked_directories:
                    return False
            for name in files:
                if (current / name).relative_to(root).as_posix() not in tracked:
                    return False
        return _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") == b""
    except (OSError, ValueError, UnicodeError, _FinalizationError):
        return False


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize the action-QBC v8 evidence bundle.")
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--preparation-receipt", required=True)
    parser.add_argument("--preparation-verification-receipt", required=True)
    parser.add_argument("--remote-claim", required=True)
    parser.add_argument("--remote-verifier-claim", required=True)
    parser.add_argument("--remote-receipt", required=True)
    parser.add_argument("--remote-supervisor-receipt", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--driver-claim", required=True)
    parser.add_argument("--lifecycle-ledger", required=True)
    parser.add_argument("--process-a-start-claim", required=True)
    parser.add_argument("--process-a-validator-claim", required=True)
    parser.add_argument("--process-a-validation-receipt", required=True)
    parser.add_argument("--process-a", required=True)
    parser.add_argument("--process-b-start-claim", required=True)
    parser.add_argument("--process-b-validator-claim", required=True)
    parser.add_argument("--process-b-validation-receipt", required=True)
    parser.add_argument("--process-b", required=True)
    parser.add_argument("--bundle", required=True)
    return parser.parse_args(argv)


def _require_argv(args: argparse.Namespace, registration: Mapping[str, Any]) -> None:
    expected = {
        "repository_root": ".",
        "registration": _REGISTRATION,
        "preparation_receipt": _PREPARATION,
        "preparation_verification_receipt": _PREPARATION_VERIFICATION,
        "remote_claim": _REMOTE_CLAIM,
        "remote_verifier_claim": _REMOTE_VERIFIER_CLAIM,
        "remote_receipt": _REMOTE_RECEIPT,
        "remote_supervisor_receipt": _REMOTE_SUPERVISOR,
        "arm_receipt": _ARM,
        "driver_claim": _DRIVER,
        "lifecycle_ledger": _LEDGER,
        "process_a_start_claim": _PROCESS_A_START,
        "process_a_validator_claim": _PROCESS_A_VALIDATOR,
        "process_a_validation_receipt": _PROCESS_A_VALIDATION,
        "process_a": _PROCESS_A,
        "process_b_start_claim": _PROCESS_B_START,
        "process_b_validator_claim": _PROCESS_B_VALIDATOR,
        "process_b_validation_receipt": _PROCESS_B_VALIDATION,
        "process_b": _PROCESS_B,
        "bundle": _BUNDLE,
    }
    if any(getattr(args, key) != value for key, value in expected.items()):
        _fail("finalizer arguments differ from the registered fixed paths")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("finalizer requires Python -I -B")
    if platform.python_implementation() != "CPython" or sys.version_info[:3] != (3, 12, 3):
        _fail("finalizer requires CPython 3.12.3")
    if Path(sys.executable).absolute() != Path("/usr/bin/python3"):
        _fail("finalizer interpreter path differs from registration")
    if Path.cwd().resolve(strict=True) != _AUTHORITY_ROOT:
        _fail("finalizer cwd differs from the authority clone")
    execution = registration.get("execution_contract")
    template = execution.get("finalizer_argv_template") if isinstance(execution, Mapping) else None
    if template != _expected_finalizer_argv():
        _fail("registered finalizer argv is invalid")
    try:
        script_index = template.index("scripts/finalize_action_qbc_v8_open_diagnostic.py")
    except ValueError as exc:
        raise _FinalizationError("registered finalizer argv lacks its script") from exc
    if list(sys.argv) != template[script_index:]:
        _fail("observed finalizer argv differs from registration")
    hashes = execution.get("argv_hashes") if isinstance(execution, Mapping) else None
    if not isinstance(hashes, Mapping) or hashes.get("finalizer") != _sha256(_canonical(template)):
        _fail("registered finalizer argv digest is invalid")


def _matching(
    artifact: _Artifact,
    *,
    commit: str,
    registration_sha: str,
) -> bool:
    return bool(
        artifact.value is not None
        and artifact.value.get("open_freeze_commit_sha") == commit
        and artifact.value.get("registration_content_sha256") == registration_sha
    )


def _preparation_attempt_plan() -> tuple[tuple[str, str, str | None, bool], ...]:
    clone = (
        ("clone", "clone", True),
        ("git_config", "config", True),
        ("git_config", "config", True),
        ("git_config", "config", True),
        ("checkout", "checkout", True),
        ("git_config", "remote", True),
        ("git_config", "config", False),
        ("raw_audit", "cat-file", False),
        ("raw_audit", "rev-parse", False),
    )
    raw_audit = (
        ("git_config", "config", False),
        ("raw_audit", "rev-parse", False),
        ("raw_audit", "ls-tree", False),
        ("raw_audit", "cat-file", False),
        ("raw_audit", "ls-files", False),
        ("raw_audit", "status", False),
    )
    result: list[tuple[str, str, str | None, bool]] = []
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in clone)
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in raw_audit)
    for label in ("A", "B"):
        result.append((label, "environment_build", None, False))
    for label in ("A", "B"):
        result.extend((label, phase, command, staging) for phase, command, staging in raw_audit)
    for label in ("A", "B"):
        result.extend((label, "preflight", None, False) for _ in range(5))
    if len(result) != 54:
        _fail("internal preparation command plan is not exactly 54 rows")
    return tuple(result)


def _preparation_git_subcommand(argv: Sequence[str]) -> str | None:
    if len(argv) < 3 or list(argv[:2]) != ["/usr/bin/git", "--no-replace-objects"]:
        return None
    if argv[2] == "-C":
        return argv[4] if len(argv) >= 5 else None
    return argv[2]


def _preparation_manifest_request(registration: Mapping[str, Any]) -> bytes:
    manifest = registration.get("source_manifest")
    if not isinstance(manifest, Mapping):
        _fail("registered preparation source manifest is invalid")
    rows: list[tuple[str, str]] = []
    for member in ("preregistration_tree", "open_freeze_added_files"):
        values = manifest.get(member)
        if not isinstance(values, list):
            _fail("registered preparation source-manifest rows are invalid")
        for value in values:
            if not isinstance(value, Mapping):
                _fail("registered preparation source-manifest row is invalid")
            path = value.get("path")
            oid = value.get("git_blob_sha1")
            if not isinstance(path, str) or not path or "\x00" in path:
                _fail("registered preparation source-manifest path is invalid")
            rows.append((path, _lower_hex(oid, 40, "registered source blob SHA-1")))
    registration_raw = _canonical(registration)
    registration_oid = hashlib.sha1(
        b"blob "
        + str(len(registration_raw)).encode("ascii")
        + b"\0"
        + registration_raw,
        usedforsecurity=False,
    ).hexdigest()
    rows.append((_REGISTRATION, registration_oid))
    rows.sort(key=lambda item: item[0].encode("utf-8"))
    if len(rows) != len({path for path, _oid in rows}):
        _fail("registered preparation source-manifest paths are duplicated")
    return b"".join(oid.encode("ascii") + b"\n" for _path, oid in rows)


def _preparation_command_identity(
    *,
    attempt_index: int | None,
    label: str,
    phase: str,
    cwd: str,
    argv: Sequence[str],
    stdin_bytes: bytes = b"",
) -> dict[str, Any]:
    arguments = list(argv)
    return {
        "attempt_index": attempt_index,
        "label": label,
        "phase": phase,
        "cwd": cwd,
        "argv": arguments,
        "argv_sha256": _sha256(_canonical(arguments)),
        "stdin_size_bytes": len(stdin_bytes),
        "stdin_sha256": _sha256(stdin_bytes),
    }


def _preparation_expected_raw_audit_identities(
    *,
    attempt_index: int,
    label: str,
    root: str,
    commit: str,
    request: bytes,
) -> list[dict[str, Any]]:
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", root]
    commands: tuple[tuple[str, list[str], bytes], ...] = (
        ("git_config", [*prefix, "config", "--local", "--null", "--list"], b""),
        ("raw_audit", [*prefix, "rev-parse", "HEAD"], b""),
        (
            "raw_audit",
            [*prefix, "ls-tree", "-r", "-l", "-z", "--full-tree", commit],
            b"",
        ),
        ("raw_audit", [*prefix, "cat-file", "--batch"], request),
        ("raw_audit", [*prefix, "ls-files", "--stage", "-z"], b""),
        (
            "raw_audit",
            [*prefix, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            b"",
        ),
    )
    return [
        _preparation_command_identity(
            attempt_index=attempt_index,
            label=label,
            phase=phase,
            cwd=root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _preparation_expected_attempt_identities(
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    attempt_index: int,
    commit: str,
) -> list[dict[str, Any]]:
    execution_root_value = execution.get("execution_root")
    environment_argv = execution.get("environment_build_argv")
    preflight_argvs = execution.get("preflight_argvs")
    if (
        not isinstance(execution_root_value, str)
        or not execution_root_value.startswith("/")
        or not isinstance(environment_argv, list)
        or not environment_argv
        or not all(isinstance(item, str) and item for item in environment_argv)
        or not isinstance(preflight_argvs, list)
        or len(preflight_argvs) != 5
        or not all(
            isinstance(argv, list)
            and argv
            and all(isinstance(item, str) and item for item in argv)
            for argv in preflight_argvs
        )
    ):
        _fail("registered preparation command arrays are invalid")
    source = f"{execution_root_value.rstrip('/')}/.prepare-attempt-{attempt_index}"
    roots = {"A": f"{source}/process-a", "B": f"{source}/process-b"}
    request = _preparation_manifest_request(registration)
    result: list[dict[str, Any]] = []

    def append(
        label: str,
        phase: str,
        cwd: str,
        argv: Sequence[str],
        stdin_bytes: bytes = b"",
    ) -> None:
        result.append(
            _preparation_command_identity(
                attempt_index=attempt_index,
                label=label,
                phase=phase,
                cwd=cwd,
                argv=argv,
                stdin_bytes=stdin_bytes,
            )
        )

    for label, root in roots.items():
        clone_commands: tuple[tuple[str, list[str]], ...] = (
            (
                "clone",
                [
                    "/usr/bin/git", "--no-replace-objects", "clone", "--no-local",
                    "--no-checkout", "--branch", _OPEN_FREEZE_TAG, "--single-branch",
                    _PREPARATION_SOURCE_URL, root,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.autocrlf", "false",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.eol", "lf",
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "config",
                    "--local", "core.safecrlf", "true",
                ],
            ),
            (
                "checkout",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "checkout",
                    "--detach", commit,
                ],
            ),
            (
                "git_config",
                [
                    "/usr/bin/git", "--no-replace-objects", "-C", root, "remote",
                    "remove", "origin",
                ],
            ),
        )
        for phase, argv in clone_commands:
            append(label, phase, source, argv)
        prefix = ["/usr/bin/git", "--no-replace-objects", "-C", root]
        append(
            label,
            "git_config",
            root,
            [*prefix, "config", "--local", "--null", "--list"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*prefix, "cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
        append(
            label,
            "raw_audit",
            root,
            [*prefix, "rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"],
        )
    for label, root in roots.items():
        result.extend(
            _preparation_expected_raw_audit_identities(
                attempt_index=attempt_index,
                label=label,
                root=root,
                commit=commit,
                request=request,
            )
        )
    for label, root in roots.items():
        append(label, "environment_build", root, environment_argv)
    for label, root in roots.items():
        result.extend(
            _preparation_expected_raw_audit_identities(
                attempt_index=attempt_index,
                label=label,
                root=root,
                commit=commit,
                request=request,
            )
        )
    for label, root in roots.items():
        for argv in preflight_argvs:
            append(label, "preflight", root, argv)
    if len(result) != 54:
        _fail("internal preparation command identity plan is not exactly 54 rows")
    return result


def _preparation_expected_authority_identities(
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    commit: str,
) -> list[dict[str, Any]]:
    authority_root = execution.get("authority_root")
    if not isinstance(authority_root, str) or not authority_root.startswith("/"):
        _fail("registered authority root is invalid")
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", authority_root]
    commands: list[tuple[str, list[str], bytes]] = []

    def append(phase: str, arguments: Sequence[str], stdin_bytes: bytes = b"") -> None:
        commands.append((phase, [*prefix, *arguments], stdin_bytes))

    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["cat-file", "-t", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", f"refs/tags/{_OPEN_FREEZE_TAG}"])
    append("raw_audit", ["rev-parse", "HEAD"])
    for prior_tag, prior_commit, parent_commit in (
        (_P8V1_TAG, _P8V1_COMMIT, _R7_COMMIT),
        (_P8V2_TAG, _P8V2_COMMIT, _P8V1_COMMIT),
        (_P8V3_TAG, _P8V3_COMMIT, _P8V2_COMMIT),
        (_P8V4_TAG, _P8V4_COMMIT, _P8V3_COMMIT),
        (_O8V1_TAG, _O8V1_COMMIT, _P8V4_COMMIT),
        (_P8V5_TAG, _P8V5_COMMIT, _O8V1_COMMIT),
        (_O8V2_TAG, _O8V2_COMMIT, _P8V5_COMMIT),
        (_P8V6_TAG, _P8V6_COMMIT, _O8V2_COMMIT),
        (_O8V3_TAG, _O8V3_COMMIT, _P8V6_COMMIT),
        (_PREREGISTRATION_TAG, _PREREGISTRATION_COMMIT, _O8V3_COMMIT),
    ):
        append("raw_audit", ["cat-file", "-t", f"refs/tags/{prior_tag}"])
        append("raw_audit", ["rev-parse", f"refs/tags/{prior_tag}"])
        append("raw_audit", ["rev-list", "--parents", "-n", "1", prior_commit])
        append(
            "raw_audit",
            [
                "diff", "--name-status", "--no-renames", "-z", parent_commit,
                prior_commit,
            ],
        )
    append(
        "raw_audit",
        ["ls-tree", "-z", _PREREGISTRATION_COMMIT, "--", _PREREGISTRATION_DOCUMENT],
    )
    append(
        "raw_audit",
        [
            "cat-file", "blob",
            f"{_PREREGISTRATION_COMMIT}:{_PREREGISTRATION_DOCUMENT}",
        ],
    )
    append("raw_audit", ["rev-list", "--parents", "-n", "1", commit])
    append(
        "raw_audit",
        [
            "diff", "--name-status", "--no-renames", "-z",
            _PREREGISTRATION_COMMIT, commit,
        ],
    )
    append("git_config", ["config", "--local", "--null", "--list"])
    append("raw_audit", ["rev-parse", "HEAD"])
    append("raw_audit", ["ls-tree", "-r", "-l", "-z", "--full-tree", commit])
    append(
        "raw_audit",
        ["cat-file", "--batch"],
        _preparation_manifest_request(registration),
    )
    append("raw_audit", ["ls-files", "--stage", "-z"])
    append(
        "raw_audit",
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )
    if len(commands) != 54:
        _fail("internal preparation authority command plan is not exactly 54 rows")
    return [
        _preparation_command_identity(
            attempt_index=None,
            label="authority",
            phase=phase,
            cwd=authority_root,
            argv=argv,
            stdin_bytes=stdin_bytes,
        )
        for phase, argv, stdin_bytes in commands
    ]


def _preparation_semantically_valid(
    artifact: _Artifact,
    *,
    commit: str,
    registration_sha: str,
    verify_filesystem: bool = True,
    execution: Mapping[str, Any] | None = None,
    registration: Mapping[str, Any] | None = None,
) -> bool:
    if not _matching(artifact, commit=commit, registration_sha=registration_sha):
        return False
    value = artifact.value
    status = value.get("status") if value is not None else None
    if (
        value is None
        or status not in {"prepared", "failed"}
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
    ):
        return False
    all_expected_roots = (
        {
            "authority": execution.get("authority_root"),
            "process_a": execution.get("process_a_root"),
            "process_b": execution.get("process_b_root"),
        }
        if execution is not None
        else {
            "authority": str(_AUTHORITY_ROOT),
            "process_a": str(_EXECUTION_ROOT / "processes/process-a"),
            "process_b": str(_EXECUTION_ROOT / "processes/process-b"),
        }
    )
    expected_roots = (
        all_expected_roots
        if status == "prepared"
        else {"authority": all_expected_roots["authority"]}
    )
    for key, root in expected_roots.items():
        clone = value.get(key)
        if not isinstance(clone, Mapping) or set(clone) != _CLONE_KEYS:
            return False
        if (
            clone.get("root") != root
            or clone.get("head_sha") != commit
            or clone.get("passes") is not True
        ):
            return False
        for identity_key in ("root_device", "root_inode", "root_owner_uid", "root_mode"):
            identity_value = clone.get(identity_key)
            if (
                not isinstance(identity_value, int)
                or isinstance(identity_value, bool)
                or identity_value < 0
            ):
                return False
        if verify_filesystem:
            try:
                root_descriptor = _open_directory_nofollow(Path(str(root)), f"{key} clone root")
                root_metadata = os.fstat(root_descriptor)
                os.close(root_descriptor)
            except (OSError, _FinalizationError):
                return False
            if (
                root_metadata.st_dev != clone.get("root_device")
                or root_metadata.st_ino != clone.get("root_inode")
                or root_metadata.st_uid != clone.get("root_owner_uid")
                or stat.S_IMODE(root_metadata.st_mode) != clone.get("root_mode")
            ):
                return False
        for digest_key in (
            "tree_sha256",
            "raw_materialization_sha256",
            "git_status_sha256",
        ):
            try:
                _lower_hex(clone.get(digest_key), 64, f"{key}.{digest_key}")
            except _FinalizationError:
                return False
        if key == "authority":
            if any(
                clone.get(field) is not None
                for field in (
                    "python_version", "uv_version", "environment_inventory",
                    "environment_inventory_sha256", "venv_materialization_sha256",
                    "venv_python_sha256",
                )
            ):
                return False
        elif (
            clone.get("python_version") != "3.12.13"
            or clone.get("uv_version") != "0.11.28"
        ):
            return False
        if key != "authority":
            inventory = clone.get("environment_inventory")
            if not isinstance(inventory, list):
                return False
            names: list[str] = []
            for distribution in inventory:
                if not isinstance(distribution, Mapping) or set(distribution) != _DISTRIBUTION_KEYS:
                    return False
                name = distribution.get("normalized_name")
                version = distribution.get("version")
                count = distribution.get("file_count")
                if (
                    not isinstance(name, str) or not name or not name.isascii()
                    or name != name.lower()
                    or name.startswith("-") or name.endswith("-") or "--" in name
                    or any(
                        character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                        for character in name
                    )
                    or not isinstance(version, str) or not version or not version.isascii()
                    or not isinstance(count, int) or isinstance(count, bool) or count < 0
                ):
                    return False
                names.append(name)
                try:
                    _lower_hex(distribution.get("files_sha256"), 64, "distribution files SHA-256")
                except _FinalizationError:
                    return False
            if names != sorted(names, key=lambda item: item.encode("utf-8")) or len(
                names
            ) != len(set(names)):
                return False
            try:
                _lower_hex(
                    clone.get("environment_inventory_sha256"),
                    64,
                    f"{key}.environment_inventory_sha256",
                )
                _lower_hex(
                    clone.get("venv_materialization_sha256"), 64,
                    f"{key}.venv_materialization_sha256",
                )
                _lower_hex(clone.get("venv_python_sha256"), 64, f"{key}.venv_python_sha256")
            except _FinalizationError:
                return False
            if clone.get("environment_inventory_sha256") != _sha256(_canonical(inventory)):
                return False
    authority_clone = value.get("authority")
    if not isinstance(authority_clone, Mapping):
        return False
    clean_status_sha = _sha256(b"")
    for key in expected_roots:
        clone = value.get(key)
        if (
            not isinstance(clone, Mapping)
            or clone.get("tree_sha256") != authority_clone.get("tree_sha256")
            or clone.get("raw_materialization_sha256")
            != authority_clone.get("raw_materialization_sha256")
            or clone.get("git_status_sha256") != clean_status_sha
        ):
            return False
    process_a_clone = value.get("process_a")
    process_b_clone = value.get("process_b")
    if status == "prepared":
        if (
            not isinstance(process_a_clone, Mapping)
            or not isinstance(process_b_clone, Mapping)
            or process_a_clone.get("venv_python_sha256")
            != process_b_clone.get("venv_python_sha256")
        ):
            return False
    elif process_a_clone is not None or process_b_clone is not None:
        return False
    attempts = value.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        return False
    try:
        _lower_hex(value.get("commands_sha256"), 64, "preparation commands SHA-256")
        _lower_hex(
            value.get("command_environment_sha256"), 64,
            "preparation command environment SHA-256",
        )
    except _FinalizationError:
        return False
    command_ledger = value.get("command_ledger")
    if (
        not isinstance(command_ledger, list)
        or not command_ledger
        or value.get("commands_sha256") != _sha256(_canonical(command_ledger))
        or (
            execution is not None
            and value.get("command_environment_sha256")
            != _sha256(_canonical(execution.get("preparation_command_environment")))
        )
    ):
        return False
    if registration is None:
        return False
    policy = execution.get("preparation_command_policy") if execution is not None else None
    if not isinstance(policy, Mapping):
        return False
    try:
        stdin_cap = _nonnegative_int(policy.get("stdin_cap_bytes"), "preparation stdin cap")
        stdout_cap = _nonnegative_int(policy.get("stdout_cap_bytes"), "preparation stdout cap")
        stderr_cap = _nonnegative_int(policy.get("stderr_cap_bytes"), "preparation stderr cap")
        default_timeout = _nonnegative_int(
            policy.get("default_timeout_seconds"), "preparation default timeout"
        )
        environment_timeout = _nonnegative_int(
            policy.get("environment_timeout_seconds"),
            "preparation environment timeout",
        )
    except _FinalizationError:
        return False
    execution_root_value = execution.get("execution_root") if execution is not None else None
    if not isinstance(execution_root_value, str) or not execution_root_value.startswith("/"):
        return False
    execution_root = execution_root_value.rstrip("/")
    plan = _preparation_attempt_plan()
    attempt_rows: dict[int, list[Mapping[str, Any]]] = {
        index: [] for index in range(1, len(attempts) + 1)
    }
    terminal_attempts: set[int] = set()
    authority_rows: list[Mapping[str, Any]] = []
    seen_attempt = False
    last_attempt = 0
    preflight_offsets = {index: {"A": 0, "B": 0} for index in attempt_rows}
    empty_sha = _sha256(b"")
    for sequence_index, command in enumerate(command_ledger):
        if not isinstance(command, Mapping) or set(command) != _PREPARATION_COMMAND_KEYS:
            return False
        argv = command.get("argv")
        attempt_index = command.get("attempt_index")
        label = command.get("label")
        phase = command.get("phase")
        cwd = command.get("cwd")
        outcome = command.get("outcome")
        if (
            command.get("sequence_index") != sequence_index
            or not isinstance(cwd, str)
            or not cwd.startswith("/")
            or "\x00" in cwd
            or not isinstance(argv, list)
            or not argv
            or not all(
                isinstance(argument, str) and argument and "\x00" not in argument
                for argument in argv
            )
            or command.get("argv_sha256") != _sha256(_canonical(argv))
            or phase not in _PREPARATION_PHASES
            or outcome not in _PREPARATION_OUTCOMES
        ):
            return False
        if attempt_index is None:
            if (
                seen_attempt
                or label != "authority"
                or cwd != execution.get("authority_root")
                or _preparation_git_subcommand(argv)
                not in {
                    "cat-file",
                    "config",
                    "diff",
                    "for-each-ref",
                    "ls-files",
                    "ls-tree",
                    "rev-list",
                    "rev-parse",
                    "status",
                }
            ):
                return False
            authority_rows.append(command)
        else:
            seen_attempt = True
            if (
                not isinstance(attempt_index, int)
                or isinstance(attempt_index, bool)
                or attempt_index < 1
                or attempt_index > len(attempts)
                or attempt_index < last_attempt
                or attempt_index in terminal_attempts
            ):
                return False
            last_attempt = attempt_index
            rows = attempt_rows[attempt_index]
            if len(rows) >= len(plan):
                return False
            expected_label, expected_phase, expected_subcommand, staging_cwd = plan[
                len(rows)
            ]
            source = f"{execution_root}/.prepare-attempt-{attempt_index}"
            process_root = f"{source}/process-{expected_label.lower()}"
            expected_cwd = source if staging_cwd else process_root
            if label != expected_label or phase != expected_phase or cwd != expected_cwd:
                return False
            if (
                expected_subcommand is not None
                and _preparation_git_subcommand(argv) != expected_subcommand
            ):
                return False
            if expected_subcommand == "clone" and argv[-1] != process_root:
                return False
            if len(argv) >= 4 and argv[2] == "-C" and argv[3] != process_root:
                return False
            if phase == "environment_build" and argv != execution.get(
                "environment_build_argv"
            ):
                return False
            if phase == "preflight":
                preflights = execution.get("preflight_argvs")
                offset = preflight_offsets[attempt_index][expected_label]
                if (
                    not isinstance(preflights, list)
                    or offset >= len(preflights)
                    or argv != preflights[offset]
                ):
                    return False
                preflight_offsets[attempt_index][expected_label] += 1
            rows.append(command)
        try:
            stdin_size = _nonnegative_int(command.get("stdin_size_bytes"), "command stdin size")
            stdout_size = _nonnegative_int(command.get("stdout_size_bytes"), "command stdout size")
            stderr_size = _nonnegative_int(command.get("stderr_size_bytes"), "command stderr size")
            duration = _nonnegative_int(
                command.get("duration_milliseconds"), "command duration"
            )
            for digest_key in ("stdin_sha256", "stdout_sha256", "stderr_sha256"):
                _lower_hex(command.get(digest_key), 64, f"command {digest_key}")
        except _FinalizationError:
            return False
        started = command.get("started")
        exit_code = command.get("exit_code")
        cleanup = command.get("child_cleanup_passes")
        timed_out = command.get("timed_out")
        if not isinstance(started, bool) or not isinstance(
            timed_out, bool
        ) or cleanup not in {None, True, False}:
            return False
        if not started:
            if (
                outcome not in {"spawn_error", "stdin_limit"}
                or exit_code is not None
                or timed_out
                or cleanup is not None
                or stdout_size != 0
                or stderr_size != 0
                or command.get("stdout_sha256") != empty_sha
                or command.get("stderr_sha256") != empty_sha
                or (outcome == "stdin_limit") != (stdin_size > stdin_cap)
            ):
                return False
        else:
            if (
                stdin_size > stdin_cap
                or outcome in {"spawn_error", "stdin_limit"}
                or (
                    exit_code is not None
                    and (not isinstance(exit_code, int) or isinstance(exit_code, bool))
                )
                or (outcome == "completed" and (exit_code != 0 or timed_out))
                or (
                    outcome == "nonzero"
                    and (exit_code is None or exit_code == 0 or timed_out)
                )
                or (outcome == "timeout" and not timed_out)
                or (
                    (timed_out or outcome in {"stdout_limit", "stderr_limit"})
                    and not isinstance(cleanup, bool)
                )
            ):
                return False
        if stdout_size > stdout_cap + 1 or stderr_size > stderr_cap + 1:
            return False
        if outcome == "stdout_limit":
            if stdout_size != stdout_cap + 1:
                return False
        elif stdout_size > stdout_cap:
            return False
        if outcome == "stderr_limit":
            if stderr_size != stderr_cap + 1 or stdout_size > stdout_cap:
                return False
        elif outcome == "stdout_limit":
            if stderr_size > stderr_cap + 1:
                return False
        elif stderr_size > stderr_cap:
            return False
        if outcome == "timeout" and (
            stdout_size > stdout_cap or stderr_size > stderr_cap
        ):
            return False
        timeout_threshold = (
            environment_timeout if phase == "environment_build" else default_timeout
        )
        if timed_out and duration < timeout_threshold * 1_000:
            return False
        if attempt_index is None and (outcome != "completed" or cleanup is False):
            return False
        if attempt_index is not None and (outcome != "completed" or cleanup is False):
            terminal_attempts.add(attempt_index)
        if cleanup is False:
            return False
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, Mapping) or set(attempt) != _PREPARATION_ATTEMPT_KEYS:
            return False
        if (
            attempt.get("attempt_index") != index
            or isinstance(attempt.get("attempt_index"), bool)
            or attempt.get("process_a_stage") not in _PREPARATION_PROCESS_STAGES
            or attempt.get("process_b_stage") not in _PREPARATION_PROCESS_STAGES
        ):
            return False
        cleanup = attempt.get("cleanup")
        promotion = attempt.get("promotion")
        if (
            not isinstance(cleanup, Mapping)
            or set(cleanup) != _PREPARATION_CLEANUP_KEYS
            or not isinstance(promotion, Mapping)
            or set(promotion) != _PREPARATION_PROMOTION_KEYS
        ):
            return False
        if execution is None:
            source = str(_EXECUTION_ROOT / f".prepare-attempt-{index}")
            destination = str(_EXECUTION_ROOT / "processes")
        else:
            execution_root = execution.get("execution_root")
            if not isinstance(execution_root, str) or not execution_root:
                return False
            source = f"{execution_root.rstrip('/')}/.prepare-attempt-{index}"
            destination = f"{execution_root.rstrip('/')}/processes"
        owned = cleanup.get("owned_paths")
        removed = cleanup.get("removed")
        if (
            promotion.get("source_path") != source
            or promotion.get("destination_path") != destination
            or not isinstance(owned, list)
            or not isinstance(removed, list)
            or not all(isinstance(path, str) for path in [*owned, *removed])
            or owned != sorted(owned)
            or removed != sorted(removed)
            or not set(removed) <= set(owned)
            or owned not in ([], [source])
            or removed not in ([], [source])
        ):
            return False
        final = index == len(attempts)
        passing = status == "prepared" and final
        if passing:
            if (
                attempt.get("passes") is not True
                or attempt.get("process_a_stage") != "completed"
                or attempt.get("process_b_stage") != "completed"
                or cleanup.get("passes") is not True
                or promotion.get("passes") is not True
                or owned != [source]
                or removed != []
            ):
                return False
            try:
                device = _nonnegative_int(
                    promotion.get("source_device"),
                    "promotion source device",
                )
                inode = _nonnegative_int(
                    promotion.get("source_inode"),
                    "promotion source inode",
                )
                destination_metadata = (
                    Path(destination).stat(follow_symlinks=False)
                    if verify_filesystem
                    else None
                )
            except _FinalizationError:
                return False
            except OSError:
                return False
            if verify_filesystem and (
                Path(source).exists()
                or Path(source).is_symlink()
                or destination_metadata is None
                or not stat.S_ISDIR(destination_metadata.st_mode)
                or stat.S_ISLNK(destination_metadata.st_mode)
                or destination_metadata.st_dev != device
                or destination_metadata.st_ino != inode
            ):
                return False
        elif (
            attempt.get("passes") is not False
            or promotion.get("passes") is not False
            or cleanup.get("passes") is not True
            or removed != owned
            or (
                verify_filesystem
                and (Path(source).exists() or Path(source).is_symlink())
            )
        ):
            return False
        if not passing:
            device = promotion.get("source_device")
            inode = promotion.get("source_inode")
            if owned:
                try:
                    _nonnegative_int(device, "failed promotion source device")
                    _nonnegative_int(inode, "failed promotion source inode")
                except _FinalizationError:
                    return False
            elif device is not None or inode is not None:
                return False
    if status == "failed" and verify_filesystem:
        processes = Path(f"{execution_root.rstrip('/')}/processes")
        if processes.exists() or processes.is_symlink():
            return False
    for index, attempt in enumerate(attempts, start=1):
        rows = attempt_rows[index]
        if attempt.get("passes") is True and len(rows) != len(plan):
            return False
        if attempt.get("passes") is True and any(
            row.get("outcome") != "completed"
            or row.get("child_cleanup_passes") is False
            for row in rows
        ):
            return False
    identity_keys = (
        "attempt_index",
        "label",
        "phase",
        "cwd",
        "argv",
        "argv_sha256",
        "stdin_size_bytes",
        "stdin_sha256",
    )
    observed_authority = [
        {key: row[key] for key in identity_keys} for row in authority_rows
    ]
    try:
        expected_authority = _preparation_expected_authority_identities(
            registration,
            execution,
            commit=commit,
        )
        if observed_authority != expected_authority:
            return False
        for index in range(1, len(attempts) + 1):
            observed = [
                {key: row[key] for key in identity_keys}
                for row in attempt_rows[index]
            ]
            expected = _preparation_expected_attempt_identities(
                registration,
                execution,
                attempt_index=index,
                commit=commit,
            )
            if observed != expected[: len(observed)]:
                return False
    except _FinalizationError:
        return False
    if verify_filesystem:
        live_roots = (
            (("authority", False), ("process_a", True), ("process_b", True))
            if status == "prepared"
            else (("authority", False),)
        )
        for key, environment in live_roots:
            clone = value.get(key)
            root_text = all_expected_roots[key]
            if (
                not isinstance(clone, Mapping)
                or not isinstance(root_text, str)
                or not _live_clone_matches_receipt(
                    Path(root_text), clone, commit=commit, environment=environment
                )
            ):
                return False
    return True


def _preparation_valid(
    artifact: _Artifact,
    *,
    commit: str,
    registration_sha: str,
    verify_filesystem: bool = True,
    execution: Mapping[str, Any] | None = None,
    registration: Mapping[str, Any] | None = None,
) -> bool:
    return bool(
        artifact.value is not None
        and artifact.value.get("status") == "prepared"
        and _preparation_semantically_valid(
            artifact,
            commit=commit,
            registration_sha=registration_sha,
            verify_filesystem=verify_filesystem,
            execution=execution,
            registration=registration,
        )
    )


def _sha_or_none(artifact: _Artifact) -> str | None:
    return artifact.sha256


def _preparation_verification_valid(
    artifact: _Artifact,
    *,
    preparation: _Artifact,
    commit: str,
    registration_sha: str,
    execution: Mapping[str, Any],
) -> bool:
    if not _matching(artifact, commit=commit, registration_sha=registration_sha):
        return False
    value = artifact.value
    preparation_value = preparation.value
    if (
        value is None
        or preparation_value is None
        or artifact.raw is None
        or preparation.raw is None
        or value.get("status") != "verified"
        or preparation_value.get("status") != "prepared"
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or value.get("preparation_receipt_sha256") != preparation.sha256
        or value.get("verification_argv_sha256")
        != _sha256(_canonical(execution.get("post_preparation_validation_argv")))
    ):
        return False
    preimage = dict(value)
    content_sha = preimage.pop("content_sha256", None)
    if content_sha != _sha256(_canonical(preimage)):
        return False
    for key in ("authority", "process_a", "process_b"):
        clone = value.get(key)
        preparation_clone = preparation_value.get(key)
        if (
            not isinstance(clone, Mapping)
            or set(clone) != _PREPARATION_VERIFICATION_CLONE_KEYS
            or not isinstance(preparation_clone, Mapping)
            or clone != {
                field: field_value
                for field, field_value in preparation_clone.items()
                if field != "environment_inventory"
            }
            or clone.get("passes") is not True
        ):
            return False
    return True


def _decode_stream(value: Mapping[str, Any], prefix: str, cap: int) -> bytes:
    size = _nonnegative_int(value.get(f"{prefix}_size_bytes"), f"{prefix} size")
    if size > cap:
        _fail(f"{prefix} exceeds its registered cap")
    digest = _lower_hex(value.get(f"{prefix}_sha256"), 64, f"{prefix} SHA-256")
    encoded = value.get(f"{prefix}_base64")
    if not isinstance(encoded, str) or any(ord(character) > 127 for character in encoded):
        _fail(f"{prefix} Base64 is invalid")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (TypeError, ValueError) as exc:
        raise _FinalizationError(f"{prefix} Base64 is invalid") from exc
    if (
        base64.b64encode(raw).decode("ascii") != encoded
        or len(raw) != size
        or _sha256(raw) != digest
    ):
        _fail(f"{prefix} byte identity is invalid")
    return raw


def _manifest_entry(registration: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    source = registration.get("source_manifest")
    rows = source.get("open_freeze_added_files") if isinstance(source, Mapping) else None
    matches = (
        [row for row in rows if isinstance(row, Mapping) and row.get("path") == path]
        if isinstance(rows, list)
        else []
    )
    if len(matches) != 1:
        _fail(f"registration does not bind exactly one {path}")
    return matches[0]


def _remote_claim_valid(
    artifact: _Artifact,
    *,
    registration: Mapping[str, Any],
    execution: Mapping[str, Any],
    commit: str,
    registration_sha: str,
) -> bool:
    value = artifact.value
    if value is None:
        return False
    supervisor = _manifest_entry(
        registration,
        "scripts/supervise_action_qbc_v8_remote_tag.py",
    )
    verifier = _manifest_entry(
        registration,
        "scripts/verify_action_qbc_v8_remote_tag.py",
    )
    hashes = execution["argv_hashes"]
    return bool(
        _matching(artifact, commit=commit, registration_sha=registration_sha)
        and value.get("open_freeze_tag") == _OPEN_FREEZE_TAG
        and value.get("supervisor_argv_sha256") == hashes["remote_supervisor"]
        and value.get("supervisor_script_git_blob_sha1") == supervisor["git_blob_sha1"]
        and value.get("supervisor_script_sha256") == supervisor["sha256"]
        and value.get("verifier_script_git_blob_sha1") == verifier["git_blob_sha1"]
        and value.get("verifier_script_sha256") == verifier["sha256"]
    )


def _remote_verifier_valid(
    artifact: _Artifact,
    *,
    claim: _Artifact,
    execution: Mapping[str, Any],
    commit: str,
    registration_sha: str,
) -> bool:
    value = artifact.value
    return bool(
        value is not None
        and _matching(artifact, commit=commit, registration_sha=registration_sha)
        and value.get("claim_sha256") == _sha_or_none(claim)
        and value.get("verifier_argv_sha256")
        == execution["argv_hashes"]["remote_verifier"]
    )


def _validate_remote_attempt(
    value: Any,
    *,
    index: int,
    expected_stdout: bytes,
) -> tuple[str, int]:
    if not isinstance(value, Mapping) or set(value) != _REMOTE_ATTEMPT_KEYS:
        _fail(f"remote attempt {index} schema is invalid")
    if (
        value.get("attempt_index") != index
        or isinstance(value.get("attempt_index"), bool)
    ):
        _fail("remote attempt indices are not contiguous one-based integers")
    classification = value.get("classification")
    if classification not in _REMOTE_CLASSIFICATIONS:
        _fail(f"remote attempt {index} classification is invalid")
    exit_code = value.get("exit_code")
    if classification in {"spawn_error", "child_cleanup_failed"}:
        if exit_code is not None:
            _actual_exit(exit_code, f"remote attempt {index} exit code")
    else:
        _actual_exit(exit_code, f"remote attempt {index} exit code")
    timed_out = value.get("timed_out")
    if not isinstance(timed_out, bool):
        _fail("remote attempt timeout flag is not Boolean")
    duration = _nonnegative_int(
        value.get("duration_milliseconds"),
        f"remote attempt {index} duration",
    )
    stdout = _decode_stream(value, "stdout", 4_096)
    stderr = _decode_stream(value, "stderr", 16_384)
    cleanup = value.get("child_cleanup_passes")
    always_cleaned = {
        "post_spawn_initialization_failed", "stream_capture_failed",
        "retryable_timeout_124", "stdout_limit", "stderr_limit", "overall_deadline",
    }
    if classification == "child_cleanup_failed":
        if cleanup is not False:
            _fail("remote cleanup failure must record false cleanup")
    elif classification in always_cleaned:
        if cleanup is not True:
            _fail("controlled remote attempt lacks passing cleanup")
    elif classification == "spawn_error":
        if cleanup is not None:
            _fail("remote pre-child spawn error has non-null cleanup")
    elif cleanup not in {None, True}:
        _fail("normal remote attempt cleanup is not null or true")
    if classification == "verified":
        valid = exit_code == 0 and stdout == expected_stdout and not timed_out
    elif classification == "retryable_empty_exit_0":
        valid = exit_code == 0 and not stdout and not timed_out
    elif classification == "retryable_timeout_124":
        valid = exit_code == 124 and timed_out and duration >= 120_000
    elif classification == "retryable_git_128":
        valid = exit_code == 128 and not stdout and not timed_out
    elif classification == "unexpected_output":
        valid = (
            bool(stdout)
            and not (exit_code == 0 and stdout == expected_stdout)
            and not timed_out
        )
    elif classification == "unexpected_exit":
        valid = exit_code not in {0, 128} and not stdout and not timed_out
    elif classification == "stdout_limit":
        valid = len(stdout) == 4_096 and (not timed_out or exit_code == 124)
    elif classification == "stderr_limit":
        valid = len(stderr) == 16_384 and (not timed_out or exit_code == 124)
    elif classification == "spawn_error":
        valid = exit_code is None and not stdout and not stderr and not timed_out
    elif classification == "post_spawn_initialization_failed":
        valid = not stdout and not stderr and not timed_out
    elif classification == "stream_capture_failed":
        valid = (timed_out and exit_code == 124) or (not timed_out and exit_code is not None)
    elif classification == "overall_deadline":
        valid = exit_code == 124 and timed_out and duration >= 120_000
    else:
        valid = classification == "child_cleanup_failed"
    if not valid:
        _fail(f"remote attempt {index} evidence is invalid")
    return str(classification), duration


def _remote_receipt_valid(
    artifact: _Artifact,
    *,
    claim: _Artifact,
    verifier: _Artifact,
    execution: Mapping[str, Any],
    commit: str,
    registration_sha: str,
) -> bool:
    value = artifact.value
    if value is None:
        return False
    try:
        expected_stdout = (
            f"{commit}\trefs/tags/{_OPEN_FREEZE_TAG}\n".encode("ascii")
        )
        expected_tools = {
            "python": {
                "path": r"C:\Users\User\anaconda3\python.exe",
                "version": "CPython 3.12.3",
                "sha256": "62c225fb9cdc41b139c7024581c233644f975ffc35314558c60ebefa6b88be01",
            },
            "git": {
                "path": r"C:\Users\User\anaconda3\Library\bin\git.exe",
                "version": "2.45.2.windows.1",
                "sha256": "5385ff9ae361ca41e7a31b335fc0d81f2de9c35fc62a165c5e34850d837b59cc",
            },
            "taskkill": {
                "path": r"C:\Windows\System32\taskkill.exe",
                "version": "file/product version 10.0.26100.8457",
                "sha256": "1249717315fc8f4d2df17d5db9da0444795fdb9fb83dfb1f763c3f39282244f7",
            },
        }
        if (
            not _matching(artifact, commit=commit, registration_sha=registration_sha)
            or value.get("claim_sha256") != _sha_or_none(claim)
            or value.get("verifier_start_claim_sha256") != _sha_or_none(verifier)
            or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
            or value.get("remote_url")
            != "https://github.com/bansarinejad/arc3-crosslevel-voi.git"
            or value.get("ref") != f"refs/tags/{_OPEN_FREEZE_TAG}"
            or value.get("policy") != execution.get("remote_policy")
            or any(value.get(name) != expected for name, expected in expected_tools.items())
        ):
            return False
        attempts = value.get("attempts")
        if not isinstance(attempts, list) or len(attempts) > 3:
            return False
        classifications: list[str] = []
        durations: list[int] = []
        for index, attempt in enumerate(attempts, start=1):
            classification, duration = _validate_remote_attempt(
                attempt,
                index=index,
                expected_stdout=expected_stdout,
            )
            classifications.append(classification)
            durations.append(duration)
            if index < len(attempts) and classification not in _REMOTE_RETRYABLE:
                return False
        status = value.get("status")
        selected = value.get("selected_attempt")
        if status == "verified":
            if not attempts or classifications[-1] != "verified" or selected != len(attempts):
                return False
        elif status == "failed":
            if selected is not None or "verified" in classifications:
                return False
        else:
            return False
        total = _nonnegative_int(value.get("total_duration_milliseconds"), "remote duration")
        retry_gaps = max(0, len(attempts) - 1) * 15_000
        return total >= sum(durations) + retry_gaps
    except _FinalizationError:
        return False


def _remote_supervisor_valid(
    artifact: _Artifact,
    *,
    claim: _Artifact,
    verifier: _Artifact,
    receipt: _Artifact,
    remote_receipt_valid: bool,
    execution: Mapping[str, Any],
    commit: str,
    registration_sha: str,
) -> bool:
    value = artifact.value
    if value is None:
        return False
    try:
        if (
            not _matching(artifact, commit=commit, registration_sha=registration_sha)
            or value.get("claim_sha256") != _sha_or_none(claim)
            or value.get("verifier_start_claim_sha256") != _sha_or_none(verifier)
            or value.get("remote_receipt_sha256") != _sha_or_none(receipt)
            or value.get("verifier_argv_sha256")
            != execution["argv_hashes"]["remote_verifier"]
        ):
            return False
        classification = value.get("classification")
        if classification not in _SUPERVISOR_CLASSIFICATIONS:
            return False
        exit_code = value.get("verifier_exit_code")
        if classification in {"spawn_error", "child_cleanup_failed"}:
            if exit_code is not None:
                _actual_exit(exit_code, "supervisor verifier exit code")
        else:
            _actual_exit(exit_code, "supervisor verifier exit code")
        timed_out = value.get("timed_out")
        if not isinstance(timed_out, bool):
            return False
        _nonnegative_int(
            value.get("duration_milliseconds"), "supervisor duration"
        )
        policy = execution.get("remote_policy")
        if not isinstance(policy, Mapping):
            return False
        supervisor_deadline = _nonnegative_int(
            policy.get("supervisor_deadline_seconds"),
            "supervisor deadline",
        )
        receipt_reserve = _nonnegative_int(
            policy.get("supervisor_receipt_reserve_seconds"),
            "supervisor receipt reserve",
        )
        if receipt_reserve > supervisor_deadline:
            return False
        stdout = _decode_stream(value, "stdout", 4_096)
        stderr = _decode_stream(value, "stderr", 16_384)
        cleanup = value.get("child_cleanup_passes")
        always_cleaned = {
            "post_spawn_initialization_failed", "stream_capture_failed",
            "verifier_timeout_124", "stdout_limit", "stderr_limit",
        }
        if classification == "child_cleanup_failed":
            if cleanup is not False:
                return False
        elif classification in always_cleaned:
            if cleanup is not True:
                return False
        elif classification == "spawn_error":
            if cleanup is not None:
                return False
        elif cleanup not in {None, True}:
            return False
        status = value.get("status")
        if status not in {"completed", "failed"} or (
            (classification == "verifier_completed") != (status == "completed")
        ):
            return False
        if classification == "verifier_completed":
            if not remote_receipt_valid or receipt.value is None:
                return False
            expected_exit = 0 if receipt.value.get("status") == "verified" else 1
            return bool(
                exit_code == expected_exit
                and not timed_out
                and not stdout
                and not stderr
                and verifier.value is not None
            )
        if classification == "verifier_timeout_124":
            return exit_code == 124 and timed_out
        if classification == "stdout_limit":
            return len(stdout) == 4_096 and (not timed_out or exit_code == 124)
        if classification == "stderr_limit":
            return len(stderr) == 16_384 and (not timed_out or exit_code == 124)
        if classification == "spawn_error":
            return exit_code is None and not stdout and not stderr and not timed_out
        if classification == "post_spawn_initialization_failed":
            return not stdout and not stderr and not timed_out
        if classification == "stream_capture_failed":
            return (timed_out and exit_code == 124) or (
                not timed_out and exit_code is not None
            )
        if classification == "remote_receipt_missing":
            return receipt.raw is None and not timed_out
        if classification == "remote_receipt_invalid":
            return receipt.raw is not None and not remote_receipt_valid and not timed_out
        return classification == "child_cleanup_failed"
    except _FinalizationError:
        return False


def _validate_layer(value: Any, *, reason_order: Sequence[str], name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != _LAYER_KEYS:
        _fail(f"{name} layer schema is invalid")
    status = value.get("status")
    passes = value.get("passes")
    reasons = value.get("reasons")
    if status not in {"evaluated", "precondition_failed"} or not isinstance(passes, bool):
        _fail(f"{name} layer status/pass is invalid")
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        _fail(f"{name} layer reasons are invalid")
    positions = {reason: index for index, reason in enumerate(reason_order)}
    if (
        len(set(reasons)) != len(reasons)
        or any(reason not in positions for reason in reasons)
        or reasons != sorted(reasons, key=positions.__getitem__)
        or passes is not (status == "evaluated" and not reasons)
        or not isinstance(value.get("details"), Mapping)
    ):
        _fail(f"{name} layer envelope is invalid")


def _validate_grid_table(value: Any) -> set[str]:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "blobs"}:
        _fail("grid evidence table schema is invalid")
    if value.get("schema_version") != "action-qbc-v7-grid-evidence-table-v1":
        _fail("grid evidence table identity is invalid")
    blobs = value.get("blobs")
    if not isinstance(blobs, list):
        _fail("grid evidence blobs are not a list")
    references: list[str] = []
    for index, item in enumerate(blobs):
        if not isinstance(item, Mapping) or set(item) != _GRID_BLOB_KEYS:
            _fail(f"grid blob {index} schema is invalid")
        shape = item.get("shape")
        if (
            item.get("encoding") != "int16-le-c-v1"
            or not isinstance(shape, list)
            or len(shape) != 2
            or any(
                not isinstance(size, int)
                or isinstance(size, bool)
                or size < 1
                or size > 64
                for size in shape
            )
        ):
            _fail(f"grid blob {index} shape/encoding is invalid")
        encoded = item.get("data_base64")
        if not isinstance(encoded, str):
            _fail(f"grid blob {index} Base64 is invalid")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, TypeError, ValueError) as exc:
            raise _FinalizationError(f"grid blob {index} Base64 is invalid") from exc
        digest = _sha256(raw)
        expected_count = shape[0] * shape[1] * 2
        reference = f"{digest}:{shape[0]}:{shape[1]}:int16-le-c-v1"
        if (
            len(raw) != expected_count
            or item.get("byte_count") != expected_count
            or item.get("sha256") != digest
            or item.get("reference") != reference
            or base64.b64encode(raw).decode("ascii") != encoded
        ):
            _fail(f"grid blob {index} byte identity is invalid")
        references.append(reference)
    if references != sorted(set(references)):
        _fail("grid blob references are not sorted and unique")
    return set(references)


def _validate_support_table(value: Any) -> set[str]:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "blobs"}:
        _fail("expected exterior support table schema is invalid")
    if value.get("schema_version") != (
        "action-qbc-v7-expected-exterior-support-table-v1"
    ):
        _fail("expected exterior support table identity is invalid")
    blobs = value.get("blobs")
    if not isinstance(blobs, list):
        _fail("expected exterior support blobs are not a list")
    references: list[str] = []
    for index, item in enumerate(blobs):
        if not isinstance(item, Mapping) or set(item) != _SUPPORT_BLOB_KEYS:
            _fail(f"support blob {index} schema is invalid")
        if item.get("encoding") != "signed-coordinate-label-json-utf8-v1":
            _fail(f"support blob {index} encoding is invalid")
        encoded = item.get("data_base64")
        if not isinstance(encoded, str):
            _fail(f"support blob {index} Base64 is invalid")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, TypeError, ValueError) as exc:
            raise _FinalizationError(f"support blob {index} Base64 is invalid") from exc
        entries = _parse_value(raw, f"support blob {index} data")
        if not isinstance(entries, list):
            _fail(f"support blob {index} data is not a list")
        for entry in entries:
            if (
                not isinstance(entry, list)
                or len(entry) != 3
                or any(not isinstance(item, int) or isinstance(item, bool) for item in entry)
                or entry[2] < -32_768
                or entry[2] > 32_767
            ):
                _fail(f"support blob {index} entry is invalid")
        if entries != sorted(entries) or len({tuple(entry) for entry in entries}) != len(entries):
            _fail(f"support blob {index} entries are not sorted and distinct")
        digest = _sha256(raw)
        reference = f"{digest}:{len(entries)}:signed-coordinate-label-json-utf8-v1"
        if (
            item.get("entry_count") != len(entries)
            or item.get("byte_count") != len(raw)
            or item.get("sha256") != digest
            or item.get("reference") != reference
            or base64.b64encode(raw).decode("ascii") != encoded
        ):
            _fail(f"support blob {index} byte identity is invalid")
        references.append(reference)
    if references != sorted(set(references)):
        _fail("support blob references are not sorted and unique")
    return set(references)


def _collect_references(rows: Sequence[Any]) -> tuple[set[str], set[str]]:
    grid: set[str] = set()
    support: set[str] = set()
    grid_names = {
        "base_prediction_ref",
        "transformed_prediction_ref",
        "expected_prediction_ref",
        "observable_mismatch_mask_ref",
    }
    for row in rows:
        evidence = row.get("evidence") if isinstance(row, Mapping) else None
        root = evidence.get("root_transition") if isinstance(evidence, Mapping) else None
        details = root.get("details") if isinstance(root, Mapping) else None
        records = details.get("pair_records") if isinstance(details, Mapping) else None
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            for name in grid_names:
                reference = record.get(name)
                if isinstance(reference, str):
                    grid.add(reference)
            reference = record.get("expected_exterior_support_ref")
            if isinstance(reference, str):
                support.add(reference)
    return grid, support


def _validate_payload(
    raw: bytes,
    registration: Mapping[str, Any],
    *,
    commit: str,
    registration_file_sha256: str,
) -> bool:
    try:
        if len(raw) > _PAYLOAD_CAP:
            return False
        payload = _parse(raw, "scientific payload")
        if set(payload) != _PAYLOAD_KEYS:
            return False
        if (
            payload.get("schema_version") != _PAYLOAD_SCHEMA
            or payload.get("treatment_id") != _TREATMENT_ID
            or payload.get("diagnostic_system_id") != _DIAGNOSTIC_ID
            or payload.get("comparison_semantics_id") != _COMPARISON_ID
            or payload.get("runtime_id") is not None
            or payload.get("authorization") != _AUTHORIZATION
            or payload.get("scientific_capability_passes") is not False
            or payload.get("preregistration_identity") != registration.get("preregistration")
            or payload.get("v6_negative_identity") != registration.get("v6_negative")
        ):
            return False
        registration_identity = payload.get("registration_identity")
        execution_identity = payload.get("execution_identity")
        source_manifest = registration.get("source_manifest")
        execution = registration.get("execution_contract")
        if not all(
            isinstance(item, Mapping)
            for item in (registration_identity, execution_identity, source_manifest, execution)
        ):
            return False
        if set(registration_identity) != {
            "schema_version",
            "path",
            "content_sha256",
            "file_sha256",
        } or set(execution_identity) != {
            "open_freeze_commit_sha",
            "open_freeze_tag",
            "source_manifest_sha256",
            "python_version",
            "python_implementation",
            "platform_system",
            "platform_machine",
            "uv_version",
            "uv_lock_sha256",
            "canonical_command_sha256",
        }:
            return False
        preregistration_tree = source_manifest.get("preregistration_tree")
        uv_rows = (
            [
                row
                for row in preregistration_tree
                if isinstance(row, Mapping) and row.get("path") == "uv.lock"
            ]
            if isinstance(preregistration_tree, list)
            else []
        )
        if len(uv_rows) != 1:
            return False
        if (
            registration_identity.get("schema_version") != _REGISTRATION_SCHEMA
            or registration_identity.get("path") != _REGISTRATION
            or registration_identity.get("content_sha256") != registration.get("content_sha256")
            or registration_identity.get("file_sha256") != registration_file_sha256
            or execution_identity.get("open_freeze_commit_sha") != commit
            or execution_identity.get("open_freeze_tag") != _OPEN_FREEZE_TAG
            or execution_identity.get("source_manifest_sha256")
            != source_manifest.get("manifest_sha256")
            or execution_identity.get("canonical_command_sha256")
            != execution.get("argv_hashes", {}).get("scientific")
            or execution_identity.get("python_version") != "3.12.13"
            or execution_identity.get("python_implementation") != "CPython"
            or execution_identity.get("platform_system") != "Linux"
            or execution_identity.get("platform_machine") != "x86_64"
            or execution_identity.get("uv_version") != "0.11.28"
            or execution_identity.get("uv_lock_sha256") != uv_rows[0].get("sha256")
        ):
            return False
        resource = registration.get("resource_contract")
        counters = payload.get("resource_counters")
        expected_counts = resource.get("expected_counts") if isinstance(resource, Mapping) else None
        if (
            not isinstance(resource, Mapping)
            or not isinstance(counters, Mapping)
            or not isinstance(expected_counts, Mapping)
            or set(counters) != set(expected_counts)
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in counters.values()
            )
        ):
            return False
        rows = payload.get("rows")
        inventory = registration.get("row_inventory")
        registered_rows = inventory.get("rows") if isinstance(inventory, Mapping) else None
        scientific = registration.get("scientific_contract")
        reason_order = scientific.get("reason_order") if isinstance(scientific, Mapping) else None
        if (
            not isinstance(rows, list)
            or not isinstance(registered_rows, list)
            or len(rows) != len(registered_rows)
            or (isinstance(inventory, Mapping) and inventory.get("count") != len(registered_rows))
            or not isinstance(reason_order, list)
            or not all(isinstance(reason, str) for reason in reason_order)
            or len(set(reason_order)) != len(reason_order)
        ):
            return False
        has_terminal = False
        has_global_terminal = False
        for index, (observed, registered) in enumerate(zip(rows, registered_rows, strict=True)):
            if not isinstance(observed, Mapping) or not isinstance(registered, Mapping):
                return False
            address = observed.get("address")
            if (
                set(observed) != _ROW_KEYS
                or not isinstance(address, Mapping)
                or set(address) != _ADDRESS_KEYS
                or dict(address)
                != {
                "row_index": registered.get("row_index"),
                "row_id": registered.get("row_id"),
                "kind": registered.get("kind"),
                }
                or registered.get("row_index") != index
                or observed.get("registered_row") != registered
            ):
                return False
            disposition = observed.get("disposition")
            if disposition == "completed":
                evidence = observed.get("evidence")
                expected_layers = _EVIDENCE_KEYS.get(str(registered.get("kind")))
                if (
                    observed.get("terminal") is not None
                    or not isinstance(evidence, Mapping)
                    or expected_layers is None
                    or set(evidence) != expected_layers
                ):
                    return False
                for layer_name, layer in evidence.items():
                    _validate_layer(layer, reason_order=reason_order, name=layer_name)
            elif disposition in {
                "terminal_addressable_negative",
                "terminal_global_negative",
            }:
                has_terminal = True
                has_global_terminal = has_global_terminal or (
                    disposition == "terminal_global_negative"
                )
                terminal = observed.get("terminal")
                if (
                    observed.get("evidence") != {}
                    or not isinstance(terminal, Mapping)
                    or set(terminal) != _TERMINAL_KEYS
                ):
                    return False
                if disposition == "terminal_addressable_negative" and terminal != {
                    "status": "authoritative_derivation_error",
                    "stage": "scientific_record_schema_invalid",
                }:
                    return False
            else:
                return False

        grid_references = _validate_grid_table(payload.get("grid_evidence"))
        support_references = _validate_support_table(payload.get("expected_exterior_support"))
        used_grid, used_support = _collect_references(rows)
        if used_grid != grid_references or used_support != support_references:
            return False
        aggregates = payload.get("aggregates")
        aggregate_keys = (
            scientific.get("aggregate_keys") if isinstance(scientific, Mapping) else None
        )
        if (
            not isinstance(aggregates, Mapping)
            or not isinstance(aggregate_keys, list)
            or not all(isinstance(key, str) for key in aggregate_keys)
            or set(aggregates) != set(aggregate_keys)
        ):
            return False
        reasons = aggregates.get("reason_counts")
        if (
            not isinstance(reasons, Mapping)
            or set(reasons) != set(reason_order)
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in reasons.values()
            )
        ):
            return False
        increment = resource.get("increment_contract")
        zero_forbidden = (
            increment.get("zero_forbidden") if isinstance(increment, Mapping) else None
        )
        if not isinstance(zero_forbidden, list) or any(
            name not in counters for name in zero_forbidden
        ):
            return False
        expected_resource_pass = counters == expected_counts and all(
            counters[name] == 0 for name in zero_forbidden
        )
        if aggregates.get("resource_contract_passes") is not expected_resource_pass:
            return False

        fallback_stage = payload.get("terminal_fallback_stage")
        candidate_size = payload.get("candidate_payload_size_bytes")
        if fallback_stage is None:
            if candidate_size is not None or has_global_terminal:
                return False
        else:
            if (
                fallback_stage not in _GLOBAL_STAGES
                or not has_global_terminal
                or any(row.get("disposition") != "terminal_global_negative" for row in rows)
                or payload.get("diagnostic_complete") is not False
            ):
                return False
            if fallback_stage == "payload_size_limit_exceeded":
                if (
                    not isinstance(candidate_size, int)
                    or isinstance(candidate_size, bool)
                    or candidate_size <= _PAYLOAD_CAP
                ):
                    return False
            elif candidate_size is not None:
                return False
            if payload.get("grid_evidence") != {
                "schema_version": "action-qbc-v7-grid-evidence-table-v1",
                "blobs": [],
            } or payload.get("expected_exterior_support") != {
                "schema_version": "action-qbc-v7-expected-exterior-support-table-v1",
                "blobs": [],
            }:
                return False
            expected_status = (
                "evaluator_internal_error"
                if fallback_stage == "evaluator_internal_error"
                else "payload_size_limit_exceeded"
                if fallback_stage == "payload_size_limit_exceeded"
                else "authoritative_derivation_error"
            )
            if any(
                row.get("terminal")
                != {"status": expected_status, "stage": fallback_stage}
                for row in rows
            ):
                return False
        diagnostic_complete = payload.get("diagnostic_complete")
        return bool(
            isinstance(diagnostic_complete, bool)
            and (not has_terminal or diagnostic_complete is False)
            and (not diagnostic_complete or expected_resource_pass)
        )
    except (TypeError, ValueError, _FinalizationError):
        return False


def _process(
    label: str,
    *,
    output: str,
    start_path: str,
    validator_path: str,
    validation_path: str,
    ledger_record: Mapping[str, Any] | None,
    registration: Mapping[str, Any],
    commit: str,
    arm_raw: bytes | None,
    driver_raw: bytes | None,
    prior_validation_raw: bytes | None,
    registration_file_sha256: str,
) -> _Process:
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    lower = label.casefold()
    replacements = {
        "<LABEL>": label,
        "<START_CLAIM>": start_path,
        "<PRIOR_VALIDATION_OR_NULL>": "null" if label == "A" else _PROCESS_A_VALIDATION,
        "<OUTPUT_PATH>": output,
    }
    scientific_argv = _substituted_argv(
        execution.get("scientific_argv_template"),
        replacements,
        "scientific",
    )
    validator_argv = _substituted_argv(
        execution.get("payload_validator_argv_template"),
        {
            "<LABEL>": label,
            "<START_CLAIM>": start_path,
            "<VALIDATOR_CLAIM>": validator_path,
            "<VALIDATION_RECEIPT>": validation_path,
            "<OUTPUT_PATH>": output,
        },
        "payload-validator",
    )
    if (
        start_path != execution.get(f"process_{lower}_start_claim")
        or validator_path != execution.get(f"process_{lower}_validator_claim")
        or validation_path != execution.get(f"process_{lower}_validation_receipt")
        or output != execution.get(f"process_{lower}_output")
    ):
        _fail(f"process {label} paths differ from registration")
    start = _artifact(
        start_path,
        role=f"process_{lower}_start_claim",
        name=f"process {label} start claim",
        keys=_START_KEYS,
        schema="action-qbc-v8-scientific-start-claim-v1",
    )
    validator_claim = _artifact(
        validator_path,
        role=f"process_{lower}_validator_claim",
        name=f"process {label} validator claim",
        keys=_VALIDATOR_KEYS,
        schema="action-qbc-v8-payload-validator-claim-v1",
    )
    validation = _artifact(
        validation_path,
        role=f"process_{lower}_validation_receipt",
        name=f"process {label} validation receipt",
        keys=_VALIDATION_KEYS,
        schema="action-qbc-v8-payload-validation-receipt-v1",
    )
    payload = _artifact(
        output,
        role=f"process_{lower}_payload",
        name=f"process {label} payload",
    )
    payload_exists = payload.exists
    payload_raw = payload.raw
    start_valid = bool(
        start.value is not None
        and start.value.get("label") == label
        and start.value.get("open_freeze_commit_sha") == commit
        and start.value.get("registration_content_sha256") == registration.get("content_sha256")
        and start.value.get("arm_receipt_sha256")
        == (_sha256(arm_raw) if arm_raw is not None else None)
        and start.value.get("lifecycle_driver_claim_sha256")
        == (_sha256(driver_raw) if driver_raw is not None else None)
        and start.value.get("prior_validation_receipt_sha256")
        == (_sha256(prior_validation_raw) if prior_validation_raw is not None else None)
        and start.value.get("scientific_argv_sha256")
        == _sha256(_canonical(scientific_argv))
        and start.value.get("output_path") == output
    )
    validator_valid = bool(
        validator_claim.value is not None
        and validator_claim.value.get("label") == label
        and validator_claim.value.get("lifecycle_driver_claim_sha256")
        == (_sha256(driver_raw) if driver_raw is not None else None)
        and validator_claim.value.get("start_claim_sha256") == _sha_or_none(start)
        and validator_claim.value.get("payload_sha256")
        == (_sha256(payload_raw) if payload_raw is not None else None)
        and validator_claim.value.get("validator_argv_sha256")
        == _sha256(_canonical(validator_argv))
    )
    validation_valid = bool(
        validation.value is not None
        and validation.value.get("label") == label
        and validation.value.get("start_claim_sha256") == _sha_or_none(start)
        and validation.value.get("validator_claim_sha256") == _sha_or_none(validator_claim)
        and validation.value.get("payload_path") == output
        and validation.value.get("payload_sha256")
        == (_sha256(payload_raw) if payload_raw is not None else None)
        and validation.value.get("payload_size_bytes")
        == (len(payload_raw) if payload_raw is not None else None)
        and validation.value.get("status") == "valid"
    )
    payload_valid = bool(
        payload_raw is not None
        and start_valid
        and validator_valid
        and validation_valid
        and _validate_payload(
            payload_raw,
            registration,
            commit=commit,
            registration_file_sha256=registration_file_sha256,
        )
    )
    exit_code = ledger_record.get("runner_exit_code") if ledger_record is not None else None
    validator_exit = (
        ledger_record.get("validator_exit_code") if ledger_record is not None else None
    )
    record = {
        "label": label,
        "output_path": output,
        "exit_code": exit_code,
        "validator_exit_code": validator_exit,
        "start_claim": start.value if start_valid else None,
        "start_claim_sha256": _sha_or_none(start),
        "validator_claim": validator_claim.value if validator_valid else None,
        "validator_claim_sha256": _sha_or_none(validator_claim),
        "validation_receipt": validation.value if validation_valid else None,
        "validation_receipt_sha256": _sha_or_none(validation),
        "payload_exists": payload_exists,
        "payload_valid": payload_valid,
        "payload_sha256": _sha256(payload_raw) if payload_raw is not None else None,
        "payload_size_bytes": len(payload_raw) if payload_raw is not None else None,
    }
    if set(record) != _PROCESS_KEYS:
        _fail("internal process schema is invalid")
    machine_recordable = bool(
        all(
            not artifact.exists or artifact.raw is not None
            for artifact in (start, validator_claim, validation)
        )
        and (not payload_exists or payload_raw is not None)
    )
    return _Process(
        record,
        payload_raw if payload_valid else None,
        machine_recordable=machine_recordable,
    )


def _first(candidates: Sequence[str]) -> str | None:
    if not candidates:
        return None
    positions = {stage: index for index, stage in enumerate(_UNDERLYING_ORDER)}
    return min(candidates, key=positions.__getitem__)


def _substituted_argv(
    template: object,
    replacements: Mapping[str, str],
    name: str,
) -> list[str]:
    if not isinstance(template, list) or not all(isinstance(item, str) for item in template):
        _fail(f"registered {name} argv template is invalid")
    result = [replacements.get(item, item) for item in template]
    if any(item.startswith("<") and item.endswith(">") for item in result):
        _fail(f"registered {name} argv retains a placeholder")
    return result


def _ledger_process_valid(
    record: object,
    *,
    label: str,
    execution: Mapping[str, Any],
    sequence: Sequence[str],
) -> bool:
    if not isinstance(record, Mapping) or set(record) != _LEDGER_PROCESS_KEYS:
        return False
    lower = label.casefold()
    start = str(execution.get(f"process_{lower}_start_claim"))
    validator_claim = str(execution.get(f"process_{lower}_validator_claim"))
    validation = str(execution.get(f"process_{lower}_validation_receipt"))
    output = str(execution.get(f"process_{lower}_output"))
    root = str(execution.get(f"process_{lower}_root"))
    prior = "null" if label == "A" else str(execution.get("process_a_validation_receipt"))
    scientific = _substituted_argv(
        execution.get("scientific_argv_template"),
        {
            "<LABEL>": label,
            "<START_CLAIM>": start,
            "<PRIOR_VALIDATION_OR_NULL>": prior,
            "<OUTPUT_PATH>": output,
        },
        "scientific",
    )
    validator_argv = _substituted_argv(
        execution.get("payload_validator_argv_template"),
        {
            "<LABEL>": label,
            "<START_CLAIM>": start,
            "<VALIDATOR_CLAIM>": validator_claim,
            "<VALIDATION_RECEIPT>": validation,
            "<OUTPUT_PATH>": output,
        },
        "payload-validator",
    )
    runner_returned = f"process_{lower}_runner_returned" in sequence
    validator_returned = f"process_{lower}_validator_returned" in sequence
    runner_exit = record.get("runner_exit_code")
    validator_exit = record.get("validator_exit_code")
    expected_runner_hash = _sha256(_canonical(scientific))
    expected_validator_hash = _sha256(_canonical(validator_argv))
    runner_hash = record.get("runner_argv_sha256")
    validator_hash = record.get("validator_argv_sha256")
    start_hash = record.get("start_claim_sha256")
    validator_claim_hash = record.get("validator_claim_sha256")
    validation_hash = record.get("validation_receipt_sha256")
    output_hash = record.get("output_sha256")

    def valid_exit(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    for key in (
        "runner_argv_sha256",
        "validator_argv_sha256",
        "start_claim_sha256",
        "validator_claim_sha256",
        "validation_receipt_sha256",
        "output_sha256",
    ):
        value = record.get(key)
        if value is not None:
            try:
                _lower_hex(value, 64, f"ledger process {label} {key}")
            except _FinalizationError:
                return False

    return bool(
        record.get("label") == label
        and record.get("cwd") == root
        and runner_hash in {None, expected_runner_hash}
        and validator_hash in {None, expected_validator_hash}
        and (not runner_returned or runner_hash == expected_runner_hash)
        and (not validator_returned or validator_hash == expected_validator_hash)
        and (valid_exit(runner_exit) if runner_returned else runner_exit is None)
        and (valid_exit(validator_exit) if validator_returned else validator_exit is None)
        and (validator_hash is None or runner_returned)
        and (validator_hash is None or runner_exit == 0)
        and (output_hash is None or start_hash is not None)
        and (validator_claim_hash is None or start_hash is not None)
        and (validation_hash is None or validator_claim_hash is not None)
        and (
            not runner_returned
            or runner_exit != 0
            or (start_hash is not None and output_hash is not None)
        )
        and (
            not validator_returned
            or validator_exit != 0
            or (
                validator_claim_hash is not None
                and validation_hash is not None
            )
        )
        and (
            runner_hash is not None
            or all(
                record.get(key) is None
                for key in (
                    "start_claim_sha256",
                    "validator_claim_sha256",
                    "validation_receipt_sha256",
                    "output_sha256",
                )
            )
        )
        and (
            validator_hash is not None
            or all(
                record.get(key) is None
                for key in ("validator_claim_sha256", "validation_receipt_sha256")
            )
        )
    )


def _ledger_artifacts_match(process: _Process, ledger_record: Mapping[str, Any]) -> bool:
    return all(
        ledger_record.get(ledger_key) == process.record.get(process_key)
        for ledger_key, process_key in (
            ("start_claim_sha256", "start_claim_sha256"),
            ("validator_claim_sha256", "validator_claim_sha256"),
            ("validation_receipt_sha256", "validation_receipt_sha256"),
            ("output_sha256", "payload_sha256"),
        )
    )


def _reached_lifecycle_stage(
    *,
    sequence: Sequence[str],
    arm_exit: object,
    ready_for_a: bool,
    process_a: _Process,
    process_b: _Process,
) -> str | None:
    """Rederive the reached child outcome without treating an unreached child as nonzero."""
    reached = set(sequence)
    if "arm_returned" not in reached:
        return "lifecycle_driver_failed"
    if arm_exit != 0 or not ready_for_a:
        return None
    if "process_a_runner_returned" not in reached:
        return "lifecycle_driver_failed"
    if process_a.record["exit_code"] != 0:
        return "process_a_nonzero"
    if process_a.record["payload_sha256"] is None:
        return "process_a_output_missing"
    if "process_a_validator_returned" not in reached:
        return "lifecycle_driver_failed"
    if (
        process_a.record["validator_exit_code"] != 0
        or not process_a.record["payload_valid"]
    ):
        return "process_a_validation_failed"
    if "process_b_runner_returned" not in reached:
        return "lifecycle_driver_failed"
    if process_b.record["exit_code"] != 0:
        return "process_b_nonzero"
    if process_b.record["payload_sha256"] is None:
        return "process_b_output_missing"
    if "process_b_validator_returned" not in reached:
        return "lifecycle_driver_failed"
    if (
        process_b.record["validator_exit_code"] != 0
        or not process_b.record["payload_valid"]
    ):
        return "process_b_validation_failed"
    if process_a.raw != process_b.raw:
        return "payload_byte_mismatch"
    return None


def _file_object(path: str, raw: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "mode": "100644",
        "size_bytes": len(raw),
        "sha256": _sha256(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }


def _normal_document(
    registration: Mapping[str, Any],
    *,
    disposition: str,
    stage: str | None,
    underlying_stage: str | None,
    commit: str,
) -> bytes:
    exposed = stage if stage is not None else "null"
    if stage == "receipt_finalization_failed":
        case_underlying = "<UNDERLYING_STAGE_OR_NULL>"
    else:
        case_underlying = underlying_stage if underlying_stage is not None else "null"
    template_case = _NORMAL_TEMPLATE.format(
        disposition=disposition,
        stage=exposed,
        underlying_stage=case_underlying,
        open_freeze_commit_sha="<O8_COMMIT>",
        registration_content_sha256="<REGISTRATION_CONTENT_SHA256>",
    ).encode("ascii")
    execution = registration.get("execution_contract")
    contract = (
        execution.get("result_document_contract") if isinstance(execution, Mapping) else None
    )
    if (
        not isinstance(contract, Mapping)
        or contract.get("schema_version") != _RESULT_DOCUMENT_SCHEMA
    ):
        _fail("registered result-document contract is invalid")
    if set(contract) != {
        "schema_version",
        "renderer_source",
        "normal_template",
        "emergency_template",
        "normal_input_names",
        "emergency_input_names",
        "normal_cases",
    }:
        _fail("result-document contract has an invalid key set")
    normal_template = contract.get("normal_template")
    if (
        not isinstance(normal_template, Mapping)
        or set(normal_template) != {"text", "sha256"}
        or normal_template.get("text") != _NORMAL_TEMPLATE
    ):
        _fail("registered normal result template differs from the finalizer")
    if normal_template.get("sha256") != _sha256(_NORMAL_TEMPLATE.encode("ascii")):
        _fail("registered normal result template digest is invalid")
    emergency_text = _NORMAL_TEMPLATE + _EMERGENCY_SUFFIX
    emergency_template = contract.get("emergency_template")
    if (
        not isinstance(emergency_template, Mapping)
        or set(emergency_template) != {"text", "sha256"}
        or emergency_template.get("text") != emergency_text
        or emergency_template.get("sha256") != _sha256(emergency_text.encode("ascii"))
    ):
        _fail("registered emergency result template is invalid")
    if contract.get("normal_input_names") != [
        "disposition",
        "open_freeze_commit_sha",
        "registration_content_sha256",
        "stage",
        "underlying_stage",
    ] or contract.get("emergency_input_names") != [
        "disposition",
        "finalization_bundle_exists",
        "finalization_bundle_sha256",
        "finalizer_child_cleanup_passes",
        "finalizer_classification",
        "finalizer_exit_code",
        "finalizer_timed_out",
        "lifecycle_ledger_exists",
        "lifecycle_ledger_sha256",
        "open_freeze_commit_sha",
        "preparation_receipt_exists",
        "preparation_receipt_read_status",
        "preparation_receipt_sha256",
        "preparation_verification_receipt_exists",
        "preparation_verification_receipt_read_status",
        "preparation_verification_receipt_sha256",
        "registration_content_sha256",
        "stage",
        "underlying_stage",
    ]:
        _fail("registered result-document input names are invalid")
    cases = contract.get("normal_cases")
    if not isinstance(cases, list):
        _fail("registered normal result cases are invalid")
    expected_case_underlying = (
        "<UNDERLYING_STAGE_OR_NULL>"
        if stage == "receipt_finalization_failed"
        else underlying_stage
    )
    matching = [
        item
        for item in cases
        if isinstance(item, Mapping)
        and item.get("disposition") == disposition
        and item.get("stage") == stage
        and item.get("underlying_stage") == expected_case_underlying
    ]
    if len(matching) != 1:
        _fail("registered normal result case is missing or ambiguous")
    case = matching[0]
    if set(case) != {
        "disposition",
        "stage",
        "underlying_stage",
        "content_base64",
        "sha256",
        "size_bytes",
    }:
        _fail("registered normal result case has an invalid key set")
    try:
        bound = base64.b64decode(str(case["content_base64"]), validate=True)
    except ValueError as exc:
        raise _FinalizationError("registered result case Base64 is invalid") from exc
    if (
        bound != template_case
        or case.get("sha256") != _sha256(bound)
        or case.get("size_bytes") != len(bound)
    ):
        _fail("registered normal result case bytes are invalid")
    rendered = bound
    replacements = {
        b"<O8_COMMIT>": commit.encode("ascii"),
        b"<REGISTRATION_CONTENT_SHA256>": str(registration["content_sha256"]).encode("ascii"),
    }
    if b"<UNDERLYING_STAGE_OR_NULL>" in rendered:
        replacements[b"<UNDERLYING_STAGE_OR_NULL>"] = (
            (underlying_stage if underlying_stage is not None else "null").encode("ascii")
        )
    for old, new in replacements.items():
        if rendered.count(old) != 1:
            _fail("registered result template placeholder count is invalid")
        rendered = rendered.replace(old, new)
    if b"<" in rendered or b">" in rendered:
        _fail("rendered result document retains a placeholder")
    return rendered


def _bundle(
    *,
    registration: Mapping[str, Any],
    commit: str,
    disposition: str,
    stage: str | None,
    underlying_stage: str | None,
    files: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    value = {
        "schema_version": _BUNDLE_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "disposition": disposition,
        "stage": stage,
        "underlying_stage": underlying_stage,
        "files": sorted(files, key=lambda item: str(item["path"]).encode("utf-8")),
        "authorization": _AUTHORIZATION,
    }
    value["content_sha256"] = _sha256(_canonical(value))
    return value


def _decode_bundle_file(value: Any) -> tuple[str, bytes]:
    if not isinstance(value, Mapping) or set(value) != _FILE_KEYS:
        _fail("bundle file object has an invalid key set")
    path = value.get("path")
    if (
        not isinstance(path, str)
        or not path
        or "\\" in path
        or path.startswith("/")
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        _fail("bundle file path is not canonical repository-relative POSIX text")
    if value.get("mode") != "100644":
        _fail("bundle file mode is not 100644")
    encoded = value.get("content_base64")
    if not isinstance(encoded, str) or any(ord(character) > 127 for character in encoded):
        _fail("bundle file Base64 is invalid")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (TypeError, ValueError) as exc:
        raise _FinalizationError("bundle file Base64 is invalid") from exc
    size = value.get("size_bytes")
    digest = value.get("sha256")
    if (
        base64.b64encode(raw).decode("ascii") != encoded
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size != len(raw)
        or _lower_hex(digest, 64, "bundle file SHA-256") != _sha256(raw)
    ):
        _fail("bundle file byte identity is invalid")
    return path, raw


def _optional_sha(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _lower_hex(value, 64, name)


def _embedded_object(
    value: Any,
    *,
    keys: set[str],
    schema: str,
    commit: str,
    registration_sha: str,
    name: str,
) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or value.get("schema_version") != schema
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
    ):
        _fail(f"embedded {name} identity/schema is invalid")
    return value


def _validate_result_process(
    value: Any,
    *,
    label: str,
    commit: str,
    registration_sha: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PROCESS_KEYS:
        _fail(f"result process {label} schema is invalid")
    expected_output = _PROCESS_A if label == "A" else _PROCESS_B
    if value.get("label") != label or value.get("output_path") != expected_output:
        _fail(f"result process {label} identity is invalid")
    for member in ("exit_code", "validator_exit_code"):
        observed = value.get(member)
        if observed is not None:
            _nonnegative_int(observed, f"result process {label} {member}")
    if value.get("validator_exit_code") is not None and value.get("exit_code") != 0:
        _fail(f"result process {label} validator order is invalid")
    for member in (
        "start_claim_sha256",
        "validator_claim_sha256",
        "validation_receipt_sha256",
        "payload_sha256",
    ):
        _optional_sha(value.get(member), f"result process {label} {member}")

    start = value.get("start_claim")
    if start is not None:
        if (
            not isinstance(start, Mapping)
            or set(start) != _START_KEYS
            or start.get("schema_version")
            != "action-qbc-v8-scientific-start-claim-v1"
            or start.get("treatment_id") != _TREATMENT_ID
            or start.get("label") != label
            or start.get("open_freeze_commit_sha") != commit
            or start.get("registration_content_sha256") != registration_sha
            or start.get("output_path") != expected_output
            or value.get("start_claim_sha256") != _sha256(_canonical(start))
        ):
            _fail(f"result process {label} embedded start claim is invalid")
        for member in (
            "arm_receipt_sha256",
            "lifecycle_driver_claim_sha256",
            "scientific_argv_sha256",
        ):
            _lower_hex(start.get(member), 64, f"process {label} start {member}")
        _optional_sha(
            start.get("prior_validation_receipt_sha256"),
            f"process {label} prior validation SHA-256",
        )

    validator_claim = value.get("validator_claim")
    if validator_claim is not None:
        if (
            not isinstance(validator_claim, Mapping)
            or set(validator_claim) != _VALIDATOR_KEYS
            or validator_claim.get("schema_version")
            != "action-qbc-v8-payload-validator-claim-v1"
            or validator_claim.get("treatment_id") != _TREATMENT_ID
            or validator_claim.get("label") != label
            or value.get("validator_claim_sha256")
            != _sha256(_canonical(validator_claim))
        ):
            _fail(f"result process {label} embedded validator claim is invalid")
        for member in (
            "lifecycle_driver_claim_sha256",
            "start_claim_sha256",
            "validator_argv_sha256",
            "payload_sha256",
        ):
            _lower_hex(
                validator_claim.get(member),
                64,
                f"process {label} validator {member}",
            )

    validation = value.get("validation_receipt")
    if validation is not None:
        if (
            not isinstance(validation, Mapping)
            or set(validation) != _VALIDATION_KEYS
            or validation.get("schema_version")
            != "action-qbc-v8-payload-validation-receipt-v1"
            or validation.get("treatment_id") != _TREATMENT_ID
            or validation.get("label") != label
            or validation.get("payload_path") != expected_output
            or validation.get("status") != "valid"
            or value.get("validation_receipt_sha256")
            != _sha256(_canonical(validation))
        ):
            _fail(f"result process {label} embedded validation receipt is invalid")
        _lower_hex(
            validation.get("start_claim_sha256"),
            64,
            f"process {label} validation start SHA-256",
        )
        _lower_hex(
            validation.get("validator_claim_sha256"),
            64,
            f"process {label} validation claim SHA-256",
        )
        _lower_hex(
            validation.get("payload_sha256"),
            64,
            f"process {label} validation payload SHA-256",
        )
        _nonnegative_int(
            validation.get("payload_size_bytes"),
            f"process {label} validation payload size",
        )

    payload_exists = value.get("payload_exists")
    payload_valid = value.get("payload_valid")
    payload_sha = value.get("payload_sha256")
    payload_size = value.get("payload_size_bytes")
    if not isinstance(payload_exists, bool) or not isinstance(payload_valid, bool):
        _fail(f"result process {label} payload flags are invalid")
    if payload_exists:
        if payload_sha is None:
            _fail(f"result process {label} existing payload lacks raw identity")
        _nonnegative_int(payload_size, f"result process {label} payload size")
    elif payload_sha is not None or payload_size is not None or payload_valid:
        _fail(f"result process {label} absent payload evidence is inconsistent")
    if payload_valid and (
        value.get("exit_code") != 0
        or value.get("validator_exit_code") != 0
        or start is None
        or validator_claim is None
        or validation is None
        or validator_claim.get("start_claim_sha256")
        != value.get("start_claim_sha256")
        or validator_claim.get("payload_sha256") != payload_sha
        or validation.get("start_claim_sha256") != value.get("start_claim_sha256")
        or validation.get("validator_claim_sha256")
        != value.get("validator_claim_sha256")
        or validation.get("payload_sha256") != payload_sha
        or validation.get("payload_size_bytes") != payload_size
    ):
        _fail(f"result process {label} valid-payload evidence is inconsistent")
    return value


def _validate_embedded_success_evidence(
    embedded: Mapping[str, Mapping[str, Any] | None],
    *,
    registration: Mapping[str, Any],
    commit: str,
    registration_sha: str,
) -> None:
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")

    def artifact(name: str) -> _Artifact:
        value = embedded.get(name)
        if value is None:
            _fail(f"successful receipt lacks {name}")
        raw = _canonical(value)
        return _Artifact(True, "readable", raw, _sha256(raw), dict(value))

    preparation = artifact("preparation_receipt")
    preparation_verification = artifact("preparation_verification_receipt")
    claim = artifact("remote_verification_claim")
    verifier = artifact("remote_verifier_claim")
    receipt = artifact("remote_verification_receipt")
    supervisor = artifact("remote_supervisor_receipt")
    arm = artifact("arm_receipt")
    if not _preparation_valid(
        preparation,
        commit=commit,
        registration_sha=registration_sha,
        verify_filesystem=False,
        execution=execution,
        registration=registration,
    ):
        _fail("successful receipt preparation evidence is invalid")
    if not _preparation_verification_valid(
        preparation_verification,
        preparation=preparation,
        commit=commit,
        registration_sha=registration_sha,
        execution=execution,
    ):
        _fail("successful receipt preparation-verification evidence is invalid")
    claim_valid = _remote_claim_valid(
        claim,
        registration=registration,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    verifier_valid = _remote_verifier_valid(
        verifier,
        claim=claim,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    receipt_valid = _remote_receipt_valid(
        receipt,
        claim=claim,
        verifier=verifier,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    supervisor_valid = _remote_supervisor_valid(
        supervisor,
        claim=claim,
        verifier=verifier,
        receipt=receipt,
        remote_receipt_valid=receipt_valid,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    if (
        not claim_valid
        or not verifier_valid
        or not receipt_valid
        or receipt.value is None
        or receipt.value.get("status") != "verified"
        or not supervisor_valid
        or supervisor.value is None
        or supervisor.value.get("status") != "completed"
        or not _matching(arm, commit=commit, registration_sha=registration_sha)
        or arm.value is None
        or arm.value.get("status") != "armed"
        or arm.value.get("preparation_receipt_exists") is not True
        or arm.value.get("preparation_receipt_read_status") != "readable"
        or arm.value.get("preparation_receipt_sha256") != _sha_or_none(preparation)
        or arm.value.get("preparation_verification_receipt_exists") is not True
        or arm.value.get("preparation_verification_receipt_read_status") != "readable"
        or arm.value.get("preparation_verification_receipt_sha256")
        != _sha_or_none(preparation_verification)
        or arm.value.get("remote_claim_sha256") != _sha_or_none(claim)
        or arm.value.get("remote_verifier_claim_sha256") != _sha_or_none(verifier)
        or arm.value.get("remote_receipt_sha256") != _sha_or_none(receipt)
        or arm.value.get("remote_supervisor_receipt_sha256") != _sha_or_none(supervisor)
    ):
        _fail("successful receipt remote/arm evidence is invalid")


def _validate_machine_result(
    value: Mapping[str, Any],
    *,
    schema: str,
    commit: str,
    registration_sha: str,
    registration: Mapping[str, Any],
) -> None:
    expected_keys = _RECEIPT_KEYS if schema == _RECEIPT_SCHEMA else _ADMIN_KEYS
    if (
        set(value) != expected_keys
        or value.get("schema_version") != schema
        or value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or value.get("registration_content_sha256") != registration_sha
        or value.get("authorization") != _AUTHORIZATION
    ):
        _fail("machine result fixed identity/schema is invalid")

    embedded_specs = (
        (
            "preparation_receipt",
            _PREPARATION_KEYS,
            "action-qbc-v8-preparation-receipt-v2",
        ),
        (
            "preparation_verification_receipt",
            _PREPARATION_VERIFICATION_KEYS,
            "action-qbc-v8-preparation-verification-receipt-v1",
        ),
        (
            "remote_verification_claim",
            _REMOTE_CLAIM_KEYS,
            "action-qbc-v8-remote-tag-verification-claim-v1",
        ),
        (
            "remote_verifier_claim",
            _REMOTE_VERIFIER_KEYS,
            "action-qbc-v8-remote-tag-verifier-start-claim-v1",
        ),
        (
            "remote_verification_receipt",
            _REMOTE_RECEIPT_KEYS,
            "action-qbc-v8-remote-tag-verification-receipt-v1",
        ),
        (
            "remote_supervisor_receipt",
            _REMOTE_SUPERVISOR_KEYS,
            "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1",
        ),
        ("arm_receipt", _ARM_KEYS, "action-qbc-v8-arm-receipt-v2"),
        (
            "lifecycle_driver_claim",
            _DRIVER_KEYS,
            "action-qbc-v8-lifecycle-driver-claim-v1",
        ),
        ("lifecycle_ledger", _LEDGER_KEYS, "action-qbc-v8-lifecycle-ledger-v1"),
    )
    embedded: dict[str, Mapping[str, Any] | None] = {}
    for name, keys, identity in embedded_specs:
        embedded[name] = _embedded_object(
            value.get(name),
            keys=keys,
            schema=identity,
            commit=commit,
            registration_sha=registration_sha,
            name=name,
        )

    preparation = embedded["preparation_receipt"]
    preparation_verification = embedded["preparation_verification_receipt"]
    remote_claim = embedded["remote_verification_claim"]
    remote_verifier = embedded["remote_verifier_claim"]
    remote_receipt = embedded["remote_verification_receipt"]
    remote_supervisor = embedded["remote_supervisor_receipt"]
    arm = embedded["arm_receipt"]
    driver = embedded["lifecycle_driver_claim"]
    for prefix, object_name in (
        ("preparation_receipt", "preparation_receipt"),
        ("preparation_verification_receipt", "preparation_verification_receipt"),
    ):
        exists = value.get(f"{prefix}_exists")
        read_status = value.get(f"{prefix}_read_status")
        digest = value.get(f"{prefix}_sha256")
        embedded_object = embedded[object_name]
        if not isinstance(exists, bool) or read_status not in {
            "absent", "readable", "unsafe_type", "oversized", "read_error",
            "changed_during_read",
        }:
            _fail("machine result preparation read-state is invalid")
        if (
            (read_status == "absent" and (exists or digest is not None))
            or (read_status == "readable" and (not exists or digest is None))
            or (read_status not in {"absent", "readable"} and (not exists or digest is not None))
        ):
            _fail("machine result preparation read-state nullability is invalid")
        if digest is not None:
            _lower_hex(digest, 64, f"{prefix} SHA-256")
        if embedded_object is not None and (
            read_status != "readable" or digest != _sha256(_canonical(embedded_object))
        ):
            _fail("machine result embedded preparation object differs from raw evidence")
    if preparation is not None and (
        preparation.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or preparation.get("status") not in {"prepared", "failed"}
    ):
        _fail("embedded preparation receipt status is invalid")
    if preparation_verification is not None and (
        preparation is None
        or preparation_verification.get("status") != "verified"
        or preparation_verification.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or preparation_verification.get("preparation_receipt_sha256")
        != _sha256(_canonical(preparation))
    ):
        _fail("embedded preparation-verification dependency/status is invalid")
    if remote_claim is not None and remote_claim.get("open_freeze_tag") != _OPEN_FREEZE_TAG:
        _fail("embedded remote claim tag is invalid")
    if remote_verifier is not None and (
        remote_claim is None
        or remote_verifier.get("claim_sha256") != _sha256(_canonical(remote_claim))
    ):
        _fail("embedded remote verifier dependency is invalid")
    if remote_receipt is not None and (
        remote_claim is None
        or remote_verifier is None
        or remote_receipt.get("claim_sha256") != _sha256(_canonical(remote_claim))
        or remote_receipt.get("verifier_start_claim_sha256")
        != _sha256(_canonical(remote_verifier))
        or remote_receipt.get("open_freeze_tag") != _OPEN_FREEZE_TAG
        or remote_receipt.get("status") not in {"verified", "failed"}
    ):
        _fail("embedded remote receipt dependency/status is invalid")
    if remote_supervisor is not None and (
        remote_claim is None
        or remote_supervisor.get("claim_sha256")
        != _sha256(_canonical(remote_claim))
        or remote_supervisor.get("status") not in {"completed", "failed"}
        or (
            remote_verifier is not None
            and remote_supervisor.get("verifier_start_claim_sha256")
            != _sha256(_canonical(remote_verifier))
        )
        or (
            remote_receipt is not None
            and remote_supervisor.get("remote_receipt_sha256")
            != _sha256(_canonical(remote_receipt))
        )
    ):
        _fail("embedded remote supervisor dependency/status is invalid")

    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")

    def embedded_artifact(item: Mapping[str, Any] | None) -> _Artifact:
        if item is None:
            return _Artifact(False, "absent", None, None, None)
        raw = _canonical(item)
        return _Artifact(True, "readable", raw, _sha256(raw), dict(item))

    preparation_artifact = embedded_artifact(preparation)
    verification_artifact = embedded_artifact(preparation_verification)
    claim_artifact = embedded_artifact(remote_claim)
    verifier_artifact = embedded_artifact(remote_verifier)
    receipt_artifact = embedded_artifact(remote_receipt)
    supervisor_artifact = embedded_artifact(remote_supervisor)
    preparation_semantically_valid = bool(
        preparation is not None
        and _preparation_semantically_valid(
            preparation_artifact,
            commit=commit,
            registration_sha=registration_sha,
            verify_filesystem=False,
            execution=execution,
            registration=registration,
        )
    )
    if preparation is not None and not preparation_semantically_valid:
        _fail("embedded preparation receipt is not deeply valid")
    preparation_ready = bool(
        preparation_semantically_valid
        and preparation is not None
        and preparation.get("status") == "prepared"
    )
    preparation_verification_ready = bool(
        preparation_verification is not None
        and _preparation_verification_valid(
            verification_artifact,
            preparation=preparation_artifact,
            commit=commit,
            registration_sha=registration_sha,
            execution=execution,
        )
    )
    if preparation_verification is not None and not preparation_verification_ready:
        _fail("embedded preparation verification is not deeply valid")
    claim_is_valid = _remote_claim_valid(
        claim_artifact,
        registration=registration,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    verifier_is_valid = _remote_verifier_valid(
        verifier_artifact,
        claim=claim_artifact,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    receipt_is_valid = _remote_receipt_valid(
        receipt_artifact,
        claim=claim_artifact,
        verifier=verifier_artifact,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    supervisor_is_valid = _remote_supervisor_valid(
        supervisor_artifact,
        claim=claim_artifact,
        verifier=verifier_artifact,
        receipt=receipt_artifact,
        remote_receipt_valid=receipt_is_valid,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    if (
        (remote_claim is not None and not claim_is_valid)
        or (remote_verifier is not None and not verifier_is_valid)
        or (remote_receipt is not None and not receipt_is_valid)
        or (remote_supervisor is not None and not supervisor_is_valid)
    ):
        _fail("embedded remote evidence is not deeply valid")
    if arm is not None:
        if arm.get("status") not in {"armed", "failed"}:
            _fail("embedded arm status is invalid")
        arm_dependencies = (
            ("remote_claim_sha256", remote_claim),
            ("remote_verifier_claim_sha256", remote_verifier),
            ("remote_receipt_sha256", remote_receipt),
            ("remote_supervisor_receipt_sha256", remote_supervisor),
        )
        if (
            arm.get("preparation_receipt_exists")
            != value.get("preparation_receipt_exists")
            or arm.get("preparation_receipt_read_status")
            != value.get("preparation_receipt_read_status")
            or arm.get("preparation_receipt_sha256")
            != value.get("preparation_receipt_sha256")
            or arm.get("preparation_verification_receipt_exists")
            != value.get("preparation_verification_receipt_exists")
            or arm.get("preparation_verification_receipt_read_status")
            != value.get("preparation_verification_receipt_read_status")
            or arm.get("preparation_verification_receipt_sha256")
            != value.get("preparation_verification_receipt_sha256")
        ):
            _fail("embedded arm preparation read-state differs from machine evidence")
        for member, dependency in arm_dependencies:
            if dependency is not None and arm.get(member) != _sha256(_canonical(dependency)):
                _fail("embedded arm dependency hash is invalid")
        if arm.get("status") == "armed" and (
            any(dependency is None for _member, dependency in arm_dependencies)
            or preparation is None
            or preparation_verification is None
        ):
            _fail("armed receipt lacks a complete embedded dependency set")
    if driver is not None and (
        remote_claim is None
        or driver.get("remote_claim_sha256") != _sha256(_canonical(remote_claim))
    ):
        _fail("embedded lifecycle-driver dependency is invalid")

    process_a = _validate_result_process(
        value.get("process_a"),
        label="A",
        commit=commit,
        registration_sha=registration_sha,
    )
    process_b = _validate_result_process(
        value.get("process_b"),
        label="B",
        commit=commit,
        registration_sha=registration_sha,
    )
    for label, process, prior in (
        ("A", process_a, None),
        ("B", process_b, process_a.get("validation_receipt")),
    ):
        start = process.get("start_claim")
        validator_claim = process.get("validator_claim")
        validation = process.get("validation_receipt")
        if start is not None and (
            arm is None
            or driver is None
            or start.get("arm_receipt_sha256") != _sha256(_canonical(arm))
            or start.get("lifecycle_driver_claim_sha256")
            != _sha256(_canonical(driver))
            or start.get("prior_validation_receipt_sha256")
            != (_sha256(_canonical(prior)) if prior is not None else None)
        ):
            _fail(f"result process {label} start dependencies are invalid")
        if validator_claim is not None and (
            driver is None
            or start is None
            or validator_claim.get("lifecycle_driver_claim_sha256")
            != _sha256(_canonical(driver))
            or validator_claim.get("start_claim_sha256")
            != process.get("start_claim_sha256")
            or validator_claim.get("payload_sha256")
            != process.get("payload_sha256")
        ):
            _fail(f"result process {label} validator dependencies are invalid")
        if validation is not None and (
            start is None
            or validator_claim is None
            or validation.get("start_claim_sha256")
            != process.get("start_claim_sha256")
            or validation.get("validator_claim_sha256")
            != process.get("validator_claim_sha256")
        ):
            _fail(f"result process {label} validation dependencies are invalid")
    pair = value.get("payloads_byte_identical")
    both_valid = process_a.get("payload_valid") is True and process_b.get(
        "payload_valid"
    ) is True
    expected_pair = (
        process_a.get("payload_sha256") == process_b.get("payload_sha256")
        if both_valid
        else None
    )
    if pair is not expected_pair:
        _fail("machine result payload-pair evidence is inconsistent")

    ledger = embedded["lifecycle_ledger"]
    if ledger is not None:
        _optional_sha(ledger.get("driver_claim_sha256"), "embedded ledger driver SHA-256")
        _optional_sha(ledger.get("arm_receipt_sha256"), "embedded ledger arm SHA-256")
        sequence = ledger.get("sequence")
        if (
            not isinstance(sequence, list)
            or sequence != _SEQUENCE[: len(sequence)]
            or ledger.get("stage") not in {*_UNDERLYING_ORDER, None}
            or ledger.get("driver_claim_sha256")
            != (
                _sha256(_canonical(embedded["lifecycle_driver_claim"]))
                if embedded["lifecycle_driver_claim"] is not None
                else ledger.get("driver_claim_sha256")
            )
            or ledger.get("arm_receipt_sha256")
            != (
                _sha256(_canonical(embedded["arm_receipt"]))
                if embedded["arm_receipt"] is not None
                else ledger.get("arm_receipt_sha256")
            )
        ):
            _fail("machine result embedded ledger dependency is invalid")
        for ledger_name, process in (("process_a", process_a), ("process_b", process_b)):
            ledger_process = ledger.get(ledger_name)
            if not isinstance(ledger_process, Mapping) or set(
                ledger_process
            ) != _LEDGER_PROCESS_KEYS:
                _fail("machine result embedded ledger process is invalid")
            for ledger_key, result_key in (
                ("runner_exit_code", "exit_code"),
                ("validator_exit_code", "validator_exit_code"),
                ("start_claim_sha256", "start_claim_sha256"),
                ("validator_claim_sha256", "validator_claim_sha256"),
                ("validation_receipt_sha256", "validation_receipt_sha256"),
                ("output_sha256", "payload_sha256"),
            ):
                if ledger_process.get(ledger_key) != process.get(result_key):
                    _fail("machine result process/ledger evidence differs")

    if schema == _RECEIPT_SCHEMA:
        _validate_embedded_success_evidence(
            embedded,
            registration=registration,
            commit=commit,
            registration_sha=registration_sha,
        )
        if (
            any(embedded[name] is None for name in embedded)
            or ledger is None
            or ledger.get("sequence") != _SEQUENCE
            or ledger.get("stage") is not None
            or process_a.get("payload_valid") is not True
            or process_b.get("payload_valid") is not True
            or pair is not True
            or value.get("published_payload_path")
            != "artifacts/action_qbc_v8_open_diagnostic.json"
            or value.get("published_payload_sha256")
            != process_a.get("payload_sha256")
        ):
            _fail("successful receipt does not contain complete successful evidence")
    else:
        stage = value.get("stage")
        if stage not in _UNDERLYING_ORDER:
            _fail("administrative terminal stage is invalid")
        if (
            driver is not None
            and not preparation_ready
            and stage != "preparation_receipt_invalid"
        ):
            _fail("administrative terminal does not expose preparation failure precedence")
        if (
            driver is not None
            and preparation_ready
            and not preparation_verification_ready
            and stage
            not in {
                "preparation_receipt_invalid",
                "preparation_verification_invalid",
            }
        ):
            _fail(
                "administrative terminal does not expose preparation-verification precedence"
            )
        if ledger is not None and ledger.get("stage") != stage:
            _fail("administrative terminal and ledger stages differ")


def _validate_final_bundle(
    value: Mapping[str, Any],
    *,
    registration: Mapping[str, Any],
    registration_file_sha256: str,
    commit: str,
) -> None:
    registration_sha = str(registration.get("content_sha256"))
    if set(value) != _BUNDLE_KEYS or value.get("schema_version") != _BUNDLE_SCHEMA:
        _fail("normal finalization bundle key/schema identity is invalid")
    unsigned = dict(value)
    claimed = unsigned.pop("content_sha256", None)
    if (
        value.get("treatment_id") != _TREATMENT_ID
        or value.get("open_freeze_commit_sha") != commit
        or value.get("registration_content_sha256") != registration_sha
        or value.get("authorization") != _AUTHORIZATION
        or _lower_hex(claimed, 64, "bundle content SHA-256")
        != _sha256(_canonical(unsigned))
    ):
        _fail("normal finalization bundle fixed/content identity is invalid")
    file_values = value.get("files")
    if not isinstance(file_values, list) or not file_values:
        _fail("normal finalization bundle file list is empty or invalid")
    decoded = [_decode_bundle_file(item) for item in file_values]
    paths = [path for path, _raw in decoded]
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")) or len(paths) != len(
        set(paths)
    ):
        _fail("normal finalization bundle files are not unique and path-sorted")
    disposition = value.get("disposition")
    stage = value.get("stage")
    underlying = value.get("underlying_stage")
    if disposition == "scientific_result":
        expected_paths = [
            "artifacts/action_qbc_v8_open_diagnostic.json",
            "artifacts/action_qbc_v8_open_diagnostic_receipt.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ]
        if stage is not None or underlying is not None or paths != expected_paths:
            _fail("scientific result bundle disposition/path set is invalid")
    elif disposition == "administrative_terminal":
        if stage == "receipt_finalization_failed":
            if underlying not in {*_UNDERLYING_ORDER, None} or paths != [
                "docs/action_qbc_v8_open_diagnostic_result.md"
            ]:
                _fail("receipt-finalization bundle path/stage is invalid")
        elif stage in _UNDERLYING_ORDER:
            if underlying != stage or paths != [
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                "docs/action_qbc_v8_open_diagnostic_result.md",
            ]:
                _fail("administrative bundle path/stage is invalid")
        else:
            _fail("normal bundle has an unknown administrative stage")
    else:
        _fail("normal bundle disposition is invalid")
    expected_document = _NORMAL_TEMPLATE.format(
        disposition=disposition,
        stage=stage if stage is not None else "null",
        underlying_stage=underlying if underlying is not None else "null",
        open_freeze_commit_sha=commit,
        registration_content_sha256=registration_sha,
    ).encode("ascii")
    files = dict(decoded)
    if files.get("docs/action_qbc_v8_open_diagnostic_result.md") != expected_document:
        _fail("bundle result-document bytes differ from the registered rendering")
    if disposition == "scientific_result":
        payload = files["artifacts/action_qbc_v8_open_diagnostic.json"]
        payload_a = _plain(Path(_PROCESS_A), "reopened process-A payload")
        payload_b = _plain(Path(_PROCESS_B), "reopened process-B payload")
        if (
            len(payload_a) != len(payload_b)
            or _sha256(payload_a) != _sha256(payload_b)
            or payload_a != payload_b
            or payload != payload_a
        ):
            _fail("bundled scientific result lacks complete payload-byte parity")
        if not _validate_payload(
            payload,
            registration,
            commit=commit,
            registration_file_sha256=registration_file_sha256,
        ):
            _fail("bundled scientific payload is invalid")
        receipt = _parse(
            files["artifacts/action_qbc_v8_open_diagnostic_receipt.json"],
            "bundled successful receipt",
        )
        _validate_machine_result(
            receipt,
            schema=_RECEIPT_SCHEMA,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
        if (
            set(receipt) != _RECEIPT_KEYS
            or receipt.get("schema_version") != _RECEIPT_SCHEMA
            or receipt.get("treatment_id") != _TREATMENT_ID
            or receipt.get("open_freeze_commit_sha") != commit
            or receipt.get("open_freeze_tag") != _OPEN_FREEZE_TAG
            or receipt.get("registration_content_sha256") != registration_sha
            or receipt.get("published_payload_path")
            != "artifacts/action_qbc_v8_open_diagnostic.json"
            or receipt.get("published_payload_sha256") != _sha256(payload)
            or receipt.get("payloads_byte_identical") is not True
            or receipt.get("authorization") != _AUTHORIZATION
        ):
            _fail("bundled successful receipt identity is invalid")
    elif stage in _UNDERLYING_ORDER:
        terminal = _parse(
            files["artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json"],
            "bundled administrative terminal",
        )
        _validate_machine_result(
            terminal,
            schema=_ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
        if (
            set(terminal) != _ADMIN_KEYS
            or terminal.get("schema_version") != _ADMIN_SCHEMA
            or terminal.get("treatment_id") != _TREATMENT_ID
            or terminal.get("open_freeze_commit_sha") != commit
            or terminal.get("open_freeze_tag") != _OPEN_FREEZE_TAG
            or terminal.get("registration_content_sha256") != registration_sha
            or terminal.get("stage") != stage
            or terminal.get("authorization") != _AUTHORIZATION
        ):
            _fail("bundled administrative terminal identity is invalid")


def _receipt_failure_bundle(
    registration: Mapping[str, Any],
    *,
    commit: str,
    underlying_stage: str | None,
) -> dict[str, Any]:
    document = _normal_document(
        registration,
        disposition="administrative_terminal",
        stage="receipt_finalization_failed",
        underlying_stage=underlying_stage,
        commit=commit,
    )
    return _bundle(
        registration=registration,
        commit=commit,
        disposition="administrative_terminal",
        stage="receipt_finalization_failed",
        underlying_stage=underlying_stage,
        files=[_file_object("docs/action_qbc_v8_open_diagnostic_result.md", document)],
    )


def _exclusive_bundle(
    path: Path,
    value: Mapping[str, Any],
    *,
    registration: Mapping[str, Any],
    registration_file_sha256: str,
    commit: str,
) -> None:
    expected_mode = _expected_evidence_mode(path, "normal_finalization_bundle")
    _validate_final_bundle(
        value,
        registration=registration,
        registration_file_sha256=registration_file_sha256,
        commit=commit,
    )
    raw = _canonical(value)
    parent = _open_directory_nofollow(path.parent, "finalization bundle parent")
    metadata = os.fstat(parent)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or (os.name == "posix" and metadata.st_uid != os.getuid())
    ):
        os.close(parent)
        _fail("finalization bundle parent is not a mode-0700 plain directory")
    try:
        if path.name in os.listdir(parent):
            _fail("finalization bundle destination already exists")
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            expected_mode,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
        reopened_descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
        try:
            reopened_metadata = os.fstat(reopened_descriptor)
            reopened = _bounded_descriptor_bytes(
                reopened_descriptor, max(len(raw), 1), "finalization bundle"
            )
            if (
                not stat.S_ISREG(reopened_metadata.st_mode)
                or stat.S_IMODE(reopened_metadata.st_mode) != expected_mode
                or reopened_metadata.st_uid != metadata.st_uid
                or reopened_metadata.st_nlink != 1
                or reopened_metadata.st_size != len(raw)
            ):
                _fail("finalization bundle reopened metadata is invalid")
        finally:
            os.close(reopened_descriptor)
        after_parent = os.fstat(parent)
        if (
            metadata.st_dev, metadata.st_ino, metadata.st_uid,
            stat.S_IFMT(metadata.st_mode), stat.S_IMODE(metadata.st_mode),
        ) != (
            after_parent.st_dev, after_parent.st_ino, after_parent.st_uid,
            stat.S_IFMT(after_parent.st_mode), stat.S_IMODE(after_parent.st_mode),
        ):
            _fail("finalization bundle parent changed during publication")
    finally:
        os.close(parent)
    parsed = _parse(reopened, "finalization bundle")
    if reopened != raw or parsed != value:
        _fail("finalization bundle failed durable canonical validation")
    _validate_final_bundle(
        parsed,
        registration=registration,
        registration_file_sha256=registration_file_sha256,
        commit=commit,
    )


def _embedded_base(
    *,
    commit: str,
    registration: Mapping[str, Any],
    preparation: _Artifact,
    preparation_verification: _Artifact,
    remote_claim: _Artifact,
    remote_verifier: _Artifact,
    remote_receipt: _Artifact,
    remote_supervisor: _Artifact,
    arm: _Artifact,
    driver: _Artifact,
    ledger: _Artifact,
    process_a: _Process,
    process_b: _Process,
    preparation_valid: bool = True,
    preparation_verification_valid: bool = True,
    remote_claim_valid: bool = True,
    remote_verifier_valid: bool = True,
    remote_receipt_valid: bool = True,
    remote_supervisor_valid: bool = True,
    arm_valid: bool = True,
    driver_valid: bool = True,
    ledger_valid: bool = True,
) -> dict[str, Any]:
    def canonical_value(artifact: _Artifact, _valid: bool) -> dict[str, Any] | None:
        return artifact.value if _valid else None

    return {
        "schema_version": _RECEIPT_SCHEMA,
        "treatment_id": _TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": _OPEN_FREEZE_TAG,
        "registration_content_sha256": registration["content_sha256"],
        "preparation_receipt": canonical_value(preparation, preparation_valid),
        "preparation_receipt_exists": preparation.exists,
        "preparation_receipt_read_status": preparation.read_status,
        "preparation_receipt_sha256": preparation.sha256,
        "preparation_verification_receipt": canonical_value(
            preparation_verification, preparation_verification_valid
        ),
        "preparation_verification_receipt_exists": preparation_verification.exists,
        "preparation_verification_receipt_read_status": preparation_verification.read_status,
        "preparation_verification_receipt_sha256": preparation_verification.sha256,
        "remote_verification_claim": canonical_value(remote_claim, remote_claim_valid),
        "remote_verifier_claim": canonical_value(remote_verifier, remote_verifier_valid),
        "remote_verification_receipt": canonical_value(
            remote_receipt, remote_receipt_valid
        ),
        "remote_supervisor_receipt": canonical_value(
            remote_supervisor, remote_supervisor_valid
        ),
        "arm_receipt": canonical_value(arm, arm_valid),
        "lifecycle_driver_claim": canonical_value(driver, driver_valid),
        "lifecycle_ledger": canonical_value(ledger, ledger_valid),
        "process_a": process_a.record,
        "process_b": process_b.record,
        "payloads_byte_identical": (
            process_a.raw == process_b.raw
            if process_a.raw is not None and process_b.raw is not None
            else None
        ),
    }


def _finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path.cwd().resolve(strict=True)
    commit, registration, registration_raw = _repository_and_registration(root)
    _require_argv(args, registration)
    registration_sha = str(registration["content_sha256"])
    execution = registration.get("execution_contract")
    if not isinstance(execution, Mapping):
        _fail("registration execution contract is invalid")
    authority_valid = _authority_raw_audit(root, commit, registration_raw)

    preparation = _artifact(
        _PREPARATION,
        role="preparation_receipt",
        name="preparation receipt",
        keys=_PREPARATION_KEYS,
        schema="action-qbc-v8-preparation-receipt-v2",
    )
    preparation_verification = _artifact(
        _PREPARATION_VERIFICATION,
        role="preparation_verification_receipt",
        name="preparation verification receipt",
        keys=_PREPARATION_VERIFICATION_KEYS,
        schema="action-qbc-v8-preparation-verification-receipt-v1",
    )
    remote_claim = _artifact(
        _REMOTE_CLAIM,
        role="remote_claim",
        name="remote claim",
        keys=_REMOTE_CLAIM_KEYS,
        schema="action-qbc-v8-remote-tag-verification-claim-v1",
    )
    remote_verifier = _artifact(
        _REMOTE_VERIFIER_CLAIM,
        role="remote_verifier_claim",
        name="remote verifier claim",
        keys=_REMOTE_VERIFIER_KEYS,
        schema="action-qbc-v8-remote-tag-verifier-start-claim-v1",
    )
    remote_receipt = _artifact(
        _REMOTE_RECEIPT,
        role="remote_receipt",
        name="remote receipt",
        keys=_REMOTE_RECEIPT_KEYS,
        schema="action-qbc-v8-remote-tag-verification-receipt-v1",
    )
    remote_supervisor = _artifact(
        _REMOTE_SUPERVISOR,
        role="remote_supervisor_receipt",
        name="remote supervisor receipt",
        keys=_REMOTE_SUPERVISOR_KEYS,
        schema="action-qbc-v8-remote-tag-verification-supervisor-receipt-v1",
    )
    arm = _artifact(
        _ARM,
        role="arm_receipt",
        name="arm receipt",
        keys=_ARM_KEYS,
        schema="action-qbc-v8-arm-receipt-v2",
    )
    driver = _artifact(
        _DRIVER,
        role="lifecycle_driver_claim",
        name="driver claim",
        keys=_DRIVER_KEYS,
        schema="action-qbc-v8-lifecycle-driver-claim-v1",
    )
    ledger = _artifact(
        _LEDGER,
        role="lifecycle_ledger",
        name="lifecycle ledger",
        keys=_LEDGER_KEYS,
        schema="action-qbc-v8-lifecycle-ledger-v1",
    )

    preparation_semantically_valid = _preparation_semantically_valid(
        preparation,
        commit=commit,
        registration_sha=registration_sha,
        verify_filesystem=False,
        execution=execution,
        registration=registration,
    )
    preparation_valid = _preparation_valid(
        preparation,
        commit=commit,
        registration_sha=registration_sha,
        execution=execution,
        registration=registration,
    )
    preparation_verification_valid = bool(
        preparation_semantically_valid
        and _preparation_verification_valid(
            preparation_verification,
            preparation=preparation,
            commit=commit,
            registration_sha=registration_sha,
            execution=execution,
        )
    )
    claim_valid = _remote_claim_valid(
        remote_claim,
        registration=registration,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    verifier_valid = _remote_verifier_valid(
        remote_verifier,
        claim=remote_claim,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    remote_valid = _remote_receipt_valid(
        remote_receipt,
        claim=remote_claim,
        verifier=remote_verifier,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    supervisor_valid = _remote_supervisor_valid(
        remote_supervisor,
        claim=remote_claim,
        verifier=remote_verifier,
        receipt=remote_receipt,
        remote_receipt_valid=remote_valid,
        execution=execution,
        commit=commit,
        registration_sha=registration_sha,
    )
    remote_failed = bool(
        claim_valid
        and supervisor_valid
        and (
            remote_supervisor.value.get("status") == "failed"
            or (remote_valid and remote_receipt.value.get("status") == "failed")
        )
    )
    remote_success = bool(
        claim_valid
        and verifier_valid
        and remote_valid
        and supervisor_valid
        and remote_receipt.value.get("status") == "verified"
        and remote_supervisor.value.get("status") == "completed"
    )
    expected_arm_status = (
        "armed"
        if preparation_valid and preparation_verification_valid and remote_success
        else "failed"
    )
    arm_canonical = bool(
        _matching(arm, commit=commit, registration_sha=registration_sha)
        and arm.value is not None
        and arm.value.get("preparation_receipt_exists") == preparation.exists
        and arm.value.get("preparation_receipt_read_status") == preparation.read_status
        and arm.value.get("preparation_receipt_sha256") == _sha_or_none(preparation)
        and arm.value.get("preparation_verification_receipt_exists")
        == preparation_verification.exists
        and arm.value.get("preparation_verification_receipt_read_status")
        == preparation_verification.read_status
        and arm.value.get("preparation_verification_receipt_sha256")
        == _sha_or_none(preparation_verification)
        and arm.value.get("remote_claim_sha256") == _sha_or_none(remote_claim)
        and arm.value.get("remote_verifier_claim_sha256") == _sha_or_none(remote_verifier)
        and arm.value.get("remote_receipt_sha256") == _sha_or_none(remote_receipt)
        and arm.value.get("remote_supervisor_receipt_sha256")
        == _sha_or_none(remote_supervisor)
        and arm.value.get("status") == expected_arm_status
    )
    driver_valid = bool(
        _matching(driver, commit=commit, registration_sha=registration_sha)
        and driver.value is not None
        and driver.value.get("remote_claim_sha256") == _sha_or_none(remote_claim)
        and driver.value.get("driver_argv_sha256")
        == _sha256(_canonical(execution.get("lifecycle_driver_argv")))
    )
    ledger_valid = bool(
        _matching(ledger, commit=commit, registration_sha=registration_sha)
        and ledger.value is not None
        and driver_valid
        and ledger.value.get("driver_claim_sha256") == _sha_or_none(driver)
        and ledger.value.get("arm_receipt_sha256") == _sha_or_none(arm)
        and isinstance(ledger.value.get("sequence"), list)
        and ledger.value.get("sequence")
        == _SEQUENCE[: len(ledger.value.get("sequence", []))]
        and ledger.value.get("stage") in {*_UNDERLYING_ORDER, None}
    )
    ledger_a = ledger.value.get("process_a") if ledger_valid and ledger.value else None
    ledger_b = ledger.value.get("process_b") if ledger_valid and ledger.value else None
    sequence = ledger.value.get("sequence") if ledger_valid and ledger.value else []
    if not isinstance(sequence, list):
        ledger_valid = False
        sequence = []
    arm_exit = ledger.value.get("arm_exit_code") if ledger_valid and ledger.value else None
    arm_returned = "arm_returned" in sequence
    if arm_returned != (
        isinstance(arm_exit, int) and not isinstance(arm_exit, bool)
    ):
        ledger_valid = False
    if not _ledger_process_valid(
        ledger_a,
        label="A",
        execution=execution,
        sequence=sequence,
    ):
        ledger_valid = False
        ledger_a = None
    if not _ledger_process_valid(
        ledger_b,
        label="B",
        execution=execution,
        sequence=sequence,
    ):
        ledger_valid = False
        ledger_b = None

    arm_exit_matches = bool(
        arm_returned
        and arm_canonical
        and arm.value is not None
        and (
            (arm.value.get("status") == "armed" and arm_exit == 0)
            or (arm.value.get("status") == "failed" and arm_exit == 1)
        )
    )
    arm_dependency_raw = (
        arm.raw
        if arm_canonical and arm.value is not None and arm.value.get("status") == "armed"
        else None
    )
    driver_dependency_raw = driver.raw if driver_valid else None
    ready_for_a = bool(
        preparation_valid
        and preparation_verification_valid
        and remote_success
        and arm_canonical
        and arm_exit_matches
        and authority_valid
        and driver_valid
    )

    process_a = _process(
        "A",
        output=_PROCESS_A,
        start_path=_PROCESS_A_START,
        validator_path=_PROCESS_A_VALIDATOR,
        validation_path=_PROCESS_A_VALIDATION,
        ledger_record=ledger_a,
        registration=registration,
        commit=commit,
        arm_raw=arm_dependency_raw,
        driver_raw=driver_dependency_raw,
        prior_validation_raw=None,
        registration_file_sha256=_sha256(registration_raw),
    )
    a_validation = process_a.record.get("validation_receipt")
    prior_validation_raw = (
        _canonical(a_validation)
        if process_a.record.get("payload_valid") is True
        and isinstance(a_validation, Mapping)
        else None
    )
    process_b = _process(
        "B",
        output=_PROCESS_B,
        start_path=_PROCESS_B_START,
        validator_path=_PROCESS_B_VALIDATOR,
        validation_path=_PROCESS_B_VALIDATION,
        ledger_record=ledger_b,
        registration=registration,
        commit=commit,
        arm_raw=arm_dependency_raw,
        driver_raw=driver_dependency_raw,
        prior_validation_raw=prior_validation_raw,
        registration_file_sha256=_sha256(registration_raw),
    )

    if ledger_valid:
        if ledger_a is None or ledger_b is None:
            ledger_valid = False
        else:
            a_runner_started = ledger_a.get("runner_argv_sha256") is not None
            a_validator_started = ledger_a.get("validator_argv_sha256") is not None
            b_runner_started = ledger_b.get("runner_argv_sha256") is not None
            b_validator_started = ledger_b.get("validator_argv_sha256") is not None
            ledger_valid = bool(
                _ledger_artifacts_match(process_a, ledger_a)
                and _ledger_artifacts_match(process_b, ledger_b)
                and (not a_runner_started or ready_for_a)
                and (
                    not a_validator_started
                    or process_a.record.get("payload_sha256") is not None
                )
                and (
                    not b_runner_started
                    or (
                        "process_a_validator_returned" in sequence
                        and process_a.record.get("validator_exit_code") == 0
                        and process_a.record.get("payload_valid") is True
                    )
                )
                and (
                    not b_validator_started
                    or process_b.record.get("payload_sha256") is not None
                )
            )

    candidates: list[str] = []
    if not preparation_valid:
        candidates.append("preparation_receipt_invalid")
    elif not preparation_verification_valid:
        candidates.append("preparation_verification_invalid")
    if remote_failed:
        candidates.append("remote_verification_failed")
    elif not remote_success:
        candidates.append("remote_receipt_invalid")
    if not arm_canonical or (arm_returned and not arm_exit_matches):
        candidates.append("arm_receipt_invalid")
    if not authority_valid:
        candidates.append("authority_identity_invalid")
    if not ledger_valid:
        candidates.append("lifecycle_ledger_invalid")
    else:
        reached_stage = _reached_lifecycle_stage(
            sequence=sequence,
            arm_exit=arm_exit,
            ready_for_a=ready_for_a,
            process_a=process_a,
            process_b=process_b,
        )
        if reached_stage is not None:
            candidates.append(reached_stage)
    underlying = _first(candidates)
    if ledger_valid and ledger.value.get("stage") != underlying:
        candidates.append("lifecycle_ledger_invalid")
        underlying = _first(candidates)

    embedded = _embedded_base(
        commit=commit,
        registration=registration,
        preparation=preparation,
        preparation_verification=preparation_verification,
        remote_claim=remote_claim,
        remote_verifier=remote_verifier,
        remote_receipt=remote_receipt,
        remote_supervisor=remote_supervisor,
        arm=arm,
        driver=driver,
        ledger=ledger,
        process_a=process_a,
        process_b=process_b,
        preparation_valid=preparation_semantically_valid,
        preparation_verification_valid=preparation_verification_valid,
        remote_claim_valid=claim_valid,
        remote_verifier_valid=verifier_valid,
        remote_receipt_valid=remote_valid,
        remote_supervisor_valid=supervisor_valid,
        arm_valid=arm_canonical,
        driver_valid=driver_valid,
        ledger_valid=ledger_valid,
    )
    if underlying is None:
        if process_a.raw is None or process_b.raw is None or process_a.raw != process_b.raw:
            _fail("scientific result lacks a valid byte-identical pair")
        receipt = dict(embedded)
        receipt.update(
            {
                "published_payload_path": "artifacts/action_qbc_v8_open_diagnostic.json",
                "published_payload_sha256": _sha256(process_a.raw),
                "authorization": _AUTHORIZATION,
            }
        )
        try:
            if set(receipt) != _RECEIPT_KEYS:
                raise _FinalizationError("successful receipt key set is invalid")
            _validate_machine_result(
                receipt,
                schema=_RECEIPT_SCHEMA,
                commit=commit,
                registration_sha=registration_sha,
                registration=registration,
            )
            receipt_raw = _canonical(receipt)
            if _parse(receipt_raw, "successful receipt") != receipt:
                raise _FinalizationError("successful receipt is not canonically stable")
        except Exception:
            return _receipt_failure_bundle(
                registration,
                commit=commit,
                underlying_stage=None,
            )
        document = _normal_document(
            registration,
            disposition="scientific_result",
            stage=None,
            underlying_stage=None,
            commit=commit,
        )
        return _bundle(
            registration=registration,
            commit=commit,
            disposition="scientific_result",
            stage=None,
            underlying_stage=None,
            files=[
                _file_object("artifacts/action_qbc_v8_open_diagnostic.json", process_a.raw),
                _file_object(
                    "artifacts/action_qbc_v8_open_diagnostic_receipt.json", receipt_raw
                ),
                _file_object("docs/action_qbc_v8_open_diagnostic_result.md", document),
            ],
        )

    if not process_a.machine_recordable or not process_b.machine_recordable:
        return _receipt_failure_bundle(
            registration,
            commit=commit,
            underlying_stage=underlying,
        )

    terminal = dict(embedded)
    terminal["schema_version"] = _ADMIN_SCHEMA
    terminal["stage"] = underlying
    terminal["authorization"] = _AUTHORIZATION
    try:
        if set(terminal) != _ADMIN_KEYS:
            raise _FinalizationError("administrative terminal key set is invalid")
        _validate_machine_result(
            terminal,
            schema=_ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration_sha,
            registration=registration,
        )
        terminal_raw = _canonical(terminal)
        if _parse(terminal_raw, "administrative terminal") != terminal:
            raise _FinalizationError("administrative terminal is not canonically stable")
    except Exception:
        return _receipt_failure_bundle(
            registration,
            commit=commit,
            underlying_stage=underlying,
        )
    document = _normal_document(
        registration,
        disposition="administrative_terminal",
        stage=underlying,
        underlying_stage=underlying,
        commit=commit,
    )
    return _bundle(
        registration=registration,
        commit=commit,
        disposition="administrative_terminal",
        stage=underlying,
        underlying_stage=underlying,
        files=[
            _file_object(
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                terminal_raw,
            ),
            _file_object("docs/action_qbc_v8_open_diagnostic_result.md", document),
        ],
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if argv is not None:
            _fail("programmatic argv is not permitted for the production finalizer")
        bundle = _finalize(args)
        commit, registration, registration_raw = _repository_and_registration(
            Path.cwd().resolve(strict=True)
        )
        _exclusive_bundle(
            Path(_BUNDLE),
            bundle,
            registration=registration,
            registration_file_sha256=_sha256(registration_raw),
            commit=commit,
        )
        return 0
    except Exception as exc:
        print(f"action-QBC v8 finalizer failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
