"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Trash2, Sparkles, Clock, ArrowRight, Camera, Wand2 } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { usePageTitle } from "@/components/use-page-title";
import { loadInventory, saveInventory } from "@/lib/inventory/storage";
import { SafetyBanner } from "@/components/safety-banner";
import type { InventoryPart, ProjectSuggestion, SafetyLevel, SalvageModule } from "@/lib/cad-types";

const KIND_OPTIONS: Array<{ value: SalvageModule["kind"]; label: string }> = [
  { value: "mcu", label: "MCU" },
  { value: "power", label: "Power" },
  { value: "sensor", label: "Sensor" },
  { value: "driver", label: "Driver" },
  { value: "radio", label: "Radio" },
  { value: "connector", label: "Connector" },
  { value: "passive", label: "Passive" },
  { value: "unknown", label: "Other" },
];

export default function PartsPage() {
  usePageTitle("Parts | Circuit.AI");

  const [inventory, setInventory] = useState<InventoryPart[]>([]);
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<SalvageModule["kind"]>("mcu");
  const [qty, setQty] = useState(1);

  const [suggesting, setSuggesting] = useState(false);
  const [suggestions, setSuggestions] = useState<ProjectSuggestion[]>([]);
  const [safety, setSafety] = useState<SafetyLevel>("safe");
  const [explanation, setExplanation] = useState<string | null>(null);
  const [suggestError, setSuggestError] = useState<string | null>(null);

  useEffect(() => {
    setInventory(loadInventory());
  }, []);

  useEffect(() => {
    saveInventory(inventory);
  }, [inventory]);

  const addPart = useCallback(() => {
    const trimmed = label.trim();
    if (!trimmed) return;
    const part: InventoryPart = {
      id: `p-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      label: trimmed,
      kind,
      source: "typed",
      qty: Math.max(1, qty),
      addedAt: Date.now(),
    };
    setInventory((prev) => [part, ...prev]);
    setLabel("");
    setQty(1);
  }, [label, kind, qty]);

  const removePart = useCallback((id: string) => {
    setInventory((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const askJarvis = useCallback(async () => {
    if (inventory.length === 0) {
      setSuggestError("Add some parts first.");
      return;
    }
    setSuggesting(true);
    setSuggestError(null);
    try {
      const resp = await fetch("/api/jarvis/suggest-project", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          inventory: inventory.map((p) => ({ label: p.label, kind: p.kind, qty: p.qty })),
        }),
      });
      if (!resp.ok) throw new Error(`Suggest failed: ${resp.status}`);
      const data = await resp.json() as {
        suggestions?: ProjectSuggestion[];
        safety_level?: SafetyLevel;
        explanation?: string;
        error?: string;
      };
      if (data.error) throw new Error(data.error);
      setSuggestions(data.suggestions ?? []);
      setSafety(data.safety_level ?? "safe");
      setExplanation(data.explanation ?? null);
    } catch (err) {
      setSuggestError((err as Error).message);
    } finally {
      setSuggesting(false);
    }
  }, [inventory]);

  const totalCount = useMemo(() => inventory.reduce((sum, p) => sum + p.qty, 0), [inventory]);

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Your parts bin</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Tell Jarvis what's in your drawer. We'll suggest projects you can actually build today.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Add a part
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addPart()}
                  placeholder="e.g. ESP32 DevKit, 5V buck, DHT22"
                  className="min-w-[200px] flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-white/20 focus:outline-none"
                />
                <select
                  value={kind}
                  onChange={(e) => setKind(e.target.value as SalvageModule["kind"])}
                  className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white focus:border-white/20 focus:outline-none"
                >
                  {KIND_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value} className="bg-slate-900">
                      {o.label}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  min={1}
                  value={qty}
                  onChange={(e) => setQty(parseInt(e.target.value) || 1)}
                  className="w-16 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white focus:border-white/20 focus:outline-none"
                />
                <button
                  onClick={addPart}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
                >
                  <Plus className="h-4 w-4" /> Add
                </button>
              </div>
              <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
                <Link href="/scan" className="inline-flex items-center gap-1.5 text-cyan-300 hover:text-cyan-200">
                  <Camera className="h-3.5 w-3.5" /> Or add from a scan
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Inventory ({totalCount})
                </div>
              </div>
              {inventory.length === 0 ? (
                <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                  No parts yet. Add one above to get project suggestions.
                </div>
              ) : (
                <ul className="divide-y divide-white/5">
                  {inventory.map((p) => (
                    <li key={p.id} className="flex items-center gap-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-white">{p.label}</div>
                        <div className="text-xs text-slate-500">
                          {p.kind} · qty {p.qty} · {p.source}
                        </div>
                      </div>
                      <button
                        onClick={() => removePart(p.id)}
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-white/5 hover:text-rose-300"
                        aria-label="Remove"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <aside className="space-y-3">
            <button
              onClick={askJarvis}
              disabled={suggesting || inventory.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-50"
            >
              <Wand2 className="h-4 w-4" />
              {suggesting ? "Thinking…" : "What can I build?"}
            </button>

            {suggestError && (
              <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 p-3 text-xs text-rose-200">
                {suggestError}
              </div>
            )}

            {safety !== "safe" && (
              <SafetyBanner
                level={safety}
                message={
                  safety === "hazard"
                    ? "Your parts include something with serious hazards (mains, lithium, high-voltage)."
                    : "Some of your parts need care — check the project-level notes before you build."
                }
              />
            )}

            {explanation && (
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs leading-5 text-slate-300">
                {explanation}
              </div>
            )}

            {suggestions.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Suggested projects
                </div>
                {suggestions.map((s) => (
                  <div key={s.id} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                    <div className="flex items-start gap-2">
                      <Sparkles className="mt-0.5 h-3.5 w-3.5 text-cyan-300" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold text-white">{s.title}</div>
                        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500">
                          <span className="uppercase tracking-wider">{s.difficulty}</span>
                          {s.estimatedTimeHours && (
                            <span className="inline-flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {s.estimatedTimeHours}h
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-300">{s.summary}</p>
                    {s.requiredModules && s.requiredModules.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {s.requiredModules.map((m, i) => (
                          <span
                            key={i}
                            className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                    <Link
                      href={`/build?modules=${encodeURIComponent((s.requiredModules ?? []).join(","))}`}
                      className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-cyan-300 hover:text-cyan-200"
                    >
                      Open in Build <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </aside>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
