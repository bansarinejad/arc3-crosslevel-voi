"""Emit a machine-readable dependency and BF16 CUDA stack check."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from arc3_voi.preflight import detect_hardware, detect_runtime
from arc3_voi.provenance import inspect_git_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--uv", type=Path, required=True)
    args = parser.parse_args()

    dependency = subprocess.run(
        [str(args.uv), "pip", "check", "--python", sys.executable],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    bf16: dict[str, Any]
    try:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        values = torch.arange(256 * 256, device="cuda", dtype=torch.float32)
        matrix = (values.reshape(256, 256) / float(256 * 256)).to(torch.bfloat16)
        product = matrix @ matrix.T
        torch.cuda.synchronize()
        bf16 = {
            "passed": True,
            "dtype": str(product.dtype),
            "shape": list(product.shape),
            "mean_checksum": float(product.float().mean()),
        }
    except Exception as exc:
        bf16 = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}

    report = {
        "schema_version": 1,
        "git": asdict(inspect_git_provenance()),
        "hardware": asdict(detect_hardware()),
        "runtime": asdict(detect_runtime()),
        "dependency_check": {
            "passed": dependency.returncode == 0,
            "returncode": dependency.returncode,
            "stdout": dependency.stdout.strip(),
            "stderr": dependency.stderr.strip(),
        },
        "bf16_cuda_smoke": bf16,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if dependency.returncode == 0 and bf16["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
