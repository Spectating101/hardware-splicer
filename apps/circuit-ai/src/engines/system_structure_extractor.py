from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from src.engines.evidence_extractor import infer_common_interface_facts, is_ground_net, is_power_net
from src.engines.controller_runtime_analysis import analyze_controller_runtime
from src.engines.kicad_hints import find_rail_candidates, guess_ground_net, infer_ldo_candidates
from src.engines.kicad_netlist_compiler import _parse_kicad_pcb_components_and_pinmap, parse_resistance_ohms
from src.engines.kicad_parser import KiCadParser
from src.engines.machine_requirements import compile_machine_requirements
from src.engines.power_control_analysis import analyze_power_control


_POWER_NET_VOLTAGES: List[Tuple[re.Pattern[str], float]] = [
    (re.compile(r"(^|\b)(\+?1V8|1V8|1\.8V|VDD1V8)(\b|$)", re.I), 1.8),
    (re.compile(r"(^|\b)(\+?2V5|2V5|2\.5V|VDD2V5)(\b|$)", re.I), 2.5),
    (re.compile(r"(^|\b)(\+?3V3|3V3|3\.3V|VCC3V3|VDD3V3)(\b|$)", re.I), 3.3),
    (re.compile(r"(^|\b)(\+?5V|5V0|VBUS|USB_5V|VUSB|VCC5V|VDD5V)(\b|$)", re.I), 5.0),
    (re.compile(r"(^|\b)(\+?9V|9V0|VCC9V|VDD9V)(\b|$)", re.I), 9.0),
    (re.compile(r"(^|\b)(\+?12V|12V0|VCC12V|VDD12V)(\b|$)", re.I), 12.0),
    (re.compile(r"(^|\b)(\+?24V|24V0|VCC24V|VDD24V)(\b|$)", re.I), 24.0),
]

_CATEGORY_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "mcu": (
        "STM32",
        "ESP32",
        "ESP8266",
        "ATMEGA",
        "ATSAMD",
        "RP2040",
        "NRF52",
        "PIC",
        "GD32",
        "CH32",
        "LPC",
        "IMXRT",
        "TINYPICO",
        "NODEMCU",
        "DEVKIT",
        "FEATHER",
    ),
    "gate_driver": (
        "LM5101",
        "IR210",
        "IRS200",
        "MIC460",
        "FAN738",
        "HIP210",
    ),
    "current_sense_amp": (
        "INA240",
        "INA181",
        "INA199",
        "MAX4080",
        "CURRENT_SENSE",
    ),
    "sensor": (
        "BME",
        "BMP",
        "SHT",
        "MPU",
        "ICM",
        "BMI",
        "LIS3",
        "TOF",
        "VL53",
        "ADS",
        "HX711",
        "ACS",
        "SENSOR",
    ),
    "regulator": (
        "LDO",
        "REG",
        "AMS1117",
        "AP2112",
        "LM1117",
        "LM7805",
        "7805",
        "TLV",
        "TPS",
        "MCP17",
        "MCP1642",
        "LM22675",
        "AZ1117",
        "LM2596",
        "XL6009",
        "MPM",
        "MP1584",
        "XC620",
        "BUCK",
        "BOOST",
        "TL431",
    ),
    "motor_driver": (
        "DRV",
        "TB6612",
        "A4988",
        "TMC",
        "BTN797",
        "VNH",
        "MOTOR",
        "ESC",
    ),
    "radio": (
        "NRF24",
        "SX127",
        "LORA",
        "CC1101",
        "ESP32-WROOM",
        "ESP32-WROVER",
        "WIFI",
        "BLE",
        "GNSS",
        "GPS",
    ),
    "transceiver": (
        "MAX485",
        "SN65",
        "MCP2551",
        "TJA105",
        "CH340",
        "CP210",
        "FT232",
        "LAN",
        "ETH",
        "PHY",
    ),
    "memory": ("FLASH", "EEPROM", "FRAM", "QSPI", "EMMC"),
}

_CONNECTOR_PREFIXES = ("J", "P", "X", "CN", "CONN")
_CONNECTOR_KEYWORDS = (
    "CONN",
    "CONNECTOR",
    "JST",
    "HEADER",
    "USB",
    "RJ45",
    "RJ11",
    "TERMINAL",
    "MOLEX",
    "PINHEADER",
    "XH",
    "SH",
    "XT30",
    "XT60",
)

_INTERFACE_SIGNAL_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("SCL", re.compile(r"(^|[_\-/])SCL($|[_\-/])|I2C.*SCL|SCL.*I2C", re.I)),
    ("SDA", re.compile(r"(^|[_\-/])SDA($|[_\-/])|I2C.*SDA|SDA.*I2C", re.I)),
    ("SCLK", re.compile(r"(^|[_\-/])(SCLK|SCK|CLK)($|[_\-/])|SPI.*(SCLK|SCK)", re.I)),
    ("MOSI", re.compile(r"(^|[_\-/])(MOSI|SDO)($|[_\-/])|SPI.*MOSI", re.I)),
    ("MISO", re.compile(r"(^|[_\-/])(MISO|SDI)($|[_\-/])|SPI.*MISO", re.I)),
    ("CS", re.compile(r"(^|[_\-/])(CS|NCS|NSS|SS)($|[_\-/])", re.I)),
    ("TX", re.compile(r"(^|[_\-/])(TXD?\d*|USART\d*TX|UART\d*TX)($|[_\-/])|UART.*TX|TX.*UART", re.I)),
    ("RX", re.compile(r"(^|[_\-/])(RXD?\d*|USART\d*RX|UART\d*RX)($|[_\-/])|UART.*RX|RX.*UART", re.I)),
    ("CANH", re.compile(r"CAN[\s_\-/]*H", re.I)),
    ("CANL", re.compile(r"CAN[\s_\-/]*L", re.I)),
    ("D+", re.compile(r"(D\+|USB_DP|USBDP|DP$)", re.I)),
    ("D-", re.compile(r"(D\-|USB_DM|USBDM|DM$)", re.I)),
    ("SWDIO", re.compile(r"SWDIO", re.I)),
    ("SWCLK", re.compile(r"SWCLK", re.I)),
]

_INTERFACE_RULES: Dict[str, Tuple[Set[str], ...]] = {
    "i2c": ({"SCL"}, {"SDA"}),
    "spi": ({"SCLK"}, {"MOSI"}, {"MISO"}),
    "uart": ({"TX"}, {"RX"}),
    "can": ({"CANH"}, {"CANL"}),
    "usb2": ({"D+"}, {"D-"}),
    "swd": ({"SWDIO"}, {"SWCLK"}),
}


def _normalize_net(net: str) -> str:
    if not net:
        return ""
    stripped = net.strip()
    if is_ground_net(stripped):
        return "0"
    return stripped


def _ref_prefix(ref: str) -> str:
    ref = (ref or "").strip().upper()
    for index, char in enumerate(ref):
        if char.isdigit():
            return ref[:index]
    return ref


def _infer_nominal_voltage(net: str) -> Optional[float]:
    text = (net or "").strip()
    candidates = [text, text.lstrip("/")]
    normalized = candidates[-1].upper()
    for suffix in ("_RAIL", "-RAIL"):
        if normalized.endswith(suffix):
            candidates.append(normalized[: -len(suffix)])
    for candidate in candidates:
        for pattern, nominal in _POWER_NET_VOLTAGES:
            if pattern.search(candidate):
                return nominal
    for token in re.split(r"[^A-Z0-9+]+", normalized):
        match = re.fullmatch(r"\+?(\d{1,2})V(\d)?", token)
        if not match:
            continue
        whole = int(match.group(1))
        fractional = match.group(2)
        if fractional is not None:
            return float(f"{whole}.{fractional}")
        return float(whole)
    return None


def _is_source_like_power_net(net: str) -> bool:
    up = (net or "").strip().upper().lstrip("/")
    for suffix in ("_RAIL", "-RAIL"):
        if up.endswith(suffix):
            up = up[: -len(suffix)]
    if up.endswith("V+"):
        return True
    return up.startswith(("VIN", "VBAT", "VBUS", "VUSB", "VPP", "VSYS")) or up in {"+12V", "+24V", "12V", "24V"}


def _pinmap_from_nets(nets: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    pinmap: Dict[str, Dict[str, str]] = {}
    for net_name, net_data in (nets or {}).items():
        normalized = _normalize_net(net_name)
        for node in net_data.get("nodes", []) or []:
            ref = node.get("ref")
            pin = node.get("pin")
            if not ref or not pin:
                continue
            pinmap.setdefault(str(ref), {})[str(pin)] = normalized
    return pinmap


def _nets_from_pinmap(pinmap: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    nets: Dict[str, Dict[str, Any]] = {}
    code = 1
    for ref, pins in pinmap.items():
        for pin, net_name in (pins or {}).items():
            normalized = _normalize_net(net_name)
            if not normalized:
                continue
            nets.setdefault(normalized, {"code": str(code), "nodes": []})
            nets[normalized]["nodes"].append({"ref": ref, "pin": pin})
            code += 1
    return nets


def _load_components_pinmap_and_nets(design_path: Path, kind: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]], Dict[str, Dict[str, Any]]]:
    chosen_kind = (kind or design_path.suffix.lstrip(".")).strip().lower()
    if chosen_kind in {"kicad_pcb", "pcb"} or design_path.suffix.lower() == ".kicad_pcb":
        components, pinmap = _parse_kicad_pcb_components_and_pinmap(str(design_path))
        return components, pinmap, _nets_from_pinmap(pinmap)
    parsed = KiCadParser(str(design_path)).parse()
    nets = parsed.get("nets") or {}
    pinmap = _pinmap_from_nets(nets)
    return parsed.get("components") or {}, pinmap, nets


def _component_category(ref: str, meta: Dict[str, Any]) -> str:
    prefix = _ref_prefix(ref)
    value = str(meta.get("value") or "").upper()
    footprint = str(meta.get("footprint") or "").upper()
    blob = f"{value} {footprint} {prefix}"
    if _is_connector(ref, meta):
        return "connector"
    if prefix == "R":
        return "resistor"
    if prefix == "C":
        return "capacitor"
    if prefix == "L":
        return "inductor"
    if prefix == "Q":
        return "transistor"
    if prefix == "D":
        return "diode"
    for category, patterns in _CATEGORY_PATTERNS.items():
        if any(token in blob for token in patterns):
            return category
    if prefix in {"U", "IC"}:
        return "ic"
    return "other"


def _is_connector(ref: str, meta: Dict[str, Any]) -> bool:
    prefix = _ref_prefix(ref)
    value = str(meta.get("value") or "").upper()
    footprint = str(meta.get("footprint") or "").upper()
    if prefix in _CONNECTOR_PREFIXES:
        return True
    return any(token in value or token in footprint for token in _CONNECTOR_KEYWORDS)


def _canonical_signal_aliases(net_name: str) -> Set[str]:
    aliases: Set[str] = set()
    normalized = _normalize_net(net_name)
    if not normalized:
        return aliases
    if is_ground_net(normalized):
        aliases.add("GND")
    if is_power_net(normalized):
        voltage = _infer_nominal_voltage(normalized)
        if voltage is not None:
            aliases.add(f"POWER::{voltage:.1f}V")
        aliases.add(f"POWER::{normalized.upper()}")
    for signal_name, pattern in _INTERFACE_SIGNAL_PATTERNS:
        if pattern.search(normalized):
            aliases.add(signal_name)
    return aliases


def _connector_interfaces(pin_nets: Dict[str, str]) -> List[Dict[str, Any]]:
    nets = {_normalize_net(net) for net in pin_nets.values() if _normalize_net(net)}
    aliases_by_net = {net: _canonical_signal_aliases(net) for net in nets}
    interface_rows: List[Dict[str, Any]] = []

    for interface, groups in _INTERFACE_RULES.items():
        matched_signals: List[str] = []
        for group in groups:
            matched = sorted({alias for aliases in aliases_by_net.values() for alias in aliases if alias in group})
            if not matched:
                break
            matched_signals.extend(matched)
        else:
            confidence = 0.7 + min(len(matched_signals), 4) * 0.05
            interface_rows.append(
                {
                    "interface": interface,
                    "signals": sorted(set(matched_signals)),
                    "confidence": round(min(confidence, 0.95), 2),
                }
            )

    power_nets = sorted(net for net in nets if is_power_net(net))
    if power_nets and any(is_ground_net(net) for net in nets):
        interface_rows.append(
            {
                "interface": "power",
                "signals": ["GND", *power_nets],
                "confidence": 0.8,
            }
        )

    return interface_rows


def _connector_semantic_role(
    *,
    value: str,
    footprint: str,
    pin_nets: Dict[str, str],
    interfaces: List[Dict[str, Any]],
) -> str:
    text = f"{value} {footprint}".upper()
    nets = {_normalize_net(net).upper() for net in pin_nets.values() if _normalize_net(net)}
    interface_names = {str(row.get("interface") or "") for row in interfaces}
    power_nets = {net for net in nets if is_power_net(net)}
    non_power_nets = {net for net in nets if net not in power_nets and not is_ground_net(net)}
    control_like_nets = {
        net
        for net in non_power_nets
        if any(token in net for token in ("PWM", "INA", "INB", "ENA", "ENB", "TX", "RX", "SCL", "SDA", "SWD", "RST", "CAN"))
    }
    if power_nets and not non_power_nets:
        if any((_infer_nominal_voltage(net) or 0.0) >= 9.0 or _is_source_like_power_net(net) for net in power_nets):
            return "power_input"
        return "power_link"
    if power_nets and len(control_like_nets) >= 2:
        return "control_harness"
    if any(token in text for token in ("LIPO", "BAT", "BATTERY", "POWER_IN", "BAT_IN", "VIN", "XT30", "XT60")):
        return "power_input"
    if any(token in text for token in ("MOTOR", "SERVO", "ESC", "PHASE", "FAN", "PUMP")):
        return "actuation"
    if any(token in text for token in ("IMU", "SENSOR", "GYRO", "ENCODER")):
        return "sensor_link"
    if any(token in text for token in ("DEBUG", "SWD", "UART", "USB", "PROG", "PROGRAM", "ISP")):
        return "debug_link"
    if interface_names & {"uart", "i2c", "spi", "swd", "usb2"}:
        return "board_link"
    if any(net.startswith(("VBAT", "VIN", "+12V", "+24V", "/M_V+", "/BOT_V+")) for net in nets):
        return "power_input"
    if any(is_power_net(net) for net in nets):
        return "power_link"
    return "generic"


def _build_passives(components: Dict[str, Dict[str, Any]], pinmap: Dict[str, Dict[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    resistors: List[Dict[str, Any]] = []
    capacitors: List[Dict[str, Any]] = []
    for ref, meta in (components or {}).items():
        pins = pinmap.get(ref) or {}
        if len(pins) < 2:
            continue
        ordered_pins = sorted(pins.keys())
        n1 = _normalize_net(pins[ordered_pins[0]])
        n2 = _normalize_net(pins[ordered_pins[1]])
        value = str(meta.get("value") or "").strip()
        if ref.upper().startswith("R"):
            ohms = parse_resistance_ohms(value)
            if ohms is not None and ohms > 0:
                resistors.append({"ref": ref, "ohms": float(ohms), "n1": n1, "n2": n2})
        elif ref.upper().startswith("C"):
            capacitors.append({"ref": ref, "value": value, "n1": n1, "n2": n2})
    return resistors, capacitors


def _rail_records(
    nets: Dict[str, Dict[str, Any]],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
) -> List[Dict[str, Any]]:
    connector_refs = {ref for ref, category in category_by_ref.items() if category == "connector"}
    rails: List[Dict[str, Any]] = []
    for net_name, net_data in (nets or {}).items():
        normalized = _normalize_net(net_name)
        if not is_power_net(normalized):
            continue
        component_refs = sorted({str(node.get("ref")) for node in net_data.get("nodes", []) or [] if node.get("ref")})
        connector_refs_on_net = sorted(ref for ref in component_refs if ref in connector_refs)
        consumer_refs = sorted(
            ref
            for ref in component_refs
            if category_by_ref.get(ref) not in {"connector", "capacitor", "resistor", "inductor", "diode", None}
        )
        rails.append(
            {
                "net": normalized,
                "nominal_v": _infer_nominal_voltage(normalized),
                "node_count": len(net_data.get("nodes", []) or []),
                "connector_refs": connector_refs_on_net,
                "consumer_refs": consumer_refs,
                "is_input_root": normalized.upper() in {"VIN", "VBAT", "VBUS", "VUSB", "+12V", "+24V"} or normalized.upper().startswith("VIN"),
            }
        )
    rails.sort(key=lambda row: (row.get("nominal_v") is None, row.get("nominal_v") or 999.0, row["net"]))
    return rails


def _regulator_rows(
    components: Dict[str, Dict[str, Any]],
    ref_nets: Dict[str, Set[str]],
    ground_net: str,
    category_by_ref: Dict[str, str],
) -> List[Dict[str, Any]]:
    inferred = infer_ldo_candidates(components, ref_nets, ground_net)
    rows: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for entry in inferred:
        ref = str(entry.get("name") or "").strip()
        if not ref or ref in seen:
            continue
        rows.append(
            {
                "ref": ref,
                "kind": "ldo_like",
                "vin_net": _normalize_net(str(entry.get("vin_net") or "")),
                "vout_net": _normalize_net(str(entry.get("vout_net") or "")),
                "gnd_net": _normalize_net(str(entry.get("gnd_net") or "")),
                "vout_nominal_v": entry.get("vout_nom_v"),
                "confidence": 0.72,
                "note": entry.get("note") or "",
            }
        )
        seen.add(ref)

    for ref, meta in (components or {}).items():
        if ref in seen:
            continue
        if _component_category(ref, meta if isinstance(meta, dict) else {}) != "regulator":
            continue
        nets = sorted({_normalize_net(net) for net in (ref_nets.get(ref) or set()) if _normalize_net(net) and not is_ground_net(net)})
        power_nets = sorted({net for net in nets if is_power_net(net) or _is_source_like_power_net(net)})
        if len(power_nets) < 2:
            continue
        ranked = sorted(
            power_nets,
            key=lambda net: (
                0 if _is_source_like_power_net(net) else 1,
                _infer_nominal_voltage(net) is None,
                -(_infer_nominal_voltage(net) or 0.0),
                net,
            ),
        )
        vin_net = ranked[0]
        vout_candidates = sorted(
            power_nets,
            key=lambda net: (
                1 if net == vin_net else 0,
                _infer_nominal_voltage(net) is None,
                (_infer_nominal_voltage(net) or 999.0),
                net,
            ),
        )
        vout_net = next((net for net in vout_candidates if net != vin_net), None)
        if not vout_net:
            continue
        rows.append(
            {
                "ref": ref,
                "kind": "regulator_like",
                "vin_net": vin_net,
                "vout_net": vout_net,
                "gnd_net": _normalize_net(ground_net),
                "vout_nominal_v": _infer_nominal_voltage(vout_net),
                "confidence": 0.66,
                "note": "inferred from regulator-class component spanning multiple power nets",
            }
        )
        seen.add(ref)

    existing_outputs = {_normalize_net(str(row.get("vout_net") or "")) for row in rows}
    for ref, meta in (components or {}).items():
        if ref in seen or category_by_ref.get(ref) != "mcu":
            continue
        text = f"{str(meta.get('value') or '').upper()} {str(meta.get('footprint') or '').upper()}"
        if not any(token in text for token in ("TINYPICO", "PICO", "NODEMCU", "DEVKIT", "FEATHER", "HUZZAH32")):
            continue
        nets = sorted({_normalize_net(net) for net in (ref_nets.get(ref) or set()) if _normalize_net(net) and not is_ground_net(net)})
        source_nets = sorted(
            {net for net in nets if _is_source_like_power_net(net) or ((is_power_net(net) and (_infer_nominal_voltage(net) or 0.0) >= 4.5))},
            key=lambda net: (
                0 if _is_source_like_power_net(net) else 1,
                _infer_nominal_voltage(net) is None,
                -(_infer_nominal_voltage(net) or 0.0),
                net,
            ),
        )
        low_rails = sorted(
            {net for net in nets if is_power_net(net) and (_infer_nominal_voltage(net) or 99.0) <= 3.6 and _normalize_net(net) not in existing_outputs},
            key=lambda net: ((_infer_nominal_voltage(net) or 99.0), net),
        )
        if not source_nets or not low_rails:
            continue
        rows.append(
            {
                "ref": ref,
                "kind": "module_regulator",
                "vin_net": source_nets[0],
                "vout_net": low_rails[0],
                "gnd_net": _normalize_net(ground_net),
                "vout_nominal_v": _infer_nominal_voltage(low_rails[0]),
                "confidence": 0.58,
                "note": "inferred from dev-module board exposing both upstream power and an onboard low-voltage rail",
            }
        )
        seen.add(ref)
    return rows


def _role_scores(category_counts: Dict[str, int], connectors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = defaultdict(float)
    if category_counts.get("mcu", 0):
        scores["controller"] += 4.0
    if category_counts.get("gate_driver", 0) >= 2:
        scores["motor_control"] += 3.8
    if category_counts.get("current_sense_amp", 0) >= 2:
        scores["motor_control"] += 1.4
    if category_counts.get("sensor", 0):
        scores["sensor_io"] += 2.0 if not category_counts.get("mcu", 0) else 1.0
    if category_counts.get("regulator", 0) or category_counts.get("power", 0):
        scores["power_board"] += 3.0 if not category_counts.get("mcu", 0) else 1.0
    if category_counts.get("motor_driver", 0):
        scores["motor_control"] += 3.5
    if category_counts.get("radio", 0):
        scores["communications"] += 2.5
    if category_counts.get("transceiver", 0) and len(connectors) >= 2:
        scores["interface_board"] += 2.0
    if len(connectors) >= 3 and not category_counts.get("mcu", 0):
        scores["breakout"] += 1.5
    ranked = [{"role": role, "score": round(score, 2)} for role, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if score > 0]
    return ranked[:3]


def _board_questions(
    primary_role: str,
    connectors: List[Dict[str, Any]],
    regulators: List[Dict[str, Any]],
    interface_hits: Dict[str, int],
) -> List[str]:
    questions: List[str] = []
    if connectors and not interface_hits:
        questions.append("Connector components were found, but no common bus/interface signatures were extracted.")
    if primary_role == "controller" and not any(name in interface_hits for name in ("usb2", "uart", "swd")):
        questions.append("Controller-like board has no obvious programming or debug interface extracted.")
    if primary_role in {"controller", "sensor_io"} and not regulators:
        questions.append("No regulator relationship was extracted; confirm how low-voltage rails are generated.")
    if not connectors:
        questions.append("No explicit connector components were extracted; system-level integration may be incomplete.")
    return questions


def extract_board_structure(design_path: str, *, board_id: Optional[str] = None, board_name: Optional[str] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    path = Path(design_path)
    if not path.exists():
        raise FileNotFoundError(f"design path not found: {path}")

    components, pinmap, nets = _load_components_pinmap_and_nets(path, kind=kind)
    ground_net = guess_ground_net(nets) or "0"
    ref_nets: Dict[str, Set[str]] = {ref: {_normalize_net(net) for net in pins.values() if _normalize_net(net)} for ref, pins in pinmap.items()}
    category_by_ref = {ref: _component_category(ref, meta if isinstance(meta, dict) else {}) for ref, meta in components.items()}
    category_counts: Dict[str, int] = defaultdict(int)
    for category in category_by_ref.values():
        category_counts[category] += 1

    rails = _rail_records(nets, pinmap, category_by_ref)
    resistors, capacitors = _build_passives(components, pinmap)
    evidence_findings = infer_common_interface_facts(
        resistors=[
            type("ParsedResistor", (), resistor)()  # lightweight duck typing for existing helper
            for resistor in resistors
        ],
        capacitors=[
            type("ParsedCapacitor", (), capacitor)()
            for capacitor in capacitors
        ],
        rails=[row["net"] for row in rails],
    )
    regulators = _regulator_rows(components, ref_nets, ground_net, category_by_ref)

    connectors: List[Dict[str, Any]] = []
    interface_hits: Dict[str, int] = defaultdict(int)
    for ref, meta in components.items():
        if category_by_ref.get(ref) != "connector":
            continue
        pins = pinmap.get(ref) or {}
        pin_nets = {pin: _normalize_net(net) for pin, net in pins.items() if _normalize_net(net)}
        interfaces = _connector_interfaces(pin_nets)
        for row in interfaces:
            interface_hits[str(row.get("interface") or "")] += 1
        connectors.append(
            {
                "ref": ref,
                "value": meta.get("value") or "",
                "footprint": meta.get("footprint") or "",
                "pin_nets": pin_nets,
                "power_nets": sorted(net for net in set(pin_nets.values()) if is_power_net(net)),
                "interfaces": interfaces,
                "semantic_role": _connector_semantic_role(
                    value=str(meta.get("value") or ""),
                    footprint=str(meta.get("footprint") or ""),
                    pin_nets=pin_nets,
                    interfaces=interfaces,
                ),
            }
        )
    connectors.sort(key=lambda row: row["ref"])

    active_components: List[Dict[str, Any]] = []
    for ref, meta in components.items():
        category = category_by_ref.get(ref, "other")
        if category in {"connector", "resistor", "capacitor", "inductor", "diode", "transistor", "other"}:
            continue
        active_components.append(
            {
                "ref": ref,
                "category": category,
                "value": meta.get("value") or "",
                "footprint": meta.get("footprint") or "",
                "nets": sorted(ref_nets.get(ref) or []),
            }
        )
    active_components.sort(key=lambda row: row["ref"])

    roles = _role_scores(dict(category_counts), connectors)
    primary_role = roles[0]["role"] if roles else "board"
    questions = _board_questions(primary_role, connectors, regulators, interface_hits)
    controller_runtime = analyze_controller_runtime(
        board_id=board_id or path.stem,
        components=components,
        pinmap=pinmap,
        category_by_ref=category_by_ref,
        connectors=connectors,
        rails=rails,
        regulators=regulators,
        resistors=resistors,
    )
    power_control = analyze_power_control(
        components=components,
        ref_nets=ref_nets,
        category_by_ref=category_by_ref,
        rails=rails,
        regulators=regulators,
        connectors=connectors,
        active_components=active_components,
        resistors=resistors,
        capacitors=capacitors,
        primary_role=primary_role,
    )
    if controller_runtime.get("programming_paths"):
        questions = [
            question
            for question in questions
            if question != "Controller-like board has no obvious programming or debug interface extracted."
        ]
    questions.extend(controller_runtime.get("firmware_readiness", {}).get("warnings") or [])
    questions.extend(power_control.get("questions") or [])

    return {
        "board_id": board_id or path.stem,
        "board_name": board_name or path.stem,
        "source": {"path": str(path), "kind": kind or path.suffix.lstrip(".")},
        "summary": {
            "component_count": len(components),
            "connector_count": len(connectors),
            "power_rail_count": len(rails),
            "active_component_count": len(active_components),
        },
        "ground_net": _normalize_net(ground_net),
        "roles": roles,
        "primary_role": primary_role,
        "connectors": connectors,
        "power": {
            "rails": rails,
            "regulators": regulators,
            "findings": evidence_findings,
        },
        "active_components": active_components,
        "categories": dict(sorted(category_counts.items())),
        "controller_runtime": controller_runtime,
        "power_control_analysis": power_control,
        "bring_up_plan": controller_runtime.get("bring_up_plan") or [],
        "questions": sorted(dict.fromkeys(question for question in questions if question)),
    }


def _shared_interface_rows(board_a: Dict[str, Any], board_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    connectors_a = board_a.get("connectors") or []
    connectors_b = board_b.get("connectors") or []
    for conn_a in connectors_a:
        by_interface_a = {row["interface"]: row for row in (conn_a.get("interfaces") or []) if row.get("interface") != "power"}
        for conn_b in connectors_b:
            by_interface_b = {row["interface"]: row for row in (conn_b.get("interfaces") or []) if row.get("interface") != "power"}
            for interface in sorted(set(by_interface_a.keys()) & set(by_interface_b.keys())):
                sig_a = set(by_interface_a[interface].get("signals") or [])
                sig_b = set(by_interface_b[interface].get("signals") or [])
                shared = sorted(sig_a & sig_b)
                if len(shared) < 2:
                    continue
                confidence = min(
                    0.55
                    + 0.08 * len(shared)
                    + 0.05 * min(by_interface_a[interface].get("confidence", 0.0), by_interface_b[interface].get("confidence", 0.0)),
                    0.97,
                )
                rows.append(
                    {
                        "from_board": board_a.get("board_id"),
                        "to_board": board_b.get("board_id"),
                        "from_connector": conn_a.get("ref"),
                        "to_connector": conn_b.get("ref"),
                        "interface": interface,
                        "signals": shared,
                        "confidence": round(confidence, 2),
                        "notes": f"Matched {interface} signal set across {conn_a.get('ref')} and {conn_b.get('ref')}.",
                    }
                )
    deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row["from_board"]), str(row["to_board"]), str(row["interface"]))
        existing = deduped.get(key)
        if existing is None or row["confidence"] > existing["confidence"]:
            deduped[key] = row
    return list(deduped.values())


def _power_source_score(board: Dict[str, Any], rail_name: str, nominal_v: Optional[float]) -> float:
    score = 0.0
    primary_role = str(board.get("primary_role") or "")
    role_weights = {
        "power_board": 3.0,
        "controller": 1.8,
        "interface_board": 1.5,
        "motor_control": 0.9,
        "sensor_io": 0.6,
    }
    score += role_weights.get(primary_role, 0.2)
    for regulator in board.get("power", {}).get("regulators", []) or []:
        if _normalize_net(str(regulator.get("vout_net") or "")) == _normalize_net(rail_name):
            score += 2.5
    for rail in board.get("power", {}).get("rails", []) or []:
        if _normalize_net(str(rail.get("net") or "")) != _normalize_net(rail_name):
            continue
        if rail.get("is_input_root"):
            score += 1.5
        if nominal_v is not None and rail.get("nominal_v") == nominal_v:
            score += 0.5
    for connector in board.get("connectors") or []:
        if _normalize_net(rail_name) not in {_normalize_net(net) for net in (connector.get("power_nets") or [])}:
            continue
        score += 0.2
        semantic_role = str(connector.get("semantic_role") or "")
        if semantic_role == "power_input":
            score += 1.2 if _is_source_like_power_net(rail_name) or ((nominal_v or 0.0) >= 9.0) else 0.1
        elif semantic_role in {"board_link", "debug_link"}:
            score += 0.6
        elif semantic_role == "control_harness":
            score += 0.1
        elif semantic_role == "actuation":
            score -= 0.15
    return score


def _prune_power_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, Optional[float]], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("board_id") or ""), _normalize_net(str(row.get("rail") or "")), row.get("voltage_v"))
        existing = grouped.get(key)
        if existing is None or float(row.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
            grouped[key] = row
    return sorted(grouped.values(), key=lambda row: (str(row.get("board_id") or ""), str(row.get("rail") or ""), -float(row.get("confidence") or 0.0)))


def _board_locally_generates_rail(board: Dict[str, Any], rail_name: str, nominal_v: Optional[float]) -> bool:
    target = _normalize_net(rail_name)
    for regulator in board.get("power", {}).get("regulators", []) or []:
        vout = _normalize_net(str(regulator.get("vout_net") or ""))
        if target and vout == target:
            return True
        reg_v = regulator.get("vout_nominal_v")
        if nominal_v is not None and reg_v is not None and abs(float(reg_v) - nominal_v) <= 0.05:
            return True
    return False


def _shared_power_rows(
    board_a: Dict[str, Any],
    board_b: Dict[str, Any],
    interface_rows: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    rows: List[Dict[str, Any]] = []
    questions: List[str] = []
    power_nets_a: Dict[str, Optional[float]] = {}
    power_nets_b: Dict[str, Optional[float]] = {}

    for connector in board_a.get("connectors") or []:
        for net_name in connector.get("power_nets") or []:
            power_nets_a[_normalize_net(str(net_name))] = _infer_nominal_voltage(str(net_name))
    for connector in board_b.get("connectors") or []:
        for net_name in connector.get("power_nets") or []:
            power_nets_b[_normalize_net(str(net_name))] = _infer_nominal_voltage(str(net_name))

    exact_matches = sorted(set(power_nets_a.keys()) & set(power_nets_b.keys()))
    voltage_matches: List[Tuple[str, str, float]] = []
    for net_a, voltage_a in power_nets_a.items():
        if voltage_a is None:
            continue
        for net_b, voltage_b in power_nets_b.items():
            if voltage_b is None or abs(voltage_a - voltage_b) > 0.05:
                continue
            voltage_matches.append((net_a, net_b, voltage_a))

    considered = {(net_name, net_name) for net_name in exact_matches}
    for net_name in exact_matches:
        nominal_v = power_nets_a.get(net_name) or power_nets_b.get(net_name)
        if _board_locally_generates_rail(board_a, net_name, nominal_v) and _board_locally_generates_rail(board_b, net_name, nominal_v):
            questions.append(
                f"Both {board_a.get('board_id')} and {board_b.get('board_id')} appear to generate {net_name} locally; cross-board sourcing is likely not required."
            )
            continue
        score_a = _power_source_score(board_a, net_name, nominal_v)
        score_b = _power_source_score(board_b, net_name, nominal_v)
        if score_a == score_b:
            if not interface_rows:
                continue
            questions.append(
                f"Both {board_a.get('board_id')} and {board_b.get('board_id')} expose {net_name}; source direction is ambiguous."
            )
            continue
        source_board = board_a if score_a > score_b else board_b
        sink_board = board_b if source_board is board_a else board_a
        rows.append(
            {
                "source": f"{source_board.get('board_id')}:{net_name}",
                "board_id": sink_board.get("board_id"),
                "rail": net_name,
                "voltage_v": nominal_v,
                "confidence": round(0.65 + min(abs(score_a - score_b), 2.0) * 0.1, 2),
                "notes": f"Shared power rail extracted on connectors of {board_a.get('board_id')} and {board_b.get('board_id')}.",
            }
        )

    for net_a, net_b, nominal_v in voltage_matches:
        if (net_a, net_b) in considered or (net_b, net_a) in considered:
            continue
        if not interface_rows:
            continue
        if _board_locally_generates_rail(board_a, net_a, nominal_v) and _board_locally_generates_rail(board_b, net_b, nominal_v):
            continue
        score_a = _power_source_score(board_a, net_a, nominal_v)
        score_b = _power_source_score(board_b, net_b, nominal_v)
        if score_a == score_b:
            continue
        source_board = board_a if score_a > score_b else board_b
        sink_board = board_b if source_board is board_a else board_a
        rail_name = net_a if source_board is board_a else net_b
        rows.append(
            {
                "source": f"{source_board.get('board_id')}:{rail_name}",
                "board_id": sink_board.get("board_id"),
                "rail": net_b if sink_board is board_b else net_a,
                "voltage_v": nominal_v,
                "confidence": round(0.6 + min(abs(score_a - score_b), 2.0) * 0.08, 2),
                "notes": f"Matched connector power rails by nominal voltage ({nominal_v:.1f}V).",
            }
        )
        considered.add((net_a, net_b))

    deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row["source"]), str(row["board_id"]), str(row["rail"]))
        existing = deduped.get(key)
        if existing is None or row["confidence"] > existing["confidence"]:
            deduped[key] = row
    return list(deduped.values()), questions


def _motor_control_pack(
    boards: List[Dict[str, Any]],
    interconnects: List[Dict[str, Any]],
    power_tree: List[Dict[str, Any]],
    bring_up_sequence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    actuation_boards: List[Dict[str, Any]] = []
    questions: List[str] = []
    totals = {
        "motor_driver_count": 0,
        "gate_driver_count": 0,
        "current_sense_amp_count": 0,
        "actuation_connector_count": 0,
    }

    for board in boards:
        if not isinstance(board, dict):
            continue
        analysis = board.get("power_control_analysis") or {}
        summary = analysis.get("summary") or {}
        role = str(board.get("primary_role") or "")
        is_actuation = role == "motor_control" or any(
            int(summary.get(key) or 0) > 0 for key in ("motor_driver_count", "gate_driver_count")
        )
        if not is_actuation:
            continue
        board_row = {
            "board_id": board.get("board_id"),
            "role": role,
            "runtime_role": ((board.get("controller_runtime") or {}).get("firmware_surface") or {}).get("runtime_role"),
            "motor_driver_count": int(summary.get("motor_driver_count") or 0),
            "gate_driver_count": int(summary.get("gate_driver_count") or 0),
            "current_sense_amp_count": int(summary.get("current_sense_amp_count") or 0),
            "actuation_connector_count": int(summary.get("actuation_connector_count") or 0),
        }
        actuation_boards.append(board_row)
        for key in totals:
            totals[key] += int(board_row.get(key) or 0)
        questions.extend(str(question) for question in (analysis.get("questions") or []) if question)
        for finding in (analysis.get("risk_findings") or []):
            topic = str(finding.get("topic") or "")
            if topic in {"phase_current_feedback", "motor_supply_headroom", "actuation_outputs", "current_sense"}:
                message = str(finding.get("message") or "").strip()
                if message:
                    questions.append(message)

    actuation_ids = {str(row.get("board_id") or "") for row in actuation_boards if row.get("board_id")}
    control_links = [
        row
        for row in (interconnects or [])
        if str(row.get("from_board") or "") in actuation_ids or str(row.get("to_board") or "") in actuation_ids
    ]
    power_feeds = [row for row in (power_tree or []) if str(row.get("board_id") or "") in actuation_ids]
    bring_up_focus = [row for row in (bring_up_sequence or []) if str(row.get("board_id") or "") in actuation_ids]

    if actuation_boards and not power_feeds:
        questions.append("Actuation-capable boards were extracted, but no supporting machine power feed was inferred.")
    if actuation_boards and len(actuation_boards) > 1 and not control_links:
        questions.append("Several actuation boards were extracted, but no inter-board control link was recovered.")

    if not actuation_boards:
        status = "not_applicable"
        topology = "none"
    elif power_feeds and (control_links or len(actuation_boards) == 1):
        status = "integrated"
        topology = "distributed_motor_control" if len(actuation_boards) > 1 else "single_motor_control"
    else:
        status = "partial"
        topology = "distributed_motor_control" if len(actuation_boards) > 1 else "single_motor_control"

    return {
        "status": status,
        "topology": topology,
        "actuation_boards": actuation_boards,
        "control_links": control_links,
        "power_feeds": power_feeds,
        "bring_up_focus": bring_up_focus,
        "totals": totals,
        "questions": sorted(dict.fromkeys(question for question in questions if question)),
    }


def synthesize_machine_topology(board_structures: Iterable[Dict[str, Any]], *, machine_name: str = "auto_machine") -> Dict[str, Any]:
    boards = [board for board in board_structures if isinstance(board, dict)]
    machine_boards = [
        {
            "board_id": board.get("board_id"),
            "name": board.get("board_name") or board.get("board_id"),
            "role": board.get("primary_role"),
        }
        for board in boards
    ]
    interconnects: List[Dict[str, Any]] = []
    power_tree_candidates: List[Dict[str, Any]] = []
    questions: List[str] = []
    graph_edges: List[Dict[str, Any]] = []

    for board_a, board_b in combinations(boards, 2):
        interface_rows = _shared_interface_rows(board_a, board_b)
        interconnects.extend(interface_rows)
        for row in interface_rows:
            graph_edges.append(
                {
                    "from_board": row["from_board"],
                    "to_board": row["to_board"],
                    "kind": row["interface"],
                    "confidence": row["confidence"],
                }
            )
        power_rows, power_questions = _shared_power_rows(board_a, board_b, interface_rows=interface_rows)
        power_tree_candidates.extend(power_rows)
        questions.extend(power_questions)

    power_tree = _prune_power_candidates(power_tree_candidates)
    for row in power_tree:
        graph_edges.append(
            {
                "from_board": str(row["source"]).split(":", 1)[0],
                "to_board": row["board_id"],
                "kind": "power",
                "confidence": row["confidence"],
            }
        )

    connected_board_ids = {edge["from_board"] for edge in graph_edges} | {edge["to_board"] for edge in graph_edges}
    for board in boards:
        if board.get("board_id") not in connected_board_ids and len(boards) > 1:
            questions.append(f"No strong inter-board match was extracted for {board.get('board_id')}; connector intent may need manual confirmation.")

    machine_payload = {
        "machine_name": machine_name,
        "boards": machine_boards,
        "interconnects": interconnects,
        "power_tree": power_tree,
    }
    compiled_preview = compile_machine_requirements(machine_payload)
    board_by_id = {str(board.get("board_id")): board for board in boards if board.get("board_id")}
    incoming_power: Dict[str, int] = defaultdict(int)
    for row in power_tree:
        sink = str(row.get("board_id") or "")
        if sink:
            incoming_power[sink] += 1
    bring_up_order = sorted(
        [str(board.get("board_id")) for board in boards if board.get("board_id")],
        key=lambda bid: (
            incoming_power.get(bid, 0),
            0 if str((board_by_id.get(bid) or {}).get("primary_role") or "") in {"power_board", "controller"} else 1,
            bid,
        ),
    )
    machine_bring_up_sequence = []
    for order, board_id in enumerate(bring_up_order, start=1):
        board = board_by_id.get(board_id) or {}
        first_steps = [step.get("title") for step in (board.get("bring_up_plan") or [])[:3] if isinstance(step, dict) and step.get("title")]
        machine_bring_up_sequence.append(
            {
                "order": order,
                "board_id": board_id,
                "role": board.get("primary_role"),
                "first_steps": first_steps,
            }
        )
    motor_control_pack = _motor_control_pack(boards, interconnects, power_tree, machine_bring_up_sequence)
    return {
        "machine": {
            "machine_name": machine_name,
            "board_count": len(boards),
            "candidate_interconnect_count": len(interconnects),
            "candidate_power_link_count": len(power_tree),
        },
        "boards": boards,
        "candidate_interconnects": interconnects,
        "candidate_power_tree": power_tree,
        "system_graph": {
            "nodes": [{"board_id": board.get("board_id"), "role": board.get("primary_role")} for board in boards],
            "edges": graph_edges,
        },
        "questions": sorted(set(questions + list((compiled_preview.get("system") or {}).get("questions") or []))),
        "machine_payload": machine_payload,
        "compiled_preview": compiled_preview,
        "machine_bring_up_sequence": machine_bring_up_sequence,
        "motor_control_pack": motor_control_pack,
    }
