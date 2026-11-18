# P0L4: four-second isolated stereo routing diagnostic

This is the **original, hardware-audible P0 four-channel demonstration**
followed by a 0.3-second gap and a four-second isolated oscillator test.
It does **not** change firmware, mixer panning, or the original P0 song.

## Timeline

| Approx. time | Audio |
|---|---|
| 0–7.68 s | Original P0 four-channel demo, unmodified |
| 7.68–7.98 s | All 32 DOC voices halted, intentional silence |
| 7.98–11.98 s | DOC oscillator **1 only**, triangle sample at wave-table page $01, FC=$0800 (~411 Hz), volume $70, control $10 |
| After marker | Zero volume, halt, and ProDOS MLI QUIT |

P0L4 drives the stereo-select bit **4 = 1** on oscillator 1. The P0
converter also uses bit4=1 for channels 1 and 2, which were expected to
be on the left in the initial test. The actual HDMI left/right orientation
is the **measurement under test**, not an assumption.

If the final tone is solely in the physical right channel, compare the
DOC mixer bit4 routing with HDMI assignment and your splitter/DAW channel
labels before changing HDL. If it appears in both channels, check for
mono mixing in the capture chain. The original 7.68-second notes are
unchanged to preserve a directly comparable P0 baseline.

The Apple IIe slot interface itself cannot spontaneously swap audio
outputs: both left/right values eventually come from the Enhanced
`sound_glu` mixer and reach the HDMI audio serializer. A swap must
arise in mixer semantics, wiring/serialization, or the capture chain.
This diagnostic differentiates those possibilities from note-level
differences.

## Regenerating the native ProDOS SYS

One command per line, PowerShell **5.1**:

```powershell
cd C:\AppleIIgsDev_02\SenseiPlay8
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
py -3 tools/make_p0l4_sys.py
```

Use `dist/SENSEI8-P0L4.SYSTEM` as ProDOS file **SENSEI8.SYSTEM**, file
type `SYS` ($FF) with aux/load address `$2000` on your own ProDOS 2.4.3
disk. The original P0 raw BIN is not ProDOS-safe without a wrapper.

For convenience, the accompanying project conversation supplies a
*separate* ProDOS 2.4.3 boot image with the P0L4 SYS installed and its
original boot files preserved. The ProDOS OS image itself is **not
committed to this source repository**.

This is a hardware diagnostic, not a full MOD playback feature release.
Test the isolation recording and Bitsy Bye return on the physical IIe.
