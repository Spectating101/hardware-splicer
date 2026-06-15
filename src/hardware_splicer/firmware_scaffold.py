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
    return f"""// {build_id} — A4988 STEP/DIR + limit switches
const int STEP_PIN = 2;
const int DIR_PIN = 3;
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
    return f"""// {build_id} — L298N serial motor commands
const int IN1 = 2;
const int IN2 = 3;

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


_BUILD_SKETCHES: Dict[str, SketchFn] = {
    "automatic_plant_watering": _plant_watering_esp32,
    "automatic_plant_watering_usb": _plant_watering_esp32,
    "plotter_motion_stage": _plotter_arduino,
    "camera_ir_light_or_sensor_mount": _camera_esp32,
    "small_audio_amp_box": _audio_esp32,
    "robot_drive_base": _robot_arduino,
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
    return fw_path
