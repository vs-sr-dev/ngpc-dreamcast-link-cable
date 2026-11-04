# Architecture

Three pieces, joined by two sockets:

```
 NGPC game ──BIOS vectors──► beetle-ngp HLE ──system_comms_*()──► TCP client ─┐
                                                                               │ :42424
                                                     bridge/bridge.py ◄────────┘
                                                            │  UDP 'D'+byte → :37391
                                                            │  UDP 'D'+byte ← :42500
 Dreamcast game ──SCIF──► Flycast NullModemPipe ◄───────────┘
```

| Port | Protocol | Who binds | Who sends to it |
|---|---|---|---|
| 42424 | TCP | bridge (listen) | patched beetle-ngp (`NGPC_LINK_ROLE=client`) |
| 42500 | UDP | bridge | Flycast (`server = 127.0.0.1:42500`) |
| 37391 | UDP | Flycast (`LocalPort`, default) | bridge |

The design was validated in three concentric rings, each one green before
the next was added. Every ring is still reproducible with the launchers.

## NGPC side: the beetle-ngp patch

### Why the BIOS layer is enough

No emulator models the NGPC's serial hardware (the TMP95C061 UART inside
the TLCS-900H); see [EMULATOR_SURVEY.md](EMULATOR_SURVEY.md). Building one
was not needed. The NGPC BIOS exposes the link through a set of system
calls, and a MAME trace of the retail game showed that *Match of the
Millennium* uses **only** those calls; its only direct register writes are
two setup writes to `SC0CR`. The serial registers themselves are touched by
the BIOS code, which an HLE BIOS never runs.

beetle-ngp (the libretro version of Mednafen's NGP core, itself descended
from NeoPop) has an HLE BIOS. Its `biosHLE.c` already routes the comms
vectors to three frontend hooks, which upstream leaves as stubs:

```c
bool system_comms_read(uint8_t* buffer) { return 0; }
bool system_comms_poll(uint8_t* buffer) { return 0; }
void system_comms_write(uint8_t data) { }
```

| Vector | Address | HLE behaviour | Hook |
|---|---|---|---|
| `VECT_COMCREATEDATA` (0x13) | `0xFF2C86` | send the byte in register B | `system_comms_write(B)`, then raises the TX interrupt |
| `VECT_COMGETDATA` (0x14) | `0xFF2CB4` | read one byte into B, status in W | `system_comms_read(&data)` |
| `VECT_COMRECIVESTATUS` (0x18) | `0xFF2D4E` | how many bytes are waiting | `system_comms_read(NULL)` |
| `VECT_COMSENDSTATUS`, `ONRTS`, `OFFRTS`, … | | handled inside the HLE | none |

The patch ([`emulator/beetle-ngp/`](../emulator/beetle-ngp/)) fills in the
three hooks in `mednafen/ngp/system.c` and links Winsock (`-lws2_32`).

### Backends

Chosen once, on the first comms call, from environment variables (RetroArch
passes its environment to the core DLL, so the launchers just `set` them):

| `NGPC_LINK_ROLE` | Backend | Ring |
|---|---|---|
| unset / anything else | 64-byte in-process ring buffer: every byte written is read back | 1 |
| `server` | listen on `NGPC_LINK_PORT` (default 42424), accept one peer | 2 |
| `client` | connect to `NGPC_LINK_HOST:NGPC_LINK_PORT` (default `127.0.0.1:42424`) | 2, 3 |
| `null` | no backend, the link looks dead exactly as on the stock core, but every call is logged | captures |

All sockets are non-blocking, and no comms call ever waits on the network:
the hooks run several times per emulated frame. The server accepts lazily on
each comms call. The client starts a non-blocking `connect()`, checks it
with a zero-timeout `select()` on later calls, and if the peer is missing
or goes away it retries at most once per second. (A blocking `connect()` to
a closed port takes about 2 s on Windows; the version used during the
sessions did one on every call while the bridge was down, and froze
RetroArch.) A peer closing the connection shows up as `WSAECONNRESET`
(10054) in the log; that is expected.

Other variables:

| Variable | Effect |
|---|---|
| `NGPC_LINK_LOG_DIR` | if set, every comms call is logged to `<dir>/ngpc_link_<role>.log`, unbuffered (RetroArch swallows a core's stderr on Windows) |
| `NGPC_LINK_MMIO=1` | enables the homebrew side-channel below. **Never for retail games.** |

When logging is on, each `0xFF` sent also dumps a handful of MOTM RAM cells
(`4DA5`, `4DA7`, `4DA9`, `4D62`, `4D3E`, `4013`, `400F`): the state of its
link state machine, see [PROTOCOL.md](PROTOCOL.md#the-motm-side-in-ram).

### The read hook must not consume on a status query

`system_comms_read(NULL)` is the HLE's implementation of "how many bytes are
waiting?". It must **peek**, not read. The first version of the TCP backend
called `recv()` in both cases, so every status query swallowed a byte and
the following `VECT_COMGETDATA` found nothing: MOTM polled forever. The
homebrew demo never calls the status vector, so the bug only showed up with
the retail game. The fix is one flag:

```c
int flags = buffer ? 0 : MSG_PEEK;
int n = recv(link_peer_sock, (char*)&b, 1, flags);
```

The general rule: whenever an HLE function has a "count only" form (a NULL
buffer), the transport behind it needs a real peek.

### The homebrew side-channel (`NGPC_LINK_MMIO`)

The HLE returns the received byte in register B and the status in W, in
register bank 3. Reading W back from C turned out to be the hard part with
the period toolchain: ASM900 (the assembler behind cc900) rejects the
bank-explicit names (`RW3`) in a memory `LD`, and `LD (mem),W` assembles to
something that always stored 0.

The workaround: with `NGPC_LINK_MMIO=1`, the patched read hook also writes
the status to RAM `0x6BFC` (1 = empty, 0 = byte received) and the byte to
`0x6BFD`, at the top of work RAM. The demo ROM reads those two addresses.

That RAM belongs to the game. MOTM keeps live state there, and writing it on
every comms call corrupted the game: it hung or reset in the VS menu, but
only on our core. That is why the side-channel is off by default and why
the retail launchers set `NGPC_LINK_MMIO=0`.

## The bridge

[`bridge/bridge.py`](../bridge/bridge.py), Python standard library only,
one `selectors` loop.

| From | To | Translation |
|---|---|---|
| NGPC (TCP byte) | Flycast | `sendto(b"D" + byte)` |
| Flycast `'D'` + byte | NGPC | one TCP byte |
| Flycast `'B'` (break) | — | logged and dropped; the NGPC has no break |

**Frame coalescing (on by default).** DC→NGPC bytes from an opening `0xFF`
to the closing `0xFF` are held and written to the NGPC in one piece; bytes
outside a frame go through at once. Flycast delivers the serial port one
emulated frame at a time, so a frame can otherwise reach the NGPC split
across ~16 ms, and MOTM stops reading when its buffer runs dry mid-frame
([PROTOCOL.md](PROTOCOL.md#motm-reads-a-frame-until-its-buffer-runs-dry)).
A frame that never closes is delivered after 250 ms
(`BRIDGE_COALESCE_TIMEOUT_MS`); `BRIDGE_COALESCE_FRAMES=0` turns it off.

Apart from that one buffer, the bridge is stateless. It accepts one NGPC peer at a time and rejects a
second one. With no NGPC attached, bytes from Flycast are logged as dropped:
the first ones are usually the KallistiOS boot banner (`0D 0A 2D …`), because
KOS's debug output also goes to the serial port.

Every diagnostic mode (`BRIDGE_ECHO_*`, `BRIDGE_POST_INJECT`,
`BRIDGE_SYNTH_*`) was written to probe the retail protocol one side at a
time. **For a live retail link, leave them all unset** (coalescing is not one of them: keep it on). In particular
`BRIDGE_SYNTH_MF2K_ACK` answers the NGPC's upload request on the
Dreamcast's behalf *while the request is still forwarded to the Dreamcast*,
so the NGPC receives two acknowledgements and stops; see
[DEVLOG.md](DEVLOG.md#session-9--the-bridge-was-the-bug-75-minutes).

## Dreamcast side: Flycast, unmodified

Flycast implements the Dreamcast serial port (SCIF) and, with the
`BattleCable` option, connects it to a `NullModemPipe`
(`core/network/null_modem.h`) that carries it over UDP:

- one UDP socket, bound to `LocalPort` (default 37391, `NaomiNetwork::SERVER_PORT`);
- data is sent as 2-byte datagrams `'D', byte`; a break as the 1-byte datagram `'B'`;
- no handshake, no checksum, no sequencing;
- with `server = host:port` the peer is fixed; with `server` empty, Flycast
  broadcasts to `255.255.255.255:37391` and locks onto the first sender.

`emu.cfg`, section `[network]`:

```ini
BattleCable = yes
server = 127.0.0.1:42500
LocalPort = 37391
ActAsServer = no
```

The cfg key is literally `server` (`NetworkServer` is only the name of the
C++ option variable, `core/cfg/option.cpp`). The option is checked in
`net_handshake.cpp`: `BattleCableEnable && !isNaomi()`. It applies to every
Dreamcast title, not just the one you are testing, and takes over the SCIF
for all of them. Switch it off afterwards.

## The demos

| | NGPC ([`homebrew/ngpc_hello_link`](../homebrew/ngpc_hello_link/)) | Dreamcast ([`homebrew/dc_hello_link`](../homebrew/dc_hello_link/)) |
|---|---|---|
| Send | A → `0x42` | A / B / X → `0x42` / `0xAB` / `0xC5` |
| Receive | polls `VECT_COMGETDATA` every frame | drains `scif_read()` every frame (polled, no IRQ) |
| Screen | four hex numbers: TX count, RX count, last byte, status | TX count, RX count, last byte |
| Toolchain | cc900 (Toshiba), Ivan Mackintosh's framework | KallistiOS |

The NGPC demo's text labels do not render (only `PrintHex` output shows),
so its screen is four bare numbers, top to bottom: TX count (row 8), RX
count (row 9), last byte (row 11), status (row 12, `01` = nothing this
frame).

## Known limitations

- **HLE only.** The NGPC demo calls the HLE entry points `0xFF2C86` and
  `0xFF2CB4` directly and relies on the RAM side-channel. On a real BIOS
  (MAME, real hardware) it would have to go through the system-call
  dispatcher and read the status from W. MOTM shows how a retail game does
  it: `ld RW3, <vector>`, `call` its dispatcher, then `ld WA, RWA3`.
- **Windows only** for the TCP backend; elsewhere the core falls back to
  the loopback.
- **Environment variables, not core options.** Fine for research; an
  upstreamable version would expose role, host and port as libretro core
  options.
- **One NGPC peer** per bridge.
- Byte-at-a-time transport with no timing model. The retail games did not
  need one: the real cable's baud rate is not emulated, and MOTM and MF2K
  completed their exchange anyway.
