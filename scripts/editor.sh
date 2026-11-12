#!/usr/bin/env bash
# Editor lifecycle for the lead. See AGENTS.md "Code changes".
#   editor.sh open [editor args...]  launch with MCP on 8000; returns once MCP listens and L_vilm is fully loaded
#   editor.sh close                  save dirty packages (stops if that fails), quit, force-quit if a dialog still holds it; returns once 8000 is free
#   editor.sh kill                   force-quit a hung editor (unsaved work is lost); returns once 8000 is free
#   editor.sh build                  full build; the editor must be closed
#   editor.sh hot                    hot reload build; .cpp function bodies only, editor open
#   editor.sh status                 check process, port ownership, MCP and Python queue
#   editor.sh restart                close, build, open
set -euo pipefail

UE_ROOT=${UE_ROOT:-"/Users/Shared/Epic Games/UE_5.8"}
HERE="$(cd "$(dirname "$0")" && pwd)"
UPROJECT=${EDITOR_UPROJECT:-"$HERE/../Forest/Forest.uproject"}
UPROJECT="$(cd "$(dirname "$UPROJECT")" && pwd)/$(basename "$UPROJECT")"
PORT=${EDITOR_PORT:-8000}
export EDITOR_MCP_URL="http://127.0.0.1:$PORT/mcp"

editor_pids() { pgrep -f "UnrealEditor.*$UPROJECT" || true; }
running() { [[ -n "$(editor_pids)" ]]; }
LOG=${EDITOR_LOG:-"$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log"}

# lsof sees sockets inherited by CrashReportClient; netstat alone missed these (#190).
command -v lsof >/dev/null || { echo "lsof is required to inspect port $PORT" >&2; exit 1; }
holders() { { lsof -nP -iTCP:$PORT -sTCP:LISTEN -t || true; } | sort -u; }
port_free() {
  local pids; pids=$(holders)
  [[ -z "$pids" ]] && return 0
  echo "port $PORT held by:" >&2
  ps -p "$(echo "$pids" | paste -sd , -)" -o pid=,comm= >&2
  return 1
}
cleanup_crash_reporters() {
  local pid parent command executable project_name=${UPROJECT##*/}
  project_name=${project_name%.uproject}
  while read -r pid parent command; do
    # macOS uses a bare executable name and a shared engine crash directory (#190).
    # Require this project's folder name, executable identity and orphanhood.
    if [[ "$parent" == 1 && (
          "$command" == *"$HOME/Library/Application Support/Epic/UnrealEngine/"*"/Saved/Crashes/CrashReport-UE-$project_name-pid-"* ||
          "$command" == *"$(dirname "$UPROJECT")/Saved/Crashes/"* ) ]]; then
      executable=$(ps -p "$pid" -o comm=)
      [[ "${executable##*/}" == CrashReportClient ]] || continue
      echo "stopping orphaned CrashReportClient pid $pid: $command"
      kill -9 "$pid"
    fi
  done < <(ps -ww -axo pid=,ppid=,command=)
}
bind_failed() { [[ -f "$LOG" ]] && grep -q "HttpListener unable to bind to 127.0.0.1:$PORT" "$LOG"; }
owned_listener() {
  local pids; pids=$(holders)
  [[ -n "$pids" && "$pids" == "$editor_pid" ]]
}
# subprocess.run's timeout kills and reaps the child (Python 3 subprocess docs); no custom watchdog.
bounded() {
  python3 - "$@" <<'PYTHON'
import subprocess, sys
try:
    sys.exit(subprocess.run(sys.argv[2:], timeout=float(sys.argv[1]), check=False).returncode)
except subprocess.TimeoutExpired:
    sys.exit(f"timed out after {sys.argv[1]}s waiting for {sys.argv[2:]}")
PYTHON
}
mcp_probe() {
  local budget=$(( ${deadline:-$((SECONDS + 6))} - SECONDS ))
  (( budget > 0 )) || return 1
  (( budget <= 6 )) || budget=6
  EDITOR_MCP_TIMEOUT=2 bounded "$budget" "$HERE/editor-mcp"
}
mcp_up() {
  bind_failed && { echo "fresh editor log $LOG: MCP could not bind port $PORT" >&2; exit 1; }
  kill -0 "$editor_pid" 2>/dev/null || { echo "launched editor pid $editor_pid exited; see $LOG" >&2; exit 1; }
  if [[ -n "$(holders)" ]] && ! owned_listener; then
    echo "listener is not owned exclusively by launched editor pid $editor_pid" >&2
    port_free; exit 1
  fi
  [[ -f "$LOG" ]] && owned_listener && mcp_probe && owned_listener && ! bind_failed
}

# wait_for <seconds> <description> <command...>
wait_for() {
  local limit=$1 what=$2; shift 2
  local deadline=$((SECONDS + limit))
  while (( SECONDS < deadline )); do "$@" && return 0; sleep 1; done
  echo "timed out after ${limit}s waiting for $what" >&2
  return 1
}

build() {
  bounded 3600 "$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" ForestEditor Mac Development \
    -Project="$UPROJECT" -Architecture=arm64 "$@"
}

case ${1:-} in
  open)
    shift
    running && { echo "editor already running" >&2; exit 1; }
    cleanup_crash_reporters
    port_free
    # Preserve yesterday's errors; a new file proves this launch wrote the log (mtime can share a second).
    [[ ! -f "$LOG" ]] || mv "$LOG" "$(mktemp "$LOG.XXXXXX")"
    # Packages left by an earlier forced exit raise a restore prompt at startup whatever bAutoSaveEnable says
    # (PackageAutoSaver reads this file on its own), and the prompt blocks MCP and editor-py until clicked. Move it
    # aside, not away: the autosave packages and their mapping stay for a manual restore.
    restore="$(dirname "$UPROJECT")/Saved/Autosaves/PackageRestoreData.json"
    [[ -f "$restore" ]] && mv -f "$restore" "$(mktemp "$restore.XXXXXX")"  # mktemp: a name no earlier backup has
    # Popen(start_new_session=True) supplies setsid; no custom fork/detach mechanism.
    # https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    editor_pid=$(python3 - "${EDITOR_LAUNCH:-$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor}" \
      "$UPROJECT" -ModelContextProtocolStartServer -ModelContextProtocolPort=$PORT "$@" <<'PYTHON'
import signal, subprocess, sys
signal.signal(signal.SIGHUP, signal.SIG_IGN)  # inherited across exec; caller shutdown cannot hang up the editor
print(subprocess.Popen(sys.argv[1:], start_new_session=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid)
PYTHON
    )
    wait_for "${EDITOR_OPEN_TIMEOUT:-900}" "MCP owned by pid $editor_pid on port $PORT (log: $LOG)" mcp_up
    echo "MCP up at http://127.0.0.1:$PORT/mcp"
    # A fresh editor loads no World Partition cells; load them all and set morning light (review/view_ready.py).
    "$(dirname "$0")/editor-py" "$(dirname "$0")/review/view_ready.py" ||
      { echo "editor is open, but loading L_vilm's cells failed (see above)" >&2; exit 1; }
    ;;
  close)
    if ! running; then cleanup_crash_reporters; port_free; exit; fi
    # Save first, so quitting never stops on Unreal's unsaved-changes dialog: a modal blocks MCP and editor-py, and
    # the lead closes the editor unattended. The same request closes the queue (init_unreal.py), so nothing queued
    # after it can write before the quit. It refuses, leaving the editor open, when a regeneration is still running
    # (it writes through its own callbacks, not the queue; regenerate_biome.ACTIVE) or when it runs after this
    # shell stopped waiting for it, so a late request cannot close the queue with no quit to follow. A failed save
    # also stops here: use kill only when losing unsaved work is acceptable.
    deadline=$(($(date +%s) + 240))  # start by 240 s and mark closed by 295 s, inside editor-py's 300 s wait
    printf '%s\n' 'import builtins, os, time' \
      "if time.time() > $deadline: raise SystemExit('close request ran after its caller gave up')" \
      'if getattr(builtins, "_forest_biome_regeneration", None): raise SystemExit("a regeneration is still running")' \
      'if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True): raise SystemExit("not saved")' \
      "if time.time() > $((deadline + 55)): raise SystemExit('saved, but too late to close the queue for this caller')" \
      'open(os.path.join(unreal.Paths.project_saved_dir(), "EditorPy", "closing"), "w").close()' |
      EDITOR_PY_TIMEOUT=300 "$(dirname "$0")/editor-py" - ||
      { echo "could not save and close the queue; editor left open (editor.sh kill discards unsaved work)" >&2; exit 1; }
    # Everything is saved and the queue is closed, so a dialog that still holds the editor (or a quit request it
    # cannot answer) is force-quit below without losing work.
    bounded 15 osascript -e 'with timeout of 10 seconds' -e 'quit app "UnrealEditor"' -e 'end timeout' || true
    if ! wait_for 120 "the editor to quit" eval '! running'; then
      echo "force-quitting: a dialog still holds the editor after the save" >&2
      pkill -9 -f "UnrealEditor.*$UPROJECT" || true
      wait_for 30 "the editor to exit" eval '! running'
    fi
    cleanup_crash_reporters
    wait_for 60 "port $PORT to free" port_free
    ;;
  kill)
    pkill -9 -f "UnrealEditor.*$UPROJECT" || true
    wait_for 30 "the editor to exit" eval '! running'
    cleanup_crash_reporters
    wait_for 60 "port $PORT to free" port_free
    ;;
  status)
    editor_pid=$(editor_pids)
    echo "editor pid: ${editor_pid:-missing}; log: $LOG"
    failed=0
    port_free && failed=1
    if [[ -z "$editor_pid" ]] || ! owned_listener; then
      echo "port $PORT listener does not belong exclusively to the editor" >&2; failed=1
    fi
    mcp_probe || failed=1
    EDITOR_PY_TIMEOUT=5 "$HERE/editor-py" -e "'editor-py round trip OK'" || failed=1
    exit "$failed"
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
