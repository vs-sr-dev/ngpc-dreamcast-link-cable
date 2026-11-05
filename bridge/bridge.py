#!/usr/bin/env python3
# NGPC <-> Dreamcast link-cable bridge (Ring 3).
#
# Sits between:
#   - beetle-ngp libretro core (patched, NGPC_LINK_ROLE=client) -- TCP byte stream on :42424
#   - Flycast (BattleCable=yes, server=127.0.0.1:42500)         -- UDP BattleCable framing
#
# UDP framing (from Flycast core/network/null_modem.h):
#   Flycast TX:  sendto(peer, ['D', byte], 2)   data packet
#                sendto(peer, ['B'],       1)   break packet
#   Flycast RX:  recvfrom bind LocalPort=37391, expects same frames from us.
#
# TCP framing (matches the patched beetle-ngp backend): raw 1-byte-at-a-time stream, no framing.
#
# Bridge translation:
#   UDP 'D' byte  -> write byte to TCP client
#   UDP 'B' break -> log, discarded (NGPC has no break concept)
#   TCP byte      -> sendto Flycast as ['D', byte]
#
# Run from repo root (stdlib only, Python 3.8+):
#   python bridge/bridge.py
# Optional env overrides: BRIDGE_UDP_BIND, BRIDGE_FLYCAST_HOST,
#                         BRIDGE_UDP_FLYCAST_PORT, BRIDGE_TCP_PORT,
#                         BRIDGE_LOG (file path; default: stderr only)
#
# For retail games use pure passthrough: leave every diagnostic variable
# below unset. See docs/PROTOCOL.md.

import os
import selectors
import socket
import sys
import time

UDP_BIND_PORT     = int(os.environ.get("BRIDGE_UDP_BIND",          "42500"))
UDP_FLYCAST_HOST  =     os.environ.get("BRIDGE_FLYCAST_HOST", "127.0.0.1")
UDP_FLYCAST_PORT  = int(os.environ.get("BRIDGE_UDP_FLYCAST_PORT",  "37391"))
TCP_BIND_PORT     = int(os.environ.get("BRIDGE_TCP_PORT",          "42424"))
LOG_PATH          =     os.environ.get("BRIDGE_LOG", "")
# DC->NGPC frame coalescing (default on). Flycast hands the SCIF bytes over
# one emulated frame at a time, so an FF-delimited frame can reach the NGPC
# in two pieces ~16 ms apart. MOTM reads until its buffer is momentarily
# empty, gives up mid-frame ("Huh, link broke!"), and the bytes it left
# behind (ending in FF) desync its frame parser on the next attempt. With
# coalescing, the bytes from an opening FF to the closing FF are held and
# delivered in one write; bytes outside a frame pass straight through.
# Byte values and order are unchanged; only delivery timing is.
#   BRIDGE_COALESCE_FRAMES=0          disable (pure byte-by-byte passthrough)
#   BRIDGE_COALESCE_TIMEOUT_MS=250    deliver an unterminated frame after this
COALESCE          =     os.environ.get("BRIDGE_COALESCE_FRAMES", "1") != "0"
COALESCE_TIMEOUT  = float(os.environ.get("BRIDGE_COALESCE_TIMEOUT_MS", "250")) / 1000.0
COALESCE_MAX      = 64
# Real Dreamcast instead of Flycast: talk to the DC serial port through a
# USB-UART adapter (needs pyserial). The NGPC BIOS sets its UART to 19200
# baud, 8N1, with CTS flow control (VECT_COMINIT: SC0MOD=49h, BR0CR=05h),
# so that is the default. RTS is asserted so that, if the adapter wires it
# to the Dreamcast's CTS, the game sees a peer ready to receive; changes of
# the adapter's CTS input (the Dreamcast's RTS, if wired) are logged.
#   BRIDGE_SERIAL=COM7            enable, replaces the Flycast UDP side
#   BRIDGE_BAUD=19200
#   BRIDGE_SERIAL_RTS=0           leave RTS deasserted
SERIAL_PORT       =     os.environ.get("BRIDGE_SERIAL", "")
SERIAL_BAUD       = int(os.environ.get("BRIDGE_BAUD", "19200"))
SERIAL_RTS        =     os.environ.get("BRIDGE_SERIAL_RTS", "1") != "0"
# Diagnostic: when set, bridge echoes a byte back to NGPC whenever it
# sees the configured trigger byte, to simulate a Flycast-side ack in
# isolation. Does NOT suppress forwarding to Flycast.
#   BRIDGE_ECHO_HANDSHAKE=1       enables the echo path
#   BRIDGE_ECHO_TRIGGER=92 (hex)  byte from NGPC that triggers echo
#   BRIDGE_ECHO_REPLY=92   (hex)  byte injected back to NGPC
ECHO_HANDSHAKE    =     os.environ.get("BRIDGE_ECHO_HANDSHAKE", "") == "1"
# Primary + optional secondary challenge/complement rules. Each (trigger, reply)
# fires every time the trigger byte is seen from NGPC.
ECHO_TRIGGER      = int(os.environ.get("BRIDGE_ECHO_TRIGGER",  "92"), 16)
ECHO_REPLY        = int(os.environ.get("BRIDGE_ECHO_REPLY",    "92"), 16)
ECHO_TRIGGER2_HEX =     os.environ.get("BRIDGE_ECHO_TRIGGER2", "")
ECHO_REPLY2_HEX   =     os.environ.get("BRIDGE_ECHO_REPLY2",   "")
ECHO_TRIGGER2     = int(ECHO_TRIGGER2_HEX, 16) if ECHO_TRIGGER2_HEX else None
ECHO_REPLY2       = int(ECHO_REPLY2_HEX,   16) if ECHO_REPLY2_HEX   else None
# Post-ack injection: after the first echo fires for a given TCP peer,
# optionally inject an arbitrary byte sequence (hex string, no spaces) into
# the NGPC stream. Used to empirically probe MOTM's state machine past the
# initial handshake without ROM disassembly.
POST_INJECT_HEX   =     os.environ.get("BRIDGE_POST_INJECT", "")
POST_INJECT       = bytes.fromhex(POST_INJECT_HEX) if POST_INJECT_HEX else b""
POST_INJECT_DELAY = float(os.environ.get("BRIDGE_POST_INJECT_DELAY_MS", "50")) / 1000.0

# Retail MF2K ACK synthesis — DEPRECATED.
# When enabled AND MF2K is connected via passthrough, BOTH the synth ACK
# and MF2K's own natural ACK arrive at NGPC -> MOTM reads 46 bytes of ACK
# instead of 23 and wedges into announce-only state (no data frame emitted).
# This was the actual root cause of the "reproducibility gap" described in
# docs/DEVLOG.md. Left in the code for archaeological replay scenarios
# (bridge-only, MF2K absent) but do NOT enable in live retail bridge mode.
# Canonical retail bridge invocation: no env vars, pure passthrough.
#   BRIDGE_SYNTH_MF2K_ACK=1                 enable frame-detection + synth
#   BRIDGE_MF2K_ACK_DELAY_MS=100            delay before synth reply (default 100ms)
# The captured retail MF2K ACK frame (replay observation):
#   FF 00 10 00 00 00 00 00 00 00 00 1C 00 00 04 00 00 0C 00 00 10 00 FF
SYNTH_MF2K_ACK    =     os.environ.get("BRIDGE_SYNTH_MF2K_ACK", "") == "1"
MF2K_ACK_DELAY    = float(os.environ.get("BRIDGE_MF2K_ACK_DELAY_MS", "100")) / 1000.0
MF2K_ACK_FRAME    = bytes([
    0xFF, 0x00, 0x10,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x1C, 0x00, 0x00, 0x04, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x10, 0x00,
    0xFF,
])
# Frame-detect pattern for MOTM upload-request (first 4 bytes are distinctive:
# FF opens, 00 preamble, 31 31 magic).
MOTM_UPLOAD_REQ_PREFIX = bytes([0xFF, 0x00, 0x31, 0x31])

# Full protocol replay: after we see MOTM's announce frame (16B starting with
# FF 00 10 02 01), if MOTM doesn't proceed to the data frame on its own, we
# inject the captured MOTM data frame DIRECTLY TO FLYCAST via UDP, as if
# MOTM had sent it. This drives the protocol to completion on the DC side
# even when the NGPC-side state machine aborts.
# The canonical data frame captured from Capture B (60 VS Points):
#   FF 00 10 00 00 02 00 00 00 00 43 00 00 06 01 00 00 00 00 06 00 00 3C 00 FF
SYNTH_DATA_FRAME   =     os.environ.get("BRIDGE_SYNTH_DATA_FRAME", "") == "1"
DATA_FRAME_DELAY   = float(os.environ.get("BRIDGE_DATA_FRAME_DELAY_MS", "50")) / 1000.0
# VS Points value to inject at offset 22 of the data frame (raw byte, 0-255).
# Default 0x3C = 60 (from original Capture B). Set via BRIDGE_VS_POINTS=<hex>.
VS_POINTS_VAL      = int(os.environ.get("BRIDGE_VS_POINTS", "3C"), 16)
MOTM_DATA_FRAME    = bytes([
    0xFF, 0x00, 0x10, 0x00, 0x00, 0x02,
    0x00, 0x00, 0x00, 0x00,
    0x43, 0x00, 0x00, 0x06, 0x01,
    0x00, 0x00, 0x00, 0x00,
    0x06, 0x00, 0x00, VS_POINTS_VAL, 0x00,
    0xFF,
])
# Pattern to detect MOTM's announce frame (distinctive prefix)
MOTM_ANNOUNCE_PREFIX = bytes([0xFF, 0x00, 0x10, 0x02, 0x01])


def open_log(path):
    try:
        f = open(path, "w", buffering=1)
    except OSError as e:
        sys.stderr.write(f"[bridge] cannot open log {path}: {e}\n")
        return None
    return f


_log_fp = None
_t0 = time.time()


def log(msg):
    line = f"[{time.time()-_t0:8.3f}] {msg}"
    sys.stderr.write(line + "\n")
    if _log_fp is not None:
        _log_fp.write(line + "\n")


def make_udp(bind_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", bind_port))
    s.setblocking(False)
    log(f"UDP bind OK on 0.0.0.0:{bind_port} (Flycast should have server={bind_port})")
    return s


def open_serial(port, baud, rts):
    """Open the USB-UART adapter and pump its input into a socket, so the
    main selector loop can wait on it like on the UDP and TCP sockets
    (Windows cannot select() on a COM port)."""
    try:
        import serial
    except ImportError:
        sys.exit("BRIDGE_SERIAL needs pyserial: python -m pip install pyserial")
    import threading
    ser = serial.serial_for_url(port, baudrate=baud, bytesize=8, parity="N",
                                stopbits=1, timeout=0.02, rtscts=False)
    try:
        ser.rts = rts
    except Exception:
        pass
    rx, tx = socket.socketpair()
    rx.setblocking(False)

    def pump():
        last_cts = None
        while True:
            try:
                data = ser.read(256)
                cts = ser.cts
            except Exception as e:
                log(f"serial read failed: {e}")
                tx.close()
                return
            if cts != last_cts:
                log(f"serial CTS {'asserted' if cts else 'released'} (the Dreamcast's RTS, if the adapter wires it)")
                last_cts = cts
            if data:
                tx.sendall(data)

    threading.Thread(target=pump, daemon=True).start()
    log(f"serial {port} open at {baud} 8N1")
    return ser, rx


def make_tcp_server(bind_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", bind_port))
    s.listen(1)
    s.setblocking(False)
    log(f"TCP listen OK on 0.0.0.0:{bind_port} (beetle-ngp client should connect here)")
    return s


def main():
    global _log_fp
    _log_fp = open_log(LOG_PATH) if LOG_PATH else None
    log(f"NGPC<->DC bridge starting -- pid={os.getpid()}")
    if SERIAL_PORT:
        log(f"Dreamcast peer: serial {SERIAL_PORT} {SERIAL_BAUD} 8N1, RTS {'on' if SERIAL_RTS else 'off'}")
        if SYNTH_DATA_FRAME:
            sys.exit("BRIDGE_SYNTH_DATA_FRAME talks to Flycast directly; not available with BRIDGE_SERIAL")
    else:
        log(f"Flycast peer: {UDP_FLYCAST_HOST}:{UDP_FLYCAST_PORT}")
    log(f"DC->NGPC frame coalescing {'ON' if COALESCE else 'OFF'}"
        + (f" (timeout {COALESCE_TIMEOUT*1000:.0f} ms)" if COALESCE else ""))
    if ECHO_HANDSHAKE:
        log(f"DIAG: ECHO_HANDSHAKE=1 -- rule1 0x{ECHO_TRIGGER:02x}->0x{ECHO_REPLY:02x}")
        if ECHO_TRIGGER2 is not None and ECHO_REPLY2 is not None:
            log(f"DIAG:                      rule2 0x{ECHO_TRIGGER2:02x}->0x{ECHO_REPLY2:02x}")
    if POST_INJECT:
        log(f"DIAG: POST_INJECT={POST_INJECT.hex()} delay={POST_INJECT_DELAY*1000:.0f}ms (fires once per TCP peer, after first echo)")
    if SYNTH_MF2K_ACK:
        log(f"SYNTH: MF2K ACK synthesis ENABLED -- reply frame {MF2K_ACK_FRAME.hex()} delay={MF2K_ACK_DELAY*1000:.0f}ms")
    if SYNTH_DATA_FRAME:
        log(f"SYNTH: MOTM data frame injection ENABLED -- payload {MOTM_DATA_FRAME.hex()} (VS Points={VS_POINTS_VAL} dec=0x{VS_POINTS_VAL:02x}) delay={DATA_FRAME_DELAY*1000:.0f}ms")

    udp = ser = ser_rx = None
    if SERIAL_PORT:
        ser, ser_rx = open_serial(SERIAL_PORT, SERIAL_BAUD, SERIAL_RTS)
    else:
        udp = make_udp(UDP_BIND_PORT)
    tcp_srv = make_tcp_server(TCP_BIND_PORT)

    sel = selectors.DefaultSelector()
    if udp is not None:
        sel.register(udp, selectors.EVENT_READ, data="udp")
    if ser_rx is not None:
        sel.register(ser_rx, selectors.EVENT_READ, data="serial")
    sel.register(tcp_srv, selectors.EVENT_READ, data="tcp_accept")

    tcp_peer = None
    tcp_peer_addr = None
    flycast_peer_seen = False
    post_inject_fired = False
    ngpc_tail = bytearray()      # ring of last 4 bytes from NGPC (for upload-req prefix match)
    synth_ack_pending = False    # True when we saw the prefix, waiting for closing FF
    synth_ack_fired = False      # fire once per TCP session
    frame_buf = bytearray()      # accumulator from opening FF to closing FF
    dc_frame = bytearray()       # DC->NGPC frame being assembled (COALESCE)
    dc_frame_t0 = 0.0

    def to_ngpc(data, what=None):
        nonlocal tcp_peer
        if tcp_peer is None:
            log(f"  (no NGPC peer, {what or 'byte'} dropped)")
            return
        try:
            tcp_peer.sendall(data)
            if what:
                log(f"  -> NGPC {what} delivered in one write")
        except OSError as e:
            log(f"TCP send to NGPC failed: {e}; dropping peer")
            sel.unregister(tcp_peer)
            tcp_peer.close()
            tcp_peer = None

    def from_dc(byte):
        nonlocal dc_frame, dc_frame_t0
        if COALESCE and (dc_frame or byte == 0xFF):
            if not dc_frame:
                dc_frame_t0 = time.time()
            dc_frame.append(byte)
            if (byte == 0xFF and len(dc_frame) > 1) or len(dc_frame) >= COALESCE_MAX:
                to_ngpc(bytes(dc_frame), f"frame {len(dc_frame)}B")
                dc_frame = bytearray()
        else:
            to_ngpc(bytes([byte]))

    while True:
        events = sel.select(timeout=0.02 if dc_frame else 1.0)
        if dc_frame and time.time() - dc_frame_t0 > COALESCE_TIMEOUT:
            to_ngpc(bytes(dc_frame), f"unterminated frame {len(dc_frame)}B (timeout)")
            dc_frame = bytearray()
        for key, _ in events:
            if key.data == "udp":
                while True:
                    try:
                        pkt, addr = udp.recvfrom(256)
                    except BlockingIOError:
                        break
                    except OSError as e:
                        log(f"UDP recv error: {e}")
                        break
                    if not flycast_peer_seen:
                        log(f"Flycast peer seen from {addr[0]}:{addr[1]}")
                        flycast_peer_seen = True
                    if len(pkt) == 2 and pkt[0:1] == b"D":
                        byte = pkt[1]
                        log(f"UDP<-Flycast 'D' {byte:02x}")
                        from_dc(byte)
                    elif len(pkt) == 1 and pkt[0:1] == b"B":
                        log("UDP<-Flycast 'B' break (discarded, NGPC has no break)")
                    else:
                        log(f"UDP<-Flycast unexpected packet len={len(pkt)} head={pkt[:4]!r}")

            elif key.data == "serial":
                try:
                    data = ser_rx.recv(4096)
                except BlockingIOError:
                    continue
                if not data:
                    log("serial reader stopped; exiting")
                    return
                for byte in data:
                    log(f"SER<-DC {byte:02x}")
                    from_dc(byte)

            elif key.data == "tcp_accept":
                try:
                    conn, addr = tcp_srv.accept()
                except BlockingIOError:
                    continue
                if tcp_peer is not None:
                    log(f"TCP second client {addr} rejected (already have {tcp_peer_addr})")
                    conn.close()
                    continue
                conn.setblocking(False)
                tcp_peer = conn
                tcp_peer_addr = addr
                post_inject_fired = False
                synth_ack_pending = False
                synth_ack_fired = False
                ngpc_tail = bytearray()
                frame_buf = bytearray()
                sel.register(conn, selectors.EVENT_READ, data="tcp_peer")
                log(f"TCP accept from {addr[0]}:{addr[1]} (NGPC peer attached)")

            elif key.data == "tcp_peer":
                try:
                    chunk = tcp_peer.recv(256)
                except BlockingIOError:
                    continue
                except OSError as e:
                    log(f"TCP recv error: {e}")
                    chunk = b""
                if not chunk:
                    log(f"TCP peer {tcp_peer_addr} disconnected")
                    sel.unregister(tcp_peer)
                    tcp_peer.close()
                    tcp_peer = None
                    tcp_peer_addr = None
                    continue
                if ser is not None:
                    # one write per TCP chunk: the frame goes out back to back
                    try:
                        ser.write(chunk)
                    except Exception as e:
                        log(f"serial write failed: {e}")
                for b in chunk:
                    if ser is not None:
                        log(f"TCP<-NGPC {b:02x} -> SER->DC {b:02x}")
                    else:
                        pkt = bytes([0x44, b])
                        try:
                            udp.sendto(pkt, (UDP_FLYCAST_HOST, UDP_FLYCAST_PORT))
                        except OSError as e:
                            log(f"UDP send to Flycast failed: {e}")
                            break
                        log(f"TCP<-NGPC {b:02x} -> UDP->Flycast 'D' {b:02x}")
                    if SYNTH_MF2K_ACK:
                        # Track last 4 bytes from NGPC, detect MOTM upload-request prefix
                        ngpc_tail.append(b)
                        if len(ngpc_tail) > 4:
                            del ngpc_tail[0]
                        if b == 0xFF and len(frame_buf) == 0:
                            # opening FF
                            frame_buf.append(b)
                        elif len(frame_buf) > 0:
                            frame_buf.append(b)
                            if b == 0xFF and len(frame_buf) > 1:
                                # closing FF — frame complete
                                frame_hex = ' '.join(f'{x:02x}' for x in frame_buf)
                                log(f"  [SYNTH] NGPC frame complete ({len(frame_buf)}B): {frame_hex}")
                                if bytes(frame_buf[:4]) == MOTM_UPLOAD_REQ_PREFIX:
                                    # schedule MF2K ACK synthesis
                                    if MF2K_ACK_DELAY > 0:
                                        time.sleep(MF2K_ACK_DELAY)
                                    try:
                                        tcp_peer.sendall(MF2K_ACK_FRAME)
                                        log(f"  [SYNTH-ACK] sent MF2K ACK frame ({len(MF2K_ACK_FRAME)}B) back to NGPC")
                                    except OSError as e:
                                        log(f"  [SYNTH-ACK] send failed: {e}")
                                elif SYNTH_DATA_FRAME and len(frame_buf) >= 5 and bytes(frame_buf[:5]) == MOTM_ANNOUNCE_PREFIX:
                                    # MOTM sent announce frame; inject the captured data frame
                                    # to Flycast directly so MF2K sees a complete upload session
                                    if DATA_FRAME_DELAY > 0:
                                        time.sleep(DATA_FRAME_DELAY)
                                    try:
                                        for db in MOTM_DATA_FRAME:
                                            udp.sendto(bytes([0x44, db]), (UDP_FLYCAST_HOST, UDP_FLYCAST_PORT))
                                        log(f"  [SYNTH-DATA] injected MOTM data frame ({len(MOTM_DATA_FRAME)}B) directly to Flycast")
                                    except OSError as e:
                                        log(f"  [SYNTH-DATA] send failed: {e}")
                                frame_buf = bytearray()
                            elif len(frame_buf) > 64:
                                # safety: abort over-long frame
                                log(f"  [SYNTH] frame buffer overflow, resetting")
                                frame_buf = bytearray()
                    if ECHO_HANDSHAKE:
                        reply_byte = None
                        if b == ECHO_TRIGGER:
                            reply_byte = ECHO_REPLY
                        elif ECHO_TRIGGER2 is not None and b == ECHO_TRIGGER2:
                            reply_byte = ECHO_REPLY2
                        if reply_byte is not None:
                            try:
                                tcp_peer.sendall(bytes([reply_byte]))
                                log(f"  [DIAG-ECHO] saw 0x{b:02x}, injected 0x{reply_byte:02x} back to NGPC")
                                if POST_INJECT and not post_inject_fired:
                                    if POST_INJECT_DELAY > 0:
                                        time.sleep(POST_INJECT_DELAY)
                                    tcp_peer.sendall(POST_INJECT)
                                    log(f"  [DIAG-INJECT] sent post-ack sequence ({len(POST_INJECT)}B): {POST_INJECT.hex()}")
                                    post_inject_fired = True
                            except OSError as e:
                                log(f"  [DIAG-ECHO] inject failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted, bye")
