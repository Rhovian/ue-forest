# editor-py: fresh-siblings
"""Set the Forest Biome Trees group's rows from biome_variants.TREE_VARIANTS (#144).

    scripts/editor-py scripts/pcg/canopy_trees.py

The rows (DA_Forest_TreesAssets) were set by hand with the four Megaplants beech. This keeps each existing row whose
mesh is still listed (its wind, options and children) and adds a copy of the first row for each new mesh, so a new
species shares the beech's generator, scale and filter. Every row gets its own AssetType and the weights are nudged
apart (forest-pcg skill: rows sharing a type share one point pool; equal weights share every sampler point). Then flare_moss.py (moss children for the trees that have shells),
shore_trees.py, exact_exclusions.py and regenerate_biome.py --save.
"""

import importlib

import biome_variants
from deadwood_rocks import ROOT, get, load, put, save


def main():
    variants = importlib.reload(biome_variants).TREE_VARIANTS
    if not variants or any(weight <= 0 for _, weight in variants):
        raise RuntimeError("Tree variants must be nonempty with positive weights")
    if len({path for path, _ in variants}) != len(variants):
        raise RuntimeError("A tree mesh may appear only once in TREE_VARIANTS")
    trees = load(ROOT + "DA_Forest_TreesAssets")
    rows = list(trees.get_editor_property("BiomeAssets"))
    existing = {(get(row, "SkeletalMesh") or get(row, "Mesh")).get_path_name().split(".")[0]: row for row in rows}
    template = rows[0]
    out = []
    for index, (path, weight) in enumerate(variants):
        row = existing.get(path)
        if row is None:
            row = template.copy()
            put(row, SkeletalMesh=load(path), Mesh=None, ChildAssets=None)
        put(row, AssetType="Tree_" + load(path).get_name(), Weight=weight * (1 + index * 0.01))
        out.append(row)
    trees.set_editor_property("BiomeAssets", out)
    save(trees)
    dropped = sorted(set(existing) - {path for path, _ in variants})
    print(f"Trees: {len(out)} rows, {len(out) - len(set(existing) & {p for p, _ in variants})} new, dropped {dropped}")


if __name__ == "__main__":
    main()
