#!/usr/bin/env python3
"""Test the actual MCP bind without address reuse: covers ownerless closing states and TIME_WAIT."""
import errno
import socket
import sys


def main():
    port = int(sys.argv[1])
    try:
        # Deliberately no SO_REUSEADDR: UE's listener must be able to make this same bind (#192 R2-1).
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", port))
    except OSError as error:
        print(f"cannot bind 127.0.0.1:{port}: {error}", file=sys.stderr)
        return 1 if error.errno == errno.EADDRINUSE else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
