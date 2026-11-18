#!/usr/bin/env python3
"""Build ONE generic Apple IIe SenseiPlay8 P2 ProDOS SYS controller.

No MOD samples, patterns, songs, or precomputed effect data are embedded.
The BL616 USB/SD OSD menu provides the first release's runtime folder
picker; the 6502 program is the permanent launcher / ESC-to-STOP client.
Requires Enhanced native DOC in Slot 4 and paired P2 MCU + FPGA firmware.

This is 6502 code, not 65C02/65816-only. No Apple IIe RAM expansion needed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib
import struct

from p1c_effects import Asm, OP

ROOT=Path(__file__).resolve().parents[1]
OP[('DEY','imp')]=0x88
OP[('CLD','imp')]=0xD8


def build() -> bytes:
    a=Asm(0x2000)
    a.emit('CLD')
    a.emit('JSR','abs',0xFC58)  # Apple monitor HOME
    a.emit('LDA','abs',0xC051) # set TEXT mode
    a.emit('LDA','abs',0xC054) # PAGE1
    a.emit('LDA','abs',0xC010) # clear keyboard strobe
    a.emit('LDA','abs',0xC0CA) # P1D/P2 mailbox 'S'
    a.emit('CMP','imm',0x53)
    a.emit('BEQ','rel','CheckProtocol')
    a.emit('JMP','abs','NoBridge')
    a.label('CheckProtocol')
    a.emit('LDA','abs',0xC0CB)
    a.emit('CMP','imm',0x1D)
    a.emit('BEQ','rel','Ready')
    a.emit('JMP','abs','NoBridge')
    a.label('Ready')

    def line(msg: str) -> None:
        for ch in msg+'\r':
            c=ord(ch)
            if not 0<=c<=127:raise ValueError('ASCII only')
            a.emit('LDA','imm',c|0x80)
            a.emit('JSR','abs',0xFDED) # Apple monitor COUT

    line('SENSEIPLAY8 - P2 RUNTIME MOD')
    line('APPLE IIE + A2FPGA ENHANCED')
    line(' ')
    line('PRESS TAB ON HDMI USB KEYBOARD.')
    line('OPEN MAIN MENU / MOD LIBRARY.')
    line('BROWSE USB/SD FOLDERS FOR .MOD.')
    line('SELECT SONG TO PLAY VIA ENSONIQ.')
    line('USE MOD LIBRARY TO STOP/RESELECT.')
    line(' ')
    line('PRESS ESC HERE TO EXIT.')
    # Song ID3 means generic runtime client; song loading belongs to
    # the MCU's UI and FatFS file broker, never to a compiled-in SYS.
    a.emit('LDA','imm',3)
    a.emit('STA','abs',0xC0CD)
    a.emit('LDA','imm',1)
    a.emit('STA','abs',0xC0CC)
    a.label('PollKeyboard')
    a.emit('LDA','abs',0xC000)
    a.emit('CMP','imm',0x9B) # ESC high-bit keycode
    a.emit('BEQ','rel','Exit')
    a.emit('JMP','abs','PollKeyboard')
    a.label('Exit')
    a.emit('LDA','abs',0xC010)
    a.emit('LDA','imm',2)
    a.emit('STA','abs',0xC0CC)
    # Bounded wait for MCU to mute/release DOC; no unbounded STOP hang.
    a.emit('LDY','imm',255)
    a.label('StopOuter')
    a.emit('LDX','imm',255)
    a.label('StopInner')
    a.emit('LDA','abs',0xC0CC)
    a.emit('CMP','imm',0)
    a.emit('BEQ','rel','Quit')
    a.emit('CMP','imm',3)
    a.emit('BEQ','rel','Quit')
    a.emit('CMP','imm',4)
    a.emit('BEQ','rel','Quit')
    a.emit('DEX')
    a.emit('BNE','rel','StopInner')
    a.emit('DEY')
    a.emit('BNE','rel','StopOuter')
    a.emit('LDA','imm',0xA5)
    a.emit('STA','abs',0xC0CF) # hardware forced DOC release
    a.emit('JMP','abs','Quit')
    a.label('NoBridge')
    line('P2 TRACKER FPGA MAILBOX NOT FOUND.')
    line('SELECT NATIVE DOC IN SLOT 4.')
    a.label('Quit')
    a.emit('INC','abs',0x03F4) # invalidate warm reset vector like P0
    a.emit('JSR','abs',0xBF00) # ProDOS MLI QUIT
    # Apple's MLI request is inline after the JSR.
    a.b.append(0x65)
    idx=len(a.b)
    a.b.extend(b'\x00\x00')
    a.b.extend(b'\x00\x00')    # original P0 ProDOS stub padding
    param=0x2000+len(a.b)
    a.b.extend(b'\x04'+b'\x00'*6)
    a.b[idx:idx+2]=struct.pack('<H',param)
    code,_=a.finish()
    if len(code)>0x7000:raise ValueError('Too large for ProDOS SYS')
    return code


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'dist/SENSEI8-P2.SYSTEM')
    args=p.parse_args()
    exe=build()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(exe)
    print('PASS: generic 6502 ProDOS SYS',len(exe),'bytes, load address $2000')
    print('SHA256',hashlib.sha256(exe).hexdigest())
    print('No song-specific samples/patterns included; requires P2 MCU+FPGA')


if __name__=='__main__':
    main()
