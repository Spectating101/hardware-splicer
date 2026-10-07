'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { LoaderCircle } from 'lucide-react';
import { ViewerOverlay, type ViewerHighlight } from '@/components/engineering/viewer-overlay';
import { copyCamera, useKiCanvasEmbed, useKiCanvasScript } from '@/lib/kicanvas';

export type CompareMode = 'before' | 'swipe' | 'difference';
type Kind = 'schematic' | 'pcb';
type Side = { key: string; status: 'loading' | 'ready' | 'missing' | 'error'; text?: string; message?: string };

const NOT_RETAINED = 'was not retained, so it can\'t be compared visually.';

async function fetchRetained(projectId: string, revision: number, kind: Kind, signal: AbortSignal): Promise<Pick<Side, 'status' | 'text' | 'message'>> {
  try {
    const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/revisions/${revision}/artifacts/${kind}/file`, { cache: 'no-store', signal });
    if (response.status === 404) return { status: 'missing', message: `Revision ${revision}'s ${kind === 'pcb' ? 'PCB' : 'schematic'} ${NOT_RETAINED}` };
    if (!response.ok) return { status: 'error', message: `Revision ${revision}'s ${kind === 'pcb' ? 'PCB' : 'schematic'} could not be loaded (${response.status}).` };
    return { status: 'ready', text: await response.text() };
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') throw caught;
    return { status: 'error', message: 'The comparison service could not be reached.' };
  }
}

/**
 * The two revisions' retained files drawn over one another: Before alone, a Swipe between them, or a Difference in which
 * what is identical cancels to black and only what changed shows. They are the files each revision kept, checked against
 * their hashes, not whatever the build folder holds now. The two viewers share one camera, so panning or zooming moves both.
 */
export function ComparisonViewer({
  projectId,
  baseRevision,
  candidateRevision,
  mode,
  highlights = [],
  focusHighlightId = null,
  onActiveArtifact,
}: {
  projectId: string;
  baseRevision: number;
  candidateRevision: number;
  mode: CompareMode;
  highlights?: ViewerHighlight[];
  focusHighlightId?: string | null;
  onActiveArtifact?: (artifact: { relative: string; kind: string } | null) => void;
}) {
  const { ready, failed } = useKiCanvasScript();
  const [kind, setKind] = useState<Kind>('schematic');
  const [position, setPosition] = useState(50);
  const [baseSide, setBaseSide] = useState<Side | null>(null);
  const [candidateSide, setCandidateSide] = useState<Side | null>(null);
  const [candidateRelative, setCandidateRelative] = useState<{ key: string; relative: string } | null>(null);
  const [baseHost, setBaseHost] = useState<HTMLDivElement | null>(null);
  const [topHost, setTopHost] = useState<HTMLDivElement | null>(null);
  const topRef = useRef<HTMLDivElement | null>(null);
  const stage = useRef<HTMLDivElement | null>(null);

  // Everything fetched or mounted belongs to this exact comparison; a different one starts from nothing.
  const identity = `${projectId}|${baseRevision}|${candidateRevision}|${kind}`;

  useEffect(() => {
    const controller = new AbortController();
    setBaseSide(null);
    setCandidateSide(null);
    const load = async (revision: number, apply: (side: Side) => void) => {
      try {
        const result = await fetchRetained(projectId, revision, kind, controller.signal);
        apply({ key: identity, ...result });
      } catch {
        // Aborted: a newer comparison is already loading.
      }
    };
    void load(baseRevision, setBaseSide);
    void load(candidateRevision, setCandidateSide);
    fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/revisions/${candidateRevision}/artifacts`, { cache: 'no-store', signal: controller.signal })
      .then((response) => response.json())
      .then((body) => {
        const relative = body?.pin?.artifacts?.[kind]?.relative;
        if (typeof relative === 'string') setCandidateRelative({ key: identity, relative });
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [identity, projectId, baseRevision, candidateRevision, kind]);

  const base = baseSide && baseSide.key === identity ? baseSide : null;
  const candidate = candidateSide && candidateSide.key === identity ? candidateSide : null;
  const relative = candidateRelative && candidateRelative.key === identity ? candidateRelative.relative : '';

  useEffect(() => {
    onActiveArtifact?.(relative ? { relative, kind } : null);
    // Report when the artifact changes, not when the caller re-creates its callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [relative, kind]);

  const baseEmbed = useKiCanvasEmbed(baseHost, ready, base?.status === 'ready' ? base.text || null : null, `${identity}|base`, kind, { controls: 'basic', faintFills: true });
  const topEmbed = useKiCanvasEmbed(topHost, ready, candidate?.status === 'ready' ? candidate.text || null : null, `${identity}|candidate`, kind, { controls: 'basic', faintFills: true });

  // Whichever viewer is the one the person can touch leads; the other follows it every frame.
  const leader = mode === 'before' ? baseEmbed : topEmbed;
  const follower = mode === 'before' ? topEmbed : baseEmbed;
  useEffect(() => {
    if (!leader || !follower) return;
    // Start together, then stay together.
    copyCamera(leader, follower);
    let frame = 0;
    const loop = () => {
      copyCamera(leader, follower);
      frame = window.requestAnimationFrame(loop);
    };
    frame = window.requestAnimationFrame(loop);
    return () => window.cancelAnimationFrame(frame);
  }, [leader, follower]);

  const moveDivider = useCallback((clientX: number) => {
    const box = stage.current?.getBoundingClientRect();
    if (!box || box.width <= 0) return;
    setPosition(Math.max(2, Math.min(98, ((clientX - box.left) / box.width) * 100)));
  }, []);
  const onDividerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    moveDivider(event.clientX);
  };
  const onDividerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) moveDivider(event.clientX);
  };
  const onDividerKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowLeft') { event.preventDefault(); setPosition((value) => Math.max(2, value - 3)); }
    if (event.key === 'ArrowRight') { event.preventDefault(); setPosition((value) => Math.min(98, value + 3)); }
  };

  const problem = useMemo(() => {
    const parts = [base, candidate].filter((side): side is Side => Boolean(side && (side.status === 'missing' || side.status === 'error')));
    return parts.length ? parts.map((side) => side.message).join(' ') : failed ? 'The bundled KiCanvas viewer failed to load.' : '';
  }, [base, candidate, failed]);
  const waiting = !problem && (!base || !candidate || base.status === 'loading' || candidate.status === 'loading' || !baseEmbed || !topEmbed);

  const kindButton = (value: Kind, label: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setKind(value)}
      aria-pressed={kind === value}
      className={`border-b-2 px-3 py-2.5 text-xs font-medium ${kind === value ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
    >
      {label}
    </button>
  );

  const showTop = mode !== 'before';
  return (
    <div className="flex h-full min-h-[520px] flex-col bg-white" data-testid="comparison-viewer" data-mode={mode}>
      <div className="flex min-h-11 items-center justify-between gap-3 border-b border-stone-200 px-3">
        <div className="flex items-center gap-1">{kindButton('schematic', 'Schematic')}{kindButton('pcb', 'PCB')}</div>
        <div className="flex min-w-0 items-center gap-2 text-[10px] text-stone-500">
          {mode === 'before' ? <span>Revision {baseRevision}, as it was saved</span> : null}
          {mode === 'swipe' ? <span>Revision {baseRevision} on the left, revision {candidateRevision} on the right</span> : null}
          {mode === 'difference' ? <span>What changed between revisions {baseRevision} and {candidateRevision}: identical parts disappear</span> : null}
          <span className="shrink-0 rounded border border-stone-200 bg-stone-50 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-stone-500">Saved copies</span>
        </div>
      </div>

      <div ref={stage} className="relative min-h-0 flex-1 overflow-hidden bg-[#13111a]" style={{ isolation: 'isolate' }} data-testid="comparison-stage">
        {/* The earlier revision underneath, the later one on top. Only one of them takes the mouse. */}
        <div ref={setBaseHost} className={`absolute inset-0 ${mode === 'before' ? '' : 'pointer-events-none'} [&>kicanvas-embed]:block [&>kicanvas-embed]:h-full [&>kicanvas-embed]:w-full`} />
        <div
          ref={(element) => { topRef.current = element; setTopHost(element); }}
          className={`absolute inset-0 ${showTop ? '' : 'pointer-events-none opacity-0'} [&>kicanvas-embed]:block [&>kicanvas-embed]:h-full [&>kicanvas-embed]:w-full`}
          style={{
            mixBlendMode: mode === 'difference' ? 'difference' : 'normal',
            clipPath: mode === 'swipe' ? `inset(0 0 0 ${position}%)` : undefined,
          }}
        />

        {topEmbed ? <ViewerOverlay hostRef={topRef} activeRelative={relative} activeKind={kind} highlights={highlights} focusId={focusHighlightId} /> : null}

        {mode === 'swipe' && !waiting && !problem ? (
          <div
            role="slider"
            tabIndex={0}
            aria-label="Divider between the two revisions"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(position)}
            aria-valuetext={`Revision ${baseRevision} to the left, revision ${candidateRevision} to the right`}
            onPointerDown={onDividerDown}
            onPointerMove={onDividerMove}
            onKeyDown={onDividerKey}
            className="absolute inset-y-0 z-[13] w-6 -translate-x-1/2 cursor-ew-resize touch-none focus-visible:outline-none"
            style={{ left: `${position}%` }}
            data-testid="swipe-divider"
          >
            <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white/80 shadow-[0_0_0_1px_rgba(0,0,0,0.4)]" />
            <div className="absolute left-1/2 top-1/2 flex h-8 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/80 bg-stone-900/90 text-[9px] text-white shadow focus-visible:ring-2">⇆</div>
          </div>
        ) : null}

        {waiting ? <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#13111a]/70"><LoaderCircle className="h-5 w-5 animate-spin text-stone-300" aria-label="Loading the saved copies" /></div> : null}
        {problem ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#13111a] p-8">
            <div role="alert" className="max-w-sm text-center text-sm leading-6 text-stone-200">{problem}</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
