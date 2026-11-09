# editor-py: fresh-siblings
"""Build the Forest Biome Debris group: driftwood scattered over the beach (#38).

    scripts/editor-py scripts/pcg/debris_band.py

Operator ruling (#38): some driftwood is fine, a distinct line between sand and forest is not. So debris is scattered
over the whole beach sand (SAND_FROM up to the shore height), not banded by distance from the forest foot. Small
pieces (DRIFTWOOD_VARIANTS) lie in small piles, each placed stick the anchor of PILE more around it (now and then a
weathered log among them), with bare sand between piles; large trunks (LOG_VARIANTS with a
bleached, moss-free child of each log's material; MossAmount 0 is bare, moss_coating.py) lie apart. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib

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
from saplings_understory import drift_points
from trees_above_shore import shore_height, z_range

FOLDER = ROOT + "Driftwood"
BLEACH = {"MossAmount": 0.0, "Saturation": 0.15, "Brightness": 2.4}  # sun-bleached grey; at 1.7 sticks read black in shade
SAND_FROM = 3  # cm above the sea
# Candidates/ha, without spatial noise, so counts scale with density: trunks 12 -> 4, 60 -> 21, 800 -> 266 island-wide.
# At 12/ha (4 trunks) the beach read as bare sand with twigs (operator: "dont see any driftwood on the sand at all").
# A generator samples the whole biome volume for this thin strip of sand: five stick generators at 2,500/ha each passed
# the 60 GB regenerate limit, so the count comes from children (PILE per anchor), which cost no volume sampling.
# One generator for all anchors (#92 review) did not behave like five sparse ones: at 5,000/ha logs walled the beach,
# at 2,000/ha the beach view was bare with ~9,300 anchors island-wide and almost no children spawned. Hence one
# generator per anchor variant, densities nudged 5% apart (equal densities share every point, deadwood_rocks.py).
PILES_PER_HA = 1000  # per anchor variant; 5 x 1,000/ha peaked at 37-55 GB after a restart, 5 x 1,500/ha at 58 GB
PILE = 12  # pieces around each anchor, in an irregular patch PILE_SIZE cm long and wide
PILE_SIZE = (450, 300)
PILE_LOGS = 0.05  # share of the logs' weights in a pile's palette: about one weathered log in eight piles; 0.2 walled the beach
TRUNKS_PER_HA = 800
TRUNK_PRIORITY, STICK_PRIORITY = 55, 60  # lower numbers place first
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


def bleach(assets, materials):
    """Give every entry of the asset list its mesh's bleached material (children() leaves the source material)."""
    entries = list(assets.get_editor_property("BiomeAssets"))
    for value in entries:
        options = get(value, "MeshOptions")
        put(options, Material=materials[get(value, "Mesh").get_name()])
        put(value, MeshOptions=options)
    assets.set_editor_property("BiomeAssets", entries)
    save(assets)


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
    # The vendor trunks only: the mossy Electric Dreams log (a full /Game path) does not belong on the sand.
    logs = [(load(variants.VENDOR + path), weight) for path, weight in variants.LOG_VARIANTS if not path.startswith("/Game/")]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    sticks = [(load(variants.VENDOR + path), weight) for path, weight in variants.DRIFTWOOD_VARIANTS]
    materials = {mesh.get_name(): driftwood_material(mesh) for mesh, _ in logs + sticks}
    graph = sand_graph()
    # Priorities above the trees' so the forest and shore trees win Core's priority difference; slope up to 35 degrees
    # (the soft rise). Trunks come before sticks: at equal priority the ~17,600 sticks were placed first and pruned all
    # but 4 trunks island-wide; this way the sticks are pruned around the trunks instead.
    # No spatial noise: its density picked the variant, so with noisy singleton sticks only 2 of 5 meshes ever
    # spawned, and it made counts jump nonlinearly. Each anchor variant has its own pile outline; every pile mixes
    # all sticks and, rarely, a log, so weathered trunks lie among the branches (beach reference).
    flat = ({"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    trunk_group = generator("DebrisTrunks", TRUNKS_PER_HA, 35, TRUNK_PRIORITY, *flat)
    palette = sticks + [(mesh, weight * PILE_LOGS) for mesh, weight in logs]
    entries = []
    for index, (mesh, weight) in enumerate(sticks):
        pile = children(f"DA_DebrisPile{index}", template, [(f"PCG_DebrisPile{index}", drift_points(PILE, *PILE_SIZE, index),
                                                             (0.8, 1.3), palette, True)])
        bleach(pile, materials)
        pile_group = generator("DebrisSticks_" + mesh.get_name(), PILES_PER_HA * weight * (1 + 0.05 * index), 35,
                               STICK_PRIORITY, *flat)
        value = entry(template, mesh, pile_group, graph, collision=False, aligned=True, children=pile)
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
    print(f"Debris: {len(sticks)} driftwood pieces, piles of 1 + {PILE} at {PILES_PER_HA}/ha each, {len(logs)} bleached trunks at"
          f" {TRUNKS_PER_HA}/ha, on beach sand")


if __name__ == "__main__":
    main()
