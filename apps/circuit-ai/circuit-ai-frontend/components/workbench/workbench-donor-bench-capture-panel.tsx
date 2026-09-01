'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, FlaskConical, Loader2, Plus, Trash2 } from 'lucide-react';
import { constructorTarget } from '@/lib/workbench-constructor-demo';
import { useWorkbenchDonorEvidenceStore } from '@/lib/workbench-donor-evidence-store';
import { type WorkbenchDonorResource } from '@/lib/workbench-donor-intake-store';
import {
  useWorkbenchDonorBenchStore,
  type BenchCalibrationStatus,
  type BenchMeasurementKind,
  type BenchMeasurementStatus,
  type WorkbenchBenchMeasurement,
  type WorkbenchDonorBenchCapture,
} from '@/lib/workbench-donor-bench-store';

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function safeId(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'capture';
}

function backendCapture(capture: WorkbenchDonorBenchCapture) {
  const instruments = Array.from(new Map(capture.measurements.map((measurement) => [measurement.instrumentId, {
    instrument_id: measurement.instrumentId,
    instrument_type: measurement.instrumentType,
    calibration_status: measurement.calibrationStatus,
  }])).values());
  const artifacts = Array.from(new Set(capture.measurements.map((measurement) => measurement.evidenceUri).filter(Boolean)))
    .map((uri, index) => ({ kind: 'measurement_log', uri, notes: `Bench evidence artifact ${index + 1}` }));

  return {
    schema_version: 'bench_topology_capture.v1',
    capture_id: capture.captureId,
    operator_id: capture.operatorId,
    recorded_at: capture.recordedAt,
    instruments,
    connectors: [],
    measurements: capture.measurements.map((measurement) => ({
      measurement_id: measurement.measurementId,
      kind: measurement.kind,
      target: measurement.target,
      value: measurement.value,
      unit: measurement.unit,
      status: measurement.status,
      instrument_id: measurement.instrumentId,
      instrument_type: measurement.instrumentType,
      calibration_status: measurement.calibrationStatus,
      evidence_uri: measurement.evidenceUri,
      notes: measurement.notes,
    })),
    artifacts,
  };
}

function progressPayload(resource: WorkbenchDonorResource, capture: WorkbenchDonorBenchCapture | undefined, operatorClaim: Record<string, unknown>) {
  const markings = String(operatorClaim.identityLabel || '').trim();
  const damaged = operatorClaim.condition === 'damaged';
  return {
    goal: constructorTarget.prompt,
    device_hint: resource.name,
    required_capabilities: resource.capabilities,
    strategy_mode: 'constrained',
    target_authority_level: 'measured_topology',
    constraints: {
      safety_level: 'low_voltage_only',
      evidence_policy: 'instrument and artifact provenance required before measurement authority can advance',
    },
    board_evidence: {
      schema_version: 'board_evidence.v1',
      components: [{ id: resource.resourceId, label: resource.name, kind: 'donor_resource' }],
      markings: markings ? [{ id: `${resource.resourceId}-marking`, marking: markings }] : [],
      connectors: [],
      damage: damaged ? [{ id: `${resource.resourceId}-damage`, label: 'Operator marked donor as damaged or suspect.' }] : [],
      salvage_candidates: [{ id: `${resource.resourceId}-reuse`, label: `Reuse ${resource.name}` }],
    },
    photo_observations: [{
      resource_id: resource.resourceId,
      label: resource.observedLabel,
      confidence: resource.confidence,
      source_name: resource.sourceName,
    }],
    operator_claim: operatorClaim,
    use_reference_catalog: false,
    ...(capture ? { bench_topology_capture: backendCapture(capture) } : {}),
  };
}

function defaultUnit(kind: string) {
  if (kind === 'resistance') return 'ohm';
  if (kind === 'voltage') return 'V';
  if (kind === 'current') return 'A';
  if (kind === 'thermal') return 'C';
  return '';
}

export function WorkbenchDonorBenchCapturePanel({ resource }: { resource: WorkbenchDonorResource }) {
  const captures = useWorkbenchDonorBenchStore((state) => state.captures);
  const hydrated = useWorkbenchDonorBenchStore((state) => state.hydrated);
  const hydrate = useWorkbenchDonorBenchStore((state) => state.hydrate);
  const saveCapture = useWorkbenchDonorBenchStore((state) => state.saveCapture);
  const clearCapture = useWorkbenchDonorBenchStore((state) => state.clearCapture);
  const operatorEvidence = useWorkbenchDonorEvidenceStore((state) => state.records[resource.resourceId]);
  const capture = captures[resource.resourceId];

  const [state, setState] = useState<'idle' | 'loading' | 'live' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [progressEnvelope, setProgressEnvelope] = useState<Record<string, unknown>>({});
  const [operatorId, setOperatorId] = useState(capture?.operatorId ?? 'operator');
  const [instrumentId, setInstrumentId] = useState('bench-dmm-01');
  const [instrumentType, setInstrumentType] = useState('calibrated_dmm');
  const [calibrationStatus, setCalibrationStatus] = useState<BenchCalibrationStatus>('valid');
  const [evidenceUri, setEvidenceUri] = useState('');
  const [value, setValue] = useState('');
  const [status, setStatus] = useState<BenchMeasurementStatus>('pass');
  const [notes, setNotes] = useState('');
  const [manualKind, setManualKind] = useState<BenchMeasurementKind>('resistance');
  const [manualTarget, setManualTarget] = useState('');

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => {
    if (capture?.operatorId) setOperatorId(capture.operatorId);
  }, [capture?.operatorId]);

  const progress = asRecord(progressEnvelope.progress);
  const nextMeasurement = asRecord(progressEnvelope.next_measurement);
  const integrity = asRecord(progressEnvelope.capture_integrity);
  const authorityClosure = asRecord(progressEnvelope.authority_closure);
  const authorityAfter = asRecord(authorityClosure.authority_after);
  const currentKind = String(nextMeasurement.kind || manualKind) as BenchMeasurementKind;
  const currentTarget = String(nextMeasurement.target || manualTarget);
  const currentUnit = String(nextMeasurement.unit || defaultUnit(currentKind));
  const nextPrompt = String(nextMeasurement.prompt || 'Record a trusted bench measurement.');
  const measurements = capture?.measurements ?? [];

  const operatorClaim = useMemo(() => operatorEvidence ? {
    identityLabel: operatorEvidence.identityLabel,
    condition: operatorEvidence.condition,
    dimensionsNote: operatorEvidence.dimensionsNote,
    connectorNote: operatorEvidence.connectorNote,
    powerNote: operatorEvidence.powerNote,
    evidenceUri: operatorEvidence.evidenceUri,
    notes: operatorEvidence.notes,
    authority: operatorEvidence.authority,
    recordedAt: operatorEvidence.recordedAt,
  } : {}, [operatorEvidence]);

  async function refresh(nextCapture = capture) {
    setState('loading');
    setMessage('Checking the real measurement-session contract…');
    try {
      const response = await fetch('/api/proxy/hardware/measurement-session/progress', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(progressPayload(resource, nextCapture, operatorClaim)),
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`measurement-session HTTP ${response.status}`);
      const envelope = asRecord(await response.json());
      const session = asRecord(envelope.measurement_session_progress);
      if (session.schema_version !== 'measurement_session_progress.v1') throw new Error('measurement_session_progress.v1 response required');
      setProgressEnvelope(session);
      setState('live');
      const summary = asRecord(session.progress);
      setMessage(`${Number(summary.closed_count || 0)} closed · ${Number(summary.open_count || 0)} open · ${String(session.status || 'unknown')}`);
    } catch (error: unknown) {
      setProgressEnvelope({});
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    if (!hydrated) return;
    void refresh(capture);
    // Re-run when switching donor or when a stored capture revision changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource.resourceId, capture?.updatedAt, hydrated]);

  function addMeasurement() {
    const target = currentTarget.trim();
    const reading = value.trim();
    const instrument = instrumentId.trim();
    const artifact = evidenceUri.trim();
    const operator = operatorId.trim();
    if (!target || !reading || !instrument || !artifact || !operator) {
      setState('error');
      setMessage('Operator, target, value, instrument ID and evidence URI are required before a reading can enter the capture packet.');
      return;
    }
    const now = new Date().toISOString();
    const measurement: WorkbenchBenchMeasurement = {
      measurementId: `m-${Date.now()}-${safeId(currentKind)}`,
      kind: currentKind,
      target,
      value: reading,
      unit: currentUnit,
      status,
      instrumentId: instrument,
      instrumentType: instrumentType.trim() || 'unknown_instrument',
      calibrationStatus,
      evidenceUri: artifact,
      notes: notes.trim(),
    };
    const nextCapture: WorkbenchDonorBenchCapture = {
      resourceId: resource.resourceId,
      captureId: capture?.captureId || `bench-${safeId(resource.resourceId)}-${Date.now()}`,
      operatorId: operator,
      recordedAt: capture?.recordedAt || now,
      measurements: [...measurements, measurement],
      updatedAt: now,
      schemaVersion: 'bench_topology_capture.v1',
    };
    saveCapture(nextCapture);
    setValue('');
    setNotes('');
    setManualTarget('');
    void refresh(nextCapture);
  }

  const canAdd = Boolean(operatorId.trim() && instrumentId.trim() && evidenceUri.trim() && currentTarget.trim() && value.trim());
  const verdict = String(integrity.verdict || 'measurement_capture_required');
  const authorityLevel = String(authorityAfter.current_authority_level || 'visual_candidate');
  const requiredRows = asArray(progressEnvelope.required_measurements).map(asRecord);

  return (
    <section className="mt-3 border-t border-white/8 pt-3" data-testid="donor-bench-capture">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-violet-200/85"><FlaskConical className="h-3.5 w-3.5" /> Trusted bench capture</div>
          <div className="mt-1 text-[9px] leading-4 text-slate-500">Build a real <code>bench_topology_capture.v1</code> packet one reading at a time. Instrument, calibration, operator and artifact provenance stay attached.</div>
        </div>
        {measurements.length > 0 ? <button type="button" onClick={() => clearCapture(resource.resourceId)} className="text-slate-600 hover:text-red-300" aria-label="Clear bench capture"><Trash2 className="h-3.5 w-3.5" /></button> : null}
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-md border border-white/8 bg-black/10 px-2 py-1.5"><div className="text-sm font-semibold text-white">{Number(progress.closed_count || 0)}</div><div className="text-[7px] uppercase tracking-[0.1em] text-slate-600">closed</div></div>
        <div className="rounded-md border border-white/8 bg-black/10 px-2 py-1.5"><div className="text-sm font-semibold text-amber-200">{Number(progress.open_count || 0)}</div><div className="text-[7px] uppercase tracking-[0.1em] text-slate-600">open</div></div>
        <div className="rounded-md border border-white/8 bg-black/10 px-2 py-1.5"><div className="text-sm font-semibold text-cyan-200">{Math.round(Number(progress.progress_score || 0) * 100)}%</div><div className="text-[7px] uppercase tracking-[0.1em] text-slate-600">packet</div></div>
      </div>

      <div className="mt-2 rounded-lg border border-violet-300/12 bg-violet-300/[0.025] p-2.5" data-testid="next-bench-measurement">
        <div className="flex items-center justify-between gap-2"><span className="text-[8px] font-semibold uppercase tracking-[0.1em] text-violet-200/70">Next reading</span><span className="text-[8px] text-slate-600">{currentKind}</span></div>
        <div className="mt-1 text-[10px] font-medium text-slate-200">{currentTarget || 'Choose a measurement target'}</div>
        <div className="mt-1 text-[9px] leading-4 text-slate-500">{nextPrompt}</div>
      </div>

      {!nextMeasurement.kind ? (
        <div className="mt-2 grid grid-cols-[120px_1fr] gap-2">
          <select value={manualKind} onChange={(event) => setManualKind(event.target.value as BenchMeasurementKind)} className="rounded-md border border-white/10 bg-[#07101d] px-2 py-1.5 text-[9px] text-slate-300">
            <option value="resistance">resistance</option><option value="continuity">continuity</option><option value="voltage">voltage</option><option value="current">current</option><option value="thermal">thermal</option>
          </select>
          <input value={manualTarget} onChange={(event) => setManualTarget(event.target.value)} placeholder="Measurement target" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] text-slate-200 outline-none focus:border-violet-300/25" />
        </div>
      ) : null}

      <div className="mt-2 grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Operator ID<input value={operatorId} onChange={(event) => setOperatorId(event.target.value)} className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200" /></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Evidence URI<input value={evidenceUri} onChange={(event) => setEvidenceUri(event.target.value)} placeholder="bench://run-1/log" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200" /></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Instrument ID<input value={instrumentId} onChange={(event) => setInstrumentId(event.target.value)} className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200" /></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Instrument type<select value={instrumentType} onChange={(event) => setInstrumentType(event.target.value)} className="rounded-md border border-white/10 bg-[#07101d] px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200"><option value="calibrated_dmm">calibrated DMM</option><option value="current_limited_supply">current-limited supply</option><option value="thermal_probe">thermal probe</option><option value="usb_power_meter">USB power meter</option><option value="other_instrument">other</option></select></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Calibration<select value={calibrationStatus} onChange={(event) => setCalibrationStatus(event.target.value as BenchCalibrationStatus)} className="rounded-md border border-white/10 bg-[#07101d] px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200"><option value="valid">valid</option><option value="unknown">unknown</option><option value="expired">expired</option></select></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Result status<select value={status} onChange={(event) => setStatus(event.target.value as BenchMeasurementStatus)} className="rounded-md border border-white/10 bg-[#07101d] px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200"><option value="pass">pass</option><option value="failed">failed / unsafe</option><option value="recorded">recorded only</option></select></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Value<input value={value} onChange={(event) => setValue(event.target.value)} placeholder={currentKind === 'resistance' || currentKind === 'continuity' ? 'pass or measured value' : 'numeric reading'} className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200" /></label>
        <label className="grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Unit<input value={currentUnit} readOnly className="rounded-md border border-white/7 bg-black/10 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-500" /></label>
      </div>
      <label className="mt-2 grid gap-1 text-[8px] uppercase tracking-[0.09em] text-slate-600">Measurement note<input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Current limit, probe points, physical orientation, anomalies…" className="rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[9px] normal-case tracking-normal text-slate-200" /></label>

      <button type="button" disabled={!canAdd || state === 'loading'} onClick={addMeasurement} className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-violet-300/20 bg-violet-300/[0.06] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-violet-100 hover:bg-violet-300/[0.1] disabled:cursor-not-allowed disabled:opacity-35">
        {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />} Add trusted reading
      </button>

      <div className={`mt-2 text-[8px] leading-4 ${state === 'error' ? 'text-red-300/80' : 'text-slate-600'}`}>{message}</div>

      {measurements.length > 0 ? (
        <div className="mt-2 space-y-1" data-testid="bench-measurement-list">
          {measurements.slice(-6).map((measurement) => (
            <div key={measurement.measurementId} className="flex items-start gap-2 rounded-md border border-white/7 bg-black/10 px-2 py-1.5">
              {measurement.status === 'failed' ? <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-red-300" /> : <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-300/70" />}
              <div className="min-w-0 flex-1"><div className="truncate text-[8px] font-medium text-slate-300">{measurement.kind} · {measurement.target}</div><div className="mt-0.5 text-[8px] text-slate-600">{measurement.value}{measurement.unit ? ` ${measurement.unit}` : ''} · {measurement.instrumentId} · calibration {measurement.calibrationStatus}</div></div>
            </div>
          ))}
        </div>
      ) : null}

      {requiredRows.length > 0 ? <div className="mt-2 text-[8px] leading-4 text-slate-600">Template · {requiredRows.filter((row) => row.status === 'open').length} required readings still open.</div> : null}

      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="rounded-md border border-white/8 bg-black/10 px-2 py-1.5"><div className="flex items-center gap-1 text-[7px] uppercase tracking-[0.1em] text-slate-600"><Activity className="h-2.5 w-2.5" /> Capture verdict</div><div className="mt-1 text-[8px] font-medium text-slate-300">{verdict}</div></div>
        <div className="rounded-md border border-white/8 bg-black/10 px-2 py-1.5"><div className="text-[7px] uppercase tracking-[0.1em] text-slate-600">Authority after</div><div className="mt-1 text-[8px] font-medium text-slate-300">{authorityLevel}</div></div>
      </div>

      <div className="mt-2 text-[8px] leading-4 text-amber-100/45">A reading with missing/expired calibration or no artifact can be recorded, but HS will not treat it as trusted production measurement authority. A failed safety reading keeps the session blocked.</div>
    </section>
  );
}
