import unittest
from unittest.mock import patch

import numpy as np
from scipy.ndimage import distance_transform_edt

from scripts.terrain.heightmap import CHANNEL_HALF_WIDTH, SEABED, SPACING, carve_stream, falloff, z_mapping


class HeightmapTests(unittest.TestCase):
    def test_carve_stream(self):
        grid = np.full((31, 31), 50.0)
        grid[:, 15] = np.arange(31, 0, -1) * 0.5
        grid[18, 15] = grid[17, 15] + 0.2  # A bump on the downhill route.
        grid[22:] = 0
        with patch("scripts.terrain.heightmap.STREAM_HEAD", (0, 0)):
            carved, points = carve_stream(grid)
        centre = (grid.shape[0] - 1) // 2
        x, y, _ = points[-1]
        self.assertLessEqual(grid[centre + y // (SPACING * 100), centre + x // (SPACING * 100)], 0)
        self.assertTrue(np.all(np.diff(np.array(points)[:, 2]) <= 0))
        mask = np.ones(grid.shape, dtype=bool)
        mask[15:23, 15] = False
        distance = distance_transform_edt(mask, sampling=SPACING)
        outside = distance > CHANNEL_HALF_WIDTH
        np.testing.assert_array_equal(carved[outside], grid[outside])
        self.assertTrue(np.all(carved <= grid))
        self.assertAlmostEqual(carved[18, 15], grid[17, 15] - 0.6)

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
