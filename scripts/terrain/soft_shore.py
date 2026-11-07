#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Soften the last metres of land before the beach into a gentle ramp (#38, operator ruling: soft slope, option 2).

    scripts/terrain/soft_shore.py

Reads heightmap.py's Forest/Saved/Terrain/vilm_1513.png (+ .json) and writes vilm_1513_shore.png (same 16-bit
encoding and metadata, .json alongside), vilm_1513_shore_rg.png (the same heights as 8-bit R high byte and G low byte
for ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget; scripts/terrain/import_heights.py) and
vilm_1513_shore_samples.json (pixels and world points that import_heights.py checks).
Ground is only ever lowered. Within RAMP_FULL of the beach (the sea, i.e. below-SAND_FROM ground connected to the map
edge, and the sand below SHORE connected to it) no step between neighbouring vertices rises more than RAMP_DEG, from
the beach's own heights outward; the limit fades out by RAMP_FADE, where the original terrain resumes. So the bank at
the sand line becomes a ramp (transition_ground_01) and the bluffs further inland stay.
"""

import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label

ROOT = Path(__file__).resolve().parents[2]
TERRAIN = ROOT / "Forest/Saved/Terrain"
SAND_FROM = 0.03  # m above the sea: below is sea
SHORE = 0.75  # m, MI_ForestFloor's ShoreHeight: the top of the beach sand
RAMP_DEG = 12  # steepest rise between neighbouring vertices within RAMP_FULL
RAMP_FULL = 10.0  # m from the beach where the slope limit applies in full
RAMP_FADE = 20.0  # m from the beach where the original terrain resumes


def beach_mask(height):
    """The sea (below SAND_FROM, connected to the map edge) and the sand below SHORE connected to it."""
    low, _ = label(height < SAND_FROM)
    edge = np.unique(np.concatenate([low[0], low[-1], low[:, 0], low[:, -1]]))
    sea = np.isin(low, edge[edge > 0])
    sand, _ = label(height < SHORE)
    return np.isin(sand, np.unique(sand[sea])) & (height < SHORE)


def soften(height, metres):
    """Heights (m) slope-limited to RAMP_DEG outward from the beach within RAMP_FADE (full within RAMP_FULL); only
    ever lowered."""
    beach = beach_mask(height)
    if not beach.any():
        return height.copy()
    distance = distance_transform_edt(~beach, sampling=metres)
    band = ~beach & (distance <= RAMP_FADE)
    rise = math.tan(math.radians(RAMP_DEG))
    limited = height.copy()
    steps = [(dr, dc, metres * math.hypot(dr, dc)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
    for _ in range(4 * int(RAMP_FADE / metres) + 8):  # propagation settles within a few band widths
        before = limited.copy()
        for dr, dc, step in steps:
            neighbour = np.full_like(limited, np.inf)
            neighbour[max(dr, 0):limited.shape[0] + min(dr, 0), max(dc, 0):limited.shape[1] + min(dc, 0)] = \
                limited[max(-dr, 0):limited.shape[0] + min(-dr, 0), max(-dc, 0):limited.shape[1] + min(-dc, 0)]
            limited = np.where(band, np.minimum(limited, neighbour + step * rise), limited)
        if np.array_equal(limited, before):
            break
    t = np.clip((distance - RAMP_FULL) / (RAMP_FADE - RAMP_FULL), 0, 1)
    weight = np.where(band, 1 - t * t * (3 - 2 * t), 0)  # 1 within RAMP_FULL, smooth to 0 at RAMP_FADE
    return height - weight * (height - limited)


def samples(height, soft, half, metres, count=6):
    """Pixels and world points (cm) to check the import: `count` lowered by over 3 m, `count` unchanged above 5 m."""
    rng = np.random.default_rng(0)
    picks = []
    for mask in ((height - soft) > 3, ((height - soft) == 0) & (height > 5)):
        cells = np.argwhere(mask)
        picks += [tuple(cells[i]) for i in rng.choice(len(cells), min(count, len(cells)), replace=False)]
    return [{"col": int(c), "row": int(r), "x_cm": int((c - half) * metres * 100), "y_cm": int((r - half) * metres * 100),
             "z_cm": round(float(soft[r, c]) * 100, 1)} for r, c in picks]


def main():
    meta = json.loads((TERRAIN / "vilm_1513.json").read_text())
    raw = np.asarray(Image.open(TERRAIN / "vilm_1513.png"), dtype=float)
    span, metres = meta["max_m"] - meta["min_m"], meta["XYScale"] / 100
    height = meta["min_m"] + raw / 65535 * span
    soft = soften(height, metres)
    encoded = np.rint((soft - meta["min_m"]) * 65535 / span).astype(np.uint16)
    Image.fromarray(encoded).save(TERRAIN / "vilm_1513_shore.png")
    shutil.copy(TERRAIN / "vilm_1513.json", TERRAIN / "vilm_1513_shore.json")
    rg = np.zeros(encoded.shape + (3,), dtype=np.uint8)
    rg[..., 0], rg[..., 1] = encoded >> 8, encoded & 0xFF
    Image.fromarray(rg, "RGB").save(TERRAIN / "vilm_1513_shore_rg.png")
    soft = meta["min_m"] + encoded / 65535 * span  # as stored
    points = samples(height, soft, (height.shape[0] - 1) / 2, metres)
    for point in points:
        point["encoded"] = int(encoded[point["row"], point["col"]])
    (TERRAIN / "vilm_1513_shore_samples.json").write_text(json.dumps(points, indent=1) + "\n")
    lowered = height - soft
    print(f"lowered {np.count_nonzero(lowered > 0.05) * metres ** 2 / 1e4:.1f} ha, max {lowered.max():.2f} m;"
          f" wrote vilm_1513_shore.png, _rg.png, _samples.json")


if __name__ == "__main__":
    main()
