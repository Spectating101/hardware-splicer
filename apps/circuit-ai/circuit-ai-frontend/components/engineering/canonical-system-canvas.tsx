'use client';

import { useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Box,
  CircuitBoard,
  Cpu,
  FileSearch,
  Gauge,
  PlugZap,
  ShieldAlert,
  ShieldCheck,
  Waypoints,
  Wrench,
  Zap,
} from 'lucide-react';

type JsonRecord = Record<string, unknown>;

export type CanonicalVisualObject = {
  id: string;
  label: string;
  kind: string;
  domain: string;
  description: string;
  status: 'supported' | 'proposed' | 'blocked' | 'unknown';
  evidenceIds: string[];
  sourceIds: string[];
  blockers: string[];
  proposalIds: string[];
  authority: 'none';
};

type CanvasProps = {
  snapshot: JsonRecord | null;
  session: JsonRecord | null;
  revision: number | null;
  selectedObjectId?: string;
  onSelectObject?: (object: CanonicalVisualObject) => void;
};

type VisualNodeData = CanonicalVisualObject & {
  selected?: boolean;
};

type SystemGraph = {
  objects: CanonicalVisualObject[];
  edges: Edge[];
};

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((row) => String(row || '')).filter(Boolean)
    : [];
}

function text(value: unknown, fallback = '') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function statusFrom(value: unknown): CanonicalVisualObject['status'] {
  const normalized = text(value).toLowerCase();
  if (['supported', 'verified', 'pass', 'complete'].includes(normalized)) return 'supported';
  if (['proposed', 'candidate', 'draft'].includes(normalized)) return 'proposed';
  if (['blocked', 'failed', 'error', 'conflict'].includes(normalized)) return 'blocked';
  return 'unknown';
}

function objectFromRaw(row: JsonRecord): CanonicalVisualObject {
  return {
    id: text(row.object_id || row.id || row.node_id),
    label: text(row.label || row.title || row.name, 'Unnamed object'),
    kind: text(row.kind || row.type, 'module'),
    domain: text(row.domain, 'system'),
    description: text(row.description || row.summary),
    status: statusFrom(row.status),
    evidenceIds: strings(row.evidence_ids || row.evidenceIds),
    sourceIds: strings(row.source_ids || row.sourceIds),
    blockers: strings(row.blockers),
    proposalIds: strings(row.proposal_ids || row.proposalIds),
    authority: 'none',
  };
}

function fixtureGraph(snapshot: JsonRecord, session: JsonRecord | null): SystemGraph {
  const actions = rows(session?.actions);
  const candidates = rows(session?.architecture_candidates);
  const failedAction = actions.find((action) => text(action.status) === 'failed');
  const hasProtectedCandidate = candidates.some((candidate) => (
    text(candidate.id).includes('protected') || text(candidate.title).toLowerCase().includes('translated')
  ));
  const repairCandidate = candidates.find((candidate) => (
    text(candidate.id).includes('protected') || text(candidate.title).toLowerCase().includes('translated')
  ));
  const failureMessage = text(
    record(record(failedAction?.tool_result).error).message
      || record(record(failedAction?.tool_result).summary).message,
    'The 1.8 V and 3.3 V interface is not proven safe.',
  );

  const objects: CanonicalVisualObject[] = [
    {
      id: 'fixture-controller',
      label: 'USB fixture controller',
      kind: 'controller',
      domain: '3.3 V control',
      description: 'Stimulus, sequencing, and host communication.',
      status: 'supported',
      evidenceIds: ['fixture-controller-manual-r1'],
      sourceIds: ['fixture-controller-manual-r1'],
      blockers: ['Reset-time pull-up behavior crosses the DUT boundary.'],
      proposalIds: [],
      authority: 'none',
    },
    {
      id: 'level-translation',
      label: hasProtectedCandidate ? 'Default-off translator' : 'Unresolved translation',
      kind: 'interface',
      domain: '3.3 V ↔ 1.8 V',
      description: hasProtectedCandidate
        ? text(repairCandidate?.summary, 'Proposed powered-off-safe translation and explicit enable sequencing.')
        : 'Required protection between the controller and DUT digital domains.',
      status: hasProtectedCandidate ? 'proposed' : 'blocked',
      evidenceIds: ['dut-datasheet-r1', 'fixture-controller-manual-r1'],
      sourceIds: ['dut-datasheet-r1', 'fixture-controller-manual-r1'],
      blockers: hasProtectedCandidate
        ? ['Exact translator part and powered-off behavior remain unverified.']
        : [failureMessage],
      proposalIds: repairCandidate ? [text(repairCandidate.id)] : [],
      authority: 'none',
    },
    {
      id: 'dut-socket',
      label: '32-pin DUT socket',
      kind: 'socket',
      domain: '1.8 V DUT',
      description: 'Replaceable DUT interface with pin-1 orientation and keepout constraints.',
      status: 'proposed',
      evidenceIds: ['dut-pin-map-r1', 'socket-drawing-r1'],
      sourceIds: ['dut-pin-map-r1', 'socket-drawing-r1'],
      blockers: ['Reserved-pin no-connect check has not passed.'],
      proposalIds: [],
      authority: 'none',
    },
    {
      id: 'dut-rail',
      label: 'Current-limited 1.8 V rail',
      kind: 'power',
      domain: 'DUT power',
      description: 'Programmable supply path with startup and steady-state limits.',
      status: 'proposed',
      evidenceIds: ['dut-datasheet-r1', 'test-limits-r1', 'lab-supply-procedure-r1'],
      sourceIds: ['dut-datasheet-r1', 'test-limits-r1', 'lab-supply-procedure-r1'],
      blockers: ['No measured startup-current evidence exists.'],
      proposalIds: [],
      authority: 'none',
    },
    {
      id: 'current-monitor',
      label: 'High-side current monitor',
      kind: 'measurement',
      domain: 'measurement',
      description: 'Captures startup and steady-state DUT current.',
      status: 'proposed',
      evidenceIds: ['test-limits-r1'],
      sourceIds: ['test-limits-r1'],
      blockers: ['Measurement chain has no physical calibration evidence.'],
      proposalIds: [],
      authority: 'none',
    },
    {
      id: 'test-equipment',
      label: 'Bench equipment interface',
      kind: 'equipment',
      domain: 'laboratory',
      description: 'Protected analog observation and keyed external test connection.',
      status: 'unknown',
      evidenceIds: [],
      sourceIds: [],
      blockers: ['Instrument identity and capture procedure are not registered.'],
      proposalIds: [],
      authority: 'none',
    },
  ];

  const edges: Edge[] = [
    {
      id: 'edge-controller-translation',
      source: 'fixture-controller',
      target: 'level-translation',
      label: '3.3 V GPIO',
      animated: !hasProtectedCandidate,
      style: { stroke: hasProtectedCandidate ? '#a78bfa' : '#fb7185', strokeWidth: 2.5 },
      labelStyle: { fill: '#cbd5e1', fontSize: 11 },
    },
    {
      id: 'edge-translation-dut',
      source: 'level-translation',
      target: 'dut-socket',
      label: '1.8 V digital',
      style: { stroke: hasProtectedCandidate ? '#22d3ee' : '#fb7185', strokeWidth: 2.5 },
      labelStyle: { fill: '#cbd5e1', fontSize: 11 },
    },
    {
      id: 'edge-rail-monitor',
      source: 'dut-rail',
      target: 'current-monitor',
      label: 'limited rail',
      style: { stroke: '#fbbf24', strokeWidth: 2 },
      labelStyle: { fill: '#cbd5e1', fontSize: 11 },
    },
    {
      id: 'edge-monitor-dut',
      source: 'current-monitor',
      target: 'dut-socket',
      label: '1.8 V sensed',
      style: { stroke: '#fbbf24', strokeWidth: 2 },
      labelStyle: { fill: '#cbd5e1', fontSize: 11 },
    },
    {
      id: 'edge-dut-equipment',
      source: 'dut-socket',
      target: 'test-equipment',
      label: 'analog observation',
      style: { stroke: '#94a3b8', strokeWidth: 2 },
      labelStyle: { fill: '#cbd5e1', fontSize: 11 },
    },
  ];

  return { objects, edges };
}

function genericGraph(snapshot: JsonRecord, session: JsonRecord | null): SystemGraph {
  const sources = rows(snapshot.engineeringSources);
  const candidates = rows(session?.architecture_candidates);
  const actions = rows(session?.actions);
  const failed = actions.filter((action) => text(action.status) === 'failed');
  const projectId = text(snapshot.projectId || snapshot.project_id, 'project');

  const objects: CanonicalVisualObject[] = [
    {
      id: 'project-system',
      label: text(snapshot.name || snapshot.projectName, 'Project system'),
      kind: 'system',
      domain: text(snapshot.mode, 'engineering'),
      description: text(snapshot.mission, 'Canonical project boundary.'),
      status: candidates.length ? 'proposed' : 'unknown',
      evidenceIds: sources.map((source) => text(source.source_id)).filter(Boolean),
      sourceIds: sources.map((source) => text(source.source_id)).filter(Boolean),
      blockers: failed.map((action) => text(record(record(action.tool_result).error).message)).filter(Boolean),
      proposalIds: candidates.map((candidate) => text(candidate.id)).filter(Boolean),
      authority: 'none',
    },
    {
      id: 'evidence-boundary',
      label: `${sources.length} registered sources`,
      kind: 'evidence',
      domain: 'evidence',
      description: 'Declared source identities and parser-derived records.',
      status: sources.length ? 'supported' : 'unknown',
      evidenceIds: sources.map((source) => text(source.source_id)).filter(Boolean),
      sourceIds: sources.map((source) => text(source.source_id)).filter(Boolean),
      blockers: sources.length ? [] : ['No engineering sources are registered.'],
      proposalIds: [],
      authority: 'none',
    },
    {
      id: 'candidate-boundary',
      label: candidates.length ? text(candidates.at(-1)?.title, 'Latest candidate') : 'No candidate yet',
      kind: 'candidate',
      domain: 'proposal',
      description: candidates.length
        ? text(candidates.at(-1)?.summary, 'Reviewable architecture candidate.')
        : 'Generate a candidate from the current revision and evidence boundary.',
      status: candidates.length ? 'proposed' : 'unknown',
      evidenceIds: [],
      sourceIds: strings(candidates.at(-1)?.source_ids),
      blockers: failed.length ? [`${failed.length} persisted preview failure${failed.length === 1 ? '' : 's'}.`] : [],
      proposalIds: candidates.map((candidate) => text(candidate.id)).filter(Boolean),
      authority: 'none',
    },
  ];

  return {
    objects,
    edges: [
      { id: `${projectId}-evidence`, source: 'evidence-boundary', target: 'project-system', label: 'grounds', style: { stroke: '#22d3ee', strokeWidth: 2 } },
      { id: `${projectId}-candidate`, source: 'project-system', target: 'candidate-boundary', label: 'proposes', style: { stroke: '#c084fc', strokeWidth: 2 } },
    ],
  };
}

export function deriveCanonicalSystemGraph(snapshot: JsonRecord | null, session: JsonRecord | null): SystemGraph {
  if (!snapshot) return { objects: [], edges: [] };
  const storedGraph = record(snapshot.engineeringSystemGraph);
  const storedNodes = rows(storedGraph.nodes);
  if (storedNodes.length) {
    return {
      objects: storedNodes.map(objectFromRaw).filter((object) => object.id),
      edges: rows(storedGraph.edges).map((row, index): Edge => ({
        id: text(row.id, `system-edge-${index}`),
        source: text(row.source),
        target: text(row.target),
        label: text(row.label),
        animated: Boolean(row.animated),
      })).filter((edge) => edge.source && edge.target),
    };
  }

  const sourceIds = new Set(rows(snapshot.engineeringSources).map((source) => text(source.source_id)));
  if (sourceIds.has('dut-datasheet-r1') && sourceIds.has('fixture-controller-manual-r1')) {
    return fixtureGraph(snapshot, session);
  }
  return genericGraph(snapshot, session);
}

function iconFor(kind: string) {
  if (kind === 'controller') return Cpu;
  if (kind === 'interface') return PlugZap;
  if (kind === 'socket') return CircuitBoard;
  if (kind === 'power') return Zap;
  if (kind === 'measurement') return Gauge;
  if (kind === 'equipment') return Wrench;
  if (kind === 'evidence') return FileSearch;
  if (kind === 'candidate') return Waypoints;
  if (kind === 'system') return Box;
  return CircuitBoard;
}

function statusClasses(status: CanonicalVisualObject['status']) {
  if (status === 'supported') return 'border-emerald-300/30 bg-emerald-300/10 text-emerald-100';
  if (status === 'proposed') return 'border-violet-300/30 bg-violet-300/10 text-violet-100';
  if (status === 'blocked') return 'border-rose-300/35 bg-rose-300/10 text-rose-100';
  return 'border-white/12 bg-slate-900/90 text-slate-200';
}

function CanonicalNode({ data: rawData }: NodeProps) {
  const data = rawData as unknown as VisualNodeData;
  const Icon = iconFor(data.kind);
  return (
    <div className={`min-w-[220px] rounded-2xl border px-4 py-3 shadow-[0_18px_50px_rgba(2,6,23,0.35)] backdrop-blur ${statusClasses(data.status)} ${data.selected ? 'ring-2 ring-cyan-200/80' : ''}`}>
      <Handle type="target" position={Position.Left} className="!h-2.5 !w-2.5 !border-2 !border-slate-950 !bg-cyan-300" />
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-white/10 bg-black/20 p-2"><Icon className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70">{data.domain}</div>
          <div className="mt-1 text-sm font-semibold text-white">{data.label}</div>
          <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-300">{data.description}</div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em]">
        <span className="rounded-full border border-white/10 bg-black/15 px-2 py-1">{data.status}</span>
        <span className="rounded-full border border-white/10 bg-black/15 px-2 py-1">{data.evidenceIds.length} evidence</span>
        {data.blockers.length ? <span className="rounded-full border border-rose-200/20 bg-rose-300/10 px-2 py-1">{data.blockers.length} blockers</span> : null}
        {data.proposalIds.length ? <span className="rounded-full border border-violet-200/20 bg-violet-300/10 px-2 py-1">proposal</span> : null}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2.5 !w-2.5 !border-2 !border-slate-950 !bg-cyan-300" />
    </div>
  );
}

const nodeTypes: NodeTypes = { canonical: CanonicalNode };

const fixturePositions: Record<string, { x: number; y: number }> = {
  'fixture-controller': { x: 20, y: 80 },
  'level-translation': { x: 350, y: 80 },
  'dut-socket': { x: 680, y: 80 },
  'dut-rail': { x: 20, y: 330 },
  'current-monitor': { x: 350, y: 330 },
  'test-equipment': { x: 680, y: 330 },
  'evidence-boundary': { x: 20, y: 180 },
  'project-system': { x: 350, y: 180 },
  'candidate-boundary': { x: 680, y: 180 },
};

export function CanonicalSystemCanvas({
  snapshot,
  session,
  revision,
  selectedObjectId,
  onSelectObject,
}: CanvasProps) {
  const graph = useMemo(() => deriveCanonicalSystemGraph(snapshot, session), [snapshot, session]);
  const objectMap = useMemo(() => new Map(graph.objects.map((object) => [object.id, object])), [graph.objects]);
  const nodes = useMemo(() => graph.objects.map((object, index): Node => ({
    id: object.id,
    type: 'canonical',
    position: fixturePositions[object.id] || { x: 40 + (index % 3) * 330, y: 70 + Math.floor(index / 3) * 240 },
    data: { ...object, selected: selectedObjectId === object.id },
    draggable: false,
    selectable: true,
  })), [graph.objects, selectedObjectId]);

  if (!snapshot) {
    return (
      <div className="flex h-full min-h-[520px] items-center justify-center rounded-3xl border border-dashed border-white/10 bg-[#050b14] p-10 text-center">
        <div>
          <Waypoints className="mx-auto h-10 w-10 text-slate-600" />
          <div className="mt-4 text-sm font-semibold text-white">Load a project to open its system canvas</div>
          <div className="mt-2 max-w-md text-xs leading-5 text-slate-500">The canvas projects canonical objects, interfaces, evidence, failures, proposals, and authority without replacing native engineering tools.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-[600px] overflow-hidden rounded-3xl border border-white/10 bg-[#050b14]">
      <div className="pointer-events-none absolute left-4 top-4 z-20 flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-[0.14em]">
        <span className="rounded-full border border-cyan-300/20 bg-[#07111f]/90 px-3 py-1.5 text-cyan-100">System canvas</span>
        <span className="rounded-full border border-white/10 bg-[#07111f]/90 px-3 py-1.5 text-slate-300">Revision {revision ?? '—'}</span>
        <span className="rounded-full border border-emerald-300/20 bg-[#07111f]/90 px-3 py-1.5 text-emerald-100">Authority effect none</span>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={graph.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesConnectable={false}
        elementsSelectable
        deleteKeyCode={null}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          const selected = objectMap.get(node.id);
          if (selected) onSelectObject?.(selected);
        }}
        style={{ background: 'radial-gradient(circle at 50% 45%, rgba(14,116,144,0.08), transparent 40%), #050b14' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="rgba(255,255,255,0.07)" />
        <Controls showInteractive={false} style={{ background: '#07111f', border: '1px solid rgba(255,255,255,0.12)' }} />
        <MiniMap
          style={{ background: '#07111f', border: '1px solid rgba(255,255,255,0.1)' }}
          nodeColor={(node) => {
            const object = objectMap.get(node.id);
            if (object?.status === 'blocked') return '#fb7185';
            if (object?.status === 'proposed') return '#a78bfa';
            if (object?.status === 'supported') return '#34d399';
            return '#64748b';
          }}
          maskColor="rgba(2,6,23,0.72)"
        />
      </ReactFlow>
      <div className="pointer-events-none absolute bottom-4 left-4 z-20 flex items-center gap-2 rounded-2xl border border-white/10 bg-[#07111f]/90 px-3 py-2 text-[10px] text-slate-400">
        {graph.objects.some((object) => object.status === 'blocked') ? <ShieldAlert className="h-3.5 w-3.5 text-rose-300" /> : <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />}
        Select an object to inspect evidence, blockers, proposal lineage, and cross-view identity.
      </div>
    </div>
  );
}
