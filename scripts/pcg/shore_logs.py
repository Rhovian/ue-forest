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
from water_exclusions import KEEPOUT_TAG, place

LABEL = "ShoreLog"  # label prefix and outliner folder
# Each log's footprint, grown by this many cm, is a keepout for every group but the ground plants (KEEPOUT_TAG, applied
# by exact_exclusions.py): Biome Core knew nothing of these hand-placed logs, and a regenerate put a slab and a boulder
# straight through the near one (#160). Rerun exact_exclusions.py and regenerate_biome.py afterwards.
KEEPOUT_CM = 120.0
# Site -> (camera x m, y m, yaw, reach m, side): the lake spline point inside that camera's cone on the near or the far
# shore (see site()). Both are in lake_edge, the bank view judged against lake_shore_01 (poses.py); from the
# lake_shore pose the lake is 55 m and more away behind bank plants, and neither a near- nor a far-shore log read
# there (#115 review; lead ruling on #114).
SITES = {"lake_edge_near": (852.7, -414.3, -105, 40, "near"), "lake_edge_far": (852.7, -414.3, -105, 40, "far")}
CONE, NEAR = 30, 5  # deg either side of the view's yaw; m
SCALE = 0.8  # of a 17 m trunk: about 13 m, half of it over the water; at 0.55 the bank plants hid it
SINK = 8  # cm the underside sits below the bank and bed line, so neither end floats
AFLOAT = 20  # cm below the water surface that the log's water end rests at most
BANK_SAMPLES = (0.5, 1, 1.5, 2, 2.5, 3)  # m inland of the shore point where the trunk's underside is traced
GAP_SAMPLES = (-4, -2, 0, 2, 4)  # m along the normal at which the final gap is reported

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


def site(points, x, y, yaw, reach, side):
    """The nearest ("near") or farthest ("far") spline point inside the view's central cone (CONE deg either side),
    between NEAR m and reach m out."""
    def bearing(p):
        return abs((math.degrees(math.atan2(p.y - y, p.x - x)) - yaw + 180) % 360 - 180)

    ahead = [p for p in points if bearing(p) < CONE and NEAR * 100 < math.hypot(p.x - x, p.y - y) < reach * 100]
    if not ahead:
        raise RuntimeError(f"no lake shoreline in view of ({x / 100:.0f}, {y / 100:.0f}) m within {reach} m")
    return (min if side == "near" else max)(ahead, key=lambda p: math.hypot(p.x - x, p.y - y))


def underside_gap(log, x, y):
    """cm between the landscape and the log's collision underside at (x, y) (negative: sunk into it), traced up from
    5 m below the ground, ignoring the landscape: a trace starting inside the hull would not hit it."""
    z = ground(x, y)
    landscapes = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(x, y, z - 500), unreal.Vector(x, y, z + 500),
                                                 unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, landscapes,
                                                 unreal.DrawDebugTrace.NONE, True)
    fields = hit.to_tuple() if hit else None
    if not fields or fields[9] is None or fields[9].get_actor_label() != log.get_actor_label():
        return None
    return round(fields[4].z - z)


def main():
    variants = importlib.reload(biome_variants)
    hosts = [unreal.load_asset(variants.VENDOR + path) for path, _ in variants.SHORE_LOG_VARIANTS]
    shells = [unreal.load_asset(f"/Game/ForestBiome/MossShells/SM_{host.get_name()}_MossShell") for host in hosts]
    if None in hosts or None in shells:
        raise RuntimeError("SHORE_LOG_VARIANTS must load, each with a shell (run moss_shells.py first)")
    lakes = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.WaterBodyLake)]
    if len(lakes) != 1:
        raise RuntimeError(f"expected one lake, found {len(lakes)}")
    spline = lakes[0].get_editor_property("spline_comp")
    surface = lakes[0].get_actor_location().z  # the lake's water level
    points = [spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
              for i in range(spline.get_number_of_spline_points())]
    cx, cy = sum(p.x for p in points) / len(points), sum(p.y for p in points) / len(points)
    old = {a.get_actor_label(): a for a in actors.get_all_level_actors() if a.get_actor_label().startswith(LABEL + "_")}
    placed = []
    for index, (name, (x, y, yaw, reach, side)) in enumerate(SITES.items()):
        host, shell = hosts[index % len(hosts)], shells[index % len(hosts)]  # appendable: sites cycle the variants
        box = host.get_bounding_box()
        axis = "x" if box.max.x - box.min.x >= box.max.y - box.min.y else "y"  # the trunk's long axis in the mesh
        low, high = getattr(box.min, axis) * SCALE, getattr(box.max, axis) * SCALE  # the trunk's ends from its pivot
        middle, half = (low + high) / 2, (high - low) / 2
        p = site(points, x * 100, y * 100, yaw, reach, side)
        out = math.atan2(p.y - cy, p.x - cx)  # shore normal, pointing inland
        ux, uy = math.cos(out), math.sin(out)
        pitch = 0.0
        for _ in range(2):  # the ends' reach shrinks with the tilt: trace, tilt, trace again at the tilted reach
            reach_h = half * math.cos(pitch)
            inland, bed = ground(p.x + ux * reach_h, p.y + uy * reach_h), ground(p.x - ux * reach_h, p.y - uy * reach_h)
            if inland is None or bed is None:
                raise RuntimeError(f"{name}: no landscape under the log's ends; are all cells loaded?")
            # The water end rests just under the surface (on a snag), not on the lake bed: lying on the bed, most of
            # the trunk sank out of sight.
            water = max(bed, surface - AFLOAT)
            pitch = math.atan2(inland - water, 2 * half)  # the inland end is higher
        # The trunk's long axis points inland and up; the mesh's middle sits over the shore point, its underside
        # SINK below the line between the two rests.
        direction = unreal.Vector(ux * math.cos(pitch), uy * math.cos(pitch), math.sin(pitch))
        up = unreal.Vector(-ux * math.sin(pitch), -uy * math.sin(pitch), math.cos(pitch))
        rotation = (unreal.MathLibrary.make_rot_from_xz if axis == "x" else unreal.MathLibrary.make_rot_from_yz)(direction, up)
        under = (inland + water) / 2 - SINK
        pivot = unreal.Vector(p.x - direction.x * middle - up.x * box.min.z * SCALE,
                              p.y - direction.y * middle - up.y * box.min.z * SCALE,
                              under - direction.z * middle - up.z * box.min.z * SCALE)
        for part, mesh in (("Log", host), ("Shell", shell)):
            label = f"{LABEL}_{name}_{part}"
            actor = old.pop(label, None) or actors.spawn_actor_from_object(mesh, pivot)
            actor.set_actor_location_and_rotation(pivot, rotation, False, False)
            actor.set_actor_scale3d(unreal.Vector(SCALE, SCALE, SCALE))
            actor.set_actor_label(label)
            actor.set_folder_path(LABEL)
            if part == "Shell":
                actor.get_component_by_class(unreal.StaticMeshComponent).set_collision_enabled(
                    unreal.CollisionEnabled.NO_COLLISION)
            else:
                log = actor
            placed.append(actor)
        # Measured, not assumed: the bounds' lowest point can be a branch or root rather than the trunk's underside, so
        # the computed placement floated 25-40 cm on the bank (#115 review). Trace the trunk's hull from below along its
        # bank half and lower both actors until its lowest contact sits SINK into the bank.
        bank = [g for g in (underside_gap(log, p.x + ux * d * 100, p.y + uy * d * 100) for d in BANK_SAMPLES) if g is not None]
        if not bank:
            raise RuntimeError(f"{name}: the log's hull is not over the bank; check its axis")
        drop = min(bank) + SINK
        for actor in placed[-2:]:  # the log and its shell
            actor.add_actor_world_offset(unreal.Vector(0, 0, -drop), False, False)
        gaps = [(d, underside_gap(log, p.x + ux * d * 100, p.y + uy * d * 100)) for d in GAP_SAMPLES]
        print(f"{name}: {host.get_name()} at ({p.x / 100:.1f}, {p.y / 100:.1f}) m, pitch {math.degrees(pitch):.1f} deg;"
              f" bank {inland / 100:.2f} m, bed {bed / 100:.2f} m, surface {surface / 100:.2f} m; lowered {drop:.0f} cm;"
              f" underside gap (m along the normal, + inland: cm) {gaps}")
        margin = KEEPOUT_CM / SCALE  # in the mesh's own units
        corners = [unreal.Vector(x, y, box.min.z) for x, y in ((box.min.x - margin, box.min.y - margin),
                                                               (box.max.x + margin, box.min.y - margin),
                                                               (box.max.x + margin, box.max.y + margin),
                                                               (box.min.x - margin, box.max.y + margin))]
        footprint = [log.get_actor_transform().transform_location(c) for c in corners]
        keepout_label = f"{LABEL}_{name}_Keepout"
        stale = old.pop(keepout_label, None)
        if stale is not None:
            old[keepout_label + "_stale"] = stale  # destroyed and saved with the other leftovers below
        keepout = place(keepout_label, [(c.x, c.y) for c in footprint], 1000.0, KEEPOUT_TAG)
        keepout.set_folder_path(LABEL)
        placed.append(keepout)
    packages = [a.get_package() for a in old.values()]
    for actor in old.values():
        actors.destroy_actor(actor)
    packages += [a.get_package() for a in placed]
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
        raise RuntimeError("could not save the shore logs")
    print(f"{len(placed) // 3} shore logs with keepouts; {len(old)} removed")


main()
