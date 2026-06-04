import crypto from "node:crypto";

import { buildBoardEvidenceFromLocalAnalyzer, type BoardEvidence } from "./board-evidence";

const DEFAULT_VISION_BASE_URL = "http://127.0.0.1:8000";

type JsonRecord = Record<string, unknown>;

export interface CopilotImageEvidence {
  promptText: string;
  metadata: {
    mediaType: string;
    sizeBytes: number;
    sha256: string;
    width?: number;
    height?: number;
  };
  backend: {
    attempted: boolean;
    ok: boolean;
    target?: string;
    error?: string;
  };
  boardEvidence: BoardEvidence;
}

interface BuildEvidenceOptions {
  buf: Buffer;
  mediaType: string;
  request?: Request;
  filename?: string;
  description?: string;
  includeBoardEvidenceInPrompt?: boolean;
}

function getVisionApiBaseUrl() {
  return (
    process.env.CIRCUIT_AI_VISION_URL ||
    process.env.NEXT_PUBLIC_VISION_API_URL ||
    DEFAULT_VISION_BASE_URL
  );
}

function getProxyAuthHeaders(request?: Request): HeadersInit {
  const forwardedAuthorization = request?.headers.get("authorization");
  if (forwardedAuthorization) return { Authorization: forwardedAuthorization };
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";
  return apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function imageSize(buf: Buffer): { width?: number; height?: number; format?: string } {
  if (buf.length >= 24 && buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
    return { format: "png", width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
  }
  if (buf.length >= 10 && buf.subarray(0, 3).toString("ascii") === "GIF") {
    return { format: "gif", width: buf.readUInt16LE(6), height: buf.readUInt16LE(8) };
  }
  if (buf.length >= 12 && buf.subarray(0, 4).toString("ascii") === "RIFF" && buf.subarray(8, 12).toString("ascii") === "WEBP") {
    return { format: "webp" };
  }
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < buf.length) {
      if (buf[offset] !== 0xff) break;
      const marker = buf[offset + 1];
      const length = buf.readUInt16BE(offset + 2);
      if (length < 2) break;
      if ((marker >= 0xc0 && marker <= 0xc3) || (marker >= 0xc5 && marker <= 0xc7) || (marker >= 0xc9 && marker <= 0xcb) || (marker >= 0xcd && marker <= 0xcf)) {
        return { format: "jpeg", height: buf.readUInt16BE(offset + 5), width: buf.readUInt16BE(offset + 7) };
      }
      offset += 2 + length;
    }
    return { format: "jpeg" };
  }
  return {};
}

function normalizeBbox(raw: unknown, width?: number, height?: number) {
  const bbox = Array.isArray(raw) ? raw.map(numberValue) : [];
  if (bbox.length !== 4 || bbox.some((value) => value === undefined)) return undefined;
  const [x1, y1, x2, y2] = bbox as number[];
  if (width && height && Math.max(x1, y1, x2, y2) > 1) {
    return {
      x: Number((x1 / width).toFixed(4)),
      y: Number((y1 / height).toFixed(4)),
      w: Number(((x2 - x1) / width).toFixed(4)),
      h: Number(((y2 - y1) / height).toFixed(4)),
    };
  }
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

function summarizeAnalysis(payload: unknown, width?: number, height?: number) {
  const root = asRecord(payload);
  const results = asRecord(root.results ?? root);
  const summary = asRecord(root.summary);
  const metadata = asRecord(root.metadata);
  const detectionSummary = asRecord(results.detection_summary ?? metadata.detection_summary);
  const analysisMetadata = asRecord(results.analysis_metadata);
  const certainty = asRecord(results.certainty_ledger);
  const visualTopology = asRecord(results.visual_topology);
  const detections = asArray(results.detections).slice(0, 50).map((entry, index) => {
    const det = asRecord(entry);
    return {
      id: det.id ?? `D${index + 1}`,
      class_name: stringValue(det.class_name) ?? stringValue(det.label) ?? "unknown",
      confidence: numberValue(det.confidence),
      method: stringValue(det.method),
      bbox: normalizeBbox(det.bbox, width, height),
      text: stringValue(det.text_content) ?? stringValue(det.ocr_text) ?? stringValue(det.part_number),
      quality_score: numberValue(det.quality_score),
    };
  });
  const markings = detections
    .map((det) => det.text)
    .filter((text, index, all): text is string => Boolean(text) && all.indexOf(text) === index)
    .slice(0, 30);

  return {
    summary_text: stringValue(summary.summary_text),
    backend: stringValue(metadata.backend) ?? stringValue(analysisMetadata.backend),
    detection_quality: stringValue(metadata.detection_quality) ?? stringValue(detectionSummary.detection_quality),
    total_components: numberValue(detectionSummary.total_components) ?? detections.length,
    components_by_type: asRecord(detectionSummary.components_by_type),
    review_required: Boolean(detectionSummary.review_required ?? analysisMetadata.review_required),
    visual_topology: {
      trace_count: numberValue(visualTopology.trace_count),
      connection_count: numberValue(visualTopology.connection_count),
      confidence: numberValue(visualTopology.confidence),
      uncertainty: stringValue(visualTopology.uncertainty),
    },
    certainty: {
      overall: asRecord(certainty.overall),
      missing_evidence: asArray(certainty.missing_evidence).slice(0, 20),
      next_actions: asArray(certainty.next_actions).slice(0, 20),
    },
    detections,
    markings,
  };
}

async function callLocalAnalyzer(opts: BuildEvidenceOptions, width?: number, height?: number) {
  const target = `${getVisionApiBaseUrl().replace(/\/+$/, "")}/analyze`;
  const outbound = new FormData();
  outbound.set(
    "file",
    new Blob([new Uint8Array(opts.buf)], { type: opts.mediaType }),
    opts.filename || "copilot-vision-upload",
  );
  outbound.set("backend", "hybrid");
  outbound.set("enable_ocr", "true");

  const response = await fetch(target, {
    method: "POST",
    headers: getProxyAuthHeaders(opts.request),
    body: outbound,
  });
  const text = await response.text();
  if (!response.ok) {
    let error = text;
    try {
      const parsed = JSON.parse(text) as { detail?: string; error?: string; message?: string };
      error = parsed.error || parsed.detail || parsed.message || text;
    } catch {
      // Keep raw text below.
    }
    return { target, ok: false, error: error.slice(0, 500), analysis: null };
  }
  try {
    return { target, ok: true, error: undefined, analysis: summarizeAnalysis(JSON.parse(text), width, height) };
  } catch (error) {
    return { target, ok: false, error: `Could not parse local analyzer JSON: ${error instanceof Error ? error.message : String(error)}`, analysis: null };
  }
}

export async function buildCopilotImageEvidence(opts: BuildEvidenceOptions): Promise<CopilotImageEvidence> {
  const size = imageSize(opts.buf);
  const sha256 = crypto.createHash("sha256").update(opts.buf).digest("hex");
  const metadata = {
    mediaType: opts.mediaType,
    sizeBytes: opts.buf.length,
    sha256,
    width: size.width,
    height: size.height,
  };

  let backend: CopilotImageEvidence["backend"] = { attempted: true, ok: false };
  let analysis: unknown = null;
  try {
    const result = await callLocalAnalyzer(opts, size.width, size.height);
    backend = {
      attempted: true,
      ok: result.ok,
      target: result.target,
      error: result.error,
    };
    analysis = result.analysis;
  } catch (error) {
    backend = {
      attempted: true,
      ok: false,
      target: `${getVisionApiBaseUrl().replace(/\/+$/, "")}/analyze`,
      error: error instanceof Error ? error.message : String(error),
    };
  }

  const boardEvidence = buildBoardEvidenceFromLocalAnalyzer({
    analysis,
    image: {
      ...metadata,
      description: opts.description || undefined,
    },
    backendOk: backend.ok,
  });

  const boardEvidenceForPrompt = opts.includeBoardEvidenceInPrompt === false
    ? {
        schema_version: boardEvidence.schema_version,
        omitted: true,
        reason: "Native vision provider receives the raw image. This local analyzer summary is context only, not an output template.",
        component_count: boardEvidence.components.length,
        marking_count: boardEvidence.markings.length,
        connector_count: boardEvidence.connectors.length,
        uncertainty: boardEvidence.uncertainty,
        recommended_checks: boardEvidence.recommended_checks,
      }
    : boardEvidence;

  const packet = {
    source: "copilot_image_evidence_bridge",
    raw_multimodal_pixels_sent_to_copilot_cli: false,
    bridge_policy: [
      "Use this as image-derived evidence from local CV/OCR plus image metadata.",
      "Do not invent part labels, pinouts, voltages, or safety status beyond evidence.",
      "When evidence is sparse or local analyzer failed, return unknown/caution and request better evidence.",
      "Bounding boxes, when present, are normalized 0-1 image coordinates.",
    ],
    image: {
      ...metadata,
      format: size.format,
      description: opts.description || undefined,
    },
    local_analyzer: {
      attempted: backend.attempted,
      ok: backend.ok,
      error: backend.error,
      analysis,
    },
    board_evidence: boardEvidenceForPrompt,
  };

  return {
    promptText: `COPILOT_IMAGE_EVIDENCE_JSON:\n${JSON.stringify(packet, null, 2)}`,
    metadata,
    backend,
    boardEvidence,
  };
}
