import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    # 600,000/ha at extent 8 is ~185 million candidates island-wide but ~0.4 million on one tile.
    def test_measured_area_generator_is_charged_its_tiles(self):
        with patch.object(area_sampling, "ranges", return_value={}), patch.object(area_sampling, "area_graph") as built, \
                patch.object(deadwood_rocks, "put"):
            deadwood_rocks.generator("Meadow", 600000, 25, 60, extent=8, region=[(0, 0)])
        built.assert_called_once()

    def test_measuring_area_generator_is_charged_the_whole_island(self):
        with patch.object(area_sampling, "ranges", return_value=None), patch.object(area_sampling, "pending"), \
                patch.object(area_sampling, "area_graph"), self.assertRaisesRegex(RuntimeError, "million points"):
            deadwood_rocks.generator("Meadow", 600000, 25, 60, extent=8, region=[(0, 0)])

    def test_ranges_are_measured_again_when_generator_settings_change(self):
        stored = {"Herbs": {"inputs": {"PointsPerSquareMeter": 0.02}, "ranges": {"AttributeRemap_1": [0.0, 0.9]}}}
        with patch.object(area_sampling, "_load", return_value=stored):
            self.assertEqual(area_sampling.ranges("Herbs", {"PointsPerSquareMeter": 0.02}), {"AttributeRemap_1": (0.0, 0.9)})
            self.assertIsNone(area_sampling.ranges("Herbs", {"PointsPerSquareMeter": 0.01}))  # --density-scale 0.5
            self.assertIsNone(area_sampling.ranges("Ferns", {"PointsPerSquareMeter": 0.02}))


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

    def test_foot_cells_cover_the_reach_of_every_foot_point(self):
        import json
        reach, cell = 500, area_sampling.TILE
        covered = set(deadwood_rocks.foot_cells(reach))
        foot = json.loads(Path(deadwood_rocks.__file__).with_name("forest_foot.json").read_text())["points_m"]
        for x, y in foot[::50]:
            for dx, dy in ((reach, 0), (-reach, 0), (0, reach), (0, -reach), (0, 0)):
                self.assertIn(((x * 100 + dx) // cell, (y * 100 + dy) // cell), covered)


NOISE_VORONOI = {"EnableSpatialNoise": True, "EnableVoronoiNoiseBreakup": True}


# A distinct value per probe, so a min read in place of a max (or one rescale's probes for another's) shows.
PROBES = {f"AttributeReduce_{i}": (i + 1) / 8 for i in range(6)}


class MeasureTests(unittest.TestCase):
    def test_every_rescale_the_settings_run_is_measured_from_its_own_probes(self):
        with patch.object(area_sampling, "_probe_value", side_effect=lambda group, reduce: PROBES[reduce]):
            self.assertEqual(area_sampling.measure_ranges("Herbs", NOISE_VORONOI),
                             {"AttributeRemap_1": (1 / 8, 2 / 8), "AttributeRemap_2": (3 / 8, 4 / 8), "AttributeRemap_3": (5 / 8, 6 / 8)})
            self.assertEqual(area_sampling.measure_ranges("Herbs", {"EnableSpatialNoise": True, "EnableVoronoiNoiseBreakup": False}),
                             {"AttributeRemap_1": (1 / 8, 2 / 8)})

    def test_a_missing_probe_of_a_running_rescale_raises(self):
        for lost in ("AttributeReduce_0", "AttributeReduce_1", "AttributeReduce_5"):  # an interrupted run lost one export
            def probe(group, reduce, lost=lost):
                return None if reduce == lost else 0.5
            with self.subTest(lost=lost), patch.object(area_sampling, "_probe_value", side_effect=probe), \
                    self.assertRaises(RuntimeError):
                area_sampling.measure_ranges("Herbs", NOISE_VORONOI)

if __name__ == "__main__":
    unittest.main()
