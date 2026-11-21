import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def test_noise_free_area_generator_samples_its_tiles_without_measuring(self):
        # Spatial noise off: the rescales never run, so nothing is measured and the tiles alone are charged.
        with patch.object(area_sampling, "ranges", return_value=None), patch.object(area_sampling, "pending") as pending, \
                patch.object(area_sampling, "area_graph") as built, patch.object(deadwood_rocks, "put"):
            deadwood_rocks.generator("Meadow", 600000, 25, 60, extent=8, region=[(0, 0)], bools={"EnableSpatialNoise": False})
        pending.assert_not_called()
        self.assertEqual(built.call_args.args[2], {})

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
        for x, y in foot:  # every point: the filter measures from all of them
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

def summaries(cells):
    """A terrain_cells stand-in over {(ix, iy): (z_min, z_max, slope)}."""
    return lambda predicate: sorted(c for c, summary in cells.items() if predicate(*summary))


class RegionTests(unittest.TestCase):
    SHORE = 75  # cm; the lowest any plant filter keeps is the shore height (PLANT_FLOOR less the deepest fade)

    def test_above_shore_tiles_count_the_beach_lift(self):
        cells = {(0, 0): (-500, self.SHORE - 150, 0), (1, 0): (-500, self.SHORE - 151, 0), (2, 0): (0, 900, 0)}
        with patch.object(deadwood_rocks, "terrain_cells", summaries(cells)), \
                patch.object(deadwood_rocks, "shore_height", return_value=self.SHORE):
            self.assertEqual(deadwood_rocks.above_shore_cells(), [(0, 0), (2, 0)])  # lifted 150 cm, (0, 0) reaches it

    def test_without_a_fade_the_band_starts_at_the_plant_floor(self):
        cells = {(0, 0): (-500, self.SHORE, 0), (1, 0): (-500, self.SHORE - 1, 0)}
        with patch.object(deadwood_rocks, "terrain_cells", summaries(cells)), patch.object(deadwood_rocks, "PLANT_FADE", ()), \
                patch.object(deadwood_rocks, "shore_height", return_value=self.SHORE):
            self.assertEqual(deadwood_rocks.above_shore_cells(), [(0, 0)])  # lifted 150 cm, it reaches PLANT_FLOOR

    def test_tree_ground_starts_at_the_shore_whatever_the_plant_fade(self):
        cells = {(0, 0): (-500, self.SHORE - 150, 0), (1, 0): (-500, self.SHORE - 151, 0)}
        for fade in ((), ((50, 0.35),), deadwood_rocks.PLANT_FADE):
            with self.subTest(fade=fade), patch.object(deadwood_rocks, "terrain_cells", summaries(cells)), \
                    patch.object(deadwood_rocks, "PLANT_FADE", fade), patch.object(deadwood_rocks, "shore_height", return_value=self.SHORE):
                self.assertEqual(deadwood_rocks.forest_floor_cells(), [(0, 0)])  # lifted 150 cm, (0, 0) reaches the shore

    def test_damp_tiles_are_low_or_near_water_and_above_the_shore(self):
        import saplings_understory
        cells = {(0, 0): (1199, 5000, 0), (1, 0): (1200, 5000, 0), (2, 0): (1300, 5000, 0), (3, 0): (100, 900, 0)}
        with patch.object(saplings_understory, "terrain_cells", summaries(cells)), \
                patch.object(saplings_understory, "bank_cells", return_value=[(2, 0), (9, 9)]), \
                patch.object(deadwood_rocks, "above_shore_cells", return_value=[(0, 0), (1, 0), (2, 0)]):
            # (0, 0) low by its lowest ground; (1, 0) neither low nor near; (2, 0) high but near water; (3, 0) and the
            # near-water (9, 9) below the shore
            self.assertEqual(saplings_understory.damp_cells(), [(0, 0), (2, 0)])


class KeepProperties:
    def get_editor_property(self, name):
        return getattr(self, name)

    def set_editor_property(self, name, value):
        setattr(self, name, value)

    def import_text(self, text):
        self.text = text

    def export_text(self):
        return self.text


class KeepTests(unittest.TestCase):
    def test_ramp_reads_height_from_json_and_defaults_to_identity(self):
        with TemporaryDirectory() as directory, patch.object(area_sampling, "KEEPS", Path(directory) / "blend_keep.json"):
            self.assertEqual(area_sampling.ramp("Trees"), 0.0)  # Missing file.
            area_sampling.KEEPS.write_text('{"Trees": {"ramp": 1250, "blended": 1, "unblended": 4}, "New": {"blended": 1}}')
            for group, expected in (("Trees", 1250), ("New", 0.0), ("Unknown", 0.0)):
                with self.subTest(group=group):
                    self.assertEqual(area_sampling.ramp(group), expected)

    def test_reapplication_replaces_filter_and_identity_restores_original_connection(self):
        class Noise(KeepProperties):
            pass

        graph, source, output = MagicMock(), MagicMock(), MagicMock()
        nodes, original = [source], (source, "Roots", output, "GeneratedPoints")
        edges = [original]
        graph.get_output_node.return_value = output
        graph.get_editor_property.side_effect = lambda name: nodes
        graph.remove_edge.side_effect = lambda *edge: edges.remove(edge)

        def add_node(cls):
            settings = cls()
            node = MagicMock()
            node.get_settings.return_value = settings
            nodes.append(node)
            return node, settings

        def remove_node(node):
            nodes.remove(node)
            edges[:] = [e for e in edges if node not in (e[0], e[2])]

        graph.add_node_of_type.side_effect = add_node
        graph.remove_node.side_effect = remove_node
        # Adapt only graph storage: thin() and z_range() still perform all graph/settings edits.
        with patch.multiple(area_sampling.unreal, PCGAttributeNoiseSettings=Noise,
                            PCGAttributeFilteringRangeSettings=KeepProperties,
                            PCGAttributePropertyInputSelector=KeepProperties,
                            PCGAttributePropertyOutputSelector=KeepProperties,
                            PCGAttributeFilterThresholdSettings=KeepProperties), \
                patch.object(area_sampling, "_edges", side_effect=lambda graph: iter(edges)), \
                patch.object(area_sampling, "_connect", side_effect=lambda graph, *edge: edges.append(edge)):
            for ramp in (0.0, 1250.0, 1250.0, 2500.0, -1.0, 1.0, 0.0):
                with self.subTest(ramp=ramp):
                    area_sampling.thin(graph, ramp)
                    if ramp <= 0:
                        self.assertEqual((nodes, edges), ([source], [original]))
                        continue
                    self.assertEqual(len(nodes), 3)  # One draw/filter pair, never stacked or left disconnected.
                    noise, below = nodes[1:]
                    self.assertEqual(edges, [(source, "Roots", noise, "In"), (noise, "Out", below, "In"),
                                             (below, "InsideFilter", output, "GeneratedPoints")])
                    settings, bounds = noise.get_settings(), below.get_settings()
                    self.assertEqual((settings.noise_min, settings.noise_max), (0.0, ramp))
                    self.assertEqual(settings.mode, area_sampling.unreal.PCGAttributeNoiseMode.SET)
                    self.assertEqual(settings.output_target.text, "PCGBegin(BlendKeep)PCGEnd")
                    self.assertEqual(bounds.target_attribute.text, settings.output_target.text)
                    self.assertIn("DoubleValue=0.0)", bounds.min_threshold.text)
                    self.assertIn("bInclusive=True,bUseConstantThreshold=True", bounds.min_threshold.text)
                    self.assertIn("bInclusive=False,bUseConstantThreshold=False", bounds.max_threshold.text)
                    self.assertIn("ThresholdAttribute=PCGBegin($Position.Z)PCGEnd", bounds.max_threshold.text)


class ParentTests(unittest.TestCase):
    """Every generator is copied from the Trees instance, whose own parent is cropped to the Trees' area: generator()
    must give each copy its parent, before any parameter (changing the parent resets them)."""

    def build(self, region):
        order, instance = MagicMock(), MagicMock()
        with patch.object(deadwood_rocks, "copy_asset", return_value=instance), \
                patch.object(deadwood_rocks, "load", side_effect=lambda path: f"loaded {path}"), \
                patch.object(deadwood_rocks.unreal, "PCGGraphParametersHelpers") as helpers, \
                patch.object(area_sampling, "ranges", return_value={}), patch.object(area_sampling, "area_graph", return_value="own area"), \
                patch.object(deadwood_rocks, "put"):
            order.attach_mock(instance.set_editor_property, "parent")
            order.attach_mock(helpers.set_double_parameter, "parameter")
            deadwood_rocks.generator("Example", 100, 25, 60, region=region, bools={"EnableSpatialNoise": False})
        calls = [name for name, args, _ in order.mock_calls if name == "parameter" or args[0] == "graph"]
        parent = next(args[1] for name, args, _ in order.mock_calls if name == "parent" and args[0] == "graph")
        return parent, calls

    def test_a_generator_without_a_region_takes_the_template(self):
        parent, calls = self.build(None)
        self.assertEqual(parent, f"loaded {area_sampling.TEMPLATE}")
        self.assertEqual(calls[0], "parent")

    def test_an_area_generator_takes_its_own_area_graph(self):
        parent, calls = self.build([(0, 0)])
        self.assertEqual(parent, "own area")
        self.assertEqual(calls[0], "parent")


if __name__ == "__main__":
    unittest.main()
