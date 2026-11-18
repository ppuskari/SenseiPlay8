#!/usr/bin/env python3
"""Generate an ORIGINAL three-pattern, four-instrument MOD for SenseiPlay8.

This is a longer noncopyrighted hardware exercise using the P0P8 eight-cycle
instrument approach. No third-party module/samples are required.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
from demo_waves import VOICE_SAMPLES

SONG = b"SENSEI8 THREE PATTERNS"
# P0P8 showed eight cycles in a 256-byte DOC table have musical pitches.
SAMPLES = tuple(bytes(s[::8]) * 8 for s in VOICE_SAMPLES)
NOTES = (
    (428, 381, 339, 320, 285, 254, 226, 214),  # sine melody
    (571, 508, 453, 428, 381, 339, 302, 285),  # triangle harmony
    (856, 762, 678, 640, 570, 508, 453, 428),  # pulse bass
    (214, 226, 254, 285, 320, 339, 381, 428),  # bell highlight
)


def make() -> bytes:
    song = bytearray(1084 + 3*1024)
    song[:20] = SONG[:20].ljust(20, b" ")
    for ch, name in enumerate((b"SINE8", b"TRIANGLE8", b"PULSE8", b"BELL8")):
        off = 20 + ch*30
        song[off:off+len(name)] = name
        song[off+22:off+24] = struct.pack(">H", 128)
        song[off+25] = 48
        song[off+26:off+28] = struct.pack(">H", 0)
        song[off+28:off+30] = struct.pack(">H", 128)
    song[950] = 3                 # 3 distinct patterns in 3 orders
    song[951] = 127
    song[952:955] = bytes((0,1,2))
    song[1080:1084] = b"M.K."
    for pattern in range(3):
        for row in range(64):
            for ch in range(4):
                # Chords change by section, melody/harmony at different times.
                trigger = (row % 4 == 0 if ch != 2 else row % 8 == 0)
                if not trigger:
                    continue
                step = (row//4 + pattern*(ch+1)) % 8
                period = NOTES[ch][step]
                if pattern == 1 and ch == 3:
                    period = NOTES[ch][(step+3)%8]
                index = 1084 + pattern*1024 + row*16 + ch*4
                inst = ch+1
                song[index] = (inst & 0xF0) | ((period>>8)&15)
                song[index+1] = period & 255
                song[index+2] = (inst & 15)<<4
                song[index+3] = 0
    return bytes(song) + b"".join(SAMPLES)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("assets/sensei8-p1-three-pattern.mod"))
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    image = make()
    args.out.write_bytes(image)
    print(f"PASS: original three-pattern MOD {args.out}: {len(image)} bytes")


if __name__ == "__main__":
    main()
