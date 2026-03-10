'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Brain,
  CheckCircle2,
  CircuitBoard,
  FileImage,
  KeyRound,
  LoaderCircle,
  PlayCircle,
  Settings2,
  Sparkles,
  Terminal,
  Upload,
  Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StudioShell } from '@/components/studio-shell';
import { usePageTitle } from '@/components/use-page-title';

type AnalyzeResult = Record<string, any> | null;

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/cad', label: 'CAD' },
];

const backendOptions = [
  { value: 'ensemble', label: 'Ensemble' },
  { value: 'classical', label: 'Classical' },
  { value: 'yolo', label: 'YOLO' },
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

function panelTitle(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
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
      setErrorMessage(`Could not complete analysis against ${apiBaseUrl}/analyze. Confirm the target is reachable and try again.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <StudioShell
      eyebrow="Workbench"
      title="Analyze a board inside a real studio layout."
      description="Controls stay on the left, the board stays in the middle, and findings stay docked instead of dropping into a page-length report."
      status={selectedFile ? `Active artifact: ${selectedFile.name}` : 'No artifact loaded'}
      activeHref="/analyze"
      navItems={navItems}
      actions={
        <>
          <Button asChild className="rounded-full bg-white text-slate-950 hover:bg-slate-100">
            <Link href="/playground">
              <Terminal className="mr-2 h-4 w-4" />
              Playground
            </Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/docs">
              <Workflow className="mr-2 h-4 w-4" />
              Docs
            </Link>
          </Button>
        </>
      }
      left={
        <div className="space-y-5">
          <div>
            {panelTitle('Session', 'Run controls')}
            <div className="space-y-3">
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Access key</div>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Paste key if required"
                  className="rounded-2xl border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                />
              </div>

              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Artifact</div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-white/15 bg-white/[0.03] px-4 py-6 text-center transition-colors hover:border-cyan-300/40 hover:bg-white/[0.06]"
                >
                  <Upload className="mb-3 h-7 w-7 text-cyan-200" />
                  <div className="text-sm font-medium text-white">{selectedFile ? selectedFile.name : 'Load board image'}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : 'PNG, JPG, JPEG'}
                  </div>
                </button>
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
              </div>

              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Mode</div>
                <select
                  value={backend}
                  onChange={(event) => setBackend(event.target.value)}
                  className="h-11 w-full rounded-2xl border border-white/10 bg-white/5 px-4 text-sm text-white outline-none"
                >
                  {backendOptions.map((option) => (
                    <option key={option.value} value={option.value} className="bg-slate-900">
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-cyan-400/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Settings2 className="h-4 w-4 text-cyan-300" />
              Analysis switches
            </div>
            <label className="flex items-center justify-between gap-3 py-2 text-sm text-slate-300">
              <span>OCR enrichment</span>
              <input type="checkbox" checked={enableOcr} onChange={() => setEnableOcr((value) => !value)} />
            </label>
            <label className="flex items-center justify-between gap-3 py-2 text-sm text-slate-300">
              <span>Quality assessment</span>
              <input type="checkbox" checked={enableQuality} onChange={() => setEnableQuality((value) => !value)} />
            </label>
          </div>

          <Button
            onClick={runAnalysis}
            disabled={!selectedFile || isAnalyzing}
            className="w-full rounded-full bg-cyan-300 text-slate-950 hover:bg-cyan-200"
          >
            {isAnalyzing ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            {isAnalyzing ? 'Running analysis' : 'Run analysis'}
          </Button>

          <div className="rounded-[1.5rem] border border-white/8 bg-[#08111f] p-4 text-sm leading-6 text-slate-300">
            This route is meant to feel like a workstation: controls on the rail, artifact in the center, findings in docks.
          </div>
        </div>
      }
      main={
        <div className="grid h-full gap-px bg-white/5 lg:grid-rows-[minmax(0,1fr)_220px]">
          <div className="grid min-h-0 gap-px lg:grid-cols-[minmax(0,1fr)_240px]">
            <div className="relative min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.16),transparent_24%),linear-gradient(180deg,#0b1323_0%,#0f1a30_100%)] p-4">
              <div className="flex h-full flex-col rounded-[1.5rem] border border-white/10 bg-[#0a1220] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Canvas</div>
                    <div className="mt-1 text-sm font-semibold text-white">Active board</div>
                  </div>
                  <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                    {selectedFile ? 'Loaded' : 'Waiting for upload'}
                  </div>
                </div>
                <div className="flex min-h-0 flex-1 items-center justify-center p-4">
                  {previewUrl ? (
                    <img src={previewUrl} alt="PCB preview" className="max-h-full rounded-[1.25rem] border border-white/10 object-contain shadow-[0_20px_45px_rgba(2,6,23,0.35)]" />
                  ) : (
                    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden rounded-[1.25rem] border border-dashed border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.7),rgba(8,15,28,0.96))] text-center">
                      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:42px_42px]" />
                      <div className="relative mb-8 flex h-36 w-56 items-center justify-center rounded-[1.5rem] border border-cyan-300/20 bg-cyan-300/5 shadow-[0_30px_60px_rgba(8,145,178,0.10)]">
                        <div className="absolute left-6 top-7 h-3 w-3 rounded-full bg-cyan-300" />
                        <div className="absolute right-8 top-10 h-3 w-3 rounded-full bg-orange-300" />
                        <div className="absolute left-10 bottom-9 h-3 w-3 rounded-full bg-emerald-300" />
                        <div className="absolute right-12 bottom-8 h-3 w-3 rounded-full bg-cyan-300" />
                        <div className="absolute left-12 top-9 h-px w-24 bg-cyan-300/40" />
                        <div className="absolute right-12 top-11 h-16 w-px bg-orange-300/35" />
                        <div className="absolute left-14 bottom-10 h-px w-28 bg-emerald-300/35" />
                        <FileImage className="h-12 w-12 text-cyan-200" />
                      </div>
                      <div className="relative text-base font-medium text-slate-100">Drop a board into the canvas</div>
                      <div className="relative mt-2 max-w-md text-sm leading-6 text-slate-400">
                        The artifact stays central while controls and findings remain docked around it.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="min-h-0 overflow-y-auto bg-[#08101d] p-4">
              <div className="space-y-4">
                <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Telemetry</div>
                  <div className="mt-3 grid gap-3">
                    {[
                      ['Detections', String(detections.length)],
                      ['Backend', metricValue(result, ['backend'])],
                      ['Quality', metricValue(result, ['detection_quality', 'quality', 'confidence'])],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                        <div className="mt-2 text-lg font-semibold text-white">{value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Sparkles className="h-4 w-4 text-cyan-300" />
                    Next surface
                  </div>
                  <div className="mt-3 space-y-2">
                    <Link href="/components" className="block rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
                      Component intelligence
                    </Link>
                    <Link href="/projects" className="block rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
                      Project orchestration
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Brain className="h-4 w-4 text-cyan-300" />
              Findings tray
            </div>
            {result ? (
              <div className="grid gap-3 xl:grid-cols-2">
                {detections.length ? (
                  detections.slice(0, 8).map((item, index) => (
                    <div key={`${item.class_name || item.name || 'detection'}-${index}`} className="rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-white">
                            {item.class_name || item.name || item.type || 'Detected component'}
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-400">
                            {item.ocr_text || item.part_number || item.description || 'Structured detection ready for enrichment.'}
                          </p>
                        </div>
                        <div className="rounded-full border border-white/10 bg-[#07111f] px-3 py-1 text-xs text-slate-300">
                          {item.confidence ? `${Math.round(Number(item.confidence) * 100)}%` : 'Detected'}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 text-sm text-slate-400 xl:col-span-2">
                    The response did not expose a simple detection list. The raw response remains available in the inspector.
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 text-sm leading-6 text-slate-400">
                Run an analysis to populate the findings tray without leaving the current workspace.
              </div>
            )}
          </div>
        </div>
      }
      right={
        <div className="space-y-4">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelTitle('Inspector', 'Session summary')}
            <div className="space-y-3 text-sm text-slate-300">
              <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Target</div>
                <div className="mt-2 font-medium text-white">{apiBaseUrl}</div>
              </div>
              <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Artifact state</div>
                <div className="mt-2 font-medium text-white">{selectedFile ? 'Artifact mounted' : 'No artifact yet'}</div>
              </div>
            </div>
          </div>

          {errorMessage ? (
            <div className="rounded-[1.5rem] border border-rose-400/20 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
              {errorMessage}
            </div>
          ) : (
            <div className="rounded-[1.5rem] border border-emerald-400/20 bg-emerald-500/10 p-4 text-sm leading-6 text-emerald-100">
              Keep the workspace stable: the board stays central and the findings tray updates in place instead of forcing another page jump.
            </div>
          )}

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <CheckCircle2 className="h-4 w-4 text-cyan-300" />
              Raw response
            </div>
            <div className="max-h-[320px] overflow-auto rounded-[1rem] border border-white/8 bg-[#08111d] p-3">
              <pre className="text-xs leading-6 text-slate-400">
                <code>{result ? JSON.stringify(result, null, 2) : 'No analysis response yet.'}</code>
              </pre>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <KeyRound className="h-4 w-4 text-cyan-300" />
              Route shortcuts
            </div>
            <div className="space-y-2">
              {[
                ['/dashboard/keys', 'Key management'],
                ['/components', 'Component intelligence'],
                ['/projects', 'Project planning'],
              ].map(([href, label]) => (
                <Link key={href} href={href} className="block rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      }
    />
  );
}
