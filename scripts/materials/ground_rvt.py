"""Set up the forest floor's runtime virtual textures, so rocks, slabs and ground scans can blend into it (#135, #166).

    scripts/editor-py scripts/materials/ground_rvt.py

Rocks and scans sat on the landscape with hard rims (rock_assembly, operator 2026-11-09): nothing under them knew the
ground. This builds T_ForestHeightRVT (the landscape's world height) and a volume fitted to the landscape, with every
landscape proxy rendering into it; forest_floor.py writes the height and moss_coating.py's MF_GroundBlend reads it to
know how far a rock's surface is above the floor. Only the height: a material that writes a runtime virtual texture
cannot sample virtual-streamed textures, and the floor samples the Electric Dreams surfaces, so writing its colour
failed to compile on every landscape component (#157). The blend samples those surfaces itself. Rerun after the
landscape's extent changes.
"""

import unreal

FOLDER = "/Game/ForestBiome/RVT"
Kind = unreal.RuntimeVirtualTextureMaterialType
TEXTURES = {  # asset -> (contents, tile count): the 3 km landscape over 64 tiles of 256 px is about 18 cm per texel
    "T_ForestHeightRVT": (Kind.WORLD_HEIGHT, 64),
}
LABEL = "ForestRVTVolume_"


def texture(name, kind, tiles):
    path = f"{FOLDER}/{name}"
    asset = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if asset is None:
        asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, FOLDER, unreal.RuntimeVirtualTexture, unreal.RuntimeVirtualTextureFactory())
    asset.set_editor_property("material_type", kind)
    asset.set_editor_property("tile_count", tiles)
    asset.set_editor_property("tile_size", 256)
    unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
    return asset


def main():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [a for a in actors.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
    if not landscapes:
        raise SystemExit("no landscape in the open level")
    lows, highs = zip(*[(origin - extent, origin + extent) for origin, extent in (a.get_actor_bounds(False)
                                                                                  for a in landscapes)])
    low = unreal.Vector(min(v.x for v in lows), min(v.y for v in lows), min(v.z for v in lows) - 100)
    high = unreal.Vector(max(v.x for v in highs), max(v.y for v in highs), max(v.z for v in highs) + 100)
    rvts = [texture(name, kind, tiles) for name, (kind, tiles) in TEXTURES.items()]
    old = [a for a in actors.get_all_level_actors() if a.get_actor_label().startswith(LABEL)]
    gone = [a.get_outermost() for a in old]  # saving a destroyed external actor's package deletes its file
    for actor in old:
        actors.destroy_actor(actor)
    for rvt in rvts:
        # The volume's box is the unit cube from its pivot, scaled by the actor: pivot at the low corner.
        volume = actors.spawn_actor_from_class(unreal.RuntimeVirtualTextureVolume, low)
        volume.set_actor_label(LABEL + rvt.get_name())
        volume.set_actor_scale3d(high - low)
        volume.get_component_by_class(unreal.RuntimeVirtualTextureComponent).set_editor_property("virtual_texture", rvt)
    for proxy in landscapes:
        proxy.set_editor_property("runtime_virtual_textures", rvts)
    volumes = [a for a in actors.get_all_level_actors() if a.get_actor_label().startswith(LABEL)]
    if not unreal.EditorLoadingAndSavingUtils.save_packages([a.get_outermost() for a in landscapes + volumes] + gone,
                                                            True):
        raise SystemExit("could not save the landscape and volume actors")
    print(f"{len(rvts)} RVTs over {len(landscapes)} landscape proxies, {(high.x - low.x) / 100:.0f} x "
          f"{(high.y - low.y) / 100:.0f} m")


if __name__ == "__main__":
    main()
