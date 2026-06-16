from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.firmware_scaffold import generate_firmware_from_salvage
from hardware_splicer.salvage_bom_estimate import (
    build_salvage_bom_estimate,
    enrich_salvage_bom_estimate,
    write_salvage_bom_artifacts,
)
from hardware_splicer.salvage_revision import apply_salvage_edits, diff_salvage_packages
from hardware_splicer.vision_inventory import extract_parts_from_attachments, merge_attachment_inventory_into_intake


def test_salvage_bom_estimate_has_prices(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    lines = build_salvage_bom_estimate(
        resolved_modules=[
            {"module_id": "esp32-devkit", "part_name": "ESP32 dev board", "source": "heuristic"},
            {"module_id": "soil_moisture", "part_name": "soil sensor"},
        ],
        gap_analysis={"shopping_list": [{"module_id": "level-shifter-4ch", "priority": "recommended"}]},
        budget={"currency": "USD", "amount": 25},
    )
    assert lines["line_count"] >= 2
    assert lines["estimated_total_usd"] is not None
    assert any(row.get("mpn") for row in lines["lines"])
    esp = next(row for row in lines["lines"] if row["module_id"] == "esp32-devkit")
    assert esp.get("unit_price_usd") == 8.0
    assert esp.get("price_note") == "prototype_fallback"


def test_salvage_bom_jlc_enrich_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")
    from unittest.mock import MagicMock

    bom = build_salvage_bom_estimate(
        resolved_modules=[{"module_id": "resistor-10k"}],
        gap_analysis={},
    )
    mock = MagicMock()
    mock.search_resistors.return_value = [{"lcsc": 21190, "mfr": "0603WAF1001T5E", "price1": 0.001}]
    enriched = enrich_salvage_bom_estimate(bom, client=mock)
    line = enriched["lines"][0]
    assert line.get("jlc_lcsc") == "21190"
    paths = write_salvage_bom_artifacts(enriched, tmp_path)
    assert Path(paths["salvage_bom_csv"]).is_file()


def test_firmware_from_bringup_card():
    bringup = {
        "gpio_assignments": [
            {
                "from": "ESP32 DevKit (GPIO4)",
                "to": "IRLZ44N (SIG)",
                "from_pin": "GPIO4",
                "purpose": "control signal",
            }
        ],
        "connections": [],
    }
    fw = generate_firmware_from_salvage(
        build_id="automatic_plant_watering",
        bringup_card=bringup,
        module_ids=["esp32-devkit", "soil_moisture", "mosfet-irlz44n", "mini-pump-5v"],
        goal="water plants when soil is dry",
    )
    assert fw.get("generator") in {"bringup_card", "catalog_sketch+bringup_pins"}
    assert fw["pins"].get("pump") == 4
    assert "PUMP_PIN" in fw["source"] or "ACTUATOR" in fw["source"]


def test_offline_attachment_inventory():
    body, report = merge_attachment_inventory_into_intake(
        {
            "goal": "plant watering",
            "available_parts": [],
            "attachments": [
                {"path": "/tmp/esp32_dev_board_photo.jpg", "label": "ESP32 on breadboard"},
            ],
        }
    )
    assert report.get("merged_count", 0) >= 1
    assert len(body.get("available_parts") or []) >= 1


def test_salvage_revision_add_part(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "0")
    intake = json.loads(Path("examples/intakes/plant_watering_brief.json").read_text(encoding="utf-8"))
    before_goal = intake["goal"]
    rev = apply_salvage_edits(
        goal=before_goal,
        parts=intake["available_parts"],
        constraints=intake.get("constraints") or {},
        edits=[{"op": "add_part", "part": {"name": "BME280 sensor", "type": "sensor"}}],
    )
    assert rev.get("package")
    assert len(rev.get("parts_after") or []) > len(intake["available_parts"])


def test_extract_parts_from_attachment_filename():
    parts = extract_parts_from_attachments(
        {"attachments": [{"path": "/bench/soil_moisture_sensor.jpg"}]}
    )
    names = " ".join(p["name"].lower() for p in parts)
    assert "soil" in names or "moisture" in names
