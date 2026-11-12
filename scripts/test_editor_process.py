"""Bounded command trees stop on timeout, terminal signals, and caller death; no editor involved."""
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

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

    def caller(self, seconds):
        caller = subprocess.Popen(["bash", "-c", 'source "$1"; bounded "$2" "$3"', "caller",
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
