#!/usr/bin/env python3
"""P1D 6502 hardware-mailbox simulation (no FPGA/BL616 deployment)."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from make_p1d_sys import create
from test_player import Tiny6502

class LinkedIIe(Tiny6502):
    def __init__(self,raw, *, bridge=True):
        super().__init__(raw)
        self.bridge=bridge
        self.commands=[]
        self.mcu_state=0
        self.state_polls=0
        self.song_arg=None
    def read(self,addr):
        if addr==0xC0CA:return 0x53 if self.bridge else 0
        if addr==0xC0CB:return 0x1D if self.bridge else 0
        if addr==0xC0CC:
            self.state_polls+=1
            if self.mcu_state==2 and self.state_polls>=300:
                self.mcu_state=3
            return self.mcu_state
        return super().read(addr)
    def write(self,addr,value):
        if addr==0xC0CD:
            self.song_arg=value
        elif addr==0xC0CC:
            self.commands.append(value)
            self.mcu_state=2 if value==1 else 0
        else:
            super().write(addr,value)

def run():
    orig=(ROOT/"dist/SENSEI8-P0.BIN").read_bytes()
    image,labels=create(orig)
    assert len(image)>len(orig)+24 and len(image)<0x7000
    assert image[0]==0x4C
    assert "WaitStart" in labels and "WaitPlay" in labels
    # Compare encoded sample bank against established P0P8 eight-cycle patch.
    off=len(orig)-1024
    for ch in range(4):
        start=off+256*ch
        assert image[start:start+256]==orig[start:start+256:8]*8
    raw=bytearray(image[:-24])
    raw[:3]=orig[:3]
    sim=LinkedIIe(raw)
    sim.run(limit=500000)
    assert sim.upload_count==1024,sim.upload_count
    assert sim.song_arg==0 and sim.commands==[1],sim.commands
    assert sim.state_polls>=300
    assert sim.run_events==[],"6502 must not run the original row sequencer"
    assert sim.regs[0x40]==0 and sim.regs[0x43]==0
    print("PASS: P1D 6502 loads 1024 DOC bytes and delegates all playback to MCU")
    print("PASS: mailbox START, MCU PLAYING->DONE, DOC halt, original ZP restoration")
    no_link=LinkedIIe(raw,bridge=False)
    no_link.run(limit=500000)
    assert no_link.upload_count==1024 and not no_link.commands
    print("PASS: older FPGA safely skips unsupported P1D mailbox")
    class StalledMCU(LinkedIIe):
        def __init__(self,binary):
            super().__init__(binary,bridge=True)
            self.panicked=False
        def write(self,addr,val):
            if addr==0xC0CC and val==1:
                self.commands.append(val)
                self.mcu_state=0  # mismatched old MCU never acknowledges
            elif addr==0xC0CF and val==0xA5:
                self.panicked=True
            else:
                super().write(addr,val)
    stalled=StalledMCU(raw)
    stalled.run(limit=1500000)
    assert stalled.panicked and stalled.commands==[1]
    assert stalled.regs[0x40]==0 and stalled.regs[0x43]==0
    print("PASS: new FPGA + old MCU startup times out safely and panics")
    # F4EE/ProDOS QUIT wrapper byte checks (not an OS simulation).
    assert image[-24:-21]==bytes.fromhex("D8 A5 06")
    assert image[-21:-18]==bytes.fromhex("20 03 20")
    assert bytes.fromhex("20 00 BF 65") in image[-24:]
    print("PASS: ProDOS SYS entry and MLI QUIT byte structure")

if __name__=="__main__":
    run()
