"""Optional local Qwen backend and deterministic test backends."""

from __future__ import annotations

import gc
import json
import random
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .prompts import (
    DIRECT_SYSTEM_PROMPT,
    PROGRAM_SYSTEM_PROMPT,
    PROMPT_CONTRACT_SHA256,
    PROMPT_CONTRACT_VERSION,
    direct_prompt,
    extract_python,
    parse_action_json,
    program_prompt,
)
from .provenance import inspect_model_artifact
from .rendering import (
    PERCEPTION_CONTRACT_SHA256,
    PERCEPTION_CONTRACT_VERSION,
    render_grid_pil,
)


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    temperature: float = 0.6
    top_p: float = 0.95
    max_new_tokens: int = 1536
    context_length: int = 16_384


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model_id: str
    quantization: str = "none"
    compute_dtype: str = "bfloat16"
    offline: bool = False
    device_map: str = "auto"
    seed: int = 20_260_712
    max_batch_sequences: int = 4
    max_peak_vram_gb: float | None = None
    settings: GenerationSettings = field(default_factory=GenerationSettings)


@dataclass(frozen=True, slots=True)
class GenerationResult:
    texts: tuple[str, ...]
    output_tokens: int
    elapsed_seconds: float
    peak_vram_gb: float | None = None
    sequence_token_counts: tuple[int, ...] = ()
    hit_token_limit: tuple[bool, ...] = ()

    @property
    def tokens_per_second(self) -> float:
        return self.output_tokens / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0


class ModelBackend(Protocol):
    """One backbone exposes both program-induction and direct-policy modes."""

    def generate_programs(
        self,
        history: Any,
        count: int,
        *,
        feedback: str | None = None,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult: ...

    def direct_action(
        self,
        history: Any,
        valid_actions: Sequence[str],
        *,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[dict[str, Any], GenerationResult]: ...


class ScriptedBackend:
    """Dependency-free backend for replay tests and deterministic experiments."""

    def __init__(
        self,
        programs: Sequence[str] = (),
        action_policy: Callable[[Sequence[Any], Sequence[str]], dict[str, Any]] | None = None,
    ) -> None:
        self._programs = tuple(programs)
        self._action_policy = action_policy or (lambda _history, actions: {"kind": actions[0]})
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def generate_programs(
        self,
        history: Any,
        count: int,
        *,
        feedback: str | None = None,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult:
        del history, feedback, max_new_tokens, max_wall_seconds
        texts = (
            tuple(self._programs[index % len(self._programs)] for index in range(count))
            if self._programs
            else ()
        )
        return GenerationResult(
            texts=texts,
            output_tokens=sum(len(x.split()) for x in texts),
            elapsed_seconds=0.001,
        )

    def direct_action(
        self,
        history: Any,
        valid_actions: Sequence[str],
        *,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[dict[str, Any], GenerationResult]:
        del max_new_tokens, max_wall_seconds
        action = self._action_policy(history, valid_actions)
        return action, GenerationResult((json.dumps(action),), 1, 0.001)


class TransformersQwenBackend:
    """Lazy multimodal backend; importing the core package never imports Torch."""

    def __init__(self, profile: ModelProfile, *, model_path: str | Path | None = None) -> None:
        self.profile = profile
        self.model_path = str(model_path or profile.model_id)
        self._processor: Any = None
        self._model: Any = None
        self._torch: Any = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoProcessor, BitsAndBytesConfig
        except ImportError as exc:  # pragma: no cover - optional heavy dependencies
            raise RuntimeError("install the 'model' optional dependencies to load Qwen") from exc

        self._torch = torch
        dtype = getattr(torch, self.profile.compute_dtype)
        random.seed(self.profile.seed)
        np.random.seed(self.profile.seed % (2**32))
        torch.manual_seed(self.profile.seed)
        if torch.cuda.is_available():
            fraction = _cuda_memory_fraction(
                self.profile.max_peak_vram_gb,
                int(torch.cuda.get_device_properties(0).total_memory),
            )
            if fraction is not None and fraction < 1.0:
                torch.cuda.set_per_process_memory_fraction(fraction, device=0)
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.manual_seed_all(self.profile.seed)
        kwargs: dict[str, Any] = {
            "device_map": self.profile.device_map,
            "dtype": dtype,
            "local_files_only": self.profile.offline,
        }
        if self.profile.quantization.lower() == "nf4":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype,
            )
        self._processor = AutoProcessor.from_pretrained(
            self.model_path, local_files_only=self.profile.offline
        )
        self._model = AutoModelForMultimodalLM.from_pretrained(self.model_path, **kwargs)
        self._model.eval()

    def close(self) -> None:
        """Release model references and CUDA caches between experimental rows."""

        torch = self._torch
        self._model = None
        self._processor = None
        self._torch = None
        gc.collect()
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
            ipc_collect = getattr(torch.cuda, "ipc_collect", None)
            if callable(ipc_collect):
                with suppress(RuntimeError):
                    ipc_collect()

    def generate_programs(
        self,
        history: Any,
        count: int,
        *,
        feedback: str | None = None,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult:
        prompt = program_prompt(history, feedback=feedback)
        started = time.perf_counter()
        chunks: list[GenerationResult] = []
        remaining_count = count
        while remaining_count > 0:
            chunk_count = min(remaining_count, self.profile.max_batch_sequences)
            wall_remaining = (
                None
                if max_wall_seconds is None
                else max_wall_seconds - (time.perf_counter() - started)
            )
            if wall_remaining is not None and wall_remaining <= 0:
                raise TimeoutError("program generation exhausted the shared wall-time budget")
            chunks.append(
                self._generate(
                    PROGRAM_SYSTEM_PROMPT,
                    prompt,
                    history,
                    count=chunk_count,
                    max_new_tokens=max_new_tokens,
                    max_wall_seconds=wall_remaining,
                )
            )
            remaining_count -= chunk_count
        result = GenerationResult(
            texts=tuple(text for chunk in chunks for text in chunk.texts),
            output_tokens=sum(chunk.output_tokens for chunk in chunks),
            elapsed_seconds=sum(chunk.elapsed_seconds for chunk in chunks),
            peak_vram_gb=max(
                (chunk.peak_vram_gb for chunk in chunks if chunk.peak_vram_gb is not None),
                default=None,
            ),
            sequence_token_counts=tuple(
                value for chunk in chunks for value in chunk.sequence_token_counts
            ),
            hit_token_limit=tuple(
                value for chunk in chunks for value in chunk.hit_token_limit
            ),
        )
        return GenerationResult(
            texts=tuple(extract_python(text) for text in result.texts),
            output_tokens=result.output_tokens,
            elapsed_seconds=result.elapsed_seconds,
            peak_vram_gb=result.peak_vram_gb,
            sequence_token_counts=result.sequence_token_counts,
            hit_token_limit=result.hit_token_limit,
        )

    def direct_action(
        self,
        history: Any,
        valid_actions: Sequence[str],
        *,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[dict[str, Any], GenerationResult]:
        result = self._generate(
            DIRECT_SYSTEM_PROMPT,
            direct_prompt(history, valid_actions),
            history,
            count=1,
            max_new_tokens=min(256, max_new_tokens) if max_new_tokens is not None else 256,
            max_wall_seconds=max_wall_seconds,
        )
        try:
            action = parse_action_json(result.texts[0])
        except ValueError:
            action = {}
        return action, result

    def _generate(
        self,
        system_prompt: str,
        text_prompt: str,
        history: Sequence[Any],
        *,
        count: int,
        max_new_tokens: int | None = None,
        max_wall_seconds: float | None = None,
    ) -> GenerationResult:
        total_started = time.perf_counter()
        self.load()
        assert self._torch is not None
        assert self._processor is not None
        assert self._model is not None
        content = _multimodal_content(history, text_prompt)
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": content},
        ]
        inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            enable_thinking=False,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        input_length = int(inputs["input_ids"].shape[-1])
        generation_limit = (
            self.profile.settings.max_new_tokens
            if max_new_tokens is None
            else max_new_tokens
        )
        _validate_context_budget(
            input_length,
            generation_limit,
            self.profile.settings.context_length,
        )

        device = next(self._model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        stopping_criteria = None
        if max_wall_seconds is not None:
            remaining = max_wall_seconds - (time.perf_counter() - total_started)
            if remaining <= 0:
                raise TimeoutError("model wall-time budget expired before generation")
            from transformers import MaxTimeCriteria, StoppingCriteriaList

            stopping_criteria = StoppingCriteriaList([MaxTimeCriteria(remaining)])
        started = time.perf_counter()
        try:
            with self._torch.inference_mode():
                outputs = self._model.generate(
                    **inputs,
                    do_sample=True,
                    temperature=self.profile.settings.temperature,
                    top_p=self.profile.settings.top_p,
                    max_new_tokens=generation_limit,
                    num_return_sequences=count,
                    stopping_criteria=stopping_criteria,
                )
        except self._torch.OutOfMemoryError as exc:
            if self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
            limit = self.profile.max_peak_vram_gb
            detail = "available CUDA memory" if limit is None else f"{limit:.3f} GiB budget"
            raise RuntimeError(f"CUDA allocation exceeded the configured {detail}") from exc
        if self._torch.cuda.is_available():
            self._torch.cuda.synchronize()
        elapsed = max(time.perf_counter() - started, 1e-9)
        generated = outputs[:, input_length:]
        texts = tuple(self._processor.batch_decode(generated, skip_special_tokens=True))
        token_counts, hit_token_limit = _sequence_token_counts(
            generated,
            eos_token_id=getattr(self._model.generation_config, "eos_token_id", None),
            pad_token_id=getattr(self._model.generation_config, "pad_token_id", None),
            max_new_tokens=generation_limit,
        )
        peak = None
        if self._torch.cuda.is_available():
            peak = self._torch.cuda.max_memory_allocated() / 1024**3
            if (
                self.profile.max_peak_vram_gb is not None
                and peak > self.profile.max_peak_vram_gb
            ):
                raise RuntimeError(
                    f"CUDA peak {peak:.3f} GiB exceeded configured "
                    f"{self.profile.max_peak_vram_gb:.3f} GiB budget"
                )
        return GenerationResult(
            texts,
            sum(token_counts),
            elapsed,
            peak,
            token_counts,
            hit_token_limit,
        )


def backend_from_config(
    config: Any, *, model_path: str | Path | None = None
) -> TransformersQwenBackend:
    """Create the lazy backend from a validated SystemConfig-like object."""

    if config.model is None:
        raise ValueError("selected configuration has no model section")
    if config.experiment.prompt_contract_version != PROMPT_CONTRACT_VERSION:
        raise ValueError(
            "configuration prompt contract does not match the implemented prompt"
        )
    if config.experiment.prompt_contract_sha256 != PROMPT_CONTRACT_SHA256:
        raise ValueError(
            "configuration prompt contract fingerprint does not match the implemented prompt"
        )
    if config.experiment.perception_contract_version != PERCEPTION_CONTRACT_VERSION:
        raise ValueError(
            "configuration perception contract does not match the implemented renderer"
        )
    if config.experiment.perception_contract_sha256 != PERCEPTION_CONTRACT_SHA256:
        raise ValueError(
            "configuration perception contract fingerprint does not match the implemented renderer"
        )
    if (
        config.model.expected_revision is None
        or config.model.expected_weight_manifest_sha256 is None
    ):
        raise ValueError("model configuration must freeze revision and weight manifest")
    if model_path is None:
        raise ValueError("model_path is required to verify the frozen model artifact")
    artifact = inspect_model_artifact(model_path)
    if artifact.revision != config.model.expected_revision:
        raise ValueError("local model revision does not match the frozen configuration")
    if artifact.weight_manifest_sha256 != config.model.expected_weight_manifest_sha256:
        raise ValueError("local model weight manifest does not match the frozen configuration")
    profile = ModelProfile(
        model_id=config.model.id,
        quantization=config.model.quantization,
        compute_dtype=config.model.compute_dtype,
        offline=config.model.offline,
        seed=config.experiment.seed,
        max_batch_sequences=config.model.max_batch_sequences,
        max_peak_vram_gb=config.model.max_peak_vram_gb,
        settings=GenerationSettings(
            temperature=config.generation.temperature,
            top_p=config.generation.top_p,
            max_new_tokens=config.generation.max_new_tokens_per_hypothesis,
            context_length=config.model.context_length,
        ),
    )
    return TransformersQwenBackend(profile, model_path=model_path)


def _history_grids(history: Any) -> tuple[Any, ...]:
    """Return every available frame oldest-to-newest without duplicating the latest."""

    if hasattr(history, "frames"):
        return tuple(history.frames)[-8:]
    entries = tuple(history)[-8:]
    grids = tuple(getattr(entry, "grid", None) for entry in entries)
    if any(grid is None for grid in grids):
        raise ValueError("every prompt history entry must contain a grid")
    return grids


def _multimodal_content(history: Any, text_prompt: str) -> list[dict[str, Any]]:
    """Build ordered image blocks followed by exactly one textual request."""

    content = [
        {"type": "image", "image": render_grid_pil(grid)}
        for grid in _history_grids(history)
    ]
    content.append({"type": "text", "text": text_prompt})
    return content


def _validate_context_budget(
    input_tokens: int, output_tokens: int, context_length: int
) -> None:
    """Fail before CUDA transfer when a request cannot fit the declared context."""

    if input_tokens < 0:
        raise ValueError("input token count cannot be negative")
    if output_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    if context_length < 1:
        raise ValueError("context length must be positive")
    if input_tokens + output_tokens > context_length:
        raise RuntimeError(
            f"prompt ({input_tokens}) plus output budget ({output_tokens}) exceeds "
            f"context budget {context_length}"
        )


def _cuda_memory_fraction(max_peak_vram_gb: float | None, total_memory: int) -> float | None:
    """Translate an explicit GiB cap into PyTorch's per-process allocator fraction."""

    if max_peak_vram_gb is None:
        return None
    if max_peak_vram_gb <= 0:
        raise ValueError("max_peak_vram_gb must be positive when supplied")
    if total_memory <= 0:
        raise ValueError("total CUDA memory must be positive")
    return min(1.0, max_peak_vram_gb * 1024**3 / total_memory)


def _count_generated_tokens(
    generated: Any, *, eos_token_id: int | list[int] | None, pad_token_id: int | None
) -> int:
    """Count real generated tokens without charging batch padding as model output."""

    counts, _ = _sequence_token_counts(
        generated,
        eos_token_id=eos_token_id,
        pad_token_id=pad_token_id,
        max_new_tokens=None,
    )
    return sum(counts)


def _sequence_token_counts(
    generated: Any,
    *,
    eos_token_id: int | list[int] | None,
    pad_token_id: int | None,
    max_new_tokens: int | None,
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    eos_ids = {eos_token_id} if isinstance(eos_token_id, int) else set(eos_token_id or ())
    counts: list[int] = []
    limit_flags: list[bool] = []
    for row in generated.tolist():
        count = 0
        terminated = False
        for token_id in row:
            if token_id in eos_ids:
                count += 1
                terminated = True
                break
            if pad_token_id is not None and token_id == pad_token_id:
                terminated = True
                break
            count += 1
        counts.append(count)
        limit_flags.append(
            max_new_tokens is not None and count >= max_new_tokens and not terminated
        )
    return tuple(counts), tuple(limit_flags)
