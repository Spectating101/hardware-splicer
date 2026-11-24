'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ClipboardCopy, FileText, RefreshCw } from 'lucide-react';
import {
  inspectMissionDelivery, operationName,
  type Mission, type MissionCandidate, type MissionDeliveryInspection,
} from '@/lib/missions';

const sha = (value: string | null | undefined) => value || 'Not retained';
const display = (lines: string[]) => lines.map((line) => '- ' + line).join('\n') || '- None recorded';

function citedSources(spec: Record<string, unknown> | undefined): string[] {
  const refs = spec?.source_ids;
  return Array.isArray(refs) ? refs.filter((ref): ref is string => typeof ref === 'string') : [];
}

/** Clipboard text is assembled only from an inspected mission. It never invents part ratings or dimensions. */
export function buildSheetText(mission: Mission, candidate: MissionCandidate, delivery: MissionDeliveryInspection | null): string {
  const decisive = mission.terminal?.state === 'READY_FOR_HUMAN_BUILD'
    && mission.terminal.candidate_id === candidate.id;
  const concerns = (mission.safety_concerns ?? []).map((c) => 'Event ' + c.need_seq + ': ' + c.concern);
  const openNeeds = mission.needs.filter((n) => n.need_state !== 'resolved'
    && (n.candidate_id === null || n.candidate_id === candidate.id));
  const files = delivery?.recorded_files.filter((f) => f.candidate_id === candidate.id) ?? [];
  const omitted = candidate.donor_coverage?.missing_required_donors ?? [];
  const unverified = candidate.donor_coverage?.unverified_used_donors ?? [];
  const unchecked = candidate.spec_diagnostics?.unrecognized_fields ?? [];
  const physical = mission.terminal?.physical_evidence_required ?? [];
  return [
    'HARDWARE SPLICER — ENGINEERING REVIEW SHEET (NOT BUILD INSTRUCTIONS)',
    'Project: ' + mission.project_id,
    'Mission: ' + mission.mission_id,
    'Mission event sequence: ' + mission.last_event_seq,
    'Goal (intake): ' + mission.intake.goal,
    'Design (agent proposal): ' + candidate.id + ' — ' + candidate.label,
    'Rationale (agent proposal): ' + candidate.rationale,
    'Verdict: ' + (mission.terminal?.state || 'No terminal verdict'),
    'Candidate status: ' + (decisive ? 'HS software checks support this proposal; no physical approval' : 'Review only, not selected as a READY candidate'),
    'Physical correctness: ' + mission.physical_correctness,
    'Firmware authorized: ' + String(mission.firmware_authorized),
    'Power-on authorized: ' + String(mission.power_on_authorized),
    '',
    'USER-LISTED INVENTORY (NOT A VERIFIED BOM)',
    display(mission.intake.inventory),
    '',
    'SOURCE IDS REFERENCED BY AGENT (NOT VERIFIED BY THIS VIEW)',
    display(citedSources(candidate.spec)),
    '',
    'DONOR GAPS / UNVERIFIED REFERENCES',
    display([
      ...omitted.map((d) => 'Required donor left out: ' + d),
      ...unverified.map((d) => 'Unverified donor: ' + d.donor_id + '; missing ' + d.missing_facts.join(', ')),
    ]),
    '',
    'INVENTORY LINES NOT COVERED',
    display(candidate.uncovered_inventory),
    '',
    'UNRECOGNIZED SPEC FIELDS (NOT CHECKED BY HS PLANNER)',
    display(unchecked),
    '',
    'CHECK RESULTS (SOFTWARE ONLY)',
    display(candidate.evaluations.map((e) => e.operation + ': ' + e.result.errors + ' errors, ' + e.result.warnings
      + ' warnings; event ' + e.seq + '; result SHA-256 ' + sha(e.result.result_sha256))),
    '',
    'RETAINED OUTPUT INSPECTION (READ-ONLY)',
    delivery ? 'Inspected mission event sequence: ' + delivery.last_event_seq : 'Inspection not available; do not infer artifact availability.',
    display(files.map((f) => f.kind + ': ' + f.status + (f.current ? ', current' : ', superseded')
      + '; SHA-256 ' + sha(f.sha256) + '; check event ' + f.evaluation_seq)),
    'Prototype review package: ' + (delivery?.prototype_package.status || 'Not inspected'),
    'File existence does not prove which agent produced it.',
    '',
    'OPEN EVIDENCE NEEDS',
    display(openNeeds.map((n) => 'Event ' + n.seq + ': ' + n.blocker + ' — ' + n.need)),
    '',
    'AGENT-REPORTED SAFETY CONCERNS (NOT HS SAFETY ASSESSMENTS)',
    display(concerns),
    '',
    'PHYSICAL WORK STILL REQUIRED BY TERMINAL VERDICT',
    display(physical),
    '',
    'Proposed design data (unverified where not checked):',
    JSON.stringify(candidate.spec || {}, null, 2),
    '',
    'This sheet is a read-only review, not proof of safety, real-donor compatibility, or authority to fabricate, flash or power hardware.',
  ].join('\n');
}

/**
 * A human-readable inspection of what is retained and what is only proposed.
 * It never builds, approves, stages or downloads a package during inspection.
 */
export function BuildSheetPanel({ mission }: { mission: Mission }) {
  const [opened, setOpened] = useState(false);
  const [chosen, setChosen] = useState('');
  const [delivery, setDelivery] = useState<MissionDeliveryInspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    setChosen(mission.terminal?.candidate_id || mission.candidates[0]?.id || '');
    setOpened(false);
    setCopied(false);
  }, [mission.mission_id]);
  useEffect(() => {
    if (!opened) return;
    let live = true;
    setBusy(true);
    setError('');
    inspectMissionDelivery(mission.project_id, mission.mission_id)
      .then((result) => { if (live) setDelivery(result); })
      .catch((caught: unknown) => {
        if (live) {
          setDelivery(null);
          setError(caught instanceof Error ? caught.message : 'Delivery inspection failed');
        }
      })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [opened, mission.project_id, mission.mission_id, mission.last_event_seq, refresh]);

  const candidate = useMemo(
    () => mission.candidates.find((row) => row.id === chosen) || mission.candidates[0],
    [chosen, mission.candidates],
  );
  // Never show or copy inspection files from a mission that was selected previously.
  const inspection = delivery?.project_id === mission.project_id && delivery.mission_id === mission.mission_id
    ? delivery : null;
  if (!mission.accepted || !candidate) return null;
  const decisive = mission.terminal?.state === 'READY_FOR_HUMAN_BUILD'
    && mission.terminal.candidate_id === candidate.id;
  const openNeeds = mission.needs.filter((n) => n.need_state !== 'resolved'
    && (n.candidate_id === null || n.candidate_id === candidate.id));
  const missingDonors = candidate.donor_coverage?.missing_required_donors ?? [];
  const unverifiedDonors = candidate.donor_coverage?.unverified_used_donors ?? [];
  const unchecked = candidate.spec_diagnostics?.unrecognized_fields ?? [];
  const files = inspection?.recorded_files.filter((file) => file.candidate_id === candidate.id) ?? [];
  const concerns = mission.safety_concerns ?? [];

  async function copySheet() {
    if (!candidate) return;
    try {
      await navigator.clipboard.writeText(buildSheetText(mission, candidate, inspection));
      setCopied(true);
    } catch {
      setError('Clipboard unavailable. The review details are visible below and can be selected.');
    }
  }

  return (
    <section data-testid="mission-build-sheet" aria-label="Engineering review sheet"
      className="rounded-2xl border border-white/15 bg-[#07111f]/80 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <FileText className="h-4 w-4" /> Engineering review sheet
          </h3>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Existing evidence and proposed work, not a fabrication recipe or physical safety approval.
          </p>
        </div>
        <button type="button" data-testid="build-sheet-toggle" aria-expanded={opened}
          onClick={() => setOpened(!opened)}
          className="rounded-full border border-slate-400/40 px-4 py-2 text-xs font-semibold text-slate-100 hover:bg-white/10">
          {opened ? 'Close review sheet' : 'Open review sheet'}
        </button>
      </div>
      {opened ? (
        <div className="mt-4 space-y-4" data-testid="build-sheet-content">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <label className="text-xs text-slate-400">
              Agent-proposed design
              <select value={candidate.id} onChange={(e) => { setChosen(e.target.value); setCopied(false); }}
                data-testid="build-sheet-candidate"
                className="mt-1 block max-w-full rounded-lg border border-white/20 bg-[#07111f] px-3 py-2 text-sm text-slate-100">
                {mission.candidates.map((row) => <option key={row.id} value={row.id}>{row.id}: {row.label}</option>)}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setRefresh((n) => n + 1)} disabled={busy}
                className="inline-flex items-center gap-2 rounded-full border border-white/25 px-3 py-2 text-xs text-slate-100 disabled:opacity-50">
                <RefreshCw className="h-3.5 w-3.5" /> Refresh retained files
              </button>
              <button type="button" data-testid="build-sheet-copy" onClick={copySheet}
                className="inline-flex items-center gap-2 rounded-full border border-amber-300/50 px-3 py-2 text-xs text-amber-100">
                <ClipboardCopy className="h-3.5 w-3.5" /> {copied ? 'Copied review sheet' : 'Copy review sheet'}
              </button>
            </div>
          </div>
          <p data-testid="build-sheet-authority" className="rounded-xl border border-amber-300/40 bg-amber-950/20 p-3 text-xs leading-5 text-amber-100">
            {decisive
              ? 'HS recorded software readiness for this candidate. This is not evidence of physical correctness and does not authorize construction, flashing or power-on.'
              : 'REVIEW ONLY — this design has not earned the READY_FOR_HUMAN_BUILD verdict. Do not use it as build instructions.'}
            {' '}Physical correctness: {mission.physical_correctness}. Firmware authorized: {String(mission.firmware_authorized)}.
            Power-on authorized: {String(mission.power_on_authorized)}.
          </p>
          {concerns.length ? (
            <div data-testid="build-sheet-safety" className="rounded-xl border border-red-400/40 bg-red-950/25 p-3">
              <h4 className="flex items-center gap-2 text-xs font-semibold text-red-100">
                <AlertTriangle className="h-4 w-4" /> Recorded safety concerns — reporter claims, not HS safety checks
              </h4>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-200">
                {concerns.map((c) => <li key={c.need_seq}>Event #{c.need_seq}: {c.concern}</li>)}
              </ul>
            </div>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h4 className="text-xs font-semibold text-slate-100">User inventory, not a verified bill of materials</h4>
              <ul data-testid="build-sheet-inventory" className="mt-1 list-disc pl-5 text-xs leading-6 text-slate-300">
                {mission.intake.inventory.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
              {candidate.uncovered_inventory.length ? (
                <p className="mt-2 text-xs leading-5 text-red-200">
                  Inventory not covered by this proposal: {candidate.uncovered_inventory.join('; ')}
                </p>
              ) : null}
              {missingDonors.length ? (
                <p data-testid="build-sheet-missing-donors" className="mt-2 text-xs leading-5 text-red-200">
                  Required donors omitted: {missingDonors.join('; ')}
                </p>
              ) : null}
              {unverifiedDonors.length ? (
                <ul className="mt-2 space-y-1 text-xs leading-5 text-amber-100">
                  {unverifiedDonors.map((d) => <li key={d.donor_id}>
                    Donor reference not verified: {d.donor_id}. Missing: {d.missing_facts.join(', ') || 'facts not identified'}
                  </li>)}
                </ul>
              ) : null}
              {citedSources(candidate.spec).length ? (
                <p className="mt-2 text-xs leading-5 text-slate-400">
                  Agent-cited source IDs (not authenticated by this view): {citedSources(candidate.spec).join('; ')}
                </p>
              ) : null}
            </div>
            <div>
              <h4 className="text-xs font-semibold text-slate-100">Unresolved evidence and unverified design fields</h4>
              {openNeeds.length ? (
                <ul data-testid="build-sheet-open-needs" className="mt-1 space-y-2 text-xs leading-5 text-amber-100">
                  {openNeeds.map((n) => <li key={n.seq}>
                    Event #{n.seq} ({n.blocker}): {n.need}
                  </li>)}
                </ul>
              ) : <p className="mt-1 text-xs text-slate-400">No open evidence needs recorded for this candidate. Absence is not proof of safety.</p>}
              {unchecked.length ? (
                <p data-testid="build-sheet-unchecked" className="mt-3 text-xs leading-5 text-amber-100">
                  Not checked by the HS catalog planner: {unchecked.join('; ')}
                </p>
              ) : null}
              {mission.terminal?.physical_evidence_required?.length ? (
                <ul className="mt-3 list-disc pl-5 text-xs leading-5 text-amber-100">
                  {mission.terminal.physical_evidence_required.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              ) : null}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-100">Actual HS software evaluations</h4>
            {candidate.evaluations.length ? (
              <ul className="mt-2 space-y-2 text-xs text-slate-300">
                {candidate.evaluations.map((e) => (
                  <li key={e.seq} className="rounded-lg border border-white/10 p-3">
                    <div>{operationName(e.operation)} — {e.result.errors} errors; {e.result.warnings} warnings (event #{e.seq})</div>
                    <div className="mt-1 break-all font-mono text-[11px] text-slate-500">
                      Result SHA-256: {sha(e.result.result_sha256)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-xs text-slate-400">No software evaluation recorded for this design.</p>}
          </div>
          <div data-testid="build-sheet-retained">
            <h4 className="text-xs font-semibold text-slate-100">Retained outputs: non-generating backend inspection</h4>
            {busy ? <p className="mt-1 text-xs text-slate-400">Inspecting retained output…</p> : null}
            {error ? <p role="alert" className="mt-1 text-xs text-red-200">{error}</p> : null}
            {inspection ? (
              <>
                {inspection.last_event_seq !== mission.last_event_seq ? (
                  <p className="mt-1 text-xs text-amber-100">Inspection and mission events differ; refresh before relying on this list.</p>
                ) : null}
                <p className="mt-1 text-xs text-slate-400">
                  Prototype review package: {inspection.prototype_package.status}. Physical correctness: {inspection.physical_correctness}.
                  {inspection.inspection_generated_artifacts ? ' Inspection generated artifacts.' : ' Inspection generated no artifacts.'}
                </p>
                {files.length ? (
                  <ul className="mt-2 space-y-2">
                    {files.map((file) => (
                      <li key={file.kind + ':' + file.evaluation_seq} className="rounded-lg border border-white/10 p-3 text-xs text-slate-300">
                        <span>{file.kind} — {file.status}, {file.current ? 'current' : 'superseded'}; event #{file.evaluation_seq}</span>
                        <p className="mt-1 break-all font-mono text-[11px] text-slate-500">SHA-256: {sha(file.sha256)}</p>
                        {file.scope ? <p className="mt-1 text-amber-100">Scope: {file.scope}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-1 text-xs text-slate-400">No retained files for this candidate were found in the inspection.</p>}
                {inspection.prototype_package.retained_packages.length ? (
                  <ul data-testid="build-sheet-packages" className="mt-2 space-y-1 text-xs text-slate-300">
                    {inspection.prototype_package.retained_packages.map((pkg) => (
                      <li key={pkg.sha256} className="rounded-lg border border-white/10 px-3 py-2">
                        Prototype review ZIP retained: {pkg.size_bytes} bytes, scope {pkg.scope}.
                        <p className="break-all font-mono text-[11px] text-slate-500">SHA-256: {pkg.sha256}</p>
                        <p className="text-[11px] text-amber-100">Producer attribution: {pkg.producer_attribution}</p>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="mt-2 text-xs text-slate-500">
                  File presence is not proof of agent delivery. Only explicitly listed available files are retained; this view never generates missing files.
                </p>
              </>
            ) : !busy ? <p className="mt-1 text-xs text-slate-400">No trustworthy output inspection available.</p> : null}
          </div>
          <details className="rounded-xl border border-white/10 p-3">
            <summary className="cursor-pointer text-xs font-semibold text-slate-200">Inspect exact agent-proposed spec (not validated by this view)</summary>
            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all text-[11px] text-slate-400">{JSON.stringify(candidate.spec ?? {}, null, 2)}</pre>
          </details>
          <p className="text-[11px] leading-5 text-slate-500">
            This read-only sheet does not provide dimensions, wiring, force limits, or physical approval not present in HS records.
            The existing hand-off workflow remains separate and human-gated.
          </p>
        </div>
      ) : null}
    </section>
  );
}
