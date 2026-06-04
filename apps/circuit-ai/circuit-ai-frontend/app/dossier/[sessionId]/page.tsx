'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Cpu,
  GitBranch,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Target,
  Wrench,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type Claim = {
  claim_id?: string;
  claim?: string;
  score?: number;
  certainty?: string;
  grounding_status?: string;
  supporting_evidence?: string[];
  missing_evidence?: string[];
};

type Dossier = {
  session_id?: string;
  title?: string;
  route?: string;
  status?: string;
  executive_summary?: string;
  identity?: {
    device_hint?: string;
    board_role?: string;
    board_confidence?: number;
    repair_family?: string;
    repair_confidence?: number;
  };
  aoi?: {
    available?: boolean;
    disposition?: string;
    release_authorized?: boolean;
    certainty_score?: number;
    certainty_level?: string;
    blockers?: string[];
    gates?: Array<{ gate_id?: string; status?: string; score?: number }>;
  };
  components?: {
    total?: number;
    counts?: Record<string, number>;
    review_required?: boolean;
    top_detections?: Array<{ label?: string; confidence?: number; part_number?: string; ocr_text?: string }>;
  };
  repair_reuse?: {
    top_fault?: string;
    repair_safety?: string;
    reuse_verdict?: string;
    reuse_target?: string;
    reusable_blocks?: unknown[];
  };
  evidence?: {
    graph_summary?: {
      source_count?: number;
      claim_count?: number;
      grounded_claim_count?: number;
      weak_claim_count?: number;
    };
    grounded_claims?: Claim[];
    weak_claims?: Claim[];
    next_grounding_actions?: string[];
  };
  known?: string[];
  uncertain?: string[];
  next_actions?: string[];
  open_tasks?: Array<{ task_id?: string; type?: string; prompt?: string; priority?: number; status?: string }>;
  outcomes?: Array<{ outcome_id?: string; decision?: string; aoi_actual_status?: string; value_recovered_usd?: number; time_saved_minutes?: number }>;
  claim_boundary?: string;
};

type DossierResponse = { dossier?: Dossier };

function percent(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function statusVariant(status: string | undefined) {
  if (status === 'release_ready') return 'success';
  if (status === 'rework' || status === 'hold_for_capture' || status === 'hold_for_reference' || status === 'hold_for_calibration') return 'warning';
  if (status === 'needs_evidence') return 'info';
  return 'default';
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function DossierPage() {
  usePageTitle('Board Dossier | Circuit.AI');
  const params = useParams<{ sessionId: string }>();
  const sessionId = params?.sessionId ?? '';
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(sessionId)}/dossier`, { cache: 'no-store' });
      const payload = await readUiJson<DossierResponse>(response, 'Could not load board dossier.');
      setDossier(payload.dossier ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Dossier failed.');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const componentCounts = useMemo(
    () => Object.entries(dossier?.components?.counts ?? {}).sort((a, b) => b[1] - a[1]),
    [dossier?.components?.counts],
  );

  return (
    <div className="min-h-screen bg-[#090f18] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="outline" className="rounded-lg border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
            <Link href="/review">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Review
            </Link>
          </Button>
          <Button onClick={() => void load()} disabled={loading} className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
            {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>
        </div>

        {error && (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        )}

        {loading ? (
          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-8 text-center text-sm text-slate-400">
            <LoaderCircle className="mx-auto mb-3 h-5 w-5 animate-spin text-cyan-200" />
            Loading board dossier...
          </section>
        ) : dossier ? (
          <>
            <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">board dossier</Badge>
                <Badge variant={statusVariant(dossier.status)}>{dossier.status?.replace(/_/g, ' ') ?? 'review'}</Badge>
                {dossier.route ? <Badge variant="default">{dossier.route}</Badge> : null}
              </div>
              <h1 className="text-3xl font-semibold text-white">{dossier.title ?? 'Board dossier'}</h1>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">{dossier.executive_summary}</p>
              <p className="mt-3 max-w-4xl text-xs leading-5 text-slate-500">{dossier.claim_boundary}</p>
            </section>

            <section className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <Metric label="Sources" value={dossier.evidence?.graph_summary?.source_count ?? 0} icon={<GitBranch className="h-4 w-4 text-cyan-200" />} />
              <Metric label="Claims" value={dossier.evidence?.graph_summary?.claim_count ?? 0} icon={<ClipboardList className="h-4 w-4 text-cyan-200" />} />
              <Metric label="Grounded" value={dossier.evidence?.graph_summary?.grounded_claim_count ?? 0} icon={<CheckCircle2 className="h-4 w-4 text-emerald-200" />} />
              <Metric label="Weak" value={dossier.evidence?.graph_summary?.weak_claim_count ?? 0} icon={<AlertTriangle className="h-4 w-4 text-amber-200" />} />
              <Metric label="AOI" value={dossier.aoi?.available ? dossier.aoi.disposition?.replace(/_/g, ' ') ?? 'ready' : 'N/A'} icon={<ShieldCheck className="h-4 w-4 text-cyan-200" />} />
            </section>

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
              <section className="space-y-4">
                <Panel title="What We Know" icon={<CheckCircle2 className="h-4 w-4" />}>
                  <ItemList items={dossier.known ?? []} empty="No grounded facts yet." />
                </Panel>
                <Panel title="What Needs Evidence" icon={<AlertTriangle className="h-4 w-4" />}>
                  <ItemList items={dossier.uncertain ?? []} empty="No weak claims flagged." muted />
                </Panel>
                <Panel title="Next Actions" icon={<Target className="h-4 w-4" />}>
                  <ItemList items={dossier.next_actions ?? []} empty="No next actions generated." />
                </Panel>
                <Panel title="Grounded Claims" icon={<GitBranch className="h-4 w-4" />}>
                  <ClaimList claims={dossier.evidence?.grounded_claims ?? []} empty="No strongly grounded claims yet." />
                </Panel>
                <Panel title="Weak Claims" icon={<AlertTriangle className="h-4 w-4" />}>
                  <ClaimList claims={dossier.evidence?.weak_claims ?? []} empty="No weak claims flagged." />
                </Panel>
              </section>

              <aside className="space-y-4">
                <Panel title="Identity" icon={<Cpu className="h-4 w-4" />}>
                  <KeyValues rows={[
                    ['Device', dossier.identity?.device_hint ?? 'unknown'],
                    ['Board role', dossier.identity?.board_role?.replace(/_/g, ' ') ?? 'unknown'],
                    ['Board confidence', percent(dossier.identity?.board_confidence)],
                    ['Repair family', dossier.identity?.repair_family ?? 'unknown'],
                  ]} />
                </Panel>
                <Panel title="Components" icon={<Cpu className="h-4 w-4" />}>
                  <KeyValues rows={[
                    ['Total', String(dossier.components?.total ?? 0)],
                    ['Review required', dossier.components?.review_required ? 'yes' : 'no'],
                  ]} />
                  <div className="mt-3 space-y-1.5">
                    {componentCounts.slice(0, 8).map(([label, count]) => (
                      <div key={label} className="flex items-center justify-between rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm">
                        <span className="text-slate-300">{label}</span>
                        <span className="text-white">{count}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
                <Panel title="Production AOI" icon={<ShieldCheck className="h-4 w-4" />}>
                  <KeyValues rows={[
                    ['Disposition', dossier.aoi?.disposition?.replace(/_/g, ' ') ?? 'not available'],
                    ['Release', dossier.aoi?.release_authorized ? 'authorized' : 'blocked'],
                    ['Certainty', percent(dossier.aoi?.certainty_score)],
                    ['Level', dossier.aoi?.certainty_level ?? 'unknown'],
                  ]} />
                  <ItemList items={(dossier.aoi?.blockers ?? []).slice(0, 4)} empty="No AOI blockers." muted />
                </Panel>
                <Panel title="Repair / Reuse" icon={<Wrench className="h-4 w-4" />}>
                  <KeyValues rows={[
                    ['Top fault', dossier.repair_reuse?.top_fault ?? 'unknown'],
                    ['Safety', dossier.repair_reuse?.repair_safety ?? 'unknown'],
                    ['Reuse verdict', dossier.repair_reuse?.reuse_verdict ?? 'unknown'],
                    ['Reuse target', dossier.repair_reuse?.reuse_target ?? 'unknown'],
                  ]} />
                </Panel>
                <Panel title="Open Tasks" icon={<ClipboardList className="h-4 w-4" />}>
                  <ItemList items={(dossier.open_tasks ?? []).slice(0, 6).map((task) => task.prompt ?? 'Open task')} empty="No open tasks." muted />
                </Panel>
              </aside>
            </div>
          </>
        ) : (
          <section className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] p-8 text-center text-sm text-slate-400">
            No dossier found.
          </section>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
        {icon}
      </div>
      <div className="mt-3 text-2xl font-semibold text-white">{String(value)}</div>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
        {icon}
        {title}
      </div>
      {children}
    </section>
  );
}

function ItemList({ items, empty, muted = false }: { items: string[]; empty: string; muted?: boolean }) {
  if (!items.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <p key={item} className={`rounded-md border border-white/10 bg-black/20 p-3 text-sm leading-6 ${muted ? 'text-slate-400' : 'text-slate-200'}`}>
          {item}
        </p>
      ))}
    </div>
  );
}

function ClaimList({ claims, empty }: { claims: Claim[]; empty: string }) {
  if (!claims.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="space-y-2">
      {claims.map((claim) => (
        <div key={claim.claim_id ?? claim.claim} className="rounded-md border border-white/10 bg-black/20 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm leading-6 text-slate-200">{claim.claim}</p>
            <Badge variant={claim.grounding_status === 'grounded' ? 'success' : 'warning'}>{claim.certainty ?? 'weak'}</Badge>
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {percent(claim.score)} · {(claim.supporting_evidence ?? []).length} support · {(claim.missing_evidence ?? []).length} missing
          </div>
        </div>
      ))}
    </div>
  );
}

function KeyValues({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div className="space-y-1.5">
      {rows.map(([key, value]) => (
        <div key={key} className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm">
          <span className="text-slate-500">{key}</span>
          <span className="text-right text-slate-200">{value}</span>
        </div>
      ))}
    </div>
  );
}
