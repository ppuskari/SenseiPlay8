#!/usr/bin/env python3
"""Restore exact original SenseiPlay8 P0 binaries from a Git binary patch.

This intentionally avoids "git apply": Git for Windows may check out the
archive patch with CRLF endings, which breaks Git's binary-patch parser.

Usage: py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
"""
from __future__ import annotations

import argparse
import base64
import json
from hashlib import sha256
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "src/sensei8.s",
    "src/module_data.s",
    "tools/mod_to_s8m.py",
    "tools/make_demo_mod.py",
    "tools/s8asm.py",
    "tests/test_player.py",
)
ASSETS = {
    "assets/sensei8-original-demo.mod": "assets/sensei8-original-demo.mod",
    "build/SENSEI8.BIN": "dist/SENSEI8-P0.BIN",
}
PREFIX = "apps/senseiplay-iie/"


def checked(data: bytes, path: str, manifest: dict) -> None:
    record = manifest[path]
    if len(data) != record["size"] or sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"Checksum/size mismatch for {path}")


def decode_git_binary_patch(lines: list[str], source_path: str) -> bytes:
    """Decode a Git literal patch: per-line length + Git base85 + zlib."""
    header = (
        f"diff --git a/{PREFIX}{source_path} "
        f"b/{PREFIX}{source_path}"
    )
    try:
        i = lines.index(header) + 1
    except ValueError as exc:
        raise ValueError(f"Patch entry missing: {source_path}") from exc
    while i < len(lines) and lines[i] != "GIT binary patch":
        if lines[i].startswith("diff --git "):
            raise ValueError(f"No Git binary patch for {source_path}")
        i += 1
    if i + 1 >= len(lines) or not lines[i + 1].startswith("literal "):
        raise ValueError(f"Missing literal section: {source_path}")

    expected = int(lines[i + 1].split()[1])
    i += 2
    packed = bytearray()
    while i < len(lines) and lines[i]:
        line = lines[i]
        tag = line[0]
        if "A" <= tag <= "Z":
            length = ord(tag) - ord("A") + 1
        elif "a" <= tag <= "z":
            length = ord(tag) - ord("a") + 27
        else:
            raise ValueError(f"Bad Git base85 length prefix in {source_path}")
        encoded = line[1:]
        if len(encoded) != 5 * ((length + 3) // 4):
            raise ValueError(f"Bad base85 payload length in {source_path}")
        packed.extend(base64.b85decode(encoded.encode("ascii"))[:length])
        i += 1

    result = zlib.decompress(packed)
    if len(result) != expected:
        raise ValueError(
            f"Decompressed {source_path} is {len(result)} bytes, "
            f"expected {expected}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", type=Path)
    args = parser.parse_args()
    patch_path = args.patch.expanduser().resolve()
    if not patch_path.is_file():
        raise ValueError(f"Patch missing: {patch_path}")
    manifest_path = ROOT / "recovery/original-P0-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Git for Windows may check out text sources as CRLF; compare canonical LF.
    for name in SOURCES:
        data = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        original = manifest[name]
        if len(data) != original["size"] or sha256(data).hexdigest() != original["sha256"]:
            print(f"NOTE: {name} differs from archived P0; "
                  "maintained source may have evolved")

    # Universal newline handling safely accepts CRLF and LF archive checkouts.
    lines = patch_path.read_text(encoding="ascii").splitlines()
    recovered = {}
    for original_name, output_name in ASSETS.items():
        raw = decode_git_binary_patch(lines, original_name)
        checked(raw, original_name, manifest)
        recovered[output_name] = raw

    # Publish only after *all* checks pass.
    for name, raw in recovered.items():
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        print(f"Recovered {name}: {len(raw)} bytes "
              f"(SHA256 {sha256(raw).hexdigest()[:12]}...)")
    print("PASS: P0 sources verified; original MOD and binary restored")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, zlib.error) as exc:
        sys.exit(f"ERROR: {exc}")
