"""Read-only extraction from a real KiCad PCB, using the system pcbnew interpreter."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

def main() -> int:
    import pcbnew as p
    ap=argparse.ArgumentParser()
    ap.add_argument("--pcb",required=True)
    a=ap.parse_args()
    source=Path(a.pcb).resolve()
    board=p.LoadBoard(str(source))
    if board is None: raise SystemExit("Failed to open PCB with this KiCad version")
    u=p.ToMM
    bb=board.GetBoardEdgesBoundingBox()
    bbox={"x_min":u(bb.GetX()),"x_max":u(bb.GetX()+bb.GetWidth()),"y_min":u(bb.GetY()),"y_max":u(bb.GetY()+bb.GetHeight())}
    tracks=[];vias=[]
    for t in board.GetTracks():
        if type(t).__name__=="PCB_VIA":
            vias.append({"x":u(t.GetPosition().x),"y":u(t.GetPosition().y),"diameter_mm":u(t.GetWidth(p.F_Cu)),"net":t.GetNetname(),"via_type":str(t.GetViaType())})
        else:
            # These are native copper-track segments, NOT an autorouted netlist.
            s,e=t.GetStart(),t.GetEnd()
            tracks.append({"x1":u(s.x),"y1":u(s.y),"x2":u(e.x),"y2":u(e.y),"width_mm":u(t.GetWidth()),"net":t.GetNetname(),"layer":t.GetLayerName()})
    pads=[];footprints=[];switches=[]
    for f in board.GetFootprints():
        x,y=u(f.GetPosition().x),u(f.GetPosition().y)
        rec={"ref":f.GetReference(),"value":f.GetValue(),"footprint":f.GetFPIDAsString(),"x":x,"y":y}
        footprints.append(rec)
        ref=f.GetReference()
        if ref.startswith("S") and ("mx" in f.GetValue().lower() or "switch" in f.GetValue().lower() or "sw_push" in f.GetValue().lower()):
            switches.append(rec)
        for pad in f.Pads():
            xpad,ypad=u(pad.GetPosition().x),u(pad.GetPosition().y)
            sz=pad.GetSize()
            pads.append({"ref":ref,"pad":pad.GetNumber(),"x":xpad,"y":ypad,"size_x_mm":u(sz.x),"size_y_mm":u(sz.y),"orientation_degrees":pad.GetOrientationDegrees(),"pad_shape":int(pad.GetShape()),"pad_attribute":int(pad.GetAttribute()),"net":pad.GetNetname(),"layer":pad.GetLayerName()})
    print(json.dumps({
        "source_label":source.name,
        "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_warnings":(["legacy_format_conversion_requires_independent_board_review"] if "(version 4)" in source.read_text(encoding="utf-8",errors="replace")[:100] else []),
        "pcbnew_version":p.Version(),
        "outline_bbox_mm":bbox,
        "zone_count":len(board.Zones()),
        "tracks":tracks,"vias":vias,"pads":pads,"footprints":footprints,"switch_positions":switches
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
