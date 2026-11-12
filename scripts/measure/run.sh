#!/usr/bin/env bash
# Measure one Megaplants Beech tree: run.sh <A|B|C|D> <count>
# Measure a level along a fixed walking route: run.sh level <map>
# Opens the editor on baseline.py, waits for it to quit, then prints the summary.
# Variants of a level run, for comparing against the plain one (all optional, recorded in manifest.json):
#   MEASURE_LABEL=nograss   suffix for the run directory
#   MEASURE_POINTS=interior,beach   only these route points, in this order
#   MEASURE_CMDS=$'r.ScreenPercentage 50\nShowFlag.InstancedGrass 0'   console commands, run once PIE is up
#   MEASURE_HIDE=Fern,Moss   hide instanced meshes, static and skinned, whose asset path contains one of these
#   MEASURE_SET='Fern:cast_shadow=False;/Tree_:shadow_cache_invalidation_behavior=STATIC'   set a property on the
#       instanced mesh components whose asset path contains the part before the colon
#   MEASURE_TRACE=0   no Unreal Insights trace (about 300 MB a run)
#   MEASURE_WALK=1   after each point, walk forward for 30 s and capture that as <point>_walk
#   MEASURE_SHOTS=1   a screenshot of the PIE view before and after each point's capture (<point>_a.png, _b.png)
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
# baseline.py splits the editor command line on whitespace, so a space in any of these would silently measure the
# plain run into another directory.
for name in MEASURE_LABEL MEASURE_POINTS MEASURE_HIDE MEASURE_SET; do
  if [[ "${!name:-}" =~ [[:space:]] ]]; then echo "$name must not contain whitespace: '${!name}'" >&2; exit 2; fi
done
# MEASURE_HIDE and MEASURE_SET are applied once, to what is loaded at the point; a walk streams in components they
# would not have reached, and the capture would mix the two.
if [[ "${MEASURE_WALK:-0}" == 1 && -n "${MEASURE_HIDE:-}${MEASURE_SET:-}" ]]; then
  echo "MEASURE_WALK cannot be combined with MEASURE_HIDE or MEASURE_SET" >&2; exit 2
fi
if [[ ! "${MEASURE_LABEL:-}" =~ ^[A-Za-z0-9_.-]*$ ]]; then
  echo "MEASURE_LABEL may hold only letters, digits, '_', '.' and '-': '$MEASURE_LABEL'" >&2; exit 2
fi
out="$here/../../Forest/Saved/Measure/$(date +%Y%m%dT%H%M%S)-$label${MEASURE_LABEL:+-$MEASURE_LABEL}"
mkdir -p "$out"
out=$(cd "$out" && pwd)
[[ -z "${MEASURE_CMDS:-}" ]] || printf '%s\n' "$MEASURE_CMDS" > "$out/commands.txt"
[[ -z "${MEASURE_POINTS:-}" ]] || measure_args+=(-MeasurePoints="$MEASURE_POINTS")
[[ -z "${MEASURE_HIDE:-}" ]] || measure_args+=(-MeasureHide="$MEASURE_HIDE")
[[ -z "${MEASURE_SET:-}" ]] || measure_args+=(-MeasureSet="$MEASURE_SET")
[[ "${MEASURE_SHOTS:-0}" != 1 ]] || measure_args+=(-MeasureShots)
[[ "${MEASURE_WALK:-0}" != 1 ]] || measure_args+=(-MeasureWalk)
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
