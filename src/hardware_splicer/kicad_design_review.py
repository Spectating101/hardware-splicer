"""Review any KiCad schematic from KiCad's own netlist, not only boards HS laid out itself.

KiCad's netlist export (``kicad-cli sch export netlist --format kicadsexpr``) gives every node its pin function name
("U0TXD/GPIO43", "CC1", "D") and electrical type (input, output, bidirectional, power_in, passive...), and every component
its value and library symbol. That is enough to check a board drawn by anyone. The checks here target the bug classes
that KiCad's ERC and other checkers missed on real fix commits (examples/schematic_bug_benchmark):

* ``uart_tx_to_tx`` / ``uart_rx_to_rx``: one net joins the transmit pins (or the receive pins) of two different parts;
* ``power_pin_unconnected``: a power-input pin with nothing else on its net (not a connector pin whose same-named twin is wired);
* ``i2c_no_pullup``: an I2C data or clock net with no resistor to a supply;
* ``mosfet_source_drain``: a MOSFET whose drain, not its source, sits on the rail its type expects at the source, unless it is
  half of a common-source pair or a P-channel load-sharing switch with its gate on a supply;
* ``usb_c_cc_no_pulldown``: a USB-C receptacle's CC pin with no resistor to ground, unless it has Rp to a supply (a source port);
  a CC pin that reaches a controller or module is reported as a note.

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
# A rail by name: +5V, VCC_IO, 3V3, VBAT; also 3.3V and 1.8V written with a point, and an embedded 3V3 or 1V8 (D+3V3, P3V3).
SUPPLY = re.compile(r"^\+|(^|[/_])(\d+V\d*\w*|V(CC|DD|IN|BUS|BAT|SYS)\w*|3V3\w*|1V8\w*|VBATT?\w*)$|(^|[^A-Za-z0-9.])\d+\.\d+V\w*$|\dV\d+\w*$", re.I)
TX = re.compile(r"(^|[/_])(U\d?TXD?\d?|TXD?\d?|UART\d?_TX)($|[/_])", re.I)
RX = re.compile(r"(^|[/_])(U\d?RXD?\d?|RXD?\d?|UART\d?_RX)($|[/_])", re.I)
TRANSCEIVER = re.compile(r"transceiver|\bCAN\b|RS-?485|RS-?422|\bLIN\b|ISO10[45]\d|TJA1\d|SN65HVD|MCP25\d\d|MAX3?48\d|ADM\d{4}|THVD", re.I)
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


def _is_connector(comp: dict[str, Any]) -> bool:
    return bool(re.search(r"connector|header|receptacle|socket", f"{comp.get('lib', '')} {comp.get('part', '')}", re.I))


# Common linear-regulator families, for imported designs whose pins carry no power-output type.
LDO = re.compile(r"(TLV7\d|AMS1117|AP2112|AP7\d{3}|XC62\d|MCP17\d|RT90\d|ME62\d|LM1117|LD1117|LDL\d|SPX\d|NCP1\d{2}|HT7\d|LP29\d|LP59\d|TPS7\d|MIC5\d)", re.I)
RESISTANCE = re.compile(r"^\d+(\.\d+)?\s*[RkKM]?\d*\s*(Ω|ohms?)?$", re.I)


def _kind(comp: dict[str, Any], ref: str = "") -> str:
    text = f"{comp['lib']}:{comp['part']} {comp['description']}".lower()
    if re.search(r"pmos|p-?ch|q_p\w*mos|pfet", text):
        return "pmos"
    if re.search(r"nmos|n-?ch|q_n\w*mos|nfet", text):
        return "nmos"
    if re.search(r"usb_?c|type-?c", text):
        return "usb_c"
    # A receptacle named only by its maker's part number (CUI UJ20-C, GCT USB4105): a connector designator with CC1 and CC2 pins.
    # A PD controller IC has CC pins too, so only connector designators count.
    if re.fullmatch(r"(J|P|CN|CON|USB|X)\d+", ref) and {"CC1", "CC2"} <= {str(p.get("name", "")).upper() for p in comp.get("pins", [])}:
        return "usb_c"
    # Imported designs (EasyEDA, Altium) carry a manufacturer part number instead of Device:R: judge those by designator and value.
    by_value = bool(re.fullmatch(r"R\d+", ref)) and bool(RESISTANCE.match(str(comp.get("value", "")).strip()))
    if re.search(r"(^|[:_ ])r($|[_ ])|resistor|r_small|r_us", text) or comp["part"] in ("R", "R_Small", "R_US") or by_value:
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

    wired = {n["ref"] for ns in nets.values() for n in ns}
    unannotated = sorted(r for r in comps if "?" in r and r in wired)  # a drawing-sheet symbol is on no net
    skipped: list[str] = []

    def finding(severity: str, rule: str, message: str, basis: str, refs: list[str], net: str | None = None) -> None:
        # An unannotated designator ("R?") names several parts at once, so nothing traced through one can be trusted.
        if any("?" in r for r in refs) or (net and any("?" in n["ref"] for n in nets.get(net, []))):
            skipped.append(rule)
            return
        findings.append({"severity": severity, "rule": rule, "message": message, "basis": basis, "components": sorted(set(refs)),
                         **({"net": net} if net else {})})

    def driven_supply(net_name: str) -> bool:
        """A net a power-output pin or a linear regulator's output drives, whatever it is called (Argo's VREF)."""
        for n in nets.get(net_name, []):
            comp = comps.get(n["ref"], {})
            if n["type"] == "power_out":
                return True
            if re.fullmatch(r"V?OUT\d*(_\d+)?|VO", n["function"], re.I) and (
                    re.search(r"regulator|ldo", f"{comp.get('lib', '')} {comp.get('description', '')}", re.I) or LDO.match(str(comp.get("value", "")))):
                return True
        return False

    def resistor_to(net_name: str, pattern: re.Pattern) -> bool:
        for n in nets.get(net_name, []):
            if _kind(comps.get(n["ref"], {"lib": "", "part": "", "description": ""}), n["ref"]) != "resistor":
                continue
            other = [pin_net.get((n["ref"], p)) for p in ("1", "2") if p != n["pin"]]
            # A solder jumper or net tie may sit between the resistor and the rail (AQEYE's I2C_PUE pull-up enable).
            other += [far for o in other if o for far in beyond_jumper(o)]
            if any(o and (pattern.search(o) or (pattern is SUPPLY and driven_supply(o))) for o in other):
                return True
        return False

    def beyond_jumper(net_name: str) -> list[str]:
        nets_beyond = []
        for n in nets.get(net_name, []):
            comp = comps.get(n["ref"], {})
            if re.match(r"(JP|SJ|NT)\d", n["ref"]) or re.search(r"jumper|net_?tie", f"{comp.get('lib', '')} {comp.get('part', '')}", re.I):
                nets_beyond += [net for (r, q), net in pin_net.items() if r == n["ref"] and q != n["pin"]]
        return nets_beyond

    for name, nodes in nets.items():
        parts = [n for n in nodes if n["type"] != "passive" and not n["function"].lower().startswith("pin_")]
        # A bus transceiver's RXD is an output to the MCU, and boards often carry two alternative transceivers on one footprint pair.
        uart_parts = [n for n in parts if not TRANSCEIVER.search(" ".join(str(v) for k, v in comps.get(n["ref"], {}).items() if k != "pins"))]
        txs = [n for n in uart_parts if TX.search(n["function"]) and not RX.search(n["function"])]
        rxs = [n for n in uart_parts if RX.search(n["function"]) and not TX.search(n["function"])]
        for label, group, rule in (("transmit", txs, "uart_tx_to_tx"), ("receive", rxs, "uart_rx_to_rx")):
            if len({n["ref"] for n in group}) >= 2:
                finding("error", rule, f"Net {name} joins the UART {label} pins of {', '.join(sorted({n['ref'] + '.' + n['function'] for n in group}))}. "
                        f"A UART links one part's TX to the other's RX.", "UART convention (TX to RX); pin functions from KiCad's symbols", [n["ref"] for n in group], name)
        module = comps.get(nodes[0]["ref"], {}) if nodes else {}
        # A module (a Pico, a DevKit, a breakout) exposes optional supply pins that may stay open: VBUS, VSYS, 3V3 out.
        is_module = bool(re.search(r"module|pico|devkit|board|breakout", f"{module.get('lib', '')} {module.get('part', '')}", re.I))
        n = nodes[0] if nodes else None
        # A connector repeats supply pins (a Raspberry Pi header has two 3V3 pins); one wired twin is enough.
        twin_wired = n is not None and _is_connector(comps.get(n["ref"], {})) and any(
            r == n["ref"] and q != n["pin"] and len(nets[net]) > 1 and any(x["ref"] == r and x["pin"] == q and x["function"] == n["function"] for x in nets[net])
            for (r, q), net in pin_net.items())
        if len(nodes) == 1 and n["type"] == "power_in" and not is_module and not twin_wired:
            finding("error", "power_pin_unconnected", f"{n['ref']} pin {n['pin']} ({n['function'] or 'power input'}) is a power input with nothing else on its net.",
                    "KiCad pin type power_in", [n["ref"]], name)
        sda = sorted({n["ref"] + "." + n["function"] for n in parts if re.search(r"(^|[/_])SDA", n["function"], re.I) and not re.search(r"SCL", n["function"], re.I)})
        scl = sorted({n["ref"] + "." + n["function"] for n in parts if re.search(r"(^|[/_])SCL", n["function"], re.I) and not re.search(r"SDA", n["function"], re.I)})
        if sda and scl:
            finding("error", "i2c_sda_scl_short", f"Net {name} joins I2C data ({', '.join(sda)}) and clock ({', '.join(scl)}). SDA and SCL must be separate nets.",
                    UM10204, [x.split(".")[0] for x in sda + scl], name)
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
        kind = _kind(comp, ref)
        if kind in ("pmos", "nmos"):
            pins = {}
            for (r, p), net in pin_net.items():
                if r == ref:
                    fn = next((n["function"] for n in nets[net] if n["ref"] == ref and n["pin"] == p), "")
                    if fn.upper() in ("D", "S", "G", "DRAIN", "SOURCE", "GATE"):
                        pins[fn.upper()[:1]] = net
            d, s, g = pins.get("D"), pins.get("S"), pins.get("G")
            if d and s:
                rail = SUPPLY if kind == "pmos" else GROUND
                # Two deliberate circuits put the drain on the rail: a common-source pair (reverse blocking or ORing: another
                # FET's source shares this source net) and a load-sharing power path (the gate sits on a supply such as VBUS).
                paired = any(n["ref"] != ref and n["function"].upper() in ("S", "SOURCE") for n in nets.get(s, []))
                power_path = kind == "pmos" and g is not None and SUPPLY.search(g)
                # Reverse-polarity protection runs the body diode on purpose: a P-channel with its gate held at ground, or an
                # N-channel in the return with its gate held at a supply (rs485-moist-sensor's Q1).
                held = {"pmos": GROUND, "nmos": SUPPLY}[kind]
                polarity_guard = g is not None and (held.search(g) or resistor_to(g, held))
                if rail.search(d) and not rail.search(s) and not paired and not power_path and not polarity_guard:
                    where = "supply" if kind == "pmos" else "ground"
                    finding("warning", "mosfet_source_drain", f"{ref} ({comp['part']}) has its drain on the {where} net {d} and its source on {s}. "
                            f"A {'P' if kind == 'pmos' else 'N'}-channel switch normally has its source on the {where}; reversed, the body diode conducts and it cannot switch off.",
                            "MOSFET body-diode orientation (high-side P-channel, low-side N-channel); pin names from KiCad's symbol", [ref], d)
        if kind == "usb_c":
            # USB 2.0 data appears twice on a full receptacle (A6/B6 D+, A7/B7 D-); with one copy open, data works in one plug orientation only.
            for signal in ("D+", "D-"):
                copies = [q["num"] for q in comp.get("pins", []) if str(q.get("name", "")).upper() == signal]
                wired = [q for q in copies if len(nets.get(pin_net.get((ref, q), ""), [])) > 1]
                if len(copies) == 2 and len(wired) == 1:
                    open_pin = next(q for q in copies if q not in wired)
                    finding("warning", "usb_c_data_one_side", f"{ref} {signal} is wired on pin {wired[0]} but pin {open_pin} is open, so USB data works with the plug "
                            "one way round only. Join both copies.", "USB Type-C receptacle pinout (D+ on A6/B6, D- on A7/B7)", [ref], pin_net.get((ref, wired[0])))
            # Every CC pin the symbol has, wired or not: an unwired CC pin does not appear in any net.
            cc_pins = [(p["num"], p["name"]) for p in comp.get("pins", []) if re.fullmatch(r"CC\d", p["name"], re.I)]
            for p, fn in cc_pins:
                net = pin_net.get((ref, p))
                if net is not None and resistor_to(net, SUPPLY) and not resistor_to(net, GROUND):
                    continue  # Rp to a supply: a source (host) port, which needs no Rd
                # An IC or module on the CC net (by designator; its pins may be typed passive), never an ESD or TVS clamp.
                controller = sorted({x["ref"] for x in nets.get(net or "", []) if x["ref"] != ref and re.match(r"(U|IC|M|MOD|Module)\d", x["ref"])
                                     and not re.search(r"esd|tvs|usblc|prtr|clamp|protect", " ".join(str(v) for v in comps.get(x["ref"], {}).values()), re.I)})
                if controller:
                    finding("info", "usb_c_cc_no_pulldown", f"{ref} {fn} has no resistor to ground but goes to {', '.join(controller)}, which may terminate CC itself "
                            "(a PD or CC controller, or a module such as the CM5): check its datasheet.", "USB Type-C sink termination Rd = 5.1 kOhm", [ref, *controller], net)
                    continue
                if net is None or not resistor_to(net, GROUND):
                    finding("warning", "usb_c_cc_no_pulldown", f"{ref} {fn} {'is not connected' if net is None else 'has no resistor to ground'}. A USB-C sink needs Rd (5.1 kOhm) on each CC pin or a "
                            "source will not supply 5 V.", "USB Type-C specification, sink termination Rd = 5.1 kOhm (cited by section, not quoted here)", [ref], net)
    _mated_findings(comps, nets, pin_net, mates, finding)
    if unannotated:
        findings.append({"severity": "info", "rule": "unannotated", "components": unannotated,
                         "message": f"{len(unannotated)} designator(s) still end in '?' ({', '.join(unannotated[:5])}). Annotate the schematic and review again: "
                                    f"{len(skipped)} check(s) touching those parts were not reported.", "basis": "KiCad annotation; the netlist keys parts by designator"})
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("error", "warning", "info")}
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "components": len(comps), "nets": len(nets), "findings": findings, "counts": counts}


def review_schematic(path: Path, mates: dict[str, Any] | None = None) -> dict[str, Any]:
    if path.suffix == ".net":
        return review(parse_netlist(path.read_text(encoding="utf-8", errors="replace")), mates)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "board.net"
        from .model3d import resolve_kicad_cli

        cli = resolve_kicad_cli()
        if cli is None:
            raise KicadReviewError("kicad-cli not found: install KiCad or set HARDWARE_SPLICER_KICAD_CLI")
        run = subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(out), str(path)],
                             capture_output=True, text=True, timeout=300, check=False)
        if not out.exists():
            fmt = re.search(r"\(version (\d{8})\)", path.read_text(encoding="utf-8", errors="replace")[:400])
            newer = f" The schematic's file format is {fmt.group(1)}; a format from 2026 needs KiCad 10, which HARDWARE_SPLICER_KICAD_CLI can point to." if fmt and fmt.group(1) >= "20260101" else ""
            raise KicadReviewError(f"kicad-cli could not export a netlist: {run.stderr.strip()[:300]}.{newer}")
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
