"""Import the beach lift (#240) as /Game/ForestBiome/T_BeachLift, and read it back for the editor-side masks.

    uv run --with numpy --with pillow --with scipy python scripts/terrain/landheight.py   # writes beach_lift.png
    scripts/editor-py scripts/materials/beach_lift.py

landheight.py bakes the lift field on the heightmap's grid: 1513 x 1513 vertex samples 2 m apart, centred on the world
origin, columns along +X and rows along +Y, 0 within the beach strip and 255 (LIFT_CM) beyond its fade. The floor
material (forest_floor.py), scan_mask.py and the placement filters (#241) all read this one baked line.
"""
import re
import struct
import zlib
from pathlib import Path

import unreal

PROJECT = Path(unreal.Paths.project_dir())
PNG = PROJECT / "Saved/Terrain/beach_lift.png"
# landheight.py needs NumPy and SciPy, which the editor's Python lacks: read its constant rather than restate it.
LIFT_CM = int(re.search(r"^LIFT_CM = (\d+)", (PROJECT / "../scripts/terrain/landheight.py").read_text(), re.MULTILINE)[1])
NAME = "T_BeachLift"
SIZE = 1513
# The texels are vertex samples: their centres fall on the vertices when the texture spans one spacing more than the
# vertex extent (+-1512 m), so the material and lift_cm map world XY over +-HALF_CM.
HALF_CM = SIZE * 100.0


def read_gray(path):
    """(width, height, rows) of an 8-bit grayscale PNG, undoing the per-row filters (PNG spec 9.2)."""
    data = Path(path).read_bytes()
    width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
    if (depth, colour) != (8, 0):
        raise SystemExit(f"{path}: expected 8-bit grayscale, got depth {depth} colour type {colour}")
    chunks, at = [], 8
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        if kind == b"IDAT":
            chunks.append(data[at + 8:at + 8 + length])
        at += length + 12
    raw, rows, prior = zlib.decompress(b"".join(chunks)), [], bytes(width)
    for r in range(height):
        kind, line = raw[r * (width + 1)], bytearray(raw[r * (width + 1) + 1:(r + 1) * (width + 1)])
        for i in range(width):
            left, up, corner = (line[i - 1] if i else 0), prior[i], (prior[i - 1] if i else 0)
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
        rows.append(bytes(line))
        prior = rows[-1]
    return width, height, rows


def lift_cm():
    """A function (x, y) in cm -> the lift in cm at the nearest heightmap vertex (0 off the map)."""
    width, height, rows = read_gray(PNG)

    def at(x, y):
        i, j = int((x + HALF_CM) / (2 * HALF_CM) * width), int((y + HALF_CM) / (2 * HALF_CM) * height)
        return rows[j][i] / 255 * LIFT_CM if 0 <= i < width and 0 <= j < height else 0.0
    return at


def main():
    from groundcover_mask import import_png
    width, height, rows = read_gray(PNG)
    if (width, height) != (SIZE, SIZE):
        raise SystemExit(f"{PNG}: {width}x{height}, expected {SIZE}x{SIZE} (the heightmap's grid)")
    import_png(str(PNG), NAME)
    lifted = sum(v == 255 for row in rows for v in row) * 4 / 10000
    print(f"{NAME}: {width}x{height} from {PNG.name}, {lifted:.0f} ha lifted by {LIFT_CM} cm")


if __name__ == "__main__":
    main()
