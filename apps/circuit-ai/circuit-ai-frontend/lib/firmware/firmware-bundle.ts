import type { BuildGraph } from "@/lib/rules/safety-rules";
import { extractPinsFromGraph, type GraphPinMap } from "@/lib/firmware/graph-pin-map";
import { buildZipStore } from "@/lib/firmware/zip-store";

export interface FirmwareBundle {
  zipName: string;
  primaryFile: string;
  files: Record<string, string>;
  installSteps: string[];
}

function readme(buildId: string, steps: string[]): string {
  return `Hardware Splicer — ${buildId.replace(/_/g, " ")}
================================

${steps.join("\n")}

Pins match your Circuit.AI canvas wiring. Open this folder in VS Code with the
PlatformIO extension, then click Upload. Serial monitor: 115200 baud.
`;
}

function platformioEsp32(
  libDeps: string[],
  buildFlags: string[] = [],
): string {
  const deps = libDeps.length ? libDeps.map((d) => `  ${d}`).join("\n") : "  ; none";
  const flags = buildFlags.length
    ? `\nbuild_flags =\n${buildFlags.map((f) => `  ${f}`).join("\n")}`
    : "";
  return `[platformio]
default_envs = esp32dev

[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
${deps}${flags}
`;
}

function tftUserSetup(pins: GraphPinMap): string {
  const spi = pins.spi ?? {};
  const cs = spi.cs ?? 15;
  const rst = spi.rst ?? 2;
  const dc = spi.dc ?? 4;
  const mosi = spi.mosi ?? 23;
  const sck = spi.sck ?? 18;
  return `#pragma once
#define USER_SETUP_LOADED 1
#define ILI9341_DRIVER
#define TFT_WIDTH 240
#define TFT_HEIGHT 320
#define TFT_MOSI ${mosi}
#define TFT_SCLK ${sck}
#define TFT_CS   ${cs}
#define TFT_DC   ${dc}
#define TFT_RST  ${rst}
#define LOAD_GLCD
#define SMOOTH_FONT
`;
}

function plantMain(pins: GraphPinMap): string {
  const soil = pins.soil ?? 34;
  const pump = pins.pump ?? 4;
  return `#include <Arduino.h>

const int SOIL_PIN = ${soil};
const int PUMP_PIN = ${pump};
const int DRY_THRESHOLD = 2800;

void setup() {
  Serial.begin(115200);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
  Serial.println("Plant watering — dry soil turns pump ON");
}

void loop() {
  int raw = analogRead(SOIL_PIN);
  bool dry = raw > DRY_THRESHOLD;
  digitalWrite(PUMP_PIN, dry ? HIGH : LOW);
  Serial.printf("soil=%d pump=%s\\n", raw, dry ? "ON" : "off");
  delay(2000);
}
`;
}

function dhtLoggerMain(pins: GraphPinMap): string {
  const data = pins.dhtData ?? 4;
  return `#include <Arduino.h>
#include <DHT.h>

#define DHT_PIN ${data}
DHT dht(DHT_PIN, DHT22);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("DHT22 logger");
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) Serial.printf("temp=%.1fC hum=%.1f%%\\n", t, h);
  else Serial.println("DHT read failed — check wiring");
  delay(2000);
}
`;
}

function bmeLoggerMain(pins: GraphPinMap): string {
  const sda = pins.i2c?.sda ?? 21;
  const scl = pins.i2c?.scl ?? 22;
  return `#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

Adafruit_BME280 bme;
#define SDA_PIN ${sda}
#define SCL_PIN ${scl}

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  if (!bme.begin(0x76)) {
    Serial.println("BME280 not found — try 0x77 or check I2C wires");
    while (1) delay(1000);
  }
  Serial.println("BME280 logger");
}

void loop() {
  Serial.printf("temp=%.1fC hum=%.1f%% press=%.1fhPa\\n",
    bme.readTemperature(), bme.readHumidity(), bme.readPressure() / 100.0f);
  delay(2000);
}
`;
}

function roomDisplayMain(pins: GraphPinMap): string {
  const dht = pins.dhtData ?? 16;
  return `#include <Arduino.h>
#include <DHT.h>
#include <TFT_eSPI.h>
#include <SPI.h>

#define DHT_PIN ${dht}
DHT dht(DHT_PIN, DHT22);
TFT_eSPI tft = TFT_eSPI();

void setup() {
  Serial.begin(115200);
  dht.begin();
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Room monitor", 10, 10, 2);
  Serial.println("TFT + DHT ready");
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  tft.fillRect(0, 40, 240, 80, TFT_BLACK);
  if (!isnan(t)) {
    tft.drawString(String("Temp: ") + String(t, 1) + " C", 10, 50, 2);
    tft.drawString(String("Hum:  ") + String(h, 1) + " %", 10, 75, 2);
    Serial.printf("temp=%.1f hum=%.1f\\n", t, h);
  } else {
    tft.drawString("DHT read error", 10, 50, 2);
  }
  delay(2000);
}
`;
}

function distanceMain(pins: GraphPinMap): string {
  const trig = pins.trig ?? 4;
  const echo = pins.echo ?? 16;
  return `#include <Arduino.h>

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

/** Full upload-ready project (PlatformIO + libraries + pin headers). */
export function buildFirmwareBundle(
  buildId: string,
  graph: BuildGraph,
): FirmwareBundle {
  const pins = extractPinsFromGraph(graph);
  const modules = graph.nodes.map((n) => n.moduleId);
  const hasBme = modules.includes("bme280");
  const hasDht = modules.includes("dht22");
  const hasTft = modules.includes("ili9341_tft") || modules.includes("st7735_tft");
  const hasHc = modules.includes("hc-sr04");

  const files: Record<string, string> = {};
  let installSteps: string[] = [
    "1. Install VS Code + PlatformIO extension (platformio.org).",
    "2. Open this ZIP folder as a PlatformIO project.",
    "3. Connect your board via USB, click Upload (→ arrow).",
  ];

  if (buildId === "room_display_station" || hasTft) {
    files["include/tft_user_setup.h"] = tftUserSetup(pins);
    files["src/main.cpp"] = roomDisplayMain(pins);
    files["platformio.ini"] = platformioEsp32(
      [
        "bodmer/TFT_eSPI@^2.5.43",
        "adafruit/DHT sensor library@^1.4.6",
        "adafruit/Adafruit Unified Sensor@^1.1.14",
      ],
      ["-I include", "-include include/tft_user_setup.h"],
    );
    installSteps = [
      ...installSteps,
      "4. First upload may take a few minutes while libraries download.",
      "5. You should see room temp and humidity on the color screen.",
    ];
    return {
      zipName: `${buildId}-firmware.zip`,
      primaryFile: "src/main.cpp",
      files: { ...files, "README.txt": readme(buildId, installSteps) },
      installSteps,
    };
  }

  if (buildId === "automatic_plant_watering" || modules.includes("soil_moisture")) {
    files["src/main.cpp"] = plantMain(pins);
    files["platformio.ini"] = platformioEsp32([]);
    installSteps.push("4. Serial monitor shows soil reading; pump pin goes HIGH when dry.");
    return {
      zipName: `${buildId}-firmware.zip`,
      primaryFile: "src/main.cpp",
      files: { ...files, "README.txt": readme(buildId, installSteps) },
      installSteps,
    };
  }

  if (hasBme || (buildId === "sensor_logger" && pins.i2c)) {
    files["src/main.cpp"] = bmeLoggerMain(pins);
    files["platformio.ini"] = platformioEsp32([
      "adafruit/Adafruit BME280 Library@^2.2.4",
      "adafruit/Adafruit Unified Sensor@^1.1.14",
    ]);
    installSteps.push("4. Serial monitor prints temperature, humidity, and pressure.");
    return {
      zipName: `${buildId}-firmware.zip`,
      primaryFile: "src/main.cpp",
      files: { ...files, "README.txt": readme(buildId, installSteps) },
      installSteps,
    };
  }

  if (hasDht || buildId === "sensor_logger") {
    files["src/main.cpp"] = dhtLoggerMain(pins);
    files["platformio.ini"] = platformioEsp32([
      "adafruit/DHT sensor library@^1.4.6",
      "adafruit/Adafruit Unified Sensor@^1.1.14",
    ]);
    installSteps.push("4. Serial monitor prints temperature and humidity every 2 seconds.");
    return {
      zipName: `${buildId}-firmware.zip`,
      primaryFile: "src/main.cpp",
      files: { ...files, "README.txt": readme(buildId, installSteps) },
      installSteps,
    };
  }

  if (hasHc) {
    files["src/main.cpp"] = distanceMain(pins);
    files["platformio.ini"] = platformioEsp32([]);
    installSteps.push("4. Serial monitor prints distance in centimeters.");
    return {
      zipName: `${buildId}-firmware.zip`,
      primaryFile: "src/main.cpp",
      files: { ...files, "README.txt": readme(buildId, installSteps) },
      installSteps,
    };
  }

  files["src/main.cpp"] = `#include <Arduino.h>
void setup() { Serial.begin(115200); pinMode(LED_BUILTIN, OUTPUT); }
void loop() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  Serial.println("${buildId}: heartbeat");
  delay(1000);
}
`;
  files["platformio.ini"] = platformioEsp32([]);
  return {
    zipName: `${buildId}-firmware.zip`,
    primaryFile: "src/main.cpp",
    files: { ...files, "README.txt": readme(buildId, installSteps) },
    installSteps,
  };
}

export function downloadFirmwareBundle(bundle: FirmwareBundle): void {
  const blob = buildZipStore(bundle.files);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = bundle.zipName;
  a.click();
  URL.revokeObjectURL(url);
}
