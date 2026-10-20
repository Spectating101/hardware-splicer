"""Native SolidCraft -> independently audited STL/3MF -> PartCAD two-part casing.

Geometry-only. Does not run a slicer, access a printer, or authorize physical
fabrication. Requires caller-supplied trusted local SolidCraft and PartCAD CLIs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from hardware_splicer.printed_enclosure_mesh_audit import mesh_report
from hardware_splicer.printed_enclosure_workbench import prepare_printed_enclosure


def _save(path:Path, data:Any):
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")


def _invoke(binary:Path,args:list[str],cwd:Path,timeout:int=160)->dict:
    result=subprocess.run([str(binary),*args],cwd=str(cwd),capture_output=True,text=True,
                          check=False,timeout=timeout)
    result_obj={"returncode":result.returncode,"stdout_tail":result.stdout[-6000:],
                "stderr_tail":result.stderr[-1600:]}
    if result.returncode:
        raise RuntimeError("native CLI execution failed: "+json.dumps({
            "cmd":args[:4],**result_obj
        })[:1400])
    return result_obj


def _compare(a:float,b:float,tol:float=0.5)->bool:
    return abs(float(a)-float(b))<=tol


def _close_bbox(actual:dict,expected_min:list,expected_max:list,tol:float=.03)->bool:
    return all(_compare(v,u,tol) for u,v in zip(expected_min,actual["min"])) and all(
        _compare(v,u,tol) for u,v in zip(expected_max,actual["max"])
    )


def _stl_report(path:Path)->dict:
    data=path.read_bytes()
    if len(data)<84 or len(data)>12_000_000:
        raise ValueError("STL size invalid")
    n=struct.unpack_from("<I",data,80)[0]
    if n<12 or len(data)!=84+50*n:
        raise ValueError("STL binary triangle count invalid")
    # Reuse existing HS independent closed-mesh check rather than trusting a
    # SolidCraft success code or generated artifact filename.
    tris=[]
    for i in range(n):
        row=struct.unpack_from("<12fH",data,84+50*i)
        tris.append(tuple(tuple(round(row[3+3*j+k]*100) for k in range(3)) for j in range(3)))
    report=mesh_report(tris)
    if not report["closed_manifold"] or report["volume_mm3"]<=0:
        raise ValueError("non-manifold or empty printable mesh "+str(path))
    return report


def _3mf_report(path:Path)->dict:
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        model=[n for n in names if n.endswith(".model") and n.startswith("3D/")]
        if not model:raise ValueError("3MF missing 3D model XML")
        root=ElementTree.fromstring(z.read(model[0]))
        units=root.attrib.get("unit")
        objects=root.findall(".//{*}object")
        if units not in ("millimeter","millimetre") or len(objects)!=2:
            raise ValueError("3MF unit/body count differs from our 2-part print layout")
        return {"valid_3mf":True,"model_units":units,"mesh_objects":len(objects),
                "model_file":model[0]}


def _parts_workspace(out:Path,plan:dict)->Path:
    pc=out/"partcad"
    pc.mkdir(exist_ok=True)
    for name in ("Base","Lid"):
        source=out/f"HS_Casing_{name}.step"
        if not source.exists():
            raise ValueError("native STEP per part missing")
        (pc/f"HS_Casing_{name}.step").write_bytes(source.read_bytes())
    (pc/"partcad.yaml").write_text(
        "desc: Two-part HS printed enclosure prototype, not real harvested device.\n"
        "parts:\n"
        "  casing_base:\n"
        "    type: step\n"
        "    path: HS_Casing_Base.step\n"
        "    desc: Open printed housing, cable exit, screw and board bosses; conceptual only\n"
        "  casing_lid:\n"
        "    type: step\n"
        "    path: HS_Casing_Lid.step\n"
        "    desc: Ventilated printable lid with locating skirt and clearance holes; conceptual only\n"
        "assemblies:\n"
        "  casing_print_layout:\n"
        "    type: assy\n"
        "    path: casing_print_layout.assy\n"
        "  casing_assembled:\n"
        "    type: assy\n"
        "    path: casing_assembled.assy\n"
    )
    (pc/"casing_print_layout.assy").write_text(
        "links:\n"
        "  - part: casing_base\n    name: HS_Casing_Base\n"
        "    location: [[0,0,0],[0,0,1],0]\n"
        "  - part: casing_lid\n    name: HS_Casing_Lid\n"
        "    location: [[0,0,0],[0,0,1],0]\n"
    )
    x,D,z=plan["solidcraft_assembly_transform"]["translate"]
    (pc/"casing_assembled.assy").write_text(
        "links:\n"
        "  - part: casing_base\n    name: HS_Casing_Base\n"
        "    location: [[0,0,0],[0,0,1],0]\n"
        "  - part: casing_lid\n    name: HS_Casing_Lid\n"
        f"    location: [[{x},{D},{z}],[1,0,0],180]\n"
    )
    return pc


def _native_plan(plan:dict,out:Path,cli:Path)->dict:
    command_path=out/"PRINT_LAYOUT.commands.json"
    assembled_path=out/"ASSEMBLY.commands.json"
    _save(command_path,plan["solidcraft_print_layout_commands"])
    _save(assembled_path,plan["solidcraft_assembly_transform_commands"])
    native={}
    native["layout"]=_invoke(cli,[
        "run",str(command_path),"--save",str(out/"CASE_PRINT_LAYOUT.solidcraft"),
        "--out",str(out/"CASE_PRINT_LAYOUT.step"),"--results",
        "--json-out",str(out/"LAYOUT_COMMANDS_RESULT.json")],out)
    native["eval_print"]=_invoke(cli,["eval",str(out/"CASE_PRINT_LAYOUT.solidcraft"),
                                         "--json-out",str(out/"CASE_PRINT_EVAL.json")],out)
    dims=plan["case_dimensions_mm"]
    W,D,H=dims["width"],dims["depth"],dims["base_height"]
    lid_t=dims["lid_thickness"]
    lip_h=plan["lid_alignment_mm"]["lip_depth"]
    lx=plan["print_layout_mm"]["lid_offset_x"]
    body=json.loads((out/"CASE_PRINT_EVAL.json").read_text())["bodies"]
    by_name={b["name"]:b for b in body}
    if set(by_name)!={"HS_Casing_Base","HS_Casing_Lid"}:
        raise ValueError("wrong native case body names/count")
    if not _close_bbox(by_name["HS_Casing_Base"]["bbox"],[0,0,0],[W,D,H]):
        raise ValueError("native base bbox invalid")
    if not _close_bbox(by_name["HS_Casing_Lid"]["bbox"],[lx,0,0],[lx+W,D,lid_t+lip_h]):
        raise ValueError("native lid bbox invalid")

    export_steps=[]
    for name in ("Base","Lid"):
        bodyname="HS_Casing_"+name
        export_steps.extend([
            {"command":"file.save_mesh","params":{
                "path":str(out/f"HS_Casing_{name}.stl"),"format":"stl","bodies":[bodyname]}},
            {"command":"file.export","params":{
                "path":str(out/f"HS_Casing_{name}.step"),"format":"step","bodies":[bodyname]}},
        ])
    export_steps.append({"command":"file.save_mesh","params":{
        "path":str(out/"CASE_PRINT_LAYOUT.3mf"),"format":"3mf",
        "bodies":["HS_Casing_Base","HS_Casing_Lid"]}})
    p=out/"EXPORT.commands.json"
    _save(p,{"commands":export_steps})
    native["export"]=_invoke(cli,[
        "run",str(p),"--in",str(out/"CASE_PRINT_LAYOUT.solidcraft"),
        "--results","--json-out",str(out/"EXPORT_COMMANDS_RESULT.json")],out)
    meshes={}
    for name in ("Base","Lid"):
        report=_stl_report(out/f"HS_Casing_{name}.stl")
        original=by_name["HS_Casing_"+name]
        if abs(report["volume_mm3"]-original["volume_mm3"])>max(0.5,original["volume_mm3"]*0.005):
            raise ValueError("meshed solid volume deviates from CAD kernel")
        exp=[W,D,H if name=="Base" else lid_t+lip_h]
        if any(not _compare(a,b,tol=0.03) for a,b in zip(report["size_mm"],exp)):
            raise ValueError("STL size disagrees with conceptual CAD envelope")
        meshes[name]={"report":report,"native_solid_volume_mm3":original["volume_mm3"],
                      "independent_meshing_volume_difference_mm3":round(report["volume_mm3"]-original["volume_mm3"],3)}
    native["mesh_validation"]={"base":meshes["Base"],"lid":meshes["Lid"]}
    native["3mf"]=_3mf_report(out/"CASE_PRINT_LAYOUT.3mf")
    native["assembled"]=_invoke(cli,[
        "run",str(assembled_path),"--in",str(out/"CASE_PRINT_LAYOUT.solidcraft"),
        "--save",str(out/"CASE_ASSEMBLED.solidcraft"),
        "--out",str(out/"CASE_ASSEMBLED.step"),"--results",
        "--json-out",str(out/"ASSEMBLY_COMMANDS_RESULT.json")],out)
    _invoke(cli,["eval",str(out/"CASE_ASSEMBLED.solidcraft"),
                 "--json-out",str(out/"CASE_ASSEMBLED_EVAL.json")],out)
    assembled=json.loads((out/"CASE_ASSEMBLED_EVAL.json").read_text())["bodies"]
    native["assembled_geometry"]=[{"name":b["name"],"bbox":b["bbox"],"volume_mm3":b["volume_mm3"]} for b in assembled]
    by_name_assy={b["name"]:b for b in assembled}
    if (len(by_name_assy)!=2 or not _close_bbox(
        by_name_assy["HS_Casing_Lid"]["bbox"],[0,0,H-lip_h],[W,D,H+lid_t]
    )):
        raise ValueError("assembled lid incorrect alignment/rotation")
    for mode in ("PRINT_LAYOUT","ASSEMBLED"):
        native["preview_"+mode]=_invoke(cli,[
            "snapshot",str(out/f"CASE_{mode}.solidcraft"),"--out",str(out/f"CASE_{mode}.png"),
            "--width","1024","--height","700","--view","iso","--no-grid","--no-axes"
        ],out)
    return native


def _native_partcad(out:Path,plan:dict,pc_bin:Path,solidcraft_cli:Path)->dict:
    pc=_parts_workspace(out,plan)
    common=["--no-ansi","--offline","--telemetry-type","none",
            "--internal-state-dir",str(pc/".pc-state")]
    result={"partcad_package_exists":True}
    result["parts"]=_invoke(pc_bin,common+["list","parts"],pc)
    result["assembly_list"]=_invoke(pc_bin,common+["list","assemblies"],pc)
    result["bom"]=_invoke(pc_bin,common+["bom","-j","casing_assembled"],pc)
    match=re.search(r'(\{\s*"assembly"\s*:\s*"[^"]+"[\s\S]*?\})\s*$',result["bom"]["stdout_tail"])
    if not match:
        raise ValueError("PartCAD BOM JSON not found")
    bom=json.loads(match.group(1))
    counts={x["name"].rsplit(":",1)[-1]:x["count"] for x in bom["items"]}
    if counts!={"casing_base":1,"casing_lid":1} or bom["total"]!=2:
        raise ValueError("PartCAD BOM does not contain exact two casing parts")
    result["bom_assertion"]={"casing_base":1,"casing_lid":1,"physical_owned_donor_count":0}
    exports=pc/"exported"
    exports.mkdir(exist_ok=True)
    result["native_assembly_export"]=_invoke(pc_bin,common+[
        "export","-a","-t","step","-O",str(exports),"casing_assembled"],pc,timeout=250)
    target=exports/"casing_assembled.step"
    if not target.is_file() or target.stat().st_size<1000:
        raise ValueError("PartCAD failed to export assembled real CAD")
    _invoke(solidcraft_cli,["eval",str(target),"--json-out",str(pc/"ASSEMBLED_FROM_PARTCAD_EVAL.json")],pc)
    bodies=json.loads((pc/"ASSEMBLED_FROM_PARTCAD_EVAL.json").read_text())["bodies"]
    source=json.loads((out/"CASE_ASSEMBLED_EVAL.json").read_text())["bodies"]
    expected=sorted(source,key=lambda b:b["volume_mm3"])
    actual=sorted(bodies,key=lambda b:b["volume_mm3"])
    if len(expected)!=2 or len(actual)!=2:
        raise ValueError("PartCAD exported assembly body count wrong")
    comparison=[]
    for x,y in zip(expected,actual):
        ok=_close_bbox(y["bbox"],x["bbox"]["min"],x["bbox"]["max"],tol=.03)
        ok=ok and _compare(y["volume_mm3"],x["volume_mm3"],tol=0.6)
        comparison.append({"within_tolerance":ok,"source_volume":x["volume_mm3"],
                           "partcad_volume":y["volume_mm3"],
                           "source_bbox":x["bbox"],"partcad_bbox":y["bbox"]})
    if not all(x["within_tolerance"] for x in comparison):
        raise ValueError("PartCAD exported casing volume or alignment differs from native SolidCraft")
    result["native_roundtrip_geometry_checked"]=True
    result["roundtrip_comparison"]=comparison
    return result


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--spec",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--solidcraft-cli",type=Path)
    parser.add_argument("--partcad-cli",type=Path)
    args=parser.parse_args()
    if args.partcad_cli and not args.solidcraft_cli:
        parser.error("PartCAD integration requires SolidCraft's independent CAD evaluator")
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/"MECHANICAL_WORKBENCH_REPORT.json").exists():
        raise ValueError("Refusing to overwrite existing verification result")
    spec=json.loads(args.spec.read_text())
    plan=prepare_printed_enclosure(spec)
    _save(args.out/"MECHANICAL_CASING_PLAN.json",plan)
    summary={
        "schema_version":"hardware_splicer.native_printed_enclosure_trial.v1",
        "source_is_declared_concept_not_measured":True,
        "cad_proposal_created":True,
        "native_solidcraft_executed":False,
        "stl_manifold_both_passed":False,
        "3mf_validated":False,
        "partcad_two_part_bom_verified":False,
        "partcad_exported_geometry_verified":False,
        "slicer_executed":False,
        "printer_gcode_produced":False,
        "physical_assembly_verified":False,
        "production_mechanical_release":False,
        "connected_printer_actuated":False,
    }
    if args.solidcraft_cli:
        native=_native_plan(plan,args.out,args.solidcraft_cli.resolve(strict=True))
        summary.update({"native_solidcraft_executed":True,"stl_manifold_both_passed":True,
                        "3mf_validated":native["3mf"]["valid_3mf"],"native_results":native})
    if args.partcad_cli:
        pc=_native_partcad(args.out,plan,args.partcad_cli.resolve(strict=True),
                           args.solidcraft_cli.resolve(strict=True))
        summary.update({"partcad_two_part_bom_verified":True,
                        "partcad_exported_geometry_verified":pc["native_roundtrip_geometry_checked"],
                        "partcad_results":pc})
    paths=[p for p in args.out.rglob("*") if p.is_file() and ".pc-state" not in p.parts]
    summary["actual_output_file_hashes"]={
        str(p.relative_to(args.out)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths) if p.name!="MECHANICAL_WORKBENCH_REPORT.json"
    }
    _save(args.out/"MECHANICAL_WORKBENCH_REPORT.json",summary)
    print(json.dumps({k:v for k,v in summary.items() if k in (
        "native_solidcraft_executed","stl_manifold_both_passed","3mf_validated",
        "partcad_two_part_bom_verified","partcad_exported_geometry_verified",
        "slicer_executed","production_mechanical_release"
    )},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
