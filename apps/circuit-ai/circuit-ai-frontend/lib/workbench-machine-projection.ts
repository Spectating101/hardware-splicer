'use client';

import {
  constructorCandidateMap,
  constructorResourceMap,
  constructorResources,
  type ConstructorResource,
} from '@/lib/workbench-constructor-demo';
import type {
  ConstructorCandidateId,
  PlannerCandidateProjection,
  PlannerSourceState,
} from '@/lib/machine-workbench-store';

export type ProjectionDisposition = 'retained' | 'substituted' | 'held' | 'gap' | 'implicit' | 'suppressed';
export type ProjectionGeometryState = 'fixture' | 'working_projection' | 'held_volume' | 'gap_envelope';
export type MachinePartVariant =
  | 'donor-mainboard'
  | 'documented-mainboard'
  | 'controlled-display'
  | 'raw-display'
  | 'documented-display'
  | 'donor-keyboard'
  | 'known-battery'
  | 'pd-module'
  | 'donor-cooling'
  | 'generated-shell'
  | 'native-nvme'
  | 'usb-breakout'
  | 'gap';

export type MachinePartProjection = {
  entityId: string;
  resourceId: string | null;
  resourceName: string;
  disposition: ProjectionDisposition;
  geometryState: ProjectionGeometryState;
  variant: MachinePartVariant;
  visible: boolean;
  opacity: number;
  sizeScale: [number, number, number];
  positionOffset: [number, number, number];
  label: string;
  note: string;
};

export type CandidateMachineProjection = {
  candidateId: ConstructorCandidateId;
  source: PlannerSourceState;
  selectedResourceIds: string[];
  parts: Record<string, MachinePartProjection>;
  substitutedCount: number;
  heldCount: number;
  gapCount: number;
  suppressedCount: number;
};

const ROLE_ENTITY: Record<string, string> = {
  compute: 'cmp-mainboard',
  display: 'cmp-display',
  input: 'cmp-keyboard',
  power: 'cmp-battery',
  thermal: 'cmp-cooling',
  structure: 'cmp-enclosure',
};

const PREFERENCE: Record<ConstructorCandidateId, string[]> = {
  balanced: [
    'res-mainboard-donor',
    'res-mainboard-documented',
    'res-display-controlled',
    'res-display-documented',
    'res-display-raw',
    'res-keyboard-donor',
    'res-battery-new',
    'res-pd-module',
    'res-cooling-donor',
    'res-shell-generated',
  ],
  'max-reuse': [
    'res-mainboard-donor',
    'res-mainboard-documented',
    'res-display-raw',
    'res-display-controlled',
    'res-display-documented',
    'res-keyboard-donor',
    'res-battery-old',
    'res-battery-new',
    'res-pd-module',
    'res-cooling-donor',
    'res-shell-generated',
  ],
  'low-risk': [
    'res-mainboard-documented',
    'res-mainboard-donor',
    'res-display-documented',
    'res-display-controlled',
    'res-display-raw',
    'res-keyboard-donor',
    'res-battery-new',
    'res-pd-module',
    'res-cooling-donor',
    'res-shell-generated',
  ],
};

function normalizeId(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function selectedSet(
  candidateId: ConstructorCandidateId,
  source: PlannerSourceState,
  planner?: PlannerCandidateProjection,
) {
  if (source === 'live' && planner) return new Set(planner.selectedResourceIds.map(normalizeId));
  const candidate = constructorCandidateMap.get(candidateId) ?? constructorCandidateMap.get('balanced');
  return new Set((candidate?.resourceIds ?? []).map(normalizeId));
}

function selectedResourceForEntity(
  candidateId: ConstructorCandidateId,
  entityId: string,
  selected: Set<string>,
) {
  const candidates = constructorResources.filter((resource) => resource.mappedEntityId === entityId && selected.has(normalizeId(resource.id)));
  if (!candidates.length) return null;
  const order = PREFERENCE[candidateId];
  return [...candidates].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))[0] ?? candidates[0];
}

function selectedPowerPath(selected: Set<string>) {
  return selected.has('res-pd-module') ? constructorResourceMap.get('res-pd-module') ?? null : null;
}

function baseProjection(entityId: string): MachinePartProjection {
  return {
    entityId,
    resourceId: null,
    resourceName: 'No selected resource',
    disposition: 'gap',
    geometryState: 'gap_envelope',
    variant: 'gap',
    visible: true,
    opacity: 0.22,
    sizeScale: [1, 1, 1],
    positionOffset: [0, 0, 0],
    label: 'RESOURCE GAP',
    note: 'No selected resource currently backs this spatial role.',
  };
}

function projectionForResource(entityId: string, resource: ConstructorResource): MachinePartProjection {
  const projection = baseProjection(entityId);
  projection.resourceId = resource.id;
  projection.resourceName = resource.name;
  projection.opacity = 1;
  projection.geometryState = 'fixture';
  projection.disposition = resource.kind === 'procurable' || resource.kind === 'designed' ? 'substituted' : 'retained';
  projection.label = projection.disposition === 'substituted' ? 'WORKING SUBSTITUTE' : 'RETAINED RESOURCE';
  projection.note = resource.note;

  if (resource.id === 'res-mainboard-donor') projection.variant = 'donor-mainboard';
  if (resource.id === 'res-mainboard-documented') {
    projection.variant = 'documented-mainboard';
    projection.geometryState = 'working_projection';
    projection.sizeScale = [0.86, 1.18, 0.9];
    projection.positionOffset = [0.22, 0.04, -0.08];
  }
  if (resource.id === 'res-display-controlled') projection.variant = 'controlled-display';
  if (resource.id === 'res-display-raw') {
    projection.variant = 'raw-display';
    projection.disposition = 'held';
    projection.geometryState = 'held_volume';
    projection.opacity = 0.34;
    projection.sizeScale = [0.94, 0.92, 0.72];
    projection.label = 'HELD · MEASURE FIRST';
  }
  if (resource.id === 'res-display-documented') {
    projection.variant = 'documented-display';
    projection.geometryState = 'working_projection';
    projection.sizeScale = [0.98, 0.98, 1.42];
    projection.positionOffset = [0, 0.06, 0.04];
  }
  if (resource.id === 'res-keyboard-donor') projection.variant = 'donor-keyboard';
  if (resource.id === 'res-battery-old') {
    projection.variant = 'gap';
    projection.disposition = 'held';
    projection.geometryState = 'held_volume';
    projection.opacity = 0.14;
    projection.label = 'BLOCKED BATTERY';
  }
  if (resource.id === 'res-battery-new') {
    projection.variant = 'known-battery';
    projection.geometryState = 'working_projection';
    projection.sizeScale = [0.92, 1.08, 0.9];
  }
  if (resource.id === 'res-pd-module') {
    projection.variant = 'pd-module';
    projection.geometryState = 'working_projection';
  }
  if (resource.id === 'res-cooling-donor') projection.variant = 'donor-cooling';
  if (resource.id === 'res-shell-generated') {
    projection.variant = 'generated-shell';
    projection.geometryState = 'working_projection';
  }
  return projection;
}

function implicitProjection(entityId: string, variant: MachinePartVariant, label: string): MachinePartProjection {
  return {
    ...baseProjection(entityId),
    resourceName: label,
    disposition: 'implicit',
    geometryState: 'fixture',
    variant,
    visible: true,
    opacity: 1,
    label: 'IMPLICIT NATIVE PATH',
    note: 'Represented by the current architecture fixture; not separately selected by resource_strategy.v1.',
  };
}

export function buildCandidateMachineProjection(
  candidateId: ConstructorCandidateId,
  source: PlannerSourceState,
  planner?: PlannerCandidateProjection,
): CandidateMachineProjection {
  const selected = selectedSet(candidateId, source, planner);
  const parts: Record<string, MachinePartProjection> = {};

  for (const entityId of Object.values(ROLE_ENTITY)) {
    const resource = selectedResourceForEntity(candidateId, entityId, selected);
    parts[entityId] = resource ? projectionForResource(entityId, resource) : baseProjection(entityId);
  }

  const pd = selectedPowerPath(selected);
  parts['cmp-pd'] = pd ? projectionForResource('cmp-pd', pd) : baseProjection('cmp-pd');
  parts['cmp-nvme'] = implicitProjection('cmp-nvme', 'native-nvme', 'Native NVMe path');
  parts['cmp-hub'] = implicitProjection('cmp-hub', 'usb-breakout', 'USB breakout');

  if (candidateId === 'max-reuse' && parts['cmp-enclosure']) {
    parts['cmp-enclosure'].sizeScale = [1.07, 1, 1.05];
    parts['cmp-enclosure'].positionOffset = [0, 0, 0.1];
  }
  if (candidateId === 'low-risk' && parts['cmp-enclosure']) {
    parts['cmp-enclosure'].sizeScale = [0.96, 1, 0.95];
    parts['cmp-enclosure'].positionOffset = [0, 0, -0.08];
  }
  if (candidateId === 'low-risk' && parts['cmp-hub']) {
    parts['cmp-hub'] = {
      ...parts['cmp-hub'],
      disposition: 'suppressed',
      visible: false,
      label: 'SUPPRESSED',
      note: 'The documented compute candidate is projected to satisfy the minimum external-I/O requirement without a separate breakout block.',
    };
  }

  const rows = Object.values(parts);
  return {
    candidateId,
    source,
    selectedResourceIds: [...selected],
    parts,
    substitutedCount: rows.filter((row) => row.disposition === 'substituted').length,
    heldCount: rows.filter((row) => row.disposition === 'held').length,
    gapCount: rows.filter((row) => row.disposition === 'gap').length,
    suppressedCount: rows.filter((row) => row.disposition === 'suppressed').length,
  };
}
