#!/usr/bin/env python3
"""KiCad 9 mechanical footprint staging board; explicitly NOT a circuit PCB.

A true 300-contact Radxa symbol/footprint staging artifact for HS.
No power rails, netlist, tracks, component circuitry, or fabrication claim.
Run with /usr/bin/python3 or another Python exposing KiCad pcbnew.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def create(*, library_dir: Path, destination: Path) -> dict[str,object]:
    try:
        import pcbnew
    except ImportError as exc:
        raise RuntimeError("KiCad pcbnew Python bindings are required") from exc
    part=pcbnew.FootprintLoad(str(library_dir), "Radxa_CM5")
    if part is None:
        raise RuntimeError("KiCad could not load the actual CM5 footprint")
    numbered=[int(p.GetNumber()) for p in part.Pads() if p.GetNumber().isdigit()]
    mounting=[p for p in part.Pads() if not p.GetNumber()]
    if sorted(numbered)!=list(range(1,301)) or len(mounting)!=4:
        raise RuntimeError("KiCad footprint lacks exactly 300 contacts plus 4 mounting holes")
    board=pcbnew.BOARD()
    # All the footprint's pads are from the MIT-licensed reference library.
    # No tracks or nets are assigned; this is a geometry/parse fixture ONLY.
    board.Add(part)
    bb=part.GetBoundingBox()
    mm=1_000_000
    margin=8*mm
    x0=bb.GetX()-margin
    y0=bb.GetY()-margin
    x1=bb.GetX()+bb.GetWidth()+margin
    y1=bb.GetY()+bb.GetHeight()+margin
    outline=pcbnew.PCB_SHAPE(board)
    outline.SetShape(pcbnew.SHAPE_T_RECT)
    outline.SetStart(pcbnew.VECTOR2I(int(x0),int(y0)))
    outline.SetEnd(pcbnew.VECTOR2I(int(x1),int(y1)))
    outline.SetLayer(pcbnew.Edge_Cuts)
    outline.SetWidth(int(.1*mm))
    board.Add(outline)
    # A persistent native KiCad warning visible on inspection.
    warning=pcbnew.PCB_TEXT(board)
    warning.SetText("FOOTPRINT STUDY ONLY - NO NETLIST - DO NOT FAB")
    warning.SetLayer(pcbnew.Cmts_User)
    warning.SetPosition(pcbnew.VECTOR2I(int((x0+x1)/2),int(y0+3*mm)))
    warning.SetTextSize(pcbnew.VECTOR2I(mm,mm))
    warning.SetTextThickness(int(.15*mm))
    board.Add(warning)
    destination.parent.mkdir(parents=True,exist_ok=True)
    pcbnew.SaveBoard(str(destination),board)
    reloaded=pcbnew.LoadBoard(str(destination))
    if reloaded is None or len(reloaded.GetFootprints())!=1:
        raise RuntimeError("KiCad board serialization/reimport failed")
    placed=reloaded.GetFootprints()[0]
    electrical=[p for p in placed.Pads() if p.GetNumber()]
    if len(electrical)!=300 or len(list(reloaded.GetTracks())):
        raise RuntimeError("invalid unconnected footprint staging board")
    return {"schema":"hs.cm5_footprint_staging.v1","kicad_version":pcbnew.GetBuildVersion(),
            "electrical_numbered_pads":len(electrical),"unnumbered_mounting_holes":len(mounting),
            "unrouted":True,"nets_proven":False,"power_safe":False,
            "fabrication_authorized":False,"board_path":str(destination)}


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--library",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    opts=ap.parse_args()
    print(create(library_dir=opts.library,destination=opts.out))

