"""Insert Bone Reduction before a PVE graph's export nodes, and set their trunk collision.

    scripts/editor-py scripts/pve-bone-reduction.py <PVE asset> <variants> [--strength N] [--collision LETTERS]

variants: export letters, e.g. AB (the exported mesh's name ends in _<letter>; node names differ between packs).
Required: reduce only variants over the bone budget; "-" reduces none. --collision sets Trunk Only collision
generation (docs/asset-budget.md: trees taller than 6 m) on those variants' export nodes.
Strength 1.0 is the only setting that brought Megaplants beech under the 400-bone budget (#16).
Variants already fed by a Bone Reduction node are left alone, so re-running is safe. Then export the
variants by hand in the PVE editor (force regenerate first; export is not scriptable, #18).
"""

import argparse

import unreal


def exports_for(graph, path, variants):
    """The export nodes of these variant letters, matched by the exported mesh's name."""
    found = {}
    for node in graph.get_editor_property("nodes"):
        settings = node.get_settings()
        if isinstance(settings, unreal.PVExportSettings):
            name = str(settings.get_editor_property("export_settings").get_editor_property("mesh_name"))
            if name[-2:-1] == "_" and name[-1] in variants:
                found[name[-1]] = node
    if sorted(found) != sorted(variants):
        raise SystemExit(f"{path}: expected export nodes for {variants}, found {sorted(found)}")
    return list(found.values())


def collide(graph, path, variants):
    for export in exports_for(graph, path, variants):
        settings = export.get_settings()
        params = settings.get_editor_property("export_settings")
        params.set_editor_property("collision_generation", unreal.PVCollisionGeneration.TRUNK_ONLY)
        settings.set_editor_property("export_settings", params)
        print(f"{export.get_name()}: Trunk Only collision")


def reduce(path, variants, strength, collision):
    asset = unreal.load_asset(path)
    if asset is None:
        raise SystemExit(f"{path}: not found")
    graph = unreal.find_object(None, asset.get_path_name() + ":ProceduralVegetationGraph")
    feeds = {}  # export node -> upstream node
    for node in graph.get_editor_property("nodes"):
        for pin in node.get_editor_property("output_pins"):
            for edge in pin.get_editor_property("edges"):
                feeds[edge.get_editor_property("output_pin").get_outer()] = node
    for export in exports_for(graph, path, variants.replace("-", "")):
        upstream = feeds[export]
        if isinstance(upstream.get_settings(), unreal.PVBoneReductionSettings):
            print(f"{export.get_name()}: already reduced")
            continue
        graph.remove_edge(upstream, "Out", export, "In")
        node, settings = graph.add_node_of_type(unreal.PVBoneReductionSettings)
        settings.set_editor_property("strength", strength)
        graph.add_edge(upstream, "Out", node, "In")
        graph.add_edge(node, "Out", export, "In")
        print(f"{export.get_name()}: Bone Reduction {strength}")
    if collision:
        collide(graph, path, collision)
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)


parser = argparse.ArgumentParser(prog="pve-bone-reduction.py")
parser.add_argument(
    "asset", help="PVE asset path, e.g. /Game/Megaplant_Library/.../PVE_Tree_European_Beech_Saplings_01"
)
parser.add_argument("variants", help='export letters to reduce, e.g. AB, or "-" for none')
parser.add_argument("--strength", type=float, default=1.0)
parser.add_argument("--collision", default="", help="export letters to give Trunk Only collision, e.g. ABCD")
args = parser.parse_args()
reduce(args.asset, args.variants, args.strength, args.collision)
