"""Create canonical offline admission evidence for the scene-topology compiler."""

from __future__ import annotations

import argparse
import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from arc3_voi.config import load_config
from arc3_voi.structured_templates import run_scene_topology_admission_audit


def write_new_artifact_atomic(output: Path, report: dict[str, Any]) -> None:
    """Publish sorted LF JSON atomically without replacing prior evidence."""

    if output.exists():
        raise FileExistsError(f"refusing to replace admission artifact: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output)
        temporary.unlink()
    except BaseException:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_config(args.config)
    report = run_scene_topology_admission_audit(
        args.fixture,
        config,
        config_path=args.config,
        require_clean_commit=True,
        require_linux_memory=True,
    )
    write_new_artifact_atomic(args.output, report)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "output": str(args.output),
                "status": report["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["gate"]["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
