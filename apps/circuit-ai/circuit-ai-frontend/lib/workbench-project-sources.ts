'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type ProjectSourceDescriptor = {
  sourceId: string;
  contentHash: string;
  originalFilename?: string;
  parserRoute?: string;
  candidateId?: ConstructorCandidateId;
  resourceId?: string;
  entityId?: string;
  modelId?: string;
};

export type RegisteredWorkbenchStepSource = {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  projectId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
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
  registeredByResource: Record<string, RegisteredWorkbenchStepSource>;
  beginProjectLoad: (projectId: string) => void;
  bindProject: (projectId: string, revision: number, sources: ProjectSourceDescriptor[]) => void;
  failProjectLoad: (projectId: string, message: string) => void;
  clearProject: () => void;
  setProjectRevision: (projectId: string, revision: number) => void;
  setRegisteredSource: (source: RegisteredWorkbenchStepSource) => void;
  clearRegisteredSource: (candidateId: ConstructorCandidateId, resourceId: string) => void;
};

function key(candidateId: ConstructorCandidateId, resourceId: string) {
  return `${candidateId}::${resourceId}`;
}

function rehydratedBindings(
  projectId: string,
  revision: number,
  sources: ProjectSourceDescriptor[],
) {
  const registered: Record<string, RegisteredWorkbenchStepSource> = {};
  for (const source of sources) {
    if (
      source.parserRoute !== 'step_geometry'
      || !source.candidateId
      || !source.resourceId
      || !source.entityId
    ) continue;
    registered[key(source.candidateId, source.resourceId)] = {
      candidateId: source.candidateId,
      resourceId: source.resourceId,
      entityId: source.entityId,
      projectId,
      sourceId: source.sourceId,
      modelId: source.modelId || source.sourceId,
      contentHash: source.contentHash,
      revision,
      sourceMaterialization: 'registered_project',
    };
  }
  return registered;
}

function projectMessage(projectId: string, revision: number, sources: ProjectSourceDescriptor[], bindingCount: number) {
  return `Project ${projectId} · revision ${revision} · ${sources.length} registered source${sources.length === 1 ? '' : 's'} · ${bindingCount} workbench binding${bindingCount === 1 ? '' : 's'}`;
}

export const useWorkbenchProjectSourceStore = create<WorkbenchProjectSourceState>((set) => ({
  projectId: null,
  revision: null,
  status: 'unbound',
  message: 'Session-only workbench. Add ?project=<id> to bind durable project sources.',
  projectSources: [],
  registeredByResource: {},

  beginProjectLoad: (projectId) => set({
    projectId,
    revision: null,
    status: 'loading',
    message: `Loading project ${projectId}…`,
    projectSources: [],
    registeredByResource: {},
  }),

  bindProject: (projectId, revision, sources) => {
    const registeredByResource = rehydratedBindings(projectId, revision, sources);
    set({
      projectId,
      revision,
      status: 'bound',
      message: projectMessage(projectId, revision, sources, Object.keys(registeredByResource).length),
      projectSources: sources,
      registeredByResource,
    });
  },

  failProjectLoad: (projectId, message) => set({
    projectId,
    revision: null,
    status: 'error',
    message,
    projectSources: [],
    registeredByResource: {},
  }),

  clearProject: () => set({
    projectId: null,
    revision: null,
    status: 'unbound',
    message: 'Session-only workbench. Add ?project=<id> to bind durable project sources.',
    projectSources: [],
    registeredByResource: {},
  }),

  setProjectRevision: (projectId, revision) => set((state) => {
    if (state.projectId !== projectId || state.status !== 'bound') return state;
    const registeredByResource = Object.fromEntries(
      Object.entries(state.registeredByResource).map(([sourceKey, source]) => [
        sourceKey,
        source.projectId === projectId ? { ...source, revision } : source,
      ]),
    );
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
      candidateId: source.candidateId,
      resourceId: source.resourceId,
      entityId: source.entityId,
      modelId: source.modelId,
    };
    const existingIndex = state.projectSources.findIndex(
      (row) => row.sourceId === source.sourceId && row.contentHash === source.contentHash,
    );
    const projectSources = existingIndex >= 0
      ? state.projectSources.map((row, index) => index === existingIndex ? { ...row, ...sourceDescriptor } : row)
      : [...state.projectSources, sourceDescriptor];
    const registeredByResource = {
      ...state.registeredByResource,
      [key(source.candidateId, source.resourceId)]: source,
    };
    return {
      revision: source.revision,
      projectSources,
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
