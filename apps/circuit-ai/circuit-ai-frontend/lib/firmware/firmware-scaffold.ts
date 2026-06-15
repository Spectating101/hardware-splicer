import type { BuildGraph } from "@/lib/rules/safety-rules";
import { extractPinsFromGraph, type GraphPinMap } from "@/lib/firmware/graph-pin-map";

export const FIRMWARE_SCHEMA_VERSION = "hardware_splicer.firmware_scaffold.v1";

export interface FirmwareScaffold {
  schema_version: string;
  build_id: string;
  mcu_family: "esp32" | "arduino" | "pico" | "generic";
  filename: string;
  modules: string[];
  pins: GraphPinMap;
  source: string;
  claim_boundary: string;
}

const DEFAULT_PLANT = { soil: 34, pump: 4 };
const DEFAULT_HC = { trig: 4, echo: 16 };
const DEFAULT_ROBOT = { in1: 2, in2: 3 };

function plantWateringEsp32(buildId: string, pins: GraphPinMap): string {
  const soil = pins.soil ?? DEFAULT_PLANT.soil;
  const pump = pins.pump ?? DEFAULT_PLANT.pump;
  const pinNote = pins.sourcedFromGraph ? "from your wiring" : "default — verify on canvas";
  return `// ${buildId} — soil moisture + pump (${pinNote})
#include <Arduino.h>

const int SOIL_PIN = ${soil};
const int PUMP_PIN = ${pump};
const int DRY_THRESHOLD = 2800;

void setup() {
  Serial.begin(115200);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
}

void loop() {
  int raw = analogRead(SOIL_PIN);
  bool dry = raw > DRY_THRESHOLD;
  digitalWrite(PUMP_PIN, dry ? HIGH : LOW);
  Serial.printf("soil=%d pump=%d\\n", raw, dry ? 1 : 0);
  delay(2000);
}
`;
}

function sensorLoggerEsp32(buildId: string, pins: GraphPinMap): string {
  const data = pins.dhtData;
  if (data !== undefined) {
    return `// ${buildId} — DHT22 on GPIO${data}
#include <Arduino.h>
#include <DHT.h>

#define DHT_PIN ${data}
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  dht.begin();
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) Serial.printf("temp=%.1fC hum=%.1f%%\\n", t, h);
  delay(2000);
}
`;
  }
  const i2c = pins.i2c;
  if (i2c) {
    return `// ${buildId} — I2C env sensor SDA=${i2c.sda} SCL=${i2c.scl}
#include <Arduino.h>
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin(${i2c.sda}, ${i2c.scl});
  Serial.println(F("Mount BME280 library — read temp/humidity over I2C"));
}

void loop() {
  Serial.println(F("sensor tick"));
  delay(2000);
}
`;
  }
  return `// ${buildId} — env sensor logger stub
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  Serial.println(F("Mount DHT or BME library — log temp/humidity every 2s"));
}

void loop() {
  Serial.println(F("sensor tick"));
  delay(2000);
}
`;
}

function roomDisplayStationEsp32(buildId: string, pins: GraphPinMap): string {
  const spi = pins.spi ?? {};
  const dht = pins.dhtData ?? 16;
  const cs = spi.cs ?? 15;
  const rst = spi.rst ?? 2;
  const dc = spi.dc ?? 4;
  const mosi = spi.mosi ?? 23;
  const sck = spi.sck ?? 18;
  return `// ${buildId} — ILI9341 TFT + DHT22 (install TFT_eSPI + DHT)
#include <Arduino.h>
#include <DHT.h>

#define TFT_CS   ${cs}
#define TFT_RST  ${rst}
#define TFT_DC   ${dc}
#define TFT_MOSI ${mosi}
#define TFT_SCK  ${sck}
#define DHT_PIN  ${dht}

DHT dht(DHT_PIN, DHT22);

void setup() {
  Serial.begin(115200);
  dht.begin();
  // Configure TFT_eSPI User_Setup: CS=${cs} DC=${dc} RST=${rst} MOSI=${mosi} SCK=${sck}
  Serial.println(F("Init TFT_eSPI then show temp/humidity on screen"));
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  Serial.printf("display temp=%.1f hum=%.1f\\n", t, h);
  delay(2000);
}
`;
}

function distanceHcSr04(buildId: string, pins: GraphPinMap): string {
  const trig = pins.trig ?? DEFAULT_HC.trig;
  const echo = pins.echo ?? DEFAULT_HC.echo;
  return `// ${buildId} — HC-SR04 distance
#include <Arduino.h>

const int TRIG = ${trig};
const int ECHO = ${echo};

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
}

void loop() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long us = pulseIn(ECHO, HIGH, 30000);
  float cm = us * 0.0343f / 2.0f;
  Serial.printf("distance=%.1f cm\\n", cm);
  delay(500);
}
`;
}

function robotArduino(buildId: string, pins: GraphPinMap): string {
  const in1 = pins.motorIn1 ?? DEFAULT_ROBOT.in1;
  const in2 = pins.motorIn2 ?? DEFAULT_ROBOT.in2;
  return `// ${buildId} — L298N motor over serial
const int IN1 = ${in1};
const int IN2 = ${in2};

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'f') { digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW); }
    if (c == 'b') { digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH); }
    if (c == 's') { digitalWrite(IN1, LOW); digitalWrite(IN2, LOW); }
  }
}
`;
}

function audioEsp32(buildId: string): string {
  return `// ${buildId} — MAX98357A I2S alert stub
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  Serial.println(F("Wire I2S BCLK/LRC/DIN to MAX98357A"));
}

void loop() {
  Serial.println(F("audio alert tick"));
  delay(1000);
}
`;
}

function genericHeartbeat(buildId: string, modules: string[]): string {
  return `// Auto-generated scaffold for ${buildId}
// Modules: ${modules.join(", ")}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  Serial.println(F("${buildId}: tick"));
  delay(1000);
}
`;
}

function picoSketch(buildId: string): string {
  return `# ${buildId}
from machine import Pin
import time

led = Pin("LED", Pin.OUT)
while True:
    led.toggle()
    print("${buildId}: tick")
    time.sleep(1)
`;
}

function mcuFamily(modules: string[]): FirmwareScaffold["mcu_family"] {
  const joined = modules.join(" ").toLowerCase();
  if (/esp32/.test(joined)) return "esp32";
  if (/pico|rpi-pico/.test(joined)) return "pico";
  if (/arduino|atmega/.test(joined)) return "arduino";
  return "generic";
}

/** Guess catalog build id from what's on the canvas. */
export function inferBuildIdFromGraph(graph: BuildGraph): string {
  const ids = new Set(graph.nodes.map((n) => n.moduleId));
  if (ids.has("soil_moisture") && (ids.has("mosfet-irlz44n") || ids.has("water_pump_5v"))) {
    return "automatic_plant_watering";
  }
  if ((ids.has("ili9341_tft") || ids.has("st7735_tft"))
    && (ids.has("dht22") || ids.has("bme280"))) {
    return "room_display_station";
  }
  if (ids.has("ili9341_tft") || ids.has("st7735_tft")) return "room_display_station";
  if (ids.has("dht22") || ids.has("bme280") || ids.has("ds18b20")) return "sensor_logger";
  if (ids.has("hc-sr04")) return "sensor_logger";
  if (ids.has("l298n")) return "robot_drive_base";
  if (ids.has("max98357a-i2s-amp")) return "small_audio_amp_box";
  if (ids.has("cooling_fan_5v") && ids.has("mosfet-irlz44n")) return "usb_fume_extractor";
  if (ids.has("relay-1ch-5v")) return "smart_relay_box";
  return "generic_low_voltage_build";
}

export function generateFirmwareScaffold(
  buildId: string,
  graph: BuildGraph,
): FirmwareScaffold {
  const modules = graph.nodes.map((n) => n.moduleId);
  const family = mcuFamily(modules);
  const pins = extractPinsFromGraph(graph);

  let body: string;
  let filename: string;

  if (family === "pico") {
    body = picoSketch(buildId);
    filename = `${buildId}_main.py`;
  } else if (buildId === "room_display_station") {
    body = roomDisplayStationEsp32(buildId, pins);
    filename = `${buildId}.ino`;
  } else if (buildId === "automatic_plant_watering") {
    body = plantWateringEsp32(buildId, pins);
    filename = `${buildId}.ino`;
  } else if (buildId === "sensor_logger") {
    body = sensorLoggerEsp32(buildId, pins);
    filename = `${buildId}.ino`;
  } else if (buildId === "robot_drive_base") {
    body = robotArduino(buildId, pins);
    filename = `${buildId}.ino`;
  } else if (buildId === "small_audio_amp_box") {
    body = audioEsp32(buildId);
    filename = `${buildId}.ino`;
  } else if (modules.includes("hc-sr04")) {
    body = distanceHcSr04(buildId, pins);
    filename = `${buildId}.ino`;
  } else {
    body = genericHeartbeat(buildId, modules);
    filename = `${buildId}.ino`;
  }

  const claim = pins.sourcedFromGraph
    ? "Starter scaffold — pin numbers match your canvas wiring; still verify before upload."
    : "Starter scaffold — pin numbers are defaults; match them to your wiring before upload.";

  return {
    schema_version: FIRMWARE_SCHEMA_VERSION,
    build_id: buildId,
    mcu_family: family,
    filename,
    modules,
    pins,
    source: body,
    claim_boundary: claim,
  };
}
