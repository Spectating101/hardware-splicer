"""Distance from each IC supply pad to its nearest small capacitor on the same net (KiCad's pcbnew; KiCad 9 or 10).

    <kicad python> decoupling_report.py board.kicad_pcb [--max-mm 5]

Prints JSON: one row per IC pad on a net that carries a capacitor of 1 uF or less, with the nearest such capacitor and
its distance (pad centre to pad centre). Bulk capacitors (over 1 uF) and ground nets are left out.
"""
import json
import math
import re
import sys

import pcbnew

UNIT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3}


def farads(value: str):
    m = re.match(r"\s*([\d.]+)\s*([pnuµm]?)", value or "")
    return float(m.group(1)) * UNIT.get(m.group(2), 1.0) if m else None


def main(argv):
    board = pcbnew.LoadBoard(argv[0])
    limit = float(argv[argv.index("--max-mm") + 1]) if "--max-mm" in argv else 5.0
    caps, ics = {}, []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net or re.search(r"GND|VSS", net, re.I):
                continue
            xy = (pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y))
            if ref.startswith("C"):
                f = farads(fp.GetValue())
                if f is not None and f <= 1e-6:
                    caps.setdefault(net, []).append((ref, xy))
            elif re.match(r"(U|IC)\d", ref):
                ics.append((ref, pad.GetNumber(), net, xy))
    rows = []
    for ref, num, net, xy in ics:
        if net not in caps:
            continue
        cap, d = min(((c, math.hypot(cxy[0] - xy[0], cxy[1] - xy[1])) for c, cxy in caps[net]), key=lambda t: t[1])
        rows.append({"ic": ref, "pad": num, "net": net, "nearest_cap": cap, "distance_mm": round(d, 1), "over_limit": d > limit})
    print(json.dumps({"limit_mm": limit, "pads": sorted(rows, key=lambda r: -r["distance_mm"])}))


if __name__ == "__main__":
    main(sys.argv[1:])
