"""Compact latching IDC 2x25 native KiCad junction for source-bound 49 wires.

One 50-pin latching IDC footprint carries 49 independent donor/remount wiring
tails, electrically shorting only pins assigned to the *same original PCB net*
by the original full-junction proof. It remains a connector/cable preview,
not an IPC-approved board, qualified FFC, or ready-to-cut donor.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p


NAME="IDC-Header_2x25_P2.54mm_Latch_Vertical"
LIBRARY=Path("/usr/share/kicad/footprints/Connector_IDC.pretty")
WIDTH_MM=42.0
HEIGHT_MM=94.0
ORIGIN=(20.0,15.0)
COPPER_MM=0.35


def make_compact(original:dict,out:Path)->dict:
    if original.get("schema")!="hs.keyboard-full-harness-junction.v1":
        raise ValueError("unsupported source junction evidence")
    if (original.get("physical_assembly_authorized") is not False or
        original.get("fabrication_release")!="BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW" or
        original.get("valid_connection_model") is not True):
        raise ValueError("unverified or authorized original source junction")
    assignments=original.get("source_terminal_mapping",[])
    if not isinstance(assignments,list) or len(assignments)!=49:
        raise ValueError("expected 49 source-bound wire leads")
    if original.get("total_junction_board_pins")!=49:
        raise ValueError("source junction lead count inconsistent")
    if original.get("unique_source_nets_joined")!=20:
        raise ValueError("unexpected source-net group count")
    if original.get("source_original_pads_with_only_one_wire_each")!=39 or (
        original.get("relocated_key_header_pins")!=10
    ):
        raise ValueError("original donor pads and relocations must remain distinct")
    distinct=set()
    by_net=defaultdict(list)
    for row in assignments:
        net=row.get("original_source_net")
        role=row.get("external_role")
        key=(role,row.get("source_ref"),row.get("source_pin"))
        if not net or role not in ("donor","remount") or None in key or key in distinct:
            raise ValueError("duplicate or unnamed original source contact")
        distinct.add(key)
        if row.get("physical_wire_installed") is not False:
            raise ValueError("unmeasured source contact advertised as installed")
        by_net[net].append(row)
    if len(by_net)!=20 or any(len(v)<2 for v in by_net.values()):
        raise ValueError("shorted source bus groups or unpaired source lead")
    footprint_file=LIBRARY/(NAME+".kicad_mod")
    if not footprint_file.is_file():
        raise ValueError("native KiCad IDC latching header library missing")
    board=p.BOARD()
    f=p.FootprintLoad(str(LIBRARY),NAME)
    if f is None:
        raise ValueError("KiCad 9 cannot load the latching IDC 2x25 component")
    f.SetReference("J1")
    f.SetValue("UNVERIFIED_IDC_50_WAY")
    f.SetPosition(p.VECTOR2I(p.FromMM(ORIGIN[0]),p.FromMM(ORIGIN[1])))
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    board.Add(f)
    pads={int(x.GetNumber()):x for x in f.Pads() if x.GetNumber()}
    if set(pads)!=set(range(1,51)):
        raise ValueError("KiCad standard footprint must have all 50 numbered pins")
    records=[]
    previous_buses=[]
    pin=1
    for group,(source_net,rows) in enumerate(sorted(by_net.items()),1):
        assigned=sorted(rows,key=lambda row:(
            str(row["external_role"]),str(row["source_ref"]),str(row["source_pin"])
        ))
        net=p.NETINFO_ITEM(board,f"SOURCE_BUS_{group:02d}")
        board.Add(net)
        occupied=[]
        for row in assigned:
            if pin>50:
                raise ValueError("more than 50 physical leads, cannot map all contacts")
            pads[pin].SetNet(net)
            occupied.append(pin)
            records.append({
                "IDC_header_ref":"J1",
                "IDC_header_pin":pin,
                "IDC_net":net.GetNetname(),
                "original_source_net":source_net,
                "external_role":row["external_role"],
                "source_ref":row["source_ref"],
                "source_pin":row["source_pin"],
                "original_junction_header":row["harness_connector"],
                "original_junction_pin":row["harness_pin"],
                "physical_connection_verified":False,
            })
            pin+=1
        for a,b in zip(occupied,occupied[1:]):
            tr=p.PCB_TRACK(board)
            tr.SetStart(pads[a].GetPosition())
            tr.SetEnd(pads[b].GetPosition())
            tr.SetWidth(p.FromMM(COPPER_MM))
            tr.SetLayer(p.F_Cu)
            tr.SetNet(net)
            board.Add(tr)
        previous_buses.append(occupied)

    if pin!=50:
        raise ValueError("missing original donor or daughterboard source wire")
    if pads[50].GetNetname():
        raise ValueError("50th unused IDC pin must remain electrically unassigned")
    footprint_box=f.GetBoundingBox()
    if not (p.ToMM(footprint_box.GetX())>=.5
            and p.ToMM(footprint_box.GetY())>=.5
            and p.ToMM(footprint_box.GetX()+footprint_box.GetWidth())<=WIDTH_MM-.5
            and p.ToMM(footprint_box.GetY()+footprint_box.GetHeight())<=HEIGHT_MM-.5):
        raise ValueError("native latching IDC body exceeds physical board perimeter")
    corners=((0.0,0.0),(WIDTH_MM,0.0),(WIDTH_MM,HEIGHT_MM),(0.0,HEIGHT_MM))
    for left,right in zip(corners,corners[1:]+corners[:1]):
        edge=p.PCB_SHAPE(board)
        edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(p.VECTOR2I(p.FromMM(left[0]),p.FromMM(left[1])))
        edge.SetEnd(p.VECTOR2I(p.FromMM(right[0]),p.FromMM(right[1])))
        edge.SetWidth(p.FromMM(.05))
        edge.SetLayer(p.Edge_Cuts)
        board.Add(edge)
    out.mkdir(parents=True,exist_ok=True)
    pcb=out/"compact_idc50_junction.kicad_pcb"
    p.SaveBoard(str(pcb),board)
    original_area=float(original["physical_junction_board_width_mm"])*float(original["physical_junction_board_height_mm"])
    compact_area=WIDTH_MM*HEIGHT_MM
    manifest={
        "schema":"hs.keyboard-compact-50pin-idc-junction.v1",
        "source_sha256":original["source_sha256"],
        "source_junction_original_net_groups":original["unique_source_nets_joined"],
        "source_original_wiring_assignments":original["total_junction_board_pins"],
        "IDC_pin_count":50,
        "IDC_used_pins":49,
        "IDC_unused_insulated_pin":50,
        "independent_source_bus_net_count":20,
        "original_source_donor_contacts":39,
        "original_remounted_key_ports":10,
        "full_size_junction_width_mm":original["physical_junction_board_width_mm"],
        "full_size_junction_height_mm":original["physical_junction_board_height_mm"],
        "full_size_junction_area_mm2":round(original_area,2),
        "compact_board_width_mm":WIDTH_MM,
        "compact_board_height_mm":HEIGHT_MM,
        "compact_board_area_mm2":round(compact_area,2),
        "board_area_reduction_percent":round(100*(1-compact_area/original_area),2),
        "KiCad_standard_footprint":"Connector_IDC:"+NAME,
        "native_KiCad_footprint_used":True,
        "junction_pin_assignments":records,
        "source_original_junction_mutually_exclusive":True,
        "source_original_17_channel_interposer_mutually_exclusive":True,
        "physical_connector_mpn":None,
        "ribbon_cable_routing_and_MPN":None,
        "enclosure_strain_relief_verified":False,
        "actual_donor_wires_soldered":False,
        "fabrication_authorized":False,
        "release":"BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW",
    }
    (out/"COMPACT_JUNCTION_WIRING.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    return manifest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--full-junction-json",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    manifest=json.loads(a.full_junction_json.read_text(encoding="utf-8"))
    result=make_compact(manifest,a.out)
    print("PHYSICAL_SOURCE_CONTACTS",result["IDC_used_pins"])
    print("SOURCE_BUSES",result["independent_source_bus_net_count"])
    print("BOARD_MM",result["compact_board_width_mm"],result["compact_board_height_mm"])
    print("AREA_REDUCTION_PERCENT",result["board_area_reduction_percent"])
    print("RELEASE",result["release"])


if __name__=="__main__":
    main()
