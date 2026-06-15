"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Bot, Loader2, Send, Sparkles } from "lucide-react";
import { useJarvisChat } from "@/lib/jarvis/use-jarvis-chat";
import {
  buildJarvisContextString,
  buildUnmatchedUserGuidance,
  formatBuildToolSummary,
  runBuildTools,
  type BuildJarvisHandlers,
  type BuildJarvisSnapshot,
  type BuildToolInvocation,
  type BuildToolResult,
} from "@/lib/jarvis/build-agent";
import { expandAndDetectTools } from "@/lib/jarvis/build-tool-planner";

export function BuildJarvisPanel({
  getSnapshot,
  handlers,
}: {
  getSnapshot: () => BuildJarvisSnapshot;
  handlers: BuildJarvisHandlers;
}) {
  const [input, setInput] = useState("");
  const toolResultsRef = useRef<BuildToolResult[]>([]);
  const snapshotOverrideRef = useRef<BuildJarvisSnapshot | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const lastUserTextRef = useRef("");

  const contextProvider = useCallback(() => {
    const snap = snapshotOverrideRef.current ?? getSnapshot();
    snapshotOverrideRef.current = null;
    return buildJarvisContextString(snap, toolResultsRef.current, lastUserTextRef.current);
  }, [getSnapshot]);

  const { messages, isStreaming, send } = useJarvisChat({
    contextProvider,
    onComplete: () => {
      toolResultsRef.current = [];
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const planTools = useCallback(async (text: string, snap: BuildJarvisSnapshot): Promise<BuildToolInvocation[]> => {
    const ctx = { moduleCount: snap.moduleCount, wireCount: snap.wireCount };
    try {
      const resp = await fetch("/api/jarvis/plan-build-tools", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text, context: ctx }),
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) {
        const json = await resp.json() as { invocations?: BuildToolInvocation[] };
        if (json.invocations?.length) return json.invocations;
      }
    } catch {
      // offline / timeout — regex + phrase expander below
    }
    return expandAndDetectTools(text, ctx);
  }, []);

  const runTurn = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    lastUserTextRef.current = trimmed;
    const snapNow = getSnapshot();
    const invocations = await planTools(trimmed, snapNow);
    const { results, snapshot: snap } = await runBuildTools(trimmed, invocations, handlers, getSnapshot);
    toolResultsRef.current = results;
    if (snap) snapshotOverrideRef.current = snap;

    const summarySnap = snap ?? snapNow;
    const assistantPrefix = results.length > 0
      ? formatBuildToolSummary(results, summarySnap)
      : invocations.length === 0
        ? buildUnmatchedUserGuidance(trimmed, summarySnap)
        : undefined;

    await send(trimmed, { assistantPrefix });
  }, [handlers, isStreaming, send, getSnapshot, planTools]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void runTurn(input).then(() => setInput(""));
    }
  };

  const showGreeting = messages.length === 0;

  return (
    <div className="flex min-h-[280px] flex-1 flex-col overflow-hidden rounded-xl border border-violet-400/25 bg-violet-500/[0.04]">
      <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2">
        <Bot className="h-4 w-4 text-violet-300" />
        <span className="text-xs font-semibold text-violet-100">Jarvis</span>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2">
        {showGreeting && (
          <div className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-2 text-[11px] leading-5 text-slate-300">
            Talk to me like you&apos;d explain to a friend — no part numbers needed. I&apos;ll pick
            parts, wire them, check if it&apos;s safe to plug in, and can download starter code.
            Try: &quot;water my plants when the soil is dry&quot;, &quot;room temp on a small
            screen&quot;, or &quot;write the code for this board&quot; (PlatformIO ZIP).
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-lg px-2.5 py-2 text-[11px] leading-5 ${
              msg.role === "user"
                ? "ml-4 border border-white/10 bg-white/5 text-slate-200"
                : "mr-2 border border-violet-400/15 bg-violet-500/10 text-violet-50"
            }`}
          >
            {msg.role === "assistant" && (
              <div className="mb-1 flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-violet-300/80">
                <Sparkles className="h-3 w-3" />
                Jarvis
                {msg.streaming && <Loader2 className="h-3 w-3 animate-spin" />}
              </div>
            )}
            <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            {msg.error && (
              <div className="mt-1 text-[10px] text-rose-300">{msg.error}</div>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-1.5 border-t border-white/10 p-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={isStreaming}
          rows={3}
          placeholder="Water my plants when it's dry… or write the code for this board…"
          className="min-h-[3.5rem] flex-1 resize-none rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 text-[11px] text-white placeholder:text-slate-500 focus:border-violet-400/40 focus:outline-none disabled:opacity-50"
        />
        <button
          type="button"
          disabled={isStreaming || !input.trim()}
          onClick={() => void runTurn(input).then(() => setInput(""))}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-500 text-white hover:bg-violet-400 disabled:bg-white/10 disabled:text-slate-500"
          aria-label="Send"
        >
          {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}
