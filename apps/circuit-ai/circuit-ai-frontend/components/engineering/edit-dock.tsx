'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';
import { LoaderCircle, RotateCcw, RotateCw, X } from 'lucide-react';
import type { Candidate, EditOp, ProposalInput, RoutingCapability } from '@/lib/project-candidates';

type Selected = {
  uuid: string;
  ref: string;
  label: string;
  x: number | null;
  y: number | null;
  value: string;
};

type Draft = { id: number; op: EditOp; text: string };
type Loose = Record<string, unknown> & { constructor?: { name?: string } };

function num(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? Math.round(value * 1000) / 1000 : null;
}

/**
 * The item KiCanvas currently has selected, reduced to what an edit needs. Only placed schematic symbols and PCB
 * footprints are offered for editing; anything else reads as "not editable here" rather than guessing an operation.
 */
/** `undefined` when nothing is selected, `null` when something is selected that cannot be edited here. */
function readSelection(host: HTMLElement | null, kind: string): Selected | null | undefined {
  const embed = host?.querySelector('kicanvas-embed:not([data-retired])') as (HTMLElement & { shadowRoot: ShadowRoot | null }) | null;
  const app = embed?.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { selected?: { context?: Loose } | null } }) | null;
  const ctx = app?.viewer?.selected?.context;
  if (!ctx) return undefined;
  if (typeof ctx.uuid !== 'string') return null;
  const isSymbol = kind === 'schematic' && typeof ctx.lib_id === 'string';
  const isFootprint = kind === 'pcb' && typeof ctx.reference === 'string' && Boolean(ctx.pads);
  if (!isSymbol && !isFootprint) return null;
  const at = ctx.at as { position?: { x?: number; y?: number } } | undefined;
  let value = '';
  try {
    const properties = ctx.properties as Map<string, { text?: string }> | undefined;
    value = String(properties?.get?.('Value')?.text ?? ctx.value ?? '');
  } catch {
    value = '';
  }
  const ref = String(ctx.reference ?? '');
  return {
    uuid: ctx.uuid,
    ref,
    label: `${ref || 'Item'}${value ? ` · ${value}` : ''}`,
    x: num(at?.position?.x),
    y: num(at?.position?.y),
    value,
  };
}

/**
 * Drafts edits to the item selected in the viewer and sends them as one proposal. Nothing here changes a revision:
 * the backend applies the edits to a copy of the retained file and opens it for review.
 */
export function EditDock({
  hostRef,
  kind,
  onPropose,
  onProposed,
  onClose,
  routing,
  draftStatus,
  onDraftChange,
}: {
  hostRef: RefObject<HTMLDivElement | null>;
  kind: string;
  routing?: RoutingCapability | null;
  /** How the dry run of the current draft is going; null when there is nothing to preview. */
  draftStatus?: { status: 'loading' | 'ready' | 'error'; message?: string } | null;
  onDraftChange?: (ops: EditOp[]) => void;
  onPropose: (input: ProposalInput, note: string) => Promise<Candidate>;
  onProposed: (candidate: Candidate) => void;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<Selected | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [x, setX] = useState('');
  const [y, setY] = useState('');
  const [value, setValue] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const counter = useRef(0);
  const lastUuid = useRef('');

  useEffect(() => {
    const timer = window.setInterval(() => {
      const next = readSelection(hostRef.current, kind);
      // Reloading the viewer to show a draft clears KiCanvas's own selection. The part stays chosen here until another
      // one is picked, so the person can keep editing it.
      if (next === undefined) return;
      if (next === null) {
        if (lastUuid.current) { lastUuid.current = ''; setSelected(null); }
        return;
      }
      if (next.uuid === lastUuid.current) return;
      lastUuid.current = next.uuid;
      setSelected(next);
      setConfirmDelete(false);
      setX(next.x === null ? '' : String(next.x));
      setY(next.y === null ? '' : String(next.y));
      setValue(next.value || '');
    }, 150);
    return () => window.clearInterval(timer);
  }, [hostRef, kind]);

  // A draft belongs to one file; switching between schematic and PCB must not carry edits across.
  useEffect(() => {
    setDrafts([]);
    setError('');
    setSelected(null);
    lastUuid.current = '';
  }, [kind]);

  // Tell the viewer what the draft is, so it can show the result.
  useEffect(() => {
    onDraftChange?.(drafts.map((draft) => draft.op));
    // Only the ops matter; the callback identity changes every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts]);

  function add(op: EditOp, text: string) {
    counter.current += 1;
    setError('');
    setDrafts((current) => [...current, { id: counter.current, op, text }]);
  }

  function addRotate(degrees: number) {
    if (!selected) return;
    // Schematic rotation takes 0, 90, 180 or 270, so a turn the other way is sent as its positive equivalent.
    const normalized = ((degrees % 360) + 360) % 360;
    add({ op: 'rotate', uuid: selected.uuid, degrees: normalized }, `Rotate ${selected.ref || 'item'} ${degrees > 0 ? '+' : '−'}${Math.abs(degrees)}°`);
  }

  function addMove() {
    if (!selected) return;
    const nx = Number(x);
    const ny = Number(y);
    if (!x.trim() || !y.trim() || !Number.isFinite(nx) || !Number.isFinite(ny)) {
      setError('Enter both coordinates in millimetres.');
      return;
    }
    add({ op: 'move', uuid: selected.uuid, x_mm: nx, y_mm: ny }, `Move ${selected.ref || 'item'} to ${nx}, ${ny} mm`);
  }

  function addValue() {
    if (!selected || value === selected.value) return;
    add({ op: 'set_property', uuid: selected.uuid, name: 'Value', value }, `Set ${selected.ref || 'item'} value to ${value || '(empty)'}`);
  }

  function addDelete() {
    if (!selected) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    add(kind === 'pcb' ? { op: 'delete', uuid: selected.uuid, confirm: true } : { op: 'delete', uuid: selected.uuid }, `Delete ${selected.ref || 'item'}`);
    setConfirmDelete(false);
  }

  async function submit() {
    if (!drafts.length || busy) return;
    setBusy(true);
    setError('');
    try {
      const candidate = await onPropose({ ops: drafts.map((draft) => draft.op) }, note.trim());
      setDrafts([]);
      setNote('');
      onProposed(candidate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The proposal could not be created.');
    } finally {
      setBusy(false);
    }
  }

  async function autoroute() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const candidate = await onPropose({ autoroute: {} }, note.trim());
      setNote('');
      onProposed(candidate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The proposal could not be created.');
    } finally {
      setBusy(false);
    }
  }

  const field = 'h-7 min-w-0 rounded-md border border-stone-300 bg-white px-2 text-xs text-stone-900 focus:border-stone-500 focus:outline-none';
  const small = 'inline-flex h-7 shrink-0 items-center justify-center gap-1 rounded-md border border-stone-300 bg-white px-2 text-[11px] font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400';
  const divider = <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-stone-300 sm:inline-block" />;
  const proposeLabel = `Propose ${drafts.length} ${drafts.length === 1 ? 'change' : 'changes'}`;

  // A toolbar above the drawing, not a card over it: it pushes the canvas down so it never covers the part being edited.
  return (
    <div className="shrink-0 border-b border-stone-300 bg-stone-50 px-3 py-2 text-stone-800" data-testid="edit-dock">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <div className="min-w-0 max-w-[16rem] truncate text-xs font-semibold text-stone-900" title={selected?.label}>{selected ? selected.label : 'Select a part to change it'}</div>

        {selected ? (
          <>
            {divider}
            <button type="button" className={small} onClick={() => addRotate(-90)} aria-label="Rotate 90 degrees counter-clockwise" title="Turn 90° counter-clockwise"><RotateCcw className="h-3 w-3" aria-hidden="true" />90°</button>
            <button type="button" className={small} onClick={() => addRotate(90)} aria-label="Rotate 90 degrees clockwise" title="Turn 90° clockwise"><RotateCw className="h-3 w-3" aria-hidden="true" />90°</button>
            {divider}
            <input className={`${field} w-16`} inputMode="decimal" value={x} onChange={(event) => setX(event.target.value)} aria-label="X position in millimetres" placeholder="x mm" />
            <input className={`${field} w-16`} inputMode="decimal" value={y} onChange={(event) => setY(event.target.value)} aria-label="Y position in millimetres" placeholder="y mm" />
            <button type="button" className={small} onClick={addMove}>Move</button>
            {divider}
            <input className={`${field} w-28`} value={value} onChange={(event) => setValue(event.target.value)} aria-label="Value" placeholder="Value" maxLength={120} />
            <button type="button" className={small} onClick={addValue} disabled={value === selected.value}>Set value</button>
          </>
        ) : null}

        {kind === 'pcb' && !drafts.length ? (
          <>
            {divider}
            <button type="button" onClick={() => void autoroute()} disabled={busy || !routing?.available} title={routing?.available ? 'Routes the unrouted nets and proposes the result for review' : (routing?.reason || 'Checking whether routing is available')} className={small}>
              {busy ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}Autoroute the board
            </button>
            <span className="min-w-0 truncate text-[10px] text-stone-500">{routing === null || routing === undefined ? 'Checking router…' : routing.available ? 'Existing tracks are kept' : 'Not available on this server'}</span>
          </>
        ) : null}

        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {selected ? (
            <button type="button" className={`${small} ${confirmDelete ? 'border-red-300 bg-red-50 text-red-800 hover:bg-red-100' : ''}`} onClick={addDelete}>{confirmDelete ? `Confirm delete ${selected.ref}` : 'Delete'}</button>
          ) : null}
          <button type="button" onClick={onClose} aria-label="Close editing" className="shrink-0 rounded p-1 text-stone-500 hover:bg-stone-200"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
        </div>
      </div>

      {kind === 'pcb' && !drafts.length && routing && !routing.available && routing.reason ? <p className="m-0 mt-1 text-[10px] leading-4 text-stone-500">{routing.reason}</p> : null}

      {drafts.length ? (
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5 border-t border-stone-200 pt-2">
          <ul className="m-0 flex min-w-0 list-none flex-wrap gap-1.5 p-0">
            {drafts.map((draft) => (
              <li key={draft.id} className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border border-stone-300 bg-white py-0.5 pl-2 pr-1 text-[11px] text-stone-700">
                <span className="min-w-0 truncate">{draft.text}</span>
                <button type="button" onClick={() => setDrafts((current) => current.filter((item) => item.id !== draft.id))} aria-label={`Remove: ${draft.text}`} className="shrink-0 rounded-full p-0.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700"><X className="h-3 w-3" aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
          <input className={`${field} ml-auto w-56`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why (optional)" maxLength={500} aria-label="Reason for the proposal" />
          <button type="button" onClick={() => void submit()} disabled={busy || draftStatus?.status === 'error'} className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md bg-stone-900 px-3 text-[11px] font-medium text-white hover:bg-stone-700 disabled:opacity-60">
            {busy ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}
            {proposeLabel}
          </button>
        </div>
      ) : null}

      {drafts.length && draftStatus ? (
        draftStatus.status === 'error' ? (
          <div role="alert" className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-[11px] leading-4 text-amber-900">
            This draft can&apos;t be applied: {draftStatus.message} Remove the change that caused it to continue.
          </div>
        ) : (
          <p className="m-0 mt-1.5 text-[10px] leading-4 text-stone-500">
            {draftStatus.status === 'loading' ? 'Updating the preview…' : 'The viewer shows the result with your changes marked. Nothing is saved until you propose.'}
          </p>
        )
      ) : (
        <p className="m-0 mt-1.5 text-[10px] leading-4 text-stone-500">Changes become a proposal for review. Nothing is applied until it is accepted.</p>
      )}

      {error ? <div role="alert" className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] leading-4 text-red-800">{error}</div> : null}
    </div>
  );
}
