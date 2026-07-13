"""Exclusively freeze the reviewed data-only action-QBC lockbox manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import types
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CANONICAL_WRAPPER_SOURCE = Path("scripts/freeze_action_qbc_lockbox.py")
CANONICAL_RELATIVE_OUTPUT = Path("artifacts/action_conditional_qbc_v1_lockbox.json")
CANONICAL_STAGING_OUTPUT = Path(
    "artifacts/.action_conditional_qbc_v1_lockbox.json.staging"
)
CANONICAL_PROBE_OUTPUT = Path("artifacts/.action_conditional_qbc_v1_lockbox.json.probe")
CANONICAL_GENERATOR_SOURCE = Path("src/arc3_voi/action_qbc_lockbox.py")
CANONICAL_PREREGISTRATION = Path(
    "docs/experiment_amendment_2026-07-13_action_conditional_qbc_v1.md"
)
PREREGISTRATION_COMMIT = "1477f8a04ab17adf0bd78b4e98accee3c846aa36"
PREREGISTRATION_FILE_SHA256 = (
    "aba4f9639242922a5be53fecb2e9a1833eec353a84ffc1c1476aad9bad5725ce"
)
PREREGISTRATION_GIT_BLOB_OID = "d1b23227ab44f619c89545e6453946efc3c1c3f9"
PREREGISTRATION_TAG = "prereg-action-conditional-outcome-qbc-v1"
RESERVATION_MARKER = b"arc3-action-conditional-qbc-v1-publication-reservation\n"

_MODULE_FILE = Path(os.path.abspath(__file__))
ROOT = _MODULE_FILE.parent.parent


class FreezePreconditionError(RuntimeError):
    """Raised before registered seed evaluation when freeze provenance is not exact."""


@dataclass(frozen=True, slots=True)
class VerifiedSource:
    """Exact reviewed source bytes and repository identities."""

    raw: bytes
    head: str
    source_sha256: str
    wrapper_sha256: str


@dataclass(slots=True)
class PublicationReservation:
    """Exclusive publication capability acquired before registered evaluation."""

    fd: int
    output: Path
    staging: Path
    probe: Path
    parent_identity: tuple[int, int]
    staging_identity: tuple[int, int]
    published: bool = False


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _artifact_json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _normalized_absolute(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _is_reparse(value: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(value, "st_file_attributes", 0)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _require_plain_path(path: Path, *, directory: bool) -> os.stat_result:
    try:
        result = os.lstat(path)
    except OSError as error:
        raise FreezePreconditionError(f"required canonical path is unavailable: {path}") from error
    if _is_reparse(result):
        raise FreezePreconditionError(f"symlink/junction/reparse path is forbidden: {path}")
    correct_kind = stat.S_ISDIR(result.st_mode) if directory else stat.S_ISREG(result.st_mode)
    if not correct_kind:
        expected = "directory" if directory else "regular file"
        raise FreezePreconditionError(f"canonical path is not a {expected}: {path}")
    return result


def _require_relative_path_chain(
    root: Path,
    relative: Path,
    *,
    leaf_directory: bool,
) -> os.stat_result:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise FreezePreconditionError(f"invalid canonical relative path: {relative}")
    _require_plain_path(root, directory=True)
    current = root
    result: os.stat_result | None = None
    for index, part in enumerate(relative.parts):
        current = current / part
        result = _require_plain_path(
            current,
            directory=leaf_directory if index == len(relative.parts) - 1 else True,
        )
    if result is None:  # pragma: no cover - guarded by the nonempty-parts check
        raise FreezePreconditionError("empty canonical relative path")
    return result


def _require_isolated_runtime() -> None:
    if not (
        sys.flags.isolated
        and sys.flags.no_site
        and sys.flags.dont_write_bytecode
    ):
        raise FreezePreconditionError(
            "freeze requires an isolated interpreter: python -I -S -B"
        )


def _git(
    *arguments: str, root: Path = ROOT, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("git", *arguments),
        cwd=root,
        check=check,
        capture_output=True,
    )


def require_canonical_output(
    requested: Path,
    *,
    root: Path = ROOT,
    working_directory: Path | None = None,
) -> Path:
    """Return the lexical canonical leaf without resolving or following it."""

    current = Path.cwd() if working_directory is None else working_directory
    root_absolute = _normalized_absolute(root)
    if _normalized_absolute(current) != root_absolute:
        raise FreezePreconditionError("lockbox freeze must run from the lexical repository root")
    if requested != CANONICAL_RELATIVE_OUTPUT or requested.is_absolute():
        raise FreezePreconditionError(
            f"noncanonical lockbox output refused: expected {CANONICAL_RELATIVE_OUTPUT.as_posix()}"
        )
    output = root / requested
    output_absolute = _normalized_absolute(output)
    try:
        common = os.path.commonpath((root_absolute, output_absolute))
    except ValueError as error:
        raise FreezePreconditionError("canonical output escaped the repository volume") from error
    if common != root_absolute:
        raise FreezePreconditionError("canonical output escaped the repository root")
    _require_relative_path_chain(
        root,
        CANONICAL_RELATIVE_OUTPUT.parent,
        leaf_directory=True,
    )
    if os.path.lexists(output):
        raise FileExistsError(f"refusing to replace frozen lockbox artifact: {output}")
    return output


def _validate_lower_hex(value: str, length: int, *, field: str) -> None:
    if len(value) != length or any(character not in "0123456789abcdef" for character in value):
        raise FreezePreconditionError(f"{field} must be a {length}-character lowercase hex digest")


def require_canonical_invocation(*, root: Path = ROOT) -> None:
    """Reject alternate wrapper paths and any reparse point in canonical inputs."""

    expected_wrapper = root / CANONICAL_WRAPPER_SOURCE
    if _normalized_absolute(_MODULE_FILE) != _normalized_absolute(expected_wrapper):
        raise FreezePreconditionError("wrapper was invoked through a noncanonical path")
    if _normalized_absolute(Path.cwd()) != _normalized_absolute(root):
        raise FreezePreconditionError("wrapper must run from the lexical repository root")
    for relative in (
        CANONICAL_WRAPPER_SOURCE,
        CANONICAL_GENERATOR_SOURCE,
        CANONICAL_PREREGISTRATION,
    ):
        _require_relative_path_chain(root, relative, leaf_directory=False)
    _require_relative_path_chain(
        root,
        CANONICAL_RELATIVE_OUTPUT.parent,
        leaf_directory=True,
    )


def require_reviewed_clean_source(
    *,
    reviewed_head: str,
    reviewed_generator_source_sha256: str,
    root: Path = ROOT,
) -> VerifiedSource:
    """Bind the sole registered evaluation to a clean reviewed source commit."""

    _validate_lower_hex(reviewed_head, 40, field="reviewed HEAD")
    _validate_lower_hex(
        reviewed_generator_source_sha256,
        64,
        field="reviewed generator source SHA-256",
    )
    status = _git("status", "--porcelain=v1", "--untracked-files=all", root=root).stdout
    if status:
        raise FreezePreconditionError("registered lockbox freeze requires a clean worktree")
    head = _git("rev-parse", "HEAD", root=root).stdout.decode().strip()
    if head != reviewed_head:
        raise FreezePreconditionError("current HEAD does not equal the explicitly reviewed commit")
    tag_commit = (
        _git("rev-parse", f"{PREREGISTRATION_TAG}^{{commit}}", root=root).stdout.decode().strip()
    )
    if tag_commit != PREREGISTRATION_COMMIT:
        raise FreezePreconditionError("frozen preregistration tag identity mismatch")
    tag_blob_oid = (
        _git(
            "rev-parse",
            f"{PREREGISTRATION_TAG}:{CANONICAL_PREREGISTRATION.as_posix()}",
            root=root,
        )
        .stdout.decode()
        .strip()
    )
    if tag_blob_oid != PREREGISTRATION_GIT_BLOB_OID:
        raise FreezePreconditionError("frozen preregistration Git blob OID mismatch")
    ancestor = _git(
        "merge-base",
        "--is-ancestor",
        PREREGISTRATION_COMMIT,
        head,
        root=root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise FreezePreconditionError(
            "reviewed generator commit does not descend from preregistration"
        )

    source_path = root / CANONICAL_GENERATOR_SOURCE
    preregistration_path = root / CANONICAL_PREREGISTRATION
    wrapper_path = root / CANONICAL_WRAPPER_SOURCE
    _require_relative_path_chain(root, CANONICAL_GENERATOR_SOURCE, leaf_directory=False)
    _require_relative_path_chain(root, CANONICAL_PREREGISTRATION, leaf_directory=False)
    _require_relative_path_chain(root, CANONICAL_WRAPPER_SOURCE, leaf_directory=False)
    source_raw = source_path.read_bytes()
    if _sha256(source_raw) != reviewed_generator_source_sha256:
        raise FreezePreconditionError(
            "working generator source hash differs from reviewed identity"
        )
    committed_source = _git(
        "show", f"{head}:{CANONICAL_GENERATOR_SOURCE.as_posix()}", root=root
    ).stdout
    if committed_source != source_raw:
        raise FreezePreconditionError("generator bytes do not equal the reviewed committed blob")
    preregistration_raw = preregistration_path.read_bytes()
    if _sha256(preregistration_raw) != PREREGISTRATION_FILE_SHA256:
        raise FreezePreconditionError("immutable preregistration file SHA-256 mismatch")
    committed_preregistration = _git(
        "show", f"{head}:{CANONICAL_PREREGISTRATION.as_posix()}", root=root
    ).stdout
    if committed_preregistration != preregistration_raw:
        raise FreezePreconditionError("preregistration bytes differ from the reviewed commit")
    wrapper_raw = wrapper_path.read_bytes()
    committed_wrapper = _git(
        "show", f"{head}:{CANONICAL_WRAPPER_SOURCE.as_posix()}", root=root
    ).stdout
    if committed_wrapper != wrapper_raw:
        raise FreezePreconditionError("wrapper bytes differ from the reviewed commit")
    return VerifiedSource(
        raw=source_raw,
        head=head,
        source_sha256=reviewed_generator_source_sha256,
        wrapper_sha256=_sha256(wrapper_raw),
    )


def _unlink_if_present(path: Path) -> None:
    with suppress(FileNotFoundError):
        os.unlink(path)


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("zero-byte write to reserved publication descriptor")
        remaining = remaining[written:]


def _read_all(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _remove_unpublished_paths(paths: tuple[Path, ...]) -> None:
    errors: list[OSError] = []
    for path in paths:
        try:
            _unlink_if_present(path)
        except OSError as error:
            errors.append(error)
    remaining = [path for path in paths if os.path.lexists(path)]
    if errors or remaining:
        detail = ", ".join(os.fspath(path) for path in remaining) or "unlink error"
        raise FreezePreconditionError(
            f"failed to clean unpublished lockbox staging paths: {detail}"
        ) from (errors[0] if errors else None)


def reserve_publication(
    output: Path,
    *,
    root: Path = ROOT,
) -> PublicationReservation:
    """Reserve the sole canonical leaf before loading the reviewed generator."""

    expected = root / CANONICAL_RELATIVE_OUTPUT
    if _normalized_absolute(output) != _normalized_absolute(expected):
        raise FreezePreconditionError("publication reservation received a noncanonical leaf")
    parent_stat = _require_relative_path_chain(
        root,
        CANONICAL_RELATIVE_OUTPUT.parent,
        leaf_directory=True,
    )
    staging = root / CANONICAL_STAGING_OUTPUT
    probe = root / CANONICAL_PROBE_OUTPUT
    for path in (output, staging, probe):
        if os.path.lexists(path):
            raise FileExistsError(f"lockbox publication path already exists: {path}")

    descriptor = -1
    try:
        descriptor = os.open(
            staging,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        _write_all(descriptor, RESERVATION_MARKER)
        os.fsync(descriptor)
        staging_stat = _require_plain_path(staging, directory=False)
        descriptor_identity = _identity(os.fstat(descriptor))
        if _identity(staging_stat) != descriptor_identity:
            raise FreezePreconditionError("staging descriptor/path identity mismatch")

        os.link(staging, probe)
        probe_stat = _require_plain_path(probe, directory=False)
        if _identity(probe_stat) != descriptor_identity:
            raise FreezePreconditionError("hard-link publication probe changed file identity")
        with probe.open("rb") as handle:
            if handle.read() != RESERVATION_MARKER:
                raise FreezePreconditionError("hard-link publication probe changed bytes")
        os.unlink(probe)
        if os.path.lexists(probe):
            raise FreezePreconditionError("hard-link publication probe was not removed")
        if _identity(os.fstat(descriptor)) != descriptor_identity:
            raise FreezePreconditionError("reserved descriptor identity changed during preflight")
        return PublicationReservation(
            fd=descriptor,
            output=output,
            staging=staging,
            probe=probe,
            parent_identity=_identity(parent_stat),
            staging_identity=descriptor_identity,
        )
    except BaseException:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        _remove_unpublished_paths((probe, staging))
        raise


def abort_publication(reservation: PublicationReservation) -> None:
    """Best-effort cleanup before publication; the canonical leaf remains absent."""

    if reservation.fd >= 0:
        with suppress(OSError):
            os.close(reservation.fd)
        reservation.fd = -1
    _remove_unpublished_paths((reservation.probe, reservation.staging))


def load_reviewed_generator(verified: VerifiedSource, *, root: Path = ROOT) -> Any:
    """Execute only the source bytes already bound to the reviewed Git commit."""

    if _sha256(verified.raw) != verified.source_sha256:
        raise FreezePreconditionError("verified generator source bytes changed in memory")
    canonical_path = root / CANONICAL_GENERATOR_SOURCE
    wrapper_path = root / CANONICAL_WRAPPER_SOURCE
    if _sha256(wrapper_path.read_bytes()) != verified.wrapper_sha256:
        raise FreezePreconditionError(
            "verified wrapper source bytes changed after provenance check"
        )
    module_name = "_arc3_voi_action_qbc_lockbox_reviewed"
    if module_name in sys.modules:
        raise FreezePreconditionError("private reviewed-generator module name is already occupied")
    module = types.ModuleType(module_name)
    module.__file__ = os.fspath(canonical_path)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        code = compile(
            verified.raw,
            os.fspath(canonical_path),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__)
        if (
            module.PREREGISTRATION_COMMIT != PREREGISTRATION_COMMIT
            or module.PREREGISTRATION_FILE_SHA256 != PREREGISTRATION_FILE_SHA256
            or module.PREREGISTRATION_GIT_BLOB_OID != PREREGISTRATION_GIT_BLOB_OID
        ):
            raise FreezePreconditionError("reviewed generator preregistration constants drifted")
        contract_hash = module.GENERATOR_CONTRACT_SHA256
        _validate_lower_hex(contract_hash, 64, field="generator contract SHA-256")
        if module.canonical_sha256(module.GENERATOR_CONTRACT) != contract_hash:
            raise FreezePreconditionError("reviewed generator contract hash is inconsistent")
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def publish_reserved_artifact(
    reservation: PublicationReservation,
    payload: bytes,
    *,
    root: Path = ROOT,
) -> None:
    """Fill and hard-link the retained staging inode into the canonical leaf exactly once."""

    if reservation.published or reservation.fd < 0:
        raise FreezePreconditionError("publication reservation is no longer active")
    parent_stat = _require_relative_path_chain(
        root,
        CANONICAL_RELATIVE_OUTPUT.parent,
        leaf_directory=True,
    )
    if _identity(parent_stat) != reservation.parent_identity:
        raise FreezePreconditionError("canonical artifact directory identity changed")
    staging_stat = _require_plain_path(reservation.staging, directory=False)
    descriptor_stat = os.fstat(reservation.fd)
    if (
        _identity(staging_stat) != reservation.staging_identity
        or _identity(descriptor_stat) != reservation.staging_identity
    ):
        raise FreezePreconditionError("reserved staging identity changed")
    if os.path.lexists(reservation.output):
        raise FileExistsError(f"refusing to replace frozen lockbox artifact: {reservation.output}")

    os.lseek(reservation.fd, 0, os.SEEK_SET)
    os.ftruncate(reservation.fd, 0)
    _write_all(reservation.fd, payload)
    os.fsync(reservation.fd)
    if _identity(os.fstat(reservation.fd)) != reservation.staging_identity:
        raise FreezePreconditionError("reserved descriptor changed after payload write")
    if _identity(_require_plain_path(reservation.staging, directory=False)) != (
        reservation.staging_identity
    ):
        raise FreezePreconditionError("staging path changed after payload write")
    staged_payload = _read_all(reservation.fd)
    if staged_payload != payload or _sha256(staged_payload) != _sha256(payload):
        raise FreezePreconditionError("reserved staging bytes differ from serialized payload")
    parent_stat = _require_relative_path_chain(
        root,
        CANONICAL_RELATIVE_OUTPUT.parent,
        leaf_directory=True,
    )
    if _identity(parent_stat) != reservation.parent_identity:
        raise FreezePreconditionError("canonical artifact directory changed before publication")
    if os.path.lexists(reservation.probe):
        raise FileExistsError("hard-link publication probe reappeared before publication")
    if os.path.lexists(reservation.output):
        raise FileExistsError(f"refusing raced frozen artifact: {reservation.output}")

    try:
        os.link(reservation.staging, reservation.output)
        output_stat = _require_plain_path(reservation.output, directory=False)
        if _identity(output_stat) != reservation.staging_identity:
            raise FreezePreconditionError("canonical hard link has the wrong file identity")
        with reservation.output.open("rb") as handle:
            if _identity(os.fstat(handle.fileno())) != reservation.staging_identity:
                raise FreezePreconditionError("canonical output handle has the wrong identity")
            canonical_payload = _read_all(handle.fileno())
        final_stat = _require_plain_path(reservation.output, directory=False)
        if _identity(final_stat) != reservation.staging_identity:
            raise FreezePreconditionError("canonical output identity changed during verification")
        if canonical_payload != payload or _sha256(canonical_payload) != _sha256(payload):
            raise FreezePreconditionError("canonical output bytes differ from serialized payload")
        # This is the publication commit point. Keep it inside the rollback-protected
        # region so an interruption before the assignment cannot strand the link.
        reservation.published = True
    except BaseException:
        reservation.published = False
        try:
            current = os.lstat(reservation.output)
            if (
                not _is_reparse(current)
                and stat.S_ISREG(current.st_mode)
                and _identity(current) == reservation.staging_identity
            ):
                os.unlink(reservation.output)
        except FileNotFoundError:
            pass
        except OSError as rollback_error:
            raise FreezePreconditionError(
                "publication failed and canonical rollback was unsuccessful"
            ) from rollback_error
        raise
    # A fully adversarial same-user writer cannot be excluded with portable stdlib file
    # handles. The exact post-link readback closes detectable mutation before success.
    with suppress(OSError):
        os.close(reservation.fd)
    reservation.fd = -1
    for path in (reservation.probe, reservation.staging):
        # The canonical hard link is already durable; cleanup cannot turn success into error.
        with suppress(OSError):
            _unlink_if_present(path)


def require_manifest_provenance(
    manifest: dict[str, Any], verified: VerifiedSource
) -> None:
    """Independently bind emitted provenance to the source bytes reviewed by this wrapper."""

    provenance = manifest.get("registration_provenance")
    expected = {
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "preregistration_file_sha256": PREREGISTRATION_FILE_SHA256,
        "preregistration_git_blob_oid": PREREGISTRATION_GIT_BLOB_OID,
        "reviewed_generator_commit": verified.head,
        "generator_source_sha256": verified.source_sha256,
    }
    if not isinstance(provenance, dict) or any(
        provenance.get(name) != value for name, value in expected.items()
    ):
        raise FreezePreconditionError(
            "manifest provenance does not match the independently verified source"
        )


def freeze(
    *,
    reviewed_head: str,
    reviewed_generator_source_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    """Validate provenance, evaluate once in memory, then exclusively publish."""

    _require_isolated_runtime()
    require_canonical_invocation(root=ROOT)
    output = require_canonical_output(
        CANONICAL_RELATIVE_OUTPUT,
        root=ROOT,
        working_directory=Path.cwd(),
    )
    verified = require_reviewed_clean_source(
        reviewed_head=reviewed_head,
        reviewed_generator_source_sha256=reviewed_generator_source_sha256,
        root=ROOT,
    )
    reservation = reserve_publication(output, root=ROOT)
    try:
        lockbox = load_reviewed_generator(verified, root=ROOT)
        capability = lockbox._make_registered_freeze_capability(
            preregistration_commit=PREREGISTRATION_COMMIT,
            preregistration_file_sha256=PREREGISTRATION_FILE_SHA256,
            preregistration_git_blob_oid=PREREGISTRATION_GIT_BLOB_OID,
            reviewed_head=reviewed_head,
            generator_source_sha256=reviewed_generator_source_sha256,
        )
        manifest = lockbox._build_registered_lockbox_manifest(capability)
        lockbox.validate_registered_manifest(manifest)
        require_manifest_provenance(manifest, verified)
        payload = _artifact_json_bytes(manifest)
        decoded = json.loads(payload)
        if decoded != manifest or _artifact_json_bytes(decoded) != payload:
            raise FreezePreconditionError("manifest serialization is not canonical and lossless")
        publish_reserved_artifact(reservation, payload, root=ROOT)
        return output, manifest
    except BaseException:
        if not reservation.published:
            abort_publication(reservation)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-head", required=True)
    parser.add_argument("--reviewed-generator-source-sha256", required=True)
    args = parser.parse_args(argv)
    _output, manifest = freeze(
        reviewed_head=args.reviewed_head,
        reviewed_generator_source_sha256=args.reviewed_generator_source_sha256,
    )
    print(
        json.dumps(
            {
                "artifact_sha256": _sha256(_artifact_json_bytes(manifest)),
                "generation_status": manifest["generation_status"],
                "manifest_content_sha256": manifest["content_sha256"],
                "output": CANONICAL_RELATIVE_OUTPUT.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if manifest["generation_status"] == "registered_generation_exhausted" else 0


if __name__ == "__main__":
    raise SystemExit(main())
