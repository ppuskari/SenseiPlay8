#!/usr/bin/env python3
"""P1A regression: multi-order conversion, sample relocation, physical-DOC bus simulation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
from make_p1_demo_mod import make as make3
from make_demo_mod import make as make0
from mod_to_s8m import convert, ModError
from p1_build import compile_mod, make_sys, inspect
from test_player import Tiny6502


def run():
    p0 = (ROOT/"dist/SENSEI8-P0.BIN").read_bytes()
    # P0 is bit-for-bit preserved by the generic P1A reformatter.
    bank, rows, warnings, _ = convert(make0())
    p0sys, info = compile_mod(make0(), p0)
    assert info["rows"] == 64 and len(p0sys) == len(p0)+24
    assert p0sys[0] == 0x4C
    assert p0sys[3:0x294] == p0[3:0x294]
    assert p0sys[0x294:0x298] == p0[0x294:0x298]
    assert p0sys[0x298:0x298+len(rows)] == rows

    three = make3()
    assert len(three) == 1084+3072+1024
    image, info = compile_mod(three, p0)
    assert info["orders"] == 3 and info["unique_patterns"] == 3
    assert info["rows"] == 192 and info["doc_sample_bytes"] == 1024
    assert info["prodos_sys_bytes"] < 0x2000
    assert info["end_address"] < 0x9000
    assert info["warnings"] == [], info["warnings"]
    # Verify sample pointer moved from original P0 address.
    old = p0.find(bytes.fromhex("A9 D8 85 08 A9 29 85 09"))
    assert old >= 0 and image[old+1:old+2] != p0[old+1:old+2]
    address = image[old+1] + 256*image[old+5]
    assert address == 0x2000 + 0x298 + 192*29
    assert image[0] == 0x4C and len(image) < 0x7000
    raw = bytearray(image[:-24])
    raw[:3] = p0[:3]
    sim = Tiny6502(raw)
    sim.run(limit=1500000)
    assert sim.upload_count == 1024, sim.upload_count
    assert len(sim.run_events) == 168, len(sim.run_events)  # 48 x 3 non-bass + 24 bass
    assert {e[0] for e in sim.run_events} == {0xA0,0xA1,0xA2,0xA3}
    assert "SENSEI8" in sim.console
    print("PASS: P1A three-pattern MOD -> 192 rows -> DOC RAM -> 6502 simulated playback")
    print("P1A SYS bytes:",len(image),"ProDOS end:",hex(info["end_address"]))

    # Non-NTP format; reject unsupported MOD changes unless explicitly requested.
    bad = bytearray(three)
    bad[1084+3] = 0x12       # 1xx portamento on channel zero
    try:
        compile_mod(bytes(bad), p0)
        raise AssertionError("unsupported MOD effect accepted")
    except ModError:
        pass
    # 13 repeats should exceed main memory as unrolled rows.
    long = bytearray(three)
    long[950] = 13
    long[952:965] = bytes([0,1,2,0,1,2,0,1,2,0,1,2,0])
    try:
        compile_mod(bytes(long), p0)
        raise AssertionError("oversized MOD accepted")
    except (ModError,ValueError):
        pass
    print("PASS: unsupported effects and oversized songs rejected; P0 unchanged")


if __name__ == "__main__":
    run()
