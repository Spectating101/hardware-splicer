'use client';

import { useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Film,
  Gauge,
  LoaderCircle,
  PlayCircle,
  Search,
  ShieldCheck,
  Wrench,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;

type CoverageRecord = {
  item_id: string;
  label: string;
  examples: string[];
  coverage: number;
  relevance: number;
  strategic_score: number;
  coverage_level: string;
  signal_hits?: string[];
  why: string[];
  gaps: string[];
};

type CoveragePortfolio = {
  summary: {
    strong_count: number;
    partial_count: number;
    weak_count: number;
    weighted_coverage: number;
  };
  strong_fit: CoverageRecord[];
  partial_fit: CoverageRecord[];
  weak_fit: CoverageRecord[];
  recommended_next_builds: string[];
};

type CoverageResponse = {
  coverage?: CoveragePortfolio | {
    matched: boolean;
    top_matches: CoverageRecord[];
    recommendation: string;
  };
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
    category?: string;
    evidence?: string[];
    repair_steps?: string[];
  }>;
  diagnostic_flow?: Array<{
    order?: number;
    title?: string;
    purpose?: string;
    pass_condition?: string;
    fail_branch?: string;
  }>;
  parts_and_tools?: {
    tools?: string[];
    likely_parts?: string[];
  };
  evidence_to_collect_next?: string[];
};

type RepairGuideResponse = {
  repair_guide?: RepairGuide;
};

type VideoPlaybook = {
  can_follow_score?: number;
  difficulty?: string;
  video_pattern?: {
    id?: string;
    label?: string;
    confidence?: number;
  };
  repair_guide?: RepairGuide;
  watch_map?: Array<{ moment?: string; capture?: string[] }>;
  recreation_flow?: Array<{ order?: number; action?: string; circuit_ai_support?: string; done_when?: string }>;
  quality_gates?: string[];
};

type VideoPlaybookResponse = {
  playbook?: VideoPlaybook;
};

const fallbackPortfolio: CoveragePortfolio = {
  summary: {
    strong_count: 4,
    partial_count: 3,
    weak_count: 3,
    weighted_coverage: 0.518,
  },
  strong_fit: [
    {
      item_id: 'retro_handheld_console',
      label: 'Retro handheld consoles',
      examples: ['Game Boy', 'Game Gear', 'PS Vita'],
      coverage: 0.78,
      relevance: 0.92,
      strategic_score: 0.718,
      coverage_level: 'strong',
      why: ['cleaning, corrosion, contacts, buttons, screens, speakers, and simple boards are inspectable'],
      gaps: ['revision/reference photo library', 'model-specific parts catalog'],
    },
    {
      item_id: 'small_usb_gadget',
      label: 'Small USB powered gadgets',
      examples: ['USB fan', 'LED gadget', 'small pump'],
      coverage: 0.86,
      relevance: 0.72,
      strategic_score: 0.619,
      coverage_level: 'strong',
      why: ['power, connector, regulator, driver, load, and cable faults fit the current repair lane'],
      gaps: ['motor/fan/load test library', 'enclosure and mechanical notes'],
    },
    {
      item_id: 'game_controller',
      label: 'Game controllers',
      examples: ['DualSense', 'Xbox controller', 'Joy-Con'],
      coverage: 0.66,
      relevance: 0.9,
      strategic_score: 0.594,
      coverage_level: 'usable_with_gaps',
      why: ['cleaning, contacts, USB, battery, button, flex, connector, and resale workflows are relevant'],
      gaps: ['stick-drift decision tree', 'calibration software workflow'],
    },
    {
      item_id: 'sensor_display_module',
      label: 'Sensor/display modules',
      examples: ['meter', 'weather monitor', 'panel display'],
      coverage: 0.74,
      relevance: 0.7,
      strategic_score: 0.518,
      coverage_level: 'usable_with_gaps',
      why: ['board understanding, OCR, connector mapping, and firmware smoke-test planning are useful'],
      gaps: ['calibration procedure database', 'display ribbon/backlight guides'],
    },
  ],
  partial_fit: [
    {
      item_id: 'modern_game_console',
      label: 'Modern game consoles',
      examples: ['Nintendo Switch', 'PlayStation 5', 'Xbox Series'],
      coverage: 0.52,
      relevance: 0.96,
      strategic_score: 0.499,
      coverage_level: 'partial',
      why: ['triage, cleaning, fan, connector, corrosion, and resale guidance are useful'],
      gaps: ['HDMI/USB-C microsoldering', 'boardview/schematic integration', 'BGA/APU/storage faults'],
    },
    {
      item_id: 'phone_or_tablet',
      label: 'Phones and tablets',
      examples: ['iPhone', 'iPad', 'Android tablet'],
      coverage: 0.36,
      relevance: 0.94,
      strategic_score: 0.338,
      coverage_level: 'partial',
      why: ['symptom intake and safety warnings are useful'],
      gaps: ['model-specific teardown', 'battery/adhesive safety', 'paired parts and calibration'],
    },
  ],
  weak_fit: [
    {
      item_id: 'mains_appliance',
      label: 'Mains appliances',
      examples: ['microwave', 'vacuum', 'washing machine'],
      coverage: 0.24,
      relevance: 0.82,
      strategic_score: 0.197,
      coverage_level: 'weak',
      why: ['some control-board visual triage is possible after safe isolation'],
      gaps: ['mains safety', 'heater/compressor/mechanical diagnostics', 'liability boundaries'],
    },
  ],
  recommended_next_builds: [
    'controller stick-drift and button/contact cleaning lane',
    'retro handheld console revision/parts catalog',
    'modern console triage lane with HDMI/USB-C caution and boardview hooks',
  ],
};

const demoAnalysis = {
  detection_summary: {
    total_components: 10,
    components_by_type: { connector: 5, transistor: 4, inductor: 1 },
    average_confidence: 0.64,
  },
  board_understanding: {
    board_identity: {
      primary_type: 'motor_or_actuator_driver',
      confidence: 0.785,
    },
    functional_blocks: [
      {
        block_type: 'actuator_drive',
        confidence: 0.85,
        component_count: 9,
        function: 'Switches current for motors, relays, solenoids, or loads',
      },
      {
        block_type: 'power_input_protection',
        confidence: 0.95,
        component_count: 10,
        function: 'Accepts incoming power and protects downstream circuitry',
      },
      {
        block_type: 'io_connectivity',
        confidence: 0.85,
        component_count: 5,
        function: 'Provides external electrical connections',
      },
    ],
  },
  machine_connection_map: { connector_count: 5 },
  marking_analysis: { components: [{ text: 'ESP8266' }, { text: 'CONN' }, { text: 'MCU' }] },
  aoi_inspection: { readiness: 'prototype_ready', blockers: [] },
  salvage_opportunities: {
    asset_summary: {
      capabilities: { actuator_driver: 1, controller: 1, power: 1, connector: 1 },
    },
  },
};

const demoSymptoms = 'fan will not spin\ndriver board gets hot\nworks if the connector is wiggled';

function splitLines(value: string) {
  return value
    .split(/\n|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseJsonObject(value: string): JsonRecord {
  if (!value.trim()) return {};
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Analysis JSON must be an object.');
  }
  return parsed as JsonRecord;
}

function percent(value?: number) {
  if (typeof value !== 'number') return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function coverageBadge(record: CoverageRecord) {
  if (record.coverage >= 0.75) return 'success';
  if (record.coverage >= 0.55) return 'info';
  if (record.coverage >= 0.35) return 'warning';
  return 'error';
}

function Panel({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#0b1422] p-5 shadow-[0_20px_60px_rgba(2,6,23,0.22)]">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/80">{eyebrow}</div>
          <h2 className="mt-2 text-lg font-semibold text-white">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function CoverageCard({ record }: { record: CoverageRecord }) {
  return (
    <div className="rounded-lg border border-white/10 bg-[#08111d] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-white">{record.label}</div>
          <div className="mt-1 text-xs text-slate-400">{record.examples.slice(0, 3).join(' / ')}</div>
        </div>
        <Badge variant={coverageBadge(record)}>{record.coverage_level}</Badge>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-md border border-white/8 bg-white/[0.03] p-2">
          <div className="text-slate-500">Coverage</div>
          <div className="mt-1 font-semibold text-white">{percent(record.coverage)}</div>
        </div>
        <div className="rounded-md border border-white/8 bg-white/[0.03] p-2">
          <div className="text-slate-500">Demand</div>
          <div className="mt-1 font-semibold text-white">{percent(record.relevance)}</div>
        </div>
        <div className="rounded-md border border-white/8 bg-white/[0.03] p-2">
          <div className="text-slate-500">Score</div>
          <div className="mt-1 font-semibold text-white">{record.strategic_score.toFixed(2)}</div>
        </div>
      </div>
      <div className="mt-4 text-sm leading-6 text-slate-300">{record.why[0]}</div>
      <div className="mt-3 text-xs leading-5 text-amber-200/90">Gap: {record.gaps[0]}</div>
    </div>
  );
}

function RepairGuideView({ guide }: { guide: RepairGuide | null }) {
  if (!guide) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 bg-[#08111d] p-5 text-sm leading-6 text-slate-400">
        Generate a guide to see device family, fault candidates, diagnostic branches, safety gates, and parts/tools.
      </div>
    );
  }

  const candidates = guide.fault_candidates || [];
  const flow = guide.diagnostic_flow || [];
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-emerald-300/20 bg-emerald-300/8 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="success">{guide.device_family?.label || 'Device family'}</Badge>
          <Badge variant="info">confidence {percent(guide.confidence)}</Badge>
          <Badge variant={guide.safety_profile?.risk_level === 'high' ? 'warning' : 'default'}>
            {guide.safety_profile?.risk_level || 'risk pending'}
          </Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-200">{guide.quick_summary}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Board</div>
          <div className="mt-1 text-sm font-semibold text-white">{guide.scan_evidence?.board_type || 'unknown'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Components</div>
          <div className="mt-1 text-sm font-semibold text-white">{guide.scan_evidence?.components_detected ?? 'N/A'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Connectors</div>
          <div className="mt-1 text-sm font-semibold text-white">{guide.scan_evidence?.connector_count ?? 'N/A'}</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            Fault candidates
          </div>
          {candidates.slice(0, 4).map((candidate) => (
            <div key={candidate.fault_id || candidate.name} className="rounded-lg border border-white/10 bg-[#08111d] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-semibold text-white">{candidate.name}</div>
                <Badge variant="warning">{percent(candidate.likelihood)}</Badge>
              </div>
              <div className="mt-2 text-xs leading-5 text-slate-400">{(candidate.evidence || []).slice(0, 2).join(' • ')}</div>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <ClipboardCheck className="h-4 w-4 text-cyan-300" />
            Diagnostic flow
          </div>
          {flow.slice(0, 5).map((step) => (
            <div key={`${step.order}-${step.title}`} className="rounded-lg border border-white/10 bg-[#08111d] p-4">
              <div className="text-sm font-semibold text-white">
                {step.order}. {step.title}
              </div>
              <div className="mt-2 text-xs leading-5 text-slate-400">{step.purpose}</div>
              <div className="mt-2 text-xs leading-5 text-emerald-200/80">Pass: {step.pass_condition}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function VideoPlaybookView({ playbook }: { playbook: VideoPlaybook | null }) {
  if (!playbook) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 bg-[#08111d] p-5 text-sm leading-6 text-slate-400">
        Generate a playbook to convert a repair video reference into a watch map, recreation flow, and quality gates.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3 md:col-span-2">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Pattern</div>
          <div className="mt-1 text-sm font-semibold text-white">{playbook.video_pattern?.label || 'unknown'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Can follow</div>
          <div className="mt-1 text-sm font-semibold text-white">{percent(playbook.can_follow_score)}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Difficulty</div>
          <div className="mt-1 text-sm font-semibold text-white">{playbook.difficulty || 'N/A'}</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Film className="h-4 w-4 text-cyan-300" />
            Watch map
          </div>
          <div className="space-y-3">
            {(playbook.watch_map || []).slice(0, 5).map((item) => (
              <div key={item.moment} className="rounded-lg border border-white/10 bg-[#08111d] p-4">
                <div className="text-sm font-semibold text-white">{item.moment}</div>
                <div className="mt-2 text-xs leading-5 text-slate-400">{(item.capture || []).join(', ')}</div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            Quality gates
          </div>
          <div className="space-y-2">
            {(playbook.quality_gates || []).slice(0, 7).map((gate) => (
              <div key={gate} className="rounded-lg border border-white/10 bg-[#08111d] px-4 py-3 text-sm text-slate-300">
                {gate}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RepairStudioPage() {
  usePageTitle('Repair Studio | Circuit.AI');

  const [apiKey, setApiKey] = useState('');
  const [coverageQuery, setCoverageQuery] = useState('Odd Tinkering Game Boy restoration cleaning corrosion');
  const [coverageResult, setCoverageResult] = useState<CoverageRecord[] | null>(null);
  const [coverageMessage, setCoverageMessage] = useState<string | null>(null);
  const [symptoms, setSymptoms] = useState(demoSymptoms);
  const [deviceHint, setDeviceHint] = useState('USB desk fan / small motorized gadget');
  const [analysisText, setAnalysisText] = useState(JSON.stringify(demoAnalysis, null, 2));
  const [guide, setGuide] = useState<RepairGuide | null>(null);
  const [videoTitle, setVideoTitle] = useState('Fixing a broken USB desk fan that will not spin');
  const [videoChannel, setVideoChannel] = useState('Repair video reference');
  const [videoUrl, setVideoUrl] = useState('https://www.youtube.com/results?search_query=usb+desk+fan+repair+not+spinning');
  const [videoActions, setVideoActions] = useState('inspect PCB and motor driver\ntest power input and motor load\nrepair connector or driver stage');
  const [playbook, setPlaybook] = useState<VideoPlaybook | null>(null);
  const [busy, setBusy] = useState<'coverage' | 'guide' | 'video' | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const allCoverage = useMemo(
    () => [...fallbackPortfolio.strong_fit, ...fallbackPortfolio.partial_fit, ...fallbackPortfolio.weak_fit],
    [],
  );

  const requestHeaders = useMemo<HeadersInit>(() => ({
    'content-type': 'application/json',
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
  }), [apiKey]);

  const runCoverage = async () => {
    setBusy('coverage');
    setErrorMessage(null);
    try {
      const response = await fetch('/api/proxy/repair/coverage', {
        method: 'POST',
        headers: requestHeaders,
        body: JSON.stringify({ query: coverageQuery }),
      });
      const payload = await readJsonPayload<CoverageResponse | ProxyErrorPayload>(response);
      if (isProxyFailure(payload)) {
        setErrorMessage(getProxyErrorMessage(payload, 'Coverage request failed.'));
        return;
      }
      const coverage = (payload as CoverageResponse | null)?.coverage;
      if (coverage && 'top_matches' in coverage) {
        setCoverageResult(coverage.top_matches);
        setCoverageMessage(coverage.recommendation);
      }
    } catch {
      setErrorMessage('Coverage request failed. The local fallback matrix is still shown below.');
    } finally {
      setBusy(null);
    }
  };

  const runGuide = async () => {
    setBusy('guide');
    setErrorMessage(null);
    try {
      const analysis = parseJsonObject(analysisText);
      const response = await fetch('/api/proxy/repair/guide', {
        method: 'POST',
        headers: requestHeaders,
        body: JSON.stringify({
          analysis,
          symptoms: splitLines(symptoms),
          device_hint: deviceHint,
        }),
      });
      const payload = await readJsonPayload<RepairGuideResponse | ProxyErrorPayload>(response);
      if (isProxyFailure(payload)) {
        setErrorMessage(getProxyErrorMessage(payload, 'Repair guide request failed.'));
        return;
      }
      setGuide((payload as RepairGuideResponse | null)?.repair_guide || null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Repair guide request failed.');
    } finally {
      setBusy(null);
    }
  };

  const runVideoPlaybook = async () => {
    setBusy('video');
    setErrorMessage(null);
    try {
      const analysis = parseJsonObject(analysisText);
      const response = await fetch('/api/proxy/repair/video-playbook', {
        method: 'POST',
        headers: requestHeaders,
        body: JSON.stringify({
          video_reference: {
            title: videoTitle,
            channel: videoChannel,
            url: videoUrl,
            observed_actions: splitLines(videoActions),
          },
          analysis,
          symptoms: splitLines(symptoms),
          device_hint: deviceHint,
        }),
      });
      const payload = await readJsonPayload<VideoPlaybookResponse | ProxyErrorPayload>(response);
      if (isProxyFailure(payload)) {
        setErrorMessage(getProxyErrorMessage(payload, 'Video playbook request failed.'));
        return;
      }
      setPlaybook((payload as VideoPlaybookResponse | null)?.playbook || null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Video playbook request failed.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#07101d] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-8 rounded-2xl border border-white/10 bg-[#0a1321] p-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">repair intelligence</Badge>
                <Badge variant="success">small electronics wedge</Badge>
                <Badge variant="warning">coverage-aware</Badge>
              </div>
              <h1 className="mt-5 max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Repair Studio turns scan evidence and messy video inspiration into reproducible repair work.
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
                Start with a random item class, symptoms, or a repair video reference. The studio separates strong product targets from weak ones, then generates a measured diagnostic flow with safety gates.
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-[#08111d] p-4">
              <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Backend access key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="Optional bearer token"
                className="mt-2 w-full rounded-lg border border-white/10 bg-[#050b13] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
              />
              <div className="mt-3 text-xs leading-5 text-slate-400">
                Proxy routes call the local FastAPI backend through `CIRCUIT_AI_API_URL`.
              </div>
            </div>
          </div>
        </section>

        {errorMessage && (
          <div className="mb-6 rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
            {errorMessage}
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          <div className="space-y-6">
            <Panel
              eyebrow="Coverage"
              title="Check whether a random repair item is worth supporting."
              action={<Gauge className="h-5 w-5 text-cyan-300" />}
            >
              <div className="space-y-3">
                <textarea
                  value={coverageQuery}
                  onChange={(event) => setCoverageQuery(event.target.value)}
                  className="min-h-24 w-full resize-none rounded-lg border border-white/10 bg-[#050b13] px-3 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/60"
                />
                <Button onClick={runCoverage} disabled={busy === 'coverage'} className="w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200">
                  {busy === 'coverage' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                  Score coverage
                </Button>
              </div>
              {coverageResult && (
                <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/8 p-3 text-sm leading-6 text-cyan-50">
                  {coverageMessage}
                </div>
              )}
            </Panel>

            <Panel
              eyebrow="Evidence"
              title="Symptoms and scan context"
              action={<Activity className="h-5 w-5 text-emerald-300" />}
            >
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Device hint</label>
                  <input
                    value={deviceHint}
                    onChange={(event) => setDeviceHint(event.target.value)}
                    className="mt-2 w-full rounded-lg border border-white/10 bg-[#050b13] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Symptoms</label>
                  <textarea
                    value={symptoms}
                    onChange={(event) => setSymptoms(event.target.value)}
                    className="mt-2 min-h-28 w-full resize-none rounded-lg border border-white/10 bg-[#050b13] px-3 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/60"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between gap-3">
                    <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Analysis JSON</label>
                    <button
                      type="button"
                      onClick={() => setAnalysisText(JSON.stringify(demoAnalysis, null, 2))}
                      className="text-xs font-medium text-cyan-200 hover:text-cyan-100"
                    >
                      Load demo
                    </button>
                  </div>
                  <textarea
                    value={analysisText}
                    onChange={(event) => setAnalysisText(event.target.value)}
                    spellCheck={false}
                    className="mt-2 min-h-56 w-full resize-y rounded-lg border border-white/10 bg-[#050b13] px-3 py-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-300/60"
                  />
                </div>
              </div>
            </Panel>
          </div>

          <div className="space-y-6">
            <Panel
              eyebrow="Market Map"
              title="Where the current system is strong enough to sell."
              action={<ShieldCheck className="h-5 w-5 text-emerald-300" />}
            >
              <div className="mb-5 grid gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
                  <div className="text-xs text-slate-500">Weighted coverage</div>
                  <div className="mt-1 text-lg font-semibold text-white">{percent(fallbackPortfolio.summary.weighted_coverage)}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
                  <div className="text-xs text-slate-500">Strong</div>
                  <div className="mt-1 text-lg font-semibold text-emerald-200">{fallbackPortfolio.summary.strong_count}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
                  <div className="text-xs text-slate-500">Partial</div>
                  <div className="mt-1 text-lg font-semibold text-amber-200">{fallbackPortfolio.summary.partial_count}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-[#08111d] p-3">
                  <div className="text-xs text-slate-500">Weak</div>
                  <div className="mt-1 text-lg font-semibold text-rose-200">{fallbackPortfolio.summary.weak_count}</div>
                </div>
              </div>

              {coverageResult && (
                <div className="mb-5">
                  <div className="mb-3 text-sm font-semibold text-white">Query result</div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    {coverageResult.slice(0, 2).map((record) => (
                      <CoverageCard key={record.item_id} record={record} />
                    ))}
                  </div>
                </div>
              )}

              <div className="grid gap-3 lg:grid-cols-2">
                {allCoverage.slice(0, 6).map((record) => (
                  <CoverageCard key={record.item_id} record={record} />
                ))}
              </div>
            </Panel>

            <Panel
              eyebrow="Repair Guide"
              title="Generate a diagnostic workflow from symptoms and scan evidence."
              action={
                <Button onClick={runGuide} disabled={busy === 'guide'} className="rounded-lg bg-emerald-300 text-slate-950 hover:bg-emerald-200">
                  {busy === 'guide' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                  Generate
                </Button>
              }
            >
              <RepairGuideView guide={guide} />
            </Panel>

            <Panel
              eyebrow="Video Reference"
              title="Convert a repair video idea into an independent playbook."
              action={<Film className="h-5 w-5 text-cyan-300" />}
            >
              <div className="mb-5 grid gap-3 md:grid-cols-2">
                <input
                  value={videoTitle}
                  onChange={(event) => setVideoTitle(event.target.value)}
                  placeholder="Video title"
                  className="rounded-lg border border-white/10 bg-[#050b13] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
                />
                <input
                  value={videoChannel}
                  onChange={(event) => setVideoChannel(event.target.value)}
                  placeholder="Channel"
                  className="rounded-lg border border-white/10 bg-[#050b13] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
                />
                <input
                  value={videoUrl}
                  onChange={(event) => setVideoUrl(event.target.value)}
                  placeholder="Video URL"
                  className="rounded-lg border border-white/10 bg-[#050b13] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60 md:col-span-2"
                />
                <textarea
                  value={videoActions}
                  onChange={(event) => setVideoActions(event.target.value)}
                  className="min-h-24 resize-none rounded-lg border border-white/10 bg-[#050b13] px-3 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/60 md:col-span-2"
                />
                <Button onClick={runVideoPlaybook} disabled={busy === 'video'} className="rounded-lg bg-white text-slate-950 hover:bg-slate-100 md:col-span-2">
                  {busy === 'video' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Wrench className="mr-2 h-4 w-4" />}
                  Generate video playbook
                </Button>
              </div>
              <VideoPlaybookView playbook={playbook} />
            </Panel>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
