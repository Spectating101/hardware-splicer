from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def _module_path() -> Path:
    return Path(__file__).resolve().parents[1] / "intelligence" / "pinout_database.py"


@lru_cache(maxsize=1)
def _load_pinout_runtime() -> Tuple[Any, Any]:
    pinout_path = _module_path()
    spec = importlib.util.spec_from_file_location("circuit_ai_light_pinout_database", pinout_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load pinout database: {pinout_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.pinout_database, module.PinType


def _get_pinout(value: str) -> Optional[Any]:
    pinout_db, _ = _load_pinout_runtime()
    if not value:
        return None
    value_text = str(value).strip()
    pinout = pinout_db.get_pinout(value_text)
    if pinout:
        return pinout
    return pinout_db.search_by_component_name(value_text)


def _is_power_net(net: str) -> bool:
    up = (net or "").strip().upper().lstrip("/")
    for suffix in ("_RAIL", "-RAIL"):
        if up.endswith(suffix):
            up = up[: -len(suffix)]
    return (
        up.startswith(("VIN", "VBAT", "VBUS", "VUSB", "VDD", "VCC", "+"))
        or up.endswith("V+")
        or up.endswith("V-")
        or bool(re.search(r"(^|[_/\-+])(\+?\d+V\d*|V(?:BUS|BAT|USB|CC|DD|IN|REF))($|[_/\-+])", up))
    )


def _normalize_net(net: str) -> str:
    if not net:
        return ""
    stripped = net.strip()
    up = stripped.upper()
    if up in {"GND", "GNDPWR", "PGND", "AGND", "0"}:
        return "0"
    return stripped


def _role_tags(pin: Any) -> Set[str]:
    tags: Set[str] = set()
    text = " ".join(
        [
            str(getattr(pin, "pin_name", "") or ""),
            str(getattr(pin, "description", "") or ""),
            " ".join(getattr(pin, "alternate_functions", []) or []),
            " ".join(getattr(pin, "typical_connections", []) or []),
        ]
    ).upper()
    pin_type = str(getattr(getattr(pin, "pin_type", None), "value", "") or "").lower()

    if "GND" in text or pin_type == "ground":
        tags.add("GROUND")
    if "VCC" in text or "VDD" in text or "3V3" in text or "VIN" in text or "VOUT" in text or pin_type == "power":
        tags.add("POWER")
    if "TXD" in text or "UART TRANSMIT" in text or "UART TX" in text or "USB SERIAL RX" in text:
        tags.add("UART_TX")
    if "RXD" in text or "UART RECEIVE" in text or "UART RX" in text or "USB SERIAL TX" in text:
        tags.add("UART_RX")
    if "SDA" in text:
        tags.add("I2C_SDA")
    if "SCL" in text:
        tags.add("I2C_SCL")
    if "MOSI" in text:
        tags.add("SPI_MOSI")
    if "MISO" in text:
        tags.add("SPI_MISO")
    if "SCK" in text or "SPI CLOCK" in text:
        tags.add("SPI_SCK")
    if "SS" in text or "CS" in text or "NSS" in text:
        tags.add("SPI_CS")
    if "D+" in text or "USBDP" in text or "UD+" in text:
        tags.add("USB_DP")
    if "D-" in text or "USBDM" in text or "UD-" in text:
        tags.add("USB_DM")
    if "DTR" in text:
        tags.add("DTR")
    if "RTS" in text:
        tags.add("RTS")
    if "RESET" in text or "RST" in text:
        tags.add("RESET")
    if "EN" in text or "CH_PD" in text or "CHIP ENABLE" in text:
        tags.add("ENABLE")
    if "BOOT" in text or "FLASH MODE" in text:
        tags.add("BOOT")
    if "GPIO0" in text:
        tags.add("BOOT_GPIO0")
    if "GPIO2" in text:
        tags.add("BOOT_GPIO2")
    if "GPIO15" in text:
        tags.add("BOOT_GPIO15")
    if "XTAL" in text or "CRYSTAL" in text:
        tags.add("CLOCK")
    if "ADC" in text:
        tags.add("ANALOG")
    return tags


def _component_kind(part_number: str) -> str:
    up = (part_number or "").upper()
    if up.startswith(("ESP32", "ESP8266", "ATMEGA", "STM32", "RP2040", "ATSAMD", "GD32", "CH32", "PIC")):
        return "controller"
    if up.startswith(("CP210", "CH340", "FT232", "ATMEGA16U2")):
        return "usb_uart_bridge"
    if up.startswith(("AMS1117", "LM7805", "LM1117", "AP2112")):
        return "regulator"
    if up.startswith(("W25Q", "MX25")):
        return "flash_memory"
    return "known_ic"


def _build_bias_maps(resistors: Iterable[Dict[str, Any]]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    pullups: Dict[str, List[Dict[str, Any]]] = {}
    pulldowns: Dict[str, List[Dict[str, Any]]] = {}
    for row in resistors:
        try:
            ohms = float(row.get("ohms") or 0.0)
        except Exception:
            ohms = 0.0
        if not (1000.0 <= ohms <= 100000.0):
            continue
        n1 = _normalize_net(str(row.get("n1") or ""))
        n2 = _normalize_net(str(row.get("n2") or ""))
        ref = str(row.get("ref") or "")
        entry = {"ref": ref, "ohms": ohms}
        if _is_power_net(n1) and n2 not in {"", "0"}:
            pullups.setdefault(n2, []).append({**entry, "rail": n1})
        elif _is_power_net(n2) and n1 not in {"", "0"}:
            pullups.setdefault(n1, []).append({**entry, "rail": n2})
        if n1 == "0" and n2 not in {"", "0"}:
            pulldowns.setdefault(n2, []).append(entry)
        elif n2 == "0" and n1 not in {"", "0"}:
            pulldowns.setdefault(n1, []).append(entry)
    return pullups, pulldowns


def _pin_instance_rows(part_number: str, ref: str, pinmap: Dict[str, str]) -> List[Dict[str, Any]]:
    pinout = _get_pinout(part_number)
    if not pinout:
        return []
    rows: List[Dict[str, Any]] = []
    for pin in pinout.pins:
        net = pinmap.get(str(pin.pin_number))
        if not net:
            continue
        rows.append(
            {
                "pin_number": pin.pin_number,
                "pin_name": pin.pin_name,
                "net": _normalize_net(net),
                "tags": sorted(_role_tags(pin)),
                "critical": bool(getattr(pin, "critical", False)),
                "description": getattr(pin, "description", "") or "",
            }
        )
    return rows


def _connector_net_lookup(connectors: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    lookup: Dict[str, List[Dict[str, Any]]] = {}
    for connector in connectors or []:
        for pin, net in (connector.get("pin_nets") or {}).items():
            normalized = _normalize_net(str(net))
            if not normalized:
                continue
            lookup.setdefault(normalized, []).append(
                {
                    "ref": connector.get("ref"),
                    "pin": pin,
                    "interfaces": [row.get("interface") for row in (connector.get("interfaces") or [])],
                }
            )
    return lookup


def _find_mcu_instances(
    components: Dict[str, Dict[str, Any]],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ref, meta in (components or {}).items():
        if category_by_ref.get(ref) != "mcu":
            continue
        part_number = str(meta.get("value") or "").strip()
        pin_rows = _pin_instance_rows(part_number, ref, pinmap.get(ref) or {})
        rows.append(
            {
                "ref": ref,
                "part_number": part_number,
                "kind": _component_kind(part_number),
                "pins": pin_rows,
            }
        )
    return rows


def _find_known_support_instances(
    components: Dict[str, Dict[str, Any]],
    pinmap: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ref, meta in (components or {}).items():
        part_number = str(meta.get("value") or "").strip()
        pinout = _get_pinout(part_number)
        if not pinout:
            continue
        kind = _component_kind(pinout.part_number)
        if kind == "controller":
            continue
        rows.append(
            {
                "ref": ref,
                "part_number": pinout.part_number,
                "kind": kind,
                "pins": _pin_instance_rows(pinout.part_number, ref, pinmap.get(ref) or {}),
            }
        )
    return rows


def _tag_nets(pin_rows: Iterable[Dict[str, Any]], tag: str) -> Set[str]:
    return {row["net"] for row in pin_rows if tag in (row.get("tags") or []) and row.get("net")}


def _bridge_programming_paths(
    mcu: Dict[str, Any],
    support_parts: Iterable[Dict[str, Any]],
    connector_lookup: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    paths: List[Dict[str, Any]] = []
    mcu_pins = mcu.get("pins") or []
    mcu_tx = _tag_nets(mcu_pins, "UART_TX")
    mcu_rx = _tag_nets(mcu_pins, "UART_RX")
    if not (mcu_tx and mcu_rx):
        return paths

    for part in support_parts:
        if part.get("kind") != "usb_uart_bridge":
            continue
        pins = part.get("pins") or []
        bridge_tx = _tag_nets(pins, "UART_TX")
        bridge_rx = _tag_nets(pins, "UART_RX")
        usb_dp = _tag_nets(pins, "USB_DP")
        usb_dm = _tag_nets(pins, "USB_DM")
        if not (mcu_tx & bridge_rx and mcu_rx & bridge_tx):
            continue
        usb_exposed = bool(usb_dp and usb_dm and any(net in connector_lookup for net in usb_dp | usb_dm))
        paths.append(
            {
                "type": "usb_uart_bridge",
                "mcu_ref": mcu.get("ref"),
                "bridge_ref": part.get("ref"),
                "tx_net": sorted(mcu_tx & bridge_rx)[0],
                "rx_net": sorted(mcu_rx & bridge_tx)[0],
                "usb_connector_refs": sorted({row["ref"] for net in usb_dp | usb_dm for row in connector_lookup.get(net, [])}),
                "confidence": 0.95 if usb_exposed else 0.82,
            }
        )
    return paths


def _header_programming_paths(
    mcu: Dict[str, Any],
    connectors: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    paths: List[Dict[str, Any]] = []
    mcu_pins = mcu.get("pins") or []
    mcu_tx = _tag_nets(mcu_pins, "UART_TX")
    mcu_rx = _tag_nets(mcu_pins, "UART_RX")
    mcu_spi = {
        "mosi": _tag_nets(mcu_pins, "SPI_MOSI"),
        "miso": _tag_nets(mcu_pins, "SPI_MISO"),
        "sck": _tag_nets(mcu_pins, "SPI_SCK"),
        "cs": _tag_nets(mcu_pins, "SPI_CS"),
        "reset": _tag_nets(mcu_pins, "RESET"),
    }
    for connector in connectors or []:
        nets = {_normalize_net(net) for net in (connector.get("pin_nets") or {}).values() if _normalize_net(net)}
        interfaces = {row.get("interface") for row in (connector.get("interfaces") or [])}
        if mcu_tx & nets and mcu_rx & nets:
            paths.append(
                {
                    "type": "uart_header",
                    "mcu_ref": mcu.get("ref"),
                    "connector_ref": connector.get("ref"),
                    "nets": sorted((mcu_tx | mcu_rx) & nets),
                    "confidence": 0.85 if "usb2" not in interfaces else 0.7,
                }
            )
        if mcu_spi["mosi"] & nets and mcu_spi["miso"] & nets and mcu_spi["sck"] & nets and mcu_spi["reset"] & nets:
            paths.append(
                {
                    "type": "isp_header",
                    "mcu_ref": mcu.get("ref"),
                    "connector_ref": connector.get("ref"),
                    "nets": sorted((mcu_spi["mosi"] | mcu_spi["miso"] | mcu_spi["sck"] | mcu_spi["reset"]) & nets),
                    "confidence": 0.88,
                }
            )
        if {"SWDIO", "SWCLK"}.issubset({signal for row in (connector.get("interfaces") or []) for signal in (row.get("signals") or [])}):
            paths.append(
                {
                    "type": "swd_header",
                    "mcu_ref": mcu.get("ref"),
                    "connector_ref": connector.get("ref"),
                    "nets": sorted(nets),
                    "confidence": 0.9,
                }
            )
    return paths


def _boot_constraints(
    mcu: Dict[str, Any],
    pullups: Dict[str, List[Dict[str, Any]]],
    pulldowns: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    pins = mcu.get("pins") or []
    part_number = str(mcu.get("part_number") or "").upper()
    for pin in pins:
        tags = set(pin.get("tags") or [])
        net = _normalize_net(str(pin.get("net") or ""))
        if not net:
            continue
        expected = None
        severity = "info"
        if "ENABLE" in tags or "RESET" in tags:
            expected = "pull_up"
        if "BOOT_GPIO0" in tags:
            expected = "pull_up"
        if "BOOT_GPIO2" in tags:
            expected = "pull_up"
        if "BOOT_GPIO15" in tags:
            expected = "pull_down"
        if "BOOT" in tags and expected is None and "ESP" in part_number:
            expected = "pull_up"
        if expected is None:
            continue
        has_pullup = bool(pullups.get(net))
        has_pulldown = bool(pulldowns.get(net))
        status = "ok"
        if expected == "pull_up" and not has_pullup:
            status = "missing_pullup"
            severity = "warning"
        if expected == "pull_down" and not has_pulldown:
            status = "missing_pulldown"
            severity = "warning"
        rows.append(
            {
                "pin_name": pin.get("pin_name"),
                "net": net,
                "expected_bias": expected,
                "status": status,
                "severity": severity,
                "pullup_refs": [row["ref"] for row in pullups.get(net, [])],
                "pulldown_refs": [row["ref"] for row in pulldowns.get(net, [])],
            }
        )
    return rows


def _bus_inventory(mcu: Dict[str, Any], connectors: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nets = {row["net"]: set(row.get("tags") or []) for row in (mcu.get("pins") or [])}
    inventory: List[Dict[str, Any]] = []
    buses = {
        "i2c": ("I2C_SDA", "I2C_SCL"),
        "spi": ("SPI_MOSI", "SPI_MISO", "SPI_SCK"),
        "uart": ("UART_TX", "UART_RX"),
    }
    connector_nets = {_normalize_net(net) for connector in (connectors or []) for net in (connector.get("pin_nets") or {}).values() if _normalize_net(net)}
    for name, tags in buses.items():
        matching = sorted(net for net, row_tags in nets.items() if set(tags) & row_tags)
        if not matching:
            continue
        inventory.append(
            {
                "bus": name,
                "nets": matching,
                "exposed_on_connector": bool(set(matching) & connector_nets),
            }
        )
    return inventory


def _controller_bring_up_plan(
    board_id: str,
    connectors: Iterable[Dict[str, Any]],
    rails: Iterable[Dict[str, Any]],
    regulators: Iterable[Dict[str, Any]],
    mcu_rows: Iterable[Dict[str, Any]],
    programming_paths: Iterable[Dict[str, Any]],
    bus_inventory: Iterable[Dict[str, Any]],
    boot_constraints: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    connector_power = sorted(
        {
            net
            for connector in (connectors or [])
            for net in (connector.get("power_nets") or [])
            if _normalize_net(net) != "0"
        }
    )
    if connector_power:
        plan.append(
            {
                "stage": "power_input",
                "title": f"Verify incoming power on {board_id}",
                "action": f"Measure {', '.join(connector_power)} at the board input connector before enabling downstream peripherals.",
                "expected": "Input rail is present and stable relative to GND.",
            }
        )
    regulated_nets = sorted({str(row.get("vout_net") or "") for row in (regulators or []) if row.get("vout_net")})
    if regulated_nets:
        plan.append(
            {
                "stage": "regulated_rails",
                "title": f"Confirm regulated rails on {board_id}",
                "action": f"Probe regulator outputs: {', '.join(regulated_nets)}.",
                "expected": "Each rail reaches its nominal output without collapse or overheating.",
            }
        )
    for mcu in mcu_rows:
        plan.append(
            {
                "stage": "controller_power",
                "title": f"Confirm controller core rails for {mcu.get('ref')}",
                "action": f"Check power, enable, and reset nets for {mcu.get('part_number')}.",
                "expected": "MCU power rails are valid and reset/enable state allows boot.",
            }
        )
        if boot_constraints:
            plan.append(
                {
                    "stage": "boot_straps",
                    "title": f"Validate boot strap bias for {mcu.get('ref')}",
                    "action": "Check boot-related nets for the expected pull-up or pull-down resistors before flashing.",
                    "expected": "Critical boot pins match their expected bias and no strap net is floating.",
                }
            )
    for path in programming_paths:
        if path.get("type") == "usb_uart_bridge":
            plan.append(
                {
                    "stage": "programming_link",
                    "title": f"Verify USB-UART programming path via {path.get('bridge_ref')}",
                    "action": f"Attach USB, confirm the bridge enumerates, then open serial on nets {path.get('tx_net')} / {path.get('rx_net')}.",
                    "expected": "Console output or boot chatter is visible and the board can enter flashing mode.",
                }
            )
        elif path.get("type") in {"uart_header", "isp_header", "swd_header"}:
            plan.append(
                {
                    "stage": "programming_link",
                    "title": f"Verify {path.get('type')} access on {path.get('connector_ref')}",
                    "action": f"Attach the expected programmer/debugger to {path.get('connector_ref')} and verify link-level communication.",
                    "expected": "Programmer detects the target without forcing abnormal reset sequences.",
                }
            )
    for bus in bus_inventory:
        if bus.get("bus") == "i2c":
            plan.append(
                {
                    "stage": "bus_probe",
                    "title": "Run an I2C scan",
                    "action": f"Probe {', '.join(bus.get('nets') or [])} with a scanner after the board boots.",
                    "expected": "Expected peripheral addresses respond and the bus is not stuck low.",
                }
            )
        elif bus.get("bus") == "uart":
            plan.append(
                {
                    "stage": "bus_probe",
                    "title": "Check UART console activity",
                    "action": f"Open a serial terminal on {', '.join(bus.get('nets') or [])}.",
                    "expected": "Boot or diagnostic output appears without framing errors.",
                }
            )
    if not plan:
        plan.append(
            {
                "stage": "generic",
                "title": f"Basic bring-up for {board_id}",
                "action": "Verify power, ground continuity, and connector pinout before exercising any peripherals.",
                "expected": "Board accepts power safely and no rail collapses immediately.",
            }
        )
    return plan


def analyze_controller_runtime(
    *,
    board_id: str,
    components: Dict[str, Dict[str, Any]],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
    connectors: List[Dict[str, Any]],
    rails: List[Dict[str, Any]],
    regulators: List[Dict[str, Any]],
    resistors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    pullups, pulldowns = _build_bias_maps(resistors)
    support_parts = _find_known_support_instances(components, pinmap)
    mcu_rows = _find_mcu_instances(components, pinmap, category_by_ref)
    connector_lookup = _connector_net_lookup(connectors)

    controller_rows: List[Dict[str, Any]] = []
    programming_paths: List[Dict[str, Any]] = []
    board_bus_inventory: List[Dict[str, Any]] = []
    board_boot_constraints: List[Dict[str, Any]] = []

    for mcu in mcu_rows:
        mcu_programming_paths = _bridge_programming_paths(mcu, support_parts, connector_lookup) + _header_programming_paths(mcu, connectors)
        mcu_boot_constraints = _boot_constraints(mcu, pullups, pulldowns)
        mcu_bus_inventory = _bus_inventory(mcu, connectors)
        programming_paths.extend(mcu_programming_paths)
        board_boot_constraints.extend(mcu_boot_constraints)
        board_bus_inventory.extend(mcu_bus_inventory)
        controller_rows.append(
            {
                "ref": mcu.get("ref"),
                "part_number": mcu.get("part_number"),
                "pins": mcu.get("pins"),
                "programming_paths": mcu_programming_paths,
                "boot_constraints": mcu_boot_constraints,
                "bus_inventory": mcu_bus_inventory,
            }
        )

    bring_up_plan = _controller_bring_up_plan(
        board_id=board_id,
        connectors=connectors,
        rails=rails,
        regulators=regulators,
        mcu_rows=controller_rows,
        programming_paths=programming_paths,
        bus_inventory=board_bus_inventory,
        boot_constraints=board_boot_constraints,
    )

    readiness = "passive_only"
    warnings: List[str] = []
    if controller_rows:
        readiness = "controller_present"
        if not programming_paths:
            warnings.append("Controller detected, but no deterministic programming/debug path was extracted.")
        if any(row.get("status") != "ok" for row in board_boot_constraints):
            warnings.append("One or more boot-critical nets are missing the expected pull resistor bias.")
    else:
        warnings.append("No controller-class IC matched the lightweight pinout database.")

    return {
        "controllers": controller_rows,
        "support_components": support_parts,
        "programming_paths": programming_paths,
        "boot_constraints": board_boot_constraints,
        "bus_inventory": board_bus_inventory,
        "bias_networks": {
            "pullups": pullups,
            "pulldowns": pulldowns,
        },
        "firmware_readiness": {
            "status": readiness,
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        "bring_up_plan": bring_up_plan,
    }
