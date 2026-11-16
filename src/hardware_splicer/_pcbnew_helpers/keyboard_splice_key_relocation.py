"""KiCad prototype daughterboard that preserves sacrificed keys via remounting.

All source switch contact names are taken from the *original KiCad donor PCB*
and require source hash equality. Every source contact gets its own independent
wire channel to a physical through-hole header. This does NOT prove a complete
keyboard after repair, or a strain-relieved/mated usable harness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p

X0 = 22.0
PITCH = 24.0
Y0 = 22.0
HEADER_DX = 9.0
HEADER_DY = 14.0


def point(x,y):
    return p.VECTOR2I(p.FromMM(float(x)),p.FromMM(float(y)))


def pad_near_kerf(pad,route):
    """Conservative circle-vs-polyline intersection, no system Shapely needed."""
    px=float(pad["x"]);py=float(pad["y"])
    radius=max(float(pad["size_x_mm"]),float(pad["size_y_mm"]))/2
    margin=radius+float(route["kerf_mm"])/2
    coordinates=route["cut_points_mm"]
    for (x1,y1),(x2,y2) in zip(coordinates,coordinates[1:]):
        dx=float(x2)-float(x1);dy=float(y2)-float(y1)
        norm=dx*dx+dy*dy
        t=min(1.0,max(0.0,((px-float(x1))*dx+(py-float(y1))*dy)/norm)) if norm else 0.0
        x=float(x1)+t*dx;y=float(y1)+t*dy
        if (px-x)**2+(py-y)**2 <= margin**2:
            return True
    return False


def trace(board,net,x1,y1,x2,y2,layer):
    seg=p.PCB_TRACK(board)
    seg.SetStart(point(x1,y1))
    seg.SetEnd(point(x2,y2))
    seg.SetWidth(p.FromMM(.3))
    seg.SetLayer(layer)
    seg.SetNet(net)
    board.Add(seg)


def load_fp(board,library,name,ref,x,y):
    folder=Path("/usr/share/kicad/footprints")/(library+".pretty")
    if not (folder/(name+".kicad_mod")).is_file():
        raise ValueError("Native KiCad source footprint not installed: "+name)
    fp=p.FootprintLoad(str(folder),name)
    if not fp:raise ValueError("Native KiCad failed to parse "+name)
    fp.SetReference(ref)
    fp.SetPosition(point(x,y))
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    return fp


def _verify_digest(body:dict)->str:
    digest=body.get("payload_sha256")
    check=hashlib.sha256(json.dumps({k:v for k,v in body.items() if k!="payload_sha256"},
         sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    if digest!=check:
        raise ValueError("selected cut route digest invalid")
    return str(digest)


def create_relocation(board_data:dict, path_data:dict, consequence:dict, outdir:Path):
    source=str(board_data.get("source_sha256",""))
    if not source or source!=path_data.get("source_sha256") or source!=consequence.get("source_sha256"):
        raise ValueError("source identity mismatch in key remount request")
    route_digest=_verify_digest(path_data)
    if consequence.get("cut_path_sha256")!=route_digest:
        raise ValueError("consequence audit was from a different saw path")
    if path_data.get("release")!="PROPOSED_CUT_ONLY_NOT_VERIFIED" or path_data.get("physical_cut_authorized") is not False:
        raise ValueError("cut path is not in untrusted research state")
    if not consequence.get("nominally_salvageable_except_sacrificed_switches"):
        raise ValueError("cannot remount when source electrical pads, vias or critical components are damaged")
    selected=consequence.get("sacrificed_switches",[])
    if not 1<=len(selected)<=8:
        raise ValueError("prototype daughterboard supports 1..8 source-verified key positions")
    refs={str(s["ref"]) for s in selected}
    if len(refs)!=len(selected):
        raise ValueError("duplicated sacrificed source switch")
    source_switches={str(s["ref"]):s for s in board_data.get("switch_positions",[])}
    if not refs.issubset(source_switches):
        raise ValueError("unrecognized original sacrificed switch reference")
    # Independently reconstruct the complete key casualty inventory; never
    # trust a stale or edited consequence report to omit another damaged key.
    near_switches={
        ref for ref,sw in source_switches.items()
        if pad_near_kerf({
            "x":sw["x"],"y":sw["y"],
            "size_x_mm":17.0,"size_y_mm":17.0
        },path_data)
    }
    if refs != near_switches:
        raise ValueError("source cut crosses keys missing from the proposed relocation inventory")
    # Reject all damage to live original copper terminals, independent of the
    # caller's claim that the nominal route is geometrically acceptable.
    for pad in board_data.get("pads",[]):
        if not pad_near_kerf(pad,path_data):
            continue
        if pad.get("net"):
            raise ValueError("cut impacts a live source PCB terminal")
        if pad.get("pad_attribute") != 3 or str(pad.get("ref")) not in refs:
            raise ValueError("cut intersects unqualified source mounting geometry")
    for via in board_data.get("vias",[]):
        if pad_near_kerf({
            "x":via["x"],"y":via["y"],
            "size_x_mm":via["diameter_mm"],"size_y_mm":via["diameter_mm"],
        },path_data):
            raise ValueError("cut damages a source via")
    mapping=[]
    for original in sorted(selected,key=lambda x:x["ref"]):
        ref=str(original["ref"])
        if (float(original["x"])!=float(source_switches[ref]["x"]) or
            float(original["y"])!=float(source_switches[ref]["y"])):
            raise ValueError("sacrificed reference differs from original footprint location")
        pads={}
        for pad in board_data.get("pads",[]):
            if str(pad.get("ref"))!=ref or str(pad.get("pad")) not in ("1","2"):
                continue
            n=str(pad.get("net",""))
            if not n or str(pad["pad"]) in pads:
                raise ValueError("ambiguous original switch contact")
            # The physical metal pad must survive the modeled material removal.
            # Use a conservative circular envelope around its source dimensions.
            if pad_near_kerf(pad,path_data):
                raise ValueError("source switch pad is cut, cannot attach remount jumper")
            pads[str(pad["pad"])]=pad
        if set(pads)!={"1","2"} or pads["1"]["net"]==pads["2"]["net"]:
            raise ValueError("source switch must expose two distinct conserved nets")
        mapping.append({
            "original_ref":ref,
            "original_label":str(original.get("value","")),
            "original_footprint":str(source_switches[ref].get("footprint","")),
            "source_pads":{
                number:{
                    "original_net":pads[number]["net"],
                    "x_mm":pads[number]["x"],"y_mm":pads[number]["y"],
                    "pad_attribute":pads[number].get("pad_attribute"),
                } for number in ("1","2")
            },
        })

    board=p.BOARD()
    for i,row in enumerate(mapping):
        cx=X0+PITCH*i;cy=Y0
        sw=load_fp(board,"Button_Switch_Keyboard","SW_Cherry_MX_1.00u_PCB",
                   f"SW{i+1}",cx,cy)
        header=load_fp(board,"Connector_PinHeader_2.54mm",
                       "PinHeader_1x02_P2.54mm_Vertical",
                       f"J{i+1}",cx+HEADER_DX,cy+HEADER_DY)
        switch_pads={pad.GetNumber():pad for pad in sw.Pads() if pad.GetNumber()}
        header_pads={pad.GetNumber():pad for pad in header.Pads() if pad.GetNumber()}
        if set(switch_pads)!={"1","2"} or set(header_pads)!={"1","2"}:
            raise ValueError("standard switch/header footprint did not match expected pad numbers")
        for number in ("1","2"):
            net=p.NETINFO_ITEM(board,f"KEY{i+1:02d}_CONTACT{number}")
            board.Add(net)
            switch_pads[number].SetNet(net)
            header_pads[number].SetNet(net)
            row.setdefault("wire_map",[]).append({
                "daughterboard_switch_ref":f"SW{i+1}",
                "daughterboard_switch_pad":number,
                "daughterboard_header_ref":f"J{i+1}",
                "daughterboard_header_pad":number,
                "new_pcb_net":f"KEY{i+1:02d}_CONTACT{number}",
                "original_source_ref":row["original_ref"],
                "original_source_pad":number,
                "original_source_net":row["source_pads"][number]["original_net"],
                "source_wire_connection_verified":False,
            })
        trace(board,switch_pads["1"].GetNet(),cx,cy,cx+HEADER_DX,cy,p.F_Cu)
        trace(board,switch_pads["1"].GetNet(),
              cx+HEADER_DX,cy,cx+HEADER_DX,cy+HEADER_DY,p.F_Cu)
        sx=cx-6.35;sy=cy+2.54
        trace(board,switch_pads["2"].GetNet(),sx,sy,sx,cy+HEADER_DY+2.54,p.B_Cu)
        trace(board,switch_pads["2"].GetNet(),
              sx,cy+HEADER_DY+2.54,cx+HEADER_DX,cy+HEADER_DY+2.54,p.B_Cu)

    width=X0+PITCH*(len(mapping)-1)+22.0
    height=62.0
    corners=((0.0,0.0),(width,0.0),(width,height),(0.0,height))
    for a,b in zip(corners,corners[1:]+corners[:1]):
        edge=p.PCB_SHAPE(board)
        edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(point(*a))
        edge.SetEnd(point(*b))
        edge.SetWidth(p.FromMM(.05))
        edge.SetLayer(p.Edge_Cuts)
        board.Add(edge)
    outdir.mkdir(parents=True,exist_ok=True)
    pcb=outdir/"remount_keys.kicad_pcb"
    p.SaveBoard(str(pcb),board)
    output={
        "schema":"hs.keyboard-source-bound-key-relocation.v1",
        "source_sha256":source,
        "cut_path_sha256":route_digest,
        "reference_switch_candidates":len(board_data["switch_positions"]),
        "original_main_board_switches_retained":consequence["remaining_switches"],
        "key_switches_relocated":len(mapping),
        "total_original_switch_positions_accounted":len(mapping)+consequence["remaining_switches"],
        "original_main_left":consequence["remaining_left"],
        "original_main_right":consequence["remaining_right"],
        "source_wiring_map":mapping,
        "independent_wire_endpoints":len(mapping)*2,
        "key_pitch_mm":PITCH,
        "board_width_mm":width,
        "board_height_mm":height,
        "physical_connector_mpn":None,
        "reuse_original_switch_fit_verified":False,
        "new_casing_and_keycap_accessibility_verified":False,
        "donor_continuity_verified":False,
        "firmware_remapping_required":None,
        "firmware_layout_compatibility_verified":False,
        "firmware_simulated_or_tested":False,
        "physical_authority_granted":False,
        "fabrication_release":"BLOCKED_RELOCATION_PREVIEW_ONLY",
    }
    (outdir/"RELOCATION_MAP.json").write_text(json.dumps(
        output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--board-json",type=Path,required=True)
    ap.add_argument("--route-search-json",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    original=json.loads(args.board_json.read_text(encoding="utf-8"))
    planned=json.loads(args.route_search_json.read_text(encoding="utf-8"))
    result=create_relocation(original,planned["selected_route"],
                             planned["selected_consequence"],args.out)
    print("RELOCATED_KEYS",result["key_switches_relocated"])
    print("ORIGINAL_SWITCH_COUNTS_REPRESENTED",result["total_original_switch_positions_accounted"])
    print("KICAD_SOURCE_BOUND_REMOUNT",args.out/"remount_keys.kicad_pcb")
    print("FABRICATION_RELEASE",result["fabrication_release"])


if __name__=="__main__":
    main()
