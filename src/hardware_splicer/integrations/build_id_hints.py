"""Deterministic catalog build_id hints from goal + parts (shared by salvage and Qwen build pick)."""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from ..catalog import CATALOG_BUILD_IDS

GENERIC_BUILD_ID = "generic_low_voltage_build"

# One-line routing guide for LLM build-pick prompts.
BUILD_ID_GUIDE: dict[str, str] = {
    "automatic_plant_watering": "Soil moisture / plant watering / drip pump / irrigation",
    "automatic_plant_watering_usb": "USB-powered plant watering variant",
    "robot_drive_base": "Rover, wheels, mobile robot, differential drive",
    "plotter_motion_stage": "Plotter, inkjet printer salvage, stepper motion, CNC axis, scanner rail",
    "usb_fume_extractor": "Desk fan, solder fumes, airflow, cooling fan, ventilation, temp-controlled fan",
    "room_display_station": "Room monitor, TFT/OLED display station, environmental panel",
    "smart_relay_box": "Relay switching lamp, outlet, desk lamp, smart switch",
    "sensor_logger": "BME280/DHT data logger, environmental logging, WiFi sensor node",
    "inspection_motion_fixture": "Pan-tilt, camera mount, gimbal, inspection head",
    "low_voltage_motor_test_jig": "Motor test, gripper, claw, bench motor jig",
    "generic_low_voltage_build": "Vague beginner MCU project only when nothing else fits",
}


def intake_goal_parts_text(goal: str, parts: List[Mapping[str, Any]] | None = None) -> str:
    chunks = [str(goal or "")]
    for part in parts or []:
        chunks.append(str(part.get("name") or ""))
        chunks.append(str(part.get("type") or ""))
    return " ".join(chunks).lower()


def keyword_build_id(
    goal: str,
    parts: List[Mapping[str, Any]] | None = None,
    *,
    salvage_id: str = "",
) -> Optional[str]:
    """High-confidence keyword routing — regression-tested against golden intakes."""
    text = intake_goal_parts_text(goal, parts)

    if any(word in text for word in ["soil", "water", "watering", "pump", "irrigation", "plant"]):
        return "automatic_plant_watering"
    if any(
        word in text
        for word in [
            "plotter",
            "inkjet",
            "printer motion",
            "printer parts",
            "dead inkjet",
            "cnc",
            "stepper",
            "linear rail",
            "scanner motion",
            "motion stage",
            "motion test jig",
        ]
    ):
        return "plotter_motion_stage"
    if any(word in text for word in ["rover", "wheel", "wheeled", "robot car", "drive motor", "rc toy"]):
        return "robot_drive_base"
    if any(word in text for word in ["fan", "airflow", "vent", "blower", "fume"]):
        return "usb_fume_extractor"
    if any(
        word in text
        for word in ["tft", "oled", "display station", "room display", "room temp", "ili9341"]
    ):
        return "room_display_station"
    if any(word in text for word in ["relay box", "smart relay", "relay module", "desk lamp"]):
        return "smart_relay_box"
    if any(
        word in text
        for word in ["sensor logger", "bme280", "log temperature", "environment sensor", "data logger"]
    ):
        return "sensor_logger"
    if any(word in text for word in ["pan", "tilt", "camera mount", "gimbal"]):
        return "inspection_motion_fixture"
    if any(word in text for word in ["gripper", "claw", "grab"]):
        return "low_voltage_motor_test_jig"
    if salvage_id == "sensor_logger" and any("pump" in str(part.get("type") or "").lower() for part in (parts or [])):
        return "automatic_plant_watering"
    return None


def build_catalog_context_for_pick() -> str:
    lines = []
    for build_id in CATALOG_BUILD_IDS:
        guide = BUILD_ID_GUIDE.get(build_id, "")
        lines.append(f"- {build_id}: {guide}" if guide else f"- {build_id}")
    return "\n".join(lines)


def reconcile_build_pick(
    llm_build_id: str | None,
    keyword_build_id: str | None,
    *,
    diy_build_id: str = "",
    splice_build_id: str = "",
    llm_confidence: float = 0.0,
) -> Optional[str]:
    """Merge LLM pick with deterministic keyword + planner agreement."""
    generic = GENERIC_BUILD_ID
    llm = str(llm_build_id or "").strip()
    keyword = str(keyword_build_id or "").strip() or None
    diy = str(diy_build_id or "").strip()
    splice = str(splice_build_id or "").strip()

    if keyword and keyword != generic:
        planners_agree = keyword in {diy, splice} and bool(diy or splice)
        if not llm or llm == generic:
            return keyword
        if llm != keyword and (planners_agree or llm_confidence < 0.85):
            return keyword

    if llm and llm in CATALOG_BUILD_IDS:
        return llm
    if keyword:
        return keyword
    if diy:
        return diy
    if splice:
        return splice
    return None
