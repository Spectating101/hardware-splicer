"use client";

import { useState, useMemo } from "react";
import type { PcbGeometry } from "@/lib/cad-types";
import type { LayerVis } from "@/lib/workbench-store";

interface LayerPanelProps {
  geometry: PcbGeometry | null;
  layers: LayerVis[];
  selectedRef: string | null;
  onToggleLayer: (name: string) => void;
  onSelectRef: (ref: string | null) => void;
}

export function LayerPanel({
  geometry,
  layers,
  selectedRef,
  onToggleLayer,
  onSelectRef,
}: LayerPanelProps) {
  const [search, setSearch] = useState("");

  // Only show layers that have actual data or are always-present
  const activeLayers = useMemo(() => {
    if (!geometry) return layers.filter((l) => ["F.Cu", "B.Cu", "Edge.Cuts"].includes(l.name));
    const usedLayerNames = new Set<string>();
    for (const seg of geometry.segments) usedLayerNames.add(seg.layer);
    for (const fp of geometry.footprints) usedLayerNames.add(fp.layer);
    usedLayerNames.add("Edge.Cuts");
    // Airwire is always useful to toggle as long as any pads on multi-pad nets exist
    if (geometry.segments.some((s) => s.layer === "Airwire")) usedLayerNames.add("Airwire");
    return layers.filter((l) => usedLayerNames.has(l.name));
  }, [geometry, layers]);

  const filteredRefs = useMemo(() => {
    if (!geometry) return [];
    const q = search.trim().toUpperCase();
    return geometry.footprints
      .filter((fp) => !q || fp.ref.toUpperCase().includes(q) || fp.value.toUpperCase().includes(q))
      .sort((a, b) => a.ref.localeCompare(b.ref, undefined, { numeric: true }));
  }, [geometry, search]);

  return (
    <div className="w-52 flex-shrink-0 bg-[#0b1220] border-r border-white/8 flex flex-col overflow-hidden">
      {/* Layers section */}
      <div className="flex-shrink-0 px-3 pt-3 pb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2">
          Layers
        </p>
        <div className="space-y-0.5">
          {activeLayers.map((layer) => (
            <button
              key={layer.name}
              onClick={() => onToggleLayer(layer.name)}
              className="w-full flex items-center gap-2 px-2 py-1 rounded-md hover:bg-white/5 transition-colors group"
            >
              {/* Color swatch / visibility indicator */}
              <span
                className="w-3 h-3 rounded-sm flex-shrink-0 border border-white/10"
                style={{
                  backgroundColor: layer.visible ? layer.color : "transparent",
                  borderColor: layer.visible ? layer.color : "rgba(255,255,255,0.15)",
                  opacity: layer.visible ? 1 : 0.4,
                }}
              />
              <span
                className={`text-xs font-mono truncate transition-colors ${
                  layer.visible ? "text-white/80" : "text-white/30"
                }`}
              >
                {layer.name}
              </span>
              {/* Segment count badge */}
              {geometry && (() => {
                const count = geometry.segments.filter((s) => s.layer === layer.name).length;
                if (count === 0) return null;
                return (
                  <span className="ml-auto text-[9px] text-white/20 flex-shrink-0 group-hover:text-white/40">
                    {count}
                  </span>
                );
              })()}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-white/8 mx-3" />

      {/* Components section */}
      <div className="flex flex-col flex-1 overflow-hidden px-3 pt-2 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2 flex-shrink-0">
          Components{geometry ? ` (${geometry.footprints.length})` : ""}
        </p>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter refs…"
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
                    style={{ backgroundColor: isFront ? "#c84b4b" : "#4b8fc8" }}
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
