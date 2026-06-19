#!/usr/bin/env python3
"""Generate a small synthetic donor-board PNG for vision smoke tests (stdlib only)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tests" / "data" / "donor_rc_board_sample.png"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_synthetic_board_png(path: Path, *, width: int = 96, height: int = 64) -> Path:
    """Draw a green PCB rectangle with copper traces — enough for vision dry-run."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for y in range(height):
        row = bytearray([0])  # filter type 0
        for x in range(width):
            border = x < 4 or y < 4 or x >= width - 4 or y >= height - 4
            trace_h = 20 <= y <= 24 and 10 <= x <= width - 10
            trace_v = 30 <= x <= 34 and 8 <= y <= height - 8
            chip = 42 <= x <= 58 and 28 <= y <= 44
            if chip:
                r, g, b = 32, 32, 36
            elif trace_h or trace_v:
                r, g, b = 184, 134, 48
            elif border:
                r, g, b = 18, 74, 36
            else:
                r, g, b = 28, 110, 52
            row.extend([r, g, b])
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")
    path.write_bytes(png)
    return path


def main() -> int:
    out = write_synthetic_board_png(DEFAULT_OUT)
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
