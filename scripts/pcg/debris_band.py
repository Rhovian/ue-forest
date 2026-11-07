# editor-py: fresh-siblings
"""Build the Forest Biome Debris group: driftwood on the beach strip, densest at the forest foot (#38).

    scripts/editor-py scripts/pcg/debris_band.py

edge_in_01/03, beach_01/02: a debris band of bleached driftwood runs the length of the beach, densest within a few
metres of the trees and thinning toward the waterline; pieces vary in size. #33 fallback (the driftwood listings
checked were paid): the installed fallen logs (LOG_VARIANTS) with a bleached, moss-free child of each log's material
(MossAmount 0 is bare, moss_coating.py; colour drained and brightened). Beach sand is split by distance from the forest
foot (scripts/pcg/forest_foot.json, from scripts/terrain/forest_foot.py): the band nearest the trees gets most of the
pieces, sparser bands follow toward the water. Saves assets and attaches the group; the lead regenerates Core and
saves the level.
"""

import importlib
import json
from pathlib import Path

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

FOLDER = ROOT + "Driftwood"
BLEACH = {"MossAmount": 0.0, "Saturation": 0.25, "Brightness": 1.7}
FOOT = Path(biome_variants.__file__).with_name("forest_foot.json")  # this folder; editor-py runs code without __file__
SAND_FROM = 3  # cm above the sea
# (farthest cm from the forest foot, candidates/ha) per band, nearest band first; each starts where the previous ends.
BANDS = [(400, 20000), (1200, 2500)]
mel = unreal.MaterialEditingLibrary


def driftwood_material(mesh):
    """The bleached child of mesh's first material, created or updated: MI_<mesh id>_Driftwood."""
    source = mesh.get_editor_property("static_materials")[0].get_editor_property("material_interface")
    name = "MI_" + mesh.get_name().split("_")[0] + "_Driftwood"
    instance = unreal.load_asset(f"{FOLDER}/{name}") or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    mel.set_material_instance_parent(instance, source)
    for parameter, value in BLEACH.items():
        mel.set_material_instance_scalar_parameter_value(instance, parameter, value)
    save(instance)
    return instance


def band_graph(name, foot_m, near, far):
    """Filter keeping beach sand points whose distance to the nearest forest foot point is in [near, far) cm."""
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", name)
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    sand = z_range(graph, SAND_FROM, shore_height())
    edge(graph, inp, "In", sand, "In")
    marks, settings = graph.add_node_of_type(unreal.PCGCreatePointsSettings)
    created = []
    for x, y in foot_m:
        point = unreal.PCGPoint()
        point.set_editor_property("transform", unreal.Transform(location=unreal.Vector(x * 100, y * 100, 0)))
        created.append(point)
    settings.set_editor_property("points_to_create", created)
    settings.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    settings.set_editor_property("cull_points_outside_volume", False)
    # Same native distance and density filter as shore_trees.py: density = horizontal distance / BANDS' last far.
    reach = BANDS[-1][0]
    distance, settings = graph.add_node_of_type(unreal.PCGDistanceSettings)
    settings.set_editor_property("set_density", True)
    settings.set_editor_property("maximum_distance", reach)
    settings.set_editor_property("source_shape", unreal.PCGDistanceShape.CENTER)
    settings.set_editor_property("target_shape", unreal.PCGDistanceShape.CENTER)
    edge(graph, sand, "InsideFilter", distance, "Source")
    edge(graph, marks, "Out", distance, "Target")
    band, settings = graph.add_node_of_type(unreal.PCGDensityFilterSettings)
    settings.set_editor_property("lower_bound", near / reach)
    settings.set_editor_property("upper_bound", min(far / reach, 0.99))  # drop the saturated beyond-reach distance
    edge(graph, distance, "Out", band, "In")
    edge(graph, band, "Out", out, "Out")
    save(graph)
    return graph


def main():
    variants = importlib.reload(biome_variants)
    logs = [(load(variants.VENDOR + path), weight) for path, weight in variants.LOG_VARIANTS]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    materials = {mesh.get_name(): driftwood_material(mesh) for mesh, _ in logs}
    foot = json.loads(FOOT.read_text())
    if abs(foot["shore_cm"] - shore_height()) > 1:
        raise RuntimeError(f"{FOOT.name} was built for shore {foot['shore_cm']} cm; rerun scripts/terrain/forest_foot.py")
    entries, near = [], 0
    for index, (far, per_ha) in enumerate(BANDS):
        graph = band_graph(f"PCG_DebrisBand{index}", foot["points_m"], near, far)
        # Own generator per band; priority 60 so the forest and shore trees win Core's priority difference. Spatial
        # noise off (it thins nearly all candidates); slope up to 35 degrees, the beach's rise to the forest foot.
        group = generator(f"Debris{index}", per_ha, 35, 60, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False}, 30)
        for mesh, weight in logs:
            value = entry(template, mesh, group, graph, weight, aligned=True)
            put(value, AssetType=f"Driftwood{index}_" + mesh.get_name())
            options = get(value, "MeshOptions")
            put(options, Material=materials[mesh.get_name()])
            put(value, MeshOptions=options)
            entries.append(value)
        near = far
    assets = asset_list("DA_Forest_DebrisAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Debris band: {BANDS} (cm from the forest foot, candidates/ha), {len(foot['points_m'])} foot points,"
          f" {len(logs)} driftwood variants")


if __name__ == "__main__":
    main()
