"""No grass weight inside an exclusion polygon, wherever its edges cut the mask grid (#108 review).

    python3 -m unittest scripts/materials/test_mask_raster.py   (from scripts/materials)
"""

import math
import random
import unittest

from mask_raster import bilinear, dilate, fill

W = H = 40
OFFSETS = [k / 4 - 1 for k in range(9)]  # -1 .. 1 cell


def mask(points):
    pixels = bytearray(b"\xff" * (W * H))
    fill(pixels, W, H, points)
    return dilate(pixels, W, H)


def inside(points, x, y):
    crossings = 0
    for a, b in zip(points, points[1:] + points[:1]):
        if (a[1] <= y) != (b[1] <= y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            crossings += 1
    return crossings % 2 == 1


def corridor(x0, y0, x1, y1, half):
    """A straight band `half` cells either side of a segment: the footpath's shape."""
    nx, ny = y0 - y1, x1 - x0
    n = math.hypot(nx, ny)
    nx, ny = nx / n * half, ny / n * half
    return [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]


class NoWeightInside(unittest.TestCase):
    def assert_clear(self, points, samples=4000):
        """Every point inside gets zero weight from every landscape vertex within one cell (the interpolation)."""
        pixels, rng = mask(points), random.Random(1)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        checked = 0
        for _ in range(samples):
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            if not inside(points, x, y):
                continue
            checked += 1
            # Landscape vertices are one cell apart at an unknown offset, and a point blends the four around it:
            # every vertex position within one cell of the point must read zero.
            for dx in OFFSETS:
                for dy in OFFSETS:
                    self.assertEqual(bilinear(pixels, W, H, x + dx, y + dy), 0, (points, x, y, dx, dy))
        self.assertGreater(checked, 50)

    def test_edges_off_the_grid(self):
        # A 1.5-cell (3 m at 2 m cells) corridor whose edges fall at fractions of a cell.
        self.assert_clear(corridor(5.3, 10.6, 30.7, 10.6, 0.75))

    def test_diagonal_corridor(self):
        self.assert_clear(corridor(6.2, 7.9, 31.4, 29.3, 0.75))

    def test_irregular_lake(self):
        rng = random.Random(3)
        self.assert_clear([(20 + r * math.cos(a), 20 + r * math.sin(a)) for a, r in
                           ((k * math.tau / 23, rng.uniform(5, 11)) for k in range(23))])

    def test_far_ground_stays_open(self):
        pixels = mask(corridor(5.3, 10.6, 30.7, 10.6, 0.75))
        self.assertEqual(bilinear(pixels, W, H, 18.0, 25.0), 255)


if __name__ == "__main__":
    unittest.main()
