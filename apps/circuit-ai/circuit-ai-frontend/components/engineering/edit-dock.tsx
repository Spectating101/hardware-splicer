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
function readSelection(host: HTMLElement | null, kind: string): Selected | null {
  const embed = host?.querySelector('kicanvas-embed:not([data-retired])') as (HTMLElement & { shadowRoot: ShadowRoot | null }) | null;
  const app = embed?.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { selected?: { context?: Loose } | null } }) | null;
  const ctx = app?.viewer?.selected?.context;
  if (!ctx || typeof ctx.uuid !== 'string') return null;
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
}: {
  hostRef: RefObject<HTMLDivElement | null>;
  kind: string;
  routing?: RoutingCapability | null;
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
      const uuid = next?.uuid || '';
      if (uuid === lastUuid.current) return;
      lastUuid.current = uuid;
      setSelected(next);
      setConfirmDelete(false);
      setX(next?.x === null || next === null ? '' : String(next?.x));
      setY(next?.y === null || next === null ? '' : String(next?.y));
      setValue(next?.value || '');
    }, 150);
    return () => window.clearInterval(timer);
  }, [hostRef, kind]);

  // A draft belongs to one file; switching between schematic and PCB must not carry edits across.
  useEffect(() => {
    setDrafts([]);
    setError('');
  }, [kind]);

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
  const small = 'inline-flex h-7 items-center justify-center gap-1 rounded-md border border-stone-300 bg-white px-2 text-[11px] font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400';

  return (
    <div className="absolute bottom-3 left-1/2 z-[14] w-[min(26rem,calc(100%-14rem))] -translate-x-1/2 rounded-lg border border-stone-300 bg-white/95 p-3 text-stone-800 shadow-xl backdrop-blur" data-testid="edit-dock">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-stone-900">{selected ? selected.label : 'Select a part to change it'}</div>
          <div className="text-[10px] leading-4 text-stone-500">Changes become a proposal for review. Nothing is applied until it is accepted.</div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close editing" className="shrink-0 rounded p-1 text-stone-500 hover:bg-stone-100"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </div>

      {selected ? (
        <div className="mt-2.5 space-y-2">
          <div className="flex items-center gap-1.5">
            <button type="button" className={small} onClick={() => addRotate(-90)} aria-label="Rotate 90 degrees counter-clockwise"><RotateCcw className="h-3 w-3" aria-hidden="true" />90°</button>
            <button type="button" className={small} onClick={() => addRotate(90)} aria-label="Rotate 90 degrees clockwise"><RotateCw className="h-3 w-3" aria-hidden="true" />90°</button>
            <button type="button" className={`${small} ml-auto ${confirmDelete ? 'border-red-300 bg-red-50 text-red-800 hover:bg-red-100' : ''}`} onClick={addDelete}>{confirmDelete ? `Confirm delete ${selected.ref}` : 'Delete'}</button>
          </div>
          <div className="flex items-center gap-1.5">
            <input className={`${field} w-20`} inputMode="decimal" value={x} onChange={(event) => setX(event.target.value)} aria-label="X position in millimetres" placeholder="x mm" />
            <input className={`${field} w-20`} inputMode="decimal" value={y} onChange={(event) => setY(event.target.value)} aria-label="Y position in millimetres" placeholder="y mm" />
            <button type="button" className={small} onClick={addMove}>Move</button>
          </div>
          <div className="flex items-center gap-1.5">
            <input className={`${field} flex-1`} value={value} onChange={(event) => setValue(event.target.value)} aria-label="Value" placeholder="Value" maxLength={120} />
            <button type="button" className={small} onClick={addValue} disabled={value === selected.value}>Set value</button>
          </div>
        </div>
      ) : null}

      {kind === 'pcb' && !drafts.length ? (
        <div className="mt-2.5 border-t border-stone-200 pt-2">
          <div className="flex items-center justify-between gap-2">
            <button type="button" onClick={() => void autoroute()} disabled={busy || !routing?.available} title={routing?.available ? 'Routes the unrouted nets and proposes the result for review' : (routing?.reason || 'Checking whether routing is available')} className={small}>
              {busy ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}Autoroute the board
            </button>
            <span className="min-w-0 truncate text-[10px] text-stone-500">{routing === null || routing === undefined ? 'Checking router…' : routing.available ? 'Existing tracks are kept' : 'Not available on this server'}</span>
          </div>
          {routing && !routing.available && routing.reason ? <p className="mt-1.5 text-[10px] leading-4 text-stone-500">{routing.reason}</p> : null}
        </div>
      ) : null}

      {drafts.length ? (
        <div className="mt-2.5 border-t border-stone-200 pt-2">
          <ul className="m-0 list-none space-y-1 p-0">
            {drafts.map((draft) => (
              <li key={draft.id} className="flex items-center justify-between gap-2 text-[11px] text-stone-700">
                <span className="min-w-0 truncate">{draft.text}</span>
                <button type="button" onClick={() => setDrafts((current) => current.filter((item) => item.id !== draft.id))} aria-label={`Remove: ${draft.text}`} className="shrink-0 rounded p-0.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700"><X className="h-3 w-3" aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex items-center gap-1.5">
            <input className={`${field} flex-1`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why (optional)" maxLength={500} aria-label="Reason for the proposal" />
            <button type="button" onClick={() => void submit()} disabled={busy} className="inline-flex h-7 items-center gap-1.5 rounded-md bg-stone-900 px-3 text-[11px] font-medium text-white hover:bg-stone-700 disabled:opacity-60">
              {busy ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}
              Propose {drafts.length} {drafts.length === 1 ? 'change' : 'changes'}
            </button>
          </div>
        </div>
      ) : null}

      {error ? <div role="alert" className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] leading-4 text-red-800">{error}</div> : null}
    </div>
  );
}
