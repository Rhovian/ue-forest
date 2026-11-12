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
                        EDITOR_LOG=str(self.root / "editor.log"), EDITOR_OPEN_TIMEOUT="6", HOME=str(self.root),
                        PYTHONPATH=str(SCRIPTS))
        self.env["PATH"] = str(self.root) + os.pathsep + os.environ["PATH"]
        # No lifecycle command may discover or signal a real editor/reporter, even on a dirty machine.
        self.script("ps", '#!/bin/sh\ncase "$*" in *-axo*) exit 0;; *) exec /bin/ps "$@";; esac\n')
        self.script("pgrep", "#!/bin/sh\nexit 1\n")
        self.script("pkill", "#!/bin/sh\nexit 0\n")
        self.script("osascript", "#!/bin/sh\nexit 0\n")
        for name in ("editor.sh", "editor-mcp", "editor_port.py", "editor_process.py"):
            if (SCRIPTS / name).exists():
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

    def helper(self, body, *args):
        return subprocess.run(["bash", "-c", 'source "$1"; shift; ' + body,
                               "helper", str(self.root / "editor.sh"), *args], check=False,
                              env=self.env, capture_output=True, text=True, timeout=10)

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
        (self.root / "editor.log.prev").write_text("older launch")
        (self.root / "editor.log").write_text(f"HttpListener unable to bind to 127.0.0.1:{self.port}")
        self.env["LISTEN"] = "1"
        self.env["EDITOR_OPEN_TIMEOUT"] = "8"
        real_mcp = self.root / "editor-mcp-ready"
        (self.root / "editor-mcp").rename(real_mcp)
        pending = self.root / "startup-pending"
        self.script("editor-mcp", f'#!/bin/sh\nif [ ! -f "{pending}" ]; then touch "{pending}"; '
                    f'echo "startup-probe-not-ready" >&2; exit 1; fi\nexec "{real_mcp}" "$@"\n')
        output = self.run_editor("open", ok=True)
        self.assertIn("MCP up", output)
        self.assertNotIn("startup-probe-not-ready", output)
        self.assertNotIn("done", output)
        self.assertEqual((self.root / "editor.log.prev").read_text(),
                         f"HttpListener unable to bind to 127.0.0.1:{self.port}")
        self.assertEqual(list(self.root.glob("editor.log.*")), [self.root / "editor.log.prev"])

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
        self.assertEqual(output.count("last MCP readiness probe:"), 1)
        self.assertIn("is still running", output)
        self.assertNotIn("MCP up", output)

    def test_fresh_log_bind_error_is_fatal(self):
        self.env["LOG_TEXT"] = f"HttpListener unable to bind to 127.0.0.1:{self.port}"
        output = self.run_editor("open")
        self.assertIn("could not bind", output)
        self.assertIn(f"pid {(self.root / 'pid').read_text()} is still running", output)
        self.assertIn("editor.sh status", output)

    def test_status_checks_ownership_mcp_and_python_queue(self):
        self.env["LISTEN"] = "1"
        self.run_editor("open", ok=True)
        self.script("pgrep", '#!/bin/sh\ncat "$MARKER"\n')
        self.env["PATH"] = str(self.root) + os.pathsep + os.environ["PATH"]
        real_mcp = self.root / "editor-mcp-real"
        (self.root / "editor-mcp").rename(real_mcp)
        probe_limit = self.root / "probe-limit"
        self.script("editor-mcp", f'#!/bin/sh\necho "$EDITOR_MCP_TIMEOUT" > "{probe_limit}"\nexec "{real_mcp}" "$@"\n')
        self.script("editor-py", '#!/bin/sh\n[ "$EDITOR_PY_TIMEOUT" = 30 ] && [ "$1" = --probe ] || exit 2\necho python-queue-ok\n')
        output = self.run_editor("status", ok=True)
        self.assertIn((self.root / "pid").read_text(), output)
        self.assertIn("MCP round trip OK", output)
        self.assertNotIn("done", output)
        self.assertNotIn("held by", output)
        self.assertIn("python-queue-ok", output)
        self.assertEqual(probe_limit.read_text().strip(), "10")
        self.script("editor-py", "#!/bin/sh\necho queue-failed >&2\nexit 1\n")
        self.assertIn("queue-failed", self.run_editor("status"))
        self.script("editor-py", "#!/bin/sh\necho python-queue-ok\n")
        self.script("editor-mcp", "#!/bin/sh\necho mcp-failed\nexit 1\n")
        self.assertIn("mcp-failed", self.run_editor("status"))

    def test_closed_status_never_queues_a_probe(self):
        queued = self.root / "queued"
        self.script("editor-py", f'#!/bin/sh\ntouch "{queued}"\n')
        output = self.run_editor("status")
        self.assertIn("missing", output)
        self.assertFalse(queued.exists())

    def test_bind_gate_is_checked_before_open_close_or_kill_return(self):
        self.env["LISTEN"] = "1"
        real_launch = self.root / "launch-real"
        (self.root / "launch").rename(real_launch)
        cleared, early, attempted = self.root / "clear", self.root / "early", self.root / "attempted"
        self.script("launch", f'#!/bin/sh\n[ -f "{cleared}" ] || touch "{early}"\nexec "{real_launch}" "$@"\n')
        # Empty netstat must not bypass the bind check on macOS 27 (#192 R2-1).
        self.script("netstat", "#!/bin/sh\nexit 0\n")
        for action in ("close", "kill", "open"):
            with self.subTest(action=action):
                cleared.unlink(missing_ok=True)
                attempted.unlink(missing_ok=True)
                self.script("editor_port.py", f'#!/bin/sh\nif [ -f "{attempted}" ]; then touch "{cleared}"; exit 0; fi\n'
                            f'touch "{attempted}"\necho "bind still busy" >&2\nexit 1\n')
                self.run_editor(action, ok=True)
                self.assertTrue(cleared.exists(), f"{action} never checked bindability")
                self.assertFalse(early.exists(), "launched before bind succeeded")

    def test_kernel_bind_rejects_ownerless_time_wait_and_fin_wait(self):
        self.script("netstat", "#!/bin/sh\nexit 0\n")
        for state in ("TIME_WAIT", "FIN_WAIT_2"):
            with self.subTest(state=state), socket.socket() as server, socket.socket() as client:
                server.settimeout(2)
                client.settimeout(2)
                server.bind(("127.0.0.1", 0))
                port = server.getsockname()[1]
                server.listen()
                client.connect(("127.0.0.1", port))
                accepted, _ = server.accept()
                accepted.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1), b"")
                accepted.close()
                server.close()
                if state == "TIME_WAIT":
                    client.close()
                self.env["EDITOR_PORT"] = str(port)
                self.assertEqual(self.helper("holders").stdout, "")
                result = self.helper('if port_clear; then exit 0; else code=$?; echo "$port_error" >&2; exit "$code"; fi')
                self.assertNotEqual(result.returncode, 0, f"claimed {state} port bindable")
                self.assertIn("bind", result.stderr)

    def test_close_and_kill_grant_exiting_editor_a_socket_release_grace(self):
        for action in ("close", "kill"):
            with self.subTest(action=action):
                child = subprocess.Popen(["sleep", "30"])
                self.addCleanup(child.wait, 5)
                self.addCleanup(child.kill)
                seen, stale = self.root / "seen", self.root / "stale"
                seen.unlink(missing_ok=True)
                stale.unlink(missing_ok=True)
                self.script("pgrep", f'#!/bin/sh\nif [ -f "{seen}" ]; then exit 1; fi\ntouch "{seen}"\necho {child.pid}\n')
                self.script("lsof", f'#!/bin/sh\nif [ -f "{stale}" ]; then exit 1; fi\ntouch "{stale}"\necho {child.pid}\n')
                output = self.run_editor(action, ok=True)
                self.assertNotIn("held by", output)

    def test_open_and_kill_wait_for_cleaned_reporter_to_release_socket(self):
        self.env["LISTEN"] = "1"
        for action in ("kill", "open"):
            with self.subTest(action=action):
                child = subprocess.Popen(["sleep", "30"])
                self.addCleanup(child.wait, 5)
                self.addCleanup(child.kill)
                table = f"{child.pid} 1 CrashReportClient {self.root}/Saved/Crashes/local"
                self.script("ps", f'#!/bin/sh\ncase "$*" in *-axo*) echo "{table}";; *) echo CrashReportClient;; esac\n')
                stale = self.root / "stale"
                stale.unlink(missing_ok=True)
                self.script("lsof", f'#!/bin/sh\nif [ ! -f "{stale}" ]; then touch "{stale}"; echo {child.pid}; '
                            'else exec /usr/sbin/lsof "$@"; fi\n')
                output = self.run_editor(action, ok=True)
                self.assertIn(f"stopping orphaned CrashReportClient pid {child.pid}", output)
                self.assertNotIn("held by", output)
                self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)

    def test_inspection_does_not_find_its_own_wrapper_and_usage_includes_restart(self):
        self.script("pgrep", '#!/bin/sh\nexec /usr/bin/pgrep "$@"\n')
        result = self.helper("editor_pids")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "", "process query matched its own timeout wrapper")
        self.assertIn("editor.sh restart", self.run_editor("unknown"))

    def test_probe_budget_is_explicit_even_with_an_epoch_deadline(self):
        self.script("editor-mcp", "#!/bin/sh\nsleep 3\n")
        result = self.helper("deadline=9999999999; mcp_probe .2 .1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out after .2s", result.stderr)

    def test_process_exit_during_inspection_or_cleanup_is_harmless(self):
        child = subprocess.Popen(["true"])
        child.wait(timeout=2)
        table = f"{child.pid} 1 CrashReportClient {self.root}/Saved/Crashes/local"
        self.script("ps", f'#!/bin/sh\ncase "$*" in *-axo*) echo "{table}";; *) exit 1;; esac\n')
        output = self.run_editor("close", ok=True)
        self.assertIn(f"pid {child.pid} already exited", output)
        result = self.helper('show_holders "$1"', str(child.pid))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(child.pid), result.stdout)
        self.script("ps", f'#!/bin/sh\ncase "$*" in *-axo*) echo "{table}";; *) echo CrashReportClient;; esac\n')
        result = self.helper('kill() { return 1; }; cleanup_crash_reporters')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopping orphaned", result.stdout)
        result = self.helper('kill() { [[ "$1" == -0 ]]; }; cleanup_crash_reporters')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"could not stop crash reporter pid {child.pid}", result.stderr)

    def test_editor_py_probe_timeout_removes_only_its_own_request(self):
        queue = self.root / "queue"
        (queue / "in").mkdir(parents=True)
        (queue / "out").mkdir()
        foreign = queue / "in/keep.py"
        foreign.write_text("unrelated queued work")
        env = dict(self.env, EDITOR_PY_ROOT=str(queue), EDITOR_PY_TIMEOUT=".2")
        result = subprocess.run([str(SCRIPTS / "editor-py"), "--probe"], check=False, env=env,
                                capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("probe request removed", result.stderr)
        self.assertEqual(list((queue / "in").iterdir()), [foreign])
        result = subprocess.run([str(SCRIPTS / "editor-py"), "-e", "1"], check=False, env=env,
                                capture_output=True, text=True, timeout=3)
        self.assertIn("request left", result.stderr)
        self.assertEqual(len(list((queue / "in").glob("*.py"))), 2)

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
        children = [subprocess.Popen(["sleep", "30"]) for _ in range(6)]
        for child in children:
            self.addCleanup(child.wait, 5)
            self.addCleanup(child.kill)
        # The lead's real #190 command; remap its home and PID into private, owned test fixtures.
        observed = ("CrashReportClient /Users/tp/Library/Application Support/Epic/UnrealEngine/5.8/"
                    "Saved/Crashes/CrashReport-UE-Forest-pid-33014-CC15FA4C8745D60EA51B51B4D1A42A9C")
        observed = observed.replace("/Users/tp", self.env["HOME"])
        commands = (observed, observed.replace("UE-Forest-pid", "UE-Other-pid"), observed,
                    observed.replace("CrashReportClient ", "Other ", 1), "Other " + observed, f"CrashReportClient {self.root}/Saved/Crashes/local")
        table = "\n".join(f"{child.pid} {parent} {command}" for child, parent, command in
                          zip(children, (1, 1, 99, 1, 1, 1), commands))
        self.script("ps", f"#!/bin/sh\nif [ \"$1\" = -p ]; then\n"
                    f"  case \"$2\" in {children[0].pid}|{children[-1].pid}) echo CrashReportClient;; *) echo /fake/Other;; esac\n"
                    f"else printf '%s\\n' '{table}'; fi\n")
        self.env["PATH"] = str(self.root) + os.pathsep + os.environ["PATH"]
        output = self.run_editor("close", ok=True)
        self.assertIn(f"stopping orphaned CrashReportClient pid {children[0].pid}", output)
        self.assertEqual(children[0].wait(timeout=5), -signal.SIGKILL)
        self.assertEqual(children[-1].wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(all(child.poll() is None for child in children[1:-1]))


if __name__ == "__main__":
    unittest.main()
