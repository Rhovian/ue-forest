"""Keep the Forest Biome out of the level's lakes and rivers.

    scripts/editor-py scripts/pcg/water_exclusions.py [--lake-margin CM] [--river-margin CM]

Replaces every ForestExclusion_* actor with Biome Core exclusion splines built from the open level's water
bodies: each lake's shoreline pushed out by the lake margin, and a corridor along each river, its half
width plus the river margin on each side. The ocean is handled by the trees' shore-height filter.
Saves nothing; save the level afterwards.
"""

import argparse
import math

import unreal

EXCLUSION = "/PCGBiomeCore/Blueprints/BP_PCGBiomeExclusionSpline"


def offset(points, distances, closed):
    """Offset a 2D polyline sideways: positive distance is to the left of travel."""
    out = []
    n = len(points)
    for i in range(n):
        prev = points[i - 1] if closed or i > 0 else points[i]
        nxt = points[(i + 1) % n] if closed or i < n - 1 else points[i]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        length = math.hypot(dx, dy) or 1.0
        out.append((points[i][0] - dy / length * distances[i], points[i][1] + dx / length * distances[i]))
    return out


def signed_area(points):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2


def world_points(water):
    spline = water.get_editor_property("spline_comp")
    world = unreal.SplineCoordinateSpace.WORLD
    return [spline.get_location_at_spline_point(i, world) for i in range(spline.get_number_of_spline_points())]


def place(label, outline, z):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_object(unreal.load_asset(EXCLUSION), unreal.Vector(outline[0][0], outline[0][1], z))
    actor.set_actor_label(label)
    spline = actor.get_component_by_class(unreal.SplineComponent)
    spline.set_override_construction_script(True)  # otherwise the Blueprint resets the points on reload
    spline.set_spline_points([unreal.Vector(x, y, z) for x, y in outline], unreal.SplineCoordinateSpace.WORLD, False)
    for i in range(spline.get_number_of_spline_points()):
        spline.set_spline_point_type(i, unreal.SplinePointType.LINEAR, False)
    spline.set_closed_loop(True)
    spline.update_spline()
    print(f"{label}: {len(outline)} points")


def main():
    parser = argparse.ArgumentParser(prog="water_exclusions.py")
    parser.add_argument("--lake-margin", type=float, default=300.0)
    parser.add_argument("--river-margin", type=float, default=300.0)
    args = parser.parse_args()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label().startswith("ForestExclusion_"):
            actors.destroy_actor(actor)
    for water in actors.get_all_level_actors():
        if isinstance(water, unreal.WaterBodyLake):
            pts = [(p.x, p.y) for p in world_points(water)]
            # Left of travel is inside for a counter-clockwise loop, so push out with a negative distance.
            outward = -args.lake_margin if signed_area(pts) > 0 else args.lake_margin
            place(f"ForestExclusion_{water.get_actor_label()}", offset(pts, [outward] * len(pts), True), 1000.0)
        elif isinstance(water, unreal.WaterBodyRiver):
            body = water.get_editor_property("water_body_component")
            spline = water.get_editor_property("spline_comp")
            pts = [(p.x, p.y) for p in world_points(water)]
            half = [
                body.get_river_width_at_spline_input_key(float(i)) / 2 + args.river_margin
                if hasattr(body, "get_river_width_at_spline_input_key")
                else 500.0 + args.river_margin
                for i in range(spline.get_number_of_spline_points())
            ]
            left, right = offset(pts, half, False), offset(pts, [-h for h in half], False)
            place(f"ForestExclusion_{water.get_actor_label()}", left + right[::-1], 1000.0)


if __name__ == "__main__":
    main()
