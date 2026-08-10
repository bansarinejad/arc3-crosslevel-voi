# ruff: noqa: E501
"""Independently reconstruct and byte-verify the v7 open registration.

This program is deliberately standard-library-only and does not import the producer or any
project module.  It parses the frozen preregistration for public data identities, rebuilds
the source manifests, maps, rows, contracts, and command hashes, then compares canonical
bytes.  It never imports or executes scientific code or the public scene generator.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

SCHEMA_VERSION: Final = "action-qbc-v7-open-registration-v1"
STATUS: Final = "registered_zero_result"
TREATMENT_ID: Final = "action-qbc-v7-open-failure-decomposition-v1"
DIAGNOSTIC_SYSTEM_ID: Final = "crosslevel-voi-open-diagnostic-v7"
COMPARISON_SEMANTICS_ID: Final = "action-qbc-v7-boundary-compound-selector-decomposition-v1"
PREREGISTRATION_TAG: Final = "prereg-action-qbc-v7-open-failure-decomposition-v1"
PREREGISTRATION_DOCUMENT: Final = "docs/experiment_amendment_2026-08-10_action_qbc_v7_open_failure_decomposition.md"
V6_COMMIT: Final = "6a7f6fb25b7e676d6aff5aecaaa26de63e436481"
V6_JSON_PATH: Final = "artifacts/action_qbc_v6_open_gate_result.json"
V6_DOCUMENT_PATH: Final = "docs/action_qbc_v6_open_gate_result.md"
V6_JSON_SHA256: Final = "853394f0b68bddaac9b5c1840e8afa51ffeba444920b132ad45b8d53740c751d"
V6_VECTOR_SHA256: Final = "589070b5ba1dbe5c400ec462a41ea0e8098462fc59f041b673e99da823370055"
V6_DOCUMENT_SHA256: Final = "a3bf5b20291d1b35f65b7fa20de7b9c6247ba918265eab588c6a34f66ff64c59"
RAW_POLICY_SHA256: Final = "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
CONTROL_SHA256: Final = "44d08c5867f0c6842151e371263d2e25cdf550da7199c29801ed8c22f4afb9f7"
REGISTRATION_PATH: Final = "artifacts/action_qbc_v7_open_registration.json"
OPEN_FREEZE_TAG: Final = "action-qbc-v7-open-diagnostic-freeze-v1"
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
ALL_ADDITIONS: Final = tuple(sorted((*NON_REGISTRATION_ADDITIONS, REGISTRATION_PATH)))
AUTHORIZATION: Final = {
    "lockbox_generation_authorized": False,
    "sealed_execution_authorized": False,
    "runtime_admission_authorized": False,
    "runtime_v7_enabled": False,
    "final_admission_claimed": False,
}
GLOBAL_STAGES: Final = (
    "transform_action_map_invalid", "scientific_record_inventory_invalid",
    "grid_evidence_table_invalid", "expected_exterior_support_table_invalid",
    "evaluator_internal_error", "payload_size_limit_exceeded",
)
ADMIN_STAGES: Final = (
    "tag_verification_failed", "execution_root_setup_failed", "clone_a_failed",
    "clone_b_failed", "environment_a_failed", "environment_b_failed",
    "preflight_a_failed", "preflight_b_failed", "registration_invalid",
    "process_a_nonzero", "process_a_output_missing", "process_a_payload_invalid",
    "process_b_nonzero", "process_b_output_missing", "process_b_payload_invalid",
    "payload_byte_mismatch", "receipt_finalization_failed", "exclusive_publication_failed",
    "publication_rollback_failed",
)


class ReconstructionError(RuntimeError):
    """Raised when independent reconstruction cannot prove exact registration identity."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _strict_object(raw: bytes) -> dict[str, object]:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ReconstructionError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ReconstructionError(f"non-finite JSON number: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs_hook, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReconstructionError("registration is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ReconstructionError("registration must be a JSON object")
    if canonical_json_bytes(value) != raw:
        raise ReconstructionError("registration bytes are not canonical compact ASCII JSON")
    return value


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(root), *arguments), input=input_bytes,
        check=False, capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReconstructionError(f"local Git query failed ({' '.join(arguments)}): {detail}")
    return completed.stdout


def _hex(value: str, length: int, label: str) -> None:
    if len(value) != length or any(character not in "0123456789abcdef" for character in value):
        raise ReconstructionError(f"{label} is not lowercase {length}-hex")


def _preregistration_commit(root: Path) -> str:
    if _git(root, "cat-file", "-t", PREREGISTRATION_TAG).strip() != b"commit":
        raise ReconstructionError("preregistration tag is not lightweight")
    commit = _git(root, "rev-parse", PREREGISTRATION_TAG).decode("ascii").strip()
    _hex(commit, 40, "preregistration commit")
    if _git(root, "rev-parse", f"{commit}^").decode("ascii").strip() != V6_COMMIT:
        raise ReconstructionError("P is not a direct child of the frozen v6 result")
    delta = _git(root, "diff", "--name-status", "-z", V6_COMMIT, commit)
    expected = b"A\0" + PREREGISTRATION_DOCUMENT.encode() + b"\0"
    if delta != expected:
        raise ReconstructionError("P contains more than the one amendment addition")
    return commit


def _tree_entries(root: Path, commit: str) -> list[tuple[str, str, int]]:
    raw = _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit)
    rows: list[tuple[str, str, int]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, tab, path_bytes = record.partition(b"\t")
        fields = metadata.split()
        if not tab or len(fields) != 4 or fields[1] != b"blob":
            raise ReconstructionError("malformed/non-blob P tree entry")
        path = path_bytes.decode("utf-8")
        oid = fields[2].decode("ascii")
        _hex(oid, 40, f"blob {path}")
        rows.append((path, oid, int(fields[3])))
    rows.sort(key=lambda row: row[0])
    if not rows or len({row[0] for row in rows}) != len(rows):
        raise ReconstructionError("P tree is empty or has duplicate paths")
    return rows


def _batch_blobs(root: Path, entries: Sequence[tuple[str, str, int]]) -> list[bytes]:
    request = b"".join(oid.encode() + b"\n" for _, oid, _ in entries)
    response = _git(root, "cat-file", "--batch", input_bytes=request)
    offset = 0
    result: list[bytes] = []
    for path, oid, size in entries:
        newline = response.find(b"\n", offset)
        if newline < 0:
            raise ReconstructionError("truncated cat-file batch header")
        fields = response[offset:newline].split()
        if fields != [oid.encode(), b"blob", str(size).encode()]:
            raise ReconstructionError(f"unexpected cat-file header for {path}")
        start, end = newline + 1, newline + 1 + size
        if end >= len(response) or response[end : end + 1] != b"\n":
            raise ReconstructionError(f"truncated cat-file blob for {path}")
        result.append(response[start:end])
        offset = end + 1
    if offset != len(response):
        raise ReconstructionError("cat-file batch response has trailing data")
    return result


def _p_manifest(root: Path, commit: str) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    entries = _tree_entries(root, commit)
    blobs = _batch_blobs(root, entries)
    manifest: list[dict[str, object]] = []
    by_path: dict[str, bytes] = {}
    for (path, oid, size), raw in zip(entries, blobs, strict=True):
        calculated = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False
        ).hexdigest()
        if calculated != oid or len(raw) != size:
            raise ReconstructionError(f"P blob identity mismatch: {path}")
        by_path[path] = raw
        manifest.append(
            {"path": path, "git_blob_sha1": oid, "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": size}
        )
    return manifest, by_path


def _plain_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ReconstructionError(f"required plain file absent: {relative}")
    return path.read_bytes()


def _added_manifest(root: Path) -> list[dict[str, object]]:
    rows = []
    for relative in sorted(NON_REGISTRATION_ADDITIONS):
        raw = _plain_bytes(root, relative)
        oid = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False
        ).hexdigest()
        observed = _git(root, "hash-object", "--no-filters", relative).decode().strip()
        if observed != oid:
            raise ReconstructionError(f"worktree race or filter drift: {relative}")
        rows.append(
            {"path": relative, "git_blob_sha1": oid, "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}
        )
    return rows


def _repository_phase(root: Path, preregistration_commit: str) -> bool:
    """Validate the exact allowlist and return true only in a clean O checkout."""

    head = _git(root, "rev-parse", "HEAD").decode().strip()
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if head == preregistration_commit:
        seen: set[str] = set()
        for record in status.split(b"\0"):
            if not record:
                continue
            if len(record) < 4 or record[2:3] != b" ":
                raise ReconstructionError("malformed pre-O Git status")
            path = record[3:].decode("utf-8")
            if record[:2] != b"A " or path not in ALL_ADDITIONS:
                raise ReconstructionError(f"non-allowlisted pre-O path: {path}")
            seen.add(path)
        if seen != set(ALL_ADDITIONS):
            raise ReconstructionError("pre-O reconstruction requires exactly ten additions")
        if _git(root, "diff", "--name-status", "-z") != b"":
            raise ReconstructionError("pre-O worktree differs from its staged bytes")
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
            b"A\0" + path.encode() + b"\0" for path in ALL_ADDITIONS
        )
        if cached != expected_cached:
            raise ReconstructionError("index is not the exact ten staged additions")
        tracked = _git(root, "diff", "--name-status", "--no-renames", "-z", preregistration_commit)
        tokens = tracked.split(b"\0")
        for offset in range(0, len(tokens) - 1, 2):
            if tokens[offset] != b"A" or tokens[offset + 1].decode() not in ALL_ADDITIONS:
                raise ReconstructionError("P existing bytes changed before O")
        return False
    if status != b"":
        raise ReconstructionError("O checkout is not byte-clean")
    if _git(root, "rev-parse", f"{head}^").decode().strip() != preregistration_commit:
        raise ReconstructionError("O is not a direct child of P")
    delta = _git(root, "diff", "--name-status", "--no-renames", "-z", preregistration_commit, head)
    expected = b"".join(b"A\0" + path.encode() + b"\0" for path in ALL_ADDITIONS)
    if delta != expected:
        raise ReconstructionError("P..O is not the exact ten-addition delta")
    if _git(root, "cat-file", "-t", OPEN_FREEZE_TAG).strip() != b"commit":
        raise ReconstructionError("open-freeze tag is absent or annotated")
    if _git(root, "rev-parse", OPEN_FREEZE_TAG).decode().strip() != head:
        raise ReconstructionError("open-freeze tag does not resolve to HEAD")
    return True


def _fence_after(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        raise ReconstructionError(f"amendment marker absent: {marker}")
    fence = text.find("```", start + len(marker))
    if fence < 0:
        raise ReconstructionError(f"amendment fence absent after: {marker}")
    line_end = text.find("\n", fence)
    close = text.find("```", line_end + 1)
    if line_end < 0 or close < 0:
        raise ReconstructionError(f"unterminated amendment fence after: {marker}")
    return text[line_end + 1 : close].strip("\n")


def _name_block(text: str, marker: str) -> list[str]:
    block = _fence_after(text, marker)
    values = [line.strip() for line in block.splitlines() if line.strip()]
    if any(" " in value for value in values) or len(values) != len(set(values)):
        raise ReconstructionError(f"invalid name block after: {marker}")
    return values


def _json_block(text: str, marker: str) -> object:
    block = _fence_after(text, marker)
    try:
        return json.loads(block)
    except json.JSONDecodeError as error:
        raise ReconstructionError(f"invalid amendment JSON block after: {marker}") from error


def _parse_scenes(text: str) -> list[dict[str, object]]:
    identity_pattern = re.compile(
        r"^\| (homologue|containment|reflection) \| ([0-3]) \| `([0-9a-f]{16})` \| `([0-9a-f]{64})` \|$",
        re.MULTILINE,
    )
    palette_pattern = re.compile(
        r"^\| (homologue|containment|reflection) \| ([0-3]) \| ([0-9]+) \| ([0-9]+) \| `(\[[0-9, ]+\])` \|$",
        re.MULTILINE,
    )
    identities = [(family, int(index), seed, digest) for family, index, seed, digest in identity_pattern.findall(text)]
    palettes = []
    for family, index, background, destination, raw_palette in palette_pattern.findall(text):
        palette = json.loads(raw_palette)
        palettes.append((family, int(index), int(background), int(destination), palette))
    if len(identities) != 12 or len(palettes) != 12:
        raise ReconstructionError("amendment does not contain exactly twelve scene table rows")
    expected_order = [(family, index) for family in ("homologue", "containment", "reflection") for index in range(4)]
    if [(row[0], row[1]) for row in identities] != expected_order or [(row[0], row[1]) for row in palettes] != expected_order:
        raise ReconstructionError("scene table order differs from the frozen family/index order")
    fixed_zero = {
        "homologue": "1020304050607080", "containment": "2233445566778899",
        "reflection": "3141592653589793",
    }
    scenes: list[dict[str, object]] = []
    for identity, palette_row in zip(identities, palettes, strict=True):
        family, index, seed, digest = identity
        _, _, background, destination, palette = palette_row
        if index == 0:
            expected_seed = fixed_zero[family]
        else:
            material = f"action-qbc-v7-open-extension-v1|{family}|{index}".encode()
            expected_seed = hashlib.sha256(material).digest()[:8].hex()
        if seed != expected_seed:
            raise ReconstructionError(f"scene seed formula mismatch: {family}/{index}")
        if sorted(palette) != list(range(16)) or palette[background] != destination:
            raise ReconstructionError(f"palette table mismatch: {family}/{index}")
        scenes.append(
            {
                "family": family, "scene_index": index, "seed_hex": seed,
                "scene_sha256": digest, "background_label": background,
                "source_shape": [32, 32], "available_actions": ["ACTION3", "ACTION6"],
                "palette_forward": palette,
            }
        )
    return scenes


def _action_map_hash(name: str, kind: str, contract_hash: str, destination_shape: list[int]) -> str:
    rows: list[list[list[int]]] = []
    for source_row in range(32):
        for source_col in range(32):
            if name == "palette_bijection":
                destination = [source_row, source_col]
            elif name in {"translation_row_plus_3_col_plus_5", "translation_row_minus_3_col_minus_5"}:
                dr, dc = ((3, 5) if "plus" in name else (-3, -5))
                if kind == "actual":
                    destination = [source_row + dr, source_col + dc]
                    if not (0 <= destination[0] < 32 and 0 <= destination[1] < 32):
                        continue
                else:
                    destination = [source_row + abs(dr) + dr, source_col + abs(dc) + dc]
            elif name == "scale_2_nearest_neighbor":
                destination = [source_row * 2, source_col * 2]
            else:
                raise ReconstructionError(f"unknown transform in map: {name}")
            rows.append([[source_row, source_col], destination])
    return canonical_sha256(
        {
            "schema_version": "action-qbc-v7-action-map-v1", "map_kind": kind,
            "transform_contract_sha256": contract_hash, "source_shape": [32, 32],
            "destination_shape": destination_shape, "simple_actions": ["ACTION3"],
            "action6_forward": rows,
        }
    )


def _transform(scene: Mapping[str, object], name: str) -> dict[str, object]:
    background = cast(int, scene["background_label"])
    palette = cast(list[int], scene["palette_forward"])
    if name == "palette_bijection":
        actual = isolated = [32, 32]
        destination_background = palette[background]
        parameters: dict[str, object] = {"forward_palette": palette}
    elif name == "translation_row_plus_3_col_plus_5":
        actual, isolated, destination_background = [32, 32], [38, 42], background
        parameters = {"delta_row": 3, "delta_col": 5}
    elif name == "translation_row_minus_3_col_minus_5":
        actual, isolated, destination_background = [32, 32], [38, 42], background
        parameters = {"delta_row": -3, "delta_col": -5}
    elif name == "scale_2_nearest_neighbor":
        actual = isolated = [64, 64]
        destination_background = background
        parameters = {"factor": 2}
    else:
        raise ReconstructionError(f"unknown transform contract: {name}")
    preimage = {
        "schema_version": "action-qbc-v7-transform-contract-v1",
        "family": scene["family"], "scene_index": scene["scene_index"],
        "transform_name": name, "source_shape": [32, 32],
        "actual_destination_shape": actual, "isolated_destination_shape": isolated,
        "source_background_label": background,
        "destination_background_label": destination_background, "parameters": parameters,
    }
    digest = canonical_sha256(preimage)
    result = {key: value for key, value in preimage.items() if key != "schema_version"}
    result.update(
        {
            "contract_sha256": digest,
            "actual_action_map_sha256": _action_map_hash(name, "actual", digest, actual),
            "isolated_action_map_sha256": _action_map_hash(name, "isolated", digest, isolated),
        }
    )
    return result


def _rows_and_transforms(
    scenes: list[dict[str, object]], visual_names: list[str], order_contracts: list[dict[str, object]],
    controls: list[str], predicates: list[str],
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, int | str]]]:
    transforms = [_transform(scene, name) for scene in scenes for name in visual_names]
    transform_lookup = {
        (row["family"], row["scene_index"], row["transform_name"]): row for row in transforms
    }
    rows: list[dict[str, object]] = []
    for scene in scenes:
        family, index = scene["family"], scene["scene_index"]
        rows.append(
            {"row_index": len(rows), "row_id": f"base:{family}:{index}", "kind": "base_scene", "registered_placeholder": True, "family": family, "scene_index": index, "seed_hex": scene["seed_hex"], "scene_sha256": scene["scene_sha256"]}
        )
    for scene in scenes:
        family, index = scene["family"], scene["scene_index"]
        for name in visual_names:
            contract = transform_lookup[(family, index, name)]
            rows.append(
                {"row_index": len(rows), "row_id": f"visual:{family}:{index}:{name}", "kind": "visual_transform", "registered_placeholder": True, "family": family, "scene_index": index, "seed_hex": scene["seed_hex"], "scene_sha256": scene["scene_sha256"], "transform_name": name, "transform_contract_sha256": contract["contract_sha256"], "actual_action_map_sha256": contract["actual_action_map_sha256"], "isolated_action_map_sha256": contract["isolated_action_map_sha256"]}
            )
    order_names = [cast(str, contract["name"]) for contract in order_contracts]
    hashes = {cast(str, contract["name"]): canonical_sha256(contract) for contract in order_contracts}
    for scene in scenes:
        family, index = scene["family"], scene["scene_index"]
        for name in order_names:
            rows.append(
                {"row_index": len(rows), "row_id": f"order:{family}:{index}:{name}", "kind": "order_transform", "registered_placeholder": True, "family": family, "scene_index": index, "seed_hex": scene["seed_hex"], "scene_sha256": scene["scene_sha256"], "transform_name": name, "order_contract_sha256": hashes[name]}
            )
    call_counts = [1] * 14 + [0, 0, 0, 1, 2, 2]
    ledger: list[dict[str, int | str]] = []
    for index, (control, predicate, calls) in enumerate(zip(controls, predicates, call_counts, strict=True)):
        fixed_suffix = "compound_canonical_invariant" if index == 19 else "legacy_record_pass"
        rows.append(
            {"row_index": len(rows), "row_id": f"control:{control}", "kind": "control", "registered_placeholder": True, "control_id": control, "control_index": index, "raw_selector_call_count": calls, "fixed_selector_call_count": calls, "control_contract_sha256": CONTROL_SHA256, "raw_predicate_id": f"{predicate}:legacy_record_pass", "fixed_predicate_id": f"{predicate}:{fixed_suffix}"}
        )
        ledger.append(
            {"control_id": control, "raw_selector_call_count": calls, "fixed_selector_call_count": calls}
        )
    if len(rows) != 140 or [row["row_index"] for row in rows] != list(range(140)):
        raise ReconstructionError("independent row plan is not 140 contiguous addresses")
    return transforms, {
        "count": 140,
        "order": "base-all-scenes_then-visual-all-scenes_then-order-all-scenes_then-controls-v1",
        "rows": rows,
    }, ledger


def _expected_counts(scene_count: int, visual_count: int, order_count: int, control_calls: int) -> dict[str, int]:
    pipelines = scene_count * (visual_count + 1)
    candidate_pipelines = scene_count * 4
    order_rows = scene_count * order_count
    raw_scene = candidate_pipelines * 3 + scene_count + order_rows
    fixed_scene = pipelines + order_rows
    isolated = scene_count * visual_count * 2
    result = {
        "public_scene_generations": scene_count, "registered_scene_file_reads": 0,
        "candidate_builder_calls": candidate_pipelines, "compiler_calls": pipelines,
        "compiled_programs": pipelines * 4, "grounding_evaluations": pipelines * 4,
        "hypothesis_pool_constructions": pipelines, "persistent_worker_starts": pipelines * 4,
        "transient_worker_starts": pipelines * 4, "total_worker_starts": pipelines * 8,
        "planner_calls": pipelines, "completed_planning_snapshots": pipelines,
        "controller_calls": candidate_pipelines * 2, "controller_snapshot_replays": candidate_pipelines * 2,
        "v4_counterfactual_calls": scene_count, "raw_selector_scene_order_calls": raw_scene,
        "raw_selector_control_calls": control_calls, "fixed_selector_scene_order_calls": fixed_scene,
        "fixed_selector_control_calls": control_calls, "isolated_raw_selector_calls": isolated,
        "isolated_fixed_selector_calls": isolated,
        "pure_selector_calls": raw_scene + control_calls + fixed_scene + control_calls + isolated * 2,
        "model_calls": 0, "generated_tokens": 0, "gpu_operations": 0, "network_calls": 0,
        "environment_actions": 0, "reward_observations": 0, "rhae_observations": 0,
        "lockbox_path_operations": 0, "lockbox_bytes_read": 0,
    }
    if len(result) != 31 or result["pure_selector_calls"] != 566:
        raise ReconstructionError("independent resource call graph differs from frozen vector")
    return result


def _legacy_adapter(text: str) -> dict[str, object]:
    field_map = _json_block(text, "`field_map` maps legacy names")
    if not isinstance(field_map, dict):
        raise ReconstructionError("legacy field-map block is not an object")
    return {
        "field_map": field_map,
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
    }


def _raw_selector() -> dict[str, object]:
    return {
        "module": "arc3_voi.action_qbc_policy", "callable": "select_action_conditional_qbc",
        "policy_version": "action-conditional-outcome-qbc-v1",
        "runtime_version": "crosslevel-voi-runtime-v5", "source_bundle_sha256": RAW_POLICY_SHA256,
    }


def _execution() -> dict[str, object]:
    root = "/var/tmp/arc3-crosslevel-voi-action-qbc-v7-open"
    a_root, b_root = f"{root}/process-a", f"{root}/process-b"
    a_output = f"{root}/process-a-output/open/action_qbc_v7_open_diagnostic.json"
    b_output = f"{root}/process-b-output/open/action_qbc_v7_open_diagnostic.json"
    producer = ["uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B", "scripts/build_action_qbc_v7_open_registration.py", "--repository-root", ".", "--preregistration-tag", PREREGISTRATION_TAG, "--output", REGISTRATION_PATH]
    reconstructor = ["uv", "run", "--frozen", "--extra", "dev", "python3", "-I", "-B", "scripts/reconstruct_action_qbc_v7_open_registration.py", "--repository-root", ".", "--registration", REGISTRATION_PATH]
    tag_step = {"argv": ["git", "ls-remote", "--tags", "https://github.com/bansarinejad/arc3-crosslevel-voi.git", f"refs/tags/{OPEN_FREEZE_TAG}"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": f"<O_COMMIT>\trefs/tags/{OPEN_FREEZE_TAG}\n"}
    setup = [
        {"argv": ["/usr/bin/test", "!", "-e", root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["install", "-d", "-m", "700", root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "clone", "--branch", OPEN_FREEZE_TAG, "--single-branch", "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi", a_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "clone", "--branch", OPEN_FREEZE_TAG, "--single-branch", "file:///mnt/d/kaggle%20competitions/arc3-crosslevel-voi", b_root], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["git", "-C", a_root, "rev-parse", "HEAD"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": "<O_COMMIT>\n"},
        {"argv": ["git", "-C", b_root, "rev-parse", "HEAD"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": "<O_COMMIT>\n"},
        {"argv": ["install", "-d", "-m", "700", f"{root}/process-a-output/open"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
        {"argv": ["install", "-d", "-m", "700", f"{root}/process-b-output/open"], "cwd": "/var/tmp", "expected_exit_code": 0, "expected_stdout": ""},
    ]
    environment = ["/usr/bin/env", "UV_OFFLINE=1", "uv", "sync", "--python", "3.12.13", "--frozen", "--no-dev", "--offline"]
    preflight = [["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], ["git", "rev-parse", "HEAD"], [".venv/bin/python3", "--version"], ["uv", "--version"], [".venv/bin/python3", "-I", "-B", "scripts/reconstruct_action_qbc_v7_open_registration.py", "--repository-root", ".", "--registration", REGISTRATION_PATH]]
    scientific = ["/usr/bin/timeout", "--foreground", "--signal=TERM", "--kill-after=15s", "2700s", ".venv/bin/python3", "-I", "-B", "scripts/run_action_qbc_v7_open_diagnostic.py", "--repository-root", ".", "--registration", REGISTRATION_PATH, "--compute-deadline-seconds", "2100", "--wall-time-seconds", "2400", "--output", "<OUTPUT_PATH>"]
    tests = [["uv", "run", "--frozen", "--extra", "dev", "pytest", "-q", "tests/test_action_qbc_v7_audit.py", "tests/test_action_qbc_v7_registration.py"], ["uv", "run", "--frozen", "--extra", "dev", "ruff", "check", "src/arc3_voi/action_qbc_v7_reference.py", "src/arc3_voi/action_qbc_v7_audit.py", "scripts/build_action_qbc_v7_open_registration.py", "scripts/finalize_action_qbc_v7_open_diagnostic.py", "scripts/reconstruct_action_qbc_v7_open_registration.py", "scripts/run_action_qbc_v7_open_diagnostic.py", "tests/test_action_qbc_v7_audit.py", "tests/test_action_qbc_v7_registration.py"], ["uv", "run", "--frozen", "--extra", "dev", "mypy", "src/arc3_voi/action_qbc_v7_reference.py", "src/arc3_voi/action_qbc_v7_audit.py"]]
    finalizer = ["/usr/bin/python3", "-I", "-B", "scripts/finalize_action_qbc_v7_open_diagnostic.py", "--repository-root", ".", "--registration", REGISTRATION_PATH, "--process-a", a_output, "--process-b", b_output, "--process-a-exit-code", "<A_EXIT_CODE>", "--process-b-exit-code", "<B_EXIT_CODE_OR_NULL>", "--lifecycle-stage", "<STAGE_OR_NULL>", "--publish", "artifacts/action_qbc_v7_open_diagnostic.json", "--receipt", "artifacts/action_qbc_v7_open_diagnostic_receipt.json", "--administrative-terminal", "artifacts/action_qbc_v7_open_diagnostic_administrative_terminal.json"]
    hashes = {"producer": canonical_sha256(producer), "reconstructor": canonical_sha256(reconstructor), "tag_verification": canonical_sha256(tag_step), "setup": canonical_sha256(setup), "environment_build": canonical_sha256(environment), "preflight": canonical_sha256(preflight), "scientific": canonical_sha256(scientific), "tests": canonical_sha256(tests), "finalizer": canonical_sha256(finalizer)}
    return {
        "compute_deadline_seconds": 2100, "wall_time_seconds": 2400, "hard_timeout_seconds": 2700,
        "registered_start_count": 2, "process_labels": ["A", "B"], "execution_root": root,
        "process_a_root": a_root, "process_b_root": b_root, "process_a_output": a_output,
        "process_b_output": b_output, "producer_argv": producer, "reconstructor_argv": reconstructor,
        "tag_verification_step": tag_step, "setup_steps": setup, "environment_build_argv": environment,
        "preflight_argvs": preflight, "scientific_argv_template": scientific, "test_argvs": tests,
        "finalizer_argv_template": finalizer, "finalizer_cwd": "/mnt/d/kaggle competitions/arc3-crosslevel-voi",
        "argv_hashes": hashes, "administrative_stage_order": list(ADMIN_STAGES), "third_start_allowed": False,
    }


def reconstruct_registration(repository_root: str | Path) -> tuple[dict[str, object], bool]:
    """Independently build expected registration and report whether this is clean O."""

    root = Path(repository_root).resolve(strict=True)
    p_commit = _preregistration_commit(root)
    clean_o = _repository_phase(root, p_commit)
    p_tree, blobs = _p_manifest(root, p_commit)
    document_raw = blobs.get(PREREGISTRATION_DOCUMENT)
    if document_raw is None:
        raise ReconstructionError("P amendment blob is absent")
    try:
        document_text = document_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReconstructionError("P amendment is not UTF-8") from error
    added = _added_manifest(root)
    source_manifest: dict[str, object] = {
        "preregistration_tree": p_tree, "open_freeze_added_files": added,
    }
    source_manifest["manifest_sha256"] = canonical_sha256(source_manifest)
    scenes = _parse_scenes(document_text)
    visual_names = _name_block(document_text, "The four visual transform identifiers")
    order_names = _name_block(document_text, "The five order transform identifiers")
    controls = _name_block(document_text, "The twenty control identifiers")
    role_order = _name_block(document_text, "The frozen role order is")
    reason_order = _name_block(document_text, "The global scientific reason vocabulary")
    aggregate_keys = _name_block(document_text, "`aggregates` has exactly these keys")
    predicates = re.findall(r"^\| `(c[0-9]{2}_[^`]+)` \|", document_text, re.MULTILINE)
    if len(predicates) != 20 or len(set(predicates)) != 20:
        raise ReconstructionError("control predicate table is not exactly twenty unique rows")
    order_contracts_obj = _json_block(document_text, "`order_contracts` is an additional exact field")
    if not isinstance(order_contracts_obj, list) or not all(isinstance(row, dict) for row in order_contracts_obj):
        raise ReconstructionError("order-contract amendment block is malformed")
    order_contracts = cast(list[dict[str, object]], order_contracts_obj)
    if [row.get("name") for row in order_contracts] != order_names:
        raise ReconstructionError("order name block and contracts disagree")
    transforms, row_inventory, ledger = _rows_and_transforms(
        scenes, visual_names, order_contracts, controls, predicates
    )
    increment_obj = _json_block(document_text, "The exact increment members are")
    if not isinstance(increment_obj, dict):
        raise ReconstructionError("increment amendment block is not an object")
    increment = dict(increment_obj)
    increment["legacy_adapter"] = _legacy_adapter(document_text)
    counts = _expected_counts(len(scenes), len(visual_names), len(order_names), sum(row["raw_selector_call_count"] for row in ledger))
    partition = [
        *cast(list[str], increment["before_attempt"]), *cast(list[str], increment["after_success"]),
        *cast(list[str], increment["on_observation"]), *cast(dict[str, str], increment["derived"]).keys(),
    ]
    if len(partition) != len(set(partition)) or set(partition) != set(counts):
        raise ReconstructionError("increment classes do not partition all 31 counters")
    raw_selector = _raw_selector()
    fixed_selector = {
        "version": "action-qbc-v7-compound-selector-2^-40-dense-canonical-v1",
        "raw_selector_identity": raw_selector, "quantum_numerator": 1,
        "quantum_denominator": 1099511627776, "rank_policy": "dense_by_integer_key",
        "tie_set_policy": "complete_integer_key_ties", "singleton_tie_break": "canonical_action_order",
        "positive_utility_gate": "integer_key_strictly_greater_than_zero",
    }
    v6_json = blobs.get(V6_JSON_PATH)
    v6_doc = blobs.get(V6_DOCUMENT_PATH)
    if v6_json is None or v6_doc is None:
        raise ReconstructionError("v6 anchors are absent from P tree")
    if hashlib.sha256(v6_json).hexdigest() != V6_JSON_SHA256 or hashlib.sha256(v6_doc).hexdigest() != V6_DOCUMENT_SHA256:
        raise ReconstructionError("v6 file anchor mismatch")
    try:
        vector = json.loads(v6_json)["failing_visuals"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ReconstructionError("cannot reconstruct v6 failure vector") from error
    if canonical_sha256(vector) != V6_VECTOR_SHA256:
        raise ReconstructionError("v6 failure-vector digest mismatch")
    document_entry = next(row for row in p_tree if row["path"] == PREREGISTRATION_DOCUMENT)
    without: dict[str, object] = {
        "schema_version": SCHEMA_VERSION, "status": STATUS, "treatment_id": TREATMENT_ID,
        "diagnostic_system_id": DIAGNOSTIC_SYSTEM_ID,
        "comparison_semantics_id": COMPARISON_SEMANTICS_ID, "runtime_id": None,
        "preregistration": {"commit_sha": p_commit, "tag": PREREGISTRATION_TAG, "document_path": PREREGISTRATION_DOCUMENT, "document_git_blob_sha1": document_entry["git_blob_sha1"], "document_sha256": document_entry["sha256"]},
        "v6_negative": {"result_commit_sha": V6_COMMIT, "result_json_path": V6_JSON_PATH, "result_json_sha256": V6_JSON_SHA256, "failure_vector_sha256": V6_VECTOR_SHA256, "result_document_sha256": V6_DOCUMENT_SHA256},
        "platform": {"python_version": "3.12.13", "python_implementation": "CPython", "platform_system": "Linux", "platform_machine": "x86_64", "uv_version": "0.11.28"},
        "dependencies": [{"name": "arc3-crosslevel-voi", "version": "0.1.0", "editable": True}, {"name": "numpy", "version": "2.5.1", "editable": False}, {"name": "PyYAML", "version": "6.0.3", "editable": False}],
        "source_manifest": source_manifest,
        "scene_inventory": {"count": 12, "scenes": scenes}, "row_inventory": row_inventory,
        "transform_contracts": transforms,
        "scientific_contract": {"role_order": role_order, "raw_selector_identity": raw_selector, "fixed_selector_identity": fixed_selector, "absolute_tolerance": 1e-12, "relative_tolerance": 1e-12, "fixed_quantum_numerator": 1, "fixed_quantum_denominator": 1099511627776, "reason_order": reason_order, "grid_evidence_schema": "action-qbc-v7-grid-evidence-table-v1", "expected_exterior_support_schema": "action-qbc-v7-expected-exterior-support-table-v1", "aggregate_keys": aggregate_keys, "global_fallback_stage_order": list(GLOBAL_STAGES), "payload_cap_bytes": 67108864, "order_contracts": order_contracts},
        "resource_contract": {"expected_counts": counts, "control_call_ledger": ledger, "control_contract_sha256": CONTROL_SHA256, "increment_contract": increment},
        "execution_contract": _execution(), "authorization": dict(AUTHORIZATION),
    }
    if len(without) != 18:
        raise ReconstructionError("independent registration preimage is not eighteen keys")
    result = dict(without)
    result["content_sha256"] = canonical_sha256(without)
    return result, clean_o


def _normalize_project_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _verify_clean_o_environment() -> None:
    if sys.version_info[:3] != (3, 12, 13) or platform.python_implementation() != "CPython":
        raise ReconstructionError("preflight Python is not CPython 3.12.13")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ReconstructionError("preflight platform is not Linux x86_64")
    uv = subprocess.run(("uv", "--version"), check=False, capture_output=True)
    if uv.returncode != 0 or uv.stdout.decode("utf-8", errors="strict").strip() != "uv 0.11.28":
        raise ReconstructionError("preflight uv is not exactly 0.11.28")
    distributions: dict[str, importlib.metadata.Distribution] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not isinstance(name, str):
            raise ReconstructionError("installed distribution lacks a canonical Name")
        normalized = _normalize_project_name(name)
        if normalized in distributions:
            raise ReconstructionError(f"duplicate normalized distribution: {normalized}")
        distributions[normalized] = distribution
    expected = {
        "arc3-crosslevel-voi": ("0.1.0", True), "numpy": ("2.5.1", False),
        "pyyaml": ("6.0.3", False),
    }
    if set(distributions) != set(expected):
        raise ReconstructionError("preflight distribution inventory is not the exact three packages")
    for name, (version, editable) in expected.items():
        distribution = distributions[name]
        if distribution.version != version:
            raise ReconstructionError(f"preflight version mismatch: {name}")
        direct_text = distribution.read_text("direct_url.json")
        direct: object = None if direct_text is None else json.loads(direct_text)
        observed_editable = (
            isinstance(direct, Mapping)
            and isinstance(direct.get("dir_info"), Mapping)
            and direct["dir_info"].get("editable") is True
        )
        if observed_editable is not editable:
            raise ReconstructionError(f"preflight editable flag mismatch: {name}")


def verify_registration(repository_root: str | Path, registration_path: str | Path) -> dict[str, object]:
    root = Path(repository_root).resolve(strict=True)
    path = (root / registration_path).resolve()
    if path != (root / REGISTRATION_PATH).resolve() or path.is_symlink() or not path.is_file():
        raise ReconstructionError("registration path is not the canonical plain repository file")
    raw = path.read_bytes()
    supplied = _strict_object(raw)
    expected, clean_o = reconstruct_registration(root)
    expected_raw = canonical_json_bytes(expected)
    if raw != expected_raw or supplied != expected:
        raise ReconstructionError("registration bytes differ from independent reconstruction")
    content = supplied.get("content_sha256")
    preimage = dict(supplied)
    preimage.pop("content_sha256", None)
    if content != canonical_sha256(preimage):
        raise ReconstructionError("registration content hash does not bind its other eighteen keys")
    if clean_o:
        _verify_clean_o_environment()
    return supplied


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registration = verify_registration(args.repository_root, args.registration)
    raw = canonical_json_bytes(registration)
    print(
        json.dumps(
            {"content_sha256": registration["content_sha256"], "file_sha256": hashlib.sha256(raw).hexdigest(), "row_count": 140, "status": "verified"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReconstructionError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error), "status": "refused"}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from error
