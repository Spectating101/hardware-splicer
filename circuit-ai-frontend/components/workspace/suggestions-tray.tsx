"use client";

import { useCallback, useEffect, useState } from "react";
import { Wand2, Check, X, Loader2, Sparkles, TrendingUp } from "lucide-react";

export interface LayoutSuggestion {
  id: string;
  title: string;
  reason: string;
  confidence: number;   // 0–1
  impact?: string;      // "trace length -12%", "thermal margin +8°C", etc.
  target?: string;      // ref designator affected (for highlight)
  kind?: "move" | "rotate" | "swap" | "reroute" | "decouple" | "other";
}

export interface SuggestionsTrayProps {
  /** Whether the board is in a state where advice makes sense. */
  ready: boolean;
  filename: string | null;
  /** Called after apply succeeds so the caller can refresh geometry / message log. */
  onApplied?: (s: LayoutSuggestion, revisionId: string | null) => void;
  onHighlight?: (ref: string | null) => void;
  onMessage?: (role: "user" | "jarvis", text: string) => void;
}

export function SuggestionsTray({ ready, filename, onApplied, onHighlight, onMessage }: SuggestionsTrayProps) {
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<LayoutSuggestion[]>([]);
  const [applying, setApplying] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const fetchAdvice = useCallback(async () => {
    if (!ready) return;
    setLoading(true);
    onMessage?.("jarvis", "Asking the layout engine for improvement ideas via `/api/v2/layout/advice`…");
    try {
      const res = await fetch("/api/proxy/layout/advice", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ filename }),
      });
      const json = await res.json().catch(() => ({} as { suggestions?: LayoutSuggestion[]; error?: string }));
      if (!res.ok || json.error) {
        onMessage?.("jarvis", `Layout engine unavailable — ${json.error ?? res.status}. Showing heuristic placeholders for the UX shape.`);
        setSuggestions(PLACEHOLDERS);
      } else {
        const raw: LayoutSuggestion[] = Array.isArray(json.suggestions) && json.suggestions.length
          ? json.suggestions
          : PLACEHOLDERS;
        setSuggestions(raw);
        onMessage?.("jarvis", `${raw.length} layout suggestion${raw.length === 1 ? "" : "s"} ready. Review and apply what fits.`);
      }
    } catch {
      onMessage?.("jarvis", "Network error fetching layout advice — showing heuristic placeholders.");
      setSuggestions(PLACEHOLDERS);
    } finally {
      setLoading(false);
    }
  }, [ready, filename, onMessage]);

  // Auto-fetch the first time iterate mode is opened with a validated board.
  useEffect(() => {
    if (ready && suggestions.length === 0 && !loading) {
      fetchAdvice();
    }
  }, [ready, suggestions.length, loading, fetchAdvice]);

  const apply = useCallback(async (s: LayoutSuggestion) => {
    setApplying(s.id);
    onMessage?.("user", `Apply suggestion: **${s.title}**`);
    try {
      const res = await fetch("/api/proxy/projects/revisions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ filename, suggestion_id: s.id, kind: s.kind, target: s.target }),
      });
      const json = await res.json().catch(() => ({} as { revision_id?: string; error?: string }));
      if (!res.ok || json.error) {
        onMessage?.("jarvis", `Couldn't commit revision — ${json.error ?? res.status}. (Endpoint will land when projects are wired.)`);
        onApplied?.(s, null);
      } else {
        onMessage?.("jarvis", `Revision **${json.revision_id ?? "r?"}** committed — **${s.title}**.`);
        onApplied?.(s, json.revision_id ?? null);
      }
      // Either way, hide the card — it's been acted on.
      setDismissed((d) => new Set(d).add(s.id));
    } catch {
      onMessage?.("jarvis", "Network error committing revision.");
    } finally {
      setApplying(null);
    }
  }, [filename, onApplied, onMessage]);

  const dismiss = useCallback((s: LayoutSuggestion) => {
    setDismissed((d) => new Set(d).add(s.id));
  }, []);

  const visible = suggestions.filter((s) => !dismissed.has(s.id));

  if (!ready) {
    return (
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-md px-4 py-2 rounded-lg bg-[#0f1624]/95 border border-violet-500/30 text-[11px] text-violet-200 shadow-lg pointer-events-auto">
        Validate the board first — then Iterate suggestions unlock.
      </div>
    );
  }

  return (
    <div className="absolute top-3 left-3 right-3 z-20 flex flex-col gap-2 pointer-events-none">
      <div className="flex items-center gap-2 pointer-events-auto">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-violet-500/15 border border-violet-500/30 text-[10px] font-semibold text-violet-200 uppercase tracking-wider">
          <Wand2 size={11} />
          <span>Jarvis suggestions</span>
          {suggestions.length > 0 && (
            <span className="font-mono text-violet-300/80">{visible.length}/{suggestions.length}</span>
          )}
        </div>
        <button
          onClick={fetchAdvice}
          disabled={loading}
          className="inline-flex items-center gap-1 text-[10px] text-white/45 hover:text-violet-300 disabled:opacity-50 transition-colors"
          title="Ask the layout engine again"
        >
          {loading ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
          {loading ? "Thinking…" : "Refresh"}
        </button>
      </div>

      {visible.length === 0 && !loading && (
        <div className="pointer-events-auto max-w-md px-3 py-2 rounded-lg bg-[#0f1624]/90 border border-white/8 text-[11px] text-white/50">
          No open suggestions. Board is in good shape — or dismiss-stack is full.
        </div>
      )}

      <div className="flex flex-col gap-2 max-w-[420px] pointer-events-auto">
        {visible.slice(0, 4).map((s) => (
          <div
            key={s.id}
            onMouseEnter={() => s.target && onHighlight?.(s.target)}
            onMouseLeave={() => onHighlight?.(null)}
            className="group rounded-xl bg-[#0f1624]/95 border border-white/10 hover:border-violet-500/40 transition-colors p-3 shadow-lg backdrop-blur-sm"
          >
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[12px] font-medium text-white/85 leading-tight">{s.title}</span>
                  <ConfidenceDot value={s.confidence} />
                  {s.target && (
                    <span className="font-mono text-[10px] text-cyan-300/80 bg-cyan-500/10 border border-cyan-500/20 rounded px-1.5 py-px">
                      {s.target}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-white/50 leading-snug mt-1">{s.reason}</p>
                {s.impact && (
                  <div className="flex items-center gap-1 mt-1.5 text-[10px] text-emerald-300/80">
                    <TrendingUp size={9} />
                    <span className="font-mono">{s.impact}</span>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2.5">
              <button
                onClick={() => apply(s)}
                disabled={applying === s.id}
                className="flex items-center gap-1.5 text-[10.5px] font-medium bg-violet-500/20 hover:bg-violet-500/30 border border-violet-500/40 text-violet-100 rounded-md px-2.5 py-1 transition-colors disabled:opacity-50"
              >
                {applying === s.id ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
                {applying === s.id ? "Committing…" : "Apply"}
              </button>
              <button
                onClick={() => dismiss(s)}
                className="flex items-center gap-1 text-[10.5px] text-white/40 hover:text-white/70 rounded-md px-2 py-1 transition-colors"
              >
                <X size={10} />
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfidenceDot({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const tone = pct >= 80 ? "emerald" : pct >= 55 ? "amber" : "white";
  const cls = {
    emerald: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    amber:   "bg-amber-500/15 text-amber-300 border-amber-500/30",
    white:   "bg-white/5 text-white/45 border-white/10",
  }[tone];
  return (
    <span className={`inline-flex items-center border rounded-full px-1.5 py-px text-[9px] font-mono font-semibold ${cls}`}>
      {pct}%
    </span>
  );
}

/** Heuristic placeholders when backend layout engine is offline — the UX shape
 *  stays useful so devs can iterate on the tray without needing the backend. */
const PLACEHOLDERS: LayoutSuggestion[] = [
  {
    id: "p-decouple-1",
    title: "Add 100nF decoupling near VCC pin of U1",
    reason: "Bulk cap is 12mm from U1 VCC — a ceramic bypass at the pin reduces switching noise.",
    confidence: 0.87,
    impact: "switching noise −3dB",
    target: "U1",
    kind: "decouple",
  },
  {
    id: "p-shorten-2",
    title: "Shorten SDA trace to sensor",
    reason: "I2C SDA routes 42mm with a loop — a direct path saves length and reduces crosstalk.",
    confidence: 0.72,
    impact: "trace length −12mm",
    kind: "reroute",
  },
  {
    id: "p-rotate-3",
    title: "Rotate connector J1 180°",
    reason: "Current orientation forces a long USB D+/D− detour. 180° rotation lets traces run straight.",
    confidence: 0.64,
    impact: "skew ↓ ~0.4ns",
    target: "J1",
    kind: "rotate",
  },
];
