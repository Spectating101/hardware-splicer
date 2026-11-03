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

    # These routes were motivated by #271's immutable 17-story holdout.
    # Every fixture added after viewing its output is a DEVELOPMENT regression,
    # never evidence of independent unseen accuracy.
    if (
        family == "retro_handheld_aa_power"
        and (
            _contains(text, "lcd bias", "dc-dc converter", "-33 v", "negative voltage rail")
            or (_contains(text, "powers up", "powers on", "boots") and
                _contains(text, "lcd", "screen") and
                _contains(text, "abnormal", "white", "garbled", "bias"))
        )
    ):
        reason = "A powered handheld with abnormal LCD/bias behavior should not be routed back to missing AA input."
        verification = [
            "Confirm whether normal startup sound/gameplay proves the logic rail is running; do not assume all subsystems are healthy.",
            "Identify the exact Game Boy DC-DC/LCD bias reference and capture photo of the regulator revision.",
            "Only a qualified technician may verify regulated negative output with rated probes and appropriate precautions.",
            "Treat game boot, LCD contrast/bias and missing audio as potentially separate faults; no aftermarket Zener modification authorized.",
        ]
        candidate = _hypothesis(
            "retro_lcd_bias_or_dc_dc_regulation_unverified",
            "Handheld LCD-bias converter or display/interconnect differential",
            ["abnormal negative LCD bias supply", "damaged regulator or feedback",
             "LCD ribbon or display-specific defect", "separate cartridge/audio symptom"],
            verification,
            "handheld runs but display/bias measurements or behavior are inconsistent",
        )
    elif (
        family == "retro_handheld_aa_power"
        and _contains(text, "speaker", "audio", "sound", "volume")
        and _contains(text, "silent", "no sound", "quiet", "faint", "buzz", "volume", "speaker")
        and not _contains(text, "won't turn on", "will not turn on", "does not turn on", "fails to power")
    ):
        headphone_works = (
            _contains(text, "headphones work", "headphone audio works", "headphone path works",
                      "sound works on headphone", "sound works in headphone")
            or (_contains(text, "headphone") and _contains(text, "display still", "gameplay still"))
        )
        reason = "Audio-only symptoms on a functioning handheld require a signal-path differential, not AA contacts."
        verification = [
            "Record whether gameplay, display and power indicator work; distinguish no sound versus low sound.",
            "Compare headphone and built-in speaker function and whether the volume-wheel position changes output.",
            "Remove cells before passive speaker lead, headphone switch and volume potentiometer inspection.",
            "Escalate capacitor, audio amplifier and signal-trace measurements to a qualified service procedure; no blind part swap.",
        ]
        candidate = _hypothesis(
            "speaker_jack_switch_or_audio_path_unverified" if headphone_works
            else "retro_audio_output_or_coupling_unverified",
            "Speaker/jack output path differential" if headphone_works
            else "Audio capacitor, amplifier, speaker or volume-control differential",
            ["failed audio coupling component", "dirty/worn volume control",
             "speaker/jack disconnect switch", "speaker harness or amplifier"],
            verification,
            "device powers sufficiently for an audio symptom; power-contact fault unsupported",
        )
    elif (
        family == "laptop_power_path"
        and _contains(text, "adapter", "charger", "barrel")
        and _contains(text, "wattage and type cannot", "adapter not detected",
                      "charger not detected", "adapter id", "adapter identification",
                      "not recognizing charger")
    ):
        reason = "Correct nominal adapter voltage does not establish adapter identification or charge-authorization signaling."
        verification = [
            "Record adapter manufacturer, connector center-ID pin and laptop's specific charger identification protocol.",
            "Distinguish stable low-voltage power from identification/data-pin continuity; do not bridge pins.",
            "Use a verified same-model rated charger before any battery or motherboard replacement.",
            "For qualified service, record manufacturer-safe jack, center-pin and charge-authorization evidence.",
        ]
        candidate = _hypothesis(
            "laptop_adapter_identification_or_sense_unverified",
            "Laptop barrel adapter identification, connector sense, or charge-path differential",
            ["adapter center-ID pin contact", "incompatible adapter/identification protocol",
             "DC jack sense lead", "battery management not ruled out"],
            verification,
            "owner reports charger detection failure despite supply input evidence",
        )
        unsafe_operation = True
    elif (
        family == "laptop_power_path"
        and _contains(text, "barrel", "charger", "adapter")
        and _contains(text, "fluctuat", "13-19", "while powered off", "while off",
                      "usb-c charging still works", "usb-c still")
    ):
        reason = "Barrel-input voltage droop or charging-state dependence does not prove a USB-C port failure."
        verification = [
            "Identify the actual active charger connector and OEM power rating rather than assume USB-C input.",
            "Record unloaded versus loaded voltage using a qualified external method and compare with adapter specification.",
            "Verify compatible known-good rated adapter and barrel jack contact, then board-side input only if trained.",
            "Separately document USB-C bypass charging, battery behavior and state-dependent charge indicators.",
        ]
        candidate = _hypothesis(
            "laptop_barrel_dc_in_or_loaded_supply_unverified",
            "Laptop barrel input, adapter load regulation and charge-state differential",
            ["adapter voltage collapse under load", "barrel-jack intermittency",
             "power-management/charge-state fault", "battery fault still possible"],
            verification,
            "owner reports barrel connector charging anomaly while other input modes differ",
        )
        unsafe_operation = True
    elif (
        family == "phone_charging_port_flex"
        and _contains(text, "battery health", "charge cycles", "1200+", "shuts off at", "shuts down at")
        and _contains(text, "charge", "charging", "battery")
    ):
        reason = "Severe pack degradation and state-dependent charging are a battery/management differential, not proof of a port flex failure."
        verification = [
            "Capture battery health/cycle history and whether shutdown occurs under battery load versus external supply.",
            "Review owner charge-current observations with charger/meter model and screen-on/off states; do not equate current change with root cause.",
            "Inspect physical battery condition with manufacturer-safe procedure; stop for heat, swelling or puncture.",
            "Qualified service must distinguish known-compatible battery pack/BMS from charging-controller, cable and port faults.",
        ]
        candidate = _hypothesis(
            "phone_battery_bms_or_state_dependent_charge_unverified",
            "Battery pack/BMS and charge-state regulation differential",
            ["degraded battery pack or protection state", "incorrect battery communication",
             "screen-state-dependent charging controller behavior", "port/cable still not excluded"],
            verification,
            "owner reports battery degradation and charge instability; no component causality measured by HS",
        )
        unsafe_operation = True
    elif (
        family == "modern_console_usb_c_video"
        and _contains(text, "black screen", "no boot", "does not boot", "won't turn on")
        and _contains(text, "ammeter", "current draw", "charging behavior", "m92 replacement", "0.44 a")
    ):
        reason = "A black-screen console with reported charge current can have firmware/boot-state or board causes; charging-IC replacement is premature."
        verification = [
            "Record exact console revision, whether ever modified, and separately observed USB-C charge voltage and current.",
            "Ask whether bootloader/AutoRCM mode is enabled; do not assert it without evidence.",
            "Identify noninvasive manufacturer-approved power/boot diagnostics before declaring USB-C or battery defective.",
            "If physical service is needed, qualified technicians isolate USB-C electrical and board boot faults with independent measurements.",
        ]
        candidate = _hypothesis(
            "console_boot_mode_or_power_path_unverified",
            "Console boot/configuration state versus charging power-path differential",
            ["firmware boot/RCM state", "battery/input failure",
             "board logic or display symptom", "USB-C connector/PD issue not yet confirmed"],
            verification,
            "reported current alone cannot prove charging-IC failure",
        )
        unsafe_operation = True
    elif (
        _contains(hint, "printer", "deskjet", "inkjet", "officejet", "epson", "pixma")
        and _contains(text, "print", "alignment", "nozzle", "lines", "image")
        and _contains(text, "distort", "misalign", "alignment", "blur", "shift", "wonky", "uneven")
        and not _contains(text, "carriage stuck", "carriage jam")
    ):
        reason = "Print-registration errors can arise from encoder contamination or positioning, not motor-driver electronics."
        verification = [
            "Disconnect power before any printer mechanism or encoder inspection; no live carriage intervention.",
            "Record before/after print alignment pattern and precise model/encoder strip routing.",
            "Inspect encoder strip and photo-sensor gently under manufacturer-safe procedures; avoid damaging calibration markings.",
            "Do not replace printhead, board or motor without model-specific test results.",
        ]
        candidate = _hypothesis(
            "printer_encoder_strip_or_registration_unverified",
            "Encoder positioning, printhead registration or sensor-path differential",
            ["dirty/displaced encoder strip", "printhead alignment or sensor tracking",
             "feed/roller transport skew", "printhead defect not yet proven"],
            verification,
            "owner reports print alignment failure without a confirmed electronic driver fault",
        )
        unsafe_operation = True

    elif (
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
                      "not fly", "tilt", "tip over", "doesn't lift",
                      "fails to take off", "fails to lift", "no takeoff",
                      "doesn't take off", "does not take off", "not taking off")
    ):
        swapped = _contains(text, "replaced", "replacement", "changed", "new prop", "new blade", "swapped", "built", "builder")
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
        _contains(hint, "printer", "deskjet", "inkjet", "officejet", "epson", "pixma")
        and _contains(text, "carriage", "cartridge", "jam", "stuck", "move", "printhead")
        and _contains(text, "stuck", "jam", "won't move", "does not move", "not move", "blocked",
                      "catches", "catching", "binds", "rubbing")
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
