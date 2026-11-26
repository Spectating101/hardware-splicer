"""Component-level KiCad boards: real library symbols and footprints, and the checks that close the loop.

A design is a list of parts (each a KiCad library symbol and footprint) and named nets of ``REF.PIN`` endpoints. This
module writes the schematic from it and checks that what KiCad reads back is what was meant:

* ``write_schematic``: a ``.kicad_sch`` whose symbols are copied from the installed KiCad libraries (derived symbols
  flattened). Each connected pin gets a short wire and a net label; each pin declared unused gets a no-connect flag.
* ``pin_coverage``: every pin of every symbol is either on a net or declared unused, and every endpoint exists.
* ``schematic_netlist`` and ``netlist_parity``: KiCad's own netlist export of the schematic, compared net by net with
  the design. A label that lands on the wrong pin, or a stub that touches another pin, shows up here.
* ``pcb_spec``: the placement and the schematic's own nets for ``_pcbnew_helpers/build_component_board.py``, which
  places the library footprints with pcbnew. Routing, zone fill and DRC (with schematic parity) run from the project.

The KiCad libraries are read where KiCad installed them (``KICAD9_SYMBOL_DIR`` / ``KICAD9_FOOTPRINT_DIR`` or
``/usr/share/kicad``); none of their content is stored in this repository. Generated boards embed the symbols they use,
as KiCad itself does, under the libraries' design exception.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

GRID = 1.27
STUB = 2.54


def symbol_dir() -> Path:
    return Path(os.environ.get("KICAD9_SYMBOL_DIR") or "/usr/share/kicad/symbols")


def footprint_dir() -> Path:
    return Path(os.environ.get("KICAD9_FOOTPRINT_DIR") or "/usr/share/kicad/footprints")


# ---------------------------------------------------------------- S-expressions


class Q(str):
    """A quoted string token."""


def parse_sexpr(text: str) -> list:
    tokens = re.finditer(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack: list[list] = [[]]
    for match in tokens:
        tok = match.group(0)
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(Q(re.sub(r"\\(.)", r"\1", tok[1:-1])))
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced S-expression")
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def dump_sexpr(node: Any, indent: int = 0) -> str:
    if isinstance(node, Q):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if not isinstance(node, list):
        return str(node)
    flat = "(" + " ".join(dump_sexpr(n) for n in node) + ")"
    if len(flat) < 100 and not any(isinstance(n, list) and n and n[0] in ("symbol", "pin", "property") for n in node[1:]):
        return flat
    pad = "  " * (indent + 1)
    head = " ".join(dump_sexpr(n) for n in node if not isinstance(n, list))
    body = "\n".join(pad + dump_sexpr(n, indent + 1) for n in node if isinstance(n, list))
    return "(" + head + "\n" + body + ")"


def _child(node: list, key: str) -> list | None:
    return next((n for n in node if isinstance(n, list) and n and n[0] == key), None)


def _children(node: list, key: str) -> list[list]:
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


# ---------------------------------------------------------------- symbol libraries


_LIB_CACHE: dict[str, dict[str, list]] = {}


def _library(lib: str) -> dict[str, list]:
    if lib not in _LIB_CACHE:
        path = symbol_dir() / f"{lib}.kicad_sym"
        tree = parse_sexpr(path.read_text(encoding="utf-8"))
        _LIB_CACHE[lib] = {str(s[1]): s for s in _children(tree, "symbol")}
    return _LIB_CACHE[lib]


def library_symbol(lib_id: str) -> list:
    """The symbol, flattened (``extends`` resolved), named as a schematic embeds it: ``Lib:Name``."""
    lib, name = lib_id.split(":", 1)
    flat = _flatten(_library(lib), name)
    flat[1] = Q(lib_id)
    return flat


def _flatten(symbols: Mapping[str, list], name: str) -> list:
    node = symbols[name]
    ext = _child(node, "extends")
    if not ext:
        return copy.deepcopy(node)
    parent_name = str(ext[1])
    out = _flatten(symbols, parent_name)
    out[1] = Q(name)
    for sub in _children(out, "symbol"):
        sub[1] = Q(name + str(sub[1])[len(parent_name):])
    for prop in _children(node, "property"):
        old = next((p for p in _children(out, "property") if str(p[1]) == str(prop[1])), None)
        if old is not None:
            out[out.index(old)] = copy.deepcopy(prop)
        else:
            out.append(copy.deepcopy(prop))
    return out


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    etype: str
    x: float
    y: float
    angle: float
    unit: int
    hidden: bool


def symbol_pins(symbol: list) -> list[Pin]:
    pins = []
    for sub in _children(symbol, "symbol"):
        unit = int(str(sub[1]).rsplit("_", 2)[1])
        for pin in _children(sub, "pin"):
            at = _child(pin, "at")
            hidden = "hide" in pin or bool(_child(pin, "hide") and _child(pin, "hide")[1] == "yes")
            pins.append(Pin(number=str(_child(pin, "number")[1]), name=str(_child(pin, "name")[1]), etype=str(pin[1]),
                            x=float(at[1]), y=float(at[2]), angle=float(at[3]) if len(at) > 3 else 0.0, unit=unit,
                            hidden=hidden))
    return pins


def symbol_property(symbol: list, key: str) -> str | None:
    prop = next((p for p in _children(symbol, "property") if str(p[1]) == key), None)
    return str(prop[2]) if prop else None


# ---------------------------------------------------------------- design


@dataclass
class Part:
    ref: str
    lib_id: str
    value: str
    footprint: str = ""
    sch_xy: tuple[float, float] = (0.0, 0.0)
    pcb_xy: tuple[float, float] | None = None
    pcb_rot: float = 0.0
    pcb_side: str = "top"
    fields: dict[str, str] = field(default_factory=dict)
    board_only: bool = False


@dataclass
class Design:
    name: str
    title: str
    parts: list[Part]
    nets: dict[str, list[str]]  # net name -> ["REF.PIN", ...]
    unused: list[str] = field(default_factory=list)  # pins declared not connected
    power_flag_nets: list[str] = field(default_factory=list)  # nets fed from off the sheet (USB, a supply)
    paper: str = "A3"
    revision: str = "A"

    def part(self, ref: str) -> Part:
        return next(p for p in self.parts if p.ref == ref)


def _snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 4)


def pin_coverage(design: Design) -> dict[str, Any]:
    """Every pin is on exactly one net or declared unused; every named endpoint exists."""
    known: dict[str, set[str]] = {}
    for part in design.parts:
        known[part.ref] = {p.number for p in symbol_pins(library_symbol(part.lib_id))}
    seen: dict[str, list[str]] = {}
    unknown = []
    for net, ends in design.nets.items():
        for end in ends:
            ref, _, pin = end.partition(".")
            if pin not in known.get(ref, set()):
                unknown.append(f"{net}: {end}")
            seen.setdefault(end, []).append(net)
    for end in design.unused:
        ref, _, pin = end.partition(".")
        if pin not in known.get(ref, set()):
            unknown.append(f"unused: {end}")
        seen.setdefault(end, []).append("(unused)")
    multiple = {k: v for k, v in seen.items() if len(v) > 1}
    missing = sorted(f"{ref}.{pin}" for ref, pins in known.items() for pin in pins if f"{ref}.{pin}" not in seen)
    return {"pass": not (unknown or multiple or missing), "unknown_endpoints": unknown, "on_several_nets": multiple,
            "pins_neither_connected_nor_declared_unused": missing,
            "pins_total": sum(len(v) for v in known.values())}


# ---------------------------------------------------------------- schematic


def _effects(hide: bool = False, justify: str | None = None) -> list:
    eff: list = ["effects", ["font", ["size", 1.27, 1.27]]]
    if justify:
        eff.append(["justify", *justify.split()])
    if hide:
        eff.append(["hide", "yes"])
    return eff


def _uid() -> Q:
    return Q(str(uuid.uuid4()))


def _pin_point(part_xy: tuple[float, float], pin: Pin) -> tuple[float, float]:
    return (_snap(part_xy[0] + pin.x), _snap(part_xy[1] - pin.y))


def _outward(pin: Pin) -> tuple[float, float, int]:
    """Unit vector on the sheet pointing away from the symbol body, and the label angle for it."""
    a = int(round(pin.angle)) % 360
    return {0: (-1.0, 0.0, 180), 180: (1.0, 0.0, 0), 90: (0.0, 1.0, 270), 270: (0.0, -1.0, 90)}[a]


def write_schematic(design: Design, path: Path, symbol_uuids: dict[str, str] | None = None) -> dict[str, str]:
    """Write the schematic; returns the symbol UUID of each reference (footprints are linked to these)."""
    root = str(uuid.uuid4())
    symbol_uuids = dict(symbol_uuids or {})
    lib_ids = sorted({p.lib_id for p in design.parts} | ({"power:PWR_FLAG"} if design.power_flag_nets else set()))
    embedded = {lib_id: library_symbol(lib_id) for lib_id in lib_ids}
    pins_of = {lib_id: symbol_pins(sym) for lib_id, sym in embedded.items()}
    net_of = {end: net for net, ends in design.nets.items() for end in ends}
    body: list = []
    endpoints: dict[tuple[float, float], str] = {}

    def place(ref: str, lib_id: str, value: str, xy: tuple[float, float], footprint: str, fields: Mapping[str, str],
              power: bool = False) -> None:
        sym_uuid = symbol_uuids.setdefault(ref, str(uuid.uuid4()))
        x, y = _snap(xy[0]), _snap(xy[1])
        flags = {n[0]: n[1] for n in embedded[lib_id] if isinstance(n, list) and n and n[0] in ("in_bom", "on_board")}
        node: list = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, 0], ["unit", 1], ["exclude_from_sim", "no"],
                      ["in_bom", "no" if power else flags.get("in_bom", "yes")],
                      ["on_board", "no" if power else flags.get("on_board", "yes")],
                      ["dnp", "no"], ["uuid", Q(sym_uuid)],
                      *_name_fields(ref, value, x, y, pins_of[lib_id], power),
                      ["property", Q("Footprint"), Q(footprint), ["at", x, y, 0], _effects(hide=True)],
                      ["property", Q("Datasheet"), Q(fields.get("Datasheet", "")), ["at", x, y, 0], _effects(hide=True)]]
        for key, val in fields.items():
            if key != "Datasheet":
                node.append(["property", Q(key), Q(val), ["at", x, y, 0], _effects(hide=True)])
        for pin in pins_of[lib_id]:
            node.append(["pin", Q(pin.number), ["uuid", _uid()]])
        node.append(["instances", ["project", Q(design.name), ["path", Q("/" + root), ["reference", Q(ref)], ["unit", 1]]]])
        body.append(node)

    for part in design.parts:
        if part.board_only:
            continue
        place(part.ref, part.lib_id, part.value, part.sch_xy, part.footprint, part.fields)
        for pin in pins_of[part.lib_id]:
            end = f"{part.ref}.{pin.number}"
            px, py = _pin_point(part.sch_xy, pin)
            if end in design.unused:
                body.append(["no_connect", ["at", px, py], ["uuid", _uid()]])
                continue
            net = net_of.get(end)
            if net is None:
                continue
            dx, dy, label_angle = _outward(pin)
            sx, sy = _snap(px + dx * STUB), _snap(py + dy * STUB)
            for point in ((px, py), (sx, sy)):
                if endpoints.get(point, net) != net:
                    raise ValueError(f"{end} ({net}) lands on {point}, already used by net {endpoints[point]}")
                endpoints[point] = net
            body.append(["wire", ["pts", ["xy", px, py], ["xy", sx, sy]], ["stroke", ["width", 0], ["type", "default"]], ["uuid", _uid()]])
            justify = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[label_angle]
            body.append(["label", Q(net), ["at", sx, sy, label_angle], ["fields_autoplaced", "yes"],
                         _effects(justify=justify), ["uuid", _uid()]])

    # One PWR_FLAG per off-sheet-fed net, beside the first endpoint of that net, on its own labelled stub.
    flag_pin = pins_of.get("power:PWR_FLAG", [None])[0]
    for n, net in enumerate(design.power_flag_nets, start=1):
        first = design.nets[net][0]
        ref, _, pin_no = first.partition(".")
        part = design.part(ref)
        pin = next(p for p in pins_of[part.lib_id] if p.number == pin_no)
        px, py = _pin_point(part.sch_xy, pin)
        dx, dy, _ = _outward(pin)
        fx, fy = _snap(px + dx * STUB * 2 + (0 if dx else 2 * STUB)), _snap(py + dy * STUB * 2 + (0 if dy else -2 * STUB))
        place(f"#FLG{n:02d}", "power:PWR_FLAG", "PWR_FLAG", (fx, fy), "", {}, power=True)
        lx, ly = _pin_point((fx, fy), flag_pin)
        sx, sy = lx, _snap(ly + STUB)
        body.append(["wire", ["pts", ["xy", lx, ly], ["xy", sx, sy]], ["stroke", ["width", 0], ["type", "default"]], ["uuid", _uid()]])
        body.append(["label", Q(net), ["at", sx, sy, 0], ["fields_autoplaced", "yes"], _effects(justify="left bottom"), ["uuid", _uid()]])

    doc: list = ["kicad_sch", ["version", 20250114], ["generator", Q("hardware_splicer")], ["generator_version", Q("9.0")],
                 ["uuid", Q(root)], ["paper", Q(design.paper)],
                 ["title_block", ["title", Q(design.title)], ["rev", Q(design.revision)], ["company", Q("Hardware-Splicer")]],
                 ["lib_symbols", *embedded.values()], *body,
                 ["sheet_instances", ["path", Q("/"), ["page", Q("1")]]], ["embedded_fonts", "no"]]
    path.write_text(dump_sexpr(doc) + "\n", encoding="utf-8")
    return symbol_uuids


def _name_fields(ref: str, value: str, x: float, y: float, pins: Sequence[Pin], hide: bool) -> list[list]:
    """Reference and value beside a symbol whose pins all leave top or bottom (passives), else above and below it,
    clear of the pin stubs and their labels."""
    if pins and all(int(round(p.angle)) % 180 == 90 for p in pins):
        dx = max(abs(p.x) for p in pins) + 2.54
        return [["property", Q("Reference"), Q(ref), ["at", _snap(x + dx), _snap(y - 1.27), 0], _effects(hide=hide, justify="left")],
                ["property", Q("Value"), Q(value), ["at", _snap(x + dx), _snap(y + 1.27), 0], _effects(hide=hide, justify="left")]]
    top = max([p.y for p in pins if int(round(p.angle)) % 360 == 270] + [p.y for p in pins] + [0.0])
    bottom = min([p.y for p in pins] + [0.0])
    up = top + (STUB + 3.81 if any(int(round(p.angle)) % 360 == 270 for p in pins) else 2.54)
    down = -bottom + (STUB + 3.81 if any(int(round(p.angle)) % 360 == 90 for p in pins) else 2.54)
    return [["property", Q("Reference"), Q(ref), ["at", x, _snap(y - up), 0], _effects(hide=hide)],
            ["property", Q("Value"), Q(value), ["at", x, _snap(y + down), 0], _effects(hide=hide)]]


# ---------------------------------------------------------------- KiCad read-back


def kicad_cli() -> str:
    path = shutil.which("kicad-cli")
    if not path:
        raise RuntimeError("kicad-cli is not on PATH")
    return path


def schematic_netlist(sch: Path) -> dict[str, Any]:
    """KiCad's own netlist of the schematic: components (ref -> symbol UUID, footprint) and nets (name -> endpoints)."""
    with tempfile.TemporaryDirectory(prefix="hs-net-") as tmp:
        out = Path(tmp) / "net.net"
        subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)],
                       check=True, capture_output=True, text=True, timeout=120)
        tree = parse_sexpr(out.read_text(encoding="utf-8"))
    comps = {}
    for comp in _children(_child(tree, "components"), "comp"):
        ref = str(_child(comp, "ref")[1])
        tstamps = _child(comp, "tstamps")
        fp = _child(comp, "footprint")
        comps[ref] = {"uuid": str(tstamps[1]) if tstamps else "", "footprint": str(fp[1]) if fp else "",
                      "value": str(_child(comp, "value")[1])}
    nets = {}
    for net in _children(_child(tree, "nets"), "net"):
        name = str(_child(net, "name")[1])
        nodes = sorted(f"{_child(n, 'ref')[1]}.{_child(n, 'pin')[1]}" for n in _children(net, "node"))
        nets[name] = nodes
    return {"components": comps, "nets": nets}


def _plain(name: str) -> str:
    return name[1:] if name.startswith("/") else name


def netlist_parity(design: Design, readback: Mapping[str, Any]) -> dict[str, Any]:
    """Net-by-net comparison of the design with KiCad's read-back (PWR_FLAG endpoints ignored)."""
    got = {}
    for name, ends in readback["nets"].items():
        ends = [e for e in ends if not e.startswith("#")]
        if ends:
            got[_plain(name)] = sorted(ends)
    want = {name: sorted(ends) for name, ends in design.nets.items()}
    unconnected = sorted(name for name in got if name.startswith("unconnected-"))
    stray = {n: e for n, e in got.items() if n not in want and not n.startswith("unconnected-")}
    mismatched = {n: {"design": want[n], "schematic": got.get(n)} for n in want if got.get(n) != want[n]}
    declared_unused = set(design.unused)
    unconnected_not_declared = [n for n in unconnected if not set(got[n]) <= declared_unused]
    return {"pass": not (stray or mismatched or unconnected_not_declared), "nets_compared": len(want),
            "mismatched": mismatched, "extra_nets": stray, "unconnected_pins_not_declared": unconnected_not_declared}


def run_erc(sch: Path, out_dir: Path) -> dict[str, Any]:
    import json

    report = out_dir / "erc.json"
    subprocess.run([kicad_cli(), "sch", "erc", "--format", "json", "--severity-all", "-o", str(report), str(sch)],
                   capture_output=True, text=True, timeout=180)
    data = json.loads(report.read_text())
    items = [v for sheet in data.get("sheets", []) for v in sheet.get("violations", [])]
    errors = [v for v in items if v.get("severity") == "error"]
    warnings = [v for v in items if v.get("severity") == "warning"]
    return {"errors": len(errors), "warnings": len(warnings),
            "violations": [{"type": v.get("type"), "severity": v.get("severity"), "description": v.get("description")} for v in items],
            "report": report.name, "kicad_version": data.get("kicad_version")}


def run_drc(pcb: Path, out_dir: Path) -> dict[str, Any]:
    import json

    report = out_dir / "drc.json"
    subprocess.run([kicad_cli(), "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", str(report), str(pcb)],
                   capture_output=True, text=True, timeout=300)
    data = json.loads(report.read_text())
    groups = {"violations": data.get("violations", []), "unconnected_items": data.get("unconnected_items", []),
              "schematic_parity": data.get("schematic_parity", [])}
    out: dict[str, Any] = {"report": report.name, "kicad_version": data.get("kicad_version")}
    for key, items in groups.items():
        out[key] = {"errors": sum(1 for v in items if v.get("severity") == "error"),
                    "warnings": sum(1 for v in items if v.get("severity") == "warning"),
                    "items": [{"type": v.get("type"), "severity": v.get("severity"), "description": v.get("description"),
                               "where": [i.get("description") for i in v.get("items", [])][:3]} for v in items]}
    return out


# ---------------------------------------------------------------- PCB hand-off


def pcb_spec(design: Design, readback: Mapping[str, Any], *, outline_mm: Sequence[float], rules: Mapping[str, float],
             netclasses: Sequence[Mapping[str, Any]] = (), route_now: Iterable[str] | None = None,
             tracks: Sequence[Mapping[str, Any]] = (), keepouts: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Everything the pcbnew helper needs. Pad nets come from KiCad's netlist of the schematic, not from the design, so
    the board is built from what the schematic says. ``route_now`` limits which nets the helper assigns (the rest are
    assigned later, before zones are poured)."""
    pad_net: dict[str, dict[str, str]] = {}
    for name, ends in readback["nets"].items():
        for end in ends:
            ref, _, pin = end.partition(".")
            if not ref.startswith("#"):
                pad_net.setdefault(ref, {})[pin] = name
    allowed = None if route_now is None else set(route_now)
    parts = []
    for part in design.parts:
        if part.pcb_xy is None:
            continue
        comp = readback["components"].get(part.ref, {})
        nets = {pin: net for pin, net in pad_net.get(part.ref, {}).items() if allowed is None or _plain(net) in allowed}
        parts.append({"ref": part.ref, "value": part.value, "footprint": part.footprint, "x": part.pcb_xy[0], "y": part.pcb_xy[1],
                      "rot": part.pcb_rot, "side": part.pcb_side, "uuid": comp.get("uuid", ""), "nets": nets,
                      "board_only": part.board_only})
    return {"outline_mm": list(outline_mm), "rules": dict(rules), "netclasses": list(netclasses), "parts": parts,
            "tracks": list(tracks), "keepouts": list(keepouts), "footprint_dir": str(footprint_dir())}
