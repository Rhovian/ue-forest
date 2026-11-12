"""Make textures meet the Asset Budget's texture rule (docs/asset-budget.md): at most 4096, virtual texturing above 2048.

    scripts/editor-py scripts/fit-textures.py <texture folder> <material folder>...

Every Texture2D under the texture folder larger than 4096 has its source halved until it fits (exported, downscaled
with macOS sips, reimported over itself with its settings restored), which also shrinks the package; every one larger
than 2048 gets virtual texture streaming. Texture samples of those textures in the materials and material functions
under each material folder switch to the matching virtual sampler type, or the materials would not compile. Re-running
is safe. Saves what it changed.
"""

import os
import subprocess
import sys
import tempfile

import unreal

MAX, VT_ABOVE = 4096, 2048
mel = unreal.MaterialEditingLibrary
ST = unreal.MaterialSamplerType
VIRTUAL = {ST.SAMPLERTYPE_COLOR: ST.SAMPLERTYPE_VIRTUAL_COLOR, ST.SAMPLERTYPE_LINEAR_COLOR: ST.SAMPLERTYPE_VIRTUAL_LINEAR_COLOR,
           ST.SAMPLERTYPE_NORMAL: ST.SAMPLERTYPE_VIRTUAL_NORMAL, ST.SAMPLERTYPE_MASKS: ST.SAMPLERTYPE_VIRTUAL_MASKS,
           ST.SAMPLERTYPE_GRAYSCALE: ST.SAMPLERTYPE_VIRTUAL_GRAYSCALE, ST.SAMPLERTYPE_ALPHA: ST.SAMPLERTYPE_VIRTUAL_ALPHA,
           ST.SAMPLERTYPE_LINEAR_GRAYSCALE: ST.SAMPLERTYPE_VIRTUAL_LINEAR_GRAYSCALE}
KEPT = ("compression_settings", "srgb", "lod_group", "address_x", "address_y", "mip_gen_settings", "flip_green_channel")


def size(texture):
    # Built size from the source and settings: blueprint_get_size_x reads 32 while a texture still compiles.
    built = texture.blueprint_get_built_texture_size()
    return int(max(built.x, built.y))


def downscale(texture):
    """Export the source, halve it until it fits MAX, and reimport it over the asset with its settings."""
    settings = {key: texture.get_editor_property(key) for key in KEPT}
    path = texture.get_path_name().split(".")[0]
    folder, name = path.rsplit("/", 1)
    scratch = tempfile.mkdtemp()
    png = os.path.join(scratch, name + ".png")
    task = unreal.AssetExportTask()
    for key, value in {"object": texture, "filename": png, "automated": True, "prompt": False, "replace_identical": True}.items():
        task.set_editor_property(key, value)
    if not unreal.Exporter.run_asset_export_task(task) or not os.path.exists(png):
        raise SystemExit(f"could not export {path}")
    subprocess.run(["sips", "-Z", str(MAX), png], check=True, capture_output=True, timeout=60)
    task = unreal.AssetImportTask()
    for key, value in {"filename": png, "destination_path": folder, "destination_name": name, "replace_existing": True,
                       "automated": True, "save": False}.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    os.remove(png)
    os.rmdir(scratch)
    texture = unreal.load_asset(path)
    for key, value in settings.items():
        texture.set_editor_property(key, value)
    return texture


def textures(folder):
    """The fitted textures under folder, by object path, that now need virtual sampling."""
    virtual = set()
    for asset in unreal.EditorAssetLibrary.list_assets(folder, recursive=True):
        texture = unreal.load_asset(asset)
        if not isinstance(texture, unreal.Texture2D):
            continue
        before = size(texture)
        if before > MAX:
            texture = downscale(texture)
            print(f"{texture.get_name()}: {before} -> {size(texture)}")
        if size(texture) > VT_ABOVE:
            texture.set_editor_property("virtual_texture_streaming", True)
            virtual.add(texture.get_path_name())
        unreal.EditorAssetLibrary.save_loaded_asset(texture, True)
    return virtual


def samplers(folder, virtual):
    """Switch every sample of a virtual texture under folder to the virtual sampler type; returns assets changed."""
    changed = 0
    for asset in unreal.EditorAssetLibrary.list_assets(folder, recursive=True):
        owner = unreal.load_asset(asset)
        if isinstance(owner, unreal.Material):
            expressions = mel.get_material_expressions(owner)
        elif isinstance(owner, unreal.MaterialFunction):
            expressions = mel.get_material_function_expressions(owner)
        else:
            continue
        edits = 0
        for expression in expressions:
            if not isinstance(expression, unreal.MaterialExpressionTextureSample):
                continue
            texture = expression.get_editor_property("texture")
            kind = expression.get_editor_property("sampler_type")
            if texture and texture.get_path_name() in virtual and kind in VIRTUAL:
                expression.set_editor_property("sampler_type", VIRTUAL[kind])
                edits += 1
        if edits:
            if isinstance(owner, unreal.Material):
                mel.recompile_material(owner)
            else:
                mel.update_material_function(owner)
            unreal.EditorAssetLibrary.save_loaded_asset(owner, False)
            print(f"{owner.get_name()}: {edits} virtual sampler(s)")
            changed += 1
    return changed


if len(sys.argv) < 3:
    raise SystemExit(__doc__)
virtual = textures(sys.argv[1])
print(f"{len(virtual)} virtual textures; {sum(samplers(folder, virtual) for folder in sys.argv[2:])} materials updated")
