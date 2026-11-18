# P1C design and validation

## Memory layout

The frozen P0 6502 row player is kept at $2000-$2293. The 29-byte row stream
starts at $2298, followed by the packed DOC sample bank (used for the startup
DOC RAM upload). Immediately after the sample bank is a variable-length
**effect timeline**, followed by a 6502 effects interpreter and the ProDOS
SYS/QUIT wrapper.

The existing player executes `JSR PrepareSong` ($2133) and `JSR WaitFrames`
($2204). Only the **JSR targets** are patched: the first initializes the
effects pointer, and the second consumes the effects scheduled within the
row. When a row has no effects, the timeline contains only `$FF` and the
original WaitFrames is called for the entire row. The existing DOCWrite
routine ($20BA), WaitOneFrame ($2210), and playback exit remain unchanged.

`$08/$09` are used first as the sample upload pointer, and then as the
effects timeline pointer. The frozen P0 startup/finish already save and
restore those addresses, so the ProDOS QUIT wrapper sees preserved state.

Effect commands are `[frame-offset, opcode, low-value, high-value]`, followed
by `$FF` for end-of-row. Opcodes `0x00..0x03` write frequency low/high for
DOC oscillators 0..3; `0x10..0x13` write their volumes; `0x20..0x23` perform
halt/unhalt oscillator retrigger with the previously chosen control value.
Frame offsets start at zero and are always non-decreasing within a row.

ProTracker semantics are precomputed in Python, with 60Hz integer-frame
quantization. A zero-offset event is applied immediately after PlayRow.
All time-consuming runtime effects simply call the same original VBL wait
routine; no 6502 sine/pitch math is necessary.

## Known limitations

- Exact effect tick placement is quantized to the IIe's 60Hz VBL, not the
  native 50Hz PAL MOD rate. Heavy effects may sound slightly different.
- The vibrato curve is a sine approximation, not a bit-for-bit ProTracker
  sine table reproduction. Correct stereo routing is retained.
- EDx note delay, 9xx sample offset, fine volume slide, pattern delay,
  glissando, filter toggle, panning and full native NTP format deferred.
- 15k Boogie is currently an excerpt of the first two orders. Its full six
  orders require additional sample/memory staging and note-delay support.
- One 256..8192-byte aligned DOC table per instrument; one-shot attack and
  sustain loop fidelity are still constrained by P0 sample handling.
- Native DOC personality $A2 Slot4 required.

## Private sample provenance

The two-order 15k test SYS includes samples derived from the MOD supplied by
the user for private testing. The *original* MOD is not distributed here
and must not be committed to a public GitHub repository. The original
FXDEMO and the archived P0/P1A test samples are separately generated music.