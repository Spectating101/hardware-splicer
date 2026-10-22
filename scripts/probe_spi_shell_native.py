"""Native FreeCAD topology sampling for one source-defined SPI shell.

Only run with FreeCADCmd in trusted local CI. This validates the proposed
open-shell STEP B-rep's floor, walls and void regions, not PCB mounts,
connectors, tolerances or manufacturability.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import FreeCAD
import Part

source = Path(os.environ["HS_SHELL_STEP"])
destination = Path(os.environ["HS_SHELL_TOPOLOGY_REPORT"])
shape = Part.Shape()
shape.read(str(source))
samples = [
    {"id": "floor_center_material", "point_mm": [55, 35, 1], "expected_material": True},
    {"id": "left_wall_material", "point_mm": [1, 35, 12], "expected_material": True},
    {"id": "rear_wall_material", "point_mm": [55, 69, 12], "expected_material": True},
    {"id": "pcb_cavity_void", "point_mm": [55, 35, 12], "expected_material": False},
    {"id": "top_opening_void", "point_mm": [55, 35, 24], "expected_material": False},
    {"id": "outside_void", "point_mm": [125, 80, 12], "expected_material": False},
]
for sample in samples:
    xyz = sample["point_mm"]
    sample["actual_material"] = bool(shape.isInside(
        FreeCAD.Vector(float(xyz[0]), float(xyz[1]), float(xyz[2])), 0.01, False))
    sample["pass"] = sample["actual_material"] == sample["expected_material"]

result = {
    "schema": "hardware_splicer.native_shell_topology.v1",
    "source_step_sha256": "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
    "engine": "FreeCAD Part.Shape.isInside",
    "shape_valid": bool(shape.isValid()),
    "solid_count": len(shape.Solids),
    "samples": samples,
    "all_samples_match": bool(shape.isValid() and len(shape.Solids) == 1 and
                              all(sample["pass"] for sample in samples)),
    "physical_measurement_performed": False,
    "fabrication_authorized": False,
    "release_authorized": False,
}
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
if not result["all_samples_match"]:
    raise SystemExit("Native shell cavity topology did not match source-defined test points")
