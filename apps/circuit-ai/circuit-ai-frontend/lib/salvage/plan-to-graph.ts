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
import { findModulesByCapabilities, type ModuleSpec } from "@/lib/modules/module-library";

// Mirror of the backend BUILD_CATALOG (src/intelligence/salvage_splice_planner.py)
// — used as a fall-back when no hand-curated recipe matches the build_id.
// Each entry's requires_any is the capability-set list the salvage planner
// uses; we match against the library's derived capabilityTags to suggest
// concrete library modules for buildable products without a wired recipe.
const BUILD_CATALOG_CAPS: Record<string, string[][]> = {
  automatic_plant_watering: [["controller"], ["sensor_or_adc"], ["actuator_driver"], ["motor_or_load", "fan_or_pump"], ["power"]],
  usb_fume_extractor: [["motor_or_load", "fan_or_pump"], ["actuator_driver"], ["power"]],
  inspection_motion_fixture: [["mechanical_motion"], ["led_or_light", "camera_or_vision"], ["power"]],
  low_voltage_motor_test_jig: [["motor_or_load", "fan_or_pump", "mechanical_motion"], ["power"], ["connector", "switch_or_button"]],
  robot_drive_base: [["motor_or_load", "wheel_or_drive"], ["actuator_driver", "controller"], ["power"]],
  plotter_motion_stage: [["mechanical_motion"], ["switch_or_button", "sensor_or_adc"], ["power"]],
  smart_relay_box: [["controller"], ["actuator_driver"], ["power"]],
  sensor_logger: [["controller"], ["sensor_or_adc"], ["power"]],
  network_status_indicator: [["wireless", "network_interface"], ["display_or_ui", "led_or_light"], ["power"]],
  small_audio_amp_box: [["speaker_or_audio"], ["power"], ["switch_or_button", "connector"]],
  salvaged_input_panel: [["switch_or_button"], ["connector"], ["power", "controller"]],
  camera_ir_light_or_sensor_mount: [["camera_or_vision", "sensor_or_adc"], ["power"], ["enclosure_candidate", "connector"]],
  bench_power_adapter: [["power"], ["connector"]],
  usb_uart_debug_adapter: [["usb_serial"], ["connector"]],
  indicator_or_task_light: [["led_or_light"], ["power"]],
};

/** Pick one module per requirement group (set-cover) — fallback composer. */
function pickModulesForRequirements(reqAny: string[][]): ModuleSpec[] {
  const chosen: ModuleSpec[] = [];
  const chosenIds = new Set<string>();
  for (const group of reqAny) {
    const candidates = findModulesByCapabilities([group]).filter((m) => !chosenIds.has(m.id));
    if (candidates.length === 0) continue;
    // Prefer the most-focused module (fewest unrelated tags) for tighter fits.
    candidates.sort((a, b) => (a.capabilityTags?.length ?? 99) - (b.capabilityTags?.length ?? 99));
    chosen.push(candidates[0]);
    chosenIds.add(candidates[0].id);
  }
  return chosen;
}

type Wire = { from: { role: string; pin: string }; to: { role: string; pin: string } };
type Recipe = {
  modules: Array<{ role: string; moduleId: string }>;
  wires: Wire[];
  /** Notes the translator surfaces (substitutions, library gaps). */
  notes?: string[];
};

const i2cBus = (
  ctrl: string, sda: string, scl: string, vcc: string, gnd: string,
  dev: string,
): Wire[] => [
  { from: { role: ctrl, pin: vcc }, to: { role: dev, pin: "VCC" } },
  { from: { role: ctrl, pin: gnd }, to: { role: dev, pin: "GND" } },
  { from: { role: ctrl, pin: sda }, to: { role: dev, pin: "SDA" } },
  { from: { role: ctrl, pin: scl }, to: { role: dev, pin: "SCL" } },
];

/** 12V bench supply into a buck regulator (shared GND). */
const barrelToBuck = (pwr: string, buck: string): Wire[] => [
  { from: { role: pwr, pin: "V+" }, to: { role: buck, pin: "IN+" } },
  { from: { role: pwr, pin: "GND" }, to: { role: buck, pin: "IN-" } },
];

/** 5V USB supply into a load pin that accepts 5V (ESP32 VIN, Pico VBUS, etc.). */
const usbToMcu = (usb: string, mcu: string, mcuPin: string): Wire[] => [
  { from: { role: usb, pin: "V+" }, to: { role: mcu, pin: mcuPin } },
  { from: { role: usb, pin: "GND" }, to: { role: mcu, pin: "GND" } },
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
  // ESP32 USB-powered; soil sensor on 3V3/GPIO34; pump on a dedicated 5V buck +
  // MOSFET rail so the MCU is not loaded by pump inrush.
  automatic_plant_watering: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "soil_moisture" },
      { role: "buck", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      { from: { role: "pwr", pin: "V+" }, to: { role: "buck", pin: "IN+" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "buck", pin: "IN-" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "buck", pin: "OUT+" }, to: { role: "mcu", pin: "VIN" } },
      { from: { role: "buck", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "buck", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "buck", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "3V3" }, to: { role: "sns", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "sns", pin: "GND" } },
      { from: { role: "sns", pin: "A0" }, to: { role: "mcu", pin: "GPIO34" } },
      { from: { role: "mcu", pin: "GPIO4" }, to: { role: "drv", pin: "SIG" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: [
      "Set the MP1584 output to 5.0V with a multimeter before connecting the pump.",
      "Wire the mini pump to driver VOUT+/VOUT-; keep electronics above the wet zone.",
      "ESP32 may also be powered via USB for programming; share GND with the 12V supply.",
      "Add a flyback diode across the pump if the module does not include one.",
    ],
  },

  // Salvage path: USB power bank only (no 12V barrel). 5V rail feeds MCU + pump driver.
  automatic_plant_watering_usb: {
    modules: [
      { role: "pwr", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "soil_moisture" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      ...usbToMcu("pwr", "mcu", "VIN"),
      { from: { role: "pwr", pin: "V+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "3V3" }, to: { role: "sns", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "sns", pin: "GND" } },
      { from: { role: "sns", pin: "A0" }, to: { role: "mcu", pin: "GPIO34" } },
      { from: { role: "mcu", pin: "GPIO4" }, to: { role: "drv", pin: "SIG" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: [
      "USB power bank feeds ESP32 VIN and pump driver — no buck converter in the salvage path.",
      "Wire mini pump to driver VOUT+/VOUT-; add flyback diode if the module lacks one.",
      "Keep electronics above the wet zone; common GND across all modules.",
    ],
  },

  // USB-in -> 3.3V breakout, with optional Li-ion charging from the same
  // 5V rail. tp4056.IN+ (5V) sits cleanly in the LDO's 4.75-15V input range
  // and both modules share GND.
  bench_power_adapter: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "chg", moduleId: "tp4056" },
      { role: "ldo", moduleId: "ldo-ams1117-3v3" },
    ],
    wires: [
      { from: { role: "usb", pin: "V+" }, to: { role: "chg", pin: "IN+" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "chg", pin: "IN-" } },
      { from: { role: "chg", pin: "OUT+" }, to: { role: "ldo", pin: "VIN" } },
      { from: { role: "chg", pin: "OUT-" }, to: { role: "ldo", pin: "GND" } },
    ],
    notes: [
      "3.3V on LDO VOUT for sensors/MCU.",
      "Optional Li-ion cell on TP4056 BAT+/BAT- for charging.",
    ],
  },

  usb_fume_extractor: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      ...barrelToBuck("pwr", "psu"),
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["Set buck to fan voltage (often 5V or 12V). Fan wires to driver VOUT+/VOUT-."],
  },

  indicator_or_task_light: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      ...barrelToBuck("pwr", "psu"),
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["LED load on VOUT+/VOUT- with appropriate series resistor."],
  },

  low_voltage_motor_test_jig: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      ...barrelToBuck("pwr", "psu"),
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: ["Add a manual switch on SIG for benchtop on/off."],
  },

  smart_relay_box: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "rly", moduleId: "relay-1ch-5v" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "mcu", pin: "5V" }, to: { role: "rly", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "rly", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "rly", pin: "IN" } },
    ],
    notes: ["Add a fly-back diode if switching inductive loads."],
  },

  sensor_logger: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
    notes: ["3V3 from ESP32 feeds the BME280 directly."],
  },

  network_status_indicator: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "ui", moduleId: "ssd1306-128x64" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "ui"),
    ],
    notes: ["ESP32 supplies Wi-Fi; OLED on shared 3V3 I2C bus."],
  },

  // Pico (3.3V logic) matches ssd1306 directly — no level shifter. The new
  // AMS1117-5V LDO gives the servo its own clean 5V rail, dedicated, so it
  // doesn't drag the MCU.
  inspection_motion_fixture: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "rpi-pico" },
      { role: "ui", moduleId: "ssd1306-128x64" },
      { role: "svo_psu", moduleId: "ldo-ams1117-5v" },
      { role: "svo", moduleId: "sg90" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VBUS"),
      { from: { role: "pwr", pin: "V+" }, to: { role: "svo_psu", pin: "VIN" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "svo_psu", pin: "GND" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      ...i2cBus("mcu", "GP4", "GP5", "3V3", "GND", "ui"),
      { from: { role: "svo_psu", pin: "VOUT" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "svo_psu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
      { from: { role: "mcu", pin: "GP0" }, to: { role: "svo", pin: "SIG" } },
    ],
    notes: [
      "12V barrel feeds the servo LDO; USB 5V feeds the Pico.",
      "Common GND between Pico, display, and servo rail.",
    ],
  },

  // HC-SR04 is 5V-only; arduino (5V logic) matches without level shift.
  // Servo gets its own dedicated 5V via AMS1117-5V — never the MCU rail.
  plotter_motion_stage: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "limit", moduleId: "hc-sr04" },
      { role: "svo_psu", moduleId: "ldo-ams1117-5v" },
      { role: "svo", moduleId: "sg90" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "pwr", pin: "V+" }, to: { role: "svo_psu", pin: "VIN" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "svo_psu", pin: "GND" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "mcu", pin: "5V" }, to: { role: "limit", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "limit", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "limit", pin: "TRIG" } },
      { from: { role: "mcu", pin: "A0" }, to: { role: "limit", pin: "ECHO" } },
      { from: { role: "svo_psu", pin: "VOUT" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "svo_psu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "svo", pin: "SIG" } },
    ],
    notes: [
      "12V barrel feeds servo LDO; USB 5V feeds Arduino.",
      "HC-SR04 runs from Arduino 5V rail.",
    ],
  },

  robot_drive_base: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "mot_psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "l298n" },
    ],
    wires: [
      ...barrelToBuck("pwr", "mot_psu"),
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "mot_psu", pin: "OUT+" }, to: { role: "drv", pin: "VCC" } },
      { from: { role: "mot_psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "drv", pin: "IN1" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "drv", pin: "IN2" } },
    ],
    notes: [
      "Set motor buck to motor rated voltage. Motors on OUT1/OUT2.",
      "USB 5V feeds Arduino; 12V barrel feeds motor driver supply.",
    ],
  },

  usb_uart_debug_adapter: {
    modules: [
      { role: "adapter", moduleId: "ch340-usb-ttl" },
      { role: "target", moduleId: "arduino-nano" },
    ],
    wires: [
      { from: { role: "adapter", pin: "VCC" }, to: { role: "target", pin: "VIN" } },
      { from: { role: "adapter", pin: "GND" }, to: { role: "target", pin: "GND" } },
      { from: { role: "adapter", pin: "TX" }, to: { role: "target", pin: "D2" } },
      { from: { role: "adapter", pin: "RX" }, to: { role: "target", pin: "D3" } },
    ],
    notes: [
      "CH340 is powered from its USB cable; VCC feeds the target MCU.",
      "Wire to native UART pins on your target for production use.",
    ],
  },

  small_audio_amp_box: {
    modules: [
      { role: "pwr", moduleId: "dc-barrel-12v" },
      { role: "psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
    ],
    wires: [
      ...barrelToBuck("pwr", "psu"),
      { from: { role: "psu", pin: "OUT+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "psu", pin: "OUT-" }, to: { role: "drv", pin: "GND" } },
    ],
    notes: [
      "MOSFET stand-in until a Class-D amp module is added to the library.",
      "Speaker load on VOUT+/VOUT- with series resistor where needed.",
    ],
  },

  salvaged_input_panel: {
    modules: [
      { role: "mcu", moduleId: "arduino-nano" },
      { role: "adapter", moduleId: "ch340-usb-ttl" },
    ],
    wires: [
      { from: { role: "adapter", pin: "VCC" }, to: { role: "mcu", pin: "VIN" } },
      { from: { role: "adapter", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "adapter", pin: "TX" }, to: { role: "mcu", pin: "D2" } },
      { from: { role: "adapter", pin: "RX" }, to: { role: "mcu", pin: "D3" } },
    ],
    notes: ["Switches wire to A0..A5; read over USB serial via CH340."],
  },

  camera_ir_light_or_sensor_mount: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "bme280" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      ...i2cBus("mcu", "GPIO21", "GPIO22", "3V3", "GND", "sns"),
    ],
    notes: [
      "BME280 stand-in until a camera module spec is added.",
      "Mount mechanics are handled by Mecha-Splicer enclosure output.",
    ],
  },
};

export interface SalvagePlanInput {
  target?: { recommended_build_id?: string | null };
  reusable_blocks?: Array<{ id?: string; name?: string; capabilities?: string[]; source?: string }>;
  build_candidates?: Array<{ id?: string; name?: string }>;
  resolved_modules?: Array<{ module_id?: string | null; role?: string; part_name?: string; source?: string }>;
  module_overrides?: Record<string, string>;
  power_topology?: "usb_5v" | "barrel_12v" | "hybrid" | string;
  strategy_mode?: string;
  custom_graph?: BuildGraph;
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

  if (plan?.custom_graph?.nodes?.length) {
    notes.push("Using inventory-composed custom_graph from salvage bridge.");
    return { graph: plan.custom_graph, buildId, notes, warnings };
  }

  const overridesPreview = { ...(plan?.module_overrides || {}) };
  let recipeKey = buildId;
  if (buildId === "automatic_plant_watering") {
    const topo = plan?.power_topology || "";
    const pwr = overridesPreview.pwr || "";
    if (topo === "usb_5v" || pwr === "usb-power-5v") {
      recipeKey = "automatic_plant_watering_usb";
      notes.push("Power topology: USB 5V salvage path (no 12V barrel).");
    }
  }

  const recipe = RECIPES[recipeKey];
  if (!recipe) {
    // Fall-back: use capability matcher against the library to suggest modules
    // for this build's requires_any. Returns an unwired starter graph the user
    // can complete on the canvas — strictly better than an empty result.
    const reqAny = BUILD_CATALOG_CAPS[buildId];
    if (reqAny) {
      const picked = pickModulesForRequirements(reqAny);
      if (picked.length > 0) {
        const nodes = picked.map((m, i) => ({ id: `n${i + 1}`, moduleId: m.id }));
        warnings.push(
          `No hand-curated recipe for "${buildId}" — suggested ${picked.length} module(s) ` +
          `via capability matching: ${picked.map((m) => m.id).join(", ")}. Wire them on the canvas.`,
        );
        return { graph: { nodes, wires: [] }, buildId, notes, warnings };
      }
    }
    warnings.push(`No translator recipe and no capability fall-back for "${buildId}".`);
    return { graph: { nodes: [], wires: [] }, buildId, notes, warnings };
  }

  const overrides = { ...overridesPreview };
  for (const row of plan?.resolved_modules || []) {
    if (row?.role && row?.module_id && !overrides[row.role]) {
      overrides[row.role] = row.module_id;
    }
  }

  const modules = recipe.modules.map((m) => ({
    role: m.role,
    moduleId: overrides[m.role] || m.moduleId,
  }));
  if (Object.keys(overrides).length > 0) {
    notes.push(`Module overrides applied: ${JSON.stringify(overrides)}`);
  }

  // Materialize role -> nodeId; build BuildGraph nodes.
  const idOf = new Map<string, string>();
  const nodes = modules.map((m, i) => {
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
