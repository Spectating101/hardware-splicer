#!/usr/bin/env python3
"""Verify one SPI electronics + native CAD candidate with source-bound evidence.

Input: an independent, operator-authorized SolidCraft -> FreeCAD CLI run and
the reference KiCad PCB + its historical native verification receipt.
Output is review-only. The command never manufactures or operates hardware.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.crossdomain_device_acceptance import assess_crossdomain_reference  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engines", type=Path, required=True,
                   help="directory with native SolidCraft and FreeCAD report")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--pcb", type=Path, default=ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb")
    p.add_argument("--receipt", type=Path, default=ROOT / "hardware/reference_designs/spi_flash_adapter_v1/verification.json")
    p.add_argument("--recipe", type=Path, default=ROOT / "examples/external_engines/cad/spi_adapter_shell.json")
    a = p.parse_args()
    result = assess_crossdomain_reference(
        pcb_path=a.pcb, receipt_path=a.receipt, cad_recipe_path=a.recipe,
        engine_output_dir=a.engines, output_dir=a.out,
    )
    print(json.dumps({
        "status": result["status"],
        "board_size_mm": result["electrical"]["board_size_mm"],
        "nominal_cavity_mm": result["mechanical"]["source_shell_model"]["nominal_cavity_dimensions_mm"],
        "native_shell_valid": result["mechanical"]["native_freecad_geometry"]["shape_valid"],
        "envelope_screen_blockers": result["interface_screen"]["blocker_count"],
        "release_authorized": False,
        "report": str(a.out / "CROSS_DOMAIN_DEVICE_ASSESSMENT.json"),
    }, indent=2))
    if result["status"] != "source_linked_envelope_clear_unverified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
