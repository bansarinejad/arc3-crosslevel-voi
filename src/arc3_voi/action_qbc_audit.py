"""Permit-gated sealed evaluator for the dormant action-QBC runtime.

The registered lockbox is deliberately outside this module's open-fixture path.
The shipped CLI consumes one of two external one-shot permits and issues an opaque
capability only at the exact clean, tagged registration.  Authorization is checked
before even a lockbox path-metadata operation, and capability issuance itself never
reads or stats the registered lockbox.  The legacy scaffold remains fail-closed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import platform
import site
import stat
import subprocess
import sys
import sysconfig
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isclose, isfinite
from pathlib import Path
from threading import Lock
from types import MappingProxyType, ModuleType
from typing import Any, Final, TypeAlias, cast

import numpy as np

from . import action_qbc_policy as _action_qbc_policy_module
from .action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    MAX_PROBES_PER_LEVEL,
    ActionQBCSelection,
    OutcomeCell,
    action_qbc_policy_sha256,
    normalise_gibbs_weights,
    partition_exact_outcomes,
    select_action_conditional_qbc,
)
from .candidates import (
    CANDIDATE_POLICY_HASH,
    candidates_from_history,
)
from .candidates import (
    CANDIDATE_POLICY_VERSION as IMPLEMENTED_CANDIDATE_POLICY_VERSION,
)
from .config import SystemConfig
from .controller import Variant
from .controller_v5 import V5Controller, V5ControllerConfig
from .grounding import evaluate_program_grounding
from .hypothesis import Hypothesis, HypothesisPool
from .planner import (
    BeamSearchPlanner,
    PlanningSnapshot,
    committee_agreement,
    level_multiplier,
)
from .program import ExecutableHypothesis, candidate_points_from_source
from .runtime.sandbox import validate_program
from .runtime.worker import RLIMIT_DATA_HEADROOM_KIND
from .runtime_admission import (
    EvaluatedSource,
    construct_eligible_hypotheses,
    role_requirements,
)
from .structured_templates import (
    STRUCTURED_PRIOR_CONTRACT_SHA256,
    STRUCTURED_PRIOR_CONTRACT_VERSION,
    STRUCTURED_PRIOR_ROLES,
    StructuredPriorSource,
    instantiate_structured_priors,
)
from .topology_compiler import (
    TOPOLOGY_COMPILER_CODE_SHA256 as TOPOLOGY_COMPILER_CODE_SHA256,
)
from .types import (
    Action,
    ActionKind,
    Budget,
    GameState,
    History,
    Observation,
    Prediction,
)

JsonScalar: TypeAlias = str | int | float | bool | None  # noqa: UP040
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]  # noqa: UP040

ACTION_QBC_AUDIT_CONTRACT_VERSION: Final = "action-qbc-audit-authorization-v1"
ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION: Final = "action-qbc-scientific-payload-v1"
AUDIT_REGISTRATION_SCHEMA_VERSION: Final = "action-qbc-v5-audit-registration-v1"
AUDIT_AUTHORIZATION_STATE: Final = (
    "sealed-audit-capability-required-runtime-v5-disabled"
)
AUDIT_AUTHORIZATION_ENABLED: Final = False
AUDIT_REGISTRATION_TAG: Final = "action-qbc-v5-audit-freeze-v1"
AUDIT_CONFIG_RELATIVE_PATH: Final = "configs/template_v1_action_conditional_qbc_v1_x.yaml"
AUDIT_CONFIG_FILE_SHA256: Final = (
    "b5067f34dc7934d93b798217ff9e9c29cdc4c5c7af9ab2391d47189012908d11"
)
AUDIT_MATRIX_RELATIVE_PATH: Final = (
    "artifacts/development_matrix_template_v1_action_conditional_qbc_v1.json"
)
AUDIT_MATRIX_FILE_SHA256: Final = (
    "6fb58e3c44d9b2cc3a71e12366cd86d3dca7a140df0b120a074e9d01a1d4efe2"
)
AUDIT_REGISTRATION_RELATIVE_PATH: Final = "artifacts/action_qbc_v5_audit_registration.json"

PATH_DEFICIT_POLICY_VERSION: Final = "path-deficit-v2"
PATH_DEFICIT_POLICY_SHA256: Final = (
    "055f52473893709d88beffed0b22fa035c24af7b9da3ce24306e481cf2abc670"
)
CANDIDATE_POLICY_VERSION: Final = "salience-frontier-v1"
CANDIDATE_POLICY_SHA256: Final = (
    "a9220009c5fd4b6da602580db439e25f9acaef74799de050a7a56e6c64bba82c"
)
COMPILER_CONTRACT_VERSION: Final = "scene-topology-compiler-v1"
COMPILER_CONTRACT_SHA256: Final = (
    "eeccd86db3346fd15d2e3dbc8e82ee2bb60e23bc30c0490750a7a0fbaa9e14e5"
)
GENERATOR_VERSION: Final = "action-qbc-lockbox-generator-v1"
GENERATOR_CONTRACT_SHA256: Final = (
    "fbaa4663ea3d2b47bc6ec2e2ba1f68b4c717f63f19e6538b270a4c77339a0b74"
)
GENERATOR_SOURCE_COMMIT: Final = "4aae43d2dda05b2b4b9ef2670ef83e3b6a52eb37"
GENERATOR_SOURCE_SHA256: Final = (
    "7b27e1d06ae26e354edd41aaa9e9889ea80a28b0d3a206aeb7158282d067e72a"
)
LOCKBOX_ARTIFACT_RELATIVE_PATH: Final = (
    "artifacts/action_conditional_qbc_v1_lockbox.json"
)
LOCKBOX_ARTIFACT_SIZE_BYTES: Final = 47_241_363
LOCKBOX_ARTIFACT_SHA256: Final = (
    "d2e84af6527b1dfe686d3113000e0e0b72925c0a8735228da0d3f3c094975953"
)
LOCKBOX_CONTENT_SHA256: Final = (
    "64ede8fcefaeff061f313d79021ad5188a63170aa63d9d0ab824187860e6760b"
)

AUDIT_SOURCE_FILE_ORDER: Final = (
    "artifacts/development_matrix_template_v1_action_conditional_qbc_v1.json",
    "configs/template_v1_action_conditional_qbc_v1_x.yaml",
    "docs/experiment_amendment_2026-07-13_action_conditional_qbc_v1.md",
    "docs/experiment_protocol.md",
    "pyproject.toml",
    "scripts/audit_action_qbc_lockbox.py",
    "scripts/build_action_qbc_audit_registration.py",
    "scripts/build_action_qbc_zero_run_manifest.py",
    "src/arc3_voi/__init__.py",
    "src/arc3_voi/action_qbc_audit.py",
    "src/arc3_voi/action_qbc_lockbox.py",
    "src/arc3_voi/action_qbc_policy.py",
    "src/arc3_voi/action_qbc_zero_run.py",
    "src/arc3_voi/agent.py",
    "src/arc3_voi/arc2.py",
    "src/arc3_voi/arc_adapter.py",
    "src/arc3_voi/candidates.py",
    "src/arc3_voi/cli.py",
    "src/arc3_voi/competition.py",
    "src/arc3_voi/config.py",
    "src/arc3_voi/controller.py",
    "src/arc3_voi/controller_v5.py",
    "src/arc3_voi/experiment.py",
    "src/arc3_voi/grounding.py",
    "src/arc3_voi/grounding_repair.py",
    "src/arc3_voi/hypothesis.py",
    "src/arc3_voi/metrics.py",
    "src/arc3_voi/model.py",
    "src/arc3_voi/planner.py",
    "src/arc3_voi/preflight.py",
    "src/arc3_voi/program.py",
    "src/arc3_voi/prompts.py",
    "src/arc3_voi/provenance.py",
    "src/arc3_voi/rendering.py",
    "src/arc3_voi/replay.py",
    "src/arc3_voi/run_store.py",
    "src/arc3_voi/runner.py",
    "src/arc3_voi/runtime/__init__.py",
    "src/arc3_voi/runtime/sandbox.py",
    "src/arc3_voi/runtime/worker.py",
    "src/arc3_voi/runtime_admission.py",
    "src/arc3_voi/splitting.py",
    "src/arc3_voi/statistics.py",
    "src/arc3_voi/structured_templates.py",
    "src/arc3_voi/topology_compiler.py",
    "src/arc3_voi/trajectory_deficit.py",
    "src/arc3_voi/types.py",
    "uv.lock",
)

AUDIT_RESOURCE_COUNTER_INVENTORY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "candidate_builder_calls": "increment immediately before candidate builder entry",
        "compiler_calls": "increment immediately before scene compiler entry",
        "compiled_programs": "add the exact number of compiler programs returned",
        "completed_planning_snapshots": (
            "increment only after one complete shared PlanningSnapshot is returned"
        ),
        "controller_calls": "increment immediately before controller decision entry",
        "controller_snapshot_replays": (
            "increment after a controller consumes the exact verified shared snapshot"
        ),
        "environment_actions": "increment immediately before environment action dispatch",
        "generated_tokens": "sum generated model tokens returned by model calls",
        "grounding_evaluations": "add one for each source grounding evaluation",
        "gpu_operations": "increment immediately before each GPU-backed model operation",
        "hypothesis_pool_constructions": (
            "increment immediately after one selected four-program pool is constructed"
        ),
        "lockbox_bytes_read": "sum bytes returned by the authorized lockbox read",
        "lockbox_path_operations": (
            "increment before each authorized lockbox resolve/stat/open/read operation"
        ),
        "model_calls": "increment immediately before model generation entry",
        "network_calls": "increment immediately before any network operation",
        "planner_calls": "increment immediately before BeamSearchPlanner.evaluate entry",
        "persistent_worker_starts": "add one for each constructed persistent worker",
        "pure_selector_calls": "sum scene/order and control selector calls",
        "pure_selector_control_calls": "increment before each control selector call",
        "pure_selector_scene_order_calls": (
            "increment before each scene, visual, controller, or order selector call"
        ),
        "registered_scenes_read": "increment once per decoded registered scene",
        "reward_observations": "increment once per observed environment reward",
        "rhae_observations": "increment once per observed RHAE value",
        "total_worker_starts": "sum transient and persistent worker starts",
        "transient_worker_starts": "add one for each returned grounding worker result",
        "v4_counterfactual_calls": "increment once per base-scene v4 diagnostic",
    }
)
AUDIT_RESOURCE_COUNTER_FIELDS: Final = tuple(sorted(AUDIT_RESOURCE_COUNTER_INVENTORY))
AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256: Final = hashlib.sha256(
    json.dumps(
        {
            "fields": list(AUDIT_RESOURCE_COUNTER_FIELDS),
            "increment_contract": dict(AUDIT_RESOURCE_COUNTER_INVENTORY),
            "schema_version": 1,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()

EXPECTED_SEALED_RESOURCE_COUNTS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "candidate_builder_calls": 48,
        "compiler_calls": 60,
        "compiled_programs": 240,
        "completed_planning_snapshots": 60,
        "controller_calls": 96,
        "controller_snapshot_replays": 96,
        "environment_actions": 0,
        "generated_tokens": 0,
        "grounding_evaluations": 240,
        "gpu_operations": 0,
        "hypothesis_pool_constructions": 60,
        "lockbox_bytes_read": LOCKBOX_ARTIFACT_SIZE_BYTES,
        "lockbox_path_operations": 4,
        "model_calls": 0,
        "network_calls": 0,
        "persistent_worker_starts": 240,
        "planner_calls": 60,
        "pure_selector_calls": 235,
        "pure_selector_control_calls": 19,
        "pure_selector_scene_order_calls": 216,
        "registered_scenes_read": 12,
        "reward_observations": 0,
        "rhae_observations": 0,
        "total_worker_starts": 480,
        "transient_worker_starts": 240,
        "v4_counterfactual_calls": 12,
    }
)

PENDING_FREEZE_FIELDS: Final = (
    "code_commit",
    "git_clean_status_sha256",
    "git_index_diff_sha256",
    "git_worktree_diff_sha256",
    "registration_sha256",
    "source_files",
    "source_manifest_sha256",
)


class RegisteredAuditNotAuthorized(PermissionError):
    """Raised before any registered-payload filesystem access is possible."""


@dataclass(frozen=True, slots=True)
class SourceFileIdentity:
    """One exact source blob included in the clean-HEAD capability."""

    path: str
    sha256: str

    def as_json(self) -> dict[str, JsonValue]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class AuditProvenance:
    """Complete identity tuple required by a future sealed-audit capability."""

    code_commit: str | None
    config_sha256: str | None
    matrix_sha256: str | None
    registration_sha256: str | None
    source_files: tuple[SourceFileIdentity, ...] | None
    source_manifest_sha256: str | None
    git_clean_status_sha256: str | None
    git_index_diff_sha256: str | None
    git_worktree_diff_sha256: str | None
    audit_contract_version: str
    registration_schema_version: str
    resource_counter_schema_sha256: str
    runtime_version: str
    completion_cost_policy_version: str
    completion_cost_policy_sha256: str
    probe_policy_version: str
    probe_policy_sha256: str
    candidate_policy_version: str
    candidate_policy_sha256: str
    compiler_contract_version: str
    compiler_contract_sha256: str
    generator_version: str
    generator_contract_sha256: str
    generator_source_commit: str
    generator_source_sha256: str
    lockbox_artifact_path: str
    lockbox_artifact_size_bytes: int
    lockbox_artifact_sha256: str
    lockbox_content_sha256: str

    @property
    def fully_frozen(self) -> bool:
        return all(getattr(self, field) is not None for field in PENDING_FREEZE_FIELDS)

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "audit_contract_version": self.audit_contract_version,
            "candidate_policy_sha256": self.candidate_policy_sha256,
            "candidate_policy_version": self.candidate_policy_version,
            "code_commit": self.code_commit,
            "compiler_contract_sha256": self.compiler_contract_sha256,
            "compiler_contract_version": self.compiler_contract_version,
            "completion_cost_policy_sha256": self.completion_cost_policy_sha256,
            "completion_cost_policy_version": self.completion_cost_policy_version,
            "config_sha256": self.config_sha256,
            "generator_contract_sha256": self.generator_contract_sha256,
            "generator_source_commit": self.generator_source_commit,
            "generator_source_sha256": self.generator_source_sha256,
            "generator_version": self.generator_version,
            "git_clean_status_sha256": self.git_clean_status_sha256,
            "git_index_diff_sha256": self.git_index_diff_sha256,
            "git_worktree_diff_sha256": self.git_worktree_diff_sha256,
            "lockbox_artifact_path": self.lockbox_artifact_path,
            "lockbox_artifact_sha256": self.lockbox_artifact_sha256,
            "lockbox_artifact_size_bytes": self.lockbox_artifact_size_bytes,
            "lockbox_content_sha256": self.lockbox_content_sha256,
            "matrix_sha256": self.matrix_sha256,
            "probe_policy_sha256": self.probe_policy_sha256,
            "probe_policy_version": self.probe_policy_version,
            "registration_sha256": self.registration_sha256,
            "registration_schema_version": self.registration_schema_version,
            "resource_counter_schema_sha256": self.resource_counter_schema_sha256,
            "runtime_version": self.runtime_version,
            "source_files": (
                None
                if self.source_files is None
                else [identity.as_json() for identity in self.source_files]
            ),
            "source_manifest_sha256": self.source_manifest_sha256,
        }


EXPECTED_AUDIT_PROVENANCE: Final = AuditProvenance(
    code_commit=None,
    config_sha256=AUDIT_CONFIG_FILE_SHA256,
    matrix_sha256=AUDIT_MATRIX_FILE_SHA256,
    registration_sha256=None,
    source_files=None,
    source_manifest_sha256=None,
    git_clean_status_sha256=None,
    git_index_diff_sha256=None,
    git_worktree_diff_sha256=None,
    audit_contract_version=ACTION_QBC_AUDIT_CONTRACT_VERSION,
    registration_schema_version=AUDIT_REGISTRATION_SCHEMA_VERSION,
    resource_counter_schema_sha256=AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256,
    runtime_version=ACTION_QBC_RUNTIME_VERSION,
    completion_cost_policy_version=PATH_DEFICIT_POLICY_VERSION,
    completion_cost_policy_sha256=PATH_DEFICIT_POLICY_SHA256,
    probe_policy_version=ACTION_QBC_POLICY_VERSION,
    probe_policy_sha256=ACTION_QBC_POLICY_SHA256,
    candidate_policy_version=CANDIDATE_POLICY_VERSION,
    candidate_policy_sha256=CANDIDATE_POLICY_SHA256,
    compiler_contract_version=COMPILER_CONTRACT_VERSION,
    compiler_contract_sha256=COMPILER_CONTRACT_SHA256,
    generator_version=GENERATOR_VERSION,
    generator_contract_sha256=GENERATOR_CONTRACT_SHA256,
    generator_source_commit=GENERATOR_SOURCE_COMMIT,
    generator_source_sha256=GENERATOR_SOURCE_SHA256,
    lockbox_artifact_path=LOCKBOX_ARTIFACT_RELATIVE_PATH,
    lockbox_artifact_size_bytes=LOCKBOX_ARTIFACT_SIZE_BYTES,
    lockbox_artifact_sha256=LOCKBOX_ARTIFACT_SHA256,
    lockbox_content_sha256=LOCKBOX_CONTENT_SHA256,
)

AUDIT_AUTHORIZATION_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "authorization_state": AUDIT_AUTHORIZATION_STATE,
        "capability_issuance": (
            "exact dedicated registration, exhaustive sources, clean tagged HEAD, and one "
            "durably consumed primary/replica permit at " + AUDIT_REGISTRATION_TAG
        ),
        "contract_version": ACTION_QBC_AUDIT_CONTRACT_VERSION,
        "fail_closed_order": (
            "authorization gate precedes path resolve, stat, exists, open, and read"
        ),
        "pending_freeze_fields": PENDING_FREEZE_FIELDS,
        "registered_execution": (
            "implemented only through the fixed two-start external-permit CLI; runtime-v5 "
            "remains absent from every live allowlist"
        ),
        "registration_path": AUDIT_REGISTRATION_RELATIVE_PATH,
        "resource_counter_fields": AUDIT_RESOURCE_COUNTER_FIELDS,
        "resource_counter_schema_sha256": AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256,
        "required_identity_fields": tuple(EXPECTED_AUDIT_PROVENANCE.as_json()),
        "shipped_cli_capability": "external one-shot permit plus opaque issued capability",
    }
)


class RegisteredAuditLaunchAttestation:
    """Opaque proof that this process is the exact registered uv/Python launch."""

    __slots__ = ()

    def __new__(cls) -> RegisteredAuditLaunchAttestation:
        del cls
        raise TypeError("launch attestations are issued only by the canonical CLI process")


REGISTERED_AUDIT_UV_VERSION: Final = "0.11.28"
REGISTERED_AUDIT_DISTRIBUTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "arc3-crosslevel-voi": "0.1.0",
        "numpy": "2.5.1",
        "pyyaml": "6.0.3",
    }
)
REGISTERED_AUDIT_VIRTUALENV_PTH_SHA256: Final = (
    "69ac3d8f27e679c81b94ab30b3b56e9cd138219b1ba94a1fa3606d5a76a1433d"
)
REGISTERED_AUDIT_VIRTUALENV_MODULE_SHA256: Final = (
    "cfb3db86aaa53bb62b5ff764970bec2d71c9228590a0ebec57f6ec926cc0bf1a"
)
_REGISTERED_LAUNCH_PREFIX: Final = (
    "uv",
    "run",
    "--frozen",
    "--no-sync",
    "python3",
    "-I",
    "-B",
    "scripts/audit_action_qbc_lockbox.py",
)
_REGISTERED_LAUNCH_OPTION_NAMES: Final = (
    "--repository-root",
    "--registration",
    "--permit-record",
    "--permit-marker",
    "--output",
)


@dataclass(slots=True)
class _RegisteredLaunchAttestationState:
    root: Path
    exact_command: tuple[str, ...]
    identity: dict[str, JsonValue]
    attestation_sha256: str
    process_id: int
    parent_process_id: int
    process_start_time_ticks: int
    parent_start_time_ticks: int
    code_commit: str
    registration_sha256: str
    source_manifest_sha256: str
    issuance_id: str
    run_label: str
    permit_directory: Path
    output_path: Path
    consumed_permit_sha256: str
    capability_phase_consumed: bool = False
    ledger_phase_consumed: bool = False


def _process_start_time_ticks(process_id: int) -> int:
    raw = (Path("/proc") / str(process_id) / "stat").read_text(encoding="utf-8")
    closing = raw.rfind(")")
    fields = raw[closing + 2 :].split() if closing >= 0 else []
    if len(fields) <= 19 or not fields[19].isdigit():
        raise RegisteredAuditNotAuthorized("Linux process start identity is malformed")
    return int(fields[19])


def _require_source_only_launch_tree(repository: Path) -> None:
    for source_root in (repository / "src" / "arc3_voi", repository / "scripts"):
        if not source_root.is_dir() or source_root.is_symlink():
            raise RegisteredAuditNotAuthorized("registered launch source root is invalid")
        for directory, directory_names, file_names in os.walk(
            source_root,
            followlinks=False,
        ):
            current = Path(directory)
            if current.name == "__pycache__" or "__pycache__" in directory_names:
                raise RegisteredAuditNotAuthorized(
                    "registered launch source tree contains cached bytecode"
                )
            if any(name.endswith((".pyc", ".pyo")) for name in file_names):
                raise RegisteredAuditNotAuthorized(
                    "registered launch source tree contains cached bytecode"
                )
            if any((current / name).is_symlink() for name in directory_names):
                raise RegisteredAuditNotAuthorized(
                    "registered launch source tree contains a symbolic directory"
                )


def _registered_launch_command_options(
    exact_command: Sequence[str],
) -> tuple[tuple[str, ...], dict[str, str]]:
    command = tuple(exact_command)
    command_tail = command[len(_REGISTERED_LAUNCH_PREFIX) :]
    if (
        command[: len(_REGISTERED_LAUNCH_PREFIX)] != _REGISTERED_LAUNCH_PREFIX
        or len(command_tail) != 2 * len(_REGISTERED_LAUNCH_OPTION_NAMES)
        or tuple(command_tail[::2]) != _REGISTERED_LAUNCH_OPTION_NAMES
        or any(not value for value in command_tail[1::2])
    ):
        raise RegisteredAuditNotAuthorized("registered launch command is invalid")
    options = dict(
        zip(_REGISTERED_LAUNCH_OPTION_NAMES, command_tail[1::2], strict=True)
    )
    if (
        options["--repository-root"] != "."
        or options["--registration"] != AUDIT_REGISTRATION_RELATIVE_PATH
    ):
        raise RegisteredAuditNotAuthorized("registered launch repository option is invalid")
    return command, options


def _normalized_distribution_name(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def _read_plain_launcher_environment_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RegisteredAuditNotAuthorized(f"registered launcher {label} is not a plain file")
    return path.read_bytes()


def _verified_python_executable_identity(path: Path) -> dict[str, JsonValue]:
    """Bind uv's expected interpreter symlink and its resolved plain target."""

    try:
        metadata = path.lstat()
    except OSError as error:
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python executable is unavailable"
        ) from error
    if not stat.S_ISLNK(metadata.st_mode):
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python executable is not uv's python3 symlink"
        )
    intermediate = path.parent / "python"
    versioned = path.parent / "python3.12"
    try:
        symlink_target = os.readlink(path)
        intermediate_metadata = intermediate.lstat()
        intermediate_target = os.readlink(intermediate)
        versioned_metadata = versioned.lstat()
        versioned_target = os.readlink(versioned)
    except OSError as error:
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python symlink chain cannot be read"
        ) from error
    if (
        symlink_target != "python"
        or not stat.S_ISLNK(intermediate_metadata.st_mode)
        or not stat.S_ISLNK(versioned_metadata.st_mode)
        or versioned_target != "python"
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python symlink chain differs from uv 0.11.28"
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python executable target is unavailable"
        ) from error
    if (
        resolved.is_symlink()
        or not resolved.is_file()
        or intermediate.resolve(strict=True) != resolved
        or versioned.resolve(strict=True) != resolved
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launcher Python executable target is not a plain file"
        )
    raw = resolved.read_bytes()
    return {
        "python_executable_resolved_path_sha256": hashlib.sha256(
            resolved.as_posix().encode("utf-8")
        ).hexdigest(),
        "python_executable_sha256": hashlib.sha256(raw).hexdigest(),
        "python_executable_symlink_target_sha256": (
            hashlib.sha256(symlink_target.encode("utf-8")).hexdigest()
        ),
        "python_intermediate_symlink_target_sha256": hashlib.sha256(
            intermediate_target.encode("utf-8")
        ).hexdigest(),
        "python_versioned_symlink_target_sha256": hashlib.sha256(
            versioned_target.encode("utf-8")
        ).hexdigest(),
    }


def _verified_python_environment_identity(repository: Path) -> dict[str, JsonValue]:
    """Require the dependency-minimal uv environment used by canonical clones."""

    root = repository.resolve(strict=True)
    venv = root / ".venv"
    expected_executable = venv / "bin" / "python3"
    expected_site_packages = (
        venv
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if (
        sys.version_info[:2] != (3, 12)
        or Path(sys.prefix) != venv
        or Path(sys.exec_prefix) != venv
        or Path(sys.executable) != expected_executable
        or Path(sys.base_prefix) == venv
        or not venv.is_dir()
        or venv.is_symlink()
        or not expected_site_packages.is_dir()
        or expected_site_packages.is_symlink()
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launch virtual-environment prefix is invalid"
        )
    site_packages = expected_site_packages.resolve(strict=True)
    configured_site_packages = tuple(
        Path(value).resolve(strict=True) for value in site.getsitepackages()
    )
    purelib = Path(sysconfig.get_path("purelib")).resolve(strict=True)
    platlib = Path(sysconfig.get_path("platlib")).resolve(strict=True)
    if (
        configured_site_packages != (site_packages,)
        or purelib != site_packages
        or platlib != site_packages
        or site.ENABLE_USER_SITE is not False
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launch site-packages configuration is invalid"
        )
    project_source = (root / "src").resolve(strict=True)
    resolved_sys_path = tuple(
        Path(value).resolve(strict=False) for value in sys.path if value
    )
    if (
        resolved_sys_path.count(site_packages) != 1
        or resolved_sys_path.count(project_source) != 1
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launch sys.path lacks its exact editable-project paths"
        )
    for value in resolved_sys_path:
        try:
            value.relative_to(root)
        except ValueError:
            continue
        if value not in {site_packages, project_source}:
            raise RegisteredAuditNotAuthorized(
                "registered launch sys.path contains an extra worktree path"
            )
    for module_name in ("sitecustomize", "usercustomize"):
        if module_name in sys.modules:
            raise RegisteredAuditNotAuthorized(
                "registered launch loaded a customization module"
            )
        try:
            customization_spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError) as error:
            raise RegisteredAuditNotAuthorized(
                "registered launch customization-module lookup failed"
            ) from error
        if customization_spec is not None:
            raise RegisteredAuditNotAuthorized(
                "registered launch exposes a customization module"
            )
    editable_pth = site_packages / "_editable_impl_arc3_crosslevel_voi.pth"
    virtualenv_pth = site_packages / "_virtualenv.pth"
    pth_files = tuple(sorted(site_packages.glob("*.pth")))
    if set(pth_files) != {editable_pth, virtualenv_pth} or any(
        site_packages.glob("*.egg-link")
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launch .pth inventory differs from uv 0.11.28"
        )
    pth_raw = _read_plain_launcher_environment_file(
        editable_pth, "editable-project .pth file"
    )
    try:
        pth_text = pth_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RegisteredAuditNotAuthorized(
            "registered launcher .pth file is not UTF-8"
        ) from error
    if (
        "\r" in pth_text
        or tuple(pth_text.splitlines()) != (str(project_source),)
        or pth_text.lstrip().startswith(("import ", "import\t"))
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launcher .pth file is not the sole project-source path"
        )
    virtualenv_pth_raw = _read_plain_launcher_environment_file(
        virtualenv_pth, "uv virtualenv .pth file"
    )
    virtualenv_module_path = site_packages / "_virtualenv.py"
    virtualenv_module_raw = _read_plain_launcher_environment_file(
        virtualenv_module_path, "uv virtualenv module"
    )
    virtualenv_module = sys.modules.get("_virtualenv")
    virtualenv_module_origin = getattr(virtualenv_module, "__file__", None)
    if (
        virtualenv_pth_raw != b"import _virtualenv"
        or hashlib.sha256(virtualenv_pth_raw).hexdigest()
        != REGISTERED_AUDIT_VIRTUALENV_PTH_SHA256
        or len(virtualenv_module_raw) != 5_246
        or hashlib.sha256(virtualenv_module_raw).hexdigest()
        != REGISTERED_AUDIT_VIRTUALENV_MODULE_SHA256
        or not isinstance(virtualenv_module_origin, str)
        or Path(virtualenv_module_origin).resolve(strict=True)
        != virtualenv_module_path.resolve(strict=True)
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launcher uv virtualenv hook differs from uv 0.11.28"
        )
    distributions: dict[str, str] = {}
    project_direct_url: JsonValue | None = None
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        raw_name = distribution.metadata.get("Name")
        if not isinstance(raw_name, str) or not raw_name:
            raise RegisteredAuditNotAuthorized(
                "registered launcher distribution lacks a canonical name"
            )
        name = _normalized_distribution_name(raw_name)
        if name in distributions:
            raise RegisteredAuditNotAuthorized(
                "registered launcher contains a duplicate distribution"
            )
        if Path(str(distribution.locate_file(""))).resolve(strict=True) != site_packages:
            raise RegisteredAuditNotAuthorized(
                "registered launcher distribution is outside site-packages"
            )
        distributions[name] = distribution.version
        if name == "arc3-crosslevel-voi":
            direct_url_text = distribution.read_text("direct_url.json")
            if not isinstance(direct_url_text, str):
                raise RegisteredAuditNotAuthorized(
                    "registered launcher project lacks editable direct_url metadata"
                )
            try:
                direct_url_value = json.loads(direct_url_text)
            except json.JSONDecodeError as error:
                raise RegisteredAuditNotAuthorized(
                    "registered launcher project direct_url metadata is malformed"
                ) from error
            if not isinstance(direct_url_value, dict):
                raise RegisteredAuditNotAuthorized(
                    "registered launcher project direct_url metadata is malformed"
                )
            project_direct_url = cast(JsonValue, direct_url_value)
    if distributions != dict(REGISTERED_AUDIT_DISTRIBUTIONS):
        raise RegisteredAuditNotAuthorized(
            "registered launcher installed-distribution inventory is invalid"
        )
    if project_direct_url != {
        "dir_info": {"editable": True},
        "url": root.as_uri(),
    }:
        raise RegisteredAuditNotAuthorized(
            "registered launcher project is not editable from the exact worktree"
        )
    pyvenv_raw = _read_plain_launcher_environment_file(
        venv / "pyvenv.cfg", "pyvenv.cfg"
    )
    try:
        pyvenv_lines = tuple(
            line.strip() for line in pyvenv_raw.decode("utf-8").splitlines()
        )
    except UnicodeDecodeError as error:
        raise RegisteredAuditNotAuthorized(
            "registered launcher pyvenv.cfg is not UTF-8"
        ) from error
    if (
        "include-system-site-packages = false" not in pyvenv_lines
        or f"uv = {REGISTERED_AUDIT_UV_VERSION}" not in pyvenv_lines
    ):
        raise RegisteredAuditNotAuthorized(
            "registered launcher pyvenv.cfg differs from the required uv environment"
        )
    return {
        **_verified_python_executable_identity(expected_executable),
        "distribution_versions": dict(sorted(distributions.items())),
        "project_pth_sha256": hashlib.sha256(pth_raw).hexdigest(),
        "project_direct_url": project_direct_url,
        "pyvenv_sha256": hashlib.sha256(pyvenv_raw).hexdigest(),
        "python_version": platform.python_version(),
        "site_packages_sha256": hashlib.sha256(
            site_packages.as_posix().encode("utf-8")
        ).hexdigest(),
        "sys_path_sha256": canonical_sha256(list(sys.path)),
        "uv_virtualenv_module_sha256": REGISTERED_AUDIT_VIRTUALENV_MODULE_SHA256,
        "uv_virtualenv_pth_sha256": REGISTERED_AUDIT_VIRTUALENV_PTH_SHA256,
        "venv_prefix_sha256": hashlib.sha256(venv.as_posix().encode("utf-8")).hexdigest(),
    }


def _verified_uv_executable_identity(parent_executable: Path) -> dict[str, JsonValue]:
    """Execute and bind the actual parent uv binary, not a PATH lookup."""

    try:
        version_process = subprocess.run(
            (str(parent_executable), "--version"),
            check=True,
            capture_output=True,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            timeout=5.0,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RegisteredAuditNotAuthorized(
            "registered uv parent version cannot be verified"
        ) from error
    try:
        uv_version_output = version_process.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise RegisteredAuditNotAuthorized(
            "registered uv parent version is not UTF-8"
        ) from error
    version_tokens = uv_version_output.split()
    if (
        version_tokens[:2] != ["uv", REGISTERED_AUDIT_UV_VERSION]
        or version_process.stderr
    ):
        raise RegisteredAuditNotAuthorized("registered uv parent version is invalid")
    return {
        "uv_executable_path_sha256": hashlib.sha256(
            parent_executable.as_posix().encode("utf-8")
        ).hexdigest(),
        "uv_executable_sha256": hashlib.sha256(
            _read_plain_launcher_environment_file(
                parent_executable, "uv parent executable"
            )
        ).hexdigest(),
        "uv_version": REGISTERED_AUDIT_UV_VERSION,
        "uv_version_output_sha256": hashlib.sha256(
            version_process.stdout
        ).hexdigest(),
    }


def _verified_uv_parent_identity(
    repository: Path,
    exact_command: Sequence[str],
) -> tuple[dict[str, JsonValue], int, int]:
    root = repository.resolve(strict=True)
    command, _options = _registered_launch_command_options(exact_command)
    parent_process_id = os.getppid()
    process_directory = Path("/proc") / str(parent_process_id)
    parent_executable = (process_directory / "exe").resolve(strict=True)
    parent_directory = (process_directory / "cwd").resolve(strict=True)
    raw_cmdline = (process_directory / "cmdline").read_bytes()
    if not raw_cmdline.endswith(b"\0"):
        raise RegisteredAuditNotAuthorized("registered uv parent command is malformed")
    try:
        parent_argv = tuple(
            token.decode("utf-8") for token in raw_cmdline[:-1].split(b"\0")
        )
    except UnicodeDecodeError as error:
        raise RegisteredAuditNotAuthorized("registered uv parent argv is not UTF-8") from error
    if (
        parent_executable.name != "uv"
        or not parent_argv
        or Path(parent_argv[0]).name != "uv"
        or parent_argv[1:] != command[1:]
        or parent_directory != root
    ):
        raise RegisteredAuditNotAuthorized("registered uv parent identity is invalid")
    parent_start = _process_start_time_ticks(parent_process_id)
    return (
        _verified_uv_executable_identity(parent_executable),
        parent_process_id,
        parent_start,
    )


def _verified_registered_launcher_environment(
    repository: Path,
    exact_command: Sequence[str],
) -> tuple[dict[str, JsonValue], int, int]:
    if platform.system() != "Linux":
        raise RegisteredAuditNotAuthorized("registered launch platform is invalid")
    uv_identity, parent_process_id, parent_start = _verified_uv_parent_identity(
        repository,
        exact_command,
    )
    python_identity = _verified_python_environment_identity(repository)
    details: dict[str, JsonValue] = {
        "python": python_identity,
        "uv": uv_identity,
    }
    return (
        {
            "launcher_distribution_versions": python_identity[
                "distribution_versions"
            ],
            "launcher_environment_sha256": canonical_sha256(details),
            "launcher_uv_version": REGISTERED_AUDIT_UV_VERSION,
        },
        parent_process_id,
        parent_start,
    )


def require_registered_launcher_environment(
    repository: str | Path,
    exact_command: Sequence[str],
) -> dict[str, JsonValue]:
    """Fail before permit consumption unless the canonical base uv environment holds."""

    identity, _parent_process_id, _parent_start = (
        _verified_registered_launcher_environment(
            Path(repository).resolve(strict=True),
            exact_command,
        )
    )
    return identity


def _verified_registered_launch_identity(
    repository: Path,
    exact_command: Sequence[str],
) -> tuple[dict[str, JsonValue], int, int, int, int]:
    root = repository.resolve(strict=True)
    command, options = _registered_launch_command_options(exact_command)
    launcher_environment, parent_process_id, parent_start = (
        _verified_registered_launcher_environment(root, command)
    )
    permit_record = Path(options["--permit-record"]).resolve(strict=False)
    permit_marker = Path(options["--permit-marker"]).resolve(strict=False)
    output_path = Path(options["--output"]).resolve(strict=False)
    labels = tuple(
        label
        for label in ("primary", "replica")
        if permit_record.name == f"{label}.permit.json"
        and permit_marker.name == f"{label}.available"
    )
    if len(labels) != 1 or permit_record.parent != permit_marker.parent:
        raise RegisteredAuditNotAuthorized("registered launch permit paths are inconsistent")
    run_label = labels[0]
    if (
        sys.flags.isolated != 1
        or sys.flags.safe_path != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
    ):
        raise RegisteredAuditNotAuthorized("registered launch lacks exact -I -B isolation")
    _require_source_only_launch_tree(root)
    expected_executable = root / ".venv" / "bin" / "python3"
    if Path(sys.executable) != expected_executable or not expected_executable.exists():
        raise RegisteredAuditNotAuthorized("registered launch interpreter is invalid")
    expected_script = (root / _REGISTERED_LAUNCH_PREFIX[-1]).resolve(strict=True)
    main_module = sys.modules.get("__main__")
    main_origin = getattr(main_module, "__file__", None)
    if (
        not isinstance(main_origin, str)
        or Path(main_origin).resolve(strict=True) != expected_script
        or Path(sys.argv[0]).resolve(strict=True) != expected_script
        or Path.cwd().resolve(strict=True) != root
    ):
        raise RegisteredAuditNotAuthorized("registered launch script/cwd identity is invalid")
    script_index = command.index(_REGISTERED_LAUNCH_PREFIX[-1])
    if tuple(sys.argv[1:]) != command[script_index + 1 :]:
        raise RegisteredAuditNotAuthorized("registered launch Python argv is invalid")
    original = tuple(sys.orig_argv)
    if (
        not original
        or original[0] != "python3"
        or original[1:] != ("-I", "-B", *command[script_index:])
    ):
        raise RegisteredAuditNotAuthorized("registered launch original Python argv is invalid")
    source_root = (root / "src" / "arc3_voi").resolve(strict=True)
    required_modules = {"arc3_voi", "arc3_voi.action_qbc_audit", "arc3_voi.config"}
    loaded_modules: set[str] = set()
    for name, module in tuple(sys.modules.items()):
        if name == "arc3_voi" or name.startswith("arc3_voi."):
            origin = getattr(module, "__file__", None)
            if not isinstance(origin, str):
                raise RegisteredAuditNotAuthorized("registered project module lacks origin")
            resolved = Path(origin).resolve(strict=True)
            try:
                relative = resolved.relative_to(source_root)
            except ValueError as error:
                raise RegisteredAuditNotAuthorized(
                    "registered project module is outside the worktree"
                ) from error
            module_parts = name.split(".")[1:]
            expected_origins = {
                Path(*module_parts).with_suffix(".py") if module_parts else Path("__init__.py"),
                Path(*module_parts) / "__init__.py" if module_parts else Path("__init__.py"),
            }
            if relative not in expected_origins:
                raise RegisteredAuditNotAuthorized(
                    "registered project module origin/name mapping is invalid"
                )
            loaded_modules.add(name)
    if not required_modules.issubset(loaded_modules):
        raise RegisteredAuditNotAuthorized("registered project module inventory is incomplete")
    admin = sys.modules.get("_arc3_action_qbc_audit_registration_admin")
    admin_origin = getattr(admin, "__file__", None)
    expected_admin = (root / "scripts" / "build_action_qbc_audit_registration.py").resolve(
        strict=True
    )
    if not isinstance(admin_origin, str) or Path(admin_origin).resolve(
        strict=True
    ) != expected_admin:
        raise RegisteredAuditNotAuthorized("registration-admin module origin is invalid")
    process_id = os.getpid()
    process_start = _process_start_time_ticks(process_id)
    identity: dict[str, JsonValue] = {
        **launcher_environment,
        "command_sha256": canonical_sha256(list(command)),
        "output_path_sha256": _sha256(output_path.as_posix().encode("utf-8")),
        "parent_process_id": parent_process_id,
        "parent_start_time_ticks": parent_start,
        "permit_marker_path_sha256": _sha256(
            permit_marker.as_posix().encode("utf-8")
        ),
        "permit_record_path_sha256": _sha256(
            permit_record.as_posix().encode("utf-8")
        ),
        "process_id": process_id,
        "process_start_time_ticks": process_start,
        "repository_root_sha256": _sha256(root.as_posix().encode("utf-8")),
        "run_label": run_label,
    }
    return identity, process_id, parent_process_id, process_start, parent_start


type _LaunchAttestationIssuer = Callable[..., RegisteredAuditLaunchAttestation]
type _LaunchAttestationLookup = Callable[..., _RegisteredLaunchAttestationState]


def _build_registered_launch_attestation_api() -> tuple[
    _LaunchAttestationIssuer,
    _LaunchAttestationLookup,
]:
    registry: dict[RegisteredAuditLaunchAttestation, _RegisteredLaunchAttestationState] = {}
    issued_bindings: set[tuple[str, str, Path, int, int]] = set()
    registry_lock = Lock()

    def lookup(
        attestation: RegisteredAuditLaunchAttestation | None,
        *,
        consume_phase: str | None,
    ) -> _RegisteredLaunchAttestationState:
        if attestation is None or not isinstance(
            attestation, RegisteredAuditLaunchAttestation
        ):
            raise RegisteredAuditNotAuthorized("an issued launch attestation is required")
        with registry_lock:
            state = registry.get(attestation)
            if state is None:
                raise RegisteredAuditNotAuthorized(
                    "launch attestation was not issued by this process"
                )
            if consume_phase == "capability":
                if state.capability_phase_consumed:
                    raise RegisteredAuditNotAuthorized(
                        "launch attestation capability phase is exhausted"
                    )
                state.capability_phase_consumed = True
            elif consume_phase == "ledger":
                if state.ledger_phase_consumed:
                    raise RegisteredAuditNotAuthorized(
                        "launch attestation ledger phase is exhausted"
                    )
                state.ledger_phase_consumed = True
            elif consume_phase is not None:
                raise ValueError("unknown launch-attestation phase")
            return state

    def issue(
        *,
        root: str | Path,
        exact_command: Sequence[str],
        consumed_permit: Mapping[str, object],
    ) -> RegisteredAuditLaunchAttestation:
        repository = Path(root).resolve(strict=True)
        command = tuple(exact_command)
        identity, pid, ppid, process_start, parent_start = (
            _verified_registered_launch_identity(repository, command)
        )
        run_label = consumed_permit.get("run_label")
        permit_directory_value = consumed_permit.get("permit_directory")
        issuance_id = consumed_permit.get("issuance_id")
        code_commit = consumed_permit.get("code_commit")
        registration_sha256 = consumed_permit.get("registration_sha256")
        source_manifest_sha256 = consumed_permit.get("source_manifest_sha256")
        if (
            run_label != identity["run_label"]
            or not isinstance(permit_directory_value, str)
            or not _is_lower_hex(issuance_id, 64)
            or not _is_lower_hex(code_commit, 40)
            or not _is_lower_hex(registration_sha256, 64)
            or not _is_lower_hex(source_manifest_sha256, 64)
            or consumed_permit.get("repository_root") != str(repository)
            or consumed_permit.get("consumed") is not True
        ):
            raise RegisteredAuditNotAuthorized(
                "launch attestation consumed-permit binding is malformed"
            )
        permit_directory = Path(permit_directory_value).resolve(strict=True)
        script_index = command.index("scripts/audit_action_qbc_lockbox.py")
        command_tail = command[script_index + 1 :]
        command_options = {
            command_tail[index]: command_tail[index + 1]
            for index in range(0, len(command_tail), 2)
        }
        expected_record = permit_directory / f"{run_label}.permit.json"
        expected_marker = permit_directory / f"{run_label}.available"
        output_path = Path(command_options["--output"]).resolve(strict=False)
        scientific_output_path = consumed_permit.get("scientific_output_path")
        scientific_output_paths = consumed_permit.get("scientific_output_paths")
        if (
            Path(command_options["--permit-record"]).resolve(strict=False)
            != expected_record
            or Path(command_options["--permit-marker"]).resolve(strict=False)
            != expected_marker
            or identity["permit_record_path_sha256"]
            != _sha256(expected_record.as_posix().encode("utf-8"))
            or identity["permit_marker_path_sha256"]
            != _sha256(expected_marker.as_posix().encode("utf-8"))
            or not isinstance(scientific_output_path, str)
            or scientific_output_path != str(output_path)
            or not isinstance(scientific_output_paths, Mapping)
            or set(scientific_output_paths) != {"primary", "replica"}
            or scientific_output_paths.get(run_label) != str(output_path)
            or any(
                not isinstance(value, str) or not value
                for value in scientific_output_paths.values()
            )
            or len(set(scientific_output_paths.values())) != 2
            or _require_clean_tagged_head(repository) != code_commit
        ):
            raise RegisteredAuditNotAuthorized(
                "launch attestation command/permit/HEAD binding differs"
            )
        registration_raw = _read_plain_file(
            repository,
            AUDIT_REGISTRATION_RELATIVE_PATH,
        )
        source_files = _source_file_manifest(repository)
        if (
            _sha256(registration_raw) != registration_sha256
            or canonical_sha256(_source_manifest_json(source_files))
            != source_manifest_sha256
        ):
            raise RegisteredAuditNotAuthorized(
                "launch attestation registration/source identity differs"
            )
        consumed_permit_sha256 = canonical_sha256(
            cast(JsonValue, dict(consumed_permit))
        )
        identity.update(
            {
                "code_commit": code_commit,
                "consumed_permit_sha256": consumed_permit_sha256,
                "issuance_id": cast(str, issuance_id),
                "registration_sha256": registration_sha256,
                "source_manifest_sha256": source_manifest_sha256,
            }
        )
        token = object.__new__(RegisteredAuditLaunchAttestation)
        state = _RegisteredLaunchAttestationState(
            root=repository,
            exact_command=command,
            identity=identity,
            attestation_sha256=canonical_sha256(identity),
            process_id=pid,
            parent_process_id=ppid,
            process_start_time_ticks=process_start,
            parent_start_time_ticks=parent_start,
            code_commit=code_commit,
            registration_sha256=registration_sha256,
            source_manifest_sha256=source_manifest_sha256,
            issuance_id=cast(str, issuance_id),
            run_label=cast(str, run_label),
            permit_directory=permit_directory,
            output_path=output_path,
            consumed_permit_sha256=consumed_permit_sha256,
        )
        binding = (
            state.issuance_id,
            state.run_label,
            state.root,
            state.process_id,
            state.process_start_time_ticks,
        )
        with registry_lock:
            if binding in issued_bindings:
                raise RegisteredAuditNotAuthorized(
                    "launch attestation was already issued for this permit/process"
                )
            issued_bindings.add(binding)
            registry[token] = state
        return token

    return issue, lookup


issue_registered_audit_launch_attestation, _registered_launch_attestation_state = (
    _build_registered_launch_attestation_api()
)


def _revalidate_registered_launch_attestation_state(
    state: _RegisteredLaunchAttestationState,
) -> None:
    observed, pid, ppid, process_start, parent_start = (
        _verified_registered_launch_identity(state.root, state.exact_command)
    )
    if (
        any(state.identity.get(key) != value for key, value in observed.items())
        or canonical_sha256(state.identity) != state.attestation_sha256
        or (pid, ppid, process_start, parent_start)
        != (
            state.process_id,
            state.parent_process_id,
            state.process_start_time_ticks,
            state.parent_start_time_ticks,
        )
    ):
        raise RegisteredAuditNotAuthorized("registered launch identity changed")
    if (
        _require_clean_tagged_head(state.root) != state.code_commit
        or _sha256(
            _read_plain_file(state.root, AUDIT_REGISTRATION_RELATIVE_PATH)
        )
        != state.registration_sha256
        or canonical_sha256(_source_manifest_json(_source_file_manifest(state.root)))
        != state.source_manifest_sha256
        or state.identity.get("issuance_id") != state.issuance_id
        or state.identity.get("consumed_permit_sha256")
        != state.consumed_permit_sha256
        or state.identity.get("run_label") != state.run_label
    ):
        raise RegisteredAuditNotAuthorized("registered launch frozen binding changed")


def _consume_registered_launch_attestation_for_capability(
    attestation: RegisteredAuditLaunchAttestation | None,
    *,
    repository_root: str | Path,
) -> _RegisteredLaunchAttestationState:
    state = _registered_launch_attestation_state(
        attestation,
        consume_phase="capability",
    )
    if state.root != Path(repository_root).resolve(strict=True):
        raise RegisteredAuditNotAuthorized("launch attestation worktree differs")
    _revalidate_registered_launch_attestation_state(state)
    return state


def consume_registered_audit_launch_attestation_for_ledger(
    attestation: RegisteredAuditLaunchAttestation | None,
    *,
    repository_root: str | Path,
    exact_command: Sequence[str],
) -> dict[str, JsonValue]:
    state = _registered_launch_attestation_state(attestation, consume_phase="ledger")
    if (
        state.root != Path(repository_root).resolve(strict=True)
        or state.exact_command != tuple(exact_command)
    ):
        raise RegisteredAuditNotAuthorized("ledger launch-attestation binding differs")
    _revalidate_registered_launch_attestation_state(state)
    return {
        "attestation_sha256": state.attestation_sha256,
        "code_commit": state.code_commit,
        "command_sha256": cast(str, state.identity["command_sha256"]),
        "consumed_permit_sha256": state.consumed_permit_sha256,
        "issuance_id": state.issuance_id,
        "launcher_distribution_versions": state.identity[
            "launcher_distribution_versions"
        ],
        "launcher_environment_sha256": cast(
            str, state.identity["launcher_environment_sha256"]
        ),
        "launcher_uv_version": cast(str, state.identity["launcher_uv_version"]),
        "output_path_sha256": cast(str, state.identity["output_path_sha256"]),
        "parent_process_id": state.parent_process_id,
        "parent_start_time_ticks": state.parent_start_time_ticks,
        "phase": "ledger",
        "permit_directory_sha256": _sha256(
            state.permit_directory.as_posix().encode("utf-8")
        ),
        "permit_marker_path_sha256": cast(
            str, state.identity["permit_marker_path_sha256"]
        ),
        "permit_record_path_sha256": cast(
            str, state.identity["permit_record_path_sha256"]
        ),
        "process_id": state.process_id,
        "process_start_time_ticks": state.process_start_time_ticks,
        "repository_root_sha256": cast(
            str, state.identity["repository_root_sha256"]
        ),
        "registration_sha256": state.registration_sha256,
        "run_label": state.run_label,
        "source_manifest_sha256": state.source_manifest_sha256,
        "valid": True,
    }


def consume_registered_audit_capability_for_ledger(
    capability: RegisteredAuditCapability | None,
    launch_attestation: RegisteredAuditLaunchAttestation | None,
    *,
    repository_root: str | Path,
    exact_command: Sequence[str],
    exit_status: int,
    payload_sha256: str | None,
) -> dict[str, JsonValue]:
    """One-shot ledger grant tied to the launch and, for success, consumed read auth."""

    capability_issued = capability is not None
    read_consumed = False
    if capability is not None:
        capability_state = _registered_capability_state(
            capability,
            consume_read=False,
        )
        if capability_state.launch_attestation is not launch_attestation:
            raise RegisteredAuditNotAuthorized(
                "ledger capability and launch attestation differ"
            )
        _revalidate_registered_capability_state(capability_state)
        read_consumed = capability_state.read_authorization_consumed
    if (exit_status == 0 or payload_sha256 is not None) and (
        not capability_issued or not read_consumed
    ):
        raise RegisteredAuditNotAuthorized(
            "successful ledger evidence lacks consumed registered read authorization"
        )
    proof = consume_registered_audit_launch_attestation_for_ledger(
        launch_attestation,
        repository_root=repository_root,
        exact_command=exact_command,
    )
    return {
        **proof,
        "capability_issued": capability_issued,
        "read_authorization_consumed": read_consumed,
    }


class RegisteredAuditCapability:
    """Opaque registry-backed capability; public construction is unavailable."""

    __slots__ = ()

    def __new__(cls) -> RegisteredAuditCapability:
        del cls
        raise TypeError("use issue_registered_audit_capability after the clean freeze")


@dataclass(slots=True)
class _RegisteredCapabilityState:
    root: Path
    consumed_permit: Mapping[str, object]
    provenance: AuditProvenance
    launch_attestation: RegisteredAuditLaunchAttestation
    launch_attestation_sha256: str
    read_authorization_consumed: bool = False


def require_registered_audit_authorized(
    capability: RegisteredAuditCapability | None,
) -> AuditProvenance:
    """Require an issued, complete, identity-bound capability before path access."""

    state = _registered_capability_state(capability, consume_read=False)
    _revalidate_registered_capability_state(state)
    return state.provenance


def run_registered_audit_scaffold(
    lockbox_path: str | Path,
    *,
    capability: RegisteredAuditCapability | None = None,
) -> None:
    """Legacy non-CLI entrypoint remains fail-closed and never accepts a lockbox path."""

    require_registered_audit_authorized(capability)
    del lockbox_path
    raise RegisteredAuditNotAuthorized(
        "legacy scaffold cannot execute; use the fixed permit-gated sealed audit CLI"
    )


class AuditControl(StrEnum):
    """Preregistered scientific control labels for open-fixture tests."""

    CONCENTRATION_ONE = "outcome_concentration_eq_1"
    CONCENTRATION_THRESHOLD = "outcome_concentration_eq_0_8"
    EVSI_ZERO = "evsi_eq_0"
    EVSI_0049 = "evsi_eq_0_049"
    HIGH_CONCENTRATION_POSITIVE_UTILITY = "high_concentration_positive_utility"
    PROBE_CAP = "probe_cap"
    CATASTROPHE = "catastrophe_cost"
    FINAL_LEVEL = "final_level_equivalence"
    TIE_BEHAVIOR = "tie_behavior"


REQUIRED_OPEN_CONTROL_ORDER: Final = tuple(AuditControl)


@dataclass(frozen=True, slots=True)
class OpenAuditCase:
    """One injected open PlanningSnapshot; it carries no scene or seed reference."""

    control: AuditControl
    snapshot: PlanningSnapshot
    cross_level_multiplier: float
    probes_used: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.control, AuditControl):
            object.__setattr__(self, "control", AuditControl(self.control))
        if not isfinite(self.cross_level_multiplier) or self.cross_level_multiplier < 1.0:
            raise ValueError("cross_level_multiplier must be finite and at least one")
        if (
            isinstance(self.probes_used, bool)
            or not isinstance(self.probes_used, int)
            or self.probes_used < 0
        ):
            raise ValueError("probes_used must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ResourceCounters:
    """Zero-only resource boundary for this pre-authorization scaffold."""

    candidate_builder_calls: int = 0
    compiler_calls: int = 0
    compiled_programs: int = 0
    completed_planning_snapshots: int = 0
    controller_calls: int = 0
    controller_snapshot_replays: int = 0
    environment_actions: int = 0
    generated_tokens: int = 0
    grounding_evaluations: int = 0
    gpu_operations: int = 0
    hypothesis_pool_constructions: int = 0
    lockbox_bytes_read: int = 0
    lockbox_path_operations: int = 0
    model_calls: int = 0
    network_calls: int = 0
    persistent_worker_starts: int = 0
    planner_calls: int = 0
    pure_selector_calls: int = 0
    pure_selector_control_calls: int = 0
    pure_selector_scene_order_calls: int = 0
    registered_scenes_read: int = 0
    reward_observations: int = 0
    rhae_observations: int = 0
    total_worker_starts: int = 0
    transient_worker_starts: int = 0
    v4_counterfactual_calls: int = 0

    def __post_init__(self) -> None:
        if set(self.__dataclass_fields__) != set(AUDIT_RESOURCE_COUNTER_FIELDS):
            raise RuntimeError("resource counter dataclass and registered inventory drifted")
        for name in AUDIT_RESOURCE_COUNTER_FIELDS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value != 0:
                raise ValueError(f"open-fixture resource counter {name} must remain zero")

    def as_json(self) -> dict[str, JsonValue]:
        return {name: getattr(self, name) for name in AUDIT_RESOURCE_COUNTER_FIELDS}


@dataclass(slots=True)
class AuditCounterState:
    """Mutable, schema-closed counters used only inside one audit execution."""

    _values: dict[str, int] = field(
        default_factory=lambda: {name: 0 for name in AUDIT_RESOURCE_COUNTER_FIELDS}
    )
    _scientific_exposure_started: bool = False
    _scientific_exposure_callback_failed: bool = False
    _exposure_callback: Callable[[], None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if set(self._values) != set(AUDIT_RESOURCE_COUNTER_FIELDS):
            raise ValueError("audit counter state differs from the registered inventory")
        if any(type(value) is not int or value < 0 for value in self._values.values()):
            raise ValueError("audit counters must be non-negative integers")

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._values:
            raise KeyError(f"unregistered audit counter: {name}")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("audit counter increments must be non-negative integers")
        self._values[name] += amount

    def mark_scientific_exposure_started(self) -> None:
        """Latch the first planning exposure without polluting scientific counters."""

        if self._scientific_exposure_callback_failed:
            raise RuntimeError("scientific exposure marker publication previously failed")
        if self._scientific_exposure_started:
            return
        self._scientific_exposure_started = True
        if self._exposure_callback is not None:
            try:
                self._exposure_callback()
            except BaseException:
                self._scientific_exposure_callback_failed = True
                raise

    @property
    def scientific_exposure_started(self) -> bool:
        return self._scientific_exposure_started

    def snapshot(self) -> dict[str, int]:
        return {name: self._values[name] for name in AUDIT_RESOURCE_COUNTER_FIELDS}

    def require_exact(self, expected: Mapping[str, int]) -> tuple[str, ...]:
        if set(expected) != set(AUDIT_RESOURCE_COUNTER_FIELDS):
            raise ValueError("expected counter mapping has the wrong schema")
        return tuple(
            name
            for name in AUDIT_RESOURCE_COUNTER_FIELDS
            if self._values[name] != expected[name]
        )


OPEN_FIXTURE_RESOURCE_COUNTERS: Final = ResourceCounters()
ACTION_QBC_AUDIT_SELECTOR: Final = select_action_conditional_qbc


def _action_json(action: Action | None) -> JsonValue:
    if action is None:
        return None
    return {
        "col": action.col,
        "kind": int(action.kind),
        "row": action.row,
    }


def _prediction_json(prediction: Prediction | None) -> JsonValue:
    if prediction is None:
        return None
    signature = prediction.signature()
    return {
        "game_state": str(prediction.game_state),
        "grid_bytes_sha256": hashlib.sha256(signature[1]).hexdigest(),
        "grid_shape": [signature[0][0], signature[0][1]],
        "level_delta": prediction.level_delta,
    }


def _snapshot_json(snapshot: PlanningSnapshot) -> dict[str, JsonValue]:
    rows: list[JsonValue] = []
    for action in snapshot.actions:
        rows.append(
            {
                "action": _action_json(action),
                "costs": [float(value) for value in snapshot.costs[action]],
                "predictions": [
                    _prediction_json(prediction)
                    for prediction in snapshot.predictions[action]
                ],
            }
        )
    return {
        "actions": [_action_json(action) for action in snapshot.actions],
        "cost_prediction_rows": rows,
        "hypothesis_ids": list(snapshot.hypothesis_ids),
        "invalid_hypothesis_ids": list(snapshot.invalid_hypothesis_ids),
        "weights": [float(value) for value in snapshot.weights],
    }


def _decision_json(selection: ActionQBCSelection, variant: str) -> dict[str, JsonValue]:
    decision = selection.m_decision if variant == "M" else selection.x_decision
    maximizers = (
        selection.m_utility_maximizers
        if variant == "M"
        else selection.x_utility_maximizers
    )
    return {
        "action": _action_json(decision.action),
        "gate_reason": decision.gate_reason,
        "mode": decision.mode,
        "probe_candidate": _action_json(decision.probe_candidate),
        "score": decision.score,
        "utility_maximizers": [_action_json(action) for action in maximizers],
    }


def _selection_json(selection: ActionQBCSelection) -> dict[str, JsonValue]:
    return {
        "exploit": {
            "action": _action_json(selection.exploit.action),
            "mean_cost": selection.exploit.mean_cost,
            "score": selection.exploit.score,
            "standard_deviation": selection.exploit.standard_deviation,
        },
        "historical_agreement": selection.historical_agreement,
        "historical_indifference": selection.historical_indifference,
        "m_decision": _decision_json(selection, "M"),
        "normalized_weights": list(selection.normalized_weights),
        "rows": [
            {
                "action": _action_json(row.action),
                "catastrophe_mass": row.catastrophe_mass,
                "eligible": row.eligible,
                "evsi": row.evsi,
                "exploit_mean_cost": row.exploit_mean_cost,
                "exploit_score": row.exploit_score,
                "exploit_standard_deviation": row.exploit_standard_deviation,
                "m_rank": row.m_rank,
                "m_selected": row.m_selected,
                "m_utility": row.m_utility,
                "outcome_cell_count": row.outcome_cell_count,
                "outcome_concentration": row.outcome_concentration,
                "x_rank": row.x_rank,
                "x_selected": row.x_selected,
                "x_utility": row.x_utility,
            }
            for row in selection.rows
        ],
        "x_decision": _decision_json(selection, "X"),
    }


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Serialize deterministic scientific records without platform-dependent whitespace."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _git(
    *arguments: str,
    root: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ("git", "-c", "core.quotepath=false", *arguments),
            cwd=root,
            check=check,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RegisteredAuditNotAuthorized(
            f"audit registration Git check failed: {' '.join(arguments)}"
        ) from error


def _require_clean_tagged_head(root: Path) -> str:
    status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        ".",
        f":(exclude){LOCKBOX_ARTIFACT_RELATIVE_PATH}",
        root=root,
    ).stdout
    if status:
        raise RegisteredAuditNotAuthorized(
            "registered-audit capability requires a completely clean worktree"
        )
    head = _git("rev-parse", "HEAD", root=root).stdout.decode("ascii").strip()
    tag = _git(
        "rev-parse",
        f"{AUDIT_REGISTRATION_TAG}^{{commit}}",
        root=root,
    ).stdout.decode("ascii").strip()
    if not _is_lower_hex(head, 40) or tag != head:
        raise RegisteredAuditNotAuthorized(
            "clean HEAD is not the frozen action-QBC audit registration tag"
        )
    return head


def _git_state_hashes(root: Path) -> dict[str, str]:
    pathspec = ("--", ".", f":(exclude){LOCKBOX_ARTIFACT_RELATIVE_PATH}")
    status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        *pathspec,
        root=root,
    ).stdout
    worktree_diff = _git(
        "diff",
        "--no-ext-diff",
        "--binary",
        "--no-color",
        *pathspec,
        root=root,
    ).stdout
    index_diff = _git(
        "diff",
        "--cached",
        "--no-ext-diff",
        "--binary",
        "--no-color",
        *pathspec,
        root=root,
    ).stdout
    if status or worktree_diff or index_diff:
        raise RegisteredAuditNotAuthorized(
            "registered-audit Git state differs from the clean tagged freeze"
        )
    return {
        "git_clean_status_sha256": _sha256(status),
        "git_index_diff_sha256": _sha256(index_diff),
        "git_worktree_diff_sha256": _sha256(worktree_diff),
    }


def _require_canonical_relative_path(relative: str) -> None:
    path = Path(relative)
    if (
        not relative
        or path.is_absolute()
        or "\\" in relative
        or path.as_posix() != relative
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"noncanonical registration path: {relative!r}")


def _read_plain_file(root: Path, relative: str) -> bytes:
    _require_canonical_relative_path(relative)
    if relative == LOCKBOX_ARTIFACT_RELATIVE_PATH:
        raise RegisteredAuditNotAuthorized(
            "capability issuance must not inspect the registered lockbox"
        )
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise RegisteredAuditNotAuthorized(
            f"registered audit input is not a plain file: {relative}"
        )
    return path.read_bytes()


def _require_committed_bytes(root: Path, head: str, relative: str, raw: bytes) -> None:
    committed = _git("show", f"{head}:{relative}", root=root).stdout
    if committed != raw:
        raise RegisteredAuditNotAuthorized(
            f"working bytes differ from the frozen audit commit: {relative}"
        )


def _source_file_manifest(root: Path) -> tuple[SourceFileIdentity, ...]:
    discovered_package_sources = tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in (root / "src" / "arc3_voi").rglob("*.py")
        )
    )
    frozen_package_sources = tuple(
        relative
        for relative in AUDIT_SOURCE_FILE_ORDER
        if relative.startswith("src/arc3_voi/") and relative.endswith(".py")
    )
    if discovered_package_sources != frozen_package_sources:
        raise RegisteredAuditNotAuthorized(
            "discovered package sources differ from the exhaustive frozen inventory"
        )
    return tuple(
        SourceFileIdentity(relative, _sha256(_read_plain_file(root, relative)))
        for relative in AUDIT_SOURCE_FILE_ORDER
    )


def _source_manifest_json(
    source_files: Sequence[SourceFileIdentity],
) -> list[JsonValue]:
    return [identity.as_json() for identity in source_files]


def load_audit_registration_admin(root: str | Path) -> ModuleType:
    """Load the registered admin script explicitly under Python isolated mode."""

    source = Path(root).resolve() / "scripts" / "build_action_qbc_audit_registration.py"
    spec = importlib.util.spec_from_file_location(
        "_arc3_action_qbc_audit_registration_admin",
        source,
    )
    if spec is None or spec.loader is None:
        raise RegisteredAuditNotAuthorized("audit registration admin module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
        raise
    return module


def _complete_provenance(
    *,
    head: str,
    registration_sha256: str,
    source_files: tuple[SourceFileIdentity, ...],
    git_state_hashes: Mapping[str, str],
) -> AuditProvenance:
    expected = EXPECTED_AUDIT_PROVENANCE
    return AuditProvenance(
        code_commit=head,
        config_sha256=expected.config_sha256,
        matrix_sha256=expected.matrix_sha256,
        registration_sha256=registration_sha256,
        source_files=source_files,
        source_manifest_sha256=canonical_sha256(_source_manifest_json(source_files)),
        git_clean_status_sha256=git_state_hashes["git_clean_status_sha256"],
        git_index_diff_sha256=git_state_hashes["git_index_diff_sha256"],
        git_worktree_diff_sha256=git_state_hashes["git_worktree_diff_sha256"],
        audit_contract_version=expected.audit_contract_version,
        registration_schema_version=expected.registration_schema_version,
        resource_counter_schema_sha256=expected.resource_counter_schema_sha256,
        runtime_version=expected.runtime_version,
        completion_cost_policy_version=expected.completion_cost_policy_version,
        completion_cost_policy_sha256=expected.completion_cost_policy_sha256,
        probe_policy_version=expected.probe_policy_version,
        probe_policy_sha256=expected.probe_policy_sha256,
        candidate_policy_version=expected.candidate_policy_version,
        candidate_policy_sha256=expected.candidate_policy_sha256,
        compiler_contract_version=expected.compiler_contract_version,
        compiler_contract_sha256=expected.compiler_contract_sha256,
        generator_version=expected.generator_version,
        generator_contract_sha256=expected.generator_contract_sha256,
        generator_source_commit=expected.generator_source_commit,
        generator_source_sha256=expected.generator_source_sha256,
        lockbox_artifact_path=expected.lockbox_artifact_path,
        lockbox_artifact_size_bytes=expected.lockbox_artifact_size_bytes,
        lockbox_artifact_sha256=expected.lockbox_artifact_sha256,
        lockbox_content_sha256=expected.lockbox_content_sha256,
    )


def _revalidate_registered_capability_state(
    state: _RegisteredCapabilityState,
) -> ModuleType:
    """Recheck durable permit, registration, source, and Git identity before use."""

    repository = state.root
    launch_state = _registered_launch_attestation_state(
        state.launch_attestation,
        consume_phase=None,
    )
    _revalidate_registered_launch_attestation_state(launch_state)
    if (
        launch_state.root != repository
        or launch_state.attestation_sha256 != state.launch_attestation_sha256
    ):
        raise RegisteredAuditNotAuthorized(
            "registered capability launch-attestation binding changed"
        )
    provenance = state.provenance
    source_files = provenance.source_files
    if (
        not provenance.fully_frozen
        or not _is_lower_hex(provenance.code_commit, 40)
        or not _is_lower_hex(provenance.registration_sha256, 64)
        or not _is_lower_hex(provenance.source_manifest_sha256, 64)
        or source_files is None
        or tuple(identity.path for identity in source_files) != AUDIT_SOURCE_FILE_ORDER
        or any(not _is_lower_hex(identity.sha256, 64) for identity in source_files)
        or canonical_sha256(_source_manifest_json(source_files))
        != provenance.source_manifest_sha256
    ):
        raise RegisteredAuditNotAuthorized("registered-audit provenance is malformed")
    expected = EXPECTED_AUDIT_PROVENANCE
    static_fields = tuple(
        field for field in expected.as_json() if field not in PENDING_FREEZE_FIELDS
    )
    if any(
        getattr(provenance, field) != getattr(expected, field)
        for field in static_fields
    ):
        raise RegisteredAuditNotAuthorized("registered-audit provenance identity mismatch")
    permit = state.consumed_permit
    if (
        permit.get("consumed") is not True
        or permit.get("code_commit") != provenance.code_commit
        or permit.get("registration_sha256") != provenance.registration_sha256
        or permit.get("source_manifest_sha256") != provenance.source_manifest_sha256
        or permit.get("run_label") not in {"primary", "replica"}
    ):
        raise RegisteredAuditNotAuthorized(
            "registered-audit capability is not bound to a consumed two-start permit"
        )
    head = _require_clean_tagged_head(repository)
    if head != provenance.code_commit:
        raise RegisteredAuditNotAuthorized(
            "registered-audit capability no longer matches the clean tagged HEAD"
        )
    current_git_state = _git_state_hashes(repository)
    if any(
        current_git_state[name] != getattr(provenance, name)
        for name in (
            "git_clean_status_sha256",
            "git_index_diff_sha256",
            "git_worktree_diff_sha256",
        )
    ):
        raise RegisteredAuditNotAuthorized(
            "registered-audit capability Git-state hashes changed"
        )
    try:
        registration = load_audit_registration_admin(repository)
        registration_value, registration_raw = registration.load_validated_registration(
            repository,
            AUDIT_REGISTRATION_RELATIVE_PATH,
        )
    except Exception as error:
        raise RegisteredAuditNotAuthorized(
            "dedicated action-QBC audit registration revalidation failed"
        ) from error
    if _sha256(registration_raw) != provenance.registration_sha256:
        raise RegisteredAuditNotAuthorized("audit registration bytes changed after issuance")
    _require_committed_bytes(
        repository,
        head,
        AUDIT_REGISTRATION_RELATIVE_PATH,
        registration_raw,
    )
    frozen = registration_value.get("frozen_files")
    if not isinstance(frozen, Mapping):
        raise RegisteredAuditNotAuthorized("registration frozen-file manifest is malformed")
    registered_source_rows = frozen.get("files")
    if (
        not isinstance(registered_source_rows, list)
        or registered_source_rows != _source_manifest_json(source_files)
        or frozen.get("manifest_sha256") != provenance.source_manifest_sha256
    ):
        raise RegisteredAuditNotAuthorized(
            "registration/source identity changed after capability issuance"
        )
    try:
        registration.validate_consumed_audit_start_permit(
            permit,
            expected_repository_root=repository,
            expected_code_commit=head,
            expected_registration_sha256=provenance.registration_sha256,
            expected_source_manifest_sha256=provenance.source_manifest_sha256,
        )
    except Exception as error:
        raise RegisteredAuditNotAuthorized(
            "durable consumed audit permit revalidation failed"
        ) from error
    config_raw = _read_plain_file(repository, AUDIT_CONFIG_RELATIVE_PATH)
    if _sha256(config_raw) != AUDIT_CONFIG_FILE_SHA256:
        raise RegisteredAuditNotAuthorized(
            "registered action-QBC config file identity mismatch"
        )
    _require_committed_bytes(
        repository,
        head,
        AUDIT_CONFIG_RELATIVE_PATH,
        config_raw,
    )
    current_sources = _source_file_manifest(repository)
    if current_sources != source_files:
        raise RegisteredAuditNotAuthorized("audit source bytes changed after issuance")
    for identity in current_sources:
        _require_committed_bytes(
            repository,
            head,
            identity.path,
            _read_plain_file(repository, identity.path),
        )
    return registration


type _CapabilityIssuer = Callable[..., RegisteredAuditCapability]
type _CapabilityLookup = Callable[..., _RegisteredCapabilityState]


def _build_registered_capability_api() -> tuple[_CapabilityIssuer, _CapabilityLookup]:
    registry: dict[RegisteredAuditCapability, _RegisteredCapabilityState] = {}
    registry_lock = Lock()

    def lookup(
        capability: RegisteredAuditCapability | None,
        *,
        consume_read: bool,
    ) -> _RegisteredCapabilityState:
        if capability is None or not isinstance(capability, RegisteredAuditCapability):
            raise RegisteredAuditNotAuthorized(
                "an explicit registered-audit capability is required"
            )
        with registry_lock:
            state = registry.get(capability)
            if state is None:
                raise RegisteredAuditNotAuthorized(
                    "registered-audit capability was not issued by this process"
                )
            if consume_read:
                if state.read_authorization_consumed:
                    raise RegisteredAuditNotAuthorized(
                        "registered-audit capability read authorization is exhausted"
                    )
                state.read_authorization_consumed = True
            return state

    def issue(
        *,
        root: str | Path,
        launch_attestation: RegisteredAuditLaunchAttestation | None,
        registration_path: str | Path = AUDIT_REGISTRATION_RELATIVE_PATH,
        consumed_permit: Mapping[str, object] | None = None,
    ) -> RegisteredAuditCapability:
        """Issue only from exact frozen files and sources at a clean tagged HEAD."""

        repository = Path(root).resolve()
        launch_state = _consume_registered_launch_attestation_for_capability(
            launch_attestation,
            repository_root=repository,
        )
        head = _require_clean_tagged_head(repository)
        git_state_hashes = _git_state_hashes(repository)
        supplied = Path(registration_path).as_posix()
        if supplied != AUDIT_REGISTRATION_RELATIVE_PATH:
            raise RegisteredAuditNotAuthorized(
                "only the canonical action-QBC audit registration path is accepted"
            )
        try:
            registration = load_audit_registration_admin(repository)
            registration_value, registration_raw = registration.load_validated_registration(
                repository,
                supplied,
            )
        except Exception as error:
            raise RegisteredAuditNotAuthorized(
                "dedicated action-QBC audit registration validation failed"
            ) from error
        registration_sha256 = _sha256(registration_raw)
        frozen = registration_value.get("frozen_files")
        if not isinstance(frozen, Mapping):
            raise RegisteredAuditNotAuthorized(
                "registration frozen-file manifest is malformed"
            )
        source_manifest_sha256 = frozen.get("manifest_sha256")
        if not isinstance(source_manifest_sha256, str):
            raise RegisteredAuditNotAuthorized(
                "registration source-manifest identity is malformed"
            )
        if consumed_permit is None:
            raise RegisteredAuditNotAuthorized(
                "a durably consumed primary/replica audit permit is required"
            )
        if (
            launch_state.consumed_permit_sha256
            != canonical_sha256(cast(JsonValue, dict(consumed_permit)))
            or launch_state.run_label != consumed_permit.get("run_label")
            or launch_state.code_commit != head
            or launch_state.registration_sha256 != registration_sha256
            or launch_state.source_manifest_sha256 != source_manifest_sha256
        ):
            raise RegisteredAuditNotAuthorized(
                "launch attestation differs from the consumed permit/freeze"
            )
        try:
            registration.validate_consumed_audit_start_permit(
                consumed_permit,
                expected_repository_root=repository,
                expected_code_commit=head,
                expected_registration_sha256=registration_sha256,
                expected_source_manifest_sha256=source_manifest_sha256,
            )
        except Exception as error:
            raise RegisteredAuditNotAuthorized(
                "consumed audit permit validation failed"
            ) from error
        config_raw = _read_plain_file(repository, AUDIT_CONFIG_RELATIVE_PATH)
        if _sha256(config_raw) != AUDIT_CONFIG_FILE_SHA256:
            raise RegisteredAuditNotAuthorized(
                "registered action-QBC config file identity mismatch"
            )
        _require_committed_bytes(
            repository,
            head,
            AUDIT_CONFIG_RELATIVE_PATH,
            config_raw,
        )
        _require_committed_bytes(repository, head, supplied, registration_raw)
        source_files = _source_file_manifest(repository)
        registered_source_rows = frozen.get("files")
        if (
            not isinstance(registered_source_rows, list)
            or registered_source_rows != _source_manifest_json(source_files)
            or canonical_sha256(cast(JsonValue, registered_source_rows))
            != source_manifest_sha256
        ):
            raise RegisteredAuditNotAuthorized(
                "dedicated registration differs from the exhaustive source manifest"
            )
        for relative in AUDIT_SOURCE_FILE_ORDER:
            raw = _read_plain_file(repository, relative)
            _require_committed_bytes(repository, head, relative, raw)
        capability = object.__new__(RegisteredAuditCapability)
        state = _RegisteredCapabilityState(
            root=repository,
            consumed_permit=MappingProxyType(dict(consumed_permit)),
            launch_attestation=cast(
                RegisteredAuditLaunchAttestation, launch_attestation
            ),
            launch_attestation_sha256=launch_state.attestation_sha256,
            provenance=_complete_provenance(
                head=head,
                registration_sha256=registration_sha256,
                source_files=source_files,
                git_state_hashes=git_state_hashes,
            ),
        )
        with registry_lock:
            registry[capability] = state
        return capability

    return issue, lookup


issue_registered_audit_capability, _registered_capability_state = (
    _build_registered_capability_api()
)


@dataclass(frozen=True, slots=True)
class PipelineAuditResult:
    """One complete compiler-to-selector audit over a single visible grid."""

    history: History
    actions: tuple[Action, ...]
    cached_points: tuple[tuple[int, int], ...]
    source_roles: tuple[str, ...]
    source_manifest: tuple[dict[str, JsonValue], ...]
    program_rows: tuple[dict[str, Any], ...]
    persistent_worker_rows: tuple[dict[str, Any], ...]
    snapshot: PlanningSnapshot
    selection: ActionQBCSelection
    controller_rows: tuple[dict[str, JsonValue], ...]


def _history_fingerprint(history: History) -> str:
    payload: dict[str, JsonValue] = {
        "available_actions": cast(
            JsonValue,
            [
            sorted(int(kind) for kind in action_set)
            for action_set in history.available_action_sets
            ],
        ),
        "frames": [
            {
                "bytes_sha256": _sha256(frame.tobytes(order="C")),
                "shape": [int(frame.shape[0]), int(frame.shape[1])],
            }
            for frame in history.frames
        ],
        "game_states": [state.value for state in history.game_states],
        "level_deltas": list(history.level_deltas),
        "levels": list(history.levels),
    }
    return canonical_sha256(payload)


def _scene_history(
    grid_record: Mapping[str, Any],
    base_scene: Mapping[str, Any],
) -> History:
    grid = grid_record.get("grid")
    if not isinstance(grid, list):
        raise ValueError("scene grid is not a JSON array")
    expected_shape = grid_record.get("grid_shape")
    array = np.asarray(grid, dtype=np.int16)
    if (
        array.ndim != 2
        or list(array.shape) != expected_shape
        or not np.issubdtype(array.dtype, np.integer)
    ):
        raise ValueError("scene grid differs from its declared two-dimensional shape")
    raw_actions = base_scene.get("available_actions")
    if raw_actions != ["ACTION3", "ACTION6"]:
        raise ValueError("audit scenes must expose exactly ACTION3 and ACTION6")
    level = base_scene.get("level")
    win_levels = base_scene.get("win_levels")
    persistence = base_scene.get("initial_persistence")
    if (level, win_levels, persistence) != (1, 9, 0.5):
        raise ValueError("scene level/persistence metadata differs from registration")
    observation = Observation(
        array,
        frozenset({ActionKind.ACTION3, ActionKind.ACTION6}),
        GameState.NOT_FINISHED,
        level=1,
        win_levels=9,
    )
    return History.from_observation(observation)


def _compiled_points(sources: Sequence[StructuredPriorSource]) -> tuple[tuple[int, int], ...]:
    points: list[tuple[int, int]] = []
    for source in sources:
        for point in candidate_points_from_source(source.source):
            if point not in points:
                points.append(point)
    return tuple(points)


def _source_rows(
    sources: Sequence[StructuredPriorSource],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "candidate_index": index,
            "assigned_role": source.role,
            "source": source.source,
            "source_sha256": _sha256(source.source.encode("utf-8")),
        }
        for index, source in enumerate(sources)
    )


def _grounding_memory_row(item: EvaluatedSource) -> dict[str, Any]:
    result = item.result
    headroom = (
        None
        if result.memory_baseline_bytes is None or result.memory_ceiling_bytes is None
        else result.memory_ceiling_bytes - result.memory_baseline_bytes
    )
    return {
        "hard_limit_enforced": result.hard_memory_limit_enforced,
        "limit_kind": result.memory_limit_kind,
        "allocation_headroom_bytes": headroom,
        "diagnostic": result.memory_limit_diagnostic,
    }


def _persistent_memory_row(hypothesis: ExecutableHypothesis) -> dict[str, Any]:
    metadata = hypothesis.worker_metadata
    if metadata is None:
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "hard_limit_enforced": None,
            "limit_kind": None,
            "allocation_headroom_bytes": None,
            "diagnostic": "persistent worker startup metadata is absent",
        }
    headroom = (
        None
        if metadata.memory_baseline_bytes is None or metadata.memory_ceiling_bytes is None
        else metadata.memory_ceiling_bytes - metadata.memory_baseline_bytes
    )
    return {
        "hypothesis_id": hypothesis.hypothesis_id,
        "hard_limit_enforced": metadata.hard_memory_limit_enforced,
        "limit_kind": metadata.memory_limit_kind,
        "allocation_headroom_bytes": headroom,
        "diagnostic": metadata.memory_limit_diagnostic,
    }


class VerifyingSnapshotPlanner:
    """Return one exact precomputed snapshot only after replay-input verification."""

    completion_cost_policy = PATH_DEFICIT_POLICY_VERSION
    completion_cost_policy_sha256 = PATH_DEFICIT_POLICY_SHA256

    def __init__(
        self,
        history: History,
        snapshot: PlanningSnapshot,
    ) -> None:
        self._history_sha256 = _history_fingerprint(history)
        self._snapshot = snapshot
        self.calls = 0

    def evaluate(
        self,
        history: History,
        actions: Sequence[Action],
        weighted_hypotheses: Sequence[tuple[Hypothesis, float]],
        *,
        win_levels: int,
        deadline: float | None = None,
    ) -> PlanningSnapshot:
        del deadline
        if _history_fingerprint(history) != self._history_sha256:
            raise ValueError("controller replay history differs from audited planning history")
        if tuple(actions) != self._snapshot.actions or win_levels != 9:
            raise ValueError("controller replay action/level inputs differ from snapshot")
        ids = tuple(hypothesis.hypothesis_id for hypothesis, _weight in weighted_hypotheses)
        weights = tuple(float(weight) for _hypothesis, weight in weighted_hypotheses)
        if ids != self._snapshot.hypothesis_ids or len(weights) != len(
            self._snapshot.weights
        ):
            raise ValueError("controller replay committee identity differs from snapshot")
        if any(
            not isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
            for actual, expected in zip(weights, self._snapshot.weights, strict=True)
        ):
            raise ValueError("controller replay Gibbs weights differ from snapshot")
        self.calls += 1
        return self._snapshot


def _forbidden_direct_policy(
    _history: History,
    _actions: tuple[Action, ...],
    _budget: Budget,
) -> Action:
    raise AssertionError("direct policy was reached during sealed committee replay")


def _controller_action_record(action: Action) -> dict[str, JsonValue]:
    return {"col": action.col, "kind": action.kind.name, "row": action.row}


def _controller_action_key(action: Action) -> str:
    if action.kind is ActionKind.ACTION6:
        return f"ACTION6({action.row},{action.col})"
    return action.kind.name


def _controller_candidate_rows(selection: ActionQBCSelection) -> list[JsonValue]:
    return [
        {
            "action": _controller_action_record(row.action),
            "catastrophe_mass": row.catastrophe_mass,
            "eligible": row.eligible,
            "evsi": row.evsi,
            "exploit_mean_cost": row.exploit_mean_cost,
            "exploit_score": row.exploit_score,
            "exploit_standard_deviation": row.exploit_standard_deviation,
            "m_rank": row.m_rank,
            "m_selected": row.m_selected,
            "m_utility": row.m_utility,
            "outcome_cell_count": row.outcome_cell_count,
            "outcome_concentration": row.outcome_concentration,
            "x_rank": row.x_rank,
            "x_selected": row.x_selected,
            "x_utility": row.x_utility,
        }
        for row in selection.rows
    ]


def _parse_controller_json(diagnostics: Mapping[str, Any], key: str) -> JsonValue:
    raw = diagnostics.get(key)
    if not isinstance(raw, str):
        raise RuntimeError(f"controller replay omitted {key}")
    parsed: Any = json.loads(raw)
    return cast(JsonValue, parsed)


def _require_controller_trace_equal(
    *,
    decision_action: Action,
    decision_mode: str,
    decision_score: float,
    diagnostics: Mapping[str, Any],
    selection: ActionQBCSelection,
    variant: Variant,
) -> dict[str, JsonValue]:
    authoritative = (
        selection.m_decision if variant is Variant.MYOPIC else selection.x_decision
    )
    expected_rows = _controller_candidate_rows(selection)
    observed_rows = _parse_controller_json(diagnostics, "action_qbc_candidate_rows")
    expected_m_maximizers: JsonValue = [
        _controller_action_record(action) for action in selection.m_utility_maximizers
    ]
    expected_x_maximizers: JsonValue = [
        _controller_action_record(action) for action in selection.x_utility_maximizers
    ]
    observed_m_maximizers = _parse_controller_json(
        diagnostics, "m_utility_maximizer_actions"
    )
    observed_x_maximizers = _parse_controller_json(
        diagnostics, "x_utility_maximizer_actions"
    )
    probe_row = next(
        (
            row
            for row in selection.rows
            if row.action == authoritative.probe_candidate
        ),
        None,
    )
    expected_trace: dict[str, JsonValue] = {
        "candidate_rows": expected_rows,
        "m_decision_action": _controller_action_key(selection.m_decision.action),
        "m_decision_mode": selection.m_decision.mode,
        "m_utility_maximizers": expected_m_maximizers,
        "probe_candidate_action": (
            None
            if authoritative.probe_candidate is None
            else _controller_action_key(authoritative.probe_candidate)
        ),
        "probe_cap": MAX_PROBES_PER_LEVEL,
        "probe_catastrophe_probability": (
            None if probe_row is None else probe_row.catastrophe_mass
        ),
        "probe_count_before": 0,
        "probe_evsi": None if probe_row is None else probe_row.evsi,
        "probe_gate_reason": authoritative.gate_reason,
        "probe_selected": authoritative.mode == "probe",
        "probe_utility": (
            None
            if probe_row is None
            else (
                probe_row.m_utility
                if variant is Variant.MYOPIC
                else probe_row.x_utility
            )
        ),
        "x_decision_action": _controller_action_key(selection.x_decision.action),
        "x_decision_mode": selection.x_decision.mode,
        "x_utility_maximizers": expected_x_maximizers,
    }
    observed_trace: dict[str, JsonValue] = {
        "candidate_rows": observed_rows,
        "m_decision_action": cast(JsonValue, diagnostics.get("m_decision_action")),
        "m_decision_mode": cast(JsonValue, diagnostics.get("m_decision_mode")),
        "m_utility_maximizers": observed_m_maximizers,
        "probe_candidate_action": cast(
            JsonValue, diagnostics.get("probe_candidate_action")
        ),
        "probe_cap": cast(JsonValue, diagnostics.get("probe_cap")),
        "probe_catastrophe_probability": cast(
            JsonValue, diagnostics.get("probe_catastrophe_probability")
        ),
        "probe_count_before": cast(JsonValue, diagnostics.get("probe_count_before")),
        "probe_evsi": cast(JsonValue, diagnostics.get("probe_evsi")),
        "probe_gate_reason": cast(JsonValue, diagnostics.get("probe_gate_reason")),
        "probe_selected": cast(JsonValue, diagnostics.get("probe_selected")),
        "probe_utility": cast(JsonValue, diagnostics.get("probe_utility")),
        "x_decision_action": cast(JsonValue, diagnostics.get("x_decision_action")),
        "x_decision_mode": cast(JsonValue, diagnostics.get("x_decision_mode")),
        "x_utility_maximizers": observed_x_maximizers,
    }
    if observed_trace != expected_trace:
        raise RuntimeError("controller diagnostics differ from the standalone selector")
    if (
        decision_action != authoritative.action
        or decision_mode != authoritative.mode
        or not isclose(
            decision_score, authoritative.score, rel_tol=1e-12, abs_tol=1e-12
        )
    ):
        raise RuntimeError("controller action, mode, or score differs from selector")
    return {
        "candidate_rows_sha256": canonical_sha256(observed_rows),
        "selector_trace_sha256": canonical_sha256(observed_trace),
    }


def _controller_replay_rows(
    *,
    history: History,
    snapshot: PlanningSnapshot,
    pool: HypothesisPool,
    cached_points: Sequence[tuple[int, int]],
    selection: ActionQBCSelection,
    counters: AuditCounterState,
) -> tuple[dict[str, JsonValue], ...]:
    observation = Observation(
        history.latest_grid,
        history.latest_action_set,
        history.latest_game_state,
        level=history.current_level,
        win_levels=9,
    )
    rows: list[dict[str, JsonValue]] = []
    for variant in (Variant.MYOPIC, Variant.CROSS_LEVEL):
        replay = VerifyingSnapshotPlanner(history, snapshot)
        controller = V5Controller(
            direct_policy=_forbidden_direct_policy,
            pool=pool,
            config=V5ControllerConfig(variant=variant),
            cached_points=cached_points,
            planner=replay,
        )
        counters.increment("controller_calls")
        counters.increment("pure_selector_calls")
        counters.increment("pure_selector_scene_order_calls")
        decision = controller.act(observation, Budget())
        if replay.calls != 1:
            raise RuntimeError("controller did not consume exactly one verified snapshot replay")
        counters.increment("controller_snapshot_replays")
        trace = _require_controller_trace_equal(
            decision_action=decision.action,
            decision_mode=decision.mode.value,
            decision_score=decision.score,
            diagnostics=decision.diagnostics,
            selection=selection,
            variant=variant,
        )
        rows.append(
            {
                "action": _action_json(decision.action),
                **trace,
                "decision_mode": decision.mode.value,
                "implementation_contract_version": cast(
                    str,
                    decision.diagnostics["implementation_contract_version"],
                ),
                "probe_disagreement_policy_sha256": cast(
                    str,
                    decision.diagnostics["probe_disagreement_policy_sha256"],
                ),
                "probe_disagreement_policy_version": cast(
                    str,
                    decision.diagnostics["probe_disagreement_policy_version"],
                ),
                "replay_calls": replay.calls,
                "variant": variant.value,
            }
        )
    return tuple(rows)


def _validate_pipeline_config(config: SystemConfig) -> None:
    observed = (
        config.experiment.implementation_contract_version,
        config.planning.probe_disagreement_policy_version,
        config.planning.probe_disagreement_policy_sha256,
        config.planning.outcome_concentration_threshold,
        config.planning.completion_cost_policy_version,
        config.planning.max_candidates,
        config.planning.depth,
        config.planning.beam_width,
        config.planning.max_probes_per_level,
        config.planning.risk_coefficient,
        config.planning.robust_std_coefficient,
        config.hypotheses.max_hypotheses,
        config.hypotheses.eta,
        config.hypotheses.complexity_lambda,
        config.sandbox.timeout_ms,
        config.sandbox.memory_mb,
    )
    expected = (
        ACTION_QBC_RUNTIME_VERSION,
        ACTION_QBC_POLICY_VERSION,
        ACTION_QBC_POLICY_SHA256,
        0.8,
        PATH_DEFICIT_POLICY_VERSION,
        12,
        4,
        8,
        3,
        3.0,
        0.5,
        4,
        5.0,
        0.002,
        100,
        256,
    )
    if observed != expected:
        raise ValueError("audit configuration differs from the fixed runtime-v5 contract")
    if (
        CANDIDATE_POLICY_HASH != CANDIDATE_POLICY_SHA256
        or IMPLEMENTED_CANDIDATE_POLICY_VERSION != CANDIDATE_POLICY_VERSION
        or STRUCTURED_PRIOR_CONTRACT_VERSION != COMPILER_CONTRACT_VERSION
        or STRUCTURED_PRIOR_CONTRACT_SHA256 != COMPILER_CONTRACT_SHA256
    ):
        raise RuntimeError("candidate/compiler implementation identity drifted")


def _evaluate_source_programs_counted(
    rows: Sequence[Mapping[str, Any]],
    history: History,
    actions: Sequence[Action],
    *,
    config: SystemConfig,
    counters: AuditCounterState,
) -> tuple[EvaluatedSource, ...]:
    """Ground validated sources while counting only calls actually attempted."""

    validated: list[tuple[int, str, str, str | None, bool, bool]] = []
    for expected_index, row in enumerate(rows):
        if row.get("candidate_index") != expected_index:
            raise ValueError("source candidate indices must be contiguous and ordered")
        source = row.get("source")
        role = row.get("assigned_role")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"candidate {expected_index} has no source program")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"candidate {expected_index} has no assigned role")
        if row.get("source_sha256") != _sha256(source.encode("utf-8")):
            raise ValueError(f"candidate {expected_index} source digest mismatch")
        require_sensitivity, require_goal = role_requirements(expected_index)
        try:
            hypothesis_id = validate_program(source).sha256
        except Exception:
            hypothesis_id = None
        validated.append(
            (
                expected_index,
                role,
                source,
                hypothesis_id,
                require_sensitivity,
                require_goal,
            )
        )
    evaluated: list[EvaluatedSource] = []
    for (
        candidate_index,
        role,
        source,
        hypothesis_id,
        require_sensitivity,
        require_goal,
    ) in validated:
        counters.mark_scientific_exposure_started()
        counters.increment("grounding_evaluations")
        counters.increment("transient_worker_starts")
        counters.increment("total_worker_starts")
        result = evaluate_program_grounding(
            source,
            history,
            actions,
            timeout_seconds=config.sandbox.timeout_ms / 1000.0,
            memory_limit_mb=config.sandbox.memory_mb,
            rollout_depth=config.planning.depth,
            require_action_sensitivity=require_sensitivity,
            require_goal_conditioning=require_goal,
        )
        evaluated.append(
            EvaluatedSource(candidate_index, role, source, hypothesis_id, result)
        )
    return tuple(evaluated)


def evaluate_compiler_planner_snapshot(
    history: History,
    *,
    config: SystemConfig,
    counters: AuditCounterState,
    supplied_actions: Sequence[Action] | None = None,
    exercise_controllers: bool,
) -> PipelineAuditResult:
    """Execute the registered compiler/grounding/pool/planner/selector path once."""

    _validate_pipeline_config(config)
    counters.increment("compiler_calls")
    sources = instantiate_structured_priors(history)
    if tuple(source.role for source in sources) != STRUCTURED_PRIOR_ROLES or len(sources) != 4:
        raise RuntimeError("scene compiler did not supply the exact four registered roles")
    counters.increment("compiled_programs", len(sources))
    points = _compiled_points(sources)
    if supplied_actions is None:
        counters.increment("candidate_builder_calls")
        actions = candidates_from_history(
            history,
            cached_points=points,
            max_candidates=config.planning.max_candidates,
        )
    else:
        actions = tuple(supplied_actions)
        if not actions or len(actions) > config.planning.max_candidates:
            raise ValueError("fixed mapped action list violates candidate bounds")
    rows = _source_rows(sources)
    evaluated = _evaluate_source_programs_counted(
        rows,
        history,
        actions,
        config=config,
        counters=counters,
    )
    selected: tuple[ExecutableHypothesis, ...] = ()

    def counted_hypothesis_factory(
        source: str,
        **kwargs: Any,
    ) -> ExecutableHypothesis:
        hypothesis = ExecutableHypothesis(source, **kwargs)
        counters.increment("persistent_worker_starts")
        counters.increment("total_worker_starts")
        return hypothesis

    try:
        selected, deduplicated_ids = construct_eligible_hypotheses(
            evaluated,
            history,
            actions,
            timeout_seconds=config.sandbox.timeout_ms / 1000.0,
            memory_limit_mb=config.sandbox.memory_mb,
            max_hypotheses=config.hypotheses.max_hypotheses,
            hypothesis_factory=counted_hypothesis_factory,
        )
        pool = HypothesisPool.from_hypotheses(
            selected,
            eta=config.hypotheses.eta,
            complexity_lambda=config.hypotheses.complexity_lambda,
            max_hypotheses=config.hypotheses.max_hypotheses,
        )
        counters.increment("hypothesis_pool_constructions")
        planner = BeamSearchPlanner(
            depth=config.planning.depth,
            beam_width=config.planning.beam_width,
            parallel_hypotheses=False,
            completion_cost_policy=PATH_DEFICIT_POLICY_VERSION,
        )
        counters.increment("planner_calls")
        snapshot = planner.evaluate(
            history,
            actions,
            pool.weighted_hypotheses,
            win_levels=9,
        )
        counters.increment("completed_planning_snapshots")
        counters.increment("pure_selector_calls")
        counters.increment("pure_selector_scene_order_calls")
        selection = ACTION_QBC_AUDIT_SELECTOR(
            snapshot,
            cross_level_multiplier=level_multiplier(1, 9, 0.5),
            probes_used=0,
            probe_cap=MAX_PROBES_PER_LEVEL,
        )
        controller_rows = (
            _controller_replay_rows(
                history=history,
                snapshot=snapshot,
                pool=pool,
                cached_points=points,
                selection=selection,
                counters=counters,
            )
            if exercise_controllers
            else ()
        )
        selected_ids = {hypothesis.hypothesis_id for hypothesis in selected}
        program_rows = tuple(
            {
                "assigned_role": item.assigned_role,
                "ast_nodes": item.result.ast_nodes,
                "behavior_signature": item.result.behavior_signature,
                "candidate_index": item.candidate_index,
                "eligible": item.result.eligible,
                "goal_value_ok": item.result.goal_value_ok,
                "all_actions_ok": item.result.all_actions_ok,
                "sandbox_valid": item.result.sandbox_valid,
                "palette_conflicts": len(item.result.palette_conflicts),
                "hypothesis_id": item.hypothesis_id,
                "selected": item.hypothesis_id in selected_ids,
                "grounding_worker_memory": _grounding_memory_row(item),
            }
            for item in evaluated
        )
        source_manifest: tuple[dict[str, JsonValue], ...] = tuple(
            {
                "bindings_sha256": canonical_sha256(cast(JsonValue, dict(source.bindings))),
                "evidence_sha256": canonical_sha256(list(source.evidence)),
                "role": source.role,
                "source_sha256": cast(str, rows[index]["source_sha256"]),
            }
            for index, source in enumerate(sources)
        )
        if deduplicated_ids:
            raise RuntimeError("behavioral deduplication removed a registered compiler role")
        return PipelineAuditResult(
            history=history,
            actions=tuple(actions),
            cached_points=points,
            source_roles=tuple(source.role for source in sources),
            source_manifest=source_manifest,
            program_rows=program_rows,
            persistent_worker_rows=tuple(
                _persistent_memory_row(hypothesis) for hypothesis in selected
            ),
            snapshot=snapshot,
            selection=selection,
            controller_rows=controller_rows,
        )
    finally:
        for hypothesis in selected:
            hypothesis.close()


def _pipeline_json(result: PipelineAuditResult) -> dict[str, JsonValue]:
    return {
        "actions": [_action_json(action) for action in result.actions],
        "candidate_set_sha256": canonical_sha256(
            [_action_json(action) for action in result.actions]
        ),
        "controller_rows": list(result.controller_rows),
        "history_sha256": _history_fingerprint(result.history),
        "persistent_worker_rows": cast(JsonValue, list(result.persistent_worker_rows)),
        "planning": {
            "hypothesis_ids": list(result.snapshot.hypothesis_ids),
            "invalid_hypothesis_ids": list(result.snapshot.invalid_hypothesis_ids),
            "rows": [
                {
                    "action": _action_json(action),
                    "costs": [float(value) for value in result.snapshot.costs[action]],
                    "predictions": [
                        _prediction_json(prediction)
                        for prediction in result.snapshot.predictions[action]
                    ],
                }
                for action in result.snapshot.actions
            ],
            "weights": list(result.snapshot.weights),
        },
        "program_rows": cast(JsonValue, list(result.program_rows)),
        "selection": _selection_json(result.selection),
        "source_manifest": list(result.source_manifest),
        "source_roles": list(result.source_roles),
    }


def _worker_memory_valid(row: Mapping[str, Any]) -> bool:
    return (
        row.get("hard_limit_enforced") is True
        and row.get("limit_kind") == RLIMIT_DATA_HEADROOM_KIND
        and row.get("allocation_headroom_bytes") == 268_435_456
        and row.get("diagnostic") is None
    )


FORBIDDEN_AUDIT_RESOURCE_FIELDS: Final = (
    "environment_actions",
    "generated_tokens",
    "gpu_operations",
    "model_calls",
    "network_calls",
    "reward_observations",
    "rhae_observations",
)


@dataclass(frozen=True, slots=True)
class AdmissionResourceSignals:
    """Pure fail-closed dimensions shared by scene gates and negative controls."""

    invalid_programs: int = 0
    timeout_programs: int = 0
    eligible_graded_roles: int = 2
    worker_memory_ok: bool = True
    probe_cap_available: bool = True
    forbidden_resource_counts: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType(
            {name: 0 for name in FORBIDDEN_AUDIT_RESOURCE_FIELDS}
        )
    )


def _admission_resource_gate(
    signals: AdmissionResourceSignals,
) -> dict[str, JsonValue]:
    reasons: list[str] = []
    if signals.invalid_programs:
        reasons.append("invalid_program")
    if signals.timeout_programs:
        reasons.append("timeout_program")
    if signals.eligible_graded_roles < 2:
        reasons.append("fewer_than_two_eligible_graded_roles")
    if not signals.worker_memory_ok:
        reasons.append("worker_memory_drift")
    if not signals.probe_cap_available:
        reasons.append("probe_cap_exhausted")
    resource_counts = dict(signals.forbidden_resource_counts)
    if set(resource_counts) != set(FORBIDDEN_AUDIT_RESOURCE_FIELDS):
        reasons.append("forbidden_resource_schema_drift")
    used_resources = sorted(name for name, value in resource_counts.items() if value != 0)
    if used_resources:
        reasons.append("forbidden_resource_use")
    return {
        "eligible_graded_roles": signals.eligible_graded_roles,
        "forbidden_resources_used": cast(JsonValue, used_resources),
        "invalid_programs": signals.invalid_programs,
        "passes": not reasons,
        "probe_cap_available": signals.probe_cap_available,
        "reasons": cast(JsonValue, reasons),
        "timeout_programs": signals.timeout_programs,
        "worker_memory_ok": signals.worker_memory_ok,
    }


def _structural_gate(
    result: PipelineAuditResult,
    *,
    require_linux_memory: bool,
) -> dict[str, JsonValue]:
    reasons: list[str] = []
    programs = result.program_rows
    selected = tuple(row for row in programs if row["selected"] is True)
    if len(programs) != 4 or any(row["eligible"] is not True for row in programs):
        reasons.append("exactly four safe valid compiler programs were not supplied")
    behavior_signatures = {
        json.dumps(row["behavior_signature"], sort_keys=True, default=str)
        for row in selected
    }
    if len(selected) != 4 or len(behavior_signatures) != 4:
        reasons.append("four behaviorally distinct programs did not survive")
    varying_roles = 0
    for index in range(1, min(4, len(result.snapshot.hypothesis_ids))):
        costs = [float(result.snapshot.costs[action][index]) for action in result.actions]
        if max(costs) - min(costs) > 1e-12:
            varying_roles += 1
    if varying_roles < 2:
        reasons.append("fewer than two graded roles have action-varying depth-four costs")
    if result.snapshot.invalid_hypothesis_ids:
        reasons.append("one or more selected programs became invalid during planning")
    if not 2 <= len(result.actions) <= 12:
        reasons.append("candidate count does not provide two bounded exploitation candidates")
    if len(result.snapshot.weights) != 4:
        reasons.append("shared filtered snapshot does not contain exactly four weights")
    grounding_memory = [
        cast(Mapping[str, Any], row["grounding_worker_memory"])
        for row in programs
    ]
    persistent_memory = list(result.persistent_worker_rows)
    if len(grounding_memory) != 4 or len(persistent_memory) != 4:
        reasons.append("worker telemetry does not cover four transient and persistent workers")
    if require_linux_memory:
        if sys.platform != "linux":
            reasons.append("canonical worker-memory evidence requires Linux")
        if any(
            not _worker_memory_valid(row)
            for row in (*grounding_memory, *persistent_memory)
        ):
            reasons.append("one or more workers lack exact +256 MiB RLIMIT_DATA headroom")
    memory_ok = (
        not require_linux_memory
        or (
            sys.platform == "linux"
            and all(
                _worker_memory_valid(row)
                for row in (*grounding_memory, *persistent_memory)
            )
        )
    )
    shared_gate = _admission_resource_gate(
        AdmissionResourceSignals(
            invalid_programs=len(result.snapshot.invalid_hypothesis_ids),
            eligible_graded_roles=varying_roles,
            worker_memory_ok=memory_ok,
        )
    )
    reasons.extend(cast(list[str], shared_gate["reasons"]))
    return {
        "admission_resource_gate": shared_gate,
        "graded_action_varying_roles": varying_roles,
        "passes": not reasons,
        "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
        "require_linux_memory": require_linux_memory,
        "selected_distinct_programs": len(behavior_signatures),
        "selected_programs": len(selected),
    }


def _mechanism_gate(
    selection: ActionQBCSelection,
    *,
    probe_cap_available: bool = True,
    selected_evsi_minimum_margin: float = 1e-9,
) -> dict[str, JsonValue]:
    reasons: list[str] = []
    rows = selection.rows
    eligible = tuple(row for row in rows if row.eligible)
    concentration_margin = min(abs(row.outcome_concentration - 0.8) for row in rows)
    if concentration_margin < 1e-9:
        reasons.append("one or more outcome concentrations lack the registered margin")
    selected_x = next((row for row in rows if row.x_selected), None)
    if selected_x is None or selection.x_decision.mode != "probe":
        reasons.append("X did not select one disagreement-eligible probe")
        selected_evsi_margin = None
        selected_x_utility = None
    else:
        selected_evsi_margin = selected_x.evsi - 0.05
        selected_x_utility = selected_x.x_utility
        if (
            selected_evsi_margin < selected_evsi_minimum_margin
            or selected_x.x_utility < 1e-9
        ):
            reasons.append("X selected probe lacks material EVSI or positive-utility margin")
    if selection.m_decision.mode != "exploit":
        reasons.append("M did not exploit")
    action_contrast = selection.x_decision.action != selection.m_decision.action
    if not action_contrast:
        reasons.append("M and X selected the same environment action")
    if not probe_cap_available:
        reasons.append("shared probe cap is unavailable")
    if any(row.m_utility > -1e-9 for row in eligible):
        reasons.append("an eligible candidate lacks the nonpositive M-utility margin")
    x_ranked = sorted(
        eligible,
        key=lambda row: (-row.x_utility, _result_index(rows, row.action)),
    )
    if len(x_ranked) < 2:
        reasons.append("fewer than two disagreement-eligible X candidates")
        x_gap = None
    else:
        x_gap = x_ranked[0].x_utility - x_ranked[1].x_utility
        if x_gap < 1e-9:
            reasons.append("eligible X-utility winner lacks a unique runner-up margin")
    exploit_ranked = sorted(
        rows,
        key=lambda row: (row.exploit_score, _result_index(rows, row.action)),
    )
    if len(exploit_ranked) < 2:
        reasons.append("fewer than two M exploitation candidates")
        exploit_gap = None
    else:
        exploit_gap = exploit_ranked[1].exploit_score - exploit_ranked[0].exploit_score
        if exploit_gap < 1e-9:
            reasons.append("M robust-exploitation winner lacks a unique runner-up margin")
    return {
        "eligible_candidate_count": len(eligible),
        "environment_action_contrast": action_contrast,
        "exploit_gap": exploit_gap,
        "minimum_concentration_margin": concentration_margin,
        "passes": not reasons,
        "probe_cap_available": probe_cap_available,
        "reasons": cast(JsonValue, reasons),
        "selected_x_evsi_margin": selected_evsi_margin,
        "selected_x_evsi_minimum_margin": selected_evsi_minimum_margin,
        "selected_x_utility": selected_x_utility,
        "x_utility_gap": x_gap,
    }


def _result_index(rows: Sequence[Any], action: Action) -> int:
    """Return stable candidate position without relying on Action ordering."""

    return next(index for index, row in enumerate(rows) if row.action == action)


V4_AGREEMENT_SOURCE_SHA256: Final = (
    "5e659e6ad3a3f6e50dd4bfe709b901e29999b031ac5565c5469f0d66a216aa8a"
)


def _v4_counterfactual(
    result: PipelineAuditResult,
    *,
    structural_passes: bool,
    probe_cap_available: bool,
    counters: AuditCounterState,
) -> dict[str, JsonValue]:
    counters.increment("v4_counterfactual_calls")
    if _sha256(inspect.getsource(committee_agreement).encode("utf-8")) != (
        V4_AGREEMENT_SOURCE_SHA256
    ):
        raise RuntimeError("historical v4 agreement function source identity drifted")
    return _v4_counterfactual_from_evidence(
        result.snapshot,
        result.selection,
        structural_passes=structural_passes,
        probe_cap_available=probe_cap_available,
    )


def _v4_counterfactual_from_evidence(
    snapshot: PlanningSnapshot,
    selection: ActionQBCSelection,
    *,
    structural_passes: bool,
    probe_cap_available: bool,
) -> dict[str, JsonValue]:
    """Pure v4 contrast derivation shared by execution and payload validation."""

    agreement = committee_agreement(
        snapshot.actions,
        snapshot.costs,
        snapshot.weights,
    )
    rows = selection.rows
    selected = max(
        enumerate(rows),
        key=lambda indexed: (indexed[1].x_utility, -indexed[0]),
    )[1]
    no_positive_m = all(row.m_utility <= 0.0 for row in rows)
    actual_x_action = selection.x_decision.action
    same_selected_probe = (
        selection.x_decision.mode == "probe" and selected.action == actual_x_action
    )
    action_contrast = actual_x_action != selection.m_decision.action
    predicate_only_block = (
        structural_passes
        and probe_cap_available
        and agreement >= 0.8
        and selected.eligible
        and same_selected_probe
        and action_contrast
        and selected.evsi - 0.05 >= 1e-9
        and selected.x_utility >= 1e-9
        and no_positive_m
    )
    return {
        "agreement": agreement,
        "agreement_predicate_blocks": agreement >= 0.8,
        "causal_exercise": predicate_only_block,
        "environment_action_contrast": action_contrast,
        "no_positive_m_action": no_positive_m,
        "probe_cap_available": probe_cap_available,
        "same_as_v5_selected_probe": same_selected_probe,
        "selected_action_qbc_eligible": selected.eligible,
        "structural_passes": structural_passes,
        "selected_action": _action_json(selected.action),
        "selected_evsi": selected.evsi,
        "selected_x_utility": selected.x_utility,
        "source_sha256": V4_AGREEMENT_SOURCE_SHA256,
    }


def reverse_candidate_order(snapshot: PlanningSnapshot) -> PlanningSnapshot:
    """Reverse only candidate serialization order, retaining action-bound rows."""

    actions = tuple(reversed(snapshot.actions))
    return PlanningSnapshot(
        actions=actions,
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions={action: snapshot.predictions[action] for action in actions},
        costs={action: snapshot.costs[action] for action in actions},
        invalid_hypothesis_ids=snapshot.invalid_hypothesis_ids,
    )


def _map_action(action: Action, action_map: Mapping[str, Any]) -> Action:
    if action.kind is not ActionKind.ACTION6:
        simple = action_map.get("simple_forward")
        if not isinstance(simple, list):
            raise ValueError("visual transform lacks a simple-action map")
        simple_mapping = {str(source): str(destination) for source, destination in simple}
        destination = simple_mapping.get(action.kind.name)
        if destination is None:
            raise ValueError(f"visual transform does not map {action.kind.name}")
        return Action(ActionKind.coerce(destination))
    raw = action_map.get("action6_forward")
    if not isinstance(raw, list):
        raise ValueError("visual transform lacks an ACTION6 map")
    coordinate_mapping: dict[tuple[int, int], tuple[int, int]] = {
        (int(source[0]), int(source[1])): (int(destination[0]), int(destination[1]))
        for source, destination in raw
    }
    assert action.row is not None and action.col is not None
    if (action.row, action.col) not in coordinate_mapping:
        raise ValueError("base ACTION6 candidate lies outside transform action map")
    row, col = coordinate_mapping[(action.row, action.col)]
    return Action(ActionKind.ACTION6, row, col)


def _transform_prediction(
    prediction: Prediction,
    transform: Mapping[str, Any],
    *,
    background: int,
) -> Prediction:
    name = transform.get("name")
    parameters = transform.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("visual transform parameters are missing")
    grid = prediction.next_grid
    if name == "palette_bijection":
        raw_palette = parameters.get("forward_palette")
        if not isinstance(raw_palette, list) or len(raw_palette) != 16:
            raise ValueError("palette transform is not a sixteen-label bijection")
        palette = np.asarray(raw_palette, dtype=np.int16)
        if np.any(grid < 0) or np.any(grid >= len(palette)):
            raise ValueError("prediction grid lies outside palette-transform domain")
        mapped = palette[grid]
    elif name in {
        "translation_row_plus_3_col_plus_5",
        "translation_row_minus_3_col_minus_5",
    }:
        row_delta = int(parameters["row_delta"])
        col_delta = int(parameters["col_delta"])
        mapped = np.full_like(grid, background)
        rows, cols = np.nonzero(grid != background)
        destinations = tuple(
            (int(row) + row_delta, int(col) + col_delta)
            for row, col in zip(rows, cols, strict=True)
        )
        if any(
            not 0 <= row < grid.shape[0] or not 0 <= col < grid.shape[1]
            for row, col in destinations
        ):
            raise ValueError("predicted object leaves the registered translation frame")
        for (source_row, source_col), (row, col) in zip(
            zip(rows, cols, strict=True), destinations, strict=True
        ):
            mapped[row, col] = grid[source_row, source_col]
    elif name == "scale_2_nearest_neighbor":
        if parameters.get("factor") != 2:
            raise ValueError("scale diagnostic factor differs from two")
        mapped = np.repeat(np.repeat(grid, 2, axis=0), 2, axis=1)
    else:
        raise ValueError(f"unknown registered visual transform: {name!r}")
    return Prediction(mapped, prediction.game_state, prediction.level_delta, {})


def _selection_by_action(selection: ActionQBCSelection) -> dict[Action, Any]:
    return {row.action: row for row in selection.rows}


def _exploit_minimizers(selection: ActionQBCSelection) -> tuple[Action, ...]:
    minimum = min(row.exploit_score for row in selection.rows)
    return tuple(
        row.action
        for row in selection.rows
        if isclose(row.exploit_score, minimum, rel_tol=1e-12, abs_tol=1e-12)
    )


def _mapped_action_set(
    actions: Sequence[Action],
    action_map: Mapping[str, Any],
) -> set[Action]:
    return {_map_action(action, action_map) for action in actions}


def _compare_visual_transform(
    base: PipelineAuditResult,
    transformed: PipelineAuditResult,
    transform: Mapping[str, Any],
) -> dict[str, JsonValue]:
    action_map = transform.get("action_map")
    if not isinstance(action_map, Mapping):
        raise ValueError("visual transform action map is missing")
    mapped_actions = tuple(_map_action(action, action_map) for action in base.actions)
    reasons: list[str] = []
    if mapped_actions != transformed.actions:
        reasons.append("mapped base actions differ from transformed action order/frontier")
    if base.source_roles != transformed.source_roles:
        reasons.append("compiler roles differ under visual transform")
    if any(
        not isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(
            base.snapshot.weights,
            transformed.snapshot.weights,
            strict=True,
        )
    ):
        reasons.append("Gibbs weights differ under visual transform")
    background = int(transform["background_label"])
    for base_action, mapped_action in zip(base.actions, mapped_actions, strict=True):
        if mapped_action not in transformed.snapshot.costs:
            continue
        for index in range(len(base.snapshot.hypothesis_ids)):
            left_cost = float(base.snapshot.costs[base_action][index])
            right_cost = float(transformed.snapshot.costs[mapped_action][index])
            if not isclose(left_cost, right_cost, rel_tol=1e-12, abs_tol=1e-12):
                reasons.append("rolewise costs differ under visual transform")
                break
            base_prediction = base.snapshot.predictions[base_action][index]
            transformed_prediction = transformed.snapshot.predictions[mapped_action][index]
            if base_prediction is None or transformed_prediction is None:
                reasons.append("visual comparison encountered an invalid root prediction")
                break
            expected_prediction = _transform_prediction(
                base_prediction,
                transform,
                background=background,
            )
            if expected_prediction.signature() != transformed_prediction.signature():
                reasons.append("mapped prediction differs under visual transform")
                break
    base_rows = _selection_by_action(base.selection)
    transformed_rows = _selection_by_action(transformed.selection)
    numeric_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    exact_fields = (
        "outcome_cell_count",
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
    )
    for base_action, mapped_action in zip(base.actions, mapped_actions, strict=True):
        if mapped_action not in transformed_rows:
            continue
        left = base_rows[base_action]
        right = transformed_rows[mapped_action]
        if any(
            not isclose(
                float(getattr(left, field_name)),
                float(getattr(right, field_name)),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for field_name in numeric_fields
        ):
            reasons.append("selector numeric diagnostics differ under visual transform")
        if any(
            getattr(left, field_name) != getattr(right, field_name)
            for field_name in exact_fields
        ):
            reasons.append("selector disposition/ranks differ under visual transform")
    for left, right in (
        (base.selection.m_decision, transformed.selection.m_decision),
        (base.selection.x_decision, transformed.selection.x_decision),
    ):
        if (
            _map_action(left.action, action_map) != right.action
            or (
                None
                if left.probe_candidate is None
                else _map_action(left.probe_candidate, action_map)
            )
            != right.probe_candidate
            or left.mode != right.mode
            or left.gate_reason != right.gate_reason
            or not isclose(left.score, right.score, rel_tol=1e-12, abs_tol=1e-12)
        ):
            reasons.append("mapped M/X decision differs under visual transform")
    action_sets = (
        (
            "robust exploitation",
            _exploit_minimizers(base.selection),
            _exploit_minimizers(transformed.selection),
        ),
        (
            "M utility maximizer",
            base.selection.m_utility_maximizers,
            transformed.selection.m_utility_maximizers,
        ),
        (
            "X utility maximizer",
            base.selection.x_utility_maximizers,
            transformed.selection.x_utility_maximizers,
        ),
    )
    for label, left_actions, right_actions in action_sets:
        if _mapped_action_set(left_actions, action_map) != set(right_actions):
            reasons.append(f"mapped {label} action set differs under visual transform")
    if (
        _map_action(base.selection.exploit.action, action_map)
        != transformed.selection.exploit.action
        or not isclose(
            base.selection.exploit.mean_cost,
            transformed.selection.exploit.mean_cost,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.standard_deviation,
            transformed.selection.exploit.standard_deviation,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.score,
            transformed.selection.exploit.score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    ):
        reasons.append("mapped robust-exploitation result differs under visual transform")
    return {
        "base_selection": _selection_json(base.selection),
        "frontier_mode": cast(str, transform.get("frontier_mode")),
        "mapped_actions": [_action_json(action) for action in mapped_actions],
        "mapped_action_count": len(mapped_actions),
        "passes": not reasons,
        "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
        "transform": cast(str, transform.get("name")),
        "transformed_selection": _selection_json(transformed.selection),
    }


def _permute_hypotheses(
    snapshot: PlanningSnapshot,
    permutation: Sequence[int],
) -> PlanningSnapshot:
    if sorted(permutation) != list(range(len(snapshot.hypothesis_ids))):
        raise ValueError("hypothesis transform is not a complete permutation")
    return PlanningSnapshot(
        actions=snapshot.actions,
        hypothesis_ids=tuple(snapshot.hypothesis_ids[index] for index in permutation),
        weights=tuple(snapshot.weights[index] for index in permutation),
        predictions={
            action: tuple(snapshot.predictions[action][index] for index in permutation)
            for action in snapshot.actions
        },
        costs={
            action: tuple(snapshot.costs[action][index] for index in permutation)
            for action in snapshot.actions
        },
        invalid_hypothesis_ids=snapshot.invalid_hypothesis_ids,
    )


def _candidate_permutation(
    snapshot: PlanningSnapshot,
    permutation: Sequence[int],
) -> PlanningSnapshot:
    if sorted(permutation) != list(range(len(snapshot.actions))):
        raise ValueError("candidate transform is not a complete permutation")
    actions = tuple(snapshot.actions[index] for index in permutation)
    return PlanningSnapshot(
        actions=actions,
        hypothesis_ids=snapshot.hypothesis_ids,
        weights=snapshot.weights,
        predictions={action: snapshot.predictions[action] for action in actions},
        costs={action: snapshot.costs[action] for action in actions},
        invalid_hypothesis_ids=snapshot.invalid_hypothesis_ids,
    )


def _selection_invariant_by_action(
    base: ActionQBCSelection,
    transformed: ActionQBCSelection,
    *,
    require_order_relative_fields: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    left_rows = _selection_by_action(base)
    right_rows = _selection_by_action(transformed)
    if set(left_rows) != set(right_rows):
        return ("order transform changed candidate identity set",)
    for action in left_rows:
        left = left_rows[action]
        right = right_rows[action]
        for field_name in (
            "outcome_concentration",
            "evsi",
            "catastrophe_mass",
            "m_utility",
            "x_utility",
            "exploit_mean_cost",
            "exploit_standard_deviation",
            "exploit_score",
        ):
            if not isclose(
                float(getattr(left, field_name)),
                float(getattr(right, field_name)),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                reasons.append(f"order transform changed {field_name}")
        if left.eligible != right.eligible:
            reasons.append("order transform changed eligibility")
        if left.outcome_cell_count != right.outcome_cell_count:
            reasons.append("order transform changed outcome-cell count")
        if require_order_relative_fields and (
            left.m_selected,
            left.x_selected,
            left.m_rank,
            left.x_rank,
        ) != (
            right.m_selected,
            right.x_selected,
            right.m_rank,
            right.x_rank,
        ):
            reasons.append("order transform changed selection disposition or utility ranks")
    if set(base.m_utility_maximizers) != set(transformed.m_utility_maximizers):
        reasons.append("order transform changed M utility maximizer set")
    if set(base.x_utility_maximizers) != set(transformed.x_utility_maximizers):
        reasons.append("order transform changed X utility maximizer set")
    if base.m_decision.mode != transformed.m_decision.mode:
        reasons.append("order transform changed M probe/exploit mode")
    if base.x_decision.mode != transformed.x_decision.mode:
        reasons.append("order transform changed X probe/exploit mode")
    for label, left, right in (
        ("M", base.m_decision, transformed.m_decision),
        ("X", base.x_decision, transformed.x_decision),
    ):
        if left.gate_reason != right.gate_reason or not isclose(
            left.score,
            right.score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            reasons.append(f"order transform changed {label} gate reason or score")
        if require_order_relative_fields and (
            left.action != right.action or left.probe_candidate != right.probe_candidate
        ):
            reasons.append(f"order transform changed {label} selected/probe action")
    return tuple(dict.fromkeys(reasons))


def _outcome_cell_payload(
    snapshot: PlanningSnapshot,
    source_roles: Sequence[str],
) -> list[dict[str, JsonValue]]:
    if len(source_roles) != len(snapshot.hypothesis_ids):
        raise ValueError("outcome serialization role count differs from committee size")
    payload: list[dict[str, JsonValue]] = []
    for action in snapshot.actions:
        predictions = snapshot.predictions[action]
        if any(prediction is None for prediction in predictions):
            raise ValueError("outcome serialization requires a filtered valid snapshot")
        cells = partition_exact_outcomes(
            tuple(prediction for prediction in predictions if prediction is not None),
            snapshot.weights,
        )
        payload.append(
            {
                "action": _action_json(action),
                "cells": [
                    {
                        "hypothesis_indices": list(cell.hypothesis_indices),
                        "hypothesis_roles": [
                            source_roles[index] for index in cell.hypothesis_indices
                        ],
                        "mass": cell.mass,
                        "signature_sha256": canonical_sha256(
                            _prediction_json(
                                cast(Prediction, predictions[cell.hypothesis_indices[0]])
                            )
                        ),
                    }
                    for cell in cells
                ],
            }
        )
    return payload


ORDER_TRANSFORM_NAMES: Final = (
    "candidate_list_reversal",
    "candidate_list_left_rotation_by_one",
    "hypothesis_list_reversal",
    "hypothesis_list_left_rotation_by_one",
    "serialized_outcome_cell_order_reversal",
)
_OUTCOME_CELL_TRANSFORM_LOCK: Final = Lock()


def _registered_order_permutation(
    transform: Mapping[str, Any],
    *,
    expected_name: str,
    expected_target: str,
    length: int,
) -> tuple[int, ...]:
    if transform.get("name") != expected_name or transform.get("target_sequence") != (
        expected_target
    ):
        raise ValueError("registered order transform name/target drifted")
    table = transform.get("maps_by_length")
    if not isinstance(table, list):
        raise ValueError("registered order transform lacks its length table")
    matches = [row for row in table if isinstance(row, Mapping) and row.get("length") == length]
    if len(matches) != 1:
        raise ValueError("registered order transform has no unique applicable length row")
    raw = matches[0].get("forward_output_to_input")
    inverse = matches[0].get("inverse_output_to_input")
    if not isinstance(raw, list) or not isinstance(inverse, list):
        raise ValueError("registered order transform map is malformed")
    permutation = tuple(int(index) for index in raw)
    inverse_permutation = tuple(int(index) for index in inverse)
    if sorted(permutation) != list(range(length)) or sorted(inverse_permutation) != list(
        range(length)
    ):
        raise ValueError("registered order transform map is not a complete permutation")
    restored = tuple(permutation[inverse_permutation[index]] for index in range(length))
    if restored != tuple(range(length)):
        raise ValueError("registered order transform forward/inverse maps disagree")
    return permutation


def evaluate_order_transforms(
    base: PipelineAuditResult,
    *,
    counters: AuditCounterState,
    order_transform_maps: Sequence[Mapping[str, Any]],
    base_positive: bool,
    continue_after_failure: bool = False,
    deadline: float | None = None,
) -> tuple[dict[str, JsonValue], ...]:
    if tuple(item.get("name") for item in order_transform_maps) != ORDER_TRANSFORM_NAMES:
        raise ValueError("registered order transform set/order drifted")
    action_count = len(base.snapshot.actions)
    hypothesis_count = len(base.snapshot.hypothesis_ids)
    candidate_permutations = (
        (
            ORDER_TRANSFORM_NAMES[0],
            _registered_order_permutation(
                order_transform_maps[0],
                expected_name=ORDER_TRANSFORM_NAMES[0],
                expected_target="candidate_sequence",
                length=action_count,
            ),
        ),
        (
            ORDER_TRANSFORM_NAMES[1],
            _registered_order_permutation(
                order_transform_maps[1],
                expected_name=ORDER_TRANSFORM_NAMES[1],
                expected_target="candidate_sequence",
                length=action_count,
            ),
        ),
    )
    hypothesis_permutations = (
        (
            ORDER_TRANSFORM_NAMES[2],
            _registered_order_permutation(
                order_transform_maps[2],
                expected_name=ORDER_TRANSFORM_NAMES[2],
                expected_target="hypothesis_sequence",
                length=hypothesis_count,
            ),
        ),
        (
            ORDER_TRANSFORM_NAMES[3],
            _registered_order_permutation(
                order_transform_maps[3],
                expected_name=ORDER_TRANSFORM_NAMES[3],
                expected_target="hypothesis_sequence",
                length=hypothesis_count,
            ),
        ),
    )
    records: list[dict[str, JsonValue]] = []
    for name, permutation in candidate_permutations:
        try:
            if deadline is not None:
                _require_before_deadline(deadline)
            snapshot = _candidate_permutation(base.snapshot, permutation)
            counters.increment("pure_selector_calls")
            counters.increment("pure_selector_scene_order_calls")
            selection = ACTION_QBC_AUDIT_SELECTOR(
                snapshot,
                cross_level_multiplier=23.0,
                probes_used=0,
                probe_cap=3,
            )
            reasons = list(
                _selection_invariant_by_action(
                    base.selection,
                    selection,
                    require_order_relative_fields=base_positive,
                )
            )
            if base_positive and (
                selection.m_decision.action != base.selection.m_decision.action
                or selection.x_decision.action != base.selection.x_decision.action
            ):
                reasons.append(
                    "unique positive-row decision changed under candidate order"
                )
            records.append(
                {
                    "kind": "order_transform",
                    "name": name,
                    "passes": not reasons,
                    "permutation": list(permutation),
                    "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
                    "selection": _selection_json(selection),
                }
            )
        except Exception as error:
            if not continue_after_failure or not counters.scientific_exposure_started:
                raise
            records.append(
                {
                    "failure": {
                        "error_type": type(error).__name__,
                        "stage": "order_transform_failed",
                    },
                    "kind": "order_transform",
                    "name": name,
                    "passes": False,
                    "permutation": list(permutation),
                    "reasons": ["order_transform_failed"],
                }
            )
    for name, permutation in hypothesis_permutations:
        try:
            if deadline is not None:
                _require_before_deadline(deadline)
            snapshot = _permute_hypotheses(base.snapshot, permutation)
            counters.increment("pure_selector_calls")
            counters.increment("pure_selector_scene_order_calls")
            selection = ACTION_QBC_AUDIT_SELECTOR(
                snapshot,
                cross_level_multiplier=23.0,
                probes_used=0,
                probe_cap=3,
            )
            reasons = list(
                _selection_invariant_by_action(
                    base.selection,
                    selection,
                    require_order_relative_fields=True,
                )
            )
            if (
                selection.m_decision.action != base.selection.m_decision.action
                or selection.x_decision.action != base.selection.x_decision.action
            ):
                reasons.append("mapped decision changed under hypothesis permutation")
            records.append(
                {
                    "kind": "order_transform",
                    "name": name,
                    "passes": not reasons,
                    "permutation": list(permutation),
                    "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
                    "selection": _selection_json(selection),
                }
            )
        except Exception as error:
            if not continue_after_failure or not counters.scientific_exposure_started:
                raise
            records.append(
                {
                    "failure": {
                        "error_type": type(error).__name__,
                        "stage": "order_transform_failed",
                    },
                    "kind": "order_transform",
                    "name": name,
                    "passes": False,
                    "permutation": list(permutation),
                    "reasons": ["order_transform_failed"],
                }
            )
    try:
        if deadline is not None:
            _require_before_deadline(deadline)
        counters.increment("pure_selector_calls")
        counters.increment("pure_selector_scene_order_calls")
        original_partitioner = (
            _action_qbc_policy_module._partition_normalized_outcomes
        )

        def registered_cell_reversal(
            predictions: Sequence[Prediction],
            normalized_weights: Sequence[float],
        ) -> tuple[OutcomeCell, ...]:
            forward = original_partitioner(predictions, normalized_weights)
            permutation = _registered_order_permutation(
                order_transform_maps[4],
                expected_name=ORDER_TRANSFORM_NAMES[4],
                expected_target="serialized_outcome_cell_sequence",
                length=len(forward),
            )
            return tuple(forward[index] for index in permutation)

        with _OUTCOME_CELL_TRANSFORM_LOCK:
            _action_qbc_policy_module._partition_normalized_outcomes = (
                registered_cell_reversal
            )
            try:
                unchanged = ACTION_QBC_AUDIT_SELECTOR(
                    base.snapshot,
                    cross_level_multiplier=23.0,
                    probes_used=0,
                    probe_cap=3,
                )
            finally:
                _action_qbc_policy_module._partition_normalized_outcomes = (
                    original_partitioner
                )
        cells = _outcome_cell_payload(base.snapshot, base.source_roles)
        reversed_cells: list[JsonValue] = []
        for row in cells:
            row_cells = cast(list[JsonValue], row["cells"])
            permutation = _registered_order_permutation(
                order_transform_maps[4],
                expected_name=ORDER_TRANSFORM_NAMES[4],
                expected_target="serialized_outcome_cell_sequence",
                length=len(row_cells),
            )
            reversed_cells.append(
                {**row, "cells": [row_cells[index] for index in permutation]}
            )
        cell_reasons = list(
            _selection_invariant_by_action(
                base.selection,
                unchanged,
                require_order_relative_fields=True,
            )
        )
        if (
            unchanged.m_decision.action != base.selection.m_decision.action
            or unchanged.x_decision.action != base.selection.x_decision.action
        ):
            cell_reasons.append("decision changed under serialized outcome-cell reversal")
        records.append(
            {
                "forward_cells_sha256": canonical_sha256(cast(JsonValue, cells)),
                "kind": "order_transform",
                "name": ORDER_TRANSFORM_NAMES[4],
                "passes": not cell_reasons,
                "policy_input_transform_applied": True,
                "reasons": cast(JsonValue, list(dict.fromkeys(cell_reasons))),
                "reversed_cells_sha256": canonical_sha256(
                    cast(JsonValue, reversed_cells)
                ),
                "selection": _selection_json(unchanged),
                "transformed_cells": reversed_cells,
            }
        )
    except Exception as error:
        if not continue_after_failure or not counters.scientific_exposure_started:
            raise
        records.append(
            {
                "failure": {
                    "error_type": type(error).__name__,
                    "stage": "order_transform_failed",
                },
                "kind": "order_transform",
                "name": ORDER_TRANSFORM_NAMES[4],
                "passes": False,
                "reasons": ["order_transform_failed"],
            }
        )
    return tuple(records)


PREREGISTERED_CONTROL_ORDER: Final = (
    "identical_signatures_A1",
    "dominant_mass_Aeq0_8_positive_JX",
    "A_lt_0_8_evsi0",
    "fragmented_cosmetic_evsi0",
    "evsi_0_049",
    "material_positive_JX_A_ge_0_8",
    "inverse_low_global_agreement_A_ge_0_8",
    "unused_rowwise_x_only_X_selects_other_probe",
    "M_positive_eligible_different_from_X",
    "exhausted_probe_cap",
    "catastrophe_makes_JX_nonpositive",
    "final_multiplier_1_M_equals_X",
    "invalid_program_structural_false",
    "timeout_program_structural_false",
    "fewer_than_two_eligible_graded_roles",
    "worker_memory_drift",
    "forbidden_resource_use",
    "boundary_evsi_eq_0_05",
    "cosmetic_refinement_pair",
    "candidate_tie_pair",
)

PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER: Final[Mapping[str, int]] = (
    MappingProxyType(
        {
            **{name: 1 for name in PREREGISTERED_CONTROL_ORDER[:14]},
            PREREGISTERED_CONTROL_ORDER[14]: 0,
            PREREGISTERED_CONTROL_ORDER[15]: 0,
            PREREGISTERED_CONTROL_ORDER[16]: 0,
            PREREGISTERED_CONTROL_ORDER[17]: 1,
            PREREGISTERED_CONTROL_ORDER[18]: 2,
            PREREGISTERED_CONTROL_ORDER[19]: 2,
        }
    )
)
PREREGISTERED_CONTROL_SELECTOR_CALLS: Final = sum(
    PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER.values()
)


def _control_prediction(
    label: int,
    *,
    game_state: GameState = GameState.NOT_FINISHED,
) -> Prediction:
    return Prediction(np.asarray([[label]], dtype=np.int16), game_state, 0, {})


def _control_snapshot(
    actions: Sequence[Action],
    weights: Sequence[float],
    predictions: Mapping[Action, Sequence[Prediction]],
    costs: Mapping[Action, Sequence[float]],
) -> PlanningSnapshot:
    return PlanningSnapshot(
        actions=tuple(actions),
        hypothesis_ids=tuple(f"control-h{index}" for index in range(len(weights))),
        weights=tuple(weights),
        predictions={action: tuple(predictions[action]) for action in actions},
        costs={action: tuple(float(value) for value in costs[action]) for action in actions},
    )


def _two_hypothesis_control(
    *,
    weights: tuple[float, float] = (0.5, 0.5),
    cross_cost: float = 2.0,
    probe_cost: float = 4.0,
    catastrophe: bool = False,
) -> PlanningSnapshot:
    actions = (
        Action(ActionKind.ACTION1),
        Action(ActionKind.ACTION2),
        Action(ActionKind.ACTION3),
    )
    first = _control_prediction(1)
    second = _control_prediction(
        2,
        game_state=GameState.GAME_OVER if catastrophe else GameState.NOT_FINISHED,
    )
    return _control_snapshot(
        actions,
        weights,
        {
            actions[0]: (first, first),
            actions[1]: (second, second),
            actions[2]: (first, second),
        },
        {
            actions[0]: (0.0, cross_cost),
            actions[1]: (cross_cost, 0.0),
            actions[2]: (probe_cost, probe_cost),
        },
    )


def _select_control(
    snapshot: PlanningSnapshot,
    counters: AuditCounterState,
    *,
    multiplier: float = 23.0,
    probes_used: int = 0,
) -> ActionQBCSelection:
    counters.increment("pure_selector_calls")
    counters.increment("pure_selector_control_calls")
    return ACTION_QBC_AUDIT_SELECTOR(
        snapshot,
        cross_level_multiplier=multiplier,
        probes_used=probes_used,
        probe_cap=3,
    )


def _control_record(
    name: str,
    *,
    passes: bool,
    expected: str,
    observed: JsonValue,
) -> dict[str, JsonValue]:
    return {
        "expected_gate_semantics": expected,
        "name": name,
        "observed": observed,
        "passes": passes,
    }


def _evaluate_preregistered_controls_monolithic(
    counters: AuditCounterState,
) -> tuple[dict[str, JsonValue], ...]:
    """Evaluate the exact twenty control records using nineteen selector calls."""

    calls_before = counters.snapshot()["pure_selector_control_calls"]
    total_calls_before = counters.snapshot()["pure_selector_calls"]
    records: list[dict[str, JsonValue]] = []
    a1 = Action(ActionKind.ACTION1)
    a2 = Action(ActionKind.ACTION2)
    a3 = Action(ActionKind.ACTION3)
    a4 = Action(ActionKind.ACTION4)

    identical = _two_hypothesis_control(cross_cost=0.0)
    selection = _select_control(identical, counters)
    row = _selection_by_action(selection)[a1]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[0],
            passes=row.outcome_concentration == 1.0 and not row.eligible,
            expected="A=1 is strictly ineligible and cannot establish the contrast",
            observed=_selection_json(selection),
        )
    )

    threshold = _two_hypothesis_control(
        weights=(0.8, 0.2), cross_cost=10.0, probe_cost=20.0
    )
    selection = _select_control(threshold, counters)
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[1],
            passes=(
                isclose(row.outcome_concentration, 0.8, abs_tol=1e-12)
                and row.x_utility > 0.0
                and not row.eligible
                and selection.x_decision.mode == "exploit"
            ),
            expected="strict equality at A=0.8 blocks despite positive J_X",
            observed=_selection_json(selection),
        )
    )

    first = _control_prediction(1)
    second = _control_prediction(2)
    zero_evsi = _control_snapshot(
        (a1, a2, a3),
        (0.5, 0.5),
        {a1: (first, first), a2: (second, second), a3: (first, second)},
        {a1: (0.0, 0.0), a2: (1.0, 1.0), a3: (2.0, 2.0)},
    )
    selection = _select_control(zero_evsi, counters)
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[2],
            passes=row.eligible and row.evsi == 0.0 and selection.x_decision.mode == "exploit",
            expected="A<0.8 without decision information blocks",
            observed=_selection_json(selection),
        )
    )

    weights4 = (0.4, 0.3, 0.2, 0.1)
    labels = tuple(_control_prediction(index + 1) for index in range(4))
    fragmented = _control_snapshot(
        (a1, a2, a3),
        weights4,
        {
            a1: (labels[0],) * 4,
            a2: (labels[1],) * 4,
            a3: labels,
        },
        {a1: (0.0,) * 4, a2: (1.0,) * 4, a3: (2.0,) * 4},
    )
    selection = _select_control(fragmented, counters)
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[3],
            passes=row.outcome_cell_count == 4 and row.evsi == 0.0,
            expected="fragmented cosmetic outcomes do not create EVSI",
            observed=_selection_json(selection),
        )
    )

    below_material = _two_hypothesis_control(cross_cost=0.098, probe_cost=1.0)
    selection = _select_control(below_material, counters)
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[4],
            passes=(
                isclose(row.evsi, 0.049, abs_tol=1e-12)
                and selection.x_decision.mode == "probe"
                and row.evsi < 0.05
            ),
            expected="live X may probe, but admission blocks solely on EVSI<0.05",
            observed=_selection_json(selection),
        )
    )

    high_a = _two_hypothesis_control(
        weights=(0.9, 0.1), cross_cost=20.0, probe_cost=30.0
    )
    selection = _select_control(high_a, counters)
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[5],
            passes=row.x_utility > 0.0 and row.outcome_concentration >= 0.8 and not row.eligible,
            expected="material positive J_X remains blocked by high A",
            observed=_selection_json(selection),
        )
    )

    a5 = Action(ActionKind.ACTION5)
    inverse_costs = {
        a1: (0.0, 10.0, 10.0, 10.0),
        a2: (10.0, 0.0, 10.0, 10.0),
        a3: (10.0, 10.0, 0.0, 10.0),
        a4: (10.0, 10.0, 10.0, 0.0),
        a5: (20.0, 20.0, 20.0, 20.0),
    }
    inverse = _control_snapshot(
        (a1, a2, a3, a4, a5),
        weights4,
        {
            a1: (labels[0],) * 4,
            a2: (labels[1],) * 4,
            a3: (labels[2],) * 4,
            a4: (labels[3],) * 4,
            a5: (labels[0], labels[0], labels[0], labels[3]),
        },
        inverse_costs,
    )
    selection = _select_control(inverse, counters)
    row = _selection_by_action(selection)[a5]
    global_agreement = committee_agreement(
        inverse.actions, inverse.costs, inverse.weights
    )
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[6],
            passes=(
                global_agreement < 0.8
                and row.outcome_concentration >= 0.8
                and row.x_utility > 0.0
                and not row.eligible
            ),
            expected="low global agreement cannot override action-specific high A",
            observed={
                "global_agreement": global_agreement,
                "selection": _selection_json(selection),
            },
        )
    )

    shared_and_x_only = _control_snapshot(
        (a1, a2, a3, a4),
        (0.5, 0.5),
        {
            a1: (first, first),
            a2: (second, second),
            a3: (first, second),
            a4: (
                first,
                _control_prediction(2, game_state=GameState.GAME_OVER),
            ),
        },
        {
            a1: (0.0, 4.0),
            a2: (4.0, 0.0),
            a3: (8.0, 8.0),
            a4: (8.0, 8.0),
        },
    )
    selection = _select_control(shared_and_x_only, counters)
    selected_shared = _selection_by_action(selection)[a3]
    unused = _selection_by_action(selection)[a4]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[7],
            passes=(
                unused.eligible
                and unused.x_utility > 0.0
                and unused.m_utility <= 0.0
                and not unused.x_selected
                and selection.x_decision.action == a3
                and selection.m_decision.action == a3
                and selected_shared.eligible
                and selected_shared.m_utility > 0.0
                and selected_shared.x_utility > 0.0
                and selected_shared.m_selected
                and selected_shared.x_selected
            ),
            expected=(
                "an eligible unused row-wise X-only action is not the selected shared "
                "positive M/X probe"
            ),
            observed=_selection_json(selection),
        )
    )

    a6 = Action(ActionKind.ACTION6, 0, 0)
    different = _control_snapshot(
        (a1, a2, a3, a4, a5, a6),
        weights4,
        {
            a1: (labels[0],) * 4,
            a2: (labels[1],) * 4,
            a3: (labels[2],) * 4,
            a4: (labels[3],) * 4,
            a5: (labels[0], labels[1], labels[2], labels[2]),
            a6: (
                labels[0],
                labels[1],
                _control_prediction(3, game_state=GameState.GAME_OVER),
                labels[3],
            ),
        },
        {
            a1: (0, 6, 3, 6),
            a2: (0, 8, 3, 7),
            a3: (7, 8, 3, 5),
            a4: (3, 3, 7, 4),
            a5: (0, 6, 8, 1),
            a6: (2, 4, 1, 5),
        },
    )
    selection = _select_control(different, counters)
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[8],
            passes=(
                selection.m_decision.mode == "probe"
                and selection.x_decision.mode == "probe"
                and selection.m_decision.action == a5
                and selection.x_decision.action == a6
            ),
            expected="any positive eligible M probe blocks the M-exploit/X-probe conjunction",
            observed=_selection_json(selection),
        )
    )

    selection = _select_control(_two_hypothesis_control(), counters, probes_used=3)
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[9],
            passes=(
                selection.m_decision.mode == selection.x_decision.mode == "exploit"
                and selection.x_decision.gate_reason == "level_probe_cap_reached"
            ),
            expected="exhausted shared probe cap blocks probing",
            observed=_selection_json(selection),
        )
    )

    selection = _select_control(
        _two_hypothesis_control(catastrophe=True), counters, multiplier=2.0
    )
    row = _selection_by_action(selection)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[10],
            passes=row.catastrophe_mass == 0.5 and row.x_utility <= 0.0,
            expected="catastrophe cost makes J_X nonpositive",
            observed=_selection_json(selection),
        )
    )

    selection = _select_control(
        _two_hypothesis_control(cross_cost=4.0, probe_cost=8.0),
        counters,
        multiplier=1.0,
    )
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[11],
            passes=selection.m_decision == selection.x_decision,
            expected="final-level multiplier one makes M and X identical",
            observed=_selection_json(selection),
        )
    )

    filtered = _two_hypothesis_control()
    for index, name in enumerate(PREREGISTERED_CONTROL_ORDER[12:14], start=12):
        selection = _select_control(filtered, counters)
        reason = "invalid_program" if index == 12 else "timeout_program"
        gate = _admission_resource_gate(
            AdmissionResourceSignals(
                invalid_programs=1 if index == 12 else 0,
                timeout_programs=1 if index == 13 else 0,
            )
        )
        records.append(
            _control_record(
                name,
                passes=(gate["passes"] is False and gate["reasons"] == [reason]),
                expected=(
                    "planner filters the failed program globally; the separately supplied "
                    "structural flag remains false"
                ),
                observed={
                    "failure_kind": "invalid" if index == 12 else "timeout",
                    "admission_resource_gate": gate,
                    "selector_on_filtered_snapshot": _selection_json(selection),
                },
            )
        )

    fewer_roles_gate = _admission_resource_gate(
        AdmissionResourceSignals(eligible_graded_roles=1)
    )
    memory_gate = _admission_resource_gate(
        AdmissionResourceSignals(worker_memory_ok=False)
    )
    forbidden_counts = {name: 0 for name in FORBIDDEN_AUDIT_RESOURCE_FIELDS}
    forbidden_counts["model_calls"] = 1
    resource_gate = _admission_resource_gate(
        AdmissionResourceSignals(forbidden_resource_counts=forbidden_counts)
    )
    records.extend(
        (
            _control_record(
                PREREGISTERED_CONTROL_ORDER[14],
                passes=(
                    fewer_roles_gate["passes"] is False
                    and fewer_roles_gate["reasons"]
                    == ["fewer_than_two_eligible_graded_roles"]
                ),
                expected="fewer than two eligible graded roles blocks structurally",
                observed=fewer_roles_gate,
            ),
            _control_record(
                PREREGISTERED_CONTROL_ORDER[15],
                passes=(
                    memory_gate["passes"] is False
                    and memory_gate["reasons"] == ["worker_memory_drift"]
                ),
                expected="any worker-memory drift blocks structurally",
                observed=memory_gate,
            ),
            _control_record(
                PREREGISTERED_CONTROL_ORDER[16],
                passes=(
                    resource_gate["passes"] is False
                    and resource_gate["reasons"] == ["forbidden_resource_use"]
                    and resource_gate["forbidden_resources_used"] == ["model_calls"]
                ),
                expected="hypothetical forbidden resource use blocks without using it",
                observed=resource_gate,
            ),
        )
    )

    boundary = _control_snapshot(
        (a1, a2, a3),
        (0.25, 0.25, 0.25, 0.25),
        {
            a1: (first, first, first, first),
            a2: (first, first, second, second),
            a3: (first, second, first, second),
        },
        {
            a1: (0.05, 0.05, 0.05, 0.05),
            a2: (0.0, 0.0, 0.1, 0.1),
            a3: (0.1, 0.1, 0.0, 0.0),
        },
    )
    selection = _select_control(boundary, counters)
    row = _selection_by_action(selection)[a2]
    boundary_gate = _admission_resource_gate(AdmissionResourceSignals())
    boundary_mechanism = _mechanism_gate(
        selection,
        selected_evsi_minimum_margin=0.0,
    )
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[17],
            passes=(
                isclose(row.evsi, 0.05, abs_tol=1e-12)
                and row.evsi >= 0.05
                and row.eligible
                and row.outcome_concentration < 0.8
                and row.x_utility > 0.0
                and row.m_utility <= 0.0
                and selection.m_decision.mode == "exploit"
                and selection.x_decision.mode == "probe"
                and selection.x_decision.action == a2
                and row.x_selected
                and boundary_gate["passes"] is True
                and boundary_mechanism["passes"] is True
            ),
            expected="EVSI equality at 0.05 satisfies admission materiality",
            observed={
                "admission_resource_gate": boundary_gate,
                "mechanism_gate": boundary_mechanism,
                "selection": _selection_json(selection),
            },
        )
    )

    refinement_base = _control_snapshot(
        (a1, a2, a3),
        weights4,
        {
            a1: (labels[0],) * 4,
            a2: (labels[1],) * 4,
            a3: (labels[0], labels[0], labels[1], labels[1]),
        },
        {a1: (0.0,) * 4, a2: (1.0,) * 4, a3: (2.0,) * 4},
    )
    refinement_split = _control_snapshot(
        (a1, a2, a3),
        weights4,
        {
            a1: (labels[0],) * 4,
            a2: (labels[1],) * 4,
            a3: labels,
        },
        refinement_base.costs,
    )
    before = _select_control(refinement_base, counters)
    after = _select_control(refinement_split, counters)
    before_row = _selection_by_action(before)[a3]
    after_row = _selection_by_action(after)[a3]
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[18],
            passes=(
                before_row.evsi == after_row.evsi == 0.0
                and before_row.outcome_concentration != after_row.outcome_concentration
                and before.m_decision == after.m_decision
                and before.x_decision == after.x_decision
            ),
            expected="cosmetic refinement changes A but is not a robustness pass",
            observed={
                "after_A": after_row.outcome_concentration,
                "before_A": before_row.outcome_concentration,
                "evsi": before_row.evsi,
                "robustness_pass_claimed": False,
            },
        )
    )

    tie_probe = _control_snapshot(
        (a1, a2, a3, a4),
        (0.5, 0.5),
        {
            a1: (first, first),
            a2: (second, second),
            a3: (first, second),
            a4: (first, second),
        },
        {
            a1: (0.0, 4.0),
            a2: (4.0, 0.0),
            a3: (8.0, 8.0),
            a4: (8.0, 8.0),
        },
    )
    forward = _select_control(tie_probe, counters, multiplier=1.0)
    reversed_snapshot = reverse_candidate_order(tie_probe)
    reversed_selection = _select_control(reversed_snapshot, counters, multiplier=1.0)
    records.append(
        _control_record(
            PREREGISTERED_CONTROL_ORDER[19],
            passes=(
                set(forward.x_utility_maximizers)
                == set(reversed_selection.x_utility_maximizers)
                and forward.x_decision.mode == reversed_selection.x_decision.mode
                and forward.x_decision.action != reversed_selection.x_decision.action
            ),
            expected="candidate-order tie break switches action but preserves maximizers/mode",
            observed={
                "forward": _selection_json(forward),
                "reversed": _selection_json(reversed_selection),
            },
        )
    )
    if tuple(record["name"] for record in records) != PREREGISTERED_CONTROL_ORDER:
        raise RuntimeError("control record order differs from preregistration")
    observed_control_calls = (
        counters.snapshot()["pure_selector_control_calls"] - calls_before
    )
    observed_total_calls = counters.snapshot()["pure_selector_calls"] - total_calls_before
    if (
        observed_control_calls != PREREGISTERED_CONTROL_SELECTOR_CALLS
        or observed_total_calls != PREREGISTERED_CONTROL_SELECTOR_CALLS
    ):
        raise RuntimeError("control selector calls differ from the explicit call ledger")
    return tuple(records)


def _evaluate_preregistered_control(
    index: int,
    counters: AuditCounterState,
) -> dict[str, JsonValue]:
    """Evaluate one control independently so a failed row cannot hide later rows."""

    name = PREREGISTERED_CONTROL_ORDER[index]
    a1 = Action(ActionKind.ACTION1)
    a2 = Action(ActionKind.ACTION2)
    a3 = Action(ActionKind.ACTION3)
    a4 = Action(ActionKind.ACTION4)
    first = _control_prediction(1)
    second = _control_prediction(2)
    weights4 = (0.4, 0.3, 0.2, 0.1)
    labels = tuple(_control_prediction(item + 1) for item in range(4))

    if index == 0:
        selection = _select_control(
            _two_hypothesis_control(cross_cost=0.0), counters
        )
        row = _selection_by_action(selection)[a1]
        return _control_record(
            name,
            passes=row.outcome_concentration == 1.0 and not row.eligible,
            expected="A=1 is strictly ineligible and cannot establish the contrast",
            observed=_selection_json(selection),
        )
    if index == 1:
        selection = _select_control(
            _two_hypothesis_control(
                weights=(0.8, 0.2), cross_cost=10.0, probe_cost=20.0
            ),
            counters,
        )
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=(
                isclose(row.outcome_concentration, 0.8, abs_tol=1e-12)
                and row.x_utility > 0.0
                and not row.eligible
                and selection.x_decision.mode == "exploit"
            ),
            expected="strict equality at A=0.8 blocks despite positive J_X",
            observed=_selection_json(selection),
        )
    if index == 2:
        snapshot = _control_snapshot(
            (a1, a2, a3),
            (0.5, 0.5),
            {a1: (first, first), a2: (second, second), a3: (first, second)},
            {a1: (0.0, 0.0), a2: (1.0, 1.0), a3: (2.0, 2.0)},
        )
        selection = _select_control(snapshot, counters)
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=(
                row.eligible
                and row.evsi == 0.0
                and selection.x_decision.mode == "exploit"
            ),
            expected="A<0.8 without decision information blocks",
            observed=_selection_json(selection),
        )
    if index == 3:
        snapshot = _control_snapshot(
            (a1, a2, a3),
            weights4,
            {a1: (labels[0],) * 4, a2: (labels[1],) * 4, a3: labels},
            {a1: (0.0,) * 4, a2: (1.0,) * 4, a3: (2.0,) * 4},
        )
        selection = _select_control(snapshot, counters)
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=row.outcome_cell_count == 4 and row.evsi == 0.0,
            expected="fragmented cosmetic outcomes do not create EVSI",
            observed=_selection_json(selection),
        )
    if index == 4:
        selection = _select_control(
            _two_hypothesis_control(cross_cost=0.098, probe_cost=1.0), counters
        )
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=(
                isclose(row.evsi, 0.049, abs_tol=1e-12)
                and selection.x_decision.mode == "probe"
                and row.evsi < 0.05
            ),
            expected="live X may probe, but admission blocks solely on EVSI<0.05",
            observed=_selection_json(selection),
        )
    if index == 5:
        selection = _select_control(
            _two_hypothesis_control(
                weights=(0.9, 0.1), cross_cost=20.0, probe_cost=30.0
            ),
            counters,
        )
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=(
                row.x_utility > 0.0
                and row.outcome_concentration >= 0.8
                and not row.eligible
            ),
            expected="material positive J_X remains blocked by high A",
            observed=_selection_json(selection),
        )
    if index == 6:
        a5 = Action(ActionKind.ACTION5)
        inverse_costs = {
            a1: (0.0, 10.0, 10.0, 10.0),
            a2: (10.0, 0.0, 10.0, 10.0),
            a3: (10.0, 10.0, 0.0, 10.0),
            a4: (10.0, 10.0, 10.0, 0.0),
            a5: (20.0, 20.0, 20.0, 20.0),
        }
        snapshot = _control_snapshot(
            (a1, a2, a3, a4, a5),
            weights4,
            {
                a1: (labels[0],) * 4,
                a2: (labels[1],) * 4,
                a3: (labels[2],) * 4,
                a4: (labels[3],) * 4,
                a5: (labels[0], labels[0], labels[0], labels[3]),
            },
            inverse_costs,
        )
        selection = _select_control(snapshot, counters)
        row = _selection_by_action(selection)[a5]
        agreement = committee_agreement(
            snapshot.actions, snapshot.costs, snapshot.weights
        )
        return _control_record(
            name,
            passes=(
                agreement < 0.8
                and row.outcome_concentration >= 0.8
                and row.x_utility > 0.0
                and not row.eligible
            ),
            expected="low global agreement cannot override action-specific high A",
            observed={"global_agreement": agreement, "selection": _selection_json(selection)},
        )
    if index == 7:
        catastrophe = _control_prediction(2, game_state=GameState.GAME_OVER)
        snapshot = _control_snapshot(
            (a1, a2, a3, a4),
            (0.5, 0.5),
            {
                a1: (first, first),
                a2: (second, second),
                a3: (first, second),
                a4: (first, catastrophe),
            },
            {
                a1: (0.0, 4.0),
                a2: (4.0, 0.0),
                a3: (8.0, 8.0),
                a4: (8.0, 8.0),
            },
        )
        selection = _select_control(snapshot, counters)
        selected = _selection_by_action(selection)[a3]
        unused = _selection_by_action(selection)[a4]
        return _control_record(
            name,
            passes=(
                unused.eligible
                and unused.x_utility > 0.0
                and unused.m_utility <= 0.0
                and not unused.x_selected
                and selection.x_decision.action == a3
                and selection.m_decision.action == a3
                and selected.eligible
                and selected.m_utility > 0.0
                and selected.x_utility > 0.0
                and selected.m_selected
                and selected.x_selected
            ),
            expected="an unused X-only row is not the selected shared positive M/X probe",
            observed=_selection_json(selection),
        )
    if index == 8:
        a5 = Action(ActionKind.ACTION5)
        a6 = Action(ActionKind.ACTION6, 0, 0)
        snapshot = _control_snapshot(
            (a1, a2, a3, a4, a5, a6),
            weights4,
            {
                a1: (labels[0],) * 4,
                a2: (labels[1],) * 4,
                a3: (labels[2],) * 4,
                a4: (labels[3],) * 4,
                a5: (labels[0], labels[1], labels[2], labels[2]),
                a6: (
                    labels[0],
                    labels[1],
                    _control_prediction(3, game_state=GameState.GAME_OVER),
                    labels[3],
                ),
            },
            {
                a1: (0, 6, 3, 6),
                a2: (0, 8, 3, 7),
                a3: (7, 8, 3, 5),
                a4: (3, 3, 7, 4),
                a5: (0, 6, 8, 1),
                a6: (2, 4, 1, 5),
            },
        )
        selection = _select_control(snapshot, counters)
        return _control_record(
            name,
            passes=(
                selection.m_decision.mode == "probe"
                and selection.x_decision.mode == "probe"
                and selection.m_decision.action == a5
                and selection.x_decision.action == a6
            ),
            expected="positive M probing blocks the M-exploit/X-probe conjunction",
            observed=_selection_json(selection),
        )
    if index == 9:
        selection = _select_control(
            _two_hypothesis_control(), counters, probes_used=3
        )
        return _control_record(
            name,
            passes=(
                selection.m_decision.mode == selection.x_decision.mode == "exploit"
                and selection.x_decision.gate_reason == "level_probe_cap_reached"
            ),
            expected="exhausted shared probe cap blocks probing",
            observed=_selection_json(selection),
        )
    if index == 10:
        selection = _select_control(
            _two_hypothesis_control(catastrophe=True), counters, multiplier=2.0
        )
        row = _selection_by_action(selection)[a3]
        return _control_record(
            name,
            passes=row.catastrophe_mass == 0.5 and row.x_utility <= 0.0,
            expected="catastrophe cost makes J_X nonpositive",
            observed=_selection_json(selection),
        )
    if index == 11:
        selection = _select_control(
            _two_hypothesis_control(cross_cost=4.0, probe_cost=8.0),
            counters,
            multiplier=1.0,
        )
        return _control_record(
            name,
            passes=selection.m_decision == selection.x_decision,
            expected="final-level multiplier one makes M and X identical",
            observed=_selection_json(selection),
        )
    if index in {12, 13}:
        selection = _select_control(_two_hypothesis_control(), counters)
        reason = "invalid_program" if index == 12 else "timeout_program"
        gate = _admission_resource_gate(
            AdmissionResourceSignals(
                invalid_programs=1 if index == 12 else 0,
                timeout_programs=1 if index == 13 else 0,
            )
        )
        return _control_record(
            name,
            passes=gate["passes"] is False and gate["reasons"] == [reason],
            expected="filtered program failure keeps the structural gate false",
            observed={
                "failure_kind": "invalid" if index == 12 else "timeout",
                "admission_resource_gate": gate,
                "selector_on_filtered_snapshot": _selection_json(selection),
            },
        )
    if index == 14:
        gate = _admission_resource_gate(
            AdmissionResourceSignals(eligible_graded_roles=1)
        )
        return _control_record(
            name,
            passes=(
                gate["passes"] is False
                and gate["reasons"] == ["fewer_than_two_eligible_graded_roles"]
            ),
            expected="fewer than two eligible graded roles blocks structurally",
            observed=gate,
        )
    if index == 15:
        gate = _admission_resource_gate(AdmissionResourceSignals(worker_memory_ok=False))
        return _control_record(
            name,
            passes=(
                gate["passes"] is False and gate["reasons"] == ["worker_memory_drift"]
            ),
            expected="any worker-memory drift blocks structurally",
            observed=gate,
        )
    if index == 16:
        counts = {field: 0 for field in FORBIDDEN_AUDIT_RESOURCE_FIELDS}
        counts["model_calls"] = 1
        gate = _admission_resource_gate(
            AdmissionResourceSignals(forbidden_resource_counts=counts)
        )
        return _control_record(
            name,
            passes=(
                gate["passes"] is False
                and gate["reasons"] == ["forbidden_resource_use"]
                and gate["forbidden_resources_used"] == ["model_calls"]
            ),
            expected="hypothetical forbidden resource use blocks without using it",
            observed=gate,
        )
    if index == 17:
        snapshot = _control_snapshot(
            (a1, a2, a3),
            (0.25, 0.25, 0.25, 0.25),
            {
                a1: (first, first, first, first),
                a2: (first, first, second, second),
                a3: (first, second, first, second),
            },
            {
                a1: (0.05, 0.05, 0.05, 0.05),
                a2: (0.0, 0.0, 0.1, 0.1),
                a3: (0.1, 0.1, 0.0, 0.0),
            },
        )
        selection = _select_control(snapshot, counters)
        row = _selection_by_action(selection)[a2]
        resource_gate = _admission_resource_gate(AdmissionResourceSignals())
        mechanism = _mechanism_gate(selection, selected_evsi_minimum_margin=0.0)
        return _control_record(
            name,
            passes=(
                isclose(row.evsi, 0.05, abs_tol=1e-12)
                and row.eligible
                and row.x_utility > 0.0
                and row.m_utility <= 0.0
                and selection.m_decision.mode == "exploit"
                and selection.x_decision.mode == "probe"
                and selection.x_decision.action == a2
                and resource_gate["passes"] is True
                and mechanism["passes"] is True
            ),
            expected="EVSI equality at 0.05 satisfies admission materiality",
            observed={
                "admission_resource_gate": resource_gate,
                "mechanism_gate": mechanism,
                "selection": _selection_json(selection),
            },
        )
    if index == 18:
        base = _control_snapshot(
            (a1, a2, a3),
            weights4,
            {
                a1: (labels[0],) * 4,
                a2: (labels[1],) * 4,
                a3: (labels[0], labels[0], labels[1], labels[1]),
            },
            {a1: (0.0,) * 4, a2: (1.0,) * 4, a3: (2.0,) * 4},
        )
        split = _control_snapshot(
            (a1, a2, a3),
            weights4,
            {a1: (labels[0],) * 4, a2: (labels[1],) * 4, a3: labels},
            base.costs,
        )
        before = _select_control(base, counters)
        after = _select_control(split, counters)
        before_row = _selection_by_action(before)[a3]
        after_row = _selection_by_action(after)[a3]
        return _control_record(
            name,
            passes=(
                before_row.evsi == after_row.evsi == 0.0
                and before_row.outcome_concentration
                != after_row.outcome_concentration
                and before.m_decision == after.m_decision
                and before.x_decision == after.x_decision
            ),
            expected="cosmetic refinement changes A but is not a robustness pass",
            observed={
                "after_A": after_row.outcome_concentration,
                "before_A": before_row.outcome_concentration,
                "evsi": before_row.evsi,
                "robustness_pass_claimed": False,
            },
        )
    if index == 19:
        snapshot = _control_snapshot(
            (a1, a2, a3, a4),
            (0.5, 0.5),
            {
                a1: (first, first),
                a2: (second, second),
                a3: (first, second),
                a4: (first, second),
            },
            {
                a1: (0.0, 4.0),
                a2: (4.0, 0.0),
                a3: (8.0, 8.0),
                a4: (8.0, 8.0),
            },
        )
        forward = _select_control(snapshot, counters, multiplier=1.0)
        reversed_selection = _select_control(
            reverse_candidate_order(snapshot), counters, multiplier=1.0
        )
        return _control_record(
            name,
            passes=(
                set(forward.x_utility_maximizers)
                == set(reversed_selection.x_utility_maximizers)
                and forward.x_decision.mode == reversed_selection.x_decision.mode
                and forward.x_decision.action != reversed_selection.x_decision.action
            ),
            expected="candidate-order tie switches action but preserves maximizers/mode",
            observed={
                "forward": _selection_json(forward),
                "reversed": _selection_json(reversed_selection),
            },
        )
    raise ValueError("control index is outside the preregistered inventory")


def evaluate_preregistered_controls(
    counters: AuditCounterState,
    *,
    continue_after_failure: bool = False,
) -> tuple[dict[str, JsonValue], ...]:
    """Evaluate twenty independent rows using the exact nineteen-call ledger."""

    total_before = counters.snapshot()["pure_selector_calls"]
    control_before = counters.snapshot()["pure_selector_control_calls"]
    records: list[dict[str, JsonValue]] = []
    had_failure = False
    for index, name in enumerate(PREREGISTERED_CONTROL_ORDER):
        row_calls_before = counters.snapshot()["pure_selector_control_calls"]
        try:
            record = _evaluate_preregistered_control(index, counters)
            observed_calls = (
                counters.snapshot()["pure_selector_control_calls"] - row_calls_before
            )
            if observed_calls != PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER[name]:
                raise RuntimeError("control selector calls differ from its row ledger")
        except Exception as error:
            if not continue_after_failure or not counters.scientific_exposure_started:
                raise
            had_failure = True
            failure = _deterministic_stage_failure("control_row_failed", error)
            record = {
                "expected_gate_semantics": "registered control row completes",
                "failure": failure,
                "name": name,
                "observed": failure,
                "passes": False,
            }
        records.append(record)
    if tuple(record["name"] for record in records) != PREREGISTERED_CONTROL_ORDER:
        raise RuntimeError("control record order differs from preregistration")
    observed_control_calls = (
        counters.snapshot()["pure_selector_control_calls"] - control_before
    )
    observed_total_calls = counters.snapshot()["pure_selector_calls"] - total_before
    if not had_failure and (
        observed_control_calls != PREREGISTERED_CONTROL_SELECTOR_CALLS
        or observed_total_calls != PREREGISTERED_CONTROL_SELECTOR_CALLS
    ):
        raise RuntimeError("control selector calls differ from the explicit call ledger")
    return tuple(records)


def preregistered_control_contract_sha256() -> str:
    """Return the source-bound identity used by the dedicated registration."""

    return canonical_sha256(
        {
            "control_order": list(PREREGISTERED_CONTROL_ORDER),
            "evaluator_source_sha256": _sha256(
                (
                    inspect.getsource(_evaluate_preregistered_control)
                    + inspect.getsource(evaluate_preregistered_controls)
                ).encode("utf-8")
            ),
            "schema_version": 1,
            "selector_call_ledger": dict(PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER),
        }
    )


AUDIT_WALL_TIME_SECONDS: Final = 1_200.0
SEALED_SCENE_FAMILIES: Final = ("homologue", "containment", "reflection")
SEALED_VISUAL_TRANSFORM_NAMES: Final = (
    "palette_bijection",
    "translation_row_plus_3_col_plus_5",
    "translation_row_minus_3_col_minus_5",
    "scale_2_nearest_neighbor",
)


class AuditWallTimeExceeded(TimeoutError):
    """The fixed whole-audit wall-time budget expired."""


def _require_before_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise AuditWallTimeExceeded("sealed audit exceeded the fixed 1,200-second wall cap")


def _scene_identity(scene: Mapping[str, Any]) -> tuple[str, int, str]:
    family = scene.get("family")
    family_index = scene.get("family_index")
    if family not in SEALED_SCENE_FAMILIES:
        raise ValueError("audit scene family differs from the registered family set")
    if (
        isinstance(family_index, bool)
        or not isinstance(family_index, int)
        or not 0 <= family_index < 4
    ):
        raise ValueError("audit scene lacks a registered family index")
    return str(family), family_index, f"{family}/{family_index}"


def _deterministic_stage_failure(
    stage: str,
    error: Exception | None = None,
) -> dict[str, JsonValue]:
    """Describe a scientific-stage failure without unstable paths or messages."""

    payload: dict[str, JsonValue] = {"stage": stage}
    if error is not None:
        payload["error_type"] = type(error).__name__
    return payload


def _deterministic_finalization_failure(
    stage: str,
    error: Exception | None = None,
) -> dict[str, JsonValue]:
    """Use one exact schema for failures consumed by the output validator."""

    return {
        "error_type": type(error).__name__ if error is not None else None,
        "stage": stage,
    }


def _failed_scientific_gate(
    stage: str,
    error: Exception | None = None,
) -> dict[str, JsonValue]:
    return {
        "failure": _deterministic_stage_failure(stage, error),
        "passes": False,
        "reasons": [stage],
    }


def _failed_order_records(
    stage: str,
    error: Exception | None = None,
) -> tuple[dict[str, JsonValue], ...]:
    failure = _deterministic_stage_failure(stage, error)
    return tuple(
        {
            "failure": failure,
            "kind": "order_transform",
            "name": name,
            "passes": False,
            "reasons": [stage],
        }
        for name in ORDER_TRANSFORM_NAMES
    )


def _failed_scene_records(
    scene: Mapping[str, Any],
    *,
    stage: str,
    error: Exception | None,
) -> tuple[dict[str, JsonValue], ...]:
    """Materialize every registered row for an unexpectedly failed scene."""

    family, family_index, scene_id = _scene_identity(scene)
    scene_sha256 = cast(str, scene.get("content_sha256"))
    failure = _deterministic_stage_failure(stage, error)
    failed_gate = _failed_scientific_gate(stage, error)
    records: list[dict[str, JsonValue]] = [
        {
            "causal_exercise": False,
            "family": family,
            "family_index": family_index,
            "kind": "base_scene",
            "mechanism_gate": failed_gate,
            "pipeline": {"failure": failure, "status": "failed"},
            "positive_mechanism": False,
            "scene_content_sha256": scene_sha256,
            "scene_id": scene_id,
            "structural_gate": failed_gate,
            "v4_counterfactual": {
                "causal_exercise": False,
                "failure": failure,
                "passes": False,
            },
        }
    ]
    visual_transforms = cast(Sequence[Mapping[str, Any]], scene["visual_transforms"])
    for transform_index, transform in enumerate(visual_transforms):
        records.append(
            {
                "comparison": failed_gate,
                "family": family,
                "family_index": family_index,
                "grid_sha256": cast(str, transform.get("grid_sha256")),
                "kind": "visual_transform",
                "pipeline": {"failure": failure, "status": "failed"},
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
                "structural_gate": failed_gate,
                "transform_content_sha256": cast(
                    str, transform.get("content_sha256")
                ),
                "transform_index": transform_index,
                "transform_name": cast(str, transform.get("name")),
            }
        )
    for order_index, order_record in enumerate(_failed_order_records(stage, error)):
        records.append(
            {
                **order_record,
                "family": family,
                "family_index": family_index,
                "order_index": order_index,
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
            }
        )
    if len(records) != 10:
        raise RuntimeError("failed scene materialization did not produce ten rows")
    return tuple(records)


def evaluate_scene_record(
    scene: Mapping[str, Any],
    *,
    config: SystemConfig,
    counters: AuditCounterState,
    order_transform_maps: Sequence[Mapping[str, Any]],
    require_linux_memory: bool,
    deadline: float,
) -> tuple[dict[str, JsonValue], ...]:
    """Produce one base, four visual, and five order records for a scene."""

    family, family_index, scene_id = _scene_identity(scene)
    if scene.get("generation_status") != "complete" or scene.get("scope") != "registered":
        raise ValueError("sealed audit requires a complete registered scene")
    base_scene = scene.get("base_scene")
    visual_transforms = scene.get("visual_transforms")
    if not isinstance(base_scene, Mapping) or not isinstance(visual_transforms, list):
        raise ValueError("complete registered scene lacks base/visual records")
    if tuple(
        transform.get("name") if isinstance(transform, Mapping) else None
        for transform in visual_transforms
    ) != SEALED_VISUAL_TRANSFORM_NAMES:
        raise ValueError("visual transform set/order differs from registration")
    typed_visual_transforms: list[Mapping[str, Any]] = []
    for raw_transform in visual_transforms:
        if not isinstance(raw_transform, Mapping):
            raise ValueError("visual transform is not a mapping")
        if not isinstance(raw_transform.get("action_map"), Mapping):
            raise ValueError("visual transform lacks its registered action map")
        typed_visual_transforms.append(raw_transform)

    base: PipelineAuditResult | None = None
    base_pipeline_payload: dict[str, JsonValue] | None = None
    base_pipeline_failure: Exception | None = None
    try:
        _require_before_deadline(deadline)
        completed_base = evaluate_compiler_planner_snapshot(
            _scene_history(base_scene, base_scene),
            config=config,
            counters=counters,
            exercise_controllers=True,
        )
        base_pipeline_payload = _pipeline_json(completed_base)
        base = completed_base
    except Exception as error:
        if not counters.scientific_exposure_started:
            raise
        base_pipeline_failure = error

    v4: dict[str, JsonValue]
    if base is None:
        structural = _failed_scientific_gate(
            "base_pipeline_failed", base_pipeline_failure
        )
        mechanism = _failed_scientific_gate(
            "base_pipeline_failed", base_pipeline_failure
        )
    else:
        try:
            structural = _structural_gate(
                base, require_linux_memory=require_linux_memory
            )
        except Exception as error:
            structural = _failed_scientific_gate("base_structural_gate_failed", error)
        try:
            mechanism = _mechanism_gate(base.selection, probe_cap_available=True)
        except Exception as error:
            mechanism = _failed_scientific_gate("base_mechanism_gate_failed", error)
    positive = structural["passes"] is True and mechanism["passes"] is True
    if base is None:
        v4 = {
            "causal_exercise": False,
            "failure": _deterministic_stage_failure(
                "base_pipeline_failed", base_pipeline_failure
            ),
            "passes": False,
        }
    else:
        try:
            v4 = _v4_counterfactual(
                base,
                structural_passes=structural["passes"] is True,
                probe_cap_available=True,
                counters=counters,
            )
        except Exception as error:
            v4 = {
                "causal_exercise": False,
                "failure": _deterministic_stage_failure(
                    "v4_counterfactual_failed", error
                ),
                "passes": False,
            }
    causal = positive and v4["causal_exercise"] is True
    records: list[dict[str, JsonValue]] = [
        {
            "causal_exercise": causal,
            "family": family,
            "family_index": family_index,
            "kind": "base_scene",
            "mechanism_gate": mechanism,
            "pipeline": (
                base_pipeline_payload
                if base_pipeline_payload is not None
                else {
                    "failure": _deterministic_stage_failure(
                        "base_pipeline_failed", base_pipeline_failure
                    ),
                    "status": "failed",
                }
            ),
            "positive_mechanism": positive,
            "scene_content_sha256": cast(str, scene.get("content_sha256")),
            "scene_id": scene_id,
            "structural_gate": structural,
            "v4_counterfactual": v4,
        }
    ]

    for transform_index, raw_transform in enumerate(typed_visual_transforms):
        action_map = cast(Mapping[str, Any], raw_transform["action_map"])
        is_scale = transform_index == 3
        transformed: PipelineAuditResult | None = None
        transformed_pipeline_payload: dict[str, JsonValue] | None = None
        transformed_failure: Exception | None = None
        visual_failure_stage = "visual_pipeline_failed"
        if is_scale and base is None:
            visual_failure_stage = "base_pipeline_unavailable"
        else:
            try:
                supplied_actions = (
                    tuple(_map_action(action, action_map) for action in base.actions)
                    if is_scale and base is not None
                    else None
                )
                _require_before_deadline(deadline)
                completed_transformed = evaluate_compiler_planner_snapshot(
                    _scene_history(raw_transform, base_scene),
                    config=config,
                    counters=counters,
                    supplied_actions=supplied_actions,
                    exercise_controllers=not is_scale,
                )
                transformed_pipeline_payload = _pipeline_json(completed_transformed)
                transformed = completed_transformed
            except Exception as error:
                if not counters.scientific_exposure_started:
                    raise
                transformed_failure = error
        if transformed is None:
            transformed_structural = _failed_scientific_gate(
                visual_failure_stage, transformed_failure
            )
            comparison = _failed_scientific_gate(
                visual_failure_stage, transformed_failure
            )
        else:
            try:
                transformed_structural = _structural_gate(
                    transformed,
                    require_linux_memory=require_linux_memory,
                )
            except Exception as error:
                transformed_structural = _failed_scientific_gate(
                    "visual_structural_gate_failed", error
                )
            if base is None:
                comparison = _failed_scientific_gate("base_pipeline_unavailable")
            else:
                try:
                    comparison = _compare_visual_transform(
                        base, transformed, raw_transform
                    )
                except Exception as error:
                    comparison = _failed_scientific_gate(
                        "visual_comparison_failed", error
                    )
        records.append(
            {
                "comparison": comparison,
                "family": family,
                "family_index": family_index,
                "grid_sha256": cast(str, raw_transform.get("grid_sha256")),
                "kind": "visual_transform",
                "pipeline": (
                    transformed_pipeline_payload
                    if transformed_pipeline_payload is not None
                    else {
                        "failure": _deterministic_stage_failure(
                            visual_failure_stage, transformed_failure
                        ),
                        "status": "failed",
                    }
                ),
                "scene_content_sha256": cast(str, scene.get("content_sha256")),
                "scene_id": scene_id,
                "structural_gate": transformed_structural,
                "transform_content_sha256": cast(
                    str, raw_transform.get("content_sha256")
                ),
                "transform_index": transform_index,
                "transform_name": cast(str, raw_transform.get("name")),
            }
        )

    if base is None:
        order_records = _failed_order_records("base_pipeline_unavailable")
    else:
        try:
            _require_before_deadline(deadline)
            order_records = evaluate_order_transforms(
                base,
                counters=counters,
                order_transform_maps=order_transform_maps,
                base_positive=positive,
                continue_after_failure=True,
                deadline=deadline,
            )
        except Exception as error:
            if not counters.scientific_exposure_started:
                raise
            order_records = _failed_order_records("order_transform_suite_failed", error)
    for order_index, order_record in enumerate(order_records):
        records.append(
            {
                **order_record,
                "family": family,
                "family_index": family_index,
                "order_index": order_index,
                "scene_content_sha256": cast(str, scene.get("content_sha256")),
                "scene_id": scene_id,
            }
        )
    if len(records) != 10:
        raise RuntimeError("scene evaluator did not emit exactly ten registered records")
    return tuple(records)


def _aggregate_acceptance(
    records: Sequence[Mapping[str, Any]],
    counters: AuditCounterState,
    *,
    finalization_complete: bool = True,
    within_deadline: bool = True,
) -> dict[str, JsonValue]:
    base_rows = tuple(row for row in records if row.get("kind") == "base_scene")
    visual_rows = tuple(row for row in records if row.get("kind") == "visual_transform")
    order_rows = tuple(row for row in records if row.get("kind") == "order_transform")
    control_rows = tuple(row for row in records if row.get("kind") == "control")
    pipeline_rows = (*base_rows, *visual_rows)
    positive_by_family = {
        family: sum(
            row.get("positive_mechanism") is True
            for row in base_rows
            if row.get("family") == family
        )
        for family in SEALED_SCENE_FAMILIES
    }
    causal_by_family = {
        family: sum(
            row.get("causal_exercise") is True
            for row in base_rows
            if row.get("family") == family
        )
        for family in SEALED_SCENE_FAMILIES
    }
    positive_total = sum(positive_by_family.values())
    causal_total = sum(causal_by_family.values())
    counter_mismatches = counters.require_exact(EXPECTED_SEALED_RESOURCE_COUNTS)
    checks: dict[str, bool] = {
        "all_base_structural": len(base_rows) == 12
        and all(
            cast(Mapping[str, Any], row.get("structural_gate")).get("passes") is True
            for row in base_rows
        ),
        "all_control_gates": len(control_rows) == 20
        and all(row.get("passes") is True for row in control_rows),
        "all_pipeline_structural": len(pipeline_rows) == 60
        and all(
            cast(Mapping[str, Any], row.get("structural_gate")).get("passes") is True
            for row in pipeline_rows
        ),
        "all_order_transforms": len(order_rows) == 60
        and all(row.get("passes") is True for row in order_rows),
        "all_visual_transforms": len(visual_rows) == 48
        and all(
            cast(Mapping[str, Any], row.get("comparison")).get("passes") is True
            for row in visual_rows
        ),
        "causal_family_minimum": all(value >= 1 for value in causal_by_family.values()),
        "causal_total_minimum": causal_total >= 6,
        "exact_record_count": len(records) == 140,
        "exact_resource_counters": not counter_mismatches,
        "finalization_complete": finalization_complete,
        "positive_family_minimum": all(
            value >= 3 for value in positive_by_family.values()
        ),
        "positive_total_minimum": positive_total >= 9,
        "scientific_exposure_recorded": counters.scientific_exposure_started,
        "within_wall_time": within_deadline,
    }
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    return {
        "acceptance_passes": not failed_checks,
        "causal_by_family": cast(JsonValue, causal_by_family),
        "causal_total": causal_total,
        "checks": cast(JsonValue, checks),
        "counter_mismatches": cast(JsonValue, list(counter_mismatches)),
        "failed_checks": cast(JsonValue, failed_checks),
        "final_admission_claimed": False,
        "positive_by_family": cast(JsonValue, positive_by_family),
        "positive_total": positive_total,
        "runtime_v5_enabled": False,
    }


def _deterministic_environment_identity(
    provenance: AuditProvenance,
) -> dict[str, JsonValue]:
    source_files = provenance.source_files or ()
    dependency_files = {
        identity.path: identity.sha256
        for identity in source_files
        if identity.path in {"pyproject.toml", "uv.lock"}
    }
    if set(dependency_files) != {"pyproject.toml", "uv.lock"}:
        raise ValueError("scientific provenance lacks deterministic dependency files")
    return {
        "dependency_file_sha256": cast(JsonValue, dependency_files),
        "machine": platform.machine(),
        "numpy_version": np.__version__,
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def _bind_registered_row_inventory(
    records: Sequence[dict[str, JsonValue]],
    registration_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, JsonValue]]:
    known_kinds = {"base_scene", "visual_transform", "order_transform", "control"}
    if len(records) != 140 or any(row.get("kind") not in known_kinds for row in records):
        raise ValueError("scientific record inventory has unknown or extra/missing rows")
    ordered = [
        *(row for row in records if row.get("kind") == "base_scene"),
        *(row for row in records if row.get("kind") == "visual_transform"),
        *(row for row in records if row.get("kind") == "order_transform"),
        *(row for row in records if row.get("kind") == "control"),
    ]
    if (
        len(ordered) != len(records)
        or len(ordered) != 140
        or len(registration_rows) != 140
    ):
        raise ValueError("scientific/registered row inventory does not contain 140 rows")
    bound: list[dict[str, JsonValue]] = []
    for row_index, (record, registered) in enumerate(
        zip(ordered, registration_rows, strict=True)
    ):
        row_id = registered.get("row_id")
        if (
            registered.get("row_index") != row_index
            or registered.get("kind") != record.get("kind")
            or not isinstance(row_id, str)
        ):
            raise ValueError("scientific record differs from registered row index/kind")
        kind = record["kind"]
        if kind == "base_scene":
            identity_matches = (
                registered.get("family") == record.get("family")
                and registered.get("scene_index") == record.get("family_index")
                and record.get("scene_id")
                == f"{record.get('family')}/{record.get('family_index')}"
                and registered.get("fixture_sha256")
                == record.get("scene_content_sha256")
                and row_id
                == f"base:{record.get('family')}:{record.get('family_index')}"
            )
        elif kind in {"visual_transform", "order_transform"}:
            transform = (
                record.get("transform_name")
                if kind == "visual_transform"
                else record.get("name")
            )
            address: JsonValue = {
                "lockbox_content_sha256": LOCKBOX_CONTENT_SHA256,
                "scene_sha256": cast(str, record.get("scene_content_sha256")),
                "transform": cast(str, transform),
            }
            prefix = "visual" if kind == "visual_transform" else "order"
            identity_matches = (
                registered.get("family") == record.get("family")
                and registered.get("scene_index") == record.get("family_index")
                and record.get("scene_id")
                == f"{record.get('family')}/{record.get('family_index')}"
                and registered.get("transform") == transform
                and registered.get("fixture_address_sha256")
                == canonical_sha256(address)
                and row_id
                == (
                    f"{prefix}:{record.get('family')}:{record.get('family_index')}:"
                    f"{transform}"
                )
            )
        else:
            identity_matches = (
                kind == "control"
                and registered.get("control_id") == record.get("name")
                and row_id == f"control:{record.get('name')}"
            )
        if not identity_matches:
            raise ValueError("scientific record identity differs from registration")
        bound.append(
            {
                **record,
                "registered_row": cast(JsonValue, dict(registered)),
                "row_id": row_id,
                "row_index": row_index,
            }
        )
    return bound


type ScientificRecordAddress = tuple[str | int, ...]


def _scientific_record_address(
    record: Mapping[str, Any],
) -> ScientificRecordAddress:
    """Return the full registered identity of one scientific record."""

    kind = record.get("kind")
    if kind == "control":
        name = record.get("name")
        if not isinstance(name, str):
            raise ValueError("control record lacks a stable registered identity")
        return (kind, name)
    if kind not in {"base_scene", "visual_transform", "order_transform"}:
        raise ValueError("scientific record has an unknown kind")
    family = record.get("family")
    family_index = record.get("family_index")
    scene_id = record.get("scene_id")
    scene_sha256 = record.get("scene_content_sha256")
    if (
        not isinstance(family, str)
        or isinstance(family_index, bool)
        or not isinstance(family_index, int)
        or not isinstance(scene_id, str)
        or not isinstance(scene_sha256, str)
    ):
        raise ValueError("scene record lacks a stable registered identity")
    if scene_id != f"{family}/{family_index}":
        raise ValueError("scene record id differs from family/index identity")
    base: ScientificRecordAddress = (
        kind,
        family,
        family_index,
        scene_id,
        scene_sha256,
    )
    if kind == "base_scene":
        return base
    transform = (
        record.get("transform_name")
        if kind == "visual_transform"
        else record.get("name")
    )
    if not isinstance(transform, str):
        raise ValueError("transform record lacks a stable registered identity")
    return (*base, transform)


def _not_completed_record_inventory(
    scenes: Sequence[Mapping[str, Any]],
) -> list[dict[str, JsonValue]]:
    """Build all 140 deterministic negative rows before scientific exposure."""

    records: list[dict[str, JsonValue]] = []
    for scene in scenes:
        records.extend(
            _failed_scene_records(
                scene,
                stage="not_completed",
                error=None,
            )
        )
    failure = _deterministic_stage_failure("not_completed")
    records.extend(
        {
            "expected": "registered control evaluates without an exception",
            "failure": failure,
            "kind": "control",
            "name": name,
            "observed": failure,
            "passes": False,
        }
        for name in PREREGISTERED_CONTROL_ORDER
    )
    if len(records) != 140:
        raise RuntimeError("not-completed inventory did not produce 140 rows")
    return records


def _accumulator_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[ScientificRecordAddress, int]:
    index: dict[ScientificRecordAddress, int] = {}
    for row_index, record in enumerate(records):
        address = _scientific_record_address(record)
        if address in index:
            raise ValueError("registered accumulator contains a duplicate identity")
        if record.get("row_index") != row_index:
            raise ValueError("registered accumulator differs from row-index order")
        index[address] = row_index
    if len(index) != 140:
        raise ValueError("registered accumulator does not contain 140 unique rows")
    return index


def _accumulate_completed_records(
    accumulator: list[dict[str, JsonValue]],
    records: Sequence[Mapping[str, Any]],
    *,
    index: Mapping[ScientificRecordAddress, int],
    completed_indices: set[int],
) -> tuple[dict[str, JsonValue], ...]:
    """Atomically retain a batch only after authoritative 140-row revalidation."""

    staged = [dict(record) for record in accumulator]
    staged_indices: set[int] = set()
    try:
        for record in records:
            address = _scientific_record_address(record)
            row_index = index.get(address)
            if row_index is None:
                raise ValueError("scientific record is not in the registered inventory")
            if row_index in completed_indices or row_index in staged_indices:
                raise ValueError("scientific record repeats a completed registered row")
            placeholder = accumulator[row_index]
            candidate: dict[str, JsonValue] = {
                **cast(dict[str, JsonValue], dict(record)),
                "registered_row": placeholder["registered_row"],
                "row_id": cast(str, placeholder["row_id"]),
                "row_index": row_index,
            }
            if _scientific_record_address(candidate) != _scientific_record_address(
                placeholder
            ):
                raise ValueError("scientific record address differs from its placeholder")
            candidate_value = json.loads(canonical_json_bytes(candidate))
            if not isinstance(candidate_value, dict):
                raise ValueError("scientific record did not round-trip as a mapping")
            staged[row_index] = cast(dict[str, JsonValue], candidate_value)
            staged_indices.add(row_index)
        registration_rows: list[Mapping[str, Any]] = []
        for row in staged:
            registered_row = row.get("registered_row")
            if not isinstance(registered_row, Mapping):
                raise ValueError("scientific accumulator lacks its registered row")
            registration_rows.append(cast(Mapping[str, Any], registered_row))
        validated = validate_and_rederive_scientific_records(
            cast(Sequence[Mapping[str, Any]], staged),
            registration_rows,
        )
        for row_index in staged_indices:
            accumulator[row_index] = validated[row_index]
        completed_indices.update(staged_indices)
    except Exception as error:
        return (
            _deterministic_finalization_failure(
                "scientific_record_finalization_failed",
                error,
            ),
        )
    return ()


def _negative_aggregate_acceptance(
    counters: AuditCounterState,
    *,
    within_deadline: bool,
) -> dict[str, JsonValue]:
    """Return the stable acceptance schema when aggregation itself fails."""

    counter_mismatches = counters.require_exact(EXPECTED_SEALED_RESOURCE_COUNTS)
    checks = {
        "aggregation_completed": False,
        "all_base_structural": False,
        "all_control_gates": False,
        "all_pipeline_structural": False,
        "all_order_transforms": False,
        "all_visual_transforms": False,
        "causal_family_minimum": False,
        "causal_total_minimum": False,
        "exact_record_count": True,
        "exact_resource_counters": not counter_mismatches,
        "finalization_complete": False,
        "positive_family_minimum": False,
        "positive_total_minimum": False,
        "scientific_exposure_recorded": counters.scientific_exposure_started,
        "within_wall_time": within_deadline,
    }
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    zeros = {family: 0 for family in SEALED_SCENE_FAMILIES}
    return {
        "acceptance_passes": False,
        "causal_by_family": cast(JsonValue, zeros),
        "causal_total": 0,
        "checks": cast(JsonValue, checks),
        "counter_mismatches": cast(JsonValue, list(counter_mismatches)),
        "failed_checks": cast(JsonValue, failed_checks),
        "final_admission_claimed": False,
        "positive_by_family": cast(JsonValue, zeros),
        "positive_total": 0,
        "runtime_v5_enabled": False,
    }


def _exact_mapping(
    value: object,
    keys: set[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} has a noncanonical schema")
    return cast(Mapping[str, Any], value)


def _require_json_equal(actual: object, expected: JsonValue, label: str) -> None:
    try:
        actual_raw = canonical_json_bytes(cast(JsonValue, actual))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not canonical JSON evidence") from error
    if actual_raw != canonical_json_bytes(expected):
        raise ValueError(f"{label} differs from authoritative rederivation")


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} is not numeric")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{label} is not finite")
    return numeric


def _decode_action_evidence(value: object, label: str) -> Action:
    row = _exact_mapping(value, {"col", "kind", "row"}, label)
    kind = row["kind"]
    coordinate_row = row["row"]
    coordinate_col = row["col"]
    if isinstance(kind, bool) or not isinstance(kind, int):
        raise ValueError(f"{label} kind is not an integer")
    if coordinate_row is not None and (
        isinstance(coordinate_row, bool) or not isinstance(coordinate_row, int)
    ):
        raise ValueError(f"{label} row is not an integer/null")
    if coordinate_col is not None and (
        isinstance(coordinate_col, bool) or not isinstance(coordinate_col, int)
    ):
        raise ValueError(f"{label} col is not an integer/null")
    try:
        action = Action(ActionKind(kind), coordinate_row, coordinate_col)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not a valid bounded action") from error
    if action.kind not in {
        ActionKind.ACTION1,
        ActionKind.ACTION2,
        ActionKind.ACTION3,
        ActionKind.ACTION4,
        ActionKind.ACTION5,
        ActionKind.ACTION6,
    }:
        raise ValueError(f"{label} is outside the registered action set")
    return action


type _PredictionEvidenceKey = tuple[str, int, int, str, int]


def _prediction_evidence_key(value: object, label: str) -> _PredictionEvidenceKey:
    row = _exact_mapping(
        value,
        {"game_state", "grid_bytes_sha256", "grid_shape", "level_delta"},
        label,
    )
    digest = row["grid_bytes_sha256"]
    shape = row["grid_shape"]
    game_state = row["game_state"]
    level_delta = row["level_delta"]
    if not _is_lower_hex(digest, 64):
        raise ValueError(f"{label} grid digest is malformed")
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in shape)
        or not all(1 <= cast(int, item) <= 64 for item in shape)
    ):
        raise ValueError(f"{label} grid shape is malformed")
    if not isinstance(game_state, str):
        raise ValueError(f"{label} game state is malformed")
    if isinstance(level_delta, bool) or not isinstance(level_delta, int):
        raise ValueError(f"{label} level delta is malformed")
    try:
        state = GameState(game_state)
    except ValueError as error:
        raise ValueError(f"{label} game state is unknown") from error
    return (
        cast(str, digest),
        cast(int, shape[0]),
        cast(int, shape[1]),
        state.value,
        level_delta,
    )


def _decode_prediction_evidence(
    value: object,
    *,
    cache: dict[_PredictionEvidenceKey, Prediction],
    label: str,
) -> Prediction:
    key = _prediction_evidence_key(value, label)
    if key not in cache:
        cache[key] = Prediction(
            np.asarray([[len(cache)]], dtype=np.int16),
            GameState(key[3]),
            key[4],
            {},
        )
    return cache[key]


def _expected_controller_trace(
    selection: ActionQBCSelection,
    variant: Variant,
) -> dict[str, JsonValue]:
    authoritative = (
        selection.m_decision if variant is Variant.MYOPIC else selection.x_decision
    )
    candidate_rows = _controller_candidate_rows(selection)
    probe_row = next(
        (
            row
            for row in selection.rows
            if row.action == authoritative.probe_candidate
        ),
        None,
    )
    trace: dict[str, JsonValue] = {
        "candidate_rows": candidate_rows,
        "m_decision_action": _controller_action_key(selection.m_decision.action),
        "m_decision_mode": selection.m_decision.mode,
        "m_utility_maximizers": [
            _controller_action_record(action)
            for action in selection.m_utility_maximizers
        ],
        "probe_candidate_action": (
            None
            if authoritative.probe_candidate is None
            else _controller_action_key(authoritative.probe_candidate)
        ),
        "probe_cap": MAX_PROBES_PER_LEVEL,
        "probe_catastrophe_probability": (
            None if probe_row is None else probe_row.catastrophe_mass
        ),
        "probe_count_before": 0,
        "probe_evsi": None if probe_row is None else probe_row.evsi,
        "probe_gate_reason": authoritative.gate_reason,
        "probe_selected": authoritative.mode == "probe",
        "probe_utility": (
            None
            if probe_row is None
            else (
                probe_row.m_utility
                if variant is Variant.MYOPIC
                else probe_row.x_utility
            )
        ),
        "x_decision_action": _controller_action_key(selection.x_decision.action),
        "x_decision_mode": selection.x_decision.mode,
        "x_utility_maximizers": [
            _controller_action_record(action)
            for action in selection.x_utility_maximizers
        ],
    }
    return {
        "action": _action_json(authoritative.action),
        "candidate_rows_sha256": canonical_sha256(candidate_rows),
        "decision_mode": authoritative.mode,
        "implementation_contract_version": ACTION_QBC_RUNTIME_VERSION,
        "probe_disagreement_policy_sha256": ACTION_QBC_POLICY_SHA256,
        "probe_disagreement_policy_version": ACTION_QBC_POLICY_VERSION,
        "replay_calls": 1,
        "selector_trace_sha256": canonical_sha256(trace),
        "variant": variant.value,
    }


@dataclass(frozen=True, slots=True)
class _RevalidatedPipelineEvidence:
    snapshot: PlanningSnapshot
    selection: ActionQBCSelection
    actions: tuple[Action, ...]
    source_roles: tuple[str, ...]
    program_rows: tuple[Mapping[str, Any], ...]
    persistent_worker_rows: tuple[Mapping[str, Any], ...]
    prediction_keys: Mapping[Action, tuple[_PredictionEvidenceKey, ...]]


def _validate_worker_memory_evidence(value: object, *, persistent: bool) -> None:
    keys = {
        "allocation_headroom_bytes",
        "diagnostic",
        "hard_limit_enforced",
        "limit_kind",
    }
    if persistent:
        keys.add("hypothesis_id")
    row = _exact_mapping(value, keys, "worker-memory evidence")
    if persistent and not isinstance(row["hypothesis_id"], str):
        raise ValueError("persistent worker evidence lacks a hypothesis id")
    if not isinstance(row["hard_limit_enforced"], bool):
        raise ValueError("worker hard-limit evidence is not boolean")
    if row["limit_kind"] is not None and not isinstance(row["limit_kind"], str):
        raise ValueError("worker limit-kind evidence is malformed")
    headroom = row["allocation_headroom_bytes"]
    if headroom is not None and (
        isinstance(headroom, bool) or not isinstance(headroom, int) or headroom < 0
    ):
        raise ValueError("worker headroom evidence is malformed")
    if row["diagnostic"] is not None and not isinstance(row["diagnostic"], str):
        raise ValueError("worker diagnostic evidence is malformed")


def _validate_pipeline_evidence(
    value: object,
    *,
    expect_controller_rows: bool,
) -> _RevalidatedPipelineEvidence:
    pipeline = _exact_mapping(
        value,
        {
            "actions",
            "candidate_set_sha256",
            "controller_rows",
            "history_sha256",
            "persistent_worker_rows",
            "planning",
            "program_rows",
            "selection",
            "source_manifest",
            "source_roles",
        },
        "completed pipeline evidence",
    )
    raw_actions = pipeline["actions"]
    if not isinstance(raw_actions, list) or not 2 <= len(raw_actions) <= 12:
        raise ValueError("pipeline action inventory is malformed")
    actions = tuple(
        _decode_action_evidence(item, f"pipeline action {index}")
        for index, item in enumerate(raw_actions)
    )
    if len(set(actions)) != len(actions):
        raise ValueError("pipeline actions are not unique")
    _require_json_equal(
        pipeline["candidate_set_sha256"],
        canonical_sha256([_action_json(action) for action in actions]),
        "candidate-set digest",
    )
    if not _is_lower_hex(pipeline["history_sha256"], 64):
        raise ValueError("pipeline history digest is malformed")

    planning = _exact_mapping(
        pipeline["planning"],
        {"hypothesis_ids", "invalid_hypothesis_ids", "rows", "weights"},
        "planning evidence",
    )
    hypothesis_ids = planning["hypothesis_ids"]
    invalid_ids = planning["invalid_hypothesis_ids"]
    weights = planning["weights"]
    planning_rows = planning["rows"]
    if (
        not isinstance(hypothesis_ids, list)
        or len(hypothesis_ids) != 4
        or any(not isinstance(item, str) or not item for item in hypothesis_ids)
        or len(set(hypothesis_ids)) != 4
    ):
        raise ValueError("planning hypothesis identities are malformed")
    if (
        not isinstance(invalid_ids, list)
        or any(not isinstance(item, str) for item in invalid_ids)
    ):
        raise ValueError("planning invalid-hypothesis inventory is malformed")
    if not isinstance(weights, list) or len(weights) != 4:
        raise ValueError("planning weights are malformed")
    numeric_weights = tuple(_finite_number(item, "planning weight") for item in weights)
    if any(item < 0.0 for item in numeric_weights) or sum(numeric_weights) <= 0.0:
        raise ValueError("planning weights lack positive nonnegative mass")
    if not isinstance(planning_rows, list) or len(planning_rows) != len(actions):
        raise ValueError("planning rows do not cover the candidate actions")
    prediction_cache: dict[_PredictionEvidenceKey, Prediction] = {}
    predictions: dict[Action, tuple[Prediction | None, ...]] = {}
    prediction_keys: dict[Action, tuple[_PredictionEvidenceKey, ...]] = {}
    costs: dict[Action, tuple[float, ...]] = {}
    for index, (action, raw_row) in enumerate(
        zip(actions, planning_rows, strict=True)
    ):
        row = _exact_mapping(
            raw_row,
            {"action", "costs", "predictions"},
            f"planning row {index}",
        )
        if _decode_action_evidence(row["action"], f"planning row {index} action") != action:
            raise ValueError("planning row action differs from candidate order")
        raw_costs = row["costs"]
        raw_predictions = row["predictions"]
        if (
            not isinstance(raw_costs, list)
            or len(raw_costs) != 4
            or not isinstance(raw_predictions, list)
            or len(raw_predictions) != 4
        ):
            raise ValueError("planning row does not cover the four hypotheses")
        costs[action] = tuple(
            _finite_number(item, f"planning row {index} cost")
            for item in raw_costs
        )
        predictions[action] = tuple(
            _decode_prediction_evidence(
                item,
                cache=prediction_cache,
                label=f"planning row {index} prediction {prediction_index}",
            )
            for prediction_index, item in enumerate(raw_predictions)
        )
        prediction_keys[action] = tuple(
            _prediction_evidence_key(
                item,
                f"planning row {index} prediction {prediction_index}",
            )
            for prediction_index, item in enumerate(raw_predictions)
        )
    snapshot = PlanningSnapshot(
        actions=actions,
        hypothesis_ids=tuple(cast(list[str], hypothesis_ids)),
        weights=numeric_weights,
        predictions=predictions,
        costs=costs,
        invalid_hypothesis_ids=tuple(cast(list[str], invalid_ids)),
    )
    selection = ACTION_QBC_AUDIT_SELECTOR(
        snapshot,
        cross_level_multiplier=23.0,
        probes_used=0,
        probe_cap=MAX_PROBES_PER_LEVEL,
    )
    _require_json_equal(
        pipeline["selection"],
        _selection_json(selection),
        "pipeline selection",
    )

    source_roles = pipeline["source_roles"]
    source_manifest = pipeline["source_manifest"]
    if source_roles != list(STRUCTURED_PRIOR_ROLES):
        raise ValueError("pipeline source roles differ from the frozen compiler roles")
    if not isinstance(source_manifest, list) or len(source_manifest) != 4:
        raise ValueError("pipeline source manifest is malformed")
    for index, item in enumerate(source_manifest):
        row = _exact_mapping(
            item,
            {"bindings_sha256", "evidence_sha256", "role", "source_sha256"},
            f"source manifest row {index}",
        )
        if row["role"] != STRUCTURED_PRIOR_ROLES[index] or any(
            not _is_lower_hex(row[name], 64)
            for name in ("bindings_sha256", "evidence_sha256", "source_sha256")
        ):
            raise ValueError("pipeline source manifest identity is malformed")

    raw_programs = pipeline["program_rows"]
    if not isinstance(raw_programs, list) or len(raw_programs) != 4:
        raise ValueError("pipeline program evidence is malformed")
    programs: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw_programs):
        row = _exact_mapping(
            item,
            {
                "all_actions_ok",
                "assigned_role",
                "ast_nodes",
                "behavior_signature",
                "candidate_index",
                "eligible",
                "goal_value_ok",
                "grounding_worker_memory",
                "hypothesis_id",
                "palette_conflicts",
                "sandbox_valid",
                "selected",
            },
            f"program row {index}",
        )
        if (
            row["candidate_index"] != index
            or row["assigned_role"] != STRUCTURED_PRIOR_ROLES[index]
            or row["hypothesis_id"] != hypothesis_ids[index]
            or any(
                row[name] is not True
                for name in (
                    "all_actions_ok",
                    "eligible",
                    "goal_value_ok",
                    "sandbox_valid",
                    "selected",
                )
            )
            or isinstance(row["ast_nodes"], bool)
            or not isinstance(row["ast_nodes"], int)
            or row["ast_nodes"] <= 0
            or row["palette_conflicts"] != 0
        ):
            raise ValueError("program row differs from the four safe selected roles")
        canonical_json_bytes(cast(JsonValue, row["behavior_signature"]))
        _validate_worker_memory_evidence(
            row["grounding_worker_memory"],
            persistent=False,
        )
        programs.append(row)

    raw_persistent = pipeline["persistent_worker_rows"]
    if not isinstance(raw_persistent, list) or len(raw_persistent) != 4:
        raise ValueError("persistent-worker evidence is malformed")
    persistent_rows: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw_persistent):
        _validate_worker_memory_evidence(item, persistent=True)
        row = cast(Mapping[str, Any], item)
        if row["hypothesis_id"] != hypothesis_ids[index]:
            raise ValueError("persistent-worker identity differs from planning order")
        persistent_rows.append(row)

    raw_controllers = pipeline["controller_rows"]
    if not isinstance(raw_controllers, list):
        raise ValueError("controller replay evidence is not a list")
    expected_controllers = (
        [
            _expected_controller_trace(selection, Variant.MYOPIC),
            _expected_controller_trace(selection, Variant.CROSS_LEVEL),
        ]
        if expect_controller_rows
        else []
    )
    _require_json_equal(
        raw_controllers,
        cast(JsonValue, expected_controllers),
        "controller replay evidence",
    )
    return _RevalidatedPipelineEvidence(
        snapshot=snapshot,
        selection=selection,
        actions=actions,
        source_roles=tuple(cast(list[str], source_roles)),
        program_rows=tuple(programs),
        persistent_worker_rows=tuple(persistent_rows),
        prediction_keys=MappingProxyType(prediction_keys),
    )


def _structural_gate_from_evidence(
    evidence: _RevalidatedPipelineEvidence,
) -> dict[str, JsonValue]:
    reasons: list[str] = []
    programs = evidence.program_rows
    selected = tuple(row for row in programs if row["selected"] is True)
    if len(programs) != 4 or any(row["eligible"] is not True for row in programs):
        reasons.append("exactly four safe valid compiler programs were not supplied")
    behavior_signatures = {
        json.dumps(row["behavior_signature"], sort_keys=True, default=str)
        for row in selected
    }
    if len(selected) != 4 or len(behavior_signatures) != 4:
        reasons.append("four behaviorally distinct programs did not survive")
    varying_roles = 0
    for index in range(1, min(4, len(evidence.snapshot.hypothesis_ids))):
        role_costs = [
            float(evidence.snapshot.costs[action][index])
            for action in evidence.actions
        ]
        if max(role_costs) - min(role_costs) > 1e-12:
            varying_roles += 1
    if varying_roles < 2:
        reasons.append("fewer than two graded roles have action-varying depth-four costs")
    if evidence.snapshot.invalid_hypothesis_ids:
        reasons.append("one or more selected programs became invalid during planning")
    if not 2 <= len(evidence.actions) <= 12:
        reasons.append("candidate count does not provide two bounded exploitation candidates")
    if len(evidence.snapshot.weights) != 4:
        reasons.append("shared filtered snapshot does not contain exactly four weights")
    grounding_memory = [
        cast(Mapping[str, Any], row["grounding_worker_memory"])
        for row in programs
    ]
    persistent_memory = list(evidence.persistent_worker_rows)
    if len(grounding_memory) != 4 or len(persistent_memory) != 4:
        reasons.append("worker telemetry does not cover four transient and persistent workers")
    memory_ok = all(
        _worker_memory_valid(row)
        for row in (*grounding_memory, *persistent_memory)
    )
    if not memory_ok:
        reasons.append("one or more workers lack exact +256 MiB RLIMIT_DATA headroom")
    shared_gate = _admission_resource_gate(
        AdmissionResourceSignals(
            invalid_programs=len(evidence.snapshot.invalid_hypothesis_ids),
            eligible_graded_roles=varying_roles,
            worker_memory_ok=memory_ok,
        )
    )
    reasons.extend(cast(list[str], shared_gate["reasons"]))
    return {
        "admission_resource_gate": shared_gate,
        "graded_action_varying_roles": varying_roles,
        "passes": not reasons,
        "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
        "require_linux_memory": True,
        "selected_distinct_programs": len(behavior_signatures),
        "selected_programs": len(selected),
    }


def _map_registered_visual_action(name: str, action: Action) -> Action:
    if action.kind is not ActionKind.ACTION6:
        return action
    assert action.row is not None and action.col is not None
    if name == "palette_bijection":
        return action
    if name == "translation_row_plus_3_col_plus_5":
        return Action(ActionKind.ACTION6, action.row + 3, action.col + 5)
    if name == "translation_row_minus_3_col_minus_5":
        return Action(ActionKind.ACTION6, action.row - 3, action.col - 5)
    if name == "scale_2_nearest_neighbor":
        return Action(ActionKind.ACTION6, action.row * 2, action.col * 2)
    raise ValueError("visual record has an unknown registered transform")


def _compare_visual_evidence(
    base: _RevalidatedPipelineEvidence,
    transformed: _RevalidatedPipelineEvidence,
    *,
    transform_name: str,
) -> dict[str, JsonValue]:
    mapped_actions = tuple(
        _map_registered_visual_action(transform_name, action)
        for action in base.actions
    )
    reasons: list[str] = []
    if mapped_actions != transformed.actions:
        reasons.append("mapped base actions differ from transformed action order/frontier")
    if base.source_roles != transformed.source_roles:
        reasons.append("compiler roles differ under visual transform")
    if any(
        not isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(
            base.snapshot.weights,
            transformed.snapshot.weights,
            strict=True,
        )
    ):
        reasons.append("Gibbs weights differ under visual transform")
    for base_action, mapped_action in zip(base.actions, mapped_actions, strict=True):
        if mapped_action not in transformed.snapshot.costs:
            continue
        base_keys = base.prediction_keys[base_action]
        transformed_keys = transformed.prediction_keys[mapped_action]
        for index in range(len(base.snapshot.hypothesis_ids)):
            if not isclose(
                float(base.snapshot.costs[base_action][index]),
                float(transformed.snapshot.costs[mapped_action][index]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                reasons.append("rolewise costs differ under visual transform")
                break
            base_key = base_keys[index]
            transformed_key = transformed_keys[index]
            expected_shape = (
                (base_key[1] * 2, base_key[2] * 2)
                if transform_name == "scale_2_nearest_neighbor"
                else (base_key[1], base_key[2])
            )
            if (
                (transformed_key[1], transformed_key[2]) != expected_shape
                or base_key[3:] != transformed_key[3:]
            ):
                reasons.append("mapped prediction differs under visual transform")
                break
        base_partition = tuple(
            tuple(base_keys[left] == base_keys[right] for right in range(4))
            for left in range(4)
        )
        transformed_partition = tuple(
            tuple(
                transformed_keys[left] == transformed_keys[right]
                for right in range(4)
            )
            for left in range(4)
        )
        if base_partition != transformed_partition:
            reasons.append("mapped prediction differs under visual transform")
    base_rows = _selection_by_action(base.selection)
    transformed_rows = _selection_by_action(transformed.selection)
    numeric_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    exact_fields = (
        "outcome_cell_count",
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
    )
    for base_action, mapped_action in zip(base.actions, mapped_actions, strict=True):
        if mapped_action not in transformed_rows:
            continue
        left = base_rows[base_action]
        right = transformed_rows[mapped_action]
        if any(
            not isclose(
                float(getattr(left, field_name)),
                float(getattr(right, field_name)),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for field_name in numeric_fields
        ):
            reasons.append("selector numeric diagnostics differ under visual transform")
        if any(
            getattr(left, field_name) != getattr(right, field_name)
            for field_name in exact_fields
        ):
            reasons.append("selector disposition/ranks differ under visual transform")
    for left_decision, right_decision in (
        (base.selection.m_decision, transformed.selection.m_decision),
        (base.selection.x_decision, transformed.selection.x_decision),
    ):
        mapped_probe = (
            None
            if left_decision.probe_candidate is None
            else _map_registered_visual_action(
                transform_name, left_decision.probe_candidate
            )
        )
        if (
            _map_registered_visual_action(transform_name, left_decision.action)
            != right_decision.action
            or mapped_probe != right_decision.probe_candidate
            or left_decision.mode != right_decision.mode
            or left_decision.gate_reason != right_decision.gate_reason
            or not isclose(
                left_decision.score,
                right_decision.score,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            reasons.append("mapped M/X decision differs under visual transform")
    action_sets = (
        (
            "robust exploitation",
            _exploit_minimizers(base.selection),
            _exploit_minimizers(transformed.selection),
        ),
        (
            "M utility maximizer",
            base.selection.m_utility_maximizers,
            transformed.selection.m_utility_maximizers,
        ),
        (
            "X utility maximizer",
            base.selection.x_utility_maximizers,
            transformed.selection.x_utility_maximizers,
        ),
    )
    for label, left_actions, right_actions in action_sets:
        mapped = {
            _map_registered_visual_action(transform_name, action)
            for action in left_actions
        }
        if mapped != set(right_actions):
            reasons.append(f"mapped {label} action set differs under visual transform")
    if (
        _map_registered_visual_action(transform_name, base.selection.exploit.action)
        != transformed.selection.exploit.action
        or not isclose(
            base.selection.exploit.mean_cost,
            transformed.selection.exploit.mean_cost,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.standard_deviation,
            transformed.selection.exploit.standard_deviation,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not isclose(
            base.selection.exploit.score,
            transformed.selection.exploit.score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    ):
        reasons.append("mapped robust-exploitation result differs under visual transform")
    return {
        "base_selection": _selection_json(base.selection),
        "frontier_mode": (
            "fixed_mapped_base_action_list_only"
            if transform_name == "scale_2_nearest_neighbor"
            else "regenerate_complete_frontier"
        ),
        "mapped_actions": [_action_json(action) for action in mapped_actions],
        "mapped_action_count": len(mapped_actions),
        "passes": not reasons,
        "reasons": cast(JsonValue, list(dict.fromkeys(reasons))),
        "transform": transform_name,
        "transformed_selection": _selection_json(transformed.selection),
    }


def _validate_failure_payload(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) not in (
        {"stage"},
        {"error_type", "stage"},
    ):
        raise ValueError(f"{label} has a noncanonical failure schema")
    stage = value.get("stage")
    error_type = value.get("error_type")
    if not isinstance(stage, str) or not stage:
        raise ValueError(f"{label} has an invalid failure stage")
    if "error_type" in value and (
        not isinstance(error_type, str) or not error_type
    ):
        raise ValueError(f"{label} has an invalid failure class")
    return cast(Mapping[str, Any], value)


def _failed_pipeline_stage(value: object) -> str | None:
    if not isinstance(value, Mapping) or value.get("status") != "failed":
        return None
    row = _exact_mapping(value, {"failure", "status"}, "failed pipeline evidence")
    failure = _validate_failure_payload(row["failure"], "pipeline failure")
    return cast(str, failure["stage"])


def _require_failed_gate(
    value: object,
    *,
    expected_failure: Mapping[str, Any],
    label: str,
) -> None:
    gate = _exact_mapping(value, {"failure", "passes", "reasons"}, label)
    failure = _validate_failure_payload(gate["failure"], f"{label} failure")
    expected_stage = cast(str, expected_failure["stage"])
    if (
        gate["passes"] is not False
        or gate["reasons"] != [expected_stage]
        or failure != expected_failure
    ):
        raise ValueError(f"{label} is not the exact fail-closed gate")


def _prediction_cells_from_evidence(
    evidence: _RevalidatedPipelineEvidence,
) -> list[dict[str, JsonValue]]:
    normalized = tuple(normalise_gibbs_weights(evidence.snapshot.weights))
    rows: list[dict[str, JsonValue]] = []
    for action in evidence.actions:
        keys = evidence.prediction_keys[action]
        grouped: dict[_PredictionEvidenceKey, list[int]] = {}
        for index, key in enumerate(keys):
            grouped.setdefault(key, []).append(index)
        cells: list[JsonValue] = []
        for key, indices in grouped.items():
            prediction_json: JsonValue = {
                "game_state": key[3],
                "grid_bytes_sha256": key[0],
                "grid_shape": [key[1], key[2]],
                "level_delta": key[4],
            }
            cells.append(
                {
                    "hypothesis_indices": cast(JsonValue, indices),
                    "hypothesis_roles": [
                        evidence.source_roles[index] for index in indices
                    ],
                    "mass": sum(normalized[index] for index in indices),
                    "signature_sha256": canonical_sha256(prediction_json),
                }
            )
        rows.append({"action": _action_json(action), "cells": cells})
    return rows


_BOUND_RECORD_KEYS: Final = {"registered_row", "row_id", "row_index"}
_SCENE_RECORD_KEYS: Final = {
    "family",
    "family_index",
    "kind",
    "scene_content_sha256",
    "scene_id",
}


def _validate_base_record_evidence(
    record: Mapping[str, Any],
) -> _RevalidatedPipelineEvidence | None:
    _exact_mapping(
        record,
        _BOUND_RECORD_KEYS
        | _SCENE_RECORD_KEYS
        | {
            "causal_exercise",
            "mechanism_gate",
            "pipeline",
            "positive_mechanism",
            "structural_gate",
            "v4_counterfactual",
        },
        "base scientific record",
    )
    pipeline_stage = _failed_pipeline_stage(record["pipeline"])
    if pipeline_stage is not None:
        pipeline = cast(Mapping[str, Any], record["pipeline"])
        pipeline_failure = _validate_failure_payload(
            pipeline["failure"], "base pipeline failure"
        )
        _require_failed_gate(
            record["structural_gate"],
            expected_failure=pipeline_failure,
            label="base structural gate",
        )
        _require_failed_gate(
            record["mechanism_gate"],
            expected_failure=pipeline_failure,
            label="base mechanism gate",
        )
        v4 = _exact_mapping(
            record["v4_counterfactual"],
            {"causal_exercise", "failure", "passes"},
            "failed v4 counterfactual",
        )
        v4_failure = _validate_failure_payload(v4["failure"], "v4 failure")
        if (
            v4["causal_exercise"] is not False
            or v4["passes"] is not False
            or v4_failure != pipeline_failure
            or record["positive_mechanism"] is not False
            or record["causal_exercise"] is not False
        ):
            raise ValueError("failed base row contains a positive derived conclusion")
        return None
    evidence = _validate_pipeline_evidence(
        record["pipeline"],
        expect_controller_rows=True,
    )
    structural = _structural_gate_from_evidence(evidence)
    mechanism = _mechanism_gate(evidence.selection, probe_cap_available=True)
    v4 = _v4_counterfactual_from_evidence(
        evidence.snapshot,
        evidence.selection,
        structural_passes=structural["passes"] is True,
        probe_cap_available=True,
    )
    positive = structural["passes"] is True and mechanism["passes"] is True
    causal = positive and v4["causal_exercise"] is True
    _require_json_equal(record["structural_gate"], structural, "base structural gate")
    _require_json_equal(record["mechanism_gate"], mechanism, "base mechanism gate")
    _require_json_equal(record["v4_counterfactual"], v4, "base v4 counterfactual")
    if record["positive_mechanism"] is not positive:
        raise ValueError("base positive_mechanism differs from its gates")
    if record["causal_exercise"] is not causal:
        raise ValueError("base causal_exercise differs from mechanism/v4 evidence")
    return evidence


def _validate_visual_record_evidence(
    record: Mapping[str, Any],
    *,
    base: _RevalidatedPipelineEvidence | None,
) -> _RevalidatedPipelineEvidence | None:
    _exact_mapping(
        record,
        _BOUND_RECORD_KEYS
        | _SCENE_RECORD_KEYS
        | {
            "comparison",
            "grid_sha256",
            "pipeline",
            "structural_gate",
            "transform_content_sha256",
            "transform_index",
            "transform_name",
        },
        "visual scientific record",
    )
    transform_index = record["transform_index"]
    transform_name = record["transform_name"]
    if (
        isinstance(transform_index, bool)
        or not isinstance(transform_index, int)
        or not 0 <= transform_index < len(SEALED_VISUAL_TRANSFORM_NAMES)
        or transform_name != SEALED_VISUAL_TRANSFORM_NAMES[transform_index]
        or not _is_lower_hex(record["grid_sha256"], 64)
        or not _is_lower_hex(record["transform_content_sha256"], 64)
    ):
        raise ValueError("visual transform identity/evidence is malformed")
    pipeline_stage = _failed_pipeline_stage(record["pipeline"])
    if pipeline_stage is not None:
        pipeline = cast(Mapping[str, Any], record["pipeline"])
        pipeline_failure = _validate_failure_payload(
            pipeline["failure"], "visual pipeline failure"
        )
        _require_failed_gate(
            record["structural_gate"],
            expected_failure=pipeline_failure,
            label="visual structural gate",
        )
        _require_failed_gate(
            record["comparison"],
            expected_failure=pipeline_failure,
            label="visual comparison",
        )
        return None
    evidence = _validate_pipeline_evidence(
        record["pipeline"],
        expect_controller_rows=transform_index != 3,
    )
    structural = _structural_gate_from_evidence(evidence)
    _require_json_equal(
        record["structural_gate"],
        structural,
        "visual structural gate",
    )
    if base is None:
        expected_failure: Mapping[str, Any] = {"stage": "base_pipeline_unavailable"}
        _require_failed_gate(
            record["comparison"],
            expected_failure=expected_failure,
            label="visual comparison",
        )
    else:
        comparison = _compare_visual_evidence(
            base,
            evidence,
            transform_name=cast(str, transform_name),
        )
        _require_json_equal(record["comparison"], comparison, "visual comparison")
    return evidence


def _registered_order_permutation_from_name(name: str, length: int) -> tuple[int, ...]:
    if name in {
        "candidate_list_reversal",
        "hypothesis_list_reversal",
        "serialized_outcome_cell_order_reversal",
    }:
        return tuple(reversed(range(length)))
    if name in {
        "candidate_list_left_rotation_by_one",
        "hypothesis_list_left_rotation_by_one",
    }:
        return tuple((*range(1, length), 0))
    raise ValueError("order record has an unknown registered transform")


def _validate_order_record_evidence(
    record: Mapping[str, Any],
    *,
    base: _RevalidatedPipelineEvidence | None,
    base_positive: bool,
) -> None:
    common = _BOUND_RECORD_KEYS | _SCENE_RECORD_KEYS | {
        "name",
        "order_index",
        "passes",
        "reasons",
    }
    name = record.get("name")
    order_index = record.get("order_index")
    if (
        isinstance(order_index, bool)
        or not isinstance(order_index, int)
        or not 0 <= order_index < len(ORDER_TRANSFORM_NAMES)
        or name != ORDER_TRANSFORM_NAMES[order_index]
    ):
        raise ValueError("order-transform identity is malformed")
    if "failure" in record:
        allowed = common | {"failure"}
        if order_index < 4 and "permutation" in record:
            allowed.add("permutation")
        _exact_mapping(record, allowed, "failed order-transform record")
        failure = _validate_failure_payload(record["failure"], "order failure")
        stage = failure["stage"]
        if record["passes"] is not False or record["reasons"] != [stage]:
            raise ValueError("failed order-transform row claims a pass")
        if "permutation" in record:
            length = (
                len(base.actions)
                if base is not None and order_index < 2
                else len(base.snapshot.hypothesis_ids) if base is not None else 0
            )
            if base is not None:
                _require_json_equal(
                    record["permutation"],
                    list(_registered_order_permutation_from_name(cast(str, name), length)),
                    "failed order permutation",
                )
        return
    if base is None:
        raise ValueError("successful order-transform row lacks a completed base pipeline")
    if order_index < 4:
        _exact_mapping(
            record,
            common | {"permutation", "selection"},
            "completed order-transform record",
        )
        if order_index < 2:
            permutation = _registered_order_permutation_from_name(
                cast(str, name), len(base.actions)
            )
            snapshot = _candidate_permutation(base.snapshot, permutation)
            require_order_relative = base_positive
        else:
            permutation = _registered_order_permutation_from_name(
                cast(str, name), len(base.snapshot.hypothesis_ids)
            )
            snapshot = _permute_hypotheses(base.snapshot, permutation)
            require_order_relative = True
        selection = ACTION_QBC_AUDIT_SELECTOR(
            snapshot,
            cross_level_multiplier=23.0,
            probes_used=0,
            probe_cap=MAX_PROBES_PER_LEVEL,
        )
        reasons = list(
            _selection_invariant_by_action(
                base.selection,
                selection,
                require_order_relative_fields=require_order_relative,
            )
        )
        if order_index < 2 and base_positive and (
            selection.m_decision.action != base.selection.m_decision.action
            or selection.x_decision.action != base.selection.x_decision.action
        ):
            reasons.append("unique positive-row decision changed under candidate order")
        if order_index >= 2 and (
            selection.m_decision.action != base.selection.m_decision.action
            or selection.x_decision.action != base.selection.x_decision.action
        ):
            reasons.append("mapped decision changed under hypothesis permutation")
        reasons = list(dict.fromkeys(reasons))
        _require_json_equal(record["permutation"], list(permutation), "order permutation")
        _require_json_equal(record["selection"], _selection_json(selection), "order selection")
        if record["reasons"] != reasons or record["passes"] is not (not reasons):
            raise ValueError("order-transform pass/reasons differ from rederivation")
        return
    _exact_mapping(
        record,
        common
        | {
            "forward_cells_sha256",
            "policy_input_transform_applied",
            "reversed_cells_sha256",
            "selection",
            "transformed_cells",
        },
        "completed outcome-cell order record",
    )
    cells = _prediction_cells_from_evidence(base)
    reversed_cells: list[JsonValue] = []
    for row in cells:
        row_cells = cast(list[JsonValue], row["cells"])
        reversed_cells.append({**row, "cells": list(reversed(row_cells))})
    expected_selection = _selection_json(base.selection)
    expected_reasons: list[str] = []
    _require_json_equal(record["selection"], expected_selection, "cell-order selection")
    _require_json_equal(record["transformed_cells"], reversed_cells, "reversed cells")
    if record["forward_cells_sha256"] != canonical_sha256(cast(JsonValue, cells)):
        raise ValueError("forward outcome-cell digest differs from primitive evidence")
    if record["reversed_cells_sha256"] != canonical_sha256(
        cast(JsonValue, reversed_cells)
    ):
        raise ValueError("reversed outcome-cell digest differs from primitive evidence")
    if record["policy_input_transform_applied"] is not True:
        raise ValueError("outcome-cell policy-input transform was not recorded")
    if record["reasons"] != expected_reasons or record["passes"] is not True:
        raise ValueError("outcome-cell order pass/reasons differ from rederivation")


def _validate_control_record_evidence(
    record: Mapping[str, Any],
    *,
    control_index: int,
) -> None:
    common = _BOUND_RECORD_KEYS | {"kind", "name", "observed", "passes"}
    if record.get("name") != PREREGISTERED_CONTROL_ORDER[control_index]:
        raise ValueError("control identity differs from preregistration")
    if "failure" in record:
        expected_key = (
            "expected_gate_semantics"
            if "expected_gate_semantics" in record
            else "expected"
        )
        _exact_mapping(
            record,
            common | {"failure", expected_key},
            "failed control record",
        )
        failure = _validate_failure_payload(record["failure"], "control failure")
        expected_text = (
            "registered control row completes"
            if expected_key == "expected_gate_semantics"
            else "registered control evaluates without an exception"
        )
        if (
            record["passes"] is not False
            or record["observed"] != failure
            or record[expected_key] != expected_text
        ):
            raise ValueError("failed control row claims a pass or mismatched failure")
        return
    _exact_mapping(
        record,
        common | {"expected_gate_semantics"},
        "completed control record",
    )
    counters = AuditCounterState()
    expected = {"kind": "control", **_evaluate_preregistered_control(control_index, counters)}
    for key in _BOUND_RECORD_KEYS:
        expected[key] = cast(JsonValue, record[key])
    _require_json_equal(record, cast(JsonValue, expected), "control record")


def validate_and_rederive_scientific_records(
    records: Sequence[Mapping[str, Any]],
    registration_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, JsonValue]]:
    """Bind, exact-schema validate, and rederive all 140 scientific rows."""

    raw_records = [dict(record) for record in records]
    bound = _bind_registered_row_inventory(
        cast(Sequence[dict[str, JsonValue]], raw_records),
        registration_rows,
    )
    _require_json_equal(raw_records, cast(JsonValue, bound), "bound scientific inventory")
    bases = [row for row in bound if row["kind"] == "base_scene"]
    visuals = [row for row in bound if row["kind"] == "visual_transform"]
    orders = [row for row in bound if row["kind"] == "order_transform"]
    controls = [row for row in bound if row["kind"] == "control"]
    base_evidence: dict[tuple[str, int], _RevalidatedPipelineEvidence | None] = {}
    base_positive: dict[tuple[str, int], bool] = {}
    for row in bases:
        evidence = _validate_base_record_evidence(row)
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        base_evidence[key] = evidence
        base_positive[key] = row["positive_mechanism"] is True
    for row in visuals:
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        _validate_visual_record_evidence(row, base=base_evidence[key])
    for row in orders:
        key = (cast(str, row["family"]), cast(int, row["family_index"]))
        _validate_order_record_evidence(
            row,
            base=base_evidence[key],
            base_positive=base_positive[key],
        )
    for index, row in enumerate(controls):
        _validate_control_record_evidence(row, control_index=index)
    return bound


@dataclass(slots=True)
class RegisteredEvaluationContext:
    """Pre-exposure state that guarantees a bound 140-row fallback inventory."""

    config: SystemConfig
    scenes: tuple[Mapping[str, Any], ...]
    order_maps: tuple[Mapping[str, Any], ...]
    accumulator: list[dict[str, JsonValue]]
    registration_only_records_raw: bytes
    accumulator_index: Mapping[ScientificRecordAddress, int]
    completed_indices: set[int]
    finalization_failures: list[dict[str, JsonValue]]
    deterministic_environment: dict[str, JsonValue]
    canonical_command_template: tuple[str, ...]
    lockbox_content_sha256: str
    provenance_json: dict[str, JsonValue]
    registration_preregistration: JsonValue
    registration_sha256: str
    deadline: float
    evaluation_started: bool = False


def _validated_registration_only_inventory(
    records: Sequence[Mapping[str, Any]],
    registration_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, JsonValue]],
    bytes,
    Mapping[ScientificRecordAddress, int],
]:
    """Authoritatively freeze the pristine negative inventory before exposure."""

    validated = validate_and_rederive_scientific_records(records, registration_rows)
    raw = canonical_json_bytes(cast(JsonValue, validated))
    return (
        validated,
        raw,
        MappingProxyType(_accumulator_index(validated)),
    )


def prepare_registered_evaluation_context(
    manifest: Mapping[str, Any],
    *,
    config: SystemConfig,
    provenance: AuditProvenance,
    canonical_command_template: Sequence[str],
    registration_rows: Sequence[Mapping[str, Any]],
    registration_preregistration: Mapping[str, Any],
    registration_sha256: str,
    started_monotonic: float,
) -> RegisteredEvaluationContext:
    """Validate the authorized manifest and bind its full negative-row inventory."""

    _validate_pipeline_config(config)
    deterministic_environment = _deterministic_environment_identity(provenance)
    deadline = started_monotonic + AUDIT_WALL_TIME_SECONDS
    scenes = manifest.get("scenes")
    order_maps = manifest.get("order_transform_maps")
    if not isinstance(scenes, list) or not isinstance(order_maps, list):
        raise ValueError("registered manifest lacks scenes/order maps")
    if len(scenes) != 12:
        raise ValueError("registered manifest must contain exactly twelve scenes")
    if not all(isinstance(item, Mapping) for item in order_maps):
        raise ValueError("registered order-map entry is not a mapping")
    typed_order_maps = tuple(cast(Mapping[str, Any], item) for item in order_maps)
    if len(typed_order_maps) != 5 or tuple(
        item.get("name") for item in typed_order_maps
    ) != ORDER_TRANSFORM_NAMES:
        raise ValueError("registered manifest must contain exactly five order maps")
    expected_scene_order = tuple(
        (family, family_index)
        for family in SEALED_SCENE_FAMILIES
        for family_index in range(4)
    )
    typed_scenes: list[Mapping[str, Any]] = []
    actual_scene_order: list[tuple[str, int]] = []
    for raw_scene in scenes:
        if not isinstance(raw_scene, Mapping):
            raise ValueError("registered scene entry is not a mapping")
        family, family_index, _scene_id = _scene_identity(raw_scene)
        actual_scene_order.append((family, family_index))
        if (
            raw_scene.get("generation_status") != "complete"
            or raw_scene.get("scope") != "registered"
            or not isinstance(raw_scene.get("base_scene"), Mapping)
            or not isinstance(raw_scene.get("visual_transforms"), list)
        ):
            raise ValueError("registered scene shape differs from the audit contract")
        visual_transforms = cast(list[object], raw_scene["visual_transforms"])
        if tuple(
            transform.get("name") if isinstance(transform, Mapping) else None
            for transform in visual_transforms
        ) != SEALED_VISUAL_TRANSFORM_NAMES or not all(
            isinstance(transform, Mapping)
            and isinstance(transform.get("action_map"), Mapping)
            for transform in visual_transforms
        ):
            raise ValueError("registered visual-transform shape differs from contract")
        base_scene = cast(Mapping[str, Any], raw_scene["base_scene"])
        _scene_history(base_scene, base_scene)
        for transform in visual_transforms:
            _scene_history(cast(Mapping[str, Any], transform), base_scene)
        typed_scenes.append(raw_scene)
    if tuple(actual_scene_order) != expected_scene_order:
        raise ValueError("registered scenes differ from family-major/index order")

    identity_records: list[dict[str, JsonValue]] = []
    for raw_scene in typed_scenes:
        family, family_index, scene_id = _scene_identity(raw_scene)
        scene_sha256 = cast(str, raw_scene.get("content_sha256"))
        identity_records.append(
            {
                "family": family,
                "family_index": family_index,
                "kind": "base_scene",
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
            }
        )
        for transform in cast(
            Sequence[Mapping[str, Any]], raw_scene["visual_transforms"]
        ):
            identity_records.append(
                {
                    "family": family,
                    "family_index": family_index,
                    "kind": "visual_transform",
                    "scene_content_sha256": scene_sha256,
                    "scene_id": scene_id,
                    "transform_name": cast(str, transform.get("name")),
                }
            )
        identity_records.extend(
            {
                "family": family,
                "family_index": family_index,
                "kind": "order_transform",
                "name": name,
                "scene_content_sha256": scene_sha256,
                "scene_id": scene_id,
            }
            for name in ORDER_TRANSFORM_NAMES
        )
    identity_records.extend(
        {"kind": "control", "name": name}
        for name in PREREGISTERED_CONTROL_ORDER
    )
    _bind_registered_row_inventory(identity_records, registration_rows)
    accumulator, registration_only_records_raw, accumulator_index = (
        _validated_registration_only_inventory(
            _bind_registered_row_inventory(
                _not_completed_record_inventory(typed_scenes),
                registration_rows,
            ),
            registration_rows,
        )
    )
    lockbox_content_sha256 = manifest.get("content_sha256")
    if not _is_lower_hex(lockbox_content_sha256, 64):
        raise ValueError("registered manifest content identity is malformed")
    if not _is_lower_hex(registration_sha256, 64):
        raise ValueError("registration SHA-256 is malformed")
    command = tuple(canonical_command_template)
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("canonical command template is malformed")
    return RegisteredEvaluationContext(
        config=config,
        scenes=tuple(typed_scenes),
        order_maps=typed_order_maps,
        accumulator=accumulator,
        registration_only_records_raw=registration_only_records_raw,
        accumulator_index=accumulator_index,
        completed_indices=set(),
        finalization_failures=[],
        deterministic_environment=deterministic_environment,
        canonical_command_template=command,
        lockbox_content_sha256=cast(str, lockbox_content_sha256),
        provenance_json=provenance.as_json(),
        registration_preregistration=cast(
            JsonValue, dict(registration_preregistration)
        ),
        registration_sha256=registration_sha256,
        deadline=deadline,
    )


def prepare_registered_fallback_context_from_registration(
    *,
    config: SystemConfig,
    provenance: AuditProvenance,
    canonical_command_template: Sequence[str],
    registration_rows: Sequence[Mapping[str, Any]],
    registration_preregistration: Mapping[str, Any],
    registration_sha256: str,
    started_monotonic: float,
) -> RegisteredEvaluationContext:
    """Bind all negative rows without resolving or reading the sealed manifest.

    The registration already freezes every scientific row address. This context
    consumes only those public addresses, so a failure after the durable exposure
    latch but during resolve/stat/open/read/parse can still emit 140 bound rows.
    """

    _validate_pipeline_config(config)
    if not _is_lower_hex(registration_sha256, 64):
        raise ValueError("registration SHA-256 is malformed")
    command = tuple(canonical_command_template)
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("canonical command template is malformed")
    base_rows = tuple(
        row for row in registration_rows if row.get("kind") == "base_scene"
    )
    expected_scene_order = tuple(
        (family, family_index)
        for family in SEALED_SCENE_FAMILIES
        for family_index in range(4)
    )
    if len(base_rows) != 12 or tuple(
        (row.get("family"), row.get("scene_index")) for row in base_rows
    ) != expected_scene_order:
        raise ValueError("registration base rows differ from family-major/index order")
    placeholder_sha256 = "0" * 64
    scenes: list[Mapping[str, Any]] = []
    for row in base_rows:
        scene_sha256 = row.get("fixture_sha256")
        if not _is_lower_hex(scene_sha256, 64):
            raise ValueError("registration scene identity is malformed")
        scenes.append(
            {
                "content_sha256": scene_sha256,
                "family": row["family"],
                "family_index": row["scene_index"],
                "visual_transforms": [
                    {
                        "content_sha256": placeholder_sha256,
                        "grid_sha256": placeholder_sha256,
                        "name": name,
                    }
                    for name in SEALED_VISUAL_TRANSFORM_NAMES
                ],
            }
        )
    accumulator, registration_only_records_raw, accumulator_index = (
        _validated_registration_only_inventory(
            _bind_registered_row_inventory(
                _not_completed_record_inventory(scenes),
                registration_rows,
            ),
            registration_rows,
        )
    )
    return RegisteredEvaluationContext(
        config=config,
        scenes=tuple(scenes),
        order_maps=(),
        accumulator=accumulator,
        registration_only_records_raw=registration_only_records_raw,
        accumulator_index=accumulator_index,
        completed_indices=set(),
        finalization_failures=[],
        deterministic_environment=_deterministic_environment_identity(provenance),
        canonical_command_template=command,
        lockbox_content_sha256=LOCKBOX_CONTENT_SHA256,
        provenance_json=provenance.as_json(),
        registration_preregistration=cast(
            JsonValue, dict(registration_preregistration)
        ),
        registration_sha256=registration_sha256,
        deadline=started_monotonic + AUDIT_WALL_TIME_SECONDS,
    )


def _registered_payload_from_context(
    context: RegisteredEvaluationContext,
    counters: AuditCounterState,
    acceptance: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    disposition = (
        "mechanism_capability_pass_pair_attestation_pending"
        if acceptance["acceptance_passes"] is True
        else "mechanism_capability_failed_runtime_v5_frozen"
    )
    return {
        "acceptance": cast(JsonValue, dict(acceptance)),
        "canonical_command_template": list(context.canonical_command_template),
        "deterministic_environment": context.deterministic_environment,
        "disposition": disposition,
        "duplicate_execution_is_independent_evidence": False,
        "finalization_failures": cast(JsonValue, context.finalization_failures),
        "lockbox_content_sha256": context.lockbox_content_sha256,
        "provenance": context.provenance_json,
        "registration_preregistration": context.registration_preregistration,
        "records": cast(JsonValue, context.accumulator),
        "registration_sha256": context.registration_sha256,
        "resource_counter_schema_sha256": AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256,
        "resource_counters": cast(JsonValue, counters.snapshot()),
        "schema_version": ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION,
    }


def _append_finalization_failure_once(
    context: RegisteredEvaluationContext,
    stage: str,
    error: Exception | None = None,
) -> None:
    failure = _deterministic_finalization_failure(stage, error)
    if failure not in context.finalization_failures:
        context.finalization_failures.append(failure)


def _authoritatively_revalidate_fallback_records(
    context: RegisteredEvaluationContext,
) -> None:
    """Retain completed rows only if the full inventory still rederives exactly."""

    pristine_value = json.loads(context.registration_only_records_raw)
    if not isinstance(pristine_value, list) or not all(
        isinstance(record, Mapping) for record in pristine_value
    ):
        raise RuntimeError("registration-only fallback inventory is malformed")
    pristine = [cast(dict[str, JsonValue], record) for record in pristine_value]
    registration_rows: list[Mapping[str, Any]] = []
    for record in pristine:
        registered_row = record.get("registered_row")
        if not isinstance(registered_row, Mapping):
            raise RuntimeError("registration-only fallback row lacks its registration")
        registration_rows.append(cast(Mapping[str, Any], registered_row))
    try:
        validated_current = validate_and_rederive_scientific_records(
            cast(Sequence[Mapping[str, Any]], context.accumulator),
            registration_rows,
        )
    except Exception as error:
        context.accumulator = pristine
        context.completed_indices.clear()
        _append_finalization_failure_once(
            context,
            "scientific_evidence_revalidation_failed",
            error,
        )
    else:
        context.accumulator = validated_current
        context.completed_indices.clear()
        context.completed_indices.update(
            index
            for index, (current, placeholder) in enumerate(
                zip(validated_current, pristine, strict=True)
            )
            if current != placeholder
        )
    context.accumulator_index = MappingProxyType(
        _accumulator_index(context.accumulator)
    )


def build_registered_evaluation_fallback(
    context: RegisteredEvaluationContext,
    counters: AuditCounterState,
    error: Exception,
    *,
    stage: str = "registered_scientific_phase_failed",
) -> dict[str, JsonValue]:
    """Finalize the prebound accumulator after any post-exposure escape."""

    if not counters.scientific_exposure_started:
        raise ValueError("registered fallback is forbidden before scientific exposure")
    _authoritatively_revalidate_fallback_records(context)
    _append_finalization_failure_once(context, stage, error)
    if len(context.completed_indices) != 140:
        _append_finalization_failure_once(context, "scientific_rows_not_completed")
    within_deadline = not isinstance(error, AuditWallTimeExceeded) and (
        time.monotonic() < context.deadline
    )
    try:
        acceptance = _aggregate_acceptance(
            context.accumulator,
            counters,
            finalization_complete=False,
            within_deadline=within_deadline,
        )
    except Exception as aggregation_error:
        _append_finalization_failure_once(
            context,
            "acceptance_aggregation_failed",
            aggregation_error,
        )
        acceptance = _negative_aggregate_acceptance(
            counters,
            within_deadline=within_deadline,
        )
    payload = _registered_payload_from_context(context, counters, acceptance)
    try:
        canonical_json_bytes(payload)
    except Exception as serialization_error:
        payload = build_emergency_negative_payload(payload, serialization_error)
    return payload


def _evaluate_registered_scientific_phase(
    context: RegisteredEvaluationContext,
    counters: AuditCounterState,
) -> dict[str, JsonValue]:
    accumulator = context.accumulator
    completed_indices = context.completed_indices
    finalization_failures = context.finalization_failures

    for raw_scene in context.scenes:
        counters.increment("registered_scenes_read")
        try:
            scene_records = evaluate_scene_record(
                raw_scene,
                config=context.config,
                counters=counters,
                order_transform_maps=context.order_maps,
                require_linux_memory=True,
                deadline=context.deadline,
            )
        except Exception as error:
            if not counters.scientific_exposure_started:
                raise
            scene_records = _failed_scene_records(
                raw_scene,
                stage="scene_evaluator_failed",
                error=error,
            )
        finalization_failures.extend(
            _accumulate_completed_records(
                accumulator,
                scene_records,
                index=context.accumulator_index,
                completed_indices=completed_indices,
            )
        )
    controls: tuple[dict[str, JsonValue], ...]
    if time.monotonic() >= context.deadline:
        failure = _deterministic_stage_failure("audit_wall_deadline_exceeded")
        controls = tuple(
            {
                "expected": "registered control evaluates without an exception",
                "failure": failure,
                "name": name,
                "observed": failure,
                "passes": False,
            }
            for name in PREREGISTERED_CONTROL_ORDER
        )
    else:
        try:
            controls = evaluate_preregistered_controls(
                counters,
                continue_after_failure=True,
            )
        except Exception as error:
            if not counters.scientific_exposure_started:
                raise
            failure = _deterministic_stage_failure("control_suite_failed", error)
            controls = tuple(
                {
                    "expected": "registered control evaluates without an exception",
                    "failure": failure,
                    "name": name,
                    "observed": failure,
                    "passes": False,
                }
                for name in PREREGISTERED_CONTROL_ORDER
            )
    finalization_failures.extend(
        _accumulate_completed_records(
            accumulator,
            tuple({"kind": "control", **record} for record in controls),
            index=context.accumulator_index,
            completed_indices=completed_indices,
        )
    )
    if len(completed_indices) != 140:
        finalization_failures.append(
            _deterministic_finalization_failure("scientific_rows_not_completed")
        )
    within_deadline = time.monotonic() < context.deadline
    try:
        acceptance = _aggregate_acceptance(
            accumulator,
            counters,
            finalization_complete=not finalization_failures,
            within_deadline=within_deadline,
        )
    except Exception as error:
        finalization_failures.append(
            _deterministic_finalization_failure(
                "acceptance_aggregation_failed",
                error,
            )
        )
        acceptance = _negative_aggregate_acceptance(
            counters,
            within_deadline=within_deadline,
        )
    payload = _registered_payload_from_context(context, counters, acceptance)
    try:
        canonical_json_bytes(payload)
    except Exception as error:
        payload = build_emergency_negative_payload(payload, error)
    return payload


def evaluate_registered_manifest(
    manifest: Mapping[str, Any],
    *,
    config: SystemConfig,
    counters: AuditCounterState,
    provenance: AuditProvenance,
    canonical_command_template: Sequence[str],
    registration_rows: Sequence[Mapping[str, Any]],
    registration_preregistration: Mapping[str, Any],
    registration_sha256: str,
    started_monotonic: float,
    prepared_context: RegisteredEvaluationContext | None = None,
) -> dict[str, JsonValue]:
    """Evaluate with an outer guard over every post-exposure scientific stage."""

    context = prepared_context or prepare_registered_evaluation_context(
        manifest,
        config=config,
        provenance=provenance,
        canonical_command_template=canonical_command_template,
        registration_rows=registration_rows,
        registration_preregistration=registration_preregistration,
        registration_sha256=registration_sha256,
        started_monotonic=started_monotonic,
    )
    if context.evaluation_started:
        raise ValueError("registered evaluation context is one-shot")
    context.evaluation_started = True
    try:
        return _evaluate_registered_scientific_phase(context, counters)
    except Exception as error:
        if not counters.scientific_exposure_started:
            raise
        return build_registered_evaluation_fallback(context, counters, error)


def _emergency_json_value(value: object) -> JsonValue:
    """Sanitize a completed in-memory payload without consulting external state."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if isfinite(value):
            return value
        return {"invalid_json_value": "non_finite_float"}
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            return {"invalid_json_value": "non_string_mapping_key"}
        return {
            cast(str, key): _emergency_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_emergency_json_value(item) for item in value]
    return {"invalid_json_value": type(value).__name__}


def build_emergency_negative_payload(
    payload: Mapping[str, object],
    error: Exception,
) -> dict[str, JsonValue]:
    """Make one schema-preserving negative payload after serialization fails."""

    sanitized = _emergency_json_value(payload)
    if not isinstance(sanitized, dict):
        raise RuntimeError("emergency payload sanitizer did not return a mapping")
    records = sanitized.get("records")
    if not isinstance(records, list) or len(records) != 140:
        raise RuntimeError("emergency payload lacks the 140-row accumulator")
    if not all(isinstance(record, Mapping) for record in records):
        raise RuntimeError("emergency payload contains a malformed scientific row")
    registration_rows: list[Mapping[str, Any]] = []
    for record in records:
        registered_row = cast(Mapping[str, object], record).get("registered_row")
        if not isinstance(registered_row, Mapping):
            raise RuntimeError("emergency scientific row lacks its registration")
        registration_rows.append(cast(Mapping[str, Any], registered_row))
    try:
        validated_records = validate_and_rederive_scientific_records(
            cast(Sequence[Mapping[str, Any]], records),
            registration_rows,
        )
    except Exception as validation_error:
        raise RuntimeError(
            "emergency payload scientific rows fail authoritative revalidation"
        ) from validation_error
    sanitized["records"] = cast(JsonValue, validated_records)
    raw_failures = sanitized.get("finalization_failures")
    failures: list[JsonValue] = []
    if isinstance(raw_failures, list):
        failures.extend(
            item
            for item in raw_failures
            if isinstance(item, dict)
            and set(item) == {"error_type", "stage"}
            and (item["error_type"] is None or isinstance(item["error_type"], str))
            and isinstance(item["stage"], str)
        )
    failures.append(
        _deterministic_finalization_failure("final_payload_serialization_failed", error)
    )
    acceptance_value = sanitized.get("acceptance")
    acceptance = (
        dict(acceptance_value) if isinstance(acceptance_value, dict) else {}
    )
    checks_value = acceptance.get("checks")
    checks = (
        {
            key: item is True
            for key, item in checks_value.items()
            if isinstance(key, str)
        }
        if isinstance(checks_value, dict)
        else {}
    )
    checks["finalization_complete"] = False
    acceptance["acceptance_passes"] = False
    acceptance["checks"] = cast(JsonValue, checks)
    acceptance["failed_checks"] = cast(
        JsonValue,
        sorted(name for name, passed in checks.items() if not passed),
    )
    acceptance["final_admission_claimed"] = False
    acceptance["runtime_v5_enabled"] = False
    sanitized["acceptance"] = cast(JsonValue, acceptance)
    sanitized["disposition"] = "mechanism_capability_failed_runtime_v5_frozen"
    sanitized["finalization_failures"] = failures
    return sanitized


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key in registered lockbox: {key}")
        result[key] = value
    return result


def read_authorized_registered_manifest(
    capability: RegisteredAuditCapability,
    *,
    counters: AuditCounterState,
) -> dict[str, Any]:
    """Perform the sole resolve/stat/open/read sequence after capability admission."""

    state = _registered_capability_state(capability, consume_read=False)
    registration = _revalidate_registered_capability_state(state)
    provenance = state.provenance
    try:
        registration.claim_registered_lockbox_read_once(
            state.consumed_permit,
            expected_repository_root=state.root,
            expected_code_commit=provenance.code_commit,
            expected_registration_sha256=provenance.registration_sha256,
            expected_source_manifest_sha256=provenance.source_manifest_sha256,
        )
    except Exception as error:
        raise RegisteredAuditNotAuthorized(
            "durable registered-lockbox read authorization is unavailable"
        ) from error
    counters.mark_scientific_exposure_started()
    consumed_state = _registered_capability_state(capability, consume_read=True)
    if consumed_state is not state:
        raise RegisteredAuditNotAuthorized("capability registry identity changed")
    expected = state.root / LOCKBOX_ARTIFACT_RELATIVE_PATH
    counters.increment("lockbox_path_operations")
    resolved = expected.resolve(strict=True)
    if resolved != expected:
        raise RegisteredAuditNotAuthorized("registered lockbox path is not canonical/plain")
    counters.increment("lockbox_path_operations")
    metadata = resolved.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != LOCKBOX_ARTIFACT_SIZE_BYTES:
        raise RegisteredAuditNotAuthorized("registered lockbox size or file type mismatch")
    counters.increment("lockbox_path_operations")
    descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        counters.increment("lockbox_path_operations")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read()
    finally:
        os.close(descriptor)
    counters.increment("lockbox_bytes_read", len(raw))
    if len(raw) != LOCKBOX_ARTIFACT_SIZE_BYTES or _sha256(raw) != LOCKBOX_ARTIFACT_SHA256:
        raise RegisteredAuditNotAuthorized("registered lockbox byte identity mismatch")
    try:
        parsed: Any = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RegisteredAuditNotAuthorized("registered lockbox JSON is invalid") from error
    if not isinstance(parsed, dict):
        raise RegisteredAuditNotAuthorized("registered lockbox root is not a mapping")
    from .action_qbc_lockbox import validate_registered_manifest

    validate_registered_manifest(parsed)
    if parsed.get("content_sha256") != LOCKBOX_CONTENT_SHA256:
        raise RegisteredAuditNotAuthorized(
            "registered lockbox manifest content identity mismatch"
        )
    return cast(dict[str, Any], parsed)


def evaluate_open_fixture(case: OpenAuditCase) -> dict[str, JsonValue]:
    """Run the shared pure selector over one caller-built, unsealed snapshot."""

    if action_qbc_policy_sha256() != ACTION_QBC_POLICY_SHA256:
        raise RuntimeError("action-QBC policy source identity drifted")
    selection = ACTION_QBC_AUDIT_SELECTOR(
        case.snapshot,
        cross_level_multiplier=case.cross_level_multiplier,
        probes_used=case.probes_used,
        probe_cap=MAX_PROBES_PER_LEVEL,
    )
    snapshot_payload = _snapshot_json(case.snapshot)
    return {
        "control": case.control.value,
        "cross_level_multiplier": case.cross_level_multiplier,
        "probe_cap": MAX_PROBES_PER_LEVEL,
        "probes_used": case.probes_used,
        "selection": _selection_json(selection),
        "snapshot_sha256": canonical_sha256(snapshot_payload),
    }


def build_open_scientific_payload(
    cases: Sequence[OpenAuditCase],
    *,
    require_complete_controls: bool = True,
) -> dict[str, JsonValue]:
    """Build a deterministic zero-resource payload from injected open fixtures."""

    by_control: dict[AuditControl, OpenAuditCase] = {}
    for case in cases:
        if case.control in by_control:
            raise ValueError(f"duplicate audit control: {case.control.value}")
        by_control[case.control] = case
    if require_complete_controls and set(by_control) != set(REQUIRED_OPEN_CONTROL_ORDER):
        missing = [
            control.value
            for control in REQUIRED_OPEN_CONTROL_ORDER
            if control not in by_control
        ]
        unexpected = sorted(
            control.value
            for control in by_control
            if control not in REQUIRED_OPEN_CONTROL_ORDER
        )
        raise ValueError(f"open control set mismatch: missing={missing}, unexpected={unexpected}")
    ordered = [
        by_control[control]
        for control in REQUIRED_OPEN_CONTROL_ORDER
        if control in by_control
    ]
    case_payloads: list[JsonValue] = [evaluate_open_fixture(case) for case in ordered]
    payload: dict[str, JsonValue] = {
        "audit_contract_version": ACTION_QBC_AUDIT_CONTRACT_VERSION,
        "authorization": {
            "enabled": AUDIT_AUTHORIZATION_ENABLED,
            "pending_freeze_fields": list(PENDING_FREEZE_FIELDS),
            "state": AUDIT_AUTHORIZATION_STATE,
        },
        "case_count": len(case_payloads),
        "cases": case_payloads,
        "execution_scope": "injected-open-planning-snapshots-only",
        "expected_registered_provenance": EXPECTED_AUDIT_PROVENANCE.as_json(),
        "policy_sha256": ACTION_QBC_POLICY_SHA256,
        "policy_version": ACTION_QBC_POLICY_VERSION,
        "resource_counter_fields": list(AUDIT_RESOURCE_COUNTER_FIELDS),
        "resource_counter_schema_sha256": AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256,
        "resource_counters": OPEN_FIXTURE_RESOURCE_COUNTERS.as_json(),
        "schema_version": ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION,
    }
    return payload


__all__ = [
    "ACTION_QBC_AUDIT_CONTRACT_VERSION",
    "ACTION_QBC_AUDIT_SELECTOR",
    "ACTION_QBC_SCIENTIFIC_SCHEMA_VERSION",
    "AUDIT_AUTHORIZATION_CONTRACT",
    "AUDIT_AUTHORIZATION_ENABLED",
    "AUDIT_AUTHORIZATION_STATE",
    "AUDIT_CONFIG_FILE_SHA256",
    "AUDIT_CONFIG_RELATIVE_PATH",
    "AUDIT_MATRIX_FILE_SHA256",
    "AUDIT_MATRIX_RELATIVE_PATH",
    "AUDIT_REGISTRATION_RELATIVE_PATH",
    "AUDIT_REGISTRATION_SCHEMA_VERSION",
    "AUDIT_REGISTRATION_TAG",
    "AUDIT_RESOURCE_COUNTER_FIELDS",
    "AUDIT_RESOURCE_COUNTER_INVENTORY",
    "AUDIT_RESOURCE_COUNTER_SCHEMA_SHA256",
    "AUDIT_SOURCE_FILE_ORDER",
    "AUDIT_WALL_TIME_SECONDS",
    "EXPECTED_AUDIT_PROVENANCE",
    "EXPECTED_SEALED_RESOURCE_COUNTS",
    "LOCKBOX_ARTIFACT_RELATIVE_PATH",
    "LOCKBOX_ARTIFACT_SHA256",
    "LOCKBOX_ARTIFACT_SIZE_BYTES",
    "LOCKBOX_CONTENT_SHA256",
    "OPEN_FIXTURE_RESOURCE_COUNTERS",
    "ORDER_TRANSFORM_NAMES",
    "PENDING_FREEZE_FIELDS",
    "PREREGISTERED_CONTROL_ORDER",
    "PREREGISTERED_CONTROL_SELECTOR_CALLS",
    "PREREGISTERED_CONTROL_SELECTOR_CALL_LEDGER",
    "REGISTERED_AUDIT_DISTRIBUTIONS",
    "REGISTERED_AUDIT_UV_VERSION",
    "REGISTERED_AUDIT_VIRTUALENV_MODULE_SHA256",
    "REGISTERED_AUDIT_VIRTUALENV_PTH_SHA256",
    "REQUIRED_OPEN_CONTROL_ORDER",
    "SEALED_SCENE_FAMILIES",
    "SEALED_VISUAL_TRANSFORM_NAMES",
    "TOPOLOGY_COMPILER_CODE_SHA256",
    "AuditControl",
    "AuditCounterState",
    "AuditProvenance",
    "AuditWallTimeExceeded",
    "JsonValue",
    "OpenAuditCase",
    "PipelineAuditResult",
    "RegisteredAuditCapability",
    "RegisteredAuditLaunchAttestation",
    "RegisteredAuditNotAuthorized",
    "RegisteredEvaluationContext",
    "ResourceCounters",
    "SourceFileIdentity",
    "build_open_scientific_payload",
    "build_registered_evaluation_fallback",
    "canonical_json_bytes",
    "canonical_sha256",
    "consume_registered_audit_capability_for_ledger",
    "consume_registered_audit_launch_attestation_for_ledger",
    "evaluate_compiler_planner_snapshot",
    "evaluate_open_fixture",
    "evaluate_order_transforms",
    "evaluate_preregistered_controls",
    "evaluate_registered_manifest",
    "evaluate_scene_record",
    "issue_registered_audit_capability",
    "issue_registered_audit_launch_attestation",
    "load_audit_registration_admin",
    "prepare_registered_evaluation_context",
    "prepare_registered_fallback_context_from_registration",
    "preregistered_control_contract_sha256",
    "read_authorized_registered_manifest",
    "require_registered_audit_authorized",
    "require_registered_launcher_environment",
    "reverse_candidate_order",
    "run_registered_audit_scaffold",
    "validate_and_rederive_scientific_records",
]
