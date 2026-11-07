import unittest

import numpy as np

from scripts.terrain.forest_foot import STEP, foot_and_bounds


class ForestFootTests(unittest.TestCase):
    def test_bounds_include_low_ground_and_joined_lobes(self):
        # Sea everywhere; a forest block above the shore height; beach and low meadow (below it) beyond the block
        # to the east; past the meadow a second high lobe joined to the island only through that low ground.
        height = np.full((41, 41), -1.0)
        height[10:30, 5:15] = 5.0  # forest, columns 5-14
        height[10:30, 15:30] = 0.4  # beach and meadow, below the 0.75 m shore height
        height[18:22, 30:36] = 3.0  # high lobe beyond the low ground, columns 30-35
        points, bounds = foot_and_bounds(height, 0.75, 1.0)
        half = 20
        # Bounds reach the far lobe's east edge (column 35) and every row of low ground, not just the forest block.
        self.assertEqual(bounds, [5 - half, 35 - half, 10 - half, 29 - half])
        # The forest foot follows the larger high block's edge on the beach (column 14), one point per STEP cell.
        self.assertTrue(points)
        self.assertTrue(all(x == 14 - half for x, _ in points))
        self.assertEqual(len(points), len({(y + half) // STEP for _, y in points}))


if __name__ == "__main__":
    unittest.main()
