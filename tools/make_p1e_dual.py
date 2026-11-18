#!/usr/bin/env python3
"""P1E dual real-MOD build for enhanced IIe + BL616 + FPGA.

Uses the *unmodified* P0 InitDOC/UploadSamples 6502 code. Each native
ProDOS SYS embeds only one MOD's DOC sample bank. All executed pattern
rows are stored in a locally generated C header for the BL616 real-time
tick interpreter. Bxx/Dxx/E6x pattern flow is flattened, effects are not.
Do NOT commit the generated source header or user-owned MOD samples.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import struct
from mod_to_s8m import read_mod, make_waves, ModError
from p1b_flow_build import trace_flow
from p1c_effects import Asm
from p1_build import P0_HASH, ENGINE_BYTES, ROWS_OFFSET, BANK_LOAD_OPERANDS
from s8asm import assemble

ROOT=Path(__file__).resolve().parents[1]
P0_TITLE=b'SENSEI8 P0 - FOUR CHANNEL DOC'
SUPPORTED={0,1,2,3,4,5,6,10,11,12,13,14,15}


def convert_song(path:Path):
    orders,patterns,samples=read_mod(path.read_bytes())
    played=trace_flow(orders,patterns)
    used={inst for _,_,_,notes in played for inst,per,fx,arg in notes
          if inst and per}
    bank,catalog=make_waves(samples,used)
    for order,pat,row,notes in played:
        for inst,per,fx,arg in notes:
            if fx not in SUPPORTED or (fx==14 and arg>>4 not in (6,9,12,13)):
                raise ModError(f'Unsupported {fx:X}{arg:02X} in {path.name} order {order} row {row}')
    # Preserve four original 4-byte ProTracker events for each visited row.
    rowdata=bytes(b for _,_,_,notes in played
                  for inst,per,fx,arg in notes
                  for b in ((inst&0xF0)|((per>>8)&15),per&255,
                            ((inst&15)<<4)|fx,arg))
    assert len(rowdata)==len(played)*16
    return bank,catalog,rowdata,len(played)


def controller(origin,song_id,syms):
    a=Asm(origin)
    a.emit('LDA','abs',0xC0CA);a.emit('CMP','imm',0x53);a.emit('BNE','rel','NoBridge')
    a.emit('LDA','abs',0xC0CB);a.emit('CMP','imm',0x1D);a.emit('BNE','rel','NoBridge')
    a.emit('LDA','abs',0xC010)
    a.emit('LDA','imm',song_id);a.emit('STA','abs',0xC0CD)
    a.emit('LDA','imm',1);a.emit('STA','abs',0xC0CC)
    a.emit('LDX','imm',180)
    a.label('WaitStart')
    a.emit('LDA','abs',0xC0CC);a.emit('CMP','imm',2);a.emit('BEQ','rel','WaitPlay')
    a.emit('CMP','imm',4);a.emit('BEQ','rel','Panic')
    a.emit('LDA','abs',0xC000);a.emit('CMP','imm',0x80);a.emit('BCC','rel','CheckStartTimeout')
    a.emit('JMP','abs','Panic')
    a.label('CheckStartTimeout')
    a.emit('JSR','abs',syms['WaitOneFrame']);a.emit('DEX');a.emit('BNE','rel','WaitStart')
    a.emit('JMP','abs','Panic')
    a.label('WaitPlay')
    a.emit('LDA','abs',0xC0CC);a.emit('CMP','imm',3);a.emit('BEQ','rel','End')
    a.emit('CMP','imm',4);a.emit('BEQ','rel','Panic')
    a.emit('LDA','abs',0xC000);a.emit('CMP','imm',0x80);a.emit('BCC','rel','WaitPlay')
    a.emit('LDA','abs',0xC010)
    a.emit('LDA','imm',2);a.emit('STA','abs',0xC0CC)
    a.emit('LDX','imm',180)
    a.label('WaitStop')
    a.emit('LDA','abs',0xC0CC);a.emit('CMP','imm',0);a.emit('BEQ','rel','End')
    a.emit('JSR','abs',syms['WaitOneFrame']);a.emit('DEX');a.emit('BNE','rel','WaitStop')
    a.label('Panic')
    a.emit('LDA','imm',0xA5);a.emit('STA','abs',0xC0CF)
    a.label('End');a.emit('JSR','abs',syms['StopDOC'])
    a.label('NoBridge');a.emit('RTS')
    return a.finish()[0]


def native_sys(p0,syms,bank,song_id,title):
    engine=bytearray(p0[:ENGINE_BYTES])
    if engine[0x2C:0x2F]!=bytes.fromhex('20 33 21'):
        raise ValueError('Original P0 callsite changed')
    if engine.count(P0_TITLE)!=1:
        raise ValueError('Original title changed')
    engine=bytearray(engine.replace(P0_TITLE,
                    title.encode('ascii')[:len(P0_TITLE)].ljust(len(P0_TITLE),b' ')))
    at=engine.find(BANK_LOAD_OPERANDS)
    if at<0 or engine.find(BANK_LOAD_OPERANDS,at+1)>=0:
        raise ValueError('Cannot uniquely patch P0 DOC sample pointer')
    sampleaddr=0x2000+ROWS_OFFSET
    engine[at+1]=sampleaddr&255;engine[at+5]=sampleaddr>>8
    trailer=controller(0x2000+ENGINE_BYTES+4+len(bank),song_id,syms)
    dest=0x2000+ENGINE_BYTES+4+len(bank)
    engine[0x2C:0x2F]=bytes((0x20,dest&255,dest>>8))
    finish=syms['Finish']
    engine[0x2F:0x32]=bytes((0x4C,finish&255,finish>>8))
    img=engine+struct.pack('<HH',0,len(bank))+bank+trailer
    stubaddr=0x2000+len(img)
    stub=bytearray(bytes.fromhex('D8 A5 06 20 03 20 EE F4 03 20 00 BF 65'))
    ptr=stubaddr+len(stub)+4
    stub+=struct.pack('<H',ptr)+bytes.fromhex('00 00 04 00 00 00 00 00 00')
    assert len(stub)==24
    img[:3]=bytes((0x4C,stubaddr&255,stubaddr>>8))
    img+=stub
    if 0x2000+len(img)>0x9000:raise ValueError('P1E ProDOS SYS too large')
    return bytes(img)


def hex_rows(data):
    return ',\n'.join('    '+','.join('0x%02X'%v for v in data[i:i+20])
                     for i in range(0,len(data),20))

def generate_header(songs):
    lines=['/* PRIVATE GENERATED P1E MOD DATA: NEVER COMMIT. */',
           '#ifndef SENSEI_P1E_LOCAL_MOD_DATA_H',
           '#define SENSEI_P1E_LOCAL_MOD_DATA_H',
           '#define SENSEI_HAS_LOCAL_MODS 1']
    for name,bank,catalog,rows,nrows in songs:
        cat=bytearray()
        for n in range(32):
            cat.extend(catalog.get(n,(0,0,0,0)))
        lines += [f'static const unsigned char sensei_rows_{name}[]={{',
                  hex_rows(rows),'};',
                  f'static const unsigned char sensei_catalog_{name}[128]={{',
                  hex_rows(cat),'};']
    lines += ['static const sensei_mod_song_t sensei_local_songs[2]={']
    for name,bank,catalog,rows,nrows in songs:
        lines.append(f'    {{sensei_rows_{name}, {nrows}, sensei_catalog_{name}}},')
    lines += ['};','#endif','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mod15k',type=Path,required=True)
    p.add_argument('--modwaltz',type=Path,required=True)
    p.add_argument('--p0',type=Path,default=ROOT/'dist/SENSEI8-P0.BIN')
    p.add_argument('--out-dir',type=Path,default=ROOT/'dist/p1e')
    p.add_argument('--mcu-dir',type=Path,required=True,
                   help='Existing a2fpga Enhanced firmware_host directory')
    opt=p.parse_args()
    raw=opt.p0.read_bytes()
    origin,p0,syms=assemble(ROOT/'src/sensei8.s')
    if origin!=0x2000 or p0!=raw or sha256(raw).hexdigest()!=P0_HASH:
        raise ValueError('Frozen P0 source/binary mismatch')
    songs=[]
    for name,file,id,title,exe in (
      ('boogie',opt.mod15k,1,'SENSEI8 P1E 15K BOOGIE','BOOGIE.SYSTEM'),
      ('waltz',opt.modwaltz,2,'SENSEI8 P1E DEAD WALTZ','WALTZ.SYSTEM')
    ):
        bank,catalog,rows,nrows=convert_song(file)
        img=native_sys(raw,syms,bank,id,title)
        opt.out_dir.mkdir(parents=True,exist_ok=True)
        dst=opt.out_dir/exe
        dst.write_bytes(img)
        songs.append((name,bank,catalog,rows,nrows))
        print(f'{name}: {nrows} rows, {len(catalog)} instruments, '
              f'{len(bank)} DOC sample bytes, SYS {len(img)} bytes')
        print('SYS:',dst,'SHA256',sha256(img).hexdigest())
    dest=opt.mcu_dir/'sensei_p1e_local_data.h'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(generate_header(songs),encoding='ascii')
    print('Local-only firmware song tables:',dest,'bytes',dest.stat().st_size)


if __name__=='__main__':
    main()
