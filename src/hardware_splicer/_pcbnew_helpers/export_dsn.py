#!/usr/bin/env python3
"""Export a KiCad board to Specctra DSN. Runs under a pcbnew-capable interpreter."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: export_dsn.py board.kicad_pcb board.dsn", file=sys.stderr)
        return 2
    board_path, dsn_path = args
    try:
        import pcbnew
    except ImportError:
        print("pcbnew is not importable", file=sys.stderr)
        return 1
    try:
        board = pcbnew.LoadBoard(board_path)
        ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
    except Exception as exc:
        print(f"DSN export failed: {exc}", file=sys.stderr)
        return 1
    dsn = Path(dsn_path)
    if not ok or not dsn.is_file() or dsn.stat().st_size < 1:
        print("ExportSpecctraDSN produced no DSN", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
