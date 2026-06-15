import type { BuildGraph } from "@/lib/rules/safety-rules";
import { findModule } from "@/lib/modules/module-library";

const LEVEL_SHIFTER_ID = "level-shifter-4ch";
const HV_TO_LV: Record<string, string> = {
  HV1: "LV1", HV2: "LV2", HV3: "LV3", HV4: "LV4",
};
const LV_TO_HV: Record<string, string> = {
  LV1: "HV1", LV2: "HV2", LV3: "LV3", LV4: "HV4",
};

export function findMcuNodeId(graph: BuildGraph): string | undefined {
  return graph.nodes.find((n) => findModule(n.moduleId)?.category === "mcu")?.id;
}

/** Arduino/ESP32 pin id → numeric pin for digitalWrite/analogRead. */
export function parsePinNumber(pinId: string): number | null {
  const gpio = pinId.match(/^GPIO(\d+)$/i);
  if (gpio) return Number.parseInt(gpio[1], 10);
  const d = pinId.match(/^D(\d+)$/i);
  if (d) return Number.parseInt(d[1], 10);
  const a = pinId.match(/^A(\d+)$/i);
  if (a) return Number.parseInt(a[1], 10);
  const gp = pinId.match(/^GP(\d+)$/i);
  if (gp) return Number.parseInt(gp[1], 10);
  return null;
}

function nodeById(graph: BuildGraph, nodeId: string) {
  return graph.nodes.find((n) => n.id === nodeId);
}

/** Trace from a peripheral pin back to the MCU pin id (handles level shifters). */
export function traceMcuPin(
  graph: BuildGraph,
  targetModuleId: string,
  targetPinId: string,
): string | undefined {
  const mcuNodeId = findMcuNodeId(graph);
  const targetNode = graph.nodes.find((n) => n.moduleId === targetModuleId);
  if (!mcuNodeId || !targetNode) return undefined;

  const visited = new Set<string>();

  function walk(nodeId: string, pinId: string): string | undefined {
    const key = `${nodeId}:${pinId}`;
    if (visited.has(key)) return undefined;
    visited.add(key);

    if (nodeId === mcuNodeId) return pinId;

    for (const w of graph.wires) {
      let other: { nodeId: string; pinId: string } | undefined;
      if (w.from.nodeId === nodeId && w.from.pinId === pinId) other = w.to;
      else if (w.to.nodeId === nodeId && w.to.pinId === pinId) other = w.from;
      if (!other) continue;

      const otherNode = nodeById(graph, other.nodeId);
      if (!otherNode) continue;

      if (otherNode.moduleId === LEVEL_SHIFTER_ID) {
        const paired = HV_TO_LV[other.pinId] ?? LV_TO_HV[other.pinId];
        if (paired) {
          const via = walk(other.nodeId, paired);
          if (via) return via;
        }
      }

      const direct = walk(other.nodeId, other.pinId);
      if (direct) return direct;
    }
    return undefined;
  }

  return walk(targetNode.id, targetPinId);
}

export interface GraphPinMap {
  soil?: number;
  pump?: number;
  dhtData?: number;
  trig?: number;
  echo?: number;
  relay?: number;
  motorIn1?: number;
  motorIn2?: number;
  spi?: { cs?: number; rst?: number; dc?: number; mosi?: number; sck?: number };
  i2c?: { sda?: number; scl?: number };
  sourcedFromGraph: boolean;
}

function pinNum(graph: BuildGraph, moduleId: string, pinId: string): number | undefined {
  const mcuPin = traceMcuPin(graph, moduleId, pinId);
  if (!mcuPin) return undefined;
  const n = parsePinNumber(mcuPin);
  return n ?? undefined;
}

const SPI_MOSI = new Set(["SDI", "SDA", "MOSI", "DIN"]);
const SPI_SCK = new Set(["SCK", "SCL", "CLK"]);
const SPI_CS = new Set(["CS"]);
const SPI_RST = new Set(["RST", "RES"]);
const SPI_DC = new Set(["DC"]);

export function extractPinsFromGraph(graph: BuildGraph): GraphPinMap {
  const out: GraphPinMap = { sourcedFromGraph: false };
  const moduleIds = new Set(graph.nodes.map((n) => n.moduleId));

  if (moduleIds.has("soil_moisture")) {
    const soil = pinNum(graph, "soil_moisture", "A0");
    if (soil !== undefined) { out.soil = soil; out.sourcedFromGraph = true; }
  }

  if (moduleIds.has("mosfet-irlz44n")) {
    const pump = pinNum(graph, "mosfet-irlz44n", "SIG");
    if (pump !== undefined) { out.pump = pump; out.sourcedFromGraph = true; }
  }

  if (moduleIds.has("dht22")) {
    const data = pinNum(graph, "dht22", "DATA");
    if (data !== undefined) { out.dhtData = data; out.sourcedFromGraph = true; }
  }

  if (moduleIds.has("hc-sr04")) {
    const trig = pinNum(graph, "hc-sr04", "TRIG");
    const echo = pinNum(graph, "hc-sr04", "ECHO");
    if (trig !== undefined) { out.trig = trig; out.sourcedFromGraph = true; }
    if (echo !== undefined) { out.echo = echo; out.sourcedFromGraph = true; }
  }

  if (moduleIds.has("relay-1ch-5v")) {
    const relay = pinNum(graph, "relay-1ch-5v", "IN");
    if (relay !== undefined) { out.relay = relay; out.sourcedFromGraph = true; }
  }

  if (moduleIds.has("l298n")) {
    const in1 = pinNum(graph, "l298n", "IN1");
    const in2 = pinNum(graph, "l298n", "IN2");
    if (in1 !== undefined) { out.motorIn1 = in1; out.sourcedFromGraph = true; }
    if (in2 !== undefined) { out.motorIn2 = in2; out.sourcedFromGraph = true; }
  }

  const mcuNodeId = findMcuNodeId(graph);
  if (mcuNodeId) {
    const sda = traceMcuPin(graph, "bme280", "SDA")
      ?? traceMcuPin(graph, "ssd1306-128x64", "SDA");
    const scl = traceMcuPin(graph, "bme280", "SCL")
      ?? traceMcuPin(graph, "ssd1306-128x64", "SCL");
    const sdaN = sda ? parsePinNumber(sda) : null;
    const sclN = scl ? parsePinNumber(scl) : null;
    if (sdaN !== null && sclN !== null) {
      out.i2c = { sda: sdaN, scl: sclN };
      out.sourcedFromGraph = true;
    }
  }

  for (const tftId of ["ili9341_tft", "st7735_tft"]) {
    if (!moduleIds.has(tftId)) continue;
    const spec = findModule(tftId);
    if (!spec) continue;
    const spi: NonNullable<GraphPinMap["spi"]> = {};
    for (const p of spec.pins) {
      const n = pinNum(graph, tftId, p.id);
      if (n === undefined) continue;
      if (SPI_CS.has(p.id)) spi.cs = n;
      else if (SPI_RST.has(p.id)) spi.rst = n;
      else if (SPI_DC.has(p.id)) spi.dc = n;
      else if (SPI_MOSI.has(p.id) || p.role === "spi_mosi") spi.mosi = n;
      else if (SPI_SCK.has(p.id) || p.role === "spi_sck") spi.sck = n;
    }
    if (Object.keys(spi).length > 0) {
      out.spi = spi;
      out.sourcedFromGraph = true;
    }
    break;
  }

  return out;
}
