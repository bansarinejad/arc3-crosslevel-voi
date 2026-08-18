"""Build the zero-result action-QBC v8 registration from staged Git objects."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final, cast


class RegistrationError(RuntimeError):
    """Raised when the frozen registration cannot be produced exactly."""


def _load_independent_reconstructor() -> ModuleType:
    path = Path(__file__).with_name("reconstruct_action_qbc_v8_open_registration.py")
    spec = importlib.util.spec_from_file_location("_action_qbc_v8_registration_reconstructor", path)
    if spec is None or spec.loader is None:
        raise RegistrationError("cannot load the independent v8 registration reconstructor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_RECONSTRUCTION: Final = _load_independent_reconstructor()

SCHEMA_VERSION: Final = cast(str, _RECONSTRUCTION.SCHEMA_VERSION)
STATUS: Final = cast(str, _RECONSTRUCTION.STATUS)
TREATMENT_ID: Final = cast(str, _RECONSTRUCTION.TREATMENT_ID)
DIAGNOSTIC_SYSTEM_ID: Final = cast(str, _RECONSTRUCTION.DIAGNOSTIC_SYSTEM_ID)
COMPARISON_SEMANTICS_ID: Final = cast(str, _RECONSTRUCTION.COMPARISON_SEMANTICS_ID)
PREREGISTRATION_TAG: Final = cast(str, _RECONSTRUCTION.PREREGISTRATION_TAG)
PREREGISTRATION_COMMIT: Final = cast(str, _RECONSTRUCTION.PREREGISTRATION_COMMIT)
PREREGISTRATION_DOCUMENT: Final = cast(str, _RECONSTRUCTION.PREREGISTRATION_DOCUMENT)
OPEN_FREEZE_TAG: Final = cast(str, _RECONSTRUCTION.OPEN_FREEZE_TAG)
OUTPUT_PATH: Final = cast(str, _RECONSTRUCTION.OUTPUT_PATH)
REGISTRATION_PATH: Final = OUTPUT_PATH
NON_REGISTRATION_ADDITIONS: Final = cast(
    tuple[str, ...], _RECONSTRUCTION.NON_REGISTRATION_ADDITIONS
)
ALL_ADDITIONS: Final = cast(tuple[str, ...], _RECONSTRUCTION.ALL_ADDITIONS)
AUTHORIZATION: Final = cast(dict[str, bool], _RECONSTRUCTION.AUTHORIZATION)


def canonical_json_bytes(value: object) -> bytes:
    return cast(bytes, _RECONSTRUCTION.canonical_json_bytes(value))


def canonical_sha256(value: object) -> str:
    return cast(str, _RECONSTRUCTION.canonical_sha256(value))


def build_registration(
    repository_root: str | Path,
    preregistration_tag: str = PREREGISTRATION_TAG,
) -> dict[str, object]:
    """Reconstruct the complete registration while exactly fourteen additions are staged."""

    if preregistration_tag != PREREGISTRATION_TAG:
        raise RegistrationError("only the frozen v8 preregistration tag is accepted")
    try:
        return cast(dict[str, object], _RECONSTRUCTION.build_registration(repository_root))
    except _RECONSTRUCTION.ReconstructionError as error:
        raise RegistrationError(str(error)) from error


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _open_parent(root: Path, relative: str) -> tuple[int, str]:
    if os.name != "posix":
        raise RegistrationError("registration publication requires the registered Linux host")
    parts = relative.split("/")
    if (
        len(parts) < 2
        or any(not part or part in {".", ".."} or "/" in part or "\x00" in part for part in parts)
    ):
        raise RegistrationError("registration output is not a canonical relative path")
    descriptor = os.open(root, _directory_flags())
    try:
        for component in parts[:-1]:
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RegistrationError("registration parent is not an owner-controlled directory")
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _exclusive_write(root: Path, relative: str, raw: bytes) -> None:
    parent_descriptor, basename = _open_parent(root, relative)
    parent_before = os.fstat(parent_descriptor)
    descriptor: int | None = None
    created_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            basename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_descriptor,
        )
        created = os.fstat(descriptor)
        if not stat.S_ISREG(created.st_mode) or stat.S_IMODE(created.st_mode) != 0o600:
            raise RegistrationError("registration destination is not a private regular file")
        created_identity = (created.st_dev, created.st_ino)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        reopened = os.open(
            basename,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_descriptor,
        )
        try:
            reopened_metadata = os.fstat(reopened)
            if (
                created_identity != (reopened_metadata.st_dev, reopened_metadata.st_ino)
                or not stat.S_ISREG(reopened_metadata.st_mode)
                or reopened_metadata.st_size != len(raw)
            ):
                raise RegistrationError("registration destination changed during publication")
            chunks: list[bytes] = []
            remaining = len(raw) + 1
            while remaining:
                chunk = os.read(reopened, min(1 << 20, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if b"".join(chunks) != raw:
                raise RegistrationError("registration destination bytes did not round-trip")
        finally:
            os.close(reopened)
        os.fsync(parent_descriptor)
        parent_after = os.fstat(parent_descriptor)
        if (
            parent_before.st_dev,
            parent_before.st_ino,
            parent_before.st_uid,
            stat.S_IMODE(parent_before.st_mode),
        ) != (
            parent_after.st_dev,
            parent_after.st_ino,
            parent_after.st_uid,
            stat.S_IMODE(parent_after.st_mode),
        ):
            raise RegistrationError("registration parent changed during publication")
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if created_identity is not None:
            with contextlib.suppress(OSError):
                candidate = os.stat(basename, dir_fd=parent_descriptor, follow_symlinks=False)
                if (
                    stat.S_ISREG(candidate.st_mode)
                    and (candidate.st_dev, candidate.st_ino) == created_identity
                ):
                    os.unlink(basename, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
        raise
    finally:
        os.close(parent_descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--preregistration-tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repository_root.resolve(strict=True)
    if args.output.as_posix() != OUTPUT_PATH:
        raise RegistrationError("registration has one canonical repository output path")
    output = root / OUTPUT_PATH
    if output.exists() or output.is_symlink():
        raise RegistrationError("registration output already exists and is never overwritten")
    registration = build_registration(root, args.preregistration_tag)
    raw = canonical_json_bytes(registration)
    _exclusive_write(root, OUTPUT_PATH, raw)
    summary = {
        "content_sha256": registration["content_sha256"],
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "output": OUTPUT_PATH,
        "row_count": cast(dict[str, object], registration["row_inventory"])["count"],
        "status": STATUS,
    }
    sys.stdout.buffer.write(canonical_json_bytes(summary) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RegistrationError, OSError, ValueError, json.JSONDecodeError) as error:
        sys.stderr.buffer.write(
            canonical_json_bytes({"error": str(error), "status": "refused"}) + b"\n"
        )
        raise SystemExit(2) from error
