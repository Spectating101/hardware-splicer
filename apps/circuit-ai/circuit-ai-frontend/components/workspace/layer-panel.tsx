"use client";

import { useState, useMemo } from "react";
import {
  Eye, EyeOff, Waves, ShieldAlert, Zap, Activity, Thermometer,
  Package, Layers as LayersIcon, Move3d,
  type LucideIcon,
} from "lucide-react";
import type { PcbGeometry } from "@/lib/cad-types";
import type { Lenses } from "@/lib/workbench-store";

interface LayerPanelProps {
  geometry: PcbGeometry | null;
  lenses: Lenses;
  selectedRef: string | null;
  /** Which data-backed lenses have a backing stream available. */
  availability: {
    voltage: boolean;
    current: boolean;
    thermal: boolean;
    bom: boolean;
  };
  onToggleLens: <K extends keyof Lenses>(key: K) => void;
  onSetLens: <K extends keyof Lenses>(key: K, value: Lenses[K]) => void;
  onSelectRef: (ref: string | null) => void;
}

/** Each lens maps a backend data stream onto the 3D canvas. Absent data ⇒ disabled. */
const LENS_DEFS: Array<{
  key: keyof Omit<Lenses, "explode">;
  label: string;
  hint: string;
  Icon: LucideIcon;
  color: string;
  requires?: (g: PcbGeometry | null) => boolean;
}> = [
  {
    key: "netFocus", label: "Net focus",
    hint: "Hover or click any trace/pad to isolate its full net.",
    Icon: Waves, color: "#9fe8ff",
  },
  {
    key: "drc", label: "DRC halos",
    hint: "Flagged components get a red halo with a linked issue.",
    Icon: ShieldAlert, color: "#ff5a5a",
  },
  {
    key: "voltage", label: "Voltage drop",
    hint: "Gradient along each power net from source to load (MNA solver).",
    Icon: Zap, color: "#ffd66b",
  },
  {
    key: "current", label: "Current flow",
    hint: "Animated UV scroll on traces — thickness × scroll-speed scale with I (A).",
    Icon: Activity, color: "#7effb8",
  },
  {
    key: "thermal", label: "Thermal",
    hint: "Fragment-shader contour bands around hot parts (Tj projection).",
    Icon: Thermometer, color: "#ff8a4a",
  },
  {
    key: "bom", label: "BOM risk",
    hint: "Tint parts by supply risk: availability, leadtime, price.",
    Icon: Package, color: "#c49bff",
  },
  {
    key: "peelMask", label: "Peel solder mask",
    hint: "Hide the green mask to reveal raw copper + inner layers.",
    Icon: LayersIcon, color: "#d99763",
  },
];

export function LayerPanel({
  geometry,
  lenses,
  selectedRef,
  availability,
  onToggleLens,
  onSetLens,
  onSelectRef,
}: LayerPanelProps) {
  const disabledByData: Record<string, boolean> = {
    voltage: !availability.voltage,
    current: !availability.current,
    thermal: !availability.thermal,
    bom: !availability.bom,
  };
  const [search, setSearch] = useState("");

  const filteredRefs = useMemo(() => {
    if (!geometry) return [];
    const q = search.trim().toUpperCase();
    return geometry.footprints
      .filter((fp) => !q || fp.ref.toUpperCase().includes(q) || fp.value.toUpperCase().includes(q))
      .sort((a, b) => a.ref.localeCompare(b.ref, undefined, { numeric: true }));
  }, [geometry, search]);

  return (
    <div className="w-56 flex-shrink-0 bg-[#0b1220] border-r border-white/8 flex flex-col overflow-hidden">
      {/* Lenses */}
      <div className="flex-shrink-0 px-3 pt-3 pb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2">
          Lenses
        </p>
        <div className="space-y-0.5">
          {LENS_DEFS.map(({ key, label, hint, Icon, color }) => {
            const on = lenses[key];
            const disabled = disabledByData[key] ?? false;
            return (
              <button
                key={key}
                onClick={() => !disabled && onToggleLens(key)}
                disabled={disabled}
                title={disabled ? `${hint}\n\n(no backend data for this lens on this board)` : hint}
                className={`w-full flex items-center gap-2 px-2 py-1 rounded-md transition-colors text-left ${
                  disabled ? "opacity-40 cursor-not-allowed" : on ? "bg-white/5" : "hover:bg-white/5"
                }`}
              >
                <Icon size={12} className="flex-shrink-0" style={{ color: on && !disabled ? color : "rgba(255,255,255,0.3)" }} />
                <span className={`text-xs flex-1 truncate transition-colors ${
                  disabled ? "text-white/30" : on ? "text-white/90" : "text-white/45"
                }`}>
                  {label}
                </span>
                {disabled ? (
                  <span className="text-[9px] text-white/25 font-mono">n/a</span>
                ) : on ? (
                  <Eye size={11} className="text-white/50" />
                ) : (
                  <EyeOff size={11} className="text-white/20" />
                )}
              </button>
            );
          })}
        </div>

        {/* Explode slider — sits with the lenses because it's a view transform */}
        <div className="mt-2 px-2 py-1.5 rounded-md bg-white/[0.03]">
          <label className="flex items-center gap-2 text-[11px] text-white/55">
            <Move3d size={11} className="text-cyan-300/70" />
            <span className="flex-1">Explode</span>
            <span className="font-mono text-white/70">{Math.round(lenses.explode * 100)}%</span>
          </label>
          <input
            type="range"
            min={0} max={1} step={0.02}
            value={lenses.explode}
            onChange={(e) => onSetLens("explode", Number(e.target.value))}
            className="w-full mt-1 accent-cyan-400"
          />
        </div>
      </div>

      <div className="border-t border-white/8 mx-3" />

      {/* Component browser */}
      <div className="flex flex-col flex-1 overflow-hidden px-3 pt-2 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2 flex-shrink-0">
          Components{geometry ? ` · ${geometry.footprints.length}` : ""}
        </p>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter refs / values…"
          className="w-full bg-white/5 border border-white/10 rounded-md px-2 py-1 text-xs text-white placeholder:text-white/25 outline-none focus:border-white/25 mb-2 flex-shrink-0"
        />
        <div className="flex-1 overflow-y-auto space-y-0.5 -mx-1 px-1">
          {!geometry ? (
            <p className="text-xs text-white/25 px-1 py-2">No board loaded.</p>
          ) : filteredRefs.length === 0 ? (
            <p className="text-xs text-white/25 px-1 py-2">No matches.</p>
          ) : (
            filteredRefs.map((fp, i) => {
              const isSelected = selectedRef === fp.ref;
              const isFront = fp.layer === "F.Cu";
              return (
                <button
                  key={`${fp.ref}-${i}`}
                  onClick={() => onSelectRef(isSelected ? null : fp.ref)}
                  className={`w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-left transition-colors ${
                    isSelected
                      ? "bg-cyan-500/15 text-cyan-200"
                      : "hover:bg-white/5 text-white/70"
                  }`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: isFront ? "#d99763" : "#7aa1ff" }}
                  />
                  <span className="text-xs font-mono font-medium">{fp.ref}</span>
                  <span className="text-[10px] text-white/35 truncate ml-1">{fp.value}</span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
