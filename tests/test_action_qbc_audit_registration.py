from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import scripts.build_action_qbc_audit_registration as registration
from arc3_voi.controller import Variant
from arc3_voi.planner import PlanningSnapshot
from arc3_voi.types import Action, ActionKind, GameState, Prediction

ROOT = Path(__file__).resolve().parents[1]
HEX40 = "1" * 40
TEST_REGISTRATION_RAW = b"{}"
HEX64 = hashlib.sha256(TEST_REGISTRATION_RAW).hexdigest()
HEX64_B = "3" * 64


@pytest.fixture(autouse=True)
def _inject_linux_posix_admin_platform_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic lifecycle tests explicitly supply the production platform fact."""

    monkeypatch.setattr(
        registration,
        "_linux_posix_admin_platform_fact",
        lambda: True,
    )


def _permit_context() -> dict[str, str]:
    return {
        "clean_status_porcelain_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "code_commit": HEX40,
        "index_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "registration_content_sha256": "4" * 64,
        "registration_sha256": HEX64,
        "source_manifest_sha256": HEX64_B,
        "working_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
    }


def _test_output_path(directory: Path, label: str) -> Path:
    return Path(registration._registered_scientific_output_paths(directory)[label])


def _prepare_test_output_directories(directory: Path) -> dict[str, str]:
    directory.parent.chmod(0o700)
    output_paths = registration._registered_scientific_output_paths(directory)
    for value in output_paths.values():
        output_path = Path(value)
        output_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        output_path.parent.parent.chmod(0o700)
        output_path.parent.chmod(0o700)
    return output_paths


def test_exclusive_write_failure_never_publishes_partial_bytes_and_retry_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "published.json"
    raw = b'{"complete":true}'
    original_write = os.write
    write_calls = 0

    def fail_after_partial_write(descriptor: int, value: bytes) -> int:
        nonlocal write_calls
        write_calls += 1
        if write_calls == 1:
            partial = max(1, len(value) // 2)
            return original_write(descriptor, value[:partial])
        raise OSError("injected publication write failure")

    monkeypatch.setattr(os, "write", fail_after_partial_write)
    with pytest.raises(OSError, match="injected publication write failure"):
        registration._exclusive_write(destination, raw)

    assert not os.path.lexists(destination)
    assert not tuple(tmp_path.glob(f".{destination.name}.*.tmp"))

    monkeypatch.setattr(os, "write", original_write)
    registration._exclusive_write(destination, raw)
    assert destination.read_bytes() == raw

    with pytest.raises(FileExistsError):
        registration._exclusive_write(destination, b"replacement")
    assert destination.read_bytes() == raw
    assert not tuple(tmp_path.glob(f".{destination.name}.*.tmp"))


def test_exclusive_write_fsyncs_temporary_before_atomic_no_replace_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "published.json"
    raw = b'{"complete":true}'
    events: list[tuple[str, object]] = []
    original_fsync = os.fsync
    original_link = os.link

    def record_file_fsync(descriptor: int) -> None:
        events.append(("file_fsync", descriptor))
        original_fsync(descriptor)

    def record_link(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        events.append(
            (
                "link",
                (Path(os.fsdecode(source)), Path(os.fsdecode(target)), follow_symlinks),
            )
        )
        original_link(source, target, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "fsync", record_file_fsync)
    monkeypatch.setattr(os, "link", record_link)
    monkeypatch.setattr(
        registration,
        "_fsync_directory",
        lambda directory: events.append(("directory_fsync", directory)),
    )

    registration._exclusive_write(destination, raw)

    names = [name for name, _value in events]
    assert names == ["file_fsync", "link", "directory_fsync", "directory_fsync"]
    source, target, follow_symlinks = cast(
        tuple[Path, Path, bool],
        events[1][1],
    )
    assert source.parent == destination.parent
    assert source.name.startswith(f".{destination.name}.")
    assert source.name.endswith(".tmp")
    assert target == destination
    assert follow_symlinks is False
    assert destination.read_bytes() == raw
    assert not source.exists()


def _publish_test_permits(
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    primary_root: Path | None = None,
    replica_root: Path | None = None,
    permit_context: dict[str, str] | None = None,
    registration_value: dict[str, object] | None = None,
    registration_raw: bytes = TEST_REGISTRATION_RAW,
) -> dict[str, Path]:
    context = permit_context if permit_context is not None else _permit_context()
    supplied_registration = registration_value if registration_value is not None else {}
    primary = (primary_root or directory.parent / "primary-worktree").resolve()
    replica = (replica_root or directory.parent / "replica-worktree").resolve()
    primary.mkdir(parents=True, exist_ok=True)
    replica.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(registration, "CANONICAL_EXTERNAL_PERMIT_DIRECTORY", directory.resolve())
    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        lambda _root, **_kwargs: context,
    )
    monkeypatch.setattr(
        registration,
        "load_validated_registration",
        lambda _root: (supplied_registration, registration_raw),
    )
    monkeypatch.setattr(
        registration,
        "_validate_registered_scientific_payload",
        lambda raw, **_kwargs: registration._strict_json_object(raw),
    )
    scientific_output_paths = _prepare_test_output_directories(directory)
    directory.mkdir()
    worktree_roots = {"primary": str(primary), "replica": str(replica)}
    issuance_id = registration._issuance_id(
        context=context,
        scientific_output_paths=scientific_output_paths,
        worktree_roots=worktree_roots,
    )
    hashes: dict[str, str] = {}
    for ordinal, label in enumerate(registration.REGISTERED_START_LABELS, start=1):
        record = registration._permit_record(
            label=label,
            ordinal=ordinal,
            context=context,
            issuance_id=issuance_id,
            scientific_output_paths=scientific_output_paths,
            worktree_roots=worktree_roots,
        )
        raw = registration.canonical_json_bytes(record)
        digest = hashlib.sha256(raw).hexdigest()
        registration._exclusive_write(directory / f"{label}.permit.json", raw)
        registration._exclusive_write(
            directory / f"{label}.available",
            registration.canonical_json_bytes(
                {
                    "issuance_id": issuance_id,
                    "permit_record_sha256": digest,
                    "run_label": label,
                    "state": "available",
                }
            ),
        )
        hashes[label] = digest
    registration._exclusive_write(
        directory / "audit_runs.exposed.json",
        registration.canonical_json_bytes(
            {
                "canonical_external_permit_directory": str(directory.resolve()),
                "issuance_id": issuance_id,
                "permit_record_sha256": hashes,
                "registered_start_labels": list(registration.REGISTERED_START_LABELS),
                "registration_sha256": context["registration_sha256"],
                "schema_version": registration.EXPOSURE_SCHEMA_VERSION,
                "scientific_output_paths": scientific_output_paths,
                "state": "durably_exposed",
                "promotion_staging_temporary_policy": (
                    registration.PROMOTION_STAGING_TEMPORARY_POLICY
                ),
                "trusted_admin_integrity_boundary": (registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY),
                "trusted_admin_no_delete_or_rollback_boundary": True,
                "worktree_roots": worktree_roots,
            }
        ),
    )

    def consume_test_launcher_proof(
        _capability: object,
        _launch_attestation: object,
        *,
        repository_root: str | Path,
        exact_command: tuple[str, ...] | list[str],
        exit_status: int,
        payload_sha256: str | None,
    ) -> dict[str, object]:
        del exit_status, payload_sha256
        command = tuple(exact_command)
        record_path = Path(command[command.index("--permit-record") + 1]).resolve()
        output_path = Path(command[command.index("--output") + 1]).resolve()
        label = record_path.name.removesuffix(".permit.json")
        repository = Path(repository_root).resolve()
        consumed = {
            "code_commit": context["code_commit"],
            "clean_status_porcelain_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
            "consumed": True,
            "consumed_marker_path": str(directory / f"{label}.consumed"),
            "index_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
            "issuance_id": issuance_id,
            "lockbox_read_claim_marker_path": str(directory / f"{label}.lockbox-read-claimed"),
            "permit_directory": str(directory),
            "permit_record_sha256": hashes[label],
            "registration_content_sha256": context["registration_content_sha256"],
            "registration_sha256": context["registration_sha256"],
            "repository_root": str(repository),
            "run_label": label,
            "scientific_output_path": scientific_output_paths[label],
            "scientific_output_paths": scientific_output_paths,
            "scientific_exposure_marker_path": str(
                directory / f"{label}.scientific-exposure-started"
            ),
            "source_manifest_sha256": context["source_manifest_sha256"],
            "worktree_roots": worktree_roots,
            "working_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        }
        identity = {
            "code_commit": context["code_commit"],
            "command_sha256": registration.canonical_sha256(list(command)),
            "consumed_permit_sha256": registration.canonical_sha256(consumed),
            "issuance_id": issuance_id,
            "launcher_distribution_versions": dict(
                registration.LAUNCHER_DISTRIBUTION_VERSIONS
            ),
            "launcher_environment_sha256": hashlib.sha256(
                b"synthetic pinned Linux uv/Python environment"
            ).hexdigest(),
            "launcher_uv_version": registration.LAUNCHER_UV_VERSION,
            "output_path_sha256": hashlib.sha256(output_path.as_posix().encode()).hexdigest(),
            "parent_process_id": 100,
            "parent_start_time_ticks": 10_000,
            "permit_marker_path_sha256": hashlib.sha256(
                (directory / f"{label}.available").as_posix().encode()
            ).hexdigest(),
            "permit_record_path_sha256": hashlib.sha256(
                record_path.as_posix().encode()
            ).hexdigest(),
            "process_id": 101,
            "process_start_time_ticks": 10_001,
            "registration_sha256": context["registration_sha256"],
            "repository_root_sha256": hashlib.sha256(repository.as_posix().encode()).hexdigest(),
            "run_label": label,
            "source_manifest_sha256": context["source_manifest_sha256"],
        }
        return {
            **identity,
            "attestation_sha256": registration.canonical_sha256(identity),
            "capability_issued": True,
            "permit_directory_sha256": hashlib.sha256(directory.as_posix().encode()).hexdigest(),
            "phase": "ledger",
            "read_authorization_consumed": True,
            "valid": True,
        }

    monkeypatch.setattr(
        registration._audit_module(),
        "consume_registered_audit_capability_for_ledger",
        consume_test_launcher_proof,
    )
    return {"primary": primary, "replica": replica}


def _complete_matching_test_pair(
    tmp_path: Path,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Path], Path, bytes, str]:
    roots = _publish_test_permits(directory, monkeypatch)
    repository = roots["primary"]
    (repository / "artifacts").mkdir()
    payload_raw = registration.canonical_json_bytes(
        {"disposition": "scientific-negative-runtime-v5-frozen", "rows": 140}
    )
    payload_sha256 = hashlib.sha256(payload_raw).hexdigest()
    for label in registration.REGISTERED_START_LABELS:
        consumed = registration.consume_audit_start_permit(
            repository_root=roots[label],
            permit_record_path=directory / f"{label}.permit.json",
            available_marker_path=directory / f"{label}.available",
            output_path=_test_output_path(directory, label),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
        registration.claim_registered_lockbox_read_once(
            consumed,
            expected_code_commit=HEX40,
            expected_repository_root=roots[label],
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
        registration.mark_scientific_exposure_started(consumed)
        output_path = _test_output_path(directory, label)
        output_path.write_bytes(payload_raw)
        registration.append_execution_ledger(
            repository_root=roots[label],
            permit_directory=directory,
            run_label=label,
            exact_command=registration.realized_audit_command(directory, label, output_path),
            output_path=output_path,
            exit_status=0,
            payload_sha256=payload_sha256,
            disposition="scientific-negative-runtime-v5-frozen",
            utc=("2026-07-13T00:00:0" f"{registration.REGISTERED_START_LABELS.index(label)}+00:00"),
            hostname="test-host",
        )
    return roots, repository, payload_raw, payload_sha256


def _registered_negative_payload_fixture() -> tuple[dict[str, object], dict[str, str], bytes]:
    audit = registration._audit_module()
    registered = registration.build_audit_registration(ROOT)
    registration_raw = registration.canonical_json_bytes(registered)
    frozen = cast(dict[str, object], registered["frozen_files"])
    context = {
        "clean_status_porcelain_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "code_commit": HEX40,
        "index_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "registration_content_sha256": cast(str, registered["content_sha256"]),
        "registration_sha256": hashlib.sha256(registration_raw).hexdigest(),
        "source_manifest_sha256": cast(str, frozen["manifest_sha256"]),
        "working_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
    }
    inventory = cast(dict[str, object], registered["row_inventory"])
    registered_rows = cast(list[dict[str, object]], inventory["rows"])
    synthetic_scene_identities: list[dict[str, object]] = []
    for family, family_index, _seed_hex, scene_sha256 in registration.SCENE_IDENTITIES:
        visual_transforms: list[dict[str, str]] = []
        for transform_name in registration.VISUAL_TRANSFORMS:
            transform_prefix = f"{family}:{family_index}:{transform_name}"
            visual_transforms.append(
                {
                    "content_sha256": hashlib.sha256(
                        f"{transform_prefix}:content".encode()
                    ).hexdigest(),
                    "grid_sha256": hashlib.sha256(f"{transform_prefix}:grid".encode()).hexdigest(),
                    "name": transform_name,
                }
            )
        synthetic_scene_identities.append(
            {
                "content_sha256": scene_sha256,
                "family": family,
                "family_index": family_index,
                "visual_transforms": visual_transforms,
            }
        )
    complete_negative_records: list[dict[str, object]] = []
    for scene in synthetic_scene_identities:
        complete_negative_records.extend(
            audit._failed_scene_records(
                scene,
                stage="scene_evaluator_failed",
                error=RuntimeError("test fixture"),
            )
        )
    control_failure = audit._deterministic_stage_failure(
        "control_suite_failed",
        RuntimeError("test fixture"),
    )
    complete_negative_records.extend(
        {
            "expected": "registered control evaluates without an exception",
            "failure": control_failure,
            "kind": "control",
            "name": name,
            "observed": control_failure,
            "passes": False,
        }
        for name in audit.PREREGISTERED_CONTROL_ORDER
    )
    records = audit._bind_registered_row_inventory(
        complete_negative_records,
        registered_rows,
    )
    counters = {name: 0 for name in audit.AUDIT_RESOURCE_COUNTER_FIELDS}
    state = audit.AuditCounterState(
        _values=counters,
        _scientific_exposure_started=True,
    )
    acceptance = audit._aggregate_acceptance(records, state, within_deadline=True)
    source_rows = cast(list[dict[str, object]], frozen["files"])
    dependencies = {
        row["path"]: cast(str, row["sha256"])
        for row in source_rows
        if row["path"] in {"pyproject.toml", "uv.lock"}
    }
    lockbox = cast(dict[str, object], registered["lockbox_identity_without_access"])
    payload = {
        "acceptance": acceptance,
        "canonical_command_template": list(registration.AUDIT_COMMAND_TEMPLATE),
        "deterministic_environment": {
            "dependency_file_sha256": dependencies,
            "machine": "x86_64",
            "numpy_version": "2.0.0",
            "platform_release": "test-linux",
            "platform_system": "Linux",
            "python_implementation": "CPython",
            "python_version": "3.12.0",
        },
        "disposition": "mechanism_capability_failed_runtime_v5_frozen",
        "duplicate_execution_is_independent_evidence": False,
        "finalization_failures": [],
        "lockbox_content_sha256": lockbox["content_sha256"],
        "provenance": registration._expected_scientific_provenance(registered, context),
        "records": records,
        "registration_preregistration": registered["preregistration"],
        "registration_sha256": context["registration_sha256"],
        "resource_counter_schema_sha256": audit.AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256,
        "resource_counters": counters,
        "schema_version": audit.ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION,
    }
    return registered, context, registration.canonical_json_bytes(payload)


def _self_asserted_positive_payload(
    registered: dict[str, object],
    negative_raw: bytes,
) -> bytes:
    """Build the exploit that the former aggregate-only validator accepted."""

    audit = registration._audit_module()
    payload = json.loads(negative_raw)
    for row in cast(list[dict[str, object]], payload["records"]):
        kind = cast(str, row["kind"])
        if kind == "base_scene":
            cast(dict[str, object], row["structural_gate"])["passes"] = True
            row["positive_mechanism"] = True
            row["causal_exercise"] = True
        elif kind == "visual_transform":
            cast(dict[str, object], row["structural_gate"])["passes"] = True
            cast(dict[str, object], row["comparison"])["passes"] = True
        else:
            row["passes"] = True
    resource_contract = cast(dict[str, object], registered["resource_contract"])
    counters = dict(cast(dict[str, int], resource_contract["expected_counts"]))
    payload["resource_counters"] = counters
    state = audit.AuditCounterState(
        _values=dict(counters),
        _scientific_exposure_started=True,
    )
    acceptance = audit._aggregate_acceptance(
        cast(list[dict[str, object]], payload["records"]),
        state,
        finalization_complete=True,
        within_deadline=True,
    )
    if acceptance["acceptance_passes"] is not True:
        raise AssertionError("crafted former-validator exploit must aggregate positive")
    payload["acceptance"] = acceptance
    payload["disposition"] = "mechanism_capability_pass_pair_attestation_pending"
    return registration.canonical_json_bytes(payload)


def _synthetic_completed_positive_pipeline(
    *, scaled_predictions: bool, include_controller_rows: bool
) -> dict[str, object]:
    """Build complete primitive evidence whose conclusions must be rederived."""

    audit = registration._audit_module()
    actions = tuple(Action(ActionKind(value)) for value in (1, 2, 3, 4))
    shape = (2, 2) if scaled_predictions else (1, 1)

    def prediction(label: int) -> Prediction:
        return Prediction(
            np.full(shape, label, dtype=np.int16),
            GameState.NOT_FINISHED,
            0,
            {},
        )

    outcomes = tuple(prediction(label) for label in range(8))
    hypothesis_ids = tuple(f"synthetic-h{index}" for index in range(4))
    snapshot = PlanningSnapshot(
        actions=actions,
        hypothesis_ids=hypothesis_ids,
        weights=(0.4, 0.4, 0.1, 0.1),
        predictions={
            actions[0]: (outcomes[0],) * 4,
            actions[1]: (outcomes[1],) * 4,
            actions[2]: (outcomes[2], outcomes[3], outcomes[4], outcomes[4]),
            actions[3]: (outcomes[5], outcomes[6], outcomes[5], outcomes[7]),
        },
        costs={
            actions[0]: (0.0, 0.0, 4.0, 4.0),
            actions[1]: (4.0, 4.0, 0.0, 0.0),
            actions[2]: (3.0, 3.0, 3.0, 3.0),
            actions[3]: (3.5, 3.5, 3.5, 3.5),
        },
    )
    selection = audit.ACTION_QBC_AUDIT_SELECTOR(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )
    worker_memory = {
        "allocation_headroom_bytes": 268_435_456,
        "diagnostic": None,
        "hard_limit_enforced": True,
        "limit_kind": audit.RLIMIT_DATA_HEADROOM_KIND,
    }

    def digest(label: str) -> str:
        return hashlib.sha256(label.encode()).hexdigest()

    controller_rows = (
        [
            audit._expected_controller_trace(selection, Variant.MYOPIC),
            audit._expected_controller_trace(selection, Variant.CROSS_LEVEL),
        ]
        if include_controller_rows
        else []
    )
    pipeline: dict[str, object] = {
        "actions": [audit._action_json(action) for action in actions],
        "candidate_set_sha256": audit.canonical_sha256(
            [audit._action_json(action) for action in actions]
        ),
        "controller_rows": controller_rows,
        "history_sha256": digest("synthetic completed-positive history"),
        "persistent_worker_rows": [
            {**worker_memory, "hypothesis_id": hypothesis_id} for hypothesis_id in hypothesis_ids
        ],
        "planning": {
            "hypothesis_ids": list(hypothesis_ids),
            "invalid_hypothesis_ids": [],
            "rows": [
                {
                    "action": audit._action_json(action),
                    "costs": list(snapshot.costs[action]),
                    "predictions": [
                        audit._prediction_json(item) for item in snapshot.predictions[action]
                    ],
                }
                for action in actions
            ],
            "weights": list(snapshot.weights),
        },
    }
    pipeline.update(
        {
            "program_rows": [
                {
                    "all_actions_ok": True,
                    "assigned_role": role,
                    "ast_nodes": index + 1,
                    "behavior_signature": {"synthetic_role": role},
                    "candidate_index": index,
                    "eligible": True,
                    "goal_value_ok": True,
                    "grounding_worker_memory": dict(worker_memory),
                    "hypothesis_id": hypothesis_ids[index],
                    "palette_conflicts": 0,
                    "sandbox_valid": True,
                    "selected": True,
                }
                for index, role in enumerate(audit.STRUCTURED_PRIOR_ROLES)
            ],
            "selection": audit._selection_json(selection),
            "source_manifest": [
                {
                    "bindings_sha256": digest(f"bindings:{role}"),
                    "evidence_sha256": digest(f"evidence:{role}"),
                    "role": role,
                    "source_sha256": digest(f"source:{role}"),
                }
                for role in audit.STRUCTURED_PRIOR_ROLES
            ],
            "source_roles": list(audit.STRUCTURED_PRIOR_ROLES),
        }
    )
    return pipeline


def _synthetic_completed_order_rows(base: Any) -> list[dict[str, object]]:
    audit = registration._audit_module()
    records: list[dict[str, object]] = []
    for order_index, name in enumerate(audit.ORDER_TRANSFORM_NAMES[:4]):
        if order_index < 2:
            permutation = audit._registered_order_permutation_from_name(name, len(base.actions))
            snapshot = audit._candidate_permutation(base.snapshot, permutation)
        else:
            permutation = audit._registered_order_permutation_from_name(
                name, len(base.snapshot.hypothesis_ids)
            )
            snapshot = audit._permute_hypotheses(base.snapshot, permutation)
        selection = audit.ACTION_QBC_AUDIT_SELECTOR(
            snapshot,
            cross_level_multiplier=23.0,
            probes_used=0,
            probe_cap=3,
        )
        reasons = list(
            audit._selection_invariant_by_action(
                base.selection,
                selection,
                require_order_relative_fields=True,
            )
        )
        if (
            selection.m_decision.action != base.selection.m_decision.action
            or selection.x_decision.action != base.selection.x_decision.action
        ):
            reasons.append("unique positive-row decision changed under candidate order")
        reasons = list(dict.fromkeys(reasons))
        records.append(
            {
                "name": name,
                "order_index": order_index,
                "passes": not reasons,
                "permutation": list(permutation),
                "reasons": reasons,
                "selection": audit._selection_json(selection),
            }
        )
    cells = audit._prediction_cells_from_evidence(base)
    reversed_cells = [
        {**row, "cells": list(reversed(cast(list[object], row["cells"])))} for row in cells
    ]
    records.append(
        {
            "forward_cells_sha256": audit.canonical_sha256(cells),
            "name": audit.ORDER_TRANSFORM_NAMES[4],
            "order_index": 4,
            "passes": True,
            "policy_input_transform_applied": True,
            "reasons": [],
            "reversed_cells_sha256": audit.canonical_sha256(reversed_cells),
            "selection": audit._selection_json(base.selection),
            "transformed_cells": reversed_cells,
        }
    )
    return records


def _completed_positive_payload(
    registered: dict[str, object],
    negative_raw: bytes,
) -> bytes:
    """Construct all 140 completed rows from authoritative primitive evidence."""

    audit = registration._audit_module()
    payload = cast(dict[str, object], json.loads(negative_raw))
    negative_records = cast(list[dict[str, object]], payload["records"])
    base_identities = [row for row in negative_records if row["kind"] == "base_scene"]
    visual_identities = {
        (row["family"], row["family_index"], row["transform_name"]): row
        for row in negative_records
        if row["kind"] == "visual_transform"
    }
    base_pipeline = _synthetic_completed_positive_pipeline(
        scaled_predictions=False,
        include_controller_rows=True,
    )
    scale_pipeline = _synthetic_completed_positive_pipeline(
        scaled_predictions=True,
        include_controller_rows=False,
    )
    base_evidence = audit._validate_pipeline_evidence(
        base_pipeline,
        expect_controller_rows=True,
    )
    transformed_evidence = {
        name: audit._validate_pipeline_evidence(
            scale_pipeline if name == "scale_2_nearest_neighbor" else base_pipeline,
            expect_controller_rows=name != "scale_2_nearest_neighbor",
        )
        for name in audit.SEALED_VISUAL_TRANSFORM_NAMES
    }
    structural = audit._structural_gate_from_evidence(base_evidence)
    mechanism = audit._mechanism_gate(base_evidence.selection, probe_cap_available=True)
    v4 = audit._v4_counterfactual_from_evidence(
        base_evidence.snapshot,
        base_evidence.selection,
        structural_passes=structural["passes"] is True,
        probe_cap_available=True,
    )
    if not (
        structural["passes"] is True
        and mechanism["passes"] is True
        and v4["causal_exercise"] is True
    ):
        raise AssertionError("synthetic primitive evidence must exercise the positive gates")

    unbound: list[dict[str, object]] = []
    for identity in base_identities:
        scene = {
            key: identity[key]
            for key in (
                "family",
                "family_index",
                "scene_content_sha256",
                "scene_id",
            )
        }
        unbound.append(
            {
                **scene,
                "causal_exercise": True,
                "kind": "base_scene",
                "mechanism_gate": mechanism,
                "pipeline": json.loads(json.dumps(base_pipeline)),
                "positive_mechanism": True,
                "structural_gate": structural,
                "v4_counterfactual": v4,
            }
        )
        for transform_index, transform_name in enumerate(audit.SEALED_VISUAL_TRANSFORM_NAMES):
            identity_row = visual_identities[
                (identity["family"], identity["family_index"], transform_name)
            ]
            pipeline = (
                scale_pipeline if transform_name == "scale_2_nearest_neighbor" else base_pipeline
            )
            evidence = transformed_evidence[transform_name]
            unbound.append(
                {
                    **scene,
                    "comparison": audit._compare_visual_evidence(
                        base_evidence,
                        evidence,
                        transform_name=transform_name,
                    ),
                    "grid_sha256": identity_row["grid_sha256"],
                    "kind": "visual_transform",
                    "pipeline": json.loads(json.dumps(pipeline)),
                    "structural_gate": audit._structural_gate_from_evidence(evidence),
                    "transform_content_sha256": identity_row["transform_content_sha256"],
                    "transform_index": transform_index,
                    "transform_name": transform_name,
                }
            )
        for order in _synthetic_completed_order_rows(base_evidence):
            unbound.append({**scene, "kind": "order_transform", **order})

    for control_index, _name in enumerate(audit.PREREGISTERED_CONTROL_ORDER):
        unbound.append(
            {
                "kind": "control",
                **audit._evaluate_preregistered_control(
                    control_index,
                    audit.AuditCounterState(),
                ),
            }
        )

    inventory = cast(dict[str, object], registered["row_inventory"])
    registered_rows = cast(list[dict[str, object]], inventory["rows"])
    records = audit._bind_registered_row_inventory(unbound, registered_rows)
    if len(records) != registration.EXPECTED_AUDIT_ROW_COUNT:
        raise AssertionError("completed fixture must cover the exact registered inventory")
    resource_contract = cast(dict[str, object], registered["resource_contract"])
    counters = dict(cast(dict[str, int], resource_contract["expected_counts"]))
    state = audit.AuditCounterState(
        _values=dict(counters),
        _scientific_exposure_started=True,
    )
    acceptance = audit._aggregate_acceptance(
        records,
        state,
        finalization_complete=True,
        within_deadline=True,
    )
    if acceptance["acceptance_passes"] is not True:
        raise AssertionError("completed fixture must meet the aggregate acceptance gate")
    payload["acceptance"] = acceptance
    payload["disposition"] = "mechanism_capability_pass_pair_attestation_pending"
    payload["finalization_failures"] = []
    payload["records"] = records
    payload["resource_counters"] = counters
    return registration.canonical_json_bytes(payload)


def test_registration_reconstructs_exact_48_file_140_row_contract() -> None:
    result = registration.build_audit_registration(ROOT)
    registration.validate_audit_registration(result, ROOT)

    frozen = cast(dict[str, object], result["frozen_files"])
    files = cast(list[dict[str, object]], frozen["files"])
    assert frozen["count"] == registration.EXPECTED_FROZEN_FILE_COUNT == 48
    assert len(files) == 48
    assert [cast(str, row["path"]) for row in files] == sorted(
        cast(str, row["path"]) for row in files
    )
    assert sum(cast(str, row["path"]).startswith("src/arc3_voi/") for row in files) == 39
    assert {
        cast(str, row["path"]) for row in files if cast(str, row["path"]).startswith("scripts/")
    } == set(registration.REGISTERED_SCRIPT_PATHS)
    assert registration.AUDIT_REGISTRATION_PATH.as_posix() not in {
        cast(str, row["path"]) for row in files
    }
    assert registration.SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix() not in {
        cast(str, row["path"]) for row in files
    }
    assert registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix() not in {
        cast(str, row["path"]) for row in files
    }
    assert "scripts/freeze_action_qbc_lockbox.py" not in {cast(str, row["path"]) for row in files}

    inventory = cast(dict[str, object], result["row_inventory"])
    rows = cast(list[dict[str, object]], inventory["rows"])
    assert inventory["count"] == registration.EXPECTED_AUDIT_ROW_COUNT == 140
    assert [row["row_index"] for row in rows] == list(range(140))
    assert [row["kind"] for row in rows[:12]] == ["base_scene"] * 12
    assert [row["kind"] for row in rows[12:60]] == ["visual_transform"] * 48
    assert [row["kind"] for row in rows[60:120]] == ["order_transform"] * 60
    assert [row["kind"] for row in rows[120:]] == ["control"] * 20

    preregistration = cast(dict[str, object], result["preregistration"])
    assert preregistration == {
        "amendment_git_blob_oid": registration.AMENDMENT_GIT_BLOB_OID,
        "amendment_path": registration.AMENDMENT_PATH.as_posix(),
        "amendment_sha256": registration.AMENDMENT_SHA256,
        "expected_clean_status_porcelain_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "expected_index_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "expected_working_diff_sha256": registration.EMPTY_GIT_OUTPUT_SHA256,
        "freeze_tag": registration.AUDIT_FREEZE_TAG,
        "pre_amendment_head": registration.PRE_AMENDMENT_HEAD,
        "preregistration_commit": registration.PREREGISTRATION_COMMIT,
        "protocol_path": registration.PROTOCOL_PATH.as_posix(),
        "protocol_sha256": registration.PROTOCOL_SHA256,
    }


def test_registration_binds_exact_controls_counters_arms_and_command() -> None:
    result = registration.build_audit_registration(ROOT)
    controls = cast(dict[str, object], result["controls"])
    fixtures = cast(list[dict[str, object]], controls["fixtures"])
    assert controls["fixture_count"] == 20
    assert controls["selector_call_count"] == 19
    assert len({cast(str, row["control_id"]) for row in fixtures}) == 20
    assert all(len(cast(str, row["fixture_sha256"])) == 64 for row in fixtures)

    resources = cast(dict[str, object], result["resource_contract"])
    counts = cast(dict[str, int], resources["expected_counts"])
    assert counts["candidate_builder_calls"] == 48
    assert counts["compiler_calls"] == 60
    assert counts["controller_calls"] == 96
    assert counts["pure_selector_control_calls"] == 19
    assert counts["pure_selector_scene_order_calls"] == 216
    assert counts["pure_selector_calls"] == 235
    assert counts["environment_actions"] == counts["model_calls"] == 0

    config = cast(dict[str, object], result["configuration"])
    arms = cast(dict[str, str], config["arm_config_sha256"])
    assert config["m_arm_sha256"] == arms["M-T"]
    assert config["x_arm_sha256"] == arms["X-T"]
    command = cast(list[str], result["canonical_command_template"])
    assert command == list(registration.AUDIT_COMMAND_TEMPLATE)
    assert command[:4] == ["uv", "run", "--frozen", "--no-sync"]
    assert "primary" not in command and "replica" not in command
    assert "<PERMIT_RECORD>" in command
    assert "<AVAILABLE_MARKER>" in command
    assert "<OUTPUT_PATH>" in command
    execution = cast(dict[str, object], result["execution_contract"])
    assert execution["canonical_external_permit_directory"] == (
        registration.CANONICAL_EXTERNAL_PERMIT_DIRECTORY.as_posix()
    )
    assert execution["distinct_worktree_roots_frozen_at_issuance"] is True
    assert execution["repository_copy_only_after_positive_pair"] is True
    assert execution["promotion_retry_recovers_exact_payload_only"] is True
    assert execution["repository_outputs_absent_at_issuance"] is True
    assert execution["pair_integrity_separate_from_evaluator_disposition"] is True
    assert execution["repository_copy_path"] == (
        registration.SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix()
    )
    assert execution["repository_receipt_path"] == (
        registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()
    )
    assert execution["trusted_admin_integrity_boundary"] == (
        registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY
    )
    assert registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY.startswith(
        "from common-root creation through receipt validation"
    )
    assert "opaque Git ref advertisement, object transport, and checkout" in (
        registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY
    )
    assert "outside that narrow transport exception and the two permit-and-capability-bound" in (
        registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY
    )
    assert execution["trusted_admin_no_delete_or_rollback_boundary"] is True


def test_build_never_routes_a_read_to_registered_lockbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    original = registration._read_repository_file

    def recording_read(root: Path, relative: str) -> bytes:
        assert relative != registration.LOCKBOX_ARTIFACT_RELATIVE_PATH
        observed.append(relative)
        return original(root, relative)

    generator = registration._lockbox_generator_module()

    def forbid_seed_generation(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("registration must not generate any scene")

    monkeypatch.setattr(generator, "_generate_scene_record", forbid_seed_generation)
    monkeypatch.setattr(registration, "_read_repository_file", recording_read)
    result = registration.build_audit_registration(ROOT)
    assert result["status"] == "registered-pre-execution"
    assert registration.LOCKBOX_ARTIFACT_RELATIVE_PATH not in observed
    assert "scripts/freeze_action_qbc_lockbox.py" not in observed


def test_content_identity_and_exact_reconstruction_reject_mutation() -> None:
    result = registration.build_audit_registration(ROOT)
    serialized = registration.canonical_json_bytes(result)
    assert serialized == serialized.strip()
    assert b"\n" not in serialized
    assert (
        registration.registration_payload_sha256(result) == hashlib.sha256(serialized).hexdigest()
    )

    mutated = json.loads(serialized)
    mutated["status"] = "changed"
    with pytest.raises(registration.AuditRegistrationError, match="content identity"):
        registration.validate_audit_registration(mutated, ROOT)

    mutated = json.loads(serialized)
    mutated["content_sha256"] = "0" * 64
    with pytest.raises(registration.AuditRegistrationError, match="content identity"):
        registration.validate_audit_registration(mutated, ROOT)


def test_strict_json_parser_rejects_duplicate_nonfinite_and_noncanonical(
    tmp_path: Path,
) -> None:
    with pytest.raises(registration.AuditRegistrationError, match="duplicate JSON key"):
        registration._strict_json_object(b'{"a":1,"a":2}')
    with pytest.raises(registration.AuditRegistrationError, match="non-finite"):
        registration._strict_json_object(b'{"a":NaN}')

    path = tmp_path / "pretty.json"
    path.write_bytes(b'{"a": 1}\n')
    with pytest.raises(registration.AuditRegistrationError, match="not canonical"):
        registration._load_canonical_object(path)


def test_scientific_payload_validator_binds_schema_provenance_and_registration() -> None:
    registered, context, raw = _registered_negative_payload_fixture()
    validated = registration._validate_registered_scientific_payload(
        raw,
        registration=registered,
        context=context,
    )
    assert validated["disposition"] == "mechanism_capability_failed_runtime_v5_frozen"

    with pytest.raises(registration.AuditRegistrationError, match="top-level schema"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes({"disposition": validated["disposition"]}),
            registration=registered,
            context=context,
        )

    mutated = json.loads(raw)
    mutated["provenance"]["code_commit"] = "9" * 40
    with pytest.raises(registration.AuditRegistrationError, match="provenance"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )

    mutated = json.loads(raw)
    mutated["records"][0]["row_id"] = "forged"
    with pytest.raises(registration.AuditRegistrationError, match="row"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )

    mutated = json.loads(raw)
    mutated["resource_counters"]["environment_actions"] = 1
    with pytest.raises(registration.AuditRegistrationError, match="acceptance"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )

    mutated = json.loads(raw)
    mutated["disposition"] = "mechanism_capability_pass_pair_attestation_pending"
    with pytest.raises(registration.AuditRegistrationError, match="disposition"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )

    mutated = json.loads(raw)
    mutated["finalization_failures"] = [
        {"error_type": None, "stage": "scientific_rows_not_completed"}
    ]
    with pytest.raises(registration.AuditRegistrationError, match="acceptance"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )

    audit = registration._audit_module()
    counter_fields = cast(list[str], list(audit.AUDIT_RESOURCE_COUNTER_FIELDS))
    counters = cast(dict[str, int], mutated["resource_counters"])
    counter_state = audit.AuditCounterState(
        _values={name: counters[name] for name in counter_fields},
        _scientific_exposure_started=True,
    )
    mutated["acceptance"] = audit._aggregate_acceptance(
        cast(list[dict[str, object]], mutated["records"]),
        counter_state,
        finalization_complete=False,
        within_deadline=True,
    )
    validated_emergency_negative = registration._validate_registered_scientific_payload(
        registration.canonical_json_bytes(mutated),
        registration=registered,
        context=context,
    )
    assert (
        validated_emergency_negative["finalization_failures"] == (mutated["finalization_failures"])
    )

    mutated = json.loads(raw)
    mutated["finalization_failures"] = [
        {"error_type": "RuntimeError", "stage": "acceptance_aggregation_failed"}
    ]
    counters = cast(dict[str, int], mutated["resource_counters"])
    counter_state = audit.AuditCounterState(
        _values={name: counters[name] for name in counter_fields},
        _scientific_exposure_started=True,
    )
    mutated["acceptance"] = audit._negative_aggregate_acceptance(
        counter_state,
        within_deadline=True,
    )
    validated_aggregation_failure = registration._validate_registered_scientific_payload(
        registration.canonical_json_bytes(mutated),
        registration=registered,
        context=context,
    )
    assert validated_aggregation_failure["acceptance"] == mutated["acceptance"]

    mutated = json.loads(raw)
    mutated["finalization_failures"] = [{"stage": "missing-error-type"}]
    with pytest.raises(registration.AuditRegistrationError, match="finalization"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(mutated),
            registration=registered,
            context=context,
        )


def test_completed_positive_140_row_payload_passes_authoritative_rederivation() -> None:
    registered, context, negative_raw = _registered_negative_payload_fixture()
    audit = registration._audit_module()
    raw = _completed_positive_payload(registered, negative_raw)

    validated = registration._validate_registered_scientific_payload(
        raw,
        registration=registered,
        context=context,
    )
    acceptance = cast(dict[str, object], validated["acceptance"])
    records = cast(list[dict[str, object]], validated["records"])
    inventory = cast(dict[str, object], registered["row_inventory"])
    registered_rows = cast(list[dict[str, object]], inventory["rows"])

    assert acceptance["acceptance_passes"] is True
    assert validated["disposition"] == ("mechanism_capability_pass_pair_attestation_pending")
    assert len(records) == 140
    assert sum(row["kind"] == "base_scene" for row in records) == 12
    assert sum(row["kind"] == "visual_transform" for row in records) == 48
    assert sum(row["kind"] == "order_transform" for row in records) == 60
    assert sum(row["kind"] == "control" for row in records) == 20
    assert (
        audit.validate_and_rederive_scientific_records(
            records,
            registered_rows,
        )
        == records
    )


def test_scientific_payload_validator_rejects_minimal_and_self_asserted_rows() -> None:
    registered, context, raw = _registered_negative_payload_fixture()
    audit = registration._audit_module()

    def reaggregate(payload: dict[str, object]) -> None:
        records = cast(list[dict[str, object]], payload["records"])
        counters = cast(dict[str, int], payload["resource_counters"])
        state = audit.AuditCounterState(
            _values=dict(counters),
            _scientific_exposure_started=True,
        )
        acceptance = audit._aggregate_acceptance(
            records,
            state,
            finalization_complete=not cast(
                list[dict[str, object]], payload["finalization_failures"]
            ),
            within_deadline=True,
        )
        payload["acceptance"] = acceptance
        payload["disposition"] = (
            "mechanism_capability_pass_pair_attestation_pending"
            if acceptance["acceptance_passes"] is True
            else "mechanism_capability_failed_runtime_v5_frozen"
        )

    minimal = json.loads(raw)
    minimal_records: list[dict[str, object]] = []
    for source in cast(list[dict[str, object]], minimal["records"]):
        kind = cast(str, source["kind"])
        common_keys = {
            "family",
            "family_index",
            "kind",
            "name",
            "registered_row",
            "row_id",
            "row_index",
            "scene_content_sha256",
            "scene_id",
            "transform_name",
        }
        row = {key: value for key, value in source.items() if key in common_keys}
        if kind == "base_scene":
            row.update(
                {
                    "causal_exercise": False,
                    "positive_mechanism": False,
                    "structural_gate": {"passes": False},
                }
            )
        elif kind == "visual_transform":
            row.update(
                {
                    "comparison": {"passes": False},
                    "structural_gate": {"passes": False},
                }
            )
        else:
            row["passes"] = False
        minimal_records.append(row)
    minimal["records"] = minimal_records
    reaggregate(minimal)
    with pytest.raises(registration.AuditRegistrationError, match="evidence"):
        registration._validate_registered_scientific_payload(
            registration.canonical_json_bytes(minimal),
            registration=registered,
            context=context,
        )

    forged_positive_raw = _self_asserted_positive_payload(registered, raw)
    forged_positive = json.loads(forged_positive_raw)
    forged_acceptance = cast(dict[str, object], forged_positive["acceptance"])
    assert forged_acceptance["acceptance_passes"] is True
    with pytest.raises(registration.AuditRegistrationError, match="evidence"):
        registration._validate_registered_scientific_payload(
            forged_positive_raw,
            registration=registered,
            context=context,
        )

    for mutation in (
        "pipeline_status",
        "nested_pass",
        "extra_field",
        "scene_id",
        "failure_error_type",
        "control_expected",
    ):
        tampered = json.loads(raw)
        records = cast(list[dict[str, object]], tampered["records"])
        if mutation == "pipeline_status":
            cast(dict[str, object], records[0]["pipeline"])["status"] = "complete"
        elif mutation == "nested_pass":
            visual = next(row for row in records if row["kind"] == "visual_transform")
            cast(dict[str, object], visual["comparison"])["passes"] = True
        elif mutation == "extra_field":
            records[0]["unregistered_evidence"] = "forged"
        elif mutation == "scene_id":
            records[0]["scene_id"] = "forged/0"
        elif mutation == "failure_error_type":
            structural_gate = cast(dict[str, object], records[0]["structural_gate"])
            cast(dict[str, object], structural_gate["failure"])["error_type"] = "ForgedError"
        else:
            control = next(row for row in records if row["kind"] == "control")
            control["expected"] = "forged control semantics"
        reaggregate(tampered)
        with pytest.raises(registration.AuditRegistrationError, match="evidence"):
            registration._validate_registered_scientific_payload(
                registration.canonical_json_bytes(tampered),
                registration=registered,
                context=context,
            )


def test_non_linux_admin_entrypoints_reject_before_path_or_authorization_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PoisonPath:
        path_accesses = 0

        def __fspath__(self) -> str:
            self.path_accesses += 1
            raise AssertionError("path access must follow the Linux/POSIX guard")

    poison = PoisonPath()
    path_value = cast(Any, poison)
    authorization_calls = 0

    def forbid_authorization(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal authorization_calls
        authorization_calls += 1
        raise AssertionError("authorization must follow the Linux/POSIX guard")

    monkeypatch.setattr(
        registration,
        "_linux_posix_admin_platform_fact",
        lambda: False,
    )
    monkeypatch.setattr(
        registration._audit_module(),
        "consume_registered_audit_capability_for_ledger",
        forbid_authorization,
    )
    calls: tuple[Callable[[], object], ...] = (
        lambda: registration.prepare_external_audit_permits(
            path_value,
            path_value,
            replica_repository_root=path_value,
        ),
        lambda: registration.consume_audit_start_permit(
            repository_root=path_value,
            permit_record_path=path_value,
            available_marker_path=path_value,
            output_path=path_value,
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        ),
        lambda: registration.append_execution_ledger(
            repository_root=path_value,
            permit_directory=path_value,
            run_label="primary",
            exact_command=(),
            output_path=path_value,
            exit_status=1,
            payload_sha256=None,
            disposition="must-not-run",
        ),
        lambda: registration.promote_verified_audit_pair(
            repository_root=path_value,
            permit_directory=path_value,
        ),
        lambda: registration.load_validated_promotion_receipt(
            path_value,
            path_value,
        ),
    )
    for call in calls:
        with pytest.raises(
            registration.AuditRegistrationError,
            match=r"Linux/POSIX.*before path access",
        ):
            call()
    assert poison.path_accesses == 0
    assert authorization_calls == 0
    assert list(tmp_path.iterdir()) == []


def test_prepare_permits_cli_rejects_non_linux_before_path_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve_calls: list[Path] = []
    arguments = [
        "--repository-root",
        str(tmp_path / "repository"),
        "--prepare-permits",
        str(tmp_path / "permits"),
        "--replica-repository-root",
        str(tmp_path / "replica"),
    ]

    def forbid_resolve(path: Path, *_args: object, **_kwargs: object) -> Path:
        resolve_calls.append(path)
        raise AssertionError("CLI path resolution must follow the platform guard")

    monkeypatch.setattr(
        registration,
        "_linux_posix_admin_platform_fact",
        lambda: False,
    )
    monkeypatch.setattr(Path, "resolve", forbid_resolve)
    with pytest.raises(
        registration.AuditRegistrationError,
        match=r"Linux/POSIX.*before path access",
    ):
        registration.main(arguments)
    assert resolve_calls == []
    assert list(tmp_path.iterdir()) == []


def test_prepare_permits_publishes_exact_pair_and_exposure_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    replica_repository = tmp_path / "replica-repository"
    replica_repository.mkdir()
    destination = tmp_path / "permits"
    monkeypatch.setattr(registration, "CANONICAL_EXTERNAL_PERMIT_DIRECTORY", destination.resolve())
    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        lambda _root, **_kwargs: _permit_context(),
    )
    expected_output_paths = _prepare_test_output_directories(destination)

    fsynced: list[Path] = []
    monkeypatch.setattr(
        registration, "_fsync_directory", lambda path: fsynced.append(path.resolve())
    )
    result = registration.prepare_external_audit_permits(
        repository,
        destination,
        replica_repository_root=replica_repository,
    )
    assert result["registration_sha256"] == HEX64
    assert {path.name for path in destination.iterdir()} == {
        "primary.permit.json",
        "primary.available",
        "replica.permit.json",
        "replica.available",
        "audit_runs.exposed.json",
    }
    assert destination.parent.resolve() in fsynced
    exposure = cast(dict[str, object], result["exposure"])
    assert result["issuance_id"] == exposure["issuance_id"]
    assert result["scientific_output_paths"] == expected_output_paths
    assert exposure["trusted_admin_integrity_boundary"] == (
        registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY
    )
    permit = cast(
        dict[str, object],
        json.loads((destination / "primary.permit.json").read_bytes()),
    )
    execution = cast(dict[str, object], permit["execution_contract"])
    assert execution["trusted_admin_integrity_boundary"] == (
        registration.TRUSTED_ADMIN_INTEGRITY_BOUNDARY
    )
    assert execution["trusted_admin_no_delete_or_rollback_boundary"] is True
    with pytest.raises(FileExistsError):
        registration.prepare_external_audit_permits(
            repository,
            destination,
            replica_repository_root=replica_repository,
        )
    with pytest.raises(registration.AuditRegistrationError, match="absolute singleton"):
        registration.prepare_external_audit_permits(
            repository,
            tmp_path / "copied-permits",
            replica_repository_root=replica_repository,
        )
    with pytest.raises(registration.AuditRegistrationError, match="distinct"):
        registration.prepare_external_audit_permits(
            repository,
            destination,
            replica_repository_root=repository,
        )


@pytest.mark.parametrize(
    ("worktree_label", "relative_path"),
    [
        ("primary", registration.SEALED_AUDIT_REPOSITORY_COPY_PATH),
        ("primary", registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH),
        ("replica", registration.SEALED_AUDIT_REPOSITORY_COPY_PATH),
        ("replica", registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH),
    ],
)
def test_prepare_permits_rejects_stale_excluded_repository_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worktree_label: str,
    relative_path: Path,
) -> None:
    roots = {
        "primary": tmp_path / "primary-repository",
        "replica": tmp_path / "replica-repository",
    }
    for root in roots.values():
        root.mkdir()
    stale_path = roots[worktree_label] / relative_path
    stale_path.parent.mkdir()
    stale_path.write_bytes(b"stale excluded output")
    destination = tmp_path / "permits"
    monkeypatch.setattr(
        registration,
        "CANONICAL_EXTERNAL_PERMIT_DIRECTORY",
        destination.resolve(),
    )
    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        lambda _root, **_kwargs: _permit_context(),
    )
    _prepare_test_output_directories(destination)

    with pytest.raises(registration.AuditRegistrationError, match="absent"):
        registration.prepare_external_audit_permits(
            roots["primary"],
            destination,
            replica_repository_root=roots["replica"],
        )
    assert not destination.exists()


def test_prepare_permits_rejects_broken_output_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "primary-repository"
    replica_repository = tmp_path / "replica-repository"
    repository.mkdir()
    replica_repository.mkdir()
    symlink_path = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    symlink_path.parent.mkdir()
    try:
        symlink_path.symlink_to(symlink_path.parent / "missing-target.json")
    except OSError:
        pytest.skip("symbolic-link creation is unavailable on this platform")
    destination = tmp_path / "permits"
    monkeypatch.setattr(
        registration,
        "CANONICAL_EXTERNAL_PERMIT_DIRECTORY",
        destination.resolve(),
    )
    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        lambda _root, **_kwargs: _permit_context(),
    )
    _prepare_test_output_directories(destination)

    with pytest.raises(registration.AuditRegistrationError, match="absent"):
        registration.prepare_external_audit_permits(
            repository,
            destination,
            replica_repository_root=replica_repository,
        )
    assert not destination.exists()


def test_permits_are_one_shot_and_scientific_exposure_is_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    repository = roots["primary"]
    consumed = registration.consume_audit_start_permit(
        repository_root=repository,
        permit_record_path=directory / "primary.permit.json",
        available_marker_path=directory / "primary.available",
        output_path=_test_output_path(directory, "primary"),
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    assert consumed["consumed"] is True
    assert consumed["run_label"] == "primary"
    assert not (directory / "primary.available").exists()
    assert (directory / "primary.consumed").is_file()
    registration.validate_consumed_audit_start_permit(
        consumed,
        expected_code_commit=HEX40,
        expected_repository_root=repository,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    forged = dict(consumed)
    forged["source_manifest_sha256"] = "9" * 64
    with pytest.raises(registration.AuditRegistrationError, match="identity mismatch"):
        registration.validate_consumed_audit_start_permit(
            forged,
            expected_code_commit=HEX40,
            expected_repository_root=repository,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
    with pytest.raises(registration.AuditRegistrationError):
        registration.consume_audit_start_permit(
            repository_root=repository,
            permit_record_path=directory / "primary.permit.json",
            available_marker_path=directory / "primary.available",
            output_path=_test_output_path(directory, "primary"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )

    lockbox_claim = registration.claim_registered_lockbox_read_once(
        consumed,
        expected_code_commit=HEX40,
        expected_repository_root=repository,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    assert lockbox_claim["state"] == "lockbox_read_claimed"
    with pytest.raises(FileExistsError):
        registration.claim_registered_lockbox_read_once(
            consumed,
            expected_code_commit=HEX40,
            expected_repository_root=repository,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )

    exposure = registration.mark_scientific_exposure_started(consumed)
    assert exposure["state"] == "scientific_exposure_started"
    assert (directory / "primary.scientific-exposure-started").is_file()
    with pytest.raises(FileExistsError):
        registration.mark_scientific_exposure_started(consumed)


def test_replica_consumption_requires_complete_durable_primary_ledger_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    primary_repository = roots["primary"]
    replica_repository = roots["replica"]

    def consume_replica() -> dict[str, object]:
        return registration.consume_audit_start_permit(
            repository_root=replica_repository,
            permit_record_path=directory / "replica.permit.json",
            available_marker_path=directory / "replica.available",
            output_path=_test_output_path(directory, "replica"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )

    with pytest.raises(registration.AuditRegistrationError, match="primary ledger"):
        consume_replica()
    assert (directory / "replica.available").is_file()
    assert not (directory / "replica.consumed").exists()

    primary = registration.consume_audit_start_permit(
        repository_root=primary_repository,
        permit_record_path=directory / "primary.permit.json",
        available_marker_path=directory / "primary.available",
        output_path=_test_output_path(directory, "primary"),
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    registration.mark_scientific_exposure_started(primary)
    with pytest.raises(registration.AuditRegistrationError, match="primary ledger"):
        consume_replica()
    assert (directory / "replica.available").is_file()
    primary_output = _test_output_path(directory, "primary")
    registration.append_execution_ledger(
        repository_root=primary_repository,
        permit_directory=directory,
        run_label="primary",
        exact_command=registration.realized_audit_command(directory, "primary", primary_output),
        output_path=primary_output,
        exit_status=1,
        payload_sha256=None,
        disposition="frozen-primary-failure",
        utc="2026-07-13T00:00:00+00:00",
        hostname="test-host",
    )
    with pytest.raises(registration.AuditRegistrationError, match="successful complete"):
        consume_replica()
    assert (directory / "replica.available").is_file()
    assert not (directory / "replica.consumed").exists()


def test_exposure_mapping_must_bind_both_permits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    exposure_path = directory / "audit_runs.exposed.json"
    exposure = json.loads(exposure_path.read_bytes())
    exposure["permit_record_sha256"].pop("replica")
    exposure_path.write_bytes(registration.canonical_json_bytes(exposure))
    with pytest.raises(registration.AuditRegistrationError, match="does not bind"):
        registration.consume_audit_start_permit(
            repository_root=roots["primary"],
            permit_record_path=directory / "primary.permit.json",
            available_marker_path=directory / "primary.available",
            output_path=_test_output_path(directory, "primary"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )


def test_copied_permit_directory_cannot_create_additional_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    copied = tmp_path / "copied-permits"
    copied.mkdir()
    for source in directory.iterdir():
        if source.is_file():
            (copied / source.name).write_bytes(source.read_bytes())
    with pytest.raises(registration.AuditRegistrationError, match="absolute singleton"):
        registration.consume_audit_start_permit(
            repository_root=roots["primary"],
            permit_record_path=copied / "primary.permit.json",
            available_marker_path=copied / "primary.available",
            output_path=_test_output_path(directory, "primary"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
    assert (directory / "primary.available").is_file()
    assert not (directory / "primary.consumed").exists()


def test_consume_rejects_permits_inside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    directory = repository / "permits"
    repository.mkdir()
    _publish_test_permits(
        directory,
        monkeypatch,
        primary_root=repository,
        replica_root=tmp_path / "replica-worktree",
    )
    with pytest.raises(registration.AuditRegistrationError, match="outside"):
        registration.consume_audit_start_permit(
            repository_root=repository,
            permit_record_path=directory / "primary.permit.json",
            available_marker_path=directory / "primary.available",
            output_path=_test_output_path(directory, "primary"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
    assert (directory / "primary.available").is_file()
    assert not (directory / "primary.consumed").exists()


def test_append_consumes_opaque_authorization_before_any_path_or_ledger_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = registration._audit_module()
    calls: list[tuple[object, object]] = []

    def reject_authorization(
        capability: object,
        launch_attestation: object,
        **_kwargs: object,
    ) -> dict[str, object]:
        calls.append((capability, launch_attestation))
        raise RuntimeError("opaque authorization rejected")

    monkeypatch.setattr(
        audit,
        "consume_registered_audit_capability_for_ledger",
        reject_authorization,
    )
    missing = tmp_path / "must-not-be-resolved"
    with pytest.raises(registration.AuditRegistrationError, match="one-shot launcher"):
        registration.append_execution_ledger(
            capability=None,
            launch_attestation=None,
            repository_root=missing,
            permit_directory=missing / "permits",
            run_label="not-registered",
            exact_command=(),
            output_path=missing / registration.SCIENTIFIC_OUTPUT_RELATIVE_PATH,
            exit_status=1,
            payload_sha256=None,
            disposition="must-not-be-inspected",
        )
    assert calls == [(None, None)]
    assert not missing.exists()


def test_execution_ledger_is_append_only_and_rejects_duplicate_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    payload_raw = registration.canonical_json_bytes(
        {"disposition": "complete", "result": "byte-identical"}
    )
    payload_sha256 = hashlib.sha256(payload_raw).hexdigest()
    for label in registration.REGISTERED_START_LABELS:
        consumed = registration.consume_audit_start_permit(
            repository_root=roots[label],
            permit_record_path=directory / f"{label}.permit.json",
            available_marker_path=directory / f"{label}.available",
            output_path=_test_output_path(directory, label),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
        registration.claim_registered_lockbox_read_once(
            consumed,
            expected_code_commit=HEX40,
            expected_repository_root=roots[label],
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
        registration.mark_scientific_exposure_started(consumed)
        output_path = _test_output_path(directory, label)
        output_path.write_bytes(payload_raw)
        registration.append_execution_ledger(
            repository_root=roots[label],
            permit_directory=directory,
            run_label=label,
            exact_command=registration.realized_audit_command(directory, label, output_path),
            output_path=output_path,
            exit_status=0,
            payload_sha256=payload_sha256,
            disposition="complete",
            utc=f"2026-07-13T00:00:0{registration.REGISTERED_START_LABELS.index(label)}+00:00",
            hostname="test-host",
        )
    lines = (directory / "execution_ledger.jsonl").read_text(encoding="ascii").splitlines()
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert [row["run_label"] for row in rows] == ["primary", "replica"]
    assert rows[0]["output_complete"] is True
    assert rows[0]["pair_attestation"] is None
    assert rows[1]["disposition"] == "complete"
    pair = cast(dict[str, object], rows[1]["pair_attestation"])
    assert pair["both_exit_zero"] is True
    assert pair["both_outputs_complete"] is True
    assert pair["payload_sha256_matches"] is True
    assert pair["exact_bytes_equal"] is True
    assert pair["positive_pair_eligible"] is True
    assert pair["positive_pair_eligibility_scope"] == "pair-integrity-only"
    assert pair["disposition"] == registration.PAIR_POSITIVE_DISPOSITION
    assert pair["third_start_allowed"] is False
    assert pair["start_allowance_state"] == "exhausted-permanently"
    with pytest.raises(registration.AuditRegistrationError, match="already contains"):
        output_path = _test_output_path(directory, "primary")
        registration.append_execution_ledger(
            repository_root=roots["primary"],
            permit_directory=directory,
            run_label="primary",
            exact_command=registration.realized_audit_command(directory, "primary", output_path),
            output_path=output_path,
            exit_status=0,
            payload_sha256=payload_sha256,
            disposition="complete",
            utc="2026-07-13T00:01:00+00:00",
            hostname="test-host",
        )


def test_consume_rejects_cross_label_output_path_before_consumed_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    primary_output = _test_output_path(directory, "primary")

    with pytest.raises(registration.AuditRegistrationError, match="frozen issuance"):
        registration.consume_audit_start_permit(
            repository_root=roots["replica"],
            permit_record_path=directory / "replica.permit.json",
            available_marker_path=directory / "replica.available",
            output_path=primary_output,
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )

    assert (directory / "replica.available").is_file()
    assert not (directory / "replica.consumed").exists()


def test_append_rejects_forged_consumed_marker_and_permit_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    consumed = registration.consume_audit_start_permit(
        repository_root=roots["primary"],
        permit_record_path=directory / "primary.permit.json",
        available_marker_path=directory / "primary.available",
        output_path=_test_output_path(directory, "primary"),
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    claim_path = directory / "primary.consumed"
    claim = json.loads(claim_path.read_bytes())
    claim["permit_record_sha256"] = "9" * 64
    claim_path.write_bytes(registration.canonical_json_bytes(claim))
    output = _test_output_path(directory, "primary")
    with pytest.raises(registration.AuditRegistrationError, match="consumed marker"):
        registration.append_execution_ledger(
            repository_root=roots["primary"],
            permit_directory=directory,
            run_label="primary",
            exact_command=registration.realized_audit_command(directory, "primary", output),
            output_path=output,
            exit_status=1,
            payload_sha256=None,
            disposition="infrastructure-failure",
        )
    assert consumed["consumed"] is True
    assert not (directory / "execution_ledger.jsonl").exists()


def test_forged_primary_ledger_blocks_replica_without_restoring_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    registration.consume_audit_start_permit(
        repository_root=roots["primary"],
        permit_record_path=directory / "primary.permit.json",
        available_marker_path=directory / "primary.available",
        output_path=_test_output_path(directory, "primary"),
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    output = _test_output_path(directory, "primary")
    registration.append_execution_ledger(
        repository_root=roots["primary"],
        permit_directory=directory,
        run_label="primary",
        exact_command=registration.realized_audit_command(directory, "primary", output),
        output_path=output,
        exit_status=1,
        payload_sha256=None,
        disposition="infrastructure-failure",
    )
    ledger_path = directory / "execution_ledger.jsonl"
    row = json.loads(ledger_path.read_text(encoding="ascii"))
    row["issuance_id"] = "9" * 64
    ledger_path.write_bytes(registration.canonical_json_bytes(row) + b"\n")
    with pytest.raises(registration.AuditRegistrationError, match="issuance"):
        registration.consume_audit_start_permit(
            repository_root=roots["replica"],
            permit_record_path=directory / "replica.permit.json",
            available_marker_path=directory / "replica.available",
            output_path=_test_output_path(directory, "replica"),
            expected_code_commit=HEX40,
            expected_registration_sha256=HEX64,
            expected_source_manifest_sha256=HEX64_B,
        )
    assert (directory / "replica.available").is_file()
    assert not (directory / "replica.consumed").exists()


@pytest.mark.parametrize("replica_failure", [False, True])
def test_replica_mismatch_or_failure_is_frozen_negative_and_exhausts_starts(
    tmp_path: Path, replica_failure: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    roots = _publish_test_permits(directory, monkeypatch)
    repository = roots["primary"]
    (repository / "artifacts").mkdir()
    primary_raw = registration.canonical_json_bytes(
        {"disposition": "complete", "payload": "primary"}
    )
    primary_output = _test_output_path(directory, "primary")
    primary = registration.consume_audit_start_permit(
        repository_root=repository,
        permit_record_path=directory / "primary.permit.json",
        available_marker_path=directory / "primary.available",
        output_path=primary_output,
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    registration.claim_registered_lockbox_read_once(
        primary,
        expected_code_commit=HEX40,
        expected_repository_root=repository,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    registration.mark_scientific_exposure_started(primary)
    primary_output.write_bytes(primary_raw)
    registration.append_execution_ledger(
        repository_root=repository,
        permit_directory=directory,
        run_label="primary",
        exact_command=registration.realized_audit_command(directory, "primary", primary_output),
        output_path=primary_output,
        exit_status=0,
        payload_sha256=hashlib.sha256(primary_raw).hexdigest(),
        disposition="complete",
        utc="2026-07-13T00:00:00+00:00",
        hostname="test-host",
    )

    replica = registration.consume_audit_start_permit(
        repository_root=roots["replica"],
        permit_record_path=directory / "replica.permit.json",
        available_marker_path=directory / "replica.available",
        output_path=_test_output_path(directory, "replica"),
        expected_code_commit=HEX40,
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    registration.claim_registered_lockbox_read_once(
        replica,
        expected_code_commit=HEX40,
        expected_repository_root=roots["replica"],
        expected_registration_sha256=HEX64,
        expected_source_manifest_sha256=HEX64_B,
    )
    registration.mark_scientific_exposure_started(replica)
    replica_output = _test_output_path(directory, "replica")
    replica_payload_sha256: str | None = None
    replica_exit_status = 1
    if not replica_failure:
        replica_raw = registration.canonical_json_bytes(
            {"disposition": "complete", "payload": "replica"}
        )
        replica_output.write_bytes(replica_raw)
        replica_payload_sha256 = hashlib.sha256(replica_raw).hexdigest()
        replica_exit_status = 0
    replica_row = registration.append_execution_ledger(
        repository_root=roots["replica"],
        permit_directory=directory,
        run_label="replica",
        exact_command=registration.realized_audit_command(directory, "replica", replica_output),
        output_path=replica_output,
        exit_status=replica_exit_status,
        payload_sha256=replica_payload_sha256,
        disposition="complete" if not replica_failure else "frozen-replica-failure",
        utc="2026-07-13T00:00:01+00:00",
        hostname="test-host",
    )
    pair = cast(dict[str, object], replica_row["pair_attestation"])
    assert replica_row["disposition"] == (
        "complete" if not replica_failure else "frozen-replica-failure"
    )
    assert pair["positive_pair_eligible"] is False
    assert pair["disposition"] == registration.PAIR_FROZEN_NEGATIVE_DISPOSITION
    assert pair["start_allowance_state"] == "exhausted-permanently"
    assert pair["third_start_allowed"] is False
    assert not (directory / "primary.available").exists()
    assert not (directory / "replica.available").exists()
    with pytest.raises(registration.AuditRegistrationError, match="positive"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert not (repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH).exists()


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("attestation_sha256", "9" * 64),
        ("command_sha256", "9" * 64),
        ("consumed_permit_sha256", "9" * 64),
        (
            "launcher_distribution_versions",
            {"arc3-crosslevel-voi": "0.1.0", "numpy": "0", "pyyaml": "6.0.3"},
        ),
        ("launcher_environment_sha256", "9" * 64),
        ("launcher_uv_version", "0.0.0"),
        ("capability_issued", False),
        ("read_authorization_consumed", False),
    ],
)
def test_promotion_rejects_tampered_launcher_capability_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, _payload_raw, _payload_sha256 = _complete_matching_test_pair(
        tmp_path,
        directory,
        monkeypatch,
    )
    ledger_path = directory / "execution_ledger.jsonl"
    rows = [
        cast(dict[str, object], json.loads(line))
        for line in ledger_path.read_text(encoding="ascii").splitlines()
    ]
    proof = cast(dict[str, object], rows[0]["launcher_attestation"])
    proof[field] = replacement
    ledger_path.write_bytes(
        b"".join(registration.canonical_json_bytes(row) + b"\n" for row in rows)
    )

    with pytest.raises(registration.AuditRegistrationError, match=r"launcher|successful"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert not (repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH).exists()
    assert not (repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH).exists()


@pytest.mark.parametrize("failure_target", ["artifact", "receipt"])
def test_promotion_retry_recovers_after_partial_temporary_write_failure(
    failure_target: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, payload_raw, payload_sha256 = _complete_matching_test_pair(
        tmp_path,
        directory,
        monkeypatch,
    )
    artifact_path = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    target_path = artifact_path if failure_target == "artifact" else receipt_path
    original_exclusive_write = registration._exclusive_write
    original_os_write = os.write
    failure_injected = False

    def fail_selected_publication_once(path: Path, raw: bytes) -> None:
        nonlocal failure_injected
        if path != target_path or failure_injected:
            original_exclusive_write(path, raw)
            return
        failure_injected = True
        write_calls = 0

        def fail_after_partial_write(descriptor: int, value: bytes) -> int:
            nonlocal write_calls
            write_calls += 1
            if write_calls == 1:
                partial = max(1, len(value) // 2)
                return original_os_write(descriptor, value[:partial])
            raise OSError("injected promotion write failure")

        monkeypatch.setattr(os, "write", fail_after_partial_write)
        try:
            original_exclusive_write(path, raw)
        finally:
            monkeypatch.setattr(os, "write", original_os_write)

    monkeypatch.setattr(registration, "_exclusive_write", fail_selected_publication_once)
    with pytest.raises(OSError, match="injected promotion write failure"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )

    assert failure_injected is True
    assert not os.path.lexists(receipt_path)
    if failure_target == "artifact":
        assert not os.path.lexists(artifact_path)
    else:
        assert artifact_path.read_bytes() == payload_raw
    assert not tuple(artifact_path.parent.glob(f".{target_path.name}.*.tmp"))
    for label in registration.REGISTERED_START_LABELS:
        external = _test_output_path(directory, label)
        assert external.read_bytes() == payload_raw

    monkeypatch.setattr(registration, "_exclusive_write", original_exclusive_write)
    result = registration.promote_verified_audit_pair(
        repository_root=repository,
        permit_directory=directory,
    )

    assert result["payload_sha256"] == payload_sha256
    assert artifact_path.read_bytes() == payload_raw
    assert receipt_path.is_file()


def test_promotion_revalidates_clean_tag_and_scientific_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, _payload_raw, _payload_sha256 = _complete_matching_test_pair(
        tmp_path, directory, monkeypatch
    )
    destination = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    clean_context = registration._clean_tagged_registration_context
    payload_validator = registration._validate_registered_scientific_payload

    def reject_dirty_head(_root: Path, **_kwargs: object) -> dict[str, str]:
        raise registration.AuditRegistrationError("dirty tagged head")

    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        reject_dirty_head,
    )
    with pytest.raises(registration.AuditRegistrationError, match="dirty tagged head"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert not destination.exists()
    assert not receipt_path.exists()

    monkeypatch.setattr(
        registration,
        "_clean_tagged_registration_context",
        clean_context,
    )

    def reject_payload(_raw: bytes, **_kwargs: object) -> dict[str, object]:
        raise registration.AuditRegistrationError("invalid scientific payload")

    monkeypatch.setattr(
        registration,
        "_validate_registered_scientific_payload",
        reject_payload,
    )
    with pytest.raises(registration.AuditRegistrationError, match="invalid scientific payload"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert not destination.exists()
    assert not receipt_path.exists()
    monkeypatch.setattr(
        registration,
        "_validate_registered_scientific_payload",
        payload_validator,
    )


def test_promotion_rejects_byte_identical_self_asserted_positive_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered, context, negative_raw = _registered_negative_payload_fixture()
    forged_raw = _self_asserted_positive_payload(registered, negative_raw)
    forged_sha256 = hashlib.sha256(forged_raw).hexdigest()
    registration_raw = registration.canonical_json_bytes(registered)
    payload_validator = registration._validate_registered_scientific_payload
    directory = tmp_path / "permits"
    roots = _publish_test_permits(
        directory,
        monkeypatch,
        permit_context=context,
        registration_value=registered,
        registration_raw=registration_raw,
    )
    repository = roots["primary"]
    (repository / "artifacts").mkdir()
    for label in registration.REGISTERED_START_LABELS:
        consumed = registration.consume_audit_start_permit(
            repository_root=roots[label],
            permit_record_path=directory / f"{label}.permit.json",
            available_marker_path=directory / f"{label}.available",
            output_path=_test_output_path(directory, label),
            expected_code_commit=context["code_commit"],
            expected_registration_sha256=context["registration_sha256"],
            expected_source_manifest_sha256=context["source_manifest_sha256"],
        )
        registration.claim_registered_lockbox_read_once(
            consumed,
            expected_code_commit=context["code_commit"],
            expected_repository_root=roots[label],
            expected_registration_sha256=context["registration_sha256"],
            expected_source_manifest_sha256=context["source_manifest_sha256"],
        )
        registration.mark_scientific_exposure_started(consumed)
        output_path = _test_output_path(directory, label)
        output_path.write_bytes(forged_raw)
        registration.append_execution_ledger(
            repository_root=roots[label],
            permit_directory=directory,
            run_label=label,
            exact_command=registration.realized_audit_command(
                directory,
                label,
                output_path,
            ),
            output_path=output_path,
            exit_status=0,
            payload_sha256=forged_sha256,
            disposition="mechanism_capability_pass_pair_attestation_pending",
            utc=f"2026-07-13T00:00:0{registration.REGISTERED_START_LABELS.index(label)}+00:00",
            hostname="test-host",
        )
    monkeypatch.setattr(
        registration,
        "_validate_registered_scientific_payload",
        payload_validator,
    )

    with pytest.raises(registration.AuditRegistrationError, match="evidence"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert not (repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH).exists()
    assert not (repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH).exists()


def test_promotion_recovers_exact_payload_after_injected_receipt_write_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, payload_raw, payload_sha256 = _complete_matching_test_pair(
        tmp_path,
        directory,
        monkeypatch,
    )
    destination = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    exclusive_write = registration._exclusive_write

    def crash_before_receipt(path: Path, raw: bytes) -> None:
        if path == receipt_path:
            raise OSError("injected second-write crash")
        exclusive_write(path, raw)

    monkeypatch.setattr(registration, "_exclusive_write", crash_before_receipt)
    with pytest.raises(OSError, match="injected second-write crash"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert destination.read_bytes() == payload_raw
    assert not receipt_path.exists()

    monkeypatch.setattr(registration, "_exclusive_write", exclusive_write)
    result = registration.promote_verified_audit_pair(
        repository_root=repository,
        permit_directory=directory,
    )
    assert result["payload_sha256"] == payload_sha256
    assert destination.read_bytes() == payload_raw
    assert receipt_path.is_file()
    assert len((directory / "execution_ledger.jsonl").read_text(encoding="ascii").splitlines()) == 2
    for label in registration.REGISTERED_START_LABELS:
        assert (directory / f"{label}.consumed").is_file()
        assert not (directory / f"{label}.available").exists()
    registration.load_validated_promotion_receipt(repository, directory)


def test_promotion_rejects_receipt_without_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, _payload_raw, _payload_sha256 = _complete_matching_test_pair(
        tmp_path, directory, monkeypatch
    )
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    receipt_only_raw = registration.canonical_json_bytes({"forged": "receipt-only"})
    receipt_path.write_bytes(receipt_only_raw)
    with pytest.raises(registration.AuditRegistrationError, match=r"without.*payload"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert receipt_path.read_bytes() == receipt_only_raw


def test_promotion_rejects_mismatched_recovery_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, _payload_raw, _payload_sha256 = _complete_matching_test_pair(
        tmp_path, directory, monkeypatch
    )
    destination = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    mismatched_payload_raw = registration.canonical_json_bytes({"forged": "payload"})
    destination.write_bytes(mismatched_payload_raw)
    with pytest.raises(registration.AuditRegistrationError, match="payload differs"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert destination.read_bytes() == mismatched_payload_raw
    assert not receipt_path.exists()


def test_matching_evaluator_negative_pair_promotes_verified_primary_bytes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "permits"
    _roots, repository, payload_raw, payload_sha256 = _complete_matching_test_pair(
        tmp_path,
        directory,
        monkeypatch,
    )
    result = registration.promote_verified_audit_pair(
        repository_root=repository,
        permit_directory=directory,
    )
    destination = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    assert destination.read_bytes() == payload_raw
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    assert receipt["artifact"] == {
        "path": registration.SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix(),
        "sha256": payload_sha256,
        "size_bytes": len(payload_raw),
    }
    assert (
        receipt["issuance_id"]
        == json.loads((directory / "audit_runs.exposed.json").read_bytes())["issuance_id"]
    )
    assert receipt["exact_bytes_equal"] is True
    assert receipt["schema_version"] == registration.PROMOTION_RECEIPT_SCHEMA_VERSION
    assert result == {
        "evaluator_dispositions": {
            "primary": "scientific-negative-runtime-v5-frozen",
            "replica": "scientific-negative-runtime-v5-frozen",
        },
        "pair_disposition": registration.PAIR_POSITIVE_DISPOSITION,
        "payload_sha256": payload_sha256,
        "positive_pair_eligible": True,
        "positive_pair_eligibility_scope": "pair-integrity-only",
        "repository_copy_path": (registration.SEALED_AUDIT_REPOSITORY_COPY_PATH.as_posix()),
        "repository_receipt_path": (registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()),
        "repository_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "size_bytes": len(payload_raw),
        "state": "repository-copy-published",
    }
    assert (
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
        == result
    )
    receipt["issuance_id"] = "9" * 64
    tampered_receipt_raw = registration.canonical_json_bytes(receipt)
    receipt_path.write_bytes(tampered_receipt_raw)
    with pytest.raises(registration.AuditRegistrationError, match="receipt identity"):
        registration.load_validated_promotion_receipt(repository, directory)
    assert destination.read_bytes() == payload_raw
    with pytest.raises(registration.AuditRegistrationError, match="receipt identity"):
        registration.promote_verified_audit_pair(
            repository_root=repository,
            permit_directory=directory,
        )
    assert receipt_path.read_bytes() == tampered_receipt_raw


def test_receipt_loader_rejects_consistent_payload_substitution_behind_old_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered, context, original_raw = _registered_negative_payload_fixture()
    original_sha256 = hashlib.sha256(original_raw).hexdigest()
    original_payload = cast(dict[str, object], json.loads(original_raw))
    disposition = cast(str, original_payload["disposition"])
    real_payload_validator = registration._validate_registered_scientific_payload
    directory = tmp_path / "permits"
    roots = _publish_test_permits(
        directory,
        monkeypatch,
        permit_context=context,
        registration_value=registered,
        registration_raw=registration.canonical_json_bytes(registered),
    )
    monkeypatch.setattr(
        registration,
        "_validate_registered_scientific_payload",
        real_payload_validator,
    )
    repository = roots["primary"]
    (repository / "artifacts").mkdir()
    for label in registration.REGISTERED_START_LABELS:
        consumed = registration.consume_audit_start_permit(
            repository_root=roots[label],
            permit_record_path=directory / f"{label}.permit.json",
            available_marker_path=directory / f"{label}.available",
            output_path=_test_output_path(directory, label),
            expected_code_commit=context["code_commit"],
            expected_registration_sha256=context["registration_sha256"],
            expected_source_manifest_sha256=context["source_manifest_sha256"],
        )
        registration.claim_registered_lockbox_read_once(
            consumed,
            expected_code_commit=context["code_commit"],
            expected_repository_root=roots[label],
            expected_registration_sha256=context["registration_sha256"],
            expected_source_manifest_sha256=context["source_manifest_sha256"],
        )
        registration.mark_scientific_exposure_started(consumed)
        output_path = _test_output_path(directory, label)
        output_path.write_bytes(original_raw)
        registration.append_execution_ledger(
            repository_root=roots[label],
            permit_directory=directory,
            run_label=label,
            exact_command=registration.realized_audit_command(
                directory,
                label,
                output_path,
            ),
            output_path=output_path,
            exit_status=0,
            payload_sha256=original_sha256,
            disposition=disposition,
            utc=f"2026-07-13T00:00:0{registration.REGISTERED_START_LABELS.index(label)}+00:00",
            hostname="test-host",
        )
    registration.promote_verified_audit_pair(
        repository_root=repository,
        permit_directory=directory,
    )
    ledger_rows = [
        cast(dict[str, object], json.loads(line))
        for line in (directory / "execution_ledger.jsonl").read_text(encoding="ascii").splitlines()
    ]
    replacement_payload = cast(dict[str, object], json.loads(original_raw))
    replacement_environment = cast(
        dict[str, object], replacement_payload["deterministic_environment"]
    )
    replacement_environment["platform_release"] = "alternate-validator-valid-test-linux"
    replacement_raw = registration.canonical_json_bytes(replacement_payload)
    replacement_sha256 = hashlib.sha256(replacement_raw).hexdigest()
    assert replacement_raw != original_raw
    assert replacement_sha256 != original_sha256
    assert (
        registration._validate_registered_scientific_payload(
            replacement_raw,
            registration=registered,
            context=context,
        )["disposition"]
        == disposition
    )

    for row in ledger_rows:
        Path(cast(str, row["output_path"])).write_bytes(replacement_raw)
        assert row["payload_sha256"] == original_sha256
    artifact_path = repository / registration.SEALED_AUDIT_REPOSITORY_COPY_PATH
    receipt_path = repository / registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH
    artifact_path.write_bytes(replacement_raw)
    receipt = cast(dict[str, object], json.loads(receipt_path.read_bytes()))
    artifact = cast(dict[str, object], receipt["artifact"])
    artifact["sha256"] = replacement_sha256
    artifact["size_bytes"] = len(replacement_raw)
    receipt_path.write_bytes(registration.canonical_json_bytes(receipt))

    with pytest.raises(
        registration.AuditRegistrationError,
        match=r"ledger hashes|immutable",
    ):
        registration.load_validated_promotion_receipt(repository, directory)
    assert artifact_path.read_bytes() == replacement_raw
    assert all(
        Path(cast(str, row["output_path"])).read_bytes() == replacement_raw for row in ledger_rows
    )


def test_promote_pair_cli_uses_canonical_permit_directory_and_rejects_mixed_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Path] = {}
    expected: dict[str, object] = {
        "repository_receipt_path": (registration.SEALED_AUDIT_REPOSITORY_RECEIPT_PATH.as_posix()),
        "repository_receipt_sha256": "5" * 64,
        "state": "repository-copy-published",
    }

    def fake_promote(
        *, repository_root: str | Path, permit_directory: str | Path
    ) -> dict[str, object]:
        captured["repository_root"] = Path(repository_root)
        captured["permit_directory"] = Path(permit_directory)
        return expected

    monkeypatch.setattr(registration, "promote_verified_audit_pair", fake_promote)
    assert (
        registration.main(
            [
                "--repository-root",
                str(tmp_path),
                "--promote-pair",
            ]
        )
        == 0
    )
    assert captured == {
        "repository_root": tmp_path.resolve(),
        "permit_directory": registration.CANONICAL_EXTERNAL_PERMIT_DIRECTORY,
    }
    assert json.loads(capsys.readouterr().out) == expected

    with pytest.raises(registration.AuditRegistrationError, match="cannot accompany"):
        registration.main(
            [
                "--repository-root",
                str(tmp_path),
                "--promote-pair",
                "--output",
                str(tmp_path / "forbidden.json"),
            ]
        )
    with pytest.raises(SystemExit):
        registration.main(
            [
                "--repository-root",
                str(tmp_path),
                "--promote-pair",
                "--prepare-permits",
                str(tmp_path / "permits"),
            ]
        )


def test_scientific_output_must_be_external_with_fixed_suffix(tmp_path: Path) -> None:
    repository = tmp_path / "run" / "repo"
    repository.mkdir(parents=True)
    external = tmp_path / "run" / registration.SCIENTIFIC_OUTPUT_RELATIVE_PATH
    assert (
        registration.require_external_scientific_output_path(repository, external)
        == external.resolve()
    )
    inside = repository / registration.SCIENTIFIC_OUTPUT_RELATIVE_PATH
    with pytest.raises(registration.AuditRegistrationError, match="outside"):
        registration.require_external_scientific_output_path(repository, inside)
    with pytest.raises(registration.AuditRegistrationError, match="fixed scientific"):
        registration.require_external_scientific_output_path(
            repository, tmp_path / "run" / "wrong.json"
        )


def test_clean_status_pathspec_explicitly_excludes_lockbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *arguments: str) -> bytes:
        calls.append(arguments)
        return b"dirty"

    monkeypatch.setattr(registration, "_git", fake_git)
    with pytest.raises(registration.AuditRegistrationError, match="clean worktree"):
        registration._clean_tagged_registration_context(tmp_path)
    assert calls == [
        (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            f":(exclude){registration.LOCKBOX_ARTIFACT_RELATIVE_PATH}",
        )
    ]
