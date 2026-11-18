#!/usr/bin/env python3
"""SenseiPlay8 P1C: precomputed tracker tick effects; stock IIe 6502 DOC runtime.

Keeps the hardware-proven P0 row note engine. The player calls a small injected
hook after PlayRow; this consumes compact, precompiled per-tick DOC FC/volume
writes from a separate stream. There are no floating-point calculations on 6502.

Implemented: 0xy arpeggio, 1xx/2xx period slide, 3xx tone portamento,
4xy vibrato, 5xy/6xy combined effects, Axy volume slides, Cxx, E1x/E2x
fine slides, ECx note cut, Fxx tempo, Bxx/Dxx/E6x order flow.
Rejects unsupported effects. E9x retrigger is supported; 9xx sample offset
and EDx note delay remain future work.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from math import sin,pi
from pathlib import Path
import struct,sys
from mod_to_s8m import read_mod, make_waves, pitch_to_fc, ModError
from p1b_flow_build import trace_flow as flatten_orders
from p1_build import (P0_HASH as P0_SHA256, ENGINE_BYTES, ROWS_OFFSET,
                      BANK_LOAD_OPERANDS, LOAD_ADDR, SAFE_END, MAX_TOTAL_MODULE)

ROOT=Path(__file__).resolve().parents[1]
STUB_QUIT=bytes.fromhex('D8 A5 06 20 03 20 EE F4 03 20 00 BF 65')

# Hand-assembled 6502 code, built by the tiny internal assembler below. No
# 65C02-only instructions; safe on both NMOS 6502 and enhanced 65C02 IIe.
OP={
    ('JSR','abs'):0x20,('JMP','abs'):0x4C,('RTS','imp'):0x60,
    ('LDA','imm'):0xA9,('LDA','zp'):0xA5,('LDA','abs'):0xAD,('LDA','indY'):0xB1,
    ('LDY','imm'):0xA0,('LDX','imm'):0xA2,
    ('STA','zp'):0x85,('STA','abs'):0x8D,
    ('INC','zp'):0xE6,('INC','abs'):0xEE,
    ('CMP','imm'):0xC9,('CPX','imm'):0xE0,
    ('BEQ','rel'):0xF0,('BNE','rel'):0xD0,('BCC','rel'):0x90,
    ('SEC','imp'):0x38,('CLC','imp'):0x18,
    ('SBC','abs'):0xED,('SBC','imm'):0xE9,
    ('ADC','imm'):0x69,('AND','imm'):0x29,('ORA','imm'):0x09,
    ('TAX','imp'):0xAA,('TXA','imp'):0x8A,('TAY','imp'):0xA8,
    ('PHA','imp'):0x48,('PLA','imp'):0x68,('DEX','imp'):0xCA,
}

class Asm:
    def __init__(self,origin):
        self.origin=origin;self.b=bytearray();self.syms={};self.reloc=[]
    def label(self,s):
        if s in self.syms:raise ValueError('Duplicate label '+s)
        self.syms[s]=self.origin+len(self.b)
    def emit(self,op,mode='imp',arg=None):
        self.b.append(OP[(op,mode)])
        n={'imp':0,'imm':1,'zp':1,'indY':1,'rel':1,'abs':2}[mode]
        if n:
            if isinstance(arg,str):self.reloc.append((len(self.b),n,arg,mode));v=0
            else:v=arg
            self.b.extend(v.to_bytes(n,'little'))
    def finish(self):
        for i,n,key,mode in self.reloc:
            if key not in self.syms:raise ValueError('Undefined label '+key)
            v=self.syms[key]
            if mode=='rel':
                v=v-(self.origin+i+1)
                if not -128<=v<=127:raise ValueError('Branch out of range '+key+' '+str(v))
                v&=255
            self.b[i:i+n]=v.to_bytes(n,'little')
        return bytes(self.b),self.syms


def make_fx_runtime(start_addr, fxdata_addr):
    a=Asm(start_addr)
    # Zero-page $08/$09 are reused AFTER upload. Original P0 saves them at
    # startup and restores them in Finish; ProDOS QUIT sees original values.
    # These two routines are reached via P0's own JSR instructions.
    a.label('FxPrep')
    a.emit('JSR','abs',0x2133)   # original PrepareSong
    a.emit('LDA','imm',fxdata_addr&255)
    a.emit('STA','zp',8)
    a.emit('LDA','imm',fxdata_addr>>8)
    a.emit('STA','zp',9)
    a.emit('RTS')
    a.label('FxWait')
    a.emit('LDA','imm',0)
    a.emit('STA','abs','Elapsed')
    a.label('Read')
    a.emit('LDY','imm',0)
    a.emit('LDA','indY',8)
    a.emit('CMP','imm',255)
    a.emit('BNE','rel','NotEnd')
    a.emit('JMP','abs','FinishRow')
    a.label('NotEnd')
    a.emit('STA','abs','Target')
    a.emit('SEC')
    a.emit('SBC','abs','Elapsed')
    a.emit('TAX')
    a.label('WaitTick')
    a.emit('CPX','imm',0)
    a.emit('BEQ','rel','DoEvent')
    a.emit('JSR','abs',0x2210)  # original WaitOneFrame
    a.emit('DEX')
    a.emit('JMP','abs','WaitTick')
    a.label('DoEvent')
    a.emit('LDA','abs','Target')
    a.emit('STA','abs','Elapsed')
    a.emit('LDY','imm',1)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('AND','imm',3)
    a.emit('TAX')
    a.emit('PLA')
    a.emit('AND','imm',0x30)
    a.emit('CMP','imm',0x20)
    a.emit('BEQ','rel','Retrigger')
    a.emit('CMP','imm',0x10)
    a.emit('BEQ','rel','Volume')
    # pitch event: DOC oscillator $00-03 low, $20-23 high
    a.emit('LDY','imm',2)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('TXA')
    a.emit('TAY')
    a.emit('PLA')
    a.emit('JSR','abs',0x20BA)
    a.emit('LDY','imm',3)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('TXA')
    a.emit('CLC')
    a.emit('ADC','imm',0x20)
    a.emit('TAY')
    a.emit('PLA')
    a.emit('JSR','abs',0x20BA)
    a.emit('JMP','abs','Advance')
    a.label('Retrigger')
    a.emit('LDY','imm',2)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('TXA')
    a.emit('CLC')
    a.emit('ADC','imm',0xA0)
    a.emit('TAY')
    a.emit('PLA')
    a.emit('ORA','imm',1)
    a.emit('JSR','abs',0x20BA)
    a.emit('LDY','imm',2)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('TXA')
    a.emit('CLC')
    a.emit('ADC','imm',0xA0)
    a.emit('TAY')
    a.emit('PLA')
    a.emit('AND','imm',0xFE)
    a.emit('JSR','abs',0x20BA)
    a.emit('JMP','abs','Advance')
    a.label('Volume')
    a.emit('LDY','imm',2)
    a.emit('LDA','indY',8)
    a.emit('PHA')
    a.emit('TXA')
    a.emit('CLC')
    a.emit('ADC','imm',0x40)
    a.emit('TAY')
    a.emit('PLA')
    a.emit('JSR','abs',0x20BA)
    a.label('Advance')
    a.emit('CLC')
    a.emit('LDA','zp',8)
    a.emit('ADC','imm',4)
    a.emit('STA','zp',8)
    a.emit('BCC','rel','PtrReady')
    a.emit('INC','zp',9)
    a.label('PtrReady')
    a.emit('JMP','abs','Read')
    a.label('FinishRow')
    a.emit('INC','zp',8)
    a.emit('BNE','rel','WaitRest')
    a.emit('INC','zp',9)
    a.label('WaitRest')
    a.emit('LDA','abs',0x228C)  # P0 FrameCount
    a.emit('SEC')
    a.emit('SBC','abs','Elapsed')
    a.emit('STA','abs',0x228C)
    a.emit('JSR','abs',0x2204)  # original WaitFrames
    a.emit('RTS')
    a.label('Elapsed')
    a.b.append(0)
    a.label('Target')
    a.b.append(0)
    return a.finish()


@dataclass
class Chan:
    inst:int=0
    vol:int=64
    period:float=0
    active:bool=False
    target:float=0
    porta:int=0
    slide_up:int=0
    slide_dn:int=0
    vib_speed:int=0
    vib_depth:int=0
    vib_phase:int=0
    vol_slide:int=0
    last_pitch:int=0
    last_doc_vol:int=0
    ctrl:int=0


def to_fc(period):
    return pitch_to_fc(max(1,int(round(period))))

def clamp_per(period):
    return max(113,min(1712,period))


def preprocess(mod:bytes, *, max_orders=None):
    orders, patterns, samples=read_mod(mod)
    if max_orders is not None:
        if not 1<=max_orders<=len(orders):raise ModError('Invalid --orders')
        orders=orders[:max_orders]
    played=flatten_orders(orders,patterns)
    used={inst for _,_,_,notes in played for inst,p,fx,arg in notes if inst and p}
    bank,catalog=make_waves(samples,used)
    channels=[Chan() for _ in range(4)]
    speed,bpm=6,125
    frame_accum=Fraction(0,1)
    song=bytearray(); effects=bytearray(); counts=Counter()
    for oi,pat,row,notes in played:
        cur_frac=frame_accum
        # Effects are applied at row tick 0; track 4-channel registers that
        # remain in effect when the underlying row contains no new note.
        active=[]; ordered=[]
        for ch,(inst,period,fx,arg) in enumerate(notes):
            v=channels[ch]
            if inst:
                v.inst=inst
                v.vol=samples[inst-1].volume
            if fx==0xF:
                if not arg:raise ModError('F00 stop unsupported')
                if arg<=31:speed=arg
                else:bpm=arg
            elif fx==0xC:
                v.vol=min(64,arg)
            elif fx==0x1:
                if arg:v.slide_up=arg
            elif fx==0x2:
                if arg:v.slide_dn=arg
            elif fx in (0x3,0x5):
                if fx==0x3 and arg:v.porta=arg
                if period:v.target=float(period)
            elif fx in (0x4,0x6):
                if fx==0x4:
                    if arg>>4:v.vib_speed=arg>>4
                    if arg&15:v.vib_depth=arg&15
            elif fx in (0x5,0x6,0xA):
                if arg:v.vol_slide=arg
            elif fx==0xE:
                ext,extarg=arg>>4,arg&15
                if ext in (0x1,0x2):
                    if v.active:
                        v.period=clamp_per(v.period + (-extarg if ext==1 else extarg))
                elif ext in (0x6,0x9,0xC):pass
                else:raise ModError(f'Unsupported E{arg:02X} at order {oi} row {row}')
            elif fx in (0x0,0xB,0xD):pass
            else:raise ModError(f'Unsupported effect {fx:X}{arg:02X} at order {oi} row {row}')
            if fx in (5,6) and arg:v.vol_slide=arg
            # If 3xx/5xx specify a target on an active voice, do not
            # retrigger the target note; pitch slides from existing period.
            retrigger=bool(period and (fx not in (3,5) or not v.active))
            if retrigger:
                v.period=float(period)
                v.active=True
                v.vib_phase=0
            fc=wtp=rts=docvol=ctrl=flags=0
            if retrigger:
                if v.inst not in catalog:raise ModError(f'Missing instrument {v.inst} at {oi}:{row}:{ch}')
                wtp,rts,mode,_=catalog[v.inst]
                fc=to_fc(v.period); docvol=min(192,v.vol*3)
                ctrl=(0x10 if ch in (1,2) else 0)|mode
                flags=1
                v.last_pitch=fc
                v.last_doc_vol=docvol
                v.ctrl=ctrl
            elif fx==0xC and not arg:
                flags=2
                v.last_doc_vol=0
            song.extend(b'') if False else None
            ordered.extend((fc&255,fc>>8,wtp,rts,docvol,ctrl,flags))
            active.append((fx,arg,retrigger))
            if fx or arg:counts[f'{fx:X}']+=1
        # Global frame carry must match the original P0/P1A row timing.
        frame_accum+=Fraction(150*speed,bpm)
        total=frame_accum.numerator//frame_accum.denominator
        frame_accum-=total
        duration=max(1,min(255,total))
        song.append(duration); song.extend(ordered)
        tick_events=[]
        for ch, (fx,arg,retrigger) in enumerate(active):
            v=channels[ch]
            def set_pitch(tick,cur_period):
                value=to_fc(clamp_per(cur_period))
                if value!=v.last_pitch:
                    v.last_pitch=value
                    tick_events.append((tick,0x00|ch,value&255,value>>8))
            def set_vol(tick,val):
                value=max(0,min(192,int(val)*3))
                if value!=v.last_doc_vol:
                    v.last_doc_vol=value
                    tick_events.append((tick,0x10|ch,value,0))
            # Cxx, E1x/E2x, or a previous row's altered pitch/volume
            # must take effect even when P0 gets no new note trigger.
            if v.active:
                if not retrigger:
                    set_pitch(0,v.period)
                    set_vol(0,v.vol if not (fx==0xE and arg>>4==0xC and (arg&15)==0) else 0)
            for tick in range(1,speed):
                if not v.active:continue
                if fx==0 and arg:
                    n = 0 if tick%3==0 else (arg>>4 if tick%3==1 else (arg&15))
                    set_pitch(tick,v.period * 2**(-n/12))
                elif fx==1:
                    v.period=clamp_per(v.period-v.slide_up)
                    set_pitch(tick,v.period)
                elif fx==2:
                    v.period=clamp_per(v.period+v.slide_dn)
                    set_pitch(tick,v.period)
                elif fx in (3,5):
                    if v.target:
                        step=v.porta
                        if step:
                            if v.period<v.target:v.period=min(v.target,v.period+step)
                            else:v.period=max(v.target,v.period-step)
                        set_pitch(tick,v.period)
                elif fx in (4,6):
                    d=(sin(v.vib_phase*2*pi/64)*v.vib_depth*2.0)
                    set_pitch(tick,v.period+d)
                    v.vib_phase=(v.vib_phase+v.vib_speed)%64
                if fx in (5,6,0xA):
                    up,down=(v.vol_slide>>4),v.vol_slide&15
                    v.vol=max(0,min(64,v.vol+(up if up else -down)))
                    set_vol(tick,v.vol)
                if fx==0xE and (arg>>4)==0xC and tick==(arg&15):
                    set_vol(tick,0)
                if fx==0xE and (arg>>4)==0x9 and (arg&15) and tick%(arg&15)==0:
                    tick_events.append((tick,0x20|ch,v.ctrl,0))
        # Restore base pitch on row entry if previous row ended on an
        # arpeggio/vibrato offset but this row starts at the nominal note.
        # Tick 0 is after PlayRow, therefore emitted updates do not retrigger.
        for ch,(fx,arg,retrigger) in enumerate(active):
            v=channels[ch]
            if v.active and not retrigger and fx not in (4,6):
                expected=to_fc(v.period)
                if expected!=v.last_pitch and not any(t==0 and op==ch for t,op,_,_ in tick_events):
                    tick_events.append((0,ch,expected&255,expected>>8));v.last_pitch=expected
        ticks=[]
        for t,op,lo,hi in sorted(tick_events,key=lambda e:e[0]):
            offset=(cur_frac+Fraction(150*t,bpm)).numerator//(cur_frac+Fraction(150*t,bpm)).denominator
            offset=min(offset,duration)
            if offset==255:raise ModError('Invalid FX sentinel offset')
            ticks.extend((offset,op,lo,hi))
        effects.extend(ticks);effects.append(0xFF)
    return bank,bytes(song),bytes(effects),played,counts


def build_sys(p0:bytes, rows:bytes, bank:bytes, fx:bytes):
    if len(p0)!=3544 or sha256(p0).hexdigest()!=P0_SHA256:raise ModError('P0 binary SHA mismatch')
    if not rows or len(rows)%29:raise ModError('Malformed row stream')
    assert p0[0x2C:0x2F]==bytes.fromhex('20 33 21')
    assert p0[0x3A:0x3D]==bytes.fromhex('20 04 22')
    base=bytearray(p0[:ENGINE_BYTES]);pos=base.find(BANK_LOAD_OPERANDS)
    if pos<0 or base.find(BANK_LOAD_OPERANDS,pos+1)>=0:raise ModError('P0 sample pointer not unique')
    bank_addr=LOAD_ADDR+ROWS_OFFSET+len(rows)
    fx_addr=bank_addr+len(bank)
    # ProDOS QUIT stub remains at the end of application code.
    # The effect routines live BEFORE the quit stub. No 6502 relocations.
    runtime,labels=make_fx_runtime(fx_addr+len(fx),fx_addr)
    stub_addr=fx_addr+len(fx)+len(runtime)
    code=base+struct.pack('<HH',len(rows)//29,len(bank))+rows+bank+fx+runtime
    code[0:3]=bytes((0x4C,stub_addr&255,stub_addr>>8))
    code[0x2D:0x2F]=struct.pack('<H',labels['FxPrep'])
    code[0x3B:0x3D]=struct.pack('<H',labels['FxWait'])
    code[pos+1]=bank_addr&255;code[pos+5]=bank_addr>>8
    stub=bytearray(STUB_QUIT)
    stub+=struct.pack('<H',stub_addr+len(STUB_QUIT)+4)
    stub+=bytes.fromhex('00 00 04 00 00 00 00 00 00')
    assert len(stub)==24
    code.extend(stub)
    if LOAD_ADDR+len(code)>SAFE_END:
        raise ModError(f'P1C memory overflow: {len(code)} bytes; ends ${LOAD_ADDR+len(code)-1:04X} >= $9000')
    return bytes(code),labels


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mod',type=Path)
    p.add_argument('--orders',type=int,help='Precompile first N orders only, for memory-limited hardware test')
    p.add_argument('--p0',type=Path,default=ROOT/'dist/SENSEI8-P0.BIN')
    p.add_argument('--out',type=Path,default=ROOT/'SENSEI8-P1C.SYSTEM')
    p.add_argument('--analyze',action='store_true')
    args=p.parse_args()
    bank,rows,fx,trace,counts=preprocess(args.mod.read_bytes(),max_orders=args.orders)
    print('Rows:',len(trace),'DOC bytes:',len(bank),'events:',len(rows),'FX bytes:',len(fx),'effects:',dict(counts))
    image,labels=build_sys(args.p0.read_bytes(),rows,bank,fx)
    print('SYS bytes:',len(image),'end:',hex(LOAD_ADDR+len(image)-1),'duration:',round(sum(rows[::29])/60,2),'s')
    if not args.analyze:
        args.out.write_bytes(image)
        print('PASS:',args.out,'SHA256',sha256(image).hexdigest())
    else:print('PASS: fits P1C, no file written')
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,ModError) as exc:sys.exit('ERROR: '+str(exc))