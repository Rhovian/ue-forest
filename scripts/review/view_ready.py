"""Runs in the editor via scripts/editor-py when scripts/editor.sh opens it: on L_vilm, loads every World Partition
actor and sets the review views' morning light, so the opened level looks complete (a fresh editor loads no cells:
the island is missing and the mist patches float over nothing). Loading and Forest.Time change no files."""
# editor-py: fresh-siblings
import unreal
from poses import TIME_OF_DAY

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world is None:  # scripts/measure/run.sh opens the editor on its own map load: no world yet, and none to prepare
    print("no editor world yet; nothing loaded")
elif world.get_path_name() == "/Game/L_vilm.L_vilm":
    partition = unreal.WorldPartitionBlueprintLibrary
    descriptors = partition.get_actor_descs()
    partition.load_actors([desc.guid for desc in descriptors])
    unreal.SystemLibrary.execute_console_command(world, f"Forest.Time {TIME_OF_DAY}")
    print(f"L_vilm: {len(descriptors)} actors loaded, Forest.Time {TIME_OF_DAY}")
else:
    print(f"{world.get_path_name()}: not L_vilm; nothing loaded")
