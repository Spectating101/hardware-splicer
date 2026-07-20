#!/usr/bin/env python3
"""Verify golden geometry snapshots for catalog builds (gate 5.4)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from hardware_splicer.build_compiler import compile_catalog_build  # noqa: E402
from hardware_splicer.geometry_snapshot import build_geometry_snapshot, compare_geometry_snapshots  # noqa: E402

GOLDEN_ROOT = ROOT / "examples" / "geometry_snapshots"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare catalog geometry against golden snapshots.")
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_verify_geometry"))
    parser.add_argument("--json", type=Path, default=None, help="Write the complete comparison report")
    parser.add_argument("--build-id", action="append", dest="build_ids")
    args = parser.parse_args()

    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"

    golden_files = sorted(GOLDEN_ROOT.glob("*.json"))
    if args.build_ids:
        golden_files = [GOLDEN_ROOT / f"{bid}.json" for bid in args.build_ids]
    rows = []
    for golden_path in golden_files:
        if not golden_path.is_file():
            rows.append({"build_id": golden_path.stem, "ok": False, "error": "missing golden file"})
            continue
        expected = json.loads(golden_path.read_text(encoding="utf-8"))
        build_id = str(expected.get("build_id") or golden_path.stem)
        target = args.out / build_id
        compile_catalog_build(build_id, target, export_gerber=False)
        actual = build_geometry_snapshot(target)
        diff = compare_geometry_snapshots(expected, actual)
        rows.append({"build_id": build_id, "golden_file": str(golden_path), **diff})

    report = {
        "schema_version": "hardware_splicer.geometry_verify.v1",
        "golden_root": str(GOLDEN_ROOT),
        "output_root": str(args.out),
        "ok": all(row.get("ok") for row in rows),
        "rows": rows,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
