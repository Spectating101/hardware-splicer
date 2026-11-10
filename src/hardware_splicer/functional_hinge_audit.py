"""Source-and-output provenance audit of the real moving-assembly study.

Imports and checks EVERY original printable STEP and STL. Independently
recomputes selection, source-link and expected leaf BRep volumes. Full
fine-motion 1-degree sweep is a separate expensive evidence report.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from typing import Any,Mapping

from .function_print_geometry import canonical,file_sha
from .functional_hinge_assembly import (
    OUTPUT,validate,machine_function_intent,make_parts,evaluate_motion
)

def audit(req:Mapping[str,Any],out:Path)->dict[str,Any]:
    import cadquery as cq
    import trimesh
    validated=validate(req)
    report=json.loads((out/"HINGE_EVALUATION.json").read_text())
    if report.get("schema")!=OUTPUT or report.get("project_id")!=validated["project_id"]:
        raise ValueError("unknown or unrelated assembly trial")
    if report["reference_spec_sha256"]!=hashlib.sha256(canonical(validated)).hexdigest():
        raise ValueError("hinge input source changed")
    if file_sha(out/"function_intent.json")!=report["native_function_intent_SHA256"]:
        raise ValueError("native HS function intent changed")
    if json.loads((out/"function_intent.json").read_text())!=machine_function_intent(validated):
        raise ValueError("intent requirements changed after engineering review")
    if len(report["candidates"])!=len(validated["alternatives"]):
        raise ValueError("missing one or more alternative mechanisms")
    eligible=[]
    for alt,row in zip(validated["alternatives"],report["candidates"]):
        if row["id"]!=alt["id"]:
            raise ValueError("candidate source order changed")
        if row["nominal_mechanism_feasible"]!=all(row["checks"].values()):
            raise ValueError("source candidate pass was misclassified")
        sweep=row["discrete_sweep"]
        if [x["angle_deg"] for x in sweep]!=list(range(0,181,validated["mechanical"]["angle_sampling_step_deg"])):
            raise ValueError("missing or reordered kinematic observation")
        if (row["geometry"]["min_modelled_shell_gap_mm"]!=min(x["shell_distance_mm"] for x in sweep)
            or row["geometry"]["min_modelled_screen_gap_mm"]!=min(x["screen_distance_mm"] for x in sweep)
            or row["geometry"]["min_screen_to_other_leaf_gap_mm"]!=min(x["screen_to_other_leaf_distance_mm"] for x in sweep)):
            raise ValueError("reported aggregate motion gap does not match actual saved sweep")
        ref=make_parts(validated,alt)
        for name in ("lower_leaf","upper_leaf"):
            path=out/"candidates"/alt["id"]/name
            receipt=row["printed_files"][name]
            st=path.with_suffix(".step");mesh=path.with_suffix(".stl")
            if file_sha(st)!=receipt["step_sha256"] or file_sha(mesh)!=receipt["stl_sha256"]:
                raise ValueError("native printed CAD source was tampered")
            original=cq.importers.importStep(str(st))
            tri=trimesh.load(str(mesh),force="mesh")
            if not original.val().isValid() or len(original.solids().vals())!=1 or not tri.is_watertight:
                raise ValueError("not a printable watertight single-shell part")
            vol=original.val().Volume()
            if not math.isclose(vol,ref[name].Volume(),abs_tol=.15):
                raise ValueError("STEP solid doesn't match source authored geometry")
            if not math.isclose(tri.volume,vol,rel_tol=.007):
                raise ValueError("STL source is not volume-consistent")
            if not math.isclose(receipt["BRep_volume_mm3"],vol,abs_tol=.15):
                raise ValueError("model-reported printed geometry volume was falsified")
            if receipt.get("fabrication_authorized") is not False:
                raise ValueError("printed component falsely granted fabrication authority")
        if row["nominal_mechanism_feasible"]:
            eligible.append(row)
    eligible.sort(key=lambda x:(x["geometry"]["solid_volume_mm3"],x["geometry"]["folded_solid_height_mm"],x["id"]))
    if report["feasible_order"]!=[x["id"] for x in eligible] or report["selected"]!=(eligible[0]["id"] if eligible else None):
        raise ValueError("selected mechanism is not the least-material feasible source design")
    if any(report["authority"].values()):
        raise ValueError("unverified physical/production authority was promoted")
    chosen=report["selected"]
    if chosen:
        for name in ("lower_leaf","upper_leaf"):
            src=out/"candidates"/chosen/name
            dest=out/"selected"/name
            for suffix in (".step",".stl"):
                if file_sha(src.with_suffix(suffix))!=file_sha(dest.with_suffix(suffix)):
                    raise ValueError("selected printed leaf differs from feasible ranked source")
        for name in ("assembly_open_0.step","assembly_half_90.step","assembly_folded_180.step",
                     "cable_service_keepout_only.step"):
            path=out/"selected"/name
            if not path.exists() or path.stat().st_size<1000:
                raise ValueError("reconstructed assembly STEP not present: "+name)
            assembled=cq.importers.importStep(str(path))
            if not assembled.solids().vals():
                raise ValueError("assembly STEP has no real OCP solids")
    return {
       "schema":"hs.cyberdeck_hinge_native_source_audit.v1",
       "source_spec_sha256":report["reference_spec_sha256"],
       "original_real_printed_parts":2*len(report["candidates"]),
       "kinematic_source_angles_per_candidate":37,
       "source_ranked_winner":chosen,
       "all_original_BRep_and_mesh_exports_verified":True,
       "physical_dimensions_fabrication_verified":False,
    }

def fine_selected(req:Mapping[str,Any],out:Path)->dict[str,Any]:
    validated=validate(req)
    report=json.loads((out/"HINGE_EVALUATION.json").read_text())
    selected=report.get("selected")
    if not selected:
        raise ValueError("no reference geometry survived declared 5-degree gates")
    alt=next(x for x in validated["alternatives"] if x["id"]==selected)
    source=make_parts(validated,alt)
    precise=evaluate_motion(validated,alt,source,step_deg=1)
    if precise["mechanism"]["interval_samples"]!=181:
        raise ValueError("one-degree sampling was not actually performed")
    return {
       "schema":"hs.cyberdeck_hinge_fine_motion_v1",
       "selected":selected,
       "source_spec_sha256":hashlib.sha256(canonical(validated)).hexdigest(),
       "step_deg":1,
       "angle_count":181,
       "all_nominal_gates_pass":precise["nominal_mechanism_feasible"],
       "minimum_printed_clearance_mm":precise["geometry"]["min_modelled_shell_gap_mm"],
       "minimum_mock_screen_gap_mm":precise["geometry"]["min_modelled_screen_gap_mm"],
       "minimum_screen_to_opposite_printed_leaf_mm":precise["geometry"]["min_screen_to_other_leaf_gap_mm"],
       "minimum_external_cable_keepout_mm":precise["geometry"]["min_reserved_cable_corridor_separation_mm"],
       "checked_intersections_by_angle":precise["discrete_sweep"],
       "continuous_geometry_collision_proven":False,
       "actual_cable_bend_fatigue_verified":False,
       "physical_hinge_fabrication_verified":False,
    }
