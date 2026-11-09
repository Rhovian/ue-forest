# editor-py: fresh-siblings
"""Build the Forest Biome Hornbeams group: hornbeam as a minority among the beech (#125).

    scripts/editor-py scripts/pcg/hornbeam_trees.py

HORNBEAM_VARIANTS are Electric Dreams' Megascans European hornbeam, static Nanite forest trees. They stand among the
beech as the shore trees do: overlap on and a priority after the Trees group, so no beech is pruned for them. Run before
the Trees group without overlap (as the veterans are), each pruned the tall beech round its lower crown and opened the
canopy (#131 review: a broad sky hole at canopy_up), and a candidate the floor filter later rejected had already pruned
its neighbours. Same forest-floor filter as the Trees group. Saves assets and attaches the group; then exact_exclusions.py and
regenerate_biome.py --save.
"""

import importlib

import biome_variants
import unreal
from deadwood_rocks import ROOT, asset_list, entry, generator, load, load_forest_actors, put, save

PER_HA = 7  # candidates/ha island-wide: 30 gave 1,303 hornbeams that pruned the beech into a hornbeam forest
PRIORITY = 40  # after the Trees group (0): among the beech, pruning none
SCALE = (1.2, 1.5)  # the meshes are 11-16 m tall; at this scale they stand in the beech's lower crown layer


def main():
    variants = importlib.reload(biome_variants).HORNBEAM_VARIANTS
    if not variants or any(weight <= 0 for _, weight in variants):
        raise RuntimeError("Hornbeam variants must be nonempty with positive weights")
    meshes = [(load(path), weight) for path, weight in variants]
    trees = load(ROOT + "DA_Forest_TreesAssets")
    template = trees.get_editor_property("BiomeAssets")[0]
    biomes = [a for a in load_forest_actors() if a.get_class().get_name().startswith("BP_PCGBiomeVolume")
              and trees in a.get_editor_property("Assets")]
    if not biomes:
        raise RuntimeError("Load the forest biome volume (all WP cells) before running")
    filter_graph = load(ROOT + "PCG_TreesAboveShore")
    group = generator("Hornbeams", PER_HA, 15, PRIORITY, {"SpatialDensityLow": 1.0}, {"EnableSpatialNoise": False})
    graph = load(ROOT + "PCG_Forest_HornbeamsGenerator")
    for name, scale in (("ScaleMin", SCALE[0]), ("ScaleMax", SCALE[1])):
        unreal.PCGGraphParametersHelpers.set_vector_parameter(graph, name, unreal.Vector(scale, scale, scale))
    save(graph)
    value = group.get_editor_property("Generator")
    put(value, GeneratorAllowOverlap=True)  # among the beech, not carved out of them
    group.set_editor_property("Generator", value)
    save(group)
    entries = []
    for index, (mesh, weight) in enumerate(meshes):
        # Equal weights share every sampler point (forest-pcg skill): nudge each.
        value = entry(template, mesh, group, filter_graph, weight * (1 + index * 0.01), None)
        put(value, AssetType="Hornbeam_" + mesh.get_name())
        entries.append(value)
    assets = asset_list("DA_Forest_HornbeamAssets", entries)
    for actor in biomes:
        current = list(actor.get_editor_property("Assets"))
        if assets not in current:
            actor.set_editor_property("Assets", current + [assets])
    print(f"Hornbeams: {PER_HA} candidates/ha, {len(entries)} variants, scale {SCALE}, priority {PRIORITY}, overlap")


if __name__ == "__main__":
    main()
