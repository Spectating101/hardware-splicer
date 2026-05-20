"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Cpu, Zap, Radio, Gauge, Monitor, Wrench, Cable, Package,
  ExternalLink, Search, X, ChevronRight, BookOpen,
} from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import {
  MODULE_LIBRARY, searchModules, type ModuleSpec,
} from "@/lib/modules/module-library";

const CATEGORY_ICON: Record<string, typeof Cpu> = {
  mcu: Cpu, power: Zap, sensor: Gauge, display: Monitor,
  actuator: Wrench, radio: Radio, interface: Cable, passive: Wrench, other: Package,
};
const CATEGORY_LABEL: Record<string, string> = {
  mcu: "Microcontrollers", power: "Power", sensor: "Sensors",
  display: "Displays", actuator: "Actuators", radio: "Radios",
  interface: "Interfaces", passive: "Passives", other: "Other ICs",
};
const CATEGORY_ORDER = ["mcu", "power", "sensor", "actuator", "display", "radio", "interface", "passive", "other"];

const SOURCE_LABEL: Record<string, string> = {
  "curated-original": "Curated (original)",
  curated: "Curated (web-verified)",
  "ingested-kb-board": "Ingested (KB board)",
  "ingested-kb-ic": "Ingested (KB IC)",
  "ingested-datasheet-pdf": "Ingested (datasheet PDF)",
  "ingested-component-db": "Ingested (component DB)",
  "ingested-pinout-extract": "Ingested (pinout extract)",
};

export default function LibraryPage() {
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string | null>(null);
  const [tag, setTag] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let base = query.trim() ? searchModules(query) : MODULE_LIBRARY;
    if (cat) base = base.filter((m) => m.category === cat);
    if (tag) base = base.filter((m) => m.capabilityTags?.includes(tag));
    return base;
  }, [query, cat, tag]);

  const fullCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const m of MODULE_LIBRARY) c[m.category] = (c[m.category] ?? 0) + 1;
    return c;
  }, []);

  const sourceCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const m of MODULE_LIBRARY) c[m.source ?? "curated-original"] = (c[m.source ?? "curated-original"] ?? 0) + 1;
    return c;
  }, []);

  const tagCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const m of MODULE_LIBRARY)
      for (const t of m.capabilityTags ?? []) c[t] = (c[t] ?? 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, []);

  const selected = selectedId ? MODULE_LIBRARY.find((m) => m.id === selectedId) ?? null : null;

  return (
    <div className="flex min-h-screen flex-col bg-[#0a0f1a] text-white">
      <SiteHeader />

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <BookOpen className="h-3.5 w-3.5" /> Module library
            </div>
            <h1 className="mt-1 text-2xl font-semibold">Encyclopedia</h1>
            <p className="mt-1 text-sm text-slate-400">
              {MODULE_LIBRARY.length} modules across {Object.keys(fullCounts).length} categories.
              Curated specs plus pinouts ingested from datasheets and the component database. Each
              entry carries a datasheet URL and a source field for traceability.
            </p>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by id, label, partNumber, manufacturer, aliases…"
              className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
              autoFocus
            />
            {query && (
              <button onClick={() => setQuery("")} className="text-slate-500 hover:text-slate-300">
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={cat === null} onClick={() => setCat(null)} count={MODULE_LIBRARY.length}>
              all
            </Chip>
            {CATEGORY_ORDER.filter((c) => fullCounts[c]).map((c) => (
              <Chip key={c} active={cat === c} onClick={() => setCat(cat === c ? null : c)} count={fullCounts[c]}>
                {c}
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="self-center text-[10px] uppercase tracking-wider text-slate-500">capability:</span>
            {tag && (
              <Chip active onClick={() => setTag(null)}>
                {tag} <X className="ml-1 inline h-3 w-3" />
              </Chip>
            )}
            {!tag && tagCounts.slice(0, 12).map(([t, n]) => (
              <Chip key={t} onClick={() => setTag(t)} count={n}>{t}</Chip>
            ))}
          </div>
        </div>

        {/* Card grid */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {filtered.length === 0 && (
            <div className="col-span-full rounded-xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-500">
              No modules match.
            </div>
          )}
          {filtered.map((m) => (
            <ModuleCard key={m.id} m={m} onClick={() => setSelectedId(m.id)} />
          ))}
        </div>

        {/* Source provenance footer */}
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-[10px] text-slate-500">
          <div className="mb-1 font-semibold uppercase tracking-wider">Source provenance</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {Object.entries(sourceCounts).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
              <span key={s}>
                <span className="font-mono text-slate-400">{n}</span> {SOURCE_LABEL[s] ?? s}
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* Detail drawer */}
      {selected && (
        <ModuleDrawer m={selected} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}

function Chip({
  active = false, onClick, count, children,
}: {
  active?: boolean; onClick?(): void; count?: number; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] transition-colors ${
        active ? "bg-cyan-400/20 text-cyan-200" : "bg-white/5 text-slate-300 hover:bg-white/10"
      }`}
    >
      <span>{children}</span>
      {count != null && <span className="opacity-60">{count}</span>}
    </button>
  );
}

function ModuleCard({ m, onClick }: { m: ModuleSpec; onClick(): void }) {
  const Icon = CATEGORY_ICON[m.category] ?? Wrench;
  return (
    <button
      onClick={onClick}
      className="group flex flex-col gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-3 text-left hover:border-cyan-400/40 hover:bg-white/[0.04]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <Icon className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300/70" />
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-white">{m.label}</div>
            <div className="truncate text-[10px] font-mono uppercase tracking-wider text-slate-500">
              {m.id}
            </div>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-slate-600 group-hover:text-cyan-300" />
      </div>
      <div className="line-clamp-2 text-[12px] leading-snug text-slate-400">{m.summary}</div>
      <div className="mt-auto flex flex-wrap items-center gap-1">
        {(m.capabilityTags ?? []).slice(0, 4).map((t) => (
          <span key={t} className="rounded-full bg-white/5 px-1.5 py-px text-[9px] text-slate-400">
            {t}
          </span>
        ))}
      </div>
      {(m.partNumber || m.manufacturer) && (
        <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-slate-600">
          {m.partNumber && <span className="font-mono">{m.partNumber}</span>}
          {m.manufacturer && <span>· {m.manufacturer}</span>}
          {m.priceUsd != null && <span>· ~${m.priceUsd}</span>}
        </div>
      )}
    </button>
  );
}

function ModuleDrawer({ m, onClose }: { m: ModuleSpec; onClose(): void }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-white/10 bg-[#0a0f1a] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              {m.category} · {m.id}
            </div>
            <h2 className="mt-1 text-xl font-semibold">{m.label}</h2>
            <p className="mt-1 text-sm text-slate-300">{m.summary}</p>
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 hover:bg-white/10">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-x-4 gap-y-2 text-[11px] text-slate-400">
          {m.partNumber && <span><b className="text-slate-300">Part:</b> {m.partNumber}</span>}
          {m.manufacturer && <span><b className="text-slate-300">Mfr:</b> {m.manufacturer}</span>}
          {m.priceUsd != null && <span><b className="text-slate-300">~Price:</b> ${m.priceUsd}</span>}
          {m.inputVoltageRange && (
            <span><b className="text-slate-300">VIN:</b> {m.inputVoltageRange[0]}-{m.inputVoltageRange[1]}V</span>
          )}
          {m.logicVoltage && (
            <span><b className="text-slate-300">Logic:</b> {m.logicVoltage}V</span>
          )}
          {m.datasheetUrl && (
            <a href={m.datasheetUrl} target="_blank" rel="noopener noreferrer"
               className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200">
              datasheet <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>

        {m.capabilityTags && m.capabilityTags.length > 0 && (
          <div className="mb-4">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Capability tags
            </div>
            <div className="flex flex-wrap gap-1">
              {m.capabilityTags.map((t) => (
                <span key={t} className="rounded-full bg-cyan-400/10 px-2 py-0.5 text-[11px] text-cyan-200">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {m.warnings && m.warnings.length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-400/30 bg-amber-500/5 p-3 text-xs text-amber-200">
            <div className="mb-1 font-semibold uppercase tracking-wider text-[10px]">Warnings</div>
            <ul className="list-disc space-y-1 pl-4">
              {m.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Pinout ({m.pins.length})
          </div>
          <div className="overflow-hidden rounded-lg border border-white/10">
            <table className="w-full text-xs">
              <thead className="bg-white/5 text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-2 py-1.5 text-left">Pin</th>
                  <th className="px-2 py-1.5 text-left">Role</th>
                  <th className="px-2 py-1.5 text-left">Voltage</th>
                  <th className="px-2 py-1.5 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {m.pins.map((p) => (
                  <tr key={p.id} className="border-t border-white/5">
                    <td className="px-2 py-1.5 font-mono text-slate-200">{p.label}</td>
                    <td className="px-2 py-1.5"><RoleBadge role={p.role} /></td>
                    <td className="px-2 py-1.5 text-slate-400">{p.voltage ?? "—"}</td>
                    <td className="px-2 py-1.5 text-[11px] text-slate-400">{p.notes ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-6 border-t border-white/10 pt-3 text-[10px] text-slate-500">
          Source: <span className="font-mono">{m.source ?? "curated-original"}</span>
          {" · "}
          <Link href={`/build?preload=${encodeURIComponent(m.id)}`} className="text-cyan-300 hover:text-cyan-200">
            open in /build canvas →
          </Link>
        </div>
      </div>
    </div>
  );
}

const ROLE_COLOR: Record<string, string> = {
  power_in: "bg-rose-500/15 text-rose-200",
  power_out: "bg-emerald-500/15 text-emerald-200",
  gnd: "bg-slate-500/20 text-slate-300",
  digital_io: "bg-cyan-500/15 text-cyan-200",
  digital_in: "bg-cyan-500/10 text-cyan-300",
  digital_out: "bg-cyan-500/10 text-cyan-300",
  analog_in: "bg-violet-500/15 text-violet-200",
  pwm: "bg-amber-500/15 text-amber-200",
  uart_tx: "bg-blue-500/15 text-blue-200",
  uart_rx: "bg-blue-500/15 text-blue-200",
  i2c_sda: "bg-fuchsia-500/15 text-fuchsia-200",
  i2c_scl: "bg-fuchsia-500/15 text-fuchsia-200",
  spi_mosi: "bg-pink-500/15 text-pink-200",
  spi_miso: "bg-pink-500/15 text-pink-200",
  spi_sck: "bg-pink-500/15 text-pink-200",
  spi_cs: "bg-pink-500/15 text-pink-200",
  reset: "bg-orange-500/15 text-orange-200",
  other: "bg-white/5 text-slate-400",
};
function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`rounded px-1.5 py-px text-[10px] font-mono uppercase ${ROLE_COLOR[role] ?? ROLE_COLOR.other}`}>
      {role}
    </span>
  );
}
