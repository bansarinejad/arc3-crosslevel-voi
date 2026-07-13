from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.audit_scene_topology_admission as admission_script
import scripts.audit_structured_templates as compatibility_script
from scripts.audit_scene_topology_admission import write_new_artifact_atomic


def test_admission_artifact_write_is_atomic_sorted_and_exclusive(tmp_path: Path) -> None:
    assert compatibility_script.main is admission_script.main
    output = tmp_path / "report.json"
    report = {"z": 1, "gate": {"passes": False, "reasons": ["blocked"]}}

    write_new_artifact_atomic(output, report)

    assert output.read_bytes() == (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    assert not (tmp_path / ".report.json.tmp").exists()
    with pytest.raises(FileExistsError, match="refusing to replace"):
        write_new_artifact_atomic(output, report)


def test_admission_artifact_writer_never_replaces_a_racing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "report.json"
    real_link = admission_script.os.link

    def racing_link(source: Path, destination: Path) -> None:
        destination.write_text("racer\n", encoding="utf-8")
        real_link(source, destination)

    monkeypatch.setattr(admission_script.os, "link", racing_link)

    with pytest.raises(FileExistsError):
        write_new_artifact_atomic(output, {"gate": {"passes": False}})
    assert output.read_text(encoding="utf-8") == "racer\n"
    assert not (tmp_path / ".report.json.tmp").exists()
