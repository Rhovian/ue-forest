#!/usr/bin/env bash
# Measure one Megaplants Beech tree: run.sh <A|B|C|D> <count>
# Opens the editor on baseline.py, waits for it to quit, then prints the summary.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
tree=${1:?tree A-D}
count=${2:?instance count}
out="$here/../../Forest/Saved/Measure/$(date +%Y%m%dT%H%M%S)-$tree-$count"
mkdir -p "$out"
out=$(cd "$out" && pwd)

# An aborted run leaves a dirty template map; kill rather than face the save prompt.
trap 'pkill -9 -f "UnrealEditor.*Forest.uproject"' INT TERM
"$here/../editor.sh" open -ExecCmds="py $here/baseline.py" \
  -MeasureTree="$tree" -MeasureCount="$count" -MeasureOut="$out" \
  -trace=cpu,frame,gpu,bookmark,loadtime,file -tracefile="$out/trace.utrace"
while pgrep -f "UnrealEditor.*Forest.uproject" >/dev/null; do sleep 2; done
cp "$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log" "$out/editor.log"  # rhi.DumpMemory output
python3 "$here/summarize.py" "$out"
