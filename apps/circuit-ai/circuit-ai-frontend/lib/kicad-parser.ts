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

export type KicadPadShape = "circle" | "oval" | "rect" | "roundrect" | "trapezoid" | "custom";
export type KicadPadType = "smd" | "thru_hole" | "np_thru_hole" | "connect";

export interface KicadPad {
  num: string;
  netId: number;
  netName: string;
  // pad center in WORLD mm (after applying footprint position + rotation)
  wx: number;
  wy: number;
  /** world rotation = footprint.rot + pad.rot */
  wrot_deg: number;
  shape: KicadPadShape;
  size_w_mm: number;
  size_h_mm: number;
  drill_mm: number;
  roundrect_ratio: number;
  type: KicadPadType;
}

export interface KicadSilkLine {
  layer: string;
  start: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
}

export interface KicadSilkArc {
  layer: string;
  start: { x: number; y: number };
  mid: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
}

export interface KicadSilkText {
  layer: string;
  text: string;
  at: { x: number; y: number; rot_deg: number };
  size_mm: number;
}

export interface KicadZone {
  layer: string;
  net_id: number;
  net_name: string;
  polygons: Array<Array<{ x: number; y: number }>>;
}

export interface KicadEdgeArc {
  start: { x: number; y: number };
  mid: { x: number; y: number };
  end: { x: number; y: number };
}

export interface KicadEdgeLine {
  start: { x: number; y: number };
  end: { x: number; y: number };
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
  zones: KicadZone[];
  silkLines: KicadSilkLine[];
  silkArcs: KicadSilkArc[];
  silkText: KicadSilkText[];
  edgeArcs: KicadEdgeArc[];
  edgeLines: KicadEdgeLine[];
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

/** `(size W H)` helper. */
function readSize(list: SList, name = "size"): { w: number; h: number } | undefined {
  const s = firstChild(list, name);
  if (!s) return undefined;
  const w = atomNum(s.rest[0]);
  const h = atomNum(s.rest[1]);
  if (w === undefined) return undefined;
  return { w, h: h ?? w };
}

function readPadShape(raw: string | undefined): KicadPadShape {
  switch ((raw ?? "").toLowerCase()) {
    case "circle": return "circle";
    case "oval": return "oval";
    case "rect": return "rect";
    case "roundrect": return "roundrect";
    case "trapezoid": return "trapezoid";
    case "custom": return "custom";
    default: return "rect";
  }
}

function readPadType(raw: string | undefined): KicadPadType {
  switch ((raw ?? "").toLowerCase()) {
    case "smd": return "smd";
    case "thru_hole": return "thru_hole";
    case "np_thru_hole": return "np_thru_hole";
    case "connect": return "connect";
    default: return "smd";
  }
}

/** `(drill D)` or `(drill oval W H)` → hole diameter in mm (larger axis). */
function readDrill(pad: SList): number {
  const d = firstChild(pad, "drill");
  if (!d) return 0;
  // Shape: (drill D), (drill D (offset X Y)), (drill oval W H)
  const first = d.rest[0];
  if (typeof first === "string" && first === "oval") {
    const w = atomNum(d.rest[1]) ?? 0;
    const h = atomNum(d.rest[2]) ?? 0;
    return Math.max(w, h);
  }
  return atomNum(first) ?? 0;
}

function parseFootprint(fp: SList, silkLines: KicadSilkLine[], silkArcs: KicadSilkArc[], silkText: KicadSilkText[]): KicadComponent {
  const footprintLib = atomStr(fp.rest[0]) ?? "";
  const layer = readLayer(fp, "F.Cu");
  const { x, y, rot: rot_deg } = readAt(fp);

  const ref = readProperty(fp, "Reference") ?? (footprintLib || "?");
  const value = readProperty(fp, "Value") ?? "";

  const theta = (rot_deg * Math.PI) / 180;
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  const rotatePt = (lx: number, ly: number) => ({
    x: x + lx * cos - ly * sin,
    y: y + lx * sin + ly * cos,
  });

  const pads: KicadPad[] = [];
  for (const pad of childrenNamed(fp, "pad")) {
    const num = atomStr(pad.rest[0]) ?? "";
    const type = readPadType(atomStr(pad.rest[1]));
    const shape = readPadShape(atomStr(pad.rest[2]));
    const padAt = readAt(pad);
    const size = readSize(pad) ?? { w: 1, h: 1 };
    const drill = readDrill(pad);
    const rratio = numberProp(pad, "roundrect_rratio") ?? (shape === "roundrect" ? 0.25 : 0);
    const net = readNetRef(pad);
    const netId = net?.id ?? 0;
    const netName = net?.name ?? "";
    const world = rotatePt(padAt.x, padAt.y);
    pads.push({
      num, netId, netName,
      wx: world.x, wy: world.y,
      wrot_deg: rot_deg + padAt.rot,
      shape,
      size_w_mm: size.w,
      size_h_mm: size.h,
      drill_mm: drill,
      roundrect_ratio: rratio,
      type,
    });
  }

  // ── Footprint silkscreen (fp_line / fp_arc / fp_text on *.SilkS) ──────
  for (const line of childrenNamed(fp, "fp_line")) {
    const lyr = readLayer(line, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const s = readPoint(line, "start");
    const e = readPoint(line, "end");
    if (!s || !e) continue;
    const widthStroke = firstChild(line, "stroke");
    const width = widthStroke ? numberProp(widthStroke, "width") ?? 0.12 : numberProp(line, "width") ?? 0.12;
    silkLines.push({
      layer: lyr,
      start: rotatePt(s.x, s.y),
      end: rotatePt(e.x, e.y),
      width_mm: width,
    });
  }
  for (const arc of childrenNamed(fp, "fp_arc")) {
    const lyr = readLayer(arc, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const s = readPoint(arc, "start");
    const m = readPoint(arc, "mid");
    const e = readPoint(arc, "end");
    if (!s || !e) continue;
    const widthStroke = firstChild(arc, "stroke");
    const width = widthStroke ? numberProp(widthStroke, "width") ?? 0.12 : numberProp(arc, "width") ?? 0.12;
    silkArcs.push({
      layer: lyr,
      start: rotatePt(s.x, s.y),
      mid: m ? rotatePt(m.x, m.y) : rotatePt((s.x + e.x) / 2, (s.y + e.y) / 2),
      end: rotatePt(e.x, e.y),
      width_mm: width,
    });
  }
  for (const t of childrenNamed(fp, "fp_text")) {
    const lyr = readLayer(t, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const kind = atomStr(t.rest[0])?.toLowerCase();
    // `user` text is always drawn; `reference` and `value` only when visible
    // (KiCad emits a `hide` token when hidden — we rely on that absence).
    const hide = childrenNamed(t, "hide").length > 0 || t.rest.some((r) => r === "hide");
    if (hide) continue;
    const txt = atomStr(t.rest[1]) ?? "";
    const at = readAt(t);
    const effects = firstChild(t, "effects");
    const font = effects ? firstChild(effects, "font") : undefined;
    const sz = font ? readSize(font) : undefined;
    silkText.push({
      layer: lyr,
      text: kind === "reference" ? ref : txt,
      at: { ...rotatePt(at.x, at.y), rot_deg: rot_deg + at.rot },
      size_mm: sz?.w ?? 1.0,
    });
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
      zones: [],
      silkLines: [],
      silkArcs: [],
      silkText: [],
      edgeArcs: [],
      edgeLines: [],
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

  // ── Footprints (also harvest their silkscreen as we go)
  const silkLines: KicadSilkLine[] = [];
  const silkArcs: KicadSilkArc[] = [];
  const silkText: KicadSilkText[] = [];
  const footprints = childrenNamed(root, "footprint");
  const modules = childrenNamed(root, "module");
  const components: KicadComponent[] = [...footprints, ...modules].map((fp) =>
    parseFootprint(fp, silkLines, silkArcs, silkText),
  );

  // ── Top-level graphic silkscreen (logo outlines, board labels, etc.)
  for (const gl of childrenNamed(root, "gr_line")) {
    const lyr = readLayer(gl, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const s = readPoint(gl, "start");
    const e = readPoint(gl, "end");
    if (!s || !e) continue;
    const ws = firstChild(gl, "stroke");
    const width = ws ? numberProp(ws, "width") ?? 0.12 : numberProp(gl, "width") ?? 0.12;
    silkLines.push({ layer: lyr, start: s, end: e, width_mm: width });
  }
  for (const ga of childrenNamed(root, "gr_arc")) {
    const lyr = readLayer(ga, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const s = readPoint(ga, "start");
    const m = readPoint(ga, "mid");
    const e = readPoint(ga, "end");
    if (!s || !e) continue;
    const ws = firstChild(ga, "stroke");
    const width = ws ? numberProp(ws, "width") ?? 0.12 : numberProp(ga, "width") ?? 0.12;
    silkArcs.push({
      layer: lyr, start: s,
      mid: m ?? { x: (s.x + e.x) / 2, y: (s.y + e.y) / 2 },
      end: e, width_mm: width,
    });
  }
  for (const gt of childrenNamed(root, "gr_text")) {
    const lyr = readLayer(gt, "");
    if (!lyr.endsWith(".SilkS")) continue;
    const txt = atomStr(gt.rest[0]) ?? "";
    const at = readAt(gt);
    const effects = firstChild(gt, "effects");
    const font = effects ? firstChild(effects, "font") : undefined;
    const sz = font ? readSize(font) : undefined;
    silkText.push({
      layer: lyr, text: txt,
      at: { x: at.x, y: at.y, rot_deg: at.rot },
      size_mm: sz?.w ?? 1.0,
    });
  }

  // ── Edge.Cuts arcs — captured separately so we can draw a curved board
  //    outline later. (Plain edge lines are picked up via gr_line above for
  //    bbox purposes only.)
  const edgeArcs: KicadEdgeArc[] = [];
  for (const ga of childrenNamed(root, "gr_arc")) {
    const lyr = readLayer(ga, "");
    if (lyr !== "Edge.Cuts") continue;
    const s = readPoint(ga, "start");
    const m = readPoint(ga, "mid");
    const e = readPoint(ga, "end");
    if (!s || !e) continue;
    edgeArcs.push({
      start: s,
      mid: m ?? { x: (s.x + e.x) / 2, y: (s.y + e.y) / 2 },
      end: e,
    });
  }
  const edgeLines: KicadEdgeLine[] = [];
  for (const gl of childrenNamed(root, "gr_line")) {
    const lyr = readLayer(gl, "");
    if (lyr !== "Edge.Cuts") continue;
    const s = readPoint(gl, "start");
    const e = readPoint(gl, "end");
    if (!s || !e) continue;
    edgeLines.push({ start: s, end: e });
  }

  // ── Zones (copper pours) ─────────────────────────────────────────────
  //    Prefer `filled_polygon` rings (the actual poured copper after fill).
  //    Fall back to the user-drawn `polygon` outline when the board hasn't
  //    been filled — at least something renders.
  const zones: KicadZone[] = [];
  for (const z of childrenNamed(root, "zone")) {
    const layerList = firstChild(z, "layer");
    const layersListMulti = firstChild(z, "layers");
    const netId = numberProp(z, "net") ?? 0;
    const netName = stringProp(z, "net_name") ?? (netNameById.get(netId) ?? "");
    // A zone may target one or several layers. Collect them.
    const layers: string[] = [];
    if (layerList) {
      const l = atomStr(layerList.rest[0]);
      if (l) layers.push(l);
    }
    if (layersListMulti) {
      for (const r of layersListMulti.rest) {
        const l = atomStr(r);
        if (l) layers.push(l);
      }
    }
    if (layers.length === 0) layers.push("F.Cu");

    // Gather fill rings for each target layer.
    const fillRings = childrenNamed(z, "filled_polygon");
    const outlineRings = childrenNamed(z, "polygon");

    for (const lyr of layers) {
      const polys: Array<Array<{ x: number; y: number }>> = [];
      for (const fp of fillRings) {
        // filled_polygon carries its own (layer "X") on KiCad 7+
        const fpLayer = stringProp(fp, "layer");
        if (fpLayer && fpLayer !== lyr) continue;
        const pts = firstChild(fp, "pts");
        if (!pts) continue;
        const ring: Array<{ x: number; y: number }> = [];
        for (const xy of childrenNamed(pts, "xy")) {
          const px = atomNum(xy.rest[0]);
          const py = atomNum(xy.rest[1]);
          if (px !== undefined && py !== undefined) ring.push({ x: px, y: py });
        }
        if (ring.length >= 3) polys.push(ring);
      }
      if (polys.length === 0) {
        for (const op of outlineRings) {
          const pts = firstChild(op, "pts");
          if (!pts) continue;
          const ring: Array<{ x: number; y: number }> = [];
          for (const xy of childrenNamed(pts, "xy")) {
            const px = atomNum(xy.rest[0]);
            const py = atomNum(xy.rest[1]);
            if (px !== undefined && py !== undefined) ring.push({ x: px, y: py });
          }
          if (ring.length >= 3) polys.push(ring);
        }
      }
      if (polys.length === 0) continue;
      zones.push({ layer: lyr, net_id: netId, net_name: netName, polygons: polys });
    }
  }

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
    zones,
    silkLines,
    silkArcs,
    silkText,
    edgeArcs,
    edgeLines,
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
