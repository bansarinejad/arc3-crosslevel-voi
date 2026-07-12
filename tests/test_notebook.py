from __future__ import annotations

import json
from pathlib import Path


def test_reproduction_notebook_is_valid_json_without_results_fabrication() -> None:
    raw = Path("notebooks/reproduce.ipynb").read_text(encoding="utf-8")
    value = json.loads(raw)
    assert value["nbformat"] == 4
    source = "\n".join(
        line
        for cell in value["cells"]
        for line in cell.get("source", ())
    )
    assert "does not fabricate placeholder scores" in source
    assert "ScoreObservation" in source
    assert "verify_manifest" in source
    assert "strongest_comparator" in source
    assert "evaluate_mechanism_gate" in source
    assert "summarize_paired_observations" in source
    assert "_mean_prequential_loss" in source
    assert "ARC-AGI-2: GATED OFF" in source
    assert "NOT EVALUABLE" in source
    assert "\ufffd" not in raw
