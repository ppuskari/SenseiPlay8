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

## Later / optional hardware tiers

- Dynamic DOC RAM allocation and up to 128KB Enhanced DOC sample RAM if the hardware protocol supports it.
- Faster song loading and PCM instruments; independent FX and noise bank.
- TransWarp IIe 65C816 accelerated edition, AUX 64KB and 16MB RAMWorks/RAMFactor memory profiles.
- Keep features separated from Mockingboard replacement and SSI263 speech projects.
