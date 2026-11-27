"""Draft a device-planner module entry from a maker's Eagle board file.

Adafruit and others publish the Eagle board (.brd) for their breakouts. That file is the maker's own geometry: the board
outline, where each header pad sits, which net each pad carries, and the mounting holes. This turns it into the geometric
half of a ``device_modules.json`` entry, every figure traceable to the file and the commit it was read from.

It does not invent the electrical half. I2C addresses, supply notes, currents and quotes must come from the maker's text,
so the draft lists them as gaps for a person to fill from a cited page. Pin roles come from the net names on the pads by a
small fixed table (GND, Vin, 3Vo, SDA, SCL); any other pin gets no role. The draft is not added to the library by this
module; it is a starting point to review.

    PYTHONPATH=src python -m hardware_splicer.eagle_board_import board.brd --url <pinned board URL> --id <new id> [--mirror]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Net names on Adafruit boards, to planner pin roles. Anything else is left without a role.
ROLE_BY_NET = {
    "GND": ["ground"],
    "VIN": ["power_in"], "VCC": ["power_in"],
    "3.3V": ["power_3v3"], "3V": ["power_3v3"], "3VO": ["power_3v3"], "3V3": ["power_3v3"],
    "SDA": ["i2c_sda"], "SCL": ["i2c_scl"],
}
MAX_BYTES = 8 * 1024 * 1024


class EagleImportError(ValueError):
    pass


def _f(value: str | None) -> float:
    return float(value) if value is not None else 0.0


def _rotate(x: float, y: float, rot: str | None) -> tuple[float, float, bool]:
    """Eagle element rotation 'R90', 'MR180' and so on: mirror first (bottom side), then rotate."""
    rot = rot or "R0"
    mirrored = rot.startswith("M")
    angle = float(re.sub(r"[^0-9.]", "", rot) or 0)
    if mirrored:
        x = -x
    turns = round(angle / 90) % 4
    for _ in range(turns):
        x, y = -y, x
    return x, y, mirrored


def read_board(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_BYTES:
        raise EagleImportError("board file larger than 8 MB")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise EagleImportError(f"not an Eagle XML board file: {exc}") from exc
    board = root.find("drawing/board")
    if board is None:
        raise EagleImportError("no <board> in this file (a schematic, or an old binary Eagle file?)")
    xs, ys = [], []
    for wire in board.findall("plain/wire"):
        if wire.get("layer") == "20":  # Dimension: the board outline
            xs += [_f(wire.get("x1")), _f(wire.get("x2"))]
            ys += [_f(wire.get("y1")), _f(wire.get("y2"))]
    if not xs:
        raise EagleImportError("the board has no outline on the Dimension layer")
    outline = (min(xs), min(ys), max(xs), max(ys))
    packages = {(lib.get("name"), pkg.get("name")): pkg for lib in board.findall("libraries/library") for pkg in lib.findall("packages/package")}
    nets: dict[tuple[str, str], str] = {}
    for signal in board.findall("signals/signal"):
        for ref in signal.findall("contactref"):
            nets[(ref.get("element"), ref.get("pad"))] = signal.get("name")
    elements = []
    for element in board.findall("elements/element"):
        pkg = packages.get((element.get("library"), element.get("package")))
        pads = []
        if pkg is not None:
            for pad in pkg.findall("pad") + pkg.findall("smd"):
                dx, dy, _ = _rotate(_f(pad.get("x")), _f(pad.get("y")), element.get("rot"))
                pads.append({"pad": pad.get("name"), "x": _f(element.get("x")) + dx, "y": _f(element.get("y")) + dy,
                             "net": nets.get((element.get("name"), pad.get("name"))), "through_hole": pad.tag == "pad"})
        elements.append({"name": element.get("name"), "package": element.get("package") or "", "value": element.get("value") or "",
                         "x": _f(element.get("x")), "y": _f(element.get("y")), "rot": element.get("rot") or "R0", "pads": pads})
    return {"outline": outline, "elements": elements}


def draft_entry(data: bytes, *, module_id: str, url: str, name: str = "", kind: str = "i2c_breakout", mirror: bool = False) -> dict[str, Any]:
    """The planner entry's geometry from a board file. ``mirror`` gives the front view of a board whose file draws the other
    face, as for a display whose glass is on the board's bottom layer."""

    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,63}", module_id):
        raise EagleImportError("module id must be 3 to 64 lowercase letters, digits, dots or hyphens")
    if not re.match(r"https://github\.com/[^/]+/[^/]+/blob/[0-9a-f]{7,40}/", url):
        raise EagleImportError("the url must be a GitHub blob link pinned to a commit, so the figures can be traced")
    board = read_board(data)
    x0, y0, x1, y1 = board["outline"]
    width, height = x1 - x0, y1 - y0

    def frame(x: float, y: float) -> tuple[float, float]:
        fx = (x1 - x) if mirror else (x - x0)
        return round(fx, 2), round(y1 - y, 2)  # top-left origin, y down

    headers = [e for e in board["elements"] if re.match(r"1X\d+", e["package"]) and all(p["through_hole"] for p in e["pads"]) and e["pads"]]
    if not headers:
        raise EagleImportError("no single-row header (package 1Xnn) on this board")
    pins, seen = [], set()
    for header in headers:
        for pad in sorted(header["pads"], key=lambda p: int(re.sub(r"\D", "", p["pad"] or "0") or 0)):
            net = (pad["net"] or f"{header['name']}-{pad['pad']}").strip()
            label = re.sub(r"_\d(\.\d)?V$", "", net)  # Adafruit names level-shifted nets like RST_5.0V
            pin_id = label if label not in seen else f"{label}-{header['name']}-{pad['pad']}"
            seen.add(pin_id)
            x, y = frame(pad["x"], pad["y"])
            pins.append({"id": pin_id, "name": label, "roles": ROLE_BY_NET.get(label.upper(), []), "x": x, "y": y, "side": "top",
                         "board_pad": f"{header['name']}.{pad['pad']}"})
    holes = [frame(e["x"], e["y"]) for e in board["elements"] if "MOUNTINGHOLE" in e["package"].upper()]
    sockets = [{"element": e["name"], "x": frame(e["x"], e["y"])[0], "y": frame(e["x"], e["y"])[1]} for e in board["elements"]
               if "JST_SH" in e["package"].upper()]
    roles = {r for p in pins for r in p["roles"]}
    gaps = [{"field": f, "reason": r} for f, r in (
        ("i2c.addresses", "Not in the board file; take it from the maker's page and quote it."),
        ("electrical.supply_note", "Regulator and level shifting are the maker's claims; quote their page."),
        ("engineering.loads", "Supply current is not in the board file."),
        ("above_board_mm / below_board_mm", "Component heights are not in the board file; measure or take the maker's overall size."),
    )]
    if not {"i2c_sda", "i2c_scl"} <= roles:
        gaps.append({"field": "pins.roles", "reason": "No pads on nets named SDA and SCL; assign the I2C pins by hand from the maker's pinout."})
    return {
        "id": module_id, "name": name or module_id, "kind": kind,
        "frame": ("Front view (the face the board file draws as the bottom), " if mirror else "Top view, ")
                 + "origin at the board's top-left corner, from the maker's board file.",
        "pcb_mm": {"x": round(width, 2), "y": round(height, 2), "z": 1.6},
        "pins": pins, "pin_order_varies": False,
        "dimension_basis": {
            "pcb": f"Board file outline {round(width, 2)} x {round(height, 2)} mm. Thickness 1.6 mm is the usual stock, not in the file.",
            "pins": "Header pad positions and net names from the board file" + (", mirrored to the front view." if mirror else "."),
            "holes": "Mounting holes at " + ", ".join(f"({x:g}, {y:g})" for x, y in holes) + " mm." if holes else "No mounting holes in the board file.",
        },
        "stemma_qt_sockets": sockets,
        "sources": [{"label": "Maker's board file", "url": url}],
        "draft": {"status": "GEOMETRY_ONLY_DRAFT", "gaps": gaps,
                  "note": "Not added to the library. Fill the gaps from cited maker text, then review before adding."},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", type=Path)
    ap.add_argument("--url", required=True, help="GitHub blob URL of the board file, pinned to a commit")
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--kind", default="i2c_breakout", choices=["i2c_breakout", "display"])
    ap.add_argument("--mirror", action="store_true", help="front view of a board whose file draws the other face")
    args = ap.parse_args(argv)
    try:
        entry = draft_entry(args.board.read_bytes(), module_id=args.id, url=args.url, name=args.name, kind=args.kind, mirror=args.mirror)
    except (EagleImportError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
