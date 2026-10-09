'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { Download, LoaderCircle, Plus, RotateCcw, Trash2, Upload } from 'lucide-react';
import { AssemblyViewer, type AssemblyPlan } from '@/components/engineering/assembly-viewer';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload } from '@/lib/proxy-client';

type Part = {
  key: string;
  ref: string;
  kind: string;
  package: string;
  marking: string;
  x_mm: number;
  y_mm: number;
  width_mm: number | null;
  length_mm: number | null;
  rotation_deg: number;
  side: 'front' | 'back';
};
type Capture = { name: string; width_mm: number; length_mm: number; parts: Part[] };
type Options = {
  size_basis: string;
  kinds: Record<string, { prefix: string; packages: Record<string, { width_mm: number; length_mm: number; mounting: string }> }>;
};

const STORAGE_KEY = 'hs-donor-capture-v1';
const SNAP = 0.5;
const VERDICT_FILL: Record<string, string> = { keep: '#3fb950', test_first: '#f5c542', identify: '#4c8dff', optional: '#a0a7b4', skip: '#5b616c' };
const VERDICT_TEXT: Record<string, string> = { keep: 'Worth taking', test_first: 'Test first', identify: 'Read the marking', optional: 'Cheap to buy new', skip: 'Leave it' };

const EMPTY: Capture = { name: 'My donor board', width_mm: 60, length_mm: 40, parts: [] };

/** A made-up layout, to show the page working. The part names come from the project's own RC-car donor fixture; the places and packages are invented. */
const EXAMPLE: Capture = {
  name: 'Example: a dead RC car controller (made-up layout)',
  width_mm: 60,
  length_mm: 40,
  parts: [
    { key: 'e1', ref: 'U3', kind: 'ic', package: 'SOIC', marking: '', x_mm: 22, y_mm: 12, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e2', ref: 'U4', kind: 'ic', package: 'SOIC', marking: 'L9110S', x_mm: 34, y_mm: 12, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e3', ref: 'J_MOTOR_L', kind: 'connector', package: 'JST', marking: '', x_mm: 6, y_mm: 8, width_mm: null, length_mm: null, rotation_deg: 90, side: 'front' },
    { key: 'e4', ref: 'J_MOTOR_R', kind: 'connector', package: 'JST', marking: '', x_mm: 6, y_mm: 20, width_mm: null, length_mm: null, rotation_deg: 90, side: 'front' },
    { key: 'e5', ref: 'J_BATT', kind: 'connector', package: 'terminal block', marking: '', x_mm: 52, y_mm: 32, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e6', ref: 'C1', kind: 'capacitor', package: 'electrolytic can', marking: '470uF 16V', x_mm: 44, y_mm: 18, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e7', ref: 'F1', kind: 'mains or power part', package: 'fuse', marking: '', x_mm: 30, y_mm: 32, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e8', ref: 'D1', kind: 'diode or LED', package: 'diode SMD', marking: '', x_mm: 22, y_mm: 28, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
    { key: 'e9', ref: 'R1', kind: 'resistor', package: '0603', marking: '103', x_mm: 14, y_mm: 30, width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' },
  ],
};

const snap = (value: number) => Math.round(value / SNAP) * SNAP;
const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);

function sizeOf(part: Part, options: Options | null): { w: number; l: number } {
  const typical = options?.kinds[part.kind]?.packages[part.package];
  const w = part.width_mm ?? typical?.width_mm ?? 5;
  const l = part.length_mm ?? typical?.length_mm ?? 5;
  return part.rotation_deg === 90 || part.rotation_deg === 270 ? { w: l, l: w } : { w, l };
}

function toPayload(capture: Capture) {
  return {
    schema_version: 'hardware_splicer.donor_capture.v1',
    name: capture.name,
    board: { width_mm: capture.width_mm, length_mm: capture.length_mm },
    parts: capture.parts.map(({ key: _key, ...rest }) => rest),
  };
}

function looksLikeCapture(value: unknown): value is Capture {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return typeof v.name === 'string' && typeof v.width_mm === 'number' && typeof v.length_mm === 'number' && Array.isArray(v.parts)
    && v.parts.every((p) => p && typeof p === 'object' && typeof (p as Part).kind === 'string' && typeof (p as Part).package === 'string' && typeof (p as Part).x_mm === 'number' && typeof (p as Part).y_mm === 'number');
}

export default function DonorPage() {
  usePageTitle('Salvage a board');
  const [capture, setCapture] = useState<Capture>(EMPTY);
  const [options, setOptions] = useState<Options | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tool, setTool] = useState<{ kind: string; package: string }>({ kind: 'ic', package: 'SOIC' });
  const [plan, setPlan] = useState<(AssemblyPlan & { name?: string }) | null>(null);
  const [plannedFor, setPlannedFor] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [photo, setPhoto] = useState<string | null>(null);
  const [photoOpacity, setPhotoOpacity] = useState(0.6);
  const [loaded, setLoaded] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ key: string; dx: number; dy: number } | null>(null);
  const counter = useRef(1);

  const newKey = () => `p${Date.now().toString(36)}${counter.current++}`;

  useEffect(() => {
    fetch('/api/proxy/engineering/donors/options', { cache: 'no-store' })
      .then((r) => r.json())
      .then((body) => {
        if (body?.options) setOptions(body.options as Options);
        else setError(getProxyErrorMessage(body, 'The part choices could not be loaded.'));
      })
      .catch(() => setError('The part choices could not be loaded.'));
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (looksLikeCapture(saved)) setCapture(saved);
      }
    } catch { /* private window or blocked storage: start empty */ }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    const timer = window.setTimeout(() => {
      try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(capture)); } catch { /* not saved: fine */ }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [capture, loaded]);

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo); }, [photo]);

  const current = capture.parts.find((p) => p.key === selected) ?? null;
  const spec = useMemo(() => JSON.stringify(toPayload(capture)), [capture]);
  const stale = Boolean(plan) && plannedFor !== spec;
  const verdictOf = useMemo(() => new Map((plan?.parts ?? []).map((p) => [p.ref, p.salvage?.verdict ?? ''])), [plan]);

  const update = useCallback((key: string, patch: Partial<Part>) => {
    setCapture((c) => ({ ...c, parts: c.parts.map((p) => (p.key === key ? { ...p, ...patch } : p)) }));
  }, []);

  const addPart = useCallback((x: number, y: number) => {
    setCapture((c) => {
      const prefix = options?.kinds[tool.kind]?.prefix ?? 'Z';
      const used = new Set(c.parts.map((p) => p.ref.toLowerCase()));
      let n = 1;
      while (used.has(`${prefix}${n}`.toLowerCase())) n += 1;
      const key = newKey();
      setSelected(key);
      return { ...c, parts: [...c.parts, { key, ref: `${prefix}${n}`, kind: tool.kind, package: tool.package, marking: '', x_mm: clamp(snap(x), 0, c.width_mm), y_mm: clamp(snap(y), 0, c.length_mm), width_mm: null, length_mm: null, rotation_deg: 0, side: 'front' }] };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, tool]);

  const point = (event: { clientX: number; clientY: number }) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const matrix = svg.getScreenCTM();
    if (!matrix) return { x: 0, y: 0 };
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return { x: p.x, y: p.y };
  };

  const onBackgroundDown = (event: ReactPointerEvent<SVGElement>) => {
    const { x, y } = point(event);
    if (x < 0 || y < 0 || x > capture.width_mm || y > capture.length_mm) { setSelected(null); return; }
    addPart(x, y);
  };
  const onPartDown = (event: ReactPointerEvent<SVGElement>, part: Part) => {
    event.stopPropagation();
    setSelected(part.key);
    const { x, y } = point(event);
    drag.current = { key: part.key, dx: part.x_mm - x, dy: part.y_mm - y };
    (event.currentTarget.ownerSVGElement ?? svgRef.current)?.setPointerCapture?.(event.pointerId);
  };
  const onMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const { x, y } = point(event);
    setCapture((c) => ({ ...c, parts: c.parts.map((p) => (p.key === d.key ? { ...p, x_mm: clamp(snap(x + d.dx), 0, c.width_mm), y_mm: clamp(snap(y + d.dy), 0, c.length_mm) } : p)) }));
  };
  const onUp = () => { drag.current = null; };

  const remove = (key: string) => {
    setCapture((c) => ({ ...c, parts: c.parts.filter((p) => p.key !== key) }));
    setSelected((s) => (s === key ? null : s));
  };

  const onKey = (event: React.KeyboardEvent) => {
    if (!current || (event.target instanceof HTMLInputElement) || (event.target instanceof HTMLSelectElement) || (event.target instanceof HTMLTextAreaElement)) return;
    const step = event.shiftKey ? 5 : SNAP;
    const moves: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (moves[event.key]) {
      event.preventDefault();
      const [dx, dy] = moves[event.key];
      update(current.key, { x_mm: clamp(current.x_mm + dx, 0, capture.width_mm), y_mm: clamp(current.y_mm + dy, 0, capture.length_mm) });
    } else if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      remove(current.key);
    }
  };

  const planIt = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/proxy/engineering/donors/salvage-plan', { method: 'POST', headers: { 'content-type': 'application/json' }, body: spec, cache: 'no-store' });
      const body = await readJsonPayload<unknown>(response);
      if (!body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The plan could not be made.'));
      const made = (body as { plan?: AssemblyPlan }).plan;
      if (!made) throw new Error('The plan could not be made.');
      setPlan(made);
      setPlannedFor(spec);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The plan could not be made.');
    } finally {
      setBusy(false);
    }
  };

  const onPhoto = (file: File | null) => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      // Match the board's shape to the photo's, so what is drawn over it lines up.
      setCapture((c) => ({ ...c, length_mm: clamp(Math.round((c.width_mm * image.naturalHeight / image.naturalWidth) * 10) / 10, 5, 500) }));
    };
    image.src = url;
    setPhoto(url);
  };
  const download = () => {
    const blob = new Blob([JSON.stringify(toPayload(capture), null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${capture.name.replace(/[^A-Za-z0-9._-]+/g, '-').slice(0, 40) || 'donor-board'}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 2000);
  };
  const upload = async (file: File | null) => {
    if (!file) return;
    try {
      const text = await file.text();
      if (text.length > 400_000) throw new Error('too large');
      const data = JSON.parse(text);
      const parts = Array.isArray(data?.parts) ? data.parts.map((p: Part) => ({ ...p, key: newKey(), width_mm: p.width_mm ?? null, length_mm: p.length_mm ?? null, rotation_deg: p.rotation_deg ?? 0, side: p.side ?? 'front', marking: p.marking ?? '', ref: p.ref ?? '' })) : [];
      const next = { name: String(data?.name ?? 'Donor board'), width_mm: Number(data?.board?.width_mm ?? data?.width_mm), length_mm: Number(data?.board?.length_mm ?? data?.length_mm), parts };
      if (!looksLikeCapture(next) || !Number.isFinite(next.width_mm) || !Number.isFinite(next.length_mm)) throw new Error('bad shape');
      setCapture(next);
      setSelected(null);
      setPlan(null);
      setNotice(`Loaded ${parts.length} parts.`);
    } catch {
      setNotice('That file is not a board description this page can read.');
    }
  };

  const packages = options?.kinds[tool.kind]?.packages ?? {};
  const pad = 4;

  return (
    <main className="min-h-screen bg-[#0b0d12] px-4 pb-24 pt-6 text-stone-200" data-testid="donor-page" onKeyDown={onKey}>
      <div className="mx-auto max-w-7xl">
        <header className="mb-3">
          <h1 className="text-lg font-semibold text-stone-50">Salvage a board</h1>
          <p className="mt-0.5 max-w-3xl text-xs leading-5 text-stone-400">
            A board with no file? Describe it: its size, then where each part sits, what kind it is, and the marking printed on it. You get the same take-apart advice, in 3D.
            Everything here is what you tell it; a marking is what you read, not proof of what the part is.
          </p>
        </header>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="min-w-0 space-y-3" aria-label="Describe the board">
            <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <label className="flex items-center gap-1.5 text-stone-400">Place
                  <select data-testid="donor-kind" value={tool.kind} onChange={(e) => { const kind = e.target.value; setTool({ kind, package: Object.keys(options?.kinds[kind]?.packages ?? {})[0] ?? '' }); }} className="rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                    {Object.keys(options?.kinds ?? {}).map((k) => <option key={k} value={k}>{k}</option>)}
                  </select>
                </label>
                <select data-testid="donor-package" aria-label="Package" value={tool.package} onChange={(e) => setTool((t) => ({ ...t, package: e.target.value }))} className="rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                  {Object.keys(packages).map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <button type="button" data-testid="donor-add-centre" onClick={() => addPart(capture.width_mm / 2, capture.length_mm / 2)} className="inline-flex items-center gap-1 rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800"><Plus className="h-3.5 w-3.5" aria-hidden="true" />Add at the centre</button>
                <span className="text-stone-500">or click on the board</span>
                <span className="ml-auto flex items-center gap-1.5">
                  <label className="inline-flex cursor-pointer items-center gap-1 rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800"><Upload className="h-3.5 w-3.5" aria-hidden="true" />Photo underlay
                    <input data-testid="donor-photo" type="file" accept="image/*" className="sr-only" onChange={(e) => onPhoto(e.target.files?.[0] ?? null)} />
                  </label>
                  {photo ? <input aria-label="Photo opacity" type="range" min={0.1} max={1} step={0.05} value={photoOpacity} onChange={(e) => setPhotoOpacity(Number(e.target.value))} className="h-1 w-20 accent-amber-300" /> : null}
                </span>
              </div>
              {photo ? <p className="mt-1 text-[10px] text-stone-500">Your photo stays in this browser tab. It is not uploaded.</p> : null}
              <div
                className="mt-2 overflow-hidden rounded-lg border border-stone-800 bg-[#10141b] outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
                tabIndex={0}
                aria-label="Board, seen from above. Arrow keys move the selected part, Delete removes it."
              >
                <svg
                  ref={svgRef}
                  data-testid="donor-canvas"
                  viewBox={`${-pad} ${-pad} ${capture.width_mm + 2 * pad} ${capture.length_mm + 2 * pad}`}
                  className="block h-auto max-h-[480px] w-full touch-none select-none"
                  onPointerDown={onBackgroundDown}
                  onPointerMove={onMove}
                  onPointerUp={onUp}
                  onPointerCancel={onUp}
                >
                  <defs>
                    <pattern id="donor-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M 5 0 L 0 0 0 5" fill="none" stroke="#243042" strokeWidth="0.1" /></pattern>
                  </defs>
                  <rect x={0} y={0} width={capture.width_mm} height={capture.length_mm} fill="#17624a" fillOpacity={photo ? 0.15 : 0.55} stroke="#6fb89f" strokeWidth={0.3} />
                  {photo ? <image href={photo} x={0} y={0} width={capture.width_mm} height={capture.length_mm} preserveAspectRatio="none" opacity={photoOpacity} /> : null}
                  <rect x={0} y={0} width={capture.width_mm} height={capture.length_mm} fill="url(#donor-grid)" pointerEvents="none" />
                  {capture.parts.map((part) => {
                    const { w, l } = sizeOf(part, options);
                    const verdict = verdictOf.get(part.ref);
                    const fill = verdict ? VERDICT_FILL[verdict] ?? '#7b8aa0' : '#7b8aa0';
                    const isSelected = part.key === selected;
                    return (
                      <g key={part.key} data-testid={`donor-part-${part.ref}`} data-selected={isSelected ? '1' : '0'} onPointerDown={(e) => onPartDown(e, part)} style={{ cursor: 'grab' }}>
                        <rect x={part.x_mm - w / 2} y={part.y_mm - l / 2} width={w} height={l} fill={fill} fillOpacity={0.8} stroke={isSelected ? '#ffcf5a' : '#0b0d12'} strokeWidth={isSelected ? 0.5 : 0.2} rx={0.3} />
                        <text x={part.x_mm} y={part.y_mm} fontSize={Math.min(2.4, Math.max(1.1, w / (Math.max(part.ref.length, 2) * 0.62)))} textAnchor="middle" dominantBaseline="middle" fill="#0b0d12" fontWeight={700} pointerEvents="none">{part.ref}</text>
                      </g>
                    );
                  })}
                </svg>
              </div>
              <p className="mt-1.5 text-[10px] leading-4 text-stone-500">Top view. Part sizes are typical for the package: measure the real part and type the size to overwrite it. {options?.size_basis ?? ''}</p>
            </div>

            {error ? <p role="alert" data-testid="donor-error" className="rounded-md border border-red-500/40 bg-red-950/40 p-2 text-xs leading-5 text-red-100">{error}</p> : null}
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" data-testid="donor-plan" onClick={() => void planIt()} disabled={busy} className="inline-flex h-9 items-center gap-1.5 rounded-md bg-amber-300 px-4 text-xs font-semibold text-stone-950 hover:bg-amber-200 disabled:opacity-50">
                {busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}Plan the take-apart in 3D
              </button>
              {stale ? <span data-testid="donor-stale" className="text-xs text-amber-300">You changed the board since this plan was made.</span> : null}
              {notice ? <span data-testid="donor-notice" className="text-xs text-stone-400">{notice}</span> : null}
            </div>

            {plan ? (
              <section aria-label="Take-apart plan" className="overflow-hidden rounded-xl border border-stone-800" style={{ height: 'min(80vh, 760px)', minHeight: 560 }} data-testid="donor-viewer-frame">
                <AssemblyViewer plan={plan} />
              </section>
            ) : null}
          </section>

          <aside className="min-w-0 space-y-3" aria-label="Board and parts">
            <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4">
              <h2 className="text-sm font-semibold text-stone-100">The board</h2>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <label className="col-span-2 text-stone-400">Name
                  <input data-testid="donor-name" value={capture.name} maxLength={80} onChange={(e) => setCapture((c) => ({ ...c, name: e.target.value }))} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                </label>
                <label className="text-stone-400">Width, mm
                  <input data-testid="donor-width" type="number" min={5} max={500} step={0.5} value={capture.width_mm} onChange={(e) => setCapture((c) => ({ ...c, width_mm: clamp(Number(e.target.value) || 5, 5, 500) }))} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                </label>
                <label className="text-stone-400">Length, mm
                  <input data-testid="donor-length" type="number" min={5} max={500} step={0.5} value={capture.length_mm} onChange={(e) => setCapture((c) => ({ ...c, length_mm: clamp(Number(e.target.value) || 5, 5, 500) }))} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                </label>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
                <button type="button" data-testid="donor-example" onClick={() => { setCapture(structuredClone(EXAMPLE)); setSelected(null); setPlan(null); setNotice('Example loaded: the places and packages are made up.'); }} className="rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800">Load the example</button>
                <button type="button" data-testid="donor-reset" onClick={() => { setCapture(structuredClone(EMPTY)); setSelected(null); setPlan(null); setNotice(''); }} className="inline-flex items-center gap-1 rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800"><RotateCcw className="h-3 w-3" aria-hidden="true" />Start again</button>
                <button type="button" onClick={download} className="inline-flex items-center gap-1 rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800"><Download className="h-3 w-3" aria-hidden="true" />Save</button>
                <label className="inline-flex cursor-pointer items-center gap-1 rounded border border-stone-700 px-2 py-1 text-stone-200 hover:bg-stone-800"><Upload className="h-3 w-3" aria-hidden="true" />Open
                  <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => { void upload(e.target.files?.[0] ?? null); e.target.value = ''; }} />
                </label>
              </div>
              <p className="mt-2 text-[10px] leading-4 text-stone-500">Your work is kept in this browser as you go.</p>
            </section>

            <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="donor-selected">
              <h2 className="text-sm font-semibold text-stone-100">{current ? `Part ${current.ref}` : 'Selected part'}</h2>
              {current ? (
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <label className="text-stone-400">Label
                    <input data-testid="donor-ref" value={current.ref} maxLength={16} onChange={(e) => update(current.key, { ref: e.target.value })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                  </label>
                  <label className="text-stone-400">Kind
                    <select value={current.kind} onChange={(e) => update(current.key, { kind: e.target.value, package: Object.keys(options?.kinds[e.target.value]?.packages ?? {})[0] ?? '' })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                      {Object.keys(options?.kinds ?? {}).map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                  </label>
                  <label className="col-span-2 text-stone-400">Package
                    <select value={current.package} onChange={(e) => update(current.key, { package: e.target.value })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                      {Object.keys(options?.kinds[current.kind]?.packages ?? {}).map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </label>
                  <label className="col-span-2 text-stone-400">Marking printed on it
                    <input data-testid="donor-marking" value={current.marking} maxLength={40} placeholder="what you can read, or leave empty" onChange={(e) => update(current.key, { marking: e.target.value })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                  </label>
                  <label className="text-stone-400">Width, mm
                    <input type="number" min={0.5} max={120} step={0.1} value={current.width_mm ?? ''} placeholder={String(options?.kinds[current.kind]?.packages[current.package]?.width_mm ?? '')} onChange={(e) => update(current.key, { width_mm: e.target.value === '' ? null : Number(e.target.value) })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                  </label>
                  <label className="text-stone-400">Length, mm
                    <input type="number" min={0.5} max={120} step={0.1} value={current.length_mm ?? ''} placeholder={String(options?.kinds[current.kind]?.packages[current.package]?.length_mm ?? '')} onChange={(e) => update(current.key, { length_mm: e.target.value === '' ? null : Number(e.target.value) })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100" />
                  </label>
                  <label className="text-stone-400">Turned
                    <select value={current.rotation_deg} onChange={(e) => update(current.key, { rotation_deg: Number(e.target.value) })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                      {[0, 90, 180, 270].map((d) => <option key={d} value={d}>{d}°</option>)}
                    </select>
                  </label>
                  <label className="text-stone-400">Side
                    <select value={current.side} onChange={(e) => update(current.key, { side: e.target.value as 'front' | 'back' })} className="mt-0.5 w-full rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-stone-100">
                      <option value="front">front</option><option value="back">back</option>
                    </select>
                  </label>
                  <div className="col-span-2 flex items-center justify-between">
                    {current.marking ? <a href={`https://duckduckgo.com/?q=${encodeURIComponent(`${current.marking} datasheet`)}`} target="_blank" rel="noreferrer" className="text-sky-300 underline-offset-2 hover:underline">Search for its datasheet</a> : <span className="text-stone-500">Type its marking to search for a datasheet.</span>}
                    <button type="button" data-testid="donor-delete" onClick={() => remove(current.key)} className="inline-flex items-center gap-1 rounded border border-red-500/40 px-2 py-1 text-red-200 hover:bg-red-950/40"><Trash2 className="h-3 w-3" aria-hidden="true" />Remove</button>
                  </div>
                </div>
              ) : <p className="mt-2 text-xs leading-5 text-stone-500">Click a part on the board to edit it, drag it to move it.</p>}
            </section>

            <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="donor-parts-list">
              <h2 className="text-sm font-semibold text-stone-100">Parts ({capture.parts.length})</h2>
              {capture.parts.length === 0 ? <p className="mt-2 text-xs text-stone-500">None yet.</p> : (
                <ul className="mt-2 space-y-1 text-xs">
                  {capture.parts.map((part) => {
                    const verdict = verdictOf.get(part.ref);
                    return (
                      <li key={part.key}>
                        <button type="button" onClick={() => setSelected(part.key)} className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left hover:bg-stone-800 ${part.key === selected ? 'bg-stone-800' : ''}`}>
                          <span className="truncate"><span className="font-medium text-stone-100">{part.ref}</span> <span className="text-stone-500">{part.package}{part.marking ? ` · ${part.marking}` : ''}</span></span>
                          {verdict && !stale ? <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px]" style={{ background: `${VERDICT_FILL[verdict] ?? '#555'}33`, color: VERDICT_FILL[verdict] ?? '#ccc' }}>{VERDICT_TEXT[verdict] ?? verdict}</span> : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
