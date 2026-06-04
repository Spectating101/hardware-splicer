"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Cable,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  Gauge,
  Layers3,
  Lock,
  ScanLine,
  ShieldCheck,
  ThermometerSun,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { usePageTitle } from "@/components/use-page-title";
import { cn } from "@/lib/utils";

type DemoState = "reference" | "measured" | "release";
type GateStatus = "pass" | "open" | "blocked";
type BadgeTone = "success" | "warning" | "info" | "error" | "default";
type CasefileFetchStatus = "idle" | "loading" | "live" | "error";

interface CasefileSummary {
  current_authority_level?: string;
  authority_score?: number;
  production_authorized?: boolean;
  next_action_id?: string | null;
  closure_stage?: string;
  release_decision?: string;
}

interface CasefileReleaseReport {
  decision?: string;
  authorized?: boolean;
  authority_level?: string;
  authority_score?: number;
  remaining_tasks?: unknown[];
  release_artifacts_required?: string[];
}

interface CasefileLedgerStage {
  stage_id?: string;
  status?: string;
  blockers?: string[];
  next_unlock?: string;
}

interface ProductionCasefile {
  casefile_id?: string;
  summary?: CasefileSummary;
  release_report?: CasefileReleaseReport;
  authority_ledger?: {
    current_authority_level?: string;
    authority_score?: number;
    can?: Record<string, boolean>;
    stages?: CasefileLedgerStage[];
  };
}

interface ProductionCasefileResponse {
  ok?: boolean;
  error?: string;
  production_casefile?: ProductionCasefile;
  metadata?: {
    casefile_id?: string;
    current_authority_level?: string;
    authority_score?: number;
    production_authorized?: boolean;
  };
}

const demoStates: Array<{
  id: DemoState;
  label: string;
  authority: string;
  score: string;
  summary: string;
}> = [
  {
    id: "reference",
    label: "Reference only",
    authority: "visual_candidate",
    score: "0.18",
    summary: "Public pinout and visual evidence seed the measurement plan.",
  },
  {
    id: "measured",
    label: "Measured packet",
    authority: "electrical_simulation",
    score: "0.62",
    summary: "Bench capture grants measured topology and simulation authority.",
  },
  {
    id: "release",
    label: "Release ready",
    authority: "production_repair",
    score: "1.00",
    summary: "Outcome and release manifest close the scoped low-voltage claim.",
  },
];

const authorityStages: Array<{
  id: string;
  title: string;
  icon: typeof ScanLine;
  description: string;
  passAt: DemoState[];
}> = [
  {
    id: "visual",
    title: "Visual candidate",
    icon: ScanLine,
    description: "Board, connector, component, and marking candidates are usable for planning.",
    passAt: ["reference", "measured", "release"],
  },
  {
    id: "reference",
    title: "Reference topology",
    icon: Layers3,
    description: "Public schematic/pinout is attached, but it is not physical evidence.",
    passAt: ["reference", "measured", "release"],
  },
  {
    id: "measured",
    title: "Measured topology",
    icon: ClipboardCheck,
    description: "Operator packet records no-short, ground, voltage, current, and thermal evidence.",
    passAt: ["measured", "release"],
  },
  {
    id: "simulation",
    title: "Electrical simulation",
    icon: Gauge,
    description: "Measured source/load envelope passes deterministic checks.",
    passAt: ["measured", "release"],
  },
  {
    id: "bench",
    title: "Controlled bench",
    icon: Activity,
    description: "Loopback/function proof passes under current limit.",
    passAt: ["release"],
  },
  {
    id: "release",
    title: "Production release",
    icon: BadgeCheck,
    description: "Release manifest scopes what is repeatable and what remains excluded.",
    passAt: ["release"],
  },
];

const measurementRows = [
  { id: "m1", kind: "resistance", target: "power to ground no-short", icon: ShieldCheck, value: "pass" },
  { id: "m2", kind: "continuity", target: "connector ground to exposed ground", icon: Cable, value: "pass" },
  { id: "m3", kind: "voltage", target: "VCC polarity and 3.3V rail", icon: Zap, value: "3.31 V" },
  { id: "m4", kind: "current", target: "current-limited first power", icon: Gauge, value: "0.04 A" },
  { id: "m5", kind: "thermal", target: "thermal behavior after first power", icon: ThermometerSun, value: "normal" },
  { id: "m6", kind: "function", target: "UART loopback / safe serial capture", icon: Activity, value: "verified" },
];

const signalPins = [
  { pin: "1", label: "DTR", x: 135, y: 95, color: "#60a5fa" },
  { pin: "2", label: "RXI", x: 135, y: 135, color: "#34d399" },
  { pin: "3", label: "TXO", x: 135, y: 175, color: "#facc15" },
  { pin: "4", label: "VCC", x: 135, y: 215, color: "#fb7185" },
  { pin: "5", label: "CTS", x: 135, y: 255, color: "#a78bfa" },
  { pin: "6", label: "GND", x: 135, y: 295, color: "#94a3b8" },
];

const boardEvidence = {
  schema_version: "board_evidence.v1",
  components: [{ id: "u1", label: "CH340C USB serial bridge IC", kind: "integrated_circuit" }],
  markings: [{ id: "m1", marking: "CH340C" }],
  connectors: [
    { id: "usb_c", label: "USB-C connector", kind: "connector" },
    { id: "uart_header", label: "UART header", kind: "header" },
  ],
  damage: [],
  salvage_candidates: [{ id: "s1", label: "UART debug header reuse" }],
};

const benchTopologyCapture = {
  schema_version: "bench_topology_capture.v1",
  capture_id: "bench-ch340c-001",
  operator_id: "operator-1",
  recorded_at: "2026-06-02T06:00:00Z",
  instruments: [
    { instrument_id: "bench_dmm_01", instrument_type: "calibrated_dmm", calibration_status: "valid" },
    { instrument_id: "bench_supply_01", instrument_type: "current_limited_supply", calibration_status: "valid" },
    { instrument_id: "thermal_probe_01", instrument_type: "thermal_probe", calibration_status: "valid" },
  ],
  artifacts: [
    { kind: "photo", uri: "session://bench/ch340c/pinout-photo" },
    { kind: "measurement_log", uri: "session://bench/ch340c/measurement-log" },
  ],
  connectors: [
    {
      ref: "J1",
      label: "bench verified CH340C UART header",
      pins: [
        { pin: "1", net: "DTR", role: "dtr", status: "verified" },
        { pin: "2", net: "RXI", role: "rxi", logic_voltage: 3.3, status: "verified" },
        { pin: "3", net: "TXO", role: "txo", logic_voltage: 3.3, status: "verified" },
        { pin: "4", net: "VCC", role: "vcc", voltage: 3.3, status: "verified" },
        { pin: "5", net: "CTS", role: "cts", status: "verified" },
        { pin: "6", net: "GND", role: "gnd", status: "verified" },
      ],
    },
  ],
  measurements: [
    { kind: "resistance", target: "power to ground no-short", value: "pass", status: "pass", instrument_id: "bench_dmm_01" },
    { kind: "continuity", target: "connector ground to exposed ground", value: "pass", status: "pass", instrument_id: "bench_dmm_01" },
    { kind: "voltage", target: "logic high voltage", value: 3.3, unit: "V", status: "pass", instrument_id: "bench_dmm_01" },
    { kind: "current", target: "current draw under current-limited supply", value: 0.12, unit: "A", status: "pass", instrument_id: "bench_supply_01" },
    { kind: "thermal", target: "thermal behavior after first power", value: "normal", status: "pass", instrument_id: "thermal_probe_01" },
  ],
};

const controlledOutcome = {
  decision: "reused",
  selected_resource_ids_used: ["topology_j1"],
  measurements_recorded: true,
  cash_spent_usd: 0,
  value_recovered_usd: 8,
  time_spent_minutes: 18,
  deviations_from_plan: [],
  failure_or_stop_reason: "",
  output_function_verified: true,
  first_power_result: "pass",
  thermal_result: "normal",
  current_limit_used: true,
  evidence_uri: "session://bench/ch340c/outcome",
};

const productionRelease = {
  release_id: "REL-CH340C-001",
  selected_resource_ids: ["topology_j1"],
  released_by: "operator-1",
  released_at: "2026-06-02T06:30:00Z",
  scope_statement: "Release is limited to measured CH340C UART header reuse.",
  artifact_uris: ["session://bench/ch340c/release"],
  acceptance_reviewed: true,
  repeatability_count: 1,
};

function stageStatus(stage: (typeof authorityStages)[number], state: DemoState): GateStatus {
  if (stage.passAt.includes(state)) return "pass";
  return "open";
}

function statusTone(status: GateStatus): BadgeTone {
  if (status === "pass") return "success";
  if (status === "blocked") return "error";
  return "warning";
}

function measurementStatus(index: number, state: DemoState): "open" | "pass" {
  if (state === "reference") return "open";
  if (state === "measured" && index <= 4) return "pass";
  return state === "release" ? "pass" : "open";
}

function parseDemoState(value: string | null): DemoState | null {
  if (value === "reference" || value === "measured" || value === "release") return value;
  return null;
}

function buildCasefilePayload(state: DemoState) {
  const payload: Record<string, unknown> = {
    goal: "reuse this CH340C board as a USB serial debug adapter",
    device_hint: "CH340C serial adapter",
    board_evidence: boardEvidence,
    required_capabilities: ["usb_serial", "connector"],
    strategy_mode: "constrained",
    target_authority_level: "production_repair",
    constraints: { current_limit_a: 0.5 },
    use_reference_catalog: false,
  };

  if (state === "measured" || state === "release") {
    payload.bench_topology_capture = benchTopologyCapture;
  }
  if (state === "release") {
    payload.outcome_history = [controlledOutcome];
    payload.production_release = productionRelease;
  }

  return payload;
}

function formatScore(score: number | undefined, fallback: string) {
  return typeof score === "number" ? score.toFixed(2) : fallback;
}

function labelFromId(value: string | undefined) {
  return value ? value.replace(/_/g, " ") : "not available";
}

export default function AuthorityDemoPage() {
  usePageTitle("Authority Workbench | Circuit.AI");
  const [activeState, setActiveState] = useState<DemoState>("reference");
  const [casefileResponse, setCasefileResponse] = useState<ProductionCasefileResponse | null>(null);
  const [casefileStatus, setCasefileStatus] = useState<CasefileFetchStatus>("idle");
  const [casefileError, setCasefileError] = useState<string>("");

  useEffect(() => {
    const requested = parseDemoState(new URLSearchParams(window.location.search).get("state"));
    if (requested) setActiveState(requested);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function runCasefile() {
      setCasefileStatus("loading");
      setCasefileError("");
      try {
        const response = await fetch("/api/proxy/hardware/production-casefile/run", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(buildCasefilePayload(activeState)),
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = (await response.json()) as ProductionCasefileResponse;
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.error || `Production casefile request failed with ${response.status}.`);
        }
        setCasefileResponse(payload);
        setCasefileStatus("live");
      } catch (error) {
        if (controller.signal.aborted) return;
        setCasefileStatus("error");
        setCasefileResponse(null);
        setCasefileError(error instanceof Error ? error.message : String(error));
      }
    }

    runCasefile();
    return () => controller.abort();
  }, [activeState]);

  const active = useMemo(
    () => demoStates.find((state) => state.id === activeState) ?? demoStates[0],
    [activeState],
  );

  const liveCasefile = casefileResponse?.production_casefile;
  const liveSummary = liveCasefile?.summary;
  const liveAuthority = liveSummary?.current_authority_level ?? active.authority;
  const liveScore = formatScore(liveSummary?.authority_score, active.score);
  const passedStages = authorityStages.filter((stage) => stageStatus(stage, activeState) === "pass").length;
  const releaseReady = activeState === "release";
  const measuredReady = activeState !== "reference";
  const selectState = (state: DemoState) => {
    setActiveState(state);
    const url = new URL(window.location.href);
    url.searchParams.set("state", state);
    window.history.replaceState(null, "", url.toString());
  };

  return (
    <div className="min-h-screen bg-[#071018] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8">
        <section className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="rounded-md border border-white/10 bg-[#0c1622] px-4 py-3 shadow-2xl shadow-black/20">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">Circuit-AI Authority Workbench</Badge>
                  <Badge variant={releaseReady ? "success" : measuredReady ? "info" : "warning"}>
                    {liveAuthority}
                  </Badge>
                  <Badge variant={casefileStatus === "live" ? "success" : casefileStatus === "error" ? "error" : "warning"}>
                    {casefileStatus === "live" ? "live backend casefile" : casefileStatus === "error" ? "backend unavailable" : "checking backend"}
                  </Badge>
                  <Badge variant="default">SparkFun CH340C USB-C Serial Board</Badge>
                </div>
                <h1 className="mt-2 text-2xl font-semibold tracking-normal text-white sm:text-3xl">
                  Scoped board reasoning demo
                </h1>
              </div>
              <div className="grid min-w-[260px] grid-cols-3 gap-2">
                <Metric label="authority" value={liveScore} />
                <Metric label="gates" value={`${passedStages}/6`} />
                <Metric label="overclaims" value="0" tone="good" />
              </div>
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-[#0c1622] p-3">
            <div className="grid grid-cols-3 gap-2">
              {demoStates.map((state) => (
                <button
                  key={state.id}
                  type="button"
                  onClick={() => selectState(state.id)}
                  className={cn(
                    "min-h-16 rounded-md border px-3 py-2 text-left text-xs transition-colors",
                    activeState === state.id
                      ? "border-cyan-300/70 bg-cyan-300/[0.12] text-cyan-50"
                      : "border-white/10 bg-black/20 text-slate-400 hover:border-white/20 hover:text-white",
                  )}
                >
                  <span className="block font-semibold">{state.label}</span>
                  <span className="mt-1 block leading-4">{state.score}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <div className="grid min-w-0 gap-4 xl:grid-cols-[260px_minmax(0,1fr)_360px]">
          <aside className="min-w-0 rounded-md border border-white/10 bg-[#0b1520] p-3">
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <Cpu className="h-4 w-4" />
              Case packet
            </div>
            <div className="space-y-2">
              <PacketRow label="Source" value="public docs + board vision" />
              <PacketRow label="Board" value="CH340C USB serial adapter" />
              <PacketRow label="Target" value="low-voltage UART reuse" />
              <PacketRow label="Scope" value="J1 six-pin header only" />
            </div>
            <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-300/[0.08] p-3">
              <div className="text-sm font-semibold text-cyan-100">{active.label}</div>
              <p className="mt-2 text-xs leading-5 text-slate-300">{active.summary}</p>
            </div>
            <div className="mt-4 grid gap-2">
              <StatusTile label="Reference docs" state="available" tone="info" />
              <StatusTile label="Bench capture" state={measuredReady ? "attached" : "required"} tone={measuredReady ? "success" : "warning"} />
              <StatusTile label="Release manifest" state={releaseReady ? "complete" : "missing"} tone={releaseReady ? "success" : "warning"} />
            </div>
          </aside>

          <section className="grid min-h-[720px] min-w-0 gap-4 lg:grid-rows-[minmax(430px,1fr)_auto]">
            <div className="min-w-0 rounded-md border border-white/10 bg-[#101925] p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <ScanLine className="h-4 w-4" />
                  Board topology canvas
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={measuredReady ? "success" : "warning"}>
                    {measuredReady ? "measured topology" : "reference topology"}
                  </Badge>
                  <Badge variant={releaseReady ? "success" : "default"}>
                    {releaseReady ? "release packet closed" : "release gated"}
                  </Badge>
                </div>
              </div>
              <BoardCanvas state={activeState} />
            </div>

            <MeasurementPanel state={activeState} />
          </section>

          <aside className="grid min-w-0 gap-4">
            <section className="min-w-0 rounded-md border border-white/10 bg-[#0b1520] p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <ShieldCheck className="h-4 w-4" />
                  Authority ladder
                </div>
                <Badge variant={releaseReady ? "success" : "warning"}>{passedStages}/6</Badge>
              </div>
              <div className="space-y-2">
                {authorityStages.map((stage) => {
                  const Icon = stage.icon;
                  const status = stageStatus(stage, activeState);
                  return (
                    <div
                      key={stage.id}
                      className={cn(
                        "rounded-md border p-3",
                        status === "pass"
                          ? "border-emerald-300/25 bg-emerald-300/[0.08]"
                          : "border-white/10 bg-black/20",
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
                            status === "pass"
                              ? "border-emerald-300/30 bg-emerald-300/12 text-emerald-200"
                              : "border-white/10 bg-white/5 text-slate-500",
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="text-sm font-semibold text-white">{stage.title}</div>
                            <Badge variant={statusTone(status)}>{status}</Badge>
                          </div>
                          <p className="mt-1 text-xs leading-5 text-slate-400">{stage.description}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <ReleasePanel state={activeState} />
            <BackendCasefilePanel
              response={casefileResponse}
              status={casefileStatus}
              error={casefileError}
            />
          </aside>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

function BoardCanvas({ state }: { state: DemoState }) {
  const measured = state !== "reference";
  const release = state === "release";

  return (
    <div className="relative h-full min-h-[390px] overflow-hidden rounded-md border border-white/10 bg-[#e8edf0]">
      <div className="absolute inset-0 opacity-60 [background-image:linear-gradient(rgba(15,23,42,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,.08)_1px,transparent_1px)] [background-size:24px_24px]" />
      <svg className="relative h-full min-h-[390px] w-full" viewBox="0 0 780 460" role="img" aria-label="PCB authority canvas">
        <defs>
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#0f172a" floodOpacity="0.18" />
          </filter>
          <linearGradient id="board" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#12382f" />
            <stop offset="100%" stopColor="#0e2b35" />
          </linearGradient>
        </defs>

        <rect x="86" y="46" width="560" height="360" rx="18" fill="url(#board)" filter="url(#shadow)" />
        <rect x="106" y="66" width="520" height="320" rx="12" fill="none" stroke="#66e7c4" strokeOpacity="0.18" strokeWidth="2" />

        <rect x="440" y="72" width="150" height="72" rx="8" fill="#dbeafe" stroke="#1e3a8a" strokeWidth="2" />
        <text x="465" y="116" fill="#172554" fontSize="18" fontWeight="700">USB-C</text>

        <rect x="315" y="168" width="150" height="96" rx="10" fill="#111827" stroke="#93c5fd" strokeWidth="2" />
        <text x="354" y="211" fill="#e0f2fe" fontSize="20" fontWeight="700">CH340C</text>
        <text x="339" y="234" fill="#94a3b8" fontSize="13">USB to Serial</text>

        <rect x="502" y="282" width="96" height="44" rx="8" fill="#172554" stroke="#60a5fa" strokeWidth="2" />
        <text x="523" y="310" fill="#dbeafe" fontSize="14" fontWeight="700">AP2112</text>

        <rect x="100" y="78" width="70" height="248" rx="10" fill="#0f172a" stroke="#cbd5e1" strokeWidth="2" />
        <text x="103" y="355" fill="#cbd5e1" fontSize="15" fontWeight="700">J1 UART HEADER</text>

        {signalPins.map((pin, index) => (
          <g key={pin.pin}>
            <circle cx={pin.x} cy={pin.y} r="12" fill={pin.color} stroke="#f8fafc" strokeWidth="3" />
            <text x="104" y={pin.y + 5} fill="#f8fafc" fontSize="13" fontWeight="700">
              {pin.label}
            </text>
            <path
              d={`M ${pin.x + 14} ${pin.y} C ${240 + index * 8} ${pin.y} ${260 + index * 6} ${192 + index * 12} 315 ${192 + index * 6}`}
              fill="none"
              stroke={pin.color}
              strokeOpacity={measured ? "0.95" : "0.45"}
              strokeDasharray={measured ? "0" : "8 8"}
              strokeWidth={measured ? "4" : "3"}
            />
          </g>
        ))}

        <path d="M 440 110 C 420 130 398 152 390 168" fill="none" stroke="#60a5fa" strokeWidth="5" />
        <path d="M 465 218 C 504 226 520 258 548 282" fill="none" stroke="#fb7185" strokeWidth="5" />
        <path d="M 170 295 C 250 350 420 350 548 326" fill="none" stroke="#94a3b8" strokeWidth="5" />

        <g>
          <rect x="492" y="160" width="108" height="34" rx="17" fill={measured ? "#064e3b" : "#713f12"} stroke={measured ? "#34d399" : "#fbbf24"} />
          <text x="510" y="182" fill={measured ? "#d1fae5" : "#fef3c7"} fontSize="13" fontWeight="700">
            {measured ? "MEASURED" : "REFERENCE"}
          </text>
        </g>

        <g>
          <rect x="492" y="206" width="120" height="34" rx="17" fill={release ? "#064e3b" : "#172033"} stroke={release ? "#34d399" : "#475569"} />
          <text x="508" y="228" fill={release ? "#d1fae5" : "#cbd5e1"} fontSize="13" fontWeight="700">
            {release ? "RELEASED" : "BENCH GATED"}
          </text>
        </g>

        <g opacity={measured ? 1 : 0.35}>
          <circle cx="245" cy="92" r="7" fill="#34d399" />
          <circle cx="270" cy="92" r="7" fill="#34d399" />
          <circle cx="295" cy="92" r="7" fill="#34d399" />
          <text x="322" y="97" fill="#d1fae5" fontSize="13" fontWeight="700">
            DMM packet
          </text>
        </g>
      </svg>

      <div className="absolute bottom-3 left-3 right-3 grid gap-2 sm:grid-cols-3">
        <CanvasBadge label="pinout" value={measured ? "verified" : "candidate"} tone={measured ? "good" : "warn"} />
        <CanvasBadge label="first power" value={release ? "passed" : measured ? "ready for bench" : "blocked"} tone={release ? "good" : "warn"} />
        <CanvasBadge label="claim" value={release ? "scoped release" : "evidence required"} tone={release ? "good" : "warn"} />
      </div>
    </div>
  );
}

function MeasurementPanel({ state }: { state: DemoState }) {
  return (
    <section className="min-w-0 rounded-md border border-white/10 bg-[#0b1520] p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <ClipboardCheck className="h-4 w-4" />
          Measurement queue
        </div>
        <Badge variant={state === "reference" ? "warning" : "success"}>
          {state === "reference" ? "operator input required" : "packet attached"}
        </Badge>
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {measurementRows.map((row, index) => {
          const Icon = row.icon;
          const status = measurementStatus(index, state);
          return (
            <div key={row.id} className="min-h-24 rounded-md border border-white/10 bg-black/20 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon className={cn("h-4 w-4", status === "pass" ? "text-emerald-300" : "text-slate-500")} />
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{row.kind}</span>
                </div>
                <Badge variant={status === "pass" ? "success" : "warning"}>{status}</Badge>
              </div>
              <div className="mt-2 text-sm font-medium leading-5 text-white">{row.target}</div>
              <div className="mt-2 text-xs text-slate-400">{status === "pass" ? row.value : "pending operator evidence"}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ReleasePanel({ state }: { state: DemoState }) {
  const release = state === "release";
  const measured = state !== "reference";

  return (
    <section className="min-w-0 rounded-md border border-white/10 bg-[#0b1520] p-3">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        <Lock className="h-4 w-4" />
        Release packet
      </div>
      <div className="rounded-md border border-white/10 bg-black/20 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold text-white">
              {release ? "REL-SPARKFUN-CH340C-DEMO" : "release gated"}
            </div>
            <div className="mt-1 text-sm text-slate-400">
              {release ? "J1 low-voltage UART header scope" : "production claim not available"}
            </div>
          </div>
          {release ? <CheckCircle2 className="h-6 w-6 text-emerald-300" /> : <AlertTriangle className="h-6 w-6 text-amber-300" />}
        </div>
        <div className="mt-4 grid gap-2">
          <StatusTile label="Measured topology" state={measured ? "pass" : "open"} tone={measured ? "success" : "warning"} />
          <StatusTile label="Electrical simulation" state={measured ? "pass" : "open"} tone={measured ? "success" : "warning"} />
          <StatusTile label="Controlled bench" state={release ? "pass" : "open"} tone={release ? "success" : "warning"} />
          <StatusTile label="Manifest artifacts" state={release ? "attached" : "missing"} tone={release ? "success" : "warning"} />
        </div>
        <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-slate-300">
          {release
            ? "Authorized only for the recorded low-voltage UART reuse scope. Hidden nets, unmeasured connectors, and higher-risk domains remain excluded."
            : "Reference topology and model output cannot authorize power, splice, or production repair without measured evidence."}
        </div>
      </div>
    </section>
  );
}

function BackendCasefilePanel({
  response,
  status,
  error,
}: {
  response: ProductionCasefileResponse | null;
  status: CasefileFetchStatus;
  error: string;
}) {
  const casefile = response?.production_casefile;
  const summary = casefile?.summary;
  const release = casefile?.release_report;
  const stages = casefile?.authority_ledger?.stages ?? [];
  const remainingTasks = release?.remaining_tasks ?? [];
  const statusToneValue: BadgeTone = status === "live" ? "success" : status === "error" ? "error" : "warning";

  return (
    <section className="min-w-0 rounded-md border border-white/10 bg-[#0b1520] p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <Cpu className="h-4 w-4" />
          Backend casefile
        </div>
        <Badge variant={statusToneValue}>
          {status === "live" ? "live" : status === "error" ? "error" : "loading"}
        </Badge>
      </div>

      {status === "error" ? (
        <div className="rounded-md border border-red-300/20 bg-red-400/[0.08] p-3 text-xs leading-5 text-red-100">
          {error || "Could not reach the production casefile backend."}
        </div>
      ) : (
        <div className="rounded-md border border-white/10 bg-black/20 p-3">
          <div className="break-all text-sm font-semibold text-white">
            {casefile?.casefile_id ?? "waiting for casefile"}
          </div>
          <div className="mt-3 grid gap-2">
            <StatusTile
              label="Authority"
              state={labelFromId(summary?.current_authority_level)}
              tone={summary?.production_authorized ? "success" : "warning"}
            />
            <StatusTile
              label="Score"
              state={typeof summary?.authority_score === "number" ? summary.authority_score.toFixed(2) : "pending"}
              tone={summary?.production_authorized ? "success" : "warning"}
            />
            <StatusTile
              label="Decision"
              state={labelFromId(release?.decision ?? summary?.release_decision)}
              tone={release?.authorized ? "success" : "warning"}
            />
            <StatusTile
              label="Remaining tasks"
              state={status === "loading" ? "checking" : String(remainingTasks.length)}
              tone={remainingTasks.length === 0 && status === "live" ? "success" : "warning"}
            />
          </div>

          <div className="mt-3 space-y-2">
            {stages.slice(0, 6).map((stage) => {
              const passed = stage.status === "pass";
              return (
                <div key={stage.stage_id} className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
                  <span className="min-w-0 text-xs text-slate-300">{labelFromId(stage.stage_id)}</span>
                  <Badge variant={passed ? "success" : "warning"}>{stage.status ?? "open"}</Badge>
                </div>
              );
            })}
          </div>

          {remainingTasks.length > 0 && status === "live" && (
            <div className="mt-3 rounded-md border border-amber-300/20 bg-amber-300/[0.08] p-3 text-xs leading-5 text-amber-100">
              Backend still has {remainingTasks.length} release task(s) open. Production repair is not authorized in this state.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold text-white", tone === "good" && "text-emerald-300")}>{value}</div>
    </div>
  );
}

function PacketRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-sm leading-5 text-slate-200">{value}</div>
    </div>
  );
}

function StatusTile({ label, state, tone }: { label: string; state: string; tone: BadgeTone }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black/20 px-3 py-2">
      <span className="min-w-0 text-sm text-slate-300">{label}</span>
      <Badge variant={tone}>{state}</Badge>
    </div>
  );
}

function CanvasBadge({ label, value, tone }: { label: string; value: string; tone: "good" | "warn" }) {
  return (
    <div className="rounded-md border border-slate-900/10 bg-white/90 px-3 py-2 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-0.5 text-sm font-semibold", tone === "good" ? "text-emerald-700" : "text-amber-700")}>
        {value}
      </div>
    </div>
  );
}
