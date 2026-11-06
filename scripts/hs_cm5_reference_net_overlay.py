"""KiCad 9 native reference-net inspection overlay, NOT a routed motherboard.

Uses the corrected CM5 fixture plus routed endpoint-to-net names extracted
from the manufacturer PADS PCB. No tracks, no power, no devices to boot.
Do not interpret this as an independent schematic or a successful full DRC.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(input_board: Path, mapping_file: Path, output_board: Path) -> dict:
    try:
        import pcbnew
    except ImportError as exc:
        raise RuntimeError("KiCad 9 pcbnew binding unavailable") from exc
    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    if mapping["schema"] != "hs.cm5_reference_board_routed_nets.v1":
        raise ValueError("unsupported reference routed-net snapshot")
    if mapping["safe_to_fabricate"] or mapping["module_revision_compatibility_verified"]:
        raise ValueError("unsafe claim in source material")
    if mapping["reference_contacts_with_routes"] != 241:
        raise ValueError("source contact count mismatch")
    src = {int(k): v for k, v in mapping["reference_contact_routed_net_map"].items()}
    if set(src) != set(range(1,301)) - set(mapping["unrepresented_unrouted_or_single_terminal_contacts"]):
        raise ValueError("routed contact set mismatches the report")
    board = pcbnew.LoadBoard(str(input_board))
    if board is None or len(board.GetFootprints()) != 1 or len(list(board.GetTracks())) != 0:
        raise ValueError("source board was not a native unrouted footprint-only KiCad fixture")
    footprint = board.GetFootprints()[0]
    pads = [pad for pad in footprint.Pads() if pad.GetNumber().isdigit()]
    if sorted(int(pad.GetNumber()) for pad in pads)!=list(range(1,301)):
        raise ValueError("missing or duplicate electrical CM5 pads")
    names = sorted({item for items in src.values() for item in items})
    if len(names) != 159 or any(len(items)!=1 for items in src.values()):
        raise ValueError("unexpected reference routing identity set")
    nets = {}
    for name in names:
        net = pcbnew.NETINFO_ITEM(board,name)
        board.Add(net)
        nets[name]=net
    for pad in pads:
        num=int(pad.GetNumber())
        if num in src:
            pad.SetNet(nets[src[num][0]])
    # Deliberately include visible text. A board with zero tracks and one
    # footprint is only net-label evidence, NOT an electrical schematic.
    for item in board.GetDrawings():
        if isinstance(item,pcbnew.PCB_TEXT) and "FOOTPRINT STUDY" in item.GetText():
            item.SetText("MANUFACTURER ROUTED-NET LABELS ONLY - NO POWER - DO NOT FAB")
    output_board.parent.mkdir(parents=True,exist_ok=True)
    pcbnew.SaveBoard(str(output_board),board)
    reload = pcbnew.LoadBoard(str(output_board))
    padlist = list(reload.GetFootprints()[0].Pads())
    assigned = {int(p.GetNumber()):p.GetNetname() for p in padlist if p.GetNumber().isdigit() and p.GetNetname()}
    if len(assigned)!=241 or len({v for v in assigned.values()})!=159 or list(reload.GetTracks()):
        raise RuntimeError("KiCad saved board does not retain exact source net identity")
    if any(assigned[n] != src[n][0] for n in src):
        raise RuntimeError("KiCad lost reference source net identity")
    return {"board":str(output_board),"pads_with_source_net_labels":len(assigned),
            "source_routed_net_names":len(set(assigned.values())),
            "tracks":len(list(reload.GetTracks())),
            "routed":False,"revision_compatible":False,"fabrication_authorized":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixture",required=True,type=Path)
    parser.add_argument("--map",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.fixture,args.map,args.output),indent=2))
