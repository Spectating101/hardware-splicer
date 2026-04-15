/**
 * Infer a component's physical footprint size from its KiCad library name.
 * Returns the bounding box (mm) in the footprint's local frame — x is "along the pins",
 * y is "across the body". The canvas applies rot_deg after drawing.
 *
 * This is purely pattern-based; when the backend eventually ships real pad geometry
 * the canvas should prefer that source and fall back to this.
 */

export interface FootprintSize {
  w_mm: number;         // body + pads extent along X (local)
  h_mm: number;         // along Y (local)
  kind: "passive" | "ic" | "connector" | "module" | "diode" | "inductor" | "crystal" | "mounting" | "led" | "unknown";
  pinCount?: number;    // best-effort
}

/** Common IPC/industry metric passive sizes — LxW in mm, with small pad allowance. */
const PASSIVE_IMPERIAL: Record<string, [number, number]> = {
  "0201": [0.8, 0.6],
  "0402": [1.4, 0.8],
  "0603": [1.9, 1.0],
  "0805": [2.4, 1.4],
  "1206": [3.6, 1.8],
  "1210": [3.6, 2.8],
  "2512": [6.5, 3.4],
};

const PASSIVE_METRIC: Record<string, [number, number]> = {
  "0603Metric": [0.8, 0.6],  // imperial 0201
  "1005Metric": [1.4, 0.8],  // imperial 0402
  "1608Metric": [1.9, 1.0],  // imperial 0603
  "2012Metric": [2.4, 1.4],  // imperial 0805
  "3216Metric": [3.6, 1.8],  // imperial 1206
  "3225Metric": [3.6, 2.8],  // imperial 1210
};

const SOIC_PITCH = 1.27;
const SSOP_PITCH = 0.65;

function parseSoicLike(name: string): FootprintSize | null {
  // SOIC-8_3.9x4.9mm, SOP-16_4.4x10.4mm, etc.
  const m = name.match(/(SOIC|SOP|TSSOP|SSOP|MSOP|VSSOP)[-_]?(\d+)[-_]?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm/i);
  if (!m) return null;
  const pinCount = parseInt(m[2], 10);
  const w = parseFloat(m[3]);
  const h = parseFloat(m[4]);
  return { w_mm: Math.max(w, h) + 1, h_mm: Math.min(w, h) + 1.5, kind: "ic", pinCount };
}

function parseQfpLike(name: string): FootprintSize | null {
  // LQFP-48_7x7mm, TQFP-100_14x14mm
  const m = name.match(/(LQFP|TQFP|QFP|QFN|DFN|VQFN)[-_]?(\d+)[-_]?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm/i);
  if (!m) return null;
  return {
    w_mm: parseFloat(m[3]),
    h_mm: parseFloat(m[4]),
    kind: "ic",
    pinCount: parseInt(m[2], 10),
  };
}

function parseBgaLike(name: string): FootprintSize | null {
  const m = name.match(/BGA[-_]?(\d+)[-_]?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm/i);
  if (!m) return null;
  return {
    w_mm: parseFloat(m[2]),
    h_mm: parseFloat(m[3]),
    kind: "ic",
    pinCount: parseInt(m[1], 10),
  };
}

function parsePassive(name: string): FootprintSize | null {
  // Resistor_SMD:R_0805_2012Metric, Capacitor_SMD:C_0603_1608Metric, etc.
  // Match imperial first (more distinctive).
  for (const [k, [w, h]] of Object.entries(PASSIVE_IMPERIAL)) {
    if (new RegExp(`[_:]${k}(?:[_\\s]|$)`).test(name)) return { w_mm: w, h_mm: h, kind: "passive", pinCount: 2 };
  }
  for (const [k, [w, h]] of Object.entries(PASSIVE_METRIC)) {
    if (name.includes(k)) return { w_mm: w, h_mm: h, kind: "passive", pinCount: 2 };
  }
  return null;
}

function parseConnector(name: string): FootprintSize | null {
  // PinHeader_1x04_P2.54mm_Vertical, Conn_01x08_P2.54mm, JST_PH_S3B-PH
  const pitchM = name.match(/P(\d+(?:\.\d+)?)mm/i);
  const countM = name.match(/(\d+)x(\d+)/);
  if (pitchM && countM) {
    const pitch = parseFloat(pitchM[1]);
    const rows = parseInt(countM[1], 10);
    const cols = parseInt(countM[2], 10);
    return {
      w_mm: cols * pitch + 1.2,
      h_mm: rows * pitch + 1.2,
      kind: "connector",
      pinCount: rows * cols,
    };
  }
  if (/USB|RJ45|HDMI|DB9|Terminal|Jack|Socket|Conn_/i.test(name)) {
    return { w_mm: 12, h_mm: 8, kind: "connector" };
  }
  return null;
}

function parseMounting(name: string): FootprintSize | null {
  const m = name.match(/MountingHole(?:.*?)(\d+(?:\.\d+)?)mm/i);
  if (m) {
    const d = parseFloat(m[1]);
    return { w_mm: d + 1.5, h_mm: d + 1.5, kind: "mounting" };
  }
  if (/MountingHole/i.test(name)) return { w_mm: 3.2, h_mm: 3.2, kind: "mounting" };
  return null;
}

function parseLed(name: string): FootprintSize | null {
  if (/LED_0603|LED_0402/i.test(name)) return { w_mm: 1.6, h_mm: 0.9, kind: "led", pinCount: 2 };
  if (/LED_0805/i.test(name)) return { w_mm: 2.2, h_mm: 1.4, kind: "led", pinCount: 2 };
  if (/LED_1206/i.test(name)) return { w_mm: 3.4, h_mm: 1.8, kind: "led", pinCount: 2 };
  if (/LED_D5\.0mm|LED_THT.*?5mm/i.test(name)) return { w_mm: 5.5, h_mm: 5.5, kind: "led", pinCount: 2 };
  return null;
}

function parseCrystal(name: string): FootprintSize | null {
  const m = name.match(/Crystal.*?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm/i);
  if (m) return { w_mm: parseFloat(m[1]), h_mm: parseFloat(m[2]), kind: "crystal", pinCount: 4 };
  if (/Crystal/i.test(name)) return { w_mm: 5.0, h_mm: 3.2, kind: "crystal", pinCount: 4 };
  return null;
}

function parseModule(name: string): FootprintSize | null {
  if (/ESP32.*?WROOM|ESP32-WROOM/i.test(name)) return { w_mm: 18, h_mm: 25.5, kind: "module", pinCount: 38 };
  if (/ESP32-S3-WROOM/i.test(name)) return { w_mm: 18, h_mm: 25.5, kind: "module", pinCount: 41 };
  if (/ESP-?12[EF]?/i.test(name)) return { w_mm: 16, h_mm: 24, kind: "module", pinCount: 22 };
  if (/RaspberryPi.*?Pico|RPi.*?Pico/i.test(name)) return { w_mm: 21, h_mm: 51, kind: "module", pinCount: 40 };
  if (/Arduino.*?Nano/i.test(name)) return { w_mm: 18, h_mm: 45, kind: "module", pinCount: 30 };
  if (/NRF24|nRF24/i.test(name)) return { w_mm: 15, h_mm: 29, kind: "module" };
  return null;
}

function fallbackByPrefix(ref: string): FootprintSize {
  const p = ref.replace(/\d+$/, "").toUpperCase();
  switch (p) {
    case "R": return { w_mm: 2.4, h_mm: 1.4, kind: "passive", pinCount: 2 };
    case "C": return { w_mm: 1.9, h_mm: 1.0, kind: "passive", pinCount: 2 };
    case "L": return { w_mm: 3.2, h_mm: 2.5, kind: "inductor", pinCount: 2 };
    case "D":
    case "DZ":
    case "DS": return { w_mm: 2.4, h_mm: 1.2, kind: "diode", pinCount: 2 };
    case "Q": return { w_mm: 3.0, h_mm: 2.5, kind: "ic", pinCount: 3 };
    case "U":
    case "IC": return { w_mm: 5.0, h_mm: 4.0, kind: "ic" };
    case "J":
    case "P":
    case "CN": return { w_mm: 7.0, h_mm: 5.0, kind: "connector" };
    case "Y":
    case "X":
    case "XT": return { w_mm: 5.0, h_mm: 3.2, kind: "crystal", pinCount: 4 };
    case "SW": return { w_mm: 6.0, h_mm: 6.0, kind: "connector" };
    case "LED": return { w_mm: 2.2, h_mm: 1.4, kind: "led", pinCount: 2 };
    case "H":
    case "MH": return { w_mm: 3.2, h_mm: 3.2, kind: "mounting" };
    default: return { w_mm: 3.0, h_mm: 3.0, kind: "unknown" };
  }
}

export function inferFootprintSize(footprintLib: string, ref: string): FootprintSize {
  const name = footprintLib || "";
  return (
    parseSoicLike(name) ??
    parseQfpLike(name) ??
    parseBgaLike(name) ??
    parsePassive(name) ??
    parseLed(name) ??
    parseCrystal(name) ??
    parseModule(name) ??
    parseConnector(name) ??
    parseMounting(name) ??
    fallbackByPrefix(ref)
  );
}

export function sizeKindColor(kind: FootprintSize["kind"]): string {
  switch (kind) {
    case "passive": return "#c0b280";
    case "ic": return "#222";
    case "connector": return "#1e3a5f";
    case "module": return "#0d3b1e";
    case "diode": return "#444";
    case "inductor": return "#3a2a1a";
    case "crystal": return "#4a4a4a";
    case "mounting": return "#555";
    case "led": return "#f5c04b";
    default: return "#333";
  }
}
