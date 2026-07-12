from __future__ import annotations

from pathlib import Path


def test_text_artifacts_are_utf8_without_replacement_characters() -> None:
    roots = (Path("docs"), Path("paper"), Path("kaggle"), Path("scripts"))
    paths = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".md", ".py", ".bib"}
    ]
    paths.extend((Path("README.md"), Path("NOTICE"), Path("CITATION.cff")))

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, f"replacement character in {path}"


def test_theory_contains_scoped_proofs_and_numeric_counterexample() -> None:
    text = Path("docs/theory.md").read_text(encoding="utf-8")

    assert "Proposition 1: exact one-query threshold" in text
    assert "Proposition 2: monotone remaining-mass threshold" in text
    assert "22/3" in text
    assert "This proposition is a one-query comparison" in text
