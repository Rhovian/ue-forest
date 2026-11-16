"""Import the beach lift (#240) as /Game/ForestBiome/T_BeachLift, and read it back for the editor-side masks.

    uv run --with numpy --with pillow --with scipy python scripts/terrain/landheight.py   # writes beach_lift.png
    scripts/editor-py scripts/materials/beach_lift.py

landheight.py bakes the lift field on the heightmap's grid: 1513 x 1513 vertex samples 2 m apart, centred on the world
origin, columns along +X and rows along +Y, 0 within the beach strip and 255 (LIFT_CM) beyond its fade. The floor
material (forest_floor.py), scan_mask.py and the placement filters (#241) all read this one baked line.
"""
import re
from pathlib import Path

import unreal
from mask_raster import bilinear, read_gray

PROJECT = Path(unreal.Paths.project_dir())
PNG = PROJECT / "Saved/Terrain/beach_lift.png"
# landheight.py needs NumPy and SciPy, which the editor's Python lacks: read its constant rather than restate it.
LIFT_CM = int(re.search(r"^LIFT_CM = (\d+)", (PROJECT / "../scripts/terrain/landheight.py").read_text(), re.MULTILINE)[1])
NAME = "T_BeachLift"
SIZE = 1513
# The texels are vertex samples: their centres fall on the vertices when the texture spans one spacing more than the
# vertex extent (+-1512 m), so the material and lift_cm map world XY over +-HALF_CM.
HALF_CM = SIZE * 100.0


def lift_cm():
    """A function (x, y) in cm -> the lift in cm, sampled as the floor material samples T_BeachLift (bilinear,
    clamped), so the masks and the rendered shore agree in the fade (#240 review)."""
    width, height, pixels = read_gray(PNG)

    def at(x, y):
        u, v = (x + HALF_CM) / (2 * HALF_CM) * width, (y + HALF_CM) / (2 * HALF_CM) * height
        return bilinear(pixels, width, height, u, v) / 255 * LIFT_CM
    return at


def main():
    from groundcover_mask import import_png
    width, height, pixels = read_gray(PNG)
    if (width, height) != (SIZE, SIZE):
        raise SystemExit(f"{PNG}: {width}x{height}, expected {SIZE}x{SIZE} (the heightmap's grid)")
    import_png(str(PNG), NAME)
    lifted = pixels.count(255) * 4 / 10000
    print(f"{NAME}: {width}x{height} from {PNG.name}, {lifted:.0f} ha lifted by {LIFT_CM} cm")


if __name__ == "__main__":
    main()
