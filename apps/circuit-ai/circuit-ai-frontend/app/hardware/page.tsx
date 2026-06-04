"use client";

import { useCallback, useMemo, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  LoaderCircle,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  Wrench,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { usePageTitle } from "@/components/use-page-title";
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from "@/lib/proxy-client";

type HardwarePlanResponse = {
  hardware_plan?: HardwarePlan;
  mode?: string;
  integrated_plan?: IntegratedPlan;
};

type HardwarePlan = {
  integrated_plan?: IntegratedPlan;
  resource_strategy?: {
    selected_resources?: HardwareResource[];
    coverage?: {
      coverage_score?: number;
      missing_capabilities?: string[];
    };
  };
};

type HardwareResource = {
  resource_id?: string;
  name?: string;
  resource_kind?: string;
  capabilities?: string[];
  status?: string;
};

type IntegratedPlan = {
  status?: string;
  reason?: string;
  selected_resource_count?: number;
  selected_resource_ids?: string[];
  next_actions?: string[];
  measurement_evidence?: {
    measurement_count?: number;
    closed_gate_count?: number;
    failed_gate_count?: number;
    open_measurement_gate_count?: number;
  };
  assurance?: {
    level?: string;
    score?: number;
    can_build_now?: boolean;
    can_power_or_splice?: boolean;
    open_gate_count?: number;
    failed_gate_count?: number;
    blockers?: string[];
  };
  completion_contract?: {
    state?: string;
    plan_done?: boolean;
    workflow_done?: boolean;
    outcome_recorded?: boolean;
    outcome_contract_complete?: boolean;
    outcome_decision?: string | null;
    required_before_done?: string[];
  };
  evidence_gates?: EvidenceGate[];
  execution_package?: {
    current_stage?: string;
    completion_state?: string;
    stages?: ExecutionStage[];
    outcome_contract?: {
      recorded?: boolean;
      latest_decision?: string | null;
      required_fields?: string[];
      required_fields_present?: Record<string, boolean>;
    };
  };
};

type EvidenceGate = {
  gate_id?: string;
  type?: string;
  status?: string;
  source?: string;
  prompt?: string;
  closure?: {
    measurement_id?: string;
    measurement_type?: string;
    target?: string;
    value?: unknown;
    unit?: string;
  };
};

type ExecutionStage = {
  stage_id?: string;
  status?: string;
  objective?: string;
  actions?: string[];
  blocked_by?: string[];
};

const starterResources = JSON.stringify(
  [
    {
      resource_id: "known_ch340",
      name: "known CH340 adapter",
      resource_kind: "owned",
      capabilities: ["usb_serial", "connector"],
      confidence: 0.92,
      evidence_status: "verified",
    },
  ],
  null,
  2,
);

const proofMeasurements = [
  {
    type: "resistance",
    target: "power to ground no-short",
    value: "pass",
    notes: "unpowered resistance between power and ground is no-short",
  },
  {
    type: "continuity",
    target: "connector ground to exposed ground",
    value: "pass",
    notes: "connector ground continuity ok",
  },
  {
    type: "voltage",
    target: "UART logic high voltage",
    value: 3.31,
    unit: "V",
    notes: "UART TX/RX idle high at 3.3V",
  },
  {
    type: "continuity",
    target: "shared ground continuity",
    value: "pass",
    notes: "shared ground continuity pass",
  },
  {
    type: "logic_level",
    target: "serial UART idle state",
    value: "pass",
    notes: "serial idle high and stable before connecting target board",
  },
];

const terminalOutcome = {
  decision: "built",
  selected_resource_ids_used: ["known_ch340"],
  measurements_recorded: true,
  cash_spent_usd: 0,
  value_recovered_usd: 9,
  time_spent_minutes: 20,
  deviations_from_plan: [],
  failure_or_stop_reason: "",
  output_function_verified: true,
};

function splitCapabilities(value: string) {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function percent(value: number | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${Math.round(value * 100)}%`;
}

function gateTone(status: string | undefined) {
  if (status === "closed" || status === "pass") return "success";
  if (status === "failed" || status === "blocked") return "error";
  return "warning";
}

function stateTone(state: string | undefined) {
  if (state === "workflow_complete") return "success";
  if (state === "blocked") return "error";
  if (state === "plan_complete_awaiting_outcome") return "info";
  return "warning";
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function HardwarePage() {
  usePageTitle("Hardware Plan | Circuit.AI");

  const [goal, setGoal] = useState("build a UART debug adapter from a known CH340 module");
  const [requiredCapabilities, setRequiredCapabilities] = useState("usb_serial, connector");
  const [resources, setResources] = useState(starterResources);
  const [attachMeasurements, setAttachMeasurements] = useState(true);
  const [attachOutcome, setAttachOutcome] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<HardwarePlan | null>(null);

  const integrated = plan?.integrated_plan;
  const selectedResources = useMemo(() => plan?.resource_strategy?.selected_resources ?? [], [plan]);

  const runPlan = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setPlan(null);

    try {
      const parsedResources = JSON.parse(resources) as unknown;
      if (!Array.isArray(parsedResources)) {
        throw new Error("Resources must be a JSON array.");
      }

      const response = await fetch("/api/proxy/hardware/plan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          goal,
          strategy_mode: "hybrid",
          required_capabilities: splitCapabilities(requiredCapabilities),
          available_resources: parsedResources,
          measurements: attachMeasurements ? proofMeasurements : [],
          outcome_history: attachOutcome ? [terminalOutcome] : [],
          repair_authority: {
            status: attachMeasurements ? "authoritative_low_risk" : "measurement_backed",
            score: attachMeasurements ? 0.91 : 0.72,
            required_measurements: attachMeasurements ? [] : ["Confirm UART idle high voltage before connecting target board."],
            blocked_decisions: attachMeasurements ? [] : ["production repair release"],
          },
          use_reference_catalog: false,
        }),
      });
      const payload = await readUiJson<HardwarePlanResponse>(response, "Could not run hardware plan.");
      setPlan(payload.hardware_plan ?? { integrated_plan: payload.integrated_plan });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Hardware planning failed.");
    } finally {
      setLoading(false);
    }
  }, [attachMeasurements, attachOutcome, goal, requiredCapabilities, resources]);

  return (
    <div className="min-h-screen bg-[#081018] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">hardware plan</Badge>
                <Badge variant="default">evidence gated</Badge>
                <Badge variant="default">outcome closed</Badge>
              </div>
              <h1 className="text-3xl font-semibold text-white">Hardware execution workbench</h1>
            </div>
            {integrated?.completion_contract ? (
              <Badge variant={stateTone(integrated.completion_contract.state)} className="px-3 py-1">
                {integrated.completion_contract.state?.replace(/_/g, " ") ?? "unknown"}
              </Badge>
            ) : null}
          </div>
        </section>

        {error ? (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
            <form onSubmit={runPlan} className="space-y-4">
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Goal</label>
                <input
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan-300/60"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Required capabilities</label>
                <input
                  value={requiredCapabilities}
                  onChange={(event) => setRequiredCapabilities(event.target.value)}
                  className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan-300/60"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Resources JSON</label>
                <textarea
                  value={resources}
                  onChange={(event) => setResources(event.target.value)}
                  rows={11}
                  className="w-full resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs leading-5 text-white outline-none focus:border-cyan-300/60"
                  required
                />
              </div>
              <div className="grid gap-2">
                <label className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200">
                  <span className="flex items-center gap-2">
                    <SlidersHorizontal className="h-4 w-4 text-cyan-200" />
                    Attach passing measurements
                  </span>
                  <input
                    type="checkbox"
                    checked={attachMeasurements}
                    onChange={(event) => setAttachMeasurements(event.target.checked)}
                    className="h-4 w-4 accent-cyan-300"
                  />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200">
                  <span className="flex items-center gap-2">
                    <ClipboardCheck className="h-4 w-4 text-emerald-200" />
                    Attach terminal outcome
                  </span>
                  <input
                    type="checkbox"
                    checked={attachOutcome}
                    onChange={(event) => setAttachOutcome(event.target.checked)}
                    className="h-4 w-4 accent-cyan-300"
                  />
                </label>
              </div>
              <Button
                type="submit"
                disabled={loading || !goal.trim() || !requiredCapabilities.trim() || !resources.trim()}
                className="w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
              >
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                Run hardware plan
              </Button>
            </form>
          </section>

          <section className="space-y-6">
            {integrated ? (
              <>
                <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                  <div className="mb-4 flex flex-wrap gap-2">
                    <Badge variant={stateTone(integrated.completion_contract?.state)}>{integrated.completion_contract?.state?.replace(/_/g, " ")}</Badge>
                    <Badge variant={integrated.assurance?.can_power_or_splice ? "success" : "warning"}>
                      power {integrated.assurance?.can_power_or_splice ? "allowed" : "blocked"}
                    </Badge>
                    <Badge variant="default">{percent(integrated.assurance?.score)}</Badge>
                  </div>
                  <div className="grid gap-3 md:grid-cols-4">
                    <Metric label="Plan done" value={integrated.completion_contract?.plan_done ? "yes" : "no"} />
                    <Metric label="Workflow done" value={integrated.completion_contract?.workflow_done ? "yes" : "no"} />
                    <Metric label="Open gates" value={String(integrated.assurance?.open_gate_count ?? 0)} />
                    <Metric label="Outcome" value={integrated.completion_contract?.outcome_decision ?? "pending"} />
                  </div>
                  {integrated.reason ? <p className="mt-4 text-sm leading-6 text-slate-300">{integrated.reason}</p> : null}
                </section>

                <div className="grid gap-6 xl:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <ShieldCheck className="h-4 w-4" />
                      Evidence gates
                    </div>
                    <div className="space-y-2">
                      {(integrated.evidence_gates ?? []).map((gate) => (
                        <div key={`${gate.type}-${gate.prompt}`} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Badge variant={gateTone(gate.status)}>{gate.status ?? "open"}</Badge>
                            <span className="text-xs text-slate-500">{gate.source}</span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-200">{gate.prompt}</p>
                          {gate.closure ? (
                            <p className="mt-2 text-xs text-slate-400">
                              {gate.closure.measurement_type}: {gate.closure.target} = {String(gate.closure.value ?? "")} {gate.closure.unit ?? ""}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Zap className="h-4 w-4" />
                      Execution stages
                    </div>
                    <div className="space-y-2">
                      {(integrated.execution_package?.stages ?? []).map((stage) => (
                        <div key={stage.stage_id} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="font-semibold text-white">{stage.stage_id?.replace(/_/g, " ")}</div>
                            <Badge variant={stage.status === "complete" || stage.status === "ready" || stage.status === "not_required" ? "success" : stage.status === "blocked" ? "error" : "warning"}>
                              {stage.status?.replace(/_/g, " ")}
                            </Badge>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-400">{stage.objective}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>

                <div className="grid gap-6 xl:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <Wrench className="h-4 w-4" />
                      Selected resources
                    </div>
                    <div className="space-y-2">
                      {selectedResources.map((resource) => (
                        <div key={resource.resource_id ?? resource.name} className="rounded-md border border-white/10 bg-black/20 p-3">
                          <div className="font-semibold text-white">{resource.name}</div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {(resource.capabilities ?? []).map((capability) => (
                              <Badge key={capability} variant="default">{capability.replace(/_/g, " ")}</Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
                    <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <AlertTriangle className="h-4 w-4" />
                      Required before done
                    </div>
                    <div className="space-y-2">
                      {(integrated.completion_contract?.required_before_done ?? []).length ? (
                        integrated.completion_contract?.required_before_done?.map((item) => (
                          <div key={item} className="rounded-md border border-amber-300/30 bg-amber-300/10 p-3 text-sm leading-6 text-amber-50/90">
                            {item}
                          </div>
                        ))
                      ) : (
                        <div className="flex items-center gap-2 rounded-md border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-50">
                          <CheckCircle2 className="h-4 w-4" />
                          Complete
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              </>
            ) : (
              <section className="rounded-lg border border-white/10 bg-white/[0.02] p-8 text-center">
                <Wrench className="mx-auto h-10 w-10 text-cyan-200" />
                <h2 className="mt-4 text-xl font-semibold text-white">No hardware plan loaded</h2>
              </section>
            )}
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}
