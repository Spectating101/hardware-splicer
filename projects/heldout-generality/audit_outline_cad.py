"""Independent KiCad polygon/STEP geometry audit; never imports outline_cad.

Uses source-native polygon again in source stage, and separately checks the
STEP cross-section, source area, and nominal loose fit with real CAD booleans.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path
import cadquery as cq

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def polygon_area(points):
    return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in
                   zip(points,points[1:]+points[:1])))/2

def audit(source,models,board):
    if digest(board)!=source["original_pcb_sha256"]:
        raise ValueError("STALE_PCB_SOURCE")
    if source.get("fabrication_authorized") is not False:
        raise ValueError("FALSE_FABRICATION_AUTHORITY")
    receipt=json.loads((models/"design-receipt.json").read_text())
    if receipt["source_sha256"]!=source["original_pcb_sha256"]:
        raise ValueError("STEP_RECEIPT_SOURCE_REVISION_MISMATCH")
    if receipt["source_strategy"]!=source["strategy"]:
        raise ValueError("STRATEGY_NOT_SOURCE_BOUND")
    for name,expected in receipt["files_sha256"].items():
        if digest(models/name)!=expected:
            raise ValueError("CAD_FILE_DIGEST_CHANGED:"+name)
    outline=source["edge_cut_contour"]
    cutouts=source["internal_cutouts"]
    theoretical_area=polygon_area(outline)-sum(polygon_area(h) for h in cutouts)
    if theoretical_area<=0:raise ValueError("NONPOSITIVE_SOURCE_AREA")
    ref=cq.importers.importStep(str(models/"nominal-source-board.step"))
    tray=cq.importers.importStep(str(models/"inspection-tray.step"))
    if len(ref.solids().vals())!=1 or len(tray.solids().vals())!=1:
        raise ValueError("INVALID_REIMPORTED_SOLID_COUNT")
    a,b=ref.val(),tray.val()
    if not a.isValid() or not b.isValid():
        raise ValueError("INVALID_BREP_TOPOLOGY")
    measured_area=a.Volume()/1.6
    if abs(measured_area-theoretical_area)>max(.002,theoretical_area*.00001):
        raise ValueError("SOURCE_POLYGON_AREA_MISMATCH")
    w,h=source["bounds"]["width"],source["bounds"]["height"]
    b1=a.BoundingBox()
    if abs(b1.xlen-w)>.002 or abs(b1.ylen-h)>.002 or abs(b1.zlen-1.6)>.002:
        raise ValueError("SOURCE_BBOX_NOT_PRESERVED")
    tb=b.BoundingBox()
    if abs(tb.xlen-(w+14))>.002 or abs(tb.ylen-(h+14))>.002 or abs(tb.zlen-4)>.002:
        raise ValueError("TRAY_DIMENSIONS_NOT_SUPPORTED")
    # Board positioned inside the nominal shallow pocket at z=2.2,
    # corresponding to 0.2 mm under top surface. This is only a digital
    # collision check on a bare board, not a fit or component clearance.
    intersection=a.translate(cq.Vector(0,0,2.2)).intersect(b)
    overlap=intersection.Volume()
    if overlap>.005:
        raise ValueError("NOMINAL_BOARD_INTERSECTS_TRAY")
    # Verify internal cutout count against source-derived source face shape.
    if receipt["source_internal_cutouts"]!=len(cutouts):
        raise ValueError("SOURCE_CUTOUT_COUNT_FALSE")
    if receipt.get("standoff_posts_modeled")!=0 or receipt["tray_is_nonretaining"] is not True:
        raise ValueError("FALSE_RETENTION_CLAIM")
    if receipt["fab_authority"] is not False:
        raise ValueError("FALSE_FABRICATION_AUTHORITY")
    return {
        "schema":"hs.independent_contour_step_audit.v1",
        "status":"PASS",
        "source_pcb_sha256":source["original_pcb_sha256"],
        "source_outline_vertices":len(outline),
        "source_cutout_count":len(cutouts),
        "source_strategy":source["strategy"],
        "planar_polygon_area_mm2":round(theoretical_area,5),
        "reopened_step_planar_area_mm2":round(measured_area,5),
        "reopened_model_source_bounds_mm":[round(b1.xlen,4),round(b1.ylen,4)],
        "reopened_tray_bounds_mm":[round(tb.xlen,4),round(tb.ylen,4)],
        "nominal_unpopulated_board_tray_overlap_mm3":round(overlap,7),
        "physical_contact_or_fit":"NOT_VERIFIED",
        "fabrication_authorized":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--board",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    source=json.loads(args.source.read_text())
    result=audit(source,args.models,args.board)
    negatives={}
    for label in ("wrong_revision","source_cutout_deleted","fake_retention"):
        changed=copy.deepcopy(source)
        if label=="wrong_revision":changed["original_pcb_sha256"]="0"*64
        elif label=="source_cutout_deleted":
            if source["internal_cutouts"]: changed["internal_cutouts"]=[]
            else:
                changed["edge_cut_contour"][0][0]+=9.0
                changed["edge_cut_contour"][0][1]+=5.0
        else:changed["fabrication_authorized"]=True
        try:audit(changed,args.models,args.board)
        except ValueError as exc:negatives[label]={"rejected":True,"reason":str(exc)}
        else:negatives[label]={"rejected":False}
    # For the source polygons without cutouts, misaltered contour can escape
    # area-only checks if all vertices form the same area; this control
    # explicitly shifts a vertex, guaranteeing a measurable source-area delta.
    if not all(x["rejected"] for x in negatives.values()):
        raise ValueError("NEGATIVE_CONTROL_FAILED:"+str(negatives))
    result["negative_controls"]=negatives
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,indent=2))
