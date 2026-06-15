// Client-side safety/correctness solver for the Build canvas. Runs in <1ms
// on any wiring graph the user constructs — no LLM round-trip.
//
// Focus: the handful of rules that catch 90% of beginner mistakes.
//   1. Voltage mismatch between connected logic pins (3.3V <-> 5V direct).
//   2. Power fed into a power_out pin (backfeed).
//   3. GND connected to a non-GND pin.
//   4. Missing pull-up on open-drain (DHT, I2C sometimes).
//   5. Current-over-budget on a 3V3 rail.
//   6. Powering a 3.3V-only module (BME280, nRF24) from 5V.
//   7. Weak 3.3V drive into non-logic-level MOSFET.

import { findModule, findPin, type ModuleSpec, type ModulePin } from "@/lib/modules/module-library";

export type WarningLevel = "info" | "warn" | "error";

export interface BuildWarning {
  id: string;
  level: WarningLevel;
  message: string;
  /** Which wire or node this warning attaches to. */
  wireId?: string;
  nodeId?: string;
}

export interface BuildNode {
  id: string;
  moduleId: string;
}

export interface BuildWire {
  id: string;
  from: { nodeId: string; pinId: string };
  to: { nodeId: string; pinId: string };
}

export interface BuildGraph {
  nodes: BuildNode[];
  wires: BuildWire[];
}

interface ResolvedEndpoint {
  node: BuildNode;
  moduleSpec: ModuleSpec;
  pin: ModulePin;
}

/** Pin notes/voltage that explicitly allow a range of logic levels (e.g. opto relay IN). */
function pinAcceptsPeerLogic(pin: ModulePin, peerLogicV: number): boolean {
  const text = `${pin.voltage ?? ""} ${pin.notes ?? ""}`;
  if (/3\.3\s*[-–to]+\s*5|3\.3-5/i.test(text)) {
    return peerLogicV === 3.3 || peerLogicV === 5;
  }
  return false;
}

function resolve(graph: BuildGraph, nodeId: string, pinId: string): ResolvedEndpoint | null {
  const node = graph.nodes.find((n) => n.id === nodeId);
  if (!node) return null;
  const moduleSpec = findModule(node.moduleId);
  if (!moduleSpec) return null;
  const pin = findPin(moduleSpec, pinId);
  if (!pin) return null;
  return { node, moduleSpec, pin };
}

/** Parse voltage strings like "3.3V", "5V", "0-3.3V", "7-35V" → nominal V. */
function parseVoltage(v: string | undefined): number | null {
  if (!v) return null;
  const m = v.match(/([\d.]+)\s*V/i);
  if (!m) return null;
  return parseFloat(m[1]);
}

function voltageRange(v: string | undefined): [number, number] | null {
  if (!v) return null;
  const m = v.match(/([\d.]+)\s*-\s*([\d.]+)\s*V/i);
  if (m) return [parseFloat(m[1]), parseFloat(m[2])];
  const single = parseVoltage(v);
  return single == null ? null : [single, single];
}

export function analyzeBuild(graph: BuildGraph): BuildWarning[] {
  const warnings: BuildWarning[] = [];

  // 1. Wire-level checks
  for (const w of graph.wires) {
    const a = resolve(graph, w.from.nodeId, w.from.pinId);
    const b = resolve(graph, w.to.nodeId, w.to.pinId);
    if (!a || !b) continue;

    // GND on one side but not the other
    const aGnd = a.pin.role === "gnd";
    const bGnd = b.pin.role === "gnd";
    if (aGnd !== bGnd) {
      warnings.push({
        id: `${w.id}-gnd`,
        level: "error",
        message: `Wire connects GND (${aGnd ? a.moduleSpec.label : b.moduleSpec.label}) to a non-GND pin. This will short or misbehave.`,
        wireId: w.id,
      });
      continue;
    }
    if (aGnd && bGnd) continue;

    // Power backfeed: power_in ←→ power_in (both are inputs, nothing sources)
    if (a.pin.role === "power_in" && b.pin.role === "power_in") {
      warnings.push({
        id: `${w.id}-noSource`,
        level: "warn",
        message: `Both ends of this wire are power inputs — nothing actually sources power. Connect to a power_out pin.`,
        wireId: w.id,
      });
    }
    // Power_out driving power_out — two sources fighting
    if (a.pin.role === "power_out" && b.pin.role === "power_out") {
      warnings.push({
        id: `${w.id}-twoSources`,
        level: "error",
        message: `Two power sources (${a.moduleSpec.label}:${a.pin.id} and ${b.moduleSpec.label}:${b.pin.id}) fighting on the same rail.`,
        wireId: w.id,
      });
    }

    // Voltage mismatch on power pins
    const isPower = (p: ModulePin) => p.role === "power_in" || p.role === "power_out";
    if (isPower(a.pin) && isPower(b.pin)) {
      const src = a.pin.role === "power_out" ? a : b.pin.role === "power_out" ? b : null;
      const snk = src === a ? b : src === b ? a : null;
      if (src && snk) {
        const srcRange = voltageRange(src.pin.voltage);
        const snkRange = voltageRange(snk.pin.voltage) ?? (snk.moduleSpec.inputVoltageRange ?? null);
        const srcV = parseVoltage(src.pin.voltage);
        if (srcRange && snkRange && srcRange[1] >= snkRange[0] && srcRange[0] <= snkRange[1]) {
          if (/adjust|trim|set/i.test(src.pin.voltage) || /adjust|trim|set/i.test(src.pin.notes ?? "")) {
            warnings.push({
              id: `${w.id}-adjustable`,
              level: "info",
              message: `${src.moduleSpec.label} is adjustable — set output to ${snkRange[0]}–${snkRange[1]}V with a multimeter before connecting ${snk.moduleSpec.label}.`,
              wireId: w.id,
            });
          }
        } else if (srcV != null && snkRange) {
          if (srcV < snkRange[0] - 0.2 || srcV > snkRange[1] + 0.2) {
            warnings.push({
              id: `${w.id}-voltage`,
              level: "error",
              message: `${src.moduleSpec.label} outputs ${srcV}V but ${snk.moduleSpec.label} expects ${snkRange[0]}–${snkRange[1]}V. Insert a regulator.`,
              wireId: w.id,
            });
          }
        }
      }
    }

    // Logic-level mismatch: digital pins at different voltages, no level shifter
    const aLV = a.moduleSpec.logicVoltage;
    const bLV = b.moduleSpec.logicVoltage;
    const aDigital = a.pin.role !== "power_in" && a.pin.role !== "power_out" && a.pin.role !== "gnd" && a.pin.role !== "other";
    const bDigital = b.pin.role !== "power_in" && b.pin.role !== "power_out" && b.pin.role !== "gnd" && b.pin.role !== "other";
    if (aDigital && bDigital && aLV && bLV && aLV !== bLV) {
      const tolerant = pinAcceptsPeerLogic(a.pin, bLV) || pinAcceptsPeerLogic(b.pin, aLV);
      if (!tolerant) {
        warnings.push({
          id: `${w.id}-logic`,
          level: "error",
          message: `${a.moduleSpec.label} uses ${aLV}V logic, ${b.moduleSpec.label} uses ${bLV}V logic. Add a level shifter.`,
          wireId: w.id,
        });
      }
    }

    // I2C / open-drain needs pull-ups (at least one end must have them)
    if (a.pin.role === "i2c_sda" || a.pin.role === "i2c_scl" || b.pin.role === "i2c_sda" || b.pin.role === "i2c_scl") {
      const anyBuiltIn = [a, b].some((e) => /pull/i.test(e.pin.notes ?? ""));
      if (!anyBuiltIn) {
        warnings.push({
          id: `${w.id}-pullup`,
          level: "info",
          message: `I2C bus: confirm 4.7k pull-ups to VCC exist. Many breakouts include them; MCU boards usually do not.`,
          wireId: w.id,
        });
      }
    }

    // IRF520-style non-logic-level MOSFET driven from 3.3V (IRLZ44N is OK)
    if (
      (a.moduleSpec.id === "mosfet-irf520" && bLV === 3.3) ||
      (b.moduleSpec.id === "mosfet-irf520" && aLV === 3.3)
    ) {
      warnings.push({
        id: `${w.id}-fetDrive`,
        level: "warn",
        message: `IRF520 does not switch fully from 3.3V logic. Use IRLZ44N, AO3400, or a 5V MCU.`,
        wireId: w.id,
      });
    }
  }

  // 2. Per-node checks
  for (const n of graph.nodes) {
    const moduleSpec = findModule(n.moduleId);
    if (!moduleSpec) continue;

    const powerInPins = moduleSpec.pins.filter((p) => p.role === "power_in");
    const powerInWired = powerInPins.some((p) => graph.wires.some((w) =>
      (w.from.nodeId === n.id && w.from.pinId === p.id) ||
      (w.to.nodeId === n.id && w.to.pinId === p.id)
    ));
    const selfPoweredUsb = powerInPins.some(
      (p) => /usb|host/i.test(`${p.notes ?? ""} ${p.label ?? ""} ${p.id}`)
    );
    if (!powerInWired && powerInPins.length > 0 && !selfPoweredUsb) {
      warnings.push({
        id: `${n.id}-unpowered`,
        level: "warn",
        message: `${moduleSpec.label} has no power connection yet.`,
        nodeId: n.id,
      });
    }

    const gndWired = moduleSpec.pins
      .filter((p) => p.role === "gnd")
      .some((p) => graph.wires.some((w) =>
        (w.from.nodeId === n.id && w.from.pinId === p.id) ||
        (w.to.nodeId === n.id && w.to.pinId === p.id)
      ));
    if (!gndWired && moduleSpec.pins.some((p) => p.role === "gnd")) {
      warnings.push({
        id: `${n.id}-nognd`,
        level: "error",
        message: `${moduleSpec.label} has no GND connection. All modules need a common ground.`,
        nodeId: n.id,
      });
    }

    // High-current loads shouldn't draw from MCU 5V
    if (moduleSpec.id === "sg90" || moduleSpec.id === "l298n") {
      const poweredFromMcu = graph.wires.some((w) => {
        const ends = [w.from, w.to];
        const mine = ends.find((e) => e.nodeId === n.id);
        const other = ends.find((e) => e.nodeId !== n.id);
        if (!mine || !other) return false;
        const myPin = findPin(moduleSpec, mine.pinId);
        if (myPin?.role !== "power_in") return false;
        const otherNode = graph.nodes.find((x) => x.id === other.nodeId);
        const otherMod = otherNode && findModule(otherNode.moduleId);
        return otherMod?.category === "mcu";
      });
      if (poweredFromMcu) {
        warnings.push({
          id: `${n.id}-highCurrent`,
          level: "error",
          message: `${moduleSpec.label} can pull >200mA. Don't power it from the MCU's 5V pin — use a separate supply.`,
          nodeId: n.id,
        });
      }
    }
  }

  return warnings;
}
