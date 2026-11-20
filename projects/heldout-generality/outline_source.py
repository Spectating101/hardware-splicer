"""KiCad-native Edge.Cuts polygonization and explicit mounting strategy.
No component keepouts or physical clearance inferred from a board outline.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import pcbnew

def mm(v):return round(pcbnew.ToMM(v),6)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def loop(chain):
    pts=[(mm(chain.CPoint(i).x),mm(chain.CPoint(i).y))
         for i in range(chain.PointCount())]
    if len(pts)<3 or len(set(pts))<3:raise ValueError("DEGENERATE_OUTLINE")
    return pts
def extract(p):
    board=pcbnew.LoadBoard(str(p))
    polygons=pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(polygons):
        raise ValueError("NATIVE_EDGE_CUTS_CONTOUR_INVALID")
    if polygons.OutlineCount()!=1:
        raise ValueError("MULTIPLE_BOARD_OUTLINE_ISLANDS_NOT_SUPPORTED")
    outer=loop(polygons.Outline(0))
    cutouts=[loop(polygons.Hole(0,i)) for i in range(polygons.HoleCount(0))]
    xs=[x for x,y in outer];ys=[y for x,y in outer]
    bounds={"xmin":min(xs),"ymin":min(ys),"width":round(max(xs)-min(xs),6),
            "height":round(max(ys)-min(ys),6)}
    if bounds["width"]<10 or bounds["height"]<10 or bounds["width"]>250 or bounds["height"]>200:
        raise ValueError("PCB_OUTLINE_OUTSIDE_BOUNDED_TRAY_ENVELOPE")
    mounting=[]
    for f in board.GetFootprints():
        if "MountingHole" not in f.GetFPIDAsString():continue
        pp=list(f.Pads())
        if len(pp)!=1:continue
        pad=pp[0]
        d=mm(pad.GetDrillSize().x)
        if not 1.5<=d<=5 or abs(d-mm(pad.GetDrillSize().y))>.001 or pad.GetNetCode()>0:
            continue
        mounting.append({"ref":f.GetReference(),"x":mm(pad.GetPosition().x),
                         "y":mm(pad.GetPosition().y),"drill":d})
    mounting.sort(key=lambda m:m["ref"])
    # No attempt to invent hole positions from graphical or component evidence.
    if len(mounting)>=3 and len({m["ref"] for m in mounting})==len(mounting):
        strategy="SOURCE_HOLES_PRESENT_NONRETAINING_TRAY"
    elif len(mounting)==1:
        strategy="SINGLE_HOLE_NONRETAINING_GRAVITY_TRAY"
    else:
        strategy="HOLELESS_NONRETAINING_GRAVITY_TRAY"
    return {
        "schema":"hs.native_outlines.v1",
        "original_pcb_sha256":sha(p),
        "outline_source":"native KiCad 9 BOARD.GetBoardPolygonOutlines; tessellated source polygon",
        "edge_cut_contour":outer,"internal_cutouts":cutouts,
        "bounds":bounds,"mounting_holes":mounting,
        "strategy":strategy,
        "geometry_is_tessellated_not_exact_analytic_arc":True,
        "physical_board_thickness":"NOT_MEASURED",
        "populated_component_envelopes":"NOT_VERIFIED",
        "powered_access":"NOT_AUTHORIZED",
        "fabrication_authorized":False,
    }
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--board",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=extract(a.board)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"strategy":result["strategy"],"bounds":result["bounds"],
                      "contour_vertices":len(result["edge_cut_contour"]),
                      "cutouts":len(result["internal_cutouts"]),
                      "mounts":len(result["mounting_holes"])},indent=2))
