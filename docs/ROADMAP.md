# SenseiPlay8 roadmap

## P0 — recovered, software-verified (current)

- Preserve 6502 assembly, MOD converter, synthetic MOD generator, standalone assembler and bus simulation.
- Rebuild P0 under Python 3 and reproduce original synthetic demo and binary from recovery patch.
- Keep the verified audio-personality Flash behavior in a2fpga untouched.

## P0-HW — next milestone (required)

1. Confirm the DOC register probe and RAM access against the **actual** enhanced-card RTL/MCU checkout.
2. Boot Apple IIe into DOS 3.3, stage raw P0 binary at $2000, CALL 8192.
3. Record four simultaneous distinct synthetic instruments from HDMI.
4. Check for missing notes, clipping, timing drift, keyboard stop and clean return to BASIC.
5. Add readback/debug counters before changing tone, volume or buffering.

## P1 — real tracker player

- Support longer songs / multiple patterns and order navigation, not just static baked row sequence.
- Implement ProTracker tick-level effects: arpeggio, slides, vibrato, portamento, retrigger, volume ramp, pattern break.
- Improve instrument repeat/loop semantics, sample pitch mapping and 8-bit MIDI-style event scheduling.
- Optional ProDOS 8 loader relocated out of BASIC.SYSTEM memory; disk browser and player UI.

## P2 — ProDOS 8 80-column remote MOD jukebox (NEW, independent workstream)

- Build `SENSEI8.SYSTEM` (ProDOS SYS $FF, entry $2000) for both
  Apple IIe 128K and Apple IIgs; ordinary 80×24 text screen.
- Keep the J2R11 hardware-tested BL616 HxCMOD audio pipeline, PCM512
  transport and 2KiB sample LRU windows completely unchanged.
- First validate the existing ROMless M1 physical Apple slot-3
  `$C0B0–$C0BF` signature on both Apple machines.
- Then implement basic M1 commands and a navigable 80-column UI shell
  in this repository. Full FAT SD/USB browsing requires a separate
  bidirectional M2 mailbox extension in `a2fpga_core`.
- [P2 detailed wire protocol, UI mock, compatibility constraints and
  hardware acceptance plan](P2_80COL_REMOTE_JUKEBOX.md).
- This UI is **not** a conversion of the Apple-side native DOC/S8M0
  playback engine; it operates as a remote controller for the MCU player.

## Later / optional hardware tiers

- Dynamic DOC RAM allocation and up to 128KB Enhanced DOC sample RAM if the hardware protocol supports it.
- Faster song loading and PCM instruments; independent FX and noise bank.
- TransWarp IIe 65C816 accelerated edition, AUX 64KB and 16MB RAMWorks/RAMFactor memory profiles.
- Keep features separated from Mockingboard replacement and SSI263 speech projects.
