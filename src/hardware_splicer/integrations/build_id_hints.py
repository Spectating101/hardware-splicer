"""Catalog build descriptions plus explicitly legacy keyword compatibility hints.

The catalog descriptions are safe model context: they describe bounded build recipes.
``keyword_build_id`` is different. It interprets free-form prose with a hand-written
ontology and therefore must never outrank a valid model proposal or masquerade as
canonical engineering truth. It remains only for explicit offline/legacy compatibility
while callers migrate to typed semantic architecture proposals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from ..catalog import CATALOG_BUILD_IDS

GENERIC_BUILD_ID = "generic_low_voltage_build"

# One-line descriptions for model/catalog browsing. These are descriptions, not routing
# rules; callers must not turn them into keyword trigger tables.
BUILD_ID_GUIDE: dict[str, str] = {
    "automatic_plant_watering": "Soil moisture / plant watering / drip pump / irrigation",
    "automatic_plant_watering_usb": "USB-powered plant watering variant",
    "robot_drive_base": "Rover, wheels, mobile robot, differential drive, Enabot-like rolling camera",
    "plotter_motion_stage": "Plotter, inkjet printer salvage, stepper motion, CNC axis, scanner rail",
    "usb_fume_extractor": "Desk fan, solder fumes, airflow, cooling fan, ventilation, temp-controlled fan",
    "room_display_station": "Room monitor, TFT/OLED display station, environmental panel",
    "smart_relay_box": "Relay switching lamp, outlet, desk lamp, smart switch",
    "sensor_logger": "BME280/DHT data logger, environmental logging, WiFi sensor node",
    "inspection_motion_fixture": "Pan-tilt, camera mount, gimbal, inspection head",
    "low_voltage_motor_test_jig": "Motor test, gripper, claw, bench motor jig",
    "generic_low_voltage_build": "General low-voltage build when no bounded recipe is a defensible fit",
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
    """Return a *legacy heuristic* build hint from prose.

    This function is intentionally retained for explicit offline/demo compatibility.
    Its result has no authority and must not override a valid model proposal. New
    product paths should use typed semantic architecture selection instead.
    """
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
    if any(
        word in text
        for word in [
            "enabot",
            "telepresence",
            "rolling camera",
            "home camera robot",
            "wifi camera robot",
            "wi-fi camera robot",
            "pet camera robot",
        ]
    ):
        return "robot_drive_base"
    if any(word in text for word in ["rover", "wheel", "wheeled", "robot car", "drive motor", "rc toy"]):
        return "robot_drive_base"
    if any(word in text for word in ["fan", "airflow", "vent", "blower", "fume", "aerator", "chiller fan"]):
        return "usb_fume_extractor"
    if any(
        word in text
        for word in [
            "tft",
            "oled",
            "display station",
            "room display",
            "room temp",
            "ili9341",
            "status board",
            "ticker",
            "calendar desk",
            "weather station",
        ]
    ):
        return "room_display_station"
    if any(
        word in text
        for word in [
            "relay box",
            "smart relay",
            "relay module",
            "desk lamp",
            "solenoid",
            "valve",
            "heater relay",
            "heater guard",
            "frost",
            "dehumidifier",
            "humidifier",
            "mister",
            "mist",
            "sprinkler",
            "garage door",
            "dry-contact",
            "auto-start",
            "preheat",
            "slow cooker",
            "incubator",
            "fermentation",
            "sous-vide",
            "sous vide",
            "uv cure",
        ]
    ):
        return "smart_relay_box"
    if any(
        word in text
        for word in [
            "sensor logger",
            "bme280",
            "log temperature",
            "environment sensor",
            "data logger",
            "leak",
            "alarm",
            "notifier",
            "door alarm",
            "fridge door",
            "fridge case",
            "freezer",
            "mailbox",
            "beam-break",
            "break-beam",
            "tof alert",
            "grain bin",
            "hive weight",
            "lightning",
            "power outage",
            "pulse-ox",
            "pulse ox",
            "seismometer",
            "physiology logger",
            "aqi",
            "air quality",
            "co2",
            "compost",
            "posture",
            "handwash",
            "temp cable",
            "temperature alarm",
            "temperature logger",
            "temp logger",
        ]
    ):
        return "sensor_logger"
    if any(
        word in text
        for word in [
            "amp box",
            "amplifier",
            "i2s amp",
            "pam8403",
            "dfplayer",
            "practice amp",
            "intercom",
            "doorbell",
            "audio monitor",
            "soundboard",
        ]
    ):
        return "small_audio_amp_box"
    if any(word in text for word in ["macro pad", "keypad", "call button", "panic button", "stream-deck", "stream deck"]):
        return "salvaged_input_panel"
    if any(word in text for word in ["task light", "led strip", "grow light", "night light", "softbox", "illuminator", "led bar", "led panel"]):
        return "indicator_or_task_light"
    if any(word in text for word in ["pan", "tilt", "camera mount", "gimbal", "turntable", "trash lid", "blind tilt"]):
        return "inspection_motion_fixture"
    if any(word in text for word in ["gripper", "claw", "grab", "curtain", "coop door", "motor test", "jog"]):
        return "low_voltage_motor_test_jig"
    if any(word in text for word in ["bench power", "adjustable buck", "pd trigger"]):
        return "bench_power_adapter"
    if any(word in text for word in ["uart debug", "usb serial", "ch340"]):
        return "usb_uart_debug_adapter"
    if any(word in text for word in ["pager", "status led", "led ack", "network status"]):
        return "network_status_indicator"
    if salvage_id == "sensor_logger" and any("pump" in str(part.get("type") or "").lower() for part in (parts or [])):
        return "automatic_plant_watering"
    return None


def build_catalog_context_for_pick() -> str:
    lines = []
    for build_id in CATALOG_BUILD_IDS:
        guide = BUILD_ID_GUIDE.get(build_id, "")
        lines.append(f"- {build_id}: {guide}" if guide else f"- {build_id}")
    return "\n".join(lines)


def _legacy_fallback_allowed_by_policy() -> bool:
    """Legacy architecture heuristics are available only in explicit offline salvage."""
    try:
        from .llm_policy import offline_salvage_enabled
    except ImportError:
        from hardware_splicer.integrations.llm_policy import offline_salvage_enabled

    return bool(offline_salvage_enabled())


def reconcile_build_pick_with_provenance(
    llm_build_id: str | None,
    keyword_build_id: str | None,
    *,
    diy_build_id: str = "",
    splice_build_id: str = "",
    llm_confidence: float = 0.0,
    allow_legacy_fallback: bool | None = None,
) -> Dict[str, Any]:
    """Resolve a build proposal without allowing heuristics to overrule the model.

    A valid model-selected catalog ID always wins. Keyword/DIY/splice values are legacy
    compatibility signals only. If ``allow_legacy_fallback`` is omitted, availability
    follows the explicit offline-salvage policy instead of silently defaulting to true.
    """
    llm = str(llm_build_id or "").strip()
    keyword = str(keyword_build_id or "").strip()
    diy = str(diy_build_id or "").strip()
    splice = str(splice_build_id or "").strip()

    if llm and llm in CATALOG_BUILD_IDS:
        return {
            "build_id": llm,
            "source": "model_proposed",
            "confidence": max(0.0, min(1.0, float(llm_confidence or 0.0))),
            "authority_effect": "none",
            "legacy_fallback_used": False,
        }

    legacy_allowed = (
        _legacy_fallback_allowed_by_policy()
        if allow_legacy_fallback is None
        else bool(allow_legacy_fallback)
    )
    if not legacy_allowed:
        return {
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "authority_effect": "none",
            "legacy_fallback_used": False,
        }

    for source, candidate in (
        ("legacy_keyword", keyword),
        ("legacy_diy_planner", diy),
        ("legacy_splice_planner", splice),
    ):
        if candidate and candidate in CATALOG_BUILD_IDS:
            return {
                "build_id": candidate,
                "source": source,
                "confidence": 0.0,
                "authority_effect": "none",
                "legacy_fallback_used": True,
            }

    return {
        "build_id": None,
        "source": "unresolved",
        "confidence": 0.0,
        "authority_effect": "none",
        "legacy_fallback_used": False,
    }


def reconcile_build_pick(
    llm_build_id: str | None,
    keyword_build_id: str | None,
    *,
    diy_build_id: str = "",
    splice_build_id: str = "",
    llm_confidence: float = 0.0,
    allow_legacy_fallback: bool | None = None,
) -> Optional[str]:
    """Compatibility wrapper returning only the selected ID.

    Unlike the historical implementation, a keyword result can never override a valid
    model proposal, and an omitted fallback flag follows the explicit offline policy.
    """
    decision = reconcile_build_pick_with_provenance(
        llm_build_id,
        keyword_build_id,
        diy_build_id=diy_build_id,
        splice_build_id=splice_build_id,
        llm_confidence=llm_confidence,
        allow_legacy_fallback=allow_legacy_fallback,
    )
    return decision["build_id"]
