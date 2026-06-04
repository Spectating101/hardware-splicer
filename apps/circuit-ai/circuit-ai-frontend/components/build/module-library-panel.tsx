"use client";

import { useMemo, useState } from "react";
import { Cpu, Zap, Radio, Gauge, Monitor, Wrench, Cable, Package, ExternalLink } from "lucide-react";
import { MODULE_LIBRARY, searchModules, type ModuleSpec } from "@/lib/modules/module-library";

const CATEGORY_ICON: Record<string, typeof Cpu> = {
  mcu: Cpu,
  power: Zap,
  radio: Radio,
  sensor: Gauge,
  display: Monitor,
  actuator: Wrench,
  interface: Cable,
  passive: Wrench,
  other: Package,
};

const CATEGORY_LABEL: Record<string, string> = {
  mcu: "Microcontrollers",
  power: "Power",
  sensor: "Sensors",
  display: "Display",
  actuator: "Actuators",
  radio: "Radio",
  interface: "Interface",
  passive: "Passive",
  other: "Other ICs",
};

const CATEGORY_ORDER = ["mcu", "power", "sensor", "actuator", "display", "radio", "interface", "passive", "other"];

interface ModuleLibraryPanelProps {
  onAdd(spec: ModuleSpec): void;
}

export function ModuleLibraryPanel({ onAdd }: ModuleLibraryPanelProps) {
  const [query, setQuery] = useState("");
  const [activeCat, setActiveCat] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const base = query.trim() ? searchModules(query) : MODULE_LIBRARY;
    return activeCat ? base.filter((m) => m.category === activeCat) : base;
  }, [query, activeCat]);

  const byCategory = useMemo(() => {
    const acc: Record<string, ModuleSpec[]> = {};
    for (const m of filtered) (acc[m.category] ??= []).push(m);
    return acc;
  }, [filtered]);

  const fullCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const m of MODULE_LIBRARY) c[m.category] = (c[m.category] ?? 0) + 1;
    return c;
  }, []);

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-white/10 bg-black/40">
      <div className="border-b border-white/10 p-3">
        <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          <span>Module library</span>
          <span className="font-mono text-slate-600">{MODULE_LIBRARY.length}</span>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search id, label, part #, mfr…"
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-white/20 focus:outline-none"
        />
        <div className="mt-2 flex flex-wrap gap-1">
          <button
            onClick={() => setActiveCat(null)}
            className={`rounded-full px-2 py-0.5 text-[10px] ${activeCat === null ? "bg-cyan-400/20 text-cyan-200" : "bg-white/5 text-slate-400 hover:bg-white/10"}`}
          >
            all
          </button>
          {CATEGORY_ORDER.filter((c) => fullCounts[c]).map((c) => (
            <button
              key={c}
              onClick={() => setActiveCat(activeCat === c ? null : c)}
              className={`rounded-full px-2 py-0.5 text-[10px] ${activeCat === c ? "bg-cyan-400/20 text-cyan-200" : "bg-white/5 text-slate-400 hover:bg-white/10"}`}
              title={CATEGORY_LABEL[c]}
            >
              {c} <span className="opacity-60">{fullCounts[c]}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {filtered.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-slate-500">No modules match.</div>
        )}
        {CATEGORY_ORDER.filter((c) => byCategory[c]).map((cat) => {
          const Icon = CATEGORY_ICON[cat] ?? Wrench;
          const mods = byCategory[cat];
          return (
            <div key={cat} className="mb-3">
              <div className="mb-1 flex items-center justify-between gap-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <Icon className="h-3 w-3" />
                  {CATEGORY_LABEL[cat] ?? cat}
                </span>
                <span className="font-mono text-slate-600">{mods.length}</span>
              </div>
              <div className="space-y-1">
                {mods.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => onAdd(m)}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/circuit-module", m.id);
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                    className="group w-full cursor-grab rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-2 text-left text-xs hover:border-white/20 hover:bg-white/[0.05] active:cursor-grabbing"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="font-medium text-white">{m.label}</div>
                      {m.datasheetUrl && (
                        <a
                          href={m.datasheetUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="shrink-0 text-slate-500 opacity-0 hover:text-cyan-300 group-hover:opacity-100"
                          title="Datasheet"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-400">
                      {m.summary}
                    </div>
                    {(m.partNumber || m.manufacturer) && (
                      <div className="mt-1 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-slate-600">
                        {m.partNumber && <span className="font-mono">{m.partNumber}</span>}
                        {m.manufacturer && <span>· {m.manufacturer}</span>}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
