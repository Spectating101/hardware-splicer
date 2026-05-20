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
// Roles are local labels; module ids are the canonical library ids.
const RECIPES: Record<string, Recipe> = {
  bench_power_adapter: {
    modules: [{ role: "psu", moduleId: "buck-lm2596" }],
    wires: [],
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

  smart_relay_box: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "rly", moduleId: "relay-1ch-5v" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      { from: { role: "mcu", pin: "5V" }, to: { role: "rly", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "rly", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "rly", pin: "IN" } },
    ],
  },

  sensor_logger: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
  },

  network_status_indicator: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "ui", moduleId: "ssd1306-128x64" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "ui"),
    ],
    notes: ["ESP32 supplies the wireless interface natively."],
  },

  inspection_motion_fixture: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "svo", moduleId: "sg90" },
      { role: "ui", moduleId: "ssd1306-128x64" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      { from: { role: "mcu", pin: "5V" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "svo", pin: "SIG" } },
      ...i2cBus("mcu", "A4", "A5", "5V", "GND", "ui"),
    ],
  },

  plotter_motion_stage: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "svo", moduleId: "sg90" },
      { role: "limit", moduleId: "hc-sr04" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      { from: { role: "mcu", pin: "5V" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "svo", pin: "SIG" } },
      { from: { role: "mcu", pin: "5V" }, to: { role: "limit", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "limit", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "limit", pin: "TRIG" } },
      // ECHO is a digital_out from the sensor; the Arduino digital input
      // reads it. The library lacks a free digital_in on Nano besides D2/D3
      // — using A0 as a digital input is fine on AVR.
      { from: { role: "mcu", pin: "A0" }, to: { role: "limit", pin: "ECHO" } },
    ],
  },

  robot_drive_base: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "drv", moduleId: "l298n" },
    ],
    wires: [
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VCC" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "drv", pin: "5V" }, to: { role: "mcu", pin: "VIN" } },
      { from: { role: "drv", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "drv", pin: "IN1" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "drv", pin: "IN2" } },
    ],
    notes: ["Motor connects to OUT1/OUT2 (external load wiring)."],
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

  salvaged_input_panel: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "arduino-nano" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
    ],
    notes: ["Switches/buttons wire to D2/D3/A0 as digital inputs with pull-ups."],
  },

  camera_ir_light_or_sensor_mount: {
    modules: [
      { role: "psu", moduleId: "buck-lm2596" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...powerChain("psu", "OUT+", "OUT-", "mcu", "VIN", "GND"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
    notes: ["Camera/IR-light module not in library — wired stand-in is BME280 sensor."],
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
