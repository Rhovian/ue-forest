"""Calm the wind sway of trees that move too much (#161).

    scripts/editor-py scripts/materials/tree_wind.py

The veteran beech (biome_variants.VETERAN_VARIANTS, a static Nanite mesh) sways by its material's SimpleWind world
position offset, and at its placed scale (1.6-1.8) it swayed far more than the forest round it (tour stop 9, operator
2026-11-09). WIND is appendable: material instance -> scalar overrides.
"""

import unreal

WIND = {
    "/Game/EuropeanBeech/Materials/Simplewind/MAI_EuropeanBeech": {
        # Halving the first two (0.4, 0.6) still swayed too much in motion (operator review, #161).
        "Wind Animation Strength": 0.15,  # was 0.85
        "Wind Noise Strength": 0.25,  # was 1.3
        "Additional Wind Animation Noise Strength": 0.3,  # was 1.0
    },
}

for path, values in WIND.items():
    mi = unreal.load_asset(path)
    for name, value in values.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, name, value)
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mi, False):
        raise SystemExit(f"could not save {path}")
    print(f"{path}: {values}")
