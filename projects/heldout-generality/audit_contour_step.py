"""Independent CadQuery BRep audit against independently reloaded KiCad polygon.

No call to source_contour.extract or contour_cad.build; the reference geometry
is independently reconstructed from native inspector output and compared by
boolean symmetric difference to reopened STEP parts, including interior slots.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path
import cadquery as cq

SEAT_Z=3.85
THICKNESS=1.6

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def reference(native):
    outer=native["source_outer_exact_xy"]
    result=cq.Workplane("XY").polyline([tuple(p) for p in outer]).close().extrude(THICKNESS)
    for hole in native["source_cutouts_exact_xy"]:
        result=result.cut(cq.Workplane("XY").polyline([tuple(p) for p in hole]).close().extrude(THICKNESS))
    for m in native["source_mounts"]:
        result=result.cut(cq.Workplane("XY").center(m["x"],m["y"])
                          .circle(m["drill_mm"]/2).extrude(THICKNESS))
    return result.val()

def audit(native:dict,study:dict,models:Path):
    if native.get("status")!="PASS" or study.get("schema")!="hs.native_contour_3d_study.v1":
        raise ValueError("WRONG_STUDY_OR_SOURCE_STATUS")
    if study["source_board_sha256"]!=native["source_sha256"]:
        raise ValueError("SOURCE_DIGEST_CHANGED")
    if study["fabrication_authorized"] is not False or study["physical_measurements"] is not False:
        raise ValueError("PHYSICAL_AUTHORITY_FORGED")
    check_native=reference(native)
    model={}
    for name in ("nominal-unpopulated-PCB","source-outline-cartridge",
                 "common-inspection-dock","inspection-gauge"):
        p=models/(name+".step")
        shape=cq.importers.importStep(str(p))
        if len(shape.solids().vals())!=1 or not shape.val().isValid():
            raise ValueError("STEP_GEOMETRY_NOT_ONE_VALID_SOLID:"+name)
        b=shape.val().BoundingBox()
        model[name]=shape.val()
        if any(abs(q-v)>.0003 for q,v in zip(
          (b.xlen,b.ylen,b.zlen),study["cad"][name]["bbox_mm"])):
            raise ValueError("STEP_BBOX_NOT_AS_CLAIMED:"+name)
        if abs(shape.val().Volume()-study["cad"][name]["volume_mm3"])>.0005:
            raise ValueError("STEP_VOLUME_NOT_AS_CLAIMED:"+name)
    seen=model["nominal-unpopulated-PCB"]
    # This checks actual 3D topology, including cutouts and mounting bores.
    missing=check_native.cut(seen).Volume()
    extra=seen.cut(check_native).Volume()
    if max(missing,extra)>.0005:
        raise ValueError("SOURCE_NATIVE_3D_SYMMETRIC_DIFFERENCE:"+str((missing,extra)))
    native_area=native["source_polygon_area_mm2"]
    expected_volume=(native_area-sum(math.pi*(m["drill_mm"]/2)**2
                        for m in native["source_mounts"]))*THICKNESS
    if abs(seen.Volume()-expected_volume)>.003:
        raise ValueError("SOURCE_CUTOUT_AND_MOUNT_AREA_INCONSISTENT")
    # Pocket must accommodate the BRep board at the claimed height.
    relocated=seen.translate(cq.Vector(0,0,SEAT_Z))
    collision=model["source-outline-cartridge"].intersect(relocated).Volume()
    if collision>.002:
        raise ValueError("SOURCE_BOARD_INTERSECTS_NOMINAL_CARTRIDGE:"+str(collision))
    strategy=("source-hole-registration" if len(native["source_mounts"])>=3
              else "non-clamping-edge-nest")
    if study["mount_strategy"]!=strategy:
        raise ValueError("UNSUPPORTED_OR_INVENTED_MOUNTING_STRATEGY")
    for name,h in study["file_sha256"].items():
        if sha(models/name)!=h:raise ValueError("CAD_OUTPUT_DIGEST_CHANGED:"+name)
    return {
        "schema":"hs.independent_contour_step_audit.v1",
        "status":"PASS",
        "source_sha256":native["source_sha256"],
        "source_outline_vertices":native["source_outer_vertices"],
        "source_internal_cutouts_preserved":native["source_cutout_count"],
        "source_mounts_preserved":len(native["source_mounts"]),
        "mount_strategy":strategy,
        "nominal_board_symmetric_difference_mm3":[round(missing,8),round(extra,8)],
        "nominal_pocket_interference_mm3":round(collision,8),
        "source_nominal_area_mm2":native_area,
        "model_nominal_board_volume_mm3":round(seen.Volume(),5),
        "physical_fit_tested":False,
        "fabrication_authorized":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--native",type=Path,required=True)
    p.add_argument("--study",type=Path,required=True)
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    n=json.loads(a.native.read_text());s=json.loads(a.study.read_text())
    result=audit(n,s,a.models)
    fail={}
    for label in ("wrong_revision","missing_cutout","injected_mount","forged_authority"):
        nn,ss=copy.deepcopy(n),copy.deepcopy(s)
        if label=="wrong_revision":nn["source_sha256"]="0"*64
        elif label=="missing_cutout":
            # With no source cutouts, inject a false interior cutout instead.
            nn["source_cutouts_exact_xy"]=([] if nn["source_cutouts_exact_xy"]
                else [[[-1,-1],[1,-1],[1,1],[-1,1]]])
        elif label=="injected_mount":
            nn["source_mounts"]=[{"ref":"FAKE","x":4,"y":3,"drill_mm":3.2,"net":""}]
        else:ss["fabrication_authorized"]=True
        try:audit(nn,ss,a.models)
        except ValueError as exc:fail[label]={"rejected":True,"reason":str(exc)}
        else:fail[label]={"rejected":False}
    if not all(x["rejected"] for x in fail.values()):
        raise ValueError("ADVERSARIAL_NEGATIVE_CONTROL_ESCAPED")
    result["negative_controls"]=fail
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("STEP INDEPENDENT AUDIT PASS",result["source_outline_vertices"],"vertices",
          result["source_internal_cutouts_preserved"],"cutouts",
          result["mount_strategy"])
