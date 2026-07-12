"""Compact provenance fingerprints for local model snapshots."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WeightFileInfo:
    filename: str
    size_bytes: int
    etag_sha256: str


@dataclass(frozen=True, slots=True)
class ModelArtifactInfo:
    revision: str | None
    weight_manifest_sha256: str | None
    weight_files: tuple[WeightFileInfo, ...]


@dataclass(frozen=True, slots=True)
class GitProvenance:
    repository_root: str
    commit: str | None
    dirty: bool | None
    status_sha256: str | None
    tracked_diff_sha256: str | None


def inspect_model_artifact(path: str | Path | None) -> ModelArtifactInfo:
    """Read Hugging Face download metadata without hashing multi-gigabyte weights."""

    if path is None:
        return ModelArtifactInfo(None, None, ())
    root = Path(path)
    metadata_root = root / ".cache" / "huggingface" / "download"
    entries: list[WeightFileInfo] = []
    revisions: set[str] = set()
    for metadata_path in sorted(metadata_root.glob("*.safetensors.metadata")):
        lines = metadata_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            continue
        revision, etag = lines[0].strip(), lines[1].strip().lower()
        filename = metadata_path.name.removesuffix(".metadata")
        weight_path = root / filename
        if (
            not weight_path.is_file()
            or len(etag) != 64
            or any(character not in "0123456789abcdef" for character in etag)
        ):
            continue
        if revision:
            revisions.add(revision)
        entries.append(WeightFileInfo(filename, weight_path.stat().st_size, etag))
    if not entries:
        return ModelArtifactInfo(next(iter(revisions), None), None, ())
    payload = json.dumps(
        [asdict(entry) for entry in entries],
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    resolved_revision = next(iter(revisions)) if len(revisions) == 1 else None
    return ModelArtifactInfo(
        resolved_revision, hashlib.sha256(payload).hexdigest(), tuple(entries)
    )


def inspect_git_provenance(repository: str | Path | None = None) -> GitProvenance:
    """Record HEAD plus deterministic dirty-tree diagnostics from the repository root."""

    root = (
        Path(repository).resolve()
        if repository is not None
        else Path(__file__).resolve().parents[2]
    )
    command_prefix = ["git", "-c", f"safe.directory={root.as_posix()}"]
    try:
        commit = subprocess.run(
            [*command_prefix, "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            [*command_prefix, "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.replace("\r\n", "\n")
        tracked_diff = subprocess.run(
            [*command_prefix, "diff", "--binary", "HEAD", "--", "."],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return GitProvenance(root.as_posix(), None, None, None, None)
    return GitProvenance(
        repository_root=root.as_posix(),
        commit=commit or None,
        dirty=bool(status),
        status_sha256=hashlib.sha256(status.encode("utf-8")).hexdigest(),
        tracked_diff_sha256=hashlib.sha256(tracked_diff).hexdigest(),
    )


__all__ = [
    "GitProvenance",
    "ModelArtifactInfo",
    "WeightFileInfo",
    "inspect_git_provenance",
    "inspect_model_artifact",
]
