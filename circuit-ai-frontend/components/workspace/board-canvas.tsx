"use client";

import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import type { PcbGeometry } from "@/lib/cad-types";
import type { LayerVis } from "@/lib/workbench-store";
import { inferFootprintSize } from "@/lib/footprint-sizes";

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface BoardCanvasProps {
  geometry: PcbGeometry | null;
  layers: LayerVis[];
  selectedRef: string | null;
  onSelectRef: (ref: string | null) => void;
  filename?: string | null;
}

/** PCB palette — modeled after real JLCPCB dark-green + bright copper. */
const PCB = {
  substrate:     "#0c2a1e",   // FR4 under the mask
  maskTop:       "#0f6b3f",   // solder mask — rich green
  maskTopHi:     "#13824c",
  maskBot:       "#0b4b2b",
  silkscreen:    "#e9e3d2",   // ivory white
  copperTop:     "#e0a86b",   // warm bright copper
  copperTopHi:   "#f6c78c",
  copperBot:     "#c78b52",   // slightly darker, back layer
  pad:           "#f3c88e",   // HASL finish highlight
  padShadow:     "#9e6530",
  viaRing:       "#e0a86b",
  viaHole:       "#0a1d14",
  edgeCut:       "#f9e29a",
  airwire:       "#7aa1ff",
  internal1:     "#b88b55",
  internal2:     "#8eb89d",
};

const LAYER_COLORS: Record<string, string> = {
  "F.Cu":         PCB.copperTop,
  "B.Cu":         PCB.copperBot,
  "In1.Cu":       PCB.internal1,
  "In2.Cu":       PCB.internal2,
  "F.Silkscreen": PCB.silkscreen,
  "B.Silkscreen": "#c8c2b0",
  "Edge.Cuts":    PCB.edgeCut,
  "F.Mask":       PCB.maskTop,
  "B.Mask":       PCB.maskBot,
  "Airwire":      PCB.airwire,
};

function layerColor(name: string): string {
  return LAYER_COLORS[name] ?? "#888888";
}

/** Render order: back-to-front */
const LAYER_ORDER = [
  "Edge.Cuts",
  "B.Mask",
  "B.Cu",
  "B.Silkscreen",
  "In2.Cu",
  "In1.Cu",
  "F.Mask",
  "F.Cu",
  "F.Silkscreen",
  "Airwire",
];

function layerZ(name: string): number {
  const idx = LAYER_ORDER.indexOf(name);
  return idx === -1 ? 5 : idx;
}

export function BoardCanvas({
  geometry,
  layers,
  selectedRef,
  onSelectRef,
  filename,
}: BoardCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [vb, setVb] = useState<ViewBox | null>(null);
  const [hoveredRef, setHoveredRef] = useState<string | null>(null);
  const [hoveredNet, setHoveredNet] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<{ clientX: number; clientY: number; vb: ViewBox } | null>(null);

  const visibleLayers = new Set(
    layers.filter((l) => l.visible).map((l) => l.name)
  );

  // Build a quick ref→net set for the selected/hovered component
  // so we can highlight the whole net of a hovered trace.
  const highlightedNet = useMemo(() => {
    if (hoveredNet != null) return hoveredNet;
    if (!selectedRef || !geometry) return null;
    const fp = geometry.footprints.find((f) => f.ref === selectedRef);
    if (!fp || !fp.pads || fp.pads.length === 0) return null;
    // Highlight *the first net* on the selected part — a small nicety;
    // a richer future step is to render per-pad net highlights.
    return fp.pads[0].net.id;
  }, [hoveredNet, selectedRef, geometry]);

  useEffect(() => {
    if (!geometry) return;
    const bbox = geometry.board.bbox_mm;
    if (bbox) {
      const pad = Math.max(bbox.width, bbox.height) * 0.12;
      setVb({ x: bbox.min_x - pad, y: bbox.min_y - pad, w: bbox.width + pad * 2, h: bbox.height + pad * 2 });
    } else if (geometry.footprints.length > 0) {
      const xs = geometry.footprints.map((f) => f.at.x);
      const ys = geometry.footprints.map((f) => f.at.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const pad = 10;
      setVb({ x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 });
    }
  }, [geometry]);

  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      if (!vb || !svgRef.current) return;
      const factor = e.deltaY < 0 ? 0.85 : 1.18;
      const rect = svgRef.current.getBoundingClientRect();
      const mx = vb.x + ((e.clientX - rect.left) / rect.width) * vb.w;
      const my = vb.y + ((e.clientY - rect.top) / rect.height) * vb.h;
      setVb({
        x: mx - (mx - vb.x) * factor,
        y: my - (my - vb.y) * factor,
        w: vb.w * factor,
        h: vb.h * factor,
      });
    },
    [vb]
  );

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    if (!vb) return;
    setDragging(true);
    dragStart.current = { clientX: e.clientX, clientY: e.clientY, vb: { ...vb } };
    (e.target as Element).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!dragging || !dragStart.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = ((e.clientX - dragStart.current.clientX) / rect.width) * dragStart.current.vb.w;
    const dy = ((e.clientY - dragStart.current.clientY) / rect.height) * dragStart.current.vb.h;
    setVb({
      ...dragStart.current.vb,
      x: dragStart.current.vb.x - dx,
      y: dragStart.current.vb.y - dy,
    });
  };

  const handlePointerUp = () => {
    setDragging(false);
    dragStart.current = null;
  };

  if (!geometry || !vb) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#050a12] relative overflow-hidden select-none">
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.08 }}>
          <defs>
            <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
              <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#4b8fc8" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
        <div className="text-center z-10">
          <div className="w-16 h-16 rounded-2xl border-2 border-dashed border-white/10 flex items-center justify-center mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8" cy="8" r="1.5" />
              <circle cx="16" cy="8" r="1.5" />
              <circle cx="8" cy="16" r="1.5" />
              <circle cx="16" cy="16" r="1.5" />
              <path d="M8 8 L16 8 M8 16 L16 16" />
            </svg>
          </div>
          <p className="text-white/30 text-sm font-medium">
            {filename ? "Parsing board…" : "Drop your .kicad_pcb file here"}
          </p>
          {!filename && (
            <p className="text-white/15 text-xs mt-1">or use the command bar to get started</p>
          )}
        </div>
      </div>
    );
  }

  const bbox = geometry.board.bbox_mm;

  // Group segments by layer, back-to-front
  const segmentsByLayer = new Map<string, typeof geometry.segments>();
  for (const seg of geometry.segments) {
    if (!segmentsByLayer.has(seg.layer)) segmentsByLayer.set(seg.layer, []);
    segmentsByLayer.get(seg.layer)!.push(seg);
  }
  const layerOrder = [...segmentsByLayer.keys()].sort(
    (a, b) => layerZ(a) - layerZ(b)
  );

  // Board size for shadow sizing
  const boardW = bbox?.width ?? 100;
  const boardH = bbox?.height ?? 100;
  const boardRadius = Math.min(2, Math.min(boardW, boardH) * 0.04);

  return (
    <svg
      ref={svgRef}
      className="flex-1 w-full h-full select-none"
      viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
      style={{ cursor: dragging ? "grabbing" : "crosshair", background: "radial-gradient(ellipse at center, #0b1220 0%, #050810 70%)" }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onClick={(e) => {
        if (e.target === svgRef.current) {
          onSelectRef(null);
          setHoveredNet(null);
        }
      }}
    >
      <defs>
        {/* Solder-mask gradient — warm highlight from top-left, deeper green below */}
        <linearGradient id="pcb-mask" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"  stopColor={PCB.maskTopHi} />
          <stop offset="55%" stopColor={PCB.maskTop} />
          <stop offset="100%" stopColor={PCB.maskBot} />
        </linearGradient>

        {/* Copper gradient — warm-to-bright along length */}
        <linearGradient id="pcb-copper" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={PCB.copperTopHi} />
          <stop offset="100%" stopColor={PCB.copperTop} />
        </linearGradient>

        {/* Solder pad radial — hot center */}
        <radialGradient id="pcb-pad" cx="50%" cy="40%" r="60%">
          <stop offset="0%"  stopColor="#fff3dd" />
          <stop offset="55%" stopColor={PCB.pad} />
          <stop offset="100%" stopColor={PCB.padShadow} />
        </radialGradient>

        {/* Soft board drop shadow */}
        <filter id="board-shadow" x="-10%" y="-10%" width="120%" height="125%">
          <feGaussianBlur in="SourceAlpha" stdDeviation={Math.min(boardW, boardH) * 0.012} />
          <feOffset dx="0" dy={Math.min(boardW, boardH) * 0.01} />
          <feComponentTransfer><feFuncA type="linear" slope="0.55" /></feComponentTransfer>
          <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>

        {/* Glow for selection */}
        <filter id="copper-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="0.3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>

        {/* Subtle noise for FR4 texture — turbulence */}
        <filter id="fr4-noise" x="0%" y="0%" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="2.2" numOctaves="1" seed="7" />
          <feColorMatrix values="0 0 0 0 0.04  0 0 0 0 0.16  0 0 0 0 0.07  0 0 0 0.35 0" />
          <feComposite in2="SourceGraphic" operator="in" />
        </filter>

        {/* Silkscreen text shadow (slight offset) */}
        <filter id="silk-depth" x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur in="SourceAlpha" stdDeviation="0.02" />
          <feOffset dx="0" dy="0.04" />
          <feComponentTransfer><feFuncA type="linear" slope="0.4" /></feComponentTransfer>
          <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>

        {/* Grid lines in mm */}
        <pattern id="wb-grid-major" x={vb.x % 10} y={vb.y % 10} width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(75,143,200,0.10)" strokeWidth="0.08" />
        </pattern>
      </defs>

      {/* Grid OUTSIDE the board */}
      <rect x={vb.x} y={vb.y} width={vb.w} height={vb.h} fill="url(#wb-grid-major)" />

      {/* Board — solder-mask green with rounded corners, drop shadow, texture */}
      {bbox && (
        <g filter="url(#board-shadow)">
          <rect
            x={bbox.min_x} y={bbox.min_y}
            width={bbox.width} height={bbox.height}
            rx={boardRadius} ry={boardRadius}
            fill="url(#pcb-mask)"
          />
          {/* FR4 texture overlay */}
          <rect
            x={bbox.min_x} y={bbox.min_y}
            width={bbox.width} height={bbox.height}
            rx={boardRadius} ry={boardRadius}
            fill={PCB.substrate}
            filter="url(#fr4-noise)"
            opacity="0.35"
          />
          {/* Inner bevel highlight */}
          <rect
            x={bbox.min_x + 0.2} y={bbox.min_y + 0.2}
            width={bbox.width - 0.4} height={bbox.height - 0.4}
            rx={Math.max(0, boardRadius - 0.2)} ry={Math.max(0, boardRadius - 0.2)}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="0.12"
          />
          {/* Edge cut line */}
          {visibleLayers.has("Edge.Cuts") && (
            <rect
              x={bbox.min_x} y={bbox.min_y}
              width={bbox.width} height={bbox.height}
              rx={boardRadius} ry={boardRadius}
              fill="none"
              stroke={PCB.edgeCut}
              strokeWidth={0.15}
              opacity={0.55}
            />
          )}
        </g>
      )}

      {/* Traces — grouped by layer, back-to-front */}
      {layerOrder.map((layerName) => {
        if (!visibleLayers.has(layerName)) return null;
        const segs = segmentsByLayer.get(layerName)!;
        const isAirwire = layerName === "Airwire";
        const isCopper = layerName.endsWith(".Cu");
        const baseColor = isCopper ? "url(#pcb-copper)" : layerColor(layerName);
        return (
          <g key={layerName} style={isCopper ? { filter: "url(#copper-glow)" } : undefined}>
            {segs.map((seg, i) => {
              const netId = seg.net?.id ?? null;
              const isHighlighted = highlightedNet != null && netId === highlightedNet;
              return (
                <line
                  key={i}
                  x1={seg.start.x} y1={seg.start.y}
                  x2={seg.end.x}   y2={seg.end.y}
                  stroke={isHighlighted ? "#ffffff" : isAirwire ? PCB.airwire : baseColor}
                  strokeWidth={isAirwire ? 0.08 : (seg.width_mm ?? 0.2)}
                  strokeLinecap={isAirwire ? "butt" : "round"}
                  strokeDasharray={isAirwire ? "0.6 0.4" : undefined}
                  opacity={isAirwire ? 0.55 : isHighlighted ? 1 : 0.95}
                  onMouseEnter={() => netId != null && setHoveredNet(netId)}
                  onMouseLeave={() => setHoveredNet(null)}
                  style={{ cursor: netId != null ? "pointer" : "default" }}
                />
              );
            })}
          </g>
        );
      })}

      {/* Vias — concentric copper ring over drilled hole */}
      {geometry.vias?.map((v, i) => {
        const isHi = highlightedNet != null && v.net.id === highlightedNet;
        return (
          <g key={`via-${i}`}>
            <circle cx={v.x} cy={v.y} r={v.size_mm / 2} fill={isHi ? "#ffffff" : PCB.viaRing} />
            <circle cx={v.x} cy={v.y} r={v.drill_mm / 2} fill={PCB.viaHole} />
          </g>
        );
      })}

      {/* Pads — real copper pads under every component */}
      {geometry.footprints.map((fp, fpIdx) => {
        if (!visibleLayers.has(fp.layer)) return null;
        if (!fp.pads || fp.pads.length === 0) return null;
        const size = inferFootprintSize(fp.footprint, fp.ref);
        // Pad size heuristic by package kind — good enough visually without real geometry
        const padR = size.kind === "passive" || size.kind === "led" || size.kind === "diode"
          ? Math.min(size.w_mm, size.h_mm) * 0.45
          : size.kind === "ic" || size.kind === "module"
          ? Math.max(0.25, Math.min(size.w_mm, size.h_mm) * 0.06)
          : size.kind === "connector"
          ? 0.7
          : 0.45;
        return (
          <g key={`pads-${fpIdx}`}>
            {fp.pads.map((p, pi) => {
              const isHi = highlightedNet != null && p.net.id === highlightedNet;
              return (
                <circle
                  key={pi}
                  cx={p.wx} cy={p.wy} r={padR}
                  fill={isHi ? "#ffffff" : "url(#pcb-pad)"}
                  stroke={isHi ? "#fff" : "rgba(50,20,5,0.5)"}
                  strokeWidth={0.04}
                  onMouseEnter={() => setHoveredNet(p.net.id)}
                  onMouseLeave={() => setHoveredNet(null)}
                  style={{ cursor: "pointer" }}
                />
              );
            })}
          </g>
        );
      })}

      {/* Silkscreen: component body outlines + refs */}
      {geometry.footprints.map((fp, fpIdx) => {
        if (!visibleLayers.has(fp.layer)) return null;
        const isSelected = selectedRef === fp.ref;
        const isHovered = hoveredRef === fp.ref;

        const size = inferFootprintSize(fp.footprint, fp.ref);
        const w = size.w_mm;
        const h = size.h_mm;

        // Body color for the chip itself (above the pads)
        const bodyFill =
          size.kind === "passive" ? "#1a1a1a"
          : size.kind === "led" ? "#fff0c8"
          : size.kind === "ic" ? "#1e1e1e"
          : size.kind === "module" ? "#121a14"
          : size.kind === "connector" ? "#1a2233"
          : size.kind === "mounting" ? "transparent"
          : "#1d1d1d";

        const isMounting = size.kind === "mounting";
        const labelSize = Math.min(Math.max(Math.min(w, h) * 0.32, 0.5), 1.2);

        return (
          <g
            key={`fp-${fpIdx}`}
            transform={`translate(${fp.at.x},${fp.at.y}) rotate(${fp.at.rot_deg ?? 0})`}
            style={{ cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              onSelectRef(isSelected ? null : fp.ref);
            }}
            onMouseEnter={() => setHoveredRef(fp.ref)}
            onMouseLeave={() => setHoveredRef(null)}
          >
            {/* Selection halo */}
            {isSelected && (
              <rect
                x={-w / 2 - 0.7} y={-h / 2 - 0.7}
                width={w + 1.4} height={h + 1.4}
                rx={0.4}
                fill="none"
                stroke="#7aeaff"
                strokeWidth={0.12}
                strokeDasharray="0.3 0.2"
                opacity={0.9}
              />
            )}
            {isHovered && !isSelected && (
              <rect
                x={-w / 2 - 0.3} y={-h / 2 - 0.3}
                width={w + 0.6} height={h + 0.6}
                rx={0.25}
                fill="rgba(255,255,255,0.06)"
              />
            )}

            {/* Mounting hole special rendering */}
            {isMounting ? (
              <>
                <circle r={w / 2} fill={PCB.substrate} stroke={PCB.copperTop} strokeWidth={0.15} />
                <circle r={w / 3.5} fill="#03080b" />
              </>
            ) : (
              <>
                {/* Silkscreen body outline */}
                <rect
                  x={-w / 2 - 0.1} y={-h / 2 - 0.1}
                  width={w + 0.2} height={h + 0.2}
                  rx={0.15}
                  fill="none"
                  stroke={PCB.silkscreen}
                  strokeWidth={0.08}
                  opacity={0.55}
                />
                {/* Body */}
                <rect
                  x={-w / 2} y={-h / 2} width={w} height={h}
                  rx={Math.min(0.2, Math.min(w, h) * 0.08)}
                  fill={bodyFill}
                  stroke="rgba(0,0,0,0.6)"
                  strokeWidth={0.04}
                  opacity={fp.layer === "B.Cu" ? 0.75 : 1}
                />
                {/* Pin-1 dot on ICs/modules */}
                {(size.kind === "ic" || size.kind === "module") && (
                  <circle
                    cx={-w / 2 + Math.min(0.8, w * 0.08)}
                    cy={-h / 2 + Math.min(0.8, h * 0.08)}
                    r={Math.min(0.18, w * 0.03)}
                    fill={PCB.silkscreen}
                    opacity={0.85}
                  />
                )}
                {/* Silkscreen ref (beside body — looks printed, not baked in) */}
                {Math.min(w, h) > 1.4 && (
                  <text
                    x={0} y={-h / 2 - 0.35}
                    fontSize={labelSize}
                    fill={PCB.silkscreen}
                    fontFamily="monospace"
                    fontWeight="700"
                    textAnchor="middle"
                    filter="url(#silk-depth)"
                    style={{ pointerEvents: "none", userSelect: "none" }}
                  >
                    {fp.ref}
                  </text>
                )}
              </>
            )}

            {/* Callout on hover / select */}
            {(isHovered || isSelected) && (
              <g transform={`rotate(${-(fp.at.rot_deg ?? 0)})`}>
                <rect
                  x={w / 2 + 0.5} y={-h / 2 - 1.9}
                  width={Math.max(fp.ref.length, (fp.value || "").length) * 0.62 + 1.8}
                  height={2.6}
                  rx={0.25}
                  fill="rgba(5,10,15,0.95)"
                  stroke="#7aeaff"
                  strokeWidth={0.07}
                />
                <text
                  x={w / 2 + 0.9} y={-h / 2 - 0.7}
                  fontSize={0.95}
                  fill="white"
                  fontFamily="monospace"
                  fontWeight="700"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {fp.ref}
                </text>
                <text
                  x={w / 2 + 0.9} y={-h / 2 + 0.45}
                  fontSize={0.7}
                  fill="rgba(255,255,255,0.65)"
                  fontFamily="monospace"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {fp.value || size.kind} · {w.toFixed(1)}×{h.toFixed(1)}mm
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* Board title — feels like a silkscreen tag off the board corner */}
      {bbox && (
        <text
          x={bbox.min_x}
          y={bbox.min_y - 1.8}
          fontSize={1.6}
          fill="rgba(255,255,255,0.35)"
          fontFamily="monospace"
          style={{ userSelect: "none", pointerEvents: "none" }}
        >
          {filename?.replace(/\.kicad_pcb$/i, "") ?? "Board"} · {bbox.width.toFixed(1)}×{bbox.height.toFixed(1)}mm
        </text>
      )}
    </svg>
  );
}
