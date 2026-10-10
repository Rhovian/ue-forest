import unittest

import numpy as np

from scripts.terrain.heightmap import SEABED, falloff, z_mapping


class HeightmapTests(unittest.TestCase):
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
