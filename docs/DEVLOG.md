# Development log

A condensed English account of the working sessions that produced this
repository (April 2026). The original, much longer log was kept in Italian
as part of a larger homebrew project and is not included. The timings are
real wall-clock times, as recorded in that log.

Names in this log are the ones used at the time. Before publication the
environment variables were renamed (`SR3_LINK_*` → `NGPC_LINK_*`,
`SR3_MMIO` → `NGPC_LINK_MMIO`, `SR3_BRIDGE_*` → `BRIDGE_*`) and the
hard-coded log paths were replaced by `NGPC_LINK_LOG_DIR` / `BRIDGE_LOG`.
The logs in [`captures/`](../captures/) predate the rename.

---

## Session 2 — Is it even possible? (survey and first trace)

The NGPC–Dreamcast cable shipped with a handful of retail pairs (Capcom vs.
SNK, King of Fighters, Cool Cool Toon, Bikkuriman 2000) and was never used
by homebrew. The first question was which emulators model it. The answer
was none, on either side, and Flycast turned out to be the exception: its
BattleCable option already put the Dreamcast serial port on UDP. The
NGPC emulators were surveyed for the cheapest place to add the other end;
see [EMULATOR_SURVEY.md](EMULATOR_SURVEY.md).

The deciding question was whether a retail game talks to the BIOS
comms system calls or pokes the UART registers itself. If it uses the
BIOS, an HLE BIOS is enough. A BizHawk Lua trace failed: BizHawk's NGPC core
did not deliver execute callbacks on the BIOS addresses. MAME's debugger
worked: breakpoints on the eight comms vectors plus watchpoints on the
serial registers, with *Match of the Millennium* in its link menu.

**Result:** MOTM uses only the BIOS vectors. The only cart-side register
writes were two setup writes to `SC0CR`. The trace also showed the first
traffic: `0x92` repeated, and a frame delimited by `0xFF`.

## Session 3 — Ring 1: loopback inside the core

beetle-ngp's HLE BIOS already calls `system_comms_read/poll/write`, which
upstream leaves empty. They were filled with a 64-byte ring buffer and file
logging (RetroArch drops a core's stderr on Windows). A first homebrew ROM
went through `SWI 1`. It failed twice, for two separate reasons:
beetle-ngp's software-interrupt HLE appeared to read the vector number from
the wrong register, and ASM900 mis-assembled `LD (mem),W`, so the status
byte could not be read back. The demo was rewritten to call the HLE entry
points directly, and the status was given a way around the register problem:
the core mirrors status and byte into two RAM cells, `0x6BFC`/`0x6BFD`.
Press A, the byte comes back, both counters go up.

That side-channel worked, and it caused the worst bug of the project two
sessions later.

## Session 4 — Ring 2: two NGPCs over TCP

The same hooks got a Winsock backend chosen by environment variable:
server or client, non-blocking, lazy accept and reconnect. Two RetroArch
instances exchanged bytes on the first try. The only friction was the build:
MSYS2's bash drops `TMPDIR`, gcc then tries to write its temporary files in
`C:\WINDOWS`, and the fix is a `SHELL` wrapper that re-injects the variable.

## Session 5 — Ring 3: NGPC ↔ Dreamcast (~15 minutes)

Reading Flycast's `null_modem.h` gave the whole UDP format in one pass: `'D'`
plus a byte, or `'B'` for a break, with no handshake. A 146-line bridge
translated between that and the core's raw TCP stream. A Dreamcast demo in
pure KallistiOS sent bytes from the controller buttons. The two demos
exchanged bytes in both directions, at full speed, on the first run. The
bridge log also showed the KOS boot banner arriving before the NGPC
connected: with BattleCable on, Flycast hands the serial port of *every*
game to the pipe.

## Session 6 — The 0x6D detour

The retail pair, *Match of the Millennium* and *Millennium Fight 2000*, then
went through the same setup. MOTM sent `0x92` twice and froze; MF2K said
nothing. A diagnostic mode in the bridge answered `0x92` on Flycast's behalf.
An echo of `0x92` made MOTM reset after about 3.6 seconds; `0x6D`, its
complement, made it sit still. "Sitting still" was read as "accepted,
waiting for data", and the session closed on that. Session 7 found the
reading was wrong.

## Session 7 — The peek bug, and MOTM's state machine

Reading `biosHLE.c` again showed that `VECT_COMRECIVESTATUS` calls
`system_comms_read(NULL)` to *count* waiting bytes. The TCP backend did a
real `recv()` there, so every status check ate the byte that the next read
was supposed to return. The homebrew demo had never called that vector, so
the bug had been invisible. Fix: `MSG_PEEK` when the buffer is NULL.

Then MAME's debugger, properly this time (TLCS-900H in MAME 0.287: the
stack pointer is `xssp`, conditions need `0x` constants). The first
"caller" address was a return address inside MOTM's own BIOS dispatcher at
`0x3ABDB9`, which multiplies the vector number in W by 4 and calls through
the table at `0xFFFE00`. Breaking on the dispatcher's trampoline gave the
real call sites and the polling routine:

```
201F39  cp  (0x004DA9), 0x92   ; last received byte
201F3F  ret NZ
```

The acknowledgement is the **echo**, `0x92`. `0x6D` had only kept MOTM
polling. With the echo and the peek fix, MOTM reached its VS screen once,
then reset; a second run hung. This was put down to a timing race.

*In hindsight:* every MOTM run in Sessions 6 and 7 still had the RAM
side-channel active (it became optional in Session 8). The resets and the
run-to-run differences were very likely caused, at least in part, by the
core writing into MOTM's RAM, not by timing.

## Session 8 — "Why would logging make it hang?" (~7 hours)

MF2K, on its *Download Stand By* screen, stayed silent under everything:
all 256 byte values, BREAKs, common magic pairs, and the 8-byte frame from
the Session 2 trace. A GameFAQs guide found by the user gave the missing
context: the cable carries VS Points from MOTM to the Dreamcast, started
from MOTM's *Send to DC* menu.

To capture that, MOTM was run on the patched core in loopback. It hung in
the VS menu. The user pointed out the contradiction: *the only way I reach
VS mode and the upload is with the stock core — why would just reading a
log make it hang?* The answer was the side-channel. The patched core wrote
`0x6BFC`/`0x6BFD` on every comms call, and MOTM keeps its own state there.
It was gated behind `SR3_MMIO=1`, off by default, and MOTM immediately ran
cleanly.

From there it went quickly:

1. The loopback log showed the 256-byte `92 92` VS sync blocks, and then,
   on *Send to DC*, the upload request `FF 00 31 31 00×13 FF`.
2. Replaying that frame straight into Flycast got MF2K's first reply ever:
   a 23-byte `FF 00 10 … FF` acknowledgement, and the screen
   *データの受信は中断されました* ("reception interrupted").
3. A bridge mode that synthesised that acknowledgement got MOTM to send its
   next frame (the announce).
4. On a second *Send to DC* in the same session, MOTM sent a third frame
   with the points at offset 22 (`0x3C` = 60). MF2K echoed it and showed
   *データの受信を完了しました* with `60 vs.`, Karin said the data had been
   uploaded, and the eight secret characters were unlocked in MOTM's save.

Then two hours went into trying to reproduce it for a video, and it would
not reproduce: the data frame never came again, and MOTM's RAM showed its
handshake flag never set.

## Session 9 — The bridge was the bug (~75 minutes)

Rereading the two captures from scratch showed that "capture A" and
"capture B" were the same bridge process, with the failed first Send and
the successful second one twelve minutes apart. In the failed Send, the
NGPC received the 23-byte acknowledgement **twice**: once synthesised by the
bridge and once from MF2K, which got the forwarded request and answered by
itself. MOTM cannot parse two. On the second Send the synthesiser had
already fired (it was latched once per connection), so MOTM got one
acknowledgement and completed the upload. Every reproduction attempt had
been a first Send, with two acknowledgements, so every one of them failed
the same way.

Test: the bridge with no diagnostic mode at all, both games cold-booted.
The first Send completed the full six-frame exchange, with the success
dialogue and the unlock. A fresh reset reproduced it.

Two last findings from that run:

- Offset 10 of the data frame is the VS Points plus 7 (60→`43`, 65→`48`, 25→`20`).
- A second upload from a save that already has the unlock sends the same
  bytes and the Dreamcast takes the points, but MOTM shows an error. That is
  MOTM's own logic, not the link.

**Lesson:** when an A/B test is compared with the only successful run,
check that the harness is in the same *internal* state, not just the same
configuration.

## After the sessions — the reconnect that blocked (November 2026)

While the repository was being prepared, a review of the core patch found
one more bug, which no session had hit because the bridge was always
started first. With the peer missing, the client called a blocking
`connect()` on every comms call, and on Windows a refused connect to
localhost takes about 2 s. A test harness that drives the hooks directly,
with the peer down for 3 s and then for 1.5 s, measured the slowest single
call at **3168 ms** with the session-era core and **2.3 ms** with the fix
(a non-blocking connect, polled, retried once per second). In RetroArch
that is the difference between a frozen window and nothing at all.

The same day the whole chain ran live for the first time since April,
with the renamed core and bridge. It found one more problem. The upload
went through, and MF2K showed the 40 points, but MOTM said *"Huh, link
broke!"* and unlocked nothing. The core log showed MOTM had read 22 of the
25 bytes of MF2K's final echo: Flycast had delivered the last three 15 ms
later, in the next emulated frame, and MOTM had stopped reading as soon as
its buffer ran dry. A retry failed at once, because MOTM first read the
three leftover bytes, and their `FF` put its frame parser one delimiter out
of step.

Looking back, the April captures had the same split frames. Whether MOTM
coped seems to depend on where the gap falls; Session 9's "error because
the save had already uploaded" was probably this instead. The bridge now
holds each DC→NGPC frame until its closing `FF` and delivers it in one
write. On the next attempt Flycast split two frames late again; MOTM got
them whole, showed the success line and unlocked the eight characters.

---

## The bugs, in one table

| Bug | Where | Symptom | Cost |
|---|---|---|---|
| Destructive peek | core, `system_comms_read(NULL)` | MOTM polls forever | Session 6 conclusions |
| RAM side-channel on retail | core, `0x6BFC`/`0x6BFD` writes | MOTM hangs/resets in VS menu, only on our core | Sessions 6-8 |
| Double acknowledgement | bridge, `SYNTH_MF2K_ACK` | MOTM stops after the announce frame | end of Session 8 |
| Blocking reconnect | core, client `connect()` | RetroArch freezes while the bridge is down | never hit; found in review |
| Split frames | bridge, byte-by-byte delivery | "Huh, link broke!", then a poisoned retry | intermittent since April; found live in November |

All of them were in our own tooling, and none was in the games or in
Flycast. Two came to light because the user asked why an observation did
not fit.
