'use client';

import { useState } from 'react';
import Link from 'next/link';
import { BadgeCheck, Crosshair, Eye, EyeOff, LoaderCircle } from 'lucide-react';
import { changeKey } from '@/lib/artifact-diff';
import { useOperatorToken } from '@/lib/operator-token';
import type { Candidate, ReviewState } from '@/lib/project-candidates';

function when(iso: string | null | undefined) {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function checksLine(candidate: Candidate) {
  const checks = candidate.checks;
  if (!checks || !checks.ran) {
    return checks?.reason ? `Design-rule check did not run: ${checks.reason}` : 'Design-rule check did not run';
  }
  const label = candidate.kind === 'pcb' ? 'DRC' : 'ERC';
  const delta = checks.new_violations ?? 0;
  const after = checks.after?.total;
  return `${label} reports ${delta} new ${delta === 1 ? 'violation' : 'violations'}${typeof after === 'number' ? ` (${after} total)` : ''}`;
}

/** The proposal in a few words, so a confirmation can say exactly which one it applies to. */
function describe(candidate: Candidate) {
  const first = candidate.applied?.[0];
  const what = first ? `${first.op}${first.target?.ref ? ` ${first.target.ref}` : ''}` : 'a change';
  const extra = (candidate.applied?.length || 0) > 1 ? ` and ${(candidate.applied?.length || 1) - 1} more` : '';
  return `${candidate.created_by}'s proposal (${what}${extra})`;
}

type Standing = { label: string; tone: string };

/** One honest word for where a proposal stands. Only an accepted proposal ever reads as applied. */
function standing(candidate: Candidate, state: ReviewState | undefined): Standing {
  if (state?.status === 'accepted') return { label: `Applied as revision ${state.accepted_revision ?? '?'}`, tone: 'border-emerald-300 bg-emerald-50 text-emerald-900' };
  if (state?.status === 'rejected') return { label: 'Rejected', tone: 'border-stone-300 bg-stone-100 text-stone-700' };
  if (state?.status === 'missing') return { label: 'Review missing', tone: 'border-red-300 bg-red-50 text-red-800' };
  if (state?.stale) return { label: 'Out of date', tone: 'border-stone-300 bg-stone-100 text-stone-700' };
  return { label: 'Not applied', tone: 'border-amber-300 bg-amber-50 text-amber-900' };
}

function ProposalCard({
  candidate,
  projectId,
  nextRevision,
  previewing,
  onPreview,
  onFocusChange,
  decide,
}: {
  candidate: Candidate;
  projectId: string;
  nextRevision: number | null;
  previewing: boolean;
  onPreview: (candidate: Candidate | null) => void;
  onFocusChange: (key: string) => void;
  decide: (candidateId: string, decision: 'accepted' | 'rejected', note: string) => Promise<unknown>;
}) {
  const { token, setToken } = useOperatorToken();
  const [note, setNote] = useState('');
  const [confirming, setConfirming] = useState<'accepted' | 'rejected' | null>(null);
  const [busy, setBusy] = useState<'accepted' | 'rejected' | null>(null);
  const [error, setError] = useState('');
  const state = candidate.review_state;
  const badge = standing(candidate, state);
  const summary = candidate.diff?.summary;
  const changes = candidate.diff?.changes || [];
  const open = (state?.status ?? 'pending') === 'pending' && !state?.stale;

  async function submit(decision: 'accepted' | 'rejected') {
    setBusy(decision);
    setError('');
    try {
      await decide(candidate.candidate_id, decision, note.trim());
      setConfirming(null);
      setNote('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The decision could not be recorded.');
    } finally {
      setBusy(null);
    }
  }

  const action = 'inline-flex h-7 items-center justify-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium disabled:cursor-not-allowed disabled:opacity-60';

  return (
    <li className={`rounded-md border bg-white p-3 ${previewing ? 'border-stone-900' : 'border-stone-200'}`} data-testid="proposal-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1 truncate text-xs font-medium text-stone-900">
            {candidate.created_by}
            {candidate.verified ? <BadgeCheck className="h-3 w-3 shrink-0 text-emerald-700" aria-label="Operator identity confirmed by the server" /> : null}
          </div>
          <div className="text-[10px] text-stone-500">{candidate.kind === 'pcb' ? 'PCB' : 'Schematic'} · from revision {candidate.base_revision}{when(candidate.created_at) ? ` · ${when(candidate.created_at)}` : ''}</div>
        </div>
        <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${badge.tone}`}>{badge.label}</span>
      </div>

      {candidate.note ? <p className="m-0 mt-2 text-xs leading-5 text-stone-700">“{candidate.note}”</p> : null}

      {candidate.applied?.length ? (
        <ul className="m-0 mt-2 list-none space-y-0.5 p-0 text-[11px] text-stone-700">
          {candidate.applied.slice(0, 4).map((item, index) => (
            <li key={index} className="truncate">{item.op}{item.target?.ref ? ` ${item.target.ref}` : ''}{item.detail ? ` · ${item.detail}` : ''}</li>
          ))}
          {candidate.applied.length > 4 ? <li className="text-stone-400">and {candidate.applied.length - 4} more</li> : null}
        </ul>
      ) : null}

      {summary ? (
        <div className="mt-2 flex gap-2 text-[11px]" aria-label="Changes in this proposal">
          <span className="text-emerald-700">+{summary.added}</span>
          <span className="text-red-700">−{summary.removed}</span>
          <span className="text-amber-700">~{summary.changed}</span>
        </div>
      ) : null}

      {changes.length ? (
        <ul className="m-0 mt-1.5 list-none space-y-0.5 p-0">
          {changes.slice(0, 6).map((change, index) => (
            <li key={changeKey(change, index)}>
              <button
                type="button"
                onClick={() => { if (!previewing) onPreview(candidate); onFocusChange(changeKey(change, index)); }}
                className="group flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-[11px] text-stone-600 hover:bg-stone-100 hover:text-stone-900 focus-visible:bg-stone-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-stone-500"
                title="Show this change on the file"
              >
                <Crosshair className="h-3 w-3 shrink-0 text-stone-400 group-hover:text-stone-700" aria-hidden="true" />
                <span className="min-w-0 truncate">{change.label}</span>
              </button>
            </li>
          ))}
          {changes.length > 6 ? <li className="px-1 text-[10px] text-stone-400">and {changes.length - 6} more</li> : null}
        </ul>
      ) : null}

      <div className="mt-2 text-[10px] leading-4 text-stone-500">{checksLine(candidate)}. Reported for the reviewer; it does not accept or reject anything.</div>

      <button
        type="button"
        onClick={() => onPreview(previewing ? null : candidate)}
        className={`${action} mt-2 border border-stone-300 text-stone-700 hover:bg-stone-50`}
      >
        {previewing ? <EyeOff className="h-3 w-3" aria-hidden="true" /> : <Eye className="h-3 w-3" aria-hidden="true" />}
        {previewing ? 'Stop previewing' : 'Preview with changes marked'}
      </button>

      {open ? (
        <div className="mt-3 border-t border-stone-200 pt-2.5">
          {!token ? (
            <details className="text-[11px] text-stone-600">
              <summary className="cursor-pointer select-none font-medium text-stone-700">Deciding needs an operator token</summary>
              <p className="mt-1 leading-4 text-stone-500">Accepting creates a new revision, so it is recorded under an identity the server has verified, not a typed name.</p>
              <input
                type="password"
                autoComplete="off"
                aria-label="Operator token"
                placeholder="Paste your operator token"
                onChange={(event) => setToken(event.target.value.trim())}
                className="mt-1.5 w-full rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-900 outline-none focus:border-stone-500"
              />
              <p className="mt-1 leading-4 text-stone-400">Kept for this browser tab only.</p>
            </details>
          ) : (
            <div className="space-y-2">
              <input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                maxLength={500}
                aria-label="Reason for the decision"
                placeholder="Reason (optional)"
                className="h-7 w-full rounded-md border border-stone-300 bg-white px-2 text-xs text-stone-900 outline-none focus:border-stone-500"
              />
              {confirming ? (
                <div className="rounded-md border border-stone-300 bg-stone-50 p-2" role="group" aria-label="Confirm decision">
                  <p className="m-0 text-[11px] leading-4 text-stone-700">
                    {confirming === 'accepted'
                      ? <>Make {nextRevision ? `revision ${nextRevision}` : 'the next revision'} from {describe(candidate)}. It does not verify the design or open fabrication.</>
                      : <>Reject {describe(candidate)}. It stays on record and can no longer be accepted.</>}
                  </p>
                  <div className="mt-2 flex gap-1.5">
                    <button type="button" disabled={busy !== null} onClick={() => void submit(confirming)} className={`${action} bg-stone-900 text-white hover:bg-stone-700`}>
                      {busy === confirming ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}{confirming === 'accepted' ? 'Make revision' : 'Reject proposal'}
                    </button>
                    <button type="button" disabled={busy !== null} onClick={() => setConfirming(null)} className={`${action} border border-stone-300 text-stone-700 hover:bg-white`}>Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <button type="button" onClick={() => setConfirming('accepted')} className={`${action} bg-stone-900 text-white hover:bg-stone-700`}>Accept as a new revision</button>
                  <button type="button" onClick={() => setConfirming('rejected')} className={`${action} border border-stone-300 text-stone-700 hover:bg-stone-50`}>Reject</button>
                </div>
              )}
              <button type="button" onClick={() => setToken('')} className="text-[10px] text-stone-400 underline">Remove operator token</button>
            </div>
          )}
          {error ? <div role="alert" className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] leading-4 text-red-800">{error}</div> : null}
        </div>
      ) : null}

      {state?.stale ? (
        <p className="mt-3 border-t border-stone-200 pt-2.5 text-[11px] leading-4 text-stone-500">
          A newer revision exists, so this proposal can no longer be accepted. Make the change again from the latest revision.
        </p>
      ) : null}

      {state?.status === 'accepted' || state?.status === 'rejected' ? (
        <div className="mt-3 border-t border-stone-200 pt-2.5 text-[11px] leading-4 text-stone-600">
          {state.status === 'accepted' ? 'Accepted' : 'Rejected'} by <span className="font-medium text-stone-800">{state.decided_by || 'an operator'}</span>{when(state.decided_at) ? ` · ${when(state.decided_at)}` : ''}
          {state.note ? <span className="block text-stone-500">“{state.note}”</span> : null}
          {state.status === 'accepted' && state.accepted_revision ? (
            <Link
              href={`/engineering/evidence/compare?project=${encodeURIComponent(projectId)}&base=${candidate.base_revision}&candidate=${state.accepted_revision}`}
              className="mt-1 inline-block font-medium text-stone-900 underline"
            >
              Compare revision {candidate.base_revision} with {state.accepted_revision}
            </Link>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

/**
 * Edits that have been proposed. A proposal is held for review: the project's revisions do not change when one is
 * created. Only an operator the server has verified can accept one, and accepting makes a revision, nothing more.
 */
export function ProposalsPanel({
  candidates,
  loading,
  projectId,
  nextRevision,
  previewId,
  onPreview,
  onFocusChange,
  decide,
}: {
  candidates: Candidate[];
  loading: boolean;
  projectId: string;
  nextRevision: number | null;
  previewId: string | null;
  onPreview: (candidate: Candidate | null) => void;
  onFocusChange: (key: string) => void;
  decide: (candidateId: string, decision: 'accepted' | 'rejected', note: string) => Promise<unknown>;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3" data-testid="proposals-panel">
      {loading && !candidates.length ? <div className="flex items-center gap-2 text-xs text-stone-500"><LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Loading proposals</div> : null}
      {!loading && !candidates.length ? (
        <div className="rounded-md border border-dashed border-stone-300 p-3 text-xs leading-5 text-stone-500">
          No proposals yet. Choose Edit above the viewer, select a part, and describe a change. It is held here for review and does not alter the design.
        </div>
      ) : null}
      <ul className="m-0 list-none space-y-2.5 p-0">
        {candidates.map((candidate) => (
          <ProposalCard
            key={candidate.candidate_id}
            candidate={candidate}
            projectId={projectId}
            nextRevision={nextRevision}
            previewing={previewId === candidate.candidate_id}
            onPreview={onPreview}
            onFocusChange={onFocusChange}
            decide={decide}
          />
        ))}
      </ul>
    </div>
  );
}
