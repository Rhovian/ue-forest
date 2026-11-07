# editor-py: fresh-siblings
"""Find the canopy gaps in the generated forest and write them to canopy_gaps.json (#71 item 2).

    scripts/editor-py scripts/pcg/canopy_gaps.py

Reads the Trees group's generated points (ForestPCGLibrary.GetGeneratedPointLocations), so run it on a loaded level
after a regenerate, and again whenever the Trees group changes. A gap is ground whose nearest trunk is at least MIN_GAP
away while trees stand in all eight octants within RING (so shores are not gaps), at least KEEPOUT from the stream, lake
and footpath exclusion splines (their corridors are tree-free but not gaps), and outside the meadows.
saplings_understory.py reads the JSON and grows dense regeneration in each gap.
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import meadow
import unreal

STEP = 3  # m between probes
RING = 20  # m: trees must surround the probe within this radius
MIN_GAP = 9  # m to the nearest trunk; typical spacing is 2-5 m (measured)
KEEPOUT = 6  # m of clearance from an exclusion spline; gap radii are also cut back to it
CROWN = 4  # m of crown overhang taken off the trunk distance: the open sky is smaller than the trunk-free disc
OUT = Path(meadow.__file__).with_name("canopy_gaps.json")  # editor-py runs scripts without __file__


def gaps(trunks, exclusions):
    """[(x, y, z, radius)] in metres (z: mean height of the surrounding trunks): the largest open probes first, kept only where they don't overlap a kept gap."""
    cells, keepout = defaultdict(list), defaultdict(list)
    for x, y, z in trunks:
        cells[(int(x // 10), int(y // 10))].append((x, y, z))
    for x, y in exclusions:
        keepout[(int(x // 10), int(y // 10))].append((x, y))
    xs, ys = [t[0] for t in trunks], [t[1] for t in trunks]
    found = []
    for gx in range(int(min(xs)), int(max(xs)), STEP):
        for gy in range(int(min(ys)), int(max(ys)), STEP):
            if any(math.hypot(gx - mx, gy - my) < radius for mx, my, radius in meadow.MEADOWS):
                continue
            near = [(x - gx, y - gy, z) for dx in range(-2, 3) for dy in range(-2, 3)
                    for x, y, z in cells.get((gx // 10 + dx, gy // 10 + dy), []) if math.hypot(x - gx, y - gy) < RING]
            if len({int(math.atan2(y, x) // (math.pi / 4)) for x, y, _ in near}) < 8:
                continue
            nearest = min(math.hypot(x, y) for x, y, _ in near)
            clear = min([math.hypot(x - gx, y - gy) for dx in range(-2, 3) for dy in range(-2, 3)
                         for x, y in keepout.get((gx // 10 + dx, gy // 10 + dy), [])] + [RING])
            radius = min(nearest - CROWN, clear - KEEPOUT)
            if nearest >= MIN_GAP and radius >= MIN_GAP - CROWN:
                found.append((radius, gx, gy, sum(z for _, _, z in near) / len(near)))
    kept = []
    for radius, x, y, z in sorted(found, reverse=True):
        if all(math.hypot(x - kx, y - ky) > radius + kr for kx, ky, _, kr in kept):
            kept.append((x, y, round(z, 1), round(radius, 1)))
    return kept


def main():
    trunks = [(p.x / 100, p.y / 100, p.z / 100) for actor in unreal.EditorLevelLibrary.get_all_level_actors()
              for component in actor.get_components_by_class(unreal.PCGComponent)
              for p in unreal.ForestPCGLibrary.get_generated_point_locations(component, "GEN:Trees")]
    if not trunks:
        raise RuntimeError("No generated Trees points: load all cells and regenerate the biome first")
    exclusions = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.actor_has_tag("PCG_BiomeExclusion"):
            for spline in actor.get_components_by_class(unreal.SplineComponent):
                for i in range(int(spline.get_spline_length() / 200) + 1):
                    p = spline.get_location_at_distance_along_spline(i * 200, unreal.SplineCoordinateSpace.WORLD)
                    exclusions.append((p.x / 100, p.y / 100))
    if not exclusions:
        raise RuntimeError("No exclusion splines loaded: run water_exclusions.py and shore_path.py first")
    found = gaps(trunks, exclusions)
    OUT.write_text(json.dumps({"trees": len(trunks), "gaps_m": found}, indent=0) + "\n")
    print(f"{len(found)} canopy gaps from {len(trunks)} trees -> {OUT.name}; "
          f"{sum(math.pi * r * r for *_, r in found) / 10000:.1f} ha open")


if __name__ == "__main__":
    main()
