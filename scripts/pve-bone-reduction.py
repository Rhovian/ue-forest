"""Insert a Bone Reduction node before PVE export nodes; run with scripts/editor-py scripts/pve-bone-reduction.py.

Edit TARGETS, run, then export the variants by hand in the PVE editor (export is not scriptable, #18).
Strength 1.0 is the only setting that brought Megaplants beech under the 400-bone budget (#16).
Variants that already feed from a Bone Reduction node are left alone, so re-running is safe.
"""

import unreal

STRENGTH = 1.0
# PVE asset -> variant letters; an export node's name ends in _<letter>_0 (titles keep Epic's template names).
TARGETS = {
    "/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_Saplings_01/PVE_Tree_European_Beech_Saplings_01": "AB",  # C dropped: its branch data has no parent bones, reduction is a no-op
}


def reduce(path, variants):
    asset = unreal.load_asset(path)
    graph = unreal.find_object(None, asset.get_path_name() + ":ProceduralVegetationGraph")
    feeds = {}  # export node -> upstream node
    for node in graph.get_editor_property("nodes"):
        for pin in node.get_editor_property("output_pins"):
            for edge in pin.get_editor_property("edges"):
                feeds[edge.get_editor_property("output_pin").get_outer()] = node
    exports = [n for n in graph.get_editor_property("nodes") if isinstance(n.get_settings(), unreal.PVExportSettings)]
    for variant in variants:
        export = next(n for n in exports if n.get_name().endswith(f"_{variant}_0"))
        upstream = feeds[export]
        if isinstance(upstream.get_settings(), unreal.PVBoneReductionSettings):
            print(f"{path} {variant}: already reduced")
            continue
        graph.remove_edge(upstream, "Out", export, "In")
        node, settings = graph.add_node_of_type(unreal.PVBoneReductionSettings)
        settings.set_editor_property("strength", STRENGTH)
        graph.add_edge(upstream, "Out", node, "In")
        graph.add_edge(node, "Out", export, "In")
        print(f"{path} {variant}: Bone Reduction {STRENGTH} before {export.get_name()}")
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)


for path, variants in TARGETS.items():
    reduce(path, variants)
