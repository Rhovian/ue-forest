# editor-py: fresh-siblings
"""Give each Trees group beech its root-flare moss tufts as a child (#116, nurse_log_01, rock_assembly_01).

    scripts/editor-py scripts/pcg/flare_moss.py

moss_shells.py bakes SM_<tree>_MossShell for each of its FLARE_TREES: tufts only, on the bark's up-facing faces near
the ground. The Trees group's rows (DA_Forest_TreesAssets) are set by hand, not by a builder, so this sets each row's
ChildAssets to its tree's shell, placed at the tree's own transform like the deadwood's (deadwood_rocks.shell_children).
A row whose tree has no shell keeps no child. veteran_trees.py attaches the veterans' own; shore_trees.py copies these
rows, so rerun it afterwards. Then exact_exclusions.py and regenerate_biome.py.
"""

import unreal
from deadwood_rocks import ROOT, get, load, put, save, shell_children


def match_bounds(children, tree, tree_extents):
    """Give the tufts the tree's own pruning bounds. Core prunes the beech around each veteran by bounds after their
    children are made, so a shell child at deadwood_rocks.SHELL_EXTENTS outlived its pruned tree: about one in eight
    tuft clumps stood alone, all within 21 m of a veteran (#116)."""
    entries = list(children.get_editor_property("BiomeAssets"))
    for value in entries:
        shell = get(value, "Mesh").get_bounds().box_extent
        size = tree.get_bounds().box_extent
        options = get(value, "AssetOptions")
        put(options, ExtentsMultiplier=unreal.Vector(*(getattr(size, a) * getattr(tree_extents, a) / max(getattr(shell, a), 1)
                                                       for a in "xyz")))
        put(value, AssetOptions=options)
    children.set_editor_property("BiomeAssets", entries)
    save(children)


def main():
    trees = load(ROOT + "DA_Forest_TreesAssets")
    rows = list(trees.get_editor_property("BiomeAssets"))
    template = rows[0].copy()
    for row in rows:
        mesh = get(row, "SkeletalMesh") or get(row, "Mesh")
        children = shell_children(template, mesh)
        if children:
            match_bounds(children, mesh, get(get(row, "AssetOptions"), "ExtentsMultiplier"))
        put(row, ChildAssets=children)
        if children:  # as deadwood_rocks.entry sets on its hosts: else Core prunes the child that overlaps its parent
            put(row, AssetOptions=put(get(row, "AssetOptions"), OverlapWithChildren=True))
        print(f"{mesh.get_name()}: " + (f"child {children.get_name()}" if children else "no moss shell, no child"))
    trees.set_editor_property("BiomeAssets", rows)
    save(trees)


if __name__ == "__main__":
    main()
