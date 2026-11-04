#!/usr/bin/env python3
# MF2K SCIF fuzz probe.
#
# Connects to bridge.py TCP:42424 as if it were the NGPC peer, and sends
# each byte 0x00..0xFF three times (100ms apart), waiting 500ms between
# values. Any MF2K response will appear in the bridge log (BRIDGE_LOG) as
# "UDP<-Flycast 'D' XX".
#
# Run AFTER bridge/bridge.py is up and AFTER MF2K is in "Download Stand By" screen.

import socket
import sys
import time

HOST = "127.0.0.1"
PORT = 42424
REPEATS = 3
INTRA_MS = 100   # ms between repeats of same byte
INTER_MS = 500   # ms wait after last repeat (for MF2K to respond)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    s.setblocking(True)
    t0 = time.time()
    sys.stderr.write(f"[{time.time()-t0:7.3f}] fuzz connected to bridge {HOST}:{PORT}\n")
    try:
        for b in range(256):
            for r in range(REPEATS):
                s.sendall(bytes([b]))
                sys.stderr.write(f"[{time.time()-t0:7.3f}] sent 0x{b:02x} (rep {r+1}/{REPEATS})\n")
                sys.stderr.flush()
                if r < REPEATS - 1:
                    time.sleep(INTRA_MS / 1000.0)
            time.sleep(INTER_MS / 1000.0)
        sys.stderr.write(f"[{time.time()-t0:7.3f}] fuzz complete, 256 bytes sent\n")
    finally:
        s.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("fuzz interrupted\n")
    except OSError as e:
        sys.stderr.write(f"fuzz error: {e}\n")
        sys.exit(1)
