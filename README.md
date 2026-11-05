<p align="center"><sub><i>Neo Geo Pocket Color, SNK vs. Capcom: The Match of the Millennium and every other SNK name are trademarks of SNK. Dreamcast is a trademark of Sega. Capcom vs. SNK: Millennium Fight 2000 is a trademark of Capcom. Those owners have nothing to do with this project. This is an unofficial, non-commercial research project that contains no game data, no BIOS and no emulator binaries. Read the code, build it yourself.</i></sub></p>

# ngpc-dreamcast-link-cable

**A virtual NGPC ↔ Dreamcast link cable between two separate emulators.**
A Neo Geo Pocket Color running in RetroArch (beetle-ngp) and a Dreamcast
running in Flycast exchange bytes as if they were joined by SNK's
NGPC–Dreamcast cable. The retail pair *SNK vs. Capcom: The Match of the
Millennium* (NGPC) and *Capcom vs. SNK: Millennium Fight 2000* (Dreamcast)
completes its upload over it: the Dreamcast receives the VS Points, and the
NGPC unlocks the eight secret characters it gives out on the first
successful link.
A second pair, *King of Fighters R-2* and MOTM with *The King of Fighters
Dream Match 1999*, works over the same bridge without changes.

As far as we know, no emulator emulated this cable before. Flycast already
had a serial "battle cable" over UDP; no NGPC emulator had anything on the
other end. This repository adds that end, plus the bridge between the two.

**The cable path to a real Dreamcast works too, at prototype level.** An
emulated MOTM, through the bridge and a USB-UART adapter plugged into the
console's serial port, completed its upload to a real Dreamcast running a
homebrew stand-in that answers like MF2K
([`dc_link_probe`](homebrew/README.md#dc_link_probe)). The retail game itself
has not been tried on hardware yet. If it behaves as it does in Flycast,
anyone with a Dreamcast and their own copy of MF2K can send it VS Points
from an emulated MOTM, without ever having owned a Neo Geo Pocket Color or
the cable.

```
 RetroArch + patched beetle-ngp          bridge/bridge.py                    Flycast (stock)
 ┌──────────────────────────┐   TCP    ┌──────────────────┐    UDP     ┌──────────────────────┐
 │ NGPC game                │ :42424   │ raw bytes        │  :42500 ←  │ Dreamcast game       │
 │  └ BIOS comms vectors    │ ───────► │      ⇅           │  :37391 →  │  └ SCIF serial port  │
 │     (HLE) → TCP socket   │ ◄─────── │ BattleCable      │ ◄────────► │     → NullModemPipe  │
 └──────────────────────────┘          │ 'D'+byte / 'B'   │            └──────────────────────┘
                                       └──────────────────┘
```

---

## ⚠️ BYOA — Bring Your Own Assets

This repository contains **only code, documentation and byte-level logs**.
It ships no game ROM, no disc image, no BIOS, no save file, no emulator
binary and no NGPC SDK.

To reproduce the retail result you need your **own, legally obtained**
dumps of both games, plus your own emulator setup. The homebrew demos need
no game at all.

| What you bring | Used for |
|---|---|
| RetroArch (Windows) | Runs the patched NGPC core |
| Flycast, with whatever BIOS setup you normally use | Dreamcast side, unmodified |
| MSYS2 + mingw64 gcc | Building the patched core |
| Python 3.8+ | The bridge (standard library only; pyserial for a real Dreamcast) |
| *Optional:* cc900 toolchain (`ngpcbins`) + [ngpc-project-template](https://github.com/ameliandev/ngpc-project-template) | Building the NGPC demo ROM |
| *Optional:* a KallistiOS toolchain | Building the Dreamcast demo and probe |
| *Optional, real Dreamcast:* a 3.3 V USB-UART adapter wired to the console's serial port, and a way to boot homebrew on it | The real-hardware test |
| *Optional, retail:* *SNK vs. Capcom: The Match of the Millennium* (World, En/Ja) `.ngc` | NGPC side of the retail test |
| *Optional, retail:* *Capcom vs. SNK: Millennium Fight 2000* (Japan, Rev A) disc image | Dreamcast side of the retail test |

---

## Status

| Ring | What it proves | State |
|---|---|---|
| 1. NGPC loopback | The core's comms hooks carry bytes (in-process ring buffer) | ✅ |
| 2. NGPC ↔ NGPC | Two RetroArch instances linked over TCP | ✅ |
| 3. NGPC ↔ Dreamcast | Homebrew demos on both sides, through the bridge and Flycast's BattleCable | ✅ |
| Retail | MOTM ↔ MF2K upload completes; VS Points arrive; secret characters unlock | ✅ (needs the bridge's frame coalescing, on by default; see [PROTOCOL.md](docs/PROTOCOL.md#motm-reads-a-frame-until-its-buffer-runs-dry)) |
| Retail, second pair | MOTM → *KoF Dream Match 1999* and *KoF R-2* → DM99 uploads complete; R-2 works with the core unchanged | ✅ in emulation (DM99 → R-2 not yet captured; see [PROTOCOL.md](docs/PROTOCOL.md#the-king-of-fighters-dream-match-1999)) |
| Real Dreamcast | Emulated MOTM → bridge → USB-UART adapter → console serial port → homebrew stand-in for MF2K: upload completes, points and checksum arrive, MOTM confirms; clean loopback at 19200, all four cable lines (TX, RX, RTS, CTS) work | ✅ prototype (retail MF2K on hardware not yet tried; see [SETUP.md](docs/SETUP.md#8-real-dreamcast-prototype)) |

**The NGPC is always emulated.** Only the Dreamcast side has run on real
hardware, and only with the homebrew stand-in. The NGPC demo calls the BIOS
entry points directly, which works on beetle-ngp's HLE BIOS and nowhere else
(see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#known-limitations)).

**Windows only, for the NGPC side.** The TCP backend in the core patch uses
Winsock; on other platforms the patched core compiles but falls back to the
in-process loopback. The bridge and Flycast are cross-platform.

The retail protocol is documented byte by byte in
[docs/PROTOCOL.md](docs/PROTOCOL.md). About 90% of it is decoded; what is
still a hypothesis is marked as such.

---

## Quick start

Full instructions are in [docs/SETUP.md](docs/SETUP.md). The short version:

```bash
# 1. Build the patched core (MSYS2 MINGW64 shell)
./emulator/beetle-ngp/build_core.sh          # -> build/mednafen_ngp_libretro.dll
./emulator/beetle-ngp/test/run_link_test.sh  # core link hooks, no RetroArch -> PASS

# 2. Check the bridge without any emulator
python bridge/selftest.py                     # -> PASS
```

```bat
rem 3. Point the launchers at your files
copy launchers\config.example.bat launchers\config.bat
notepad launchers\config.bat
```

Then, in Flycast's `emu.cfg`, section `[network]`:

```ini
BattleCable = yes
server = 127.0.0.1:42500
```

and start, in this order: `launchers\bridge.bat`, Flycast with the Dreamcast
game, then `launchers\motm_client.bat` (retail) or `launchers\demo_client.bat`
(homebrew).

> Turn `BattleCable` back to `no` when you are done. While it is on, Flycast
> sends the serial port of **every** Dreamcast game to the bridge.

---

## Repository layout

| Path | What |
|---|---|
| [`emulator/beetle-ngp/`](emulator/beetle-ngp/) | The core patch (`0001-ngpc-link-cable-backend.patch`), `build_core.sh`, and a test of the link hooks that runs without RetroArch |
| [`bridge/bridge.py`](bridge/bridge.py) | TCP ↔ BattleCable UDP bridge; passes bytes through unchanged, delivering each DC→NGPC frame in one piece; diagnostic modes behind env vars |
| [`bridge/selftest.py`](bridge/selftest.py) | Loopback test of the bridge with fake peers |
| [`launchers/`](launchers/) | Windows `.bat` files for every ring and capture mode |
| [`homebrew/ngpc_hello_link/`](homebrew/ngpc_hello_link/) | NGPC demo: press A to send `0x42`, counters for TX/RX |
| [`homebrew/dc_hello_link/`](homebrew/dc_hello_link/) | Dreamcast demo: A/B/X send `0x42`/`0xAB`/`0xC5`, counters for TX/RX |
| [`homebrew/dc_link_probe/`](homebrew/dc_link_probe/) | Serial link diagnostics for a real Dreamcast: bytes, errors and RTS/CTS on screen; sniff, echo, or answer like MF2K / DM99 |
| [`tools/frames.py`](tools/frames.py) | Rebuilds the FF-delimited frames from a bridge log |
| [`tools/first_contact.py`](tools/first_contact.py) | Plays MOTM's upload request through the bridge and checks MF2K's answer: the first test of any new setup |
| [`tools/dc_probe.py`](tools/dc_probe.py) | PC side of the probe: serial upload, loopback, RTS/CTS and MOTM-dialogue tests |
| [`tools/re/`](tools/re/) | Probes used to reverse-engineer MF2K: fuzzer, BREAK probe, frame replay |
| [`tools/trace/`](tools/trace/) | MAME debugger and BizHawk Lua scripts that trace the BIOS comms vectors |
| [`captures/`](captures/) | Byte logs of the retail runs and of the experiments that led there |
| [`docs/`](docs/) | [Architecture](docs/ARCHITECTURE.md), [retail protocol](docs/PROTOCOL.md), [setup](docs/SETUP.md), [emulator survey](docs/EMULATOR_SURVEY.md), [development log](docs/DEVLOG.md) |

---

## How it was made

The project was done over nine working sessions in April 2026, as the
research spike of a larger homebrew project. The [development log](docs/DEVLOG.md)
tells the whole story, including the bugs of our own that cost the most
time: a destructive peek in the core, a debug side-channel that corrupted
the retail game's RAM, a bridge "helper" that sent the game its
acknowledgement twice, and frames that reached the game in two pieces.

**Who did what.** Samuele Voltan had the idea, did part of the research
(including the 2000-era GameFAQs guide that described the upload menu),
ran every empirical test on both emulators, played the games to produce the
captures, and made the observation that unlocked the retail protocol: *"the
only way I reach VS mode is with the stock core — why would logging make it
hang?"*. **Claude Opus 4.7** (Anthropic), working in Claude Code, wrote all
of the code (core patch, bridge, demos, probes, trace scripts), read the
emulator sources, did the MAME disassembly work and the analysis of the
captures, and wrote the session logs. The repository was later assembled
from that working tree, cleaned up and documented in English by **Claude
Opus 5.5**, also in Claude Code.

**The real-Dreamcast test (November 2026).** With the MF2K disc image ruled
out (it cannot be made to fit a CD-R without defeating the game's copy
check), Samuele had the idea that unblocked the hardware test: the cable
does not need the retail game, only something on the console that speaks
the Dreamcast side of the protocol. He ran every hardware test, from
coaxing a worn development disc into booting to playing MOTM for the final
upload. **Claude Opus 5.5**, in Claude Code, wrote the bridge's serial mode,
the probe and its PC-side tool, and tested them in Flycast first.

## Credits

- **libretro / beetle-ngp-libretro** and the **Mednafen** NGP core, descended
  from **NeoPop** by neopop_uk: the HLE BIOS whose comms hooks this patch fills in.
- **Flycast**: its BattleCable `NullModemPipe` made the Dreamcast side free.
- **MAME**: the debugger that traced and disassembled MOTM's link code.
- **ameliandev/ngpc-project-template** and **Ivan Mackintosh**'s NGPC framework,
  which the NGPC demo builds against.
- **KallistiOS**, for the Dreamcast demo.
- **Razorclaw**'s *SNK vs. Capcom: Match of the Millennium* guide on GameFAQs,
  for the upload menu and the first-link unlock.

## Licence

MIT for the original code, tools and documentation; see [LICENSE](LICENSE).
The core patch modifies GPL-2.0 code and is distributed under GPL-2.0, like
beetle-ngp itself. The games, the BIOSes and the emulators are not covered.
