"""Convert repair/restoration video references into reproducible playbooks."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from src.intelligence.repair_encyclopedia import RepairEncyclopedia


class RepairVideoPlaybookBuilder:
    """Build independent repair playbooks from video metadata and observations.

    The builder intentionally does not copy video transcripts or frame-by-frame
    creative choices. It converts a video reference plus observed repair actions
    into a safety-first workflow that can be followed with Circuit-AI evidence.
    """

    PATTERNS: Dict[str, Dict[str, Any]] = {
        "console_cleaning_restoration": {
            "label": "Console/handheld cleaning and restoration",
            "keywords": {"game boy", "console", "controller", "handheld", "retro", "restoration", "cleaning"},
            "core_actions": [
                "document condition and missing parts",
                "disassemble shell and organize screws",
                "separate plastics from electronics",
                "clean shell, buttons, membranes, and contacts",
                "inspect battery terminals, connector pads, and PCB corrosion",
                "repair broken traces or replace damaged contacts",
                "reassemble and validate every control/input",
            ],
            "common_risks": [
                "chemical damage to plastics",
                "torn ribbon cables",
                "lost screw position causing board or shell damage",
                "corrosion hidden under battery terminals or connectors",
            ],
        },
        "controller_input_repair": {
            "label": "Controller stick/button input repair",
            "keywords": {"stick drift", "joystick", "controller", "gamepad", "dualsense", "joy-con", "xbox controller", "button"},
            "core_actions": [
                "record live input behavior before opening",
                "document screw, ribbon, and connector positions",
                "inspect stick modules, membranes, and PCB contacts",
                "clean contacts and retest before replacing modules",
                "replace worn analog stick or membrane parts when cleaning fails",
                "run calibration and functional validation after reassembly",
            ],
            "common_risks": [
                "tearing controller flex cables",
                "damaging plastic clips",
                "using solvent that attacks rubber membranes",
                "replacing a stick module without calibration or test evidence",
            ],
        },
        "battery_charging_diagnostics": {
            "label": "Battery and charging-path diagnostics",
            "keywords": {"not charging", "won't charge", "doesn't charge", "battery", "charger", "toothbrush", "cordless", "drill"},
            "core_actions": [
                "document charger, dock, contacts, and battery rating",
                "inspect contacts, ports, and corrosion before applying power",
                "verify charger output and cable/dock continuity",
                "measure pack voltage and protection path with power disconnected",
                "separate battery replacement from charge-controller or BMS faults",
                "record charge current and post-repair runtime validation",
            ],
            "common_risks": [
                "shorting battery packs while probing",
                "replacing cells without matching chemistry and protection",
                "waterproofing damage on sealed rechargeable gadgets",
                "brand-specific BMS lockouts after cell replacement",
            ],
        },
        "mains_or_backlight_safety_triage": {
            "label": "Mains heater or TV backlight safety triage",
            "keywords": {"coffee maker", "not heating", "thermal fuse", "heating element", "tv", "television", "backlight", "sound but no picture"},
            "core_actions": [
                "confirm the repair can be done unpowered or with trained high-voltage procedure",
                "document mains wiring, safety devices, and connector orientation",
                "use unpowered continuity/resistance checks first",
                "isolate heater, thermal fuse, thermostat, backlight strip, or power-board path",
                "replace only parts with verified voltage, current, and temperature ratings",
                "perform insulation, leak, thermal, or display validation before return to use",
            ],
            "common_risks": [
                "live mains probing without isolation and training",
                "incorrect thermal fuse or heater rating",
                "charged capacitors in TV power supplies",
                "cracking LCD glass or damaging diffuser layers",
            ],
        },
        "board_level_fault_finding": {
            "label": "Board-level electronic fault finding",
            "keywords": {
                "pcb",
                "board",
                "fault",
                "short",
                "schematic",
                "microscope",
                "solder",
                "gpu",
                "xbox",
                "ps5",
                "repair",
                "fixing",
                "fix",
                "driver",
                "mosfet",
                "regulator",
                "not spin",
                "will not spin",
            },
            "core_actions": [
                "capture symptoms and board history",
                "inspect under magnification",
                "check input resistance and obvious shorts",
                "inject or apply current-limited power only after polarity is known",
                "divide the circuit into power, control, IO, and load sections",
                "replace or rework only after measurements isolate the fault",
                "thermal and functional retest after repair",
            ],
            "common_risks": [
                "misidentified voltage rail",
                "lifting pads during rework",
                "shorting adjacent pins while probing",
                "replacing parts without confirming the upstream cause",
            ],
        },
        "bulk_broken_device_triage": {
            "label": "Bulk broken-device triage and repair/resale",
            "keywords": {"broken", "lot", "bulk", "resell", "make money", "repairability"},
            "core_actions": [
                "sort devices by symptom and visible condition",
                "perform non-invasive power and port checks",
                "separate quick wins from board-level repairs",
                "estimate parts, labor, and resale value before deep work",
                "document pass/fail results per unit",
                "salvage donor parts from no-fix units",
            ],
            "common_risks": [
                "spending expert time on low-margin repairs",
                "mixing untested and tested parts",
                "missing serial/model differences between units",
                "selling a device without burn-in validation",
            ],
        },
        "mechanical_cleaning_restoration": {
            "label": "Mechanical cleaning and cosmetic restoration",
            "keywords": {"rust", "dirty", "clean", "restore", "yellowed", "retrobright", "case", "shell"},
            "core_actions": [
                "photograph original state and labels",
                "disassemble into material groups",
                "test cleaner on hidden area",
                "clean mechanically before chemical treatment",
                "protect electronics from water and solvents",
                "recondition contacts, springs, and fasteners",
                "reassemble and verify fit/function",
            ],
            "common_risks": [
                "faked or cosmetic-only restoration mistaken for repair",
                "solvent attacking plastic",
                "water trapped under chips or switches",
                "hydrogen peroxide/light treatment changing plastic color or texture",
            ],
        },
    }

    def __init__(self, encyclopedia: RepairEncyclopedia | None = None):
        self.encyclopedia = encyclopedia or RepairEncyclopedia()

    def build(
        self,
        video_reference: Dict[str, Any],
        analysis: Dict[str, Any] | None = None,
        symptoms: Sequence[str] | None = None,
        device_hint: str | None = None,
    ) -> Dict[str, Any]:
        title = str(video_reference.get("title") or "")
        channel = str(video_reference.get("channel") or "")
        description = str(video_reference.get("description") or "")
        observed_actions = [str(item) for item in video_reference.get("observed_actions", []) or []]
        pattern_id, pattern_score, evidence = self._select_pattern(title, channel, description, observed_actions, device_hint)
        repair_guide = self.encyclopedia.generate(
            analysis=analysis or {},
            symptoms=list(symptoms or []) + self._symptoms_from_video_text(title, description, observed_actions),
            device_hint=device_hint or title,
        )
        pattern = self.PATTERNS[pattern_id]
        return {
            "mode": "repair_video_to_playbook",
            "source_video": {
                "title": title,
                "channel": channel,
                "url": video_reference.get("url"),
                "notes": video_reference.get("notes"),
            },
            "copyright_boundary": [
                "Use the linked video as a reference source; do not clone the creator's edit, narration, or exact transcript.",
                "This playbook is an independent safety and repair workflow derived from observed repair intent and Circuit-AI evidence.",
            ],
            "video_pattern": {
                "id": pattern_id,
                "label": pattern["label"],
                "confidence": round(pattern_score, 3),
                "evidence": evidence,
            },
            "watch_map": self._watch_map(pattern_id),
            "circuit_ai_inputs": self._circuit_ai_inputs(pattern_id),
            "recreation_flow": self._recreation_flow(pattern_id, repair_guide),
            "repair_guide": repair_guide,
            "operator_capture_checklist": self._operator_capture_checklist(pattern_id),
            "quality_gates": self._quality_gates(pattern_id, repair_guide),
            "difficulty": self._difficulty(pattern_id, repair_guide),
            "can_follow_score": self._can_follow_score(pattern_score, repair_guide, bool(analysis)),
            "limitations": [
                "A single video may omit failed attempts, safety setup, exact measurements, or model-specific differences.",
                "The user still needs the actual device, photos, measurements, and replacement-part verification.",
                "High-voltage, battery, microwave, CRT, and mains appliances require stricter procedures than generic gadget repairs.",
            ],
        }

    def _select_pattern(
        self,
        title: str,
        channel: str,
        description: str,
        observed_actions: List[str],
        device_hint: str | None,
    ) -> tuple[str, float, List[str]]:
        text = " ".join([title, channel, description, device_hint or "", *observed_actions]).lower()
        scores = {pattern_id: 0.05 for pattern_id in self.PATTERNS}
        evidence: Dict[str, List[str]] = {pattern_id: [] for pattern_id in self.PATTERNS}
        for pattern_id, pattern in self.PATTERNS.items():
            hits = sorted(keyword for keyword in pattern["keywords"] if keyword in text)
            if hits:
                scores[pattern_id] += min(0.75, 0.12 * len(hits))
                evidence[pattern_id].append(f"keyword hits: {', '.join(hits[:8])}")
        if "tronicsfix" in text:
            scores["bulk_broken_device_triage"] += 0.18
            scores["board_level_fault_finding"] += 0.12
            evidence["bulk_broken_device_triage"].append("channel style: broken-device triage")
        if "odd tinkering" in text:
            scores["console_cleaning_restoration"] += 0.22
            scores["mechanical_cleaning_restoration"] += 0.16
            evidence["console_cleaning_restoration"].append("channel style: detailed restoration/cleaning")
        if "ifixit" in text:
            scores["console_cleaning_restoration"] += 0.1
            scores["board_level_fault_finding"] += 0.1
            evidence["console_cleaning_restoration"].append("guide-oriented source")
        best_id, score = max(scores.items(), key=lambda item: item[1])
        return best_id, min(score, 0.95), evidence[best_id]

    def _symptoms_from_video_text(self, title: str, description: str, observed_actions: List[str]) -> List[str]:
        text = " ".join([title, description, *observed_actions]).lower()
        symptoms = []
        for phrase in [
            "won't turn on",
            "not charging",
            "no power",
            "corrosion",
            "dirty contacts",
            "won't spin",
            "short circuit",
            "overheating",
            "broken trace",
            "liquid damage",
        ]:
            if phrase in text:
                symptoms.append(phrase)
        return symptoms

    def _watch_map(self, pattern_id: str) -> List[Dict[str, Any]]:
        base = [
            {
                "moment": "before disassembly",
                "capture": ["device model", "initial symptom", "all labels", "connector orientation", "missing screws or parts"],
            },
            {
                "moment": "first board view",
                "capture": ["top-side board photo", "bottom-side board photo", "chip markings", "connector labels", "corrosion/burn areas"],
            },
            {
                "moment": "before power test",
                "capture": ["input voltage", "polarity", "rail-to-ground resistance", "current limit setting"],
            },
            {
                "moment": "after repair",
                "capture": ["retest result", "current draw", "thermal behavior", "remaining symptoms"],
            },
        ]
        if pattern_id in {"console_cleaning_restoration", "mechanical_cleaning_restoration"}:
            base.insert(
                2,
                {
                    "moment": "cleaning phase",
                    "capture": ["material type", "cleaner used", "soak/contact time", "before/after contact resistance if applicable"],
                },
            )
        if pattern_id == "controller_input_repair":
            base.insert(
                2,
                {
                    "moment": "input diagnosis",
                    "capture": ["stick center values", "axis range", "button failures", "module markings", "membrane/contact condition"],
                },
            )
        if pattern_id == "battery_charging_diagnostics":
            base.insert(
                2,
                {
                    "moment": "charging diagnosis",
                    "capture": ["charger rating", "charger output", "battery nominal voltage", "pack voltage", "charge current"],
                },
            )
        if pattern_id == "mains_or_backlight_safety_triage":
            base.insert(
                2,
                {
                    "moment": "safety isolation",
                    "capture": ["mains wiring map", "discharge status", "thermal fuse/element resistance", "backlight flashlight-test result"],
                },
            )
        return base

    def _circuit_ai_inputs(self, pattern_id: str) -> List[str]:
        inputs = [
            "clear PCB image before cleaning or rework",
            "closeups of damaged regions and IC markings",
            "reported symptoms",
            "input voltage and current draw",
        ]
        if pattern_id in {"console_cleaning_restoration", "mechanical_cleaning_restoration"}:
            inputs.extend(["shell/contact photos before and after cleaning", "battery compartment closeup"])
        if pattern_id == "controller_input_repair":
            inputs.extend(["live controller tester readings", "stick/button module closeups", "post-clean calibration result"])
        if pattern_id == "battery_charging_diagnostics":
            inputs.extend(["charger rating", "charger output voltage", "battery pack voltage", "charge current", "contact closeups"])
        if pattern_id == "mains_or_backlight_safety_triage":
            inputs.extend(["unpowered resistance/continuity readings", "service label ratings", "flashlight-test/backlight result"])
        if pattern_id == "bulk_broken_device_triage":
            inputs.extend(["per-unit condition sheet", "parts/labor/resale estimate"])
        return inputs

    def _recreation_flow(self, pattern_id: str, repair_guide: Dict[str, Any]) -> List[Dict[str, Any]]:
        pattern = self.PATTERNS[pattern_id]
        flow = []
        for idx, action in enumerate(pattern["core_actions"], start=1):
            flow.append(
                {
                    "order": idx,
                    "action": action,
                    "circuit_ai_support": self._support_for_action(action),
                    "done_when": self._done_when(action),
                }
            )
        diagnostic_start = len(flow) + 1
        for offset, step in enumerate((repair_guide.get("diagnostic_flow") or [])[:4]):
            flow.append(
                {
                    "order": diagnostic_start + offset,
                    "action": step.get("title"),
                    "circuit_ai_support": "repair encyclopedia diagnostic branch",
                    "done_when": step.get("pass_condition"),
                }
            )
        return flow

    def _support_for_action(self, action: str) -> str:
        if "inspect" in action or "capture" in action or "document" in action:
            return "image scan, board role inference, AOI defect candidates"
        if "power" in action or "resistance" in action or "short" in action:
            return "repair guide measurement plan and stop conditions"
        if "clean" in action or "corrosion" in action:
            return "cleaning checklist plus before/after evidence capture"
        if "repair" in action or "replace" in action or "rework" in action:
            return "fault candidate playbooks and validation gates"
        if "resale" in action or "salvage" in action:
            return "salvage opportunity and build-package scoring"
        return "operator checklist"

    def _done_when(self, action: str) -> str:
        if "document" in action or "capture" in action:
            return "photos and notes are sufficient to reassemble and compare"
        if "clean" in action:
            return "no residue remains and electronics are fully dry before power"
        if "power" in action:
            return "rails and current draw are within expected limits"
        if "repair" in action or "replace" in action:
            return "fault is confirmed fixed by measurement, not only by appearance"
        if "reassemble" in action:
            return "all controls/connectors pass functional validation"
        return "operator records pass/fail result"

    def _operator_capture_checklist(self, pattern_id: str) -> List[str]:
        checklist = [
            "device model and board revision",
            "symptoms before repair",
            "tool and chemical list",
            "before/after photos for every repaired area",
            "measurements before replacing parts",
            "validation result after reassembly",
        ]
        if pattern_id in {"console_cleaning_restoration", "mechanical_cleaning_restoration"}:
            checklist.extend(["plastic material notes", "cleaner/chemical dwell time", "drying time before power"])
        if pattern_id == "controller_input_repair":
            checklist.extend(["before/after input tester readings", "calibration status", "stick/module part number"])
        if pattern_id == "battery_charging_diagnostics":
            checklist.extend(["battery chemistry and rating", "charger output", "charge current", "runtime after repair"])
        if pattern_id == "mains_or_backlight_safety_triage":
            checklist.extend(["discharge confirmation", "thermal/backlight resistance readings", "replacement part ratings"])
        if pattern_id == "bulk_broken_device_triage":
            checklist.extend(["unit-by-unit status table", "parts/labor/resale value table"])
        return checklist

    def _quality_gates(self, pattern_id: str, repair_guide: Dict[str, Any]) -> List[str]:
        gates = [
            "no unknown input voltage or polarity",
            "no powered testing before rail-to-ground resistance check",
            "repair action tied to a confirmed fault candidate",
            "post-repair thermal and functional test recorded",
        ]
        gates.extend((repair_guide.get("safety_profile") or {}).get("rules", [])[:4])
        if pattern_id in {"console_cleaning_restoration", "mechanical_cleaning_restoration"}:
            gates.append("electronics are completely dry before power-up")
        if pattern_id == "battery_charging_diagnostics":
            gates.append("battery chemistry, polarity, protection, and rating are verified before replacement")
        if pattern_id == "mains_or_backlight_safety_triage":
            gates.append("no live mains or TV power-board probing without trained high-voltage procedure")
        if pattern_id == "controller_input_repair":
            gates.append("controller tester/calibration passes after reassembly")
        return list(dict.fromkeys(gates))

    def _difficulty(self, pattern_id: str, repair_guide: Dict[str, Any]) -> str:
        top = (repair_guide.get("fault_candidates") or [{}])[0]
        difficulty = str(top.get("repair_difficulty") or "")
        if "expert" in difficulty or pattern_id == "board_level_fault_finding":
            return "hard_to_expert"
        if "hard" in difficulty:
            return "medium_to_hard"
        if pattern_id in {"console_cleaning_restoration", "mechanical_cleaning_restoration"}:
            return "easy_to_medium_unless_board_repair_is_needed"
        return difficulty or "medium"

    def _can_follow_score(self, pattern_score: float, repair_guide: Dict[str, Any], has_analysis: bool) -> float:
        score = 0.25 + pattern_score * 0.25 + float(repair_guide.get("confidence", 0.0) or 0.0) * 0.25
        if has_analysis:
            score += 0.18
        if repair_guide.get("fault_candidates"):
            score += 0.07
        return round(min(score, 0.95), 3)
