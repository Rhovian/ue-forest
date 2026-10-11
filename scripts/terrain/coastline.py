#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scikit-image", "shapely"]
# ///
"""Trace Vilm's coastline from the heightmap as the Ocean's island spline, in UE world centimetres."""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from skimage import measure

TERRAIN = Path(__file__).resolve().parents[2] / "Forest/Saved/Terrain"
# Contour this far above sea level so the island hole sits on land and the water reaches the beach.
INLAND_M = 1.0
TOLERANCE_CM = 1500


def main():
    meta = json.loads((TERRAIN / "vilm_1513.json").read_text())
    encoded = np.array(Image.open(TERRAIN / "vilm_1513.png"), dtype=np.float64)
    heights = meta["min_m"] + encoded * (meta["max_m"] - meta["min_m"]) / 65535
    contour = max(measure.find_contours(heights, INLAND_M), key=len)
    # The landscape is centred on the origin; image rows run along +Y, columns along +X.
    origin = -(heights.shape[0] - 1) / 2 * meta["XYScale"]
    ring = Polygon(origin + contour[:, ::-1] * meta["XYScale"]).simplify(TOLERANCE_CM)
    points = [[round(x), round(y)] for x, y in ring.exterior.coords[:-1]]
    (TERRAIN / "vilm_coastline.json").write_text(json.dumps(points) + "\n")
    print(f"{len(points)} points, {ring.area / 1e10:.3f} km2 inside")


if __name__ == "__main__":
    main()
