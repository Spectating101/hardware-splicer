"""A quantitative equipment design for a small, externally powered DC station.

This describes hardware and its interfaces. It does not claim that components
have been bought, wired, calibrated, or tested. INA228 is not an isolator.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

TI_DATASHEET = "https://www.ti.com/lit/ds/symlink/ina228.pdf"
SCHEMA = "hardware_splicer.dc_measurement_station.v1"
CAL_FACTOR = 13107.2e6  # TI SLYS021A section 8.1.2, ADCRANGE = 0.


@dataclass(frozen=True)
class StationSpec:
    nominal_voltage_v: float = 24.0
    maximum_bus_voltage_v: float = 24.0
    maximum_power_w: float = 120.0
    monitor_headroom_a: float = 7.5
    calibration_full_scale_a: float = 10.0
    shunt_ohm: float = 0.005
    shunt_rated_power_w: float = 2.0
    shunt_tolerance_percent: float = 0.1
    shunt_power_derating: float = 0.5
    shunt_value_basis: str = "Unprocured four-terminal candidate; nominal value, not a calibration"
    reference_shunt_ohm: float = 0.01
    reference_shunt_rated_power_w: float = 2.0
    reference_shunt_tolerance_percent: float = 0.1
    reference_shunt_value_basis: str = "Separate unprocured precision-shunt candidate; no independent instrument selected"

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name.endswith("_basis"):
                if not isinstance(value, str) or not value.strip() or len(value) > 500:
                    raise ValueError(f"{item.name} must be 1 to 500 characters")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{item.name} must be a finite number")
            if not 1e-12 <= value <= 1e9:
                raise ValueError(f"{item.name} must be positive and within numerical design bounds")
        if max(self.shunt_tolerance_percent, self.reference_shunt_tolerance_percent) >= 100 or self.shunt_power_derating > 1:
            raise ValueError("shunt tolerance must be below 100%; derating must be at most 1")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StationSpec":
        if not isinstance(value, dict) or set(value) - {f.name for f in fields(cls)}:
            raise ValueError("station spec must contain only documented StationSpec fields")
        return cls(**value)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def design_station(spec: StationSpec = StationSpec()) -> dict[str, Any]:
    """Calculate nominal and worst-tolerance margins without inventing ratings."""
    nominal_i = spec.maximum_power_w / spec.nominal_voltage_v
    worst_r = spec.shunt_ohm * (1 + spec.shunt_tolerance_percent / 100)
    requested_lsb = spec.calibration_full_scale_a / 2**19
    calibration = round(CAL_FACTOR * requested_lsb * spec.shunt_ohm)
    current_lsb = calibration / (CAL_FACTOR * spec.shunt_ohm)
    positive_range = current_lsb * (2**19 - 1)
    shunt_adc_range_a = 0.16384 / worst_r
    allowable_w = spec.shunt_rated_power_w * spec.shunt_power_derating
    nominal_loss = nominal_i**2 * worst_r
    headroom_loss = spec.monitor_headroom_a**2 * worst_r
    reference_r = spec.reference_shunt_ohm * (1 + spec.reference_shunt_tolerance_percent / 100)
    reference_headroom_loss = spec.monitor_headroom_a**2 * reference_r
    reference_allowable_w = spec.reference_shunt_rated_power_w * spec.shunt_power_derating
    total_drop = nominal_i * (worst_r + reference_r)
    checks = [
        ("nominal_bus", spec.nominal_voltage_v <= spec.maximum_bus_voltage_v,
         spec.nominal_voltage_v, spec.maximum_bus_voltage_v, "V", "nominal <= maximum bus"),
        ("ina228_bus_range", spec.maximum_bus_voltage_v <= 85,
         spec.maximum_bus_voltage_v, 85, "V", "maximum bus <= INA228 recommended bus range"),
        ("monitor_headroom", spec.monitor_headroom_a >= 1.5 * nominal_i,
         spec.monitor_headroom_a, 1.5 * nominal_i, "A", "monitor headroom >= 1.5 * P / V"),
        ("current_register_range", positive_range >= spec.monitor_headroom_a,
         positive_range, spec.monitor_headroom_a, "A", "effective positive current range >= monitor headroom"),
        ("shunt_adc_range", shunt_adc_range_a > spec.monitor_headroom_a,
         shunt_adc_range_a, spec.monitor_headroom_a, "A", "0.16384 / worst-tolerance R > monitor headroom"),
        ("shunt_dissipation", headroom_loss <= allowable_w,
         headroom_loss, allowable_w, "W", "I_headroom^2 * worst-tolerance R <= rated W * derating"),
        ("reference_shunt_dissipation", reference_headroom_loss <= reference_allowable_w,
         reference_headroom_loss, reference_allowable_w, "W", "I_headroom^2 * reference R_max <= reference rated W * derating"),
        ("combined_burden", total_drop < spec.nominal_voltage_v,
         total_drop, spec.nominal_voltage_v, "V", "I_nominal * (R_primary_max + R_reference_max) < nominal source voltage"),
        ("calibration_register", 1 <= calibration <= 0x7FFF,
         calibration, 0x7FFF, "register count", "1 <= SHUNT_CAL <= 32767"),
    ]
    findings = [{"id": name, "passed": bool(passed), "actual": actual, "limit": limit,
                 "unit": unit, "equation": equation}
                for name, passed, actual, limit, unit, equation in checks]
    parts = [
        {"ref": "PS1", "item": "External isolated, current-limited DC bench source",
         "requirement": f"0 to {spec.maximum_bus_voltage_v:g} V; {spec.maximum_power_w:g} W working envelope",
         "unresolved": "Exact source, isolation/earthing, output current limit and fault behavior"},
        {"ref": "F1", "item": "DC fuse and accessible manual disconnect before the shunt",
         "requirement": "Coordinate with supply short-circuit current, conductors, connectors and load",
         "unresolved": "Part, DC interrupt rating, time-current curve, inrush and fault-energy coordination"},
        {"ref": "RSH1", "item": "Separate four-terminal current shunt",
         "requirement": f"{spec.shunt_ohm:g} ohm; {spec.shunt_rated_power_w:g} W stated rating; {spec.shunt_tolerance_percent:g}% stated tolerance",
         "unresolved": "Exact part, Kelvin terminals, rating conditions, temperature coefficient, resistance measurement and mounting"},
        {"ref": "U1", "item": "TI INA228 monitor or documented external-shunt carrier",
         "requirement": "3.3 V logic supply; ADCRANGE=0; no onboard shunt in parallel with RSH1",
         "unresolved": "Exact carrier schematic, routing, connector pin order and thermal/mechanical dimensions"},
        {"ref": "RSH2", "item": "Distinct four-terminal precision shunt for the independent reference",
         "requirement": f"{spec.reference_shunt_ohm:g} ohm; {spec.reference_shunt_rated_power_w:g} W stated rating; {spec.reference_shunt_tolerance_percent:g}% stated tolerance",
         "unresolved": "Independent calibration, part, temperature coefficient, mounting and four-wire connections"},
        {"ref": "J1/J2", "item": "Covered, polarized source/load connectors and power conductors",
         "requirement": f"Working current >= {spec.monitor_headroom_a:g} A; working voltage >= {spec.maximum_bus_voltage_v:g} V before chosen derating",
         "unresolved": "Exact parts, wire gauge/length, contact loss, temperature rise and strain relief"},
        {"ref": "C1/RPU", "item": "Local VS bypass and I2C pull-ups",
         "requirement": "100 nF near VS/GND; calculate SDA/SCL pull-ups for actual capacitance and existing pull-ups, 3.3 V only",
         "unresolved": "Carrier fitted parts, I2C edge timing and actual pull-up rail"},
        {"ref": "REF", "item": "Independent voltage/current reference logger",
         "requirement": "Paired load-voltage and RSH2 differential-voltage inputs with documented common-mode capability",
         "unresolved": "Actual instrument, dual-input or scan timing, input isolation/common-mode, calibration, UTC alignment and uncertainty"},
    ]
    wiring = [
        ("PS1.+", "F1.input", "power", "Upstream source protection"),
        ("F1.output", "RSH1.power+", "power", "High-side source terminal"),
        ("RSH1.power-", "RSH2.power+", "power", "The primary and independent reference shunts carry the same series load current"),
        ("RSH2.power-", "J2.load+", "power", "Both shunt burdens are upstream of the measured load boundary"),
        ("PS1.-", "J2.load-", "power", "Dedicated load return, separate from sense conductors"),
        ("RSH1.sense+", "U1.IN+ (pin 10)", "Kelvin sense", "Separate sense conductor at source-side shunt terminal"),
        ("RSH1.sense-", "U1.IN- (pin 9)", "Kelvin sense", "Separate sense conductor at load-side shunt terminal"),
        ("J2.load+", "U1.VBUS (pin 8)", "voltage sense", "Voltage measurement at load boundary; includes no shunt loss"),
        ("J2.load-", "U1.GND (pin 7)", "sense return", "Common reference; INA228 is not galvanically isolated"),
        ("RSH2.sense+", "REF.shunt high", "reference Kelvin sense", "Separate reference pair; instrument must accept the load common-mode voltage"),
        ("RSH2.sense-", "REF.shunt low", "reference Kelvin sense", "Do not join to return; high-side differential measurement"),
        ("J2.load+", "REF.voltage high", "reference voltage sense", "Same load boundary as INA228 VBUS"),
        ("J2.load-", "REF.voltage low", "reference voltage sense", "Record voltage/shunt channel pairing and any scan time offset"),
        ("3V3.logic", "U1.VS (pin 6)", "logic power", "100 nF bypass to U1.GND at the device"),
        ("host.SDA", "U1.SDA (pin 4)", "I2C", "Open drain; pull up only to 3.3 V"),
        ("host.SCL", "U1.SCL (pin 5)", "I2C", "Start at 100 kHz; check bus capacitance and edges"),
        ("host.GND", "U1.GND (pin 7)", "logic reference", "A direct host connection may earth the DC circuit"),
        ("U1.A0 (pin 2), U1.A1 (pin 1)", "U1.GND", "address straps", "0x40, verify carrier straps; ALERT pin 3 unused, status polled"),
    ]
    return {
        "schema_version": SCHEMA,
        "name": "DC measurement station with independent reference interface",
        "spec": asdict(spec), "design_checks_passed": all(f["passed"] for f in findings),
        "physical_status": "UNBUILT_UNVERIFIED", "parts_status": "UNPROCURED_CANDIDATES",
        "scope": "Externally isolated DC source; no batteries, mains wiring or grid connection in the station",
        "isolation": {"monitor_is_galvanically_isolated": False,
                      "host_barrier": "Not provided. Specify and verify an isolator plus isolated power if floating operation is required."},
        "calculations": {"nominal_current_a": nominal_i, "monitor_headroom_a": spec.monitor_headroom_a,
                         "worst_tolerance_shunt_ohm": worst_r,
                         "nominal_shunt_drop_v": nominal_i * worst_r,
                         "headroom_shunt_drop_v": spec.monitor_headroom_a * worst_r,
                         "nominal_shunt_dissipation_w": nominal_loss,
                         "headroom_shunt_dissipation_w": headroom_loss,
                         "derated_shunt_power_w": allowable_w,
                         "reference_headroom_shunt_dissipation_w": reference_headroom_loss,
                         "reference_derated_shunt_power_w": reference_allowable_w,
                         "combined_nominal_shunt_drop_v": total_drop,
                         "combined_nominal_shunt_loss_w": nominal_i * total_drop,
                         "load_voltage_at_nominal_source_v": spec.nominal_voltage_v - total_drop,
                         "load_power_at_nominal_current_w": nominal_i * (spec.nominal_voltage_v - total_drop),
                         "shunt_adc_current_range_a": shunt_adc_range_a,
                         "current_positive_range_a": positive_range},
        "ina228_configuration": {"config": 0, "adc_config": 0x3B6A,
                                 "shunt_cal": calibration, "shunt_tempco": 0,
                                 "current_lsb_a": current_lsb, "shunt_lsb_v": 312.5e-9,
                                 "bus_lsb_v": 195.3125e-6, "i2c_address": 0x40,
                                 "conversion": "Triggered bus + shunt, 1052 us each, 16 averages",
                                 "nominal_conversion_seconds": 0.033664,
                                 "energy_register_used": False},
        "measurement_boundary": "Both voltage channels measure at J2 after both shunts. Load energy excludes both shunt losses; 120 W is the source-envelope ceiling, not guaranteed delivered load power.",
        "runtime_limit_boundary": "Logger voltage/power checks apply only at J2. The program cannot enforce upstream source voltage, power or fault limits and does not disconnect the load.",
        "checks": findings, "parts": parts,
        "wiring": [{"from": a, "to": b, "role": role, "note": note} for a, b, role, note in wiring],
        "mechanical": {"status": "Dimensioned fixture pending exact component measurements",
                       "requirements": ["Covered power terminals with separate strain relief for source and load",
                                        "Keep shunt heat away from logic, plastic supports and reference sensors",
                                        "Route twisted Kelvin pair separately from load conductors",
                                        "Provide accessible fuse/disconnect and labeled reference test points",
                                        "Measure actual hole patterns and cable bend radii before CAD/export"]},
        "unresolved": ["Source/host isolation and earth continuity", "Fuse and wire fault coordination",
                       "Exact carrier and shunt sourcing", "Thermal rise and touch-safe covers",
                       "Traceable current/voltage calibration and temperature effects",
                       "Independent reference instrument and shared measurement boundary",
                       "UTC clock synchronization and sampling uncertainty", "Actual I2C, load and loss-of-power tests"],
        "source": {"url": TI_DATASHEET, "document": "TI SLYS021A, revision A, May 2022",
                   "sections": ["5 pin functions", "6.3 recommended operation", "7.6 registers", "8.1.2 calibration", "10.1 Kelvin layout"]},
    }


def write_design(out: Path, spec: StationSpec = StationSpec()) -> dict[str, Any]:
    """Write a reviewable equipment package into a new directory."""
    design = design_station(spec)
    out.mkdir(parents=True, exist_ok=False)
    (out / "station-design.json").write_bytes(json_bytes(design))
    for filename, columns, rows in (
        ("wiring.csv", ("from", "to", "role", "note"), design["wiring"]),
        ("parts.csv", ("ref", "item", "requirement", "unresolved"), design["parts"]),
    ):
        import csv
        with (out / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    (out / "README.md").write_text(
        "# DC measurement station\n\n"
        "See station-design.json for calculations, checks and remaining physical work; parts.csv and wiring.csv are the assembly interface.\n\n"
        "The source must be externally isolated. INA228 itself and a direct I2C host connection provide no isolation.\n"
        "This is an unbuilt candidate equipment design. The parts, thermal behavior, wiring and calibration have not been verified.\n"
        "The logger records actual triggered conversions when manually run on a configured Linux I2C bus. It does not switch or disconnect load power.\n"
        f"\nPrimary component source: {TI_DATASHEET}\n", encoding="utf-8")
    return design
