// salvage_splice_planner.plan() -> BuildGraph translator.
//
// The salvage backend (src/intelligence/salvage_splice_planner.py) emits a
// rich plan in CAPABILITY vocabulary (motor_or_load, power, controller, …)
// with a recommended_build_id from a fixed BUILD_CATALOG of 14 products.
// The /build forward pipeline (router + DRC + KiCad export + Gerber/DFM)
// consumes a BuildGraph in MODULE-LIBRARY vocabulary (esp32-devkit,
// buck-lm2596, sg90, …) with pin-level wires.
//
// This module is the missing bridge: one recipe per catalog id, hand-mapped
// to a concrete module composition with pin-accurate wiring. Output drops
// straight into the existing buildGraphToGeometry -> runDrc -> serializer
// chain, closing the loop "junk in -> splice plan -> manufacturable board".
//
// Pure, deterministic, no deps. Pin names match lib/modules/module-library.

import type { BuildGraph } from "@/lib/rules/safety-rules";

type Wire = { from: { role: string; pin: string }; to: { role: string; pin: string } };
type Recipe = {
  modules: Array<{ role: string; moduleId: string }>;
  wires: Wire[];
  /** Notes the translator surfaces (substitutions, library gaps). */
  notes?: string[];
};

// Building blocks for common wire patterns.
const powerChain = (
  src: string, sPlus: string, sMinus: string,
  load: string, lPos: string, lNeg: string,
): Wire[] => [
  { from: { role: src, pin: sPlus }, to: { role: load, pin: lPos } },
  { from: { role: src, pin: sMinus }, to: { role: load, pin: lNeg } },
];

const i2cBus = (
  ctrl: string, sda: string, scl: string, vcc: string, gnd: string,
  dev: string,
): Wire[] => [
  { from: { role: ctrl, pin: vcc }, to: { role: dev, pin: "VCC" } },
  { from: { role: ctrl, pin: gnd }, to: { role: dev, pin: "GND" } },
  { from: { role: ctrl, pin: sda }, to: { role: dev, pin: "SDA" } },
  { from: { role: ctrl, pin: scl }, to: { role: dev, pin: "SCL" } },
];

// One recipe per BUILD_CATALOG entry in salvage_splice_planner.BUILD_CATALOG.
// Roles are local labels; module ids are canonical library ids.
//
// Design discipline learned from a strict per-recipe safety audit:
//   • MCU-based recipes do NOT carry an on-board regulator — the MCU is
//     powered via its USB jack, then its 3V3/5V output feeds peripherals.
//     This avoids cascading a settable buck's upper-bound voltage (30V) onto
//     a 5V MCU input pin (the safety engine correctly refuses that).
//   • Recipes that mix a high-current peripheral (sg90 servo, 200mA+) with
//     an MCU give the peripheral its OWN buck rail — never the MCU's 5V pin.
//   • 3.3V-logic peripherals (ssd1306, bme280) paired with an MCU use the
//     rpi-pico (3.3V logic) instead of arduino-nano (5V logic) to avoid a
//     real level mismatch.
const RECIPES: Record<string, Recipe> = {
  // USB-in -> 3.3V breakout, with optional Li-ion charging from the same
  // 5V rail. tp4056.IN+ (5V) sits cleanly in the LDO's 4.75-15V input range
  // and both modules share GND.
  bench_power_adapter: {
    modules: [
      { role: "usb", moduleId: "tp4056" },
      { role: "ldo", moduleId: "ldo-ams1117-3v3" },
    ],
    wires: [
      { from: { role: "usb", pin: "IN+" }, to: { role: "ldo", pin: "VIN" } },
      { from: { role: "usb", pin: "IN-" }, to: { role: "ldo", pin: "GND" } },
    ],
    notes: [
      "USB-C/microUSB on TP4056 IN+/IN-; 3.3V/1A on LDO VOUT.",
      "Optional Li-ion cell on TP4056 BAT+/BAT- for charging.",
    ],
  },

  usb_fume_extractor: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "drv", moduleId: "mosfet-irf520" },
    ],
    wires: [
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["Motor load wires to VOUT+/VOUT- of the driver."],
  },

  indicator_or_task_light: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "drv", moduleId: "mosfet-irf520" },
    ],
    wires: [
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["LED wires from VOUT+ to VOUT- with appropriate series resistor."],
  },

  low_voltage_motor_test_jig: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "drv", moduleId: "mosfet-irf520" },
    ],
    wires: [
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["Add a manual switch on SIG for benchtop on/off."],
  },

  // MCU is USB-powered; its 5V output runs the relay coil.
  smart_relay_box: {
    modules: [
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "rly", moduleId: "relay-1ch-5v" },
    ],
    wires: [
      { from: { role: "mcu", pin: "5V" }, to: { role: "rly", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "rly", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "rly", pin: "IN" } },
    ],
    notes: ["Power the MCU via USB. Add a fly-back diode if switching inductive loads."],
  },

  // ESP32 USB-powered; its 3V3 output runs the I2C sensor directly.
  sensor_logger: {
    modules: [
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
    notes: ["Power the ESP32 via USB; 3V3 rail feeds the BME280 directly."],
  },

  network_status_indicator: {
    modules: [
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "ui", moduleId: "ssd1306-128x64" },
    ],
    wires: [
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "ui"),
    ],
    notes: ["ESP32 supplies the wireless interface natively; USB-powered."],
  },

  // Pico (3.3V logic) matches ssd1306 directly — no level shifter. Servo
  // VCC is intentionally OFF-board: a 200mA+ servo must not share an MCU
  // rail and the library has no fixed-output 5V regulator. Bench connects
  // sg90 VCC to a 5V supply; we wire its signal + ground only.
  inspection_motion_fixture: {
    modules: [
      { role: "mcu", moduleId: "rpi-pico" },
      { role: "ui", moduleId: "ssd1306-128x64" },
      { role: "svo", moduleId: "sg90" },
    ],
    wires: [
      ...i2cBus("mcu", "GP4", "GP5", "3V3", "GND", "ui"),
      { from: { role: "mcu", pin: "GP0" }, to: { role: "svo", pin: "SIG" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
    ],
    notes: [
      "Power the SG90 VCC from a SEPARATE 5V bench supply (NOT the MCU rail).",
      "Pico is USB-powered; signal/ground share with the servo via a single GND tie.",
    ],
  },

  // HC-SR04 is 5V-only; arduino-nano matches without level shift. Servo VCC
  // stays off-board for the same reason as inspection_motion_fixture.
  plotter_motion_stage: {
    modules: [
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "limit", moduleId: "hc-sr04" },
      { role: "svo", moduleId: "sg90" },
    ],
    wires: [
      { from: { role: "mcu", pin: "5V" }, to: { role: "limit", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "limit", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "limit", pin: "TRIG" } },
      { from: { role: "mcu", pin: "A0" }, to: { role: "limit", pin: "ECHO" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "svo", pin: "SIG" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
    ],
    notes: [
      "Power the SG90 VCC from a SEPARATE 5V bench supply (NOT the Arduino 5V rail).",
      "Arduino is USB-powered.",
    ],
  },

  // L298N motor supply on its own buck; arduino USB-powered, drives IN1/IN2.
  robot_drive_base: {
    modules: [
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "mot_psu", moduleId: "buck-lm2596" },
      { role: "drv", moduleId: "l298n" },
    ],
    wires: [
      { from: { role: "mot_psu", pin: "OUT+" }, to: { role: "drv", pin: "VCC" } },
      { from: { role: "mot_psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "drv", pin: "IN1" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "drv", pin: "IN2" } },
    ],
    notes: [
      "Motor connects to OUT1/OUT2 (external load wiring).",
      "Set the motor buck to your motor's rated voltage. Arduino is USB-powered.",
    ],
  },

  usb_uart_debug_adapter: {
    modules: [
      { role: "adapter", moduleId: "ch340-usb-ttl" },
      { role: "target", moduleId: "arduino-nano" },
    ],
    wires: [
      { from: { role: "adapter", pin: "GND" }, to: { role: "target", pin: "GND" } },
      // CH340 TX -> target RX, CH340 RX -> target TX (crossover).
      // Arduino Nano exposes D2/D3 as generic digital_io; for serial bring-up
      // wire to D2 (RX) and D3 (TX) to keep within library pin set.
      { from: { role: "adapter", pin: "TX" }, to: { role: "target", pin: "D2" } },
      { from: { role: "adapter", pin: "RX" }, to: { role: "target", pin: "D3" } },
    ],
    notes: ["Wire to your target's native UART pins for production use."],
  },

  small_audio_amp_box: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "drv", moduleId: "mosfet-irf520" },
    ],
    wires: [
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: [
      "No discrete audio-amp in the module library — using MOSFET as load driver",
      "Substitute a real Class-D amp (PAM8403 / TPA3110) when adding to the library.",
    ],
  },

  // Tester fixture: arduino reads inputs, CH340 surfaces results over USB serial.
  salvaged_input_panel: {
    modules: [
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "adapter", moduleId: "ch340-usb-ttl" },
    ],
    wires: [
      { from: { role: "adapter", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "adapter", pin: "TX" }, to: { role: "mcu", pin: "D2" } },
      { from: { role: "adapter", pin: "RX" }, to: { role: "mcu", pin: "D3" } },
    ],
    notes: ["Switches/buttons wire to A0 as digital inputs with pull-ups; results read over USB serial."],
  },

  camera_ir_light_or_sensor_mount: {
    modules: [
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
    notes: [
      "ESP32 USB-powered; 3V3 rail feeds the sensor.",
      "Camera/IR-light module not in library — BME280 is a wired stand-in until a camera spec is added.",
    ],
  },
};

export interface SalvagePlanInput {
  target?: { recommended_build_id?: string | null };
  reusable_blocks?: Array<{ id?: string; name?: string; capabilities?: string[]; source?: string }>;
  build_candidates?: Array<{ id?: string; name?: string }>;
}

export interface TranslationResult {
  graph: BuildGraph;
  buildId: string | null;
  notes: string[];
  warnings: string[];
}

/** Convert a salvage splice_plan response into a /build BuildGraph. */
export function splicePlanToBuildGraph(plan: SalvagePlanInput | null | undefined): TranslationResult {
  const warnings: string[] = [];
  const notes: string[] = [];

  const buildId =
    plan?.target?.recommended_build_id ||
    plan?.build_candidates?.[0]?.id ||
    null;

  if (!buildId) {
    warnings.push("Plan has no recommended_build_id (and no build_candidates).");
    return { graph: { nodes: [], wires: [] }, buildId: null, notes, warnings };
  }

  const recipe = RECIPES[buildId];
  if (!recipe) {
    warnings.push(`No translator recipe for build "${buildId}".`);
    return { graph: { nodes: [], wires: [] }, buildId, notes, warnings };
  }

  // Materialize role -> nodeId; build BuildGraph nodes.
  const idOf = new Map<string, string>();
  const nodes = recipe.modules.map((m, i) => {
    const nodeId = `n${i + 1}`;
    idOf.set(m.role, nodeId);
    return { id: nodeId, moduleId: m.moduleId };
  });

  // Resolve wires; drop (with warning) any whose roles aren't present.
  const wires = recipe.wires.flatMap((w, i) => {
    const from = idOf.get(w.from.role);
    const to = idOf.get(w.to.role);
    if (!from || !to) {
      warnings.push(`Wire ${i} drops unknown role: ${w.from.role}/${w.to.role}.`);
      return [];
    }
    return [{
      id: `w${i + 1}`,
      from: { nodeId: from, pinId: w.from.pin },
      to: { nodeId: to, pinId: w.to.pin },
    }];
  });

  if (recipe.notes) notes.push(...recipe.notes);

  const reused = plan?.reusable_blocks?.filter(Boolean) ?? [];
  if (reused.length > 0) {
    notes.push(
      `Harvest from inventory: ${reused
        .map((b) => b.name || b.id)
        .filter(Boolean)
        .slice(0, 8)
        .join(", ")}`,
    );
  }

  return { graph: { nodes, wires }, buildId, notes, warnings };
}

/** All build ids this translator knows how to materialize. */
export const SUPPORTED_BUILD_IDS = Object.keys(RECIPES).sort();
