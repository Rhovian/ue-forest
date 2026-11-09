"""Bake /Game/ForestBiome/T_GroundcoverMask: where the floor's groundcover grass may grow (#100).

    scripts/editor-py scripts/materials/groundcover_mask.py

Landscape Grass knows nothing of PCG exclusions, so tufts grew under clear stream water and would cover the
vegetation-free shore path. This blacks out every water exclusion polygon (ForestExclusion_*, water_exclusions.py) and
the footpath corridor (shore_path.py) on a white grid of landscape-quad cells over the island's bounds
(forest_foot.json), which forest_floor.py multiplies into the grass weight. Grass weight is resolved per landscape
vertex, so mask_raster.py blacks every touched cell and grows it by two cells: no plant inside a polygon, and growth
thins over the 2-4 m beside it. Rerun after either script changes its splines, then forest_floor.py. The PNG is a
temporary file; only the texture asset is kept.
"""

import json
import math
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/pcg"))
sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "../scripts/materials"))
from mask_raster import dilate, fill
from shore_path import LABEL

FOLDER = "/Game/ForestBiome"
NAME = "T_GroundcoverMask"
CELL = 200  # cm per pixel: L_vilm's landscape quad, the grass weight's own resolution (and under 2048 px, no VT)
PREFIX = "ForestExclusion_"
ISLAND = json.loads((Path(unreal.Paths.project_dir()) / "../scripts/pcg/forest_foot.json").read_text())["island_m"]


def bounds():
    """(x0, y0) in cm and (width, height) in pixels of the mask, from the island's bounds in metres."""
    x_min, x_max, y_min, y_max = ISLAND
    return x_min * 100, y_min * 100, math.ceil((x_max - x_min) * 100 / CELL), math.ceil((y_max - y_min) * 100 / CELL)


def polygons():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    found = [a for a in actors if a.get_actor_label().startswith(PREFIX) or a.get_actor_label() == LABEL]
    if not any(a.get_actor_label() == LABEL for a in found) or len(found) < 2:
        raise SystemExit("Run water_exclusions.py and shore_path.py first: exclusion splines missing")
    outlines = []
    for actor in found:
        spline = actor.get_component_by_class(unreal.SplineComponent)
        world = unreal.SplineCoordinateSpace.WORLD
        outlines.append([spline.get_location_at_spline_point(i, world) for i in range(spline.get_number_of_spline_points())])
    return outlines


def write_png(path, pixels, width, height):
    rows = b"".join(b"\0" + bytes(pixels[r * width:(r + 1) * width]) for r in range(height))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def import_texture(pixels, width, height, name):
    """Import the 8-bit mask as FOLDER/name: linear, clamped, no mips, saved."""
    folder = tempfile.mkdtemp()
    png = os.path.join(folder, name + ".png")
    write_png(png, pixels, width, height)
    task = unreal.AssetImportTask()
    for key, value in {"filename": png, "destination_path": FOLDER, "destination_name": name, "replace_existing": True,
                       "automated": True, "save": False}.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    os.remove(png)
    os.rmdir(folder)
    texture = unreal.load_asset(f"{FOLDER}/{name}")
    if texture is None:
        raise SystemExit("mask import failed")
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)  # mips blur white in
    unreal.EditorAssetLibrary.save_loaded_asset(texture, False)


def main():
    x0, y0, width, height = bounds()
    pixels = bytearray(b"\xff" * (width * height))
    outlines = polygons()
    for outline in outlines:
        fill(pixels, width, height, [((p.x - x0) / CELL, (p.y - y0) / CELL) for p in outline])
    pixels = dilate(pixels, width, height)
    import_texture(pixels, width, height, NAME)
    blocked = width * height - sum(1 for v in pixels if v)
    print(f"{NAME}: {width}x{height} px at {CELL} cm, {len(outlines)} exclusions, {blocked * CELL * CELL / 1e8:.1f} ha masked")


if __name__ == "__main__":
    main()
