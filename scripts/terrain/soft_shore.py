#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Soften the last metres of land before the beach into a gentle ramp (#38, operator ruling: soft slope, option 2).

    scripts/terrain/soft_shore.py

Reads heightmap.py's Forest/Saved/Terrain/vilm_1513.png (+ .json) and writes vilm_1513_shore.png (same 16-bit
encoding and metadata, .json alongside) plus vilm_1513_shore_rg.png, the same heights as 8-bit R (high byte) and G
(low byte) for ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget (scripts/terrain/import_heights.py).
Ground is only ever lowered: within RAMP_FULL of the beach's inland edge (sand below SHORE connected to the sea) it may
rise from SHORE by at most RAMP_DEG, fading to the original terrain by RAMP_FADE, so the bank at the sand line becomes
a ramp (transition_ground_01) and the bluffs further inland stay.
"""

import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label
from skimage.graph import MCP_Geometric

ROOT = Path(__file__).resolve().parents[2]
TERRAIN = ROOT / "Forest/Saved/Terrain"
SAND_FROM = 0.03  # m above the sea: below is sea
SHORE = 0.75  # m, MI_ForestFloor's ShoreHeight: the top of the beach sand
RAMP_DEG = 12  # steepest rise from the sand within RAMP_FULL
RAMP_FULL = 10.0  # m from the beach where the ramp applies in full
RAMP_FADE = 20.0  # m from the beach where the original terrain resumes


def soften(height, metres):
    """Heights (m) with the ground within RAMP_FADE of the beach lowered toward a RAMP_DEG ramp; never raised."""
    sea = height < SAND_FROM
    if not sea.any():
        return height.copy()
    # The beach: sea and sand below SHORE connected to it (not low ground around the lake or stream).
    parts, _ = label(height < SHORE)
    beach = np.isin(parts, np.unique(parts[sea]))
    # Geodesic distance from the beach in metres, around headlands rather than across water.
    distance, _ = MCP_Geometric(np.ones_like(height)).find_costs(np.argwhere(beach))
    distance = distance * metres
    ramp = SHORE + distance * math.tan(math.radians(RAMP_DEG))
    t = np.clip((distance - RAMP_FULL) / (RAMP_FADE - RAMP_FULL), 0, 1)
    weight = 1 - t * t * (3 - 2 * t)  # 1 within RAMP_FULL, smooth to 0 at RAMP_FADE
    lowered = height - weight * np.maximum(height - ramp, 0)
    lowered[beach] = height[beach]
    return lowered


def main():
    meta = json.loads((TERRAIN / "vilm_1513.json").read_text())
    raw = np.asarray(Image.open(TERRAIN / "vilm_1513.png"), dtype=float)
    span = meta["max_m"] - meta["min_m"]
    height = meta["min_m"] + raw / 65535 * span
    soft = soften(height, meta["XYScale"] / 100)
    encoded = np.rint((soft - meta["min_m"]) * 65535 / span).astype(np.uint16)
    Image.fromarray(encoded).save(TERRAIN / "vilm_1513_shore.png")
    shutil.copy(TERRAIN / "vilm_1513.json", TERRAIN / "vilm_1513_shore.json")
    rg = np.zeros(encoded.shape + (3,), dtype=np.uint8)
    rg[..., 0], rg[..., 1] = encoded >> 8, encoded & 0xFF
    Image.fromarray(rg, "RGB").save(TERRAIN / "vilm_1513_shore_rg.png")
    lowered = height - soft
    print(f"lowered {np.count_nonzero(lowered > 0.05) * (meta['XYScale'] / 100) ** 2 / 1e4:.1f} ha, max {lowered.max():.2f} m;"
          f" wrote vilm_1513_shore.png, vilm_1513_shore_rg.png")


if __name__ == "__main__":
    main()
