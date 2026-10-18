'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Check, CircleHelp, LoaderCircle, Plus, X } from 'lucide-react';
import { OperatorTokenField, WhoChip } from '@/components/engineering/mission-detail';
import { useOperatorToken } from '@/lib/operator-token';
import { openMission, readParts, type Mission, type PartsReading } from '@/lib/missions';

const lines = (text: string) => text.split('\n').map((line) => line.trim()).filter(Boolean);

function ReadingList({ reading }: { reading: PartsReading }) {
  const matched = reading.fragments.filter((fragment) => fragment.matches.length && !fragment.unread?.length).length;
  const total = reading.fragments.length;
  return (
    <div data-testid="parts-reading" className="mt-3 rounded-xl border border-white/10 bg-black/25 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <WhoChip who="system" label="How HS reads your list" />
        <span className="text-xs text-slate-400">{matched} of {total} {total === 1 ? 'line' : 'lines'} matched a part it has data for</span>
      </div>
      <ul className="mt-3 space-y-2">
        {reading.fragments.map((fragment, index) => {
          const hasMatch = fragment.matches.length > 0;
          const unread = fragment.unread || [];
          const generic = fragment.matches.some((match) => match.basis === 'generic_word');
          const state = !hasMatch ? 'none' : unread.length ? 'partial' : generic ? 'generic' : 'ok';
          return (
            <li key={`${fragment.text}-${index}`} data-status={state} className="flex gap-3 text-sm leading-6">
              {state === 'ok' ? <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-300" aria-label="Matched" />
                : state === 'none' ? <X className="mt-1 h-4 w-4 shrink-0 text-sky-300" aria-label="No data" />
                : <CircleHelp className="mt-1 h-4 w-4 shrink-0 text-amber-300" aria-label="Check this" />}
              <div className="min-w-0">
                <p className="text-slate-100">{fragment.text}</p>
                {hasMatch ? (
                  <p className="text-xs text-slate-400">
                    Read as {fragment.matches.map((match) => `${match.name}${match.quantity > 1 ? ` ×${match.quantity}` : ''}`).join(' and ')}
                  </p>
                ) : (
                  <p className="text-xs text-sky-200/90">
                    HS has no data for this{fragment.note ? `. ${fragment.note}` : '.'}
                  </p>
                )}
                {generic ? <p className="text-xs text-amber-200">Matched on a generic word. Check it is the part you have.</p> : null}
                {unread.length ? <p className="text-xs text-amber-200">It also names {unread.join(', ')}, which HS cannot place, so this line counts as not matched.</p> : null}
              </div>
            </li>
          );
        })}
      </ul>
      {matched < total ? (
        <p className="mt-3 border-t border-white/10 pt-3 text-xs leading-5 text-slate-400">
          A mission can only end <em>ready</em> if every line you list is in the design. Lines HS has no data for will end it as
          “blocked: HS has no data for a part you listed”, and nothing will be dropped to avoid that.
        </p>
      ) : null}
      {!reading.controller ? (
        <p className="mt-2 text-xs leading-5 text-amber-200/90">
          No controller HS has data for is named, so it cannot draft a design from this list.
        </p>
      ) : null}
    </div>
  );
}

export function MissionStart({ projectId, onOpened, onCancel }: { projectId: string; onOpened: (mission: Mission) => void; onCancel: () => void }) {
  const { token, setToken } = useOperatorToken();
  const [goal, setGoal] = useState('');
  const [parts, setParts] = useState('');
  const [constraints, setConstraints] = useState('');
  const [limits, setLimits] = useState({ jobs: '', designs: '', repairs: '' });
  const [reading, setReading] = useState<PartsReading | null>(null);
  const [readError, setReadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // Show how HS reads the list as it is typed, before anything is opened.
  useEffect(() => {
    const text = parts.trim();
    if (!text) {
      setReading(null);
      setReadError('');
      return;
    }
    let live = true;
    const timer = window.setTimeout(() => {
      readParts(text)
        .then((parsed) => { if (live) { setReading(parsed); setReadError(''); } })
        .catch((caught: unknown) => { if (live) { setReading(null); setReadError(caught instanceof Error ? caught.message : 'Could not read the list'); } });
    }, 400);
    return () => { live = false; window.clearTimeout(timer); };
  }, [parts]);

  const ready = goal.trim().length > 0 && lines(parts).length > 0 && Boolean(token) && !busy;

  async function submit() {
    setBusy(true);
    setError('');
    const budgets: Record<string, number> = {};
    if (limits.jobs) budgets.max_operator_jobs = Number(limits.jobs);
    if (limits.designs) budgets.max_candidates = Number(limits.designs);
    if (limits.repairs) budgets.max_repairs_per_candidate = Number(limits.repairs);
    try {
      onOpened(await openMission(projectId, {
        goal: goal.trim(),
        inventory: lines(parts),
        constraints: lines(constraints),
        ...(Object.keys(budgets).length ? { budgets } : {}),
      }, token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not open the mission');
    } finally {
      setBusy(false);
    }
  }

  const field = 'mt-1 w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-300/60';
  return (
    <section aria-label="Start a mission" className="rounded-2xl border border-amber-300/30 bg-amber-950/10 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold text-white">Start a mission</h2>
        <WhoChip who="human" label="Written by you" />
      </div>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
        Say what you want and what you have. This is the one thing the agent cannot change. You will read it again and accept it
        before anything runs.
      </p>

      <label className="mt-5 block text-xs font-medium text-slate-300">
        What do you want to make?
        <textarea data-testid="mission-goal-input" value={goal} onChange={(event) => setGoal(event.target.value)} rows={2} maxLength={500}
          placeholder="A small desk display that shows temperature and humidity" className={field} />
      </label>

      <label className="mt-4 block text-xs font-medium text-slate-300">
        The parts you have, one per line
        <textarea data-testid="mission-parts-input" value={parts} onChange={(event) => setParts(event.target.value)} rows={5}
          placeholder={'ESP32\nBME280\n0.96 inch OLED'} className={`${field} font-mono`} />
      </label>
      {readError ? <p className="mt-2 flex items-start gap-2 text-xs text-amber-200"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {readError}</p> : null}
      {reading ? <ReadingList reading={reading} /> : null}

      <label className="mt-4 block text-xs font-medium text-slate-300">
        Constraints in your own words <span className="font-normal text-slate-500">(optional; noted for the agent, not enforced by HS)</span>
        <textarea value={constraints} onChange={(event) => setConstraints(event.target.value)} rows={2} placeholder={'Powered over USB\nUnder NT$800'} className={field} />
      </label>

      <details className="mt-4 rounded-xl border border-white/10 p-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-300">Limits <span className="font-normal text-slate-500">(defaults: 20 checks, 3 designs, 3 repairs each)</span></summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {([['jobs', 'Checks HS may run'], ['designs', 'Designs the agent may try'], ['repairs', 'Repairs per design']] as const).map(([key, label]) => (
            <label key={key} className="text-xs text-slate-400">{label}
              <input type="number" min={1} value={limits[key]} onChange={(event) => setLimits({ ...limits, [key]: event.target.value })} className={field} />
            </label>
          ))}
        </div>
      </details>

      <div className="mt-5 flex flex-wrap items-end gap-3">
        <OperatorTokenField token={token} setToken={setToken} />
        <button type="button" onClick={submit} disabled={!ready}
          className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40">
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Open this mission
        </button>
        <button type="button" onClick={onCancel} className="rounded-full border border-white/20 px-5 py-2.5 text-sm text-slate-200 hover:bg-white/5">Cancel</button>
      </div>
      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/40 bg-red-950/40 px-3 py-2 text-sm text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </p>
      ) : null}
    </section>
  );
}
