"""Audit the offline generic structured-prior library after a clean root commit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arc3_voi.config import load_config
from arc3_voi.structured_templates import run_structured_prior_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = run_structured_prior_audit(
        args.fixture,
        load_config(args.config),
        require_clean_commit=True,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["gate"]["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
