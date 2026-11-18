#!/usr/bin/env python3
"""Synthetic-only P1B pattern-flow tests (no third-party audio)."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
from p1b_flow_build import trace_flow, convert_flow
from p1_build import make_sys, compile_mod
from make_p1_demo_mod import make
from mod_to_s8m import ModError
from test_player import Tiny6502

def run():
    p0=(ROOT/"dist/SENSEI8-P0.BIN").read_bytes()
    mod=make()
    bank,rows,played=convert_flow(mod)
    baseline,details=compile_mod(mod,p0)
    assert len(played)==192 and make_sys(p0,rows,bank)==baseline
    print("PASS: P1B reproduces P1A exactly without flow effects")
    mutated=bytearray(mod)
    # First order D00 at row 23, skipping rows 24..63.
    i=1084+23*16+3*4
    mutated[i+2]=(mutated[i+2]&0xF0)|0x0D
    mutated[i+3]=0
    # Last pattern E60 at row 0, E61 at row 23: one extra loop.
    i=1084+2*1024
    mutated[i+2]=(mutated[i+2]&0xF0)|0x0E
    mutated[i+3]=0x60
    i=1084+2*1024+23*16
    mutated[i+2]=(mutated[i+2]&0xF0)|0x0E
    mutated[i+3]=0x61
    bank,rows,played=convert_flow(bytes(mutated))
    assert len(played)==176 and len(rows)==176*29
    assert sum(o==0 for o,_,_,_ in played)==24
    assert sum(o==2 and r==0 for o,_,r,_ in played)==2
    binary=make_sys(p0,rows,bank)
    raw=bytearray(binary[:-24])
    raw[:3]=p0[:3]
    emu=Tiny6502(raw)
    emu.run(limit=2500000)
    assert emu.upload_count==len(bank)
    assert len(emu.run_events)>100
    print("PASS: D00 break + E6x repeat +",len(played),"6502-played rows")
    # Unsupported vibrato command must fail rather than sound wrong.
    mutated[1084+3]=0x24
    try:
        convert_flow(bytes(mutated))
    except ModError:
        pass
    else:
        raise AssertionError("Unsupported tracker effect silently accepted")
    print("PASS: unsupported effects refused")

if __name__=="__main__":
    run()
