'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CircuitBoard, LoaderCircle, Pencil } from 'lucide-react';
import { EditDock } from '@/components/engineering/edit-dock';
import { useRoutingCapability, type Candidate, type ProposalInput } from '@/lib/project-candidates';
import { Model3DViewer } from '@/components/engineering/model3d-viewer';
import { ViewerOverlay, type PlacedPin, type ViewerHighlight, type ViewerPin } from '@/components/engineering/viewer-overlay';

export type { PlacedPin, ViewerHighlight, ViewerPin } from '@/components/engineering/viewer-overlay';
export type ActiveArtifact = { relative: string; kind: string };
/** A proposal's file shown in place of the retained one. It is a preview only and never replaces what is stored. */
export type ProposalPreview = { candidateId: string; kind: 'schematic' | 'pcb'; text: string };

type JsonRecord = Record<string, unknown>;
export type EvidenceBuildFile = { name?: string; relative?: string; kind?: string };
type BuildFilesResponse = { ok?: boolean; files?: EvidenceBuildFile[] };
type BuildContentResponse = { ok?: boolean; content?: string };
type PreferredArtifactKind = 'schematic' | 'pcb';
type KiCanvasBoardViewer = { zoom_to_board?: () => void; draw?: () => void };
type KiCanvasBoardApp = HTMLElement & { viewer?: KiCanvasBoardViewer };

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

function focusKiCanvasBoard(embed: HTMLElement) {
  let cancelled = false;
  let attempts = 0;
  let frame = 0;

  const tryFocus = () => {
    if (cancelled) return;
    attempts += 1;
    try {
      const boardApp = embed.shadowRoot?.querySelector('kc-board-app') as KiCanvasBoardApp | null;
      const viewer = boardApp?.viewer;
      if (viewer?.zoom_to_board) {
        viewer.zoom_to_board();
        viewer.draw?.();
        embed.setAttribute('data-board-fit', 'applied');
        return;
      }
    } catch {
      // KiCanvas may have rendered kc-board-app before its viewer is initialized.
    }

    if (attempts < 180) {
      frame = window.requestAnimationFrame(tryFocus);
    } else {
      embed.setAttribute('data-board-fit', 'unavailable');
    }
  };

  frame = window.requestAnimationFrame(tryFocus);
  return () => {
    cancelled = true;
    window.cancelAnimationFrame(frame);
  };
}

// KiCanvas initialises asynchronously and adds resources to itself as it goes. An embed removed before it finishes throws
// an uncaught error from inside the library, so a replaced embed is hidden and removed only once it has loaded.
const RETIRE_AFTER_LOAD_MS = 300;
const RETIRE_GIVE_UP_MS = 15000;
const SWITCH_SETTLE_MS = 120;

function retireEmbed(embed: HTMLElement) {
  embed.setAttribute('data-retired', '');
  embed.style.display = 'none';
  const remove = () => embed.remove();
  if (embed.dataset.loaded === '1') {
    window.setTimeout(remove, RETIRE_AFTER_LOAD_MS);
    return;
  }
  embed.addEventListener('kicanvas:load', () => window.setTimeout(remove, RETIRE_AFTER_LOAD_MS), { once: true });
  window.setTimeout(remove, RETIRE_GIVE_UP_MS);
}

export function EvidenceArtifactViewport({
  buildDir,
  overlayFinding = '',
  compact = false,
  preferredKind = 'schematic',
  pins,
  highlights,
  placing,
  onPlace,
  onCancelPlace,
  onActiveArtifact,
  focusHighlightId,
  model3d,
  proposing,
  preview,
}: {
  buildDir: string;
  overlayFinding?: string;
  compact?: boolean;
  preferredKind?: PreferredArtifactKind;
  pins?: ViewerPin[];
  highlights?: ViewerHighlight[];
  placing?: boolean;
  onPlace?: (pin: PlacedPin) => void;
  onCancelPlace?: () => void;
  onActiveArtifact?: (artifact: ActiveArtifact | null) => void;
  focusHighlightId?: string | null;
  /** When set, a 3D tab is offered for this project revision. */
  model3d?: { projectId: string; revision: number | null };
  /** When set, the viewer offers Edit, which drafts changes and sends them as a proposal for review. */
  proposing?: { projectId: string; onPropose: (kind: 'schematic' | 'pcb', input: ProposalInput, note: string) => Promise<Candidate>; onProposed: (candidate: Candidate) => void };
  preview?: ProposalPreview | null;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const { ready, failed: viewerFailed } = useKiCanvasScript();
  const [files, setFiles] = useState<EvidenceBuildFile[]>([]);
  const [activeRelative, setActiveRelative] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [show3d, setShow3d] = useState(false);
  const [editing, setEditing] = useState(false);
  const activeKind = files.find((file) => file.relative === activeRelative)?.kind;
  const previewing = Boolean(preview && preview.kind === activeKind);
  const routing = useRoutingCapability(proposing?.projectId || '', Boolean(proposing) && editing && activeKind === 'pcb');
  const shownContent = previewing && preview ? preview.text : content;

  useEffect(() => {
    onActiveArtifact?.(activeRelative && activeKind ? { relative: activeRelative, kind: activeKind } : null);
    // Report only when the artifact actually changes, not when the caller re-creates its callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRelative, activeKind]);

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
    if (!host || !ready || !shownContent) return;
    let embed: HTMLElement | null = null;
    let stopFocus: (() => void) | undefined;

    const mount = () => {
      host.querySelectorAll('kicanvas-embed:not([data-retired])').forEach((stray) => retireEmbed(stray as HTMLElement));
      const created = document.createElement('kicanvas-embed');
      embed = created;
      created.addEventListener('kicanvas:load', () => { created.dataset.loaded = '1'; });
      created.setAttribute('controls', 'basic');
      created.setAttribute('controlslist', 'nodownload nooverlay');
      const source = document.createElement('kicanvas-source');
      source.textContent = shownContent;
      created.appendChild(source);
      host.appendChild(created);

      if (activeKind === 'pcb') {
        // The vendored KiCanvas declares an embed `zoom` attribute but does not currently
        // forward it into kc-board-app. Its BoardViewer does expose zoom_to_board(), which
        // fits the camera to Edge.Cuts. Use that real viewer API after initialization.
        created.setAttribute('zoom', 'objects');
        stopFocus = focusKiCanvasBoard(created);
      }
    };

    // Opening the first file mounts at once. Switching waits a beat, so flipping between files faster than KiCanvas can
    // load them only ever loads the last one instead of stacking up a heavy viewer for each click.
    const switching = Boolean(host.querySelector('kicanvas-embed'));
    const timer = window.setTimeout(mount, switching ? SWITCH_SETTLE_MS : 0);

    return () => {
      window.clearTimeout(timer);
      stopFocus?.();
      if (!embed) return;
      // KiCanvas queues a draw on the next animation frame. If this embed is replaced first, that queued draw runs
      // against a disposed renderer and throws. Silence this viewer's draws before it goes away.
      try {
        const app = embed.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { on_draw?: () => void } }) | null;
        if (app?.viewer) app.viewer.on_draw = () => undefined;
      } catch {
        // The viewer may not have initialised yet; there is then nothing queued.
      }
      retireEmbed(embed);
    };
  }, [activeKind, shownContent, ready]);

  // Previewing a proposal shows the file it changed.
  useEffect(() => {
    if (!preview) return;
    const target = files.find((file) => file.kind === preview.kind);
    if (target?.relative) { setShow3d(false); setActiveRelative(target.relative); }
    // Only when a different proposal is chosen, not on every file-list refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.candidateId]);

  useEffect(() => {
    if (show3d || preview) setEditing(false);
  }, [show3d, preview]);

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
                onClick={() => { setShow3d(false); setActiveRelative(file.relative || ''); }}
                className={`border-b-2 px-3 py-2.5 text-xs font-medium ${active && !show3d ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
              >
                {file.kind === 'schematic' ? 'Schematic' : file.kind === 'pcb' ? 'PCB' : file.name}
              </button>
            );
          })}
          {model3d && model3d.revision ? (
            <button
              type="button"
              onClick={() => setShow3d(true)}
              aria-pressed={show3d}
              className={`border-b-2 px-3 py-2.5 text-xs font-medium ${show3d ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
            >
              3D
            </button>
          ) : null}
          {!visibleFiles.length && !model3d ? <span className="px-3 text-xs text-stone-500">Artifact</span> : null}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          {proposing && !show3d && !preview && (activeKind === 'schematic' || activeKind === 'pcb') ? (
            <button
              type="button"
              onClick={() => setEditing((value) => !value)}
              aria-pressed={editing}
              className={`inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border px-2.5 text-[11px] font-medium ${editing ? 'border-stone-900 bg-stone-900 text-white' : 'border-stone-300 text-stone-700 hover:bg-stone-50'}`}
              title="Select a part and propose a change. The proposal is held for review."
            >
              <Pencil className="h-3 w-3" aria-hidden="true" />Edit
            </button>
          ) : null}
          <span className={`shrink-0 rounded border px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] ${previewing ? 'border-amber-300 bg-amber-50 text-amber-900' : editing ? 'border-stone-900 text-stone-900' : 'border-stone-200 bg-stone-50 text-stone-500'}`}>{previewing ? 'Proposal preview · not applied' : editing ? 'Drafting a proposal' : 'Read-only review'}</span>
          <span className="max-w-[20rem] truncate font-mono text-[10px] text-stone-400">{show3d ? 'rendered from the retained PCB' : activeRelative || 'no KiCad artifact attached'}</span>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[#fbfbfa]">
        {show3d && model3d && model3d.revision ? <Model3DViewer projectId={model3d.projectId} revision={model3d.revision} /> : null}
        {show3d ? null : loading ? <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/70"><LoaderCircle className="h-5 w-5 animate-spin text-stone-500" /></div> : null}
        <div className={show3d ? 'hidden' : 'contents'}>
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
        {shownContent ? (
          <ViewerOverlay
            hostRef={hostRef}
            activeRelative={activeRelative}
            activeKind={activeKind || ''}
            pins={pins}
            highlights={highlights}
            placing={placing}
            onPlace={onPlace}
            onCancelPlace={onCancelPlace}
            focusId={focusHighlightId}
          />
        ) : null}
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
        {editing && proposing && (activeKind === 'schematic' || activeKind === 'pcb') ? (
          <EditDock
            hostRef={hostRef}
            kind={activeKind}
            routing={routing}
            onPropose={(input, note) => proposing.onPropose(activeKind, input, note)}
            onProposed={(candidate) => { setEditing(false); proposing.onProposed(candidate); }}
            onClose={() => setEditing(false)}
          />
        ) : null}
      </div>
    </div>
  );
}
