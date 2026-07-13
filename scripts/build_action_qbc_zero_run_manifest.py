"""Build the deterministic runtime-v5 zero-run registration artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arc3_voi.action_qbc_zero_run import (
    REGISTERED_MANIFEST_PATH,
    build_zero_run_registration,
    registration_payload_sha256,
    serialize_zero_run_registration,
    validate_zero_run_registration,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository containing the content-addressed config, split, and predecessors",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output path (defaults to the registered artifact inside the repository)",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.repository_root.resolve()
    destination = (
        args.output.resolve()
        if args.output is not None
        else root / REGISTERED_MANIFEST_PATH
    )
    registration = build_zero_run_registration(root)
    validate_zero_run_registration(registration, root)
    payload = serialize_zero_run_registration(registration)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "development_matrix_execution_authorized": False,
                "output": str(destination),
                "payload_sha256": registration_payload_sha256(registration),
                "runs": len(registration["runs"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
