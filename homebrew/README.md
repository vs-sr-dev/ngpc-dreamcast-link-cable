# Demos

Two minimal programs that exchange single bytes over the link, one per
console. They need no game data. Build instructions are in
[docs/SETUP.md](../docs/SETUP.md#5-build-the-demos-optional).

## `ngpc_hello_link/`

- Press **A**: sends `0x42` (`VECT_COMCREATEDATA`).
- Every frame: one `VECT_COMGETDATA`.
- Screen (labels do not render, only the numbers): TX count, RX count,
  last byte received, status (`01` = nothing received this frame).

Our files are `main.c`, `core/rom/comms.c/.h`, the `Makefile` and the two
scripts. The rest (`library.c`, `ngpc.h`, `system.lib`, …) comes from
[ngpc-project-template](https://github.com/ameliandev/ngpc-project-template)
through `fetch_sdk.sh`; it is not redistributed here.

**Emulator only, patched core only.** `comms.c` calls the HLE entry points
`0xFF2C86`/`0xFF2CB4` directly, and `main.c` reads the RAM side-channel
that only the patched core writes (launch with `NGPC_LINK_MMIO=1`, as the
`demo_*.bat` launchers do).

## `dc_hello_link/`

- **A / B / X**: send `0x42` / `0xAB` / `0xC5`. **Start**: exit.
- Every frame: drains the SCIF receive buffer (polled, no interrupts).
- Screen: TX count, RX count, last byte received.

Pure KallistiOS. Runs in Flycast as an `.elf`.

## `dc_link_probe/`

Serial link diagnostics for a **real** Dreamcast, so that the cable can be
tested without a retail Dreamcast game. The screen shows the received bytes,
error counters (framing errors mean a wrong baud rate), and the CTS and RTS
lines. SCIF at 19200 8N1, as set by the NGPC BIOS.

- **A**: cycles the mode: `SNIFF` (listen only), `ECHO` (sends every byte
  back), `FAKE MF2K` / `FAKE DM99` (answers MOTM's upload like those games,
  using the frames in `captures/`, and decodes the points and checksum).
- **X**: clear. **Y**: send a test line. **D-pad up**: hardware flow
  control (MCE) on/off. **D-pad down**: the Dreamcast's RTS
  default/asserted/released.

`build.sh` (same options as `dc_hello_link`) produces `dc_link_probe.elf`
for Flycast and `dc_link_probe.bin` + `.bin.span` for a serial loader. The
PC side is [`tools/dc_probe.py`](../tools/README.md#dc_probepy). Add
`-DPROBE_START_MODE=MODE_MF2K` (or `MODE_ECHO`) to start in another mode in
Flycast, where no one presses the buttons.
