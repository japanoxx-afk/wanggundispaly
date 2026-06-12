#!/usr/bin/env python3
"""Patch Taejo Wang Geon/WangGun.exe from 800x600 to a chosen resolution."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXE = Path("C:/Program Files/\ud0dc\uc870\uc655\uac74/WangGun.exe")
SUPPORTED_SHA256 = "5e80aad54982ddf8cafbb367b70e65b9438b093ade414f36b3959e9e8b08e5fe"


@dataclass(frozen=True)
class PatchPoint:
    offset: int
    original: int
    label: str


PATCH_POINTS = [
    PatchPoint(0x5030A, 800, "global screen width"),
    PatchPoint(0x50325, 600, "global screen height"),
    PatchPoint(0x50340, 449, "gameplay viewport height"),
    PatchPoint(0x532B9, 600, "CreateWindowEx height"),
    PatchPoint(0x532BE, 800, "CreateWindowEx width"),
    PatchPoint(0x53492, 600, "iCARUS_Init viewport height"),
    PatchPoint(0x53497, 800, "iCARUS_Init viewport width"),
    PatchPoint(0x5349E, 600, "iCARUS_Init surface height"),
    PatchPoint(0x534A3, 800, "iCARUS_Init surface width"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch WangGun.exe resolution constants. Creates WangGun.exe.bak before writing."
    )
    parser.add_argument("width", type=int, help="new width, for example 1024")
    parser.add_argument("height", type=int, help="new height, for example 768")
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE, help=f"target EXE path, default: {DEFAULT_EXE}")
    parser.add_argument("--dry-run", action="store_true", help="validate and show changes without writing")
    parser.add_argument("--force", action="store_true", help="allow patching an unrecognized EXE hash")
    return parser.parse_args()


def validate_resolution(width: int, height: int) -> None:
    if width < 800 or height < 600:
        raise ValueError("width and height must be at least 800x600")
    if width > 8192 or height > 8192:
        raise ValueError("resolution is unexpectedly large; refusing to patch")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")


def verify_patch_points(data: bytes) -> list[str]:
    issues: list[str] = []
    for point in PATCH_POINTS:
        actual = read_u32(data, point.offset)
        if actual != point.original:
            issues.append(
                f"0x{point.offset:05X} {point.label}: expected {point.original}, found {actual}"
            )
    return issues


def verify_repatchable_points(data: bytes) -> list[str]:
    width_values = {read_u32(data, point.offset) for point in PATCH_POINTS if point.original == 800}
    height_values = {read_u32(data, point.offset) for point in PATCH_POINTS if point.original == 600}
    viewport_values = {read_u32(data, point.offset) for point in PATCH_POINTS if point.original == 449}
    issues: list[str] = []
    if len(width_values) != 1:
        issues.append(f"width patch points disagree: {sorted(width_values)}")
    if len(height_values) != 1:
        issues.append(f"height patch points disagree: {sorted(height_values)}")
    if len(viewport_values) != 1:
        issues.append(f"viewport-height patch points disagree: {sorted(viewport_values)}")
    width = next(iter(width_values))
    height = next(iter(height_values))
    viewport_height = next(iter(viewport_values))
    if width < 800 or width > 8192:
        issues.append(f"current width is outside expected range: {width}")
    if height < 600 or height > 8192:
        issues.append(f"current height is outside expected range: {height}")
    if viewport_height not in (449, height - 151):
        issues.append(
            f"current gameplay viewport height should be 449 or screen height - 151: {viewport_height}"
        )
    return issues


def main() -> int:
    args = parse_args()
    try:
        validate_resolution(args.width, args.height)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    exe = args.exe
    if not exe.exists():
        print(f"error: EXE not found: {exe}", file=sys.stderr)
        return 2

    original = exe.read_bytes()
    digest = sha256(original)
    backup = exe.with_name(exe.name + ".bak")
    backup_is_supported = backup.exists() and sha256(backup.read_bytes()) == SUPPORTED_SHA256
    if digest != SUPPORTED_SHA256 and not backup_is_supported and not args.force:
        print(f"error: unsupported EXE sha256: {digest}", file=sys.stderr)
        print("Use --force only if this is a compatible WangGun.exe build.", file=sys.stderr)
        return 2

    if digest == SUPPORTED_SHA256:
        issues = verify_patch_points(original)
    else:
        issues = verify_repatchable_points(original)
    if issues:
        print("error: target does not look like a supported WangGun.exe layout:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        print("Restore from WangGun.exe.bak or use a fresh compatible EXE.", file=sys.stderr)
        return 2

    replacements = {
        "width": args.width,
        "height": args.height,
        "viewport_height": args.height - 151,
    }
    patched = bytearray(original)
    for point in PATCH_POINTS:
        if point.original == 800:
            value = replacements["width"]
        elif point.original == 600:
            value = replacements["height"]
        else:
            value = replacements["viewport_height"]
        write_u32(patched, point.offset, value)

    print(f"target: {exe}")
    print(f"sha256: {digest}")
    for point in PATCH_POINTS:
        current = read_u32(original, point.offset)
        if point.original == 800:
            value = replacements["width"]
        elif point.original == 600:
            value = replacements["height"]
        else:
            value = replacements["viewport_height"]
        print(f"0x{point.offset:05X}: {current} -> {value} ({point.label})")

    if args.dry_run:
        print("dry-run: no files changed")
        return 0

    if not backup.exists():
        shutil.copy2(exe, backup)
        print(f"backup created: {backup}")
    else:
        print(f"backup already exists: {backup}")

    exe.write_bytes(patched)
    print(f"patched: {args.width}x{args.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
