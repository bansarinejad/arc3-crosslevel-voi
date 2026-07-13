"""Deterministic zero-run registration for the dormant runtime-v5 matrix.

This module is deliberately limited to configuration hashing and manifest assembly.  It
does not admit runtime-v5, start a matrix row, construct a model, or access an ARC
environment.  The resulting manifest is registration data, not an execution capability.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from .config import HypothesisSource, SystemConfig, load_config
from .experiment import (
    ArmLabel,
    RunSpec,
    Variant,
    build_source_development_matrix,
    stable_config_hash,
    validate_matrix,
)

REGISTRATION_SCHEMA_VERSION: Final = "action-qbc-zero-run-registration-v1"
REGISTERED_MANIFEST_PATH: Final = Path(
    "artifacts/development_matrix_template_v1_action_conditional_qbc_v1.json"
)
REGISTERED_MANIFEST_SHA256: Final = (
    "6fb58e3c44d9b2cc3a71e12366cd86d3dca7a140df0b120a074e9d01a1d4efe2"
)
REGISTERED_CONFIG_PATH: Final = Path(
    "configs/template_v1_action_conditional_qbc_v1_x.yaml"
)
REGISTERED_CONFIG_FILE_SHA256: Final = (
    "b5067f34dc7934d93b798217ff9e9c29cdc4c5c7af9ab2391d47189012908d11"
)
REGISTERED_SPLIT_PATH: Final = Path("artifacts/public_split.json")
REGISTERED_SPLIT_FILE_SHA256: Final = (
    "0edf4f937be4ed391eb477343fd4fdee32cf6cd255092ae4f1ea617872ab1614"
)
REGISTERED_SNAPSHOT_SHA256: Final = (
    "a72200110a68528ac986c1a20bcbbef2fcf388e53f6432425ccae552234c2fee"
)

REGISTERED_RUNTIME_VERSION: Final = "crosslevel-voi-runtime-v5"
REGISTERED_POLICY_VERSION: Final = "action-conditional-outcome-qbc-v1"
REGISTERED_POLICY_SHA256: Final = (
    "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
)
REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD: Final = 0.8
REGISTERED_COMPLETION_POLICY_VERSION: Final = "path-deficit-v2"
REGISTERED_COMPLETION_POLICY_SHA256: Final = (
    "055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670"
)

REGISTERED_DEVELOPMENT_GAMES: Final = (
    "bp35",
    "cd82",
    "cn04",
    "g50t",
    "lf52",
    "lp85",
    "re86",
    "sb26",
    "sc25",
    "sk48",
    "sp80",
    "tn36",
    "tr87",
    "vc33",
    "wa30",
)
REGISTERED_DEVELOPMENT_SEEDS: Final = (11, 23, 47)
REGISTERED_ARMS: Final = (
    ("D-Q", "D", "qwen"),
    ("S-T", "S", "template_v1"),
    ("M-T", "M", "template_v1"),
    ("X-T", "X", "template_v1"),
)
REGISTERED_ARM_CONFIG_SHA256: Final[Mapping[str, str]] = MappingProxyType(
    {
        "D-Q": "8247eb92b176d471bba365856e28d441b186ddf0396b6fccd9a79b7636f22381",
        "S-T": "0c4dee3abaec89b6b42c75e60fee823099e3a95e49dffda84206fac7079a1094",
        "M-T": "2981a4d4209a7de924e16278eea180d2e4ab1c9b58359733f8c6be1900e4a3fa",
        "X-T": "e612be62a2cebca81062c5791f07af9b5b5c088f565b5cf25852aa41f859d60a",
    }
)

GLOBAL_ZERO_COUNTERS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "matrix_starts": 0,
        "model_calls": 0,
        "generated_tokens": 0,
        "gpu_use_events": 0,
        "environment_actions": 0,
        "reward_observations": 0,
        "rhae_observations": 0,
        "outputs": 0,
    }
)


@dataclass(frozen=True, slots=True)
class ContentAddressedPredecessor:
    """One immutable predecessor matrix admitted only as collision evidence."""

    path: str
    sha256: str


FROZEN_PREDECESSOR_MATRICES: Final = (
    ContentAddressedPredecessor(
        "artifacts/development_matrix.json",
        "ea2dbc2eec0159e63452ab805545021d5101a17882402dd3bc9869fc39241147",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_fair_v2.json",
        "76bcfd53547b4cf4c376bff45fab5511dad4bc30ccf778f2f90e07da88bef495",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_goal_v3_pilot.json",
        "7bf39d2c1ea7c986e7c473069a8647ae8d8677b66ab5a2a510576d00b4bd3816",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_pre_grounding.json",
        "45f3c2c9e8693d23cbf63c4bf12c765785429b084ac30dbf8ba9be5243c28c25",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_runtime_v1.json",
        "b207c451e81ef6f6b815fbd9dc557a7149d221f8af3f7d4034f6d79325580fc7",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_template_v1.json",
        "6878b39d2379d6ffc11d45953db046883a8622ac529e3702efb679b3d9f6978b",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_template_v1_path_deficit_v2.json",
        "949fe7a7455e3637acdeb2ec278ff9822e78a15284854fd730e47a3c84775d5e",
    ),
    ContentAddressedPredecessor(
        "artifacts/development_matrix_visible_causal_v4.json",
        "6f7f5b9f6748cd06335eb269d6afa1277bb9b5d690feba5c082dc609d7e471d9",
    ),
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_content(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ValueError(f"registered input is missing: {path.as_posix()}")
    actual = _file_sha256(path)
    if actual != expected_sha256:
        raise ValueError(
            f"registered input hash mismatch for {path.as_posix()}: "
            f"expected {expected_sha256}, got {actual}"
        )


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.as_posix()}")
    return cast(dict[str, Any], value)


def _validate_registered_identity(config: SystemConfig) -> None:
    actual = (
        config.experiment.implementation_contract_version,
        config.planning.probe_disagreement_policy_version,
        config.planning.probe_disagreement_policy_sha256,
        config.planning.outcome_concentration_threshold,
        config.planning.completion_cost_policy_version,
        config.planning.completion_cost_policy_sha256,
    )
    expected = (
        REGISTERED_RUNTIME_VERSION,
        REGISTERED_POLICY_VERSION,
        REGISTERED_POLICY_SHA256,
        REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD,
        REGISTERED_COMPLETION_POLICY_VERSION,
        REGISTERED_COMPLETION_POLICY_SHA256,
    )
    if actual != expected:
        raise ValueError("runtime-v5 policy/completion identity differs from registration")
    if config.experiment.variant != "X":
        raise ValueError("registered base configuration must be variant X")
    if config.experiment.hypothesis_source != "template_v1":
        raise ValueError("registered base configuration must use template_v1")
    if config.model is None:
        raise ValueError("registered base configuration requires a model profile identity")


def registered_arm_config_hashes(config: SystemConfig) -> dict[ArmLabel, str]:
    """Derive all four semantic identities from one immutable v5 base config."""

    _validate_registered_identity(config)
    hashes: dict[str, str] = {}
    for label_text, variant_text, source in REGISTERED_ARMS:
        variant = cast(Variant, variant_text)
        arm_config = replace(
            config,
            experiment=replace(
                config.experiment,
                variant=variant,
                hypothesis_source=cast(HypothesisSource, source),
            ),
        )
        hashes[label_text] = stable_config_hash(arm_config)
    validate_arm_config_hashes(hashes)
    if hashes != dict(REGISTERED_ARM_CONFIG_SHA256):
        raise ValueError("derived semantic arm config hashes differ from registration")
    return cast(dict[ArmLabel, str], hashes)


def validate_arm_config_hashes(config_hashes: Mapping[str, str]) -> None:
    """Reject incomplete, duplicate, malformed, or eight-prefix-ambiguous hashes."""

    expected_arms = {label for label, _variant, _source in REGISTERED_ARMS}
    if set(config_hashes) != expected_arms:
        raise ValueError("config hashes must exactly cover D-Q, S-T, M-T, and X-T")
    values = tuple(config_hashes[label] for label, _variant, _source in REGISTERED_ARMS)
    if any(
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        for digest in values
    ):
        raise ValueError("every arm config hash must be a lowercase SHA-256 digest")
    if len(set(values)) != len(values):
        raise ValueError("all four full semantic config hashes must be distinct")
    prefixes = tuple(digest[:8] for digest in values)
    if len(set(prefixes)) != len(prefixes):
        raise ValueError("all four semantic config hashes need distinct eight-hex prefixes")


def _registered_split(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = root / REGISTERED_SPLIT_PATH
    _require_content(path, REGISTERED_SPLIT_FILE_SHA256)
    raw = _read_json_object(path)
    development = raw.get("development")
    if not isinstance(development, list) or tuple(development) != REGISTERED_DEVELOPMENT_GAMES:
        raise ValueError("public split does not contain the frozen 15 development games")
    if raw.get("seed") != 20_260_712:
        raise ValueError("public split seed differs from 20260712")
    if raw.get("metadata_hash") != REGISTERED_SNAPSHOT_SHA256:
        raise ValueError("public split metadata hash differs from registration")
    raw_versions = raw.get("game_versions")
    if not isinstance(raw_versions, dict):
        raise ValueError("public split game_versions must be a JSON object")
    versions = {str(game): str(version) for game, version in raw_versions.items()}
    if any(
        game not in versions or not versions[game]
        for game in REGISTERED_DEVELOPMENT_GAMES
    ):
        raise ValueError("every registered development game needs a frozen version")
    return raw, versions


def _predecessor_inventory(root: Path) -> tuple[dict[str, Any], ...]:
    expected_paths = {row.path for row in FROZEN_PREDECESSOR_MATRICES}
    discovered_paths = {
        path.relative_to(root).as_posix()
        for path in (root / "artifacts").glob("development_matrix*.json")
        if path.relative_to(root) != REGISTERED_MANIFEST_PATH
    }
    if discovered_paths != expected_paths:
        missing = sorted(expected_paths - discovered_paths)
        unexpected = sorted(discovered_paths - expected_paths)
        raise ValueError(
            "frozen predecessor inventory mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )

    inventory: list[dict[str, Any]] = []
    for predecessor in FROZEN_PREDECESSOR_MATRICES:
        path = root / predecessor.path
        _require_content(path, predecessor.sha256)
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("runs") if isinstance(raw, dict) else None
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"predecessor matrix is not a non-empty runs list: {predecessor.path}")
        run_ids = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("run_id"), str):
                raise ValueError(f"predecessor row lacks a declared run ID: {predecessor.path}")
            run_ids.append(row["run_id"])
        if len(set(run_ids)) != len(run_ids):
            raise ValueError(f"predecessor matrix contains duplicate run IDs: {predecessor.path}")
        inventory.append(
            {
                "path": predecessor.path,
                "sha256": predecessor.sha256,
                "run_count": len(run_ids),
                "run_ids": frozenset(run_ids),
            }
        )
    return tuple(inventory)


def _build_matrix(
    config: SystemConfig,
    versions: Mapping[str, str],
    hashes: Mapping[ArmLabel, str],
) -> tuple[RunSpec, ...]:
    assert config.model is not None  # established by _validate_registered_identity
    matrix = build_source_development_matrix(
        REGISTERED_DEVELOPMENT_GAMES,
        hypothesis_source="template_v1",
        model_profile=config.model.profile,
        config_hashes=hashes,
        game_versions=versions,
        snapshot_hash=REGISTERED_SNAPSHOT_SHA256,
    )
    validate_matrix(matrix, require_frozen_identity=True)
    if len(matrix) != 180:
        raise ValueError("runtime-v5 registration must contain exactly 180 rows")
    if {row.seed for row in matrix} != set(REGISTERED_DEVELOPMENT_SEEDS):
        raise ValueError("runtime-v5 registration has a non-frozen seed set")
    actual_arms = {
        (row.arm_label, row.variant, row.hypothesis_source, row.identity_version)
        for row in matrix
    }
    expected_arms = {
        (label, variant, source, "source-v2")
        for label, variant, source in REGISTERED_ARMS
    }
    if actual_arms != expected_arms:
        raise ValueError("runtime-v5 registration has a non-frozen source-v2 arm set")
    return matrix


def build_zero_run_registration(repository_root: str | Path) -> dict[str, Any]:
    """Assemble the registered 180-row object without starting any run."""

    root = Path(repository_root).resolve()
    config_path = root / REGISTERED_CONFIG_PATH
    _require_content(config_path, REGISTERED_CONFIG_FILE_SHA256)
    config = load_config(config_path)
    hashes = registered_arm_config_hashes(config)
    assert config.model is not None  # established by registered_arm_config_hashes
    split, versions = _registered_split(root)
    matrix = _build_matrix(config, versions, hashes)
    inventory = _predecessor_inventory(root)

    new_run_ids = {row.run_id for row in matrix}
    for predecessor in inventory:
        collisions = new_run_ids.intersection(cast(frozenset[str], predecessor["run_ids"]))
        if collisions:
            sample = sorted(collisions)[0]
            raise ValueError(
                f"runtime-v5 run-ID collision with {predecessor['path']}: {sample}"
            )

    runs = [
        asdict(row)
        | {
            "run_id": row.run_id,
            "execution_count": 0,
            "output_count": 0,
        }
        for row in matrix
    ]
    predecessor_evidence = [
        {
            "path": predecessor["path"],
            "sha256": predecessor["sha256"],
            "run_count": predecessor["run_count"],
        }
        for predecessor in inventory
    ]
    return {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "status": "registered-zero-run",
        "development_matrix_execution_authorized": False,
        "identity_version": "source-v2",
        "treatment_identity": {
            "implementation_contract_version": REGISTERED_RUNTIME_VERSION,
            "probe_disagreement_policy_version": REGISTERED_POLICY_VERSION,
            "probe_disagreement_policy_sha256": REGISTERED_POLICY_SHA256,
            "outcome_concentration_threshold": (
                REGISTERED_OUTCOME_CONCENTRATION_THRESHOLD
            ),
            "completion_cost_policy_version": REGISTERED_COMPLETION_POLICY_VERSION,
            "completion_cost_policy_sha256": REGISTERED_COMPLETION_POLICY_SHA256,
        },
        "configuration": {
            "path": REGISTERED_CONFIG_PATH.as_posix(),
            "file_sha256": REGISTERED_CONFIG_FILE_SHA256,
            "model_profile": config.model.profile,
            "arm_config_sha256": {
                label: hashes[cast(ArmLabel, label)]
                for label, _variant, _source in REGISTERED_ARMS
            },
        },
        "public_split": {
            "path": REGISTERED_SPLIT_PATH.as_posix(),
            "file_sha256": REGISTERED_SPLIT_FILE_SHA256,
            "metadata_sha256": REGISTERED_SNAPSHOT_SHA256,
            "split_seed": split["seed"],
            "development_games": list(REGISTERED_DEVELOPMENT_GAMES),
            "development_seeds": list(REGISTERED_DEVELOPMENT_SEEDS),
        },
        "frozen_predecessors": predecessor_evidence,
        "global_zero_counters": dict(GLOBAL_ZERO_COUNTERS),
        "runs": runs,
    }


def _require_zero_count(name: str, value: object) -> None:
    if type(value) is not int or value != 0:
        raise ValueError(f"{name} must be the immutable integer zero")


def validate_zero_run_registration(
    registration: Mapping[str, Any], repository_root: str | Path
) -> None:
    """Fail closed on any changed identity, row, predecessor, or zero counter."""

    counters = registration.get("global_zero_counters")
    if not isinstance(counters, Mapping) or set(counters) != set(GLOBAL_ZERO_COUNTERS):
        raise ValueError("global zero-counter schema differs from registration")
    for key in GLOBAL_ZERO_COUNTERS:
        _require_zero_count(f"global_zero_counters.{key}", counters[key])

    runs = registration.get("runs")
    if not isinstance(runs, Sequence) or isinstance(runs, str | bytes):
        raise ValueError("registration runs must be a JSON array")
    if len(runs) != 180:
        raise ValueError("registration must contain exactly 180 run rows")
    for index, row in enumerate(runs):
        if not isinstance(row, Mapping):
            raise ValueError(f"registration run {index} must be a JSON object")
        _require_zero_count(f"runs[{index}].execution_count", row.get("execution_count"))
        _require_zero_count(f"runs[{index}].output_count", row.get("output_count"))

    if registration.get("development_matrix_execution_authorized") is not False:
        raise ValueError("zero-run registration cannot authorize matrix execution")
    expected = build_zero_run_registration(repository_root)
    if dict(registration) != expected:
        raise ValueError("zero-run registration differs from deterministic registered bytes")
    actual_sha256 = registration_payload_sha256(registration)
    if actual_sha256 != REGISTERED_MANIFEST_SHA256:
        raise ValueError(
            "zero-run registration payload hash differs from the frozen identity"
        )


def serialize_zero_run_registration(registration: Mapping[str, Any]) -> str:
    """Return the one canonical UTF-8 JSON representation used by the artifact."""

    return (
        json.dumps(
            registration,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def registration_payload_sha256(registration: Mapping[str, Any]) -> str:
    """Hash the exact canonical bytes written by the deterministic builder."""

    return hashlib.sha256(serialize_zero_run_registration(registration).encode("utf-8")).hexdigest()


__all__ = [
    "FROZEN_PREDECESSOR_MATRICES",
    "GLOBAL_ZERO_COUNTERS",
    "REGISTERED_ARMS",
    "REGISTERED_ARM_CONFIG_SHA256",
    "REGISTERED_CONFIG_FILE_SHA256",
    "REGISTERED_CONFIG_PATH",
    "REGISTERED_DEVELOPMENT_GAMES",
    "REGISTERED_DEVELOPMENT_SEEDS",
    "REGISTERED_MANIFEST_PATH",
    "REGISTERED_MANIFEST_SHA256",
    "REGISTERED_POLICY_SHA256",
    "REGISTERED_POLICY_VERSION",
    "REGISTERED_RUNTIME_VERSION",
    "REGISTERED_SPLIT_FILE_SHA256",
    "REGISTERED_SPLIT_PATH",
    "REGISTRATION_SCHEMA_VERSION",
    "build_zero_run_registration",
    "registered_arm_config_hashes",
    "registration_payload_sha256",
    "serialize_zero_run_registration",
    "validate_arm_config_hashes",
    "validate_zero_run_registration",
]
