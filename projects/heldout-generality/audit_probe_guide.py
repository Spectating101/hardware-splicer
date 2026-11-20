"""Independent source-bound STEP probe-guide verification via reopened CAD solid."""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path
import cadquery as cq

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(layout,revision,tap,tap_audit,model,model_dir):
    if layout["pcb_sha256"]!=revision or tap["edited_sha256"]!=revision:
        raise ValueError("REVISED_PCB_DIGEST_CONFLICT")
    if tap_audit["revised_sha256"]!=revision or tap_audit["status"]!="PASS":
        raise ValueError("NATIVE_ELECTRICAL_AUDIT_NOT_VERIFIED")
    if model["source_edited_pcb_sha256"]!=revision:
        raise ValueError("CAD_SOURCE_REVISION_STALE")
    if model["nominal_test_pad_diameter_mm"]!=tap_audit.get("exposed_testpoint_diameter_mm"):
        raise ValueError("SOURCE_TESTPOINT_DIAMETER_DISAGREES_WITH_GUIDE")
    if any(d.get("fabrication_authorized") is not False for d in (tap,tap_audit,model)):
        raise ValueError("FALSE_PHYSICAL_OPERATION_AUTHORITY")
    x0,y0,w,h=layout["bbox_source_mm"]
    ax,ay=tap_audit["new_access_xy"]
    x=round(ax-x0-w/2,6); y=round(y0+h/2-ay,6)
    if [x,y]!=model["probe_guide_local_xy_mm"]:
        raise ValueError("CLAIMED_PROBE_XY_DISAGREES_WITH_SOURCE")
    p=model_dir/"source-bound-signal-probe-plate.step"
    imported=cq.importers.importStep(str(p))
    if len(imported.solids().vals())!=1 or not imported.val().isValid():
        raise ValueError("REOPENED_PROBE_STEP_INVALID")
    radius=model["bore_diameter_mm"]/2
    edges={(round(edge.arcCenter().x,4),round(edge.arcCenter().y,4),
            round(edge.arcCenter().z,4))
           for edge in imported.edges().vals() if edge.geomType()=="CIRCLE"
           and abs(edge.radius()-radius)<1e-4}
    expected={(round(x,4),round(y,4),0.),
              (round(x,4),round(y,4),model["nominal_plate_height_mm"])}
    if not expected.issubset(edges):
        raise ValueError("STEP_SOURCE_PROBE_BORE_NOT_AT_EXPECTED_XY")
    reference=cq.Workplane("XY").polyline([tuple(pt) for pt in layout["outer_xy"]]).close().extrude(
        model["nominal_plate_height_mm"])
    for hole in layout["cutout_xy"]:
        reference=reference.cut(cq.Workplane("XY").polyline([tuple(pt) for pt in hole]).close().extrude(
            model["nominal_plate_height_mm"]))
    reference=reference.cut(cq.Workplane("XY").center(x,y).circle(radius).extrude(model["nominal_plate_height_mm"]))
    miss=reference.val().cut(imported.val()).Volume()
    extra=imported.val().cut(reference.val()).Volume()
    if max(miss,extra)>.0001:
        raise ValueError("STEP_PLATE_VS_SOURCE_BOOLEAN_DIFFERENCE")
    for filename,digest in model["files_sha256"].items():
        if sha(model_dir/filename)!=digest:raise ValueError("PROBE_CAD_BYTES_CHANGED")
    if abs(imported.val().Volume()-model["reimported_step_volume_mm3"])>.0001:
        raise ValueError("UNVERIFIED_CAD_VOLUME")
    return {"schema":"hs.independent_probe_guide_audit.v1","status":"PASS",
            "revised_pcb_sha256":revision,"signal_net":tap["source_anchor_net"],
            "source_testpoint":tap["new_testpoint"],"model_hole_centre_mm":[x,y],
            "modeled_bore_diameter_mm":model["bore_diameter_mm"],
            "source_cutouts_preserved":len(layout["cutout_xy"]),
            "actual_step_symmetric_difference_mm3":[round(miss,9),round(extra,9)],
            "physical_probe_contact":"NOT_PERFORMED","fabrication_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("layout","tap","tap-audit","model","revised-pcb","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=vars(p.parse_args())
    read=lambda p:json.loads(p.read_text())
    l,t,n=read(a["layout"]),read(a["tap"]),read(a["tap_audit"])
    model=read(a["model"]/"probe-plate-receipt.json")
    revision=sha(a["revised_pcb"])
    result=inspect(l,revision,t,n,model,a["model"])
    negatives={}
    for name in ("wrong_pcb","misplaced_bore","invented_source_cutout","false_fabrication"):
        ll,tt,nn,mm=copy.deepcopy(l),copy.deepcopy(t),copy.deepcopy(n),copy.deepcopy(model)
        r=revision
        if name=="wrong_pcb":r="0"*64
        elif name=="misplaced_bore":mm["probe_guide_local_xy_mm"][0]+=1
        elif name=="invented_source_cutout":
            if ll["cutout_xy"]:
                ll["cutout_xy"]=[]
            else:
                # A no-cutout board needs a *real* negative mutation: erasing
                # zero existing cutouts is a no-op that falsely fails the test.
                ll["outer_xy"][0][0]+=3.0
                ll["outer_xy"][0][1]+=5.0
        else:mm["fabrication_authorized"]=True
        try:inspect(ll,r,tt,nn,mm,a["model"])
        except ValueError as exc:negatives[name]={"rejected":True,"reason":str(exc)}
        else:negatives[name]={"rejected":False}
    if not all(v["rejected"] for v in negatives.values()):
        raise ValueError("NEGATIVE_PROBE_CAD_CONTROL_ESCAPED")
    result["adversarial_controls"]=negatives
    a["out"].write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,indent=2))
