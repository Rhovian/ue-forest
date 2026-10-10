"""Read-only /Game budget audit; run with scripts/editor-py scripts/asset-budget.py.

Uses reflected engine properties and Blueprint functions; requires UE 5.8 for
MeshNaniteSettings.shape_preservation. No assets are edited or saved.
"""
import unreal

# PVE sample content the budget relies on: master material, Wind Driver, wind transform provider.
PLUGIN_CONTENT = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/MA_Foliage_Trees",
    "/ProceduralVegetationEditor/SampleAssets/Materials/GlobalFoliageActor/BP_GlobalFoliageActor_UE5",
    "/ProceduralVegetationEditor/SampleAssets/Materials/GlobalFoliageActor/Wind_TransformProvider",
)


def blend_mode(material):
    """Resolve instance overrides through the parent chain."""
    seen = set()
    while isinstance(material, unreal.MaterialInstance):
        if material in seen:
            raise RuntimeError("cyclic material parent chain")
        seen.add(material)
        overrides = material.get_editor_property("base_property_overrides")
        if overrides.get_editor_property("override_blend_mode"):
            return overrides.get_editor_property("blend_mode")
        material = material.get_editor_property("parent")
    if material is None:
        raise RuntimeError("material parent did not load")
    return material.get_editor_property("blend_mode")


def used_by_material(data):
    """True if a material, instance or material function references the texture's package."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    referencers = registry.get_referencers(data.package_name, unreal.AssetRegistryDependencyOptions()) or []
    return any(
        "Material" in str(referencer.asset_class_path.asset_name)
        for package in referencers
        for referencer in registry.get_assets_by_package_name(package)
    )


def violations(asset, data):
    name = str(data.asset_name)
    if isinstance(asset, (unreal.StaticMesh, unreal.SkeletalMesh)):
        settings = asset.get_editor_property("nanite_settings")
        if not settings.get_editor_property("enabled"):
            yield "Nanite enabled", False
        shape = settings.get_editor_property("shape_preservation")
        if shape != unreal.NaniteShapePreservation.VOXELIZE:
            yield "Nanite shape preservation must be Voxelize", shape
    if isinstance(asset, unreal.SkeletalMesh):
        if asset.get_editor_property("physics_asset") is None:
            yield "physics asset (trunk collision)", None
        # Only this transient, unregistered component changes; the mesh asset is untouched.
        component = unreal.SkeletalMeshComponent()
        component.set_skeletal_mesh_asset(asset)
        bones = component.get_num_bones()
        if bones > 400:
            yield "bones <= 400", bones
    if isinstance(asset, unreal.Texture2D):
        # Imported size from the registry; blueprint_get_size_x/y can read a not-yet-compiled texture.
        width, height = map(int, data.get_tag_value("Dimensions").split("x"))
        short, long = sorted((width, height))
        displacement = "displacement" in name.lower()
        if long > 4096 and not (displacement and short <= 4096 and long <= 8192):
            yield "texture dimensions <= 4096 (Displacement <= 4096x8192)", f"{width}x{height}"
        streaming = asset.get_editor_property("virtual_texture_streaming")
        if long > 2048 and not streaming and used_by_material(data):
            yield "virtual texture streaming above 2048 on a material texture", streaming
    if isinstance(asset, (unreal.Material, unreal.MaterialInstance)):
        mode = blend_mode(asset)
        if mode not in (unreal.BlendMode.BLEND_OPAQUE, unreal.BlendMode.BLEND_MASKED):
            yield "blend mode opaque or masked", mode
        elif mode == unreal.BlendMode.BLEND_MASKED and not any(
            word in name.lower() for word in ("foliage", "leaf", "twig")
        ):
            yield "masked name must contain Foliage, Leaf or Twig", name


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    assets = registry.get_assets_by_path("/Game", recursive=True)
    count = 0
    for path in PLUGIN_CONTENT:
        if unreal.load_asset(path) is None:
            print(f"{path}: plugin content did not load")
            count += 1
    for data in sorted(assets, key=lambda data: (str(data.package_name), str(data.asset_name))):
        package, name = str(data.package_name), str(data.asset_name)
        # Megaplants part meshes: tree assemblies override their Nanite settings at build
        # (UE 5.8 Nanite::InheritAssemblySettings), and nothing places them directly.
        megaplant_part = package.startswith("/Game/Megaplant_Library/") and "/Instances/" in package
        if package == "/Game/Scratch" or package.startswith("/Game/Scratch/") or megaplant_part:
            continue
        path = f"{package}.{name}"
        try:
            asset = data.get_asset()
            if asset is None:
                raise RuntimeError("asset could not be loaded")
            for rule, actual in violations(asset, data):
                print(f"{path}: {rule}: {actual}")
                count += 1
        except Exception as error:  # noqa: BLE001 -- report all unreadable assets, then fail the audit
            print(f"{path}: inspection failed: {error}")
            count += 1
    print(f"Asset budget: {count} violation(s)")
    if count:
        raise RuntimeError(f"Asset budget failed: {count} violation(s)")


if __name__ == "__main__":
    main()
