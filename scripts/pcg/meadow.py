# editor-py: fresh-siblings
"""Build the Forest Biome Meadow group: grass on a few short stretches of coast (#38).

    scripts/editor-py scripts/pcg/meadow.py

edge_in_04 and high_point_01: some stretches of coast open into a grassy meadow fringe before the forest; they are
exceptions, a few short stretches, not the whole coast. MEADOWS lists them (append a line to add one): grass grows on
the low ground (from the shore height up to TOP) within each stretch's radius, evenly (no spatial-noise clumping). Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib

import biome_variants
import unreal
from deadwood_rocks import (
    ROOT,
    asset_list,
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
GRASS_PER_HA = 120000  # ~19% survive the template (measured), ~23,000 clumps on ~2 ha


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
    group = generator("Meadow", GRASS_PER_HA, 25, 60, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False}, 12)
    value = group.get_editor_property("Generator")
    put(value, GeneratorAllowOverlap=True)
    group.set_editor_property("Generator", value)
    save(group)
    entries = []
    for mesh, weight in grass:
        value = entry(template, mesh, group, graph, weight, collision=False)
        options = get(value, "AssetOptions")
        put(options, OrientUpward=1.0)
        put(value, AssetOptions=options)
        entries.append(value)
    assets = asset_list("DA_Forest_MeadowAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Meadow: {len(grass)} grass variants at {GRASS_PER_HA}/ha on {len(MEADOWS)} stretches")


if __name__ == "__main__":
    main()
