#!/usr/bin/env python3
"""P1B precompiler: MOD pattern breaks, order jumps and E6x loops.

Keeps the hardware-tested P0 engine and P1A ProDOS SYS builder.
Four-channel ProTracker MOD only. Tick-level musical effects are rejected.
"""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
import sys
from mod_to_s8m import ModError, MAX_TOTAL_MODULE, decode_event, make_waves, pitch_to_fc, read_mod
from p1_build import make_sys

ROOT = Path(__file__).resolve().parents[1]


def trace_flow(orders, patterns):
    events = []
    oi = row = 0
    starts = [0, 0, 0, 0]
    counters = [0, 0, 0, 0]
    while oi < len(orders):
        if len(events) > 4000:
            raise ModError("More than 4000 played rows: possible infinite loop")
        pat = orders[oi]
        notes = [decode_event(patterns, pat*1024+row*16+ch*4) for ch in range(4)]
        events.append((oi, pat, row, notes))
        next_order, next_row = oi, row+1
        dest = brk = loop = None
        for ch, (_, _, fx, arg) in enumerate(notes):
            if fx == 0x0B:
                dest = arg
            elif fx == 0x0D:
                brk = (arg >> 4)*10+(arg & 15)
                if brk > 63:
                    raise ModError("Bad Dxx pattern break")
            elif fx == 0x0E and arg >> 4 == 6:
                n = arg & 15
                if not n:
                    starts[ch] = row
                elif not counters[ch]:
                    counters[ch] = n
                    loop = starts[ch]
                else:
                    counters[ch] -= 1
                    if counters[ch]:
                        loop = starts[ch]
        if dest is not None or brk is not None:
            next_order = dest if dest is not None else oi+1
            next_row = brk if brk is not None else 0
        elif loop is not None:
            next_row = loop
        elif next_row == 64:
            next_order, next_row = oi+1, 0
        if next_order != oi:
            starts, counters = [0]*4, [0]*4
        if next_order > len(orders):
            raise ModError("Pattern jump exceeds song order count")
        oi, row = next_order, next_row
    return events


def convert_flow(mod: bytes):
    orders, patterns, samples = read_mod(mod)
    played = trace_flow(orders, patterns)
    used = {inst for _, _, _, notes in played for inst, period, _, _ in notes
            if inst and period}
    bank, catalog = make_waves(samples, used)
    if 29*len(played)+len(bank) > MAX_TOTAL_MODULE:
        raise ModError("Flattened song exceeds P1A main RAM limit")
    speed, bpm = 6, 125
    accum = Fraction(0, 1)
    instruments = [0]*4
    volumes = [64]*4
    data = bytearray()
    unsupported = Counter()
    for oi, pat, row, notes in played:
        event = []
        for ch, (inst, period, fx, arg) in enumerate(notes):
            if inst:
                instruments[ch] = inst
                volumes[ch] = samples[inst-1].volume
            if fx == 0x0F:
                if not arg:
                    unsupported["F00"] += 1
                elif arg <= 31:
                    speed = arg
                else:
                    bpm = arg
            elif fx == 0x0C:
                volumes[ch] = min(64, arg)
            elif fx in (0x0B, 0x0D):
                pass
            elif fx == 0x0E and arg >> 4 == 6:
                pass
            elif fx or arg:
                unsupported[f"{fx:X}{arg:02X}"] += 1
            fc = wtp = rts = vol = ctrl = flags = 0
            if period:
                n = instruments[ch]
                if n not in catalog:
                    raise ModError(f"Missing sample at order {oi}, row {row}")
                wtp, rts, mode, _ = catalog[n]
                fc = pitch_to_fc(period)
                vol = min(192, volumes[ch]*3)
                ctrl = (0x10 if ch in (1, 2) else 0) | mode
                flags = 1
            elif fx == 0x0C and not arg:
                flags = 2
            elif fx == 0x0C:
                unsupported["Cxx volume without note"] += 1
            event.extend((fc & 255, fc >> 8, wtp, rts, vol, ctrl, flags))
        accum += Fraction(150*speed, bpm)
        frames = accum.numerator//accum.denominator
        accum -= frames
        data.append(max(1, min(255, frames)))
        data.extend(event)
    if unsupported:
        raise ModError("Unsupported tracker effects: " +
                       ", ".join(f"{n} x{count}" for n,count in unsupported.most_common(8)))
    return bank, bytes(data), played


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod", type=Path)
    parser.add_argument("--p0", type=Path, default=ROOT/"dist/SENSEI8-P0.BIN")
    parser.add_argument("--out", type=Path, default=ROOT/"dist/SENSEI8-P1B.SYSTEM")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    bank, rows, played = convert_flow(args.mod.read_bytes())
    image = make_sys(args.p0.read_bytes(), rows, bank)
    print("Orders", len(set(o for o,_,_,_ in played)),
          "played rows", len(played), "DOC PCM", len(bank), "SYS", len(image))
    print("ProDOS load from 0x2000 to", hex(0x2000+len(image)-1))
    print("Expected playback seconds at 60Hz:", round(sum(rows[::29])/60, 2))
    if not args.analyze:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(image)
        print("PASS:", args.out)
    else:
        print("PASS: fits existing P1A hardware engine; no file written")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ModError) as exc:
        sys.exit("ERROR: " + str(exc))
