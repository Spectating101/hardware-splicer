"""Repair encyclopedia generation for small electronic machines and gadgets."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Sequence

from src.intelligence.common_fault_database import CommonFault, common_fault_database


class RepairEncyclopedia:
    """Generate symptom and scan-aware repair guides from Circuit-AI evidence."""

    FAMILY_CATALOG: Dict[str, Dict[str, Any]] = {
        "small_dc_motor_gadget": {
            "label": "Small DC motor / actuator gadget",
            "examples": ["desk fan", "toy car", "pump", "robot module", "motorized tool attachment"],
            "subsystems": [
                "power input and protection",
                "voltage regulation",
                "controller or PWM logic",
                "driver stage",
                "motor/load wiring",
                "user switch or connector harness",
            ],
            "symptoms": {"motor", "spin", "fan", "pump", "buzz", "stall", "weak", "vibrate", "actuator"},
            "capabilities": {"actuator_driver", "motor_or_servo"},
        },
        "usb_powered_controller": {
            "label": "USB-powered controller module",
            "examples": ["development board", "USB adapter", "controller dongle", "programmable gadget"],
            "subsystems": [
                "USB connector",
                "USB-serial bridge",
                "3.3V/5V regulator",
                "microcontroller",
                "boot/reset circuit",
                "I/O headers",
            ],
            "symptoms": {"usb", "computer", "serial", "upload", "program", "recognized", "bootloader"},
            "capabilities": {"usb_serial", "controller", "wireless"},
        },
        "relay_power_box": {
            "label": "Low-voltage relay / switched-load controller",
            "examples": ["relay module", "smart switch module", "load controller", "solenoid driver"],
            "subsystems": [
                "low-voltage control input",
                "relay coil or MOSFET driver",
                "flyback/protection diode",
                "load terminals",
                "power isolation boundary",
            ],
            "symptoms": {"relay", "click", "switch", "load", "output", "solenoid"},
            "capabilities": {"actuator_driver", "power"},
        },
        "sensor_display_gadget": {
            "label": "Sensor/display gadget",
            "examples": ["meter", "thermostat module", "environment monitor", "panel indicator"],
            "subsystems": [
                "sensor front-end",
                "display/UI",
                "controller",
                "power regulation",
                "communication connector",
            ],
            "symptoms": {"sensor", "display", "reading", "measure", "screen", "oled", "lcd"},
            "capabilities": {"sensor_or_adc", "display_or_ui"},
        },
        "game_controller_input": {
            "label": "Game controller input assembly",
            "examples": ["Xbox controller", "DualSense", "Joy-Con", "retro gamepad"],
            "subsystems": [
                "USB or battery power",
                "main controller board",
                "analog stick potentiometers or Hall sensors",
                "button membranes and contacts",
                "ribbon/flex interconnects",
                "rumble motor/load wiring",
            ],
            "symptoms": {"controller", "stick drift", "joystick", "drift", "button", "d-pad", "trigger", "gamepad", "joy-con"},
            "capabilities": {"controller", "display_or_ui"},
        },
        "battery_charging_gadget": {
            "label": "Battery charging gadget or pack",
            "examples": ["electric toothbrush", "cordless drill battery", "portable gadget", "battery charger"],
            "subsystems": [
                "charge contacts or dock",
                "charger/power adapter",
                "battery cell or pack",
                "protection/BMS board",
                "charge controller",
                "motor or load driver",
            ],
            "symptoms": {"not charging", "won't charge", "doesn't charge", "battery", "charger", "toothbrush", "cordless", "drill", "holds charge"},
            "capabilities": {"power", "battery", "motor_or_servo"},
        },
        "mains_heater_appliance": {
            "label": "Mains heater appliance control path",
            "examples": ["coffee maker", "kettle", "espresso machine", "warming plate"],
            "subsystems": [
                "AC input and switch",
                "thermal fuse and thermostat",
                "heating element",
                "triac/relay control",
                "low-voltage control board",
                "pump or valve interlock",
            ],
            "symptoms": {"coffee", "not heating", "not hot", "heater", "heating element", "thermal fuse", "thermostat", "brew", "kettle"},
            "capabilities": {"power", "actuator_driver"},
        },
        "tv_backlight_power": {
            "label": "TV/monitor backlight or power board",
            "examples": ["LED TV", "LCD monitor", "backlight driver board"],
            "subsystems": [
                "AC input and standby supply",
                "main power rails",
                "LED backlight driver",
                "main board video/control",
                "panel/T-Con connection",
                "backlight LED strips",
            ],
            "symptoms": {"tv", "television", "monitor", "sound but no picture", "no picture", "backlight", "flashlight test", "screen dark"},
            "capabilities": {"power", "display_or_ui"},
        },
        "laptop_power_path": {
            "label": "Laptop charging and power path",
            "examples": ["Windows laptop", "MacBook", "Chromebook", "USB-C laptop"],
            "subsystems": [
                "charger and cable",
                "DC jack or USB-C port",
                "battery and pack connector",
                "charge/PD controller",
                "main rails",
                "power button and embedded controller",
            ],
            "symptoms": {"laptop", "macbook", "chromebook", "won't turn on", "will not turn on", "no power", "not charging", "usb-c", "battery"},
            "capabilities": {"power", "controller"},
        },
        "generic_electronic_module": {
            "label": "Generic low-voltage electronic module",
            "examples": ["unknown PCB", "salvaged module", "control board"],
            "subsystems": ["power input", "control IC", "connectors", "I/O stage", "passives"],
            "symptoms": set(),
            "capabilities": set(),
        },
    }

    def generate(
        self,
        analysis: Dict[str, Any] | None = None,
        symptoms: Sequence[str] | None = None,
        device_hint: str | None = None,
    ) -> Dict[str, Any]:
        """Generate a repair encyclopedia entry from optional scan and symptom evidence."""

        normalized = self._normalize_analysis(analysis or {})
        symptom_list = [str(symptom).strip() for symptom in symptoms or [] if str(symptom).strip()]
        symptom_text = " ".join(symptom_list).lower()
        hint_text = str(device_hint or "").lower()
        family_id, family_score, family_evidence = self._select_family(normalized, symptom_text, hint_text)
        family = self.FAMILY_CATALOG[family_id]
        candidates = self._fault_candidates(normalized, symptom_list, family_id)
        guide = {
            "mode": "repair_encyclopedia_entry",
            "scope": "small_low_voltage_electronic_gadgets_and_modules",
            "device_family": {
                "id": family_id,
                "label": family["label"],
                "examples": family["examples"],
                "confidence": round(family_score, 3),
                "evidence": family_evidence[:10],
            },
            "symptoms": symptom_list,
            "scan_evidence": self._scan_evidence(normalized),
            "safety_profile": self._safety_profile(symptom_text, hint_text, normalized),
            "subsystem_map": self._subsystem_map(family_id, normalized),
            "fault_candidates": candidates,
            "diagnostic_flow": self._diagnostic_flow(family_id, normalized, candidates),
            "repair_playbooks": self._repair_playbooks(candidates),
            "parts_and_tools": self._parts_and_tools(family_id, candidates),
            "when_to_stop": self._when_to_stop(symptom_text, hint_text),
            "evidence_to_collect_next": self._evidence_to_collect_next(normalized, symptom_list, family_id),
            "confidence": self._overall_confidence(normalized, family_score, candidates, symptom_list),
            "limitations": [
                "This guide is a diagnostic workflow, not proof of a fault until measurements confirm it.",
                "Do not probe mains-powered equipment live. Isolate high voltage before board-level inspection.",
                "Image-only PCB inference cannot see hidden layers, bottom-side components, or exact manufacturer revisions.",
            ],
        }
        guide["quick_summary"] = self._quick_summary(guide)
        return guide

    def _normalize_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(analysis, dict):
            return {}
        if isinstance(analysis.get("results"), dict):
            analysis = analysis["results"]
        elif analysis.get("mode") == "single_image_pipeline_analysis" and isinstance(analysis.get("results"), dict):
            analysis = analysis["results"]
        elif isinstance(analysis.get("views"), list) and analysis.get("views"):
            first = analysis["views"][0] if isinstance(analysis["views"][0], dict) else {}
            fused = analysis.get("fused_board_understanding") or first.get("board_understanding") or {}
            merged = dict(first)
            merged["board_understanding"] = fused
            analysis = merged
        return analysis

    def _select_family(self, analysis: Dict[str, Any], symptom_text: str, hint_text: str) -> tuple[str, float, List[str]]:
        board_type = str(((analysis.get("board_understanding") or {}).get("board_identity") or {}).get("primary_type") or "")
        caps = set(((analysis.get("salvage_opportunities") or {}).get("asset_summary") or {}).get("capabilities") or {})
        component_counts = (analysis.get("detection_summary") or {}).get("components_by_type") or {}
        roles = {
            "motor_or_actuator_driver": "small_dc_motor_gadget",
            "controller_or_embedded_compute": "usb_powered_controller",
            "wireless_or_communications": "usb_powered_controller",
            "display_or_user_interface": "sensor_display_gadget",
            "sensor_or_signal_conditioning": "sensor_display_gadget",
            "power_supply_or_regulator": "generic_electronic_module",
        }

        scores: Dict[str, float] = {family_id: 0.05 for family_id in self.FAMILY_CATALOG}
        evidence: Dict[str, List[str]] = {family_id: [] for family_id in self.FAMILY_CATALOG}
        if board_type in roles:
            family_id = roles[board_type]
            scores[family_id] += 0.45
            evidence[family_id].append(f"board role: {board_type}")
        if int(component_counts.get("transistor", 0) or 0) + int(component_counts.get("mosfet", 0) or 0) >= 2:
            scores["small_dc_motor_gadget"] += 0.18
            evidence["small_dc_motor_gadget"].append("multiple switching devices detected")
        if int(component_counts.get("connector", 0) or 0) >= 2:
            for family_id in ("small_dc_motor_gadget", "relay_power_box", "generic_electronic_module"):
                scores[family_id] += 0.08
                evidence[family_id].append("multiple connectors/harness points detected")

        combined_text = f"{symptom_text} {hint_text}"
        for family_id, family in self.FAMILY_CATALOG.items():
            hits = sorted(token for token in family["symptoms"] if token and token in combined_text)
            if hits:
                scores[family_id] += min(0.35, 0.1 * len(hits))
                evidence[family_id].append(f"symptom/device hint: {', '.join(hits[:5])}")
            cap_hits = sorted(set(family["capabilities"]) & caps)
            if cap_hits:
                scores[family_id] += min(0.25, 0.1 * len(cap_hits))
                evidence[family_id].append(f"capabilities: {', '.join(cap_hits[:5])}")

        phrase_routes = {
            "game_controller_input": {"stick drift", "joystick drift", "game controller", "xbox controller", "dualsense", "joy-con"},
            "battery_charging_gadget": {"not charging", "won't charge", "doesn't charge", "holds charge", "electric toothbrush", "cordless drill", "battery pack"},
            "mains_heater_appliance": {"coffee maker", "not heating", "not hot", "thermal fuse", "heating element", "warming plate"},
            "tv_backlight_power": {"sound but no picture", "no picture", "backlight", "flashlight test", "led tv", "television"},
            "laptop_power_path": {"laptop won't turn on", "laptop will not turn on", "macbook won't turn on", "usb-c laptop", "chromebook"},
        }
        for family_id, phrases in phrase_routes.items():
            hits = sorted(phrase for phrase in phrases if phrase in combined_text)
            if hits:
                scores[family_id] += min(0.45, 0.16 * len(hits))
                evidence[family_id].append(f"case phrase: {', '.join(hits[:4])}")

        best = max(scores.items(), key=lambda item: item[1])
        family_id = best[0] if best[1] > 0.08 else "generic_electronic_module"
        return family_id, min(best[1], 0.95), evidence[family_id]

    def _fault_candidates(
        self,
        analysis: Dict[str, Any],
        symptoms: List[str],
        family_id: str,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        symptom_text = " ".join(symptoms).lower()
        counts = (analysis.get("detection_summary") or {}).get("components_by_type") or {}
        board_type = str(((analysis.get("board_understanding") or {}).get("board_identity") or {}).get("primary_type") or "")
        defect = analysis.get("defect_inspection") or {}
        connector_count = int((analysis.get("machine_connection_map") or {}).get("connector_count", 0) or 0)

        for fault in common_fault_database.find_faults_by_symptoms(symptoms):
            candidates.append(self._fault_from_database(fault, symptom_text))

        if family_id == "game_controller_input" or self._has_any(symptom_text, {"stick drift", "joystick drift", "drift", "button not working", "button stuck", "trigger"}):
            likelihood = 0.64
            evidence = ["controller input family selected"]
            if self._has_any(symptom_text, {"stick drift", "joystick drift", "drift"}):
                likelihood += 0.16
                evidence.append("reported analog stick drift")
            if self._has_any(symptom_text, {"dirty", "liquid", "corrosion", "intermittent"}):
                likelihood += 0.06
                evidence.append("contamination/intermittent symptom")
            candidates.append(
                {
                    "fault_id": "analog_stick_or_button_contact_fault",
                    "name": "Analog stick, trigger, or button contact fault",
                    "category": "input",
                    "severity": "minor_to_major",
                    "likelihood": round(min(likelihood, 0.92), 3),
                    "evidence": evidence,
                    "likely_causes": [
                        "dirty or worn potentiometer track",
                        "failed analog stick module",
                        "contaminated button membrane or PCB contact",
                        "torn ribbon/flex cable",
                        "calibration drift after mechanical wear",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Input live test and visual contact inspection",
                            "equipment_needed": ["controller test software or console calibration screen", "magnification", "isopropyl alcohol"],
                            "steps": [
                                "Record stick center position and button behavior in a live input tester.",
                                "Open the controller and photograph screw, flex, and connector locations.",
                                "Inspect stick modules, button membranes, and PCB contacts for contamination or wear.",
                                "Clean contacts and membranes with electronics-safe alcohol and let them dry fully.",
                                "Retest before replacing stick modules.",
                            ],
                            "expected_result": "Stick centers repeatably and buttons toggle cleanly.",
                            "fault_indicated_if": "Axis jitters at rest, does not reach full range, or buttons fail after cleaning.",
                        }
                    ],
                    "repair_steps": [
                        "Clean stick sensor openings, button membranes, and PCB contacts with electronics-safe alcohol.",
                        "Replace worn analog stick module if drift remains after cleaning and calibration.",
                        "Inspect and reseat flex cables before reassembly.",
                        "Run platform calibration or controller test after reassembly.",
                    ],
                    "repair_difficulty": "easy_to_medium",
                    "estimated_time_minutes": 35,
                }
            )

        if family_id in {"battery_charging_gadget", "laptop_power_path"} or self._has_any(symptom_text, {"not charging", "won't charge", "doesn't charge", "holds charge", "battery dead"}):
            likelihood = 0.62
            evidence = ["charging/power storage symptom"]
            if self._has_any(symptom_text, {"toothbrush", "cordless", "drill", "battery pack"}):
                likelihood += 0.08
                evidence.append("battery-powered device hint")
            if self._has_any(symptom_text, {"hot", "swollen", "bulging"}):
                likelihood += 0.08
                evidence.append("battery safety symptom")
            candidates.append(
                {
                    "fault_id": "battery_charge_path_fault",
                    "name": "Battery, charge contact, or charge-controller fault",
                    "category": "power",
                    "severity": "major",
                    "likelihood": round(min(likelihood, 0.9), 3),
                    "evidence": evidence,
                    "likely_causes": [
                        "dirty or corroded charge contacts",
                        "failed power adapter or charging dock",
                        "aged battery cell with high internal resistance",
                        "blown fuse/thermal link or failed BMS protection board",
                        "charge-controller or USB-C/PD negotiation fault",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Charger-to-battery path check",
                            "equipment_needed": ["multimeter", "known-good charger", "current-limited supply if appropriate"],
                            "steps": [
                                "Inspect and clean charge contacts or USB/DC jack.",
                                "Verify charger output voltage with no device connected.",
                                "Measure battery pack voltage and compare with nominal rating.",
                                "Check continuity through fuse/thermal link/protection path with power disconnected.",
                                "If safe, observe charge current with the correct charger connected.",
                            ],
                            "expected_result": "Charger output is correct, battery voltage is plausible, and charge current is within expected range.",
                            "fault_indicated_if": "No charger output, open fuse/protection path, very low battery voltage, or no charge current.",
                        }
                    ],
                    "repair_steps": [
                        "Clean or repair charge contacts/jack before replacing electronics.",
                        "Replace failed adapter/dock if output is wrong.",
                        "Replace battery pack/cells only with matching chemistry, protection, and rating.",
                        "Replace fuse/BMS/charge-controller parts only after confirming the upstream charger and battery are safe.",
                    ],
                    "repair_difficulty": "medium",
                    "estimated_time_minutes": 40,
                }
            )

        if family_id == "mains_heater_appliance" or self._has_any(symptom_text, {"not heating", "not hot", "heating element", "thermal fuse", "thermostat"}):
            candidates.append(
                {
                    "fault_id": "heater_thermal_cutoff_or_control_fault",
                    "name": "Heating element, thermal fuse, thermostat, or control relay fault",
                    "category": "mains_heater",
                    "severity": "major",
                    "likelihood": 0.72,
                    "evidence": ["reported heater appliance symptom"],
                    "likely_causes": [
                        "open thermal fuse or thermostat",
                        "failed heating element",
                        "relay/triac not switching heater power",
                        "scale, water path, or interlock preventing heat cycle",
                        "damaged mains wiring or switch",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Unpowered heater path continuity check",
                            "equipment_needed": ["multimeter", "service manual when available"],
                            "steps": [
                                "Unplug the appliance and confirm capacitors are discharged.",
                                "Identify heater, thermal fuse, thermostat, and switch wiring before disconnecting anything.",
                                "Measure continuity through thermal fuse and thermostat with power disconnected.",
                                "Measure heater element resistance and compare with expected wattage.",
                                "Inspect relay/triac solder joints and burned terminals.",
                            ],
                            "expected_result": "Thermal protection has continuity and heater resistance is plausible for its wattage.",
                            "fault_indicated_if": "Open thermal fuse/thermostat, open heater, burned terminal, or relay/triac damage.",
                        }
                    ],
                    "repair_steps": [
                        "Replace thermal fuse/thermostat only with the same temperature/current rating.",
                        "Replace open heating element or burned high-current terminals.",
                        "Repair relay/triac control board only after verifying the heater and safety devices.",
                        "Perform insulation and leak checks before returning a mains appliance to use.",
                    ],
                    "repair_difficulty": "medium_to_hard",
                    "estimated_time_minutes": 60,
                }
            )

        if family_id == "tv_backlight_power" or self._has_any(symptom_text, {"sound but no picture", "no picture", "backlight", "screen dark", "flashlight test"}):
            candidates.append(
                {
                    "fault_id": "display_backlight_or_power_supply_fault",
                    "name": "Backlight LED strip, inverter/driver, or power-supply fault",
                    "category": "display_power",
                    "severity": "major",
                    "likelihood": 0.68,
                    "evidence": ["reported display/backlight symptom"],
                    "likely_causes": [
                        "failed LED backlight strip or open LED string",
                        "backlight driver shutdown",
                        "bad power-supply capacitors or standby rail",
                        "main board not enabling backlight",
                        "T-Con/panel issue if image test fails",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Backlight versus video path isolation",
                            "equipment_needed": ["flashlight", "multimeter", "LED backlight tester where safe"],
                            "steps": [
                                "Confirm audio and power LED behavior.",
                                "Use a flashlight at an angle to look for a faint image on the screen.",
                                "Inspect power board capacitors, connectors, and backlight harness with power disconnected.",
                                "Measure standby and main rails only if trained for high-voltage TV power boards.",
                                "Test LED strips with a proper LED tester after disconnecting from the driver.",
                            ],
                            "expected_result": "Faint image with no light points toward backlight path; no image points toward main/T-Con/panel path.",
                            "fault_indicated_if": "Open LED strip, missing backlight enable/driver output, or failed supply rail.",
                        }
                    ],
                    "repair_steps": [
                        "Replace failed LED strips as a set when one string is open.",
                        "Replace bulged capacitors or damaged power-board parts with matching ratings.",
                        "Do not bypass protection circuits.",
                        "Reassemble panel layers carefully to avoid cracked glass or diffuser artifacts.",
                    ],
                    "repair_difficulty": "hard",
                    "estimated_time_minutes": 90,
                }
            )

        if family_id == "laptop_power_path" or self._has_any(symptom_text, {"laptop won't turn on", "laptop will not turn on", "no power laptop", "macbook won't turn on"}):
            candidates.append(
                {
                    "fault_id": "laptop_power_delivery_or_main_rail_fault",
                    "name": "Laptop charger, battery, USB-C/DC-in, or main-rail fault",
                    "category": "power",
                    "severity": "major",
                    "likelihood": 0.58,
                    "evidence": ["laptop no-power symptom"],
                    "likely_causes": [
                        "bad charger/cable/DC jack",
                        "battery pack protection or authentication issue",
                        "USB-C PD negotiation failure",
                        "shorted main rail or failed input MOSFET",
                        "embedded controller/BIOS/power button path fault",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "External power and battery isolation triage",
                            "equipment_needed": ["known-good charger", "USB-C power meter if applicable", "multimeter"],
                            "steps": [
                                "Try a known-good charger and cable rated for the laptop.",
                                "Inspect DC jack/USB-C port for damage or looseness.",
                                "Disconnect battery if the model permits safe service and test adapter-only behavior.",
                                "Measure adapter voltage and board input fuse/rail resistance with power disconnected.",
                                "Stop before board-level probing if schematics/boardview and safe tooling are unavailable.",
                            ],
                            "expected_result": "Laptop responds to a known-good charger or the fault is isolated to adapter, jack, battery, or board rail.",
                            "fault_indicated_if": "No adapter negotiation, no input voltage past fuse/MOSFETs, shorted rail, or unchanged no-power state.",
                        }
                    ],
                    "repair_steps": [
                        "Replace charger/cable/DC jack before board-level repair if they fail tests.",
                        "Replace battery only with verified compatible pack.",
                        "For board rail faults, use schematic/boardview-guided diagnosis rather than guessing components.",
                        "Escalate liquid damage, shorted CPU/GPU rails, or paired/security components to specialist workflow.",
                    ],
                    "repair_difficulty": "hard_to_expert",
                    "estimated_time_minutes": 75,
                }
            )

        if family_id in {"small_dc_motor_gadget", "relay_power_box"} or board_type == "motor_or_actuator_driver":
            likelihood = 0.58
            evidence = ["actuator-driver family selected"]
            if self._has_any(symptom_text, {"does not spin", "will not spin", "not spin", "won't spin", "no spin", "won't run", "not run", "no output", "clicks", "buzz", "stall", "weak"}):
                likelihood += 0.14
                evidence.append("reported output/motor symptom")
            if self._has_any(symptom_text, {"fan", "motor", "pump", "actuator"}):
                likelihood += 0.05
                evidence.append("reported motorized gadget symptom")
            if self._has_any(symptom_text, {"hot", "overheat", "heating"}) and family_id == "small_dc_motor_gadget":
                likelihood += 0.05
                evidence.append("driver/load heating symptom")
            if int(counts.get("transistor", 0) or 0) + int(counts.get("mosfet", 0) or 0) >= 2:
                likelihood += 0.08
                evidence.append("switching devices detected")
            candidates.append(
                {
                    "fault_id": "driver_stage_or_load_fault",
                    "name": "Driver stage or motor/load path fault",
                    "category": "actuator",
                    "severity": "major",
                    "likelihood": round(min(likelihood, 0.92), 3),
                    "evidence": evidence,
                    "likely_causes": [
                        "open motor winding or disconnected harness",
                        "shorted motor/load pulling supply down",
                        "failed MOSFET/transistor/relay contact",
                        "missing flyback/protection diode causing repeated driver damage",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Load resistance and isolation check",
                            "equipment_needed": ["multimeter"],
                            "steps": [
                                "Disconnect power and unplug the motor/load harness.",
                                "Measure resistance across the motor/load leads.",
                                "Measure each motor/load lead to board ground.",
                            ],
                            "expected_result": "Finite winding/load resistance and no short to ground unless designed that way.",
                            "fault_indicated_if": "Near-zero resistance, open circuit, or unexpected ground short.",
                        },
                        {
                            "name": "Driver output test with current limit",
                            "equipment_needed": ["bench supply", "multimeter", "dummy load"],
                            "steps": [
                                "Power the board through a current-limited supply.",
                                "Command the output while using a dummy load before reconnecting the real motor.",
                                "Measure output voltage across the load terminals.",
                            ],
                            "expected_result": "Output switches cleanly without current-limit collapse.",
                            "fault_indicated_if": "No switching, supply current limit trips, or driver overheats.",
                        },
                    ],
                    "repair_steps": [
                        "Reseat or replace damaged harness/connectors.",
                        "Replace failed MOSFET/transistor/relay with equal or higher voltage/current rating.",
                        "Replace or add flyback/protection diode for inductive loads.",
                        "Retest with dummy load before reconnecting the motor or external load.",
                    ],
                    "repair_difficulty": "medium_to_hard",
                    "estimated_time_minutes": 45,
                }
            )

        if self._has_any(symptom_text, {"won't turn on", "no power", "dead", "resets", "dim", "hot"}) or "power" in board_type:
            candidates.append(
                {
                    "fault_id": "power_input_or_regulator_fault",
                    "name": "Power input, protection, or regulator fault",
                    "category": "power",
                    "severity": "major",
                    "likelihood": 0.68 if symptoms else 0.44,
                    "evidence": ["reported power symptom"] if symptoms else ["power subsystem visible"],
                    "likely_causes": [
                        "bad adapter, cable, fuse, switch, or jack",
                        "reverse-polarity protection damage",
                        "shorted downstream rail",
                        "failed regulator or dried output capacitor",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Input-to-rail power tree check",
                            "equipment_needed": ["multimeter", "current-limited bench supply"],
                            "steps": [
                                "Identify input voltage and polarity before powering.",
                                "Measure resistance from main rail to ground with power disconnected.",
                                "Power through a current limit and measure input, regulator input, and regulator output.",
                            ],
                            "expected_result": "Input and regulated rails match expected voltages within tolerance.",
                            "fault_indicated_if": "Shorted rail, zero regulator output, excessive current draw, or unstable rail.",
                        }
                    ],
                    "repair_steps": [
                        "Replace damaged cable/jack/fuse/switch first.",
                        "If regulator input is present but output is wrong, replace regulator and nearby capacitors.",
                        "If rail is shorted, isolate loads until the short disappears.",
                        "Retest under current limit before normal power.",
                    ],
                    "repair_difficulty": "medium",
                    "estimated_time_minutes": 30,
                }
            )

        if connector_count >= 2 or self._has_any(symptom_text, {"intermittent", "wiggle", "loose", "only sometimes", "flicker"}):
            candidates.append(
                {
                    "fault_id": "connector_or_harness_fault",
                    "name": "Connector, solder joint, or harness intermittency",
                    "category": "interconnect",
                    "severity": "minor_to_major",
                    "likelihood": 0.62,
                    "evidence": [f"{connector_count} connector candidate(s)", "intermittent/connection symptom" if symptoms else "connector-heavy board"],
                    "likely_causes": [
                        "cracked solder joint",
                        "loose crimp/contact",
                        "broken wire near strain relief",
                        "oxidized connector contact",
                    ],
                    "diagnostic_tests": [
                        {
                            "name": "Wiggle and continuity test",
                            "equipment_needed": ["multimeter", "magnification"],
                            "steps": [
                                "Power off and inspect connector solder joints under magnification.",
                                "Measure continuity from connector pin to next visible node.",
                                "Flex the cable gently while observing continuity.",
                            ],
                            "expected_result": "Stable continuity with no visual cracking.",
                            "fault_indicated_if": "Continuity drops, joint ring cracks are visible, or cable movement changes behavior.",
                        }
                    ],
                    "repair_steps": [
                        "Clean contacts with electronics-safe contact cleaner.",
                        "Reflow cracked connector joints with flux.",
                        "Replace damaged cable or connector shell.",
                        "Add strain relief before final reassembly.",
                    ],
                    "repair_difficulty": "easy_to_medium",
                    "estimated_time_minutes": 20,
                }
            )

        if int(defect.get("defect_count", 0) or 0) > 0:
            candidates.append(
                {
                    "fault_id": "visible_board_damage",
                    "name": "Visible board damage from AOI",
                    "category": "visual_defect",
                    "severity": str(defect.get("max_severity") or "review"),
                    "likelihood": 0.74,
                    "evidence": [f"{defect.get('defect_count')} visual defect candidate(s)"],
                    "likely_causes": ["burn, corrosion, solder bridge, missing part, or mechanical damage"],
                    "diagnostic_tests": [
                        {
                            "name": "AOI candidate review",
                            "equipment_needed": ["magnification", "multimeter"],
                            "steps": [
                                "Review each defect bounding box manually.",
                                "Check for shorts/opens around the flagged location.",
                                "Compare against a known-good board or reference photo when available.",
                            ],
                            "expected_result": "Flagged regions are either confirmed defects or dismissed as cosmetic artifacts.",
                            "fault_indicated_if": "Confirmed solder bridge, corrosion path, burn mark, or broken trace.",
                        }
                    ],
                    "repair_steps": ["Clean corrosion, remove solder bridges, repair traces, or replace damaged parts after confirming electrically."],
                    "repair_difficulty": "medium_to_expert",
                    "estimated_time_minutes": 60,
                }
            )

        ranked = sorted(candidates, key=lambda item: float(item.get("likelihood", 0.0)), reverse=True)
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for candidate in ranked:
            fault_id = candidate.get("fault_id")
            if fault_id in seen:
                continue
            deduped.append(candidate)
            seen.add(fault_id)
        return deduped[:6]

    def _fault_from_database(self, fault: CommonFault, symptom_text: str) -> Dict[str, Any]:
        return {
            "fault_id": fault.fault_id,
            "name": fault.name,
            "category": fault.category.value,
            "severity": fault.severity.value,
            "likelihood": 0.72 if any(symptom.lower() in symptom_text for symptom in fault.symptoms) else 0.58,
            "evidence": [f"symptom match: {fault.name}"],
            "likely_causes": list(fault.common_causes),
            "diagnostic_tests": [asdict(test) for test in fault.diagnostic_tests],
            "repair_steps": list(fault.repair_steps),
            "repair_difficulty": fault.repair_difficulty,
            "estimated_time_minutes": fault.estimated_time_minutes,
        }

    def _scan_evidence(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        detection = analysis.get("detection_summary") or {}
        board = (analysis.get("board_understanding") or {}).get("board_identity") or {}
        connection = analysis.get("machine_connection_map") or {}
        marking = analysis.get("marking_analysis") or {}
        aoi = analysis.get("aoi_inspection") or {}
        return {
            "board_type": board.get("primary_type"),
            "board_confidence": board.get("confidence"),
            "components_detected": detection.get("total_components"),
            "components_by_type": detection.get("components_by_type", {}),
            "connector_count": connection.get("connector_count"),
            "resolved_markings": len(marking.get("components", []) or []),
            "aoi_readiness": aoi.get("readiness"),
            "aoi_blockers": aoi.get("blockers", [])[:6],
        }

    def _safety_profile(self, symptom_text: str, hint_text: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        text = f"{symptom_text} {hint_text}"
        high_voltage = self._has_any(
            text,
            {
                "mains",
                "120v",
                "240v",
                "ac outlet",
                "inverter",
                "microwave",
                "power supply",
                "coffee maker",
                "kettle",
                "heating element",
                "tv",
                "television",
                "backlight",
                "vacuum",
            },
        )
        battery_terms = self._has_any(text, {"battery", "lithium", "li-ion", "lipo", "18650", "cordless", "toothbrush"})
        battery_risk = self._has_any(text, {"swollen", "bulging", "punctured"}) or (
            battery_terms and self._has_any(text, {"hot", "overheat", "heating"})
        )
        thermal_symptom = self._has_any(text, {"hot", "overheat", "gets warm", "gets hot", "unexpected heating"})
        rules = [
            "disconnect power before inspection",
            "start every powered test with a current-limited supply when possible",
            "label connector polarity and voltage before reconnecting loads",
        ]
        if high_voltage:
            rules.insert(0, "do not perform live mains probing; use an isolation transformer and trained procedure")
            rules.append("discharge high-voltage capacitors with a rated discharge tool before handling")
        if battery_risk:
            rules.insert(0, "stop using or charging swollen/hot lithium batteries and move them to a fire-safe area")
        elif thermal_symptom:
            rules.append("treat unexpected heating as a fault; power only briefly under current limit while measuring")
        if ((analysis.get("board_understanding") or {}).get("board_identity") or {}).get("primary_type") == "motor_or_actuator_driver":
            rules.append("test inductive loads with flyback/protection in place")
        return {
            "risk_level": "high" if high_voltage or battery_risk else "low_to_medium",
            "high_voltage_possible": high_voltage,
            "battery_risk_possible": battery_risk,
            "rules": rules,
        }

    def _subsystem_map(self, family_id: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        family = self.FAMILY_CATALOG[family_id]
        blocks = (analysis.get("board_understanding") or {}).get("functional_blocks", []) or []
        mapped = []
        for subsystem in family["subsystems"]:
            block_hits = [
                {
                    "block_type": block.get("block_type"),
                    "confidence": block.get("confidence"),
                    "component_count": block.get("component_count"),
                    "function": block.get("function"),
                }
                for block in blocks
                if self._subsystem_matches_block(subsystem, str(block.get("block_type") or ""))
            ]
            mapped.append(
                {
                    "subsystem": subsystem,
                    "scan_matches": block_hits[:3],
                    "status": "visible_candidate" if block_hits else "not_confirmed_from_scan",
                }
            )
        return mapped

    def _subsystem_matches_block(self, subsystem: str, block_type: str) -> bool:
        text = f"{subsystem} {block_type}".lower()
        return (
            ("power" in subsystem and "power" in block_type)
            or ("driver" in subsystem and "actuator" in block_type)
            or ("connector" in subsystem and "io" in block_type)
            or ("control" in subsystem and "compute" in block_type)
            or ("sensor" in subsystem and "sensor" in block_type)
            or ("display" in subsystem and "user_interface" in block_type)
            or ("usb" in text and "io" in block_type)
        )

    def _diagnostic_flow(
        self,
        family_id: str,
        analysis: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        steps = [
            {
                "order": 1,
                "title": "Document before touching",
                "purpose": "Preserve connector orientation, labels, screws, and cable routing.",
                "actions": [
                    "photograph all sides, connectors, switch positions, and labels",
                    "record symptoms exactly and whether they are intermittent",
                    "mark unknown connectors before unplugging them",
                ],
                "pass_condition": "device state and wiring are reproducible",
                "fail_branch": "capture more evidence before disassembly",
            },
            {
                "order": 2,
                "title": "Unpowered inspection",
                "purpose": "Find obvious mechanical, thermal, liquid, or solder damage without adding risk.",
                "actions": [
                    "inspect connectors, cables, switches, and battery compartment",
                    "look for burned areas, cracked solder joints, corrosion, bulged capacitors, and missing parts",
                    "compare to scan/AOI defect candidates when available",
                ],
                "pass_condition": "no immediate stop-condition damage found",
                "fail_branch": "repair visible damage or quarantine unsafe battery/high-voltage assembly first",
            },
            {
                "order": 3,
                "title": "Power path check",
                "purpose": "Confirm that input power reaches the board and regulated rails are not shorted.",
                "actions": [
                    "measure input connector polarity and voltage",
                    "measure rail-to-ground resistance before applying power",
                    "power with current limit and check regulator outputs",
                ],
                "pass_condition": "rails are present, stable, and not current-limited",
                "fail_branch": "follow power_input_or_regulator_fault playbook",
            },
        ]
        if family_id in {"small_dc_motor_gadget", "relay_power_box"}:
            steps.append(
                {
                    "order": 4,
                    "title": "Output/load isolation",
                    "purpose": "Separate a bad board driver from a bad motor, relay, solenoid, cable, or load.",
                    "actions": [
                        "disconnect the load harness",
                        "measure load resistance and check for shorts to chassis/ground",
                        "test the board output with a dummy load before reconnecting the real load",
                    ],
                    "pass_condition": "dummy load switches correctly and real load measures sane resistance",
                    "fail_branch": "follow driver_stage_or_load_fault or connector_or_harness_fault playbook",
                }
            )
        if family_id == "usb_powered_controller":
            steps.append(
                {
                    "order": 4,
                    "title": "USB and boot path",
                    "purpose": "Separate power, USB bridge, bootloader, and firmware faults.",
                    "actions": [
                        "try a known-good cable and port",
                        "check 5V USB input and 3.3V/5V regulator output",
                        "observe reset/boot LED behavior and serial enumeration",
                    ],
                    "pass_condition": "device enumerates and boot/reset behavior is repeatable",
                    "fail_branch": "follow USB-serial or bootloader fault playbook",
                }
            )
        if family_id == "game_controller_input":
            steps.append(
                {
                    "order": 4,
                    "title": "Input module and contact validation",
                    "purpose": "Separate dirty contacts from worn analog modules or torn interconnects.",
                    "actions": [
                        "record live stick/button behavior before opening",
                        "inspect stick modules, membranes, and flex cables under magnification",
                        "clean contacts and retest before replacing modules",
                        "run platform calibration or a controller tester after reassembly",
                    ],
                    "pass_condition": "all axes center and reach full range; buttons toggle cleanly",
                    "fail_branch": "follow analog_stick_or_button_contact_fault playbook",
                }
            )
        if family_id in {"battery_charging_gadget", "laptop_power_path"}:
            steps.append(
                {
                    "order": 4,
                    "title": "Charger and battery isolation",
                    "purpose": "Separate adapter/dock/contact faults from battery pack or board-level charge faults.",
                    "actions": [
                        "verify charger output with no load",
                        "inspect and clean charge contacts, dock pins, or USB/DC jack",
                        "measure battery/pack voltage without shorting the pack",
                        "test with a known-good charger or safe adapter-only mode when available",
                    ],
                    "pass_condition": "charger, contacts, pack voltage, and charge current are each accounted for",
                    "fail_branch": "follow battery_charge_path_fault or laptop_power_delivery_or_main_rail_fault playbook",
                }
            )
        if family_id == "mains_heater_appliance":
            steps.append(
                {
                    "order": 4,
                    "title": "Unpowered heater safety chain check",
                    "purpose": "Find open heater, thermostat, thermal fuse, switch, or relay faults without live mains probing.",
                    "actions": [
                        "unplug the appliance and document every mains connector",
                        "measure continuity through thermal fuse and thermostat",
                        "measure heating-element resistance and compare with expected wattage",
                        "inspect high-current relay/triac joints and burned terminals",
                    ],
                    "pass_condition": "heater path and safety devices have plausible continuity/resistance",
                    "fail_branch": "follow heater_thermal_cutoff_or_control_fault playbook",
                }
            )
        if family_id == "tv_backlight_power":
            steps.append(
                {
                    "order": 4,
                    "title": "Backlight versus video isolation",
                    "purpose": "Separate a dark backlight from missing image, T-Con, panel, or power-supply faults.",
                    "actions": [
                        "confirm audio and standby/power LED behavior",
                        "use a flashlight test for faint image",
                        "inspect backlight harness and power-board capacitors with power disconnected",
                        "test LED strips only with a proper LED tester and safe disassembly",
                    ],
                    "pass_condition": "fault is isolated to backlight path, video path, or power board",
                    "fail_branch": "follow display_backlight_or_power_supply_fault playbook",
                }
            )
        for idx, candidate in enumerate(candidates[:3], start=len(steps) + 1):
            tests = candidate.get("diagnostic_tests") or []
            if not tests:
                continue
            test = tests[0]
            steps.append(
                {
                    "order": idx,
                    "title": f"Confirm candidate: {candidate.get('name')}",
                    "purpose": test.get("description") or "Confirm the suspected fault before replacing parts.",
                    "actions": test.get("steps", [])[:6],
                    "pass_condition": test.get("expected_result"),
                    "fail_branch": test.get("fault_indicated_if"),
                }
            )
        return steps

    def _repair_playbooks(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        playbooks = []
        for candidate in candidates[:5]:
            playbooks.append(
                {
                    "fault_id": candidate.get("fault_id"),
                    "title": candidate.get("name"),
                    "difficulty": candidate.get("repair_difficulty"),
                    "estimated_time_minutes": candidate.get("estimated_time_minutes"),
                    "repair_steps": candidate.get("repair_steps", [])[:10],
                    "confirmation_after_repair": [
                        "retest on a current-limited supply",
                        "verify fault symptom is gone",
                        "run a short thermal check under normal load",
                        "record the repair and replaced parts",
                    ],
                }
            )
        return playbooks

    def _parts_and_tools(self, family_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        tools = {"multimeter", "magnification", "ESD-safe tweezers", "current-limited bench supply", "soldering iron", "flux"}
        if family_id in {"small_dc_motor_gadget", "relay_power_box"}:
            tools.update({"dummy load", "clip leads", "thermal camera or IR thermometer"})
        if family_id == "usb_powered_controller":
            tools.update({"known-good USB cable", "USB power meter", "USB-serial adapter"})
        if family_id == "game_controller_input":
            tools.update({"controller input tester", "plastic spudger", "electronics-safe contact cleaner"})
        if family_id in {"battery_charging_gadget", "laptop_power_path"}:
            tools.update({"known-good charger", "USB-C power meter", "insulated probes"})
        if family_id in {"mains_heater_appliance", "tv_backlight_power"}:
            tools.update({"rated discharge tool", "insulated probes", "service manual"})
        if family_id == "tv_backlight_power":
            tools.update({"flashlight", "LED backlight tester"})
        parts = set()
        for candidate in candidates:
            text = " ".join(candidate.get("repair_steps", []) + candidate.get("likely_causes", [])).lower()
            if "regulator" in text:
                parts.update({"voltage regulator", "input/output capacitors"})
            if "mosfet" in text or "transistor" in text:
                parts.update({"MOSFET/transistor with matching rating", "flyback diode"})
            if "connector" in text or "harness" in text:
                parts.update({"replacement connector", "wire/crimp terminals", "heat shrink"})
            if "usb" in text:
                parts.update({"USB connector", "USB-serial bridge or external adapter"})
            if "analog stick" in text or "button" in text:
                parts.update({"analog stick module", "button membrane", "replacement flex cable"})
            if "battery" in text or "charger" in text:
                parts.update({"verified compatible battery pack", "charger/dock", "fuse or protection board"})
            if "thermal fuse" in text or "heater" in text:
                parts.update({"thermal fuse with exact rating", "thermostat", "heating element", "relay/triac"})
            if "backlight" in text:
                parts.update({"LED backlight strips", "power-board capacitors", "backlight driver parts"})
        return {
            "tools": sorted(tools),
            "likely_parts": sorted(parts),
            "consumables": ["isopropyl alcohol", "lint-free swabs", "solder wick", "quality solder", "Kapton tape"],
        }

    def _when_to_stop(self, symptom_text: str, hint_text: str) -> List[str]:
        stops = [
            "you cannot identify the input voltage or polarity",
            "the board immediately hits current limit after disconnecting all loads",
            "a replacement part rating cannot be verified",
            "the repair requires live mains probing and you do not have the proper equipment",
        ]
        if self._has_any(f"{symptom_text} {hint_text}", {"battery", "swollen", "bulging", "hot"}):
            stops.insert(0, "battery is swollen, punctured, hissing, smoking, or unusually hot")
        return stops

    def _evidence_to_collect_next(self, analysis: Dict[str, Any], symptoms: List[str], family_id: str) -> List[str]:
        needed = []
        symptom_text = " ".join(symptoms).lower()
        detection = analysis.get("detection_summary") or {}
        if not symptoms:
            needed.append("reported symptoms and exact trigger conditions")
        if not analysis:
            needed.append("top-side and bottom-side board photos")
        if analysis and float(detection.get("average_confidence", 0.0) or 0.0) < 0.55:
            needed.append("sharper closeups of IC markings and connector labels")
        if not (analysis.get("machine_connection_map") or {}).get("connector_count"):
            needed.append("connector closeups with wire colors and labels")
        family_evidence = {
            "game_controller_input": [
                "before/after controller tester readings for stick center, axis range, triggers, and buttons",
                "closeups of analog stick modules, button membranes, flex cables, and PCB contacts",
                "platform calibration or dead-zone validation after reassembly",
            ],
            "battery_charging_gadget": [
                "charger rating and no-load output voltage",
                "battery pack voltage compared with nominal rating",
                "charge current or dock current draw during safe charging test",
                "charge-contact closeups before and after cleaning",
            ],
            "mains_heater_appliance": [
                "confirm appliance is unplugged and capacitors are discharged before continuity checks",
                "thermal fuse and thermostat continuity readings",
                "heating element resistance compared with expected wattage",
                "replacement part temperature/current ratings",
            ],
            "tv_backlight_power": [
                "flashlight-test result showing whether a faint image is present",
                "power-board and backlight connector photos with model labels",
                "standby/main rail readings only if trained for high-voltage TV work",
                "LED strip test result with proper backlight tester",
            ],
            "laptop_power_path": [
                "known-good charger wattage/output and USB-C/DC jack condition",
                "battery connected versus disconnected behavior when the model permits safe service",
                "input fuse or main-rail resistance with power disconnected",
                "model number, board number, and whether boardview/schematic is available",
            ],
            "small_dc_motor_gadget": [
                "motor/load resistance and isolation reading",
                "connector continuity while gently flexing the harness",
                "driver output voltage with current limit and dummy load",
            ],
            "relay_power_box": [
                "load terminal voltage and isolation reading",
                "relay coil or driver input measurement",
                "flyback/protection diode orientation closeup",
            ],
        }
        needed.extend(family_evidence.get(family_id, []))
        if family_id not in {"game_controller_input", "mains_heater_appliance", "tv_backlight_power"}:
            if self._has_any(symptom_text, {"power", "charging", "charge", "battery", "motor", "spin", "dead", "no power", "warm", "hot"}) or family_id == "generic_electronic_module":
                needed.extend(
                    [
                        "input voltage measurement",
                        "rail-to-ground resistance before power-up",
                        "current draw at startup under current limit",
                    ]
                )
        return needed[:8]

    def _overall_confidence(
        self,
        analysis: Dict[str, Any],
        family_score: float,
        candidates: List[Dict[str, Any]],
        symptoms: List[str],
    ) -> float:
        scan_bonus = 0.0
        board_conf = float(((analysis.get("board_understanding") or {}).get("board_identity") or {}).get("confidence", 0.0) or 0.0)
        if board_conf:
            scan_bonus += min(0.2, board_conf * 0.2)
        if symptoms:
            scan_bonus += 0.12
        if candidates:
            scan_bonus += min(0.15, float(candidates[0].get("likelihood", 0.0) or 0.0) * 0.15)
        return round(max(0.05, min(0.92, 0.25 + family_score * 0.35 + scan_bonus)), 3)

    def _quick_summary(self, guide: Dict[str, Any]) -> str:
        family = guide["device_family"]["label"]
        top = guide["fault_candidates"][0]["name"] if guide.get("fault_candidates") else "no strong fault candidate yet"
        action = guide["diagnostic_flow"][0]["title"] if guide.get("diagnostic_flow") else "collect symptoms"
        return f"{family}: start with {action}; top candidate is {top}."

    def _has_any(self, text: str, needles: set[str]) -> bool:
        return any(needle in text for needle in needles)
