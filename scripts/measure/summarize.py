# Summarize a measurement run directory written by baseline.py: one row per route point.
import csv
import json
import statistics
import sys
from pathlib import Path

# RenderThreadTime and RHI/DrawCalls read 0 on Metal; render thread time is summed from its exclusive timers instead.
COLUMNS = ["FrameTime", "GameThreadTime", "RenderThread", "GPUTime", "GPUSceneInstanceCount",
           "TextureStreaming/StreamingPool", "RenderTargetPoolSize"]


EMPTY_GPU_MS = 1.0  # frames below this GPU time rendered nothing


def frames(path):
    # csv.reader returns positional lists, not end-header handling: https://docs.python.org/3/library/csv.html#csv.reader
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    header = rows.pop(0)
    if rows and rows[-1] and rows[-1][0].startswith("["):
        metadata = rows.pop()
        if dict(zip(metadata[::2], metadata[1::2])).get("[HasHeaderRowAtEnd]") == "1":
            header = rows.pop()
    return [dict(zip(header, row)) for row in rows if row]


def column(rows, name):
    if not rows:
        return []
    if name == "RenderThread":
        return [sum(float(v or 0) for k, v in row.items()
                    if k.startswith("Exclusive/RenderThread/") and "/EventWait" not in k) for row in rows]
    return [float(row[name]) for row in rows if row.get(name) not in (None, "")]


def main(run):
    manifest = json.loads((run / "manifest.json").read_text())
    label = f"level {manifest['map']}" if "map" in manifest else f"tree {manifest['tree']} x{manifest['count']}"
    print(f"{label}  cvars {manifest['cvars']}")
    print("| point | frames used / captured | " + " | ".join(f"{c} mean / p95" for c in COLUMNS) + " |")
    print("|---" * (len(COLUMNS) + 2) + "|")
    for point in manifest["points"]:
        captured = frames(run / f"{point}.csv")
        rows = [row for row in captured if float(row.get("GPUTime") or 0) >= EMPTY_GPU_MS]
        cells = []
        for name in COLUMNS:
            values = column(rows, name)
            p95 = statistics.quantiles(values, n=20)[-1] if len(values) > 1 else next(iter(values), 0)
            cells.append(f"{statistics.mean(values):.2f} / {p95:.2f}" if values else "n/a")
        # A PIE window macOS stops presenting (seemingly when covered) renders nothing: GPU time near zero. Such a
        # point is no measurement, so say so rather than print its numbers (#179).
        if not rows:
            cells = ["no frames rendered"] + ["-"] * (len(COLUMNS) - 1)
        print(f"| {point} | {len(rows)} / {len(captured)} | " + " | ".join(cells) + " |")


main(Path(sys.argv[1]))
