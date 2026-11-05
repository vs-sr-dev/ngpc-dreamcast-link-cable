#!/usr/bin/env python3
# PC side of homebrew/dc_link_probe: tests the serial link to a real
# Dreamcast without a retail Dreamcast game.
#
#   upload   push dc_link_probe.bin through the serial loader of a dev disc
#            (DC-LBA2's DC_SERLOAD: 115200 baud, "LBA2LOAD" handshake).
#            Start it first, then power the console on.
#   listen   print what the Dreamcast sends (press Y on the pad for a line)
#   loop     DC in ECHO mode: 256 bytes 00..FF there and back, compared
#   rts      toggle the adapter's RTS; the probe screen shows its CTS pin
#   motm     DC in FAKE MF2K/DM99 mode: play MOTM's side of an upload
#            (request, announce, data frame with --points) and check every
#            answer against the captures
#
# Every test except upload runs at 19200 8N1 on the serial port (--port), or
# through the bridge (--bridge host:port, playing the NGPC peer), which also
# reaches the probe in Flycast with BattleCable on.
#
#   python tools/dc_probe.py upload
#   python tools/dc_probe.py loop
#   python tools/dc_probe.py --bridge 127.0.0.1:42424 motm --points 65
#
# Needs pyserial for the serial port: python -m pip install pyserial

import argparse
import os
import socket
import sys
import time

LOADER_BAUD = 115200
LINK_BAUD = 19200
CHUNK = 4096
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BIN = os.path.join(HERE, "..", "homebrew", "dc_link_probe", "dc_link_probe.bin")

UPLOAD_REQUEST = bytes([0xFF, 0x00, 0x31, 0x31]) + bytes(13) + bytes([0xFF])
ANNOUNCE = bytes.fromhex("ff 00 10 02 01 00 00 00 00 01 00 00 01 01 00 ff")
ANNOUNCE_REPLY = bytes.fromhex("ff 00 10 00 00 01 00 00 00 00 01 00 00 01 01 00 ff")
ACKS = {
    "mf2k": bytes.fromhex("ff 00 10 00 00 00 00 00 00 00 00 1c 00 00 04 00 00 0c 00 00 10 00 ff"),
    "dm99": bytes.fromhex("ff 00 10 00 00 00 00 00 00 00 00 51 00 00 04 00 00 47 00 00 0a 00 ff"),
}


def console_text(data):
    """Loader/console bytes as printable text, anything else as \\xNN: line
    noise or a wrong baud rate then shows for what it is."""
    return "".join(chr(b) if 32 <= b < 127 or b in (9, 10) else
                   "" if b == 13 else f"\\x{b:02x}" for b in data)


def open_serial(port, baud, timeout=0.02):
    try:
        import serial
    except ImportError:
        sys.exit("the serial port needs pyserial: python -m pip install pyserial")
    # serial_for_url also takes socket://host:port (used by the self-test)
    ser = serial.serial_for_url(port, baudrate=baud, bytesize=8, parity="N", stopbits=1,
                                timeout=timeout, rtscts=False)
    ser.rts = True
    return ser


def data_frame(game, points):
    """MOTM's data frame for each partner (docs/PROTOCOL.md)."""
    hi, lo = points >> 8, points & 0xFF
    if 0xFF in (hi, lo):
        sys.exit("points must not contain a 0xFF byte (it is the frame delimiter)")
    if game == "mf2k":
        body = bytes([0x00, 0x00, 0x06, 0x01, 0, 0, 0, 0, 0x06, 0x00, hi, lo, 0x00])
    else:
        body = bytes([0x00, 0x00, 0x02, 0x00, hi, lo, 0x00])
    checksum = (sum(body) - body[2]) & 0xFF     # offset 13 is left out
    return bytes([0xFF, 0x00, 0x10, 0x00, 0x00, 0x02, 0, 0, 0, 0, checksum]) + body + bytes([0xFF])


# ---------------------------------------------------------------- transports
class SerialLink:
    def __init__(self, port):
        self.ser = open_serial(port, LINK_BAUD)
        self.name = f"serial {port} {LINK_BAUD} 8N1"

    def send(self, data):
        self.ser.write(data)
        self.ser.flush()

    def recv(self):
        return self.ser.read(256)

    def close(self):
        self.ser.close()


class BridgeLink:
    def __init__(self, addr):
        host, _, port = addr.partition(":")
        self.sock = socket.create_connection((host, int(port or 42424)), timeout=5)
        self.sock.settimeout(0.02)
        self.name = f"bridge {host}:{port or 42424}"

    def send(self, data):
        self.sock.sendall(data)

    def recv(self):
        try:
            d = self.sock.recv(256)
        except socket.timeout:
            return b""
        if not d:
            raise ConnectionError("the bridge closed the connection")
        return d

    def close(self):
        self.sock.close()


def collect(link, seconds, until=None):
    """Reads for `seconds`, or until until(buffer) is true."""
    got = b""
    t_end = time.time() + seconds
    while time.time() < t_end:
        got += link.recv()
        if until and until(got):
            break
    return got


def frames_in(data):
    """FF-delimited frames in a byte stream (stray bytes between them dropped)."""
    out, cur = [], None
    for b in data:
        if cur is None:
            if b == 0xFF:
                cur = bytearray([b])
        elif b == 0xFF and len(cur) == 1:
            continue
        else:
            cur.append(b)
            if b == 0xFF:
                out.append(bytes(cur))
                cur = None
    return out


# ------------------------------------------------------------------- upload
def cmd_upload(args):
    with open(args.bin, "rb") as f:
        image = f.read()
    with open(args.bin + ".span") as f:
        span = int(f.read().strip())
    if span < len(image):
        sys.exit(f"span {span} is smaller than the binary ({len(image)})")

    ser = open_serial(args.port, LOADER_BAUD, timeout=0.05)
    print(f"{args.port} open at {LOADER_BAUD}; sending {os.path.basename(args.bin)} "
          f"({len(image)} bytes, span {span})")
    print("waiting for the loader: power on the Dreamcast with the dev disc now...")

    # Stay silent until the loader's banner: anything sent while the console
    # boots overruns the 16-byte SCIF FIFO and latches its receiver off
    # (see DC-LBA2 scripts/dc-serial-send.ps1).
    seen = b""
    announced = False
    last_magic = 0.0
    t_end = time.time() + args.wait
    while True:
        if time.time() > t_end:
            sys.exit("the loader announced itself but never answered: power-cycle with this "
                     "script already running" if announced else
                     f"no [DC-SERLOAD] banner in {args.wait} s: is the dev disc in the drive?")
        d = ser.read(64)
        if d:
            sys.stdout.write(console_text(d))
            sys.stdout.flush()
            seen =(seen + d)[-128:]
            if seen.endswith(b"RDY\n"):
                break
            if not announced and b"[DC-SERLOAD]" in seen:
                announced = True
        if announced and time.time() - last_magic >= 1.0:
            ser.write(b"LBA2LOAD")
            last_magic = time.time()
    print("loader ready")

    def read_ack(valid, timeout):
        # The reply byte only counts as the first byte or right after a
        # newline: the reply letters also occur in the loader's text.
        first, prev = True, 10
        t_end = time.time() + timeout
        while time.time() < t_end:
            d = ser.read(1)
            if not d:
                continue
            ch = d[0]
            if (first or prev == 10) and chr(ch) in valid:
                return chr(ch)
            sys.stdout.write(console_text(d))
            prev, first = ch, False
        return None

    ser.write(len(image).to_bytes(4, "little") + span.to_bytes(4, "little"))
    ack = read_ack("LF", 5)
    if ack != "L":
        sys.exit("the loader refused the image" if ack == "F" else "no reply to the header")

    t0 = time.time()
    offset = 0
    while offset < len(image):
        chunk = image[offset:offset + CHUNK]
        for attempt in range(3):
            ser.write(chunk + (sum(chunk) & 0xFFFF).to_bytes(2, "little"))
            ack = read_ack("KE", 15)
            if ack == "K":
                break
            if ack is None:
                sys.exit(f"transfer stalled at offset {offset}")
            print(f"\n  checksum mismatch at {offset}, resending")
        else:
            sys.exit(f"3 checksum failures at offset {offset}")
        offset += len(chunk)
        sys.stdout.write(f"\r  {100 * offset // len(image)}%  ({offset // 1024} / {len(image) // 1024} KB)")
        sys.stdout.flush()
    print(f"\nuploaded in {time.time() - t0:.1f} s; waiting for the probe banner...")

    got = collect_serial_text(ser, 10, b"[PROBE]")
    ser.close()
    if b"[PROBE]" in got:
        print("probe running; the link is now at 19200 8N1")
        return 0
    print("no [PROBE] banner within 10 s (the screen is the authority: check the TV)")
    return 1


def collect_serial_text(ser, seconds, marker):
    got = b""
    t_end = time.time() + seconds
    while time.time() < t_end:
        d = ser.read(64)
        if d:
            sys.stdout.write(console_text(d))
            sys.stdout.flush()
            got += d
            if marker in got and got.endswith(b"\n"):
                break
    return got


# -------------------------------------------------------------------- tests
def cmd_listen(link, args):
    print(f"listening on {link.name} for {args.seconds} s (Ctrl-C to stop)")
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        d = link.recv()
        if d:
            text = "".join(chr(b) if 32 <= b < 127 else "." for b in d)
            print(f"{time.time() - t0:8.3f}  {len(d):3d}B  {d.hex(' ')}  |{text}|")
    return 0


def cmd_loop(link, args):
    pattern = bytes(range(256))
    failures = 0
    for r in range(1, args.rounds + 1):
        collect(link, 0.2)                      # drop anything stale
        t0 = time.time()
        link.send(pattern)
        got = collect(link, 3.0, until=lambda g: len(g) >= len(pattern))
        dt = time.time() - t0
        if got == pattern:
            print(f"round {r}: 256/256 bytes back intact in {dt:.3f} s")
            continue
        failures += 1
        bad = [i for i in range(min(len(got), 256)) if got[i] != pattern[i]]
        print(f"round {r}: got {len(got)}/256 bytes, {len(bad)} differ")
        for i in bad[:8]:
            print(f"   offset {i:3d}: sent {pattern[i]:02x} got {got[i]:02x} "
                  f"(xor {pattern[i] ^ got[i]:02x})")
        if not got:
            print("   nothing came back: DC in ECHO mode? TX/RX crossed? (see the RX counter on screen)")
    print("LOOP OK" if failures == 0 else f"LOOP FAILED in {failures}/{args.rounds} rounds")
    return 1 if failures else 0


def cmd_rts(link, args):
    if not isinstance(link, SerialLink):
        sys.exit("rts needs the serial port, not the bridge")
    ser = link.ser
    print("watch 'CTS pin' on the probe screen (D-pad DOWN there cycles the DC's own RTS)")
    for r in range(args.rounds):
        for state in (True, False):
            ser.rts = state
            time.sleep(0.1)
            print(f"adapter RTS {'asserted' if state else 'released'}: the DC should show CTS "
                  f"{'LOW' if state else 'HIGH'} if the wire is there   "
                  f"[adapter CTS = {'asserted' if ser.cts else 'released'} = the DC's RTS]")
            time.sleep(2)
    ser.rts = True
    return 0


def cmd_motm(link, args):
    print(f"playing MOTM's side over {link.name}; the DC must be in FAKE MF2K or FAKE DM99 mode")
    collect(link, 0.2)
    link.send(bytes([0x92, 0x92]))              # cable probe, as MOTM does
    time.sleep(0.3)

    def step(label, payload, want_len, timeout=2.0):
        print(f"-> {label} {len(payload)}B  {payload.hex(' ')}")
        t0 = time.time()
        link.send(payload)
        got = collect(link, timeout, until=lambda g: any(len(f) >= want_len for f in frames_in(g)))
        frames = frames_in(got)
        if not frames:
            print(f"<- nothing in {timeout:.0f} s" + (f" ({len(got)} stray bytes: {got.hex(' ')})" if got else ""))
            return None
        f = frames[0]
        print(f"<- {time.time() - t0:.3f} s  {len(f)}B  {f.hex(' ')}")
        return f

    ack = step("upload request", UPLOAD_REQUEST, 23)
    game = next((g for g, a in ACKS.items() if a == ack), None)
    if game is None:
        print("FAILED: no acknowledgement" if ack is None else "FAILED: not a known acknowledgement")
        return 1
    print(f"   acknowledgement of {game.upper()}")

    reply = step("announce", ANNOUNCE, 17)
    if reply != ANNOUNCE_REPLY:
        print("FAILED: announce reply missing or different from the captures")
        return 1

    data = data_frame(game, args.points)
    echo = step(f"data ({args.points} points)", data, len(data))
    if echo != data:
        print("FAILED: the data frame was not echoed byte for byte")
        return 1
    print(f"MOTM UPLOAD DIALOGUE OK ({game.upper()} format, {args.points} points): "
          "the probe screen should log DATA ... chk OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=os.environ.get("DC_SERIAL", "COM7"))
    ap.add_argument("--bridge", metavar="HOST:PORT", help="test through the bridge instead of the serial port")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("upload")
    p.add_argument("--bin", default=os.path.normpath(DEFAULT_BIN))
    p.add_argument("--wait", type=int, default=90, help="seconds to wait for the loader")
    p = sub.add_parser("listen")
    p.add_argument("--seconds", type=float, default=60)
    p = sub.add_parser("loop")
    p.add_argument("--rounds", type=int, default=3)
    p = sub.add_parser("rts")
    p.add_argument("--rounds", type=int, default=3)
    p = sub.add_parser("motm")
    p.add_argument("--points", type=int, default=65)
    args = ap.parse_args()

    if args.cmd == "upload":
        return cmd_upload(args)

    link = BridgeLink(args.bridge) if args.bridge else SerialLink(args.port)
    try:
        return {"listen": cmd_listen, "loop": cmd_loop, "rts": cmd_rts, "motm": cmd_motm}[args.cmd](link, args)
    except KeyboardInterrupt:
        return 130
    finally:
        link.close()


if __name__ == "__main__":
    sys.exit(main())
