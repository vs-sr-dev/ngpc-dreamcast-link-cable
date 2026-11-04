# Setup

Everything here was done on Windows 11. Tested with: beetle-ngp-libretro
at `0c81ce8` plus the patch, a mid-2023 Windows build of RetroArch, Flycast
`v2.6-160-gad03e10c1`, Python 3.14, MSYS2 with mingw64 gcc.

## 1. Build the patched NGPC core

In an **MSYS2 MINGW64** shell, from the repository root:

```bash
pacman -S --needed git make mingw-w64-x86_64-gcc
./emulator/beetle-ngp/build_core.sh
```

The script clones `libretro/beetle-ngp-libretro` into `build/`, checks out
`0c81ce8`, applies `emulator/beetle-ngp/0001-ngpc-link-cable-backend.patch`
and builds `build/mednafen_ngp_libretro.dll` (about 1.1 MB).

Then check the link hooks without RetroArch or any ROM:

```bash
./emulator/beetle-ngp/test/run_link_test.sh
```

It links a small harness against the core's objects, plays a TCP peer that
shows up late, disappears and comes back, and checks the bytes and that no
comms call blocks. Expected output ends with `PASS`.

By hand, the same thing:

```bash
git clone https://github.com/libretro/beetle-ngp-libretro.git
cd beetle-ngp-libretro
git checkout 0c81ce8
git apply ../emulator/beetle-ngp/0001-ngpc-link-cable-backend.patch
make platform=win
```

> **TMPDIR trap.** If gcc fails with *Cannot create temporary file in
> C:\WINDOWS\\*, MSYS2's bash has dropped `TMPDIR` for the recipes. Pass it
> back through the shell make uses:
> `make platform=win SHELL="/usr/bin/env TMPDIR=$(cygpath -m $PWD/.tmp) /usr/bin/bash"`
> (create `.tmp` first). `build_core.sh` does this for you.

## 2. Check the bridge

```bash
python bridge/selftest.py
```

It starts the bridge on spare ports, plays a fake Flycast and a fake NGPC,
and checks that bytes cross in both directions and that a BREAK is dropped.
Expected output ends with `PASS`.

## 3. Configure the launchers

```bat
copy launchers\config.example.bat launchers\config.bat
```

Edit `launchers\config.bat` (git-ignored):

| Variable | Set to |
|---|---|
| `RETROARCH` | your `retroarch.exe` |
| `NGPC_CORE` | defaults to `build\mednafen_ngp_libretro.dll` |
| `NGPC_DEMO_ROM` | defaults to the demo built in step 5 |
| `MOTM_ROM` | your own MOTM `.ngc` (retail test only) |
| `LINK_LOGS` | log directory, default `logs\`; empty disables logging |

**RetroArch:** set `pause_nonactive = "false"` in `retroarch.cfg` (in the
menu, the *User Interface* option that pauses content when the window is
not active). Otherwise the NGPC pauses whenever Flycast has the focus, and
the link stalls.

## 4. Configure Flycast

In `emu.cfg`, section `[network]`:

```ini
BattleCable = yes
server = 127.0.0.1:42500
```

Leave `LocalPort = 37391` and `ActAsServer = no` at their defaults.
**Set `BattleCable = no` again when you are done**: while it is on, every
Dreamcast game's serial port goes to UDP.

## 5. Build the demos (optional)

### NGPC: `homebrew/ngpc_hello_link`

You need the Toshiba cc900 toolchain (`ngpcbins`) and the files of
[ngpc-project-template](https://github.com/ameliandev/ngpc-project-template),
which are not redistributed here. The template's
`install/ngpcbins_x86_x64.zip` contains the toolchain.

In MSYS2 bash:

```bash
git clone https://github.com/ameliandev/ngpc-project-template ../ngpc-project-template
# unzip ../ngpc-project-template/install/ngpcbins_x86_x64.zip somewhere, e.g. C:\ngpcbins
cd homebrew/ngpc_hello_link
./fetch_sdk.sh ../../../ngpc-project-template
export THOME=/c/ngpcbins/T900       # MSYS2 path style, not C:/
./build.sh                           # -> bin/main.ngp
```

`THOME` must use the `/c/...` form: with `C:/...` the toolchain cannot find
its own compiler passes through `PATH`.

### Dreamcast: `homebrew/dc_hello_link`

Any KallistiOS toolchain:

```bash
source /opt/toolchains/dc/kos/environ.sh && ./homebrew/dc_hello_link/build.sh
# or, with a Docker image that has KOS in /opt/toolchains/dc/kos:
KOS_DOCKER_IMAGE=<image> ./homebrew/dc_hello_link/build.sh
```

The result, `hello_link_dc.elf`, runs directly in Flycast.

## 6. Run the rings

| Ring | Start, in order |
|---|---|
| 1. Loopback | `launchers\demo_loopback.bat`. Press A: TX and RX both go up, last byte `42`. |
| 2. NGPC ↔ NGPC | `launchers\demo_server.bat`, then `launchers\demo_client.bat`. A on either side counts on the other. |
| 3. NGPC ↔ DC | `launchers\bridge.bat`; Flycast with `hello_link_dc.elf`; `launchers\demo_client.bat`. A on the NGPC shows `0x42` on the Dreamcast; A/B/X on the Dreamcast count on the NGPC. |

## 7. Retail test (BYOA)

1. To see the unlock, move MOTM's save out of the way if it has already uploaded once
   (beetle-ngp keeps it as `<rom name>.flash` in RetroArch's saves folder);
   see
   [PROTOCOL.md](PROTOCOL.md#a-second-upload-from-the-same-save).
2. `launchers\bridge.bat`, with no `BRIDGE_*` variables set.
3. Flycast, freshly started, with MF2K. Secret Mode → **Download Stand By**.
4. `launchers\motm_client.bat`. Earn some VS Points, go to the VS menu,
   **Send to DC**, press A.

Expected: MF2K shows データの受信を完了しました and the points; Karin says
*"It's over. The data's been safely uploaded."*; the eight secret
characters are unlocked on MOTM's character select. `logs\bridge.log` holds
the exchange; `python tools/frames.py logs\bridge.log` prints the six frames.

## Capture modes

| Launcher | Use |
|---|---|
| `motm_loopback.bat` | MOTM with no peer; its own bytes come back. Logs what it emits. |
| `motm_null.bat` | MOTM with a dead link, as on the stock core, every call logged. |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| MOTM hangs or resets in the VS menu, only on the patched core | `NGPC_LINK_MMIO=1` with a retail game |
| MOTM sends the announce frame and then nothing | the NGPC got two acknowledgements: a `BRIDGE_SYNTH_*` mode is on |
| Karin: *"Huh, link broke!"*; MF2K got the points anyway | a frame from MF2K reached MOTM in two pieces: check that the bridge log says `frame coalescing ON`; restart MOTM before retrying |
| MOTM fails at once on a retry, right after MF2K's acknowledgement | leftover bytes from the previous failed attempt: restart MOTM |
| No log file appears | `LINK_LOGS` empty, or RetroArch loaded a different core (check `-L`) |
| Bridge logs `no NGPC peer, byte dropped` at Flycast start | normal: KallistiOS boot banner on the serial port |
| `err=10054` in the core log | normal: the other end closed |
| Link stalls when switching windows | RetroArch `pause_nonactive` |
| Some other Dreamcast game misbehaves later | `BattleCable` left on |
