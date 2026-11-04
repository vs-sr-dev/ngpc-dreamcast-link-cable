#!/usr/bin/env python3
# MF2K retail-frame probe.
#
# Retail MOTM (NGPC) sends framed data with 0xFF delimiter, per
# the MAME trace of BIOS vectors (docs/DEVLOG.md). Example frame captured:
#   FF 31 31 00 00 00 00 FF    (8 bytes, open/close 0xFF)
#
# Our single-byte fuzz ignored framing; MF2K silently accumulated
# bytes in a partial-frame buffer and never acted. Now we send
# full retail-format frames and listen for any MF2K response.
#
# Strategy:
#   1. Optional handshake preamble: 0x92 x2 (pre-data polling)
#   2. Send the exact retail frame FF 31 31 00 00 00 00 FF
#   3. Variants with different payload bytes to probe state space
#
# All sent as UDP 'D'+byte packets directly to Flycast 127.0.0.1:37391.
# MF2K responses appear in the bridge log (BRIDGE_LOG) via bridge (port 42500).

import socket
import sys
import time

FLYCAST_HOST = "127.0.0.1"
FLYCAST_PORT = 37391

def send_byte(s, b):
    s.sendto(bytes([0x44, b]), (FLYCAST_HOST, FLYCAST_PORT))

def send_frame(s, payload, log):
    s.sendto(bytes([0x44, 0xFF]), (FLYCAST_HOST, FLYCAST_PORT))
    time.sleep(0.01)
    for b in payload:
        s.sendto(bytes([0x44, b]), (FLYCAST_HOST, FLYCAST_PORT))
        time.sleep(0.01)
    s.sendto(bytes([0x44, 0xFF]), (FLYCAST_HOST, FLYCAST_PORT))
    log(f"sent frame: FF {' '.join(f'{b:02x}' for b in payload)} FF")

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    def log(msg):
        sys.stderr.write(f"[{time.time()-t0:7.3f}] {msg}\n")
        sys.stderr.flush()

    log("== phase 1: handshake preamble ==")
    send_byte(s, 0x92)
    time.sleep(0.05)
    send_byte(s, 0x92)
    log("sent 0x92 0x92 (pre-data polling), waiting 2s")
    time.sleep(2.0)

    log("== phase 2: retail-captured frame ==")
    send_frame(s, [0x31, 0x31, 0x00, 0x00, 0x00, 0x00], log)
    log("waiting 3s for MF2K reply")
    time.sleep(3.0)

    log("== phase 3: payload variants ==")
    # zero payload
    send_frame(s, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00], log)
    time.sleep(2.0)
    # all 0xAA
    send_frame(s, [0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA], log)
    time.sleep(2.0)
    # single-byte command variants (guess: first byte is command ID)
    for cmd in [0x01, 0x10, 0x11, 0x21, 0x30, 0x33, 0x40, 0x80, 0xA0, 0xC0, 0xF0]:
        send_frame(s, [cmd, cmd, 0x00, 0x00, 0x00, 0x00], log)
        time.sleep(1.0)

    log("== phase 4: retail frame REPEATED (in case MF2K debounces first) ==")
    for i in range(5):
        send_frame(s, [0x31, 0x31, 0x00, 0x00, 0x00, 0x00], log)
        time.sleep(1.0)

    log("probe complete, check the bridge log (BRIDGE_LOG) for UDP<-Flycast lines")

if __name__ == "__main__":
    main()
