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
