import fs from "node:fs";
import path from "node:path";
import { evaluateBoardEvidenceTrust, type BoardEvidence, type BoardEvidenceTrust } from "@/lib/jarvis/board-evidence";
import {
  evaluateRepairAuthority,
  type RepairAuthority,
  type RepairMeasurementEvidence,
} from "@/lib/jarvis/repair-authority";

export const runtime = "nodejs";
export const maxDuration = 60;

type JsonRecord = Record<string, unknown>;
type VerifierSafetyLevel = "safe" | "caution" | "hazard";
type LaunchReadinessLevel = "experimental_mvp" | "private_alpha" | "needs_more_evidence" | "unsafe";

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

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string" && Boolean(entry.trim()))
    : [];
}

function uniqueStrings(values: string[]): string[] {
  return values.filter((entry, index, all) => all.indexOf(entry) === index);
}

function launchReadinessForAuthority(
  deterministicTrust: BoardEvidenceTrust,
  repairAuthority: RepairAuthority,
): LaunchReadinessLevel {
  if (repairAuthority.status === "blocked" || deterministicTrust.launch_readiness === "blocked") return "unsafe";
  if (repairAuthority.status === "authoritative_low_risk") return "private_alpha";
  if (
    repairAuthority.status === "measurement_backed"
    && ["private_alpha_candidate", "experimental_mvp"].includes(deterministicTrust.launch_readiness)
  ) {
    return "experimental_mvp";
  }
  return "needs_more_evidence";
}

function authorityBlockers(deterministicTrust: BoardEvidenceTrust, repairAuthority: RepairAuthority): string[] {
  const measurementCount = repairAuthority.measurement_summary?.count ?? 0;
  const gateBlockers = repairAuthority.gates
    .filter((gate) => gate.status !== "pass")
    .map((gate) => `${gate.label}: ${gate.reason}`);
  const trustBlockers = deterministicTrust.blockers.filter((blocker) => {
    if (!measurementCount) return true;
    return !/no electrical measurements|no bench measurements/i.test(blocker);
  });
  return uniqueStrings([
    ...repairAuthority.required_measurements,
    ...repairAuthority.blocked_decisions.map((decision) => `blocked decision: ${decision}`),
    ...trustBlockers,
    ...gateBlockers,
  ]).slice(0, 10);
}

function applyAuthorityGuard<T extends JsonRecord>(
  verification: T,
  deterministicTrust: BoardEvidenceTrust,
  repairAuthority: RepairAuthority,
): T & {
  safety_level: VerifierSafetyLevel;
  verifier_status: string;
  launch_readiness: { level: LaunchReadinessLevel; blockers: string[] };
} {
  const launchReadiness = asRecord(verification.launch_readiness);
  const existingBlockers = stringArray(launchReadiness.blockers);
  const guardedLevel = launchReadinessForAuthority(deterministicTrust, repairAuthority);
  const guardedStatus = repairAuthority.status === "blocked"
    ? "blocked"
    : repairAuthority.status === "visual_only" && verification.verifier_status === "pass_with_gates"
      ? "needs_review"
      : String(verification.verifier_status ?? "needs_review");
  const safetyLevel: VerifierSafetyLevel = repairAuthority.safety_level === "hazard"
    ? "hazard"
    : ["blocked", "visual_only", "needs_measurements"].includes(repairAuthority.status)
      ? "caution"
    : verification.safety_level === "safe" || verification.safety_level === "hazard"
      ? verification.safety_level
      : "caution";

  return {
    ...verification,
    safety_level: safetyLevel,
    verifier_status: guardedStatus,
    launch_readiness: {
      ...launchReadiness,
      level: guardedLevel,
      blockers: uniqueStrings([...existingBlockers, ...authorityBlockers(deterministicTrust, repairAuthority)]).slice(0, 10),
    },
  };
}

function endpoint(): string {
  const base = (envValue("DEEPSEEK_BASE_URL") ?? "https://api.deepseek.com").replace(/\/+$/, "");
  return base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
}

function extractJson(raw: string): JsonRecord | null {
  const cleaned = raw.trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  try {
    const parsed = JSON.parse(cleaned) as unknown;
    return asRecord(parsed);
  } catch {
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start < 0 || end <= start) return null;
    try {
      const parsed = JSON.parse(cleaned.slice(start, end + 1)) as unknown;
      return asRecord(parsed);
    } catch {
      return null;
    }
  }
}

function offlineVerification(boardEvidence: JsonRecord, deterministicTrust: BoardEvidenceTrust, repairAuthority: RepairAuthority) {
  const uncertainty = asRecord(boardEvidence.uncertainty);
  const missing = Array.isArray(uncertainty.missing_evidence) ? uncertainty.missing_evidence : [];
  const nextActions = Array.isArray(uncertainty.next_actions) ? uncertainty.next_actions : [];
  const components = Array.isArray(boardEvidence.components) ? boardEvidence.components : [];
  const salvage = Array.isArray(boardEvidence.salvage_candidates) ? boardEvidence.salvage_candidates : [];
  return applyAuthorityGuard({
    safety_level: repairAuthority.safety_level,
    verifier_status: "offline_gate",
    summary: "DeepSeek is not configured, so this is a deterministic evidence gate only.",
    contradictions: [],
    unsupported_claims: components.length || salvage.length ? [] : ["No localized components or salvage candidates were present in board_evidence."],
    missing_measurements: missing.slice(0, 8),
    recommended_next_actions: nextActions.length
      ? nextActions.slice(0, 8)
      : ["Capture a sharper board photo, then verify suspected rails/connectors with measurements before reuse."],
    launch_readiness: { level: launchReadinessForAuthority(deterministicTrust, repairAuthority), blockers: authorityBlockers(deterministicTrust, repairAuthority) },
    deterministic_trust: deterministicTrust,
    repair_authority: repairAuthority,
  }, deterministicTrust, repairAuthority);
}

function promptFor(
  boardEvidence: JsonRecord,
  scanSummary: unknown,
  deterministicTrust: BoardEvidenceTrust,
  measurements: RepairMeasurementEvidence[],
) {
  return [
    "Verify this Circuit-AI board evidence for salvage/repair/reuse planning.",
    "Return ONLY JSON with this schema:",
    JSON.stringify({
      safety_level: "safe|caution|hazard",
      verifier_status: "pass_with_gates|needs_review|blocked|safety_hold",
      summary: "short plain-English verification summary",
      contradictions: ["claims that conflict with evidence"],
      unsupported_claims: ["claims that need visual/electrical proof"],
      missing_measurements: ["continuity/voltage/resistance/photos needed"],
      recommended_next_actions: ["specific next checks"],
      launch_readiness: {
        level: "experimental_mvp|private_alpha|needs_more_evidence|unsafe",
        blockers: ["what stops user-facing confidence"],
      },
    }),
    "Rules:",
    "- Treat model vision claims as advisory unless visible evidence supports them.",
    "- Do not mark a section safe-to-cut or reuse-ready without isolation/power/continuity evidence.",
    "- Preserve useful product momentum: identify what can be shown in an experimental MVP and what still needs measurement.",
    "- Be strict about mains, lithium packs, high-current rails, bulk capacitors, RF, and unknown power inputs.",
    "Scan summary:",
    JSON.stringify(scanSummary ?? {}, null, 2),
    "Deterministic trust gate:",
    JSON.stringify(deterministicTrust, null, 2),
    "Recorded bench measurements:",
    JSON.stringify(measurements, null, 2),
    "Board evidence:",
    JSON.stringify(boardEvidence, null, 2),
  ].join("\n\n");
}

async function callDeepSeek(prompt: string) {
  const key = envValue("DEEPSEEK_API_KEY");
  if (!key) throw new Error("DEEPSEEK_API_KEY is not configured.");
  const model = envValue("DEEPSEEK_MODEL") ?? "deepseek-v4-flash";
  const body = {
    model,
    max_tokens: 1400,
    temperature: 0.1,
    response_format: { type: "json_object" },
    thinking: { type: envValue("DEEPSEEK_THINKING")?.toLowerCase() === "enabled" ? "enabled" : "disabled" },
    messages: [
      { role: "system", content: "You are Circuit-AI's strict evidence verifier. Return valid JSON only." },
      { role: "user", content: prompt },
    ],
  };
  const response = await fetch(endpoint(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${key}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`DeepSeek verifier ${response.status}: ${text.slice(0, 500)}`);
  }
  const json = await response.json() as {
    model?: string;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
    choices?: Array<{ message?: { content?: string; reasoning_content?: string }; finish_reason?: string }>;
  };
  const text = json.choices?.[0]?.message?.content ?? json.choices?.[0]?.message?.reasoning_content ?? "";
  const parsed = extractJson(text);
  if (!parsed) {
    throw new Error("DeepSeek verifier did not return valid JSON.");
  }
  return {
    ...parsed,
    model: `deepseek/${json.model ?? model}`,
    usage: {
      input_tokens: json.usage?.prompt_tokens ?? 0,
      output_tokens: json.usage?.completion_tokens ?? 0,
    },
  } as JsonRecord & {
    verifier_status?: string;
    safety_level?: VerifierSafetyLevel;
    model: string;
    usage: { input_tokens: number; output_tokens: number };
  };
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => null) as {
    board_evidence?: unknown;
    scan_summary?: unknown;
    measurements?: RepairMeasurementEvidence[];
  } | null;
  const boardEvidence = asRecord(body?.board_evidence);
  if (!Object.keys(boardEvidence).length) {
    return Response.json({ error: "Missing board_evidence object" }, { status: 400 });
  }
  const deterministicTrust = evaluateBoardEvidenceTrust(boardEvidence as unknown as BoardEvidence);
  const measurements = Array.isArray(body?.measurements) ? body.measurements : [];
  const repairAuthorityBase = evaluateRepairAuthority({
    boardEvidence: boardEvidence as unknown as BoardEvidence,
    evidenceTrust: deterministicTrust,
    measurements,
  });

  const url = new URL(req.url);
  const forceOffline = url.searchParams.get("offline") === "1" || req.headers.get("x-circuit-ai-offline-verifier") === "true";
  if (forceOffline || !envValue("DEEPSEEK_API_KEY")) {
    return Response.json({
      ...offlineVerification(boardEvidence, deterministicTrust, repairAuthorityBase),
      model: "deterministic/offline-evidence-gate",
      usage: { input_tokens: 0, output_tokens: 0 },
    });
  }

  try {
    const verification = await callDeepSeek(promptFor(boardEvidence, body?.scan_summary, deterministicTrust, measurements));
    const repairAuthority = evaluateRepairAuthority({
      boardEvidence: boardEvidence as unknown as BoardEvidence,
      evidenceTrust: deterministicTrust,
      measurements,
      verifierStatus: typeof verification.verifier_status === "string" ? verification.verifier_status : undefined,
      verifierSafety: verification.safety_level === "safe" || verification.safety_level === "caution" || verification.safety_level === "hazard"
        ? verification.safety_level
        : undefined,
    });
    return Response.json({
      ...applyAuthorityGuard(verification, deterministicTrust, repairAuthority),
      deterministic_trust: deterministicTrust,
      repair_authority: repairAuthority,
    });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 502 });
  }
}
