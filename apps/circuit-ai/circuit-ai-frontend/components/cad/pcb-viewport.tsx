"use client";

/**
 * Circuit-AI 3D board viewport.
 *
 * The board is rendered as a single photoreal physical object — FR4 substrate,
 * translucent solder mask, copper traces visible through the mask, gold pads,
 * through-hole vias, and PBR component bodies. The whole thing is one mesh
 * stack that lenses paint on top of. No 2D "mode" — 2D is just a camera preset.
 */

import { Suspense, useMemo, useRef, useEffect } from "react";
import { Canvas, type ThreeEvent, useThree } from "@react-three/fiber";
import {
  Html,
  Environment,
  GizmoHelper,
  GizmoViewport,
  CameraControls,
  ContactShadows,
  RoundedBox,
} from "@react-three/drei";
import { EffectComposer, Bloom, N8AO } from "@react-three/postprocessing";
import * as THREE from "three";
import type {
  PcbGeometry, PcbPad, ValidationIssue, DcAnalysis, ThermalMap, BomRisk,
} from "@/lib/cad-types";
import { inferFootprintSize } from "@/lib/footprint-sizes";

/* ── Palette ──────────────────────────────────────────────────────────── */

const PALETTE = {
  substrate: "#8a7348",        // bare FR4 fibreglass tan
  mask: "#0f6b3f",             // green solder mask
  maskEdge: "#0a4d2c",
  copper: "#d99763",           // trace copper
  padENIG: "#d9b980",           // gold-plated pads
  pinMetal: "#cccccc",
  silk: "#f5efe0",
  via: "#c78b52",
  viaHole: "#08110d",
  bodyIC: "#1b1b1f",
  bodyPassive: "#2e2926",
  bodyLED: "#f3c48b",
  bodyDiode: "#19181a",
  bodyConnector: "#14263e",
  bodyModule: "#0a3d1f",
  bodyMount: "#888",
  bodyDefault: "#30302f",
  netHighlight: "#9fe8ff",
  issueHalo: "#ff5a5a",
  selection: "#4ac8ff",
};

/** Engineering ("diagram") palette. Flat, unlit, high-contrast. The whole
 *  scene is drawn with MeshBasicMaterial in this mode — no PBR, no Bloom,
 *  no shadows, no HDRI. The eye reads color-coding, not shading. */
const FLAT = {
  board:         "#1b3a2a",   // flat mask-green plank
  substrate:     "#8a7348",   // bare FR4 (when peel-mask is on)
  copper:        "#ffae45",   // bold amber-orange trace — the star
  pad:           "#ffd46a",   // gold pad
  via:           "#e89a55",
  airwire:       "#4af0ff",
  netHighlight:  "#9fe8ff",
  issueHalo:     "#ff4a4a",
  selection:     "#4ac8ff",
  bodyIC:        "#3a4d7a",
  bodyPassive:   "#7a7a7a",
  bodyLED:       "#f3c48b",
  bodyDiode:     "#3a3a3a",
  bodyConnector: "#c8784a",
  bodyModule:    "#2aa6b8",
  bodyMount:     "#888",
  bodyDefault:   "#555",
};

function flatBodyColorForKind(kind: ReturnType<typeof inferFootprintSize>["kind"]): string {
  switch (kind) {
    case "ic": return FLAT.bodyIC;
    case "passive": return FLAT.bodyPassive;
    case "led": return FLAT.bodyLED;
    case "diode": return FLAT.bodyDiode;
    case "connector": return FLAT.bodyConnector;
    case "module": return FLAT.bodyModule;
    case "mounting": return FLAT.bodyMount;
    default: return FLAT.bodyDefault;
  }
}

/* KiCad uses mm with Y growing downward. We map KiCad(x, y) → world(x, 0, y).
 * Y in world space is "up" — layer stack grows in +Y off the substrate. */
const BOARD_THICKNESS = 1.6;      // mm
const MASK_HEIGHT = 0.04;
const SILK_HEIGHT = 0.015;
const COPPER_HEIGHT = 0.035;      // above substrate, below mask

/* ── Types ────────────────────────────────────────────────────────────── */

type Footprint = PcbGeometry["footprints"][number];

export type SelectionState = {
  footprintRef: string | null;
  netId?: number | null;
};

export type PcbViewportProps = {
  geometry: PcbGeometry | null;
  issues?: ValidationIssue[];
  selection: SelectionState;
  onSelectionChange?: (sel: SelectionState) => void;
  /** Active overlay lenses. Any absent key is treated as off. */
  lenses?: {
    netFocus?: boolean;
    drc?: boolean;
    voltage?: boolean;
    current?: boolean;
    thermal?: boolean;
    bom?: boolean;
    peelMask?: boolean;   // temporarily hide solder mask so copper reads as bright gold
    explode?: number;     // 0–1
  };
  /** Backend analysis streams. When absent the matching lens is a no-op. */
  dcAnalysis?: DcAnalysis | null;
  thermal?: ThermalMap | null;
  bomRisk?: BomRisk | null;
  /** "engineering" (default) lights copper through a translucent mask so the
   *  circuit reads at a glance. "production" is the opaque-green product shot. */
  renderMode?: "engineering" | "production";
  /** Start with a top-down view so the render reads like a KiCad 2D board. */
  topDown?: boolean;
};

/** Blue → cyan → yellow → red gradient for scalar overlays (voltage, Tj, I). */
function scalarToColor(t: number): string {
  // Clamp to [0,1]
  const x = Math.max(0, Math.min(1, t));
  // Piecewise linear through blue, cyan, green, yellow, red
  const stops: Array<[number, [number, number, number]]> = [
    [0.0, [0x20, 0x4a, 0xc8]],
    [0.25, [0x24, 0xbe, 0xe8]],
    [0.5, [0x4a, 0xe8, 0x90]],
    [0.75, [0xf5, 0xc7, 0x4a]],
    [1.0, [0xf5, 0x4a, 0x3c]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i], [b, cb] = stops[i + 1];
    if (x >= a && x <= b) {
      const k = (x - a) / (b - a);
      const r = Math.round(ca[0] + (cb[0] - ca[0]) * k);
      const g = Math.round(ca[1] + (cb[1] - ca[1]) * k);
      const bl = Math.round(ca[2] + (cb[2] - ca[2]) * k);
      return `rgb(${r}, ${g}, ${bl})`;
    }
  }
  return "#888";
}

/* ── Material helpers ─────────────────────────────────────────────────── */

function bodyColorForKind(kind: ReturnType<typeof inferFootprintSize>["kind"]): string {
  switch (kind) {
    case "ic": return PALETTE.bodyIC;
    case "passive": return PALETTE.bodyPassive;
    case "led": return PALETTE.bodyLED;
    case "diode": return PALETTE.bodyDiode;
    case "connector": return PALETTE.bodyConnector;
    case "module": return PALETTE.bodyModule;
    case "mounting": return PALETTE.bodyMount;
    default: return PALETTE.bodyDefault;
  }
}

/** Build a closed THREE.Shape tracing the Edge.Cuts outline. Falls back to
 *  the bbox rectangle when edges are absent or don't form a loop — so the
 *  board always has *something* to extrude. */
function buildBoardShape(
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number },
  edgeLines?: Array<{ start: { x: number; y: number }; end: { x: number; y: number } }>,
  edgeArcs?: Array<{ start: { x: number; y: number }; mid: { x: number; y: number }; end: { x: number; y: number } }>,
): THREE.Shape {
  const rect = () => {
    const s = new THREE.Shape();
    s.moveTo(bbox.min_x, bbox.min_y);
    s.lineTo(bbox.max_x, bbox.min_y);
    s.lineTo(bbox.max_x, bbox.max_y);
    s.lineTo(bbox.min_x, bbox.max_y);
    s.closePath();
    return s;
  };

  const lines = edgeLines ?? [];
  const arcs = edgeArcs ?? [];
  if (lines.length + arcs.length < 3) return rect();

  // Discretize arcs into short segments so the whole outline is polyline-shaped.
  type Seg = { a: { x: number; y: number }; b: { x: number; y: number }; mids?: Array<{ x: number; y: number }> };
  const segs: Seg[] = lines.map((l) => ({ a: l.start, b: l.end }));
  for (const a of arcs) {
    const { start: s, mid: m, end: e } = a;
    const ax = s.x, ay = s.y, bx = m.x, by = m.y, cx_ = e.x, cy = e.y;
    const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx_ * (ay - by));
    if (Math.abs(d) < 1e-9) {
      segs.push({ a: s, b: e });
      continue;
    }
    const ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx_ * cx_ + cy * cy) * (ay - by)) / d;
    const uy = ((ax * ax + ay * ay) * (cx_ - bx) + (bx * bx + by * by) * (ax - cx_) + (cx_ * cx_ + cy * cy) * (bx - ax)) / d;
    const r = Math.hypot(ax - ux, ay - uy);
    const a0 = Math.atan2(ay - uy, ax - ux);
    const a2 = Math.atan2(cy - uy, cx_ - ux);
    const am = Math.atan2(by - uy, bx - ux);
    let start = a0, end = a2;
    const inBetween = (x: number, lo: number, hi: number) => {
      while (hi < lo) hi += 2 * Math.PI;
      while (x < lo) x += 2 * Math.PI;
      return x <= hi;
    };
    if (!inBetween(am, start, end)) {
      [start, end] = [end, start + 2 * Math.PI];
    } else if (end < start) {
      end += 2 * Math.PI;
    }
    const steps = Math.max(8, Math.ceil(Math.abs(end - start) * 12));
    const mids: Array<{ x: number; y: number }> = [];
    for (let i = 1; i < steps; i++) {
      const t = start + ((end - start) * i) / steps;
      mids.push({ x: ux + Math.cos(t) * r, y: uy + Math.sin(t) * r });
    }
    segs.push({ a: s, b: e, mids });
  }

  // Walk segments into a closed loop by matching endpoints (tolerance 0.05mm).
  const TOL = 0.05;
  const near = (p: { x: number; y: number }, q: { x: number; y: number }) =>
    Math.hypot(p.x - q.x, p.y - q.y) < TOL;
  const used = new Array<boolean>(segs.length).fill(false);
  const loop: Array<{ x: number; y: number }> = [];
  const first = segs[0];
  used[0] = true;
  loop.push(first.a);
  if (first.mids) loop.push(...first.mids);
  loop.push(first.b);
  let cursor = first.b;

  while (true) {
    let advanced = false;
    for (let i = 0; i < segs.length; i++) {
      if (used[i]) continue;
      const s = segs[i];
      if (near(s.a, cursor)) {
        used[i] = true;
        if (s.mids) loop.push(...s.mids);
        loop.push(s.b);
        cursor = s.b;
        advanced = true;
        break;
      } else if (near(s.b, cursor)) {
        used[i] = true;
        if (s.mids) loop.push(...[...s.mids].reverse());
        loop.push(s.a);
        cursor = s.a;
        advanced = true;
        break;
      }
    }
    if (!advanced) break;
    if (near(cursor, first.a)) break;
  }

  if (loop.length < 4 || !near(cursor, first.a)) return rect();

  const shape = new THREE.Shape();
  shape.moveTo(loop[0].x, loop[0].y);
  for (let i = 1; i < loop.length; i++) shape.lineTo(loop[i].x, loop[i].y);
  shape.closePath();
  return shape;
}

/* ── Substrate + mask ─────────────────────────────────────────────────── */

/** Plain box plank centered at y=0, top at +BOARD_THICKNESS/2, bottom at -BOARD_THICKNESS/2.
 *  In engineering (flat) mode this plank doubles as the mask-colored backdrop
 *  so we skip the SolderMask overlay entirely — one unlit plank, bold color. */
function BoardBody({
  bbox, flat, peeled, geometry,
}: {
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number };
  flat?: boolean;
  peeled?: boolean;
  /** When provided, the plank is extruded from the Edge.Cuts polygon rather
   *  than the axis-aligned bbox — rounded or non-rectangular boards render
   *  correctly. */
  geometry?: PcbGeometry;
}) {
  const geom = useMemo(() => {
    const shape = buildBoardShape(bbox, geometry?.edgeLines, geometry?.edgeArcs);
    return new THREE.ExtrudeGeometry(shape, {
      depth: BOARD_THICKNESS,
      bevelEnabled: false,
      steps: 1,
    });
  }, [bbox, geometry?.edgeLines, geometry?.edgeArcs]);

  if (flat) {
    return (
      <mesh
        position={[0, BOARD_THICKNESS / 2, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <primitive object={geom} attach="geometry" />
        <meshBasicMaterial color={peeled ? FLAT.substrate : FLAT.board} side={THREE.DoubleSide} />
      </mesh>
    );
  }
  return (
    <mesh
      position={[0, BOARD_THICKNESS / 2, 0]}
      rotation={[Math.PI / 2, 0, 0]}
      castShadow
      receiveShadow
    >
      <primitive object={geom} attach="geometry" />
      <meshPhysicalMaterial
        color={PALETTE.substrate}
        roughness={0.82}
        metalness={0.0}
        sheen={0.4}
        sheenColor={"#3a2f18"}
        clearcoat={0.05}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/** Build a THREE.Path approximating this pad's outline, expanded by `clearance`,
 *  in world (x,y) KiCad coordinates. Returns null when the pad has no
 *  usable shape info. */
function padHolePath(
  p: PcbPad,
  clearance: number
): THREE.Path | null {
  const w = (p.size_w_mm ?? 0) + clearance * 2;
  const h = (p.size_h_mm ?? 0) + clearance * 2;
  if (w <= 0 || h <= 0) return null;
  const shape = p.shape ?? "rect";
  const rot = ((p.wrot_deg ?? 0) * Math.PI) / 180;
  const cos = Math.cos(rot), sin = Math.sin(rot);
  const path = new THREE.Path();

  if (shape === "circle" || (shape === "oval" && Math.abs(w - h) < 1e-3)) {
    path.absarc(p.wx, p.wy, Math.max(w, h) / 2, 0, Math.PI * 2, false);
    return path;
  }

  if (shape === "oval") {
    // Ellipse — sample 28 points for a smooth opening.
    const steps = 28;
    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * Math.PI * 2;
      const lx = Math.cos(t) * (w / 2);
      const ly = Math.sin(t) * (h / 2);
      const x = p.wx + lx * cos - ly * sin;
      const y = p.wy + lx * sin + ly * cos;
      if (i === 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    path.closePath();
    return path;
  }

  // rect / roundrect / trapezoid / custom → treat as rectangle (good enough
  // for a mask opening; KiCad's pad clearance is already generous).
  const corners: Array<[number, number]> = [
    [-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2],
  ];
  corners.forEach(([lx, ly], i) => {
    const x = p.wx + lx * cos - ly * sin;
    const y = p.wy + lx * sin + ly * cos;
    if (i === 0) path.moveTo(x, y); else path.lineTo(x, y);
  });
  path.closePath();
  return path;
}

function SolderMask({ bbox, hidden, translucent, geometry }: {
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number };
  hidden?: boolean;
  /** Engineering render mode — drop alpha so copper reads through the green. */
  translucent?: boolean;
  /** Used to punch mask openings at every pad position. */
  geometry?: PcbGeometry;
}) {
  const { topGeom, botGeom } = useMemo(() => {
    // Match the mask outline to the board's Edge.Cuts polygon so rounded
    // corners flow through the whole stack (substrate + copper + mask + silk).
    const makeOuter = () => buildBoardShape(bbox, geometry?.edgeLines, geometry?.edgeArcs);
    const topShape = makeOuter();
    const botShape = makeOuter();
    const CLEAR = 0.08; // mm of mask pullback around each pad

    if (geometry?.footprints) {
      for (const fp of geometry.footprints) {
        if (!fp.pads) continue;
        const fpIsBottom = fp.layer === "B.Cu";
        for (const p of fp.pads) {
          const isThruHole = (p.type === "thru_hole" || p.type === "np_thru_hole")
            || (p.drill_mm ?? 0) > 0;
          const path = padHolePath(p, CLEAR);
          if (!path) continue;
          if (isThruHole) {
            topShape.holes.push(path);
            // Need a separate path instance for the other shape — reusing
            // the same object confuses ExtrudeGeometry triangulation.
            const path2 = padHolePath(p, CLEAR);
            if (path2) botShape.holes.push(path2);
          } else if (fpIsBottom) {
            botShape.holes.push(path);
          } else {
            topShape.holes.push(path);
          }
        }
      }
    }

    const extrude = (s: THREE.Shape) => new THREE.ExtrudeGeometry(s, {
      depth: MASK_HEIGHT, bevelEnabled: false, steps: 1,
    });
    return { topGeom: extrude(topShape), botGeom: extrude(botShape) };
  }, [bbox, geometry]);

  const alpha = translucent ? 0.42 : 1;

  // Masks live in XY (KiCad x,y) with extrusion going along local +Z. Apply
  // Rx(+π/2) so local (sx, sy, 0) maps to world (sx, 0, sy) — KiCad-y becomes
  // world-z, matching how traces and zones are laid out. The extrusion then
  // travels along world -y, so position each mesh at the *top* of its slab.
  return (
    <group>
      <mesh
        position={[0, BOARD_THICKNESS / 2 + MASK_HEIGHT, 0]}
        rotation={[Math.PI / 2, 0, 0]}
        renderOrder={2}
        visible={!hidden}
      >
        <primitive object={topGeom} attach="geometry" />
        <meshPhysicalMaterial
          color={PALETTE.mask}
          roughness={0.35}
          metalness={0.0}
          clearcoat={1}
          clearcoatRoughness={0.25}
          sheen={0.5}
          sheenColor={PALETTE.maskEdge}
          transparent={translucent}
          opacity={alpha}
          depthWrite={!translucent}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh
        position={[0, -BOARD_THICKNESS / 2, 0]}
        rotation={[Math.PI / 2, 0, 0]}
        renderOrder={2}
        visible={!hidden}
      >
        <primitive object={botGeom} attach="geometry" />
        <meshPhysicalMaterial
          color={PALETTE.mask}
          roughness={0.4}
          metalness={0.0}
          clearcoat={1}
          clearcoatRoughness={0.3}
          transparent={translucent}
          opacity={alpha}
          depthWrite={!translucent}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

/* ── Copper pours (zones) ─────────────────────────────────────────────
 *   KiCad zones are polygon regions with (potentially disjoint) fill rings.
 *   We triangulate each ring via THREE.Shape + ShapeGeometry, then place the
 *   resulting flat mesh just above (or just below) the substrate. Layers:
 *     F.Cu → y = +BOARD/2 + MASK + COPPER/2
 *     B.Cu → y = -BOARD/2 - MASK - COPPER/2
 *   This is what transforms "colored blocks floating on green" into "board
 *   with ground/power planes", which is ~80% of the perceptual lift. */

function Zones({
  geometry, highlightedNet, peelMask, engineeringMode,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
  peelMask: boolean;
  engineeringMode?: boolean;
}) {
  const meshes = useMemo(() => {
    if (!geometry.zones) return [];
    const out: Array<{
      key: string; y: number; rot: [number, number, number];
      geom: THREE.BufferGeometry; isHi: boolean; netId: number;
    }> = [];
    const signedArea = (ring: Array<{ x: number; y: number }>) => {
      let s = 0;
      for (let i = 0, n = ring.length; i < n; i++) {
        const a = ring[i], b = ring[(i + 1) % n];
        s += (b.x - a.x) * (b.y + a.y);
      }
      return s;
    };
    geometry.zones.forEach((zone, zi) => {
      const isBottom = zone.layer === "B.Cu";
      const isInner = /In\d+\.Cu/.test(zone.layer);
      if (isInner && !peelMask) return;
      // Zones sit on the copper layer just outside the substrate face. In
      // Engineering mode there's no mask, so they're immediately visible; in
      // Photoreal the opaque mask covers them (as on a real board), and only
      // pad windows would expose copper beneath.
      const y = isBottom
        ? -BOARD_THICKNESS / 2 - COPPER_HEIGHT / 2
        : BOARD_THICKNESS / 2 + COPPER_HEIGHT / 2;
      zone.polygons.forEach((ring, ri) => {
        if (ring.length < 3) return;
        // Earcut expects CCW outer rings. KiCad emits CW in screen-space
        // (y-down), so flip when the signed area is negative.
        const ordered = signedArea(ring) < 0 ? ring.slice().reverse() : ring;
        const shape = new THREE.Shape();
        shape.moveTo(ordered[0].x, ordered[0].y);
        for (let i = 1; i < ordered.length; i++) shape.lineTo(ordered[i].x, ordered[i].y);
        shape.closePath();
        // Extrude with a small depth so the pour has real thickness — sidesteps
        // any triangulation ambiguity from a flat ShapeGeometry and guarantees
        // the mesh is visible from above and below.
        const geom = new THREE.ExtrudeGeometry(shape, {
          depth: COPPER_HEIGHT,
          bevelEnabled: false,
          steps: 1,
        });
        const isHi = highlightedNet != null && zone.net_id === highlightedNet;
        out.push({
          key: `zone-${zi}-${ri}`,
          y,
          // ExtrudeGeometry lives in XY plane with +Z being depth; lay flat on XZ.
          rot: [Math.PI / 2, 0, 0],
          geom, isHi, netId: zone.net_id,
        });
      });
    });
    return out;
  }, [geometry.zones, highlightedNet, peelMask]);

  return (
    <group>
      {meshes.map((m) => {
        const color = m.isHi
          ? (engineeringMode ? FLAT.netHighlight : PALETTE.netHighlight)
          : (engineeringMode ? "#c97638" : "#b27042");
        // In engineering mode zones are slightly transparent so traces and
        // silkscreen stay legible on top. In production they're opaque copper
        // hidden under the mask.
        return (
          <mesh
            key={m.key}
            position={[0, m.y, 0]}
            rotation={m.rot}
            renderOrder={0}
          >
            <primitive object={m.geom} attach="geometry" />
            {engineeringMode ? (
              <meshBasicMaterial
                color={color}
                toneMapped={false}
                transparent
                opacity={m.isHi ? 0.98 : 0.82}
                side={THREE.DoubleSide}
                depthWrite={false}
              />
            ) : (
              <meshPhysicalMaterial
                color={color}
                metalness={1}
                roughness={0.4}
                clearcoat={0.5}
                clearcoatRoughness={0.5}
                envMapIntensity={1.15}
                side={THREE.DoubleSide}
              />
            )}
          </mesh>
        );
      })}
    </group>
  );
}

/* ── Silkscreen — white lines + arcs + text on solder mask ─────────── */

function Silkscreen({
  geometry, engineeringMode,
}: {
  geometry: PcbGeometry;
  engineeringMode?: boolean;
}) {
  const lines = geometry.silkLines ?? [];
  const arcs = geometry.silkArcs ?? [];
  const text = geometry.silkText ?? [];
  const silkColor = engineeringMode ? "#f4ecd6" : PALETTE.silk;

  const arcSegments = useMemo(() => {
    // Discretize each arc (start, mid, end) into short line segments via
    // circumcircle — good enough for viewing, cheap to compute.
    const out: Array<{
      layer: string; start: { x: number; y: number };
      end: { x: number; y: number }; width_mm: number;
    }> = [];
    for (const a of arcs) {
      const { start: s, mid: m, end: e } = a;
      // Find circle through s, m, e.
      const ax = s.x, ay = s.y, bx = m.x, by = m.y, cx_ = e.x, cy = e.y;
      const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx_ * (ay - by));
      if (Math.abs(d) < 1e-9) {
        out.push({ layer: a.layer, start: s, end: e, width_mm: a.width_mm });
        continue;
      }
      const ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx_ * cx_ + cy * cy) * (ay - by)) / d;
      const uy = ((ax * ax + ay * ay) * (cx_ - bx) + (bx * bx + by * by) * (ax - cx_) + (cx_ * cx_ + cy * cy) * (bx - ax)) / d;
      const r = Math.hypot(ax - ux, ay - uy);
      const a0 = Math.atan2(ay - uy, ax - ux);
      const a2 = Math.atan2(cy - uy, cx_ - ux);
      const am = Math.atan2(by - uy, bx - ux);
      // Walk a0 → a2 via am. Unwrap to ensure monotone sweep.
      let start = a0, end = a2;
      const inBetween = (x: number, lo: number, hi: number) => {
        while (hi < lo) hi += 2 * Math.PI;
        while (x < lo) x += 2 * Math.PI;
        return x <= hi;
      };
      if (!inBetween(am, start, end)) {
        // Sweep the other way.
        [start, end] = [end, start + 2 * Math.PI];
      } else if (end < start) {
        end += 2 * Math.PI;
      }
      const steps = Math.max(6, Math.ceil(Math.abs(end - start) * 8));
      let prev = { x: ux + Math.cos(start) * r, y: uy + Math.sin(start) * r };
      for (let i = 1; i <= steps; i++) {
        const t = start + ((end - start) * i) / steps;
        const p = { x: ux + Math.cos(t) * r, y: uy + Math.sin(t) * r };
        out.push({ layer: a.layer, start: prev, end: p, width_mm: a.width_mm });
        prev = p;
      }
    }
    return out;
  }, [arcs]);

  const renderLine = (layer: string, s: { x: number; y: number }, e: { x: number; y: number }, width: number, key: string) => {
    const isBottom = layer === "B.SilkS";
    const y = isBottom
      ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - SILK_HEIGHT / 2 - 0.005
      : BOARD_THICKNESS / 2 + MASK_HEIGHT + SILK_HEIGHT / 2 + 0.02;
    const dx = e.x - s.x;
    const dz = e.y - s.y;
    const len = Math.hypot(dx, dz);
    if (len < 0.02) return null;
    const cx = (s.x + e.x) / 2;
    const cz = (s.y + e.y) / 2;
    const angle = Math.atan2(dz, dx);
    return (
      <mesh key={key} position={[cx, y, cz]} rotation={[0, -angle, 0]} renderOrder={5}>
        <boxGeometry args={[len, SILK_HEIGHT, Math.max(0.38, width * 1.8)]} />
        <meshBasicMaterial color={silkColor} toneMapped={false} />
      </mesh>
    );
  };

  return (
    <group>
      {lines.map((l, i) => renderLine(l.layer, l.start, l.end, l.width_mm, `silk-${i}`))}
      {arcSegments.map((l, i) => renderLine(l.layer, l.start, l.end, l.width_mm, `silkarc-${i}`))}
      {text.map((t, i) => {
        const isBottom = t.layer === "B.SilkS";
        const y = isBottom
          ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - 0.02
          : BOARD_THICKNESS / 2 + MASK_HEIGHT + 0.02;
        return (
          <Html
            key={`silktxt-${i}`}
            position={[t.at.x, y, t.at.y]}
            center
            distanceFactor={40}
            occlude={false}
            pointerEvents="none"
          >
            <div
              className="font-mono font-semibold"
              style={{
                color: silkColor,
                fontSize: `${Math.max(7, t.size_mm * 5)}px`,
                lineHeight: 1,
                letterSpacing: "0.02em",
                textShadow: engineeringMode ? "none" : "0 0 2px rgba(0,0,0,0.45)",
                whiteSpace: "nowrap",
                userSelect: "none",
                transform: `rotate(${-t.at.rot_deg}deg)`,
              }}
            >
              {t.text}
            </div>
          </Html>
        );
      })}
    </group>
  );
}

/* ── Traces — thin ribbons on top of substrate ────────────────────────── */

function Traces({
  geometry,
  highlightedNet,
  peelMask,
  voltageByNet,
  voltageRange,
  engineeringMode,
  onSelectNet,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
  peelMask: boolean;
  /** If present, overrides copper color by net voltage. */
  voltageByNet?: Map<number, number> | null;
  voltageRange?: { min: number; max: number } | null;
  /** Engineering render mode — traces are emissive so they read through the
   *  translucent mask. In Production mode traces are plain metallic copper. */
  engineeringMode?: boolean;
  /** Click a trace to isolate its net. */
  onSelectNet?: (netId: number | null) => void;
}) {
  return (
    <group>
      {geometry.segments.map((seg, i) => {
        const layer = seg.layer;
        if (layer === "Airwire") return null;
        const isBottom = layer === "B.Cu";
        const isInner = /In\d+\.Cu/.test(layer);
        if (isInner && !peelMask) return null; // inner layers hidden unless peeling

        const y = isBottom
          ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - COPPER_HEIGHT / 2
          : BOARD_THICKNESS / 2 + MASK_HEIGHT + COPPER_HEIGHT / 2;

        const dx = seg.end.x - seg.start.x;
        const dz = seg.end.y - seg.start.y;
        const len = Math.hypot(dx, dz);
        if (len < 0.01) return null;
        const cx = (seg.start.x + seg.end.x) / 2;
        const cz = (seg.start.y + seg.end.y) / 2;
        const angle = Math.atan2(dz, dx);
        const width = Math.max(engineeringMode ? 0.24 : 0.12, seg.width_mm ?? 0.2);

        const isHi = highlightedNet != null && seg.net?.id === highlightedNet;

        // Voltage lens wins over the default copper color but loses to the
        // active net-highlight flash — we still want to see selected nets
        // clearly against a rainbow background.
        let color = engineeringMode ? FLAT.copper : PALETTE.copper;
        if (isHi) {
          color = engineeringMode ? FLAT.netHighlight : PALETTE.netHighlight;
        } else if (voltageByNet && voltageRange && seg.net?.id != null) {
          const v = voltageByNet.get(seg.net.id);
          if (v != null) {
            const span = voltageRange.max - voltageRange.min || 1;
            const t = (v - voltageRange.min) / span;
            color = scalarToColor(t);
          }
        }

        const netId = seg.net?.id ?? null;

        return (
          <mesh
            key={`seg-${i}`}
            position={[cx, y, cz]}
            rotation={[0, -angle, 0]}
            renderOrder={1}
            onClick={onSelectNet && netId != null ? (e) => {
              e.stopPropagation();
              onSelectNet(netId === highlightedNet ? null : netId);
            } : undefined}
            onPointerOver={onSelectNet ? (e) => { e.stopPropagation(); document.body.style.cursor = "pointer"; } : undefined}
            onPointerOut={onSelectNet ? () => { document.body.style.cursor = "default"; } : undefined}
          >
            <boxGeometry args={[len, COPPER_HEIGHT, width]} />
            {engineeringMode ? (
              <meshBasicMaterial color={color} toneMapped={false} />
            ) : (
              <meshPhysicalMaterial
                color={color}
                metalness={1}
                roughness={0.34}
                clearcoat={0.6}
                clearcoatRoughness={0.45}
                envMapIntensity={1.25}
              />
            )}
          </mesh>
        );
      })}
    </group>
  );
}

function Airwires({
  geometry,
  highlightedNet,
  engineeringMode,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
  engineeringMode?: boolean;
}) {
  const wires = useMemo(
    () => geometry.segments.filter((s) => s.layer === "Airwire"),
    [geometry],
  );
  const y = BOARD_THICKNESS / 2 + MASK_HEIGHT + 0.3;
  return (
    <group>
      {wires.map((s, i) => {
        const isHi = highlightedNet != null && s.net?.id === highlightedNet;
        const dx = s.end.x - s.start.x;
        const dz = s.end.y - s.start.y;
        const len = Math.hypot(dx, dz);
        if (len < 0.05) return null;
        const cx = (s.start.x + s.end.x) / 2;
        const cz = (s.start.y + s.end.y) / 2;
        const angle = Math.atan2(dz, dx);
        // Thin emissive tube — scaled just enough to read at any reasonable zoom.
        return (
          <mesh
            key={`aw-${i}`}
            position={[cx, y, cz]}
            rotation={[0, -angle, 0]}
            renderOrder={4}
          >
            {/* Box lies along its X axis, rotated in the XZ plane by -angle.
                Cylinder's default Y axis makes it read as a vertical pillar,
                which is exactly wrong for a ratsnest line. */}
            <boxGeometry args={[len, 0.32, 0.32]} />
            {engineeringMode ? (
              <meshBasicMaterial
                color={isHi ? FLAT.netHighlight : FLAT.airwire}
                toneMapped={false}
                transparent
                opacity={isHi ? 1 : 0.95}
              />
            ) : (
              <meshStandardMaterial
                color={isHi ? PALETTE.netHighlight : "#4af0ff"}
                emissive={isHi ? PALETTE.netHighlight : "#2abfe0"}
                emissiveIntensity={isHi ? 2.6 : 1.8}
                toneMapped={false}
                transparent
                opacity={isHi ? 1 : 0.92}
              />
            )}
          </mesh>
        );
      })}
    </group>
  );
}

/* ── Pads & vias ──────────────────────────────────────────────────────── */

function Pads({
  geometry,
  highlightedNet,
  engineeringMode,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
  engineeringMode?: boolean;
}) {
  const goldColor = engineeringMode ? FLAT.pad : PALETTE.padENIG;
  const hiColor = engineeringMode ? FLAT.netHighlight : PALETTE.netHighlight;
  const padThickness = 0.08;

  return (
    <group>
      {geometry.footprints.flatMap((fp) => {
        if (!fp.pads) return [];
        const fpSize = inferFootprintSize(fp.footprint, fp.ref);
        const isBottom = fp.layer === "B.Cu";
        const yTop = isBottom
          ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - padThickness / 2
          : BOARD_THICKNESS / 2 + MASK_HEIGHT + padThickness / 2;

        return fp.pads.map((p, pi) => {
          const isHi = highlightedNet != null && p.net.id === highlightedNet;
          const color = isHi ? hiColor : goldColor;
          const shape = p.shape ?? "rect";
          const w = p.size_w_mm ?? 0;
          const h = p.size_h_mm ?? 0;
          const drill = p.drill_mm ?? 0;
          const rot = -((p.wrot_deg ?? 0) * Math.PI) / 180;

          // Fallback sizing when the pad has no shape info (old-synth demo
          // files). Use the same heuristic as the old renderer.
          const hasShape = w > 0 && h > 0;
          const legacyR = fpSize.kind === "passive" || fpSize.kind === "led" || fpSize.kind === "diode"
            ? Math.min(fpSize.w_mm, fpSize.h_mm) * 0.38
            : fpSize.kind === "ic" || fpSize.kind === "module"
              ? Math.max(0.25, Math.min(fpSize.w_mm, fpSize.h_mm) * 0.06)
              : fpSize.kind === "connector" ? 0.7 : 0.4;

          const material = engineeringMode ? (
            <meshBasicMaterial color={color} toneMapped={false} />
          ) : (
            <meshPhysicalMaterial
              color={color}
              metalness={1}
              roughness={0.26}
              emissive={isHi ? PALETTE.netHighlight : "#000000"}
              emissiveIntensity={isHi ? 0.4 : 0}
              clearcoat={0.7}
              clearcoatRoughness={0.28}
              envMapIntensity={1.4}
            />
          );

          // THT barrel: a copper cylinder that spans the full board thickness,
          // with a dark hole drilled through it.
          const tht = (p.type === "thru_hole" || p.type === "np_thru_hole") && drill > 0 ? (
            <>
              <mesh position={[p.wx, 0, p.wy]}>
                <cylinderGeometry args={[Math.max(drill / 2 + 0.15, Math.min(w, h) / 2 || drill / 2 + 0.25), Math.max(drill / 2 + 0.15, Math.min(w, h) / 2 || drill / 2 + 0.25), BOARD_THICKNESS + 0.1, 20]} />
                {engineeringMode ? (
                  <meshBasicMaterial color={color} toneMapped={false} />
                ) : (
                  <meshPhysicalMaterial color={color} metalness={1} roughness={0.25} />
                )}
              </mesh>
              <mesh position={[p.wx, 0, p.wy]}>
                <cylinderGeometry args={[drill / 2, drill / 2, BOARD_THICKNESS + 0.18, 20]} />
                <meshBasicMaterial color={PALETTE.viaHole} />
              </mesh>
            </>
          ) : null;

          // Top-face pad geometry, oriented by world rotation.
          let geom: React.ReactElement;
          if (!hasShape) {
            geom = <cylinderGeometry args={[legacyR, legacyR, padThickness, 24]} />;
          } else if (shape === "circle") {
            geom = <cylinderGeometry args={[w / 2, w / 2, padThickness, 28]} />;
          } else if (shape === "oval") {
            // Oval ≈ scaled cylinder via group transform; keep geom cylindrical
            // and scale in render step below.
            geom = <cylinderGeometry args={[0.5, 0.5, padThickness, 28]} />;
          } else {
            // rect / roundrect / trapezoid / custom — render as a rounded box.
            const rratio = shape === "roundrect" ? Math.max(0.04, p.roundrect_ratio ?? 0.25) : 0.02;
            const radius = Math.min(w, h) * rratio;
            geom = <boxGeometry args={[w, padThickness, h]} />;
            void radius;
          }

          // Wrapper group handles rotation + oval scaling.
          const scale: [number, number, number] = shape === "oval" ? [w, 1, h] : [1, 1, 1];

          return (
            <group key={`${fp.ref}-pad-${pi}`}>
              {tht}
              <mesh
                position={[p.wx, yTop, p.wy]}
                rotation={[0, rot, 0]}
                scale={scale}
                renderOrder={3}
              >
                {geom}
                {material}
              </mesh>
            </group>
          );
        });
      })}
    </group>
  );
}

function Vias({
  geometry,
  highlightedNet,
  engineeringMode,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
  engineeringMode?: boolean;
}) {
  if (!geometry.vias) return null;
  return (
    <group>
      {geometry.vias.map((v, i) => {
        const isHi = highlightedNet != null && v.net.id === highlightedNet;
        return (
          <group key={`via-${i}`} position={[v.x, 0, v.y]}>
            <mesh>
              <cylinderGeometry args={[v.size_mm / 2, v.size_mm / 2, BOARD_THICKNESS + 0.12, 16]} />
              {engineeringMode ? (
                <meshBasicMaterial
                  color={isHi ? FLAT.netHighlight : FLAT.via}
                  toneMapped={false}
                />
              ) : (
                <meshPhysicalMaterial
                  color={isHi ? PALETTE.netHighlight : PALETTE.via}
                  metalness={1}
                  roughness={0.3}
                  emissive={isHi ? PALETTE.netHighlight : "#000000"}
                  emissiveIntensity={isHi ? 0.35 : 0}
                />
              )}
            </mesh>
            <mesh>
              <cylinderGeometry args={[v.drill_mm / 2, v.drill_mm / 2, BOARD_THICKNESS + 0.2, 16]} />
              <meshBasicMaterial color={PALETTE.viaHole} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

/* ── Components (body + pins + silk label) ────────────────────────────── */

function ComponentBody({
  fp,
  selected,
  hasIssue,
  explode,
  onSelect,
  lensDim,
  tintColor,
  tintIntensity,
  engineeringMode,
}: {
  fp: Footprint;
  selected: boolean;
  hasIssue: boolean;
  explode: number;
  onSelect?: (sel: SelectionState) => void;
  lensDim: boolean;
  /** Overlay tint (thermal / BOM risk). Absent ⇒ use kind-based body color. */
  tintColor?: string | null;
  /** 0–1, how strongly the tint replaces base body color. */
  tintIntensity?: number;
  engineeringMode?: boolean;
}) {
  const size = inferFootprintSize(fp.footprint, fp.ref);
  const w = Math.max(1.2, size.w_mm);
  const d = Math.max(1.2, size.h_mm);
  const h = size.kind === "module" ? 2.3 : size.kind === "connector" ? 5.5 : size.kind === "ic" ? 1.1 : size.kind === "led" ? 0.8 : 0.5;
  const baseColor = engineeringMode ? flatBodyColorForKind(size.kind) : bodyColorForKind(size.kind);
  const color = tintColor && tintIntensity ? tintColor : baseColor;
  const emissive = tintColor && tintIntensity ? tintColor : "#000000";
  const emissiveI = tintColor && tintIntensity ? 0.25 * tintIntensity : 0;
  const isBottom = fp.layer === "B.Cu";
  const bodyY = isBottom
    ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - h / 2
    : BOARD_THICKNESS / 2 + MASK_HEIGHT + h / 2;

  const explodeY = explode * (isBottom ? -20 : 20);

  const metalness = size.kind === "ic" || size.kind === "module" ? 0.18 : 0.02;
  const roughness =
    size.kind === "ic" ? 0.5 :
    size.kind === "passive" ? 0.65 :
    size.kind === "connector" ? 0.55 :
    size.kind === "led" ? 0.35 :
    0.6;

  return (
    <group position={[fp.at.x, 0, fp.at.y]} rotation={[0, -THREE.MathUtils.degToRad(fp.at.rot_deg || 0), 0]}>
      <group position={[0, bodyY + explodeY, 0]}>
        {/* hit box */}
        <mesh
          visible={false}
          onPointerDown={(e: ThreeEvent<PointerEvent>) => {
            e.stopPropagation();
            onSelect?.({ footprintRef: fp.ref });
          }}
        >
          <boxGeometry args={[w + 0.4, h + 0.8, d + 0.4]} />
        </mesh>

        {/* body — rounded on IC/module/connector bodies so they read as real
            parts rather than raw cubes. Passives stay as crisp boxes because
            an 0402 with rounded corners looks wrong. */}
        {(size.kind === "ic" || size.kind === "module" || size.kind === "connector") ? (
          <RoundedBox
            args={[w, h, d]}
            radius={Math.min(0.18, Math.min(w, d, h) * 0.12)}
            smoothness={3}
            castShadow={!engineeringMode}
            receiveShadow={!engineeringMode}
          >
            {engineeringMode ? (
              <meshBasicMaterial
                color={color}
                transparent={lensDim}
                opacity={lensDim ? 0.25 : 1}
              />
            ) : (
              <meshPhysicalMaterial
                color={color}
                metalness={metalness}
                roughness={roughness}
                clearcoat={size.kind === "ic" ? 0.7 : size.kind === "module" ? 0.35 : 0.2}
                clearcoatRoughness={0.35}
                transparent={lensDim}
                opacity={lensDim ? 0.25 : 1}
                emissive={emissive}
                emissiveIntensity={emissiveI}
              />
            )}
          </RoundedBox>
        ) : (
          <mesh castShadow={!engineeringMode} receiveShadow={!engineeringMode}>
            <boxGeometry args={[w, h, d]} />
            {engineeringMode ? (
              <meshBasicMaterial
                color={color}
                transparent={lensDim}
                opacity={lensDim ? 0.25 : 1}
              />
            ) : (
              <meshPhysicalMaterial
                color={color}
                metalness={metalness}
                roughness={roughness}
                clearcoat={0}
                clearcoatRoughness={0.4}
                transparent={lensDim}
                opacity={lensDim ? 0.25 : 1}
                emissive={emissive}
                emissiveIntensity={emissiveI}
              />
            )}
          </mesh>
        )}

        {/* Gold pins along the two long edges for IC bodies. Purely cosmetic
            — we don't have real pin geometry so we fake a row at the body
            edge that reads as a DIP/SOIC from any reasonable zoom. */}
        {size.kind === "ic" && (() => {
          const longAxisX = w >= d;
          const axisLen = longAxisX ? w : d;
          const pitch = 0.65;
          const count = Math.max(2, Math.min(24, Math.floor((axisLen - 0.8) / pitch)));
          const step = axisLen / (count + 1);
          const pinY = -h / 2 + 0.04;
          const pins: React.ReactElement[] = [];
          for (let i = 1; i <= count; i++) {
            const along = -axisLen / 2 + i * step;
            const side1 = longAxisX ? [along, pinY, -d / 2 - 0.02] : [-w / 2 - 0.02, pinY, along];
            const side2 = longAxisX ? [along, pinY,  d / 2 + 0.02] : [ w / 2 + 0.02, pinY, along];
            pins.push(
              <mesh key={`p1-${i}`} position={side1 as [number, number, number]}>
                <boxGeometry args={longAxisX ? [0.25, 0.08, 0.5] : [0.5, 0.08, 0.25]} />
                {engineeringMode ? (
                  <meshBasicMaterial color="#d9c27a" />
                ) : (
                  <meshStandardMaterial color="#d9c27a" metalness={0.85} roughness={0.25} />
                )}
              </mesh>,
              <mesh key={`p2-${i}`} position={side2 as [number, number, number]}>
                <boxGeometry args={longAxisX ? [0.25, 0.08, 0.5] : [0.5, 0.08, 0.25]} />
                {engineeringMode ? (
                  <meshBasicMaterial color="#d9c27a" />
                ) : (
                  <meshStandardMaterial color="#d9c27a" metalness={0.85} roughness={0.25} />
                )}
              </mesh>,
            );
          }
          return <>{pins}</>;
        })()}

        {/* pin-1 dot for ICs */}
        {(size.kind === "ic" || size.kind === "module") && (
          <mesh position={[-w / 2 + 0.4, h / 2 + 0.001, -d / 2 + 0.4]}>
            <cylinderGeometry args={[0.25, 0.25, 0.02, 16]} />
            {engineeringMode ? (
              <meshBasicMaterial color="#e0e0e0" />
            ) : (
              <meshStandardMaterial color="#e0e0e0" />
            )}
          </mesh>
        )}

        {/* Issue halo */}
        {hasIssue && (
          <mesh position={[0, -h / 2 - 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[Math.max(w, d) * 0.55, Math.max(w, d) * 0.85, 48]} />
            <meshBasicMaterial color={PALETTE.issueHalo} transparent opacity={0.65} />
          </mesh>
        )}

        {/* Selection halo */}
        {selected && (
          <mesh position={[0, -h / 2 - 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[Math.max(w, d) * 0.6, Math.max(w, d) * 0.9, 48]} />
            <meshBasicMaterial color={PALETTE.selection} transparent opacity={0.85} />
          </mesh>
        )}

        {/* Silkscreen ref label floating at top */}
        <Html
          position={[0, h / 2 + 0.8, 0]}
          center
          distanceFactor={30}
          occlude={false}
          pointerEvents="none"
        >
          <div
            className="text-[8px] font-mono font-semibold tracking-tight"
            style={{
              color: PALETTE.silk,
              textShadow: "0 0 3px rgba(0,0,0,0.9)",
              whiteSpace: "nowrap",
              userSelect: "none",
            }}
          >
            {fp.ref}
          </div>
        </Html>
      </group>
    </group>
  );
}

/* ── Camera auto-fit ──────────────────────────────────────────────────── */

function CameraFit({
  controls,
  bbox,
  target,
  topDown,
}: {
  controls: React.RefObject<CameraControls | null>;
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  target: Footprint | null;
  topDown?: boolean;
}) {
  const fittedBoardRef = useRef(false);

  useEffect(() => {
    if (!controls.current || !bbox) return;
    const w = bbox.max_x - bbox.min_x;
    const d = bbox.max_y - bbox.min_y;
    const cx = (bbox.min_x + bbox.max_x) / 2;
    const cz = (bbox.min_y + bbox.max_y) / 2;
    const diag = Math.hypot(w, d);

    if (target) {
      const size = inferFootprintSize(target.footprint, target.ref);
      const rad = Math.max(4, Math.max(size.w_mm, size.h_mm)) * 2.2;
      // Orbit smoothly in on the chosen ref
      controls.current.setTarget(target.at.x, 0, target.at.y, true);
      controls.current.fitToSphere(
        new THREE.Sphere(new THREE.Vector3(target.at.x, 0, target.at.y), rad),
        true,
      );
      return;
    }

    if (!fittedBoardRef.current) {
      // Hero framing: 35° elevation, 35° azimuth — the classic engineering
      // 3/4 view. Distance scaled off the board diagonal so every board size
      // lands nicely. We intentionally do NOT call fitToBox — that would
      // re-fit to the board's vertical extent and crush the viewing angle
      // to near-horizontal (edge-on), which is exactly the failure mode we
      // saw in the first pass.
      const elev = THREE.MathUtils.degToRad(topDown ? 89 : 38);
      const azim = THREE.MathUtils.degToRad(topDown ? 0 : 35);
      const dist = topDown ? Math.max(diag * 1.55, 65) : Math.max(diag * 1.0, 28);
      const px = cx + dist * Math.cos(elev) * Math.sin(azim);
      const py = dist * Math.sin(elev);
      const pz = cz + dist * Math.cos(elev) * Math.cos(azim);
      // Run twice: first an instant snap (so the initial frame isn't
      // edge-on), then a smoothed repeat so the controls internal state
      // matches what the camera actually shows.
      controls.current.setLookAt(px, py, pz, cx, 0, cz, false);
      controls.current.setLookAt(px, py, pz, cx, 0, cz, false);
      fittedBoardRef.current = true;
    }
  }, [controls, bbox, target]);

  return null;
}

/* ── Scene root ───────────────────────────────────────────────────────── */

function BoardScene({
  geometry,
  selection,
  issues,
  lenses,
  dcAnalysis,
  thermal,
  bomRisk,
  renderMode,
  topDown,
  onSelectionChange,
  controlsRef,
}: {
  geometry: PcbGeometry;
  selection: SelectionState;
  issues: ValidationIssue[];
  lenses: NonNullable<PcbViewportProps["lenses"]>;
  dcAnalysis?: DcAnalysis | null;
  thermal?: ThermalMap | null;
  bomRisk?: BomRisk | null;
  renderMode: "engineering" | "production";
  topDown?: boolean;
  onSelectionChange?: (sel: SelectionState) => void;
  controlsRef: React.RefObject<CameraControls | null>;
}) {
  const engineeringMode = renderMode === "engineering";
  const { scene } = useThree();
  scene.background = new THREE.Color("#0b1320");

  const bbox = geometry.board.bbox_mm;

  const highlightedNet = useMemo(() => {
    if (!lenses.netFocus) return null;
    if (selection.netId != null) return selection.netId;
    if (selection.footprintRef) {
      const fp = geometry.footprints.find((f) => f.ref === selection.footprintRef);
      return fp?.pads?.[0]?.net.id ?? null;
    }
    return null;
  }, [lenses.netFocus, selection, geometry]);

  const issueRefs = useMemo(() => {
    if (!lenses.drc) return new Set<string>();
    const s = new Set<string>();
    for (const iss of issues) {
      const m = iss.component?.match(/\b[A-Z]{1,3}\d+\b/);
      if (m) s.add(m[0]);
    }
    return s;
  }, [lenses.drc, issues]);

  const targetFp = useMemo(
    () => geometry.footprints.find((f) => f.ref === selection.footprintRef) ?? null,
    [geometry, selection.footprintRef],
  );

  /** Per-component tint color + intensity for thermal / BOM lenses. */
  const tintFor = useMemo(() => {
    const table = new Map<string, { color: string; intensity: number }>();
    if (lenses.thermal && thermal) {
      // Scale by Tj against a reasonable spread (25–125°C) — hot ⇒ red
      for (const [ref, t] of Object.entries(thermal)) {
        const v = Math.max(0, Math.min(1, (t.tj_c - 25) / 100));
        table.set(ref, { color: scalarToColor(v), intensity: 0.8 });
      }
    }
    if (lenses.bom && bomRisk) {
      // BOM risk tint wins over thermal if both are active — cooler stakes
      // drive a subdued tint, high-risk gets strong red-violet.
      for (const [ref, r] of Object.entries(bomRisk)) {
        const t = Math.max(0, Math.min(1, r.risk));
        const color = t > 0.66 ? "#ff4a9b" : t > 0.33 ? "#ffb84a" : "#4ae8b0";
        table.set(ref, { color, intensity: 0.5 + t * 0.5 });
      }
    }
    return table;
  }, [lenses.thermal, lenses.bom, thermal, bomRisk]);

  /* Voltage lens → Map<netId, volts> with shared {min,max} for colorscale. */
  const voltageLens = useMemo(() => {
    if (!lenses.voltage || !dcAnalysis?.node_voltages) return null;
    const m = new Map<number, number>();
    let min = Infinity, max = -Infinity;
    for (const [k, v] of Object.entries(dcAnalysis.node_voltages)) {
      const id = Number(k);
      if (!Number.isFinite(id) || !Number.isFinite(v)) continue;
      m.set(id, v);
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    return { byNet: m, range: { min, max } };
  }, [lenses.voltage, dcAnalysis]);

  if (!bbox) return null;

  const lensDimsOthers = lenses.netFocus && highlightedNet != null;

  return (
    <>
      <CameraFit controls={controlsRef} bbox={bbox} target={targetFp} topDown={topDown} />

      <BoardBody bbox={bbox} flat={engineeringMode} peeled={!!lenses.peelMask} geometry={geometry} />
      {/* Solder mask is only drawn in production mode — in engineering the
          BoardBody plank *is* the mask-colored backdrop. */}
      {!engineeringMode && (
        <SolderMask bbox={bbox} hidden={!!lenses.peelMask} geometry={geometry} />
      )}
      <Zones
        geometry={geometry}
        highlightedNet={highlightedNet}
        peelMask={!!lenses.peelMask}
        engineeringMode={engineeringMode}
      />
      <Silkscreen geometry={geometry} engineeringMode={engineeringMode} />
      <Traces
        geometry={geometry}
        highlightedNet={highlightedNet}
        peelMask={!!lenses.peelMask}
        voltageByNet={voltageLens?.byNet ?? null}
        voltageRange={voltageLens?.range ?? null}
        engineeringMode={engineeringMode}
        onSelectNet={onSelectionChange ? (netId) => onSelectionChange({ footprintRef: null, netId }) : undefined}
      />
      <Pads geometry={geometry} highlightedNet={highlightedNet} engineeringMode={engineeringMode} />
      <Vias geometry={geometry} highlightedNet={highlightedNet} engineeringMode={engineeringMode} />
      <Airwires geometry={geometry} highlightedNet={highlightedNet} engineeringMode={engineeringMode} />

      {geometry.footprints.map((fp) => {
        const hasIssue = issueRefs.has(fp.ref);
        const isOnNet = highlightedNet != null &&
          !!fp.pads?.some((p) => p.net.id === highlightedNet);
        const lensDim = lensDimsOthers && !isOnNet;
        const tint = tintFor.get(fp.ref) ?? null;
        return (
          <ComponentBody
            key={fp.ref}
            fp={fp}
            selected={selection.footprintRef === fp.ref}
            hasIssue={hasIssue}
            explode={lenses.explode ?? 0}
            onSelect={onSelectionChange}
            lensDim={!!lensDim}
            tintColor={tint?.color ?? null}
            tintIntensity={tint?.intensity ?? 0}
            engineeringMode={engineeringMode}
          />
        );
      })}

      {/* Photoreal-only: contact shadow, studio lights, HDRI. In engineering
          mode everything is unlit MeshBasicMaterial, so none of this matters
          and skipping it is free GPU. */}
      {!engineeringMode && (
        <>
          <ContactShadows
            position={[bbox.min_x + (bbox.max_x - bbox.min_x) / 2, -BOARD_THICKNESS / 2 - 0.2, bbox.min_y + (bbox.max_y - bbox.min_y) / 2]}
            opacity={0.55}
            scale={Math.max(bbox.max_x - bbox.min_x, bbox.max_y - bbox.min_y) * 1.8}
            blur={2.2}
            far={20}
          />
          <ambientLight intensity={0.15} />
          <directionalLight
            castShadow
            position={[bbox.max_x + 30, 60, bbox.max_y + 20]}
            intensity={2.2}
            color="#ffeacf"
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-bias={-0.0001}
          />
          <directionalLight
            position={[bbox.min_x - 30, 40, bbox.min_y - 30]}
            intensity={0.55}
            color="#6aa0ff"
          />
          <directionalLight
            position={[bbox.min_x + (bbox.max_x - bbox.min_x) * 0.5, 20, bbox.max_y + 60]}
            intensity={0.35}
            color="#ffffff"
          />
          <Environment preset="city" environmentIntensity={0.18} />
        </>
      )}
    </>
  );
}

/* ── Public component ─────────────────────────────────────────────────── */

export function PcbViewport({
  geometry,
  issues = [],
  selection,
  onSelectionChange,
  lenses = {},
  dcAnalysis = null,
  thermal = null,
  bomRisk = null,
  renderMode = "engineering",
  topDown = false,
}: PcbViewportProps) {
  const controlsRef = useRef<CameraControls | null>(null);
  const engineeringMode = renderMode === "engineering";
  // Board lies in the XZ plane (Y is up), so top-down means the camera looks
  // down the Y axis — not the Z axis — at the origin.
  const cameraStart = topDown ? [0, 140, 0.1] as [number, number, number] : [60, 60, 60] as [number, number, number];

  return (
    <div className="h-full w-full relative overflow-hidden">
      {/* Deep studio backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at 50% 40%, #1a2740 0%, #0a121e 55%, #060912 100%)",
        }}
      />

      <Canvas
        shadows={!engineeringMode}
        camera={{ position: cameraStart, fov: 38, near: 0.1, far: 2000 }}
        gl={{ antialias: true, toneMappingExposure: 1.05, preserveDrawingBuffer: true }}
        onPointerMissed={() => onSelectionChange?.({ footprintRef: null })}
      >
        <Suspense fallback={null}>
          {geometry ? (
            <BoardScene
              geometry={geometry}
              selection={selection}
              issues={issues}
              lenses={lenses}
              dcAnalysis={dcAnalysis}
              thermal={thermal}
              bomRisk={bomRisk}
              renderMode={renderMode}
              topDown={topDown}
              onSelectionChange={onSelectionChange}
              controlsRef={controlsRef}
            />
          ) : (
            <Html center>
              <div className="text-white/40 text-xs">Drop a .kicad_pcb file to begin.</div>
            </Html>
          )}
        </Suspense>

        <CameraControls
          ref={controlsRef}
          minPolarAngle={0}
          maxPolarAngle={Math.PI / 2.05}
          smoothTime={0.25}
          draggingSmoothTime={0.12}
        />

        {/* Postprocessing is a photoreal concern — engineering mode skips it
            entirely for cheaper, crisper rendering. */}
        {!engineeringMode && (
          <EffectComposer multisampling={4}>
            <N8AO
              aoRadius={2.0}
              distanceFalloff={1.2}
              intensity={2.2}
              quality="medium"
              color="black"
            />
            <Bloom
              mipmapBlur
              intensity={0.35}
              luminanceThreshold={0.82}
              luminanceSmoothing={0.1}
            />
          </EffectComposer>
        )}

        <GizmoHelper alignment="bottom-right" margin={[72, 72]}>
          <GizmoViewport axisColors={["#c84b4b", "#4bc884", "#4b8fc8"]} labelColor="white" />
        </GizmoHelper>
      </Canvas>
    </div>
  );
}
