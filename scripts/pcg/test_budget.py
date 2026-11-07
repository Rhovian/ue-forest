import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

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


if __name__ == "__main__":
    unittest.main()
