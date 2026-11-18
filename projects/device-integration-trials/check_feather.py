"""Independently check the Feather carrier datums using KiCad's native EAGLE importer."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pcbnew


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("eagle_board", type=Path)
    args = parser.parse_args()
    key = "feather-m4-express"
    with ZipFile(args.release) as archive:
        profile = json.loads(archive.read("boards.json"))[key]
        fit = json.loads(archive.read("models/verification.json"))[key]
    digest = hashlib.sha256(args.eagle_board.read_bytes()).hexdigest()
    if digest != profile["source"]["sha256"] or digest != fit["board_sha256"]:
        raise ValueError("Board revision mismatch")
    plugin = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.EAGLE)
    board = plugin.LoadBoard(str(args.eagle_board), None)
    cx, cy = profile["board_center_mm"]
    observed = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            drill = pcbnew.ToMM(pad.GetDrillSize().x)
            if 2 <= drill <= 4:
                # KiCad board Y points down; EAGLE drawing Y points up.
                pos = pad.GetPosition()
                observed.append([round(pcbnew.ToMM(pos.x) - cx, 4),
                                 round(-pcbnew.ToMM(pos.y) - cy, 4), drill])
    if sorted(observed) != sorted(fit["reference_xy_and_drill_mm"]):
        raise ValueError("Independent importer and generated carrier disagree")
    print(json.dumps({"kicad_version": pcbnew.Version(), "board_sha256": digest,
                      "kicad_xy_and_drill_mm": sorted(observed), "hs_fit": fit}, indent=2))
