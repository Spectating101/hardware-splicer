'use client';

import { type ChangeEvent, useEffect, useState } from 'react';
import { Camera, Loader2, RotateCcw, ShieldAlert } from 'lucide-react';
import { useWorkbenchDonorIntakeStore, type WorkbenchDonorResource } from '@/lib/workbench-donor-intake-store';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function rows(value: unknown) {
  return Array.isArray(value) ? value.map(record) : [];
}

function normalizeId(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown';
}

function normalizeCapability(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

function clampConfidence(value: unknown, fallback = 0.5) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : fallback;
}

function inferCapabilities(label: string) {
  const text = label.toLowerCase();
  const capabilities = new Set<string>();
  if (/fan|blower|pump/.test(text)) capabilities.add('fan_or_pump');
  if (/fan|motor|pump|actuator|servo/.test(text)) capabilities.add('motor_or_load');
  if (/display|screen|lcd|oled/.test(text)) capabilities.add('display_or_ui');
  if (/button|switch|keyboard|keypad/.test(text)) capabilities.add('switch_or_button');
  if (/connector|usb|header|socket|jack|port/.test(text)) capabilities.add('connector');
  if (/camera|vision|webcam|sensor/.test(text)) capabilities.add('camera_or_vision');
  if (/controller|microcontroller|mcu|processor|mainboard|motherboard|board/.test(text)) capabilities.add('controller');
  if (/battery|power|converter|regulator|supply/.test(text)) capabilities.add('power');
  if (/case|shell|enclosure|frame|chassis/.test(text)) capabilities.add('enclosure_candidate');
  if (capabilities.size === 0) capabilities.add('unknown_reusable_part');
  return [...capabilities];
}

function provisionalResources(payload: unknown, sourceName: string): WorkbenchDonorResource[] {
  const envelope = record(payload);
  const results = record(envelope.results);
  const functionality = record(results.functionality_data);
  const detections = rows(results.detections);
  const summary = record(envelope.summary);
  const overallConfidence = clampConfidence(summary.confidence_score, 0.5);
  const components = rows(functionality.components);

  if (components.length > 0) {
    return components.slice(0, 12).map((component, index) => {
      const type = String(component.type || component.id || `observed-part-${index + 1}`);
      const declaredCapabilities = Array.isArray(component.capabilities)
        ? component.capabilities.map(String).map(normalizeCapability).filter(Boolean)
        : [];
      const capabilities = [...new Set([...declaredCapabilities, ...inferCapabilities(type)])];
      return {
        resourceId: `photo-${normalizeId(sourceName)}-${normalizeId(String(component.id || type))}-${index + 1}`,
        name: String(component.description || component.type || component.id || `Observed donor part ${index + 1}`),
        observedLabel: type,
        capabilities,
        confidence: overallConfidence,
        evidenceStatus: 'needs_evidence',
        sourceKind: 'photo_analysis',
        sourceName,
        note: 'Photo-derived functional observation. Identity, condition, geometry, power and interfaces remain unverified.',
      };
    });
  }

  return detections.slice(0, 12).map((detection, index) => {
    const label = String(detection.class_name || `observed-part-${index + 1}`);
    return {
      resourceId: `photo-${normalizeId(sourceName)}-${normalizeId(label)}-${index + 1}`,
      name: `Observed ${label}`,
      observedLabel: label,
      capabilities: inferCapabilities(label),
      confidence: clampConfidence(detection.confidence, overallConfidence),
      evidenceStatus: 'needs_evidence',
      sourceKind: 'photo_analysis',
      sourceName,
      note: 'Photo-derived visual observation. Identity, condition, geometry, power and interfaces remain unverified.',
    };
  });
}

export function DonorIntakePanel() {
  const resources = useWorkbenchDonorIntakeStore((state) => state.resources);
  const hydrated = useWorkbenchDonorIntakeStore((state) => state.hydrated);
  const hydrate = useWorkbenchDonorIntakeStore((state) => state.hydrate);
  const addResources = useWorkbenchDonorIntakeStore((state) => state.addResources);
  const clearResources = useWorkbenchDonorIntakeStore((state) => state.clearResources);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  useEffect(() => hydrate(), [hydrate]);

  async function analyzeDonor(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setStatus('loading');
    setMessage(`Reading ${file.name} as donor evidence…`);
    const form = new FormData();
    form.set('file', file, file.name);
    form.set('backend', 'hybrid');
    form.set('enable_ocr', 'true');
    form.set('enable_quality_assessment', 'true');

    try {
      const response = await fetch('/api/proxy/analyze', { method: 'POST', body: form });
      if (!response.ok) throw new Error(`donor analysis HTTP ${response.status}`);
      const observed = provisionalResources(await response.json(), file.name);
      if (observed.length === 0) throw new Error('No reusable part observations were returned from this image.');
      addResources(observed);
      setStatus('success');
      setMessage(`${observed.length} provisional ${observed.length === 1 ? 'resource' : 'resources'} added. They may affect planning, but they still require engineering evidence.`);
    } catch (error: unknown) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.025] p-4" aria-label="Donor intake">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
            <Camera className="h-4 w-4" /> Start with messy hardware
          </div>
          <h2 className="mt-1 text-base font-semibold text-white">Photograph a donor item before you know exactly what it is.</h2>
          <p className="mt-1 text-[11px] leading-5 text-slate-400">HS can turn visual observations into provisional inventory for reuse planning. A photo never proves voltage, pinout, physical fit, condition or fabrication authority.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-cyan-100 hover:bg-cyan-300/[0.1]">
            {status === 'loading' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
            Analyze donor photo
            <input type="file" accept="image/*" className="sr-only" aria-label="Analyze donor photo" disabled={status === 'loading'} onChange={analyzeDonor} />
          </label>
          {hydrated && resources.length > 0 ? (
            <button type="button" onClick={clearResources} className="rounded-lg border border-white/10 p-2 text-slate-500 hover:bg-white/5 hover:text-slate-200" aria-label="Clear provisional donor resources"><RotateCcw className="h-3.5 w-3.5" /></button>
          ) : null}
        </div>
      </div>

      {message ? <div className={`mt-3 text-[10px] leading-4 ${status === 'error' ? 'text-red-300' : status === 'success' ? 'text-emerald-300/80' : 'text-slate-500'}`}>{message}</div> : null}

      {hydrated && resources.length > 0 ? (
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3" data-testid="provisional-donor-resources">
          {resources.map((resource) => (
            <div key={resource.resourceId} className="rounded-lg border border-white/8 bg-black/10 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[11px] font-medium text-white">{resource.name}</div>
                  <div className="mt-1 text-[9px] uppercase tracking-[0.12em] text-slate-600">{resource.capabilities.join(' · ')}</div>
                </div>
                <span className="shrink-0 rounded border border-amber-300/20 bg-amber-300/[0.05] px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-amber-200">{Math.round(resource.confidence * 100)}% observed</span>
              </div>
              <div className="mt-2 flex items-start gap-1.5 text-[9px] leading-4 text-amber-100/55"><ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" /> Needs identity, condition and interface evidence before reuse can be authorized.</div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
