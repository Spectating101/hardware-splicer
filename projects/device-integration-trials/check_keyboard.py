"""Compare the interactive viewer's two-contact footprints against the HS relocation map."""

import argparse
from copy import deepcopy
import json
from pathlib import Path


def mismatches(pcb, rows):
    footprints = {part["ref"]: part for part in pcb["footprints"]}
    differences = []
    displayed = {ref for group in pcb["bom"]["both"] for ref, _ in group}
    for row in rows:
        for role in ("switch", "header"):
            ref = row[f"daughterboard_{role}_ref"]
            number = row[f"daughterboard_{role}_pad"]
            pins = [pad for pad in footprints[ref]["pads"] if pad.get("net")]
            if len(pins) != 2 or sum(bool(pad.get("pin1")) for pad in pins) != 1:
                raise ValueError(f"Expected one marked pin on a two-contact footprint: {ref}")
            actual, = (pad["net"] for pad in pins if bool(pad.get("pin1")) == (number == "1"))
            if actual != row["new_pcb_net"] or ref not in displayed:
                differences.append({"ref": ref, "pad": number, "expected": row["new_pcb_net"],
                                    "viewer_net": actual})
    return differences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("relocation_map", type=Path)
    args = parser.parse_args()
    pcb, _ = json.JSONDecoder().raw_decode(args.html.read_text().split("var pcbdata = ", 1)[1])
    mapping = json.loads(args.relocation_map.read_text())
    rows = [wire for key in mapping["source_wiring_map"] for wire in key["wire_map"]]
    wrong = deepcopy(rows)
    wrong[0]["daughterboard_header_pad"], wrong[1]["daughterboard_header_pad"] = (
        wrong[1]["daughterboard_header_pad"], wrong[0]["daughterboard_header_pad"])
    actual, control = mismatches(pcb, rows), mismatches(pcb, wrong)
    if actual or len(control) != 2:
        raise ValueError({"expected_mapping": actual, "swapped_header_control": control})
    print(json.dumps({"keys": [key["original_label"] for key in mapping["source_wiring_map"]],
                      "wires": len(rows), "endpoints_checked": 2 * len(rows),
                      "mismatches": actual, "swapped_header_control": control}, indent=2))
