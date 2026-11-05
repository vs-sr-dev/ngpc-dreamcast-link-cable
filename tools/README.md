# Tools

## `frames.py`

Rebuilds the `FF`-delimited frames from a bridge log, one line per frame
with its direction and time, and collapses everything else (the `0x92`
probe, the VS sync stream) into byte counts.

```bash
python tools/frames.py captures/retail/deterministic_3runs_bridge.log
```

## `first_contact.py`

Plays MOTM's side of the upload request through the bridge (as if it were
the NGPC core) and reports whether MF2K answers with its 23-byte
acknowledgement. The quickest check of a new setup, Flycast or a real
Dreamcast on the serial port: MF2K on *Download Stand By*, the bridge
running, then

```bash
python tools/first_contact.py            # FIRST CONTACT OK
```

## `dc_probe.py`

PC side of [`homebrew/dc_link_probe`](../homebrew/README.md#dc_link_probe):
tests the serial link to a real Dreamcast without a retail Dreamcast game.

```bash
python tools/dc_probe.py upload        # push the probe through a dev disc's serial loader
python tools/dc_probe.py loop          # probe in ECHO mode: 256 bytes there and back
python tools/dc_probe.py rts           # toggle the adapter's RTS, watch CTS on the probe screen
python tools/dc_probe.py motm          # probe in FAKE MF2K/DM99 mode: MOTM's whole upload dialogue
python tools/dc_probe.py listen        # print what the Dreamcast sends (Y on the pad)
```

`--port` (default `COM7`, or `DC_SERIAL`) picks the serial port; `--bridge
127.0.0.1:42424` runs the tests through the bridge instead, which also
reaches the probe running in Flycast with BattleCable on.

`upload` speaks the protocol of DC-LBA2's `DC_SERLOAD` (115200 baud,
`LBA2LOAD` handshake): start it, then power on the console with that dev
disc. Any other way of booting `dc_link_probe.elf` on hardware works too.

## `re/`: probes used on MF2K

These were written to make *Millennium Fight 2000* talk, one hypothesis at a
time. All but `fuzz_mf2k.py` send UDP straight to Flycast on port 37391,
bypassing the NGPC entirely; run the bridge alongside so that MF2K's
replies land in its log (`BRIDGE_LOG`). MF2K must be on *Download Stand By*.

| Script | What it tries | Outcome |
|---|---|---|
| `fuzz_mf2k.py` | every byte 0x00-0xFF, three times each, through the bridge's TCP port | no reply |
| `probe_break.py` | BREAKs, BREAK + `0x92`, BREAK + common magic pairs | no reply |
| `probe_retail_frame.py` | the 8-byte frame from the first MAME trace, and variants | no reply (the frame was truncated) |
| `replay_motm_upload.py` | MOTM's real 18-byte upload request, captured in loopback | **MF2K answers** with its 23-byte acknowledgement |

## `trace/`: finding out how a game uses the link

| Script | For |
|---|---|
| `trace_comms_mame.cmd` | MAME debugger: logs the BIOS comms vectors and serial register accesses, without stopping |
| `trace_comms_mame_v2.cmd` | MAME debugger: the vectors again, each with the caller's return address (`d@(xssp)`), for following a game's call chain. Use with `-debuglog`. |
| `trace_comms_bizhawk.lua` | the same idea for BizHawk. It did not work with BizHawk's NGPC core at the time (no execute callbacks on BIOS addresses); kept for reference. |

MAME's TLCS-900H debugger syntax, as of 0.287: the stack pointer is `xssp`,
dword reads are `d@(addr)`, and constants in conditions need a `0x` prefix.
