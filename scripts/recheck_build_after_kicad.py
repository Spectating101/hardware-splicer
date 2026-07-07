#!/usr/bin/env python3
"""Re-run DRC/ERC and refresh package after KiCad GUI edits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.kicad_sidecar_recheck import recheck_build_after_kicad_edit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path, help="Splice or compile output directory")
    parser.add_argument("--no-package", action="store_true", help="Skip PROJECT_PACKAGE refresh")
    parser.add_argument("--no-views", action="store_true", help="Skip PDF/SVG export")
    parser.add_argument("--source", default="cli_kicad_sidecar", help="Audit source label")
    args = parser.parse_args()
    try:
        report = recheck_build_after_kicad_edit(
            args.build_dir,
            refresh_package=not args.no_package,
            export_views=not args.no_views,
            source=args.source,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    drc = report.get("drc") or {}
    if drc.get("skipped"):
        return 0
    return 0 if drc.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
