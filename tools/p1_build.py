#!/usr/bin/env python3
"""Precompile a standard four-channel MOD to a native ProDOS SYS for SenseiPlay8.

P1A extends the hardware-proven P0 engine's data area without modifying its
6502 instructions except the two immediates pointing to the moved sample bank.
The original P0, P0L4, and P0P8 test binaries stay frozen.

Limitations: preloaded MOD samples only, 4 channels, no tracker tick effects
(slides/vibrato/arpeggio), no streaming, no NTP-file parser yet. Unsupported
effects are rejected by default rather than silently changing a song.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys

from mod_to_s8m import convert, read_mod, ModError, MAX_TOTAL_MODULE

ROOT = Path(__file__).resolve().parents[1]
P0_HASH = "4731bd6b44d4270ab9d50c28fad23a4aaf13a852403af0f91158ae2e640a1152"
ENGINE_BYTES = 0x294        # bytes before the four-byte P0 module header
ROWS_OFFSET = ENGINE_BYTES + 4
LOAD_ADDR = 0x2000
SAFE_END = 0x9000          # conservative main-memory ceiling for ProDOS SYS
BANK_LOAD_OPERANDS = bytes.fromhex("A9 D8 85 08 A9 29 85 09")


def make_sys(p0: bytes, rows: bytes, bank: bytes) -> bytes:
    if hashlib.sha256(p0).hexdigest() != P0_HASH or len(p0) != 3544:
        raise ValueError("P0 executable differs from the frozen hardware-proven baseline")
    if len(rows) == 0 or len(rows) % 29 or len(rows)//29 > 65535:
        raise ValueError("Expected nonempty 29-byte/row stream with 16-bit count")
    if len(bank) == 0 or len(bank) > 65535:
        raise ValueError("Expected 1..65535-byte sound bank")
    if len(rows) + len(bank) > MAX_TOTAL_MODULE:
        raise ValueError(f"Song data {len(rows)+len(bank)} exceeds P1A {MAX_TOTAL_MODULE}-byte main RAM budget")

    engine = bytearray(p0[:ENGINE_BYTES])
    pos = engine.find(BANK_LOAD_OPERANDS)
    if pos < 0 or engine.find(BANK_LOAD_OPERANDS, pos + 1) >= 0:
        raise ValueError("Could not uniquely identify original DOC sample pointer")
    bank_address = LOAD_ADDR + ROWS_OFFSET + len(rows)
    if bank_address + len(bank) > SAFE_END - 24:
        raise ValueError("DOC bank and ProDOS exit code would exceed $8FFF")
    # The old P0 'lda #<SampleBank; sta $08; lda #>SampleBank; sta $09'
    # is immediate-addressed. No 6502 relocation or new opcodes needed.
    engine[pos + 1] = bank_address & 255
    engine[pos + 5] = bank_address >> 8
    player = engine + struct.pack("<HH", len(rows)//29, len(bank)) + rows + bank
    stub_address = LOAD_ADDR + len(player)
    assert player[:3] == bytes.fromhex("D8 A5 06")
    # Restore displaced entry bytes, execute P0, and use ProDOS MLI QUIT.
    stub = bytearray(bytes.fromhex("D8 A5 06 20 03 20 EE F4 03 20 00 BF 65"))
    param_address = stub_address + len(stub) + 4
    stub += struct.pack("<H", param_address) + bytes.fromhex("00 00 04 00 00 00 00 00 00")
    if len(stub) != 24:
        raise AssertionError("ProDOS launcher stub unexpectedly changed")
    player[:3] = bytes([0x4C]) + struct.pack("<H", stub_address)
    player.extend(stub)
    if LOAD_ADDR + len(player) > SAFE_END:
        raise ValueError("ProDOS program overlaps reserved high memory")
    return bytes(player)


def inspect(mod: bytes) -> dict:
    orders, patterns, samples = read_mod(mod)
    effect_count = {}
    used = set()
    for pat in orders:
        for off in range(pat * 1024, pat * 1024 + 1024, 4):
            a, b, c, d = patterns[off:off+4]
            inst = (a & 0xF0) | (c >> 4)
            period = ((a & 0x0F) << 8) | b
            if inst and period:
                used.add(inst)
            effect = c & 0x0F
            if effect or d:
                key = f"{effect:X}"
                effect_count[key] = effect_count.get(key, 0) + 1
    return {
        "orders": len(orders),
        "unique_patterns": len(set(orders)),
        "instruments_used": len(used),
        "source_pcm_bytes": sum(len(s.sample) for s in samples if s.index in used),
        "effects": effect_count,
    }


def compile_mod(mod: bytes, p0: bytes, allow_unsupported: bool = False):
    info = inspect(mod)
    bank, rows, warnings, catalog = convert(mod, max_rows=65535)
    # Unsupported notes/effects can produce an inaccurate song. Make the
    # user opt in explicitly, while keeping the plain P0 converter permissive.
    if warnings and not allow_unsupported:
        raise ModError("Unsupported tracker effects: " + "; ".join(warnings[:5]) +
                       ". Use --allow-unsupported to hear a partial interpretation.")
    image = make_sys(p0, rows, bank)
    info.update({
        "rows": len(rows)//29,
        "row_bytes": len(rows),
        "doc_sample_bytes": len(bank),
        "prodos_sys_bytes": len(image),
        "end_address": LOAD_ADDR + len(image) - 1,
        "free_program_bytes": SAFE_END - LOAD_ADDR - len(image),
        "warnings": warnings,
    })
    return image, info


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mod", type=Path, help="31-instrument 4-channel ProTracker .MOD")
    p.add_argument("--p0", type=Path, default=ROOT / "dist/SENSEI8-P0.BIN")
    p.add_argument("--out", type=Path, default=ROOT / "dist/SENSEI8-P1A.SYSTEM")
    p.add_argument("--analyze", action="store_true", help="check memory/effects without writing a SYS")
    p.add_argument("--allow-unsupported", action="store_true", help="ignore unsupported tracker effects")
    args = p.parse_args(argv)
    raw = args.mod.read_bytes()
    base = args.p0.read_bytes()
    image, info = compile_mod(raw, base, args.allow_unsupported)
    print(f"MOD: {args.mod.name}, {info['orders']} orders, {info['unique_patterns']} unique patterns")
    print(f"Rows: {info['rows']}; DOC PCM: {info['doc_sample_bytes']} bytes; row events: {info['row_bytes']} bytes")
    print(f"ProDOS SYS: {info['prodos_sys_bytes']} bytes, $2000-${info['end_address']:04X}; main RAM reserve: {info['free_program_bytes']} bytes")
    print(f"Effects: {info['effects'] or 'none'}")
    for msg in info["warnings"]:
        print("WARNING:", msg)
    if not args.analyze:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(image)
        print(f"PASS: wrote {args.out} (SHA256 {hashlib.sha256(image).hexdigest()})")
    else:
        print("PASS: feasible in P1A memory model; no file written")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ModError, ValueError) as exc:
        sys.exit("ERROR: " + str(exc))
