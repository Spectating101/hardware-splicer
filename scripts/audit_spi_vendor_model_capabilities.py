#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_vendor_model_capability_audit import audit_txu0304_ibis_capabilities


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit bounded claim capabilities of a captured SPI vendor model")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
    result = audit_txu0304_ibis_capabilities(args.archive.read_bytes(), manifest)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
