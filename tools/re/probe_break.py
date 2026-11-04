#!/usr/bin/env python3
# MF2K BREAK-signal probe.
#
# Sends UDP 'B' (BREAK) directly to Flycast's NullModemPipe bound port,
# bypassing bridge, to test if MF2K reacts to a serial BREAK as a
# cable-detect / peer-alive trigger (Tetris-style pattern).
#
# Flycast listens on UDP 127.0.0.1:37391 (NaomiNetwork::SERVER_PORT default).
# Packet format (from core/network/null_modem.h):
#   'B'        (1 byte)  = BREAK
#   'D' + byte (2 bytes) = data byte
#
# Run while bridge.py is up and MF2K is in "Download Stand By" screen.
# After running, read the bridge log (BRIDGE_LOG) for "UDP<-Flycast" lines.

import socket
import sys
import time

FLYCAST_HOST = "127.0.0.1"
FLYCAST_PORT = 37391

# Scenarios to test in sequence:
#   1. Single BREAK alone    - see if break triggers DC reply
#   2. BREAK + short wait + spam 0x92 - after cable-detect via break, MOTM-style byte
#   3. Repeat BREAK every 200ms for 5s - sustained cable-alive signaling
#   4. BREAK then 2-byte magic 0x55 0xAA - common 8-bit handshake

def send_break(s):
    s.sendto(b"B", (FLYCAST_HOST, FLYCAST_PORT))

def send_byte(s, b):
    s.sendto(bytes([0x44, b]), (FLYCAST_HOST, FLYCAST_PORT))

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    def log(msg):
        sys.stderr.write(f"[{time.time()-t0:7.3f}] {msg}\n")
        sys.stderr.flush()

    log("== scenario 1: single BREAK ==")
    send_break(s)
    log("BREAK sent, waiting 3s to listen for MF2K reply (check bridge log)")
    time.sleep(3.0)

    log("== scenario 2: BREAK + 0x92 spam ==")
    send_break(s)
    time.sleep(0.1)
    for _ in range(5):
        send_byte(s, 0x92)
        time.sleep(0.1)
    log("sent BREAK + 5x 0x92, waiting 3s")
    time.sleep(3.0)

    log("== scenario 3: repeated BREAK ==")
    for i in range(25):
        send_break(s)
        time.sleep(0.2)
    log("sent 25x BREAK at 200ms, waiting 3s")
    time.sleep(3.0)

    log("== scenario 4: BREAK + common magic pairs ==")
    for pair in [(0x55, 0xAA), (0xAA, 0x55), (0xFF, 0xFF), (0x00, 0x00), (0x5A, 0xA5), (0xA5, 0x5A)]:
        send_break(s)
        time.sleep(0.1)
        send_byte(s, pair[0])
        time.sleep(0.05)
        send_byte(s, pair[1])
        log(f"sent BREAK + {pair[0]:02x} {pair[1]:02x}")
        time.sleep(1.0)

    log("probe complete, check the bridge log (BRIDGE_LOG)")

if __name__ == "__main__":
    main()
