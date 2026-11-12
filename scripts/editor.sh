#!/usr/bin/env bash
# Editor lifecycle for the lead. See AGENTS.md "Code changes".
#   editor.sh open [editor args...]  launch with MCP on 8000; returns after an owned MCP round trip and loading L_vilm
#   editor.sh close                  save dirty packages (stops if that fails), quit, force-quit if a dialog still holds it; returns once 8000 is free
#   editor.sh kill                   force-quit a hung editor (unsaved work is lost); returns once 8000 is free
#   editor.sh build                  full build; the editor must be closed
#   editor.sh hot                    hot reload build; .cpp function bodies only, editor open
#   editor.sh status                 check process, port ownership, MCP and Python queue
#   editor.sh restart                close, build, open
set -euo pipefail

UE_ROOT=${UE_ROOT:-"/Users/Shared/Epic Games/UE_5.8"}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPROJECT=${EDITOR_UPROJECT:-"$HERE/../Forest/Forest.uproject"}
UPROJECT="$(cd "$(dirname "$UPROJECT")" && pwd)/$(basename "$UPROJECT")"
PORT=${EDITOR_PORT:-8000}
export EDITOR_MCP_URL="http://127.0.0.1:$PORT/mcp"

# The independent supervisor retains the deadline and stops the tree even when this caller is killed.
bounded() { python3 "$HERE/editor_process.py" "$@"; }
# Bracket the initial letter so the process query cannot match its own bounded wrapper argv.
editor_pids() {
  local code=0
  bounded 5 pgrep -f "[U]nrealEditor.*$UPROJECT" || code=$?
  [[ $code == 0 || $code == 1 ]] || return "$code"  # pgrep: 1 means no match
  return 0
}
running() { local pids; pids=$(editor_pids) || { echo "cannot query editor processes" >&2; exit 1; }; [[ -n "$pids" ]]; }
LOG=${EDITOR_LOG:-"$HOME/Library/Logs/Unreal Engine/ForestEditor/Forest.log"}

# lsof sees inherited listeners; the actual bind test also sees ownerless closing sockets.
command -v lsof >/dev/null || { echo "lsof is required to inspect port $PORT" >&2; exit 1; }
holders() {
  local pids code=0
  pids=$(bounded 5 lsof -b -w -nP -iTCP:$PORT -sTCP:LISTEN -t) || code=$?
  [[ $code == 0 || $code == 1 ]] || return "$code"
  [[ -z "$pids" ]] || echo "$pids" | sort -u
  return 0
}
show_holders() {
  local pids=$1
  [[ -n "$pids" ]] || return 0
  bounded 5 ps -p "$(echo "$pids" | paste -sd , -)" -o pid=,comm= ||
    echo "holder snapshot pid(s) $pids exited before process details were available"
}
port_clear() {
  local pids
  pids=$(holders) || return
  [[ -z "$pids" ]] || return 1
  port_error=$(bounded 5 "$HERE/editor_port.py" "$PORT" 2>&1)
}
reporter_released() {
  local pids; pids=$(holders) || return
  ! echo "$pids" | grep -qx "$1"
}
await_port_free() {
  local pids pid allowed=${1:-}
  pids=$(holders) || return
  for pid in $pids; do
    # Shutdown may lose the exiting editor's argv before its socket disappears; retain its original PID.
    if ! echo "$allowed" | grep -qx "$pid"; then
      echo "port $PORT held by:" >&2; show_holders "$pids" >&2; return 1
    fi
  done
  port_error=""
  if ! wait_for 60 "port $PORT to accept a fresh bind" port_clear; then
    pids=$(holders) || return
    show_holders "$pids" >&2
    [[ -z "$port_error" ]] || echo "$port_error" >&2
    return 1
  fi
}
cleanup_crash_reporters() {
  local pid parent command executable table project_name=${UPROJECT##*/}
  project_name=${project_name%.uproject}
  table=$(bounded 5 ps -ww -axo pid=,ppid=,command=) || return
  while read -r pid parent command; do
    # macOS uses a bare executable name and a shared engine crash directory (#190).
    # Require this project's folder name, executable identity and orphanhood.
    if [[ "$parent" == 1 && (
          "$command" == *"$HOME/Library/Application Support/Epic/UnrealEngine/"*"/Saved/Crashes/CrashReport-UE-$project_name-pid-"* ||
          "$command" == *"$(dirname "$UPROJECT")/Saved/Crashes/"* ) ]]; then
      if ! executable=$(bounded 5 ps -p "$pid" -o comm=); then
        if kill -0 "$pid" 2>/dev/null; then
          echo "cannot identify crash reporter pid $pid" >&2; return 1
        fi
        echo "crash reporter pid $pid already exited"; continue
      fi
      [[ "${executable##*/}" == CrashReportClient ]] || continue
      echo "stopping orphaned CrashReportClient pid $pid: $command"
      if ! kill -9 "$pid" 2>/dev/null && kill -0 "$pid" 2>/dev/null; then
        echo "could not stop crash reporter pid $pid" >&2; return 1
      fi
      wait_for 10 "crash reporter pid $pid to release port $PORT" reporter_released "$pid" || return
    fi
  done <<< "$table"
}
bind_failed() { [[ -f "$LOG" ]] && grep -q "HttpListener unable to bind to 127.0.0.1:$PORT" "$LOG"; }
owned_listener() {
  local pids; pids=$(holders) || return
  [[ -n "$pids" && "$pids" == "$editor_pid" ]]
}
mcp_probe() {
  local reply
  if reply=$(EDITOR_MCP_TIMEOUT="$2" bounded "$1" "$HERE/editor-mcp" 2>&1); then
    echo "MCP round trip OK"
  else
    echo "$reply" >&2; return 1
  fi
}
mcp_up() {
  local probe_end=$((SECONDS + $1)) pids budget
  bind_failed && { echo "fresh editor log $LOG: MCP could not bind port $PORT" >&2; exit 1; }
  kill -0 "$editor_pid" 2>/dev/null || { echo "launched editor pid $editor_pid exited; see $LOG" >&2; exit 1; }
  pids=$(holders) || return
  if [[ -n "$pids" && "$pids" != "$editor_pid" ]]; then
    echo "listener is not owned exclusively by launched editor pid $editor_pid" >&2
    show_holders "$pids" >&2; exit 1
  fi
  budget=$((probe_end - SECONDS))
  (( budget > 0 )) || return 1
  (( budget <= 6 )) || budget=6
  [[ -f "$LOG" ]] && owned_listener || return 1
  if last_probe_error=$(mcp_probe "$budget" 2 2>&1); then
    owned_listener && ! bind_failed || return 1
    echo "$last_probe_error"
    last_probe_error=""
  else
    return 1
  fi
}
open_exit() {
  local result=$?
  if (( result != 0 )) && [[ -n "${editor_pid:-}" ]] && kill -0 "$editor_pid" 2>/dev/null; then
    echo "open failed; launched editor pid $editor_pid is still running. Run scripts/editor.sh status, inspect $LOG, then scripts/editor.sh close (or kill if unresponsive)." >&2
  fi
}

# Checks receive their existing arguments followed by the explicit remaining budget in seconds.
wait_for() {
  local limit=$1 what=$2; shift 2
  local end=$((SECONDS + limit))
  while (( SECONDS < end )); do "$@" "$((end - SECONDS))" && return 0; sleep 1; done
  echo "timed out after ${limit}s waiting for $what" >&2
  return 1
}
stopped() { ! running; }

build() {
  bounded 3600 "$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" ForestEditor Mac Development \
    -Project="$UPROJECT" -Architecture=arm64 "$@"
}

[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0  # allow offline checks of lifecycle helpers

case ${1:-} in
  open)
    shift
    running && { echo "editor already running" >&2; exit 1; }
    cleanup_crash_reporters
    await_port_free
    # Keep one previous log; a new file proves this launch wrote it (mtime can share a second).
    [[ ! -f "$LOG" ]] || mv "$LOG" "$LOG.prev"
    # Packages left by an earlier forced exit raise a restore prompt at startup whatever bAutoSaveEnable says
    # (PackageAutoSaver reads this file on its own), and the prompt blocks MCP and editor-py until clicked. Move it
    # aside, not away: the autosave packages and their mapping stay for a manual restore.
    restore="$(dirname "$UPROJECT")/Saved/Autosaves/PackageRestoreData.json"
    [[ -f "$restore" ]] && mv -f "$restore" "$(mktemp "$restore.XXXXXX")"  # mktemp: a name no earlier backup has
    # Popen(start_new_session=True) supplies setsid; no custom fork/detach mechanism.
    # https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    editor_pid=""
    trap open_exit EXIT
    editor_pid=$(python3 - "${EDITOR_LAUNCH:-$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor}" \
      "$UPROJECT" -ModelContextProtocolStartServer -ModelContextProtocolPort=$PORT "$@" <<'PYTHON'
import signal, subprocess, sys
signal.signal(signal.SIGHUP, signal.SIG_IGN)  # inherited across exec; caller shutdown cannot hang up the editor
print(subprocess.Popen(sys.argv[1:], start_new_session=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid)
PYTHON
    )
    last_probe_error=""
    if ! wait_for "${EDITOR_OPEN_TIMEOUT:-900}" "MCP owned by pid $editor_pid on port $PORT (log: $LOG)" mcp_up; then
      [[ -z "$last_probe_error" ]] || echo "last MCP readiness probe: $last_probe_error" >&2
      exit 1
    fi
    echo "MCP up at http://127.0.0.1:$PORT/mcp"
    # A fresh editor loads no World Partition cells; load them all and set morning light (review/view_ready.py).
    "$(dirname "$0")/editor-py" "$(dirname "$0")/review/view_ready.py" ||
      { echo "editor is open, but loading L_vilm's cells failed (see above)" >&2; exit 1; }
    ;;
  close)
    exiting_pids=$(editor_pids)
    if [[ -z "$exiting_pids" ]]; then cleanup_crash_reporters; await_port_free; exit; fi
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
    if ! wait_for 120 "the editor to quit" stopped; then
      echo "force-quitting: a dialog still holds the editor after the save" >&2
      bounded 5 pkill -9 -f "[U]nrealEditor.*$UPROJECT" || true
      wait_for 30 "the editor to exit" stopped
    fi
    cleanup_crash_reporters
    await_port_free "$exiting_pids"
    ;;
  kill)
    exiting_pids=$(editor_pids)
    bounded 5 pkill -9 -f "[U]nrealEditor.*$UPROJECT" || true
    wait_for 30 "the editor to exit" stopped
    cleanup_crash_reporters
    await_port_free "$exiting_pids"
    ;;
  status)
    status_end=$((SECONDS + 60))
    editor_pid=$(editor_pids)
    echo "editor pid: ${editor_pid:-missing}; log: $LOG"
    pids=$(holders)
    echo "port $PORT listener: ${pids:-none}"
    show_holders "$pids"
    if [[ -z "$editor_pid" ]]; then
      echo "editor is not running; MCP and editor-py probes skipped" >&2; exit 1
    fi
    failed=0
    if ! owned_listener; then
      echo "port $PORT listener does not belong exclusively to the editor" >&2; failed=1
    fi
    budget=$((status_end - SECONDS)); (( budget <= 30 )) || budget=30
    (( budget > 0 )) && mcp_probe "$budget" 10 || failed=1
    budget=$((status_end - SECONDS)); (( budget <= 30 )) || budget=30
    if (( budget > 0 )); then
      EDITOR_PY_TIMEOUT="$budget" "$HERE/editor-py" --probe || failed=1
    else
      echo "status exhausted its 60s budget before the editor-py round trip" >&2; failed=1
    fi
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
    sed -n '2,9p' "$0" >&2
    exit 2
    ;;
esac
