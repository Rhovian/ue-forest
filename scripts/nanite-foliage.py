"""Make static foliage meshes meet the Asset Budget's Nanite rule (docs/asset-budget.md).

    scripts/editor-py scripts/nanite-foliage.py <mesh or folder>...

Enables Nanite with Voxelize shape preservation on every StaticMesh given, or under each folder given, and saves
the meshes that changed. Re-running is safe.
"""

import sys

import unreal

paths = []
for arg in sys.argv[1:]:
    if unreal.EditorAssetLibrary.does_directory_exist(arg):
        paths += [p.split(".")[0] for p in unreal.EditorAssetLibrary.list_assets(arg, recursive=True)]
    else:
        paths.append(arg)
for path in paths:
    mesh = unreal.load_asset(path)
    if not isinstance(mesh, unreal.StaticMesh):
        continue
    settings = mesh.get_editor_property("nanite_settings")
    if not settings.enabled or settings.shape_preservation != unreal.NaniteShapePreservation.VOXELIZE:
        settings.set_editor_property("enabled", True)
        settings.set_editor_property("shape_preservation", unreal.NaniteShapePreservation.VOXELIZE)
        mesh.set_editor_property("nanite_settings", settings)
        print(f"Nanite Voxelize: {path}")
    # Always save if dirty, so a rerun after a failed save still writes the settings.
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, True):
        raise SystemExit(f"could not save {path}; its Nanite settings changed only in memory")
