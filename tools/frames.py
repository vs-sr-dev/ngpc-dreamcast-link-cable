#!/usr/bin/env python3
# Rebuild the FF-delimited frames from a bridge log.
#
# Reads the per-byte lines bridge.py writes:
#   [  79.201] TCP<-NGPC ff -> UDP->Flycast 'D' ff     (NGPC -> DC)
#   [  79.248] UDP<-Flycast 'D' ff                      (DC -> NGPC)
# and prints one line per frame, per direction, with the time of its first
# byte. Bytes outside a frame (the 0x92 cable probe, the VS sync stream) are
# collapsed into a run count.
#
#   python tools/frames.py captures/test1_nosynth_bridge.log

import re
import sys

LINE = re.compile(r"^\[\s*([\d.]+)\]\s+(?:TCP<-NGPC ([0-9a-f]{2})|UDP<-Flycast 'D' ([0-9a-f]{2}))")
EVENT = re.compile(r"^\[\s*([\d.]+)\]\s+(TCP accept.*|TCP peer .*disconnected|.*\[SYNTH[^\]]*\].*sent.*|.*\[SYNTH-DATA\].*)$")


def main(path):
    state = {"NGPC->DC": {"buf": None, "t": None, "idle": 0, "idle_b": None},
             "DC->NGPC": {"buf": None, "t": None, "idle": 0, "idle_b": None}}

    def flush_idle(d, s):
        if s["idle"]:
            print(f"          {d}  ({s['idle']} bytes outside frames, last {s['idle_b']:02x})")
            s["idle"] = 0

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            ev = EVENT.match(raw)
            if ev:
                print(f"{float(ev.group(1)):9.3f}  -- {ev.group(2).strip()}")
                continue
            m = LINE.match(raw)
            if not m:
                continue
            t = float(m.group(1))
            d = "NGPC->DC" if m.group(2) else "DC->NGPC"
            b = int(m.group(2) or m.group(3), 16)
            s = state[d]
            if s["buf"] is None:
                if b == 0xFF:
                    flush_idle(d, s)
                    s["buf"], s["t"] = [b], t
                else:
                    s["idle"] += 1
                    s["idle_b"] = b
            else:
                s["buf"].append(b)
                if b == 0xFF and len(s["buf"]) > 1:
                    hexs = " ".join(f"{x:02x}" for x in s["buf"])
                    print(f"{s['t']:9.3f}  {d}  {len(s['buf']):2d}B  {hexs}")
                    s["buf"] = None
    for d, s in state.items():
        flush_idle(d, s)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: frames.py <bridge log>")
    main(sys.argv[1])
