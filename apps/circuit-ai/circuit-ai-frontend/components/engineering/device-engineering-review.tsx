'use client';

import { useEffect, useRef, useState } from 'react';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload } from '@/lib/proxy-client';

type Input = { name: string; value?: unknown; unit?: string; basis: 'sourced' | 'assumed'; source: string; url?: string };
type Check = { id: string; title: string; status: string; summary: string; inputs: Input[]; limits: string[] };
type Review = {
  schema_version: string; authority: string; physical_correctness: string; firmware_authorized: boolean; power_on_authorized: boolean;
  domains: { id: string; title: string; checks: Check[] }[]; counts: Record<string, number>;
  assumptions: Input[]; not_assessed: { domain: string; why: string }[];
};

const LABEL: Record<string, string> = {
  exceeds_limit: 'Over a limit', advisory: 'Needs checking', within_limit_under_assumptions: 'Under the limit, if the assumptions hold', not_assessed: 'Not assessed',
};
const TONE: Record<string, string> = {
  exceeds_limit: 'border-red-500/40 bg-red-950/40 text-red-100', advisory: 'border-amber-400/40 bg-amber-950/30 text-amber-100',
  within_limit_under_assumptions: 'border-stone-600 bg-stone-900 text-stone-200', not_assessed: 'border-stone-700 bg-stone-900 text-stone-400',
};

export function DeviceEngineeringReview({ specText, enabled }: { specText: string; enabled: boolean }) {
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
    setReview(null);
    setError('');
    setBusy(false);
    return () => { generation.current += 1; controller.current?.abort(); };
  }, [specText, enabled]);

  const run = async () => {
    const id = ++generation.current;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError('');
    setReview(null);
    try {
      const response = await fetch('/api/proxy/engineering/devices/engineering', {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: specText, signal: request.signal, cache: 'no-store',
      });
      const body = await readJsonPayload<unknown>(response);
      if (!response.ok || !body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The engineering review could not complete.'));
      const value = body as Review;
      if (value.schema_version !== 'hardware_splicer.device_engineering_review.v1' || value.physical_correctness !== 'UNPROVEN'
        || value.firmware_authorized !== false || value.power_on_authorized !== false || !Array.isArray(value.domains)) {
        throw new Error('The backend did not return a bounded engineering review.');
      }
      if (id === generation.current && !request.signal.aborted) setReview(value);
    } catch (caught) {
      if (id === generation.current && !request.signal.aborted) setError(caught instanceof Error ? caught.message : 'The engineering review could not complete.');
    } finally {
      if (id === generation.current) setBusy(false);
    }
  };

  const download = () => {
    if (!review) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(review, null, 2) + '\n'], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'device-engineering-review.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-engineering">
    <h2 className="text-sm font-semibold text-stone-100">Engineering review</h2>
    <p className="mt-1 text-xs leading-5 text-stone-400">What this layout implies for the I2C bus, the USB supply, heat, the antenna, fit and printing, with every number marked as sourced or assumed. It reports limits and things to check. It cannot show that a design works.</p>
    <button type="button" data-testid="device-engineering-start" onClick={() => void run()} disabled={!enabled || busy} className="mt-2 rounded-md bg-stone-800 px-3 py-2 text-xs font-medium text-stone-100 hover:bg-stone-700 disabled:opacity-50">
      {busy ? 'Reviewing…' : 'Review the engineering'}
    </button>
    {!enabled ? <p className="mt-1 text-xs text-amber-200">Check this wiring and resolve its findings first.</p> : null}
    {error ? <p role="alert" data-testid="device-engineering-error" className="mt-2 text-xs text-amber-200">{error}</p> : null}
    {review && enabled ? <div className="mt-3 space-y-3" data-testid="device-engineering-result">
      <p role="status" className="text-xs text-stone-300" data-testid="device-engineering-counts">
        {review.counts.exceeds_limit ?? 0} over a limit · {review.counts.advisory ?? 0} to check · {review.counts.within_limit_under_assumptions ?? 0} under a limit · {review.counts.not_assessed ?? 0} not assessed
      </p>
      <p className="text-[11px] leading-4 text-stone-400">{review.authority}</p>
      {review.domains.map((domain) => <div key={domain.id} className="space-y-1" data-testid="device-engineering-domain">
        <h3 className="text-xs font-semibold text-stone-200">{domain.title}</h3>
        {domain.checks.map((check) => <details key={check.id} open={check.status === 'exceeds_limit'} className="rounded border border-stone-700 text-xs" data-testid="device-engineering-check" data-status={check.status} data-check={check.id}>
          <summary className="flex min-h-9 cursor-pointer items-start gap-2 px-2 py-1.5">
            <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${TONE[check.status] ?? TONE.not_assessed}`}>{LABEL[check.status] ?? check.status}</span>
            <span className="min-w-0 break-words">{check.title}</span>
          </summary>
          <div className="space-y-1 px-2 pb-2">
            <p>{check.summary}</p>
            {check.limits.map((text) => <p key={text} className="text-stone-400">Limit: {text}</p>)}
            {check.inputs.length ? <ul className="space-y-0.5 text-[11px] text-stone-400">
              {check.inputs.map((input) => <li key={input.name}>
                <span className={input.basis === 'sourced' ? 'text-emerald-300' : 'text-amber-200'}>{input.basis === 'sourced' ? 'Sourced' : 'Assumed'}</span>{' '}
                {input.url ? <a className="underline" href={input.url} target="_blank" rel="noreferrer noopener">{input.source}</a> : input.source}
              </li>)}
            </ul> : null}
          </div>
        </details>)}
      </div>)}
      <details className="rounded border border-stone-700 text-xs" data-testid="device-engineering-not-assessed">
        <summary className="min-h-9 cursor-pointer px-2 py-1.5">Not assessed ({review.not_assessed.length})</summary>
        <ul className="space-y-1 px-2 pb-2 text-stone-400">{review.not_assessed.map((row) => <li key={row.domain}><span className="text-stone-200">{row.domain}.</span> {row.why}</li>)}</ul>
      </details>
      <p className="text-[11px] text-stone-400">Physical correctness: {review.physical_correctness}. Flashing and power authorization remain closed.</p>
      <button type="button" data-testid="device-engineering-download" onClick={download} className="rounded-md bg-stone-800 px-3 py-2 text-xs">Download review</button>
    </div> : null}
  </section>;
}
