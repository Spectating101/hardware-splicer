"""Pick concrete library modules from natural-language goals (Python engine port)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .pcb.module_registry import find_module, find_modules_by_capabilities
from .phrase_expander import expand_user_phrase


@dataclass
class ModulePick:
    module_ids: list[str]
    labels: list[str]
    hints: list[str]


@dataclass
class ModuleHint:
    patterns: list[re.Pattern[str]]
    label: str
    requires_any: list[list[str]]
    prefer_id: Optional[str] = None
    priority: int = 0


MODULE_HINTS: list[ModuleHint] = [
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
        patterns=[re.compile(r"robot|rover|drives around|rc car|mobile base|wheel bot", re.I)],
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
        patterns=[re.compile(r"led|indicator light|status light|blink", re.I)],
        label="indicator LED",
        requires_any=[["led_or_light", "display_or_ui"]],
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
        .replace("'", "'")
        .replace("'", "'")
        .replace(""", '"')
        .replace(""", '"')
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
    """NL goal → module ids. Regex for trained phrases; Qwen for novel goals when keyed."""
    from .integrations.llm_policy import offline_compose_enabled
    from .integrations.qwen_module_pick import call_qwen_module_pick, qwen_module_pick_enabled

    goal = text.strip()
    regex_pick = _pick_modules_regex(goal)

    if not qwen_module_pick_enabled() or offline_compose_enabled():
        return regex_pick

    # MODULE_HINTS + phrase_expander are regression-tested on compose_phrases.json (56 cases).
    if len(regex_pick.module_ids) >= 2 and regex_pick.hints:
        return regex_pick

    picked = call_qwen_module_pick(goal)
    if picked.get("ok"):
        return ModulePick(
            module_ids=list(picked.get("module_ids") or []),
            labels=[],
            hints=[str(picked.get("reasoning") or "qwen_module_pick")],
        )
    return regex_pick


def _pick_modules_regex(text: str) -> ModulePick:
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
        and not re.search(r"battery|lipo|li.?ion", t)
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
    for hint in matched_hints:
        for group in hint.requires_any:
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

    return ModulePick(
        module_ids=list(module_ids),
        labels=list(dict.fromkeys(labels)),
        hints=hints,
    )


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
