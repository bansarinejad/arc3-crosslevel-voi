from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.build_offline_bundle import (
    assemble,
    model_metadata,
    verify_manifest,
    wheel_metadata,
)


def _write(path: Path, text: str = "payload") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _repository(root: Path) -> None:
    _write(root / "configs" / "base.yaml", "experiment: {}\n")
    _write(
        root / "configs" / "kaggle.yaml",
        "extends: base.yaml\nmodel:\n  offline: true\n",
    )
    _write(root / "LICENSES" / "MIT-0.txt")
    _write(root / "kaggle" / "entrypoint.py", "VALUE = 1\n")
    _write(root / "scripts" / "__init__.py", "")
    _write(root / "scripts" / "build_offline_bundle.py", "# fixture\n")
    _write(root / "scripts" / "offline_startup_smoke.py", "# fixture\n")
    for name in ("LICENSE", "NOTICE", "uv.lock", "CITATION.cff"):
        _write(root / name)


def _model(root: Path) -> None:
    _write(root / "README.md", "---\nlicense: apache-2.0\n---\n")
    _write(root / "LICENSE", "Apache test fixture")
    _write(root / "config.json", "{}")
    _write(root / ".cache" / "huggingface" / "download" / "a.metadata", "abc123\netag\n0\n")


def _wheel(path: Path, *, name: str = "dependency", version: str = "1.0") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\nLicense-Expression: MIT\n",
        )
        archive.writestr(f"{name}-{version}.dist-info/licenses/LICENSE", "MIT fixture")
    return path


def _runtime_wheel(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("arc3_voi/__init__.py", "")
        archive.writestr(
            "arc3_voi/config.py",
            "class Model:\n    offline = True\n"
            "class Config:\n    model = Model()\n"
            "def load_config(path):\n    return Config()\n",
        )
        archive.writestr(
            "arc3_voi/model.py",
            "from pathlib import Path\n"
            "class Backend:\n    def __init__(self, path): self.model_path = str(path)\n"
            "def backend_from_config(config, model_path=None): return Backend(Path(model_path))\n",
        )
        archive.writestr(
            "arc3_crosslevel_voi-0.1.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: arc3-crosslevel-voi\nVersion: 0.1\n",
        )
    return path


def test_model_metadata_uses_only_snapshot_files(tmp_path: Path) -> None:
    model = tmp_path / "model"
    _model(model)

    value = model_metadata(model, "owner/model")

    assert value["id"] == "owner/model"
    assert value["revision"] == "abc123"
    assert value["declared_license"] == "apache-2.0"
    assert len(value["license_sha256"]) == 64


def test_model_metadata_fails_closed_without_revision_or_license(tmp_path: Path) -> None:
    model = tmp_path / "model"
    _write(model / "README.md", "---\n---\n")
    _write(model / "LICENSE", "unknown fixture")

    with pytest.raises(ValueError, match="declared license"):
        model_metadata(model, "owner/model")


def test_bundle_manifest_covers_payload_and_detects_tampering(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _repository(repository)
    project_wheel = _write(tmp_path / "dist" / "project.whl")
    wheelhouse = tmp_path / "wheelhouse"
    _wheel(wheelhouse / "dependency.whl")
    model = tmp_path / "model"
    _model(model)
    output = tmp_path / "bundle"

    manifest_path = assemble(
        repository_root=repository,
        project_wheel=project_wheel,
        wheelhouse=wheelhouse,
        model=model,
        model_id="owner/model",
        config=repository / "configs" / "kaggle.yaml",
        output=output,
    )
    manifest = verify_manifest(output)

    assert manifest_path == output / "manifest.json"
    assert manifest["provenance"]["model"]["revision"] == "abc123"
    assert any(item["path"] == "model/config.json" for item in manifest["files"])
    assert any(item["path"] == "scripts/offline_startup_smoke.py" for item in manifest["files"])
    dependency = manifest["provenance"]["dependency_wheels"][0]
    assert dependency["license_expression"] == "MIT"
    assert dependency["embedded_license_files"]
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["schema_version"] == 1

    (output / "model" / "config.json").write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="payload digest mismatch"):
        verify_manifest(output)


def test_bundle_refuses_existing_output(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _repository(repository)
    model = tmp_path / "model"
    _model(model)
    wheelhouse = tmp_path / "wheelhouse"
    _wheel(wheelhouse / "dependency.whl")
    output = tmp_path / "bundle"
    output.mkdir()

    with pytest.raises(FileExistsError):
        assemble(
            repository_root=repository,
            project_wheel=_write(tmp_path / "project.whl"),
            wheelhouse=wheelhouse,
            model=model,
            model_id="owner/model",
            config=repository / "configs" / "kaggle.yaml",
            output=output,
        )


def test_wheel_license_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    wheel = tmp_path / "malicious.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("package-1.dist-info/METADATA", "Name: package\nVersion: 1\n")
        archive.writestr("../LICENSE", "escape")

    with pytest.raises(ValueError, match="unsafe license member"):
        wheel_metadata(wheel, tmp_path / "licenses")


def test_network_disabled_startup_smoke_imports_exact_bundle(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _repository(repository)
    wheelhouse = tmp_path / "wheelhouse"
    _wheel(wheelhouse / "dependency.whl")
    model = tmp_path / "model"
    _model(model)
    output = tmp_path / "bundle"
    assemble(
        repository_root=repository,
        project_wheel=_runtime_wheel(tmp_path / "project.whl"),
        wheelhouse=wheelhouse,
        model=model,
        model_id="owner/model",
        config=repository / "configs" / "kaggle.yaml",
        output=output,
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(Path("scripts/offline_startup_smoke.py").resolve()),
            str(output),
            "--skip-model-config",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "offline startup smoke passed" in completed.stdout
