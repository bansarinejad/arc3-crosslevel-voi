# ruff: noqa: E501
"""Non-scientific registration tests for the action-QBC v8 open freeze."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.build_action_qbc_v8_open_registration as producer
import scripts.execute_action_qbc_v8_open_lifecycle as lifecycle
import scripts.finalize_action_qbc_v8_open_diagnostic as finalizer
import scripts.prepare_action_qbc_v8_open as preparation
import scripts.reconstruct_action_qbc_v8_open_registration as reconstruction
import scripts.run_action_qbc_v8_open_diagnostic as runner
import scripts.supervise_action_qbc_v8_remote_tag as supervisor
import scripts.validate_action_qbc_v8_open_payload as payload_validator
import scripts.verify_action_qbc_v8_remote_tag as remote_verifier

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / reconstruction.PREREGISTRATION_DOCUMENT


def _synthetic_finalizer_manifest() -> list[dict[str, object]]:
    return [
        {
            "mode": "100644",
            "path": "scripts/finalize_action_qbc_v8_open_diagnostic.py",
            "git_blob_sha1": "1" * 40,
            "sha256": "2" * 64,
            "byte_count": 123,
        }
    ]


def _candidate_registration_from_current_sources() -> dict[str, object]:
    """Rebuild the exact candidate registration without staging or writing it."""

    preregistration_entries = reconstruction._tree_entries(
        ROOT, reconstruction.PREREGISTRATION_COMMIT
    )
    preregistration_manifest, _ = reconstruction._manifest_and_blobs(
        ROOT, preregistration_entries
    )
    added_blobs = {
        relative: (ROOT / relative).read_bytes()
        for relative in reconstruction.NON_REGISTRATION_ADDITIONS
    }
    added_manifest = []
    for relative in sorted(added_blobs, key=lambda value: value.encode("utf-8")):
        raw = added_blobs[relative]
        added_manifest.append(
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
    return reconstruction._assemble_registration(
        preregistration_manifest,
        added_manifest,
        added_blobs,
        reconstruction._verify_frozen_anchors(ROOT),
    )


def _git(root: Path, *argv: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *argv], check=False, capture_output=True
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    return completed.stdout


def _close_local_git_configuration(root: Path) -> None:
    remotes = _git(root, "remote").decode("utf-8").splitlines()
    if "origin" in remotes:
        _git(root, "remote", "remove", "origin")
    for key in ("user.name", "user.email"):
        completed = subprocess.run(
            ["git", "-C", str(root), "config", "--local", "--unset-all", key],
            check=False,
            capture_output=True,
        )
        assert completed.returncode in {0, 5}, completed.stderr.decode(errors="replace")
    for key, value in (
        ("core.autocrlf", "false"),
        ("core.eol", "lf"),
        ("core.safecrlf", "true"),
    ):
        _git(root, "config", "--local", key, value)


@pytest.mark.skipif(os.name != "posix", reason="Linux no-follow Git source gate")
@pytest.mark.parametrize(
    ("module", "gate_name", "error_type"),
    (
        (
            reconstruction,
            "_validate_git_isolation",
            reconstruction.ReconstructionError,
        ),
        (runner, "_validate_local_git_sources", runner._AdministrativeFailure),
        (
            payload_validator,
            "_validate_local_git_sources",
            payload_validator._AdministrativeFailure,
        ),
    ),
    ids=("reconstructor", "runner", "payload-validator"),
)
def test_linux_live_git_source_gates_reject_every_promisor_sidecar_before_git_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    gate_name: str,
    error_type: type[Exception],
) -> None:
    root = tmp_path / module.__name__.rsplit(".", 1)[-1]
    pack = root / ".git/objects/pack"
    pack.mkdir(parents=True)
    (root / ".git/hooks").mkdir()
    open_commit = "a" * 40
    expected_config = {
        "core.repositoryformatversion": "0",
        "core.filemode": "true",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "core.autocrlf": "false",
        "core.eol": "lf",
        "core.safecrlf": "true",
    }
    calls: list[tuple[str, ...]] = []

    def git_stub(_root: Path, *arguments: str, **_kwargs: object) -> bytes:
        calls.append(arguments)
        if arguments == (
            "cat-file",
            "-t",
            f"refs/tags/{reconstruction.OPEN_FREEZE_TAG}",
        ):
            return b"commit\n"
        if arguments in {
            ("rev-parse", f"refs/tags/{reconstruction.OPEN_FREEZE_TAG}"),
            ("rev-parse", "HEAD"),
        }:
            return f"{open_commit}\n".encode("ascii")
        if arguments == ("config", "--local", "--name-only", "--null", "--list"):
            return b"".join(f"{key}\0".encode("ascii") for key in expected_config)
        if (
            len(arguments) == 5
            and arguments[:4] == ("config", "--local", "--null", "--get-all")
        ):
            return f"{expected_config[arguments[4]]}\0".encode("ascii")
        if arguments == ("config", "--local", "--null", "--list"):
            return b"".join(
                f"{key}\n{value}\0".encode("ascii")
                for key, value in expected_config.items()
            )
        if arguments in {
            ("for-each-ref", "--format=%(refname)", "refs/replace"),
            ("for-each-ref", "--format=%(refname)", "refs/replace/"),
        }:
            return b""
        raise AssertionError(arguments)

    monkeypatch.setattr(module, "_git", git_stub)
    gate = getattr(module, gate_name)

    if module is reconstruction:
        gate(root, open_commit)
    else:
        gate(root)
    assert calls

    for sidecar_kind in ("plain", "symlink", "directory"):
        calls.clear()
        sidecar = pack / f"synthetic-{sidecar_kind}.promisor"
        if sidecar_kind == "plain":
            sidecar.write_bytes(b"promisor\n")
        elif sidecar_kind == "symlink":
            sidecar.symlink_to("missing-promisor-target")
        else:
            sidecar.mkdir()
        with pytest.raises(error_type, match="promisor"):
            if module is reconstruction:
                gate(root, open_commit)
            else:
                gate(root)
        assert calls == []
        if sidecar_kind == "directory":
            sidecar.rmdir()
        else:
            sidecar.unlink()

    pack.rename(pack.with_name("pack-real"))
    pack.symlink_to("pack-real", target_is_directory=True)
    calls.clear()
    with pytest.raises(error_type, match="no-follow"):
        if module is reconstruction:
            gate(root, open_commit)
        else:
            gate(root)
    assert calls == []


def test_canonical_json_is_ascii_compact_sorted_and_has_no_lf() -> None:
    value = {"z": [1, True, None, "\N{SNOWMAN}"], "a": {"x": 1e-12}}
    raw = reconstruction.canonical_json_bytes(value)
    assert raw == producer.canonical_json_bytes(value)
    assert raw == b'{"a":{"x":1e-12},"z":[1,true,null,"\\u2603"]}'
    assert not raw.endswith(b"\n")
    assert reconstruction.canonical_sha256(value) == hashlib.sha256(raw).hexdigest()


@pytest.mark.skipif(os.name != "posix", reason="Linux dirfd registration publication")
def test_registration_publication_is_exclusive_dirfd_bound_and_round_trips(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    (root / "artifacts").mkdir(parents=True)
    producer._exclusive_write(root, producer.OUTPUT_PATH, b"{}")
    destination = root / producer.OUTPUT_PATH
    assert destination.read_bytes() == b"{}"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        producer._exclusive_write(root, producer.OUTPUT_PATH, b"{}")

    unsafe_root = tmp_path / "unsafe"
    unsafe_root.mkdir()
    (unsafe_root / "artifacts").symlink_to(root / "artifacts", target_is_directory=True)
    with pytest.raises(OSError):
        producer._exclusive_write(unsafe_root, producer.OUTPUT_PATH, b"{}")


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{ "x":1}',
        b'{"x":1}\n', b'[]', b'\xff',
    ],
)
def test_strict_parser_rejects_ambiguous_or_noncanonical_json(raw: bytes) -> None:
    with pytest.raises(reconstruction.ReconstructionError):
        reconstruction.strict_object(raw)


def test_reconstructor_import_boundary_is_standard_library_only() -> None:
    path = ROOT / "scripts/reconstruct_action_qbc_v8_open_registration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    permitted = {
        "__future__", "argparse", "base64", "csv", "email", "hashlib", "io", "json",
        "os", "platform", "re", "stat", "subprocess", "sys", "collections", "pathlib",
        "typing",
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
    assert not any(name.startswith("arc3_voi") for name in imports)


def test_exact_frozen_identity_and_allowlist_constants() -> None:
    assert reconstruction.PREREGISTRATION_COMMIT == "e0bff9ffc185196cafa938c8f7c9a7186366258b"
    assert reconstruction.PREREGISTRATION_DOCUMENT_BLOB == "29c991b7e23209f2c38d5e9a11a15bca51753d8e"
    assert reconstruction.PREREGISTRATION_DOCUMENT_SHA256 == "31d6a04b113e5f18621c3b27af69d9e7d3a19289047673719ccd149d33b5b7b1"
    assert reconstruction.PREREGISTRATION_DOCUMENT_BYTE_COUNT == 33_215
    assert reconstruction.PREREGISTRATION_V3_TAG == "prereg-action-qbc-v8-open-bounded-remote-verification-v3"
    assert reconstruction.PREREGISTRATION_V3_COMMIT == "996ab2bb5a24143a110673977f63e7d111cf2060"
    assert reconstruction.PREREGISTRATION_V3_DOCUMENT_BLOB == "9f014e243a6bfe4ea35636a5de0d9bde598d4130"
    assert reconstruction.PREREGISTRATION_V3_DOCUMENT_SHA256 == "b2dafb5d41ab27a63f516c102f295395f32e825a5f66a90bd5fa95dbd414dbe9"
    assert reconstruction.PREREGISTRATION_V3_DOCUMENT_BYTE_COUNT == 58_656
    assert reconstruction.PREREGISTRATION_V2_TAG == "prereg-action-qbc-v8-open-bounded-remote-verification-v2"
    assert reconstruction.PREREGISTRATION_V2_COMMIT == "91c5ba1862fc7701ed2276ddd64b99fdb8b7ad1d"
    assert reconstruction.PREREGISTRATION_V2_DOCUMENT_BLOB == "b3a639da07a92672adfd4976861a58608702a7f3"
    assert reconstruction.PREREGISTRATION_V2_DOCUMENT_SHA256 == "f5c3c7be6221cdefc789d73f140a24b289a4edc849d48c1fb9249bc258308344"
    assert reconstruction.PREREGISTRATION_V2_DOCUMENT_BYTE_COUNT == 92_798
    assert reconstruction.PREREGISTRATION_V1_TAG == "prereg-action-qbc-v8-open-bounded-remote-verification-v1"
    assert reconstruction.PREREGISTRATION_V1_COMMIT == "ebf6031a284ecbffb53ba1582124b7e4c9eb3e56"
    assert reconstruction.PREREGISTRATION_V1_DOCUMENT_BLOB == "9d5f00ea4fdb4ca6ff3cdb8c51ba0105efb1e046"
    assert reconstruction.PREREGISTRATION_V1_DOCUMENT_SHA256 == "2e0ad4415d7f230f12f48db01aae9210797aa1da7f3a4ace6723e81be7bbb254"
    assert reconstruction.R7_COMMIT == "6f918e098a9ea97cadbb377027a8eb5caeb9589b"
    assert reconstruction.O7_COMMIT == "851fb6dadc851d17ba9540165f48570ee4203ded"
    assert len(reconstruction.NON_REGISTRATION_ADDITIONS) == 14
    assert len(reconstruction.ALL_ADDITIONS) == 15
    assert reconstruction.REGISTRATION_PATH not in reconstruction.NON_REGISTRATION_ADDITIONS
    assert tuple(sorted(reconstruction.ALL_ADDITIONS)) == reconstruction.ALL_ADDITIONS


def test_preregistration_and_v7_git_object_anchors_are_exact() -> None:
    assert _git(ROOT, "cat-file", "-t", reconstruction.PREREGISTRATION_V1_TAG).strip() == b"commit"
    assert _git(ROOT, "rev-parse", reconstruction.PREREGISTRATION_V1_TAG).decode().strip() == reconstruction.PREREGISTRATION_V1_COMMIT
    assert _git(ROOT, "cat-file", "-t", reconstruction.PREREGISTRATION_V2_TAG).strip() == b"commit"
    assert _git(ROOT, "rev-parse", reconstruction.PREREGISTRATION_V2_TAG).decode().strip() == reconstruction.PREREGISTRATION_V2_COMMIT
    assert _git(ROOT, "cat-file", "-t", reconstruction.PREREGISTRATION_V3_TAG).strip() == b"commit"
    assert _git(ROOT, "rev-parse", reconstruction.PREREGISTRATION_V3_TAG).decode().strip() == reconstruction.PREREGISTRATION_V3_COMMIT
    assert _git(ROOT, "cat-file", "-t", reconstruction.PREREGISTRATION_TAG).strip() == b"commit"
    assert _git(ROOT, "rev-parse", reconstruction.PREREGISTRATION_TAG).decode().strip() == reconstruction.PREREGISTRATION_COMMIT
    assert _git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        reconstruction.R7_COMMIT,
    ) == f"{reconstruction.R7_COMMIT} {reconstruction.O7_COMMIT}\n".encode("ascii")
    assert _git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        reconstruction.PREREGISTRATION_V1_COMMIT,
    ) == (
        f"{reconstruction.PREREGISTRATION_V1_COMMIT} "
        f"{reconstruction.R7_COMMIT}\n"
    ).encode("ascii")
    assert _git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        reconstruction.PREREGISTRATION_V2_COMMIT,
    ) == (
        f"{reconstruction.PREREGISTRATION_V2_COMMIT} "
        f"{reconstruction.PREREGISTRATION_V1_COMMIT}\n"
    ).encode("ascii")
    assert _git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        reconstruction.PREREGISTRATION_V3_COMMIT,
    ) == (
        f"{reconstruction.PREREGISTRATION_V3_COMMIT} "
        f"{reconstruction.PREREGISTRATION_V2_COMMIT}\n"
    ).encode("ascii")
    assert _git(
        ROOT,
        "rev-list",
        "--parents",
        "-n",
        "1",
        reconstruction.PREREGISTRATION_COMMIT,
    ) == (
        f"{reconstruction.PREREGISTRATION_COMMIT} "
        f"{reconstruction.PREREGISTRATION_V3_COMMIT}\n"
    ).encode("ascii")
    old_document = reconstruction.PREREGISTRATION_V2_DOCUMENT.encode("utf-8")
    v3_document = reconstruction.PREREGISTRATION_V3_DOCUMENT.encode("utf-8")
    document = reconstruction.PREREGISTRATION_DOCUMENT.encode("utf-8")
    assert _git(
        ROOT,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        reconstruction.R7_COMMIT,
        reconstruction.PREREGISTRATION_V1_COMMIT,
    ) == b"A\0" + old_document + b"\0"
    assert _git(
        ROOT,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        reconstruction.PREREGISTRATION_V1_COMMIT,
        reconstruction.PREREGISTRATION_V2_COMMIT,
    ) == b"M\0" + old_document + b"\0"
    assert _git(
        ROOT,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        reconstruction.PREREGISTRATION_V2_COMMIT,
        reconstruction.PREREGISTRATION_V3_COMMIT,
    ) == b"A\0" + v3_document + b"\0"
    assert _git(
        ROOT,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        reconstruction.PREREGISTRATION_V3_COMMIT,
        reconstruction.PREREGISTRATION_COMMIT,
    ) == b"A\0" + document + b"\0"
    v1_entry, v1_raw = reconstruction._blob_at(
        ROOT,
        reconstruction.PREREGISTRATION_V1_COMMIT,
        reconstruction.PREREGISTRATION_V1_DOCUMENT,
    )
    assert v1_entry["git_blob_sha1"] == reconstruction.PREREGISTRATION_V1_DOCUMENT_BLOB
    assert hashlib.sha256(v1_raw).hexdigest() == reconstruction.PREREGISTRATION_V1_DOCUMENT_SHA256
    v2_entry, v2_raw = reconstruction._blob_at(
        ROOT,
        reconstruction.PREREGISTRATION_V2_COMMIT,
        reconstruction.PREREGISTRATION_V2_DOCUMENT,
    )
    assert v2_entry["git_blob_sha1"] == reconstruction.PREREGISTRATION_V2_DOCUMENT_BLOB
    assert hashlib.sha256(v2_raw).hexdigest() == reconstruction.PREREGISTRATION_V2_DOCUMENT_SHA256
    v3_entry, v3_raw = reconstruction._blob_at(
        ROOT,
        reconstruction.PREREGISTRATION_V3_COMMIT,
        reconstruction.PREREGISTRATION_V3_DOCUMENT,
    )
    assert v3_entry["git_blob_sha1"] == reconstruction.PREREGISTRATION_V3_DOCUMENT_BLOB
    assert hashlib.sha256(v3_raw).hexdigest() == reconstruction.PREREGISTRATION_V3_DOCUMENT_SHA256
    entry, raw = reconstruction._blob_at(
        ROOT, reconstruction.PREREGISTRATION_COMMIT, reconstruction.PREREGISTRATION_DOCUMENT
    )
    assert entry["git_blob_sha1"] == reconstruction.PREREGISTRATION_DOCUMENT_BLOB
    assert entry["sha256"] == reconstruction.PREREGISTRATION_DOCUMENT_SHA256
    assert len(raw) == reconstruction.PREREGISTRATION_DOCUMENT_BYTE_COUNT
    assert raw == AMENDMENT.read_bytes()
    anchors = reconstruction._verify_frozen_anchors(ROOT)
    assert anchors["v7_registration"]["content_sha256"] == reconstruction.V7_REGISTRATION_CONTENT_SHA256
    assert anchors["v7_audit_entry"]["git_blob_sha1"] == reconstruction.V7_AUDIT_BLOB
    assert anchors["v7_reference_entry"]["git_blob_sha1"] == reconstruction.V7_REFERENCE_BLOB


def test_index_manifest_uses_staged_blob_under_crlf_worktree_materialization(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "test")
    _git(repository, "config", "user.email", "test@example.invalid")
    (repository / ".gitattributes").write_text("*.txt text eol=lf\n", encoding="ascii")
    tracked = repository / "sample.txt"
    tracked.write_bytes(b"alpha\nbeta\n")
    _git(repository, "add", ".gitattributes", "sample.txt")
    tracked.write_bytes(b"alpha\r\nbeta\r\n")
    entries = reconstruction._index_entries(repository)
    manifest, blobs = reconstruction._manifest_for_paths(repository, entries, ("sample.txt",))
    assert blobs["sample.txt"] == b"alpha\nbeta\n"
    assert manifest == [
        {
            "mode": "100644", "path": "sample.txt",
            "git_blob_sha1": hashlib.sha1(b"blob 11\0alpha\nbeta\n", usedforsecurity=False).hexdigest(),
            "sha256": hashlib.sha256(b"alpha\nbeta\n").hexdigest(), "byte_count": 11,
        }
    ]


def test_audit_replacement_table_and_generated_bytes_are_exact() -> None:
    _entry, source = reconstruction._blob_at(
        ROOT, reconstruction.O7_COMMIT, reconstruction.V7_AUDIT_PATH
    )
    transformed = source
    assert [row[0] for row in reconstruction.AUDIT_REPLACEMENTS] == [1] * 10 + [4, 1]
    for expected_count, old, new in reconstruction.AUDIT_REPLACEMENTS:
        old_bytes, new_bytes = old.encode("ascii"), new.encode("ascii")
        assert transformed.count(old_bytes) == expected_count
        transformed = transformed.replace(old_bytes, new_bytes)
    assert len(transformed) == 180230
    assert hashlib.sha256(transformed).hexdigest() == "130dcc271799f035b571e30cc41304c2c3046ddf866eb80b3bbe4b0428c21444"
    assert hashlib.sha1(
        b"blob " + str(len(transformed)).encode() + b"\0" + transformed,
        usedforsecurity=False,
    ).hexdigest() == "c98297e729c27d6ff6ef866280a311cab7585a50"


def test_execution_contract_has_exact_keys_commands_hashes_and_remote_policy() -> None:
    execution = reconstruction._execution_contract(_synthetic_finalizer_manifest())
    assert len(execution) == 70
    assert set(execution["argv_hashes"]) == {
        "arm", "bootstrap", "environment_build", "finalizer", "lifecycle_driver",
        "linux_host_launcher", "payload_validator", "post_preparation_validation",
        "preflight", "preparation", "producer", "reconstructor", "remote_supervisor",
        "remote_verifier", "result_publisher", "result_ref_transaction", "scientific", "tests",
    }
    preimages = {
        "arm": execution["arm_argv"], "bootstrap": execution["bootstrap_steps"],
        "environment_build": execution["environment_build_argv"],
        "finalizer": execution["finalizer_argv_template"],
        "lifecycle_driver": execution["lifecycle_driver_argv"],
        "linux_host_launcher": execution["linux_host_launcher"],
        "payload_validator": execution["payload_validator_argv_template"],
        "post_preparation_validation": execution["post_preparation_validation_argv"],
        "preflight": execution["preflight_argvs"], "preparation": execution["preparation_argv"],
        "producer": execution["producer_argv"], "reconstructor": execution["reconstructor_argv"],
        "remote_supervisor": execution["remote_supervisor_argv"],
        "remote_verifier": execution["remote_verifier_argv"],
        "result_publisher": execution["result_publisher_argv"],
        "result_ref_transaction": execution["result_ref_transaction"],
        "scientific": execution["scientific_argv_template"], "tests": execution["test_argvs"],
    }
    assert execution["argv_hashes"] == {
        name: reconstruction.canonical_sha256(value) for name, value in preimages.items()
    }
    policy = execution["remote_policy"]
    assert set(policy) == {
        "max_attempts", "attempt_timeout_seconds", "retry_delay_seconds",
        "overall_deadline_seconds", "verifier_child_deadline_seconds",
        "supervisor_deadline_seconds", "supervisor_receipt_reserve_seconds",
        "stdout_cap_bytes", "stderr_cap_bytes", "child_cleanup_timeout_seconds",
        "windows_job_kill_on_close", "git_child_cwd", "git_environment",
    }
    assert len(policy["git_environment"]) == 17
    assert policy["git_environment"]["GIT_CONFIG_COUNT"] == "0"
    assert policy["git_environment"]["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert policy["overall_deadline_seconds"] == 390
    assert policy["verifier_child_deadline_seconds"] == 430
    assert policy["supervisor_receipt_reserve_seconds"] == 20
    assert execution["preparation_verification_receipt_path"].endswith(
        "/preparation-verification.json"
    )
    assert execution["preparation_command_environment"] == (
        reconstruction.PREPARATION_COMMAND_ENVIRONMENT
    )
    assert execution["preparation_command_policy"] == reconstruction.PREPARATION_COMMAND_POLICY
    assert execution["preparation_command_policy"] == {
        "default_timeout_seconds": 60,
        "environment_timeout_seconds": 600,
        "term_grace_seconds": 5,
        "kill_grace_seconds": 5,
        "stdin_cap_bytes": 1_048_576,
        "stdout_cap_bytes": 134_217_728,
        "stderr_cap_bytes": 1_048_576,
    }
    assert set(execution["preparation_command_environment"]) == {
        "PATH", "HOME", "XDG_CONFIG_HOME", "LANG", "LC_ALL", "TZ",
        "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT",
        "GIT_NO_REPLACE_OBJECTS", "GIT_TERMINAL_PROMPT", "PYTHONHASHSEED",
        "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE", "UV_CACHE_DIR",
        "UV_NO_PROGRESS", "UV_PYTHON_DOWNLOADS",
    }
    verification_path = execution["preparation_verification_receipt_path"]
    assert execution["post_preparation_validation_argv"][-2:] == [
        "--verification-receipt", verification_path,
    ]
    for key in ("arm_argv", "lifecycle_driver_argv", "finalizer_argv_template"):
        argv = execution[key]
        prep_index = argv.index("--preparation-receipt")
        assert argv[prep_index + 2 : prep_index + 4] == [
            "--preparation-verification-receipt", verification_path,
        ]
    scientific = execution["scientific_argv_template"]
    registration_index = scientific.index("--registration")
    assert scientific[registration_index + 2 : registration_index + 4] == [
        "--preparation-verification-receipt", verification_path,
    ]
    for key in (
        "arm_argv", "scientific_argv_template", "payload_validator_argv_template",
        "finalizer_argv_template", "result_publisher_argv",
    ):
        assert "--foreground" not in execution[key]
    assert execution["result_publisher_argv"][:5] == [
        "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "600s", "/usr/bin/python3",
    ]
    assert execution["result_publisher_argv"][-2:] == ["--control-time-seconds", "570"]
    bootstrap = execution["bootstrap_steps"]
    checkout_index = next(i for i, argv in enumerate(bootstrap) if "checkout" in argv)
    assert bootstrap[checkout_index + 1] == [
        "/usr/bin/git", "--no-replace-objects", "-C", execution["authority_root"],
        "remote", "remove", "origin",
    ]
    for argv in bootstrap + execution["preflight_argvs"]:
        if argv and argv[0] == "/usr/bin/git":
            assert argv[1] == "--no-replace-objects"
    transaction = execution["result_ref_transaction"]
    for argv in transaction["git_plumbing_argvs"] + transaction["local_transfer_argvs"]:
        assert argv[:2] == ["/usr/bin/git", "--no-replace-objects"]
    for argv in transaction["windows_publication_argvs"]:
        assert argv[1:3] == ["--no-replace-objects", "--no-optional-locks"]
    windows_repository = execution["windows_repository_contract"]
    assert windows_repository == reconstruction.WINDOWS_REPOSITORY_CONTRACT
    assert len(windows_repository) == 15
    assert set(windows_repository) == {
        "active_hooks_allowed", "common_directory", "forbidden_admin_relative_paths",
        "forbidden_pack_suffixes", "forbidden_ref_prefixes", "git_config_byte_count",
        "git_config_sha256", "git_directory", "index_path", "info_exclude_byte_count",
        "info_exclude_sha256", "local_config", "plain_admin_relative_directories",
        "repository_ancestor_chain", "repository_root",
    }
    assert windows_repository["repository_ancestor_chain"] == [
        "D:\\",
        r"D:\kaggle competitions",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
    ]
    assert len(windows_repository["local_config"]) == 19
    assert execution["linux_platform"]["windows_host_launcher_identity"] == {
        "path": r"C:\Windows\System32\wsl.exe",
        "product_version": "10.0.26100.8737",
        "sha256": "7e9f5cee6d641481e5a942f0e08563bae9c17ee55f0aad888f9aa0be9a5d4757",
    }
    assert execution["producer_argv"] == [
        "uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B",
        "scripts/build_action_qbc_v8_open_registration.py", "--repository-root", ".",
        "--preregistration-tag", reconstruction.PREREGISTRATION_TAG,
        "--output", reconstruction.REGISTRATION_PATH,
    ]


def test_runner_rejects_every_windows_repository_contract_key_value_or_order_mutation() -> None:
    execution = reconstruction._execution_contract(_synthetic_finalizer_manifest())
    malformed: list[dict[str, object]] = []

    missing = json.loads(reconstruction.canonical_json_bytes(execution))
    del missing["windows_repository_contract"]["index_path"]
    malformed.append(missing)

    extra = json.loads(reconstruction.canonical_json_bytes(execution))
    extra["windows_repository_contract"]["unexpected"] = False
    malformed.append(extra)

    scalar = json.loads(reconstruction.canonical_json_bytes(execution))
    scalar["windows_repository_contract"]["git_config_byte_count"] = 847
    malformed.append(scalar)

    config = json.loads(reconstruction.canonical_json_bytes(execution))
    config["windows_repository_contract"]["local_config"]["core.bare"] = "true"
    malformed.append(config)

    array_order = json.loads(reconstruction.canonical_json_bytes(execution))
    array_order["windows_repository_contract"]["repository_ancestor_chain"].reverse()
    malformed.append(array_order)

    array_member = json.loads(reconstruction.canonical_json_bytes(execution))
    array_member["windows_repository_contract"]["forbidden_pack_suffixes"][0] = ".keep"
    malformed.append(array_member)

    for candidate in malformed:
        with pytest.raises(runner._AdministrativeFailure):
            runner._validate_execution_contract({"execution_contract": candidate})


def test_windows_reconstructor_git_uses_both_global_read_isolation_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    def fake_run(argv: tuple[str, ...], **_kwargs: object) -> SimpleNamespace:
        observed.extend(argv)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(reconstruction.os, "name", "nt")
    monkeypatch.setattr(reconstruction, "_git_executable", lambda: "frozen-git.exe")
    monkeypatch.setattr(reconstruction.subprocess, "run", fake_run)
    assert reconstruction._git(Path(r"D:\repository"), "status") == b""
    assert observed[:3] == [
        "frozen-git.exe",
        "--no-replace-objects",
        "--no-optional-locks",
    ]


def test_authority_ledger_binds_complete_r7_through_p8v4_lineage() -> None:
    authority = Path("/authority")
    identities = reconstruction._expected_authority_identities(
        authority,
        "a" * 40,
        [("tracked", "100644", "b" * 40, 1)],
    )
    argvs = [row["argv"] for row in identities]
    tag_positions = [
        argvs.index(
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(authority),
                "cat-file", "-t", f"refs/tags/{tag}",
            ]
        )
        for tag in (
            reconstruction.PREREGISTRATION_V1_TAG,
            reconstruction.PREREGISTRATION_V2_TAG,
            reconstruction.PREREGISTRATION_V3_TAG,
            reconstruction.PREREGISTRATION_TAG,
        )
    ]
    assert tag_positions == sorted(tag_positions)
    for parent, child in (
        (reconstruction.R7_COMMIT, reconstruction.PREREGISTRATION_V1_COMMIT),
        (
            reconstruction.PREREGISTRATION_V1_COMMIT,
            reconstruction.PREREGISTRATION_V2_COMMIT,
        ),
        (
            reconstruction.PREREGISTRATION_V2_COMMIT,
            reconstruction.PREREGISTRATION_V3_COMMIT,
        ),
        (
            reconstruction.PREREGISTRATION_V3_COMMIT,
            reconstruction.PREREGISTRATION_COMMIT,
        ),
    ):
        assert [
            "/usr/bin/git", "--no-replace-objects", "-C", str(authority), "diff",
            "--name-status", "--no-renames", "-z", parent, child,
        ] in argvs


def test_runbook_contains_every_registered_operator_argv_as_compact_json() -> None:
    execution = reconstruction._execution_contract(_synthetic_finalizer_manifest())
    transaction = execution["result_ref_transaction"]
    local_transfer = transaction["local_transfer_argvs"]
    windows_publication = transaction["windows_publication_argvs"]
    assert len(local_transfer) == 2
    assert len(windows_publication) == 3
    required_argvs = [
        *execution["bootstrap_steps"],
        execution["producer_argv"],
        execution["reconstructor_argv"],
        *execution["test_argvs"],
        execution["preparation_argv"],
        execution["post_preparation_validation_argv"],
        execution["remote_supervisor_argv"],
        execution["lifecycle_driver_argv"],
        execution["result_publisher_argv"],
        *local_transfer,
        *windows_publication,
    ]
    runbook = (ROOT / "docs/action_qbc_v8_open_diagnostic_runbook.md").read_text(
        encoding="utf-8"
    )
    assert reconstruction.PREREGISTRATION_COMMIT in runbook
    assert reconstruction.PREREGISTRATION_TAG in runbook
    assert reconstruction.PREREGISTRATION_DOCUMENT in runbook
    assert reconstruction.PREREGISTRATION_DOCUMENT_BLOB in runbook
    assert reconstruction.PREREGISTRATION_DOCUMENT_SHA256 in runbook
    assert str(reconstruction.PREREGISTRATION_DOCUMENT_BYTE_COUNT) in runbook
    for argv in required_argvs:
        compact = reconstruction.canonical_json_bytes(argv).decode("ascii")
        assert compact in runbook, compact


def test_runbook_closes_exact_pre_o8_operator_and_publication_contract() -> None:
    runbook = (ROOT / "docs/action_qbc_v8_open_diagnostic_runbook.md").read_text(
        encoding="utf-8"
    )
    section_one = runbook.split("## 1. Build and freeze O8", 1)[1].split(
        "## 2. Read-only host preflight", 1
    )[0]

    assert (
        "wsl.exe -d Ubuntu --cd "
        "'D:\\kaggle competitions\\arc3-crosslevel-voi'"
    ) in section_one
    assert "`/mnt/d/kaggle competitions/arc3-crosslevel-voi`" in section_one
    assert "PowerShell-native or Windows-native processes" in section_one
    assert "do not place an\ninner command in a PowerShell command string" in section_one

    pre_o8_environment = {
        "GIT_CONFIG_COUNT": "0",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": "/home/bansarinejad",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
        "UV_CACHE_DIR": "/home/bansarinejad/.cache/uv",
        "UV_NO_PROGRESS": "1",
        "UV_OFFLINE": "1",
        "UV_PROJECT_ENVIRONMENT": ".venv-wsl",
        "UV_PYTHON_DOWNLOADS": "never",
        "XDG_CONFIG_HOME": "/nonexistent",
    }
    assert len(pre_o8_environment) == 19
    assert pre_o8_environment != reconstruction.PREPARATION_COMMAND_ENVIRONMENT
    assert pre_o8_environment["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert "UV_OFFLINE" not in reconstruction.PREPARATION_COMMAND_ENVIRONMENT
    assert "UV_PROJECT_ENVIRONMENT" not in reconstruction.PREPARATION_COMMAND_ENVIRONMENT
    assert (
        reconstruction.canonical_json_bytes(pre_o8_environment).decode("ascii")
        in section_one
    )
    assert (
        "operational build/gate environment, not the registered seventeen-key\n"
        "`preparation_command_environment`"
    ) in section_one
    assert "The real DrvFS checkout must use\n`.venv-wsl`" in section_one
    assert "disposable ext4 rehearsal clone may use its own `.venv`" in section_one
    assert "neither rehearsal nor real\nO8 tree" in section_one
    assert "may depend on its bytes" in section_one
    assert "disposable ext4 rehearsal is populated from a raw DrvFS snapshot" in section_one
    assert "first copy the\nexact bytes" in section_one
    assert "record every source file's SHA-256 and byte count" in section_one
    assert (
        "Before `git add`, normalize\nevery one of the fourteen ordinary source files "
        "to filesystem mode `0644`"
    ) in section_one
    assert "cacheinfo mode `100644`" in section_one
    assert (
        "Reopen all\nfourteen files after normalization, recompute SHA-256 and byte count"
    ) in section_one
    assert "equality with the pre-normalization records" in section_one
    assert "mode `100644` for all fourteen staged entries" in section_one
    assert "mode normalization applies only to the disposable ext4 materialization" in section_one
    assert "authoritative DrvFS checkout: its raw source bytes remain untouched" in section_one
    assert (
        "real\nDrvFS index must independently report mode `100644` for each of the same "
        "fourteen paths"
    ) in section_one
    assert "not evidence for, or a repair of, the real index" in section_one

    launcher_prefix = [
        r"C:\Windows\System32\wsl.exe",
        "-d",
        "Ubuntu",
        "--cd",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
        "--",
        "/usr/bin/env",
        "-i",
        "GIT_CONFIG_COUNT=0",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_NO_REPLACE_OBJECTS=1",
        "GIT_TERMINAL_PROMPT=0",
        "HOME=/home/bansarinejad",
        "LANG=C",
        "LC_ALL=C",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONHASHSEED=0",
        "PYTHONNOUSERSITE=1",
        "TZ=UTC",
        "UV_CACHE_DIR=/home/bansarinejad/.cache/uv",
        "UV_NO_PROGRESS=1",
        "UV_OFFLINE=1",
        "UV_PROJECT_ENVIRONMENT=.venv-wsl",
        "UV_PYTHON_DOWNLOADS=never",
        "XDG_CONFIG_HOME=/nonexistent",
        "<INNER_ARGV...>",
    ]
    assert reconstruction.canonical_json_bytes(launcher_prefix).decode(
        "ascii"
    ) in section_one
    assert "array\nis not embedded as one string" in section_one

    expected_paths = (*reconstruction.NON_REGISTRATION_ADDITIONS, reconstruction.REGISTRATION_PATH)
    assert len(expected_paths) == 15
    for relative in expected_paths:
        assert section_one.count(f"\n{relative}\n") == 1, relative
    assert "all and only these exact fourteen\nnon-registration additions" in section_one
    assert "sole fifteenth addition" in section_one

    for required_wording in (
        "ordinary stage-zero entry",
        "unmerged stages",
        "split-index/link extensions",
        ".git/sharedindex.*",
        "sparse-index directory entries",
        "sparse-checkout state",
        "skip-worktree",
        "assume-unchanged",
        "nonordinary cache-entry flag",
    ):
        assert required_wording in section_one

    execution = reconstruction._execution_contract(_synthetic_finalizer_manifest())
    pre_o8_argvs = [
        execution["producer_argv"],
        execution["reconstructor_argv"],
        *execution["test_argvs"],
    ]
    assert len(pre_o8_argvs) == 5
    for argv in pre_o8_argvs:
        assert section_one.count(
            reconstruction.canonical_json_bytes(argv).decode("ascii")
        ) == 1
    assert "stop the one-shot freeze immediately" in section_one
    assert "regenerate the registration, rerun a failed array" in section_one
    assert "a partial or failed sequence is not O8" in section_one

    atomic_push = [
        r"C:\Users\User\anaconda3\Library\bin\git.exe",
        "--no-replace-objects",
        "--no-optional-locks",
        "-C",
        r"D:\kaggle competitions\arc3-crosslevel-voi",
        "push",
        "--atomic",
        "origin",
        "refs/heads/action-qbc-v8-prereg:refs/heads/action-qbc-v8-prereg",
        (
            "refs/tags/action-qbc-v8-open-diagnostic-freeze-v1:"
            "refs/tags/action-qbc-v8-open-diagnostic-freeze-v1"
        ),
    ]
    independent_https_check = [
        r"C:\Windows\System32\wsl.exe",
        "-d",
        "Ubuntu",
        "--cd",
        r"D:\kaggle competitions",
        "--",
        "/usr/bin/env",
        "-i",
        "GIT_CONFIG_COUNT=0",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_NO_REPLACE_OBJECTS=1",
        "GIT_TERMINAL_PROMPT=0",
        "HOME=/home/bansarinejad",
        "LANG=C",
        "LC_ALL=C",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "XDG_CONFIG_HOME=/nonexistent",
        "/usr/bin/git",
        "--no-replace-objects",
        "-c",
        "credential.interactive=never",
        "-c",
        "core.askPass=",
        "-c",
        "credential.helper=",
        "ls-remote",
        "--refs",
        "https://github.com/bansarinejad/arc3-crosslevel-voi.git",
        "refs/heads/action-qbc-v8-prereg",
        "refs/tags/action-qbc-v8-open-diagnostic-freeze-v1",
    ]
    for argv in (atomic_push, independent_https_check):
        assert reconstruction.canonical_json_bytes(argv).decode("ascii") in section_one
    assert "one non-force atomic push" in section_one
    assert "exact set must be the two requested\nrefs, each once" in section_one
    assert "Neither the atomic push nor this independent\nread-only check is a frozen scientific command" in section_one
    assert "authentication token, password, askpass program, or other secret" in section_one

    verify_open_freeze = (
        "/usr/bin/python3 -I -B "
        "scripts/reconstruct_action_qbc_v8_open_registration.py "
        "--repository-root . --registration "
        "artifacts/action_qbc_v8_open_registration.json --verify-open-freeze"
    )
    assert section_one.count("Do not run `--verify-open-freeze`") == 1
    assert runbook.count(verify_open_freeze) == 1
    assert runbook.index(verify_open_freeze) > runbook.index(
        "## 3. One-shot authority bootstrap"
    )


def test_exact_candidate_registration_is_accepted_by_every_contract_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registration = _candidate_registration_from_current_sources()
    registration_raw = reconstruction.canonical_json_bytes(registration)
    assert reconstruction.strict_object(registration_raw, "candidate registration") == registration

    execution_value = registration["execution_contract"]
    assert isinstance(execution_value, dict)
    execution = execution_value
    preparation._validate_execution_contract(execution)

    # The Windows programs consume the same canonical bytes and re-open their own
    # registered sources.  This remains useful under POSIX because all Windows paths
    # in the contract are strings and the temporary repository paths are portable.
    for relative in (supervisor._SUPERVISOR_SCRIPT, supervisor._VERIFIER_SCRIPT):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    registration_path = tmp_path / reconstruction.REGISTRATION_PATH
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.write_bytes(registration_raw)
    assert supervisor._load_registration(tmp_path).value == registration
    assert remote_verifier._load_registration(tmp_path, registration_path).value == registration

    # pathlib deliberately renders POSIX absolute paths with backslashes on native
    # Windows.  The remaining consumers are registered Linux processes and are
    # therefore exercised only where their actual path semantics exist.
    if os.name != "posix":
        return

    assert lifecycle._require_registered_execution(
        registration,
        execute_argv=execution["lifecycle_driver_argv"],
        publish_argv=execution["result_publisher_argv"],
    ) == execution
    assert finalizer._validate_execution_contract(registration) == execution

    def exercise_runner_contract(label: str) -> None:
        process = runner._PROCESS[label]
        template = execution["scientific_argv_template"]
        assert isinstance(template, list)
        full_argv = runner._substituted_scientific_argv(
            template, label=label, process=process
        )
        script_index = full_argv.index(runner._EXPECTED_SCRIPT)
        args = argparse.Namespace(
            repository_root=".",
            registration=runner._EXPECTED_REGISTRATION,
            preparation_verification_receipt=runner._PREPARATION_VERIFICATION_RECEIPT,
            arm_receipt=runner._ARM_RECEIPT,
            driver_claim=runner._DRIVER_CLAIM,
            label=label,
            start_claim=process["start_claim"],
            prior_validation_receipt=process["prior"],
            compute_deadline_seconds=runner._COMPUTE_SECONDS,
            wall_time_seconds=runner._WALL_SECONDS,
            output=process["output"],
        )
        root = Path(process["root"])

        def resolve(path: Path, *, strict: bool = False) -> Path:
            del strict
            return path if path.is_absolute() else root / path

        directory = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700,
            st_uid=os.getuid(),
        )
        with monkeypatch.context() as patch:
            patch.setattr(runner.sys, "flags", SimpleNamespace(isolated=1, dont_write_bytecode=1))
            patch.setattr(runner.sys, "argv", full_argv[script_index:])
            patch.setattr(runner.sys, "executable", str(root / ".venv/bin/python3"))
            patch.setattr(Path, "resolve", resolve)
            patch.setattr(Path, "stat", lambda *_args, **_kwargs: directory)
            patch.setattr(Path, "exists", lambda *_args, **_kwargs: False)
            patch.setattr(Path, "is_symlink", lambda *_args, **_kwargs: False)
            patch.setattr(Path, "iterdir", lambda *_args, **_kwargs: iter(()))
            observed = runner._require_runtime_contract(
                args, registration, root=root, started=1_000.0
            )
        assert observed[0] == label
        assert observed[1] == process
        assert observed[-1] == full_argv

    def exercise_payload_validator_contract(label: str) -> None:
        process = payload_validator._PROCESS[label]
        template = execution["payload_validator_argv_template"]
        assert isinstance(template, list)
        full_argv = payload_validator._substitute_validator_argv(
            template, label=label, process=process
        )
        script_index = full_argv.index(payload_validator._EXPECTED_SCRIPT)
        args = argparse.Namespace(
            repository_root=".",
            registration=payload_validator._EXPECTED_REGISTRATION,
            arm_receipt=payload_validator._ARM_RECEIPT,
            driver_claim=payload_validator._DRIVER_CLAIM,
            label=label,
            start_claim=process["start_claim"],
            validator_claim=process["validator_claim"],
            validation_receipt=process["validation_receipt"],
            payload=process["payload"],
        )
        root = Path(process["root"])

        def resolve(path: Path, *, strict: bool = False) -> Path:
            del strict
            return path if path.is_absolute() else root / path

        directory = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700,
            st_uid=os.getuid(),
        )
        with monkeypatch.context() as patch:
            patch.setattr(
                payload_validator.sys,
                "flags",
                SimpleNamespace(isolated=1, dont_write_bytecode=1),
            )
            patch.setattr(payload_validator.sys, "argv", full_argv[script_index:])
            patch.setattr(
                payload_validator.sys,
                "executable",
                str(root / ".venv/bin/python3"),
            )
            patch.setattr(Path, "resolve", resolve)
            patch.setattr(Path, "stat", lambda *_args, **_kwargs: directory)
            patch.setattr(Path, "exists", lambda *_args, **_kwargs: False)
            patch.setattr(Path, "is_symlink", lambda *_args, **_kwargs: False)
            observed = payload_validator._require_contract(
                args, runner, root, registration
            )
        assert observed == (label, process, full_argv)

    for label in ("A", "B"):
        exercise_runner_contract(label)
        exercise_payload_validator_contract(label)


def test_preparation_binds_exact_uv_version_stdout() -> None:
    assert preparation._UV_VERSION_STDOUT == b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n"


def test_result_document_contract_binds_placeholder_cases_without_self_reference() -> None:
    contract = reconstruction._result_document_contract(_synthetic_finalizer_manifest())
    assert set(contract) == {
        "schema_version", "renderer_source", "normal_template", "emergency_template",
        "normal_input_names", "emergency_input_names", "normal_cases",
    }
    assert contract["normal_input_names"] == sorted(contract["normal_input_names"])
    assert contract["emergency_input_names"] == sorted(contract["emergency_input_names"])
    assert len(contract["normal_cases"]) == 16
    stages = [row["stage"] for row in contract["normal_cases"]]
    assert stages.count(None) == 1
    assert "receipt_finalization_failed" in stages
    for row in contract["normal_cases"]:
        assert set(row) == {
            "disposition", "stage", "underlying_stage", "content_base64", "sha256", "size_bytes"
        }
        raw = base64.b64decode(row["content_base64"], validate=True)
        assert raw.count(b"<O8_COMMIT>") == 1
        assert raw.count(b"<REGISTRATION_CONTENT_SHA256>") == 1
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        assert len(raw) == row["size_bytes"]


def test_registration_assembly_has_exact_19_keys_and_inherits_v7_contracts() -> None:
    p_entries = reconstruction._tree_entries(ROOT, reconstruction.PREREGISTRATION_COMMIT)
    p_manifest, _ = reconstruction._manifest_and_blobs(ROOT, p_entries)
    anchors = reconstruction._verify_frozen_anchors(ROOT)
    _source_entry, source = reconstruction._blob_at(
        ROOT, reconstruction.O7_COMMIT, reconstruction.V7_AUDIT_PATH
    )
    transformed = source
    for _count, old, new in reconstruction.AUDIT_REPLACEMENTS:
        transformed = transformed.replace(old.encode("ascii"), new.encode("ascii"))
    audit_entry = {
        "mode": "100644", "path": reconstruction.V8_AUDIT_PATH,
        "git_blob_sha1": hashlib.sha1(
            b"blob " + str(len(transformed)).encode() + b"\0" + transformed,
            usedforsecurity=False,
        ).hexdigest(),
        "sha256": hashlib.sha256(transformed).hexdigest(), "byte_count": len(transformed),
    }
    added = [*_synthetic_finalizer_manifest(), audit_entry]
    registration = reconstruction._assemble_registration(
        p_manifest, added, {reconstruction.V8_AUDIT_PATH: transformed}, anchors
    )
    v7 = anchors["v7_registration"]
    assert set(registration) == reconstruction.TOP_LEVEL_KEYS
    assert len(registration) == 19
    assert registration["runtime_id"] is None
    assert registration["authorization"] == reconstruction.AUTHORIZATION
    for key in ("dependencies", "scene_inventory", "row_inventory", "transform_contracts", "resource_contract"):
        assert reconstruction.canonical_json_bytes(registration[key]) == reconstruction.canonical_json_bytes(v7[key])
    scientific = dict(registration["scientific_contract"])
    transformation = scientific.pop("audit_source_transformation")
    assert reconstruction.canonical_json_bytes(scientific) == reconstruction.canonical_json_bytes(v7["scientific_contract"])
    assert transformation["generated_module"] == audit_entry
    preimage = dict(registration)
    content = preimage.pop("content_sha256")
    assert content == reconstruction.canonical_sha256(preimage)


def test_pre_o_builder_uses_exact_fourteen_staged_additions_without_writing_artifact(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "pre-o8"
    bundle = tmp_path / "source.bundle"
    _git(ROOT, "bundle", "create", str(bundle), "--all")
    completed = subprocess.run(
        ["git", "clone", "--quiet", str(bundle), str(repository)],
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    _git(repository, "config", "user.name", "v8 synthetic test")
    _git(repository, "config", "user.email", "v8-test@example.invalid")
    _git(repository, "checkout", "--detach", reconstruction.PREREGISTRATION_COMMIT)
    _entry, source = reconstruction._blob_at(
        repository, reconstruction.O7_COMMIT, reconstruction.V7_AUDIT_PATH
    )
    transformed = source
    for _count, old, new in reconstruction.AUDIT_REPLACEMENTS:
        transformed = transformed.replace(old.encode("ascii"), new.encode("ascii"))
    for relative in reconstruction.NON_REGISTRATION_ADDITIONS:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            transformed
            if relative == reconstruction.V8_AUDIT_PATH
            else f"synthetic staged source: {relative}\n".encode("ascii")
        )
    _git(repository, "add", "--", *reconstruction.NON_REGISTRATION_ADDITIONS)
    registration = producer.build_registration(repository, producer.PREREGISTRATION_TAG)
    replayed_registration = producer.build_registration(
        repository, producer.PREREGISTRATION_TAG
    )
    assert reconstruction.canonical_json_bytes(replayed_registration) == (
        reconstruction.canonical_json_bytes(registration)
    )
    assert set(registration) == reconstruction.TOP_LEVEL_KEYS
    added = registration["source_manifest"]["open_freeze_added_files"]
    assert [row["path"] for row in added] == list(reconstruction.NON_REGISTRATION_ADDITIONS)
    assert not (repository / reconstruction.REGISTRATION_PATH).exists()
    assert all(set(row) == {"mode", "path", "git_blob_sha1", "sha256", "byte_count"} for row in added)

    registration_raw = reconstruction.canonical_json_bytes(registration)
    registration_path = repository / reconstruction.REGISTRATION_PATH
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.write_bytes(registration_raw)
    _git(repository, "add", "--", reconstruction.REGISTRATION_PATH)
    _git(repository, "commit", "-q", "-m", "synthetic exact O8")
    open_freeze = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    _git(repository, "tag", "-f", reconstruction.OPEN_FREEZE_TAG, open_freeze)

    if sys.platform == "linux":
        _close_local_git_configuration(repository)
        raw_audit = preparation._raw_tree_audit(
            preparation._CommandLedger(),
            repository,
            open_freeze,
            allow_venv=False,
        )
        assert len(raw_audit.entries) == len(reconstruction._tree_entries(repository, open_freeze))
        assert len(raw_audit.tree_sha256) == 64
        assert len(raw_audit.raw_sha256) == 64
        _git(repository, "config", "user.name", "v8 synthetic test")
        _git(repository, "config", "user.email", "v8-test@example.invalid")

    rebuilt, is_open_freeze = reconstruction.reconstruct_registration(repository)
    replayed_rebuild, replayed_is_open_freeze = (
        reconstruction.reconstruct_registration(repository)
    )
    assert is_open_freeze is True
    assert replayed_is_open_freeze is True
    assert reconstruction.canonical_json_bytes(rebuilt) == registration_raw
    assert reconstruction.canonical_json_bytes(replayed_rebuild) == registration_raw
    assert reconstruction.verify_registration(
        repository, reconstruction.REGISTRATION_PATH
    ) == registration

    def stage_synthetic_freeze(*, extra_path: bool, checkout_p8: bool = True) -> None:
        if checkout_p8:
            _git(
                repository,
                "checkout",
                "-q",
                "--detach",
                reconstruction.PREREGISTRATION_COMMIT,
            )
        for relative in reconstruction.NON_REGISTRATION_ADDITIONS:
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                transformed
                if relative == reconstruction.V8_AUDIT_PATH
                else f"synthetic staged source: {relative}\n".encode("ascii")
            )
        registration_path.parent.mkdir(parents=True, exist_ok=True)
        registration_path.write_bytes(registration_raw)
        _git(repository, "add", "--", *reconstruction.ALL_ADDITIONS)
        if extra_path:
            extra = repository / "unexpected-o8-path.txt"
            extra.write_bytes(b"not allowlisted\n")
            _git(repository, "add", "--", extra.name)

    stage_synthetic_freeze(extra_path=True)
    _git(repository, "commit", "-q", "-m", "synthetic O8 with extra path")
    _git(repository, "tag", "-f", reconstruction.OPEN_FREEZE_TAG, "HEAD")
    with pytest.raises(reconstruction.ReconstructionError, match="exact fifteen-addition"):
        reconstruction.reconstruct_registration(repository)

    _git(repository, "checkout", "-q", "--detach", reconstruction.PREREGISTRATION_COMMIT)
    _git(repository, "commit", "-q", "--allow-empty", "-m", "unexpected intermediate")
    stage_synthetic_freeze(extra_path=False, checkout_p8=False)
    _git(repository, "commit", "-q", "-m", "synthetic non-direct O8")
    _git(repository, "tag", "-f", reconstruction.OPEN_FREEZE_TAG, "HEAD")
    with pytest.raises(reconstruction.ReconstructionError, match="not a direct child"):
        reconstruction.reconstruct_registration(repository)

    exact_tree = _git(
        repository, "rev-parse", f"{open_freeze}^{{tree}}"
    ).decode("ascii").strip()
    preregistration_tree = _git(
        repository,
        "rev-parse",
        f"{reconstruction.PREREGISTRATION_COMMIT}^{{tree}}",
    ).decode("ascii").strip()
    side_parent = _git(
        repository,
        "commit-tree",
        preregistration_tree,
        "-p",
        reconstruction.PREREGISTRATION_COMMIT,
        "-m",
        "synthetic merge side",
    ).decode("ascii").strip()
    merge_open_freeze = _git(
        repository,
        "commit-tree",
        exact_tree,
        "-p",
        reconstruction.PREREGISTRATION_COMMIT,
        "-p",
        side_parent,
        "-m",
        "synthetic merge O8",
    ).decode("ascii").strip()
    _git(repository, "checkout", "-q", "--detach", merge_open_freeze)
    _git(repository, "tag", "-f", reconstruction.OPEN_FREEZE_TAG, merge_open_freeze)
    with pytest.raises(reconstruction.ReconstructionError, match="not a direct child"):
        reconstruction.reconstruct_registration(repository)


@pytest.mark.parametrize(
    "relative",
    (
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "scripts/prepare_action_qbc_v8_open.py",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "scripts/validate_action_qbc_v8_open_payload.py",
        "scripts/supervise_action_qbc_v8_remote_tag.py",
        "scripts/verify_action_qbc_v8_remote_tag.py",
    ),
)
def test_o8_consumers_use_exact_parent_vector_plumbing(relative: str) -> None:
    source = (ROOT / relative).read_text(encoding="utf-8")
    assert '"rev-list"' in source
    assert '"--parents"' in source


@pytest.mark.skipif(sys.platform != "linux", reason="registered raw audit is Linux-only")
def test_preparation_raw_tree_audit_is_byte_mode_index_and_shape_exact(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "raw-audit"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "v8 raw audit test")
    _git(repository, "config", "user.email", "v8-test@example.invalid")
    (repository / ".gitignore").write_bytes(b".venv/\n")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"frozen bytes\n")
    _git(repository, "add", ".gitignore", "tracked.txt")
    _git(repository, "commit", "-q", "-m", "raw audit fixture")
    commit = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    _close_local_git_configuration(repository)

    first = preparation._raw_tree_audit(
        preparation._CommandLedger(), repository, commit, allow_venv=False
    )
    second = preparation._raw_tree_audit(
        preparation._CommandLedger(), repository, commit, allow_venv=False
    )
    assert first == second

    tracked.write_bytes(b"mutated bytes\n")
    with pytest.raises(preparation.ProtocolError, match="raw checkout bytes"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    tracked.write_bytes(b"frozen bytes\n")

    _git(repository, "update-index", "--chmod=+x", "tracked.txt")
    with pytest.raises(preparation.ProtocolError, match="stage-zero index"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    _git(repository, "update-index", "--chmod=-x", "tracked.txt")

    tracked.chmod(0o755)
    with pytest.raises(preparation.ProtocolError, match="executable mode bits"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    tracked.chmod(0o644)

    untracked = repository / "untracked.txt"
    untracked.write_bytes(b"not in the tree\n")
    with pytest.raises(preparation.ProtocolError, match="untracked file"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    untracked.unlink()

    symlink = repository / "untracked-link"
    symlink.symlink_to(tracked)
    with pytest.raises(preparation.ProtocolError, match="contains a symlink"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    symlink.unlink()

    venv = repository / ".venv"
    venv.mkdir()
    (venv / "cache.bin").write_bytes(b"ignored environment bytes\n")
    with pytest.raises(preparation.ProtocolError, match="untracked directory"):
        preparation._raw_tree_audit(
            preparation._CommandLedger(), repository, commit, allow_venv=False
        )
    assert preparation._raw_tree_audit(
        preparation._CommandLedger(), repository, commit, allow_venv=True
    ) == first


@pytest.mark.skipif(os.name != "posix", reason="Linux preparation transaction contract")
def test_prepare_attempt_orders_raw_audits_around_build_and_promotes_all_four_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    audit = preparation._RawAudit(
        tree_sha256="1" * 64,
        raw_sha256="2" * 64,
        status_sha256=hashlib.sha256(b"").hexdigest(),
        entries=(),
        blobs={},
    )
    registration = preparation._Registration(
        value={},
        raw=b"{}",
        content_sha256="3" * 64,
        file_sha256="4" * 64,
        source_manifest_sha256="5" * 64,
        execution={},
    )
    events: list[tuple[object, ...]] = []

    def clone_checkout(
        _ledger: preparation._CommandLedger,
        destination: Path,
        _open_commit: str,
        **_kwargs: Any,
    ) -> None:
        events.append(("clone", destination.name))

    def raw_audit(
        _ledger: preparation._CommandLedger,
        root: Path,
        _open_commit: str,
        *,
        allow_venv: bool,
        **_kwargs: Any,
    ) -> preparation._RawAudit:
        events.append(("audit", root.name, allow_venv))
        return audit

    def environment_build(
        _ledger: preparation._CommandLedger,
        argv: list[str],
        *,
        cwd: Path,
        timeout: int,
        **_kwargs: Any,
    ) -> bytes:
        assert argv == preparation._expected_environment_argv()
        assert timeout == 600
        events.append(("environment", cwd.name))
        return b""

    def inventory(root: Path) -> tuple[list[dict[str, object]], str]:
        events.append(("inventory", root.name))
        return [], "6" * 64

    def materialization(root: Path) -> str:
        events.append(("materialization", root.name))
        return "7" * 64

    def python_identity(root: Path) -> str:
        events.append(("python", root.name))
        return "8" * 64

    def preflight(
        _ledger: preparation._CommandLedger,
        root: Path,
        _registration: preparation._Registration,
        _open_commit: str,
        **_kwargs: Any,
    ) -> str:
        events.append(("preflight", root.name))
        return audit.status_sha256

    real_rename = preparation._rename_noreplace

    def rename(source: Path, destination: Path) -> None:
        events.append(("rename", source.name, destination.name))
        real_rename(source, destination)

    monkeypatch.setattr(preparation, "_clone_checkout", clone_checkout)
    monkeypatch.setattr(preparation, "_raw_tree_audit", raw_audit)
    monkeypatch.setattr(preparation, "_run_command", environment_build)
    monkeypatch.setattr(preparation, "_environment_inventory", inventory)
    monkeypatch.setattr(preparation, "_venv_materialization_sha256", materialization)
    monkeypatch.setattr(preparation, "_venv_python_sha256", python_identity)
    monkeypatch.setattr(preparation, "_run_preflight", preflight)
    monkeypatch.setattr(preparation, "_rename_noreplace", rename)

    outcome = preparation._prepare_attempt(
        preparation._CommandLedger(),
        tmp_path,
        1,
        registration,
        "a" * 40,
        audit,
    )
    assert outcome.error is None
    assert outcome.cleanup_passes is True
    assert outcome.record["passes"] is True
    assert events == [
        ("clone", "process-a"),
        ("clone", "process-b"),
        ("audit", "process-a", False),
        ("audit", "process-b", False),
        ("environment", "process-a"),
        ("environment", "process-b"),
        ("inventory", "process-a"),
        ("materialization", "process-a"),
        ("python", "process-a"),
        ("audit", "process-a", True),
        ("inventory", "process-b"),
        ("materialization", "process-b"),
        ("python", "process-b"),
        ("audit", "process-b", True),
        ("preflight", "process-a"),
        ("preflight", "process-b"),
        ("inventory", "process-a"),
        ("materialization", "process-a"),
        ("python", "process-a"),
        ("inventory", "process-b"),
        ("materialization", "process-b"),
        ("python", "process-b"),
        ("rename", ".prepare-attempt-1", "processes"),
    ]
    promoted = tmp_path / "processes"
    assert not (tmp_path / ".prepare-attempt-1").exists()
    assert {path.name for path in promoted.iterdir()} == {
        "process-a",
        "process-b",
        "process-a-output",
        "process-b-output",
    }
    for relative in (
        "process-a",
        "process-b",
        "process-a-output/open",
        "process-b-output/open",
    ):
        path = promoted / relative
        assert path.is_dir()
        assert not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert not any(path.iterdir())


@pytest.mark.skipif(os.name != "posix", reason="Linux preparation retry contract")
@pytest.mark.parametrize(
    ("case", "expected_attempts", "expected_status"),
    (
        ("retry_then_success", [1, 2], "prepared"),
        ("cleanup_failure_stops", [1], None),
        ("two_clean_failures", [1, 2], "failed"),
    ),
)
def test_prepare_attempt_budget_and_cleanup_gate_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_attempts: list[int],
    expected_status: str | None,
) -> None:
    execution_root = tmp_path / case
    authority = execution_root / "authority"
    authority.mkdir(parents=True, mode=0o700)
    execution_root.chmod(0o700)
    authority.chmod(0o700)
    receipt_path = execution_root / "preparation-receipt.json"
    monkeypatch.setattr(preparation, "_EXECUTION_ROOT", str(execution_root))
    monkeypatch.setattr(preparation, "_AUTHORITY_ROOT", str(authority))
    monkeypatch.setattr(preparation, "_PREPARATION_RECEIPT", str(receipt_path))
    monkeypatch.chdir(authority)

    open_commit = "a" * 40
    audit = preparation._RawAudit(
        tree_sha256="1" * 64,
        raw_sha256="2" * 64,
        status_sha256=hashlib.sha256(b"").hexdigest(),
        entries=(),
        blobs={},
    )
    registration = preparation._Registration(
        value={},
        raw=b"{}",
        content_sha256="3" * 64,
        file_sha256="4" * 64,
        source_manifest_sha256="5" * 64,
        execution={},
    )
    authority_audits: list[tuple[Path, bool]] = []

    def raw_audit(
        _ledger: preparation._CommandLedger,
        root: Path,
        _commit: str,
        *,
        allow_venv: bool,
    ) -> preparation._RawAudit:
        authority_audits.append((root, allow_venv))
        return audit

    monkeypatch.setattr(preparation, "_derive_open_freeze", lambda *_args: open_commit)
    monkeypatch.setattr(preparation, "_raw_tree_audit", raw_audit)
    monkeypatch.setattr(preparation, "_load_registration", lambda *_args: registration)
    monkeypatch.setattr(preparation, "_validate_prepare_invocation", lambda *_args: None)
    monkeypatch.setattr(preparation, "_validate_linux_host", lambda *_args: None)

    observed_attempts: list[int] = []

    def failed(attempt_index: int, *, cleanup_passes: bool) -> preparation._AttemptOutcome:
        source = execution_root / f".prepare-attempt-{attempt_index}"
        record = preparation._failure_attempt_record(
            attempt_index,
            {"a": "clone_failed", "b": "not_started"},
            source,
            execution_root / "processes",
            None,
            False,
            cleanup_passes,
        )
        return preparation._AttemptOutcome(
            record, None, None, cleanup_passes, f"failure-{attempt_index}"
        )

    def passed(attempt_index: int) -> preparation._AttemptOutcome:
        source = execution_root / f".prepare-attempt-{attempt_index}"
        process_root = execution_root / "processes"
        for relative in (
            "process-a", "process-b", "process-a-output/open", "process-b-output/open",
        ):
            path = process_root / relative
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)
        process_a = preparation._clone_receipt(
            execution_root / "processes/process-a",
            open_commit,
            audit,
            [],
            "6" * 64,
            "8" * 64,
            "9" * 64,
            environment=True,
        )
        process_b = preparation._clone_receipt(
            execution_root / "processes/process-b",
            open_commit,
            audit,
            [],
            "7" * 64,
            "8" * 64,
            "9" * 64,
            environment=True,
        )
        promoted = process_root.stat()
        record = {
            "attempt_index": attempt_index,
            "process_a_stage": "completed",
            "process_b_stage": "completed",
            "cleanup": {
                "owned_paths": [str(source)],
                "removed": [],
                "passes": True,
            },
            "promotion": {
                "source_path": str(source),
                "destination_path": str(execution_root / "processes"),
                "source_device": promoted.st_dev,
                "source_inode": promoted.st_ino,
                "passes": True,
            },
            "passes": True,
        }
        return preparation._AttemptOutcome(record, process_a, process_b, True, None)

    def prepare_attempt(
        _ledger: preparation._CommandLedger,
        _root: Path,
        attempt_index: int,
        _registration: preparation._Registration,
        _commit: str,
        _authority_audit: preparation._RawAudit,
    ) -> preparation._AttemptOutcome:
        observed_attempts.append(attempt_index)
        if case == "retry_then_success" and attempt_index == 2:
            return passed(attempt_index)
        if case == "cleanup_failure_stops":
            return failed(attempt_index, cleanup_passes=False)
        return failed(attempt_index, cleanup_passes=True)

    monkeypatch.setattr(preparation, "_prepare_attempt", prepare_attempt)
    args = argparse.Namespace(
        repository_root=Path("."),
        registration=Path(preparation._REGISTRATION_PATH),
        execution_root=execution_root,
        receipt=receipt_path,
    )
    if case == "cleanup_failure_stops":
        with pytest.raises(preparation.ProtocolError) as captured:
            preparation._prepare(args)
        assert type(captured.value) is preparation.ProtocolError
        assert str(captured.value) == (
            "preparation cleanup failed; no canonical failed receipt may be published"
        )
        assert observed_attempts == expected_attempts == [1]
        assert authority_audits == [(authority, False)]
        assert not receipt_path.exists()
        return

    return_code = preparation._prepare(args)
    receipt = reconstruction.strict_object(receipt_path.read_bytes(), "synthetic receipt")
    assert observed_attempts == expected_attempts
    assert authority_audits == [(authority, False)]
    assert receipt["status"] == expected_status
    assert len(receipt["attempts"]) == len(expected_attempts)
    if expected_status == "prepared":
        assert return_code == 0
        assert receipt["process_a"] is not None
        assert receipt["process_b"] is not None
    else:
        assert return_code == 1
        assert receipt["process_a"] is None
        assert receipt["process_b"] is None


@pytest.mark.skipif(os.name != "posix", reason="Linux arm immutability contract")
def test_arm_copies_all_four_validated_sources_once_as_immutable_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    registration = preparation._Registration(
        value={},
        raw=b"{}",
        content_sha256="a" * 64,
        file_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        execution={},
    )
    preparation_state = preparation._ArtifactState(
        tmp_path / "preparation-receipt.json", True, "readable",
        b'{"status":"prepared"}', hashlib.sha256(b'{"status":"prepared"}').hexdigest(),
    )
    verification_state = preparation._ArtifactState(
        tmp_path / "preparation-verification.json", True, "readable",
        b'{"status":"verified"}', hashlib.sha256(b'{"status":"verified"}').hexdigest(),
    )
    context = preparation._ArmContext(
        execution_root=tmp_path,
        authority=tmp_path / "authority",
        open_commit="d" * 40,
        registration=registration,
        preparation=preparation_state,
        preparation_verification=verification_state,
        preparation_valid=True,
        preparation_verification_valid=True,
        evidence_errors=(),
    )
    source_paths = {
        "claim": tmp_path / "windows-claim.json",
        "start": tmp_path / "windows-start.json",
        "remote": tmp_path / "windows-remote.json",
        "supervisor": tmp_path / "windows-supervisor.json",
    }
    source_bytes = {
        "claim": b'{"claim":true}',
        "start": b'{"start":true}',
        "remote": b'{"status":"verified"}',
        "supervisor": b'{"status":"completed"}',
    }
    by_path = {source_paths[name]: name for name in source_paths}

    def source_artifact(path: Path, _name: str) -> preparation._SourceArtifact:
        key = by_path[path]
        raw = source_bytes[key]
        return preparation._SourceArtifact(
            path=path,
            exists=True,
            read_status="readable",
            raw=raw,
            sha256=hashlib.sha256(raw).hexdigest(),
        )

    monkeypatch.setattr(preparation, "_validate_prepared_state", lambda _args: context)
    monkeypatch.setattr(preparation, "_validate_arm_invocation", lambda *_args: None)
    monkeypatch.setattr(preparation, "_source_artifact", source_artifact)
    monkeypatch.setattr(
        preparation,
        "_validate_lifecycle_claim",
        lambda raw, _context: ({}, hashlib.sha256(raw).hexdigest()),
    )
    monkeypatch.setattr(
        preparation,
        "_validate_start_claim",
        lambda raw, _context, _claim_sha: ({}, hashlib.sha256(raw).hexdigest()),
    )
    monkeypatch.setattr(
        preparation,
        "_validate_remote_receipt",
        lambda raw, _context, _claim_sha, _start_sha: (
            {"status": "verified"},
            hashlib.sha256(raw).hexdigest(),
        ),
    )
    monkeypatch.setattr(
        preparation,
        "_validate_supervisor_receipt",
        lambda raw, _context, **_kwargs: (
            {"status": "completed"},
            hashlib.sha256(raw).hexdigest(),
        ),
    )
    first_arm_receipt = tmp_path / "arm-receipt.json"
    args = argparse.Namespace(
        windows_claim=source_paths["claim"],
        windows_verifier_start_claim=source_paths["start"],
        windows_remote_receipt=source_paths["remote"],
        windows_supervisor_receipt=source_paths["supervisor"],
        arm_receipt=first_arm_receipt,
    )
    assert preparation._arm(args) == 0
    destinations = {
        "claim": tmp_path / "remote-verification-claim.json",
        "start": tmp_path / "remote-verifier-start-claim.json",
        "remote": tmp_path / "remote-verification.json",
        "supervisor": tmp_path / "remote-verification-supervisor.json",
    }
    for name, destination in destinations.items():
        assert destination.read_bytes() == source_bytes[name]
        assert stat.S_IMODE(destination.stat().st_mode) == 0o444
    arm_receipt = reconstruction.strict_object(
        first_arm_receipt.read_bytes(), "synthetic arm receipt"
    )
    assert arm_receipt["status"] == "armed"
    assert stat.S_IMODE(first_arm_receipt.stat().st_mode) == 0o444

    source_bytes["claim"] = b'{"claim":"mutated"}'
    second_args = argparse.Namespace(**vars(args))
    second_args.arm_receipt = tmp_path / "second-arm-receipt.json"
    with pytest.raises(preparation.ProtocolError, match="already exists"):
        preparation._arm(second_args)
    assert not second_args.arm_receipt.exists()
    for name, destination in destinations.items():
        expected = b'{"claim":true}' if name == "claim" else source_bytes[name]
        assert destination.read_bytes() == expected


@pytest.mark.skipif(os.name != "posix", reason="Linux arm immutability contract")
@pytest.mark.parametrize("failure_kind", ["malformed_claim", "cross_mismatched_remote"])
def test_arm_preserves_complete_invalid_source_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    tmp_path.chmod(0o700)
    registration = preparation._Registration(
        value={},
        raw=b"{}",
        content_sha256="a" * 64,
        file_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        execution={},
    )
    preparation_state = preparation._ArtifactState(
        tmp_path / "preparation-receipt.json", True, "readable",
        b'{"status":"prepared"}', hashlib.sha256(b'{"status":"prepared"}').hexdigest(),
    )
    verification_state = preparation._ArtifactState(
        tmp_path / "preparation-verification.json", True, "readable",
        b'{"status":"verified"}', hashlib.sha256(b'{"status":"verified"}').hexdigest(),
    )
    context = preparation._ArmContext(
        execution_root=tmp_path,
        authority=tmp_path / "authority",
        open_commit="d" * 40,
        registration=registration,
        preparation=preparation_state,
        preparation_verification=verification_state,
        preparation_valid=True,
        preparation_verification_valid=True,
        evidence_errors=(),
    )
    source_paths = {
        "claim": tmp_path / "windows-claim.json",
        "start": tmp_path / "windows-start.json",
        "remote": tmp_path / "windows-remote.json",
        "supervisor": tmp_path / "windows-supervisor.json",
    }
    source_bytes = {
        "claim": b'{"claim":"complete-but-malformed"}',
        "start": b'{"start":"complete"}',
        "remote": b'{"receipt":"cross-mismatched"}',
        "supervisor": b'{"supervisor":"complete"}',
    }
    for name, path in source_paths.items():
        path.write_bytes(source_bytes[name])

    monkeypatch.setattr(preparation, "_validate_prepared_state", lambda _args: context)
    monkeypatch.setattr(preparation, "_validate_arm_invocation", lambda *_args: None)

    def validate_claim(raw: bytes, _context: preparation._ArmContext) -> tuple[dict[str, object], str]:
        if failure_kind == "malformed_claim":
            raise preparation.ProtocolError("synthetic malformed claim")
        return {}, hashlib.sha256(raw).hexdigest()

    def validate_remote(
        _raw: bytes,
        _context: preparation._ArmContext,
        _claim_sha: str,
        _start_sha: str,
    ) -> tuple[dict[str, object], str]:
        raise preparation.ProtocolError("synthetic cross-mismatched remote receipt")

    monkeypatch.setattr(preparation, "_validate_lifecycle_claim", validate_claim)
    monkeypatch.setattr(
        preparation,
        "_validate_start_claim",
        lambda raw, _context, _claim_sha: ({}, hashlib.sha256(raw).hexdigest()),
    )
    monkeypatch.setattr(preparation, "_validate_remote_receipt", validate_remote)
    monkeypatch.setattr(
        preparation,
        "_validate_supervisor_receipt",
        lambda raw, _context, **_kwargs: (
            {"status": "failed"},
            hashlib.sha256(raw).hexdigest(),
        ),
    )

    arm_receipt_path = tmp_path / "arm-receipt.json"
    args = argparse.Namespace(
        windows_claim=source_paths["claim"],
        windows_verifier_start_claim=source_paths["start"],
        windows_remote_receipt=source_paths["remote"],
        windows_supervisor_receipt=source_paths["supervisor"],
        arm_receipt=arm_receipt_path,
    )
    assert preparation._arm(args) == 1

    destinations = {
        "claim": tmp_path / "remote-verification-claim.json",
        "start": tmp_path / "remote-verifier-start-claim.json",
        "remote": tmp_path / "remote-verification.json",
        "supervisor": tmp_path / "remote-verification-supervisor.json",
    }
    arm_receipt = reconstruction.strict_object(
        arm_receipt_path.read_bytes(), "failed synthetic arm receipt"
    )
    assert arm_receipt["status"] == "failed"
    receipt_hash_fields = {
        "claim": "remote_claim_sha256",
        "start": "remote_verifier_claim_sha256",
        "remote": "remote_receipt_sha256",
        "supervisor": "remote_supervisor_receipt_sha256",
    }
    for name, destination in destinations.items():
        expected = source_bytes[name]
        assert destination.read_bytes() == expected
        assert stat.S_IMODE(destination.stat().st_mode) == 0o444
        assert arm_receipt[receipt_hash_fields[name]] == hashlib.sha256(expected).hexdigest()


@pytest.mark.skipif(os.name != "posix", reason="registered Ubuntu/tool identity contract")
def test_preparation_rejects_ubuntu_and_linux_tool_identity_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = "synthetic-registered-kernel"
    registration = preparation._Registration(
        value={},
        raw=b"{}",
        content_sha256="1" * 64,
        file_sha256="2" * 64,
        source_manifest_sha256="3" * 64,
        execution={"linux_platform": {"kernel": kernel}},
    )
    monkeypatch.setattr(preparation.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preparation.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(preparation.platform, "release", lambda: kernel)
    real_read_text = Path.read_text

    def debian_release(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == Path("/etc/os-release"):
            return 'ID=debian\nVERSION_ID="12"\nVERSION="12"\nVERSION_CODENAME=bookworm\n'
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", debian_release)
    with pytest.raises(preparation.ProtocolError, match="registered Ubuntu noble"):
        preparation._validate_linux_host(registration)

    def ubuntu_release(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == Path("/etc/os-release"):
            return (
                'ID=ubuntu\nVERSION_ID="24.04"\n'
                'VERSION="24.04.1 LTS (Noble Numbat)"\n'
                "VERSION_CODENAME=noble\n"
            )
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", ubuntu_release)
    monkeypatch.setattr(
        preparation,
        "_read_plain_file",
        lambda _path, _name, **_kwargs: b"mutated registered tool bytes",
    )
    with pytest.raises(preparation.ProtocolError, match="Linux tool SHA-256 mismatch"):
        preparation._validate_linux_host(registration)


@pytest.mark.skipif(os.name != "posix", reason="independent Linux receipt gate")
def test_reconstructor_independently_revalidates_prepared_receipt_and_live_clones(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_root = tmp_path / "execution"
    authority = execution_root / "authority"
    processes = execution_root / "processes"
    process_a = processes / "process-a"
    process_b = processes / "process-b"
    output_a = processes / "process-a-output/open"
    output_b = processes / "process-b-output/open"
    for path in (execution_root, authority, processes, process_a, process_b, output_a, output_b):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    (process_a / ".venv").mkdir(mode=0o700)
    (process_b / ".venv").mkdir(mode=0o700)
    preparation_receipt = execution_root / "preparation-receipt.json"
    verification_receipt = execution_root / "preparation-verification.json"
    head = "a" * 40
    tree_sha = "b" * 64
    raw_sha = "c" * 64
    materialization_sha = "1" * 64
    python_sha = "2" * 64
    inventory = [
        {
            "normalized_name": name,
            "version": version,
            "file_count": 1,
            "files_sha256": "3" * 64,
        }
        for name, version in reconstruction._EXPECTED_DISTRIBUTIONS.items()
    ]
    environment_sha = reconstruction.canonical_sha256(inventory)
    verification_argv = [
        "/usr/bin/python3", "-I", "-B",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "--repository-root", ".", "--registration", reconstruction.REGISTRATION_PATH,
        "--verify-preparation", "--preparation-receipt", str(preparation_receipt),
        "--verification-receipt", str(verification_receipt),
    ]
    registration = {
        "content_sha256": "e" * 64,
        "source_manifest": {"manifest_sha256": "f" * 64},
        "execution_contract": {
            "preparation_receipt_path": str(preparation_receipt),
            "preparation_verification_receipt_path": str(verification_receipt),
            "preparation_command_environment": reconstruction.PREPARATION_COMMAND_ENVIRONMENT,
            "preparation_command_policy": reconstruction.PREPARATION_COMMAND_POLICY,
            "post_preparation_validation_argv": verification_argv,
            "environment_build_argv": [
                "/usr/bin/env", "UV_OFFLINE=1", "/usr/local/bin/uv", "sync", "--python",
                "3.12.13", "--frozen", "--no-dev", "--offline",
            ],
            "preflight_argvs": [
                ["/usr/bin/git", "--no-replace-objects", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                ["/usr/bin/git", "--no-replace-objects", "rev-parse", "HEAD"],
                [".venv/bin/python3", "--version"],
                ["/usr/local/bin/uv", "--version"],
                ["/usr/bin/python3", "-I", "-B", "scripts/reconstruct_action_qbc_v8_open_registration.py", "--repository-root", ".", "--registration", reconstruction.REGISTRATION_PATH, "--verify-open-freeze"],
            ],
            "execution_root": str(execution_root),
            "authority_root": str(authority),
            "process_a_root": str(process_a),
            "process_b_root": str(process_b),
            "process_a_output": str(output_a / "payload.json"),
            "process_b_output": str(output_b / "payload.json"),
        },
    }
    empty_status_sha = hashlib.sha256(b"").hexdigest()

    def clone_record(root: Path, *, environment: bool) -> dict[str, object]:
        metadata = root.stat()
        return {
            "root": str(root),
            "root_device": metadata.st_dev,
            "root_inode": metadata.st_ino,
            "root_owner_uid": metadata.st_uid,
            "root_mode": stat.S_IMODE(metadata.st_mode),
            "head_sha": head,
            "tree_sha256": tree_sha,
            "raw_materialization_sha256": raw_sha,
            "git_status_sha256": empty_status_sha,
            "python_version": "3.12.13" if environment else None,
            "uv_version": "0.11.28" if environment else None,
            "environment_inventory": inventory if environment else None,
            "environment_inventory_sha256": environment_sha if environment else None,
            "venv_materialization_sha256": materialization_sha if environment else None,
            "venv_python_sha256": python_sha if environment else None,
            "passes": True,
        }

    promoted = processes.stat()
    source = execution_root / ".prepare-attempt-1"
    receipt = {
        "schema_version": "action-qbc-v8-preparation-receipt-v2",
        "treatment_id": reconstruction.TREATMENT_ID,
        "open_freeze_commit_sha": head,
        "open_freeze_tag": reconstruction.OPEN_FREEZE_TAG,
        "registration_content_sha256": registration["content_sha256"],
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
        "authority": clone_record(authority, environment=False),
        "process_a": clone_record(process_a, environment=True),
        "process_b": clone_record(process_b, environment=True),
        "command_ledger": [],
        "commands_sha256": "",
        "command_environment_sha256": reconstruction.canonical_sha256(
            reconstruction.PREPARATION_COMMAND_ENVIRONMENT
        ),
        "status": "prepared",
    }
    ledger = _full_preparation_ledger(
        execution_root,
        registration["execution_contract"],
    )
    receipt["command_ledger"] = ledger
    receipt["commands_sha256"] = reconstruction.canonical_sha256(ledger)
    preparation_receipt.write_bytes(reconstruction.canonical_json_bytes(receipt))
    observed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        reconstruction,
        "verify_registration",
        lambda root, path: registration,
    )
    monkeypatch.setattr(
        reconstruction,
        "_reconstruct_with_identity",
        lambda root: (registration, "open_freeze", head),
    )
    monkeypatch.setattr(
        reconstruction,
        "_verify_linux_host",
        lambda _registration: observed.append(("host", "verified")),
    )
    monkeypatch.setattr(
        reconstruction,
        "_validate_git_isolation",
        lambda root, _commit: observed.append(("git", root.name)),
    )

    def raw_audit(root: Path, commit: str) -> tuple[str, str]:
        assert commit == head
        observed.append(("raw", root.name))
        return tree_sha, raw_sha

    monkeypatch.setattr(reconstruction, "_raw_tree_audit", raw_audit)
    monkeypatch.setattr(
        reconstruction,
        "_tree_entries",
        lambda _root, _commit: _SYNTHETIC_LEDGER_ENTRIES,
    )
    monkeypatch.setattr(reconstruction, "_environment_inventory", lambda _root: inventory)
    monkeypatch.setattr(
        reconstruction,
        "_venv_materialization_sha256",
        lambda _root: materialization_sha,
    )
    monkeypatch.setattr(
        reconstruction,
        "_resolved_venv_python_sha256",
        lambda _root: python_sha,
    )
    monkeypatch.setattr(
        reconstruction,
        "_run_identity_command",
        lambda argv, _cwd, _label: (
            b"Python 3.12.13\n" if argv[0] == ".venv/bin/python3"
            else b"uv 0.11.28 (x86_64-unknown-linux-gnu)\n"
        ),
    )
    monkeypatch.setattr(
        reconstruction,
        "_git",
        lambda root, *argv: b""
        if argv == ("status", "--porcelain=v1", "-z", "--untracked-files=all")
        else (_ for _ in ()).throw(AssertionError((root, argv))),
    )
    record = reconstruction.verify_preparation(
        authority,
        reconstruction.REGISTRATION_PATH,
        preparation_receipt,
        verification_receipt,
    )
    assert record["status"] == "verified"
    assert reconstruction.strict_object(verification_receipt.read_bytes()) == record
    assert observed == [
        ("host", "verified"),
        ("git", "authority"),
        ("raw", "authority"),
        ("git", "process-a"),
        ("raw", "process-a"),
        ("git", "process-b"),
        ("raw", "process-b"),
    ]
    verification_receipt.unlink()
    (output_b / "unexpected-output.json").write_bytes(b"not yet authorized")
    with pytest.raises(reconstruction.ReconstructionError, match="process B output parent"):
        reconstruction.verify_preparation(
            authority,
            reconstruction.REGISTRATION_PATH,
            preparation_receipt,
            verification_receipt,
        )
    assert not verification_receipt.exists()


def test_all_production_v7_literals_and_path_reads_are_exactly_allowlisted() -> None:
    production_paths = (
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
    )
    trees: dict[str, ast.Module] = {}
    sources: dict[str, str] = {}
    literals: dict[str, set[str]] = {}
    for relative in production_paths:
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        sources[relative] = source
        trees[relative] = tree
        literals[relative] = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "v7" in node.value.lower()
        }
        lowered = source.lower()
        assert "/var/tmp/arc3-crosslevel-voi-action-qbc-v7" not in lowered
        assert "arc3-crosslevel-voi-action-qbc-v7-open" not in lowered

    windows_repository_v7_literals = {
        "branch.action-qbc-v7-open-diagnostic.merge",
        "branch.action-qbc-v7-open-diagnostic.remote",
        "branch.action-qbc-v7-prereg.merge",
        "branch.action-qbc-v7-prereg.remote",
        "refs/heads/action-qbc-v7-open-diagnostic",
        "refs/heads/action-qbc-v7-prereg",
    }
    windows_contract_paths = {
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/prepare_action_qbc_v8_open.py",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "scripts/supervise_action_qbc_v8_remote_tag.py",
        "scripts/verify_action_qbc_v8_remote_tag.py",
    }
    assert {path for path, values in literals.items() if values} == {
        *windows_contract_paths,
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "src/arc3_voi/action_qbc_v8_audit.py",
    }
    assert literals["scripts/finalize_action_qbc_v8_open_diagnostic.py"] == {
        "action-qbc-v7-expected-exterior-support-table-v1",
        "action-qbc-v7-grid-evidence-table-v1",
        "action-qbc-v8-v7-mathematics-identity-replication-v1",
        *windows_repository_v7_literals,
    }
    for path in windows_contract_paths - {
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
    }:
        assert literals[path] == windows_repository_v7_literals
    assert literals["scripts/reconstruct_action_qbc_v8_open_registration.py"] == {
        "action-qbc-v7-boundary-compound-selector-decomposition-v1",
        "action-qbc-v7-open-diagnostic-freeze-v1",
        "action-qbc-v7-open-diagnostic-payload-v1",
        "action-qbc-v7-open-diagnostic-result-v1",
        "action-qbc-v7-open-failure-decomposition-v1",
        "action-qbc-v7-open-registration-v1",
        "action-qbc-v8-v7-mathematics-identity-replication-v1",
        "artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json",
        "artifacts/action_qbc_v7_open_registration.json",
        "crosslevel-voi-open-diagnostic-v7",
        "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md",
        "frozen v7 administrative terminal mismatch",
        "frozen v7 registration",
        "frozen v7 registration content hash is invalid",
        "frozen v7 registration content identity mismatch",
        "frozen v7 registration file SHA-256 mismatch",
        "frozen v7 registration lacks an inherited contract",
        "frozen v7 scientific contract is not the expected base object",
        "prereg-action-qbc-v7-open-failure-decomposition-v1",
        "runtime_v7_enabled",
        "scripts/run_action_qbc_v7_open_diagnostic.py",
        "src/arc3_voi/action_qbc_v7_audit.py",
        "src/arc3_voi/action_qbc_v7_reference.py",
        "tests/test_action_qbc_v7_audit.py",
        "v7 audit",
        "v7 open-freeze",
        "v7 reference",
        "v7 result",
        "v7 runner",
        "v7_audit_entry",
        "v7_audit_raw",
        "v7_reference_entry",
        "v7_registration",
        "v7_registration_entry",
        "v7_runner_entry",
        "v7_terminal_entry",
        *windows_repository_v7_literals,
    }
    audit_source = (ROOT / "src/arc3_voi/action_qbc_v8_audit.py").read_bytes()
    assert hashlib.sha256(audit_source).hexdigest() == (
        "130dcc271799f035b571e30cc41304c2c3046ddf866eb80b3bbe4b0428c21444"
    )
    audit_imports = {
        alias.name
        for node in ast.walk(trees["src/arc3_voi/action_qbc_v8_audit.py"])
        if isinstance(node, ast.ImportFrom) and node.level == 1
        for alias in node.names
        if "v7" in alias.name.lower()
    }
    assert audit_imports == {"action_qbc_v7_reference"}

    reconstructor_tree = trees[
        "scripts/reconstruct_action_qbc_v8_open_registration.py"
    ]
    parents = {
        child: parent
        for parent in ast.walk(reconstructor_tree)
        for child in ast.iter_child_nodes(parent)
    }
    v7_path_names = {
        "V7_REGISTRATION_PATH",
        "V7_TERMINAL_PATH",
        "V7_AUDIT_PATH",
        "V7_REFERENCE_PATH",
        "V7_RUNNER_PATH",
    }
    function_reads: list[str] = []
    replacement_uses: list[str] = []
    for node in ast.walk(reconstructor_tree):
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in v7_path_names
        ):
            continue
        parent = parents[node]
        if isinstance(parent, ast.Call):
            assert isinstance(parent.func, ast.Name)
            assert parent.func.id == "_blob_at"
            function_reads.append(node.id)
            continue
        ancestor: ast.AST | None = parent
        while ancestor is not None and not isinstance(ancestor, ast.AnnAssign):
            ancestor = parents.get(ancestor)
        assert isinstance(ancestor, ast.AnnAssign)
        assert isinstance(ancestor.target, ast.Name)
        assert ancestor.target.id == "AUDIT_REPLACEMENTS"
        replacement_uses.append(node.id)
    assert sorted(function_reads) == sorted(v7_path_names)
    assert replacement_uses == ["V7_REGISTRATION_PATH"]


def test_verification_record_has_one_stable_canonical_shape() -> None:
    registration = {
        "content_sha256": "a" * 64,
        "source_manifest": {"manifest_sha256": "b" * 64},
    }
    record = reconstruction.verification_record(registration, "c" * 40)
    assert set(record) == {
        "schema_version", "status", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "registration_file_sha256", "source_manifest_sha256",
    }
    assert record["status"] == "verified"
    assert record["registration_file_sha256"] == hashlib.sha256(
        reconstruction.canonical_json_bytes(registration)
    ).hexdigest()


@pytest.mark.skipif(os.name != "posix", reason="Linux no-follow venv inventory contract")
def test_independent_record_inventory_normalizes_dotdot_and_rejects_duplicate_targets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "clone"
    site = root / ".venv/lib/python3.12/site-packages"
    bin_path = root / ".venv/bin"
    site.mkdir(parents=True)
    bin_path.mkdir()
    specifications = (
        ("arc3_crosslevel_voi-0.1.0.dist-info", "arc3-crosslevel-voi", "0.1.0", "arc3_marker.py"),
        ("numpy-2.5.1.dist-info", "numpy", "2.5.1", "numpy_marker.py"),
        ("PyYAML-6.0.3.dist-info", "PyYAML", "6.0.3", "yaml_marker.py"),
    )
    for dist_info, name, version, marker in specifications:
        metadata = site / dist_info
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            encoding="utf-8",
        )
        (site / marker).write_bytes(f"{name}\n".encode("ascii"))
        record_paths = [
            marker,
            f"{dist_info}/METADATA",
            f"{dist_info}/RECORD",
        ]
        if name == "numpy":
            (bin_path / "f2py").write_bytes(b"entrypoint\n")
            record_paths.append("../../../bin/f2py")
        (metadata / "RECORD").write_text(
            "".join(f"{path},,\n" for path in record_paths),
            encoding="utf-8",
        )
    inventory = reconstruction._environment_inventory(root)
    assert [row["normalized_name"] for row in inventory] == [
        "arc3-crosslevel-voi", "numpy", "pyyaml",
    ]
    assert [row["file_count"] for row in inventory] == [3, 4, 3]
    assert all(set(row) == {"normalized_name", "version", "file_count", "files_sha256"} for row in inventory)

    pyyaml_record = site / "PyYAML-6.0.3.dist-info/RECORD"
    pyyaml_record.write_text(
        pyyaml_record.read_text(encoding="utf-8") + "../../../bin/f2py,,\n",
        encoding="utf-8",
    )
    with pytest.raises(reconstruction.ReconstructionError, match="duplicate normalized RECORD path"):
        reconstruction._environment_inventory(root)


@pytest.mark.skipif(os.name != "posix", reason="Linux recursive venv identity contract")
def test_independent_venv_materialization_binds_mode_and_symlink_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "clone"
    bin_path = root / ".venv/bin"
    lib_path = root / ".venv/lib"
    bin_path.mkdir(parents=True)
    lib_path.mkdir()
    target = tmp_path / "python-real"
    target.write_bytes(b"synthetic-python-bytes")
    target.chmod(0o755)
    (bin_path / "python3").symlink_to(target)
    payload = lib_path / "payload.bin"
    payload.write_bytes(b"payload")
    payload.chmod(0o640)

    first = reconstruction._venv_materialization_sha256(root)
    assert reconstruction._resolved_venv_python_sha256(root) == hashlib.sha256(
        b"synthetic-python-bytes"
    ).hexdigest()
    payload.chmod(0o600)
    second = reconstruction._venv_materialization_sha256(root)
    assert second != first
    (bin_path / "python3").unlink()
    other = tmp_path / "python-other"
    other.write_bytes(b"synthetic-python-bytes")
    other.chmod(0o755)
    (bin_path / "python3").symlink_to(other)
    third = reconstruction._venv_materialization_sha256(root)
    assert third != second


def _full_preparation_ledger(
    execution_root: Path,
    execution: dict[str, object],
    *,
    attempt_index: int = 1,
    open_commit: str = "a" * 40,
    entries: list[tuple[str, str, str, int | None]] | None = None,
) -> list[dict[str, object]]:
    tree_entries = entries or [("synthetic", "100644", "9" * 40, 1)]
    authority = Path(str(execution["authority_root"]))
    identities = [
        *reconstruction._expected_authority_identities(
            authority,
            open_commit,
            tree_entries,
        ),
        *reconstruction._expected_attempt_identities(
            execution,
            execution_root,
            attempt_index,
            open_commit,
            tree_entries,
        ),
    ]
    rows: list[dict[str, object]] = []
    for sequence_index, identity in enumerate(identities):
        stdout = b""
        rows.append(
            {
                **identity,
                "sequence_index": sequence_index,
                "started": True,
                "exit_code": 0,
                "outcome": "completed",
                "timed_out": False,
                "duration_milliseconds": 1,
                "stdout_size_bytes": len(stdout),
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_size_bytes": 0,
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "child_cleanup_passes": None,
            }
        )
    return rows


_SYNTHETIC_LEDGER_ENTRIES = [("synthetic", "100644", "9" * 40, 1)]


def _valid_command_ledger_fixture(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], Path]:
    execution_root = tmp_path / "execution"
    execution = {
        "authority_root": str(execution_root / "authority"),
        "environment_build_argv": ["/usr/bin/env", "UV_OFFLINE=1"],
        "preflight_argvs": [[f"preflight-{index}"] for index in range(5)],
        "preparation_command_environment": reconstruction.PREPARATION_COMMAND_ENVIRONMENT,
    }
    ledger = _full_preparation_ledger(
        execution_root,
        execution,
        entries=_SYNTHETIC_LEDGER_ENTRIES,
    )
    receipt = {
        "open_freeze_commit_sha": "a" * 40,
        "status": "prepared",
        "command_ledger": ledger,
        "commands_sha256": reconstruction.canonical_sha256(ledger),
        "command_environment_sha256": reconstruction.canonical_sha256(
            reconstruction.PREPARATION_COMMAND_ENVIRONMENT
        ),
    }
    return receipt, execution, execution_root


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("sequence_index", 1, "contiguous"),
        ("argv_sha256", "0" * 64, "argv hash"),
        ("stdout_size_bytes", 134_217_730, "cap\\+1"),
        ("outcome", "spawn_error", "unstarted outcome"),
        ("duration_milliseconds", -1, "nonnegative"),
    ),
)
def test_independent_command_ledger_rejects_mutated_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    monkeypatch.setattr(
        reconstruction,
        "_tree_entries",
        lambda _root, _commit: _SYNTHETIC_LEDGER_ENTRIES,
    )
    receipt, execution, execution_root = _valid_command_ledger_fixture(tmp_path)
    row = receipt["command_ledger"][0]
    assert isinstance(row, dict)
    row[field] = value
    receipt["commands_sha256"] = reconstruction.canonical_sha256(receipt["command_ledger"])
    with pytest.raises(reconstruction.ReconstructionError, match=message):
        reconstruction._validate_command_ledger(receipt, execution, execution_root, 1)


def test_independent_command_ledger_rejects_environment_and_keyset_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reconstruction,
        "_tree_entries",
        lambda _root, _commit: _SYNTHETIC_LEDGER_ENTRIES,
    )
    receipt, execution, execution_root = _valid_command_ledger_fixture(tmp_path)
    row = receipt["command_ledger"][0]
    assert isinstance(row, dict)
    row["invented"] = True
    receipt["commands_sha256"] = reconstruction.canonical_sha256(receipt["command_ledger"])
    with pytest.raises(reconstruction.ReconstructionError, match="exact key set"):
        reconstruction._validate_command_ledger(receipt, execution, execution_root, 1)

    receipt, execution, execution_root = _valid_command_ledger_fixture(tmp_path)
    environment = dict(reconstruction.PREPARATION_COMMAND_ENVIRONMENT)
    environment["INHERITED_SECRET"] = "forbidden"
    execution["preparation_command_environment"] = environment
    receipt["command_environment_sha256"] = reconstruction.canonical_sha256(environment)
    with pytest.raises(reconstruction.ReconstructionError, match="environment differs"):
        reconstruction._validate_command_ledger(receipt, execution, execution_root, 1)


def test_independent_command_ledger_reconstructs_exact_argv_and_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reconstruction,
        "_tree_entries",
        lambda _root, _commit: _SYNTHETIC_LEDGER_ENTRIES,
    )
    receipt, execution, execution_root = _valid_command_ledger_fixture(tmp_path)
    ledger = receipt["command_ledger"]
    assert isinstance(ledger, list)
    clone = next(
        row for row in ledger
        if isinstance(row, dict) and row.get("phase") == "clone"
    )
    argv = clone["argv"]
    assert isinstance(argv, list)
    argv[-2] = "file:///invented-source"
    clone["argv_sha256"] = reconstruction.canonical_sha256(argv)
    receipt["commands_sha256"] = reconstruction.canonical_sha256(ledger)
    with pytest.raises(reconstruction.ReconstructionError, match="invented command"):
        reconstruction._validate_command_ledger(receipt, execution, execution_root, 1)

    receipt, execution, execution_root = _valid_command_ledger_fixture(tmp_path)
    ledger = receipt["command_ledger"]
    assert isinstance(ledger, list)
    batch = next(
        row for row in ledger
        if isinstance(row, dict)
        and row.get("attempt_index") == 1
        and row.get("argv", [])[-2:] == ["cat-file", "--batch"]
    )
    batch["stdin_size_bytes"] = 0
    batch["stdin_sha256"] = hashlib.sha256(b"").hexdigest()
    receipt["commands_sha256"] = reconstruction.canonical_sha256(ledger)
    with pytest.raises(reconstruction.ReconstructionError, match="invented command"):
        reconstruction._validate_command_ledger(receipt, execution, execution_root, 1)


def test_offline_help_does_not_require_registration_or_scientific_imports() -> None:
    invocations = (
        ("scripts/build_action_qbc_v8_open_registration.py", [], "--preregistration-tag"),
        ("scripts/execute_action_qbc_v8_open_lifecycle.py", ["execute"], "--preparation-receipt"),
        ("scripts/execute_action_qbc_v8_open_lifecycle.py", ["publish"], "--finalization-bundle"),
        ("scripts/finalize_action_qbc_v8_open_diagnostic.py", [], "--lifecycle-ledger"),
        ("scripts/prepare_action_qbc_v8_open.py", ["prepare"], "--execution-root"),
        ("scripts/prepare_action_qbc_v8_open.py", ["arm"], "--windows-claim"),
        ("scripts/reconstruct_action_qbc_v8_open_registration.py", [], "--verify-preparation"),
        ("scripts/run_action_qbc_v8_open_diagnostic.py", [], "--start-claim"),
        ("scripts/supervise_action_qbc_v8_remote_tag.py", [], "--verifier-start-claim"),
        ("scripts/validate_action_qbc_v8_open_payload.py", [], "--validator-claim"),
        ("scripts/verify_action_qbc_v8_remote_tag.py", [], "--max-attempts"),
    )
    assert {row[0] for row in invocations} == {
        "scripts/build_action_qbc_v8_open_registration.py",
        "scripts/execute_action_qbc_v8_open_lifecycle.py",
        "scripts/finalize_action_qbc_v8_open_diagnostic.py",
        "scripts/prepare_action_qbc_v8_open.py",
        "scripts/reconstruct_action_qbc_v8_open_registration.py",
        "scripts/run_action_qbc_v8_open_diagnostic.py",
        "scripts/supervise_action_qbc_v8_remote_tag.py",
        "scripts/validate_action_qbc_v8_open_payload.py",
        "scripts/verify_action_qbc_v8_remote_tag.py",
    }
    for script, prefix, expected_flag in invocations:
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(ROOT / script), *prefix, "--help"],
            cwd=ROOT,
            env={"PYTHONNOUSERSITE": "1", "UV_OFFLINE": "1"},
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert "--repository-root" in completed.stdout
        assert expected_flag in completed.stdout


def test_preparation_schema_keysets_and_status_are_fail_closed() -> None:
    assert {
        "schema_version", "treatment_id", "open_freeze_commit_sha", "open_freeze_tag",
        "registration_content_sha256", "attempts", "authority", "process_a", "process_b",
        "command_ledger", "commands_sha256", "command_environment_sha256", "status",
    } == reconstruction._PREPARATION_KEYS
    with pytest.raises(reconstruction.ReconstructionError, match="exact key set"):
        reconstruction._exact_keys(
            {"schema_version": "action-qbc-v8-preparation-receipt-v2", "unexpected": True},
            reconstruction._PREPARATION_KEYS,
            "preparation receipt",
        )
    with pytest.raises(reconstruction.ReconstructionError, match="one or two attempts"):
        reconstruction._validate_attempts([], Path("/var/tmp/unused-v8-test-root"))
