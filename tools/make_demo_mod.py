#!/usr/bin/env python3
"""Generate a tiny ORIGINAL (not copyrighted) 4-channel ProTracker MOD test."""
from pathlib import Path
import struct
import argparse
from demo_waves import VOICE_SAMPLES

def make():
    song=bytearray(1084 + 1024)
    song[:20]=b'SENSEI8 FOUR-CHAN P0'
    waveforms=[]
    for i,name in enumerate(('SINE','TRIANGLE','PULSE','BELL')):
        off=20+i*30
        song[off:off+len(name)]=name.encode('ascii')
        waveforms.extend(VOICE_SAMPLES[i])
        song[off+22:off+24]=struct.pack('>H',128) # length 256
        song[off+25]=48 # volume
        song[off+26:off+28]=struct.pack('>H',0)
        song[off+28:off+30]=struct.pack('>H',128) # repeating loop 256
    song[950]=1 # 1 order
    song[951]=127
    song[952]=0
    song[1080:1084]=b'M.K.'
    notes=((428,381,339,320,285,254,226,214),
           (571,508,453,428,381,339,302,285),
           (856,762,678,640,570,508,453,428),
           (214,226,254,285,320,339,381,428))
    for row in range(64):
        for ch in range(4):
            if row % 4 != 0:
                continue
            period=notes[ch][(row//4)%8]
            sample=ch+1
            i=1084+row*16+ch*4
            song[i]=(sample&0xF0)|((period>>8)&0x0F)
            song[i+1]=period&0xff
            song[i+2]=(sample&0x0F)<<4
            song[i+3]=0
    return bytes(song)+bytes(waveforms)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,default=Path('assets/sensei8-original-demo.mod'))
    args=ap.parse_args()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(make())
    print('Generated',args.out,'bytes',args.out.stat().st_size)
