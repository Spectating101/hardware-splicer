"""Read-only extraction from a real KiCad PCB, using the system pcbnew interpreter."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
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
        if type(t).__name__=="PCB_ARC":
            # The downstream cut/island model consumes straight segments.
            # An arc's endpoints define a chord, not its copper geometry;
            # silently substituting that chord can miss an actual cut hit.
            raise ValueError(
                "Unsupported curved copper PCB_ARC in keyboard cut/topology extraction; "
                "arc geometry must be supported before this PCB can be modeled"
            )
        if type(t).__name__=="PCB_VIA":
            vias.append({"x":u(t.GetPosition().x),"y":u(t.GetPosition().y),"diameter_mm":u(t.GetWidth(p.F_Cu)),"net":t.GetNetname(),"via_type":str(t.GetViaType())})
        else:
            # These are native copper-track segments, NOT an autorouted netlist.
            s,e=t.GetStart(),t.GetEnd()
            tracks.append({"x1":u(s.x),"y1":u(s.y),"x2":u(e.x),"y2":u(e.y),"width_mm":u(t.GetWidth()),"net":t.GetNetname(),"layer":t.GetLayerName()})
    pads=[];footprints=[];switches=[]
    warnings=[]
    # Original PCB vendors use K*, S*, SW*, or MX* key refs. Footprint
    # identities are stronger evidence than a source-specific reference.
    keyboard_footprint = re.compile(
        r"(?i)(?:cherry[_ -]?mx|mxonly|mx1a|mx[_-]?alps|"
        r"sw[_-]?choc|choc[_ -]?(?:switch|v[12]|mini)|pg135[03]|mx[_-]?[0-9]u)"
    )
    for f in board.GetFootprints():
        x,y=u(f.GetPosition().x),u(f.GetPosition().y)
        rec={"ref":f.GetReference(),"value":f.GetValue(),"footprint":f.GetFPIDAsString(),"x":x,"y":y}
        footprints.append(rec)
        ref=f.GetReference()
        identity=f.GetFPIDAsString()
        value=f.GetValue()
        # A library nickname can apply to every item from a vendor, including
        # jacks, power switches and logos. Classify the footprint item itself.
        item_name=identity.rsplit(":", 1)[-1]
        known_switch=bool(keyboard_footprint.search(item_name))
        is_key=known_switch
        if not is_key and re.fullmatch(r"(?i)MX[0-9]+",ref):
            is_key=bool("mx" in value.lower() or "mx" in identity.lower())
        if not is_key and ref.upper().startswith(("SW","S")):
            is_key=bool(re.fullmatch(r"(?i)MX[0-9A-Za-z_-]*",value))
        # Bespoke keyboard PCBs sometimes use a non-MX tactile switch
        # library (e.g. ML1A in Kinesis F-keys). Treat such switches as
        # *candidates*, retaining their evidence rather than assuming MX.
        if not is_key and re.fullmatch(r"(?i)S(?:W)?[0-9]+",ref):
            # Kinesis uses ML1A tact switches for actual F-key caps. A broad
            # library-name "keyboard" match would incorrectly classify e.g.
            # a SKQG reset pushbutton as a retained typing key.
            if re.search(r"(?i)ML1A[ _-]?11JW",identity+" "+value):
                conductive={pad.GetNetname() for pad in f.Pads() if pad.GetNetname()}
                is_key=len(conductive)>=2
        if is_key:
            rec["detected_as_keyboard_switch"]=True
            rec["switch_detected_from"]=(
                "known_keyboard_footprint" if known_switch
                else "candidate_switch_footprint_or_ref"
            )
            switches.append(rec)
        for pad in f.Pads():
            xpad,ypad=u(pad.GetPosition().x),u(pad.GetPosition().y)
            sz=pad.GetSize()
            pads.append({"ref":ref,"pad":pad.GetNumber(),"x":xpad,"y":ypad,"size_x_mm":u(sz.x),"size_y_mm":u(sz.y), "orientation_degrees":pad.GetOrientationDegrees(),
                         "roundrect_radius_mm":u(int(pad.GetRoundRectCornerRadius()))
                             if int(pad.GetShape())==int(p.PAD_SHAPE_ROUNDRECT) else None,
                         "pad_shape":int(pad.GetShape()),"pad_attribute":int(pad.GetAttribute()),"net":pad.GetNetname(),"layer":pad.GetLayerName()})
    conductive_zones=[]
    rule_area_count=0
    for zone_index, zone in enumerate(board.Zones()):
        if zone.GetIsRuleArea():
            rule_area_count+=1
            continue
        # zone.IsFilled() can be true on an imported board even when KiCad
        # carries *no filled polygon list for the requested layer*. Calling
        # GetFilledPolysList there can abort the native process, not merely
        # raise a Python exception; consult the layer-specific accessor first.
        has_fill=bool(zone.IsFilled() and zone.HasFilledPolysForLayer(zone.GetLayer()))
        record={
            "net":zone.GetNetname(), "layer":zone.GetLayerName(),
            "is_filled":has_fill,"polygons":[],
            "source_zone_index":zone_index,
        }
        if not has_fill and zone.GetNetname():
            warnings.append(f"unfilled_zone:{zone_index}:{zone.GetNetname()}")
        if has_fill:
            polys=zone.GetFilledPolysList(zone.GetLayer())
            for poly_index in range(polys.OutlineCount()):
                def points(chain):
                    return [[round(u(chain.CPoint(k).x),6),round(u(chain.CPoint(k).y),6)]
                            for k in range(chain.PointCount())]
                shell=points(polys.COutline(poly_index))
                holes=[points(polys.CHole(poly_index,j))
                       for j in range(polys.HoleCount(poly_index))]
                if len(shell)>=3:
                    record["polygons"].append({"shell":shell,"holes":holes})
        conductive_zones.append(record)
    print(json.dumps({
        "source_label":source.name,
        "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_warnings":(
            (["legacy_format_conversion_requires_independent_board_review"]
             if "(version 4)" in source.read_text(encoding="utf-8",errors="replace")[:100] else [])
            + warnings
        ),
        "pcbnew_version":p.Version(),
        "outline_bbox_mm":bbox,
        "zone_count":len(board.Zones()),
        "rule_area_count":rule_area_count,
        "conductive_zone_count":len(conductive_zones),
        "filled_zones":conductive_zones,
        "copper_layer_count":board.GetCopperLayerCount(),
        "tracks":tracks,"vias":vias,"pads":pads,"footprints":footprints,"switch_positions":switches
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
