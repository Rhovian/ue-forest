#!/usr/bin/env bash
# Measure one Megaplants Beech tree: run.sh <A|B|C|D> <count>
# Measure a level along a fixed walking route: run.sh level <map>
# Opens the editor on baseline.py, waits for it to quit, then prints the summary.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
tree=${1:?tree A-D}
count=${2:?instance count}
if [[ "$tree" == level ]]; then
  measure_args=(-MeasureMap="$count")
  label="level-${count##*/}"
else
  measure_args=(-MeasureTree="$tree" -MeasureCount="$count")
  label="$tree-$count"
fi
out="$here/../../Forest/Saved/Measure/$(date +%Y%m%dT%H%M%S)-$label"
mkdir -p "$out"
out=$(cd "$out" && pwd)

# An aborted run leaves a dirty template map; kill rather than face the save prompt.
trap 'pkill -9 -f "UnrealEditor.*Forest.uproject"' INT TERM
# The editor throttles itself when it is not the foreground app, and the PIE window then measured empty frames
# (0.4 ms GPU) at the route's first points; this override is for this run only, not saved.
"$here/../editor.sh" open -ExecCmds="py $here/baseline.py" \
  -ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False \
  "${measure_args[@]}" -MeasureOut="$out" \
  -trace=cpu,frame,gpu,bookmark,loadtime,file -tracefile="$out/trace.utrace"
while pgrep -f "UnrealEditor.*Forest.uproject" >/dev/null; do sleep 2; done
cp "$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log" "$out/editor.log"  # rhi.DumpMemory output
python3 "$here/summarize.py" "$out"
