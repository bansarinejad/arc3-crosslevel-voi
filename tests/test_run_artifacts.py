from __future__ import annotations

import json
from pathlib import Path

import pytest

import arc3_voi.run_store as run_store
from arc3_voi.experiment import RunSpec, completed_run_ids
from arc3_voi.metrics import RunMetrics, write_run
from arc3_voi.runner import run_game

from .test_runner import FakeController, FakeSession


def _row() -> RunSpec:
    return RunSpec(
        phase="development",
        game_id="fake",
        seed=7,
        variant="D",
        model_profile="test",
        config_hash="abc",
    )


def _metrics(row: RunSpec) -> RunMetrics:
    return run_game(
        FakeSession(),
        FakeController(),
        run_id=row.run_id,
        seed=row.seed,
        variant=row.variant,
        model_profile=row.model_profile,
        config_hash=row.config_hash,
    )


def test_resume_requires_both_summary_and_trace(tmp_path: Path) -> None:
    row = _row()
    summary, trace = write_run(_metrics(row), tmp_path)

    metadata = json.loads(summary.read_text())[run_store.TRACE_ARTIFACT_KEY]
    assert metadata["record_count"] == 2
    assert len(metadata["sha256"]) == 64
    trace.unlink()

    assert completed_run_ids((row,), tmp_path) == frozenset()


def test_resume_rejects_truncated_trace(tmp_path: Path) -> None:
    row = _row()
    _summary, trace = write_run(_metrics(row), tmp_path)
    trace.write_bytes(trace.read_bytes()[:-10])

    assert completed_run_ids((row,), tmp_path) == frozenset()


def test_resume_rejects_valid_json_trace_with_wrong_checksum(tmp_path: Path) -> None:
    row = _row()
    _summary, trace = write_run(_metrics(row), tmp_path)
    lines = trace.read_text().splitlines()
    replacement = json.loads(lines[0])
    replacement["decision_mode"] = "probe"
    lines[0] = json.dumps(replacement, separators=(",", ":"), sort_keys=True)
    trace.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    assert completed_run_ids((row,), tmp_path) == frozenset()


def test_write_refuses_to_replace_clean_claim_with_missing_trace(tmp_path: Path) -> None:
    row = _row()
    metrics = _metrics(row)
    summary, trace = write_run(metrics, tmp_path)
    original_summary = summary.read_bytes()
    trace.unlink()
    replacement = _metrics(row)
    replacement.wall_seconds = metrics.wall_seconds + 1.0

    with pytest.raises(FileExistsError, match="clean completion claim"):
        write_run(replacement, tmp_path)

    assert summary.read_bytes() == original_summary
    assert not trace.exists()


def test_write_refuses_to_replace_unparseable_summary(tmp_path: Path) -> None:
    row = _row()
    summary = tmp_path / f"{row.run_id}.json"
    summary.write_text("{not-json", encoding="utf-8")

    with pytest.raises(FileExistsError, match="corrupt or unreadable"):
        write_run(_metrics(row), tmp_path)

    assert summary.read_text(encoding="utf-8") == "{not-json"


def test_interrupted_publish_never_exposes_completed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _row()
    metrics = _metrics(row)
    summary = tmp_path / f"{row.run_id}.json"
    trace = tmp_path / f"{row.run_id}.jsonl"
    real_replace = run_store.os.replace

    def fail_summary_replace(source: Path, destination: Path) -> None:
        if Path(destination) == summary:
            raise OSError("simulated interruption before summary commit")
        real_replace(source, destination)

    monkeypatch.setattr(run_store.os, "replace", fail_summary_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        write_run(metrics, tmp_path)

    assert trace.exists()
    assert not summary.exists()
    assert summary.with_suffix(".pending").exists()
    assert completed_run_ids((row,), tmp_path) == frozenset()

    monkeypatch.setattr(run_store.os, "replace", real_replace)
    write_run(metrics, tmp_path)
    assert completed_run_ids((row,), tmp_path) == {row.run_id}
    assert not summary.with_suffix(".pending").exists()


def test_write_run_preserves_a_complete_historical_pair(tmp_path: Path) -> None:
    row = _row()
    original = _metrics(row)
    summary, trace = write_run(original, tmp_path)
    before = (summary.read_bytes(), trace.read_bytes())

    changed = _metrics(row)
    changed.wall_seconds = original.wall_seconds + 1.0
    with pytest.raises(FileExistsError, match="historical"):
        write_run(changed, tmp_path)

    assert (summary.read_bytes(), trace.read_bytes()) == before


def test_retry_can_atomically_replace_a_failed_attempt(tmp_path: Path) -> None:
    row = _row()
    failed = _metrics(row)
    failed.error = "simulated failure"
    write_run(failed, tmp_path)
    assert completed_run_ids((row,), tmp_path) == frozenset()

    write_run(_metrics(row), tmp_path)
    assert completed_run_ids((row,), tmp_path) == {row.run_id}


@pytest.mark.parametrize("run_id", ("bad\\name", "bad:name", "CON", "trailing."))
def test_write_rejects_nonportable_run_ids(tmp_path: Path, run_id: str) -> None:
    metrics = _metrics(_row())
    metrics.run_id = run_id

    with pytest.raises(ValueError, match="portable ASCII"):
        write_run(metrics, tmp_path)


def test_resume_rejects_derivable_summary_trace_mismatch(tmp_path: Path) -> None:
    row = _row()
    summary, _trace = write_run(_metrics(row), tmp_path)
    payload = json.loads(summary.read_text())
    payload["generated_tokens"] += 1
    summary.write_text(json.dumps(payload), encoding="utf-8")

    assert completed_run_ids((row,), tmp_path) == frozenset()
