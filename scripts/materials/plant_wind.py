"""Calm the material wind of static plants that sway far more than the plants round them (#269).

    scripts/editor-py scripts/materials/plant_wind.py

The static Megascans and Electric Dreams plants sway by their material's world position offset, not by the Wind
Driver that moves the skinned Megaplants. Those materials move a vertex by a fixed distance, whatever the plant's size,
so a strength that suits a tree throws a seedling or a ground creeper about (operator, 2026-11-26: the ground ivy carpet
at `clearing`, the hornbeam saplings at `edge_out`).

WIND: material instance -> scalar overrides, for instances that only these plants use. Appendable.
SMALL: (shared instance, small plants' copy, overrides, meshes): the shared instance also dresses trees, so the small
plants get a child instance with calmer wind, and only their meshes are pointed at it. Appendable.
Trees: scripts/materials/tree_wind.py.
"""

import unreal

HORNBEAM = "/Game/Megascans/3D_Plants/EuropeanHornbeam/"
SMALL_HORNBEAMS = [f"{HORNBEAM}Geometry/SimpleWind/SM_EuropeanHornbeam_Sapling_{i:02}" for i in range(1, 9)] + [
    f"{HORNBEAM}Geometry/SimpleWind/SM_EuropeanHornbeam_Seedling_{i:02}" for i in range(1, 6)]
CALM_HORNBEAM = {"Wind Noise Strength": 0.15, "Wind Gust Strength": 0.15, "Wind Gust Noise Strength": 0.2}

IVY_CALM = {"Local Primary Wind Strength": 0.15, "Local Secondary Wind Strength": 0.15}  # was 1.0, 1.0
IVY = "/Game/Fab/Megascans/Plants/English_Ivy_xfcnebhqx/Medium/xfcnebhqx_tier_2/Materials/"

# The sword fern's own values (MI_Fern_01), whose motion reads right (operator, 2026-11-26).
FERN_CALM = {"Wind Noise Strength": 0.2, "Wind Gust Strength": 0.4, "Wind Gust Noise Strength": 0.3}
ED = "/Game/Megascans/3D_Plants/"

WIND = {
    # Ground ivy carpet, biome_variants.IVY_VARIANTS.
    f"{IVY}MI_xfcnebhqx": IVY_CALM,
    f"{IVY}MI_xfcnebhqx_Billboard": IVY_CALM,
    # Electric Dreams plants still on the sample's 0.5 / 3.0 / 0.3 (noise, gust, gust noise): at `clearing` they swayed
    # far more than the ferns beside them. GROUNDCOVER_VARIANTS (the landscape grass) and UNDERGROWTH_VARIANTS.
    **{f"{ED}{path}": FERN_CALM for path in (
        "GroundCover/MI_GroundCover_01",
        "PurpleShamrock/MI_PurpleShamrock_01",
        "RedLachenalia/MI_RedLachenalia_01",
        "LilyOfTheValley/MI_LilyOfTheValley_01",
        "Crownbeard/MI_Crownbeard_01",
        "VariegatedCroton/MI_VariegatedCroton_01",
        "WhiteWindflower/MI_WhiteWindflower_01",
        "WhiteWindflower/MI_WhiteWindflower_02",
    )},
}

SMALL = [
    # TwoSided noise 1.0, gust 0.65, gust noise 2.0; Tileable 0.5, 1.5, 0.0 (both shared with the hornbeam trees).
    (f"{HORNBEAM}Materials/SimpleWind/MI_EuropeanHornbeam_TwoSided", "MI_EuropeanHornbeam_TwoSided_Small",
     CALM_HORNBEAM, SMALL_HORNBEAMS),
    (f"{HORNBEAM}Materials/SimpleWind/MI_EuropeanHornbeam_Tileable", "MI_EuropeanHornbeam_Tileable_Small",
     CALM_HORNBEAM, SMALL_HORNBEAMS),
]

MEL = unreal.MaterialEditingLibrary


def save(asset):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise SystemExit(f"could not save {asset.get_path_name()}")


def override(mi, values):
    for name, value in values.items():
        if name not in [str(n) for n in MEL.get_scalar_parameter_names(mi)]:
            raise SystemExit(f"{mi.get_path_name()} has no scalar parameter {name!r}")
        MEL.set_material_instance_scalar_parameter_value(mi, name, value)
    MEL.update_material_instance(mi)


for path, values in WIND.items():
    mi = unreal.load_asset(path)
    if mi is None:
        raise SystemExit(f"missing {path}")
    override(mi, values)
    save(mi)
    print(f"{path}: {values}")

for shared_path, name, values, meshes in SMALL:
    shared = unreal.load_asset(shared_path)
    if shared is None:
        raise SystemExit(f"missing {shared_path}")
    folder = shared_path.rsplit("/", 1)[0]
    small = unreal.load_asset(f"{folder}/{name}")
    if small is None:
        small = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(small, shared)
    override(small, values)
    save(small)
    for mesh_path in meshes:
        mesh = unreal.load_asset(mesh_path)
        if mesh is None:
            raise SystemExit(f"missing {mesh_path}")
        slots = list(mesh.static_materials)
        changed = False
        for i, slot in enumerate(slots):
            if slot.material_interface == shared:
                mesh.set_material(i, small)
                changed = True
        if changed:
            save(mesh)
        elif not any(slot.material_interface == small for slot in slots):
            raise SystemExit(f"{mesh_path} uses neither {shared_path} nor its small copy")
    print(f"{folder}/{name} ({values}) on {len(meshes)} meshes")
