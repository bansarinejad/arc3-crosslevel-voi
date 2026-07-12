"""Deterministic ARC grid rendering for multimodal model input."""

from __future__ import annotations

from typing import Any

import numpy as np

# ARC's 16 symbolic colours. Exact hues do not affect scoring, but remain frozen for runs.
ARC_PALETTE = np.asarray(
    [
        (0, 0, 0),
        (0, 116, 217),
        (255, 65, 54),
        (46, 204, 64),
        (255, 220, 0),
        (170, 170, 170),
        (240, 18, 190),
        (255, 133, 27),
        (127, 219, 255),
        (135, 12, 37),
        (255, 255, 255),
        (80, 80, 80),
        (120, 80, 200),
        (80, 180, 160),
        (180, 130, 80),
        (220, 220, 220),
    ],
    dtype=np.uint8,
)


def render_grid_array(grid: Any, *, scale: int = 8, grid_lines: bool = True) -> np.ndarray:
    """Render a symbolic grid to an RGB uint8 array."""

    values = np.asarray(grid, dtype=np.int16)
    if values.ndim != 2 or values.shape != (64, 64):
        raise ValueError(f"expected a 64x64 grid, got {values.shape}")
    if values.min(initial=0) < 0 or values.max(initial=0) > 15:
        raise ValueError("grid values must be in [0, 15]")
    image = ARC_PALETTE[values]
    image = np.repeat(np.repeat(image, scale, axis=0), scale, axis=1)
    if grid_lines and scale >= 4:
        image[::scale, :, :] = 35
        image[:, ::scale, :] = 35
    return image


def render_grid_pil(grid: Any, *, scale: int = 8) -> Any:
    """Return a PIL image while keeping Pillow an optional dependency."""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Pillow is required for multimodal rendering") from exc
    return Image.fromarray(render_grid_array(grid, scale=scale), mode="RGB")

