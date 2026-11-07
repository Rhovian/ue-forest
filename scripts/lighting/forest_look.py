"""Exposure, grade, mist and bark tone for the forest read (#35) on L_vilm.

    scripts/editor-py scripts/lighting/forest_look.py

Auto exposure stays on; its bias darkens the frame one stop so sunlit floor and bark stop blowing out while the
shade stays readable, and from the forest edge the sea and the dark foreground both read (edge_out_01). A light
height fog starting 15 m out separates the far trunks (interior_01); the mist itself lies in drifting patches over
low ground, not a blanket (high_point_01): local fog volumes on part of the ground below 7 m, i.e. the lake basin,
the lower stream and the coast. Beech bark is mid-grey, not near-white (interior_01 Ignore).
Saves only the volume's and the fog's actor packages, the mist actors and the bark instance: the sun's time-of-day
rotation and other unsaved level edits are left alone.
"""

import random

import unreal

LABEL = "PP_ForestLook"
SETTINGS = {  # PostProcessSettings property -> value; each one is overridden on the volume
    "auto_exposure_bias": -1.0,
    # Grade toward interior_01's cool, rich greens: a slightly cooler white balance, more green saturation, a faint
    # blue lift in the shadows. Sea and shade on the edge stay readable (edge_out_01). In the default White Balance
    # mode the temperature names the light being corrected for, so a value below 6500 K cools the image
    # (TonemapCommon.ush; #59 review).
    "white_temp": 6100.0,
    "color_saturation": unreal.Vector4(0.95, 1.12, 0.97, 1.0),
    "color_gain_shadows": unreal.Vector4(0.96, 1.0, 1.04, 1.0),
}
FOG = {  # ExponentialHeightFogComponent property -> value
    "fog_density": 0.02,
    "fog_height_falloff": 0.2,
    "start_distance": 1500.0,  # cm
    "fog_inscattering_luminance": unreal.LinearColor(0.35, 0.45, 0.5, 1),  # cool grey-green mist
}
MIST = "Mist"  # label prefix and outliner folder of the patches
MIST_BELOW = 700  # cm above the sea: low ground (lake surface 5.9 m)
MIST_CELL = 4000  # cm grid over the island (x 0..1100 m, y -1000..0 m)
MIST_SHARE = 0.45  # of low cells that get a patch, so patches drift apart rather than join into a sheet
MIST_RADIUS = 2500  # cm
MIST_BASE = 500  # cm: a LocalFogVolume's radius at scale 1 (LocalFogVolumeComponent.h GetBaseVolumeSize)
MIST_FOG = {  # LocalFogVolumeComponent property -> value
    "radial_fog_extinction": 0.15,
    "height_fog_extinction": 0.6,
    "fog_albedo": unreal.LinearColor(0.8, 0.9, 0.95, 1),
}
BARK = "/Game/Megaplant_Library/Tree_European_Beech/Materials/MI_European_Beech_Bark_01"
BARK_TINT = unreal.LinearColor(0.284, 0.294, 0.3, 1)  # stock tint (0.473, 0.490, 0.5) scaled to 0.6

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name() != "/Game/L_vilm.L_vilm":
    raise RuntimeError("Open L_vilm in the editor (not PIE) before running")
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for probe in [a for a in actors if a.get_actor_label() == "TMP_ExposureProbe"]:  # left by manual look tests
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(probe)
volume = next((a for a in actors if a.get_actor_label() == LABEL), None)
if volume is None:
    volume = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.PostProcessVolume, unreal.Vector(0, 0, 0)
    )
    volume.set_actor_label(LABEL)
volume.set_editor_property("unbound", True)
settings = unreal.PostProcessSettings()
for name, value in SETTINGS.items():
    settings.set_editor_property("override_" + name, True)
    settings.set_editor_property(name, value)
volume.set_editor_property("settings", settings)
fogs = [a for a in actors if isinstance(a, unreal.ExponentialHeightFog)]
if len(fogs) != 1:
    raise RuntimeError(f"expected one ExponentialHeightFog on L_vilm, found {len(fogs)}")
component = fogs[0].get_component_by_class(unreal.ExponentialHeightFogComponent)
for name, value in FOG.items():
    component.set_editor_property(name, value)

def ground(x, y):
    """Landscape height at (x, y), ignoring anything else the ray meets; None off the landscape."""
    start, end, ignored = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000), []
    for _ in range(64):
        hit = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, unreal.DrawDebugTrace.NONE, True
        )
        if hit is None:
            return None
        fields = hit.to_tuple()
        if isinstance(fields[9], unreal.LandscapeProxy):
            return fields[4].z
        ignored.append(fields[9])
    return None


subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
# Every World Partition cell must be loaded, or traces over unloaded landscape miss and the rebuilt patch set
# silently shrinks (WorldPartitionBlueprintLibrary.LoadActors keeps them loaded; see deadwood_rocks.py).
descriptors = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in descriptors])
actors = subsystem.get_all_level_actors()
# A rerun updates patches in place by label and destroys only those no longer placed; saving a destroyed actor's
# external package deletes its file.
old = {a.get_actor_label(): a for a in actors if a.get_actor_label().startswith(MIST + "_")}
mist = []
for i in range(110000 // MIST_CELL + 1):
    for j in range(100000 // MIST_CELL + 1):
        x, y = i * MIST_CELL, -j * MIST_CELL
        z = ground(x, y)
        if z is None and 15000 < x < 100000 and -95000 < y < -10000:
            raise RuntimeError(f"no landscape under ({x / 100:.0f}, {y / 100:.0f}) m inside the island; are all cells loaded?")
        # 30 cm keeps patches off the sea floor; the seeded draw keeps the pattern fixed between runs.
        if z is None or not 30 < z < MIST_BELOW or random.Random(f"{i},{j}").random() >= MIST_SHARE:
            continue
        label = f"{MIST}_{i:02d}_{j:02d}"
        patch = old.pop(label, None) or subsystem.spawn_actor_from_class(unreal.LocalFogVolume, unreal.Vector(x, y, z))
        patch.set_actor_location(unreal.Vector(x, y, z), False, False)
        patch.set_actor_label(label)
        patch.set_folder_path(MIST)
        patch.set_actor_scale3d(unreal.Vector(1, 1, 1) * (MIST_RADIUS / MIST_BASE))
        component = patch.get_component_by_class(unreal.LocalFogVolumeComponent)
        for name, value in MIST_FOG.items():
            component.set_editor_property(name, value)
        mist.append(patch)
packages = [a.get_package() for a in old.values()]
for actor in old.values():
    subsystem.destroy_actor(actor)
bark = unreal.load_asset(BARK)
# SetMaterialInstanceVectorParameterValue already updates the instance (MaterialEditingLibrary.cpp).
unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(bark, "BaseColor Tint", BARK_TINT)
packages += [volume.get_package(), fogs[0].get_package()] + [patch.get_package() for patch in mist]
if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, False):
    raise RuntimeError(f"could not save {LABEL}, the height fog or the mist patches")
if not unreal.EditorAssetLibrary.save_loaded_asset(bark, False):
    raise RuntimeError(f"could not save {BARK}")
print(f"{LABEL}: {SETTINGS}; fog: {FOG}; {len(mist)} mist patches; bark tint {BARK_TINT}")
