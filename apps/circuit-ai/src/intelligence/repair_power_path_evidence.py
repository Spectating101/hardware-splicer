"""Source-provenanced, typed evidence state for a laptop's DC-input repair.

This is a STATE TRACKER, not a root-cause classifier and not a bench procedure.
It consumes explicit observations supplied by a technician, distinguishes
a PSU setpoint from a measured rail, and carries evidence into a diagnostic
state and negative evidence against stale guesses. It cannot authorize repair.

The original unstructured RepairEncyclopedia remains the fallback for cases
without recognized typed evidence. No natural-language outcome heuristics here.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Dict, List, Sequence

# Only specifically recognizable observations can change the state.
OBSERVATIONS = {
    "adapter_led_trips_when_connected",
    "rail_collapses_under_load_reported",
    "board_short_persists_with_jack_removed",
    "sense_resistor_heat_is_false_localization",
    "mlcc_removal_cleared_board_short",
    "main_input_rail_recovered",
    "no_boot_after_input_recovered",
    "rtc_disconnected_changes_startup",
    "source_claims_component_replacement",
    "source_claims_repeated_power_cycles",
}
MEASUREMENTS = {
    "adapter_output_unloaded": "V",
    "bench_supply_setpoint_not_board_voltage": "V",
    "input_fault_current_reported": "A",
    "localization_current_reported": "A",
    "board_input_rail": "V",
    "board_idle_current": "mA",
    "power_button_logic": "V",
}
SOURCE_ROLES = {"external_technician", "owner_report", "operator_unverified"}
PROVENANCE = {"third_party_source_report", "user_supplied_unverified"}
HIGH_ENERGY_INTERVENTIONS = {"current_injection", "powered_rtc_connection", "flammable_solvent_heating", "component_rework"}

STATE = {
    "insufficient_structured_evidence": {
        "fault_id": None,
        "name": "No discriminating structured evidence",
        "next": ["Obtain the device identity and externally recorded, condition-labeled observations before choosing a component."],
    },
    "input_loading_suspected": {
        "fault_id": "laptop_main_input_loading_or_protection_trip_unverified",
        "name": "Adapter protection trip: input load, cable, or main-rail short differential",
        "next": [
            "Record charger identity and compare known-compatible externally verified adapter behavior.",
            "Qualified service must distinguish external adapter protection from board-side loading without assuming an internal failed part.",
        ],
    },
    "board_input_short_reported": {
        "fault_id": "laptop_downstream_main_input_short_reported",
        "name": "Source-reported board-side DC input short, component not yet isolated",
        "next": [
            "Record the exact board revision, jack and board isolation boundaries and unpowered resistance observations.",
            "Require qualified instrument and circuit documentation to identify the affected rail and safe test constraints.",
        ],
    },
    "component_short_localized_reported": {
        "fault_id": "laptop_input_mlcc_short_isolation_reported",
        "name": "Source-reported MLCC isolation on main DC input; part equivalence unverified",
        "next": [
            "Document exact board position and manufacturer schematic for the isolated component.",
            "Do not buy or install a donor MLCC without capacitance, dielectric, rated voltage, footprint and derating evidence.",
        ],
    },
    "second_boot_fault_after_rail_recovery": {
        "fault_id": "laptop_secondary_startup_fault_after_main_rail_restoration",
        "name": "Recovered DC input followed by a separate EC/RTC/boot-sequencing fault",
        "next": [
            "Record which supply rails and power-button signals are present while startup remains absent.",
            "Collect manufacturer-approved, de-energized diagnostics of EC reset, RTC and BIOS startup state.",
        ],
    },
    "rtc_dependent_boot_state_reported": {
        "fault_id": "laptop_rtc_dependent_startup_state_unverified",
        "name": "Source-reported RTC-dependent startup behavior; root mechanism unverified",
        "next": [
            "Record BIOS/RTC cell condition and model-revision servicing requirements while all power is isolated.",
            "Verify restart, RTC time retention, battery charging, thermals and peripherals before a return-to-service claim.",
        ],
    },
}


def normalize_events(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate typed, source-attributed observations. Reject fake verified evidence."""
    if isinstance(events, (str, bytes)) or not isinstance(events, (tuple, list)):
        raise ValueError("evidence_events must be a list of explicit typed source events")
    normalized: List[Dict[str, Any]] = []
    ids = set()
    last_stage = -1
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each evidence event must be a dict")
        event_id = str(event.get("event_id") or "")
        kind = str(event.get("event_type") or "")
        signal = str(event.get("signal") or "")
        actor = str(event.get("actor") or "")
        provenance = str(event.get("provenance") or "")
        stage = str(event.get("stage_id") or "")
        if not event_id or event_id in ids:
            raise ValueError("missing or duplicated source event ID")
        if kind not in {"measurement", "observation", "intervention"}:
            raise ValueError("unsupported evidence event kind")
        if actor not in SOURCE_ROLES or provenance not in PROVENANCE:
            raise ValueError("unsupported or falsely independently-verified evidence provenance")
        if not stage.startswith("T") or not stage[1:].isdigit():
            raise ValueError("stage ID must be T plus a nonnegative integer")
        stage_index = int(stage[1:])
        if stage_index < last_stage:
            raise ValueError("events must be supplied in chronology order")
        last_stage = stage_index
        if kind == "measurement":
            if signal not in MEASUREMENTS:
                raise ValueError("unrecognized measured electrical quantity")
            expected_unit = MEASUREMENTS[signal]
            if event.get("unit") != expected_unit:
                raise ValueError("wrong measurement unit: expected " + expected_unit)
            value = event.get("value")
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
                raise ValueError("a recorded measurement must be a finite numeric value")
            if not event.get("condition"):
                raise ValueError("measurement missing state/condition")
        elif kind == "observation":
            if signal not in OBSERVATIONS:
                raise ValueError("unrecognized diagnostic observation")
        elif kind == "intervention":
            if signal not in HIGH_ENERGY_INTERVENTIONS:
                raise ValueError("unrecognized historical intervention")
        if event.get("HS_instrument_verified") is True or event.get("repair_authorized") is True:
            raise ValueError("source statement cannot assert HS measurement or authorize repair")
        ids.add(event_id)
        normalized.append(dict(event))
    return normalized


def analyze_laptop_power_evidence(events: Sequence[Dict[str, Any]], *, device_hint: str) -> Dict[str, Any]:
    """Evidence-ranked *states* with reported source provenance, never probabilities."""
    if not any(token in str(device_hint).lower() for token in
               ("laptop", "notebook", "macbook", "thinkpad", "latitude", "zephyrus")):
        return {"applicable": False, "state": "out_of_scope_laptop_power_path",
                "reason": "power-rail model only applies to explicit laptop identity"}

    items = normalize_events(events)
    observed: Dict[str, List[str]] = {}
    measured: Dict[str, List[str]] = {}
    chronology: List[Dict[str, Any]] = []
    unsafe_history: List[str] = []
    previous_state = "insufficient_structured_evidence"
    latest_input_v = None
    for item in items:
        signal, eid, kind = item["signal"], item["event_id"], item["event_type"]
        if kind == "observation":
            observed.setdefault(signal, []).append(eid)
        elif kind == "measurement":
            measured.setdefault(signal, []).append(eid)
            if signal == "board_input_rail":
                latest_input_v = float(item["value"])
        else:
            unsafe_history.append(eid)
        # Negative evidence is explicit. Do not infer observed voltage from a
        # nominal PSU setpoint or mean that heat in a sense resistor proves defect.
        has = lambda sig: sig in observed
        state = "insufficient_structured_evidence"
        if has("adapter_led_trips_when_connected"):
            state = "input_loading_suspected"
        if has("board_short_persists_with_jack_removed") and has("rail_collapses_under_load_reported"):
            state = "board_input_short_reported"
        if state in ("board_input_short_reported", "input_loading_suspected") and has("mlcc_removal_cleared_board_short"):
            state = "component_short_localized_reported"
        if (has("mlcc_removal_cleared_board_short") and has("main_input_rail_recovered")
            and has("no_boot_after_input_recovered") and latest_input_v is not None
            and latest_input_v >= 10.0):
            state = "second_boot_fault_after_rail_recovery"
        if state == "second_boot_fault_after_rail_recovery" and has("rtc_disconnected_changes_startup"):
            state = "rtc_dependent_boot_state_reported"
        if state != previous_state:
            chronology.append({"event_id": eid, "stage_id": item["stage_id"],
                               "from": previous_state, "to": state})
            previous_state = state

    supporting = []
    rebuttals = []
    state = previous_state
    if state == "input_loading_suspected":
        supporting = observed.get("adapter_led_trips_when_connected", [])
        rebuttals = [{"hypothesis": "battery_replacement_is_sufficient",
                      "reason": "adapter output trip is not explained by a diagnosed battery defect"}]
    if state in ("board_input_short_reported", "component_short_localized_reported",
                 "second_boot_fault_after_rail_recovery", "rtc_dependent_boot_state_reported"):
        supporting = observed.get("board_short_persists_with_jack_removed", []) + observed.get("rail_collapses_under_load_reported", [])
        rebuttals = [{"hypothesis": "dc_jack_only_fault",
                      "reason": "source reports short persists after disconnecting jack"},
                     {"hypothesis": "battery_charge_path_is_proven",
                      "reason": "neither a failed battery nor its charging controller was independently isolated"}]
    if state in ("component_short_localized_reported", "second_boot_fault_after_rail_recovery",
                 "rtc_dependent_boot_state_reported"):
        supporting += observed.get("mlcc_removal_cleared_board_short", [])
        rebuttals.append({"hypothesis": "sense_resistor_is_failed",
                          "reason": "reported first heat location was current transit, not failed element"})
    if state in ("second_boot_fault_after_rail_recovery", "rtc_dependent_boot_state_reported"):
        supporting += observed.get("main_input_rail_recovered", []) + observed.get("no_boot_after_input_recovered", []) + measured.get("board_input_rail", [])
        rebuttals.append({"hypothesis": "input_short_remains_active_fault",
                          "reason": "source reports restored main input rail while startup still failed"})
        rebuttals.append({"hypothesis": "usb_c_port_must_be_replaced",
                          "reason": "no observed USB-C port failure; documented board input restored"})
    if state == "rtc_dependent_boot_state_reported":
        supporting += observed.get("rtc_disconnected_changes_startup", [])
        rebuttals.append({"hypothesis": "rtc_cell_itself_confirmed_failed",
                          "reason": "startup dependence alone does not isolate cell, connector, EC state or firmware"})

    definition = STATE[state]
    return {
        "schema_version": "hs.laptop_power_evidence_state.v1",
        "applicable": True,
        "state": state,
        "fault_id": definition["fault_id"],
        "fault_name": definition["name"],
        "state_transitions": chronology,
        "source_evidence_ids_supporting": list(dict.fromkeys(supporting)),
        "hypotheses_contradicted_by_record": rebuttals,
        "source_reported_numeric_measurement_count": sum(item["event_type"]=="measurement" for item in items),
        "independently_verified_HS_measurement_count": 0,
        "unverified_hazardous_interventions": unsafe_history,
        "next_required_evidence": definition["next"],
        "confidence_type": "qualitative_state_support_only_no_probability",
        "source_is_ground_truth": False,
        "component_failure_independently_verified": False,
        "physical_repair_ready": False,
        "parts_purchase_authorized": False,
        "power_or_rework_authorized": False,
    }


def apply_laptop_evidence_to_guide(guide: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Drive the existing guide from typed evidence, never a generic repair score."""
    if not state.get("applicable") or not state.get("fault_id"):
        return guide
    definition = STATE[state["state"]]
    old_faults = [x.get("fault_id") for x in guide.get("fault_candidates") or []]
    steps = list(definition["next"])
    candidate = {
        "fault_id": definition["fault_id"],
        "name": definition["name"],
        "category": "reported_evidence_supported_differential",
        "severity": "unverified_requires_qualified_test",
        "likelihood": 0.0,
        "ranking_method": "explicit_state_and_evidence_not_numeric_probability",
        "evidence": state["source_evidence_ids_supporting"],
        "likely_causes": [definition["name"]],
        "diagnostic_tests": [{
            "name": "Model-specific documented evidence review",
            "equipment_needed": ["model-specific schematic", "qualified technician", "external source measurements"],
            "steps": steps,
            "expected_result": "An independently verified discriminating observation.",
            "fault_indicated_if": "Actual qualified data eliminates competing hypotheses.",
        }],
        "repair_steps": ["No actual physical repair, current injection, donor part installation or powered RTC work authorized."],
        "repair_difficulty": "unknown_until_evidence_and_board_revision",
        "estimated_time_minutes": None,
    }
    guide["superseded_generic_fault_ids"] = old_faults
    guide["fault_candidates"] = [candidate]
    guide["evidence_state"] = state
    guide["triage_state"] = {
        "mode": "typed_laptop_power_evidence_state",
        "state": state["state"],
        "requires_measurement": True,
        "hypothesis_verified": False,
        "repair_ready": False,
        "physical_authority": False,
        "why": "Typed, source-attributed findings outrank an unstructured battery/USB template.",
    }
    guide["repair_playbooks"] = [{
        "fault_id": candidate["fault_id"],
        "title": "Source evidence review only; no physical repair approved",
        "repair_steps": steps,
        "confirmation_after_repair": ["Full independent laptop function acceptance is still required."],
    }]
    guide["parts_and_tools"] = {
        "tools": ["model-specific service manual", "board revision record", "qualified metrology"],
        "likely_parts": [], "consumables": [],
    }
    guide["diagnostic_flow"] = [{
        "order": 1,
        "title": "Provenance and contradiction review (unpowered only)",
        "purpose": "Do not substitute inferred device damage for qualified measurements.",
        "actions": steps,
        "pass_condition": "Sources, board revision and independent discriminating evidence recorded.",
        "fail_branch": "BLOCK physical rework, replacement-part purchase and customer release.",
    }]
    guide["evidence_to_collect_next"] = list(dict.fromkeys(
        steps + list(guide.get("evidence_to_collect_next") or [])))[:12]
    guide["confidence"] = min(float(guide.get("confidence", 0) or 0), 0.40)
    safety = guide.setdefault("safety_profile", {})
    safety["risk_level"] = "high"
    safety["rules"] = [
        "No energized board injection, flammable heat diagnostic, live RTC connection, solder rework or replacement is approved.",
        "Follow manufacturer-approved power isolation, trained technician procedures, and independent instrumentation.",
    ] + list(safety.get("rules") or [])
    guide.setdefault("limitations", []).append(
        "All supplied evidence is unverified external reports; an evidence-state label is NOT a verified component diagnosis.")
    return guide
