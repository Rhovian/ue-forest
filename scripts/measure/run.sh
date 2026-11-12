#!/usr/bin/env bash
# Measure one Megaplants Beech tree: run.sh <A|B|C|D> <count>
# Measure a level along a fixed walking route: run.sh level <map>
# Opens the editor on baseline.py, waits for it to quit, then prints the summary.
# Variants of a level run, for comparing against the plain one (all optional, recorded in manifest.json):
#   MEASURE_LABEL=nograss   suffix for the run directory
#   MEASURE_POINTS=interior,beach   only these route points
#   MEASURE_CMDS=$'r.ScreenPercentage 50\nShowFlag.InstancedGrass 0'   console commands, run once PIE is up
#   MEASURE_HIDE=Fern,Moss   hide instanced meshes, static and skinned, whose asset path contains one of these
#   MEASURE_TRACE=0   no Unreal Insights trace (about 300 MB a run)
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
out="$here/../../Forest/Saved/Measure/$(date +%Y%m%dT%H%M%S)-$label${MEASURE_LABEL:+-$MEASURE_LABEL}"
mkdir -p "$out"
out=$(cd "$out" && pwd)
[[ -z "${MEASURE_CMDS:-}" ]] || printf '%s\n' "$MEASURE_CMDS" > "$out/commands.txt"
[[ -z "${MEASURE_POINTS:-}" ]] || measure_args+=(-MeasurePoints="$MEASURE_POINTS")
[[ -z "${MEASURE_HIDE:-}" ]] || measure_args+=(-MeasureHide="$MEASURE_HIDE")
trace_args=(-trace=cpu,frame,gpu,bookmark,loadtime,file -tracefile="$out/trace.utrace")
[[ "${MEASURE_TRACE:-1}" != 0 ]] || trace_args=()

# An aborted run leaves a dirty template map; kill rather than face the save prompt.
trap 'pkill -9 -f "UnrealEditor.*Forest.uproject"' INT TERM
"$here/../editor.sh" open -ExecCmds="py $here/baseline.py" \
  "${measure_args[@]}" -MeasureOut="$out" ${trace_args[@]+"${trace_args[@]}"} || {
  # baseline.py quits on a bad argument, which can be before MCP is up; say why, not only that the editor exited.
  [[ ! -f "$out/error.txt" ]] || cat "$out/error.txt" >&2
  exit 1
}
deadline=$((SECONDS + 1800))
while pgrep -f "UnrealEditor.*Forest.uproject" >/dev/null; do
  if (( SECONDS >= deadline )); then
    echo "timed out after 1800s waiting for measurement editor to quit" >&2; exit 1
  fi
  sleep 2
done
cp "$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log" "$out/editor.log"  # rhi.DumpMemory output
if [[ -f "$out/error.txt" ]]; then cat "$out/error.txt" >&2; exit 1; fi
python3 "$here/summarize.py" "$out"
