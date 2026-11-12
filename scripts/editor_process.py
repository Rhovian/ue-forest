#!/usr/bin/env python3
"""Run a bounded command tree; a detached supervisor owns its clock and watches caller lifetime."""
import math
import os
import select
import signal
import subprocess
import sys
import time

# Popen timeouts do not provide group cleanup or parent-death handling. A pipe closes even on SIGKILL;
# the independently launched supervisor owns the command before it ever starts, avoiding a watchdog-start race.
# https://docs.python.org/3/library/subprocess.html#subprocess.Popen
# https://docs.python.org/3/library/select.html#select.select

def supervise(limit, command):
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal.SIG_IGN)
    end = time.monotonic() + float(limit)
    if select.select([0], [], [], 0)[0] and not os.read(0, 1):
        return 125  # caller disappeared before launch
    process = subprocess.Popen(command, start_new_session=True, stdin=subprocess.DEVNULL)
    reason, code = None, 0
    try:
        while process.poll() is None:
            remaining = end - time.monotonic()
            if remaining <= 0:
                reason, code = f"timed out after {limit}s waiting for", 124
                break
            if select.select([0], [], [], min(.1, remaining))[0] and not os.read(0, 1):
                reason, code = "caller stopped while waiting for", 125
                break
        if reason is None:
            code = process.returncode
    finally:
        # Also stop children left behind by a command which exited without waiting for them.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
    if reason:
        print(f"{reason} {command} (process group stopped)", file=sys.stderr)
    return code


def run(limit, command):
    caller = os.getppid()
    supervisor = None
    interrupted = 0

    def cancel(sig, *_):
        nonlocal interrupted
        interrupted = sig
        if supervisor is not None:
            supervisor.stdin.close()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, cancel)
    supervisor = subprocess.Popen([sys.executable, __file__, "--supervise", limit, *command],
                                  stdin=subprocess.PIPE, start_new_session=True)
    end = time.monotonic() + float(limit) + 6  # supervisor's deadline plus its bounded reap
    try:
        while supervisor.poll() is None:
            if interrupted or os.getppid() != caller:
                supervisor.stdin.close()
            remaining = end - time.monotonic()
            if remaining <= 0:
                print(f"supervisor did not finish waiting for {command}", file=sys.stderr)
                return 124  # closing the pipe still leaves the independent deadline in force
            try:
                supervisor.wait(timeout=min(.1, remaining))
            except subprocess.TimeoutExpired:
                pass
        return 128 + interrupted if interrupted else supervisor.returncode
    finally:
        supervisor.stdin.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    supervising = args[:1] == ["--supervise"]
    if supervising:
        args = args[1:]
    if len(args) < 2 or not math.isfinite(float(args[0])) or float(args[0]) <= 0:
        sys.exit("editor_process.py requires a positive finite timeout and a command")
    sys.exit((supervise if supervising else run)(args[0], args[1:]))
