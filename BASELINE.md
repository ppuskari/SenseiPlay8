# P0 preserved baseline

Snapshot date: 2026-11-17.

## Hardware known-good (separate a2fpga work)

The enhanced a2fpga card's selector was proven to persist the chosen audio personality across physical power cycling using Flash configuration. **Do not change FPGA/MCU settings in this repo.** Current a2fpga firmware is independently maintained in `ppuskari/a2fpga_core`. A previous session reported firmware checkpoint `b7ea7f6`; confirm the full commit and branch in that repository before making integration changes.

## Standalone SenseiPlay8 P0

- Apple IIe 8-bit player using 6502-compatible instructions; no GS/OS.
- Four channels, one synthetic 64-row MOD, converted into 29-byte/row events.
- Sample bank: 1,024 bytes, uploaded to DOC RAM from 6502 code.
- Source `src/sensei8.s` assembled at $2000; recovered binary: 3,544 bytes.
- P0 code probes DOC identification and native audio personality ($A2) in slot 4.
- Software 6502/DOC bus emulator validates simulated playback and clean return to BASIC.
- **Physical IIe playback not yet established; actual bus mapping must be verified first.**

## Workstream boundaries

No embedded firmware, BL616 build or FPGA bitstreams here. Mockingboard AY FX/piano and SSI263 speech continue in their own tracks. Optional faster CPU (TransWarp IIe), 64KB AUX, 16MB memory are later enhancements, not prerequisites.
