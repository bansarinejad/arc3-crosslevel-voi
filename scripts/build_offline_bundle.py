"""Assemble and hash an offline Kaggle runtime bundle.

The script never downloads artifacts. Build the project wheel and wheelhouse separately,
then provide exact local paths. The output manifest records every payload byte plus the
model snapshot's locally observed revision and license declaration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from email.policy import compat32
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "manifest.json"
MANIFEST_DIGEST_NAME = "manifest.sha256"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_metadata(model: Path, model_id: str) -> dict[str, Any]:
    """Read provenance only from files present in the selected snapshot."""

    license_path = model / "LICENSE"
    readme_path = model / "README.md"
    if not license_path.is_file() or not readme_path.is_file():
        raise ValueError("model snapshot must contain README.md and LICENSE")
    declared_license: str | None = None
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, separator, value = line.partition(":")
            if separator and key.strip() == "license":
                declared_license = value.strip() or None
                break

    revisions = set()
    metadata_dir = model / ".cache" / "huggingface" / "download"
    for metadata_path in metadata_dir.glob("*.metadata") if metadata_dir.is_dir() else ():
        metadata_lines = metadata_path.read_text(encoding="utf-8").splitlines()
        if metadata_lines and metadata_lines[0].strip():
            revisions.add(metadata_lines[0].strip())
    if not declared_license:
        raise ValueError("model card has no declared license")
    if len(revisions) != 1:
        raise ValueError("model snapshot must expose one consistent immutable revision")
    revision = next(iter(revisions))
    return {
        "id": model_id,
        "revision": revision,
        "declared_license": declared_license,
        "license_sha256": sha256_file(license_path),
        "provenance_basis": "files packaged in the local model snapshot",
    }


def payload_records(root: Path) -> list[dict[str, Any]]:
    excluded = {MANIFEST_NAME, MANIFEST_DIGEST_NAME}
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        records.append(
            {"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)}
        )
    return records


def wheel_metadata(wheel: Path, license_root: Path) -> dict[str, Any]:
    """Record package metadata and extract exact embedded license/NOTICE files."""

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"wheel must contain one dist-info/METADATA: {wheel.name}")
        message = BytesParser(policy=compat32).parsebytes(archive.read(metadata_names[0]))
        license_names = [
            name
            for name in names
            if not name.endswith("/")
            and (
                ".dist-info/licenses/" in name.lower()
                or PurePosixPath(name).name.lower().startswith(("license", "copying", "notice"))
            )
        ]
        extracted = []
        for name in sorted(license_names):
            member = PurePosixPath(name)
            parts = member.parts
            if (
                member.is_absolute()
                or "\\" in name
                or not parts
                or any(part in {"", ".", ".."} or ":" in part for part in parts)
            ):
                raise ValueError(f"unsafe license member in {wheel.name}: {name}")
            destination = license_root / wheel.name / Path(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            extracted.append(name)
    return {
        "name": message.get("Name"),
        "version": message.get("Version"),
        "license_expression": message.get("License-Expression"),
        "license_field": message.get("License"),
        "wheel": wheel.name,
        "size": wheel.stat().st_size,
        "sha256": sha256_file(wheel),
        "embedded_license_files": extracted,
    }


def write_manifest(root: Path, provenance: dict[str, Any]) -> Path:
    manifest = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "generated_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "provenance": provenance,
        "files": payload_records(root),
    }
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / MANIFEST_DIGEST_NAME).write_text(
        f"{sha256_file(path)}  {MANIFEST_NAME}\n", encoding="ascii"
    )
    return path


def verify_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    digest_path = root / MANIFEST_DIGEST_NAME
    if not path.is_file() or not digest_path.is_file():
        raise ValueError("bundle is missing manifest.json or manifest.sha256")
    expected_manifest = digest_path.read_text(encoding="ascii").split()[0]
    if sha256_file(path) != expected_manifest:
        raise ValueError("manifest digest mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {entry["path"]: entry for entry in manifest["files"]}
    observed = {entry["path"]: entry for entry in payload_records(root)}
    if set(expected) != set(observed):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise ValueError(f"bundle file set mismatch; missing={missing}, extra={extra}")
    for relative, record in expected.items():
        actual = observed[relative]
        if record["size"] != actual["size"] or record["sha256"] != actual["sha256"]:
            raise ValueError(f"payload digest mismatch: {relative}")
    return manifest


def assemble(
    *,
    repository_root: Path,
    project_wheel: Path,
    wheelhouse: Path,
    model: Path,
    model_id: str,
    config: Path,
    output: Path,
) -> Path:
    inputs = (repository_root, project_wheel, wheelhouse, model, config)
    if any(not item.exists() for item in inputs):
        missing = [str(item) for item in inputs if not item.exists()]
        raise FileNotFoundError(f"missing bundle inputs: {missing}")
    if project_wheel.suffix != ".whl":
        raise ValueError("project_wheel must be a built .whl")
    dependency_wheels = sorted(wheelhouse.glob("*.whl"))
    if not dependency_wheels:
        raise ValueError("wheelhouse contains no .whl files")
    if output.exists():
        raise FileExistsError(f"refusing to merge into existing output: {output}")

    output.mkdir(parents=True)
    (output / "code").mkdir()
    shutil.copy2(project_wheel, output / "code" / project_wheel.name)
    shutil.copytree(wheelhouse, output / "wheelhouse", ignore=shutil.ignore_patterns("*.part"))
    shutil.copytree(model, output / "model")
    shutil.copytree(repository_root / "configs", output / "configs")
    shutil.copytree(repository_root / "LICENSES", output / "provenance" / "LICENSES")
    shutil.copytree(repository_root / "kaggle", output / "runtime")
    shutil.copytree(
        repository_root / "scripts",
        output / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("LICENSE", "NOTICE", "uv.lock", "CITATION.cff"):
        shutil.copy2(repository_root / name, output / "provenance" / name)

    selected_config = config.resolve().relative_to((repository_root / "configs").resolve())
    wheel_licenses = output / "provenance" / "wheel-licenses"
    dependency_metadata = [wheel_metadata(path, wheel_licenses) for path in dependency_wheels]
    provenance = {
        "repository_wheel": project_wheel.name,
        "repository_wheel_sha256": sha256_file(project_wheel),
        "uv_lock_sha256": sha256_file(repository_root / "uv.lock"),
        "selected_config": f"configs/{selected_config.as_posix()}",
        "model": model_metadata(model, model_id),
        "dependency_wheels": dependency_metadata,
    }
    return write_manifest(output, provenance)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--project-wheel", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = assemble(
        repository_root=args.repository_root.resolve(),
        project_wheel=args.project_wheel.resolve(),
        wheelhouse=args.wheelhouse.resolve(),
        model=args.model.resolve(),
        model_id=args.model_id,
        config=args.config.resolve(),
        output=args.output.resolve(),
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
