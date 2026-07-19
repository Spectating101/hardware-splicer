// KiCad footprint names, body envelopes, and pad positions (local mm from center).
// Sync footprint names with hardware_splicer/bom_generator.py _PART_HINTS.

import type { ModuleSpec } from "./module-library";

const P = 2.54;

export type ModulePadDef = { pinId: string; x: number; y: number };

export type ModuleFootprintMeta = {
  kicadFootprint: string;
  bodyMm: { w: number; h: number };
  pads?: ModulePadDef[];
};

function dualCol(left: string[], right: string[], xSpan = P * 4): ModulePadDef[] {
  const rows = Math.max(left.length, right.length);
  const y0 = -((rows - 1) * P) / 2;
  const xL = -xSpan / 2;
  const xR = xSpan / 2;
  const pads: ModulePadDef[] = [];
  for (let i = 0; i < left.length; i++) pads.push({ pinId: left[i], x: xL, y: y0 + i * P });
  for (let i = 0; i < right.length; i++) pads.push({ pinId: right[i], x: xR, y: y0 + i * P });
  return pads;
}

function row(pinIds: string[], y = 0, x0 = 0, pitch = P): ModulePadDef[] {
  const span = (pinIds.length - 1) * pitch;
  const start = x0 - span / 2;
  return pinIds.map((pinId, i) => ({ pinId, x: start + i * pitch, y }));
}

function quad(inPos: [string, string], outPos: [string, string], hw = 5, hh = 3): ModulePadDef[] {
  return [
    { pinId: inPos[0], x: -hw, y: -hh },
    { pinId: inPos[1], x: -hw, y: hh },
    { pinId: outPos[0], x: hw, y: -hh },
    { pinId: outPos[1], x: hw, y: hh },
  ];
}

export const MODULE_FOOTPRINTS: Record<string, ModuleFootprintMeta> = {
  "dc-barrel-12v": {
    kicadFootprint: "Connector:BarrelJack_CUI_PJ-002A",
    bodyMm: { w: 10, h: 10 },
    pads: row(["V+", "GND"], 0, 0, 3.5),
  },
  "usb-power-5v": {
    kicadFootprint: "Connector:USB-MICRO-POWER",
    bodyMm: { w: 8, h: 7 },
    pads: row(["V+", "GND"], -2, 0, 2.5),
  },
  "esp32-devkit": {
    kicadFootprint: "Module:ESP32-WROOM-32",
    bodyMm: { w: 26, h: 50 },
    pads: dualCol(
      ["VIN", "GND", "GPIO4", "GPIO16", "GPIO17"],
      ["3V3", "GPIO2", "GPIO21", "GPIO22", "GPIO34"],
      P * 5,
    ),
  },
  "arduino-nano": {
    kicadFootprint: "Module:Arduino_Nano",
    bodyMm: { w: 18, h: 45 },
    pads: dualCol(["VIN", "GND", "D2", "D3", "A0"], ["5V", "3V3", "A4", "A5"], P * 7),
  },
  "rpi-pico": {
    kicadFootprint: "Module:RPi_Pico",
    bodyMm: { w: 21, h: 51 },
    pads: dualCol(["VSYS", "GND", "GP0", "GP4", "GP26"], ["VBUS", "3V3", "GP1", "GP5"], P * 10),
  },
  "soil_moisture": {
    kicadFootprint: "Sensor:SOIL-MOISTURE-3PIN",
    bodyMm: { w: 20, h: 12 },
    pads: row(["VCC", "GND", "A0", "D0"], 4, 0, P),
  },
  "bme280": {
    kicadFootprint: "Sensor:BME280-BREAKOUT",
    bodyMm: { w: 12, h: 10 },
    pads: row(["VCC", "GND", "SCL", "SDA"], 0, 0, P),
  },
  "dht22": {
    kicadFootprint: "Sensor:DHT22-4PIN",
    bodyMm: { w: 15, h: 12 },
    pads: row(["VCC", "DATA", "NC", "GND"], 0, 0, P),
  },
  "hc-sr04": {
    kicadFootprint: "Sensor:HC-SR04",
    bodyMm: { w: 45, h: 20 },
    pads: row(["VCC", "TRIG", "ECHO", "GND"], 0, 0, P * 2),
  },
  "buck-mp1584": {
    kicadFootprint: "Power:BUCK-MP1584-MODULE",
    bodyMm: { w: 17, h: 11 },
    pads: quad(["IN+", "IN-"], ["OUT+", "OUT-"], 6, 3.5),
  },
  "buck-lm2596": {
    kicadFootprint: "Power:BUCK-LM2596-MODULE",
    bodyMm: { w: 43, h: 21 },
    pads: quad(["IN+", "IN-"], ["OUT+", "OUT-"], 14, 6),
  },
  "ldo-ams1117-3v3": {
    kicadFootprint: "Power:AMS1117-3V3-MODULE",
    bodyMm: { w: 12, h: 10 },
    pads: row(["VIN", "GND", "VOUT"], 0, 0, P),
  },
  "ldo-ams1117-5v": {
    kicadFootprint: "Power:AMS1117-5V-MODULE",
    bodyMm: { w: 12, h: 10 },
    pads: row(["VIN", "GND", "VOUT"], 0, 0, P),
  },
  "tp4056": {
    kicadFootprint: "Power:TP4056-CHARGER",
    bodyMm: { w: 27, h: 17 },
    pads: [
      ...row(["IN+", "IN-"], -5, -6, P * 2),
      ...row(["BAT+", "BAT-"], 5, -6, P * 2),
      ...row(["OUT+", "OUT-"], 0, 6, P * 2),
    ],
  },
  "mosfet-irlz44n": {
    kicadFootprint: "Driver:MOSFET-LOGIC-MODULE",
    bodyMm: { w: 33, h: 24 },
    pads: [
      { pinId: "VIN", x: -11, y: -7 },
      { pinId: "VIN-", x: -11, y: 7 },
      { pinId: "SIG", x: -2, y: 7 },
      { pinId: "GND", x: -2, y: -7 },
      { pinId: "VOUT+", x: 11, y: -7 },
      { pinId: "VOUT-", x: 11, y: 7 },
    ],
  },
  "mosfet-irf520": {
    kicadFootprint: "Driver:MOSFET-IRF520-MODULE",
    bodyMm: { w: 33, h: 24 },
    pads: [
      { pinId: "VIN", x: -11, y: -7 },
      { pinId: "VIN-", x: -11, y: 7 },
      { pinId: "SIG", x: -2, y: 7 },
      { pinId: "GND", x: -2, y: -7 },
      { pinId: "VOUT+", x: 11, y: -7 },
      { pinId: "VOUT-", x: 11, y: 7 },
    ],
  },
  "relay-1ch-5v": {
    kicadFootprint: "Driver:RELAY-1CH-5V",
    bodyMm: { w: 50, h: 26 },
    pads: [
      ...row(["VCC", "GND", "IN"], -6, -8, P),
      ...row(["COM", "NO", "NC"], 6, 8, P),
    ],
  },
  "l298n": {
    kicadFootprint: "Driver:L298N-HBRIDGE",
    bodyMm: { w: 43, h: 43 },
    pads: [
      { pinId: "VCC", x: -14, y: -10 },
      { pinId: "GND", x: -14, y: 10 },
      { pinId: "5V", x: -5, y: -10 },
      { pinId: "IN1", x: -5, y: -2 },
      { pinId: "IN2", x: -5, y: 4 },
      { pinId: "IN3", x: -5, y: 10 },
      { pinId: "IN4", x: -5, y: 16 },
      { pinId: "OUT1", x: 14, y: -12 },
      { pinId: "OUT2", x: 14, y: -4 },
      { pinId: "OUT3", x: 14, y: 4 },
      { pinId: "OUT4", x: 14, y: 12 },
    ],
  },
  "sg90": {
    kicadFootprint: "Actuator:SG90-SERVO",
    bodyMm: { w: 23, h: 12 },
    pads: row(["VCC", "GND", "SIG"], -8, 0, P),
  },
  "ssd1306-128x64": {
    kicadFootprint: "Display:SSD1306-OLED",
    bodyMm: { w: 27, h: 27 },
    pads: row(["VCC", "GND", "SCL", "SDA"], 10, 0, P),
  },
  "ch340-usb-ttl": {
    kicadFootprint: "Interface:USB-TTL-CH340",
    bodyMm: { w: 17, h: 32 },
    pads: row(["VCC", "GND", "TX", "RX"], 0, 0, P),
  },
  "mini-pump-5v": {
    kicadFootprint: "Actuator:PUMP-5V-MINI",
    bodyMm: { w: 24, h: 18 },
    pads: row(["V+", "GND"], 0, 0, P * 2),
  },
  "level-shifter-4ch": {
    kicadFootprint: "Interface:LEVEL-SHIFTER-4CH",
    bodyMm: { w: 15, h: 12 },
    pads: row(["LV", "HV", "GND", "LV1", "HV1", "LV2", "HV2"], 0, 0, P),
  },
  "a4988-stepper": {
    kicadFootprint: "Driver:A4988-STEPSTICK",
    bodyMm: { w: 20, h: 15 },
    pads: row(["VDD", "GND_LOGIC", "STEP", "DIR", "EN", "VMOT", "GND_MOTOR"], 0, 0, P * 1.4),
  },
  "max98357a-i2s-amp": {
    kicadFootprint: "Driver:MAX98357A-I2S",
    bodyMm: { w: 18, h: 12 },
    pads: row(["VIN", "GND", "BCLK", "LRC", "DIN", "SD", "SPK+", "SPK-"], 0, 0, P),
  },
  "limit-switch-3pin": {
    kicadFootprint: "Sensor:LIMIT-SWITCH-3PIN",
    bodyMm: { w: 20, h: 10 },
    pads: row(["VCC", "GND", "SIG"], 0, 0, P),
  },
  "esp32-cam-module": {
    kicadFootprint: "Module:ESP32-CAM",
    bodyMm: { w: 32, h: 48 },
    pads: dualCol(
      ["5V", "GND", "GPIO12", "GPIO13"],
      ["GPIO14", "GPIO15", "U0T", "U0R"],
      P * 6,
    ),
  },
};

export function resolveModuleFootprint(moduleId: string): string {
  return MODULE_FOOTPRINTS[moduleId]?.kicadFootprint ?? `Circuit.AI:${moduleId}`;
}

export function resolveModuleBodyMm(moduleId: string): { w: number; h: number } | null {
  return MODULE_FOOTPRINTS[moduleId]?.bodyMm ?? null;
}

export function resolveModulePads(moduleId: string, spec?: ModuleSpec): ModulePadDef[] | null {
  const custom = MODULE_FOOTPRINTS[moduleId]?.pads;
  if (custom?.length) return custom;
  if (!spec?.pins?.length) return null;
  const half = Math.ceil(spec.pins.length / 2);
  return dualCol(
    spec.pins.slice(0, half).map((p) => p.id),
    spec.pins.slice(half).map((p) => p.id),
  );
}

export function boundsFromPads(pads: ModulePadDef[], margin = 3): { w: number; h: number } {
  if (!pads.length) return { w: 10, h: 10 };
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const pad of pads) {
    minX = Math.min(minX, pad.x);
    maxX = Math.max(maxX, pad.x);
    minY = Math.min(minY, pad.y);
    maxY = Math.max(maxY, pad.y);
  }
  return {
    w: Math.max(maxX - minX + margin * 2, 8),
    h: Math.max(maxY - minY + margin * 2, 8),
  };
}
