"""Offline reference matching checks; rendering is also checked on real captures."""
import runpy
import tempfile
import unittest
from pathlib import Path

COMPARE = Path(__file__).with_name("compare")


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tool = runpy.run_path(str(COMPARE))

    def test_document_matching(self):
        notes = self.tool["read_notes"](self.tool["NOTES"])
        pairs = self.tool["pairings"]
        edge = pairs("edge_in", notes)
        self.assertEqual([name for name, _ in edge], [f"edge_in_{n:02}.png" for n in range(1, 6)])
        self.assertIn("debris band runs the length", dict(edge)["edge_in_03.png"])
        self.assertIn("unbroken fern/understory band", dict(edge)["edge_in_02.png"])
        self.assertEqual(pairs("high_point_eye", notes), pairs("high_point", notes))
        self.assertEqual([name for name, _ in pairs("canopy_up", notes)], ["canopy_up_01.png"])
        with self.assertRaisesRegex(ValueError, "unknown view"):
            pairs("edge", notes)
        with self.assertRaisesRegex(ValueError, "no reference notes"):
            pairs("interior", {})

    def test_invalid_capture_cannot_shift_reference_into_capture_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / "interior.png"
            capture.write_text("not an image")
            reference = self.tool["NOTES"].parent / "art-direction/interior_01.png"
            output = Path(tmp) / "comparison.png"
            with self.assertRaisesRegex(ValueError, "sips did not produce"):
                self.tool["render"](capture, reference, "Targets", output)
            self.assertFalse(output.exists())

    def test_notes_do_not_use_prompt_or_template_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.md"
            path.write_text("### interior\n- Targets: wrong\n## References\n"
                            "### interior_01.png — first\n- Take: take\n- Targets: first;\n  continued.\n"
                            "### interior_02.png — second\n- Targets: second.\n")
            read = self.tool["read_notes"]
            self.assertEqual(read(path), {"interior_01.png": "first; continued.",
                                          "interior_02.png": "second."})
            path.write_text("## References\n### interior_01.png — broken\n- Take: only\n")
            with self.assertRaisesRegex(ValueError, "Targets"):
                read(path)
            path.write_text("## References\n### interior_01.png — a\n- Targets: a\n"
                            "### interior_01.png — b\n- Targets: b\n")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read(path)


if __name__ == "__main__":
    unittest.main()
