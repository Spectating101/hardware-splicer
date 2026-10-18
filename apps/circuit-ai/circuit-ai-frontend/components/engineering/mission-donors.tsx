'use client';

import { Recycle } from 'lucide-react';
import { WhoChip } from '@/components/engineering/mission-detail';
import type { DonorFact, Mission, MissionDonor } from '@/lib/missions';

// How well a fact about donor hardware is established. Weakest first; a stronger grade never comes from a weaker one.
const GRADE: Record<string, { label: string; className: string }> = {
  person_measurement: { label: 'Measured by a person', className: 'border-amber-300/50 bg-amber-300/10 text-amber-100' },
  document: { label: 'From a document, not measured', className: 'border-slate-400/50 bg-slate-800/60 text-slate-200' },
  re_observation: { label: 'Observed, not measured', className: 'border-fuchsia-300/50 bg-fuchsia-400/10 text-fuchsia-100' },
  agent_assertion: { label: 'The agent’s claim', className: 'border-dashed border-fuchsia-300/60 text-fuchsia-100' },
};

const STATE: Record<string, { label: string; meaning: string; className: string }> = {
  unknown: { label: 'Nothing on record', meaning: 'HS has no record of this donor, so it cannot use anything about it.', className: 'border-slate-500/60 text-slate-200' },
  partial: { label: 'Partly known', meaning: 'Some facts are written down, but not all of them are established well enough to build on.', className: 'border-amber-300/50 bg-amber-950/30 text-amber-100' },
  verified: { label: 'Established', meaning: 'Every fact HS needs is measured and accepted.', className: 'border-emerald-300/40 bg-emerald-400/10 text-emerald-100' },
  rejected: { label: 'Rejected', meaning: 'A reviewer rejected this record.', className: 'border-red-400/50 bg-red-950/40 text-red-100' },
};

const FACT: Record<string, string> = {
  voltage_max_v: 'Highest voltage',
  active_level: 'Active level',
  controller_pin: 'Controller pin',
  protocol: 'Protocol',
  interface_complete: 'Description complete',
};

function missingWords(path: string) {
  const parts = path.split('.');
  if (parts[0] === 'signals' && parts.length === 3) return `${parts[1]}: ${(FACT[parts[2]] || parts[2]).toLowerCase()}`;
  return FACT[path] || path.replace(/[._]/g, ' ');
}

function GradeChip({ fact }: { fact: DonorFact }) {
  const grade = fact.grade ? GRADE[fact.grade] : null;
  return grade
    ? <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${grade.className}`}>{grade.label}</span>
    : <span className="rounded-full border border-dashed border-slate-500/60 px-2 py-0.5 text-[11px] text-slate-400">Unknown</span>;
}

function shown(fact: DonorFact) {
  if (fact.value === null || fact.value === undefined) return '—';
  return `${String(fact.value)}${fact.unit ? ` ${fact.unit}` : ''}`;
}

function Donor({ donor }: { donor: MissionDonor }) {
  const state = STATE[donor.contract_state] || STATE.unknown;
  return (
    <li data-testid="donor" data-state={donor.contract_state} className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{donor.label}</h4>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${state.className}`}>{state.label}</span>
        {donor.optional ? <span className="text-[11px] text-slate-500">optional</span> : null}
      </div>
      <p className="mt-1 text-[11px] text-slate-500"><code>{donor.donor_id}</code></p>
      <p className="mt-2 text-xs leading-5 text-slate-400">
        {state.meaning} {donor.can_generate_firmware ? 'HS can generate firmware for it.' : 'HS cannot generate firmware for it yet.'}
      </p>

      {donor.signals.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[30rem] text-left text-xs">
            <thead className="text-slate-500">
              <tr><th className="py-1 pr-3 font-medium">Signal</th><th className="py-1 pr-3 font-medium">Highest voltage</th><th className="py-1 pr-3 font-medium">Active level</th><th className="py-1 font-medium">Controller pin</th></tr>
            </thead>
            <tbody>
              {donor.signals.map((signal) => (
                <tr key={signal.name} className="border-t border-white/10 align-top text-slate-200">
                  <td className="py-2 pr-3"><span className="font-medium">{signal.name}</span><span className="block text-slate-500">{signal.direction} · contact {signal.contact_id}</span></td>
                  {[signal.voltage_max_v, signal.active_level, signal.controller_pin].map((fact, index) => (
                    <td key={index} className="py-2 pr-3"><span className="block">{shown(fact)}</span><GradeChip fact={fact} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {donor.missing_facts.length ? (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-200/80">Still needed before a design can rely on it</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-slate-300">
            {donor.missing_facts.map((path) => <li key={path}>{path === 'interface_complete' ? 'A person’s confirmation that the description is complete' : `${missingWords(path)}, measured by a person`}</li>)}
          </ul>
        </div>
      ) : null}

      {donor.findings.length ? (
        <div className="mt-4 border-t border-white/10 pt-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">What the agent found</p>
          <ul className="mt-2 space-y-2">
            {donor.findings.map((finding) => (
              <li key={finding.seq} className="rounded-lg border border-dashed border-fuchsia-300/30 p-3 text-sm leading-6 text-slate-200">
                <div className="flex flex-wrap items-center gap-2">
                  <WhoChip who="agent" />
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${GRADE[finding.grade]?.className || ''}`}>{GRADE[finding.grade]?.label || finding.grade}</span>
                  <span className="text-[11px] text-slate-500">{finding.method}{finding.signal ? ` · ${finding.signal}` : ''} · {finding.source}</span>
                </div>
                <p className="mt-1.5">“{finding.claim}”</p>
                {finding.artifacts.length ? (
                  <ul className="mt-1.5 text-[11px] text-slate-500">
                    {finding.artifacts.map((artifact) => <li key={artifact.sha256}>{artifact.name} <code>{artifact.sha256.slice(0, 12)}…</code></li>)}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-5 text-slate-500">Findings help the agent and you decide what to measure. They never count as a measurement and never make a donor ready.</p>
        </div>
      ) : null}
    </li>
  );
}

/** The donor hardware a mission was told about, and how well each fact about it is established. */
export function DonorsPanel({ mission }: { mission: Mission }) {
  const donors = mission.donors || [];
  if (!donors.length) return null;
  return (
    <section className="rounded-2xl border border-white/10 bg-[#07111f]/70 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-slate-300"><Recycle className="h-4 w-4" /> Donor hardware</h3>
        <p className="text-xs text-slate-500">HS’s record as it stood when you accepted</p>
      </div>
      <ul className="mt-3 space-y-3">{donors.map((donor) => <Donor key={donor.donor_id} donor={donor} />)}</ul>
    </section>
  );
}
