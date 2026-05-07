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

interface IdentifyResponse {
  safety_level: SafetyLevel;
  explanation: string;
  components?: SalvageModule[];
  modules?: SalvageModule[];
  error?: string;
  fromCache?: boolean;
  model?: string;
  source?: "local" | "jarvis";
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
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
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
    setError(null);
    setSaveMessage(null);
  }, [imageUrl]);

  const analyze = useCallback(async () => {
    if (!imageFile) return;
    setLoading(true);
    setError(null);
    setSaveMessage(null);
    setResult(null);

    const fd = new FormData();
    const endpoint = mode === "salvage" ? "/api/jarvis/plan-salvage" : "/api/proxy/analyze";
    if (mode === "salvage") {
      fd.append("image", imageFile);
    } else {
      fd.append("file", imageFile);
      fd.append("backend", "hybrid");
      fd.append("enable_ocr", "false");
      if (goldenFile) fd.append("golden_file", goldenFile);
      if (referenceCounts.trim()) fd.append("reference_counts", referenceCounts.trim());
      if (referenceTopology.trim()) fd.append("reference_topology", referenceTopology.trim());
      if (aoiProfile.trim()) fd.append("aoi_profile", aoiProfile.trim());
    }

    try {
      const resp = await fetch(endpoint, { method: "POST", body: fd });
      const rawJson = await resp.json() as IdentifyResponse | LocalAnalyzeResponse;
      const json = mode === "salvage" ? rawJson as IdentifyResponse : mapLocalAnalysis(rawJson as LocalAnalyzeResponse);
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

  const saveReviewCase = useCallback(async () => {
    if (!result) return;
    setSavingSession(true);
    setError(null);
    setSaveMessage(null);
    const productionAoi = result.productionAoi;
    const analysis = result.rawAnalysis ?? {
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
      setSaveMessage(`Saved review case ${payload.session?.session_id ?? ""}`.trim());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save review case.");
    } finally {
      setSavingSession(false);
    }
  }, [mode, result]);

  const reset = () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(null);
    setImageUrl(null);
    setGoldenFile(null);
    setImageSize(null);
    setResult(null);
    setSelectedId(null);
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
        hidden
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
