#!/usr/bin/env python3
"""Native FreeCAD bore/boss verification for PCB-sourced SPI mounting features.

Runs *within FreeCADCmd*, not standard Python. Tests CAD solid/void material
and reference-driven nominal volume without approving 3D printing or fasteners.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path

import FreeCAD
import Part

source=Path(os.environ["HS_MOUNTED_SHELL_STEP"])
manifest_path=Path(os.environ["HS_MOUNTING_REQUIREMENTS"])
destination=Path(os.environ["HS_MOUNTED_SHELL_TOPOLOGY"])
manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
shape=Part.Shape()
shape.read(str(source))
def point_test(ref,category,xyz,expect):
    observed=bool(shape.isInside(FreeCAD.Vector(*[float(v) for v in xyz]),0.01,False))
    return {"ref":ref,"kind":category,"sample_xyz_mm":xyz,
            "expected_material":expect,"measured_material":observed,"pass":observed is expect}

samples=[
    point_test("shell","floor_center",[55,35,1],True),
    point_test("shell","open_cavity",[55,35,12],False),
]
for m in manifest["mounts"]:
    x,y=m["cad_shell_center_xy_mm"]
    ref=m["ref"]
    samples.extend([
        point_test(ref,"boss_annulus",[x+2.4,y,4],True),
        point_test(ref,"pilot_hole",[x,y,4],False),
        point_test(ref,"floor_through_hole",[x,y,1],False),
    ])
expected_volume=(
    110*70*25-104*64*23 +
    4*(math.pi*3.3*3.3*3.2-math.pi*1.65*1.65*5.2)
)
result={
    "schema":"hardware_splicer.native_mounted_shell_topology.v1",
    "engine":"FreeCAD Part.Shape.isInside",
    "source_step_sha256":"sha256:"+hashlib.sha256(source.read_bytes()).hexdigest(),
    "source_mount_manifest_sha256":"sha256:"+hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "source_kicad_sha256":manifest["input_pcb_sha256"],
    "shape_valid":bool(shape.isValid()),"solid_count":len(shape.Solids),
    "volume_mm3":float(shape.Volume),"expected_volume_mm3":expected_volume,
    "solid_volume_agrees":abs(float(shape.Volume)-expected_volume)<0.1,
    "bbox_mm":[float(shape.BoundBox.XLength),float(shape.BoundBox.YLength),float(shape.BoundBox.ZLength)],
    "sample_checks":samples,
    "checks_passed":bool(shape.isValid() and len(shape.Solids)==1 and
                        abs(float(shape.Volume)-expected_volume)<0.1 and
                        all(row["pass"] for row in samples)),
    "physical_fit_verified":False,
    "fastener_torque_verified":False,
    "fabrication_authorized":False,
    "release_authorized":False,
}
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"checks_passed":result["checks_passed"],
                  "samples":len(samples),
                  "solid_count":result["solid_count"],
                  "volume_mm3":result["volume_mm3"],
                  "expected_volume_mm3":expected_volume},indent=2))
if not result["checks_passed"]:
    raise SystemExit("Native CAD mounting holes or their bosses are invalid")
