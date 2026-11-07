# editor-py: fresh-siblings
"""Build the Forest Biome Debris group: driftwood scattered over the beach (#38).

    scripts/editor-py scripts/pcg/debris_band.py

Operator ruling (#38): some driftwood is fine, a distinct line between sand and forest is not. So debris is scattered
over the whole beach sand (SAND_FROM up to the shore height), not banded by distance from the forest foot. Small
pieces (DRIFTWOOD_VARIANTS) use the template's spatial noise, so they gather into occasional small piles with bare sand
between; a few large trunks (LOG_VARIANTS with a bleached, moss-free child of each log's material; MossAmount 0 is
bare, moss_coating.py) lie apart. Saves assets and attaches the group; the lead regenerates Core and saves the level.
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
SAND_FROM = 3  # cm above the sea
STICKS_PER_HA = 2500  # candidates/ha; ~17,600 pieces island-wide. Between ~1,800 and 2,500 the count jumps (~400 -> 17,600)
TRUNKS_PER_HA = 12
mel = unreal.MaterialEditingLibrary


def driftwood_material(mesh):
    """The bleached child of mesh's first material, created or updated: MI_<mesh id>_Driftwood."""
    source = mesh.get_editor_property("static_materials")[0].get_editor_property("material_interface")
    name = "MI_" + mesh.get_name().removeprefix("SM_").split("_")[0] + "_Driftwood"
    instance = unreal.load_asset(f"{FOLDER}/{name}") or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    mel.set_material_instance_parent(instance, source)
    for parameter, value in BLEACH.items():
        mel.set_material_instance_scalar_parameter_value(instance, parameter, value)
    save(instance)
    return instance


def sand_graph():
    """Filter keeping beach sand points (SAND_FROM up to the shore height)."""
    graph = copy_asset(ROOT + "PCG_TreesAboveShore", "PCG_DebrisSand")
    inp, out = graph.get_input_node(), graph.get_output_node()
    for node in list(graph.get_editor_property("nodes")):
        if node not in (inp, out):
            graph.remove_node(node)
    sand = z_range(graph, SAND_FROM, shore_height())
    edge(graph, inp, "In", sand, "In")
    edge(graph, sand, "InsideFilter", out, "Out")
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
    sticks = [(load(variants.VENDOR + path), weight) for path, weight in variants.DRIFTWOOD_VARIANTS]
    materials = {mesh.get_name(): driftwood_material(mesh) for mesh, _ in logs + sticks}
    graph = sand_graph()
    # Priority 60 so the forest and shore trees win Core's priority difference; slope up to 35 degrees (the soft rise).
    # Sticks keep the spatial noise (piles with bare sand between); trunks are rare and need none.
    stick_group = generator("DebrisSticks", STICKS_PER_HA, 35, 60)
    trunk_group = generator("DebrisTrunks", TRUNKS_PER_HA, 35, 60, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    entries = []
    for mesh, weight in sticks:
        value = entry(template, mesh, stick_group, graph, weight, collision=False, aligned=True)
        put(value, AssetType="Driftwood_" + mesh.get_name())
        options = get(value, "MeshOptions")
        put(options, Material=materials[mesh.get_name()])  # sun-bleached, like the trunks
        put(value, MeshOptions=options)
        entries.append(value)
    for mesh, weight in logs:
        value = entry(template, mesh, trunk_group, graph, weight, aligned=True)
        put(value, AssetType="DriftTrunk_" + mesh.get_name())
        options = get(value, "MeshOptions")
        put(options, Material=materials[mesh.get_name()])
        put(value, MeshOptions=options)
        entries.append(value)
    assets = asset_list("DA_Forest_DebrisAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Debris: {len(sticks)} driftwood pieces at {STICKS_PER_HA}/ha (noise patches), {len(logs)} bleached trunks at"
          f" {TRUNKS_PER_HA}/ha, on beach sand")


if __name__ == "__main__":
    main()
