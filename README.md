# SenseiPlay8 — Apple IIe 8-bit MOD player

**P0 status: software proof-of-playback; real Apple IIe audio validation pending.**

An independent, 8-bit 6502/65C02-compatible four-channel ProTracker MOD player targeting the **a2fpga Enhanced native Ensoniq DOC** sound personality. This is a **new 8-bit implementation**, not a direct reassembly of the Apple IIgs SenseiPlay source, and does not need IIgs tools or a 65C816.

## Build and software test (Python 3)

Run from the repository root (Windows PowerShell commands):

```powershell
py -3 tools/make_demo_mod.py
py -3 tools/mod_to_s8m.py assets/sensei8-original-demo.mod
py -3 tools/s8asm.py src/sensei8.s --out build/SENSEI8.BIN
py -3 tests/test_player.py
```

To restore the **exact original recovered P0 binary and synthetic MOD** from the archived patch, also run:

```powershell
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
```

The import tool verifies the recovered source matches this repository, then creates `assets/sensei8-original-demo.mod` and `dist/SENSEI8-P0.BIN` from the original Git binary patch. `build/` is ignored because generated binaries are rebuilt locally.

## Hardware P0 — not yet confirmed

Requires physical Apple IIe, a2fpga Enhanced card in the slot-4 personality, native DOC mode `$A2`, and the DOC register contract described in [docs/DOC_INTERFACE.md](docs/DOC_INTERFACE.md).

Under **DOS 3.3**, stage the binary as a DOS binary file, `BLOAD` it at **$2000**, and `CALL 8192`; press any key to stop. **Do not use ProDOS 8 BASIC.SYSTEM** for this P0, because it overlaps $2000. Never assume this software test proves the current FPGA firmware I/O mapping; readback should be checked first.

## Scope / features

- Four MOD channels to DOC oscillators 0–3; no AUX RAM, TransWarp, 65816, or IIgs toolbox required for P0.
- Original synthetic 4-instrument demo (sine, triangle, pulse, bell), 64 rows, 1,024 bytes of DOC sample RAM, 29 bytes per converted row.
- Preliminary note retriggers, Cxx row volume, Fxx speed/tempo support. **Other tracker effects, pattern navigation and streaming files are not implemented yet.**
- 6502 software simulator exercises 64 rows, sample writes and return-to-BASIC; **hardware audio is unverified**.
- Later optional TransWarp IIe 65C816, AUX 64K and 16MB RAMWorks/RAMFactor-style memory support.
- Keep this application standalone; do not merge unrelated Mockingboard FX, piano or SSI263 work into it.

See [BASELINE.md](BASELINE.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## Credits / provenance

Inspired by [SenseiPlay for Apple IIgs](https://github.com/digarok/senseiplay) (digarok / Dagen Brock), whose playback architecture uses Jesse Blue's NinjaTrackerPlus. Neither the original SenseiPlay source nor NinjaTrackerPlus source is vendored in this repository. Respect their licensing and attributions. The bundled demonstration audio is generated here rather than copied from third-party MOD files.

Copyright (c) 2026 Petar Puskarich / contributors. **No license granted merely by publishing the code; choose a license explicitly before external redistribution or contributions.**
