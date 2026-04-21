"use client";

import { Suspense, useCallback, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Camera, Image as ImageIcon, Loader2, RefreshCw, Scissors, Sparkles, Upload, Wrench } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { SafetyBanner } from "@/components/safety-banner";
import { IdentificationOverlay } from "@/components/scan/identification-overlay";
import { ModuleDetail } from "@/components/scan/module-detail";
import { CameraCapture } from "@/components/scan/camera-capture";
import { usePageTitle } from "@/components/use-page-title";
import { useWorkbenchStore } from "@/lib/workbench-store";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

interface IdentifyResponse {
  safety_level: SafetyLevel;
  explanation: string;
  components?: SalvageModule[];
  modules?: SalvageModule[];
  error?: string;
  fromCache?: boolean;
  model?: string;
}

type Mode = "identify" | "salvage";

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
  const [result, setResult] = useState<IdentifyResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  const onSelectFile = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please pick an image file (JPEG, PNG, etc.)");
      return;
    }
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(file);
    setImageUrl(URL.createObjectURL(file));
    setResult(null);
    setSelectedId(null);
    setError(null);
  }, [imageUrl]);

  const analyze = useCallback(async () => {
    if (!imageFile) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    fd.append("image", imageFile);

    const endpoint = mode === "salvage" ? "/api/jarvis/plan-salvage" : "/api/jarvis/identify";

    try {
      const resp = await fetch(endpoint, { method: "POST", body: fd });
      const json = await resp.json() as IdentifyResponse;
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
  }, [imageFile, mode, setSalvageModules, setSafetyLevel]);

  const reset = () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(null);
    setImageUrl(null);
    setResult(null);
    setSelectedId(null);
    setError(null);
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
                {result?.fromCache && (
                  <span className="ml-1 text-[11px] text-slate-500">
                    served from cache · {result.model}
                  </span>
                )}
              </div>

              {error && (
                <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-200">
                  {error}
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

              {selectedModule ? (
                <ModuleDetail
                  module={selectedModule}
                  onAddToInventory={() => {
                    addInventoryPart({
                      label: selectedModule.label,
                      kind: selectedModule.kind ?? "unknown",
                      source: "scan",
                      qty: 1,
                    });
                  }}
                  onStartBuild={() => {
                    // Phase 4 will route into /build with this module preloaded.
                    // For now, add to inventory and send to parts.
                    addInventoryPart({
                      label: selectedModule.label,
                      kind: selectedModule.kind ?? "unknown",
                      source: "scan",
                      qty: 1,
                    });
                    window.location.href = "/build";
                  }}
                />
              ) : modules.length > 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    {modules.length} {modules.length === 1 ? "block" : "blocks"} identified — click one on the image
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
