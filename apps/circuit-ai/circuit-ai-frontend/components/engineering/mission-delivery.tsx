'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Download, FileArchive, LoaderCircle, PackageCheck } from 'lucide-react';
import { OperatorTokenField } from '@/components/engineering/mission-detail';
import { useOperatorToken } from '@/lib/operator-token';
import { buildPackage, packageUrl, stageDesign, type Mission, type PackageManifest } from '@/lib/missions';

const DELIVERABLES: Record<string, string> = {
  firmware: 'Firmware',
  firmware_test: 'Firmware test',
  enclosure: 'Enclosure',
  physical: 'Checks only you can do',
};

const STATUS_WORDS: Record<string, { label: string; className: string }> = {
  generated: { label: 'Generated', className: 'border-emerald-300/40 bg-emerald-400/10 text-emerald-100' },
  blocked: { label: 'HS could not generate this', className: 'border-amber-300/50 bg-amber-950/30 text-amber-100' },
  not_run: { label: 'Not run', className: 'border-slate-500/50 bg-slate-800/60 text-slate-200' },
  modeled_passed: { label: 'Passed in a software model', className: 'border-emerald-300/40 bg-emerald-400/10 text-emerald-100' },
  modeled_partial: { label: 'Partly modeled', className: 'border-amber-300/50 bg-amber-950/30 text-amber-100' },
  modeled_failed: { label: 'Failed in a software model', className: 'border-red-400/50 bg-red-950/40 text-red-100' },
  required: { label: 'Still required', className: 'border-amber-300/50 bg-amber-950/30 text-amber-100' },
};

/** After READY: the package a person builds from, and the step that puts the design in front of a reviewer. */
export function DeliveryPanel({ mission, onChanged }: { mission: Mission; onChanged: () => void }) {
  const { token, setToken } = useOperatorToken();
  const [manifest, setManifest] = useState<PackageManifest | null>(null);
  const [busy, setBusy] = useState<'build' | 'stage' | ''>('');
  const [error, setError] = useState('');
  if (mission.terminal?.state !== 'READY_FOR_HUMAN_BUILD') return null;

  async function run(kind: 'build' | 'stage') {
    setBusy(kind);
    setError('');
    try {
      if (kind === 'build') setManifest(await buildPackage(mission.project_id, mission.mission_id));
      else {
        await stageDesign(mission.project_id, mission.mission_id, token);
        onChanged();
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'That did not work');
    } finally {
      setBusy('');
    }
  }

  return (
    <section className="rounded-2xl border border-emerald-300/25 bg-emerald-950/15 p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-emerald-100"><PackageCheck className="h-4 w-4" /> Hand-off</h3>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
        One package with your request, the design, the exact check results it rests on, and whatever firmware and enclosure HS could generate.
        Anything HS could not generate is named, never faked.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => run('build')} disabled={Boolean(busy)} className="inline-flex items-center gap-2 rounded-full bg-emerald-300 px-5 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-emerald-200 disabled:opacity-50">
          {busy === 'build' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FileArchive className="h-4 w-4" />} {manifest ? 'Rebuild' : 'Build'} the package
        </button>
        {manifest ? (
          <a href={packageUrl(mission.project_id, mission.mission_id)} download className="inline-flex items-center gap-2 rounded-full border border-emerald-300/50 px-5 py-2.5 text-sm font-semibold text-emerald-100 hover:bg-emerald-300/10">
            <Download className="h-4 w-4" /> Download ZIP
          </a>
        ) : null}
      </div>

      {manifest ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-black/25 p-4">
          <ul className="grid gap-2 sm:grid-cols-2">
            {Object.entries(manifest.deliverables).map(([key, item]) => {
              const words = STATUS_WORDS[item.status] || { label: item.status, className: 'border-slate-500/50 text-slate-200' };
              return (
                <li key={key} className="rounded-lg border border-white/10 p-3">
                  <p className="text-xs text-slate-400">{DELIVERABLES[key] || key}</p>
                  <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${words.className}`}>{words.label}</span>
                  {item.reason ? <p className="mt-1.5 text-xs leading-5 text-slate-400">{item.reason}</p> : null}
                </li>
              );
            })}
          </ul>
          <p className="mt-3 break-all text-[11px] text-slate-500">Package fingerprint (sha256): {manifest.package_sha256}</p>
        </div>
      ) : null}

      <div className="mt-5 border-t border-white/10 pt-4">
        <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Put the design up for review</h4>
        {mission.staged ? (
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Opened as review <code className="rounded bg-black/40 px-1 py-0.5 text-xs">{mission.staged.review_id}</code>. It becomes part of the project only if you accept that review in{' '}
            <Link href="/engineering/evidence" className="text-cyan-200 underline underline-offset-2 hover:text-white">Project review</Link>.
          </p>
        ) : (
          <>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              This opens a review of the design and the repairs that produced it. Nothing changes in your project until a person accepts that review.
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              {!token ? <OperatorTokenField token={token} setToken={setToken} /> : null}
              <button type="button" onClick={() => run('stage')} disabled={Boolean(busy) || !token} className="inline-flex items-center gap-2 rounded-full border border-amber-300/50 px-5 py-2.5 text-sm font-semibold text-amber-100 hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:opacity-40">
                {busy === 'stage' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null} Open a review
              </button>
            </div>
          </>
        )}
      </div>
      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/40 bg-red-950/40 px-3 py-2 text-sm text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </p>
      ) : null}
    </section>
  );
}
