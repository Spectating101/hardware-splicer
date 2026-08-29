'use client';

import { useEffect } from 'react';
import {
  constructorResources,
  constructorTarget,
} from '@/lib/workbench-constructor-demo';
import {
  useMachineWorkbenchStore,
  type ConstructorCandidateId,
  type PlannerCandidateProjection,
} from '@/lib/machine-workbench-store';

const MODES: Array<{ id: ConstructorCandidateId; strategyMode: PlannerCandidateProjection['strategyMode'] }> = [
  { id: 'balanced', strategyMode: 'hybrid' },
  { id: 'max-reuse', strategyMode: 'constrained' },
  { id: 'low-risk', strategyMode: 'open_procurement' },
];

const REQUIRED_CAPABILITIES = [
  'x86_compute',
  'display_or_ui',
  'switch_or_button',
  'storage',
  'network_interface',
  'power',
  'fan_or_pump',
  'enclosure_candidate',
];

const CAPABILITY_MAP: Record<string, string[]> = {
  'res-mainboard-donor': ['x86_compute', 'storage', 'network_interface', 'connector'],
  'res-mainboard-documented': ['x86_compute', 'storage', 'network_interface', 'connector'],
  'res-display-controlled': ['display_or_ui', 'connector'],
  'res-display-raw': ['display_or_ui'],
  'res-display-documented': ['display_or_ui', 'connector'],
  'res-keyboard-donor': ['switch_or_button', 'controller', 'connector'],
  'res-battery-old': ['power'],
  'res-battery-new': ['power'],
  'res-pd-module': ['power', 'connector', 'protection'],
  'res-cooling-donor': ['fan_or_pump'],
  'res-shell-generated': ['enclosure_candidate'],
};

function confidenceForAuthority(authority: string) {
  if (authority === 'verified') return 0.94;
  if (authority === 'partial') return 0.66;
  if (authority === 'proposed') return 0.58;
  if (authority === 'blocked') return 0.18;
  return 0.35;
}

function evidenceStatus(authority: string) {
  if (authority === 'verified') return 'verified';
  if (authority === 'blocked') return 'failed_evidence';
  if (authority === 'partial') return 'needs_evidence';
  return 'candidate';
}

function plannerRow(resource: (typeof constructorResources)[number]) {
  return {
    resource_id: resource.id,
    name: resource.name,
    resource_kind: resource.kind,
    capabilities: CAPABILITY_MAP[resource.id] ?? resource.capabilities,
    confidence: confidenceForAuthority(resource.authority),
    evidence_status: evidenceStatus(resource.authority),
    cost_usd: resource.costNtd > 0 ? Number((resource.costNtd / 32).toFixed(2)) : 0,
    replacement_value_usd: resource.costNtd > 0 ? Number((resource.costNtd / 32).toFixed(2)) : undefined,
    notes: `${resource.note}${resource.authority === 'blocked' ? ' Blocked failed evidence; do not select.' : ''}`,
  };
}

function buildPayload(strategyMode: PlannerCandidateProjection['strategyMode']) {
  const available = constructorResources.filter((resource) => resource.kind !== 'procurable').map(plannerRow);
  const procurable = constructorResources.filter((resource) => resource.kind === 'procurable').map(plannerRow);
  return {
    goal: constructorTarget.prompt,
    strategy_mode: strategyMode,
    required_capabilities: REQUIRED_CAPABILITIES,
    constraints: {
      budget_usd: 375,
      safety_level: 'low_voltage_only',
      environment: 'portable_workstation_prototype',
      cost_priority: strategyMode === 'constrained' ? 'high' : 'balanced',
      time_priority: strategyMode === 'open_procurement' ? 'high' : 'balanced',
    },
    available_resources: available,
    procurable_catalog: procurable,
    use_reference_catalog: false,
    derive_salvage_plan: false,
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeId(value: unknown) {
  return String(value ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function projectionFromResponse(payload: unknown, expectedMode: PlannerCandidateProjection['strategyMode']): PlannerCandidateProjection {
  const envelope = asRecord(payload);
  const strategy = asRecord(envelope.resource_strategy);
  if (strategy.schema_version !== 'resource_strategy.v1') throw new Error('resource_strategy.v1 response required');
  const readiness = asRecord(strategy.build_readiness);
  const coverage = asRecord(strategy.coverage);
  const procurement = asRecord(strategy.procurement_plan);
  const selectedResources = asArray(strategy.selected_resources).map(asRecord);
  const blockedResources = asArray(strategy.blocked_resources);
  const selectedIds = selectedResources.map((resource) => normalizeId(resource.resource_id || resource.name)).filter(Boolean);
  const missing = asArray(coverage.missing_capabilities).map((value) => String(value));
  return {
    strategyMode: String(strategy.strategy_mode || expectedMode) as PlannerCandidateProjection['strategyMode'],
    readinessStatus: String(readiness.status || 'unknown'),
    readinessReason: String(readiness.reason || 'No readiness reason returned.'),
    coverageScore: asNumber(coverage.coverage_score),
    openGateCount: asNumber(readiness.open_gate_count),
    blockedResourceCount: blockedResources.length,
    selectedResourceIds: selectedIds,
    missingCapabilities: missing,
    procurementItemCount: asArray(procurement.items).length,
    procurementCostUsd: asNumber(procurement.estimated_cost_usd),
  };
}

async function fetchProjection(strategyMode: PlannerCandidateProjection['strategyMode'], signal: AbortSignal) {
  const response = await fetch('/api/proxy/resource/strategy', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(buildPayload(strategyMode)),
    cache: 'no-store',
    signal,
  });
  if (!response.ok) throw new Error(`resource planner HTTP ${response.status}`);
  return projectionFromResponse(await response.json(), strategyMode);
}

export function ConstructorPlannerBridge() {
  const setPlannerState = useMachineWorkbenchStore((state) => state.setPlannerState);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 2200);
    let active = true;

    setPlannerState('loading', 'Checking Hardware-Splicer resource_strategy.v1…', {});
    Promise.all(MODES.map(async ({ id, strategyMode }) => [id, await fetchProjection(strategyMode, controller.signal)] as const))
      .then((rows) => {
        if (!active) return;
        const projections = Object.fromEntries(rows) as Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>>;
        setPlannerState('live', 'Live resource_strategy.v1 projections are driving resource coverage and candidate gates.', projections);
      })
      .catch((error: unknown) => {
        if (!active) return;
        const reason = error instanceof Error && error.name !== 'AbortError' ? error.message : 'backend unavailable';
        setPlannerState('fixture', `Planner unavailable (${reason}); using explicit constructor fixture without promoting it to live planning.`, {});
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [setPlannerState]);

  return null;
}
