#!/usr/bin/env python3
"""Print canonical Hardware Splicer capability truth as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.capability_runtime import capability_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report discovered, configured, compatible, machine-tested, and "
            "project-used Hardware Splicer capabilities."
        )
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="Optional build directory used to detect project-scoped capability artifacts.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON rather than an indented operator report.",
    )
    args = parser.parse_args()

    payload = capability_report(build_dir=args.build_dir)
    print(
        json.dumps(
            payload,
            indent=None if args.compact else 2,
            sort_keys=True,
        )
    )
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
