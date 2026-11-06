#!/usr/bin/env python3
"""Check every quote in the robot part library against the captured copy of its own source.

Writes the result, with each capture's sha256, to ``docs/status/generated/robot_part_quote_check_<YYYYMMDD>.json`` and
exits non-zero when any quote is not found or when there is nothing to check.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.robot_parts import load_parts, verify_quotes  # noqa: E402

DEFAULT_DIR = ROOT / ".cache" / "hardware-splicer" / "robot_part_sources"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "status" / "generated" /
                    f"robot_part_quote_check_{date.today():%Y%m%d}.json")
    args = ap.parse_args()
    result = verify_quotes(load_parts(), args.capture_dir)
    result["checked_on"] = date.today().isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "quotes_checked": result["quotes_checked"], "failed": result["failed"]},
                     indent=1, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
