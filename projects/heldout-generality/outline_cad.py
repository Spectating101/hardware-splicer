"""Build native STEP from exact KiCad polygonization for an UNPOWERED inspection tray.
Designed for an unpopulated board reference. Never assert a physical fit.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import cadquery as cq

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def centered(loop,bounds):
    x0=bounds["xmin"]+bounds["width"]/2
    y0=bounds["ymin"]+bounds["height"]/2
    return [(round(x-x0,6),round(y0-y,6)) for x,y in loop]
def section(vertices,height):
    return cq.Workplane("XY").polyline(vertices).close().extrude(height)

def build(source,board,out):
    if digest(board)!=source["original_pcb_sha256"]:
        raise ValueError("STALE_BOARD_SOURCE_DIGEST")
    if source.get("fabrication_authorized") is not False:
        raise ValueError("INVALID_PHYSICAL_AUTHORITY")
    b=source["bounds"]
    contour=centered(source["edge_cut_contour"],b)
    holes=[centered(h,b) for h in source["internal_cutouts"]]
    w,h=b["width"],b["height"]
    original=section(contour,1.6)
    for cut in holes:original=original.cut(section(cut,1.6))
    if len(original.solids().vals())!=1 or not original.val().isValid():
        raise ValueError("NONMANIFOLD_SOURCE_OUTLINE")
    base=cq.Workplane("XY").rect(w+14,h+14).extrude(4)
    # A shallow nominal seat. No claim that physical copper/features fit.
    # The 0.6 mm wall clearance is only a geometry assumption.
    cavity=cq.Workplane("XY").polyline(contour).close().offset2D(.6).extrude(2)
    cavity=cavity.translate((0,0,2))
    # Cutout islands are intentionally NOT retained in the cavity: simplified
    # full-outline clearance prevents trapped protrusions under unknown parts.
    tray=base.cut(cavity)
    if len(tray.solids().vals())!=1 or not tray.val().isValid():
        raise ValueError("NONMANIFOLD_TRAY")
    models={"nominal-source-board":original,"inspection-tray":tray}
    out.mkdir(parents=True,exist_ok=False)
    for name,model in models.items():
        cq.exporters.export(model,str(out/(name+".step")))
        cq.exporters.export(model,str(out/(name+".stl")))
        reread=cq.importers.importStep(str(out/(name+".step")))
        if len(reread.solids().vals())!=1 or not reread.val().isValid():
            raise ValueError("STEP_REIMPORT_FAILURE:"+name)
    evidence={
        "schema":"hs.source_contour_cad.v1",
        "source_sha256":source["original_pcb_sha256"],
        "source_outline_vertices":len(contour),
        "source_internal_cutouts":len(holes),
        "source_polygon_area_mm2":round(original.val().Volume()/1.6,5),
        "source_strategy":source["strategy"],
        "standoff_posts_modeled":0,
        "tray_is_nonretaining":True,
        "nominal_board_thickness_mm":1.6,
        "tray_cavity_clearance_mm":.6,
        "design_spec":"Unpopulated loose board shape in a gravity tray, without electrical contacts or measured component keepouts",
        "fixture_mechanical_fit":"UNTESTED",
        "source_device_energization":"NOT_AUTHORIZED",
        "fab_authority":False,
        "files_sha256":{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    (out/"design-receipt.json").write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
    return evidence

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--outline",type=Path,required=True)
    p.add_argument("--board",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=build(json.loads(a.outline.read_text()),a.board,a.out)
    print(json.dumps({k:v for k,v in r.items() if k!="files_sha256"},indent=2))
