#!/usr/bin/env python3
"""Narrow, deterministic 6502 assembler for Sensei8 P0's Merlin-style subset.

Used for CI and to emit a ProDOS BLOAD binary without depending on Merlin32.
Not a general-purpose Merlin assembler. In particular, it does not accept
macros, 65816 opcodes, relocations, or banked addressing.
"""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import re
import sys

OPCODES = {
    'lda': {'imm':0xA9,'zp':0xA5,'zpx':0xB5,'abs':0xAD,'absx':0xBD,'absy':0xB9,'indy':0xB1},
    'sta': {'zp':0x85,'zpx':0x95,'abs':0x8D,'absx':0x9D,'absy':0x99,'indy':0x91},
    'stx': {'zp':0x86,'abs':0x8E},
    'sty': {'zp':0x84,'abs':0x8C},
    'ldx': {'imm':0xA2,'zp':0xA6,'abs':0xAE},
    'ldy': {'imm':0xA0,'zp':0xA4,'abs':0xAC},
    'cmp': {'imm':0xC9,'zp':0xC5,'abs':0xCD},
    'cpx': {'imm':0xE0,'zp':0xE4,'abs':0xEC},
    'adc': {'imm':0x69,'zp':0x65,'abs':0x6D},
    'and': {'imm':0x29,'zp':0x25,'abs':0x2D},
    'ora': {'imm':0x09,'zp':0x05,'abs':0x0D},
    'inc': {'zp':0xE6,'abs':0xEE},
    'dec': {'zp':0xC6,'abs':0xCE},
    'jsr': {'abs':0x20},
    'jmp': {'abs':0x4C},
    'beq': {'rel':0xF0},
    'bne': {'rel':0xD0},
    'bcc': {'rel':0x90},
    'bcs': {'rel':0xB0},
    'bpl': {'rel':0x10},
    'bmi': {'rel':0x30},
    'rts': {'imp':0x60},
    'clc': {'imp':0x18},
    'sec': {'imp':0x38},
    'cld': {'imp':0xD8},
    'pha': {'imp':0x48},
    'pla': {'imp':0x68},
    'inx': {'imp':0xE8},
    'dex': {'imp':0xCA},
    'iny': {'imp':0xC8},
    'txa': {'imp':0x8A},
    'tay': {'imp':0xA8},
    'tax': {'imp':0xAA},
}
DIRECTIVES={'org','typ','equ','db','dw','asc','hex','put'}
LABEL_RE=re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

class AssemblyError(ValueError):
    pass


def strip_comment(s: str) -> str:
    # We only emit a small subset where single quotes protect all ASC text.
    out=[]; quote=None
    for c in s:
        if c in "'\"":
            if quote is None: quote=c
            elif quote==c: quote=None
        if c==';' and quote is None: break
        out.append(c)
    return ''.join(out).rstrip()


def read_lines(root: Path):
    out=[]
    def read(path):
        for n,line in enumerate(path.read_text(encoding='ascii').splitlines(),1):
            if not line.strip() or line.lstrip().startswith('*'):
                continue
            line=strip_comment(line)
            if not line.strip(): continue
            parts=line.split(None, 2) if line[0] not in ' \t' else line.strip().split(None,1)
            if line[0] in ' \t':
                label=None; cmd=parts[0].lower(); arg=parts[1].strip() if len(parts)>1 else ''
            else:
                label=parts[0]
                if not LABEL_RE.fullmatch(label): raise AssemblyError(f'{path}:{n}: invalid label {label}')
                cmd=parts[1].lower() if len(parts)>1 else ''
                arg=parts[2].strip() if len(parts)>2 else ''
            if cmd=='put':
                inc=path.parent/(arg+'.s')
                if not inc.exists(): raise AssemblyError(f'Missing PUT include {inc}')
                read(inc)
            else: out.append((str(path),n,label,cmd,arg))
    read(root)
    return out


def expr(s: str, symbols: dict[str,int], allow_missing=False):
    s=s.strip()
    take=None
    if s and s[0] in '<>':
        take=s[0]; s=s[1:]
    m=re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*|\$[0-9a-fA-F]+|\d+)(?:([+\-])(\$[0-9a-fA-F]+|\d+))?',s)
    if not m: raise AssemblyError('Bad expression '+repr(s))
    t,op,num=m.groups()
    if t.startswith('$'): val=int(t[1:],16)
    elif t.isdigit(): val=int(t)
    elif t in symbols: val=symbols[t]
    elif allow_missing: val=0xFF00
    else: raise AssemblyError('Undefined label '+t)
    if op:
        z=int(num[1:],16) if num.startswith('$') else int(num)
        val=val+z if op=='+' else val-z
    if take=='<': return val&255
    if take=='>': return (val>>8)&255
    return val


def asc_bytes(arg: str):
    items=[]; cur=''; quote=None
    for c in arg:
        if c in "'\"":
            if quote is None: quote=c
            elif quote==c: quote=None
        if c==',' and quote is None:
            items.append(cur.strip()); cur=''
        else: cur+=c
    if cur.strip(): items.append(cur.strip())
    data=bytearray()
    for p in items:
        if p[0] in "'\"":
            v=ast.literal_eval(p)
            if not isinstance(v,str):raise AssemblyError('ASC literal required')
            data.extend(v.encode('ascii'))
        else:
            n=expr(p,{})
            if n>255: raise AssemblyError('ASC byte overflow')
            data.append(n)
    return bytes(data)


def mode_for(mnem, arg, symbols):
    supported=OPCODES[mnem]
    if not arg: mode='imp'; token=''
    elif arg.startswith('#'): mode='imm'; token=arg[1:]
    elif re.fullmatch(r'\([^)]*\),[Yy]',arg): mode='indy'; token=arg[1:-3]
    elif arg.lower().endswith(',x'):
        token=arg[:-2].strip(); mode='zpx' if expr(token,symbols,True)<=255 and 'zpx' in supported else 'absx'
    elif arg.lower().endswith(',y'):
        token=arg[:-2].strip(); mode='absy'
    elif 'rel' in supported: mode='rel'; token=arg
    else:
        token=arg
        v=expr(token,symbols,True)
        mode='zp' if v<=255 and 'zp' in supported else 'abs'
    if mode not in supported:
        raise AssemblyError(f'Unsupported addressing {mnem} {arg}, mode {mode}')
    return mode,token


def assemble(path: Path):
    lines=read_lines(path)
    sym={}
    origin=0x2000
    # 2 pass; fixed sizing. Forward labels use ABS (never forward zero-page).
    for pass_id in (0,1):
        pc=origin; body=bytearray()
        for fn,n,label,cmd,arg in lines:
            try:
                if label:
                    if cmd=='equ':
                        sym[label]=expr(arg,sym)
                        continue
                    if pass_id==0: sym[label]=pc
                    elif sym[label]!=pc: raise AssemblyError(f'Pass mismatch {label} {sym[label]:04X} != {pc:04X}')
                if not cmd: continue
                if cmd=='org':
                    pc=expr(arg,sym)
                    if pc!=origin: raise AssemblyError('Only fixed $2000 org allowed')
                    continue
                if cmd=='typ': continue
                if cmd in ('db','dw'):
                    count=1 if cmd=='db' else 2
                    val=expr(arg,sym,pass_id==0)
                    payload=bytes([val&255]) if count==1 else bytes([val&255,(val>>8)&255])
                elif cmd=='asc': payload=asc_bytes(arg)
                elif cmd=='hex':
                    digits=''.join(arg.split())
                    if len(digits)%2: raise AssemblyError('Odd-length HEX')
                    payload=bytes.fromhex(digits)
                else:
                    if cmd not in OPCODES: raise AssemblyError(f'Unknown opcode {cmd}')
                    mode,operand=mode_for(cmd,arg,sym)
                    op=OPCODES[cmd][mode]
                    if mode=='imp': payload=bytes([op])
                    elif mode=='rel':
                        off=expr(operand,sym,pass_id==0)-(pc+2)
                        if pass_id==1 and not -128<=off<=127:
                            raise AssemblyError(f'Branch out of range: {off:+d}')
                        payload=bytes([op,off&255])
                    elif mode in ('imm','zp','indy','zpx'):
                        v=expr(operand,sym,pass_id==0)
                        if pass_id==1 and not 0<=v<=255:
                            raise AssemblyError('8-bit operand overflow')
                        payload=bytes([op,v&255])
                    else:
                        v=expr(operand,sym,pass_id==0)
                        payload=bytes([op,v&255,(v>>8)&255])
                pc+=len(payload)
                if pass_id==1: body.extend(payload)
            except (ValueError,KeyError) as e:
                raise AssemblyError(f'{fn}:{n} {label or ""} {cmd} {arg}: {e}') from e
    return origin,bytes(body),sym


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path,nargs='?',default=Path('src/sensei8.s'))
    ap.add_argument('--out',type=Path,default=Path('build/SENSEI8.BIN'))
    a=ap.parse_args()
    origin,body,sym=assemble(a.source)
    if origin+len(body) > 0x9000:
        raise SystemExit(f'ERROR: binary ends at ${origin+len(body):04X}; P0 requires < $9000')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(body)
    print(f'PASS: Sensei8 6502 BIN ${origin:04X}-${origin+len(body)-1:04X} '+
          f'({len(body)} bytes); first byte ${body[0]:02X}; MODULE=${sym["SongRows"]:04X}')
    print('BLOAD under DOS 3.3 at $2000, CALL 8192. NOT ProDOS BASIC.SYSTEM!')

if __name__=='__main__':
    try: main()
    except (AssemblyError,OSError) as e: sys.exit('ERROR: '+str(e))
