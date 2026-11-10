# Summarize a measurement run directory written by baseline.py: one row per route point.
import csv
import json
import statistics
import sys
from pathlib import Path

# RenderThreadTime and RHI/DrawCalls read 0 on Metal; render thread time is summed from its exclusive timers instead.
COLUMNS = ["FrameTime", "GameThreadTime", "RenderThread", "GPUTime", "GPUSceneInstanceCount",
           "TextureStreaming/StreamingPool", "RenderTargetPoolSize"]


EMPTY_GPU_MS = 1.0  # mean GPU time below which a point rendered nothing


def numeric(value):
    try:
        float(value or 0)
        return True
    except (TypeError, ValueError):
        return False


def column(rows, name):
    if name == "RenderThread":
        keys = [k for k in rows[0] if k.startswith("Exclusive/RenderThread/") and "/EventWait" not in k]
        return [sum(float(row[k] or 0) for k in keys) for row in rows]
    return [float(row[name]) for row in rows if row.get(name) not in (None, "")]


def main(run):
    manifest = json.loads((run / "manifest.json").read_text())
    label = f"level {manifest['map']}" if "map" in manifest else f"tree {manifest['tree']} x{manifest['count']}"
    print(f"{label}  cvars {manifest['cvars']}")
    print("| point | " + " | ".join(f"{c} mean / p95" for c in COLUMNS) + " |")
    print("|---" * (len(COLUMNS) + 1) + "|")
    for point in manifest["points"]:
        with open(run / f"{point}.csv", newline="") as f:
            # The CSV profiler appends metadata rows after the frames; keep only rows whose cells are all numeric.
            rows = [row for row in csv.DictReader(f) if all(numeric(v) for v in row.values())]
        cells = []
        for name in COLUMNS:
            values = column(rows, name)
            cells.append(f"{statistics.mean(values):.2f} / {statistics.quantiles(values, n=20)[-1]:.2f}" if values else "n/a")
        gpu = column(rows, "GPUTime")
        # A PIE window macOS stops presenting (seemingly when covered) renders nothing: GPU time near zero. Such a
        # point is no measurement, so say so rather than print its numbers (#179).
        if gpu and statistics.mean(gpu) < EMPTY_GPU_MS:
            cells = [f"no frames rendered (GPU {statistics.mean(gpu):.2f} ms)"] + ["-"] * (len(COLUMNS) - 1)
        print(f"| {point} | " + " | ".join(cells) + " |")


main(Path(sys.argv[1]))
