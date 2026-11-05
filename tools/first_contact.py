#!/usr/bin/env python3
# First contact: play MOTM's side of the upload request, through the bridge.
#
# Connects to the bridge's TCP port as if it were the patched NGPC core,
# sends MOTM's upload request (the frame it emits on "Send to DC") and
# reports whether Millennium Fight 2000 answers with its 23-byte
# acknowledgement. Works the same against Flycast and against a real
# Dreamcast on the serial port (BRIDGE_SERIAL), so it is the first test to
# run on new hardware: no RetroArch, no MOTM needed.
#
# MF2K must be on its Download Stand By screen (Secret Mode).
#
#   python tools/first_contact.py [host:port]      (default 127.0.0.1:42424)

import socket
import sys
import time

UPLOAD_REQUEST = bytes([0xFF, 0x00, 0x31, 0x31]) + bytes(13) + bytes([0xFF])
MF2K_ACK = bytes.fromhex("ff 00 10 00 00 00 00 00 00 00 00 1c 00 00 04 00 00 0c 00 00 10 00 ff")
WAIT_S = 5.0


def main():
    host, _, port = (sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:42424").partition(":")
    s = socket.create_connection((host, int(port or 42424)), timeout=5)
    s.settimeout(0.2)
    print(f"connected to the bridge at {host}:{port or 42424}")

    s.sendall(bytes([0x92, 0x92]))          # MOTM's cable probe, as in the captures
    time.sleep(0.5)
    print("sending upload request:", UPLOAD_REQUEST.hex(" "))
    s.sendall(UPLOAD_REQUEST)

    got = b""
    t0 = time.time()
    while time.time() - t0 < WAIT_S:
        try:
            d = s.recv(256)
        except socket.timeout:
            continue
        if not d:
            break
        got += d
        if MF2K_ACK in got:
            break
    s.close()

    if MF2K_ACK in got:
        print(f"MF2K answered after {time.time() - t0:.3f} s with its acknowledgement:")
        print("  ", MF2K_ACK.hex(" "))
        print("FIRST CONTACT OK")
        return 0
    if got:
        print(f"received {len(got)} bytes, but not the expected acknowledgement:")
        print("  ", got.hex(" "))
    else:
        print(f"no answer in {WAIT_S:.0f} s. Check: MF2K on Download Stand By, the bridge log "
              "(serial CTS?), the baud rate, TX/RX crossed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
