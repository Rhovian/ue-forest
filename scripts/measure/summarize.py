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
    # The profiler grows columns and writes its full header before metadata; csv.reader only parses records:
    # https://docs.python.org/3/library/csv.html#csv.reader
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    header = rows.pop(0)
    if rows and rows[-1] and rows[-1][0].startswith("["):
        metadata = rows.pop()
        if dict(zip(metadata[::2], metadata[1::2])).get("[HasHeaderRowAtEnd]") == "1":
            header = rows.pop()
    for line, row in enumerate(rows, start=2):
        if len(row) > len(header):
            raise ValueError(f"{path}: row {line} has {len(row)} cells, header has {len(header)}")
    return [dict(zip(header, row)) for row in rows if row]


def column(rows, name):
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
            if values:
                p95 = statistics.quantiles(values, n=20)[-1] if len(values) > 1 else values[0]
                cells.append(f"{statistics.mean(values):.2f} / {p95:.2f}")
            else:
                cells.append("n/a")
        # A PIE window macOS stops presenting renders nothing: drop those frames (#179).
        # Keep sparse samples' numbers, but mark points with fewer than half their frames rendered (#200).
        if not rows:
            cells = ["no frames rendered"] + ["-"] * (len(COLUMNS) - 1)
        count = f"{len(rows)} / {len(captured)}"
        if len(rows) * 2 < len(captured):
            count += " (under half rendered)"
        print(f"| {point} | {count} | " + " | ".join(cells) + " |")


main(Path(sys.argv[1]))
