// Converts a BuildGraph (user's wiring of salvaged/breakout modules) into a
// PcbGeometry that the full PcbViewport can render as a real PCB — green
// solder mask, copper traces, gold pads, drilled vias. Layout is deterministic
// and cosmetic, not fabrication-grade — the point is to let a beginner see
// their wiring as an actual board.

import type { BuildGraph } from "@/lib/rules/safety-rules";
import type { PcbGeometry, PcbPad } from "@/lib/cad-types";
import { findModule, type ModuleSpec } from "@/lib/modules/module-library";

const PITCH = 2.54;              // mm between pins
const PAD_DRILL = 1.0;            // mm
const PAD_SIZE = 1.8;             // mm outer
const TRACE_WIDTH = 0.35;         // mm
const MODULE_MARGIN_X = 6;        // mm padding inside footprint rectangle
const MODULE_MARGIN_Y = 4;
const MODULE_GAP = 8;             // mm between modules
const BOARD_MARGIN = 3;
const COLS = 2;

type Placed = {
  nodeId: string;
  spec: ModuleSpec;
  /** footprint origin in mm (center of footprint) */
  x: number;
  y: number;
  /** footprint outline half-widths */
  hw: number;
  hh: number;
  /** map from pinId to world-space (mm) pad position */
  padPos: Map<string, { x: number; y: number }>;
  /** pin order used for net assignment */
  pinOrder: string[];
};

function unionFind(pairs: Array<[string, string]>, nodes: string[]): Map<string, string> {
  const parent = new Map<string, string>();
  const find = (x: string): string => {
    const p = parent.get(x) ?? x;
    if (p === x) return x;
    const r = find(p);
    parent.set(x, r);
    return r;
  };
  const union = (a: string, b: string) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent.set(ra, rb);
  };
  for (const n of nodes) parent.set(n, n);
  for (const [a, b] of pairs) {
    if (!parent.has(a)) parent.set(a, a);
    if (!parent.has(b)) parent.set(b, b);
    union(a, b);
  }
  const roots = new Map<string, string>();
  for (const n of parent.keys()) roots.set(n, find(n));
  return roots;
}

export function buildGraphToGeometry(graph: BuildGraph): PcbGeometry {
  // --- 1) Place each module on a grid ---
  const placed: Placed[] = [];
  let cursorX = BOARD_MARGIN;
  let cursorY = BOARD_MARGIN;
  let rowMaxH = 0;
  let colIdx = 0;

  for (const node of graph.nodes) {
    const spec = findModule(node.moduleId);
    if (!spec) continue;
    const half = Math.ceil(spec.pins.length / 2);
    const rows = half;
    const padW = 2 * PITCH;                       // horizontal gap between the two pin columns
    const footprintW = padW + 2 * MODULE_MARGIN_X;
    const footprintH = (rows - 1) * PITCH + 2 * MODULE_MARGIN_Y + PITCH;

    const centerX = cursorX + footprintW / 2;
    const centerY = cursorY + footprintH / 2;

    const left = spec.pins.slice(0, half);
    const right = spec.pins.slice(half);

    const padPos = new Map<string, { x: number; y: number }>();
    const leftX = centerX - padW / 2;
    const rightX = centerX + padW / 2;
    const topY = centerY - ((rows - 1) * PITCH) / 2;

    for (let i = 0; i < left.length; i++) {
      padPos.set(left[i].id, { x: leftX, y: topY + i * PITCH });
    }
    for (let i = 0; i < right.length; i++) {
      padPos.set(right[i].id, { x: rightX, y: topY + i * PITCH });
    }

    placed.push({
      nodeId: node.id,
      spec,
      x: centerX,
      y: centerY,
      hw: footprintW / 2,
      hh: footprintH / 2,
      padPos,
      pinOrder: [...left.map((p) => p.id), ...right.map((p) => p.id)],
    });

    rowMaxH = Math.max(rowMaxH, footprintH);
    colIdx += 1;
    if (colIdx >= COLS) {
      colIdx = 0;
      cursorX = BOARD_MARGIN;
      cursorY += rowMaxH + MODULE_GAP;
      rowMaxH = 0;
    } else {
      cursorX += footprintW + MODULE_GAP;
    }
  }

  if (placed.length === 0) {
    return { board: { bbox_mm: null }, nets: [], footprints: [], segments: [] };
  }

  // --- 2) Board bbox ---
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of placed) {
    minX = Math.min(minX, p.x - p.hw);
    maxX = Math.max(maxX, p.x + p.hw);
    minY = Math.min(minY, p.y - p.hh);
    maxY = Math.max(maxY, p.y + p.hh);
  }
  minX -= BOARD_MARGIN;
  maxX += BOARD_MARGIN;
  minY -= BOARD_MARGIN;
  maxY += BOARD_MARGIN;

  // --- 3) Compute nets via union-find over wires ---
  const pairs: Array<[string, string]> = graph.wires.map((w) => [
    `${w.from.nodeId}|${w.from.pinId}`,
    `${w.to.nodeId}|${w.to.pinId}`,
  ]);
  const allPinIds: string[] = [];
  for (const p of placed) {
    for (const id of p.pinOrder) allPinIds.push(`${p.nodeId}|${id}`);
  }
  const roots = unionFind(pairs, allPinIds);

  // Name nets: GND for gnd-role groups, +3V3/+5V for matching power_out, else Net-N
  const rootToNet = new Map<string, { id: number; name: string }>();
  let netCounter = 1;
  const padByKey = new Map<string, { placed: Placed; pinId: string }>();
  for (const p of placed) {
    for (const pinId of p.pinOrder) padByKey.set(`${p.nodeId}|${pinId}`, { placed: p, pinId });
  }
  for (const [key, root] of roots) {
    if (rootToNet.has(root)) continue;
    const members = [...roots.entries()].filter(([, r]) => r === root).map(([k]) => k);
    // Inspect roles in the group
    const roles = members.map((m) => {
      const hit = padByKey.get(m);
      if (!hit) return null;
      const pin = hit.placed.spec.pins.find((p) => p.id === hit.pinId);
      return pin?.role ?? null;
    });
    const voltages = members.map((m) => {
      const hit = padByKey.get(m);
      if (!hit) return null;
      return hit.placed.spec.pins.find((p) => p.id === hit.pinId)?.voltage ?? null;
    });
    let name: string;
    if (roles.includes("gnd")) name = "GND";
    else {
      const v = voltages.find((x) => x != null);
      if (v === "3.3V") name = "+3V3";
      else if (v === "5V") name = "+5V";
      else name = `Net-${netCounter}`;
    }
    rootToNet.set(root, { id: netCounter, name });
    netCounter += 1;
    // silence unused var
    void key;
  }
  // Ensure unique names if collisions happen (e.g. two GND clusters)
  const seen = new Map<string, number>();
  for (const net of rootToNet.values()) {
    const c = seen.get(net.name) ?? 0;
    if (c > 0) net.name = `${net.name}-${c + 1}`;
    seen.set(net.name, c + 1);
  }

  // --- 4) Build footprints with pads ---
  const footprints: PcbGeometry["footprints"] = placed.map((p, idx) => {
    const pads: PcbPad[] = p.pinOrder.map((pinId, i) => {
      const pos = p.padPos.get(pinId)!;
      const netKey = `${p.nodeId}|${pinId}`;
      const root = roots.get(netKey) ?? netKey;
      const net = rootToNet.get(root) ?? { id: 0, name: "" };
      return {
        num: String(i + 1),
        wx: pos.x,
        wy: pos.y,
        net,
        shape: "circle" as const,
        size_w_mm: PAD_SIZE,
        size_h_mm: PAD_SIZE,
        drill_mm: PAD_DRILL,
        type: "thru_hole" as const,
      };
    });
    return {
      ref: `U${idx + 1}`,
      value: p.spec.label,
      footprint: `Circuit.AI:${p.spec.id}`,
      layer: "F.Cu",
      at: { x: p.x, y: p.y, rot_deg: 0 },
      pads,
    };
  });

  // --- 5) Build Manhattan-routed trace segments ---
  // Each wire becomes a 3-segment run (stub out, lane, stub in). Lanes are
  // offset per-wire by a small amount so parallel traces don't overlap — this
  // gives the characteristic parallel-bus look of a real KiCad board.
  const segments: PcbGeometry["segments"] = [];
  const LANE_OFFSET = 0.9; // mm between parallel trace lanes
  graph.wires.forEach((w, wireIdx) => {
    const from = placed.find((p) => p.nodeId === w.from.nodeId);
    const to = placed.find((p) => p.nodeId === w.to.nodeId);
    const a = from?.padPos.get(w.from.pinId);
    const b = to?.padPos.get(w.to.pinId);
    const netKey = `${w.from.nodeId}|${w.from.pinId}`;
    const root = roots.get(netKey);
    const net = root ? rootToNet.get(root) : undefined;
    if (!a || !b) return;
    const netTag = net ? { id: net.id, name: net.name } : { id: null, name: "" };
    // Offset lane so parallel wires don't stack. Sign alternates to spread lanes.
    const lane = ((wireIdx % 6) - 2.5) * LANE_OFFSET;
    const midY = (a.y + b.y) / 2 + lane;
    // stub out from pad A (horizontal), lane (vertical), stub in to pad B (horizontal)
    segments.push(
      { start: a, end: { x: a.x, y: midY }, width_mm: TRACE_WIDTH, layer: "F.Cu", net: netTag },
      { start: { x: a.x, y: midY }, end: { x: b.x, y: midY }, width_mm: TRACE_WIDTH, layer: "F.Cu", net: netTag },
      { start: { x: b.x, y: midY }, end: b, width_mm: TRACE_WIDTH, layer: "F.Cu", net: netTag },
    );
  });

  // --- 6) Silkscreen rectangle + label per module ---
  const silkLines: PcbGeometry["silkLines"] = [];
  const silkText: PcbGeometry["silkText"] = [];
  for (const p of placed) {
    const x0 = p.x - p.hw, x1 = p.x + p.hw;
    const y0 = p.y - p.hh, y1 = p.y + p.hh;
    silkLines.push(
      { layer: "F.SilkS", start: { x: x0, y: y0 }, end: { x: x1, y: y0 }, width_mm: 0.15 },
      { layer: "F.SilkS", start: { x: x1, y: y0 }, end: { x: x1, y: y1 }, width_mm: 0.15 },
      { layer: "F.SilkS", start: { x: x1, y: y1 }, end: { x: x0, y: y1 }, width_mm: 0.15 },
      { layer: "F.SilkS", start: { x: x0, y: y1 }, end: { x: x0, y: y0 }, width_mm: 0.15 },
    );
    silkText.push({
      layer: "F.SilkS",
      text: p.spec.label,
      at: { x: p.x, y: y0 - 1.0, rot_deg: 0 },
      size_mm: 1.0,
    });
  }
  // Ref designator (U1, U2...) printed inside each footprint — KiCad convention.
  placed.forEach((p, idx) => {
    silkText.push({
      layer: "F.SilkS",
      text: `U${idx + 1}`,
      at: { x: p.x, y: p.y + p.hh - 1.2, rot_deg: 0 },
      size_mm: 1.4,
    });
  });

  // --- 7) GND copper pour on back layer (big copper fill = realistic KiCad look) ---
  const gndNet = [...rootToNet.values()].find((n) => n.name === "GND");
  const zones: PcbGeometry["zones"] = [];
  if (gndNet) {
    const inset = 0.5;
    zones.push({
      layer: "B.Cu",
      net_id: gndNet.id,
      net_name: gndNet.name,
      polygons: [[
        { x: minX + inset, y: minY + inset },
        { x: maxX - inset, y: minY + inset },
        { x: maxX - inset, y: maxY - inset },
        { x: minX + inset, y: maxY - inset },
      ]],
    });
  }

  return {
    board: {
      bbox_mm: {
        min_x: minX, min_y: minY, max_x: maxX, max_y: maxY,
        width: maxX - minX, height: maxY - minY,
      },
    },
    nets: [...rootToNet.values()].map((n) => ({ id: n.id, name: n.name })),
    footprints,
    segments,
    zones,
    silkLines,
    silkText,
    edgeLines: [
      { start: { x: minX, y: minY }, end: { x: maxX, y: minY } },
      { start: { x: maxX, y: minY }, end: { x: maxX, y: maxY } },
      { start: { x: maxX, y: maxY }, end: { x: minX, y: maxY } },
      { start: { x: minX, y: maxY }, end: { x: minX, y: minY } },
    ],
  };
}
