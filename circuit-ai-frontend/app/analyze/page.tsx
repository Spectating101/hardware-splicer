'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  CircuitBoard,
  Eye,
  FileImage,
  KeyRound,
  LoaderCircle,
  PlayCircle,
  Settings2,
  Sparkles,
  Terminal,
  Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

type AnalyzeResult = Record<string, any> | null;

const backendOptions = [
  { value: 'ensemble', label: 'Ensemble', note: 'Use the full enhanced analysis path.' },
  { value: 'classical', label: 'Classical', note: 'Lighter analysis for local validation and comparison.' },
  { value: 'yolo', label: 'YOLO', note: 'Vision-heavy path when you want detector-centric behavior.' },
];

function metricValue(result: AnalyzeResult, keys: string[], fallback = 'N/A') {
  if (!result) return fallback;

  const candidates = [
    result,
    result.summary,
    result.metadata,
    result.results,
    result.analysis_summary,
    result.detection_summary,
  ].filter(Boolean);

  for (const candidate of candidates) {
    for (const key of keys) {
      const value = candidate?.[key];
      if (value !== undefined && value !== null && value !== '') return String(value);
    }
  }

  return fallback;
}

function detectionList(result: AnalyzeResult) {
  if (!result) return [];
  return (
    result.detections ||
    result.components ||
    result.results?.detections ||
    result.results?.components ||
    []
  ) as Array<Record<string, any>>;
}

export default function AnalyzePage() {
  usePageTitle('Analyze Workspace | Circuit.AI');
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [apiKey, setApiKey] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [backend, setBackend] = useState('ensemble');
  const [enableOcr, setEnableOcr] = useState(true);
  const [enableQuality, setEnableQuality] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalyzeResult>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedFile]);

  const detections = useMemo(() => detectionList(result), [result]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setResult(null);
    setErrorMessage(null);
  };

  const runAnalysis = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('backend', backend);
    formData.append('enable_ocr', String(enableOcr));
    formData.append('enable_quality_assessment', String(enableQuality));

    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${apiBaseUrl}/analyze`, {
        method: 'POST',
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined,
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis request failed (${response.status})`);
      }

      const payload = await response.json();
      setResult(payload);
    } catch (error) {
      console.error('Analyze route request failed', error);
      setErrorMessage(`Could not complete analysis against ${apiBaseUrl}/analyze. Confirm the backend is reachable and the auth mode matches the deployed service.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Analysis workspace"
          title="Run an actual PCB analysis without dropping back into a disconnected demo UI."
          description="This route is the bridge between the public product story and the heavier engineering surfaces. Upload a board image, choose the backend mode, and inspect the response shape the rest of the frontend should be built around."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/playground">
                  <Terminal className="mr-2 h-4 w-4" />
                  Open playground
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/docs">
                  <Workflow className="mr-2 h-4 w-4" />
                  Review endpoints
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Why this route exists</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <CircuitBoard className="h-4 w-4 text-slate-700" />
                  Frontend job
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Translate backend depth into an operable surface. The point is not a pretty upload widget. The point is making analysis behavior legible.
                </p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                The enhanced backend accepts uploads under <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700">file</code>. The UI now reflects that contract directly.
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[0.92fr_1.08fr]">
            <div className="space-y-6">
              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="text-2xl text-slate-950">Analysis controls</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Set the trust boundary first, then run the board through the target backend mode.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div>
                    <div className="mb-2 text-sm font-semibold text-slate-900">API key</div>
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder="Optional locally, required for protected deployments"
                      className="rounded-2xl border-slate-200 bg-white"
                    />
                  </div>

                  <div>
                    <div className="mb-2 text-sm font-semibold text-slate-900">Board image</div>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="flex w-full flex-col items-center justify-center rounded-[1.75rem] border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition-colors hover:border-slate-400 hover:bg-white"
                    >
                      <FileImage className="mb-4 h-10 w-10 text-slate-400" />
                      <div className="text-sm font-semibold text-slate-900">
                        {selectedFile ? selectedFile.name : 'Upload PCB image'}
                      </div>
                      <div className="mt-1 text-sm text-slate-500">
                        {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB selected` : 'PNG, JPG, or JPEG'}
                      </div>
                    </button>
                    <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <div className="mb-2 text-sm font-semibold text-slate-900">Backend mode</div>
                      <select
                        value={backend}
                        onChange={(event) => setBackend(event.target.value)}
                        className="h-10 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none"
                      >
                        {backendOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-sm leading-6 text-slate-500">
                        {backendOptions.find((option) => option.value === backend)?.note}
                      </p>
                    </div>

                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Settings2 className="h-4 w-4" />
                        Analysis options
                      </div>
                      <label className="flex items-center justify-between gap-3 text-sm text-slate-700">
                        <span>OCR enrichment</span>
                        <input type="checkbox" checked={enableOcr} onChange={() => setEnableOcr((value) => !value)} />
                      </label>
                      <label className="mt-3 flex items-center justify-between gap-3 text-sm text-slate-700">
                        <span>Quality assessment</span>
                        <input type="checkbox" checked={enableQuality} onChange={() => setEnableQuality((value) => !value)} />
                      </label>
                    </div>
                  </div>

                  <Button
                    onClick={runAnalysis}
                    disabled={!selectedFile || isAnalyzing}
                    className="w-full rounded-full bg-slate-900 text-white hover:bg-slate-800"
                  >
                    {isAnalyzing ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                    {isAnalyzing ? 'Running analysis' : 'Run PCB analysis'}
                  </Button>

                  {errorMessage ? (
                    <div className="rounded-[1.5rem] border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700">
                      {errorMessage}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_24px_65px_rgba(15,23,42,0.18)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-2xl text-white">
                    <Sparkles className="h-5 w-5 text-cyan-300" />
                    Workflow position
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-slate-300">
                  <p>Use this route when you want a richer operator-facing analysis surface than the playground, but you are still validating core backend behavior before CAD or fabrication workflows.</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link href="/components" className="rounded-[1.25rem] border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/10">
                      <div className="flex items-center gap-2 font-semibold text-white">
                        <Eye className="h-4 w-4" />
                        Component intelligence
                      </div>
                    </Link>
                    <Link href="/projects" className="rounded-[1.25rem] border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/10">
                      <div className="flex items-center gap-2 font-semibold text-white">
                        <KeyRound className="h-4 w-4" />
                        Project templates
                      </div>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card className="overflow-hidden rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="text-2xl text-slate-950">Board preview</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Keep the user anchored to the specific artifact being analyzed.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {previewUrl ? (
                    <img src={previewUrl} alt="PCB preview" className="w-full rounded-[1.5rem] border border-slate-200 object-cover" />
                  ) : (
                    <div className="flex min-h-[280px] items-center justify-center rounded-[1.5rem] border-2 border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
                      Upload an image to preview the board here.
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-3">
                <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Detections</CardDescription>
                    <CardTitle className="text-4xl text-slate-950">{detections.length}</CardTitle>
                  </CardHeader>
                </Card>
                <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Backend</CardDescription>
                    <CardTitle className="text-2xl text-slate-950">{metricValue(result, ['backend'])}</CardTitle>
                  </CardHeader>
                </Card>
                <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Quality</CardDescription>
                    <CardTitle className="text-2xl text-slate-950">{metricValue(result, ['detection_quality', 'quality', 'confidence'])}</CardTitle>
                  </CardHeader>
                </Card>
              </div>

              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                    <Brain className="h-5 w-5 text-slate-700" />
                    Findings
                  </CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Structure the response so the next route can keep context instead of starting over.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {result ? (
                    <>
                      {detections.length ? (
                        <div className="grid gap-3">
                          {detections.slice(0, 8).map((item, index) => (
                            <div key={`${item.class_name || item.name || 'detection'}-${index}`} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <div className="text-sm font-semibold text-slate-900">
                                    {item.class_name || item.name || item.type || 'Detected component'}
                                  </div>
                                  <p className="mt-1 text-sm leading-6 text-slate-600">
                                    {item.ocr_text || item.part_number || item.description || 'Structured detection output ready for enrichment.'}
                                  </p>
                                </div>
                                <div className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
                                  {item.confidence ? `${Math.round(Number(item.confidence) * 100)}%` : 'Detected'}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                          The current payload did not expose a simple detection list. The raw response is still shown below so the integration path remains inspectable.
                        </div>
                      )}

                      <div className="rounded-[1.75rem] border border-slate-200 bg-slate-950 p-5">
                        <pre className="overflow-x-auto text-sm leading-7 text-emerald-300">
                          <code>{JSON.stringify(result, null, 2)}</code>
                        </pre>
                      </div>
                    </>
                  ) : (
                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5 text-sm leading-6 text-slate-600">
                      Run an analysis to inspect returned detections, metadata, and any enriched summary fields.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
