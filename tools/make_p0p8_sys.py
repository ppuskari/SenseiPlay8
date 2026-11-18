#!/usr/bin/env python3
"""Experimental P0P8: musical-register synthetic sample variant.

Only the four synthetic 256-byte instrument tables change (8 cycles each
instead of one). Original P0 engine and row event data remain identical.
P0L4's last nominal-left marker stays ~411 Hz using FC=$0100.

PowerShell 5.1 from the SenseiPlay8 repository root:
    py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
    py -3 tools/make_p0p8_sys.py
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from make_p0l4_sys import build as build_p0l4

ROOT = Path(__file__).resolve().parents[1]
P0_SIZE = 3544
SAMPLE_BYTES = 1024
SAMPLE_OFFSET = P0_SIZE - SAMPLE_BYTES
P0P8_SHA256 = "9ca81bd61a39caa7f1d3feda90a85ff619ae4ef2e756bd69d378303ddde73b23"


def build(p0: bytes) -> bytes:
    original = build_p0l4(p0)  # validates frozen P0 and P0L4 hashes
    assert len(original) == 3728
    changed = bytearray(original)

    for instrument in range(4):
        start = SAMPLE_OFFSET + instrument * 256
        cycle = original[start:start + 256]
        assert len(cycle) == 256 and 0 not in cycle
        changed[start:start + 256] = cycle[::8] * 8

    # P0L4's ending diagnostic sets oscillator-1 freq high byte $08.
    # Eight wave cycles per table means an 8x smaller FC keeps ~411 Hz.
    instruction = bytes.fromhex("A0 21 A9 08 20 7E 2E")
    assert original.count(instruction) == 1
    byte_offset = original.index(instruction) + 3
    assert byte_offset > P0_SIZE
    changed[byte_offset] = 0x01

    for i, b in enumerate(original):
        if SAMPLE_OFFSET <= i < SAMPLE_OFFSET + SAMPLE_BYTES or i == byte_offset:
            continue
        assert changed[i] == b
    result = bytes(changed)
    assert sha256(result).hexdigest() == P0P8_SHA256
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p0", type=Path, default=ROOT / "dist/SENSEI8-P0.BIN")
    parser.add_argument("--out", type=Path, default=ROOT / "dist/SENSEI8-P0P8.SYSTEM")
    args = parser.parse_args()
    result = build(args.p0.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    print(f"PASS: P0P8 experimental ProDOS SYS: {len(result)} bytes")
    print("PASS: 8 cycles in each 256-byte synthetic instrument table")
    print("PASS: original player and sequence unchanged; isolated LEFT marker ~411 Hz")
    print(f"SHA256: {sha256(result).hexdigest()}")


if __name__ == "__main__":
    main()
