#!/usr/bin/env python3
# Replay retail MOTM upload-start frame to MF2K via Flycast.
#
# Frame captured from the loopback comms log (bytes 5108-5129), emitted by
# MOTM when user pressed A on "Send to DC" in VS submenu:
#
#   Preamble : 10 10 10 00   (transition / pre-frame signal)
#   Frame    : FF 00 31 31 00 00 00 00 00 00 00 00 00 00 00 00 00 FF
#                ^^          ^^ ^^                                 ^^
#             delim        cmd magic                              delim
#
# Also replays the cable-probe preamble (0x92 0x92) that MOTM does at
# VS-menu entry, in case MF2K requires it before accepting the upload.
#
# Sends UDP 'D'+byte packets directly to Flycast 127.0.0.1:37391.
# MF2K responses appear in the bridge log (BRIDGE_LOG) via bridge (port 42500).

import socket
import sys
import time

FLYCAST_HOST = "127.0.0.1"
FLYCAST_PORT = 37391

PREAMBLE_PROBE = [0x92, 0x92]
PREAMBLE_FRAME = [0x10, 0x10, 0x10, 0x00]
UPLOAD_FRAME   = [0xFF, 0x00, 0x31, 0x31,
                  0x00, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00,
                  0x00, 0xFF]

def send_byte(s, b):
    s.sendto(bytes([0x44, b]), (FLYCAST_HOST, FLYCAST_PORT))

def send_seq(s, seq, label, log, delay_ms=10):
    log(f"sending {label} ({len(seq)}B): {' '.join(f'{b:02x}' for b in seq)}")
    for b in seq:
        send_byte(s, b)
        time.sleep(delay_ms / 1000.0)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    def log(msg):
        sys.stderr.write(f"[{time.time()-t0:7.3f}] {msg}\n")
        sys.stderr.flush()

    log("== phase 1: cable probe (2x 0x92) ==")
    send_seq(s, PREAMBLE_PROBE, "probe", log)
    log("wait 2s for MF2K to register cable alive")
    time.sleep(2.0)

    log("== phase 2: transition signal (10 10 10 00) ==")
    send_seq(s, PREAMBLE_FRAME, "transition", log)
    log("wait 500ms")
    time.sleep(0.5)

    log("== phase 3: UPLOAD START FRAME ==")
    send_seq(s, UPLOAD_FRAME, "FF-frame", log)
    log("wait 5s listening for MF2K response")
    time.sleep(5.0)

    log("== phase 4: retry frame without preamble ==")
    send_seq(s, UPLOAD_FRAME, "FF-frame retry", log)
    log("wait 3s")
    time.sleep(3.0)

    log("== phase 5: full sequence again with inter-byte 50ms pacing ==")
    send_seq(s, PREAMBLE_PROBE, "probe", log, delay_ms=50)
    time.sleep(0.5)
    send_seq(s, PREAMBLE_FRAME, "transition", log, delay_ms=50)
    time.sleep(0.3)
    send_seq(s, UPLOAD_FRAME, "FF-frame slow", log, delay_ms=50)
    log("wait 5s")
    time.sleep(5.0)

    log("probe complete, check the bridge log (BRIDGE_LOG) for UDP<-Flycast lines")

if __name__ == "__main__":
    main()
