# Emulator survey (April 2026)

Before writing anything, we checked which emulators model the NGPC link
port, and where one end could be added most cheaply. The source references
are to the trees as they were in April 2026.

**Summary:** no NGPC emulator emulated the link. On the Dreamcast side,
Flycast already exposed the serial port over UDP. The cheapest NGPC route
was an emulator with an HLE BIOS, since the retail game turned out to use
only the BIOS comms calls.

## Dreamcast: Flycast, ready as is

- `core/network/null_modem.h`: `NullModemPipe`, attached to the SCIF
  (`core/hw/sh4/modules/serial.cpp`) with `setPipe()`.
- UDP, `'D'`+byte for data, `'B'` for break; no handshake, no checksum.
- Config keys `[network] BattleCable`, `server`, `LocalPort`
  (`core/cfg/option.cpp`); default port 37391 (`NaomiNetwork::SERVER_PORT`).
- Activated for any non-Naomi game (`net_handshake.cpp`).
- Also has a `PTYPipe` for debug serial output; not used here.

## NGPC candidates, cheapest first

| Emulator | What exists | Work needed |
|---|---|---|
| **NeoPop lineage** (OpenEmu NeoPop-Core, **beetle-ngp**) | HLE BIOS routes the comms vectors to `system_comms_read/poll/write` frontend hooks, left as stubs | Fill the hooks. **Chosen**, in its libretro form (beetle-ngp), so that RetroArch could host it. |
| **MAME** | NGPC driver on the TMP95C061; its UART is stubbed (`tmp95c061.cpp`: "Fake finish sending data") | Transplant the real UART of `tmp94c241_serial.cpp` (same TLCS-900 family) and add rx/tx callbacks. Register-level, runs the real BIOS. |
| **RACE** (libretro) | No serial MMIO handling; runs the real BIOS; INTRX/INTTX vectors never raised | Write a UART from scratch in a monolithic CPU core |
| **ares** | `ngp/cpu/serial.cpp` is a 5-line buffer; SC0/SC1 registers decoded but never acted on | Write the UART; the architecture is clean (a "Link Cable" port node would fit) |
| **BizHawk / Mednafen** | Mednafen's NGP core has no UART at all | Mednafen patch + Waterbox export + C# wrapper with a socket |

## Why the HLE route is enough for MOTM

Register-level emulation is only required if a game drives the UART
itself. A MAME trace of *The Match of the Millennium* (breakpoints on the
BIOS comms vectors, watchpoints on `SC0BUF`/`SC0CR`/`SC0MOD`/`BR0CR` and
their channel-1 twins) showed:

- calls to `VECT_COMCREATEDATA`, `VECT_COMSENDSTATUS`, `VECT_COMONRTS`,
  `VECT_COMOFFRTS`, `VECT_COMGETDATA` (and, traced later, `COMINIT`,
  `COMSENDSTART`, `COMRECIVESTART`);
- serial register writes only from BIOS code, plus two setup writes
  `SC0CR ← 0x09` / `0x0A` from the cartridge.

The scripts are in [`tools/trace/`](../tools/trace/). Other retail link
games have not been traced; one that drives the UART directly would need
the MAME route.

A MAME implementation would be the more faithful one, since it runs the
real BIOS and could later be checked against real hardware. It is the
natural next step if this is ever taken further.
