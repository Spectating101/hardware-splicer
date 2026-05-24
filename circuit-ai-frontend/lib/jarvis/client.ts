// Server-side Jarvis LLM client. Uses fetch against provider REST APIs — no
// SDK dependency. Designed to run inside Next.js route handlers.
//
// Models:
//   - Claude Sonnet         → chat + identify + salvage + project (vision primary)
//   - DeepSeek V4           → chat + project text provider when configured
//   - Mistral               → legacy text fallback when configured
//
// Falls back to echo-mode when no suitable key is configured so devs can
// exercise the UI wiring without spending tokens.

import { JARVIS_PROMPTS, type JarvisFlow } from "./prompts";

const ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL = process.env.JARVIS_MODEL ?? "claude-sonnet-4-5-20250929";
const ANTHROPIC_VERSION = "2023-06-01";
const DEFAULT_DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL ?? "deepseek-v4-flash";

type TextProvider = "anthropic" | "deepseek" | "mistral";

export type JarvisMessage =
  | { role: "user"; content: string | JarvisContent[] }
  | { role: "assistant"; content: string | JarvisContent[] };

export type JarvisContent =
  | { type: "text"; text: string }
  | { type: "image"; source: { type: "base64"; media_type: string; data: string } };

export interface JarvisCallOptions {
  flow: JarvisFlow;
  messages: JarvisMessage[];
  model?: string;
  maxTokens?: number;
  /** When true, returns an AsyncIterable<string> of text deltas instead of a
   *  single resolved string. Used by the SSE chat endpoint. */
  stream?: boolean;
}

export interface JarvisResult {
  text: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  stopReason?: string;
}

function hasAnthropicKey(): boolean {
  return !!process.env.ANTHROPIC_API_KEY;
}

function hasDeepSeekKey(): boolean {
  return !!process.env.DEEPSEEK_API_KEY;
}

function hasMistralKey(): boolean {
  return !!process.env.MISTRAL_API_KEY;
}

function isTextOnlyFlow(flow: JarvisFlow): boolean {
  return flow === "chat" || flow === "project";
}

function requestedTextProvider(): TextProvider | null {
  const raw = process.env.JARVIS_TEXT_PROVIDER?.trim().toLowerCase();
  if (raw === "anthropic" || raw === "deepseek" || raw === "mistral") return raw;
  return null;
}

function chooseTextProvider(flow: JarvisFlow): Exclude<TextProvider, "anthropic"> | null {
  if (!isTextOnlyFlow(flow)) return null;
  const requested = requestedTextProvider();
  if (requested === "deepseek" && hasDeepSeekKey()) return "deepseek";
  if (requested === "mistral" && hasMistralKey()) return "mistral";
  if (requested) return null;
  if (!hasAnthropicKey() && hasDeepSeekKey()) return "deepseek";
  if (!hasAnthropicKey() && hasMistralKey()) return "mistral";
  return null;
}

function deepSeekEndpoint(): string {
  const base = (process.env.DEEPSEEK_BASE_URL ?? "https://api.deepseek.com").replace(/\/+$/, "");
  return base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
}

function deepSeekThinking(): { type: "enabled" | "disabled" } {
  return {
    type: process.env.DEEPSEEK_THINKING?.trim().toLowerCase() === "enabled" ? "enabled" : "disabled",
  };
}

/** Flatten Anthropic-style content blocks into a plain string for providers
 *  that don't accept array content. Drops image blocks silently. */
function flattenContent(c: string | JarvisContent[]): string {
  if (typeof c === "string") return c;
  return c.filter((b) => b.type === "text").map((b) => (b as { type: "text"; text: string }).text).join("\n");
}

function providerMessages(opts: JarvisCallOptions): Array<{ role: string; content: string }> {
  return [
    { role: "system", content: JARVIS_PROMPTS[opts.flow] },
    ...opts.messages.map((m) => ({ role: m.role, content: flattenContent(m.content) })),
  ];
}

function openAiContentToText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (part && typeof part === "object" && "text" in part) {
        const text = (part as { text?: unknown }).text;
        return typeof text === "string" ? text : "";
      }
      return "";
    })
    .join("");
}

/** Text-only provider via DeepSeek's OpenAI-compatible chat completions API.
 *  Vision flows still require the Anthropic path because PCB/photo payloads
 *  use image blocks. */
async function callDeepSeek(opts: JarvisCallOptions): Promise<JarvisResult> {
  const body: Record<string, unknown> = {
    model: opts.model ?? DEFAULT_DEEPSEEK_MODEL,
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
    thinking: deepSeekThinking(),
  };
  if (deepSeekThinking().type === "enabled") {
    body.reasoning_effort = process.env.DEEPSEEK_REASONING_EFFORT ?? "high";
  }

  const resp = await fetch(deepSeekEndpoint(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${process.env.DEEPSEEK_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.text().catch(() => "(unparseable)");
    throw new Error(`DeepSeek ${resp.status}: ${err.slice(0, 400)}`);
  }
  const json = await resp.json() as {
    choices: Array<{
      message?: { content?: unknown; reasoning_content?: string };
      finish_reason?: string;
    }>;
    model: string;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const message = json.choices[0]?.message;
  const text = openAiContentToText(message?.content) || message?.reasoning_content || "";
  return {
    text,
    model: json.model,
    inputTokens: json.usage?.prompt_tokens ?? 0,
    outputTokens: json.usage?.completion_tokens ?? 0,
    stopReason: json.choices[0]?.finish_reason,
  };
}

async function* streamDeepSeek(opts: JarvisCallOptions): AsyncGenerator<string, void, unknown> {
  const body: Record<string, unknown> = {
    model: opts.model ?? DEFAULT_DEEPSEEK_MODEL,
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
    thinking: deepSeekThinking(),
    stream: true,
  };
  if (deepSeekThinking().type === "enabled") {
    body.reasoning_effort = process.env.DEEPSEEK_REASONING_EFFORT ?? "high";
  }

  const resp = await fetch(deepSeekEndpoint(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${process.env.DEEPSEEK_API_KEY}`,
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    const err = await resp.text().catch(() => "(unparseable)");
    throw new Error(`DeepSeek stream ${resp.status}: ${err.slice(0, 400)}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const payload = dataLine.slice(6).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const evt = JSON.parse(payload) as {
          choices?: Array<{ delta?: { content?: string | null; reasoning_content?: string | null } }>;
        };
        const delta = evt.choices?.[0]?.delta?.content;
        if (delta) yield delta;
      } catch { /* skip */ }
    }
  }
}

/** Text-only fallback via Mistral. Used when ANTHROPIC_API_KEY is unset but
 *  MISTRAL_API_KEY is present. Vision flows (identify, salvage) still fall back
 *  to echo mode — Mistral's vision models need a different payload shape. */
async function callMistral(opts: JarvisCallOptions): Promise<JarvisResult> {
  const body = {
    model: process.env.MISTRAL_MODEL ?? "mistral-small-latest",
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
  };
  const resp = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${process.env.MISTRAL_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.text().catch(() => "(unparseable)");
    throw new Error(`Mistral ${resp.status}: ${err.slice(0, 400)}`);
  }
  const json = await resp.json() as {
    choices: Array<{ message?: { content?: string }; finish_reason?: string }>;
    model: string;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const text = json.choices[0]?.message?.content ?? "";
  return {
    text,
    model: json.model,
    inputTokens: json.usage?.prompt_tokens ?? 0,
    outputTokens: json.usage?.completion_tokens ?? 0,
    stopReason: json.choices[0]?.finish_reason,
  };
}

async function* streamMistral(opts: JarvisCallOptions): AsyncGenerator<string, void, unknown> {
  const body = {
    model: process.env.MISTRAL_MODEL ?? "mistral-small-latest",
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
    stream: true,
  };
  const resp = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${process.env.MISTRAL_API_KEY}`,
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) {
    const err = await resp.text().catch(() => "(unparseable)");
    throw new Error(`Mistral stream ${resp.status}: ${err.slice(0, 400)}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const payload = dataLine.slice(6).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const evt = JSON.parse(payload) as {
          choices?: Array<{ delta?: { content?: string } }>;
        };
        const delta = evt.choices?.[0]?.delta?.content;
        if (delta) yield delta;
      } catch { /* skip */ }
    }
  }
}

/** Echo response used when no API key is configured — keeps the UI wiring
 *  testable without network calls. Includes realistic shape for each flow. */
function echoFallback(flow: JarvisFlow, messages: JarvisMessage[]): JarvisResult {
  const lastUser = messages.filter((m) => m.role === "user").pop();
  const userText = (() => {
    if (!lastUser) return "";
    if (typeof lastUser.content === "string") return lastUser.content;
    return lastUser.content.filter((c) => c.type === "text").map((c) => (c as { type: "text"; text: string }).text).join("\n");
  })();
  const demo: Record<JarvisFlow, string> = {
    chat: `> _Running in demo mode (set \`ANTHROPIC_API_KEY\`, \`DEEPSEEK_API_KEY\`, or \`MISTRAL_API_KEY\` to get real answers)_\n\nYou asked: **${userText.slice(0, 200) || "(no prompt)"}**.\n\nIn production I'd explain this board to you in plain English, flag anything dangerous, and point out what's worth reusing.`,
    identify: JSON.stringify({
      safety_level: "safe",
      explanation: "Demo mode: this is a placeholder identification. Configure ANTHROPIC_API_KEY to enable real vision.",
      components: [
        { id: "C1", label: "Demo MCU", kind: "mcu", description: "Placeholder microcontroller block.", safety: "safe", bbox: { x: 0.1, y: 0.1, w: 0.3, h: 0.2 } },
        { id: "C2", label: "Demo power section", kind: "power", description: "Placeholder power regulator.", safety: "safe", bbox: { x: 0.55, y: 0.1, w: 0.3, h: 0.2 } },
      ],
    }),
    salvage: JSON.stringify({
      safety_level: "caution",
      explanation: "Demo mode salvage plan. Real mode analyzes your actual board.",
      modules: [
        { id: "M1", label: "Demo 5V buck", kind: "power", description: "Example reusable regulator.", safety: "caution", extraction: "Demo extraction notes." },
      ],
    }),
    project: JSON.stringify({
      safety_level: "safe",
      suggestions: [
        { id: "P1", title: "Demo weather station", difficulty: "beginner", summary: "Placeholder project.", requiredModules: ["ESP32", "DHT22"], safety: "safe", estimatedTimeHours: 2 },
      ],
    }),
  };
  return { text: demo[flow], model: "demo-echo", inputTokens: 0, outputTokens: 0, stopReason: "end_turn" };
}

/** Non-streaming single call. Returns complete text + usage. */
export async function callJarvis(opts: JarvisCallOptions): Promise<JarvisResult> {
  const textProvider = chooseTextProvider(opts.flow);
  if (textProvider === "deepseek") return callDeepSeek(opts);
  if (textProvider === "mistral") return callMistral(opts);

  if (!hasAnthropicKey()) {
    return echoFallback(opts.flow, opts.messages);
  }

  const body = {
    model: opts.model ?? DEFAULT_MODEL,
    max_tokens: opts.maxTokens ?? 1500,
    system: JARVIS_PROMPTS[opts.flow],
    messages: opts.messages,
  };

  const resp = await fetch(ANTHROPIC_ENDPOINT, {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY!,
      "anthropic-version": ANTHROPIC_VERSION,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => "(unparseable error)");
    throw new Error(`Jarvis API ${resp.status}: ${err.slice(0, 400)}`);
  }

  const json = await resp.json() as {
    content: Array<{ type: string; text?: string }>;
    model: string;
    usage: { input_tokens: number; output_tokens: number };
    stop_reason?: string;
  };

  const text = json.content
    .filter((c) => c.type === "text")
    .map((c) => c.text ?? "")
    .join("");

  return {
    text,
    model: json.model,
    inputTokens: json.usage.input_tokens,
    outputTokens: json.usage.output_tokens,
    stopReason: json.stop_reason,
  };
}

/** Streaming call. Yields text deltas as they arrive. Caller is responsible
 *  for piping them out as SSE. */
export async function* streamJarvis(opts: JarvisCallOptions): AsyncGenerator<string, void, unknown> {
  const textProvider = chooseTextProvider(opts.flow);
  if (textProvider === "deepseek") {
    yield* streamDeepSeek(opts);
    return;
  }
  if (textProvider === "mistral") {
    yield* streamMistral(opts);
    return;
  }

  if (!hasAnthropicKey()) {
    const fallback = echoFallback(opts.flow, opts.messages);
    // Simulate progressive stream.
    for (const chunk of fallback.text.match(/[\s\S]{1,20}/g) ?? [fallback.text]) {
      yield chunk;
      await new Promise((r) => setTimeout(r, 20));
    }
    return;
  }

  const body = {
    model: opts.model ?? DEFAULT_MODEL,
    max_tokens: opts.maxTokens ?? 1500,
    system: JARVIS_PROMPTS[opts.flow],
    messages: opts.messages,
    stream: true,
  };

  const resp = await fetch(ANTHROPIC_ENDPOINT, {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY!,
      "anthropic-version": ANTHROPIC_VERSION,
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok || !resp.body) {
    const err = await resp.text().catch(() => "(unparseable error)");
    throw new Error(`Jarvis stream ${resp.status}: ${err.slice(0, 400)}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE frames are separated by \n\n
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const payload = dataLine.slice(6).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const evt = JSON.parse(payload) as {
          type: string;
          delta?: { type?: string; text?: string };
        };
        if (evt.type === "content_block_delta" && evt.delta?.type === "text_delta" && evt.delta.text) {
          yield evt.delta.text;
        }
      } catch {
        // ignore malformed frames
      }
    }
  }
}

/** Utility: extract and parse the first JSON object from a model response. */
export function extractJson<T = unknown>(raw: string): T | null {
  const trimmed = raw.trim();
  // Strip markdown code fences if model ignored the "no fences" instruction.
  const cleaned = trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  try {
    return JSON.parse(cleaned) as T;
  } catch {
    // Try to find a top-level JSON object.
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start === -1 || end === -1 || end <= start) return null;
    try {
      return JSON.parse(cleaned.slice(start, end + 1)) as T;
    } catch {
      return null;
    }
  }
}
