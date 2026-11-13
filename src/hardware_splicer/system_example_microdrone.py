"""Offline cross-discipline assessment of HS microdrone system example 001.

All outputs are engineering *proposals*. No telemetry, firmware, simulation or
physical device is invoked. Calculations on illustrative inputs never promote
a project to flight, fabrication, firmware flashing or power-on authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "hardware_splicer.microdrone_system_assessment.v1"
BASELINE = "Crazyflie 2.1+"
G = 9.80665


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    v = float(value)
    if not math.isfinite(v) or v < minimum:
        raise ValueError(f"{label} must be finite and >= {minimum}")
    return v


def _required(body: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    result = body.get(key)
    if not isinstance(result, dict):
        raise ValueError(f"Missing structured {key}")
    return result


def _source_bytes(data: Mapping[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def assess_microdrone(
    design: Mapping[str, Any], *,
    guidance_scenario: Mapping[str, Any],
) -> dict[str, Any]:
    """Use existing HS Crazyflie guidance case without inheriting verification."""

    if design.get("schema_version") != "hardware_splicer.microdrone_design.v1":
        raise ValueError("Unexpected microdrone input schema")
    baseline = _required(design, "baseline")
    requirements = _required(design, "requirements")
    candidate = _required(design, "candidate")
    if baseline.get("model") != BASELINE or baseline.get("manufacturer") != "Bitcraze":
        raise ValueError("Example 001 requires the correct Crazyflie 2.1+ reference identity")
    if baseline.get("reference_guidance_scenario") != guidance_scenario.get("scenario_id"):
        raise ValueError("Scenario cross-reference has drifted")
    if guidance_scenario.get("reference_project") != BASELINE:
        raise ValueError("Guidance reference is a different hardware variant")
    if int(_number(baseline.get("motor_count"), "motor count")) != 4:
        raise ValueError("This quadcopter fixture must preserve four motor identities")
    vendor_mass = _number(baseline.get("stock_takeoff_mass_g"), "vendor mass")
    vendor_payload = _number(baseline.get("vendor_max_recommended_payload_g"), "vendor payload")
    vendor_voltage = _number(baseline.get("vendor_expansion_vcc_v"), "vendor VCC")
    vendor_current = _number(baseline.get("vendor_expansion_vcc_max_ma"), "vendor VCC current")
    max_mass = _number(requirements.get("max_added_deck_mass_g"), "project mass limit")
    max_current = _number(requirements.get("max_deck_peak_current_ma"), "project current limit")
    scenario_constraints = _required(_required(guidance_scenario, "intake"), "constraints")
    if max_mass > _number(scenario_constraints.get("deck_mass_limit_g"), "guidance deck mass limit"):
        raise ValueError("User project policy exceeds existing guidance-mass bound")
    if max_current > _number(scenario_constraints.get("deck_current_limit_ma"), "guidance current limit"):
        raise ValueError("User project policy exceeds existing guidance-current bound")

    mass_field = _required(candidate, "proposed_deck_mass_g")
    current_field = _required(candidate, "proposed_deck_peak_current_ma")
    voltage_field = _required(candidate, "deck_vcc_v")
    deck_mass = _number(mass_field.get("value"), "candidate mass")
    peak_ma = _number(current_field.get("value"), "candidate current")
    deck_voltage = _number(voltage_field.get("value"), "deck VCC")
    for label, field in (("mass", mass_field), ("current", current_field), ("voltage", voltage_field)):
        if field.get("measured") is not False:
            raise ValueError(f"Example only accepts unmeasured {label}; measured evidence needs its own receipt")
        if not field.get("basis"):
            raise ValueError(f"Missing {label} estimate provenance")

    ee = _required(candidate, "electrical")
    mecha = _required(candidate, "mechanical")
    firmware = _required(candidate, "firmware")
    simulation = _required(candidate, "simulation")
    components = candidate.get("components")
    if not isinstance(components, list) or len(components) < 3:
        raise ValueError("System BOM incomplete")
    ids = [item.get("identity") for item in components if isinstance(item, dict)]
    if len(ids) != len(components) or len(set(ids)) != len(ids):
        raise ValueError("BOM component identity must be unique and complete")
    if not {"BME688", "DS28E05", "deck connector"}.issubset(set(ids)):
        raise ValueError("Missing sensor, identity memory or deck connection")

    preliminary = {
        "reference_motor_count_preserved": True,
        "estimated_deck_mass_within_project_limit": deck_mass <= max_mass,
        "estimated_deck_mass_within_vendor_payload": deck_mass <= vendor_payload,
        "estimated_deck_current_within_project_limit": peak_ma <= max_current,
        "estimated_deck_current_within_vendor_rail_limit": peak_ma <= vendor_current,
        "deck_rail_nominal_voltage_matches_reference": math.isclose(
            deck_voltage, vendor_voltage, abs_tol=1e-6
        ),
        "emergency_disarm_is_required": requirements.get("preserve_emergency_disarm") is True,
        "propeller_guard_is_required": requirements.get("require_propeller_guards") is True,
        "simulation_validation_is_required": requirements.get("require_simulator_validation") is True,
    }
    project_failures = [key for key, ok in preliminary.items() if not ok]
    hard_blockers = list(project_failures)
    outstanding = {
        "electrical_parts_voltage_and_currents": (
            ee.get("parts_voltage_compatibility_verified") is True
            and ee.get("power_measurements_available") is True
        ),
        "deck_pinout_and_native_eda": (
            ee.get("connector_pin_mapping_verified") is True
            and ee.get("native_schematic_and_board_files_available") is True
        ),
        "physical_module_and_propeller_clearances": (
            mecha.get("mount_geometry_measured") is True
            and mecha.get("propeller_deck_clearance_measured") is True
            and mecha.get("center_of_mass_measured") is True
        ),
        "guards_physically_confirmed": mecha.get("installed_propeller_guards_verified") is True,
        "flight_firmware_revisions_and_watchdog": (
            bool(firmware.get("flight_controller_source_revision"))
            and bool(firmware.get("radio_firmware_source_revision"))
            and firmware.get("deck_driver_build_passed") is True
            and firmware.get("watchdog_and_disarm_regression_passed") is True
        ),
        "validated_dynamics_in_simulator": (
            bool(simulation.get("simulator_version"))
            and simulation.get("validated_model_parameters") is True
            and simulation.get("dynamic_model_executed") is True
        ),
    }
    for key, value in outstanding.items():
        if not value:
            hard_blockers.append("unverified_" + key)
    # Require external independent observation; a malicious declaration of true
    # cannot by itself unlock any physical authority.
    hard_blockers.extend([
        "actual_material_and_mounting_measurements_missing",
        "independent_battery_motor_and_thrust_test_missing",
        "reviewed_hil_and_hardware_failsafe_test_missing",
        "independent_assembly_and_propeller_safety_review_missing",
    ])

    gross_mass = vendor_mass + deck_mass
    static_hover_per_motor_n = gross_mass / 1000.0 * G / 4
    envelope = {
        "baseline_mass_g": vendor_mass,
        "proposed_deck_mass_g": deck_mass,
        "proposed_total_mass_g": round(gross_mass, 4),
        "estimated_hover_load_per_motor_n": round(static_hover_per_motor_n, 6),
        "hover_load_assumption": "Static force equilibrium divided evenly over 4 rotors, not measured thrust or a flight dynamics simulation",
        "vendor_max_recommended_payload_g": vendor_payload,
        "project_mass_headroom_g": round(max_mass-deck_mass, 4),
        "project_deck_current_headroom_ma": round(max_current-peak_ma, 4),
        "vendor_deck_current_headroom_ma": round(vendor_current-peak_ma, 4),
        "estimated_deck_electrical_power_w": round(deck_voltage*peak_ma/1000.0, 6),
        "flight_time_projection_min": None,
        "flight_time_reason": "Additional flight consumption and motor thrust/current curves were not independently measured",
        "mass_sensitivity": [
            {"added_mass_g": x, "ideal_hover_force_per_motor_n": round((vendor_mass+x)*G/4000, 6)}
            for x in (0.0, deck_mass, max_mass)
        ],
    }
    return {
        "schema_version": SCHEMA,
        "system_example_id": design["id"],
        "baseline_identity": BASELINE,
        "source_design_sha256": hashlib.sha256(_source_bytes(design)).hexdigest(),
        "source_guidance_sha256": hashlib.sha256(_source_bytes(guidance_scenario)).hexdigest(),
        "requirements": dict(requirements),
        "discipline_status": {
            "electrical": "catalog_architecture_only",
            "firmware": "upstream_reference_not_built",
            "mechanical": "envelope_only_not_cad",
            "physical": "analytical_static_equilibrium_only",
            "flight_control": "upstream_reference_not_simulated",
            "manufacturing": "not_prepared",
        },
        "mass_and_power": envelope,
        "preliminary_declared_estimate_checks": preliminary,
        "preliminary_checks_pass": not project_failures,
        "independent_evidence_obligations": outstanding,
        "blockers": sorted(set(hard_blockers)),
        "reviewable_architecture": {
            "parts": [{"identity": item["identity"], "quantity": item["quantity"], "role": item["role"],
                       "vendor_electrical_identity_verified": item.get("exact_board_or_die_and_electrical_characteristics_verified") is True}
                      for item in components],
            "interfaces": [
                {"name": "sensor_deck_power", "from": "Crazyflie VCC 3.0V", "to": "deck candidate VCC",
                 "net_mapping_verified": False},
                {"name": "environment_sensor_i2c", "from": "Crazyflie deck I2C", "to": "BME688",
                 "net_mapping_verified": False},
                {"name": "deck_identification", "from": "Crazyflie 1-Wire deck discovery", "to": "DS28E05",
                 "net_mapping_verified": False},
                {"name": "flight_comms", "from": "nRF51822", "to": "STM32F405 flight controller",
                 "net_mapping_verified": False},
            ],
            "firmware_reference": baseline["firmware_url"],
            "simulator_discovery": simulation.get("official_source"),
        },
        "artifact_authority": {
            "native_schematic_validated": False,
            "firmware_build_validated": False,
            "dynamics_simulated": False,
            "manufacturing_authorized": False,
            "firmware_flash_authorized": False,
            "motors_start_authorized": False,
            "flight_authorized": False,
        },
        "verdict": "DESIGN_REVIEW_BLOCKED",
    }


def generate_package(
    design: Mapping[str, Any],
    scenario: Mapping[str, Any],
    output: Path,
) -> dict[str, Any]:
    report = assess_microdrone(design, guidance_scenario=scenario)
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Refuse overwrite of an existing microdrone assessment")
    output.mkdir(parents=True, exist_ok=True)
    architecture = report["reviewable_architecture"]
    evidence_gate = {
        "schema_version": "hardware_splicer.microdrone_evidence_gate.v1",
        "source_design_sha256": report["source_design_sha256"],
        "source_guidance_sha256": report["source_guidance_sha256"],
        "preliminary_checks_pass": report["preliminary_checks_pass"],
        "blockers": report["blockers"],
        "artifact_authority": report["artifact_authority"],
    }
    files = {
        "DESIGN_INPUT.json": _source_bytes(design),
        "GUIDANCE_REFERENCE.json": _source_bytes(scenario),
        "MICRODRONE_ASSESSMENT.json": _source_bytes(report),
        "ARCHITECTURE_CONTRACT.json": _source_bytes(architecture),
        "PHYSICAL_EVIDENCE_GATE.json": _source_bytes(evidence_gate),
    }
    for name, blob in files.items():
        (output / name).write_bytes(blob)
    receipt = {
        "schema_version": "hardware_splicer.microdrone_package_receipt.v1",
        "source_design_sha256": report["source_design_sha256"],
        "files": {
            name: {"sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
            for name, blob in sorted(files.items())
        },
        "all_physical_actions_authorized": False,
    }
    (output / "PACKAGE_RECEIPT.json").write_bytes(_source_bytes(receipt))
    return receipt
