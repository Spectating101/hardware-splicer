#!/usr/bin/env python3
"""Render PROJECT_PACKAGE artifacts from an existing build directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.sdk import render_project_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path, help="Splice or synthesis output directory")
    parser.add_argument("--source", default="cli", help="Package source label")
    parser.add_argument("--json", action="store_true", help="Print package JSON to stdout")
    args = parser.parse_args()
    report = render_project_package(args.build_dir, source=args.source)
    print(json.dumps(report.get("artifacts") or report, indent=2))
    if args.json and report.get("package"):
        print(json.dumps(report["package"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
