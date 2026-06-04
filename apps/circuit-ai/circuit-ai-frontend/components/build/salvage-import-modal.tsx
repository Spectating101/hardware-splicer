"use client";

import { useState } from "react";
import { X, Recycle, AlertCircle, CheckCircle2 } from "lucide-react";
import {
  splicePlanToBuildGraph,
  SUPPORTED_BUILD_IDS,
  type SalvagePlanInput,
  type TranslationResult,
} from "@/lib/salvage/plan-to-graph";

const EXAMPLE_PLAN: SalvagePlanInput = {
  target: { recommended_build_id: "sensor_logger" },
  reusable_blocks: [
    { id: "fan_1", name: "12V case fan", capabilities: ["motor_or_load", "fan_or_pump"], source: "junk_pc" },
    { id: "psu_1", name: "5V wall adapter", capabilities: ["power"], source: "junk_pc" },
    { id: "btn_1", name: "Reset button", capabilities: ["switch_or_button"], source: "junk_router" },
  ],
  build_candidates: [{ id: "sensor_logger", name: "Sensor logger or alert module" }],
};

export function SalvageImportModal({
  open,
  onClose,
  onImport,
}: {
  open: boolean;
  onClose(): void;
  onImport(result: TranslationResult): void;
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);

  if (!open) return null;

  const tryImport = () => {
    setErr(null);
    let plan: SalvagePlanInput;
    try {
      plan = JSON.parse(text);
    } catch (e) {
      setErr(`Plan JSON is invalid: ${e instanceof Error ? e.message : String(e)}`);
      return;
    }
    const result = splicePlanToBuildGraph(plan);
    if (result.graph.nodes.length === 0) {
      setErr(result.warnings.join(" ") || "Plan produced an empty graph.");
      return;
    }
    onImport(result);
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-[min(680px,92vw)] max-h-[88vh] overflow-hidden rounded-2xl border border-white/10 bg-[#0a0f1a] shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-200">
            <Recycle className="h-4 w-4" /> Import salvage plan
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 p-5">
          <p className="text-xs leading-5 text-slate-300">
            Paste a <code className="font-mono text-emerald-300">/salvage/splice-plan</code>{" "}
            response. The translator turns its <code>recommended_build_id</code> into a wired
            BuildGraph that drops into the canvas — ready to route, DRC, and manufacture.
          </p>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder='{ "target": { "recommended_build_id": "sensor_logger" }, ... }'
            className="h-56 w-full resize-none rounded-lg border border-white/10 bg-black/40 p-3 font-mono text-[11px] leading-5 text-slate-100 focus:border-emerald-400/40 focus:outline-none"
            spellCheck={false}
          />

          {err && (
            <div className="flex items-start gap-2 rounded-lg border border-rose-400/40 bg-rose-500/5 p-2.5 text-xs text-rose-200">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{err}</span>
            </div>
          )}

          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] text-slate-500">
              Supported builds ({SUPPORTED_BUILD_IDS.length}):{" "}
              <span className="font-mono">{SUPPORTED_BUILD_IDS.slice(0, 4).join(", ")}…</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setText(JSON.stringify(EXAMPLE_PLAN, null, 2))}
                className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/10"
              >
                Load example
              </button>
              <button
                onClick={tryImport}
                disabled={!text.trim()}
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-emerald-300 disabled:bg-white/10 disabled:text-slate-500"
              >
                <CheckCircle2 className="h-3.5 w-3.5" /> Import
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
