"""Deterministic ARC grid rendering for multimodal model input."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

PERCEPTION_CONTRACT_VERSION = "arc-agi-0.9.9-color-map-scale8-grid-v1"
ARC_COLOR_NAMES = (
    "white",
    "off-white",
    "light gray",
    "gray",
    "off-black",
    "black",
    "magenta",
    "light magenta",
    "red",
    "blue",
    "light blue",
    "yellow",
    "orange",
    "maroon",
    "green",
    "purple",
)

# Mirrored from arc_agi.rendering.COLOR_MAP in the pinned arc-agi==0.9.9 toolkit.
# The exact mapping is part of the perception contract and therefore frozen for runs.
_ARC_PALETTE_RGB = (
        (255, 255, 255),
        (204, 204, 204),
        (153, 153, 153),
        (102, 102, 102),
        (51, 51, 51),
        (0, 0, 0),
        (229, 58, 163),
        (255, 123, 204),
        (249, 60, 49),
        (30, 147, 255),
        (136, 216, 241),
        (255, 220, 0),
        (255, 133, 27),
        (146, 18, 49),
        (79, 204, 48),
        (163, 86, 214),
)
# A bytes-backed view cannot be made writeable, so prompt and renderer state cannot diverge.
ARC_PALETTE = np.frombuffer(
    bytes(component for color in _ARC_PALETTE_RGB for component in color),
    dtype=np.uint8,
).reshape(16, 3)
GRID_LINE_RGB = (35, 35, 35)
DEFAULT_RENDER_SCALE = 8
ARC_PALETTE_LEGEND = "; ".join(
    f"{index}={name} RGB({red},{green},{blue})"
    for index, (name, (red, green, blue)) in enumerate(
        zip(ARC_COLOR_NAMES, ARC_PALETTE.tolist(), strict=True)
    )
)


def render_grid_array(
    grid: Any, *, scale: int = DEFAULT_RENDER_SCALE, grid_lines: bool = True
) -> np.ndarray:
    """Render a symbolic grid to an RGB uint8 array."""

    values = np.asarray(grid, dtype=np.int16)
    if values.ndim != 2 or values.shape != (64, 64):
        raise ValueError(f"expected a 64x64 grid, got {values.shape}")
    if values.min(initial=0) < 0 or values.max(initial=0) > 15:
        raise ValueError("grid values must be in [0, 15]")
    image = ARC_PALETTE[values]
    image = np.repeat(np.repeat(image, scale, axis=0), scale, axis=1)
    if grid_lines and scale >= 4:
        image[::scale, :, :] = GRID_LINE_RGB
        image[:, ::scale, :] = GRID_LINE_RGB
    return image


def render_grid_pil(grid: Any, *, scale: int = DEFAULT_RENDER_SCALE) -> Any:
    """Return a PIL image while keeping Pillow an optional dependency."""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Pillow is required for multimodal rendering") from exc
    return Image.fromarray(render_grid_array(grid, scale=scale), mode="RGB")


_PERCEPTION_SPEC = json.dumps(
    {
        "color_names": ARC_COLOR_NAMES,
        "default_scale": DEFAULT_RENDER_SCALE,
        "grid_line_rgb": GRID_LINE_RGB,
        "grid_lines": True,
        "palette_rgb": _ARC_PALETTE_RGB,
        "symbolic_shape": [64, 64],
    },
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
PERCEPTION_SPEC_SHA256 = hashlib.sha256(_PERCEPTION_SPEC).hexdigest()
_REFERENCE_GRID = (np.arange(64 * 64, dtype=np.int16).reshape(64, 64) % 16).astype(
    np.int16
)
PERCEPTION_REFERENCE_RENDER_SHA256 = hashlib.sha256(
    render_grid_array(_REFERENCE_GRID).tobytes(order="C")
).hexdigest()
PERCEPTION_CONTRACT_SHA256 = hashlib.sha256(
    f"{PERCEPTION_SPEC_SHA256}:{PERCEPTION_REFERENCE_RENDER_SHA256}".encode("ascii")
).hexdigest()
