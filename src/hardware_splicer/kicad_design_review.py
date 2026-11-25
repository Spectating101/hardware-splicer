"""Review any KiCad schematic from KiCad's own netlist, not only boards HS laid out itself.

KiCad's netlist export (``kicad-cli sch export netlist --format kicadsexpr``) gives every node its pin function name
("U0TXD/GPIO43", "CC1", "D") and electrical type (input, output, bidirectional, power_in, passive...), and every component
its value and library symbol. That is enough to check a board drawn by anyone. The checks here target the bug classes
that KiCad's ERC and other checkers missed on real fix commits (examples/schematic_bug_benchmark):

* ``uart_tx_to_tx`` / ``uart_rx_to_rx``: one net joins the transmit pins (or the receive pins) of two different parts;
* ``power_pin_unconnected``: a power-input pin with nothing else on its net;
* ``i2c_no_pullup``: an I2C data or clock net with no resistor to a supply;
* ``mosfet_source_drain``: a MOSFET whose drain, not its source, sits on the rail its type expects at the source;
* ``usb_c_cc_no_pulldown``: a USB-C receptacle's CC pin with no resistor to ground.

Each finding says what it rests on: KiCad's pin data plus a stated convention or standard. A finding is a reason to look,
never a verdict, and nothing here was measured. Net names are not trusted for direction: a net called RX may be named
from either end, so names never decide a finding on their own.

    PYTHONPATH=src python -m hardware_splicer.kicad_design_review board.kicad_sch   # or a .net file
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .netlist.import_kicad import _parse_sexpr, _tokenize_sexpr

SCHEMA = "hardware_splicer.kicad_design_review.v1"
BOUNDARY = "Static checks of KiCad netlist data against stated conventions. Not a simulation or a measurement; nothing is approved."
UM10204 = "NXP UM10204 I2C-bus specification: SDA and SCL are connected to a positive supply through pull-up resistors"
GROUND = re.compile(r"(^|[/_])(A|D|P|S)?GND\w*$|^/?(GND|VSS|0V)\w*$", re.I)
# KiCad power symbols name their nets with a leading + (+5V, +VSW, +BATT); other supply names are matched by pattern.
SUPPLY = re.compile(r"^\+|(^|[/_])(\d+V\d*\w*|V(CC|DD|IN|BUS|BAT|SYS)\w*|3V3\w*|1V8\w*|VBATT?\w*)$", re.I)
TX = re.compile(r"(^|[/_])(U\d?TXD?\d?|TXD?\d?|UART\d?_TX)($|[/_])", re.I)
RX = re.compile(r"(^|[/_])(U\d?RXD?\d?|RXD?\d?|UART\d?_RX)($|[/_])", re.I)
I2C = re.compile(r"(^|[/_])(I2C\d?_)?(SDA|SCL)\d?($|[/_])", re.I)


class KicadReviewError(ValueError):
    pass


def _child(node: list, name: str) -> list | None:
    return next((x for x in node if isinstance(x, list) and x and x[0] == name), None)


def _scalar(node: list, name: str) -> str | None:
    c = _child(node, name)
    return str(c[1]) if c and len(c) > 1 and not isinstance(c[1], list) else None


def parse_netlist(text: str) -> dict[str, Any]:
    tree, _ = _parse_sexpr(_tokenize_sexpr(text))
    if not isinstance(tree, list) or tree[:1] != ["export"]:
        raise KicadReviewError("not a KiCad sexpr netlist (expected (export ...))")
    comps: dict[str, dict[str, Any]] = {}
    for comp in (_child(tree, "components") or [])[1:]:
        if isinstance(comp, list) and comp[:1] == ["comp"]:
            src = _child(comp, "libsource") or []
            comps[_scalar(comp, "ref") or "?"] = {"value": _scalar(comp, "value") or "", "lib": _scalar(src, "lib") or "",
                                                 "part": _scalar(src, "part") or "", "description": _scalar(src, "description") or ""}
    libparts: dict[tuple[str, str], list[dict[str, str]]] = {}
    for lp in (_child(tree, "libparts") or [])[1:]:
        if isinstance(lp, list) and lp[:1] == ["libpart"]:
            pins = [{"num": _scalar(p, "num") or "", "name": _scalar(p, "name") or "", "type": _scalar(p, "type") or ""}
                    for p in (_child(lp, "pins") or [])[1:] if isinstance(p, list) and p[:1] == ["pin"]]
            libparts[(_scalar(lp, "lib") or "", _scalar(lp, "part") or "")] = pins
    for comp in comps.values():
        comp["pins"] = libparts.get((comp["lib"], comp["part"]), [])
    nets: dict[str, list[dict[str, str]]] = {}
    for net in (_child(tree, "nets") or [])[1:]:
        if not (isinstance(net, list) and net[:1] == ["net"]):
            continue
        nodes = []
        for node in net[1:]:
            if isinstance(node, list) and node[:1] == ["node"]:
                nodes.append({"ref": _scalar(node, "ref") or "", "pin": _scalar(node, "pin") or "",
                              "function": _scalar(node, "pinfunction") or "", "type": _scalar(node, "pintype") or ""})
        nets[_scalar(net, "name") or f"net{len(nets)}"] = nodes
    return {"components": comps, "nets": nets}


def _kind(comp: dict[str, Any]) -> str:
    text = f"{comp['lib']}:{comp['part']} {comp['description']}".lower()
    if re.search(r"pmos|p-?ch|q_p\w*mos|pfet", text):
        return "pmos"
    if re.search(r"nmos|n-?ch|q_n\w*mos|nfet", text):
        return "nmos"
    if re.search(r"usb_?c|type-?c", text):
        return "usb_c"
    if re.search(r"(^|[:_ ])r($|[_ ])|resistor|r_small|r_us", text) or comp["part"] in ("R", "R_Small", "R_US"):
        return "resistor"
    return "other"


REF_TX = re.compile(r"(^|[\s./_])((LP)?U(S)?ART\d*[._])?TXD?\d?($|\b)", re.I)
REF_RX = re.compile(r"(^|[\s./_])((LP)?U(S)?ART\d*[._])?RXD?\d?($|\b)", re.I)


def _volts(label: str) -> float | None:
    m = re.search(r"(\d+(?:[.V]\d+)?)\s*V", label.upper())
    if re.fullmatch(r"\+?3V3|3\.3V", label.strip(), re.I):
        return 3.3
    return float(m.group(1).replace("V", ".")) if m else None


def _align(local: dict[int, str], reference: list[dict[str, Any]]) -> tuple[int | None, int]:
    """The offset that lines a connector's pins up with a reference header, scored on ground, supply and debug pins."""
    best, best_score, tie = None, 0, False
    for offset in range(0, max(1, len(reference) - len(local) + 1) + 1):
        score = 0
        for k, net in local.items():
            ref = next((p for p in reference if p["position"] == k + offset), None)
            if ref is None:
                score -= 1
                continue
            label = ref["label"].upper()
            if GROUND.search(net) and label == "GND":
                score += 1
            elif SUPPLY.search(net) and _volts(label) is not None and _volts(label) == _volts(net.split("/")[-1].lstrip("+").replace("Ext_", "")):
                score += 1
            elif any(f.upper() in net.upper() for f in [label, *ref.get("functions", [])] if len(f) >= 4):
                score += 1
        if score > best_score:
            best, best_score, tie = offset, score, False
        elif score == best_score and score > 0:
            tie = True
    return (None if tie else best), best_score


def _mated_findings(comps, nets, pin_net, mates, finding) -> None:
    from .blackwire_bridge import snapshot as black_wire

    boards = black_wire()["boards"]
    for ref, mate in (mates or {}).items():
        board = boards.get(mate.get("board", ""))
        if board is None or ref not in comps:
            finding("info", "mate_unknown", f"{ref}: no Black Wire board {mate.get('board')!r}, so the mating check did not run.", "mates declaration", [ref])
            continue
        connector = next((c for c in board["connectors"] if c["name"] == mate.get("connector")), board["connectors"][0] if board["connectors"] else None)
        if connector is None:
            continue
        local = {int(p): net for (r, p), net in pin_net.items() if r == ref and p.isdigit()}
        offset, score = (int(mate["offset"]), -1) if "offset" in mate else _align(local, connector["pins"])
        source = f"Black Wire pinout of {mate['board']} / {connector['name']} ({board.get('review')}, CC-BY-4.0, (c) Valleytech Solutions)"
        if offset is None or (score != -1 and score < 2):
            finding("info", "mate_unaligned", f"{ref} could not be lined up with {mate['board']} {connector['name']}: give the pin offset in the mates declaration.", source, [ref])
            continue
        how = f"pin offset {offset}" + (f", inferred from {score} matching ground/supply/debug pins" if score >= 0 else ", as declared")
        for k, net in sorted(local.items()):
            pin = next((p for p in connector["pins"] if p["position"] == k + offset), None)
            if pin is None:
                continue
            roles = " ".join(pin.get("functions") or []) + " " + pin["label"]
            theirs = "TX" if REF_TX.search(roles) and not REF_RX.search(roles) else "RX" if REF_RX.search(roles) and not REF_TX.search(roles) else None
            for n in nets.get(net, []):
                if n["ref"] == ref or n["type"] == "passive":
                    continue
                ours = "TX" if TX.search(n["function"]) and not RX.search(n["function"]) else "RX" if RX.search(n["function"]) and not TX.search(n["function"]) else None
                if theirs and ours == theirs:
                    finding("error", f"uart_{ours.lower()}_to_{ours.lower()}_across_connector",
                            f"{ref} pin {k} is {mate['board']} pin {k + offset} ({pin['label']}: {theirs}), wired to {n['ref']}.{n['function']} ({ours}) on net {net}. "
                            "A UART links TX to RX.", f"{source}; {how}", [ref, n["ref"]], net)
            label = pin["label"].upper()
            if label == "GND" and SUPPLY.search(net):
                finding("error", "mate_ground_on_supply", f"{ref} pin {k} meets {mate['board']}'s GND but is on supply net {net}.", f"{source}; {how}", [ref], net)
            elif _volts(label) is not None and GROUND.search(net):
                finding("error", "mate_supply_on_ground", f"{ref} pin {k} meets {mate['board']}'s {pin['label']} but is on ground net {net}.", f"{source}; {how}", [ref], net)


def review(model: dict[str, Any], mates: dict[str, Any] | None = None) -> dict[str, Any]:
    comps, nets = model["components"], model["nets"]
    pin_net: dict[tuple[str, str], str] = {}
    for name, nodes in nets.items():
        for n in nodes:
            pin_net[(n["ref"], n["pin"])] = name
    findings: list[dict[str, Any]] = []

    def finding(severity: str, rule: str, message: str, basis: str, refs: list[str], net: str | None = None) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "basis": basis, "components": sorted(set(refs)),
                         **({"net": net} if net else {})})

    def resistor_to(net_name: str, pattern: re.Pattern) -> bool:
        for n in nets.get(net_name, []):
            if _kind(comps.get(n["ref"], {"lib": "", "part": "", "description": ""})) != "resistor":
                continue
            other = [pin_net.get((n["ref"], p)) for p in ("1", "2") if p != n["pin"]]
            if any(o and pattern.search(o) for o in other):
                return True
        return False

    for name, nodes in nets.items():
        parts = [n for n in nodes if n["type"] != "passive" and not n["function"].lower().startswith("pin_")]
        txs = [n for n in parts if TX.search(n["function"]) and not RX.search(n["function"])]
        rxs = [n for n in parts if RX.search(n["function"]) and not TX.search(n["function"])]
        for label, group, rule in (("transmit", txs, "uart_tx_to_tx"), ("receive", rxs, "uart_rx_to_rx")):
            if len({n["ref"] for n in group}) >= 2:
                finding("error", rule, f"Net {name} joins the UART {label} pins of {', '.join(sorted({n['ref'] + '.' + n['function'] for n in group}))}. "
                        f"A UART links one part's TX to the other's RX.", "UART convention (TX to RX); pin functions from KiCad's symbols", [n["ref"] for n in group], name)
        module = comps.get(nodes[0]["ref"], {}) if nodes else {}
        # A module (a Pico, a DevKit, a breakout) exposes optional supply pins that may stay open: VBUS, VSYS, 3V3 out.
        is_module = bool(re.search(r"module|pico|devkit|board|breakout", f"{module.get('lib', '')} {module.get('part', '')}", re.I))
        if len(nodes) == 1 and nodes[0]["type"] == "power_in" and not is_module:
            n = nodes[0]
            finding("error", "power_pin_unconnected", f"{n['ref']} pin {n['pin']} ({n['function'] or 'power input'}) is a power input with nothing else on its net.",
                    "KiCad pin type power_in", [n["ref"]], name)
        i2c_parts = {n["ref"] for n in parts if I2C.search(n["function"])}
        if len(i2c_parts) >= 2 and not resistor_to(name, SUPPLY):  # a bus needs two parts; one strap pin is not a bus
            # Any part on the net that is a module (judged by its part name, never its library's name), whatever its pin there is called.
            modules = sorted({n["ref"] for n in nodes if re.search(r"module|compute ?module|\bcm[345]\b|wroom|wrover|\bpico\b|devkit",
                                                                    f"{comps.get(n['ref'], {}).get('part', '')} {comps.get(n['ref'], {}).get('value', '')}", re.I)})
            listed = ", ".join(sorted(n["ref"] + "." + n["function"] for n in parts if I2C.search(n["function"])))
            if modules:
                finding("info", "i2c_no_pullup", f"Net {name} carries I2C ({listed}) with no resistor to a supply on this board. {', '.join(modules)} is a module, "
                        "which often carries its own pull-ups: check its datasheet.", UM10204, sorted(i2c_parts), name)
            else:
                finding("warning", "i2c_no_pullup", f"Net {name} carries I2C ({listed}) but no resistor on it reaches a supply net. Check the parts for built-in pull-ups.",
                        UM10204, sorted(i2c_parts), name)

    for ref, comp in comps.items():
        kind = _kind(comp)
        if kind in ("pmos", "nmos"):
            pins = {}
            for (r, p), net in pin_net.items():
                if r == ref:
                    fn = next((n["function"] for n in nets[net] if n["ref"] == ref and n["pin"] == p), "")
                    if fn.upper() in ("D", "S", "G", "DRAIN", "SOURCE", "GATE"):
                        pins[fn.upper()[:1]] = net
            d, s = pins.get("D"), pins.get("S")
            if d and s:
                rail = SUPPLY if kind == "pmos" else GROUND
                if rail.search(d) and not rail.search(s):
                    where = "supply" if kind == "pmos" else "ground"
                    finding("warning", "mosfet_source_drain", f"{ref} ({comp['part']}) has its drain on the {where} net {d} and its source on {s}. "
                            f"A {'P' if kind == 'pmos' else 'N'}-channel switch normally has its source on the {where}; reversed, the body diode conducts and it cannot switch off.",
                            "MOSFET body-diode orientation (high-side P-channel, low-side N-channel); pin names from KiCad's symbol", [ref], d)
        if kind == "usb_c":
            # Every CC pin the symbol has, wired or not: an unwired CC pin does not appear in any net.
            cc_pins = [(p["num"], p["name"]) for p in comp.get("pins", []) if re.fullmatch(r"CC\d", p["name"], re.I)]
            for p, fn in cc_pins:
                net = pin_net.get((ref, p))
                if net is None or not resistor_to(net, GROUND):
                    finding("warning", "usb_c_cc_no_pulldown", f"{ref} {fn} {'is not connected' if net is None else 'has no resistor to ground'}. A USB-C sink needs Rd (5.1 kOhm) on each CC pin or a "
                            "source will not supply 5 V.", "USB Type-C specification, sink termination Rd = 5.1 kOhm (cited by section, not quoted here)", [ref], net)
    _mated_findings(comps, nets, pin_net, mates, finding)
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("error", "warning", "info")}
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "components": len(comps), "nets": len(nets), "findings": findings, "counts": counts}


def review_schematic(path: Path, mates: dict[str, Any] | None = None) -> dict[str, Any]:
    if path.suffix == ".net":
        return review(parse_netlist(path.read_text(encoding="utf-8", errors="replace")), mates)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "board.net"
        run = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(out), str(path)],
                             capture_output=True, text=True, timeout=300, check=False)
        if not out.exists():
            raise KicadReviewError(f"kicad-cli could not export a netlist: {run.stderr.strip()[:300]}")
        return review(parse_netlist(out.read_text(encoding="utf-8", errors="replace")), mates)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    mates = None
    if "--mates" in args:
        i = args.index("--mates")
        mates = json.loads(Path(args[i + 1]).read_text(encoding="utf-8"))
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        print(json.dumps(review_schematic(Path(args[0]), mates), indent=2))
    except (KicadReviewError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
