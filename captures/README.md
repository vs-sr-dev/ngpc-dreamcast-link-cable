# Captures

Byte logs written by the bridge and by the patched core during the
sessions in [docs/DEVLOG.md](../docs/DEVLOG.md). They contain only link
traffic, no game data.

Except for the `live_*` logs from November 2026, they predate the cleanup
for publication, so they show the old names (`SR3 bridge starting`, `[SR3 COMMS]`, `SR3_LINK_ROLE`). The format is
otherwise what the current code writes, and `tools/frames.py` reads them.

Two log formats:

- **bridge logs** (`*_bridge.log`, `experiments/mf2k_*.log`): one line per
  byte, `TCP<-NGPC xx -> UDP->Flycast 'D' xx` or `UDP<-Flycast 'D' xx`,
  timestamped from the bridge's start;
- **core logs** (`*_motm.log`, `experiments/comms_*.log`): one line per
  comms call as seen by MOTM: `send`, `recv ->`, `peek ->`, plus a dump of
  MOTM's link RAM on every `0xFF` sent.

## `retail/`

| File | What |
|---|---|
| `deterministic_3runs_bridge.log` | Session 9. Pure passthrough, no diagnostic mode. Three NGPC connections, one *Send to DC* each: 65 points (success), 25 points from an already-linked save (bytes OK, MOTM shows an error; probably a split echo, see [PROTOCOL.md](../docs/PROTOCOL.md#motm-reads-a-frame-until-its-buffer-runs-dry)), 25 points after a full save reset (success). |
| `capture_B_60pts_Karin_bridge.log` | The first full success, with `SYNTH_MF2K_ACK` on. First Send at t≈78 s fails (the NGPC gets two acknowledgements); second Send at t≈800 s succeeds with 60 points. |
| `capture_B_60pts_Karin_motm.log` | The same run from the core's side; the doubled acknowledgement is visible in the `recv ->` lines. |
| `capture_A_25pts_bridge.log`, `capture_A_25pts_motm.log` | The first part of the same run, saved separately at the time. It was later recognised as a prefix of capture B. |
| `live_split_echo_bridge.log`, `live_split_echo_motm.log` | 2026-11-04, first live run after the cleanup, bridge without coalescing, fresh save, 40 points. MF2K gets the points; Flycast splits the data echo after byte 22, MOTM reads 22 of 25 bytes and says "Huh, link broke!". A retry (t≈883 s) fails right after the acknowledgement, because MOTM first reads the 3 leftover bytes. |
| `live_coalesced_success_bridge.log`, `live_coalesced_success_motm.log` | The same setup, MOTM restarted, bridge with frame coalescing. Flycast splits the ack after byte 22 and the echo after byte 19; the bridge delivers each frame whole (`delivered in one write`); full success with the unlock. These logs use the current names. |

## `dm99/`

*The King of Fighters Dream Match 1999* (Dreamcast, Japan) on 2026-11-04,
through the bridge with frame coalescing, in Flycast. These logs use the
current names. See [PROTOCOL.md](../docs/PROTOCOL.md#the-king-of-fighters-dream-match-1999).

| File | What |
|---|---|
| `motm_to_dm99_bridge.log`, `motm_to_dm99_motm.log` | MOTM uploads to DM99: two requests while DM99 was not yet on its DOWNLOAD screen, then the full exchange with the 19-byte data frame (value 100, credited as 3800 NGP points: ×40, capped). |
| `r2_to_dm99_bridge.log`, `r2_to_dm99_r2core.log` | *King of Fighters R-2* uploads from its DC MODE: cable probe `0x91`, the same request and announce as MOTM, a 19-byte data frame with value 1. Later in the bridge log, a 21-byte all-zero exchange from DM99's upload menu opened with no DC points. |

## `experiments/`

The attempts in between, kept for the record. Most were made with
diagnostic bridge modes on, which is visible in the first lines of each log.

| File | What |
|---|---|
| `mf2k_observe.log` | MF2K alone, then the fuzzing, BREAK and frame probes from `tools/re/`, then the replay that got the first answer |
| `mf2k_synth.log`, `mf2k_synth2.log`, `mf2k_2send.log` | Reproduction attempts with the acknowledgement synthesiser. Most Sends deliver two acknowledgements (synthesised + MF2K's); MOTM sends the announce, MF2K answers it, and MOTM stops before the data frame. In the few Sends where MF2K did not answer (not on *Download Stand By*), MOTM got only the synthesised one and also stopped after the announce, since nothing answered it. |
| `mf2k_pure.log` | A passthrough attempt from the same night: MOTM gets **one** acknowledgement and stops even before the announce. **Unexplained.** Whether MOTM was rebooted after the earlier wedged attempts is not recorded; in Session 9 every cold-booted passthrough run succeeded. |
| `mf2k_full.log` | Echo + synthesiser together |
| `mf2k_fullproto.log`, `mf2k_500ms.log` | Data frame injected straight into Flycast after the announce (50 ms and 500 ms delay); MF2K takes the bytes but does not complete |
| `comms_null.log` | MOTM in null mode: what it emits with a dead link |
| `comms_loop.log` | MOTM in loopback |
| `comms_server.log`, `comms_client.log` | Core-side logs from Ring 2 and from a later retail client run |
