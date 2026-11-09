# editor-py: fresh-siblings
"""Build the Forest Biome Veterans group: a few massive old beech among the forest (#80, interior_01).

    scripts/editor-py scripts/pcg/veteran_trees.py

interior_01 wants massive old trunks with spreading root flares among the mature trees; the Megaplants beech are one
adult shape (#79: scaling them only varied girth). VETERAN_VARIANTS are the Megascans open-grown field beech, static
Nanite meshes. Their generator runs before the Trees group (a lower priority number) without overlap, so the forest
beech are pruned around each veteran's crown instead of growing through it. A veteran trial with skinned Megaplants
meshes left canopy holes with no tree (forest-pcg skill); these meshes are static. Same forest-floor filter as the
Trees group. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib

import biome_variants
import unreal
from deadwood_rocks import ROOT, asset_list, entry, generator, get, load, load_forest_actors, put, save, shell_children

PER_HA = 2  # candidates/ha island-wide
PRIORITY = -10  # before the Trees group (0): the beech are pruned around the veteran
# Core differences point sets by priority before the forest-floor filter, so a candidate the filter later rejects
# (sand, water, path) has already pruned beech within its pruning bounds (#96 review). Both groups use the same filter,
# so only beech within PRUNE_EXTENT x half the crown (~6 m) of that boundary are at risk: at PER_HA, about a dozen
# candidates fall in that strip along the whole coast. Accepted for the veteran crowns; do not raise PER_HA blindly.
# The field tree is 23 m tall with a moderate trunk at 1.0 (and the generator's default 0.8-1.2 read as an ordinary
# beech); veterans are the island's biggest trees, trunks clearly thicker than the 1.1-1.9 forest beech (#79).
SCALE = (1.5, 1.9)
# Pruning uses the asset's bounds: at full size (the mesh is ~23 m across at 1.0, ~44 m at 1.9) each veteran cleared ~0.2 ha of beech, a sunlit
# hole in the interior view. Shrunk, the neighbours stand at the inner crown and the outer crown interleaves with them.
PRUNE_EXTENT = 0.3


def main():
    variants = importlib.reload(biome_variants).VETERAN_VARIANTS
    if not variants or any(weight <= 0 for _, weight in variants):
        raise RuntimeError("Veteran variants must be nonempty with positive weights")
    meshes = [(load(path), weight) for path, weight in variants]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    filter_graph = load(ROOT + "PCG_TreesAboveShore")
    group = generator("Veterans", PER_HA, 15, PRIORITY, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    graph = load(ROOT + "PCG_Forest_VeteransGenerator")
    for name, scale in (("ScaleMin", SCALE[0]), ("ScaleMax", SCALE[1])):
        unreal.PCGGraphParametersHelpers.set_vector_parameter(graph, name, unreal.Vector(scale, scale, scale))
    save(graph)
    value = group.get_editor_property("Generator")
    put(value, GeneratorAllowOverlap=False)  # prune the forest beech around each veteran
    group.set_editor_property("Generator", value)
    save(group)
    entries = []
    for mesh, weight in meshes:
        value = entry(template, mesh, group, filter_graph, weight, shell_children(template, mesh))  # root-flare tufts (#116)
        put(value, AssetType="Veteran_" + mesh.get_name())
        options = get(value, "AssetOptions")
        put(options, ExtentsMultiplier=unreal.Vector(PRUNE_EXTENT, PRUNE_EXTENT, 1.0))
        put(value, AssetOptions=options)
        entries.append(value)
    assets = asset_list("DA_Forest_VeteranAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Veterans: {PER_HA} candidates/ha, {len(entries)} variants, scale {SCALE}, priority {PRIORITY}, no overlap")


if __name__ == "__main__":
    main()
