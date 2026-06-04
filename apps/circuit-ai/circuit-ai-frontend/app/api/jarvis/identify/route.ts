// Vision identification endpoint. Accepts multipart/form-data with a single
// "image" field OR JSON { imageBase64, mediaType }. Returns structured
// component list + safety level. Cached by perceptual hash.

import { callJarvis, extractJson, type JarvisMessage } from "@/lib/jarvis/client";
import { buildCopilotImageEvidence } from "@/lib/jarvis/copilot-vision-bridge";
import {
  buildBoardEvidenceFromModelResult,
  evaluateBoardEvidenceTrust,
  scrubUnsupportedExactPartClaims,
  type BoardEvidence,
  type BoardEvidenceTrust,
} from "@/lib/jarvis/board-evidence";
import { cacheGet, cacheSet, hashBuffer } from "@/lib/cache/component-cache";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

export const runtime = "nodejs";
export const maxDuration = 60;

interface IdentifyResult {
  safety_level: SafetyLevel;
  explanation: string;
  components: Array<Partial<SalvageModule> & { id: string; label: string; kind: string }>;
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

function isReusableBridgeCache(value: IdentifyResult): boolean {
  return value.source !== "copilot_evidence_bridge" || value.evidence?.backend?.ok === true;
}

function withEvidenceTrust(value: IdentifyResult): IdentifyResult {
  const boardEvidence = value.board_evidence ?? value.evidence?.board_evidence;
  if (!boardEvidence) return value;
  return {
    ...value,
    board_evidence: value.board_evidence ?? boardEvidence,
    evidence_trust: evaluateBoardEvidenceTrust(boardEvidence),
  };
}

async function readImage(req: Request): Promise<{ buf: Buffer; mediaType: string } | null> {
  const ct = req.headers.get("content-type") ?? "";

  if (ct.startsWith("multipart/form-data")) {
    const fd = await req.formData();
    const file = fd.get("image");
    if (!(file instanceof Blob)) return null;
    const buf = Buffer.from(await file.arrayBuffer());
    const mediaType = file.type || "image/jpeg";
    return { buf, mediaType };
  }

  if (ct.includes("application/json")) {
    const json = await req.json() as { imageBase64?: string; mediaType?: string };
    if (!json.imageBase64) return null;
    const cleaned = json.imageBase64.replace(/^data:[^,]+,/, "");
    return { buf: Buffer.from(cleaned, "base64"), mediaType: json.mediaType ?? "image/jpeg" };
  }

  return null;
}

function providerCacheSegment(): string {
  return (process.env.JARVIS_VISION_PROVIDER || "auto")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .slice(0, 32);
}

function sourceForModel(model: string): IdentifyResult["source"] {
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
  const img = await readImage(req);
  if (!img) {
    return Response.json({ error: "Missing image (multipart 'image' field or JSON imageBase64)" }, { status: 400 });
  }

  const authState = req.headers.get("authorization") || process.env.CIRCUIT_AI_API_KEY ? "auth" : "noauth";
  const providerSegment = providerCacheSegment();
  const qwenNativeVision = providerSegment === "qwen";
  const key = `${hashBuffer(img.buf)}_vision_${providerSegment}_${authState}_v9`;
  const cached = await cacheGet<IdentifyResult>("identify", key);
  if (cached && isReusableBridgeCache(cached.value)) {
    return Response.json(withEvidenceTrust({ ...cached.value, fromCache: true, model: cached.model }));
  }

  const evidence = await buildCopilotImageEvidence({
    buf: img.buf,
    mediaType: img.mediaType,
    request: req,
    filename: "jarvis-identify-upload",
    includeBoardEvidenceInPrompt: !qwenNativeVision,
  });

  const messages: JarvisMessage[] = [{
    role: "user",
    content: [
      { type: "image", source: { type: "base64", media_type: img.mediaType, data: img.buf.toString("base64") } },
      {
        type: "text",
        text: [
          evidence.promptText,
          qwenNativeVision
            ? [
                "You have the raw image pixels. Use the evidence packet only as local analyzer context. Do not copy its board_evidence object; create fresh board_evidence from what you can see in the image.",
                "Return exactly one compact JSON object. Use safety_level exactly safe, caution, or hazard.",
                "Use at most 8 visible components. Keep descriptions short. Use bbox as {x,y,w,h}, never bbox_2d or box.",
                "Do not use product knowledge to name exact ICs unless their markings are legible in the image.",
              ].join(" ")
            : "",
          "Identify every visible component or functional block on this board from the evidence packet.",
          "When the evidence does not identify a component confidently, label it unknown and set safety to caution.",
          "Output the JSON described in the system prompt.",
        ].join("\n\n"),
      },
    ],
  }];

  try {
    const result = await callJarvis({
      flow: "identify",
      messages,
      maxTokens: qwenNativeVision ? 1800 : 2500,
      budget: { cacheKey: key },
    });
    const parsed = extractJson<IdentifyResult>(result.text);
    if (!parsed) {
      return Response.json({
        error: "Model output was not valid JSON",
        raw: result.text.slice(0, 500),
        model: result.model,
      }, { status: 502 });
    }
    const source = sourceForModel(result.model);
    const boardEvidence = buildBoardEvidenceFromModelResult({
      result: parsed,
      provider: source === "qwen_native_vision" ? "qwen" : source === "copilot_evidence_bridge" ? "copilot" : "jarvis",
      mode: source === "qwen_native_vision" ? "native_vision" : source === "copilot_evidence_bridge" ? "evidence_bridge" : "native_vision",
      model: result.model,
      rawPixelsSent: source !== "copilot_evidence_bridge",
      image: evidence.metadata,
      cacheKey: key,
      costUsdEstimate: result.estimatedCostUsd,
    });
    const explanationScrub = scrubUnsupportedExactPartClaims(parsed.explanation, boardEvidence);
    const normalizedComponents = boardEvidence.components
      .slice(0, 8)
      .map((component) => ({
        id: component.id,
        label: component.label,
        kind: salvageKind(String(component.kind), component.label),
        description: component.role ?? component.evidence?.join("; ") ?? "Visible board feature identified by native vision.",
        safety: component.safety ?? parsed.safety_level,
        bbox: component.bbox,
        warnings: component.warnings ?? [],
      }));
    const evidenceTrust = evaluateBoardEvidenceTrust(boardEvidence);
    const responsePayload: IdentifyResult = {
      ...parsed,
      explanation: explanationScrub.text ?? parsed.explanation,
      components: normalizedComponents.length ? normalizedComponents : parsed.components,
      board_evidence: boardEvidence,
      evidence_trust: evidenceTrust,
      fromCache: false,
      model: result.model,
      source,
      cost_usd_estimate: result.estimatedCostUsd,
      evidence: {
        metadata: evidence.metadata,
        backend: evidence.backend,
        board_evidence: evidence.boardEvidence,
        raw_multimodal_pixels_sent_to_copilot_cli: false,
      },
    };
    if (responsePayload.source !== "copilot_evidence_bridge" || evidence.backend.ok) {
      await cacheSet("identify", key, responsePayload, result.model);
    }
    return Response.json(responsePayload);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
