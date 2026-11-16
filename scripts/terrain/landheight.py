#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Bake beach_lift.png (8-bit, original grid/orientation) and pcg/waterline.json (#239).

Effective heights are for classification only: the imported terrain is never edited.
World X follows columns, world Y follows rows; the heightmap is centred on the origin.
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, label, map_coordinates

ROOT = Path(__file__).resolve().parents[2]
TERRAIN = ROOT / "Forest/Saved/Terrain/vilm_1513_shore"
LIFT_CM = 150
BEACH_STRIP_M = 20
BEACH_VARY_M = 8
BEACH_FEATURE_M = 120
BEACH_FADE_M = 10
BEACH_SEED = 239
SAND_FROM = 0.03
CELL_M = 4


def sea_mask(height):
    """Ground below 3 cm connected (four neighbours) to a map edge; enclosed water is excluded."""
    parts, _ = label(height < SAND_FROM)
    edge = np.unique(np.concatenate([parts[0], parts[-1], parts[:, 0], parts[:, -1]]))
    return np.isin(parts, edge[edge > 0])


def strip_width(shape, metres):
    """Seeded, smooth value noise on a BEACH_FEATURE_M lattice in centred world metres.

    The RNG lattice depends on shape; consumers at other extents must sample the baked mask.
    """
    coords = [(np.arange(n) - (n - 1) / 2) * metres / BEACH_FEATURE_M for n in shape]
    origin = [int(np.floor(axis.min())) for axis in coords]
    size = [int(np.floor(axis.max())) - start + 2 for axis, start in zip(coords, origin)]
    values = np.random.default_rng(BEACH_SEED).uniform(-1, 1, size)
    axes = []
    for axis, start in zip(coords, origin):
        base = np.floor(axis)
        t = axis - base
        axes.append(base - start + t * t * (3 - 2 * t))
    # Bilinear interpolation of the smoothstep-warped lattice gives smoothly drifting widths (#239).
    noise = map_coordinates(values, np.meshgrid(*axes, indexing="ij"), order=1, prefilter=False)
    return BEACH_STRIP_M + BEACH_VARY_M * noise


def lift(height, metres):
    """Lift weight on the original heightmap grid, with rows along world +Y."""
    sea = sea_mask(height)
    if not sea.any():
        return np.ones_like(height, dtype=float)
    distance = distance_transform_edt(~sea, sampling=metres)
    return np.clip((distance - strip_width(height.shape, metres)) / BEACH_FADE_M, 0, 1)


def effective(height, metres):
    """Classification height in metres: original ground plus up to LIFT_CM."""
    return height + LIFT_CM / 100 * lift(height, metres)


def cell_points(mask, metres, cell_m=CELL_M):
    """First row-major point per occupied cell, sorted as centred world (x, y) metres."""
    pixels = np.argwhere(mask)
    if not len(pixels):
        return []
    # First pixel per occupied cell preserves diagonal stretches that parity can miss (#62).
    _, first = np.unique(np.floor(pixels * metres / cell_m), axis=0, return_index=True)
    world = (pixels[first] - (np.array(mask.shape) - 1) / 2) * metres
    return sorted((round(x), round(y)) for y, x in world)


def waterline(height, metres):
    """World (x, y) m points on the land side of the sea's 3 cm edge, one per 4 m cell."""
    sea = sea_mask(height)
    return cell_points((height >= SAND_FROM) & binary_dilation(sea), metres)


def read_height():
    """Decode the imported, softened 16-bit terrain and its grid spacing (m)."""
    meta = json.loads(TERRAIN.with_suffix(".json").read_text())
    raw = np.asarray(Image.open(TERRAIN.with_suffix(".png")), dtype=float)
    return meta["min_m"] + raw / 65535 * (meta["max_m"] - meta["min_m"]), meta["XYScale"] / 100


def main():
    height, metres = read_height()
    points = waterline(height, metres)
    out = ROOT / "scripts/pcg/waterline.json"
    out.write_text(json.dumps({"points_m": points}) + "\n")
    image = TERRAIN.parent / "beach_lift.png"
    Image.fromarray(np.rint(lift(height, metres) * 255).astype(np.uint8)).save(image)
    print(f"{out.relative_to(ROOT)}: {len(points)} waterline points")
    print(f"{image.relative_to(ROOT)}: {height.shape[1]}x{height.shape[0]}, 8-bit lift, rows along +Y")


if __name__ == "__main__":
    main()
