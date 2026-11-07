"""Runs in the editor via scripts/editor-py: loads every World Partition actor, sets morning light, and prints each
pose's camera location (cm) as JSON. scripts/review/capture calls it."""
# editor-py: fresh-siblings
import json

import unreal
from poses import POSES, TIME_OF_DAY

partition = unreal.WorldPartitionBlueprintLibrary
partition.load_actors([desc.guid for desc in partition.get_actor_descs()])
world = unreal.UnrealEditorSubsystem().get_editor_world()
unreal.SystemLibrary.execute_console_command(world, f"Forest.Time {TIME_OF_DAY}")


def ground(x, y):
    start, end = unreal.Vector(x, y, 100000), unreal.Vector(x, y, -100000)
    hits = unreal.SystemLibrary.line_trace_multi(
        world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True
    )
    landscape = [h for h in hits or [] if isinstance(h.to_tuple()[9], unreal.LandscapeProxy)]
    return (landscape or hits)[0].to_tuple()[4].z if (landscape or hits) else 0.0


cameras = {}
for name, x, y, height, pitch, yaw in POSES:
    cameras[name] = {"x": x * 100, "y": y * 100, "z": ground(x * 100, y * 100) + height * 100, "pitch": pitch, "yaw": yaw}
print(json.dumps(cameras))
