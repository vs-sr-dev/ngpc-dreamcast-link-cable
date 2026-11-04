# beetle-ngp link-cable patch

`0001-ngpc-link-cable-backend.patch` applies to
[libretro/beetle-ngp-libretro](https://github.com/libretro/beetle-ngp-libretro)
at commit `0c81ce8` ("libretro: add webOS to CI (#117)"). It touches two files:

- `mednafen/ngp/system.c`: implements the `system_comms_read/poll/write`
  hooks that the HLE BIOS calls (loopback, TCP server, TCP client, null),
  the optional homebrew RAM side-channel and the optional log;
- `Makefile`: links `ws2_32` on Windows.

`build_core.sh` clones, checks out, applies and builds in one go; see
[docs/SETUP.md](../../docs/SETUP.md). The design is in
[docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md#ngpc-side-the-beetle-ngp-patch).

`test/run_link_test.sh` then checks the hooks without RetroArch: a harness
linked against the core's objects talks to a scripted peer that connects
late, drops and returns, and fails if any comms call takes over 100 ms.

## Runtime configuration

| Variable | Values | Default |
|---|---|---|
| `NGPC_LINK_ROLE` | `server`, `client`, `null`; anything else = loopback | loopback |
| `NGPC_LINK_HOST` | peer address for `client` | `127.0.0.1` |
| `NGPC_LINK_PORT` | TCP port | `42424` |
| `NGPC_LINK_MMIO` | `1` = mirror status/byte to RAM `0x6BFC`/`0x6BFD` (homebrew demo only) | off |
| `NGPC_LINK_LOG_DIR` | directory for `ngpc_link_<role>.log` | no log |

Read once, on the first comms call.

## Licence

beetle-ngp is GPL-2.0 (Mednafen, NeoPop). This patch is a modification of
that code and is distributed under the same licence.
