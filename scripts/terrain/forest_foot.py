#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Write the forest foot line, where the beach meets the land above the shore height, for the debris band (#38).

    scripts/terrain/forest_foot.py [SHORE_CM]

Reads the landscape heightmap that heightmap.py wrote (Forest/Saved/Terrain/vilm_1513.png and .json; centred on the
world origin, 2 m per pixel, rows along +Y) and writes scripts/pcg/forest_foot.json: world (x, y) metres of every
pixel of the island (its largest piece of land at or above SHORE_CM, default 75, MI_ForestFloor's
ShoreHeight) that touches beach sand (3 cm up to
SHORE_CM) connected to the sea, thinned to one point per 4 x 4 m cell it crosses, and the island's bounds (island_m: x min, x max, y min,
y max in metres) for the scripts that place things over it. Rerun after the terrain changes.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, label

ROOT = Path(__file__).resolve().parents[2]
TERRAIN = ROOT / "Forest/Saved/Terrain/vilm_1513_shore"  # the imported heights, after soft_shore.py
OUT = ROOT / "scripts/pcg/forest_foot.json"
SAND_FROM = 0.03  # m above the sea
STEP = 2  # pixel cell side (2 m pixels): one kept point per 4 x 4 m cell the line crosses


def foot_and_bounds(height, shore, metres):
    """Forest foot points (world m, one per STEP x STEP cell) and the island's placement bounds [x min, x max, y min,
    y max] in m, from a heightmap in m centred on the world origin with rows along +Y."""
    half = (height.shape[0] - 1) / 2
    sand = (height >= SAND_FROM) & (height < shore)
    # Beach sand only: sand connected to the sea, not shallow ground around the lake or stream.
    sea_side = binary_dilation(height < SAND_FROM, iterations=1)
    parts, _ = label(sand | sea_side)
    beach = sand & np.isin(parts, np.unique(parts[sea_side & (height < SAND_FROM)]))
    # The island is the largest piece of land above the shore height (heightmap.py's rule for the land itself).
    land, _ = label(height >= shore)
    island = land == np.argmax(np.bincount(land.ravel())[1:]) + 1
    foot = island & binary_dilation(beach, iterations=1)
    rows, cols = np.nonzero(foot)
    # One point per occupied STEP x STEP pixel cell: every foot pixel lies within one cell diagonal (~5.7 m) of a kept
    # point, whatever the line's direction (a parity rule could drop a whole diagonal stretch; #62 review).
    cells = {}
    for r, c in zip(rows, cols):
        cells.setdefault((r // STEP, c // STEP), (r, c))
    points = sorted({(round((c - half) * metres), round((r - half) * metres)) for r, c in cells.values()})
    # Placement bounds cover the whole island down to the beach (its connected land and sand above SAND_FROM), not just
    # the forest-foot mask: mist and wisps also use lower coastal ground (#63 review).
    ground, _ = label(height >= SAND_FROM)
    whole = np.isin(ground, np.unique(ground[island]))
    ir, ic = np.nonzero(whole)
    bounds = [round((ic.min() - half) * metres), round((ic.max() - half) * metres),
              round((ir.min() - half) * metres), round((ir.max() - half) * metres)]
    return points, bounds


def main():
    shore = (float(sys.argv[1]) if len(sys.argv) > 1 else 75) / 100
    meta = json.loads(TERRAIN.with_suffix(".json").read_text())
    raw = np.asarray(Image.open(TERRAIN.with_suffix(".png")), dtype=float)
    height = meta["min_m"] + raw / 65535 * (meta["max_m"] - meta["min_m"])
    points, bounds = foot_and_bounds(height, shore, meta["XYScale"] / 100)
    OUT.write_text(json.dumps({"shore_cm": shore * 100, "island_m": bounds, "points_m": points}) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(points)} forest foot points, island bounds {bounds} m")


if __name__ == "__main__":
    main()
