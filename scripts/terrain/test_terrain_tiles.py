import importlib
import json
import math
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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
        self.assertEqual([(c[0], c[1]) for c in data["cells"]],
                         [(x, y) for x in range(-2, 3) for y in range(-2, 2)])
        for _, _, low, high, slope in data["cells"]:
            self.assertLessEqual(known, slope)
            self.assertLess(slope - known, 0.001)
        cell = next(c for c in data["cells"] if c[:2] == [0, 0])
        self.assertAlmostEqual(cell[2], -300)
        self.assertAlmostEqual(cell[3], 1100)

    def test_step_flags_both_sides_including_the_one_vertex_border(self):
        for axis in (0, 1):
            with self.subTest(axis=axis):
                height = np.zeros((61, 61))
                # x/y = 20 to 22 m: tile 0's border must see the step just beyond it.
                height[(slice(41, None), slice(None)) if axis == 0 else (slice(None), slice(41, None))] = 4
                cells = summaries(height, 2)["cells"]
                along = {c[1 - axis] for c in cells if c[4] >= 45}
                self.assertEqual(along, {0, 1})

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
        data = {"slope_margin_deg": 3.0, "cells": [[1, 0, -20, 80, 35], [-2, 4, 10, 40, 28],
                                                     [0, 0, 100, 120, 40], [-1, 0, 10, 30, 2]]}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "terrain_tiles.json"
            path.write_text(json.dumps(data))
            with patch.object(terrain_regions, "DATA", path), patch.dict(sys.modules, numpy=None, unreal=None):
                self.assertEqual(terrain_regions.terrain_cells(lambda lo, hi, s: lo < 50 and hi < 100 and s >= 27),
                                 [(-2, 4), (1, 0)])
                self.assertEqual(terrain_regions.terrain_cells(lambda *_: False), [])
                self.assertEqual(terrain_regions.terrain_slope_margin(), 3.0)
                # Reimport with unavailable UE/scientific dependencies, as in UE's Python.
                importlib.reload(terrain_regions)

    def test_landscape_normals_include_diagonal_triangles(self):
        height = np.zeros((3, 3))
        height[2, 2] = 2
        # Centre touches four flat faces plus normals (0,-1,1) and (-1,0,1), normalised.
        xy, z = -1 / math.sqrt(2), 4 + math.sqrt(2)
        component = xy / math.sqrt(2 * xy * xy + z * z)
        packed = math.floor(127.5 * (component + 1) + 0.5) / 127.5 - 1
        expected = math.degrees(math.asin(math.sqrt(2) * abs(packed)))
        self.assertAlmostEqual(landscape_slopes(height, 2)[1, 1], expected)

    def test_margin_accounts_for_packed_flat_normal(self):
        data = summaries(np.zeros((21, 21)), 2)
        self.assertTrue(all(c[4] == 0 for c in data["cells"]))
        # Even a flat normal packs XY=128,128, decoded as (1/255,1/255).
        packed_slope = math.degrees(math.asin(math.sqrt(2) / 255))
        self.assertGreaterEqual(data["slope_margin_deg"], packed_slope)
        self.assertLess(data["slope_margin_deg"], packed_slope + 0.02)


if __name__ == "__main__":
    unittest.main()
