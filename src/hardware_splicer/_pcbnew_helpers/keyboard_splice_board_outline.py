"""Extract KiCad's actual arc-tessellated Edge.Cuts board polygon.

No geometric guess from a bounding rectangle is permitted. Original third
party PCB is read-only and bound by file digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pcb",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    raw=args.pcb.read_bytes()
    board=p.LoadBoard(str(args.pcb.resolve()))
    if board is None:
        raise ValueError("source KiCad board cannot be parsed")
    polygons=p.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(polygons):
        raise ValueError("native KiCad Edge.Cuts cannot form a closed board outline")
    if polygons.OutlineCount()!=1 or polygons.HoleCount(0)!=0:
        raise ValueError("multi-piece or slotted original board needs separate outline support")
    outline=polygons.COutline(0)
    coords=[
        [round(p.ToMM(outline.CPoint(i).x),6),
         round(p.ToMM(outline.CPoint(i).y),6)]
        for i in range(outline.PointCount())
    ]
    if len(coords)<4 or len(coords)>20000:
        raise ValueError("invalid or excessive source outline tessellation")
    result={
        "schema":"hs.original-kicad-board-edge-outline.v1",
        "source_file_sha256":hashlib.sha256(raw).hexdigest(),
        "source_name":args.pcb.name,
        "native_kicad_version":p.Version(),
        "tessellated_edge_cuts_points_mm":coords,
        "source_edge_geometry_measured":True,
        "actual_discarded_donor_measured":False,
        "fabrication_release":"REFERENCE_OUTLINE_ONLY",
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("SOURCE_BOARD_OUTLINE",len(coords),"points")
    print("HASH",result["source_file_sha256"])


if __name__=="__main__":
    main()
