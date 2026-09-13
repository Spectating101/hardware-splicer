#!/usr/bin/env python3
"""Exercise Hardware Splicer's SPI repair-loop plumbing without model inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.spi_virtual_repair_control import (
    run_scripted_repair_control,
    run_scripted_repair_control_matrix,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic SPI repair-loop control."
    )
    parser.add_argument(
        "--fault",
        choices=(
            "all",
            "direct_3v3_drive",
            "reversed_miso",
            "grouped_direction_translator",
            "missing_absmax_provenance",
        ),
        default="all",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.fault == "all":
        result = run_scripted_repair_control_matrix()
        success = bool(result["all_controls_pass"])
    else:
        result = run_scripted_repair_control(args.fault)
        success = bool(result["control_pass"])

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
