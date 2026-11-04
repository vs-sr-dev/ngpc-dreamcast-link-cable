# The retail protocol: Match of the Millennium ↔ Millennium Fight 2000

What *SNK vs. Capcom: The Match of the Millennium* (NGPC, "MOTM") and
*Capcom vs. SNK: Millennium Fight 2000* (Dreamcast, Japan Rev A, "MF2K")
say to each other over the link cable, as captured through this bridge.
Every frame quoted here is in [`captures/retail/`](../captures/retail/), and
`python tools/frames.py <log>` reproduces the listings.

Offsets count from the opening `FF` (offset 0). "Hypothesis" marks anything
not confirmed by at least two independent data points.

## Overview

| Phase | Direction | Bytes | When |
|---|---|---|---|
| Cable probe | NGPC → | `92 92 …`, repeated | while MOTM is in the VS menu |
| VS sync stream | NGPC ↔ NGPC | 256-byte blocks headed `92 92` | only once a peer echoes `92` |
| Upload request | NGPC → DC | 18-byte frame `FF 00 31 31 … FF` | the player chooses *Send to DC* |
| Acknowledgement | DC → NGPC | 23-byte frame `FF 00 10 … FF` | ~45 ms later |
| Announce | NGPC → DC | 16-byte frame | |
| Announce reply | DC → NGPC | 17-byte frame | |
| Data | NGPC → DC | 25-byte frame, carries the VS Points | |
| Data echo | DC → NGPC | the same 25 bytes | MF2K confirms by echoing |

The whole upload takes about 270 ms. The frames are delimited by `0xFF`
and never contain it.

## Setting it up in the games

- **MF2K**: open Secret Mode and wait on **Download Stand By** (the
  "waiting for data" screen). In this state MF2K only listens: it sent
  nothing in 60 s of observation.
- **MOTM**: accumulate VS Points (Olympic mode), open the VS menu, choose
  **Send to DC** and press A.

## Phase 1: the cable probe (`0x92`)

As soon as MOTM is in the VS menu it sends `0x92` about every 30 ms and
watches for the same byte to come back. Its polling routine (MAME
disassembly, cart addresses):

```
201F1A  ld   RW3, 0x17          ; VECT_COMSENDSTATUS
201F1E  call 0x200474           ; MOTM's BIOS dispatcher
201F22  ld   WA, RWA3           ; send buffer count
201F2C  and  A, A
201F2E  jr   NZ, 0x201F39       ; still busy: don't queue another
201F30  ld   (0x004DA7), 0x92   ; queue 0x92
201F36  calr 0x2020C9           ; send it (CREATEDATA inside)
201F39  cp   (0x004DA9), 0x92   ; last received byte == 0x92 ?
201F3F  ret  NZ                 ; no: keep polling
201F41  ...                     ; yes: clear state, set bit 0 of 0x4DA5, enter stage 2
```

The acknowledgement is the **literal echo** `0x92`. An early hypothesis
(`0x6D`, the complement) was wrong; see [DEVLOG.md](DEVLOG.md#session-6--the-0x6d-detour).

MF2K **never** answers the probe: the upload below works with the probe
unanswered. The echo comes from another MOTM (NGPC ↔ NGPC VS play), or from
the core's loopback backend, which echoes everything.

### The MOTM side, in RAM

| Address | Meaning |
|---|---|
| `0x4DA5` | link state flags; bit 0 = probe acknowledged ("handshake complete") |
| `0x4DA7` | byte about to be sent (`0x92` while probing) |
| `0x4DA8` | byte just sent |
| `0x4DA9` | last byte received (written by the RX routine at `0x202073` → `VECT_COMGETDATA`) |
| `0x4D3E` | set by the stage-2 entry at `0x2009B2` |

The core patch dumps these to its log on every `0xFF` it sends.

## Phase 2: the VS sync stream (NGPC ↔ NGPC)

Once the probe is echoed, MOTM starts a continuous stream of 256-byte
blocks, each starting with `92 92`. The rest is mostly zeros, with
triple-repeated values (`08 08 08`, `04 04`, `02 02 02` …).

*Hypothesis:* this is the NGPC ↔ NGPC VS mode synchronisation (inputs and
state, with repetition as error protection). It is not part of the
Dreamcast upload, and earlier sessions mistook it for one.

## Phase 3: the upload

From the deterministic capture (`deterministic_3runs_bridge.log`, first
run, 65 VS Points):

```
  79.201  NGPC->DC  18B  ff 00 31 31 00 00 00 00 00 00 00 00 00 00 00 00 00 ff
  79.248  DC->NGPC  23B  ff 00 10 00 00 00 00 00 00 00 00 1c 00 00 04 00 00 0c 00 00 10 00 ff
  79.272  NGPC->DC  16B  ff 00 10 02 01 00 00 00 00 01 00 00 01 01 00 ff
  79.315  DC->NGPC  17B  ff 00 10 00 00 01 00 00 00 00 01 00 00 01 01 00 ff
  79.441  NGPC->DC  25B  ff 00 10 00 00 02 00 00 00 00 48 00 00 06 01 00 00 00 00 06 00 00 41 00 ff
  79.473  DC->NGPC  25B  ff 00 10 00 00 02 00 00 00 00 48 00 00 06 01 00 00 00 00 06 00 00 41 00 ff
```

### Upload request (NGPC → DC, 18 bytes)

```
FF 00 31 31 00 00 00 00 00 00 00 00 00 00 00 00 00 FF
```

Constant across every capture. `31 31` is the command. In a loopback
capture MOTM sent `10 10 10 00` just before it; over the live link that
prologue does not appear.

### Acknowledgement (DC → NGPC, 23 bytes)

```
offset  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22
        FF 00 10 00 00 00 00 00 00 00 00 1C 00 00 04 00 00 0C 00 00 10 00 FF
```

Constant across every capture. Values at offsets 11, 14, 17, 20.
*Hypothesis:* these describe what MF2K offers or expects (unlock categories,
in the guide's terms); their meaning is not decoded.

### Announce (NGPC → DC, 16 bytes) and reply (DC → NGPC, 17 bytes)

```
NGPC  FF 00 10 02 01 00 00 00 00 01 00 00 01 01 00 FF
DC    FF 00 10 00 00 01 00 00 00 00 01 00 00 01 01 00 FF
```

Both constant, regardless of the points. The reply is not an echo: it is
one byte longer and differs at offsets 3-5.

### Data (NGPC → DC, 25 bytes) and echo

| Offset | Value (65 pts) | Meaning |
|---|---|---|
| 0 | `FF` | open |
| 1-2 | `00 10` | command, same as the other data-phase frames |
| 3-5 | `00 00 02` | subtype (hypothesis: "points follow") |
| 6-9 | `00 00 00 00` | |
| 10 | `48` | **VS Points + 7** (4 data points: 60→`43`, 65→`48`, 25→`20`, 40→`2F`) |
| 11-12 | `00 00` | |
| 13-14 | `06 01` | |
| 15-18 | `00 00 00 00` | |
| 19 | `06` | |
| 20-21 | `00 00` | |
| 22 | `41` | **VS Points**, raw binary (60→`3C`, 65→`41`, 25→`19`, 40→`28`) |
| 23 | `00` | hypothesis: high byte of a 16-bit little-endian count (the guide gives a 0-9999 range); never seen non-zero |
| 24 | `FF` | close |

MF2K echoes the frame byte for byte. That echo is the final confirmation.

## Outcome

On a first successful upload:

- MF2K shows **データの受信を完了しました** ("data reception complete") and
  the points (`65 vs.`).
- MOTM's Karin says *"It's over. The data's been safely uploaded."*
- MOTM's character select now shows **all eight secret characters**. The
  game sets this flag in its save only after a link it accepts, which makes
  it the strongest evidence that the exchange is authentic.

If MF2K gets the request but nothing after it, it shows
**データの受信は中断されました** ("data reception was interrupted").

### MOTM reads a frame until its buffer runs dry

MOTM reads an incoming frame byte by byte and, if its receive buffer goes
empty before the closing `FF`, it may give up: Karin says *"Huh, link
broke!"*. The points still reach MF2K (it has already echoed them) but stay
on MOTM too, and nothing is unlocked.

Flycast delivers the serial bytes one emulated frame at a time, so a frame
from MF2K sometimes arrives in two pieces about 16 ms apart. Whether MOTM
survives that seems to depend on where the gap falls:

| Run | Gap in MF2K's data echo, after byte | MOTM |
|---|---|---|
| Session 9, run 1 | none | success |
| Session 9, run 3 | 6 | success |
| Session 8, capture B | 11 | success |
| Session 9, run 2 | 13 | Karin error |
| 2026-11-04, fresh save | 22 | "Huh, link broke!" (read 22 of 25 bytes) |

Five runs are not proof of a threshold, but the last one rules out the
explanation recorded in Session 9 for run 2 ("MOTM's error path for a save
that has already uploaded"): its save was fresh.

Worse, the bytes MOTM leaves unread stay in the stream. On the next
attempt MOTM reads them first; the stray `FF` among them opens a frame in
its parser, every delimiter after it is off by one, and MOTM rejects a
perfectly good acknowledgement at once (`captures/retail/live_split_echo_*`).

The bridge therefore **coalesces** DC→NGPC frames by default: bytes from an
opening `FF` to the closing `FF` are held and delivered in one write.
Byte values and order do not change. In the first run with coalescing,
Flycast split both the acknowledgement (after byte 22) and the data echo
(after byte 19); MOTM received each in one piece, showed the success line
and unlocked the eight characters (`captures/retail/live_coalesced_success_*`).

A real cable has no such gaps: the UART delivers a frame's bytes back to
back. MOTM was never written to tolerate a pause in the middle.

## Pitfalls we hit

- **A frame split in two** can stop MOTM mid-read and poison the next
  attempt; see above. Keep `BRIDGE_COALESCE_FRAMES` at its default (on).
- **Two acknowledgements stop MOTM.** If the NGPC receives the 23-byte ack
  twice (for instance from the bridge's `BRIDGE_SYNTH_MF2K_ACK` mode *and*
  from MF2K), MOTM sends the announce and then stops: no data frame. Leave
  the diagnostic modes off.
- **A peek that consumes** makes MOTM poll forever
  ([ARCHITECTURE.md](ARCHITECTURE.md#the-read-hook-must-not-consume-on-a-status-query)).
- **Writing into the game's RAM** (the homebrew side-channel) hangs MOTM in
  the VS menu. Keep `NGPC_LINK_MMIO=0` for retail.
- **After a failed attempt, restart MOTM** before trying again, in case its
  frame parser was left inside a frame.

## What is still open

- The meaning of the ack's four values and of offsets 13-14 and 19 of the data frame.
- Why offset 10 is the points plus 7.
- MOTM's other link partners (*King of Fighters: Dream Match 1999* and the
  other games paired with NGPC titles) have not been tried; the guide
  suggests the Dream Match protocol differs.
- The `0x92` VS sync stream between two MOTMs has only been observed in
  loopback, not decoded.
- One passthrough run from Session 8 (`captures/experiments/mf2k_pure.log`)
  stopped after a single, correct acknowledgement, exactly like the second
  attempt of 2026-11-04. Leftover bytes from an earlier split frame are the
  likely cause, but that run has no core log to confirm it.
- Whether an already-uploaded save really makes MOTM answer with an error
  (the Session 9 reading of run 2) is now untested.
