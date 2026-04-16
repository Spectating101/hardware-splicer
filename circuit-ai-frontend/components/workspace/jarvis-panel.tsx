"use client";

import { useRef, useEffect, useState, KeyboardEvent } from "react";
import { Zap, AlertTriangle, ChevronRight, Send, Cpu, Layers, Network, Ruler, CornerDownLeft } from "lucide-react";
import type { PcbGeometry, ValidationIssue } from "@/lib/cad-types";
import type { JarvisMsg } from "@/lib/workbench-store";
import { parseIntent, contextualResponse, generateBoardInsights, healthLabel } from "@/lib/jarvis";
import type { JarvisContext } from "@/lib/jarvis";
import { tokenize, chipToken, type ChatChipKind } from "@/lib/chat-tokens";

interface JarvisPanelProps {
  geometry: PcbGeometry | null;
  filename: string | null;
  issues: ValidationIssue[];
  healthScore: number | null;
  dfmNotes: string[];
  nextSteps: string[];
  messages: JarvisMsg[];
  thinking: boolean;
  pipeline: { parsed: boolean; validated: boolean; manufactured: boolean };
  selectedRef: string | null;
  onAddMessage(msg: { role: "user" | "jarvis"; text: string }): void;
  onSetThinking(v: boolean): void;
  onValidate(): void;
  onManufacture(): void;
  /** Chat-token chip handlers — click a chip in a message, act on the canvas. */
  onRefChip(ref: string): void;
  onNetChip(net: string): void;
  onIssueChip(id: string): void;
}

/** Tokenised message body: text runs + inline clickable chips for ref/net/issue. */
function MessageBody({
  text,
  onRefChip,
  onNetChip,
  onIssueChip,
}: {
  text: string;
  onRefChip: (ref: string) => void;
  onNetChip: (net: string) => void;
  onIssueChip: (id: string) => void;
}) {
  const parts = tokenize(text);
  return (
    <>
      {parts.map((p, i) => {
        if (p.kind === "text") return <span key={i}>{p.value}</span>;
        const style =
          p.kind === "ref"   ? "bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/30"
        : p.kind === "net"   ? "bg-violet-500/20 text-violet-100 hover:bg-violet-500/30"
        :                      "bg-amber-500/20 text-amber-100 hover:bg-amber-500/30";
        const onClick: (e: React.MouseEvent) => void =
          p.kind === "ref"   ? () => onRefChip(p.value)
        : p.kind === "net"   ? () => onNetChip(p.value)
        :                      () => onIssueChip(p.value);
        const label =
          p.kind === "ref"   ? p.value
        : p.kind === "net"   ? `net ${p.value}`
        :                      `issue #${p.value}`;
        return (
          <button
            key={i}
            onClick={onClick}
            className={`inline-flex items-center align-baseline rounded px-1.5 py-px font-mono text-[10px] leading-[1.1] mx-0.5 transition-colors ${style}`}
            title={`Click to focus ${p.kind}: ${p.value}`}
          >
            {label}
          </button>
        );
      })}
    </>
  );
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function InsightBullet({ level, label, body }: { level: "info" | "tip" | "warn"; label: string; body: string }) {
  const colors = {
    info: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    tip:  "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    warn: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  };
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${colors[level]}`}>
      <p className="text-[11px] font-semibold mb-0.5">{label}</p>
      <p className="text-[10px] opacity-80 leading-relaxed">{body}</p>
    </div>
  );
}

export function JarvisPanel({
  geometry,
  filename,
  issues,
  healthScore,
  dfmNotes,
  nextSteps,
  messages,
  thinking,
  pipeline,
  selectedRef,
  onAddMessage,
  onSetThinking,
  onValidate,
  onManufacture,
  onRefChip,
  onNetChip,
  onIssueChip,
}: JarvisPanelProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  // Cmd+K focuses input
  useEffect(() => {
    function onKey(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function submit() {
    const text = input.trim();
    if (!text) return;
    setInput("");
    onAddMessage({ role: "user", text });

    const intent = parseIntent(text);
    if (intent.type === "validate") {
      onValidate();
      return;
    }
    if (intent.type === "manufacture") {
      onManufacture();
      return;
    }

    onSetThinking(true);
    setTimeout(() => {
      onSetThinking(false);
      const critCount = issues.filter((i) => {
        const s = String(i.severity).toLowerCase();
        return s === "critical" || s === "error";
      }).length;
      const boardName = filename?.replace(/\.kicad_pcb$/i, "") ?? undefined;
      // Rank issues by severity; pluck up to 3 refs so the reply can surface
      // them as chip tokens for one-click navigation from chat to canvas.
      const sevOrder: Record<string, number> = { critical: 0, error: 1, warning: 2, info: 3 };
      const topIssueRefs = [...issues]
        .sort((a, b) => (sevOrder[String(a.severity).toLowerCase()] ?? 4) - (sevOrder[String(b.severity).toLowerCase()] ?? 4))
        .map((i) => i.component)
        .filter((r, i, arr) => !!r && arr.indexOf(r) === i)
        .slice(0, 3);
      const ctx: JarvisContext = {
        hasBoardNode: pipeline.parsed,
        hasValidation: pipeline.validated,
        hasManufacturing: pipeline.manufactured,
        hasCriticals: critCount > 0,
        activeIssueCount: issues.length,
        healthScore: healthScore ?? undefined,
        boardName,
        componentCount: geometry?.footprints.length,
        layerCount: geometry ? [...new Set(geometry.footprints.map(f => f.layer))].length : undefined,
        topIssueRefs,
        selectedRef: selectedRef ?? undefined,
      };
      const reply = contextualResponse(intent, ctx);
      onAddMessage({ role: "jarvis", text: reply });
    }, 600 + Math.random() * 400);
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  /** Paste a chip token into the composer — used by the canvas↔chat bridge. */
  function insertChip(kind: ChatChipKind, value: string) {
    const token = chipToken(kind, value);
    setInput((prev) => {
      const sep = prev.length === 0 || /\s$/.test(prev) ? "" : " ";
      return `${prev}${sep}${token} `;
    });
    // Defer focus until after React commits the new value so the caret lands
    // at the end. Focusing synchronously re-selects the old value.
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  // Board stats from geometry
  const componentCount = geometry?.footprints.length ?? 0;
  const netCount = geometry?.nets.length ?? 0;
  const layerNames = geometry
    ? [...new Set(geometry.footprints.map((f) => f.layer))].filter(Boolean)
    : [];
  const layerCount = layerNames.length;
  const bbox = geometry?.board.bbox_mm;

  // Selected component info
  const selectedFp = selectedRef
    ? geometry?.footprints.find((f) => f.ref === selectedRef)
    : null;
  const selectedIssues = selectedRef
    ? issues.filter((i) => i.component === selectedRef)
    : [];

  // Board insights
  const insights = geometry
    ? generateBoardInsights(componentCount, layerCount, netCount, healthScore ?? undefined)
    : [];

  // Health score bar color
  const scoreColor =
    healthScore == null ? "bg-white/20"
    : healthScore >= 80 ? "bg-emerald-500"
    : healthScore >= 60 ? "bg-amber-500"
    : "bg-red-500";

  return (
    <div className="w-72 flex-shrink-0 bg-[#0b1220] border-l border-white/8 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/8 flex-shrink-0">
        <div className="w-5 h-5 rounded bg-cyan-500/15 flex items-center justify-center">
          <Zap size={11} className="text-cyan-400" />
        </div>
        <span className="text-xs font-semibold text-white/80">JARVIS</span>
        {thinking && (
          <div className="ml-auto flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1 h-1 rounded-full bg-cyan-400 animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          {/* Board Stats */}
          {geometry && (
            <div className="px-3 pt-3 pb-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2">Board Stats</p>
              <div className="grid grid-cols-2 gap-1.5">
                <div className="bg-white/4 rounded-lg px-2.5 py-2 flex items-center gap-2">
                  <Cpu size={11} className="text-white/40 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-white/40">Components</p>
                    <p className="text-xs font-mono font-semibold text-white/80">{componentCount}</p>
                  </div>
                </div>
                <div className="bg-white/4 rounded-lg px-2.5 py-2 flex items-center gap-2">
                  <Layers size={11} className="text-white/40 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-white/40">Layers</p>
                    <p className="text-xs font-mono font-semibold text-white/80">{layerCount}L</p>
                  </div>
                </div>
                <div className="bg-white/4 rounded-lg px-2.5 py-2 flex items-center gap-2">
                  <Network size={11} className="text-white/40 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-white/40">Nets</p>
                    <p className="text-xs font-mono font-semibold text-white/80">{netCount}</p>
                  </div>
                </div>
                {bbox && (
                  <div className="bg-white/4 rounded-lg px-2.5 py-2 flex items-center gap-2">
                    <Ruler size={11} className="text-white/40 flex-shrink-0" />
                    <div>
                      <p className="text-[10px] text-white/40">Size</p>
                      <p className="text-xs font-mono font-semibold text-white/80">
                        {bbox.width.toFixed(0)}×{bbox.height.toFixed(0)}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Health score */}
              {healthScore != null && (
                <div className="mt-2.5">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[10px] text-white/40">Health Score</p>
                    <p className="text-[10px] font-mono font-semibold text-white/70">
                      {healthScore}/100 — {healthLabel(healthScore)}
                    </p>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${scoreColor}`}
                      style={{ width: `${healthScore}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Selected component */}
          {selectedFp && (
            <div className="px-3 pb-2">
              <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 px-2.5 py-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wide mb-1">Selected</p>
                    <p className="text-xs font-mono text-white/80">{selectedFp.ref}</p>
                    <p className="text-[10px] text-white/40 truncate">{selectedFp.value} · {selectedFp.footprint.split(":").pop()}</p>
                    <p className="text-[10px] text-white/30">{selectedFp.layer} · ({selectedFp.at.x.toFixed(1)}, {selectedFp.at.y.toFixed(1)}) mm</p>
                  </div>
                  <button
                    onClick={() => insertChip("ref", selectedFp.ref)}
                    title={`Paste [ref:${selectedFp.ref}] into the chat`}
                    className="flex items-center gap-1 flex-shrink-0 text-[10px] text-cyan-300/70 hover:text-cyan-200 bg-cyan-500/10 hover:bg-cyan-500/20 rounded px-1.5 py-0.5 transition-colors"
                  >
                    <CornerDownLeft size={9} />
                    <span>Chat</span>
                  </button>
                </div>
                {selectedIssues.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-1">
                    <AlertTriangle size={9} className="text-amber-400" />
                    <p className="text-[10px] text-amber-400">{selectedIssues.length} issue{selectedIssues.length > 1 ? "s" : ""}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* DFM / Mechanical notes */}
          {dfmNotes.length > 0 && (
            <div className="px-3 pb-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-1.5">
                DFM & Mechanical
              </p>
              <div className="space-y-1">
                {dfmNotes.slice(0, 4).map((note, i) => (
                  <div key={i} className="flex items-start gap-1.5 px-2 py-1.5 rounded-md bg-white/3">
                    <ChevronRight size={9} className="text-purple-400 flex-shrink-0 mt-0.5" />
                    <p className="text-[10px] text-white/55 leading-relaxed">{note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Board insights */}
          {insights.length > 0 && (
            <div className="px-3 pb-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-1.5">
                Insights
              </p>
              <div className="space-y-1.5">
                {insights.map((ins, i) => (
                  <InsightBullet key={i} level={ins.level} label={ins.label} body={ins.body} />
                ))}
              </div>
            </div>
          )}

          {/* Conversation messages */}
          {messages.length > 0 && (
            <div className="px-3 pb-2">
              {(geometry || insights.length > 0) && <div className="border-t border-white/8 mb-2" />}
              <div className="space-y-2">
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col gap-0.5 ${msg.role === "user" ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-lg px-2.5 py-1.5 text-[11px] leading-relaxed ${
                        msg.role === "user"
                          ? "bg-cyan-500/15 text-cyan-100"
                          : "bg-white/5 text-white/75"
                      }`}
                    >
                      <MessageBody
                        text={msg.text}
                        onRefChip={onRefChip}
                        onNetChip={onNetChip}
                        onIssueChip={onIssueChip}
                      />
                    </div>
                    <p className="text-[9px] text-white/20">{relativeTime(msg.ts)}</p>
                  </div>
                ))}
              </div>
              {thinking && (
                <div className="flex items-center gap-1.5 mt-2 px-1">
                  <div className="flex gap-0.5">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="w-1 h-1 rounded-full bg-white/30 animate-bounce"
                        style={{ animationDelay: `${i * 120}ms` }}
                      />
                    ))}
                  </div>
                  <p className="text-[10px] text-white/30">JARVIS is thinking…</p>
                </div>
              )}
            </div>
          )}

          {/* Empty state — no geometry, no messages */}
          {!geometry && messages.length === 0 && (
            <div className="px-3 pt-4 pb-2">
              <p className="text-[11px] text-white/30 leading-relaxed">
                Drop a <span className="text-cyan-400 font-mono">.kicad_pcb</span> file on the canvas
                to get started. I&apos;ll analyze the board and walk you through validation, DFM, and manufacturing.
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Command input */}
        <div className="flex-shrink-0 px-3 py-2.5 border-t border-white/8">
          <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 focus-within:border-cyan-500/40 transition-colors">
            <Zap size={10} className="text-cyan-400/60 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask JARVIS… (⌘K)"
              className="flex-1 bg-transparent text-xs text-white placeholder:text-white/25 outline-none min-w-0"
            />
            {input.trim() && (
              <button
                onClick={submit}
                className="flex-shrink-0 text-cyan-400 hover:text-cyan-200 transition-colors"
              >
                <Send size={11} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
