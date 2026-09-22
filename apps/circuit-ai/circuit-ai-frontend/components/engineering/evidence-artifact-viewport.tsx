'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CircuitBoard, LoaderCircle } from 'lucide-react';

type JsonRecord = Record<string, unknown>;
export type EvidenceBuildFile = { name?: string; relative?: string; kind?: string };
type BuildFilesResponse = { ok?: boolean; files?: EvidenceBuildFile[] };
type BuildContentResponse = { ok?: boolean; content?: string };

type PreferredArtifactKind = 'schematic' | 'pcb';

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

export function deriveEvidenceBuildDir(snapshot: JsonRecord | null, session: JsonRecord | null) {
  if (!snapshot) return '';
  const projectPackage = record(snapshot.projectPackage || snapshot.project_package);
  const compose = record(snapshot.composeResult || snapshot.compose_result);
  const sessionPackage = record(session?.projectPackage || session?.project_package);
  const direct = firstString(
    snapshot.buildDir,
    snapshot.build_dir,
    projectPackage.build_dir,
    compose.out_dir,
    compose.build_dir,
    session?.buildDir,
    session?.build_dir,
    sessionPackage.build_dir,
  );
  if (direct) return direct;

  const actions = rows(session?.actions).slice().reverse();
  for (const action of actions) {
    const result = record(action.tool_result || action.result || action.payload);
    const nested = record(result.result || result.payload || result.project_package);
    const candidate = firstString(
      action.build_dir,
      action.out_dir,
      result.build_dir,
      result.out_dir,
      nested.build_dir,
      nested.out_dir,
    );
    if (candidate) return candidate;
  }
  return '';
}

function useKiCanvasScript() {
  const [ready, setReady] = useState(() => (
    typeof customElements !== 'undefined' && Boolean(customElements.get('kicanvas-embed'))
  ));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (ready) return;
    const existing = document.querySelector('script[data-kicanvas-vnext="1"]');
    if (existing) {
      const onLoad = () => setReady(true);
      const onError = () => setFailed(true);
      existing.addEventListener('load', onLoad, { once: true });
      existing.addEventListener('error', onError, { once: true });
      return () => {
        existing.removeEventListener('load', onLoad);
        existing.removeEventListener('error', onError);
      };
    }
    const script = document.createElement('script');
    script.type = 'module';
    script.src = '/kicanvas/kicanvas.js';
    script.dataset.kicanvasVnext = '1';
    script.onload = () => setReady(true);
    script.onerror = () => setFailed(true);
    document.head.appendChild(script);
  }, [ready]);

  return { ready, failed };
}

export function EvidenceArtifactViewport({
  buildDir,
  overlayFinding = '',
  compact = false,
  preferredKind = 'schematic',
}: {
  buildDir: string;
  overlayFinding?: string;
  compact?: boolean;
  preferredKind?: PreferredArtifactKind;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const { ready, failed: viewerFailed } = useKiCanvasScript();
  const [files, setFiles] = useState<EvidenceBuildFile[]>([]);
  const [activeRelative, setActiveRelative] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!buildDir) {
      setFiles([]);
      setActiveRelative('');
      setContent('');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetch('/api/proxy/hardware-splicer/build-files/list', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ build_dir: buildDir }),
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json() as BuildFilesResponse;
        if (!response.ok) throw new Error('Build artifact list is unavailable.');
        return payload;
      })
      .then((payload) => {
        if (cancelled) return;
        const nextFiles = payload.files || [];
        setFiles(nextFiles);
        const preferred = nextFiles.find((file) => file.kind === preferredKind)
          || nextFiles.find((file) => file.kind === (preferredKind === 'schematic' ? 'pcb' : 'schematic'))
          || nextFiles[0];
        setActiveRelative(preferred?.relative || '');
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Build artifact list is unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [buildDir, preferredKind]);

  useEffect(() => {
    if (!buildDir || !activeRelative) {
      setContent('');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetch('/api/proxy/hardware-splicer/build-files/content', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ build_dir: buildDir, relative: activeRelative }),
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json() as BuildContentResponse;
        if (!response.ok) throw new Error('Artifact content is unavailable.');
        return payload;
      })
      .then((payload) => {
        if (!cancelled) setContent(payload.content || '');
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Artifact content is unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeRelative, buildDir]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !ready || !content) return;
    host.replaceChildren();
    const embed = document.createElement('kicanvas-embed');
    embed.setAttribute('controls', 'basic');
    embed.setAttribute('controlslist', 'nodownload nooverlay');
    const source = document.createElement('kicanvas-source');
    source.textContent = content;
    embed.appendChild(source);
    host.appendChild(embed);
  }, [content, ready]);

  const visibleFiles = files.filter((file) => file.kind === 'schematic' || file.kind === 'pcb');
  const minHeight = compact ? 'min-h-[520px]' : 'min-h-[650px]';

  return (
    <div className={`flex h-full ${minHeight} flex-col bg-white`}>
      <div className="flex min-h-11 items-center justify-between gap-3 border-b border-stone-200 px-3">
        <div className="flex items-center gap-1">
          {visibleFiles.map((file) => {
            const active = file.relative === activeRelative;
            return (
              <button
                key={file.relative || file.name}
                type="button"
                onClick={() => setActiveRelative(file.relative || '')}
                className={`border-b-2 px-3 py-2.5 text-xs font-medium ${active ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
              >
                {file.kind === 'schematic' ? 'Schematic' : file.kind === 'pcb' ? 'PCB' : file.name}
              </button>
            );
          })}
          {!visibleFiles.length ? <span className="px-3 text-xs text-stone-500">Artifact</span> : null}
        </div>
        <span className="max-w-[45%] truncate font-mono text-[10px] text-stone-400">{activeRelative || 'no KiCad artifact attached'}</span>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[#fbfbfa]">
        {loading ? <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/70"><LoaderCircle className="h-5 w-5 animate-spin text-stone-500" /></div> : null}
        {!buildDir || error || viewerFailed || (!content && !loading) ? (
          <div className={`flex h-full ${compact ? 'min-h-[470px]' : 'min-h-[600px]'} items-center justify-center p-8`}>
            <div className="max-w-sm text-center">
              <CircuitBoard className="mx-auto h-9 w-9 text-stone-300" />
              <div className="mt-3 text-sm font-medium text-stone-800">{buildDir ? 'KiCad preview unavailable' : 'No build artifact attached'}</div>
              <div className="mt-1 text-xs leading-5 text-stone-500">{error || (viewerFailed ? 'The bundled KiCanvas viewer failed to load.' : 'The current project snapshot does not expose a build directory yet.')}</div>
            </div>
          </div>
        ) : (
          <div ref={hostRef} className={`${compact ? 'min-h-[470px]' : 'min-h-[600px]'} h-full w-full [&>kicanvas-embed]:block [&>kicanvas-embed]:h-full [&>kicanvas-embed]:w-full`} />
        )}
        {overlayFinding ? (
          <div className="absolute left-4 top-4 z-10 max-w-[17rem] rounded-md border border-red-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
            <div className="flex gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-600 text-white"><AlertTriangle className="h-3 w-3" /></span>
              <div>
                <div className="text-[11px] font-semibold text-red-800">Review required</div>
                <div className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-stone-700">{overlayFinding}</div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}