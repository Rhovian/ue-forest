#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "tifffile", "pillow", "scipy"]
# ///
"""Crop Vilm island from DGM1 pixel centres and slope the sea around it down to a seabed for UE."""

import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import tifffile
from PIL import Image
from scipy.ndimage import distance_transform_edt, label

SEABED = -15.0
SIZE = 3025  # 1 m DGM1 samples per side of the window
SPACING = 2  # metres between landscape vertices: 1513x1513, the size that imports reliably (12x12 components)
WEST, NORTH = 402975, 6021769  # window corner; Vilm spans E403606-405468, N6019015-6021499
BBOX = [WEST, NORTH - SIZE, WEST + SIZE, NORTH]
OUT = Path(__file__).resolve().parents[2] / "Forest/Saved/Terrain"
# 2x2 km tiles, top-left corner (east, north + 2000); rows north to south.
TILE_ROWS = [[f"dgm1_33_{east}_{north}_2_gtiff.tif" for east in (402, 404)] for north in (6020, 6018)]
DGM_URL = "https://www.geodaten-mv.de/dienste/dgm_download?" + urlencode(
    {"index": 4, "dataset": "ca268792-s2q1-4a39-b34c-9ec5bf9a4469"}
)
# Official RGB service: LAiV's Kurzbeschreibung_WMS_DOP.pdf; layer from GetCapabilities.
DOP_URL = "https://www.geodaten-mv.de/dienste/adv_dop?" + urlencode({
    "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": "mv_dop",
    "STYLES": "", "CRS": "EPSG:25833", "BBOX": ",".join(map(str, BBOX)),
    "WIDTH": 1500, "HEIGHT": 1500, "FORMAT": "image/jpeg",
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
    rows = []
    for row in TILE_ROWS:
        for name in row:
            download(DGM_URL + "&file=" + name, OUT / "src" / name)
        rows.append([read_tile(OUT / "src" / name) for name in row])
    mosaic = np.block([[heights for heights, _ in row] for row in rows])
    invalid = np.block([[mask for _, mask in row] for row in rows])
    window = np.s_[6022000 - NORTH:6022000 - NORTH + SIZE, WEST - 402000:WEST - 402000 + SIZE]
    heights, invalid = mosaic[window], invalid[window]
    # The island is the largest piece of land; islets and mainland edges become sea.
    parts, _ = label(~invalid & (heights > 0))
    land = parts == np.argmax(np.bincount(parts.ravel())[1:]) + 1
    grid = falloff(heights, land)[::SPACING, ::SPACING]
    minimum, maximum = float(grid.min()), float(grid.max())
    zscale, actor_z = z_mapping(minimum, maximum)
    encoded = np.rint((grid - minimum) * 65535 / (maximum - minimum)).astype(np.uint16)
    Image.fromarray(encoded).save(OUT / "vilm_1513.png")
    metadata = {"min_m": minimum, "max_m": maximum, "ZScale": zscale, "actor_Z_cm": actor_z,
                "XYScale": 100 * SPACING, "island_km2": float(land.sum()) / 1e6, "source_tiles": TILE_ROWS,
                "crs": "EPSG:25833", "bbox": BBOX, "dop_url": DOP_URL}
    (OUT / "vilm_1513.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    preview = OUT / "vilm_dop.jpg"
    download(DOP_URL, preview, cache=False)
    with Image.open(preview) as image:
        image.load()
        if image.size != (1500, 1500) or image.mode != "RGB" or image.format != "JPEG":
            raise ValueError(f"Unexpected DOP image: {image.size}, {image.mode}, {image.format}")
    print(f"Heightmap: {OUT / 'vilm_1513.png'}\nAerial preview: {preview}")


if __name__ == "__main__":
    main()
