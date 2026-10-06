'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CircuitBoard, LoaderCircle, Pencil } from 'lucide-react';
import { EditDock } from '@/components/engineering/edit-dock';
import { previewDraft, useRoutingCapability, type Candidate, type DraftPreview, type EditOp, type ProposalInput } from '@/lib/project-candidates';
import { changesToHighlights } from '@/lib/artifact-diff';
import { Model3DViewer } from '@/components/engineering/model3d-viewer';
import { ViewerOverlay, type PlacedPin, type ViewerHighlight, type ViewerPin } from '@/components/engineering/viewer-overlay';

export type { PlacedPin, ViewerHighlight, ViewerPin } from '@/components/engineering/viewer-overlay';
export type ActiveArtifact = { relative: string; kind: string };
/** A proposal's file shown in place of the retained one. It is a preview only and never replaces what is stored. */
/** Ask the viewer to find a part by its reference designator. `nonce` makes asking for the same part twice work. */
export type FocusPart = { ref: string; kind: 'schematic' | 'pcb'; nonce: number; /** The file the reference was read from. */ relative?: string };

export type ProposalPreview = { candidateId: string; kind: 'schematic' | 'pcb'; text: string; relative?: string };

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').split('/').filter((part) => part && part !== '.').join('/');
}

/**
 * Two paths are the same retained file only when the whole path matches. A file name alone is not enough: a project can
 * keep `a/control.kicad_sch` and `b/control.kicad_sch`, and drawing one's result over the other would be a lie.
 */
function sameFile(a: string | undefined, b: string | undefined) {
  if (!a || !b) return false;
  return normalizePath(a) === normalizePath(b);
}

/** The file a result belongs to, among those on offer: an exact match on the whole path, never a guess. */
function resolveFile(files: EvidenceBuildFile[], kind: string, relative: string | undefined) {
  // No path, no match: a result that cannot say which file it belongs to is not drawn over whichever file is lying around.
  if (!relative) return null;
  return files.find((file) => file.kind === kind && sameFile(file.relative, relative)) || null;
}

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

type KeptCamera = { relative: string; x: number; y: number; zoom: number };
type LooseCamera = { zoom: number; center: { x: number; y: number; constructor: unknown } };

function cameraOf(embed: HTMLElement) {
  const app = embed.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { viewport?: { camera?: LooseCamera; callback?: () => void }; draw?: () => void } }) | null;
  return { app, viewer: app?.viewer, camera: app?.viewer?.viewport?.camera };
}

function readCamera(embed: HTMLElement, relative: string): KeptCamera | null {
  try {
    const { camera } = cameraOf(embed);
    if (!camera || !Number.isFinite(camera.zoom) || !Number.isFinite(camera.center?.x)) return null;
    return { relative, x: camera.center.x, y: camera.center.y, zoom: camera.zoom };
  } catch {
    return null;
  }
}

/** KiCanvas fits its own view as it finishes loading; put the person's view back after that. */
function restoreCamera(embed: HTMLElement, kept: KeptCamera) {
  const apply = () => {
    try {
      const { viewer, camera } = cameraOf(embed);
      if (!viewer || !camera) return;
      const Vector = camera.center.constructor as new (x: number, y: number) => { x: number; y: number };
      camera.center = new Vector(kept.x, kept.y);
      camera.zoom = kept.zoom;
      viewer.viewport?.callback?.();
      viewer.draw?.();
    } catch {
      // A viewer that is not ready keeps its own fit.
    }
  };
  [80, 250, 600].forEach((delay) => window.setTimeout(apply, delay));
}

const FOCUS_REQUEST_LIFETIME_MS = 8000;
// After a part has been found, a later KiCanvas load may still clear the selection; reapply only for this long.
const FOCUS_REAPPLY_WINDOW_MS = 2000;

/** Selects a part and brings it into view. KiCanvas looks a footprint or symbol up by its reference. True once it took. */
function tryFocusOnPart(embed: HTMLElement, ref: string) {
  try {
    const app = embed.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { select?: (item: string) => void; selected?: { context?: { reference?: string } } | null; zoom_to_selection?: () => void; draw?: () => void } }) | null;
    const viewer = app?.viewer;
    if (!viewer?.select) return false;
    viewer.select(ref);
    if (viewer.selected?.context?.reference !== ref) return false;
    viewer.zoom_to_selection?.();
    viewer.draw?.();
    return true;
  } catch {
    return false;
  }
}

/**
 * KiCanvas reports `load` more than once, and the first can come before the viewer is able to select anything, so one
 * attempt can be wasted. Keep trying briefly; a reference the file does not have simply leaves the view as it was.
 */
function focusOnPart(embed: HTMLElement, ref: string, isCurrent: () => boolean, onDone?: () => void, attempt = 0) {
  if (!isCurrent()) return;
  if (tryFocusOnPart(embed, ref)) { onDone?.(); return; }
  if (attempt >= 12) return;
  window.setTimeout(() => { if (embed.isConnected) focusOnPart(embed, ref, isCurrent, onDone, attempt + 1); }, 250);
}

type FillMode = 'faint' | 'full';
const FAINT_FILL_OPACITY = 0.22;

/**
 * Copper pours are drawn opaque by default, which buries the tracks, pads and labels under a flat slab of colour. Faint
 * keeps them visible as context; full shows them as KiCad would. KiCanvas reads a per-layer opacity at draw time.
 */
function applyFillMode(embed: HTMLElement, mode: FillMode) {
  try {
    const app = embed.shadowRoot?.querySelector('kc-board-app') as (HTMLElement & { viewer?: { layers?: { in_display_order?: () => Iterable<{ name: string; opacity?: number }> }; draw?: () => void } }) | null;
    const viewer = app?.viewer;
    if (!viewer?.layers?.in_display_order) return;
    for (const layer of viewer.layers.in_display_order()) {
      if (/:(F|B|In\d+)\.Cu:Zones$/.test(layer.name)) layer.opacity = mode === 'faint' ? FAINT_FILL_OPACITY : 1;
    }
    viewer.draw?.();
  } catch {
    // A viewer that is not ready keeps its own look.
  }
}

function applyFillModeAfterLoad(embed: HTMLElement, mode: () => FillMode) {
  // The pours are painted after the load event; apply again as they appear.
  embed.addEventListener('kicanvas:load', () => [60, 250, 700].forEach((delay) => window.setTimeout(() => applyFillMode(embed, mode()), delay)), { once: true });
}

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

/** "Schematic" or "PCB", or the file's own name when a project has several files of one kind so the tabs can be told apart. */
function tabLabel(file: EvidenceBuildFile, all: EvidenceBuildFile[]) {
  const base = file.kind === 'schematic' ? 'Schematic' : file.kind === 'pcb' ? 'PCB' : file.name || 'Artifact';
  const sameKind = all.filter((other) => other.kind === file.kind);
  if (sameKind.length < 2) return base;
  const path = normalizePath(file.relative || file.name || base);
  const leaf = path.split('/').pop() || base;
  // Files that share a name are told apart by their folder, so two tabs never read the same.
  const clash = sameKind.some((other) => other !== file && (normalizePath(other.relative || other.name || '').split('/').pop() === leaf));
  return (clash ? path : leaf).replace(/\.kicad_(sch|pcb)$/, '');
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
  focusPart,
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
  proposing?: { projectId: string; baseRevision: number | null; onPropose: (kind: 'schematic' | 'pcb', input: ProposalInput, note: string) => Promise<Candidate>; onProposed: (candidate: Candidate) => void };
  preview?: ProposalPreview | null;
  focusPart?: FocusPart | null;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  // The host is not always on screen (an error or an empty state replaces it), so its arrival is what mounts a viewer.
  const [hostEl, setHostEl] = useState<HTMLDivElement | null>(null);
  const { ready, failed: viewerFailed } = useKiCanvasScript();
  // One identity for what is open: project, revision, build and file. Drafts, selections, cameras and searches belong to it.
  const contextKey = [proposing?.projectId || '', proposing?.baseRevision ?? '', buildDir].join('|');
  // What was fetched is kept with the project, revision and build it came from, so a slow or failed fetch for another one
  // never leaves the previous one's files or text standing in for it.
  const [listed, setListed] = useState<{ key: string; files: EvidenceBuildFile[] } | null>(null);
  const files = useMemo(() => (listed && listed.key === contextKey ? listed.files : []), [listed, contextKey]);
  const [activeRelative, setActiveRelative] = useState('');
  const [loaded, setLoaded] = useState<{ key: string; text: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [show3d, setShow3d] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftOps, setDraftOps] = useState<EditOp[]>([]);
  const [draft, setDraft] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; preview?: DraftPreview; message?: string; forKey?: string }>({ status: 'idle' });
  const cameraRef = useRef<{ relative: string; x: number; y: number; zoom: number } | null>(null);
  const relativeRef = useRef('');
  const [fills, setFills] = useState<FillMode>('faint');
  const fillsRef = useRef<FillMode>('faint');
  const pendingFocus = useRef<(FocusPart & { appliedAt?: number }) | null>(null);
  // Each request for a part gets a generation. Moving to another file or tab ends it, and so does a newer request.
  const focusGeneration = useRef(0);
  const cancelFocus = () => { focusGeneration.current += 1; pendingFocus.current = null; };
  fillsRef.current = fills;
  const activeKind = files.find((file) => file.relative === activeRelative)?.kind;
  const contentKey = `${contextKey}|${activeRelative}`;
  const content = loaded && loaded.key === contentKey ? loaded.text : '';
  // The file identity: the context above and the path.
  const artifactKey = `${contextKey}|${activeRelative}`;
  const artifactRef = useRef('');
  artifactRef.current = artifactKey;
  const previewing = Boolean(preview && preview.relative && preview.kind === activeKind && sameFile(preview.relative, activeRelative));
  // A proposal for a file that is not among those shown, or that does not say which file it changed, cannot be drawn anywhere honest.
  const previewMissing = Boolean(preview && (!preview.relative || (files.length && !resolveFile(files, preview.kind, preview.relative))));
  const routing = useRoutingCapability(proposing?.projectId || '', Boolean(proposing) && editing && activeKind === 'pcb');
  relativeRef.current = activeRelative;
  // Only over the file the edits were made to: another file of the same kind must not show this file's result.
  const draftShown = !previewing && draft.status === 'ready' && draft.preview?.kind === activeKind && draft.forKey === artifactKey && sameFile(draft.preview?.relative, activeRelative);
  const shownContent = previewing && preview ? preview.text : draftShown && draft.preview ? draft.preview.text : content;
  // Where the draft differs from the retained file, marked the same way a previewed proposal is.
  const draftHighlights = draftShown && draft.preview
    ? changesToHighlights({ available: true, kind: draft.preview.kind, summary: draft.preview.diff.summary || { added: 0, removed: 0, changed: 0, unchanged: 0 }, changes: draft.preview.diff.changes || [] }, activeRelative)
    : [];

  useEffect(() => {
    onActiveArtifact?.(activeRelative && activeKind ? { relative: activeRelative, kind: activeKind } : null);
    // Report only when the artifact actually changes, not when the caller re-creates its callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRelative, activeKind]);

  useEffect(() => {
    if (!buildDir) {
      setListed(null);
      setActiveRelative('');
      setLoaded(null);
      return;
    }
    let cancelled = false;
    const requestContext = contextKey;
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
        setListed({ key: requestContext, files: nextFiles });
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
  }, [buildDir, preferredKind, contextKey]);

  useEffect(() => {
    if (!buildDir || !activeRelative) {
      setLoaded(null);
      return;
    }
    const requestKey = `${contextKey}|${activeRelative}`;
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
        if (!cancelled) setLoaded({ key: requestKey, text: payload.content || '' });
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Artifact content is unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeRelative, buildDir, contextKey]);

  useEffect(() => {
    const host = hostEl;
    if (!host || !ready || !shownContent) return;
    let embed: HTMLElement | null = null;
    let stopFocus: (() => void) | undefined;
    const relativeAtMount = relativeRef.current;
    const artifactAtMount = artifactRef.current;
    const keptCamera = cameraRef.current && cameraRef.current.relative === artifactAtMount ? cameraRef.current : null;

    const mount = () => {
      host.querySelectorAll('kicanvas-embed:not([data-retired])').forEach((stray) => retireEmbed(stray as HTMLElement));
      const created = document.createElement('kicanvas-embed');
      embed = created;
      created.addEventListener('kicanvas:load', () => { created.dataset.loaded = '1'; });
      if (activeKind === 'pcb') applyFillModeAfterLoad(created, () => fillsRef.current);
      // A part asked for while this file was opening is found once it has loaded. KiCanvas can load more than once and a
      // later load clears the selection, so the request is reapplied after each load until it goes stale.
      created.dataset.artifact = artifactAtMount;
      created.addEventListener('kicanvas:load', () => window.setTimeout(() => {
        const wanted = pendingFocus.current;
        if (!wanted || wanted.kind !== activeKind || Date.now() - wanted.nonce >= FOCUS_REQUEST_LIFETIME_MS) return;
        // Only for the file the reference was read from, and only while the person has not moved on.
        if (wanted.relative && !sameFile(wanted.relative, relativeAtMount)) return;
        if (wanted.appliedAt && Date.now() - wanted.appliedAt > FOCUS_REAPPLY_WINDOW_MS) { pendingFocus.current = null; return; }
        const generation = focusGeneration.current;
        focusOnPart(created, wanted.ref, () => generation === focusGeneration.current && pendingFocus.current === wanted, () => { wanted.appliedAt = wanted.appliedAt || Date.now(); });
      }, 200));
      created.setAttribute('controls', 'basic');
      created.setAttribute('controlslist', 'nodownload nooverlay');
      const source = document.createElement('kicanvas-source');
      source.textContent = shownContent;
      created.appendChild(source);
      host.appendChild(created);

      if (keptCamera) {
        // The same file reloaded with other content (a draft or a previewed proposal): keep the view the person had.
        created.addEventListener('kicanvas:load', () => restoreCamera(created, keptCamera), { once: true });
      } else if (activeKind === 'pcb') {
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
      cameraRef.current = readCamera(embed, artifactAtMount) || cameraRef.current;
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
  }, [activeKind, artifactKey, shownContent, ready, hostEl]);

  // Finding a part: open the right kind of file if needed, then select it and bring it into view.
  useEffect(() => {
    if (!focusPart) return;
    focusGeneration.current += 1;
    const generation = focusGeneration.current;
    const request: FocusPart & { appliedAt?: number } = { ...focusPart };
    pendingFocus.current = request;
    setShow3d(false);
    // The file the reference was read from; never merely the first file of that kind.
    const target = resolveFile(files, focusPart.kind, focusPart.relative);
    if (!target?.relative) { pendingFocus.current = null; return; }
    if (!sameFile(target.relative, activeRelative)) { setActiveRelative(target.relative); return; }
    const embed = hostRef.current?.querySelector('kicanvas-embed:not([data-retired])') as HTMLElement | null;
    if (embed && embed.dataset.loaded === '1') focusOnPart(embed, request.ref, () => generation === focusGeneration.current && pendingFocus.current === request, () => { request.appliedAt = Date.now(); });
    // Only when a new request is made, not when the file list or the active file changes underneath it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPart?.nonce]);

  // Previewing a proposal shows the file it changed.
  useEffect(() => {
    if (!preview) return;
    // The file the proposal changed, never merely the first file of that kind.
    const target = resolveFile(files, preview.kind, preview.relative);
    if (target?.relative) { cancelFocus(); setShow3d(false); setActiveRelative(target.relative); }
    // Only when a different proposal is chosen, not on every file-list refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.candidateId]);

  useEffect(() => {
    if (show3d || preview) setEditing(false);
  }, [show3d, preview]);

  // Leaving edit mode, or changing file, drops the draft with it.
  useEffect(() => {
    if (!editing) { setDraftOps([]); setDraft({ status: 'idle' }); }
  }, [editing]);
  useEffect(() => { setDraftOps([]); setDraft({ status: 'idle' }); }, [artifactKey]);

  // Another project, revision or build ends editing and any search for a part.
  useEffect(() => {
    setEditing(false);
    cancelFocus();
  }, [contextKey]);

  // A dry run of the draft, a beat after the last change, so the viewer can show the result and a refused edit is reported
  // while the person is still editing. Nothing is saved.
  useEffect(() => {
    if (!editing || !proposing || !draftOps.length || (activeKind !== 'schematic' && activeKind !== 'pcb')) {
      setDraft((current) => (current.status === 'idle' ? current : { status: 'idle' }));
      return;
    }
    const controller = new AbortController();
    const requestedFor = activeRelative;
    const requestedKey = artifactKey;
    setDraft((current) => ({ ...current, status: 'loading' }));
    const timer = window.setTimeout(() => {
      previewDraft(proposing.projectId, { baseRevision: proposing.baseRevision, kind: activeKind, ops: draftOps }, controller.signal)
        .then((result) => {
          if (!result.ok) { setDraft({ status: 'error', message: result.message }); return; }
          // Edits always apply to the one file a revision retains for this kind. If another file is on screen, say so
          // rather than drawing that file's result under this file's name.
          if (!sameFile(result.preview.relative, requestedFor)) {
            const kept = result.preview.relative || 'another file';
            setDraft({ status: 'error', message: `This revision keeps ${kept} as its editable ${activeKind === 'pcb' ? 'PCB' : 'schematic'}, not the file on screen. Open that file to edit it.` });
            return;
          }
          setDraft({ status: 'ready', preview: result.preview, forKey: requestedKey });
        })
        .catch(() => undefined);
    }, 350);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // The ops, the file (artifactKey) and the revision are the triggers; the callback identity is not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftOps, editing, activeKind, artifactKey, proposing?.projectId, proposing?.baseRevision]);

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
                onClick={() => { cancelFocus(); setShow3d(false); setActiveRelative(file.relative || ''); }}
                className={`border-b-2 px-3 py-2.5 text-xs font-medium ${active && !show3d ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
              >
                {tabLabel(file, visibleFiles)}
              </button>
            );
          })}
          {model3d && model3d.revision ? (
            <button
              type="button"
              onClick={() => { cancelFocus(); setShow3d(true); }}
              aria-pressed={show3d}
              className={`border-b-2 px-3 py-2.5 text-xs font-medium ${show3d ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
            >
              3D
            </button>
          ) : null}
          {!visibleFiles.length && !model3d ? <span className="px-3 text-xs text-stone-500">Artifact</span> : null}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          {activeKind === 'pcb' && !show3d ? (
            <button
              type="button"
              onClick={() => {
                const next: FillMode = fills === 'faint' ? 'full' : 'faint';
                setFills(next);
                const embed = hostRef.current?.querySelector('kicanvas-embed:not([data-retired])') as HTMLElement | null;
                if (embed) applyFillMode(embed, next);
              }}
              aria-pressed={fills === 'full'}
              title="Copper pours cover most of a board. Faint keeps tracks, pads and labels readable; full shows the pours as KiCad draws them."
              className="inline-flex h-7 shrink-0 items-center rounded-md border border-stone-300 px-2.5 text-[11px] font-medium text-stone-700 hover:bg-stone-50"
            >
              Copper fills: {fills}
            </button>
          ) : null}
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
          <span className={`shrink-0 rounded border px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] ${previewing || draftShown ? 'border-amber-300 bg-amber-50 text-amber-900' : editing ? 'border-stone-900 text-stone-900' : 'border-stone-200 bg-stone-50 text-stone-500'}`}>{previewing ? 'Proposal preview · not applied' : draftShown ? 'Draft preview · not saved' : editing ? 'Drafting a proposal' : 'Read-only review'}</span>
          <span className="max-w-[20rem] truncate font-mono text-[10px] text-stone-400">{show3d ? 'rendered from the retained PCB' : activeRelative || 'no KiCad artifact attached'}</span>
        </div>
      </div>

      {editing && proposing && (activeKind === 'schematic' || activeKind === 'pcb') ? (
        <EditDock
          hostRef={hostRef}
          kind={activeKind}
          fileKey={artifactKey}
          routing={routing}
          draftStatus={draft.status === 'idle' ? null : { status: draft.status, message: draft.message }}
          onDraftChange={setDraftOps}
          onPropose={(input, note) => proposing.onPropose(activeKind, input, note)}
          onProposed={(candidate) => { setEditing(false); proposing.onProposed(candidate); }}
          onClose={() => setEditing(false)}
        />
      ) : null}
      {previewMissing && preview ? (
        <div role="alert" className="shrink-0 border-b border-amber-300 bg-amber-50 px-3 py-1.5 text-[11px] leading-4 text-amber-900">
          {preview.relative
            ? `This proposal changed ${preview.relative}, which is not among the files shown, so it can't be drawn here.`
            : "This proposal was recorded without the path of the file it changed, so it can't be drawn over a file with certainty."}
        </div>
      ) : null}
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
          <div ref={(element) => { hostRef.current = element; setHostEl(element); }} className={`${compact ? 'min-h-[470px]' : 'min-h-[600px]'} h-full w-full [&>kicanvas-embed]:block [&>kicanvas-embed]:h-full [&>kicanvas-embed]:w-full`} />
        )}
        {shownContent ? (
          <ViewerOverlay
            hostRef={hostRef}
            activeRelative={activeRelative}
            activeKind={activeKind || ''}
            pins={pins}
            highlights={[...(highlights || []), ...draftHighlights]}
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
      </div>
    </div>
  );
}
