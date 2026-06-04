// Salvage planner. Accepts multipart image + optional description, returns
// a list of reusable modules with extraction recipes.

import { callJarvis, extractJson, type JarvisMessage, type JarvisContent } from "@/lib/jarvis/client";
import { buildCopilotImageEvidence, type CopilotImageEvidence } from "@/lib/jarvis/copilot-vision-bridge";
import {
  buildBoardEvidenceFromModelResult,
  evaluateBoardEvidenceTrust,
  scrubUnsupportedExactPartClaims,
  type BoardEvidence,
  type BoardEvidenceTrust,
} from "@/lib/jarvis/board-evidence";
import { cacheGet, cacheSet, hashBuffer, hashString } from "@/lib/cache/component-cache";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

export const runtime = "nodejs";
export const maxDuration = 60;

interface SalvageResult {
  safety_level: SafetyLevel;
  explanation: string;
  modules: SalvageModule[];
  fromCache?: boolean;
  model?: string;
  source?: "jarvis" | "copilot_evidence_bridge" | "qwen_native_vision";
  cost_usd_estimate?: number;
  board_evidence?: BoardEvidence;
  evidence_trust?: BoardEvidenceTrust;
  evidence?: {
    metadata: Record<string, unknown>;
    backend: Record<string, unknown>;
    board_evidence?: BoardEvidence;
    raw_multimodal_pixels_sent_to_copilot_cli: false;
  };
}

function isReusableBridgeCache(value: SalvageResult): boolean {
  return value.source !== "copilot_evidence_bridge" || value.evidence?.backend?.ok === true;
}

function withEvidenceTrust(value: SalvageResult): SalvageResult {
  const boardEvidence = value.board_evidence ?? value.evidence?.board_evidence;
  if (!boardEvidence) return value;
  return {
    ...value,
    board_evidence: value.board_evidence ?? boardEvidence,
    evidence_trust: evaluateBoardEvidenceTrust(boardEvidence),
  };
}

function providerCacheSegment(): string {
  return (process.env.JARVIS_VISION_PROVIDER || "auto")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .slice(0, 32);
}

function sourceForModel(model: string): SalvageResult["source"] {
  if (model.startsWith("copilot/")) return "copilot_evidence_bridge";
  if (model.startsWith("qwen/")) return "qwen_native_vision";
  return "jarvis";
}

function salvageKind(kind: string | undefined, label: string): SalvageModule["kind"] {
  const raw = `${kind ?? ""} ${label}`.toLowerCase();
  if (raw.includes("connector") || raw.includes("port") || raw.includes("usb") || raw.includes("hdmi") || raw.includes("ethernet") || raw.includes("header")) return "connector";
  if (raw.includes("power") || raw.includes("regulator") || raw.includes("pmic") || raw.includes("battery")) return "power";
  if (raw.includes("radio") || raw.includes("wifi") || raw.includes("bluetooth") || raw.includes("antenna")) return "radio";
  if (raw.includes("sensor")) return "sensor";
  if (raw.includes("driver")) return "driver";
  if (raw.includes("resistor") || raw.includes("capacitor") || raw.includes("passive") || raw.includes("crystal")) return "passive";
  if (raw.includes("mcu") || raw.includes("cpu") || raw.includes("soc") || raw.includes("chip") || raw.includes("ic") || raw.includes("memory") || raw.includes("ram")) return "mcu";
  return "unknown";
}

export async function POST(req: Request) {
  const ct = req.headers.get("content-type") ?? "";

  let imageBuf: Buffer | null = null;
  let mediaType = "image/jpeg";
  let description = "";

  if (ct.startsWith("multipart/form-data")) {
    const fd = await req.formData();
    const file = fd.get("image");
    if (file instanceof Blob) {
      imageBuf = Buffer.from(await file.arrayBuffer());
      mediaType = file.type || "image/jpeg";
    }
    description = (fd.get("description") as string) ?? "";
  } else if (ct.includes("application/json")) {
    const json = await req.json() as { imageBase64?: string; mediaType?: string; description?: string };
    if (json.imageBase64) {
      imageBuf = Buffer.from(json.imageBase64.replace(/^data:[^,]+,/, ""), "base64");
      mediaType = json.mediaType ?? "image/jpeg";
    }
    description = json.description ?? "";
  }

  if (!imageBuf && !description) {
    return Response.json({ error: "Need either image or description" }, { status: 400 });
  }

  const authState = req.headers.get("authorization") || process.env.CIRCUIT_AI_API_KEY ? "auth" : "noauth";
  const providerSegment = providerCacheSegment();
  const qwenNativeVision = providerSegment === "qwen";
  const key = imageBuf
    ? `${hashBuffer(imageBuf)}_${hashString(description).slice(0, 8)}_vision_${providerSegment}_${authState}_v10`
    : hashString(description);
  const cached = await cacheGet<SalvageResult>("salvage", key);
  if (cached && isReusableBridgeCache(cached.value)) {
    return Response.json(withEvidenceTrust({ ...cached.value, fromCache: true, model: cached.model }));
  }

  const content: JarvisContent[] = [];
  let evidence: CopilotImageEvidence | null = null;
  if (imageBuf) {
    evidence = await buildCopilotImageEvidence({
      buf: imageBuf,
      mediaType,
      request: req,
      filename: "jarvis-salvage-upload",
      description,
      includeBoardEvidenceInPrompt: !qwenNativeVision,
    });
    content.push({ type: "image", source: { type: "base64", media_type: mediaType, data: imageBuf.toString("base64") } });
    content.push({
      type: "text",
      text: [
        evidence.promptText,
        qwenNativeVision
          ? [
              "You have the raw image pixels. Use the evidence packet only as local analyzer context. Do not copy its board_evidence object; create fresh board_evidence from what you can see in the image.",
              "Return exactly one compact JSON object. Use safety_level exactly safe, caution, or hazard.",
              "Use at most 6 visible modules/components. Keep descriptions and extraction instructions under 12 words each. Use bbox as {x,y,w,h}, never bbox_2d or box.",
              "Do not use product knowledge to name exact ICs unless their markings are legible in the image.",
            ].join(" ")
          : "",
        "Plan salvage from the image-derived evidence packet above.",
        "Only mark modules reusable when the evidence supports an independent low-voltage function.",
      ].join("\n\n"),
    });
  }
  content.push({
    type: "text",
    text: `Plan the salvage for this device. ${description ? `User notes: ${description}` : ""} Output the JSON described in the system prompt.`,
  });

  const messages: JarvisMessage[] = [{ role: "user", content }];

  try {
    const result = await callJarvis({
      flow: "salvage",
      messages,
      maxTokens: qwenNativeVision ? 3000 : 3000,
      budget: imageBuf ? { cacheKey: key } : undefined,
    });
    const parsed = extractJson<SalvageResult>(result.text);
    if (!parsed) {
      return Response.json({ error: "Model output was not valid JSON", raw: result.text.slice(0, 500) }, { status: 502 });
    }
    const source = sourceForModel(result.model);
    const boardEvidence = buildBoardEvidenceFromModelResult({
      result: parsed,
      provider: source === "qwen_native_vision" ? "qwen" : source === "copilot_evidence_bridge" ? "copilot" : "jarvis",
      mode: source === "qwen_native_vision" ? "native_vision" : source === "copilot_evidence_bridge" ? "evidence_bridge" : "native_vision",
      model: result.model,
      rawPixelsSent: Boolean(imageBuf) && source !== "copilot_evidence_bridge",
      image: evidence?.metadata,
      cacheKey: imageBuf ? key : undefined,
      costUsdEstimate: result.estimatedCostUsd,
    });
    const explanationScrub = scrubUnsupportedExactPartClaims(parsed.explanation, boardEvidence);
    const normalizedModules = boardEvidence.salvage_candidates
      .filter((candidate) => candidate.label !== "unknown salvage candidate" || candidate.bbox || candidate.rationale)
      .slice(0, 6)
      .map((candidate) => ({
        id: candidate.id,
        label: candidate.label,
        kind: salvageKind(candidate.kind, candidate.label),
        description: candidate.rationale ?? "Visible reusable candidate identified by native vision.",
        safety: parsed.safety_level,
        bbox: candidate.bbox,
        extraction: candidate.required_checks?.join(" "),
        warnings: candidate.risks ?? [],
      }));
    const evidenceTrust = evaluateBoardEvidenceTrust(boardEvidence);
    const responsePayload: SalvageResult = {
      ...parsed,
      explanation: explanationScrub.text ?? parsed.explanation,
      modules: normalizedModules.length ? normalizedModules : parsed.modules,
      board_evidence: boardEvidence,
      evidence_trust: evidenceTrust,
      fromCache: false,
      model: result.model,
      source,
      cost_usd_estimate: result.estimatedCostUsd,
      evidence: evidence ? {
        metadata: evidence.metadata,
        backend: evidence.backend,
        board_evidence: evidence.boardEvidence,
        raw_multimodal_pixels_sent_to_copilot_cli: false,
      } : undefined,
    };
    if (responsePayload.source !== "copilot_evidence_bridge" || evidence?.backend.ok !== false) {
      await cacheSet("salvage", key, responsePayload, result.model);
    }
    return Response.json(responsePayload);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
