"""Independent inspection of native KiCad audit + reimported STEP surfaces.

Does not import the CAD generator or use its point-placement functions.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from pathlib import Path
import cadquery as cq

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def circles(path,radius,z):
    solid=cq.importers.importStep(str(path))
    if len(solid.solids().vals())!=1 or not solid.val().isValid():
        raise ValueError("STEP_BREP_IMPORT_FAILED:"+str(path))
    found=set()
    for edge in solid.edges().vals():
        if edge.geomType()!="CIRCLE" or abs(edge.radius()-radius)>1e-4:continue
        p=edge.arcCenter()
        if abs(p.z-z)<=1e-4:
            found.add((round(p.x,3),round(p.y,3)))
    return found

def audit(model_dir:Path,native:dict,design:dict,fixture:dict):
    if native["status"]!="PASS" or not native["original_outline_preserved"]:
        raise ValueError("NATIVE_BOARD_AUDIT_NOT_PASS")
    if native["source_sha256"]!=fixture["source_original_sha256"]:
        raise ValueError("ORIGINAL_PCB_REVISION_MISMATCH")
    if native["revised_sha256"]!=fixture["source_modified_sha256"]:
        raise ValueError("REVISED_PCB_REVISION_MISMATCH")
    if design["edited_sha256"]!=native["revised_sha256"]:
        raise ValueError("EDITED_PCB_RECEIPT_MISMATCH")
    if fixture["fabrication_authorized"] is not False or design["fabrication_authorized"] is not False:
        raise ValueError("FALSE_FABRICATION_AUTHORITY")
    if fixture["source_library_footprints_not_updated"] is not True:
        raise ValueError("FOOTPRINT_GAP_SUPPRESSED")
    source_edges=native["outline_edges"]
    xy=[(x,y) for _,sx,sy,ex,ey in source_edges for x,y in ((sx,sy),(ex,ey))]
    x0,y0=min(a for a,b in xy),min(b for a,b in xy)
    width=round(max(a for a,b in xy)-x0,3)
    height=round(max(b for a,b in xy)-y0,3)
    dr=design["outline"]
    if abs(dr["width"]-width)>.001 or abs(dr["height"]-height)>.001:
        raise ValueError("SOURCE_OUTLINE_DIMENSIONS_DISAGREE")
    expected={
        (round(p["x"]-x0-width/2,3),
         round(y0+height/2-p["y"],3))
        for p in native["edited_holes"].values()
    }
    if len(expected)!=4:raise ValueError("DUPLICATE_SOURCE_HOLE_GEOMETRY")
    claimed={tuple(round(v,3) for v in pair)
             for pair in fixture["model_hole_centres_mm"]}
    if claimed!=expected:
        raise ValueError("CLAIMED_MODEL_HOLES_DO_NOT_MATCH_NATIVE_SOURCE")
    def assert_holes(filename,radius,levels):
        for z in levels:
            found=circles(model_dir/filename,radius,z)
            if found!=expected:
                raise ValueError("STEP_SOURCE_HOLE_GEOMETRY_MISMATCH:"+filename+
                                 " z="+str(z)+" found="+str(found)+" expected="+str(expected))
    assert_holes("nominal-unpopulated-board.step",1.6,(0,1.6))
    assert_holes("hole-inspection-template.step",1.725,(0,3))
    assert_holes("fixture-carrier.step",1.725,(0,8))
    # Additional, independent physical dimensions of the reimported BRep.
    shape=cq.importers.importStep(str(model_dir/"nominal-unpopulated-board.step")).val()
    b=shape.BoundingBox()
    if any(abs(value-expected_dimension)>.001 for value,expected_dimension
           in ((b.xlen,width),(b.ylen,height),(b.zlen,1.6))):
        raise ValueError("STEP_BARE_BOARD_BOUNDING_DIMS_DO_NOT_MATCH_SOURCE")
    for name in ("fixture-carrier.step","hole-inspection-template.step",
                 "nominal-unpopulated-board.step","exploded-UNASSEMBLED.step"):
        p=model_dir/name
        if not p.exists():raise ValueError("MISSING_NATIVE_CAD_OUTPUT:"+name)
        if name!="exploded-UNASSEMBLED.step" and len(cq.importers.importStep(str(p)).solids().vals())!=1:
            raise ValueError("BAD_CAD_SOLID_COUNT")
    for name,expected_hash in fixture["artifacts_sha256"].items():
        if sha(model_dir/name)!=expected_hash:
            raise ValueError("CAD_EXPORT_BYTES_CHANGED:"+name)
    return {"schema":"hs.heldout_mount_step_independent_audit.v1",
            "status":"PASS","original_pcb_sha256":native["source_sha256"],
            "revised_pcb_sha256":native["revised_sha256"],
            "reopened_source_mapped_holes":len(expected),
            "source_dimension_mm":[width,height],"source_drill_mm":3.2,
            "guide_clearance_mm":3.45,
            "source_footprint_library_alignment":"REVIEW_HOLD",
            "mechanical_contact_or_fit_measurement":"NOT_PERFORMED",
            "electrical_powered_measurement":"NOT_PERFORMED",
            "fabrication_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--native-audit",type=Path,required=True)
    p.add_argument("--edit-receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    load=lambda p:json.loads(p.read_text())
    native,design,fixture=load(a.native_audit),load(a.edit_receipt),load(a.models/"fixture-receipt.json")
    result=audit(a.models,native,design,fixture)
    # Negative controls are not a second generator or fake PDF result.
    negatives={}
    for kind in ("wrong_pcb_revision","shifted_reported_hole","fabrication_promotion"):
        n,d,f=copy.deepcopy(native),copy.deepcopy(design),copy.deepcopy(fixture)
        if kind=="wrong_pcb_revision":n["revised_sha256"]="0"*64
        elif kind=="shifted_reported_hole":f["model_hole_centres_mm"][0][0]+=.8
        else:f["fabrication_authorized"]=True
        try:audit(a.models,n,d,f)
        except ValueError as err:negatives[kind]={"rejected":True,"reason":str(err)}
        else:negatives[kind]={"rejected":False}
    if not all(q["rejected"] for q in negatives.values()):
        raise ValueError("NEGATIVE_CONTROL_NOT_REJECTED")
    result["negative_controls"]=negatives
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,indent=2))
