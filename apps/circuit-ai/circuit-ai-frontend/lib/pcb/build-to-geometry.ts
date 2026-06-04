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
const MODULE_MARGIN_X = 6;        // mm padding inside footprint rectangle
const MODULE_MARGIN_Y = 4;
const MODULE_GAP = 14;            // mm between modules — also the per-module
                                  // vertical routing channel (kept pad-free)
const BOARD_MARGIN = 3;
// Single row: nothing is ever "below" another module, so escape jogs and net
// rails reach the channel band without crossing a footprint.
const COLS = Number.MAX_SAFE_INTEGER;

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

  // --- 5) Correct-by-construction 2-layer router -------------------------
  //
  // The previous router drew every trace on F.Cu with a cosmetic lane offset,
  // so different nets crossed and shorted. This one is short-free by
  // construction and the DRC (lib/pcb/drc.ts) is its proof:
  //
  //   • HV-split: horizontals on F.Cu, verticals on B.Cu. A horizontal and a
  //     vertical can cross geometrically but never short — different layers.
  //   • Each net gets a UNIQUE horizontal track Y (a "rail" in the channel
  //     below the modules) and a UNIQUE convergence column X. Two different
  //     nets therefore never share an F.Cu Y or a B.Cu X in the routing field.
  //   • Each pad escapes via a per-pad-UNIQUE jog lane placed inside its own
  //     module footprint, so per-pad B.Cu verticals never share an X either.
  //   • The pad's only at-pad move is a short B.Cu stub; same-column pads are
  //     >= PITCH apart, longer than the stub, so those don't overlap.
  //
  // Result: no two different-net copper features share a layer+coordinate.
  const segments: PcbGeometry["segments"] = [];
  const vias: NonNullable<PcbGeometry["vias"]> = [];
  const RT_W = 0.25;            // routed trace width (>= DRC minTraceWidth)
  const TRK = 1.0;              // mm between adjacent net tracks
  const GAP = 6;                // mm from modules to the rail band

  const seg = (
    start: { x: number; y: number },
    end: { x: number; y: number },
    layer: "F.Cu" | "B.Cu",
    net: { id: number | null; name: string },
  ) => {
    if (start.x === end.x && start.y === end.y) return;
    segments.push({ start, end, width_mm: RT_W, layer, net });
  };
  const via = (x: number, y: number, net: { id: number; name: string }) =>
    vias.push({ x, y, size_mm: 0.8, drill_mm: 0.4, net });

  // Only nets with >= 2 pads are routed; each gets a unique rail Y.
  const netSize = new Map<string, number>();
  for (const r of roots.values()) netSize.set(r, (netSize.get(r) ?? 0) + 1);
  const orderedRoots = [...new Set(roots.values())].filter(
    (r) => (netSize.get(r) ?? 0) >= 2,
  );
  const kOf = new Map<string, number>();
  orderedRoots.forEach((r, i) => kOf.set(r, i));

  // Modules are a single row, so the band below every footprint is empty.
  const railY0 = maxY + GAP;
  const railY = (k: number) => railY0 + k * TRK;
  // Convergence columns sit to the right of every module and every channel.
  const lastRight = placed.reduce((m, p) => Math.max(m, p.x + p.hw), -Infinity);
  const convX0 = lastRight + MODULE_GAP + GAP;
  const convX = (k: number) => convX0 + k * TRK;

  // Left-column pads escape LEFT, right-column pads escape RIGHT, each into a
  // per-module side channel (a pad-free strip). Same-row L/R pads thus travel
  // in opposite directions and never share F.Cu X; within one side there is
  // exactly one pad per row, so escape hops at the pad's own Y never collide.
  // No inter-row dead-band gymnastics needed — the hop is at p.y.
  const HALF = MODULE_GAP / 2;
  let routeMinX = Infinity;
  let routeMaxX = -Infinity;
  let routeMaxY = -Infinity;

  for (const pl of placed) {
    const leftPads: Array<{ pid: string; y: number }> = [];
    const rightPads: Array<{ pid: string; y: number }> = [];
    for (const pid of pl.pinOrder) {
      const pos = pl.padPos.get(pid)!;
      (pos.x < pl.x ? leftPads : rightPads).push({ pid, y: pos.y });
    }

    const routeSide = (
      side: Array<{ pid: string; y: number }>,
      chLo: number,
      chHi: number,
    ) => {
      const m = side.length;
      side.forEach(({ pid }, idx) => {
        const key = `${pl.nodeId}|${pid}`;
        const root = roots.get(key);
        if (root == null) return;
        const k = kOf.get(root);
        if (k == null) return; // unrouted single-pad net
        const net = rootToNet.get(root)!;
        const tag = { id: net.id, name: net.name };
        const p = pl.padPos.get(pid)!;
        const laneX = chLo + ((idx + 1) * (chHi - chLo)) / (m + 1);
        const ry = railY(k);
        const cx = convX(k);

        // 1) F.Cu escape straight out of the pad to this side's channel
        seg(p, { x: laneX, y: p.y }, "F.Cu", tag);
        via(laneX, p.y, net);
        // 2) B.Cu down the unique lane to the net's rail (below all modules)
        seg({ x: laneX, y: p.y }, { x: laneX, y: ry }, "B.Cu", tag);
        via(laneX, ry, net);
        // 3) F.Cu along the net's unique rail to its convergence point
        seg({ x: laneX, y: ry }, { x: cx, y: ry }, "F.Cu", tag);
        via(cx, ry, net);

        routeMinX = Math.min(routeMinX, laneX);
        routeMaxX = Math.max(routeMaxX, cx);
        routeMaxY = Math.max(routeMaxY, ry);
      });
    };

    // Right channel = left half of the gap to this module's right.
    // Left channel  = right half of the gap to this module's left.
    // Adjacent modules' channels are therefore disjoint (2 mm apart).
    const rEdge = pl.x + pl.hw;
    const lEdge = pl.x - pl.hw;
    routeSide(rightPads, rEdge + 1.0, rEdge + HALF - 1.0);
    routeSide(leftPads, lEdge - HALF + 1.0, lEdge - 1.0);
  }
  // Every pad of net k terminates at the identical point (convX(k),railY(k)),
  // so the net is connected there — no separate trunk needed.

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

  // --- 7) (removed) The old full-board GND pour had no keepout and shorted
  // every non-GND through-hole pad. A clean 2-layer board with GND routed as
  // a normal net is honest and manufacturable; the PcbZone type can't express
  // proper thermal-relief keepouts, so we don't fake one.

  // --- 8) Board outline encloses modules AND the routing field, with edge
  // clearance so DRC edge-clearance passes.
  const EDGE_PAD = 1.5;
  const bx0 = Math.min(minX, routeMinX === Infinity ? minX : routeMinX) - EDGE_PAD;
  const by0 = minY - EDGE_PAD;
  const bx1 = Math.max(maxX, routeMaxX === -Infinity ? maxX : routeMaxX) + EDGE_PAD;
  const by1 = Math.max(maxY, routeMaxY === -Infinity ? maxY : routeMaxY) + EDGE_PAD;

  return {
    board: {
      bbox_mm: {
        min_x: bx0, min_y: by0, max_x: bx1, max_y: by1,
        width: bx1 - bx0, height: by1 - by0,
      },
    },
    nets: [...rootToNet.values()].map((n) => ({ id: n.id, name: n.name })),
    footprints,
    segments,
    vias,
    silkLines,
    silkText,
    edgeLines: [
      { start: { x: bx0, y: by0 }, end: { x: bx1, y: by0 } },
      { start: { x: bx1, y: by0 }, end: { x: bx1, y: by1 } },
      { start: { x: bx1, y: by1 }, end: { x: bx0, y: by1 } },
      { start: { x: bx0, y: by1 }, end: { x: bx0, y: by0 } },
    ],
  };
}
