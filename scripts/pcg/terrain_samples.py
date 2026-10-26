#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pillow"]
# ///
"""Read saved terrain heights outside UE's bundled Python, which does not ship Pillow."""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def sample(saved, points):
    uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
    # Pillow handles PNG decoding; subprocess runs its existing terrain-tool dependency offline.
    # UE 5.8 LandscapeProxy.h:GetHeightAtLocation has no UFUNCTION/Python binding.
    result = subprocess.run([uv, "run", "--offline", "--script", str(Path(__file__).resolve()), str(saved)],
                            input=json.dumps(points), text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(f"Source terrain sampling failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def main():
    from PIL import Image
    terrain = Path(sys.argv[1]) / "Terrain"
    meta = json.loads((terrain / "vilm_1513.json").read_text())
    with Image.open(terrain / "vilm_1513.png") as image:
        heights = []
        for x, y in json.load(sys.stdin):
            col, row = round(x / meta["XYScale"] + (image.width - 1) / 2), round(y / meta["XYScale"] + (image.height - 1) / 2)
            if not (0 <= col < image.width and 0 <= row < image.height):
                raise RuntimeError("Footpath outside source terrain")
            height = 100 * (meta["min_m"] + image.getpixel((col, row)) * (meta["max_m"] - meta["min_m"]) / 65535)
            if not math.isfinite(height):
                raise RuntimeError("Nonfinite source height")
            heights.append(height)
    print(json.dumps(heights))


if __name__ == "__main__":
    main()
