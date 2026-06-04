"use client";

import { Suspense, useCallback, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Camera, ClipboardList, Image as ImageIcon, Loader2, RefreshCw, Scissors, Search, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { SafetyBanner } from "@/components/safety-banner";
import { IdentificationOverlay } from "@/components/scan/identification-overlay";
import { ModuleDetail } from "@/components/scan/module-detail";
import { CameraCapture } from "@/components/scan/camera-capture";
import { usePageTitle } from "@/components/use-page-title";
import { useWorkbenchStore } from "@/lib/workbench-store";
import { addInventoryItem } from "@/lib/inventory/storage";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";
import type { BoardEvidence, BoardEvidenceTrust } from "@/lib/jarvis/board-evidence";
import type { RepairAuthority, RepairMeasurementEvidence } from "@/lib/jarvis/repair-authority";

interface IdentifyResponse {
  safety_level: SafetyLevel;
  explanation: string;
  components?: SalvageModule[];
  modules?: SalvageModule[];
  error?: string;
  fromCache?: boolean;
  model?: string;
  source?: "local" | "jarvis" | "copilot_evidence_bridge" | "qwen_native_vision";
  cost_usd_estimate?: number;
  board_evidence?: BoardEvidence;
  evidence_trust?: BoardEvidenceTrust;
  evidence?: {
    board_evidence?: BoardEvidence;
  };
  backend?: string;
  reviewRequired?: boolean;
  rawAnalysis?: Record<string, unknown>;
  visualTopology?: {
    traceCount: number;
    connectionCount: number;
    confidence: number;
    uncertainty?: string;
  };
  aoiInspection?: {
    readiness?: string;
    score?: number;
    learnedDetectionRatio?: number;
    defectCandidateCount?: number;
  };
  productionAoi?: {
    disposition?: string;
    releaseAuthorized?: boolean;
    certaintyScore?: number;
    certaintyLevel?: string;
    blockers?: string[];
    requiredEvidence?: string[];
    gates?: Array<{
      gate_id?: string;
      status?: string;
      score?: number;
      evidence?: string;
    }>;
  };
  certaintyLedger?: {
    overall?: {
      score?: number;
      level?: string;
      summary?: string;
    };
    counts?: Record<string, number>;
    missing_evidence?: string[];
    next_actions?: string[];
    training_queue?: {
      should_capture?: boolean;
      reasons?: string[];
      candidate_labels?: string[];
    };
  };
}

interface VerifyResponse {
  safety_level?: SafetyLevel;
  verifier_status?: string;
  summary?: string;
  contradictions?: string[];
  unsupported_claims?: string[];
  missing_measurements?: string[];
  recommended_next_actions?: string[];
  launch_readiness?: {
    level?: string;
    blockers?: string[];
  };
  model?: string;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
  };
  deterministic_trust?: BoardEvidenceTrust;
  repair_authority?: RepairAuthority;
  error?: string;
}

type LocalAnalyzeDetection = {
  bbox?: number[];
  class_name?: string;
  confidence?: number;
  part_number?: string | null;
  ocr_text?: string;
};

type LocalAnalyzeResponse = {
  ok?: boolean;
  error?: string;
  results?: {
    detections?: LocalAnalyzeDetection[];
    detection_summary?: {
      total_components?: number;
      components_by_type?: Record<string, number>;
      detection_quality?: string;
      review_required?: boolean;
    };
    analysis_metadata?: {
      backend?: string;
      review_required?: boolean;
      semantic_quality?: string;
      limitations?: string[];
    };
    visual_topology?: {
      trace_count?: number;
      connection_count?: number;
      confidence?: number;
      uncertainty?: string;
    };
    aoi_inspection?: {
      readiness?: string;
      score?: number;
      learned_detection_ratio?: number;
      defect_candidate_count?: number;
    };
    production_aoi?: {
      disposition?: string;
      release_authorized?: boolean;
      certainty_score?: number;
      certainty_level?: string;
      blockers?: string[];
      required_evidence?: string[];
      gates?: Array<{
        gate_id?: string;
        status?: string;
        score?: number;
        evidence?: string;
      }>;
    };
    defect_inspection?: {
      defect_count?: number;
    };
    certainty_ledger?: IdentifyResponse["certaintyLedger"] & {
      items?: Array<{
        claim?: string;
        certainty?: string;
        score?: number;
      }>;
    };
  };
  metadata?: {
    backend?: string;
    detection_quality?: string;
  };
  summary?: {
    summary_text?: string;
  };
};

type Mode = "identify" | "salvage";

type MeasurementDraft = {
  type: string;
  target: string;
  value: string;
  unit: string;
  notes: string;
};

type MeasurementQueueItem = {
  id: string;
  prompt: string;
  type: string;
  unit: string;
  source: string;
  recorded: boolean;
  matchedValue?: string;
};

function inferMeasurementType(prompt: string) {
  const normalized = prompt.toLowerCase();
  if (normalized.includes("resistance") || normalized.includes("no-short") || normalized.includes("short")) return "resistance";
  if (normalized.includes("continuity") || normalized.includes("ground")) return "continuity";
  if (normalized.includes("thermal") || normalized.includes("temperature") || normalized.includes("heat")) return "thermal";
  if (normalized.includes("current") || normalized.includes("load")) return "current";
  if (normalized.includes("logic") || normalized.includes("uart") || normalized.includes("i2c") || normalized.includes("spi")) return "logic_level";
  if (normalized.includes("voltage") || normalized.includes("rail") || normalized.includes("vbus") || normalized.includes("+3v3") || normalized.includes("5v")) return "voltage";
  if (normalized.includes("functional") || normalized.includes("loopback") || normalized.includes("scan")) return "functional";
  return "measurement";
}

function inferMeasurementUnit(type: string) {
  if (type === "voltage" || type === "logic_level") return "V";
  if (type === "resistance") return "ohm";
  if (type === "current") return "mA";
  return "";
}

function measurementValuePlaceholder(type: string) {
  if (type === "voltage" || type === "logic_level") return "3.31";
  if (type === "resistance") return "open, 10k, 47k";
  if (type === "current") return "18";
  if (type === "thermal") return "normal";
  if (type === "continuity" || type === "functional") return "pass";
  return "pass, 4.91, 10k";
}

function draftFromMeasurementPrompt(prompt: string): MeasurementDraft {
  const type = inferMeasurementType(prompt);
  return {
    type,
    target: prompt,
    value: "",
    unit: inferMeasurementUnit(type),
    notes: `Verifier requested: ${prompt}`,
  };
}

function normalizeQueueText(value: string | undefined) {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9+.-]+/g, " ")
    .trim();
}

function measurementDisplayValue(measurement: RepairMeasurementEvidence) {
  return `${String(measurement.value ?? "")}${measurement.unit ? ` ${measurement.unit}` : ""}`.trim();
}

function measurementMatchesPrompt(measurement: RepairMeasurementEvidence, prompt: string, type: string) {
  const promptText = normalizeQueueText(prompt);
  const targetText = normalizeQueueText(measurement.target);
  if (!promptText || !targetText) return false;
  if (targetText === promptText || targetText.includes(promptText) || promptText.includes(targetText)) return true;

  const measurementText = normalizeQueueText(`${measurement.type ?? ""} ${measurement.target ?? ""} ${measurement.notes ?? ""}`);
  const typeMatches = normalizeQueueText(measurement.type).includes(normalizeQueueText(type));
  const promptTokens = promptText.split(" ").filter((token) => token.length > 3);
  const tokenMatches = promptTokens.filter((token) => measurementText.includes(token)).length;
  return typeMatches && tokenMatches >= Math.min(3, promptTokens.length);
}

function addQueuePrompts(rows: Array<{ prompt: string; source: string }>, prompts: string[] | undefined, source: string) {
  for (const prompt of prompts ?? []) {
    const trimmed = prompt.trim();
    if (trimmed) rows.push({ prompt: trimmed, source });
  }
}

function buildMeasurementQueue({
  evidence,
  verification,
  measurements,
  trust,
  certaintyLedger,
}: {
  evidence: BoardEvidence | null;
  verification: VerifyResponse | null;
  measurements: RepairMeasurementEvidence[];
  trust?: BoardEvidenceTrust;
  certaintyLedger?: IdentifyResponse["certaintyLedger"];
}): MeasurementQueueItem[] {
  const rows: Array<{ prompt: string; source: string }> = [];
  addQueuePrompts(rows, verification?.repair_authority?.required_measurements, "repair authority");
  addQueuePrompts(rows, verification?.recommended_next_actions, "verifier next check");
  addQueuePrompts(rows, trust?.required_evidence, "trust gate");
  addQueuePrompts(rows, evidence?.recommended_checks, "board evidence");
  addQueuePrompts(rows, evidence?.uncertainty?.next_actions, "visual uncertainty");
  addQueuePrompts(rows, certaintyLedger?.missing_evidence, "certainty ledger");
  addQueuePrompts(rows, certaintyLedger?.next_actions, "certainty next action");

  const seen = new Set<string>();
  return rows
    .filter((row) => {
      const key = normalizeQueueText(row.prompt);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 12)
    .map((row, index) => {
      const type = inferMeasurementType(row.prompt);
      const matched = measurements.find((measurement) => measurementMatchesPrompt(measurement, row.prompt, type));
      return {
        id: `${row.source}-${index}-${normalizeQueueText(row.prompt).slice(0, 24)}`,
        prompt: row.prompt,
        type,
        unit: inferMeasurementUnit(type),
        source: row.source,
        recorded: Boolean(matched),
        matchedValue: matched ? measurementDisplayValue(matched) : undefined,
      };
    });
}

function formatPercent(value: number | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${Math.round(value * 100)}%`;
}

export default function ScanPage() {
  usePageTitle("Scan | Circuit.AI");
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0a0f1a]" />}>
      <ScanPageInner />
    </Suspense>
  );
}

function ScanPageInner() {
  const search = useSearchParams();
  const initialMode: Mode = search?.get("mode") === "salvage" ? "salvage" : "identify";

  const [mode, setMode] = useState<Mode>(initialMode);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [goldenFile, setGoldenFile] = useState<File | null>(null);
  const [referenceCounts, setReferenceCounts] = useState("");
  const [referenceTopology, setReferenceTopology] = useState("");
  const [aoiProfile, setAoiProfile] = useState("");
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [result, setResult] = useState<IdentifyResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingSession, setSavingSession] = useState(false);
  const [verifyingEvidence, setVerifyingEvidence] = useState(false);
  const [verification, setVerification] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [savedSessionId, setSavedSessionId] = useState<string | null>(null);
  const [measurements, setMeasurements] = useState<RepairMeasurementEvidence[]>([]);
  const [measurementDraft, setMeasurementDraft] = useState<MeasurementDraft>({
    type: "continuity",
    target: "",
    value: "",
    unit: "",
    notes: "",
  });
  const [addingMeasurement, setAddingMeasurement] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addInventoryPart = useWorkbenchStore((s) => s.addInventoryPart);
  const setSalvageModules = useWorkbenchStore((s) => s.setSalvageModules);
  const setSafetyLevel = useWorkbenchStore((s) => s.setSafetyLevel);

  const modules: SalvageModule[] = useMemo(() => {
    if (!result) return [];
    return result.modules ?? result.components ?? [];
  }, [result]);

  const selectedModule = useMemo(
    () => modules.find((m) => m.id === selectedId) ?? null,
    [modules, selectedId],
  );

  const boardEvidence = useMemo(() => (
    result?.board_evidence ?? result?.evidence?.board_evidence ?? null
  ), [result]);

  const measurementQueue = useMemo(
    () => buildMeasurementQueue({
      evidence: boardEvidence,
      verification,
      measurements,
      trust: result?.evidence_trust,
      certaintyLedger: result?.certaintyLedger,
    }),
    [boardEvidence, measurements, result?.certaintyLedger, result?.evidence_trust, verification],
  );

  const buildSessionAnalysis = useCallback((nextVerification?: VerifyResponse | null) => {
    if (!result) return {};
    const productionAoi = result.productionAoi;
    const componentsByType = modules.reduce<Record<string, number>>((counts, module) => {
      const key = module.kind ?? "unknown";
      counts[key] = (counts[key] ?? 0) + 1;
      return counts;
    }, {});
    const moduleDetections = modules.map((module) => ({
      class_name: module.kind ?? "unknown",
      label: module.label,
      confidence: undefined,
      bbox: module.bbox,
      safety: module.safety,
      warnings: module.warnings ?? [],
    }));
    const base = result.rawAnalysis && typeof result.rawAnalysis === "object" ? { ...result.rawAnalysis } : {};
    return {
      ...base,
      detections: Array.isArray(base.detections) ? base.detections : moduleDetections,
      detection_summary: typeof base.detection_summary === "object" && base.detection_summary
        ? base.detection_summary
        : {
            total_components: modules.length,
            components_by_type: componentsByType,
            review_required: Boolean(result.reviewRequired),
          },
      board_evidence: boardEvidence,
      evidence_trust: nextVerification?.deterministic_trust ?? result.evidence_trust,
      deterministic_trust: nextVerification?.deterministic_trust,
      repair_authority: nextVerification?.repair_authority,
      verification: nextVerification ? {
        safety_level: nextVerification.safety_level,
        verifier_status: nextVerification.verifier_status,
        summary: nextVerification.summary,
        launch_readiness: nextVerification.launch_readiness,
        contradictions: nextVerification.contradictions,
        unsupported_claims: nextVerification.unsupported_claims,
        missing_measurements: nextVerification.missing_measurements,
        recommended_next_actions: nextVerification.recommended_next_actions,
        model: nextVerification.model,
        usage: nextVerification.usage,
      } : undefined,
      production_aoi: productionAoi ? {
        disposition: productionAoi.disposition,
        release_authorized: productionAoi.releaseAuthorized,
        certainty_score: productionAoi.certaintyScore,
        certainty_level: productionAoi.certaintyLevel,
        blockers: productionAoi.blockers,
        required_evidence: productionAoi.requiredEvidence,
        gates: productionAoi.gates,
      } : undefined,
      certainty_ledger: result.certaintyLedger,
    };
  }, [boardEvidence, modules, result]);

  const addScannedModuleToInventory = useCallback((module: SalvageModule) => {
    const part = {
      label: module.label,
      kind: module.kind ?? "unknown",
      source: mode === "salvage" ? "salvage" as const : "scan" as const,
      qty: 1,
      notes: module.description ?? module.extraction,
      photoUrl: imageUrl ?? undefined,
    };
    addInventoryPart(part);
    addInventoryItem(part);
  }, [addInventoryPart, imageUrl, mode]);

  const mapKind = useCallback((className: string): SalvageModule["kind"] => {
    const normalized = className.toLowerCase();
    if (normalized.includes("connector") || normalized.includes("switch")) return "connector";
    if (normalized.includes("ic") || normalized.includes("mcu") || normalized.includes("micro")) return "mcu";
    if (normalized.includes("sensor")) return "sensor";
    if (normalized.includes("transistor") || normalized.includes("mosfet") || normalized.includes("driver")) return "driver";
    if (normalized.includes("capacitor") || normalized.includes("resistor") || normalized.includes("inductor") || normalized.includes("diode") || normalized.includes("crystal")) return "passive";
    return "unknown";
  }, []);

  const mapLocalAnalysis = useCallback((json: LocalAnalyzeResponse): IdentifyResponse => {
    if (json.error) {
      return {
        safety_level: "caution",
        explanation: json.error,
        components: [],
        error: json.error,
        source: "local",
      };
    }

    const detections = json.results?.detections ?? [];
    const summary = json.results?.detection_summary;
    const backend = json.metadata?.backend ?? json.results?.analysis_metadata?.backend ?? "local";
    const quality = json.metadata?.detection_quality ?? summary?.detection_quality ?? "unknown";
    const reviewRequired = Boolean(summary?.review_required ?? json.results?.analysis_metadata?.review_required);

    const modules = detections.map((det, index): SalvageModule => {
      const className = det.class_name ?? "unknown";
      const bbox = det.bbox;
      const normalizedBox = bbox && imageSize
        ? {
          x: Math.max(0, Math.min(1, bbox[0] / imageSize.width)),
          y: Math.max(0, Math.min(1, bbox[1] / imageSize.height)),
          w: Math.max(0, Math.min(1, (bbox[2] - bbox[0]) / imageSize.width)),
          h: Math.max(0, Math.min(1, (bbox[3] - bbox[1]) / imageSize.height)),
        }
        : undefined;
      const confidence = typeof det.confidence === "number" ? ` (${Math.round(det.confidence * 100)}%)` : "";
      const partText = det.part_number || det.ocr_text;
      return {
        id: `local-${index + 1}`,
        kind: mapKind(className),
        label: partText ? `${partText} ${className}` : className,
        description: `Local ${backend} detector classified this region as ${className}${confidence}. Treat this as a candidate detection until reviewed against the photo.`,
        safety: "safe",
        bbox: normalizedBox,
      };
    });

    return {
      safety_level: "safe",
      explanation: json.summary?.summary_text
        ?? `Local scan completed with ${summary?.total_components ?? modules.length} candidate detections using ${backend}. Detection quality: ${quality}.`,
      components: modules,
      source: "local",
      backend,
      model: backend,
      reviewRequired,
      rawAnalysis: json.results as Record<string, unknown> | undefined,
      visualTopology: {
        traceCount: json.results?.visual_topology?.trace_count ?? 0,
        connectionCount: json.results?.visual_topology?.connection_count ?? 0,
        confidence: json.results?.visual_topology?.confidence ?? 0,
        uncertainty: json.results?.visual_topology?.uncertainty,
      },
      aoiInspection: {
        readiness: json.results?.aoi_inspection?.readiness,
        score: json.results?.aoi_inspection?.score,
        learnedDetectionRatio: json.results?.aoi_inspection?.learned_detection_ratio,
        defectCandidateCount: json.results?.aoi_inspection?.defect_candidate_count
          ?? json.results?.defect_inspection?.defect_count
          ?? 0,
      },
      productionAoi: {
        disposition: json.results?.production_aoi?.disposition,
        releaseAuthorized: json.results?.production_aoi?.release_authorized,
        certaintyScore: json.results?.production_aoi?.certainty_score,
        certaintyLevel: json.results?.production_aoi?.certainty_level,
        blockers: json.results?.production_aoi?.blockers,
        requiredEvidence: json.results?.production_aoi?.required_evidence,
        gates: json.results?.production_aoi?.gates,
      },
      certaintyLedger: json.results?.certainty_ledger,
    };
  }, [imageSize, mapKind]);

  const onSelectFile = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please pick an image file (JPEG, PNG, etc.)");
      return;
    }
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    const nextUrl = URL.createObjectURL(file);
    setImageFile(file);
    setImageUrl(nextUrl);
    setImageSize(null);
    const img = new Image();
    img.onload = () => setImageSize({ width: img.naturalWidth || 1, height: img.naturalHeight || 1 });
    img.src = nextUrl;
    setResult(null);
    setSelectedId(null);
    setSavedSessionId(null);
    setMeasurements([]);
    setError(null);
    setSaveMessage(null);
  }, [imageUrl]);

  const analyze = useCallback(async () => {
    if (!imageFile) return;
    setLoading(true);
    setError(null);
    setSaveMessage(null);
    setVerification(null);
    setResult(null);

    const fd = new FormData();
    const needsLocalAoi = Boolean(goldenFile || referenceCounts.trim() || referenceTopology.trim() || aoiProfile.trim());
    const endpoint = mode === "salvage"
      ? "/api/jarvis/plan-salvage"
      : needsLocalAoi
        ? "/api/proxy/analyze"
        : "/api/jarvis/identify";
    if (mode === "salvage") {
      fd.append("image", imageFile);
    } else if (needsLocalAoi) {
      fd.append("file", imageFile);
      fd.append("backend", "hybrid");
      fd.append("enable_ocr", "false");
      if (goldenFile) fd.append("golden_file", goldenFile);
      if (referenceCounts.trim()) fd.append("reference_counts", referenceCounts.trim());
      if (referenceTopology.trim()) fd.append("reference_topology", referenceTopology.trim());
      if (aoiProfile.trim()) fd.append("aoi_profile", aoiProfile.trim());
    } else {
      fd.append("image", imageFile);
    }

    try {
      const resp = await fetch(endpoint, { method: "POST", body: fd });
      const rawJson = await resp.json() as IdentifyResponse | LocalAnalyzeResponse;
      const json = mode === "salvage" || !needsLocalAoi
        ? rawJson as IdentifyResponse
        : mapLocalAnalysis(rawJson as LocalAnalyzeResponse);
      if (!resp.ok || json.error) {
        setError(json.error ?? `Request failed (${resp.status})`);
        return;
      }
      setResult(json);
      const mods = json.modules ?? json.components ?? [];
      setSalvageModules(mods);
      setSafetyLevel(json.safety_level ?? "safe");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [aoiProfile, goldenFile, imageFile, mapLocalAnalysis, mode, referenceCounts, referenceTopology, setSalvageModules, setSafetyLevel]);

  const verifyBoardEvidence = useCallback(async (measurementOverride?: RepairMeasurementEvidence[]) => {
    if (!boardEvidence || !result) return;
    const activeMeasurements = measurementOverride ?? measurements;
    setVerifyingEvidence(true);
    setError(null);
    setVerification(null);
    try {
      const response = await fetch("/api/jarvis/verify-board-evidence", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          board_evidence: boardEvidence,
          scan_summary: {
            safety_level: result.safety_level,
            explanation: result.explanation,
            source: result.source,
            model: result.model,
            modules: modules.slice(0, 20),
            measurements: activeMeasurements,
          },
          measurements: activeMeasurements,
        }),
      });
      const payload = await response.json() as VerifyResponse;
      if (!response.ok || payload.error) {
        throw new Error(payload.error ?? `Verification failed (${response.status})`);
      }
      setVerification(payload);
      if (savedSessionId) {
        try {
          const persistResponse = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(savedSessionId)}/analysis`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              source: "scan_verification",
              summary: {
                summary_text: payload.summary,
                verifier_status: payload.verifier_status,
                repair_authority_status: payload.repair_authority?.status,
                launch_readiness: payload.launch_readiness?.level,
              },
              analysis: buildSessionAnalysis(payload),
            }),
          });
          const persistPayload = await persistResponse.json() as { error?: string };
          if (!persistResponse.ok || persistPayload.error) {
            throw new Error(persistPayload.error ?? `Case update failed (${persistResponse.status})`);
          }
          setSaveMessage(`Updated authority snapshot for ${savedSessionId}`);
        } catch (persistError) {
          setSaveMessage(`Verified, but case snapshot was not updated: ${persistError instanceof Error ? persistError.message : String(persistError)}`);
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not verify board evidence.");
    } finally {
      setVerifyingEvidence(false);
    }
  }, [boardEvidence, buildSessionAnalysis, measurements, modules, result, savedSessionId]);

  const saveReviewCase = useCallback(async () => {
    if (!result) return;
    setSavingSession(true);
    setError(null);
    setSaveMessage(null);
    const productionAoi = result.productionAoi;
    const analysis = buildSessionAnalysis(verification);
    try {
      const response = await fetch("/api/proxy/board-sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          description: productionAoi?.disposition
            ? `Scan AOI result: ${productionAoi.disposition.replace(/_/g, " ")}`
            : "Scan analysis result",
          route: productionAoi ? "aoi" : mode,
          analysis,
          summary: { summary_text: result.explanation },
          source: "scan_ui",
        }),
      });
      const payload = await response.json() as { session?: { session_id?: string }; error?: string };
      if (!response.ok || payload.error) {
        throw new Error(payload.error ?? `Save failed (${response.status})`);
      }
      const nextSessionId = payload.session?.session_id ?? "";
      setSavedSessionId(nextSessionId || null);
      setSaveMessage(`Saved review case ${nextSessionId}`.trim());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save review case.");
    } finally {
      setSavingSession(false);
    }
  }, [buildSessionAnalysis, mode, result, verification]);

  const addMeasurementEvidence = useCallback(async () => {
    if (!savedSessionId) {
      setError("Save the case before adding bench measurements.");
      return;
    }
    const target = measurementDraft.target.trim();
    const value = measurementDraft.value.trim();
    if (!target || !value) {
      setError("Measurement target and value are required.");
      return;
    }
    setAddingMeasurement(true);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(savedSessionId)}/measurement`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          type: measurementDraft.type.trim() || "measurement",
          target,
          value,
          unit: measurementDraft.unit.trim(),
          notes: measurementDraft.notes.trim(),
          confidence: 1,
        }),
      });
      const payload = await response.json() as {
        result?: {
          measurement?: RepairMeasurementEvidence;
          session?: { evidence?: { measurements?: RepairMeasurementEvidence[] } };
        };
        error?: string;
      };
      if (!response.ok || payload.error) {
        throw new Error(payload.error ?? `Measurement save failed (${response.status})`);
      }
      const nextMeasurements = payload.result?.session?.evidence?.measurements
        ?? (payload.result?.measurement ? [...measurements, payload.result.measurement] : measurements);
      setMeasurements(nextMeasurements);
      setMeasurementDraft({ type: "voltage", target: "", value: "", unit: "", notes: "" });
      setVerification(null);
      setSaveMessage(`Added measurement to ${savedSessionId}`);
      void verifyBoardEvidence(nextMeasurements);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save measurement.");
    } finally {
      setAddingMeasurement(false);
    }
  }, [measurementDraft, measurements, savedSessionId, verifyBoardEvidence]);

  const reset = () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(null);
    setImageUrl(null);
    setGoldenFile(null);
    setImageSize(null);
    setResult(null);
    setVerification(null);
    setSelectedId(null);
    setSavedSessionId(null);
    setMeasurements([]);
    setError(null);
    setSaveMessage(null);
  };

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header with mode toggle */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">Scan a board</h1>
            <p className="mt-1 text-sm text-slate-400">
              Upload a photo — we identify every block and tell you what&apos;s worth reusing.
            </p>
          </div>

          <div className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.02] p-0.5 text-xs font-medium">
            <button
              onClick={() => { setMode("identify"); setResult(null); }}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors ${
                mode === "identify" ? "bg-white text-slate-900" : "text-slate-400 hover:text-white"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" /> Identify
            </button>
            <button
              onClick={() => { setMode("salvage"); setResult(null); }}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors ${
                mode === "salvage" ? "bg-white text-slate-900" : "text-slate-400 hover:text-white"
              }`}
            >
              <Scissors className="h-3.5 w-3.5" /> Salvage plan
            </button>
          </div>
        </div>

        {/* Drop/upload zone OR image + overlay */}
        {!imageUrl ? (
          <UploadZone onPick={onSelectFile} fileInputRef={fileInputRef} onOpenCamera={() => setCameraOpen(true)} />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
            {/* Canvas */}
            <div className="space-y-4">
              <IdentificationOverlay
                imageUrl={imageUrl}
                modules={modules}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={analyze}
                  disabled={loading}
                  size="sm"
                  className="rounded-full bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-60"
                >
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  {loading ? "Analyzing…" : result ? "Analyze again" : `Run ${mode === "salvage" ? "salvage plan" : "identification"}`}
                </Button>
                <Button
                  onClick={reset}
                  size="sm"
                  variant="outline"
                  className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  New photo
                </Button>
                {result && (
                  <Button
                    onClick={() => void saveReviewCase()}
                    disabled={savingSession}
                    size="sm"
                    variant="outline"
                    className="rounded-full border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15"
                  >
                    {savingSession ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ClipboardList className="mr-2 h-4 w-4" />}
                    Save case
                  </Button>
                )}
                {result?.fromCache && (
                  <span className="ml-1 text-[11px] text-slate-500">
                    served from cache · {result.model}
                  </span>
                )}
              </div>

              {mode === "identify" && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
                  <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">
                    <ShieldCheck className="h-4 w-4" />
                    Production gate inputs
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <label className="block rounded-lg border border-white/10 bg-black/20 p-3">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Golden image</span>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(event) => setGoldenFile(event.target.files?.[0] ?? null)}
                        className="mt-2 block w-full text-xs text-slate-400 file:mr-3 file:rounded-full file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-900"
                      />
                      {goldenFile && <span className="mt-2 block truncate text-xs text-slate-400">{goldenFile.name}</span>}
                    </label>
                    <label className="block rounded-lg border border-white/10 bg-black/20 p-3">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Reference counts</span>
                      <textarea
                        value={referenceCounts}
                        onChange={(event) => setReferenceCounts(event.target.value)}
                        rows={3}
                        placeholder='{"resistor": 4, "capacitor": 2}'
                        className="mt-2 w-full resize-none rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                      />
                    </label>
                    <label className="block rounded-lg border border-white/10 bg-black/20 p-3">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Reference topology</span>
                      <textarea
                        value={referenceTopology}
                        onChange={(event) => setReferenceTopology(event.target.value)}
                        rows={3}
                        placeholder='{"nets":{},"components":{}}'
                        className="mt-2 w-full resize-none rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                      />
                    </label>
                    <label className="block rounded-lg border border-white/10 bg-black/20 p-3">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">AOI profile</span>
                      <textarea
                        value={aoiProfile}
                        onChange={(event) => setAoiProfile(event.target.value)}
                        rows={3}
                        placeholder='{"fixture_id":"fx-1","calibration_id":"cal-1","station_id":"aoi-1"}'
                        className="mt-2 w-full resize-none rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                      />
                    </label>
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
              {saveMessage && (
                <div className="rounded-xl border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-100">
                  {saveMessage}
                </div>
              )}
            </div>

            {/* Side panel */}
            <div className="space-y-4">
              {result?.safety_level && result.safety_level !== "safe" && (
                <SafetyBanner
                  level={result.safety_level}
                  message={
                    result.safety_level === "hazard"
                      ? "This device contains mains voltage, a lithium pack, bulk capacitors, or another serious hazard. Read the warnings on each block before touching anything."
                      : "This device runs above low-voltage safe limits. Power it off and discharge capacitors before probing."
                  }
                />
              )}

              {result?.explanation && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">
                    What this is
                  </div>
                  <p className="text-sm leading-6 text-slate-200">{result.explanation}</p>
                </div>
              )}

              {boardEvidence && (
                <>
                  <BoardEvidencePanel
                    evidence={boardEvidence}
                    result={result}
                    verification={verification}
                    verifying={verifyingEvidence}
                    onVerify={verifyBoardEvidence}
                    onUseMeasurementPrompt={(prompt) => setMeasurementDraft(draftFromMeasurementPrompt(prompt))}
                  />
                  <MeasurementEvidencePanel
                    sessionId={savedSessionId}
                    measurements={measurements}
                    queue={measurementQueue}
                    draft={measurementDraft}
                    adding={addingMeasurement}
                    authorityStatus={verification?.repair_authority?.status ?? result?.evidence_trust?.launch_readiness}
                    authorityScore={verification?.repair_authority?.score ?? result?.evidence_trust?.score}
                    onDraftChange={setMeasurementDraft}
                    onUsePrompt={(prompt) => setMeasurementDraft(draftFromMeasurementPrompt(prompt))}
                    onAdd={() => void addMeasurementEvidence()}
                  />
                </>
              )}

              {result?.aoiInspection && (
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">AOI</div>
                    <div className="mt-1 text-sm text-white">{result.aoiInspection.readiness ?? "unknown"}</div>
                    <div className="text-[11px] text-slate-500">{Math.round((result.aoiInspection.score ?? 0) * 100)}%</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Topology</div>
                    <div className="mt-1 text-sm text-white">
                      {result.visualTopology?.traceCount ?? 0} traces · {result.visualTopology?.connectionCount ?? 0} links
                    </div>
                    <div className="text-[11px] text-slate-500">{Math.round((result.visualTopology?.confidence ?? 0) * 100)}% · {result.visualTopology?.uncertainty ?? "high"}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Learned</div>
                    <div className="mt-1 text-sm text-white">{Math.round((result.aoiInspection.learnedDetectionRatio ?? 0) * 100)}%</div>
                    <div className="text-[11px] text-slate-500">{result.backend ?? "local"}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Defects</div>
                    <div className="mt-1 text-sm text-white">{result.aoiInspection.defectCandidateCount ?? 0} candidates</div>
                    <div className="text-[11px] text-slate-500">visual AOI</div>
                  </div>
                </div>
              )}

              {result?.productionAoi?.disposition && (
                <div className={`rounded-2xl border p-5 ${
                  result.productionAoi.releaseAuthorized
                    ? "border-emerald-300/30 bg-emerald-300/10"
                    : "border-amber-300/30 bg-amber-300/10"
                }`}>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-100/90">
                      <ShieldCheck className="h-4 w-4" />
                      Production AOI gate
                    </div>
                    <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-[11px] text-slate-100">
                      {result.productionAoi.certaintyLevel ?? "not production ready"} · {formatPercent(result.productionAoi.certaintyScore)}
                    </span>
                  </div>
                  <div className="text-lg font-semibold text-white">
                    {result.productionAoi.disposition.replace(/_/g, " ")}
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {(result.productionAoi.gates ?? []).slice(0, 6).map((gate) => (
                      <div key={gate.gate_id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-white">{gate.gate_id?.replace(/_/g, " ")}</span>
                          <span className="text-[11px] uppercase text-slate-400">{gate.status}</span>
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400">{formatPercent(gate.score)}</div>
                      </div>
                    ))}
                  </div>
                  {(result.productionAoi.blockers ?? []).length ? (
                    <div className="mt-4 space-y-1.5">
                      {(result.productionAoi.blockers ?? []).slice(0, 4).map((item) => (
                        <div key={item} className="text-xs leading-5 text-amber-50/90">{item}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}

              {result?.certaintyLedger?.overall && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">
                      <ShieldCheck className="h-4 w-4" />
                      Evidence certainty
                    </div>
                    <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-200">
                      {result.certaintyLedger.overall.level ?? "unknown"} · {formatPercent(result.certaintyLedger.overall.score)}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-slate-200">
                    {result.certaintyLedger.overall.summary ?? "The scan produced an evidence ledger for review."}
                  </p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        <Search className="h-3.5 w-3.5" />
                        Missing evidence
                      </div>
                      <div className="space-y-1.5">
                        {(result.certaintyLedger.missing_evidence ?? []).slice(0, 4).map((item) => (
                          <div key={item} className="text-xs leading-5 text-slate-400">{item}</div>
                        ))}
                        {!(result.certaintyLedger.missing_evidence ?? []).length && (
                          <div className="text-xs text-slate-500">No major missing evidence flagged.</div>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        <ClipboardList className="h-3.5 w-3.5" />
                        Next actions
                      </div>
                      <div className="space-y-1.5">
                        {(result.certaintyLedger.next_actions ?? []).slice(0, 4).map((item) => (
                          <div key={item} className="text-xs leading-5 text-slate-400">{item}</div>
                        ))}
                        {!(result.certaintyLedger.next_actions ?? []).length && (
                          <div className="text-xs text-slate-500">No extra action generated.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {selectedModule ? (
                <ModuleDetail
                  module={selectedModule}
                  onAddToInventory={() => addScannedModuleToInventory(selectedModule)}
                  onStartBuild={() => {
                    addScannedModuleToInventory(selectedModule);
                    window.location.href = `/build?modules=${encodeURIComponent(selectedModule.label)}`;
                  }}
                />
              ) : modules.length > 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    {modules.length} {result?.reviewRequired ? "candidate " : ""}{modules.length === 1 ? "block" : "blocks"} identified — click one on the image
                  </div>
                  <div className="space-y-1.5">
                    {modules.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => setSelectedId(m.id)}
                        className="flex w-full items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-left hover:bg-white/5 transition-colors"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm text-white">{m.label}</div>
                          <div className="text-[11px] text-slate-500">{m.kind ?? "unknown"}</div>
                        </div>
                        {m.safety && m.safety !== "safe" && (
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                            m.safety === "hazard" ? "bg-rose-400/20 text-rose-200" : "bg-amber-400/20 text-amber-200"
                          }`}>
                            {m.safety}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ) : !loading ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.01] p-8 text-center text-sm text-slate-500">
                  Click <strong className="text-white/80">{result ? "Analyze again" : `Run ${mode === "salvage" ? "salvage plan" : "identification"}`}</strong> to get started.
                </div>
              ) : null}

              <div className="rounded-2xl border border-white/5 bg-white/[0.01] p-4 text-xs text-slate-500">
                After you&apos;re done here: add useful blocks to your <Link href="/parts" className="text-cyan-300 hover:text-cyan-200 underline underline-offset-2">parts bin</Link> or jump to <Link href="/build" className="text-cyan-300 hover:text-cyan-200 underline underline-offset-2">Build</Link> to wire them up.
              </div>
            </div>
          </div>
        )}

        {cameraOpen && (
          <CameraCapture
            onCapture={(file) => {
              setCameraOpen(false);
              onSelectFile(file);
            }}
            onClose={() => setCameraOpen(false)}
          />
        )}
      </main>
    </div>
  );
}

function statusTone(status?: string) {
  const normalized = (status ?? "").toLowerCase();
  if (normalized.includes("pass") || normalized.includes("experimental") || normalized.includes("private_alpha") || normalized.includes("authoritative") || normalized.includes("measurement_backed")) return "border-emerald-300/30 bg-emerald-300/10 text-emerald-100";
  if (normalized.includes("blocked") || normalized.includes("unsafe") || normalized.includes("hold")) return "border-rose-300/30 bg-rose-300/10 text-rose-100";
  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
}

function EvidencePill({ label, value }: { label: string; value: string | number | undefined }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-1 truncate text-xs text-white">{value ?? "unknown"}</div>
    </div>
  );
}

function EvidenceList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="space-y-1.5">
        {items.slice(0, 5).map((item) => (
          <div key={item} className="rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-xs leading-5 text-slate-300">
            {item}
          </div>
        ))}
        {!items.length && <div className="text-xs text-slate-500">{empty}</div>}
      </div>
    </div>
  );
}

function ActionableEvidenceList({
  title,
  items,
  empty,
  onUse,
}: {
  title: string;
  items: string[];
  empty: string;
  onUse(prompt: string): void;
}) {
  return (
    <div>
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="space-y-1.5">
        {items.slice(0, 5).map((item) => (
          <div key={item} className="flex items-start justify-between gap-2 rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5">
            <div className="min-w-0 text-xs leading-5 text-slate-300">{item}</div>
            <button
              type="button"
              onClick={() => onUse(item)}
              className="shrink-0 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-100 hover:bg-cyan-300/15"
            >
              Use
            </button>
          </div>
        ))}
        {!items.length && <div className="text-xs text-slate-500">{empty}</div>}
      </div>
    </div>
  );
}

function BoardEvidencePanel({
  evidence,
  result,
  verification,
  verifying,
  onVerify,
  onUseMeasurementPrompt,
}: {
  evidence: BoardEvidence;
  result: IdentifyResponse | null;
  verification: VerifyResponse | null;
  verifying: boolean;
  onVerify(): void;
  onUseMeasurementPrompt(prompt: string): void;
}) {
  const markings = (evidence.markings ?? []).map((marking) => marking.text).filter(Boolean);
  const damage = (evidence.damage ?? []).map((item) => `${item.label}${item.severity ? ` · ${item.severity}` : ""}`);
  const testPoints = (evidence.test_points ?? []).map((item) => `${item.label}${item.expected_signal ? ` · ${item.expected_signal}` : ""}`);
  const salvage = (evidence.salvage_candidates ?? []).map((item) => `${item.label}${item.rationale ? ` · ${item.rationale}` : ""}`);
  const uncertaintyReasons = [
    ...(evidence.uncertainty?.reasons ?? []),
    ...(evidence.uncertainty?.missing_evidence ?? []),
  ];
  const sourceLabel = result?.source?.replace(/_/g, " ") ?? evidence.source.provider;
  const cost = typeof result?.cost_usd_estimate === "number" ? `$${result.cost_usd_estimate.toFixed(6)}` : undefined;
  const trust = result?.evidence_trust ?? verification?.deterministic_trust;
  const trustScore = typeof trust?.score === "number" ? `${Math.round(trust.score * 100)}%` : "unknown";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">
            <Search className="h-4 w-4" />
            Board evidence
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {sourceLabel} · {result?.model ?? evidence.source.model ?? evidence.source.provider}
          </div>
        </div>
        <Button
          onClick={onVerify}
          disabled={verifying}
          size="sm"
          variant="outline"
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
        >
          {verifying ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
          Verify evidence
        </Button>
      </div>

      <div className="grid gap-2 sm:grid-cols-4">
        <EvidencePill label="Components" value={(evidence.components ?? []).length} />
        <EvidencePill label="Markings" value={markings.length} />
        <EvidencePill label="Uncertainty" value={evidence.uncertainty?.level} />
        <EvidencePill label="Cost" value={cost ?? "cached/free"} />
      </div>

      {trust && (
        <div className={`mt-4 rounded-xl border p-3 ${statusTone(trust.launch_readiness)}`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em]">
                Evidence trust · {trust.launch_readiness.replace(/_/g, " ")}
              </div>
              <div className="mt-1 text-[11px] opacity-80">{trust.level} confidence · {trustScore}</div>
            </div>
            <div className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-[11px]">
              image-only gate
            </div>
          </div>
          <p className="mt-2 text-sm leading-6">{trust.summary}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <EvidenceList title="Strengths" items={trust.strengths ?? []} empty="No trust strengths yet." />
            <EvidenceList title="Required evidence" items={trust.required_evidence ?? []} empty="No extra evidence required." />
          </div>
          {(trust.blockers ?? []).length ? (
            <div className="mt-3">
              <EvidenceList title="Trust blockers" items={trust.blockers} empty="No blockers listed." />
            </div>
          ) : null}
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <EvidenceList title="Markings" items={markings} empty="No readable markings returned." />
        <EvidenceList title="Salvage candidates" items={salvage} empty="No independent salvage candidates yet." />
        <EvidenceList title="Damage / risk" items={damage} empty="No damage regions flagged." />
        <EvidenceList title="Test points" items={testPoints} empty="No test points localized." />
      </div>

      <div className="mt-4">
        <EvidenceList title="Uncertainty / missing evidence" items={uncertaintyReasons} empty="No major uncertainty listed." />
      </div>

      {verification && (
        <div className={`mt-4 rounded-xl border p-3 ${statusTone(verification.verifier_status ?? verification.launch_readiness?.level)}`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-[0.18em]">
              {verification.verifier_status ?? "verified"}
            </div>
            <div className="text-[11px] opacity-80">{verification.model}</div>
          </div>
          {verification.summary && <p className="mt-2 text-sm leading-6">{verification.summary}</p>}
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <EvidenceList title="Unsupported claims" items={verification.unsupported_claims ?? []} empty="No unsupported claims listed." />
            <ActionableEvidenceList
              title="Next checks"
              items={verification.recommended_next_actions ?? []}
              empty="No next checks listed."
              onUse={onUseMeasurementPrompt}
            />
          </div>
          {verification.repair_authority && (
            <div className={`mt-3 rounded-lg border p-3 ${statusTone(verification.repair_authority.status)}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-[0.18em]">
                  Repair authority · {verification.repair_authority.status.replace(/_/g, " ")}
                </div>
                <div className="text-[11px] opacity-80">{Math.round(verification.repair_authority.score * 100)}%</div>
              </div>
              <p className="mt-2 text-xs leading-5">{verification.repair_authority.summary}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <ActionableEvidenceList
                  title="Required measurements"
                  items={verification.repair_authority.required_measurements ?? []}
                  empty="No missing measurements listed."
                  onUse={onUseMeasurementPrompt}
                />
                <EvidenceList title="Blocked decisions" items={verification.repair_authority.blocked_decisions ?? []} empty="No blocked decisions listed." />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AuthorityStep({ label, done }: { label: string; done: boolean }) {
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${
      done
        ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"
        : "border-white/10 bg-black/15 text-slate-400"
    }`}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em]">{done ? "done" : "open"}</div>
      <div className="mt-1 text-xs leading-4">{label}</div>
    </div>
  );
}

function MeasurementEvidencePanel({
  sessionId,
  measurements,
  queue,
  draft,
  adding,
  authorityStatus,
  authorityScore,
  onDraftChange,
  onUsePrompt,
  onAdd,
}: {
  sessionId: string | null;
  measurements: RepairMeasurementEvidence[];
  queue: MeasurementQueueItem[];
  draft: MeasurementDraft;
  adding: boolean;
  authorityStatus?: string;
  authorityScore?: number;
  onDraftChange(next: MeasurementDraft): void;
  onUsePrompt(prompt: string): void;
  onAdd(): void;
}) {
  const completedQueue = queue.filter((item) => item.recorded).length;
  const nextPending = queue.find((item) => !item.recorded);
  const authorityLabel = authorityStatus?.replace(/_/g, " ") ?? "visual evidence not verified";
  const authorityScoreLabel = typeof authorityScore === "number" ? `${Math.round(authorityScore * 100)}%` : "N/A";
  const hasVerifiedAuthority = Boolean(authorityStatus);
  const hasBenchEvidence = measurements.length > 0;
  const queueClosed = queue.length > 0 && completedQueue === queue.length;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">
            <ClipboardList className="h-4 w-4" />
            Bench measurements
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {sessionId ? `case ${sessionId}` : "save case to attach readings"}
          </div>
        </div>
        <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-[11px] text-slate-200">
          {measurements.length} recorded
        </span>
      </div>

      <div className={`mb-4 rounded-xl border p-3 ${statusTone(authorityStatus)}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em]">Authority path</div>
            <div className="mt-1 text-[11px] opacity-80">{authorityLabel} · {authorityScoreLabel}</div>
          </div>
          <div className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-[11px]">
            {queue.length ? `${completedQueue}/${queue.length} checks recorded` : "verify to build queue"}
          </div>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <AuthorityStep label="Visual candidate" done={Boolean(queue.length || hasVerifiedAuthority || measurements.length)} />
          <AuthorityStep label="Verifier run" done={hasVerifiedAuthority} />
          <AuthorityStep label="Bench readings" done={hasBenchEvidence} />
          <AuthorityStep label="Authority upgrade" done={queueClosed || authorityStatus === "authoritative_low_risk"} />
        </div>
      </div>

      <div className="mb-4 rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Measurement queue</div>
            <div className="mt-1 text-xs text-slate-400">
              {queue.length ? "Close these checks, then re-run verification for an authority upgrade." : "Verify board evidence to generate the first measurement queue."}
            </div>
          </div>
          <Button
            type="button"
            onClick={() => nextPending && onUsePrompt(nextPending.prompt)}
            disabled={!nextPending}
            size="sm"
            variant="outline"
            className="rounded-full border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15 disabled:opacity-50"
          >
            Use next pending
          </Button>
        </div>
        <div className="space-y-2">
          {queue.slice(0, 8).map((item) => (
            <div
              key={item.id}
              className={`rounded-lg border p-3 ${
                item.recorded
                  ? "border-emerald-300/25 bg-emerald-300/10"
                  : "border-white/10 bg-white/[0.02]"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                      item.recorded
                        ? "border-emerald-300/30 bg-emerald-300/10 text-emerald-100"
                        : "border-amber-300/30 bg-amber-300/10 text-amber-100"
                    }`}>
                      {item.recorded ? "recorded" : "pending"}
                    </span>
                    <span className="rounded-full border border-white/10 bg-black/20 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-300">
                      {item.type.replace(/_/g, " ")}
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{item.source}</span>
                  </div>
                  <div className="mt-2 text-xs leading-5 text-slate-200">{item.prompt}</div>
                  {item.matchedValue ? (
                    <div className="mt-1 text-[11px] text-emerald-100/80">Recorded value: {item.matchedValue}</div>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => onUsePrompt(item.prompt)}
                  className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-white/10"
                >
                  Use
                </button>
              </div>
            </div>
          ))}
          {!queue.length ? (
            <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] p-3 text-xs leading-5 text-slate-500">
              The queue appears after evidence verification or when the vision result includes required evidence.
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Type</span>
          <select
            value={draft.type}
            onChange={(event) => onDraftChange({ ...draft, type: event.target.value })}
            className="mt-1 w-full rounded-md border border-white/10 bg-black/30 px-2 py-2 text-xs text-white outline-none focus:border-cyan-300/60"
          >
            <option value="continuity">continuity</option>
            <option value="resistance">resistance</option>
            <option value="voltage">voltage</option>
            <option value="current">current</option>
            <option value="logic_level">logic level</option>
            <option value="functional">functional</option>
            <option value="thermal">thermal</option>
            <option value="measurement">measurement</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Target</span>
          <input
            value={draft.target}
            onChange={(event) => onDraftChange({ ...draft, target: event.target.value })}
            placeholder="5V rail to GND"
            className="mt-1 w-full rounded-md border border-white/10 bg-black/30 px-2 py-2 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
          />
        </label>
        <label className="block">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Value</span>
          <input
            value={draft.value}
            onChange={(event) => onDraftChange({ ...draft, value: event.target.value })}
            placeholder={measurementValuePlaceholder(draft.type)}
            className="mt-1 w-full rounded-md border border-white/10 bg-black/30 px-2 py-2 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
          />
        </label>
        <label className="block">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Unit</span>
          <input
            value={draft.unit}
            onChange={(event) => onDraftChange({ ...draft, unit: event.target.value })}
            placeholder="V, ohm, mA"
            className="mt-1 w-full rounded-md border border-white/10 bg-black/30 px-2 py-2 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
          />
        </label>
      </div>
      <label className="mt-2 block">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Notes</span>
        <textarea
          value={draft.notes}
          onChange={(event) => onDraftChange({ ...draft, notes: event.target.value })}
          rows={2}
          placeholder="current-limited bench supply, no short observed"
          className="mt-1 w-full resize-none rounded-md border border-white/10 bg-black/30 px-2 py-2 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
        />
      </label>
      <Button
        onClick={onAdd}
        disabled={adding || !sessionId}
        size="sm"
        variant="outline"
        className="mt-3 rounded-full border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15 disabled:opacity-50"
      >
        {adding ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
        Add measurement
      </Button>

      <div className="mt-4 space-y-1.5">
        {measurements.slice(-5).map((measurement) => (
          <div key={measurement.measurement_id ?? `${measurement.type}-${measurement.target}-${measurement.value}`} className="rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-xs leading-5 text-slate-300">
            <span className="font-medium text-white">{measurement.type ?? "measurement"}</span>
            {" · "}
            {measurement.target ?? "target"} = {String(measurement.value ?? "")} {measurement.unit ?? ""}
          </div>
        ))}
        {!measurements.length && <div className="text-xs text-slate-500">No bench readings attached.</div>}
      </div>
    </div>
  );
}

function UploadZone({ onPick, fileInputRef, onOpenCamera }: { onPick(file: File): void; fileInputRef: React.RefObject<HTMLInputElement | null>; onOpenCamera(): void }) {
  const [dragging, setDragging] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onPick(f);
      }}
      className={`relative rounded-3xl border-2 border-dashed p-16 text-center transition-colors ${
        dragging ? "border-cyan-400/60 bg-cyan-500/5" : "border-white/10 bg-white/[0.02] hover:border-white/20"
      }`}
    >
      <div className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-cyan-300">
        <ImageIcon className="h-6 w-6" />
      </div>
      <h2 className="text-xl font-semibold text-white">Drop a board photo, or pick one</h2>
      <p className="mt-2 text-sm text-slate-400">JPEG or PNG. Any angle is fine — we straighten later.</p>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button
          onClick={() => fileInputRef.current?.click()}
          size="lg"
          className="rounded-full bg-white text-slate-900 hover:bg-slate-100"
        >
          <Upload className="mr-2 h-4 w-4" />
          Choose image
        </Button>
        <Button
          onClick={onOpenCamera}
          size="lg"
          variant="outline"
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
        >
          <Camera className="mr-2 h-4 w-4" />
          Use camera
        </Button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        tabIndex={-1}
        suppressHydrationWarning
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = "";
        }}
      />

      <div className="mt-10 text-xs text-slate-500">
        New here? Try <Link href="/parts" className="text-cyan-300 hover:text-cyan-200 underline underline-offset-2">telling us what parts you already have</Link> instead.
      </div>
    </div>
  );
}
