'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Braces, LoaderCircle, PlayCircle, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  type EngineeringPlan,
  type NextAction,
  type PreparedActionResponse,
  type PreparedEngineeringAction,
} from '@/lib/engineering-status';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

export function EngineeringActionPanel({
  plan,
  action,
}: {
  plan: EngineeringPlan;
  action: NextAction | null;
}) {
  const [prepared, setPrepared] = useState<PreparedEngineeringAction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPrepared(null);
    setError(null);
  }, [action?.action_id, plan]);

  const payloadPreview = useMemo(() => {
    if (!prepared) return '';
    const rendered = JSON.stringify(prepared.payload, null, 2);
    return rendered.length > 3600 ? `${rendered.slice(0, 3600)}\n… truncated in UI` : rendered;
  }, [prepared]);

  async function prepare() {
    if (!action) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/proxy/engineering/actions/prepare', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ plan, action_id: action.action_id }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<PreparedActionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not prepare this action.'));
      }
      const result = (payload as PreparedActionResponse | null)?.prepared_action;
      if (!result) throw new Error('The action endpoint returned no prepared packet.');
      setPrepared(result);
    } catch (value: unknown) {
      setPrepared(null);
      setError(value instanceof Error ? value.message : 'Action preparation failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-[1.5rem] border border-cyan-300/18 bg-[linear-gradient(180deg,rgba(34,211,238,0.10),rgba(8,20,35,0.96))] p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Next action</div>
      <div className="mt-2 text-sm font-semibold text-white">{action?.title || 'Compile project status'}</div>

      {action ? (
        <>
          <div className="mt-3 text-sm leading-6 text-slate-200">{action.instruction}</div>
          <div className="mt-4 rounded-xl border border-cyan-300/15 bg-black/15 p-3 font-mono text-[10px] leading-5 text-cyan-200">
            {action.method || 'POST'} {action.route}
          </div>
          {action.required_inputs?.length ? (
            <div className="mt-4 text-xs leading-5 text-slate-300">
              <span className="font-semibold text-white">Needs:</span> {action.required_inputs.slice(0, 5).join(' • ')}
            </div>
          ) : null}
          <Button
            type="button"
            onClick={() => void prepare()}
            disabled={loading}
            className="mt-4 w-full rounded-xl bg-cyan-300 text-slate-950 hover:bg-cyan-200"
          >
            {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            Prepare action packet
          </Button>
        </>
      ) : (
        <div className="mt-3 text-sm leading-6 text-slate-400">Load or compile a guided plan to receive an API-backed next action.</div>
      )}

      {error ? (
        <div className="mt-4 rounded-xl border border-rose-400/20 bg-rose-500/10 p-3 text-xs leading-5 text-rose-100">
          <AlertTriangle className="mr-1.5 inline h-3.5 w-3.5" />{error}
        </div>
      ) : null}

      {prepared ? (
        <div className="mt-4 space-y-3 border-t border-white/8 pt-4">
          <div className="flex items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 text-xs font-semibold text-white"><Braces className="h-4 w-4 text-cyan-200" />Prepared packet</div>
            <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${prepared.status === 'ready' ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200' : 'border-amber-300/20 bg-amber-300/8 text-amber-200'}`}>{prepared.status}</span>
          </div>
          {prepared.blockers.length ? (
            <div className="rounded-xl border border-rose-400/20 bg-rose-500/8 p-3 text-xs leading-5 text-rose-100">{prepared.blockers.join(' • ')}</div>
          ) : null}
          {prepared.warnings.length ? (
            <div className="rounded-xl border border-amber-300/20 bg-amber-300/8 p-3 text-xs leading-5 text-amber-100">{prepared.warnings.join(' • ')}</div>
          ) : null}
          <pre className="max-h-72 overflow-auto rounded-xl border border-white/8 bg-[#050c16] p-3 font-mono text-[10px] leading-5 text-slate-300">{payloadPreview}</pre>
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5" />Preparation only • no automatic physical execution
          </div>
        </div>
      ) : null}
    </div>
  );
}
