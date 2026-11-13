# editor-py: fresh-siblings
"""Build the Forest Biome Debris group: driftwood on the beach (#38, #230).

    scripts/editor-py scripts/pcg/debris_band.py

Operator ruling (#38): some driftwood is fine, a distinct line between sand and forest is not. Operator decision
(#167): seen from above, driftwood lies in irregular clusters along a wrack line, with bare sand between. So debris
lies on the beach sand (SAND_FROM up to the shore height) within reach of the forest foot, broken up, not as a
continuous band: small pieces (DRIFTWOOD_VARIANTS) in piles of uneven size (PILES), each placed stick the anchor of
more around it (now and then a weathered log among them), with bare sand between piles; large trunks (LOG_VARIANTS
with a bleached, moss-free child of each log's material; MossAmount 0 is bare, moss_coating.py) lie apart, a little
further out. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib

import biome_variants
import unreal
from deadwood_rocks import (
    ROOT,
    asset_list,
    children,
    entry,
    foot_graph,
    generator,
    get,
    load,
    load_forest_actors,
    put,
    save,
)
from saplings_understory import drift_points
from trees_above_shore import shore_height

FOLDER = ROOT + "Driftwood"
# Sun-bleached grey (at 1.7 sticks read black in shade), with no moss and no floor blend at its base: the coated logs
# it derives from take moss_coating.py's ground blend, which turned beach driftwood green at the sand (#168 review).
BLEACH = {"MossAmount": 0.0, "GroundBlend": 0.0, "Saturation": 0.15, "Brightness": 2.4}
SAND_FROM = 3  # cm above the sea
# Candidates/ha, without spatial noise, so counts scale with density: trunks 12 -> 4, 60 -> 21, 800 -> 266 island-wide.
# At 12/ha (4 trunks) the beach read as bare sand with twigs (operator: "dont see any driftwood on the sand at all").
# A generator samples the whole biome volume for this thin strip of sand: five stick generators at 2,500/ha each passed
# the 60 GB regenerate limit, so the count comes from children (PILES per anchor), which cost no volume sampling.
# One generator for all anchors (#92 review) did not behave like five sparse ones: at 5,000/ha logs walled the beach,
# at 2,000/ha the beach view was bare with ~9,300 anchors island-wide and almost no children spawned. Hence one
# generator per anchor variant, densities nudged 5% apart (equal densities share every point, deadwood_rocks.py).
# Wrack line (#230): from 40 m up, sticks spread evenly over the whole sand read as scattered bones on the broad
# north-west flat. They now lie within WRACK_REACH of the forest foot (deadwood_rocks.foot_graph: the shore-height
# contour), where storms leave what the sea carries, in piles of uneven size; trunks reach a little further out. A
# beach narrower than the reach is covered as before; a broad flat keeps its outer sand bare. Bands of height were
# tried first: 40-70 cm took in the whole flat, and 54-72 cm with trunks above 45 cm emptied the low beach of the
# beach view.
WRACK_REACH = 1200  # cm from the forest foot
TRUNK_REACH = 2000
PILES_PER_HA = 900  # per anchor variant; 5 x 1,000/ha peaked at 37-55 GB after a restart, 5 x 1,500/ha at 58 GB
# (pieces around the anchor, patch length cm, patch width cm) per anchor variant: piles of one size at one spacing read
# as a pattern from above, so they run from a few sticks to a heap.
PILES = [(10, 300, 150), (18, 450, 200), (28, 600, 250), (44, 800, 300), (70, 1100, 350)]
PILE_LOGS = 0.05  # share of the logs' weights in a pile's palette: about one weathered log in eight piles; 0.2 walled the beach
TRUNKS_PER_HA = 800  # over the whole sand this gave a trunk every few metres of the broad north-west flat (#230);
# 300 over the whole sand left the beach view without any; hence 800 within TRUNK_REACH of the forest foot
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


def main():
    variants = importlib.reload(biome_variants)
    # The vendor trunks only: the mossy Electric Dreams log (a full /Game path) does not belong on the sand.
    logs = [(load(variants.asset_path(path)), weight) for path, weight in variants.LOG_VARIANTS if not path.startswith("/Game/")]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    sticks = [(load(variants.VENDOR + path), weight) for path, weight in variants.DRIFTWOOD_VARIANTS]
    if len(sticks) != len(PILES):
        raise RuntimeError(f"PILES needs one row per DRIFTWOOD_VARIANTS entry: {len(PILES)} for {len(sticks)}")
    materials = {mesh.get_name(): driftwood_material(mesh) for mesh, _ in logs + sticks}
    graph = foot_graph("PCG_DebrisSand", SAND_FROM, shore_height(), TRUNK_REACH)  # trunks
    wrack = foot_graph("PCG_DebrisWrack", SAND_FROM, shore_height(), WRACK_REACH)  # sticks: the wrack line
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
        pile = children(f"DA_DebrisPile{index}", template, [(f"PCG_DebrisPile{index}", drift_points(*PILES[index], index),
                                                             (0.8, 1.3), palette, True)])
        bleach(pile, materials)
        pile_group = generator("DebrisSticks_" + mesh.get_name(), PILES_PER_HA * weight * (1 + 0.05 * index), 35,
                               STICK_PRIORITY, *flat)
        value = entry(template, mesh, pile_group, wrack, collision=False, aligned=True, children=pile)
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
    print(f"Debris: {len(sticks)} driftwood pieces, piles of 1 + {[pile[0] for pile in PILES]} at {PILES_PER_HA}/ha each, {len(logs)} bleached trunks at"
          f" {TRUNKS_PER_HA}/ha within {TRUNK_REACH / 100:.0f} m of the forest foot, piles within {WRACK_REACH / 100:.0f} m")


if __name__ == "__main__":
    main()
