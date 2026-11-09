"""Bake the water-bed distance textures for the floor material (#141).

    scripts/editor-py scripts/materials/water_bed_mask.py

The ground under the lake and stream showed the forest's moss floor (operator, 2026-11-09: the bed should not be the
same ground as above it, but keep some of its green). Two grayscale textures on T_GroundcoverMask's 2 m grid (same
cells, same UVs) hold the signed distance to the water's edge, positive in the water, SCALE cm per step around 128:
T_WaterBedMask for every water body, T_LakeMask for the lake alone (its stones and shallow plants; the stream gets the
bed only). A distance interpolates smoothly between cells, so the bed's edge lands where it should, not in 2 m steps.
The edge is the water exclusion outline (ForestExclusion_<water>, water_exclusions.py) less MARGINS. Rerun after
water_exclusions.py, then forest_floor.py.
"""

import math
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
from groundcover_mask import CELL, bounds, import_texture

PREFIX = "ForestExclusion_"
# cm the outline lies outside the visible water's edge, at water_exclusions.py's defaults (rerun both if those change):
# the lake's is pushed out by --lake-margin; the stream's corridor is narrowed to the visible water by its negative
# --river-margin, so it already is the edge (#149 review).
MARGINS = {"Lake": 60.0, "Stream": 0.0}
LAKES = ("Lake",)
SCALE = 8.0  # cm per step: 128 +- 127 steps covers +-10 m of the edge
REACH = 1200.0  # cm around each outline that is measured; beyond it a cell is "far" (0 outside, 255 inside)


def outlines():
    found = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = actor.get_actor_label()
        if label.startswith(PREFIX):
            spline = actor.get_component_by_class(unreal.SplineComponent)
            world = unreal.SplineCoordinateSpace.WORLD
            count = spline.get_number_of_spline_points() * 8  # follow the curve between points
            length = spline.get_spline_length()
            found[label[len(PREFIX):]] = [(p.x, p.y) for p in (
                spline.get_location_at_distance_along_spline(length * k / count, world) for k in range(count))]
    missing = set(MARGINS) - set(found)
    if missing:
        raise SystemExit(f"Run water_exclusions.py first: no outline for {sorted(missing)}")
    return found


def signed_distance(points, x, y):
    """Distance from (x, y) to the closed outline, positive inside."""
    best, inside = math.inf, False
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        if (ay <= y) != (by <= y) and x < ax + (y - ay) * dx / (dy or 1e-9):
            inside = not inside
    return best if inside else -best


def bake(name, bodies, x0, y0, width, height):
    pixels = bytearray(width * height)  # 0: far outside
    for points, margin in bodies:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        i0, i1 = max(0, int((min(xs) - REACH - x0) // CELL)), min(width, int((max(xs) + REACH - x0) // CELL) + 1)
        j0, j1 = max(0, int((min(ys) - REACH - y0) // CELL)), min(height, int((max(ys) + REACH - y0) // CELL) + 1)
        for j in range(j0, j1):
            for i in range(i0, i1):
                d = signed_distance(points, x0 + (i + 0.5) * CELL, y0 + (j + 0.5) * CELL) - margin
                value = max(1, min(255, round(128 + d / SCALE)))
                pixels[j * width + i] = max(pixels[j * width + i], value)  # union of the bodies
    import_texture(pixels, width, height, name)
    return sum(1 for v in pixels if v > 128)


def main():
    x0, y0, width, height = bounds()
    found = outlines()
    water = bake("T_WaterBedMask", [(found[n], m) for n, m in MARGINS.items()], x0, y0, width, height)
    lake = bake("T_LakeMask", [(found[n], MARGINS[n]) for n in LAKES], x0, y0, width, height)
    print(f"T_WaterBedMask: {water} cells in water; T_LakeMask: {lake} in the lake ({CELL} cm cells)")


if __name__ == "__main__":
    main()
