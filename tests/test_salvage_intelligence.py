from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.salvage_bridge import build_intake_salvage_package
from hardware_splicer.salvage_intelligence import analyze_salvage_gaps, build_bringup_card
from hardware_splicer.vision_inventory import extract_parts_from_vision_report, merge_vision_inventory_into_intake


def test_gap_analysis_plant_watering_covers_inventory():
    intake = json.loads(
        Path("examples/intakes/plant_watering_brief.json").read_text(encoding="utf-8")
    )
    pkg = build_intake_salvage_package(
        goal=intake["goal"],
        parts=intake["available_parts"],
        constraints=intake.get("constraints") or {},
    )
    gap = pkg.get("gap_analysis") or {}
    assert gap.get("ready_to_compile") is True
    assert len(gap.get("covered") or []) >= 3
    assert gap.get("power_topology") == "usb_5v"


def test_bringup_card_has_connections_for_plant_watering():
    intake = json.loads(
        Path("examples/intakes/plant_watering_brief.json").read_text(encoding="utf-8")
    )
    pkg = build_intake_salvage_package(
        goal=intake["goal"],
        parts=intake["available_parts"],
        constraints=intake.get("constraints") or {},
    )
    card = pkg.get("bringup_card") or {}
    assert card.get("schema_version")
    assert len(card.get("connections") or []) >= 2
    assert card.get("markdown", "").startswith("# Bench bring-up")


def test_vision_inventory_merges_identified_parts():
    intake = {"goal": "water plants", "available_parts": [{"name": "ESP32", "type": "mcu"}]}
    report = {
        "candidates": [
            {
                "identified_parts": [{"name": "capacitive soil moisture sensor", "confidence": 0.9}],
                "observations": ["5V mini pump beside breadboard"],
            }
        ]
    }
    body, inv = merge_vision_inventory_into_intake(intake, report)
    names = [row["name"] for row in body.get("available_parts") or []]
    assert "capacitive soil moisture sensor" in names
    assert inv.get("merged_count") >= 1


def test_extract_parts_heuristic_from_observations():
    report = {
        "candidates": [
            {"observations": ["ESP32 dev board next to LM2596 buck and a mini pump"]}
        ]
    }
    parts = extract_parts_from_vision_report(report)
    names = " ".join(p["name"].lower() for p in parts)
    assert "esp32" in names
    assert "pump" in names or "buck" in names
