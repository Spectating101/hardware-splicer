'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, LoaderCircle, RotateCcw } from 'lucide-react';
import { DeviceViewer, type DeviceFinding, type DevicePlan } from '@/components/engineering/device-viewer';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload } from '@/lib/proxy-client';
import { fetchDeviceReclaimMatches, RECLAIM_DEVICE_STORAGE, type DeviceReclaimResult } from '@/lib/device-reclaim';

type Spec = Record<string, unknown>;
type ModuleInfo = { id: string; name: string; sources: { label: string; url: string; as_of: string }[]; dimension_basis?: Record<string, string>; notes?: string[]; pin_orders?: { id: string; label: string; signals: string[]; source: string }[] };

const BASIS_LABELS: Record<string, string> = {
  pcb: 'Board size',
  usb: 'USB socket',
  heights: 'Heights',
  active_area: 'Display area',
  pins: 'Pin order',
};

const SEVERITY: Record<DeviceFinding['severity'], { label: string; className: string; Icon: typeof Info }> = {
  error: { label: 'Problem', className: 'border-red-500/40 bg-red-950/40 text-red-100', Icon: AlertTriangle },
  warning: { label: 'Check this', className: 'border-amber-400/40 bg-amber-950/30 text-amber-100', Icon: AlertTriangle },
  info: { label: 'Note', className: 'border-sky-400/30 bg-sky-950/30 text-sky-100', Icon: Info },
};

export default function DevicePage() {
  usePageTitle('Build a device');
  const [specText, setSpecText] = useState('');
  const [exampleText, setExampleText] = useState('');
  const [examples, setExamples] = useState<Record<string, Spec>>({});
  const [selectedExample, setSelectedExample] = useState('');
  const [plan, setPlan] = useState<DevicePlan | null>(null);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [onHand, setOnHand] = useState<DeviceReclaimResult | null>(null);
  const [onHandError, setOnHandError] = useState('');

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('from') !== 'donor') return;
    const controller = new AbortController();
    (async () => {
      try {
        const raw = window.sessionStorage.getItem(RECLAIM_DEVICE_STORAGE);
        if (!raw || raw.length > 64 * 1024) throw new Error('The reclaim list could not be read. Return to Salvage a board to send it again.');
        // Browser storage contains only input; the backend validates it and checks the current library again.
        const result = await fetchDeviceReclaimMatches(JSON.parse(raw), controller.signal);
        if (!controller.signal.aborted) setOnHand(result);
      } catch {
        if (!controller.signal.aborted) setOnHandError('The reclaim list could not be checked. Return to Salvage a board to send it again.');
      }
    })();
    return () => controller.abort();
  }, []);

  const planFrom = useCallback(async (text: string) => {
    setBusy(true);
    setError('');
    try {
      let spec: unknown;
      try { spec = JSON.parse(text); } catch { throw new Error('That is not valid JSON. Check the brackets and quotes.'); }
      const response = await fetch('/api/proxy/engineering/devices/plan', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(spec), cache: 'no-store' });
      const body = await readJsonPayload<unknown>(response);
      if (!body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The plan could not be made.'));
      const planned = (body as { plan?: DevicePlan }).plan;
      if (!planned) throw new Error('The plan could not be made.');
      setPlan(planned);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The plan could not be made.');
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [examples, library] = await Promise.all([
          fetch('/api/proxy/engineering/devices/examples', { cache: 'no-store' }).then((r) => r.json()),
          fetch('/api/proxy/engineering/devices/modules', { cache: 'no-store' }).then((r) => r.json()),
        ]);
        if (cancelled) return;
        const available = (examples?.examples ?? {}) as Record<string, Spec>;
        const firstKey = available.esp32_oled_usb ? 'esp32_oled_usb' : Object.keys(available)[0];
        const first = available[firstKey];
        if (!first) throw new Error('No example device is available.');
        const text = JSON.stringify(first, null, 2);
        setSpecText(text);
        setExampleText(text);
        setExamples(available);
        setSelectedExample(firstKey);
        setModules((library?.library?.modules ?? []) as ModuleInfo[]);
        await planFrom(text);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'The device examples could not be loaded.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [planFrom]);

  const used = useMemo(() => (plan ? modules.filter((m) => plan.modules.some((p) => p.module === m.id)) : []), [plan, modules]);
  const errors = plan?.findings.filter((f) => f.severity === 'error').length ?? 0;
  const hasWiringFindings = plan?.findings.some((finding) => finding.severity === 'error' || finding.severity === 'warning') ?? false;

  const chooseExample = (key: string) => {
    const example = examples[key];
    if (!example) return;
    const text = JSON.stringify(example, null, 2);
    setSelectedExample(key);
    setSpecText(text);
    setExampleText(text);
    void planFrom(text);
  };

  const choosePinOrder = (moduleRef: string, pinOrder: string) => {
    try {
      const spec = JSON.parse(specText);
      if (!Array.isArray(spec?.modules) || !spec.modules.some((module: { id?: string }) => module?.id === moduleRef)) {
        throw new Error('The spec needs this module before you can choose its pin order.');
      }
      spec.modules = spec.modules.map((module: { id: string }) => module.id === moduleRef ? { ...module, pin_order: pinOrder } : module);
      const text = JSON.stringify(spec, null, 2);
      setSpecText(text);
      void planFrom(text);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? 'That is not valid JSON. Check the brackets and quotes.' : caught instanceof Error ? caught.message : 'The pin order could not be changed.');
    }
  };

  return (
    <main className="min-h-screen bg-[#0b0d12] px-4 pb-24 pt-6 text-stone-200" data-testid="device-page">
      <div className="mx-auto max-w-7xl">
        <header className="mb-3">
          <h1 className="text-lg font-semibold text-stone-50">Build a device</h1>
          <p className="mt-0.5 max-w-3xl text-xs leading-5 text-stone-400">
            Watch a whole gadget go together: the boards into their case, each wire from the pin it starts on to the pin it ends on, then the display, the lid and USB.
            It is a plan to follow and check, not proof that the device works.
          </p>
          {Object.keys(examples).length > 1 ? <div className="mt-3 max-w-xl">
            <label htmlFor="device-example" className="text-xs font-medium text-stone-300">Try an example</label>
            <select id="device-example" data-testid="device-example" value={selectedExample} disabled={busy || loading} onChange={(event) => chooseExample(event.target.value)} className="mt-1 w-full rounded-md border border-stone-700 bg-stone-950 p-2 text-xs text-stone-200">
              {Object.entries(examples).map(([key, example]) => <option key={key} value={key}>{typeof example.name === 'string' ? example.name : key}</option>)}
            </select>
          </div> : null}
        </header>

        {onHand ? <section className="mb-4 rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-on-hand" aria-label="Parts you may have on hand">
          <h2 className="text-sm font-semibold text-stone-100">Parts you may have on hand</h2>
          <p className="mt-1 text-xs leading-5 text-stone-400">{onHand.note}</p>
          <ul className="mt-2 space-y-1 text-xs leading-5 text-stone-300">
            {onHand.parts.filter((part) => part.matched).map((part) => <li key={part.ref} data-testid="device-on-hand-part">
              {part.ref} · marking you read: {part.marking} · kind you reported: {part.kind}
              {part.matches.map((match) => <span key={`${match.module}:${match.relation}:${match.matched_name}`} data-relation={match.relation} className="block text-stone-400">
                {match.relation === 'chip_on_module' ? <>{match.note} ({match.tier === 'exact' ? 'same name' : 'variant'}). <a href={match.source} target="_blank" rel="noreferrer noopener" className="text-sky-300 underline-offset-2 hover:underline">Source</a></> : <>Library: {match.name} ({match.tier === 'exact' ? 'same name' : 'variant'}).</>}
              </span>)}
            </li>)}
          </ul>
          {!onHand.parts.some((part) => part.matched) ? <p className="mt-2 text-xs text-stone-400">No exact or variant name matches in the device library.</p> : null}
        </section> : null}
        {onHandError ? <p role="status" className="mb-4 text-xs text-stone-400" data-testid="device-on-hand-error">{onHandError}</p> : null}

        {loading ? <div className="flex h-64 items-center justify-center text-stone-400"><LoaderCircle className="h-5 w-5 animate-spin" aria-label="Loading" /></div> : null}
        {!loading && !plan ? <div role="alert" className="rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-100" data-testid="device-error">{error || 'No plan is available.'}</div> : null}

        {plan ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <section aria-label="Assembly animation" className="min-w-0 overflow-hidden rounded-xl border border-stone-800 lg:sticky lg:top-16 lg:h-[calc(100vh-9.5rem)] lg:min-h-[600px]">
              <DeviceViewer plan={plan} />
            </section>

            <aside className="min-w-0 space-y-4 [overflow-wrap:anywhere]" aria-label="About this device">
              {plan.modules.map((placed) => {
                const orders = modules.find((module) => module.id === placed.module)?.pin_orders;
                if (!orders?.length) return null;
                return <section key={placed.id} className="rounded-xl border border-stone-800 bg-stone-900/50 p-4">
                  <label htmlFor={`pin-order-${placed.id}`} className="text-sm font-semibold text-stone-100">Which order is printed on your module?</label>
                  <p className="mt-1 text-xs leading-5 text-stone-400">{placed.name}. {placed.kind === 'display' ? 'Read left to right looking at the screen, with the header at the top. ' : null}Connect by the printed labels, not by position in the picture.</p>
                  <select id={`pin-order-${placed.id}`} data-testid="device-pin-order" value={placed.pin_order ?? ''} disabled={busy} onChange={(event) => choosePinOrder(placed.id, event.target.value)} className="mt-2 w-full rounded-md border border-stone-700 bg-stone-950 p-2 text-xs text-stone-200">
                    {orders.map((order) => <option key={order.id} value={order.id}>{order.signals.join(', ')} ({order.label})</option>)}
                  </select>
                </section>;
              })}
              <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-findings">
                <h2 className="text-sm font-semibold text-stone-100">Wiring check</h2>
                {!hasWiringFindings ? (
                  <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-300"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" /><span>These checks found nothing wrong with the wiring. That does not prove it will work. These are the checks this tool makes; a wire that passes them is not a wire that works.</span></p>
                ) : null}
                {plan.findings.length > 0 ? (
                  <ul className="mt-2 space-y-2">
                    {plan.findings.map((finding, index) => {
                      const tone = SEVERITY[finding.severity];
                      return (
                        <li key={`${finding.rule}-${index}`} className={`rounded-lg border p-2.5 text-xs leading-5 ${tone.className}`} data-severity={finding.severity} data-rule={finding.rule}>
                          <div className="flex items-center gap-1.5 font-semibold"><tone.Icon className="h-3.5 w-3.5" aria-hidden="true" />{tone.label}</div>
                          <div className="mt-0.5">{finding.message}</div>
                          <div className="mt-1 text-[10px] opacity-70">Basis: {finding.basis}</div>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </section>

              <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-shopping">
                <h2 className="text-sm font-semibold text-stone-100">What you need</h2>
                <ul className="mt-2 space-y-1.5 text-xs leading-5 text-stone-300">
                  {plan.shopping.map((row) => (
                    <li key={row.item}><span className="font-medium text-stone-100">{row.quantity} × {row.item}</span>{row.note ? <span className="text-stone-500"> — {row.note}</span> : null}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-measure">
                <h2 className="text-sm font-semibold text-stone-100">Before you print the case</h2>
                <p className="mt-2 text-xs leading-5 text-stone-300">{plan.case.basis}</p>
                <dl className="mt-2 space-y-1.5 text-xs leading-5 text-stone-400">
                  {used.flatMap((module) => Object.entries(module.dimension_basis ?? {}).map(([key, text]) => (
                    <div key={`${module.id}-${key}`}><dt className="font-medium text-stone-200">{module.name.split(/ \(|, /)[0]}: {BASIS_LABELS[key] ?? key}</dt><dd>{text}</dd></div>
                  )))}
                </dl>
                {plan.case.window ? <p className="mt-2 text-xs leading-5 text-stone-400">Window: {plan.case.window.basis}.</p> : null}
              </section>

              <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-sources">
                <h2 className="text-sm font-semibold text-stone-100">Where the numbers come from</h2>
                <ul className="mt-2 space-y-1.5 text-xs leading-5 text-stone-400">
                  {used.flatMap((module) => module.sources.map((source) => (
                    <li key={`${module.id}-${source.url}`}><a href={source.url} target="_blank" rel="noreferrer" className="text-sky-300 underline-offset-2 hover:underline">{source.label}</a> <span className="text-stone-500">· read {source.as_of}</span></li>
                  )))}
                </ul>
              </section>

              <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4">
                <h2 className="text-sm font-semibold text-stone-100">Change the wiring</h2>
                <p className="mt-1 text-xs leading-5 text-stone-400">Edit which pin goes to which and see what the checks say. Try putting SDA on <code className="text-stone-200">mcu.D2</code> or the supply on <code className="text-stone-200">mcu.5V</code>.</p>
                <textarea
                  value={specText}
                  onChange={(event) => setSpecText(event.target.value)}
                  spellCheck={false}
                  aria-label="Device spec"
                  data-testid="device-spec-editor"
                  className="mt-2 h-56 w-full resize-y rounded-lg border border-stone-700 bg-stone-950 p-2 font-mono text-[11px] leading-4 text-stone-200 focus:border-amber-300 focus:outline-none"
                />
                <div className="mt-2 flex items-center gap-2">
                  <button type="button" onClick={() => void planFrom(specText)} disabled={busy} data-testid="device-spec-apply" className="inline-flex h-8 items-center gap-1.5 rounded-md bg-amber-300 px-3 text-xs font-semibold text-stone-950 hover:bg-amber-200 disabled:opacity-50">
                    {busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}Check this wiring
                  </button>
                  <button type="button" onClick={() => { setSpecText(exampleText); void planFrom(exampleText); }} disabled={busy} className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium text-stone-300 hover:bg-stone-800 disabled:opacity-50">
                    <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />Back to the example
                  </button>
                </div>
                {error ? <p role="alert" data-testid="device-error" className="mt-2 rounded-md border border-red-500/40 bg-red-950/40 p-2 text-xs leading-5 text-red-100">{error}</p> : null}
                {errors > 0 ? <p className="mt-2 text-[11px] text-red-300">{errors} {errors === 1 ? 'problem' : 'problems'} in this wiring.</p> : null}
              </section>
            </aside>
          </div>
        ) : null}
      </div>
    </main>
  );
}
