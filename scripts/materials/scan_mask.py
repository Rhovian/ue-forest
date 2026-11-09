"""Bake /Game/ForestBiome/T_ScanSandMask: how far from the sand the forest floor's ground scans may grow.

    scripts/editor-py scripts/materials/scan_mask.py

The ground scans (forest_floor.py's Scans layer) are slabs of forest soil with hard edges; on or by the sand they read
as cut-out tiles (operator, 2026-11-09). The floor material only knows height and slope, and a height-through-slope
setback lets scans onto a flat shoulder a metre behind a short bank (#136 review). So this samples the landscape's
height on T_GroundcoverMask's grid (same cells, same UVs), calls every cell below SAND_BELOW_CM (or off the landscape)
sand, and writes black up to SETBACK_CM from it, rising to white over FADE_CM. Rerun after the landscape changes, then
forest_floor.py.

The same distances, the other way round, make T_SandEdgeMask (#38; operator 2026-11-09: a few plants on the sand side
just before the edge, so it is not abrupt): on beach sand (EDGE_ABOVE_CM to EDGE_SHORE_CM), white at the forest
edge fading to black EDGE_CM out; the sea and everything else black.
"""

import sys
from collections import deque
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
from groundcover_mask import CELL, bounds, import_texture

NAME = "T_ScanSandMask"
SAND_BELOW_CM = 120.0  # MI_ForestFloor's ShoreHeight (75) plus its noisy interleave on flat ground
SETBACK_CM = 600.0
FADE_CM = 600.0
EDGE_NAME = "T_SandEdgeMask"
EDGE_CM = 600.0  # cm out onto the sand that the edge plants reach
EDGE_ABOVE_CM = 5.0  # not at or below the sea
EDGE_SHORE_CM = 75.0  # where the sand meets the forest floor: MI_ForestFloor's ShoreHeight (not SAND_BELOW_CM)


def heights(x0, y0, width, height):
    """Landscape z at each cell centre, or None where no landscape is under it."""
    world = unreal.UnrealEditorSubsystem().get_editor_world()
    out = [None] * (width * height)
    for j in range(height):
        for i in range(width):
            x, y = x0 + (i + 0.5) * CELL, y0 + (j + 0.5) * CELL
            # Ignore each actor in the way and trace again, so placed logs and rocks with collision cannot hide the
            # ground: stepping down past them 1 cm at a time stalled inside the large logs (#38).
            ignored = []
            for _ in range(16):
                hit = unreal.SystemLibrary.line_trace_single(
                    world, unreal.Vector(x, y, 100000), unreal.Vector(x, y, -50000),
                    unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignored, unreal.DrawDebugTrace.NONE, True)
                fields = hit.to_tuple() if hit else None
                if not fields or not fields[0]:
                    break
                if "Landscape" in type(fields[9]).__name__:
                    out[j * width + i] = fields[4].z
                    break
                ignored.append(fields[9])
    return out


def distances(sand, width, height):
    """Cells from the nearest sand cell (8-connected steps)."""
    far = width + height
    out = [0 if s else far for s in sand]
    queue = deque(k for k, s in enumerate(sand) if s)
    while queue:
        k = queue.popleft()
        i, j = k % width, k // width
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                a, b = i + di, j + dj
                if 0 <= a < width and 0 <= b < height and out[b * width + a] > out[k] + 1:
                    out[b * width + a] = out[k] + 1
                    queue.append(b * width + a)
    return out


def main():
    x0, y0, width, height = bounds()
    z = heights(x0, y0, width, height)
    sand = [h is None or h < SAND_BELOW_CM for h in z]  # no landscape: open sea
    pixels = bytearray(min(255, max(0, round(255 * (d * CELL - SETBACK_CM) / FADE_CM)))
                       for d in distances(sand, width, height))
    import_texture(pixels, width, height, NAME)
    beach = [h is not None and EDGE_ABOVE_CM <= h < EDGE_SHORE_CM for h in z]
    inland = distances([h is not None and h >= EDGE_SHORE_CM for h in z], width, height)  # cells from the forest floor
    edge = bytearray(round(255 * max(0.0, 1 - (d - 1) * CELL / EDGE_CM)) if b else 0 for b, d in zip(beach, inland))
    import_texture(edge, width, height, EDGE_NAME)
    print(f"{EDGE_NAME}: {sum(1 for v in edge if v) * CELL * CELL / 1e4:.0f} m2 of sand edge")
    print(f"{NAME}: {width}x{height} px at {CELL} cm, {sum(sand) * CELL * CELL / 1e8:.1f} ha sand or below, "
          f"{sum(1 for h in z if h is None)} cells without landscape")


if __name__ == "__main__":
    main()
