"""shore_band's floor is the lifted land height and its top the true height (#241 review): the lift is 1 across the
whole interior, so a top on LandZ would move the meadow's TOP and the damp cap island-wide.

    python3 -m unittest scripts/pcg/test_land_band.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("unreal", MagicMock())
sys.path.insert(0, str(Path(__file__).parent))

import trees_above_shore as shore


class ShoreBandTests(unittest.TestCase):
    def filters(self, low, high):
        """[(attribute, (min, inclusive), (max, inclusive))] for each range filter shore_band builds."""
        texts = []
        selector, threshold = MagicMock(), MagicMock()
        selector.import_text.side_effect = lambda text: texts.append(("attribute", text))
        threshold.import_text.side_effect = lambda text: texts.append(("threshold", text))
        graph = MagicMock()
        graph.add_node_of_type.side_effect = lambda cls: (MagicMock(), MagicMock())
        with patch.object(shore.unreal, "PCGAttributePropertyInputSelector", return_value=selector), \
                patch.object(shore.unreal, "PCGAttributeFilterThresholdSettings", return_value=threshold), \
                patch.object(shore, "link"):
            shore.shore_band(graph, low, high)

        def bound(text):
            return float(text.split("DoubleValue=")[1].removesuffix("))")), "bInclusive=True" in text

        out = []
        for i in range(0, len(texts), 3):
            (_, attribute), (_, low_text), (_, high_text) = texts[i:i + 3]
            out.append((attribute, bound(low_text), bound(high_text)))
        return out

    def test_floor_on_land_height_top_on_true_height(self):
        floor, top = self.filters(75.0, 300.0)
        self.assertEqual(floor, ("PCGBegin(LandZ)PCGEnd", (75.0, True), (1.0e7, False)))
        self.assertEqual(top, ("PCGBegin($Position.Z)PCGEnd", (-1.0e7, True), (300.0, False)))

    def test_meadow_point_inland_is_kept_by_its_true_height(self):
        """Raw 200 cm with the full lift: LandZ 350 is above TOP, the true height is not."""
        (_, (low, _), _), (_, _, (top, inclusive)) = self.filters(75.0, 300.0)
        raw, land = 200.0, 200.0 + 150.0
        self.assertTrue(land >= low and raw < top and not inclusive)
        self.assertFalse(land < top)


if __name__ == "__main__":
    unittest.main()
