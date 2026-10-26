# editor-py: fresh-siblings
"""Derive the level's first override: a 3 m vegetation-free shore path past its lake.

    scripts/editor-py scripts/pcg/shore_path.py [--check]

Uses terrain/coastline.py's world-cm ring; never edits terrain or paints a material.
Closed Biome exclusion corridor affects every group. Regenerate Core and save level.
"""

import argparse
import importlib
import json
import math
from pathlib import Path

import terrain_samples
import unreal
from deadwood_rocks import load
from water_exclusions import EXCLUSION, offset, place, signed_area, world_points

importlib.reload(terrain_samples)

LABEL = "ForestFootpath_ShoreLake"  # deliberately outside water_exclusions.py's replacement namespace


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
    centre = offset([dense[i] for i in indices], distances, False)
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
    return offset(centre, [150] * len(centre), False) + offset(centre, [-150] * len(centre), False)[::-1]


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
            subsystem.destroy_actor(actor)
    place(LABEL, outline, 1000)
    print("Footpath built: 600 m shore arc nearest lake, 25 m inland with lake detour, 3 m wide. Regenerate ALL groups; save level")


if __name__ == "__main__":
    main()
