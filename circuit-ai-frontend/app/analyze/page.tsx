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
import { CopilotDock } from '@/components/copilot-dock';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
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
  const { setArtifactName, setAnalysisMode, setDetectionCount } = useStudioRuntime();

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
      setArtifactName(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    setArtifactName(selectedFile.name);
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedFile, setArtifactName]);

  const detections = useMemo(() => detectionList(result), [result]);

  useEffect(() => {
    setAnalysisMode(backend);
  }, [backend, setAnalysisMode]);

  useEffect(() => {
    setDetectionCount(result ? detections.length : null);
  }, [detections.length, result, setDetectionCount]);

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
      description="The board owns the center viewport, tooling stays docked, and detections stream into a bottom tray instead of turning into a report page."
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
                  className="editor-input h-auto border-0 px-4 py-3"
                />
              </div>

              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Artifact</div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="editor-dropzone flex w-full flex-col items-center justify-center px-4 py-6 text-center"
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
                  className="editor-select h-11 py-0 text-sm"
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

          <div className="editor-subpanel rounded-[1.5rem] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Settings2 className="h-4 w-4 text-cyan-300" />
              Analysis switches
            </div>
            <label className="flex items-center justify-between gap-3 py-2 text-sm text-slate-300">
              <span>OCR enrichment</span>
              <input className="editor-toggle" type="checkbox" checked={enableOcr} onChange={() => setEnableOcr((value) => !value)} />
            </label>
            <label className="flex items-center justify-between gap-3 py-2 text-sm text-slate-300">
              <span>Quality assessment</span>
              <input className="editor-toggle" type="checkbox" checked={enableQuality} onChange={() => setEnableQuality((value) => !value)} />
            </label>
          </div>

          <Button
            onClick={runAnalysis}
            disabled={!selectedFile || isAnalyzing}
            className="editor-button-primary w-full rounded-full"
          >
            {isAnalyzing ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            {isAnalyzing ? 'Running analysis' : 'Run analysis'}
          </Button>

          <div className="rounded-[1.5rem] border border-white/8 bg-[#08111f] p-4 text-sm leading-6 text-slate-300">
            Treat this as a live stage: load a board, lock a mode, then keep reading the same surface while the trays update around it.
          </div>
        </div>
      }
      main={
        <div className="grid h-full grid-rows-[44px_minmax(0,1fr)] bg-white/5">
          <div className="flex items-center justify-between border-b border-white/8 bg-[#08111e] px-4">
            <div className="flex items-center gap-2">
              {['Viewport', 'Annotate', 'Compare'].map((item, index) => (
                <button
                  key={item}
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              stage locked to active artifact
            </div>
          </div>

          <div className="min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(8,145,178,0.16),transparent_24%),linear-gradient(180deg,#0b1323_0%,#0b1627_100%)] p-3">
            <div className="relative flex h-full flex-col overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09111d] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <div className="pointer-events-none absolute right-4 top-16 z-10 hidden w-48 space-y-2 xl:block">
                {[
                  ['Detections', String(detections.length)],
                  ['Engine', metricValue(result, ['backend'])],
                  ['Confidence', metricValue(result, ['detection_quality', 'quality', 'confidence'])],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-[1rem] border border-white/10 bg-[#081423]/90 p-3 backdrop-blur">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                    <div className="mt-2 text-lg font-semibold text-white">{value}</div>
                  </div>
                ))}
              </div>

              <div className="pointer-events-none absolute bottom-4 left-4 z-10 hidden max-w-sm rounded-[1rem] border border-white/10 bg-[#081423]/88 p-3 text-sm leading-6 text-slate-300 backdrop-blur xl:block">
                Keep attention on the stage. Route jumps and detailed output belong in the side dock and lower console, not inside the viewport.
              </div>

              <div className="pointer-events-none absolute bottom-4 right-4 z-10 hidden items-center gap-2 xl:flex">
                <Link href="/components" className="pointer-events-auto rounded-full border border-white/10 bg-[#081423]/88 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 hover:text-white">
                  Component atlas
                </Link>
                <Link href="/projects" className="pointer-events-auto rounded-full border border-white/10 bg-[#081423]/88 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 hover:text-white">
                  Project board
                </Link>
              </div>

              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Viewport</div>
                  <div className="mt-1 text-sm font-semibold text-white">Board canvas</div>
                </div>
                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                  {selectedFile ? 'Artifact mounted' : 'Awaiting board'}
                </div>
              </div>

              <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden p-5">
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.026)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.026)_1px,transparent_1px)] bg-[size:44px_44px]" />
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.08),transparent_44%)]" />
                {previewUrl ? (
                  <div className="relative flex max-h-full max-w-full items-center justify-center">
                    <img
                      src={previewUrl}
                      alt="PCB preview"
                      className="max-h-[72vh] max-w-full rounded-[1.15rem] border border-white/12 object-contain shadow-[0_25px_60px_rgba(2,6,23,0.5)]"
                    />
                    <div className="pointer-events-none absolute left-[12%] top-[18%] rounded-full border border-cyan-300/30 bg-cyan-300/12 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-100">
                      OCR lane
                    </div>
                    <div className="pointer-events-none absolute right-[14%] top-[32%] rounded-full border border-amber-300/30 bg-amber-300/12 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100">
                      hot spot
                    </div>
                    <div className="pointer-events-none absolute bottom-[16%] left-[28%] rounded-full border border-emerald-300/30 bg-emerald-300/12 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-100">
                      salvage
                    </div>
                  </div>
                ) : (
                  <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden rounded-[1.15rem] border border-dashed border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.68),rgba(8,15,28,0.96))] text-center">
                    <div className="relative mb-8 flex h-36 w-56 items-center justify-center rounded-[1.4rem] border border-cyan-300/20 bg-cyan-300/5 shadow-[0_30px_60px_rgba(8,145,178,0.10)]">
                      <div className="absolute left-6 top-7 h-3 w-3 rounded-full bg-cyan-300" />
                      <div className="absolute right-8 top-10 h-3 w-3 rounded-full bg-orange-300" />
                      <div className="absolute left-10 bottom-9 h-3 w-3 rounded-full bg-emerald-300" />
                      <div className="absolute right-12 bottom-8 h-3 w-3 rounded-full bg-cyan-300" />
                      <div className="absolute left-12 top-9 h-px w-24 bg-cyan-300/40" />
                      <div className="absolute right-12 top-11 h-16 w-px bg-orange-300/35" />
                      <div className="absolute left-14 bottom-10 h-px w-28 bg-emerald-300/35" />
                      <FileImage className="h-12 w-12 text-cyan-200" />
                    </div>
                    <div className="relative text-base font-medium text-slate-100">Drop a board into the viewport</div>
                    <div className="relative mt-2 max-w-md text-sm leading-6 text-slate-400">
                      The active board stays centered while the side docks and console trays update around it.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      }
      bottom={
        <div className="grid h-full grid-rows-[40px_minmax(0,1fr)]">
          <div className="flex items-center gap-2 border-b border-white/8 bg-[#08111d] px-4">
            {['Detections', 'Console', 'Activity'].map((item, index) => (
              <button
                key={item}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
            {result ? (
              <div className="grid gap-3 xl:grid-cols-3">
                {detections.length ? (
                  detections.slice(0, 9).map((item, index) => (
                    <div key={`${item.class_name || item.name || 'detection'}-${index}`} className="rounded-[1.1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
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
                  <div className="rounded-[1.1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 text-sm leading-6 text-slate-400 xl:col-span-3">
                    The response did not expose a simple detection list. The raw response remains available in the inspector.
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-[1.1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 text-sm leading-6 text-slate-400">
                Run an analysis to populate the detection console without changing the current stage.
              </div>
            )}
          </div>
        </div>
      }
      right={
        <CopilotDock
          modeLabel="Analyze"
          objective="Use the agent to scan the current board, steer inspection, and decide what should become the next focused part or route."
          status={errorMessage ? 'Attention required' : isAnalyzing ? 'Running' : 'Ready'}
          messages={[
            {
              role: 'agent',
              body: selectedFile
                ? `The current board is loaded as ${selectedFile.name}. Ask for a targeted scan, a suspect region review, or a summary of what should move forward.`
                : 'Load a board into the stage, then ask the agent what it sees or what it should focus on first.',
            },
            {
              role: 'user',
              body: result
                ? `Show me what matters most in this run and tell me whether I should branch into parts or project planning next.`
                : 'Prepare the next inspection pass and keep the canvas centered while you work.',
            },
            errorMessage
              ? {
                  role: 'system',
                  body: errorMessage,
                }
              : {
                  role: 'agent',
                  body: result
                    ? `This run currently exposes ${detections.length} detections. The bottom console holds the raw detection feed while I keep the canvas stable.`
                    : 'The console below will fill in once the run completes. Use it as a trace, not as the primary reading surface.',
                },
          ]}
          prompts={[
            'Scan for power issues',
            'Focus on the most suspicious region',
            'Summarize likely components',
            'Prepare the parts atlas',
          ]}
          links={[
            { href: '/dashboard/keys', label: 'Key management' },
            { href: '/components', label: 'Open component atlas' },
            { href: '/projects', label: 'Open project board' },
          ]}
          footer={
            <div className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <CheckCircle2 className="h-4 w-4 text-cyan-300" />
                Raw trace
              </div>
              <div className="max-h-[148px] overflow-auto rounded-[0.85rem] border border-white/8 bg-[#08111d] p-3">
                <pre className="text-xs leading-6 text-slate-400">
                  <code>{result ? JSON.stringify(result, null, 2) : 'No analysis response yet.'}</code>
                </pre>
              </div>
            </div>
          }
        />
      }
    />
  );
}
