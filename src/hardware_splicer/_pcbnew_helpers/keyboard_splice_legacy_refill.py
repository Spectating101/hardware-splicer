"""Native KiCad 9 best-effort *copy* of a board with regenerated zone fills.

This is an isolated diagnostic, never a transformation of the original file
or authority to fabricate the resulting converted PCB.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as pcb


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--original",type=Path,required=True)
    ap.add_argument("--converted",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--expected-sha256",required=True)
    a=ap.parse_args()

    source=a.original.resolve(strict=True)
    converted=a.converted.resolve()
    if source==converted:
        raise ValueError("refuse to edit original source PCB")
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha!=a.expected_sha256:
        raise ValueError("original PCB source digest mismatch")
    board=pcb.LoadBoard(str(source))
    if board is None:
        raise ValueError("unsupported original board format")
    zones=list(board.Zones())
    if not zones:
        raise ValueError("this diagnostic requires at least one existing legacy zone")
    if board.GetCopperLayerCount()!=2:
        raise ValueError("only two-layer rigid PCB zone conversion assessed")
    names=[str(z.GetNetname()) for z in zones]
    original_filled=sum(bool(z.IsFilled()) for z in zones)
    for zone in zones:
        if not zone.UnFill():
            raise ValueError("native KiCad could not unfill original zone")
    fill_ok=pcb.ZONE_FILLER(board).Fill(board.Zones())
    if not fill_ok:
        raise ValueError("KiCad 9 could not regenerate zone fills")
    converted_filled=sum(bool(z.IsFilled()) for z in board.Zones())
    if converted_filled != len(zones):
        raise ValueError("some KiCad zones were not regenerated")
    converted.parent.mkdir(parents=True,exist_ok=True)
    pcb.SaveBoard(str(converted),board)
    if not converted.is_file():
        raise ValueError("refilled PCB copy was not produced")
    receipt={
        "schema":"hs.native-legacy-kicad-zone-refill.v1",
        "original_source_sha256":source_sha,
        "converted_copy_sha256":hashlib.sha256(converted.read_bytes()).hexdigest(),
        "native_kicad_version":pcb.Version(),
        "copper_layer_count":board.GetCopperLayerCount(),
        "original_zone_count":len(zones),
        "original_filled_zone_count":original_filled,
        "regenerated_filled_zone_count":converted_filled,
        "original_zone_source_net_names":names,
        "original_file_modified":False,
        "original_upstream_source_format_updated_in_copy":True,
        "source_copper_pads_tracks_vias_equivalence_not_yet_verified":True,
        "fabrication_approved":False,
        "physical_board_tested":False,
    }
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SOURCE",source_sha,"CONVERTED",receipt["converted_copy_sha256"])
    print("ZONE_REBUILD",len(zones),"->",converted_filled)
    print("PHYSICAL_RELEASE",False)


if __name__=="__main__":
    main()
