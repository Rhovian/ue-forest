"""Leaves floating on the lake (#159): drifts of fallen leaves resting on the water near its shore.

    scripts/editor-py scripts/pcg/lake_leaves.py

Landscape Grass grows on the lake bed, so the leaves are instances on an actor of their own (LABEL), one instanced
component per mesh, at the lake's surface height; each run replaces it. The drifts are clumps of a hashed value noise,
thinning away from the shore. The shore is the lake's own water spline, where its water is drawn: the bank beside it
lies below the lake's level in places with no water over it, and the exclusion outline put leaves there.
"""
import importlib
import math
import random
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
import biome_variants
from groundcover_mask import landscape_z
from water_bed_mask import signed_distance

importlib.reload(biome_variants)  # the editor keeps imported modules between runs

LABEL = "LakeLeaves"
LAKE = "Lake"
SPACING = 25.0  # cm between candidate leaves
SHORE_CM = 30.0  # inside the lake's water spline: from just off its edge
REACH_CM = (0.0, 1000.0)  # out as far as a slower noise says, from bare shore to wide drifts, so the edge is not one band
REACH_NOISE_CM = 1300.0  # feature size of the stretches of shore with and without leaves
DRIFT_CM = 350.0  # feature size of the drifts
DRIFT = (0.45, 0.6)  # noise from no leaves to a full drift
JITTER = 0.8  # share of SPACING a leaf moves off its grid point
SCALE = (3.0, 4.5)  # single 4-9 cm leaves to 12-40 cm, readable on the water from the shore
MAT_SCALE = (0.6, 0.9)  # a leaf mat (a mesh over MAT_CM across) is already 0.8 m
MAT_CM = 50.0
MIN_DEPTH = 5.0  # cm of water over the bed for a leaf to float
SEED = 159


def value_noise(x, y, size, seed=SEED):
    """Smooth 0..1 noise with features about size cm across, the same on every run."""
    gx, gy = x / size, y / size
    ix, iy = math.floor(gx), math.floor(gy)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def corner(i, j):
        return random.Random(hash((i, j, seed)) & 0xFFFFFFFF).random()
    top = corner(ix, iy) + (corner(ix + 1, iy) - corner(ix, iy)) * fx
    bottom = corner(ix, iy + 1) + (corner(ix + 1, iy + 1) - corner(ix, iy + 1)) * fx
    return top + (bottom - top) * fy


def smoothstep(low, high, value):
    t = max(0.0, min(1.0, (value - low) / (high - low)))
    return t * t * (3 - 2 * t)


def water(world_actors):
    """The lake's water edge [(x, y)] in cm, following the curve between its spline points, and its surface z."""
    lake = next(a for a in world_actors if isinstance(a, unreal.WaterBodyLake) and a.get_actor_label() == LAKE)
    spline = lake.get_component_by_class(unreal.WaterSplineComponent)
    space = unreal.SplineCoordinateSpace.WORLD
    count, length = spline.get_number_of_spline_points() * 8, spline.get_spline_length()
    edge = [spline.get_location_at_distance_along_spline(length * k / count, space) for k in range(count)]
    return [(p.x, p.y) for p in edge], max(p.z for p in edge)


def leaves(points, surface):
    """[(mesh path, Transform)] for the drifts."""
    world = unreal.UnrealEditorSubsystem().get_editor_world()
    rng = random.Random(SEED)
    paths, weights = zip(*biome_variants.LAKE_LEAF_VARIANTS)
    mats = set()
    for path in paths:
        box = unreal.load_asset(path).get_bounding_box()
        if box.max.x - box.min.x > MAT_CM:
            mats.add(path)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    out = []
    y = min(ys)
    while y <= max(ys):
        x = min(xs)
        while x <= max(xs):
            px, py = x + rng.uniform(-JITTER, JITTER) * SPACING / 2, y + rng.uniform(-JITTER, JITTER) * SPACING / 2
            keep, rotation, scale = rng.random(), rng.uniform(0, 360), rng.uniform(*SCALE)
            drift = smoothstep(*DRIFT, value_noise(px, py, DRIFT_CM))
            reach = REACH_CM[0] + (REACH_CM[1] - REACH_CM[0]) * smoothstep(0.3, 0.7, value_noise(px, py, REACH_NOISE_CM, SEED + 1))
            # The noise first: the distance to the outline is the costly test, and most of the lake is not a drift.
            inside = signed_distance(points, px, py) if keep < drift and reach > SHORE_CM else -1
            if SHORE_CM <= inside <= reach and keep < drift * (1 - smoothstep(SHORE_CM, reach, inside)):
                ground = landscape_z(world, px, py)
                if ground is not None and ground < surface - MIN_DEPTH:
                    path = rng.choices(paths, weights)[0]
                    scale = scale / SCALE[0] * MAT_SCALE[0] if path in mats else scale
                    out.append((path, unreal.Transform(unreal.Vector(px, py, surface + 4.0), unreal.Rotator(0, 0, rotation),
                                                       unreal.Vector(scale, scale, scale))))
            x += SPACING
        y += SPACING
    return out


def main():
    actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = actors_sub.get_all_level_actors()
    for actor in all_actors:
        if actor.get_actor_label() == LABEL:
            actors_sub.destroy_actor(actor)
    placed = leaves(*water(all_actors))

    actor = actors_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(LABEL)
    subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = subobjects.k2_gather_subobject_data_for_instance(actor)[0]
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    by_mesh = {}
    for path, transform in placed:
        by_mesh.setdefault(path, []).append(transform)
    for path, transforms in sorted(by_mesh.items()):
        handle, failure = subobjects.add_new_subobject(unreal.AddNewSubobjectParams(
            parent_handle=root, new_class=unreal.InstancedStaticMeshComponent))
        if not failure.is_empty():
            raise SystemExit(f"could not add a component for {path}: {failure}")
        component = library.get_object(library.get_data(handle))
        component.set_static_mesh(unreal.load_asset(path))
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_editor_property("cast_shadow", False)
        component.add_instances(transforms, False, True)
    print(f"{LABEL}: {len(placed)} leaves in {len(by_mesh)} components")


if __name__ == "__main__":
    main()
