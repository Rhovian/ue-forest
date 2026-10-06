# Summarize a measurement run directory written by baseline.py: one row per route point.
import csv
import json
import statistics
import sys
from pathlib import Path

COLUMNS = ["FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "RHI/DrawCalls", "RHI/PrimitivesDrawn"]


def column(rows, name):
    values = [float(row[name]) for row in rows if row.get(name) not in (None, "")]
    return values


def main(run):
    manifest = json.loads((run / "manifest.json").read_text())
    print(f"tree {manifest['tree']} x{manifest['count']}  cvars {manifest['cvars']}")
    print("| point | " + " | ".join(f"{c} mean / p95" for c in COLUMNS) + " |")
    print("|---" * (len(COLUMNS) + 1) + "|")
    for point in manifest["points"]:
        with open(run / f"{point}.csv", newline="") as f:
            # The CSV profiler appends metadata rows after the frames; they fail float() and are skipped.
            rows = [row for row in csv.DictReader(f) if (row.get("FrameTime") or "").replace(".", "", 1).isdigit()]
        cells = []
        for name in COLUMNS:
            values = column(rows, name)
            cells.append(f"{statistics.mean(values):.2f} / {statistics.quantiles(values, n=20)[-1]:.2f}" if values else "n/a")
        print(f"| {point} | " + " | ".join(cells) + " |")


main(Path(sys.argv[1]))
