import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import area_sampling
import deadwood_rocks


class CandidateBudgetTests(unittest.TestCase):
    def test_estimate_scales_with_density_and_cell_cap(self):
        low = deadwood_rocks.candidate_estimate(100, 100)
        self.assertAlmostEqual(deadwood_rocks.candidate_estimate(200, 100), 2 * low)
        # 600,000/ha is above the 100 cm extent's cell cap (2,500/ha), so the cap governs.
        self.assertAlmostEqual(deadwood_rocks.candidate_estimate(600000, 100), deadwood_rocks.candidate_estimate(2500, 100))

    def test_generator_refuses_over_budget(self):
        with self.assertRaisesRegex(RuntimeError, "million points"):
            deadwood_rocks.generator("Meadow", 600000, 25, 60, extent=8)  # the configuration that hit memory pressure

    def test_generator_refuses_density_override(self):
        # A PointsPerSquareMeter override would install a density the estimate never checked.
        with self.assertRaisesRegex(RuntimeError, "PointsPerSquareMeter override"):
            deadwood_rocks.generator("Example", 1, 25, 60, {"PointsPerSquareMeter": 60}, extent=10)

    def test_estimate_counts_an_area_generators_tiles(self):
        self.assertAlmostEqual(deadwood_rocks.candidate_estimate(100, 100, area_ha=2), 200)


class AreaTileTests(unittest.TestCase):
    def test_tiles_cover_every_point_within_reach(self):
        samples = [(x * 100.0, 0.37 * x * 100.0) for x in range(0, 300, 3)]  # a slanting line of samples
        reach, cell = 1300, area_sampling.TILE
        covered = set(area_sampling.tiles_near(samples, reach))
        for sx, sy in samples:
            for dx in range(-reach, reach + 1, 97):
                for dy in range(-reach, reach + 1, 97):
                    if dx * dx + dy * dy <= reach * reach:
                        x, y = sx + dx, sy + dy
                        self.assertIn((x // cell, y // cell), covered)

    def test_tiles_keep_only_cells_within_reach(self):
        cells = area_sampling.tiles_near([(0.0, 0.0)], 500)
        self.assertEqual(cells, [(-1, -1), (-1, 0), (0, -1), (0, 0)])  # the four cells round a corner sample
        self.assertAlmostEqual(area_sampling.tile_area_ha(cells), 0.16)


if __name__ == "__main__":
    unittest.main()
