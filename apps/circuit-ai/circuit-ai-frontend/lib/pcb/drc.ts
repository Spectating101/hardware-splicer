// Design Rule Check for a generated PcbGeometry.
//
// build-to-geometry.ts produces a *cosmetic* layout: its Manhattan router
// offsets parallel traces by a fixed cosmetic lane and lays a full-board GND
// pour with no keepout. That looks like a PCB but is not manufacturable —
// different-net traces cross on the same copper layer (electrical shorts) and
// the pour floods over every through-hole pad.
//
// This module does NOT fix the layout. It makes the tool honest: it measures
// the generated geometry against fabrication constraints (JLCPCB 2-layer class
// defaults) and reports the violations. Detection before correction —
// autorouting is a separate, larger problem; you cannot reach fab-grade
// without a DRC to define what "correct" means.
//
// Pure, deterministic, dependency-free. All units are millimetres.

import type { PcbGeometry, PcbPad, PcbZone } from "@/lib/cad-types";

export type DrcSeverity = "error" | "warn";

export type DrcRule =
  | "trace-width"
  | "trace-short"
  | "copper-clearance"
  | "annular-ring"
  | "drill-size"
  | "edge-clearance"
  | "pour-short";

export interface DrcViolation {
  rule: DrcRule;
  severity: DrcSeverity;
  message: string;
  /** Approximate board-space location of the offending feature, mm. */
  at?: { x: number; y: number };
}

export interface DrcRules {
  /** Minimum copper trace width (JLCPCB 2-layer: 0.127 mm / 5 mil). */
  minTraceWidth: number;
  /** Minimum copper-to-copper edge gap between different nets. */
  minClearance: number;
  /** Minimum annular ring: (pad - drill) / 2. */
  minAnnular: number;
  /** Minimum finished drill diameter. */
  minDrill: number;
  /** Minimum copper-to-board-edge gap. */
  edgeClearance: number;
}

export const JLCPCB_2LAYER: DrcRules = {
  minTraceWidth: 0.127,
  minClearance: 0.127,
  minAnnular: 0.13,
  minDrill: 0.2,
  edgeClearance: 0.3,
};

export interface DrcResult {
  pass: boolean;
  violations: DrcViolation[];
  summary: { errors: number; warnings: number; byRule: Record<string, number> };
}

// ---- geometry primitives ---------------------------------------------------

type Pt = { x: number; y: number };

function clamp(v: number, lo: number, hi: number) {
  return v < lo ? lo : v > hi ? hi : v;
}

function dist(a: Pt, b: Pt): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function pointSegDist(p: Pt, a: Pt, b: Pt): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return dist(p, a);
  const t = clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / len2, 0, 1);
  return dist(p, { x: a.x + t * dx, y: a.y + t * dy });
}

function segsIntersect(p1: Pt, p2: Pt, p3: Pt, p4: Pt): boolean {
  const o = (a: Pt, b: Pt, c: Pt) =>
    Math.sign((b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y));
  const o1 = o(p1, p2, p3);
  const o2 = o(p1, p2, p4);
  const o3 = o(p3, p4, p1);
  const o4 = o(p3, p4, p2);
  if (o1 !== o2 && o3 !== o4) return true;
  // collinear-overlap cases are caught by the distance fallback below.
  return false;
}

/** Minimum distance between two segments (0 if they cross). */
function segSegDist(p1: Pt, p2: Pt, p3: Pt, p4: Pt): number {
  if (segsIntersect(p1, p2, p3, p4)) return 0;
  return Math.min(
    pointSegDist(p1, p3, p4),
    pointSegDist(p2, p3, p4),
    pointSegDist(p3, p1, p2),
    pointSegDist(p4, p1, p2),
  );
}

function pointInPolygon(p: Pt, poly: Pt[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i];
    const b = poly[j];
    const hit =
      a.y > p.y !== b.y > p.y &&
      p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x;
    if (hit) inside = !inside;
  }
  return inside;
}

function polygonEdgeDist(p: Pt, poly: Pt[]): number {
  let m = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    m = Math.min(m, pointSegDist(p, poly[i], poly[j]));
  }
  return m;
}

// ---- net identity ----------------------------------------------------------

// Two copper features belong to the same net (a connection, not a short) when
// their net ids match, or — when an id is unassigned — their net names match.
function sameNet(
  a: { id: number | null; name: string },
  b: { id: number | null; name: string },
): boolean {
  if (a.id != null && a.id !== 0 && b.id != null && b.id !== 0) {
    return a.id === b.id;
  }
  return a.name !== "" && a.name === b.name;
}

// A feature only participates in short/clearance checks if it carries a real
// net. Unrouted pads (id 0, name "") and net-less stubs are not copper
// conflicts we can reason about — comparing them yields false shorts.
function hasNet(n: { id: number | null; name: string }): boolean {
  return (n.id != null && n.id !== 0) || n.name !== "";
}

function isCopperLayer(layer: string): boolean {
  return layer.endsWith(".Cu");
}

/** Conservative pad radius (mm) — half the larger pad dimension. */
function padRadius(pad: PcbPad): number {
  const w = pad.size_w_mm ?? 0;
  const h = pad.size_h_mm ?? 0;
  return Math.max(w, h, 0) / 2;
}

/** A through-hole pad is present on every copper layer. */
function padOnCopper(pad: PcbPad): boolean {
  return (pad.type ?? "thru_hole") === "thru_hole" ||
    pad.type === "np_thru_hole" ||
    (pad.drill_mm ?? 0) > 0;
}

// ---- the check -------------------------------------------------------------

export function runDrc(
  geometry: PcbGeometry,
  rules: DrcRules = JLCPCB_2LAYER,
): DrcResult {
  const v: DrcViolation[] = [];
  const segs = geometry.segments ?? [];

  // Flatten pads to world space with their owning footprint ref.
  const pads: Array<{ ref: string; pad: PcbPad; at: Pt }> = [];
  for (const fp of geometry.footprints ?? []) {
    for (const pad of fp.pads ?? []) {
      pads.push({ ref: fp.ref, pad, at: { x: pad.wx, y: pad.wy } });
    }
  }

  // 1) Trace width.
  for (const s of segs) {
    if (!isCopperLayer(s.layer)) continue;
    if (s.width_mm != null && s.width_mm < rules.minTraceWidth - 1e-9) {
      v.push({
        rule: "trace-width",
        severity: "error",
        message: `Trace on ${s.layer} is ${s.width_mm.toFixed(3)} mm — below the ${rules.minTraceWidth} mm fab minimum.`,
        at: s.start,
      });
    }
  }

  // 2 & 3) Trace-to-trace short / copper clearance (different nets, same layer).
  for (let i = 0; i < segs.length; i++) {
    const a = segs[i];
    if (!isCopperLayer(a.layer)) continue;
    if (!hasNet(a.net)) continue;
    const aw = (a.width_mm ?? rules.minTraceWidth) / 2;
    for (let j = i + 1; j < segs.length; j++) {
      const b = segs[j];
      if (b.layer !== a.layer) continue;
      if (!hasNet(b.net)) continue;
      if (sameNet(a.net, b.net)) continue;
      const bw = (b.width_mm ?? rules.minTraceWidth) / 2;
      const edge = segSegDist(a.start, a.end, b.start, b.end) - aw - bw;
      if (edge < rules.minClearance - 1e-9) {
        const shorted = edge <= 0;
        v.push({
          rule: shorted ? "trace-short" : "copper-clearance",
          severity: shorted ? "error" : "warn",
          message: shorted
            ? `Nets "${a.net.name || a.net.id}" and "${b.net.name || b.net.id}" cross on ${a.layer} — electrical short.`
            : `Nets "${a.net.name || a.net.id}" and "${b.net.name || b.net.id}" are ${(edge).toFixed(3)} mm apart on ${a.layer} — under ${rules.minClearance} mm clearance.`,
          at: { x: (a.start.x + b.start.x) / 2, y: (a.start.y + b.start.y) / 2 },
        });
      }
    }
  }

  // 3b) Pad-to-trace clearance (different nets).
  for (const { pad, at, ref } of pads) {
    if (!padOnCopper(pad)) continue;
    if (!hasNet(pad.net)) continue;
    const r = padRadius(pad);
    for (const s of segs) {
      if (!isCopperLayer(s.layer)) continue;
      if (!hasNet(s.net)) continue;
      if (sameNet(pad.net, s.net)) continue;
      const sw = (s.width_mm ?? rules.minTraceWidth) / 2;
      const edge = pointSegDist(at, s.start, s.end) - r - sw;
      if (edge < rules.minClearance - 1e-9) {
        v.push({
          rule: edge <= 0 ? "trace-short" : "copper-clearance",
          severity: edge <= 0 ? "error" : "warn",
          message: `Pad ${ref}.${pad.num} (net "${pad.net.name || pad.net.id}") is ${edge <= 0 ? "shorted to" : `${edge.toFixed(3)} mm from`} trace net "${s.net.name || s.net.id}".`,
          at,
        });
      }
    }
  }

  // 4 & 5) Annular ring + drill size on through-hole pads.
  for (const { pad, at, ref } of pads) {
    const drill = pad.drill_mm ?? 0;
    if (drill <= 0) continue;
    const minPad = Math.min(pad.size_w_mm ?? 0, pad.size_h_mm ?? 0);
    const annular = (minPad - drill) / 2;
    if (annular < rules.minAnnular - 1e-9) {
      v.push({
        rule: "annular-ring",
        severity: "error",
        message: `Pad ${ref}.${pad.num} annular ring is ${annular.toFixed(3)} mm (pad ${minPad} mm, drill ${drill} mm) — below ${rules.minAnnular} mm.`,
        at,
      });
    }
    if (drill < rules.minDrill - 1e-9) {
      v.push({
        rule: "drill-size",
        severity: "warn",
        message: `Pad ${ref}.${pad.num} drill ${drill} mm is below the ${rules.minDrill} mm fab minimum.`,
        at,
      });
    }
  }

  // 6) Board-edge clearance for copper.
  const edges = geometry.edgeLines ?? [];
  if (edges.length > 0) {
    const edgeDistOf = (p: Pt) =>
      Math.min(...edges.map((e) => pointSegDist(p, e.start, e.end)));
    for (const s of segs) {
      if (!isCopperLayer(s.layer)) continue;
      const d = Math.min(edgeDistOf(s.start), edgeDistOf(s.end)) -
        (s.width_mm ?? rules.minTraceWidth) / 2;
      if (d < rules.edgeClearance - 1e-9) {
        v.push({
          rule: "edge-clearance",
          severity: "warn",
          message: `Trace net "${s.net.name || s.net.id}" is ${d.toFixed(3)} mm from the board edge — under ${rules.edgeClearance} mm.`,
          at: s.start,
        });
      }
    }
    for (const { pad, at, ref } of pads) {
      const d = edgeDistOf(at) - padRadius(pad);
      if (d < rules.edgeClearance - 1e-9) {
        v.push({
          rule: "edge-clearance",
          severity: "warn",
          message: `Pad ${ref}.${pad.num} is ${d.toFixed(3)} mm from the board edge — under ${rules.edgeClearance} mm.`,
          at,
        });
      }
    }
  }

  // 7) Copper pour flooding over foreign-net pads (the cosmetic GND pour bug).
  for (const zone of (geometry.zones ?? []) as PcbZone[]) {
    if (!isCopperLayer(zone.layer)) continue;
    const zNet = { id: zone.net_id, name: zone.net_name };
    for (const { pad, at, ref } of pads) {
      if (!padOnCopper(pad)) continue; // thru-hole reaches the pour layer
      if (!hasNet(pad.net)) continue;
      if (sameNet(pad.net, zNet)) continue;
      const inside = zone.polygons.some((poly) => pointInPolygon(at, poly));
      const nearEdge = zone.polygons.some(
        (poly) => polygonEdgeDist(at, poly) < padRadius(pad) + rules.minClearance,
      );
      if (inside || nearEdge) {
        v.push({
          rule: "pour-short",
          severity: "error",
          message: `${zone.net_name} pour floods over pad ${ref}.${pad.num} (net "${pad.net.name || pad.net.id}") with no keepout — that net is shorted to ${zone.net_name}.`,
          at,
        });
      }
    }
  }

  const byRule: Record<string, number> = {};
  let errors = 0;
  let warnings = 0;
  for (const x of v) {
    byRule[x.rule] = (byRule[x.rule] ?? 0) + 1;
    if (x.severity === "error") errors++;
    else warnings++;
  }

  return { pass: errors === 0, violations: v, summary: { errors, warnings, byRule } };
}
