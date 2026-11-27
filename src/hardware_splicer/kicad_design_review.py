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
* ``input_pin_floating``: a fixed-function input pin (not a GPIO) with nothing on it and no no-connect mark;
* ``i2c_sda_scl_short``: SDA and SCL pins on one net;
* ``usb_c_data_one_side``: a USB-C receptacle's D+ or D- wired on one row only;
* ``usb_c_cc_no_pulldown``: a USB-C receptacle's CC pin with no resistor to ground, unless it has Rp to a supply (a source port);
  a CC pin that reaches a controller or module is reported as a note;
* ``esp32_enable_floating``: an ESP32 chip or module whose CHIP_PU/EN pin has no pull-up, no supply and no push-pull driver
  (Espressif: "CHIP_PU must not be left floating");
* ``z80_wired_or_no_pullup``: a Z80's INT or BUSREQ with no pull-up and no push-pull driver (Zilog UM0080: each "is normally
  wired-OR and requires an external pull-up");
* ``mdio_no_pullup``: an Ethernet PHY's MDIO net with no resistor to a supply, following series 0 ohm links (TI DP83848C:
  "The MDIO pin requires a pullup resistor (1.5 kΩ)");
* ``diode_forward_across_rails`` / ``led_reversed``: a diode forward-biased between two rails (anode above cathode, voltages read from
  the net names), or an LED that can never be forward-biased (anode on ground, or cathode on a supply, in a board with no negative rail);
* ``bjt_collector_emitter_reversed``: an NPN with its collector on ground, or a PNP with its collector on a supply;
* ``ground_pin_on_supply`` / ``supply_pin_on_ground``: a pin named GND on a supply rail, or one named VCC/VDD/VIN on ground;
* ``joined_pins_split``: two pins with one signal name (an ESD array's I/O1, a receptacle's D+) on two different nets;
* ``net_name_pin_mismatch``: a net named SDA, MOSI or HSYNC that meets an SCL, MISO or VSYNC pin;
* ``supply_rails_inverted``: a part's V+ (VCC, VDD) on a lower rail than its V- (VEE, VSS, GND);
* ``pinout_differs_from_kicad_library``: a part whose value or part number is a symbol in KiCad's own library, drawn with another
  symbol that numbers its pins differently.

Each finding says what it rests on: KiCad's pin data plus a stated convention or standard. A finding is a reason to look,
never a verdict, and nothing here was measured. Net names are not trusted for direction: a net called RX may be named
from either end, so names never decide a direction. A name may still say which signal a net is (SDA is not SCL, at either
end), and a rail's name gives its voltage for the diode and supply-pin checks.

    PYTHONPATH=src python -m hardware_splicer.kicad_design_review board.kicad_sch   # or a .net file
    PYTHONPATH=src python -m hardware_splicer.kicad_design_review board.kicad_sch --also   # with KiCad ERC and kicad-happy
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
            # Fields carry part numbers (LCSC, MPN, distributor codes); KiCad 9 writes them both as (fields) and (property).
            fields = {_scalar(f, "name") or "": (f[2] if len(f) > 2 and isinstance(f[2], str) else "")
                      for f in (_child(comp, "fields") or [])[1:] if isinstance(f, list) and f[:1] == ["field"]}
            for prop in comp[1:]:
                if isinstance(prop, list) and prop[:1] == ["property"] and _scalar(prop, "name"):
                    fields.setdefault(_scalar(prop, "name"), _scalar(prop, "value") or "")
            comps[_scalar(comp, "ref") or "?"] = {"value": _scalar(comp, "value") or "", "lib": _scalar(src, "lib") or "",
                                                 "part": _scalar(src, "part") or "", "description": _scalar(src, "description") or "",
                                                 "footprint": _scalar(comp, "footprint") or "", "fields": {k: v for k, v in fields.items() if k}}
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
    if re.search(r"pmos|\bp-?ch(annel)?\b|q_p\w*mos|pfet", text):
        return "pmos"
    if re.search(r"nmos|\bn-?ch(annel)?\b|q_n\w*mos|nfet", text):
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


# Pins that a datasheet or standard says must be pulled, each with its source quoted.
ESP32_PART = re.compile(r"ESP32", re.I)
DEV_BOARD = re.compile(r"devkit|dev ?board|\bboard\b|breakout|feather|xiao|nodemcu", re.I)
ESP32_EN = re.compile(r"^(CHIP_PU|CHIP_EN|EN)$", re.I)
ESPRESSIF_EN = ("Espressif hardware design guidelines, schematic checklist, Chip Power-up and Reset Timing: \"CHIP_PU must not be "
                "left floating.\" (ESP32 and ESP32-S3 pages)")
Z80_PART = re.compile(r"\bZ80|Z84C|Z8400", re.I)
Z80_WIRED_OR = re.compile(r"^[~/]?\{?(INT|BUSREQ|BUSRQ)\}?$", re.I)
ZILOG_UM0080 = ("Zilog Z80 CPU User Manual UM0080, pin descriptions: INT and BUSREQ are each \"normally wired-OR and requires an "
                "external pull-up\"")
MDIO_PIN = re.compile(r"(^|[/_])MDIO\d?($|[/_])", re.I)
CARRIER = re.compile(r"module|\bsom\b|carrier|osm|\bcm[345]\b", re.I)
TI_MDIO = ("TI DP83848C datasheet, MII serial management: \"The MDIO pin requires a pullup resistor (1.5 kΩ) which, during IDLE "
           "and turnaround, will pull MDIO high.\" (DP83867 and DP83822 state 2.2 kΩ); IEEE 802.3 clause 22")
ZERO_OHM = re.compile(r"^(0|0R|0R0|R_0R\w*|0 ?(Ω|ohm))$", re.I)


def _pull_rule_findings(comps, nets, pin_net, finding, resistor_to, driven_supply) -> None:
    def text(ref: str) -> str:
        c = comps.get(ref, {})
        return f"{c.get('value', '')} {c.get('part', '')} {c.get('lib', '')}"

    def node(ref: str, pin: str, net: str) -> dict[str, str]:
        return next((n for n in nets.get(net, []) if n["ref"] == ref and n["pin"] == pin), {"function": "", "type": ""})

    def held(net: str, ref: str) -> bool:
        """Pulled or driven: the net is a supply, reaches one through a resistor, or another part drives it push-pull."""
        if SUPPLY.search(net) or driven_supply(net) or resistor_to(net, SUPPLY):
            return True
        return any(n["ref"] != ref and n["type"] in ("output", "power_out") for n in nets.get(net, []))

    for (ref, pin), net in pin_net.items():
        fn = node(ref, pin, net)["function"]
        if not fn:
            continue
        if ESP32_EN.match(fn) and ESP32_PART.search(text(ref)) and not DEV_BOARD.search(text(ref)) and not held(net, ref):
            finding("warning", "esp32_enable_floating", f"{ref} {fn} (net {net}) has no pull-up, no supply and no push-pull driver, so the "
                    "chip enable floats when nothing is plugged in. Fit a pull-up to 3.3 V (Espressif suggests an RC delay, 10 kOhm and 1 uF).",
                    ESPRESSIF_EN, [ref], net)
        if Z80_WIRED_OR.match(fn) and Z80_PART.search(text(ref)) and not held(net, ref):
            finding("warning", "z80_wired_or_no_pullup", f"{ref} {fn} (net {net}) has no pull-up and no push-pull driver. The Z80 has no "
                    "internal pull-up on it, so open-collector sources leave it floating.", ZILOG_UM0080, [ref], net)
        trigger = MDIO_PIN.search(fn) and "no_connect" not in node(ref, pin, net)["type"] and node(ref, pin, net)["type"] != "passive"
        # A connector or a module's edge pin is where the bus leaves, not a PHY or MAC that needs the pull-up here.
        if trigger and not _is_connector(comps.get(ref, {})) and not CARRIER.search(text(ref)):
            # Follow series 0 ohm links (option resistors) to the nets they join.
            group, todo = {net}, [net]
            while todo:
                current = todo.pop()
                for n in nets.get(current, []):
                    if ZERO_OHM.match(str(comps.get(n["ref"], {}).get("value", ""))):
                        for (r, q), far in pin_net.items():
                            if r == n["ref"] and far not in group:
                                group.add(far)
                                todo.append(far)
            if any(resistor_to(g, SUPPLY) for g in group):
                continue
            members = {n["ref"] for g in group for n in nets.get(g, [])}
            off_board = [r for r in members if r != ref and (_is_connector(comps.get(r, {})) or CARRIER.search(text(r)))]
            finding("info" if off_board else "warning", "mdio_no_pullup",
                    f"{ref} {fn} (net {net}) has no resistor to a supply" + (f"; it reaches {', '.join(sorted(off_board))}, which may carry the pull-up"
                    if off_board else "") + ". MDIO is open-drain and needs a pull-up (1.5 kOhm to 2.2 kOhm) to idle high.",
                    TI_MDIO, [ref], net)


# Rules from the parts' physics and pin names, each a reason to look, not a verdict.
GROUND_PIN = re.compile(r"^(GND|AGND|DGND|PGND|SGND|GNDA|GNDD|GND_?\d+|EP_?GND)$", re.I)
SUPPLY_PIN = re.compile(r"^(VCC|VDD|VIN|V\+|VS|AVDD|DVDD|VDDA|VDDIO|VCCIO|VCCA|VCCB|PVIN|VREG_IN|IOVDD)\d*$", re.I)
RAIL_PAIRS = (("V+", "V-"), ("VCC", "VEE"), ("+VS", "-VS"), ("VS+", "VS-"), ("VDD", "VSS"))  # GND pins have their own rules
NAME_PAIRS = (("SDA", "SCL"), ("MOSI", "MISO"), ("COPI", "CIPO"), ("HSYNC", "VSYNC"))
NC_NAME = re.compile(r"^(NC|DNC|N\.?C\.?|RSV\w*|RESERVED\w*|SHIELD\w*|SH\d*|MP\d*|MH\d*|EP|PAD\d*|TAB|~)$", re.I)
JOINED_NAME = re.compile(r"^(D[+-]|DP|DN)$|[A-Z].*\d|\d.*[A-Z]", re.I)


MAIN_GROUND = re.compile(r"^(GND|AGND|DGND|PGND|GNDA|GNDD|GNDPWR|0V)$", re.I)
GENERIC_LIBS = re.compile(r"^(Device|Jumper|Connector\w*|power|Switch|Mechanical|Graphic|Diode|LED|Transistor_BJT|Battery_Management_generic|Simulation\w*)$")


def _different_signals(a: str, b: str) -> bool:
    """Two nets that are plainly not one signal: a rail and a non-rail, or the + and - halves of a pair."""
    if (rail_voltage(a) is None) != (rail_voltage(b) is None):
        return True
    sa, sb = (_diff_polarity(n.split("/")[-1])[1] for n in (a, b))
    return bool(sa and sb and sa != sb)


def _token(name: str, token: str) -> bool:
    return bool(re.search(rf"(^|[^A-Z0-9]){token}(\d*)($|[^A-Z])", name.upper()))


def rail_voltage(net: str) -> float | None:
    """0 for a ground net, a signed voltage for a net named after one (+5V, 3V3, A-2V5, -12V), else None."""
    if GROUND.search(net):
        return 0.0
    seg = net.split("/")[-1]
    if not (SUPPLY.search(net) or seg[:1] in "+-"):
        return None
    up = seg.upper()
    m = (re.search(r"([+-])?(\d+)V(\d+)", up) or re.search(r"([+-])?(\d+)\.(\d+)V", up) or re.search(r"([+-])?(\d+)()V(?![A-Z])", up)
         or re.search(r"([+-])(\d+)(?:\.(\d+))?$", up))
    if not m:
        return None
    value = float(f"{m.group(2)}.{m.group(3) or 0}")
    return -value if m.group(1) == "-" else value


def _pin_name(comp: dict[str, Any], node: dict[str, str]) -> str:
    if node.get("function"):
        return node["function"]
    return next((str(p.get("name", "")) for p in comp.get("pins", []) if p.get("num") == node.get("pin")), "")


def _physics_findings(comps, nets, pin_net, finding) -> None:
    names: dict[tuple[str, str], str] = {}
    for net, nodes in nets.items():
        for n in nodes:
            names[(n["ref"], n["pin"])] = _pin_name(comps.get(n["ref"], {}), n)
    negative_rails = any((v := rail_voltage(net)) is not None and v < 0 for net in nets)

    def comp_of(ref: str) -> dict[str, Any]:
        return comps.get(ref, {})

    def describe(ref: str) -> str:
        c = comps.get(ref, {})
        return " ".join(str(c.get(k, "")) for k in ("lib", "part", "value", "description"))

    by_ref: dict[str, dict[str, str]] = {}
    for (ref, pin), net in pin_net.items():
        by_ref.setdefault(ref, {})[pin] = net

    for ref, pins in by_ref.items():
        text = describe(ref)
        roles: dict[str, list[str]] = {}
        for pin in pins:
            roles.setdefault(names.get((ref, pin), "").upper(), []).append(pin)
        # Diodes, from their anode (A) and cathode (K) pins: dual parts pair A1 with K1.
        diode = re.match(r"(D|LED|CR|DS)\d", ref) or re.search(r"diode|\bled\b", text, re.I)
        # A part that repeats A or K (BAV99 names its pins K, A, K; MMBD1503A K, A, A) cannot be paired by name, so it is skipped.
        repeated = any(sum(str(p.get("name", "")).upper() == n for p in comps.get(ref, {}).get("pins", [])) > 1 for n in ("A", "K"))
        if diode and not repeated:
            led = bool(re.search(r"\bled\b|^LED|:LED", text, re.I)) or ref.upper().startswith("LED")
            for suffix in ("", "1", "2", "3", "4"):
                a = roles.get("A" + suffix, [None])[0]
                k = roles.get("K" + suffix, [None])[0]
                if a is None or k is None:
                    continue
                na, nk = pins[a], pins[k]
                va, vk = rail_voltage(na), rail_voltage(nk)
                # Between two positive rails a diode is often deliberate (a drop to "4.6V", OR-ing), so only a path to ground or below counts.
                if va is not None and vk is not None and va > 0 >= vk:
                    finding("error" if not led else "warning", "diode_forward_across_rails",
                            f"{ref} anode{suffix} is on {na} ({va:g} V) and its cathode on {nk} ({vk:g} V): it is forward-biased between two rails and "
                            "conducts all the time. Check the part's pinout and its orientation.",
                            "diode conducts from anode to cathode; rail voltages read from the net names", [ref], na, local=True)
                elif led and not negative_rails and (va == 0 or (vk is not None and vk > 0 and va is None)):
                    where = f"anode on ground net {na}" if va == 0 else f"cathode on supply net {nk}"
                    finding("warning", "led_reversed", f"{ref} has its {where}, so it can never be forward-biased in a board with no negative rail. "
                            "Check its orientation and pinout.", "LED conducts from anode to cathode; pin names from KiCad's symbol", [ref], na if va == 0 else nk, local=True)
        # Bipolar transistors: an NPN conducts collector to emitter, so its collector sits above its emitter (a PNP the other way).
        bjt = "npn" if re.search(r"\bnpn\b|q_npn", text, re.I) else "pnp" if re.search(r"\bpnp\b|q_pnp", text, re.I) else None
        if bjt and "C" in roles and "E" in roles:
            nc, ne = pins[roles["C"][0]], pins[roles["E"][0]]
            vc, ve = rail_voltage(nc), rail_voltage(ne)
            if bjt == "npn" and vc == 0 and ve != 0 and not (ve is not None and ve < 0):
                finding("warning", "bjt_collector_emitter_reversed", f"{ref} (NPN) has its collector on ground net {nc} and its emitter on {ne}. "
                        "An NPN switch normally has its emitter on ground; reversed it works poorly, if at all.",
                        "NPN conduction from collector to emitter; pin names from KiCad's symbol", [ref], nc, local=True)
            if bjt == "pnp" and vc is not None and vc > 0 and (ve is None or ve < vc) and not SUPPLY.search(ne):
                finding("warning", "bjt_collector_emitter_reversed", f"{ref} (PNP) has its collector on supply net {nc} and its emitter on {ne}. "
                        "A PNP switch normally has its emitter on the supply.", "PNP conduction from emitter to collector; pin names from KiCad's symbol", [ref], nc, local=True)
        # Power pins on the wrong rail.
        for pin, net in pins.items():
            name = names.get((ref, pin), "")
            v = rail_voltage(net)
            if GROUND_PIN.match(name) and v not in (None, 0.0) and not GROUND.search(net):
                finding("error", "ground_pin_on_supply", f"{ref} pin {pin} ({name}) is on supply net {net} ({v:g} V).",
                        "pin named as a ground; rail voltage read from the net name", [ref], net, local=True)
            # Only the board's main ground: stacked designs (Bitcoin-miner ASIC chains) feed each chip's VDD from the next one's GND1.
            if SUPPLY_PIN.match(name) and MAIN_GROUND.match(net.split("/")[-1]) and len(nets.get(net, [])) > 1:
                finding("error", "supply_pin_on_ground", f"{ref} pin {pin} ({name}) is on ground net {net}, so the part has no supply.",
                        "pin named as a supply input; ground read from the net name", [ref], net, local=True)
        # Two pins with one signal name are usually one node inside the part (an ESD array's pass-through I/O1, a receptacle's D+),
        # so putting them on two nets joins those nets through the part.
        comp = comp_of(ref)
        lib_names: dict[str, list[dict[str, str]]] = {}
        for p in comp.get("pins", []):
            lib_names.setdefault(str(p.get("name", "")), []).append(p)
        for pname, group in lib_names.items():
            if len(group) != 2 or not JOINED_NAME.search(pname) or NC_NAME.match(pname) or any(p.get("type") in ("power_in", "power_out") for p in group):
                continue
            a, b = (pins.get(p["num"]) for p in group)
            # Flow-through layouts (a clamp's pin 1 to the connector, pin 6 to the chip) join two names for one signal on purpose, and
            # multi-unit symbols repeat names, so only nets that are plainly different signals count: the two halves of a pair, or a rail and a signal.
            if a and b and a != b and len(nets.get(a, [])) > 1 and len(nets.get(b, [])) > 1 and _different_signals(a, b):
                finding("warning", "joined_pins_split", f"{ref} pins {group[0]['num']} and {group[1]['num']} are both {pname}, usually one node inside the part, "
                        f"but they sit on two nets ({a} and {b}), which the part then joins.", "pin names from KiCad's symbol", [ref], a, local=True)
    # A part's positive and negative supply pins on rails the wrong way round (an op-amp's V+ on -12 V and V- on +12 V).
    for ref, pins in by_ref.items():
        named = {names.get((ref, pin), "").upper(): net for pin, net in pins.items()}
        for pos, neg in RAIL_PAIRS:
            if pos in named and neg in named:
                vp, vn = rail_voltage(named[pos]), rail_voltage(named[neg])
                if vp is not None and vn is not None and vp < vn:
                    finding("error", "supply_rails_inverted", f"{ref} {pos} is on {named[pos]} ({vp:g} V) but {neg} on {named[neg]} ({vn:g} V): "
                            f"its supply is reversed.", "pin names from KiCad's symbol; rail voltages read from the net names", [ref], named[pos], local=True)
    # A net named after one signal of a pair that meets the other signal's pin: SDA on an SCL pin, MOSI on MISO.
    for net, nodes in nets.items():
        seg = net.split("/")[-1]
        for first, second in NAME_PAIRS:
            for named, other in ((first, second), (second, first)):
                if not _token(seg, named) or _token(seg, other):
                    continue
                # Pins of both signals on one net are a short, which i2c_sda_scl_short already reports.
                if any(_token(names.get((n["ref"], n["pin"]), ""), named) for n in nodes):
                    continue
                for n in nodes:
                    pname = names.get((n["ref"], n["pin"]), "")
                    if _token(pname, other) and not _token(pname, named) and not _is_connector(comps.get(n["ref"], {})):
                        finding("warning", "net_name_pin_mismatch", f"Net {net} is named {named} but meets {n['ref']} pin {n['pin']} ({pname}). "
                                f"Check {named} and {other} are not swapped.", "net label versus the pin function in KiCad's symbol", [n["ref"]], net)


def _library_pinout_findings(comps, finding) -> None:
    """A part whose value or part number names a symbol in KiCad's own library, drawn with a different symbol that numbers its pins
    differently: one of the two pinouts is wrong for the real part."""
    try:
        from .part_lookup import libraries_available, lookup_part, symbol_pins
    except ImportError:
        return
    if not libraries_available():
        return

    def role(name: str) -> str | None:
        n = name.upper().strip()
        if n in ("G", "GATE"):
            return "gate"
        if n in ("S", "SOURCE"):
            return "source"
        if n in ("D", "DRAIN"):
            return "drain"
        if n in ("B", "BASE"):
            return "base"
        if n in ("C", "COLLECTOR"):
            return "collector"
        if n in ("E", "EMITTER"):
            return "emitter"
        if n in ("A", "ANODE"):
            return "anode"
        if n in ("K", "CATHODE"):
            return "cathode"
        if GROUND_PIN.match(n) or n == "VSS":
            return "ground"
        if SUPPLY_PIN.match(n):
            return "supply"
        return None

    for ref, comp in comps.items():
        if not comp.get("pins") or len(comp["pins"]) > 64:
            continue
        fields = comp.get("fields", {})
        names = [comp.get("value", "")] + [v for k, v in fields.items() if re.search(r"mpn|part ?number|manufacturer_?part", k, re.I)]
        # A part number has letters and digits (AO3401A, W25Q128JVS); "Jumper_3_Bridged12" or "LED" names a generic symbol instead.
        for candidate in dict.fromkeys(n.strip() for n in names if n and 5 <= len(n.strip()) <= 40 and re.search(r"[A-Za-z]{2}", n)
                                       and re.search(r"\d", n) and not re.search(r"[_ ]", n.strip())):
            hits = [m for m in lookup_part(candidate).get("matches", []) if m.get("tier") == "exact" and not GENERIC_LIBS.match(m.get("library", ""))]
            if not hits:
                continue
            hit = hits[0]
            if hit["library"] == comp.get("lib") and hit["name"] == comp.get("part"):
                break
            try:
                theirs = {p["number"]: p["name"] for p in symbol_pins(hit["library"], hit["name"], limit=None)["pins"]}
            except Exception:  # an unreadable library symbol is a reason to skip, not to fail the review
                break
            ours = {str(p.get("num")): str(p.get("name", "")) for p in comp["pins"]}
            if len(ours) != len(theirs):  # a breakout module (BME280's VIN, GND, SCL, SDA) is drawn with fewer pins than its chip
                break
            clashes = [(num, ours[num], theirs[num]) for num in sorted(set(ours) & set(theirs))
                       if role(ours[num]) and role(theirs[num]) and role(ours[num]) != role(theirs[num])]
            if clashes:
                listed = "; ".join(f"pin {num}: {a} here, {b} in KiCad" for num, a, b in clashes[:4])
                finding("warning", "pinout_differs_from_kicad_library",
                        f"{ref} ({candidate}) is drawn with {comp.get('lib')}:{comp.get('part')}, but KiCad's own symbol {hit['library']}:{hit['name']} "
                        f"for that part numbers its pins differently ({listed}). Check the datasheet's pinout.",
                        f"KiCad library symbol {hit['library']}:{hit['name']}, matched by exact part name", [ref])
            break


USB2_PIN = re.compile(r"(^|[/_])(USB\d?_?)?D\d?(?P<sign>[+-]|P|M|N)$", re.I)
DIFF_PIN = re.compile(r"(^|[/_])[A-Z0-9_]*?(TX|RX|HS[IO]|HSO|HSI|CLK|LANE|REFCLK)\d*_?(?P<sign>P|N|\+|-)$", re.I)


def _diff_polarity(function: str) -> tuple[str | None, str | None]:
    """('usb2' or 'pair', '+' or '-') for a differential pin function, else (None, None)."""
    for kind, pat in (("usb2", USB2_PIN), ("pair", DIFF_PIN)):
        m = pat.search(function or "")
        if m:
            return kind, "+" if m.group("sign").upper() in ("+", "P") else "-"
    return None, None


def review(model: dict[str, Any], mates: dict[str, Any] | None = None, library_check: bool = True) -> dict[str, Any]:
    comps, nets = model["components"], model["nets"]
    pin_net: dict[tuple[str, str], str] = {}
    for name, nodes in nets.items():
        for n in nodes:
            pin_net[(n["ref"], n["pin"])] = name
    findings: list[dict[str, Any]] = []

    wired = {n["ref"] for ns in nets.values() for n in ns}
    unannotated = sorted(r for r in comps if "?" in r and r in wired)  # a drawing-sheet symbol is on no net
    skipped: list[str] = []

    def finding(severity: str, rule: str, message: str, basis: str, refs: list[str], net: str | None = None, local: bool = False) -> None:
        # An unannotated designator ("R?") names several parts at once, so nothing traced through one can be trusted. A local
        # finding rests only on the part's own pins and the net's name, so other parts' designators on that net do not matter.
        if any("?" in r for r in refs) or (net and not local and any("?" in n["ref"] for n in nets.get(net, []))):
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
        uart_parts = [n for n in parts if not TRANSCEIVER.search(" ".join(str(v) for k, v in comps.get(n["ref"], {}).items() if k not in ("pins", "fields", "footprint")))]
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
        # A logic input with nothing on it floats. KiCad marks deliberate no-connects as "input+no_connect", so a bare "input" was forgotten.
        # General-purpose and analog pins (GPIO, PA3, ADC1) are left open on most boards, so only fixed-function inputs count.
        if (len(nodes) == 1 and n["type"] == "input" and not is_module and not _is_connector(comps.get(n["ref"], {}))
                and not re.match(r"(GPIO|GP\d|IO\d|P[A-K]?\d|ADC|AIN|SENSOR|A\d|D\d|NC|DNC|N\.C|TEST|TP|RESERVED|RSV)", n["function"], re.I)):
            # Standard logic (74xx, 4000 series) has no internal pull resistors; other ICs often do (BQ25895 QON, TJA1051 S), so those get a note.
            part = comps.get(n["ref"], {})
            logic = bool(re.search(r"^(4xxx|74xx|CMOS)|^(74|CD4|HEF4|MC14|SN74|4\d{3}\b)", f"{part.get('lib', '')}|{part.get('value', '')}|{part.get('part', '')}".replace("|", "\n"), re.I | re.M))
            finding("warning" if logic else "info", "input_pin_floating",
                    f"{n['ref']} pin {n['pin']} ({n['function'] or 'input'}) is an input with nothing on it. "
                    + ("Standard logic has no internal pull: tie it high or low." if logic else "Check the datasheet for an internal pull resistor; otherwise tie it high or low."),
                    "KiCad pin type input; CMOS inputs must not float", [n["ref"]], name)
        # Some symbols type an IC's I2C pins passive (osm-l-bmc-som's PMIC and EEPROM): an IC's pin counts whatever its type.
        ic_pins = parts + [n for n in nodes if n["type"] == "passive" and n not in parts and n["function"]
                           and _kind(comps.get(n["ref"], {"lib": "", "part": "", "description": ""}), n["ref"]) not in ("resistor", "capacitor")
                           and not _is_connector(comps.get(n["ref"], {})) and re.match(r"(U|IC)\d", n["ref"])]
        sda = sorted({n["ref"] + "." + n["function"] for n in ic_pins if re.search(r"(^|[/_])SDA", n["function"], re.I) and not re.search(r"SCL", n["function"], re.I)})
        scl = sorted({n["ref"] + "." + n["function"] for n in ic_pins if re.search(r"(^|[/_])SCL", n["function"], re.I) and not re.search(r"SDA", n["function"], re.I)})
        # A differential pair crossed: one net joins a pair's positive and negative pins of two different parts.
        polar = [(n, *_diff_polarity(n["function"])) for n in ic_pins + [x for x in nodes if _is_connector(comps.get(x["ref"], {})) and x not in ic_pins]]
        # An ESD or TVS array's channels (TPD4EUSB30 "D2+") carry no polarity: any channel may take either line.
        clamp = lambda ref: re.search(r"esd|tvs|usblc|prtr|clamp|protect|TPD\d", " ".join(str(v) for k, v in comps.get(ref, {}).items()
                                                                                  if k not in ("pins", "fields", "footprint")), re.I)
        polar = [(n, kind, sign) for n, kind, sign in polar if kind and not clamp(n["ref"])]
        signs = {sign for _, _, sign in polar}
        if len(signs) == 2 and len({n["ref"] for n, _, _ in polar}) >= 2:
            usb = any(kind == "usb2" for _, kind, _ in polar)
            listed = ", ".join(sorted(f"{n['ref']}.{n['function']}" for n, _, _ in polar))
            finding("error" if usb else "warning", "diff_pair_polarity_swap",
                    f"Net {name} joins positive and negative pins of a differential pair ({listed})."
                    + (" USB 2.0 has no polarity inversion: D+ must meet D+." if usb else
                       " Check it is deliberate: PCIe, SATA and USB 3 lanes may be inverted, other pairs may not."),
                    "pin functions from KiCad's symbols; USB 2.0 data pair (D+ to D+, D- to D-)" if usb else
                    "pin functions from KiCad's symbols; lane polarity inversion is allowed by PCIe and USB 3 only",
                    [n["ref"] for n, _, _ in polar], name)
        if sda and scl:
            finding("error", "i2c_sda_scl_short", f"Net {name} joins I2C data ({', '.join(sda)}) and clock ({', '.join(scl)}). SDA and SCL must be separate nets.",
                    UM10204, [x.split(".")[0] for x in sda + scl], name)
        i2c_parts = {n["ref"] for n in parts if I2C.search(n["function"])}
        # A bus from GPIO pins to a connector is I2C by its net name only (vandaemon's /MCU/I2C_SDA on IO12 and J13).
        named_bus = len(i2c_parts) < 2 and bool(I2C.search(name.split("/")[-1])) and bool(parts) and len({n["ref"] for n in nodes}) >= 2
        if named_bus:
            i2c_parts = {n["ref"] for n in nodes}
        if len(i2c_parts) >= 2 and not resistor_to(name, SUPPLY):  # a bus needs two parts; one strap pin is not a bus
            # Any part on the net that is a module (judged by its part name, never its library's name), whatever its pin there is called.
            modules = sorted({n["ref"] for n in nodes if re.search(r"module|compute ?module|\bcm[345]\b|wroom|wrover|\bpico\b|devkit",
                                                                    f"{comps.get(n['ref'], {}).get('part', '')} {comps.get(n['ref'], {}).get('value', '')}", re.I)})
            listed = ", ".join(sorted(n["ref"] + "." + (n["function"] or n["pin"]) for n in (nodes if named_bus else parts) if named_bus or I2C.search(n["function"])))
            # A bus known only by name that leaves through a connector may get its pull-ups from the far side (a GPS module, an HDMI sink).
            off_board = named_bus and any(_is_connector(comps.get(n["ref"], {})) or re.match(r"(J|CN|P|X|CON|HDMI|DPHY)\d", n["ref"]) for n in nodes)
            if off_board:
                finding("info", "i2c_no_pullup", f"Net {name} is named as I2C and leaves the board through a connector with no pull-up here ({listed}). "
                        "Fit pull-ups unless the device on the other end has them.", UM10204, sorted(i2c_parts), name)
            elif modules:
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
                                     and not re.search(r"esd|tvs|usblc|prtr|clamp|protect", " ".join(str(v) for k, v in comps.get(x["ref"], {}).items() if k not in ("pins", "fields", "footprint")), re.I)})
                if controller:
                    finding("info", "usb_c_cc_no_pulldown", f"{ref} {fn} has no resistor to ground but goes to {', '.join(controller)}, which may terminate CC itself "
                            "(a PD or CC controller, or a module such as the CM5): check its datasheet.", "USB Type-C sink termination Rd = 5.1 kOhm", [ref, *controller], net)
                    continue
                if net is None or not resistor_to(net, GROUND):
                    finding("warning", "usb_c_cc_no_pulldown", f"{ref} {fn} {'is not connected' if net is None else 'has no resistor to ground'}. A USB-C sink needs Rd (5.1 kOhm) on each CC pin or a "
                            "source will not supply 5 V.", "USB Type-C specification, sink termination Rd = 5.1 kOhm (cited by section, not quoted here)", [ref], net)
    _pull_rule_findings(comps, nets, pin_net, finding, resistor_to, driven_supply)
    _physics_findings(comps, nets, pin_net, finding)
    if library_check:
        _library_pinout_findings(comps, finding)
    _mated_findings(comps, nets, pin_net, mates, finding)
    if unannotated:
        findings.append({"severity": "info", "rule": "unannotated", "components": unannotated,
                         "message": f"{len(unannotated)} designator(s) still end in '?' ({', '.join(unannotated[:5])}). Annotate the schematic and review again: "
                                    f"{len(skipped)} check(s) touching those parts were not reported.", "basis": "KiCad annotation; the netlist keys parts by designator"})
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("error", "warning", "info")}
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "components": len(comps), "nets": len(nets), "findings": findings, "counts": counts}


# On 35 held-out bugs (examples/schematic_bug_benchmark/heldout_benchmark_20261127.json) KiCad ERC caught 9, kicad-happy 9 and HS 5;
# together 14. ``also`` runs the other two next to HS's rules so one call gets all three.
ALSO = ("kicad_erc", "kicad_happy")


def _kicad_erc(sch: Path, cli: str, work: Path) -> dict[str, Any]:
    sch = sch.resolve()
    report = work / "erc.json"
    subprocess.run([cli, "sch", "erc", "--format", "json", "--severity-all", "--output", str(report), str(sch)],
                   capture_output=True, text=True, timeout=600, check=False, cwd=str(sch.parent))
    if not report.exists():
        return {"ran": False, "why": "kicad-cli wrote no ERC report"}
    data = json.loads(report.read_text(encoding="utf-8"))
    rows = [{"type": v.get("type"), "severity": v.get("severity"), "message": v.get("description"),
             "where": [i.get("description") for i in v.get("items", [])][:4]} for sheet in data.get("sheets", []) for v in sheet.get("violations", [])]
    return {"ran": True, "kicad_version": data.get("kicad_version"), "findings": rows,
            "counts": {s: sum(r["severity"] == s for r in rows) for s in ("error", "warning")}}


def _kicad_happy(sch: Path, work: Path) -> dict[str, Any]:
    import os
    import shutil

    root = os.environ.get("HARDWARE_SPLICER_KICAD_HAPPY_ROOT")
    script = Path(root) / "skills/kicad/scripts/analyze_schematic.py" if root else None
    if script is None or not script.exists():
        return {"ran": False, "why": "kicad-happy (MIT, aklofas/kicad-happy) is not set up: clone it and set HARDWARE_SPLICER_KICAD_HAPPY_ROOT"}
    out = work / "kicad_happy.json"
    cmd = [sys.executable, "-I", str(script), str(sch.resolve()), "--only-deterministic", "--compact", "-o", str(out)]
    if shutil.which("bwrap"):  # no network for an outside tool reading the user's design
        cmd = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--bind", str(work), str(work), "--dev", "/dev", "--proc", "/proc", *cmd]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    if not out.exists():
        return {"ran": False, "why": "kicad-happy wrote no report"}
    data = json.loads(out.read_text(encoding="utf-8"))
    rows = [{"rule": f.get("rule_id") or f.get("detector"), "severity": f.get("severity"), "message": str(f.get("summary", ""))[:300],
             "components": f.get("components") or f.get("refs") or []} for f in data.get("findings", [])]
    return {"ran": True, "findings": rows, "counts": {s: sum(r["severity"] == s for r in rows) for s in ("error", "warning", "info")}}


def review_schematic(path: Path, mates: dict[str, Any] | None = None, also: tuple[str, ...] = ()) -> dict[str, Any]:
    result = _review_schematic(path, mates)
    if also:
        if path.suffix == ".net":
            result["also"] = {name: {"ran": False, "why": "needs the .kicad_sch, not a netlist"} for name in also}
            return result
        from .model3d import resolve_kicad_cli

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            result["also"] = {}
            if "kicad_erc" in also:
                cli = resolve_kicad_cli()
                result["also"]["kicad_erc"] = _kicad_erc(path, cli, work) if cli else {"ran": False, "why": "kicad-cli not found"}
            if "kicad_happy" in also:
                result["also"]["kicad_happy"] = _kicad_happy(path, work)
        result["also_note"] = ("KiCad ERC and kicad-happy findings are theirs, reported unchanged beside HS's own; on held-out bugs the three "
                               "together caught 14 of 35, each alone at most 9.")
    return result


def _review_schematic(path: Path, mates: dict[str, Any] | None = None) -> dict[str, Any]:
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
    also = ()
    if "--also" in args:
        also = ALSO
        args = [a for a in args if a != "--also"]
    if "--mates" in args:
        i = args.index("--mates")
        mates = json.loads(Path(args[i + 1]).read_text(encoding="utf-8"))
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        print(json.dumps(review_schematic(Path(args[0]), mates, also), indent=2))
    except (KicadReviewError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
