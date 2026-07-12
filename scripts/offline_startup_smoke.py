"""Verify a bundle and import its runtime while Python networking is disabled."""

from __future__ import annotations

import argparse
import importlib.util
import os
import socket
import sys
from pathlib import Path
from typing import NoReturn

if __package__:
    from .build_offline_bundle import verify_manifest
else:  # Support ``python scripts/offline_startup_smoke.py``.
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from scripts.build_offline_bundle import verify_manifest


def _blocked(*_args: object, **_kwargs: object) -> NoReturn:
    raise RuntimeError("network access attempted during offline startup smoke")


def disable_python_network() -> None:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PIP_NO_INDEX": "1",
            "HF_DATASETS_OFFLINE": "1",
        }
    )
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]


def smoke(bundle: Path, *, load_model_config: bool = True) -> None:
    manifest = verify_manifest(bundle)
    wheels = sorted((bundle / "code").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("bundle must contain exactly one project wheel")
    sys.path.insert(0, str(wheels[0]))
    disable_python_network()

    from arc3_voi.config import load_config
    from arc3_voi.model import backend_from_config

    config_path = bundle / manifest["provenance"]["selected_config"]
    config = load_config(config_path)
    if config.model is None or not config.model.offline:
        raise ValueError("Kaggle bundle config must set model.offline: true")
    backend = backend_from_config(config, model_path=bundle / "model")
    if Path(backend.model_path).resolve() != (bundle / "model").resolve():
        raise AssertionError("backend did not retain the bundled model path")

    entrypoint = bundle / "runtime" / "entrypoint.py"
    spec = importlib.util.spec_from_file_location("arc3_voi_offline_entrypoint", entrypoint)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if load_model_config:
        from transformers import AutoConfig

        AutoConfig.from_pretrained(bundle / "model", local_files_only=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--skip-model-config", action="store_true")
    args = parser.parse_args(argv)
    smoke(args.bundle.resolve(), load_model_config=not args.skip_model_config)
    print("offline startup smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
