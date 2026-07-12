"""Download an official model using the OS trust store on managed Windows hosts."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_id")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--include", action="append")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args()

    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    from huggingface_hub import snapshot_download

    resolved = snapshot_download(
        repo_id=args.model_id,
        local_dir=args.destination,
        allow_patterns=args.include,
        max_workers=args.max_workers,
    )
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
