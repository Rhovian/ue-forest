#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Bake scripts/pcg/terrain_tiles.json from landheight's raw landscape heights (#247).

    scripts/terrain/terrain_tiles.py [PATH/TO/vilm_1513_shore]

Default input: Forest/Saved/Terrain/vilm_1513_shore.png + .json, centred on the
world origin, 2 m per pixel, rows along +Y. Cells use area_sampling.TILE (2000 cm):
[ix, iy, z_min_cm, z_max_cm, slope_max_deg]. Include submerged landscape too.
Height extrema enclose the vertices supporting each cell; slopes are the maximum
central-difference slope over those vertices and their one-vertex border (one-sided
differences at map edges). Heights round outward to 0.01 cm, slopes up to 0.001 deg.

Central differences do not bound UE's averaged, packed vertex normals. Consumers
must subtract slope_margin_deg from their slope cutoff. It is recomputed against
UE 5.8's imported vertex normals, including packing, rounded up with 0.01 deg slack.
PCGLandscapeCache.cpp:GetInterpolatedPointInternal interpolates upward normals with
nonnegative weights: their cone cannot exceed the steepest supporting vertex.
Thus slope_max_deg + slope_margin_deg bounds the normal anywhere in the cell,
provided the landscape still matches this unrotated heightmap. Rebake after edits.
"""

import json
import sys
from pathlib import Path

import numpy as np

if __package__:
    from . import landheight
else:
    import landheight

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scripts/pcg/terrain_tiles.json"
TILE = 2000  # cm; area_sampling imports unreal, so it cannot be imported here


def landscape_slopes(height, metres):
    """UE 5.8 LandscapeEdit.cpp:Import / LandscapeEditInterface.cpp:SetHeightData normals.

    NumPy has no landscape-normal routine: sum the two unit face normals per quad
    into their incident vertices, then pack/unpack XY as LandscapeDataAccess.h does.
    """
    dx, dy = np.diff(height, axis=1) / metres, np.diff(height, axis=0) / metres
    normals = np.zeros((*height.shape, 3))
    for gx, gy, omitted in ((dx[:-1], dy[:, 1:], (1, 0)), (dx[1:], dy[:, :-1], (0, 1))):
        face = np.stack((-gx, -gy, np.ones_like(gx)), axis=-1)
        face /= np.linalg.norm(face, axis=-1)[..., None]
        for y, x in ((0, 0), (0, 1), (1, 0), (1, 1)):
            if (y, x) != omitted:
                normals[y:y + face.shape[0], x:x + face.shape[1]] += face
    normals /= np.linalg.norm(normals, axis=-1)[..., None]
    # At rounding ties choose the steeper packed component; epsilon covers float noise.
    xy = np.floor((np.abs(normals[..., :2]) + 1) * 127.5 + 0.50001) / 127.5 - 1
    return np.degrees(np.arcsin(np.minimum(1, np.linalg.norm(xy, axis=-1))))


def summaries(height, metres):
    """Sorted tile summaries and a global additive slope margin, using raw heights in m."""
    slope = np.degrees(np.arctan(np.hypot(*np.gradient(height, metres))))
    landscape = landscape_slopes(height, metres)
    axes = []
    for n in reversed(height.shape):  # X (columns), then Y (rows)
        coords = (np.arange(n) - (n - 1) / 2) * metres * 100
        spans = []
        for i in range(int(np.floor(coords[0] / TILE)), int(np.floor(coords[-1] / TILE)) + 1):
            lo = max(0, int(np.searchsorted(coords, i * TILE, side="right")) - 1)
            hi = min(n, int(np.searchsorted(coords, (i + 1) * TILE)) + 1)
            spans.append((i, lo, hi))
        axes.append(spans)
    cells, margin = [], 0.0
    for ix, x0, x1 in axes[0]:
        for iy, y0, y1 in axes[1]:
            patch = height[y0:y1, x0:x1] * 100
            border = (slice(max(0, y0 - 1), y1 + 1), slice(max(0, x0 - 1), x1 + 1))
            steepest = float(slope[border].max())
            margin = max(margin, float(landscape[border].max()) - steepest)
            cells.append([ix, iy, float(np.floor(patch.min() * 100) / 100),
                          float(np.ceil(patch.max() * 100) / 100), float(np.ceil(steepest * 1000) / 1000)])
    return {"tile_cm": TILE, "slope_margin_deg": float((np.ceil(margin * 100) + 1) / 100), "cells": cells}


def main():
    if len(sys.argv) > 1:
        landheight.TERRAIN = Path(sys.argv[1])
    data = summaries(*landheight.read_height())
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(data['cells'])} cells, {OUT.stat().st_size} bytes, "
          f"max slope {max(c[4] for c in data['cells']):.3f} deg, margin {data['slope_margin_deg']:.2f} deg")


if __name__ == "__main__":
    main()
