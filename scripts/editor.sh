#!/usr/bin/env bash
# Editor lifecycle for the lead. See AGENTS.md "Code changes".
#   editor.sh open [editor args...]  launch with MCP on 8000; returns once MCP listens and L_vilm is fully loaded
#   editor.sh close                  save dirty packages (stops if that fails), quit, force-quit if a dialog still holds it; returns once 8000 is free
#   editor.sh kill                   force-quit a hung editor (unsaved work is lost); returns once 8000 is free
#   editor.sh build                  full build; the editor must be closed
#   editor.sh hot                    hot reload build; .cpp function bodies only, editor open
#   editor.sh restart                close, build, open
set -euo pipefail

UE_ROOT=${UE_ROOT:-"/Users/Shared/Epic Games/UE_5.8"}
UPROJECT="$(cd "$(dirname "$0")/.." && pwd)/Forest/Forest.uproject"
PORT=8000

running() { pgrep -f "UnrealEditor.*$UPROJECT" >/dev/null; }
LOG="$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log"

listening() { lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null; }
# Any socket on the port, including TIME_WAIT (no owning process, so lsof misses it): Unreal's listener cannot bind until they clear.
port_busy() { netstat -an -p tcp | grep -q "[.:]$PORT "; }
bind_failed() { [[ "$LOG" -nt "$launched" ]] && grep -q "HttpListener unable to bind to 127.0.0.1:$PORT" "$LOG"; }
mcp_up() {
  bind_failed && { echo "MCP could not bind port $PORT; run editor.sh close, then open" >&2; exit 1; }
  listening
}

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
    wait_for 60 "port $PORT to free" eval '! port_busy'
    launched=$(mktemp); trap 'rm -f "$launched"' EXIT
    # Packages left by an earlier forced exit raise a restore prompt at startup whatever bAutoSaveEnable says
    # (PackageAutoSaver reads this file on its own), and the prompt blocks MCP and editor-py until clicked. Move it
    # aside, not away: the autosave packages and their mapping stay for a manual restore.
    restore="$(dirname "$UPROJECT")/Saved/Autosaves/PackageRestoreData.json"
    [[ -f "$restore" ]] && mv -f "$restore" "$(mktemp "$restore.XXXXXX")"  # mktemp: a name no earlier backup has
    open -n -a "$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app" --args "$UPROJECT" \
      -ModelContextProtocolStartServer -ModelContextProtocolPort=$PORT "$@"
    wait_for 900 "MCP on port $PORT" mcp_up
    echo "MCP up at http://127.0.0.1:$PORT/mcp"
    # A fresh editor loads no World Partition cells; load them all and set morning light (review/view_ready.py).
    "$(dirname "$0")/editor-py" "$(dirname "$0")/review/view_ready.py" ||
      { echo "editor is open, but loading L_vilm's cells failed (see above)" >&2; exit 1; }
    ;;
  close)
    running || exit 0
    # Save first, so quitting never stops on Unreal's unsaved-changes dialog: a modal blocks MCP and editor-py, and
    # the lead closes the editor unattended. The same request closes the queue (init_unreal.py), so nothing queued
    # after it can write before the quit. It refuses, leaving the editor open, when a regeneration is still running
    # (it writes through its own callbacks, not the queue; regenerate_biome.ACTIVE) or when it runs after this
    # shell stopped waiting for it, so a late request cannot close the queue with no quit to follow. A failed save
    # also stops here: use kill only when losing unsaved work is acceptable.
    deadline=$(($(date +%s) + 240))  # before the 300 s editor-py timeout, leaving the save a minute
    printf '%s\n' 'import builtins, os, time' \
      "if time.time() > $deadline: raise SystemExit('close request ran after its caller gave up')" \
      'if getattr(builtins, "_forest_biome_regeneration", None): raise SystemExit("a regeneration is still running")' \
      'if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True): raise SystemExit("not saved")' \
      'open(os.path.join(unreal.Paths.project_saved_dir(), "EditorPy", "closing"), "w").close()' |
      EDITOR_PY_TIMEOUT=300 "$(dirname "$0")/editor-py" - ||
      { echo "could not save and close the queue; editor left open (editor.sh kill discards unsaved work)" >&2; exit 1; }
    # Everything is saved and the queue is closed, so a dialog that still holds the editor (or a quit request it
    # cannot answer) is force-quit below without losing work.
    osascript -e 'quit app "UnrealEditor"' || true
    if ! wait_for 120 "the editor to quit" eval '! running'; then
      echo "force-quitting: a dialog still holds the editor after the save" >&2
      pkill -9 -f "UnrealEditor.*$UPROJECT" || true
      wait_for 30 "the editor to exit" eval '! running'
    fi
    wait_for 60 "port $PORT to free" eval '! port_busy'
    ;;
  kill)
    pkill -9 -f "UnrealEditor.*$UPROJECT" || true
    wait_for 30 "the editor to exit" eval '! running'
    wait_for 60 "port $PORT to free" eval '! port_busy'
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
    sed -n '2,8p' "$0" >&2
    exit 2
    ;;
esac
