'use client';

import { useEffect, useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { getProxyErrorMessage, isProxyFailure } from '@/lib/proxy-client';

export type Gate = { key: string; kind: string; from: string; to: string; instruction: string; expect: string };
type Match = { name: string; library: string; tier: 'exact' | 'variant' | 'family'; tier_text: string; description: string; datasheet: string | null; footprint: string | null };
type LookupData = {
  query: string;
  source: { name: string; version: string; symbols: number; note: string } | null;
  matches: Match[];
  reason: string | null;
  libraries_available: boolean;
  gates: Gate[];
  gates_from: string | null;
  search_links: { smd_code?: string };
};

const TIER_LABEL: Record<Match['tier'], string> = { exact: 'Same name', variant: 'Variant', family: 'Same family' };
const TIER_CLASS: Record<Match['tier'], string> = {
  exact: 'bg-emerald-500/20 text-emerald-200',
  variant: 'bg-sky-500/20 text-sky-200',
  family: 'bg-stone-500/25 text-stone-300',
};

/** The package choice on the capture page that a KiCad footprint name stands for, or null when none fits. */
export function packageFromFootprint(footprint: string | null): string | null {
  if (!footprint) return null;
  const f = footprint.toLowerCase();
  if (f.startsWith('package_dip:')) return 'DIP';
  if (f.startsWith('package_so:')) return f.startsWith('package_so:tssop-') ? 'TSSOP' : /msop|ssop|vssop|qsop|sc-70/.test(f) ? null : 'SOIC';   // no capture package matches those, so none is offered
  if (f.startsWith('package_to_sot_smd:sot-23')) return 'SOT-23';
  if (f.startsWith('package_qfp:')) return 'QFP';
  if (f.startsWith('package_dfn_qfn:')) return 'QFN';
  if (f.startsWith('package_bga:')) return 'BGA';
  if (f.startsWith('package_to_sot_tht:to-220')) return 'TO-220';
  return null;
}

/**
 * What KiCad's own libraries say about a marking, and the measurements to write down. A library entry is a part with
 * that name, not proof that the chip in hand is that part, and the panel says so. Readings are notes: never a pass.
 */
export function PartLookupPanel({
  marking,
  readings,
  onReading,
  onUsePackage,
}: {
  marking: string;
  readings: Record<string, string>;
  onReading: (key: string, value: string) => void;
  onUsePackage: (pkg: string) => void;
}) {
  const [state, setState] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; data?: LookupData; message?: string }>({ status: 'idle' });

  useEffect(() => {
    const text = marking.trim();
    if (text.length < 3) { setState({ status: 'idle' }); return; }
    const controller = new AbortController();
    let current = true;                 // false once this marking has been replaced: a late answer must not be shown under a newer one
    setState({ status: 'loading' });
    const timer = window.setTimeout(() => {
      fetch(`/api/proxy/engineering/parts/lookup?marking=${encodeURIComponent(text)}`, { cache: 'no-store', signal: controller.signal })
        .then((response) => response.json())
        .then((body: unknown) => {
          if (!body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The lookup failed.'));
          if (current) setState({ status: 'ready', data: body as LookupData });
        })
        .catch((caught: unknown) => {
          if (!current || (caught instanceof DOMException && caught.name === 'AbortError')) return;
          setState({ status: 'error', message: caught instanceof Error ? caught.message : 'The lookup failed.' });
        });
    }, 400);
    return () => { current = false; window.clearTimeout(timer); controller.abort(); };
  }, [marking]);

  const { status, data } = state;
  const recorded = data ? data.gates.filter((g) => (readings[g.key] ?? '').trim() !== '').length : 0;

  return (
    <div className="col-span-2 rounded-lg border border-stone-800 bg-stone-950/60 p-2.5 text-xs" data-testid="lookup-panel" data-status={status}>
      <div className="font-medium text-stone-100">What KiCad&apos;s library says</div>
      {status === 'idle' ? <p className="mt-1 leading-5 text-stone-500">Type the marking (3 characters or more) to look it up.</p> : null}
      {status === 'loading' && !data ? <p className="mt-1 flex items-center gap-1.5 text-stone-400"><LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" />Looking it up</p> : null}
      {status === 'error' ? <p role="alert" className="mt-1 leading-5 text-red-300" data-testid="lookup-error">{state.message}</p> : null}
      {data && status !== 'idle' ? (
        <div className={status === 'loading' ? 'opacity-60' : ''}>
          {!data.libraries_available ? <p className="mt-1 leading-5 text-amber-200">KiCad&apos;s libraries are not installed on the server, so there is nothing to look up in.</p> : null}
          {data.libraries_available && data.matches.length === 0 ? (
            <div className="mt-1 leading-5 text-stone-400" data-testid="lookup-none">
              <p>{data.reason ?? 'KiCad\'s library has nothing under this marking. That does not mean it is fake: many chips are not in it.'}</p>
              <p className="mt-1">
                <a href={`https://duckduckgo.com/?q=${encodeURIComponent(`${data.query} datasheet`)}`} target="_blank" rel="noreferrer noopener" className="text-sky-300 underline-offset-2 hover:underline">Search for its datasheet</a>
                {data.search_links.smd_code ? <> · <a href={data.search_links.smd_code} target="_blank" rel="noreferrer noopener" className="text-sky-300 underline-offset-2 hover:underline" data-testid="lookup-smd-link">Look it up as a top-mark code</a></> : null}
              </p>
            </div>
          ) : null}
          {data.matches.length ? (
            <ul className="mt-1.5 space-y-2" data-testid="lookup-matches">
              {data.matches.slice(0, 4).map((match) => {
                const pkg = match.tier === 'family' ? null : packageFromFootprint(match.footprint);
                return (
                  <li key={`${match.library}-${match.name}`} className="rounded border border-stone-800 p-1.5" data-tier={match.tier}>
                    <div className="flex items-center gap-1.5">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${TIER_CLASS[match.tier]}`}>{TIER_LABEL[match.tier]}</span>
                      <span className="font-semibold text-stone-100">{match.name}</span>
                      <span className="text-stone-500">{match.library}</span>
                    </div>
                    <p className="mt-0.5 leading-4 text-stone-300">{match.description || 'No description.'}</p>
                    <p className="mt-0.5 text-[10px] leading-4 text-stone-500">{match.tier_text}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {match.datasheet ? <a href={match.datasheet} target="_blank" rel="noreferrer noopener" className="text-sky-300 underline-offset-2 hover:underline">Datasheet</a> : null}
                      {pkg ? <button type="button" data-testid="lookup-use-package" onClick={() => onUsePackage(pkg)} className="rounded border border-stone-700 px-1.5 py-0.5 text-stone-200 hover:bg-stone-800">Use package {pkg}</button> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {data.gates.length ? (
            <div className="mt-2" data-testid="lookup-gates">
              <div className="font-medium text-stone-100">Measure these and write the readings down</div>
              <p className="mt-0.5 text-[10px] leading-4 text-stone-500">The pin names are from the library&apos;s {data.gates_from}, not read from your chip: confirm them in its datasheet. Write down what you measure; only the datasheet says what it should be. None of these readings shows a removed chip works.</p>
              <ul className="mt-1.5 space-y-2">
                {data.gates.map((gate) => (
                  <li key={gate.key} className="leading-4 text-stone-300">
                    <div>{gate.instruction}</div>
                    <label className="mt-1 flex items-center gap-1.5 text-stone-400">Reading
                      <input
                        data-testid="lookup-reading"
                        value={readings[gate.key] ?? ''}
                        maxLength={40}
                        placeholder="what you measured"
                        onChange={(event) => onReading(gate.key, event.target.value)}
                        className="min-w-0 flex-1 rounded border border-stone-700 bg-stone-950 px-1.5 py-0.5 text-stone-100"
                      />
                    </label>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-[11px] text-stone-400" data-testid="lookup-recorded">{recorded} of {data.gates.length} readings recorded</p>
            </div>
          ) : null}
          {data.source ? <p className="mt-2 text-[10px] leading-4 text-stone-600">{data.source.name} {data.source.version}, {data.source.symbols.toLocaleString()} parts. {data.source.note}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
