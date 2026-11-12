"""Offline queue publication checks, including cancellation after a probe has been picked up."""
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
INIT = SCRIPTS.parent / "Forest/Content/Python/init_unreal.py"


class QueueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        unreal = types.SimpleNamespace(Paths=types.SimpleNamespace(project_saved_dir=lambda: str(self.root)),
                                       register_slate_post_tick_callback=lambda callback: None)
        with patch.dict(sys.modules, unreal=unreal):
            self.queue = runpy.run_path(str(INIT))
        self.folder = self.root / "EditorPy"

    def test_normal_request_keeps_its_existing_result_protocol(self):
        (self.folder / "in/normal.py").write_text("print('normal result')")
        self.queue["_run"]("normal.py")
        self.assertEqual(json.loads((self.folder / "out/normal.json").read_text()),
                         {"ok": True, "output": "normal result\n"})

    def probe_client(self, timeout):
        env = dict(os.environ, EDITOR_PY_ROOT=str(self.folder), EDITOR_PY_TIMEOUT=timeout)
        client = subprocess.Popen([str(SCRIPTS / "editor-py"), "--probe"], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(client.stdout.close)
        self.addCleanup(client.stderr.close)
        self.addCleanup(client.wait, 3)
        self.addCleanup(client.kill)
        end = time.monotonic() + 3
        while not (requests := list((self.folder / "in").glob("*.py"))):
            self.assertLess(time.monotonic(), end, "probe did not queue its request")
            time.sleep(.01)
        return client, requests[0]

    def test_successful_probe_reads_its_private_reply_and_cleans_it(self):
        client, request = self.probe_client("3")
        self.queue["_run"](request.name)
        output, error = client.communicate(timeout=3)
        self.assertEqual(client.returncode, 0, error)
        self.assertIn("editor-py round trip OK", output)
        self.assertEqual(list((self.folder / "out").iterdir()), [])

    def test_late_probe_publication_leaves_no_result_after_cancellation(self):
        client, request = self.probe_client(".3")
        replace = os.replace

        def delayed_publication(source, destination):
            _, error = client.communicate(timeout=3)  # let cancellation happen after pickup, before publication
            self.assertNotEqual(client.returncode, 0)
            self.assertIn("probe request removed", error)
            return replace(source, destination)

        with patch("os.replace", delayed_publication):
            self.queue["_run"](request.name)
        self.assertEqual(list((self.folder / "in").iterdir()), [])
        self.assertEqual(list((self.folder / "out").iterdir()), [], "late probe result survived cancellation")

    def test_probe_cancelled_between_directory_scan_and_pickup_is_skipped(self):
        try:
            self.queue["_run"]("probe-gone.py")
        except FileNotFoundError:
            self.fail("cancelled probe crashed the queue pickup")
        with self.assertRaises(FileNotFoundError):
            self.queue["_run"]("ordinary-missing.py")


if __name__ == "__main__":
    unittest.main()
