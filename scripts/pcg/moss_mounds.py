# editor-py: fresh-siblings
"""Build the Forest Biome MossMounds group: low moss cushions over the interior floor (#71, interior_01).

    scripts/editor-py scripts/pcg/moss_mounds.py
    scripts/editor-py scripts/materials/moss_coating.py   # then coat the mound materials this script copies

interior_01 has overlapping soft moss cushions over the ground; ours was one smooth sheet with plants on it
(docs/research/forest-floor-terrain.md: missing intermediate-scale relief, trial 1). MOUND_VARIANTS are mossy
boulders, flattened, mostly sunk and fully moss-coated (copies of their materials, MOUND in moss_coating.py), in
irregular colonies: sparse anchors carry a drift of mounds each, as ground-projected children, so the cushions cost no
dense whole-volume sampling. A bounded trial first (the research's trial 1, #97 review): mounds grow only on SITES,
the fixed interior view's foreground and the nurse log, to judge scale and contact before any wider rollout. Anchors
are flattened and sunk like their drifts. Saves assets and attaches the group; the lead regenerates Core and saves the
level.
"""

import importlib

import biome_variants
import unreal
from canopy_gaps import ground_range
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
from saplings_understory import SHAPES, column, drift_points
from trees_above_shore import shore_height, z_range

FOLDER = "/Game/ForestBiome/Moss"
# (x m, y m, radius m) trial sites: interior's near 3-13 m (pose 486, -512 looking +x), nurse_log's log (4.5 m along
# its pose's 144 deg yaw). Island-wide colonies at 600/ha read as scattered mossy rocks with the foreground still smooth.
SITES = [(494, -512, 8), (457.8, -472.6, 6)]
ANCHORS_PER_HA = 800  # colony anchors, no noise: inside the sites the colonies overlap into one hummocky floor
DRIFT = (10, 560, 420)  # mounds per colony, length and width cm
SCALE = (0.5, 0.9)  # across
FLATTEN = (0.25, 0.35)  # height, on top of SCALE: 1.3-2.4 m boulders become 0.2-0.5 m tall
SINK = 8  # cm into the floor; at 25 cm the small flattened mounds (from 7 cm tall) vanished, leaving one cushion per colony


def mound_material(mesh):
    """MI_<mesh id>_Mound in FOLDER: a copy of the boulder's material, which moss_coating.py coats all over."""
    source = mesh.get_editor_property("static_materials")[0].get_editor_property("material_interface")
    name = "MI_" + mesh.get_name().split("_")[0] + "_Mound"
    path = f"{FOLDER}/{name}"
    return unreal.load_asset(path) or unreal.EditorAssetLibrary.duplicate_asset(source.get_path_name().split(".")[0], path)


def anchor_graph():
    """Forest floor (as the plants' filter) inside a trial site, each anchor flattened and sunk like its drift."""
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_MoundAnchors")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    band = z_range(graph, shore_height() + 150, 1.0e7)
    edge(graph, inp, "In", band, "In")
    merge, _ = graph.add_node_of_type(unreal.PCGMergeSettings)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    for x, y, radius in SITES:  # one native Distance + Density Filter per site (meadow.py's pattern)
        # Distance is 3D: a vertical column of targets over the site's traced ground range keeps it horizontal
        # (canopy_filter); one target at z 0 left the 21 m high interior floor outside every radius.
        mark, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
        points = []
        for z in column(*ground_range(world, x, y, radius)):
            point = unreal.PCGPoint()
            point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x * 100, y * 100, z)))
            points.append(point)
        settings.set_editor_property("points_to_create", points)
        settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
        settings.set_editor_property("cull_points_outside_volume", False)
        distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
        settings.set_editor_property("set_density", True)
        settings.set_editor_property("maximum_distance", radius * 100)
        settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
        settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
        edge(graph, band, "InsideFilter", distance, "Source")
        edge(graph, mark, "Out", distance, "Target")
        near, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
        settings.set_editor_property("lower_bound", 0)
        settings.set_editor_property("upper_bound", 0.99)  # drop the saturated beyond-radius distance
        edge(graph, distance, "Out", near, "In")
        edge(graph, near, "Out", merge, "In")
    shape, settings = graph.add_node_of_type(unreal.PCGTransformPointsSettings)
    settings.set_editor_property("absolute_offset", True)
    settings.set_editor_property("offset_min", unreal.Vector(0, 0, -SINK))
    settings.set_editor_property("offset_max", unreal.Vector(0, 0, -SINK))
    settings.set_editor_property("uniform_scale", False)
    settings.set_editor_property("scale_min", unreal.Vector(SCALE[0], SCALE[0], SCALE[0] * FLATTEN[0]))
    settings.set_editor_property("scale_max", unreal.Vector(SCALE[1], SCALE[1], SCALE[1] * FLATTEN[1]))
    edge(graph, merge, "Out", shape, "In")
    edge(graph, shape, "Out", out, "Out")
    save(graph)
    return graph


def main():
    variants = importlib.reload(biome_variants)
    if not variants.MOUND_VARIANTS or any(w <= 0 for _, w in variants.MOUND_VARIANTS):
        raise RuntimeError("Mound variants must be nonempty with positive weights")
    mounds = [(load(variants.VENDOR + path), weight) for path, weight in variants.MOUND_VARIANTS]
    materials = {mesh.get_name(): mound_material(mesh) for mesh, _ in mounds}
    for material in materials.values():
        save(material)
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    anchors = anchor_graph()
    group = generator("MossMounds", ANCHORS_PER_HA, 20, 45, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    entries = []
    for k in range(SHAPES):
        drift = children(f"DA_MoundDrift{k}", template, [(f"PCG_MoundDrift{k}", drift_points(*DRIFT, k), SCALE, mounds,
                                                          True, {"flatten": FLATTEN, "sink": SINK})])
        rows = list(drift.get_editor_property("BiomeAssets"))
        for value in rows:
            options = get(value, "MeshOptions")
            put(options, Material=materials[get(value, "Mesh").get_name()], AllowCollision=False)
            put(value, MeshOptions=options)
        drift.set_editor_property("BiomeAssets", rows)
        save(drift)
        for mesh, weight in mounds:  # the anchor is one more mound, flattened, sunk and coated as its drift
            value = entry(template, mesh, group, anchors, weight / SHAPES, children=drift, collision=False)
            put(value, AssetType=f"Mound{k}_" + mesh.get_name())
            options = get(value, "MeshOptions")
            put(options, Material=materials[mesh.get_name()])
            put(value, MeshOptions=options)
            entries.append(value)
    assets = asset_list("DA_Forest_MoundAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Moss mounds: {len(mounds)} variants, colonies of {DRIFT[0]} at {ANCHORS_PER_HA}/ha on {len(SITES)} trial"
          f" sites, scale {SCALE}, flatten {FLATTEN}, sunk {SINK} cm")


if __name__ == "__main__":
    main()
