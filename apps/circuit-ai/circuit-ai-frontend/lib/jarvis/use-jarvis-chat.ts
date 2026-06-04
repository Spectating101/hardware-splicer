"use client";

import { useCallback, useRef, useState } from "react";

export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  /** True while the assistant is still streaming tokens. */
  streaming?: boolean;
  /** Populated if the stream ended in an error. */
  error?: string;
}

export interface UseJarvisChatOptions {
  /** Optional text injected before the first user turn (e.g. current board
   *  geometry summary). Re-evaluated on every send. */
  contextProvider?: () => string | undefined;
  /** Called when the assistant's message fully finishes streaming. */
  onComplete?: (finalText: string) => void;
}

/** Hook for any UI that wants to talk to /api/jarvis/chat. Handles SSE parsing,
 *  streaming state, cancellation. */
export function useJarvisChat(opts: UseJarvisChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (userText: string) => {
    if (!userText.trim()) return;
    const userMsg: ChatMsg = { role: "user", content: userText.trim() };
    const assistantMsg: ChatMsg = { role: "assistant", content: "", streaming: true };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const ctl = new AbortController();
    abortRef.current = ctl;

    const outgoing = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));
    const context = opts.contextProvider?.();

    try {
      const resp = await fetch("/api/jarvis/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: outgoing, context }),
        signal: ctl.signal,
      });

      if (!resp.ok || !resp.body) {
        const text = await resp.text().catch(() => "");
        throw new Error(`Chat failed (${resp.status}): ${text.slice(0, 200)}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let final = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const frame of frames) {
          const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          const payload = dataLine.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload) as { delta?: string; done?: boolean; error?: string };
            if (evt.error) throw new Error(evt.error);
            if (evt.delta) {
              final += evt.delta;
              setMessages((prev) => {
                const next = prev.slice();
                const last = next[next.length - 1];
                if (last?.role === "assistant") {
                  next[next.length - 1] = { ...last, content: final };
                }
                return next;
              });
            }
          } catch {
            // malformed frame — skip
          }
        }
      }

      setMessages((prev) => {
        const next = prev.slice();
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { ...last, streaming: false };
        }
        return next;
      });
      opts.onComplete?.(final);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { ...last, streaming: false };
          }
          return next;
        });
      } else {
        const msg = err instanceof Error ? err.message : String(err);
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { ...last, streaming: false, error: msg };
          }
          return next;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [messages, opts]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, send, cancel, reset };
}
