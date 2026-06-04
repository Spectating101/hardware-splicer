// Server-side Jarvis LLM client. Uses fetch against provider REST APIs — no
// SDK dependency. Designed to run inside Next.js route handlers.
//
// Models:
//   - Claude Sonnet         → chat + identify + salvage + project
//   - GitHub Copilot CLI    → chat + project + evidence-mediated identify/salvage
//   - Qwen VL               → paid native image identify/salvage when explicitly configured
//   - DeepSeek V4           → chat + project text provider when configured
//   - Mistral               → legacy text fallback when configured
//
// Falls back to echo-mode when no suitable key is configured so devs can
// exercise the UI wiring without spending tokens.

import fs from "node:fs";
import path from "node:path";
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";

import { JARVIS_PROMPTS, type JarvisFlow } from "./prompts";
import {
  assertVisionBudgetAllowsCall,
  estimateQwenCostUsd,
  getVisionBudgetPolicy,
  getVisionBudgetSnapshotSync,
  recordVisionUsage,
} from "./vision-budget";

const execFileAsync = promisify(execFile);

let parentEnvCache: Record<string, string> | null = null;

function parseEnvFile(text: string): Record<string, string> {
  const parsed: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    const rawValue = line.slice(eq + 1).trim();
    parsed[key] = rawValue.replace(/^(['"])(.*)\1$/, "$2");
  }
  return parsed;
}

function parentEnv(): Record<string, string> {
  if (parentEnvCache) return parentEnvCache;
  const candidates = [
    path.resolve(process.cwd(), "..", ".env.local"),
    path.resolve(process.cwd(), "..", ".env"),
  ];
  for (const file of candidates) {
    try {
      if (fs.existsSync(file)) {
        parentEnvCache = parseEnvFile(fs.readFileSync(file, "utf8"));
        return parentEnvCache;
      }
    } catch {
      // Ignore unreadable local env files; normal process.env still applies.
    }
  }
  parentEnvCache = {};
  return parentEnvCache;
}

function envValue(name: string): string | undefined {
  return process.env[name] ?? parentEnv()[name];
}

const ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL = envValue("JARVIS_MODEL") ?? "claude-sonnet-4-5-20250929";
const ANTHROPIC_VERSION = "2023-06-01";
const DEFAULT_DEEPSEEK_MODEL = envValue("DEEPSEEK_MODEL") ?? "deepseek-v4-flash";
const DEFAULT_COPILOT_MODEL = envValue("COPILOT_MODEL") ?? "gpt-4.1";
const DEFAULT_QWEN_VISION_MODEL = envValue("QWEN_VISION_MODEL") ?? "qwen3-vl-flash";
const DEFAULT_QWEN_VISION_ROTATION = ["qwen3-vl-flash", "qwen3-vl-30b-a3b-thinking", "qwen-vl-ocr-2025-11-20"];
const DEFAULT_QWEN_LOW_QUOTA_MODELS = ["qwen-plus", "qwen-plus-2025-07-28"];

type TextProvider = "anthropic" | "copilot" | "deepseek" | "mistral";
type VisionProvider = "anthropic" | "copilot" | "qwen";

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
  budget?: {
    cacheKey?: string;
    estimatedUsd?: number;
  };
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
  estimatedCostUsd?: number;
}

export interface JarvisProviderStatus {
  requestedTextProvider: TextProvider | null;
  selectedTextProvider: TextProvider | "demo-echo" | null;
  selectedTextModel: string;
  textProviderReady: boolean;
  visionProvider: VisionProvider | "demo-echo";
  selectedVisionModel: string;
  visionProviderReady: boolean;
  configured: {
    anthropic: boolean;
    copilot: boolean;
    deepseek: boolean;
    mistral: boolean;
    qwen: boolean;
  };
  supportedFlows: {
    copilot: JarvisFlow[];
    qwen: JarvisFlow[];
    deepseek: JarvisFlow[];
    anthropic: JarvisFlow[];
    mistral: JarvisFlow[];
  };
  paidVisionBudget: ReturnType<typeof getVisionBudgetSnapshotSync>;
  qwenRouting: {
    disabled: boolean;
    lowQuotaModels: string[];
    visionRotation: string[];
    selectedVisionModel: string;
  };
  blockers: string[];
}

function hasAnthropicKey(): boolean {
  return !!envValue("ANTHROPIC_API_KEY");
}

function hasDeepSeekKey(): boolean {
  return !!envValue("DEEPSEEK_API_KEY");
}

function hasMistralKey(): boolean {
  return !!envValue("MISTRAL_API_KEY");
}

function hasQwenKey(): boolean {
  if (qwenDisabled()) return false;
  return !!(envValue("QWEN_API_KEY") || envValue("DASHSCOPE_API_KEY"));
}

function qwenBudgetConfigured(): boolean {
  return getVisionBudgetPolicy().enabled;
}

function shellWords(value: string | undefined, fallback: string[]): string[] {
  const text = value?.trim();
  if (!text) return fallback;
  return text.split(/\s+/).filter(Boolean);
}

function systemNodeSupportsCopilot(): boolean {
  try {
    const version = execFileSync("node", ["--version"], { encoding: "utf8", timeout: 2000 }).trim();
    const major = Number.parseInt(version.replace(/^v/, "").split(".")[0] ?? "", 10);
    return Number.isFinite(major) && major >= 20;
  } catch {
    return false;
  }
}

function copilotRunner(): string[] {
  if (envValue("COPILOT_NODE_RUNNER")) {
    return shellWords(envValue("COPILOT_NODE_RUNNER"), []);
  }
  return systemNodeSupportsCopilot() ? [] : ["npx", "-y", "node@20"];
}

function copilotExecutable(runner: string[]): string {
  const configured = envValue("COPILOT_COMMAND")?.trim();
  if (configured) return configured;
  if (runner.length) {
    try {
      const resolved = execFileSync("which", ["copilot"], { encoding: "utf8", timeout: 2000 }).trim();
      if (resolved) return resolved;
    } catch {
      // Fall through to PATH lookup below.
    }
  }
  return "copilot";
}

function copilotCommandBase(): string[] {
  const runner = copilotRunner();
  return [...runner, copilotExecutable(runner)];
}

function hasCopilotCli(): boolean {
  try {
    const [bin, ...baseArgs] = copilotCommandBase();
    execFileSync(bin, [...baseArgs, "--version"], {
      encoding: "utf8",
      timeout: 20000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    return true;
  } catch {
    return false;
  }
}

function isTextOnlyFlow(flow: JarvisFlow): boolean {
  return flow === "chat" || flow === "project";
}

function isVisionFlow(flow: JarvisFlow): boolean {
  return flow === "identify" || flow === "salvage";
}

function requestedTextProvider(): TextProvider | null {
  const raw = envValue("JARVIS_TEXT_PROVIDER")?.trim().toLowerCase();
  if (raw === "anthropic" || raw === "copilot" || raw === "deepseek" || raw === "mistral") return raw;
  return null;
}

function requestedVisionProvider(): VisionProvider | null {
  const raw = envValue("JARVIS_VISION_PROVIDER")?.trim().toLowerCase();
  if (raw === "qwen") return raw;
  if (raw === "copilot") return raw;
  if (raw === "anthropic") return raw;
  return null;
}

function qwenDisabled(): boolean {
  return envFlag("QWEN_DISABLED", false) || envFlag("QWEN_OUT_OF_QUOTA", false);
}

function chooseTextProvider(flow: JarvisFlow): Exclude<TextProvider, "anthropic"> | null {
  if (!isTextOnlyFlow(flow)) return null;
  const requested = requestedTextProvider();
  if (requested === "copilot") {
    if (!hasCopilotCli()) {
      throw new Error("JARVIS_TEXT_PROVIDER=copilot requires the local copilot CLI and Node 20 runner.");
    }
    return "copilot";
  }
  if (requested === "deepseek") {
    if (!hasDeepSeekKey()) {
      throw new Error("JARVIS_TEXT_PROVIDER=deepseek requires DEEPSEEK_API_KEY for Jarvis text flows.");
    }
    return "deepseek";
  }
  if (requested === "mistral") {
    if (!hasMistralKey()) {
      throw new Error("JARVIS_TEXT_PROVIDER=mistral requires MISTRAL_API_KEY for Jarvis text flows.");
    }
    return "mistral";
  }
  if (requested === "anthropic") return null;
  if (hasCopilotCli()) return "copilot";
  if (!hasAnthropicKey() && hasDeepSeekKey()) return "deepseek";
  if (!hasAnthropicKey() && hasMistralKey()) return "mistral";
  return null;
}

function chooseVisionProvider(flow: JarvisFlow): VisionProvider | null {
  if (!isVisionFlow(flow)) return null;
  const requested = requestedVisionProvider();
  if (requested === "qwen") {
    if (qwenDisabled()) {
      throw new Error("JARVIS_VISION_PROVIDER=qwen is disabled because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set.");
    }
    if (!hasQwenKey()) {
      throw new Error("JARVIS_VISION_PROVIDER=qwen requires QWEN_API_KEY or DASHSCOPE_API_KEY.");
    }
    if (!qwenBudgetConfigured()) {
      throw new Error("JARVIS_VISION_PROVIDER=qwen requires VISION_MONTHLY_USD_LIMIT > 0 so paid calls are explicitly capped.");
    }
    return "qwen";
  }
  if (requested === "copilot") {
    if (!hasCopilotCli()) {
      throw new Error("JARVIS_VISION_PROVIDER=copilot requires the local copilot CLI and Node 20 runner.");
    }
    return "copilot";
  }
  if (requested === "anthropic") {
    if (!hasAnthropicKey()) {
      throw new Error("JARVIS_VISION_PROVIDER=anthropic requires ANTHROPIC_API_KEY for Jarvis vision flows.");
    }
    return "anthropic";
  }
  if (hasCopilotCli()) return "copilot";
  if (hasAnthropicKey()) return "anthropic";
  return null;
}

export function getJarvisProviderStatus(flow: JarvisFlow = "chat"): JarvisProviderStatus {
  const requested = requestedTextProvider();
  const blockers: string[] = [];
  let selectedTextProvider: JarvisProviderStatus["selectedTextProvider"] = null;
  let selectedTextModel = DEFAULT_MODEL;
  let visionProvider: JarvisProviderStatus["visionProvider"] = "demo-echo";
  let selectedVisionModel = "demo-echo";

  if (isTextOnlyFlow(flow)) {
    try {
      const provider = chooseTextProvider(flow);
      if (provider === "copilot") {
        selectedTextProvider = "copilot";
        selectedTextModel = DEFAULT_COPILOT_MODEL;
      } else if (provider === "deepseek") {
        selectedTextProvider = "deepseek";
        selectedTextModel = DEFAULT_DEEPSEEK_MODEL;
      } else if (provider === "mistral") {
        selectedTextProvider = "mistral";
        selectedTextModel = envValue("MISTRAL_MODEL") ?? "mistral-small-latest";
      } else if (hasAnthropicKey()) {
        selectedTextProvider = "anthropic";
      } else {
        selectedTextProvider = "demo-echo";
        selectedTextModel = "demo-echo";
        blockers.push("No Copilot CLI, Anthropic, DeepSeek, or Mistral provider configured for Jarvis text flows.");
      }
    } catch (err) {
      selectedTextProvider = null;
      selectedTextModel = "unavailable";
      blockers.push(err instanceof Error ? err.message : String(err));
    }
  } else {
    blockers.push(`${flow} is not a text-only Jarvis flow.`);
  }

  try {
    const selectedVisionProvider = chooseVisionProvider("identify");
    if (selectedVisionProvider === "copilot") {
      visionProvider = "copilot";
      selectedVisionModel = DEFAULT_COPILOT_MODEL;
    } else if (selectedVisionProvider === "qwen") {
      visionProvider = "qwen";
      selectedVisionModel = qwenVisionModelCandidates()[0];
    } else if (selectedVisionProvider === "anthropic") {
      visionProvider = "anthropic";
      selectedVisionModel = DEFAULT_MODEL;
    } else {
      blockers.push("No explicit Qwen, Copilot CLI, or Anthropic provider configured for Jarvis image flows.");
    }
  } catch (err) {
    blockers.push(err instanceof Error ? err.message : String(err));
  }

  return {
    requestedTextProvider: requested,
    selectedTextProvider,
    selectedTextModel,
    textProviderReady: selectedTextProvider !== null && selectedTextProvider !== "demo-echo",
    visionProvider,
    selectedVisionModel,
    visionProviderReady: visionProvider !== "demo-echo",
    configured: {
      anthropic: hasAnthropicKey(),
      copilot: hasCopilotCli(),
      deepseek: hasDeepSeekKey(),
      mistral: hasMistralKey(),
      qwen: hasQwenKey(),
    },
    supportedFlows: {
      copilot: ["chat", "identify", "salvage", "project"],
      qwen: ["identify", "salvage"],
      deepseek: ["chat", "project"],
      anthropic: ["chat", "identify", "salvage", "project"],
      mistral: ["chat", "project"],
    },
    paidVisionBudget: getVisionBudgetSnapshotSync(),
    qwenRouting: {
      disabled: qwenDisabled(),
      lowQuotaModels: qwenLowQuotaModels(),
      visionRotation: qwenVisionModelCandidates(),
      selectedVisionModel: qwenVisionModelCandidates()[0],
    },
    blockers,
  };
}

function deepSeekEndpoint(): string {
  const base = (envValue("DEEPSEEK_BASE_URL") ?? "https://api.deepseek.com").replace(/\/+$/, "");
  return base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
}

function deepSeekThinking(): { type: "enabled" | "disabled" } {
  return {
    type: envValue("DEEPSEEK_THINKING")?.trim().toLowerCase() === "enabled" ? "enabled" : "disabled",
  };
}

/** Flatten Anthropic-style content blocks into a plain string for providers
 *  that don't accept array content. Image blocks become explicit placeholders;
 *  Copilot image flows should include a text evidence packet alongside them. */
function flattenContent(c: string | JarvisContent[]): string {
  if (typeof c === "string") return c;
  return c.map((b) => {
    if (b.type === "text") return b.text;
    return `[image block omitted from text-only provider: ${b.source.media_type}, ${b.source.data.length} base64 chars]`;
  }).join("\n");
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

function qwenEndpoint(): string {
  const base = (
    envValue("QWEN_BASE_URL") ??
    envValue("DASHSCOPE_BASE_URL") ??
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
  ).replace(/\/+$/, "");
  return base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
}

function qwenApiKey(): string | undefined {
  return envValue("QWEN_API_KEY") ?? envValue("DASHSCOPE_API_KEY");
}

function envFlag(name: string, fallback = false): boolean {
  const raw = envValue(name)?.trim().toLowerCase();
  if (!raw) return fallback;
  if (["1", "true", "yes", "on"].includes(raw)) return true;
  if (["0", "false", "no", "off"].includes(raw)) return false;
  return fallback;
}

function envPositiveInt(name: string): number | undefined {
  const raw = envValue(name)?.trim();
  if (!raw) return undefined;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function envList(name: string, fallback: string[] = []): string[] {
  const raw = envValue(name)?.trim();
  if (!raw) return fallback;
  return raw.split(",").map((part) => part.trim()).filter(Boolean);
}

function qwenLowQuotaModels(): string[] {
  return envList("QWEN_LOW_QUOTA_MODELS", envList("QWEN_BLOCKED_MODELS", DEFAULT_QWEN_LOW_QUOTA_MODELS))
    .map((model) => model.toLowerCase());
}

function qwenModelIsBlocked(model: string, blocked = qwenLowQuotaModels()): boolean {
  const normalized = model.trim().toLowerCase();
  return blocked.some((item) => normalized === item || normalized.startsWith(`${item}-`));
}

function qwenVisionModelCandidates(requested?: string): string[] {
  const rawCandidates = [
    ...envList("QWEN_VISION_MODEL_ROTATION"),
    requested?.trim() ?? "",
    DEFAULT_QWEN_VISION_MODEL,
    ...DEFAULT_QWEN_VISION_ROTATION,
  ];
  const blocked = qwenLowQuotaModels();
  const seen = new Set<string>();
  const candidates: string[] = [];
  for (const raw of rawCandidates) {
    const model = raw.trim();
    const key = model.toLowerCase();
    if (!model || seen.has(key) || qwenModelIsBlocked(model, blocked)) continue;
    seen.add(key);
    candidates.push(model);
  }
  return candidates.length ? candidates : [DEFAULT_QWEN_VISION_ROTATION[0]];
}

function qwenQuotaError(status: number, text: string): boolean {
  const lowered = text.toLowerCase();
  return (status === 403 || status === 429) && ["allocationquota", "freequota", "free quota", "quota", "insufficient", "billing"].some((marker) => lowered.includes(marker));
}

type QwenContentBlock =
  | { type: "text"; text: string }
  | { type: "image_url"; image_url: { url: string }; max_pixels?: number };

type QwenMessage = { role: string; content: string | QwenContentBlock[] };
type QwenChatResponse = {
  choices: Array<{
    message?: { content?: unknown };
    finish_reason?: string;
  }>;
  model?: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number };
};

function qwenContent(content: string | JarvisContent[]): string | QwenContentBlock[] {
  if (typeof content === "string") return content;
  const maxPixels = envPositiveInt("QWEN_IMAGE_MAX_PIXELS");
  return content.map((block): QwenContentBlock => {
    if (block.type === "text") return { type: "text", text: block.text };
    return {
      type: "image_url",
      image_url: { url: `data:${block.source.media_type};base64,${block.source.data}` },
      ...(maxPixels ? { max_pixels: maxPixels } : {}),
    };
  });
}

function qwenSystemPrompt(flow: JarvisFlow): string {
  if (flow === "identify") {
    return [
      "You are Circuit-AI native vision. Inspect PCB/device images and return ONLY one compact JSON object.",
      "No markdown. No repeated keys. No prose outside JSON.",
      "Use safety_level exactly: safe, caution, or hazard.",
      "Top-level schema: safety_level, explanation, components, board_evidence.",
      "components: at most 8 visible items, each with id, label, kind, bbox, warnings. Keep labels and descriptions short. Use bbox as {x,y,w,h} normalized 0-1; never bbox_2d or box.",
      "board_evidence.schema_version must be board_evidence.v1.",
      "board_evidence arrays must be components, markings, regions, damage, connectors, test_points, salvage_candidates, recommended_checks.",
      "Do not invent pinouts, voltages, nets, exact part numbers, or repair certainty. Do not use product knowledge to name exact ICs unless markings are legible.",
      "Prefer unknown plus uncertainty.missing_evidence and uncertainty.next_actions when unsure.",
    ].join(" ");
  }
  if (flow === "salvage") {
    return [
      "You are Circuit-AI native vision. Inspect PCB/device images and return ONLY one compact JSON object.",
      "No markdown. No repeated keys. No prose outside JSON.",
      "Use safety_level exactly: safe, caution, or hazard.",
      "Top-level schema: safety_level, explanation, modules, board_evidence.",
      "modules: at most 6 independently reusable visible sections, each with id, label, kind, description, safety, bbox, extraction, warnings. Keep description and extraction under 12 words each. Use bbox as {x,y,w,h} normalized 0-1; never bbox_2d or box.",
      "board_evidence.schema_version must be board_evidence.v1.",
      "board_evidence arrays must be components, markings, regions, damage, connectors, test_points, salvage_candidates, recommended_checks.",
      "Do not invent pinouts, voltages, nets, exact part numbers, or reuse safety. Do not use product knowledge to name exact ICs unless markings are legible.",
      "Prefer unknown plus uncertainty.missing_evidence and uncertainty.next_actions when unsure.",
    ].join(" ");
  }
  return JARVIS_PROMPTS[flow];
}

function qwenMessages(opts: JarvisCallOptions): QwenMessage[] {
  return [
    { role: "system", content: qwenSystemPrompt(opts.flow) },
    ...opts.messages.map((message) => ({
      role: message.role,
      content: qwenContent(message.content),
    })),
  ];
}

async function callQwenVision(opts: JarvisCallOptions): Promise<JarvisResult> {
  if (qwenDisabled()) {
    throw new Error("Qwen vision is disabled because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set.");
  }
  const models = qwenVisionModelCandidates(opts.model);
  let json: QwenChatResponse | undefined;
  let selectedModel = models[0];
  const quotaErrors: string[] = [];
  for (const [index, model] of models.entries()) {
    assertVisionBudgetAllowsCall({
      provider: "qwen",
      model,
      flow: opts.flow,
      cacheKey: opts.budget?.cacheKey,
      estimatedUsd: opts.budget?.estimatedUsd,
    });

    const body: Record<string, unknown> = {
      model,
      max_tokens: opts.maxTokens ?? 2500,
      messages: qwenMessages(opts),
    };
    if (!envFlag("QWEN_JSON_MODE_DISABLED", false)) {
      body.response_format = { type: "json_object" };
    }
    if (envFlag("QWEN_VL_HIGH_RESOLUTION_IMAGES", false)) {
      body.vl_high_resolution_images = true;
    }

    const resp = await fetch(qwenEndpoint(), {
      method: "POST",
      headers: {
        authorization: `Bearer ${qwenApiKey()}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.text().catch(() => "(unparseable)");
      if (index < models.length - 1 && qwenQuotaError(resp.status, err)) {
        quotaErrors.push(`${model}: ${err.slice(0, 160)}`);
        continue;
      }
      throw new Error(`Qwen ${resp.status}: ${err.slice(0, 500)}`);
    }
    json = await resp.json() as QwenChatResponse;
    selectedModel = model;
    break;
  }
  if (json === undefined) {
    throw new Error(`Qwen model rotation exhausted: ${quotaErrors.join(" | ") || "no response"}`);
  }
  const resolvedModel = json.model ?? selectedModel;
  const inputTokens = json.usage?.prompt_tokens ?? 0;
  const outputTokens = json.usage?.completion_tokens ?? 0;
  const estimatedCostUsd = estimateQwenCostUsd(resolvedModel, inputTokens, outputTokens);
  await recordVisionUsage({
    provider: "qwen",
    model: resolvedModel,
    flow: opts.flow,
    cacheKey: opts.budget?.cacheKey,
    inputTokens,
    outputTokens,
    estimatedUsd: estimatedCostUsd,
  });
  return {
    text: openAiContentToText(json.choices[0]?.message?.content),
    model: `qwen/${resolvedModel}`,
    inputTokens,
    outputTokens,
    stopReason: json.choices[0]?.finish_reason,
    estimatedCostUsd,
  };
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
    body.reasoning_effort = envValue("DEEPSEEK_REASONING_EFFORT") ?? "high";
  }

  const resp = await fetch(deepSeekEndpoint(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${envValue("DEEPSEEK_API_KEY")}`,
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
    body.reasoning_effort = envValue("DEEPSEEK_REASONING_EFFORT") ?? "high";
  }

  const resp = await fetch(deepSeekEndpoint(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${envValue("DEEPSEEK_API_KEY")}`,
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
    model: envValue("MISTRAL_MODEL") ?? "mistral-small-latest",
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
  };
  const resp = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${envValue("MISTRAL_API_KEY")}`,
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
    model: envValue("MISTRAL_MODEL") ?? "mistral-small-latest",
    max_tokens: opts.maxTokens ?? 1500,
    messages: providerMessages(opts),
    stream: true,
  };
  const resp = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${envValue("MISTRAL_API_KEY")}`,
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

function copilotPrompt(opts: JarvisCallOptions): string {
  return [
    JARVIS_PROMPTS[opts.flow],
    "Return the answer only. Do not edit files, run tools, or mutate the repository.",
    isVisionFlow(opts.flow)
      ? "For image flows, reason from any COPILOT_IMAGE_EVIDENCE_JSON text in the messages. If there is only an omitted image placeholder and no evidence packet, return conservative unknown/caution JSON."
      : "",
    ...opts.messages.map((message) => `${message.role.toUpperCase()}:\n${flattenContent(message.content)}`),
  ].filter(Boolean).join("\n\n");
}

function cleanCopilotOutput(stdout: string, stderr: string): string {
  const text = [stdout, stderr].filter(Boolean).join("\n").trim();
  const kept: string[] = [];
  let skipUsage = false;
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    const stripped = line.trim();
    if (!stripped) {
      if (kept.length && !skipUsage) kept.push("");
      continue;
    }
    if (stripped.startsWith("Total usage est:")) {
      skipUsage = true;
      continue;
    }
    if (stripped.startsWith("Total duration") || stripped.startsWith("Total code changes:")) continue;
    if (stripped.startsWith("Usage by model:")) {
      skipUsage = true;
      continue;
    }
    if (skipUsage && /^(gpt-|claude-)/.test(stripped)) continue;
    kept.push(stripped.startsWith("● ") ? stripped.slice(2).trim() : line);
  }
  return kept.join("\n").trim();
}

async function callCopilot(opts: JarvisCallOptions): Promise<JarvisResult> {
  const model = opts.model ?? DEFAULT_COPILOT_MODEL;
  const command = copilotCommandBase();
  const [bin, ...baseArgs] = command;
  const timeoutSeconds = Number.parseFloat(envValue("COPILOT_TIMEOUT_SECONDS") ?? "90");
  const { stdout, stderr } = await execFileAsync(
    bin,
    [
      ...baseArgs,
      "--prompt",
      copilotPrompt(opts),
      "--model",
      model,
      "--stream",
      "off",
      "--no-custom-instructions",
      "--disable-builtin-mcps",
      "--log-level",
      "error",
    ],
    {
      encoding: "utf8",
      timeout: Number.isFinite(timeoutSeconds) ? timeoutSeconds * 1000 : 90000,
      maxBuffer: 1024 * 1024,
    },
  ) as { stdout: string; stderr: string };
  return {
    text: cleanCopilotOutput(stdout, stderr),
    model: `copilot/${model}`,
    inputTokens: 0,
    outputTokens: 0,
    stopReason: "end_turn",
  };
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
    chat: `> _Running in demo mode (configure local Copilot CLI/OAuth, \`ANTHROPIC_API_KEY\`, \`DEEPSEEK_API_KEY\`, or \`MISTRAL_API_KEY\` to get real answers)_\n\nYou asked: **${userText.slice(0, 200) || "(no prompt)"}**.\n\nIn production I'd explain this board to you in plain English, flag anything dangerous, and point out what's worth reusing.`,
    identify: JSON.stringify({
      safety_level: "safe",
      explanation: "Demo mode: this is a placeholder identification. Configure local Copilot CLI/OAuth plus the image evidence bridge, or a direct vision provider, to enable real image analysis.",
      components: [
        { id: "C1", label: "Demo MCU", kind: "mcu", description: "Placeholder microcontroller block.", safety: "safe", bbox: { x: 0.1, y: 0.1, w: 0.3, h: 0.2 } },
        { id: "C2", label: "Demo power section", kind: "power", description: "Placeholder power regulator.", safety: "safe", bbox: { x: 0.55, y: 0.1, w: 0.3, h: 0.2 } },
      ],
    }),
    salvage: JSON.stringify({
      safety_level: "caution",
      explanation: "Demo mode salvage plan. Configure local Copilot CLI/OAuth plus the image evidence bridge, or a direct vision provider, to enable real board-photo salvage.",
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
  if (isVisionFlow(opts.flow)) {
    const visionProvider = chooseVisionProvider(opts.flow);
    if (visionProvider === "qwen") return callQwenVision(opts);
    if (visionProvider === "copilot") return callCopilot(opts);
    if (!hasAnthropicKey()) {
      return echoFallback(opts.flow, opts.messages);
    }
  }

  const textProvider = chooseTextProvider(opts.flow);
  if (textProvider === "copilot") return callCopilot(opts);
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
      "x-api-key": envValue("ANTHROPIC_API_KEY")!,
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
  if (textProvider === "copilot") {
    const result = await callCopilot(opts);
    for (const chunk of result.text.match(/[\s\S]{1,80}/g) ?? [result.text]) {
      yield chunk;
    }
    return;
  }
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
      "x-api-key": envValue("ANTHROPIC_API_KEY")!,
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
function escapeJsonStringControlChars(text: string): string {
  let out = "";
  let inString = false;
  let escaped = false;
  for (const ch of text) {
    if (escaped) {
      out += ch;
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      out += ch;
      escaped = true;
      continue;
    }
    if (ch === "\"") {
      out += ch;
      inString = !inString;
      continue;
    }
    if (inString) {
      if (ch === "\n") {
        out += "\\n";
        continue;
      }
      if (ch === "\r") continue;
      if (ch === "\t") {
        out += "\\t";
        continue;
      }
      if (ch.charCodeAt(0) < 0x20) {
        out += " ";
        continue;
      }
    }
    out += ch;
  }
  return out;
}

function parseJsonLenient<T>(text: string): T | null {
  try {
    return JSON.parse(text) as T;
  } catch {
    try {
      return JSON.parse(escapeJsonStringControlChars(text)) as T;
    } catch {
      return null;
    }
  }
}

export function extractJson<T = unknown>(raw: string): T | null {
  const trimmed = raw.trim();
  // Strip markdown code fences if model ignored the "no fences" instruction.
  const cleaned = trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  const direct = parseJsonLenient<T>(cleaned);
  if (direct) return direct;

  // Try to find a top-level JSON object.
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) return null;
  return parseJsonLenient<T>(cleaned.slice(start, end + 1));
}
