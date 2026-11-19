"""Scoreable digital design decisions. Run from the HS checkout (see README)."""
import argparse
from configparser import ConfigParser
from hashlib import sha256
import json
from math import degrees
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from hardware_splicer.part_substitution import evaluate_substitution
from hardware_splicer.robot_model_import import parse_robot_model

HERE = Path(__file__).resolve().parent


def read_inputs(cache, fetch):
    result = {}
    for file, source in json.loads((HERE / "inputs.json").read_text()).items():
        path = cache / file
        if not path.exists() and fetch:
            url = "https://raw.githubusercontent.com/{repo}/{revision}/".format(**source) + quote(source["path"])
            with urlopen(url, timeout=45) as response:
                data = response.read()
            if sha256(data).hexdigest() != source["sha256"]:
                raise ValueError(f"Unexpected download for {file}")
            cache.mkdir(exist_ok=True, parents=True)
            path.write_bytes(data)
        data = path.read_bytes()
        if sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Unexpected design revision for {file}")
        result[file] = data
    return result


def verdict(question, decision):
    return {"claim": question, "prediction": "unresolved" if decision is None else "yes" if decision else "no"}


def printer(inputs):
    # The slicer file contains many non-printer settings. Only follow the chosen
    # printer and its parents. Refuse non-rectangular or offset build plates.
    text = inputs["preset.ini"].decode()
    cfg = ConfigParser(interpolation=None, strict=False)
    cfg.read_string(text)
    name = "Original Prusa i3 MK3S & MK3S+"
    chain, values = [], {}
    while name:
        if name in chain:
            raise ValueError("Cyclic printer preset")
        chain.append(name)
        section = cfg["printer:" + name]
        for key in ("bed_shape", "max_print_height"):
            if key in section:
                values.setdefault(key, section[key])
        name = section.get("inherits")
    points = {tuple(map(float, pt.split("x"))) for pt in values["bed_shape"].split(",")}
    width, depth = (max(axis) for axis in zip(*points))
    if points != {(0, 0), (width, 0), (0, depth), (width, depth)}:
        raise ValueError("Expected rectangular bed with zero origin")
    size = [width, depth, float(values["max_print_height"])]
    firmware = inputs["printer.h"].decode()
    travel = {axis: float(re.search(rf"^#define {axis}_MAX_POS\s+([\d.]+)", firmware, re.M)[1]) for axis in "XYZ"}
    claims = {}
    for ident, dims in {"tray": [245, 205, 20], "wide": [252, 100, 20], "tower": [100, 100, 211]}.items():
        part = {"part_id": "print", "name": "Declared part", "position_mm": [0, 0, 0]}
        result = evaluate_substitution({"parts": [part], "replace_part_id": "print",
                                       "candidate": {**part, "dimensions_mm": dims},
                                       "enclosure": {"minimum_mm": [0, 0, 0], "maximum_mm": size}})
        fit, = [row for row in result["checks"] if row["code"] == "enclosure_fit"]
        claims[ident] = verdict(f"{dims} mm fits the nominal build volume in the specified orientation", fit["status"] == "pass")
    return {"preset_chain": chain, "print_volume_mm": size, "firmware_max_pos_mm": travel, "cases": claims}


def arm(inputs):
    model = parse_robot_model(inputs["arm.urdf"], "urdf")
    # Number movable axes from the base along the single kinematic chain.
    parents = {j.parent_link_id for j in model.joints}
    base, = parents - {j.child_link_id for j in model.joints}
    chain = []
    while base in parents:
        joint, = [j for j in model.joints if j.parent_link_id == base]
        if joint.joint_type.value == "revolute":
            chain.append(joint)
        base = joint.child_link_id
    limits = [[round(degrees(j.limits[k]), 3) for k in ("lower", "upper")] for j in chain]
    claims = {}
    for ident, n, angle in [("j2_135", 2, 135), ("j2_145", 2, 145), ("j6_175", 6, 175)]:
        lower, upper = limits[n - 1]
        claims[ident] = verdict(f"J{n} target +{angle} degrees is within the nominal axis range", lower <= angle <= upper)
    claims["payload"] = verdict("A 300 g tool is within the nominal rated payload", None)
    return {"ordered_joints": [j.name for j in chain], "urdf_limits_deg": limits, "cases": claims}


def pads(data):
    root = ET.fromstring(data)
    pins = {}
    for signal in root.findall("./drawing/board/signals/signal"):
        for terminal in signal.findall("contactref"):
            part = pins.setdefault(terminal.attrib["element"], {})
            pin = terminal.attrib["pad"]
            if pin in part:
                raise ValueError("Duplicate PCB pad")
            part[pin] = signal.attrib["name"]
    return pins


def console(inputs):
    pins = pads(inputs["console.brd"])
    sd, flash, buttons = (pins[ref] for ref in ("X5", "U1", "IC1"))
    sd_bus = [sd[pin] for pin in ("3", "7", "5")]
    flash_bus = [flash[pin] for pin in ("5", "2", "3", "7", "6")]
    controls = [buttons[pin] for pin in ("9", "2", "1")]
    shift_register = ET.fromstring(inputs["console.brd"]).find("./drawing/board/elements/element[@name='IC1']")
    serial_buttons = (shift_register.attrib["value"].startswith("74165")
                      and controls == ["BUTTON_OUT", "BUTTON_CLK", "BUTTON_LATCH"])
    return {"card_cs": sd["2"], "card_nets": sd_bus, "flash_nets": flash_bus, "button_control": controls, "cases": {
        "sd_d4": verdict("Use D4 as the stock microSD chip select", sd["2"] == "D4_SDCS"),
        "shared_flash": verdict("The built-in flash shares the microSD clock net", flash["6"] == sd["5"]),
        "i2c_buttons": verdict("Use an I2C GPIO-expander driver for the four digital buttons", False if serial_buttons else None),
    }}


def logger(inputs):
    pins = pads(inputs["logger.brd"])
    mcu, imu = pins["U8"], pins["U13"]
    by_net = {net: pad for pad, net in mcu.items() if net in {"MICROSD_!CS!", "QWIIC_PWR", "MICROSD_PWR", "ICM_!CS!"}}
    signals = [imu[pin] for pin in ("22", "23", "24", "9")]
    return {"imu_signals": signals, "mcu_pads": by_net, "cases": {
        "spi_imu": verdict("The stock motion sensor communicates over SPI", all(net.endswith(suffix) for net, suffix in
                           zip(signals, ("!CS!", "SCK", "SDI", "SDO"), strict=True))),
        "sd_d10": verdict("Use Artemis D10 as the onboard microSD chip select", by_net["MICROSD_!CS!"].strip("~") == "D10"),
        "separate_power": verdict("Firmware has separate control lines for Qwiic and microSD power",
                                  by_net["QWIIC_PWR"] != by_net["MICROSD_PWR"]),
    }}


def amplifier(inputs):
    pins = pads(inputs["amp.brd"])
    terminals = [pins[ref][n] for ref in ("J2", "J3") for n in ("1", "2")]
    # Each output terminal connects through its own ferrite to an amplifier output.
    chip_nets = set(pins["U1"].values()) - {"GND", "AGND", "VDD", "3.3V"}
    for net in terminals:
        bead, = [pins[f"FB{i}"] for i in range(2, 6) if net in pins[f"FB{i}"].values()]
        if not (set(bead.values()) - {net}) & chip_nets:
            raise ValueError("Cannot trace the output to the amplifier")
    return {"speaker_terminal_nets": terminals, "input_jack": pins["X2"], "cases": {
        "shared_return": verdict("A three-wire stereo speaker harness preserves the two output circuits",
                                 False if len(set(terminals)) == 4 else None),
        "line_input": verdict("An analog stereo input can be fed through the 3.5 mm jack",
                              {"LEFTIN", "RIGHTIN", "AGND"} <= set(pins["X2"].values())),
        "donor_condition": verdict("An unmarked salvaged speaker is within the allowed impedance range", None),
    }}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    inputs = read_inputs(args.directory, args.fetch)
    print(json.dumps({f.__name__: f(inputs) for f in (printer, arm, console, logger, amplifier)}, indent=2, sort_keys=True))
