"""Runs in the editor via scripts/editor-py before each capture: switches the level viewport to game view, puts its
camera at the pose and runs every particle system 10 s ahead.

    scripts/editor-py scripts/review/warm.py '{"x": ..., "y": ..., "z": ..., "pitch": ..., "yaw": ...}'

The editor viewport does not tick particles between captures, so the wisps and motes (#40) would be empty; and their
distance culling measures from the last rendered view (NiagaraWorldManager), so the camera must be at the pose first.
"""

import json
import sys

import unreal

camera = json.loads(sys.argv[1])
# Game view, so the capture carries no spline lines, volume bounds or gizmo: a freshly opened editor is not in it, and
# the capture otherwise showed whatever the viewport was left in (#194). It is left on; the lead's editor is for captures.
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_game_view(True)
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
    unreal.Vector(camera["x"], camera["y"], camera["z"]), unreal.Rotator(pitch=camera["pitch"], yaw=camera["yaw"], roll=0)
)
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    for component in actor.get_components_by_class(unreal.NiagaraComponent):
        component.activate(True)
        component.advance_simulation(300, 1 / 30)
