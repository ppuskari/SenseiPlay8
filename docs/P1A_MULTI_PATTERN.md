# P1A — multi-pattern precompiled MOD player

P1A is the **first expanded music build** after the hardware-proven P0P8.
The original P0/P0L4/P0P8 binaries are unchanged and remain our reference.

## What's new

- 31-instrument, four-channel standard ProTracker MOD input (`M.K.` etc.)
- **Multiple order entries and patterns**, converted on the development PC
- Up to the remaining `$2000–$8FFF` main RAM capacity; actual maximum
  varies with note rows and packed instrument samples
- Four simultaneous DOC voices, same 6502-safe sequencing engine and
  native audio personality `$A2`, Slot 4
- Relocates the inline sample-bank pointer as the row table grows
- Native ProDOS SYS loader/QUIT wrapper computed from the new program size
- Reports exact row count, PCM bytes, SYS size and program end address
- Hard-fails unsupported tracker effects by default

## First three-pattern demo

This is an **original** melody, not copied tracker music. Its eight-cycle
sine, triangle, pulse, and bell tables preserve the P0P8 pitch fix. It runs
for approximately **23 seconds** (192 rows) and is designed to fit the
140K ProDOS 2.4.3 disk and stock IIe main RAM.

## Build on Windows PowerShell 5.1

Copy and paste one command at a time:

```powershell
cd C:\AppleIIgsDev_02\SenseiPlay8
git pull --ff-only
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
py -3 tools/make_p1_demo_mod.py
py -3 tools/p1_build.py assets/sensei8-p1-three-pattern.mod --analyze
py -3 tools/p1_build.py assets/sensei8-p1-three-pattern.mod
py -3 tests/test_p1.py
```

Output: `dist/SENSEI8-P1A.SYSTEM` (ProDOS file type `SYS` $FF,
auxiliary/load address $2000). This is **not** a DOS 3.3 BLOAD file.

For a user's local MOD, substitute its path as the converter's first
argument and run `--analyze` before writing. Modules with unsupported
effects are rejected unless `--allow-unsupported` is explicitly passed,
which may sound inaccurate. Do not commit copyrighted module samples.

## What is *not* supported yet

- Native `.NTP` file parsing — those are **not** ProTracker MOD binaries
- True tick-level Amiga effects (slide, vibrato, arpeggio, portamento)
- Pattern flow effects Bxx/Dxx; use preflattend simple MODs first
- Real-time song selection/loading from disk; SYS embeds one converted song
- Large samples requiring >8192-byte individual tables or DOC streaming
- Auxiliary RAM / TransWarp support

**Memory accounting:** each converted row is **29 bytes**, three patterns
consume 5,568 bytes of main RAM. DOC sample-bank data is uploaded on
startup but initially embedded in main RAM to keep the P1A engine minimal.
In P1B we should split that PCM into a separate ProDOS data file and
load/transfer it incrementally, enabling longer songs and more instruments.

NinjaTrackerPlus's original design also uses 256..32768-byte aligned
sample tables and employs streaming for oversized instruments:
https://www.ninjaforce.com/html/products_ninjatrackerplus.php
