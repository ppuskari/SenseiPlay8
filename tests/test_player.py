#!/usr/bin/env python3
"""Executable P0 source/6502 register-bus smoke, not a physical IIe test."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
from s8asm import assemble, OPCODES
from mod_to_s8m import convert, read_mod, pitch_to_fc, emit, ModError
from make_demo_mod import make


class Tiny6502:
    """Narrow emulation of the exact opcodes Sensei8 uses; fails on any other."""
    def __init__(self, binary):
        self.mem=bytearray(65536)
        self.mem[0x2000:0x2000+len(binary)]=binary
        self.pc=0x2000; self.a=0; self.x=0; self.y=0; self.sp=0xFD
        self.c=0; self.z=0; self.n=0; self.steps=0; self.finished=False
        self.ctl=0x0F; self.ptr=0; self.hi=0
        self.ram=bytearray(65536); self.regs={}; self.writes=[]
        self.upload_count=0; self.run_events=[]; self.console=''
        self.rev={code:(mn,mode) for mn,modes in OPCODES.items() for mode,code in modes.items()}
        # CALL $2000 entered from BASIC; stack RTS returns to 0x0000.
        self.mem[0x01FE]=0xFF; self.mem[0x01FF]=0xFF
        self.sp=0xFD

    def read(self,addr):
        addr&=0xffff
        if addr==0xC0C4: return 0x44
        if addr==0xC0C5: return 0x4F
        if addr==0xC0C6: return 0x43
        if addr==0xC0C8: return 0xA2
        if addr==0xC019: return 0x80 if self.steps%160>=120 else 0
        if addr==0xC000: return 0
        return self.mem[addr]

    def write(self,addr,value):
        addr&=0xffff; value&=255
        if addr==0xC0C0:
            self.ctl=value
        elif addr==0xC0C2:
            self.ptr=(self.ptr&0xFF00)|value
        elif addr==0xC0C3:
            self.ptr=(self.ptr&0x00FF)|(value<<8)
        elif addr==0xC0C1:
            if self.ctl & 0x40:
                self.ram[self.ptr]=value
                self.upload_count+=1
                if self.ctl & 0x20: self.ptr=(self.ptr+1)&65535
            else:
                self.regs[self.ptr]=value
                self.writes.append((self.ptr,value))
                if 0xA0<=self.ptr<=0xA3 and not (value & 1):
                    self.run_events.append((self.ptr,value))
        elif addr in (0xC010,0xC051): pass
        else: self.mem[addr]=value

    def f(self,v):
        v&=255
        self.z=int(v==0); self.n=(v>>7)&1
        return v

    def pop(self):
        self.sp=(self.sp+1)&255
        return self.read(0x0100+self.sp)

    def push(self,v):
        self.write(0x0100+self.sp,v)
        self.sp=(self.sp-1)&255

    def step(self):
        if self.finished:return
        self.steps+=1
        op=self.read(self.pc); self.pc=(self.pc+1)&65535
        if op not in self.rev: raise AssertionError(f'unsupported opcode {op:02X} at {self.pc-1:04X}')
        mn,mode=self.rev[op]
        if mode=='imp': value=0; addr=None
        elif mode in ('imm','rel'):
            value=self.read(self.pc); self.pc=(self.pc+1)&65535; addr=None
        elif mode=='zp':
            addr=self.read(self.pc); self.pc=(self.pc+1)&65535; value=self.read(addr)
        elif mode=='zpx':
            addr=(self.read(self.pc)+self.x)&255; self.pc=(self.pc+1)&65535; value=self.read(addr)
        elif mode in ('abs','absx','absy'):
            lo=self.read(self.pc); hi=self.read(self.pc+1); self.pc=(self.pc+2)&65535
            addr=((hi<<8)|lo)+(self.x if mode=='absx' else self.y if mode=='absy' else 0)
            addr&=65535; value=self.read(addr)
        elif mode=='indy':
            zp=self.read(self.pc); self.pc=(self.pc+1)&65535
            addr=(self.read(zp)|self.read((zp+1)&255)<<8)+self.y
            addr&=65535; value=self.read(addr)
        else: raise AssertionError(mode)
        if mn=='lda':self.a=self.f(value)
        elif mn=='ldx':self.x=self.f(value)
        elif mn=='ldy':self.y=self.f(value)
        elif mn=='sta':self.write(addr,self.a)
        elif mn=='stx':self.write(addr,self.x)
        elif mn=='sty':self.write(addr,self.y)
        elif mn=='inx':self.x=self.f(self.x+1)
        elif mn=='iny':self.y=self.f(self.y+1)
        elif mn=='dex':self.x=self.f(self.x-1)
        elif mn=='txa':self.a=self.f(self.x)
        elif mn=='tax':self.x=self.f(self.a)
        elif mn=='tay':self.y=self.f(self.a)
        elif mn=='clc':self.c=0
        elif mn=='sec':self.c=1
        elif mn=='cld':pass
        elif mn=='pha':self.push(self.a)
        elif mn=='pla':self.a=self.f(self.pop())
        elif mn=='and':self.a=self.f(self.a&value)
        elif mn=='ora':self.a=self.f(self.a|value)
        elif mn=='adc':
            result=self.a+value+self.c;self.c=int(result>255);self.a=self.f(result)
        elif mn=='cmp':
            result=self.a-value;self.c=int(result>=0);self.f(result)
        elif mn=='cpx':
            result=self.x-value;self.c=int(result>=0);self.f(result)
        elif mn=='inc':self.write(addr,self.f(value+1))
        elif mn=='dec':self.write(addr,self.f(value-1))
        elif mn=='jmp':self.pc=addr
        elif mn=='jsr':
            if addr==0xFDED:
                self.console+=chr(self.a&127)
            elif addr==0xFD8E:
                self.console+='\n'
            else:
                ret=(self.pc-1)&65535
                self.push((ret>>8)&255);self.push(ret&255)
                self.pc=addr
        elif mn=='rts':
            lo=self.pop();hi=self.pop();ret=((hi<<8)|lo)
            self.pc=(ret+1)&65535
            if self.pc==0: self.finished=True
        elif mn in ('beq','bne','bcc','bcs','bpl','bmi'):
            take={'beq':self.z==1,'bne':self.z==0,'bcc':self.c==0,
                  'bcs':self.c==1,'bpl':self.n==0,'bmi':self.n==1}[mn]
            if take:self.pc=(self.pc+(value-256 if value>127 else value))&65535
        else: raise AssertionError(mn)

    def run(self,limit=1000000):
        while not self.finished and self.steps<limit:self.step()
        assert self.finished, f'6502 did not return to BASIC after {self.steps} steps, PC={self.pc:04X}'


def test_good():
    orders, patterns, instruments=read_mod(make())
    assert len(orders)==1 and len(patterns)==1024
    assert instruments[0].repeat_length==256
    bank,rows,warnings,catalog=convert(make())
    assert len(bank)==1024 and len(rows)==64*29
    assert not warnings, warnings
    assert [catalog[i][0] for i in range(1,5)]==[0,1,2,3]
    assert [rows[n*29] for n in range(5)]==[7,7,7,7,8]
    assert pitch_to_fc(428)==161
    assert 'SongRows' in emit(bank,rows)
    origin,binary,sym=assemble(root/'src/sensei8.s')
    assert origin==0x2000 and binary[:1]==b'\xD8'
    assert origin+len(binary)<0x9000
    emu=Tiny6502(binary)
    emu.run()
    assert emu.upload_count==len(bank),(emu.upload_count,len(bank))
    assert emu.ram[:len(bank)]==bank
    assert (0xE1,0x3E) in emu.writes
    assert len(emu.run_events)==64
    assert {x[0] for x in emu.run_events}=={0xA0,0xA1,0xA2,0xA3}
    assert 'SENSEI8' in emu.console
    assert emu.regs[0x40]==0 and emu.regs[0x43]==0  # voices silenced on exit
    print('PASS: MOD -> 64 rows -> 6502 BIN -> 1024 DOC sample uploads -> 64 voice retriggers -> return to BASIC')
    print(f'     6502 steps={emu.steps}, code+data={len(binary)}, audio status='+str(emu.run_events[:4]))


def test_reject():
    bad=bytearray(make());bad[1080:1084]=b'6CHN'
    try:read_mod(bytes(bad)); assert False
    except ModError:pass
    bad=make()[:1084+500]
    try:read_mod(bad);assert False
    except ModError:pass
    print('PASS: invalid channel format and truncated MOD rejected')

if __name__=='__main__':
    test_good();test_reject()
