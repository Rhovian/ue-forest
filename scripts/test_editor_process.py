"""Bounded command trees stop on timeout, terminal signals, and caller death; no editor involved."""
import os
import runpy
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parent


class ProcessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        project = self.root / "Fixture.uproject"
        project.touch()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.env = dict(os.environ, HOME=str(self.root), EDITOR_UPROJECT=str(project), EDITOR_PORT=str(port))
        for name in ("editor.sh", "editor_process.py"):
            if (SCRIPTS / name).exists():
                shutil.copy(SCRIPTS / name, self.root / name)
        self.pids = self.root / "pids"
        tree = self.root / "tree"
        tree.write_text(f'''#!/usr/bin/env python3
import os, subprocess, time
from pathlib import Path
with open(os.devnull, 'rb+') as null:
    for fd in (0, 1, 2): os.dup2(null.fileno(), fd)
child = subprocess.Popen(['sleep', '30'])
Path({str(self.pids)!r}).write_text(f'{{os.getpid()}} {{child.pid}}')
time.sleep(30)
''')
        tree.chmod(0o755)
        self.tree = tree
        self.addCleanup(self.stop_tree)

    def active_pids(self):
        active = []
        for pid in map(int, self.pids.read_text().split()):
            state = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="], check=False,
                                   capture_output=True, text=True, timeout=1)
            if state.returncode == 0 and not state.stdout.strip().startswith("Z"):
                active.append(pid)
        return active

    def stop_tree(self):
        if self.pids.exists() and self.active_pids():
            os.killpg(int(self.pids.read_text().split()[0]), signal.SIGKILL)

    def caller(self, seconds, polling=False):
        body = 'source "$1"; bounded "$2" "$3"'
        if polling:
            body = ('source "$1"; wait_for 1 "test polling command" bounded "$2" "$3" || true; '
                    f'echo continued > "{self.root / "continued"}"')
        caller = subprocess.Popen(["bash", "-c", body, "caller",
                                   str(self.root / "editor.sh"), str(seconds), str(self.tree)],
                                  env=self.env, start_new_session=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(caller.stderr.close)
        self.addCleanup(caller.stdout.close)
        self.addCleanup(caller.wait, 5)
        def stop_caller():
            self.stop_tree()
            if caller.poll() is None:
                caller.kill()
        self.addCleanup(stop_caller)
        end = time.monotonic() + 3
        while not self.pids.exists():
            self.assertLess(time.monotonic(), end, "test command tree did not start")
            time.sleep(.01)
        return caller

    def assert_tree_stopped(self):
        end = time.monotonic() + 3
        active = []
        while time.monotonic() < end:
            active = self.active_pids()
            if not active:
                return
            time.sleep(.02)
        self.assertEqual(active, [], "bounded command tree survived cancellation")

    def test_timeout_stops_the_command_process_group_including_children(self):
        caller = self.caller(.5)
        stdout, stderr = caller.communicate(timeout=5)
        self.assertEqual(caller.returncode, 124, stdout + stderr)
        self.assertIn("timed out after 0.5s", stderr)
        self.assertIn("process group stopped", stderr)
        self.assert_tree_stopped()

    def test_terminal_signals_and_caller_sigkill_stop_the_tree(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGKILL):
            with self.subTest(signal=sig):
                self.pids.unlink(missing_ok=True)
                caller = self.caller(30)
                try:
                    os.killpg(caller.pid, sig)
                    self.assert_tree_stopped()
                finally:
                    self.stop_tree()
                    caller.communicate(timeout=5)
                self.assertNotEqual(caller.returncode, 0)

    def test_sigint_stops_a_polling_shell_instead_of_being_swallowed(self):
        caller = self.caller(30, polling=True)
        os.killpg(caller.pid, signal.SIGINT)
        output, error = caller.communicate(timeout=5)
        self.assertEqual(caller.returncode, -signal.SIGINT, output + error)
        self.assertFalse((self.root / "continued").exists(), "polling shell continued after Ctrl-C")
        self.assert_tree_stopped()

    def test_zombie_only_group_preserves_completed_command_status(self):
        supervise = runpy.run_path(str(SCRIPTS / "editor_process.py"))["supervise"]
        process = Mock(returncode=7)
        process.poll.return_value = 7
        with patch("signal.signal"), patch("subprocess.Popen", return_value=process), \
                patch("select.select", return_value=([], [], [])), \
                patch("os.killpg", side_effect=PermissionError("macOS zombie-only group")):
            try:
                code = supervise("1", ["fixture"])
            except PermissionError:
                self.fail("zombie-only group cleanup replaced the completed command's exit status")
            self.assertEqual(code, 7)
        # A permission error while the command is still live must remain an error.
        process.poll.return_value = None
        with patch("signal.signal"), patch("subprocess.Popen", return_value=process), \
                patch("select.select", side_effect=[([], [], []), ([0], [], [])]), \
                patch("os.read", return_value=b""), patch("os.killpg", side_effect=PermissionError), \
                self.assertRaises(PermissionError):
            supervise("1", ["fixture"])

    def test_killing_only_the_calling_shell_stops_the_tree(self):
        caller = self.caller(30)
        try:
            caller.kill()
            self.assert_tree_stopped()
        finally:
            self.stop_tree()
            caller.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
