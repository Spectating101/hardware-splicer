"""Heuristic auto-wiring for inventory-composed module sets (Python engine port)."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from .pcb.module_registry import find_module, find_modules_by_capabilities

ModuleSpec = Dict[str, Any]
Recipe = Dict[str, Any]
BuildGraph = Dict[str, Any]
ComposeResult = Dict[str, Any]


def _pin_by_role(mod: ModuleSpec, role: str) -> Optional[str]:
    for pin in mod.get("pins") or []:
        if pin.get("role") == role:
            return str(pin.get("id"))
    return None


def _mcu_power_in_pin(mod: ModuleSpec) -> Optional[str]:
    for pin_id in ("VIN", "VBUS", "5V"):
        if any(p.get("id") == pin_id for p in mod.get("pins") or []):
            return pin_id
    return _pin_by_role(mod, "power_in")


def _power_out_pin(mod: ModuleSpec) -> Optional[str]:
    for pin in mod.get("pins") or []:
        if pin.get("id") == "V+":
            return "V+"
    out = _pin_by_role(mod, "power_out")
    if out:
        return out
    return _pin_by_role(mod, "power_in")


def _first_pin(mod: ModuleSpec, pred: Callable[[Mapping[str, Any]], bool]) -> Optional[str]:
    for pin in mod.get("pins") or []:
        if pred(pin):
            return str(pin.get("id"))
    return None


def _device_wants_5v(dev: ModuleSpec, dev_vcc_pin: Optional[Mapping[str, Any]]) -> bool:
    """True when a peripheral's primary supply should come from the 5V rail (not MCU 3V3)."""
    ivr = dev.get("inputVoltageRange") or []
    if ivr and float(ivr[0]) >= 4.5:
        return True
    pin_text = " ".join(
        str((dev_vcc_pin or {}).get(key) or "")
        for key in ("voltage", "notes", "label")
    )
    if re.search(r"\b5\s*V\b", pin_text, re.I):
        return True
    if re.search(r"4\.5\s*-\s*5(?:\.5)?\s*V", pin_text, re.I):
        return True
    return False


_SKIP_GENERIC_POWER_IDS = frozenset(
    {
        "a4988-stepper",
        "max98357a-i2s-amp",
        "l298n",
        "relay-1ch-5v",
        "esp32-cam-module",
    }
)


def _alloc_gpio(mcu: ModuleSpec, used: Set[str]) -> Optional[str]:
    order = [
        "GPIO4", "GPIO2", "GPIO16", "GPIO17", "GP4", "GP5", "GP0", "GP1", "GP26",
        "D2", "D3", "A0", "A1", "A2", "A3", "A4", "A5",
    ]
    pins = mcu.get("pins") or []
    for pin_id in order:
        if any(p.get("id") == pin_id for p in pins) and pin_id not in used:
            used.add(pin_id)
            return pin_id
    for pin in pins:
        pin_id = str(pin.get("id"))
        if pin_id in used:
            continue
        if pin.get("role") in ("digital_io", "pwm", "analog_in"):
            used.add(pin_id)
            return pin_id
    return None


def auto_wire_picked_modules(modules: List[ModuleSpec]) -> Recipe:
    roles = [{"role": f"m{i + 1}", "moduleId": m["id"]} for i, m in enumerate(modules)]
    role_of = {m["id"]: f"m{i + 1}" for i, m in enumerate(modules)}
    wires: List[Dict[str, Any]] = []
    wire_keys: Set[str] = set()

    def wire(from_id: str, from_pin: str, to_id: str, to_pin: str) -> None:
        fr = role_of.get(from_id)
        tr = role_of.get(to_id)
        if not fr or not tr:
            return
        key = f"{fr}:{from_pin}->{tr}:{to_pin}"
        rev = f"{tr}:{to_pin}->{fr}:{from_pin}"
        if key in wire_keys or rev in wire_keys:
            return
        wire_keys.add(key)
        wires.append({"from": {"role": fr, "pin": from_pin}, "to": {"role": tr, "pin": to_pin}})

    barrel = next((m for m in modules if m.get("id") == "dc-barrel-12v"), None)
    usb = next((m for m in modules if re.search(r"usb-power", str(m.get("id")))), None)
    buck = next((m for m in modules if re.search(r"buck", str(m.get("id")))), None)
    ldo = next((m for m in modules if re.search(r"ldo-ams1117", str(m.get("id")))), None)
    power = usb or barrel or next((m for m in modules if m.get("category") == "power"), None)
    mcu = next((m for m in modules if m.get("category") == "mcu"), None)

    def gnd_pin(m: ModuleSpec) -> Optional[str]:
        return _pin_by_role(m, "gnd")

    used_gpio: Set[str] = set()
    skip_ids = {m.get("id") for m in (power, mcu, barrel, buck, ldo) if m}

    if barrel and buck:
        wire(barrel["id"], "V+", buck["id"], "IN+")
        wire(barrel["id"], "GND", buck["id"], "IN-")
    elif buck and power and power.get("id") != buck.get("id") and not barrel:
        p_out = _power_out_pin(power) or _first_pin(power, lambda p: p.get("role") == "power_in")
        p_gnd = gnd_pin(power)
        if p_out:
            wire(power["id"], p_out, buck["id"], "IN+")
        if p_gnd:
            wire(power["id"], p_gnd, buck["id"], "IN-")

    m_in = _mcu_power_in_pin(mcu) if mcu else None
    m_gnd = gnd_pin(mcu) if mcu else None
    if buck and mcu and m_in and m_gnd:
        wire(buck["id"], "OUT+", mcu["id"], m_in)
        wire(buck["id"], "OUT-", mcu["id"], m_gnd)
    elif power and mcu and m_in and m_gnd:
        p_out = _power_out_pin(power)
        gnd = gnd_pin(power)
        if p_out:
            wire(power["id"], p_out, mcu["id"], m_in)
        if gnd:
            wire(power["id"], gnd, mcu["id"], m_gnd)
    elif barrel and mcu and not buck and m_in and m_gnd:
        wire(barrel["id"], "V+", mcu["id"], m_in)
        wire(barrel["id"], "GND", mcu["id"], m_gnd)

    if barrel and mcu and m_gnd and not buck:
        wire(barrel["id"], "GND", mcu["id"], m_gnd)

    if barrel and ldo and not buck:
        wire(barrel["id"], "V+", ldo["id"], "VIN")
        wire(barrel["id"], "GND", ldo["id"], "GND")

    if buck:
        rail_pos: Optional[Tuple[str, str]] = (buck["id"], "OUT+")
        rail_gnd: Optional[Tuple[str, str]] = (buck["id"], "OUT-")
    elif ldo:
        rail_pos = (ldo["id"], "VOUT")
        rail_gnd = (ldo["id"], "GND")
    elif usb:
        rail_pos = (usb["id"], _power_out_pin(usb) or "5V")
        gnd = gnd_pin(usb)
        rail_gnd = (usb["id"], gnd) if gnd else None
    elif mcu:
        v5 = next((p.get("id") for p in mcu.get("pins") or [] if p.get("id") == "5V"), None)
        rail_pos = (mcu["id"], v5 or "3V3")
        gnd = gnd_pin(mcu)
        rail_gnd = (mcu["id"], gnd) if gnd else None
    else:
        rail_pos = None
        rail_gnd = None

    mcu_pins = mcu.get("pins") or [] if mcu else []
    mcu_sda = next((p.get("id") for p in mcu_pins if p.get("role") == "i2c_sda"), None)
    mcu_scl = next((p.get("id") for p in mcu_pins if p.get("role") == "i2c_scl"), None)
    mcu_vout = next((p.get("id") for p in mcu_pins if p.get("id") == "3V3"), None) or next(
        (p.get("id") for p in mcu_pins if p.get("id") == "5V"), None
    )
    level_shifter = next((m for m in modules if re.search(r"level-shifter", str(m.get("id")))), None)
    load_switch = next(
        (m for m in modules if re.search(r"mosfet-irlz44n|mosfet-irf520", str(m.get("id")))),
        None,
    )

    if level_shifter and mcu and rail_pos and rail_gnd:
        hv_rail = _first_pin(level_shifter, lambda p: p.get("id") == "HV")
        lv_rail = _first_pin(level_shifter, lambda p: p.get("id") == "LV")
        sh_gnd = gnd_pin(level_shifter)
        if hv_rail and rail_pos:
            wire(rail_pos[0], rail_pos[1], level_shifter["id"], hv_rail)
        if sh_gnd and rail_gnd:
            wire(rail_gnd[0], rail_gnd[1], level_shifter["id"], sh_gnd)
        if lv_rail and mcu_vout:
            wire(mcu["id"], mcu_vout, level_shifter["id"], lv_rail)
        mcu_g = gnd_pin(mcu)
        if sh_gnd and mcu_g:
            wire(mcu["id"], mcu_g, level_shifter["id"], sh_gnd)

    switched_loads = {"water_pump_5v", "cooling_fan_5v", "mini-pump-5v"}

    for dev in modules:
        if dev.get("id") in skip_ids or dev is level_shifter:
            continue
        dev_id = str(dev.get("id") or "")
        is_mosfet_driver = bool(re.search(r"mosfet", dev_id))
        dev_gnd = gnd_pin(dev)
        mcu_g = gnd_pin(mcu) if mcu else None
        if mcu and dev_gnd and mcu_g:
            wire(mcu["id"], mcu_g, dev["id"], dev_gnd)
        elif rail_gnd and dev_gnd:
            wire(rail_gnd[0], rail_gnd[1], dev["id"], dev_gnd)

        has_dedicated_power = (
            is_mosfet_driver
            or dev_id in _SKIP_GENERIC_POWER_IDS
            or bool(re.search(r"ili9341|st7735", dev_id))
        )
        if not has_dedicated_power:
            dev_vcc_pin = next(
                (p for p in dev.get("pins") or [] if p.get("id") in ("VCC", "VIN", "V+") or p.get("role") == "power_in"),
                None,
            )
            dev_vcc = dev_vcc_pin.get("id") if dev_vcc_pin else None
            wants_5v = _device_wants_5v(dev, dev_vcc_pin)
            via_switch = bool(load_switch and dev_id in switched_loads and dev_vcc)
            if via_switch and load_switch:
                if rail_pos:
                    wire(rail_pos[0], rail_pos[1], load_switch["id"], "VIN")
                if rail_gnd:
                    wire(rail_gnd[0], rail_gnd[1], load_switch["id"], "VIN-")
                wire(load_switch["id"], "VOUT+", dev["id"], dev_vcc)
                vout_neg = _first_pin(load_switch, lambda p: p.get("id") == "VOUT-")
                if vout_neg and dev_gnd:
                    wire(load_switch["id"], vout_neg, dev["id"], dev_gnd)
            elif wants_5v and rail_pos and dev_vcc:
                wire(rail_pos[0], rail_pos[1], dev["id"], dev_vcc)
            elif mcu and mcu_vout and dev_vcc:
                wire(mcu["id"], mcu_vout, dev["id"], dev_vcc)
            elif rail_pos and dev_vcc:
                wire(rail_pos[0], rail_pos[1], dev["id"], dev_vcc)

        dev_sda = next((p.get("id") for p in dev.get("pins") or [] if p.get("role") == "i2c_sda"), None)
        dev_scl = next((p.get("id") for p in dev.get("pins") or [] if p.get("role") == "i2c_scl"), None)
        if mcu and mcu_sda and mcu_scl and dev_sda and dev_scl:
            wire(mcu["id"], mcu_sda, dev["id"], dev_sda)
            wire(mcu["id"], mcu_scl, dev["id"], dev_scl)

        dev_id = str(dev.get("id"))
        if mcu and re.search(r"mosfet", dev_id):
            sig = _alloc_gpio(mcu, used_gpio)
            vin = _first_pin(dev, lambda p: p.get("id") == "VIN")
            vin_neg = _first_pin(dev, lambda p: p.get("id") == "VIN-")
            sig_gnd = _first_pin(dev, lambda p: p.get("id") == "GND")
            if sig and _first_pin(dev, lambda p: p.get("id") == "SIG"):
                wire(mcu["id"], sig, dev["id"], "SIG")
            if rail_pos and vin:
                wire(rail_pos[0], rail_pos[1], dev["id"], vin)
            if rail_gnd and vin_neg:
                wire(rail_gnd[0], rail_gnd[1], dev["id"], vin_neg)
            if mcu_g and sig_gnd:
                wire(mcu["id"], mcu_g, dev["id"], "GND")
        if mcu and dev_id == "relay-1ch-5v":
            sig = _alloc_gpio(mcu, used_gpio)
            if sig:
                wire(mcu["id"], sig, dev["id"], "IN")
        if mcu and dev_id == "l298n":
            in1 = _alloc_gpio(mcu, used_gpio)
            in2 = _alloc_gpio(mcu, used_gpio)
            if in1:
                wire(mcu["id"], in1, dev["id"], "IN1")
            if in2:
                wire(mcu["id"], in2, dev["id"], "IN2")
            if rail_pos:
                wire(rail_pos[0], rail_pos[1], dev["id"], "VCC")
            if mcu_g:
                wire(mcu["id"], mcu_g, dev["id"], "GND")
        if mcu and dev_id == "a4988-stepper":
            step = _alloc_gpio(mcu, used_gpio)
            dir_pin = _alloc_gpio(mcu, used_gpio)
            if step:
                wire(mcu["id"], step, dev["id"], "STEP")
            if dir_pin:
                wire(mcu["id"], dir_pin, dev["id"], "DIR")
            if mcu_vout:
                wire(mcu["id"], mcu_vout, dev["id"], "VDD")
            if rail_pos:
                wire(rail_pos[0], rail_pos[1], dev["id"], "VMOT")
            if mcu_g:
                wire(mcu["id"], mcu_g, dev["id"], "GND_LOGIC")
            if rail_gnd:
                wire(rail_gnd[0], rail_gnd[1], dev["id"], "GND_MOTOR")
        if mcu and dev_id == "sg90":
            sig = _alloc_gpio(mcu, used_gpio)
            if sig:
                wire(mcu["id"], sig, dev["id"], "SIG")
        if mcu and dev_id == "hc-sr04":
            trig = _alloc_gpio(mcu, used_gpio)
            echo = _alloc_gpio(mcu, used_gpio)
            if level_shifter and trig and echo:
                wire(mcu["id"], trig, level_shifter["id"], "LV1")
                wire(level_shifter["id"], "HV1", dev["id"], "TRIG")
                wire(dev["id"], "ECHO", level_shifter["id"], "HV2")
                wire(level_shifter["id"], "LV2", mcu["id"], echo)
            else:
                if trig:
                    wire(mcu["id"], trig, dev["id"], "TRIG")
                if echo:
                    wire(mcu["id"], echo, dev["id"], "ECHO")
        if mcu and dev_id == "dht22":
            data = _alloc_gpio(mcu, used_gpio)
            if data:
                wire(mcu["id"], data, dev["id"], "DATA")
        if mcu and dev_id == "soil_moisture":
            ao = _alloc_gpio(mcu, used_gpio)
            if ao:
                wire(mcu["id"], ao, dev["id"], "A0")
        if mcu and dev_id == "ldr_photoresistor":
            sense = _alloc_gpio(mcu, used_gpio)
            if mcu_vout:
                wire(mcu["id"], mcu_vout, dev["id"], "PIN1")
            if sense:
                wire(mcu["id"], sense, dev["id"], "PIN2")
        if mcu and dev_id == "limit-switch-3pin":
            sig = _alloc_gpio(mcu, used_gpio)
            if sig:
                wire(mcu["id"], sig, dev["id"], "SIG")
        if mcu and re.search(r"ili9341|st7735", dev_id):

            def pick_mcu_pin(preferred: List[str], dev_pin_id: str) -> None:
                for p in preferred:
                    if any(pin.get("id") == p for pin in mcu_pins) and p not in used_gpio:
                        used_gpio.add(p)
                        wire(mcu["id"], p, dev["id"], dev_pin_id)
                        return
                sig = _alloc_gpio(mcu, used_gpio)
                if sig:
                    wire(mcu["id"], sig, dev["id"], dev_pin_id)

            mosi_pin = next(
                (
                    p.get("id")
                    for p in dev.get("pins") or []
                    if p.get("role") == "spi_mosi" or p.get("id") in ("SDI", "SDA")
                ),
                None,
            )
            sck_pin = next(
                (
                    p.get("id")
                    for p in dev.get("pins") or []
                    if p.get("role") == "spi_sck" or p.get("id") in ("SCK", "SCL")
                ),
                None,
            )
            cs_pin = next(
                (p.get("id") for p in dev.get("pins") or [] if p.get("role") == "spi_cs" or p.get("id") == "CS"),
                None,
            )
            rst_pin = next(
                (p.get("id") for p in dev.get("pins") or [] if p.get("id") in ("RST", "RES")),
                None,
            )
            dc_pin = next((p.get("id") for p in dev.get("pins") or [] if p.get("id") == "DC"), None)
            if mosi_pin:
                pick_mcu_pin(["GPIO23", "GPIO21", "GPIO17"], mosi_pin)
            if sck_pin:
                pick_mcu_pin(["GPIO18", "GPIO22", "GPIO5"], sck_pin)
            if cs_pin:
                pick_mcu_pin(["GPIO15", "GPIO4", "GPIO2"], cs_pin)
            if rst_pin:
                pick_mcu_pin(["GPIO2", "GPIO4", "GPIO16"], rst_pin)
            if dc_pin:
                pick_mcu_pin(["GPIO4", "GPIO16", "GPIO17"], dc_pin)
            if rail_pos and any(p.get("id") == "VCC" for p in dev.get("pins") or []):
                wire(rail_pos[0], rail_pos[1], dev["id"], "VCC")
        if mcu and dev_id == "max98357a-i2s-amp":
            bclk = next(
                (p.get("id") for p in mcu_pins if p.get("id") == "GPIO22" or p.get("role") == "i2c_scl"),
                None,
            )
            lrc = next(
                (p.get("id") for p in mcu_pins if p.get("id") == "GPIO21" or p.get("role") == "i2c_sda"),
                None,
            )
            din = _alloc_gpio(mcu, used_gpio)
            if rail_pos:
                wire(rail_pos[0], rail_pos[1], dev["id"], "VIN")
            elif mcu_vout:
                wire(mcu["id"], mcu_vout, dev["id"], "VIN")
            if mcu_g:
                wire(mcu["id"], mcu_g, dev["id"], "GND")
            if bclk:
                wire(mcu["id"], bclk, dev["id"], "BCLK")
            if lrc:
                wire(mcu["id"], lrc, dev["id"], "LRC")
            if din:
                wire(mcu["id"], din, dev["id"], "DIN")
        if power and dev_id == "esp32-cam-module":
            p_out = _power_out_pin(power)
            gnd = gnd_pin(power)
            dev_g = gnd_pin(dev)
            if p_out:
                wire(power["id"], p_out, dev["id"], "5V")
            if gnd and dev_g:
                wire(power["id"], gnd, dev["id"], "GND")

        if mcu:
            dev_role = role_of.get(dev["id"])
            wired_pins = {
                pin
                for w in wires
                if w["from"]["role"] == dev_role or w["to"]["role"] == dev_role
                for pin in (w["from"]["pin"], w["to"]["pin"])
            }
            analog = next(
                (
                    p
                    for p in dev.get("pins") or []
                    if p.get("role") == "analog_in" and p.get("id") not in wired_pins
                ),
                None,
            )
            if analog:
                mcu_analog = next((p.get("id") for p in mcu_pins if p.get("role") == "analog_in"), None)
                if not mcu_analog:
                    mcu_analog = _alloc_gpio(mcu, used_gpio)
                if mcu_analog:
                    wire(mcu["id"], mcu_analog, dev["id"], analog["id"])
            else:
                digital = next(
                    (
                        p
                        for p in dev.get("pins") or []
                        if p.get("role") in ("digital_io", "digital_in", "digital_out")
                        and p.get("id") != "VCC"
                        and p.get("id") not in wired_pins
                    ),
                    None,
                )
                if digital:
                    sig = _alloc_gpio(mcu, used_gpio)
                    if sig:
                        wire(mcu["id"], sig, dev["id"], digital["id"])

    return {
        "modules": roles,
        "wires": wires,
        "notes": ["Auto-wired via inventory/capability composer — review pins before fab."],
    }


def _recipe_to_build_graph(recipe: Recipe) -> BuildGraph:
    id_of: Dict[str, str] = {}
    nodes = []
    for i, m in enumerate(recipe.get("modules") or []):
        node_id = f"n{i + 1}"
        id_of[str(m.get("role"))] = node_id
        nodes.append({"id": node_id, "moduleId": m.get("moduleId")})
    wires = []
    for i, w in enumerate(recipe.get("wires") or []):
        from_role = w.get("from", {}).get("role")
        to_role = w.get("to", {}).get("role")
        from_id = id_of.get(str(from_role))
        to_id = id_of.get(str(to_role))
        if not from_id or not to_id:
            continue
        wires.append(
            {
                "id": f"w{i + 1}",
                "from": {"nodeId": from_id, "pinId": w.get("from", {}).get("pin")},
                "to": {"nodeId": to_id, "pinId": w.get("to", {}).get("pin")},
            }
        )
    return {"nodes": nodes, "wires": wires}


def pick_modules_for_requirements(req_any: List[List[str]]) -> List[ModuleSpec]:
    chosen: List[ModuleSpec] = []
    chosen_ids: Set[str] = set()
    for group in req_any:
        candidates = [m for m in find_modules_by_capabilities([group]) if m.get("id") not in chosen_ids]
        if not candidates:
            continue
        candidates.sort(key=lambda m: len(m.get("capabilityTags") or []))
        chosen.append(candidates[0])
        chosen_ids.add(str(candidates[0].get("id")))
    return chosen


def compose_build_graph_from_module_ids(module_ids: List[str]) -> ComposeResult:
    modules = [find_module(mid) for mid in module_ids]
    modules = [m for m in modules if m]
    if len(modules) < 2:
        return {
            "graph": {"nodes": [], "wires": []},
            "build_id": "generic_low_voltage_build",
            "notes": [],
            "warnings": ["Need at least two known module ids to compose a graph."],
        }
    recipe = auto_wire_picked_modules(modules)
    return {
        "graph": _recipe_to_build_graph(recipe),
        "build_id": "generic_low_voltage_build",
        "notes": list(recipe.get("notes") or []),
        "warnings": [],
    }


def compose_build_graph_from_canvas_nodes(
    nodes: List[Mapping[str, str]],
) -> BuildGraph:
    specs: List[ModuleSpec] = []
    node_ids: List[str] = []
    for node in nodes:
        spec = find_module(str(node.get("moduleId") or ""))
        if not spec:
            continue
        specs.append(spec)
        node_ids.append(str(node["id"]))
    if len(specs) < 2:
        return {
            "nodes": [{"id": n["id"], "moduleId": n.get("moduleId")} for n in nodes],
            "wires": [],
        }
    recipe = auto_wire_picked_modules(specs)
    role_to_node_id = {recipe["modules"][i]["role"]: node_ids[i] for i in range(len(node_ids))}
    build_nodes = [{"id": nid, "moduleId": specs[i]["id"]} for i, nid in enumerate(node_ids)]
    out_wires = []
    for i, w in enumerate(recipe.get("wires") or []):
        from_id = role_to_node_id.get(w["from"]["role"])
        to_id = role_to_node_id.get(w["to"]["role"])
        if not from_id or not to_id:
            continue
        out_wires.append(
            {
                "id": f"w{i + 1}",
                "from": {"nodeId": from_id, "pinId": w["from"]["pin"]},
                "to": {"nodeId": to_id, "pinId": w["to"]["pin"]},
            }
        )
    return {"nodes": build_nodes, "wires": out_wires}
