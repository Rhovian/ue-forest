import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import canopy_gaps


def forest(hole=None, size=120, spacing=4):
    """Trunks on a jittered grid over size x size m, far from the meadows, with an optional (x, y, r) hole."""
    trunks = []
    for i in range(0, size, spacing):
        for j in range(0, size, spacing):
            x, y = 2000 + i + (j % 3) * 0.7, 2000 + j + (i % 3) * 0.7
            if hole and (x - hole[0]) ** 2 + (y - hole[1]) ** 2 < hole[2] ** 2:
                continue
            trunks.append((x, y, 10.0))
    return trunks


class CanopyGapTests(unittest.TestCase):
    def test_closed_forest_has_no_gaps(self):
        self.assertEqual(canopy_gaps.gaps(forest(), [(0, 0)]), [])

    def test_hole_inside_forest_is_one_gap(self):
        found = canopy_gaps.gaps(forest(hole=(2060, 2060, 14)), [(0, 0)])
        self.assertEqual(len(found), 1)
        x, y, z, radius = found[0]
        self.assertLess(abs(x - 2060) + abs(y - 2060), 6)
        self.assertEqual(z, 10.0)
        self.assertGreaterEqual(radius, canopy_gaps.MIN_GAP - canopy_gaps.CROWN)

    def test_hole_beside_an_exclusion_spline_is_not_a_gap(self):
        # A footpath or stream corridor is tree-free but is not a canopy gap.
        path = [(2060 + d, 2062) for d in range(-20, 21, 2)]
        self.assertEqual(canopy_gaps.gaps(forest(hole=(2060, 2060, 14)), path), [])

    def test_forest_edge_is_not_a_gap(self):
        # Open ground at the forest's edge lacks trees in every octant.
        self.assertEqual(canopy_gaps.gaps(forest(hole=(2000, 2060, 14)), [(0, 0)]), [])


if __name__ == "__main__":
    unittest.main()
