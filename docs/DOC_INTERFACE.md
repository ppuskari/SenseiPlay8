# P0 native DOC register contract (software-side)

**This is what the recovered software expects, not an independently verified promise about the latest FPGA build.** Check the exact a2fpga RTL/MCU branch before running on hardware.

| Address | P0 symbol | Expected behavior |
| --- | --- | --- |
| $C0C0 | DOCCTL | Select register access ($0F) or RAM/autoincrement mode ($6F) |
| $C0C1 | DOCDATA | DOC register or sample RAM write |
| $C0C2 | DOCPTR | Register address / RAM pointer low |
| $C0C3 | DOCPTRHI | RAM pointer high / bank selector (zero in P0) |
| $C0C4..$C0C6 | DOCID0..2 | Signature bytes `D`, `O`, `C` |
| $C0C8 | DOCMODE | `$A2` for native DOC personality |
| $C019 | RDVBL | NTSC 60Hz vertical blank latch used to pace rows |

P0 halts all 32 DOC oscillators, configures 32-voice DOC mode via register $E1=$3E, uploads 1KiB to bank 0, and retriggers 4 voices by writing frequency, wave table pointer, resolution, volume and control registers.

**Preflight:** cold-start with the known-good Flash-persisted Native DOC selection; read $C0C4..$C0C6 and $C0C8; do not flash any new firmware just to run this P0. Capture HDMI audio/monitor output, note timing, sample integrity and clean exit.

P0 assembly currently uses `RDVBL` spin waits; this needs testing against the IIe CPU clock and card mode. An accelerated TransWarp implementation should be a separate target with timing tests.
