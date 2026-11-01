#!/usr/bin/env python3
"""Require actual CADCLAW STEP assembly and verifiable dry-component placements."""
from __future__ import annotations
import argparse,hashlib,json,math,subprocess
from pathlib import Path
import cadquery as cq
import yaml

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def check(ok:bool,msg:str):
    if not ok:raise ValueError("Native CADCLAW evidence REFUSED: "+msg)

def verify(root:Path)->dict:
    root=Path(root).resolve()
    original=json.loads((root/"CADCLAW_INPUT_RECEIPT.json").read_text())
    check(original.get("schema_version")=="hardware_splicer.cadclaw_dry_assembly_input.v1",
          "wrong input evidence")
    expected={
        "tray":([450,260,14]),
        "panel":([450,12,716]),
        "housing_envelope":([118,118,308]),
        "sample_concept":([66,66,75]),
    }
    check(set(original.get("authored_step_parts",{}))==set(expected),
          "wrong native part inventory")
    for name,dimensions in expected.items():
        info=original["authored_step_parts"][name]
        path=root/info["file"]
        check(path.is_file() and digest(path.read_bytes())==info["sha256"],
              "authored STEP altered: "+name)
        part=cq.importers.importStep(str(path))
        bb=part.val().BoundingBox()
        check(all(math.isclose(x,y,abs_tol=0.05) for x,y in
                  zip((bb.xlen,bb.ylen,bb.zlen),dimensions)),
              "authored STEP dimensions unexpected: "+name)
    spec=yaml.safe_load((root/"assembly.yaml").read_text())
    check(spec["schema_version"]=="assembly_spec.v0.1" and
          len(spec["instances"])==4,"CADCLAW source inventory wrong")
    check({i["id"] for i in spec["instances"]}==set(expected),"CADCLAW component refs changed")
    panel=next(i for i in spec["instances"] if i["id"]=="panel")
    check(panel["place_relative_to"]["ref"]=="tray" and
          panel["place_relative_to"]["lock"]=="frame" and
          panel["place_relative_to"]["offset_mm"]==0,
          "no true constraint based dry panel seating")
    check(len(spec["not_built_yet"])>=6 and all(
          row["required_for_release"] is True for row in spec["not_built_yet"]),
          "unqualified wet assembly released by incomplete spec")
    combined=root/"clearbench_s1_dry_reference.step"
    check(combined.is_file() and combined.stat().st_size>1500,
          "CADCLAW did not actually compile STEP assembly")
    assembly=cq.importers.importStep(str(combined))
    solids=assembly.solids().vals()
    check(len(solids)>=4,"CADCLAW lost required authored STEP parts")
    b=assembly.val().BoundingBox()
    check(math.isclose(b.xlen,450,abs_tol=0.05) and
          math.isclose(b.ylen,260,abs_tol=0.05) and
          math.isclose(b.zlen,730,abs_tol=0.05),
          "native assembly STEP global bounds differ from product spec")
    check(original["physical_release_authorized"] is False and
          original["fit_mating_verified"] is False and
          original["hydraulic_pressure_safety_verified"] is False,
          "physical authority falsely promoted")
    proof={
        "schema_version":"hardware_splicer.cadclaw_native_dry_assembly.v1",
        "product_id":original["product_id"],
        "source_spec_sha256":original["source_spec_sha256"],
        "cadclaw_native_assembly_step_sha256":digest(combined.read_bytes()),
        "cadclaw_native_assembly_step_bytes":combined.stat().st_size,
        "authored_step_part_count":len(expected),
        "assembly_solids_count":len(solids),
        "solved_constraint":{"child":"panel","parent":"tray","type":"full_frame",
                             "unknown_actual_fasteners":True},
        "assembly_bbox_mm":[round(b.xlen,2),round(b.ylen,2),round(b.zlen,2)],
        "vendor_component_assembly_complete":False,
        "pressurized_system_build_ready":False,
        "independent_MARB_score":None,
        "manufacturing_authorized":False,
        "water_operation_authorized":False,
    }
    target=root/"CADCLAW_NATIVE_ASSEMBLY_EVIDENCE.json"
    if target.exists():raise FileExistsError("No overwriting CADCLAW evidence")
    target.write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
    return proof

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assembly",type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(verify(a.assembly),indent=2,sort_keys=True))
    except (OSError,KeyError,ValueError,TypeError) as e:
        print(e)
        raise SystemExit(1)
