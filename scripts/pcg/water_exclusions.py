# editor-py: fresh-siblings
"""Keep the Forest Biome out of the level's lakes and rivers.

    scripts/editor-py scripts/pcg/water_exclusions.py [--lake-margin CM] [--river-margin CM] [--keepout CM]

Replaces every ForestExclusion_* and ForestKeepout_* actor with splines built from the open level's water
bodies: each lake's shoreline pushed out by a margin, and a corridor along each river, its half width plus the
margin on each side. ForestExclusion_* (tag PCG_BiomeExclusion, the narrow margin) keeps everything out of the
water; ground plants grow up to it, so banks are green to the water (stream_bank_01, #71 item 5).
ForestKeepout_* (tag KEEPOUT_TAG, the wider keepout) is ignored by Biome Core; exact_exclusions.py applies it to
every group but ground plants, so trees, logs and rocks keep their distance. The ocean is handled by the shore-height
filter.
Saves nothing; save the level afterwards.
"""

import argparse
import builtins
import math

import unreal

EXCLUSION = "/PCGBiomeCore/Blueprints/BP_PCGBiomeExclusionSpline"



# Names survive fresh-sibling module reloads, but are scoped to the editor world.
# FileHelpers.cpp saves empty external packages by deleting them; the missing part
# is retaining their allowlist membership after the actor disappears from the level.
TRACKED = "_forest_managed_actor_packages"


def remembered_packages(world):
    return set(getattr(builtins, TRACKED, {}).get(world.get_path_name(), ()))


def remember_packages(world, names):
    if not hasattr(builtins, TRACKED):
        setattr(builtins, TRACKED, {})
    getattr(builtins, TRACKED).setdefault(world.get_path_name(), set()).update(names)


def destroy_managed(subsystem, actor):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    package = unreal.EditorAssetLibrary.get_package_for_object(actor).get_name()
    if not subsystem.destroy_actor(actor):
        raise RuntimeError(f"Could not destroy managed actor in {package}")
    remember_packages(world, [package])
    print(f"Managed deletion queued for save: {package}")


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


KEEPOUT_TAG = "Forest_WaterKeepout"


def place(label, outline, z, tag=None):
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
    if tag:  # Biome Core selects exclusions by the PCG_BiomeExclusion tag: swap it so only exact_exclusions applies this
        actor.tags = [tag]
    print(f"{label}: {len(outline)} points")
    return actor


def main():
    parser = argparse.ArgumentParser(prog="water_exclusions.py")
    parser.add_argument("--lake-margin", type=float, default=60.0)
    # Negative: the river spline's width (7.5 m) is wider than its visible water, so the corridor is narrowed to it.
    parser.add_argument("--river-margin", type=float, default=-100.0)
    parser.add_argument("--keepout", type=float, default=300.0)
    args = parser.parse_args()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label().startswith(("ForestExclusion_", "ForestKeepout_")):
            destroy_managed(actors, actor)
    for water in actors.get_all_level_actors():
        if isinstance(water, unreal.WaterBodyLake):
            pts = [(p.x, p.y) for p in world_points(water)]
            # Left of travel is inside for a counter-clockwise loop, so push out with a negative distance.
            sign = -1 if signed_area(pts) > 0 else 1
            for prefix, margin, tag in (("ForestExclusion_", args.lake_margin, None),
                                        ("ForestKeepout_", args.keepout, KEEPOUT_TAG)):
                place(prefix + water.get_actor_label(), offset(pts, [sign * margin] * len(pts), True), 1000.0, tag)
        elif isinstance(water, unreal.WaterBodyRiver):
            body = water.get_editor_property("water_body_component")
            spline = water.get_editor_property("spline_comp")
            pts = [(p.x, p.y) for p in world_points(water)]
            for prefix, margin, tag in (("ForestExclusion_", args.river_margin, None),
                                        ("ForestKeepout_", args.keepout, KEEPOUT_TAG)):
                half = [
                    body.get_river_width_at_spline_input_key(float(i)) / 2 + margin
                    if hasattr(body, "get_river_width_at_spline_input_key")
                    else 500.0 + margin
                    for i in range(spline.get_number_of_spline_points())
                ]
                left, right = offset(pts, half, False), offset(pts, [-h for h in half], False)
                place(prefix + water.get_actor_label(), left + right[::-1], 1000.0, tag)


if __name__ == "__main__":
    main()
