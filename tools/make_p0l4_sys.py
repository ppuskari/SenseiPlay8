#!/usr/bin/env python3
"""Create a P0L4 ProDOS SYS from the original SenseiPlay8 P0 binary.

The 184-byte appended 6502 wrapper is the frozen P0L4 stereo test:
 P0 music -> ~0.3 s silence -> DOC oscillator 1 ONLY, CTRL bit4=1,
 triangle table 1, FC=$0800, volume $70, 240 x 60Hz VBL frames.
No original player bytes change except the 3-byte entrypoint JMP.
The OS-containing ProDOS .po image is not included in this repository.

Usage (Windows PowerShell 5.1, one line per command):
  py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
  py -3 tools/make_p0l4_sys.py
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path

P0_SHA256 = "4731bd6b44d4270ab9d50c28fad23a4aaf13a852403af0f91158ae2e640a1152"
SYS_SHA256 = "10cc6fd3b51ed49ebe5487faa244a415f68fc32519893e17200a3531f7ffb21e"

# Hand-assembled 6502 entry trampoline and isolated left-bit4 oscillator tail.
# The first 24 bytes are P0 entry/ProDOS QUIT; the rest are the DOC test.
# Base $2DD8. Documentation: docs/P0L4_STEREO_TEST.md
STUB = bytes.fromhex("""
D8A50620032020F22DEEF4032000BF65EB2D0004000000000000ADC8C0C9A2F0
0160ADC4C0C944F00160ADC5C0C94FF00160ADC6C0C943F00160A21220852ECA
D0FAA90F8DC0C0A9008DC3C0A0A1A911207E2EA081A901207E2EA0C1A900207E
2EA001A900207E2EA021A908207E2EA041A900207E2EA0A1A910207E2EA041A9
70207E2EA2F020852EAD00C03006CAD0F54C6F2EAD10C0A041A900207E2EA0A1
A911207E2E608CC2C08DC1C060AD19C030FBAD19C010FB60
""")


def build(p0: bytes) -> bytes:
    if len(p0) != 3544 or sha256(p0).hexdigest() != P0_SHA256:
        raise ValueError("Expected unmodified 3544-byte P0 source binary")
    if p0[:3] != bytes.fromhex("D8 A5 06") or len(STUB) != 184:
        raise ValueError("Unexpected P0 entry bytes or diagnostic stub length")
    player = bytearray(p0)
    player[:3] = bytes.fromhex("4C D8 2D")  # JMP $2DD8, appended stub
    player.extend(STUB)
    result = bytes(player)
    if len(result) != 3728 or sha256(result).hexdigest() != SYS_SHA256:
        raise ValueError("P0L4 executable hash mismatch")
    return result


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p0", type=Path, default=repo / "dist/SENSEI8-P0.BIN")
    parser.add_argument("--out", type=Path, default=repo / "dist/SENSEI8-P0L4.SYSTEM")
    args = parser.parse_args()
    payload = build(args.p0.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(f"PASS: P0L4 native ProDOS SYS {len(payload)} bytes, SHA256 {SYS_SHA256}")
    print("P0 music; 0.3-sec silence; four-second bit4=1 isolated voice; QUIT")


if __name__ == "__main__":
    main()
