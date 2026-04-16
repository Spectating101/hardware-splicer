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
  PcbGeometry, ValidationIssue, DcAnalysis, ThermalMap, BomRisk,
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
  silk: "#eadfc8",
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

/* ── Substrate + mask ─────────────────────────────────────────────────── */

/** Plain box plank centered at y=0, top at +BOARD_THICKNESS/2, bottom at -BOARD_THICKNESS/2. */
function BoardBody({ bbox }: { bbox: { min_x: number; min_y: number; max_x: number; max_y: number } }) {
  const w = bbox.max_x - bbox.min_x;
  const d = bbox.max_y - bbox.min_y;
  const cx = (bbox.min_x + bbox.max_x) / 2;
  const cz = (bbox.min_y + bbox.max_y) / 2;
  return (
    <mesh position={[cx, 0, cz]} castShadow receiveShadow>
      <boxGeometry args={[w, BOARD_THICKNESS, d]} />
      <meshPhysicalMaterial
        color={PALETTE.substrate}
        roughness={0.82}
        metalness={0.0}
        sheen={0.4}
        sheenColor={"#3a2f18"}
        clearcoat={0.05}
      />
    </mesh>
  );
}

function SolderMask({ bbox, hidden, translucent }: {
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number };
  hidden?: boolean;
  /** Engineering render mode — drop alpha so copper reads through the green. */
  translucent?: boolean;
}) {
  const w = bbox.max_x - bbox.min_x;
  const d = bbox.max_y - bbox.min_y;
  const cx = (bbox.min_x + bbox.max_x) / 2;
  const cz = (bbox.min_y + bbox.max_y) / 2;
  const alpha = translucent ? 0.42 : 1;

  // Ever-so-slightly bigger than substrate in-plane so the green fully skins
  // it, and MASK_HEIGHT tall so pads/traces peek above when emissive.
  return (
    <group position={[cx, 0, cz]}>
      <mesh position={[0, BOARD_THICKNESS / 2 + MASK_HEIGHT / 2, 0]} renderOrder={2} visible={!hidden}>
        <boxGeometry args={[w + 0.02, MASK_HEIGHT, d + 0.02]} />
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
        />
      </mesh>
      <mesh position={[0, -BOARD_THICKNESS / 2 - MASK_HEIGHT / 2, 0]} renderOrder={2} visible={!hidden}>
        <boxGeometry args={[w + 0.02, MASK_HEIGHT, d + 0.02]} />
        <meshPhysicalMaterial
          color={PALETTE.mask}
          roughness={0.4}
          metalness={0.0}
          clearcoat={1}
          clearcoatRoughness={0.3}
          transparent={translucent}
          opacity={alpha}
          depthWrite={!translucent}
        />
      </mesh>
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
        let color = PALETTE.copper;
        let emissive = "#000000";
        let emissiveI = 0;
        let tone = true;
        if (isHi) {
          color = PALETTE.netHighlight;
          emissive = PALETTE.netHighlight;
          emissiveI = 0.4;
        } else if (voltageByNet && voltageRange && seg.net?.id != null) {
          const v = voltageByNet.get(seg.net.id);
          if (v != null) {
            const span = voltageRange.max - voltageRange.min || 1;
            const t = (v - voltageRange.min) / span;
            color = scalarToColor(t);
            emissive = color;
            emissiveI = 0.25;
          }
        } else if (engineeringMode) {
          // Engineering view: copper glows hot through the translucent mask
          // so the circuit is legible at a glance. Driven hard — this is the
          // primary readable signal on the board.
          color = "#ffb277";
          emissive = "#ff8a3c";
          emissiveI = 2.6;
          tone = false;
        }

        return (
          <mesh
            key={`seg-${i}`}
            position={[cx, y, cz]}
            rotation={[0, -angle, 0]}
            renderOrder={1}
          >
            <boxGeometry args={[len, COPPER_HEIGHT, width]} />
            <meshPhysicalMaterial
              color={color}
              metalness={1}
              roughness={0.28}
              emissive={emissive}
              emissiveIntensity={emissiveI}
              toneMapped={tone}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function Airwires({
  geometry,
  highlightedNet,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
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
            <meshStandardMaterial
              color={isHi ? PALETTE.netHighlight : "#4af0ff"}
              emissive={isHi ? PALETTE.netHighlight : "#2abfe0"}
              emissiveIntensity={isHi ? 2.6 : 1.8}
              toneMapped={false}
              transparent
              opacity={isHi ? 1 : 0.92}
            />
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
  return (
    <group>
      {geometry.footprints.flatMap((fp) => {
        if (!fp.pads) return [];
        const size = inferFootprintSize(fp.footprint, fp.ref);
        const padR =
          size.kind === "passive" || size.kind === "led" || size.kind === "diode"
            ? Math.min(size.w_mm, size.h_mm) * 0.38
            : size.kind === "ic" || size.kind === "module"
              ? Math.max(0.25, Math.min(size.w_mm, size.h_mm) * 0.06)
              : size.kind === "connector"
                ? 0.7
                : 0.4;
        const isBottom = fp.layer === "B.Cu";
        // Pads sit just above the mask — their own thickness is 0.08, so
        // offset by half of it to keep them fully above.
        const y = isBottom
          ? -BOARD_THICKNESS / 2 - MASK_HEIGHT - 0.04
          : BOARD_THICKNESS / 2 + MASK_HEIGHT + 0.04;

        return fp.pads.map((p, pi) => {
          const isHi = highlightedNet != null && p.net.id === highlightedNet;
          return (
            <mesh key={`${fp.ref}-pad-${pi}`} position={[p.wx, y, p.wy]} renderOrder={3}>
              <cylinderGeometry args={[padR, padR, 0.08, 24]} />
              <meshPhysicalMaterial
                color={isHi ? PALETTE.netHighlight : PALETTE.padENIG}
                metalness={1}
                roughness={0.22}
                emissive={isHi ? PALETTE.netHighlight : engineeringMode ? "#ffd07a" : "#000000"}
                emissiveIntensity={isHi ? 0.4 : engineeringMode ? 0.95 : 0}
                toneMapped={!(isHi || engineeringMode)}
              />
            </mesh>
          );
        });
      })}
    </group>
  );
}

function Vias({
  geometry,
  highlightedNet,
}: {
  geometry: PcbGeometry;
  highlightedNet: number | null;
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
              <meshPhysicalMaterial
                color={isHi ? PALETTE.netHighlight : PALETTE.via}
                metalness={1}
                roughness={0.3}
                emissive={isHi ? PALETTE.netHighlight : "#000000"}
                emissiveIntensity={isHi ? 0.35 : 0}
              />
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
}) {
  const size = inferFootprintSize(fp.footprint, fp.ref);
  const w = Math.max(1.2, size.w_mm);
  const d = Math.max(1.2, size.h_mm);
  const h = size.kind === "module" ? 2.3 : size.kind === "connector" ? 5.5 : size.kind === "ic" ? 1.1 : size.kind === "led" ? 0.8 : 0.5;
  const baseColor = bodyColorForKind(size.kind);
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
            castShadow
            receiveShadow
          >
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
          </RoundedBox>
        ) : (
          <mesh castShadow receiveShadow>
            <boxGeometry args={[w, h, d]} />
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
                <meshStandardMaterial color="#d9c27a" metalness={0.85} roughness={0.25} />
              </mesh>,
              <mesh key={`p2-${i}`} position={side2 as [number, number, number]}>
                <boxGeometry args={longAxisX ? [0.25, 0.08, 0.5] : [0.5, 0.08, 0.25]} />
                <meshStandardMaterial color="#d9c27a" metalness={0.85} roughness={0.25} />
              </mesh>,
            );
          }
          return <>{pins}</>;
        })()}

        {/* pin-1 dot for ICs */}
        {(size.kind === "ic" || size.kind === "module") && (
          <mesh position={[-w / 2 + 0.4, h / 2 + 0.001, -d / 2 + 0.4]}>
            <cylinderGeometry args={[0.25, 0.25, 0.02, 16]} />
            <meshStandardMaterial color="#e0e0e0" />
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
}: {
  controls: React.RefObject<CameraControls | null>;
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  target: Footprint | null;
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
      const elev = THREE.MathUtils.degToRad(38);
      const azim = THREE.MathUtils.degToRad(35);
      const dist = Math.max(diag * 1.12, 32);
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
      <CameraFit controls={controlsRef} bbox={bbox} target={targetFp} />

      <BoardBody bbox={bbox} />
      <SolderMask bbox={bbox} hidden={!!lenses.peelMask} translucent={engineeringMode} />
      <Traces
        geometry={geometry}
        highlightedNet={highlightedNet}
        peelMask={!!lenses.peelMask}
        voltageByNet={voltageLens?.byNet ?? null}
        voltageRange={voltageLens?.range ?? null}
        engineeringMode={engineeringMode}
      />
      <Pads geometry={geometry} highlightedNet={highlightedNet} engineeringMode={engineeringMode} />
      <Vias geometry={geometry} highlightedNet={highlightedNet} />
      <Airwires geometry={geometry} highlightedNet={highlightedNet} />

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
          />
        );
      })}

      {/* Soft contact shadow under the board to ground it */}
      <ContactShadows
        position={[bbox.min_x + (bbox.max_x - bbox.min_x) / 2, -BOARD_THICKNESS / 2 - 0.2, bbox.min_y + (bbox.max_y - bbox.min_y) / 2]}
        opacity={0.55}
        scale={Math.max(bbox.max_x - bbox.min_x, bbox.max_y - bbox.min_y) * 1.8}
        blur={2.2}
        far={20}
      />

      {/* Studio lighting — warm key, cool rim, subtle ambient. HDRI is dialed
          way back so dark component bodies actually read as dark. */}
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
      {/* Cool rim — only matters in production/photo mode. In engineering we
          kill it because the harsh blue hot-spot fights the copper glow. */}
      <directionalLight
        position={[bbox.min_x - 30, 40, bbox.min_y - 30]}
        intensity={engineeringMode ? 0 : 0.55}
        color="#6aa0ff"
      />
      {/* Engineering top-fill — a soft white light straight above so the
          copper surface is lit evenly and traces read end-to-end. */}
      {engineeringMode && (
        <directionalLight
          position={[bbox.min_x + (bbox.max_x - bbox.min_x) / 2, 80, bbox.min_y + (bbox.max_y - bbox.min_y) / 2]}
          intensity={0.65}
          color="#ffffff"
        />
      )}
      <directionalLight
        position={[bbox.min_x + (bbox.max_x - bbox.min_x) * 0.5, 20, bbox.max_y + 60]}
        intensity={0.35}
        color="#ffffff"
      />
      <Environment preset="city" environmentIntensity={0.18} />
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
}: PcbViewportProps) {
  const controlsRef = useRef<CameraControls | null>(null);
  const engineeringMode = renderMode === "engineering";

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
        shadows
        camera={{ position: [60, 60, 60], fov: 38, near: 0.1, far: 2000 }}
        gl={{ antialias: true, toneMappingExposure: engineeringMode ? 1.25 : 1.05, preserveDrawingBuffer: true }}
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
            intensity={engineeringMode ? 0.85 : 0.35}
            luminanceThreshold={engineeringMode ? 0.38 : 0.82}
            luminanceSmoothing={0.15}
          />
        </EffectComposer>

        <GizmoHelper alignment="bottom-right" margin={[72, 72]}>
          <GizmoViewport axisColors={["#c84b4b", "#4bc884", "#4b8fc8"]} labelColor="white" />
        </GizmoHelper>
      </Canvas>
    </div>
  );
}
