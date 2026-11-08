# editor-py: fresh-siblings
"""Build the Forest Biome MossMounds group: low moss cushions over the interior floor (#71, interior_01).

    scripts/editor-py scripts/pcg/moss_mounds.py
    scripts/editor-py scripts/materials/moss_coating.py   # then coat the mound materials this script copies

interior_01 has overlapping soft moss cushions over the ground; ours was one smooth sheet with plants on it
(docs/research/forest-floor-terrain.md: missing intermediate-scale relief, trial 1). MOUND_VARIANTS are mossy
boulders, flattened, mostly sunk and fully moss-coated (copies of their materials, MOUND in moss_coating.py), in
irregular colonies: sparse anchors carry a drift of mounds each, as ground-projected children, so the cushions cost no
dense whole-volume sampling. Saves assets and attaches the group; the lead regenerates Core and saves the level.
"""

import importlib

import biome_variants
import unreal
from deadwood_rocks import (
    ROOT,
    asset_list,
    children,
    entry,
    filter_graph,
    generator,
    get,
    load,
    load_forest_actors,
    put,
    save,
)
from saplings_understory import SHAPES, drift_points

FOLDER = "/Game/ForestBiome/Moss"
ANCHORS_PER_HA = 600  # colony anchors; the understory's spatial noise keeps colonies with open floor between
DRIFT = (10, 560, 420)  # mounds per colony, length and width cm
SCALE = (0.6, 1.0)  # across
FLATTEN = (0.3, 0.4)  # height, on top of SCALE: 1.3-2.4 m boulders become 0.2-0.6 m tall
SINK = 20  # cm into the floor: 0.1-0.4 m of cushion shows (research trial: 0.1-0.3 m rise)


def mound_material(mesh):
    """MI_<mesh id>_Mound in FOLDER: a copy of the boulder's material, which moss_coating.py coats all over."""
    source = mesh.get_editor_property("static_materials")[0].get_editor_property("material_interface")
    name = "MI_" + mesh.get_name().split("_")[0] + "_Mound"
    path = f"{FOLDER}/{name}"
    return unreal.load_asset(path) or unreal.EditorAssetLibrary.duplicate_asset(source.get_path_name().split(".")[0], path)


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
    plain = filter_graph("PCG_PlantsAboveShore")
    # The understory's colony noise (saplings_understory.py), so mound colonies leave open floor between them.
    group = generator("MossMounds", ANCHORS_PER_HA, 20, 45,
                      {"SpatialDensityLow": 0.3, "SpatialDensityHigh": 1.0}, {"EnableVoronoiNoiseBreakup": True})
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
        for mesh, weight in mounds:  # the anchor is one more mound, as sunk and coated as its drift
            value = entry(template, mesh, group, plain, weight / SHAPES, children=drift, collision=False)
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
    print(f"Moss mounds: {len(mounds)} variants, colonies of {DRIFT[0]} at {ANCHORS_PER_HA}/ha, scale {SCALE},"
          f" flatten {FLATTEN}, sunk {SINK} cm")


if __name__ == "__main__":
    main()
