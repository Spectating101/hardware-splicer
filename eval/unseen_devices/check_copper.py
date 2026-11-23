"""Post-reveal continuity checks on selected imported EAGLE traces with system KiCad."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "unseen_sweep"))
from check_wiring import connected

ROUTES = {
    "console.brd": [
        ("card chip select", "X5", "2", "U$24", "31"),
        ("card clock", "X5", "5", "U$24", "36"),
        ("flash clock", "U1", "6", "U$24", "23"),
        ("button data", "IC1", "9", "U$24", "59"),
        ("button clock", "IC1", "2", "U$24", "60"),
        ("button latch", "IC1", "1", "U$24", "61"),
    ],
    "logger.brd": [
        ("card chip select", "U8", "~D23", "J6", "CS/DAT3"),
        ("IMU chip select to level shifter", "U8", "~D44", "Q9", "3"),
        ("Qwiic power control", "U8", "~D18", "U4", "3"),
        ("card power control", "U8", "D15", "Q2", "1"),
    ],
    "amp.brd": [
        ("left line input", "X2", "2", "X1", "3"),
        ("right line input", "X2", "3", "X1", "1"),
        ("left output A to filter", "J3", "1", "FB5", "2"),
        ("left output B to filter", "J3", "2", "FB4", "2"),
        ("right output A to filter", "J2", "1", "FB2", "2"),
        ("right output B to filter", "J2", "2", "FB3", "2"),
        ("left A filter to amplifier", "FB5", "1", "U1", "3"),
        ("left B filter to amplifier", "FB4", "1", "U1", "41"),
        ("right A filter to amplifier", "FB2", "1", "U1", "36"),
        ("right B filter to amplifier", "FB3", "1", "U1", "31"),
    ],
}


def audit(directory):
    manifest = json.loads((HERE / "inputs.json").read_text())
    result = {}
    for file, routes in ROUTES.items():
        path = directory / file
        source = path.read_bytes()
        if sha256(source).hexdigest() != manifest[file]["sha256"]:
            raise ValueError(f"Unexpected board source for {file}")
        poured = {signal.get("name") for signal in ET.fromstring(source).findall("./drawing/board/signals/signal")
                  if signal.find("polygon") is not None}
        board = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.EAGLE, str(path.resolve()))
        if not board.BuildConnectivity():
            raise ValueError("Could not build board connectivity")
        footprints = {f.GetReference(): f for f in board.GetFootprints()}
        checks = []
        for name, r1, p1, r2, p2 in routes:
            a, = [p for p in footprints[r1].Pads() if p.GetNumber() == p1]
            b, = [p for p in footprints[r2].Pads() if p.GetNumber() == p2]
            if not a.GetNetCode() or a.GetNetCode() != b.GetNetCode():
                raise ValueError(f"Selected endpoints are on different or unnamed nets for {file}, {name}")
            trace = connected(board.GetConnectivity(), a, b)
            checks.append({
                "role": name, "from": f"{r1}/{p1}", "to": f"{r2}/{p2}", "net": a.GetNetname(),
                "track_path_verified": trace,
            })
            if not trace:
                checks[-1]["source_net_has_polygon"] = a.GetNetname() in poured
        result[file] = checks
    return {"kicad": pcbnew.Version(), "boards": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    report = audit(parser.parse_args().directory)
    print(json.dumps(report, indent=2, sort_keys=True))
