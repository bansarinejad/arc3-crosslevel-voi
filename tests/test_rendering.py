from __future__ import annotations

import numpy as np
import pytest

from arc3_voi.rendering import render_grid_array


def test_render_grid_array_shape_and_dtype() -> None:
    rendered = render_grid_array(np.zeros((64, 64), dtype=np.int8), scale=2)
    assert rendered.shape == (128, 128, 3)
    assert rendered.dtype == np.uint8


def test_render_grid_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError):
        render_grid_array(np.zeros((3, 3)))


def test_render_grid_rejects_invalid_colour() -> None:
    grid = np.zeros((64, 64), dtype=np.int8)
    grid[0, 0] = 16
    with pytest.raises(ValueError):
        render_grid_array(grid)

