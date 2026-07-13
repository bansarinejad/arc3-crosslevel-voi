"""Preregistered experiment matrices, config hashes, and decision gates."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal, cast

from .config import HypothesisSource
from .planner import (
    COMPLETION_COST_POLICY_HASHES,
    ENDPOINT_COMPLETION_COST_POLICY,
)
from .run_store import read_complete_run

Variant = Literal["D", "S", "M", "X"]
ArmLabel = Literal["D-Q", "S-Q", "M-Q", "X-Q", "S-T", "M-T", "X-T", "M-H", "X-H"]
IdentityVersion = Literal["legacy-v1", "source-v2"]

DEVELOPMENT_SEEDS = (11, 23, 47)
CONFIRMATION_SEEDS = (101, 211, 307, 401, 503)
KAGGLE_TRANSFER_SEEDS = (701,)
FALLBACK_DEVELOPMENT_SEEDS = DEVELOPMENT_SEEDS[:2]
FALLBACK_CONFIRMATION_SEEDS = CONFIRMATION_SEEDS[:3]
ETA_GRID = (2.0, 5.0, 10.0)
LAMBDA_GRID = (0.0, 0.002, 0.01)


@dataclass(frozen=True, slots=True)
class RunSpec:
    phase: Literal["development", "confirmation", "kaggle-transfer"]
    game_id: str
    seed: int
    variant: Variant
    model_profile: str
    config_hash: str
    game_version: str = "unknown"
    snapshot_hash: str = ""
    hypothesis_source: HypothesisSource = "qwen"
    arm_label: ArmLabel | None = None
    identity_version: IdentityVersion = "source-v2"

    def __post_init__(self) -> None:
        if self.phase not in {"development", "confirmation", "kaggle-transfer"}:
            raise ValueError("invalid run phase")
        if self.variant not in {"D", "S", "M", "X"}:
            raise ValueError("invalid controller variant")
        if self.hypothesis_source not in {
            "qwen",
            "template_v1",
            "qwen_then_template_v1",
        }:
            raise ValueError("invalid hypothesis source")
        expected = arm_label_for(self.variant, self.hypothesis_source)
        if self.arm_label is None:
            object.__setattr__(self, "arm_label", expected)
        elif self.arm_label != expected:
            raise ValueError(
                f"arm {self.arm_label} is inconsistent with variant {self.variant} "
                f"and source {self.hypothesis_source}"
            )
        if self.identity_version not in {"legacy-v1", "source-v2"}:
            raise ValueError("invalid run identity version")
        if self.identity_version == "legacy-v1" and self.hypothesis_source != "qwen":
            raise ValueError("legacy-v1 identity is valid only for implicit Qwen rows")

    @property
    def full_game_id(self) -> str:
        if not self.game_version or self.game_version == "unknown":
            return self.game_id
        return f"{self.game_id}-{self.game_version}"

    @property
    def run_id(self) -> str:
        if self.identity_version == "source-v2":
            return (
                f"{self.phase}-{self.full_game_id}-{self.seed}-{self.arm_label}-"
                f"{self.hypothesis_source}-{self.config_hash[:8]}"
            )
        return (
            f"{self.phase}-{self.full_game_id}-{self.seed}-{self.variant}-"
            f"{self.config_hash[:8]}"
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RunSpec:
        """Load both current manifests and pre-version legacy manifests safely."""

        identity_keys = {"hypothesis_source", "arm_label", "identity_version"}
        present_identity_keys = identity_keys.intersection(value)
        if present_identity_keys and present_identity_keys != identity_keys:
            missing = ", ".join(sorted(identity_keys - present_identity_keys))
            raise ValueError(f"matrix row has incomplete source identity: {missing}")
        has_source_identity = bool(present_identity_keys)
        if has_source_identity and value.get("arm_label") is None:
            raise ValueError("source-v2 matrix row requires an explicit arm_label")

        return cls(
            phase=str(value["phase"]),  # type: ignore[arg-type]
            game_id=str(value["game_id"]),
            seed=int(value["seed"]),
            variant=str(value["variant"]),  # type: ignore[arg-type]
            model_profile=str(value["model_profile"]),
            config_hash=str(value["config_hash"]),
            game_version=str(value.get("game_version", "unknown")),
            snapshot_hash=str(value.get("snapshot_hash", "")),
            hypothesis_source=str(value.get("hypothesis_source", "qwen")),  # type: ignore[arg-type]
            arm_label=cast(
                ArmLabel | None,
                str(value["arm_label"]) if value.get("arm_label") is not None else None,
            ),
            identity_version=str(
                value.get("identity_version", "source-v2" if has_source_identity else "legacy-v1")
            ),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class HyperparameterObservation:
    game_id: str
    seed: int
    eta: float
    complexity_lambda: float
    rhae: float
    generated_tokens: int


@dataclass(frozen=True, slots=True)
class HyperparameterSelection:
    eta: float
    complexity_lambda: float
    mean_rhae: float
    mean_generated_tokens: float
    observations: int


@dataclass(frozen=True, slots=True)
class ScoreGateInput:
    x_rhae: float
    m_rhae: float
    x_levels: int
    m_levels: int
    x_actions: int
    m_actions: int
    positive_game_fraction: float
    x_wall_seconds: float
    m_wall_seconds: float


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]


def stable_config_hash(config: object, *, implicit_qwen_legacy: bool = False) -> str:
    hash_input = (
        _implicit_qwen_projection(config)
        if implicit_qwen_legacy
        else _historical_completion_cost_projection(config)
    )
    payload = json.dumps(
        hash_input,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def arm_label_for(variant: Variant, source: HypothesisSource) -> ArmLabel:
    """Return the preregistered label for one controller/source combination."""

    if source == "qwen":
        return f"{variant}-Q"  # type: ignore[return-value]
    if source == "template_v1" and variant in {"S", "M", "X"}:
        return f"{variant}-T"  # type: ignore[return-value]
    if source == "qwen_then_template_v1" and variant in {"M", "X"}:
        return f"{variant}-H"  # type: ignore[return-value]
    raise ValueError(f"variant {variant} is not defined for hypothesis source {source}")


def development_arms(
    source: HypothesisSource,
) -> tuple[tuple[ArmLabel, Variant, HypothesisSource], ...]:
    """Return the frozen development arms for one proposal-source experiment."""

    if source == "qwen":
        return tuple(
            (arm_label_for(variant, "qwen"), variant, "qwen")
            for variant in ("D", "S", "M", "X")
        )
    if source == "template_v1":
        return (
            ("D-Q", "D", "qwen"),
            ("S-T", "S", "template_v1"),
            ("M-T", "M", "template_v1"),
            ("X-T", "X", "template_v1"),
        )
    raise ValueError(
        "qwen_then_template_v1 is a typed reserved source, but hybrid arms are not "
        "preregistered"
    )


def build_development_matrix(
    games: tuple[str, ...],
    *,
    model_profile: str,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
    fallback: bool = False,
) -> tuple[RunSpec, ...]:
    arm_hashes: dict[ArmLabel, str] = {
        arm_label_for(variant, "qwen"): config_hashes[variant]
        for variant in ("D", "S", "M", "X")
    }
    return build_source_development_matrix(
        games,
        hypothesis_source="qwen",
        model_profile=model_profile,
        config_hashes=arm_hashes,
        game_versions=game_versions,
        snapshot_hash=snapshot_hash,
        fallback=fallback,
    )


def build_source_development_matrix(
    games: tuple[str, ...],
    *,
    hypothesis_source: HypothesisSource,
    model_profile: str,
    config_hashes: Mapping[ArmLabel, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
    fallback: bool = False,
) -> tuple[RunSpec, ...]:
    """Build a source-aware development manifest without mutating the Qwen manifest."""

    seeds = FALLBACK_DEVELOPMENT_SEEDS if fallback else DEVELOPMENT_SEEDS
    arms = development_arms(hypothesis_source)
    expected_labels = {label for label, _variant, _source in arms}
    if set(config_hashes) != expected_labels:
        raise ValueError("config hashes must exactly cover the frozen development arms")
    return tuple(
        RunSpec(
            phase="development",
            game_id=game,
            seed=seed,
            variant=variant,
            model_profile=model_profile,
            config_hash=config_hashes[label],
            game_version=_game_version(game, game_versions),
            snapshot_hash=snapshot_hash,
            hypothesis_source=arm_source,
            arm_label=label,
            identity_version="source-v2",
        )
        for game in games
        for seed in seeds
        for label, variant, arm_source in arms
    )


def build_confirmation_matrix(
    games: tuple[str, ...],
    *,
    comparator: Variant,
    model_profile: str,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
    fallback: bool = False,
) -> tuple[RunSpec, ...]:
    if comparator == "X":
        raise ValueError("confirmation comparator must differ from X")
    seeds = FALLBACK_CONFIRMATION_SEEDS if fallback else CONFIRMATION_SEEDS
    variants: tuple[Variant, ...] = (comparator, "X")
    return tuple(
        RunSpec(
            phase="confirmation",
            game_id=game,
            seed=seed,
            variant=variant,
            model_profile=model_profile,
            config_hash=config_hashes[variant],
            game_version=_game_version(game, game_versions),
            snapshot_hash=snapshot_hash,
            hypothesis_source="qwen",
            arm_label=arm_label_for(variant, "qwen"),
            identity_version="source-v2",
        )
        for game in games
        for seed in seeds
        for variant in variants
    )


def build_kaggle_transfer_matrix(
    games: tuple[str, ...],
    *,
    comparator: Variant,
    config_hashes: Mapping[Variant, str],
    game_versions: Mapping[str, str] | None = None,
    snapshot_hash: str = "",
) -> tuple[RunSpec, ...]:
    return tuple(
        RunSpec(
            phase="kaggle-transfer",
            game_id=game,
            seed=seed,
            variant=variant,
            model_profile="kaggle-fp8",
            config_hash=config_hashes[variant],
            game_version=_game_version(game, game_versions),
            snapshot_hash=snapshot_hash,
            hypothesis_source="qwen",
            arm_label=arm_label_for(variant, "qwen"),
            identity_version="source-v2",
        )
        for game in games
        for seed in KAGGLE_TRANSFER_SEEDS
        for variant in (comparator, "X")
    )


def evaluate_score_gate(value: ScoreGateInput) -> GateResult:
    delta_points = 100.0 * (value.x_rhae - value.m_rhae)
    score_improved = delta_points >= 0.5
    level_improved = value.x_levels > value.m_levels and value.x_actions <= value.m_actions
    reasons = []
    if not (score_improved or level_improved):
        reasons.append("neither +0.5 RHAE points nor an action-neutral extra level")
    if value.positive_game_fraction < 0.60:
        reasons.append("positive on fewer than 60% of development games")
    if value.m_wall_seconds <= 0 or value.x_wall_seconds > 1.5 * value.m_wall_seconds:
        reasons.append("wall time exceeds 1.5x the myopic controller")
    return GateResult(not reasons, tuple(reasons))


def projected_gpu_hours(run_count: int, median_run_seconds: float) -> float:
    if run_count < 0 or median_run_seconds < 0:
        raise ValueError("run count and duration must be non-negative")
    return run_count * median_run_seconds / 3600.0


def save_matrix(matrix: tuple[RunSpec, ...], path: str | Path) -> None:
    validate_matrix(matrix, require_frozen_identity=True)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps([asdict(item) | {"run_id": item.run_id} for item in matrix], indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_matrix(path: str | Path, *, require_frozen_identity: bool = True) -> tuple[RunSpec, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("runs", ())
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes):
        raise ValueError("matrix must be a JSON list or an object containing a runs list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("every matrix row must be a JSON object")
    matrix = tuple(RunSpec.from_mapping(row) for row in rows)
    for source, row in zip(rows, matrix, strict=True):
        declared_run_id = source.get("run_id")
        if declared_run_id is not None and declared_run_id != row.run_id:
            raise ValueError(f"declared run ID does not match row fields: {declared_run_id}")
    validate_matrix(matrix, require_frozen_identity=require_frozen_identity)
    return matrix


def validate_matrix(
    matrix: Sequence[RunSpec], *, require_frozen_identity: bool = True
) -> None:
    """Reject incomplete, unpaired, mutable, or hash-ambiguous run manifests."""

    if not matrix:
        raise ValueError("matrix cannot be empty")
    if len({row.run_id for row in matrix}) != len(matrix):
        raise ValueError("matrix run IDs must be unique")
    phases = {row.phase for row in matrix}
    if len(phases) != 1:
        raise ValueError("a matrix must contain exactly one phase")
    if not phases <= {"development", "confirmation", "kaggle-transfer"}:
        raise ValueError("matrix contains an invalid phase")
    if any(row.variant not in {"D", "S", "M", "X"} for row in matrix):
        raise ValueError("matrix contains an invalid variant")
    if any(not row.game_id or not row.model_profile for row in matrix):
        raise ValueError("matrix game IDs and model profiles cannot be empty")
    if require_frozen_identity:
        snapshots = {row.snapshot_hash for row in matrix}
        if len(snapshots) != 1 or not _is_sha256(next(iter(snapshots))):
            raise ValueError("matrix must carry one valid frozen snapshot hash")
        if any(not row.game_version or row.game_version == "unknown" for row in matrix):
            raise ValueError("every matrix row must carry a frozen game version")

    identity_versions = {row.identity_version for row in matrix}
    if len(identity_versions) != 1:
        raise ValueError("a matrix cannot mix legacy and source-aware identities")
    arm_hashes: dict[ArmLabel, set[str]] = defaultdict(set)
    cells: dict[tuple[str, ArmLabel], set[int]] = defaultdict(set)
    arms = {row.arm_label for row in matrix}
    if None in arms:
        raise ValueError("every matrix row must carry a derivable arm label")
    typed_arms = {arm for arm in arms if arm is not None}
    games_by_arm: dict[ArmLabel, set[str]] = defaultdict(set)
    for row in matrix:
        if not _is_sha256(row.config_hash):
            raise ValueError(f"invalid config hash for {row.run_id}")
        assert row.arm_label is not None
        arm_hashes[row.arm_label].add(row.config_hash)
        cell = (row.full_game_id, row.arm_label)
        if row.seed in cells[cell]:
            raise ValueError(f"duplicate game/seed/arm cell: {cell}, seed={row.seed}")
        cells[cell].add(row.seed)
        games_by_arm[row.arm_label].add(row.full_game_id)
    if any(len(hashes) != 1 for hashes in arm_hashes.values()):
        raise ValueError("each arm must have exactly one config hash")
    hashes = {next(iter(values)) for values in arm_hashes.values()}
    if len(hashes) != len(arm_hashes):
        raise ValueError("arm config hashes must be distinct")
    reference_games = games_by_arm[next(iter(typed_arms))]
    if any(games != reference_games for games in games_by_arm.values()):
        raise ValueError("arms must cover identical game sets")
    expected_seeds: set[int] | None = None
    for game in sorted(reference_games):
        per_arm = [cells[(game, arm)] for arm in typed_arms]
        if any(seeds != per_arm[0] for seeds in per_arm[1:]):
            raise ValueError(f"arms have non-identical paired seed sets for {game}")
        if expected_seeds is None:
            expected_seeds = per_arm[0]
        elif per_arm[0] != expected_seeds:
            raise ValueError("all games must use the same frozen seed set")


def completed_run_ids(matrix: Sequence[RunSpec], output: str | Path) -> frozenset[str]:
    """Return only complete run pairs matching their manifest row and clean exit."""

    destination = Path(output)
    completed: set[str] = set()
    for row in matrix:
        path = destination / f"{row.run_id}.json"
        artifacts = read_complete_run(path)
        if artifacts is None:
            continue
        value, _trace = artifacts
        expected = {
            "run_id": row.run_id,
            "game_id": row.full_game_id,
            "seed": row.seed,
            "variant": row.variant,
            "model_profile": row.model_profile,
            "config_hash": row.config_hash,
        }
        source_identity_matches = True
        if row.identity_version == "source-v2":
            source_identity_matches = (
                value.get("hypothesis_source") == row.hypothesis_source
                and value.get("arm_label") == row.arm_label
                and value.get("identity_version") == row.identity_version
                and isinstance(value.get("producer_contract_sha256"), str)
                and _is_sha256(value["producer_contract_sha256"])
            )
        if (
            all(value.get(key) == expected_value for key, expected_value in expected.items())
            and source_identity_matches
            and value.get("error") is None
            and value.get("termination_reason") is not None
        ):
            completed.add(row.run_id)
    return frozenset(completed)


def pending_runs(matrix: Sequence[RunSpec], output: str | Path) -> tuple[RunSpec, ...]:
    completed = completed_run_ids(matrix, output)
    return tuple(row for row in matrix if row.run_id not in completed)


def select_eta_lambda(
    observations: Iterable[HyperparameterObservation],
) -> HyperparameterSelection:
    """Select the preregistered 3x3 grid by RHAE, tokens, lambda, then eta."""

    buckets: dict[tuple[float, float], list[HyperparameterObservation]] = defaultdict(list)
    for row in observations:
        key = (float(row.eta), float(row.complexity_lambda))
        if key not in {(eta, value) for eta in ETA_GRID for value in LAMBDA_GRID}:
            raise ValueError(f"observation outside preregistered eta/lambda grid: {key}")
        buckets[key].append(row)
    expected = {(eta, value) for eta in ETA_GRID for value in LAMBDA_GRID}
    if set(buckets) != expected:
        missing = sorted(expected - set(buckets))
        raise ValueError(f"missing eta/lambda grid cells: {missing}")
    reference_cells: set[tuple[str, int]] | None = None
    candidates: list[HyperparameterSelection] = []
    for (eta, value), rows in sorted(buckets.items()):
        cells = {(row.game_id, row.seed) for row in rows}
        if len(cells) != len(rows):
            raise ValueError(f"duplicate observations in eta/lambda cell {(eta, value)}")
        if reference_cells is None:
            reference_cells = cells
        elif cells != reference_cells:
            raise ValueError("eta/lambda cells must contain identical game/seed observations")
        candidates.append(
            HyperparameterSelection(
                eta=eta,
                complexity_lambda=value,
                mean_rhae=mean(row.rhae for row in rows),
                mean_generated_tokens=mean(row.generated_tokens for row in rows),
                observations=len(rows),
            )
        )
    return max(
        candidates,
        key=lambda row: (
            row.mean_rhae,
            -row.mean_generated_tokens,
            -row.complexity_lambda,
            -row.eta,
        ),
    )


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _implicit_qwen_projection(config: object) -> object:
    """Project a source-aware config onto the pre-amendment implicit-Qwen schema."""

    if is_dataclass(config) and not isinstance(config, type):
        projected: object = asdict(config)
    elif isinstance(config, Mapping):
        projected = dict(config)
    else:
        raise ValueError("legacy Qwen projection requires a dataclass or mapping")
    if not isinstance(projected, dict):  # pragma: no cover - guarded above
        raise AssertionError("legacy projection must be a mapping")
    raw_experiment = projected.get("experiment")
    if not isinstance(raw_experiment, Mapping):
        raise ValueError("legacy Qwen projection requires an experiment mapping")
    experiment = dict(raw_experiment)
    source = experiment.pop("hypothesis_source", "qwen")
    if source != "qwen":
        raise ValueError("only Qwen configs have a valid pre-amendment hash projection")
    experiment["implementation_contract_version"] = "crosslevel-voi-runtime-v2"
    for key in (
        "candidate_policy_version",
        "candidate_policy_sha256",
        "compiler_contract_version",
        "compiler_contract_sha256",
    ):
        experiment.pop(key, None)
    projected["experiment"] = experiment
    raw_planning = projected.get("planning")
    if isinstance(raw_planning, Mapping):
        planning = dict(raw_planning)
        _validate_historical_completion_cost_policy(planning)
        _validate_historical_probe_disagreement_policy(planning)
        planning.pop("completion_cost_policy_version", None)
        planning.pop("completion_cost_policy_sha256", None)
        planning.pop("probe_disagreement_policy_version", None)
        planning.pop("probe_disagreement_policy_sha256", None)
        projected["planning"] = planning
    return projected


def _historical_completion_cost_projection(config: object) -> object:
    """Keep runtime-v2/v3/v4 identities stable after policy versioning."""

    if is_dataclass(config) and not isinstance(config, type):
        projected: object = asdict(config)
    elif isinstance(config, Mapping):
        projected = dict(config)
    else:
        return config
    if not isinstance(projected, dict):  # pragma: no cover - guarded above
        return config
    raw_experiment = projected.get("experiment")
    raw_planning = projected.get("planning")
    if not isinstance(raw_experiment, Mapping) or not isinstance(raw_planning, Mapping):
        return config
    runtime_version = raw_experiment.get("implementation_contract_version")
    if runtime_version not in {
        "crosslevel-voi-runtime-v2",
        "crosslevel-voi-runtime-v3",
        "crosslevel-voi-runtime-v4",
    }:
        return projected
    planning = dict(raw_planning)
    _validate_historical_probe_disagreement_policy(planning)
    planning.pop("probe_disagreement_policy_version", None)
    planning.pop("probe_disagreement_policy_sha256", None)
    if runtime_version in {
        "crosslevel-voi-runtime-v2",
        "crosslevel-voi-runtime-v3",
    }:
        _validate_historical_completion_cost_policy(planning)
        planning.pop("completion_cost_policy_version", None)
        planning.pop("completion_cost_policy_sha256", None)
    projected["planning"] = planning
    return projected


def _validate_historical_completion_cost_policy(planning: Mapping[str, object]) -> None:
    policy_keys = {
        "completion_cost_policy_version",
        "completion_cost_policy_sha256",
    }
    present = policy_keys.intersection(planning)
    if not present:
        return
    if present != policy_keys:
        raise ValueError("historical completion-cost policy identity is incomplete")
    expected = (
        ENDPOINT_COMPLETION_COST_POLICY,
        COMPLETION_COST_POLICY_HASHES[ENDPOINT_COMPLETION_COST_POLICY],
    )
    actual = (
        planning["completion_cost_policy_version"],
        planning["completion_cost_policy_sha256"],
    )
    if actual != expected:
        raise ValueError("historical completion-cost policy identity must be endpoint-v1")


def _validate_historical_probe_disagreement_policy(
    planning: Mapping[str, object],
) -> None:
    policy_keys = {
        "probe_disagreement_policy_version",
        "probe_disagreement_policy_sha256",
    }
    present = policy_keys.intersection(planning)
    if not present:
        return
    if present != policy_keys:
        raise ValueError("historical probe-disagreement policy identity is incomplete")
    expected = (
        "winning-action-agreement-v1",
        "5e659e6ad3a3f6e50dd4bfe709b901e29999b031ac5565c5469f0d66a216aa8a",
    )
    actual = (
        planning["probe_disagreement_policy_version"],
        planning["probe_disagreement_policy_sha256"],
    )
    if actual != expected:
        raise ValueError(
            "historical probe-disagreement policy identity must be "
            "winning-action-agreement-v1"
        )


def _game_version(game: str, versions: Mapping[str, str] | None) -> str:
    if versions is not None:
        return str(versions.get(game, "unknown"))
    _, separator, version = game.partition("-")
    return version if separator else "unknown"


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
