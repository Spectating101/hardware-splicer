#!/usr/bin/env python3
"""Inspect the current KiCad-9 SPI reference review ZIP without authorizing power/fabrication."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.spi_native_cam_review import inspect_spi_native_cam_archive  # noqa: E402

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = inspect_spi_native_cam_archive(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit": result["status"], "issues": result["issues"],
                      "native_kiCad": result.get("native_receipt_kicad_cli_version"),
                      "gerber_layers": len(result.get("gerber_layers", [])),
                      "drill_files": len(result.get("drill_files", [])),
                      "output": str(args.out)}, indent=2))
    if result["issues"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
