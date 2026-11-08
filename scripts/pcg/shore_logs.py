"""Place mossy logs across the lake shoreline, half on the bank and half in the water (#114, lake_shore_01).

    scripts/editor-py scripts/pcg/shore_logs.py

Biome Core keeps deadwood out of the water keepout, so no log can cross the shore by placement rules; these few are
placed directly. Each sits on a lake spline point chosen for a review view (SITES), its long axis along the shore
normal (from the lake's centre outward), pitched so its underside rests on the bank at the inland end and just under
the water surface at the other, with its moss shell (moss_shells.py) as a second component at the same transform. Reruns
replace the actors by label. Saves only their actor packages.
"""

import importlib
import math

import biome_variants
import unreal

LABEL = "ShoreLog"  # label prefix and outliner folder
# Review view -> how far (m) to look for a lake spline point in front of it (see site()).
SITES = {"lake_edge": (852.7, -414.3, -105, 40), "lake_shore": (800, -390, -48, 110)}
CONE, NEAR = 25, 10  # deg either side of the view's yaw; m
HOST = 1  # LOG_VARIANTS row: Large_Fallen_Tree wd1mbcvbw, the nurse-log trunk
SCALE = 0.8  # of a 17 m trunk: about 13 m, half of it over the water; at 0.55 the bank plants hid it
SINK = 8  # cm the underside sits below the bank and bed line, so neither end floats
AFLOAT = 20  # cm below the water surface that the log's water end rests at most

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def ground(x, y):
    """Landscape height (the lake bed under water), ignoring everything else; None off the landscape."""
    start, end, ignored = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000), []
    for _ in range(64):
        hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True,
                                                     ignored, unreal.DrawDebugTrace.NONE, True)
        if hit is None:
            return None
        fields = hit.to_tuple()
        if isinstance(fields[9], unreal.LandscapeProxy):
            return fields[4].z
        ignored.append(fields[9])
    return None


def site(points, x, y, yaw, reach):
    """The nearest spline point inside the view's central cone (CONE deg either side), at least NEAR m out: close
    enough to read, far enough that the bank plants do not hide it."""
    def bearing(p):
        return abs((math.degrees(math.atan2(p.y - y, p.x - x)) - yaw + 180) % 360 - 180)

    ahead = [p for p in points if bearing(p) < CONE and NEAR * 100 < math.hypot(p.x - x, p.y - y) < reach * 100]
    if not ahead:
        raise RuntimeError(f"no lake shoreline in view of ({x / 100:.0f}, {y / 100:.0f}) m within {reach} m")
    return min(ahead, key=lambda p: math.hypot(p.x - x, p.y - y))


def main():
    variants = importlib.reload(biome_variants)
    host = unreal.load_asset(variants.VENDOR + variants.LOG_VARIANTS[HOST][0])
    shell = unreal.load_asset(f"/Game/ForestBiome/MossShells/SM_{host.get_name()}_MossShell")
    if shell is None:
        raise RuntimeError("Run moss_shells.py first")
    lakes = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.WaterBodyLake)]
    if len(lakes) != 1:
        raise RuntimeError(f"expected one lake, found {len(lakes)}")
    spline = lakes[0].get_editor_property("spline_comp")
    surface = lakes[0].get_actor_location().z  # the lake's water level
    points = [spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
              for i in range(spline.get_number_of_spline_points())]
    cx, cy = sum(p.x for p in points) / len(points), sum(p.y for p in points) / len(points)
    box = host.get_bounding_box()
    along_x = box.max.x - box.min.x >= box.max.y - box.min.y  # the trunk's long axis in the mesh
    half = SCALE * (max(box.max.x - box.min.x, box.max.y - box.min.y)) / 2
    old = {a.get_actor_label(): a for a in actors.get_all_level_actors() if a.get_actor_label().startswith(LABEL + "_")}
    placed = []
    for name, (x, y, yaw, reach) in SITES.items():
        p = site(points, x * 100, y * 100, yaw, reach)
        out = math.atan2(p.y - cy, p.x - cx)  # shore normal, pointing inland
        ux, uy = math.cos(out), math.sin(out)
        inland, water = ground(p.x + ux * half, p.y + uy * half), ground(p.x - ux * half, p.y - uy * half)
        if inland is None or water is None:
            raise RuntimeError(f"{name}: no landscape under the log's ends; are all cells loaded?")
        # The water end rests just under the surface (on a snag or stone), not on the lake bed: lying on the bed, most
        # of the trunk sank out of sight.
        water = max(water, surface - AFLOAT)
        pitch = math.degrees(math.atan2(inland - water, 2 * half))  # the inland end is higher
        z = (inland + water) / 2 - box.min.z * SCALE - SINK
        # The trunk's axis points inland: yaw along the normal, plus 90 deg if the mesh lies along Y.
        rotation = unreal.Rotator(roll=0, pitch=pitch, yaw=math.degrees(out) + (0 if along_x else 90))
        if not along_x:  # a Y-axis trunk tilts by roll, not pitch
            rotation = unreal.Rotator(roll=-pitch, pitch=0, yaw=math.degrees(out) + 90)
        for part, mesh in (("Log", host), ("Shell", shell)):
            label = f"{LABEL}_{name}_{part}"
            actor = old.pop(label, None) or actors.spawn_actor_from_object(mesh, unreal.Vector(p.x, p.y, z))
            actor.set_actor_location_and_rotation(unreal.Vector(p.x, p.y, z), rotation, False, False)
            actor.set_actor_scale3d(unreal.Vector(SCALE, SCALE, SCALE))
            actor.set_actor_label(label)
            actor.set_folder_path(LABEL)
            if part == "Shell":
                actor.get_component_by_class(unreal.StaticMeshComponent).set_collision_enabled(
                    unreal.CollisionEnabled.NO_COLLISION)
            placed.append(actor)
        print(f"{name}: log at ({p.x / 100:.1f}, {p.y / 100:.1f}) m, bank {inland / 100:.2f} m, bed {water / 100:.2f} m,"
              f" pitch {pitch:.1f} deg")
    packages = [a.get_package() for a in old.values()]
    for actor in old.values():
        actors.destroy_actor(actor)
    packages += [a.get_package() for a in placed]
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError("could not save the shore logs")
    print(f"{len(placed) // 2} shore logs; {len(old)} removed")


main()
