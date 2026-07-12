"""Typed configuration schema independent of the serialization format."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a configuration mapping violates the experiment contract."""


def _positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{name} must be a positive integer")


def _non_negative_float(name: str, value: float) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"{name} must be numeric")
    if not isfinite(float(value)) or value < 0:
        raise ConfigError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    seed: int = 20_260_712
    variant: str = "X"
    implementation_contract_version: str = "crosslevel-voi-runtime-v1"
    prompt_contract_version: str = "grounded-actions-palette-graded-goals-v3"
    perception_contract_version: str = "arc-agi-0.9.9-color-map-scale8-grid-v1"
    prompt_contract_sha256: str = (
        "391eadfb3bbf860cb8266fea6f4a3cd5855eb9ab60fc1610b37b66516a44b6de"
    )
    perception_contract_sha256: str = (
        "fade727568f9a95e45bb2c40e97d3a4ba524b04c4c2645c18bdd911312a494d0"
    )
    max_environment_actions: int = 256
    max_generated_tokens: int = 12_288
    max_generation_batches: int = 3
    max_wall_seconds: float = 1_200.0
    history_length: int = 8

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ConfigError("seed must be an integer")
        if self.variant not in {"D", "S", "M", "X"}:
            raise ConfigError("variant must be one of D, S, M, or X")
        if not self.implementation_contract_version.strip():
            raise ConfigError("implementation_contract_version cannot be empty")
        if not self.prompt_contract_version.strip():
            raise ConfigError("prompt_contract_version cannot be empty")
        if not self.perception_contract_version.strip():
            raise ConfigError("perception_contract_version cannot be empty")
        for name in ("prompt_contract_sha256", "perception_contract_sha256"):
            digest = getattr(self, name)
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ConfigError(f"{name} must be a lowercase SHA-256 digest")
        for name in (
            "max_environment_actions",
            "max_generated_tokens",
            "max_generation_batches",
            "history_length",
        ):
            _positive_int(name, getattr(self, name))
        if self.history_length != 8:
            raise ConfigError("history_length is fixed at eight by the research protocol")
        _non_negative_float("max_wall_seconds", self.max_wall_seconds)
        if self.max_wall_seconds == 0:
            raise ConfigError("max_wall_seconds must be positive")


@dataclass(frozen=True, slots=True)
class HypothesisConfig:
    max_hypotheses: int = 4
    eta: float = 5.0
    complexity_lambda: float = 0.002
    loss_refresh_threshold: float = 0.25
    consecutive_loss_refreshes: int = 2
    effective_pool_refresh_threshold: float = 1.5
    max_refreshes_per_level: int = 1

    def __post_init__(self) -> None:
        _positive_int("max_hypotheses", self.max_hypotheses)
        if self.max_hypotheses > 4:
            raise ConfigError("max_hypotheses cannot exceed four")
        for name in (
            "eta",
            "complexity_lambda",
            "loss_refresh_threshold",
            "effective_pool_refresh_threshold",
        ):
            _non_negative_float(name, getattr(self, name))
        if self.eta == 0 or self.effective_pool_refresh_threshold == 0:
            raise ConfigError("eta and effective_pool_refresh_threshold must be positive")
        _positive_int("consecutive_loss_refreshes", self.consecutive_loss_refreshes)
        _positive_int("max_refreshes_per_level", self.max_refreshes_per_level)


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    max_candidates: int = 12
    depth: int = 4
    beam_width: int = 8
    agreement_threshold: float = 0.8
    max_probes_per_level: int = 3
    risk_coefficient: float = 3.0
    robust_std_coefficient: float = 0.5

    def __post_init__(self) -> None:
        for name in ("max_candidates", "depth", "beam_width", "max_probes_per_level"):
            _positive_int(name, getattr(self, name))
        for name in ("agreement_threshold", "risk_coefficient", "robust_std_coefficient"):
            _non_negative_float(name, getattr(self, name))
        if not 0 <= self.agreement_threshold <= 1:
            raise ConfigError("agreement_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    temperature: float = 0.6
    top_p: float = 0.95
    max_new_tokens_per_hypothesis: int = 1536

    def __post_init__(self) -> None:
        _non_negative_float("temperature", self.temperature)
        _non_negative_float("top_p", self.top_p)
        if not 0 < self.top_p <= 1:
            raise ConfigError("top_p must be in (0, 1]")
        _positive_int("max_new_tokens_per_hypothesis", self.max_new_tokens_per_hypothesis)


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    timeout_ms: int = 100
    memory_mb: int = 256

    def __post_init__(self) -> None:
        _positive_int("timeout_ms", self.timeout_ms)
        _positive_int("memory_mb", self.memory_mb)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    id: str
    profile: str
    expected_revision: str | None = None
    expected_weight_manifest_sha256: str | None = None
    context_length: int = 16_384
    quantization: str = "none"
    double_quantization: bool = False
    compute_dtype: str = "bfloat16"
    max_peak_vram_gb: float | None = None
    min_tokens_per_second: float | None = None
    max_runtime_fraction: float | None = None
    offline: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.profile.strip():
            raise ConfigError("model id and profile cannot be empty")
        if (self.expected_revision is None) != (
            self.expected_weight_manifest_sha256 is None
        ):
            raise ConfigError(
                "expected_revision and expected_weight_manifest_sha256 must be set together"
            )
        if self.expected_revision is not None and (
            len(self.expected_revision) != 40
            or any(character not in "0123456789abcdef" for character in self.expected_revision)
        ):
            raise ConfigError("expected_revision must be a lowercase 40-character commit")
        if self.expected_weight_manifest_sha256 is not None and (
            len(self.expected_weight_manifest_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.expected_weight_manifest_sha256
            )
        ):
            raise ConfigError(
                "expected_weight_manifest_sha256 must be a lowercase SHA-256 digest"
            )
        _positive_int("context_length", self.context_length)
        if self.quantization not in {"none", "nf4", "fp8"}:
            raise ConfigError("quantization must be none, nf4, or fp8")
        if self.compute_dtype not in {"bfloat16", "float16", "float32"}:
            raise ConfigError("unsupported compute_dtype")
        if self.max_peak_vram_gb is not None:
            _non_negative_float("max_peak_vram_gb", self.max_peak_vram_gb)
        if self.min_tokens_per_second is not None:
            _non_negative_float("min_tokens_per_second", self.min_tokens_per_second)
        if self.max_runtime_fraction is not None:
            _non_negative_float("max_runtime_fraction", self.max_runtime_fraction)
            if not 0 < self.max_runtime_fraction <= 1:
                raise ConfigError("max_runtime_fraction must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class SystemConfig:
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    hypotheses: HypothesisConfig = field(default_factory=HypothesisConfig)
    planning: PlanningConfig = field(default_factory=PlanningConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    model: ModelConfig | None = None


def _section[ConfigT](
    section_type: Callable[..., ConfigT],
    raw: object,
    name: str,
    allowed: frozenset[str],
    default_factory: Callable[[], ConfigT] | None = None,
) -> ConfigT:
    if raw is None:
        if default_factory is None:
            raise ConfigError(f"{name} is required")
        return default_factory()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(f"unknown {name} keys: {', '.join(sorted(map(str, unknown)))}")
    try:
        return section_type(**dict(raw))
    except TypeError as exc:
        raise ConfigError(f"invalid {name} section: {exc}") from exc


def config_from_mapping(raw: Mapping[str, Any]) -> SystemConfig:
    """Construct a validated config after a caller parses YAML/JSON.

    Serialization is deliberately kept outside the domain layer so the Kaggle
    offline bundle is not coupled to a particular YAML implementation.
    """

    allowed = {"experiment", "hypotheses", "planning", "generation", "sandbox", "model"}
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(f"unknown top-level keys: {', '.join(sorted(map(str, unknown)))}")
    model_raw = raw.get("model")
    model = (
        None
        if model_raw is None
        else _section(
            ModelConfig,
            model_raw,
            "model",
            frozenset(
                {
                    "id",
                    "profile",
                    "expected_revision",
                    "expected_weight_manifest_sha256",
                    "context_length",
                    "quantization",
                    "double_quantization",
                    "compute_dtype",
                    "max_peak_vram_gb",
                    "min_tokens_per_second",
                    "max_runtime_fraction",
                    "offline",
                }
            ),
        )
    )
    return SystemConfig(
        experiment=_section(
            ExperimentConfig,
            raw.get("experiment"),
            "experiment",
            frozenset(
                {
                    "seed",
                    "variant",
                    "implementation_contract_version",
                    "prompt_contract_version",
                    "perception_contract_version",
                    "prompt_contract_sha256",
                    "perception_contract_sha256",
                    "max_environment_actions",
                    "max_generated_tokens",
                    "max_generation_batches",
                    "max_wall_seconds",
                    "history_length",
                }
            ),
            ExperimentConfig,
        ),
        hypotheses=_section(
            HypothesisConfig,
            raw.get("hypotheses"),
            "hypotheses",
            frozenset(
                {
                    "max_hypotheses",
                    "eta",
                    "complexity_lambda",
                    "loss_refresh_threshold",
                    "consecutive_loss_refreshes",
                    "effective_pool_refresh_threshold",
                    "max_refreshes_per_level",
                }
            ),
            HypothesisConfig,
        ),
        planning=_section(
            PlanningConfig,
            raw.get("planning"),
            "planning",
            frozenset(
                {
                    "max_candidates",
                    "depth",
                    "beam_width",
                    "agreement_threshold",
                    "max_probes_per_level",
                    "risk_coefficient",
                    "robust_std_coefficient",
                }
            ),
            PlanningConfig,
        ),
        generation=_section(
            GenerationConfig,
            raw.get("generation"),
            "generation",
            frozenset({"temperature", "top_p", "max_new_tokens_per_hypothesis"}),
            GenerationConfig,
        ),
        sandbox=_section(
            SandboxConfig,
            raw.get("sandbox"),
            "sandbox",
            frozenset({"timeout_ms", "memory_mb"}),
            SandboxConfig,
        ),
        model=model,
    )


def load_config(path: str | Path) -> SystemConfig:
    """Load YAML with one or more relative ``extends`` layers."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - declared project dependency
        raise RuntimeError("PyYAML is required to load configuration files") from exc

    def load_mapping(source: Path, seen: frozenset[Path]) -> dict[str, Any]:
        resolved = source.resolve()
        if resolved in seen:
            raise ConfigError(f"configuration inheritance cycle at {resolved}")
        if not resolved.exists():
            raise ConfigError(f"configuration file does not exist: {resolved}")
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, Mapping):
            raise ConfigError(f"configuration root must be a mapping: {resolved}")
        local = dict(raw)
        parent_name = local.pop("extends", None)
        if parent_name is None:
            return local
        if not isinstance(parent_name, str):
            raise ConfigError("extends must be a relative path string")
        parent = load_mapping(resolved.parent / parent_name, seen | {resolved})
        return _deep_merge(parent, local)

    return config_from_mapping(load_mapping(Path(path), frozenset()))


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(value, Mapping) and isinstance(existing, Mapping):
            merged[key] = _deep_merge(dict(existing), dict(value))
        else:
            merged[key] = value
    return merged
