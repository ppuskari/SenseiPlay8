#!/usr/bin/env python3
"""P1C regression: original music only, no privately uploaded MOD samples."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from make_p1c_effects_demo import build
from make_p1_demo_mod import make as make_p1
from mod_to_s8m import convert
from p1c_effects import preprocess, build_sys
from p1b_flow_build import convert_flow
from p1_build import make_sys

def inspect_fx(fx, rows):
    i=0
    counters={0:0,16:0,32:0}
    for row in range(len(rows)//29):
        prev=0
        duration=rows[row*29]
        while True:
            assert i<len(fx), ("missing FX row sentinel",row)
            at=fx[i]
            if at==255:
                i+=1
                break
            assert i+4<=len(fx)
            op=fx[i+1]
            assert op & 3 in range(4)
            assert (op & 0x30) in counters
            assert prev<=at<=duration,(row,prev,at,duration)
            counters[op&0x30]+=1
            prev=at
            i+=4
    assert i==len(fx), (i,len(fx))
    return counters

def run():
    p0=(ROOT/"dist/SENSEI8-P0.BIN").read_bytes()
    mod=build()
    assert len(mod)==4156
    bank,rows,fx,trace,counts=preprocess(mod)
    assert len(trace)==128 and len(rows)==128*29
    assert len(bank)==1024 and len(fx)==2328
    assert sum(rows[::29])==921
    for effect in ("0","1","2","3","4","5","6","A"):
        assert counts[effect]==16,(effect,counts)
    assert counts["E"]==6 and counts["C"]==2
    regcounts=inspect_fx(fx,rows)
    assert regcounts[0]>50 and regcounts[16]>10 and regcounts[32]>=2
    image,symbols=build_sys(p0,rows,bank,fx)
    assert len(image)==7937
    assert image[:1]==b"\x4C"
    assert symbols["FxWait"]>symbols["FxPrep"]>0x2000
    assert image[0x2D:0x2F]==symbols["FxPrep"].to_bytes(2,"little")
    assert image[0x3B:0x3D]==symbols["FxWait"].to_bytes(2,"little")
    assert 0x2000+len(image)<0x9000
    print("PASS: P1C 128-row FX demo, frequency/volume/retrigger timeline, 6502 hooks")
    original=make_p1()
    normal_bank,normal_rows,warnings,_=convert(original)
    p1b_bank,p1b_rows,_,_,_=convert_flow(original)
    p1c_bank,p1c_rows,p1c_fx,trace,_=preprocess(original)
    assert not warnings
    assert normal_rows==p1b_rows==p1c_rows
    assert normal_bank==p1b_bank==p1c_bank
    assert p1c_fx==b"\xFF"*(len(p1c_rows)//29)
    previous=make_sys(p0,p1b_rows,p1b_bank)
    updated,symbols=build_sys(p0,p1c_rows,p1c_bank,p1c_fx)
    assert len(updated)>len(previous)
    assert updated[0x298:0x298+len(normal_rows)]==previous[0x298:0x298+len(normal_rows)]
    print("PASS: P1A and P1B original no-effects rows remain bit-identical")

if __name__=="__main__":
    run()
