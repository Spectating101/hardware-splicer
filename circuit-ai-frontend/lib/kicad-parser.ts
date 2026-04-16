/**
 * Client-side parser for KiCad PCB files (.kicad_pcb).
 *
 * Backed by the proper s-expression tokenizer in `./kicad/sexpr.ts`, so we
 * no longer silently drop `(gr_arc ...)`, `(zone ...)`, custom pad primitives,
 * or anything that spans multiple lines.
 */

import {
  parseSexpr,
  childrenNamed,
  firstChild,
  stringProp,
  numberProp,
  atomStr,
  atomNum,
  isSList,
  type SList,
  type SValue,
} from "./kicad/sexpr";

export interface KicadPad {
  num: string;
  netId: number;
  netName: string;
  // pad center in WORLD mm (after applying footprint position + rotation)
  wx: number;
  wy: number;
}

export interface KicadComponent {
  ref: string;
  value: string;
  footprint: string; // e.g. "Resistor_SMD:R_0805_2012Metric"
  layer: string; // "F.Cu" | "B.Cu" | etc.
  x: number;
  y: number;
  rot_deg: number;
  pads: KicadPad[];
}

export interface KicadSegment {
  start: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
  layer: string;
  net_id: number;
  net_name: string;
}

export interface KicadVia {
  x: number;
  y: number;
  size_mm: number;
  drill_mm: number;
  net_id: number;
}

export interface KicadBoardInfo {
  componentCount: number;
  layerCount: number;
  netCount: number;
  components: KicadComponent[];
  segments: KicadSegment[];
  vias: KicadVia[];
  nets: Array<{ id: number; name: string }>;
  boardWidthMm?: number;
  boardHeightMm?: number;
}

/** Read a `(at X Y [ROT])` child as a triple with defaults. */
function readAt(list: SList): { x: number; y: number; rot: number } {
  const at = firstChild(list, "at");
  if (!at) return { x: 0, y: 0, rot: 0 };
  return {
    x: atomNum(at.rest[0]) ?? 0,
    y: atomNum(at.rest[1]) ?? 0,
    rot: atomNum(at.rest[2]) ?? 0,
  };
}

/** Read a `(layer "L")` or `(layer L)` child → layer name. */
function readLayer(list: SList, fallback = "F.Cu"): string {
  const l = firstChild(list, "layer");
  if (!l) return fallback;
  return atomStr(l.rest[0]) ?? fallback;
}

/** Read a `(start X Y)` / `(end X Y)` style point. */
function readPoint(list: SList, name: string): { x: number; y: number } | undefined {
  const p = firstChild(list, name);
  if (!p) return undefined;
  const x = atomNum(p.rest[0]);
  const y = atomNum(p.rest[1]);
  if (x === undefined || y === undefined) return undefined;
  return { x, y };
}

/** Read a pad's `(net N "NAME")` sub-list. */
function readNetRef(list: SList): { id: number; name: string } | undefined {
  const n = firstChild(list, "net");
  if (!n) return undefined;
  const id = atomNum(n.rest[0]);
  if (id === undefined) return undefined;
  const name = atomStr(n.rest[1]) ?? "";
  return { id, name };
}

/** Extract the Reference / Value property from a footprint, with fallbacks. */
function readProperty(fp: SList, key: string): string | undefined {
  for (const prop of childrenNamed(fp, "property")) {
    if (atomStr(prop.rest[0]) === key) return atomStr(prop.rest[1]);
  }
  // Legacy: (fp_text reference "R1" ...)
  for (const t of childrenNamed(fp, "fp_text")) {
    const kind = atomStr(t.rest[0])?.toLowerCase();
    if (kind === key.toLowerCase()) return atomStr(t.rest[1]);
  }
  return undefined;
}

function parseFootprint(fp: SList): KicadComponent {
  const footprintLib = atomStr(fp.rest[0]) ?? "";
  const layer = readLayer(fp, "F.Cu");
  const { x, y, rot: rot_deg } = readAt(fp);

  const ref = readProperty(fp, "Reference") ?? (footprintLib || "?");
  const value = readProperty(fp, "Value") ?? "";

  const theta = (rot_deg * Math.PI) / 180;
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);

  const pads: KicadPad[] = [];
  for (const pad of childrenNamed(fp, "pad")) {
    const num = atomStr(pad.rest[0]) ?? "";
    const padAt = readAt(pad);
    const net = readNetRef(pad);
    const netId = net?.id ?? 0;
    const netName = net?.name ?? "";
    const wx = x + padAt.x * cos - padAt.y * sin;
    const wy = y + padAt.x * sin + padAt.y * cos;
    pads.push({ num, netId, netName, wx, wy });
  }

  return { ref, value, footprint: footprintLib, layer, x, y, rot_deg, pads };
}

export function parseKicadPcb(text: string): KicadBoardInfo {
  let root: SList;
  try {
    root = parseSexpr(text);
  } catch {
    // Malformed file — return empty scaffold rather than crash the UI
    return {
      componentCount: 0,
      layerCount: 2,
      netCount: 0,
      components: [],
      segments: [],
      vias: [],
      nets: [],
    };
  }

  // ── Nets: (net 0 "") ... (net N "NAME")
  const nets: Array<{ id: number; name: string }> = [];
  for (const n of childrenNamed(root, "net")) {
    const id = atomNum(n.rest[0]);
    const name = atomStr(n.rest[1]) ?? "";
    if (id === undefined || id === 0) continue;
    nets.push({ id, name });
  }
  const netNameById = new Map(nets.map((n) => [n.id, n.name] as const));

  // ── Layer count: (layers (0 "F.Cu" signal) (1 "In1.Cu" signal) ... )
  let copperLayerCount = 0;
  const layersBlock = firstChild(root, "layers");
  if (layersBlock) {
    const seen = new Set<string>();
    for (const child of layersBlock.rest) {
      if (!isSList(child)) continue;
      // child.head is the layer index as a string (e.g. "0", "31"); the
      // actual layer name is the first atom of `rest`.
      const name = atomStr(child.rest[0]);
      if (name && name.endsWith(".Cu")) seen.add(name);
    }
    copperLayerCount = seen.size;
  }

  // ── Footprints
  const footprints = childrenNamed(root, "footprint");
  // Some older files use `module` instead of `footprint`
  const modules = childrenNamed(root, "module");
  const components: KicadComponent[] = [...footprints, ...modules].map(parseFootprint);

  // ── Segments
  const segments: KicadSegment[] = [];
  for (const seg of childrenNamed(root, "segment")) {
    const start = readPoint(seg, "start");
    const end = readPoint(seg, "end");
    if (!start || !end) continue;
    const width_mm = numberProp(seg, "width") ?? 0.25;
    const layer = readLayer(seg, "F.Cu");
    const netId = numberProp(seg, "net") ?? 0;
    segments.push({
      start, end, width_mm, layer,
      net_id: netId,
      net_name: netNameById.get(netId) ?? "",
    });
  }

  // ── Vias
  const vias: KicadVia[] = [];
  for (const via of childrenNamed(root, "via")) {
    const at = firstChild(via, "at");
    if (!at) continue;
    const x = atomNum(at.rest[0]) ?? 0;
    const y = atomNum(at.rest[1]) ?? 0;
    const size_mm = numberProp(via, "size") ?? 0.8;
    const drill_mm = numberProp(via, "drill") ?? 0.4;
    const net_id = numberProp(via, "net") ?? 0;
    vias.push({ x, y, size_mm, drill_mm, net_id });
  }

  // ── Board bounds: prefer Edge.Cuts geometry if present, else component spread.
  let boardWidthMm: number | undefined;
  let boardHeightMm: number | undefined;
  const edgePts: Array<{ x: number; y: number }> = [];
  const collectPt = (p?: { x: number; y: number }) => { if (p) edgePts.push(p); };
  for (const head of ["gr_line", "gr_arc", "gr_rect", "gr_circle", "gr_poly"]) {
    for (const g of childrenNamed(root, head)) {
      if (readLayer(g, "") !== "Edge.Cuts") continue;
      collectPt(readPoint(g, "start"));
      collectPt(readPoint(g, "end"));
      collectPt(readPoint(g, "center"));
      // gr_poly: (pts (xy X Y) (xy X Y) ...)
      const pts = firstChild(g, "pts");
      if (pts) {
        for (const xy of childrenNamed(pts, "xy")) {
          const px = atomNum(xy.rest[0]);
          const py = atomNum(xy.rest[1]);
          if (px !== undefined && py !== undefined) edgePts.push({ x: px, y: py });
        }
      }
    }
  }
  const pointsForBounds: Array<{ x: number; y: number }> =
    edgePts.length > 0
      ? edgePts
      : components.map((c) => ({ x: c.x, y: c.y }));
  if (pointsForBounds.length > 0) {
    const xs = pointsForBounds.map((p) => p.x);
    const ys = pointsForBounds.map((p) => p.y);
    const pad = edgePts.length > 0 ? 0 : 20;
    boardWidthMm = Math.max(...xs) - Math.min(...xs) + pad;
    boardHeightMm = Math.max(...ys) - Math.min(...ys) + pad;
  }

  // ── Net count (excluding the unconnected pseudo-net 0)
  const netCount = nets.length;

  // Silence unused import warning for SValue (exported type convenience)
  void (undefined as unknown as SValue);

  return {
    componentCount: components.length,
    layerCount: Math.max(2, copperLayerCount),
    netCount,
    components,
    segments,
    vias,
    nets,
    boardWidthMm,
    boardHeightMm,
  };
}

/**
 * Generate ratsnest airwires — straight lines between pads sharing a net —
 * for any net that has 2+ pads. Uses a simple star-topology from the first pad.
 */
export function generateAirwires(components: KicadComponent[]): KicadSegment[] {
  const byNet = new Map<number, { name: string; pads: KicadPad[] }>();
  for (const c of components) {
    for (const p of c.pads) {
      if (p.netId <= 0) continue;
      const bucket = byNet.get(p.netId) ?? { name: p.netName, pads: [] };
      bucket.pads.push(p);
      byNet.set(p.netId, bucket);
    }
  }
  const out: KicadSegment[] = [];
  for (const [netId, { name, pads }] of byNet) {
    if (pads.length < 2) continue;
    const root = pads[0];
    for (let i = 1; i < pads.length; i++) {
      out.push({
        start: { x: root.wx, y: root.wy },
        end: { x: pads[i].wx, y: pads[i].wy },
        width_mm: 0.08,
        layer: "Airwire",
        net_id: netId,
        net_name: name,
      });
    }
  }
  return out;
}
