"""Create actual source-bound STEP mounting-carrier + inspection jig.

Not assembled, printed, fitted or electrically probed. Physical operation HOLD.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
import cadquery as cq

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def roundrect(width,height,radius,thickness):
    p=cq.Workplane("XY").rect(width,height).extrude(thickness)
    return p.edges("|Z").fillet(radius)

def make(rec:dict,edited:Path,out:Path):
    if rec.get("schema")!="hs.heldout_mechanical_edit.v1":
        raise ValueError("wrong PCB engineering receipt")
    if sha(edited)!=rec.get("edited_sha256"):
        raise ValueError("PCB_REVISED_HASH_MISMATCH")
    if rec.get("native_drc_error_count")!=0 or rec.get("native_drc_unconnected")!=0:
        raise ValueError("PCB_DRC_NOT_ZERO")
    if rec.get("fabrication_authorized") is not False:
        raise ValueError("INVALID_FABRICATION_AUTHORITY")
    o=rec["outline"]
    w,h,r=o["width"],o["height"],o["radius"]
    if not(20<=w<=80 and 20<=h<=80 and 1<=r<=10):
        raise ValueError("source outline outside bounded fixture envelope")
    holes=sorted(rec["revised_holes"],key=lambda item:item["ref"])
    if len(holes)!=4 or set(q["ref"] for q in holes)!={"H1","H2","H3","H4"}:
        raise ValueError("invalid source hole identity")
    source_centres=[(round(p["x"]-o["x"]-w/2,5),
                     round(o["y"]+h/2-p["y"],5)) for p in holes]
    # Fixture frame: viewed from top, its Y axis is opposite KiCad's Y down.
    gap=.25
    outer=w+16
    outer_h=h+16
    carrier=cq.Workplane("XY").rect(outer,outer_h).extrude(4)
    # Four large 9mm support rings with through-fastener bores; no forced
    # overconstrained registration pins, since physical alignment is untested.
    for (x,y),p in zip(source_centres,holes):
        if not abs(p["drill"]-3.2)<.01:raise ValueError("unsupported drill diameter")
        ring=(cq.Workplane("XY").workplane(offset=4).center(x,y)
              .circle(4.5).circle((p["drill"]+gap)/2).extrude(4))
        carrier=carrier.union(ring)
    carrier=carrier.cut(
        cq.Workplane("XY").pushPoints(source_centres)
        .circle((3.2+gap)/2).extrude(8))
    # This reference represents nominal UNPOPULATED source board, not a real
    # physical PCB. Thickness is assumed and must be measured before fit.
    nominal_thickness=1.6
    board=roundrect(w,h,r,nominal_thickness)
    board=board.cut(cq.Workplane("XY").pushPoints(source_centres)
                    .circle(3.2/2).extrude(nominal_thickness))
    template=cq.Workplane("XY").rect(outer,outer_h).extrude(3)
    template=template.cut(cq.Workplane("XY").pushPoints(source_centres)
                          .circle((3.2+gap)/2).extrude(3))
    parts={"fixture-carrier":carrier,"hole-inspection-template":template,
           "nominal-unpopulated-board":board}
    out.mkdir(parents=True,exist_ok=False)
    for name,solid in parts.items():
        path=out/(name+".step")
        cq.exporters.export(solid,str(path))
        reopened=cq.importers.importStep(str(path))
        if len(reopened.solids().vals())!=1 or not reopened.val().isValid():
            raise ValueError("STEP_IMPORT_SOLID_INVALID:"+name)
        if name!="nominal-unpopulated-board":
            cq.exporters.export(solid,str(out/(name+".stl")))
    compound=cq.Compound.makeCompound([
        carrier.val(),
        board.val().translate(cq.Vector(0,0,10)),
        template.val().translate(cq.Vector(0,0,20))])
    cq.exporters.export(compound,str(out/"exploded-UNASSEMBLED.step"))
    with (out/"hole-map.csv").open("w",newline="") as hfile:
        writer=csv.writer(hfile)
        writer.writerow(["source_hole_ref","source_x_mm","source_y_mm",
                         "model_x_mm","model_y_mm","source_drill_mm","template_dia_mm",
                         "physical_fit_validated"])
        for p,(x,y) in zip(holes,source_centres):
            writer.writerow([p["ref"],p["x"],p["y"],x,y,p["drill"],3.2+gap,"NO"])
    with (out/"candidate-bom.csv").open("w",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["part","qty","candidate","physical_status"])
        writer.writerow(["carrier",1,"nonconductive polymer, dimensions to be independently checked","UNBUILT"])
        writer.writerow(["hole template",1,"3D printed or machined, 3.45mm nominal guide diameter","UNBUILT"])
        writer.writerow(["M3 insulated standoff / bolt set",4,"operator selection, proper head clearance required","UNSOURCED"])
        writer.writerow(["PCB specimen",1,"source board revision only, not actual constructed board","UNBUILT"])
    artifacts=sorted(str(p.relative_to(out)) for p in out.iterdir() if p.is_file())
    result={
        "schema":"hs.heldout_mount_fixture_design.v1",
        "source_original_sha256":rec["source_sha256"],
        "source_modified_sha256":sha(edited),
        "source_outline":o,"original_holes":rec["original_holes"],
        "modified_holes":holes,"model_hole_centres_mm":source_centres,
        "nominal_clearance_diameter_mm":3.45,
        "nominal_board_thickness_mm":nominal_thickness,
        "source_library_footprints_not_updated":True,
        "STEP_validated_against_source_coordinates":False,
        "source_to_step_independent_audit":"PENDING",
        "physical_status":"UNBUILT_UNMEASURED",
        "fabrication_authorized":False,
        "artifacts_sha256":{name:sha(out/name) for name in artifacts},
    }
    (out/"fixture-receipt.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--edit-receipt",type=Path,required=True)
    p.add_argument("--edited-pcb",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(make(json.loads(a.edit_receipt.read_text()),a.edited_pcb,a.out),indent=2))
