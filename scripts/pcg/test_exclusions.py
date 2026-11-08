import itertools
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import canopy_gaps
import exact_exclusions
import saplings_understory
from water_exclusions import KEEPOUT_TAG


class TwoTierExclusionTests(unittest.TestCase):
    def test_ground_plants_reach_the_narrow_water_exclusion_only(self):
        for name in ("PCG_PlantsAboveShore", "PCG_UnderstoryDamp", "PCG_UnderstoryBankNear", "PCG_FernsDrift2",
                     "PCG_HerbsDrift0", "PCG_BalsamDrift1"):
            self.assertEqual(exact_exclusions.exclusion_tags(name), ["PCG_BiomeExclusion"], name)

    def test_every_other_group_also_keeps_out_of_the_wider_keepout(self):
        for name in ("PCG_TreesAboveShore", "PCG_DeadwoodAboveShore", "PCG_RockBase_wdbncbl_tier_2",
                     "PCG_SaplingsCanopyGaps", "PCG_MeadowGround"):
            self.assertIn(KEEPOUT_TAG, exact_exclusions.exclusion_tags(name), name)

    def test_reruns_install_only_missing_tags(self):
        self.assertEqual(exact_exclusions.missing("PCG_TreesAboveShore", []), ["PCG_BiomeExclusion", KEEPOUT_TAG])
        self.assertEqual(exact_exclusions.missing("PCG_TreesAboveShore", ["PCG_BiomeExclusion"]), [KEEPOUT_TAG])
        self.assertEqual(exact_exclusions.missing("PCG_TreesAboveShore", ["PCG_BiomeExclusion", KEEPOUT_TAG]), [])
        self.assertEqual(exact_exclusions.missing("PCG_PlantsAboveShore", ["PCG_BiomeExclusion"]), [])

    def test_canopy_gaps_keep_clear_of_the_keepout_too(self):
        self.assertTrue(canopy_gaps.is_exclusion(["PCG_BiomeExclusion"]))
        self.assertTrue(canopy_gaps.is_exclusion([KEEPOUT_TAG]))
        self.assertFalse(canopy_gaps.is_exclusion(["Something_Else"]))


class BankFalloffTests(unittest.TestCase):
    def test_bands_are_contiguous_and_density_falls_off_inland(self):
        banks = saplings_understory.BANKS
        self.assertGreaterEqual(len(banks), 2)  # one band would be the constant-density band the falloff replaced
        self.assertEqual(banks[0][1], 0)
        for (_, _, outer, near), (_, inner, _, far) in itertools.pairwise(banks):
            self.assertEqual(outer, inner)
            for kind, share in far.items():
                self.assertLess(share, near[kind], kind)

    def test_each_band_drops_what_the_nearer_band_covers(self):
        # Distance gives density = distance / outer; a band keeps [lower, 0.99), so its lower bound is inner / outer.
        for _, inner, outer, _ in saplings_understory.BANKS:
            lower = saplings_understory.band_lower(inner, outer)
            self.assertAlmostEqual(lower * outer, inner)
        self.assertGreater(saplings_understory.band_lower(*saplings_understory.BANKS[1][1:3]), 0)


if __name__ == "__main__":
    unittest.main()
