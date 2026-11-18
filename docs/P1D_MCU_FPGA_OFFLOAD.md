# SenseiPlay8 P1D — first offloaded tracker demonstration

The P1B Waltz is the first full real-MOD song verified on the physical
Apple IIe. P1C adds software-side tick effects. Neither release is
replaced by P1D.

P1D demonstrates an **alternate playback architecture** using all three
available processors on an a2fpga Enhanced card:

1. **Apple IIe / 6502:** initializes native DOC, uploads the P0P8
   four-instrument 1,024-byte sample bank once, writes a START command
   to the new native Slot 4 `$C0CA..$C0CF` mailbox, watches playback
   status and keypress, sends STOP, then returns through ProDOS MLI QUIT.
2. **BL616 MCU:** runs a FreeRTOS task which calculates original
   192-row demo note sequences and per-tick arpeggio, vibrato and
   volume effects on a 20-ms ProTracker tick schedule.
3. **FPGA:** provides a 1-ms timestamp clock, 64-slot DOC event FIFO,
   and a single, exclusive DOC host-register writer.

**P1D is a real-time co-processor architecture demonstration, not yet
a native MOD parser or tracker-file player**. We will stage MOD
patterns/PCM into MCU and Enhanced DOC RAM in later versions.

## Required paired hardware branch

a2fpga_core:

`petar/sensei8-p1d-mcu-fpga-20261118`

Base is the hardware-validated `petar/audio-m641-a3-hwvalidated-20261117`
branch, **not** the older a2fpga_core repository default branch.

Code resides in:
- `boards/a2n20v2-Enhanced/hdl/sensei_tracker_bridge.sv`
- `boards/a2n20v2-Enhanced/hdl/bl616/bl616_spi_connector.sv`
- `hdl/sound/sound_glu.sv`
- `boards/a2n20v2-Enhanced/hdl/top.sv`
- `boards/a2n20v2-Enhanced/src/a2n20_bl616/firmware_host/sensei_tracker.c`
- `boards/a2n20v2-Enhanced/docs/SENSEI_P1D_PROTOCOL.md`

The FPGA and MCU binaries must be compiled as a matched pair.
Do not flash an unverified bitstream over the Golden firmware.
The first-stage BL616 flash loader must not be overwritten.

## Building the IIe ProDOS SYS on Windows PowerShell 5.1

Run each line separately, inside your SenseiPlay8 checkout:

```powershell
cd C:\AppleIIgsDev_02\SenseiPlay8
git fetch origin petar/p1d-offload-20261118
git switch --track origin/petar/p1d-offload-20261118
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
py -3 tools/make_p1d_sys.py
py -3 tests/test_p1d.py
```

Output is `dist\SENSEI8-P1D.SYSTEM`, native ProDOS SYS
(file type `$FF`, auxiliary/load address `$2000`).

This executable checks for the **new** FPGA signature at `$C0CA/$C0CB`.
On an old FPGA, the IIe will stop without launching the co-processor
demo. On paired P1D hardware, use Native DOC audio mode A2 and Slot 4.

## Tests and limitations

- Python CI exercises the P0 waveform bytes, the new 6502 mailbox,
  the no-bridge fallback, exit path, and original source hash.
- The separate a2fpga_core CI exercises the FPGA mailbox and timer
  with Icarus Verilog, plus BL616 worker C syntax on a portable stub
  build.
- Full Gowin place-and-route, Bouffalo SDK firmware linking, HDMI
  output, and physical Apple IIe testing are **not verified** by
  these software-only tests.
- P1D currently uses CPU preloading of 1 KiB of sample data.
  Full 128-KB DOC sound-RAM DMA and MCU file-based MOD pattern parsing
  are the next two engineering milestones.

## Safety invariants

- Original Native DOC `$C0C0..$C0C9` unchanged.
- No MCU tracker writes if audio mode isn't Native/Shared.
- Owner arbitration never allows CPU + MCU DOC register writes
  simultaneously.
- Old P1B Waltz / P1C MOD builds are preserved.
- The feature branches are kept separate until paired hardware validation.
