"""Independent, zero-result registration tests for the v7 open diagnostic."""

from __future__ import annotations

import ast
import copy
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.build_action_qbc_v7_open_registration as producer
import scripts.finalize_action_qbc_v7_open_diagnostic as finalizer
import scripts.reconstruct_action_qbc_v7_open_registration as reconstruction
import scripts.run_action_qbc_v7_open_diagnostic as runner

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / producer.PREREGISTRATION_DOCUMENT
REGISTRATION = ROOT / producer.OUTPUT_PATH


def _document_text() -> str:
    return AMENDMENT.read_text(encoding="utf-8")


def _process_observation(
    label: str,
    output_path: str,
    payload: bytes,
) -> finalizer._ProcessObservation:
    return finalizer._ProcessObservation(
        record={
            "label": label,
            "output_path": output_path,
            "exit_code": 0,
            "payload_exists": True,
            "payload_valid": True,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_size_bytes": len(payload),
        },
        data=payload,
    )


def _publication_inputs(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    bytes,
    dict[str, Any],
    finalizer._Registration,
    finalizer._RepositoryIdentity,
    finalizer._ProcessObservation,
    finalizer._ProcessObservation,
]:
    payload_path = tmp_path / "action_qbc_v7_open_diagnostic.json"
    receipt_path = tmp_path / "action_qbc_v7_open_diagnostic_receipt.json"
    administrative_path = tmp_path / "action_qbc_v7_open_diagnostic_administrative_terminal.json"
    payload = b'{"schema_version":"synthetic-valid-payload"}'
    registration = finalizer._Registration(
        value={"content_sha256": "a" * 64},
        data=b"{}",
        file_sha256="b" * 64,
        path_text=producer.OUTPUT_PATH,
    )
    repository = finalizer._RepositoryIdentity(commit_sha="c" * 40, tag_valid=True)
    process_a = _process_observation("A", finalizer._EXPECTED_PROCESS_A, payload)
    process_b = _process_observation("B", finalizer._EXPECTED_PROCESS_B, payload)
    receipt = finalizer._receipt_object(
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
        publish_text=finalizer._EXPECTED_PUBLISH,
    )
    return (
        payload_path,
        receipt_path,
        administrative_path,
        payload,
        receipt,
        registration,
        repository,
        process_a,
        process_b,
    )


def test_canonical_json_has_one_ascii_no_lf_representation() -> None:
    value = {"z": [1, True, None, "\N{SNOWMAN}"], "a": {"x": 1e-12}}
    raw = producer.canonical_json_bytes(value)
    assert raw == reconstruction.canonical_json_bytes(value)
    assert raw == b'{"a":{"x":1e-12},"z":[1,true,null,"\\u2603"]}'
    assert not raw.endswith(b"\n")
    assert producer.canonical_sha256(value) == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{ "x":1}',
        b'{"x":1}\n',
        b'[]',
        b'\xff',
    ],
)
def test_strict_registration_parser_rejects_ambiguous_or_noncanonical_json(raw: bytes) -> None:
    with pytest.raises(reconstruction.ReconstructionError):
        reconstruction._strict_object(raw)


def test_preregistration_is_exact_direct_child_and_document_blob_is_bound() -> None:
    commit = producer._resolve_preregistration(ROOT, producer.PREREGISTRATION_TAG)
    assert commit == "f4a267757a7abbd72bc1aeb86e98811c521bf574"
    manifest = producer._preregistration_manifest(ROOT, commit)
    assert len(manifest) == 215
    assert [row["path"] for row in manifest] == sorted(row["path"] for row in manifest)
    assert len({row["path"] for row in manifest}) == 215
    document = next(row for row in manifest if row["path"] == producer.PREREGISTRATION_DOCUMENT)
    assert document == {
        "path": producer.PREREGISTRATION_DOCUMENT,
        "git_blob_sha1": "4ccb19e94fcacd19af488123281c4a8ec34041f6",
        "sha256": "fcd284ce499983fcc953f54a9f833e1b6d80a822384768f75cb18948d627a1a7",
        "byte_count": 137738,
    }


def test_reconstructor_has_a_standard_library_only_import_boundary() -> None:
    path = ROOT / "scripts/reconstruct_action_qbc_v7_open_registration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    permitted = {
        "__future__",
        "argparse",
        "hashlib",
        "importlib",
        "json",
        "platform",
        "re",
        "subprocess",
        "sys",
        "collections",
        "pathlib",
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
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "build_action_qbc_v7_open_registration",
        "action_qbc_v7_audit",
        "action_qbc_v7_reference",
        "action_qbc_v6_audit",
        "action_qbc_policy",
        "action_qbc_lockbox",
    ):
        assert f"import {forbidden}" not in source
        assert f"from arc3_voi.{forbidden}" not in source
        assert f"from scripts.{forbidden}" not in source


def test_finalizer_has_a_standard_library_only_import_boundary() -> None:
    path = ROOT / "scripts/finalize_action_qbc_v7_open_diagnostic.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    permitted = {
        "__future__",
        "argparse",
        "base64",
        "binascii",
        "collections",
        "contextlib",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "platform",
        "stat",
        "struct",
        "subprocess",
        "sys",
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


def test_runner_starts_offline_without_entering_scientific_evaluation() -> None:
    environment = os.environ.copy()
    environment["UV_OFFLINE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/run_action_qbc_v7_open_diagnostic.py"),
            "--help",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Run one registered action-QBC v7 open diagnostic process" in completed.stdout
    assert "--compute-deadline-seconds" in completed.stdout


def test_runner_rejects_programmatic_argv_before_any_scientific_work(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("scientific or registration work must not start")

    monkeypatch.setattr(runner, "load_registration", forbidden)
    monkeypatch.setattr(runner, "produce_scientific_candidate", forbidden)
    return_code = runner.main(
        [
            "--repository-root",
            ".",
            "--registration",
            producer.OUTPUT_PATH,
            "--compute-deadline-seconds",
            "2100",
            "--wall-time-seconds",
            "2400",
            "--output",
            finalizer._EXPECTED_PROCESS_A,
        ]
    )
    captured = capsys.readouterr()
    assert return_code == 2
    assert "programmatic argv is not permitted" in captured.err


def test_receipt_link_failure_rolls_back_owned_payload_and_publishes_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        payload_path,
        receipt_path,
        administrative_path,
        payload,
        receipt,
        registration,
        repository,
        process_a,
        process_b,
    ) = _publication_inputs(tmp_path)
    monkeypatch.setattr(finalizer, "_validate_payload_bytes", lambda *_args: {})
    real_link = finalizer._exclusive_link

    def fail_receipt_link(staged: finalizer._StagedFile, destination: Path) -> None:
        if destination == receipt_path:
            raise OSError("injected receipt-link failure")
        real_link(staged, destination)

    monkeypatch.setattr(finalizer, "_exclusive_link", fail_receipt_link)
    succeeded, stage = finalizer._publish_success(
        payload_final=payload_path,
        receipt_final=receipt_path,
        administrative_final=administrative_path,
        payload_data=payload,
        receipt=receipt,
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
    )

    assert succeeded is True
    assert stage == "exclusive_publication_failed"
    assert not payload_path.exists()
    assert not receipt_path.exists()
    terminal = finalizer._parse_canonical_json(
        administrative_path.read_bytes(), "administrative terminal"
    )
    assert terminal["stage"] == "exclusive_publication_failed"
    assert sorted(path.name for path in tmp_path.iterdir()) == [administrative_path.name]


def test_receipt_link_failure_with_unproved_ownership_retains_orphan_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        payload_path,
        receipt_path,
        administrative_path,
        payload,
        receipt,
        registration,
        repository,
        process_a,
        process_b,
    ) = _publication_inputs(tmp_path)
    monkeypatch.setattr(finalizer, "_validate_payload_bytes", lambda *_args: {})
    monkeypatch.setattr(finalizer, "_owned_final", lambda *_args: False)
    real_link = finalizer._exclusive_link

    def fail_receipt_link(staged: finalizer._StagedFile, destination: Path) -> None:
        if destination == receipt_path:
            raise OSError("injected receipt-link failure")
        real_link(staged, destination)

    monkeypatch.setattr(finalizer, "_exclusive_link", fail_receipt_link)
    succeeded, stage = finalizer._publish_success(
        payload_final=payload_path,
        receipt_final=receipt_path,
        administrative_final=administrative_path,
        payload_data=payload,
        receipt=receipt,
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
    )

    assert succeeded is True
    assert stage == "publication_rollback_failed"
    assert payload_path.read_bytes() == payload
    assert not receipt_path.exists()
    terminal = finalizer._parse_canonical_json(
        administrative_path.read_bytes(), "administrative terminal"
    )
    assert terminal["stage"] == "publication_rollback_failed"
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        [payload_path.name, administrative_path.name]
    )


@pytest.mark.parametrize("preexisting", ["payload", "receipt", "administrative"])
def test_preexisting_publication_destinations_are_never_overwritten_or_adopted(
    preexisting: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        payload_path,
        receipt_path,
        administrative_path,
        payload,
        receipt,
        registration,
        repository,
        process_a,
        process_b,
    ) = _publication_inputs(tmp_path)
    destinations = {
        "payload": payload_path,
        "receipt": receipt_path,
        "administrative": administrative_path,
    }
    foreign = b"foreign-preexisting-bytes"
    destinations[preexisting].write_bytes(foreign)
    monkeypatch.setattr(finalizer, "_validate_payload_bytes", lambda *_args: {})

    succeeded, stage = finalizer._publish_success(
        payload_final=payload_path,
        receipt_final=receipt_path,
        administrative_final=administrative_path,
        payload_data=payload,
        receipt=receipt,
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
    )

    assert stage == "exclusive_publication_failed"
    assert destinations[preexisting].read_bytes() == foreign
    if preexisting == "administrative":
        assert succeeded is False
        assert not payload_path.exists()
        assert not receipt_path.exists()
    else:
        assert succeeded is True
        terminal = finalizer._parse_canonical_json(
            administrative_path.read_bytes(), "administrative terminal"
        )
        assert terminal["stage"] == "exclusive_publication_failed"


def test_administrative_terminal_creation_failure_leaves_no_adopted_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        payload_path,
        receipt_path,
        administrative_path,
        payload,
        receipt,
        registration,
        repository,
        process_a,
        process_b,
    ) = _publication_inputs(tmp_path)
    foreign = b"foreign-payload"
    payload_path.write_bytes(foreign)

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected administrative-link failure")

    monkeypatch.setattr(finalizer, "_exclusive_link", fail_link)
    succeeded, stage = finalizer._publish_success(
        payload_final=payload_path,
        receipt_final=receipt_path,
        administrative_final=administrative_path,
        payload_data=payload,
        receipt=receipt,
        registration=registration,
        repository=repository,
        process_a=process_a,
        process_b=process_b,
    )

    assert succeeded is False
    assert stage == "exclusive_publication_failed"
    assert payload_path.read_bytes() == foreign
    assert not receipt_path.exists()
    assert not administrative_path.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == [payload_path.name]


def test_public_scene_tables_parse_and_seed_formula_is_independent() -> None:
    scenes = reconstruction._parse_scenes(_document_text())
    assert len(scenes) == 12
    assert [(row["family"], row["scene_index"]) for row in scenes] == [
        (family, index)
        for family in ("homologue", "containment", "reflection")
        for index in range(4)
    ]
    assert scenes[0]["seed_hex"] == "1020304050607080"
    assert scenes[1]["seed_hex"] == hashlib.sha256(
        b"action-qbc-v7-open-extension-v1|homologue|1"
    ).digest()[:8].hex()
    assert all(sorted(row["palette_forward"]) == list(range(16)) for row in scenes)
    for row in scenes:
        palette = row["palette_forward"]
        assert isinstance(palette, list)
        assert row["source_shape"] == [32, 32]
        assert row["available_actions"] == ["ACTION3", "ACTION6"]


def test_scene_parser_rejects_seed_and_palette_table_tampering() -> None:
    text = _document_text()
    with pytest.raises(reconstruction.ReconstructionError, match="seed formula"):
        reconstruction._parse_scenes(text.replace("82c9dc349d88e442", "82c9dc349d88e443", 1))
    bad_palette = text.replace(
        "[4,2,3,13,1,8,10,12,5,11,14,6,9,15,0,7]",
        "[4,2,3,13,1,8,10,12,5,11,14,6,9,15,0,0]",
        1,
    )
    with pytest.raises(reconstruction.ReconstructionError, match="palette table"):
        reconstruction._parse_scenes(bad_palette)


def test_producer_regenerates_exact_public_scene_metadata() -> None:
    inventory, generated = producer._scene_inventory()
    independently_parsed = reconstruction._parse_scenes(_document_text())
    assert inventory == {"count": 12, "scenes": independently_parsed}
    assert len(generated) == 12
    assert [row["content_sha256"] for row in generated] == [
        row["scene_sha256"] for row in independently_parsed
    ]


def test_transform_contracts_and_action_maps_are_independently_identical() -> None:
    scene_inventory, _ = producer._scene_inventory()
    producer_transforms, producer_rows = producer._transforms_and_rows(scene_inventory)
    text = _document_text()
    scenes = reconstruction._parse_scenes(text)
    visual_names = reconstruction._name_block(text, "The four visual transform identifiers")
    controls = reconstruction._name_block(text, "The twenty control identifiers")
    predicate_pattern = r"^\| `(c[0-9]{2}_[^`]+)` \|"
    predicates = reconstruction.re.findall(predicate_pattern, text, reconstruction.re.MULTILINE)
    order_contracts = reconstruction._json_block(
        text, "`order_contracts` is an additional exact field"
    )
    assert isinstance(order_contracts, list)
    reconstructed_transforms, reconstructed_rows, _ = reconstruction._rows_and_transforms(
        scenes,
        visual_names,
        order_contracts,
        controls,
        predicates,
    )
    assert producer_transforms == reconstructed_transforms
    assert producer_rows == reconstructed_rows
    assert len(producer_transforms) == 48
    positive = next(
        row
        for row in producer_transforms
        if row["family"] == "homologue"
        and row["scene_index"] == 0
        and row["transform_name"] == "translation_row_plus_3_col_plus_5"
    )
    assert positive["actual_destination_shape"] == [32, 32]
    assert positive["isolated_destination_shape"] == [38, 42]
    assert positive["actual_action_map_sha256"] != positive["isolated_action_map_sha256"]


def test_map_preimages_have_exact_complete_and_partial_cardinalities() -> None:
    contract_hash = "0" * 64
    palette = {
        "actual": producer._action_map_hash(
            "palette_bijection", "actual", contract_hash, [32, 32]
        ),
        "isolated": producer._action_map_hash(
            "palette_bijection", "isolated", contract_hash, [32, 32]
        ),
    }
    assert palette["actual"] != palette["isolated"]  # map_kind is identity-bearing.
    # Independently construct the partial positive-translation list: 29 * 27 entries.
    action6 = [
        [[row, col], [row + 3, col + 5]]
        for row in range(29)
        for col in range(27)
    ]
    preimage = {
        "schema_version": "action-qbc-v7-action-map-v1",
        "map_kind": "actual",
        "transform_contract_sha256": contract_hash,
        "source_shape": [32, 32],
        "destination_shape": [32, 32],
        "simple_actions": ["ACTION3"],
        "action6_forward": action6,
    }
    assert len(action6) == 783
    assert producer._action_map_hash(
        "translation_row_plus_3_col_plus_5", "actual", contract_hash, [32, 32]
    ) == producer.canonical_sha256(preimage)


def test_row_inventory_has_exact_addresses_schemas_and_control_ledger() -> None:
    scene_inventory = {"count": 12, "scenes": reconstruction._parse_scenes(_document_text())}
    _, inventory = producer._transforms_and_rows(scene_inventory)
    rows = inventory["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 140
    assert [row["row_index"] for row in rows] == list(range(140))
    assert rows[0]["row_id"] == "base:homologue:0"
    assert rows[11]["row_id"] == "base:reflection:3"
    assert rows[12]["row_id"] == "visual:homologue:0:palette_bijection"
    assert rows[59]["row_id"] == "visual:reflection:3:scale_2_nearest_neighbor"
    assert rows[60]["row_id"] == "order:homologue:0:candidate_list_reversal"
    assert rows[119]["row_id"].startswith("order:reflection:3:")
    assert rows[120]["row_id"] == "control:identical_signatures_A1"
    assert rows[139]["row_id"] == "control:candidate_tie_pair"
    assert [row["raw_selector_call_count"] for row in rows[120:]] == [
        *([1] * 14), 0, 0, 0, 1, 2, 2
    ]
    assert rows[139]["fixed_predicate_id"].endswith(":compound_canonical_invariant")


def test_resource_contract_is_derived_and_partitioned_exactly_once() -> None:
    contract = producer._resource_contract()
    counts = contract["expected_counts"]
    assert isinstance(counts, dict)
    assert len(counts) == 31
    assert counts["public_scene_generations"] == 12
    assert counts["compiler_calls"] == 60
    assert counts["raw_selector_scene_order_calls"] == 216
    assert counts["fixed_selector_scene_order_calls"] == 120
    assert counts["isolated_raw_selector_calls"] == 96
    assert counts["isolated_fixed_selector_calls"] == 96
    assert counts["pure_selector_calls"] == 566
    assert counts["total_worker_starts"] == 480
    increment = contract["increment_contract"]
    assert isinstance(increment, dict)
    partition = [
        *increment["before_attempt"],
        *increment["after_success"],
        *increment["on_observation"],
        *increment["derived"],
    ]
    assert len(partition) == len(set(partition)) == 31
    assert set(partition) == set(counts)
    assert sum(row["raw_selector_call_count"] for row in contract["control_call_ledger"]) == 19
    assert increment["legacy_adapter"]["ignored_fields"] == [
        "pure_selector_calls", "total_worker_starts"
    ]


def test_scientific_contract_exact_lists_are_parsed_from_amendment() -> None:
    contract = producer._scientific_contract()
    text = _document_text()
    assert contract["role_order"] == reconstruction._name_block(text, "The frozen role order is")
    assert contract["reason_order"] == reconstruction._name_block(
        text, "The global scientific reason vocabulary"
    )
    assert contract["aggregate_keys"] == reconstruction._name_block(
        text, "`aggregates` has exactly these keys"
    )
    assert contract["payload_cap_bytes"] == 67_108_864
    fixed = contract["fixed_selector_identity"]
    assert fixed["quantum_numerator"] == 1
    assert fixed["quantum_denominator"] == 2**40
    assert fixed["raw_selector_identity"] == contract["raw_selector_identity"]


def test_execution_contract_hashes_exact_preimages_and_frozen_cwds() -> None:
    execution = producer._execution_contract()
    assert execution == reconstruction._execution()
    assert set(execution) == {
        "compute_deadline_seconds", "wall_time_seconds", "hard_timeout_seconds",
        "registered_start_count", "process_labels", "execution_root", "process_a_root",
        "process_b_root", "process_a_output", "process_b_output", "producer_argv",
        "reconstructor_argv", "tag_verification_step", "setup_steps",
        "environment_build_argv", "preflight_argvs", "scientific_argv_template",
        "test_argvs", "finalizer_argv_template", "finalizer_cwd", "argv_hashes",
        "administrative_stage_order", "third_start_allowed",
    }
    hashes = execution["argv_hashes"]
    preimages = {
        "producer": execution["producer_argv"],
        "reconstructor": execution["reconstructor_argv"],
        "tag_verification": execution["tag_verification_step"],
        "setup": execution["setup_steps"],
        "environment_build": execution["environment_build_argv"],
        "preflight": execution["preflight_argvs"],
        "scientific": execution["scientific_argv_template"],
        "tests": execution["test_argvs"],
        "finalizer": execution["finalizer_argv_template"],
    }
    assert hashes == {key: producer.canonical_sha256(value) for key, value in preimages.items()}
    assert execution["finalizer_cwd"] == "/mnt/d/kaggle competitions/arc3-crosslevel-voi"
    assert execution["scientific_argv_template"][-1] == "<OUTPUT_PATH>"
    assert execution["third_start_allowed"] is False


def test_content_hash_excludes_only_itself_and_mutations_change_identity() -> None:
    synthetic = {"a": 1, "authorization": copy.deepcopy(producer.AUTHORIZATION)}
    registration = dict(synthetic)
    registration["content_sha256"] = producer.canonical_sha256(synthetic)
    assert registration["content_sha256"] == producer.canonical_sha256(
        {key: value for key, value in registration.items() if key != "content_sha256"}
    )
    mutated = copy.deepcopy(synthetic)
    mutated["authorization"]["runtime_v7_enabled"] = True
    assert producer.canonical_sha256(mutated) != registration["content_sha256"]


def test_actual_registration_is_exactly_reconstructed_when_present() -> None:
    assert REGISTRATION.is_file(), "build the tenth allowlisted registration before freeze tests"
    supplied = reconstruction.verify_registration(ROOT, producer.OUTPUT_PATH)
    producer_value = producer.build_registration(ROOT, producer.PREREGISTRATION_TAG)
    reconstructed, _clean_o = reconstruction.reconstruct_registration(ROOT)
    assert supplied == producer_value == reconstructed
    assert set(supplied) == {
        "schema_version", "status", "treatment_id", "diagnostic_system_id",
        "comparison_semantics_id", "runtime_id", "preregistration", "v6_negative",
        "platform", "dependencies", "source_manifest", "scene_inventory", "row_inventory",
        "transform_contracts", "scientific_contract", "resource_contract",
        "execution_contract", "authorization", "content_sha256",
    }
    assert supplied["status"] == "registered_zero_result"
    assert supplied["runtime_id"] is None
    assert supplied["authorization"] == producer.AUTHORIZATION
    assert supplied["row_inventory"]["count"] == 140
    raw = REGISTRATION.read_bytes()
    assert raw == producer.canonical_json_bytes(supplied)
    assert not raw.endswith(b"\n")


def test_registration_rejects_every_single_top_level_mutation() -> None:
    assert REGISTRATION.is_file(), "build the registration before mutation tests"
    original = reconstruction._strict_object(REGISTRATION.read_bytes())
    for key in original:
        mutated = copy.deepcopy(original)
        if key == "content_sha256":
            mutated[key] = "0" * 64
        elif isinstance(mutated[key], bool):
            mutated[key] = not mutated[key]
        elif mutated[key] is None:
            mutated[key] = "not-null"
        elif isinstance(mutated[key], str):
            mutated[key] += "-tampered"
        elif isinstance(mutated[key], list):
            mutated[key] = [*mutated[key], None]
        elif isinstance(mutated[key], dict):
            mutated[key] = {**mutated[key], "unexpected": True}
        else:
            raise AssertionError(f"uncovered top-level type for {key}")
        assert producer.canonical_json_bytes(mutated) != REGISTRATION.read_bytes()
        preimage = dict(mutated)
        claimed = preimage.pop("content_sha256", None)
        assert claimed != producer.canonical_sha256(preimage)


def test_forbidden_v7_paths_are_absent_at_open_freeze() -> None:
    forbidden_fragments = ("lockbox", "sealed", "permit", "exposure", "runtime_admission")
    allowed = set(producer.ALL_ADDITIONS)
    unexpected = []
    for path in ROOT.rglob("*v7*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed or relative == producer.PREREGISTRATION_DOCUMENT:
            continue
        lowered = relative.casefold()
        if any(fragment in lowered for fragment in forbidden_fragments):
            unexpected.append(relative)
    assert unexpected == []
