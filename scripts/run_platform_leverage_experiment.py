#!/usr/bin/env python3
"""Calculate a Hardware-Splicer platform-leverage experiment report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.platform_leverage import (
    calculate_platform_leverage,
    evaluate_platform_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path, help="platform-leverage experiment JSON")
    parser.add_argument("--thresholds", type=Path, help="optional preregistered threshold JSON")
    parser.add_argument("--out", type=Path, help="write report JSON here")
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    report = calculate_platform_leverage(record)

    if args.thresholds:
        thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
        report["gate"] = evaluate_platform_gate(report, thresholds)

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
