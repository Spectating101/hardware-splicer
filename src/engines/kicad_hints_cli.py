#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.engines.kicad_hints import generate_hints_template


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate hint template JSON for KiCad .net validation")
    ap.add_argument("netlist", type=Path, help="Path to KiCad .net")
    ap.add_argument("--out", type=Path, default=None, help="Write to file (default: stdout)")
    args = ap.parse_args()

    payload = generate_hints_template(str(args.netlist))
    text = json.dumps(payload, indent=2, sort_keys=True)

    if args.out:
        args.out.write_text(text)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
