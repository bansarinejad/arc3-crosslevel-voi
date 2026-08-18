"""Non-scientific lifecycle and one-shot boundary tests for action-QBC v8."""

from __future__ import annotations

import ast
import base64
import hashlib
import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.execute_action_qbc_v8_open_lifecycle as lifecycle
import scripts.finalize_action_qbc_v8_open_diagnostic as finalizer
import scripts.prepare_action_qbc_v8_open as preparation
import scripts.reconstruct_action_qbc_v8_open_registration as reconstruction
import scripts.run_action_qbc_v8_open_diagnostic as runner
import scripts.supervise_action_qbc_v8_remote_tag as supervisor
import scripts.validate_action_qbc_v8_open_payload as validator
import scripts.verify_action_qbc_v8_remote_tag as remote_verifier

ROOT = Path(__file__).resolve().parents[1]


def _rebind_evidence_paths(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    **role_paths: Path,
) -> None:
    paths = dict(module._EVIDENCE_PATHS_BY_ROLE)
    paths.update(role_paths)
    monkeypatch.setattr(module, "_EVIDENCE_PATHS_BY_ROLE", paths)


class _Fallback(Exception):
    def __init__(self, stage: str, candidate_payload_size_bytes: int | None = None) -> None:
        super().__init__(stage)
        self.stage = stage
        self.candidate_payload_size_bytes = candidate_payload_size_bytes


def _audit_stub(
    *,
    producer: Any | None = None,
    finalizer: Any | None = None,
    validator_fn: Any | None = None,
    encoder: Any | None = None,
) -> SimpleNamespace:
    def default_producer(
        _root: Path, _registration: Any, *, compute_deadline: float
    ) -> dict[str, Any]:
        assert compute_deadline > 0
        return {"candidate": True}

    def default_finalizer(candidate: Any, _registration: Any) -> Any:
        return candidate

    def default_validator(payload: Any, _registration: Any) -> Any:
        return payload

    def default_encoder(payload: Any) -> bytes:
        if isinstance(payload, dict) and "fallback" in payload:
            return b'{"fallback":true}'
        return b'{"candidate":true}'

    def fallback_builder(
        _registration: Any,
        stage: str,
        *,
        candidate_payload_size_bytes: int | None = None,
    ) -> dict[str, Any]:
        return {
            "fallback": stage,
            "candidate_payload_size_bytes": candidate_payload_size_bytes,
        }

    return SimpleNamespace(
        GlobalFallbackRequired=_Fallback,
        produce_scientific_candidate=producer or default_producer,
        finalize_scientific_payload=finalizer or default_finalizer,
        validate_scientific_payload=validator_fn or default_validator,
        canonical_json_bytes=encoder or default_encoder,
        build_global_fallback=fallback_builder,
    )


def _result_contract_registration() -> dict[str, Any]:
    normal_cases: list[dict[str, Any]] = []
    cases = [
        ("scientific_result", None, None),
        *[("administrative_terminal", stage, stage) for stage in finalizer._UNDERLYING_ORDER],
        (
            "administrative_terminal",
            "receipt_finalization_failed",
            "<UNDERLYING_STAGE_OR_NULL>",
        ),
    ]
    for disposition, stage, underlying in cases:
        case_raw = finalizer._NORMAL_TEMPLATE.format(
            disposition=disposition,
            stage=stage if stage is not None else "null",
            underlying_stage=underlying if underlying is not None else "null",
            open_freeze_commit_sha="<O8_COMMIT>",
            registration_content_sha256="<REGISTRATION_CONTENT_SHA256>",
        ).encode("ascii")
        import base64

        normal_cases.append(
            {
                "disposition": disposition,
                "stage": stage,
                "underlying_stage": underlying,
                "content_base64": base64.b64encode(case_raw).decode("ascii"),
                "sha256": hashlib.sha256(case_raw).hexdigest(),
                "size_bytes": len(case_raw),
            }
        )
    emergency_text = finalizer._NORMAL_TEMPLATE + finalizer._EMERGENCY_SUFFIX
    contract = {
        "schema_version": finalizer._RESULT_DOCUMENT_SCHEMA,
        "renderer_source": {
            "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
            "mode": "100644",
            "git_blob_sha1": "a" * 40,
            "sha256": "b" * 64,
            "size_bytes": 1,
        },
        "normal_template": {
            "text": finalizer._NORMAL_TEMPLATE,
            "sha256": hashlib.sha256(finalizer._NORMAL_TEMPLATE.encode("ascii")).hexdigest(),
        },
        "emergency_template": {
            "text": emergency_text,
            "sha256": hashlib.sha256(emergency_text.encode("ascii")).hexdigest(),
        },
        "normal_input_names": [
            "disposition",
            "open_freeze_commit_sha",
            "registration_content_sha256",
            "stage",
            "underlying_stage",
        ],
        "emergency_input_names": [
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
        ],
        "normal_cases": normal_cases,
    }
    return {
        "content_sha256": "c" * 64,
        "execution_contract": {"result_document_contract": contract},
    }


def test_runner_and_validator_help_are_offline_and_do_not_import_science() -> None:
    environment = os.environ.copy()
    environment["UV_OFFLINE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    for relative, expected in (
        ("scripts/run_action_qbc_v8_open_diagnostic.py", "--start-claim"),
        ("scripts/validate_action_qbc_v8_open_payload.py", "--validator-claim"),
        ("scripts/finalize_action_qbc_v8_open_diagnostic.py", "--lifecycle-ledger"),
    ):
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(ROOT / relative), "--help"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert expected in completed.stdout


def test_scientific_module_imports_are_deferred_until_after_exclusive_claim() -> None:
    for relative, claim_call in (
        ("scripts/run_action_qbc_v8_open_diagnostic.py", "_acquire_start_claim("),
        ("scripts/validate_action_qbc_v8_open_payload.py", "_exclusive_json("),
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("arc3_voi") for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("arc3_voi")
        assert source.index(claim_call, source.index("def main")) < source.index(
            'import_module("arc3_voi.action_qbc_v8_audit")', source.index("def main")
        )


def test_runner_rejects_programmatic_argv_before_registration_or_science(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("registration or scientific work must not start")

    monkeypatch.setattr(runner, "_load_registration", forbidden)
    return_code = runner.main(
        [
            "--repository-root",
            ".",
            "--registration",
            runner._EXPECTED_REGISTRATION,
            "--preparation-verification-receipt",
            runner._PREPARATION_VERIFICATION_RECEIPT,
            "--arm-receipt",
            runner._ARM_RECEIPT,
            "--driver-claim",
            runner._DRIVER_CLAIM,
            "--label",
            "A",
            "--start-claim",
            runner._PROCESS["A"]["start_claim"],
            "--prior-validation-receipt",
            "null",
            "--compute-deadline-seconds",
            "2100",
            "--wall-time-seconds",
            "2400",
            "--output",
            runner._PROCESS["A"]["output"],
        ]
    )
    assert return_code == 2
    assert "programmatic argv is not permitted" in capsys.readouterr().err


def test_validator_post_create_claim_failure_attempts_invalid_receipt_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim_path = tmp_path / "validator-claim.json"
    receipt_path = tmp_path / "validation-receipt.json"
    payload_path = tmp_path / "payload.json"
    payload_raw = b'{"payload":true}'
    payload_path.write_bytes(payload_raw)
    process = {
        "root": str(tmp_path),
        "start_claim": str(tmp_path / "start-claim.json"),
        "validator_claim": str(claim_path),
        "validation_receipt": str(receipt_path),
        "payload": str(payload_path),
    }
    registration = {"content_sha256": "a" * 64}
    start_raw = b'{"start":true}'
    driver_raw = b'{"driver":true}'
    arm_raw = b'{"arm":true}'
    publication_paths: list[Path] = []

    def exclusive_canonical(path: Path, value: dict[str, Any]) -> bytes:
        raw = validator._canonical_json_bytes(value)
        publication_paths.append(path)
        path.write_bytes(raw)
        if path == claim_path:
            raise RuntimeError("synthetic post-create verification failure")
        return raw

    helper = SimpleNamespace(
        _PROCESS={"A": process},
        _load_registration=lambda _root, _path: (registration, b"registration"),
        _verify_repository=lambda _root, _registration, _raw: "b" * 40,
        _validate_dependencies=lambda *_args, **_kwargs: (
            arm_raw,
            driver_raw,
            None,
            {},
            {},
        ),
        _exclusive_canonical=exclusive_canonical,
    )
    args = SimpleNamespace(registration=Path("registration.json"))
    monkeypatch.setattr(validator, "_parse_args", lambda _argv: args)
    monkeypatch.setattr(
        validator.sys,
        "flags",
        SimpleNamespace(isolated=1, dont_write_bytecode=1),
    )
    monkeypatch.setattr(
        validator,
        "_preverify_and_load_runner",
        lambda _root: (helper, "b" * 40),
    )
    monkeypatch.setattr(
        validator,
        "_require_contract",
        lambda *_args, **_kwargs: ("A", process, ["validator", "A"]),
    )
    monkeypatch.setattr(
        validator,
        "_validate_start_claim",
        lambda *_args, **_kwargs: ({}, start_raw),
    )
    monkeypatch.setattr(
        validator,
        "_plain",
        lambda path, _name, *, maximum: (
            path.read_bytes()
            if path.stat().st_size <= maximum
            else pytest.fail("synthetic fixture exceeded read cap")
        ),
    )
    monkeypatch.setattr(
        validator.importlib,
        "import_module",
        lambda _name: pytest.fail("science import after failed claim verification"),
    )

    assert validator.main() == 1
    claim_raw = claim_path.read_bytes()
    receipt = validator.json.loads(receipt_path.read_bytes())
    assert publication_paths == [claim_path, receipt_path]
    assert receipt["status"] == "invalid"
    assert receipt["validator_claim_sha256"] == hashlib.sha256(claim_raw).hexdigest()
    assert receipt["start_claim_sha256"] == hashlib.sha256(start_raw).hexdigest()
    assert receipt["payload_sha256"] == hashlib.sha256(payload_raw).hexdigest()


def test_runner_normal_path_calls_producer_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def producer(
        _root: Path, _registration: Any, *, compute_deadline: float
    ) -> dict[str, bool]:
        assert compute_deadline == 10.0
        calls.append("producer")
        return {"candidate": True}

    monkeypatch.setattr(runner.time, "monotonic", lambda: 0.0)
    payload, encoded = runner._evaluate(
        _audit_stub(producer=producer),
        Path("."),
        {},
        compute_deadline=10.0,
    )
    assert calls == ["producer"]
    assert payload == {"candidate": True}
    assert encoded == b'{"candidate":true}'


@pytest.mark.parametrize(
    "phase",
    ["pre_deadline", "producer", "post_deadline", "finalizer", "validator", "encoder"],
)
def test_each_frozen_try_operation_builds_one_fallback(
    phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer_calls = 0
    clock = iter([10.0] if phase == "pre_deadline" else [0.0, 10.0])
    if phase in {"pre_deadline", "post_deadline"}:
        monkeypatch.setattr(runner.time, "monotonic", lambda: next(clock))
    else:
        monkeypatch.setattr(runner.time, "monotonic", lambda: 0.0)

    def producer(
        _root: Path, _registration: Any, *, compute_deadline: float
    ) -> dict[str, bool]:
        nonlocal producer_calls
        producer_calls += 1
        if phase == "producer":
            raise RuntimeError("injected producer fault")
        return {"candidate": True}

    def finalizer(candidate: Any, _registration: Any) -> Any:
        if phase == "finalizer":
            raise RuntimeError("injected finalizer fault")
        return candidate

    validation_calls = 0

    def validate(payload: Any, _registration: Any) -> Any:
        nonlocal validation_calls
        validation_calls += 1
        if phase == "validator" and validation_calls == 1:
            raise RuntimeError("injected validation fault")
        return payload

    encoding_calls = 0

    def encode(payload: Any) -> bytes:
        nonlocal encoding_calls
        encoding_calls += 1
        if phase == "encoder" and encoding_calls == 1:
            raise RuntimeError("injected encoding fault")
        if isinstance(payload, dict) and "fallback" in payload:
            return b'{"fallback":true}'
        return b'{"candidate":true}'

    payload, encoded = runner._evaluate(
        _audit_stub(
            producer=producer,
            finalizer=finalizer,
            validator_fn=validate,
            encoder=encode,
        ),
        Path("."),
        {},
        compute_deadline=10.0,
    )
    assert payload["fallback"] == "evaluator_internal_error"
    assert encoded == b'{"fallback":true}'
    assert producer_calls == (0 if phase == "pre_deadline" else 1)


def test_declared_global_fallback_stage_and_size_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def producer(*_args: object, **_kwargs: object) -> Any:
        raise _Fallback("payload_size_limit_exceeded", 12345)

    monkeypatch.setattr(runner.time, "monotonic", lambda: 0.0)
    payload, _ = runner._evaluate(
        _audit_stub(producer=producer), Path("."), {}, compute_deadline=10.0
    )
    assert payload == {
        "fallback": "payload_size_limit_exceeded",
        "candidate_payload_size_bytes": 12345,
    }


@pytest.mark.parametrize(
    ("candidate_size", "falls_back"),
    [
        (runner._PAYLOAD_CAP_BYTES - 1, False),
        (runner._PAYLOAD_CAP_BYTES, False),
        (runner._PAYLOAD_CAP_BYTES + 1, True),
    ],
)
def test_payload_cap_boundary(candidate_size: int, falls_back: bool) -> None:
    def encode(payload: Any) -> bytes:
        if isinstance(payload, dict) and "fallback" in payload:
            return b'{"fallback":true}'
        return b"x" * candidate_size

    payload, encoded = runner._evaluate(
        _audit_stub(encoder=encode), Path("."), {}, compute_deadline=float("inf")
    )
    if falls_back:
        assert payload["fallback"] == "payload_size_limit_exceeded"
        assert payload["candidate_payload_size_bytes"] == candidate_size
        assert encoded == b'{"fallback":true}'
    else:
        assert payload == {"candidate": True}
        assert len(encoded) == candidate_size


@pytest.mark.skipif(os.name == "nt", reason="runner publication uses Linux dirfd APIs")
def test_staged_validation_failure_is_administrative_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    output_parent = tmp_path / "open"
    output_parent.mkdir(mode=0o700)
    output = output_parent / "payload.json"

    def reject_staged(*_args: object, **_kwargs: object) -> Any:
        raise ValueError("injected staged validation failure")

    audit = _audit_stub(validator_fn=reject_staged)
    descriptor = os.open(output_parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(ValueError, match="staged validation"):
            runner._publish(
                output,
                descriptor,
                {"candidate": True},
                b'{"candidate":true}',
                wall_deadline=float("inf"),
                registration={},
                audit=audit,
            )
    finally:
        os.close(descriptor)
    assert not output.exists()
    assert list(output_parent.iterdir()) == []


def test_exclusive_claim_creation_is_durable_and_never_replaces(tmp_path: Path) -> None:
    if os.name != "nt":
        tmp_path.chmod(0o700)
    value = {"schema_version": "synthetic", "value": 1}
    destination = tmp_path / "claim.json"
    raw = runner._exclusive_canonical(destination, value)
    assert raw == runner._canonical_json_bytes(value)
    assert destination.read_bytes() == raw
    before = hashlib.sha256(raw).hexdigest()
    with pytest.raises(runner._AdministrativeFailure):
        runner._exclusive_canonical(destination, {"schema_version": "replacement"})
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == before


def test_claim_and_validation_schemas_have_exact_frozen_keys() -> None:
    expected_start_keys = {
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
    expected_validator_keys = {
        "schema_version",
        "treatment_id",
        "label",
        "lifecycle_driver_claim_sha256",
        "start_claim_sha256",
        "validator_argv_sha256",
        "payload_sha256",
    }
    expected_validation_keys = {
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
    assert expected_start_keys == runner._START_KEYS
    assert expected_validator_keys == validator._VALIDATOR_KEYS
    assert expected_validation_keys == validator._VALIDATION_KEYS


def test_all_cross_component_schema_keysets_are_identical() -> None:
    assert (
        runner._REGISTRATION_KEYS
        == preparation._REGISTRATION_KEYS
        == remote_verifier._REGISTRATION_KEYS
        == supervisor._REGISTRATION_KEYS
        == lifecycle._REGISTRATION_KEYS
        == finalizer._REGISTRATION_KEYS
    )
    assert (
        preparation._ARM_KEYS
        == runner._ARM_KEYS
        == lifecycle._ARM_KEYS
        == finalizer._ARM_KEYS
    )
    assert runner._DRIVER_KEYS == lifecycle._DRIVER_KEYS == finalizer._DRIVER_KEYS
    assert runner._START_KEYS == finalizer._START_KEYS
    assert (
        runner._VALIDATION_KEYS
        == validator._VALIDATION_KEYS
        == lifecycle._VALIDATION_KEYS
        == finalizer._VALIDATION_KEYS
    )
    assert (
        preparation._CLAIM_KEYS
        == remote_verifier._CLAIM_KEYS
        == supervisor._CLAIM_KEYS
        == lifecycle._REMOTE_CLAIM_KEYS
        == finalizer._REMOTE_CLAIM_KEYS
    )
    assert (
        preparation._START_CLAIM_KEYS
        == remote_verifier._START_CLAIM_KEYS
        == supervisor._START_CLAIM_KEYS
        == lifecycle._REMOTE_VERIFIER_KEYS
        == finalizer._REMOTE_VERIFIER_KEYS
    )
    assert (
        preparation._REMOTE_RECEIPT_KEYS
        == remote_verifier._RECEIPT_KEYS
        == supervisor._REMOTE_RECEIPT_KEYS
        == lifecycle._REMOTE_RECEIPT_KEYS
        == finalizer._REMOTE_RECEIPT_KEYS
    )
    assert (
        preparation._REMOTE_ATTEMPT_KEYS
        == remote_verifier._ATTEMPT_KEYS
        == supervisor._ATTEMPT_KEYS
        == finalizer._REMOTE_ATTEMPT_KEYS
    )
    assert (
        preparation._SUPERVISOR_KEYS
        == supervisor._SUPERVISOR_RECEIPT_KEYS
        == lifecycle._REMOTE_SUPERVISOR_KEYS
        == finalizer._REMOTE_SUPERVISOR_KEYS
    )
    assert preparation._PREPARATION_KEYS == finalizer._PREPARATION_KEYS
    assert preparation._CLONE_KEYS == finalizer._CLONE_KEYS
    assert preparation._ATTEMPT_RECORD_KEYS == finalizer._PREPARATION_ATTEMPT_KEYS
    assert preparation._CLEANUP_KEYS == finalizer._PREPARATION_CLEANUP_KEYS
    assert preparation._PROMOTION_KEYS == finalizer._PREPARATION_PROMOTION_KEYS
    assert lifecycle._LEDGER_KEYS == finalizer._LEDGER_KEYS
    assert lifecycle._LEDGER_PROCESS_KEYS == finalizer._LEDGER_PROCESS_KEYS


def test_p8v7_expected_mode_maps_are_exhaustive_identical_and_alias_free() -> None:
    immutable = {
        "preparation_receipt",
        "remote_claim",
        "remote_verifier_claim",
        "remote_receipt",
        "remote_supervisor_receipt",
        "arm_receipt",
    }
    private = {
        "preparation_verification_receipt",
        "lifecycle_driver_claim",
        "lifecycle_ledger",
        "process_a_start_claim",
        "process_b_start_claim",
        "process_a_validator_claim",
        "process_b_validator_claim",
        "process_a_validation_receipt",
        "process_b_validation_receipt",
        "process_a_payload",
        "process_b_payload",
        "normal_finalization_bundle",
        "emergency_result_bundle",
        "result_git_owner_claim",
    }
    modules_and_errors = (
        (preparation, preparation.ProtocolError),
        (lifecycle, lifecycle.LifecycleError),
        (finalizer, finalizer._FinalizationError),
    )
    expected_modes = {
        **dict.fromkeys(immutable, 0o444),
        **dict.fromkeys(private, 0o600),
    }
    reference_paths = {
        role: str(path)
        for role, path in preparation._EVIDENCE_PATHS_BY_ROLE.items()
    }
    assert len(expected_modes) == 20
    for module, error in modules_and_errors:
        paths = module._EVIDENCE_PATHS_BY_ROLE
        assert expected_modes == module._EVIDENCE_EXPECTED_MODES
        assert set(paths) == set(expected_modes)
        assert all(isinstance(path, Path) for path in paths.values())
        assert len(set(paths.values())) == len(paths)
        assert {role: str(path) for role, path in paths.items()} == reference_paths
        for role, path in paths.items():
            assert module._expected_evidence_mode(path, role) == expected_modes[role]
        with pytest.raises(error, match="unknown evidence role"):
            module._expected_evidence_mode(next(iter(paths.values())), "unknown-role")
        with pytest.raises(error, match="path differs"):
            module._expected_evidence_mode(Path("/not/the/registered/path"), next(iter(paths)))


@pytest.mark.skipif(os.name != "posix", reason="exact POSIX evidence modes")
@pytest.mark.parametrize(
    ("module", "reader"),
    [
        pytest.param(
            preparation,
            lambda selected, path, role: selected._artifact_state(
                path,
                role,
                role=role,
                maximum=1 << 20,
            ),
            id="preparation",
        ),
        pytest.param(
            lifecycle,
            lambda selected, path, role: selected._evidence_state(
                path,
                role,
                role=role,
            ),
            id="lifecycle",
        ),
        pytest.param(
            finalizer,
            lambda selected, path, role: selected._artifact(
                str(path),
                role=role,
                name=role,
            ),
            id="finalizer",
        ),
    ],
)
def test_p8v7_every_evidence_role_accepts_only_its_single_exact_mode(
    module: Any,
    reader: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapped = dict(module._EVIDENCE_PATHS_BY_ROLE)
    for index, (role, expected_mode) in enumerate(
        sorted(module._EVIDENCE_EXPECTED_MODES.items())
    ):
        path = tmp_path / f"{index:02d}-{role}.json"
        path.write_bytes(b"{}")
        path.chmod(expected_mode)
        mapped[role] = path
        monkeypatch.setattr(module, "_EVIDENCE_PATHS_BY_ROLE", dict(mapped))
        accepted = reader(module, path, role)
        assert accepted.read_status == "readable"
        assert accepted.raw == b"{}"

        wrong_mode = 0o600 if expected_mode == 0o444 else 0o444
        path.chmod(wrong_mode)
        rejected = reader(module, path, role)
        assert rejected.read_status == "unsafe_type"
        path.chmod(expected_mode)


@pytest.mark.skipif(os.name != "posix", reason="POSIX evidence identity gates")
@pytest.mark.parametrize("hazard", ["symlink", "hardlink", "wrong_owner", "oversized", "changing"])
@pytest.mark.parametrize("module", [preparation, lifecycle, finalizer])
def test_p8v7_role_aware_readers_reject_every_hostile_file_identity(
    module: Any,
    hazard: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / f"{module.__name__.rsplit('.', 1)[-1]}-{hazard}"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    path = (parent / "driver-claim.json").resolve()
    role = "lifecycle_driver_claim"
    mapped = dict(module._EVIDENCE_PATHS_BY_ROLE)
    mapped[role] = path
    monkeypatch.setattr(module, "_EVIDENCE_PATHS_BY_ROLE", mapped)
    expected_status = "unsafe_type"
    maximum = 1 << 20

    if hazard == "symlink":
        target = parent / "target.json"
        target.write_bytes(b"{}")
        target.chmod(0o600)
        path.symlink_to(target)
    else:
        path.write_bytes(b"{}")
        path.chmod(0o600)
        if hazard == "hardlink":
            os.link(path, parent / "second-link.json")
        elif hazard == "wrong_owner":
            actual_uid = os.getuid()
            if module is preparation:
                monkeypatch.setattr(module.os, "geteuid", lambda: actual_uid + 1)
            elif module is lifecycle:
                monkeypatch.setattr(module, "_owner_uid", lambda: actual_uid + 1)
            else:
                monkeypatch.setattr(module.os, "getuid", lambda: actual_uid + 1)
        elif hazard == "oversized":
            maximum = 1
            expected_status = "oversized"
            if module is finalizer:
                monkeypatch.setattr(module, "_PAYLOAD_CAP", maximum)
        elif hazard == "changing":
            original_read = module.os.read
            changed = False

            def changing_read(descriptor: int, count: int) -> bytes:
                nonlocal changed
                raw = original_read(descriptor, count)
                if not changed:
                    changed = True
                    with path.open("ab") as stream:
                        stream.write(b"x")
                return raw

            monkeypatch.setattr(module.os, "read", changing_read)
            expected_status = "changed_during_read"

    if module is preparation:
        state = module._artifact_state(
            path,
            role,
            role=role,
            maximum=maximum,
        )
    elif module is lifecycle:
        state = module._evidence_state(
            path,
            role,
            role=role,
            maximum=maximum,
        )
    else:
        state = module._artifact(str(path), role=role, name=role)
    assert state.exists is True
    assert state.read_status == expected_status
    assert state.raw is None


@pytest.mark.skipif(os.name != "posix", reason="real POSIX publication subprocess")
def test_p8v7_real_producer_to_all_consumers_reopens_complete_mode_matrix(
    tmp_path: Path,
) -> None:
    probe = (
        "import importlib.util,os,pathlib,sys\n"
        "repo=pathlib.Path(sys.argv[1]); evidence=pathlib.Path(sys.argv[2])\n"
        "def load(name,path):\n"
        " s=importlib.util.spec_from_file_location(name,path); "
        "m=importlib.util.module_from_spec(s); "
        "sys.modules[name]=m; s.loader.exec_module(m); return m\n"
        "p=load('_p8v7_prepare',repo/'scripts/prepare_action_qbc_v8_open.py')\n"
        "l=load('_p8v7_lifecycle',repo/'scripts/execute_action_qbc_v8_open_lifecycle.py')\n"
        "f=load('_p8v7_finalizer',repo/'scripts/finalize_action_qbc_v8_open_diagnostic.py')\n"
        "roles=sorted(p._EVIDENCE_EXPECTED_MODES)\n"
        "paths={role:evidence/f'{i:02d}-{role}.json' for i,role in enumerate(roles)}\n"
        "[path.parent.mkdir(parents=True,exist_ok=True) for path in paths.values()]\n"
        "[path.parent.chmod(0o700) for path in paths.values()]\n"
        "p._EVIDENCE_PATHS_BY_ROLE=dict(paths); l._EVIDENCE_PATHS_BY_ROLE=dict(paths); "
        "f._EVIDENCE_PATHS_BY_ROLE=dict(paths)\n"
        "assert p._EVIDENCE_EXPECTED_MODES==l._EVIDENCE_EXPECTED_MODES\n"
        "assert l._EVIDENCE_EXPECTED_MODES==f._EVIDENCE_EXPECTED_MODES\n"
        "for role in roles:\n"
        " path=paths[role]; p._publish_bytes_exclusive(path,b'{}',role,role=role)\n"
        " assert (path.stat().st_mode & 0o777)==p._EVIDENCE_EXPECTED_MODES[role]\n"
        " assert p._artifact_state(path,role,role=role,maximum=1024).read_status=='readable'\n"
        " assert l._evidence_state(path,role,role=role,maximum=1024).read_status=='readable'\n"
        " assert f._artifact(str(path),role=role,name=role).read_status=='readable'\n"
        "sys.stdout.write('mode-matrix-ok\\n')\n"
    )
    boundary_probe = textwrap.dedent(
        r"""
        import argparse
        import hashlib
        import importlib.util
        import os
        import pathlib
        import sys

        repo = pathlib.Path(sys.argv[1])
        evidence = pathlib.Path(sys.argv[2])

        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

        p = load("_p8v7_prepare_boundary", repo / "scripts/prepare_action_qbc_v8_open.py")
        l = load(
            "_p8v7_lifecycle_boundary",
            repo / "scripts/execute_action_qbc_v8_open_lifecycle.py",
        )
        f = load(
            "_p8v7_finalizer_boundary",
            repo / "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        )
        roles = sorted(p._EVIDENCE_EXPECTED_MODES)
        authority = evidence / "authority"
        execution_root = evidence / "execution"
        windows = evidence / "windows-source"
        for directory in (authority, execution_root, windows):
            directory.mkdir(parents=True, mode=0o700)
            directory.chmod(0o700)
        paths = {
            role: execution_root / f"{index:02d}-{role}.json"
            for index, role in enumerate(roles)
        }
        paths.update(
            {
                "preparation_receipt": execution_root / "preparation-receipt.json",
                "preparation_verification_receipt": (
                    execution_root / "preparation-verification-receipt.json"
                ),
                "remote_claim": execution_root / "remote-verification-claim.json",
                "remote_verifier_claim": (
                    execution_root / "remote-verifier-start-claim.json"
                ),
                "remote_receipt": execution_root / "remote-verification.json",
                "remote_supervisor_receipt": (
                    execution_root / "remote-verification-supervisor.json"
                ),
                "arm_receipt": execution_root / "arm-receipt.json",
            }
        )
        assert len(set(paths.values())) == len(paths)
        p._EVIDENCE_PATHS_BY_ROLE = dict(paths)
        l._EVIDENCE_PATHS_BY_ROLE = dict(paths)
        f._EVIDENCE_PATHS_BY_ROLE = dict(paths)

        commit = "c" * 40
        registration_sha = "a" * 64
        p._AUTHORITY_ROOT = str(authority.resolve())
        p._EXECUTION_ROOT = str(execution_root)
        p._PREPARATION_RECEIPT = str(paths["preparation_receipt"])
        p._PREPARATION_VERIFICATION_RECEIPT = str(
            paths["preparation_verification_receipt"]
        )
        p._ARM_RECEIPT = str(paths["arm_receipt"])
        p._WINDOWS_CLAIM = str(windows / "remote-verification-claim-v4.json")
        p._WINDOWS_START_CLAIM = str(
            windows / "remote-verifier-start-claim-v4.json"
        )
        p._WINDOWS_REMOTE_RECEIPT = str(windows / "remote-verification-v4.json")
        p._WINDOWS_SUPERVISOR_RECEIPT = str(
            windows / "remote-verification-supervisor-v4.json"
        )
        registration = p._Registration(
            value={},
            raw=b"registration",
            content_sha256=registration_sha,
            file_sha256="b" * 64,
            source_manifest_sha256="d" * 64,
            execution={"arm_argv": p._expected_arm_argv()},
        )
        p._validate_preparation_root = lambda *args, **kwargs: None
        p._derive_open_freeze = lambda *args, **kwargs: commit
        p._raw_tree_audit = lambda *args, **kwargs: object()
        p._load_registration = lambda *args, **kwargs: registration
        p._validate_prepare_invocation = lambda *args, **kwargs: None
        p._validate_linux_host = lambda *args, **kwargs: None
        p._clone_receipt = lambda *args, **kwargs: {"synthetic": "authority"}

        def prepare_attempt(_ledger, root, attempt_index, *_args):
            attempt_root = root / f".prepare-attempt-{attempt_index}"
            return p._AttemptOutcome(
                {
                    "attempt_index": attempt_index,
                    "process_a_stage": "completed",
                    "process_b_stage": "completed",
                    "cleanup": {"owned_paths": [], "removed": [], "passes": True},
                    "promotion": {
                        "source_path": str(attempt_root),
                        "destination_path": str(root / "processes"),
                        "source_device": 1,
                        "source_inode": 1,
                        "passes": True,
                    },
                    "passes": True,
                },
                {"synthetic": "process-a"},
                {"synthetic": "process-b"},
                True,
                None,
            )

        p._prepare_attempt = prepare_attempt
        prepare_args = argparse.Namespace(
            repository_root=authority,
            registration=pathlib.Path("registration.json"),
            execution_root=execution_root,
            receipt=paths["preparation_receipt"],
        )
        assert p._prepare(prepare_args) == 0
        assert paths["preparation_receipt"].stat().st_mode & 0o777 == 0o444
        p._publish_bytes_exclusive(
            paths["preparation_verification_receipt"],
            b'{"synthetic":true}',
            "preparation-verification-receipt",
            role="preparation_verification_receipt",
        )

        def remote_value(keys, schema):
            value = dict.fromkeys(keys)
            value.update(
                {
                    "schema_version": schema,
                    "treatment_id": p._TREATMENT_ID,
                    "open_freeze_commit_sha": commit,
                    "registration_content_sha256": registration_sha,
                }
            )
            return value

        claim = remote_value(
            l._REMOTE_CLAIM_KEYS,
            "action-qbc-v8-remote-tag-verification-claim-v1",
        )
        claim["open_freeze_tag"] = l._OPEN_FREEZE_TAG
        claim_raw = p.canonical_json_bytes(claim)
        claim_sha = hashlib.sha256(claim_raw).hexdigest()
        start = remote_value(
            l._REMOTE_VERIFIER_KEYS,
            "action-qbc-v8-remote-tag-verifier-start-claim-v1",
        )
        start["claim_sha256"] = claim_sha
        start_raw = p.canonical_json_bytes(start)
        start_sha = hashlib.sha256(start_raw).hexdigest()
        remote = remote_value(
            l._REMOTE_RECEIPT_KEYS,
            "action-qbc-v8-remote-tag-verification-receipt-v1",
        )
        remote.update(
            {
                "claim_sha256": claim_sha,
                "verifier_start_claim_sha256": start_sha,
                "open_freeze_tag": l._OPEN_FREEZE_TAG,
                "status": "verified",
            }
        )
        remote_raw = p.canonical_json_bytes(remote)
        remote_sha = hashlib.sha256(remote_raw).hexdigest()
        supervisor = remote_value(
            l._REMOTE_SUPERVISOR_KEYS,
            "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1",
        )
        supervisor.update(
            {
                "claim_sha256": claim_sha,
                "verifier_start_claim_sha256": start_sha,
                "remote_receipt_sha256": remote_sha,
                "status": "completed",
            }
        )
        supervisor_raw = p.canonical_json_bytes(supervisor)
        sources = {
            "claim": (pathlib.Path(p._WINDOWS_CLAIM), claim_raw),
            "start": (pathlib.Path(p._WINDOWS_START_CLAIM), start_raw),
            "remote": (pathlib.Path(p._WINDOWS_REMOTE_RECEIPT), remote_raw),
            "supervisor": (
                pathlib.Path(p._WINDOWS_SUPERVISOR_RECEIPT),
                supervisor_raw,
            ),
        }
        for source_path, raw in sources.values():
            source_path.write_bytes(raw)
            source_path.chmod(0o600)
        preparation_state = p._artifact_state(
            paths["preparation_receipt"],
            "preparation receipt",
            role="preparation_receipt",
            maximum=1 << 20,
        )
        verification_state = p._artifact_state(
            paths["preparation_verification_receipt"],
            "preparation verification receipt",
            role="preparation_verification_receipt",
            maximum=1 << 20,
        )
        context = p._ArmContext(
            execution_root=execution_root,
            authority=authority,
            open_commit=commit,
            registration=registration,
            preparation=preparation_state,
            preparation_verification=verification_state,
            preparation_valid=True,
            preparation_verification_valid=True,
            evidence_errors=(),
        )
        p._validate_prepared_state = lambda _args: context

        def accepted(raw, *args, **kwargs):
            value = p._parse_canonical_object(raw, "synthetic remote evidence")
            return value, hashlib.sha256(raw).hexdigest()

        p._validate_lifecycle_claim = accepted
        p._validate_start_claim = accepted
        p._validate_remote_receipt = accepted
        p._validate_supervisor_receipt = accepted
        arm_args = argparse.Namespace(
            repository_root=pathlib.Path("."),
            registration=pathlib.Path(p._REGISTRATION_PATH),
            execution_root=execution_root,
            preparation_receipt=paths["preparation_receipt"],
            preparation_verification_receipt=paths[
                "preparation_verification_receipt"
            ],
            windows_claim=pathlib.Path(p._WINDOWS_CLAIM),
            windows_verifier_start_claim=pathlib.Path(p._WINDOWS_START_CLAIM),
            windows_remote_receipt=pathlib.Path(p._WINDOWS_REMOTE_RECEIPT),
            windows_supervisor_receipt=pathlib.Path(p._WINDOWS_SUPERVISOR_RECEIPT),
            arm_receipt=paths["arm_receipt"],
        )
        assert p._arm(arm_args) == 0
        copied = {
            "claim": paths["remote_claim"],
            "start": paths["remote_verifier_claim"],
            "remote": paths["remote_receipt"],
            "supervisor": paths["remote_supervisor_receipt"],
        }
        for name, destination in copied.items():
            assert destination.read_bytes() == sources[name][1]
            assert destination.stat().st_mode & 0o777 == 0o444
        assert paths["arm_receipt"].stat().st_mode & 0o777 == 0o444

        l._PREPARATION = paths["preparation_receipt"]
        l._PREPARATION_VERIFICATION = paths["preparation_verification_receipt"]
        l._REMOTE_CLAIM = paths["remote_claim"]
        l._REMOTE_VERIFIER = paths["remote_verifier_claim"]
        l._REMOTE_RECEIPT = paths["remote_receipt"]
        l._REMOTE_SUPERVISOR = paths["remote_supervisor_receipt"]
        l._ARM = paths["arm_receipt"]
        l._validate_embedded_preparation_success = lambda *args, **kwargs: None
        l._validate_embedded_preparation_verification = lambda *args, **kwargs: None
        assert (
            l._remote_and_arm_stage(
                commit=commit,
                registration_sha=registration_sha,
                registration={},
                execution={},
            )
            is None
        )

        for role in roles:
            if role != "result_git_owner_claim" and not paths[role].exists():
                p._publish_bytes_exclusive(paths[role], b"{}", role, role=role)

        observed_bundle_roles = []
        real_evidence_state = l._evidence_state

        def observed_evidence_state(path, label, *, role, maximum=l._EVIDENCE_CAP):
            state = real_evidence_state(path, label, role=role, maximum=maximum)
            if role in {"normal_finalization_bundle", "emergency_result_bundle"}:
                assert state.read_status == "readable" and state.raw is not None
                observed_bundle_roles.append(role)
            return state

        l._evidence_state = observed_evidence_state
        l._FINAL_BUNDLE = paths["normal_finalization_bundle"]
        l._EMERGENCY_BUNDLE = paths["emergency_result_bundle"]
        try:
            l._selected_bundle(
                commit=commit,
                registration_sha=registration_sha,
                registration={},
            )
        except l.LifecycleError:
            pass
        else:
            raise AssertionError("synthetic invalid bundles unexpectedly validated")
        assert observed_bundle_roles == [
            "emergency_result_bundle",
            "normal_finalization_bundle",
        ]
        l._evidence_state = real_evidence_state

        l._EXECUTION_ROOT = execution_root
        l._OWNER_CLAIM = paths["result_git_owner_claim"]
        l._WORK_ROOT = execution_root / "result-git-work"
        owner, owner_raw, _work = l._ensure_owner(
            commit=commit,
            registration_sha=registration_sha,
            driver_raw=b"{}",
        )
        reopened_owner, reopened_raw, _work = l._ensure_owner(
            commit=commit,
            registration_sha=registration_sha,
            driver_raw=b"{}",
        )
        assert reopened_owner == owner and reopened_raw == owner_raw
        assert paths["result_git_owner_claim"].stat().st_mode & 0o777 == 0o600

        finalizer_constants = {
            "_PREPARATION": "preparation_receipt",
            "_PREPARATION_VERIFICATION": "preparation_verification_receipt",
            "_REMOTE_CLAIM": "remote_claim",
            "_REMOTE_VERIFIER_CLAIM": "remote_verifier_claim",
            "_REMOTE_RECEIPT": "remote_receipt",
            "_REMOTE_SUPERVISOR": "remote_supervisor_receipt",
            "_ARM": "arm_receipt",
            "_DRIVER": "lifecycle_driver_claim",
            "_LEDGER": "lifecycle_ledger",
            "_PROCESS_A_START": "process_a_start_claim",
            "_PROCESS_B_START": "process_b_start_claim",
            "_PROCESS_A_VALIDATOR": "process_a_validator_claim",
            "_PROCESS_B_VALIDATOR": "process_b_validator_claim",
            "_PROCESS_A_VALIDATION": "process_a_validation_receipt",
            "_PROCESS_B_VALIDATION": "process_b_validation_receipt",
            "_PROCESS_A": "process_a_payload",
            "_PROCESS_B": "process_b_payload",
        }
        for attribute, role in finalizer_constants.items():
            setattr(f, attribute, str(paths[role]))
        execution = {
            "scientific_argv_template": [
                "runner",
                "<LABEL>",
                "<START_CLAIM>",
                "<PRIOR_VALIDATION_OR_NULL>",
                "<OUTPUT_PATH>",
            ],
            "payload_validator_argv_template": [
                "validator",
                "<LABEL>",
                "<START_CLAIM>",
                "<VALIDATOR_CLAIM>",
                "<VALIDATION_RECEIPT>",
                "<OUTPUT_PATH>",
            ],
            "process_a_start_claim": str(paths["process_a_start_claim"]),
            "process_b_start_claim": str(paths["process_b_start_claim"]),
            "process_a_validator_claim": str(paths["process_a_validator_claim"]),
            "process_b_validator_claim": str(paths["process_b_validator_claim"]),
            "process_a_validation_receipt": str(
                paths["process_a_validation_receipt"]
            ),
            "process_b_validation_receipt": str(
                paths["process_b_validation_receipt"]
            ),
            "process_a_output": str(paths["process_a_payload"]),
            "process_b_output": str(paths["process_b_payload"]),
            "authority_root": str(authority),
            "process_a_root": str(execution_root / "process-a"),
            "process_b_root": str(execution_root / "process-b"),
            "lifecycle_driver_argv": [],
            "argv_hashes": {"remote_supervisor": None, "remote_verifier": None},
        }
        registration_value = {
            "content_sha256": registration_sha,
            "execution_contract": execution,
            "source_manifest": {
                "open_freeze_added_files": [
                    {
                        "path": "scripts/supervise_action_qbc_v8_remote_tag.py",
                        "git_blob_sha1": None,
                        "sha256": None,
                    },
                    {
                        "path": "scripts/verify_action_qbc_v8_remote_tag.py",
                        "git_blob_sha1": None,
                        "sha256": None,
                    },
                ]
            },
        }
        f._repository_and_registration = lambda _root: (
            commit,
            registration_value,
            b"registration",
        )
        f._require_argv = lambda *args, **kwargs: None
        f._authority_raw_audit = lambda *args, **kwargs: False
        observed_roles = []
        real_artifact = f._artifact

        def observed_artifact(path, *, role, name, keys=None, schema=None):
            observed_roles.append(role)
            artifact = real_artifact(path, role=role, name=name, keys=keys, schema=schema)
            assert artifact.read_status == "readable" and artifact.raw is not None
            return artifact

        f._artifact = observed_artifact

        def stop_rendering(*args, **kwargs):
            raise f._FinalizationError("synthetic post-reopen renderer stop")

        f._validate_machine_result = stop_rendering
        f._receipt_failure_bundle = lambda *args, **kwargs: {"reopened": True}
        os.chdir(authority)
        assert f._finalize(argparse.Namespace()) == {"reopened": True}
        assert observed_roles == [
            "preparation_receipt",
            "preparation_verification_receipt",
            "remote_claim",
            "remote_verifier_claim",
            "remote_receipt",
            "remote_supervisor_receipt",
            "arm_receipt",
            "lifecycle_driver_claim",
            "lifecycle_ledger",
            "process_a_start_claim",
            "process_a_validator_claim",
            "process_a_validation_receipt",
            "process_a_payload",
            "process_b_start_claim",
            "process_b_validator_claim",
            "process_b_validation_receipt",
            "process_b_payload",
        ]
        sys.stdout.write("producer-arm-consumers-ok\n")
        """
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(ROOT), str(evidence)],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "mode-matrix-ok\n"
    boundary_evidence = tmp_path / "boundary-evidence"
    boundary_evidence.mkdir(mode=0o700)
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            boundary_probe,
            str(ROOT),
            str(boundary_evidence),
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "producer-arm-consumers-ok\n"


@pytest.mark.skipif(os.name != "posix", reason="registered publisher is Linux-only")
def test_p8v7_publisher_full_wrapper_and_child_suffix_are_exact_and_disjoint() -> None:
    import copy

    renderer_row = {
        "mode": "100644",
        "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "git_blob_sha1": "a" * 40,
        "sha256": "b" * 64,
        "byte_count": 1,
    }
    execution = reconstruction._execution_contract([renderer_row])
    registration = {"execution_contract": execution}
    full = execution["result_publisher_argv"]
    assert full[:4] == [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "600s",
    ]
    assert len(full) == 23
    assert len(full[4:]) == 19
    assert full[4:8] == [
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
    ]
    assert (
        lifecycle._require_registered_execution(
            registration,
            publish_argv=full[4:],
        )
        is execution
    )
    with pytest.raises(lifecycle.LifecycleError, match="observed publish argv differs"):
        lifecycle._require_registered_execution(registration, publish_argv=full)

    child_mutations = {
        0: "/usr/bin/python3.12",
        1: "-E",
        2: "-s",
        3: "scripts/not-the-lifecycle.py",
        4: "execute",
        6: "not-dot",
    }
    for index, replacement in child_mutations.items():
        observed = list(full[4:])
        observed[index] = replacement
        with pytest.raises(lifecycle.LifecycleError, match="observed publish argv differs"):
            lifecycle._require_registered_execution(
                registration,
                publish_argv=observed,
            )
    reordered = list(full[4:])
    reordered[8:12] = reordered[10:12] + reordered[8:10]
    with pytest.raises(lifecycle.LifecycleError, match="observed publish argv differs"):
        lifecycle._require_registered_execution(registration, publish_argv=reordered)

    for index, replacement in {
        0: "/usr/local/bin/timeout",
        1: "--signal=KILL",
        2: "--kill-after=6s",
        3: "601s",
    }.items():
        candidate = copy.deepcopy(registration)
        candidate_full = candidate["execution_contract"]["result_publisher_argv"]
        candidate_full[index] = replacement
        candidate["execution_contract"]["argv_hashes"]["result_publisher"] = (
            lifecycle.canonical_sha256(candidate_full)
        )
        with pytest.raises(lifecycle.LifecycleError, match="wrapper"):
            lifecycle._require_registered_execution(
                candidate,
                publish_argv=candidate_full[4:],
            )


def _p8v7_publisher_main_probe(
    tmp_path: Path,
) -> tuple[Path, list[str], bytes]:
    import json

    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    driver = tmp_path / "driver.json"
    ledger = tmp_path / "ledger.json"
    normal = tmp_path / "normal.json"
    emergency = tmp_path / "emergency.json"
    tokens = [
        "publish",
        "--repository-root",
        ".",
        "--registration",
        "registration.json",
        "--driver-claim",
        str(driver),
        "--lifecycle-ledger",
        str(ledger),
        "--finalization-bundle",
        str(normal),
        "--emergency-bundle",
        str(emergency),
        "--control-time-seconds",
        "570",
    ]
    source = ROOT / "scripts/execute_action_qbc_v8_open_lifecycle.py"
    probe = (
        "import importlib.util,json,os,pathlib,sys\n"
        "source=pathlib.Path(sys.argv[1]); authority=pathlib.Path(sys.argv[2]); "
        "tokens=json.loads(sys.argv[3])\n"
        "spec=importlib.util.spec_from_file_location('_p8v7_publisher_main',source)\n"
        "module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; "
        "spec.loader.exec_module(module)\n"
        "module._AUTHORITY_ROOT=authority; module._REGISTRATION_PATH='registration.json'\n"
        "module._DRIVER=pathlib.Path(tokens[tokens.index('--driver-claim')+1])\n"
        "module._LEDGER=pathlib.Path(tokens[tokens.index('--lifecycle-ledger')+1])\n"
        "module._FINAL_BUNDLE=pathlib.Path(tokens[tokens.index('--finalization-bundle')+1])\n"
        "module._EMERGENCY_BUNDLE=pathlib.Path(tokens[tokens.index('--emergency-bundle')+1])\n"
        "def publish_result(**kwargs):\n"
        " expected=['/usr/bin/python3','-I','-B',module._SCRIPT_PATH,*tokens]\n"
        " assert kwargs['authority']==authority.resolve(strict=True)\n"
        " assert kwargs['observed_argv']==expected\n"
        " return 'e'*40\n"
        "module._publish_result=publish_result; module.sys.argv=[module._SCRIPT_PATH,*tokens]\n"
        "os.chdir(authority); raise SystemExit(module.main(tokens))\n"
    )
    wrapper = [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "600s",
        sys.executable,
        "-I",
        "-B",
        "-c",
        probe,
        str(source),
        str(authority),
        json.dumps(tokens, separators=(",", ":")),
    ]
    expected = lifecycle.canonical_json_bytes(
        {"result_commit_sha": "e" * 40, "status": "published"}
    ) + b"\n"
    return authority, wrapper, expected


@pytest.mark.skipif(os.name != "posix", reason="real GNU-timeout publisher subprocess")
def test_p8v7_in_lifecycle_timeout_wrapper_reaches_publisher_main(
    tmp_path: Path,
) -> None:
    authority, wrapper, _expected = _p8v7_publisher_main_probe(tmp_path)
    assert (
        lifecycle._run_publisher_once(
            wrapper,
            authority,
            deadline=lifecycle.time.monotonic() + 700,
        )
        == 0
    )


@pytest.mark.skipif(os.name != "posix", reason="real GNU-timeout publisher subprocess")
def test_p8v7_standalone_repeatable_wrapper_reaches_publisher_main_twice(
    tmp_path: Path,
) -> None:
    authority, wrapper, expected = _p8v7_publisher_main_probe(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
    for _ in range(2):
        completed = subprocess.run(
            wrapper,
            cwd=authority,
            env=environment,
            check=False,
            capture_output=True,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == expected
        assert completed.stderr == b""


def test_windows_remote_contract_is_cross_script_exact_and_environment_is_closed() -> None:
    expected_environment_keys = {
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "PATH",
        "PATHEXT",
        "HOME",
        "XDG_CONFIG_HOME",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_COUNT",
        "GIT_TERMINAL_PROMPT",
        "GIT_NO_REPLACE_OBJECTS",
        "GCM_INTERACTIVE",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
    }
    verifier_environment = remote_verifier._git_environment()
    supervisor_environment = supervisor._git_environment()
    assert set(verifier_environment) == expected_environment_keys
    assert len(verifier_environment) == 17
    assert verifier_environment == supervisor_environment
    assert "USERPROFILE" not in verifier_environment
    assert "GITHUB_TOKEN" not in verifier_environment
    assert verifier_environment["HOME"] == remote_verifier._NONEXISTENT_HOME
    assert remote_verifier._remote_policy() == supervisor._remote_policy()
    assert len(remote_verifier._remote_policy()) == 13
    assert remote_verifier._expected_verifier_argv() == supervisor._expected_verifier_argv()
    assert remote_verifier._expected_supervisor_argv() == supervisor._expected_supervisor_argv()


def test_windows_components_accept_canonical_registered_local_git_timeout(
    tmp_path: Path,
) -> None:
    renderer_row = {
        "mode": "100644",
        "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "git_blob_sha1": "a" * 40,
        "sha256": "b" * 64,
        "byte_count": 1,
    }
    execution = reconstruction._execution_contract([renderer_row])
    assert execution["local_git_timeout_seconds"] == 60
    assert (
        supervisor._REGISTERED_LOCAL_GIT_TIMEOUT_SECONDS
        == remote_verifier._REGISTERED_LOCAL_GIT_TIMEOUT_SECONDS
        == 60
    )
    assert (
        supervisor._WINDOWS_GIT_CHILD_TIMEOUT_SECONDS
        == remote_verifier._WINDOWS_GIT_CHILD_TIMEOUT_SECONDS
        == 60
    )

    rows: list[dict[str, Any]] = []
    for relative in (supervisor._SUPERVISOR_SCRIPT, supervisor._VERIFIER_SCRIPT):
        raw = (ROOT / relative).read_bytes()
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        rows.append(
            {
                "mode": "100644",
                "path": relative,
                "git_blob_sha1": hashlib.sha1(
                    b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
                    usedforsecurity=False,
                ).hexdigest(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        )
    rows.sort(key=lambda row: str(row["path"]).encode("utf-8"))
    manifest_preimage = {
        "preregistration_tree": [],
        "open_freeze_added_files": rows,
    }
    registration: dict[str, Any] = {
        key: None for key in supervisor._REGISTRATION_KEYS
    }
    registration.update(
        {
            "schema_version": supervisor._REGISTRATION_SCHEMA,
            "status": "registered_zero_result",
            "treatment_id": supervisor._TREATMENT_ID,
            "runtime_id": None,
            "preregistration": {
                "commit_sha": supervisor._PREREGISTRATION_COMMIT,
                "tag": supervisor._PREREGISTRATION_TAG,
                "document_path": supervisor._PREREGISTRATION_DOCUMENT,
                "document_git_blob_sha1": supervisor._PREREGISTRATION_DOCUMENT_BLOB,
                "document_sha256": supervisor._PREREGISTRATION_DOCUMENT_SHA256,
            },
            "authorization": dict(supervisor._AUTHORIZATION),
            "source_manifest": {
                **manifest_preimage,
                "manifest_sha256": supervisor.canonical_sha256(manifest_preimage),
            },
            "execution_contract": execution,
        }
    )
    unsigned = {key: value for key, value in registration.items() if key != "content_sha256"}
    registration["content_sha256"] = supervisor.canonical_sha256(unsigned)
    registration_path = tmp_path / supervisor._REGISTRATION_PATH
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.write_bytes(supervisor.canonical_json_bytes(registration))

    assert supervisor._load_registration(tmp_path).execution == execution
    assert remote_verifier._load_registration(tmp_path, registration_path).execution == execution


def test_windows_components_accept_the_registered_five_field_source_manifest_rows() -> None:
    path = "scripts/verify_action_qbc_v8_remote_tag.py"
    row = {
        "mode": "100644",
        "path": path,
        "git_blob_sha1": "a" * 40,
        "sha256": "b" * 64,
        "byte_count": 123,
    }
    for module in (remote_verifier, supervisor):
        preimage = {
            "preregistration_tree": [],
            "open_freeze_added_files": [row],
        }
        registration = {
            "source_manifest": {
                **preimage,
                "manifest_sha256": module.canonical_sha256(preimage),
            }
        }
        assert module._manifest_entry(registration, path) == row

        invalid_row = {key: value for key, value in row.items() if key != "mode"}
        invalid_preimage = {
            "preregistration_tree": [],
            "open_freeze_added_files": [invalid_row],
        }
        invalid = {
            "source_manifest": {
                **invalid_preimage,
                "manifest_sha256": module.canonical_sha256(invalid_preimage),
            }
        }
        with pytest.raises(module._ProtocolFailure):
            module._manifest_entry(invalid, path)


@pytest.mark.parametrize(
    (
        "spawned",
        "exit_code",
        "stdout",
        "stderr",
        "reason",
        "timed_out",
        "cleanup",
        "classification",
        "recorded_cleanup",
    ),
    [
        (False, None, b"", b"", "spawn_error", False, None, "spawn_error", None),
        (True, 124, b"", b"", "timeout", True, True, "retryable_timeout_124", True),
        (True, 1, b"x", b"", "stdout_limit", False, True, "stdout_limit", True),
        (True, 1, b"", b"e", "stderr_limit", False, True, "stderr_limit", True),
        (
            True,
            1,
            b"",
            b"",
            "child_cleanup_failed",
            False,
            False,
            "child_cleanup_failed",
            False,
        ),
        (True, 124, b"", b"", "overall_deadline", True, True, "overall_deadline", True),
        (True, 0, b"expected\n", b"", None, False, None, "verified", None),
        (True, 0, b"wrong\n", b"", None, False, None, "unexpected_output", None),
        (True, 0, b"", b"", None, False, None, "retryable_empty_exit_0", None),
        (True, 128, b"", b"git", None, False, None, "retryable_git_128", None),
        (True, 7, b"", b"", None, False, None, "unexpected_exit", None),
    ],
)
def test_verifier_attempt_classification_and_nullability_are_exact(
    spawned: bool,
    exit_code: int | None,
    stdout: bytes,
    stderr: bytes,
    reason: str | None,
    timed_out: bool,
    cleanup: bool | None,
    classification: str,
    recorded_cleanup: bool | None,
) -> None:
    result = remote_verifier._ManagedResult(
        spawned=spawned,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_milliseconds=17,
        reason=reason,
        timed_out=timed_out,
        cleanup_passes=cleanup,
    )
    record = remote_verifier._attempt_record(2, result, expected_stdout=b"expected\n")
    assert set(record) == remote_verifier._ATTEMPT_KEYS
    assert record["attempt_index"] == 2
    assert record["classification"] == classification
    assert record["child_cleanup_passes"] is recorded_cleanup
    assert record["stdout_size_bytes"] == len(stdout)
    assert record["stdout_sha256"] == hashlib.sha256(stdout).hexdigest()
    assert record["stderr_size_bytes"] == len(stderr)
    assert record["stderr_sha256"] == hashlib.sha256(stderr).hexdigest()


@pytest.mark.parametrize("selected_index", [1, 2, 3])
def test_verifier_remote_success_is_selectable_on_each_registered_attempt(
    selected_index: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifications = iter(
        ["retryable_empty_exit_0"] * (selected_index - 1) + ["verified"]
    )
    observed_indices: list[int] = []
    retry_points: list[int] = []

    def attempt(index: int, **_kwargs: object) -> dict[str, object]:
        observed_indices.append(index)
        return {"attempt_index": index, "classification": next(classifications)}

    def retry(prior_end_ns: int, _overall_deadline_ns: int) -> bool:
        retry_points.append(prior_end_ns)
        return True

    monkeypatch.setattr(remote_verifier, "_remote_attempt", attempt)
    monkeypatch.setattr(remote_verifier, "_sleep_retry", retry)
    attempts, selected = remote_verifier._run_attempts(
        live_admission_deadline_ns=10**30,
        cleanup_deadline_ns=10**30,
        expected_stdout=b"expected\n",
    )
    assert observed_indices == list(range(1, selected_index + 1))
    assert len(retry_points) == selected_index - 1
    assert [row["classification"] for row in attempts] == [
        "retryable_empty_exit_0"
    ] * (selected_index - 1) + ["verified"]
    assert selected == selected_index


def test_verifier_git_128_is_retryable_and_never_exceeds_three_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_indices: list[int] = []

    def attempt(index: int, **_kwargs: object) -> dict[str, object]:
        observed_indices.append(index)
        return {"attempt_index": index, "classification": "retryable_git_128"}

    monkeypatch.setattr(remote_verifier, "_remote_attempt", attempt)
    monkeypatch.setattr(remote_verifier, "_sleep_retry", lambda *_args: True)
    attempts, selected = remote_verifier._run_attempts(
        live_admission_deadline_ns=10**30,
        cleanup_deadline_ns=10**30,
        expected_stdout=b"expected\n",
    )
    assert observed_indices == [1, 2, 3]
    assert len(attempts) == 3
    assert selected is None


def test_verifier_never_retries_a_nonretryable_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def attempt(index: int, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"attempt_index": index, "classification": "unexpected_output"}

    def forbidden_retry(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("nonretryable evidence must stop immediately")

    monkeypatch.setattr(remote_verifier, "_remote_attempt", attempt)
    monkeypatch.setattr(remote_verifier, "_sleep_retry", forbidden_retry)
    attempts, selected = remote_verifier._run_attempts(
        live_admission_deadline_ns=10**30,
        cleanup_deadline_ns=10**30,
        expected_stdout=b"expected\n",
    )
    assert calls == 1
    assert [row["classification"] for row in attempts] == ["unexpected_output"]
    assert selected is None


def test_verifier_retry_delay_is_monotonic_and_deadline_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    clock = iter([15_000_000_000])
    monkeypatch.setattr(remote_verifier.time, "sleep", sleeps.append)
    monkeypatch.setattr(remote_verifier.time, "monotonic_ns", lambda: next(clock))
    assert remote_verifier._sleep_retry(0, 20_000_000_000) is True
    assert sleeps == [15]

    sleeps.clear()
    assert remote_verifier._sleep_retry(10_000_000_000, 20_000_000_000) is False
    assert sleeps == []


@pytest.mark.parametrize(
    "malformed",
    [
        b"0" * 40 + b"\trefs/tags/wrong\n",
        b"expected\nextra\n",
        b" expected\n",
    ],
)
def test_verifier_rejects_wrong_tag_hash_and_multiple_lines(malformed: bytes) -> None:
    result = remote_verifier._ManagedResult(
        spawned=True,
        exit_code=0,
        stdout=malformed,
        stderr=b"",
                    duration_milliseconds=0,
        reason=None,
        timed_out=False,
        cleanup_passes=None,
    )
    record = remote_verifier._attempt_record(
        1,
        result,
        expected_stdout=b"f" * 40 + b"\trefs/tags/correct\n",
    )
    assert record["classification"] == "unexpected_output"


@pytest.mark.parametrize(
    ("classification", "cleanup", "recorded_cleanup"),
    [
        ("verifier_completed", None, None),
        ("verifier_timeout_124", True, True),
        ("stdout_limit", True, True),
        ("stderr_limit", False, False),
        ("spawn_error", None, None),
        ("remote_receipt_missing", None, None),
        ("remote_receipt_invalid", None, None),
    ],
)
def test_supervisor_receipt_has_exact_schema_and_cleanup_nullability(
    classification: str,
    cleanup: bool | None,
    recorded_cleanup: bool | None,
) -> None:
    registration = supervisor._Registration(
        value={"content_sha256": "a" * 64},
        execution={"argv_hashes": {"remote_verifier": "b" * 64}},
        supervisor_manifest={},
        verifier_manifest={},
    )
    result = supervisor._ManagedResult(
        spawned=classification != "spawn_error",
        exit_code=None if classification == "spawn_error" else 1,
        stdout=b"",
        stderr=b"",
        duration_milliseconds=0,
        reason=None,
        timed_out=classification == "verifier_timeout_124",
        cleanup_passes=cleanup,
    )
    receipt = supervisor._supervisor_receipt_object(
        registration=registration,
        lifecycle_claim={"open_freeze_commit_sha": "c" * 40},
        lifecycle_claim_sha256="d" * 64,
        start_claim_sha256=None,
        remote_receipt_sha256=None,
        result=result,
        classification=classification,
        status="failed",
    )
    assert set(receipt) == supervisor._SUPERVISOR_RECEIPT_KEYS
    assert receipt["classification"] == classification
    assert receipt["child_cleanup_passes"] is recorded_cleanup


def test_remote_claim_publication_is_exclusive_for_both_windows_components(
    tmp_path: Path,
) -> None:
    for module, name in ((remote_verifier, "verifier"), (supervisor, "supervisor")):
        destination = tmp_path / f"{name}.json"
        expected = {"schema_version": "synthetic", "value": name}

        def validate(
            value: dict[str, Any], expected_value: dict[str, str] = expected
        ) -> None:
            assert value == expected_value

        raw = module._publish_canonical(destination, expected, validate, name)
        assert raw == module.canonical_json_bytes(expected)
        assert destination.read_bytes() == raw
        with pytest.raises(module._ProtocolFailure):
            module._publish_canonical(destination, expected, validate, name)
        assert destination.read_bytes() == raw


def test_windows_job_and_one_shot_supervisor_boundaries_are_statically_explicit() -> None:
    supervisor_source = (
        ROOT / "scripts/supervise_action_qbc_v8_remote_tag.py"
    ).read_text(encoding="utf-8")
    verifier_source = (ROOT / "scripts/verify_action_qbc_v8_remote_tag.py").read_text(
        encoding="utf-8"
    )
    assert "_CREATE_SUSPENDED | _CREATE_NEW_PROCESS_GROUP" in supervisor_source
    assert "_CREATE_SUSPENDED | _CREATE_NEW_PROCESS_GROUP" in verifier_source
    assert "_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in supervisor_source
    assert "_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in verifier_source
    supervisor_main = supervisor_source[supervisor_source.index("def main(") :]
    assert supervisor_main.count("_run_bounded_process(") == 1
    assert supervisor_main.index("_publish_canonical(") < supervisor_main.index(
        "_run_bounded_process("
    )
    assert "ls-remote" not in supervisor_source
    assert verifier_source.count('"ls-remote"') == 1
    assert supervisor._SUPERVISOR_DEADLINE_SECONDS == 480
    assert supervisor._SUPERVISOR_RECEIPT_RESERVE_SECONDS == 20
    assert supervisor._VERIFIER_CHILD_DEADLINE_SECONDS == 430
    assert supervisor._OVERALL_DEADLINE_SECONDS == 390


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_forced_termination_requires_taskkill_job_termination_and_zero_active_tree(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        pid = 123

        def __init__(self) -> None:
            self.exit_code: int | None = None

        def poll(self) -> int | None:
            return self.exit_code

        def wait(self, timeout: float) -> int:
            assert timeout > 0
            self.exit_code = 1
            return 1

    class FakeJob:
        def __init__(self) -> None:
            self.active = 1
            self.terminate_calls = 0

        def active_processes(self) -> int:
            return self.active

        def terminate(self) -> bool:
            self.terminate_calls += 1
            self.active = 0
            return True

    process = FakeProcess()
    job = FakeJob()
    taskkill_calls: list[int] = []

    def taskkill(pid: int, _deadline_ns: int) -> bool:
        taskkill_calls.append(pid)
        return True

    clock = iter([0, 1, 2])
    monkeypatch.setattr(module, "_run_taskkill", taskkill)
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: next(clock))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    assert module._cleanup_tree(process, job, deadline_ns=10) is True
    assert taskkill_calls == [123]
    assert job.terminate_calls == 1
    assert process.exit_code == 1


def test_preparation_command_ledger_and_hostile_git_environment_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = preparation._CommandLedger()
    ledger.record(
        attempt_index=None,
        label=None,
        phase="raw_audit",
        cwd=Path("/authority"),
        argv=["/usr/bin/git", "status"],
        stdin_bytes=b"",
        started=True,
        exit_code=0,
        outcome="completed",
        timed_out=False,
        duration_milliseconds=12,
        stdout=b"clean\n",
        stderr=b"",
        child_cleanup_passes=None,
    )
    ledger.record(
        attempt_index=1,
        label="A",
        phase="preflight",
        cwd=Path("/process-a"),
        argv=["/usr/local/bin/uv", "--version"],
        stdin_bytes=b"input",
        started=True,
        exit_code=7,
        outcome="nonzero",
        timed_out=False,
        duration_milliseconds=34,
        stdout=b"",
        stderr=b"failure",
        child_cleanup_passes=None,
    )
    assert [entry["sequence_index"] for entry in ledger.entries] == [0, 1]
    assert [entry["argv"] for entry in ledger.entries] == [
        ["/usr/bin/git", "status"],
        ["/usr/local/bin/uv", "--version"],
    ]
    assert [entry["exit_code"] for entry in ledger.entries] == [0, 7]
    assert [entry["outcome"] for entry in ledger.entries] == ["completed", "nonzero"]
    assert all(set(entry) == preparation._COMMAND_LEDGER_KEYS for entry in ledger.entries)
    assert ledger.entries[0]["stdout_sha256"] == hashlib.sha256(b"clean\n").hexdigest()
    assert ledger.entries[1]["stdin_sha256"] == hashlib.sha256(b"input").hexdigest()
    assert ledger.digest() == preparation.canonical_sha256(ledger.entries)

    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "/hostile/object-store")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "99")
    environment = preparation._command_environment()
    assert "GIT_OBJECT_DIRECTORY" not in environment
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["LC_ALL"] == "C"
    assert environment["LANG"] == "C"
    assert environment["TZ"] == "UTC"


def test_preparation_receipt_and_attempt_schemas_are_exact() -> None:
    assert {
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
    } == preparation._PREPARATION_KEYS
    assert {
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
    } == preparation._CLONE_KEYS
    assert {
        "sequence_index",
        "attempt_index",
        "label",
        "phase",
        "cwd",
        "argv",
        "argv_sha256",
        "stdin_size_bytes",
        "stdin_sha256",
        "started",
        "exit_code",
        "outcome",
        "timed_out",
        "duration_milliseconds",
        "stdout_size_bytes",
        "stdout_sha256",
        "stderr_size_bytes",
        "stderr_sha256",
        "child_cleanup_passes",
    } == preparation._COMMAND_LEDGER_KEYS
    assert {
        "attempt_index",
        "process_a_stage",
        "process_b_stage",
        "cleanup",
        "promotion",
        "passes",
    } == preparation._ATTEMPT_RECORD_KEYS
    assert {"owned_paths", "removed", "passes"} == preparation._CLEANUP_KEYS
    assert {
        "source_path",
        "destination_path",
        "source_device",
        "source_inode",
        "passes",
    } == preparation._PROMOTION_KEYS
    assert {
        "not_started",
        "clone_failed",
        "raw_audit_failed",
        "environment_failed",
        "preflight_failed",
        "completed",
    } == preparation._PROCESS_STAGES


def test_preparation_failure_attempt_preserves_nullability_and_owned_cleanup_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / ".prepare-attempt-1"
    destination = tmp_path / "processes"
    record_without_owner = preparation._failure_attempt_record(
        1,
        {"a": "not_started", "b": "not_started"},
        source,
        destination,
        None,
        False,
        True,
    )
    assert set(record_without_owner) == preparation._ATTEMPT_RECORD_KEYS
    assert record_without_owner["cleanup"] == {
        "owned_paths": [],
        "removed": [],
        "passes": True,
    }
    assert record_without_owner["promotion"] == {
        "source_path": str(source),
        "destination_path": str(destination),
        "source_device": None,
        "source_inode": None,
        "passes": False,
    }

    owned = preparation._OwnedStage(source, 2, 3, 4, b"marker")
    record_with_owner = preparation._failure_attempt_record(
        1,
        {"a": "completed", "b": "preflight_failed"},
        source,
        destination,
        owned,
        True,
        True,
    )
    assert record_with_owner["cleanup"] == {
        "owned_paths": [str(source)],
        "removed": [str(source)],
        "passes": True,
    }
    assert record_with_owner["promotion"]["source_device"] == 2
    assert record_with_owner["promotion"]["source_inode"] == 3


@pytest.mark.skipif(os.name != "posix", reason="Linux owner/mode/dirfd contract")
def test_preparation_owned_stage_cleanup_is_identity_bound_and_symlink_safe(
    tmp_path: Path,
) -> None:
    tmp_path.chmod(0o700)
    source = tmp_path / ".prepare-attempt-1"
    owned = preparation._create_owned_stage(source, 1)
    preparation._create_stage_children(owned)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"preserve")
    (source / "process-a" / "escape").symlink_to(outside, target_is_directory=True)
    assert preparation._cleanup_owned_stage(owned) is True
    assert not source.exists()
    assert sentinel.read_bytes() == b"preserve"


@pytest.mark.skipif(os.name != "posix", reason="Linux renameat2 contract")
def test_preparation_promotion_is_atomic_noreplace_and_preserves_inode(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir(mode=0o700)
    source_metadata = source.stat()
    preparation._rename_noreplace(source, destination)
    assert not source.exists()
    assert destination.stat().st_ino == source_metadata.st_ino
    assert destination.stat().st_dev == source_metadata.st_dev

    second_source = tmp_path / "second-source"
    second_source.mkdir(mode=0o700)
    with pytest.raises(preparation.ProtocolError):
        preparation._rename_noreplace(second_source, destination)
    assert second_source.is_dir()


@pytest.mark.skipif(os.name != "posix", reason="Linux immutable receipt publication")
def test_preparation_exclusive_publication_never_replaces_existing_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "receipt.json"
    paths = dict(preparation._EVIDENCE_PATHS_BY_ROLE)
    paths["preparation_receipt"] = destination
    monkeypatch.setattr(preparation, "_EVIDENCE_PATHS_BY_ROLE", paths)
    preparation._publish_bytes_exclusive(
        destination,
        b"first",
        "synthetic-receipt",
        role="preparation_receipt",
    )
    assert destination.read_bytes() == b"first"
    with pytest.raises(preparation.ProtocolError):
        preparation._publish_bytes_exclusive(
            destination,
            b"second",
            "synthetic-receipt",
            role="preparation_receipt",
        )
    assert destination.read_bytes() == b"first"


def test_post_arm_components_contain_no_remote_command_or_v7_output_path() -> None:
    for relative in (
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "scripts/validate_action_qbc_v8_open_payload.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        lowered = source.lower()
        assert "ls-remote" not in lowered
        assert "urllib" not in lowered
        assert "requests" not in lowered
        assert "import socket" not in lowered
        assert "artifacts/action_qbc_v7" not in lowered
        assert "action-qbc-v7-open-diagnostic-result" not in lowered


def test_invalid_arm_dependency_fails_before_driver_or_prior_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    def fake_receipt(
        _path: Path, *, keys: set[str], schema: str, name: str
    ) -> tuple[dict[str, Any], bytes]:
        del keys, schema
        observed.append(name)
        if name == "arm receipt":
            return (
                {
                    "schema_version": runner._ARM_SCHEMA,
                    "status": "failed",
                    "open_freeze_commit_sha": "a" * 40,
                    "registration_content_sha256": "b" * 64,
                },
                b"invalid-arm",
            )
        raise AssertionError("driver/prior receipt must not be accessed after invalid arm")

    monkeypatch.setattr(runner, "_validate_receipt", fake_receipt)
    monkeypatch.setattr(
        runner,
        "_validate_preparation_chain",
        lambda *_args, **_kwargs: ({}, b"preparation", {}, b"verification"),
    )
    with pytest.raises(runner._AdministrativeFailure, match="arm receipt"):
        runner._validate_dependencies(
            {"content_sha256": "b" * 64, "execution_contract": {}},
            label="A",
            process=runner._PROCESS["A"],
            open_commit="a" * 40,
        )
    assert observed == ["arm receipt"]


@pytest.mark.parametrize(
    ("failure", "expected_stage", "expected_child_count", "expected_sequence_length"),
    [
        (None, None, 5, 5),
        ("arm", "remote_verification_failed", 1, 1),
        ("a_runner", "process_a_nonzero", 2, 2),
        ("a_validator", "process_a_validation_failed", 3, 3),
        ("b_runner", "process_b_nonzero", 4, 4),
        ("b_validator", "process_b_validation_failed", 5, 5),
    ],
)
def test_lifecycle_orders_arm_a_validation_b_validation_without_retry_or_third_start(
    failure: str | None,
    expected_stage: str | None,
    expected_child_count: int,
    expected_sequence_length: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    child_index = 0

    def run_child(
        _argv: list[str],
        _cwd: Path,
        *,
        wrapper_seconds: int,
        deadline: float,
        reserve_seconds: int,
    ) -> int:
        del wrapper_seconds, deadline, reserve_seconds
        nonlocal child_index
        child_index += 1
        names = ["arm", "a_runner", "a_validator", "b_runner", "b_validator"]
        name = names[child_index - 1]
        events.append(name)
        return 1 if failure == name and name in {"a_runner", "b_runner"} else 0

    def authority_check(_authority: Path, _environment: dict[str, str]) -> None:
        events.append("authority_check")

    monkeypatch.setattr(lifecycle, "_run_child", run_child)
    monkeypatch.setattr(lifecycle, "_preparation_command_environment", lambda: {})
    monkeypatch.setattr(lifecycle, "_validate_authority_config", authority_check)
    monkeypatch.setattr(
        lifecycle,
        "_remote_and_arm_stage",
        lambda **_kwargs: "remote_verification_failed" if failure == "arm" else None,
    )
    monkeypatch.setattr(
        lifecycle,
        "_validation_is_valid",
        lambda _path, *, label, output: not (
            (failure == "a_validator" and label == "A")
            or (failure == "b_validator" and label == "B")
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "_optional_raw",
        lambda _path, *, role: b"payload",
    )
    monkeypatch.setattr(
        lifecycle,
        "_evidence_state",
        lambda _path, _label, *, role, maximum=lifecycle._EVIDENCE_CAP: (
            SimpleNamespace(raw=b"payload")
        ),
    )
    monkeypatch.setattr(lifecycle, "_plain_bytes", lambda *_args, **_kwargs: b"payload")
    execution = {
        "arm_argv": ["arm"],
        "scientific_argv_template": [
            "runner",
            "<LABEL>",
            "<START_CLAIM>",
            "<PRIOR_VALIDATION_OR_NULL>",
            "<OUTPUT_PATH>",
        ],
        "payload_validator_argv_template": [
            "validator",
            "<LABEL>",
            "<START_CLAIM>",
            "<VALIDATOR_CLAIM>",
            "<VALIDATION_RECEIPT>",
            "<OUTPUT_PATH>",
        ],
    }
    stage, arm_exit, sequence, process_a, process_b = lifecycle._run_registered_lifecycle(
        authority=Path("/synthetic-authority"),
        registration={"content_sha256": "a" * 64},
        execution=execution,
        commit="b" * 40,
        driver_raw=b"driver",
        deadline=float("inf"),
    )
    assert stage == expected_stage
    assert arm_exit == 0
    assert len(sequence) == expected_sequence_length
    assert sequence == list(lifecycle._SEQUENCE[:expected_sequence_length])
    child_events = [event for event in events if event != "authority_check"]
    assert child_events == [
        "arm",
        "a_runner",
        "a_validator",
        "b_runner",
        "b_validator",
    ][:expected_child_count]
    if failure == "arm":
        assert events == ["arm"]
    else:
        assert events[:2] == ["arm", "authority_check"]
    assert process_a["label"] == "A"
    assert process_b["label"] == "B"
    assert (process_a["runner_argv_sha256"] is not None) is (expected_child_count >= 2)
    assert (process_a["validator_argv_sha256"] is not None) is (
        expected_child_count >= 3
    )
    assert (process_b["runner_argv_sha256"] is not None) is (expected_child_count >= 4)
    assert (process_b["validator_argv_sha256"] is not None) is (
        expected_child_count >= 5
    )


def test_lifecycle_ledger_accepts_only_registered_order_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "_artifact_hash", lambda _path, *, role: None)
    process_a = lifecycle._process_record("A", Path("/a"))
    process_b = lifecycle._process_record("B", Path("/b"))
    for length in range(len(lifecycle._SEQUENCE) + 1):
        ledger = lifecycle._ledger_value(
            commit="a" * 40,
            registration_sha="b" * 64,
            driver_raw=b"driver",
            arm_exit=None,
            sequence=lifecycle._SEQUENCE[:length],
            process_a=process_a,
            process_b=process_b,
            stage="lifecycle_driver_failed",
        )
        assert ledger["sequence"] == list(lifecycle._SEQUENCE[:length])
    with pytest.raises(lifecycle.LifecycleError, match="registered prefix"):
        lifecycle._ledger_value(
            commit="a" * 40,
            registration_sha="b" * 64,
            driver_raw=b"driver",
            arm_exit=None,
            sequence=["process_a_runner_returned"],
            process_a=process_a,
            process_b=process_b,
            stage="lifecycle_driver_failed",
        )


@pytest.mark.skipif(os.name != "posix", reason="Linux driver-claim durability contract")
def test_lifecycle_driver_claim_is_exclusive_and_blocks_every_second_driver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(lifecycle, "_EXECUTION_ROOT", tmp_path)
    monkeypatch.setattr(lifecycle, "_DRIVER", tmp_path / "driver-claim.json")
    monkeypatch.setattr(lifecycle, "_REMOTE_CLAIM", tmp_path / "remote-claim.json")
    monkeypatch.setattr(lifecycle, "_REMOTE_VERIFIER", tmp_path / "remote-verifier.json")
    monkeypatch.setattr(lifecycle, "_REMOTE_RECEIPT", tmp_path / "remote-receipt.json")
    monkeypatch.setattr(lifecycle, "_REMOTE_SUPERVISOR", tmp_path / "supervisor.json")
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        lifecycle_driver_claim=lifecycle._DRIVER,
        remote_claim=lifecycle._REMOTE_CLAIM,
        remote_verifier_claim=lifecycle._REMOTE_VERIFIER,
        remote_receipt=lifecycle._REMOTE_RECEIPT,
        remote_supervisor_receipt=lifecycle._REMOTE_SUPERVISOR,
    )
    registration = {"content_sha256": "a" * 64}
    execution = {"argv_hashes": {"lifecycle_driver": "b" * 64}}
    claim, raw = lifecycle._acquire_driver_claim(
        commit="c" * 40,
        registration=registration,
        windows_claim_raw=b"windows-claim",
        execution=execution,
    )
    assert set(claim) == lifecycle._DRIVER_KEYS
    assert (tmp_path / "driver-claim.json").read_bytes() == raw
    with pytest.raises(lifecycle.LifecycleError, match="must be absent"):
        lifecycle._acquire_driver_claim(
            commit="c" * 40,
            registration=registration,
            windows_claim_raw=b"windows-claim",
            execution=execution,
        )
    assert (tmp_path / "driver-claim.json").read_bytes() == raw


@pytest.mark.parametrize("finalizer_outcome", [1, "spawn_error"])
def test_lifecycle_attempts_finalizer_once_then_uses_emergency_and_publisher_once(
    finalizer_outcome: int | str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_calls: list[list[str]] = []
    emergency_calls: list[tuple[str | None, str, int | None]] = []

    def run_child_evidence(
        argv: list[str],
        _cwd: Path,
        *,
        wrapper_seconds: int,
        deadline: float,
        reserve_seconds: int,
    ) -> lifecycle._ChildResult:
        del wrapper_seconds, deadline, reserve_seconds
        child_calls.append(argv)
        assert argv == ["finalizer"]
        if finalizer_outcome == "spawn_error":
            return lifecycle._ChildResult(False, None, None, None, "spawn_error")
        return lifecycle._ChildResult(True, int(finalizer_outcome), False, None, "nonzero")

    def emergency(
        _registration: dict[str, Any],
        *,
        commit: str,
        underlying_stage: str | None,
        finalizer: lifecycle._ChildResult,
    ) -> tuple[dict[str, Any], bytes]:
        assert commit == "a" * 40
        emergency_calls.append(
            (underlying_stage, finalizer.classification, finalizer.exit_code)
        )
        return {}, b"emergency"

    monkeypatch.setattr(
        lifecycle, "_publish_lifecycle_ledger", lambda **_kwargs: (b"ledger", True)
    )
    monkeypatch.setattr(lifecycle, "_validate_ledger_for_publish", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(lifecycle, "_run_child_evidence", run_child_evidence)
    monkeypatch.setattr(lifecycle, "_publish_emergency_bundle", emergency)
    monkeypatch.setattr(lifecycle, "_selected_bundle", lambda **_kwargs: ({}, []))

    def publisher_once(argv: list[str], *_args: object, **_kwargs: object) -> int:
        child_calls.append(argv)
        assert argv == ["publisher"]
        return 0

    monkeypatch.setattr(lifecycle, "_run_publisher_once", publisher_once)
    process_a = lifecycle._process_record("A", Path("/a"))
    process_b = lifecycle._process_record("B", Path("/b"))
    result = lifecycle._finish_lifecycle(
        authority=Path("/authority"),
        registration={"content_sha256": "b" * 64},
        execution={
            "finalizer_argv_template": ["finalizer"],
            "result_publisher_argv": ["publisher"],
        },
        commit="a" * 40,
        driver_raw=b"driver",
        deadline=float("inf"),
        stage="process_a_nonzero",
        arm_exit=0,
        sequence=lifecycle._SEQUENCE[:2],
        process_a=process_a,
        process_b=process_b,
    )
    assert result == 0
    assert child_calls.count(["finalizer"]) == 1
    assert child_calls.count(["publisher"]) == 1
    expected_exit = None if finalizer_outcome == "spawn_error" else 1
    expected_classification = "spawn_error" if finalizer_outcome == "spawn_error" else "nonzero"
    assert emergency_calls == [
        ("process_a_nonzero", expected_classification, expected_exit)
    ]


def test_finalizer_is_stdlib_only_and_has_no_project_import() -> None:
    source = (ROOT / "scripts/finalize_action_qbc_v8_open_diagnostic.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    permitted = {
        "__future__",
        "argparse",
        "base64",
        "collections",
        "dataclasses",
        "hashlib",
        "io",
        "json",
        "os",
        "pathlib",
        "platform",
        "re",
        "stat",
        "subprocess",
        "sys",
        "time",
        "typing",
        "csv",
        "email",
    }
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "__import__"}
    assert imports <= permitted


def test_finalizer_stage_precedence_is_exact_and_collision_stable() -> None:
    assert finalizer._first(finalizer._UNDERLYING_ORDER[::-1]) == (
        "preparation_receipt_invalid"
    )
    assert finalizer._first(["process_b_nonzero", "process_a_output_missing"]) == (
        "process_a_output_missing"
    )
    assert finalizer._first([]) is None


@pytest.mark.parametrize(
    ("disposition", "stage", "underlying"),
    [
        ("scientific_result", None, None),
        ("administrative_terminal", "remote_receipt_invalid", "remote_receipt_invalid"),
        (
            "administrative_terminal",
            "receipt_finalization_failed",
            "authority_identity_invalid",
        ),
    ],
)
def test_normal_result_documents_are_registered_and_deterministic(
    disposition: str,
    stage: str | None,
    underlying: str | None,
) -> None:
    registration = _result_contract_registration()
    commit = "d" * 40
    observed = finalizer._normal_document(
        registration,
        disposition=disposition,
        stage=stage,
        underlying_stage=underlying,
        commit=commit,
    )
    assert observed == finalizer._NORMAL_TEMPLATE.format(
        disposition=disposition,
        stage=stage if stage is not None else "null",
        underlying_stage=underlying if underlying is not None else "null",
        open_freeze_commit_sha=commit,
        registration_content_sha256="c" * 64,
    ).encode("ascii")
    assert observed.endswith(b"- authorization: all false\n")


def test_normal_bundle_is_self_hashed_and_path_sorted() -> None:
    registration = _result_contract_registration()
    bundle = finalizer._bundle(
        registration=registration,
        commit="d" * 40,
        disposition="administrative_terminal",
        stage="registration_invalid",
        underlying_stage="registration_invalid",
        files=[
            finalizer._file_object("z/path", b"z"),
            finalizer._file_object("a/path", b"a"),
        ],
    )
    claimed = bundle["content_sha256"]
    unsigned = dict(bundle)
    del unsigned["content_sha256"]
    assert claimed == hashlib.sha256(finalizer._canonical(unsigned)).hexdigest()
    assert [row["path"] for row in bundle["files"]] == ["a/path", "z/path"]


def test_receipt_failure_bundle_contains_only_the_deterministic_document() -> None:
    bundle = finalizer._receipt_failure_bundle(
        _result_contract_registration(),
        commit="d" * 40,
        underlying_stage="lifecycle_ledger_invalid",
    )
    assert bundle["disposition"] == "administrative_terminal"
    assert bundle["stage"] == "receipt_finalization_failed"
    assert bundle["underlying_stage"] == "lifecycle_ledger_invalid"
    assert [row["path"] for row in bundle["files"]] == [
        "docs/action_qbc_v8_open_diagnostic_result.md"
    ]


def _publisher_test_git(authority: Path, *arguments: str) -> bytes:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "XDG_CONFIG_HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    completed = subprocess.run(
        [lifecycle._GIT, *arguments],
        cwd=authority,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return completed.stdout


def _publisher_result_transaction(work_root: Path) -> dict[str, Any]:
    result_tag_ref = f"refs/tags/{lifecycle._RESULT_TAG}"
    result_branch_ref = lifecycle._RESULT_BRANCH_REF
    authority = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4/authority"
    local_root = "/mnt/d/kaggle competitions/arc3-crosslevel-voi"
    result_path_sets = {
        "scientific_result": [
            "artifacts/action_qbc_v8_open_diagnostic.json",
            "artifacts/action_qbc_v8_open_diagnostic_receipt.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ],
        "administrative_terminal": [
            "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
            "docs/action_qbc_v8_open_diagnostic_result.md",
        ],
        "receipt_finalization_failed": [
            "docs/action_qbc_v8_open_diagnostic_result.md"
        ],
        "finalizer_process_failed": ["docs/action_qbc_v8_open_diagnostic_result.md"],
    }
    return {
        "authoritative_tag": result_tag_ref,
        "forbidden_authority_branch": result_branch_ref,
        "commit_message": "Record action-QBC v8 open diagnostic result\n",
        "git_plumbing_argvs": [
            [lifecycle._GIT, "--no-replace-objects", "read-tree", "<O8_COMMIT>"],
            [
                lifecycle._GIT,
                "--no-replace-objects",
                "hash-object",
                "-w",
                "--stdin",
            ],
            [
                lifecycle._GIT,
                "--no-replace-objects",
                "update-index",
                "--add",
                "--cacheinfo",
                "100644,<FILE_BLOB>,<FILE_PATH>",
            ],
            [lifecycle._GIT, "--no-replace-objects", "write-tree"],
            [
                lifecycle._GIT,
                "--no-replace-objects",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "i18n.commitEncoding=UTF-8",
                "commit-tree",
                "<RESULT_TREE>",
                "-p",
                "<O8_COMMIT>",
            ],
            [
                lifecycle._GIT,
                "--no-replace-objects",
                "diff-tree",
                "--no-commit-id",
                "--name-status",
                "-r",
                "-z",
                "<O8_COMMIT>",
                "<R8_COMMIT>",
            ],
            [
                lifecycle._GIT,
                "--no-replace-objects",
                "cat-file",
                "-p",
                "<R8_COMMIT>",
            ],
        ],
        "scratch_index_path": str(work_root / "index-<i>"),
        "scratch_lock_path": str(work_root / "index-<i>.lock"),
        "scratch_tag_path": str(work_root / "result-tag-<i>"),
        "scratch_tag_bytes": "<R8_COMMIT>\n",
        "scratch_tag_mode": "0444",
        "result_path_sets": result_path_sets,
        "local_transfer_argvs": [
            [
                lifecycle._GIT,
                "-C",
                local_root,
                "fetch",
                "--no-tags",
                f"file://{authority}",
                f"{result_tag_ref}:{result_branch_ref}",
            ],
            [
                lifecycle._GIT,
                "-C",
                local_root,
                "fetch",
                "--no-tags",
                f"file://{authority}",
                f"{result_tag_ref}:{result_tag_ref}",
            ],
        ],
        "windows_publication_argvs": [
            [
                r"C:\Users\User\anaconda3\Library\bin\git.exe",
                "push",
                "origin",
                f"{result_branch_ref}:{result_branch_ref}",
            ],
            [
                r"C:\Users\User\anaconda3\Library\bin\git.exe",
                "push",
                "origin",
                f"{result_tag_ref}:{result_tag_ref}",
            ],
            [
                r"C:\Users\User\anaconda3\Library\bin\git.exe",
                "-c",
                "credential.interactive=never",
                "ls-remote",
                "--refs",
                "origin",
                result_branch_ref,
                result_tag_ref,
            ],
        ],
    }


def _publisher_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    path_set: str = "scientific_result",
) -> SimpleNamespace:
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    authority.chmod(0o700)
    _publisher_test_git(authority, "init", "--quiet")
    for key, value in (
        ("core.autocrlf", "false"),
        ("core.eol", "lf"),
        ("core.safecrlf", "true"),
    ):
        _publisher_test_git(authority, "config", "--local", key, value)
    (authority / "baseline.txt").write_bytes(b"synthetic O8 baseline\n")
    _publisher_test_git(authority, "add", "--", "baseline.txt")
    _publisher_test_git(
        authority,
        "-c",
        "user.name=Synthetic O8",
        "-c",
        "user.email=synthetic-o8@invalid.example",
        "commit",
        "--quiet",
        "-m",
        "Synthetic O8",
    )
    parent = _publisher_test_git(authority, "rev-parse", "HEAD").decode("ascii").strip()

    execution_root = tmp_path / "execution"
    execution_root.mkdir(mode=0o700)
    execution_root.chmod(0o700)
    work_root = execution_root / "result-git-work"
    monkeypatch.setattr(lifecycle, "_EXECUTION_ROOT", execution_root)
    monkeypatch.setattr(lifecycle, "_OWNER_CLAIM", execution_root / "result-git-owner.json")
    monkeypatch.setattr(lifecycle, "_WORK_ROOT", work_root)
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        result_git_owner_claim=lifecycle._OWNER_CLAIM,
    )
    monkeypatch.setattr(
        lifecycle,
        "_GIT_CONTROL_DEADLINE",
        lifecycle.time.monotonic() + 600,
    )

    transaction = _publisher_result_transaction(work_root)
    execution = {
        "result_git_environment": lifecycle._base_git_environment(
            authority, work_root / "index-<i>"
        ),
        "result_ref_transaction": transaction,
    }
    registration_sha = "3" * 64
    driver_raw = b'{"synthetic":"driver claim"}\n'
    _owner, _owner_raw, work = lifecycle._ensure_owner(
        commit=parent,
        registration_sha=registration_sha,
        driver_raw=driver_raw,
    )
    all_files = {
        "artifacts/action_qbc_v8_open_diagnostic.json": b'{"synthetic":"result"}\n',
        "artifacts/action_qbc_v8_open_diagnostic_receipt.json": (
            b'{"synthetic":"receipt"}\n'
        ),
        "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json": (
            b'{"synthetic":"administrative terminal"}\n'
        ),
        "docs/action_qbc_v8_open_diagnostic_result.md": b"# Synthetic result\n",
    }
    paths = transaction["result_path_sets"][path_set]
    files = [(path, all_files[path]) for path in paths]
    bundle_path = execution_root / "synthetic-immutable-bundle.json"
    bundle_raw = b'{"synthetic":"immutable bundle"}\n'
    bundle_path.write_bytes(bundle_raw)
    bundle_path.chmod(0o600)
    monkeypatch.setattr(lifecycle, "_FINAL_BUNDLE", bundle_path)
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        normal_finalization_bundle=bundle_path,
    )
    environment = lifecycle._publisher_environment(
        execution, authority, work_root / "index-1"
    )
    return SimpleNamespace(
        authority=authority,
        bundle_path=bundle_path,
        bundle_raw=bundle_raw,
        environment=environment,
        execution=execution,
        files=files,
        parent=parent,
        path_set=path_set,
        work=work,
        work_root=work_root,
    )


def _publisher_publish_attempt(fixture: SimpleNamespace, *, attempt: int = 1) -> str:
    return lifecycle._publication_attempt(
        fixture.authority,
        fixture.execution,
        attempt=attempt,
        parent=fixture.parent,
        bundle_path=fixture.bundle_path,
        bundle_raw=fixture.bundle_raw,
        files=fixture.files,
        work=fixture.work,
    )


def _publisher_object_snapshot(authority: Path) -> tuple[tuple[str, str], ...]:
    object_root = authority / ".git" / "objects"
    return tuple(
        sorted(
            (
                path.relative_to(object_root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in object_root.rglob("*")
            if path.is_file()
        )
    )


def _publisher_assert_tag_integrity(fixture: SimpleNamespace, commit: str) -> None:
    scratch = fixture.work_root / "result-tag-1"
    authoritative = (
        fixture.authority / ".git" / "refs" / "tags" / lifecycle._RESULT_TAG
    )
    expected = f"{commit}\n".encode("ascii")
    assert scratch.read_bytes() == expected
    assert authoritative.read_bytes() == expected
    scratch_stat = scratch.stat(follow_symlinks=False)
    authoritative_stat = authoritative.stat(follow_symlinks=False)
    assert (scratch_stat.st_dev, scratch_stat.st_ino) == (
        authoritative_stat.st_dev,
        authoritative_stat.st_ino,
    )
    assert scratch_stat.st_nlink == authoritative_stat.st_nlink == 2
    assert scratch_stat.st_mode & 0o777 == 0o444
    assert authoritative_stat.st_mode & 0o777 == 0o444


@pytest.mark.skipif(os.name != "posix", reason="Linux Git object publication contract")
@pytest.mark.parametrize(
    "path_set",
    [
        "scientific_result",
        "administrative_terminal",
        "receipt_finalization_failed",
        "finalizer_process_failed",
    ],
)
def test_publisher_exact_r8_direct_child_and_terminal_path_set_exclusivity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_set: str,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch, path_set=path_set)
    commit = _publisher_publish_attempt(fixture)
    paths = [path for path, _raw in fixture.files]

    transaction = lifecycle._result_transaction(fixture.execution)
    assert transaction["result_path_sets"][path_set] == paths
    assert transaction["local_transfer_argvs"] == _publisher_result_transaction(
        fixture.work_root
    )["local_transfer_argvs"]
    assert transaction["windows_publication_argvs"] == _publisher_result_transaction(
        fixture.work_root
    )["windows_publication_argvs"]
    assert _publisher_test_git(
        fixture.authority, "rev-list", "--parents", "-n", "1", commit
    ).decode("ascii").split() == [commit, fixture.parent]
    assert lifecycle._git(
        fixture.authority,
        fixture.environment,
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        "-z",
        fixture.parent,
        commit,
    ) == lifecycle._expected_delta(paths)
    commit_raw = lifecycle._git(
        fixture.authority, fixture.environment, "cat-file", "-p", commit
    )
    assert lifecycle._git_oid("commit", commit_raw) == commit
    lifecycle._validate_result_commit(
        fixture.authority,
        fixture.environment,
        commit=commit,
        parent=fixture.parent,
        files=fixture.files,
    )
    for path, raw in fixture.files:
        blob = _publisher_test_git(
            fixture.authority, "rev-parse", f"{commit}:{path}"
        ).decode("ascii").strip()
        assert blob == lifecycle._git_oid("blob", raw)
    lifecycle._require_branch_absent(fixture.authority, fixture.environment)
    _publisher_assert_tag_integrity(fixture, commit)


@pytest.mark.skipif(os.name != "posix", reason="Linux isolated Git environment contract")
def test_publisher_tolerates_dirty_authority_scrubs_inherited_git_state_and_ignores_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch)
    baseline = fixture.authority / "baseline.txt"
    baseline.write_bytes(b"staged authority bytes\n")
    _publisher_test_git(fixture.authority, "add", "--", "baseline.txt")
    baseline.write_bytes(b"unstaged authority bytes\n")
    (fixture.authority / "untracked.txt").write_bytes(b"untracked authority bytes\n")
    status_before = _publisher_test_git(
        fixture.authority, "status", "--porcelain=v2", "--untracked-files=all"
    )
    default_index = fixture.authority / ".git" / "index"
    default_index_before = default_index.read_bytes()

    hook = fixture.authority / ".git" / "hooks" / "reference-transaction"
    hook.write_bytes(
        b"#!/bin/sh\nprintf invoked > \"$GIT_DIR/reference-hook-invoked\"\nexit 97\n"
    )
    hook.chmod(0o755)
    hostile = {
        "GIT_OBJECT_DIRECTORY": "/hostile/object-directory",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/hostile/alternates",
        "GIT_INDEX_FILE": "/hostile/index",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "alias.cat-file",
        "GIT_CONFIG_VALUE_0": "!exit 91",
        "GIT_NAMESPACE": "hostile-namespace",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)

    real_popen = subprocess.Popen
    observed_environments: list[dict[str, str]] = []

    def recording_popen(*args: Any, **kwargs: Any) -> Any:
        environment = kwargs.get("env")
        if isinstance(environment, dict):
            observed_environments.append(dict(environment))
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(lifecycle.subprocess, "Popen", recording_popen)
    lifecycle._validate_authority_config(fixture.authority, fixture.environment)
    commit = _publisher_publish_attempt(fixture)

    publisher_environments = [
        environment
        for environment in observed_environments
        if environment.get("GIT_DIR") == str(fixture.authority / ".git")
    ]
    assert publisher_environments
    assert all(environment == fixture.environment for environment in publisher_environments)
    inherited_only = set(hostile) - {"GIT_INDEX_FILE"}
    assert all(not inherited_only & set(environment) for environment in publisher_environments)
    assert all(
        environment["GIT_INDEX_FILE"] == str(fixture.work_root / "index-1")
        for environment in publisher_environments
    )
    assert all(
        environment["GIT_INDEX_FILE"] != hostile["GIT_INDEX_FILE"]
        for environment in publisher_environments
    )
    assert default_index.read_bytes() == default_index_before
    assert _publisher_test_git(
        fixture.authority, "status", "--porcelain=v2", "--untracked-files=all"
    ) == status_before
    assert not (fixture.authority / ".git" / "reference-hook-invoked").exists()
    _publisher_assert_tag_integrity(fixture, commit)


@pytest.mark.skipif(os.name != "posix", reason="Linux fail-before-write tag lock contract")
def test_publisher_refuses_authority_tag_lock_before_any_object_or_scratch_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch)
    lock = (
        fixture.authority
        / ".git"
        / "refs"
        / "tags"
        / f"{lifecycle._RESULT_TAG}.lock"
    )
    lock.write_bytes(b"synthetic foreign lock\n")
    lock.chmod(0o600)
    objects_before = _publisher_object_snapshot(fixture.authority)
    work_before = sorted(path.name for path in fixture.work_root.iterdir())

    with pytest.raises(lifecycle.LifecycleError, match="result-tag lock must be absent"):
        _publisher_publish_attempt(fixture)

    assert _publisher_object_snapshot(fixture.authority) == objects_before
    assert sorted(path.name for path in fixture.work_root.iterdir()) == work_before == [
        ".owner"
    ]
    assert lock.read_bytes() == b"synthetic foreign lock\n"
    assert not (
        fixture.authority / ".git" / "refs" / "tags" / lifecycle._RESULT_TAG
    ).exists()


@pytest.mark.skipif(os.name != "posix", reason="Linux owned scratch recovery contract")
def test_publisher_recovers_verified_owned_partial_index_and_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch)
    index = fixture.work_root / "index-1"
    lock = fixture.work_root / "index-1.lock"
    index.write_bytes(b"verified-owned partial index")
    lock.write_bytes(b"verified-owned partial lock")
    index.chmod(0o600)
    lock.chmod(0o600)

    commit = _publisher_publish_attempt(fixture)

    assert not lock.exists()
    assert index.read_bytes() != b"verified-owned partial index"
    entries = lifecycle._git(
        fixture.authority, fixture.environment, "ls-files", "--stage", "-z"
    ).rstrip(b"\0").split(b"\0")
    indexed_paths = sorted(entry.split(b"\t", 1)[1].decode("utf-8") for entry in entries)
    assert indexed_paths == sorted(["baseline.txt", *[path for path, _raw in fixture.files]])
    _publisher_assert_tag_integrity(fixture, commit)


@pytest.mark.skipif(os.name != "posix", reason="Linux crash-before-link recovery contract")
def test_publisher_recovers_deterministically_after_crash_before_authoritative_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch)
    original_link = lifecycle._link_authoritative_tag
    constructed_commits: list[str] = []

    def crash_before_link(*args: Any, **kwargs: Any) -> str:
        del args
        constructed_commits.append(str(kwargs["commit"]))
        raise lifecycle._AttemptError("synthetic crash before link")

    monkeypatch.setattr(lifecycle, "_link_authoritative_tag", crash_before_link)
    with pytest.raises(lifecycle._AttemptError, match="synthetic crash before link"):
        _publisher_publish_attempt(fixture)
    assert len(constructed_commits) == 1
    assert not (
        fixture.authority / ".git" / "refs" / "tags" / lifecycle._RESULT_TAG
    ).exists()
    scratch = fixture.work_root / "result-tag-1"
    assert scratch.read_bytes() == f"{constructed_commits[0]}\n".encode("ascii")
    assert scratch.stat(follow_symlinks=False).st_nlink == 1
    objects_after_crash = _publisher_object_snapshot(fixture.authority)

    monkeypatch.setattr(lifecycle, "_link_authoritative_tag", original_link)
    recovered = _publisher_publish_attempt(fixture)

    assert recovered == constructed_commits[0]
    assert _publisher_object_snapshot(fixture.authority) == objects_after_crash
    _publisher_assert_tag_integrity(fixture, recovered)


@pytest.mark.skipif(os.name != "posix", reason="Linux crash-after-link recovery contract")
def test_publisher_crash_after_link_recovers_idempotently_without_new_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _publisher_fixture(tmp_path, monkeypatch)
    original_link = lifecycle._link_authoritative_tag
    linked_commits: list[str] = []

    def crash_after_link(*args: Any, **kwargs: Any) -> str:
        commit = original_link(*args, **kwargs)
        linked_commits.append(commit)
        raise lifecycle._AttemptError("synthetic crash after link")

    monkeypatch.setattr(lifecycle, "_link_authoritative_tag", crash_after_link)
    with pytest.raises(lifecycle._AttemptError, match="synthetic crash after link"):
        _publisher_publish_attempt(fixture)
    assert len(linked_commits) == 1
    commit = linked_commits[0]
    _publisher_assert_tag_integrity(fixture, commit)
    authoritative = (
        fixture.authority / ".git" / "refs" / "tags" / lifecycle._RESULT_TAG
    )
    tag_identity_before = (
        authoritative.stat(follow_symlinks=False).st_dev,
        authoritative.stat(follow_symlinks=False).st_ino,
    )
    index_before = (fixture.work_root / "index-1").read_bytes()
    objects_before = _publisher_object_snapshot(fixture.authority)

    monkeypatch.setattr(lifecycle, "_link_authoritative_tag", original_link)
    recovered = _publisher_publish_attempt(fixture)

    assert recovered == commit
    assert _publisher_object_snapshot(fixture.authority) == objects_before
    assert (fixture.work_root / "index-1").read_bytes() == index_before
    assert (
        authoritative.stat(follow_symlinks=False).st_dev,
        authoritative.stat(follow_symlinks=False).st_ino,
    ) == tag_identity_before
    _publisher_assert_tag_integrity(fixture, recovered)


def _finalizer_completion_empty_process(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "output_path": finalizer._PROCESS_A if label == "A" else finalizer._PROCESS_B,
        "exit_code": None,
        "validator_exit_code": None,
        "start_claim": None,
        "start_claim_sha256": None,
        "validator_claim": None,
        "validator_claim_sha256": None,
        "validation_receipt": None,
        "validation_receipt_sha256": None,
        "payload_exists": False,
        "payload_valid": False,
        "payload_sha256": None,
        "payload_size_bytes": None,
    }


def _finalizer_completion_admin_fixture(
    stage: str = "lifecycle_ledger_invalid",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registration = _result_contract_registration()
    commit = "d" * 40
    terminal = {
        "schema_version": finalizer._ADMIN_SCHEMA,
        "treatment_id": finalizer._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": finalizer._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration["content_sha256"],
        "preparation_receipt": None,
        "preparation_receipt_exists": False,
        "preparation_receipt_read_status": "absent",
        "preparation_receipt_sha256": None,
        "preparation_verification_receipt": None,
        "preparation_verification_receipt_exists": False,
        "preparation_verification_receipt_read_status": "absent",
        "preparation_verification_receipt_sha256": None,
        "remote_verification_claim": None,
        "remote_verifier_claim": None,
        "remote_verification_receipt": None,
        "remote_supervisor_receipt": None,
        "arm_receipt": None,
        "lifecycle_driver_claim": None,
        "lifecycle_ledger": None,
        "process_a": _finalizer_completion_empty_process("A"),
        "process_b": _finalizer_completion_empty_process("B"),
        "payloads_byte_identical": None,
        "stage": stage,
        "authorization": dict(finalizer._AUTHORIZATION),
    }
    document = finalizer._normal_document(
        registration,
        disposition="administrative_terminal",
        stage=stage,
        underlying_stage=stage,
        commit=commit,
    )
    bundle = finalizer._bundle(
        registration=registration,
        commit=commit,
        disposition="administrative_terminal",
        stage=stage,
        underlying_stage=stage,
        files=[
            finalizer._file_object(
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                finalizer._canonical(terminal),
            ),
            finalizer._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md",
                document,
            ),
        ],
    )
    return registration, terminal, bundle


def _finalizer_completion_validate_admin(
    registration: dict[str, Any], bundle: dict[str, Any]
) -> None:
    finalizer._validate_final_bundle(
        bundle,
        registration=registration,
        registration_file_sha256="e" * 64,
        commit="d" * 40,
    )


def test_finalizer_completion_every_underlying_precedence_collision_is_stable() -> None:
    order = list(finalizer._UNDERLYING_ORDER)
    for left_index, left in enumerate(order):
        assert finalizer._first([left, left]) == left
        for right_index, right in enumerate(order):
            expected = order[min(left_index, right_index)]
            assert finalizer._first([left, right]) == expected
            assert finalizer._first([right, left]) == expected


def _finalizer_completion_ledger_execution() -> dict[str, Any]:
    return {
        "process_a_root": str(finalizer._EXECUTION_ROOT / "processes/process-a"),
        "process_a_start_claim": finalizer._PROCESS_A_START,
        "process_a_validator_claim": finalizer._PROCESS_A_VALIDATOR,
        "process_a_validation_receipt": finalizer._PROCESS_A_VALIDATION,
        "process_a_output": finalizer._PROCESS_A,
        "process_b_root": str(finalizer._EXECUTION_ROOT / "processes/process-b"),
        "process_b_start_claim": finalizer._PROCESS_B_START,
        "process_b_validator_claim": finalizer._PROCESS_B_VALIDATOR,
        "process_b_validation_receipt": finalizer._PROCESS_B_VALIDATION,
        "process_b_output": finalizer._PROCESS_B,
        "scientific_argv_template": finalizer._expected_scientific_argv(),
        "payload_validator_argv_template": finalizer._expected_validator_argv(),
    }


def test_finalizer_completion_rejects_inconsistent_exit_order_and_artifact_evidence() -> None:
    import copy

    execution = _finalizer_completion_ledger_execution()
    record = {
        "label": "A",
        "cwd": execution["process_a_root"],
        "runner_argv_sha256": None,
        "runner_exit_code": None,
        "validator_argv_sha256": None,
        "validator_exit_code": None,
        "start_claim_sha256": None,
        "validator_claim_sha256": None,
        "validation_receipt_sha256": None,
        "output_sha256": None,
    }
    assert finalizer._ledger_process_valid(
        record,
        label="A",
        execution=execution,
        sequence=[],
    )
    scientific = finalizer._substituted_argv(
        execution["scientific_argv_template"],
        {
            "<LABEL>": "A",
            "<START_CLAIM>": finalizer._PROCESS_A_START,
            "<PRIOR_VALIDATION_OR_NULL>": "null",
            "<OUTPUT_PATH>": finalizer._PROCESS_A,
        },
        "scientific",
    )
    validator_argv = finalizer._substituted_argv(
        execution["payload_validator_argv_template"],
        {
            "<LABEL>": "A",
            "<START_CLAIM>": finalizer._PROCESS_A_START,
            "<VALIDATOR_CLAIM>": finalizer._PROCESS_A_VALIDATOR,
            "<VALIDATION_RECEIPT>": finalizer._PROCESS_A_VALIDATION,
            "<OUTPUT_PATH>": finalizer._PROCESS_A,
        },
        "validator",
    )
    runner_hash = hashlib.sha256(finalizer._canonical(scientific)).hexdigest()
    validator_hash = hashlib.sha256(finalizer._canonical(validator_argv)).hexdigest()
    digest = "a" * 64

    returned = copy.deepcopy(record)
    returned.update(
        {
            "runner_argv_sha256": runner_hash,
            "runner_exit_code": 0,
            "start_claim_sha256": digest,
            "output_sha256": digest,
        }
    )
    assert finalizer._ledger_process_valid(
        returned,
        label="A",
        execution=execution,
        sequence=finalizer._SEQUENCE[:2],
    )
    validated = copy.deepcopy(returned)
    validated.update(
        {
            "validator_argv_sha256": validator_hash,
            "validator_exit_code": 0,
            "validator_claim_sha256": "b" * 64,
            "validation_receipt_sha256": "c" * 64,
        }
    )
    assert finalizer._ledger_process_valid(
        validated,
        label="A",
        execution=execution,
        sequence=finalizer._SEQUENCE[:3],
    )

    impossible: list[tuple[dict[str, Any], list[str]]] = []
    exit_without_return = copy.deepcopy(record)
    exit_without_return["runner_exit_code"] = 1
    impossible.append((exit_without_return, []))
    zero_without_claim_or_output = copy.deepcopy(record)
    zero_without_claim_or_output.update(
        {"runner_argv_sha256": runner_hash, "runner_exit_code": 0}
    )
    impossible.append((zero_without_claim_or_output, finalizer._SEQUENCE[:2]))
    output_without_start = copy.deepcopy(record)
    output_without_start.update(
        {"runner_argv_sha256": runner_hash, "output_sha256": digest}
    )
    impossible.append((output_without_start, []))
    validation_without_claim = copy.deepcopy(returned)
    validation_without_claim.update(
        {
            "validator_argv_sha256": validator_hash,
            "validation_receipt_sha256": digest,
        }
    )
    impossible.append((validation_without_claim, finalizer._SEQUENCE[:2]))
    validator_zero_without_receipt = copy.deepcopy(returned)
    validator_zero_without_receipt.update(
        {"validator_argv_sha256": validator_hash, "validator_exit_code": 0}
    )
    impossible.append((validator_zero_without_receipt, finalizer._SEQUENCE[:3]))
    for candidate, sequence in impossible:
        assert not finalizer._ledger_process_valid(
            candidate,
            label="A",
            execution=execution,
            sequence=sequence,
        )


def test_finalizer_completion_pair_equality_and_mismatch_are_exact_bytes() -> None:
    def process(label: str, raw: bytes) -> finalizer._Process:
        return finalizer._Process(
            {
                "exit_code": 0,
                "validator_exit_code": 0,
                "payload_sha256": hashlib.sha256(raw).hexdigest(),
                "payload_valid": True,
            },
            raw,
        )

    process_a = process("A", b"same")
    process_b = process("B", b"same")
    assert (
        finalizer._reached_lifecycle_stage(
            sequence=finalizer._SEQUENCE,
            arm_exit=0,
            ready_for_a=True,
            process_a=process_a,
            process_b=process_b,
        )
        is None
    )
    process_b = process("B", b"different")
    assert (
        finalizer._reached_lifecycle_stage(
            sequence=finalizer._SEQUENCE,
            arm_exit=0,
            ready_for_a=True,
            process_a=process_a,
            process_b=process_b,
        )
        == "payload_byte_mismatch"
    )


def test_finalizer_completion_admin_bundle_reopen_enforces_exact_terminal_paths() -> None:
    registration, terminal, bundle = _finalizer_completion_admin_fixture()
    _finalizer_completion_validate_admin(registration, bundle)
    assert [item["path"] for item in bundle["files"]] == [
        "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
        "docs/action_qbc_v8_open_diagnostic_result.md",
    ]
    document = finalizer._normal_document(
        registration,
        disposition="administrative_terminal",
        stage="lifecycle_ledger_invalid",
        underlying_stage="lifecycle_ledger_invalid",
        commit="d" * 40,
    )
    terminal_file = finalizer._file_object(
        "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
        finalizer._canonical(terminal),
    )
    document_file = finalizer._file_object(
        "docs/action_qbc_v8_open_diagnostic_result.md", document
    )
    orphan_file = finalizer._file_object(
        "artifacts/action_qbc_v8_open_diagnostic.json", b"orphan"
    )
    for files in ([document_file], [terminal_file], [terminal_file, document_file, orphan_file]):
        candidate = finalizer._bundle(
            registration=registration,
            commit="d" * 40,
            disposition="administrative_terminal",
            stage="lifecycle_ledger_invalid",
            underlying_stage="lifecycle_ledger_invalid",
            files=files,
        )
        with pytest.raises(finalizer._FinalizationError, match="path"):
            _finalizer_completion_validate_admin(registration, candidate)

    doc_only = finalizer._receipt_failure_bundle(
        registration,
        commit="d" * 40,
        underlying_stage="lifecycle_ledger_invalid",
    )
    _finalizer_completion_validate_admin(registration, doc_only)
    assert [item["path"] for item in doc_only["files"]] == [
        "docs/action_qbc_v8_open_diagnostic_result.md"
    ]
    partial = finalizer._bundle(
        registration=registration,
        commit="d" * 40,
        disposition="administrative_terminal",
        stage="receipt_finalization_failed",
        underlying_stage="lifecycle_ledger_invalid",
        files=[*doc_only["files"], terminal_file],
    )
    with pytest.raises(finalizer._FinalizationError, match="path"):
        _finalizer_completion_validate_admin(registration, partial)


def test_finalizer_completion_reopen_rejects_every_terminal_and_process_key_mutation() -> None:
    import copy

    registration, terminal, _bundle = _finalizer_completion_admin_fixture()

    def rejected(mutated: dict[str, Any]) -> None:
        document = finalizer._normal_document(
            registration,
            disposition="administrative_terminal",
            stage="lifecycle_ledger_invalid",
            underlying_stage="lifecycle_ledger_invalid",
            commit="d" * 40,
        )
        candidate = finalizer._bundle(
            registration=registration,
            commit="d" * 40,
            disposition="administrative_terminal",
            stage="lifecycle_ledger_invalid",
            underlying_stage="lifecycle_ledger_invalid",
            files=[
                finalizer._file_object(
                    "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                    finalizer._canonical(mutated),
                ),
                finalizer._file_object(
                    "docs/action_qbc_v8_open_diagnostic_result.md", document
                ),
            ],
        )
        with pytest.raises(finalizer._FinalizationError):
            _finalizer_completion_validate_admin(registration, candidate)

    for key in finalizer._ADMIN_KEYS:
        mutated = copy.deepcopy(terminal)
        del mutated[key]
        rejected(mutated)
    for process_name in ("process_a", "process_b"):
        for key in finalizer._PROCESS_KEYS:
            mutated = copy.deepcopy(terminal)
            del mutated[process_name][key]
            rejected(mutated)
        mutated = copy.deepcopy(terminal)
        mutated[process_name]["unexpected"] = None
        rejected(mutated)
    mutated = copy.deepcopy(terminal)
    mutated["preparation_receipt"] = {}
    rejected(mutated)
    mutated = copy.deepcopy(terminal)
    mutated["process_a"]["start_claim"] = {}
    mutated["process_a"]["start_claim_sha256"] = "a" * 64
    rejected(mutated)


def test_finalizer_completion_override_and_underlying_stage_collisions_fail_closed() -> None:
    registration = _result_contract_registration()
    for underlying in [None, *finalizer._UNDERLYING_ORDER]:
        bundle = finalizer._receipt_failure_bundle(
            registration,
            commit="d" * 40,
            underlying_stage=underlying,
        )
        _finalizer_completion_validate_admin(registration, bundle)
        assert bundle["stage"] == "receipt_finalization_failed"
        assert bundle["underlying_stage"] == underlying

    document = finalizer._NORMAL_TEMPLATE.format(
        disposition="administrative_terminal",
        stage="process_b_nonzero",
        underlying_stage="process_a_nonzero",
        open_freeze_commit_sha="d" * 40,
        registration_content_sha256=registration["content_sha256"],
    ).encode("ascii")
    inconsistent = finalizer._bundle(
        registration=registration,
        commit="d" * 40,
        disposition="administrative_terminal",
        stage="process_b_nonzero",
        underlying_stage="process_a_nonzero",
        files=[
            finalizer._file_object(
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                b"{}",
            ),
            finalizer._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md", document
            ),
        ],
    )
    with pytest.raises(finalizer._FinalizationError, match="path/stage"):
        _finalizer_completion_validate_admin(registration, inconsistent)
    invalid_override = finalizer._bundle(
        registration=registration,
        commit="d" * 40,
        disposition="administrative_terminal",
        stage="finalizer_process_failed",
        underlying_stage="lifecycle_ledger_invalid",
        files=[
            finalizer._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md", b"invalid"
            )
        ],
    )
    with pytest.raises(finalizer._FinalizationError, match="unknown administrative stage"):
        _finalizer_completion_validate_admin(registration, invalid_override)


@pytest.mark.skipif(os.name != "posix", reason="Linux emergency publication uses dirfd APIs")
def test_finalizer_completion_normal_and_emergency_bundle_bytes_are_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _result_contract_registration()
    first_normal = finalizer._receipt_failure_bundle(
        registration,
        commit="d" * 40,
        underlying_stage="authority_identity_invalid",
    )
    second_normal = finalizer._receipt_failure_bundle(
        registration,
        commit="d" * 40,
        underlying_stage="authority_identity_invalid",
    )
    assert finalizer._canonical(first_normal) == finalizer._canonical(second_normal)
    _finalizer_completion_validate_admin(registration, first_normal)

    monkeypatch.setattr(lifecycle, "_FINAL_BUNDLE", tmp_path / "missing-normal.json")
    monkeypatch.setattr(lifecycle, "_LEDGER", tmp_path / "missing-ledger.json")
    monkeypatch.setattr(lifecycle, "_PREPARATION", tmp_path / "missing-preparation.json")
    monkeypatch.setattr(
        lifecycle,
        "_PREPARATION_VERIFICATION",
        tmp_path / "missing-preparation-verification.json",
    )
    monkeypatch.setattr(lifecycle, "_EMERGENCY_BUNDLE", tmp_path / "emergency-one.json")
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        normal_finalization_bundle=lifecycle._FINAL_BUNDLE,
        lifecycle_ledger=lifecycle._LEDGER,
        preparation_receipt=lifecycle._PREPARATION,
        preparation_verification_receipt=lifecycle._PREPARATION_VERIFICATION,
        emergency_result_bundle=lifecycle._EMERGENCY_BUNDLE,
    )
    monkeypatch.setattr(lifecycle, "_fsync_directory", lambda _path: None)
    finalizer_result = lifecycle._ChildResult(True, 124, True, None, "timeout")
    first_emergency, first_raw = lifecycle._publish_emergency_bundle(
        registration,
        commit="d" * 40,
        underlying_stage="authority_identity_invalid",
        finalizer=finalizer_result,
    )
    monkeypatch.setattr(lifecycle, "_EMERGENCY_BUNDLE", tmp_path / "emergency-two.json")
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        emergency_result_bundle=lifecycle._EMERGENCY_BUNDLE,
    )
    second_emergency, second_raw = lifecycle._publish_emergency_bundle(
        registration,
        commit="d" * 40,
        underlying_stage="authority_identity_invalid",
        finalizer=finalizer_result,
    )
    assert first_emergency == second_emergency
    assert first_raw == second_raw == lifecycle.canonical_json_bytes(first_emergency)
    assert [item["path"] for item in first_emergency["files"]] == [
        "docs/action_qbc_v8_open_diagnostic_result.md"
    ]
    _path, document = lifecycle._decode_file_object(first_emergency["files"][0])
    absent = lifecycle._EvidenceState(False, "absent", None, None, None)
    assert document == lifecycle._emergency_document(
        registration,
        commit="d" * 40,
        underlying_stage="authority_identity_invalid",
        finalizer=finalizer_result,
        finalization=absent,
        ledger=absent,
        preparation=absent,
        preparation_verification=absent,
    )


def test_finalizer_completion_registration_identity_survives_authority_materialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _result_contract_registration()
    registration["execution_contract"]["lifecycle_driver_argv"] = []
    commit = "d" * 40
    raw_by_name = {
        "preparation receipt": b"preparation",
        "preparation verification receipt": b"preparation-verification",
        "remote claim": b"remote-claim",
        "remote verifier claim": b"remote-verifier",
        "remote receipt": b"remote-receipt",
        "remote supervisor receipt": b"remote-supervisor",
        "arm receipt": b"arm",
        "driver claim": b"driver",
    }
    values: dict[str, dict[str, Any]] = {
        name: {} for name in raw_by_name
    }
    values["remote receipt"]["status"] = "verified"
    values["remote supervisor receipt"]["status"] = "completed"
    values["arm receipt"].update(
        {
            "preparation_receipt_exists": True,
            "preparation_receipt_read_status": "readable",
            "preparation_receipt_sha256": hashlib.sha256(
                raw_by_name["preparation receipt"]
            ).hexdigest(),
            "preparation_verification_receipt_exists": True,
            "preparation_verification_receipt_read_status": "readable",
            "preparation_verification_receipt_sha256": hashlib.sha256(
                raw_by_name["preparation verification receipt"]
            ).hexdigest(),
            "remote_claim_sha256": hashlib.sha256(
                raw_by_name["remote claim"]
            ).hexdigest(),
            "remote_verifier_claim_sha256": hashlib.sha256(
                raw_by_name["remote verifier claim"]
            ).hexdigest(),
            "remote_receipt_sha256": hashlib.sha256(
                raw_by_name["remote receipt"]
            ).hexdigest(),
            "remote_supervisor_receipt_sha256": hashlib.sha256(
                raw_by_name["remote supervisor receipt"]
            ).hexdigest(),
            "status": "armed",
        }
    )
    values["driver claim"].update(
        {
            "remote_claim_sha256": hashlib.sha256(
                raw_by_name["remote claim"]
            ).hexdigest(),
            "driver_argv_sha256": hashlib.sha256(finalizer._canonical([])).hexdigest(),
        }
    )

    def artifact(_path: str, *, name: str, **_kwargs: Any) -> finalizer._Artifact:
        if name == "lifecycle ledger":
            return finalizer._Artifact(False, "absent", None, None, None)
        if name.startswith("process "):
            return finalizer._Artifact(False, "absent", None, None, None)
        raw = raw_by_name[name]
        return finalizer._Artifact(
            True,
            "readable",
            raw,
            hashlib.sha256(raw).hexdigest(),
            values[name],
        )

    def process(label: str, **_kwargs: Any) -> finalizer._Process:
        return finalizer._Process(_finalizer_completion_empty_process(label), None)

    monkeypatch.setattr(
        finalizer,
        "_repository_and_registration",
        lambda _root: (commit, registration, b"registration"),
    )
    monkeypatch.setattr(finalizer, "_require_argv", lambda *_args: None)
    monkeypatch.setattr(finalizer, "_authority_raw_audit", lambda *_args: False)
    monkeypatch.setattr(finalizer, "_artifact", artifact)
    monkeypatch.setattr(
        finalizer, "_preparation_semantically_valid", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(finalizer, "_preparation_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        finalizer, "_preparation_verification_valid", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(finalizer, "_remote_claim_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(finalizer, "_remote_verifier_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(finalizer, "_remote_receipt_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(finalizer, "_remote_supervisor_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(finalizer, "_matching", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(finalizer, "_process", process)
    monkeypatch.setattr(finalizer, "_validate_machine_result", lambda *_args, **_kwargs: None)

    bundle = finalizer._finalize(SimpleNamespace())
    assert bundle["stage"] == "authority_identity_invalid"
    assert bundle["open_freeze_commit_sha"] == commit
    assert bundle["registration_content_sha256"] == registration["content_sha256"]
    import base64
    import json

    terminal_file = next(
        item
        for item in bundle["files"]
        if item["path"]
        == "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json"
    )
    terminal = json.loads(base64.b64decode(terminal_file["content_base64"]))
    assert terminal["open_freeze_commit_sha"] == commit
    assert terminal["registration_content_sha256"] == registration["content_sha256"]
    assert terminal["stage"] == "authority_identity_invalid"


def _publisher_empty_result_process(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "output_path": str(lifecycle._A_OUTPUT if label == "A" else lifecycle._B_OUTPUT),
        "exit_code": None,
        "validator_exit_code": None,
        "start_claim": None,
        "start_claim_sha256": None,
        "validator_claim": None,
        "validator_claim_sha256": None,
        "validation_receipt": None,
        "validation_receipt_sha256": None,
        "payload_exists": False,
        "payload_valid": False,
        "payload_sha256": None,
        "payload_size_bytes": None,
    }


def _publisher_minimal_administrative_result(
    *,
    commit: str,
    registration_sha: str,
    stage: str,
) -> dict[str, Any]:
    return {
        "schema_version": lifecycle._ADMIN_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "preparation_receipt": None,
        "preparation_receipt_exists": False,
        "preparation_receipt_read_status": "absent",
        "preparation_receipt_sha256": None,
        "preparation_verification_receipt": None,
        "preparation_verification_receipt_exists": False,
        "preparation_verification_receipt_read_status": "absent",
        "preparation_verification_receipt_sha256": None,
        "remote_verification_claim": None,
        "remote_verifier_claim": None,
        "remote_verification_receipt": None,
        "remote_supervisor_receipt": None,
        "arm_receipt": None,
        "lifecycle_driver_claim": None,
        "lifecycle_ledger": None,
        "process_a": _publisher_empty_result_process("A"),
        "process_b": _publisher_empty_result_process("B"),
        "payloads_byte_identical": None,
        "stage": stage,
        "authorization": dict(lifecycle._AUTHORIZATION),
    }


def _publisher_normal_machine_bundle(
    registration: dict[str, Any],
    *,
    commit: str,
    disposition: str,
    stage: str | None,
    machine: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    underlying = stage
    document = lifecycle._normal_document(
        registration,
        commit=commit,
        disposition=disposition,
        stage=stage,
        underlying_stage=underlying,
    )
    if disposition == "scientific_result":
        files = [
            lifecycle._file_object(
                "artifacts/action_qbc_v8_open_diagnostic.json",
                b'{"synthetic":"scientific payload"}',
            ),
            lifecycle._file_object(
                "artifacts/action_qbc_v8_open_diagnostic_receipt.json",
                lifecycle.canonical_json_bytes(machine),
            ),
            lifecycle._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md", document
            ),
        ]
    else:
        files = [
            lifecycle._file_object(
                "artifacts/action_qbc_v8_open_diagnostic_administrative_terminal.json",
                lifecycle.canonical_json_bytes(machine),
            ),
            lifecycle._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md", document
            ),
        ]
    bundle = {
        "schema_version": lifecycle._BUNDLE_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "disposition": disposition,
        "stage": stage,
        "underlying_stage": underlying,
        "files": sorted(files, key=lambda item: str(item["path"]).encode("utf-8")),
        "authorization": dict(lifecycle._AUTHORIZATION),
    }
    bundle["content_sha256"] = lifecycle.canonical_sha256(bundle)
    return bundle, lifecycle.canonical_json_bytes(bundle)


def _publisher_emergency_bundle(
    registration: dict[str, Any],
    *,
    commit: str,
    finalizer_exit_code: object,
) -> tuple[dict[str, Any], bytes]:
    underlying = "lifecycle_driver_failed"
    if finalizer_exit_code is None:
        finalizer_result = lifecycle._ChildResult(
            False, None, None, None, "spawn_error"
        )
    elif finalizer_exit_code == 124 and not isinstance(finalizer_exit_code, bool):
        finalizer_result = lifecycle._ChildResult(True, 124, True, None, "timeout")
    else:
        finalizer_result = lifecycle._ChildResult(
            True, finalizer_exit_code, False, None, "nonzero"
        )
    absent = lifecycle._EvidenceState(False, "absent", None, None, None)
    document = lifecycle._emergency_document(
        registration,
        commit=commit,
        underlying_stage=underlying,
        finalizer=finalizer_result,
        finalization=absent,
        ledger=absent,
        preparation=absent,
        preparation_verification=absent,
    )
    bundle = {
        "schema_version": lifecycle._EMERGENCY_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration["content_sha256"],
        "disposition": "administrative_terminal",
        "stage": "finalizer_process_failed",
        "underlying_stage": underlying,
        "finalizer_classification": finalizer_result.classification,
        "finalizer_exit_code": finalizer_exit_code,
        "finalizer_timed_out": finalizer_result.timed_out,
        "finalizer_child_cleanup_passes": finalizer_result.child_cleanup_passes,
        "finalization_bundle_exists": False,
        "finalization_bundle_sha256": None,
        "lifecycle_ledger_exists": False,
        "lifecycle_ledger_sha256": None,
        "preparation_receipt_exists": False,
        "preparation_receipt_read_status": "absent",
        "preparation_receipt_sha256": None,
        "preparation_verification_receipt_exists": False,
        "preparation_verification_receipt_read_status": "absent",
        "preparation_verification_receipt_sha256": None,
        "files": [
            lifecycle._file_object(
                "docs/action_qbc_v8_open_diagnostic_result.md", document
            )
        ],
        "authorization": dict(lifecycle._AUTHORIZATION),
    }
    bundle["content_sha256"] = lifecycle.canonical_sha256(bundle)
    return bundle, lifecycle.canonical_json_bytes(bundle)


def test_publisher_machine_validator_accepts_same_minimal_admin_as_finalizer() -> None:
    registration = _result_contract_registration()
    commit = "d" * 40
    stage = "process_a_nonzero"
    machine = _publisher_minimal_administrative_result(
        commit=commit,
        registration_sha=registration["content_sha256"],
        stage=stage,
    )
    bundle, raw = _publisher_normal_machine_bundle(
        registration,
        commit=commit,
        disposition="administrative_terminal",
        stage=stage,
        machine=machine,
    )

    value, files = lifecycle._validate_bundle_bytes(
        raw,
        commit=commit,
        registration_sha=registration["content_sha256"],
        registration=registration,
        emergency=False,
    )
    lifecycle._validate_selected_document(
        registration,
        commit=commit,
        bundle=value,
        files=files,
        emergency=False,
    )
    finalizer._validate_final_bundle(
        bundle,
        registration=registration,
        registration_file_sha256="e" * 64,
        commit=commit,
    )


@pytest.mark.parametrize(
    "mutation",
    ["extra_machine_key", "extra_process_key", "inconsistent_payload", "wrong_stage"],
)
def test_publisher_rejects_rehashed_nested_admin_mutations_in_parity_with_finalizer(
    mutation: str,
) -> None:
    registration = _result_contract_registration()
    commit = "d" * 40
    stage = "process_a_nonzero"
    machine = _publisher_minimal_administrative_result(
        commit=commit,
        registration_sha=registration["content_sha256"],
        stage=stage,
    )
    if mutation == "extra_machine_key":
        machine["unexpected"] = True
    elif mutation == "extra_process_key":
        process_a = dict(machine["process_a"])
        process_a["unexpected"] = True
        machine["process_a"] = process_a
    elif mutation == "inconsistent_payload":
        process_a = dict(machine["process_a"])
        process_a["payload_exists"] = True
        machine["process_a"] = process_a
    else:
        machine["stage"] = "process_b_nonzero"
    bundle, raw = _publisher_normal_machine_bundle(
        registration,
        commit=commit,
        disposition="administrative_terminal",
        stage=stage,
        machine=machine,
    )
    unsigned = dict(bundle)
    claimed = unsigned.pop("content_sha256")
    assert claimed == lifecycle.canonical_sha256(unsigned)

    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_bundle_bytes(
            raw,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
            emergency=False,
        )
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_final_bundle(
            bundle,
            registration=registration,
            registration_file_sha256="e" * 64,
            commit=commit,
        )


def test_publisher_rejects_rehashed_malformed_scientific_receipt_before_r8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _result_contract_registration()
    commit = "d" * 40
    malformed_receipt = {
        "schema_version": lifecycle._RECEIPT_SCHEMA,
        "unexpected": "rehashed nested mutation",
    }
    bundle, raw = _publisher_normal_machine_bundle(
        registration,
        commit=commit,
        disposition="scientific_result",
        stage=None,
        machine=malformed_receipt,
    )
    unsigned = dict(bundle)
    claimed = unsigned.pop("content_sha256")
    assert claimed == lifecycle.canonical_sha256(unsigned)
    payload = b'{"synthetic":"scientific payload"}'

    def scientific_payload_state(
        path: Path,
        _label: str,
        *,
        role: str,
    ) -> lifecycle._EvidenceState:
        assert path in {lifecycle._A_OUTPUT, lifecycle._B_OUTPUT}
        assert role in {"process_a_payload", "process_b_payload"}
        return lifecycle._EvidenceState(
            True,
            "readable",
            payload,
            hashlib.sha256(payload).hexdigest(),
            None,
        )

    monkeypatch.setattr(lifecycle, "_evidence_state", scientific_payload_state)

    with pytest.raises(lifecycle.LifecycleError, match="machine result"):
        lifecycle._validate_bundle_bytes(
            raw,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
            emergency=False,
        )
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_final_bundle(
            bundle,
            registration=registration,
            registration_file_sha256="e" * 64,
            commit=commit,
        )


@pytest.mark.parametrize(
    ("finalizer_exit_code", "accepted"),
    [(None, True), (1, True), (124, True), (0, False), (True, False)],
)
def test_publisher_emergency_exit_code_is_strictly_nonzero_or_null(
    finalizer_exit_code: object,
    accepted: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _result_contract_registration()
    commit = "d" * 40
    _bundle, raw = _publisher_emergency_bundle(
        registration,
        commit=commit,
        finalizer_exit_code=finalizer_exit_code,
    )
    monkeypatch.setattr(
        lifecycle,
        "_evidence_state",
        lambda *_args, **_kwargs: lifecycle._EvidenceState(
            False, "absent", None, None, None
        ),
    )

    if not accepted:
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle._validate_bundle_bytes(
                raw,
                commit=commit,
                registration_sha=registration["content_sha256"],
                registration=registration,
                emergency=True,
            )
        return
    value, files = lifecycle._validate_bundle_bytes(
        raw,
        commit=commit,
        registration_sha=registration["content_sha256"],
        registration=registration,
        emergency=True,
    )
    lifecycle._validate_selected_document(
        registration,
        commit=commit,
        bundle=value,
        files=files,
        emergency=True,
    )


@pytest.mark.parametrize(
    ("parents", "accepted"),
    [
        ([lifecycle._PREREGISTRATION_COMMIT], True),
        ([lifecycle._PREREGISTRATION_COMMIT, "e" * 40], False),
        ([], False),
        (["e" * 40], False),
    ],
)
def test_publisher_o8_identity_requires_exactly_one_parent_equal_to_p8(
    parents: list[str],
    accepted: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = {
        (lifecycle._P8V1_COMMIT, lifecycle._P8V2_DOCUMENT): b"synthetic P8v1\n",
        (lifecycle._P8V2_COMMIT, lifecycle._P8V2_DOCUMENT): b"synthetic P8v2\n",
        (lifecycle._P8V3_COMMIT, lifecycle._P8V3_DOCUMENT): b"synthetic P8v3\n",
        (lifecycle._P8V4_COMMIT, lifecycle._P8V4_DOCUMENT): b"synthetic P8v4\n",
        (lifecycle._P8V5_COMMIT, lifecycle._P8V5_DOCUMENT): b"synthetic P8v5\n",
        (lifecycle._P8V6_COMMIT, lifecycle._P8V6_DOCUMENT): b"synthetic P8v6\n",
        (
            lifecycle._PREREGISTRATION_COMMIT,
            lifecycle._PREREGISTRATION_DOCUMENT,
        ): b"synthetic P8v7\n",
    }
    p8v1_raw = documents[(lifecycle._P8V1_COMMIT, lifecycle._P8V2_DOCUMENT)]
    p8v2_raw = documents[(lifecycle._P8V2_COMMIT, lifecycle._P8V2_DOCUMENT)]
    p8v3_raw = documents[(lifecycle._P8V3_COMMIT, lifecycle._P8V3_DOCUMENT)]
    p8v4_raw = documents[(lifecycle._P8V4_COMMIT, lifecycle._P8V4_DOCUMENT)]
    p8v5_raw = documents[(lifecycle._P8V5_COMMIT, lifecycle._P8V5_DOCUMENT)]
    p8v6_raw = documents[(lifecycle._P8V6_COMMIT, lifecycle._P8V6_DOCUMENT)]
    p8v7_raw = documents[
        (lifecycle._PREREGISTRATION_COMMIT, lifecycle._PREREGISTRATION_DOCUMENT)
    ]
    monkeypatch.setattr(lifecycle, "_P8V1_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v1_raw))
    monkeypatch.setattr(lifecycle, "_P8V1_DOCUMENT_SHA256", hashlib.sha256(p8v1_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V2_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v2_raw))
    monkeypatch.setattr(lifecycle, "_P8V2_DOCUMENT_SHA256", hashlib.sha256(p8v2_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V2_DOCUMENT_BYTE_COUNT", len(p8v2_raw))
    monkeypatch.setattr(lifecycle, "_P8V3_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v3_raw))
    monkeypatch.setattr(lifecycle, "_P8V3_DOCUMENT_SHA256", hashlib.sha256(p8v3_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V3_DOCUMENT_BYTE_COUNT", len(p8v3_raw))
    monkeypatch.setattr(lifecycle, "_P8V4_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v4_raw))
    monkeypatch.setattr(lifecycle, "_P8V4_DOCUMENT_SHA256", hashlib.sha256(p8v4_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V4_DOCUMENT_BYTE_COUNT", len(p8v4_raw))
    monkeypatch.setattr(lifecycle, "_P8V5_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v5_raw))
    monkeypatch.setattr(lifecycle, "_P8V5_DOCUMENT_SHA256", hashlib.sha256(p8v5_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V5_DOCUMENT_BYTE_COUNT", len(p8v5_raw))
    monkeypatch.setattr(lifecycle, "_P8V6_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v6_raw))
    monkeypatch.setattr(lifecycle, "_P8V6_DOCUMENT_SHA256", hashlib.sha256(p8v6_raw).hexdigest())
    monkeypatch.setattr(lifecycle, "_P8V6_DOCUMENT_BYTE_COUNT", len(p8v6_raw))
    monkeypatch.setattr(
        lifecycle, "_PREREGISTRATION_DOCUMENT_BLOB", lifecycle._git_oid("blob", p8v7_raw)
    )
    monkeypatch.setattr(
        lifecycle, "_PREREGISTRATION_DOCUMENT_SHA256", hashlib.sha256(p8v7_raw).hexdigest()
    )
    monkeypatch.setattr(lifecycle, "_PREREGISTRATION_DOCUMENT_BYTE_COUNT", len(p8v7_raw))

    raw = (
        b"tree "
        + b"a" * 40
        + b"\n"
        + b"".join(f"parent {parent}\n".encode("ascii") for parent in parents)
        + b"author Synthetic <synthetic@invalid.example> 1 +0000\n"
        + b"committer Synthetic <synthetic@invalid.example> 1 +0000\n\n"
        + b"Synthetic O8\n"
    )
    commit = lifecycle._git_oid("commit", raw)
    tag_commits = {
        lifecycle._P8V1_TAG: lifecycle._P8V1_COMMIT,
        lifecycle._P8V2_TAG: lifecycle._P8V2_COMMIT,
        lifecycle._P8V3_TAG: lifecycle._P8V3_COMMIT,
        lifecycle._P8V4_TAG: lifecycle._P8V4_COMMIT,
        lifecycle._O8V1_TAG: lifecycle._O8V1_COMMIT,
        lifecycle._P8V5_TAG: lifecycle._P8V5_COMMIT,
        lifecycle._O8V2_TAG: lifecycle._O8V2_COMMIT,
        lifecycle._P8V6_TAG: lifecycle._P8V6_COMMIT,
        lifecycle._O8V3_TAG: lifecycle._O8V3_COMMIT,
        lifecycle._PREREGISTRATION_TAG: lifecycle._PREREGISTRATION_COMMIT,
    }
    lineage = {
        lifecycle._P8V1_COMMIT: lifecycle._R7_COMMIT,
        lifecycle._P8V2_COMMIT: lifecycle._P8V1_COMMIT,
        lifecycle._P8V3_COMMIT: lifecycle._P8V2_COMMIT,
        lifecycle._P8V4_COMMIT: lifecycle._P8V3_COMMIT,
        lifecycle._O8V1_COMMIT: lifecycle._P8V4_COMMIT,
        lifecycle._P8V5_COMMIT: lifecycle._O8V1_COMMIT,
        lifecycle._O8V2_COMMIT: lifecycle._P8V5_COMMIT,
        lifecycle._P8V6_COMMIT: lifecycle._O8V2_COMMIT,
        lifecycle._O8V3_COMMIT: lifecycle._P8V6_COMMIT,
        lifecycle._PREREGISTRATION_COMMIT: lifecycle._O8V3_COMMIT,
    }

    def fake_git(
        _authority: Path,
        _environment: dict[str, str],
        *arguments: str,
        input_bytes: bytes | None = None,
    ) -> bytes:
        assert input_bytes is None
        for tag, expected in tag_commits.items():
            ref = f"refs/tags/{tag}"
            if arguments == ("cat-file", "-t", ref):
                return b"commit\n"
            if arguments == ("rev-parse", ref):
                return f"{expected}\n".encode("ascii")
        for child, parent in lineage.items():
            if arguments == ("rev-list", "--parents", "-n", "1", child):
                return f"{child} {parent}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._R7_COMMIT,
            lifecycle._P8V1_COMMIT,
        ):
            return b"A\0" + lifecycle._P8V2_DOCUMENT.encode("utf-8") + b"\0"
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V1_COMMIT,
            lifecycle._P8V2_COMMIT,
        ):
            return b"M\0" + lifecycle._P8V2_DOCUMENT.encode("utf-8") + b"\0"
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V2_COMMIT,
            lifecycle._P8V3_COMMIT,
        ):
            return b"A\0" + lifecycle._P8V3_DOCUMENT.encode("utf-8") + b"\0"
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V3_COMMIT,
            lifecycle._P8V4_COMMIT,
        ):
            return b"A\0" + lifecycle._P8V4_DOCUMENT.encode("utf-8") + b"\0"
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V4_COMMIT,
            lifecycle._O8V1_COMMIT,
        ):
            return lifecycle._expected_name_status(lifecycle._O8_ADDITIONS)
        if arguments == (
            "rev-parse",
            f"{lifecycle._O8V1_COMMIT}^{{tree}}",
        ):
            return f"{lifecycle._O8V1_TREE}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V1_COMMIT,
            lifecycle._P8V5_COMMIT,
        ):
            return lifecycle._expected_forward_reset_name_status(
                lifecycle._O8_ADDITIONS,
                lifecycle._P8V5_DOCUMENT,
            )
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V4_COMMIT,
            lifecycle._P8V5_COMMIT,
        ):
            return lifecycle._expected_name_status((lifecycle._P8V5_DOCUMENT,))
        if arguments == ("rev-parse", f"{lifecycle._P8V5_COMMIT}^{{tree}}"):
            return f"{lifecycle._P8V5_TREE}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V5_COMMIT,
            lifecycle._O8V2_COMMIT,
        ):
            return lifecycle._expected_name_status(lifecycle._O8_ADDITIONS)
        if arguments == ("rev-parse", f"{lifecycle._O8V2_COMMIT}^{{tree}}"):
            return f"{lifecycle._O8V2_TREE}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V2_COMMIT,
            lifecycle._P8V6_COMMIT,
        ):
            return lifecycle._expected_forward_reset_name_status(
                lifecycle._O8_ADDITIONS,
                lifecycle._P8V6_DOCUMENT,
            )
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V5_COMMIT,
            lifecycle._P8V6_COMMIT,
        ):
            return lifecycle._expected_name_status((lifecycle._P8V6_DOCUMENT,))
        if arguments == ("rev-parse", f"{lifecycle._P8V6_COMMIT}^{{tree}}"):
            return f"{lifecycle._P8V6_TREE}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V6_COMMIT,
            lifecycle._O8V3_COMMIT,
        ):
            return lifecycle._expected_name_status(lifecycle._O8_ADDITIONS)
        if arguments == ("rev-parse", f"{lifecycle._O8V3_COMMIT}^{{tree}}"):
            return f"{lifecycle._O8V3_TREE}\n".encode("ascii")
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V3_COMMIT,
            lifecycle._PREREGISTRATION_COMMIT,
        ):
            return lifecycle._expected_forward_reset_name_status(
                lifecycle._O8_ADDITIONS,
                lifecycle._PREREGISTRATION_DOCUMENT,
            )
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V6_COMMIT,
            lifecycle._PREREGISTRATION_COMMIT,
        ):
            return lifecycle._expected_name_status((lifecycle._PREREGISTRATION_DOCUMENT,))
        if arguments == (
            "rev-parse",
            f"{lifecycle._PREREGISTRATION_COMMIT}^{{tree}}",
        ):
            return f"{lifecycle._PREREGISTRATION_TREE}\n".encode("ascii")
        if len(arguments) == 3 and arguments[:2] == ("cat-file", "blob"):
            commit_and_path = arguments[2]
            for identity, document_raw in documents.items():
                if commit_and_path == f"{identity[0]}:{identity[1]}":
                    return document_raw
        if arguments == (
            "cat-file",
            "-t",
            f"refs/tags/{lifecycle._OPEN_FREEZE_TAG}",
        ):
            return b"commit\n"
        if arguments == (
            "rev-parse",
            f"refs/tags/{lifecycle._OPEN_FREEZE_TAG}",
        ):
            return f"{commit}\n".encode("ascii")
        if arguments == ("cat-file", "-p", commit):
            return raw
        if arguments == (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._PREREGISTRATION_COMMIT,
            commit,
        ):
            return lifecycle._expected_name_status(lifecycle._O8_ADDITIONS)
        if arguments == ("rev-parse", "HEAD"):
            return f"{commit}\n".encode("ascii")
        raise AssertionError(f"unexpected synthetic Git argv: {arguments!r}")

    monkeypatch.setattr(lifecycle, "_validate_object_pack_sources", lambda _root: None)
    monkeypatch.setattr(lifecycle, "_git", fake_git)
    if accepted:
        assert lifecycle._derive_o8(Path("/synthetic-authority"), {}) == commit
    else:
        with pytest.raises(lifecycle.LifecycleError, match="one-parent direct child"):
            lifecycle._derive_o8(Path("/synthetic-authority"), {})


@pytest.mark.parametrize(
    ("parents_line", "accepted"),
    [
        ("{commit} {parent}\n", True),
        ("{commit} {parent} {other}\n", False),
        ("{commit}\n", False),
        ("{commit} {other}\n", False),
    ],
)
def test_finalizer_completion_o8_requires_exactly_one_p8_parent(
    parents_line: str,
    accepted: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "d" * 40
    parent = "c" * 40
    other = "b" * 40

    def fake_git(_root: Path, *arguments: str, **_kwargs: Any) -> bytes:
        assert arguments == ("rev-list", "--parents", "-n", "1", commit)
        return parents_line.format(
            commit=commit,
            parent=parent,
            other=other,
        ).encode("ascii")

    monkeypatch.setattr(finalizer, "_git", fake_git)
    assert finalizer._has_exact_parent(Path("/synthetic-authority"), commit, parent) is accepted


def test_publisher_machine_result_schema_constants_match_stable_finalizer() -> None:
    for name in (
        "_PREPARATION_KEYS",
        "_REMOTE_CLAIM_KEYS",
        "_REMOTE_VERIFIER_KEYS",
        "_REMOTE_RECEIPT_KEYS",
        "_REMOTE_SUPERVISOR_KEYS",
        "_ARM_KEYS",
        "_DRIVER_KEYS",
        "_LEDGER_KEYS",
        "_LEDGER_PROCESS_KEYS",
        "_START_KEYS",
        "_VALIDATOR_KEYS",
        "_VALIDATION_KEYS",
        "_PROCESS_KEYS",
        "_RECEIPT_KEYS",
        "_ADMIN_KEYS",
    ):
        assert set(getattr(lifecycle, name)) == set(getattr(finalizer, name)), name
    assert lifecycle._RECEIPT_SCHEMA == finalizer._RECEIPT_SCHEMA
    assert lifecycle._ADMIN_SCHEMA == finalizer._ADMIN_SCHEMA
    assert lifecycle._TREATMENT_ID == finalizer._TREATMENT_ID
    assert lifecycle._OPEN_FREEZE_TAG == finalizer._OPEN_FREEZE_TAG
    assert lifecycle._AUTHORIZATION == finalizer._AUTHORIZATION


@pytest.mark.skipif(os.name != "nt", reason="real Windows Job Object boundary")
@pytest.mark.parametrize(
    ("module", "stream_name"),
    [
        pytest.param(supervisor, "stdout", id="supervisor-stdout"),
        pytest.param(supervisor, "stderr", id="supervisor-stderr"),
        pytest.param(remote_verifier, "stdout", id="verifier-stdout"),
        pytest.param(remote_verifier, "stderr", id="verifier-stderr"),
    ],
)
def test_remote_completion_actual_cap_plus_one_is_truncated_and_forced_clean(
    module: Any,
    stream_name: str,
    tmp_path: Path,
) -> None:
    cap = 37
    child = (
        "import sys,time;"
        f"stream=sys.{stream_name}.buffer;"
        f"stream.write(b'Q'*{cap + 1});"
        "stream.flush();time.sleep(1)"
    )
    now = module.time.monotonic_ns()
    arguments: dict[str, Any] = {
        "cwd": str(tmp_path),
        "environment": os.environ.copy(),
        "live_deadline_ns": now + 10_000_000_000,
        "cleanup_deadline_ns": now + 15_000_000_000,
        "stdout_cap": cap if stream_name == "stdout" else cap + 100,
        "stderr_cap": cap if stream_name == "stderr" else cap + 100,
        "deadline_reason": "timeout",
    }
    result = module._run_bounded_process(
        [sys.executable, "-I", "-B", "-c", child],
        **arguments,
    )

    assert result.spawned is True
    assert result.reason == f"{stream_name}_limit"
    assert result.timed_out is False
    assert result.cleanup_passes is True
    assert getattr(result, stream_name) == b"Q" * cap
    other = "stderr" if stream_name == "stdout" else "stdout"
    assert getattr(result, other) == b""


@pytest.mark.parametrize(
    "module",
    [
        pytest.param(supervisor, id="supervisor"),
        pytest.param(remote_verifier, id="verifier"),
    ],
)
def test_remote_completion_git_children_ignore_hostile_inherited_config_and_use_neutral_cwd(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.https://evil.invalid/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    monkeypatch.setenv("GIT_DIR", r"D:\hostile\git-dir")
    monkeypatch.setenv("GIT_WORK_TREE", r"D:\hostile\work-tree")
    observed: list[tuple[list[str], dict[str, Any]]] = []

    def bounded(argv: Any, **kwargs: Any) -> Any:
        observed.append((list(argv), dict(kwargs)))
        return module._ManagedResult(
            True,
            0,
            b"synthetic\n",
            b"",
            1,
            None,
            False,
            None,
        )

    monkeypatch.setattr(module, "_run_bounded_process", bounded)
    deadline = module.time.monotonic_ns() + 1_000_000_000_000
    assert module._run_git_command(["--version"], overall_deadline_ns=deadline) == (
        b"synthetic\n"
    )

    assert len(observed) == 1
    argv, kwargs = observed[0]
    assert argv == [
        module._GIT_PATH,
        "--no-replace-objects",
        "--no-optional-locks",
        "--version",
    ]
    assert kwargs["cwd"] == module._NEUTRAL_GIT_CWD
    assert os.path.normcase(kwargs["cwd"]) != os.path.normcase(module._REPOSITORY_ROOT)
    environment = kwargs["environment"]
    assert environment == module._git_environment()
    assert environment["GIT_CONFIG_COUNT"] == "0"
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert "GIT_CONFIG_KEY_0" not in environment
    assert "GIT_CONFIG_VALUE_0" not in environment
    assert "GIT_DIR" not in environment
    assert "GIT_WORK_TREE" not in environment
    assert not any("insteadof" in key.casefold() for key in environment)
    assert "https://evil.invalid/" not in environment.values()


def test_remote_completion_ls_remote_uses_only_neutral_cwd_and_closed_git_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.https://evil.invalid/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", remote_verifier._REMOTE_URL)
    observed: list[tuple[list[str], dict[str, Any]]] = []
    expected = b"c" * 40 + b"\t" + remote_verifier._REMOTE_REF.encode("ascii") + b"\n"

    def bounded(argv: Any, **kwargs: Any) -> Any:
        observed.append((list(argv), dict(kwargs)))
        return remote_verifier._ManagedResult(
            True,
            0,
            expected,
            b"",
            1,
            None,
            False,
            None,
        )

    monkeypatch.setattr(remote_verifier, "_run_bounded_process", bounded)
    attempt = remote_verifier._remote_attempt(
        1,
        live_admission_deadline_ns=(
            remote_verifier.time.monotonic_ns() + 1_000_000_000_000
        ),
        cleanup_deadline_ns=(
            remote_verifier.time.monotonic_ns() + 1_030_000_000_000
        ),
        expected_stdout=expected,
    )

    assert attempt is not None
    assert attempt["classification"] == "verified"
    assert len(observed) == 1
    argv, kwargs = observed[0]
    assert argv[:2] == [remote_verifier._GIT_PATH, "--no-replace-objects"]
    assert "--no-optional-locks" not in argv
    assert argv[-4:] == [
        "ls-remote",
        "--tags",
        remote_verifier._REMOTE_URL,
        remote_verifier._REMOTE_REF,
    ]
    assert kwargs["cwd"] == remote_verifier._NEUTRAL_GIT_CWD
    assert kwargs["environment"] == remote_verifier._git_environment()
    assert kwargs["environment"]["GIT_CONFIG_COUNT"] == "0"
    assert kwargs["environment"]["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert "GIT_CONFIG_KEY_0" not in kwargs["environment"]
    assert "GIT_CONFIG_VALUE_0" not in kwargs["environment"]


class _RemoteCompletionStream:
    def __init__(self, stream_name: str) -> None:
        self.stream_name = stream_name

    def close(self) -> None:
        return None


class _RemoteCompletionProcess:
    pid = 4242

    def __init__(self) -> None:
        self.stdout = _RemoteCompletionStream("stdout")
        self.stderr = _RemoteCompletionStream("stderr")
        self.exit_code: int | None = None

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float) -> int:
        assert timeout >= 0
        if self.exit_code is None:
            raise subprocess.TimeoutExpired("synthetic", timeout)
        return self.exit_code


class _RemoteCompletionJob:
    def __init__(self) -> None:
        self.active = 1
        self.closed = False

    def active_processes(self) -> int:
        return self.active

    def terminate(self) -> bool:
        self.active = 0
        return True

    def close(self) -> None:
        self.closed = True


def test_p8v3_remote_timeout_duration_uses_attempt_admission_epoch_after_spawn_stall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _RemoteCompletionProcess()
    job = _RemoteCompletionJob()
    first_read = True

    def clock() -> int:
        nonlocal first_read
        if first_read:
            first_read = False
            return 10_000_000_000
        return 120_000_000_000

    def cleanup(_process: Any, _job: Any, *, deadline_ns: int) -> bool:
        assert deadline_ns == 150_000_000_000
        process.exit_code = 1
        job.active = 0
        return True

    monkeypatch.setattr(remote_verifier.time, "monotonic_ns", clock)
    monkeypatch.setattr(
        remote_verifier,
        "_spawn_suspended",
        lambda *_args, **_kwargs: (process, job),
    )
    monkeypatch.setattr(remote_verifier, "_capture_stream", lambda *_args: None)
    monkeypatch.setattr(remote_verifier, "_cleanup_tree", cleanup)
    result = remote_verifier._run_bounded_process(
        ["synthetic-child"],
        cwd=remote_verifier._NEUTRAL_GIT_CWD,
        environment=remote_verifier._git_environment(),
        live_deadline_ns=120_000_000_000,
        cleanup_deadline_ns=150_000_000_000,
        stdout_cap=1,
        stderr_cap=1,
        deadline_reason="timeout",
        duration_start_ns=0,
    )
    assert result.reason == "timeout"
    assert result.exit_code == remote_verifier._SYNTHETIC_TIMEOUT_EXIT
    assert result.timed_out is True
    assert result.cleanup_passes is True
    assert result.duration_milliseconds == 120_000


@pytest.mark.parametrize(
    ("module", "trigger", "deadline_reason", "expected_reason"),
    [
        pytest.param(supervisor, "deadline", "timeout", "timeout", id="supervisor-timeout"),
        pytest.param(supervisor, "stdout", "timeout", "stdout_limit", id="supervisor-stdout"),
        pytest.param(supervisor, "stderr", "timeout", "stderr_limit", id="supervisor-stderr"),
        pytest.param(
            supervisor,
            "capture_error",
            "timeout",
            "stream_capture_failed",
            id="supervisor-capture-error",
        ),
        pytest.param(remote_verifier, "deadline", "timeout", "timeout", id="verifier-timeout"),
        pytest.param(
            remote_verifier,
            "deadline",
            "overall_deadline",
            "overall_deadline",
            id="verifier-overall-deadline",
        ),
        pytest.param(
            remote_verifier,
            "stdout",
            "timeout",
            "stdout_limit",
            id="verifier-stdout",
        ),
        pytest.param(
            remote_verifier,
            "stderr",
            "timeout",
            "stderr_limit",
            id="verifier-stderr",
        ),
        pytest.param(
            remote_verifier,
            "capture_error",
            "timeout",
            "stream_capture_failed",
            id="verifier-capture-error",
        ),
    ],
)
def test_remote_completion_every_forced_reason_runs_tree_cleanup_before_classification(
    module: Any,
    trigger: str,
    deadline_reason: str,
    expected_reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _RemoteCompletionProcess()
    job = _RemoteCompletionJob()
    cleanup_calls: list[tuple[Any, Any, int]] = []

    def spawn(*_args: Any, **_kwargs: Any) -> tuple[Any, Any]:
        return process, job

    def capture(stream: _RemoteCompletionStream, state: Any) -> None:
        if trigger == stream.stream_name:
            state.data.extend(b"X" * state.cap)
            state.overflow.set()
        elif trigger == "capture_error" and stream.stream_name == "stdout":
            state.failed.set()

    def cleanup(process_arg: Any, job_arg: Any, *, deadline_ns: int) -> bool:
        cleanup_calls.append((process_arg, job_arg, deadline_ns))
        process.exit_code = 1
        job.active = 0
        return True

    monkeypatch.setattr(module, "_spawn_suspended", spawn)
    monkeypatch.setattr(module, "_capture_stream", capture)
    monkeypatch.setattr(module, "_cleanup_tree", cleanup)
    arguments: dict[str, Any] = {
        "cwd": module._NEUTRAL_GIT_CWD,
        "environment": module._git_environment(),
        "live_deadline_ns": (
            module.time.monotonic_ns() + 10_000_000
            if trigger == "deadline"
            else 10**30
        ),
        "cleanup_deadline_ns": module.time.monotonic_ns() + 10_000_000_000,
        "stdout_cap": 11,
        "stderr_cap": 13,
        "deadline_reason": deadline_reason,
    }
    result = module._run_bounded_process(["synthetic-child"], **arguments)

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0][0] is process
    assert cleanup_calls[0][1] is job
    assert cleanup_calls[0][2] > 0
    assert job.closed is True
    assert result.reason == expected_reason
    assert result.cleanup_passes is True
    assert result.timed_out is (expected_reason in {"timeout", "overall_deadline"})
    if expected_reason == "stdout_limit":
        assert result.stdout == b"X" * 11
    if expected_reason == "stderr_limit":
        assert result.stderr == b"X" * 13


def _remote_completion_supervisor_registration() -> Any:
    return supervisor._Registration(
        value={"content_sha256": "a" * 64},
        execution={
            "argv_hashes": {
                "remote_supervisor": supervisor.canonical_sha256(
                    supervisor._expected_supervisor_argv()
                ),
                "remote_verifier": supervisor.canonical_sha256(
                    supervisor._expected_verifier_argv()
                ),
            }
        },
        supervisor_manifest={"git_blob_sha1": "b" * 40, "sha256": "c" * 64},
        verifier_manifest={"git_blob_sha1": "d" * 40, "sha256": "e" * 64},
    )


def test_remote_completion_supervisor_bounds_child_cleanup_before_receipt_reserve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _remote_completion_supervisor_registration()
    base = 17_000_000_000
    claim_path = tmp_path / "claim.json"
    start_path = tmp_path / "start.json"
    remote_path = tmp_path / "remote.json"
    supervisor_path = tmp_path / "supervisor.json"
    for name, value in (
        ("_CLAIM_PATH", claim_path),
        ("_START_CLAIM_PATH", start_path),
        ("_REMOTE_RECEIPT_PATH", remote_path),
        ("_SUPERVISOR_RECEIPT_PATH", supervisor_path),
    ):
        monkeypatch.setattr(supervisor, name, str(value))
    monkeypatch.setattr(supervisor, "_validate_invocation", lambda *_args: tmp_path)
    snapshot = object()
    monkeypatch.setattr(
        supervisor,
        "_capture_repository_snapshot",
        lambda *_args: snapshot,
    )
    monkeypatch.setattr(supervisor, "_load_registration", lambda _root: registration)
    tools = ({"path": "python", "version": "v", "sha256": "1" * 64},) * 3
    monkeypatch.setattr(supervisor, "_validate_tools", lambda: tools)
    monkeypatch.setattr(supervisor.time, "monotonic_ns", lambda: base)
    repository_deadlines: list[int] = []
    child_calls: list[tuple[list[str], dict[str, Any]]] = []
    publications: list[tuple[Path, str]] = []

    def repository_identity(
        _root: Path,
        _registration: Any,
        *,
        overall_deadline_ns: int,
        repository_snapshot: Any,
    ) -> str:
        assert repository_snapshot is snapshot
        repository_deadlines.append(overall_deadline_ns)
        return "f" * 40

    def bounded(argv: Any, **kwargs: Any) -> Any:
        child_calls.append((list(argv), dict(kwargs)))
        return supervisor._ManagedResult(
            False,
            None,
            b"",
            b"",
            0,
            "spawn_error",
            False,
            None,
        )

    def publish(
        path: Path,
        value: Any,
        validate: Any,
        purpose: str,
    ) -> bytes:
        validate(value)
        publications.append((path, purpose))
        return supervisor.canonical_json_bytes(value)

    monkeypatch.setattr(supervisor, "_validate_repository_identity", repository_identity)
    monkeypatch.setattr(supervisor, "_run_bounded_process", bounded)
    monkeypatch.setattr(supervisor, "_publish_canonical", publish)
    argv = supervisor._expected_supervisor_argv()[4:]

    assert supervisor.main(argv) == 1
    assert repository_deadlines == [
        base + supervisor._VERIFIER_CHILD_DEADLINE_SECONDS * 1_000_000_000
    ]
    assert len(child_calls) == 1
    child_argv, child_kwargs = child_calls[0]
    assert child_argv == supervisor._expected_verifier_argv()
    assert child_kwargs["live_deadline_ns"] == (
        base + supervisor._VERIFIER_CHILD_DEADLINE_SECONDS * 1_000_000_000
    )
    assert child_kwargs["cleanup_deadline_ns"] == base + (
        supervisor._SUPERVISOR_DEADLINE_SECONDS
        - supervisor._SUPERVISOR_RECEIPT_RESERVE_SECONDS
    ) * 1_000_000_000
    assert (
        base + supervisor._SUPERVISOR_DEADLINE_SECONDS * 1_000_000_000
        - child_kwargs["cleanup_deadline_ns"]
        == supervisor._SUPERVISOR_RECEIPT_RESERVE_SECONDS * 1_000_000_000
    )
    assert publications == [
        (claim_path, "lifecycle-claim"),
        (supervisor_path, "supervisor-receipt"),
    ]


def test_p8v3_remote_duration_fields_are_actual_and_not_deadline_clamped() -> None:
    registration = remote_verifier._Registration(
        value={"content_sha256": "a" * 64},
        data=b"registration",
        execution={},
        supervisor_manifest={},
        verifier_manifest={},
    )
    lifecycle_claim = {"open_freeze_commit_sha": "b" * 40}
    python = {"path": "python", "version": "v", "sha256": "1" * 64}
    git = {"path": "git", "version": "v", "sha256": "2" * 64}
    taskkill = {"path": "taskkill", "version": "v", "sha256": "3" * 64}
    remote_receipt = remote_verifier._receipt_object(
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256="5" * 64,
        python=python,
        git=git,
        taskkill=taskkill,
        attempts=[],
        status="failed",
        selected_attempt=None,
        total_duration_milliseconds=500_000,
    )
    remote_verifier._validate_receipt(
        remote_receipt,
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256="5" * 64,
        python=python,
        git=git,
        taskkill=taskkill,
    )

    supervisor_registration = _remote_completion_supervisor_registration()
    supervisor_result = supervisor._ManagedResult(
        spawned=False,
        exit_code=None,
        stdout=b"",
        stderr=b"",
        duration_milliseconds=500_000,
        reason="spawn_error",
        timed_out=False,
        cleanup_passes=None,
    )
    supervisor_receipt = supervisor._supervisor_receipt_object(
        registration=supervisor_registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256=None,
        remote_receipt_sha256=None,
        result=supervisor_result,
        classification="spawn_error",
        status="failed",
    )
    supervisor._validate_supervisor_receipt(
        supervisor_receipt,
        registration=supervisor_registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256=None,
        remote_receipt_sha256=None,
        remote_status=None,
    )
    verifier_source = (
        ROOT / "scripts/verify_action_qbc_v8_remote_tag.py"
    ).read_text(encoding="utf-8")
    assert "min(total_milliseconds" not in verifier_source


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v3_remote_timeout_evidence_cannot_precede_its_live_threshold(
    module: Any,
) -> None:
    empty = b""
    attempt = {
        "attempt_index": 1,
        "exit_code": module._SYNTHETIC_TIMEOUT_EXIT,
        "classification": "retryable_timeout_124",
        "timed_out": True,
        "duration_milliseconds": module._ATTEMPT_TIMEOUT_SECONDS * 1_000,
        **module._stream_fields("stdout", empty),
        **module._stream_fields("stderr", empty),
        "child_cleanup_passes": True,
    }
    assert module._validate_attempt(attempt, 1, b"expected") == (
        "retryable_timeout_124",
        module._ATTEMPT_TIMEOUT_SECONDS * 1_000,
    )
    attempt["duration_milliseconds"] -= 1
    with pytest.raises(module._ProtocolFailure, match="timeout attempt evidence"):
        module._validate_attempt(attempt, 1, b"expected")


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v3_remote_spawn_failure_duration_uses_actual_monotonic_interval(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter([0, 500_000_000_000])
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: next(clock))
    monkeypatch.setattr(
        module,
        "_spawn_suspended",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("spawn failed")),
    )
    result = module._run_bounded_process(
        ["synthetic"],
        cwd=module._NEUTRAL_GIT_CWD,
        environment=module._git_environment(),
        live_deadline_ns=10**30,
        cleanup_deadline_ns=10**30,
        stdout_cap=1,
        stderr_cap=1,
        deadline_reason="timeout",
    )
    assert result.spawned is False
    assert result.duration_milliseconds == 500_000


def test_p8v3_remote_attempt_admission_uses_distinct_live_and_cleanup_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = 1_000_000_000
    expected = b"b" * 40 + b"\t" + remote_verifier._REMOTE_REF.encode() + b"\n"
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(remote_verifier.time, "monotonic_ns", lambda: origin)

    def bounded(_argv: Any, **kwargs: Any) -> Any:
        calls.append(dict(kwargs))
        return remote_verifier._ManagedResult(
            True, 0, expected, b"", 1, None, False, None
        )

    monkeypatch.setattr(remote_verifier, "_run_bounded_process", bounded)
    live = origin + 120 * 1_000_000_000
    cleanup = origin + 150 * 1_000_000_000
    assert (
        remote_verifier._remote_attempt(
            1,
            live_admission_deadline_ns=live,
            cleanup_deadline_ns=cleanup,
            expected_stdout=expected,
        )
        is not None
    )
    assert calls[0]["live_deadline_ns"] == live
    assert calls[0]["cleanup_deadline_ns"] == cleanup
    assert calls[0]["duration_start_ns"] == origin
    assert (
        remote_verifier._remote_attempt(
            1,
            live_admission_deadline_ns=live - 1,
            cleanup_deadline_ns=cleanup,
            expected_stdout=expected,
        )
        is None
    )
    assert (
        remote_verifier._remote_attempt(
            1,
            live_admission_deadline_ns=live,
            cleanup_deadline_ns=cleanup - 1,
            expected_stdout=expected,
        )
        is None
    )
    assert len(calls) == 1


def test_remote_completion_durable_supervisor_claim_blocks_second_child_after_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = _remote_completion_supervisor_registration()
    paths = {
        "_CLAIM_PATH": tmp_path / "claim.json",
        "_START_CLAIM_PATH": tmp_path / "start.json",
        "_REMOTE_RECEIPT_PATH": tmp_path / "remote.json",
        "_SUPERVISOR_RECEIPT_PATH": tmp_path / "supervisor.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(supervisor, name, str(path))
    monkeypatch.setattr(supervisor, "_validate_invocation", lambda *_args: tmp_path)
    repository_snapshot = object()
    monkeypatch.setattr(
        supervisor,
        "_capture_repository_snapshot",
        lambda *_args: repository_snapshot,
    )
    monkeypatch.setattr(supervisor, "_load_registration", lambda _root: registration)
    tool = {"path": "tool", "version": "v", "sha256": "1" * 64}
    monkeypatch.setattr(supervisor, "_validate_tools", lambda: (tool, tool, tool))
    monkeypatch.setattr(
        supervisor,
        "_validate_repository_identity",
        lambda *_args, **_kwargs: "f" * 40,
    )
    child_calls = 0

    def crash_after_claim(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal child_calls
        child_calls += 1
        raise SystemExit(91)

    monkeypatch.setattr(supervisor, "_run_bounded_process", crash_after_claim)
    argv = supervisor._expected_supervisor_argv()[4:]

    with pytest.raises(SystemExit, match="91"):
        supervisor.main(argv)
    claim_raw = paths["_CLAIM_PATH"].read_bytes()
    assert set(supervisor._parse_canonical_object(claim_raw, "claim")) == (
        supervisor._CLAIM_KEYS
    )
    with pytest.raises(supervisor._ProtocolFailure, match="already exists"):
        supervisor.main(argv)
    assert child_calls == 1
    assert paths["_CLAIM_PATH"].read_bytes() == claim_raw


def test_remote_completion_durable_verifier_start_claim_blocks_second_online_attempt_after_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = remote_verifier._Registration(
        value={"content_sha256": "a" * 64},
        data=b"registration",
        execution={"argv_hashes": {"remote_verifier": "b" * 64}},
        supervisor_manifest={},
        verifier_manifest={},
    )
    lifecycle_path = tmp_path / "lifecycle.json"
    start_path = tmp_path / "start.json"
    receipt_path = tmp_path / "receipt.json"
    lifecycle_path.write_bytes(b"synthetic-lifecycle-claim")
    monkeypatch.setattr(remote_verifier, "_CLAIM_PATH", str(lifecycle_path))
    monkeypatch.setattr(remote_verifier, "_START_CLAIM_PATH", str(start_path))
    monkeypatch.setattr(remote_verifier, "_RECEIPT_PATH", str(receipt_path))
    monkeypatch.setattr(remote_verifier, "_validate_invocation", lambda *_args: tmp_path)
    repository_snapshot = object()
    monkeypatch.setattr(
        remote_verifier,
        "_capture_repository_snapshot",
        lambda *_args: repository_snapshot,
    )
    monkeypatch.setattr(
        remote_verifier,
        "_load_registration",
        lambda *_args: registration,
    )
    tool = {"path": "tool", "version": "v", "sha256": "1" * 64}
    monkeypatch.setattr(remote_verifier, "_validate_tools", lambda: (tool, tool, tool))
    lifecycle_claim = {"open_freeze_commit_sha": "c" * 40}
    monkeypatch.setattr(
        remote_verifier,
        "_validate_lifecycle_claim",
        lambda *_args: (lifecycle_claim, "d" * 64),
    )
    monkeypatch.setattr(
        remote_verifier,
        "_validate_repository_identity",
        lambda *_args, **_kwargs: None,
    )
    online_calls = 0

    def crash_online(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal online_calls
        online_calls += 1
        raise SystemExit(92)

    monkeypatch.setattr(remote_verifier, "_run_attempts", crash_online)
    argv = remote_verifier._expected_verifier_argv()[4:]

    with pytest.raises(SystemExit, match="92"):
        remote_verifier.main(argv)
    start_raw = start_path.read_bytes()
    assert set(remote_verifier._parse_canonical_object(start_raw, "start")) == (
        remote_verifier._START_CLAIM_KEYS
    )
    assert not receipt_path.exists()
    with pytest.raises(remote_verifier._ProtocolFailure, match="already exists"):
        remote_verifier.main(argv)
    assert online_calls == 1
    assert start_path.read_bytes() == start_raw


def test_p8v7_verifier_real_sibling_start_claim_precedes_snapshot_and_admits_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    lifecycle_path = tmp_path / "remote-verification-claim-v4.json"
    start_path = tmp_path / "remote-verifier-start-claim-v4.json"
    receipt_path = tmp_path / "remote-verification-v4.json"
    lifecycle_path.write_bytes(b"synthetic-lifecycle-claim")
    registration = remote_verifier._Registration(
        value={"content_sha256": "a" * 64},
        data=b"registration",
        execution={"argv_hashes": {"remote_verifier": "b" * 64}},
        supervisor_manifest={},
        verifier_manifest={},
    )
    lifecycle_claim = {"open_freeze_commit_sha": "c" * 40}
    tool = {"path": "tool", "version": "v", "sha256": "1" * 64}
    events: list[str] = []
    parent_snapshot: tuple[int, int, int] | None = None

    monkeypatch.setattr(remote_verifier, "_CLAIM_PATH", str(lifecycle_path))
    monkeypatch.setattr(remote_verifier, "_START_CLAIM_PATH", str(start_path))
    monkeypatch.setattr(remote_verifier, "_RECEIPT_PATH", str(receipt_path))
    monkeypatch.setattr(
        remote_verifier,
        "_validate_invocation",
        lambda *_args: repository_root,
    )
    monkeypatch.setattr(
        remote_verifier,
        "_load_registration",
        lambda *_args: registration,
    )
    monkeypatch.setattr(remote_verifier, "_validate_tools", lambda: (tool, tool, tool))
    monkeypatch.setattr(
        remote_verifier,
        "_validate_lifecycle_claim",
        lambda *_args: (lifecycle_claim, "d" * 64),
    )

    def capture(_contract: dict[str, Any]) -> object:
        nonlocal parent_snapshot
        assert start_path.is_file()
        start = remote_verifier._parse_canonical_object(
            start_path.read_bytes(), "verifier-start claim"
        )
        assert set(start) == remote_verifier._START_CLAIM_KEYS
        metadata = tmp_path.stat()
        parent_snapshot = (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns)
        events.append("snapshot_after_start")
        return object()

    def validate_identity(
        _root: Path,
        _registration: Any,
        _commit: str,
        **kwargs: Any,
    ) -> None:
        assert kwargs["repository_snapshot"] is not None
        assert start_path.is_file()
        metadata = tmp_path.stat()
        assert parent_snapshot == (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mtime_ns,
        )
        events.append("unchanged_identity")

    def admitted_attempts(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        assert events == ["snapshot_after_start", "unchanged_identity"]
        expected_stdout = kwargs["expected_stdout"]
        attempt = remote_verifier._attempt_record(
            1,
            remote_verifier._ManagedResult(
                spawned=True,
                exit_code=0,
                stdout=expected_stdout,
                stderr=b"",
                duration_milliseconds=0,
                reason=None,
                timed_out=False,
                cleanup_passes=None,
            ),
            expected_stdout=expected_stdout,
        )
        events.append("attempt_admitted")
        return [attempt], 1

    monkeypatch.setattr(remote_verifier, "_capture_repository_snapshot", capture)
    monkeypatch.setattr(
        remote_verifier,
        "_validate_repository_identity",
        validate_identity,
    )
    monkeypatch.setattr(remote_verifier, "_run_attempts", admitted_attempts)

    assert remote_verifier.main(remote_verifier._expected_verifier_argv()[4:]) == 0
    receipt = remote_verifier._parse_canonical_object(
        receipt_path.read_bytes(), "remote receipt"
    )
    assert events == [
        "snapshot_after_start",
        "unchanged_identity",
        "attempt_admitted",
    ]
    assert receipt["status"] == "verified"
    assert receipt["selected_attempt"] == 1
    assert len(receipt["attempts"]) == 1


@pytest.mark.skipif(os.name != "nt", reason="registered Windows invocation boundary")
@pytest.mark.parametrize(
    ("module", "script_name", "expected_argv_name"),
    [
        pytest.param(
            supervisor,
            supervisor._SUPERVISOR_SCRIPT,
            "_expected_supervisor_argv",
            id="supervisor",
        ),
        pytest.param(
            remote_verifier,
            remote_verifier._VERIFIER_SCRIPT,
            "_expected_verifier_argv",
            id="verifier",
        ),
    ],
)
def test_remote_completion_invocation_accepts_exactly_the_one_registered_command(
    module: Any,
    script_name: str,
    expected_argv_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    neutral = tmp_path / "neutral"
    root.mkdir()
    neutral.mkdir()
    script = root / Path(script_name)
    script.parent.mkdir(parents=True)
    script.write_bytes(b"# synthetic origin\n")
    monkeypatch.chdir(root)
    monkeypatch.setattr(module, "_REPOSITORY_ROOT", str(root))
    monkeypatch.setattr(module, "_NEUTRAL_GIT_CWD", str(neutral))
    monkeypatch.setattr(module, "_NONEXISTENT_HOME", str(tmp_path / "absent-home"))
    monkeypatch.setattr(module.sys, "executable", module._PYTHON_PATH)
    monkeypatch.setattr(
        module.sys,
        "flags",
        SimpleNamespace(isolated=1, dont_write_bytecode=1),
    )
    monkeypatch.setattr(module.sys, "argv", [str(script)])
    expected_argv = getattr(module, expected_argv_name)()
    arguments = expected_argv[4:]
    parsed = module._parser().parse_args(arguments)
    observed = [expected_argv[3], *arguments]

    assert module._validate_invocation(parsed, observed) == root.resolve(strict=True)
    with pytest.raises(module._ProtocolFailure, match="argv differs"):
        module._validate_invocation(parsed, [*observed, "--unregistered"])


def _schema_gap_mutations(
    value: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    import copy

    result: list[tuple[str, dict[str, Any]]] = []
    for key in sorted(value):
        candidate = copy.deepcopy(value)
        del candidate[key]
        result.append((f"missing:{key}", candidate))
    candidate = copy.deepcopy(value)
    candidate["__unexpected_schema_key__"] = None
    result.append(("extra:__unexpected_schema_key__", candidate))
    return result


_SCHEMA_GAP_REGISTRATION_CACHE: list[dict[str, Any]] = []


def _schema_gap_full_registration() -> dict[str, Any]:
    import scripts.reconstruct_action_qbc_v8_open_registration as reconstruction

    if _SCHEMA_GAP_REGISTRATION_CACHE:
        return _SCHEMA_GAP_REGISTRATION_CACHE[0]
    preregistration_entries = reconstruction._tree_entries(
        ROOT, reconstruction.PREREGISTRATION_COMMIT
    )
    preregistration_manifest, _ = reconstruction._manifest_and_blobs(
        ROOT, preregistration_entries
    )
    anchors = reconstruction._verify_frozen_anchors(ROOT)
    added_manifest: list[dict[str, object]] = []
    added_blobs: dict[str, bytes] = {}
    for relative in reconstruction.NON_REGISTRATION_ADDITIONS:
        raw = (ROOT / relative).read_bytes()
        added_blobs[relative] = raw
        header = f"blob {len(raw)}\0".encode("ascii")
        added_manifest.append(
            {
                "mode": "100644",
                "path": relative,
                "git_blob_sha1": hashlib.sha1(
                    header + raw, usedforsecurity=False
                ).hexdigest(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        )
    added_manifest.sort(key=lambda row: str(row["path"]).encode("utf-8"))
    value = reconstruction._assemble_registration(
        preregistration_manifest,
        added_manifest,
        added_blobs,
        anchors,
    )
    assert set(value) == reconstruction.TOP_LEVEL_KEYS
    _SCHEMA_GAP_REGISTRATION_CACHE.append(value)
    return value


def _schema_gap_fallback_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], dict[str, Any], bytes, str, str]:
    import arc3_voi.action_qbc_v8_audit as v8_audit
    import scripts.reconstruct_action_qbc_v8_open_registration as reconstruction

    registration = _schema_gap_full_registration()
    registration_raw = reconstruction.canonical_json_bytes(registration)
    commit = "d" * 40
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text(commit + "\n", encoding="ascii")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "action_qbc_v8_open_registration.json").write_bytes(
        registration_raw
    )
    (tmp_path / "uv.lock").write_bytes((ROOT / "uv.lock").read_bytes())
    monkeypatch.chdir(tmp_path)
    payload = v8_audit.build_global_fallback(
        registration,
        "evaluator_internal_error",
        repository_root=tmp_path,
    )
    validated = v8_audit.validate_scientific_payload(payload, registration)
    raw = v8_audit.canonical_json_bytes(validated)
    process_a_output = (
        tmp_path
        / "process-a-output"
        / "open"
        / "action_qbc_v8_open_diagnostic.json"
    )
    process_b_output = (
        tmp_path
        / "process-b-output"
        / "open"
        / "action_qbc_v8_open_diagnostic.json"
    )
    for output in (process_a_output, process_b_output):
        output.parent.mkdir(parents=True)
        output.write_bytes(raw)
        output.chmod(0o600)
    monkeypatch.setattr(lifecycle, "_A_OUTPUT", process_a_output)
    monkeypatch.setattr(lifecycle, "_B_OUTPUT", process_b_output)
    monkeypatch.setattr(finalizer, "_PROCESS_A", str(process_a_output))
    monkeypatch.setattr(finalizer, "_PROCESS_B", str(process_b_output))
    _rebind_evidence_paths(
        monkeypatch,
        lifecycle,
        process_a_payload=process_a_output,
        process_b_payload=process_b_output,
    )
    _rebind_evidence_paths(
        monkeypatch,
        finalizer,
        process_a_payload=process_a_output,
        process_b_payload=process_b_output,
    )
    real_evidence_state = lifecycle._evidence_state

    def fixture_evidence_state(
        path: Path,
        label: str,
        *,
        role: str,
        maximum: int = lifecycle._EVIDENCE_CAP,
    ) -> Any:
        if path in {process_a_output, process_b_output}:
            observed = path.read_bytes()
            assert len(observed) <= maximum
            return lifecycle._EvidenceState(
                True,
                "readable",
                observed,
                hashlib.sha256(observed).hexdigest(),
                None,
            )
        return real_evidence_state(path, label, role=role, maximum=maximum)

    real_finalizer_plain = finalizer._plain

    def fixture_finalizer_plain(
        path: Path,
        name: str,
        *,
        maximum: int = finalizer._MAX_JSON,
    ) -> bytes:
        if path in {process_a_output, process_b_output}:
            observed = path.read_bytes()
            assert len(observed) <= maximum
            return observed
        return real_finalizer_plain(path, name, maximum=maximum)

    monkeypatch.setattr(lifecycle, "_evidence_state", fixture_evidence_state)
    monkeypatch.setattr(finalizer, "_plain", fixture_finalizer_plain)
    return (
        registration,
        validated,
        raw,
        commit,
        hashlib.sha256(registration_raw).hexdigest(),
    )


@pytest.mark.parametrize(
    "phase",
    ["pre_deadline", "producer", "post_deadline", "finalizer", "validator", "encoder"],
)
def test_schema_gap_global_fallback_required_at_each_frozen_try_operation(
    phase: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer_calls = 0
    monotonic_calls = 0

    def injected_fallback() -> _Fallback:
        return _Fallback("payload_size_limit_exceeded", 12_345)

    def monotonic() -> float:
        nonlocal monotonic_calls
        monotonic_calls += 1
        if phase == "pre_deadline" and monotonic_calls == 1:
            raise injected_fallback()
        if phase == "post_deadline" and monotonic_calls == 2:
            raise injected_fallback()
        return 0.0

    def producer(
        _root: Path,
        _registration: Any,
        *,
        compute_deadline: float,
    ) -> dict[str, bool]:
        nonlocal producer_calls
        assert compute_deadline == 10.0
        producer_calls += 1
        if phase == "producer":
            raise injected_fallback()
        return {"candidate": True}

    def finalize(candidate: Any, _registration: Any) -> Any:
        if phase == "finalizer":
            raise injected_fallback()
        return candidate

    def validate(payload: Any, _registration: Any) -> Any:
        if phase == "validator" and not (
            isinstance(payload, dict) and "fallback" in payload
        ):
            raise injected_fallback()
        return payload

    def encode(payload: Any) -> bytes:
        if phase == "encoder" and not (
            isinstance(payload, dict) and "fallback" in payload
        ):
            raise injected_fallback()
        if isinstance(payload, dict) and "fallback" in payload:
            return b'{"fallback":true}'
        return b'{"candidate":true}'

    monkeypatch.setattr(runner.time, "monotonic", monotonic)
    payload, encoded = runner._evaluate(
        _audit_stub(
            producer=producer,
            finalizer=finalize,
            validator_fn=validate,
            encoder=encode,
        ),
        Path("."),
        {},
        compute_deadline=10.0,
    )

    assert payload == {
        "fallback": "payload_size_limit_exceeded",
        "candidate_payload_size_bytes": 12_345,
    }
    assert encoded == b'{"fallback":true}'
    assert producer_calls == (0 if phase == "pre_deadline" else 1)


def test_schema_gap_canonical_v8_fallback_replay_is_byte_identical_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    import arc3_voi.action_qbc_v8_audit as v8_audit

    registration, payload, first, _commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    replayed_once = v8_audit.validate_scientific_payload(
        json.loads(first.decode("ascii")), registration
    )
    second = v8_audit.canonical_json_bytes(replayed_once)
    replayed_twice = v8_audit.validate_scientific_payload(
        json.loads(second.decode("ascii")), registration
    )
    third = v8_audit.canonical_json_bytes(replayed_twice)

    assert replayed_once == payload
    assert replayed_twice == payload
    assert first == second == third


def test_schema_gap_payload_rejects_every_removed_key_and_one_extra_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arc3_voi.action_qbc_v8_audit as v8_audit

    registration, payload, _raw, _commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    assert set(payload) == set(v8_audit.TOP_LEVEL_KEYS)
    assert len(payload) == 19
    for _mutation, candidate in _schema_gap_mutations(payload):
        with pytest.raises(v8_audit.V7AuditError):
            v8_audit.validate_scientific_payload(candidate, registration)


def _schema_gap_successful_machine(
    *,
    registration: dict[str, Any],
    commit: str,
    registration_sha: str,
    payload_raw: bytes,
) -> dict[str, Any]:
    digest = hashlib.sha256(payload_raw).hexdigest()

    def sha(label: str) -> str:
        return hashlib.sha256(label.encode("ascii")).hexdigest()

    execution = registration["execution_contract"]
    tree_sha = sha("preparation-tree")
    raw_materialization_sha = sha("preparation-raw")
    inventory = [
        {
            "normalized_name": name,
            "version": version,
            "file_count": 1,
            "files_sha256": sha(f"record:{name}"),
        }
        for name, version in (
            ("arc3-crosslevel-voi", "0.1.0"),
            ("numpy", "2.5.1"),
            ("pyyaml", "6.0.3"),
        )
    ]
    inventory_sha = lifecycle.canonical_sha256(inventory)
    venv_sha = sha("complete-venv-materialization")
    python_sha = sha("resolved-venv-python")

    def clone(root: str, *, environment: bool, inode: int) -> dict[str, Any]:
        return {
            "root": root,
            "root_device": 1,
            "root_inode": inode,
            "root_owner_uid": 1000,
            "root_mode": 0o700,
            "head_sha": commit,
            "tree_sha256": tree_sha,
            "raw_materialization_sha256": raw_materialization_sha,
            "git_status_sha256": hashlib.sha256(b"").hexdigest(),
            "python_version": "3.12.13" if environment else None,
            "uv_version": "0.11.28" if environment else None,
            "environment_inventory": inventory if environment else None,
            "environment_inventory_sha256": inventory_sha if environment else None,
            "venv_materialization_sha256": venv_sha if environment else None,
            "venv_python_sha256": python_sha if environment else None,
            "passes": True,
        }

    execution_root = str(execution["execution_root"]).rstrip("/")
    preparation_source = f"{execution_root}/.prepare-attempt-1"
    manifest = registration["source_manifest"]
    manifest_rows = [
        *manifest["preregistration_tree"],
        *manifest["open_freeze_added_files"],
    ]
    registration_raw = lifecycle.canonical_json_bytes(registration)
    manifest_rows.append(
        {
            "mode": "100644",
            "path": "artifacts/action_qbc_v8_open_registration.json",
            "git_blob_sha1": hashlib.sha1(
                b"blob "
                + str(len(registration_raw)).encode("ascii")
                + b"\0"
                + registration_raw,
                usedforsecurity=False,
            ).hexdigest(),
            "byte_count": len(registration_raw),
        }
    )
    entries = [
        preparation._TreeEntry(
            mode=str(row["mode"]),
            path=str(row["path"]),
            oid=str(row["git_blob_sha1"]),
            size=int(row["byte_count"]),
        )
        for row in sorted(
            manifest_rows,
            key=lambda row: str(row["path"]).encode("utf-8"),
        )
    ]

    def preparation_posix_path(value: str) -> str:
        normalized = value.replace("\\", "/")
        if len(normalized) >= 3 and normalized[1:3] == ":/":
            normalized = normalized[2:]
        return normalized

    authority_entries = [
        (entry.mode, entry.path, entry.oid, entry.size) for entry in entries
    ]
    command_identities = [
        *reconstruction._expected_authority_identities(
            Path(execution["authority_root"]),
            commit,
            authority_entries,
        ),
        *preparation._expected_attempt_identities(
            Path(execution_root),
            1,
            commit,
            entries,
        ),
    ]
    command_ledger: list[dict[str, Any]] = []
    for sequence_index, identity in enumerate(command_identities):
        identity = dict(identity)
        identity["cwd"] = preparation_posix_path(str(identity["cwd"]))
        identity["argv"] = [
            preparation_posix_path(str(argument))
            for argument in identity["argv"]
        ]
        identity["argv_sha256"] = lifecycle.canonical_sha256(identity["argv"])
        command_ledger.append(
            {
                "sequence_index": sequence_index,
                **identity,
                "started": True,
                "exit_code": 0,
                "outcome": "completed",
                "timed_out": False,
                "duration_milliseconds": 0,
                "stdout_size_bytes": 0,
                "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                "stderr_size_bytes": 0,
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "child_cleanup_passes": None,
            }
        )
    preparation_receipt: dict[str, Any] = {
        "schema_version": preparation._PREPARATION_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "attempts": [
            {
                "attempt_index": 1,
                "process_a_stage": "completed",
                "process_b_stage": "completed",
                "cleanup": {
                    "owned_paths": [preparation_source],
                    "removed": [],
                    "passes": True,
                },
                "promotion": {
                    "source_path": preparation_source,
                    "destination_path": f"{execution_root}/processes",
                    "source_device": 1,
                    "source_inode": 1,
                    "passes": True,
                },
                "passes": True,
            }
        ],
        "authority": clone(
            execution["authority_root"], environment=False, inode=2
        ),
        "process_a": clone(
            execution["process_a_root"], environment=True, inode=3
        ),
        "process_b": clone(
            execution["process_b_root"], environment=True, inode=4
        ),
        "command_ledger": command_ledger,
        "commands_sha256": lifecycle.canonical_sha256(command_ledger),
        "command_environment_sha256": lifecycle.canonical_sha256(
            execution["preparation_command_environment"]
        ),
        "status": "prepared",
    }
    preparation_verification_receipt: dict[str, Any] = {
        "schema_version": preparation._PREPARATION_VERIFICATION_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "preparation_receipt_sha256": lifecycle.canonical_sha256(
            preparation_receipt
        ),
        "verification_argv_sha256": lifecycle.canonical_sha256(
            execution["post_preparation_validation_argv"]
        ),
        "authority": {
            key: value
            for key, value in preparation_receipt["authority"].items()
            if key != "environment_inventory"
        },
        "process_a": {
            key: value
            for key, value in preparation_receipt["process_a"].items()
            if key != "environment_inventory"
        },
        "process_b": {
            key: value
            for key, value in preparation_receipt["process_b"].items()
            if key != "environment_inventory"
        },
        "status": "verified",
    }
    preparation_verification_receipt["content_sha256"] = (
        lifecycle.canonical_sha256(preparation_verification_receipt)
    )
    additions = {
        row["path"]: row for row in registration["source_manifest"]["open_freeze_added_files"]
    }
    supervisor_source = additions["scripts/supervise_action_qbc_v8_remote_tag.py"]
    verifier_source = additions["scripts/verify_action_qbc_v8_remote_tag.py"]
    remote_claim: dict[str, Any] = {
        "schema_version": "action-qbc-v8-remote-tag-verification-claim-v1",
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "supervisor_argv_sha256": execution["argv_hashes"]["remote_supervisor"],
        "supervisor_script_git_blob_sha1": supervisor_source["git_blob_sha1"],
        "supervisor_script_sha256": supervisor_source["sha256"],
        "verifier_script_git_blob_sha1": verifier_source["git_blob_sha1"],
        "verifier_script_sha256": verifier_source["sha256"],
    }
    remote_verifier_claim: dict[str, Any] = {
        "schema_version": "action-qbc-v8-remote-tag-verifier-start-claim-v1",
        "treatment_id": lifecycle._TREATMENT_ID,
        "claim_sha256": lifecycle.canonical_sha256(remote_claim),
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "verifier_argv_sha256": execution["argv_hashes"]["remote_verifier"],
    }
    expected_stdout = (
        f"{commit}\trefs/tags/{lifecycle._OPEN_FREEZE_TAG}\n".encode("ascii")
    )
    verified_attempt = {
        "attempt_index": 1,
        "exit_code": 0,
        "classification": "verified",
        "timed_out": False,
        "duration_milliseconds": 0,
        "stdout_size_bytes": len(expected_stdout),
        "stdout_sha256": hashlib.sha256(expected_stdout).hexdigest(),
        "stdout_base64": base64.b64encode(expected_stdout).decode("ascii"),
        "stderr_size_bytes": 0,
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_base64": "",
        "child_cleanup_passes": None,
    }
    remote_receipt: dict[str, Any] = {
        "schema_version": "action-qbc-v8-remote-tag-verification-receipt-v1",
        "treatment_id": lifecycle._TREATMENT_ID,
        "claim_sha256": lifecycle.canonical_sha256(remote_claim),
        "verifier_start_claim_sha256": lifecycle.canonical_sha256(
            remote_verifier_claim
        ),
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "remote_url": "https://github.com/bansarinejad/arc3-crosslevel-voi.git",
        "ref": f"refs/tags/{lifecycle._OPEN_FREEZE_TAG}",
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
        "policy": dict(execution["remote_policy"]),
        "attempts": [verified_attempt],
        "status": "verified",
        "selected_attempt": 1,
        "total_duration_milliseconds": 0,
    }
    remote_supervisor_receipt: dict[str, Any] = {
        "schema_version": (
            "action-qbc-v8-remote-tag-verification-supervisor-receipt-v1"
        ),
        "treatment_id": lifecycle._TREATMENT_ID,
        "claim_sha256": lifecycle.canonical_sha256(remote_claim),
        "verifier_start_claim_sha256": lifecycle.canonical_sha256(
            remote_verifier_claim
        ),
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "verifier_argv_sha256": execution["argv_hashes"]["remote_verifier"],
        "verifier_exit_code": 0,
        "classification": "verifier_completed",
        "timed_out": False,
        "duration_milliseconds": 0,
        "stdout_size_bytes": 0,
        "stdout_sha256": hashlib.sha256(b"").hexdigest(),
        "stdout_base64": "",
        "stderr_size_bytes": 0,
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_base64": "",
        "child_cleanup_passes": None,
        "remote_receipt_sha256": lifecycle.canonical_sha256(remote_receipt),
        "status": "completed",
    }
    arm_receipt: dict[str, Any] = {
        "schema_version": lifecycle._ARM_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "preparation_receipt_exists": True,
        "preparation_receipt_read_status": "readable",
        "preparation_receipt_sha256": lifecycle.canonical_sha256(
            preparation_receipt
        ),
        "preparation_verification_receipt_exists": True,
        "preparation_verification_receipt_read_status": "readable",
        "preparation_verification_receipt_sha256": lifecycle.canonical_sha256(
            preparation_verification_receipt
        ),
        "remote_claim_sha256": lifecycle.canonical_sha256(remote_claim),
        "remote_verifier_claim_sha256": lifecycle.canonical_sha256(
            remote_verifier_claim
        ),
        "remote_receipt_sha256": lifecycle.canonical_sha256(remote_receipt),
        "remote_supervisor_receipt_sha256": lifecycle.canonical_sha256(
            remote_supervisor_receipt
        ),
        "status": "armed",
    }
    driver_claim: dict[str, Any] = {
        "schema_version": lifecycle._DRIVER_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "remote_claim_sha256": lifecycle.canonical_sha256(remote_claim),
        "driver_argv_sha256": sha("driver-argv"),
    }

    processes: dict[str, dict[str, Any]] = {}
    prior_validation_sha: str | None = None
    for label in ("A", "B"):
        output_path = str(lifecycle._A_OUTPUT if label == "A" else lifecycle._B_OUTPUT)
        start_claim: dict[str, Any] = {
            "schema_version": "action-qbc-v8-scientific-start-claim-v1",
            "treatment_id": lifecycle._TREATMENT_ID,
            "label": label,
            "open_freeze_commit_sha": commit,
            "registration_content_sha256": registration_sha,
            "arm_receipt_sha256": lifecycle.canonical_sha256(arm_receipt),
            "lifecycle_driver_claim_sha256": lifecycle.canonical_sha256(driver_claim),
            "scientific_argv_sha256": sha(f"scientific-{label}"),
            "prior_validation_receipt_sha256": prior_validation_sha,
            "output_path": output_path,
        }
        start_sha = lifecycle.canonical_sha256(start_claim)
        validator_claim: dict[str, Any] = {
            "schema_version": "action-qbc-v8-payload-validator-claim-v1",
            "treatment_id": lifecycle._TREATMENT_ID,
            "label": label,
            "lifecycle_driver_claim_sha256": lifecycle.canonical_sha256(driver_claim),
            "start_claim_sha256": start_sha,
            "validator_argv_sha256": sha(f"validator-{label}"),
            "payload_sha256": digest,
        }
        validator_sha = lifecycle.canonical_sha256(validator_claim)
        validation_receipt: dict[str, Any] = {
            "schema_version": lifecycle._VALIDATION_SCHEMA,
            "treatment_id": lifecycle._TREATMENT_ID,
            "label": label,
            "start_claim_sha256": start_sha,
            "validator_claim_sha256": validator_sha,
            "payload_path": output_path,
            "payload_sha256": digest,
            "payload_size_bytes": len(payload_raw),
            "status": "valid",
        }
        validation_sha = lifecycle.canonical_sha256(validation_receipt)
        processes[label] = {
            "label": label,
            "output_path": output_path,
            "exit_code": 0,
            "validator_exit_code": 0,
            "start_claim": start_claim,
            "start_claim_sha256": start_sha,
            "validator_claim": validator_claim,
            "validator_claim_sha256": validator_sha,
            "validation_receipt": validation_receipt,
            "validation_receipt_sha256": validation_sha,
            "payload_exists": True,
            "payload_valid": True,
            "payload_sha256": digest,
            "payload_size_bytes": len(payload_raw),
        }
        prior_validation_sha = validation_sha

    ledger_processes: dict[str, dict[str, Any]] = {}
    for label, process in processes.items():
        ledger_processes[label] = {
            "label": label,
            "cwd": str(
                lifecycle._A_ROOT if label == "A" else lifecycle._B_ROOT
            ),
            "runner_argv_sha256": sha(f"runner-{label}"),
            "runner_exit_code": process["exit_code"],
            "validator_argv_sha256": sha(f"validator-{label}"),
            "validator_exit_code": process["validator_exit_code"],
            "start_claim_sha256": process["start_claim_sha256"],
            "validator_claim_sha256": process["validator_claim_sha256"],
            "validation_receipt_sha256": process["validation_receipt_sha256"],
            "output_sha256": process["payload_sha256"],
        }
    lifecycle_ledger: dict[str, Any] = {
        "schema_version": lifecycle._LEDGER_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "registration_content_sha256": registration_sha,
        "driver_claim_sha256": lifecycle.canonical_sha256(driver_claim),
        "arm_exit_code": 0,
        "arm_receipt_sha256": lifecycle.canonical_sha256(arm_receipt),
        "sequence": list(lifecycle._SEQUENCE),
        "process_a": ledger_processes["A"],
        "process_b": ledger_processes["B"],
        "stage": None,
    }
    return {
        "schema_version": lifecycle._RECEIPT_SCHEMA,
        "treatment_id": lifecycle._TREATMENT_ID,
        "open_freeze_commit_sha": commit,
        "open_freeze_tag": lifecycle._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "preparation_receipt": preparation_receipt,
        "preparation_receipt_exists": True,
        "preparation_receipt_read_status": "readable",
        "preparation_receipt_sha256": lifecycle.canonical_sha256(
            preparation_receipt
        ),
        "preparation_verification_receipt": preparation_verification_receipt,
        "preparation_verification_receipt_exists": True,
        "preparation_verification_receipt_read_status": "readable",
        "preparation_verification_receipt_sha256": lifecycle.canonical_sha256(
            preparation_verification_receipt
        ),
        "remote_verification_claim": remote_claim,
        "remote_verifier_claim": remote_verifier_claim,
        "remote_verification_receipt": remote_receipt,
        "remote_supervisor_receipt": remote_supervisor_receipt,
        "arm_receipt": arm_receipt,
        "lifecycle_driver_claim": driver_claim,
        "lifecycle_ledger": lifecycle_ledger,
        "process_a": processes["A"],
        "process_b": processes["B"],
        "payloads_byte_identical": True,
        "published_payload_path": "artifacts/action_qbc_v8_open_diagnostic.json",
        "published_payload_sha256": digest,
        "authorization": dict(lifecycle._AUTHORIZATION),
    }


def _schema_gap_set_if_present(
    value: object,
    key: str,
    replacement: object,
) -> None:
    if isinstance(value, dict) and key in value:
        value[key] = replacement


def _schema_gap_rehash_successful_machine(
    machine: dict[str, Any],
    *,
    rehash_preparation_verification_content: bool = True,
) -> None:
    preparation_receipt = machine["preparation_receipt"]
    preparation_verification_receipt = machine[
        "preparation_verification_receipt"
    ]
    remote_claim = machine["remote_verification_claim"]
    remote_verifier_claim = machine["remote_verifier_claim"]
    remote_receipt = machine["remote_verification_receipt"]
    remote_supervisor_receipt = machine["remote_supervisor_receipt"]
    arm_receipt = machine["arm_receipt"]
    driver_claim = machine["lifecycle_driver_claim"]
    ledger = machine["lifecycle_ledger"]

    preparation_sha = lifecycle.canonical_sha256(preparation_receipt)
    _schema_gap_set_if_present(
        preparation_verification_receipt,
        "preparation_receipt_sha256",
        preparation_sha,
    )
    if rehash_preparation_verification_content:
        verification_preimage = dict(preparation_verification_receipt)
        verification_preimage.pop("content_sha256", None)
        preparation_verification_receipt["content_sha256"] = (
            lifecycle.canonical_sha256(verification_preimage)
        )
    preparation_verification_sha = lifecycle.canonical_sha256(
        preparation_verification_receipt
    )
    for prefix, digest in (
        ("preparation_receipt", preparation_sha),
        ("preparation_verification_receipt", preparation_verification_sha),
    ):
        _schema_gap_set_if_present(machine, f"{prefix}_exists", True)
        _schema_gap_set_if_present(machine, f"{prefix}_read_status", "readable")
        _schema_gap_set_if_present(machine, f"{prefix}_sha256", digest)

    remote_claim_sha = lifecycle.canonical_sha256(remote_claim)
    _schema_gap_set_if_present(remote_verifier_claim, "claim_sha256", remote_claim_sha)
    remote_verifier_sha = lifecycle.canonical_sha256(remote_verifier_claim)
    _schema_gap_set_if_present(remote_receipt, "claim_sha256", remote_claim_sha)
    _schema_gap_set_if_present(
        remote_receipt,
        "verifier_start_claim_sha256",
        remote_verifier_sha,
    )
    remote_receipt_sha = lifecycle.canonical_sha256(remote_receipt)
    _schema_gap_set_if_present(remote_supervisor_receipt, "claim_sha256", remote_claim_sha)
    _schema_gap_set_if_present(
        remote_supervisor_receipt,
        "verifier_start_claim_sha256",
        remote_verifier_sha,
    )
    _schema_gap_set_if_present(
        remote_supervisor_receipt,
        "remote_receipt_sha256",
        remote_receipt_sha,
    )
    _schema_gap_set_if_present(
        arm_receipt,
        "preparation_receipt_sha256",
        preparation_sha,
    )
    _schema_gap_set_if_present(arm_receipt, "preparation_receipt_exists", True)
    _schema_gap_set_if_present(
        arm_receipt,
        "preparation_receipt_read_status",
        "readable",
    )
    _schema_gap_set_if_present(
        arm_receipt,
        "preparation_verification_receipt_sha256",
        preparation_verification_sha,
    )
    _schema_gap_set_if_present(
        arm_receipt,
        "preparation_verification_receipt_exists",
        True,
    )
    _schema_gap_set_if_present(
        arm_receipt,
        "preparation_verification_receipt_read_status",
        "readable",
    )
    _schema_gap_set_if_present(arm_receipt, "remote_claim_sha256", remote_claim_sha)
    _schema_gap_set_if_present(
        arm_receipt,
        "remote_verifier_claim_sha256",
        remote_verifier_sha,
    )
    _schema_gap_set_if_present(arm_receipt, "remote_receipt_sha256", remote_receipt_sha)
    _schema_gap_set_if_present(
        arm_receipt,
        "remote_supervisor_receipt_sha256",
        lifecycle.canonical_sha256(remote_supervisor_receipt),
    )
    arm_sha = lifecycle.canonical_sha256(arm_receipt)
    _schema_gap_set_if_present(driver_claim, "remote_claim_sha256", remote_claim_sha)
    driver_sha = lifecycle.canonical_sha256(driver_claim)

    prior_validation_sha: str | None = None
    for label in ("A", "B"):
        process = machine[f"process_{label.casefold()}"]
        start_claim = process["start_claim"]
        validator_claim = process["validator_claim"]
        validation_receipt = process["validation_receipt"]
        _schema_gap_set_if_present(start_claim, "arm_receipt_sha256", arm_sha)
        _schema_gap_set_if_present(
            start_claim,
            "lifecycle_driver_claim_sha256",
            driver_sha,
        )
        _schema_gap_set_if_present(
            start_claim,
            "prior_validation_receipt_sha256",
            prior_validation_sha,
        )
        start_sha = lifecycle.canonical_sha256(start_claim)
        _schema_gap_set_if_present(process, "start_claim_sha256", start_sha)
        _schema_gap_set_if_present(
            validator_claim,
            "lifecycle_driver_claim_sha256",
            driver_sha,
        )
        _schema_gap_set_if_present(validator_claim, "start_claim_sha256", start_sha)
        _schema_gap_set_if_present(
            validator_claim,
            "payload_sha256",
            process.get("payload_sha256"),
        )
        validator_sha = lifecycle.canonical_sha256(validator_claim)
        _schema_gap_set_if_present(process, "validator_claim_sha256", validator_sha)
        _schema_gap_set_if_present(validation_receipt, "start_claim_sha256", start_sha)
        _schema_gap_set_if_present(
            validation_receipt,
            "validator_claim_sha256",
            validator_sha,
        )
        _schema_gap_set_if_present(
            validation_receipt,
            "payload_sha256",
            process.get("payload_sha256"),
        )
        _schema_gap_set_if_present(
            validation_receipt,
            "payload_size_bytes",
            process.get("payload_size_bytes"),
        )
        validation_sha = lifecycle.canonical_sha256(validation_receipt)
        _schema_gap_set_if_present(
            process,
            "validation_receipt_sha256",
            validation_sha,
        )
        prior_validation_sha = validation_sha

        ledger_process = ledger[f"process_{label.casefold()}"]
        for ledger_key, process_key in (
            ("runner_exit_code", "exit_code"),
            ("validator_exit_code", "validator_exit_code"),
            ("start_claim_sha256", "start_claim_sha256"),
            ("validator_claim_sha256", "validator_claim_sha256"),
            ("validation_receipt_sha256", "validation_receipt_sha256"),
            ("output_sha256", "payload_sha256"),
        ):
            _schema_gap_set_if_present(
                ledger_process,
                ledger_key,
                process.get(process_key),
            )
    _schema_gap_set_if_present(ledger, "driver_claim_sha256", driver_sha)
    _schema_gap_set_if_present(ledger, "arm_receipt_sha256", arm_sha)


def _schema_gap_scientific_bundle(
    registration: dict[str, Any],
    *,
    commit: str,
    machine: dict[str, Any],
    payload_raw: bytes,
) -> tuple[dict[str, Any], bytes]:
    bundle, _ = _publisher_normal_machine_bundle(
        registration,
        commit=commit,
        disposition="scientific_result",
        stage=None,
        machine=machine,
    )
    payload_path = "artifacts/action_qbc_v8_open_diagnostic.json"
    files = [
        lifecycle._file_object(payload_path, payload_raw)
        if item["path"] == payload_path
        else item
        for item in bundle["files"]
    ]
    bundle["files"] = sorted(
        files, key=lambda item: str(item["path"]).encode("utf-8")
    )
    unsigned = dict(bundle)
    del unsigned["content_sha256"]
    bundle["content_sha256"] = lifecycle.canonical_sha256(unsigned)
    return bundle, lifecycle.canonical_json_bytes(bundle)


def _schema_gap_validate_successful_bundle(
    registration: dict[str, Any],
    *,
    commit: str,
    registration_file_sha256: str,
    bundle: dict[str, Any],
    raw: bytes,
) -> None:
    value, files = lifecycle._validate_bundle_bytes(
        raw,
        commit=commit,
        registration_sha=registration["content_sha256"],
        registration=registration,
        emergency=False,
    )
    lifecycle._validate_selected_document(
        registration,
        commit=commit,
        bundle=value,
        files=files,
        emergency=False,
    )
    finalizer._validate_final_bundle(
        bundle,
        registration=registration,
        registration_file_sha256=registration_file_sha256,
        commit=commit,
    )


def _schema_gap_reject_successful_bundle(
    registration: dict[str, Any],
    *,
    commit: str,
    registration_file_sha256: str,
    bundle: dict[str, Any],
    raw: bytes,
) -> None:
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_bundle_bytes(
            raw,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
            emergency=False,
        )
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_final_bundle(
            bundle,
            registration=registration,
            registration_file_sha256=registration_file_sha256,
            commit=commit,
        )


def test_schema_gap_success_receipt_fixture_passes_both_real_bundle_validators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    assert set(machine) == set(lifecycle._RECEIPT_KEYS)
    assert set(machine["process_a"]) == set(lifecycle._PROCESS_KEYS)
    assert set(machine["process_b"]) == set(lifecycle._PROCESS_KEYS)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_validate_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "preparation_status",
        "remote_status",
        "supervisor_status",
        "arm_status",
        "remote_attempt",
        "remote_policy",
        "remote_tool",
        "preparation_clone",
    ],
)
def test_rehashed_success_bundle_rejects_deep_evidence_mutations_in_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    if mutation == "preparation_status":
        machine["preparation_receipt"]["status"] = "failed"
    elif mutation == "remote_status":
        machine["remote_verification_receipt"]["status"] = "failed"
    elif mutation == "supervisor_status":
        machine["remote_supervisor_receipt"]["status"] = "failed"
    elif mutation == "arm_status":
        machine["arm_receipt"]["status"] = "failed"
    elif mutation == "remote_attempt":
        attempt = machine["remote_verification_receipt"]["attempts"][0]
        attempt["classification"] = "unexpected_exit"
        attempt["exit_code"] = 7
        attempt["stdout_size_bytes"] = 0
        attempt["stdout_sha256"] = hashlib.sha256(b"").hexdigest()
        attempt["stdout_base64"] = ""
    elif mutation == "remote_policy":
        machine["remote_verification_receipt"]["policy"]["max_attempts"] = 2
    elif mutation == "remote_tool":
        machine["remote_verification_receipt"]["python"]["version"] = "CPython 0.0.0"
    else:
        machine["preparation_receipt"]["process_a"]["python_version"] = "3.12.12"
    _schema_gap_rehash_successful_machine(machine)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_reject_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


@pytest.mark.parametrize("duration_milliseconds", [470_000, 470_001])
def test_p8v3_supervisor_duration_is_not_capped_at_the_legacy_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    duration_milliseconds: int,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    machine["remote_supervisor_receipt"][
        "duration_milliseconds"
    ] = duration_milliseconds
    _schema_gap_rehash_successful_machine(machine)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_validate_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


def test_schema_gap_runner_claim_and_validation_key_mutations_rehash_all_enclosures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    baseline = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    schemas = {
        "start_claim": lifecycle._START_KEYS,
        "validator_claim": lifecycle._VALIDATOR_KEYS,
        "validation_receipt": lifecycle._VALIDATION_KEYS,
    }
    for label in ("A", "B"):
        process_name = f"process_{label.casefold()}"
        for member, keys in schemas.items():
            nested = baseline[process_name][member]
            assert set(nested) == set(keys)
            for mutation, candidate in _schema_gap_mutations(nested):
                machine = copy.deepcopy(baseline)
                machine[process_name][member] = candidate
                _schema_gap_rehash_successful_machine(machine)
                bundle, raw = _schema_gap_scientific_bundle(
                    registration,
                    commit=commit,
                    machine=machine,
                    payload_raw=payload_raw,
                )
                unsigned = dict(bundle)
                claimed = unsigned.pop("content_sha256")
                assert claimed == lifecycle.canonical_sha256(unsigned), (
                    label,
                    member,
                    mutation,
                )
                _schema_gap_reject_successful_bundle(
                    registration,
                    commit=commit,
                    registration_file_sha256=registration_file_sha,
                    bundle=bundle,
                    raw=raw,
                )


def test_schema_gap_process_key_mutations_rehash_bundle_and_fail_both_validators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    baseline = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    for label in ("A", "B"):
        process_name = f"process_{label.casefold()}"
        for mutation, candidate in _schema_gap_mutations(baseline[process_name]):
            machine = copy.deepcopy(baseline)
            machine[process_name] = candidate
            bundle, raw = _schema_gap_scientific_bundle(
                registration,
                commit=commit,
                machine=machine,
                payload_raw=payload_raw,
            )
            unsigned = dict(bundle)
            claimed = unsigned.pop("content_sha256")
            assert claimed == lifecycle.canonical_sha256(unsigned), (label, mutation)
            _schema_gap_reject_successful_bundle(
                registration,
                commit=commit,
                registration_file_sha256=registration_file_sha,
                bundle=bundle,
                raw=raw,
            )


def test_schema_gap_final_receipt_key_mutations_rehash_bundle_and_fail_both_validators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    baseline = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    for mutation, machine in _schema_gap_mutations(baseline):
        bundle, raw = _schema_gap_scientific_bundle(
            registration,
            commit=commit,
            machine=machine,
            payload_raw=payload_raw,
        )
        unsigned = dict(bundle)
        claimed = unsigned.pop("content_sha256")
        assert claimed == lifecycle.canonical_sha256(unsigned), mutation
        _schema_gap_reject_successful_bundle(
            registration,
            commit=commit,
            registration_file_sha256=registration_file_sha,
            bundle=bundle,
            raw=raw,
        )


def test_schema_gap_terminal_key_mutations_rehash_bundle_and_fail_both_validators(
    tmp_path: Path,
) -> None:
    registration = _schema_gap_full_registration()
    commit = "d" * 40
    terminal = _publisher_minimal_administrative_result(
        commit=commit,
        registration_sha=registration["content_sha256"],
        stage="lifecycle_ledger_invalid",
    )
    baseline_bundle, baseline_raw = _publisher_normal_machine_bundle(
        registration,
        commit=commit,
        disposition="administrative_terminal",
        stage="lifecycle_ledger_invalid",
        machine=terminal,
    )
    registration_file_sha = hashlib.sha256(
        finalizer._canonical(registration)
    ).hexdigest()
    _schema_gap_validate_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=baseline_bundle,
        raw=baseline_raw,
    )
    for mutation, machine in _schema_gap_mutations(terminal):
        bundle, raw = _publisher_normal_machine_bundle(
            registration,
            commit=commit,
            disposition="administrative_terminal",
            stage="lifecycle_ledger_invalid",
            machine=machine,
        )
        unsigned = dict(bundle)
        claimed = unsigned.pop("content_sha256")
        assert claimed == lifecycle.canonical_sha256(unsigned), mutation
        _schema_gap_reject_successful_bundle(
            registration,
            commit=commit,
            registration_file_sha256=registration_file_sha,
            bundle=bundle,
            raw=raw,
        )


def test_schema_gap_registration_key_mutations_recompute_content_hash_and_fail_loaders(
    tmp_path: Path,
) -> None:
    import arc3_voi.action_qbc_v8_audit as v8_audit
    import scripts.reconstruct_action_qbc_v8_open_registration as reconstruction

    baseline = _schema_gap_full_registration()
    path = tmp_path / reconstruction.REGISTRATION_PATH
    path.parent.mkdir()
    path.write_bytes(reconstruction.canonical_json_bytes(baseline))
    assert v8_audit.load_registration(tmp_path, reconstruction.REGISTRATION_PATH) == baseline
    supplied, raw, content, file_sha = reconstruction._canonical_registration_file(
        tmp_path, reconstruction.REGISTRATION_PATH
    )
    assert supplied == baseline
    assert raw == reconstruction.canonical_json_bytes(baseline)
    assert content == baseline["content_sha256"]
    assert file_sha == hashlib.sha256(raw).hexdigest()

    for _mutation, candidate in _schema_gap_mutations(baseline):
        if "content_sha256" in candidate:
            preimage = dict(candidate)
            del preimage["content_sha256"]
            candidate["content_sha256"] = reconstruction.canonical_sha256(preimage)
        path.write_bytes(reconstruction.canonical_json_bytes(candidate))
        with pytest.raises(v8_audit.V7AuditError):
            v8_audit.load_registration(tmp_path, reconstruction.REGISTRATION_PATH)
        with pytest.raises(reconstruction.ReconstructionError):
            reconstruction._canonical_registration_file(
                tmp_path, reconstruction.REGISTRATION_PATH
            )


def _schema_gap_preparation_receipt(
    execution_root: Path,
    authority_root: Path,
    *,
    commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import copy

    processes_root = execution_root / "processes"
    roots = {
        "authority": authority_root,
        "process_a": processes_root / "process-a",
        "process_b": processes_root / "process-b",
    }
    processes_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    processes_root.chmod(0o700)
    for root in roots.values():
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        root.chmod(0o700)

    registration = copy.deepcopy(_schema_gap_full_registration())
    execution = registration["execution_contract"]
    execution.update(
        {
            "execution_root": str(execution_root),
            "authority_root": str(authority_root),
            "process_a_root": str(roots["process_a"]),
            "process_b_root": str(roots["process_b"]),
        }
    )
    preimage = dict(registration)
    del preimage["content_sha256"]
    registration["content_sha256"] = lifecycle.canonical_sha256(preimage)

    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=b"synthetic preparation payload",
    )
    receipt = machine["preparation_receipt"]
    for name, root in roots.items():
        metadata = root.stat(follow_symlinks=False)
        clone = receipt[name]
        clone["root_device"] = metadata.st_dev
        clone["root_inode"] = metadata.st_ino
        clone["root_owner_uid"] = metadata.st_uid
        clone["root_mode"] = metadata.st_mode & 0o777
    promoted = processes_root.stat(follow_symlinks=False)
    receipt["attempts"][0]["promotion"].update(
        {
            "source_device": promoted.st_dev,
            "source_inode": promoted.st_ino,
        }
    )
    return registration, receipt


@pytest.mark.skipif(os.name != "posix", reason="Linux preparation mode contract")
def test_schema_gap_preparation_attempt_clone_cleanup_and_promotion_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    execution_root = tmp_path / "execution"
    authority_root = tmp_path / "authority"
    monkeypatch.setattr(finalizer, "_EXECUTION_ROOT", execution_root)
    monkeypatch.setattr(finalizer, "_AUTHORITY_ROOT", authority_root)
    commit = "d" * 40
    registration, baseline = _schema_gap_preparation_receipt(
        execution_root,
        authority_root,
        commit=commit,
    )
    registration_sha = registration["content_sha256"]
    execution = registration["execution_contract"]

    def artifact(value: dict[str, Any]) -> finalizer._Artifact:
        raw = finalizer._canonical(value)
        return finalizer._Artifact(
            True,
            "readable",
            raw,
            hashlib.sha256(raw).hexdigest(),
            value,
        )

    def preparation_valid(value: dict[str, Any]) -> bool:
        return finalizer._preparation_valid(
            artifact(value),
            commit=commit,
            registration_sha=registration_sha,
            verify_filesystem=False,
            execution=execution,
            registration=registration,
        )

    assert set(baseline) == set(finalizer._PREPARATION_KEYS)
    assert preparation_valid(baseline)
    preparation._validate_preparation_attempts(
        baseline["attempts"], execution_root
    )

    for clone_name in ("authority", "process_a", "process_b"):
        for _mutation, candidate in _schema_gap_mutations(baseline[clone_name]):
            receipt = copy.deepcopy(baseline)
            receipt[clone_name] = candidate
            assert not preparation_valid(receipt)

    attempt = baseline["attempts"][0]
    for _mutation, candidate in _schema_gap_mutations(attempt):
        receipt = copy.deepcopy(baseline)
        receipt["attempts"] = [candidate]
        assert not preparation_valid(receipt)
        with pytest.raises(preparation.ProtocolError):
            preparation._validate_preparation_attempts([candidate], execution_root)

    for member in ("cleanup", "promotion"):
        nested = attempt[member]
        for _mutation, candidate in _schema_gap_mutations(nested):
            receipt = copy.deepcopy(baseline)
            receipt["attempts"][0][member] = candidate
            assert not preparation_valid(receipt)
            with pytest.raises(preparation.ProtocolError):
                preparation._validate_preparation_attempts(
                    receipt["attempts"], execution_root
                )


def _schema_gap_verified_remote_attempt(expected_stdout: bytes) -> dict[str, Any]:
    import base64

    return {
        "attempt_index": 1,
        "exit_code": 0,
        "classification": "verified",
        "timed_out": False,
        "duration_milliseconds": 0,
        "stdout_size_bytes": len(expected_stdout),
        "stdout_sha256": hashlib.sha256(expected_stdout).hexdigest(),
        "stdout_base64": base64.b64encode(expected_stdout).decode("ascii"),
        "stderr_size_bytes": 0,
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_base64": "",
        "child_cleanup_passes": None,
    }


def test_schema_gap_remote_attempt_key_mutations_fail_both_real_validators() -> None:
    expected_stdout = (
        b"dddddddddddddddddddddddddddddddddddddddd"
        + f"\trefs/tags/{lifecycle._OPEN_FREEZE_TAG}\n".encode("ascii")
    )
    baseline = _schema_gap_verified_remote_attempt(expected_stdout)
    assert set(baseline) == set(finalizer._REMOTE_ATTEMPT_KEYS)
    assert set(baseline) == set(supervisor._ATTEMPT_KEYS)
    assert finalizer._validate_remote_attempt(
        baseline,
        index=1,
        expected_stdout=expected_stdout,
    ) == ("verified", 0)
    assert supervisor._validate_attempt(baseline, 1, expected_stdout) == ("verified", 0)

    for _mutation, candidate in _schema_gap_mutations(baseline):
        with pytest.raises(finalizer._FinalizationError):
            finalizer._validate_remote_attempt(
                candidate,
                index=1,
                expected_stdout=expected_stdout,
            )
        with pytest.raises(supervisor._ProtocolFailure):
            supervisor._validate_attempt(candidate, 1, expected_stdout)


def test_schema_gap_preparation_remote_arm_and_driver_mutations_rehash_chain_and_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    baseline = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    schemas = {
        "preparation_receipt": lifecycle._PREPARATION_KEYS,
        "preparation_verification_receipt": (
            lifecycle._PREPARATION_VERIFICATION_KEYS
        ),
        "remote_verification_claim": lifecycle._REMOTE_CLAIM_KEYS,
        "remote_verifier_claim": lifecycle._REMOTE_VERIFIER_KEYS,
        "remote_verification_receipt": lifecycle._REMOTE_RECEIPT_KEYS,
        "remote_supervisor_receipt": lifecycle._REMOTE_SUPERVISOR_KEYS,
        "arm_receipt": lifecycle._ARM_KEYS,
        "lifecycle_driver_claim": lifecycle._DRIVER_KEYS,
    }
    for member, keys in schemas.items():
        assert set(baseline[member]) == set(keys)
        for mutation, candidate in _schema_gap_mutations(baseline[member]):
            machine = copy.deepcopy(baseline)
            machine[member] = candidate
            _schema_gap_rehash_successful_machine(
                machine,
                rehash_preparation_verification_content=(
                    member != "preparation_verification_receipt"
                ),
            )
            bundle, raw = _schema_gap_scientific_bundle(
                registration,
                commit=commit,
                machine=machine,
                payload_raw=payload_raw,
            )
            unsigned = dict(bundle)
            claimed = unsigned.pop("content_sha256")
            assert claimed == lifecycle.canonical_sha256(unsigned), (member, mutation)
            _schema_gap_reject_successful_bundle(
                registration,
                commit=commit,
                registration_file_sha256=registration_file_sha,
                bundle=bundle,
                raw=raw,
            )


_DESCRIPTOR_BOUND_READERS = [
    pytest.param(
        runner,
        "_plain_file_bytes",
        runner._AdministrativeFailure,
        id="runner",
    ),
    pytest.param(
        validator,
        "_plain",
        validator._AdministrativeFailure,
        id="validator",
    ),
    pytest.param(
        lifecycle,
        "_plain_bytes",
        lifecycle.LifecycleError,
        id="lifecycle",
    ),
    pytest.param(
        finalizer,
        "_plain",
        finalizer._FinalizationError,
        id="finalizer",
        marks=pytest.mark.skipif(
            os.name == "nt", reason="finalizer reader uses Linux dirfd traversal"
        ),
    ),
    pytest.param(
        supervisor,
        "_read_plain_file",
        supervisor._ProtocolFailure,
        id="supervisor",
    ),
    pytest.param(
        remote_verifier,
        "_read_plain_file",
        remote_verifier._ProtocolFailure,
        id="remote-verifier",
    ),
]


def _descriptor_bound_read(
    module: Any,
    reader_name: str,
    path: Path,
    *,
    maximum: int,
) -> bytes:
    reader = getattr(module, reader_name)
    return reader(path, "descriptor-bound fixture", maximum=maximum)


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_normal_path_uses_open_descriptor_and_preserves_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    del error_type
    path = tmp_path / "evidence.bin"
    raw = b"descriptor-bound-normal-path\x00\xff"
    path.write_bytes(raw)

    def forbidden_path_read(_self: Path) -> bytes:
        raise AssertionError("path-level read_bytes must not be used")

    monkeypatch.setattr(Path, "read_bytes", forbidden_path_read)
    assert _descriptor_bound_read(module, reader_name, path, maximum=len(raw)) == raw
    if module in (supervisor, remote_verifier):
        assert module._sha256_file(path, "descriptor-bound hash") == hashlib.sha256(
            raw
        ).hexdigest()


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_rejects_symlink_or_windows_reparse_file(
    tmp_path: Path,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable on this host: {exc}")
    with pytest.raises(error_type):
        _descriptor_bound_read(module, reader_name, link, maximum=64)


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_rejects_swap_between_path_metadata_and_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    path = tmp_path / "evidence.bin"
    replacement = tmp_path / "replacement.bin"
    path.write_bytes(b"original")
    replacement.write_bytes(b"replacement")
    real_open = module.os.open
    swapped = False

    def swapping_open(candidate: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal swapped
        candidate_path = Path(candidate)
        descriptor_relative = (
            module is finalizer
            and candidate_path == Path(path.name)
            and kwargs.get("dir_fd") is not None
        )
        if not swapped and (candidate_path == path or descriptor_relative):
            swapped = True
            module.os.replace(replacement, path)
        return real_open(candidate, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", swapping_open)
    with pytest.raises(error_type):
        _descriptor_bound_read(module, reader_name, path, maximum=64)
    assert swapped


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_rejects_mid_read_size_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"original")
    real_read = module.os.read
    changed = False

    def growing_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, size)
        if not changed:
            changed = True
            with path.open("ab") as stream:
                stream.write(b"+")
                stream.flush()
        return chunk

    monkeypatch.setattr(module.os, "read", growing_read)
    with pytest.raises(error_type):
        _descriptor_bound_read(module, reader_name, path, maximum=64)
    assert changed


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_rejects_same_size_in_place_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"original")
    before = path.stat(follow_symlinks=False)
    real_read = module.os.read
    changed = False

    def mutating_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, size)
        if not changed:
            changed = True
            with path.open("r+b") as stream:
                stream.write(b"X")
                stream.flush()
                module.os.fsync(stream.fileno())
            module.os.utime(
                path,
                # Restore the visible write clock: POSIX ctime or Windows stable-byte
                # replay must still expose the same-size in-place mutation.
                ns=(before.st_atime_ns, before.st_mtime_ns),
            )
        return chunk

    monkeypatch.setattr(module.os, "read", mutating_read)
    with pytest.raises(error_type):
        _descriptor_bound_read(module, reader_name, path, maximum=64)
    assert changed
    assert path.stat(follow_symlinks=False).st_size == before.st_size


@pytest.mark.parametrize(("module", "reader_name", "error_type"), _DESCRIPTOR_BOUND_READERS)
def test_descriptor_bound_rejects_non_regular_directory(
    tmp_path: Path,
    module: Any,
    reader_name: str,
    error_type: type[Exception],
) -> None:
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(error_type):
        _descriptor_bound_read(module, reader_name, directory, maximum=64)


def test_descriptor_bound_strict_optional_reader_linearizes_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing.json"

    def forbidden_exists(_self: Path) -> bool:
        raise AssertionError("strict optional reads must not use path.exists")

    def forbidden_is_symlink(_self: Path) -> bool:
        raise AssertionError("strict optional reads must not use path.is_symlink")

    monkeypatch.setattr(Path, "exists", forbidden_exists)
    monkeypatch.setattr(Path, "is_symlink", forbidden_is_symlink)
    assert lifecycle._strict_optional_raw(missing, "optional evidence") is None


def test_descriptor_bound_strict_optional_reader_rejects_appearance_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "appearing.json"
    real_stat = Path.stat
    lookups = 0

    def appearing_stat(
        candidate: Path,
        *args: Any,
        **kwargs: Any,
    ) -> os.stat_result:
        nonlocal lookups
        if candidate == path:
            lookups += 1
            if lookups == 1:
                path.write_bytes(b"{}")
                raise FileNotFoundError(path)
        return real_stat(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", appearing_stat)
    with pytest.raises(lifecycle.LifecycleError, match="appeared"):
        lifecycle._strict_optional_raw(path, "optional evidence")
    assert lookups == 2


@pytest.mark.skipif(os.name == "nt", reason="runner cleanup uses Linux dirfd APIs")
def test_descriptor_bound_runner_cleanup_unlinks_only_exact_owned_hardlink(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging.json"
    output = tmp_path / "output.json"
    raw = b'{"owned":true}'
    staging.write_bytes(raw)
    os.link(staging, output)
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        runner._unlink_owned_output(
            descriptor,
            output.name,
            staging.name,
            hashlib.sha256(raw).hexdigest(),
        )
    finally:
        os.close(descriptor)
    assert not output.exists()
    assert staging.read_bytes() == raw


@pytest.mark.skipif(os.name == "nt", reason="runner cleanup uses Linux dirfd APIs")
def test_descriptor_bound_runner_cleanup_preserves_path_swapped_after_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "staging.json"
    output = tmp_path / "output.json"
    replacement = tmp_path / "replacement.json"
    raw = b'{"owned":true}'
    intruder = b'{"intruder":true}'
    staging.write_bytes(raw)
    os.link(staging, output)
    replacement.write_bytes(intruder)
    real_reader = runner._plain_file_bytes_at

    def swapping_reader(
        parent_descriptor: int,
        component: str,
        name: str,
        *,
        maximum: int = runner._MAX_ADMIN_BYTES,
    ) -> bytes:
        observed = real_reader(
            parent_descriptor,
            component,
            name,
            maximum=maximum,
        )
        if component == output.name:
            os.replace(replacement, output)
        return observed

    monkeypatch.setattr(runner, "_plain_file_bytes_at", swapping_reader)
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        runner._unlink_owned_output(
            descriptor,
            output.name,
            staging.name,
            hashlib.sha256(raw).hexdigest(),
        )
    finally:
        os.close(descriptor)
    assert output.read_bytes() == intruder
    assert staging.read_bytes() == raw


@pytest.mark.skipif(os.name != "posix", reason="P8v3 venv gates use Linux dirfd APIs")
def test_p8v3_runner_independently_recomputes_exact_preparation_venv_preimages(
    tmp_path: Path,
) -> None:
    root = tmp_path / "process"
    site_packages = root / ".venv/lib/python3.12/site-packages"
    (root / ".venv/bin").mkdir(parents=True)
    site_packages.mkdir(parents=True)
    versions = {
        "arc3-crosslevel-voi": "0.1.0",
        "numpy": "2.5.1",
        "pyyaml": "6.0.3",
    }
    for normalized_name, version in versions.items():
        dist_name = f"{normalized_name.replace('-', '_')}-{version}.dist-info"
        dist = site_packages / dist_name
        dist.mkdir()
        (dist / "METADATA").write_text(
            f"Name: {normalized_name}\nVersion: {version}\n\n",
            encoding="utf-8",
            newline="\n",
        )
        (dist / "RECORD").write_text(
            f"{dist_name}/METADATA,,\n{dist_name}/RECORD,,\n",
            encoding="utf-8",
            newline="\n",
        )
    (root / ".venv/bin/python3").symlink_to(Path(sys.executable).resolve())
    root.chmod(0o700)

    runner_inventory, runner_inventory_sha = runner._compact_environment_inventory(
        root
    )
    preparation_inventory, preparation_inventory_sha = preparation._environment_inventory(
        root
    )
    assert runner_inventory == preparation_inventory
    assert runner_inventory_sha == preparation_inventory_sha
    assert [row["normalized_name"] for row in runner_inventory] == sorted(versions)

    initial_runner_venv = runner._venv_materialization_sha256(root)
    assert initial_runner_venv == preparation._venv_materialization_sha256(root)
    assert runner._venv_python_sha256(root) == preparation._venv_python_sha256(root)

    marker = root / ".venv/materialization-marker"
    marker.write_bytes(b"changed")
    changed_runner_venv = runner._venv_materialization_sha256(root)
    assert changed_runner_venv == preparation._venv_materialization_sha256(root)
    assert changed_runner_venv != initial_runner_venv


@pytest.mark.skipif(os.name != "posix", reason="P8v3 preparation chain is Linux-only")
def test_p8v3_runner_rejects_coherently_rehashed_verification_clone_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_commit = "b" * 40
    registration_sha = "a" * 64
    execution_root = tmp_path / "execution"
    processes = execution_root / "processes"
    processes.mkdir(parents=True, mode=0o700)
    processes.chmod(0o700)
    authority_root = execution_root / "authority"
    authority_root.mkdir(mode=0o700)
    authority_root.chmod(0o700)
    monkeypatch.setattr(runner, "_EXECUTION_ROOT", execution_root)
    environment = runner._fixed_git_environment(Path("/"))
    policy = {
        "default_timeout_seconds": 60,
        "environment_timeout_seconds": 600,
        "term_grace_seconds": 5,
        "kill_grace_seconds": 5,
        "stdin_cap_bytes": 1_048_576,
        "stdout_cap_bytes": 134_217_728,
        "stderr_cap_bytes": 1_048_576,
    }
    preparation_path = tmp_path / "preparation.json"
    verification_path = tmp_path / "verification.json"
    monkeypatch.setattr(runner, "_PREPARATION_RECEIPT", str(preparation_path))
    monkeypatch.setattr(
        runner,
        "_PREPARATION_VERIFICATION_RECEIPT",
        str(verification_path),
    )
    verification_argv = [
        "/usr/bin/python3",
        "-I",
        "-B",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "--repository-root",
        ".",
        "--registration",
        runner._EXPECTED_REGISTRATION,
        "--verify-preparation",
        "--preparation-receipt",
        str(preparation_path),
        "--verification-receipt",
        str(verification_path),
    ]
    roots = {
        "authority": str(authority_root),
        "process_a": str(processes / "process-a"),
        "process_b": str(processes / "process-b"),
    }
    inventory = [
        {
            "normalized_name": name,
            "version": version,
            "file_count": 1,
            "files_sha256": hashlib.sha256(name.encode()).hexdigest(),
        }
        for name, version in (
            ("arc3-crosslevel-voi", "0.1.0"),
            ("numpy", "2.5.1"),
            ("pyyaml", "6.0.3"),
        )
    ]
    inventory_sha = runner._sha256(runner._canonical_json_bytes(inventory))

    def clone(key: str) -> dict[str, Any]:
        authority = key == "authority"
        return {
            "root": roots[key],
            "root_device": 1,
            "root_inode": {"authority": 2, "process_a": 3, "process_b": 4}[key],
            "root_owner_uid": 1000,
            "root_mode": 0o700,
            "head_sha": open_commit,
            "tree_sha256": "1" * 64,
            "raw_materialization_sha256": "2" * 64,
            "git_status_sha256": hashlib.sha256(b"").hexdigest(),
            "python_version": None if authority else "3.12.13",
            "uv_version": None if authority else "0.11.28",
            "environment_inventory": None if authority else inventory,
            "environment_inventory_sha256": None if authority else inventory_sha,
            "venv_materialization_sha256": None if authority else "4" * 64,
            "venv_python_sha256": None if authority else "5" * 64,
            "passes": True,
        }

    preflights = [
        [
            "/usr/bin/git",
            "--no-replace-objects",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        ["/usr/bin/git", "--no-replace-objects", "rev-parse", "HEAD"],
        [".venv/bin/python3", "--version"],
        ["/usr/local/bin/uv", "--version"],
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            "scripts/reconstruct_action_qbc_v8_open_registration.py",
            "--repository-root",
            ".",
            "--registration",
            runner._EXPECTED_REGISTRATION,
            "--verify-open-freeze",
        ],
    ]
    execution = {
        "execution_root": str(execution_root),
        "authority_root": roots["authority"],
        "process_a_root": roots["process_a"],
        "process_b_root": roots["process_b"],
        "preparation_command_environment": environment,
        "preparation_command_policy": policy,
        "environment_build_argv": [
            "/usr/bin/env",
            "UV_OFFLINE=1",
            "/usr/local/bin/uv",
            "sync",
            "--python",
            "3.12.13",
            "--frozen",
            "--no-dev",
            "--offline",
        ],
        "preflight_argvs": preflights,
        "post_preparation_validation_argv": verification_argv,
    }
    entries = [("synthetic.txt", "100644", "d" * 40, 1)]
    monkeypatch.setattr(runner, "_tree_entries", lambda *_args: entries)
    identities = [
        *runner._expected_authority_identities(authority_root, open_commit, entries),
        *runner._expected_attempt_identities(
            execution,
            execution_root,
            1,
            open_commit,
            entries,
        ),
    ]
    empty_sha = hashlib.sha256(b"").hexdigest()
    ledger = [
        {
            "sequence_index": index,
            **identity,
            "started": True,
            "exit_code": 0,
            "outcome": "completed",
            "timed_out": False,
            "duration_milliseconds": 1,
            "stdout_size_bytes": 0,
            "stdout_sha256": empty_sha,
            "stderr_size_bytes": 0,
            "stderr_sha256": empty_sha,
            "child_cleanup_passes": None,
        }
        for index, identity in enumerate(identities)
    ]
    promoted = processes.stat(follow_symlinks=False)
    source = execution_root / ".prepare-attempt-1"
    preparation_value = {
        "schema_version": runner._PREPARATION_SCHEMA,
        "treatment_id": runner._TREATMENT_ID,
        "open_freeze_commit_sha": open_commit,
        "open_freeze_tag": runner._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "attempts": [
            {
                "attempt_index": 1,
                "process_a_stage": "completed",
                "process_b_stage": "completed",
                "cleanup": {
                    "owned_paths": [str(source)],
                    "removed": [],
                    "passes": True,
                },
                "promotion": {
                    "source_path": str(source),
                    "destination_path": str(processes),
                    "source_device": promoted.st_dev,
                    "source_inode": promoted.st_ino,
                    "passes": True,
                },
                "passes": True,
            }
        ],
        "authority": clone("authority"),
        "process_a": clone("process_a"),
        "process_b": clone("process_b"),
        "command_ledger": ledger,
        "commands_sha256": runner._sha256(runner._canonical_json_bytes(ledger)),
        "command_environment_sha256": runner._sha256(
            runner._canonical_json_bytes(environment)
        ),
        "status": "prepared",
    }
    preparation_raw = runner._canonical_json_bytes(preparation_value)
    preparation_path.write_bytes(preparation_raw)
    verification_value: dict[str, Any] = {
        "schema_version": runner._PREPARATION_VERIFICATION_SCHEMA,
        "treatment_id": runner._TREATMENT_ID,
        "open_freeze_commit_sha": open_commit,
        "open_freeze_tag": runner._OPEN_FREEZE_TAG,
        "registration_content_sha256": registration_sha,
        "preparation_receipt_sha256": runner._sha256(preparation_raw),
        "verification_argv_sha256": runner._sha256(
            runner._canonical_json_bytes(verification_argv)
        ),
        "authority": {
            key: value
            for key, value in preparation_value["authority"].items()
            if key != "environment_inventory"
        },
        "process_a": {
            key: value
            for key, value in preparation_value["process_a"].items()
            if key != "environment_inventory"
        },
        "process_b": {
            key: value
            for key, value in preparation_value["process_b"].items()
            if key != "environment_inventory"
        },
        "status": "verified",
    }
    verification_value["content_sha256"] = runner._sha256(
        runner._canonical_json_bytes(verification_value)
    )
    verification_path.write_bytes(runner._canonical_json_bytes(verification_value))
    registration = {
        "content_sha256": registration_sha,
        "execution_contract": execution,
    }
    runner._validate_preparation_chain(registration, open_commit=open_commit)

    verification_value["process_a"]["root_inode"] = 99
    unsigned = dict(verification_value)
    del unsigned["content_sha256"]
    verification_value["content_sha256"] = runner._sha256(
        runner._canonical_json_bytes(unsigned)
    )
    verification_path.write_bytes(runner._canonical_json_bytes(verification_value))
    with pytest.raises(
        runner._AdministrativeFailure,
        match="differs from preparation",
    ):
        runner._validate_preparation_chain(registration, open_commit=open_commit)


@pytest.mark.skipif(os.name != "posix", reason="P8v4 local Git policy uses /usr/bin/git")
def test_p8v4_runner_and_validator_reject_unlisted_local_git_sources(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", "init", str(repository)],
        check=True,
        capture_output=True,
    )
    for key, value in (
        ("core.autocrlf", "false"),
        ("core.eol", "lf"),
        ("core.safecrlf", "true"),
    ):
        subprocess.run(
            [
                "/usr/bin/git",
                "--no-replace-objects",
                "-C",
                str(repository),
                "config",
                "--local",
                key,
                value,
            ],
            check=True,
            capture_output=True,
        )
    runner._validate_local_git_sources(repository)
    validator._validate_local_git_sources(repository)

    subprocess.run(
        [
            "/usr/bin/git",
            "--no-replace-objects",
            "-C",
            str(repository),
            "config",
            "--local",
            "core.ignorecase",
            "true",
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(runner._AdministrativeFailure, match="closed P8v4 mapping"):
        runner._validate_local_git_sources(repository)
    with pytest.raises(validator._AdministrativeFailure, match="closed P8v4 mapping"):
        validator._validate_local_git_sources(repository)


def test_descriptor_bound_supervisor_optional_read_normal_and_absent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "optional.json"
    assert supervisor._read_optional_raw(path, "optional fixture") == (None, None)
    raw = b'{"optional":true}'
    path.write_bytes(raw)
    assert supervisor._read_optional_raw(path, "optional fixture") == (
        raw,
        hashlib.sha256(raw).hexdigest(),
    )


def test_descriptor_bound_supervisor_optional_read_rejects_pre_read_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "optional.json"
    replacement = tmp_path / "replacement.json"
    path.write_bytes(b'{"original":true}')
    replacement.write_bytes(b'{"replacement":true}')
    real_reader = supervisor._read_plain_file
    swapped = False

    def swapping_reader(candidate: Path, name: str, *, maximum: int = 134_217_728) -> bytes:
        nonlocal swapped
        if not swapped and candidate == path:
            swapped = True
            os.replace(replacement, path)
        return real_reader(candidate, name, maximum=maximum)

    monkeypatch.setattr(supervisor, "_read_plain_file", swapping_reader)
    with pytest.raises(supervisor._ProtocolFailure, match="changed"):
        supervisor._read_optional_raw(path, "optional fixture")
    assert swapped


def _p8v3_duration_parity_validate_machine_with_both_consumers(
    registration: dict[str, Any],
    machine: dict[str, Any],
    *,
    commit: str,
) -> None:
    lifecycle._validate_machine_result(
        machine,
        schema=lifecycle._RECEIPT_SCHEMA,
        commit=commit,
        registration_sha=registration["content_sha256"],
        registration=registration,
    )
    finalizer._validate_machine_result(
        machine,
        schema=finalizer._RECEIPT_SCHEMA,
        commit=commit,
        registration_sha=registration["content_sha256"],
        registration=registration,
    )


def _p8v3_duration_parity_reject_machine_with_both_consumers(
    registration: dict[str, Any],
    machine: dict[str, Any],
    *,
    commit: str,
) -> None:
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_machine_result(
            machine,
            schema=lifecycle._RECEIPT_SCHEMA,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
        )
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_machine_result(
            machine,
            schema=finalizer._RECEIPT_SCHEMA,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
        )


def _p8v3_duration_parity_rebind_registration_identity(
    registration: dict[str, Any],
    machine: dict[str, Any],
) -> None:
    registration_preimage = dict(registration)
    registration_preimage.pop("content_sha256", None)
    registration_sha = lifecycle.canonical_sha256(registration_preimage)
    registration["content_sha256"] = registration_sha

    def bind(value: object) -> None:
        if isinstance(value, dict):
            if "registration_content_sha256" in value:
                value["registration_content_sha256"] = registration_sha
            for nested in value.values():
                bind(nested)
        elif isinstance(value, list):
            for nested in value:
                bind(nested)

    bind(machine)
    preparation_receipt = machine["preparation_receipt"]
    execution = registration["execution_contract"]
    commit = machine["open_freeze_commit_sha"]
    expected_identities = lifecycle._preparation_expected_authority_identities(
        registration,
        execution,
        commit=commit,
    )
    for index in range(1, len(preparation_receipt["attempts"]) + 1):
        expected_identities.extend(
            lifecycle._preparation_expected_attempt_identities(
                registration,
                execution,
                attempt_index=index,
                commit=commit,
            )
        )
    assert len(expected_identities) == len(preparation_receipt["command_ledger"])
    for row, identity in zip(
        preparation_receipt["command_ledger"],
        expected_identities,
        strict=True,
    ):
        row.update(identity)
    preparation_receipt["commands_sha256"] = lifecycle.canonical_sha256(
        preparation_receipt["command_ledger"]
    )
    _schema_gap_rehash_successful_machine(machine)


def test_p8v3_duration_parity_accepts_unclamped_remote_cleanup_overruns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    policy = registration["execution_contract"]["remote_policy"]
    actual_overrun_milliseconds = 500_001
    assert actual_overrun_milliseconds > (
        policy["attempt_timeout_seconds"]
        + policy["child_cleanup_timeout_seconds"]
    ) * 1_000
    assert actual_overrun_milliseconds > (
        policy["overall_deadline_seconds"]
        + policy["child_cleanup_timeout_seconds"]
    ) * 1_000
    assert (
        actual_overrun_milliseconds
        > policy["supervisor_deadline_seconds"] * 1_000
    )
    machine["remote_verification_receipt"]["attempts"][0][
        "duration_milliseconds"
    ] = actual_overrun_milliseconds
    machine["remote_verification_receipt"][
        "total_duration_milliseconds"
    ] = actual_overrun_milliseconds
    machine["remote_supervisor_receipt"][
        "duration_milliseconds"
    ] = actual_overrun_milliseconds
    _schema_gap_rehash_successful_machine(machine)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_validate_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


def test_p8v3_duration_parity_retains_remote_total_lower_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    machine["remote_verification_receipt"]["attempts"][0][
        "duration_milliseconds"
    ] = 500_001
    machine["remote_verification_receipt"][
        "total_duration_milliseconds"
    ] = 500_000
    _schema_gap_rehash_successful_machine(machine)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_reject_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


@pytest.mark.parametrize(
    "member",
    ["remote_total_duration", "supervisor_duration"],
)
def test_p8v3_duration_parity_retains_nonnegative_duration_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member: str,
) -> None:
    registration, _payload, payload_raw, commit, registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    if member == "remote_total_duration":
        machine["remote_verification_receipt"][
            "total_duration_milliseconds"
        ] = -1
    else:
        machine["remote_supervisor_receipt"]["duration_milliseconds"] = -1
    _schema_gap_rehash_successful_machine(machine)
    bundle, raw = _schema_gap_scientific_bundle(
        registration,
        commit=commit,
        machine=machine,
        payload_raw=payload_raw,
    )
    _schema_gap_reject_successful_bundle(
        registration,
        commit=commit,
        registration_file_sha256=registration_file_sha,
        bundle=bundle,
        raw=raw,
    )


@pytest.mark.parametrize(
    ("reserve_seconds", "accepted"),
    [(480, True), (481, False)],
)
def test_p8v3_duration_parity_retains_supervisor_reserve_relation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reserve_seconds: int,
    accepted: bool,
) -> None:
    import copy

    baseline, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    registration = copy.deepcopy(baseline)
    registration["execution_contract"]["remote_policy"][
        "supervisor_receipt_reserve_seconds"
    ] = reserve_seconds
    machine = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    machine["remote_verification_receipt"]["policy"] = dict(
        registration["execution_contract"]["remote_policy"]
    )
    _p8v3_duration_parity_rebind_registration_identity(registration, machine)
    if accepted:
        _p8v3_duration_parity_validate_machine_with_both_consumers(
            registration,
            machine,
            commit=commit,
        )
    else:
        _p8v3_duration_parity_reject_machine_with_both_consumers(
            registration,
            machine,
            commit=commit,
        )


def _p8v3_preparation_semantics_failed_receipt(
    prepared: dict[str, Any],
    *,
    attempt_count: int,
) -> dict[str, Any]:
    import copy

    assert attempt_count in {1, 2}
    receipt = copy.deepcopy(prepared)
    execution_root = str(
        receipt["attempts"][0]["promotion"]["destination_path"]
    ).removesuffix("/processes")

    authority_commands = [
        copy.deepcopy(command)
        for command in receipt["command_ledger"]
        if command["attempt_index"] is None
    ]
    first_command = copy.deepcopy(
        next(
            command
            for command in receipt["command_ledger"]
            if command["attempt_index"] == 1
        )
    )
    first_command.update(
        {
            "sequence_index": len(authority_commands),
            "attempt_index": 1,
            "exit_code": 1,
            "outcome": "nonzero",
            "timed_out": False,
            "child_cleanup_passes": None,
        }
    )
    commands = [*authority_commands, first_command]
    attempts: list[dict[str, Any]] = []
    for index in range(1, attempt_count + 1):
        source = f"{execution_root}/.prepare-attempt-{index}"
        attempts.append(
            {
                "attempt_index": index,
                "process_a_stage": "clone_failed",
                "process_b_stage": "not_started",
                "cleanup": {
                    "owned_paths": [source],
                    "removed": [source],
                    "passes": True,
                },
                "promotion": {
                    "source_path": source,
                    "destination_path": f"{execution_root}/processes",
                    "source_device": 1,
                    "source_inode": index,
                    "passes": False,
                },
                "passes": False,
            }
        )
        if index == 2:
            second_command = copy.deepcopy(first_command)
            second_command["sequence_index"] = len(commands)
            second_command["attempt_index"] = 2
            second_command["cwd"] = str(second_command["cwd"]).replace(
                ".prepare-attempt-1", ".prepare-attempt-2"
            )
            second_command["argv"] = [
                str(argument).replace(
                    ".prepare-attempt-1", ".prepare-attempt-2"
                )
                for argument in second_command["argv"]
            ]
            second_command["argv_sha256"] = lifecycle.canonical_sha256(
                second_command["argv"]
            )
            commands.append(second_command)

    receipt.update(
        {
            "attempts": attempts,
            "process_a": None,
            "process_b": None,
            "command_ledger": commands,
            "commands_sha256": lifecycle.canonical_sha256(commands),
            "status": "failed",
        }
    )
    return receipt


def _p8v3_preparation_semantics_artifact(
    value: dict[str, Any],
) -> finalizer._Artifact:
    raw = finalizer._canonical(value)
    return finalizer._Artifact(
        exists=True,
        read_status="readable",
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        value=value,
    )


def _p8v3_preparation_semantics_validate_receipt_with_both_consumers(
    registration: dict[str, Any],
    receipt: dict[str, Any],
    *,
    commit: str,
) -> None:
    execution = registration["execution_contract"]
    assert (
        lifecycle._validate_embedded_preparation_receipt(
            receipt,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
            execution=execution,
        )
        == receipt["status"]
    )
    assert finalizer._preparation_semantically_valid(
        _p8v3_preparation_semantics_artifact(receipt),
        commit=commit,
        registration_sha=registration["content_sha256"],
        verify_filesystem=False,
        execution=execution,
        registration=registration,
    )


def _p8v3_preparation_semantics_reject_receipt_with_both_consumers(
    registration: dict[str, Any],
    receipt: dict[str, Any],
    *,
    commit: str,
) -> None:
    execution = registration["execution_contract"]
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_embedded_preparation_receipt(
            receipt,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
            execution=execution,
        )
    assert not finalizer._preparation_semantically_valid(
        _p8v3_preparation_semantics_artifact(receipt),
        commit=commit,
        registration_sha=registration["content_sha256"],
        verify_filesystem=False,
        execution=execution,
        registration=registration,
    )


def _p8v3_preparation_semantics_admin_machine(
    successful: dict[str, Any],
    *,
    commit: str,
    registration_sha: str,
    preparation_receipt: dict[str, Any] | None,
    preparation_verification_receipt: dict[str, Any] | None,
    stage: str,
) -> dict[str, Any]:
    machine = _publisher_minimal_administrative_result(
        commit=commit,
        registration_sha=registration_sha,
        stage=stage,
    )
    for prefix, receipt in (
        ("preparation_receipt", preparation_receipt),
        (
            "preparation_verification_receipt",
            preparation_verification_receipt,
        ),
    ):
        machine[prefix] = receipt
        machine[f"{prefix}_exists"] = receipt is not None
        machine[f"{prefix}_read_status"] = (
            "readable" if receipt is not None else "absent"
        )
        machine[f"{prefix}_sha256"] = (
            lifecycle.canonical_sha256(receipt) if receipt is not None else None
        )
    machine["remote_verification_claim"] = successful[
        "remote_verification_claim"
    ]
    machine["lifecycle_driver_claim"] = successful["lifecycle_driver_claim"]
    return machine


def _p8v3_preparation_semantics_validate_admin_with_both_consumers(
    registration: dict[str, Any],
    machine: dict[str, Any],
    *,
    commit: str,
) -> None:
    for consumer in (lifecycle, finalizer):
        consumer._validate_machine_result(
            machine,
            schema=consumer._ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
        )


def _p8v3_preparation_semantics_reject_admin_with_both_consumers(
    registration: dict[str, Any],
    machine: dict[str, Any],
    *,
    commit: str,
) -> None:
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_machine_result(
            machine,
            schema=lifecycle._ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
        )
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_machine_result(
            machine,
            schema=finalizer._ADMIN_SCHEMA,
            commit=commit,
            registration_sha=registration["content_sha256"],
            registration=registration,
        )


@pytest.mark.parametrize("attempt_count", [1, 2])
def test_p8v3_preparation_semantics_accepts_canonical_failed_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attempt_count: int,
) -> None:
    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    failed = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=attempt_count
    )
    _p8v3_preparation_semantics_validate_receipt_with_both_consumers(
        registration,
        failed,
        commit=commit,
    )
    machine = _p8v3_preparation_semantics_admin_machine(
        successful,
        commit=commit,
        registration_sha=registration["content_sha256"],
        preparation_receipt=failed,
        preparation_verification_receipt=None,
        stage="preparation_receipt_invalid",
    )
    _p8v3_preparation_semantics_validate_admin_with_both_consumers(
        registration,
        machine,
        commit=commit,
    )


def test_p8v3_preparation_semantics_accepts_cleanup_after_nonzero_child_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    failed = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=1
    )
    failed["command_ledger"][-1]["child_cleanup_passes"] = True
    failed["commands_sha256"] = lifecycle.canonical_sha256(
        failed["command_ledger"]
    )
    _p8v3_preparation_semantics_validate_receipt_with_both_consumers(
        registration,
        failed,
        commit=commit,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "attempts_not_array",
        "authority_environment_nonnull",
        "promoted_process_present",
        "attempt_passes",
        "failed_attempt_cleanup_false",
        "promotion_passes",
        "attempt_index_bool",
        "ledger_plan_label",
        "ledger_after_terminal",
        "stdin_identity",
        "invented_argv",
        "ledger_hash",
    ],
)
def test_p8v3_preparation_semantics_rejects_failed_receipt_mutations_in_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    receipt = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=1
    )
    if mutation == "attempts_not_array":
        receipt["attempts"] = "invalid"
    elif mutation == "authority_environment_nonnull":
        receipt["authority"]["python_version"] = "3.12.13"
    elif mutation == "promoted_process_present":
        receipt["process_a"] = copy.deepcopy(
            successful["preparation_receipt"]["process_a"]
        )
    elif mutation == "attempt_passes":
        receipt["attempts"][0]["passes"] = True
    elif mutation == "failed_attempt_cleanup_false":
        receipt["attempts"][0]["cleanup"].update(
            {
                "passes": False,
                "removed": [],
            }
        )
    elif mutation == "promotion_passes":
        receipt["attempts"][0]["promotion"]["passes"] = True
    elif mutation == "attempt_index_bool":
        receipt["attempts"][0]["attempt_index"] = True
    elif mutation == "ledger_plan_label":
        receipt["command_ledger"][-1]["label"] = "B"
        receipt["commands_sha256"] = lifecycle.canonical_sha256(
            receipt["command_ledger"]
        )
    elif mutation == "ledger_after_terminal":
        extra = copy.deepcopy(receipt["command_ledger"][-1])
        extra["sequence_index"] = len(receipt["command_ledger"])
        receipt["command_ledger"].append(extra)
        receipt["commands_sha256"] = lifecycle.canonical_sha256(
            receipt["command_ledger"]
        )
    elif mutation == "stdin_identity":
        receipt["command_ledger"][-1]["stdin_size_bytes"] = 1
        receipt["command_ledger"][-1]["stdin_sha256"] = hashlib.sha256(
            b"x"
        ).hexdigest()
        receipt["commands_sha256"] = lifecycle.canonical_sha256(
            receipt["command_ledger"]
        )
    elif mutation == "invented_argv":
        receipt["command_ledger"][-1]["argv"][-2] = (
            "file:///invented-preparation-source"
        )
        receipt["command_ledger"][-1]["argv_sha256"] = (
            lifecycle.canonical_sha256(receipt["command_ledger"][-1]["argv"])
        )
        receipt["commands_sha256"] = lifecycle.canonical_sha256(
            receipt["command_ledger"]
        )
    else:
        receipt["commands_sha256"] = "0" * 64
    _p8v3_preparation_semantics_reject_receipt_with_both_consumers(
        registration,
        receipt,
        commit=commit,
    )


@pytest.mark.parametrize(
    "stage",
    [
        stage
        for stage in lifecycle._UNDERLYING_ORDER
        if stage != "preparation_receipt_invalid"
    ],
)
def test_p8v3_preparation_semantics_failed_receipt_forces_first_stage_in_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    failed = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=1
    )
    machine = _p8v3_preparation_semantics_admin_machine(
        successful,
        commit=commit,
        registration_sha=registration["content_sha256"],
        preparation_receipt=failed,
        preparation_verification_receipt=None,
        stage=stage,
    )
    _p8v3_preparation_semantics_reject_admin_with_both_consumers(
        registration,
        machine,
        commit=commit,
    )


def test_p8v3_preparation_semantics_admin_validates_embedded_verification_in_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    machine = _p8v3_preparation_semantics_admin_machine(
        successful,
        commit=commit,
        registration_sha=registration["content_sha256"],
        preparation_receipt=copy.deepcopy(successful["preparation_receipt"]),
        preparation_verification_receipt=copy.deepcopy(
            successful["preparation_verification_receipt"]
        ),
        stage="process_a_nonzero",
    )
    _p8v3_preparation_semantics_validate_admin_with_both_consumers(
        registration,
        machine,
        commit=commit,
    )

    verification = machine["preparation_verification_receipt"]
    verification["authority"]["root"] = "/invented-authority"
    verification_preimage = dict(verification)
    verification_preimage.pop("content_sha256")
    verification["content_sha256"] = lifecycle.canonical_sha256(
        verification_preimage
    )
    machine["preparation_verification_receipt_sha256"] = (
        lifecycle.canonical_sha256(verification)
    )
    _p8v3_preparation_semantics_reject_admin_with_both_consumers(
        registration,
        machine,
        commit=commit,
    )


def test_p8v3_preparation_semantics_admin_retains_invalid_readable_raw_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    invalid_receipt = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=1
    )
    invalid_receipt["attempts"] = "invalid"
    invalid_raw = lifecycle.canonical_json_bytes(invalid_receipt)
    machine = _p8v3_preparation_semantics_admin_machine(
        successful,
        commit=commit,
        registration_sha=registration["content_sha256"],
        preparation_receipt=None,
        preparation_verification_receipt=None,
        stage="preparation_receipt_invalid",
    )
    machine["preparation_receipt_exists"] = True
    machine["preparation_receipt_read_status"] = "readable"
    machine["preparation_receipt_sha256"] = hashlib.sha256(invalid_raw).hexdigest()
    _p8v3_preparation_semantics_validate_admin_with_both_consumers(
        registration,
        machine,
        commit=commit,
    )


def test_p8v3_preparation_semantics_embeds_only_pure_valid_receipt_value() -> None:
    invalid_value = {
        key: None for key in finalizer._PREPARATION_KEYS
    }
    invalid_value.update(
        {
            "schema_version": "action-qbc-v8-preparation-receipt-v2",
            "treatment_id": finalizer._TREATMENT_ID,
            "open_freeze_commit_sha": "d" * 40,
            "open_freeze_tag": finalizer._OPEN_FREEZE_TAG,
            "registration_content_sha256": "e" * 64,
            "status": "failed",
        }
    )
    raw = finalizer._canonical(invalid_value)
    invalid = finalizer._Artifact(
        exists=True,
        read_status="readable",
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        value=invalid_value,
    )
    absent = finalizer._Artifact(False, "absent", None, None, None)
    empty_a = finalizer._Process(_publisher_empty_result_process("A"), None)
    empty_b = finalizer._Process(_publisher_empty_result_process("B"), None)
    embedded = finalizer._embedded_base(
        commit="d" * 40,
        registration={"content_sha256": "e" * 64},
        preparation=invalid,
        preparation_verification=absent,
        remote_claim=absent,
        remote_verifier=absent,
        remote_receipt=absent,
        remote_supervisor=absent,
        arm=absent,
        driver=absent,
        ledger=absent,
        process_a=empty_a,
        process_b=empty_b,
        preparation_valid=False,
    )
    assert embedded["preparation_receipt"] is None
    assert embedded["preparation_receipt_exists"] is True
    assert embedded["preparation_receipt_read_status"] == "readable"
    assert embedded["preparation_receipt_sha256"] == hashlib.sha256(raw).hexdigest()


def _p8v3_runner_dirfd_renderer_row() -> dict[str, Any]:
    return {
        "mode": "100644",
        "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "git_blob_sha1": "a" * 40,
        "sha256": "b" * 64,
        "byte_count": 1,
    }


def test_p8v3_runner_dirfd_exact_execution_rejects_rehashed_remote_argv() -> None:
    import copy

    additions = [_p8v3_runner_dirfd_renderer_row()]
    execution = reconstruction._execution_contract(additions)
    registration = {
        "source_manifest": {"open_freeze_added_files": additions},
        "execution_contract": execution,
    }
    runner._validate_execution_contract(registration)
    runner._validate_reconstructed_execution(ROOT, registration)

    mutated = copy.deepcopy(registration)
    mutated_execution = mutated["execution_contract"]
    mutated_execution["remote_verifier_argv"].append("--invented")
    mutated_execution["argv_hashes"]["remote_verifier"] = runner._sha256(
        runner._canonical_json_bytes(mutated_execution["remote_verifier_argv"])
    )
    runner._validate_execution_contract(mutated)
    with pytest.raises(
        runner._AdministrativeFailure,
        match="differs from exact reconstruction",
    ):
        runner._validate_reconstructed_execution(ROOT, mutated)


def test_p8v6_runner_validates_real_registration_manifest_shape() -> None:
    import json

    registration_path = ROOT / runner._EXPECTED_REGISTRATION
    if registration_path.is_file():
        registration_raw = registration_path.read_bytes()
    else:
        git = remote_verifier._GIT_PATH if os.name == "nt" else "/usr/bin/git"
        environment = dict(os.environ)
        environment.update(
            {
                "GIT_CONFIG_COUNT": "0",
                "GIT_CONFIG_GLOBAL": "NUL" if os.name == "nt" else "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        completed = subprocess.run(
            [
                git,
                "--no-replace-objects",
                "--no-optional-locks",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                "-C",
                str(ROOT),
                "cat-file",
                "blob",
                f"{runner._O8V2_COMMIT}:{runner._EXPECTED_REGISTRATION}",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stderr == b""
        registration_raw = completed.stdout
    generated = json.loads(registration_raw)
    source_manifest = generated["source_manifest"]
    assert set(source_manifest) == {
        "manifest_sha256",
        "open_freeze_added_files",
        "preregistration_tree",
    }
    additions = source_manifest["open_freeze_added_files"]
    registration = {
        "source_manifest": source_manifest,
        "execution_contract": reconstruction._execution_contract(additions),
    }
    runner._validate_reconstructed_execution(ROOT, registration)


def test_p8v6_runner_rejects_legacy_source_manifest_key() -> None:
    additions = [_p8v3_runner_dirfd_renderer_row()]
    registration = {
        "source_manifest": {"added_in_open_freeze": additions},
        "execution_contract": reconstruction._execution_contract(additions),
    }
    with pytest.raises(
        runner._AdministrativeFailure,
        match="registration open-freeze additions are invalid",
    ):
        runner._validate_reconstructed_execution(ROOT, registration)


def test_p8v6_runtime_consumers_use_only_canonical_source_manifest_key() -> None:
    runtime_paths = (
        "scripts/build_action_qbc_v8_open_registration.py",
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/prepare_action_qbc_v8_open.py",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "scripts/supervise_action_qbc_v8_remote_tag.py",
        "scripts/validate_action_qbc_v8_open_payload.py",
        "scripts/verify_action_qbc_v8_remote_tag.py",
    )
    for relative in runtime_paths:
        raw = (ROOT / relative).read_bytes()
        assert b"added_in_open_freeze" not in raw
    assert b'get("open_freeze_added_files")' in (
        ROOT / "scripts/run_action_qbc_v8_open_diagnostic.py"
    ).read_bytes()


def test_p8v3_runner_dirfd_rejects_unregistered_empty_directory(
    tmp_path: Path,
) -> None:
    tracked = tmp_path / "tracked"
    tracked.mkdir()
    (tracked / "file.txt").write_bytes(b"tracked")
    runner._validate_worktree_entry_set(tmp_path, {"tracked/file.txt"})
    (tracked / "empty-unregistered").mkdir()
    with pytest.raises(
        runner._AdministrativeFailure,
        match="unregistered directory",
    ):
        runner._validate_worktree_entry_set(tmp_path, {"tracked/file.txt"})


@pytest.mark.skipif(os.name != "posix", reason="P8v3 immutable copies are Linux files")
def test_p8v3_runner_dirfd_immutable_remote_copy_requires_one_mode0444_link(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "remote.json"
    evidence.write_bytes(b'{"status":"verified"}')
    evidence.chmod(0o444)
    assert runner._immutable_linux_evidence(evidence, "synthetic remote") == evidence.read_bytes()
    extra_link = tmp_path / "extra-link.json"
    os.link(evidence, extra_link)
    with pytest.raises(runner._AdministrativeFailure, match="mode-0444"):
        runner._immutable_linux_evidence(evidence, "synthetic remote")
    extra_link.unlink()
    evidence.chmod(0o600)
    with pytest.raises(runner._AdministrativeFailure, match="mode-0444"):
        runner._immutable_linux_evidence(evidence, "synthetic remote")


@pytest.mark.skipif(os.name != "posix", reason="P8v3 anchors use Linux dirfd APIs")
def test_p8v3_runner_dirfd_anchor_rejects_fixed_path_replacement(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    displaced = tmp_path / "displaced"
    anchor = runner._open_directory_anchor(parent, "synthetic parent", empty=True)
    try:
        parent.rename(displaced)
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)
        with pytest.raises(
            runner._AdministrativeFailure,
            match="fixed path no longer names",
        ):
            runner._revalidate_directory_anchor(anchor)
    finally:
        os.close(anchor.descriptor)


@pytest.mark.skipif(os.name != "posix", reason="P8v3 publication uses Linux dirfd APIs")
def test_p8v3_runner_dirfd_publication_enforces_one_two_one_links(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "open"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    output = parent / "payload.json"
    payload = {"candidate": True}
    encoded = b'{"candidate":true}'
    anchor = runner._open_directory_anchor(parent, "synthetic output", empty=True)
    try:
        runner._publish(
            output,
            anchor,
            payload,
            encoded,
            wall_deadline=float("inf"),
            registration={},
            audit=_audit_stub(),
        )
        metadata = output.stat(follow_symlinks=False)
        assert output.read_bytes() == encoded
        assert runner.stat.S_IMODE(metadata.st_mode) == 0o600
        assert metadata.st_nlink == 1
        assert list(parent.iterdir()) == [output]
        runner._revalidate_directory_anchor(anchor)
    finally:
        os.close(anchor.descriptor)


@pytest.mark.skipif(os.name != "posix", reason="P8v3 publication uses Linux dirfd APIs")
def test_p8v3_runner_dirfd_publication_parent_swap_cleans_only_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "open"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    displaced = tmp_path / "displaced"
    output = parent / "payload.json"
    encoded = b'{"candidate":true}'
    anchor = runner._open_directory_anchor(parent, "synthetic output", empty=True)
    real_link = os.link

    def swapping_link(*args: Any, **kwargs: Any) -> None:
        real_link(*args, **kwargs)
        parent.rename(displaced)
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)
        (parent / "intruder.json").write_bytes(b"intruder")

    monkeypatch.setattr(runner.os, "link", swapping_link)
    try:
        with pytest.raises(
            runner._AdministrativeFailure,
            match="fixed path no longer names",
        ):
            runner._publish(
                output,
                anchor,
                {"candidate": True},
                encoded,
                wall_deadline=float("inf"),
                registration={},
                audit=_audit_stub(),
            )
    finally:
        os.close(anchor.descriptor)
    assert list(displaced.iterdir()) == []
    assert (parent / "intruder.json").read_bytes() == b"intruder"


@pytest.mark.skipif(os.name != "posix", reason="P8v3 claims use Linux dirfd APIs")
def test_p8v3_runner_dirfd_claim_parent_swap_is_detected_and_irreversible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "claims"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    displaced = tmp_path / "displaced-claims"
    claim = parent / "claim.json"
    real_reader = runner._plain_file_bytes_at

    def swapping_reader(
        parent_descriptor: int,
        component: str,
        name: str,
        *,
        maximum: int = runner._MAX_ADMIN_BYTES,
    ) -> bytes:
        observed = real_reader(
            parent_descriptor,
            component,
            name,
            maximum=maximum,
        )
        parent.rename(displaced)
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)
        return observed

    monkeypatch.setattr(runner, "_plain_file_bytes_at", swapping_reader)
    with pytest.raises(
        runner._AdministrativeFailure,
        match="fixed path no longer names",
    ):
        runner._exclusive_canonical(claim, {"schema_version": "synthetic"})
    assert not claim.exists()
    assert (displaced / "claim.json").exists()


@pytest.mark.skipif(os.name != "posix", reason="P8v3 ledger paths are Linux-only")
def test_p8v3_runner_dirfd_exact_ledger_rejects_rehashed_invented_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    open_commit = "c" * 40
    execution_root = tmp_path / "execution"
    authority_root = execution_root / "authority"
    execution = reconstruction._execution_contract(
        [_p8v3_runner_dirfd_renderer_row()]
    )
    execution["authority_root"] = str(authority_root)
    entries = [("synthetic.txt", "100644", "d" * 40, 1)]
    identities = [
        *runner._expected_authority_identities(authority_root, open_commit, entries),
        *runner._expected_attempt_identities(
            execution,
            execution_root,
            1,
            open_commit,
            entries,
        ),
    ]
    empty_sha = hashlib.sha256(b"").hexdigest()
    ledger = [
        {
            "sequence_index": index,
            **identity,
            "started": True,
            "exit_code": 0,
            "outcome": "completed",
            "timed_out": False,
            "duration_milliseconds": 1,
            "stdout_size_bytes": 0,
            "stdout_sha256": empty_sha,
            "stderr_size_bytes": 0,
            "stderr_sha256": empty_sha,
            "child_cleanup_passes": None,
        }
        for index, identity in enumerate(identities)
    ]
    receipt = {
        "status": "prepared",
        "open_freeze_commit_sha": open_commit,
        "command_ledger": ledger,
        "commands_sha256": runner._sha256(runner._canonical_json_bytes(ledger)),
        "command_environment_sha256": runner._sha256(
            runner._canonical_json_bytes(execution["preparation_command_environment"])
        ),
    }
    monkeypatch.setattr(runner, "_tree_entries", lambda *_args: entries)
    runner._validate_command_ledger(
        receipt,
        execution,
        execution_root,
        1,
        open_commit,
    )

    mutated = copy.deepcopy(receipt)
    mutated_row = mutated["command_ledger"][-1]
    mutated_row["argv"] = [*mutated_row["argv"], "--invented"]
    mutated_row["argv_sha256"] = runner._sha256(
        runner._canonical_json_bytes(mutated_row["argv"])
    )
    mutated["commands_sha256"] = runner._sha256(
        runner._canonical_json_bytes(mutated["command_ledger"])
    )
    with pytest.raises(
        runner._AdministrativeFailure,
        match="contains an invented command",
    ):
        runner._validate_command_ledger(
            mutated,
            execution,
            execution_root,
            1,
            open_commit,
        )


@pytest.mark.skipif(os.name != "posix", reason="P8v3 promotion is Linux-only")
def test_p8v3_runner_dirfd_attempt_binds_promoted_directory_inode(
    tmp_path: Path,
) -> None:
    import copy

    execution_root = tmp_path / "execution"
    processes = execution_root / "processes"
    processes.mkdir(parents=True, mode=0o700)
    source = execution_root / ".prepare-attempt-1"
    metadata = processes.stat(follow_symlinks=False)
    attempts = [
        {
            "attempt_index": 1,
            "process_a_stage": "completed",
            "process_b_stage": "completed",
            "cleanup": {
                "owned_paths": [str(source)],
                "removed": [],
                "passes": True,
            },
            "promotion": {
                "source_path": str(source),
                "destination_path": str(processes),
                "source_device": metadata.st_dev,
                "source_inode": metadata.st_ino,
                "passes": True,
            },
            "passes": True,
        }
    ]
    assert runner._validate_preparation_attempts(attempts, execution_root) == 1
    mutated = copy.deepcopy(attempts)
    mutated[0]["promotion"]["source_inode"] += 1
    with pytest.raises(
        runner._AdministrativeFailure,
        match="lost its staged identity",
    ):
        runner._validate_preparation_attempts(mutated, execution_root)
    boolean_index = copy.deepcopy(attempts)
    boolean_index[0]["attempt_index"] = True
    with pytest.raises(
        runner._AdministrativeFailure,
        match="attempt identity is invalid",
    ):
        runner._validate_preparation_attempts(boolean_index, execution_root)


@pytest.mark.skipif(os.name != "posix", reason="P8v3 claims use Linux dirfd APIs")
def test_p8v3_runner_dirfd_validator_claim_uses_shared_owned_writer(
    tmp_path: Path,
) -> None:
    tmp_path.chmod(0o700)
    claim = tmp_path / "validator-claim.json"
    value = {"schema_version": "synthetic-validator", "value": 1}
    raw = validator._exclusive_json(runner, claim, value, "synthetic validator claim")
    metadata = claim.stat(follow_symlinks=False)
    assert raw == runner._canonical_json_bytes(value)
    assert claim.read_bytes() == raw
    assert runner.stat.S_IMODE(metadata.st_mode) == 0o600
    assert metadata.st_nlink == 1


class _P8v4WindowsStream:
    def close(self) -> None:
        return None


class _P8v4WindowsProcess:
    pid = 8181

    def __init__(self, exit_code: int | None = None) -> None:
        self.stdout = _P8v4WindowsStream()
        self.stderr = _P8v4WindowsStream()
        self.exit_code = exit_code
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self.exit_code

    def kill(self) -> None:
        self.kill_calls += 1
        self.exit_code = 7

    def wait(self, timeout: float) -> int:
        assert timeout >= 0
        if self.exit_code is None:
            raise subprocess.TimeoutExpired("p8v4-windows", timeout)
        return self.exit_code


class _P8v4WindowsJob:
    def __init__(self, active: int = 0) -> None:
        self.active = active
        self.closed = False

    def active_processes(self) -> int:
        return self.active

    def terminate(self) -> bool:
        self.active = 0
        return True

    def close(self) -> bool:
        self.closed = True
        return True


def _p8v4_windows_index(
    path: str = "plain.txt",
    *,
    flags_mask: int = 0,
    extension: tuple[bytes, bytes] | None = None,
) -> bytes:
    raw_path = path.encode("utf-8")
    entry = bytearray(62)
    entry[24:28] = (0o100644).to_bytes(4, "big")
    entry[40:60] = bytes.fromhex("ab" * 20)
    entry[60:62] = (len(raw_path) | flags_mask).to_bytes(2, "big")
    body = bytes(entry) + raw_path + b"\0"
    body += b"\0" * ((-len(body)) % 8)
    payload = b"DIRC" + (2).to_bytes(4, "big") + (1).to_bytes(4, "big") + body
    if extension is not None:
        signature, value = extension
        payload += signature + len(value).to_bytes(4, "big") + value
    return payload + hashlib.sha1(payload, usedforsecurity=False).digest()


def _p8v4_windows_attempt(
    module: Any,
    classification: str,
    *,
    timed_out: bool,
    cleanup: bool | None,
    exit_code: int | None,
) -> dict[str, Any]:
    stdout = b""
    stderr = b""
    if classification == "stdout_limit":
        stdout = b"x" * module._STDOUT_CAP_BYTES
    if classification == "stderr_limit":
        stderr = b"x" * module._STDERR_CAP_BYTES
    return {
        "attempt_index": 1,
        "exit_code": exit_code,
        "classification": classification,
        "timed_out": timed_out,
        "duration_milliseconds": 120_000 if timed_out else 1,
        **module._stream_fields("stdout", stdout),
        **module._stream_fields("stderr", stderr),
        "child_cleanup_passes": cleanup,
    }


def test_p8v4_windows_exact_contract_and_cross_consumer_identity() -> None:
    expected = reconstruction.WINDOWS_REPOSITORY_CONTRACT
    assert len(remote_verifier._EXECUTION_KEYS) == 70
    assert len(supervisor._EXECUTION_KEYS) == 70
    assert remote_verifier._windows_repository_contract() == expected
    assert supervisor._windows_repository_contract() == expected
    assert set(expected) == remote_verifier._WINDOWS_REPOSITORY_CONTRACT_KEYS
    assert remote_verifier._PREREGISTRATION_TAG == reconstruction.PREREGISTRATION_TAG
    assert supervisor._PREREGISTRATION_COMMIT == reconstruction.PREREGISTRATION_COMMIT


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("flags_mask", [0x1000, 0x4000, 0x8000])
def test_p8v4_windows_index_rejects_stage_and_nonordinary_flags(
    module: Any,
    flags_mask: int,
) -> None:
    assert module._parse_git_index(_p8v4_windows_index()) == {
        "plain.txt": ("100644", "ab" * 20)
    }
    with pytest.raises(module._ProtocolFailure, match="nonordinary"):
        module._parse_git_index(_p8v4_windows_index(flags_mask=flags_mask))


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("signature", [b"link", b"sdir"])
def test_p8v4_windows_index_rejects_split_and_sparse_extensions(
    module: Any,
    signature: bytes,
) -> None:
    with pytest.raises(module._ProtocolFailure, match="split or sparse"):
        module._parse_git_index(
            _p8v4_windows_index(extension=(signature, b"synthetic"))
        )


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_local_config_parser_rejects_duplicates(
    module: Any,
) -> None:
    assert module._parse_local_config(b"Core.Bare\nfalse\0") == {
        "core.bare": "false"
    }
    with pytest.raises(module._ProtocolFailure, match="duplicate"):
        module._parse_local_config(b"core.bare\nfalse\0CORE.BARE\ntrue\0")


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize(
    ("classification", "timed_out", "cleanup", "exit_code"),
    [
        ("post_spawn_initialization_failed", False, True, 7),
        ("stream_capture_failed", False, True, 7),
        ("stream_capture_failed", True, True, 124),
        ("stdout_limit", True, True, 124),
        ("stderr_limit", True, True, 124),
        ("child_cleanup_failed", False, False, None),
        ("child_cleanup_failed", True, False, 7),
        ("verified", False, True, 0),
    ],
)
def test_p8v4_windows_attempt_classification_matrix(
    module: Any,
    classification: str,
    timed_out: bool,
    cleanup: bool | None,
    exit_code: int | None,
) -> None:
    attempt = _p8v4_windows_attempt(
        module,
        classification,
        timed_out=timed_out,
        cleanup=cleanup,
        exit_code=exit_code,
    )
    expected = b"" if classification == "verified" else b"expected"
    assert module._validate_attempt(attempt, 1, expected)[0] == classification
    if classification == "child_cleanup_failed":
        attempt["child_cleanup_passes"] = None
        with pytest.raises(module._ProtocolFailure, match="false cleanup"):
            module._validate_attempt(attempt, 1, expected)


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_post_spawn_initialization_failure_is_structured(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _P8v4WindowsProcess()
    job = _P8v4WindowsJob()
    state = module._SpawnedState(process, job, True, False)
    monkeypatch.setattr(module, "_spawn_suspended", lambda *_args, **_kwargs: state)
    now = module.time.monotonic_ns()
    kwargs = {
        "cwd": module._NEUTRAL_GIT_CWD,
        "environment": module._git_environment(),
        "live_deadline_ns": now + 10_000_000_000,
        "cleanup_deadline_ns": now + 20_000_000_000,
        "stdout_cap": 1,
        "stderr_cap": 1,
        "deadline_reason": "timeout",
    }
    result = module._run_bounded_process(["synthetic"], **kwargs)
    assert result.spawned is True
    assert result.reason == "post_spawn_initialization_failed"
    assert result.exit_code == 7
    assert result.timed_out is False
    assert result.cleanup_passes is True
    assert result.stdout == result.stderr == b""
    assert process.kill_calls == 1
    assert job.closed is True


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_initialization_cleanup_failure_has_truthful_false(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _P8v4WindowsProcess()
    job = _P8v4WindowsJob()
    state = module._SpawnedState(process, job, True, True)
    monkeypatch.setattr(module, "_spawn_suspended", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(
        module,
        "_cleanup_initialization_failure",
        lambda *_args, **_kwargs: False,
    )
    now = module.time.monotonic_ns()
    result = module._run_bounded_process(
        ["synthetic"],
        cwd=module._NEUTRAL_GIT_CWD,
        environment=module._git_environment(),
        live_deadline_ns=now + 10_000_000_000,
        cleanup_deadline_ns=now + 20_000_000_000,
        stdout_cap=1,
        stderr_cap=1,
        deadline_reason="timeout",
    )
    assert result.reason == "child_cleanup_failed"
    assert result.exit_code is None
    assert result.cleanup_passes is False


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_stream_capture_failure_is_not_cleanup_failure(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _P8v4WindowsProcess()
    job = _P8v4WindowsJob(active=1)

    def capture(_stream: Any, state: Any) -> None:
        state.data.extend(b"partial")
        state.failed.set()

    def cleanup(_process: Any, _job: Any, *, deadline_ns: int) -> bool:
        assert deadline_ns > 0
        process.exit_code = 7
        job.active = 0
        return True

    monkeypatch.setattr(module, "_spawn_suspended", lambda *_a, **_k: (process, job))
    monkeypatch.setattr(module, "_capture_stream", capture)
    monkeypatch.setattr(module, "_cleanup_tree", cleanup)
    now = module.time.monotonic_ns()
    result = module._run_bounded_process(
        ["synthetic"],
        cwd=module._NEUTRAL_GIT_CWD,
        environment=module._git_environment(),
        live_deadline_ns=now + 10_000_000_000,
        cleanup_deadline_ns=now + 20_000_000_000,
        stdout_cap=64,
        stderr_cap=64,
        deadline_reason="timeout",
    )
    assert result.reason == "stream_capture_failed"
    assert result.cleanup_passes is True
    assert result.exit_code == 7
    assert result.stdout == result.stderr == b"partial"


def test_p8v4_windows_online_deadline_equality_is_overall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = 1_000_000_000
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(remote_verifier.time, "monotonic_ns", lambda: origin)

    def bounded(_argv: Any, **kwargs: Any) -> Any:
        calls.append(dict(kwargs))
        return remote_verifier._ManagedResult(
            True, 7, b"", b"", 1, None, False, None
        )

    monkeypatch.setattr(remote_verifier, "_run_bounded_process", bounded)
    cleanup = origin + 150_000_000_000
    remote_verifier._remote_attempt(
        1,
        live_admission_deadline_ns=origin + 120_000_000_000,
        cleanup_deadline_ns=cleanup,
        expected_stdout=b"expected",
    )
    remote_verifier._remote_attempt(
        1,
        live_admission_deadline_ns=origin + 120_000_000_001,
        cleanup_deadline_ns=cleanup,
        expected_stdout=b"expected",
    )
    assert [call["deadline_reason"] for call in calls] == [
        "overall_deadline",
        "timeout",
    ]
    assert all(
        call["live_deadline_ns"] == origin + 120_000_000_000
        for call in calls
    )


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_original_checkout_git_has_both_global_options(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[list[str]] = []

    def bounded(argv: Any, **_kwargs: Any) -> Any:
        observed.append(list(argv))
        return module._ManagedResult(True, 0, b"ok", b"", 1, None, False, None)

    monkeypatch.setattr(module, "_run_bounded_process", bounded)
    module._run_git_command(
        ["--version"],
        overall_deadline_ns=module.time.monotonic_ns() + 100_000_000_000,
    )
    assert observed == [
        [
            module._GIT_PATH,
            "--no-replace-objects",
            "--no-optional-locks",
            "--version",
        ]
    ]


def _p8v4_lifecycle_stream_fields(prefix: str, raw: bytes) -> dict[str, Any]:
    return {
        f"{prefix}_size_bytes": len(raw),
        f"{prefix}_sha256": hashlib.sha256(raw).hexdigest(),
        f"{prefix}_base64": base64.b64encode(raw).decode("ascii"),
    }


def _p8v4_lifecycle_remote_attempt(
    classification: str,
    *,
    exit_code: int | None,
    timed_out: bool,
    cleanup: bool | None,
    stdout: bytes = b"",
    stderr: bytes = b"",
    duration: int = 1,
) -> dict[str, Any]:
    return {
        "attempt_index": 1,
        "exit_code": exit_code,
        "classification": classification,
        "timed_out": timed_out,
        "duration_milliseconds": duration,
        **_p8v4_lifecycle_stream_fields("stdout", stdout),
        **_p8v4_lifecycle_stream_fields("stderr", stderr),
        "child_cleanup_passes": cleanup,
    }


def _p8v4_lifecycle_validate_attempt_everywhere(
    value: dict[str, Any], expected_stdout: bytes = b"verified\n"
) -> None:
    preparation._validate_remote_attempt(value, 1, expected_stdout)
    finalizer._validate_remote_attempt(value, index=1, expected_stdout=expected_stdout)
    lifecycle._validate_embedded_remote_attempt(
        value, index=1, expected_stdout=expected_stdout
    )


def test_p8v7_lifecycle_frozen_identity_execution_schema_and_windows_object_parity() -> None:
    document_name = (
        "experiment_amendment_2026-08-18_action_qbc_v8_open_"
        "bounded_remote_verification_v7_consumed_lifecycle_recovery.md"
    )
    document = (ROOT / "docs" / document_name).read_bytes()
    modules = (preparation, lifecycle, finalizer, runner)
    assert {
        module._PREREGISTRATION_TAG for module in modules
    } == {"prereg-action-qbc-v8-open-bounded-remote-verification-v7"}
    assert {module._PREREGISTRATION_COMMIT for module in modules} == {
        "15059c482d9e463f01cb31fdfd33c96d1f60db0a"
    }
    assert {module._PREREGISTRATION_DOCUMENT_BYTE_COUNT for module in modules} == {
        len(document)
    } == {37_552}
    assert {module._PREREGISTRATION_DOCUMENT_SHA256 for module in modules} == {
        hashlib.sha256(document).hexdigest()
    }
    assert {module._P8V5_COMMIT for module in modules} == {
        "09f9caea346866a1acf35c20e0c9d937096b5ce3"
    }
    assert {module._P8V5_TAG for module in modules} == {
        "prereg-action-qbc-v8-open-bounded-remote-verification-v5"
    }
    assert {module._P8V5_TREE for module in modules} == {
        "47a978cdd887fd6dc1cb5e80e36aa3e0a5a29253"
    }
    assert {module._P8V4_COMMIT for module in modules} == {
        "e0bff9ffc185196cafa938c8f7c9a7186366258b"
    }
    assert {module._P8V4_TAG for module in modules} == {
        "prereg-action-qbc-v8-open-bounded-remote-verification-v4"
    }
    assert {module._O8V1_COMMIT for module in modules} == {
        "7685fbdccd41702216b3a3f06d2a0ac699aca7ec"
    }
    assert {module._O8V1_TAG for module in modules} == {
        "action-qbc-v8-open-diagnostic-freeze-v1"
    }
    assert {module._O8V1_TREE for module in modules} == {
        "9b9ad5ba986afacbcdb1fde3cd69e0f1c94efdf2"
    }
    assert {module._O8V2_COMMIT for module in modules} == {
        "8da637a47de0c88f917f222e52e54b342d729be9"
    }
    assert {module._O8V2_TAG for module in modules} == {
        "action-qbc-v8-open-diagnostic-freeze-v2"
    }
    assert {module._O8V2_TREE for module in modules} == {
        "247eba59e1e2ac9b0611c0e361de945dae0f2dc8"
    }
    assert {module._P8V6_COMMIT for module in modules} == {
        "61cebe90a2f4f7c78ec45119de53a482ed13a655"
    }
    assert {module._P8V6_TAG for module in modules} == {
        "prereg-action-qbc-v8-open-bounded-remote-verification-v6"
    }
    assert {module._P8V6_TREE for module in modules} == {
        "65695876c44eeb8cac5437149384071f88ff6018"
    }
    assert {module._O8V3_COMMIT for module in modules} == {
        "5725395a850627fae10e8bb8b27083ccf63b6ec7"
    }
    assert {module._O8V3_TAG for module in modules} == {
        "action-qbc-v8-open-diagnostic-freeze-v3"
    }
    assert {module._O8V3_TREE for module in modules} == {
        "7d38de8f5cec16cab92c9d3b757a218e8e490272"
    }
    windows_modules = (supervisor, remote_verifier)
    assert {module._OPEN_FREEZE_TAG for module in (*modules, *windows_modules, validator)} == {
        "action-qbc-v8-open-diagnostic-freeze-v4"
    }
    assert {module._PREREGISTRATION_COMMIT for module in (*windows_modules, validator)} == {
        "15059c482d9e463f01cb31fdfd33c96d1f60db0a"
    }
    assert {module._PREREGISTRATION_TAG for module in windows_modules} == {
        "prereg-action-qbc-v8-open-bounded-remote-verification-v7"
    }
    assert {module._PREREGISTRATION_DOCUMENT_BLOB for module in windows_modules} == {
        "c0cda2417bd98a42b76e8e1bbdee4cec01dd68f9"
    }
    assert {module._PREREGISTRATION_DOCUMENT_SHA256 for module in windows_modules} == {
        hashlib.sha256(document).hexdigest()
    }
    assert reconstruction.PREREGISTRATION_COMMIT == "15059c482d9e463f01cb31fdfd33c96d1f60db0a"
    assert len(document) == reconstruction.PREREGISTRATION_DOCUMENT_BYTE_COUNT
    assert hashlib.sha256(document).hexdigest() == reconstruction.PREREGISTRATION_DOCUMENT_SHA256
    assert reconstruction.PREREGISTRATION_DOCUMENT_BLOB == runner._PREREGISTRATION_DOCUMENT_BLOB
    assert reconstruction.PREREGISTRATION_V5_COMMIT == runner._P8V5_COMMIT
    assert reconstruction.PREREGISTRATION_V5_TREE == runner._P8V5_TREE
    assert reconstruction.PREREGISTRATION_V4_COMMIT == runner._P8V4_COMMIT
    assert reconstruction.OPEN_FREEZE_V1_COMMIT == runner._O8V1_COMMIT
    assert reconstruction.OPEN_FREEZE_V1_TREE == runner._O8V1_TREE
    assert reconstruction.OPEN_FREEZE_V2_COMMIT == runner._O8V2_COMMIT
    assert reconstruction.OPEN_FREEZE_V2_TREE == runner._O8V2_TREE
    assert reconstruction.PREREGISTRATION_V6_COMMIT == runner._P8V6_COMMIT
    assert reconstruction.PREREGISTRATION_V6_TREE == runner._P8V6_TREE
    assert reconstruction.OPEN_FREEZE_V3_COMMIT == runner._O8V3_COMMIT
    assert reconstruction.OPEN_FREEZE_V3_TREE == runner._O8V3_TREE
    assert reconstruction.OPEN_FREEZE_TAG == "action-qbc-v8-open-diagnostic-freeze-v4"
    assert reconstruction.RESULT_TAG == "action-qbc-v8-open-diagnostic-result-v4"
    assert reconstruction.RESULT_BRANCH == "action-qbc-v8-open-diagnostic-result"
    assert lifecycle._RESULT_TAG == reconstruction.RESULT_TAG
    assert f"refs/heads/{reconstruction.RESULT_BRANCH}" == lifecycle._RESULT_BRANCH_REF
    assert [len(module._EXECUTION_KEYS) for module in modules] == [70, 70, 70, 70]
    assert (
        preparation._EXECUTION_KEYS
        == lifecycle._EXECUTION_KEYS
        == finalizer._EXECUTION_KEYS
        == runner._EXECUTION_KEYS
    )
    assert (
        preparation._WINDOWS_REPOSITORY_CONTRACT
        == lifecycle._WINDOWS_REPOSITORY_CONTRACT
        == finalizer._WINDOWS_REPOSITORY_CONTRACT
        == runner._WINDOWS_REPOSITORY_CONTRACT
    )
    linux_tools = {
        value["path"]: (value["sha256"], value["version"])
        for value in reconstruction._execution_contract(
            [_p8v3_runner_dirfd_renderer_row()]
        )["linux_tool_identities"]
    }
    assert linux_tools["/usr/bin/git"] == (
        "2a8c18fbf43da9f692d75474c72bea9dfd796c260b0f3dfe456376abc3bbd668",
        "2.43.0",
    )
    assert linux_tools | {"/usr/bin/git": ("", "")} == {
        "/usr/bin/env": (
            "1490a663e7312c4347987b2e12d7d73950ed1e9a322449daf8e4836660396e31",
            "GNU coreutils 9.4",
        ),
        "/usr/bin/git": ("", ""),
        "/usr/bin/install": (
            "b4663b43190ea551f682cfac9500f3f4f6e94890d8ce8822bb81a819f15dab00",
            "GNU coreutils 9.4",
        ),
        "/usr/bin/python3": (
            "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118",
            "CPython 3.12.3",
        ),
        "/usr/bin/test": (
            "52b0ca5cef7e104ad5e0a8a29bd1522c205cc8404e46e153e5afc54605857c4d",
            "GNU coreutils 9.4",
        ),
        "/usr/bin/timeout": (
            "2ee918a5358c0388719e710134bc32cffb934f4bd2a8fb9beb86ef4d6ec8bd8a",
            "GNU coreutils 9.4",
        ),
        "/usr/local/bin/uv": (
            "1cb9cd0a1749debf6049d7d2bb933882cc52d81016326ee6d99a786d6c988b03",
            "0.11.28",
        ),
    }


def test_p8v7_fresh_namespaces_never_alias_consumed_o8v3_evidence() -> None:
    renderer_row = {
        "mode": "100644",
        "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "git_blob_sha1": "a" * 40,
        "sha256": "b" * 64,
        "byte_count": 1,
    }
    execution = reconstruction._execution_contract([renderer_row])
    fresh_root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open-v4"
    old_root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v8-open"
    assert execution["execution_root"] == fresh_root
    assert fresh_root == preparation._EXECUTION_ROOT
    assert fresh_root == runner._EXECUTION_ROOT_TEXT
    assert validator._EXECUTION_ROOT.as_posix() == fresh_root
    assert lifecycle._EXECUTION_ROOT.as_posix() == fresh_root
    assert finalizer._EXECUTION_ROOT.as_posix() == fresh_root

    windows_prefix = (
        r"D:\kaggle competitions\arc3-crosslevel-voi-action-qbc-v8-remote-"
    )
    expected_windows = {
        f"{windows_prefix}verification-claim-v4.json",
        f"{windows_prefix}verifier-start-claim-v4.json",
        f"{windows_prefix}verification-v4.json",
        f"{windows_prefix}verification-supervisor-v4.json",
    }
    assert {
        supervisor._CLAIM_PATH,
        supervisor._START_CLAIM_PATH,
        supervisor._REMOTE_RECEIPT_PATH,
        supervisor._SUPERVISOR_RECEIPT_PATH,
    } == expected_windows
    assert {
        remote_verifier._CLAIM_PATH,
        remote_verifier._START_CLAIM_PATH,
        remote_verifier._RECEIPT_PATH,
        remote_verifier._SUPERVISOR_RECEIPT_PATH,
    } == expected_windows
    assert {
        execution["remote_claim_windows_path"],
        execution["remote_verifier_claim_windows_path"],
        execution["remote_receipt_windows_path"],
        execution["remote_supervisor_receipt_windows_path"],
    } == expected_windows

    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for child in value.values() for item in strings(child)]
        if isinstance(value, (list, tuple)):
            return [item for child in value for item in strings(child)]
        return []

    active_strings = set(strings(execution))
    old_windows = {
        f"{windows_prefix}verification-claim.json",
        f"{windows_prefix}verifier-start-claim.json",
        f"{windows_prefix}verification.json",
        f"{windows_prefix}verification-supervisor.json",
    }
    assert old_root not in active_strings
    assert old_windows.isdisjoint(active_strings)
    assert reconstruction.RESULT_TAG == "action-qbc-v8-open-diagnostic-result-v4"
    assert lifecycle._RESULT_TAG == reconstruction.RESULT_TAG
    assert "action-qbc-v8-open-diagnostic-result-v3" not in active_strings


def test_p8v7_recovery_authority_and_attempt_plans_are_exactly_54_rows() -> None:
    registration = {
        "source_manifest": {
            "preregistration_tree": [],
            "open_freeze_added_files": [],
        }
    }
    authority_root = "/synthetic/authority"
    execution = {"authority_root": authority_root}
    execute_rows = lifecycle._preparation_expected_authority_identities(
        registration, execution, commit="f" * 40
    )
    finalizer_rows = finalizer._preparation_expected_authority_identities(
        registration, execution, commit="f" * 40
    )
    registration_raw = lifecycle.canonical_json_bytes(registration)
    registration_oid = hashlib.sha1(
        b"blob "
        + str(len(registration_raw)).encode("ascii")
        + b"\0"
        + registration_raw,
        usedforsecurity=False,
    ).hexdigest()
    runner_rows = runner._expected_authority_identities(
        PurePosixPath(authority_root),  # type: ignore[arg-type]
        "f" * 40,
        [
            (
                runner._EXPECTED_REGISTRATION,
                "100644",
                registration_oid,
                len(registration_raw),
            )
        ],
    )
    assert execute_rows == finalizer_rows == runner_rows
    assert len(execute_rows) == 54
    suffixes = [row["argv"][5:] for row in execute_rows]
    recovery = [
        ["-t", f"refs/tags/{lifecycle._O8V1_TAG}"],
        [f"refs/tags/{lifecycle._O8V1_TAG}"],
        ["--parents", "-n", "1", lifecycle._O8V1_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V4_COMMIT,
            lifecycle._O8V1_COMMIT,
        ],
        ["-t", f"refs/tags/{lifecycle._P8V5_TAG}"],
        [f"refs/tags/{lifecycle._P8V5_TAG}"],
        ["--parents", "-n", "1", lifecycle._P8V5_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V1_COMMIT,
            lifecycle._P8V5_COMMIT,
        ],
        ["-t", f"refs/tags/{lifecycle._O8V2_TAG}"],
        [f"refs/tags/{lifecycle._O8V2_TAG}"],
        ["--parents", "-n", "1", lifecycle._O8V2_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V5_COMMIT,
            lifecycle._O8V2_COMMIT,
        ],
        ["-t", f"refs/tags/{lifecycle._P8V6_TAG}"],
        [f"refs/tags/{lifecycle._P8V6_TAG}"],
        ["--parents", "-n", "1", lifecycle._P8V6_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V2_COMMIT,
            lifecycle._P8V6_COMMIT,
        ],
        ["-t", f"refs/tags/{lifecycle._O8V3_TAG}"],
        [f"refs/tags/{lifecycle._O8V3_TAG}"],
        ["--parents", "-n", "1", lifecycle._O8V3_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._P8V6_COMMIT,
            lifecycle._O8V3_COMMIT,
        ],
        ["-t", f"refs/tags/{lifecycle._PREREGISTRATION_TAG}"],
        [f"refs/tags/{lifecycle._PREREGISTRATION_TAG}"],
        ["--parents", "-n", "1", lifecycle._PREREGISTRATION_COMMIT],
        [
            "--name-status",
            "--no-renames",
            "-z",
            lifecycle._O8V3_COMMIT,
            lifecycle._PREREGISTRATION_COMMIT,
        ],
    ]
    first = suffixes.index(recovery[0])
    assert suffixes[first : first + len(recovery)] == recovery
    assert len(lifecycle._preparation_attempt_plan()) == 54
    assert len(finalizer._preparation_attempt_plan()) == 54
    assert len(preparation._attempt_phase_plan()) == 54


def _runner_recovery_git_responses(
    open_commit: str,
    p8v6_document_raw: bytes,
    p8v7_document_raw: bytes,
) -> dict[tuple[str, ...], bytes]:
    def name_status(records: set[tuple[str, str]]) -> bytes:
        return b"".join(
            status.encode("ascii") + b"\0" + path.encode("utf-8") + b"\0"
            for status, path in sorted(records)
        )

    return {
        ("cat-file", "-t", f"refs/tags/{runner._P8V4_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._P8V4_TAG}"): (
            f"{runner._P8V4_COMMIT}\n".encode("ascii")
        ),
        ("cat-file", "-t", f"refs/tags/{runner._O8V1_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._O8V1_TAG}"): (
            f"{runner._O8V1_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._O8V1_COMMIT): (
            f"{runner._O8V1_COMMIT} {runner._P8V4_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._O8V1_COMMIT}^{{tree}}"): (
            f"{runner._O8V1_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V4_COMMIT,
            runner._O8V1_COMMIT,
        ): name_status({("A", path) for path in runner._O8_ADDITIONS}),
        ("cat-file", "-t", f"refs/tags/{runner._P8V5_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._P8V5_TAG}"): (
            f"{runner._P8V5_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._P8V5_COMMIT): (
            f"{runner._P8V5_COMMIT} {runner._O8V1_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._P8V5_COMMIT}^{{tree}}"): (
            f"{runner._P8V5_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._O8V1_COMMIT,
            runner._P8V5_COMMIT,
        ): name_status(
            {
                *(("D", path) for path in runner._O8_ADDITIONS),
                ("A", runner._P8V5_DOCUMENT),
            }
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V4_COMMIT,
            runner._P8V5_COMMIT,
        ): name_status({("A", runner._P8V5_DOCUMENT)}),
        ("cat-file", "-t", f"refs/tags/{runner._O8V2_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._O8V2_TAG}"): (
            f"{runner._O8V2_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._O8V2_COMMIT): (
            f"{runner._O8V2_COMMIT} {runner._P8V5_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._O8V2_COMMIT}^{{tree}}"): (
            f"{runner._O8V2_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V5_COMMIT,
            runner._O8V2_COMMIT,
        ): name_status({("A", path) for path in runner._O8_ADDITIONS}),
        ("cat-file", "-t", f"refs/tags/{runner._P8V6_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._P8V6_TAG}"): (
            f"{runner._P8V6_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._P8V6_COMMIT): (
            f"{runner._P8V6_COMMIT} {runner._O8V2_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._P8V6_COMMIT}^{{tree}}"): (
            f"{runner._P8V6_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._O8V2_COMMIT,
            runner._P8V6_COMMIT,
        ): name_status(
            {
                *(("D", path) for path in runner._O8_ADDITIONS),
                ("A", runner._P8V6_DOCUMENT),
            }
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V5_COMMIT,
            runner._P8V6_COMMIT,
        ): name_status({("A", runner._P8V6_DOCUMENT)}),
        (
            "ls-tree",
            "-z",
            runner._P8V6_COMMIT,
            "--",
            runner._P8V6_DOCUMENT,
        ): (
            f"100644 blob {runner._P8V6_DOCUMENT_BLOB}\t"
            f"{runner._P8V6_DOCUMENT}\0"
        ).encode(),
        (
            "cat-file",
            "blob",
            f"{runner._P8V6_COMMIT}:{runner._P8V6_DOCUMENT}",
        ): p8v6_document_raw,
        ("cat-file", "-t", f"refs/tags/{runner._O8V3_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._O8V3_TAG}"): (
            f"{runner._O8V3_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._O8V3_COMMIT): (
            f"{runner._O8V3_COMMIT} {runner._P8V6_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._O8V3_COMMIT}^{{tree}}"): (
            f"{runner._O8V3_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V6_COMMIT,
            runner._O8V3_COMMIT,
        ): name_status({("A", path) for path in runner._O8_ADDITIONS}),
        ("cat-file", "-t", f"refs/tags/{runner._PREREGISTRATION_TAG}"): b"commit\n",
        ("rev-parse", f"refs/tags/{runner._PREREGISTRATION_TAG}"): (
            f"{runner._PREREGISTRATION_COMMIT}\n".encode("ascii")
        ),
        ("rev-list", "--parents", "-n", "1", runner._PREREGISTRATION_COMMIT): (
            f"{runner._PREREGISTRATION_COMMIT} {runner._O8V3_COMMIT}\n".encode("ascii")
        ),
        ("rev-parse", f"{runner._PREREGISTRATION_COMMIT}^{{tree}}"): (
            f"{runner._PREREGISTRATION_TREE}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._O8V3_COMMIT,
            runner._PREREGISTRATION_COMMIT,
        ): name_status(
            {
                *(("D", path) for path in runner._O8_ADDITIONS),
                ("A", runner._PREREGISTRATION_DOCUMENT),
            }
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._P8V6_COMMIT,
            runner._PREREGISTRATION_COMMIT,
        ): name_status({("A", runner._PREREGISTRATION_DOCUMENT)}),
        (
            "ls-tree",
            "-z",
            runner._PREREGISTRATION_COMMIT,
            "--",
            runner._PREREGISTRATION_DOCUMENT,
        ): (
            f"100644 blob {runner._PREREGISTRATION_DOCUMENT_BLOB}\t"
            f"{runner._PREREGISTRATION_DOCUMENT}\0"
        ).encode(),
        (
            "cat-file",
            "blob",
            f"{runner._PREREGISTRATION_COMMIT}:{runner._PREREGISTRATION_DOCUMENT}",
        ): p8v7_document_raw,
        ("rev-list", "--parents", "-n", "1", open_commit): (
            f"{open_commit} {runner._PREREGISTRATION_COMMIT}\n".encode("ascii")
        ),
        (
            "diff",
            "--name-status",
            "--no-renames",
            "-z",
            runner._PREREGISTRATION_COMMIT,
            open_commit,
        ): name_status({("A", path) for path in runner._O8_ADDITIONS}),
    }


def test_runner_requires_complete_p8v7_recovery_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_commit = "f" * 40
    p8v6_document_raw = b"synthetic P8v6 recovery document\n"
    p8v7_document_raw = b"synthetic P8v7 recovery document\n"
    monkeypatch.setattr(runner, "_P8V6_DOCUMENT_BYTE_COUNT", len(p8v6_document_raw))
    monkeypatch.setattr(
        runner,
        "_P8V6_DOCUMENT_SHA256",
        hashlib.sha256(p8v6_document_raw).hexdigest(),
    )
    monkeypatch.setattr(
        runner, "_PREREGISTRATION_DOCUMENT_BYTE_COUNT", len(p8v7_document_raw)
    )
    monkeypatch.setattr(
        runner,
        "_PREREGISTRATION_DOCUMENT_SHA256",
        hashlib.sha256(p8v7_document_raw).hexdigest(),
    )
    responses = _runner_recovery_git_responses(
        open_commit,
        p8v6_document_raw,
        p8v7_document_raw,
    )
    observed: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
        assert input_bytes is None
        observed.append(arguments)
        return responses[arguments]

    monkeypatch.setattr(runner, "_git", fake_git)
    runner._validate_recovery_lineage(Path("/synthetic-authority"), open_commit)
    assert len(runner._O8_ADDITIONS) == 15
    assert set(observed) == set(responses)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (runner._P8V4_COMMIT, runner._O8V1_COMMIT),
        (runner._O8V1_COMMIT, runner._P8V5_COMMIT),
        (runner._P8V4_COMMIT, runner._P8V5_COMMIT),
        (runner._P8V5_COMMIT, runner._O8V2_COMMIT),
        (runner._O8V2_COMMIT, runner._P8V6_COMMIT),
        (runner._P8V5_COMMIT, runner._P8V6_COMMIT),
        (runner._P8V6_COMMIT, runner._O8V3_COMMIT),
        (runner._O8V3_COMMIT, runner._PREREGISTRATION_COMMIT),
        (runner._P8V6_COMMIT, runner._PREREGISTRATION_COMMIT),
        (runner._PREREGISTRATION_COMMIT, "f" * 40),
    ],
)
def test_runner_rejects_each_inexact_recovery_delta(
    before: str,
    after: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p8v6_document_raw = b"synthetic P8v6 recovery document\n"
    p8v7_document_raw = b"synthetic P8v7 recovery document\n"
    monkeypatch.setattr(runner, "_P8V6_DOCUMENT_BYTE_COUNT", len(p8v6_document_raw))
    monkeypatch.setattr(
        runner,
        "_P8V6_DOCUMENT_SHA256",
        hashlib.sha256(p8v6_document_raw).hexdigest(),
    )
    monkeypatch.setattr(
        runner, "_PREREGISTRATION_DOCUMENT_BYTE_COUNT", len(p8v7_document_raw)
    )
    monkeypatch.setattr(
        runner,
        "_PREREGISTRATION_DOCUMENT_SHA256",
        hashlib.sha256(p8v7_document_raw).hexdigest(),
    )
    responses = _runner_recovery_git_responses(
        "f" * 40,
        p8v6_document_raw,
        p8v7_document_raw,
    )
    responses[("diff", "--name-status", "--no-renames", "-z", before, after)] = b""
    monkeypatch.setattr(
        runner,
        "_git",
        lambda _root, *arguments, input_bytes=None: responses[arguments],
    )
    with pytest.raises(runner._AdministrativeFailure, match="exact registered path delta"):
        runner._validate_recovery_lineage(Path("/synthetic-authority"), "f" * 40)


def test_p8v4_lifecycle_remote_attempt_matrix_has_cross_validator_parity() -> None:
    legal = [
        _p8v4_lifecycle_remote_attempt(
            "post_spawn_initialization_failed",
            exit_code=1,
            timed_out=False,
            cleanup=True,
        ),
        _p8v4_lifecycle_remote_attempt(
            "stream_capture_failed",
            exit_code=7,
            timed_out=False,
            cleanup=True,
            stdout=b"bounded-prefix",
        ),
        _p8v4_lifecycle_remote_attempt(
            "stream_capture_failed",
            exit_code=124,
            timed_out=True,
            cleanup=True,
            stderr=b"bounded-prefix",
        ),
        _p8v4_lifecycle_remote_attempt(
            "stdout_limit",
            exit_code=7,
            timed_out=False,
            cleanup=True,
            stdout=b"x" * 4_096,
        ),
        _p8v4_lifecycle_remote_attempt(
            "stdout_limit",
            exit_code=124,
            timed_out=True,
            cleanup=True,
            stdout=b"x" * 4_096,
        ),
        _p8v4_lifecycle_remote_attempt(
            "child_cleanup_failed",
            exit_code=None,
            timed_out=True,
            cleanup=False,
        ),
        _p8v4_lifecycle_remote_attempt(
            "verified",
            exit_code=0,
            timed_out=False,
            cleanup=None,
            stdout=b"verified\n",
        ),
        _p8v4_lifecycle_remote_attempt(
            "verified",
            exit_code=0,
            timed_out=False,
            cleanup=True,
            stdout=b"verified\n",
        ),
    ]
    for row in legal:
        _p8v4_lifecycle_validate_attempt_everywhere(row)

    illegal = [dict(legal[0], child_cleanup_passes=False),
               dict(legal[5], child_cleanup_passes=None),
               dict(legal[4], exit_code=7),
               _p8v4_lifecycle_remote_attempt(
                   "post_spawn_initialization_failed",
                   exit_code=1,
                   timed_out=False,
                   cleanup=True,
                   stdout=b"impossible-before-resume",
               )]
    for row in illegal:
        with pytest.raises(preparation.ProtocolError):
            preparation._validate_remote_attempt(row, 1, b"verified\n")
        with pytest.raises(finalizer._FinalizationError):
            finalizer._validate_remote_attempt(
                row, index=1, expected_stdout=b"verified\n"
            )
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle._validate_embedded_remote_attempt(
                row, index=1, expected_stdout=b"verified\n"
            )


def _p8v4_lifecycle_supervisor_row(
    classification: str,
    *,
    exit_code: int | None,
    timed_out: bool,
    cleanup: bool | None,
    status: str,
    stdout: bytes = b"",
    stderr: bytes = b"",
    remote_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": preparation._SUPERVISOR_SCHEMA,
        "treatment_id": preparation._TREATMENT_ID,
        "claim_sha256": "a" * 64,
        "verifier_start_claim_sha256": "b" * 64,
        "open_freeze_commit_sha": "c" * 40,
        "registration_content_sha256": "d" * 64,
        "verifier_argv_sha256": "e" * 64,
        "verifier_exit_code": exit_code,
        "classification": classification,
        "timed_out": timed_out,
        "duration_milliseconds": 600_000,
        **_p8v4_lifecycle_stream_fields("stdout", stdout),
        **_p8v4_lifecycle_stream_fields("stderr", stderr),
        "child_cleanup_passes": cleanup,
        "remote_receipt_sha256": remote_receipt_sha256,
        "status": status,
    }


def test_p8v4_lifecycle_supervisor_new_rows_and_failed_remote_propagation() -> None:
    execution = {
        "argv_hashes": {"remote_verifier": "e" * 64},
        "remote_policy": {
            "supervisor_deadline_seconds": 480,
            "supervisor_receipt_reserve_seconds": 20,
        },
    }
    registration = preparation._Registration(
        value={}, raw=b"", content_sha256="d" * 64, file_sha256="f" * 64,
        source_manifest_sha256="0" * 64, execution=execution,
    )
    absent = preparation._ArtifactState(Path("/absent"), False, "absent", None, None)
    context = preparation._ArmContext(
        Path("/execution"), Path("/authority"), "c" * 40, registration,
        absent, absent, False, False, (),
    )
    post_spawn = _p8v4_lifecycle_supervisor_row(
        "post_spawn_initialization_failed",
        exit_code=1,
        timed_out=False,
        cleanup=True,
        status="failed",
    )
    preparation._validate_supervisor_receipt(
        preparation.canonical_json_bytes(post_spawn),
        context,
        claim_sha256="a" * 64,
        start_raw_sha256="b" * 64,
        remote_raw_sha256=None,
        start_valid=True,
        remote_value=None,
    )
    lifecycle._validate_embedded_supervisor_common(
        post_spawn, receipt=None, execution=execution
    )
    claim_artifact = finalizer._Artifact(True, "readable", b"claim", "a" * 64, {})
    verifier_artifact = finalizer._Artifact(True, "readable", b"start", "b" * 64, {})
    absent_artifact = finalizer._Artifact(False, "absent", None, None, None)
    supervisor_artifact = finalizer._Artifact(
        True, "readable", preparation.canonical_json_bytes(post_spawn), "1" * 64,
        post_spawn,
    )
    assert finalizer._remote_supervisor_valid(
        supervisor_artifact,
        claim=claim_artifact,
        verifier=verifier_artifact,
        receipt=absent_artifact,
        remote_receipt_valid=False,
        execution=execution,
        commit="c" * 40,
        registration_sha="d" * 64,
    )

    failed_receipt = {"status": "failed"}
    failed_sha = "9" * 64
    completed = _p8v4_lifecycle_supervisor_row(
        "verifier_completed",
        exit_code=1,
        timed_out=False,
        cleanup=True,
        status="completed",
        remote_receipt_sha256=failed_sha,
    )
    preparation._validate_supervisor_receipt(
        preparation.canonical_json_bytes(completed),
        context,
        claim_sha256="a" * 64,
        start_raw_sha256="b" * 64,
        remote_raw_sha256=failed_sha,
        start_valid=True,
        remote_value=failed_receipt,
    )
    lifecycle._validate_embedded_supervisor_common(
        completed, receipt=failed_receipt, execution=execution
    )


def test_p8v4_lifecycle_bundle_invalid_preserves_true_cleanup_and_cleanup_failure_stops_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[lifecycle._ChildResult] = []
    child_calls: list[list[str]] = []
    monkeypatch.setattr(
        lifecycle, "_publish_lifecycle_ledger", lambda **_kwargs: (b"ledger", True)
    )
    monkeypatch.setattr(
        lifecycle, "_validate_ledger_for_publish", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        lifecycle,
        "_run_child_evidence",
        lambda *_args, **_kwargs: lifecycle._ChildResult(
            True, 0, False, True, "completed"
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "_publish_emergency_bundle",
        lambda _registration, **kwargs: (
            captured.append(kwargs["finalizer"]) or {},
            b"emergency",
        ),
    )
    monkeypatch.setattr(lifecycle, "_selected_bundle", lambda **_kwargs: ({}, b"", {}, [], True))
    monkeypatch.setattr(
        lifecycle,
        "_run_publisher_once",
        lambda argv, *_args, **_kwargs: child_calls.append(argv) or 0,
    )
    process_a = lifecycle._process_record("A", Path("/a"))
    process_b = lifecycle._process_record("B", Path("/b"))
    assert lifecycle._finish_lifecycle(
        authority=Path("/authority"),
        registration={"content_sha256": "b" * 64},
        execution={
            "finalizer_argv_template": ["finalizer"],
            "result_publisher_argv": ["publisher"],
        },
        commit="a" * 40,
        driver_raw=b"driver",
        deadline=float("inf"),
        stage=None,
        arm_exit=0,
        sequence=(),
        process_a=process_a,
        process_b=process_b,
    ) == 0
    assert captured == [lifecycle._ChildResult(True, 0, False, True, "bundle_invalid")]
    assert child_calls == [["publisher"]]

    captured.clear()
    child_calls.clear()
    monkeypatch.setattr(
        lifecycle,
        "_run_child_evidence",
        lambda *_args, **_kwargs: lifecycle._ChildResult(
            True, 0, False, False, "child_cleanup_failed"
        ),
    )
    assert lifecycle._finish_lifecycle(
        authority=Path("/authority"),
        registration={"content_sha256": "b" * 64},
        execution={
            "finalizer_argv_template": ["finalizer"],
            "result_publisher_argv": ["publisher"],
        },
        commit="a" * 40,
        driver_raw=b"driver",
        deadline=float("inf"),
        stage=None,
        arm_exit=0,
        sequence=(),
        process_a=process_a,
        process_b=process_b,
    ) == 1
    assert captured == [
        lifecycle._ChildResult(True, 0, False, False, "child_cleanup_failed")
    ]
    assert child_calls == []


def test_p8v7_lifecycle_selected_bundle_allows_only_cleanup_failure_coexistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_raw = b"canonical-normal"
    emergency_raw = b"canonical-emergency"
    normal_state = lifecycle._EvidenceState(
        True, "readable", normal_raw, hashlib.sha256(normal_raw).hexdigest(), None
    )
    emergency_state = lifecycle._EvidenceState(
        True, "readable", emergency_raw, hashlib.sha256(emergency_raw).hexdigest(), None
    )
    monkeypatch.setattr(
        lifecycle,
        "_evidence_state",
        lambda path, _label, *, role: emergency_state
        if path == lifecycle._EMERGENCY_BUNDLE
        else normal_state,
    )
    emergency_value = {
        "finalizer_classification": "child_cleanup_failed",
        "finalizer_exit_code": 0,
        "finalizer_timed_out": False,
        "finalizer_child_cleanup_passes": False,
        "finalization_bundle_exists": True,
        "finalization_bundle_sha256": hashlib.sha256(normal_raw).hexdigest(),
    }

    def validate(raw: bytes, **kwargs: Any) -> tuple[dict[str, Any], list[Any]]:
        del kwargs
        return (emergency_value, []) if raw == emergency_raw else ({}, [])

    monkeypatch.setattr(lifecycle, "_validate_bundle_bytes", validate)
    monkeypatch.setattr(lifecycle, "_validate_selected_document", lambda *_args, **_kwargs: None)
    selected = lifecycle._selected_bundle(
        commit="a" * 40,
        registration_sha="b" * 64,
        registration={},
    )
    assert selected[0] == lifecycle._EMERGENCY_BUNDLE
    assert selected[1] == emergency_raw
    assert normal_state.raw == normal_raw

    emergency_value["finalizer_classification"] = "bundle_invalid"
    with pytest.raises(lifecycle.LifecycleError, match="sole P8v7 cleanup override"):
        lifecycle._selected_bundle(
            commit="a" * 40,
            registration_sha="b" * 64,
            registration={},
        )


def _p8v4_windows_synthetic_repository_contract(root: Path) -> dict[str, Any]:
    config = b"[core]\n\tbare = false\n"
    exclude = b"# synthetic exclude\n"
    git = root / ".git"
    for relative in (
        "hooks",
        "info",
        "objects",
        "objects/info",
        "objects/pack",
        "refs",
        "refs/heads",
    ):
        (git / relative).mkdir(parents=True, exist_ok=True)
    (git / "config").write_bytes(config)
    (git / "info" / "exclude").write_bytes(exclude)
    (git / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (git / "refs" / "heads" / "main").write_bytes(b"a" * 40 + b"\n")
    (git / "hooks" / "pre-commit.sample").write_bytes(b"sample\n")
    (git / "index").write_bytes(_p8v4_windows_index())
    chain: list[str] = []
    current = Path(root.anchor)
    chain.append(str(current))
    for component in root.parts[1:]:
        current /= component
        chain.append(str(current))
    return {
        "active_hooks_allowed": False,
        "common_directory": str(git),
        "forbidden_admin_relative_paths": [
            r".git\commondir",
            r".git\config.worktree",
            r".git\index.lock",
            r".git\info\attributes",
            r".git\info\grafts",
            r".git\info\sparse-checkout",
            r".git\objects\info\alternates",
            r".git\objects\info\http-alternates",
            r".git\refs\replace",
            r".git\shallow",
        ],
        "forbidden_pack_suffixes": [".promisor"],
        "forbidden_ref_prefixes": ["refs/replace/"],
        "git_config_byte_count": len(config),
        "git_config_sha256": hashlib.sha256(config).hexdigest(),
        "git_directory": str(git),
        "index_path": str(git / "index"),
        "info_exclude_byte_count": len(exclude),
        "info_exclude_sha256": hashlib.sha256(exclude).hexdigest(),
        "local_config": {"core.bare": "false"},
        "plain_admin_relative_directories": [
            ".git",
            r".git\hooks",
            r".git\info",
            r".git\objects",
            r".git\objects\info",
            r".git\objects\pack",
            r".git\refs",
        ],
        "repository_ancestor_chain": chain,
        "repository_root": str(root),
    }


@pytest.mark.skipif(os.name != "nt", reason="P8v4 Windows repository gate")
@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize(
    ("relative", "payload"),
    [
        (r".git\hooks\pre-commit", b"active hook\n"),
        (r".git\info\attributes", b"attributes\n"),
        (r".git\objects\info\alternates", b"alternate\n"),
        (r".git\objects\pack\synthetic.promisor", b"promisor\n"),
        (
            r".git\packed-refs",
            b"# pack-refs with: peeled fully-peeled sorted\n"
            + b"a" * 40
            + b" refs/replace/synthetic\n",
        ),
        (r".git\sharedindex.synthetic", b"shared\n"),
        (r".git\index.lock", b"lock\n"),
        (r".git\refs\replace", b"replacement\n"),
    ],
)
def test_p8v4_windows_repository_gate_rejects_forbidden_sources(
    module: Any,
    relative: str,
    payload: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    contract = _p8v4_windows_synthetic_repository_contract(root)
    monkeypatch.setattr(module, "_windows_repository_contract", lambda: contract)
    module._capture_repository_snapshot(contract)
    destination = root.joinpath(*relative.split("\\"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    with pytest.raises(module._ProtocolFailure):
        module._capture_repository_snapshot(contract)


@pytest.mark.skipif(os.name != "nt", reason="P8v4 Windows repository gate")
@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("relative", [r".git\config", r".git\info\exclude"])
def test_p8v4_windows_repository_gate_rejects_bound_byte_mutation(
    module: Any,
    relative: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    contract = _p8v4_windows_synthetic_repository_contract(root)
    monkeypatch.setattr(module, "_windows_repository_contract", lambda: contract)
    module._capture_repository_snapshot(contract)
    target = root.joinpath(*relative.split("\\"))
    target.write_bytes(target.read_bytes() + b"mutation")
    with pytest.raises(module._ProtocolFailure, match="registered identity"):
        module._capture_repository_snapshot(contract)


@pytest.mark.skipif(os.name != "nt", reason="P8v4 Windows repository gate")
@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_repository_postcheck_detects_identity_change(
    module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    contract = _p8v4_windows_synthetic_repository_contract(root)
    monkeypatch.setattr(module, "_windows_repository_contract", lambda: contract)
    before = module._capture_repository_snapshot(contract)
    head = root / ".git" / "HEAD"
    head.write_bytes(b"ref: refs/heads/next\n")
    with pytest.raises(module._ProtocolFailure, match="changed"):
        module._require_repository_snapshot_unchanged(before, contract)


@pytest.mark.skipif(os.name != "nt", reason="P8v7 Windows repository gate")
@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v7_windows_repository_postcheck_detects_ancestor_sibling_change(
    module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ancestor = tmp_path / "repository-parent"
    ancestor.mkdir()
    root = ancestor / "repository"
    root.mkdir()
    contract = _p8v4_windows_synthetic_repository_contract(root)
    monkeypatch.setattr(module, "_windows_repository_contract", lambda: contract)
    before = module._capture_repository_snapshot(contract)
    sibling = root.parent / "created-after-snapshot.txt"
    sibling.write_bytes(b"ancestor mutation\n")
    with pytest.raises(module._ProtocolFailure, match="changed"):
        module._require_repository_snapshot_unchanged(before, contract)


@pytest.mark.parametrize(
    ("classification", "exit_code", "timed_out", "cleanup"),
    [
        ("post_spawn_initialization_failed", 7, False, True),
        ("stream_capture_failed", 7, False, True),
        ("stream_capture_failed", 124, True, True),
        ("child_cleanup_failed", None, False, False),
        ("child_cleanup_failed", 7, True, False),
        ("remote_receipt_missing", 1, False, True),
    ],
)
def test_p8v4_windows_supervisor_classification_matrix(
    classification: str,
    exit_code: int | None,
    timed_out: bool,
    cleanup: bool,
) -> None:
    registration = _remote_completion_supervisor_registration()
    lifecycle_claim = {"open_freeze_commit_sha": "c" * 40}
    result = supervisor._ManagedResult(
        True,
        exit_code,
        b"",
        b"",
        1,
        classification,
        timed_out,
        cleanup,
    )
    receipt = supervisor._supervisor_receipt_object(
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="d" * 64,
        start_claim_sha256=None,
        remote_receipt_sha256=None,
        result=result,
        classification=classification,
        status="failed",
    )
    supervisor._validate_supervisor_receipt(
        receipt,
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="d" * 64,
        start_claim_sha256=None,
        remote_receipt_sha256=None,
        remote_status=None,
    )
    if classification == "child_cleanup_failed":
        receipt["child_cleanup_passes"] = None
        with pytest.raises(supervisor._ProtocolFailure, match="false cleanup"):
            supervisor._validate_supervisor_receipt(
                receipt,
                registration=registration,
                lifecycle_claim=lifecycle_claim,
                lifecycle_claim_sha256="d" * 64,
                start_claim_sha256=None,
                remote_receipt_sha256=None,
                remote_status=None,
            )


def test_p8v4_windows_clean_remote_failure_propagates_as_completed_supervision() -> None:
    registration = _remote_completion_supervisor_registration()
    lifecycle_claim = {"open_freeze_commit_sha": "c" * 40}
    result = supervisor._ManagedResult(
        True,
        1,
        b"",
        b"",
        1,
        None,
        False,
        True,
    )
    receipt = supervisor._supervisor_receipt_object(
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="d" * 64,
        start_claim_sha256="e" * 64,
        remote_receipt_sha256="f" * 64,
        result=result,
        classification="verifier_completed",
        status="completed",
    )
    supervisor._validate_supervisor_receipt(
        receipt,
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="d" * 64,
        start_claim_sha256="e" * 64,
        remote_receipt_sha256="f" * 64,
        remote_status="failed",
    )
    assert receipt["status"] == "completed"
    assert receipt["classification"] == "verifier_completed"
    assert receipt["child_cleanup_passes"] is True


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("collision", ["cap_before", "exact", "timeout_before"])
@pytest.mark.parametrize(("stream_name", "selected_cap"), [("stdout", 11), ("stderr", 13)])
def test_p8v4_windows_cap_precedence_retains_orthogonal_timeout(
    module: Any,
    collision: str,
    stream_name: str,
    selected_cap: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _P8v4WindowsProcess()
    job = _P8v4WindowsJob(active=1)
    release_capture = threading.Event()

    def capture(_stream: Any, state: Any) -> None:
        if state.cap == selected_cap:
            if collision == "timeout_before":
                release_capture.wait(timeout=1)
            state.data.extend(b"x" * state.cap)
            state.overflow.set()

    def cleanup(_process: Any, _job: Any, *, deadline_ns: int) -> bool:
        assert deadline_ns >= 10
        release_capture.set()
        process.exit_code = 7
        job.active = 0
        return True

    monkeypatch.setattr(module, "_spawn_suspended", lambda *_a, **_k: (process, job))
    monkeypatch.setattr(module, "_capture_stream", capture)
    monkeypatch.setattr(module, "_cleanup_tree", cleanup)
    if collision == "cap_before":
        now = module.time.monotonic_ns()
        live_deadline = now + 10_000_000_000
        cleanup_deadline = now + 20_000_000_000
    else:
        calls = 0

        def clock() -> int:
            nonlocal calls
            calls += 1
            return 0 if calls == 1 else 10

        monkeypatch.setattr(module.time, "monotonic_ns", clock)
        live_deadline = 10
        cleanup_deadline = 1_000
    result = module._run_bounded_process(
        ["synthetic"],
        cwd=module._NEUTRAL_GIT_CWD,
        environment=module._git_environment(),
        live_deadline_ns=live_deadline,
        cleanup_deadline_ns=cleanup_deadline,
        stdout_cap=11,
        stderr_cap=13,
        deadline_reason="timeout",
    )
    assert result.reason == f"{stream_name}_limit"
    assert result.cleanup_passes is True
    assert getattr(result, stream_name) == b"x" * selected_cap
    assert result.timed_out is (collision != "cap_before")
    assert result.exit_code == (124 if result.timed_out else 7)


def test_p8v4_windows_remote_total_uses_exact_no_plus_n_lower_bound() -> None:
    registration = remote_verifier._Registration(
        value={"content_sha256": "a" * 64},
        data=b"registration",
        execution={},
        supervisor_manifest={},
        verifier_manifest={},
    )
    lifecycle_claim = {"open_freeze_commit_sha": "b" * 40}
    tools = [
        {"path": name, "version": "v", "sha256": character * 64}
        for name, character in (("python", "1"), ("git", "2"), ("taskkill", "3"))
    ]
    attempts = [
        _p8v4_windows_attempt(
            remote_verifier,
            "retryable_git_128",
            timed_out=False,
            cleanup=None,
            exit_code=128,
        ),
        {
            **_p8v4_windows_attempt(
                remote_verifier,
                "unexpected_exit",
                timed_out=False,
                cleanup=None,
                exit_code=7,
            ),
            "attempt_index": 2,
        },
    ]
    for attempt in attempts:
        attempt["duration_milliseconds"] = 0
    receipt = remote_verifier._receipt_object(
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256="5" * 64,
        python=tools[0],
        git=tools[1],
        taskkill=tools[2],
        attempts=attempts,
        status="failed",
        selected_attempt=None,
        total_duration_milliseconds=15_000,
    )
    remote_verifier._validate_receipt(
        receipt,
        registration=registration,
        lifecycle_claim=lifecycle_claim,
        lifecycle_claim_sha256="4" * 64,
        start_claim_sha256="5" * 64,
        python=tools[0],
        git=tools[1],
        taskkill=tools[2],
    )
    receipt["total_duration_milliseconds"] = 14_999
    with pytest.raises(remote_verifier._ProtocolFailure, match="shorter"):
        remote_verifier._validate_receipt(
            receipt,
            registration=registration,
            lifecycle_claim=lifecycle_claim,
            lifecycle_claim_sha256="4" * 64,
            start_claim_sha256="5" * 64,
            python=tools[0],
            git=tools[1],
            taskkill=tools[2],
        )


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "git_directory",
        "common_directory",
        "config_extra",
        "tree_oid",
        "stage",
        "cache_flag",
        "index_oid",
    ],
)
def test_p8v4_windows_fake_git_repository_contract_mutation_matrix(
    module: Any,
    mutation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = tmp_path / ".git"
    git.mkdir()
    index_path = git / "index"
    index_path.write_bytes(
        _p8v4_windows_index()
        if mutation != "index_oid"
        else _p8v4_windows_index("other.txt")
    )
    contract = {
        "repository_root": str(tmp_path),
        "git_directory": str(git),
        "common_directory": str(git),
        "index_path": str(index_path),
        "local_config": {"core.bare": "false"},
    }
    commit = "c" * 40
    oid = "ab" * 20

    def fake_git(arguments: Any, *, overall_deadline_ns: int) -> bytes:
        assert overall_deadline_ns > 0
        suffix = tuple(arguments[2:])
        if suffix == ("rev-parse", "--absolute-git-dir"):
            path = tmp_path / "wrong" if mutation == "git_directory" else git
            return f"{path}\n".encode()
        if suffix == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            path = tmp_path / "wrong" if mutation == "common_directory" else git
            return f"{path}\n".encode()
        if suffix == ("config", "--local", "--null", "--list"):
            extra = b"extra.key\nvalue\0" if mutation == "config_extra" else b""
            return b"core.bare\nfalse\0" + extra
        if suffix == ("ls-tree", "-r", "-z", commit):
            tree_oid = "de" * 20 if mutation == "tree_oid" else oid
            return f"100644 blob {tree_oid}\tplain.txt\0".encode()
        if suffix == ("ls-files", "--stage", "-z"):
            stage = "1" if mutation == "stage" else "0"
            return f"100644 {oid} {stage}\tplain.txt\0".encode()
        if suffix == ("ls-files", "-v", "-z"):
            marker = "S" if mutation == "cache_flag" else "H"
            return f"{marker} plain.txt\0".encode()
        raise AssertionError(f"unexpected fake Git argv: {arguments!r}")

    monkeypatch.setattr(module, "_run_git_command", fake_git)
    if mutation == "none":
        module._validate_repository_git_contract(
            commit,
            contract,
            overall_deadline_ns=10**30,
        )
    else:
        with pytest.raises(module._ProtocolFailure):
            module._validate_repository_git_contract(
                commit,
                contract,
                overall_deadline_ns=10**30,
            )


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
def test_p8v4_windows_plain_directory_gate_rejects_reparse_attribute(
    module: Any,
) -> None:
    class SyntheticReparsePath:
        def lstat(self) -> Any:
            return SimpleNamespace(
                st_mode=module.stat.S_IFDIR | 0o700,
                st_file_attributes=0x400,
            )

    with pytest.raises(module._ProtocolFailure, match="non-reparse"):
        module._plain_directory_metadata(SyntheticReparsePath(), "synthetic ancestor")


@pytest.mark.parametrize("attempt_count", [1, 2])
def test_p8v4_semantic_closure_failed_preparation_requires_passed_owned_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attempt_count: int,
) -> None:
    import copy

    registration, _payload, payload_raw, commit, _registration_file_sha = (
        _schema_gap_fallback_fixture(tmp_path, monkeypatch)
    )
    successful = _schema_gap_successful_machine(
        registration=registration,
        commit=commit,
        registration_sha=registration["content_sha256"],
        payload_raw=payload_raw,
    )
    failed = _p8v3_preparation_semantics_failed_receipt(
        successful["preparation_receipt"], attempt_count=attempt_count
    )
    assert all(
        attempt["cleanup"]["passes"] is True
        and attempt["cleanup"]["removed"] == attempt["cleanup"]["owned_paths"]
        for attempt in failed["attempts"]
    )
    assert failed["process_a"] is None and failed["process_b"] is None
    _p8v3_preparation_semantics_validate_receipt_with_both_consumers(
        registration,
        failed,
        commit=commit,
    )
    for index in range(attempt_count):
        mutated = copy.deepcopy(failed)
        mutated["attempts"][index]["cleanup"].update(
            {"passes": False, "removed": []}
        )
        _p8v3_preparation_semantics_reject_receipt_with_both_consumers(
            registration,
            mutated,
            commit=commit,
        )


def _p8v4_semantic_closure_prepare_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, list[tuple[Path, bytes, str, str]]]:
    authority = tmp_path / "authority"
    execution_root = tmp_path / "execution"
    authority.mkdir()
    execution_root.mkdir()
    receipt = execution_root / "preparation-receipt.json"
    registration = SimpleNamespace(content_sha256="b" * 64)
    published: list[tuple[Path, bytes, str, str]] = []
    monkeypatch.setattr(preparation, "_AUTHORITY_ROOT", str(authority.resolve()))
    monkeypatch.setattr(preparation, "_validate_preparation_root", lambda *_a: None)
    monkeypatch.setattr(preparation, "_derive_open_freeze", lambda *_a: "a" * 40)
    monkeypatch.setattr(preparation, "_raw_tree_audit", lambda *_a, **_k: object())
    monkeypatch.setattr(preparation, "_load_registration", lambda *_a, **_k: registration)
    monkeypatch.setattr(preparation, "_validate_prepare_invocation", lambda *_a: None)
    monkeypatch.setattr(preparation, "_validate_linux_host", lambda *_a: None)
    monkeypatch.setattr(
        preparation,
        "_clone_receipt",
        lambda *_a, **_k: {"synthetic": "authority"},
    )
    monkeypatch.setattr(
        preparation,
        "_publish_bytes_exclusive",
        lambda path, raw, name, *, role: published.append((path, raw, name, role)),
    )
    args = SimpleNamespace(
        repository_root=authority,
        registration=Path("registration.json"),
        execution_root=execution_root,
        receipt=receipt,
    )
    return args, published


@pytest.mark.skipif(os.name != "posix", reason="Linux preparation producer contract")
def test_p8v4_semantic_closure_cleanup_failure_publishes_no_preparation_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, published = _p8v4_semantic_closure_prepare_harness(tmp_path, monkeypatch)
    failure = preparation._AttemptOutcome(
        {
            "attempt_index": 1,
            "cleanup": {"passes": False},
        },
        None,
        None,
        False,
        "owned cleanup failed",
    )
    monkeypatch.setattr(preparation, "_prepare_attempt", lambda *_a, **_k: failure)
    with pytest.raises(
        preparation.ProtocolError,
        match="no canonical failed receipt",
    ):
        preparation._prepare(args)
    assert published == []
    assert not args.receipt.exists()


@pytest.mark.skipif(os.name != "posix", reason="Linux preparation producer contract")
def test_p8v4_semantic_closure_two_clean_failures_publish_canonical_failed_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, published = _p8v4_semantic_closure_prepare_harness(tmp_path, monkeypatch)

    def failed_attempt(
        _ledger: Any,
        _root: Path,
        attempt_index: int,
        *_args: Any,
    ) -> preparation._AttemptOutcome:
        source = str(args.execution_root / f".prepare-attempt-{attempt_index}")
        return preparation._AttemptOutcome(
            {
                "attempt_index": attempt_index,
                "process_a_stage": "clone_failed",
                "process_b_stage": "not_started",
                "cleanup": {
                    "owned_paths": [source],
                    "removed": [source],
                    "passes": True,
                },
                "promotion": {
                    "source_path": source,
                    "destination_path": str(args.execution_root / "processes"),
                    "source_device": 1,
                    "source_inode": attempt_index,
                    "passes": False,
                },
                "passes": False,
            },
            None,
            None,
            True,
            "clean failed attempt",
        )

    monkeypatch.setattr(preparation, "_prepare_attempt", failed_attempt)
    assert preparation._prepare(args) == 1
    assert len(published) == 1
    path, raw, name, role = published[0]
    receipt = preparation._parse_canonical_object(raw, "synthetic failed receipt")
    assert path == args.receipt and name == "preparation-receipt"
    assert role == "preparation_receipt"
    assert receipt["status"] == "failed"
    assert len(receipt["attempts"]) == 2
    assert receipt["process_a"] is None and receipt["process_b"] is None
    assert all(attempt["cleanup"]["passes"] is True for attempt in receipt["attempts"])
    assert not (args.execution_root / "processes").exists()


@pytest.mark.parametrize(
    ("failed_child", "expected_calls"),
    [
        ("arm", 1),
        ("process_a_runner", 2),
        ("process_a_validator", 3),
        ("process_b_runner", 4),
        ("process_b_validator", 5),
    ],
)
def test_p8v4_semantic_closure_outer_cleanup_failure_is_typed_and_stops_later_children(
    monkeypatch: pytest.MonkeyPatch,
    failed_child: str,
    expected_calls: int,
) -> None:
    child_order = [
        "arm",
        "process_a_runner",
        "process_a_validator",
        "process_b_runner",
        "process_b_validator",
    ]
    calls: list[str] = []

    def run_child_evidence(*_args: Any, **_kwargs: Any) -> lifecycle._ChildResult:
        child = child_order[len(calls)]
        calls.append(child)
        if child == failed_child:
            return lifecycle._ChildResult(
                True,
                7,
                False,
                False,
                "child_cleanup_failed",
            )
        return lifecycle._ChildResult(True, 0, False, None, "completed")

    monkeypatch.setattr(lifecycle, "_run_child_evidence", run_child_evidence)
    monkeypatch.setattr(lifecycle, "_preparation_command_environment", lambda: {})
    monkeypatch.setattr(lifecycle, "_validate_authority_config", lambda *_a: None)
    monkeypatch.setattr(lifecycle, "_remote_and_arm_stage", lambda **_k: None)
    monkeypatch.setattr(lifecycle, "_validation_is_valid", lambda *_a, **_k: True)
    monkeypatch.setattr(lifecycle, "_optional_raw", lambda *_a, **_k: b"payload")
    monkeypatch.setattr(lifecycle, "_plain_bytes", lambda *_a, **_k: b"payload")
    execution = {
        "arm_argv": ["arm"],
        "scientific_argv_template": [
            "runner",
            "<LABEL>",
            "<START_CLAIM>",
            "<PRIOR_VALIDATION_OR_NULL>",
            "<OUTPUT_PATH>",
        ],
        "payload_validator_argv_template": [
            "validator",
            "<LABEL>",
            "<START_CLAIM>",
            "<VALIDATOR_CLAIM>",
            "<VALIDATION_RECEIPT>",
            "<OUTPUT_PATH>",
        ],
    }
    with pytest.raises(lifecycle._LifecycleChildCleanupFailure) as captured:
        lifecycle._run_registered_lifecycle(
            authority=Path("/synthetic-authority"),
            registration={"content_sha256": "a" * 64},
            execution=execution,
            commit="b" * 40,
            driver_raw=b"driver",
            deadline=float("inf"),
        )
    assert captured.value.child == failed_child
    assert captured.value.result == lifecycle._ChildResult(
        True,
        7,
        False,
        False,
        "child_cleanup_failed",
    )
    assert calls == child_order[:expected_calls]


def test_p8v4_semantic_closure_typed_cleanup_failure_skips_finish_and_all_later_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = ["synthetic-lifecycle-driver"]
    execution = {"lifecycle_driver_argv": observed}
    registration = {"content_sha256": "a" * 64}
    result = lifecycle._ChildResult(
        True,
        None,
        True,
        False,
        "child_cleanup_failed",
    )
    failure = lifecycle._LifecycleChildCleanupFailure("arm", result)
    finish_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(lifecycle, "_derive_o8", lambda *_a: "b" * 40)
    monkeypatch.setattr(
        lifecycle,
        "_load_registration",
        lambda *_a: (registration, b"registration"),
    )
    monkeypatch.setattr(lifecycle, "_verify_own_source", lambda *_a: None)
    monkeypatch.setattr(lifecycle, "_execution", lambda *_a: execution)
    monkeypatch.setattr(lifecycle, "_command_hash", lambda *_a: "c" * 64)
    monkeypatch.setattr(
        lifecycle,
        "_validate_windows_claim",
        lambda *_a, **_k: ({}, b"windows-claim"),
    )
    monkeypatch.setattr(
        lifecycle,
        "_acquire_driver_claim",
        lambda **_k: ({}, b"driver-claim"),
    )
    monkeypatch.setattr(
        lifecycle,
        "_require_registered_execution",
        lambda *_a, **_k: execution,
    )
    monkeypatch.setattr(lifecycle, "_result_transaction", lambda *_a: {})
    monkeypatch.setattr(
        lifecycle,
        "_process_commands",
        lambda *_a: (["a"], ["av"], ["b"], ["bv"]),
    )
    monkeypatch.setattr(
        lifecycle,
        "_run_registered_lifecycle",
        lambda **_k: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        lifecycle,
        "_finish_lifecycle",
        lambda **kwargs: finish_calls.append(kwargs) or 0,
    )
    with pytest.raises(lifecycle._LifecycleChildCleanupFailure) as captured:
        lifecycle._execute_lifecycle(
            authority=Path("/synthetic-authority"),
            registration_relative="registration.json",
            observed_argv=observed,
            deadline=float("inf"),
        )
    assert captured.value is failure
    assert captured.value.result.child_cleanup_passes is False
    assert finish_calls == []


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("duration_milliseconds", [120_000, 120_001, 10**18])
def test_p8v4_overall_deadline_parity_accepts_boundary_and_unclamped_overrun(
    module: Any,
    duration_milliseconds: int,
) -> None:
    attempt = _p8v4_windows_attempt(
        module,
        "overall_deadline",
        timed_out=True,
        cleanup=True,
        exit_code=124,
    )
    attempt["duration_milliseconds"] = duration_milliseconds
    assert module._validate_attempt(attempt, 1, b"expected") == (
        "overall_deadline",
        duration_milliseconds,
    )


@pytest.mark.parametrize("module", [remote_verifier, supervisor])
@pytest.mark.parametrize("duration_milliseconds", [-1, 0, 119_999])
def test_p8v4_overall_deadline_parity_rejects_subthreshold_duration(
    module: Any,
    duration_milliseconds: int,
) -> None:
    attempt = _p8v4_windows_attempt(
        module,
        "overall_deadline",
        timed_out=True,
        cleanup=True,
        exit_code=124,
    )
    attempt["duration_milliseconds"] = duration_milliseconds
    with pytest.raises(module._ProtocolFailure):
        module._validate_attempt(attempt, 1, b"expected")


@pytest.mark.parametrize("duration_milliseconds", [120_000, 120_001, 10**18])
def test_p8v4_remaining_parity_all_remote_validators_accept_unclamped_overall_duration(
    duration_milliseconds: int,
) -> None:
    attempt = _p8v4_lifecycle_remote_attempt(
        "overall_deadline",
        exit_code=124,
        timed_out=True,
        cleanup=True,
        duration=duration_milliseconds,
    )
    observed = {
        remote_verifier._validate_attempt(attempt, 1, b"expected"),
        supervisor._validate_attempt(attempt, 1, b"expected"),
        preparation._validate_remote_attempt(attempt, 1, b"expected"),
        finalizer._validate_remote_attempt(
            attempt,
            index=1,
            expected_stdout=b"expected",
        ),
        lifecycle._validate_embedded_remote_attempt(
            attempt,
            index=1,
            expected_stdout=b"expected",
        ),
    }
    assert observed == {("overall_deadline", duration_milliseconds)}


@pytest.mark.parametrize("duration_milliseconds", [-1, 0, 119_999])
def test_p8v4_remaining_parity_all_remote_validators_reject_short_overall_duration(
    duration_milliseconds: int,
) -> None:
    attempt = _p8v4_lifecycle_remote_attempt(
        "overall_deadline",
        exit_code=124,
        timed_out=True,
        cleanup=True,
        duration=duration_milliseconds,
    )
    with pytest.raises(remote_verifier._ProtocolFailure):
        remote_verifier._validate_attempt(attempt, 1, b"expected")
    with pytest.raises(supervisor._ProtocolFailure):
        supervisor._validate_attempt(attempt, 1, b"expected")
    with pytest.raises(preparation.ProtocolError):
        preparation._validate_remote_attempt(attempt, 1, b"expected")
    with pytest.raises(finalizer._FinalizationError):
        finalizer._validate_remote_attempt(
            attempt,
            index=1,
            expected_stdout=b"expected",
        )
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._validate_embedded_remote_attempt(
            attempt,
            index=1,
            expected_stdout=b"expected",
        )


def _p8v4_remaining_parity_pack_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repository"
    pack = root / ".git" / "objects" / "pack"
    pack.mkdir(parents=True)
    for directory in (root / ".git", root / ".git" / "objects", pack):
        directory.chmod(0o700)
    return root, pack


@pytest.mark.skipif(os.name != "posix", reason="descriptor-safe Git pack gate is POSIX-only")
@pytest.mark.parametrize("module", [preparation, lifecycle, finalizer])
@pytest.mark.parametrize("entry_kind", ["regular", "directory", "symlink", "fifo"])
def test_p8v4_remaining_parity_promisor_entry_of_every_tested_type_is_rejected(
    module: Any,
    entry_kind: str,
    tmp_path: Path,
) -> None:
    root, pack = _p8v4_remaining_parity_pack_root(tmp_path)
    entry = pack / "synthetic.promisor"
    if entry_kind == "regular":
        entry.write_bytes(b"promisor\n")
    elif entry_kind == "directory":
        entry.mkdir()
    elif entry_kind == "symlink":
        entry.symlink_to("missing-target")
    else:
        os.mkfifo(entry)
    with pytest.raises(RuntimeError, match="promisor"):
        module._validate_object_pack_sources(root)


@pytest.mark.skipif(os.name != "posix", reason="descriptor-safe Git pack gate is POSIX-only")
@pytest.mark.parametrize("module", [preparation, lifecycle, finalizer])
@pytest.mark.parametrize(
    "relative",
    [Path(".git"), Path(".git/objects"), Path(".git/objects/pack")],
)
def test_p8v4_remaining_parity_pack_ancestry_is_opened_without_following_links(
    module: Any,
    relative: Path,
    tmp_path: Path,
) -> None:
    root, _pack = _p8v4_remaining_parity_pack_root(tmp_path)
    component = root / relative
    moved = component.with_name(f"{component.name}-real")
    component.rename(moved)
    component.symlink_to(moved.name, target_is_directory=True)
    with pytest.raises(RuntimeError, match="no-follow"):
        module._validate_object_pack_sources(root)


@pytest.mark.skipif(os.name != "posix", reason="descriptor-safe Git pack gate is POSIX-only")
@pytest.mark.parametrize("module", [preparation, lifecycle, finalizer])
@pytest.mark.parametrize(
    "relative",
    [Path(".git"), Path(".git/objects"), Path(".git/objects/pack")],
)
def test_p8v4_remaining_parity_pack_ancestry_must_be_owner_controlled(
    module: Any,
    relative: Path,
    tmp_path: Path,
) -> None:
    root, _pack = _p8v4_remaining_parity_pack_root(tmp_path)
    (root / relative).chmod(0o777)
    with pytest.raises(RuntimeError, match="owner-controlled"):
        module._validate_object_pack_sources(root)


@pytest.mark.skipif(os.name != "posix", reason="descriptor-safe Git pack gate is POSIX-only")
@pytest.mark.parametrize(
    ("module", "gate"),
    [
        (preparation, "preparation_policy"),
        (lifecycle, "lifecycle_derive"),
        (lifecycle, "lifecycle_config"),
        (finalizer, "finalizer_controls"),
        (finalizer, "finalizer_repository"),
        (finalizer, "finalizer_raw_audit"),
    ],
)
def test_p8v4_remaining_parity_every_live_identity_gate_rejects_promisor_before_git(
    module: Any,
    gate: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, pack = _p8v4_remaining_parity_pack_root(tmp_path)
    (pack / "synthetic.promisor").write_bytes(b"promisor\n")
    git_calls: list[tuple[Any, ...]] = []

    def forbidden_git(*args: Any, **_kwargs: Any) -> bytes:
        git_calls.append(args)
        raise AssertionError("Git evidence ran before the object-pack gate")

    monkeypatch.setattr(module, "_git", forbidden_git)
    if gate == "preparation_policy":
        with pytest.raises(preparation.ProtocolError, match="promisor"):
            preparation._validate_git_repository_policy(object(), root)  # type: ignore[arg-type]
    elif gate == "lifecycle_derive":
        with pytest.raises(lifecycle.LifecycleError, match="promisor"):
            lifecycle._derive_o8(root, {})
    elif gate == "lifecycle_config":
        with pytest.raises(lifecycle.LifecycleError, match="promisor"):
            lifecycle._validate_authority_config(root, {})
    elif gate == "finalizer_controls":
        assert finalizer._git_repository_controls(root) is False
    elif gate == "finalizer_repository":
        with pytest.raises(finalizer._FinalizationError, match="promisor"):
            finalizer._repository_and_registration(root)
    else:
        assert finalizer._authority_raw_audit(root, "a" * 40, b"registration") is False
    assert git_calls == []


@pytest.mark.skipif(os.name != "posix", reason="descriptor-safe Git pack gate is POSIX-only")
def test_p8v4_remaining_parity_pack_gate_matches_all_six_linux_consumers(
    tmp_path: Path,
) -> None:
    modules = (
        reconstruction,
        runner,
        validator,
        preparation,
        lifecycle,
        finalizer,
    )
    for index, module in enumerate(modules):
        root, pack = _p8v4_remaining_parity_pack_root(tmp_path / str(index))
        module._validate_object_pack_sources(root)
        (pack / "synthetic.promisor").write_bytes(b"promisor\n")
        with pytest.raises(RuntimeError, match="promisor"):
            module._validate_object_pack_sources(root)
