#!/usr/bin/env python3
"""Package native cross-domain SPI evidence for independent device-build review."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from hardware_splicer.real_device_work_package import compile_work_package  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assessment", type=Path, required=True)
    p.add_argument("--external-engines", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    assessment = json.loads(args.assessment.read_text(encoding="utf-8"))
    engines = json.loads(args.external_engines.read_text(encoding="utf-8"))
    case = {
        "id": "spi_adapter_native_crossdomain_v1",
        "device": "SPI flash adapter with proposed 3D-printed protective shell",
        "kind": "new_build",
        "deliverables": [
            "source-hashed KiCad PCB", "SolidCraft STEP shell",
            "FreeCAD cavity proof", "sourced PCB mount/cutout requirements",
        ],
        "acceptance": ["Unpowered mechanical test-fit and independent EE review"],
    }
    review = {"operator_casefile": {
        "build_or_repair_sequence": [
            "Reconcile native KiCad PCB source, BOM and DNP assembly variant",
            "Review generated SolidCraft shell and FreeCAD native cavities",
            "Review PCB mounts, exact connector access, tolerances and 3D component envelope",
        ],
        "critical_technical_unknowns": [
            "Missing mounting bosses, cutouts, lid and source-authenticated heights",
            "No fabricated board or physical current-limited SPI rail/JEDEC measurements",
        ],
        "compatible_parts_or_requirements": [
            "Qualified standoff/fastener system", "Verified connector cutouts",
            "Manufacturer-authenticated 3D bodies and assembly clearances",
        ],
    }}
    package = compile_work_package(
        case, review, external_engine_execution=engines,
        crossdomain_device_assessment=assessment,
    )
    if package["engineering_readiness"] != "blocked":
        raise ValueError("Cross-domain package incorrectly claims readiness")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(package, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "status": package["engineering_readiness"],
        "work_steps": len(package["work_steps"]),
        "acceptance_gates": len(package["acceptance_gates"]),
        "required_parts": len(package["required_parts"]),
        "physical_build_completed": package["build_or_repair_completed"],
        "output": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
