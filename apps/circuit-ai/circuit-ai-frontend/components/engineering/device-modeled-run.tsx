'use client';

import { useEffect, useRef, useState } from 'react';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload } from '@/lib/proxy-client';

type Scenario = { scenario: string; pass: boolean; detail: string; modeled_serial?: string[] };
type Phase = { status: string; reason?: string; scenarios: Scenario[] };
type Result = {
  schema_version: string; status: string; claim_boundary: string;
  spec_sha256: string; proposal_sha256: string; host: Phase; vendor_host: Phase;
  esp32_compilation: string; physical_correctness: string;
  firmware_authorized: boolean; power_on_authorized: boolean;
};

export function DeviceModeledRun({ specText, enabled }: { specText: string; enabled: boolean }) {
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
    setResult(null);
    setError('');
    setBusy(false);
    return () => { generation.current += 1; controller.current?.abort(); };
  }, [specText, enabled]);

  const run = async () => {
    const id = ++generation.current;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch('/api/proxy/engineering/devices/application/run', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ spec: JSON.parse(specText) }), signal: request.signal, cache: 'no-store',
      });
      const body = await readJsonPayload<unknown>(response);
      if (!response.ok || !body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The modeled run could not complete.'));
      const value = (body as { result?: Result }).result;
      if (!value || value.schema_version !== 'hardware_splicer.device_application_modeled_run.v1'
        || value.physical_correctness !== 'UNPROVEN' || value.firmware_authorized !== false || value.power_on_authorized !== false
        || !/^[0-9a-f]{64}$/.test(value.proposal_sha256) || !Array.isArray(value.host?.scenarios) || !Array.isArray(value.vendor_host?.scenarios)) {
        throw new Error('The backend did not return a bounded modeled-run report.');
      }
      if (id === generation.current && !request.signal.aborted) setResult(value);
    } catch (caught) {
      if (id === generation.current && !request.signal.aborted) setError(caught instanceof Error ? caught.message : 'The modeled run could not complete.');
    } finally {
      if (id === generation.current) setBusy(false);
    }
  };

  const download = () => {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + '\n'], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'device-modeled-run.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="device-modeled-run">
    <h2 className="text-sm font-semibold text-stone-100">Run the application off-hardware</h2>
    <p className="mt-1 text-xs leading-5 text-stone-400">Generate this wiring&apos;s application, compile its host harness and exercise synthetic readings, faults and recovery. Vendor-driver tests run only when the server has the pinned libraries.</p>
    <p className="mt-1 text-xs leading-5 text-stone-400" data-testid="device-modeled-boundary">Not an ESP32 emulator, physical readings, electrical validation or permission to flash or power.</p>
    <button type="button" data-testid="device-modeled-start" onClick={() => void run()} disabled={!enabled || busy} className="mt-2 rounded-md bg-stone-800 px-3 py-2 text-xs font-medium text-stone-100 hover:bg-stone-700 disabled:opacity-50">
      {busy ? 'Running modeled tests…' : 'Run modeled tests'}
    </button>
    {!enabled ? <p className="mt-1 text-xs text-amber-200">Check this wiring and resolve its findings first.</p> : null}
    {error ? <p role="alert" data-testid="device-modeled-error" className="mt-2 text-xs text-amber-200">{error}</p> : null}
    {result && enabled ? <div className="mt-3 space-y-2" data-testid="device-modeled-result" data-status={result.status}>
      <p role="status" className={`rounded-md border px-2 py-1.5 text-xs font-semibold ${result.status === 'PASSED' ? 'border-emerald-500/40 bg-emerald-950/30 text-emerald-100' : result.status === 'PARTIAL' ? 'border-amber-400/40 bg-amber-950/30 text-amber-100' : 'border-red-500/40 bg-red-950/40 text-red-100'}`}>{result.status === 'PASSED' ? 'Core and vendor-host tests passed' : result.status === 'PARTIAL' ? 'Core tests passed; vendor-host tests were not run' : 'Modeled run failed'}</p>
      <p className="text-[11px] leading-4 text-stone-400" data-testid="device-modeled-claim">Modeled results only. Nothing here is a bench reading, and flashing and power authorization remain closed.</p>
      {[['Core logic', result.host], ['Vendor-host driver', result.vendor_host]] .map(([title, phase]) => {
        const report = phase as Phase;
        return <div key={title as string} className="space-y-1 text-xs" data-testid="device-modeled-phase">
          <p>{title as string}: {report.status} ({report.scenarios.filter((s) => s.pass).length}/{report.scenarios.length} scenarios)</p>
          {report.reason ? <p className="text-stone-400">{report.reason}</p> : null}
          {report.scenarios.map((scenario) => <details key={scenario.scenario} open={!scenario.pass} className="rounded border border-stone-700" data-testid="device-modeled-scenario" data-pass={String(scenario.pass)}>
            <summary className="flex min-h-9 cursor-pointer items-center gap-2 px-2 py-1.5"><span aria-hidden="true" className={scenario.pass ? 'text-emerald-400' : 'text-red-400'}>{scenario.pass ? '✓' : '✗'}</span><span className="min-w-0 break-words">{scenario.scenario}: {scenario.pass ? 'passed' : 'failed'}</span></summary>
            <div className="px-2 pb-2">
              <p className="text-stone-400">{scenario.detail}</p>
              {scenario.modeled_serial?.length ? <><p className="mt-1 text-stone-400">Modeled serial output — synthetic, not bench evidence</p><pre className="mt-1 max-h-44 overflow-auto whitespace-pre text-[11px] leading-4" data-testid="device-modeled-serial">{scenario.modeled_serial.slice(0, 120).join('\n')}</pre></> : null}
            </div>
          </details>)}
        </div>;
      })}
      <p className="break-all font-mono text-[11px] text-stone-400" data-testid="device-modeled-hash">Source ZIP SHA-256: {result.proposal_sha256}</p>
      <p className="text-[11px] text-stone-400">ESP32 compilation: {result.esp32_compilation}. Physical correctness: {result.physical_correctness}. Flashing and power authorization remain closed.</p>
      <button type="button" data-testid="device-modeled-download" onClick={download} className="rounded-md bg-stone-800 px-3 py-2 text-xs">Download modeled-run report</button>
    </div> : null}
  </section>;
}
