# Runs at editor startup. Executes Python files the lead drops into Saved/EditorPy/in on the game
# thread and writes {"ok", "output"} to Saved/EditorPy/out/<name>.json. Used by scripts/editor-py.
import contextlib
import io
import json
import os
import traceback

import unreal

_ROOT = os.path.join(unreal.Paths.project_saved_dir(), "EditorPy")
_IN, _OUT = os.path.join(_ROOT, "in"), os.path.join(_ROOT, "out")
# scripts/editor.sh close writes this in the same request that saves; the queue then runs nothing more, so no queued
# script can dirty a package between that save and the quit (or force-quit). A new editor starts with the queue open.
_CLOSING = os.path.join(_ROOT, "closing")
os.makedirs(_IN, exist_ok=True)
os.makedirs(_OUT, exist_ok=True)
if os.path.exists(_CLOSING):
    os.remove(_CLOSING)
_elapsed = 0.0


def _run(name):
    path = os.path.join(_IN, name)
    probe = name.startswith("probe-")
    try:
        with open(path) as f:
            source = f.read()
        os.remove(path)
    except FileNotFoundError:
        if probe:  # cancellation may race the directory scan or pickup
            return
        raise
    buffer, ok = io.StringIO(), True
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        try:
            # The lead intentionally submits arbitrary Python through the local file queue.
            exec(compile(source, name, "exec"), {"__name__": "__main__", "unreal": unreal})  # noqa: S102
        except SystemExit as exit_:  # argparse usage errors and explicit exits still owe editor-py a result
            if exit_.code not in (None, 0):
                print(exit_.code if isinstance(exit_.code, str) else f"exit code {exit_.code}")
                ok = False
        except Exception:  # noqa: BLE001 -- return any submitted script error to editor-py
            traceback.print_exc()
            ok = False
    # editor-py --probe owns this directory; never recreate it after cancellation.
    folder = os.path.join(_OUT, name[:-3]) if probe else _OUT
    tmp = os.path.join(folder, "result.tmp" if probe else name + ".tmp")
    out = os.path.join(folder, "result.json" if probe else name[:-3] + ".json")
    try:
        with open(tmp, "w") as f:
            json.dump({"ok": ok, "output": buffer.getvalue()}, f)
        os.replace(tmp, out)
    except FileNotFoundError:
        if not probe:
            raise


def _tick(delta):
    global _elapsed
    _elapsed += delta
    if _elapsed < 0.2:
        return
    _elapsed = 0.0
    for name in sorted(os.listdir(_IN)):
        if os.path.exists(_CLOSING):
            return
        if name.endswith(".py"):
            _run(name)


unreal.register_slate_post_tick_callback(_tick)
