'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleOff, Cpu, LoaderCircle, RefreshCw, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  summarizeExecutionCapability,
  type EngineeringExecutionCapability,
  type ExecutionCapabilityResponse,
} from '@/lib/engineering-execution-capability';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

export function EngineeringExecutionCapabilityPanel() {
  const [report, setReport] = useState<EngineeringExecutionCapability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/proxy/engineering/execution/capabilities', {
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ExecutionCapabilityResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Execution capability truth is unavailable.'));
      }
      const capability = (payload as ExecutionCapabilityResponse | null)?.execution_capability;
      if (!capability) throw new Error('The capability endpoint returned no runtime report.');
      setReport(capability);
    } catch (value: unknown) {
      setReport(null);
      setError(value instanceof Error ? value.message : 'Capability lookup failed.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const summary = useMemo(() => summarizeExecutionCapability(report), [report]);
  const usefulRows = useMemo(() => {
    return [...(report?.operations || [])]
      .sort((a, b) => Number(b.executable_under_host_policy) - Number(a.executable_under_host_policy)
        || Number(b.tool_installed) - Number(a.tool_installed)
        || a.operation.localeCompare(b.operation))
      .slice(0, 8);
  }, [report]);

  return (
    <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Execution host</div>
          <div className="mt-2 text-sm font-semibold text-white">Adapter, tool, and policy truth</div>
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => void load()}
          disabled={loading}
          className="h-8 w-8 rounded-full text-slate-400 hover:bg-white/8 hover:text-white"
          aria-label="Refresh execution capability"
        >
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      {error ? (
        <div className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/8 p-3 text-xs leading-5 text-amber-100">
          <ShieldAlert className="mr-1.5 inline h-3.5 w-3.5" />{error}
        </div>
      ) : null}

      {report ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            {[
              ['Adapters', summary.adapters],
              ['Installed', summary.installed],
              ['Executable', summary.executable],
              ['Previewable', summary.previewable],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-[0.9rem] border border-white/8 bg-[#081423] p-2.5">
                <div className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
                <div className="mt-1 text-lg font-semibold text-white">{value}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 space-y-2">
            {usefulRows.map((row) => (
              <div key={row.operation} className="flex items-center gap-3 rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5">
                <div className={`rounded-lg border p-1.5 ${row.executable_under_host_policy ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200' : row.tool_installed ? 'border-amber-300/20 bg-amber-300/8 text-amber-200' : 'border-white/8 bg-white/[0.03] text-slate-500'}`}>
                  {row.executable_under_host_policy ? <CheckCircle2 className="h-3.5 w-3.5" /> : row.tool_installed ? <Cpu className="h-3.5 w-3.5" /> : <CircleOff className="h-3.5 w-3.5" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-semibold text-white">{row.operation.replaceAll('_', ' ')}</div>
                  <div className="mt-0.5 truncate text-[10px] text-slate-500">
                    {row.executable_under_host_policy
                      ? 'installed and permitted'
                      : row.tool_installed
                        ? 'installed; host execution disabled'
                        : 'adapter only; tool unavailable'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-xl border border-white/8 bg-[#050c16] p-3 text-[10px] leading-5 text-slate-500">
            Root: <span className="font-mono text-slate-300">{report.execution_root}</span><br />
            OS-level network isolation is not claimed. Device access, flashing, power control, motion, and field release remain prohibited.
          </div>
        </>
      ) : loading ? (
        <div className="mt-4 flex items-center gap-2 text-xs text-slate-400"><LoaderCircle className="h-4 w-4 animate-spin" />Reading host capability</div>
      ) : null}
    </div>
  );
}
