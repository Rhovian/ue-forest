"""Tint imported tree materials that read wrong in the forest (#144).

    scripts/editor-py scripts/materials/tree_tints.py

The Megaplants Norway Spruce's dead lower branches (MI_Norway_Spruce_Decorations_01) came out as bright orange spokes
round the trunk in canopy_up (#153 review); a darker, greyer tint makes them dead wood in the shade. The master's
neutral tint is 0.5. TINTS is appendable: material instance -> BaseColor Tint.
"""

import unreal

TINTS = {
    "/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/MI_Norway_Spruce_Decorations_01": (0.24, 0.23, 0.22),
}

for path, (r, g, b) in TINTS.items():
    mi = unreal.load_asset(path)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        mi, "BaseColor Tint", unreal.LinearColor(r, g, b, 0))
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mi, False):
        raise SystemExit(f"could not save {path}")
    print(f"{path}: BaseColor Tint {(r, g, b)}")
