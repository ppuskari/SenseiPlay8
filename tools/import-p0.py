#!/usr/bin/env python3
"""Recover exact P0 demo MOD and original executable from bundled Git binary patch.

Usage: python tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile

CHECK = (
    "src/sensei8.s", "src/module_data.s", "tools/mod_to_s8m.py",
    "tools/make_demo_mod.py", "tools/s8asm.py", "tests/test_player.py"
)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    patch = args.patch.expanduser().resolve()
    if not patch.is_file():
        raise SystemExit(f"Patch missing: {patch}")
    with tempfile.TemporaryDirectory(prefix="sensei8-import-") as d:
        work = Path(d)
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        subprocess.run(["git", "apply", "--binary", "-p3", str(patch)], cwd=work, check=True)
        for rel in CHECK:
            a, b = work/rel, root/rel
            if not b.exists() or sha256(a.read_bytes()).digest() != sha256(b.read_bytes()).digest():
                raise RuntimeError(f"Recovered text source mismatch: {rel}")
        paths = {
            "assets/sensei8-original-demo.mod": "assets/sensei8-original-demo.mod",
            "build/SENSEI8.BIN": "dist/SENSEI8-P0.BIN",
        }
        for src, dst in paths.items():
            out = root/dst
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((work/src).read_bytes())
            print(f"Recovered {dst}: {out.stat().st_size} bytes")
    print("PASS: text sources match recovered P0 and binary assets restored")

if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        sys.exit(f"ERROR: {exc}")
