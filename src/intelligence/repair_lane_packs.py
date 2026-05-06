"""Launch-focused repair lane packs for the case workbench."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


LANE_PACKS: Dict[str, Dict[str, Any]] = {
    "controller_input": {
        "lane_id": "controller_input",
        "label": "Controller stick/button repair",
        "status": "pilot_ready",
        "positioning": "Fast triage for controller drift, buttons, triggers, flex cables, and contact cleaning.",
        "best_for": ["Xbox/PlayStation controllers", "Joy-Con style controllers", "retro gamepads"],
        "not_for": ["BGA/MCU faults", "firmware pairing issues", "water-damaged battery packs without inspection"],
        "case_templates": [
            "Xbox controller stick drift repair",
            "DualSense trigger intermittent after drop",
            "Retro gamepad buttons require hard press",
        ],
        "intake_questions": [
            "Which controller model and revision is it?",
            "Which stick axis, button, trigger, or D-pad input is wrong?",
            "Does the fault change after cleaning, calibration, or cable movement?",
            "Was there liquid damage, impact damage, or previous repair?",
        ],
        "evidence_prompts": [
            "front and rear shell photos before opening",
            "board and flex-cable photos after opening",
            "closeups of stick modules, button membranes, and PCB contacts",
            "before/after input tester readings",
            "post-reassembly calibration result",
        ],
        "measurements": [
            "stick center, min, max, and jitter in a controller tester",
            "button/trigger pass-fail table",
            "continuity through suspect flex cable when gently moved",
        ],
        "common_faults": [
            "dirty or worn potentiometer track",
            "worn analog stick module",
            "contaminated membrane/contact pad",
            "torn or loose flex cable",
        ],
        "stop_conditions": [
            "battery is swollen, punctured, or hot",
            "board corrosion reaches fine-pitch IC pins",
            "replacement stick module pinout/rating cannot be verified",
        ],
        "outcome_fields": ["fixed_input", "module_replaced", "calibration_passed", "time_minutes", "parts_cost_usd"],
        "launch_target": {"case_count": 20, "review_completion": 0.75, "successful_fix_rate": 0.65},
    },
    "battery_charging": {
        "lane_id": "battery_charging",
        "label": "Battery and charging gadgets",
        "status": "pilot_ready",
        "positioning": "Separate charger, contact, battery, fuse/BMS, and charge-controller faults safely.",
        "best_for": ["electric toothbrushes", "small rechargeable gadgets", "cordless tool chargers and packs"],
        "not_for": ["swollen lithium packs", "EV/e-bike high-energy packs", "packs requiring undocumented BMS reset"],
        "case_templates": [
            "Electric toothbrush not charging",
            "Cordless drill battery will not charge",
            "Portable LED light charges but dies quickly",
        ],
        "intake_questions": [
            "What is the battery chemistry and nominal voltage?",
            "What charger or dock is being used, and is it known good?",
            "Does the device run from external power without the battery?",
            "Are charge contacts corroded, loose, or contaminated?",
        ],
        "evidence_prompts": [
            "charger label and connector/dock photos",
            "battery label, pack connector, and protection board photos",
            "charge contacts before and after cleaning",
            "board photos around fuse, charging IC, and battery connector",
        ],
        "measurements": [
            "charger no-load output voltage",
            "battery pack voltage compared with nominal rating",
            "charge current or dock current draw during safe charge attempt",
            "continuity through fuse/thermal link/protection path with power disconnected",
        ],
        "common_faults": [
            "dirty or corroded charge contacts",
            "bad adapter/dock/cable",
            "aged cell with high internal resistance",
            "open fuse or protection path",
            "failed charge-controller/BMS stage",
        ],
        "stop_conditions": [
            "battery is swollen, leaking, hissing, punctured, or unusually hot",
            "pack voltage is dangerously low for its chemistry",
            "cell replacement would require unprotected cells or unknown BMS behavior",
        ],
        "outcome_fields": ["charger_fault", "battery_replaced", "runtime_minutes", "value_recovered_usd", "safe_to_return"],
        "launch_target": {"case_count": 20, "review_completion": 0.75, "successful_fix_rate": 0.6},
    },
    "small_motor_usb": {
        "lane_id": "small_motor_usb",
        "label": "USB/small motor gadgets",
        "status": "pilot_ready",
        "positioning": "Repair and salvage small low-voltage motor, fan, pump, LED, and relay gadgets.",
        "best_for": ["USB desk fans", "small pumps", "toy motor boards", "low-voltage relay/load boards"],
        "not_for": ["mains motors", "large battery packs", "unknown high-current loads without ratings"],
        "case_templates": [
            "USB fan warms but motor will not spin",
            "Small pump buzzes but does not move water",
            "Relay/load controller clicks but output never switches",
        ],
        "intake_questions": [
            "What input voltage and current rating does the gadget expect?",
            "Does the load move, buzz, heat, or stay completely dead?",
            "Does flexing a cable or connector change the behavior?",
            "Can the motor/load be disconnected from the board for testing?",
        ],
        "evidence_prompts": [
            "top and bottom board photos",
            "connector and wire-color closeups",
            "driver transistor/MOSFET/relay closeups",
            "motor/load label or resistance reading",
            "burn/corrosion/cracked-solder closeups",
        ],
        "measurements": [
            "input voltage under attempted startup",
            "rail-to-ground resistance before power-up",
            "motor/load resistance and isolation reading",
            "connector continuity while gently flexing the harness",
            "driver output voltage with current limit and dummy load",
        ],
        "common_faults": [
            "broken connector or harness",
            "open or shorted motor/load",
            "failed MOSFET/transistor/relay contact",
            "missing or damaged flyback/protection diode",
            "regulator or input protection fault",
        ],
        "stop_conditions": [
            "input voltage or polarity cannot be identified",
            "board immediately hits current limit with loads disconnected",
            "replacement driver rating cannot be verified",
        ],
        "outcome_fields": ["load_repaired", "driver_replaced", "harness_repaired", "time_minutes", "value_recovered_usd"],
        "launch_target": {"case_count": 20, "review_completion": 0.75, "successful_fix_rate": 0.65},
    },
}


class RepairLanePacks:
    """Return productized repair lanes and match them to case text."""

    def list_packs(self) -> Dict[str, Any]:
        packs = [self._summarize(pack) for pack in LANE_PACKS.values()]
        return {
            "mode": "repair_lane_packs",
            "packs": packs,
            "pilot_lane_ids": [pack["lane_id"] for pack in packs if pack.get("status") == "pilot_ready"],
            "recommended_launch_order": ["controller_input", "battery_charging", "small_motor_usb"],
        }

    def get_pack(self, lane_id: str) -> Dict[str, Any] | None:
        pack = LANE_PACKS.get(lane_id)
        return deepcopy(pack) if pack else None

    def match(self, text: str) -> Dict[str, Any]:
        normalized = str(text or "").lower()
        matches: List[Dict[str, Any]] = []
        for lane_id, pack in LANE_PACKS.items():
            haystack = " ".join(
                [
                    pack["label"],
                    pack["positioning"],
                    *pack["best_for"],
                    *pack["case_templates"],
                    *pack["common_faults"],
                ]
            ).lower()
            hits = sorted({token for token in self._keywords(lane_id) if token in normalized or token in haystack and token in normalized})
            score = 0.12 + min(0.78, 0.13 * len(hits))
            if any(template.lower() in normalized for template in pack["case_templates"]):
                score += 0.18
            matches.append(
                {
                    "lane_id": lane_id,
                    "label": pack["label"],
                    "score": round(min(score, 0.98), 3),
                    "signal_hits": hits[:8],
                    "status": pack["status"],
                }
            )
        matches.sort(key=lambda item: item["score"], reverse=True)
        return {
            "mode": "repair_lane_match",
            "matched": bool(matches and matches[0]["score"] >= 0.25),
            "top_matches": matches,
            "recommended_lane_id": matches[0]["lane_id"] if matches else None,
        }

    def _summarize(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "lane_id": pack["lane_id"],
            "label": pack["label"],
            "status": pack["status"],
            "positioning": pack["positioning"],
            "best_for": list(pack["best_for"]),
            "not_for": list(pack["not_for"]),
            "case_templates": list(pack["case_templates"]),
            "evidence_prompt_count": len(pack["evidence_prompts"]),
            "measurement_count": len(pack["measurements"]),
            "launch_target": dict(pack["launch_target"]),
        }

    def _keywords(self, lane_id: str) -> List[str]:
        if lane_id == "controller_input":
            return ["controller", "stick drift", "joystick", "thumbstick", "button", "trigger", "gamepad", "joy-con", "dualsense", "xbox"]
        if lane_id == "battery_charging":
            return ["not charging", "battery", "charger", "charging dock", "toothbrush", "cordless", "drill", "pack", "bms"]
        return ["usb fan", "motor", "pump", "relay", "load", "mosfet", "harness", "connector", "will not spin", "no spin", "buzzes"]
