#!/usr/bin/env python3
"""Generic SenseiPlay8 P2 6502/ProDOS runtime client structure test.

No MOD music or sample banks embedded: the new BL616 firmware loads files
from USB/SD FAT at runtime. The first release uses its existing OSD picker.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from make_p2_runtime_sys import build

def run():
    image=build()
    assert 0<len(image)<2500,len(image)
    assert image[:4]==bytes.fromhex('D8 20 58 FC')
    assert bytes.fromhex('AD CA C0 C9 53') in image
    assert bytes.fromhex('AD CB C0 C9 1D') in image
    assert bytes.fromhex('A9 03 8D CD C0 A9 01 8D CC C0') in image
    assert bytes.fromhex('A9 02 8D CC C0') in image
    assert bytes.fromhex('A9 A5 8D CF C0') in image
    assert bytes.fromhex('20 00 BF 65') in image
    idx=image.index(bytes.fromhex('20 00 BF 65'))
    ptr=image[idx+4]|(image[idx+5]<<8)
    assert ptr==0x2000+idx+8,hex(ptr)
    assert image[ptr-0x2000]==4
    # The legacy P0 sample bank of 1,024 DOC bytes is absent.
    assert b'SENSEI8 P0 - FOUR CHANNEL DOC' not in image
    assert b'SELECT SONG' not in image # COUT immediate instructions, not data
    print('PASS P2: 6502 generic ProDOS launcher, no music/precomputed samples')
    print('PASS P2: runtime library selection and bounded ESC/STOP/MLI exit')
    print('Image length',len(image))

if __name__=='__main__':
    run()
