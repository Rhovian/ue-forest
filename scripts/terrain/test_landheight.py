import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np

from scripts.terrain.landheight import LIFT_CM, effective, lift, waterline


class LandHeightTests(unittest.TestCase):
    def coast(self):
        height = np.full((1201, 81), 0.5)  # straight coast, 60+ m inland
        height[:, :10] = -1.0
        return height

    def test_low_flat_is_land_beyond_30m_and_sand_within_12m(self):
        height = self.coast()
        weights = lift(height, 1.0)
        raised = effective(height, 1.0)
        self.assertTrue(np.all((weights >= 0) & (weights <= 1)))
        np.testing.assert_array_equal(raised[:, :22], height[:, :22])  # sea and first 12 m
        self.assertTrue(np.all(raised[:, 40:70] >= 0.75))  # 31 to 60 m inland
        np.testing.assert_array_equal(raised[:, 47:], height[:, 47:] + LIFT_CM / 100)
        np.testing.assert_allclose(raised, height + 1.5 * weights)
        self.assertTrue(np.any((weights > 0) & (weights < 1)))  # fade, not a hard step
        # Hold the width at 20 m to isolate the 10 m fade from the varying coast.
        with patch("scripts.terrain.landheight.strip_width", return_value=20):
            fixed = lift(height, 1.0)
        np.testing.assert_array_equal(fixed[0, [29, 34, 39]], [0, 0.5, 1])  # 20, 25, 30 m inland

    def test_width_drifts_between_12_and_28m_along_straight_coast(self):
        weights = lift(self.coast(), 1.0)
        first_rise = np.argmax(weights > 0, axis=1) - 9  # distance from last sea vertex
        self.assertTrue(np.all((first_rise >= 13) & (first_rise <= 29)))
        self.assertLess(first_rise.min(), 18)
        self.assertGreater(first_rise.max(), 24)
        self.assertLessEqual(np.abs(np.diff(first_rise)).max(), 1)  # low-frequency drift

    def test_noise_is_deterministic_across_runs(self):
        code = ("import hashlib, numpy as np; from scripts.terrain.landheight import lift; "
                "h=np.full((601,81),0.5); h[:,:10]=-1; print(hashlib.sha256(lift(h,1).tobytes()).hexdigest())")
        results = [subprocess.check_output([sys.executable, "-c", code]) for _ in range(2)]
        self.assertEqual(*results)
        height = self.coast()
        np.testing.assert_array_equal(lift(height, 1), lift(height, 1))

    def test_inland_hollow_and_enclosed_water_are_not_beach(self):
        height = np.full((101, 101), 3.0)
        height[:, :10] = -1.0
        height[40:60, 59:65] = 0.5  # 50 m from the sea
        height[40:60, 54:57] = -0.1  # enclosed pond beside the hollow must not create another beach
        np.testing.assert_array_equal(effective(height, 1)[40:60, 59:65], 2.0)

    def test_waterline_is_the_3cm_sea_edge_one_point_per_4m_cell(self):
        for metres in (1.0, 2.0):
            with self.subTest(metres=metres):
                height = np.full((61, 83), 0.03)
                height[:, :13] = 0.02
                height[20:25, 40:45] = -0.1  # enclosed water is not sea
                points = waterline(height, metres)
                expected_rows = range(0, 61, int(4 / metres))
                expected = [((13 - 41) * metres, (r - 30) * metres) for r in expected_rows]
                self.assertEqual(points, expected)  # rectangle, orientation, exact threshold and thinning
        # A diagonal crosses cells a row-only parity thinning rule would miss.
        r, c = np.indices((61, 61))
        diagonal = np.where(r + c < 60, 0.02, 0.03)
        points = waterline(diagonal, 2)
        pixels = [(round(y / 2 + 30), round(x / 2 + 30)) for x, y in points]
        self.assertTrue(all(r + c == 60 for r, c in pixels))
        occupied = {(r // 2, c // 2) for r, c in zip(*np.nonzero(r + c == 60))}
        self.assertEqual({(r // 2, c // 2) for r, c in pixels}, occupied)
        self.assertEqual(len(pixels), len(occupied))

    def test_no_sea_is_all_land_and_all_sea_has_no_lift_or_waterline(self):
        for height, weight in ((np.full((21, 21), 0.5), 1), (np.full((21, 21), -1.0), 0)):
            np.testing.assert_array_equal(lift(height, 2), weight)
            self.assertEqual(waterline(height, 2), [])


if __name__ == "__main__":
    unittest.main()
