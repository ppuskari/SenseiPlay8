# P2 design: A2MEDIA.SYSTEM — Apple IIe/IIgs 80-column MOD jukebox UI

Date: 2026-11-22. **Design only, not a working .SYSTEM deliverable.**
Target: ProDOS 8 on 128KiB Apple IIe and Apple IIgs, ordinary 80×24 text;
Apple II CPU is the front-end, existing a2fpga BL616 HxCMOD engine is the
44.1kHz / stereo / PCM mixer and FAT file owner.

## Source and golden baseline boundaries

- **Do not alter** the hardware-tested a2fpga J2R11 branch
  `petar/mod-j2r11-jukebox-startfile-20261122` or its beta MCU/FPGA
  binaries, and do not rewrite J2R9B golden audio internals.
- Keep all Apple 6502 code, ProDOS build scripts, simulation, and examples in
  `ppuskari/SenseiPlay8`. M2 hardware/firmware interface work
  belongs in separate future a2fpga branches.
- **A2MEDIA.SYSTEM is a new, independent ProDOS 8 application**, not a
  SenseiPlay derivative, port, or rewrite. It coexists with the archived
  SenseiPlay8 native-DOC/S8M0 prototype and controls the MCU over the
  Apple expansion-slot mailbox without touching native-DOC registers.
  The application name is **A2MEDIA.SYSTEM**; the existing SenseiPlay8
  repository currently hosts its design work for convenience only.
- No native Ensoniq, SSI263, Mockingboard, or A3 configuration changes
  are required. Leave the HDMI audio engine independent of Apple /RESET.

## Existing implementation that we can reuse

a2fpga Enhanced J2R11 **source** contains:

1. ROMless Apple **slot-3** media mailbox at **$C0B0–$C0BF**,
   firmware SPI XFER **space 7**. Signature:
   `$C0B0='M', $C0B1='B', $C0B2=1` (decimal `77 66 1`).
   Currently a 256-byte **Apple -> MCU** FIFO, command/ACK/result
   registers and no MCU->Apple data FIFO.
2. M1 control commands: PING $01, REPLAY_LAST $02, STOP $03;
   jukebox folder $04, recursive tree $05, NEXT $06, PREVIOUS $07,
   PLAY_ONCE $08, REPEAT_ONE $09; legacy diagnostic transfer
   BEGIN $10, END $11, ABORT $12. These are the MCU's existing
   stable command IDs, not new P2 commands.
3. BL616 FAT filesystem is single-threaded in the disk task.
   Existing `FSOP_MOD_LIST_OPEN/NEXT/CLOSE` is owned by the jukebox,
   so the new Apple UI **must use its own per-client listing context**
   in the disk thread rather than stealing the jukebox or FTP handles.
4. MCU MOD control can start a selected path, start sorted folder from
   chosen file, next/previous, stop, resume within same session, and
   publish now-playing track position and state.
5. PCM is already streamed directly over FPGA SPI **space 6**.
   All file browsing/control must happen outside the real-time audio
   mixing code, and must not induce full FPGA OSD redraws.

**Important physical proof gate:** The M1 docs say physical slot 3 and
the RTL hard-codes $C0B0; the current Enhanced sound configuration is
often tested in slot 4. Do **not** assume that a board physically in
slot 4 responds at $C0B0. First verify the installed beta board's
**actual** bus decoding on both IIe and IIgs. Hard-wiring new M2 logic
or sending commands to an unverified slot address is unsafe. On the
Apple IIe, slot 3's internal 80-column firmware is mapped in C300 ROM
and slot-3 C0B0 I/O remains electrically available; our mailbox claims
**no** C300 or C800 ROM, so the design should coexist with that
firmware if the bus routing works.

### Non-destructive first test on real Apple

From Applesoft / BASIC.SYSTEM, with the current beta FPGA and MCU:

    PRINT PEEK(49328),PEEK(49329),PEEK(49330)

Expected, only if M1 is physically accessible: **77 66 1**.
Do this on IIe and then on IIgs. Failure means investigate
physical slot, /M2SEL gating, 80-column/slot-3 compatibility and
FPGA bus routing before making an Apple .SYSTEM application.

## Application model

- ProDOS 8 type **SYS ($FF)**, load/entry point **$2000**, binary
  file name `A2MEDIA.SYSTEM`. Require IIe 128KiB or IIgs.
  Keep the application fully 6502-compatible for both, no 65816-only
  opcodes. Follow ProDOS system global page, MLI QUIT, zero-page and
  memory management conventions.
- Use the standard internal **80-column firmware** and 80×24 text.
  Do not claim slot-3 C300 expansion ROM; do not force a peripheral
  ROM into C300 or remap the IIgs built-in slot-3 80-column firmware.
  Use firmware text output for first working UI; consider main/AUX
  direct-video writes later, after a hardware compatibility baseline.
- Poll ordinary keyboard, debounce and process controls at UI speed.
  Do not busy-poll the mailbox during audio critical sections; use
  bounded request timeouts, cooperatively yield to firmware routines,
  and let the BL616/FPGA continue playback autonomously.

### Suggested 80×24 layout

    A2MEDIA / A2FPGA MOD JUKEBOX                 IIe/IIgs  44.1kHz STEREO
    SOURCE: SD (ACTIVE FAT)    FOLDER: /MODS/8CHANNEL
    -----------------------------------------------------------------------
    > 001  3EDGES.MOD                           8CH
      002  A_CLOWN_IN_THE_MOON.MOD               8CH
      003  CHEER.MOD                             8CH
      004  ONE_MINUTE_DEAD_WALTZ.MOD             4CH
      ...
    -----------------------------------------------------------------------
    NOW PLAYING: 003/127 CHEER.MOD             STATUS: PLAYING
    CACHE: 8 x 8 KiB / 2 KiB WINDOWS   UNDERRUNS: 0
    ENTER Play   J Start Jukebox Here   N Next   P Prev   S Stop
    R Resume Last   ESC Parent/Quit            SD/USB is MCU-owned

This is a **wireframe**, not a screenshot or implemented UI. Channel
counts in the browser need an optional header-probe API or may be
omitted in first build.

## Proposed M2 bidirectional mailbox extension (future a2fpga branch)

Preserve M1's existing command IDs, 'MB' signature, native DOC
behavior, SPI space7, and Apple->MCU 256-byte FIFO.

Add one independent **MCU -> Apple reply FIFO** (suggested size
256 bytes) and a *negotiated* protocol version/feature flag. Suggested
minimal v2 changes, subject to RTL bus-timing simulations:

- Apple **read $C0B5** (M1 returns 0) pops one MCU reply byte when
  a v2 response is active. Only advance one byte per actual Apple read
  strobe; never pop twice for a single phi0 cycle. Apple **write
  $C0B5** retains its existing Apple->MCU FIFO push behavior.
- Reserve status bit7 of read **$C0B3** for `REPLY_BYTE_READY`
  **only when M2 capabilities have been negotiated**. Legacy M1 keeps
  status bit7=0. Apple may poll for reply bytes and read $C0B5.
- Keep M1 **$C0B4 command**, $C0BA sequence, $C0BB ACK,
  $C0BC result, and existing free/queued/overflow registers stable.
  Response frames include **request sequence, payload length, type,
  status, and checksum** so the Apple can reject stale/partial data.
- Add MCU SPI7 response-data push and response FIFO reset/flush
  registers to a non-conflicting SPI-side address range, without
  changing existing SPI7 controls. If the reply FIFO fills, use
  bounded waiting/retry outside the MOD render loop.
- Use a feature/handshake command rather than blindly issuing future
  opcodes against legacy M1 firmware.

M2 request types, exact numeric IDs **not yet assigned**:

| Request | Apple reply | Backend |
| --- | --- | --- |
| CAPS / GET_SOURCE | protocol features, mounted SD or USB source | media task |
| LIST_OPEN(path) | list handle and entry count, or error | dedicated disk task view |
| LIST_PAGE(handle,offset) | bounded list of files/dirs with names and flags | dedicated disk task view |
| LIST_CLOSE(handle) | OK | disk task |
| PLAY_FILE(path) | accepted/error | existing MOD selected path |
| JUKE_START_AT(path) | queued/error | J2R11 selected-start path |
| JUKE_START_FOLDER(path,recursive) | queued/error | existing J2R11 scan |
| GET_STATUS | playing, path, position, total, errors, optional PCM stats | now-playing snapshot |
| STOP/NEXT/PREV/RESUME | accepted/error | existing MOD controls |

Directory names are FAT long filenames. Restrict transferred path to
the existing validated MCU MOD path cap (128 bytes including NUL),
and do not allow `..`, absolute paths, drive prefixes, or
backslashes. Reply pages must fit in the negotiated FIFO and can
contain fewer entries if names are long.

### The SD-versus-USB detail

The MCU currently exposes **the active FAT backend**, SD *or* USB
depending on what was mounted. A ProDOS 8 system file cannot enumerate
raw SD FAT directories through ProDOS MLI by merely selecting a slot:
ProDOS is showing mounted ProDOS volumes/disk images, while the MCU
owns FAT. Browser requests must therefore go through the mailbox.

Start with a read-only browser of whichever FAT backend is **active**.
Do not switch/remount the MCU's SD/USB backend while disk images are
mounted or while a MOD is streaming. A future explicit source switch
requires separate storage arbitration / mount safety.

## Incremental implementation gates

1. **Apple physical bus proof (no new firmware):** signature/readback
   and M1 PING on IIe + IIgs, preferably while 80-column text is enabled.
   Validate slot-3 coexistence and the board's actual physical slot.
2. **Apple UI shell (A2MEDIA workstream only):** minimal SYS at $2000,
   80-column display, keyboard navigation, mailbox discovery,
   M1 PING/STOP/NEXT/PREV; compile + emulator regression.
   No new FPGA or MCU binary required for this phase.
3. **M2 return channel (separate a2fpga branch):** FPGA response FIFO
   with simulation for strobe/CDC/overflow; MCU request handler and
   dedicated disk-thread listing context; tests proving no audio
   render-loop changes.
4. **Full browse and playback:** LIST_PAGE, selected MOD path and
   J2R11 start-at-file, live now-playing status and directory history
   displayed on the Apple; keyboard navigation/resume.
5. **Real-hardware parity:** IIe and IIgs, 80-column screen while
   CHEER.MOD loops through the demanding passages; UDR/ERR/E remain
   zero. Record bus/CPU rate and compare to J2R11 gold.
6. **Packaging:** ProDOS SYS filetype $FF, an optional ProDOS disk
   image/bootable media, and tester instructions. Archive the binary
   SHA256, source SHA and both-machine hardware status.

## Validation status

The existing J2R11 MOD player is reported as excellent on real
Apple hardware, but the Apple **M1 slot-3 physical I/O access has not
been independently proved by the MOD audio tests**. The proposed M2
response path and P8 80-column application are unimplemented.
Do not describe the wireframe or M2 as already shipped to beta users.
