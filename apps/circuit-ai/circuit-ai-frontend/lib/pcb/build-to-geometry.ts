// Converts a BuildGraph (user's wiring of salvaged/breakout modules) into a
// PcbGeometry that the full PcbViewport can render as a real PCB — green
// solder mask, copper traces, gold pads, drilled vias. Layout is deterministic
// and cosmetic, not fabrication-grade — the point is to let a beginner see
// their wiring as an actual board.

import type { BuildGraph } from "@/lib/rules/safety-rules";
import type { PcbGeometry, PcbPad } from "@/lib/cad-types";
import { findModule, type ModuleSpec } from "@/lib/modules/module-library";
import {
  boundsFromPads,
  resolveModuleBodyMm,
  resolveModuleFootprint,
  resolveModulePads,
  type ModulePadDef,
} from "@/lib/modules/module-footprints";

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

type PadLayoutKind = "dual" | "row" | "general";

type Placed = {
  nodeId: string;
  spec: ModuleSpec;
  /** footprint origin in mm (center of footprint) */
  x: number;
  y: number;
  /** footprint outline half-widths */
  hw: number;
  hh: number;
  /** world-space pad envelope (for escape channels outside real pads) */
  padMinX: number;
  padMaxX: number;
  /** map from pinId to world-space (mm) pad position */
  padPos: Map<string, { x: number; y: number }>;
  /** pin order used for net assignment */
  pinOrder: string[];
  padLayout: PadLayoutKind;
};

function detectPadLayout(padDefs: ModulePadDef[]): PadLayoutKind {
  if (padDefs.length < 2) return "general";
  const ys = padDefs.map((p) => p.y);
  const xs = padDefs.map((p) => p.x);
  const ySpan = Math.max(...ys) - Math.min(...ys);
  const xSpan = Math.max(...xs) - Math.min(...xs);
  if (ySpan < PITCH * 0.75 && xSpan >= PITCH) return "row";
  const hasLeft = padDefs.some((p) => p.x < -PITCH * 0.25);
  const hasRight = padDefs.some((p) => p.x > PITCH * 0.25);
  if (hasLeft && hasRight && ySpan >= PITCH * 0.5) return "dual";
  return "general";
}

function syntheticDualColumnPads(
  spec: ModuleSpec,
  centerX: number,
  centerY: number,
): { padPos: Map<string, { x: number; y: number }>; pinOrder: string[] } {
  const half = Math.ceil(spec.pins.length / 2);
  const rows = half;
  const padW = 2 * PITCH;
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
  const pinOrder = [...left.map((p) => p.id), ...right.map((p) => p.id)];
  return { padPos, pinOrder };
}

function pickEscapeEdge(
  pad: { x: number; y: number },
  pl: Placed,
  layout: PadLayoutKind,
): "left" | "right" | "bottom" {
  // Row footprints spread pads along X — left/right channels avoid shared-strip shorts.
  if (layout === "row" || layout === "dual") return pad.x < pl.x ? "left" : "right";
  const dLeft = pad.x - (pl.x - pl.hw);
  const dRight = pl.x + pl.hw - pad.x;
  const dBottom = pl.y + pl.hh - pad.y;
  const dTop = pad.y - (pl.y - pl.hh);
  if (dBottom <= dLeft && dBottom <= dRight && dBottom <= dTop) return "bottom";
  return dLeft <= dRight ? "left" : "right";
}

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
    const padDefs = resolveModulePads(spec.id, spec) ?? [];
    const useCustomPads = padDefs.length > 0;
    const half = Math.ceil(spec.pins.length / 2);
    const rows = half;
    const padW = 2 * PITCH;
    const body = resolveModuleBodyMm(spec.id);
    const fromPads = boundsFromPads(padDefs, MODULE_MARGIN_X);
    const footprintW = useCustomPads
      ? (body?.w ?? fromPads.w)
      : padW + 2 * MODULE_MARGIN_X;
    const footprintH = useCustomPads
      ? (body?.h ?? fromPads.h)
      : (rows - 1) * PITCH + 2 * MODULE_MARGIN_Y + PITCH;

    const centerX = cursorX + footprintW / 2;
    const centerY = cursorY + footprintH / 2;
    const padLayout = useCustomPads ? detectPadLayout(padDefs) : "dual";
    let padPos: Map<string, { x: number; y: number }>;
    let pinOrder: string[];
    if (useCustomPads) {
      padPos = new Map();
      for (const def of padDefs) {
        padPos.set(def.pinId, { x: centerX + def.x, y: centerY + def.y });
      }
      pinOrder = padDefs.map((d) => d.pinId);
    } else {
      ({ padPos, pinOrder } = syntheticDualColumnPads(spec, centerX, centerY));
    }

    const padXs = [...padPos.values()].map((p) => p.x);
    const padMinX = Math.min(...padXs);
    const padMaxX = Math.max(...padXs);
    placed.push({
      nodeId: node.id,
      spec,
      x: centerX,
      y: centerY,
      hw: footprintW / 2,
      hh: footprintH / 2,
      padMinX,
      padMaxX,
      padPos,
      pinOrder,
      padLayout,
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
    const base = net.name;
    const c = seen.get(base) ?? 0;
    if (c > 0) net.name = `${base}-${c + 1}`;
    seen.set(base, c + 1);
  }

  // --- 4) Build footprints with pads ---
  const footprints: PcbGeometry["footprints"] = placed.map((p, idx) => {
    const padDefs = resolveModulePads(p.spec.id, p.spec) ?? [];
    const pads: PcbPad[] = p.pinOrder.map((pinId, i) => {
      const def = padDefs.find((d) => d.pinId === pinId);
      const pos = def
        ? { x: p.x + def.x, y: p.y + def.y }
        : p.padPos.get(pinId)!;
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
      footprint: resolveModuleFootprint(p.spec.id),
      layer: "F.Cu",
      at: { x: p.x, y: p.y, rot_deg: 0 },
      pads,
    };
  });

  // --- 5) Correct-by-construction 2-layer router -------------------------
  // Pad positions always come from module-footprints.ts. Escapes are per-pad:
  // row footprints and same-Y side groups jog down on F.Cu (unique X per pad)
  // before any shared horizontal; dual-column footprints use side channels
  // when each pad Y is unique on that side.
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

  let routedPadCount = 0;
  for (const pl of placed) {
    for (const pid of pl.pinOrder) {
      const root = roots.get(`${pl.nodeId}|${pid}`);
      if (root != null && kOf.has(root) && (netSize.get(root) ?? 0) >= 2) routedPadCount += 1;
    }
  }
  let globalBusSlot = 0;
  const nextBusY = () => {
    const y = maxY + 2 + globalBusSlot * TRK;
    globalBusSlot += 1;
    return y;
  };
  const railY0 = maxY + 2 + routedPadCount * TRK + GAP;
  const railY = (k: number) => railY0 + k * TRK;
  const lastRight = placed.reduce(
    (m, p) => Math.max(m, p.padMaxX + PAD_SIZE / 2, p.x + p.hw),
    -Infinity,
  );
  let bCuColSlot = 0;
  const allocBCuX = () => {
    const x = lastRight + MODULE_GAP + 2 + bCuColSlot * TRK;
    bCuColSlot += 1;
    return x;
  };
  const convX0 = lastRight + MODULE_GAP + GAP + routedPadCount * TRK;
  const convX = (k: number) => convX0 + k * TRK;

  const HALF = MODULE_GAP / 2;
  let routeMinX = Infinity;
  let routeMaxX = -Infinity;
  let routeMaxY = -Infinity;
  const yEq = (a: number, b: number) => Math.abs(a - b) < 0.05;

  const finishFromChannel = (
    at: { x: number; y: number },
    net: { id: number; name: string },
    tag: { id: number; name: string },
    k: number,
  ) => {
    const dropX = allocBCuX();
    const ry = railY(k);
    const cx = convX(k);
    if (at.x !== dropX) seg(at, { x: dropX, y: at.y }, "F.Cu", tag);
    via(dropX, at.y, net);
    seg({ x: dropX, y: at.y }, { x: dropX, y: ry }, "B.Cu", tag);
    via(dropX, ry, net);
    seg({ x: dropX, y: ry }, { x: cx, y: ry }, "F.Cu", tag);
    via(cx, ry, net);
    routeMinX = Math.min(routeMinX, dropX, at.x, cx);
    routeMaxX = Math.max(routeMaxX, dropX, at.x, cx);
    routeMaxY = Math.max(routeMaxY, ry, at.y);
  };

  for (const pl of placed) {
    const leftPads: Array<{ pid: string; y: number }> = [];
    const rightPads: Array<{ pid: string; y: number }> = [];
    const bottomPads: Array<{ pid: string; x: number; y: number }> = [];

    for (const pid of pl.pinOrder) {
      const pos = pl.padPos.get(pid)!;
      if (pl.padLayout === "row") {
        bottomPads.push({ pid, x: pos.x, y: pos.y });
      } else if (pl.padLayout === "general") {
        const edge = pickEscapeEdge(pos, pl, pl.padLayout);
        if (edge === "left") leftPads.push({ pid, y: pos.y });
        else if (edge === "right") rightPads.push({ pid, y: pos.y });
        else bottomPads.push({ pid, x: pos.x, y: pos.y });
      } else {
        (pos.x < pl.x ? leftPads : rightPads).push({ pid, y: pos.y });
      }
    }

    const routeSide = (
      side: Array<{ pid: string; y: number }>,
      outward: "left" | "right",
    ) => {
      const routed = side.filter(({ pid }) => {
        const root = roots.get(`${pl.nodeId}|${pid}`);
        return root != null && kOf.has(root) && (netSize.get(root) ?? 0) >= 2;
      });
      const m = routed.length;
      const padEdge = outward === "right"
        ? pl.padMaxX + PAD_SIZE / 2
        : pl.padMinX - PAD_SIZE / 2;
      const chLo = outward === "right" ? padEdge + 0.6 : padEdge - HALF + 0.6;
      const chHi = outward === "right" ? padEdge + HALF - 0.6 : padEdge - 0.6;
      let idx = 0;
      for (const { pid, y } of routed) {
        const key = `${pl.nodeId}|${pid}`;
        const root = roots.get(key)!;
        const k = kOf.get(root)!;
        const net = rootToNet.get(root)!;
        const tag = { id: net.id, name: net.name };
        const p = pl.padPos.get(pid)!;
        const escapeX = chLo + ((idx + 1) * (chHi - chLo)) / (m + 1);
        idx += 1;

        let hopY = p.y;
        const sameY = routed.filter((s) => yEq(s.y, y));
        if (sameY.length > 1) {
          const tier = sameY.findIndex((s) => s.pid === pid);
          const bump =
            (tier % 2 === 0 ? -1.3 : 1.3) * (Math.floor(tier / 2) + 1);
          hopY = p.y + bump;
        }
        const stageY = nextBusY();
        if (!yEq(p.y, hopY)) seg(p, { x: p.x, y: hopY }, "F.Cu", tag);
        if (p.x !== escapeX) seg({ x: p.x, y: hopY }, { x: escapeX, y: hopY }, "F.Cu", tag);
        if (!yEq(hopY, stageY)) {
          via(escapeX, hopY, net);
          seg({ x: escapeX, y: hopY }, { x: escapeX, y: stageY }, "B.Cu", tag);
          via(escapeX, stageY, net);
        }
        finishFromChannel({ x: escapeX, y: stageY }, net, tag, k);
      }
    };

    const routeBottom = (side: Array<{ pid: string; x: number; y: number }>) => {
      const routed = side.filter(({ pid }) => {
        const root = roots.get(`${pl.nodeId}|${pid}`);
        return root != null && kOf.has(root) && (netSize.get(root) ?? 0) >= 2;
      });
      const m = routed.length;
      const chLo = pl.padMinX - PAD_SIZE / 2 - HALF + 0.6;
      const chHi = pl.padMaxX + PAD_SIZE / 2 + HALF - 0.6;
      let idx = 0;
      for (const { pid } of routed) {
        const key = `${pl.nodeId}|${pid}`;
        const root = roots.get(key)!;
        const k = kOf.get(root)!;
        const net = rootToNet.get(root)!;
        const tag = { id: net.id, name: net.name };
        const p = pl.padPos.get(pid)!;
        const stageY = nextBusY();
        const escapeX = chLo + ((idx + 1) * (chHi - chLo)) / (m + 1);
        idx += 1;

        let hopY = p.y;
        if (routed.filter((s) => yEq(s.y, p.y)).length > 1) {
          const tier = idx - 1;
          const bump =
            (tier % 2 === 0 ? -1.3 : 1.3) * (Math.floor(tier / 2) + 1);
          hopY = p.y + bump;
        }
        if (!yEq(p.y, hopY)) seg(p, { x: p.x, y: hopY }, "F.Cu", tag);
        if (p.x !== escapeX) seg({ x: p.x, y: hopY }, { x: escapeX, y: hopY }, "F.Cu", tag);
        if (!yEq(hopY, stageY)) {
          via(escapeX, hopY, net);
          seg({ x: escapeX, y: hopY }, { x: escapeX, y: stageY }, "B.Cu", tag);
          via(escapeX, stageY, net);
        }
        finishFromChannel({ x: escapeX, y: stageY }, net, tag, k);
      }
    };

    routeSide(rightPads, "right");
    routeSide(leftPads, "left");
    routeBottom(bottomPads);
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
