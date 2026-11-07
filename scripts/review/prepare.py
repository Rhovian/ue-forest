"""Runs in the editor via scripts/editor-py: loads every World Partition actor, sets morning light, and prints each pose's camera location (cm) as JSON. scripts/review/capture calls it."""
# editor-py: fresh-siblings
import json

import unreal
from poses import POSES, TIME_OF_DAY

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name() != "/Game/L_vilm.L_vilm":
    raise RuntimeError("Open L_vilm in the editor (not PIE) before capturing")
partition = unreal.WorldPartitionBlueprintLibrary
partition.load_actors([desc.guid for desc in partition.get_actor_descs()])
unreal.SystemLibrary.execute_console_command(world, f"Forest.Time {TIME_OF_DAY}")


def ground(x, y):
    """Landscape height: props that block the ray are ignored and the trace repeated, so placing one under a pose
    never moves its camera."""
    start, end, ignored = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000), []
    for _ in range(64):
        hit = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, unreal.DrawDebugTrace.NONE, True
        )
        if hit is None:
            break
        fields = hit.to_tuple()
        if isinstance(fields[9], unreal.LandscapeProxy):
            return fields[4].z
        ignored.append(fields[9])
    raise RuntimeError(f"no landscape under ({x / 100:.0f}, {y / 100:.0f}) m")


cameras = {}
for name, x, y, height, pitch, yaw in POSES:
    cameras[name] = {"x": x * 100, "y": y * 100, "z": ground(x * 100, y * 100) + height * 100, "pitch": pitch, "yaw": yaw}
print(json.dumps(cameras))
