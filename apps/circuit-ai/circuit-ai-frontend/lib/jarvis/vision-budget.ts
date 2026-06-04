import fs from "node:fs";
import path from "node:path";

const LEDGER_SCHEMA_VERSION = "vision_spend_ledger.v1";

interface VisionSpendEntry {
  ts: string;
  provider: string;
  model: string;
  flow: string;
  cacheKey?: string;
  inputTokens: number;
  outputTokens: number;
  estimatedUsd: number;
}

interface VisionSpendLedger {
  schema_version: typeof LEDGER_SCHEMA_VERSION;
  entries: VisionSpendEntry[];
}

export interface VisionBudgetPolicy {
  enabled: boolean;
  monthlyUsdLimit: number;
  dailyUsdLimit: number;
  maxUsdPerCall: number;
  requireCache: boolean;
  maxCropsPerScan: number;
  escalateOnlyOnUncertain: boolean;
  ledgerPath: string;
}

export interface VisionBudgetSnapshot {
  policy: VisionBudgetPolicy;
  dailySpentUsd: number;
  monthlySpentUsd: number;
  remainingDailyUsd: number;
  remainingMonthlyUsd: number;
  entriesThisMonth: number;
}

type JsonRecord = Record<string, unknown>;

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
      // Ignore unreadable local env files.
    }
  }
  parentEnvCache = {};
  return parentEnvCache;
}

function envValue(name: string): string | undefined {
  return process.env[name] ?? parentEnv()[name];
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function numberEnv(name: string, fallback: number): number {
  const raw = envValue(name);
  if (!raw?.trim()) return fallback;
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function booleanEnv(name: string, fallback: boolean): boolean {
  const raw = envValue(name)?.trim().toLowerCase();
  if (!raw) return fallback;
  if (["1", "true", "yes", "on"].includes(raw)) return true;
  if (["0", "false", "no", "off"].includes(raw)) return false;
  return fallback;
}

function ledgerPath(): string {
  const configured = envValue("VISION_SPEND_LEDGER");
  if (configured?.trim()) return configured;

  const cwd = process.cwd();
  const appRoot = path.basename(cwd) === "circuit-ai-frontend" ? path.resolve(cwd, "..") : cwd;
  return path.join(appRoot, "data", "cache", "jarvis", "vision-spend-ledger.json");
}

export function getVisionBudgetPolicy(): VisionBudgetPolicy {
  const monthlyUsdLimit = numberEnv("VISION_MONTHLY_USD_LIMIT", 0);
  const dailyUsdLimit = numberEnv("VISION_DAILY_USD_LIMIT", monthlyUsdLimit > 0 ? monthlyUsdLimit : 0);
  return {
    enabled: monthlyUsdLimit > 0,
    monthlyUsdLimit,
    dailyUsdLimit,
    maxUsdPerCall: numberEnv("VISION_MAX_USD_PER_CALL", 0.05),
    requireCache: booleanEnv("VISION_REQUIRE_CACHE", true),
    maxCropsPerScan: Math.max(1, Math.floor(numberEnv("VISION_MAX_CROPS_PER_SCAN", 3))),
    escalateOnlyOnUncertain: booleanEnv("VISION_ESCALATE_ONLY_ON_UNCERTAIN", true),
    ledgerPath: ledgerPath(),
  };
}

function readLedger(): VisionSpendLedger {
  const file = ledgerPath();
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as unknown;
    const record = asRecord(parsed);
    const entries = Array.isArray(record.entries) ? record.entries : [];
    return {
      schema_version: LEDGER_SCHEMA_VERSION,
      entries: entries
        .map((entry) => asRecord(entry))
        .map((entry) => ({
          ts: typeof entry.ts === "string" ? entry.ts : new Date(0).toISOString(),
          provider: typeof entry.provider === "string" ? entry.provider : "unknown",
          model: typeof entry.model === "string" ? entry.model : "unknown",
          flow: typeof entry.flow === "string" ? entry.flow : "unknown",
          cacheKey: typeof entry.cacheKey === "string" ? entry.cacheKey : undefined,
          inputTokens: typeof entry.inputTokens === "number" ? entry.inputTokens : 0,
          outputTokens: typeof entry.outputTokens === "number" ? entry.outputTokens : 0,
          estimatedUsd: typeof entry.estimatedUsd === "number" ? entry.estimatedUsd : 0,
        })),
    };
  } catch {
    return { schema_version: LEDGER_SCHEMA_VERSION, entries: [] };
  }
}

function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function startOfLocalMonth(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), 1).getTime();
}

export function getVisionBudgetSnapshotSync(): VisionBudgetSnapshot {
  const policy = getVisionBudgetPolicy();
  const ledger = readLedger();
  const now = new Date();
  const dayStart = startOfLocalDay(now);
  const monthStart = startOfLocalMonth(now);
  const entriesThisMonth = ledger.entries.filter((entry) => Date.parse(entry.ts) >= monthStart);
  const dailySpentUsd = entriesThisMonth
    .filter((entry) => Date.parse(entry.ts) >= dayStart)
    .reduce((total, entry) => total + entry.estimatedUsd, 0);
  const monthlySpentUsd = entriesThisMonth.reduce((total, entry) => total + entry.estimatedUsd, 0);
  return {
    policy,
    dailySpentUsd,
    monthlySpentUsd,
    remainingDailyUsd: Math.max(0, policy.dailyUsdLimit - dailySpentUsd),
    remainingMonthlyUsd: Math.max(0, policy.monthlyUsdLimit - monthlySpentUsd),
    entriesThisMonth: entriesThisMonth.length,
  };
}

export function assertVisionBudgetAllowsCall(opts: {
  provider: string;
  model: string;
  flow: string;
  cacheKey?: string;
  estimatedUsd?: number;
}): void {
  const snapshot = getVisionBudgetSnapshotSync();
  const { policy } = snapshot;
  if (!policy.enabled) {
    throw new Error("Paid vision is disabled. Set VISION_MONTHLY_USD_LIMIT to a positive dollar amount before selecting a paid vision provider.");
  }
  if (policy.requireCache && !opts.cacheKey) {
    throw new Error("Paid vision requires a cache key. Set VISION_REQUIRE_CACHE=false only for manual one-off testing.");
  }
  const estimatedUsd = opts.estimatedUsd ?? policy.maxUsdPerCall;
  if (estimatedUsd > policy.maxUsdPerCall) {
    throw new Error(`Paid vision preflight estimate $${estimatedUsd.toFixed(4)} exceeds VISION_MAX_USD_PER_CALL=$${policy.maxUsdPerCall.toFixed(4)}.`);
  }
  if (estimatedUsd > snapshot.remainingDailyUsd) {
    throw new Error(`Paid vision daily budget exhausted for ${opts.provider}/${opts.model}. Remaining daily budget is $${snapshot.remainingDailyUsd.toFixed(4)}.`);
  }
  if (estimatedUsd > snapshot.remainingMonthlyUsd) {
    throw new Error(`Paid vision monthly budget exhausted for ${opts.provider}/${opts.model}. Remaining monthly budget is $${snapshot.remainingMonthlyUsd.toFixed(4)}.`);
  }
}

function qwenRates(model: string, inputTokens: number): { inputUsdPerM: number; outputUsdPerM: number } {
  const normalized = model.toLowerCase();
  const highTier = inputTokens > 128000;
  const midTier = inputTokens > 32000;

  if (normalized.includes("qwen3-vl-plus")) {
    if (highTier) return { inputUsdPerM: 0.43, outputUsdPerM: 4.301 };
    if (midTier) return { inputUsdPerM: 0.215, outputUsdPerM: 2.15 };
    return { inputUsdPerM: 0.143, outputUsdPerM: 1.434 };
  }

  if (normalized.includes("qwen3-vl-flash-us")) {
    if (highTier) return { inputUsdPerM: 0.12, outputUsdPerM: 0.96 };
    if (midTier) return { inputUsdPerM: 0.075, outputUsdPerM: 0.6 };
    return { inputUsdPerM: 0.05, outputUsdPerM: 0.4 };
  }

  if (normalized.includes("qwen3-vl-flash")) {
    if (highTier) return { inputUsdPerM: 0.086, outputUsdPerM: 0.859 };
    if (midTier) return { inputUsdPerM: 0.043, outputUsdPerM: 0.43 };
    return { inputUsdPerM: 0.022, outputUsdPerM: 0.215 };
  }

  return {
    inputUsdPerM: numberEnv("QWEN_INPUT_USD_PER_M", 0.05),
    outputUsdPerM: numberEnv("QWEN_OUTPUT_USD_PER_M", 0.4),
  };
}

export function estimateQwenCostUsd(model: string, inputTokens: number, outputTokens: number): number {
  const rates = qwenRates(model, inputTokens);
  const cost = (inputTokens / 1_000_000) * rates.inputUsdPerM + (outputTokens / 1_000_000) * rates.outputUsdPerM;
  return Number(cost.toFixed(6));
}

export async function recordVisionUsage(opts: {
  provider: string;
  model: string;
  flow: string;
  cacheKey?: string;
  inputTokens: number;
  outputTokens: number;
  estimatedUsd: number;
}): Promise<void> {
  const file = ledgerPath();
  const ledger = readLedger();
  const entry: VisionSpendEntry = {
    ts: new Date().toISOString(),
    provider: opts.provider,
    model: opts.model,
    flow: opts.flow,
    cacheKey: opts.cacheKey,
    inputTokens: opts.inputTokens,
    outputTokens: opts.outputTokens,
    estimatedUsd: opts.estimatedUsd,
  };
  const next: VisionSpendLedger = {
    schema_version: LEDGER_SCHEMA_VERSION,
    entries: [...ledger.entries, entry].slice(-1000),
  };
  await fs.promises.mkdir(path.dirname(file), { recursive: true });
  await fs.promises.writeFile(file, JSON.stringify(next, null, 2), "utf8");
}
