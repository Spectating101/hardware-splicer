#!/usr/bin/env python3
"""Publish a source-bound canonical HS machine/product record from real sensor CI artifacts."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.engineering_product_handoff import export


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geometry", type=Path, required=True)
    p.add_argument("--firmware", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        receipt = export(args.geometry, args.firmware, args.out)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("Canonical machine handoff refused: " + str(exc), file=sys.stderr)
        return 1
    print("ESP32 sensor native evidence -> canonical MachineProject: "
          + str(len(receipt["files"])) + " source-bound files; physical release BLOCKED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
