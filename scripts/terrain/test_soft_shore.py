import math
import unittest

import numpy as np

from scripts.terrain.soft_shore import RAMP_DEG, RAMP_FADE, RAMP_FULL, soften

RISE = math.tan(math.radians(RAMP_DEG))


def max_step_slope(profile, metres):
    return np.max(np.diff(profile)) / metres


class SoftShoreTests(unittest.TestCase):
    def coast(self, metres, land):
        """A straight coast along rows: sea, a 10 m beach at 0.3 m, then `land` (m) per vertex inland."""
        sea = int(10 / metres)
        beach = int(10 / metres)
        row = np.concatenate([np.full(sea, -1.0), np.full(beach, 0.3), land])
        return np.tile(row, (7, 1)), sea + beach

    def test_bank_at_the_sand_line_becomes_a_gentle_ramp(self):
        for metres in (1.0, 2.0):
            n = int(60 / metres)
            height, start = self.coast(metres, np.full(n, 6.0))
            soft = soften(height, metres)
            np.testing.assert_array_equal(soft[:, :start], height[:, :start])  # sea and beach untouched
            self.assertTrue(np.all(soft <= height))  # only ever lowered
            full = start + int(RAMP_FULL / metres)  # the first land vertex is one spacing from the beach
            # From the beach's last vertex to the last vertex within RAMP_FULL every step rises at most RAMP_DEG.
            self.assertLessEqual(max_step_slope(soft[3, start - 1:full], metres), RISE + 1e-9)
            self.assertTrue(np.all(soft[3, start:full] > 0.3))  # a ramp, not flattened to the sand
            edge = start + math.ceil(RAMP_FADE / metres) + 1
            np.testing.assert_array_equal(soft[:, edge:], height[:, edge:])  # beyond RAMP_FADE: original terrain

    def test_bank_behind_a_low_shelf_is_also_limited(self):
        # Low land at 0.8 m up to 8 m from the sand, then a 6 m bank: no 46 degree step inside the full band.
        metres = 2.0
        height, start = self.coast(metres, np.concatenate([np.full(4, 0.8), np.full(26, 6.0)]))
        soft = soften(height, metres)
        full = start + int(RAMP_FULL / metres)
        self.assertLessEqual(max_step_slope(soft[3, start - 1:full], metres), RISE + 1e-9)

    def test_gentle_ground_is_unchanged(self):
        metres = 1.0
        # Rising at 5 degrees straight from the beach's 0.3 m: under the limit everywhere.
        height, _ = self.coast(metres, 0.3 + np.arange(1, 41) * metres * math.tan(math.radians(5)))
        np.testing.assert_array_equal(soften(height, metres), height)

    def test_inland_hollow_below_sea_level_is_not_coast(self):
        # Ocean on the left edge; an inland pond at -0.1 m far from it, ringed by 6 m ground: untouched.
        height = np.full((60, 120), 6.0)
        height[:, :5] = -1.0
        height[25:35, 80:90] = -0.1
        np.testing.assert_array_equal(soften(height, 1.0)[:, 40:], height[:, 40:])


if __name__ == "__main__":
    unittest.main()
