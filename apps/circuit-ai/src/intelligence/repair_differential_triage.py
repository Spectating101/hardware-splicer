"""Evidence-first differential repair triage, independent of product value scoring.

Heuristic hypotheses are NOT calibrated probabilities, source ground truth, part
replacement approvals, or permission to power/operate a device. This module
takes only the observations available at intake and adds model-specific checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _hypothesis(
    fault_id: str, label: str, causes: List[str], checks: List[str], evidence: str
) -> Dict[str, Any]:
    # Likelihood is an internal ranking heuristic, not an estimated posterior.
    return {
        "fault_id": fault_id,
        "name": label,
        "category": "unverified_differential",
        "severity": "unknown_pending_measurement",
        "likelihood": 0.88,
        "evidence": [evidence, "hypothesis only; no measured root cause supplied"],
        "likely_causes": causes,
        "diagnostic_tests": [{
            "name": "Power-isolated differential verification",
            "equipment_needed": ["model-specific service documentation", "photographs", "multimeter where appropriate"],
            "steps": checks,
            "expected_result": "The suspected fault and alternatives are discriminated with recorded observations.",
            "fault_indicated_if": "Reproducible model-correct measurements distinguish the candidate from alternatives.",
        }],
        "repair_steps": [
            "No component substitution or physical operation is approved by this heuristic.",
            "Confirm the isolated fault and document a qualified model-specific repair plan first.",
        ],
        "repair_difficulty": "unknown_until_verified",
        "estimated_time_minutes": None,
    }


def apply_evidence_first_triage(
    guide: Dict[str, Any], *, symptoms: Sequence[str], device_hint: str
) -> Dict[str, Any]:
    """Refine a guide when failure observations contradict a default top fault.

    Explicit device identity is taken from device_hint, not loose words in a
    repair-story title or a commercially-weighted market classifier.
    """
    hint = str(device_hint or "").lower()
    text = " ".join(str(x) for x in symptoms).lower()
    family = (guide.get("device_family") or {}).get("id")
    candidate = None
    verification: List[str] = []
    unsafe_operation = False
    reason = ""

    if (
        family == "retro_handheld_aa_power"
        and _contains(text, "speaker", "sound", "audio")
        and _contains(text, "headphone", "earphone")
        and _contains(text, "no sound", "silent", "not working", "doesn't work", "does not work")
    ):
        reason = "Speaker-only symptom with a functioning headphone path does not imply lost battery input."
        verification = [
            "Record that display, gameplay, and headphone audio still operate; do not re-diagnose AA power.",
            "With batteries removed, inspect the speaker leads and connector for opens or damage.",
            "Identify the headphone-jack speaker-disconnect switch and verify its isolated continuity.",
            "Only with appropriate service documentation distinguish audio amplifier, coupling capacitor, and PCB trace faults.",
        ]
        candidate = _hypothesis(
            "speaker_jack_switch_or_audio_path_unverified",
            "Speaker-jack switch, lead, or audio output-path fault",
            ["headphone-jack switch held open", "speaker harness or trace open",
             "audio coupling component or amplifier path fault"],
            verification,
            "reported speaker failure while headphone path is available",
        )
    elif (
        family == "laptop_power_path"
        and _contains(text, "charger", "adapter", "charging", "power lead", "power cable")
        and _contains(text, "no voltage", "zero voltage", "no output", "no power at", "measured no power")
    ):
        reason = "Reported missing external adapter output must be resolved before any motherboard hypothesis."
        verification = [
            "Record the adapter label, rated output, connector type and compatible laptop model.",
            "A qualified person verifies the adapter output at its accessible low-voltage plug using correct meter settings.",
            "Separate detachable AC cord, adapter brick and low-voltage output lead faults without opening mains equipment.",
            "Use a verified compatible replacement supply only after cable and adapter isolation; then reassess laptop boot and secondary symptoms.",
        ]
        candidate = _hypothesis(
            "external_adapter_or_lead_output_unverified",
            "External charger or output-lead fault (measurement unverified)",
            ["failed adapter brick", "open or damaged DC output lead",
             "faulty detachable AC input cord", "misreported meter measurement"],
            verification,
            "reported no charger-lead output; no independent instrument record",
        )
        unsafe_operation = True
    elif (
        _contains(hint, "drone", "quadcopter", "syma x5")
        and _contains(text, "spin", "rotat", "propeller", "prop", "lift", "tilt", "fly")
        and _contains(text, "no lift", "won't lift", "cannot lift", "won't fly",
                      "not fly", "tilt", "tip over", "doesn't lift")
    ):
        swapped = _contains(text, "replaced", "replacement", "changed", "new prop", "new blade", "swapped")
        reason = "Spinning rotors do not establish thrust; orientation/geometry and drive train precede driver replacement."
        verification = [
            "Remove battery and propellers before physical inspection; no spin, bench thrust, or flight test is authorized.",
            "Compare clockwise and counterclockwise propeller markings and rotor locations against exact manufacturer diagram.",
            "Check propeller damage, gear mesh, shaft coupling, motor mount and frame symmetry after impact.",
            "If geometry is verified, refer any controlled thrust/current test to a qualified guarded-flight test procedure.",
        ]
        candidate = _hypothesis(
            "propeller_orientation_or_thrust_path_unverified" if swapped else "postimpact_propulsion_path_unverified",
            "Propeller orientation and mechanical thrust differential" if swapped else "Post-impact thrust/propulsion differential",
            ["incorrect CW/CCW propeller layout", "slipped or damaged gear/shaft",
             "misaligned frame or motor", "electronic drive asymmetry not excluded"],
            verification,
            "rotors reportedly spin but craft has inadequate lift",
        )
        unsafe_operation = True
    elif (
        _contains(hint, "printer", "deskjet", "inkjet")
        and _contains(text, "carriage", "cartridge", "jam", "stuck", "move")
        and _contains(text, "stuck", "jam", "won't move", "does not move", "not move", "blocked")
    ):
        reason = "Carriage jam is a mechanical path fault until evidence implicates board-level drivers."
        verification = [
            "Disconnect printer from mains and wait for moving parts to stop; never pull power during a moving-carriage cycle.",
            "Inspect parked carriage, service station, guide rail, paper path and foreign objects without forcing mechanisms.",
            "Photograph obstruction or damaged drive belt/gears and consult the exact model's disassembly procedure.",
            "Escalate any powered motion diagnostics to a trained, guarded manufacturer-approved procedure.",
        ]
        candidate = _hypothesis(
            "printer_carriage_or_service_station_mechanical_unverified",
            "Mechanical carriage, service-station, or belt-path obstruction",
            ["carriage parking latch or service station obstruction",
             "paper or foreign object jam", "drive belt/rail fault", "motor driver still unproven"],
            verification,
            "reported mechanical carriage stuck/jam",
        )
        unsafe_operation = True
    elif (
        family == "phone_charging_port_flex"
        and _contains(text, "reassembl", "assembled", "installation", "installed")
        and _contains(text, "flex", "charging port", "charge port", "lightning")
        and _contains(text, "disconnect", "connected", "boot", "shutdown", "short")
    ):
        reason = "Failure depends on assembly state; fit, pressure, cable routing and short must be differentiated."
        verification = [
            "Identify exact phone model and replacement part revision; preserve observed pre-assembly comparison.",
            "Stop and follow documented battery isolation before any disassembly; do not reconnect a suspected short while powered.",
            "Inspect bracket placement, cable routing, trapped flex, connector seating and insulation without assuming any part is defective.",
            "Only after qualified isolation distinguish original/replacement flex, chassis pressure and charging-controller faults.",
        ]
        candidate = _hypothesis(
            "assembly_interference_or_charge_flex_short_unverified",
            "Reassembly-dependent flex or mechanical interference",
            ["trapped flex or bracket pressure", "part mismatch or poor connector seating",
             "flex or port short", "board charge path not yet excluded"],
            verification,
            "power/charge behavior changes after final assembly",
        )
        unsafe_operation = True

    if candidate is None:
        return guide

    old = guide.get("fault_candidates") or []
    guide["fault_candidates"] = [candidate] + [
        x for x in old if x.get("fault_id") != candidate["fault_id"]
    ][:5]
    guide["triage_state"] = {
        "mode": "symptom_contradiction_differential",
        "requires_measurement": True,
        "hypothesis_verified": False,
        "repair_ready": False,
        "why": reason,
        "operator_authority": "assistive_only_no_power_or_repair_authorization",
    }
    guide["evidence_to_collect_next"] = list(dict.fromkeys(
        verification + list(guide.get("evidence_to_collect_next") or [])
    ))[:10]
    steps = list(guide.get("diagnostic_flow") or [])
    # The generic low-voltage flow contains a powered current-limit test.
    # It is not a safe default for a jammed mains printer or an aircraft.
    if unsafe_operation:
        for step in steps:
            if step.get("title") == "Power path check":
                step["title"] = "Unpowered intake only"
                step["actions"] = [
                    "disconnect all sources and secure moving mechanisms",
                    "inspect and document the fault under model-specific service guidance",
                    "do not energize the device or infer the failed electrical component",
                ]
                step["pass_condition"] = "power isolated and physical hazards controlled"
                step["fail_branch"] = "STOP pending qualified safe diagnostic procedure"
    steps.append({
        "order": len(steps) + 1,
        "title": "Contradiction-aware differential before any replacement",
        "purpose": reason,
        "actions": verification,
        "pass_condition": "model-specific physical evidence recorded and fault alternatives excluded",
        "fail_branch": "ABSTAIN from component replacement or repair-ready claim",
    })
    guide["diagnostic_flow"] = steps
    # Remove precomputed generic rework/playbooks: they no longer correspond
    # to the evidence-first top fault and may imply powered tests/part swaps.
    guide["repair_playbooks"] = [{
        "fault_id": candidate["fault_id"],
        "title": "Diagnostic evidence collection only; no repair approved",
        "difficulty": "unknown_until_verified",
        "estimated_time_minutes": None,
        "repair_steps": verification,
        "confirmation_after_repair": [
            "No repair completion can be claimed until new independent measurements and full-product tests exist."
        ],
    }]
    guide["parts_and_tools"] = {
        "tools": ["model-specific service manual", "photographs", "multimeter only when safe and qualified"],
        "likely_parts": [],
        "consumables": [],
    }
    guide["confidence"] = min(float(guide.get("confidence", 0) or 0), 0.64)
    guide.setdefault("limitations", []).append(
        "Diagnostic ranking is an uncalibrated hypothesis, not measured fault probability or a successful physical repair."
    )
    if unsafe_operation:
        safety = guide.setdefault("safety_profile", {})
        safety["risk_level"] = "high"
        safety.setdefault("rules", []).insert(
            0, "No energized mechanical movement, flying rotor, live mains, battery reconnection or board rework authorized."
        )
    return guide
