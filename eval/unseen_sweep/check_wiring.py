"""After the reveal, compare the frozen switch map to copper paths and schematic labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

import pcbnew
from score import HERE, PREDICTIONS_SHA, read_verified


def controller_labels(schematic, library):
    # This legacy sheet puts global labels directly on the Pro Micro pins.
    # Limit this check to those endpoints. Missing labels are unresolved.
    labels = {(int(x), int(y)): name for x, y, name in
              re.findall(r"^Text GLabel (\d+) (\d+) [^\n]*\n([^\n]+)", schematic, re.M)}
    pin_locations = re.findall(r"^X \S+ (\d+) (-?\d+) (-?\d+) ", library, re.M)
    result = {}
    for block in re.findall(r"^\$Comp\n(.*?)^\$EndComp", schematic, re.M | re.S):
        symbol, ref = re.search(r"^L (\S+) (\S+)", block, re.M).groups()
        if not symbol.startswith("sweepv2-rescue:ProMicro-"):
            continue
        x, y = map(int, re.search(r"^P (\d+) (\d+)", block, re.M).groups())
        a, b, c, d = map(int, block.strip().splitlines()[-1].split())
        for pin, dx, dy in pin_locations:
            px, py = int(dx), int(dy)
            result[ref, pin] = labels.get((x + a * px + b * py, y + c * px + d * py))
    return result


def connected(conn, start, end):
    pending = [start]
    seen = set()
    endpoint = end.m_Uuid.AsString()
    while pending:
        item = pending.pop()
        uid = item.m_Uuid.AsString()
        if uid == endpoint:
            return True
        if uid not in seen:
            seen.add(uid)
            pending.extend(conn.GetConnectedTracks(item))
            pending.extend(conn.GetConnectedPads(item))
    return False


def audit(directory):
    mapping = json.loads(read_verified(HERE / "predictions.json", PREDICTIONS_SHA))["switch_to_controller"]
    schematic = read_verified(directory / "sweepv2.sch",
                              "98eb5555a53b691bc76c55b6fc7327e337dcfcec934d29326f95ff535025f5f7")
    library = read_verified(directory / "sweepv2-rescue.lib",
                            "afa261745e4d8aee5cab57ae1e991ed74695b468ca1695ce88f37ddc2d94720c")
    read_verified(directory / "sweepv2.kicad_pro", "b5dceb469e8a0b84dcb6f1615570963cd0584c30a8a1ff4fea61d17350c6c10d")
    path = directory / "sweepv2.kicad_pcb"
    board_sha = json.loads((HERE / "inputs.json").read_text())["board"]["sha256"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != board_sha:
        raise ValueError("Unexpected PCB")
    board = pcbnew.LoadBoard(str(path))
    refs = {f.GetReference(): f for f in board.GetFootprints() if f.GetReference() in mapping or f.GetReference() in {"U1", "U2"}}
    labels = controller_labels(schematic, library)
    missing_paths, differences = [], []
    for ref, net in mapping.items():
        ctrl, pin = net["controller"], net["pad"]
        start, = [p for p in refs[ref].Pads() if p.GetNetname() == net["signal"]]
        end, = [p for p in refs[ctrl].Pads() if p.GetNumber() == pin]
        if not connected(board.GetConnectivity(), start, end):
            missing_paths.append(ref)
        if labels.get((ctrl, pin)) != net["signal"]:
            differences.append({"controller": ctrl, "pad": pin, "pcb": net["signal"],
                                "schematic": labels.get((ctrl, pin))})
    with TemporaryDirectory() as temp:
        report = Path(temp) / "drc.json"
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", str(report), str(path)],
                       check=True, capture_output=True, timeout=120)
        drc = json.loads(report.read_text())
    # KiCad may choose a different representative track/pad on an island.
    # Report net names and counts rather than depending on ratsnest tie breaks.
    unconnected = Counter()
    for row in drc["unconnected_items"]:
        nets = {name for item in row["items"] for name in re.findall(r"\[([^\]]+)\]", item["description"])}
        unconnected[", ".join(sorted(nets)) or "unidentified"] += 1
    return {
        "kicad_version": drc["kicad_version"], "signal_paths_checked": len(mapping),
        "missing_signal_paths": missing_paths,
        "controller_label_differences": sorted(differences, key=lambda row: (row["controller"], int(row["pad"]))),
        "drc_violations_by_severity": dict(Counter(v["severity"] for v in drc["violations"])),
        "unconnected_items_by_net": dict(unconnected),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_project", type=Path)
    print(json.dumps(audit(parser.parse_args().upstream_project), indent=2, sort_keys=True))
