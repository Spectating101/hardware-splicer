#!/usr/bin/env python3
"""Legacy CLI entrypoint (deprecated).

The repo previously had an older KiCad-only CLI that referenced modules that no
longer exist. Keep this file as a compatibility shim to reduce confusion.
"""

from __future__ import annotations

from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    from src.cli import main as unified_main

    return unified_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
