import math
import unittest

import numpy as np

from scripts.terrain.soft_shore import RAMP_DEG, RAMP_FADE, RAMP_FULL, SHORE, soften


class SoftShoreTests(unittest.TestCase):
    def test_bank_at_the_sand_line_becomes_a_ramp(self):
        # 1 m pixels: sea (cols 0-4), a 10 m beach at 0.3 m (cols 5-14), then a 6 m bank rising from the sand line.
        height = np.full((5, 70), 6.0)
        height[:, :5] = -1.0
        height[:, 5:15] = 0.3
        soft = soften(height, 1.0)
        np.testing.assert_array_equal(soft[:, :15], height[:, :15])  # sea and beach untouched
        self.assertTrue(np.all(soft <= height))  # only ever lowered
        rise = math.tan(math.radians(RAMP_DEG))
        row = soft[2]
        for d in range(1, int(RAMP_FULL) + 1):  # within RAMP_FULL of the sand line: the ramp
            self.assertLessEqual(row[14 + d], SHORE + d * rise + 1e-6)
        edge = 14 + int(RAMP_FADE) + 1
        np.testing.assert_array_equal(row[edge:], height[2, edge:])  # beyond RAMP_FADE: the original terrain

    def test_gentle_ground_is_unchanged(self):
        # Ground rising from the sand at 5 degrees, under the ramp everywhere: nothing changes.
        height = np.full((5, 40), -1.0)
        height[:, 5:] = SHORE + np.arange(35) * math.tan(math.radians(5))
        height[:, 5] = 0.3
        np.testing.assert_array_equal(soften(height, 1.0), height)


if __name__ == "__main__":
    unittest.main()
