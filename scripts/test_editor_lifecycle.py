"""Exercise lifecycle safety on ephemeral ports and private project/process fixtures, never UE."""
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


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "Forest.uproject"
        self.project.touch()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.env = dict(os.environ, EDITOR_PORT=str(self.port), EDITOR_UPROJECT=str(self.project),
                        EDITOR_LOG=str(self.root / "editor.log"), EDITOR_OPEN_TIMEOUT="3",
                        PYTHONPATH=str(SCRIPTS))
        for name in ("editor.sh", "editor-mcp"):
            shutil.copy(SCRIPTS / name, self.root / name)
        self.script("editor-py", "#!/bin/sh\necho python-queue-ok\n")
        self.script("launch", '''#!/usr/bin/env python3
import os, time
from pathlib import Path
Path(os.environ['MARKER']).write_text(str(os.getpid()))
if not os.environ.get('NO_LOG'):
    Path(os.environ['EDITOR_LOG']).write_text(os.environ.get('LOG_TEXT', 'fresh log'))
if os.environ.get('LISTEN'):
    from http.server import ThreadingHTTPServer
    from test_editor_mcp import Hung
    server = ThreadingHTTPServer(('127.0.0.1', int(os.environ['EDITOR_PORT'])), Hung)
    server.hang, server.closing = os.environ.get('HANG'), False
    server.serve_forever()
else:
    time.sleep(30)
''')
        self.env.update(EDITOR_LAUNCH=str(self.root / "launch"), MARKER=str(self.root / "pid"))
        self.addCleanup(self.stop_launch)

    def script(self, name, source):
        path = self.root / name
        path.write_text(source)
        path.chmod(0o755)

    def stop_launch(self):
        marker = self.root / "pid"
        if marker.exists():
            try:
                os.kill(int(marker.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass

    def run_editor(self, action, ok=False):
        result = subprocess.run([str(self.root / "editor.sh"), action], check=False, env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def listener(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", self.port))
        sock.listen()
        self.addCleanup(sock.close)
        return sock

    def test_stale_listener_refuses_before_launch_and_names_holder(self):
        self.listener()
        output = self.run_editor("open")
        self.assertIn(f"port {self.port} held by", output)
        self.assertIn(str(os.getpid()), output)
        self.assertIn("python", output.lower())
        self.assertFalse((self.root / "pid").exists())
        # No editor is running: close must still diagnose a foreign holder.
        self.assertIn(str(os.getpid()), self.run_editor("close"))

    def test_listener_started_after_preflight_must_belong_to_launched_pid(self):
        # The launched stub signals readiness without binding. Start our unrelated listener then.
        process = subprocess.Popen([str(self.root / "editor.sh"), "open"], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(process.kill if process.poll() is None else lambda: None)
        deadline = time.monotonic() + 5
        while not (self.root / "pid").exists():
            self.assertLess(time.monotonic(), deadline, "stub launch did not start")
            time.sleep(0.01)
        self.listener()
        stdout, stderr = process.communicate(timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("not owned exclusively", stderr)
        self.assertIn(str(os.getpid()), stderr)
        self.assertNotIn("MCP up", stdout)

    def test_owned_listener_and_successful_round_trip_are_ready(self):
        (self.root / "editor.log").write_text(f"HttpListener unable to bind to 127.0.0.1:{self.port}")
        self.env["LISTEN"] = "1"
        self.assertIn("MCP up", self.run_editor("open", ok=True))

    def test_launch_survives_calling_shell_exit_and_sighup_in_its_own_session(self):
        self.env["LISTEN"] = "1"
        caller = subprocess.Popen(["bash", "-c", ('trap : HUP; "$1" open; result=$?; '
                                   'kill -HUP -- -$$; exit "$result"'), "caller", str(self.root / "editor.sh")],
                                  env=self.env, start_new_session=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        self.addCleanup(caller.kill)
        stdout, stderr = caller.communicate(timeout=20)
        self.assertEqual(caller.returncode, 0, stdout + stderr)
        pid = int((self.root / "pid").read_text())
        try:
            group = os.getpgid(pid)
        except ProcessLookupError:
            self.fail("editor died when its calling shell sent SIGHUP and exited")
        self.assertNotEqual(group, caller.pid, "editor stayed in the calling shell's process group")
        self.assertEqual(os.getpgid(pid), pid)
        self.assertEqual(os.getsid(pid), pid, "editor stayed in the calling shell's session")
        os.kill(pid, signal.SIGHUP)
        env = dict(self.env, EDITOR_MCP_URL=f"http://127.0.0.1:{self.port}/mcp", EDITOR_MCP_TIMEOUT="2")
        reply = subprocess.run([str(self.root / "editor-mcp")], check=False, env=env,
                               capture_output=True, text=True, timeout=8)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        self.assertIn("done", reply.stdout)

    def test_old_log_cannot_substitute_for_a_fresh_log(self):
        (self.root / "editor.log").write_text("old clean log")
        self.env.update(LISTEN="1", NO_LOG="1")
        output = self.run_editor("open")
        self.assertIn("timed out", output)
        self.assertNotIn("MCP up", output)

    def test_owned_listener_without_mcp_reply_is_not_ready(self):
        self.env.update(LISTEN="1", HANG="tools/call")
        output = self.run_editor("open")
        self.assertIn("timed out", output)
        self.assertNotIn("MCP up", output)

    def test_fresh_log_bind_error_is_fatal(self):
        self.env["LOG_TEXT"] = f"HttpListener unable to bind to 127.0.0.1:{self.port}"
        self.assertIn("could not bind", self.run_editor("open"))

    def test_status_checks_ownership_mcp_and_python_queue(self):
        self.env["LISTEN"] = "1"
        self.run_editor("open", ok=True)
        self.script("pgrep", '#!/bin/sh\ncat "$MARKER"\n')
        self.env["PATH"] = str(self.root) + os.pathsep + os.environ["PATH"]
        output = self.run_editor("status", ok=True)
        self.assertIn((self.root / "pid").read_text(), output)
        self.assertIn("done", output)
        self.assertIn("python-queue-ok", output)
        self.script("editor-py", "#!/bin/sh\necho queue-failed >&2\nexit 1\n")
        self.assertIn("queue-failed", self.run_editor("status"))

    def test_capture_stops_at_failed_status_before_python_queue(self):
        review = self.root / "review"
        review.mkdir()
        shutil.copy(SCRIPTS / "review/capture", review / "capture")
        self.script("editor.sh", "#!/bin/sh\necho unhealthy-port >&2\nexit 1\n")
        self.script("editor-py", '#!/bin/sh\ntouch "$MARKER"\n')
        result = subprocess.run([str(review / "capture"), str(self.root / "images")], check=False, env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unhealthy-port", result.stderr)
        self.assertFalse((self.root / "pid").exists())

    def test_cleanup_selects_only_project_orphan_reporter(self):
        # Fake only ps's process table; each candidate is a real sleep owned by this test.
        children = [subprocess.Popen(["sleep", "30"]) for _ in range(5)]
        for child in children:
            self.addCleanup(child.wait, 5)
            self.addCleanup(child.kill)
        # The lead's real #190 command, with only the process-table PID replaced by our child PID.
        observed = ("CrashReportClient /Users/tp/Library/Application Support/Epic/UnrealEngine/5.8/"
                    "Saved/Crashes/CrashReport-UE-Forest-pid-33014-CC15FA4C8745D60EA51B51B4D1A42A9C")
        self.env["HOME"] = "/Users/tp"
        commands = (observed, observed.replace("UE-Forest-pid", "UE-Other-pid"), observed,
                    observed.replace("CrashReportClient ", "Other ", 1), "Other " + observed)
        table = "\n".join(f"{child.pid} {parent} {command}" for child, parent, command in
                          zip(children, (1, 1, 99, 1, 1), commands))
        self.script("ps", f"#!/bin/sh\nif [ \"$1\" = -p ]; then\n"
                    f"  case \"$2\" in {children[0].pid}) echo CrashReportClient;; *) echo /fake/Other;; esac\n"
                    f"else printf '%s\\n' '{table}'; fi\n")
        self.env["PATH"] = str(self.root) + os.pathsep + os.environ["PATH"]
        output = self.run_editor("close", ok=True)
        self.assertIn(f"stopping orphaned CrashReportClient pid {children[0].pid}", output)
        self.assertEqual(children[0].wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(all(child.poll() is None for child in children[1:]))


if __name__ == "__main__":
    unittest.main()
