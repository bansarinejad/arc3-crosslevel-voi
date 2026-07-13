"""Compatibility wrapper for the scene-topology admission command."""

from __future__ import annotations

if __package__:
    from .audit_scene_topology_admission import main
else:  # pragma: no cover - exercised by direct script invocation
    from audit_scene_topology_admission import main

if __name__ == "__main__":
    raise SystemExit(main())
