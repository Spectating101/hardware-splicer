"""Native KiCad 9 single-outline polygon extraction with real internal cutouts.

Uses BOARD.GetBoardPolygonOutlines (KiCad's own stitched Edge.Cuts geometry).
No bbox-as-outline substitution; arcs are discretized by KiCad, so the result
is a *polygonized* approximation with explicit fidelity limits.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import pcbnew

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def mill(v):return round(pcbnew.ToMM(v),6)

def extract(path:Path):
    path=path.resolve(strict=True)
    board=pcbnew.LoadBoard(str(path))
    polygon=pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(polygon):
        raise ValueError("NATIVE_KICAD_EDGE_CUTS_INVALID")
    if polygon.OutlineCount()!=1:
        raise ValueError("UNSUPPORTED_MULTIPLE_DISCONNECTED_BOARD_OUTLINES")
    if polygon.HoleCount(0)>10:
        raise ValueError("UNSUPPORTED_EXCESSIVE_INTERIOR_CUTOUTS")
    def ring(chain):
        pts=[(mill(chain.CPoint(i).x),mill(chain.CPoint(i).y))
             for i in range(chain.PointCount())]
        if len(set(pts))<3 or len(pts)>500:
            raise ValueError("UNSUPPORTED_NATIVE_CONTOUR_COMPLEXITY")
        if pts[0]==pts[-1]:pts.pop()
        return pts
    outer=ring(polygon.Outline(0))
    cutouts=[ring(polygon.Hole(0,i)) for i in range(polygon.HoleCount(0))]
    x0=min(x for x,y in outer);x1=max(x for x,y in outer)
    y0=min(y for x,y in outer);y1=max(y for x,y in outer)
    w,h=round(x1-x0,6),round(y1-y0,6)
    if not(10<=w<=150 and 10<=h<=130):
        raise ValueError("BOARD_OUTSIDE_CARTRIDGE_ENVELOPE")
    mid=((x0+x1)/2,(y0+y1)/2)
    def coords(points):
        return [[round(x-mid[0],6),round(mid[1]-y,6)] for x,y in points]
    # All outer points and nested cutouts are transformed with exactly the same frame.
    outer_local=coords(outer)
    cutout_local=[coords(c) for c in cutouts]
    mounts=[]
    for fp in board.GetFootprints():
        if not("MountingHole" in fp.GetFPIDAsString() or fp.GetReference().startswith("H")):
            continue
        for pad in fp.Pads():
            dx,dy=mill(pad.GetDrillSize().x),mill(pad.GetDrillSize().y)
            if dx<=1 or abs(dx-dy)>.001 or pad.GetNetCode()>0:continue
            x,y=mill(pad.GetPosition().x),mill(pad.GetPosition().y)
            mounts.append({"ref":fp.GetReference(),"x":round(x-mid[0],6),
                           "y":round(mid[1]-y,6),"drill_mm":dx,"net":pad.GetNetname()})
    mounts.sort(key=lambda x:x["ref"])
    # Native area is signed by KiCad ring orientation, polygon set area uses holes.
    area_mm2=round(polygon.Area()/1e12,5)
    def shoelace(p):
        return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-
                       p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))/2)
    local_area=shoelace(outer_local)-sum(shoelace(h) for h in cutout_local)
    if abs(local_area-area_mm2)>0.015:
        raise ValueError("NATIVE_POLYGON_AREA_NOT_PRESERVED")
    return {
        "schema":"hs.source_edgecuts_polygon.v1",
        "pcb_sha256":sha(path),
        "original_pcb_filename":path.name,
        "source_method":"KiCad pcbnew BOARD.GetBoardPolygonOutlines()",
        "source_outline_discretization":"KiCad native stitched polygon approx; not analytic arcs",
        "source_outline_vertices":len(outer_local),
        "native_internal_edgecuts_cutouts":len(cutout_local),
        "native_board_polygon_area_mm2":area_mm2,
        "recomputed_polygon_area_mm2":round(local_area,5),
        "bbox_source_mm":[x0,y0,w,h],
        "reference_frame":"XY centred on outer board bbox, Y inverted from pcbnew, millimetres",
        "outer_xy":outer_local,
        "cutout_xy":cutout_local,
        "source_mounts":mounts,
        "mounting_strategy":("source-hole-registration" if len(mounts)>=3
                             else "non-clamping-edge-nest"),
        "physical_fit_tested":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=extract(args.source)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("outer_xy","cutout_xy")},indent=2))
