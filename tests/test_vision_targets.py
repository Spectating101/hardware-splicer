from __future__ import annotations

from hardware_splicer.vision_targets import normalize_vision_evidence_notes, vision_primitive_glossary


def test_plant_watering_glossary_detected_from_goal():
    glossary = vision_primitive_glossary({"goal": "automatic plant watering device"})
    assert "pump_mount width" in glossary
    assert "controller_case inner width" in glossary


def test_normalize_retargets_pump_mount_alias():
    notes = normalize_vision_evidence_notes(
        ["measure: desk plant water ring bench photo value_mm=55 status=observed artifact=bench.jpg"],
        {"goal": "plant watering"},
    )
    assert notes[0].startswith("measure: pump_mount width")
    assert "value_mm=55" in notes[0]
