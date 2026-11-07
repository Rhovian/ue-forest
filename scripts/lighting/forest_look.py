"""Exposure, mist and bark tone for the forest read (#35) on L_vilm.

    scripts/editor-py scripts/lighting/forest_look.py

Auto exposure stays on; its bias darkens the frame one stop so sunlit floor and bark stop blowing out while the
shade stays readable, and from the forest edge the sea and the dark foreground both read (edge_out_01). The height
fog starts 15 m out, so the near view stays clear and mist lies between the far trunks (interior_01), and it thins
with height so the sea from the edge stays bright. Beech bark is mid-grey, not near-white (interior_01 Ignore).
Saves only the volume's and the fog's actor packages and the bark instance: the sun's time-of-day rotation and
other unsaved level edits are left alone.
"""

import unreal

LABEL = "PP_ForestLook"
SETTINGS = {  # PostProcessSettings property -> value; each one is overridden on the volume
    "auto_exposure_bias": -1.0,
}
FOG = {  # ExponentialHeightFogComponent property -> value
    "fog_density": 0.03,
    "fog_height_falloff": 0.12,
    "start_distance": 1500.0,  # cm
    "fog_inscattering_luminance": unreal.LinearColor(0.35, 0.45, 0.5, 1),  # cool grey-green mist
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
bark = unreal.load_asset(BARK)
unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(bark, "BaseColor Tint", BARK_TINT)
unreal.MaterialEditingLibrary.update_material_instance(bark)
if not unreal.EditorLoadingAndSavingUtils.save_packages([volume.get_package(), fogs[0].get_package()], False):
    raise RuntimeError(f"could not save {LABEL} or the height fog")
if not unreal.EditorAssetLibrary.save_loaded_asset(bark, False):
    raise RuntimeError(f"could not save {BARK}")
print(f"{LABEL}: {SETTINGS}; fog: {FOG}; bark tint {BARK_TINT}")
