'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type ProjectSourceDescriptor = {
  sourceId: string;
  contentHash: string;
  originalFilename?: string;
  parserRoute?: string;
};

export type ProjectStepBindingDescriptor = {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
};

export type RegisteredWorkbenchStepSource = ProjectStepBindingDescriptor & {
  projectId: string;
  revision: number;
  sourceMaterialization: 'registered_project';
};

type WorkbenchProjectStatus = 'unbound' | 'loading' | 'bound' | 'error';

type WorkbenchProjectSourceState = {
  projectId: string | null;
  revision: number | null;
  status: WorkbenchProjectStatus;
  message: string;
  projectSources: ProjectSourceDescriptor[];
  projectBindings: ProjectStepBindingDescriptor[];
  registeredByResource: Record<string, RegisteredWorkbenchStepSource>;
  beginProjectLoad: (projectId: string) => void;
  bindProject: (
    projectId: string,
    revision: number,
    sources: ProjectSourceDescriptor[],
    bindings: ProjectStepBindingDescriptor[],
  ) => void;
  failProjectLoad: (projectId: string, message: string) => void;
  clearProject: () => void;
  setProjectRevision: (projectId: string, revision: number) => void;
  setRegisteredSource: (source: RegisteredWorkbenchStepSource) => void;
  clearRegisteredSource: (candidateId: ConstructorCandidateId, resourceId: string) => void;
};

function key(candidateId: ConstructorCandidateId, resourceId: string) {
  return `${candidateId}::${resourceId}`;
}

function sourceIdentity(sourceId: string, contentHash: string) {
  return `${sourceId}::${contentHash}`;
}

function rehydratedBindings(
  projectId: string,
  revision: number,
  sources: ProjectSourceDescriptor[],
  bindings: ProjectStepBindingDescriptor[],
) {
  const registered: Record<string, RegisteredWorkbenchStepSource> = {};
  const registeredStepSources = new Set(
    sources
      .filter((source) => source.parserRoute === 'step_geometry')
      .map((source) => sourceIdentity(source.sourceId, source.contentHash)),
  );
  for (const binding of bindings) {
    if (!registeredStepSources.has(sourceIdentity(binding.sourceId, binding.contentHash))) continue;
    registered[key(binding.candidateId, binding.resourceId)] = {
      ...binding,
      projectId,
      revision,
      sourceMaterialization: 'registered_project',
    };
  }
  return registered;
}

function projectMessage(
  projectId: string,
  revision: number,
  sources: ProjectSourceDescriptor[],
  bindingCount: number,
) {
  return `Project ${projectId} · revision ${revision} · ${sources.length} registered source${sources.length === 1 ? '' : 's'} · ${bindingCount} workbench binding${bindingCount === 1 ? '' : 's'}`;
}

export const useWorkbenchProjectSourceStore = create<WorkbenchProjectSourceState>((set) => ({
  projectId: null,
  revision: null,
  status: 'unbound',
  message: 'Session-only workbench. Add ?project=<id> to bind durable project sources.',
  projectSources: [],
  projectBindings: [],
  registeredByResource: {},

  beginProjectLoad: (projectId) => set({
    projectId,
    revision: null,
    status: 'loading',
    message: `Loading project ${projectId}…`,
    projectSources: [],
    projectBindings: [],
    registeredByResource: {},
  }),

  bindProject: (projectId, revision, sources, bindings) => {
    const registeredByResource = rehydratedBindings(projectId, revision, sources, bindings);
    set({
      projectId,
      revision,
      status: 'bound',
      message: projectMessage(projectId, revision, sources, Object.keys(registeredByResource).length),
      projectSources: sources,
      projectBindings: bindings,
      registeredByResource,
    });
  },

  failProjectLoad: (projectId, message) => set({
    projectId,
    revision: null,
    status: 'error',
    message,
    projectSources: [],
    projectBindings: [],
    registeredByResource: {},
  }),

  clearProject: () => set({
    projectId: null,
    revision: null,
    status: 'unbound',
    message: 'Session-only workbench. Add ?project=<id> to bind durable project sources.',
    projectSources: [],
    projectBindings: [],
    registeredByResource: {},
  }),

  setProjectRevision: (projectId, revision) => set((state) => {
    if (state.projectId !== projectId || state.status !== 'bound') return state;
    const registeredByResource = Object.fromEntries(
      Object.entries(state.registeredByResource).map(([sourceKey, source]) => [
        sourceKey,
        source.projectId === projectId ? { ...source, revision } : source,
      ]),
    ) as Record<string, RegisteredWorkbenchStepSource>;
    return {
      revision,
      registeredByResource,
      message: projectMessage(projectId, revision, state.projectSources, Object.keys(registeredByResource).length),
    };
  }),

  setRegisteredSource: (source) => set((state) => {
    if (state.status !== 'bound' || state.projectId !== source.projectId) return state;
    const sourceDescriptor: ProjectSourceDescriptor = {
      sourceId: source.sourceId,
      contentHash: source.contentHash,
      parserRoute: 'step_geometry',
    };
    const sourceExists = state.projectSources.some(
      (row) => row.sourceId === source.sourceId && row.contentHash === source.contentHash,
    );
    const projectSources = sourceExists ? state.projectSources : [...state.projectSources, sourceDescriptor];
    const binding: ProjectStepBindingDescriptor = {
      candidateId: source.candidateId,
      resourceId: source.resourceId,
      entityId: source.entityId,
      sourceId: source.sourceId,
      modelId: source.modelId,
      contentHash: source.contentHash,
    };
    const bindingKey = key(source.candidateId, source.resourceId);
    const existingBindingIndex = state.projectBindings.findIndex(
      (row) => key(row.candidateId, row.resourceId) === bindingKey,
    );
    const projectBindings = existingBindingIndex >= 0
      ? state.projectBindings.map((row, index) => index === existingBindingIndex ? binding : row)
      : [...state.projectBindings, binding];
    const registeredByResource = {
      ...state.registeredByResource,
      [bindingKey]: source,
    };
    return {
      revision: source.revision,
      projectSources,
      projectBindings,
      registeredByResource,
      message: projectMessage(source.projectId, source.revision, projectSources, Object.keys(registeredByResource).length),
    };
  }),

  clearRegisteredSource: (candidateId, resourceId) => set((state) => {
    const next = { ...state.registeredByResource };
    delete next[key(candidateId, resourceId)];
    return {
      registeredByResource: next,
      message: state.projectId && state.revision
        ? projectMessage(state.projectId, state.revision, state.projectSources, Object.keys(next).length)
        : state.message,
    };
  }),
}));

export function getRegisteredWorkbenchStepSource(
  state: Pick<WorkbenchProjectSourceState, 'registeredByResource'>,
  candidateId: ConstructorCandidateId,
  resourceId: string,
) {
  return state.registeredByResource[key(candidateId, resourceId)] ?? null;
}
