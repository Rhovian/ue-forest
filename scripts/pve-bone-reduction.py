"""Insert Bone Reduction before a PVE graph's export nodes.

    scripts/editor-py scripts/pve-bone-reduction.py <PVE asset> <variants> [--strength N]

variants: export-node letters, e.g. AB (an export node's name ends in _<letter>_0). Required: reduce
only variants over the bone budget.
Strength 1.0 is the only setting that brought Megaplants beech under the 400-bone budget (#16).
Variants already fed by a Bone Reduction node are left alone, so re-running is safe. Then export the
variants by hand in the PVE editor (force regenerate first; export is not scriptable, #18).
"""

import argparse

import unreal


def reduce(path, variants, strength):
    asset = unreal.load_asset(path)
    if asset is None:
        raise SystemExit(f"{path}: not found")
    graph = unreal.find_object(None, asset.get_path_name() + ":ProceduralVegetationGraph")
    feeds = {}  # export node -> upstream node
    for node in graph.get_editor_property("nodes"):
        for pin in node.get_editor_property("output_pins"):
            for edge in pin.get_editor_property("edges"):
                feeds[edge.get_editor_property("output_pin").get_outer()] = node
    exports = [n for n in graph.get_editor_property("nodes") if isinstance(n.get_settings(), unreal.PVExportSettings)]
    exports = [n for n in exports if any(n.get_name().endswith(f"_{v}_0") for v in variants)]
    if len(exports) != len(variants):
        raise SystemExit(f"{path}: expected export nodes for {variants}, found {[n.get_name() for n in exports]}")
    for export in exports:
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
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)


parser = argparse.ArgumentParser(prog="pve-bone-reduction.py")
parser.add_argument(
    "asset", help="PVE asset path, e.g. /Game/Megaplant_Library/.../PVE_Tree_European_Beech_Saplings_01"
)
parser.add_argument("variants", help="export letters, e.g. AB")
parser.add_argument("--strength", type=float, default=1.0)
args = parser.parse_args()
reduce(args.asset, args.variants, args.strength)
