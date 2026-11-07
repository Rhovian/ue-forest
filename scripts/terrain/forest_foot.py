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
SHORE_CM) connected to the sea, thinned to one point per 4 m. Rerun after the terrain changes.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, label

ROOT = Path(__file__).resolve().parents[2]
TERRAIN = ROOT / "Forest/Saved/Terrain/vilm_1513"
OUT = ROOT / "scripts/pcg/forest_foot.json"
SAND_FROM = 0.03  # m above the sea
STEP = 2  # pixels (2 m each) between kept points along the line


def main():
    shore = (float(sys.argv[1]) if len(sys.argv) > 1 else 75) / 100
    meta = json.loads(TERRAIN.with_suffix(".json").read_text())
    raw = np.asarray(Image.open(TERRAIN.with_suffix(".png")), dtype=float)
    height = meta["min_m"] + raw / 65535 * (meta["max_m"] - meta["min_m"])
    half, metres = (height.shape[0] - 1) / 2, meta["XYScale"] / 100
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
    keep = (rows % STEP == 0) | (cols % STEP == 0)
    keep &= ((rows // STEP) + (cols // STEP)) % 2 == 0
    points = sorted({(round((c - half) * metres), round((r - half) * metres)) for r, c in zip(rows[keep], cols[keep])})
    OUT.write_text(json.dumps({"shore_cm": shore * 100, "points_m": points}) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(points)} forest foot points (of {len(rows)} foot pixels)")


if __name__ == "__main__":
    main()
