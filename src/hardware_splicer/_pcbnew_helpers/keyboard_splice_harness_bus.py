"""One-contact-per-donor-pad KiCad junction/bus board for a modeled split.

This joins all source-conforming bridge and relocated-key endpoints on bus
nets. It *replaces*, rather than supplements, the earlier separate 17-channel
interposer in a possible assembly; wiring both would duplicate copper paths.

The generated native KiCad board is an electrical planning fixture only, not
a qualified cable, connector, mounting or powered restoration package.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p

PITCH=2.54
SPACING=9.0
TOP=11.0
LEFT=12.0


def point(x,y):
    return p.VECTOR2I(p.FromMM(float(x)),p.FromMM(float(y)))


def _receipt(data: dict):
    expected=data.get("payload_sha256")
    payload={k:v for k,v in data.items() if k!="payload_sha256"}
    actual=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,
                                    separators=(",",":")).encode()).hexdigest()
    if expected!=actual:
        raise ValueError("source-bound electrical receipt invalid")


def _source_endpoint_lookup(board:dict)->dict:
    mapping={}
    for pad in board.get("pads",[]):
        net=str(pad.get("net",""))
        ref=str(pad.get("ref",""))
        number=str(pad.get("pad",""))
        if ref and number and net:
            key=(ref,number)
            if key in mapping and mapping[key]!=net:
                raise ValueError("original pad has incompatible source nets")
            mapping[key]=net
    if not mapping:
        raise ValueError("original source pad graph absent")
    return mapping


def build_harness(source:dict,topology:dict,bridge:dict,remount:dict,
                  matrix_proof:dict,source_audit:dict,outdir:Path)->dict:
    sha=source.get("source_sha256")
    if any(s!=sha for s in (
        topology.get("source_sha256"),bridge.get("source_reference_sha256"),
        remount.get("source_sha256"),matrix_proof.get("source_sha256"),
        source_audit.get("original_pcb_sha256")
    )):
        raise ValueError("original PCB identity differs across harness inputs")
    _receipt(topology)
    _receipt(matrix_proof)
    _receipt(source_audit)
    if topology.get("model_replay_remaining_required_components")!=0:
        raise ValueError("unresolved source island connectivity")
    if topology.get("preexisting_unconnected_terminal_net_count")!=0:
        raise ValueError("original source has incomplete terminal mapping")
    if matrix_proof.get("ideal_directed_diode_matrix_model_passed") is not True:
        raise ValueError("original full key matrix not simulated successfully")
    if source_audit.get("net_assignment_equivalence") is not True:
        raise ValueError("independent KiCad schematic not electrically equivalent to board pads")
    if bridge.get("topology_sha256")!=topology.get("payload_sha256"):
        raise ValueError("old interposer models a different source-cut reconstruction")
    if len(bridge.get("channel_mapping",[]))!=len(topology.get("bridge_edges",[])):
        raise ValueError("original bridge channels inconsistent with recovery graph")
    if matrix_proof.get("source_bound_interposer_channels")!=len(bridge["channel_mapping"]):
        raise ValueError("source keyboard matrix saw a different interposer map")
    if matrix_proof.get("daughterboard_source_wires")!=remount.get("independent_wire_endpoints"):
        raise ValueError("source keyboard matrix saw a different key remount map")

    padmap=_source_endpoint_lookup(source)
    nets=defaultdict(set)
    # Multiple bridge edges share some pads. Exactly one physical donor-to-bus
    # wire is sufficient for a single net, so group by unique source pad.
    bridge_ids=set()
    for channel in bridge["channel_mapping"]:
        busnet=str(channel["source_net"])
        edge=(busnet,channel["from_model_island"],channel["to_model_island"])
        bridge_ids.add(edge)
        for field in ("from_candidate_contact","to_candidate_contact"):
            c=channel[field]
            if c.get("contact_type","existing_pad")!="existing_pad":
                raise ValueError("unqualified exposed-trace/via harness; use independent repair plan")
            ref=str(c["ref"]);pin=str(c["pad"])
            if padmap.get((ref,pin))!=busnet:
                raise ValueError(f"source donor pad {ref}/{pin} changed nets or is not modeled")
            nets[busnet].add(("donor",ref,pin))
    source_ids={
        (edge["net"],edge["from_island"],edge["to_island"])
        for edge in topology.get("bridge_edges",[])
    }
    if bridge_ids!=source_ids:
        raise ValueError("bridge endpoints do not exactly restore modeled source groups")

    remount_ports=set()
    for key in remount.get("source_wiring_map",[]):
        for connection in key["wire_map"]:
            net=str(connection["original_source_net"])
            ref=str(connection["original_source_ref"])
            pin=str(connection["original_source_pad"])
            if padmap.get((ref,pin))!=net:
                raise ValueError("remounted switch source pad does not belong to its original net")
            new_ref=str(connection["daughterboard_header_ref"])
            new_pin=str(connection["daughterboard_header_pad"])
            if (new_ref,new_pin) in remount_ports:
                raise ValueError("different keys share a daughterboard output pin")
            remount_ports.add((new_ref,new_pin))
            nets[net].add(("donor",ref,pin))
            nets[net].add(("remount",new_ref,new_pin))
    if len(remount_ports)!=2*remount.get("key_switches_relocated",0):
        raise ValueError("unaccounted physical key-relocation connector pin")
    if len(nets)>40 or len(nets)<2:
        raise ValueError("connector bus partition outside bounded prototype")
    if any(len(group)<2 for group in nets.values()):
        raise ValueError("single-ended source wire would not restore a connection")
    source_unique={
        (kind,ref,pin) for members in nets.values()
        for kind,ref,pin in members if kind=="donor"
    }
    remount_unique={
        (kind,ref,pin) for members in nets.values()
        for kind,ref,pin in members if kind=="remount"
    }
    if len(remount_unique)!=len(remount_ports):
        raise ValueError("one relocated switch contact is tied to multiple source nets")

    outdir.mkdir(parents=True,exist_ok=True)
    board=p.BOARD()
    assignments=[]
    max_pin=max(len(members) for members in nets.values())
    for group_index,(original_net,members) in enumerate(sorted(nets.items()),1):
        pin_count=len(members)
        library=Path("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty")
        footprint_name=f"PinHeader_1x{pin_count:02d}_P2.54mm_Vertical"
        path=library/(footprint_name+".kicad_mod")
        if not path.is_file():
            raise ValueError("required standard native KiCad connector footprint absent: "+footprint_name)
        fp=p.FootprintLoad(str(library),footprint_name)
        if fp is None:
            raise ValueError("native connector footprint unparseable")
        ref=f"J{group_index:02d}"
        fp.SetReference(ref)
        fp.SetValue(footprint_name)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        x=LEFT+(group_index-1)*SPACING
        fp.SetPosition(point(x,TOP))
        net=p.NETINFO_ITEM(board,f"HARNESS_NET_{group_index:02d}")
        board.Add(net)
        board.Add(fp)
        pads={int(pad.GetNumber()):pad for pad in fp.Pads()}
        if set(pads)!=set(range(1,pin_count+1)):
            raise ValueError("untrusted KiCad connector pin sequence")
        for pin,(role,source_ref,source_pin) in enumerate(sorted(members),1):
            pads[pin].SetNet(net)
            assignments.append({
                "harness_connector":ref,"harness_pin":pin,
                "harness_net":net.GetNetname(),"original_source_net":original_net,
                "external_role":role,"source_ref":source_ref,"source_pin":source_pin,
                "physical_wire_installed":False,
                "physical_mating_verified":False,
            })
        for pin in range(1,pin_count):
            track=p.PCB_TRACK(board)
            track.SetStart(point(x,TOP+(pin-1)*PITCH))
            track.SetEnd(point(x,TOP+pin*PITCH))
            track.SetLayer(p.F_Cu)
            track.SetWidth(p.FromMM(.5))
            track.SetNet(net)
            board.Add(track)

    width=LEFT*2+(len(nets)-1)*SPACING
    height=TOP*2+max_pin*PITCH
    corners=((0.0,0.0),(width,0.0),(width,height),(0.0,height))
    for a,b in zip(corners,corners[1:]+corners[:1]):
        edge=p.PCB_SHAPE(board)
        edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(point(*a))
        edge.SetEnd(point(*b))
        edge.SetWidth(p.FromMM(.05))
        edge.SetLayer(p.Edge_Cuts)
        board.Add(edge)
    pcb=outdir/"keyboard_recovery_junction.kicad_pcb"
    p.SaveBoard(str(pcb),board)
    manifest={
        "schema":"hs.keyboard-full-harness-junction.v1",
        "source_sha256":sha,
        "topology_sha256":topology["payload_sha256"],
        "full_matrix_sha256":matrix_proof["payload_sha256"],
        "independent_schematic_and_firmware_audit_sha256":source_audit["payload_sha256"],
        "unique_source_nets_joined":len(nets),
        "original_bridge_edges_replaced":len(bridge["channel_mapping"]),
        "source_original_pads_with_only_one_wire_each":len(source_unique),
        "relocated_key_header_pins":len(remount_unique),
        "total_junction_board_pins":len(assignments),
        "physical_junction_board_width_mm":width,
        "physical_junction_board_height_mm":height,
        "source_terminal_mapping":assignments,
        "valid_connection_model":True,
        "separate_original_bridge_interposer_should_not_be_installed_in_parallel":True,
        "actual_harness_connector_mpn":None,
        "strain_relief_qualified":False,
        "diode_polarity_ohmmeter_verified":False,
        "original_source_board_native_drc_passed":False,
        "firmware_compiled_flashed_or_powered":False,
        "physical_assembly_authorized":False,
        "fabrication_release":"BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW",
    }
    (outdir/"FULL_JUNCTION_WIRING.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    return manifest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-json",type=Path,required=True)
    ap.add_argument("--topology-json",type=Path,required=True)
    ap.add_argument("--bridge-json",type=Path,required=True)
    ap.add_argument("--remount-json",type=Path,required=True)
    ap.add_argument("--matrix-json",type=Path,required=True)
    ap.add_argument("--source-audit-json",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    files=[a.source_json,a.topology_json,a.bridge_json,a.remount_json,
           a.matrix_json,a.source_audit_json]
    result=build_harness(*(json.loads(f.read_text(encoding="utf-8")) for f in files),a.out)
    print("JUNCTION_NETS",result["unique_source_nets_joined"])
    print("SOURCE_DONOR_PAD_WIRES",result["source_original_pads_with_only_one_wire_each"])
    print("RELOCATED_SWITCH_PORTS",result["relocated_key_header_pins"])
    print("TOTAL_JUNCTION_PINS",result["total_junction_board_pins"])
    print("RELEASE",result["fabrication_release"])


if __name__=="__main__":
    main()
