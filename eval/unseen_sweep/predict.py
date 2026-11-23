"""Replay the Sweep board reconstruction and direct-fit screen with system KiCad."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import urlopen

import pcbnew

HERE = Path(__file__).resolve().parent
EXTRACTOR = HERE.parents[1] / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"


def verified_inputs(directory, fetch):
    files = {}
    for key, entry in json.loads((HERE / "inputs.json").read_text()).items():
        path = directory / entry["file"]
        if fetch and not path.exists():
            with urlopen(entry["url"], timeout=45) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"Downloaded {key} differs from the registered source")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Wrong revision of {key}")
        files[key] = path
    return files


def hole_pattern(footprint):
    """Local integer micrometres, independent of a key position on either half."""
    result = []
    for pad in footprint.Pads():
        drill = pad.GetDrillSize()
        if drill.x <= 0 or drill.y <= 0:
            raise ValueError("Screen requires through-hole footprints")
        pos = pad.GetFPRelativePosition()
        result.append((bool(pad.GetNumber()), round(pos.x / 1000), round(pos.y / 1000),
                       round(min(drill.x, drill.y) / 1000)))
    return tuple(sorted(result))


def compare_pattern(board, donor, declared_family):
    # Both leads are interchangeable on these passive switches. Every accepted
    # hole must retain its electrical or mechanical role under the SAME rotation.
    target = {(contact, x, y): size for contact, x, y, size in board}
    orientations = []
    for _ in range(4):
        leads_align = all((c, x, y) in target for c, x, y, _ in donor if c)
        if leads_align:
            missing = sum((c, x, y) not in target for c, x, y, _ in donor if not c)
            orientations.append(missing)
        donor = [(c, -y, x, size) for c, x, y, size in donor]
    if not orientations:
        return "reject", "The two electrical contacts cannot land on the board holes."
    if min(orientations) or not declared_family:
        return "unresolved", "Contacts line up. Mechanical features or switch series still need confirmation."
    return "accept", "Board declares this series and its contact and locating-hole centers agree."


def predict(directory, fetch, extractor):
    paths = verified_inputs(directory, fetch)
    board_path = paths.pop("board")
    extracted = json.loads(subprocess.check_output(
        [sys.executable, str(extractor), "--pcb", str(board_path)], timeout=90))
    board = pcbnew.LoadBoard(str(board_path))
    footprints = list(board.GetFootprints())
    pins = defaultdict(list)
    for f in footprints:
        if "promicro" in f.GetFPIDAsString().lower():
            for pad in f.Pads():
                pins[pad.GetNetname()].append((f.GetReference(), pad.GetNumber()))

    mapping = {}
    patterns = set()
    families = set()
    for f in footprints:
        if not re.fullmatch(r"SW\d+(?:_\w+)?", f.GetReference()) or f.GetValue() != "SW_Push":
            continue
        nets = {pad.GetNetname() for pad in f.Pads() if pad.GetNumber()}
        if len(nets) != 2 or "gnd" not in nets:
            raise ValueError("Switch does not match the direct-to-ground wiring hypothesis")
        signal, = nets - {"gnd"}
        controller, pin = pins[signal][0] if len(pins[signal]) == 1 else (None, None)
        if controller is None:
            raise ValueError(f"Cannot resolve {signal} to one controller pad")
        mapping[f.GetReference()] = {"signal": signal, "controller": controller, "pad": pin}
        patterns.add(hole_pattern(f))
        families.add(f.GetFPIDAsString().split(":")[-1].lower())
    if len(patterns) != 1 or len(families) != 1:
        raise ValueError("Expected a common switch footprint across the two halves")
    board_pattern = patterns.pop()
    family = families.pop()
    swaps = {}
    for key, path in paths.items():
        f = pcbnew.FootprintLoad(str(directory), path.stem)
        donor_pattern = hole_pattern(f)
        if sum(contact for contact, *_ in donor_pattern) != 2:
            raise ValueError("Expected a passive switch with two leads")
        series = key.lower().replace(" ", "-")
        declared = re.search(rf"(?<![a-z0-9]){re.escape(series)}(?![a-z0-9])", family) is not None
        decision, reason = compare_pattern(board_pattern, donor_pattern, declared)
        swaps[key] = {"prediction": decision, "reason": reason}
    swaps["unmarked loose switch"] = {"prediction": "unresolved", "reason": "Missing identity and terminal dimensions."}
    return {
        "design": "Sweep v2.2", "pcbnew": pcbnew.Version(),
        "input_manifest_sha256": hashlib.sha256((HERE / "inputs.json").read_bytes()).hexdigest(),
        "extractor_sha256": hashlib.sha256(extractor.read_bytes()).hexdigest(),
        "original_extractor_key_refs": sorted(f["ref"] for f in extracted["switch_positions"]),
        "pcb_footprints": dict(sorted(Counter(f.GetFPIDAsString() for f in footprints).items())),
        "keys_by_controller": dict(Counter(v["controller"] for v in mapping.values())),
        "switch_to_controller": mapping, "switch_footprint": family,
        "recommended_board_holes_um": board_pattern, "swaps": swaps,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--extractor", default=EXTRACTOR, type=Path)
    args = parser.parse_args()
    print(json.dumps(predict(args.directory, args.fetch, args.extractor), indent=2, sort_keys=True))
