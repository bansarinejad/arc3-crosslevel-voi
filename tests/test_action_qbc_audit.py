from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import platform
import site
import subprocess
import sys
import sysconfig
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

import arc3_voi.action_qbc_audit as audit
import arc3_voi.action_qbc_lockbox as lockbox_module
import scripts.audit_action_qbc_lockbox as audit_script
from arc3_voi.action_qbc_lockbox import (
    build_order_transform_maps,
    generate_open_scene,
)
from arc3_voi.action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    action_qbc_policy_sha256,
    select_action_conditional_qbc,
)
from arc3_voi.config import load_config
from arc3_voi.controller import Variant
from arc3_voi.planner import PlanningSnapshot
from arc3_voi.structured_templates import instantiate_structured_priors
from arc3_voi.types import Action, ActionKind, GameState, Prediction

A1 = Action(ActionKind.ACTION1)
A2 = Action(ActionKind.ACTION2)
A3 = Action(ActionKind.ACTION3)
A4 = Action(ActionKind.ACTION4)


def _synthetic_registered_rows() -> list[dict[str, Any]]:
    """Build public row addresses without consulting sealed scenes or seed fields."""

    scene_sha_by_key = {
        (family, family_index): audit.canonical_sha256(
            {"family": family, "family_index": family_index, "scope": "test"}
        )
        for family in audit.SEALED_SCENE_FAMILIES
        for family_index in range(4)
    }
    rows: list[dict[str, Any]] = []
    for (family, family_index), scene_sha256 in scene_sha_by_key.items():
        rows.append(
            {
                "family": family,
                "fixture_sha256": scene_sha256,
                "kind": "base_scene",
                "row_id": f"base:{family}:{family_index}",
                "scene_index": family_index,
            }
        )
    for (family, family_index), scene_sha256 in scene_sha_by_key.items():
        for transform in audit.SEALED_VISUAL_TRANSFORM_NAMES:
            address: audit.JsonValue = {
                "lockbox_content_sha256": audit.LOCKBOX_CONTENT_SHA256,
                "scene_sha256": scene_sha256,
                "transform": transform,
            }
            rows.append(
                {
                    "family": family,
                    "fixture_address_sha256": audit.canonical_sha256(address),
                    "kind": "visual_transform",
                    "row_id": f"visual:{family}:{family_index}:{transform}",
                    "scene_index": family_index,
                    "transform": transform,
                }
            )
    for (family, family_index), scene_sha256 in scene_sha_by_key.items():
        for transform in audit.ORDER_TRANSFORM_NAMES:
            address = {
                "lockbox_content_sha256": audit.LOCKBOX_CONTENT_SHA256,
                "scene_sha256": scene_sha256,
                "transform": transform,
            }
            rows.append(
                {
                    "family": family,
                    "fixture_address_sha256": audit.canonical_sha256(address),
                    "kind": "order_transform",
                    "row_id": f"order:{family}:{family_index}:{transform}",
                    "scene_index": family_index,
                    "transform": transform,
                }
            )
    rows.extend(
        {
            "control_id": name,
            "kind": "control",
            "row_id": f"control:{name}",
        }
        for name in audit.PREREGISTERED_CONTROL_ORDER
    )
    for row_index, row in enumerate(rows):
        row["row_index"] = row_index
    assert len(rows) == 140
    return rows


def _prediction(
    label: int,
    *,
    state: GameState = GameState.NOT_FINISHED,
) -> Prediction:
    return Prediction(np.asarray([[label]], dtype=np.int16), state, 0, {})


def _snapshot(
    actions: Sequence[Action],
    weights: Sequence[float],
    predictions: Mapping[Action, Sequence[Prediction]],
    costs: Mapping[Action, Sequence[float]],
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=tuple(actions),
        hypothesis_ids=tuple(f"h{index}" for index in range(len(weights))),
        weights=tuple(weights),
        predictions={action: tuple(predictions[action]) for action in actions},
        costs={action: tuple(costs[action]) for action in actions},
    )


def _split_snapshot(
    *,
    weights: tuple[float, float] = (0.5, 0.5),
    cross_cost: float = 2.0,
    probe_cost: float = 4.0,
) -> PlanningSnapshot:
    first = _prediction(1)
    second = _prediction(2)
    return _snapshot(
        (A1, A2, A3),
        weights,
        {
            A1: (first, first),
            A2: (second, second),
            A3: (first, second),
        },
        {
            A1: (0.0, cross_cost),
            A2: (cross_cost, 0.0),
            A3: (probe_cost, probe_cost),
        },
    )


def _case(control: audit.AuditControl) -> audit.OpenAuditCase:
    first = _prediction(1)
    second = _prediction(2)
    match control:
        case audit.AuditControl.CONCENTRATION_ONE:
            snapshot = _snapshot(
                (A1, A2),
                (0.5, 0.5),
                {A1: (first, first), A2: (second, second)},
                {A1: (0.0, 0.0), A2: (1.0, 1.0)},
            )
            multiplier = 23.0
            probes_used = 0
        case audit.AuditControl.CONCENTRATION_THRESHOLD:
            snapshot = _split_snapshot(weights=(0.8, 0.2), cross_cost=10.0, probe_cost=20.0)
            multiplier = 23.0
            probes_used = 0
        case audit.AuditControl.EVSI_ZERO:
            snapshot = _snapshot(
                (A1, A2, A3),
                (0.5, 0.5),
                {A1: (first, first), A2: (second, second), A3: (first, second)},
                {A1: (0.0, 0.0), A2: (1.0, 1.0), A3: (2.0, 2.0)},
            )
            multiplier = 23.0
            probes_used = 0
        case audit.AuditControl.EVSI_0049:
            snapshot = _split_snapshot(cross_cost=0.098, probe_cost=1.0)
            multiplier = 23.0
            probes_used = 0
        case audit.AuditControl.HIGH_CONCENTRATION_POSITIVE_UTILITY:
            snapshot = _split_snapshot(weights=(0.9, 0.1), cross_cost=20.0, probe_cost=30.0)
            multiplier = 23.0
            probes_used = 0
        case audit.AuditControl.PROBE_CAP:
            snapshot = _split_snapshot(cross_cost=2.0, probe_cost=4.0)
            multiplier = 23.0
            probes_used = 3
        case audit.AuditControl.CATASTROPHE:
            catastrophe = _prediction(2, state=GameState.GAME_OVER)
            snapshot = _snapshot(
                (A1, A2, A3),
                (0.5, 0.5),
                {
                    A1: (first, first),
                    A2: (catastrophe, catastrophe),
                    A3: (first, catastrophe),
                },
                {A1: (0.0, 2.0), A2: (2.0, 0.0), A3: (4.0, 4.0)},
            )
            multiplier = 2.0
            probes_used = 0
        case audit.AuditControl.FINAL_LEVEL:
            snapshot = _split_snapshot(cross_cost=4.0, probe_cost=8.0)
            multiplier = 1.0
            probes_used = 0
        case audit.AuditControl.TIE_BEHAVIOR:
            snapshot = _snapshot(
                (A1, A2, A3, A4),
                (0.5, 0.5),
                {
                    A1: (first, first),
                    A2: (second, second),
                    A3: (first, second),
                    A4: (first, second),
                },
                {
                    A1: (0.0, 4.0),
                    A2: (4.0, 0.0),
                    A3: (8.0, 8.0),
                    A4: (8.0, 8.0),
                },
            )
            multiplier = 1.0
            probes_used = 0
    return audit.OpenAuditCase(control, snapshot, multiplier, probes_used)


def _evaluate(control: audit.AuditControl) -> dict[str, Any]:
    return cast(dict[str, Any], audit.evaluate_open_fixture(_case(control)))


def _row(result: Mapping[str, Any], action: Action) -> Mapping[str, Any]:
    rows = result["selection"]["rows"]
    return next(row for row in rows if row["action"]["kind"] == int(action.kind))


def test_authorization_contract_pins_known_identities_and_marks_only_future_freezes() -> None:
    provenance = audit.EXPECTED_AUDIT_PROVENANCE

    assert audit.AUDIT_AUTHORIZATION_ENABLED is False
    assert audit.AUDIT_AUTHORIZATION_STATE == (
        "sealed-audit-capability-required-runtime-v5-disabled"
    )
    assert "code_commit" in audit.PENDING_FREEZE_FIELDS
    assert "registration_sha256" in audit.PENDING_FREEZE_FIELDS
    assert "source_manifest_sha256" in audit.PENDING_FREEZE_FIELDS
    assert "git_clean_status_sha256" in audit.PENDING_FREEZE_FIELDS
    assert not provenance.fully_frozen
    assert provenance.code_commit is None
    assert provenance.source_files is None
    assert provenance.source_manifest_sha256 is None
    assert provenance.config_sha256 == audit.AUDIT_CONFIG_FILE_SHA256
    assert provenance.matrix_sha256 == audit.AUDIT_MATRIX_FILE_SHA256
    assert provenance.registration_sha256 is None
    assert provenance.audit_contract_version == audit.ACTION_QBC_AUDIT_CONTRACT_VERSION
    assert provenance.registration_schema_version == (
        audit.AUDIT_REGISTRATION_SCHEMA_VERSION
    )
    assert provenance.resource_counter_schema_sha256 == (
        audit.AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256
    )
    assert provenance.runtime_version == "crosslevel-voi-runtime-v5"
    assert provenance.probe_policy_version == ACTION_QBC_POLICY_VERSION
    assert provenance.probe_policy_sha256 == ACTION_QBC_POLICY_SHA256
    assert provenance.candidate_policy_sha256 == (
        "a9220009c5fd4b6da602580db439e25f9acaef74799de050a7a56e6c64bba82c"
    )
    assert provenance.compiler_contract_sha256 == (
        "eeccd86db3346fd15d2e3dbc8e82ee2bb60e23bc30c0490750a7a0fbaa9e14e5"
    )
    assert provenance.generator_source_commit == (
        "4aae43d2dda05b2b4b9ef2670ef83e3b6a52eb37"
    )
    assert provenance.lockbox_artifact_sha256 == (
        "d2e84af6527b1dfe686d3113000e0e0b72925c0a8735228da0d3f3c094975953"
    )
    assert audit.AUDIT_AUTHORIZATION_CONTRACT["shipped_cli_capability"] == (
        "external one-shot permit plus opaque issued capability"
    )


def test_open_audit_uses_the_exact_shared_pure_selector() -> None:
    assert audit.ACTION_QBC_AUDIT_SELECTOR is select_action_conditional_qbc
    assert action_qbc_policy_sha256() == ACTION_QBC_POLICY_SHA256


def test_capability_is_unissuable_and_gate_rejects_before_touching_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(TypeError, match="issue_registered_audit_capability"):
        audit.RegisteredAuditCapability()

    def forbidden_path_operation(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("registered lockbox path was touched")

    for name in ("exists", "open", "read_bytes", "resolve", "stat"):
        monkeypatch.setattr(Path, name, forbidden_path_operation)

    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="explicit"):
        audit.run_registered_audit_scaffold("registered-do-not-touch.json")


def _populate_registration_inputs(root: Path) -> None:
    for index, relative in enumerate(audit.AUDIT_SOURCE_FILE_ORDER):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"open-registration-input-{index}\n".encode())
    for relative in (
        audit.AUDIT_CONFIG_RELATIVE_PATH,
        audit.AUDIT_MATRIX_RELATIVE_PATH,
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(relative).read_bytes())
    registration_path = root / audit.AUDIT_REGISTRATION_RELATIVE_PATH
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.write_bytes(b"{}")


def _fake_clean_registration_git(
    root: Path,
    head: str,
) -> Any:
    def fake_git(
        *arguments: str,
        root: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        del check
        if arguments[:3] == ("status", "--porcelain=v1", "--untracked-files=all"):
            assert arguments[3:] == (
                "--",
                ".",
                f":(exclude){audit.LOCKBOX_ARTIFACT_RELATIVE_PATH}",
            )
            payload = b""
        elif arguments[0] == "diff":
            assert arguments[-3:] == (
                "--",
                ".",
                f":(exclude){audit.LOCKBOX_ARTIFACT_RELATIVE_PATH}",
            )
            payload = b""
        elif arguments in (
            ("rev-parse", "HEAD"),
            ("rev-parse", f"{audit.AUDIT_REGISTRATION_TAG}^{{commit}}"),
        ):
            payload = f"{head}\n".encode()
        elif len(arguments) == 2 and arguments[0] == "show":
            prefix = f"{head}:"
            assert arguments[1].startswith(prefix)
            payload = (root / arguments[1][len(prefix) :]).read_bytes()
        else:  # pragma: no cover - makes unexpected provenance operations loud
            raise AssertionError(f"unexpected Git arguments: {arguments}")
        return subprocess.CompletedProcess(arguments, 0, payload, b"")

    return fake_git


def _inject_test_launch_attestation(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    consumed_permit: Mapping[str, object] | None = None,
    code_commit: str = "a" * 40,
    registration_sha256: str = "b" * 64,
    source_manifest_sha256: str = "c" * 64,
) -> audit.RegisteredAuditLaunchAttestation:
    """Install an explicit unit-test registry state around an opaque token."""

    permit = dict(consumed_permit or {})
    token = object.__new__(audit.RegisteredAuditLaunchAttestation)
    state = SimpleNamespace(
        attestation_sha256="d" * 64,
        code_commit=code_commit,
        consumed_permit_sha256=audit.canonical_sha256(cast(Any, permit)),
        registration_sha256=registration_sha256,
        root=root.resolve(strict=True),
        run_label=permit.get("run_label", "primary"),
        source_manifest_sha256=source_manifest_sha256,
    )
    monkeypatch.setattr(
        audit,
        "_registered_launch_attestation_state",
        lambda supplied, *, consume_phase: state
        if supplied is token
        else (_ for _ in ()).throw(
            audit.RegisteredAuditNotAuthorized("test token differs")
        ),
    )
    monkeypatch.setattr(
        audit,
        "_revalidate_registered_launch_attestation_state",
        lambda _state: None,
    )
    return token


def _real_launch_registry_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    issuance_digit: str,
) -> tuple[
    Path,
    tuple[str, ...],
    dict[str, object],
    dict[str, int],
    Any,
]:
    """Exercise the production issuer/registry with synthetic frozen identities."""

    repository = tmp_path / "repository"
    repository.mkdir()
    permit_directory = tmp_path / "permits"
    permit_directory.mkdir()
    output = tmp_path / "results" / "sealed" / "action_qbc_v5_scientific_payload.json"
    run_label = "primary"
    permit_record = permit_directory / f"{run_label}.permit.json"
    permit_marker = permit_directory / f"{run_label}.available"
    command = (
        *audit._REGISTERED_LAUNCH_PREFIX,
        "--repository-root",
        ".",
        "--registration",
        audit.AUDIT_REGISTRATION_RELATIVE_PATH,
        "--permit-record",
        str(permit_record),
        "--permit-marker",
        str(permit_marker),
        "--output",
        str(output),
    )
    registration_raw = b"synthetic-registration"
    source_files = (audit.SourceFileIdentity("synthetic.py", "f" * 64),)
    source_manifest_sha256 = audit.canonical_sha256(
        cast(Any, [identity.as_json() for identity in source_files])
    )
    code_commit = issuance_digit * 40
    runtime = {
        "parent_process_id": 80_001,
        "parent_start_time_ticks": 90_001,
        "process_id": 70_001,
        "process_start_time_ticks": 60_001,
    }

    def verified_identity(
        observed_repository: Path,
        observed_command: Sequence[str],
    ) -> tuple[dict[str, audit.JsonValue], int, int, int, int]:
        assert observed_repository == repository.resolve(strict=True)
        assert tuple(observed_command) == command
        identity: dict[str, audit.JsonValue] = {
            "command_sha256": audit.canonical_sha256(list(command)),
            "launcher_distribution_versions": dict(
                audit.REGISTERED_AUDIT_DISTRIBUTIONS
            ),
            "launcher_environment_sha256": "e" * 64,
            "launcher_uv_version": audit.REGISTERED_AUDIT_UV_VERSION,
            "output_path_sha256": hashlib.sha256(
                output.resolve(strict=False).as_posix().encode()
            ).hexdigest(),
            "parent_process_id": runtime["parent_process_id"],
            "parent_start_time_ticks": runtime["parent_start_time_ticks"],
            "permit_marker_path_sha256": hashlib.sha256(
                permit_marker.resolve(strict=False).as_posix().encode()
            ).hexdigest(),
            "permit_record_path_sha256": hashlib.sha256(
                permit_record.resolve(strict=False).as_posix().encode()
            ).hexdigest(),
            "process_id": runtime["process_id"],
            "process_start_time_ticks": runtime["process_start_time_ticks"],
            "repository_root_sha256": hashlib.sha256(
                repository.resolve(strict=True).as_posix().encode()
            ).hexdigest(),
            "run_label": run_label,
        }
        return (
            identity,
            runtime["process_id"],
            runtime["parent_process_id"],
            runtime["process_start_time_ticks"],
            runtime["parent_start_time_ticks"],
        )

    monkeypatch.setattr(audit, "_verified_registered_launch_identity", verified_identity)
    monkeypatch.setattr(audit, "_require_clean_tagged_head", lambda _root: code_commit)
    monkeypatch.setattr(
        audit,
        "_read_plain_file",
        lambda _root, relative: registration_raw
        if relative == audit.AUDIT_REGISTRATION_RELATIVE_PATH
        else (_ for _ in ()).throw(AssertionError(f"unexpected read: {relative}")),
    )
    monkeypatch.setattr(audit, "_source_file_manifest", lambda _root: source_files)
    consumed: dict[str, object] = {
        "code_commit": code_commit,
        "consumed": True,
        "issuance_id": issuance_digit * 64,
        "permit_directory": str(permit_directory.resolve(strict=True)),
        "registration_sha256": hashlib.sha256(registration_raw).hexdigest(),
        "repository_root": str(repository.resolve(strict=True)),
        "run_label": run_label,
        "scientific_output_path": str(output.resolve(strict=False)),
        "scientific_output_paths": {
            "primary": str(output.resolve(strict=False)),
            "replica": str(
                (
                    tmp_path
                    / "replica-results"
                    / "sealed"
                    / "action_qbc_v5_scientific_payload.json"
                ).resolve(strict=False)
            ),
        },
        "source_manifest_sha256": source_manifest_sha256,
    }

    def issue() -> audit.RegisteredAuditLaunchAttestation:
        return audit.issue_registered_audit_launch_attestation(
            root=repository,
            exact_command=command,
            consumed_permit=consumed,
        )

    return repository, command, consumed, runtime, issue


def test_real_launch_registry_rejects_constructor_forgery_and_duplicate_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(TypeError, match="canonical CLI process"):
        audit.RegisteredAuditLaunchAttestation()
    forged = object.__new__(audit.RegisteredAuditLaunchAttestation)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="not issued"):
        audit._registered_launch_attestation_state(forged, consume_phase=None)

    _repository, _command, _consumed, _runtime, issue = (
        _real_launch_registry_fixture(
            tmp_path,
            monkeypatch,
            issuance_digit="1",
        )
    )
    issued = issue()
    assert isinstance(issued, audit.RegisteredAuditLaunchAttestation)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="already issued"):
        issue()


def test_real_launch_registry_binds_consumed_permit_to_exact_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repository, _command, consumed, _runtime, issue = _real_launch_registry_fixture(
        tmp_path,
        monkeypatch,
        issuance_digit="9",
    )
    output_paths = cast(dict[str, str], consumed["scientific_output_paths"])
    consumed["scientific_output_path"] = output_paths["replica"]
    with pytest.raises(
        audit.RegisteredAuditNotAuthorized,
        match="command/permit/HEAD binding differs",
    ):
        issue()


def test_real_launch_registry_capability_and_ledger_phases_are_one_shot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, command, _consumed, _runtime, issue = _real_launch_registry_fixture(
        tmp_path,
        monkeypatch,
        issuance_digit="2",
    )
    token = issue()
    state = audit._consume_registered_launch_attestation_for_capability(
        token,
        repository_root=repository,
    )
    assert state.capability_phase_consumed is True
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="phase is exhausted"):
        audit._consume_registered_launch_attestation_for_capability(
            token,
            repository_root=repository,
        )
    proof = audit.consume_registered_audit_launch_attestation_for_ledger(
        token,
        repository_root=repository,
        exact_command=command,
    )
    assert proof["valid"] is True
    assert proof["launcher_uv_version"] == "0.11.28"
    assert proof["launcher_distribution_versions"] == dict(
        audit.REGISTERED_AUDIT_DISTRIBUTIONS
    )
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="phase is exhausted"):
        audit.consume_registered_audit_launch_attestation_for_ledger(
            token,
            repository_root=repository,
            exact_command=command,
        )


def test_real_launch_registry_revalidation_rejects_pid_start_drift_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _command, _consumed, runtime, issue = _real_launch_registry_fixture(
        tmp_path,
        monkeypatch,
        issuance_digit="3",
    )
    token = issue()
    runtime["process_start_time_ticks"] += 1
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="identity changed"):
        audit._consume_registered_launch_attestation_for_capability(
            token,
            repository_root=repository,
        )
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="phase is exhausted"):
        audit._consume_registered_launch_attestation_for_capability(
            token,
            repository_root=repository,
        )


def test_unsuccessful_ledger_is_allowed_once_without_capability_or_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, command, _consumed, _runtime, issue = _real_launch_registry_fixture(
        tmp_path,
        monkeypatch,
        issuance_digit="4",
    )
    token = issue()
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="consumed registered read"):
        audit.consume_registered_audit_capability_for_ledger(
            None,
            token,
            repository_root=repository,
            exact_command=command,
            exit_status=0,
            payload_sha256=None,
        )
    proof = audit.consume_registered_audit_capability_for_ledger(
        None,
        token,
        repository_root=repository,
        exact_command=command,
        exit_status=1,
        payload_sha256=None,
    )
    assert proof["capability_issued"] is False
    assert proof["read_authorization_consumed"] is False
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="phase is exhausted"):
        audit.consume_registered_audit_capability_for_ledger(
            None,
            token,
            repository_root=repository,
            exact_command=command,
            exit_status=1,
            payload_sha256=None,
        )


def test_successful_ledger_requires_same_capability_with_consumed_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, command, _consumed, _runtime, issue = _real_launch_registry_fixture(
        tmp_path,
        monkeypatch,
        issuance_digit="5",
    )
    launch_token = issue()
    capability = object.__new__(audit.RegisteredAuditCapability)
    capability_state = SimpleNamespace(
        launch_attestation=launch_token,
        read_authorization_consumed=False,
    )

    def capability_lookup(
        supplied: audit.RegisteredAuditCapability | None,
        *,
        consume_read: bool,
    ) -> SimpleNamespace:
        assert supplied is capability
        assert consume_read is False
        return capability_state

    monkeypatch.setattr(audit, "_registered_capability_state", capability_lookup)
    monkeypatch.setattr(
        audit,
        "_revalidate_registered_capability_state",
        lambda _state: None,
    )
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="consumed registered read"):
        audit.consume_registered_audit_capability_for_ledger(
            capability,
            launch_token,
            repository_root=repository,
            exact_command=command,
            exit_status=0,
            payload_sha256="a" * 64,
        )
    capability_state.read_authorization_consumed = True
    proof = audit.consume_registered_audit_capability_for_ledger(
        capability,
        launch_token,
        repository_root=repository,
        exact_command=command,
        exit_status=0,
        payload_sha256="a" * 64,
    )
    assert proof["capability_issued"] is True
    assert proof["read_authorization_consumed"] is True


def test_frozen_config_and_zero_run_manifest_have_exact_registered_hashes() -> None:
    assert hashlib.sha256(Path(audit.AUDIT_CONFIG_RELATIVE_PATH).read_bytes()).hexdigest() == (
        audit.AUDIT_CONFIG_FILE_SHA256
    )
    assert hashlib.sha256(Path(audit.AUDIT_MATRIX_RELATIVE_PATH).read_bytes()).hexdigest() == (
        audit.AUDIT_MATRIX_FILE_SHA256
    )


def test_capability_issuance_rejects_dirty_tree_before_registration_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def dirty_git(
        *arguments: str,
        root: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        del root, check
        assert arguments == (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            f":(exclude){audit.LOCKBOX_ARTIFACT_RELATIVE_PATH}",
        )
        return subprocess.CompletedProcess(arguments, 0, b"?? unreviewed.py\n", b"")

    monkeypatch.setattr(audit, "_git", dirty_git)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("registration was read while tree was dirty")
        ),
    )
    launch_attestation = _inject_test_launch_attestation(tmp_path, monkeypatch)

    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="clean worktree"):
        audit.issue_registered_audit_capability(
            root=tmp_path,
            launch_attestation=launch_attestation,
        )


def test_capability_issuance_rejects_missing_registration_after_clean_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    monkeypatch.setattr(audit, "_git", _fake_clean_registration_git(tmp_path, head))
    launch_attestation = _inject_test_launch_attestation(
        tmp_path,
        monkeypatch,
        code_commit=head,
    )

    with pytest.raises(
        audit.RegisteredAuditNotAuthorized,
        match="dedicated action-QBC audit registration validation failed",
    ):
        audit.issue_registered_audit_capability(
            root=tmp_path,
            launch_attestation=launch_attestation,
        )


def test_clean_tagged_exact_registration_can_issue_without_source_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _populate_registration_inputs(tmp_path)
    registration_path = tmp_path / audit.AUDIT_REGISTRATION_RELATIVE_PATH
    head = "b" * 40
    monkeypatch.setattr(audit, "_git", _fake_clean_registration_git(tmp_path, head))
    source_files = audit._source_file_manifest(tmp_path)
    source_rows = [identity.as_json() for identity in source_files]
    source_manifest_sha256 = audit.canonical_sha256(cast(Any, source_rows))
    registration_raw = registration_path.read_bytes()
    registration_sha256 = hashlib.sha256(registration_raw).hexdigest()
    read_claimed = False

    def claim_read_once(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal read_claimed
        if read_claimed:
            raise FileExistsError("synthetic durable read claim already exists")
        read_claimed = True
        return {"state": "lockbox_read_claimed"}

    fake_registration = SimpleNamespace(
        claim_registered_lockbox_read_once=claim_read_once,
        load_validated_registration=lambda _root, _path: (
            {
                "frozen_files": {
                    "files": source_rows,
                    "manifest_sha256": source_manifest_sha256,
                }
            },
            registration_raw,
        ),
        validate_consumed_audit_start_permit=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        audit,
        "load_audit_registration_admin",
        lambda _root: fake_registration,
    )
    consumed = {
        "code_commit": head,
        "consumed": True,
        "registration_sha256": registration_sha256,
        "run_label": "primary",
        "source_manifest_sha256": source_manifest_sha256,
    }
    launch_attestation = _inject_test_launch_attestation(
        tmp_path,
        monkeypatch,
        consumed_permit=consumed,
        code_commit=head,
        registration_sha256=registration_sha256,
        source_manifest_sha256=source_manifest_sha256,
    )

    capability = audit.issue_registered_audit_capability(
        root=tmp_path,
        launch_attestation=launch_attestation,
        consumed_permit=consumed,
    )
    provenance = audit.require_registered_audit_authorized(capability)

    assert provenance.fully_frozen
    assert provenance.code_commit == head
    assert provenance.config_sha256 == audit.AUDIT_CONFIG_FILE_SHA256
    assert provenance.matrix_sha256 == audit.AUDIT_MATRIX_FILE_SHA256
    assert provenance.source_files is not None
    assert tuple(identity.path for identity in provenance.source_files) == (
        audit.AUDIT_SOURCE_FILE_ORDER
    )
    assert provenance.registration_sha256 == hashlib.sha256(
        registration_path.read_bytes()
    ).hexdigest()
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="legacy scaffold"):
        audit.run_registered_audit_scaffold("still-not-read.json", capability=capability)

    forged = object.__new__(audit.RegisteredAuditCapability)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="not issued"):
        audit.require_registered_audit_authorized(forged)

    synthetic_manifest = {"content_sha256": "c" * 64}
    raw = audit.canonical_json_bytes(cast(audit.JsonValue, synthetic_manifest))
    artifact = tmp_path / audit.LOCKBOX_ARTIFACT_RELATIVE_PATH
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(raw)
    monkeypatch.setattr(audit, "LOCKBOX_ARTIFACT_SIZE_BYTES", len(raw))
    monkeypatch.setattr(audit, "LOCKBOX_ARTIFACT_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(audit, "LOCKBOX_CONTENT_SHA256", "c" * 64)
    monkeypatch.setattr(
        lockbox_module,
        "validate_registered_manifest",
        lambda _value: None,
    )
    counters = audit.AuditCounterState()

    assert audit.read_authorized_registered_manifest(
        capability,
        counters=counters,
    ) == synthetic_manifest
    assert counters.snapshot()["lockbox_path_operations"] == 4
    assert counters.snapshot()["lockbox_bytes_read"] == len(raw)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="read authorization"):
        audit.read_authorized_registered_manifest(capability, counters=counters)
    assert counters.snapshot()["lockbox_path_operations"] == 4


def _inject_read_capability_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, list[bool], list[str]]:
    claims: list[str] = []
    lookup_modes: list[bool] = []
    state = SimpleNamespace(
        consumed_permit={},
        provenance=SimpleNamespace(
            code_commit="a" * 40,
            registration_sha256="b" * 64,
            source_manifest_sha256="c" * 64,
        ),
        root=tmp_path,
    )
    registration = SimpleNamespace(
        claim_registered_lockbox_read_once=lambda *_args, **_kwargs: claims.append(
            "claimed"
        )
    )

    def lookup(_capability: object, *, consume_read: bool) -> SimpleNamespace:
        lookup_modes.append(consume_read)
        return state

    monkeypatch.setattr(audit, "_registered_capability_state", lookup)
    monkeypatch.setattr(
        audit,
        "_revalidate_registered_capability_state",
        lambda _state: registration,
    )
    return state, lookup_modes, claims


def test_lockbox_read_latches_exposure_after_claim_before_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _state, lookup_modes, claims = _inject_read_capability_state(
        tmp_path, monkeypatch
    )
    callbacks: list[str] = []
    counters = audit.AuditCounterState(
        _exposure_callback=lambda: callbacks.append("latched")
    )
    expected = tmp_path / audit.LOCKBOX_ARTIFACT_RELATIVE_PATH
    original_resolve = Path.resolve

    def fail_registered_resolve(path: Path, strict: bool = False) -> Path:
        if path == expected:
            assert counters.scientific_exposure_started is True
            raise OSError("injected after exposure latch")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_registered_resolve)

    with pytest.raises(OSError, match="after exposure latch"):
        audit.read_authorized_registered_manifest(
            cast(audit.RegisteredAuditCapability, object()),
            counters=counters,
        )

    assert claims == ["claimed"]
    assert callbacks == ["latched"]
    assert lookup_modes == [False, True]
    assert counters.scientific_exposure_started is True
    assert counters.snapshot()["lockbox_path_operations"] == 1


def test_lockbox_read_parse_failure_remains_post_exposure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _state, lookup_modes, claims = _inject_read_capability_state(
        tmp_path, monkeypatch
    )
    raw = b"{\"synthetic\":true}"
    artifact = tmp_path / audit.LOCKBOX_ARTIFACT_RELATIVE_PATH
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(raw)
    callbacks: list[str] = []
    counters = audit.AuditCounterState(
        _exposure_callback=lambda: callbacks.append("latched")
    )
    monkeypatch.setattr(audit, "LOCKBOX_ARTIFACT_SIZE_BYTES", len(raw))
    monkeypatch.setattr(
        audit, "LOCKBOX_ARTIFACT_SHA256", hashlib.sha256(raw).hexdigest()
    )
    monkeypatch.setattr(
        json,
        "loads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            json.JSONDecodeError("injected", "", 0)
        ),
    )

    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="JSON is invalid"):
        audit.read_authorized_registered_manifest(
            cast(audit.RegisteredAuditCapability, object()),
            counters=counters,
        )

    assert claims == ["claimed"]
    assert callbacks == ["latched"]
    assert lookup_modes == [False, True]
    assert counters.scientific_exposure_started is True
    assert counters.snapshot()["lockbox_path_operations"] == 4
    assert counters.snapshot()["lockbox_bytes_read"] == len(raw)


def test_exposure_marker_callback_failure_precedes_every_lockbox_path_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _state, lookup_modes, claims = _inject_read_capability_state(
        tmp_path, monkeypatch
    )

    def fail_marker() -> None:
        raise RuntimeError("injected marker publication failure")

    counters = audit.AuditCounterState(_exposure_callback=fail_marker)
    with pytest.raises(RuntimeError, match="marker publication"):
        audit.read_authorized_registered_manifest(
            cast(audit.RegisteredAuditCapability, object()),
            counters=counters,
        )

    assert claims == ["claimed"]
    assert lookup_modes == [False]
    assert counters.scientific_exposure_started is True
    assert counters.snapshot()["lockbox_path_operations"] == 0
    with pytest.raises(RuntimeError, match="previously failed"):
        counters.mark_scientific_exposure_started()


def test_registration_only_context_materializes_post_read_failure_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _synthetic_registered_rows()
    monkeypatch.setattr(
        audit,
        "_deterministic_environment_identity",
        lambda _provenance: {"test_environment": "registration-only"},
    )
    context = audit.prepare_registered_fallback_context_from_registration(
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        provenance=audit.EXPECTED_AUDIT_PROVENANCE,
        canonical_command_template=("registered",),
        registration_rows=rows,
        registration_preregistration={},
        registration_sha256="0" * 64,
        started_monotonic=time.monotonic(),
    )
    counters = audit.AuditCounterState()
    counters.mark_scientific_exposure_started()
    payload = audit.build_registered_evaluation_fallback(
        context,
        counters,
        OSError("injected lockbox read failure"),
        stage="registered_lockbox_read_failed",
    )
    records = cast(list[dict[str, Any]], payload["records"])

    assert len(records) == 140
    assert [record["row_id"] for record in records] == [
        row["row_id"] for row in rows
    ]
    assert all(
        cast(dict[str, Any], record["pipeline"])["status"] == "failed"
        for record in records[:60]
    )
    assert cast(dict[str, Any], payload["acceptance"])["acceptance_passes"] is False
    assert cast(list[dict[str, Any]], payload["finalization_failures"])[0] == {
        "error_type": "OSError",
        "stage": "registered_lockbox_read_failed",
    }
    assert audit.canonical_json_bytes(cast(audit.JsonValue, payload))


def test_fallback_resets_json_valid_but_authoritatively_invalid_retained_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _synthetic_registered_rows()
    monkeypatch.setattr(
        audit,
        "_deterministic_environment_identity",
        lambda _provenance: {"test_environment": "registration-only"},
    )
    context = audit.prepare_registered_fallback_context_from_registration(
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        provenance=audit.EXPECTED_AUDIT_PROVENANCE,
        canonical_command_template=("registered",),
        registration_rows=rows,
        registration_preregistration={},
        registration_sha256="0" * 64,
        started_monotonic=time.monotonic(),
    )
    context.accumulator[0]["positive_mechanism"] = True
    context.completed_indices.update({0, 1})
    context.accumulator_index = {}
    pristine = cast(
        list[dict[str, Any]], json.loads(context.registration_only_records_raw)
    )
    counters = audit.AuditCounterState(_scientific_exposure_started=True)

    payload = audit.build_registered_evaluation_fallback(
        context,
        counters,
        RuntimeError("injected later escape"),
        stage="injected_later_escape",
    )
    scientific_rows = cast(list[dict[str, Any]], payload["records"])
    failures = cast(list[dict[str, Any]], payload["finalization_failures"])

    assert scientific_rows[0]["positive_mechanism"] is False
    assert context.accumulator == pristine
    assert context.completed_indices == set()
    assert len(context.accumulator_index) == 140
    assert [failure["stage"] for failure in failures] == [
        "scientific_evidence_revalidation_failed",
        "injected_later_escape",
        "scientific_rows_not_completed",
    ]
    assert audit.validate_and_rederive_scientific_records(scientific_rows, rows) == (
        scientific_rows
    )


def test_completed_record_batch_is_atomic_when_its_late_row_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _synthetic_registered_rows()
    monkeypatch.setattr(
        audit,
        "_deterministic_environment_identity",
        lambda _provenance: {"test_environment": "registration-only"},
    )
    context = audit.prepare_registered_fallback_context_from_registration(
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        provenance=audit.EXPECTED_AUDIT_PROVENANCE,
        canonical_command_template=("registered",),
        registration_rows=rows,
        registration_preregistration={},
        registration_sha256="0" * 64,
        started_monotonic=time.monotonic(),
    )
    before = audit.canonical_json_bytes(cast(audit.JsonValue, context.accumulator))
    batch = list(
        audit._failed_scene_records(
            context.scenes[0],
            stage="synthetic_completed_batch",
            error=RuntimeError("synthetic"),
        )
    )
    batch[-1]["passes"] = True

    failures = audit._accumulate_completed_records(
        context.accumulator,
        batch,
        index=context.accumulator_index,
        completed_indices=context.completed_indices,
    )
    assert failures[0]["stage"] == "scientific_record_finalization_failed"
    assert audit.canonical_json_bytes(cast(audit.JsonValue, context.accumulator)) == before
    assert context.completed_indices == set()


def test_prior_valid_batch_survives_subsequent_invalid_batch_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _synthetic_registered_rows()
    monkeypatch.setattr(
        audit,
        "_deterministic_environment_identity",
        lambda _provenance: {"test_environment": "registration-only"},
    )
    context = audit.prepare_registered_fallback_context_from_registration(
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        provenance=audit.EXPECTED_AUDIT_PROVENANCE,
        canonical_command_template=("registered",),
        registration_rows=rows,
        registration_preregistration={},
        registration_sha256="0" * 64,
        started_monotonic=time.monotonic(),
    )
    first_batch = audit._failed_scene_records(
        context.scenes[0],
        stage="first_completed_batch",
        error=RuntimeError("synthetic"),
    )
    assert audit._accumulate_completed_records(
        context.accumulator,
        first_batch,
        index=context.accumulator_index,
        completed_indices=context.completed_indices,
    ) == ()
    after_first = audit.canonical_json_bytes(cast(audit.JsonValue, context.accumulator))
    completed_after_first = set(context.completed_indices)
    second_batch = list(
        audit._failed_scene_records(
            context.scenes[1],
            stage="second_invalid_batch",
            error=RuntimeError("synthetic"),
        )
    )
    second_batch[9]["reasons"] = []
    assert audit._accumulate_completed_records(
        context.accumulator,
        second_batch,
        index=context.accumulator_index,
        completed_indices=context.completed_indices,
    )
    assert audit.canonical_json_bytes(cast(audit.JsonValue, context.accumulator)) == (
        after_first
    )
    assert context.completed_indices == completed_after_first


def test_shipped_cli_rejects_arbitrary_lockbox_argument_before_reading(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("registered lockbox was read")
        ),
    )

    with pytest.raises(SystemExit) as error:
        audit_script.main(
            [
                "--permit-record",
                "primary.permit.json",
                "--permit-marker",
                "primary.available",
                "--output",
                "sealed/action_qbc_v5_scientific_payload.json",
                "--lockbox",
                "registered-do-not-read.json",
            ]
        )
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unrecognized arguments: --lockbox" in captured.err


def test_atomic_exclusive_publication_never_leaves_a_partial_final_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "scientific.json"
    raw = b'{"complete":true}'
    original_write = os.write
    calls = 0

    def fail_after_one_partial_write(descriptor: int, value: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            partial = max(1, len(value) // 2)
            return original_write(descriptor, value[:partial])
        raise OSError("injected payload write failure")

    monkeypatch.setattr(os, "write", fail_after_one_partial_write)
    with pytest.raises(OSError, match="injected payload write failure"):
        audit_script._write_exclusive(output, raw)

    assert not output.exists()
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))

    monkeypatch.setattr(os, "write", original_write)
    audit_script._write_exclusive(output, raw)
    assert output.read_bytes() == raw
    with pytest.raises(FileExistsError):
        audit_script._write_exclusive(output, b"replacement")
    assert output.read_bytes() == raw
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


@pytest.mark.parametrize("failure_stage", ["zero_write", "file_fsync", "link"])
def test_atomic_publication_precommit_failures_leave_no_final_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    output = tmp_path / "scientific.json"
    raw = b'{"complete":true}'
    if failure_stage == "zero_write":
        monkeypatch.setattr(os, "write", lambda *_args: 0)
        expected = "made no progress"
    elif failure_stage == "file_fsync":
        monkeypatch.setattr(
            os,
            "fsync",
            lambda *_args: (_ for _ in ()).throw(OSError("injected fsync failure")),
        )
        expected = "fsync failure"
    else:
        monkeypatch.setattr(
            os,
            "link",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("injected link failure")
            ),
        )
        expected = "link failure"

    with pytest.raises(OSError, match=expected):
        audit_script._write_exclusive(output, raw)
    assert not output.exists()
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


def test_atomic_publication_directory_commit_failure_leaves_only_complete_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "scientific.json"
    raw = b'{"complete":true}'
    monkeypatch.setattr(
        audit_script,
        "_fsync_parent_directory",
        lambda _directory: (_ for _ in ()).throw(
            OSError("injected directory commit failure")
        ),
    )

    with pytest.raises(OSError, match="directory commit failure"):
        audit_script._write_exclusive(output, raw)
    assert output.read_bytes() == raw
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


def test_sealed_cli_requires_exact_registered_command_tail(tmp_path: Path) -> None:
    registration = audit.load_audit_registration_admin(Path("."))
    permit_directory = registration.CANONICAL_EXTERNAL_PERMIT_DIRECTORY
    del tmp_path
    output = Path(
        registration._registered_scientific_output_paths(permit_directory)["primary"]
    )
    realized = registration.realized_audit_command(
        permit_directory,
        "primary",
        output,
    )
    script_index = realized.index("scripts/audit_action_qbc_lockbox.py")
    exact_tail = realized[script_index + 1 :]

    assert audit_script._require_canonical_invocation(
        exact_tail,
        registration=registration,
        permit_record=permit_directory / "primary.permit.json",
        permit_marker=permit_directory / "primary.available",
        output=output.resolve(),
    ) == realized
    tampered = list(exact_tail)
    tampered[1] = str(Path("elsewhere").resolve())
    with pytest.raises(RuntimeError, match="exact registered command"):
        audit_script._require_canonical_invocation(
            tampered,
            registration=registration,
            permit_record=permit_directory / "primary.permit.json",
            permit_marker=permit_directory / "primary.available",
            output=output.resolve(),
        )


def _launcher_runtime_fixture(
    tmp_path: Path,
) -> tuple[Path, audit_script._PythonRuntimeIdentity]:
    repository = tmp_path / "repository"
    executable = repository / ".venv" / "bin" / "python3"
    script = repository / "scripts" / "audit_action_qbc_lockbox.py"
    package = repository / "src" / "arc3_voi"
    origins = (
        ("arc3_voi", package / "__init__.py"),
        ("arc3_voi.action_qbc_audit", package / "action_qbc_audit.py"),
        ("arc3_voi.config", package / "config.py"),
    )
    for path in (executable, script, *(origin for _, origin in origins)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture\n")
    identity = audit_script._PythonRuntimeIdentity(
        isolated=1,
        dont_write_bytecode_flag=1,
        dont_write_bytecode_global=True,
        executable=executable,
        script_origin=script,
        argv0=script,
        current_directory=repository,
        project_module_origins=tuple((name, str(origin)) for name, origin in origins),
    )
    return repository, identity


def test_launcher_rejects_nonisolated_or_bytecode_writing_python(
    tmp_path: Path,
) -> None:
    repository, identity = _launcher_runtime_fixture(tmp_path)

    audit_script._require_python_runtime_identity(repository, identity=identity)
    with pytest.raises(RuntimeError, match="isolated mode"):
        audit_script._require_python_runtime_identity(
            repository,
            identity=replace(identity, isolated=0),
        )
    with pytest.raises(RuntimeError, match="isolated mode"):
        audit_script._require_python_runtime_identity(
            repository,
            identity=replace(identity, dont_write_bytecode_global=False),
        )


def test_launcher_rejects_preexisting_cached_bytecode(tmp_path: Path) -> None:
    repository, identity = _launcher_runtime_fixture(tmp_path)
    cache = repository / "src" / "arc3_voi" / "__pycache__"
    cache.mkdir()
    (cache / "config.cpython-312.pyc").write_bytes(b"cached")

    with pytest.raises(RuntimeError, match="cached Python bytecode"):
        audit_script._require_python_runtime_identity(repository, identity=identity)


def test_launcher_rejects_stale_project_module_origin(tmp_path: Path) -> None:
    repository, identity = _launcher_runtime_fixture(tmp_path)
    stale = tmp_path / "stale-package" / "arc3_voi" / "config.py"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale\n")
    origins = tuple(
        (name, str(stale) if name == "arc3_voi.config" else origin)
        for name, origin in identity.project_module_origins
    )

    with pytest.raises(RuntimeError, match="outside the worktree source"):
        audit_script._require_python_runtime_identity(
            repository,
            identity=replace(identity, project_module_origins=origins),
        )


def test_launcher_rejects_direct_python_parent_and_attests_exact_uv_prefix(
    tmp_path: Path,
) -> None:
    repository, _identity = _launcher_runtime_fixture(tmp_path)
    realized = (
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
    )
    uv_parent = audit_script._ParentProcessIdentity(
        executable=Path("/usr/bin/uv"),
        current_directory=repository,
        argv=("/usr/bin/uv", *realized[1:]),
    )

    audit_script._require_uv_parent_attestation(
        repository,
        realized,
        identity=uv_parent,
    )
    with pytest.raises(RuntimeError, match="not launched by the uv executable"):
        audit_script._require_uv_parent_attestation(
            repository,
            realized,
            identity=replace(
                uv_parent,
                executable=Path("/usr/bin/python3"),
                argv=("python3", *realized[4:]),
            ),
        )
    with pytest.raises(RuntimeError, match="uv parent argv differs"):
        audit_script._require_uv_parent_attestation(
            repository,
            realized,
            identity=replace(uv_parent, argv=("uv", "run", "python3")),
        )


def _production_identity_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, tuple[str, ...], SimpleNamespace]:
    repository = tmp_path / "production-identity"
    executable = repository / ".venv" / "bin" / "python3"
    script = repository / "scripts" / "audit_action_qbc_lockbox.py"
    admin = repository / "scripts" / "build_action_qbc_audit_registration.py"
    package = repository / "src" / "arc3_voi"
    origins = {
        "arc3_voi": package / "__init__.py",
        "arc3_voi.action_qbc_audit": package / "action_qbc_audit.py",
        "arc3_voi.config": package / "config.py",
    }
    for path in (executable, script, admin, *origins.values()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic production identity\n")
    permit_directory = tmp_path / "production-permits"
    permit_directory.mkdir()
    output = tmp_path / "results" / "sealed" / "action_qbc_v5_scientific_payload.json"
    command = (
        *audit._REGISTERED_LAUNCH_PREFIX,
        "--repository-root",
        ".",
        "--registration",
        audit.AUDIT_REGISTRATION_RELATIVE_PATH,
        "--permit-record",
        str(permit_directory / "primary.permit.json"),
        "--permit-marker",
        str(permit_directory / "primary.available"),
        "--output",
        str(output),
    )
    modules = {
        "__main__": SimpleNamespace(__file__=str(script)),
        **{
            name: SimpleNamespace(__file__=str(origin))
            for name, origin in origins.items()
        },
        "_arc3_action_qbc_audit_registration_admin": SimpleNamespace(
            __file__=str(admin)
        ),
    }
    fake_sys = SimpleNamespace(
        argv=[str(script), *command[len(audit._REGISTERED_LAUNCH_PREFIX) :]],
        dont_write_bytecode=True,
        executable=str(executable),
        flags=SimpleNamespace(isolated=1, safe_path=1, dont_write_bytecode=1),
        modules=modules,
        orig_argv=[
            "python3",
            "-I",
            "-B",
            *command[len(audit._REGISTERED_LAUNCH_PREFIX) - 1 :],
        ],
    )
    monkeypatch.setattr(audit, "sys", fake_sys)
    monkeypatch.setattr(
        audit,
        "_verified_registered_launcher_environment",
        lambda _root, _command: (
            {
                "launcher_distribution_versions": dict(
                    audit.REGISTERED_AUDIT_DISTRIBUTIONS
                ),
                "launcher_environment_sha256": "e" * 64,
                "launcher_uv_version": "0.11.28",
            },
            222,
            333,
        ),
    )
    monkeypatch.setattr(audit, "_process_start_time_ticks", lambda _pid: 444)
    monkeypatch.chdir(repository)
    return repository, command, fake_sys


def test_production_launch_identity_signature_and_orig_argv_are_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert tuple(inspect.signature(audit._verified_registered_launch_identity).parameters) == (
        "repository",
        "exact_command",
    )
    repository, command, fake_sys = _production_identity_fixture(
        tmp_path, monkeypatch
    )
    identity, _pid, _ppid, _process_start, _parent_start = (
        audit._verified_registered_launch_identity(repository, command)
    )
    assert identity["launcher_uv_version"] == "0.11.28"
    fake_sys.orig_argv[0] = str(repository / ".venv" / "bin" / "python3")
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="original Python argv"):
        audit._verified_registered_launch_identity(repository, command)


def test_production_launch_identity_rejects_module_name_origin_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, command, fake_sys = _production_identity_fixture(
        tmp_path, monkeypatch
    )
    audit._verified_registered_launch_identity(repository, command)
    fake_sys.modules["arc3_voi.config"].__file__ = fake_sys.modules[
        "arc3_voi.action_qbc_audit"
    ].__file__
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="origin/name mapping"):
        audit._verified_registered_launch_identity(repository, command)


def _python_environment_inventory_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, SimpleNamespace, list[SimpleNamespace], Path]:
    repository = tmp_path / "environment-repository"
    venv = repository / ".venv"
    site_packages = venv / "lib" / "python3.12" / "site-packages"
    project_source = repository / "src"
    executable = venv / "bin" / "python3"
    for directory in (site_packages, project_source, executable.parent):
        directory.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"synthetic executable")
    editable_pth = site_packages / "_editable_impl_arc3_crosslevel_voi.pth"
    editable_pth.write_bytes(
        str(project_source.resolve(strict=True)).encode("utf-8") + b"\n"
    )
    (site_packages / "_virtualenv.pth").write_bytes(b"import _virtualenv")
    virtualenv_raw = b"v" * 5_246
    virtualenv_module_path = site_packages / "_virtualenv.py"
    virtualenv_module_path.write_bytes(virtualenv_raw)
    (venv / "pyvenv.cfg").write_text(
        "include-system-site-packages = false\nuv = 0.11.28\n",
        encoding="utf-8",
    )
    real_version_info = sys.version_info
    fake_sys = SimpleNamespace(
        base_prefix="/usr/local",
        executable=str(executable),
        exec_prefix=str(venv),
        modules={
            "_virtualenv": SimpleNamespace(__file__=str(virtualenv_module_path))
        },
        path=[str(site_packages), str(project_source), "/usr/local/lib/python3.12"],
        prefix=str(venv),
        version_info=real_version_info,
    )

    def distribution(name: str, version: str) -> SimpleNamespace:
        return SimpleNamespace(
            locate_file=lambda _relative: site_packages,
            metadata={"Name": name},
            read_text=lambda filename: (
                json.dumps(
                    {
                        "dir_info": {"editable": True},
                        "url": repository.resolve(strict=True).as_uri(),
                    }
                )
                if name == "arc3-crosslevel-voi" and filename == "direct_url.json"
                else None
            ),
            version=version,
        )

    distributions = [
        distribution(name, version)
        for name, version in audit.REGISTERED_AUDIT_DISTRIBUTIONS.items()
    ]
    monkeypatch.setattr(audit, "sys", fake_sys)
    monkeypatch.setattr(site, "ENABLE_USER_SITE", False)
    monkeypatch.setattr(
        site, "getsitepackages", lambda: [str(site_packages)]
    )
    monkeypatch.setattr(sysconfig, "get_path", lambda _name: str(site_packages))
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda **_kwargs: tuple(distributions),
    )
    monkeypatch.setattr(
        audit,
        "REGISTERED_AUDIT_VIRTUALENV_MODULE_SHA256",
        hashlib.sha256(virtualenv_raw).hexdigest(),
    )
    monkeypatch.setattr(
        audit,
        "_verified_python_executable_identity",
        lambda _path: {
            "python_executable_resolved_path_sha256": "1" * 64,
            "python_executable_sha256": "2" * 64,
            "python_executable_symlink_target_sha256": "3" * 64,
            "python_intermediate_symlink_target_sha256": "4" * 64,
        },
    )
    return repository, fake_sys, distributions, editable_pth


def test_python_environment_inventory_rejects_hooks_pth_and_distribution_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, fake_sys, distributions, editable_pth = (
        _python_environment_inventory_fixture(tmp_path, monkeypatch)
    )
    identity = audit._verified_python_environment_identity(repository)
    assert identity["distribution_versions"] == dict(
        audit.REGISTERED_AUDIT_DISTRIBUTIONS
    )
    assert identity["uv_virtualenv_pth_sha256"] == (
        audit.REGISTERED_AUDIT_VIRTUALENV_PTH_SHA256
    )

    original_editable = editable_pth.read_bytes()
    editable_pth.write_bytes(b"import os")
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="sole project-source"):
        audit._verified_python_environment_identity(repository)
    editable_pth.write_bytes(original_editable)

    extra_pth = editable_pth.parent / "extra.pth"
    extra_pth.write_text("/tmp/foreign\n", encoding="utf-8")
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="pth inventory"):
        audit._verified_python_environment_identity(repository)
    extra_pth.unlink()

    fake_sys.modules["sitecustomize"] = SimpleNamespace()
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="customization module"):
        audit._verified_python_environment_identity(repository)
    fake_sys.modules.pop("sitecustomize")

    distributions[1].version = "0.0.0"
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="distribution inventory"):
        audit._verified_python_environment_identity(repository)


@pytest.mark.skipif(os.name == "nt", reason="uv's symlink chain is a POSIX contract")
def test_python3_executable_symlink_chain_is_bound_exactly(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "managed" / "python3.12"
    binary.parent.mkdir()
    binary.write_bytes(b"managed python")
    bin_directory = tmp_path / ".venv" / "bin"
    bin_directory.mkdir(parents=True)
    (bin_directory / "python").symlink_to(binary)
    python3 = bin_directory / "python3"
    python3.symlink_to("python")
    python312 = bin_directory / "python3.12"
    python312.symlink_to("python")

    identity = audit._verified_python_executable_identity(python3)
    assert identity["python_executable_sha256"] == hashlib.sha256(
        b"managed python"
    ).hexdigest()
    assert identity["python_versioned_symlink_target_sha256"] == hashlib.sha256(
        b"python"
    ).hexdigest()
    python3.unlink()
    python3.symlink_to(binary)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="symlink chain differs"):
        audit._verified_python_executable_identity(python3)
    python3.unlink()
    python3.symlink_to("python")
    python312.unlink()
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="chain cannot be read"):
        audit._verified_python_executable_identity(python3)
    python312.symlink_to(binary)
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="symlink chain differs"):
        audit._verified_python_executable_identity(python3)


def test_actual_uv_executable_version_is_exactly_0_11_28(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uv_executable = tmp_path / "uv"
    uv_executable.write_bytes(b"synthetic uv binary")

    def completed(version: bytes) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            (str(uv_executable), "--version"),
            0,
            version,
            b"",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: completed(b"uv 0.11.28\n"),
    )
    identity = audit._verified_uv_executable_identity(uv_executable)
    assert identity["uv_version"] == "0.11.28"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: completed(b"uv 0.11.29\n"),
    )
    with pytest.raises(audit.RegisteredAuditNotAuthorized, match="version is invalid"):
        audit._verified_uv_executable_identity(uv_executable)


@pytest.mark.skipif(
    platform.system() != "Linux"
    or os.environ.get("ARC3_RUN_CANONICAL_UV_ENV_TEST") != "1",
    reason="run explicitly in the fresh uv 0.11.28 no-dev .venv clone",
)
def test_fresh_native_uv_environment_matches_the_production_verifier() -> None:
    repository = Path.cwd().resolve(strict=True)
    code = "\n".join(
        (
            "import json, os, sys",
            "from pathlib import Path",
            "from arc3_voi.action_qbc_audit import (",
            "    _verified_python_environment_identity,",
            "    _verified_uv_executable_identity,",
            ")",
            "assert sys.orig_argv[0] == 'python3'",
            "assert sys.orig_argv[1:4] == ['-I', '-B', '-c']",
            "root = Path.cwd().resolve(strict=True)",
            "python_identity = _verified_python_environment_identity(root)",
            "uv = (Path('/proc') / str(os.getppid()) / 'exe').resolve(strict=True)",
            "uv_identity = _verified_uv_executable_identity(uv)",
            "print(json.dumps({'python': python_identity, 'uv': uv_identity}, sort_keys=True))",
        )
    )
    completed = subprocess.run(
        (
            "uv",
            "run",
            "--frozen",
            "--no-sync",
            "python3",
            "-I",
            "-B",
            "-c",
            code,
        ),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    observed = cast(dict[str, Any], json.loads(completed.stdout))
    assert cast(dict[str, Any], observed["python"])["distribution_versions"] == dict(
        audit.REGISTERED_AUDIT_DISTRIBUTIONS
    )
    assert cast(dict[str, Any], observed["uv"])["uv_version"] == "0.11.28"


def test_cli_exposure_classification_is_conservative_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = RuntimeError("host-specific path C:/private/should-not-escape")
    marker = tmp_path / "scientific-exposure-started"
    consumed = {"scientific_exposure_marker_path": str(marker)}
    before = audit.AuditCounterState()
    assert audit_script._classify_exposure(None, None) is (
        audit_script._ExposureState.BEFORE
    )
    assert audit_script._classify_exposure(consumed, before) is (
        audit_script._ExposureState.BEFORE
    )
    marker.write_bytes(b"durable")
    assert audit_script._classify_exposure(consumed, before) is (
        audit_script._ExposureState.AFTER
    )
    marker.unlink()
    after = audit.AuditCounterState(_scientific_exposure_started=True)
    assert audit_script._classify_exposure(consumed, after) is (
        audit_script._ExposureState.AFTER
    )

    original_lstat = Path.lstat

    def fail_marker_stat(path: Path) -> os.stat_result:
        if path == marker:
            raise PermissionError("injected uncertain marker state")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fail_marker_stat)
    assert audit_script._classify_exposure(consumed, before) is (
        audit_script._ExposureState.UNKNOWN
    )
    assert audit_script._cli_failure_record(
        secret,
        exposure_state=audit_script._ExposureState.AFTER,
    ) == {
        "error_type": "RuntimeError",
        "stage": "sealed_audit_post_exposure",
    }
    unknown = audit_script._cli_failure_record(
        secret,
        exposure_state=audit_script._ExposureState.UNKNOWN,
    )
    assert unknown == {
        "error_type": "RuntimeError",
        "stage": "sealed_audit_exposure_unknown",
    }
    before_failure = audit_script._cli_failure_record(
        secret,
        exposure_state=audit_script._ExposureState.BEFORE,
    )
    assert "message" in before_failure
    assert "private" not in json.dumps(unknown)


def test_deadline_covers_serialization_and_disarms_only_before_publication() -> None:
    secret = RuntimeError("host-specific path C:/private/should-not-escape")
    assert audit_script._ledger_failure_record(secret) == {
        "error_type": "RuntimeError",
        "stage": "execution_ledger_append_failed",
    }
    assert "private" not in json.dumps(audit_script._ledger_failure_record(secret))
    source = inspect.getsource(audit_script.main)
    assert source.index("_install_hard_deadline") < source.index(
        "issue_registered_audit_capability"
    ) < source.index("read_authorized_registered_manifest")
    evaluation = source.index("payload = evaluate_registered_manifest")
    serialization = source.index("raw = canonical_json_bytes(payload)", evaluation)
    deadline_disarmed = source.index("_set_linux_real_timer(0.0)", serialization)
    publication = source.index("_write_exclusive(output, raw)", deadline_disarmed)
    assert evaluation < serialization < deadline_disarmed < publication


def test_non_linux_platform_fails_before_repository_path_resolution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("repository path was resolved before platform admission")
        ),
    )
    exit_status = audit_script.main(
        [
            "--repository-root",
            "must-not-resolve",
            "--permit-record",
            "primary.permit.json",
            "--permit-marker",
            "primary.available",
            "--output",
            "scientific.json",
        ]
    )
    assert exit_status == 1
    assert "canonical sealed audit execution requires Linux" in capsys.readouterr().err


def test_launcher_environment_failure_precedes_permit_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumed = False

    def consume(**_kwargs: object) -> None:
        nonlocal consumed
        consumed = True

    registration = SimpleNamespace(
        consume_audit_start_permit=consume,
        require_external_scientific_output_path=lambda _root, output: Path(output),
    )
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(audit_script, "_install_hard_deadline", lambda _started: None)
    monkeypatch.setattr(audit_script, "_set_linux_real_timer", lambda _seconds: None)
    monkeypatch.setattr(audit_script, "_require_python_runtime_identity", lambda _root: None)
    monkeypatch.setattr(
        audit_script, "load_audit_registration_admin", lambda _root: registration
    )
    monkeypatch.setattr(audit_script, "_require_module_origin", lambda *_args: None)
    monkeypatch.setattr(
        audit_script,
        "_require_canonical_invocation",
        lambda *_args, **_kwargs: audit._REGISTERED_LAUNCH_PREFIX,
    )
    monkeypatch.setattr(audit_script, "_require_uv_parent_attestation", lambda *_args: None)
    monkeypatch.setattr(
        audit_script,
        "require_registered_launcher_environment",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("invalid base environment")),
    )

    assert audit_script.main(
        [
            "--repository-root",
            str(tmp_path),
            "--permit-record",
            "primary.permit.json",
            "--permit-marker",
            "primary.available",
            "--output",
            str(tmp_path / "scientific.json"),
        ]
    ) == 1
    assert consumed is False
    source = inspect.getsource(audit_script.main)
    assert source.index("require_registered_launcher_environment") < source.index(
        "consume_audit_start_permit"
    )


def test_open_resource_counter_schema_is_strictly_zero() -> None:
    counters = audit.OPEN_FIXTURE_RESOURCE_COUNTERS.as_json()

    assert counters
    assert set(counters.values()) == {0}
    assert counters["lockbox_path_operations"] == 0
    assert counters["registered_scenes_read"] == 0
    assert counters["planner_calls"] == 0
    assert counters["model_calls"] == 0
    assert counters["environment_actions"] == 0
    assert tuple(counters) == audit.AUDIT_RESOURCE_COUNTER_FIELDS
    assert set(audit.AUDIT_RESOURCE_COUNTER_INVENTORY) == set(counters)
    expected_schema_hash = hashlib.sha256(
        json.dumps(
            {
                "fields": list(audit.AUDIT_RESOURCE_COUNTER_FIELDS),
                "increment_contract": dict(audit.AUDIT_RESOURCE_COUNTER_INVENTORY),
                "schema_version": 1,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert expected_schema_hash == audit.AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256
    with pytest.raises(ValueError, match="model_calls must remain zero"):
        audit.ResourceCounters(model_calls=1)


def test_concentration_one_control_is_ineligible() -> None:
    result = _evaluate(audit.AuditControl.CONCENTRATION_ONE)
    row = _row(result, A1)

    assert row["outcome_concentration"] == 1.0
    assert row["eligible"] is False
    assert result["selection"]["x_decision"]["mode"] == "exploit"


def test_exact_point_eight_control_is_strictly_ineligible_despite_positive_utility() -> None:
    result = _evaluate(audit.AuditControl.CONCENTRATION_THRESHOLD)
    row = _row(result, A3)

    assert row["outcome_concentration"] == pytest.approx(0.8)
    assert row["x_utility"] > 0.0
    assert row["eligible"] is False
    assert result["selection"]["x_decision"]["gate_reason"] == (
        "no_disagreement_eligible_action"
    )


def test_zero_evsi_control_stays_eligible_but_has_nonpositive_utility() -> None:
    result = _evaluate(audit.AuditControl.EVSI_ZERO)
    row = _row(result, A3)

    assert row["outcome_concentration"] == 0.5
    assert row["eligible"] is True
    assert row["evsi"] == 0.0
    assert result["selection"]["x_decision"]["gate_reason"] == "nonpositive_utility"


def test_point_zero_four_nine_evsi_has_no_hidden_materiality_cutoff() -> None:
    result = _evaluate(audit.AuditControl.EVSI_0049)
    row = _row(result, A3)

    assert row["evsi"] == pytest.approx(0.049)
    assert row["x_utility"] > 0.0
    assert row["x_selected"] is True
    assert result["selection"]["x_decision"]["mode"] == "probe"


def test_high_concentration_positive_utility_is_filtered_before_ranking() -> None:
    result = _evaluate(audit.AuditControl.HIGH_CONCENTRATION_POSITIVE_UTILITY)
    row = _row(result, A3)

    assert row["outcome_concentration"] == pytest.approx(0.9)
    assert row["x_utility"] > 0.0
    assert row["eligible"] is False
    assert row["x_rank"] is None
    assert result["selection"]["x_decision"]["mode"] == "exploit"


def test_probe_cap_control_forces_exploitation() -> None:
    result = _evaluate(audit.AuditControl.PROBE_CAP)

    assert result["selection"]["x_decision"]["mode"] == "exploit"
    assert result["selection"]["x_decision"]["gate_reason"] == "level_probe_cap_reached"
    assert not any(row["x_selected"] for row in result["selection"]["rows"])


def test_catastrophe_control_charges_exact_weighted_mass() -> None:
    result = _evaluate(audit.AuditControl.CATASTROPHE)
    row = _row(result, A3)

    assert row["evsi"] == pytest.approx(1.0)
    assert row["catastrophe_mass"] == pytest.approx(0.5)
    assert row["x_utility"] == pytest.approx(-0.5)
    assert result["selection"]["x_decision"]["mode"] == "exploit"


def test_final_level_control_makes_m_and_x_identical() -> None:
    result = _evaluate(audit.AuditControl.FINAL_LEVEL)
    selection = result["selection"]

    assert selection["m_decision"] == selection["x_decision"]
    assert all(row["m_utility"] == row["x_utility"] for row in selection["rows"])
    assert all(row["m_selected"] == row["x_selected"] for row in selection["rows"])


def test_mechanism_gate_requires_distinct_environment_actions() -> None:
    first = _prediction(1)
    second = _prediction(2)
    snapshot = _snapshot(
        (A1, A2, A3),
        (0.25, 0.25, 0.25, 0.25),
        {
            A1: (first, first, first, first),
            A2: (first, first, second, second),
            A3: (first, second, first, second),
        },
        {
            A1: (0.05, 0.05, 0.05, 0.05),
            A2: (0.0, 0.0, 0.1, 0.1),
            A3: (0.1, 0.1, 0.0, 0.0),
        },
    )
    selection = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )

    assert audit._mechanism_gate(
        selection,
        selected_evsi_minimum_margin=0.0,
    )["passes"] is True
    same_action = replace(
        selection,
        m_decision=replace(
            selection.m_decision,
            action=selection.x_decision.action,
        ),
    )
    rejected = audit._mechanism_gate(
        same_action,
        selected_evsi_minimum_margin=0.0,
    )

    assert rejected["environment_action_contrast"] is False
    assert rejected["passes"] is False
    assert "M and X selected the same environment action" in cast(
        list[str], rejected["reasons"]
    )


def test_tie_control_preserves_maximizer_set_and_uses_stable_candidate_order() -> None:
    case = _case(audit.AuditControl.TIE_BEHAVIOR)
    forward = cast(dict[str, Any], audit.evaluate_open_fixture(case))
    reverse = cast(
        dict[str, Any],
        audit.evaluate_open_fixture(
            audit.OpenAuditCase(
                case.control,
                audit.reverse_candidate_order(case.snapshot),
                case.cross_level_multiplier,
                case.probes_used,
            )
        ),
    )

    forward_x = forward["selection"]["x_decision"]
    reverse_x = reverse["selection"]["x_decision"]
    assert forward_x["action"]["kind"] == int(A3.kind)
    assert reverse_x["action"]["kind"] == int(A4.kind)
    assert {item["kind"] for item in forward_x["utility_maximizers"]} == {
        int(A3.kind),
        int(A4.kind),
    }
    assert {item["kind"] for item in reverse_x["utility_maximizers"]} == {
        int(A3.kind),
        int(A4.kind),
    }


def test_complete_open_payload_is_canonical_zero_resource_and_input_order_invariant() -> None:
    cases = [_case(control) for control in audit.REQUIRED_OPEN_CONTROL_ORDER]

    forward = audit.build_open_scientific_payload(cases)
    reverse = audit.build_open_scientific_payload(tuple(reversed(cases)))

    assert forward == reverse
    assert [case["control"] for case in cast(list[dict[str, Any]], forward["cases"])] == [
        control.value for control in audit.REQUIRED_OPEN_CONTROL_ORDER
    ]
    assert set(cast(dict[str, int], forward["resource_counters"]).values()) == {0}
    assert forward["authorization"] == {
        "enabled": False,
        "pending_freeze_fields": list(audit.PENDING_FREEZE_FIELDS),
        "state": "sealed-audit-capability-required-runtime-v5-disabled",
    }
    serialized = audit.canonical_json_bytes(forward)
    assert not serialized.endswith(b"\n")
    assert audit.canonical_sha256(forward) == audit.canonical_sha256(reverse)


def test_complete_payload_rejects_missing_and_duplicate_controls() -> None:
    one = _case(audit.AuditControl.EVSI_ZERO)

    with pytest.raises(ValueError, match="control set mismatch"):
        audit.build_open_scientific_payload((one,))
    with pytest.raises(ValueError, match="duplicate audit control"):
        audit.build_open_scientific_payload((one, one), require_complete_controls=False)


def test_preregistered_controls_exercise_exact_implementation_derived_call_ledger() -> None:
    counters = audit.AuditCounterState()

    records = audit.evaluate_preregistered_controls(counters)

    assert tuple(record["name"] for record in records) == audit.PREREGISTERED_CONTROL_ORDER
    assert len(records) == 20
    assert all(record["passes"] is True for record in records)
    assert tuple(audit.PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER) == (
        audit.PREREGISTERED_CONTROL_ORDER
    )
    assert sum(audit.PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER.values()) == 19
    assert counters.snapshot()["pure_selector_control_calls"] == 19
    assert counters.snapshot()["pure_selector_calls"] == 19


def test_preregistered_controls_continue_after_one_post_exposure_row_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counters = audit.AuditCounterState()
    counters.mark_scientific_exposure_started()
    original = audit.ACTION_QBC_AUDIT_SELECTOR
    calls = 0

    def fail_third_selector(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("injected one-row selector failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(audit, "ACTION_QBC_AUDIT_SELECTOR", fail_third_selector)
    records = audit.evaluate_preregistered_controls(
        counters,
        continue_after_failure=True,
    )

    assert len(records) == 20
    assert records[2]["passes"] is False
    assert cast(dict[str, Any], records[2]["failure"])["stage"] == (
        "control_row_failed"
    )
    assert records[3]["passes"] is True
    assert records[-1]["passes"] is True
    assert counters.snapshot()["pure_selector_control_calls"] == 19
    assert counters.snapshot()["pure_selector_calls"] == 19


def test_controller_trace_equality_rejects_same_length_tampered_candidate_rows() -> None:
    selection = select_action_conditional_qbc(
        _split_snapshot(cross_cost=2.0, probe_cost=4.0),
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=3,
    )
    authoritative = selection.x_decision
    probe_row = next(
        row for row in selection.rows if row.action == authoritative.probe_candidate
    )
    diagnostics: dict[str, Any] = {
        "action_qbc_candidate_rows": json.dumps(
            audit._controller_candidate_rows(selection), separators=(",", ":")
        ),
        "m_decision_action": audit._controller_action_key(selection.m_decision.action),
        "m_decision_mode": selection.m_decision.mode,
        "m_utility_maximizer_actions": json.dumps(
            [
                audit._controller_action_record(action)
                for action in selection.m_utility_maximizers
            ],
            separators=(",", ":"),
        ),
        "probe_candidate_action": audit._controller_action_key(
            cast(Action, authoritative.probe_candidate)
        ),
        "probe_cap": 3,
        "probe_catastrophe_probability": probe_row.catastrophe_mass,
        "probe_count_before": 0,
        "probe_evsi": probe_row.evsi,
        "probe_gate_reason": authoritative.gate_reason,
        "probe_selected": True,
        "probe_utility": probe_row.x_utility,
        "x_decision_action": audit._controller_action_key(selection.x_decision.action),
        "x_decision_mode": selection.x_decision.mode,
        "x_utility_maximizer_actions": json.dumps(
            [
                audit._controller_action_record(action)
                for action in selection.x_utility_maximizers
            ],
            separators=(",", ":"),
        ),
    }
    audit._require_controller_trace_equal(
        decision_action=authoritative.action,
        decision_mode=authoritative.mode,
        decision_score=authoritative.score,
        diagnostics=diagnostics,
        selection=selection,
        variant=Variant.CROSS_LEVEL,
    )
    tampered = json.loads(diagnostics["action_qbc_candidate_rows"])
    tampered[0]["evsi"] += 1.0
    diagnostics["action_qbc_candidate_rows"] = json.dumps(
        tampered, separators=(",", ":")
    )

    with pytest.raises(RuntimeError, match="diagnostics differ"):
        audit._require_controller_trace_equal(
            decision_action=authoritative.action,
            decision_mode=authoritative.mode,
            decision_score=authoritative.score,
            diagnostics=diagnostics,
            selection=selection,
            variant=Variant.CROSS_LEVEL,
        )


def test_grounding_counters_increment_only_for_attempted_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = generate_open_scene("homologue", 0x1020304050607080)
    base = cast(dict[str, Any], scene["base_scene"])
    history = audit._scene_history(base, base)
    rows = audit._source_rows(instantiate_structured_priors(history))
    counters = audit.AuditCounterState()
    calls = 0

    def fail_third_grounding(*_args: object, **_kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("injected partial grounding failure")
        return object()

    monkeypatch.setattr(audit, "evaluate_program_grounding", fail_third_grounding)
    with pytest.raises(RuntimeError, match="partial grounding"):
        audit._evaluate_source_programs_counted(
            rows,
            history,
            (A1, A2, A3),
            config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
            counters=counters,
        )

    assert calls == 3
    assert counters.snapshot()["grounding_evaluations"] == 3
    assert counters.snapshot()["transient_worker_starts"] == 3
    assert counters.snapshot()["total_worker_starts"] == 3


def test_open_compiler_pipeline_and_registered_order_tables_use_exact_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = generate_open_scene("homologue", 0x1020304050607080)
    base = cast(dict[str, Any], scene["base_scene"])
    counters = audit.AuditCounterState()
    result = audit.evaluate_compiler_planner_snapshot(
        audit._scene_history(base, base),
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=counters,
        exercise_controllers=True,
    )
    maps = tuple(
        cast(Mapping[str, Any], item) for item in build_order_transform_maps()
    )
    order_records = audit.evaluate_order_transforms(
        result,
        counters=counters,
        order_transform_maps=maps,
        base_positive=audit._mechanism_gate(result.selection)["passes"] is True,
    )

    assert len(result.program_rows) == len(result.snapshot.hypothesis_ids) == 4
    assert audit._structural_gate(result, require_linux_memory=False)["passes"] is True
    assert [row["variant"] for row in result.controller_rows] == ["M", "X"]
    assert tuple(row["name"] for row in order_records) == audit.ORDER_TRANSFORM_NAMES
    assert all("selection" in row for row in order_records)
    assert any(
        "hypothesis_roles" in cell
        for row in cast(list[dict[str, Any]], order_records[-1]["transformed_cells"])
        for cell in row["cells"]
    )
    assert order_records[-1]["policy_input_transform_applied"] is True
    expected_nonzero = {
        "candidate_builder_calls": 1,
        "compiled_programs": 4,
        "compiler_calls": 1,
        "completed_planning_snapshots": 1,
        "controller_calls": 2,
        "controller_snapshot_replays": 2,
        "grounding_evaluations": 4,
        "hypothesis_pool_constructions": 1,
        "persistent_worker_starts": 4,
        "planner_calls": 1,
        "pure_selector_calls": 8,
        "pure_selector_scene_order_calls": 8,
        "total_worker_starts": 8,
        "transient_worker_starts": 4,
    }
    observed_nonzero = {
        name: value for name, value in counters.snapshot().items() if value
    }
    assert observed_nonzero == expected_nonzero
    assert counters.scientific_exposure_started is True

    same_action_selection = replace(
        result.selection,
        m_decision=replace(
            result.selection.m_decision,
            action=result.selection.x_decision.action,
        ),
    )
    same_action_result = replace(result, selection=same_action_selection)
    same_action_v4 = audit._v4_counterfactual(
        same_action_result,
        structural_passes=True,
        probe_cap_available=True,
        counters=audit.AuditCounterState(),
    )
    assert same_action_v4["environment_action_contrast"] is False
    assert same_action_v4["causal_exercise"] is False

    original_selector = audit.ACTION_QBC_AUDIT_SELECTOR
    selector_calls = 0

    def fail_one_order_selector(*args: Any, **kwargs: Any) -> Any:
        nonlocal selector_calls
        selector_calls += 1
        if selector_calls == 2:
            raise RuntimeError("injected order failure")
        return original_selector(*args, **kwargs)

    monkeypatch.setattr(audit, "ACTION_QBC_AUDIT_SELECTOR", fail_one_order_selector)
    resilient_order_counters = audit.AuditCounterState()
    resilient_order_counters.mark_scientific_exposure_started()
    resilient_orders = audit.evaluate_order_transforms(
        result,
        counters=resilient_order_counters,
        order_transform_maps=maps,
        base_positive=False,
        continue_after_failure=True,
    )

    assert len(resilient_orders) == 5
    assert "failure" not in resilient_orders[0]
    assert resilient_orders[1]["passes"] is False
    assert cast(dict[str, Any], resilient_orders[1]["failure"])["stage"] == (
        "order_transform_failed"
    )
    assert all("selection" in row for row in resilient_orders[2:])

    registered_scene = cast(dict[str, Any], json.loads(json.dumps(scene)))
    registered_scene["scope"] = "registered"
    registered_scene["family_index"] = 0
    continuation_counters = audit.AuditCounterState()
    continuation_counters.mark_scientific_exposure_started()
    pipeline_calls = 0

    def injected_pipeline_failure(*_args: object, **_kwargs: object) -> Any:
        nonlocal pipeline_calls
        pipeline_calls += 1
        if pipeline_calls == 3:
            raise RuntimeError("injected visual failure")
        return result

    monkeypatch.setattr(
        audit,
        "evaluate_compiler_planner_snapshot",
        injected_pipeline_failure,
    )
    continued = audit.evaluate_scene_record(
        registered_scene,
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=continuation_counters,
        order_transform_maps=maps,
        require_linux_memory=False,
        deadline=time.monotonic() + 60.0,
    )
    visual_rows = [row for row in continued if row["kind"] == "visual_transform"]

    assert len(continued) == 10
    assert pipeline_calls == 5
    assert continued[0]["pipeline"] == audit._pipeline_json(result)
    assert cast(dict[str, Any], visual_rows[1]["pipeline"])["status"] == "failed"
    assert all(
        cast(dict[str, Any], row["pipeline"]).get("status") != "failed"
        for index, row in enumerate(visual_rows)
        if index != 1
    )
    assert len([row for row in continued if row["kind"] == "order_transform"]) == 5

    monkeypatch.setattr(audit, "ACTION_QBC_AUDIT_SELECTOR", original_selector)
    monkeypatch.setattr(
        audit,
        "evaluate_compiler_planner_snapshot",
        lambda *_args, **_kwargs: result,
    )
    original_pipeline_json = audit._pipeline_json
    serialization_calls = 0

    def fail_one_pipeline_serialization(value: audit.PipelineAuditResult) -> Any:
        nonlocal serialization_calls
        serialization_calls += 1
        if serialization_calls == 2:
            raise TypeError("injected pipeline serialization failure")
        return original_pipeline_json(value)

    monkeypatch.setattr(audit, "_pipeline_json", fail_one_pipeline_serialization)
    serialization_counters = audit.AuditCounterState()
    serialization_counters.mark_scientific_exposure_started()
    serialization_records = audit.evaluate_scene_record(
        registered_scene,
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=serialization_counters,
        order_transform_maps=maps,
        require_linux_memory=False,
        deadline=time.monotonic() + 60.0,
    )
    serialized_visuals = [
        row for row in serialization_records if row["kind"] == "visual_transform"
    ]

    assert len(serialization_records) == 10
    assert cast(dict[str, Any], serialized_visuals[0]["pipeline"])["status"] == (
        "failed"
    )
    assert all(
        cast(dict[str, Any], row["pipeline"]).get("status") != "failed"
        for row in serialized_visuals[1:]
    )


def test_scene_pipeline_failure_is_not_masked_before_scientific_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = cast(
        dict[str, Any],
        json.loads(json.dumps(generate_open_scene("homologue", 0x1020304050607080))),
    )
    scene["scope"] = "registered"
    scene["family_index"] = 0
    maps = tuple(
        cast(Mapping[str, Any], item) for item in build_order_transform_maps()
    )

    def fail_before_exposure(*_args: object, **_kwargs: object) -> Any:
        raise RuntimeError("injected pre-exposure failure")

    monkeypatch.setattr(
        audit,
        "evaluate_compiler_planner_snapshot",
        fail_before_exposure,
    )
    counters = audit.AuditCounterState()
    with pytest.raises(RuntimeError, match="pre-exposure"):
        audit.evaluate_scene_record(
            scene,
            config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
            counters=counters,
            order_transform_maps=maps,
            require_linux_memory=False,
            deadline=time.monotonic() + 60.0,
        )
    assert counters.scientific_exposure_started is False


def test_post_exposure_base_failure_continues_independent_visual_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = cast(
        dict[str, Any],
        json.loads(json.dumps(generate_open_scene("homologue", 0x1020304050607080))),
    )
    scene["scope"] = "registered"
    scene["family_index"] = 0
    maps = tuple(
        cast(Mapping[str, Any], item) for item in build_order_transform_maps()
    )
    counters = audit.AuditCounterState()
    pipeline_calls = 0

    def fail_after_exposure(*_args: object, **_kwargs: object) -> Any:
        nonlocal pipeline_calls
        pipeline_calls += 1
        if pipeline_calls == 1:
            counters.mark_scientific_exposure_started()
        raise RuntimeError("injected post-exposure failure")

    monkeypatch.setattr(
        audit,
        "evaluate_compiler_planner_snapshot",
        fail_after_exposure,
    )
    records = audit.evaluate_scene_record(
        scene,
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=counters,
        order_transform_maps=maps,
        require_linux_memory=False,
        deadline=time.monotonic() + 60.0,
    )
    visuals = [row for row in records if row["kind"] == "visual_transform"]
    orders = [row for row in records if row["kind"] == "order_transform"]

    assert len(records) == 10
    assert pipeline_calls == 4
    assert len(visuals) == 4
    assert cast(dict[str, Any], visuals[-1]["pipeline"])["failure"]["stage"] == (
        "base_pipeline_unavailable"
    )
    assert len(orders) == 5
    assert all(row["passes"] is False for row in orders)


def test_scientific_records_bind_exact_registered_block_order_and_ids() -> None:
    registration_admin = audit.load_audit_registration_admin(Path("."))
    registration = registration_admin.build_audit_registration(Path("."))
    inventory = cast(dict[str, Any], registration["row_inventory"])
    registered_rows = cast(list[dict[str, Any]], inventory["rows"])
    scene_sha_by_key = {
        (row["family"], row["scene_index"]): row["fixture_sha256"]
        for row in registered_rows
        if row["kind"] == "base_scene"
    }
    scientific_rows: list[dict[str, audit.JsonValue]] = []
    for registered in registered_rows:
        kind = registered["kind"]
        if kind == "base_scene":
            scientific_rows.append(
                {
                    "family": registered["family"],
                    "family_index": registered["scene_index"],
                        "kind": kind,
                        "scene_content_sha256": registered["fixture_sha256"],
                        "scene_id": (
                            f"{registered['family']}/{registered['scene_index']}"
                        ),
                }
            )
        elif kind in {"visual_transform", "order_transform"}:
            common: dict[str, audit.JsonValue] = {
                "family": registered["family"],
                "family_index": registered["scene_index"],
                    "kind": kind,
                    "scene_content_sha256": scene_sha_by_key[
                        (registered["family"], registered["scene_index"])
                    ],
                    "scene_id": (
                        f"{registered['family']}/{registered['scene_index']}"
                    ),
            }
            if kind == "visual_transform":
                common["transform_name"] = registered["transform"]
            else:
                common["name"] = registered["transform"]
            scientific_rows.append(common)
        else:
            scientific_rows.append(
                {
                    "kind": "control",
                    "name": registered["control_id"],
                }
            )
    bases = [row for row in scientific_rows if row["kind"] == "base_scene"]
    visuals = [row for row in scientific_rows if row["kind"] == "visual_transform"]
    orders = [row for row in scientific_rows if row["kind"] == "order_transform"]
    controls = [row for row in scientific_rows if row["kind"] == "control"]
    interleaved: list[dict[str, audit.JsonValue]] = []
    for scene_index in range(12):
        interleaved.append(bases[scene_index])
        interleaved.extend(visuals[scene_index * 4 : (scene_index + 1) * 4])
        interleaved.extend(orders[scene_index * 5 : (scene_index + 1) * 5])
    interleaved.extend(controls)

    bound = audit._bind_registered_row_inventory(interleaved, registered_rows)

    assert [row["row_index"] for row in bound] == list(range(140))
    assert [row["row_id"] for row in bound] == [
        row["row_id"] for row in registered_rows
    ]
    assert [row["kind"] for row in bound[:12]] == ["base_scene"] * 12
    assert [row["kind"] for row in bound[12:60]] == ["visual_transform"] * 48
    assert [row["kind"] for row in bound[60:120]] == ["order_transform"] * 60
    assert [row["kind"] for row in bound[120:]] == ["control"] * 20

    with pytest.raises(ValueError, match="unknown or extra/missing"):
        audit._bind_registered_row_inventory(
            [*interleaved, {"kind": "unregistered"}],
            registered_rows,
        )
    duplicated = [dict(row) for row in interleaved]
    duplicated[10] = dict(duplicated[0])
    with pytest.raises(ValueError, match="identity differs"):
        audit._bind_registered_row_inventory(duplicated, registered_rows)


def test_registered_manifest_returns_all_rows_after_post_exposure_scene_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration_admin = audit.load_audit_registration_admin(Path("."))
    registration = registration_admin.build_audit_registration(Path("."))
    inventory = cast(dict[str, Any], registration["row_inventory"])
    registered_rows = cast(list[dict[str, Any]], inventory["rows"])
    fixture_by_scene = {
        (row["family"], row["scene_index"]): row["fixture_sha256"]
        for row in registered_rows
        if row["kind"] == "base_scene"
    }
    template = generate_open_scene("homologue", 0x1020304050607080)
    scenes: list[dict[str, Any]] = []
    for family in audit.SEALED_SCENE_FAMILIES:
        for family_index in range(4):
            scene = cast(dict[str, Any], json.loads(json.dumps(template)))
            scene.update(
                {
                    "content_sha256": fixture_by_scene[(family, family_index)],
                    "family": family,
                    "family_index": family_index,
                    "scope": "registered",
                }
            )
            scenes.append(scene)
    counters = audit.AuditCounterState()
    scene_calls = 0
    controls_ran = False

    def injected_scene_evaluator(
        scene: Mapping[str, Any],
        **_kwargs: object,
    ) -> tuple[dict[str, audit.JsonValue], ...]:
        nonlocal scene_calls
        scene_calls += 1
        if scene_calls == 1:
            counters.mark_scientific_exposure_started()
            raise RuntimeError("injected scene failure")
        rows = list(
            audit._failed_scene_records(
                scene,
                stage="injected_remaining_scene_failure",
                error=RuntimeError("injected"),
            )
        )
        if scene_calls == 2:
            cast(dict[str, Any], rows[0])["unsafe"] = object()
        return tuple(rows)

    def injected_controls(
        _counters: audit.AuditCounterState,
        **_kwargs: object,
    ) -> tuple[dict[str, audit.JsonValue], ...]:
        nonlocal controls_ran
        controls_ran = True
        return tuple(
            {
                "expected": "injected",
                "name": name,
                "observed": "injected",
                "passes": False,
            }
            for name in audit.PREREGISTERED_CONTROL_ORDER
        )

    monkeypatch.setattr(audit, "evaluate_scene_record", injected_scene_evaluator)
    monkeypatch.setattr(audit, "evaluate_preregistered_controls", injected_controls)
    monkeypatch.setattr(
        audit,
        "_deterministic_environment_identity",
        lambda _provenance: {"test_environment": "open-fixture"},
    )
    canonical_json_bytes = audit.canonical_json_bytes
    final_serialization_failed = False

    def fail_first_final_serialization(value: audit.JsonValue) -> bytes:
        nonlocal final_serialization_failed
        if (
            not final_serialization_failed
            and isinstance(value, dict)
            and "records" in value
            and "acceptance" in value
        ):
            final_serialization_failed = True
            raise TypeError("injected final serialization failure")
        return canonical_json_bytes(value)

    monkeypatch.setattr(audit, "canonical_json_bytes", fail_first_final_serialization)
    payload = audit.evaluate_registered_manifest(
        {
            "content_sha256": audit.LOCKBOX_CONTENT_SHA256,
            "order_transform_maps": build_order_transform_maps(),
            "scenes": scenes,
        },
        config=load_config(audit.AUDIT_CONFIG_RELATIVE_PATH),
        counters=counters,
        provenance=audit.EXPECTED_AUDIT_PROVENANCE,
        canonical_command_template=("registered",),
        registration_rows=registered_rows,
        registration_preregistration={},
        registration_sha256="0" * 64,
        started_monotonic=time.monotonic(),
    )
    rows = cast(list[dict[str, Any]], payload["records"])

    assert scene_calls == 12
    assert controls_ran is True
    assert len(rows) == 140
    assert [row["row_id"] for row in rows] == [
        row["row_id"] for row in registered_rows
    ]
    assert cast(dict[str, Any], payload["acceptance"])["acceptance_passes"] is False
    assert cast(dict[str, Any], rows[0]["pipeline"])["status"] == "failed"
    assert cast(dict[str, Any], rows[1]["pipeline"])["failure"]["stage"] == (
        "not_completed"
    )
    finalization_failures = cast(list[dict[str, Any]], payload["finalization_failures"])
    assert [failure["stage"] for failure in finalization_failures] == [
        "scientific_record_finalization_failed",
        "scientific_record_finalization_failed",
        "scientific_rows_not_completed",
        "final_payload_serialization_failed",
    ]
    assert audit.validate_and_rederive_scientific_records(rows, registered_rows) == rows
    assert final_serialization_failed is True

    forged_payload = dict(payload)
    forged_acceptance = dict(cast(dict[str, Any], payload["acceptance"]))
    forged_acceptance["final_admission_claimed"] = True
    forged_acceptance["runtime_v5_enabled"] = True
    forged_payload["acceptance"] = forged_acceptance
    emergency = audit.build_emergency_negative_payload(
        forged_payload,
        RuntimeError("injected repeat finalization failure"),
    )
    emergency_acceptance = cast(dict[str, Any], emergency["acceptance"])
    assert emergency_acceptance["final_admission_claimed"] is False
    assert emergency_acceptance["runtime_v5_enabled"] is False


def test_aggregate_acceptance_passes_complete_evidence_and_rejects_tamper() -> None:
    records: list[dict[str, Any]] = []
    for family in audit.SEALED_SCENE_FAMILIES:
        records.extend(
            {
                "causal_exercise": True,
                "family": family,
                "kind": "base_scene",
                "positive_mechanism": True,
                "structural_gate": {"passes": True},
            }
            for _index in range(4)
        )
    records.extend(
        {
            "comparison": {"passes": True},
            "kind": "visual_transform",
            "structural_gate": {"passes": True},
        }
        for _index in range(48)
    )
    records.extend(
        {"kind": "order_transform", "passes": True} for _index in range(60)
    )
    records.extend({"kind": "control", "passes": True} for _index in range(20))
    counters = audit.AuditCounterState(
        _values=dict(audit.EXPECTED_SEALED_RESOURCE_COUNTS)
    )
    counters.mark_scientific_exposure_started()

    accepted = audit._aggregate_acceptance(records, counters)

    assert accepted["acceptance_passes"] is True
    tampered = [dict(record) for record in records]
    tampered[60]["passes"] = False
    rejected = audit._aggregate_acceptance(tampered, counters)
    assert rejected["acceptance_passes"] is False
    assert "all_order_transforms" in cast(list[str], rejected["failed_checks"])
