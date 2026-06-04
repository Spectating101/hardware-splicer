"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Cable,
  Camera,
  CheckCircle2,
  CircuitBoard,
  ClipboardCheck,
  Cpu,
  DatabaseZap,
  Gauge,
  GitBranch,
  Layers3,
  Loader2,
  Lock,
  Play,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  ThermometerSun,
  UploadCloud,
  Zap,
} from "lucide-react";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { usePageTitle } from "@/components/use-page-title";
import { cn } from "@/lib/utils";

type DemoState = "reference" | "measured" | "release";
type FetchStatus = "idle" | "loading" | "live" | "error";
type Tone = "good" | "warn" | "info" | "neutral" | "bad";

interface CasefileSummary {
  current_authority_level?: string;
  authority_score?: number;
  production_authorized?: boolean;
  next_action_id?: string | null;
  closure_stage?: string;
  release_decision?: string;
}

interface CasefileStage {
  stage_id?: string;
  status?: string;
  blockers?: string[];
  next_unlock?: string;
}

interface CasefileReleaseReport {
  decision?: string;
  authorized?: boolean;
  authority_level?: string;
  authority_score?: number;
  remaining_tasks?: unknown[];
  authority_stages?: CasefileStage[];
  release_artifacts_required?: string[];
}

interface ProductionCasefile {
  casefile_id?: string;
  summary?: CasefileSummary;
  release_report?: CasefileReleaseReport;
  authority_ledger?: {
    current_authority_level?: string;
    authority_score?: number;
    stages?: CasefileStage[];
    can?: Record<string, boolean>;
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
    live_model_advisory?: boolean;
  };
}

interface JarvisStatus {
  jarvis?: {
    visionProvider?: string;
    visionProviderReady?: boolean;
    selectedTextProvider?: string;
    textProviderReady?: boolean;
    paidVisionBudget?: {
      policy?: {
        monthlyUsdLimit?: number;
        enabled?: boolean;
      };
      remainingMonthlyUsd?: number;
    };
  };
  metadata?: {
    qwen_native_vision?: {
      disabled?: boolean;
      raw_multimodal_pixels_sent_to_qwen?: boolean;
    };
  };
}

interface RuntimeHealth {
  ok?: boolean;
  status?: string;
}

interface BoardEvidenceItem {
  id?: string;
  label?: string;
  kind?: string;
  confidence?: number;
  source_refs?: unknown[];
}

interface FusedBoardEvidence {
  components?: BoardEvidenceItem[];
  connectors?: BoardEvidenceItem[];
  markings?: BoardEvidenceItem[];
  damage?: BoardEvidenceItem[];
  salvage_candidates?: BoardEvidenceItem[];
}

interface FusionResponse {
  ok?: boolean;
  error?: string;
  multiview_board_reconstruction?: {
    available?: boolean;
    input_observation_count?: number;
    usable_observation_count?: number;
    capture_coverage?: {
      score?: number;
      required_complete?: boolean;
      lanes?: Record<string, unknown>;
    };
    canonical_board_map?: {
      layout_confidence?: number;
      mapped_item_count?: number;
      unmapped_item_count?: number;
    };
    reconstruction_summary?: {
      summary?: string;
      board_role?: string;
      confidence?: number;
    };
    next_capture_requests?: Array<{
      request_id?: string;
      prompt?: string;
      reason?: string;
    }>;
    policy?: {
      fusion_is_candidate_only?: boolean;
      measurements_still_required_for_power_or_splice?: boolean;
    };
  };
  board_evidence?: FusedBoardEvidence;
  vision_evidence_bridge?: {
    available?: boolean;
    resource_candidates?: unknown[];
  };
  metadata?: {
    fixed_view_slots_required?: boolean;
  };
}

const evidenceStates: Array<{
  id: DemoState;
  title: string;
  short: string;
  expectedAuthority: string;
  expectedScore: string;
  result: string;
  description: string;
}> = [
  {
    id: "reference",
    title: "Reference only",
    short: "visual candidate",
    expectedAuthority: "visual_candidate",
    expectedScore: "0.18",
    result: "Blocks power and splice claims",
    description: "Board markings, public pinout hints, and connector candidates are enough to plan measurements, not enough to authorize repair.",
  },
  {
    id: "measured",
    title: "Measured packet",
    short: "topology proven",
    expectedAuthority: "electrical_simulation",
    expectedScore: "0.62",
    result: "Unlocks deterministic checks",
    description: "Trusted DMM/supply/thermal readings convert candidate pins into a scoped topology and source/load envelope.",
  },
  {
    id: "release",
    title: "Release ready",
    short: "production repair",
    expectedAuthority: "production_repair",
    expectedScore: "1.00",
    result: "Authorizes scoped reuse",
    description: "Bench outcome, release manifest, artifact URIs, and measurement provenance close the low-voltage UART reuse claim.",
  },
];

const authorityStages: Array<{
  id: string;
  label: string;
  icon: typeof ScanLine;
  passAt: DemoState[];
}> = [
  { id: "visual_candidate", label: "Visual candidate", icon: ScanLine, passAt: ["reference", "measured", "release"] },
  { id: "reference_topology", label: "Reference topology", icon: Layers3, passAt: ["reference", "measured", "release"] },
  { id: "measured_topology", label: "Measured topology", icon: ClipboardCheck, passAt: ["measured", "release"] },
  { id: "electrical_simulation", label: "Simulation envelope", icon: Gauge, passAt: ["measured", "release"] },
  { id: "controlled_bench", label: "Controlled bench", icon: Activity, passAt: ["release"] },
  { id: "production_repair", label: "Production release", icon: BadgeCheck, passAt: ["release"] },
];

const measurementRows = [
  { id: "resistance", label: "no-short resistance", value: "pass", icon: ShieldCheck },
  { id: "continuity", label: "ground continuity", value: "pass", icon: Cable },
  { id: "voltage", label: "logic rail voltage", value: "3.30 V", icon: Zap },
  { id: "current", label: "current-limited draw", value: "0.12 A", icon: Gauge },
  { id: "thermal", label: "first-power thermal", value: "normal", icon: ThermometerSun },
  { id: "function", label: "UART loopback", value: "verified", icon: Activity },
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

const demoPhotoObservations = [
  {
    photo_id: "wide_board_angle",
    label: "wide angled board observation",
    view_hint: "whole-board view with USB-C connector, bridge IC, and UART header visible",
    provider: "manual_demo_fixture",
    parse_diagnostics: { json_valid: true, truncated: false },
    board_evidence: {
      schema_version: "board_evidence.v1",
      components: [
        {
          id: "u1",
          label: "CH340C USB serial bridge IC",
          kind: "integrated_circuit",
          confidence: 0.86,
          bbox: [0.39, 0.32, 0.54, 0.52],
          missing_evidence: ["confirm VCC/GND and UART header continuity"],
        },
      ],
      connectors: [
        { id: "usb_c", label: "USB-C receptacle", kind: "connector", confidence: 0.84, bbox: [0.11, 0.38, 0.2, 0.61] },
        { id: "uart_header", label: "six-pin UART header", kind: "header", confidence: 0.78, bbox: [0.7, 0.27, 0.79, 0.69] },
      ],
      markings: [],
      salvage_candidates: [{ id: "uart_reuse", label: "UART debug adapter reuse", kind: "usb_serial", confidence: 0.76 }],
    },
  },
  {
    photo_id: "ic_marking_closeup",
    label: "IC marking closeup",
    view_hint: "closeup of the central bridge IC marking",
    provider: "manual_demo_fixture",
    parse_diagnostics: { json_valid: true, truncated: false },
    board_evidence: {
      schema_version: "board_evidence.v1",
      components: [
        {
          id: "u1_close",
          label: "CH340C USB serial bridge IC",
          kind: "integrated_circuit",
          confidence: 0.93,
          bbox: [0.22, 0.18, 0.72, 0.68],
        },
      ],
      markings: [{ id: "mk_ch340c", label: "CH340C marking", marking: "CH340C", kind: "ic_marking", confidence: 0.94 }],
      connectors: [],
      salvage_candidates: [],
    },
  },
  {
    photo_id: "header_closeup",
    label: "UART header closeup",
    view_hint: "closeup of header pads and silkscreen labels",
    provider: "manual_demo_fixture",
    parse_diagnostics: { json_valid: true, truncated: false },
    board_evidence: {
      schema_version: "board_evidence.v1",
      components: [],
      connectors: [
        {
          id: "uart_header_close",
          label: "TXD RXD GND VCC header",
          kind: "header",
          confidence: 0.91,
          visible_text: "TXD RXD GND VCC",
          bbox: [0.28, 0.2, 0.76, 0.74],
          missing_evidence: ["measure pin order and idle voltage before connecting target board"],
        },
      ],
      test_points: [{ id: "tp_gnd", label: "exposed ground test point", kind: "test_point", confidence: 0.72 }],
      markings: [{ id: "mk_uart", label: "TXD RXD GND VCC silkscreen", marking: "TXD RXD GND VCC", kind: "pin_label", confidence: 0.9 }],
      salvage_candidates: [{ id: "serial_header_reuse", label: "bench UART header reuse", kind: "connector_reuse", confidence: 0.88 }],
    },
  },
];

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

function buildFusionPayload() {
  return {
    goal: "reuse this CH340C board as a USB serial debug adapter",
    device_hint: "CH340C serial adapter",
    strategy_mode: "constrained",
    required_capabilities: ["usb_serial", "connector"],
    use_reference_catalog: false,
    board_photo_set: {
      photo_observations: demoPhotoObservations,
    },
  };
}

function buildCasefilePayload(state: DemoState) {
  const payload: Record<string, unknown> = {
    goal: "reuse this CH340C board as a USB serial debug adapter",
    device_hint: "CH340C serial adapter",
    board_evidence: boardEvidence,
    board_photo_set: {
      photo_observations: demoPhotoObservations,
    },
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

function parseState(value: string | null): DemoState | null {
  if (value === "reference" || value === "measured" || value === "release") return value;
  return null;
}

function scoreLabel(value: number | undefined, fallback: string) {
  return typeof value === "number" ? value.toFixed(2) : fallback;
}

function labelFromId(value: string | undefined | null) {
  return value ? value.replace(/_/g, " ") : "not available";
}

function toneClasses(tone: Tone) {
  switch (tone) {
    case "good":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "warn":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "bad":
      return "border-rose-200 bg-rose-50 text-rose-800";
    case "info":
      return "border-cyan-200 bg-cyan-50 text-cyan-800";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

function MiniBadge({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: Tone; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium", toneClasses(tone), className)}>
      {children}
    </span>
  );
}

function ShellPanel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn("rounded-lg border border-slate-200 bg-white shadow-sm", className)}>{children}</section>;
}

function PanelTitle({ icon: Icon, title, action }: { icon: typeof ScanLine; title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
      <div className="flex min-w-0 items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        <Icon className="h-4 w-4" />
        <span className="truncate">{title}</span>
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className="min-w-0 rounded-md border border-slate-200 bg-white px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-1 truncate text-lg font-semibold", tone === "good" ? "text-emerald-700" : tone === "warn" ? "text-amber-700" : "text-slate-950")}>
        {value}
      </div>
    </div>
  );
}

function activeStageCount(state: DemoState) {
  return authorityStages.filter((stage) => stage.passAt.includes(state)).length;
}

function evidenceMeasurementCount(state: DemoState) {
  if (state === "reference") return 0;
  if (state === "measured") return 5;
  return 6;
}

function BoardCanvas({ state }: { state: DemoState }) {
  const measured = state !== "reference";
  const released = state === "release";

  return (
    <div className="relative min-h-[430px] overflow-hidden rounded-md border border-slate-200 bg-[#f7faf9]">
      <div
        className="absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "linear-gradient(#dfe9e7 1px, transparent 1px), linear-gradient(90deg, #dfe9e7 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />
      <svg viewBox="0 0 720 420" className="relative h-full min-h-[430px] w-full" role="img" aria-label="Measured CH340C board topology">
        <defs>
          <filter id="boardShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="12" stdDeviation="12" floodColor="#0f172a" floodOpacity="0.16" />
          </filter>
          <linearGradient id="boardFill" x1="0" x2="1">
            <stop stopColor="#0f766e" />
            <stop offset="1" stopColor="#115e59" />
          </linearGradient>
        </defs>
        <rect x="138" y="58" width="438" height="300" rx="18" fill="url(#boardFill)" filter="url(#boardShadow)" />
        <rect x="160" y="82" width="394" height="252" rx="10" fill="none" stroke="#5eead4" strokeOpacity="0.28" strokeWidth="2" />

        <rect x="191" y="138" width="128" height="96" rx="8" fill="#172033" stroke="#94a3b8" strokeOpacity="0.6" />
        <text x="255" y="186" textAnchor="middle" fill="#e2e8f0" fontSize="18" fontWeight="700">
          CH340C
        </text>
        <text x="255" y="208" textAnchor="middle" fill="#94a3b8" fontSize="11">
          USB serial bridge
        </text>

        <rect x="108" y="162" width="58" height="92" rx="8" fill="#dbeafe" stroke="#60a5fa" strokeWidth="2" />
        <text x="137" y="212" textAnchor="middle" fill="#1e3a8a" fontSize="12" fontWeight="700">
          USB-C
        </text>

        <rect x="474" y="118" width="50" height="182" rx="7" fill="#e2e8f0" stroke="#64748b" strokeWidth="2" />
        {["DTR", "RXI", "TXO", "VCC", "CTS", "GND"].map((label, index) => {
          const y = 142 + index * 26;
          const pinPass = measured || index >= 1;
          return (
            <g key={label}>
              <circle cx="496" cy={y} r="6" fill={pinPass ? "#34d399" : "#cbd5e1"} stroke="#0f172a" strokeOpacity="0.25" />
              <text x="531" y={y + 4} fill="#0f172a" fontSize="12" fontWeight="700">
                {label}
              </text>
            </g>
          );
        })}

        <path d="M166 191 C182 176, 186 170, 191 165" fill="none" stroke={measured ? "#34d399" : "#f59e0b"} strokeWidth="4" strokeLinecap="round" />
        <path d="M166 218 C183 225, 184 228, 191 224" fill="none" stroke={measured ? "#34d399" : "#f59e0b"} strokeWidth="4" strokeLinecap="round" />
        <path d="M319 171 C382 130, 432 130, 474 142" fill="none" stroke={measured ? "#34d399" : "#94a3b8"} strokeWidth="4" strokeLinecap="round" strokeDasharray={measured ? "0" : "8 8"} />
        <path d="M319 190 C386 170, 423 168, 474 168" fill="none" stroke={measured ? "#34d399" : "#94a3b8"} strokeWidth="4" strokeLinecap="round" strokeDasharray={measured ? "0" : "8 8"} />
        <path d="M319 209 C386 220, 426 218, 474 194" fill="none" stroke={measured ? "#34d399" : "#94a3b8"} strokeWidth="4" strokeLinecap="round" strokeDasharray={measured ? "0" : "8 8"} />
        <path d="M319 229 C379 267, 433 260, 474 246" fill="none" stroke={measured ? "#34d399" : "#94a3b8"} strokeWidth="4" strokeLinecap="round" strokeDasharray={measured ? "0" : "8 8"} />

        <g transform="translate(174 268)">
          <rect width="168" height="38" rx="8" fill={released ? "#064e3b" : measured ? "#134e4a" : "#78350f"} opacity="0.95" />
          <text x="84" y="24" textAnchor="middle" fill="#ecfeff" fontSize="13" fontWeight="700">
            {released ? "BENCH PASS + RELEASE" : measured ? "MEASURED TOPOLOGY" : "CANDIDATE ONLY"}
          </text>
        </g>

        <g transform="translate(78 320)">
          <rect width="166" height="44" rx="8" fill="#ffffff" stroke="#cbd5e1" />
          <text x="14" y="18" fill="#475569" fontSize="11" fontWeight="700">
            Authority boundary
          </text>
          <text x="14" y="34" fill={released ? "#047857" : "#b45309"} fontSize="12" fontWeight="700">
            {released ? "Scoped reuse authorized" : "No production claim yet"}
          </text>
        </g>

        <g transform="translate(448 320)">
          <rect width="184" height="44" rx="8" fill="#ffffff" stroke="#cbd5e1" />
          <text x="14" y="18" fill="#475569" fontSize="11" fontWeight="700">
            Safety gate
          </text>
          <text x="14" y="34" fill={measured ? "#047857" : "#b45309"} fontSize="12" fontWeight="700">
            {measured ? "No-short and current limit" : "Measure before power"}
          </text>
        </g>
      </svg>
    </div>
  );
}

function EvidenceRail({ activeState, onSelect }: { activeState: DemoState; onSelect: (state: DemoState) => void }) {
  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle icon={UploadCloud} title="Evidence packets" />
      <div className="p-3">
        <div className="grid gap-2">
          {evidenceStates.map((state) => {
            const selected = activeState === state.id;
            const tone: Tone = state.id === "release" ? "good" : state.id === "measured" ? "info" : "warn";
            return (
              <button
                key={state.id}
                type="button"
                onClick={() => onSelect(state.id)}
                className={cn(
                  "rounded-md border p-3 text-left transition-colors",
                  selected
                    ? "border-slate-900 bg-slate-950 text-white shadow-sm"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold">{state.title}</div>
                    <div className={cn("mt-1 text-xs", selected ? "text-slate-300" : "text-slate-500")}>{state.short}</div>
                  </div>
                  <MiniBadge tone={selected ? "neutral" : tone}>{state.expectedScore}</MiniBadge>
                </div>
                <p className={cn("mt-3 text-xs leading-5", selected ? "text-slate-300" : "text-slate-500")}>{state.result}</p>
              </button>
            );
          })}
        </div>
      </div>
    </ShellPanel>
  );
}

function FusionPanel({
  response,
  status,
  error,
  onRun,
}: {
  response: FusionResponse | null;
  status: FetchStatus;
  error: string;
  onRun: () => void;
}) {
  const reconstruction = response?.multiview_board_reconstruction;
  const evidence = response?.board_evidence;
  const usable = reconstruction?.usable_observation_count ?? 0;
  const total = reconstruction?.input_observation_count ?? demoPhotoObservations.length;
  const componentCount = evidence?.components?.length ?? 0;
  const connectorCount = evidence?.connectors?.length ?? 0;
  const markingCount = evidence?.markings?.length ?? 0;
  const coverage = reconstruction?.capture_coverage?.score;
  const available = Boolean(reconstruction?.available);
  const waiting = status === "idle" || status === "loading";

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle
        icon={Camera}
        title="Photo evidence fusion"
        action={
          <Button type="button" size="sm" variant="outline" onClick={onRun} disabled={status === "loading"} className="h-8 gap-1.5 px-2.5">
            {status === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Fuse
          </Button>
        }
      />
      <div className="space-y-3 p-3">
        <div className={cn("rounded-md border p-3", available ? "border-cyan-200 bg-cyan-50" : waiting ? "border-slate-200 bg-slate-50" : "border-amber-200 bg-amber-50")}>
          <div className="flex items-start gap-3">
            <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-white", available ? "border-cyan-200 text-cyan-700" : "border-amber-200 text-amber-700")}>
              {status === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-950">
                {available ? "Candidate board map fused" : waiting ? "Fusion waiting on backend" : "Fusion needs review"}
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                {available
                  ? "Multiple observations feed one candidate board_evidence.v1 dossier."
                  : error || "The same contract can consume Qwen photo outputs later without changing the authority gate."}
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <StatusCell label="observations" value={`${usable}/${total}`} tone={usable ? "info" : "warn"} />
          <StatusCell label="coverage" value={typeof coverage === "number" ? coverage.toFixed(2) : "pending"} tone={typeof coverage === "number" && coverage >= 0.6 ? "info" : "warn"} />
          <StatusCell label="components" value={String(componentCount)} tone={componentCount ? "good" : "warn"} />
          <StatusCell label="connectors" value={String(connectorCount)} tone={connectorCount ? "good" : "warn"} />
        </div>

        <div className="grid gap-2">
          {demoPhotoObservations.map((observation) => (
            <div key={observation.photo_id} className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-sm font-medium text-slate-900">{observation.label}</div>
                <MiniBadge tone="neutral">{observation.provider}</MiniBadge>
              </div>
              <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{observation.view_hint}</div>
            </div>
          ))}
        </div>

        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Candidate counts</div>
          <div className="mt-2 text-sm text-slate-700">
            {componentCount} component{componentCount === 1 ? "" : "s"}, {connectorCount} connector{connectorCount === 1 ? "" : "s"}, {markingCount} marking{markingCount === 1 ? "" : "s"}.
          </div>
          <div className="mt-1 text-xs leading-5 text-slate-500">
            Fusion is still candidate-only; measurements remain required for power, splice, or production release.
          </div>
        </div>
      </div>
    </ShellPanel>
  );
}

function MeasurementPanel({ state }: { state: DemoState }) {
  const completed = evidenceMeasurementCount(state);

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle icon={DatabaseZap} title="Measurement closure" action={<MiniBadge tone={completed === 6 ? "good" : completed ? "info" : "warn"}>{completed}/6 closed</MiniBadge>} />
      <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-3">
        {measurementRows.map((row, index) => {
          const Icon = row.icon;
          const pass = index < completed;
          return (
            <div key={row.id} className={cn("rounded-md border p-3", pass ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50")}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <Icon className={cn("h-4 w-4 shrink-0", pass ? "text-emerald-700" : "text-slate-400")} />
                  <span className="truncate text-sm font-medium text-slate-900">{row.label}</span>
                </div>
                {pass ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-700" /> : <Lock className="h-4 w-4 shrink-0 text-slate-400" />}
              </div>
              <div className={cn("mt-2 text-xs", pass ? "text-emerald-800" : "text-slate-500")}>{pass ? row.value : "required"}</div>
            </div>
          );
        })}
      </div>
    </ShellPanel>
  );
}

function AuthorityLadder({ state, backendStages }: { state: DemoState; backendStages: CasefileStage[] }) {
  const stageMap = new Map(backendStages.map((stage) => [stage.stage_id, stage]));

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle icon={ShieldCheck} title="Authority ladder" action={<MiniBadge tone={state === "release" ? "good" : "warn"}>{activeStageCount(state)}/6</MiniBadge>} />
      <div className="space-y-2 p-3">
        {authorityStages.map((stage) => {
          const Icon = stage.icon;
          const backend = stageMap.get(stage.id);
          const pass = backend ? backend.status === "pass" : stage.passAt.includes(state);
          const blockerCount = backend?.blockers?.length ?? (pass ? 0 : 1);
          return (
            <div key={stage.id} className={cn("rounded-md border p-3", pass ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white")}>
              <div className="flex items-start gap-3">
                <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-md border", pass ? "border-emerald-200 bg-white text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-500")}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-sm font-semibold text-slate-950">{stage.label}</div>
                    <MiniBadge tone={pass ? "good" : "warn"}>{pass ? "pass" : "open"}</MiniBadge>
                  </div>
                  <div className={cn("mt-1 text-xs", blockerCount ? "text-amber-700" : "text-slate-500")}>
                    {blockerCount ? `${blockerCount} blocker${blockerCount === 1 ? "" : "s"}` : "gate closed by evidence"}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </ShellPanel>
  );
}

function CasefilePanel({
  response,
  status,
  error,
  activeState,
  onRun,
}: {
  response: ProductionCasefileResponse | null;
  status: FetchStatus;
  error: string;
  activeState: DemoState;
  onRun: () => void;
}) {
  const active = evidenceStates.find((state) => state.id === activeState) ?? evidenceStates[0];
  const summary = response?.production_casefile?.summary;
  const releaseReport = response?.production_casefile?.release_report;
  const authorized = Boolean(summary?.production_authorized);
  const authority = summary?.current_authority_level ?? active.expectedAuthority;
  const score = scoreLabel(summary?.authority_score, active.expectedScore);
  const decision = releaseReport?.decision ?? summary?.release_decision ?? "waiting for backend";
  const remainingTasks = releaseReport?.remaining_tasks?.length ?? 0;
  const waiting = status === "idle" || status === "loading";

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle
        icon={ClipboardCheck}
        title="Live production casefile"
        action={
          <Button type="button" size="sm" variant="outline" onClick={onRun} disabled={status === "loading"} className="h-8 gap-1.5 px-2.5">
            {status === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Rerun
          </Button>
        }
      />
      <div className="p-4">
        <div className={cn("rounded-md border p-4", authorized ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50")}>
          <div className="flex items-start gap-3">
            <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-md border", authorized ? "border-emerald-200 bg-white text-emerald-700" : "border-amber-200 bg-white text-amber-700")}>
              {authorized ? <BadgeCheck className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-950">{authorized ? "Production repair authorized" : waiting ? "Running casefile engine" : "Authority still gated"}</div>
              <div className="mt-1 text-xs leading-5 text-slate-600">{waiting ? "waiting for backend result" : labelFromId(decision)}</div>
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2">
          <Metric label="score" value={score} tone={authorized ? "good" : "warn"} />
          <Metric label="level" value={labelFromId(authority)} />
          <Metric label="tasks" value={String(remainingTasks)} tone={remainingTasks === 0 ? "good" : "warn"} />
        </div>

        {status === "error" && (
          <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>
        )}

        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
            <dt className="text-slate-500">Backend route</dt>
            <dd className="truncate font-medium text-slate-900">/hardware/production-casefile/run</dd>
          </div>
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
            <dt className="text-slate-500">Live model advisory</dt>
            <dd className="font-medium text-slate-900">{String(Boolean(response?.metadata?.live_model_advisory))}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500">Casefile ID</dt>
            <dd className="truncate font-medium text-slate-900">{response?.metadata?.casefile_id ?? "pending"}</dd>
          </div>
        </dl>
      </div>
    </ShellPanel>
  );
}

function RuntimeStrip({ jarvis, healthStatus }: { jarvis: JarvisStatus | null; healthStatus: FetchStatus }) {
  const qwenDisabled = Boolean(jarvis?.metadata?.qwen_native_vision?.disabled);
  const rawQwenPixels = Boolean(jarvis?.metadata?.qwen_native_vision?.raw_multimodal_pixels_sent_to_qwen);
  const monthlyLimit = jarvis?.jarvis?.paidVisionBudget?.policy?.monthlyUsdLimit ?? 0;
  const visionProvider = jarvis?.jarvis?.visionProvider ?? "unknown";

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle icon={GitBranch} title="Runtime integration" />
      <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCell label="Backend" value={healthStatus === "live" ? "online" : healthStatus === "loading" ? "checking" : "offline"} tone={healthStatus === "live" ? "good" : healthStatus === "error" ? "bad" : "warn"} />
        <StatusCell label="Vision route" value={visionProvider} tone={visionProvider === "qwen" ? "warn" : "info"} />
        <StatusCell label="Qwen spend" value={qwenDisabled && !rawQwenPixels ? "hard stopped" : "check console"} tone={qwenDisabled && !rawQwenPixels ? "good" : "warn"} />
        <StatusCell label="Vision budget" value={`$${monthlyLimit}`} tone={monthlyLimit === 0 ? "good" : "warn"} />
      </div>
    </ShellPanel>
  );
}

function StatusCell({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className={cn("rounded-md border px-3 py-2", toneClasses(tone))}>
      <div className="text-[11px] font-semibold uppercase tracking-wider opacity-70">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold">{value}</div>
    </div>
  );
}

function SummaryRail({ activeState, response }: { activeState: DemoState; response: ProductionCasefileResponse | null }) {
  const active = evidenceStates.find((state) => state.id === activeState) ?? evidenceStates[0];
  const summary = response?.production_casefile?.summary;

  return (
    <ShellPanel className="overflow-hidden">
      <PanelTitle icon={Cpu} title="Claim boundary" />
      <div className="space-y-3 p-4">
        <div>
          <div className="text-sm font-semibold text-slate-950">{active.title}</div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{active.description}</p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Engine says</div>
          <div className="mt-2 text-sm font-semibold text-slate-950">
            {!summary
              ? "Waiting for live casefile result."
              : summary.production_authorized
                ? "This scoped reuse can be released."
                : "Collect more physical evidence before release."}
          </div>
          <div className="mt-1 text-xs leading-5 text-slate-500">
            {summary?.next_action_id ? `Next action: ${labelFromId(summary.next_action_id)}` : "No remaining action for the selected scoped release."}
          </div>
        </div>
      </div>
    </ShellPanel>
  );
}

export default function ShowcasePage() {
  usePageTitle("Live Showcase | Circuit.AI");
  const [activeState, setActiveState] = useState<DemoState>("release");
  const [casefileResponse, setCasefileResponse] = useState<ProductionCasefileResponse | null>(null);
  const [casefileStatus, setCasefileStatus] = useState<FetchStatus>("idle");
  const [casefileError, setCasefileError] = useState("");
  const [fusionResponse, setFusionResponse] = useState<FusionResponse | null>(null);
  const [fusionStatus, setFusionStatus] = useState<FetchStatus>("idle");
  const [fusionError, setFusionError] = useState("");
  const [jarvisStatus, setJarvisStatus] = useState<JarvisStatus | null>(null);
  const [healthStatus, setHealthStatus] = useState<FetchStatus>("idle");

  useEffect(() => {
    const requested = parseState(new URLSearchParams(window.location.search).get("state"));
    if (requested) setActiveState(requested);
  }, []);

  const runCasefile = useCallback(async (state: DemoState, signal?: AbortSignal) => {
    setCasefileStatus("loading");
    setCasefileError("");
    try {
      const response = await fetch("/api/proxy/hardware/production-casefile/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(buildCasefilePayload(state)),
        cache: "no-store",
        signal,
      });
      const payload = (await response.json()) as ProductionCasefileResponse;
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Casefile request failed with ${response.status}.`);
      }
      setCasefileResponse(payload);
      setCasefileStatus("live");
    } catch (error) {
      if (signal?.aborted) return;
      setCasefileResponse(null);
      setCasefileStatus("error");
      setCasefileError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  const runFusion = useCallback(async (signal?: AbortSignal) => {
    setFusionStatus("loading");
    setFusionError("");
    try {
      const response = await fetch("/api/proxy/vision/board-evidence/fuse?include_hardware_plan=true", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(buildFusionPayload()),
        cache: "no-store",
        signal,
      });
      const payload = (await response.json()) as FusionResponse;
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Fusion request failed with ${response.status}.`);
      }
      setFusionResponse(payload);
      setFusionStatus("live");
    } catch (error) {
      if (signal?.aborted) return;
      setFusionResponse(null);
      setFusionStatus("error");
      setFusionError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    runCasefile(activeState, controller.signal);
    return () => controller.abort();
  }, [activeState, runCasefile]);

  useEffect(() => {
    const controller = new AbortController();
    runFusion(controller.signal);
    return () => controller.abort();
  }, [runFusion]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadRuntime() {
      try {
        setHealthStatus("loading");
        const [jarvisResponse, healthResponse] = await Promise.all([
          fetch("/api/jarvis/status", { cache: "no-store", signal: controller.signal }),
          fetch("/api/proxy/vision/health", { cache: "no-store", signal: controller.signal }),
        ]);
        if (jarvisResponse.ok) setJarvisStatus((await jarvisResponse.json()) as JarvisStatus);
        if (!healthResponse.ok) {
          setHealthStatus("error");
          return;
        }
        const healthPayload = (await healthResponse.json()) as RuntimeHealth;
        setHealthStatus(healthPayload.ok === false || healthPayload.status === "unhealthy" ? "error" : "live");
      } catch {
        if (!controller.signal.aborted) setHealthStatus("error");
      }
    }

    loadRuntime();
    return () => controller.abort();
  }, []);

  const active = useMemo(() => evidenceStates.find((state) => state.id === activeState) ?? evidenceStates[0], [activeState]);
  const summary = casefileResponse?.production_casefile?.summary;
  const liveAuthority = summary?.current_authority_level ?? active.expectedAuthority;
  const liveScore = scoreLabel(summary?.authority_score, active.expectedScore);
  const fusedObservationCount = fusionResponse?.multiview_board_reconstruction?.usable_observation_count ?? 0;
  const backendStages =
    casefileResponse?.production_casefile?.authority_ledger?.stages ??
    casefileResponse?.production_casefile?.release_report?.authority_stages ??
    [];

  const selectState = (state: DemoState) => {
    setActiveState(state);
    const url = new URL(window.location.href);
    url.searchParams.set("state", state);
    window.history.replaceState(null, "", url.toString());
  };

  return (
    <div className="min-h-screen bg-[#f5f7f8] text-slate-950">
      <SiteHeader />
      <main className="mx-auto max-w-[1560px] px-4 py-5 sm:px-6 lg:px-8">
        <section className="mb-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_480px]">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <MiniBadge tone="info">Live backend demo</MiniBadge>
                  <MiniBadge tone={summary?.production_authorized ? "good" : "warn"}>{labelFromId(liveAuthority)}</MiniBadge>
                  <MiniBadge tone={casefileStatus === "live" ? "good" : casefileStatus === "error" ? "bad" : "warn"}>
                    {casefileStatus === "live"
                      ? "casefile connected"
                      : casefileStatus === "error"
                        ? "casefile error"
                        : "casefile running"}
                  </MiniBadge>
                  <MiniBadge tone={fusionStatus === "live" ? "good" : fusionStatus === "error" ? "bad" : "info"}>
                    {fusionStatus === "live" ? "photo fusion connected" : fusionStatus === "error" ? "fusion review" : "fusion running"}
                  </MiniBadge>
                </div>
                <h1 className="mt-3 text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
                  Circuit.AI repair authority showcase
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  A focused demo surface for judges and reviewers: choose the evidence level, run the real production casefile engine, and watch the board claim move from visual candidate to scoped production repair.
                </p>
              </div>
              <Button type="button" onClick={() => runCasefile(activeState)} disabled={casefileStatus === "loading"} className="gap-2 bg-slate-950 text-white hover:bg-slate-800">
                {casefileStatus === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run live casefile
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="authority" value={liveScore} tone={summary?.production_authorized ? "good" : "warn"} />
            <Metric label="closed gates" value={`${activeStageCount(activeState)}/6`} />
            <Metric label="photo obs" value={`${fusedObservationCount}/${demoPhotoObservations.length}`} tone={fusedObservationCount ? "good" : "warn"} />
            <Metric label="token spend" value="$0" tone="good" />
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_390px]">
          <div className="grid content-start gap-4">
            <EvidenceRail activeState={activeState} onSelect={selectState} />
            <FusionPanel
              response={fusionResponse}
              status={fusionStatus}
              error={fusionError}
              onRun={() => runFusion()}
            />
            <SummaryRail activeState={activeState} response={casefileResponse} />
          </div>

          <div className="grid min-w-0 content-start gap-4">
            <ShellPanel className="overflow-hidden">
              <PanelTitle
                icon={CircuitBoard}
                title="Board reconstruction"
                action={
                  <div className="flex items-center gap-2">
                    <MiniBadge tone={activeState === "reference" ? "warn" : "good"}>{activeState === "reference" ? "measurement required" : "measured topology"}</MiniBadge>
                    <MiniBadge tone={activeState === "release" ? "good" : "warn"}>{activeState === "release" ? "release closed" : "release gated"}</MiniBadge>
                  </div>
                }
              />
              <div className="p-3">
                <BoardCanvas state={activeState} />
              </div>
            </ShellPanel>
            <MeasurementPanel state={activeState} />
            <RuntimeStrip jarvis={jarvisStatus} healthStatus={healthStatus} />
          </div>

          <div className="grid content-start gap-4">
            <CasefilePanel
              response={casefileResponse}
              status={casefileStatus}
              error={casefileError}
              activeState={activeState}
              onRun={() => runCasefile(activeState)}
            />
            <AuthorityLadder state={activeState} backendStages={backendStages} />
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
