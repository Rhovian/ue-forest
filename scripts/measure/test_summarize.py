"""Offline regression for the CSV profiler's growing-column layout."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SummarizeTests(unittest.TestCase):
    def test_frame_counts_and_statistics(self):
        header = ["EVENTS", "FrameTime", "GPUTime", "Exclusive/RenderThread/Base",
                  "Exclusive/RenderThread/EventWait/Foo"]
        final = header + ["Exclusive/RenderThread/Late"]
        captures = {
            "growing": [header, ["", 1000, 0.99, 1000, 999], ["", 10, 1, 1, 999],
                        ["", 20, 3, 2, 999, 4], ["stop; dump", 30, 5, 3, 999, 8], final,
                        ["[HasHeaderRowAtEnd]", 1, "[platform]", "Mac"]],
            "single": [header, ["event", 12, 2, 4, 999], ["", 1000, 0, 1000, 999],
                       ["[HasHeaderRowAtEnd]", 0]],
            "under_half": [header, ["", 1000, 0, 1000, 999], ["event", 12, 2, 4, 999],
                           ["", 1000, 0, 1000, 999]],
            "unrendered": [header, ["", 1000, 0, 1000, 999]],
            "empty": [header],
        }
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "manifest.json").write_text(json.dumps({"map": "test", "cvars": {}, "points": list(captures)}))
            for point, rows in captures.items():
                with (run / f"{point}.csv").open("w", newline="") as f:
                    csv.writer(f).writerows(rows)
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize.py")), tmp],
                                    capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("| frames used / captured |", result.stdout)
        expected = {
            "growing": "3 / 4 | 20.00 / 38.00 | n/a | 6.00 / 15.00 | 3.00 / 6.60 | n/a | n/a | n/a",
            "single": "1 / 2 | 12.00 / 12.00 | n/a | 4.00 / 4.00 | 2.00 / 2.00 | n/a | n/a | n/a",
            "under_half": "1 / 3 (under half rendered) | 12.00 / 12.00 | n/a | 4.00 / 4.00 | 2.00 / 2.00 | n/a | n/a | n/a",
            "unrendered": "0 / 1 (under half rendered) | no frames rendered | - | - | - | - | - | -",
            "empty": "0 / 0 | no frames rendered | - | - | - | - | - | -",
        }
        for point, cells in expected.items():
            with self.subTest(point=point):
                self.assertIn(f"| {point} | {cells} |", result.stdout.splitlines())

    def test_row_wider_than_available_header_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "manifest.json").write_text(json.dumps({"map": "test", "cvars": {}, "points": ["cut_short"]}))
            (run / "cut_short.csv").write_text("FrameTime,GPUTime\n12,2,4\n[HasHeaderRowAtEnd],0\n")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize.py")), tmp],
                                    capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("row 2 has 3 cells, header has 2", result.stderr)


if __name__ == "__main__":
    unittest.main()
