#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "tifffile", "pillow", "scipy"]
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
from scipy.ndimage import distance_transform_edt

SEABED = -15.0
CORE_E = 413300
CORE_BBOX = [CORE_E, 6047000, CORE_E + 1000, 6048000]
OUT = Path(__file__).resolve().parents[2] / "Forest/Saved/Terrain"
TILES = [f"dgm1_33_{east}_6046_2_gtiff.tif" for east in (412, 414)]
DGM_URL = "https://www.geodaten-mv.de/dienste/dgm_download?" + urlencode(
    {"index": 4, "dataset": "ca268792-s2q1-4a39-b34c-9ec5bf9a4469"}
)
# Official RGB service: LAiV's Kurzbeschreibung_WMS_DOP.pdf; layer from GetCapabilities.
DOP_URL = "https://www.geodaten-mv.de/dienste/adv_dop?" + urlencode({
    "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": "mv_dop",
    "STYLES": "", "CRS": "EPSG:25833", "BBOX": ",".join(map(str, CORE_BBOX)),
    "WIDTH": 1000, "HEIGHT": 1000, "FORMAT": "image/jpeg",
})


def download(url, path, cache=True):
    """Cache complete downloads only; never reuse an interrupted temporary file."""
    if cache and path.exists():
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
    # Pillow's bundled TIFF decoder handles LZW without requiring imagecodecs.
    with Image.open(path) as image:
        heights = np.array(image, dtype=np.float64)
    if heights.shape != (2000, 2000):
        raise ValueError(f"{path}: expected 2000x2000, got {heights.shape}")
    invalid = ~np.isfinite(heights)
    if nodata is not None:
        invalid |= heights == nodata
    return heights, invalid


def falloff(heights, land):
    """Keep land heights and lower non-land smoothly toward seabed over 256 pixels."""
    if not land.any():
        return np.full(heights.shape, SEABED)
    distance, nearest = distance_transform_edt(~land, return_indices=True)
    t = np.minimum(distance / 256, 1)
    weight = 1 - t * t * (3 - 2 * t)
    grid = SEABED + (heights[tuple(nearest)] - SEABED) * weight
    grid[land] = heights[land]
    return grid


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
    west_col, east_cols = CORE_E - 412000, CORE_E + 1000 - 414000
    core = np.concatenate((tiles[0][:1000, west_col:], tiles[1][:1000, :east_cols]), axis=1)
    invalid = np.concatenate((masks[0][:1000, west_col:], masks[1][:1000, :east_cols]), axis=1)
    core_land = ~invalid & (core > 0)
    heights, land = np.zeros((1513, 1513)), np.zeros((1513, 1513), dtype=bool)
    heights[256:1256, 256:1256], land[256:1256, 256:1256] = core, core_land
    grid = falloff(heights, land)
    minimum, maximum = float(grid.min()), float(grid.max())
    zscale, actor_z = z_mapping(minimum, maximum)
    encoded = np.rint((grid - minimum) * 65535 / (maximum - minimum)).astype(np.uint16)
    Image.fromarray(encoded).save(OUT / "jasmund_1513.png")
    metadata = {"min_m": minimum, "max_m": maximum, "ZScale": zscale, "actor_Z_cm": actor_z,
                "XYScale": 100, "land_fraction": float(core_land.mean()), "source_tiles": TILES,
                "crs": "EPSG:25833", "core_bbox": CORE_BBOX,
                "core_offset": [256, 256], "dop_url": DOP_URL}
    (OUT / "jasmund_1513.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    preview = OUT / "core_dop.jpg"
    download(DOP_URL, preview, cache=False)
    with Image.open(preview) as image:
        image.load()
        if image.size != (1000, 1000) or image.mode != "RGB" or image.format != "JPEG":
            raise ValueError(f"Unexpected DOP image: {image.size}, {image.mode}, {image.format}")
    print(f"Heightmap: {OUT / 'jasmund_1513.png'}\nAerial preview: {preview}")


if __name__ == "__main__":
    main()
