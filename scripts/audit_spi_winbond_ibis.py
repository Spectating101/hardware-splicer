#!/usr/bin/env python3
"""Audit one imported Winbond W25Q128JWSIQ IBIS capture without executing it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_winbond_ibis_capability import audit_winbond_ibis_capabilities


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--capture-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
    result = audit_winbond_ibis_capabilities(args.archive.read_bytes(), manifest)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["eligible_for_later_signal_integrity_execution"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
