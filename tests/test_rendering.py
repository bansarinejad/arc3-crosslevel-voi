from __future__ import annotations

import numpy as np
import pytest

from arc3_voi.rendering import (
    ARC_PALETTE,
    ARC_PALETTE_LEGEND,
    PERCEPTION_CONTRACT_SHA256,
    PERCEPTION_REFERENCE_RENDER_SHA256,
    PERCEPTION_SPEC_SHA256,
    render_grid_array,
)

OFFICIAL_ARC_AGI_099_PALETTE = np.asarray(
    [
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
    ],
    dtype=np.uint8,
)


def test_palette_matches_pinned_official_arc_renderer() -> None:
    assert np.array_equal(ARC_PALETTE, OFFICIAL_ARC_AGI_099_PALETTE)
    assert "0=white RGB(255,255,255)" in ARC_PALETTE_LEGEND
    assert "5=black RGB(0,0,0)" in ARC_PALETTE_LEGEND
    assert "10=light blue RGB(136,216,241)" in ARC_PALETTE_LEGEND
    assert "14=green RGB(79,204,48)" in ARC_PALETTE_LEGEND
    assert not ARC_PALETTE.flags.writeable


def test_perception_contract_fingerprints_are_sha256() -> None:
    for digest in (
        PERCEPTION_SPEC_SHA256,
        PERCEPTION_REFERENCE_RENDER_SHA256,
        PERCEPTION_CONTRACT_SHA256,
    ):
        assert len(digest) == 64
        int(digest, 16)


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
