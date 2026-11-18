#!/usr/bin/env python3
"""P1E regression on original synthetic MOD assets only; no third-party PCM."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from make_p1_demo_mod import make
from make_p1e_dual import native_sys, generate_header, convert_song
from p1_build import P0_HASH
from s8asm import assemble
from test_p1d import LinkedIIe
from hashlib import sha256
import tempfile

def run():
    origin,p0,syms=assemble(ROOT/'src/sensei8.s')
    assert origin==0x2000 and sha256(p0).hexdigest()==P0_HASH
    with tempfile.TemporaryDirectory() as name:
        file=Path(name)/'demo.mod'
        file.write_bytes(make())
        bank,catalog,rows,nrows=convert_song(file)
        assert len(bank)==1024 and len(catalog)==4 and nrows==192
        assert len(rows)==16*nrows
        song_data=[]
        for song_id,label in ((1,'SENSEI8 P1E SYNTH TEST A'),
                              (2,'SENSEI8 P1E SYNTH TEST B')):
            img=native_sys(p0,syms,bank,song_id,label)
            assert img[0]==0x4C and len(img)<0x3000
            assert int.from_bytes(img[1:3],'little')==0x2000+len(img)-24
            assert img[0x298:0x298+len(bank)]==bank
            raw=bytearray(img[:-24])
            raw[:3]=p0[:3]
            sim=LinkedIIe(raw,bridge=True)
            sim.run(limit=600000)
            assert sim.upload_count==len(bank)
            assert sim.song_arg==song_id
            assert sim.commands==[1]
            assert len(sim.run_events)==0, 'CPU must not sequence DOC notes'
            song_data.append(('boogie' if song_id==1 else 'waltz',bank,catalog,rows,nrows))
        local=generate_header(song_data)
        assert 'SENSEI_HAS_LOCAL_MODS' in local
        assert 'sensei_local_songs[2]' in local
        assert '192' in local
        print('PASS: two P1E ProDOS SYS images upload ROM, send correct song IDs, exit')
        print('PASS: 192-row synthetic MOD -> local-only BL616 tracker header')
if __name__=='__main__':
    run()
