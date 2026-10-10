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
os.makedirs(_IN, exist_ok=True)
os.makedirs(_OUT, exist_ok=True)
_elapsed = 0.0


def _run(name):
    path = os.path.join(_IN, name)
    with open(path) as f:
        source = f.read()
    os.remove(path)
    buffer, ok = io.StringIO(), True
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        try:
            # The lead intentionally submits arbitrary Python through the local file queue.
            exec(compile(source, name, "exec"), {"__name__": "__main__", "unreal": unreal})  # noqa: S102
        except Exception:  # noqa: BLE001 -- return any submitted script error to editor-py
            traceback.print_exc()
            ok = False
    tmp = os.path.join(_OUT, name + ".tmp")
    with open(tmp, "w") as f:
        json.dump({"ok": ok, "output": buffer.getvalue()}, f)
    os.replace(tmp, os.path.join(_OUT, name[:-3] + ".json"))


def _tick(delta):
    global _elapsed
    _elapsed += delta
    if _elapsed < 0.2:
        return
    _elapsed = 0.0
    for name in sorted(os.listdir(_IN)):
        if name.endswith(".py"):
            _run(name)


unreal.register_slate_post_tick_callback(_tick)
