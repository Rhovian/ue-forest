# editor-py: fresh-siblings
"""Build the Forest Biome Meadow group: grass on a few short stretches of coast (#38).

    scripts/editor-py scripts/pcg/meadow.py

edge_in_04 and high_point_01: some stretches of coast open into a grassy meadow fringe before the forest, with fallen
logs lying in it; they are exceptions, a few short stretches, not the whole coast. MEADOWS lists them (append a line to add one): grass grows on
the low ground (from the shore height up to TOP) within each stretch's radius. A sparse generator places anchor clumps;
each carries a patch of PATCH clumps as children, projected onto the ground. Sampling the dense grass directly would
cost density x the whole biome volume (deadwood_rocks.candidate_estimate): 120,000/ha drove the editor past 40 GB. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib
import math

import biome_variants
import unreal
from deadwood_rocks import (
    ROOT,
    asset_list,
    children,
    copy_asset,
    edge,
    entry,
    generator,
    get,
    load,
    load_forest_actors,
    put,
    save,
)
from trees_above_shore import shore_height, z_range

# (x m, y m, radius m) per meadow stretch: the coastal meadow at the clearing view, and grassland on the north-west lobe.
MEADOWS = [(190, -690, 70), (-815, 734, 70)]
TOP = 300  # cm above the sea: low coastal ground, below the forest understory (plants start at 2.25 m)
ANCHORS_PER_HA = 2000  # anchor clumps; cheap island-wide, only the meadow ground keeps them
PATCH = 40  # child clumps per anchor, spread over PATCH_RADIUS
PATCH_RADIUS = 300  # cm
LOGS_PER_HA = 60  # ~10% survive the slope mask and meadow filter (measured: 200/ha -> 38 logs on 2 ha); ~11 logs


def meadow_graph():
    """Low ground (shore height up to TOP) within a MEADOWS radius."""
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_MeadowGround")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    low = z_range(graph, shore_height(), TOP)
    edge(graph, inp, "In", low, "In")
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)
    # One native Distance + Density Filter per stretch (shore_trees.py's pattern), so each keeps its own radius.
    for x, y, radius in MEADOWS:
        mark, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
        point = unreal.PCGPoint()
        point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x * 100, y * 100, 0)))
        settings.set_editor_property("points_to_create", [point])
        settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
        settings.set_editor_property("cull_points_outside_volume", False)
        distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
        settings.set_editor_property("set_density", True)
        settings.set_editor_property("maximum_distance", radius * 100)
        settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
        settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
        edge(graph, low, "InsideFilter", distance, "Source")
        edge(graph, mark, "Out", distance, "Target")
        near, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
        settings.set_editor_property("lower_bound", 0)
        settings.set_editor_property("upper_bound", 0.99)  # drop the saturated beyond-radius distance
        edge(graph, distance, "Out", near, "In")
        edge(graph, near, "Out", merge, "In")
    edge(graph, merge, "Out", out, "Out")
    save(graph)
    return graph


def main():
    variants = importlib.reload(biome_variants)
    grass = [(load(path), weight) for path, weight in variants.GRASS_VARIANTS]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    graph = meadow_graph()
    # Priority 60 so trees win Core's priority difference; overlap allowed so grass also grows around them.
    # Spatial noise off: a meadow is grass throughout (the noise thinned it to sparse tufts).
    group = generator("Meadow", ANCHORS_PER_HA, 25, 60, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    value = group.get_editor_property("Generator")
    put(value, GeneratorAllowOverlap=True)
    group.set_editor_property("Generator", value)
    save(group)
    # Logs: the forest's fallen-log variants (mossy, blocking), their own sparse generator on the same meadow ground.
    log_group = generator("MeadowLogs", LOGS_PER_HA, 15, 55, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    entries = []
    for path, weight in variants.LOG_VARIANTS:
        mesh = load(variants.VENDOR + path)
        value = entry(template, mesh, log_group, graph, weight, aligned=True)
        put(value, AssetType="MeadowLog_" + mesh.get_name())  # distinct from the forest deadwood's types
        entries.append(value)
    # A disc of PATCH points (sunflower spiral: even spacing, no grid lines) around each anchor, on the ground.
    disc = [(PATCH_RADIUS * math.sqrt((i + 0.5) / PATCH) * math.cos(i * 2.39996),
             PATCH_RADIUS * math.sqrt((i + 0.5) / PATCH) * math.sin(i * 2.39996), 0) for i in range(PATCH)]
    patch = children("DA_MeadowPatch", template, [("PCG_MeadowPatch", disc, (0.8, 1.2), grass, True)])
    for mesh, weight in grass:
        value = entry(template, mesh, group, graph, weight, children=patch, collision=False)
        options = get(value, "AssetOptions")
        put(options, OrientUpward=1.0)
        put(value, AssetOptions=options)
        entries.append(value)
    assets = asset_list("DA_Forest_MeadowAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Meadow: {len(grass)} grass variants, anchors at {ANCHORS_PER_HA}/ha x {PATCH} clumps, logs at {LOGS_PER_HA}/ha on"
          f" {len(MEADOWS)} stretches")


if __name__ == "__main__":
    main()
