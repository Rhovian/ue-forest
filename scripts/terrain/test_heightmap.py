import unittest

import numpy as np

from scripts.terrain.heightmap import SEABED, add_ring, z_mapping


class HeightmapTests(unittest.TestCase):
    def test_z_round_trip(self):
        for minimum, maximum in ((-15.0, 161.0), (-3.5, 7.25)):
            scale, actor_z = z_mapping(minimum, maximum)
            step = (maximum - minimum) / 65535
            for sample, expected in ((0, minimum), (65535, maximum)):
                decoded = (sample - 32768) * scale / 12800 + actor_z / 100
                self.assertAlmostEqual(decoded, expected, delta=step)

    def test_ring(self):
        core = np.array([[-10.0, 5.0], [20.0, 30.0]])
        grid = add_ring(core)
        np.testing.assert_allclose(grid[256:258, 256:258], core)
        # At d=1 the specified smoothstep changes this edge by only 0.000228 m.
        self.assertAlmostEqual(grid[255, 256], core[0, 0], delta=0.001)
        y, x = np.indices(grid.shape)
        distance = np.hypot(y - np.clip(y, 256, 257), x - np.clip(x, 256, 257))
        self.assertTrue(np.all(grid[distance >= 256] == SEABED))


if __name__ == "__main__":
    unittest.main()
