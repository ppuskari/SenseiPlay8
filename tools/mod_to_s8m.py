#!/usr/bin/env python3
"""Convert a 4-channel ProTracker MOD into Sensei8 P0 Merlin `module_data.s`.

This is a *preload-only* first-listening conversion, NOT an implementation of
NinjaTrackerPlus .NTP format. The original SenseiPlay uses an external 65816
NTP player and cannot run on a 65C02. The first milestone is to prove direct
DOC-native sample loading and 4-channel note sequencing on a stock IIe.

Constraints: PAL 4ch/31 instruments; up to 255 unrolled rows, up to 28 KiB
combined sample+event data; uses DOC bank 0 only; fixed-instrument volumes,
Cxx cuts/level changes and Fxx speed/BPM; most tracker effects deferred.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from fractions import Fraction
import struct
import sys

PAL_CLOCK = 7_093_789.2  # Amiga PAL Paula, period -> sample rate
DOC_CLOCK = 894_886.25   # IIgs DOC master
DOC_OSCILLATORS = 32    # E1=$3E, core uses 0..31
DOC_SR = DOC_CLOCK / (DOC_OSCILLATORS + 2)
MAX_SAMPLE_BANK = 0xC000    # first 48 KiB of DOC bank 0
MAX_TOTAL_MODULE = 0x6200  # approx. $2000..$8FFF less engine and overhead
MAX_ROWS = 255

class ModError(ValueError):
    pass

@dataclass(frozen=True)
class Instrument:
    index: int
    name: str
    sample: bytes
    volume: int
    repeat_start: int
    repeat_length: int


def be16(data: bytes, off: int) -> int:
    return struct.unpack_from('>H', data, off)[0]


def read_mod(data: bytes):
    if len(data) < 1084:
        raise ModError('Truncated ProTracker MOD header')
    if data[1080:1084] not in (b'M.K.', b'M!K!', b'4CHN', b'FLT4'):
        raise ModError(f'Only 4-channel 31-instrument MODs (M.K./M!K!/4CHN/FLT4); got {data[1080:1084]!r}')
    song_len = data[950]
    if not 1 <= song_len <= 128:
        raise ModError(f'Invalid MOD order length {song_len}')
    orders = tuple(data[952:952+song_len])
    if any(p >= 128 for p in orders):
        raise ModError('Pattern index outside 0..127')
    num_patterns = max(orders) + 1
    end_patterns = 1084 + 1024 * num_patterns
    if end_patterns > len(data):
        raise ModError('Truncated pattern data')
    samples = []
    pos = end_patterns
    for i in range(31):
        off = 20 + 30*i
        name = data[off:off+22].split(b'\0', 1)[0].decode('latin-1', 'replace').strip()
        length = be16(data, off+22)*2
        volume = data[off+25]
        repeat_start = be16(data, off+26)*2
        repeat_length = be16(data, off+28)*2
        if volume > 64:
            raise ModError(f'Instrument {i+1} has illegal volume {volume}')
        if pos+length > len(data):
            raise ModError(f'Truncated sample data for instrument {i+1}')
        raw = data[pos:pos+length]
        pos += length
        samples.append(Instrument(i+1, name, raw, volume, repeat_start, repeat_length))
    return orders, data[1084:end_patterns], samples


def next_pow2(n: int) -> int:
    return 1 << (n-1).bit_length()


def make_waves(samples: list[Instrument], used: set[int]):
    """WTP (page), RTS ((WTS<<3)|RES), DOC CTRL oneshot flag, vol."""
    bank = bytearray()
    catalog = {}
    for inst in samples:
        if inst.index not in used:
            continue
        if not inst.sample:
            raise ModError(f'Used instrument {inst.index} has empty PCM')
        # P0 makes a single DOC table per instrument. For looping MOD
        # samples select the loop sustain; full attack/sustain/swap needs P1.
        valid_loop = (inst.repeat_length >= 64 and
                      inst.repeat_start + inst.repeat_length <= len(inst.sample))
        chosen = (inst.sample[inst.repeat_start:inst.repeat_start+inst.repeat_length]
                  if valid_loop else inst.sample)
        if len(chosen) > 8192:
            raise ModError(f'Instrument {inst.index} sample {len(chosen)} > 8192; streaming/128K needed')
        size = min(8192, max(256, next_pow2(len(chosen))))
        if not valid_loop and len(chosen) == size:
            # Reserve last byte for 0 HALT, preserving first size-1 bytes.
            chosen = chosen[:-1]
        # All tables power-of-two aligned: DOC WTP lower WTS bits masked.
        padding = (-len(bank)) % size
        bank.extend([0x80]*padding)
        start = len(bank)
        wave = bytearray((b ^ 0x80) or 1 for b in chosen)
        wave.extend([0x80]*(size-len(wave)))
        if not valid_loop:
            wave[-1] = 0  # DOC one-shot HALT marker
        bank.extend(wave)
        if len(bank) > MAX_SAMPLE_BANK:
            raise ModError('DOC bank 0 overflow; choose smaller samples or P1 streaming')
        wts = (size.bit_length()-1)-8
        rts = (wts << 3) | wts  # WTS and RES both track sample length
        catalog[inst.index] = (start//256, rts, 0 if valid_loop else 2, inst.volume)
    return bytes(bank), catalog


def pitch_to_fc(period: int) -> int:
    if period <= 0:
        return 0
    sample_rate = PAL_CLOCK / (2.0 * period)
    return max(1, min(65535, round(sample_rate * 512.0 / DOC_SR)))


def decode_event(pattern: bytes, offset: int):
    a,b,c,d = pattern[offset:offset+4]
    inst = (a & 0xF0) | (c >> 4)
    period = ((a & 0x0F) << 8) | b
    effect = c & 0x0F
    return inst, period, effect, d


def convert(data: bytes, *, max_rows: int = MAX_ROWS):
    orders, patterns, samples = read_mod(data)
    # Only one explicit event per MOD row. Bxx/Dxx require order control,
    # and effects 0..A require per-tick updates not implemented by P0.
    used = set()
    for p in orders:
        for row in range(64):
            for ch in range(4):
                inst, period, _, _ = decode_event(patterns, p*1024 + row*16 + ch*4)
                if inst and period:
                    used.add(inst)
    sample_bank, catalog = make_waves(samples, used)
    speed = 6
    bpm = 125
    frame_accum = Fraction(0, 1)
    channel_instrument = [0]*4
    channel_volume = [64]*4
    stream = bytearray()
    warnings = set()
    for p in orders:
        for row in range(64):
            events = []
            for ch in range(4):
                inst, period, effect, param = decode_event(patterns, p*1024 + row*16 + ch*4)
                if inst:
                    channel_instrument[ch] = inst
                    channel_volume[ch] = samples[inst-1].volume
                if effect == 0x0F:
                    if param == 0:
                        warnings.add('F00 ignored (module end not implemented)')
                    elif param <= 31:
                        speed = param
                    else:
                        bpm = param
                elif effect == 0x0C:
                    channel_volume[ch] = min(64, param)
                elif effect or param:  # effect 0xy arpeggio counts too
                    warnings.add(f'Effect {effect:X}{param:02X} not supported in P0')
                fc = 0; wtp = 0; rts = 0; vol = 0; ctrl = 0; flags = 0
                if period:
                    n = channel_instrument[ch]
                    if n not in catalog:
                        raise ModError(f'Note at row {row}, channel {ch} has no loaded instrument')
                    wtp,rts,mode,_ = catalog[n]
                    fc = pitch_to_fc(period)
                    vol = min(192, channel_volume[ch]*3)
                    ctrl = (0x10 if ch in (1,2) else 0x00) | mode
                    flags = 1
                elif effect == 0x0C and param == 0:
                    flags = 2  # cut volume on existing oscillator
                elif effect == 0x0C and param:
                    warnings.add('Cxx volume without note deferred until P1')
                events.extend([fc&255,fc>>8,wtp,rts,vol,ctrl,flags])
            # ProTracker: speed ticks per row, each tick 2.5/BPM seconds.
            # Sample the row at NTSC 60 Hz by a fractional frame accumulator.
            frame_accum += Fraction(150 * speed, bpm)
            duration = frame_accum.numerator // frame_accum.denominator
            frame_accum -= duration
            duration = max(1,min(255,duration))
            stream.append(duration)
            stream.extend(events)
    nrows = len(stream)//29
    if nrows > max_rows:
        raise ModError(f'{nrows} rows exceed configured {max_rows}-row limit')
    if len(stream)+len(sample_bank) > MAX_TOTAL_MODULE:
        raise ModError(f'{len(stream)+len(sample_bank)}-byte payload exceeds P0 main-RAM limit {MAX_TOTAL_MODULE}')
    return sample_bank, bytes(stream), sorted(warnings), catalog


def merlin_hex(data: bytes) -> str:
    return ''.join('                hex   '+data[i:i+16].hex().upper()+'\n'
                   for i in range(0,len(data),16))


def emit(bank: bytes, rows: bytes):
    assert rows and len(rows)%29 == 0
    out = ['********************************************************************************',
           '* GENERATED by tools/mod_to_s8m.py, DO NOT EDIT BY HAND.',
           '* Copyright/source MOD samples remain local. Do not commit others\' PCM.',
           '********************************************************************************',
           f'SongRowCount    dw    {len(rows)//29}',
           f'SampleBankLen   dw    {len(bank)}',
           'SongRows', merlin_hex(rows).rstrip(),
           'SampleBank', merlin_hex(bank).rstrip(), '']
    return '\n'.join(out)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mod', type=Path)
    ap.add_argument('--out',type=Path,default=Path('src/module_data.s'))
    ns=ap.parse_args(argv)
    bank,rows,warnings,catalog=convert(ns.mod.read_bytes())
    ns.out.parent.mkdir(parents=True,exist_ok=True)
    ns.out.write_text(emit(bank,rows),encoding='ascii')
    print(f'S8M0 PASS: {len(rows)//29} rows, {len(catalog)} instruments, '+
          f'{len(bank)} DOC sample bytes, {len(rows)} event bytes')
    for warning in warnings[:12]:
        print('WARNING:',warning)
    print('Generated',ns.out)

if __name__ == '__main__':
    try: main()
    except (ModError, OSError) as e: sys.exit('ERROR: '+str(e))
