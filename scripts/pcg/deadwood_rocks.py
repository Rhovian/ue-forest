# editor-py: fresh-siblings
"""Build reusable Forest Biome Deadwood/Rocks groups with stock materials.

    scripts/editor-py scripts/pcg/deadwood_rocks.py [--check]

Build saves assets, attaches groups to actors using DA_Forest_TreesAssets, but does not
save the level or regenerate Core. --check validates prerequisites without mutation.
Densities are candidates/ha before slope, noise, shore and Core exclusions/pruning.
"""

import argparse
import importlib
import math
import re

import biome_variants
import unreal
from child_layouts import along_sides, along_top, base_ring, build_points_graph, surface_hits
from long_log_keepout import water_keepout
from trees_above_shore import shore_height, z_range

ROOT = "/Game/ForestBiome/"
VARIANTS = importlib.reload(biome_variants)  # pick up one-line palette edits in the running editor


def load(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset missing: {path}")
    return asset


def load_forest_actors():
    # UE 5.8.3 WorldPartitionBlueprintLibrary.cpp:LoadActors retains a native loader adapter
    # and synchronously refreshes it. All inputs (including exclusions) must precede PCG queries.
    descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if descriptors is None:
        raise RuntimeError("Load a World Partition forest level before running")
    unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in descriptors])
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


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


def filter_graph(name, reach=0, slope=0):
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", name)
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    band = z_range(graph, shore_height() + 150 + reach * math.sin(math.radians(slope)), 1.0e7)
    edge(graph, inp, "In", band, "In")
    last, pin = water_keepout(graph, band, "InsideFilter", reach, edge) if reach else (band, "InsideFilter")
    edge(graph, last, pin, out, "Out")
    save(graph)
    return graph


LOGS_PER_HA = 20  # #32 ruling: more deadwood on the floor (was 12 logs + 6 stumps)
STUMPS_PER_HA = 8


# The surface sampler covers the whole biome volume before any filter, so a generator's cost is density x volume area,
# not density x the ground it ends up on. 600,000/ha for a 2 ha meadow asked for ~180 million candidates and drove the
# editor into memory pressure; 120,000/ha (~56 million) is the largest that has run in reasonable time.
MAX_CANDIDATES = 60e6


def candidate_estimate(density, extent):
    """Candidate points the sampler draws over the island's bounds (forest_foot.json) for this density and extent."""
    import json
    from pathlib import Path

    x0, x1, y0, y1 = json.loads(Path(biome_variants.__file__).with_name("forest_foot.json").read_text())["island_m"]
    cell_cap = 10000 / (2 * extent / 100) ** 2  # one point per (2 x extent)^2 cell, per hectare
    return min(density, cell_cap) * (x1 - x0) * (y1 - y0) / 10000


def generator(group, density, slope, priority, doubles=None, bools=None, extent=100):
    if doubles and "PointsPerSquareMeter" in doubles:
        raise RuntimeError(f"{group}: pass the density as the `density` argument, not a PointsPerSquareMeter override,"
                           " so the candidate budget checks what is installed")
    estimate = candidate_estimate(density, extent)
    if estimate > MAX_CANDIDATES:
        raise RuntimeError(f"{group}: {density:.0f}/ha at extent {extent} cm samples ~{estimate / 1e6:.0f} million points over"
                           f" the biome volume (budget {MAX_CANDIDATES / 1e6:.0f} million); lower the density or narrow"
                           " the area")
    graph = copy_asset(ROOT + "PCG_Forest_TreesGenerator", f"PCG_Forest_{group}Generator")
    # Native parameter helpers already validate names/types and notify graph instances:
    # UE 5.8 PCG/Private/Helpers/PCGGraphParametersHelpers.cpp: ValidateAndSetValue.
    helpers = unreal.PCGGraphParametersHelpers
    for name, value in ({
        "PointsPerSquareMeter": density / 10000, "SlopeMaskLow": math.cos(math.radians(slope)),
        "SlopeMaskHigh": math.cos(math.radians(5)) if group == "Rocks" else 1.0, "SpatialDensityLow": 0.35, "SpatialDensityHigh": 1.0,
        "ScaleByDensityRangeMin": 1.0, "ScaleByDensityRangeMax": 1.0, "ScramblePositionDistance": 0.0,
    } | (doubles or {})).items():
        helpers.set_double_parameter(graph, name, value)
    for name, value in ({
        "EnableSlopeMasking": True, "EnableWorldRayHitQuery": False, "EnableSpatialNoise": True,
        "EnableVoronoiNoiseBreakup": False, "EnableDistanceToEdge": False,
    } | (bools or {})).items():
        helpers.set_bool_parameter(graph, name, value)
    for name, value in {"ScaleMin": unreal.Vector(0.8, 0.8, 0.8), "ScaleMax": unreal.Vector(1.2, 1.2, 1.2),
                        # The surface sampler emits at most one point per cell of twice these extents.
                        "PointExtents": unreal.Vector(extent, extent, 100)}.items():
        helpers.set_vector_parameter(graph, name, value)
    # Python uses MakeRotator(Roll, Pitch, Yaw), not the C++ constructor order (KismetMathLibrary.h).
    helpers.set_rotator_parameter(graph, "RotationMin", unreal.Rotator(pitch=0, yaw=0, roll=0))
    helpers.set_rotator_parameter(graph, "RotationMax", unreal.Rotator(pitch=0, yaw=360, roll=0))
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


def entry(template, mesh, group, transform, weight=1, children=None, collision=True, aligned=False):
    value = template.copy()
    skinned = isinstance(mesh, unreal.SkeletalMesh)
    put(value, AssetType=mesh.get_name(), Mesh=None if skinned else mesh,
        SkeletalMesh=mesh if skinned else None, Generator=group,
        TransformGraph=transform, Weight=weight, ChildAssets=children, MeshOptionsPreset=None)
    options = get(value, "MeshOptions")
    put(options, AllowCollision=collision, Material=None)
    put(value, MeshOptions=options)
    options = get(value, "AssetOptions")
    # Keep the full parent orientation until the fungi graph positions its anchor, then upright it.
    put(options, OrientUpward=0.0 if aligned else 1.0, OverlapWithChildren=True)
    put(value, AssetOptions=options)
    return value


SHELL_EXTENTS = 0.001  # a moss shell's child bounds: it sits on its host's own point and must prune no sibling


def shell_layout(mesh):
    """The moss shell layout for a host (moss_shells.py), or [] if it has none: one point at the host's own transform."""
    shell = unreal.load_asset(f"/Game/ForestBiome/MossShells/SM_{mesh.get_name()}_MossShell")
    return [("PCG_Shell_" + mesh.get_name(), [(0, 0, 0)], (1, 1), [(shell, 1)], False, False)] if shell else []


def children(name, template, layouts):
    """One ChildAssets list from (graph name, points, scale, palette, on the ground[, upright]) layouts.

    Entries sharing a layout's graph are weighted alternatives at each of its points. Core's
    BiomeCore_ChildTransformLoop walks the list entry by entry and drops points whose bounds overlap points an earlier
    entry placed, so child bounds shrink to 5%: otherwise layouts prune each other (#32 part 2: seedlings after fungi
    on the same top line kept about 1%)."""
    entries = []
    for graph_name, points, scale, rows, ground, *rest in layouts:
        upright = rest[0] if rest else True
        graph = copy_asset(ROOT + "PCG_TreesAboveShore", graph_name)
        build_points_graph(graph, points, edge, scale, ground, upright)
        save(graph)
        extents = 0.05 if upright else SHELL_EXTENTS
        for child, w in rows:
            value = entry(template, child, None, graph, w, collision=False, aligned=True)
            options = get(value, "AssetOptions")
            put(options, ExtentsMultiplier=unreal.Vector(extents, extents, extents))
            put(value, AssetOptions=options)
            entries.append(value)
    return asset_list(name, entries)


def shell_children(template, mesh):
    """A ChildAssets list holding only the host's moss shell, or None if it has none."""
    layout = shell_layout(mesh)
    return children("DA_ShellChildren_" + mesh.get_name(), template, layout) if layout else None


def asset_list(name, entries):
    data = copy_asset(ROOT + "DA_Forest_TreesAssets", name)
    data.set_editor_property("BiomeAssets", entries)
    save(data)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    palettes = [VARIANTS.LOG_VARIANTS, VARIANTS.STUMP_VARIANTS, VARIANTS.SLAB_VARIANTS, VARIANTS.FUNGI_VARIANTS]
    plants = [VARIANTS.SEEDLING_VARIANTS, VARIANTS.BASE_PLANT_VARIANTS]  # full /Game paths, shared with the plant groups
    if any(not rows or any(weight <= 0 for _, weight in rows) for rows in palettes + plants):
        raise RuntimeError("Variant lists must be nonempty with positive weights")
    paths = [path for rows in palettes for path, _ in rows]
    if len(paths) != len(set(paths)) or any(len({p for p, _ in rows}) != len(rows) for rows in plants):
        raise RuntimeError("A mesh may appear only once across the variant lists")
    logs, stumps, slabs, fungi = [[(load(VARIANTS.VENDOR + path), weight) for path, weight in rows] for rows in palettes]
    seedlings, base_plants = [[(load(path), weight) for path, weight in rows] for rows in plants]
    # Fungi alternatives share one layout, so they need one stem-base height to bury by.
    bases = [mesh.get_bounds().origin.z - mesh.get_bounds().box_extent.z for mesh, _ in fungi]
    if max(bases) - min(bases) > 0.1:
        raise RuntimeError("Fungi variants need matching stem-base pivots (within 1 mm)")
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
            actor.get_actor_label() == "ForestExclusion_" + water.get_actor_label()
            and actor.actor_has_tag("PCG_BiomeExclusion") for actor in actors
        ):
            raise RuntimeError("Missing water exclusion; run scripts/pcg/water_exclusions.py first")
    for name in ("Mesh", "SkeletalMesh", "Generator", "TransformGraph", "ChildAssets", "MeshOptions"):
        field(template, name)
    if args.check:
        print(f"Deadwood/Rocks preflight OK: {sum(map(len, palettes))} variants, {len(biomes)} forest biome volume(s); no changes")
        return
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for mesh, _ in logs + stumps + slabs:
        name = mesh.get_name()
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
    deadwood = generator("Deadwood", STUMPS_PER_HA, 20, 10)
    entries = [entry(template, mesh, deadwood, plain, weight, shell_children(template, mesh)) for mesh, weight in stumps]
    densities = set()
    for index, (mesh, weight) in enumerate(logs):
        name, box = mesh.get_name(), mesh.get_bounding_box()
        # Enclose every scaled source corner relative to its pivot, irrespective of random yaw.
        reach = 1.2 * math.sqrt(sum(max(abs(getattr(box.min, axis)), abs(getattr(box.max, axis)))**2 for axis in "xyz"))
        long = max(getattr(box.max, a) - getattr(box.min, a) for a in "xyz") > 1000
        # Smooth hillsides can support a tilted trunk; lead checks nine terrain samples along it.
        slope = 8 if long else 20
        # Equal-weight variants with one seed share every point (#32 part 2: each Large_Fallen_Tree wd1mbcvbw lay
        # on a wgrubc1s). Neither BasicNoiseSeed, a shifted noise field nor a new cell size separated them; a
        # different density does, so nudge each variant's by 5%.
        density = LOGS_PER_HA * weight / sum(w for _, w in logs) * (1 + 0.05 * index)
        if density in densities:
            raise RuntimeError(f"Log variant {name} has the same generator density as another; adjust a weight")
        densities.add(density)
        group = generator("Deadwood_" + name, density, slope, 10)
        # Altitude alone is no dampness proxy; both forms need the same eligible ground.
        nurse = filter_graph("PCG_Nurse_" + name, reach=reach if long else 0, slope=slope)
        # nurse_log_01: about one seedling per 4 m of trunk (4 on the 17 m log), two mushroom clusters on the top of
        # a large log and one on the short piece, between the seedlings, and ferns and anemone every 90 cm along both
        # sides of the trunk and at its ends.
        hits = surface_hits(mesh)
        length = max(getattr(box.max, a) - getattr(box.min, a) for a in "xy")
        seedling_tops = along_top(hits, max(1, min(5, round(length / 400))))
        fungi_tops = [(x, y, z - min(bases) - 0.25)  # bury the stem base 2.5 mm, not the cap
                      for x, y, z in along_top(hits, 3)[::2][:2 if length > 400 else 1]]
        sides = along_sides(hits, 90, 15)
        # The moss shell comes first: Core prunes later entries against earlier ones, and its bounds are tiny.
        nurse_children = children("DA_NurseChildren_" + name, template, shell_layout(mesh) + [
            ("PCG_Fungi_" + name, fungi_tops, (0.9, 1.3), fungi, False),
            ("PCG_Seedlings_" + name, seedling_tops, (1.0, 1.5), seedlings, False),
            ("PCG_LogBase_" + name, sides, (0.7, 1.1), base_plants, True)])
        # Logs over 4 m (the Large Fallen Trees) are all nurse logs; the short piece keeps plain:nurse 2:1.
        # Only the short piece has plain logs; long ones get no plain filter graph (no unused assets).
        plain_logs = [] if length > 400 else [
            entry(template, mesh, group, filter_graph("PCG_Log_" + name, reach=reach if long else 0, slope=slope), 2,
                  shell_children(template, mesh), aligned=True)]
        entries += plain_logs + [
            entry(template, mesh, group, nurse, 1, nurse_children, aligned=True)]
        print(f"Log variant {name}: share {weight / sum(w for _, w in logs):.1%}, slope {slope} deg, reach {reach:.0f} cm,"
              f" {len(seedling_tops)} seedling / {len(fungi_tops)} fungi / {len(sides)} base points")
    rocks = generator("Rocks", 30, 35, 20)
    rock_entries = []
    for mesh, weight in slabs:
        # rock_assembly_01: ferns and flowers packed round the base with no bare ring.
        layouts = shell_layout(mesh) + [("PCG_RockBase_" + mesh.get_name(), base_ring(surface_hits(mesh), 45, 5),
                                         (0.7, 1.1), base_plants, True)]
        rock_entries.append(entry(template, mesh, rocks, plain, weight,
                                  children("DA_RockChildren_" + mesh.get_name(), template, layouts)))
    groups = [asset_list("DA_Forest_DeadwoodAssets", entries), asset_list("DA_Forest_RocksAssets", rock_entries)]
    for actor in biomes:
        assets = list(actor.get_editor_property("Assets"))
        actor.set_editor_property("Assets", assets + [group for group in groups if group not in assets])
    print(f"Deadwood/Rocks built: {LOGS_PER_HA} logs + {STUMPS_PER_HA} stumps/ha, 30 slabs/ha candidates; {len(logs)} log variants")
    print("Collision: Log/Stump/Slab simple BlockAll; stock materials; assets saved")
    print("Ground groups: priority difference bypassed (canopy bounds); terrain/water filters retained")
    print("Children: nurse logs carry fungi, seedlings and base plants; rocks carry base plants")
    print("Regenerate Biome Core, inspect nurse fungi/contact/collision, then save the level")


if __name__ == "__main__":
    main()
