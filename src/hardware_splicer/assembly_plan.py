"""An ordered, visual build sequence for one retained PCB revision.

The plan is derived from the board file alone: where each part sits, how big its outline is, which pads share a net.
It is a view of retained bytes. It carries no engineering authority, never rewrites a snapshot, revision, pin or review,
and approves nothing: a part drawn in place is not a part that works, and a suggested check is not a result.

Two things in it are estimates and say so. A part's height is not in a KiCad board file, so it is taken from a small table
of typical package heights (``height_basis`` names the row used). The assembly order is a conventional one, low parts
before tall ones; it is not the manufacturer's instruction.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .kicad_diff import KicadDiffError, parse_kicad_sexp

ASSEMBLY_PLAN_SCHEMA = "hardware_splicer.assembly_plan.v1"

MAX_PARTS = 2000
MAX_PADS_PER_PART = 400
MAX_CHECKS_PER_STEP = 3
MAX_CONNECTION_PEERS = 6
DEFAULT_THICKNESS_MM = 1.6

AUTHORITY_STATEMENT = (
    "This is a view of the retained board file. Positions and outlines come from the file; heights are typical values for "
    "the package, not measurements. The order is conventional, not the manufacturer's. A suggested check is something to "
    "try, not a result. Nothing here approves building, powering or releasing the board."
)

# (pattern on the footprint name, height in mm, basis). First match wins. Heights are typical seated heights above the board.
_HEIGHTS: tuple[tuple[str, float, str], ...] = (
    (r"R_0402|C_0402|L_0402|LED_0402", 0.5, "typical 0402 chip"),
    (r"R_0603|L_0603|FB_0603", 0.55, "typical 0603 chip"),
    (r"C_0603", 0.8, "typical 0603 capacitor"),
    (r"R_0805|L_0805", 0.6, "typical 0805 chip"),
    (r"C_0805", 1.2, "typical 0805 capacitor"),
    (r"R_1206|L_1206|C_1206", 0.9, "typical 1206 chip"),
    (r"LED_0603|LED_0805", 0.8, "typical chip LED"),
    (r"SOT-23|SOT-323|SC-70", 1.1, "typical SOT-23 package"),
    (r"SOIC|SOP|SO-", 1.75, "typical SOIC package"),
    (r"TSSOP|MSOP|SSOP", 1.2, "typical TSSOP package"),
    (r"QFN|DFN|LGA", 0.9, "typical leadless package"),
    (r"LQFP|TQFP|QFP", 1.6, "typical QFP package"),
    (r"WSON|USON|UDFN", 0.8, "typical thin leadless package"),
    (r"PinHeader|PinSocket|Pin_Header", 8.5, "typical 2.54 mm header with pins"),
    (r"JST|Molex|Conn", 6.0, "typical wire connector"),
    (r"USB", 3.5, "typical USB connector"),
    (r"TestPoint|Test_Point", 0.3, "test pad"),
    (r"SW_|Button|Switch", 4.5, "typical tactile switch"),
    (r"Crystal|Oscillator", 1.5, "typical SMD crystal"),
    (r"CP_Elec|C_Elec", 8.0, "typical electrolytic capacitor"),
)
_KIND_DEFAULT_HEIGHT = {
    "passive": (0.8, "default for a passive"),
    "ic": (1.5, "default for an IC"),
    "connector": (6.0, "default for a connector"),
    "testpoint": (0.3, "test pad"),
    "mounting_hole": (0.0, "hole in the board"),
    "other": (2.0, "unknown package, default"),
}

_REF_KIND = (
    (re.compile(r"^TP\d*"), "testpoint"),
    (re.compile(r"^(H|MH)\d+"), "mounting_hole"),
    (re.compile(r"^(JP|J|P|CN|X)\d+"), "connector"),
    (re.compile(r"^(U|IC)\d+"), "ic"),
    (re.compile(r"^(Q|T)\d+"), "ic"),
    (re.compile(r"^(R|C|L|D|F|FB|LED|RN)\d+"), "passive"),
    (re.compile(r"^(SW|S|BT|Y|BZ|K)\d+"), "other"),
)

_PHASE = {"passive": 0, "ic": 1, "other": 2, "testpoint": 3, "connector": 4, "mounting_hole": 5}
_NOUN = {
    "passive": ("part", "parts"),
    "ic": ("chip", "chips"),
    "other": ("part", "parts"),
    "testpoint": ("test point", "test points"),
    "connector": ("connector", "connectors"),
    "mounting_hole": ("mounting hole", "mounting holes"),
}
_PREFIX_NOUN = {
    "R": ("resistor", "resistors"),
    "RN": ("resistor network", "resistor networks"),
    "C": ("capacitor", "capacitors"),
    "L": ("inductor", "inductors"),
    "FB": ("ferrite bead", "ferrite beads"),
    "D": ("diode", "diodes"),
    "LED": ("LED", "LEDs"),
    "F": ("fuse", "fuses"),
    "Q": ("transistor", "transistors"),
    "SW": ("switch", "switches"),
    "Y": ("crystal", "crystals"),
}
_POWER = re.compile(r"(^|/)(\+?3V3|\+?3\.3V|\+?5V|VCC|VDD|VBUS|VIN)$", re.IGNORECASE)
_GROUND = re.compile(r"(^|/)(GND|VSS|AGND|DGND)$", re.IGNORECASE)


class AssemblyPlanError(ValueError):
    """The bytes are not a board this plan can read."""


def _num(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _children(node: Any, head: str) -> list[list[Any]]:
    return [child for child in node if isinstance(child, list) and child and child[0] == head]


def _first(node: Any, head: str) -> list[Any] | None:
    found = _children(node, head)
    return found[0] if found else None


def _at(node: Any) -> tuple[float, float, float]:
    at = _first(node, "at")
    if not at:
        return 0.0, 0.0, 0.0
    return _num(at[1] if len(at) > 1 else 0), _num(at[2] if len(at) > 2 else 0), _num(at[3] if len(at) > 3 else 0)


def _property(footprint: list[Any], name: str) -> str:
    for prop in _children(footprint, "property"):
        if len(prop) > 2 and prop[1] == name and isinstance(prop[2], str):
            return prop[2]
    return ""


def _layer_of(node: list[Any]) -> str:
    layer = _first(node, "layer")
    return str(layer[1]) if layer and len(layer) > 1 else ""


def _points_of(item: list[Any]) -> list[tuple[float, float]]:
    head = item[0]
    points: list[tuple[float, float]] = []
    if head in {"fp_line", "fp_rect", "gr_line", "gr_rect"}:
        for key in ("start", "end"):
            node = _first(item, key)
            if node and len(node) > 2:
                points.append((_num(node[1]), _num(node[2])))
    elif head in {"fp_circle", "gr_circle"}:
        centre, end = _first(item, "center"), _first(item, "end")
        if centre and end and len(centre) > 2 and len(end) > 2:
            cx, cy = _num(centre[1]), _num(centre[2])
            radius = math.hypot(_num(end[1]) - cx, _num(end[2]) - cy)
            points += [(cx - radius, cy - radius), (cx + radius, cy + radius)]
    elif head in {"gr_arc", "fp_arc"}:
        for key in ("start", "mid", "end"):
            node = _first(item, key)
            if node and len(node) > 2:
                points.append((_num(node[1]), _num(node[2])))
    elif head in {"fp_poly", "gr_poly"}:
        pts = _first(item, "pts")
        for xy in _children(pts or [], "xy"):
            if len(xy) > 2:
                points.append((_num(xy[1]), _num(xy[2])))
    return points


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _to_board(x: float, y: float, origin: tuple[float, float], degrees: float, mirrored: bool) -> tuple[float, float]:
    """A footprint-local point to board coordinates, as KiCad does it: mirror a back-side part, rotate, then translate."""

    if mirrored:
        x = -x
    radians = math.radians(degrees)
    cos, sin = math.cos(radians), math.sin(radians)
    return origin[0] + x * cos + y * sin, origin[1] + y * cos - x * sin


def _classify(ref: str, footprint: str) -> str:
    for pattern, kind in _REF_KIND:
        if pattern.match(ref):
            return kind
    lowered = footprint.lower()
    if "testpoint" in lowered:
        return "testpoint"
    if "mountinghole" in lowered:
        return "mounting_hole"
    if "pinheader" in lowered or "pinsocket" in lowered:
        return "connector"
    return "other"


def _height(footprint: str, kind: str) -> tuple[float, str]:
    if kind == "mounting_hole":
        return _KIND_DEFAULT_HEIGHT["mounting_hole"]
    for pattern, height, basis in _HEIGHTS:
        if re.search(pattern, footprint, re.IGNORECASE):
            return height, basis
    return _KIND_DEFAULT_HEIGHT.get(kind, _KIND_DEFAULT_HEIGHT["other"])


def _rounded(value: float) -> float:
    return round(value, 3) + 0.0


def _board(tree: list[Any]) -> dict[str, Any]:
    general = _first(tree, "general")
    thickness = DEFAULT_THICKNESS_MM
    basis = "default: the file does not state a thickness"
    if general:
        node = _first(general, "thickness")
        if node and len(node) > 1 and _num(node[1]) > 0:
            thickness, basis = _num(node[1]), "stated in the board file"
    edge_items = [
        item
        for item in tree
        if isinstance(item, list) and item and item[0] in {"gr_line", "gr_rect", "gr_arc", "gr_circle", "gr_poly"} and _layer_of(item) == "Edge.Cuts"
    ]
    points = [p for item in edge_items for p in _points_of(item)]
    box = _bbox(points)
    if box is None:
        raise AssemblyPlanError("the board has no outline on Edge.Cuts")
    x0, y0, x1, y1 = box
    only_straight = all(item[0] in {"gr_line", "gr_rect"} for item in edge_items)
    on_edges = all(
        (math.isclose(x, x0, abs_tol=1e-3) or math.isclose(x, x1, abs_tol=1e-3))
        and (math.isclose(y, y0, abs_tol=1e-3) or math.isclose(y, y1, abs_tol=1e-3))
        for x, y in points
    )
    return {
        "thickness_mm": _rounded(thickness),
        "thickness_basis": basis,
        "outline": {
            "kind": "rectangle" if only_straight and on_edges else "bounding_box_of_irregular_outline",
            "bbox": {"x0": _rounded(x0), "y0": _rounded(y0), "x1": _rounded(x1), "y1": _rounded(y1)},
        },
        "size_mm": [_rounded(x1 - x0), _rounded(y1 - y0)],
    }


def _part(footprint: list[Any]) -> dict[str, Any] | None:
    name = footprint[1] if len(footprint) > 1 and isinstance(footprint[1], str) else ""
    ref = _property(footprint, "Reference")
    if not ref:
        for text in _children(footprint, "fp_text"):
            if len(text) > 2 and text[1] == "reference":
                ref = str(text[2])
    if not ref:
        return None
    layer = _layer_of(footprint)
    mirrored = layer.startswith("B.")
    x, y, degrees = _at(footprint)
    crtyd = "B.CrtYd" if mirrored else "F.CrtYd"

    local_points: list[tuple[float, float]] = []
    for item in footprint:
        if isinstance(item, list) and item and item[0] in {"fp_line", "fp_rect", "fp_circle", "fp_poly", "fp_arc"} and _layer_of(item) == crtyd:
            local_points += _points_of(item)
    pads = []
    for pad in _children(footprint, "pad")[:MAX_PADS_PER_PART]:
        px, py, _ = _at(pad)
        size = _first(pad, "size")
        net = _first(pad, "net")
        pads.append(
            {
                "number": str(pad[1]) if len(pad) > 1 else "",
                "x": px,
                "y": py,
                "w": _num(size[1]) if size and len(size) > 1 else 0.0,
                "h": _num(size[2]) if size and len(size) > 2 else 0.0,
                "net": str(net[2]) if net and len(net) > 2 else "",
            }
        )
    basis = "courtyard outline"
    box = _bbox(local_points)
    if box is None:
        extent = [(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2) for p in pads] + [(p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in pads]
        box = _bbox(extent)
        basis = "pad extent (the footprint has no courtyard)"
    if box is None:
        box, basis = (-0.5, -0.5, 0.5, 0.5), "no outline or pads in the footprint"
    lx0, ly0, lx1, ly1 = box
    corners = [_to_board(cx, cy, (x, y), degrees, mirrored) for cx, cy in ((lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1))]

    kind = _classify(ref, name)
    height, height_basis = _height(name, kind)
    pin1 = None
    if kind in {"ic", "connector"} and len(pads) > 1:
        for pad in pads:
            if pad["number"] == "1":
                px, py = _to_board(pad["x"], pad["y"], (x, y), degrees, mirrored)
                pin1 = {"x": _rounded(px), "y": _rounded(py)}
                break
    return {
        "ref": ref,
        "value": _property(footprint, "Value"),
        "footprint": name,
        "kind": kind,
        "side": "back" if mirrored else "front",
        "x": _rounded(x),
        "y": _rounded(y),
        "rotation_deg": _rounded(degrees),
        "corners": [[_rounded(cx), _rounded(cy)] for cx, cy in corners],
        "outline_basis": basis,
        "height_mm": _rounded(height),
        "height_basis": height_basis,
        "pin1": pin1,
        "pad_count": len(pads),
        "_pads": pads,
        "_pad_world": [(_to_board(p["x"], p["y"], (x, y), degrees, mirrored), p) for p in pads],
    }


def _compress(refs: list[str]) -> str:
    """R1, R2, R3, R5 -> 'R1–R3, R5'."""

    parsed = []
    for ref in refs:
        match = re.fullmatch(r"([A-Za-z]+)(\d+)", ref)
        parsed.append((match.group(1), int(match.group(2)), ref) if match else (ref, -1, ref))
    parsed.sort(key=lambda row: (row[0], row[1], row[2]))
    out: list[str] = []
    index = 0
    while index < len(parsed):
        prefix, number, ref = parsed[index]
        end = index
        while number >= 0 and end + 1 < len(parsed) and parsed[end + 1][0] == prefix and parsed[end + 1][1] == parsed[end][1] + 1:
            end += 1
        out.append(ref if end - index < 2 else f"{ref}–{parsed[end][2]}")
        if end - index == 1:
            out[-1] = f"{ref}, {parsed[end][2]}"
        index = end + 1
    return ", ".join(out)


def _step_text(kind: str, side: str, parts: list[dict[str, Any]]) -> tuple[str, str]:
    one, many = _NOUN[kind]
    count = len(parts)
    refs = _compress([p["ref"] for p in parts])
    value = parts[0]["value"]
    label = f"{value} " if value and kind in {"passive", "ic", "other", "connector"} and len({p["value"] for p in parts}) == 1 else ""
    prefix = re.match(r"[A-Za-z]+", parts[0]["ref"])
    prefixes = {re.match(r"[A-Za-z]+", p["ref"]).group(0) for p in parts if re.match(r"[A-Za-z]+", p["ref"])}
    if prefix and len(prefixes) == 1 and prefix.group(0) in _PREFIX_NOUN:
        one, many = _PREFIX_NOUN[prefix.group(0)]
    noun = one if count == 1 else many
    where = "on the front" if side == "front" else "on the back"
    if kind == "mounting_hole":
        title = f"Fit the {count} mounting {'hole' if count == 1 else 'holes'}: {refs}"
        text = f"Fit mounting hardware at {refs}. Use hardware that matches the hole size on the drawing."
    elif kind == "testpoint":
        title = f"Add {count} test {'point' if count == 1 else 'points'}: {refs}"
        text = f"Solder the {count} test {'point' if count == 1 else 'points'} {refs} {where}. They stay unconnected to anything else."
    elif kind == "connector":
        title = f"Solder the {label}{noun} {refs}" if count == 1 else f"Solder {count} {label}{noun}: {refs}"
        text = f"Seat {refs} flat against the board {where}, then solder every pin. Pin 1 is marked on the drawing."
    else:
        title = f"Solder the {label}{noun} {refs}" if count == 1 else f"Solder {count} {label}{noun}: {refs}"
        text = f"Place {refs} {where} {'in the highlighted spot' if count == 1 else 'in the highlighted spots'}, then solder {'it' if count == 1 else 'them'}."
        if kind == "ic":
            text += " Match pin 1 to the marker."
    return title, text


def _checks(step_parts: list[dict[str, Any]], placed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Continuity checks that become possible once this step's parts are in: same net, one end here, the other already placed."""

    suggestions: list[dict[str, Any]] = []
    placed_refs = {p["ref"] for p in placed}
    for part in sorted(step_parts, key=lambda p: p["ref"]):
        for _, pad in part["_pad_world"]:
            if not pad["net"] or pad["net"].startswith("unconnected"):
                continue
            for other in placed:
                if other["ref"] == part["ref"] or other["ref"] not in placed_refs:
                    continue
                for _, other_pad in other["_pad_world"]:
                    if other_pad["net"] == pad["net"]:
                        suggestions.append(
                            {
                                "kind": "suggested_check",
                                "check": "continuity",
                                "from": f"{part['ref']} pin {pad['number']}",
                                "to": f"{other['ref']} pin {other_pad['number']}",
                                "net": pad["net"],
                                "expect": "the two points are connected",
                            }
                        )
                        break
                else:
                    continue
                break
            if len(suggestions) >= MAX_CHECKS_PER_STEP:
                return suggestions
    return suggestions


def _isolation_checks(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nets = {pad["net"] for part in parts for pad in part["_pads"] if pad["net"]}
    grounds = sorted(n for n in nets if _GROUND.search(n))
    rails = sorted(n for n in nets if _POWER.search(n))
    return [
        {
            "kind": "suggested_check",
            "check": "isolation",
            "from": ground,
            "to": rail,
            "net": f"{ground} / {rail}",
            "expect": "the two are NOT connected before first power",
        }
        for ground in grounds[:1]
        for rail in rails[:3]
    ]


def _connections(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_net: dict[str, list[tuple[str, str]]] = {}
    for part in parts:
        for _, pad in part["_pad_world"]:
            if pad["net"] and not pad["net"].startswith("unconnected"):
                by_net.setdefault(pad["net"], []).append((part["ref"], pad["number"]))
    rows = []
    for part in sorted((p for p in parts if p["kind"] == "connector"), key=lambda p: p["ref"]):
        pins = []
        for _, pad in sorted(part["_pad_world"], key=lambda row: (len(row[1]["number"]), row[1]["number"])):
            peers = [f"{ref} pin {number}" for ref, number in by_net.get(pad["net"], []) if ref != part["ref"]]
            pins.append(
                {
                    "pin": pad["number"],
                    "net": pad["net"] or None,
                    "also_on": peers[:MAX_CONNECTION_PEERS],
                    "also_on_total": len(peers),
                }
            )
        rows.append({"ref": part["ref"], "value": part["value"], "footprint": part["footprint"], "pins": pins})
    return rows


def build_assembly_plan(pcb_text: str, *, pcb_sha256: str | None = None) -> dict[str, Any]:
    """The plan for the board in ``pcb_text``. Pure: no I/O, deterministic for the same bytes."""

    if not isinstance(pcb_text, str):
        raise AssemblyPlanError("the board must be text")
    try:
        tree = parse_kicad_sexp(pcb_text)
    except KicadDiffError as exc:
        raise AssemblyPlanError("the board file could not be read") from exc
    if not tree or tree[0] != "kicad_pcb":
        raise AssemblyPlanError("not a KiCad board")

    footprints = _children(tree, "footprint")
    warnings: list[str] = []
    if len(footprints) > MAX_PARTS:
        warnings.append(f"Only the first {MAX_PARTS} of {len(footprints)} parts are included.")
        footprints = footprints[:MAX_PARTS]
    parts = [part for part in (_part(fp) for fp in footprints) if part is not None]
    parts.sort(key=lambda p: (p["side"] != "front", _PHASE.get(p["kind"], 2), p["height_mm"], p["footprint"], p["value"], p["ref"]))

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for part in parts:
        value = "" if part["kind"] in {"testpoint", "mounting_hole"} else part["value"]
        groups.setdefault((part["side"], _PHASE.get(part["kind"], 2), part["kind"], part["footprint"], value), []).append(part)

    steps: list[dict[str, Any]] = []
    placed: list[dict[str, Any]] = []
    current_side = "front"
    for key in sorted(groups, key=lambda k: (k[0] != "front", k[1], groups[k][0]["height_mm"], k[3], k[4])):
        side, _phase, kind, _footprint, _value = key
        members = sorted(groups[key], key=lambda p: p["ref"])
        title, text = _step_text(kind, side, members)
        placed.extend(members)
        steps.append(
            {
                "step_id": f"step-{len(steps) + 1:02d}",
                "order": len(steps) + 1,
                "title": title,
                "instruction": text,
                "kind": kind,
                "side": side,
                "turn_board_over": side != current_side,
                "refs": [p["ref"] for p in members],
                "checks": _checks(members, placed) if kind != "mounting_hole" else [],
            }
        )
        current_side = side
    if steps:
        steps.append(
            {
                "step_id": f"step-{len(steps) + 1:02d}",
                "order": len(steps) + 1,
                "title": "Check the board before first power",
                "instruction": "Before connecting power, look for shorts between the supply and ground with a meter. These are suggestions to try, not results.",
                "kind": "verify",
                "side": current_side,
                "turn_board_over": False,
                "refs": [],
                "checks": _isolation_checks(parts),
            }
        )

    public = []
    for part in parts:
        row = {k: v for k, v in part.items() if not k.startswith("_")}
        public.append(row)
    return {
        "schema_version": ASSEMBLY_PLAN_SCHEMA,
        "authority": AUTHORITY_STATEMENT,
        "source": {"pcb_sha256": pcb_sha256},
        "board": _board(tree),
        "parts": public,
        "steps": steps,
        "connections": _connections(parts),
        "counts": {"parts": len(public), "steps": len(steps)},
        "warnings": warnings,
    }
