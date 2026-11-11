"""editor-mcp gives up on a hung MCP server (python3 scripts/test_editor_mcp.py).

A fake server completes the handshake, then answers the tool call with stream headers and a keep-alive comment every
0.2 s, never the result: the shape of the 7.5-hour CaptureViewport stall, which a per-read socket timeout would miss.
"""

import json
import os
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EDITOR_MCP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor-mcp")


class Hung(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["method"] == "tools/call":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            while not self.server.closing:
                self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
                time.sleep(0.2)
            return
        reply = b"" if "id" not in body else json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode()
        self.send_response(200 if reply else 202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "test")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *_):
        pass


class EditorMcpTimeoutTests(unittest.TestCase):
    def test_tool_call_on_a_trickling_server_times_out(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Hung)
        server.closing = False
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(setattr, server, "closing", True)
        env = dict(os.environ, EDITOR_MCP_URL=f"http://127.0.0.1:{server.server_port}/mcp", EDITOR_MCP_TIMEOUT="1")
        start = time.monotonic()
        result = subprocess.run([EDITOR_MCP, "Toolset", "Tool", "{}"], check=False, env=env, capture_output=True,
                                text=True, timeout=30)
        self.assertLess(time.monotonic() - start, 10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tools/call: no reply", result.stderr)


if __name__ == "__main__":
    unittest.main()
