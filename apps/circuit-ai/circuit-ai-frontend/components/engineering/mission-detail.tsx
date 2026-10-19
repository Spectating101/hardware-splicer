'use client';

import { useState } from 'react';
import { AlertTriangle, Check, CircleDashed, Clipboard, Hourglass, KeyRound, LoaderCircle, Minus, X } from 'lucide-react';
import { useOperatorToken } from '@/lib/operator-token';
import {
  acceptMission,
  answerNeed,
  groundingOf,
  operationName,
  resultWords,
  TONE,
  verdictOf,
  WHO,
  type AuthorKind,
  type Mission,
  type MissionCandidate,
  type MissionNeed,
} from '@/lib/missions';

export function WhoChip({ who, label }: { who: AuthorKind; label?: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${WHO[who].chip}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${WHO[who].dot}`} />
      {label || WHO[who].label}
    </span>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#07111f]/70 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">{title}</h3>
        {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** What is and is not established about the physical world. Read from the mission, never assumed. */
function AuthorityStrip({ mission }: { mission: Mission }) {
  const items = [
    { label: 'Works on real hardware', value: mission.physical_correctness === 'UNPROVEN' ? 'Not proven' : mission.physical_correctness, ok: false },
    { label: 'Flashing firmware', value: mission.firmware_authorized ? 'Authorized' : 'Not authorized', ok: mission.firmware_authorized },
    { label: 'Powering the device', value: mission.power_on_authorized ? 'Authorized' : 'Not authorized', ok: mission.power_on_authorized },
  ];
  return (
    <ul aria-label="What is established about the physical world" className="mt-4 flex flex-wrap gap-2 border-t border-white/10 pt-4">
      {items.map((item) => (
        <li key={item.label} className="rounded-lg border border-white/10 bg-black/20 px-3 py-1.5 text-xs">
          <span className="text-slate-400">{item.label}: </span>
          <span className={item.ok ? 'font-semibold text-emerald-200' : 'font-semibold text-slate-200'}>{item.value}</span>
        </li>
      ))}
    </ul>
  );
}

export function VerdictPanel({ mission }: { mission: Mission }) {
  const verdict = verdictOf(mission);
  const tone = TONE[verdict.tone];
  const terminal = mission.terminal;
  const grounding = terminal ? groundingOf(terminal) : null;
  return (
    <section aria-label="Where this mission stands" className={`rounded-2xl border p-5 ${tone.panel}`}>
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Where this stands</p>
      <h2 data-testid="verdict-title" className={`mt-1 text-2xl font-semibold leading-tight ${tone.label}`}>{verdict.title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{verdict.meaning}</p>

      {terminal && grounding ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400">Established by</span>
            <WhoChip who={grounding.who} label={grounding.label} />
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-400">{grounding.detail}</p>
        </div>
      ) : null}
      {terminal?.reason ? (
        <div className="mt-3 text-sm leading-6">
          <span className="mr-2 align-middle"><WhoChip who="agent" label="The agent wrote" /></span>
          <span className="text-slate-300">“{terminal.reason}”</span>
        </div>
      ) : null}

      {terminal?.state === 'READY_FOR_HUMAN_BUILD' && terminal.physical_evidence_required?.length ? (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-200/80">Still yours to do</p>
          <ul className="mt-2 space-y-1.5">
            {terminal.physical_evidence_required.map((step) => (
              <li key={step} className="flex gap-2 text-sm leading-6 text-slate-300">
                <CircleDashed className="mt-1 h-3.5 w-3.5 shrink-0 text-emerald-300/70" /> {step}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <AuthorityStrip mission={mission} />
    </section>
  );
}

/**
 * The person's operator token: held for this browser tab only, sent only in its own header, never shown back.
 * Where it is a side detail and a token was already set when the panel appeared, it shows as "Token set" with Change and
 * Forget. Once the person types in it, it stays put: collapsing under the pointer would shift the buttons beside it and
 * swallow the click, and a mistyped token has to stay correctable.
 */
export function OperatorTokenField({ token, setToken, always = false }: { token: string; setToken: (value: string) => void; always?: boolean }) {
  const [editing, setEditing] = useState(false);
  if (token && !editing && !always) {
    return (
      <p className="flex items-center gap-2 text-xs text-slate-400">
        <KeyRound className="h-3.5 w-3.5" /> Your token is set for this tab.
        <button type="button" onClick={() => setEditing(true)} className="text-cyan-200 underline underline-offset-2 hover:text-white">Change</button>
        <button type="button" onClick={() => setToken('')} className="text-slate-400 underline underline-offset-2 hover:text-white">Forget</button>
      </p>
    );
  }
  return (
    <label className="min-w-[16rem] flex-1 text-xs text-slate-400">
      <span className="flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" /> Your operator token (kept in this tab only)</span>
      <input
        type="password"
        value={token}
        onChange={(event) => { setEditing(true); setToken(event.target.value); }}
        autoFocus={editing}
        autoComplete="off"
        spellCheck={false}
        className="mt-1 w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-300/60"
        placeholder="Paste the token you were given"
      />
    </label>
  );
}

export function AcceptPanel({ mission, onAccepted }: { mission: Mission; onAccepted: (mission: Mission) => void }) {
  const { token, setToken } = useOperatorToken();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (mission.accepted) return null;

  async function accept() {
    setBusy(true);
    setError('');
    try {
      onAccepted(await acceptMission(mission.project_id, mission.mission_id, token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not accept the mission');
    } finally {
      setBusy(false);
    }
  }

  const { budgets } = mission;
  return (
    <Section title="Your decision">
      <p className="max-w-3xl text-sm leading-6 text-slate-300">
        Accepting says the goal and parts below are what you want. It lets Hardware Splicer run its{' '}
        <strong className="font-semibold text-slate-100">software-only</strong> checks for the agent, up to{' '}
        {budgets.max_operator_jobs} checks and {budgets.max_candidates} designs. It does not power, flash or build anything,
        and you can only do it once.
      </p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <OperatorTokenField token={token} setToken={setToken} always />
        <button
          type="button"
          onClick={accept}
          disabled={busy || !token}
          className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Accept this mission
        </button>
      </div>
      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/40 bg-red-950/40 px-3 py-2 text-sm text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </p>
      ) : null}
    </Section>
  );
}

function lastReading(mission: Mission, need: MissionNeed) {
  const event = (mission.events || []).find((item) => item.seq === need.answered_by);
  const values = event?.values;
  if (!Array.isArray(values) || !values.length) return null;
  const row = values[values.length - 1] as { value?: number; unit?: string };
  return typeof row.value === 'number' ? `${row.value} ${row.unit || ''}`.trim() : null;
}

/** The person's answer to one request. They type what they measured; HS builds and checks the evidence. */
function AnswerForm({ mission, need, onChanged }: { mission: Mission; need: MissionNeed; onChanged: () => void }) {
  const { token, setToken } = useOperatorToken();
  const request = need.request!;
  const isLog = request.kind === 'boot_log';
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState(request.expected?.unit || (request.kind === 'dimensional' ? 'mm' : ''));
  const [log, setLog] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const number = Number(value);
  const ready = Boolean(token) && !busy && (isLog ? log.trim().length > 0 : value.trim() !== '' && Number.isFinite(number) && unit.trim() !== '');

  async function submit() {
    setBusy(true);
    setError('');
    try {
      await answerNeed(
        mission.project_id, mission.mission_id, need.seq,
        isLog ? { log } : [{ quantity: request.quantity || '', value: number, unit: unit.trim() }],
        token, mission.last_event_seq,
      );
      setValue('');
      setLog('');
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not record the reading');
    } finally {
      setBusy(false);
    }
  }

  const input = 'mt-1 rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-300/60';
  return (
    <div className="mt-4 rounded-lg border border-amber-300/25 bg-amber-950/10 p-3" data-testid={`answer-${need.seq}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-200/90">Your reading</p>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        {isLog ? (
          <label className="min-w-[18rem] flex-1 text-xs text-slate-400">What the board printed
            <textarea data-testid="answer-log" value={log} onChange={(event) => setLog(event.target.value)} rows={5} spellCheck={false}
              className={`${input} block w-full font-mono`} placeholder="Paste the serial output" />
          </label>
        ) : (
          <>
            <label className="text-xs text-slate-400">{request.quantity?.replace(/_/g, ' ')}
              <input data-testid="answer-value" type="number" step="any" inputMode="decimal" value={value} onChange={(event) => setValue(event.target.value)}
                className={`${input} block w-36`} placeholder="3.29" />
            </label>
            <label className="text-xs text-slate-400">unit
              <input data-testid="answer-unit" value={unit} onChange={(event) => setUnit(event.target.value)} maxLength={10} className={`${input} block w-24`} />
            </label>
          </>
        )}
        <OperatorTokenField token={token} setToken={setToken} />
        <button type="button" onClick={submit} disabled={!ready}
          className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-stone-900 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40">
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Record my reading
        </button>
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        This is your own report; HS records no instrument for it. It never authorizes building, flashing or powering anything.
      </p>
      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/40 bg-red-950/40 px-3 py-2 text-sm text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </p>
      ) : null}
    </div>
  );
}

const NEED_STATE: Record<MissionNeed['need_state'], { label: string; className: string }> = {
  open: { label: 'Waiting for you', className: 'border-amber-300/50 bg-amber-300/10 text-amber-100' },
  resolved: { label: 'Answered', className: 'border-emerald-300/40 bg-emerald-400/10 text-emerald-100' },
  contradicted: { label: 'Reading out of range', className: 'border-red-400/50 bg-red-950/40 text-red-100' },
};

/** Show "(1) a (2) b" as a list. Display only: every word of the agent's text is kept, in order. */
export function splitNumbered(text: string): { lead: string; items: string[] } {
  const marks = [...text.matchAll(/\((\d{1,2})\)\s+/g)];
  if (marks.length < 2 || marks[0][1] !== '1') return { lead: text.trim(), items: [] };
  const lead = text.slice(0, marks[0].index).trim();
  const items = marks.map((mark, index) => {
    const start = (mark.index ?? 0) + mark[0].length;
    const end = index + 1 < marks.length ? marks[index + 1].index : text.length;
    return text.slice(start, end).trim().replace(/[;,]$/, '');
  });
  return { lead, items };
}

export function NeedsPanel({ mission, onChanged }: { mission: Mission; onChanged: () => void }) {
  const ended = Boolean(mission.terminal);
  // A request is something a person can answer. A plain note is just the agent saying what it thinks is missing.
  const flagged = new Set((mission.safety_concerns ?? []).map((concern) => concern.need_seq));
  // Never offer an answer form for BLOCKED_UNSAFE, even when an older/partial response omits safety_concerns.
  const isSafety = (need: MissionNeed) => need.blocker === 'BLOCKED_UNSAFE' || flagged.has(need.seq);
  const requests = mission.needs.filter((need) => need.request && !isSafety(need));
  const plain = mission.needs.filter((need) => !need.request && !isSafety(need));
  // A free-text need on a running mission is the agent asking for something. It is not a side note.
  const asks = ended || !mission.accepted ? [] : plain.filter((need) => need.need_state === 'open');
  const notes = plain.filter((need) => !asks.includes(need));
  if (!requests.length && !notes.length && !asks.length) return null;
  return (
    <>
    {requests.length ? (
    <Section title="Asked of you" hint={ended ? 'This mission has ended' : 'Only a person can answer these, with their operator token'}>
      <ul className="space-y-3">
        {requests.map((need) => (
          <li key={need.seq} className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <WhoChip who="agent" label="Asked by the agent" />
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${NEED_STATE[need.need_state].className}`}>
                {ended && need.need_state !== 'resolved' ? 'Never answered' : NEED_STATE[need.need_state].label}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-100">{need.request?.instructions || need.need}</p>
            {need.request ? (
              <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-400 sm:grid-cols-3">
                <div><dt className="inline">Measure: </dt><dd className="inline text-slate-200">{need.request.target}</dd></div>
                {need.request.quantity ? <div><dt className="inline">Quantity: </dt><dd className="inline text-slate-200">{need.request.quantity}</dd></div> : null}
                {need.request.expected ? (
                  <div><dt className="inline">Expect: </dt><dd className="inline text-slate-200">{need.request.expected.min} to {need.request.expected.max} {need.request.expected.unit}</dd></div>
                ) : null}
              </dl>
            ) : null}
            {need.need_state === 'contradicted' && lastReading(mission, need) ? (
              <p data-testid="contradicted-note" className="mt-3 rounded-lg border border-red-400/40 bg-red-950/30 px-3 py-2 text-sm leading-6 text-red-100">
                Your last reading, {lastReading(mission, need)}, is outside what was expected
                {need.request?.expected ? ` (${need.request.expected.min} to ${need.request.expected.max} ${need.request.expected.unit})` : ''}.
                The agent can see it and may change the design. You can measure again.
              </p>
            ) : null}
            {need.need_state === 'resolved' && lastReading(mission, need) ? (
              <p className="mt-3 text-sm text-emerald-200">You answered {lastReading(mission, need)}.</p>
            ) : null}
            {need.request && need.need_state !== 'resolved' && !ended ? <AnswerForm mission={mission} need={need} onChanged={onChanged} /> : null}
          </li>
        ))}
      </ul>
    </Section>
    ) : null}
    {asks.length ? (
      <Section title="What the agent says it still needs" hint="In the agent’s own words. HS did not check this, and this page cannot take an answer to it yet.">
        <ul className="space-y-3">
          {asks.map((need) => {
            const { lead, items } = splitNumbered(need.need);
            return (
              <li key={need.seq} data-testid="agent-ask" className="rounded-xl border border-amber-300/40 bg-amber-300/5 p-4 text-sm leading-6 text-slate-100">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <WhoChip who="agent" label="Asked by the agent" />
                  <span className="rounded-full border border-amber-300/50 bg-amber-300/10 px-2 py-0.5 text-[11px] font-medium text-amber-100">Waiting for you</span>
                </div>
                {lead ? <p>{lead}</p> : null}
                {items.length ? (
                  <ol className="hs-reset mt-2 list-decimal space-y-1.5 pl-5 marker:text-amber-200">
                    {items.map((item, index) => <li key={index}>{item}</li>)}
                  </ol>
                ) : null}
              </li>
            );
          })}
        </ul>
      </Section>
    ) : null}
    {notes.length ? (
      <Section title="Concerns the agent recorded" hint="Notes, not requests. HS did not check them.">
        <ul className="space-y-2">
          {notes.map((need) => (
            <li key={need.seq} className="flex items-start gap-3 rounded-xl border border-dashed border-white/15 bg-black/20 p-3 text-sm leading-6 text-slate-200">
              <WhoChip who="agent" />
              <span>{need.need}</span>
            </li>
          ))}
        </ul>
      </Section>
    ) : null}
    </>
  );
}

/** An accepted mission with no design yet is waiting on an agent. Say how to point one at it. */
export function AgentHandoff({ mission }: { mission: Mission }) {
  const [copied, setCopied] = useState(false);
  const agentActed = (mission.events ?? []).some((event) => event.author.kind === 'agent' && event.type !== 'opened');
  if (!mission.accepted || mission.terminal || mission.candidates.length || agentActed) return null;
  const text = `Fabrication mission ${mission.mission_id} in project ${mission.project_id}.\n`
    + 'Use the fabrication_mission task (MCP) or the routes in docs/AGENT_MISSION.md. Draft from the parts list, propose a design, '
    + 'ask HS to run its checks, and propose the terminal state the evidence supports. You cannot accept the mission or record a result.';
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch { /* the text is selectable on the page */ }
  }
  return (
    <Section title="Waiting for an agent" hint="Accepted, nothing proposed yet">
      <p className="max-w-3xl text-sm leading-6 text-slate-300">
        You have accepted this mission, so HS will run its software checks for an agent. Point an agent at it. It can propose designs and
        ask for checks; it cannot change what you asked for, accept anything or record a result.
      </p>
      <pre data-testid="agent-handoff" className="mt-3 whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-3 text-xs leading-5 text-slate-300">{text}</pre>
      <button type="button" onClick={copy} className="mt-3 inline-flex items-center gap-2 rounded-full border border-white/25 px-4 py-2 text-xs font-semibold text-slate-100 hover:bg-white/5">
        <Clipboard className="h-3.5 w-3.5" /> {copied ? 'Copied' : 'Copy for the agent'}
      </button>
    </Section>
  );
}

function focusCandidate(mission: Mission): MissionCandidate | null {
  if (!mission.candidates.length) return null;
  return mission.candidates.find((candidate) => candidate.id === mission.terminal?.candidate_id) || mission.candidates[mission.candidates.length - 1];
}

export function AskedForPanel({ mission }: { mission: Mission }) {
  const focus = focusCandidate(mission);
  const { intake, budgets } = mission;
  const left = new Set(focus?.uncovered_inventory || []);
  const requirements = intake.requirements || [];
  return (
    <Section title="What you asked for" hint="Written by you. The agent cannot change it.">
      <p data-testid="goal" className="text-base leading-7 text-slate-100">{intake.goal}</p>

      <h4 className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Your parts</h4>
      <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {intake.inventory.map((line, index) => {
          const state = !focus ? 'unknown' : left.has(line) ? 'missing' : 'present';
          return (
            <li key={`${line}-${index}`} className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200">
              {state === 'present' ? <Check className="h-4 w-4 shrink-0 text-emerald-300" aria-label="In the design" />
                : state === 'missing' ? <X className="h-4 w-4 shrink-0 text-red-300" aria-label="Not in the design" />
                : <Minus className="h-4 w-4 shrink-0 text-slate-500" aria-label="No design yet" />}
              <span>{line}</span>
              {state === 'missing' ? <span className="ml-auto text-[11px] text-red-200">not in the design</span> : null}
            </li>
          );
        })}
      </ul>
      {mission.inventory?.reading?.left_out?.length ? (
        <p className="mt-2 text-xs leading-5 text-sky-200/90">
          <WhoChip who="system" /> could not match: {mission.inventory.reading.left_out.join('; ')}. It has no data for {mission.inventory.reading.left_out.length === 1 ? 'that part' : 'those parts'}.
        </p>
      ) : null}

      {requirements.length ? (
        <>
          <h4 className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Requirements HS enforces</h4>
          <ul className="mt-2 space-y-1 text-sm text-slate-200">
            {requirements.map((row) => (
              <li key={row.path}><code className="rounded bg-black/40 px-1.5 py-0.5 text-xs text-slate-300">{row.path}</code> must be {JSON.stringify(row.equals)}</li>
            ))}
          </ul>
        </>
      ) : null}

      {intake.constraints.length ? (
        <>
          <h4 className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Your constraints <span className="font-normal normal-case tracking-normal text-slate-500">— noted, not enforced by HS</span></h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
            {intake.constraints.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </>
      ) : null}

      <dl className="mt-5 grid gap-3 border-t border-white/10 pt-4 text-xs sm:grid-cols-3">
        <div><dt className="text-slate-500">Checks used</dt><dd className="mt-0.5 text-sm text-slate-200">{budgets.operator_jobs_used} of {budgets.max_operator_jobs}</dd></div>
        <div><dt className="text-slate-500">Designs allowed</dt><dd className="mt-0.5 text-sm text-slate-200">{budgets.max_candidates}</dd></div>
        <div><dt className="text-slate-500">Repairs per design</dt><dd className="mt-0.5 text-sm text-slate-200">{budgets.max_repairs_per_candidate}</dd></div>
      </dl>
    </Section>
  );
}

function CheckIcon({ errors, warnings }: { errors: number; warnings: number }) {
  if (errors) return <X className="h-4 w-4 shrink-0 text-red-300" aria-label="Problem" />;
  if (warnings) return <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" aria-label="Look at this" />;
  return <Check className="h-4 w-4 shrink-0 text-emerald-300" aria-label="Clean" />;
}

/** A reported concern is not an HS safety verdict, even when a mission terminates. */
export function SafetyPanel({ mission }: { mission: Mission }) {
  const concerns = mission.safety_concerns ?? [];
  if (!concerns.length) {
    return (
      <p data-testid="no-safety-concern" className="px-1 text-xs leading-5 text-slate-500">
        No safety concern has been recorded. That is not a safety check: HS does not assess danger, and a concern may go unreported.
      </p>
    );
  }
  const allDeclaredAgent = concerns.every((concern) => concern.author?.kind === 'agent');
  return (
    <section data-testid="safety-concern" aria-label="Safety concern" className="rounded-2xl border border-red-400/50 bg-red-950/30 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-red-300" aria-hidden="true" />
        <h2 className="text-base font-semibold text-red-100">
          {allDeclaredAgent ? 'The agent flagged a safety concern' : 'A safety concern was recorded'}
        </h2>
        {allDeclaredAgent ? (
          <WhoChip who="agent" label="The agent’s word, not checked by HS" />
        ) : (
          <span className="rounded-full border border-red-300/40 px-2 py-0.5 text-[11px] text-red-100">
            Reported claim, not checked by HS
          </span>
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-red-100/80">
        HS cannot judge danger. These are recorded claims, not a safety assessment. Do not open, power or handle the item on the strength of this page.
      </p>
      <ul className="mt-3 space-y-3">
        {concerns.map((concern) => {
          const stoppedOnThis = mission.terminal?.state === 'BLOCKED_UNSAFE'
            && (mission.terminal.cites ?? []).includes(concern.need_seq);
          const state = concern.state === 'resolved'
            ? 'Evidence recorded; safety not assessed'
            : stoppedOnThis
              ? 'Mission stopped citing this concern'
              : mission.terminal
                ? 'Mission ended for another reason; concern remains recorded'
                : concern.state === 'contradicted'
                  ? 'Evidence contested'
                  : 'Still open';
          const reporter = concern.author?.kind === 'agent' ? 'Reported as agent'
            : concern.author?.kind === 'human' ? 'Reporter declared human (identity not verified here)'
              : 'Reporter not established';
          return (
            <li key={concern.need_seq} className="rounded-xl border border-red-400/30 bg-black/25 p-4 text-sm leading-6 text-slate-100">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-red-100/80">
                <span>Recorded at event #{concern.need_seq}</span>
                <span>·</span>
                <span>{reporter}</span>
                <span>·</span>
                <span>{state}</span>
              </div>
              <p className="whitespace-pre-line">{concern.concern}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function CandidatesPanel({ mission }: { mission: Mission }) {
  if (!mission.candidates.length) {
    return (
      <Section title="Designs tried">
        <p className="flex items-center gap-2 text-sm text-slate-400"><Hourglass className="h-4 w-4" /> No design has been proposed yet.</p>
      </Section>
    );
  }
  return (
    <Section title="Designs tried" hint="HS runs every check itself; the agent cannot record a result">
      <ul className="space-y-3">
        {mission.candidates.map((candidate) => {
          const decisive = candidate.id === mission.terminal?.candidate_id;
          return (
            <li key={candidate.id} className={`rounded-xl border p-4 ${decisive ? 'border-white/30 bg-white/[0.04]' : 'border-white/10 bg-black/20'}`}>
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-slate-100">Design {candidate.id}: {candidate.label}</h4>
                <WhoChip who="agent" label="Proposed by the agent" />
                {decisive ? <span className="rounded-full border border-white/25 px-2 py-0.5 text-[11px] text-slate-200">The verdict rests on this</span> : null}
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-400">{candidate.rationale}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className={`rounded-full border px-2 py-0.5 ${candidate.covers_inventory ? 'border-emerald-300/40 text-emerald-100' : 'border-red-400/50 bg-red-950/30 text-red-100'}`}>
                  {candidate.covers_inventory ? 'Uses every part you listed' : `Missing: ${candidate.uncovered_inventory.join(', ') || 'a listed part'}`}
                </span>
                {candidate.violated_requirements.map((line) => (
                  <span key={line} className="rounded-full border border-red-400/50 bg-red-950/30 px-2 py-0.5 text-red-100">Breaks: {line}</span>
                ))}
                {(candidate.donor_coverage?.missing_required_donors ?? []).map((donor) => (
                  <span key={donor} data-testid="donor-left-out" className="rounded-full border border-red-400/50 bg-red-950/30 px-2 py-0.5 text-red-100">Leaves out the donor you named: {donor}</span>
                ))}
                {(candidate.donor_coverage?.unverified_used_donors ?? []).map((donor) => (
                  <span key={donor.donor_id} className="rounded-full border border-amber-300/50 bg-amber-300/10 px-2 py-0.5 text-amber-100">
                    Names {donor.donor_id}, not verified yet{donor.missing_facts.length ? `: needs ${donor.missing_facts.join(', ')}` : ''}
                  </span>
                ))}
                {candidate.repairs ? <span className="rounded-full border border-white/15 px-2 py-0.5 text-slate-300">{candidate.repairs} {candidate.repairs === 1 ? 'repair' : 'repairs'}</span> : null}
              </div>
              {candidate.donor_coverage?.used_donors?.length ? (
                <p className="mt-2 text-[11px] leading-5 text-slate-500">Naming a donor is a reference. It does not show the donor is wired into the design.</p>
              ) : null}
              {candidate.spec_diagnostics?.unrecognized_fields?.length ? (
                <details data-testid="unchecked-fields" className="mt-2 rounded-lg border border-amber-300/40 bg-amber-300/5 px-3 py-2 text-xs text-amber-100">
                  <summary className="cursor-pointer">{candidate.spec_diagnostics.unrecognized_fields.length} {candidate.spec_diagnostics.unrecognized_fields.length === 1 ? 'field' : 'fields'} HS did not check</summary>
                  <p className="mt-1 leading-5 text-amber-100/80">The agent wrote these. They are kept as written, but HS’s planner ignores them, so a clean check says nothing about them.</p>
                  <ul className="mt-1 font-mono text-[11px] text-amber-50/90">
                    {candidate.spec_diagnostics.unrecognized_fields.map((field) => <li key={field}>{field}</li>)}
                  </ul>
                </details>
              ) : null}
              {candidate.evaluations.length ? (
                <ol className="mt-3 space-y-1.5 border-t border-white/10 pt-3">
                  {candidate.evaluations.map((evaluation) => (
                    <li key={evaluation.seq} className="flex items-center gap-2 text-sm text-slate-200">
                      <CheckIcon errors={evaluation.result.errors} warnings={evaluation.result.warnings} />
                      <span>{operationName(evaluation.operation)}</span>
                      <span className="text-slate-400">— {resultWords(evaluation)}</span>
                      <WhoChip who="system" label="HS" />
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-3 text-xs text-slate-500">No checks have run on this design.</p>
              )}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}
