#!/usr/bin/env python3
"""Import a Specctra SES into a KiCad board. Runs under a pcbnew-capable interpreter."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("usage: import_ses.py board.kicad_pcb board.ses routed.kicad_pcb", file=sys.stderr)
        return 2
    board_path, ses_path, out_path = args
    try:
        import pcbnew
    except ImportError:
        print("pcbnew is not importable", file=sys.stderr)
        return 1
    try:
        board = pcbnew.LoadBoard(board_path)
        ok = pcbnew.ImportSpecctraSES(board, ses_path)
        if not ok:
            print("ImportSpecctraSES failed", file=sys.stderr)
            return 1
        pcbnew.SaveBoard(out_path, board)
    except Exception as exc:
        print(f"SES import failed: {exc}", file=sys.stderr)
        return 1
    routed = Path(out_path)
    if not routed.is_file() or routed.stat().st_size < 1:
        print("SaveBoard produced no PCB", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
