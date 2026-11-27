"""JLCPCB assembly files for HS-BUS-A: BOM (Comment, Designator, Footprint, LCSC Part #) and CPL (Designator, Mid X, Mid Y,
Layer, Rotation), from the board's own records. Nothing is uploaded or ordered: that is the owner's step.

    python3 projects/hs-bus-a/jlc_order_files.py

LCSC codes come from verification.json's jlcparts pricing (lines matched by keyword were checked against the BOM's value,
rating and package on 2026-11-28). Placement comes from fab/hs_bus_a_pos.csv. JLCPCB's own placement preview must still be
checked: its rotation zero differs from KiCad's for some footprints (diodes, SOT-23, connectors), and it corrects nothing.
"""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "fab" / "jlc"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = json.loads((HERE / "verification.json").read_text())["bom_pricing"]["1_boards"]["lines"]
    lcsc = {ref: line["lcsc"] for line in lines for ref in line["refs"]}
    with open(HERE / "fab" / "hs_bus_a_bom.csv", newline="") as f:
        bom = list(csv.DictReader(f))
    with open(HERE / "fab" / "hs_bus_a_pos.csv", newline="") as f:
        pos = list(csv.DictReader(f))
    placed = {p["Ref"] for p in pos}
    # KiCad's position file leaves through-hole parts out (C7, J1's shell, J2-J5); JLCPCB places or hand-solders them and
    # needs them too. Their footprint origins come from the board file, with Y negated as the position file writes it.
    board = (HERE / "kicad" / "hs_bus_a.kicad_pcb").read_text()
    for m in re.finditer(r'\(footprint "([^"]+)"(.*?)\(property "Reference" "([^"]+)"', board, re.S):
        ref = m.group(3)
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", m.group(2))
        if ref not in placed and at and not ref.startswith(("H", "#", "TP", "G")):
            pos.append({"Ref": ref, "PosX": at.group(1), "PosY": str(-float(at.group(2))), "Rot": at.group(3) or "0",
                        "Side": "top" if '(layer "F.Cu")' in m.group(2) else "bottom", "from": "board file (through-hole)"})
    rows, missing = [], []
    for item in bom:
        refs = expand(item["Refs"])
        codes = {lcsc.get(r) for r in refs}
        if None in codes or len(codes) != 1:
            missing.append(item["Refs"])
        rows.append([f'{item["Value"]} ({item["MPN"]})', ",".join(refs), item["Footprint"].split(":")[-1], next(iter(codes)) or ""])
    with open(OUT / "hs_bus_a_bom_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerows(rows)
    with open(OUT / "hs_bus_a_cpl_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in pos:
            w.writerow([p["Ref"], f'{float(p["PosX"]):.4f}mm', f'{float(p["PosY"]):.4f}mm', "Top" if p["Side"] == "top" else "Bottom", f'{float(p["Rot"]) % 360:g}'])
    placed = {p["Ref"] for p in pos}
    unplaced = sorted(r for item in bom for r in expand(item["Refs"]) if r not in placed)
    print(json.dumps({"bom_lines": len(rows), "without_lcsc": missing, "in_bom_not_in_cpl": unplaced, "through_hole_from_board": sorted(p["Ref"] for p in pos if p.get("from")), "out": str(OUT)}, indent=1))


def expand(refs: str) -> list[str]:
    out = []
    for part in refs.split(","):
        if "-" in part:
            a, b = part.split("-")
            prefix = a.rstrip("0123456789")
            out += [f"{prefix}{i}" for i in range(int(a[len(prefix):]), int(b[len(prefix):]) + 1)]
        else:
            out.append(part)
    return out


if __name__ == "__main__":
    main()
