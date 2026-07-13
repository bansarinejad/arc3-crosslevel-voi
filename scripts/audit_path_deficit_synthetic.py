"""Publish the frozen path-deficit-v2 synthetic admission result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arc3_voi.trajectory_deficit import run_path_deficit_synthetic_audit

try:
    from .audit_scene_topology_admission import write_new_artifact_atomic
except ImportError:  # pragma: no cover - direct script execution
    from audit_scene_topology_admission import write_new_artifact_atomic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/template_v1_path_deficit_v2_x.yaml"),
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("artifacts/development_matrix_template_v1_path_deficit_v2.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = run_path_deficit_synthetic_audit(
        args.config,
        args.matrix,
        require_clean_commit=True,
        require_linux=True,
    )
    write_new_artifact_atomic(args.output, report)
    print(
        json.dumps(
            {
                "acceptance_gate": report["acceptance_gate"],
                "output": str(args.output),
                "status": report["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if report["acceptance_gate"]["passes"] is not False:
        raise RuntimeError("frozen negative audit unexpectedly returned an admitted result")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
