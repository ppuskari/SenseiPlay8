#!/usr/bin/env python3
"""Generate an original two-pattern MOD that exercises SenseiPlay8 P1C FX."""
from pathlib import Path
from make_p1_demo_mod import make as make_original

ROOT=Path(__file__).resolve().parents[1]

def build():
    original=make_original()
    song=bytearray(1084+2*1024)
    song[:1084]=original[:1084]
    song[:20]=b'SENSEI8 FX SHOWCASE'[:20].ljust(20,b' ')
    song[950]=2
    song[951]=127
    song[952:954]=bytes((0,1))
    song[1080:1084]=b'M.K.'
    def cell(pat,row,ch,inst=0,per=0,fx=0,arg=0):
        i=1084+1024*pat+16*row+4*ch
        song[i]=(inst&0xF0)|((per>>8)&15)
        song[i+1]=per&255
        song[i+2]=((inst&15)<<4)|(fx&15)
        song[i+3]=arg&255
    for pat in range(2):
        for row in range(64):
            if row in (0,12,24,32,48,56):
                chord=[428,571,856,214] if pat==0 else [381,508,762,226]
                for ch,per in enumerate(chord):cell(pat,row,ch,ch+1,per)
            if row<8:
                cell(pat,row,0,1 if row==0 else 0,428 if row==0 else 0,0,0x37)
            elif row<16:
                cell(pat,row,0,1 if row==12 else 0,381 if row==12 else 0,1,0x03 if row==8 else 0)
            elif row<24:
                cell(pat,row,0,1 if row==16 else 0,339 if row==16 else 0,2,0x03 if row==16 else 0)
            elif row<32:
                cell(pat,row,0,1 if row==24 else 0,214 if row==24 else 0,3,0x18 if row==24 else 0)
            elif row<40:
                cell(pat,row,0,1 if row==32 else 0,320 if row==32 else 0,4,0x84 if row==32 else 0)
            elif row<48:
                cell(pat,row,0,0,0,6,0x03 if row==40 else 0)
            elif row<56:
                cell(pat,row,0,1 if row==48 else 0,285 if row==48 else 0,5,0x03 if row==48 else 0)
            else:
                cell(pat,row,0,1 if row==56 else 0,428 if row==56 else 0,0xA,0x05 if row==56 else 0)
            if row in (20,36,44,52):
                cell(pat,row,1,2,453 if (row%16)==4 else 508,0,0)
            if row==40:cell(pat,row,2,3,678,0xC,0x30)
            if row==43:cell(pat,row,2,0,0,0xE,0xC3)
            if row==44:cell(pat,row,2,3,856,0,0)
            if row==50:cell(pat,row,3,4,254,0xE,0x93)
            if row==51:cell(pat,row,3,0,0,0xE,0x94)
            if row==62:cell(pat,row,3,4,320,0,0)
    return bytes(song)+original[-1024:]

if __name__=="__main__":
    out=ROOT/"assets/sensei8-p1c-effects-demo.mod"
    out.parent.mkdir(parents=True,exist_ok=True)
    content=build()
    out.write_bytes(content)
    print("PASS: original effects MOD",out,len(content),"bytes")
