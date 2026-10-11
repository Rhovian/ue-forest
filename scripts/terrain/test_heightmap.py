import unittest
from itertools import pairwise
from unittest.mock import patch

import numpy as np
from scipy.ndimage import distance_transform_edt

from scripts.terrain.heightmap import CHANNEL_HALF_WIDTH, SEABED, SPACING, carve_stream, falloff, z_mapping


class HeightmapTests(unittest.TestCase):
    def test_carve_stream(self):
        # A valley at a slant to the grid, so the descent zigzags like a real DEM path, reaching sea level at row 60.
        rows, cols = np.indices((61, 61), dtype=float)
        grid = 30 - 0.5 * rows + 2 * np.abs(cols - 30 - (rows - 10) / 2)
        with patch("scripts.terrain.heightmap.STREAM_HEAD", (0, -40)):
            carved, points = carve_stream(grid)
        cells = [(30 + y // (SPACING * 100), 30 + x // (SPACING * 100)) for x, y, _ in points]
        self.assertLessEqual(grid[cells[-1]], 0)
        self.assertTrue(np.all(np.diff([z for _, _, z in points]) <= 0))
        self.assertTrue(np.all(carved <= grid))
        # Nothing changes beyond the channel, measured from the spline.
        mask = np.ones(grid.shape, dtype=bool)
        mask[tuple(np.array(cells).T)] = False
        outside = distance_transform_edt(mask, sampling=SPACING) > CHANNEL_HALF_WIDTH
        np.testing.assert_array_equal(carved[outside], grid[outside])
        # Water stays above the landscape's triangles along the spline, so banks cannot bead the stream.
        for ((r0, c0), z0), ((r1, c1), z1) in pairwise(zip(cells, points)):
            for t in np.linspace(0, 1, 8, endpoint=False):
                r, c = r0 + (r1 - r0) * t, c0 + (c1 - c0) * t
                i, j, fy, fx = int(r), int(c), r % 1, c % 1
                a, b, cc, d = carved[i, j], carved[i, j + 1], carved[i + 1, j], carved[i + 1, j + 1]
                ground = a + fx * (d - cc) + fy * (cc - a) if fy > fx else a + fx * (b - a) + fy * (d - b)
                self.assertGreater((z0[2] + (z1[2] - z0[2]) * t) / 100, ground)

    def test_z_round_trip(self):
        for minimum, maximum in ((-15.0, 161.0), (-3.5, 7.25)):
            scale, actor_z = z_mapping(minimum, maximum)
            step = (maximum - minimum) / 65535
            for sample, expected in ((0, minimum), (65535, maximum)):
                decoded = (sample - 32768) * scale / 12800 + actor_z / 100
                self.assertAlmostEqual(decoded, expected, delta=step)

    def test_falloff(self):
        heights = np.zeros((520, 520))
        heights[256:258, 256:258] = [[1.0, 2.0], [3.0, 4.0]]
        land = heights > 0
        grid = falloff(heights, land)
        np.testing.assert_array_equal(grid[land], heights[land])
        self.assertAlmostEqual(grid[255, 256], heights[256, 256], delta=0.001)
        y, x = np.indices(grid.shape)
        distance = np.hypot(y - np.clip(y, 256, 257), x - np.clip(x, 256, 257))
        self.assertTrue(np.all(grid[~land & (distance >= 256)] == SEABED))


if __name__ == "__main__":
    unittest.main()
