"use client";

import { Upload, MessageSquareQuote, LayoutGrid, GraduationCap, Zap, ArrowRight, type LucideIcon } from "lucide-react";

interface Door {
  key: "file" | "describe" | "catalog" | "learn";
  Icon: LucideIcon;
  title: string;
  subtitle: string;
  hint: string;
  accent: string;   // tailwind colour family suffix, e.g. "cyan"
}

const DOORS: Door[] = [
  {
    key: "file",
    Icon: Upload,
    title: "Open a .kicad_pcb",
    subtitle: "Drop a board, I'll parse it and run the full pipeline",
    hint: "drop / browse",
    accent: "cyan",
  },
  {
    key: "describe",
    Icon: MessageSquareQuote,
    title: "Describe what to build",
    subtitle: "\"Temperature logger with BLE\" → I compile intent into a board",
    hint: "natural language",
    accent: "violet",
  },
  {
    key: "catalog",
    Icon: LayoutGrid,
    title: "Start from a template",
    subtitle: "Fork a validated reference design — ESP32 sensor, PSU, motor driver",
    hint: "catalog",
    accent: "amber",
  },
  {
    key: "learn",
    Icon: GraduationCap,
    title: "Just learning",
    subtitle: "Guided path from resistor basics to your first PCB order",
    hint: "learning paths",
    accent: "emerald",
  },
];

const ACCENTS: Record<string, { ring: string; icon: string; arrow: string; glow: string }> = {
  cyan:    { ring: "hover:border-cyan-500/40",    icon: "group-hover:text-cyan-300",    arrow: "group-hover:text-cyan-300",    glow: "group-hover:shadow-[0_0_24px_rgba(6,182,212,0.12)]" },
  violet:  { ring: "hover:border-violet-500/40",  icon: "group-hover:text-violet-300",  arrow: "group-hover:text-violet-300",  glow: "group-hover:shadow-[0_0_24px_rgba(139,92,246,0.12)]" },
  amber:   { ring: "hover:border-amber-500/40",   icon: "group-hover:text-amber-300",   arrow: "group-hover:text-amber-300",   glow: "group-hover:shadow-[0_0_24px_rgba(245,158,11,0.12)]" },
  emerald: { ring: "hover:border-emerald-500/40", icon: "group-hover:text-emerald-300", arrow: "group-hover:text-emerald-300", glow: "group-hover:shadow-[0_0_24px_rgba(16,185,129,0.12)]" },
};

export interface EmptyStateProps {
  onOpenFile?(): void;
  onDescribe?(): void;
  onCatalog?(): void;
  onLearn?(): void;
}

export function EmptyState({ onOpenFile, onDescribe, onCatalog, onLearn }: EmptyStateProps = {}) {
  const noop = () => {};
  const handlers: Record<Door["key"], () => void> = {
    file: onOpenFile ?? noop,
    describe: onDescribe ?? noop,
    catalog: onCatalog ?? noop,
    learn: onLearn ?? noop,
  };

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
      <div className="absolute inset-8 rounded-3xl border border-dashed border-white/[0.04] pointer-events-none" />
      <div className="flex flex-col items-center gap-10 pointer-events-auto max-w-4xl px-6">
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div className="w-11 h-11 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
              <Zap size={20} className="text-cyan-400" />
            </div>
            <span className="absolute inset-0 rounded-xl border border-cyan-500/20 animate-ping opacity-30" />
          </div>
          <div className="text-center">
            <h2 className="text-white/80 text-lg font-medium tracking-tight">What are you starting with?</h2>
            <p className="text-white/35 text-xs mt-1">Pick any door — Circuit.AI bridges the full stack from intent to fab.</p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
          {DOORS.map((door) => {
            const a = ACCENTS[door.accent];
            return (
              <button
                key={door.key}
                onClick={handlers[door.key]}
                className={`group relative flex flex-col items-start gap-3 p-4 rounded-2xl border border-white/[0.07] bg-[#0f1624]/90 transition-all text-left ${a.ring} ${a.glow}`}
              >
                <div className="flex items-center justify-between w-full">
                  <door.Icon size={18} className={`text-white/35 transition-colors ${a.icon}`} />
                  <span className="text-[9px] uppercase tracking-wider text-white/25 font-mono">
                    {door.hint}
                  </span>
                </div>
                <div className="min-h-[3.25rem]">
                  <p className="text-[13px] text-white/80 font-medium leading-tight">{door.title}</p>
                  <p className="text-[11px] text-white/40 leading-snug mt-1">{door.subtitle}</p>
                </div>
                <ArrowRight size={12} className={`absolute bottom-3 right-3 text-white/20 transition-colors ${a.arrow}`} />
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-white/25 text-[11px]">
          <Upload size={11} />
          <span>or drop a <code className="text-white/45 font-mono">.kicad_pcb</code> / <code className="text-white/45 font-mono">.kicad_sch</code> anywhere on the canvas</span>
        </div>
      </div>
    </div>
  );
}
