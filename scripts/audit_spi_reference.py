#!/usr/bin/env python3
"""Independent, unpowered review handoff for HS SPI flash reference design.

This tool does not run KiCad 9 or authorize manufacturing, purchasing or power.
Native fabrication Gerbers and remote test packets remain owned by the
reference design's canonical build_package.py/build_remote_fct_campaign.py.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.spi_reference_handoff import build_spi_reference_handoff  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=ROOT / "hardware/reference_designs/spi_flash_adapter_v1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_spi_reference_handoff(args.source, output_dir=args.out)
    print(json.dumps({
        "audit": report["audit_status"],
        "issues": report["issues"],
        "initial_fit": report["bom_to_fit"],
        "initial_dnp": report["bom_dnp"],
        "unpowered_only": True,
        "output": str(args.out / "REFERENCE_HANDOFF_AUDIT.json"),
    }, indent=2))
    if report["issues"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
