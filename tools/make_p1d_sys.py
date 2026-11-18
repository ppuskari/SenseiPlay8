#!/usr/bin/env python3
"""P1D ProDOS SYS: 6502 sample preload and MCU/FPGA tracker control.

P0 DOC upload code remains hardware-proven. BL616 computes subsequent
music effects at tick rate, FPGA schedules register writes. Native DOC only.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from p1_build import P0_HASH
from p1c_effects import Asm
from s8asm import assemble

ROOT=Path(__file__).resolve().parents[1]


def create(p0: bytes):
    origin, compiled, sym = assemble(ROOT / "src/sensei8.s")
    if origin != 0x2000 or sha256(p0).hexdigest() != P0_HASH or compiled != p0:
        raise ValueError("Frozen P0 source/binary mismatch")
    if sym["SampleBank"] != origin + len(p0) - 1024:
        raise ValueError("Unexpected P0 SampleBank location")
    player = bytearray(p0)
    # Compression must operate on the DOC-encoded bank (XOR 0x80 with
    # zero/HALT semantics), not on the unsigned MOD PCM host samples.
    for ch in range(4):
        begin = len(player) - 1024 + 256*ch
        cycle = bytes(player[begin:begin+256])
        if len(cycle) != 256 or 0 in cycle:
            raise ValueError("Unexpected P0 DOC waveform")
        player[begin:begin+256] = cycle[::8]*8
    if player[0x2C:0x2F] != bytes.fromhex("20 33 21"):
        raise ValueError("Unexpected original JSR PrepareSong callsite")
    controller_address = origin + len(player)
    a = Asm(controller_address)
    a.emit("LDA","abs",0xC0CA)
    a.emit("CMP","imm",0x53)
    a.emit("BNE","rel","NoBridge")
    a.emit("LDA","abs",0xC0CB)
    a.emit("CMP","imm",0x1D)
    a.emit("BNE","rel","NoBridge")
    a.emit("LDA","abs",0xC010)
    a.emit("LDA","imm",0)
    a.emit("STA","abs",0xC0CD)
    a.emit("LDA","imm",1)
    a.emit("STA","abs",0xC0CC)
    a.label("WaitStart")
    a.emit("LDA","abs",0xC0CC)
    a.emit("CMP","imm",2)
    a.emit("BEQ","rel","WaitPlay")
    a.emit("CMP","imm",4)
    a.emit("BEQ","rel","End")
    a.emit("LDA","abs",0xC000)
    a.emit("CMP","imm",0x80)
    a.emit("BCC","rel","WaitStart")
    a.emit("JMP","abs","RequestStop")
    a.label("WaitPlay")
    a.emit("LDA","abs",0xC0CC)
    a.emit("CMP","imm",3)
    a.emit("BEQ","rel","End")
    a.emit("CMP","imm",4)
    a.emit("BEQ","rel","End")
    a.emit("LDA","abs",0xC000)
    a.emit("CMP","imm",0x80)
    a.emit("BCC","rel","WaitPlay")
    a.label("RequestStop")
    a.emit("LDA","abs",0xC010)
    a.emit("LDA","imm",2)
    a.emit("STA","abs",0xC0CC)
    a.label("WaitStop")
    a.emit("LDA","abs",0xC0CC)
    a.emit("CMP","imm",0)
    a.emit("BNE","rel","WaitStop")
    a.label("End")
    a.emit("JSR","abs",sym["StopDOC"])
    a.label("NoBridge")
    a.emit("RTS")
    machine, labels = a.finish()
    player[0x2C:0x2F] = bytes((0x20, controller_address & 255, controller_address >> 8))
    finish = sym["Finish"]
    player[0x2F:0x32] = bytes((0x4C, finish & 255, finish >> 8))
    player.extend(machine)
    stub_addr = origin + len(player)
    stub = bytearray(bytes.fromhex("D8 A5 06 20 03 20 EE F4 03 20 00 BF 65"))
    paramaddr = stub_addr + len(stub) + 4
    stub += bytes((paramaddr & 255, paramaddr >> 8))
    stub += bytes.fromhex("00 00 04 00 00 00 00 00 00")
    assert len(stub) == 24
    player[:3] = bytes((0x4C, stub_addr & 255, stub_addr >> 8))
    player.extend(stub)
    if len(player) + origin >= 0x9000:
        raise ValueError("ProDOS load would overlap high memory")
    return bytes(player), labels


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p0",type=Path,default=ROOT/"dist/SENSEI8-P0.BIN")
    ap.add_argument("--out",type=Path,default=ROOT/"dist/SENSEI8-P1D.SYSTEM")
    args = ap.parse_args(argv)
    image, labels = create(args.p0.read_bytes())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(image)
    print("PASS: P1D ProDOS SYS",len(image),"bytes; end",hex(0x2000+len(image)-1))
    print("Mailbox C0CA..C0CF, 6502 wait loop:",hex(labels["WaitStart"]))
    print("SHA256:",sha256(image).hexdigest())
    print("Requires paired P1D BL616 and FPGA firmware")


if __name__ == "__main__":
    try: main()
    except (OSError,ValueError) as exc: sys.exit("ERROR: "+str(exc))
