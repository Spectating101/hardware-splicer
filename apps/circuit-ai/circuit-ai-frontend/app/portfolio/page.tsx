"use client";

import { useCallback, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  ClipboardList,
  LoaderCircle,
  PackageCheck,
  ShieldAlert,
  Target,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { usePageTitle } from "@/components/use-page-title";
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from "@/lib/proxy-client";

type PortfolioBuild = {
  rank: number;
  build_id?: string;
  name?: string;
  readiness?: string;
  portfolio_score?: number;
  difficulty?: string;
  estimated_output_value_usd?: number;
  output_function?: string;
  source_items?: string[];
  allocated_blocks?: Array<{
    block_id?: string;
    name?: string;
    source_title?: string;
    capabilities?: string[];
    tests_before_use?: string[];
  }>;
  matched_capabilities?: string[];
  missing_capability_groups?: string[][];
  first_build_step?: string;
  first_proof_demo?: string;
};

type PortfolioPlan = {
  summary?: {
    item_count?: number;
    safety_hold_count?: number;
    build_count?: number;
    top_build?: string;
    top_build_score?: number;
    estimated_output_value_usd?: number;
    verdict?: string;
  };
  safety_holds?: Array<{ title?: string; stop_conditions?: string[]; recoverable_after_review?: string[] }>;
  aggregate_inventory?: {
    reusable_block_count?: number;
    capability_summary?: Record<string, number>;
  };
  build_portfolio?: PortfolioBuild[];
  capability_gaps?: Array<{ missing_any_of?: string[]; needed_for?: string; source_options?: string[] }>;
  work_order?: {
    first_build?: PortfolioBuild | null;
    steps?: string[];
    review_queue_seed?: string[];
  };
};

type PortfolioResponse = {
  portfolio_plan?: PortfolioPlan;
};

const starterPile = [
  "flatbed scanner: stepper motor, LED light bar, linear rail, optical sensor, 12V adapter, limit switch",
  "USB fan: 5V USB cable, small DC motor, fan blade, switch, plastic case",
  "WiFi router: 12V adapter, WiFi antenna, LED indicators, Ethernet connectors, plastic enclosure",
  "microwave oven: high voltage capacitor, magnetron, turntable motor, mains transformer",
].join("\n");

function percent(value: number | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${Math.round(value * 100)}%`;
}

function splitParts(value: string) {
  return value
    .split(/,|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parsePile(value: string) {
  return value.split(/\n/);
}

function pileItems(value: string) {
  return parsePile(value)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const separator = line.indexOf(":");
      if (separator > 0) {
        const title = line.slice(0, separator).trim();
        const parts = splitParts(line.slice(separator + 1));
        return { title, goal: "reuse useful modules", available_parts: parts };
      }
      return { title: `item ${index + 1}`, goal: "reuse useful modules", available_parts: splitParts(line) };
    });
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function PortfolioPage() {
  usePageTitle("Portfolio | Circuit.AI");

  const [title, setTitle] = useState("Weekend salvage pile");
  const [goal, setGoal] = useState("Build the most useful shop gadgets from this pile");
  const [pile, setPile] = useState(starterPile);
  const [plan, setPlan] = useState<PortfolioPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runPortfolio = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      const response = await fetch("/api/proxy/salvage/portfolio-plan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title,
          goal,
          items: pileItems(pile),
          max_builds: 5,
        }),
      });
      const payload = await readUiJson<PortfolioResponse>(response, "Could not create portfolio plan.");
      setPlan(payload.portfolio_plan ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Portfolio planning failed.");
    } finally {
      setLoading(false);
    }
  }, [goal, pile, title]);

  const topBuild = plan?.build_portfolio?.[0];
  const capabilities = Object.entries(plan?.aggregate_inventory?.capability_summary ?? {}).slice(0, 12);

  return (
    <div className="min-h-screen bg-[#081018] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">pile optimizer</Badge>
                <Badge variant="default">build portfolio</Badge>
                <Badge variant="default">safety holds</Badge>
              </div>
              <h1 className="text-3xl font-semibold text-white">Salvage portfolio planner</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Rank what to build from a pile, reserve reusable blocks, hold unsafe items, and seed the first work order.
              </p>
            </div>
            <Button asChild className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
              <Link href="/reuse">
                <Wrench className="mr-2 h-4 w-4" />
                Single item
              </Link>
            </Button>
          </div>
        </section>

        {error ? (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
            <form onSubmit={runPortfolio} className="space-y-4">
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Pile</label>
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
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Items</label>
                <textarea
                  value={pile}
                  onChange={(event) => setPile(event.target.value)}
                  rows={12}
                  className="w-full resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={loading || !title.trim() || !goal.trim() || !pile.trim()}
                className="w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
              >
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Boxes className="mr-2 h-4 w-4" />}
                Plan portfolio
              </Button>
            </form>
          </section>

          <section className="space-y-6">
            {plan ? (
              <>
                <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-3 flex flex-wrap gap-2">
                    <Badge variant="success">{plan.summary?.verdict?.replace(/_/g, " ") ?? "portfolio"}</Badge>
                    <Badge variant="default">{plan.summary?.item_count ?? 0} items</Badge>
                    <Badge variant="warning">{plan.summary?.safety_hold_count ?? 0} safety holds</Badge>
                  </div>
                  <h2 className="text-2xl font-semibold text-white">{plan.summary?.top_build ?? "No build selected"}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    {topBuild?.output_function ?? "Collect more useful low-voltage modules before building."}
                  </p>
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <div className="rounded-md border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-slate-500">Top score</div>
                      <div className="mt-1 text-lg font-semibold text-white">{percent(plan.summary?.top_build_score)}</div>
                    </div>
                    <div className="rounded-md border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-slate-500">Output value</div>
                      <div className="mt-1 text-lg font-semibold text-white">${plan.summary?.estimated_output_value_usd ?? 0}</div>
                    </div>
                    <div className="rounded-md border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-slate-500">Reusable blocks</div>
                      <div className="mt-1 text-lg font-semibold text-white">{plan.aggregate_inventory?.reusable_block_count ?? 0}</div>
                    </div>
                  </div>
                </section>

                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.65fr)]">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Target className="h-4 w-4" />
                      Ranked builds
                    </div>
                    <div className="space-y-3">
                      {(plan.build_portfolio ?? []).map((build) => (
                        <div key={`${build.rank}-${build.build_id}`} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="font-semibold text-white">{build.rank}. {build.name}</div>
                            <div className="flex flex-wrap gap-1">
                              <Badge variant="info">{percent(build.portfolio_score)}</Badge>
                              <Badge variant="default">${build.estimated_output_value_usd ?? 0}</Badge>
                              <Badge variant="default">{build.difficulty}</Badge>
                            </div>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-400">{build.first_proof_demo ?? build.first_build_step}</p>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {(build.source_items ?? []).slice(0, 5).map((item) => (
                              <Badge key={item} variant="default">{item}</Badge>
                            ))}
                          </div>
                          {(build.allocated_blocks ?? []).length ? (
                            <div className="mt-3 border-t border-white/10 pt-3">
                              <div className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                                Reserved blocks
                              </div>
                              <ul className="divide-y divide-white/10 text-xs">
                                {(build.allocated_blocks ?? []).slice(0, 6).map((block) => (
                                  <li key={`${block.block_id}-${block.name}`} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
                                    <span className="font-medium text-slate-100">{block.name}</span>
                                    <span className="text-slate-500">
                                      {block.source_title}
                                      {block.capabilities?.length ? ` · ${block.capabilities.slice(0, 2).map((cap) => cap.replace(/_/g, " ")).join(", ")}` : ""}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <ShieldAlert className="h-4 w-4" />
                      Safety holds
                    </div>
                    <div className="space-y-3">
                      {(plan.safety_holds ?? []).length ? (plan.safety_holds ?? []).map((hold) => (
                        <div key={hold.title} className="rounded-md border border-amber-300/30 bg-amber-300/10 p-3">
                          <div className="font-semibold text-amber-50">{hold.title}</div>
                          <div className="mt-2 space-y-1">
                            {(hold.stop_conditions ?? []).slice(0, 3).map((item) => (
                              <div key={item} className="flex gap-2 text-xs leading-5 text-amber-50/90">
                                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                <span>{item}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )) : (
                        <div className="rounded-md border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-50/90">
                          No hard safety holds detected.
                        </div>
                      )}
                    </div>
                  </section>
                </div>

                <div className="grid gap-6 xl:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <PackageCheck className="h-4 w-4" />
                      Work order
                    </div>
                    <div className="space-y-2">
                      {(plan.work_order?.steps ?? []).map((step) => (
                        <div key={step} className="flex gap-3 rounded-md border border-white/10 bg-black/20 p-3 text-sm leading-6 text-slate-300">
                          <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-300" />
                          <span>{step}</span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <ClipboardList className="h-4 w-4" />
                      Capabilities
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {capabilities.map(([name, count]) => (
                        <Badge key={name} variant="default">{name.replace(/_/g, " ")} x{count}</Badge>
                      ))}
                    </div>
                    {(plan.capability_gaps ?? []).length ? (
                      <div className="mt-5 space-y-2">
                        {(plan.capability_gaps ?? []).slice(0, 4).map((gap) => (
                          <div key={`${gap.needed_for}-${gap.missing_any_of?.join("-")}`} className="rounded-md border border-white/10 bg-black/20 p-3">
                            <div className="text-sm font-semibold text-white">{gap.needed_for}</div>
                            <p className="mt-1 text-xs leading-5 text-slate-400">
                              Missing: {(gap.missing_any_of ?? []).join(" or ")}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </section>
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/[0.02] p-8 text-center">
                <Boxes className="mx-auto h-10 w-10 text-cyan-200" />
                <h2 className="mt-4 text-xl font-semibold text-white">Paste a pile, then rank the builds.</h2>
                <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">
                  The planner will separate hazards, combine reusable low-voltage blocks, and produce a first work order.
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
