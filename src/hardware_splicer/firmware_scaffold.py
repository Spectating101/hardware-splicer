"""Deterministic firmware starter sketches for catalog build graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from .graph_pin_map import extract_pins_from_graph


SCHEMA_VERSION = "hardware_splicer.firmware_scaffold.v1"

SketchFn = Callable[[str, List[str], Mapping[str, Any]], str]


def _plant_watering_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    soil = int(pins.get("soil") or 34)
    pump = int(pins.get("pump") or 4)
    return f"""// {build_id} — soil moisture threshold + pump driver
#include <Arduino.h>

const int SOIL_PIN = {soil};
const int PUMP_PIN = {pump};
const int DRY_THRESHOLD = 2800;

void setup() {{
  Serial.begin(115200);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
}}

void loop() {{
  int raw = analogRead(SOIL_PIN);
  bool dry = raw > DRY_THRESHOLD;
  digitalWrite(PUMP_PIN, dry ? HIGH : LOW);
  Serial.printf("soil=%d pump=%d\\n", raw, dry ? 1 : 0);
  delay(2000);
}}
"""


def _plotter_arduino(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    def _pin(key: str, default: int) -> int:
        if key in pins and pins[key] is not None:
            return int(pins[key])
        return default

    step = _pin("step", 2)
    direction = _pin("dir", 3)
    return f"""// {build_id} — A4988 STEP/DIR + limit switches
const int STEP_PIN = {step};
const int DIR_PIN = {direction};
const int LIM_X = A0;
const int LIM_Y = A4;

void setup() {{
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(LIM_X, INPUT);
  pinMode(LIM_Y, INPUT);
  Serial.begin(115200);
}}

void pulseStep() {{
  digitalWrite(STEP_PIN, HIGH);
  delayMicroseconds(800);
  digitalWrite(STEP_PIN, LOW);
  delayMicroseconds(800);
}}

void loop() {{
  if (digitalRead(LIM_X) == LOW) {{
    digitalWrite(DIR_PIN, LOW);
    for (int i = 0; i < 200; i++) pulseStep();
  }}
  Serial.println(F("plotter tick"));
  delay(500);
}}
"""


def _camera_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    return f"""// {build_id} — ESP32-CAM capture stub
#include <Arduino.h>

void setup() {{
  Serial.begin(115200);
  Serial.println(F("ESP32-CAM: mount esp_camera + WiFi stack here"));
}}

void loop() {{
  Serial.println(F("camera heartbeat"));
  delay(3000);
}}
"""


def _audio_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    return f"""// {build_id} — MAX98357A I2S alert tone stub
#include <Arduino.h>

void setup() {{
  Serial.begin(115200);
  Serial.println(F("Wire I2S BCLK/LRC/DIN to MAX98357A"));
}}

void loop() {{
  Serial.println(F("audio alert tick"));
  delay(1000);
}}
"""


def _robot_arduino(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    in1 = int(pins.get("in1") or 12)
    in2 = int(pins.get("in2") or 13)
    in3 = pins.get("in3")
    in4 = pins.get("in4")
    cam = any("esp32-cam" in str(m).lower() for m in modules)
    header = f"// {build_id} — dual H-bridge serial drive"
    if cam:
        header += " (ESP32-CAM GPIOs from bring-up)"
    if in3 is not None and in4 is not None:
        in3_i = int(in3)
        in4_i = int(in4)
        return f"""{header}
#include <Arduino.h>

const int IN1 = {in1};
const int IN2 = {in2};
const int IN3 = {in3_i};
const int IN4 = {in4_i};

void stopAll() {{
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}}

void setup() {{
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  stopAll();
  Serial.begin(115200);
  Serial.println(F("cmds: f/b/l/r/s"));
}}

void loop() {{
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == 'f') {{
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  }} else if (c == 'b') {{
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  }} else if (c == 'l') {{
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  }} else if (c == 'r') {{
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  }} else if (c == 's') {{
    stopAll();
  }}
}}
"""
    return f"""{header}
#include <Arduino.h>

const int IN1 = {in1};
const int IN2 = {in2};

void setup() {{
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  Serial.begin(115200);
}}

void loop() {{
  if (Serial.available()) {{
    char c = Serial.read();
    if (c == 'f') {{ digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW); }}
    if (c == 'b') {{ digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH); }}
    if (c == 's') {{ digitalWrite(IN1, LOW); digitalWrite(IN2, LOW); }}
  }}
}}
"""


def _dht22_esp32_sketch(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    dht_pin = int(pins.get("dht") or 4)
    return f"""// {build_id} — DHT22 on GPIO{dht_pin}
#include <Arduino.h>
#include <DHT.h>

constexpr uint8_t DHT_PIN = {dht_pin};
constexpr uint8_t DHT_TYPE = DHT22;
DHT dht(DHT_PIN, DHT_TYPE);

void setup() {{
  Serial.begin(115200);
  dht.begin();
}}

void loop() {{
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  if (isnan(humidity) || isnan(temperature)) {{
    Serial.println(F("DHT read failed — check DATA wiring"));
    delay(2000);
    return;
  }}
  Serial.printf("temp_c=%.1f humidity=%.1f\\n", temperature, humidity);
  delay(5000);
}}
"""


def _generic_heartbeat(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    return f"""// Auto-generated scaffold for {build_id}
// Modules: {", ".join(modules)}

void setup() {{
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}}

void loop() {{
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  Serial.println(F("{build_id}: tick"));
  delay(1000);
}}
"""


def _smart_relay_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    relay = int(pins.get("relay") or pins.get("pump") or 26)
    return f"""// {build_id} — Wi-Fi desk relay stub (bring-up GPIO)
#include <Arduino.h>

const int RELAY_PIN = {relay};

void setup() {{
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  Serial.printf("relay gpio=%d\\n", RELAY_PIN);
}}

void loop() {{
  digitalWrite(RELAY_PIN, HIGH);
  Serial.println(F("relay ON"));
  delay(2000);
  digitalWrite(RELAY_PIN, LOW);
  Serial.println(F("relay OFF"));
  delay(2000);
}}
"""


def _usb_fume_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    fan = int(pins.get("fan") or pins.get("pump") or 25)
    return f"""// {build_id} — USB fume extractor MOSFET/PWM stub
#include <Arduino.h>

const int FAN_PIN = {fan};

void setup() {{
  Serial.begin(115200);
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);
}}

void loop() {{
  digitalWrite(FAN_PIN, HIGH);
  Serial.printf("fan gpio=%d ON\\n", FAN_PIN);
  delay(3000);
  digitalWrite(FAN_PIN, LOW);
  Serial.println(F("fan OFF"));
  delay(2000);
}}
"""


def _pan_tilt_esp32(build_id: str, modules: List[str], pins: Mapping[str, Any]) -> str:
    def _pin(*keys: str, default: int) -> int:
        for key in keys:
            if key in pins and pins[key] is not None:
                return int(pins[key])
        return default

    pan = _pin("servo_pan", "servo1", default=18)
    tilt = _pin("servo_tilt", "servo2", default=19)
    return f"""// {build_id} — dual SG90 pan/tilt (LEDC PWM, no lib required)
#include <Arduino.h>

const int PAN_PIN = {pan};
const int TILT_PIN = {tilt};
const int PWM_FREQ = 50;
const int PWM_RES = 16;
const int PAN_CH = 0;
const int TILT_CH = 1;

void writeServoUs(int channel, int us) {{
  uint32_t duty = (uint32_t)((us / 20000.0) * ((1 << PWM_RES) - 1));
  ledcWrite(channel, duty);
}}

void setup() {{
  Serial.begin(115200);
  ledcSetup(PAN_CH, PWM_FREQ, PWM_RES);
  ledcSetup(TILT_CH, PWM_FREQ, PWM_RES);
  ledcAttachPin(PAN_PIN, PAN_CH);
  ledcAttachPin(TILT_PIN, TILT_CH);
  writeServoUs(PAN_CH, 1500);
  writeServoUs(TILT_CH, 1500);
  Serial.printf("pan=%d tilt=%d\\n", PAN_PIN, TILT_PIN);
}}

void loop() {{
  writeServoUs(PAN_CH, 1200);
  writeServoUs(TILT_CH, 1200);
  delay(800);
  writeServoUs(PAN_CH, 1800);
  writeServoUs(TILT_CH, 1800);
  delay(800);
}}
"""


_BUILD_SKETCHES: Dict[str, SketchFn] = {
    "automatic_plant_watering": _plant_watering_esp32,
    "automatic_plant_watering_usb": _plant_watering_esp32,
    "plotter_motion_stage": _plotter_arduino,
    "camera_ir_light_or_sensor_mount": _camera_esp32,
    "small_audio_amp_box": _audio_esp32,
    "robot_drive_base": _robot_arduino,
    "smart_relay_box": _smart_relay_esp32,
    "usb_fume_extractor": _usb_fume_esp32,
    "inspection_motion_fixture": _pan_tilt_esp32,
    "sensor_logger": lambda bid, mods, pins: _dht22_esp32_sketch(bid, mods, pins)
    if "dht22" in " ".join(mods).lower()
    else _generic_heartbeat(bid, mods, pins),
}


def _mcu_family(modules: List[str]) -> str:
    joined = " ".join(modules).lower()
    if "esp32" in joined or "esp32-cam" in joined:
        return "esp32"
    if "pico" in joined or "rpi-pico" in joined:
        return "pico"
    if "arduino" in joined:
        return "arduino"
    return "generic"


def _pico_sketch(build_id: str, modules: List[str]) -> str:
    return f"""# {build_id}
from machine import Pin
import time

led = Pin("LED", Pin.OUT)
while True:
    led.toggle()
    print("{build_id}: tick")
    time.sleep(1)
"""


def generate_firmware_from_salvage(
    *,
    build_id: str,
    bringup_card: Mapping[str, Any],
    module_ids: List[str],
    goal: str = "",
) -> Dict[str, Any]:
    """Starter sketch using bring-up GPIO assignments (salvage path without KiCad graph)."""
    family = _mcu_family(module_ids)
    pins = _pins_from_bringup(bringup_card, module_ids)
    goal_l = goal.lower()
    generator = "bringup_card"
    sketch_fn = _BUILD_SKETCHES.get(build_id)

    if family == "pico":
        body = _pico_sketch(build_id, module_ids)
        filename = f"{build_id}_main.py"
    elif sketch_fn is not None:
        body = sketch_fn(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
        generator = "catalog_sketch+bringup_pins"
    elif "soil" in " ".join(module_ids) and pins.get("pump") is not None:
        body = _plant_watering_esp32(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    elif "dht22" in module_ids:
        body = _dht22_esp32_sketch(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    elif pins.get("servo_pan") is not None or "sg90" in " ".join(module_ids).lower():
        body = _pan_tilt_esp32(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    elif pins.get("relay") is not None or any("relay" in m for m in module_ids):
        body = _smart_relay_esp32(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    elif pins.get("fan") is not None or "fume" in goal_l or any("fan" in m for m in module_ids):
        body = _usb_fume_esp32(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    elif "motor" in goal_l or "l298n" in module_ids:
        body = _robot_arduino(build_id, module_ids, pins)
        filename = f"{build_id}.ino"
    else:
        body = _bringup_generic_sketch(build_id, module_ids, pins, bringup_card)
        filename = f"{build_id}.ino"

    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "mcu_family": family,
        "filename": filename,
        "modules": module_ids,
        "pins": pins,
        "source": body,
        "claim_boundary": "Pins derived from bring-up card — verify on bench before upload.",
        "generator": generator,
    }


def _parse_gpio_number(pin_id: str) -> Optional[int]:
    import re

    for pat in (r"GPIO(\d+)", r"GP(\d+)", r"D(\d+)", r"A(\d+)"):
        m = re.search(pat, pin_id, re.I)
        if m:
            return int(m.group(1))
    return None


def _pins_from_bringup(bringup_card: Mapping[str, Any], module_ids: List[str]) -> Dict[str, Any]:
    pins: Dict[str, Any] = {"sourced_from_graph": False, "sourced_from_bringup": True}
    joined = " ".join(module_ids).lower()
    servo_nums: List[int] = []
    for row in bringup_card.get("gpio_assignments") or bringup_card.get("connections") or []:
        fp = str(row.get("from_pin") or "")
        purpose = str(row.get("purpose") or "").lower()
        to_label = str(row.get("to") or row.get("to_role") or "").lower()
        to_pin = str(row.get("to_pin") or "").upper()
        to_role = str(row.get("to_role") or row.get("role") or "").lower()
        num = _parse_gpio_number(fp)
        if num is None:
            # also accept absolute pin fields
            num = _parse_gpio_number(str(row.get("from") or ""))
        if num is None:
            continue
        if to_pin in {"IN1", "IN2", "IN3", "IN4"}:
            pins.setdefault(to_pin.lower(), num)
        if "soil" in joined and ("sns" in purpose or "sensor" in to_label or "soil" in to_label):
            pins.setdefault("soil", num)
        if "pump" in joined or "mosfet" in joined:
            if "control" in purpose or "mosfet" in to_label or "pump" in to_label or "load" in to_label:
                pins.setdefault("pump", num)
        if "dht22" in joined and ("dht" in to_label or "sensor" in to_label):
            pins.setdefault("dht", num)
        if "relay" in joined or "relay" in to_label or to_role in {"rly", "relay"}:
            if "sig" in to_pin.lower() or "control" in purpose or "relay" in to_label or to_role in {"rly", "relay"}:
                pins.setdefault("relay", num)
        if "fan" in joined or "fume" in purpose or "fan" in to_label:
            if "control" in purpose or "mosfet" in to_label or "fan" in to_label or "load" in to_label:
                pins.setdefault("fan", num)
        if (
            to_role in {"svo", "servo", "act"}
            or "servo" in to_label
            or "sg90" in to_label
            or to_pin in {"SIG", "PWM", "PULSE"}
        ):
            if "sg90" in joined or "servo" in joined or to_role in {"svo", "servo", "act"}:
                servo_nums.append(num)
    if servo_nums:
        pins.setdefault("servo_pan", servo_nums[0])
        if len(servo_nums) > 1:
            pins.setdefault("servo_tilt", servo_nums[1])
        # Do NOT invent a second servo pin — wait for graph/bring-up evidence
    return pins


def _bringup_generic_sketch(
    build_id: str,
    module_ids: List[str],
    pins: Mapping[str, Any],
    bringup_card: Mapping[str, Any],
) -> str:
    assigns = []
    for row in bringup_card.get("gpio_assignments") or []:
        assigns.append(f"// {row.get('from')} -> {row.get('to')} ({row.get('purpose')})")
    assign_block = "\n".join(assigns) if assigns else "// See BRINGUP_CARD.md for hookups"
    pump = pins.get("pump")
    if pump is not None:
        return f"""// {build_id} — bring-up actuator stub
#include <Arduino.h>
{assign_block}
const int ACTUATOR_PIN = {pump};
void setup() {{
  Serial.begin(115200);
  pinMode(ACTUATOR_PIN, OUTPUT);
  digitalWrite(ACTUATOR_PIN, LOW);
}}
void loop() {{
  digitalWrite(ACTUATOR_PIN, HIGH);
  delay(500);
  digitalWrite(ACTUATOR_PIN, LOW);
  delay(2000);
}}
"""
    return f"""// {build_id} — generated from bring-up card
#include <Arduino.h>
{assign_block}
void setup() {{ Serial.begin(115200); }}
void loop() {{ Serial.println(F("bringup: wire pins per BRINGUP_CARD")); delay(1000); }}
"""


def generate_firmware_scaffold(
    *,
    build_id: str,
    build_graph: Mapping[str, Any],
) -> Dict[str, Any]:
    nodes = build_graph.get("nodes") or []
    module_ids = [str(n.get("moduleId") or "") for n in nodes if isinstance(n, dict)]
    family = _mcu_family(module_ids)
    pin_map = extract_pins_from_graph(build_graph)
    sketch_fn = _BUILD_SKETCHES.get(build_id, _generic_heartbeat)

    if family == "pico":
        body = _pico_sketch(build_id, module_ids)
        filename = f"{build_id}_main.py"
    elif build_id in _BUILD_SKETCHES:
        # Catalog sketch wins over generic DHT/heartbeat (e.g. fume has DHT + fan)
        body = sketch_fn(build_id, module_ids, pin_map)
        filename = f"{build_id}.ino"
    elif "dht22" in module_ids and any("esp32" in mid for mid in module_ids):
        body = _dht22_esp32_sketch(build_id, module_ids, pin_map)
        filename = f"{build_id}.ino"
    else:
        body = sketch_fn(build_id, module_ids, pin_map)
        filename = f"{build_id}.ino"

    claim = (
        "Pin numbers match canvas wiring."
        if pin_map.get("sourced_from_graph")
        else "Starter scaffold — verify pins against wiring before upload."
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "mcu_family": family,
        "filename": filename,
        "modules": module_ids,
        "pins": pin_map,
        "source": body,
        "claim_boundary": claim,
    }


def write_salvage_firmware(
    *,
    build_id: str,
    salvage_package: Mapping[str, Any],
    goal: str,
    out_dir: str | Path,
) -> Optional[Path]:
    bringup = dict(salvage_package.get("bringup_card") or {})
    module_ids = [
        str(r.get("module_id") or "")
        for r in salvage_package.get("resolved_modules") or []
        if r.get("module_id")
    ]
    if not bringup or not module_ids:
        return None
    payload = generate_firmware_from_salvage(
        build_id=build_id or "salvage_build",
        bringup_card=bringup,
        module_ids=module_ids,
        goal=goal,
    )
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    fw_path = target / "firmware" / str(payload["filename"])
    fw_path.parent.mkdir(parents=True, exist_ok=True)
    fw_path.write_text(str(payload["source"]), encoding="utf-8")
    meta = target / "firmware" / "FIRMWARE_SCAFFOLD.json"
    meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return fw_path


def write_firmware_scaffold(
    *,
    build_id: str,
    build_graph: Mapping[str, Any],
    out_dir: str | Path,
) -> Optional[Path]:
    payload = generate_firmware_scaffold(build_id=build_id, build_graph=build_graph)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    fw_path = target / "firmware" / str(payload["filename"])
    fw_path.parent.mkdir(parents=True, exist_ok=True)
    fw_path.write_text(str(payload["source"]), encoding="utf-8")
    meta = target / "firmware" / "FIRMWARE_SCAFFOLD.json"
    meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        from .integrations.esphome_export import write_esphome_stub

        write_esphome_stub(
            build_id=build_id,
            out_dir=target,
            build_graph=build_graph,
            pins=payload.get("pins"),
            project_name=build_id,
        )
    except Exception:
        pass
    return fw_path
