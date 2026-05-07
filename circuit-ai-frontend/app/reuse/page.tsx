"use client";

import { useCallback, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Cable,
  CheckCircle2,
  ClipboardList,
  LoaderCircle,
  Recycle,
  ShieldAlert,
  Sparkles,
  Target,
  Wrench,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { usePageTitle } from "@/components/use-page-title";
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from "@/lib/proxy-client";

type ReuseBlock = {
  block_id: string;
  name: string;
  capabilities: string[];
  source: string;
  confidence: number;
  extraction_action?: string;
  required_tests?: string[];
  suggested_uses?: string[];
};

type BuildCandidate = {
  id: string;
  name: string;
  score: number;
  difficulty: string;
  estimated_output_value_usd: number;
  output_function: string;
  matched_capabilities: string[];
  missing_capability_groups: string[][];
  first_build_step: string;
};

type ReusePlan = {
  verdict: string;
  confidence: number;
  target?: {
    recommended_build?: string;
    output_function?: string;
  };
  reusable_blocks?: ReuseBlock[];
  capability_summary?: Record<string, number>;
  build_candidates?: BuildCandidate[];
  splice_plan?: {
    safest_entry_points?: string[];
    required_measurements?: string[];
    adapter_circuits?: Array<{ name: string; use_when: string; must_include: string[] }>;
    wiring_steps?: string[];
    mechanical_steps?: string[];
    do_not_connect_until?: string[];
  };
  integration_contract?: {
    target_build_id?: string;
    target_build?: string;
    output_function?: string;
    interfaces_to_define?: Array<{ name: string; must_define: string[] }>;
    unknowns_to_close?: string[];
    hazard_state?: string;
    first_demo?: string;
  };
  evidence_plan?: {
    capture_prompts?: string[];
    measurement_prompts?: string[];
    review_prompts?: string[];
    training_labels?: string[];
  };
  stop_conditions?: string[];
  value_tracking?: {
    proof_fields?: string[];
  };
};

type ReuseSession = {
  session_id?: string;
  title?: string;
  route?: string;
  route_label?: string;
  metrics?: {
    task_count?: number;
    capture_burden?: number;
    measurement_count_required?: number;
  };
  evidence_tasks?: Array<{ type?: string; prompt?: string; source?: string }>;
};

type ReuseCaseResponse = {
  splice_plan?: ReusePlan;
  session?: ReuseSession;
};

const starterText = [
  "USB fan with 5V USB cable",
  "small DC motor and fan blade",
  "on/off switch",
  "wire harness and connector",
  "plastic enclosure that can hold a filter",
].join("\n");

function percent(value: number | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${Math.round(value * 100)}%`;
}

function splitInventory(value: string) {
  return value
    .split(/\n|;|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function verdictVariant(verdict: string) {
  if (verdict === "reuse_ready") return "success";
  if (verdict === "ready_after_measurements") return "info";
  if (verdict === "unsafe_hold") return "error";
  return "warning";
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function ReusePage() {
  usePageTitle("Reuse | Circuit.AI");

  const [title, setTitle] = useState("USB fan salvage-to-build");
  const [goal, setGoal] = useState("Turn the useful parts into a fume extractor or bench cooling fan");
  const [parts, setParts] = useState(starterText);
  const [plan, setPlan] = useState<ReusePlan | null>(null);
  const [createdSession, setCreatedSession] = useState<ReuseSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runPlan = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setPlan(null);
    setCreatedSession(null);
    try {
      const response = await fetch("/api/proxy/salvage/splice-case", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title,
          goal,
          available_parts: splitInventory(parts),
          description: "operator has the junk device in hand and wants reuse/splicing, not original repair",
        }),
      });
      const payload = await readUiJson<ReuseCaseResponse>(response, "Could not create reuse case.");
      setPlan(payload.splice_plan ?? null);
      setCreatedSession(payload.session ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reuse planning failed.");
    } finally {
      setLoading(false);
    }
  }, [goal, parts, title]);

  const topCandidate = plan?.build_candidates?.[0];

  return (
    <div className="min-h-screen bg-[#081018] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">salvage-to-build</Badge>
                <Badge variant="default">splice plan</Badge>
                <Badge variant="default">reuse proof</Badge>
              </div>
              <h1 className="text-3xl font-semibold text-white">Reuse and splice workbench</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Treat broken electronics as reusable functions: motors, power, sensors, switches, connectors, enclosures, and control boards.
              </p>
            </div>
            <Button asChild className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
              <Link href="/cases">
                <ClipboardList className="mr-2 h-4 w-4" />
                Cases
              </Link>
            </Button>
          </div>
        </section>

        {error ? (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[390px_minmax(0,1fr)]">
          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
            <form onSubmit={runPlan} className="space-y-4">
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Item</label>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Goal</label>
                <input
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Useful parts or observations</label>
                <textarea
                  value={parts}
                  onChange={(event) => setParts(event.target.value)}
                  rows={9}
                  className="w-full resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={loading || !title.trim() || !goal.trim() || !parts.trim()}
                className="w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
              >
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Recycle className="mr-2 h-4 w-4" />}
                Create reuse case
              </Button>
            </form>
          </section>

          <section className="space-y-6">
            {plan ? (
              <>
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-3 flex flex-wrap gap-2">
                    <Badge variant={verdictVariant(plan.verdict)}>{plan.verdict.replace(/_/g, " ")}</Badge>
                    <Badge variant="default">{percent(plan.confidence)}</Badge>
                    {topCandidate ? <Badge variant="info">{topCandidate.difficulty}</Badge> : null}
                  </div>
                  <h2 className="text-2xl font-semibold text-white">{plan.target?.recommended_build ?? "Reusable electronics inventory"}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    {plan.target?.output_function ?? topCandidate?.output_function ?? "Collect more evidence before choosing the build."}
                  </p>
                  {topCandidate ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <div className="rounded-md border border-white/10 bg-black/20 p-3">
                        <div className="text-xs text-slate-500">Candidate score</div>
                        <div className="mt-1 text-lg font-semibold text-white">{percent(topCandidate.score)}</div>
                      </div>
                      <div className="rounded-md border border-white/10 bg-black/20 p-3">
                        <div className="text-xs text-slate-500">Output value</div>
                        <div className="mt-1 text-lg font-semibold text-white">${topCandidate.estimated_output_value_usd}</div>
                      </div>
                      <div className="rounded-md border border-white/10 bg-black/20 p-3">
                        <div className="text-xs text-slate-500">Blocks</div>
                        <div className="mt-1 text-lg font-semibold text-white">{plan.reusable_blocks?.length ?? 0}</div>
                      </div>
                    </div>
                  ) : null}
                  {createdSession ? (
                    <div className="mt-4 rounded-md border border-emerald-300/30 bg-emerald-300/10 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="success">case created</Badge>
                            <Badge variant="default">{createdSession.route_label ?? createdSession.route ?? "salvage"}</Badge>
                            <Badge variant="default">{createdSession.metrics?.task_count ?? createdSession.evidence_tasks?.length ?? 0} tasks</Badge>
                          </div>
                          <div className="mt-2 text-sm text-emerald-50/90">
                            {createdSession.session_id}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button asChild size="sm" className="rounded-lg bg-white text-slate-950 hover:bg-slate-100">
                            <Link href="/review">
                              <CheckCircle2 className="mr-2 h-4 w-4" />
                              Review tasks
                            </Link>
                          </Button>
                          <Button asChild size="sm" className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
                            <Link href="/cases">
                              <ClipboardList className="mr-2 h-4 w-4" />
                              Value proof
                            </Link>
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="grid gap-6 xl:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Zap className="h-4 w-4" />
                      Reusable blocks
                    </div>
                    <div className="space-y-3">
                      {(plan.reusable_blocks ?? []).slice(0, 8).map((block) => (
                        <div key={block.block_id} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="font-semibold text-white">{block.name}</div>
                            <Badge variant="default">{percent(block.confidence)}</Badge>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {block.capabilities.slice(0, 5).map((capability) => (
                              <Badge key={capability} variant="default">{capability.replace(/_/g, " ")}</Badge>
                            ))}
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-400">{block.extraction_action}</p>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Cable className="h-4 w-4" />
                      Splice gates
                    </div>
                    <div className="space-y-2">
                      {(plan.splice_plan?.required_measurements ?? []).slice(0, 9).map((item) => (
                        <div key={item} className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-50/90">
                          {item}
                        </div>
                      ))}
                    </div>
                  </section>
                </div>

                <div className="grid gap-6 xl:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Wrench className="h-4 w-4" />
                      Wiring path
                    </div>
                    <div className="space-y-2">
                      {(plan.splice_plan?.wiring_steps ?? []).map((item) => (
                        <div key={item} className="flex gap-3 rounded-md border border-white/10 bg-black/20 p-3 text-sm leading-6 text-slate-300">
                          <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-300" />
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <ShieldAlert className="h-4 w-4" />
                      Stop conditions
                    </div>
                    <div className="space-y-2">
                      {(plan.stop_conditions ?? []).slice(0, 7).map((item) => (
                        <div key={item} className="flex gap-3 rounded-md border border-amber-300/30 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50/90">
                          <AlertTriangle className="mt-1 h-4 w-4 shrink-0" />
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>

                <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    <Target className="h-4 w-4" />
                    Integration contract
                  </div>
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                    <div className="rounded-md border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-slate-500">First proof demo</div>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        {plan.integration_contract?.first_demo ?? "Demonstrate the reused block alone before connecting it to another module."}
                      </p>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                      {(plan.integration_contract?.interfaces_to_define ?? []).slice(0, 6).map((item) => (
                        <div key={item.name} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="font-semibold text-white">{item.name}</div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {item.must_define.slice(0, 4).map((field) => (
                              <Badge key={field} variant="default">{field}</Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    <Sparkles className="h-4 w-4" />
                    Other builds
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {(plan.build_candidates ?? []).slice(1, 7).map((candidate) => (
                      <div key={candidate.id} className="rounded-md border border-white/10 bg-black/20 p-3">
                        <div className="font-semibold text-white">{candidate.name}</div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          <Badge variant="default">{percent(candidate.score)}</Badge>
                          <Badge variant="default">${candidate.estimated_output_value_usd}</Badge>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-400">{candidate.first_build_step}</p>
                      </div>
                    ))}
                  </div>
                </section>
              </>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/[0.02] p-8 text-center">
                <Recycle className="mx-auto h-10 w-10 text-cyan-200" />
                <h2 className="mt-4 text-xl font-semibold text-white">Describe the junk, then generate the reuse plan.</h2>
                <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">
                  The planner will separate useful blocks, required measurements, adapter circuits, wiring steps, and proof fields.
                </p>
              </div>
            )}
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
