'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useCallback, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Camera,
  CheckCircle2,
  CircuitBoard,
  ClipboardList,
  Database,
  DollarSign,
  FileText,
  LoaderCircle,
  PackageCheck,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Wrench,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;

type AnalyzeResponse = {
  ok?: boolean;
  error?: string;
  results?: {
    detections?: Array<{
      class_name?: string;
      confidence?: number;
      part_number?: string | null;
      ocr_text?: string;
    }>;
    detection_summary?: {
      total_components?: number;
      components_by_type?: Record<string, number>;
      average_confidence?: number;
      detection_quality?: string;
      review_required?: boolean;
    };
    board_understanding?: {
      board_identity?: {
        primary_type?: string;
        confidence?: number;
        description?: string;
      };
      functional_blocks?: Array<{
        block_type?: string;
        confidence?: number;
        function?: string;
      }>;
    };
    machine_connection_map?: {
      connector_count?: number;
    };
    aoi_inspection?: {
      readiness?: string;
      score?: number;
      defect_candidate_count?: number;
      blockers?: string[];
    };
    salvage_opportunities?: {
      asset_summary?: {
        capabilities?: Record<string, number>;
      };
    };
    certainty_ledger?: {
      overall?: {
        score?: number;
        level?: string;
        summary?: string;
      };
      missing_evidence?: string[];
      next_actions?: string[];
      training_queue?: {
        should_capture?: boolean;
      };
    };
  };
  metadata?: {
    backend?: string;
    detection_quality?: string;
  };
  summary?: {
    summary_text?: string;
  };
};

type CoverageRecord = {
  item_id: string;
  label: string;
  examples: string[];
  coverage: number;
  relevance: number;
  strategic_score: number;
  coverage_level: string;
  why: string[];
  gaps: string[];
};

type CoverageQuery = {
  matched: boolean;
  top_matches: CoverageRecord[];
  recommendation: string;
};

type CoverageResponse = {
  coverage?: CoverageQuery;
};

type RepairGuide = {
  quick_summary?: string;
  confidence?: number;
  device_family?: {
    id?: string;
    label?: string;
    confidence?: number;
    evidence?: string[];
  };
  scan_evidence?: {
    board_type?: string;
    components_detected?: number;
    connector_count?: number;
    aoi_readiness?: string;
  };
  safety_profile?: {
    risk_level?: string;
    rules?: string[];
  };
  fault_candidates?: Array<{
    fault_id?: string;
    name?: string;
    likelihood?: number;
    evidence?: string[];
  }>;
  diagnostic_flow?: Array<{
    order?: number;
    title?: string;
    purpose?: string;
    pass_condition?: string;
  }>;
  evidence_to_collect_next?: string[];
};

type RepairGuideResponse = {
  repair_guide?: RepairGuide;
};

type BoardSession = {
  session_id?: string;
  title?: string;
  route?: string;
  status?: string;
  metrics?: {
    open_task_count?: number;
    task_count?: number;
    capture_burden?: number;
    certainty_level?: string;
    certainty_score?: number;
  };
  certainty?: {
    overall?: {
      level?: string;
      score?: number;
    };
  };
};

type BoardSessionResponse = {
  session?: BoardSession;
};

type IntakeStage = 'idle' | 'running' | 'done' | 'error';
type CaseRoute = 'repair' | 'salvage' | 'build' | 'source' | 'evidence' | 'safety';

type CaseLane = {
  id: CaseRoute;
  label: string;
  status: 'primary' | 'ready' | 'possible' | 'blocked';
  score: number;
  summary: string;
  icon: LucideIcon;
};

type CaseAction = {
  label: string;
  href: string;
  icon: LucideIcon;
  detail: string;
  tone: 'primary' | 'repair' | 'build' | 'source' | 'neutral';
};

type CaseFile = {
  route: CaseRoute;
  routeLabel: string;
  confidence: number;
  headline: string;
  verdict: string;
  lanes: CaseLane[];
  actions: CaseAction[];
  evidence: string[];
  missingEvidence: string[];
  warnings: string[];
};

const EXAMPLES = [
  {
    label: 'USB fan repair',
    description: 'USB desk fan will not spin. Driver board gets hot. It works briefly if the connector is wiggled.',
    device: 'USB desk fan / small motorized gadget',
    symptoms: 'fan will not spin\ndriver board gets hot\nworks if connector is wiggled',
  },
  {
    label: 'Retro console',
    description: 'Game Boy Color with corrosion in the battery area, sticky buttons, and no power after storage.',
    device: 'Game Boy Color',
    symptoms: 'no power\nbattery corrosion\nsticky buttons',
  },
  {
    label: 'Sourcing lot',
    description: 'ESP32 BME280 OLED salvage lot, 10 USD landed cost, possible weather monitor or energy display builds.',
    device: 'ESP32 BME280 OLED module lot',
    symptoms: '',
  },
];

const DANGER_TERMS = /\b(mains|microwave|crt|inverter|ev battery|lithium swollen|220v|240v|120v|capacitor bank|high voltage)\b/i;
const REPAIR_TERMS = /\b(broken|repair|fix|dead|no power|will not|won't|hot|burn|corrosion|intermittent|wiggle|not spinning|not charging|fault)\b/i;
const SOURCE_TERMS = /\b(listing|lot|buy|sell|price|usd|\$|shipping|margin|arbitrage|resale|sourcing)\b/i;
const BUILD_TERMS = /\b(build|project|make|wire|parts bin|module|arduino|esp32|raspberry|sensor|oled|relay)\b/i;

function percent(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function clampScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function splitLines(value: string) {
  return value
    .split(/\n|;|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function compact<T>(items: Array<T | null | undefined | false>) {
  return items.filter(Boolean) as T[];
}

function buildModuleParam(scan: AnalyzeResponse | null) {
  const labels = scan?.results?.detections
    ?.map((item) => item.part_number || item.ocr_text || item.class_name)
    .filter((item): item is string => Boolean(item && item.trim()))
    .slice(0, 6);
  return labels && labels.length > 0 ? `?modules=${encodeURIComponent(labels.join(','))}` : '';
}

function coverageBadge(record: CoverageRecord | null) {
  if (!record) return 'default';
  if (record.coverage >= 0.75) return 'success';
  if (record.coverage >= 0.55) return 'info';
  if (record.coverage >= 0.35) return 'warning';
  return 'default';
}

function laneStatusVariant(status: CaseLane['status']) {
  if (status === 'primary') return 'success';
  if (status === 'ready') return 'info';
  if (status === 'blocked') return 'warning';
  return 'default';
}

function actionClass(tone: CaseAction['tone']) {
  if (tone === 'primary') return 'border-cyan-300/50 bg-cyan-300 text-slate-950 hover:bg-cyan-200';
  if (tone === 'repair') return 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100 hover:bg-emerald-400/20';
  if (tone === 'build') return 'border-violet-300/30 bg-violet-400/10 text-violet-100 hover:bg-violet-400/20';
  if (tone === 'source') return 'border-amber-300/30 bg-amber-400/10 text-amber-100 hover:bg-amber-400/20';
  return 'border-white/10 bg-white/[0.03] text-slate-100 hover:bg-white/[0.06]';
}

function buildCaseFile(params: {
  text: string;
  deviceHint: string;
  symptoms: string[];
  hasImage: boolean;
  scan: AnalyzeResponse | null;
  coverage: CoverageQuery | null;
  guide: RepairGuide | null;
}): CaseFile {
  const { text, deviceHint, symptoms, hasImage, scan, coverage, guide } = params;
  const normalized = `${text} ${deviceHint} ${symptoms.join(' ')}`;
  const topCoverage = coverage?.top_matches?.[0] ?? null;
  const summary = scan?.results?.detection_summary;
  const board = scan?.results?.board_understanding?.board_identity;
  const aoi = scan?.results?.aoi_inspection;
  const certainty = scan?.results?.certainty_ledger;
  const certaintyLevel = String(certainty?.overall?.level ?? '').toLowerCase();
  const connectors = scan?.results?.machine_connection_map?.connector_count;
  const components = summary?.total_components ?? scan?.results?.detections?.length ?? 0;
  const scanScore = clampScore(certainty?.overall?.score ?? summary?.average_confidence ?? board?.confidence ?? 0);
  const repairScore = clampScore(guide?.confidence ?? guide?.device_family?.confidence ?? topCoverage?.coverage ?? 0);
  const sourceScore = SOURCE_TERMS.test(normalized) ? Math.max(0.68, topCoverage?.strategic_score ?? 0.45) : topCoverage?.strategic_score ?? 0.25;
  const buildScore = BUILD_TERMS.test(normalized) || components > 0 ? Math.max(0.52, scanScore) : 0.2;
  const hasDanger = DANGER_TERMS.test(normalized);
  const hasRepairSignal = symptoms.length > 0 || REPAIR_TERMS.test(normalized) || Boolean(guide?.fault_candidates?.length);
  const hasSourceSignal = SOURCE_TERMS.test(normalized);
  const hasBuildSignal = BUILD_TERMS.test(normalized);
  const weakScan = Boolean(
    summary?.review_required
    || ['low', 'unknown'].includes(String(summary?.detection_quality ?? '').toLowerCase())
    || ['possible', 'unknown'].includes(certaintyLevel),
  );
  const aoiBlocked = Boolean(aoi?.readiness && !['prototype_ready', 'operator_review'].includes(aoi.readiness));

  let route: CaseRoute = 'evidence';
  if (hasDanger) route = 'safety';
  else if (hasSourceSignal) route = 'source';
  else if (hasRepairSignal) route = 'repair';
  else if (hasImage && components > 0) route = 'salvage';
  else if (hasBuildSignal) route = 'build';

  const routeLabel: Record<CaseRoute, string> = {
    repair: 'Repair case',
    salvage: 'Salvage case',
    build: 'Build case',
    source: 'Sourcing case',
    evidence: 'Evidence case',
    safety: 'Safety review',
  };

  const primaryScore =
    route === 'repair' ? repairScore
    : route === 'salvage' ? Math.max(scanScore, 0.55)
    : route === 'source' ? sourceScore
    : route === 'build' ? buildScore
    : route === 'safety' ? 0.9
    : 0.35;

  const boardLine = board?.primary_type
    ? `${board.primary_type.replace(/_/g, ' ')} (${percent(board.confidence)})`
    : null;

  const lanes: CaseLane[] = [
    {
      id: 'repair',
      label: 'Repair',
      status: route === 'repair' ? 'primary' : hasRepairSignal ? 'ready' : 'possible',
      score: repairScore,
      summary: guide?.quick_summary || topCoverage?.why?.[0] || 'Use symptoms and scan evidence to isolate the likely fault.',
      icon: Wrench,
    },
    {
      id: 'salvage',
      label: 'Salvage',
      status: route === 'salvage' ? 'primary' : components > 0 ? 'ready' : 'possible',
      score: Math.max(scanScore, components > 0 ? 0.5 : 0.18),
      summary: components > 0
        ? `${components} candidate component${components === 1 ? '' : 's'} detected${boardLine ? ` on a ${boardLine} board` : ''}.`
        : 'Needs a board/device photo before module harvesting can be trusted.',
      icon: PackageCheck,
    },
    {
      id: 'build',
      label: 'Build',
      status: route === 'build' ? 'primary' : components > 0 || hasBuildSignal ? 'ready' : 'possible',
      score: buildScore,
      summary: 'Turn recovered modules or typed parts into a wiring plan, BOM, and KiCad handoff.',
      icon: Boxes,
    },
    {
      id: 'source',
      label: 'Source/sell',
      status: route === 'source' ? 'primary' : topCoverage ? 'ready' : 'possible',
      score: sourceScore,
      summary: topCoverage
        ? `${topCoverage.label}: ${topCoverage.coverage_level} fit, strategic score ${topCoverage.strategic_score.toFixed(2)}.`
        : 'Needs price, shipping, failure rate, and target build/resale idea.',
      icon: DollarSign,
    },
  ];

  const evidence = compact([
    hasImage ? 'Photo evidence attached' : null,
    components > 0 ? `${components} visual component candidates` : null,
    boardLine ? `Board role: ${boardLine}` : null,
    typeof connectors === 'number' ? `${connectors} connector candidate${connectors === 1 ? '' : 's'}` : null,
    aoi?.readiness ? `AOI readiness: ${aoi.readiness}` : null,
    certainty?.overall?.level ? `Evidence certainty: ${certainty.overall.level} (${percent(certainty.overall.score)})` : null,
    topCoverage ? `Market fit: ${topCoverage.label} (${topCoverage.coverage_level})` : null,
    guide?.device_family?.label ? `Repair family: ${guide.device_family.label}` : null,
  ]);

  const missingEvidence = compact([
    ...(certainty?.missing_evidence ?? []).slice(0, 6),
    !hasImage ? 'one clear whole-device or PCB photo' : null,
    hasImage ? 'opposite-side PCB photo if available' : null,
    !deviceHint.trim() ? 'device model or board marking' : null,
    symptoms.length === 0 && route !== 'source' ? 'symptom history and what changed before failure' : null,
    route === 'repair' ? 'input voltage, rail resistance, and current-limited startup current' : null,
    route === 'source' ? 'landed cost, failure rate, labor estimate, and expected resale/build value' : null,
    weakScan || aoiBlocked ? 'better lighting, focus, and closeups for uncertain detections' : null,
  ]);

  const warnings = compact([
    hasDanger ? 'Potential high-voltage, lithium, or mains hazard. Keep this in safety review until the exact device and power system are known.' : null,
    weakScan ? 'Image result needs operator review before acting on component labels.' : null,
    certainty?.training_queue?.should_capture ? 'This case should be saved as training/evidence material after review.' : null,
    aoiBlocked ? 'AOI/readiness is not production-grade for this evidence yet.' : null,
    route === 'repair' && !guide ? 'Repair guide did not generate; keep this as intake evidence only.' : null,
  ]);

  const headline =
    route === 'safety' ? 'Hold for safety review before repair or salvage.'
    : route === 'source' ? 'Treat this as a sourcing and arbitrage decision first.'
    : route === 'repair' ? 'Start with a repair workflow, backed by scan and symptom evidence.'
    : route === 'salvage' ? 'Start by validating salvageable modules before building.'
    : route === 'build' ? 'Start from the parts/build workflow.'
    : 'Collect more evidence before choosing repair, salvage, or build.';

  const verdict =
    guide?.quick_summary
      || coverage?.recommendation
      || scan?.summary?.summary_text
      || (boardLine ? `The scan points to ${boardLine}.` : 'The case needs more evidence before the engine can commit.');

  const buildParam = buildModuleParam(scan);
  const actions: CaseAction[] = compact([
    route === 'repair' ? {
      label: 'Open repair studio',
      href: '/repair',
      icon: Wrench,
      detail: 'Continue with fault candidates, safety gates, and measurement flow.',
      tone: 'primary',
    } : null,
    route === 'source' ? {
      label: 'Open parts bin',
      href: '/parts',
      icon: DollarSign,
      detail: 'Track acquired parts and ask what can be built or resold.',
      tone: 'primary',
    } : null,
    route === 'salvage' ? {
      label: 'Run salvage scan',
      href: '/scan?mode=salvage',
      icon: PackageCheck,
      detail: 'Generate extraction, validation, and build-package context.',
      tone: 'primary',
    } : null,
    {
      label: 'Build from modules',
      href: `/build${buildParam}`,
      icon: Boxes,
      detail: 'Wire modules, run safety checks, export BOM or KiCad.',
      tone: route === 'build' ? 'primary' : 'build',
    },
    {
      label: 'Scan another angle',
      href: '/scan',
      icon: Camera,
      detail: 'Add cleaner image evidence when confidence is weak.',
      tone: 'neutral',
    },
    {
      label: 'Advanced PCB workbench',
      href: '/workspace',
      icon: CircuitBoard,
      detail: 'Use when a KiCad board file or manufacturing validation is available.',
      tone: 'neutral',
    },
  ]);

  return {
    route,
    routeLabel: routeLabel[route],
    confidence: primaryScore,
    headline,
    verdict,
    lanes,
    actions,
    evidence,
    missingEvidence: missingEvidence.length > 0 ? missingEvidence : ['post-action measurement notes and before/after photos'],
    warnings,
  };
}

async function postJson<T>(url: string, body: JsonRecord): Promise<T | null> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, `${url} failed.`));
  }
  return payload as T | null;
}

function StepBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
      active ? 'border-cyan-300/40 bg-cyan-300/10 text-cyan-100' : 'border-white/10 bg-white/[0.02] text-slate-400'
    }`}>
      <span className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-cyan-300' : 'bg-slate-600'}`} />
      {label}
    </span>
  );
}

function EvidenceList({ title, items, icon: Icon }: { title: string; items: string[]; icon: LucideIcon }) {
  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
        <Icon className="h-4 w-4" />
        {title}
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item} className="flex gap-2 text-sm leading-6 text-slate-300">
            <CheckCircle2 className="mt-1 h-3.5 w-3.5 shrink-0 text-emerald-300" />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CaseFilePanel({ caseFile, coverage, guide, session }: { caseFile: CaseFile; coverage: CoverageQuery | null; guide: RepairGuide | null; session: BoardSession | null }) {
  const topCoverage = coverage?.top_matches?.[0] ?? null;
  const topFault = guide?.fault_candidates?.[0] ?? null;

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-cyan-300/25 bg-cyan-300/[0.04] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Badge variant="info">{caseFile.routeLabel}</Badge>
              <Badge variant={caseFile.confidence >= 0.7 ? 'success' : caseFile.confidence >= 0.45 ? 'warning' : 'default'}>
                {percent(caseFile.confidence)} confidence
              </Badge>
            </div>
            <h2 className="max-w-3xl text-2xl font-semibold leading-tight text-white">{caseFile.headline}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">{caseFile.verdict}</p>
          </div>
          <Route className="h-6 w-6 text-cyan-200" />
        </div>
      </section>

      {session?.session_id && (
        <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Database className="h-4 w-4" />
                Saved board session
              </div>
              <div className="text-sm text-white">{session.title || session.session_id}</div>
              <div className="mt-1 text-xs text-slate-400">
                {session.metrics?.open_task_count ?? 0} open evidence task(s) · {session.metrics?.capture_burden ?? 0} capture prompt(s)
              </div>
            </div>
            <Link
              href="/review"
              className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-cyan-100 transition-colors hover:bg-white/[0.08]"
            >
              Open review queue
            </Link>
          </div>
        </section>
      )}

      {caseFile.warnings.length > 0 && (
        <section className="rounded-lg border border-amber-300/30 bg-amber-400/[0.05] p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            Gated before action
          </div>
          <div className="space-y-2">
            {caseFile.warnings.map((warning) => (
              <p key={warning} className="text-sm leading-6 text-amber-100/80">{warning}</p>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-3 lg:grid-cols-4">
        {caseFile.lanes.map((lane) => {
          const Icon = lane.icon;
          return (
            <div key={lane.id} className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="flex items-start justify-between gap-3">
                <Icon className="h-5 w-5 text-slate-300" />
                <Badge variant={laneStatusVariant(lane.status)}>{lane.status}</Badge>
              </div>
              <div className="mt-4 text-sm font-semibold text-white">{lane.label}</div>
              <div className="mt-1 text-xl font-semibold text-white">{percent(lane.score)}</div>
              <p className="mt-3 text-xs leading-5 text-slate-400">{lane.summary}</p>
            </div>
          );
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <EvidenceList title="Evidence captured" items={caseFile.evidence.length ? caseFile.evidence : ['Plain-language case note']} icon={ClipboardList} />
        <EvidenceList title="Evidence still needed" items={caseFile.missingEvidence} icon={Search} />
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          <ArrowRight className="h-4 w-4" />
          Next actions
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {caseFile.actions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={`${action.href}-${action.label}`}
                href={action.href}
                className={`rounded-lg border p-4 transition-colors ${actionClass(action.tone)}`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Icon className="h-4 w-4" />
                  {action.label}
                </div>
                <p className="mt-2 text-xs leading-5 opacity-80">{action.detail}</p>
              </Link>
            );
          })}
        </div>
      </section>

      {(topCoverage || topFault || guide?.diagnostic_flow?.length) && (
        <section className="grid gap-4 lg:grid-cols-2">
          {topCoverage && (
            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Market fit</div>
                <Badge variant={coverageBadge(topCoverage)}>{topCoverage.coverage_level}</Badge>
              </div>
              <div className="text-sm font-semibold text-white">{topCoverage.label}</div>
              <div className="mt-2 grid grid-cols-3 gap-2">
                <div className="rounded-md border border-white/10 bg-white/[0.02] p-2">
                  <div className="text-[10px] text-slate-500">Coverage</div>
                  <div className="text-sm font-semibold text-white">{percent(topCoverage.coverage)}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.02] p-2">
                  <div className="text-[10px] text-slate-500">Demand</div>
                  <div className="text-sm font-semibold text-white">{percent(topCoverage.relevance)}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.02] p-2">
                  <div className="text-[10px] text-slate-500">Score</div>
                  <div className="text-sm font-semibold text-white">{topCoverage.strategic_score.toFixed(2)}</div>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-400">{topCoverage.why?.[0] ?? coverage?.recommendation}</p>
            </div>
          )}

          {topFault && (
            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Top fault candidate</div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-white">{topFault.name}</div>
                  <p className="mt-2 text-xs leading-5 text-slate-400">{topFault.evidence?.slice(0, 2).join(' - ') || 'Generated from symptoms and scan context.'}</p>
                </div>
                <Badge variant="warning">{percent(topFault.likelihood)}</Badge>
              </div>
              {guide?.diagnostic_flow?.length ? (
                <div className="mt-4 space-y-2">
                  {guide.diagnostic_flow.slice(0, 3).map((step) => (
                    <div key={`${step.order}-${step.title}`} className="rounded-md border border-white/10 bg-white/[0.02] p-2">
                      <div className="text-xs font-semibold text-white">{step.order}. {step.title}</div>
                      <div className="mt-1 text-[11px] leading-4 text-slate-500">{step.pass_condition}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default function StartPage() {
  usePageTitle('Start Case | Circuit.AI');

  const [description, setDescription] = useState('');
  const [deviceHint, setDeviceHint] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [stage, setStage] = useState<IntakeStage>('idle');
  const [error, setError] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<CoverageQuery | null>(null);
  const [guide, setGuide] = useState<RepairGuide | null>(null);
  const [caseFile, setCaseFile] = useState<CaseFile | null>(null);
  const [boardSession, setBoardSession] = useState<BoardSession | null>(null);

  const combinedText = useMemo(
    () => [description, deviceHint, symptoms].map((item) => item.trim()).filter(Boolean).join('\n'),
    [description, deviceHint, symptoms],
  );

  const symptomList = useMemo(() => splitLines(symptoms || description), [description, symptoms]);

  const activeSignals = useMemo(() => ({
    photo: Boolean(imageFile),
    context: Boolean(description.trim()),
    symptoms: symptomList.length > 0,
    market: SOURCE_TERMS.test(combinedText),
  }), [combinedText, description, imageFile, symptomList.length]);

  const chooseImage = useCallback((file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Choose an image file.');
      return;
    }
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setError(null);
  }, [imagePreview]);

  const fillExample = useCallback((example: typeof EXAMPLES[number]) => {
    setDescription(example.description);
    setDeviceHint(example.device);
    setSymptoms(example.symptoms);
    setStage('idle');
    setCaseFile(null);
    setBoardSession(null);
    setError(null);
  }, []);

  const runIntake = useCallback(async () => {
    if (!combinedText && !imageFile) {
      setError('Add a photo or describe the item first.');
      return;
    }

    setStage('running');
    setError(null);
    setCoverage(null);
    setGuide(null);
    setCaseFile(null);
    setBoardSession(null);

    let nextScan: AnalyzeResponse | null = null;
    let nextCoverage: CoverageQuery | null = null;
    let nextGuide: RepairGuide | null = null;

    try {
      if (imageFile) {
        const form = new FormData();
        form.set('file', imageFile, imageFile.name);
        form.set('backend', 'hybrid');
        form.set('enable_ocr', 'true');
        form.set('enable_quality_assessment', 'true');
        const response = await fetch('/api/proxy/analyze', { method: 'POST', body: form });
        const payload = await readJsonPayload<AnalyzeResponse | ProxyErrorPayload>(response);
        if (!response.ok || isProxyFailure(payload)) {
          throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, 'Image analysis failed.'));
        }
        nextScan = payload as AnalyzeResponse;
      }

      if (combinedText) {
        const payload = await postJson<CoverageResponse>('/api/proxy/repair/coverage', { query: combinedText });
        nextCoverage = payload?.coverage ?? null;
        setCoverage(nextCoverage);
      }

      const shouldGenerateGuide = Boolean(
        combinedText
        && (REPAIR_TERMS.test(combinedText) || symptomList.length > 0 || nextScan?.results?.board_understanding?.board_identity?.primary_type),
      );

      if (shouldGenerateGuide) {
        const payload = await postJson<RepairGuideResponse>('/api/proxy/repair/guide', {
          analysis: nextScan?.results ?? {},
          symptoms: symptomList,
          device_hint: deviceHint || description,
        });
        nextGuide = payload?.repair_guide ?? null;
        setGuide(nextGuide);
      }

      const built = buildCaseFile({
        text: combinedText,
        deviceHint,
        symptoms: symptomList,
        hasImage: Boolean(imageFile),
        scan: nextScan,
        coverage: nextCoverage,
        guide: nextGuide,
      });
      setCaseFile(built);
      try {
        const saved = await postJson<BoardSessionResponse>('/api/proxy/board-sessions', {
          description,
          device_hint: deviceHint,
          symptoms: symptomList,
          route: built.route,
          route_label: built.routeLabel,
          analysis: nextScan?.results ?? {},
          summary: nextScan?.summary ?? {},
          repair_guide: nextGuide ?? {},
          coverage: nextCoverage ?? {},
          case_file: built,
          image: imageFile ? {
            filename: imageFile.name,
            content_type: imageFile.type,
            size_bytes: imageFile.size,
          } : null,
          source: 'start_intake',
        });
        setBoardSession(saved?.session ?? null);
      } catch (sessionError) {
        setBoardSession(null);
        setError(sessionError instanceof Error ? sessionError.message : 'Case file was created, but session save failed.');
      }
      try {
        localStorage.setItem('circuit-ai-latest-case', JSON.stringify({
          description,
          deviceHint,
          symptoms,
          caseFile: built,
          createdAt: new Date().toISOString(),
        }));
      } catch {
        // Local storage is a convenience only.
      }
      setStage('done');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Case intake failed.');
      setStage('error');
    }
  }, [combinedText, description, deviceHint, imageFile, symptomList, symptoms]);

  return (
    <div className="min-h-screen bg-[#090f18] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">automatic intake</Badge>
                <Badge variant="default">scan</Badge>
                <Badge variant="default">repair</Badge>
                <Badge variant="default">salvage</Badge>
                <Badge variant="default">build</Badge>
              </div>
              <h1 className="max-w-4xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
                Start with the thing. Circuit.AI decides the workflow.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Upload evidence, describe the item, or paste sourcing context. The intake creates one case file and routes it into repair, salvage, build, resale, safety review, or evidence collection.
              </p>
            </div>
            <div className="grid gap-2 self-start sm:grid-cols-2 lg:grid-cols-1">
              <StepBadge active={activeSignals.photo} label="photo evidence" />
              <StepBadge active={activeSignals.context} label="plain context" />
              <StepBadge active={activeSignals.symptoms} label="symptoms" />
              <StepBadge active={activeSignals.market} label="market signal" />
            </div>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-[440px_minmax(0,1fr)]">
          <section className="space-y-4">
            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <FileText className="h-4 w-4" />
                Case input
              </div>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Example: USB fan will not spin, board gets hot near the driver, connector must be wiggled."
                className="min-h-[132px] w-full resize-y rounded-lg border border-white/10 bg-black/30 px-3 py-3 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-cyan-300/50 focus:outline-none"
              />
              <div className="mt-3 grid gap-3">
                <input
                  value={deviceHint}
                  onChange={(event) => setDeviceHint(event.target.value)}
                  placeholder="Device, model, board marking, or listing title"
                  className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300/50 focus:outline-none"
                />
                <textarea
                  value={symptoms}
                  onChange={(event) => setSymptoms(event.target.value)}
                  placeholder="Symptoms or observed actions, one per line"
                  className="min-h-[90px] resize-y rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-cyan-300/50 focus:outline-none"
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLES.map((example) => (
                  <button
                    key={example.label}
                    type="button"
                    onClick={() => fillExample(example)}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/[0.07] hover:text-white"
                  >
                    {example.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Camera className="h-4 w-4" />
                Photo evidence
              </div>
              <label className="flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-white/15 bg-black/20 p-4 text-center transition-colors hover:border-cyan-300/40 hover:bg-cyan-300/[0.03]">
                {imagePreview ? (
                  <Image
                    src={imagePreview}
                    alt="Case evidence preview"
                    width={320}
                    height={180}
                    unoptimized
                    className="max-h-44 rounded-md object-contain"
                  />
                ) : (
                  <>
                    <Upload className="mb-3 h-6 w-6 text-cyan-200" />
                    <div className="text-sm font-semibold text-white">Add photo</div>
                    <div className="mt-1 text-xs text-slate-500">PCB, whole device, label, corrosion, connector, or listing photo</div>
                  </>
                )}
                <input
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={(event) => chooseImage(event.target.files?.[0] ?? null)}
                />
              </label>
              {imageFile && (
                <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.02] px-3 py-2">
                  <span className="min-w-0 truncate text-xs text-slate-300">{imageFile.name}</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (imagePreview) URL.revokeObjectURL(imagePreview);
                      setImageFile(null);
                      setImagePreview(null);
                    }}
                    className="text-xs text-slate-500 hover:text-white"
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>

            <Button
              onClick={runIntake}
              disabled={stage === 'running'}
              className="h-12 w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
            >
              {stage === 'running' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              {stage === 'running' ? 'Creating case file...' : 'Create case file'}
            </Button>

            {error && (
              <div className="rounded-lg border border-rose-400/40 bg-rose-500/10 p-3 text-sm leading-6 text-rose-100">
                {error}
              </div>
            )}
          </section>

          <section className="min-h-[640px]">
            {caseFile ? (
              <CaseFilePanel caseFile={caseFile} coverage={coverage} guide={guide} session={boardSession} />
            ) : (
              <div className="flex min-h-[640px] items-center justify-center rounded-lg border border-dashed border-white/10 bg-white/[0.01] p-8 text-center">
                <div className="max-w-lg">
                  <ShieldCheck className="mx-auto h-8 w-8 text-cyan-200" />
                  <h2 className="mt-4 text-xl font-semibold text-white">Case file appears here</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    The result will show the best route, confidence, evidence captured, missing evidence, safety gates, and direct next actions.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
