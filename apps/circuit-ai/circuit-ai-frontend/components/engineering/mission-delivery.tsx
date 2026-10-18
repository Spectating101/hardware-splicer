'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Check, Download, FileArchive, LoaderCircle, PackageCheck, X } from 'lucide-react';
import { OperatorTokenField } from '@/components/engineering/mission-detail';
import { useOperatorToken } from '@/lib/operator-token';
import { buildPackage, decideReview, fetchReview, packageUrl, stageDesign, type Mission, type PackageManifest, type StagedReview } from '@/lib/missions';

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

/** The staged review: what it is, and the person's decision on it. Accepting is the only step that touches the project. */
function StagedReviewBox({ mission, reviewId }: { mission: Mission; reviewId: string }) {
  const { token, setToken } = useOperatorToken();
  const [review, setReview] = useState<StagedReview | null>(null);
  const [busy, setBusy] = useState<'accepted' | 'rejected' | ''>('');
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    fetchReview(mission.project_id, reviewId).then((row) => { if (live) setReview(row); }).catch(() => { /* shown as unknown below */ });
    return () => { live = false; };
  }, [mission.project_id, reviewId]);

  async function decide(decision: 'accepted' | 'rejected') {
    setBusy(decision);
    setError('');
    try {
      setReview(await decideReview(mission.project_id, reviewId, decision, token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not record the decision');
    } finally {
      setBusy('');
    }
  }

  const status = review?.status;
  return (
    <div data-testid="staged-review" data-status={status || 'unknown'} className="mt-2 rounded-xl border border-white/10 bg-black/25 p-4">
      <p className="text-sm leading-6 text-slate-200">
        Review <code className="rounded bg-black/40 px-1 py-0.5 text-xs">{reviewId}</code>:{' '}
        {status === 'accepted' ? (
          <strong className="font-semibold text-emerald-200">accepted by {review?.decision?.actor}, now revision {review?.decision?.accepted_revision} of the project</strong>
        ) : status === 'rejected' ? (
          <strong className="font-semibold text-slate-100">rejected by {review?.decision?.actor}; the project was not changed</strong>
        ) : status === 'pending' ? (
          <strong className="font-semibold text-amber-200">waiting for your decision</strong>
        ) : (
          <span className="text-slate-400">status unknown</span>
        )}
      </p>
      {status === 'pending' ? (
        <>
          <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-400">
            Accepting adds this design, its checks and its repair history to the project’s record as a new revision. It does not
            authorize building, flashing or powering anything. Rejecting leaves the project as it is.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <OperatorTokenField token={token} setToken={setToken} />
            <button type="button" onClick={() => decide('accepted')} disabled={Boolean(busy) || !token}
              className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-stone-900 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40">
              {busy === 'accepted' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Accept into the project
            </button>
            <button type="button" onClick={() => decide('rejected')} disabled={Boolean(busy) || !token}
              className="inline-flex items-center gap-2 rounded-full border border-white/25 px-5 py-2.5 text-sm font-semibold text-slate-100 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40">
              {busy === 'rejected' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />} Reject
            </button>
          </div>
        </>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/40 bg-red-950/40 px-3 py-2 text-sm text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </p>
      ) : null}
    </div>
  );
}

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
        <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Add the design to your project</h4>
        {mission.staged ? (
          <StagedReviewBox mission={mission} reviewId={mission.staged.review_id} />
        ) : (
          <>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              First this opens a review of the design and the repairs that produced it. Nothing changes in your project until you accept that review.
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <OperatorTokenField token={token} setToken={setToken} />
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
