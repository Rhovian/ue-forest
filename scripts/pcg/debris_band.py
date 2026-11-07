# editor-py: fresh-siblings
"""Build the Forest Biome Debris group: driftwood on the beach strip, densest at the forest foot (#38).

    scripts/editor-py scripts/pcg/debris_band.py

edge_in_01/03, beach_01/02: a debris band of bleached driftwood runs the length of the beach, densest within a few
metres of the trees and thinning toward the waterline; pieces vary in size. #33 fallback (the driftwood listings
checked were paid): the installed fallen logs (LOG_VARIANTS) with a bleached, moss-free child of each log's material
(MossAmount 0 is bare, moss_coating.py; colour drained and brightened). The sand is split by height above the sea: the
upper band, at the forest foot, gets most of the pieces. Saves assets and attaches the group; the lead regenerates
Core and saves the level.
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

FOLDER = ROOT + "Driftwood"
BLEACH = {"MossAmount": 0.0, "Saturation": 0.25, "Brightness": 1.7}
# (lowest cm above the sea, candidates/ha) per band, top band first; tops are the next band up or the shore height.
BANDS = [(40, 3200), (3, 800)]
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
    entries, top = [], shore_height()
    for index, (low, per_ha) in enumerate(BANDS):
        graph = copy_asset(ROOT + "PCG_TreesAboveShore", f"PCG_DebrisBand{index}")
        inp, out = graph.get_input_node(), graph.get_output_node()
        for node in list(graph.get_editor_property("nodes")):
            if node not in (inp, out):
                graph.remove_node(node)
        band = z_range(graph, low, top)
        edge(graph, inp, "In", band, "In")
        edge(graph, band, "InsideFilter", out, "Out")
        save(graph)
        # Own generator per band; priority 60 so the forest and shore trees win Core's priority difference.
        group = generator(f"Debris{index}", per_ha, 15, 60, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False}, 60)
        for mesh, weight in logs:
            value = entry(template, mesh, group, graph, weight, aligned=True)
            put(value, AssetType=f"Driftwood{index}_" + mesh.get_name())
            options = get(value, "MeshOptions")
            put(options, Material=materials[mesh.get_name()])
            put(value, MeshOptions=options)
            entries.append(value)
        top = low
    assets = asset_list("DA_Forest_DebrisAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Debris band: {BANDS} (cm above sea, candidates/ha), {len(logs)} driftwood variants")


if __name__ == "__main__":
    main()
