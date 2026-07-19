#!/usr/bin/env python3
"""Generate the exhaustive Enabot-depth product corpus for engine capability sweeps.

Not capped at 200 — covers the full junk→intent addressable space:
multi-subsystem consumer/DIY cousins (MCU + power + sense/actuate ± wireless).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "examples" / "product_corpus" / "enabot_depth_corpus.json"

SCHEMA = "hardware_splicer.product_corpus.v1"

# ---------------------------------------------------------------------------
# Shared junk-bin part kits
# ---------------------------------------------------------------------------

ESP32 = {
    "name": "ESP32 DevKit",
    "type": "microcontroller",
    "module_id": "esp32-devkit",
    "condition": "new",
}
ESP32_CAM = {
    "name": "ESP32-CAM AI-Thinker",
    "type": "microcontroller",
    "module_id": "esp32-cam-module",
    "condition": "new",
}
USB5 = {"name": "USB 5V power bank", "type": "power", "module_id": "usb-power-5v", "condition": "salvaged"}
BATT74 = {"name": "2S LiPo 7.4V pack", "type": "battery", "condition": "salvaged", "voltage_v": 7.4}
BARREL12 = {"name": "12V wall wart", "type": "power", "module_id": "dc-barrel-12v", "condition": "salvaged"}
MOSFET = {"name": "IRLZ44N logic MOSFET", "type": "driver", "module_id": "mosfet-irlz44n", "condition": "new"}
L298 = {"name": "L298N dual H-bridge", "type": "driver", "module_id": "l298n", "condition": "salvaged"}
A4988 = {"name": "A4988 stepper driver", "type": "driver", "module_id": "a4988-stepper", "condition": "salvaged"}
SG90 = {"name": "SG90 servo", "type": "servo", "module_id": "sg90", "condition": "salvaged"}
DC_MOT = {"name": "6V DC gear motor", "type": "dc_motor", "module_id": "dc_motor_3v_6v", "condition": "salvaged"}
DC_MOT_R = {"name": "right 6V DC gear motor", "type": "dc_motor", "module_id": "dc_motor_3v_6v", "condition": "salvaged"}
STEPPER = {"name": "28BYJ-48 stepper", "type": "stepper", "module_id": "28byj48_stepper", "condition": "salvaged"}
PUMP = {"name": "5V mini pump", "type": "pump", "module_id": "mini-pump-5v", "condition": "new"}
FAN = {"name": "5V cooling fan", "type": "fan", "module_id": "cooling_fan_5v", "condition": "salvaged"}
RELAY = {"name": "5V relay module", "type": "relay", "module_id": "relay-1ch-5v", "condition": "new"}
SOIL = {"name": "soil moisture probe", "type": "sensor", "module_id": "soil_moisture", "condition": "new"}
DHT = {"name": "DHT22", "type": "sensor", "module_id": "dht22", "condition": "new"}
BME = {"name": "BME280", "type": "sensor", "module_id": "bme280", "condition": "new"}
TOF = {"name": "VL53L0X ToF", "type": "tof_range", "module_id": "vl53l0x_tof", "condition": "salvaged"}
US = {"name": "HC-SR04 ultrasonic", "type": "sensor", "module_id": "hc-sr04", "condition": "salvaged"}
PIR = {"name": "PIR motion", "type": "sensor", "module_id": "pir_motion_sensor", "condition": "salvaged"}
OLED = {"name": "SSD1306 OLED", "type": "display", "module_id": "ssd1306", "condition": "new"}
AMP = {"name": "MAX98357A I2S amp", "type": "audio", "module_id": "max98357a-i2s-amp", "condition": "new"}
LIMIT = {"name": "limit switch", "type": "sensor", "module_id": "limit-switch-3pin", "condition": "salvaged"}
BUCK = {"name": "MP1584 buck", "type": "buck", "module_id": "buck-mp1584", "condition": "salvaged"}
RC_DONOR = {
    "name": "dead RC toy car donor board",
    "type": "donor_board",
    "condition": "salvaged",
    "notes": "Dual H-bridge section intact",
}
PRINTER_DONOR = {
    "name": "dead inkjet motion board",
    "type": "donor_board",
    "condition": "salvaged",
    "notes": "Stepper driver section + endstops",
}


def _p(
    *,
    id: str,
    family: str,
    goal: str,
    parts: List[Dict[str, Any]],
    analogs: List[str],
    preferred_build_ids: Optional[List[str]] = None,
    expected_capabilities: Optional[List[str]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    compile_candidate: bool = False,
    donor_fixture: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "id": id,
        "family": family,
        "depth": "enabot_class",
        "commercial_analogs": analogs,
        "goal": goal,
        "available_parts": parts,
        "constraints": {
            "strategy_mode": "constrained",
            "prefer_salvage": True,
            **(constraints or {}),
        },
        "preferred_build_ids": preferred_build_ids or [],
        "expected_capabilities": expected_capabilities
        or ["controller", "power", "sensor_or_adc", "motor_or_load"],
        "compile_candidate": compile_candidate,
        "tags": tags or [],
    }
    if donor_fixture:
        row["donor_fixture"] = donor_fixture
        row["circuit"] = {
            "mode": "circuit_board_system",
            "boards": [
                {
                    "board_id": "donor_0",
                    "board_name": "donor",
                    "functional_salvage": f"@examples/fixtures/{donor_fixture}",
                }
            ],
        }
    return row


def _variants(base_id: str, family: str, goal_tpl: str, part_sets: List[tuple], **kwargs) -> List[Dict[str, Any]]:
    rows = []
    for suffix, parts, extra_goal in part_sets:
        rows.append(
            _p(
                id=f"{base_id}_{suffix}" if suffix else base_id,
                family=family,
                goal=goal_tpl.format(extra=extra_goal),
                parts=parts,
                **kwargs,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Family generators — exhaustive addressable space
# ---------------------------------------------------------------------------


def family_mobile_telepresence() -> List[Dict[str, Any]]:
    rows = []
    products = [
        ("enabot_ebo_air", ["Enabot EBO Air", "EBO SE"], "DIY Enabot-like rolling home camera robot"),
        ("enabot_ebo_x", ["Enabot EBO X"], "DIY family companion rolling robot with camera and dual-wheel drive"),
        ("moorebot_scout", ["Moorebot Scout"], "DIY mecanum-style home patrol camera robot"),
        ("amazon_astro_cousin", ["Amazon Astro"], "DIY indoor patrol telepresence robot with camera and obstacle sensing"),
        ("moripet_cousin", ["Moripet"], "DIY pet-watching rolling camera robot"),
        ("loona_cousin", ["Loona Petbot"], "DIY interactive pet companion robot with drive and camera"),
        ("switchbot_patrol_cam", ["SwitchBot K20+ Pro Patrol"], "DIY rolling camera patrol base separate from vacuum"),
        ("vtech_kidizoom_rover", ["VTech Kidizoom"], "DIY kid telepresence rover with camera"),
        ("double_robotics_cousin", ["Double 3"], "DIY tall telepresence drive base with camera head"),
        ("ohbot_desk_cousin", ["Ohbot"], "DIY desk telepresence head on wheeled base"),
    ]
    for pid, analogs, goal in products:
        rows.append(
            _p(
                id=pid,
                family="mobile_telepresence",
                goal=f"{goal}: dual-wheel drive, Wi-Fi camera, battery, obstacle sense",
                parts=[RC_DONOR, DC_MOT, DC_MOT_R, ESP32_CAM, TOF, BATT74],
                analogs=analogs,
                preferred_build_ids=["robot_drive_base"],
                expected_capabilities=["controller", "camera_or_vision", "wheel_or_drive", "actuator_driver"],
                constraints={"battery_voltage_v": 7.4},
                compile_candidate=pid in {"enabot_ebo_air", "moorebot_scout"},
                donor_fixture="splice_donor_rc_motor_board.json",
                tags=["flagship", "camera", "drive"],
            )
        )
        # DevKit variant without CAM module id
        rows.append(
            _p(
                id=f"{pid}_devkit_wifi",
                family="mobile_telepresence",
                goal=f"{goal} using ESP32 DevKit + separate USB webcam later",
                parts=[RC_DONOR, DC_MOT, DC_MOT_R, ESP32, US, BATT74, BUCK],
                analogs=analogs,
                preferred_build_ids=["robot_drive_base"],
                constraints={"battery_voltage_v": 7.4},
                donor_fixture="splice_donor_rc_motor_board.json",
                tags=["drive", "wifi"],
            )
        )
    return rows


def family_pet_care() -> List[Dict[str, Any]]:
    rows = []
    specs = [
        ("pet_feeder_portion", ["PETKIT Fresh Element", "WOPET"], "automatic pet feeder with timed servo portion gate", [ESP32, SG90, USB5, OLED], ["smart_relay_box", "low_voltage_motor_test_jig"], ["controller", "mechanical_motion"]),
        ("pet_feeder_gravity_alert", ["Cat Mate"], "pet feeder empty alert with load-cell style weight sense and Wi-Fi notify", [ESP32, {"name": "HX711 load cell", "type": "sensor", "module_id": "hx711-loadcell"}, USB5, OLED], ["sensor_logger"], ["controller", "sensor_or_adc"]),
        ("treat_dispenser_remote", ["Furbo", "Petcube Bites"], "remote treat dispenser with servo flapper and camera mount", [ESP32_CAM, SG90, USB5], ["inspection_motion_fixture", "robot_drive_base"], ["camera_or_vision", "mechanical_motion"]),
        ("laser_cat_play_bot", ["Pet-mate AI", "GoPetie"], "rolling laser-play bot for cats with drive and pointer servo", [ESP32, DC_MOT, DC_MOT_R, L298, SG90, USB5], ["robot_drive_base"], ["wheel_or_drive", "mechanical_motion"]),
        ("litter_box_cycle_sense", ["Litter-Robot"], "litter box cycle detector with motor current and PIR presence", [ESP32, DC_MOT, MOSFET, PIR, USB5], ["smart_relay_box", "sensor_logger"], ["motor_or_load", "sensor_or_adc"]),
        ("water_fountain_pet", ["PetSafe Drinkwell"], "pet water fountain pump controller with water-level sense", [ESP32, PUMP, MOSFET, US, USB5], ["automatic_plant_watering_usb", "automatic_plant_watering"], ["fan_or_pump"]),
        ("pet_door_latch", ["SureFlap"], "RFID/pet door latch servo with hall sense", [ESP32, SG90, {"name": "hall sensor", "type": "sensor", "module_id": "hall_effect_a3144"}, USB5], ["low_voltage_motor_test_jig", "smart_relay_box"], ["mechanical_motion"]),
        ("aquarium_auto_feeder", ["Eheim", "Fish Mate"], "aquarium auto feeder drum on stepper with schedule", [ESP32, STEPPER, A4988, USB5], ["plotter_motion_stage", "low_voltage_motor_test_jig"], ["mechanical_motion"]),
    ]
    for pid, analogs, goal, parts, builds, caps in specs:
        rows.append(
            _p(
                id=pid,
                family="pet_care",
                goal=goal,
                parts=parts,
                analogs=analogs,
                preferred_build_ids=builds,
                expected_capabilities=caps,
                compile_candidate=pid in {"pet_feeder_portion", "water_fountain_pet"},
                tags=["pet"],
            )
        )
    return rows


def family_plant_garden() -> List[Dict[str, Any]]:
    rows = []
    soils = [
        ("soil_drip", "soil moisture drip irrigation for one plant", [ESP32, SOIL, PUMP, MOSFET, USB5], True),
        ("soil_drip_12v", "garden bed drip with 12V pump and soil probe", [ESP32, SOIL, {"name": "12V pump", "type": "pump"}, MOSFET, BARREL12, BUCK], False),
        ("greenhouse_climate", "greenhouse climate logger with soil and BME280", [ESP32, SOIL, BME, USB5, OLED], False),
        ("grow_light_timer", "grow light relay schedule with light sensor", [ESP32, RELAY, {"name": "BH1750", "type": "sensor", "module_id": "bh1750"}, USB5], False),
        ("hydroponic_topoff", "hydroponic reservoir auto top-off with ultrasonic level", [ESP32, PUMP, MOSFET, US, USB5], False),
        ("balcony_rain_skip", "balcony watering that skips when rain detected", [ESP32, SOIL, PUMP, MOSFET, {"name": "rain sensor", "type": "sensor"}, USB5], False),
        ("compost_temp_logger", "compost pile temperature logger with alerts", [ESP32, {"name": "DS18B20", "type": "sensor", "module_id": "ds18b20"}, USB5], False),
        ("mushroom_humidity", "mushroom tent humidifier relay with DHT", [ESP32, DHT, RELAY, USB5], False),
        ("vineyard_node", "outdoor soil+temp LoRa-ready sensor node (Wi-Fi stand-in)", [ESP32, SOIL, DHT, BATT74], False),
        ("aeroponics_mist", "aeroponics mist solenoid timed cycles", [ESP32, {"name": "solenoid valve", "type": "solenoid", "module_id": "solenoid_valve_12v"}, MOSFET, BARREL12], False),
    ]
    for pid, goal, parts, compile_c in soils:
        rows.append(
            _p(
                id=f"plant_{pid}",
                family="plant_garden",
                goal=goal,
                parts=parts,
                analogs=["Click & Grow", "Gardena", "RainMachine", "Grobo"],
                preferred_build_ids=["automatic_plant_watering", "automatic_plant_watering_usb", "sensor_logger", "smart_relay_box"],
                compile_candidate=compile_c,
                tags=["plant"],
            )
        )
    return rows


def family_air_climate() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("usb_fume_extractor", "USB desk solder fume extractor with fan and speed control", [ESP32, FAN, MOSFET, USB5], ["usb_fume_extractor"], True),
        ("aqi_room_station", "room air quality station with display", [ESP32, {"name": "ENS160", "module_id": "ens160-airquality", "type": "sensor"}, OLED, USB5], ["room_display_station", "sensor_logger"], True),
        ("co2_classroom", "CO2 classroom monitor with SCD41 and OLED", [ESP32, {"name": "SCD41", "module_id": "scd41-co2", "type": "sensor"}, OLED, USB5], ["room_display_station", "sensor_logger"], False),
        ("humidifier_auto", "humidifier relay controlled by DHT humidity", [ESP32, DHT, RELAY, USB5], ["smart_relay_box"], False),
        ("dehumidifier_crawl", "crawlspace dehumidifier relay with humidity threshold", [ESP32, DHT, RELAY, BARREL12], ["smart_relay_box"], False),
        ("bathroom_fan_humidity", "bathroom fan controller on humidity", [ESP32, DHT, MOSFET, FAN, USB5], ["usb_fume_extractor", "smart_relay_box"], False),
        ("heater_frost_guard", "frost-guard plug relay with temperature", [ESP32, DHT, RELAY, USB5], ["smart_relay_box"], False),
        ("pc_intake_dust", "PC intake fan PWM-ish MOSFET control from temp", [ESP32, DHT, MOSFET, FAN, USB5], ["usb_fume_extractor"], False),
        ("smoke_bench_alarm", "bench MQ-2 gas/smoke alarm with buzzer", [ESP32, {"name": "MQ-2", "module_id": "mq-2_gas_sensor", "type": "sensor"}, {"name": "buzzer", "module_id": "active_buzzer", "type": "buzzer"}, USB5], ["sensor_logger", "network_status_indicator"], False),
        ("radon_style_logger", "long-term air logger (VOC stand-in) with SD-less Wi-Fi upload", [ESP32, BME, USB5], ["sensor_logger"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="air_climate",
                goal=goal,
                parts=parts,
                analogs=["Airthings", "Awair", "Dyson Purifier", "Adafruit AirLift kits"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["air"],
            )
        )
    return rows


def family_security_access() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("smart_relay_lamp", "smart relay box for desk lamp Wi-Fi control", [ESP32, RELAY, USB5], ["smart_relay_box"], True),
        ("garage_opener_button", "garage door opener dry-contact relay with status reed", [ESP32, RELAY, {"name": "reed switch", "type": "sensor"}, USB5], ["smart_relay_box"], False),
        ("door_alarm_pir", "doorway alarm with PIR and buzzer", [ESP32, PIR, {"name": "buzzer", "module_id": "active_buzzer"}, USB5], ["sensor_logger", "network_status_indicator"], False),
        ("window_leak_siren", "window/leak sensor node with siren output", [ESP32, {"name": "water leak probe", "type": "sensor"}, MOSFET, {"name": "siren", "type": "load"}, USB5], ["sensor_logger", "smart_relay_box"], False),
        ("mailbox_notifier", "mailbox open notifier with reed and Wi-Fi", [ESP32, {"name": "reed", "type": "sensor"}, BATT74], ["sensor_logger"], False),
        ("gate_latch_servo", "garden gate latch servo with limit sense", [ESP32, SG90, LIMIT, BATT74], ["low_voltage_motor_test_jig"], False),
        ("panic_button_node", "eldercare panic button Wi-Fi node with LED ack", [ESP32, {"name": "button", "type": "button"}, {"name": "status LED", "type": "led"}, USB5], ["network_status_indicator", "salvaged_input_panel"], False),
        ("camera_ir_illuminator", "IR illuminator for security cam with MOSFET dim", [ESP32, MOSFET, {"name": "IR LED array", "type": "led"}, USB5], ["camera_ir_light_or_sensor_mount", "indicator_or_task_light"], False),
        ("driveway_tof_alert", "driveway ToF beam-break alert", [ESP32, TOF, {"name": "buzzer", "module_id": "active_buzzer"}, USB5], ["sensor_logger"], False),
        ("safe_box_lock", "DIY lockbox servo latch with keypad later", [ESP32, SG90, USB5], ["low_voltage_motor_test_jig"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="security_access",
                goal=goal,
                parts=parts,
                analogs=["Ring", "Aqara", "SwitchBot", "August"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["security"],
            )
        )
    return rows


def family_desktop_fab() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("plotter_inkjet_salvage", "plotter motion stage from inkjet printer salvage", [PRINTER_DONOR, ESP32, LIMIT, LIMIT, BARREL12, BUCK], ["plotter_motion_stage"], True, "splice_donor_inkjet_motion_board.json"),
        ("laser_gantry_cousin", "diode laser gantry cousin — XY steppers + limits", [ESP32, STEPPER, STEPPER, A4988, A4988, LIMIT, BARREL12], ["plotter_motion_stage"], False, None),
        ("vinyl_cutter_cousin", "vinyl cutter X-axis stepper with force servo", [ESP32, STEPPER, A4988, SG90, LIMIT, USB5], ["plotter_motion_stage"], False, None),
        ("pcb_drill_z", "PCB drill Z stepper with limit and spindle relay", [ESP32, STEPPER, A4988, RELAY, LIMIT, BARREL12], ["plotter_motion_stage", "smart_relay_box"], False, None),
        ("rotary_engraver", "rotary engraver axis from salvaged scanner motor", [ESP32, DC_MOT, L298, LIMIT, USB5], ["low_voltage_motor_test_jig", "plotter_motion_stage"], False, None),
        ("clay_extruder", "clay extruder stepper feeder for ceramic printer cousin", [ESP32, STEPPER, A4988, BARREL12], ["plotter_motion_stage"], False, None),
        ("pick_place_demo", "desktop pick-and-place demo arm joint on servo", [ESP32, SG90, SG90, SG90, USB5], ["inspection_motion_fixture", "low_voltage_motor_test_jig"], False, None),
        ("cnc_probe_jig", "CNC Z-probe continuity jig with LED", [ESP32, {"name": "probe tip", "type": "sensor"}, {"name": "LED", "type": "led"}, USB5], ["indicator_or_task_light", "sensor_logger"], False, None),
    ]
    for pid, goal, parts, builds, compile_c, donor in items:
        rows.append(
            _p(
                id=pid,
                family="desktop_fab",
                goal=goal,
                parts=parts,
                analogs=["Axidraw", "Ortur", "Shapeoko", "Ender salvage"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                donor_fixture=donor,
                tags=["fab", "motion"],
            )
        )
    return rows


def family_inspection_camera() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("pan_tilt_inspection", "pan-tilt inspection camera mount with two servos", [ESP32, SG90, SG90, USB5], ["inspection_motion_fixture"], True),
        ("pan_tilt_esp_cam", "ESP32-CAM on pan-tilt head for bench inspection", [ESP32_CAM, SG90, SG90, USB5], ["inspection_motion_fixture", "camera_ir_light_or_sensor_mount"], True),
        ("slider_dolly", "camera slider dolly with stepper and endstops", [ESP32, STEPPER, A4988, LIMIT, USB5], ["plotter_motion_stage", "inspection_motion_fixture"], False),
        ("turntable_photo", "360° photo turntable with stepper", [ESP32, STEPPER, A4988, USB5], ["plotter_motion_stage"], False),
        ("focus_stack_rail", "focus stacking rail with fine stepper", [ESP32, STEPPER, A4988, LIMIT, USB5], ["plotter_motion_stage"], False),
        ("borescope_light", "borescope LED ring light with MOSFET dimmer", [ESP32, MOSFET, {"name": "LED ring", "type": "led"}, USB5], ["camera_ir_light_or_sensor_mount", "indicator_or_task_light"], False),
        ("timelapse_trigger", "camera timelapse trigger opto/relay", [ESP32, RELAY, USB5], ["smart_relay_box"], False),
        ("microscope_stage", "USB microscope XY stage cousin with two steppers", [ESP32, STEPPER, STEPPER, A4988, USB5], ["plotter_motion_stage"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="inspection_camera",
                goal=goal,
                parts=parts,
                analogs=["Neewer pan-tilt", "Syrp Genie", "OpenFlexure"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["camera", "motion"],
            )
        )
    return rows


def family_audio_comms() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("bluetooth_amp_box", "small Bluetooth-ish amp box with I2S amp and ESP32", [ESP32, AMP, USB5], ["small_audio_amp_box"], True),
        ("doorbell_intercom", "Wi-Fi doorbell with button, amp, and OLED", [ESP32, AMP, {"name": "button", "type": "button"}, OLED, USB5], ["small_audio_amp_box", "salvaged_input_panel"], False),
        ("baby_monitor_audio", "room audio monitor node with mic amp stub and Wi-Fi", [ESP32, AMP, USB5], ["small_audio_amp_box"], False),
        ("workshop_pager", "workshop pager buzzer + LED ack over Wi-Fi", [ESP32, {"name": "buzzer", "module_id": "active_buzzer"}, {"name": "LED", "type": "led"}, USB5], ["network_status_indicator"], False),
        ("guitar_practice_amp", "tiny practice amp with PAM8403", [ESP32, {"name": "PAM8403", "module_id": "pam8403_amplifier", "type": "audio"}, USB5], ["small_audio_amp_box"], False),
        ("tts_alert_box", "spoken alert box with DFPlayer and amp", [ESP32, {"name": "DFPlayer", "module_id": "dfplayer_mini", "type": "audio"}, AMP, USB5], ["small_audio_amp_box"], False),
        ("two_way_gate_intercom", "gate intercom amp + relay door strike", [ESP32, AMP, RELAY, USB5], ["small_audio_amp_box", "smart_relay_box"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="audio_comms",
                goal=goal,
                parts=parts,
                analogs=["Google Nest Mini hacks", "DFRobot audio kits"],
                preferred_build_ids=builds,
                expected_capabilities=["controller", "speaker_or_audio"],
                compile_candidate=compile_c,
                tags=["audio"],
            )
        )
    return rows


def family_display_info() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("room_display_station", "room display station with BME280 and OLED", [ESP32, BME, OLED, USB5], ["room_display_station", "sensor_logger"], True),
        ("kitchen_timer_panel", "kitchen timer / countdown panel with buttons and OLED", [ESP32, OLED, {"name": "buttons", "type": "button"}, USB5], ["room_display_station", "salvaged_input_panel"], False),
        ("bus_arrival_board", "bus arrival status board Wi-Fi OLED", [ESP32, OLED, USB5], ["room_display_station", "network_status_indicator"], False),
        ("server_rack_temp", "server rack temp display with alerts", [ESP32, DHT, OLED, USB5], ["room_display_station", "sensor_logger"], False),
        ("stock_ticker_desk", "desk status ticker OLED Wi-Fi", [ESP32, OLED, USB5], ["network_status_indicator", "room_display_station"], False),
        ("calendar_eink_cousin", "calendar desk display cousin on OLED", [ESP32, OLED, USB5], ["room_display_station"], False),
        ("pomodoro_lamp_display", "pomodoro timer with OLED and task light MOSFET", [ESP32, OLED, MOSFET, {"name": "LED lamp", "type": "led"}, USB5], ["indicator_or_task_light", "room_display_station"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="display_info",
                goal=goal,
                parts=parts,
                analogs=["Tidbyt", "TRMNL", "Awair"],
                preferred_build_ids=builds,
                expected_capabilities=["controller", "display_or_ui"],
                compile_candidate=compile_c,
                tags=["display"],
            )
        )
    return rows


def family_lighting() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("task_light_dim", "bench task light MOSFET dimmer with button", [ESP32, MOSFET, {"name": "LED panel", "type": "led"}, {"name": "button", "type": "button"}, USB5], ["indicator_or_task_light"], True),
        ("under_cabinet_pwm", "under-cabinet LED strip controller", [ESP32, MOSFET, {"name": "LED strip", "type": "led"}, USB5], ["indicator_or_task_light"], False),
        ("plant_grow_bar", "plant grow light bar timed MOSFET", [ESP32, MOSFET, {"name": "grow LED", "type": "led"}, USB5], ["indicator_or_task_light", "automatic_plant_watering_usb"], False),
        ("uv_cure_box", "UV cure box timed relay", [ESP32, RELAY, USB5], ["smart_relay_box", "indicator_or_task_light"], False),
        ("night_light_pir", "hallway night light on PIR", [ESP32, PIR, MOSFET, {"name": "LED", "type": "led"}, USB5], ["indicator_or_task_light"], False),
        ("photography_softbox", "softbox LED panel dimmer", [ESP32, MOSFET, {"name": "LED panel", "type": "led"}, USB5], ["indicator_or_task_light"], False),
        ("bike_dyno_light", "bike light from battery with MOSFET and button", [ESP32, MOSFET, {"name": "LED", "type": "led"}, BATT74], ["indicator_or_task_light"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="lighting",
                goal=goal,
                parts=parts,
                analogs=["Philips Hue DIY", "Nanoleaf cousin"],
                preferred_build_ids=builds,
                expected_capabilities=["controller", "led_or_light"],
                compile_candidate=compile_c,
                tags=["lighting"],
            )
        )
    return rows


def family_kitchen_appliance() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("sous_vide_controller", "sous-vide immersion controller with temp probe and heater relay", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, RELAY, OLED, USB5], ["smart_relay_box", "sensor_logger"], True),
        ("coffee_preheat", "coffee machine preheat relay schedule", [ESP32, RELAY, DHT, USB5], ["smart_relay_box"], False),
        ("fridge_door_alarm", "fridge door left-open alarm", [ESP32, {"name": "reed", "type": "sensor"}, {"name": "buzzer", "module_id": "active_buzzer"}, USB5], ["sensor_logger"], False),
        ("slow_cooker_timer", "slow cooker timed relay cutout", [ESP32, RELAY, USB5], ["smart_relay_box"], False),
        ("fermentation_chamber", "fermentation chamber temp control relay + DHT", [ESP32, DHT, RELAY, USB5], ["smart_relay_box", "sensor_logger"], False),
        ("egg_incubator", "egg incubator temp/humidity control", [ESP32, DHT, RELAY, USB5], ["smart_relay_box"], False),
        ("smoke_ventilator", "kitchen smoke-triggered vent fan", [ESP32, {"name": "MQ-2", "module_id": "mq-2_gas_sensor"}, MOSFET, FAN, USB5], ["usb_fume_extractor"], False),
        ("rice_cooker_monitor", "rice cooker done detector via temp curve logger", [ESP32, DHT, USB5], ["sensor_logger"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="kitchen_appliance",
                goal=goal,
                parts=parts,
                analogs=["Anova", "Inkbird", "ThermoPro"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["kitchen"],
            )
        )
    return rows


def family_lab_bench() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("bench_power_adapter", "bench adjustable buck power adapter UI", [ESP32, BUCK, OLED, BARREL12], ["bench_power_adapter"], True),
        ("usb_uart_debug", "USB UART debug adapter bring-up", [ESP32, {"name": "CH340", "module_id": "ch340-usb-ttl", "type": "usb"}, USB5], ["usb_uart_debug_adapter"], False),
        ("motor_test_jig", "low voltage motor test jig with driver and current sense", [ESP32, L298, DC_MOT, {"name": "INA219", "module_id": "ina219-current"}, USB5], ["low_voltage_motor_test_jig"], True),
        ("load_cell_scale", "bench scale with HX711 and OLED", [ESP32, {"name": "HX711", "module_id": "hx711-loadcell"}, OLED, USB5], ["sensor_logger", "room_display_station"], False),
        ("thermal_couple_logger", "thermocouple logger MAX31855", [ESP32, {"name": "MAX31855", "module_id": "max31855-thermocouple"}, OLED, USB5], ["sensor_logger"], False),
        ("power_logger_ina", "USB power logger with INA219", [ESP32, {"name": "INA219", "module_id": "ina219-current"}, OLED, USB5], ["sensor_logger"], False),
        ("vibration_test", "vibration endurance jig with motor and SW-420", [ESP32, DC_MOT, L298, {"name": "SW-420", "module_id": "sw_420_vibration"}, USB5], ["low_voltage_motor_test_jig"], False),
        ("relay_burn_in", "relay burn-in cycle jig", [ESP32, RELAY, USB5], ["smart_relay_box"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="lab_bench",
                goal=goal,
                parts=parts,
                analogs=["Rigol bench cousins", "SparkFun kits"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["bench"],
            )
        )
    return rows


def family_outdoor_water() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("sprinkler_zone", "sprinkler zone solenoid controller", [ESP32, {"name": "solenoid", "module_id": "solenoid_valve_12v"}, MOSFET, BARREL12], ["smart_relay_box", "automatic_plant_watering"], True),
        ("pond_pump_timer", "pond pump timer with water-level ultrasonic", [ESP32, {"name": "12V pump", "type": "pump"}, MOSFET, US, BARREL12], ["automatic_plant_watering", "smart_relay_box"], False),
        ("rain_barrel_level", "rain barrel level logger + pump assist", [ESP32, US, PUMP, MOSFET, BATT74], ["automatic_plant_watering", "sensor_logger"], False),
        ("pool_chem_logger", "pool pH/ORP-style logger stand-in with temp", [ESP32, DHT, USB5], ["sensor_logger"], False),
        ("hot_tub_panel", "hot tub temperature panel with heater relay", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, RELAY, OLED, BARREL12], ["smart_relay_box", "room_display_station"], False),
        ("drip_filter_flush", "drip filter flush solenoid weekly", [ESP32, {"name": "solenoid", "module_id": "solenoid_valve_12v"}, BARREL12], ["smart_relay_box"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="outdoor_water",
                goal=goal,
                parts=parts,
                analogs=["Rachio", "Orbit B-hyve", "Gardena"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["outdoor", "water"],
            )
        )
    return rows


def family_edu_robotics() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("line_follower", "line follower robot with dual motors and TCRT sensors", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "TCRT5000", "module_id": "tcrt5000_line_follower"}, USB5], ["robot_drive_base"], True),
        ("sumo_bot", "mini sumo bot dual drive with ultrasonic", [ESP32, DC_MOT, DC_MOT_R, L298, US, BATT74], ["robot_drive_base"], False),
        ("robot_arm_3dof", "3-DOF servo robot arm for education", [ESP32, SG90, SG90, SG90, USB5], ["inspection_motion_fixture", "low_voltage_motor_test_jig"], True),
        ("gripper_claw", "servo gripper claw test jig", [ESP32, SG90, USB5], ["low_voltage_motor_test_jig"], False),
        ("maze_solver", "maze solver rover with ToF", [ESP32, DC_MOT, DC_MOT_R, L298, TOF, BATT74], ["robot_drive_base"], False),
        ("balancing_cousin", "balancing robot cousin with MPU6050 and dual drive", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "MPU6050", "module_id": "mpu6050"}, BATT74], ["robot_drive_base"], False),
        ("drone_gimbal_2axis", "2-axis camera gimbal servos with IMU", [ESP32, SG90, SG90, {"name": "MPU6050", "module_id": "mpu6050"}, USB5], ["inspection_motion_fixture"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="edu_robotics",
                goal=goal,
                parts=parts,
                analogs=["mBot", "Arduino Robot", "Otto DIY"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["edu", "robot"],
            )
        )
    return rows


def family_sensor_networks() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("wifi_sensor_logger", "Wi-Fi environmental sensor logger", [ESP32, BME, USB5], ["sensor_logger"], True),
        ("soil_mesh_node", "garden soil moisture node", [ESP32, SOIL, BATT74], ["sensor_logger", "automatic_plant_watering"], False),
        ("leak_under_sink", "under-sink leak detector Wi-Fi", [ESP32, {"name": "leak probe", "type": "sensor"}, USB5], ["sensor_logger"], False),
        ("freezer_temp_alarm", "freezer temperature alarm node", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, BATT74], ["sensor_logger"], False),
        ("server_room_triple", "server room temp/humid/door logger", [ESP32, BME, {"name": "reed", "type": "sensor"}, USB5], ["sensor_logger"], False),
        ("bee_hive_scale", "bee hive weight + temp logger", [ESP32, {"name": "HX711", "module_id": "hx711-loadcell"}, DHT, BATT74], ["sensor_logger"], False),
        ("lightning_detector", "AS3935 lightning detector logger", [ESP32, {"name": "AS3935", "module_id": "as3935_lightning"}, USB5], ["sensor_logger"], False),
        ("power_outage_watch", "power outage watcher on battery with Wi-Fi ping", [ESP32, BATT74], ["sensor_logger", "network_status_indicator"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="sensor_networks",
                goal=goal,
                parts=parts,
                analogs=["SensorPush", "Temp Stick", "Home Assistant nodes"],
                preferred_build_ids=builds,
                expected_capabilities=["controller", "sensor_or_adc", "wireless"],
                compile_candidate=compile_c,
                tags=["sensors"],
            )
        )
    return rows


def family_cleaning_mobility_cousins() -> List[Dict[str, Any]]:
    """DIY cousins of vacuums/mowers/window bots — depth without claiming full clones."""
    rows = []
    items = [
        ("mini_vac_drive", "mini vacuum-like drive base with brush motor and cliff ToF", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "brush motor", "type": "dc_motor"}, TOF, BATT74], ["robot_drive_base"], True),
        ("mop_pad_vibe", "mop pad vibration motor robot with dual drive", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "vibe motor", "module_id": "vibration_motor"}, BATT74], ["robot_drive_base"], False),
        ("window_cleaner_cousin", "window cleaner suction-fan cousin with edge sense", [ESP32, FAN, MOSFET, US, BATT74], ["usb_fume_extractor", "robot_drive_base"], False),
        ("lawn_perimeter_bot", "lawn perimeter wire-follow cousin with coil sense + drive", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "inductive sense", "type": "sensor"}, BATT74], ["robot_drive_base"], False),
        ("pool_skim_bot", "pool surface skimmer drive cousin", [ESP32, DC_MOT, DC_MOT_R, L298, BATT74], ["robot_drive_base"], False),
        ("gutter_clean_demo", "gutter clean demo carriage with auger motor", [ESP32, DC_MOT, L298, LIMIT, BATT74], ["low_voltage_motor_test_jig", "robot_drive_base"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="cleaning_mobility",
                goal=goal,
                parts=parts,
                analogs=["Roomba", "Roborock", "Winbot", "Husqvarna Automower", "Aiper"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["cleaning", "drive"],
            )
        )
    return rows


def family_health_access() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("pulseox_bench", "bench pulse-ox logger MAX30102 with OLED", [ESP32, {"name": "MAX30102", "module_id": "max30102-pulse-ox"}, OLED, USB5], ["sensor_logger", "room_display_station"], False),
        ("med_reminder_box", "pill reminder box with servo lid and buzzer", [ESP32, SG90, {"name": "buzzer", "module_id": "active_buzzer"}, OLED, USB5], ["low_voltage_motor_test_jig", "room_display_station"], False),
        ("fall_detect_alert", "wearable-ish fall detect alert node with IMU", [ESP32, {"name": "MPU6050", "module_id": "mpu6050"}, {"name": "buzzer", "module_id": "active_buzzer"}, BATT74], ["sensor_logger"], False),
        ("handwash_timer", "handwash timer with ToF presence and LED", [ESP32, TOF, {"name": "LED", "type": "led"}, USB5], ["indicator_or_task_light", "sensor_logger"], False),
        ("posture_seat_buzz", "desk posture buzz with IMU", [ESP32, {"name": "MPU6050", "module_id": "mpu6050"}, {"name": "vibe", "module_id": "vibration_motor"}, USB5], ["sensor_logger"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="health_access",
                goal=goal,
                parts=parts,
                analogs=["Wellue", "MedMinder DIY"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["health"],
            )
        )
    return rows


def family_mobility_vehicle() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("ebike_bat_gauge", "e-bike battery gauge with INA219 and OLED", [ESP32, {"name": "INA219", "module_id": "ina219-current"}, OLED, BATT74], ["sensor_logger", "room_display_station"], False),
        ("scooter_throttle_log", "scooter throttle logger with hall sensor", [ESP32, {"name": "hall", "module_id": "hall_effect_a3144"}, OLED, BATT74], ["sensor_logger"], False),
        ("trailer_brake_light", "trailer brake light controller from switch", [ESP32, MOSFET, {"name": "LED bar", "type": "led"}, {"name": "switch", "type": "button"}, BATT74], ["indicator_or_task_light"], False),
        ("boat_bilge_auto", "boat bilge pump auto with water sense", [ESP32, {"name": "bilge pump", "type": "pump"}, MOSFET, {"name": "water sense", "type": "sensor"}, BATT74], ["automatic_plant_watering", "smart_relay_box"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="mobility_vehicle",
                goal=goal,
                parts=parts,
                analogs=["Cycle Analyst cousins", "NMEA DIY"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["vehicle"],
            )
        )
    return rows


def family_industrial_lite() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("conveyor_jog", "bench conveyor jog with DC motor and limits", [ESP32, DC_MOT, L298, LIMIT, BARREL12], ["low_voltage_motor_test_jig", "robot_drive_base"], False),
        ("label_applicator", "label applicator peel stepper demo", [ESP32, STEPPER, A4988, LIMIT, USB5], ["plotter_motion_stage"], False),
        ("parts_counter", "parts counter with IR break-beam and OLED", [ESP32, {"name": "IR obstacle", "module_id": "ir_obstacle_sensor"}, OLED, USB5], ["sensor_logger", "room_display_station"], False),
        ("solenoid_sort_gate", "solenoid sort gate on IR detect", [ESP32, {"name": "solenoid", "module_id": "solenoid_valve_12v"}, {"name": "IR", "module_id": "ir_obstacle_sensor"}, BARREL12], ["smart_relay_box"], False),
        ("vibration_bowl_feeder", "vibration bowl feeder amplitude MOSFET", [ESP32, MOSFET, {"name": "vibe motor", "module_id": "vibration_motor"}, BARREL12], ["low_voltage_motor_test_jig"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="industrial_lite",
                goal=goal,
                parts=parts,
                analogs=["factory cell demos", "Arduino industrial kits"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["industrial"],
            )
        )
    return rows


def family_home_assistive() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("curtain_opener", "curtain opener with DC motor and limits", [ESP32, DC_MOT, L298, LIMIT, USB5], ["low_voltage_motor_test_jig", "robot_drive_base"], True),
        ("blind_tilt_servo", "blind tilt servo schedule", [ESP32, SG90, USB5], ["low_voltage_motor_test_jig", "inspection_motion_fixture"], False),
        ("plant_shelf_light", "plant shelf light + watering combo", [ESP32, SOIL, PUMP, MOSFET, {"name": "LED", "type": "led"}, USB5], ["automatic_plant_watering_usb", "indicator_or_task_light"], False),
        ("trash_lid_servo", "touchless trash lid ToF + servo", [ESP32, TOF, SG90, USB5], ["inspection_motion_fixture", "low_voltage_motor_test_jig"], False),
        ("shoe_dryer_fan", "shoe dryer fan timed MOSFET", [ESP32, FAN, MOSFET, USB5], ["usb_fume_extractor"], False),
        ("wardrobe_humidity", "wardrobe dehumidifier relay + DHT", [ESP32, DHT, RELAY, USB5], ["smart_relay_box"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="home_assistive",
                goal=goal,
                parts=parts,
                analogs=["SwitchBot Curtain", "Aqara curtain"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["home"],
            )
        )
    return rows


def family_power_energy() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("solar_charge_monitor", "solar charge monitor with INA219 and OLED", [ESP32, {"name": "INA219", "module_id": "ina219-current"}, OLED, BATT74], ["sensor_logger", "bench_power_adapter"], False),
        ("usb_pd_trigger_bench", "USB-C PD trigger bench supply cousin with meter", [ESP32, {"name": "INA219", "module_id": "ina219-current"}, OLED, USB5], ["bench_power_adapter", "sensor_logger"], False),
        ("generator_auto_start", "generator auto-start relay on voltage sag sense", [ESP32, RELAY, {"name": "voltage sense", "type": "sensor"}, BARREL12], ["smart_relay_box"], False),
        ("battery_balancer_ui", "battery pack monitor UI", [ESP32, {"name": "INA219", "module_id": "ina219-current"}, OLED, BATT74], ["sensor_logger"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=pid,
                family="power_energy",
                goal=goal,
                parts=parts,
                analogs=["Victron cousins", "Powerwall DIY monitors"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["power"],
            )
        )
    return rows


def family_aquatics_vivarium() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("reef_ato", "reef aquarium auto top-off with optical level and pump", [ESP32, PUMP, MOSFET, US, USB5], ["automatic_plant_watering_usb"], True),
        ("reef_doser", "reef dosing pump timed peristaltic", [ESP32, PUMP, MOSFET, USB5], ["automatic_plant_watering_usb"], False),
        ("turtle_basking_light", "turtle basking light relay on schedule + temp", [ESP32, DHT, RELAY, USB5], ["smart_relay_box"], False),
        ("terrarium_mist", "terrarium mister solenoid + humidity", [ESP32, DHT, {"name": "solenoid", "module_id": "solenoid_valve_12v"}, BARREL12], ["smart_relay_box"], False),
        ("axolotl_chiller_fan", "axolotl tank cooling fan on temp", [ESP32, DHT, MOSFET, FAN, USB5], ["usb_fume_extractor"], False),
        ("koi_pond_aerator", "koi pond aerator pump schedule", [ESP32, {"name": "air pump", "type": "pump"}, MOSFET, BARREL12], ["smart_relay_box", "automatic_plant_watering"], False),
        ("shrimp_heater_guard", "shrimp tank heater guard relay + DS18B20", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, RELAY, USB5], ["smart_relay_box"], False),
        ("paludarium_waterfall", "paludarium waterfall pump + level", [ESP32, PUMP, MOSFET, US, USB5], ["automatic_plant_watering_usb"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=f"aqua_{pid}",
                family="aquatics_vivarium",
                goal=goal,
                parts=parts,
                analogs=["Neptune Apex cousins", "Inkbird aquarium", "Fluval"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["aqua"],
            )
        )
    return rows


def family_studio_media() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("podcast_button_box", "podcast soundboard buttons + OLED status", [ESP32, {"name": "buttons", "type": "button"}, OLED, AMP, USB5], ["salvaged_input_panel", "small_audio_amp_box"], False),
        ("stream_deck_cousin", "stream-deck cousin macro pad with LEDs", [ESP32, {"name": "buttons", "type": "button"}, {"name": "LEDs", "type": "led"}, USB5], ["salvaged_input_panel", "indicator_or_task_light"], False),
        ("camera_slider_battery", "field camera slider on battery", [ESP32, STEPPER, A4988, LIMIT, BATT74], ["plotter_motion_stage"], False),
        ("light_panel_rgb_stub", "RGB light panel MOSFET channels for studio", [ESP32, MOSFET, MOSFET, {"name": "LED panel", "type": "led"}, USB5], ["indicator_or_task_light"], False),
        ("teleprompter_scroller", "teleprompter scroll stepper", [ESP32, STEPPER, A4988, USB5], ["plotter_motion_stage"], False),
        ("clap_board_led", "clapper LED sync box", [ESP32, {"name": "button", "type": "button"}, {"name": "LED", "type": "led"}, USB5], ["indicator_or_task_light", "salvaged_input_panel"], False),
        ("vinyl_digitizer_motor", "vinyl record rotator motor speed jig", [ESP32, DC_MOT, L298, USB5], ["low_voltage_motor_test_jig"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=f"studio_{pid}",
                family="studio_media",
                goal=goal,
                parts=parts,
                analogs=["Elgato Stream Deck", "Syrp", "Nanlite DIY"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["studio"],
            )
        )
    return rows


def family_agriculture() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("chicken_coop_door", "chicken coop auto door with light sensor and motor", [ESP32, DC_MOT, L298, {"name": "BH1750", "module_id": "bh1750"}, LIMIT, BATT74], ["robot_drive_base", "low_voltage_motor_test_jig"], True),
        ("chicken_water_heat", "chicken water heater frost relay", [ESP32, DHT, RELAY, BARREL12], ["smart_relay_box"], False),
        ("greenhouse_vent", "greenhouse ridge vent opener with actuator motor", [ESP32, DC_MOT, L298, DHT, LIMIT, BATT74], ["low_voltage_motor_test_jig"], False),
        ("beehive_entrance", "beehive entrance reducer servo", [ESP32, SG90, BATT74], ["low_voltage_motor_test_jig"], False),
        ("livestock_water_trough", "livestock trough refill valve + level", [ESP32, {"name": "solenoid", "module_id": "solenoid_valve_12v"}, US, BARREL12], ["smart_relay_box", "automatic_plant_watering"], False),
        ("grain_bin_temp", "grain bin temp cable logger cousin", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, BATT74], ["sensor_logger"], False),
        ("irrigation_pivot_end", "small-plot irrigation end-gun relay", [ESP32, RELAY, BARREL12], ["smart_relay_box"], False),
        ("soil_npk_node", "soil moisture+temp farm node", [ESP32, SOIL, DHT, BATT74], ["sensor_logger", "automatic_plant_watering"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=f"ag_{pid}",
                family="agriculture",
                goal=goal,
                parts=parts,
                analogs=["FarmBot cousins", "Omlet Autodoor", "CropX"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["ag"],
            )
        )
    return rows


def family_retail_hospitality() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("queue_pager_buzzer", "restaurant queue pager buzzer Wi-Fi", [ESP32, {"name": "buzzer", "module_id": "active_buzzer"}, {"name": "LED", "type": "led"}, USB5], ["network_status_indicator"], False),
        ("table_call_button", "table call button mesh node", [ESP32, {"name": "button", "type": "button"}, USB5], ["salvaged_input_panel", "network_status_indicator"], False),
        ("fridge_case_logger", "retail fridge case temp logger", [ESP32, {"name": "DS18B20", "module_id": "ds18b20"}, USB5], ["sensor_logger"], False),
        ("door_chime_shop", "shop door chime with PIR/reed and amp", [ESP32, PIR, AMP, USB5], ["small_audio_amp_box", "sensor_logger"], False),
        ("inventory_ir_shelf", "shelf stock IR break-beam counter", [ESP32, {"name": "IR", "module_id": "ir_obstacle_sensor"}, OLED, USB5], ["sensor_logger", "room_display_station"], False),
        ("espresso_shot_timer", "espresso shot timer with button and OLED", [ESP32, {"name": "button", "type": "button"}, OLED, USB5], ["room_display_station", "salvaged_input_panel"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=f"retail_{pid}",
                family="retail_hospitality",
                goal=goal,
                parts=parts,
                analogs=["guest pager systems", "Toast hacks"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["retail"],
            )
        )
    return rows


def family_science_edu() -> List[Dict[str, Any]]:
    rows = []
    items = [
        ("weather_station_full", "DIY weather station wind/rain stubs + BME + OLED", [ESP32, BME, OLED, {"name": "reed rain tip", "type": "sensor"}, USB5], ["room_display_station", "sensor_logger"], True),
        ("seismometer_cousin", "DIY seismometer cousin with MPU6050 logger", [ESP32, {"name": "MPU6050", "module_id": "mpu6050"}, USB5], ["sensor_logger"], False),
        ("cloud_chamber_hv_watch", "cloud chamber fan + field logger (safe LV cousin)", [ESP32, FAN, MOSFET, USB5], ["usb_fume_extractor"], False),
        ("spectrometer_turn", "diy spectrometer grating turntable stepper", [ESP32, STEPPER, A4988, USB5], ["plotter_motion_stage"], False),
        ("plant_physiology_logger", "leaf temp + soil + light physiology logger", [ESP32, SOIL, {"name": "BH1750", "module_id": "bh1750"}, DHT, USB5], ["sensor_logger"], False),
        ("robotics_classroom_kit", "classroom differential drive kit with line sensors", [ESP32, DC_MOT, DC_MOT_R, L298, {"name": "TCRT", "module_id": "tcrt5000_line_follower"}, USB5], ["robot_drive_base"], False),
    ]
    for pid, goal, parts, builds, compile_c in items:
        rows.append(
            _p(
                id=f"sci_{pid}",
                family="science_edu",
                goal=goal,
                parts=parts,
                analogs=["WeatherFlow DIY", "school STEM kits"],
                preferred_build_ids=builds,
                compile_candidate=compile_c,
                tags=["science"],
            )
        )
    return rows


def expand_power_and_mcu_matrix(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cross-expand families with power/MCU/sensor variants — fills the long tail."""
    extra: List[Dict[str, Any]] = []
    expand_families = {
        "plant_garden",
        "air_climate",
        "security_access",
        "sensor_networks",
        "home_assistive",
        "pet_care",
        "kitchen_appliance",
        "outdoor_water",
        "aquatics_vivarium",
        "agriculture",
        "lighting",
        "display_info",
        "edu_robotics",
        "cleaning_mobility",
        "lab_bench",
        "science_edu",
        "retail_hospitality",
        "studio_media",
        "health_access",
        "power_energy",
        "industrial_lite",
        "mobility_vehicle",
        "audio_comms",
        "inspection_camera",
        "desktop_fab",
        "mobile_telepresence",
    }
    for row in rows:
        if row["family"] not in expand_families:
            continue
        if any(row["id"].endswith(s) for s in ("_batt", "_nano", "_pico", "_nosns")):
            continue

        # Battery variant
        parts = [p for p in row["available_parts"] if p.get("module_id") != "usb-power-5v"]
        if not any(p.get("type") == "battery" for p in parts):
            parts = parts + [BATT74]
        extra.append(
            {
                **row,
                "id": f"{row['id']}_batt",
                "goal": row["goal"] + " (battery powered)",
                "available_parts": parts,
                "constraints": {**row["constraints"], "battery_voltage_v": 7.4},
                "compile_candidate": False,
                "tags": list(set(row.get("tags") or []) | {"variant_batt"}),
            }
        )

        # Arduino nano brain variant
        parts2 = []
        swapped = False
        for p in row["available_parts"]:
            if p.get("module_id") in {"esp32-devkit", "esp32-cam-module"}:
                parts2.append(
                    {
                        "name": "Arduino Nano",
                        "type": "microcontroller",
                        "module_id": "arduino-nano",
                        "condition": "salvaged",
                    }
                )
                swapped = True
            else:
                parts2.append(p)
        if swapped:
            extra.append(
                {
                    **row,
                    "id": f"{row['id']}_nano",
                    "goal": row["goal"] + " on Arduino Nano",
                    "available_parts": parts2,
                    "compile_candidate": False,
                    "tags": list(set(row.get("tags") or []) | {"variant_nano"}),
                }
            )

        # Pico variant for sense/display-heavy
        if row["family"] in {"sensor_networks", "display_info", "lab_bench", "science_edu"}:
            parts3 = []
            swapped = False
            for p in row["available_parts"]:
                if p.get("module_id") in {"esp32-devkit", "esp32-cam-module", "arduino-nano"}:
                    parts3.append(
                        {
                            "name": "Raspberry Pi Pico",
                            "type": "microcontroller",
                            "module_id": "rpi-pico",
                            "condition": "new",
                        }
                    )
                    swapped = True
                else:
                    parts3.append(p)
            if swapped:
                extra.append(
                    {
                        **row,
                        "id": f"{row['id']}_pico",
                        "goal": row["goal"] + " on Raspberry Pi Pico",
                        "available_parts": parts3,
                        "compile_candidate": False,
                        "tags": list(set(row.get("tags") or []) | {"variant_pico"}),
                    }
                )
    return extra


def build_corpus() -> Dict[str, Any]:
    families = [
        family_mobile_telepresence,
        family_pet_care,
        family_plant_garden,
        family_air_climate,
        family_security_access,
        family_desktop_fab,
        family_inspection_camera,
        family_audio_comms,
        family_display_info,
        family_lighting,
        family_kitchen_appliance,
        family_lab_bench,
        family_outdoor_water,
        family_edu_robotics,
        family_sensor_networks,
        family_cleaning_mobility_cousins,
        family_health_access,
        family_mobility_vehicle,
        family_industrial_lite,
        family_home_assistive,
        family_power_energy,
        family_aquatics_vivarium,
        family_studio_media,
        family_agriculture,
        family_retail_hospitality,
        family_science_edu,
    ]
    products: List[Dict[str, Any]] = []
    for fn in families:
        products.extend(fn())
    products.extend(expand_power_and_mcu_matrix(products))

    # De-dupe by id
    seen = set()
    unique = []
    for p in products:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        unique.append(p)

    by_family: Dict[str, int] = {}
    for p in unique:
        by_family[p["family"]] = by_family.get(p["family"], 0) + 1

    return {
        "schema_version": SCHEMA,
        "description": (
            "Exhaustive Enabot-depth product corpus for Hardware-Splicer capability sweeps. "
            "Covers the junk→intent addressable space: multi-subsystem DIY cousins of real "
            "consumer machines (not a fixed N cap)."
        ),
        "depth_definition": {
            "enabot_class": (
                "MCU + power + at least one of sense/actuate/drive/comms; "
                "salvage-plausible; commercial analog exists or is obvious."
            )
        },
        "product_count": len(unique),
        "family_counts": dict(sorted(by_family.items())),
        "compile_candidate_count": sum(1 for p in unique if p.get("compile_candidate")),
        "products": unique,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    corpus = build_corpus()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, indent=2), encoding="utf-8")
    print(f"Wrote {corpus['product_count']} products → {args.out}")
    print("Families:")
    for fam, n in corpus["family_counts"].items():
        print(f"  {fam}: {n}")
    print(f"compile_candidates: {corpus['compile_candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
