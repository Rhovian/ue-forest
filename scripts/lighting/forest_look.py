"""Exposure for the forest read (#35): one unbound post-process volume on L_vilm.

    scripts/editor-py scripts/lighting/forest_look.py

Auto exposure stays on; its bias darkens the frame one stop so sunlit floor and bark stop blowing out while the
shade stays readable, and from the forest edge the sea and the dark foreground both read (edge_out_01). Saves only
the volume's actor package: the sun's time-of-day rotation and other unsaved level edits are left alone.
"""

import unreal

LABEL = "PP_ForestLook"
SETTINGS = {  # PostProcessSettings property -> value; each one is overridden on the volume
    "auto_exposure_bias": -1.0,
}

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
if not unreal.EditorLoadingAndSavingUtils.save_packages([volume.get_package()], False):
    raise RuntimeError(f"could not save {LABEL}")
print(f"{LABEL}: {SETTINGS}")
