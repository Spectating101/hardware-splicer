"""Concrete module selection with an explicitly isolated legacy regex picker.

``MODULE_HINTS`` remains for offline/regression compatibility, but model-enabled product
paths must not compute or prefer the regex answer before semantic model selection. The
model-backed selector operates through typed capability intent and deterministic
candidate validation; failure stays unresolved rather than falling through to regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from .pcb.module_registry import find_module, find_modules_by_capabilities
from .phrase_expander import expand_user_phrase


@dataclass
class ModulePick:
    module_ids: list[str]
    labels: list[str]
    hints: list[str]
    quantities: dict[str, int] = field(default_factory=dict)  # "four SG90 servos" -> {"sg90": 4}


@dataclass
class ModuleHint:
    patterns: list[re.Pattern[str]]
    label: str
    requires_any: list[list[str]]
    prefer_id: Optional[str] = None
    priority: int = 0


# Legacy/offline semantic compatibility table. This table must never run ahead of a
# configured model selector on normal product paths.
MODULE_HINTS: list[ModuleHint] = [
    ModuleHint(
        patterns=[re.compile(r"robot(?:ic)? arm|gripper|pan.?tilt", re.I)],
        label="servo arm",
        requires_any=[["mechanical_motion"]],
        prefer_id="sg90",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"led strip|strip of \d+|addressable|ws281\d|sk6812|neopixel strip", re.I)],
        label="addressable LED strip",
        requires_any=[["led_or_light"]],
        prefer_id="ws2812b_strip",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"\blora\b|lorawan|sx12[67]\d", re.I)],
        label="LoRa radio",
        requires_any=[["wireless"]],
        prefer_id="lora_sx1278",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"18650|\blipo\b|li-?ion|battery|rechargeable cell", re.I)],
        label="battery charging",
        requires_any=[["battery"]],
        prefer_id="tp4056",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"real.?time clock|\brtc\b|ds3231|ds1307", re.I)],
        label="real-time clock",
        requires_any=[["connector"]],
        prefer_id="ds3231_rtc",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"ds18b20|one.?wire temp|digital temp probe", re.I)],
        label="1-wire temperature",
        requires_any=[["sensor_or_adc"]],
        prefer_id="ds18b20",
        priority=10,
    ),
    ModuleHint(
        patterns=[re.compile(r"pressure|barometric|altitude|bme280|bmp280|environmental sensor", re.I)],
        label="pressure/environment sensing",
        requires_any=[["sensor_or_adc"]],
        prefer_id="bme280",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"temp|humidity|thermostat|climate|hot|cold|weather", re.I)],
        label="temperature/humidity sensing",
        requires_any=[["sensor_or_adc"]],
        prefer_id="dht22",
        priority=5,
    ),
    ModuleHint(
        patterns=[re.compile(r"soil|moist|wet plant|dry plant|garden", re.I)],
        label="soil moisture",
        requires_any=[["sensor_or_adc"]],
        prefer_id="soil_moisture",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"distance|ultrasonic|how far|proximity|object near", re.I)],
        label="distance sensing",
        requires_any=[["sensor_or_adc"]],
        prefer_id="hc-sr04",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"light level|brightness|dark|ldr|photoresistor", re.I)],
        label="light sensing",
        requires_any=[["sensor_or_adc"]],
        prefer_id="ldr_photoresistor",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"co2|air quality|voc|gas sensor|smoke detect", re.I)],
        label="air quality",
        requires_any=[["sensor_or_adc"]],
        prefer_id="mq-2_gas_sensor",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"solenoid|valve|garage door|dry contact", re.I)],
        label="solenoid/valve control",
        requires_any=[["actuator_driver"]],
        prefer_id="relay-1ch-5v",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"relay|switch (?:a |the )?(?:lamp|light|outlet|heater)|turn (?:on|off)", re.I)],
        label="relay switching",
        requires_any=[["actuator_driver"]],
        prefer_id="relay-1ch-5v",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"mosfet|high.?current switch|pump driver", re.I)],
        label="load driver",
        requires_any=[["actuator_driver"]],
        prefer_id="mosfet-irlz44n",
        priority=6,
    ),
    ModuleHint(
        patterns=[re.compile(r"servo|rc servo", re.I)],
        label="servo motion",
        requires_any=[["motor_or_load", "mechanical_motion"]],
        prefer_id="sg90",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"stepper|cnc|plotter|pen plot", re.I)],
        label="stepper motion",
        requires_any=[["mechanical_motion", "actuator_driver"]],
        prefer_id="a4988-stepper",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"\brobot\b(?!\s+arm)|rover|drives around|rc car|mobile base|wheel bot", re.I)],  # a robot arm has no wheels
        label="robot drive",
        requires_any=[["motor_or_load", "actuator_driver"]],
        prefer_id="l298n",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"dc motor|wheel|spin(?:ning)?|tank tread", re.I)],
        label="motor drive",
        requires_any=[["motor_or_load", "actuator_driver"]],
        prefer_id="l298n",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"usb[- ]powered sensor|sensor node", re.I)],
        label="sensor node",
        requires_any=[["sensor_or_adc"], ["wireless"]],
        prefer_id="dht22",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"beginner project|starter project|esp32 and sensor|first project", re.I)],
        label="starter sensor",
        requires_any=[["sensor_or_adc"]],
        prefer_id="dht22",
        priority=6,
    ),
    ModuleHint(
        patterns=[re.compile(r"pump|water flow|move water|watering|irrigation|auto water", re.I)],
        label="pump",
        requires_any=[["fan_or_pump", "motor_or_load"]],
        prefer_id="water_pump_5v",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"fan|blow air|cool(?:ing)?", re.I)],
        label="fan",
        requires_any=[["fan_or_pump", "motor_or_load"]],
        prefer_id="cooling_fan_5v",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"display|screen|oled|show (?:text|numbers)|show sensor|readings on (?:a )?screen", re.I)],
        label="display",
        requires_any=[["display_or_ui"]],
        prefer_id="ssd1306-128x64",
        priority=6,
    ),
    ModuleHint(
        patterns=[re.compile(r"room monitor|weather station|environment(?:al)? (?:station|panel)|multi.?sensor", re.I)],
        label="room monitor",
        requires_any=[["sensor_or_adc"], ["display_or_ui"]],
        prefer_id="bme280",
        priority=9,
    ),
    ModuleHint(
        patterns=[re.compile(r"camera|take photos?|video|webcam|watch", re.I)],
        label="camera",
        requires_any=[["camera_or_vision"]],
        prefer_id="esp32-cam-module",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"speaker|audio|beep|sound|play a tone", re.I)],
        label="audio output",
        requires_any=[["speaker_or_audio"]],
        prefer_id="max98357a-i2s-amp",
        priority=7,
    ),
    ModuleHint(
        patterns=[re.compile(r"button|keypad|\bpress(?:able)?\b|macro pad", re.I)],
        label="buttons",
        requires_any=[["switch_or_button"]],
        prefer_id="capacitive_touch",
        priority=5,
    ),
    ModuleHint(
        patterns=[re.compile(r"\bleds?\b|indicator light|status light|blink", re.I)],  # whole word: not the "led" in "oled"
        label="indicator LED",
        # Only a light: asking for "any display" here put an OLED into every brief that mentioned an LED.
        requires_any=[["led_or_light"]],
        priority=5,
    ),
    ModuleHint(
        patterns=[re.compile(r"wifi|wireless|internet|bluetooth|esp-?now|home assistant|esphome", re.I)],
        label="wireless",
        requires_any=[["wireless"]],
        prefer_id="esp32-devkit",
        priority=4,
    ),
    ModuleHint(
        patterns=[re.compile(r"tft|touchscreen|ili9341|lvgl|cheap yellow display|cyd", re.I)],
        label="touch display",
        requires_any=[["display_or_ui"]],
        prefer_id="ili9341_tft",
        priority=8,
    ),
    ModuleHint(
        patterns=[re.compile(r"12v|barrel|wall wart|bench supply", re.I)],
        label="higher-voltage input",
        requires_any=[["power"]],
        prefer_id="dc-barrel-12v",
        priority=6,
    ),
    ModuleHint(
        patterns=[re.compile(r"buck|step down|regulate(?:d)? power", re.I)],
        label="buck regulator",
        requires_any=[["power"]],
        prefer_id="buck-lm2596",
        priority=6,
    ),
]

SENSOR_PREFER_IDS = {
    "dht22", "ds18b20", "bme280", "soil_moisture", "hc-sr04", "ldr_photoresistor",
    "mq-2_gas_sensor",
}


def _normalize_user_text(text: str) -> str:
    return (
        text.lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def _hint_match_score(hint: ModuleHint, text: str) -> int:
    best = 0
    for pattern in hint.patterns:
        match = pattern.search(text)
        if match:
            best = max(best, len(match.group(0)) + (hint.priority or 0))
    return best


def _pick_from_capabilities(
    group: list[str],
    exclude: set[str],
    prefer_id: Optional[str] = None,
) -> Optional[dict]:
    if prefer_id and prefer_id not in exclude:
        pref = find_module(prefer_id)
        if pref:
            return pref
    candidates = [
        m for m in find_modules_by_capabilities([group])
        if m.get("id") not in exclude
    ]
    candidates.sort(key=lambda m: len(m.get("capabilityTags") or []))
    return candidates[0] if candidates else None


def _filter_redundant_hints(
    ranked: list[tuple[ModuleHint, int]],
    text: str,
) -> list[ModuleHint]:
    picked = [entry[0] for entry in ranked]

    def has(prefer_id: str) -> bool:
        return any(h.prefer_id == prefer_id for h in picked)

    out: list[ModuleHint] = []
    for hint in picked:
        if hint.prefer_id == "dht22" and has("ds18b20"):
            continue
        if hint.prefer_id == "dht22" and has("bme280") and re.search(
            r"pressure|barometric|environmental|bme|bmp", text, re.I
        ):
            continue
        if hint.prefer_id == "ssd1306-128x64" and has("ili9341_tft"):
            continue
        if hint.label == "wireless" and len(picked) > 1:
            continue
        out.append(hint)
    return out


def pick_modules_for_goal(text: str) -> ModulePick:
    """Select modules through model-first semantics or explicit offline compatibility.

    When a model-backed selector is enabled, the legacy regex picker is never evaluated
    first and is never used as a silent fallback. The model selector already performs a
    typed capability interpretation followed by deterministic candidate validation. If
    that selection cannot resolve, this function returns an empty, explicitly unresolved
    pick. Regex selection is reserved for ``offline_compose_enabled()`` or environments
    where the model selector is unavailable by policy.
    """
    from .integrations.llm_policy import offline_compose_enabled
    from .integrations.qwen_module_pick import call_qwen_module_pick, qwen_module_pick_enabled

    goal = text.strip()
    if qwen_module_pick_enabled() and not offline_compose_enabled():
        picked = call_qwen_module_pick(goal)
        if picked.get("ok"):
            return ModulePick(
                module_ids=list(picked.get("module_ids") or []),
                labels=[],
                hints=[str(picked.get("reasoning") or "semantic_model_selection")],
            )
        reason = str(
            picked.get("message")
            or picked.get("reason")
            or picked.get("error")
            or "semantic_model_selection_unresolved"
        )
        return ModulePick(module_ids=[], labels=[], hints=[f"unresolved:{reason}"])

    return _pick_modules_regex(goal)


def _pick_modules_regex(text: str) -> ModulePick:
    """Legacy/offline phrase-to-module compatibility path."""
    t = _normalize_user_text(expand_user_phrase(text))
    ranked = [
        (hint, _hint_match_score(hint, t))
        for hint in MODULE_HINTS
        if _hint_match_score(hint, t) > 0
    ]
    ranked.sort(key=lambda row: row[1], reverse=True)

    matched_hints = _filter_redundant_hints(ranked, t)
    if not matched_hints:
        return ModulePick(module_ids=[], labels=[], hints=[])

    module_ids: set[str] = set()
    labels: list[str] = []
    hints = [h.label for h in matched_hints]

    solo_part = bool(re.search(r"(?:^|\b)(?:just|only)\s+(?:a|an)\s+", t)) and len(matched_hints) == 1
    needs_brain = not solo_part and not re.search(r"no (?:mcu|microcontroller|brain|controller)", t)
    needs_barrel_rail = bool(
        re.search(r"12v|barrel|bench supply|buck|stepper|cnc|plotter", t)
        or any(
            h.prefer_id in ("dc-barrel-12v", "buck-lm2596", "a4988-stepper")
            for h in matched_hints
        )
    )
    needs_usb_power = (
        needs_brain
        and not re.search(r"battery|lipo|li.?ion|18650", t)
        and not needs_barrel_rail
    )

    if needs_barrel_rail:
        module_ids.add("dc-barrel-12v")
        barrel = find_module("dc-barrel-12v")
        labels.append(barrel.get("label") if barrel else "12V barrel input")

    if needs_usb_power:
        module_ids.add("usb-power-5v")
        usb = find_module("usb-power-5v")
        labels.append(usb.get("label") if usb else "USB 5V power")
    if needs_brain:
        module_ids.add("esp32-devkit")
        mcu = find_module("esp32-devkit")
        labels.append(mcu.get("label") if mcu else "ESP32 DevKit")

    sensor_picks: set[str] = set()
    infrastructure = {"esp32-devkit", "usb-power-5v", "dc-barrel-12v", "buck-lm2596"}

    def already_covered(group: list[str]) -> bool:
        # One display satisfies every hint that needs a display; a second is added only when a hint names it (prefer_id).
        return any(set(group) & set((find_module(m) or {}).get("capabilityTags") or []) for m in module_ids - infrastructure)

    # First the parts the matched hints name, so a generic group below does not fill a slot with something else first.
    for hint in matched_hints:
        preferred = find_module(hint.prefer_id) if hint.prefer_id else None
        tags = set((preferred or {}).get("capabilityTags") or [])
        if preferred and hint.prefer_id not in module_ids and any(set(group) & tags for group in hint.requires_any):
            if hint.prefer_id in SENSOR_PREFER_IDS:
                sensor_picks.add(hint.prefer_id)
            module_ids.add(hint.prefer_id)
            labels.append(str(preferred.get("label") or hint.prefer_id))
    for hint in matched_hints:
        for group in hint.requires_any:
            if already_covered(group):
                continue
            pick = _pick_from_capabilities(group, module_ids, hint.prefer_id)
            if not pick:
                continue
            pick_id = str(pick.get("id"))
            if pick_id in SENSOR_PREFER_IDS and pick_id in sensor_picks:
                continue
            if pick_id in SENSOR_PREFER_IDS:
                sensor_picks.add(pick_id)
            module_ids.add(pick_id)
            labels.append(str(pick.get("label") or pick_id))

    if needs_brain and re.search(r"pump|motor|relay|servo|stepper|fan|watering|irrigation", t):
        if re.search(r"pump|fan|watering|irrigation|auto water|drip irrig", t) and "mosfet-irlz44n" not in module_ids:
            module_ids.add("mosfet-irlz44n")
            mod = find_module("mosfet-irlz44n")
            labels.append(mod.get("label") if mod else "MOSFET driver")
        if re.search(r"watering|irrigation|auto water|drip irrig|water my", t) and "water_pump_5v" not in module_ids:
            module_ids.add("water_pump_5v")
            mod = find_module("water_pump_5v")
            labels.append(mod.get("label") if mod else "5V water pump")
        if re.search(r"stepper|cnc|plotter|12v|barrel|buck", t) and "buck-lm2596" not in module_ids:
            module_ids.add("buck-lm2596")
            mod = find_module("buck-lm2596")
            labels.append(mod.get("label") if mod else "Buck regulator")

    if needs_barrel_rail:
        module_ids.discard("usb-power-5v")
        if needs_brain and "buck-lm2596" not in module_ids:
            module_ids.add("buck-lm2596")
            mod = find_module("buck-lm2596")
            labels.append(mod.get("label") if mod else "Buck regulator")

    five_v_signal_ids = {"hc-sr04"}
    needs_level_shift = needs_brain and any(mid in five_v_signal_ids for mid in module_ids)
    if needs_level_shift and "level-shifter-4ch" not in module_ids:
        module_ids.add("level-shifter-4ch")
        mod = find_module("level-shifter-4ch")
        labels.append(mod.get("label") if mod else "Level shifter")

    # A part the brief names by its number (SG90, WS2812B, SX1278) is that part, whatever the hints chose.
    quantities: dict[str, int] = {}
    for module_id, count in _explicit_parts(text).items():
        if module_id not in module_ids:
            module_ids.add(module_id)
            mod = find_module(module_id)
            labels.append(str((mod or {}).get("label") or module_id))
        if count > 1:
            quantities[module_id] = count

    return ModulePick(
        module_ids=list(module_ids),
        labels=list(dict.fromkeys(labels)),
        hints=hints,
        quantities=quantities,
    )


_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}
_NOT_NAMED = {"esp32-devkit", "esp32-devkitc-v4", "usb-power-5v", "dc-barrel-12v"}  # the controller and power are chosen separately


@lru_cache(maxsize=1)
def _part_number_index() -> dict[str, str]:
    """Normalized part number -> module id, from each engine part's partNumber, id and leading label word."""
    import json
    from pathlib import Path

    library = json.loads((Path(__file__).resolve().parent / "data" / "engine_pcb_data.json").read_text(encoding="utf-8"))["module_library"]
    index: dict[str, str] = {}
    for module in sorted(library, key=lambda m: m["id"]):
        if module["id"] in _NOT_NAMED or not find_module(module["id"]):
            continue
        for raw in (module.get("partNumber"), module["id"].split("_")[0], str(module.get("label", "")).split(" ")[0]):
            key = re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())
            # Part-number-like only (letters and digits, 4+ chars): never a plain word such as "servo" or "relay".
            if len(key) >= 4 and re.search(r"\d", key) and re.search(r"[A-Z]", key) and not key.startswith("ESP32"):
                index.setdefault(key, module["id"])
    return index


def _explicit_parts(text: str) -> dict[str, int]:
    """Parts named by number in the brief, with a count when one precedes them ("four SG90", "60 WS2812B")."""
    found: dict[str, int] = {}
    index = _part_number_index()
    pattern = r"(?:(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+(?:x\s+)?)?\b([A-Za-z]+[-_]?[A-Za-z]*\d[\w-]*)"  # no space inside a part number
    for match in re.finditer(pattern, text, re.I):
        module_id = index.get(re.sub(r"[^A-Z0-9]", "", match.group(2).upper()))
        if not module_id:
            continue
        count = match.group(1)
        n = int(count) if count and count.isdigit() else _NUMBER_WORDS.get((count or "").lower(), 1)
        found[module_id] = max(found.get(module_id, 1), n)
    return found


def wants_module_composition(text: str) -> bool:
    t = _normalize_user_text(text)
    if not pick_modules_for_goal(text).module_ids:
        return False
    if re.search(
        r"(?:^|\b)(?:add|include|need|want|with (?:a|an)|on (?:a |the )?(?:small )?screen|something that|that (?:measures|reads|senses|controls|drives|spins|monitors)|uses? (?:a|an))",
        t,
    ):
        return True
    if re.search(r"(?:build|make|create|set up|help me)", t):
        return True
    return False
