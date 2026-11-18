import importlib
import json
import math
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from scripts.pcg import terrain_regions
from scripts.terrain.terrain_tiles import TILE, landscape_slopes, summaries


class TerrainTileTests(unittest.TestCase):
    def test_tilted_plane_has_known_slope_and_raw_height_extrema(self):
        row, col = np.indices((31, 41))
        height = -3 + (col - 20) * 2 * 0.3 + (row - 15) * 2 * 0.4
        data = summaries(height, 2)
        known = math.degrees(math.atan(0.5))
        self.assertTrue(all(abs(c[4] - known) < 0.5 for c in data["cells"]))  # 8-bit normal packing
        cell = next(c for c in data["cells"] if c[:2] == [0, 0])
        self.assertAlmostEqual(cell[2], -300)
        self.assertAlmostEqual(cell[3], 1100)

    def test_step_bounds_every_supporting_normal_and_flags_both_sides(self):
        for axis in (0, 1):
            with self.subTest(axis=axis):
                height = np.zeros((61, 61))
                # The face at 20..22 m contributes to supporting vertices in both cells.
                height[(slice(41, None), slice(None)) if axis == 0 else (slice(None), slice(41, None))] = 4
                cells = summaries(height, 2)["cells"]
                along = {c[1 - axis] for c in cells if c[4] >= 30}
                self.assertEqual(along, {0, 1})
                y, x = (np.indices(height.shape) - 30) * 200
                model = landscape_slopes(height, 2)
                for ix, iy, _, _, slope in cells:
                    support = (x >= ix * TILE) & (x <= (ix + 1) * TILE) & (y >= iy * TILE) & (y <= (iy + 1) * TILE)
                    self.assertGreaterEqual(slope, model[support].max())
                    self.assertLess(slope - model[support].max(), 0.001)

    def test_indexing_agrees_with_tiles_near_at_negative_world_position(self):
        with patch.dict(sys.modules, unreal=MagicMock()):
            from scripts.pcg import area_sampling
        self.assertEqual(TILE, area_sampling.TILE)
        expected = area_sampling.tiles_near([(-2150, 650)], 0)
        self.assertEqual(expected, [(-2, 0)])
        height = np.full((31, 41), -7.0)
        height[18, 9] = -2  # world (-2200, 600) cm, rows along +Y
        cells = summaries(height, 2)["cells"]
        self.assertEqual([(x, y) for x, y, _, high, _ in cells if high == -200], expected)

    def test_reader_filters_all_summary_fields_and_sorts_without_numpy(self):
        data = {"cells": [[1, 0, -20, 80, 35], [-2, 4, 10, 40, 30], [0, 0, 100, 120, 40], [-1, 0, 10, 30, 2]]}
        with patch.object(terrain_regions, "DATA") as source, patch.dict(sys.modules, numpy=None, unreal=None):
            source.read_text.return_value = json.dumps(data)
            self.assertEqual(terrain_regions.terrain_cells(lambda lo, hi, s: lo < 50 and hi < 100 and s >= 30),
                             [(-2, 4), (1, 0)])
            self.assertEqual(terrain_regions.terrain_cells(lambda *_: False), [])
            importlib.reload(terrain_regions)

    def test_landscape_normals_include_diagonal_triangles(self):
        height = np.zeros((3, 3))
        height[2, 2] = 2
        # Centre touches four flat faces plus normals (0,-1,1) and (-1,0,1), normalised.
        xy, z = -1 / math.sqrt(2), 4 + math.sqrt(2)
        component = xy / math.sqrt(2 * xy * xy + z * z)
        packed = math.floor(127.5 * (component + 1) + 0.5) / 127.5 - 1
        self.assertAlmostEqual(landscape_slopes(height, 2)[1, 1], math.degrees(math.asin(math.sqrt(2) * abs(packed))))

    def test_packing_chooses_steeper_code_only_near_a_tie(self):
        for offset, code in ((-0.0015, 191), (-0.0005, 192), (0.0005, 192), (0.0015, 192)):
            component = (191.5 + offset) / 127.5 - 1
            rise = component / math.sqrt(1 - component * component)
            height = np.tile(np.arange(3) * 2 * rise, (3, 1))
            expected = math.degrees(math.asin(math.hypot(code / 127.5 - 1, 1 / 255)))
            with self.subTest(offset=offset):
                self.assertAlmostEqual(landscape_slopes(height, 2).max(), expected)


if __name__ == "__main__":
    unittest.main()
