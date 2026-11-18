# P0P8 — pitch-corrected synthetic instrument experiment

**P0L4 is the frozen hardware-proven baseline.** This is a separate P0P8
test, not a change to the FPGA, to the original P0 source, or to the
ProTracker MOD converter.

## Evidence from the physical Apple IIe

The supplied P0L4 WAV capture has a clean 411 Hz marker **only on the left**
and no measurable samples at all on the captured right during that marker.
This verifies the slot-4 interface can address the stereo bit correctly.
Do **not** invert the Enhanced DOC mixer's left/right mapping.

The four-voice P0 song sounded muddy/bassy. Its synthetic test voices are
each only one waveform period, stretched over a 256-byte loop. With the
existing DOC sample-clock and frequency register values, the sounding
fundamentals are approximately 16–65 Hz, despite the note-event converter
using nominal MOD periods.

## P0P8 intervention

- Keep exactly the original **3544-byte P0 engine and sequence**, except
  replace the final 1024 sample bytes (four 256-byte tables).
- For each 256-byte synthesized waveform, select every eighth byte to
  create a 32-byte period, then repeat it 8 times to occupy 256 bytes.
  The existing oscillator frequencies now produce eight times the
  fundamental: roughly 128–520 Hz for the initial four instruments.
- Preserve all 64 rows, stereo controls, envelope/volume and sequencing.
- Preserve the P0L4 four-second isolated channel-1 marker at ~411 Hz by
  setting its FC from $0800 to $0100, compensating the 8x waveform cycles.
- Keep the brief silence between the 7.68-second four-channel demo and
  the isolated left channel marker.
- Program exits with ProDOS MLI QUIT through the preserved P0L4 wrapper.

This changes **synthetic demo instrument definitions only**. Arbitrary MOD
samples have different playback semantics. Do not bake this 8x conversion
into the general `mod_to_s8m.py` converter without analysis of real
instruments and their sample rates.

## Commands (PowerShell 5.1; one command per line)

```powershell
cd C:\AppleIIgsDev_02\SenseiPlay8
git pull --ff-only
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
py -3 tools/make_p0p8_sys.py
```

The result is `dist/SENSEI8-P0P8.SYSTEM`, size 3728 bytes, SHA256
`9ca81bd61a39caa7f1d3feda90a85ff619ae4ef2e756bd69d378303ddde73b23`.
The ProDOS disk image with the SYS installed is distributed separately
from the repository; do not assume a 6502 raw BIN can run under BASIC.SYSTEM.

## What to record

Capture the entire four-channel section and the same left-only 411Hz marker.
Relative note pitch and perceived instrument clarity are under test;
left/right routing is already proven correct by P0L4.

If the instrument section improves, next implement actual four-voice sample
looping, gain/ADSR, and tick-wise tracker effects as a separate P1, rather
than treating P0P8 as a general-purpose MOD player.
