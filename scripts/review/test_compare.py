"""Offline reference matching checks; rendering is also checked on real captures."""
import contextlib
import io
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

COMPARE = Path(__file__).with_name("compare")


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tool = runpy.run_path(str(COMPARE))

    def test_document_matching(self):
        notes = self.tool["read_notes"](self.tool["NOTES"])
        pairs = self.tool["pairings"]
        edge = pairs("edge_in", notes)
        self.assertEqual([name for name, _ in edge], [f"edge_in_{n:02}.png" for n in range(1, 6)])
        self.assertTrue(all(targets.strip() for targets in notes.values()))
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
            failure = subprocess.CompletedProcess(["sips"], 2, stdout="decoder stdout", stderr="decoder stderr")
            for runner, details in ((subprocess.run, ("Invalid capture or reference image",)),
                                    (unittest.mock.Mock(return_value=failure), ("decoder stdout", "decoder stderr"))):
                with self.subTest(details=details), patch("subprocess.run", runner):
                    with self.assertRaises(ValueError) as raised:
                        self.tool["render"](capture, reference, "Targets", output)
                    for detail in (str(capture), str(reference), *details):
                        self.assertIn(detail, str(raised.exception))
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["sips"], 60)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.tool["render"](capture, reference, "Targets", output)
                self.assertEqual(run.call_args.kwargs["timeout"], 60)
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
            for heading in ("edge_in_6.png", "Edge_in_06.png"):
                path.write_text(f"## References\n### {heading} — bad\n- Targets: target\n")
                with self.subTest(heading=heading), self.assertRaisesRegex(ValueError, "invalid reference heading"):
                    read(path)
            path.write_text("## References\n### interior_01.png — a\n- Targets: a\n"
                            "### interior_01.png — b\n- Targets: b\n")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read(path)

    def test_main_missing_reference_is_rendered_without_substitution_and_orphan_is_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "art-direction.md"
            notes.write_text("## References\n### edge_in_03.png — missing\n- Targets: debris\n")
            refs = root / "art-direction"
            refs.mkdir()
            (refs / "edge_in_06.png").touch()
            capture = root / "edge_in.png"
            shutil.copyfile(self.tool["NOTES"].parent / "art-direction/interior_01.png", capture)
            main = self.tool["main"]
            real_run = subprocess.run
            calls = []

            def record(args, **kwargs):
                data = json.loads(Path(args[2]).read_text().split(";\n", 1)[0].removeprefix("const data = "))
                calls.append((args[3:-2], data["count"]))
                return real_run(args, **kwargs)

            stderr = io.StringIO()
            with patch.dict(main.__globals__, NOTES=notes), patch.object(sys, "argv", ["compare", tmp, str(root / "out")]), \
                    patch("subprocess.run", record), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertTrue((root / "out/edge_in__edge_in_03.png").is_file())
            self.assertEqual(calls, [([str(capture.resolve())], 1)])
            self.assertIn(f"MISSING REFERENCE: {refs / 'edge_in_03.png'}", stderr.getvalue())
            self.assertIn(f"MISSING NOTES: {refs / 'edge_in_06.png'}", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
