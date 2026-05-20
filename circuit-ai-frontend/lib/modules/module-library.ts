// Curated catalog of common salvageable / cheaply-available modules for the
// Build flow. Each module has stable pinout + voltage/current specs so the
// safety rules engine can validate connections client-side without an LLM
// round-trip.

export type PinRole =
  | "power_in"
  | "power_out"
  | "gnd"
  | "digital_io"
  | "digital_in"
  | "digital_out"
  | "analog_in"
  | "pwm"
  | "uart_tx"
  | "uart_rx"
  | "i2c_sda"
  | "i2c_scl"
  | "spi_mosi"
  | "spi_miso"
  | "spi_sck"
  | "spi_cs"
  | "reset"
  | "other";

export interface ModulePin {
  /** Unique within the module (e.g. "VIN", "GPIO2"). */
  id: string;
  label: string;
  role: PinRole;
  /** Operating voltage for power pins, logic level for IO pins. */
  voltage?: string;
  /** Max sink/source current where meaningful. */
  currentMaxMa?: number;
  /** Free-form note (pull-ups, strap pins, ADC attenuation, etc.). */
  notes?: string;
}

export interface ModuleSpec {
  /** Stable catalog id — used in wiring graphs and KiCad serialization. */
  id: string;
  label: string;
  /** Coarse category for filtering/icons. */
  category: "mcu" | "power" | "sensor" | "display" | "actuator" | "radio" | "interface" | "passive" | "other";
  summary: string;
  /** Logic level (most common). Used by safety rules to flag mismatches. */
  logicVoltage?: 3.3 | 5 | 12;
  /** Input voltage window for the whole module (power_in pins). */
  inputVoltageRange?: [number, number];
  /** Typical quiescent current, mA. */
  typicalCurrentMa?: number;
  pins: ModulePin[];
  /** Safety notes surfaced in inspectors. */
  warnings?: string[];

  // ---- encyclopedia fields (optional, all backward-compatible) ----
  /** Where this entry originated: curated by hand or ingested from a dataset. */
  source?: "curated" | "ingested-component-db" | "ingested-pinout-extract" | "ingested-kb-board" | "ingested-kb-ic" | "ingested-datasheet-pdf";
  /** Manufacturer name (Bosch, NXP, Atmel, etc.). */
  manufacturer?: string;
  /** Canonical part number (e.g. "BME280", "ATmega328P"). */
  partNumber?: string;
  /** Link to the canonical datasheet or vendor product page. */
  datasheetUrl?: string;
  /** Typical hobby/retail price in USD. */
  priceUsd?: number;
  /** Alternative names searches should match (e.g. "Bosch BME280", "BME-280"). */
  aliases?: string[];
}

// A tight v1 library — the 20 modules that cover ~80% of beginner projects.
// Expand from telemetry once the build flow ships.
export const MODULE_LIBRARY: ModuleSpec[] = [
  {
    id: "esp32-devkit",
    label: "ESP32 DevKit",
    category: "mcu",
    summary: "Wi-Fi + BLE microcontroller dev board with USB.",
    logicVoltage: 3.3,
    inputVoltageRange: [5, 5],
    typicalCurrentMa: 150,
    pins: [
      { id: "VIN", label: "VIN", role: "power_in", voltage: "5V" },
      { id: "3V3", label: "3V3", role: "power_out", voltage: "3.3V", currentMaxMa: 600 },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "GPIO2", label: "GPIO2", role: "digital_io", voltage: "3.3V", notes: "Onboard LED on some boards" },
      { id: "GPIO4", label: "GPIO4", role: "digital_io", voltage: "3.3V" },
      { id: "GPIO16", label: "GPIO16 / RX2", role: "uart_rx", voltage: "3.3V" },
      { id: "GPIO17", label: "GPIO17 / TX2", role: "uart_tx", voltage: "3.3V" },
      { id: "GPIO21", label: "GPIO21 / SDA", role: "i2c_sda", voltage: "3.3V" },
      { id: "GPIO22", label: "GPIO22 / SCL", role: "i2c_scl", voltage: "3.3V" },
      { id: "GPIO34", label: "GPIO34", role: "analog_in", voltage: "0-3.3V", notes: "Input-only" },
    ],
    warnings: ["GPIOs are 3.3V logic — do not drive with 5V signals without a level-shifter."],
  },
  {
    id: "arduino-nano",
    label: "Arduino Nano",
    category: "mcu",
    summary: "Classic ATmega328P board, 5V logic, USB.",
    logicVoltage: 5,
    inputVoltageRange: [5, 12],
    typicalCurrentMa: 20,
    pins: [
      { id: "VIN", label: "VIN", role: "power_in", voltage: "7-12V" },
      { id: "5V", label: "5V", role: "power_out", voltage: "5V", currentMaxMa: 500 },
      { id: "3V3", label: "3V3", role: "power_out", voltage: "3.3V", currentMaxMa: 50 },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "D2", label: "D2", role: "digital_io", voltage: "5V" },
      { id: "D3", label: "D3 / PWM", role: "pwm", voltage: "5V" },
      { id: "A0", label: "A0", role: "analog_in", voltage: "0-5V" },
      { id: "A4", label: "A4 / SDA", role: "i2c_sda", voltage: "5V" },
      { id: "A5", label: "A5 / SCL", role: "i2c_scl", voltage: "5V" },
    ],
  },
  {
    id: "rpi-pico",
    label: "Raspberry Pi Pico",
    category: "mcu",
    summary: "RP2040 dev board, 3.3V logic, USB, cheap.",
    logicVoltage: 3.3,
    inputVoltageRange: [1.8, 5.5],
    typicalCurrentMa: 25,
    pins: [
      { id: "VSYS", label: "VSYS", role: "power_in", voltage: "1.8-5.5V" },
      { id: "VBUS", label: "VBUS", role: "power_in", voltage: "5V (from USB)" },
      { id: "3V3", label: "3V3", role: "power_out", voltage: "3.3V", currentMaxMa: 300 },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "GP0", label: "GP0 / UART TX", role: "uart_tx", voltage: "3.3V" },
      { id: "GP1", label: "GP1 / UART RX", role: "uart_rx", voltage: "3.3V" },
      { id: "GP4", label: "GP4 / SDA", role: "i2c_sda", voltage: "3.3V" },
      { id: "GP5", label: "GP5 / SCL", role: "i2c_scl", voltage: "3.3V" },
      { id: "GP26", label: "GP26 / ADC0", role: "analog_in", voltage: "0-3.3V" },
    ],
  },
  {
    id: "buck-lm2596",
    label: "LM2596 buck regulator",
    category: "power",
    summary: "Adjustable step-down: 7-35V in, 1.2-30V out, ~2A.",
    inputVoltageRange: [7, 35],
    typicalCurrentMa: 10,
    pins: [
      { id: "IN+", label: "IN+", role: "power_in", voltage: "7-35V" },
      { id: "IN-", label: "IN-", role: "gnd" },
      { id: "OUT+", label: "OUT+", role: "power_out", voltage: "1.2-30V (adjustable)", currentMaxMa: 2000 },
      { id: "OUT-", label: "OUT-", role: "gnd" },
    ],
    warnings: ["Always set output voltage with a multimeter BEFORE connecting your load."],
  },
  {
    id: "buck-mp1584",
    label: "MP1584 mini buck",
    category: "power",
    summary: "Tiny adjustable buck: 4.5-28V in, 0.8-20V out, ~3A.",
    inputVoltageRange: [4.5, 28],
    pins: [
      { id: "IN+", label: "IN+", role: "power_in", voltage: "4.5-28V" },
      { id: "IN-", label: "IN-", role: "gnd" },
      { id: "OUT+", label: "OUT+", role: "power_out", voltage: "0.8-20V", currentMaxMa: 3000 },
      { id: "OUT-", label: "OUT-", role: "gnd" },
    ],
  },
  {
    id: "boost-mt3608",
    label: "MT3608 boost converter",
    category: "power",
    summary: "Step-up: 2-24V in, up to 28V out, ~2A.",
    inputVoltageRange: [2, 24],
    pins: [
      { id: "IN+", label: "IN+", role: "power_in", voltage: "2-24V" },
      { id: "IN-", label: "IN-", role: "gnd" },
      { id: "OUT+", label: "OUT+", role: "power_out", voltage: "5-28V", currentMaxMa: 2000 },
      { id: "OUT-", label: "OUT-", role: "gnd" },
    ],
  },
  {
    id: "ldo-ams1117-3v3",
    label: "AMS1117 3.3V LDO",
    category: "power",
    summary: "Linear 3.3V regulator, 1A, drops excess as heat.",
    inputVoltageRange: [4.75, 15],
    pins: [
      { id: "VIN", label: "VIN", role: "power_in", voltage: "4.75-15V" },
      { id: "VOUT", label: "VOUT", role: "power_out", voltage: "3.3V", currentMaxMa: 1000 },
      { id: "GND", label: "GND", role: "gnd" },
    ],
    warnings: ["Inefficient at high drop — use a buck for >2V drop @ >200mA."],
  },
  {
    id: "ldo-ams1117-5v",
    label: "AMS1117 5V LDO",
    category: "power",
    summary: "Linear 5V regulator, 1A, drops excess as heat. Use for clean 5V from 7-15V.",
    inputVoltageRange: [7, 15],
    pins: [
      { id: "VIN", label: "VIN", role: "power_in", voltage: "7-15V" },
      { id: "VOUT", label: "VOUT", role: "power_out", voltage: "5V", currentMaxMa: 1000 },
      { id: "GND", label: "GND", role: "gnd" },
    ],
    warnings: [
      "Heatsink required above ~500mA continuous (LDO dissipates Vin-5V across the load current).",
      "For higher efficiency at >500mA, use a fixed-output 5V buck (e.g. R-78E5.0) instead.",
    ],
  },
  {
    id: "tp4056",
    label: "TP4056 Li-ion charger",
    category: "power",
    summary: "Single-cell lithium charger, 1A, USB input.",
    inputVoltageRange: [4.5, 5.5],
    pins: [
      { id: "IN+", label: "IN+", role: "power_in", voltage: "5V" },
      { id: "IN-", label: "IN-", role: "gnd" },
      { id: "BAT+", label: "BAT+", role: "power_out", voltage: "3.0-4.2V", currentMaxMa: 1000 },
      { id: "BAT-", label: "BAT-", role: "gnd" },
      { id: "OUT+", label: "OUT+", role: "power_out", voltage: "battery voltage" },
      { id: "OUT-", label: "OUT-", role: "gnd" },
    ],
    warnings: [
      "Use the protected version (with DW01 chip) — plain TP4056 has NO over-discharge protection and will destroy the cell.",
      "Li-ion cells can vent or ignite if shorted or overcharged.",
    ],
  },
  {
    id: "level-shifter-4ch",
    label: "4-channel level shifter",
    category: "interface",
    summary: "Bidirectional 3.3V ↔ 5V for I2C/UART/SPI.",
    pins: [
      { id: "LV", label: "LV", role: "power_in", voltage: "3.3V" },
      { id: "HV", label: "HV", role: "power_in", voltage: "5V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "LV1", label: "LV1", role: "digital_io", voltage: "3.3V" },
      { id: "HV1", label: "HV1", role: "digital_io", voltage: "5V" },
      { id: "LV2", label: "LV2", role: "digital_io", voltage: "3.3V" },
      { id: "HV2", label: "HV2", role: "digital_io", voltage: "5V" },
    ],
  },
  {
    id: "dht22",
    label: "DHT22 temp/humidity",
    category: "sensor",
    summary: "±0.5°C temperature, ±2% humidity, single-wire.",
    logicVoltage: 3.3,
    inputVoltageRange: [3, 5.5],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "3-5.5V" },
      { id: "DATA", label: "DATA", role: "digital_io", voltage: "logic level", notes: "Needs 4.7k-10k pull-up to VCC" },
      { id: "GND", label: "GND", role: "gnd" },
    ],
  },
  {
    id: "bme280",
    label: "BME280 env sensor",
    category: "sensor",
    summary: "Temperature, humidity, pressure — I2C or SPI.",
    logicVoltage: 3.3,
    inputVoltageRange: [3.3, 3.3],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "3.3V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "SCL", label: "SCL", role: "i2c_scl", voltage: "3.3V" },
      { id: "SDA", label: "SDA", role: "i2c_sda", voltage: "3.3V" },
    ],
    warnings: ["3.3V-only — do NOT power from 5V. Check for breakout boards with onboard regulator if you need 5V tolerance."],
  },
  {
    id: "hc-sr04",
    label: "HC-SR04 ultrasonic",
    category: "sensor",
    summary: "2-400cm range finder, 5V.",
    logicVoltage: 5,
    inputVoltageRange: [5, 5],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "5V" },
      { id: "TRIG", label: "TRIG", role: "digital_in", voltage: "5V" },
      { id: "ECHO", label: "ECHO", role: "digital_out", voltage: "5V", notes: "Use divider or level-shifter for 3.3V MCU" },
      { id: "GND", label: "GND", role: "gnd" },
    ],
  },
  {
    id: "mpu6050",
    label: "MPU6050 IMU",
    category: "sensor",
    summary: "6-axis accelerometer + gyroscope, I2C.",
    logicVoltage: 3.3,
    inputVoltageRange: [3, 5],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "3-5V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "SCL", label: "SCL", role: "i2c_scl", voltage: "3.3V" },
      { id: "SDA", label: "SDA", role: "i2c_sda", voltage: "3.3V" },
    ],
  },
  {
    id: "ssd1306-128x64",
    label: "SSD1306 OLED 128x64",
    category: "display",
    summary: "Monochrome OLED, I2C, ~20mA.",
    logicVoltage: 3.3,
    inputVoltageRange: [3.3, 5],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "3.3-5V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "SCL", label: "SCL", role: "i2c_scl", voltage: "3.3V" },
      { id: "SDA", label: "SDA", role: "i2c_sda", voltage: "3.3V" },
    ],
  },
  {
    id: "relay-1ch-5v",
    label: "1-ch relay 5V",
    category: "actuator",
    summary: "Opto-isolated relay module, up to 250VAC / 10A.",
    logicVoltage: 5,
    inputVoltageRange: [5, 5],
    typicalCurrentMa: 70,
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "5V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "IN", label: "IN", role: "digital_in", voltage: "5V" },
      { id: "COM", label: "COM", role: "other", notes: "Switched common" },
      { id: "NO", label: "NO", role: "other", notes: "Normally-open" },
      { id: "NC", label: "NC", role: "other", notes: "Normally-closed" },
    ],
    warnings: ["If switching mains (>60V AC), isolate the load side completely. Beginners should stick to low-voltage DC."],
  },
  {
    id: "mosfet-irf520",
    label: "IRF520 MOSFET module",
    category: "actuator",
    summary: "Logic-level-ish N-channel switch, up to ~10A / 100V.",
    pins: [
      { id: "VIN", label: "VIN+", role: "power_in", voltage: "load voltage" },
      { id: "VIN-", label: "VIN-", role: "gnd" },
      { id: "SIG", label: "SIG", role: "digital_in", voltage: "5V preferred (3.3V marginal)" },
      { id: "GND", label: "SIG GND", role: "gnd" },
      { id: "VOUT+", label: "VOUT+", role: "power_out" },
      { id: "VOUT-", label: "VOUT-", role: "gnd" },
    ],
    warnings: ["IRF520 is not a true logic-level FET — switches poorly from 3.3V. Prefer IRLZ44N or AO3400 for 3.3V drive."],
  },
  {
    id: "l298n",
    label: "L298N motor driver",
    category: "actuator",
    summary: "Dual H-bridge, up to ~2A/ch. Old, lossy, still cheap.",
    inputVoltageRange: [5, 35],
    pins: [
      { id: "VCC", label: "VCC (motor)", role: "power_in", voltage: "5-35V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "5V", label: "5V (logic)", role: "power_out", voltage: "5V", currentMaxMa: 100 },
      { id: "IN1", label: "IN1", role: "digital_in", voltage: "5V" },
      { id: "IN2", label: "IN2", role: "digital_in", voltage: "5V" },
      { id: "OUT1", label: "OUT1", role: "power_out" },
      { id: "OUT2", label: "OUT2", role: "power_out" },
    ],
    warnings: ["Drops ~2V — inefficient at low motor voltages. Consider DRV8833/TB6612 for 3-12V motors."],
  },
  {
    id: "sg90",
    label: "SG90 servo",
    category: "actuator",
    summary: "Small hobby servo, 180° range, 5V PWM.",
    inputVoltageRange: [4.8, 6],
    typicalCurrentMa: 200,
    pins: [
      { id: "VCC", label: "VCC (red)", role: "power_in", voltage: "4.8-6V" },
      { id: "GND", label: "GND (brown)", role: "gnd" },
      { id: "SIG", label: "SIG (orange)", role: "pwm", voltage: "3.3V or 5V" },
    ],
    warnings: ["Stall current can exceed 600mA — don't power from MCU 5V pin; use a separate 5V supply."],
  },
  {
    id: "nrf24l01",
    label: "nRF24L01+ radio",
    category: "radio",
    summary: "2.4GHz transceiver, SPI, 3.3V only.",
    logicVoltage: 3.3,
    inputVoltageRange: [1.9, 3.6],
    pins: [
      { id: "VCC", label: "VCC", role: "power_in", voltage: "3.3V" },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "CE", label: "CE", role: "digital_out", voltage: "3.3V" },
      { id: "CSN", label: "CSN", role: "spi_cs", voltage: "3.3V" },
      { id: "SCK", label: "SCK", role: "spi_sck", voltage: "3.3V" },
      { id: "MOSI", label: "MOSI", role: "spi_mosi", voltage: "3.3V" },
      { id: "MISO", label: "MISO", role: "spi_miso", voltage: "3.3V" },
    ],
    warnings: ["Power pin is 3.3V-only. Add a 10µF cap across VCC/GND near the module."],
  },
  {
    id: "ch340-usb-ttl",
    label: "CH340 USB-TTL",
    category: "interface",
    summary: "USB serial adapter, 3.3V or 5V selectable.",
    pins: [
      { id: "VCC", label: "VCC", role: "power_out", voltage: "3.3V or 5V (jumper)", currentMaxMa: 300 },
      { id: "GND", label: "GND", role: "gnd" },
      { id: "TX", label: "TX", role: "uart_tx" },
      { id: "RX", label: "RX", role: "uart_rx" },
    ],
  },
];

// Merge auto-ingested encyclopedia entries after the curated set. Curated
// wins on id collisions because it's listed first; the component-DB ingest
// (~87 module-breakouts) is followed by the bare-IC pinout extracts (~12
// op-amps, USB-UART bridges, flash chips) for completeness.
import { INGESTED_MODULES } from "./ingested";
import { INGESTED_PINOUTS } from "./ingested-pinouts";
import { CURATED_EXTENDED } from "./curated-extended";
import { INGESTED_KB } from "./ingested-kb";
import { INGESTED_DATASHEETS } from "./ingested-datasheets";
const _seenIds = new Set(MODULE_LIBRARY.map((m) => m.id));
for (const src of [CURATED_EXTENDED, INGESTED_KB, INGESTED_DATASHEETS, INGESTED_MODULES, INGESTED_PINOUTS]) {
  for (const m of src) {
    if (!_seenIds.has(m.id)) {
      MODULE_LIBRARY.push(m);
      _seenIds.add(m.id);
    }
  }
}

export function findModule(id: string): ModuleSpec | undefined {
  return MODULE_LIBRARY.find((m) => m.id === id);
}

export function findPin(module: ModuleSpec, pinId: string): ModulePin | undefined {
  return module.pins.find((p) => p.id === pinId);
}

/** Convenience: filter by category. */
export function modulesByCategory(category: ModuleSpec["category"]): ModuleSpec[] {
  return MODULE_LIBRARY.filter((m) => m.category === category);
}

/** Search by id, label, partNumber, manufacturer, or aliases — case-insensitive. */
export function searchModules(query: string): ModuleSpec[] {
  const q = query.trim().toLowerCase();
  if (!q) return MODULE_LIBRARY.slice();
  return MODULE_LIBRARY.filter((m) => {
    if (m.id.toLowerCase().includes(q)) return true;
    if (m.label.toLowerCase().includes(q)) return true;
    if (m.partNumber?.toLowerCase().includes(q)) return true;
    if (m.manufacturer?.toLowerCase().includes(q)) return true;
    if (m.aliases?.some((a) => a.toLowerCase().includes(q))) return true;
    return false;
  });
}
