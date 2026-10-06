#!/usr/bin/env bash
# Measure one Megaplants Beech tree: run.sh <A|B|C|D> <count>
# Opens the editor on baseline.py, waits for it to quit, then prints the summary.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
tree=${1:?tree A-D}
count=${2:?instance count}
out="$here/../../MyProject/Saved/Measure/$(date +%Y%m%dT%H%M%S)-$tree-$count"
mkdir -p "$out"
out=$(cd "$out" && pwd)

"$here/../editor.sh" open -ExecCmds="py $here/baseline.py" \
  -MeasureTree="$tree" -MeasureCount="$count" -MeasureOut="$out" \
  -trace=cpu,frame,gpu,bookmark,loadtime,file -tracefile="$out/trace.utrace"
while pgrep -f "UnrealEditor.*MyProject.uproject" >/dev/null; do sleep 2; done
python3 "$here/summarize.py" "$out"
