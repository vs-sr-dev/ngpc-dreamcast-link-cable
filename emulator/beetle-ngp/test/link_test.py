#!/usr/bin/env python3
# Plays the bridge's TCP side for link_harness.exe: comes up late, goes
# away, comes back. Checks the bytes in both directions and the harness's
# exit code (which fails if any comms call blocked).
#
#   python emulator/beetle-ngp/test/link_test.py <link_harness.exe> [port]
#
# run_link_test.sh builds the harness and calls this.

import os
import socket
import subprocess
import sys
import time

exe = os.path.abspath(sys.argv[1])
port = int(sys.argv[2]) if len(sys.argv) > 2 else 53111
env = dict(os.environ, NGPC_LINK_ROLE="client", NGPC_LINK_HOST="127.0.0.1",
           NGPC_LINK_PORT=str(port))
env.pop("NGPC_LINK_MMIO", None)
harness = subprocess.Popen([exe], env=env)
failures = 0


def serve(send, expect):
    global failures
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    srv.settimeout(30)
    conn, _ = srv.accept()
    conn.sendall(bytes([send]))
    conn.settimeout(30)
    got = conn.recv(1)
    ok = got == bytes([expect])
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} peer sent {send:#04x}, got {got.hex() or 'nothing'} (expected {expect:#04x})",
          flush=True)
    conn.close()
    srv.close()


time.sleep(3.0)    # the core starts with nobody listening
serve(0x5A, 0x99)
time.sleep(1.5)    # the peer is gone for a while
serve(0x6B, 0x77)

rc = harness.wait(timeout=60)
print(f"{'ok  ' if rc == 0 else 'FAIL'} harness exit code {rc}")
failures += rc != 0
print("PASS" if failures == 0 else f"{failures} check(s) failed")
sys.exit(0 if failures == 0 else 1)
