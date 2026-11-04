#!/usr/bin/env python3
# Bridge self-test: no emulators, no ROMs.
#
# Starts bridge.py on spare ports, then plays both peers itself:
#   - a fake Flycast: UDP socket speaking BattleCable framing ('D'+byte, 'B')
#   - a fake NGPC core: TCP client sending/receiving raw bytes
# and checks that every byte crosses the bridge unchanged in both directions
# and that a BREAK packet is swallowed.
#
# Run from repo root:
#   python bridge/selftest.py

import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UDP_BRIDGE = 52500   # bridge binds here (Flycast "server=" would point here)
UDP_FLYCAST = 47391  # fake Flycast binds here (Flycast LocalPort)
TCP_BRIDGE = 52424   # bridge listens here (beetle-ngp NGPC_LINK_PORT)


def recv_exact_tcp(s, n, timeout=2.0):
    s.settimeout(timeout)
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def main():
    env = dict(os.environ,
               BRIDGE_UDP_BIND=str(UDP_BRIDGE),
               BRIDGE_UDP_FLYCAST_PORT=str(UDP_FLYCAST),
               BRIDGE_TCP_PORT=str(TCP_BRIDGE),
               BRIDGE_LOG="")
    for k in ("BRIDGE_ECHO_HANDSHAKE", "BRIDGE_SYNTH_MF2K_ACK", "BRIDGE_SYNTH_DATA_FRAME",
              "BRIDGE_POST_INJECT"):
        env.pop(k, None)

    flycast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    flycast.bind(("127.0.0.1", UDP_FLYCAST))
    flycast.settimeout(2.0)

    bridge = subprocess.Popen([sys.executable, "-I", os.path.join(HERE, "bridge.py")],
                              env=env, stderr=subprocess.DEVNULL)
    failures = 0
    try:
        ngpc = None
        for _ in range(50):
            try:
                ngpc = socket.create_connection(("127.0.0.1", TCP_BRIDGE), timeout=1.0)
                break
            except OSError:
                time.sleep(0.1)
        if ngpc is None:
            print("FAIL: bridge did not start listening")
            return 1
        time.sleep(0.2)

        # NGPC -> DC: MOTM's 18-byte upload-request frame (docs/PROTOCOL.md)
        frame = bytes([0xFF, 0x00, 0x31, 0x31]) + bytes(13) + bytes([0xFF])
        ngpc.sendall(frame)
        got = b""
        for _ in frame:
            pkt, _addr = flycast.recvfrom(16)
            if len(pkt) != 2 or pkt[0:1] != b"D":
                print(f"FAIL: unexpected UDP packet {pkt!r}")
                failures += 1
                break
            got += pkt[1:2]
        ok = got == frame
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} NGPC->DC  {len(frame)} bytes as 'D' packets")

        # DC -> NGPC: BREAK must be dropped, data bytes forwarded in order
        payload = bytes(range(256))
        flycast.sendto(b"B", ("127.0.0.1", UDP_BRIDGE))
        for b in payload:
            flycast.sendto(bytes([0x44, b]), ("127.0.0.1", UDP_BRIDGE))
        got = recv_exact_tcp(ngpc, len(payload))
        ok = got == payload
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} DC->NGPC  {len(payload)} bytes, BREAK swallowed")

        # DC -> NGPC: a frame split by a gap must not reach the NGPC half-done
        # (MF2K's data echo; Flycast sometimes delivers it in two pieces).
        echo = bytes.fromhex("ff0010000002000000002f000006010000000006000028" "00ff")
        for b in echo[:22]:
            flycast.sendto(bytes([0x44, b]), ("127.0.0.1", UDP_BRIDGE))
        ngpc.settimeout(0.1)
        try:
            early = ngpc.recv(64)
        except socket.timeout:
            early = b""
        for b in echo[22:]:
            flycast.sendto(bytes([0x44, b]), ("127.0.0.1", UDP_BRIDGE))
        got = recv_exact_tcp(ngpc, len(echo))
        ok = early == b"" and got == echo
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} DC->NGPC  split frame held until its closing FF "
              f"(early={len(early)}B)")

        # DC -> NGPC: an unterminated frame is delivered after the timeout
        flycast.sendto(bytes([0x44, 0xFF]), ("127.0.0.1", UDP_BRIDGE))
        flycast.sendto(bytes([0x44, 0x00]), ("127.0.0.1", UDP_BRIDGE))
        t = time.time()
        got = recv_exact_tcp(ngpc, 2)
        ok = got == b"\xff\x00" and time.time() - t < 1.5
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} DC->NGPC  unterminated frame flushed after "
              f"{(time.time() - t) * 1000:.0f} ms")

        ngpc.close()
    finally:
        bridge.terminate()
        bridge.wait(timeout=5)
        flycast.close()

    print("PASS" if failures == 0 else f"{failures} check(s) failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
