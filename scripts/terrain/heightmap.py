#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "tifffile", "pillow"]
# ///
"""Crop Jasmund DGM1 pixel centres and surround them with a seabed falloff for UE."""

import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import tifffile
from PIL import Image

SEABED = -15.0
OUT = Path(__file__).resolve().parents[2] / "Forest/Saved/Terrain"
TILES = [f"dgm1_33_{east}_6046_2_gtiff.tif" for east in (412, 414)]
DGM_URL = "https://www.geodaten-mv.de/dienste/dgm_download?" + urlencode(
    {"index": 4, "dataset": "ca268792-s2q1-4a39-b34c-9ec5bf9a4469"}
)
# Official RGB service: LAiV's Kurzbeschreibung_WMS_DOP.pdf; layer from GetCapabilities.
DOP_URL = "https://www.geodaten-mv.de/dienste/adv_dop?" + urlencode({
    "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": "mv_dop",
    "STYLES": "", "CRS": "EPSG:25833", "BBOX": "413500,6047000,414500,6048000",
    "WIDTH": 1000, "HEIGHT": 1000, "FORMAT": "image/jpeg",
})


def download(url, path):
    """Cache complete downloads only; never reuse an interrupted temporary file."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    try:
        print(f"Downloading {path.name}", flush=True)
        with urlopen(url, timeout=60) as response, temp.open("wb") as output:
            shutil.copyfileobj(response, output)
            length = response.headers.get("Content-Length")
        if length is not None and temp.stat().st_size != int(length):
            raise ValueError(f"Incomplete download: {path}")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_tile(path):
    with tifffile.TiffFile(path) as tiff:
        tag = tiff.pages[0].tags.get("GDAL_NODATA")
        nodata = float(tag.value) if tag else None
    # Pillow's bundled TIFF decoder handles LZW without a fourth dependency (imagecodecs).
    with Image.open(path) as image:
        heights = np.array(image, dtype=np.float64)
    if heights.shape != (2000, 2000):
        raise ValueError(f"{path}: expected 2000x2000, got {heights.shape}")
    invalid = ~np.isfinite(heights) | (heights < 0)
    if nodata is not None:
        invalid |= heights == nodata
    heights[invalid] = SEABED
    return heights, invalid


def add_ring(core, width=256):
    """Distance is measured to the rectangle of core vertex centres; core is unchanged."""
    y, x = np.indices((core.shape[0] + 2 * width + 1, core.shape[1] + 2 * width + 1))
    cy = np.clip(y - width, 0, core.shape[0] - 1)
    cx = np.clip(x - width, 0, core.shape[1] - 1)
    distance = np.hypot(y - width - cy, x - width - cx)
    t = np.minimum(distance / width, 1)
    weight = 1 - t * t * (3 - 2 * t)
    return SEABED + (core[cy, cx] - SEABED) * weight


def z_mapping(minimum, maximum):
    span = maximum - minimum
    return span * 12800 / 65535, (minimum + 32768 * span / 65535) * 100


def main():
    tiles, masks = [], []
    for name in TILES:
        path = OUT / "src" / name
        download(DGM_URL + "&file=" + name, path)
        heights, invalid = read_tile(path)
        tiles.append(heights)
        masks.append(invalid)
    core = np.concatenate((tiles[0][:1000, 1500:], tiles[1][:1000, :500]), axis=1)
    affected = np.concatenate((masks[0][:1000, 1500:], masks[1][:1000, :500]), axis=1)
    grid = add_ring(core)
    minimum, maximum = float(grid.min()), float(grid.max())
    zscale, actor_z = z_mapping(minimum, maximum)
    encoded = np.rint((grid - minimum) * 65535 / (maximum - minimum)).astype(np.uint16)
    Image.fromarray(encoded).save(OUT / "jasmund_1513.png")
    metadata = {"min_m": minimum, "max_m": maximum, "ZScale": zscale, "actor_Z_cm": actor_z,
                "XYScale": 100, "sea_fraction": float(affected.mean()), "source_tiles": TILES,
                "crs": "EPSG:25833", "core_bbox": [413500, 6047000, 414500, 6048000],
                "core_offset": [256, 256], "dop_url": DOP_URL}
    (OUT / "jasmund_1513.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    preview = OUT / "core_dop.jpg"
    download(DOP_URL, preview)
    with Image.open(preview) as image:
        image.load()
        if image.size != (1000, 1000) or image.mode != "RGB" or image.format != "JPEG":
            raise ValueError(f"Unexpected DOP image: {image.size}, {image.mode}, {image.format}")
    print(f"Heightmap: {OUT / 'jasmund_1513.png'}\nAerial preview: {preview}")


if __name__ == "__main__":
    main()
