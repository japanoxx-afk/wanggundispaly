#!/usr/bin/env python3
"""Patch Taejo Wang Geon display behavior."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXE = Path("C:/Program Files/\ud0dc\uc870\uc655\uac74/WangGun.exe")
DEFAULT_ICARUS = Path("C:/Program Files/\ud0dc\uc870\uc655\uac74/iCARUS.dll")
SUPPORTED_SHA256 = "5e80aad54982ddf8cafbb367b70e65b9438b093ade414f36b3959e9e8b08e5fe"
SUPPORTED_ICARUS_SHA256 = "972ed0742efd966852f93503aa4b7db9b7532a34b54e3ed0c9bb56b9942eb6a1"


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

ICARUS_DISPLAY_MODE_PATCHES = [
    (0x184A0, bytes.fromhex("0f bf 15 60 60 0b 10"), "display mode height"),
    (0x184AA, bytes.fromhex("0f bf 15 5e 60 0b 10"), "display mode width"),
]

ICARUS_BLT_PATCHES = [
    (0x18A3D, bytes.fromhex("68 00 60 0b 10"), bytes.fromhex("6a 00 90 90 90"), "Blt flags"),
    (0x18A44, bytes.fromhex("52 6a 00"), bytes.fromhex("6a 00 52"), "Blt source argument order"),
    (0x18A4C, bytes.fromhex("1c"), bytes.fromhex("14"), "BltFast to Blt vtable slot"),
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
    parser.add_argument(
        "--icarus",
        type=Path,
        default=DEFAULT_ICARUS,
        help=f"target iCARUS.dll path for --scale mode, default: {DEFAULT_ICARUS}",
    )
    parser.add_argument(
        "--scale",
        action="store_true",
        help="keep the game renderer at 800x600 and scale the final DirectDraw blit to the requested output mode",
    )
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


def write_exe_resolution(data: bytes, width: int, height: int, scale: bool) -> bytearray:
    patched = bytearray(data)
    replacements = {
        "width": 800 if scale else width,
        "height": 600 if scale else height,
        "viewport_height": 449 if scale else height - 151,
    }
    for point in PATCH_POINTS:
        if point.original == 800:
            value = replacements["width"]
        elif point.original == 600:
            value = replacements["height"]
        else:
            value = replacements["viewport_height"]
        write_u32(patched, point.offset, value)
    return patched


def print_exe_changes(data: bytes, width: int, height: int, scale: bool) -> None:
    replacements = {
        "width": 800 if scale else width,
        "height": 600 if scale else height,
        "viewport_height": 449 if scale else height - 151,
    }
    for point in PATCH_POINTS:
        current = read_u32(data, point.offset)
        if point.original == 800:
            value = replacements["width"]
        elif point.original == 600:
            value = replacements["height"]
        else:
            value = replacements["viewport_height"]
        print(f"EXE 0x{point.offset:05X}: {current} -> {value} ({point.label})")


def verify_icarus_layout(data: bytes) -> list[str]:
    issues: list[str] = []
    for offset, original, label in ICARUS_DISPLAY_MODE_PATCHES:
        current = data[offset : offset + len(original)]
        already_patched = len(current) == 7 and current[0] == 0xBA and current[5:7] == b"\x90\x90"
        if current != original and not already_patched:
            issues.append(f"iCARUS 0x{offset:05X} {label}: unexpected bytes {current.hex(' ')}")
    for offset, original, patched, label in ICARUS_BLT_PATCHES:
        current = data[offset : offset + len(original)]
        if current != original and current != patched:
            issues.append(f"iCARUS 0x{offset:05X} {label}: unexpected bytes {current.hex(' ')}")
    return issues


def write_icarus_scale_patch(data: bytes, width: int, height: int) -> bytearray:
    patched = bytearray(data)
    patched[0x184A0 : 0x184A7] = b"\xBA" + struct.pack("<I", height) + b"\x90\x90"
    patched[0x184AA : 0x184B1] = b"\xBA" + struct.pack("<I", width) + b"\x90\x90"
    for offset, _original, replacement, _label in ICARUS_BLT_PATCHES:
        patched[offset : offset + len(replacement)] = replacement
    return patched


def print_icarus_changes(data: bytes, width: int, height: int) -> None:
    print(f"iCARUS 0x184A0: display mode height -> {height}")
    print(f"iCARUS 0x184AA: display mode width -> {width}")
    for offset, _original, replacement, label in ICARUS_BLT_PATCHES:
        current = data[offset : offset + len(replacement)]
        print(f"iCARUS 0x{offset:05X}: {current.hex(' ')} -> {replacement.hex(' ')} ({label})")


def write_with_backup(path: Path, data: bytes, dry_run: bool) -> None:
    if dry_run:
        return
    backup = path.with_name(path.name + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"backup created: {backup}")
    else:
        print(f"backup already exists: {backup}")
    path.write_bytes(data)


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

    print(f"target: {exe}")
    print(f"sha256: {digest}")
    print_exe_changes(original, args.width, args.height, args.scale)
    patched = write_exe_resolution(original, args.width, args.height, args.scale)

    icarus_patched: bytearray | None = None
    if args.scale:
        icarus = args.icarus
        if not icarus.exists():
            print(f"error: iCARUS.dll not found: {icarus}", file=sys.stderr)
            return 2
        icarus_data = icarus.read_bytes()
        icarus_digest = sha256(icarus_data)
        icarus_backup = icarus.with_name(icarus.name + ".bak")
        icarus_backup_is_supported = (
            icarus_backup.exists() and sha256(icarus_backup.read_bytes()) == SUPPORTED_ICARUS_SHA256
        )
        if icarus_digest != SUPPORTED_ICARUS_SHA256 and not icarus_backup_is_supported and not args.force:
            print(f"error: unsupported iCARUS.dll sha256: {icarus_digest}", file=sys.stderr)
            print("Use --force only if this is a compatible iCARUS.dll build.", file=sys.stderr)
            return 2
        icarus_issues = verify_icarus_layout(icarus_data)
        if icarus_issues:
            print("error: target does not look like a supported iCARUS.dll layout:", file=sys.stderr)
            for issue in icarus_issues:
                print(f"  - {issue}", file=sys.stderr)
            return 2
        print(f"target: {icarus}")
        print(f"sha256: {icarus_digest}")
        print_icarus_changes(icarus_data, args.width, args.height)
        icarus_patched = write_icarus_scale_patch(icarus_data, args.width, args.height)

    if args.dry_run:
        print("dry-run: no files changed")
        return 0

    write_with_backup(exe, patched, args.dry_run)
    if args.scale and icarus_patched is not None:
        write_with_backup(args.icarus, icarus_patched, args.dry_run)
        print(f"patched: 800x600 internal renderer scaled to {args.width}x{args.height}")
    else:
        print(f"patched: {args.width}x{args.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
