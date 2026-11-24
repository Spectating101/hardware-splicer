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
        "drv8833-motor",
        "l9110-motor",
        "bts7960-motor",
        "tb6612fng-motor",
        "relay-1ch-5v",
        "relay_module_1ch_5v",
        "relay_module_4ch_5v",
        "esp32-cam-module",
    }
)


def _alloc_gpio(mcu: ModuleSpec, used: Set[str]) -> Optional[str]:
    # Prefer ESP32-CAM free GPIOs (12–15) before flash-LED GPIO4 / boot-sensitive pins.
    order = [
        "GPIO12", "GPIO13", "GPIO14", "GPIO15",
        "GPIO16", "GPIO17", "GPIO4", "GPIO2",
        "GP4", "GP5", "GP0", "GP1", "GP26",
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


def _alloc_pin_by_role(mcu: ModuleSpec, used: Set[str], role: str) -> Optional[str]:
    for pin in mcu.get("pins") or []:
        pin_id = str(pin.get("id") or "")
        if pin.get("role") == role and pin_id and pin_id not in used:
            used.add(pin_id)
            return pin_id
    return None


def auto_wire_picked_modules(modules: List[ModuleSpec]) -> Recipe:
    # Every entry of ``modules`` is its own instance with its own role (m1, m2,
    # ... in list order), even when the same module id appears more than once.
    # Wires address instances through the private ``_role`` key on a per-call
    # copy of the spec, never through the module id, so a repeated module
    # cannot collapse onto a single role. Callers' specs are not mutated.
    roles = [{"role": f"m{i + 1}", "moduleId": m["id"]} for i, m in enumerate(modules)]
    modules = [{**m, "_role": f"m{i + 1}"} for i, m in enumerate(modules)]
    wires: List[Dict[str, Any]] = []
    wire_keys: Set[str] = set()

    def wire(fr: str, from_pin: str, tr: str, to_pin: str) -> None:
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
        wire(barrel["_role"], "V+", buck["_role"], "IN+")
        wire(barrel["_role"], "GND", buck["_role"], "IN-")
    elif buck and power and power.get("id") != buck.get("id") and not barrel:
        p_out = _power_out_pin(power) or _first_pin(power, lambda p: p.get("role") == "power_in")
        p_gnd = gnd_pin(power)
        if p_out:
            wire(power["_role"], p_out, buck["_role"], "IN+")
        if p_gnd:
            wire(power["_role"], p_gnd, buck["_role"], "IN-")

    m_in = _mcu_power_in_pin(mcu) if mcu else None
    m_gnd = gnd_pin(mcu) if mcu else None
    if buck and mcu and m_in and m_gnd:
        wire(buck["_role"], "OUT+", mcu["_role"], m_in)
        wire(buck["_role"], "OUT-", mcu["_role"], m_gnd)
    elif power and mcu and m_in and m_gnd:
        p_out = _power_out_pin(power)
        gnd = gnd_pin(power)
        if p_out:
            wire(power["_role"], p_out, mcu["_role"], m_in)
        if gnd:
            wire(power["_role"], gnd, mcu["_role"], m_gnd)
    elif barrel and mcu and not buck and m_in and m_gnd:
        wire(barrel["_role"], "V+", mcu["_role"], m_in)
        wire(barrel["_role"], "GND", mcu["_role"], m_gnd)

    if barrel and mcu and m_gnd and not buck:
        wire(barrel["_role"], "GND", mcu["_role"], m_gnd)

    if barrel and ldo and not buck:
        wire(barrel["_role"], "V+", ldo["_role"], "VIN")
        wire(barrel["_role"], "GND", ldo["_role"], "GND")
    elif ldo and power and power.get("id") != ldo.get("id") and not buck:
        p_out = _power_out_pin(power) or _first_pin(power, lambda p: p.get("role") == "power_in")
        p_gnd = gnd_pin(power)
        if p_out:
            wire(power["_role"], p_out, ldo["_role"], "VIN")
        if p_gnd:
            wire(power["_role"], p_gnd, ldo["_role"], "GND")

    mcu_has_5v = bool(mcu and any(p.get("id") == "5V" for p in mcu.get("pins") or []))
    if buck:
        rail_pos: Optional[Tuple[str, str]] = (buck["_role"], "OUT+")
        rail_gnd: Optional[Tuple[str, str]] = (buck["_role"], "OUT-")
    elif ldo and not usb and not mcu_has_5v:
        # The shared load rail feeds servos, relays, pumps and the level shifter's high side, all of which
        # need 5 V. A 3.3 V LDO is the rail only when nothing 5 V-capable is present; with USB power or an
        # MCU 5V pin it only feeds what is wired to it explicitly above.
        rail_pos = (ldo["_role"], "VOUT")
        rail_gnd = (ldo["_role"], "GND")
    elif usb:
        rail_pos = (usb["_role"], _power_out_pin(usb) or "5V")
        gnd = gnd_pin(usb)
        rail_gnd = (usb["_role"], gnd) if gnd else None
    elif barrel and not (ldo and mcu_has_5v):
        rail_pos = (barrel["_role"], "V+")
        rail_gnd = (barrel["_role"], "GND")
    elif mcu:
        v5 = next((p.get("id") for p in mcu.get("pins") or [] if p.get("id") == "5V"), None)
        rail_pos = (mcu["_role"], v5 or "3V3")
        gnd = gnd_pin(mcu)
        rail_gnd = (mcu["_role"], gnd) if gnd else None
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
    h_bridge_driver = next(
        (m for m in modules if str(m.get("id")) in {"l298n", "drv8833-motor", "l9110-motor", "bts7960-motor", "tb6612fng-motor"}),
        None,
    )

    if level_shifter and mcu and rail_pos and rail_gnd:
        hv_rail = _first_pin(level_shifter, lambda p: p.get("id") == "HV")
        lv_rail = _first_pin(level_shifter, lambda p: p.get("id") == "LV")
        sh_gnd = gnd_pin(level_shifter)
        if hv_rail and rail_pos:
            wire(rail_pos[0], rail_pos[1], level_shifter["_role"], hv_rail)
        if sh_gnd and rail_gnd:
            wire(rail_gnd[0], rail_gnd[1], level_shifter["_role"], sh_gnd)
        if lv_rail and mcu_vout:
            wire(mcu["_role"], mcu_vout, level_shifter["_role"], lv_rail)
        mcu_g = gnd_pin(mcu)
        if sh_gnd and mcu_g:
            wire(mcu["_role"], mcu_g, level_shifter["_role"], sh_gnd)

    switched_loads = {"water_pump_5v", "cooling_fan_5v", "mini-pump-5v"}

    for dev in modules:
        if dev.get("id") in skip_ids or dev is level_shifter:
            continue
        dev_id = str(dev.get("id") or "")
        is_mosfet_driver = bool(re.search(r"mosfet", dev_id))
        is_h_bridge_load = bool(
            h_bridge_driver
            and dev_id in {"dc_motor_3v_6v", "dc_geared_motor_12v", "water_pump_5v", "mini-pump-5v", "cooling_fan_5v"}
        )
        dev_gnd = gnd_pin(dev)
        mcu_g = gnd_pin(mcu) if mcu else None
        if not is_h_bridge_load and mcu and dev_gnd and mcu_g:
            wire(mcu["_role"], mcu_g, dev["_role"], dev_gnd)
        elif not is_h_bridge_load and rail_gnd and dev_gnd:
            wire(rail_gnd[0], rail_gnd[1], dev["_role"], dev_gnd)

        has_dedicated_power = (
            is_mosfet_driver
            or dev_id in _SKIP_GENERIC_POWER_IDS
            or is_h_bridge_load
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
                    wire(rail_pos[0], rail_pos[1], load_switch["_role"], "VIN")
                if rail_gnd:
                    wire(rail_gnd[0], rail_gnd[1], load_switch["_role"], "VIN-")
                wire(load_switch["_role"], "VOUT+", dev["_role"], dev_vcc)
                vout_neg = _first_pin(load_switch, lambda p: p.get("id") == "VOUT-")
                if vout_neg and dev_gnd:
                    wire(load_switch["_role"], vout_neg, dev["_role"], dev_gnd)
            elif wants_5v and rail_pos and dev_vcc:
                wire(rail_pos[0], rail_pos[1], dev["_role"], dev_vcc)
            elif mcu and mcu_vout and dev_vcc:
                wire(mcu["_role"], mcu_vout, dev["_role"], dev_vcc)
            elif rail_pos and dev_vcc:
                wire(rail_pos[0], rail_pos[1], dev["_role"], dev_vcc)

        dev_sda = next((p.get("id") for p in dev.get("pins") or [] if p.get("role") == "i2c_sda"), None)
        dev_scl = next((p.get("id") for p in dev.get("pins") or [] if p.get("role") == "i2c_scl"), None)
        if mcu and mcu_sda and mcu_scl and dev_sda and dev_scl:
            wire(mcu["_role"], mcu_sda, dev["_role"], dev_sda)
            wire(mcu["_role"], mcu_scl, dev["_role"], dev_scl)

        dev_id = str(dev.get("id"))
        if mcu and re.search(r"mosfet", dev_id):
            sig = _alloc_gpio(mcu, used_gpio)
            vin = _first_pin(dev, lambda p: p.get("id") == "VIN")
            vin_neg = _first_pin(dev, lambda p: p.get("id") == "VIN-")
            sig_gnd = _first_pin(dev, lambda p: p.get("id") == "GND")
            if sig and _first_pin(dev, lambda p: p.get("id") == "SIG"):
                wire(mcu["_role"], sig, dev["_role"], "SIG")
            if rail_pos and vin:
                wire(rail_pos[0], rail_pos[1], dev["_role"], vin)
            if rail_gnd and vin_neg:
                wire(rail_gnd[0], rail_gnd[1], dev["_role"], vin_neg)
            if mcu_g and sig_gnd:
                wire(mcu["_role"], mcu_g, dev["_role"], "GND")
        if mcu and dev_id in {"relay-1ch-5v", "relay_module_1ch_5v", "relay_module_4ch_5v"}:
            sig = _alloc_gpio(mcu, used_gpio)
            relay_in = "IN1" if _first_pin(dev, lambda p: p.get("id") == "IN1") else "IN"
            if sig:
                wire(mcu["_role"], sig, dev["_role"], relay_in)
            if rail_pos and _first_pin(dev, lambda p: p.get("id") == "VCC"):
                wire(rail_pos[0], rail_pos[1], dev["_role"], "VCC")
            if mcu_g and _first_pin(dev, lambda p: p.get("id") == "GND"):
                wire(mcu["_role"], mcu_g, dev["_role"], "GND")
        if mcu and dev_id == "l298n":
            # Dual H-bridge: always request both channels when pinout includes IN3/IN4.
            control_pins = ["IN1", "IN2"]
            if _first_pin(dev, lambda p: p.get("id") == "IN3"):
                control_pins = ["IN1", "IN2", "IN3", "IN4"]
            for pin_name in control_pins:
                if not _first_pin(dev, lambda p, n=pin_name: p.get("id") == n):
                    continue
                sig = _alloc_gpio(mcu, used_gpio)
                if sig:
                    wire(mcu["_role"], sig, dev["_role"], pin_name)
            if rail_pos:
                wire(rail_pos[0], rail_pos[1], dev["_role"], "VCC")
            if mcu_g:
                wire(mcu["_role"], mcu_g, dev["_role"], "GND")
            motor_loads = [
                m
                for m in modules
                if str(m.get("id"))
                in {
                    "dc_motor_3v_6v",
                    "dc_geared_motor_12v",
                    "water_pump_5v",
                    "mini-pump-5v",
                    "cooling_fan_5v",
                }
            ]
            out_pairs = [("OUT1", "OUT2"), ("OUT3", "OUT4")]
            for motor_load, (out_a, out_b) in zip(motor_loads, out_pairs):
                if not _first_pin(dev, lambda p, n=out_a: p.get("id") == n):
                    break
                load_pos = _first_pin(
                    motor_load,
                    lambda p: p.get("id") in {"VCC", "V+", "VIN"} or p.get("role") == "power_in",
                )
                load_gnd = gnd_pin(motor_load)
                if load_pos and load_gnd:
                    wire(dev["_role"], out_a, motor_load["_role"], load_pos)
                    wire(dev["_role"], out_b, motor_load["_role"], load_gnd)
        if mcu and dev_id in {"drv8833-motor", "l9110-motor", "bts7960-motor", "tb6612fng-motor"}:
            control_pins = [
                str(p.get("id"))
                for p in dev.get("pins") or []
                if p.get("role") in {"digital_in", "pwm"} and p.get("id") not in {"FAULT"}
            ][:4]
            for pin_id in control_pins:
                sig = _alloc_gpio(mcu, used_gpio)
                if sig:
                    wire(mcu["_role"], sig, dev["_role"], pin_id)
            motor_supply = _first_pin(dev, lambda p: p.get("id") in {"VM", "B+"}) or _first_pin(
                dev, lambda p: p.get("id") == "VCC" and p.get("role") == "power_in"
            )
            logic_supply = _first_pin(dev, lambda p: p.get("id") == "VCC")
            if rail_pos and motor_supply:
                wire(rail_pos[0], rail_pos[1], dev["_role"], motor_supply)
            if mcu_vout and logic_supply and logic_supply != motor_supply:
                wire(mcu["_role"], mcu_vout, dev["_role"], logic_supply)
            motor_ground = _first_pin(dev, lambda p: p.get("id") == "B-") or _first_pin(dev, lambda p: p.get("id") == "GND")
            if rail_gnd and motor_ground:
                wire(rail_gnd[0], rail_gnd[1], dev["_role"], motor_ground)
            if mcu_g and _first_pin(dev, lambda p: p.get("id") == "GND"):
                wire(mcu["_role"], mcu_g, dev["_role"], "GND")
            motor_load = next(
                (
                    m
                    for m in modules
                    if str(m.get("id")) in {"dc_motor_3v_6v", "dc_geared_motor_12v", "water_pump_5v", "mini-pump-5v", "cooling_fan_5v"}
                ),
                None,
            )
            if motor_load:
                out_pins = [
                    str(p.get("id"))
                    for p in dev.get("pins") or []
                    if p.get("role") == "power_out"
                ][:2]
                load_pos = _first_pin(motor_load, lambda p: p.get("id") in {"VCC", "V+", "VIN"} or p.get("role") == "power_in")
                load_gnd = gnd_pin(motor_load)
                if len(out_pins) >= 2 and load_pos and load_gnd:
                    wire(dev["_role"], out_pins[0], motor_load["_role"], load_pos)
                    wire(dev["_role"], out_pins[1], motor_load["_role"], load_gnd)
        if mcu and dev_id == "a4988-stepper":
            step = _alloc_gpio(mcu, used_gpio)
            dir_pin = _alloc_gpio(mcu, used_gpio)
            if step:
                wire(mcu["_role"], step, dev["_role"], "STEP")
            if dir_pin:
                wire(mcu["_role"], dir_pin, dev["_role"], "DIR")
            if mcu_vout:
                wire(mcu["_role"], mcu_vout, dev["_role"], "VDD")
            if rail_pos:
                wire(rail_pos[0], rail_pos[1], dev["_role"], "VMOT")
            if mcu_g:
                wire(mcu["_role"], mcu_g, dev["_role"], "GND_LOGIC")
            if rail_gnd:
                wire(rail_gnd[0], rail_gnd[1], dev["_role"], "GND_MOTOR")
        if mcu and dev_id == "sg90":
            sig = _alloc_gpio(mcu, used_gpio)
            if sig:
                wire(mcu["_role"], sig, dev["_role"], "SIG")
        if mcu and dev_id == "hc-sr04":
            trig = _alloc_gpio(mcu, used_gpio)
            echo = _alloc_gpio(mcu, used_gpio)
            if level_shifter and trig and echo:
                wire(mcu["_role"], trig, level_shifter["_role"], "LV1")
                wire(level_shifter["_role"], "HV1", dev["_role"], "TRIG")
                wire(dev["_role"], "ECHO", level_shifter["_role"], "HV2")
                wire(level_shifter["_role"], "LV2", mcu["_role"], echo)
            else:
                if trig:
                    wire(mcu["_role"], trig, dev["_role"], "TRIG")
                if echo:
                    wire(mcu["_role"], echo, dev["_role"], "ECHO")
        if mcu and dev_id == "dht22":
            data = _alloc_gpio(mcu, used_gpio)
            if data:
                wire(mcu["_role"], data, dev["_role"], "DATA")
        if mcu and dev_id == "soil_moisture":
            ao = _alloc_pin_by_role(mcu, used_gpio, "analog_in") or _alloc_gpio(mcu, used_gpio)
            if ao:
                wire(mcu["_role"], ao, dev["_role"], "A0")
        if mcu and dev_id == "ldr_photoresistor":
            sense = _alloc_gpio(mcu, used_gpio)
            if mcu_vout:
                wire(mcu["_role"], mcu_vout, dev["_role"], "PIN1")
            if sense:
                wire(mcu["_role"], sense, dev["_role"], "PIN2")
        if mcu and dev_id == "limit-switch-3pin":
            sig = _alloc_gpio(mcu, used_gpio)
            if sig:
                wire(mcu["_role"], sig, dev["_role"], "SIG")
        if mcu and re.search(r"ili9341|st7735", dev_id):

            def pick_mcu_pin(preferred: List[str], dev_pin_id: str) -> None:
                for p in preferred:
                    if any(pin.get("id") == p for pin in mcu_pins) and p not in used_gpio:
                        used_gpio.add(p)
                        wire(mcu["_role"], p, dev["_role"], dev_pin_id)
                        return
                sig = _alloc_gpio(mcu, used_gpio)
                if sig:
                    wire(mcu["_role"], sig, dev["_role"], dev_pin_id)

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
                wire(rail_pos[0], rail_pos[1], dev["_role"], "VCC")
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
                wire(rail_pos[0], rail_pos[1], dev["_role"], "VIN")
            elif mcu_vout:
                wire(mcu["_role"], mcu_vout, dev["_role"], "VIN")
            if mcu_g:
                wire(mcu["_role"], mcu_g, dev["_role"], "GND")
            if bclk:
                wire(mcu["_role"], bclk, dev["_role"], "BCLK")
            if lrc:
                wire(mcu["_role"], lrc, dev["_role"], "LRC")
            if din:
                wire(mcu["_role"], din, dev["_role"], "DIN")
        if power and dev_id == "esp32-cam-module":
            p_out = _power_out_pin(power)
            gnd = gnd_pin(power)
            dev_g = gnd_pin(dev)
            if p_out:
                wire(power["_role"], p_out, dev["_role"], "5V")
            if gnd and dev_g:
                wire(power["_role"], gnd, dev["_role"], "GND")

        if mcu:
            dev_role = dev["_role"]
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
                # Reserve the pin, so a second analog part gets its own input rather than sharing this one.
                mcu_analog = _alloc_pin_by_role(mcu, used_gpio, "analog_in")
                if not mcu_analog:
                    mcu_analog = _alloc_gpio(mcu, used_gpio)
                if mcu_analog:
                    wire(mcu["_role"], mcu_analog, dev["_role"], analog["id"])
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
                        wire(mcu["_role"], sig, dev["_role"], digital["id"])

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


def compose_build_graph_from_module_ids(module_ids: List[str], *, auto_repair: bool = True) -> ComposeResult:
    modules = [find_module(mid) for mid in module_ids]
    unresolved = [mid for mid, module in zip(module_ids, modules) if module is None]
    request = {
        "requested_module_ids": list(module_ids),
        "resolved_module_ids": [mid for mid, module in zip(module_ids, modules) if module is not None],
        "unresolved_module_ids": unresolved,
        "status": "unresolved" if unresolved else "resolved",
    }
    if unresolved:
        return {
            "graph": {"nodes": [], "wires": [], "composition_request": request},
            "build_id": "generic_low_voltage_build",
            "notes": [],
            "warnings": [
                "Cannot auto-wire unidentified module IDs: " + ", ".join(str(mid) for mid in unresolved)
                + ". Supply an explicit netlist or a source-bound interface; donor pinouts are not inferred."
            ],
            "composition_status": request["status"],
            **{key: value for key, value in request.items() if key != "status"},
        }
    modules = [m for m in modules if m]
    if len(modules) < 2:
        return {
            "graph": {"nodes": [], "wires": [], "composition_request": request},
            "build_id": "generic_low_voltage_build",
            "notes": [],
            "warnings": ["Need at least two known module ids to compose a graph."],
            "composition_status": request["status"],
            **{key: value for key, value in request.items() if key != "status"},
        }
    recipe = auto_wire_picked_modules(modules)
    graph = _recipe_to_build_graph(recipe)
    notes = list(recipe.get("notes") or [])
    if auto_repair:
        # HS composing on its own does not hand out a design it can already see is broken.
        from .graph_patch import auto_repair_i2c

        graph, repair_notes = auto_repair_i2c(graph)
        notes.extend(repair_notes)
    return {
        "graph": {**graph, "composition_request": request},
        "build_id": "generic_low_voltage_build",
        "notes": notes,
        "warnings": [],
        "composition_status": request["status"],
        **{key: value for key, value in request.items() if key != "status"},
    }


def compose_build_graph_from_canvas_nodes(
    nodes: List[Mapping[str, str]],
) -> BuildGraph:
    specs: List[ModuleSpec] = []
    node_ids: List[str] = []
    unresolved = [str(node.get("moduleId") or "") for node in nodes if find_module(str(node.get("moduleId") or "")) is None]
    if unresolved:
        return {
            "nodes": [], "wires": [],
            "composition_request": {
                "requested_module_ids": [str(node.get("moduleId") or "") for node in nodes],
                "resolved_module_ids": [str(node.get("moduleId") or "") for node in nodes if find_module(str(node.get("moduleId") or "")) is not None],
                "unresolved_module_ids": unresolved,
                "requested_nodes": [dict(node) for node in nodes],
                "status": "unresolved",
            },
        }
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
