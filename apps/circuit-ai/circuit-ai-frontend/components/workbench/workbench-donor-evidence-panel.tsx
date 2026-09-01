'use client';

import { useEffect, useMemo, useState } from 'react';
import { ClipboardCheck, Loader2, RefreshCw, Save, ShieldAlert, Wrench } from 'lucide-react';
import { constructorTarget } from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchDonorIntakeStore, type WorkbenchDonorResource } from '@/lib/workbench-donor-intake-store';
import {
  useWorkbenchDonorEvidenceStore,
  type DonorCondition,
  type WorkbenchDonorEvidence,
} from '@/lib/workbench-donor-evidence-store';

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asStrings(value: unknown) {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function fieldAgentPayload(resource: WorkbenchDonorResource, evidence?: WorkbenchDonorEvidence) {
  return {
    diy_project: constructorTarget.prompt,
    available_resources: [{
      resource_id: resource.resourceId,
      name: resource.name,
      resource_kind: 'salvaged',
      capabilities: resource.capabilities,
      confidence: resource.confidence,
      evidence_status: 'needs_evidence',
      note: resource.note,
    }],
    constraints: {
      safety_level: 'low_voltage_only',
      evidence_policy: 'operator claims remain advisory until instrument/artifact-backed verification',
    },
    photo_observations: [{
      resource_id: resource.resourceId,
      label: resource.observedLabel,
      confidence: resource.confidence,
      source_name: resource.sourceName,
    }],
    operator_notes: evidence ? {
      identity_label: evidence.identityLabel,
      condition: evidence.condition,
      dimensions_note: evidence.dimensionsNote,
      connector_note: evidence.connectorNote,
      power_note: evidence.powerNote,
      evidence_uri: evidence.evidenceUri,
      notes: evidence.notes,
      authority: evidence.authority,
      recorded_at: evidence.recordedAt,
    } : {},
  };
}

export function WorkbenchDonorEvidencePanel() {
  const selectedResourceId = useMachineWorkbenchStore((state) => state.selectedResourceId);
  const donorResources = useWorkbenchDonorIntakeStore((state) => state.resources);
  const hydrateDonors = useWorkbenchDonorIntakeStore((state) => state.hydrate);
  const evidenceRecords = useWorkbenchDonorEvidenceStore((state) => state.records);
  const evidenceHydrated = useWorkbenchDonorEvidenceStore((state) => state.hydrated);
  const hydrateEvidence = useWorkbenchDonorEvidenceStore((state) => state.hydrate);
  const saveEvidence = useWorkbenchDonorEvidenceStore((state) => state.saveEvidence);
  const clearEvidence = useWorkbenchDonorEvidenceStore((state) => state.clearEvidence);
  const focused = useMemo(
    () => donorResources.find((resource) => resource.resourceId === selectedResourceId) ?? null,
    [donorResources, selectedResourceId],
  );
  const stored = focused ? evidenceRecords[focused.resourceId] : undefined;

  const [identityLabel, setIdentityLabel] = useState('');
  const [condition, setCondition] = useState<DonorCondition>('unknown');
  const [dimensionsNote, setDimensionsNote] = useState('');
  const [connectorNote, setConnectorNote] = useState('');
  const [powerNote, setPowerNote] = useState('');
  const [evidenceUri, setEvidenceUri] = useState('');
  const [notes, setNotes] = useState('');
  const [actionState, setActionState] = useState<'idle' | 'loading' | 'live' | 'error'>('idle');
  const [actionMessage, setActionMessage] = useState('');
  const [fieldAction, setFieldAction] = useState<Record<string, unknown>>({});

  useEffect(() => {
    hydrateDonors();
    hydrateEvidence();
  }, [hydrateDonors, hydrateEvidence]);

  useEffect(() => {
    setIdentityLabel(stored?.identityLabel ?? '');
    setCondition(stored?.condition ?? 'unknown');
    setDimensionsNote(stored?.dimensionsNote ?? '');
    setConnectorNote(stored?.connectorNote ?? '');
    setPowerNote(stored?.powerNote ?? '');
    setEvidenceUri(stored?.evidenceUri ?? '');
    setNotes(stored?.notes ?? '');
  }, [focused?.resourceId, stored?.recordedAt]);

  async function refreshFieldAction(resource: WorkbenchDonorResource, evidence?: WorkbenchDonorEvidence) {
    setActionState('loading');
    setActionMessage('Asking Hardware-Splicer for the next evidence-bound field action…');
    try {
      const response = await fetch('/api/proxy/hardware/field-agent/next-action', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(fieldAgentPayload(resource, evidence)),
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`field-agent HTTP ${response.status}`);
      const envelope = asRecord(await response.json());
      const fieldOperator = asRecord(envelope.field_operator);
      const operationalCall = asRecord(fieldOperator.operational_call);
      if (!operationalCall.action_id) throw new Error('Field agent did not return an operational action.');
      setFieldAction(operationalCall);
      setActionState('live');
      setActionMessage('Live hardware_field_operator_next_action.v1 guidance. Authority remains evidence-bound.');
    } catch (error: unknown) {
      setFieldAction({});
      setActionState('error');
      setActionMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    if (!focused || !evidenceHydrated) return;
    void refreshFieldAction(focused, stored);
    // Re-run only when the focused donor or the saved worksheet revision changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focused?.resourceId, stored?.recordedAt, evidenceHydrated]);

  if (!focused) return null;

  function saveWorksheet() {
    const record: WorkbenchDonorEvidence = {
      resourceId: focused.resourceId,
      identityLabel: identityLabel.trim(),
      condition,
      dimensionsNote: dimensionsNote.trim(),
      connectorNote: connectorNote.trim(),
      powerNote: powerNote.trim(),
      evidenceUri: evidenceUri.trim(),
      notes: notes.trim(),
      recordedAt: new Date().toISOString(),
      authority: 'operator_claim',
    };
    saveEvidence(record);
    void refreshFieldAction(focused, record);
  }

  const procedure = asStrings(fieldAction.procedure);
  const tools = asStrings(fieldAction.tools);

  return (
    <aside className="fixed right-4 top-[228px] z-50 max-h-[calc(100vh-244px)] w-[390px] overflow-y-auto rounded-xl border border-cyan-300/15 bg-[#07101d]/97 p-3 shadow-2xl backdrop-blur" data-testid="workbench-donor-evidence">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.13em] text-cyan-200">
            <ClipboardCheck className="h-3.5 w-3.5" /> Donor evidence worksheet
          </div>
          <div className="mt-1 text-[11px] font-semibold text-white">{focused.name}</div>
        </div>
        <span className="rounded border border-amber-300/20 bg-amber-300/[0.05] px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-amber-200">operator claim</span>
      </div>

      <div className="mt-3 grid gap-2">
        <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
          Model / marking actually observed
          <input value={identityLabel} onChange={(event) => setIdentityLabel(event.target.value)} placeholder="e.g. DF1208SL, panel code, board revision" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
            Visible condition
            <select value={condition} onChange={(event) => setCondition(event.target.value as DonorCondition)} className="rounded-md border border-white/10 bg-[#07101d] px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25">
              <option value="unknown">Unknown</option>
              <option value="appears_usable">Appears usable</option>
              <option value="damaged">Damaged / suspect</option>
            </select>
          </label>
          <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
            Evidence URI / note source
            <input value={evidenceUri} onChange={(event) => setEvidenceUri(event.target.value)} placeholder="photo://label-2 or bench://run-1" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
          </label>
        </div>
        <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
          Dimensions / fit observation
          <input value={dimensionsNote} onChange={(event) => setDimensionsNote(event.target.value)} placeholder="measured size, mounting pitch, clearance note" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
        </label>
        <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
          Connector / interface observation
          <input value={connectorNote} onChange={(event) => setConnectorNote(event.target.value)} placeholder="pin count, connector family, cable markings" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
        </label>
        <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
          Power observation
          <input value={powerNote} onChange={(event) => setPowerNote(event.target.value)} placeholder="label rating or measured result; state which" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
        </label>
        <label className="grid gap-1 text-[9px] uppercase tracking-[0.1em] text-slate-500">
          Operator notes
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} placeholder="What was actually seen or measured?" className="resize-none rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/25" />
        </label>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button type="button" onClick={saveWorksheet} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-300/20 bg-cyan-300/[0.06] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-cyan-100 hover:bg-cyan-300/[0.1]">
          <Save className="h-3 w-3" /> Save observation
        </button>
        <button type="button" onClick={() => void refreshFieldAction(focused, stored)} disabled={actionState === 'loading'} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-400 hover:bg-white/5 disabled:opacity-50">
          {actionState === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />} Refresh next action
        </button>
        {stored ? <button type="button" onClick={() => clearEvidence(focused.resourceId)} className="ml-auto text-[8px] uppercase tracking-[0.1em] text-slate-600 hover:text-red-300">clear</button> : null}
      </div>

      <div className="mt-3 border-t border-white/8 pt-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-emerald-200/80"><Wrench className="h-3.5 w-3.5" /> Field-agent next action</div>
          {fieldAction.authority ? <span className="text-[8px] uppercase tracking-[0.1em] text-slate-600">{String(fieldAction.authority)}</span> : null}
        </div>
        <div className={`mt-1 text-[9px] leading-4 ${actionState === 'error' ? 'text-red-300/75' : 'text-slate-500'}`}>{actionMessage}</div>
        {fieldAction.summary ? (
          <div className="mt-2 rounded-lg border border-emerald-300/12 bg-emerald-300/[0.025] p-2.5" data-testid="field-agent-action">
            <div className="text-[10px] font-semibold text-emerald-100">{String(fieldAction.summary)}</div>
            {fieldAction.why ? <div className="mt-1 text-[9px] leading-4 text-slate-500">{String(fieldAction.why)}</div> : null}
            {tools.length > 0 ? <div className="mt-2 text-[8px] uppercase tracking-[0.1em] text-slate-600">Tools · {tools.join(' · ')}</div> : null}
            {procedure.length > 0 ? (
              <ol className="mt-2 space-y-1 text-[9px] leading-4 text-slate-400">
                {procedure.slice(0, 5).map((step, index) => <li key={`${index}-${step}`}><span className="mr-1 text-slate-700">{index + 1}.</span>{step}</li>)}
              </ol>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-3 flex items-start gap-1.5 rounded-md border border-amber-300/10 bg-amber-300/[0.02] px-2 py-1.5 text-[8px] leading-4 text-amber-100/45">
        <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" /> Typed observations are not topology measurements and never authorize power, splice or production release by themselves.
      </div>
    </aside>
  );
}
