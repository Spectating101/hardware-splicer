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
import {
  findModule,
  findModulesByCapabilities,
  type ModulePin,
  type ModuleSpec,
} from "@/lib/modules/module-library";
import { adaptRecipeToInventory } from "./inventory-topology";

// Mirror of the backend BUILD_CATALOG (src/intelligence/salvage_splice_planner.py)
// — used as a fall-back when no hand-curated recipe matches the build_id.
// Each entry's requires_any is the capability-set list the salvage planner
// uses; we match against the library's derived capabilityTags to suggest
// concrete library modules for buildable products without a wired recipe.
const BUILD_CATALOG_CAPS: Record<string, string[][]> = {
  automatic_plant_watering: [["controller"], ["sensor_or_adc"], ["actuator_driver"], ["motor_or_load", "fan_or_pump"], ["power"]],
  usb_fume_extractor: [["controller"], ["motor_or_load", "fan_or_pump"], ["actuator_driver"], ["power"]],
  inspection_motion_fixture: [["mechanical_motion"], ["led_or_light", "camera_or_vision"], ["power"]],
  low_voltage_motor_test_jig: [["motor_or_load", "fan_or_pump", "mechanical_motion"], ["power"], ["connector", "switch_or_button"]],
  robot_drive_base: [["motor_or_load", "wheel_or_drive"], ["actuator_driver", "controller"], ["power"]],
  plotter_motion_stage: [["mechanical_motion"], ["switch_or_button", "sensor_or_adc"], ["power"]],
  smart_relay_box: [["controller"], ["actuator_driver"], ["power"]],
  sensor_logger: [["controller"], ["sensor_or_adc"], ["power"]],
  room_display_station: [["controller"], ["sensor_or_adc"], ["display_or_ui"], ["power"]],
  network_status_indicator: [["wireless", "network_interface"], ["display_or_ui", "led_or_light"], ["power"]],
  small_audio_amp_box: [["speaker_or_audio"], ["power"], ["switch_or_button", "connector"]],
  salvaged_input_panel: [["switch_or_button"], ["connector"], ["power", "controller"]],
  camera_ir_light_or_sensor_mount: [["camera_or_vision", "sensor_or_adc"], ["power"], ["enclosure_candidate", "connector"]],
  bench_power_adapter: [["power"], ["connector"]],
  usb_uart_debug_adapter: [["usb_serial"], ["connector"]],
  indicator_or_task_light: [["led_or_light"], ["power"]],
  generic_low_voltage_build: [["controller"], ["power"], ["connector"]],
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

function pinByRole(mod: ModuleSpec, role: ModulePin["role"]): string | undefined {
  return mod.pins.find((p) => p.role === role)?.id;
}

function mcuPowerInPin(mod: ModuleSpec): string | undefined {
  return mod.pins.find((p) => p.id === "VIN")?.id
    ?? mod.pins.find((p) => p.id === "VBUS")?.id
    ?? mod.pins.find((p) => p.id === "5V")?.id
    ?? pinByRole(mod, "power_in");
}

function powerOutPin(mod: ModuleSpec): string | undefined {
  return mod.pins.find((p) => p.id === "V+")?.id
    ?? mod.pins.find((p) => p.role === "power_out")?.id
    ?? pinByRole(mod, "power_in");
}

function firstPin(mod: ModuleSpec, pred: (p: ModulePin) => boolean): string | undefined {
  return mod.pins.find(pred)?.id;
}

function allocGpio(mcu: ModuleSpec, used: Set<string>): string | undefined {
  const order = [
    "GPIO12", "GPIO13", "GPIO14", "GPIO15",
    "GPIO16", "GPIO17", "GPIO4", "GPIO2", "GP4", "GP5", "GP0", "GP1", "GP26",
    "D2", "D3", "A0", "A1", "A2", "A3", "A4", "A5",
  ];
  for (const id of order) {
    if (mcu.pins.some((p) => p.id === id) && !used.has(id)) {
      used.add(id);
      return id;
    }
  }
  const fallback = mcu.pins.find(
    (p) => (p.role === "digital_io" || p.role === "pwm" || p.role === "analog_in") && !used.has(p.id),
  );
  if (fallback) used.add(fallback.id);
  return fallback?.id;
}

/** Heuristic auto-wiring for capability-matched or inventory-composed module sets. */
function autoWirePickedModules(modules: ModuleSpec[]): Recipe {
  const roles = modules.map((m, i) => ({ role: `m${i + 1}`, moduleId: m.id }));
  const roleOf = new Map(modules.map((m, i) => [m.id, `m${i + 1}`]));
  const wires: Wire[] = [];
  const wireKeys = new Set<string>();
  const wire = (fromId: string, fromPin: string, toId: string, toPin: string) => {
    const fr = roleOf.get(fromId);
    const tr = roleOf.get(toId);
    if (!fr || !tr) return;
    const key = `${fr}:${fromPin}->${tr}:${toPin}`;
    const rev = `${tr}:${toPin}->${fr}:${fromPin}`;
    if (wireKeys.has(key) || wireKeys.has(rev)) return;
    wireKeys.add(key);
    wires.push({ from: { role: fr, pin: fromPin }, to: { role: tr, pin: toPin } });
  };

  const barrel = modules.find((m) => m.id === "dc-barrel-12v");
  const usb = modules.find((m) => /usb-power/.test(m.id));
  const buck = modules.find((m) => /buck/.test(m.id));
  const ldo = modules.find((m) => /ldo-ams1117/.test(m.id));
  const power = usb ?? barrel ?? modules.find((m) => m.category === "power");
  const mcu = modules.find((m) => m.category === "mcu");
  const gndPin = (m: ModuleSpec) => pinByRole(m, "gnd");
  const usedGpio = new Set<string>();

  if (barrel && buck) {
    wire(barrel.id, "V+", buck.id, "IN+");
    wire(barrel.id, "GND", buck.id, "IN-");
  }
  if (buck && power && power.id !== buck.id) {
    const pOut = powerOutPin(power) ?? firstPin(power, (p) => p.role === "power_in");
    const pGnd = gndPin(power);
    if (pOut) wire(power.id, pOut, buck.id, "IN+");
    if (pGnd) wire(power.id, pGnd, buck.id, "IN-");
  }
  if (power && mcu) {
    const pOut = powerOutPin(power);
    const mIn = mcuPowerInPin(mcu);
    const gnd = gndPin(power);
    const mGnd = gndPin(mcu);
    if (pOut && mIn) wire(power.id, pOut, mcu.id, mIn);
    if (gnd && mGnd) wire(power.id, gnd, mcu.id, mGnd);
  }
  if (barrel && ldo && !buck) {
    wire(barrel.id, "V+", ldo.id, "VIN");
    wire(barrel.id, "GND", ldo.id, "GND");
  }

  const railPos = buck
    ? { id: buck.id, pin: "OUT+" }
    : ldo
      ? { id: ldo.id, pin: "VOUT" }
      : usb
        ? { id: usb.id, pin: powerOutPin(usb) ?? "5V" }
        : mcu
          ? { id: mcu.id, pin: mcu.pins.find((p) => p.id === "5V")?.id ?? "3V3" }
          : null;
  const railGnd = buck
    ? { id: buck.id, pin: "OUT-" }
    : ldo
      ? { id: ldo.id, pin: "GND" }
      : usb && gndPin(usb)
        ? { id: usb.id, pin: gndPin(usb)! }
        : mcu && gndPin(mcu)
          ? { id: mcu.id, pin: gndPin(mcu)! }
          : null;

  const mcuSda = mcu?.pins.find((p) => p.role === "i2c_sda")?.id;
  const mcuScl = mcu?.pins.find((p) => p.role === "i2c_scl")?.id;
  const mcuVout = mcu?.pins.find((p) => p.id === "3V3")?.id ?? mcu?.pins.find((p) => p.id === "5V")?.id;
  const levelShifter = modules.find((m) => /level-shifter/.test(m.id));
  const loadSwitch = modules.find((m) => /mosfet-irlz44n|mosfet-irf520/.test(m.id));

  if (levelShifter && mcu && railPos && railGnd) {
    const hvRail = firstPin(levelShifter, (p) => p.id === "HV");
    const lvRail = firstPin(levelShifter, (p) => p.id === "LV");
    const shGnd = gndPin(levelShifter);
    if (hvRail && railPos) wire(railPos.id, railPos.pin, levelShifter.id, hvRail);
    if (shGnd && railGnd) wire(railGnd.id, railGnd.pin, levelShifter.id, shGnd);
    if (lvRail && mcuVout) wire(mcu.id, mcuVout, levelShifter.id, lvRail);
    if (shGnd && gndPin(mcu)) wire(mcu.id, gndPin(mcu)!, levelShifter.id, shGnd);
  }

  const switchedLoads = new Set(["water_pump_5v", "cooling_fan_5v"]);

  for (const dev of modules) {
    if ([power, mcu, barrel, buck, ldo, levelShifter].filter(Boolean).includes(dev)) continue;
    const devGnd = gndPin(dev);
    if (mcu && devGnd && gndPin(mcu)) wire(mcu.id, gndPin(mcu)!, dev.id, devGnd);
    else if (railGnd && devGnd) wire(railGnd.id, railGnd.pin, dev.id, devGnd);

    const devVccPin = dev.pins.find((p) => p.id === "VCC" || p.id === "VIN" || p.role === "power_in");
    const devVcc = devVccPin?.id;
    const wants5V = (dev.inputVoltageRange?.[0] ?? 0) >= 4.5
      || /5\s*v/i.test(devVccPin?.voltage ?? "");
    const viaSwitch = loadSwitch && switchedLoads.has(dev.id) && devVcc;
    if (viaSwitch) {
      if (railPos) wire(railPos.id, railPos.pin, loadSwitch!.id, "VIN");
      if (railGnd) wire(railGnd.id, railGnd.pin, loadSwitch!.id, "VIN-");
      wire(loadSwitch!.id, "VOUT+", dev.id, devVcc);
      if (gndPin(loadSwitch!) && devGnd) wire(loadSwitch!.id, gndPin(loadSwitch!)!, dev.id, devGnd);
    } else if (wants5V && railPos && devVcc) {
      wire(railPos.id, railPos.pin, dev.id, devVcc);
    } else if (mcu && mcuVout && devVcc) {
      wire(mcu.id, mcuVout, dev.id, devVcc);
    } else if (railPos && devVcc) {
      wire(railPos.id, railPos.pin, dev.id, devVcc);
    }

    const devSda = dev.pins.find((p) => p.role === "i2c_sda")?.id;
    const devScl = dev.pins.find((p) => p.role === "i2c_scl")?.id;
    if (mcu && mcuSda && mcuScl && devSda && devScl) {
      wire(mcu.id, mcuSda, dev.id, devSda);
      wire(mcu.id, mcuScl, dev.id, devScl);
    }

    if (mcu && /mosfet/.test(dev.id)) {
      const sig = allocGpio(mcu, usedGpio);
      const vin = firstPin(dev, (p) => p.id === "VIN");
      const gnd = firstPin(dev, (p) => p.role === "gnd");
      if (sig && firstPin(dev, (p) => p.id === "SIG")) wire(mcu.id, sig, dev.id, "SIG");
      if (railPos && vin) wire(railPos.id, railPos.pin, dev.id, vin);
      if (railGnd && gnd) wire(railGnd.id, railGnd.pin, dev.id, gnd);
    }
    if (mcu && dev.id === "relay-1ch-5v") {
      const sig = allocGpio(mcu, usedGpio);
      if (sig) wire(mcu.id, sig, dev.id, "IN");
    }
    if (mcu && dev.id === "l298n") {
      const controlPins = firstPin(dev, (p) => p.id === "IN3")
        ? (["IN1", "IN2", "IN3", "IN4"] as const)
        : (["IN1", "IN2"] as const);
      for (const pinName of controlPins) {
        if (!firstPin(dev, (p) => p.id === pinName)) continue;
        const sig = allocGpio(mcu, usedGpio);
        if (sig) wire(mcu.id, sig, dev.id, pinName);
      }
      if (railPos) wire(railPos.id, railPos.pin, dev.id, "VCC");
      if (mcu && gndPin(mcu)) wire(mcu.id, gndPin(mcu)!, dev.id, "GND");
    }
    if (mcu && dev.id === "a4988-stepper") {
      const step = allocGpio(mcu, usedGpio);
      const dir = allocGpio(mcu, usedGpio);
      if (step) wire(mcu.id, step, dev.id, "STEP");
      if (dir) wire(mcu.id, dir, dev.id, "DIR");
      if (mcuVout) wire(mcu.id, mcuVout, dev.id, "VDD");
      if (railPos) wire(railPos.id, railPos.pin, dev.id, "VMOT");
      if (mcu && gndPin(mcu)) wire(mcu.id, gndPin(mcu)!, dev.id, "GND_LOGIC");
      if (railGnd) wire(railGnd.id, railGnd.pin, dev.id, "GND_MOTOR");
    }
    if (mcu && dev.id === "sg90") {
      const sig = allocGpio(mcu, usedGpio);
      if (sig) wire(mcu.id, sig, dev.id, "SIG");
    }
    if (mcu && dev.id === "hc-sr04") {
      const trig = allocGpio(mcu, usedGpio);
      const echo = allocGpio(mcu, usedGpio);
      if (levelShifter && trig && echo) {
        wire(mcu.id, trig, levelShifter.id, "LV1");
        wire(levelShifter.id, "HV1", dev.id, "TRIG");
        wire(dev.id, "ECHO", levelShifter.id, "HV2");
        wire(levelShifter.id, "LV2", mcu.id, echo);
      } else {
        if (trig) wire(mcu.id, trig, dev.id, "TRIG");
        if (echo) wire(mcu.id, echo, dev.id, "ECHO");
      }
    }
    if (mcu && dev.id === "dht22") {
      const data = allocGpio(mcu, usedGpio);
      if (data) wire(mcu.id, data, dev.id, "DATA");
    }
    if (mcu && dev.id === "soil_moisture") {
      const ao = allocGpio(mcu, usedGpio);
      if (ao) wire(mcu.id, ao, dev.id, "A0");
    }
    if (mcu && dev.id === "limit-switch-3pin") {
      const sig = allocGpio(mcu, usedGpio);
      if (sig) wire(mcu.id, sig, dev.id, "SIG");
    }
    if (mcu && /ili9341|st7735/.test(dev.id)) {
      const pickMcuPin = (preferred: string[], devPinId: string) => {
        for (const p of preferred) {
          if (mcu!.pins.some((pin) => pin.id === p) && !usedGpio.has(p)) {
            usedGpio.add(p);
            wire(mcu!.id, p, dev.id, devPinId);
            return;
          }
        }
        const sig = allocGpio(mcu, usedGpio);
        if (sig) wire(mcu.id, sig, dev.id, devPinId);
      };
      const mosiPin = dev.pins.find((p) => p.role === "spi_mosi" || p.id === "SDI" || p.id === "SDA")?.id;
      const sckPin = dev.pins.find((p) => p.role === "spi_sck" || p.id === "SCK" || p.id === "SCL")?.id;
      const csPin = dev.pins.find((p) => p.role === "spi_cs" || p.id === "CS")?.id;
      const rstPin = dev.pins.find((p) => p.id === "RST" || p.id === "RES")?.id;
      const dcPin = dev.pins.find((p) => p.id === "DC")?.id;
      if (mosiPin) pickMcuPin(["GPIO23", "GPIO21", "GPIO17"], mosiPin);
      if (sckPin) pickMcuPin(["GPIO18", "GPIO22", "GPIO5"], sckPin);
      if (csPin) pickMcuPin(["GPIO15", "GPIO4", "GPIO2"], csPin);
      if (rstPin) pickMcuPin(["GPIO2", "GPIO4", "GPIO16"], rstPin);
      if (dcPin) pickMcuPin(["GPIO4", "GPIO16", "GPIO17"], dcPin);
      if (railPos && dev.pins.find((p) => p.id === "VCC")) {
        wire(railPos.id, railPos.pin, dev.id, "VCC");
      }
    }
    if (mcu && dev.id === "max98357a-i2s-amp") {
      const bclk = mcu.pins.find((p) => p.id === "GPIO22" || p.role === "i2c_scl")?.id;
      const lrc = mcu.pins.find((p) => p.id === "GPIO21" || p.role === "i2c_sda")?.id;
      const din = allocGpio(mcu, usedGpio);
      if (mcuVout) wire(mcu.id, mcuVout, dev.id, "VIN");
      if (mcu && gndPin(mcu)) wire(mcu.id, gndPin(mcu)!, dev.id, "GND");
      if (bclk) wire(mcu.id, bclk, dev.id, "BCLK");
      if (lrc) wire(mcu.id, lrc, dev.id, "LRC");
      if (din) wire(mcu.id, din, dev.id, "DIN");
    }
    if (power && dev.id === "esp32-cam-module") {
      const pOut = powerOutPin(power);
      const gnd = gndPin(power);
      if (pOut) wire(power.id, pOut, dev.id, "5V");
      if (gnd && gndPin(dev)) wire(power.id, gnd, dev.id, "GND");
    }

    if (mcu) {
      const wiredPins = new Set(
        wires
          .filter((w) => w.from.role === roleOf.get(dev.id) || w.to.role === roleOf.get(dev.id))
          .flatMap((w) => [w.from.pin, w.to.pin]),
      );
      const analog = dev.pins.find((p) => p.role === "analog_in" && !wiredPins.has(p.id));
      if (analog) {
        const mcuAnalog = mcu.pins.find((p) => p.role === "analog_in")?.id ?? allocGpio(mcu, usedGpio);
        if (mcuAnalog) wire(mcu.id, mcuAnalog, dev.id, analog.id);
      } else {
        const digital = dev.pins.find(
          (p) => (p.role === "digital_io" || p.role === "digital_in" || p.role === "digital_out")
            && p.id !== "VCC"
            && !wiredPins.has(p.id),
        );
        if (digital) {
          const sig = allocGpio(mcu, usedGpio);
          if (sig) wire(mcu.id, sig, dev.id, digital.id);
        }
      }
    }
  }

  return {
    modules: roles,
    wires,
    notes: ["Auto-wired via inventory/capability composer — review pins before fab."],
  };
}

/** Materialize a Recipe into a BuildGraph. */
export function recipeToBuildGraph(recipe: Recipe): BuildGraph {
  const idOf = new Map<string, string>();
  const nodes = recipe.modules.map((m, i) => {
    const nodeId = `n${i + 1}`;
    idOf.set(m.role, nodeId);
    return { id: nodeId, moduleId: m.moduleId };
  });
  const wires = recipe.wires.flatMap((w, i) => {
    const from = idOf.get(w.from.role);
    const to = idOf.get(w.to.role);
    if (!from || !to) return [];
    return [{
      id: `w${i + 1}`,
      from: { nodeId: from, pinId: w.from.pin },
      to: { nodeId: to, pinId: w.to.pin },
    }];
  });
  return { nodes, wires };
}

/** Auto-wire canvas nodes while preserving their ReactFlow node ids. */
export function composeBuildGraphFromCanvasNodes(
  nodes: Array<{ id: string; moduleId: string }>,
): BuildGraph {
  const specs: ModuleSpec[] = [];
  const nodeIds: string[] = [];
  for (const node of nodes) {
    const spec = findModule(node.moduleId);
    if (!spec) continue;
    specs.push(spec);
    nodeIds.push(node.id);
  }
  if (specs.length < 2) {
    return {
      nodes: nodes.map((n) => ({ id: n.id, moduleId: n.moduleId })),
      wires: [],
    };
  }
  const recipe = autoWirePickedModules(specs);
  const roleToNodeId = new Map(
    recipe.modules.map((m, i) => [m.role, nodeIds[i]] as const),
  );
  const buildNodes = nodeIds.map((id, i) => ({ id, moduleId: specs[i].id }));
  const wires = recipe.wires.flatMap((w, i) => {
    const fromId = roleToNodeId.get(w.from.role);
    const toId = roleToNodeId.get(w.to.role);
    if (!fromId || !toId) return [];
    return [{
      id: `w${i + 1}`,
      from: { nodeId: fromId, pinId: w.from.pin },
      to: { nodeId: toId, pinId: w.to.pin },
    }];
  });
  return { nodes: buildNodes, wires };
}

/** Compose and wire a graph from explicit library module ids. */
export function composeBuildGraphFromModuleIds(moduleIds: string[]): TranslationResult {
  const modules = moduleIds
    .map((id) => findModule(id))
    .filter((m): m is ModuleSpec => !!m);
  if (modules.length < 2) {
    return {
      graph: { nodes: [], wires: [] },
      buildId: "generic_low_voltage_build",
      notes: [],
      warnings: ["Need at least two known module ids to compose a graph."],
    };
  }
  const recipe = autoWirePickedModules(modules);
  return {
    graph: recipeToBuildGraph(recipe),
    buildId: "generic_low_voltage_build",
    notes: recipe.notes ? [...recipe.notes] : [],
    warnings: [],
  };
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

  // USB desk fume / airflow: MCU + MOSFET low-side switch + optional DHT + fan load.
  // (Legacy barrel+buck-only recipe omitted MCU — that failed junk→intent honesty.)
  usb_fume_extractor: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "sns", moduleId: "dht22" },
      { role: "drv", moduleId: "mosfet-irlz44n" },
      { role: "load", moduleId: "cooling_fan_5v" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "usb", pin: "V+" }, to: { role: "drv", pin: "VIN" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "drv", pin: "VIN-" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "mcu", pin: "3V3" }, to: { role: "sns", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "sns", pin: "GND" } },
      { from: { role: "sns", pin: "DATA" }, to: { role: "mcu", pin: "GPIO15" } },
      { from: { role: "mcu", pin: "GPIO25" }, to: { role: "drv", pin: "SIG" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND" } },
      { from: { role: "drv", pin: "VOUT+" }, to: { role: "load", pin: "VCC" } },
      { from: { role: "drv", pin: "VOUT-" }, to: { role: "load", pin: "GND" } },
    ],
    notes: [
      "USB 5V feeds MCU + MOSFET high side; fan on driver VOUT+/VOUT-.",
      "GPIO25 = fan enable; DHT22 DATA on GPIO15 for optional temp-triggered airflow.",
    ],
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

  room_display_station: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "ui", moduleId: "ili9341_tft" },
      { role: "sns", moduleId: "dht22" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "usb", pin: "V+" }, to: { role: "ui", pin: "VCC" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "ui", pin: "GND" } },
      { from: { role: "mcu", pin: "GPIO23" }, to: { role: "ui", pin: "SDI" } },
      { from: { role: "mcu", pin: "GPIO18" }, to: { role: "ui", pin: "SCK" } },
      { from: { role: "mcu", pin: "GPIO15" }, to: { role: "ui", pin: "CS" } },
      { from: { role: "mcu", pin: "GPIO2" }, to: { role: "ui", pin: "RST" } },
      { from: { role: "mcu", pin: "GPIO4" }, to: { role: "ui", pin: "DC" } },
      { from: { role: "mcu", pin: "3V3" }, to: { role: "sns", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "sns", pin: "GND" } },
      { from: { role: "mcu", pin: "GPIO16" }, to: { role: "sns", pin: "DATA" } },
    ],
    notes: [
      "ILI9341 color TFT on SPI; DHT22 on GPIO16.",
      "Install TFT_eSPI + DHT libraries — match User_Setup pins to wiring above.",
    ],
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
      { role: "mot_psu", moduleId: "buck-mp1584" },
      { role: "drv", moduleId: "a4988-stepper" },
      { role: "lim_x", moduleId: "limit-switch-3pin" },
      { role: "lim_y", moduleId: "limit-switch-3pin" },
      { role: "svo_psu", moduleId: "ldo-ams1117-5v" },
      { role: "svo", moduleId: "sg90" },
    ],
    wires: [
      ...barrelToBuck("pwr", "mot_psu"),
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "pwr", pin: "GND" }, to: { role: "mcu", pin: "GND" } },
      { from: { role: "mot_psu", pin: "OUT+" }, to: { role: "drv", pin: "VMOT" } },
      { from: { role: "mot_psu", pin: "OUT-" }, to: { role: "drv", pin: "GND_MOTOR" } },
      { from: { role: "mcu", pin: "5V" }, to: { role: "drv", pin: "VDD" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "drv", pin: "GND_LOGIC" } },
      { from: { role: "mcu", pin: "D2" }, to: { role: "drv", pin: "STEP" } },
      { from: { role: "mcu", pin: "D3" }, to: { role: "drv", pin: "DIR" } },
      { from: { role: "mcu", pin: "5V" }, to: { role: "lim_x", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "lim_x", pin: "GND" } },
      { from: { role: "mcu", pin: "A0" }, to: { role: "lim_x", pin: "SIG" } },
      { from: { role: "mcu", pin: "5V" }, to: { role: "lim_y", pin: "VCC" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "lim_y", pin: "GND" } },
      { from: { role: "mcu", pin: "A4" }, to: { role: "lim_y", pin: "SIG" } },
      { from: { role: "pwr", pin: "V+" }, to: { role: "svo_psu", pin: "VIN" } },
      { from: { role: "pwr", pin: "GND" }, to: { role: "svo_psu", pin: "GND" } },
      { from: { role: "svo_psu", pin: "VOUT" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "svo_psu", pin: "GND" }, to: { role: "svo", pin: "GND" } },
      { from: { role: "mcu", pin: "A5" }, to: { role: "svo", pin: "SIG" } },
    ],
    notes: [
      "A4988 stepper on motor buck; dual limit switches on A0/A4; tie EN to GND to enable driver.",
      "12V barrel feeds motor buck + servo LDO; USB 5V feeds Arduino.",
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
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
      { role: "amp", moduleId: "max98357a-i2s-amp" },
    ],
    wires: [
      ...usbToMcu("usb", "mcu", "VIN"),
      { from: { role: "mcu", pin: "3V3" }, to: { role: "amp", pin: "VIN" } },
      { from: { role: "mcu", pin: "GND" }, to: { role: "amp", pin: "GND" } },
      { from: { role: "mcu", pin: "GPIO21" }, to: { role: "amp", pin: "LRC" } },
      { from: { role: "mcu", pin: "GPIO22" }, to: { role: "amp", pin: "BCLK" } },
      { from: { role: "mcu", pin: "GPIO4" }, to: { role: "amp", pin: "DIN" } },
    ],
    notes: [
      "MAX98357A I2S Class-D mono amp — connect 4Ω+ speaker across SPK+/SPK-.",
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
      { role: "cam", moduleId: "esp32-cam-module" },
    ],
    wires: [
      { from: { role: "usb", pin: "V+" }, to: { role: "cam", pin: "5V" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "cam", pin: "GND" } },
    ],
    notes: [
      "ESP32-CAM OV2640 module — use U0T/U0R for flashing when GPIO0 strapped.",
      "Mount mechanics are handled by Mecha-Splicer enclosure output.",
    ],
  },

  generic_low_voltage_build: {
    modules: [
      { role: "usb", moduleId: "usb-power-5v" },
      { role: "mcu", moduleId: "esp32-devkit" },
    ],
    wires: [...usbToMcu("usb", "mcu", "VIN")],
    notes: [
      "Flexible USB-powered starter — use compose_from_inventory to auto-wire owned modules.",
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
  /** When true, wire resolved_modules via autoWirePickedModules instead of recipe-only modules. */
  compose_from_inventory?: boolean;
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

  if (plan?.compose_from_inventory && plan.resolved_modules?.length) {
    const ids = [
      ...new Set(
        plan.resolved_modules
          .map((r) => r.module_id)
          .filter((id): id is string => typeof id === "string" && id.length > 0),
      ),
    ];
    if (ids.length >= 2) {
      const composed = composeBuildGraphFromModuleIds(ids);
      notes.push(...composed.notes);
      if (composed.warnings.length) warnings.push(...composed.warnings);
      notes.push(`Inventory compose: ${ids.join(", ")}`);
      return { graph: composed.graph, buildId, notes, warnings };
    }
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
        const auto = autoWirePickedModules(picked);
        notes.push(...(auto.notes || []));
        warnings.push(
          `No hand-curated recipe for "${buildId}" — auto-wired ${picked.length} module(s): ` +
          `${picked.map((m) => m.id).join(", ")}.`,
        );
        return { graph: recipeToBuildGraph(auto), buildId, notes, warnings };
      }
    }
    warnings.push(`No translator recipe and no capability fall-back for "${buildId}".`);
    return { graph: { nodes: [], wires: [] }, buildId, notes, warnings };
  }

  const planWithOverrides: SalvagePlanInput = {
    ...plan,
    module_overrides: { ...overridesPreview },
  };
  for (const row of plan?.resolved_modules || []) {
    if (row?.role && row?.module_id && !planWithOverrides.module_overrides![row.role]) {
      planWithOverrides.module_overrides![row.role] = row.module_id;
    }
  }
  if (Object.keys(planWithOverrides.module_overrides || {}).length > 0) {
    notes.push(`Module overrides applied: ${JSON.stringify(planWithOverrides.module_overrides)}`);
  }

  const { recipe: adaptedRecipe, notes: topoNotes } = adaptRecipeToInventory(recipe, planWithOverrides);
  notes.push(...topoNotes);
  if (adaptedRecipe.modules.length !== recipe.modules.length) {
    notes.push(
      `Inventory topology: ${adaptedRecipe.modules.length} modules (was ${recipe.modules.length}).`,
    );
  }

  // Materialize role -> nodeId; build BuildGraph nodes.
  const idOf = new Map<string, string>();
  const nodes = adaptedRecipe.modules.map((m, i) => {
    const nodeId = `n${i + 1}`;
    idOf.set(m.role, nodeId);
    return { id: nodeId, moduleId: m.moduleId };
  });

  // Resolve wires; drop (with warning) any whose roles aren't present.
  const wires = adaptedRecipe.wires.flatMap((w, i) => {
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

  if (adaptedRecipe.notes) notes.push(...adaptedRecipe.notes);

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

/** Engine export: hand-curated recipes + capability fallback map for Python parity. */
export const CATALOG_RECIPES = RECIPES;
export const BUILD_CATALOG_CAPABILITY_GROUPS = BUILD_CATALOG_CAPS;
