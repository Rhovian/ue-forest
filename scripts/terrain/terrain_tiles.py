#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Bake scripts/pcg/terrain_tiles.json from landheight's raw landscape heights (#247).

    scripts/terrain/terrain_tiles.py [PATH/TO/vilm_1513_shore]

Reads Forest/Saved/Terrain/vilm_1513_shore.png + .json (origin-centred, 2 m pixels,
rows along +Y). Each landscape cell, including submerged ground, is summarized as
[ix, iy, z_min_cm, z_max_cm, slope_max_deg], using area_sampling.TILE (2000 cm).
Supporting vertices bound height/UE-normal slope; round outward to 0.01 cm/0.001 deg.
PCGLandscapeCache.cpp:GetInterpolatedPointInternal interpolates normals with positive
weights, so none exceeds the steepest supporting vertex. Filter directly at the
slope cutoff; packing allows the steeper code within 1e-3 of a tie. The PNG path/hash
records provenance: rebake after edits; bounds assume this unrotated imported terrain.
"""

import hashlib
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
    NumPy has no UE-normal routine; sum incident unit faces, pack as LandscapeDataAccess.h.
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
    # Within 1e-3 code units of a tie, allow one steeper code for GPU float/UNORM error.
    xy = np.floor((np.abs(normals[..., :2]) + 1) * 127.5 + 0.501) / 127.5 - 1
    return np.degrees(np.arcsin(np.minimum(1, np.linalg.norm(xy, axis=-1))))


def summaries(height, metres):
    """Sorted tile summaries, using raw heights in m and the supporting UE vertex normals."""
    slope = landscape_slopes(height, metres)
    axes = []
    for n in reversed(height.shape):  # X (columns), then Y (rows)
        coords = (np.arange(n) - (n - 1) / 2) * metres * 100
        spans = []
        for i in range(int(np.floor(coords[0] / TILE)), int(np.floor(coords[-1] / TILE)) + 1):
            lo = max(0, int(np.searchsorted(coords, i * TILE, side="right")) - 1)
            hi = min(n, int(np.searchsorted(coords, (i + 1) * TILE)) + 1)
            spans.append((i, lo, hi))
        axes.append(spans)
    cells = []
    for ix, x0, x1 in axes[0]:
        for iy, y0, y1 in axes[1]:
            patch = height[y0:y1, x0:x1] * 100
            steepest = float(slope[y0:y1, x0:x1].max())
            cells.append([ix, iy, float(np.floor(patch.min() * 100) / 100),
                          float(np.ceil(patch.max() * 100) / 100), float(np.ceil(steepest * 1000) / 1000)])
    return {"tile_cm": TILE, "cells": cells}


def main():
    if len(sys.argv) > 1:
        landheight.TERRAIN = Path(sys.argv[1])
    data = summaries(*landheight.read_height())
    png = landheight.TERRAIN.with_suffix(".png").resolve()
    data.update(source_png=str(png), source_sha256=hashlib.sha256(png.read_bytes()).hexdigest())
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(data['cells'])} cells, {OUT.stat().st_size} bytes, "
          f"max slope {max(c[4] for c in data['cells']):.3f} deg, "
          f"slope >= 30: {sum(c[4] >= 30 for c in data['cells'])} cells")
    print(f"source PNG: {data['source_png']}, sha256: {data['source_sha256']}")


if __name__ == "__main__":
    main()
