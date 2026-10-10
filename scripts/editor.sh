#!/usr/bin/env bash
# Editor lifecycle for the lead. See AGENTS.md "Code changes".
#   editor.sh open [editor args...]  launch with MCP on 8000; returns once MCP listens
#   editor.sh close                  quit (Unreal prompts for unsaved assets); returns once 8000 is free
#   editor.sh build                  full build; the editor must be closed
#   editor.sh hot                    hot reload build; .cpp function bodies only, editor open
#   editor.sh restart                close, build, open
set -euo pipefail

UE_ROOT=${UE_ROOT:-"/Users/Shared/Epic Games/UE_5.8"}
UPROJECT="$(cd "$(dirname "$0")/.." && pwd)/Forest/Forest.uproject"
PORT=8000

running() { pgrep -f "UnrealEditor.*$UPROJECT" >/dev/null; }
listening() { lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null; }

# wait_for <seconds> <description> <command...>
wait_for() {
  local limit=$1 what=$2; shift 2
  for ((i = 0; i < limit; i++)); do "$@" && return 0; sleep 1; done
  echo "timed out after ${limit}s waiting for $what" >&2
  return 1
}

build() {
  "$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" ForestEditor Mac Development \
    -Project="$UPROJECT" -Architecture=arm64 "$@"
}

case ${1:-} in
  open)
    shift
    running && { echo "editor already running" >&2; exit 1; }
    wait_for 60 "port $PORT to free" eval '! listening'
    open -n -a "$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app" --args "$UPROJECT" \
      -ModelContextProtocolStartServer -ModelContextProtocolPort=$PORT "$@"
    wait_for 900 "MCP on port $PORT" listening
    echo "MCP up at http://127.0.0.1:$PORT/mcp"
    ;;
  close)
    running || exit 0
    osascript -e 'quit app "UnrealEditor"'
    wait_for 120 "the editor to quit (unsaved-changes dialog?)" eval '! running'
    wait_for 60 "port $PORT to free" eval '! listening'
    ;;
  build)
    running && { echo "close the editor first" >&2; exit 1; }
    build -NoHotReload
    ;;
  hot)
    running || { echo "hot reload needs the editor open" >&2; exit 1; }
    build
    ;;
  restart)
    "$0" close && "$0" build && "$0" open
    ;;
  *)
    sed -n '2,7p' "$0" >&2
    exit 2
    ;;
esac
