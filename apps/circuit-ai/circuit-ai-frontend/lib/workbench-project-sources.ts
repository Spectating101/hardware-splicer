'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type ProjectSourceDescriptor = {
  sourceId: string;
  contentHash: string;
  originalFilename?: string;
  parserRoute?: string;
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

  bindProject: (projectId, revision, sources) => set({
    projectId,
    revision,
    status: 'bound',
    message: `Project ${projectId} · revision ${revision} · ${sources.length} registered source${sources.length === 1 ? '' : 's'}`,
    projectSources: sources,
    registeredByResource: {},
  }),

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
    return {
      revision,
      message: `Project ${projectId} · revision ${revision} · ${state.projectSources.length} registered source${state.projectSources.length === 1 ? '' : 's'}`,
    };
  }),

  setRegisteredSource: (source) => set((state) => {
    if (state.status !== 'bound' || state.projectId !== source.projectId) return state;
    const sourceDescriptor: ProjectSourceDescriptor = {
      sourceId: source.sourceId,
      contentHash: source.contentHash,
      parserRoute: 'step_geometry',
    };
    const exists = state.projectSources.some((row) => row.sourceId === source.sourceId && row.contentHash === source.contentHash);
    return {
      revision: source.revision,
      projectSources: exists ? state.projectSources : [...state.projectSources, sourceDescriptor],
      registeredByResource: {
        ...state.registeredByResource,
        [key(source.candidateId, source.resourceId)]: source,
      },
    };
  }),

  clearRegisteredSource: (candidateId, resourceId) => set((state) => {
    const next = { ...state.registeredByResource };
    delete next[key(candidateId, resourceId)];
    return { registeredByResource: next };
  }),
}));

export function getRegisteredWorkbenchStepSource(
  state: Pick<WorkbenchProjectSourceState, 'registeredByResource'>,
  candidateId: ConstructorCandidateId,
  resourceId: string,
) {
  return state.registeredByResource[key(candidateId, resourceId)] ?? null;
}
