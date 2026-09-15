#!/usr/bin/env python3
"""Compile-preflight one exact captured Winbond Verilog model with Icarus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_vendor_verilog_preflight import preflight_winbond_verilog_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--capture-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()

    manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
    result = preflight_winbond_verilog_model(
        args.archive.read_bytes(),
        manifest,
        timeout_s=args.timeout_s,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "eligible_for_bound_jedec_testbench" else 2


if __name__ == "__main__":
    raise SystemExit(main())
