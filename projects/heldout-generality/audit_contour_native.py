"""Independent, unmodified KiCad source contour replay (does not import extractor)."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import pcbnew

def mm(v):return round(pcbnew.ToMM(v),6)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(source:Path,layout:dict):
    original=pcbnew.LoadBoard(str(source))
    poly=pcbnew.SHAPE_POLY_SET()
    if not original.GetBoardPolygonOutlines(poly):raise ValueError("SOURCE_NATIVE_EDGE_FAILURE")
    if poly.OutlineCount()!=1:raise ValueError("SOURCE_MULTIPLE_OUTLINES")
    def points(chain):
        return [(mm(chain.CPoint(i).x),mm(chain.CPoint(i).y))
                for i in range(chain.PointCount())]
    outer=points(poly.Outline(0))
    if outer and outer[0]==outer[-1]:outer.pop()
    holes=[points(poly.Hole(0,i)) for i in range(poly.HoleCount(0))]
    for ring in holes:
        if ring and ring[0]==ring[-1]:ring.pop()
    cx=(min(x for x,y in outer)+max(x for x,y in outer))/2
    cy=(min(y for x,y in outer)+max(y for x,y in outer))/2
    frame=lambda ring:[[round(x-cx,6),round(cy-y,6)] for x,y in ring]
    if frame(outer)!=layout["outer_xy"] or [frame(h) for h in holes]!=layout["cutout_xy"]:
        raise ValueError("SOURCE_OUTLINE_OR_HOLE_COORDINATES_NOT_PRESERVED")
    orig_mounts=[]
    for f in original.GetFootprints():
        if not("MountingHole" in f.GetFPIDAsString() or f.GetReference().startswith("H")):continue
        for p in f.Pads():
            dx,dy=mm(p.GetDrillSize().x),mm(p.GetDrillSize().y)
            if dx<=1 or abs(dx-dy)>.001 or p.GetNetCode()>0:continue
            orig_mounts.append({"ref":f.GetReference(),
                         "x":round(mm(p.GetPosition().x)-cx,6),
                         "y":round(cy-mm(p.GetPosition().y),6),
                         "drill_mm":dx,"net":p.GetNetname()})
    orig_mounts.sort(key=lambda a:a["ref"])
    if orig_mounts!=layout["source_mounts"]:
        raise ValueError("MOUNTING_PAD_SOURCE_MISMATCH")
    src_area=round(poly.Area()/1e12,5)
    if abs(src_area-layout["native_board_polygon_area_mm2"])>.0001:
        raise ValueError("NATIVE_PCB_AREA_CHANGED")
    if sha(source)!=layout["pcb_sha256"]:
        raise ValueError("SOURCE_REVISION_MISMATCH")
    return {
        "schema":"hs.independent_native_contour_audit.v1",
        "source_sha256":sha(source),
        "source_polygon_area_mm2":src_area,
        "source_outer_vertices":len(outer),
        "source_cutout_count":len(holes),
        "source_mounts":orig_mounts,
        "source_cutouts_exact_xy":layout["cutout_xy"],
        "source_outer_exact_xy":layout["outer_xy"],
        "status":"PASS","fabrication_authorized":False,
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--layout",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    receipt=audit(args.source,json.loads(args.layout.read_text()))
    args.out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("NATIVE SOURCE AUDIT PASS",receipt["source_outer_vertices"],
          "outer vertices",receipt["source_cutout_count"],"holes")
