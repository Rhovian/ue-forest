"""Build reusable Forest Biome Deadwood/Rocks groups with stock materials.

    scripts/editor-py scripts/pcg/deadwood_rocks.py [--check]

Build saves assets, attaches groups to actors using DA_Forest_TreesAssets, but does not
save the level or regenerate Core. --check validates prerequisites without mutation.
Densities are candidates/ha before slope, noise, shore and Core exclusions/pruning.
"""

import argparse
import math
import re

import unreal
from trees_above_shore import shore_height, z_range

ROOT = "/Game/ForestBiome/"
VENDOR = "/Game/Fab/Megascans/3D/"
MESHES = {
    "Log": "Nordic_Forest_Tree_Fallen_Medium_xicmfco/Medium/xicmfco_tier_2/StaticMeshes/xicmfco_tier_2",
    "Stump": "Old_Tree_Stump_wd0qcaobw/Medium/wd0qcaobw_tier_2/StaticMeshes/wd0qcaobw_tier_2",
    "Slab": "Limestone_Slab_ubxbadpda/Medium/ubxbadpda_tier_2/StaticMeshes/ubxbadpda_tier_2",
    "Fungi": "Bolete_Mushrooms_pdvcB/Medium/pdvcB_tier_2/StaticMeshes/pdvcB_LOD0_TIER2_000",
}


def load(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset missing: {path}")
    return asset


def field(struct, name):
    # UE 5.8 user-defined struct fields have GUID suffixes; Python exposes no field iterator.
    # PyWrapperStruct.cpp: ExportToText delegates to UScriptStruct::ExportText; use that
    # only to discover the field key, leaving all value serialization/copying to UE.
    keys = set(re.findall(rf"\b({name}_\d+_[0-9A-F]+)=", struct.export_text()))
    if len(keys) != 1:
        raise RuntimeError(f"Expected one {name} field, got {keys}")
    return keys.pop()


def put(struct, **values):
    for name, value in values.items():
        struct.set_editor_property(field(struct, name), value)
    return struct


def get(struct, name):
    return struct.get_editor_property(field(struct, name))


def copy_asset(source, name):
    path = ROOT + name
    return unreal.load_asset(path) or unreal.EditorAssetLibrary.duplicate_asset(source, path) or load(path)


def save(asset):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"Save failed: {asset.get_path_name()}")


def edge(graph, source, source_pin, target, target_pin):
    # UE 5.8 PCGGraph.cpp AddEdge always returns To, including on failure.
    before = sum(len(p.get_editor_property("edges")) for p in target.get_editor_property("input_pins"))
    graph.add_edge(source, source_pin, target, target_pin)
    after = sum(len(p.get_editor_property("edges")) for p in target.get_editor_property("input_pins"))
    if after != before + 1:
        raise RuntimeError(f"PCG connection failed: {source_pin} -> {target_pin}")


def filter_graph(name, top=1.0e7, offset=None):
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", name)
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    last, pin = inp, "In"
    if offset is None:
        last = z_range(graph, shore_height() + 150, top)
        edge(graph, inp, "In", last, "In")
        pin = "InsideFilter"
    if offset is not None:
        source = last
        last, settings = graph.add_node_of_type(unreal.PCGTransformPointsSettings)
        settings.set_editor_property("offset_min", offset)
        settings.set_editor_property("offset_max", offset)
        edge(graph, source, pin, last, "In")
        pin = "Out"
    edge(graph, last, pin, out, "Out")
    save(graph)
    return graph


def generator(group, density, slope, priority):
    graph = copy_asset(ROOT + "PCG_Forest_TreesGenerator", f"PCG_Forest_{group}Generator")
    # Native parameter helpers already validate names/types and notify graph instances:
    # UE 5.8 PCG/Private/Helpers/PCGGraphParametersHelpers.cpp: ValidateAndSetValue.
    helpers = unreal.PCGGraphParametersHelpers
    for name, value in {
        "PointsPerSquareMeter": density / 10000, "SlopeMaskLow": math.cos(math.radians(slope)),
        "SlopeMaskHigh": math.cos(math.radians(5)) if group == "Rocks" else 1.0, "SpatialDensityLow": 0.35, "SpatialDensityHigh": 1.0,
        "ScaleByDensityRangeMin": 1.0, "ScaleByDensityRangeMax": 1.0,
    }.items():
        helpers.set_double_parameter(graph, name, value)
    for name, value in {
        "EnableSlopeMasking": True, "EnableWorldRayHitQuery": False, "EnableSpatialNoise": True,
        "EnableVoronoiNoiseBreakup": False, "EnableDistanceToEdge": False,
    }.items():
        helpers.set_bool_parameter(graph, name, value)
    for name, value in {"ScaleMin": unreal.Vector(0.8, 0.8, 0.8), "ScaleMax": unreal.Vector(1.2, 1.2, 1.2),
                        "PointExtents": unreal.Vector(100, 100, 100)}.items():
        helpers.set_vector_parameter(graph, name, value)
    helpers.set_rotator_parameter(graph, "RotationMin", unreal.Rotator(0, 0, 0))
    helpers.set_rotator_parameter(graph, "RotationMax", unreal.Rotator(0, 360, 0))
    data = copy_asset(ROOT + "DA_Forest_TreesGenerator", f"DA_Forest_{group}Generator")
    value = data.get_editor_property("Generator")
    # Core priority difference uses full mesh bounds, so canopy bounds erase ground obstacles.
    # Lead's same-world probe: bypass recovered 34 -> 371 deadwood and 28 -> 408 slabs.
    # Keep terrain/water filters; allow cross-generator overlap rather than carving canopy gaps.
    put(value, GeneratorType=group, GeneratorGraph=graph, GeneratorPriority=priority, GeneratorAllowOverlap=True)
    data.set_editor_property("Generator", value)
    save(graph)
    save(data)
    return data


def entry(template, mesh, group, transform, weight=1, children=None, collision=True):
    value = template.copy()
    put(value, AssetType=mesh.get_name(), Mesh=mesh, SkeletalMesh=None, Generator=group,
        TransformGraph=transform, Weight=weight, ChildAssets=children, MeshOptionsPreset=None)
    options = get(value, "MeshOptions")
    put(options, AllowCollision=collision, Material=None)
    put(value, MeshOptions=options)
    options = get(value, "AssetOptions")
    put(options, OrientUpward=0.0, OverlapWithChildren=True)
    put(value, AssetOptions=options)
    return value


def asset_list(name, entries):
    data = copy_asset(ROOT + "DA_Forest_TreesAssets", name)
    data.set_editor_property("BiomeAssets", entries)
    save(data)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    meshes = {name: load(VENDOR + path) for name, path in MESHES.items()}
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    load(ROOT + "PCG_TreesAboveShore")
    load(ROOT + "DA_Forest_TreesGenerator")
    load(ROOT + "PCG_Forest_TreesGenerator")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    # Find biome membership by its reusable assets, never by a map/actor label or position.
    biomes = [actor for actor in actors if actor.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in actor.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running; no tree assets actor found")
    for water in actors:
        if isinstance(water, (unreal.WaterBodyLake, unreal.WaterBodyRiver)) and not any(
            actor.get_actor_label() == "ForestExclusion_" + water.get_actor_label() for actor in actors
        ):
            raise RuntimeError("Missing water exclusion; run scripts/pcg/water_exclusions.py first")
    for name in ("Mesh", "SkeletalMesh", "Generator", "TransformGraph", "ChildAssets", "MeshOptions"):
        field(template, name)
    if args.check:
        print(f"Deadwood/Rocks preflight OK: 4 meshes, {len(biomes)} forest biome volume(s); no changes")
        return
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for name in ("Log", "Stump", "Slab"):
        mesh = meshes[name]
        # Engine's convex decomposition replaces existing hulls; no custom collision generator.
        # UE 5.8 StaticMeshEditorSubsystem.h: SetConvexDecompositionCollisions.
        if not subsystem.set_convex_decomposition_collisions(mesh, 4, 16, 100000):
            raise RuntimeError(f"Convex collision failed: {name}")
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
        default = body.get_editor_property("default_instance")
        default.set_editor_property("collision_profile_name", "BlockAll")
        body.set_editor_property("default_instance", default)
        # UE 5.8 StaticMeshEditorSubsystem.cpp: GetSimpleCollisionCount excludes ConvexElems.
        count = subsystem.get_convex_collision_count(mesh)
        if not 1 <= count <= 4:
            raise RuntimeError(f"Expected 1..4 convex collision hulls: {name}, got {count}")
        save(mesh)
    plain = filter_graph("PCG_DeadwoodAboveShore")
    nurse = filter_graph("PCG_NurseLogLowGround", top=1200)
    # A rooted child point in log-local space inherits the parent's yaw and scale.
    # Put fungi on the scan's upper surface; inspect on the actual mesh before acceptance.
    bounds = meshes["Log"].get_bounds()
    fungi = filter_graph("PCG_NurseLogFungi", offset=unreal.Vector(
        bounds.origin.x, bounds.origin.y, bounds.origin.z + bounds.box_extent.z - 3))
    children = asset_list("DA_Forest_NurseLogChildren", [
        entry(template, meshes["Fungi"], None, fungi, collision=False)])
    deadwood = generator("Deadwood", 18, 20, 10)
    rocks = generator("Rocks", 30, 35, 20)
    groups = [asset_list("DA_Forest_DeadwoodAssets", [
        entry(template, meshes["Log"], deadwood, plain, 8),
        entry(template, meshes["Log"], deadwood, nurse, 4, children),
        entry(template, meshes["Stump"], deadwood, plain, 6)]),
        asset_list("DA_Forest_RocksAssets", [entry(template, meshes["Slab"], rocks, plain)])]
    for actor in biomes:
        assets = list(actor.get_editor_property("Assets"))
        actor.set_editor_property("Assets", assets + [group for group in groups if group not in assets])
    print("Deadwood/Rocks built: 18/ha (8 plain logs, 4 nurse logs, 6 stumps), 30 slabs/ha candidates")
    print("Collision: Log/Stump/Slab simple BlockAll; stock materials; assets saved")
    print("Ground groups: priority difference bypassed (canopy bounds); terrain/water filters retained")
    print("Regenerate Biome Core, inspect nurse fungi/contact/collision, then save the level")


main()
