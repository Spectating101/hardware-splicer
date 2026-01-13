"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { PcbGeometry, ValidationIssue } from "@/lib/cad-types";

type Selection = {
  footprintRef?: string;
  segmentIndex?: number;
  netName?: string;
};

type Props = {
  geometry: PcbGeometry | null;
  issues: ValidationIssue[];
  selection: Selection;
  onSelectionChange: (next: Selection) => void;
};

const COLORS = {
  bg: "#0b1220",
  board: "#0f1b33",
  segTop: "#22c55e",
  segBottom: "#f97316",
  segOther: "#a3a3a3",
  fp: "#93c5fd",
  fpSelected: "#60a5fa",
  warn: "#f59e0b",
  err: "#ef4444",
};

function parseLikelyRef(s: string): string | null {
  const m = (s || "").toUpperCase().match(/\b[A-Z]{1,3}\d{1,4}\b/);
  return m ? m[0] : null;
}

function issueColor(sev: string): string {
  const s = (sev || "").toLowerCase();
  if (s === "critical" || s === "error") return COLORS.err;
  if (s === "warning") return COLORS.warn;
  return COLORS.fpSelected;
}

function footprintSizeMm(ref: string): [number, number] {
  const r = (ref || "").toUpperCase();
  if (r.startsWith("U")) return [6, 6];
  if (r.startsWith("J")) return [6, 3];
  if (r.startsWith("C")) return [2.2, 1.6];
  if (r.startsWith("R")) return [2.0, 1.2];
  return [3, 3];
}

function computeExtents(geometry: PcbGeometry | null) {
  if (!geometry) return null;
  if (geometry.board.bbox_mm) return geometry.board.bbox_mm;
  const pts: Array<{ x: number; y: number }> = [];
  for (const fp of geometry.footprints) pts.push({ x: fp.at.x, y: fp.at.y });
  for (const s of geometry.segments) pts.push(s.start, s.end);
  if (pts.length === 0) return null;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const min_x = Math.min(...xs);
  const min_y = Math.min(...ys);
  const max_x = Math.max(...xs);
  const max_y = Math.max(...ys);
  return { min_x, min_y, max_x, max_y, width: max_x - min_x, height: max_y - min_y };
}

function buildIssueHighlights(issues: ValidationIssue[], geometry: PcbGeometry | null) {
  const refs = new Map<string, string>(); // ref -> color
  const nets = new Map<string, string>(); // netName -> color
  if (!geometry) return { refs, nets };

  const netNames = new Set(geometry.nets.map((n) => (n.name || "").toUpperCase()).filter(Boolean));

  for (const issue of issues) {
    const color = issueColor(issue.severity);
    const ref = parseLikelyRef(issue.component);
    if (ref) refs.set(ref.toUpperCase(), color);

    const compU = (issue.component || "").toUpperCase();
    // Best-effort net match: if issue mentions a known net name token, highlight that net.
    for (const net of netNames) {
      if (net.length >= 2 && compU.includes(net)) {
        nets.set(net, color);
      }
    }
  }
  return { refs, nets };
}

function SegmentMesh({
  start,
  end,
  widthMm,
  color,
  y,
}: {
  start: { x: number; y: number };
  end: { x: number; y: number };
  widthMm: number;
  color: string;
  y: number;
}) {
  const v1 = useMemo(() => new THREE.Vector3(start.x, y, start.y), [start.x, start.y, y]);
  const v2 = useMemo(() => new THREE.Vector3(end.x, y, end.y), [end.x, end.y, y]);

  const { length, mid, quat } = useMemo(() => {
    const dir = new THREE.Vector3().subVectors(v2, v1);
    const length = dir.length();
    const mid = new THREE.Vector3().addVectors(v1, v2).multiplyScalar(0.5);
    const quat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    return { length, mid, quat };
  }, [v1, v2]);

  if (!Number.isFinite(length) || length <= 0) return null;

  const radius = Math.max(0.06, widthMm / 2);
  return (
    <mesh position={mid} quaternion={quat}>
      <cylinderGeometry args={[radius, radius, length, 10]} />
      <meshStandardMaterial color={color} roughness={0.6} metalness={0.2} />
    </mesh>
  );
}

function BoardScene({
  geometry,
  issues,
  selection,
  onSelectionChange,
  onFitReady,
  showTop,
  showBottom,
  showLabels,
}: Props & {
  onFitReady: (fit: () => void, reset: () => void) => void;
  showTop: boolean;
  showBottom: boolean;
  showLabels: boolean;
}) {
  const controlsRef = useRef<any>(null);
  const extents = useMemo(() => computeExtents(geometry), [geometry]);
  const highlight = useMemo(() => buildIssueHighlights(issues, geometry), [issues, geometry]);

  const center = useMemo(() => {
    if (!extents) return new THREE.Vector3(0, 0, 0);
    return new THREE.Vector3((extents.min_x + extents.max_x) / 2, 0, (extents.min_y + extents.max_y) / 2);
  }, [extents]);

  const fit = () => {
    const c = controlsRef.current;
    if (!c || !extents) return;
    const w = Math.max(10, extents.width);
    const h = Math.max(10, extents.height);
    const dist = Math.max(w, h) * 1.2;
    c.target.copy(center);
    c.object.position.set(center.x + dist, center.y + dist * 0.9, center.z + dist);
    c.object.near = 0.1;
    c.object.far = 100000;
    c.object.updateProjectionMatrix?.();
    c.update();
  };

  const reset = () => {
    const c = controlsRef.current;
    if (!c) return;
    c.reset();
    if (extents) fit();
  };

  useEffect(() => {
    onFitReady(fit, reset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extents]);

  useEffect(() => {
    if (!extents) return;
    const t = setTimeout(() => fit(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extents]);

  useEffect(() => {
    if (!selection.footprintRef || !geometry) return;
    const fp = geometry.footprints.find((f) => f.ref.toUpperCase() === selection.footprintRef?.toUpperCase());
    const c = controlsRef.current;
    if (!fp || !c) return;
    c.target.set(fp.at.x, 0, fp.at.y);
    c.update();
  }, [selection.footprintRef, geometry]);

  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[200, 240, 120]} intensity={1.1} />
      <directionalLight position={[-120, 160, -80]} intensity={0.6} />

      <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.08} rotateSpeed={0.6} />

      <gridHelper args={[1000, 100, "#1f2937", "#111827"]} position={[0, -0.01, 0]} />

      {extents ? (
        <mesh position={[center.x, 0, center.z]}>
          <boxGeometry args={[Math.max(1, extents.width), 1.2, Math.max(1, extents.height)]} />
          <meshStandardMaterial color={COLORS.board} roughness={0.95} metalness={0.05} />
        </mesh>
      ) : null}

      {geometry?.segments.map((seg, idx) => {
        const layer = (seg.layer || "").toLowerCase();
        const isTop = layer.includes("f.");
        const isBottom = layer.includes("b.");
        if ((isTop && !showTop) || (isBottom && !showBottom)) return null;
        const baseColor = layer.includes("f.") ? COLORS.segTop : layer.includes("b.") ? COLORS.segBottom : COLORS.segOther;
        const netName = (seg.net?.name || "").toUpperCase();
        const netHighlight = netName && highlight.nets.get(netName);
        const selectedNet = (selection.netName || "").toUpperCase();
        const color = (selectedNet && netName === selectedNet ? COLORS.fpSelected : netHighlight) || baseColor;
        const y = layer.includes("f.") ? 0.9 : layer.includes("b.") ? 0.3 : 0.6;
        const widthMm = seg.width_mm ?? 0.2;
        return <SegmentMesh key={idx} start={seg.start} end={seg.end} widthMm={widthMm} color={color} y={y} />;
      })}

      {geometry?.footprints.map((fp) => {
        const refU = fp.ref.toUpperCase();
        const selected = selection.footprintRef?.toUpperCase() === refU;
        const issueHl = highlight.refs.get(refU);
        const [w, h] = footprintSizeMm(fp.ref);
        const color = selected ? COLORS.fpSelected : issueHl || COLORS.fp;
        const y = 1.25;
        return (
          <group key={fp.ref} position={[fp.at.x, y, fp.at.y]} rotation={[0, THREE.MathUtils.degToRad(fp.at.rot_deg || 0), 0]}>
            <mesh
              onPointerDown={(e) => {
                e.stopPropagation();
                onSelectionChange({ footprintRef: fp.ref });
              }}
            >
              <boxGeometry args={[w, 1.2, h]} />
              <meshStandardMaterial color={color} roughness={0.55} metalness={0.15} emissive={issueHl ? new THREE.Color(issueHl) : new THREE.Color(0x000000)} emissiveIntensity={issueHl ? 0.35 : 0} />
            </mesh>
            {showLabels ? (
              <Html
                center
                distanceFactor={60}
                style={{
                  pointerEvents: "none",
                  fontSize: 12,
                  color: "rgba(255,255,255,0.85)",
                  textShadow: "0 1px 2px rgba(0,0,0,0.6)",
                }}
              >
                {fp.ref}
              </Html>
            ) : null}
          </group>
        );
      })}

    </>
  );
}

export function PcbViewport({ geometry, issues, selection, onSelectionChange }: Props) {
  const [fitFns, setFitFns] = useState<{ fit: () => void; reset: () => void } | null>(null);
  const [showTop, setShowTop] = useState(true);
  const [showBottom, setShowBottom] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg border border-white/10 bg-[#0b1220]">
      {!geometry ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
          <div className="max-w-md rounded-xl border border-white/10 bg-black/40 p-4 text-center">
            <div className="text-sm font-semibold text-white/90">No design loaded</div>
            <div className="mt-1 text-xs text-white/60">
              Open a project, then import a KiCad file or load the demo board.
            </div>
          </div>
        </div>
      ) : null}
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false }}
        camera={{ position: [120, 120, 120], fov: 45, near: 0.1, far: 200000 }}
        onPointerMissed={() => onSelectionChange({})}
        onCreated={({ gl, scene }) => {
          gl.setClearColor(new THREE.Color(COLORS.bg), 1);
          scene.fog = new THREE.Fog(new THREE.Color("#071022"), 400, 2000);
        }}
      >
        <BoardScene
          geometry={geometry}
          issues={issues}
          selection={selection}
          onSelectionChange={onSelectionChange}
          onFitReady={(fit, reset) => setFitFns({ fit, reset })}
          showTop={showTop}
          showBottom={showBottom}
          showLabels={showLabels}
        />
      </Canvas>

      <div className="pointer-events-none absolute left-3 top-3 flex gap-2 rounded-md bg-black/40 px-2 py-1 text-xs text-white/80">
        <span>Orbit: drag</span>
        <span>Zoom: wheel</span>
        <span>Pick: click</span>
      </div>
      <div className="absolute right-3 top-3 flex gap-2">
        <button
          className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs text-white/80 hover:bg-black/55"
          onClick={() => fitFns?.fit()}
          type="button"
        >
          Fit
        </button>
        <button
          className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs text-white/80 hover:bg-black/55"
          onClick={() => fitFns?.reset()}
          type="button"
        >
          Reset
        </button>
      </div>

      <div className="absolute left-3 bottom-3 flex items-center gap-2 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs text-white/80">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showTop} onChange={(e) => setShowTop(e.target.checked)} />
          F.Cu
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showBottom} onChange={(e) => setShowBottom(e.target.checked)} />
          B.Cu
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} />
          Labels
        </label>
      </div>
    </div>
  );
}
