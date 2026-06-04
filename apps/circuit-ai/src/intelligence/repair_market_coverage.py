"""Market coverage scoring for repair/restoration video item classes."""

from __future__ import annotations

from typing import Any, Dict, List


class RepairMarketCoverage:
    """Score whether Circuit-AI can serve common repair-video item classes."""

    ITEM_CLASSES: Dict[str, Dict[str, Any]] = {
        "retro_handheld_console": {
            "label": "Retro handheld consoles",
            "examples": ["Game Boy", "Game Boy Color", "Game Gear", "PS Vita"],
            "signals": {"game boy", "handheld", "retro console", "vita", "game gear"},
            "relevance": 0.92,
            "coverage": 0.78,
            "why": [
                "strong overlap with cleaning/restoration videos",
                "PCB, buttons, contacts, corrosion, battery terminals, speakers, screens are inspectable",
                "repair flow can combine board scan, connector map, cleaning checklist, and functional validation",
            ],
            "gaps": [
                "model-specific shell, screen, ribbon, and button-membrane parts catalog",
                "before/after contact-resistance capture",
                "known-good reference photos for popular revisions",
            ],
        },
        "game_controller": {
            "label": "Game controllers",
            "examples": ["DualSense", "Xbox controller", "Joy-Con", "retro controller"],
            "signals": {"controller", "joystick", "stick drift", "dualsense", "joy-con", "xbox controller"},
            "relevance": 0.9,
            "coverage": 0.74,
            "why": [
                "high customer demand and many cleaning/repair videos",
                "cleaning, connector, button, flex, USB, and battery faults fit current repair playbooks",
                "analog stick drift now has a dedicated diagnostic and validation lane",
                "salvage/arbitrage workflow can rank lots and donor parts",
            ],
            "gaps": [
                "calibration software workflow per platform",
                "part compatibility catalog for stick modules, membranes, shells, and batteries",
                "Hall-effect upgrade compatibility and dead-zone tuning knowledge",
            ],
        },
        "modern_game_console": {
            "label": "Modern game consoles",
            "examples": ["Nintendo Switch", "PlayStation 5", "Xbox Series", "Steam Deck"],
            "signals": {"switch", "ps5", "xbox", "steam deck", "hdmi", "console"},
            "relevance": 0.96,
            "coverage": 0.52,
            "why": [
                "very valuable market, common on repair channels",
                "system can help with triage, visual board evidence, connector inspection, corrosion, fans, power path, and resale math",
                "basic cleaning/thermal service can be made reproducible",
            ],
            "gaps": [
                "microsoldering workflows for HDMI/USB-C ports and torn pads",
                "boardview/schematic integration per console revision",
                "BGA/APU/storage faults are beyond image-only guidance",
                "firmware/account/drive pairing constraints need model-specific knowledge",
            ],
        },
        "small_usb_gadget": {
            "label": "Small USB powered gadgets",
            "examples": ["USB fan", "LED gadget", "desk toy", "small pump", "powered hub"],
            "signals": {"usb fan", "usb", "desk fan", "small pump", "led gadget", "hub"},
            "relevance": 0.72,
            "coverage": 0.86,
            "why": [
                "excellent match for low-voltage repair encyclopedia lane",
                "power, connector, regulator, driver, load, and cable faults are covered",
                "safe current-limited diagnostic flow is straightforward",
            ],
            "gaps": [
                "device-specific enclosures and mechanical replacement parts",
                "load libraries for motors, fans, pumps, heaters, and LEDs",
            ],
        },
        "sensor_display_module": {
            "label": "Sensor/display modules",
            "examples": ["weather monitor", "meter", "thermostat module", "panel display"],
            "signals": {"sensor", "display", "oled", "lcd", "meter", "thermostat"},
            "relevance": 0.7,
            "coverage": 0.74,
            "why": [
                "matches board understanding, OCR, connector mapping, recipe/build package flow",
                "power, sensor, display, and firmware smoke-test plans are already present",
            ],
            "gaps": [
                "calibration procedure database",
                "display ribbon/backlight-specific guides",
                "sensor accuracy validation fixtures",
            ],
        },
        "battery_charging_gadget": {
            "label": "Battery charging gadgets",
            "examples": ["electric toothbrush", "small rechargeable tool", "portable light", "wireless accessory"],
            "signals": {"toothbrush", "not charging", "won't charge", "doesn't charge", "battery", "charger", "charging dock"},
            "relevance": 0.74,
            "coverage": 0.66,
            "why": [
                "charging contacts, docks, batteries, fuses, and protection boards fit the evidence workflow",
                "board-in-hand measurements can quickly separate charger, contact, battery, and PCB faults",
                "good fit for repair/restoration videos where the owner has the item in hand",
            ],
            "gaps": [
                "sealed-device opening procedures and gasket/waterproofing validation",
                "chemistry-specific battery replacement and recycling rules",
                "brand/model battery compatibility catalog",
            ],
        },
        "power_tool_battery_pack": {
            "label": "Power-tool batteries and chargers",
            "examples": ["cordless drill pack", "tool charger", "lithium battery pack"],
            "signals": {"cordless drill", "drill battery", "tool battery", "power tool", "battery pack", "bms"},
            "relevance": 0.78,
            "coverage": 0.54,
            "why": [
                "the engine can triage charger output, pack voltage, contacts, fuse/BMS path, and salvage value",
                "useful for deciding repair versus donor-cell/parts salvage",
            ],
            "gaps": [
                "pack-opening safety and cell-balancing workflows",
                "brand-specific BMS lockout/reset behavior",
                "cell matching, spot welding, and legal shipping constraints",
            ],
        },
        "tv_monitor_backlight": {
            "label": "TV/monitor backlight and power faults",
            "examples": ["LED TV", "LCD monitor", "backlight power board"],
            "signals": {"tv", "television", "monitor", "backlight", "sound but no picture", "no picture", "screen dark"},
            "relevance": 0.72,
            "coverage": 0.46,
            "why": [
                "the system can structure flashlight-test, backlight-driver, LED-strip, and power-board evidence",
                "useful as a safety-first triage and parts/value decision flow",
            ],
            "gaps": [
                "high-voltage TV power-board training and liability controls",
                "panel disassembly procedure per model",
                "known-good rail tables and LED-strip compatibility data",
            ],
        },
        "simple_mains_heater_appliance": {
            "label": "Simple mains heater appliances",
            "examples": ["coffee maker", "kettle", "warming plate"],
            "signals": {"coffee maker", "coffee", "not heating", "not hot", "heating element", "thermal fuse", "thermostat", "kettle"},
            "relevance": 0.64,
            "coverage": 0.48,
            "why": [
                "the system can generate a safety-first unpowered continuity workflow",
                "thermal fuse, thermostat, heater element, and relay/triac triage can be represented cleanly",
                "useful for deciding whether the repair should stop, proceed, or be escalated",
            ],
            "gaps": [
                "mains isolation and certification/liability controls",
                "model-specific part ratings and water/leak safety validation",
                "clear separation from high-risk appliances like microwaves and compressors",
            ],
        },
        "audio_retro_electronics": {
            "label": "Audio and retro electronics",
            "examples": ["cassette player", "radio", "speaker amp", "VCR accessory"],
            "signals": {"cassette", "radio", "speaker", "amp", "audio", "vcr"},
            "relevance": 0.76,
            "coverage": 0.45,
            "why": [
                "cleaning and visual PCB triage are useful",
                "power and connector faults fit current guide structure",
            ],
            "gaps": [
                "analog audio signal-path diagnosis",
                "belt, gear, head alignment, tape transport, and mechanical timing procedures",
                "oscilloscope/audio injection workflows",
            ],
        },
        "phone_or_tablet": {
            "label": "Phones and tablets",
            "examples": ["iPhone", "Samsung phone", "iPad", "Android tablet"],
            "signals": {"iphone", "android", "ipad", "tablet", "phone"},
            "relevance": 0.94,
            "coverage": 0.36,
            "why": [
                "older repair-guide scaffolding exists",
                "symptom intake and safety warnings are useful",
            ],
            "gaps": [
                "model-specific disassembly and parts compatibility",
                "battery/fire safety and adhesive workflows",
                "micro-soldering, paired components, calibration, and waterproofing constraints",
                "board-level phone diagnostics require schematics/boardviews and expert tooling",
            ],
        },
        "laptop_or_macbook": {
            "label": "Laptops and MacBooks",
            "examples": ["MacBook", "Windows laptop", "Chromebook"],
            "signals": {"laptop", "macbook", "chromebook", "usb-c laptop", "won't turn on laptop"},
            "relevance": 0.88,
            "coverage": 0.42,
            "why": [
                "symptom intake and basic power/charging flow exist",
                "visual board scan can help with obvious damage",
                "charger, battery, DC-in/USB-C, and main-rail triage now has a bounded workflow",
            ],
            "gaps": [
                "boardview/schematic integration",
                "USB-C PD, battery authentication, and charger negotiation diagnostics",
                "fine-pitch board repair and model-specific teardown",
            ],
        },
        "mains_appliance": {
            "label": "Mains appliances",
            "examples": ["coffee maker", "microwave", "vacuum", "washing machine", "power supply"],
            "signals": {"appliance", "microwave", "coffee", "coffee maker", "not heating", "vacuum", "washing machine", "mains", "120v", "240v"},
            "relevance": 0.82,
            "coverage": 0.32,
            "why": [
                "some control-board visual triage is possible",
                "salvage and connector mapping can help after safe isolation",
                "heater/thermal fuse/thermostat continuity lane exists for simple heater appliances",
            ],
            "gaps": [
                "mains and high-voltage safety procedures",
                "mechanical, plumbing, heater, compressor, and motor-load diagnostics",
                "certification and liability boundaries",
            ],
        },
        "pure_mechanical_restoration": {
            "label": "Mostly mechanical restoration",
            "examples": ["tools", "lighters", "locks", "bicycles", "rusty mechanisms"],
            "signals": {"rust", "mechanical", "lock", "tool", "bicycle", "lighter"},
            "relevance": 0.55,
            "coverage": 0.18,
            "why": [
                "documentation and cleaning checklists are reusable",
                "not a strong fit for PCB/electronics intelligence",
            ],
            "gaps": [
                "mechanical geometry and part-fit reasoning",
                "materials chemistry and surface finishing database",
                "no electronics-specific value unless the item has control boards or motors",
            ],
        },
    }

    def evaluate_text(self, text: str) -> Dict[str, Any]:
        normalized = str(text or "").lower()
        matches = []
        for item_id, item in self.ITEM_CLASSES.items():
            hits = sorted(signal for signal in item["signals"] if signal in normalized)
            if hits:
                matches.append(self._record(item_id, item, hits))
        if not matches:
            matches = [self._record(item_id, item, []) for item_id, item in self.ITEM_CLASSES.items()]
            matches.sort(key=lambda record: record["strategic_score"], reverse=True)
            return {
                "mode": "repair_market_coverage",
                "query": text,
                "matched": False,
                "top_matches": matches[:5],
                "recommendation": "No direct item match; collect device type, symptoms, photos, and whether it contains electronics.",
            }
        matches.sort(key=lambda record: record["strategic_score"], reverse=True)
        return {
            "mode": "repair_market_coverage",
            "query": text,
            "matched": True,
            "top_matches": matches[:5],
            "recommendation": self._recommendation(matches[0]),
        }

    def portfolio(self) -> Dict[str, Any]:
        records = [self._record(item_id, item, []) for item_id, item in self.ITEM_CLASSES.items()]
        records.sort(key=lambda record: record["strategic_score"], reverse=True)
        strong = [record for record in records if record["coverage"] >= 0.65]
        partial = [record for record in records if 0.35 <= record["coverage"] < 0.65]
        weak = [record for record in records if record["coverage"] < 0.35]
        return {
            "mode": "repair_market_coverage_portfolio",
            "summary": {
                "strong_count": len(strong),
                "partial_count": len(partial),
                "weak_count": len(weak),
                "weighted_coverage": round(
                    sum(record["coverage"] * record["relevance"] for record in records)
                    / max(sum(record["relevance"] for record in records), 1.0),
                    3,
                ),
            },
            "strong_fit": strong,
            "partial_fit": partial,
            "weak_fit": weak,
            "recommended_next_builds": [
                "retro handheld console revision/parts catalog",
                "controller platform calibration and parts compatibility catalog",
                "battery/charger sealed-device safety and compatibility packs",
                "TV/monitor backlight model-specific rail and LED-strip references",
                "modern console triage lane with HDMI/USB-C caution and boardview hooks",
                "audio/retro signal-path diagnostic lane",
                "phone/laptop model-specific teardown and battery safety packs only after narrower gadget lanes are strong",
            ],
        }

    def _record(self, item_id: str, item: Dict[str, Any], hits: List[str]) -> Dict[str, Any]:
        coverage = float(item["coverage"])
        relevance = float(item["relevance"])
        return {
            "item_id": item_id,
            "label": item["label"],
            "examples": item["examples"],
            "coverage": coverage,
            "relevance": relevance,
            "strategic_score": round(coverage * relevance, 3),
            "coverage_level": self._coverage_level(coverage),
            "signal_hits": hits,
            "why": item["why"],
            "gaps": item["gaps"],
        }

    def _coverage_level(self, coverage: float) -> str:
        if coverage >= 0.75:
            return "strong"
        if coverage >= 0.55:
            return "usable_with_gaps"
        if coverage >= 0.35:
            return "partial"
        return "weak"

    def _recommendation(self, record: Dict[str, Any]) -> str:
        if record["coverage"] >= 0.75:
            return "Good target now: build user-facing workflows and examples for this item class."
        if record["coverage"] >= 0.55:
            return "Usable target with a narrow workflow; add the listed gaps before marketing it broadly."
        if record["coverage"] >= 0.35:
            return "Research/prototype only; needs model-specific knowledge before customer-facing use."
        return "Do not sell this as covered yet; collect examples and build a dedicated lane first."
