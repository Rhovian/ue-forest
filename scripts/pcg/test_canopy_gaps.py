import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import canopy_gaps
import saplings_understory


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
        # The open sky stops short of the nearest trunk by the crown overhang.
        nearest = min(((tx - x) ** 2 + (ty - y) ** 2) ** 0.5 for tx, ty, _ in forest(hole=(2060, 2060, 14)))
        self.assertLessEqual(radius, nearest - canopy_gaps.CROWN + 0.05)

    def test_hole_beside_an_exclusion_spline_is_not_a_gap(self):
        # A footpath or stream corridor is tree-free but is not a canopy gap.
        path = [(2060 + d, 2062) for d in range(-20, 21, 2)]
        self.assertEqual(canopy_gaps.gaps(forest(hole=(2060, 2060, 14)), path), [])

    def test_forest_edge_is_not_a_gap(self):
        # Open ground at the forest's edge lacks trees in every octant.
        self.assertEqual(canopy_gaps.gaps(forest(hole=(2000, 2060, 14)), [(0, 0)]), [])

    def test_forest_edge_has_edge_openings_with_open_sky(self):
        # Heather's edge openings (#82): open ground beside the forest, each clear of trunks by its radius + CROWN.
        trunks = forest()
        found = canopy_gaps.gaps(trunks, [(0, 0)], edge=True)
        self.assertTrue(found)
        for x, y, _, radius in found:
            nearest = min(((tx - x) ** 2 + (ty - y) ** 2) ** 0.5 for tx, ty, _ in trunks)
            self.assertGreaterEqual(nearest, canopy_gaps.EDGE_GAP)
            self.assertLessEqual(radius, min(nearest - canopy_gaps.CROWN, canopy_gaps.EDGE_MAX) + 0.05)

    def test_closed_canopy_has_no_edge_openings_inside(self):
        # Shaded floor under closed canopy is not the sunny forest edge; openings lie only outside the trunks.
        for x, y, _, _ in canopy_gaps.gaps(forest(), [(0, 0)], edge=True):
            self.assertFalse(2000 <= x <= 2120 and 2000 <= y <= 2120, (x, y))

    def test_a_veterans_outer_crown_closes_an_opening_and_spares_one_beyond(self):
        # Veterans shade their whole crown (#96 review): a hole under the outer crown of a veteran standing among the
        # trees is no gap, while a hole beyond its crown stays one.
        shaded, open_hole = (2060, 2060, 14), (2180, 2180, 14)
        trees = [t for t in forest(size=240)
                 if all((t[0] - x) ** 2 + (t[1] - y) ** 2 >= r * r for x, y, r in (shaded, open_hole))]
        veteran = (shaded[0] + canopy_gaps.VETERAN_CROWN - 4, shaded[1], 10.0)  # its crown reaches past the hole centre
        found = canopy_gaps.gaps(canopy_gaps.with_veterans(trees, [veteran]), [(0, 0)])
        centres = [(x, y) for x, y, _, _ in found]
        self.assertFalse(any(abs(x - shaded[0]) < 12 and abs(y - shaded[1]) < 12 for x, y in centres), centres)
        self.assertTrue(any(abs(x - open_hole[0]) < 8 and abs(y - open_hole[1]) < 8 for x, y in centres), centres)
        for x, y in centres:  # nothing under the crown
            self.assertGreater(((x - veteran[0]) ** 2 + (y - veteran[1]) ** 2) ** 0.5, canopy_gaps.VETERAN_CROWN)

    def test_envelope_encloses_every_sampled_height(self):
        # canopy_filter's column spans this range; it must hold every traced ground height in any order.
        for heights in ([12.04, 8.06, 9.5], [8.0], [-1.23, 3.751, 0.0]):
            low, high = canopy_gaps.envelope(heights)
            self.assertTrue(all(low <= h <= high for h in heights))
            self.assertLess(high - low, max(heights) - min(heights) + 0.2)

    def test_column_targets_reach_every_ground_height_within_half_a_step(self):
        # canopy_filter's distance is 3D: a ground point is measured horizontally only if a target sits near its height.
        for low, high in ((8.3, 8.3), (8.0, 12.1), (-1.2, 3.75)):
            targets = saplings_understory.column(low, high)
            self.assertAlmostEqual(targets[0], low * 100)
            self.assertAlmostEqual(targets[-1], high * 100)
            for ground in [low * 100 + (high - low) * 100 * k / 97 for k in range(98)]:
                self.assertLessEqual(min(abs(ground - t) for t in targets), saplings_understory.COLUMN_STEP / 2 + 1e-6)


if __name__ == "__main__":
    unittest.main()
