# editor-py: fresh-siblings
"""Derive the level's first override: a 3 m vegetation-free shore path past its lake.

    scripts/editor-py scripts/pcg/shore_path.py [--check]

Uses terrain/coastline.py's world-cm ring; never edits terrain or paints a material.
Closed Biome exclusion corridor affects every group. Regenerate Core and save level.
"""

import argparse
import importlib
import itertools
import json
import math
from pathlib import Path

import terrain_samples
import unreal
from deadwood_rocks import load
from water_exclusions import EXCLUSION, destroy_managed, offset, place, signed_area, world_points

importlib.reload(terrain_samples)

LABEL = "ForestFootpath_ShoreLake"  # deliberately outside water_exclusions.py's replacement namespace



def smooth(points):
    # SplineComponent.cpp:UpdateSpline computes tangents, not repairs to an external
    # inset polyline. Smooth the coastline inset before making LINEAR corridor edges;
    # three local corner cuts remove the audited 25 m inset's short backtracking loop.
    for _ in range(3):
        points = [points[0]] + [tuple((points[i - 1][axis] + 2 * points[i][axis] + points[i + 1][axis]) / 4
                                     for axis in (0, 1)) for i in range(1, len(points) - 1)] + [points[-1]]
    return points


# The 25 m inset runs along the brink of the coastal bluff for a third of the route: a vegetation-free corridor across
# a 40-60 deg face, which read as a bare contour stripe between planted terraces (#186). Where the ground under the
# route is steeper than STEEP_DEG, the route moves further inland, in INLAND_STEP steps up to INLAND_MAX, to the first
# ground that is gentle there and one step either side of it (the bluff top is 5-10 m in). The built corridor is then
# checked against CORRIDOR_DEG at its centre and both edges, at every vertex and between them (slope_check).
STEEP_DEG, INLAND_STEP, INLAND_MAX, SLOPE_SPAN, CORRIDOR_DEG = 20, 250, 4000, 200, 30


def slopes(points):
    """Ground slope in degrees at each point, from source heights SLOPE_SPAN either side in x and y."""
    probes = [(x + dx, y + dy) for x, y in points
              for dx, dy in ((-SLOPE_SPAN, 0), (SLOPE_SPAN, 0), (0, -SLOPE_SPAN), (0, SLOPE_SPAN))]
    heights = iter(terrain_samples.sample(unreal.Paths.project_saved_dir(), probes))
    return [math.degrees(math.atan(math.hypot(next(heights) - next(heights), next(heights) - next(heights))
                                   / (2 * SLOPE_SPAN))) for _ in points]


def off_steep_ground(coast, distances):
    """`distances` with each inset raised until the corridor there lies on ground gentler than STEEP_DEG."""
    sign = math.copysign(1, distances[0])
    steps = range(-1, INLAND_MAX // INLAND_STEP + 2)  # one step seaward and one beyond the furthest inset, as margins
    lines = [offset(coast, [d + sign * k * INLAND_STEP for d in distances], False) for k in steps]
    flat = iter(slopes([point for line in lines for point in line]))
    gentle = {k: [next(flat) < STEEP_DEG for _ in line] for k, line in zip(steps, lines)}

    def clear(k, i):
        """Gentle at step k and a step either side of it: 5 m of gentle ground under the 3 m corridor."""
        return gentle[k - 1][i] and gentle[k][i] and gentle[k + 1][i]

    def inset(i, least):
        """The first clear step at or beyond `least` for point i; none within INLAND_MAX is an error."""
        found = next((k for k in steps[1:-1] if k >= least and clear(k, i)), None)
        if found is None:
            raise RuntimeError(f"Footpath: no ground gentler than {STEEP_DEG} deg within {INLAND_MAX / 100:.0f} m "
                               f"inland of route point {i} {coast[i]}; route needs adjustment")
        return found

    # Only a point whose corridor touches steep ground has to move.
    first = [inset(i, 0) for i in range(len(coast))]
    # A point moves with its neighbours, so the route does not zigzag between the brink and the top; where it moves, it
    # goes to an inset checked for that point, not just to its neighbours' step.
    extra = [inset(i, max(first[max(0, i - 2):i + 3])) for i in range(len(first))]
    moved = sum(1 for k in extra if k)
    print("Footpath inland steps per route point:", "".join(format(k, "x") for k in extra))
    print(f"Footpath: {moved} of {len(extra)} route points moved inland off ground steeper than {STEEP_DEG} deg, "
          f"by up to {max(extra) * INLAND_STEP / 100:.1f} m")
    return [d + sign * k * INLAND_STEP for d, k in zip(distances, extra)]


def slope_check(centre):
    """Fail when the corridor to be built crosses ground steeper than CORRIDOR_DEG: its centre line and both edges, at
    each vertex and midway between vertices. The search above works on the unsmoothed route; this checks the result."""
    dense = [p for a, b in itertools.pairwise(centre) for p in (a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))] + [centre[-1]]
    worst = max((slope, side, point) for side in (-150, 0, 150)
                for slope, point in zip(slopes(offset(dense, [side] * len(dense), False)), dense))
    print(f"Footpath steepest corridor ground {worst[0]:.0f} deg ({worst[1]:+d} cm from the centre line at {worst[2]})")
    if worst[0] > CORRIDOR_DEG:
        raise RuntimeError(f"Footpath corridor crosses ground steeper than {CORRIDOR_DEG} deg; route needs adjustment")


def corridor(points):
    outline = offset(points, [150] * len(points), False) + offset(points, [-150] * len(points), False)[::-1]
    # FGeomTools2D has no Python binding; reject strict non-adjacent segment crossings
    # before authoring, rather than passing an ambiguous polygon to the native sampler.
    def side(a, b, p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (p[0] - a[0]) * (b[1] - a[1])
    segments = list(zip(outline, outline[1:] + outline[:1]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 2, len(segments)):
            if i == 0 and j == len(segments) - 1:
                continue
            c, d = segments[j]
            if side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0:
                raise RuntimeError(f"Footpath corridor self-intersects at segments {i}, {j}; adjust route")
    return outline


def route(actors):
    lakes = [a for a in actors if isinstance(a, unreal.WaterBodyLake)]
    if len(lakes) != 1:
        raise RuntimeError("Footpath expects one loaded lake")
    ring = json.loads((Path(unreal.Paths.project_saved_dir()) / "Terrain/vilm_coastline.json").read_text())
    if len(ring) < 3 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in ring):
        raise RuntimeError("Invalid world-cm coastline; run scripts/terrain/coastline.py")
    # Coastline is deliberately simplified to 15 m; densify linearly to 10 m before offsetting.
    # SplineComponent samples authored splines, not this external contour (UE 5.8 SplineComponent.h).
    dense = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        count = max(1, math.ceil(math.dist(a, b) / 1000))
        dense += [(a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count) for i in range(count)]
    inward = 2500 if signed_area(dense) > 0 else -2500
    inset = offset(dense, [inward] * len(dense), True)
    lake = lakes[0].get_actor_location()
    middle = min(range(len(inset)), key=lambda i: math.hypot(inset[i][0] - lake.x, inset[i][1] - lake.y))
    # 600 m arc centred on the coast nearest the lake, without level-specific hand coordinates.
    indices = [middle]
    for direction in (-1, 1):
        index, distance, side = middle, 0, []
        while distance < 30000:
            nxt = (index + direction) % len(inset)
            distance += math.dist(inset[index], inset[nxt])
            side.append(nxt)
            index = nxt
            if len(side) >= len(inset) // 2:
                raise RuntimeError("Coastline too short for a 600 m footpath")
        indices = side[::-1] + indices if direction < 0 else indices + side
    # Bow inland to pass 15 m outside the lake's coast-facing shoreline, then return to the shore.
    shoreline = world_points(lakes[0])
    nearest = min(shoreline, key=lambda p: math.hypot(p.x - dense[middle][0], p.y - dense[middle][1]))
    peak = max(2500, math.hypot(nearest.x - dense[middle][0], nearest.y - dense[middle][1]) - 1500)
    distances = [math.copysign(2500 + (peak - 2500) * math.sin(math.pi * j / (len(indices) - 1))**2, inward)
                 for j in range(len(indices))]
    distances = off_steep_ground([dense[i] for i in indices], distances)
    centre = smooth(offset([dense[i] for i in indices], distances, False))
    # FGeomTools2D::IsPointInPolygon (UE 5.8 Engine/Public/GeomTools.h) has no Python binding.
    # Even/odd crossings validate this external route against the authored water exclusion polygons.
    def inside(x, y, polygon):
        return sum((a.y > y) != (b.y > y) and x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x
                   for a, b in zip(polygon, polygon[1:] + polygon[:1])) % 2
    polygons = []
    for actor in actors:
        if actor.get_actor_label().startswith("ForestExclusion_"):
            spline = actor.get_component_by_class(unreal.SplineComponent)
            polygons.append([spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
                             for i in range(spline.get_number_of_spline_points())])
    for side in (-150, 0, 150):
        if any(inside(x, y, polygon) for x, y in offset(centre, [side] * len(centre), False) for polygon in polygons):
            raise RuntimeError("Footpath crosses a water exclusion; route needs adjustment")
    slope_check(centre)
    # Saved source samples work with unloaded WP cells; the imported surface still needs a PIE walk.
    heights = terrain_samples.sample(unreal.Paths.project_saved_dir(), centre)
    if min(heights) < 200:
        raise RuntimeError("Footpath crosses source beach/water")
    # Check a 20 m walking baseline, rather than #29's isolated 2 m vertex defects.
    grades = []
    for i in range(len(centre) - 1):
        distance, j = 0, i
        while j + 1 < len(centre) and distance < 2000:
            distance += math.dist(centre[j], centre[j + 1])
            j += 1
        if distance >= 2000:
            grades.append((abs(heights[j] - heights[i]) / distance, i, j, distance))
    grade, i, j, distance = max(grades)
    print(f"Footpath max 20 m grade {grade:.1%}: {centre[i]} -> {centre[j]}, "
          f"Z {heights[i]:.0f} -> {heights[j]:.0f} cm, baseline {distance:.0f} cm")
    if grade > 0.35:
        raise RuntimeError("Footpath exceeds 35% grade over 20 m; route needs adjustment")
    return corridor(centre)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    load(EXCLUSION)
    outline = route(actors)
    if args.check:
        print(f"Footpath preflight OK: {len(outline)} corridor vertices; no changes")
        return
    # Only replace our override, leaving water splines and any future hand-authored overrides alone.
    for actor in actors:
        if actor.get_actor_label() == LABEL:
            destroy_managed(subsystem, actor)
    place(LABEL, outline, 1000)
    print("Footpath built: 600 m shore arc nearest lake, 25 m inland (further where that is steep) with lake detour, "
          "3 m wide. Regenerate ALL groups; save level")


if __name__ == "__main__":
    main()
