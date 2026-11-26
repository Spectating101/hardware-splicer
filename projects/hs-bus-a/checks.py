"""HS-BUS-A electrical checks from datasheet figures (each quoted with its source), against HS-ARM-A's loads.

Logic levels: every driver's guaranteed output against its receiver's guaranteed input threshold. Current: connector,
fuse and copper ratings against the arm's currents. Voltage: part ratings against the supply and the servos' ranges.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SRC = {
    "ft232r": "FTDI DS_FT232R v2.07, Table 5.3 (VCCIO = 5.0 V) and Table 5.2; read from https://cdn-shop.adafruit.com/datasheets/DS_FT232R.pdf",
    "ahct125": "TI SCLS378P (SN74AHCT1G125), 5.3 and 5.5; https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf",
    "ahct126": "TI SCLS380L (SN74AHCT1G126), 5.3 and 5.5; https://www.ti.com/lit/ds/symlink/sn74ahct1g126.pdf",
    "lvc2g241": "TI SN74LVC2G241, Recommended Operating Conditions; https://www.ti.com/lit/ds/symlink/sn74lvc2g241.pdf",
    "robotis_ttl": "ROBOTIS TTL communication circuit (ttl_circuit.png, X-series e-manual)",
    "jst_eh": "JST EH catalogue: 'Current rating: 3 A AC/DC (AWG #22)'; https://www.jst-mfg.com/product/pdf/eng/eEH.pdf",
    "mfmsmf": "Bourns MF-MSMF series rev. BE: MF-MSMF250/16X Vmax 16 V, Ihold 2.50 A, Itrip 5.00 A, R1max 0.100 ohm; "
              "https://www.bourns.com/docs/Product-Datasheets/mfmsmf.pdf",
    "smbj": "Vishay SMBJ series doc. 88392 (09-Jan-2024): SMBJ15(C)A VWM 15 V, VBR 16.7-18.5 V, VC 24.4 V at IPPM 24.6 A; "
            "https://www.vishay.com/docs/88392/smbj.pdf",
    "tpd2e2u06": "TI SLLSEG9C (TPD2E2U06): VRWM 5.5 V; https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf",
    "servos": "src/hardware_splicer/data/actuators/cited_servos_20261126.json (ROBOTIS e-manual figures)",
    "arm": "projects/hs-arm-a/verification.json power",
}

# Guaranteed figures (min VOH / max VOL at the stated load; min VIH / max VIL) quoted from the sources above.
DRIVERS = {
    "FT232R TXD/CBUS2 at VCCIO 5 V": {"voh_min": 3.2, "vol_max": 0.6, "load": "2 mA", "src": "ft232r"},
    "74AHCT1G125/126 Y at VCC 4.5 V": {"voh_min": 3.94, "vol_max": 0.44, "load": "8 mA", "src": "ahct125"},
}
RECEIVERS = {
    "74AHCT1G125/126 input at VCC 4.5-5.5 V": {"vih_min": 2.0, "vil_max": 0.8, "src": "ahct125"},
    "74LVC2G241 input at VCC 5 V (ROBOTIS reference)": {"vih_min": 0.7 * 5.0, "vil_max": 0.3 * 5.0, "src": "lvc2g241"},
    "FT232R RXD at VCCIO 5 V (switching threshold max)": {"vih_min": 1.5, "vil_max": 1.0, "src": "ft232r"},
}
LINKS = [
    ("TXD: FT232R -> 74AHCT1G126 A", "FT232R TXD/CBUS2 at VCCIO 5 V", "74AHCT1G125/126 input at VCC 4.5-5.5 V"),
    ("TXDEN: FT232R CBUS2 -> 74AHCT1G126 OE, 74AHCT1G125 OE#", "FT232R TXD/CBUS2 at VCCIO 5 V", "74AHCT1G125/126 input at VCC 4.5-5.5 V"),
    ("RXD: 74AHCT1G125 Y -> FT232R RXD", "74AHCT1G125/126 Y at VCC 4.5 V", "FT232R RXD at VCCIO 5 V (switching threshold max)"),
    ("ROBOTIS reference: FT232R TXD -> 74LVC2G241 A2 at 5 V", "FT232R TXD/CBUS2 at VCCIO 5 V", "74LVC2G241 input at VCC 5 V (ROBOTIS reference)"),
]


def ipc2221_external_dt(current_a: float, width_mm: float, copper_um: float = 35.0) -> float:
    """Temperature rise (C) of an outer-layer track by the IPC-2221 chart fit I = 0.048 dT^0.44 A^0.725, A in mil^2."""
    area_mil2 = (width_mm / 0.0254) * (copper_um / 25.4)
    return (current_a / (0.048 * area_mil2 ** 0.725)) ** (1 / 0.44)


def logic_levels() -> list[dict]:
    rows = []
    for name, drv, rcv in LINKS:
        d, r = DRIVERS[drv], RECEIVERS[rcv]
        high, low = d["voh_min"] - r["vih_min"], r["vil_max"] - d["vol_max"]
        rows.append({"link": name, "driver": drv, "receiver": rcv, "high_margin_v": round(high, 2), "low_margin_v": round(low, 2),
                     "guaranteed": high >= 0 and low >= 0, "driver_load_in_spec": d["load"],
                     "sources": sorted({SRC[d["src"]], SRC[r["src"]]})})
    return rows


def currents(port_track_mm: float, vin_track_mm: float = 2.5) -> dict:
    arm = json.loads((ROOT / "projects/hs-arm-a/verification.json").read_text())["power"]
    hold_a, ptc_hold, ptc_trip, jst = 2.5, 2.5, 5.0, 3.0
    return {
        "per_port": {
            "connector_rating_a": jst, "fuse_hold_a": ptc_hold, "fuse_trip_a": ptc_trip,
            "fuse_hold_within_connector_rating": ptc_hold <= jst,
            "note": "Between 2.5 A and 5.0 A the fuse may or may not trip (Bourns: hold and trip at 23 C); the JST contact is "
                    "rated 3 A. A sustained load in that band is not guaranteed to be cut.",
            "track_mm": port_track_mm,
            "track_rise_c_at_hold": round(ipc2221_external_dt(hold_a, port_track_mm), 1),
            "track_rise_c_at_trip": round(ipc2221_external_dt(ptc_trip, port_track_mm), 1),
            "track_basis": "IPC-2221 outer-layer fit, 1 oz (35 um) copper assumed",
            "fuse_drop_v_at_hold_max": round(ptc_hold * 0.100, 2),
            "sources": [SRC["jst_eh"], SRC["mfmsmf"]],
        },
        "input_trunk": {
            "track_mm": vin_track_mm, "supply_a": 5.0, "supply_basis": "BOM supply: ROBOTIS SMPS 12 V 5 A",
            "track_rise_c_at_supply_max": round(ipc2221_external_dt(5.0, vin_track_mm), 1),
            "track_basis": "IPC-2221 outer-layer fit, 1 oz (35 um) copper assumed",
        },
        "arm": {
            "holding_stretched_a": arm["holding_a_stretched"], "all_stalled_a": arm["all_stalled_a"],
            "one_port_holds_arm": arm["holding_a_stretched"] <= ptc_hold,
            "ports_needed_for_all_stalled": math.ceil(arm["all_stalled_a"] / ptc_hold),
            "advice": "Run the arm on two ports (base yaw + shoulder + elbow on one, the wrist and gripper on another) so a "
                      "chain's normal current stays well under 2.5 A; a full stall of every joint trips the fuses, which is "
                      "the intended protection. ROBOTIS servos also have their own overload shutdown.",
            "source": SRC["arm"],
        },
    }


def voltages(supply_v: float = 12.0) -> dict:
    servos = {s["id"]: s for s in json.loads((ROOT / "src/hardware_splicer/data/actuators/cited_servos_20261126.json").read_text())["servos"]}
    xm, xl = servos["dynamixel-xm430-w350"]["input_voltage_v"], servos["dynamixel-xl430-w250-t"]["input_voltage_v"]
    window = (max(xm[0], xl[0]), min(xm[1], xl[1]))
    return {
        "servo_window_v": {"xm430": xm, "xl430": xl, "common": list(window), "source": SRC["servos"]},
        "supply_v": supply_v,
        "supply_inside_window": window[0] <= supply_v <= window[1],
        "supply_at_window_edge": math.isclose(supply_v, window[1]),
        "supply_note": "12 V is the XL430's maximum input; a supply that regulates high (or a 3S pack at 12.6 V full charge) "
                       "exceeds it. Use a supply set to 12.0 V or below, or 11.1 V nominal.",
        "tvs": {"part": "SMBJ15CA", "standoff_v": 15.0, "clamp_v_at_ippm": 24.4,
                "standoff_above_supply": 15.0 > supply_v,
                "clamps_below_servo_max": 24.4 <= window[1],
                "note": "The TVS absorbs fast surges (hot-plug, regeneration spikes); it clamps above every servo's rated "
                        "input, so it is not overvoltage protection for a wrong supply.", "source": SRC["smbj"]},
        "fuse_vmax_v": 16.0, "fuse_vmax_ok": 16.0 >= supply_v,
        "bulk_cap_v": 25.0, "bulk_cap_derating": round(25.0 / supply_v, 2),
        "usb_esd": {"part": "TPD2E2U06", "vrwm_v": 5.5, "ok_for_usb_data": True, "source": SRC["tpd2e2u06"]},
        "reverse_polarity": "not protected: the screw terminal is unkeyed. Check polarity before connecting the supply.",
    }


def run(port_track_mm: float, vin_track_mm: float = 2.5) -> dict:
    levels = logic_levels()
    return {"logic_levels": levels,
            "logic_levels_pass": all(r["guaranteed"] for r in levels if not r["link"].startswith("ROBOTIS reference")),
            "currents": currents(port_track_mm, vin_track_mm), "voltages": voltages(),
            "half_duplex_circuit": {"basis": SRC["robotis_ttl"],
                                    "kept": "two tri-state buffers on one DATA line, direction from a transmit-enable line "
                                            "(high = transmit), 10 kOhm pull-ups to 5 V on DATA and RXD, 10 kOhm pull-down on "
                                            "the enable",
                                    "changed": "74LVC2G241 -> 74AHCT1G126 (transmit) + 74AHCT1G125 (receive), because the "
                                               "FT232R's guaranteed 3.2 V high is below the LVC part's 3.5 V input high at 5 V",
                                    "added_from_pollen": "Data-line protection as in Pollen Robotics' production converter "
                                                         "(github.com/pollen-robotics/elec_grabette, Apache-2.0): 150 ohm series, "
                                                         "5.1 V Zener clamp, 100 ohm PTC (Murata PRG18BB101MB1RB, 24 V) toward the "
                                                         "connectors, so 12 V on the data pin cannot reach the buffers",
                                    "direction_source": "FT232R CBUS2, factory default TXDEN (DS_FT232R Table 3.x: 'Factory "
                                                        "default configuration is TXDEN'), so no EEPROM programming"}}
