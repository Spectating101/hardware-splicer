'use client';

import { create } from 'zustand';

const STORAGE_KEY = 'hardware-splicer.workbench-donor-intake.v1';

export type WorkbenchDonorResource = {
  resourceId: string;
  name: string;
  observedLabel: string;
  capabilities: string[];
  confidence: number;
  evidenceStatus: 'needs_evidence';
  sourceKind: 'photo_analysis';
  sourceName: string;
  note: string;
};

type WorkbenchDonorIntakeState = {
  resources: WorkbenchDonorResource[];
  hydrated: boolean;
  hydrate: () => void;
  addResources: (resources: WorkbenchDonorResource[]) => void;
  clearResources: () => void;
};

function readStoredResources(): WorkbenchDonorResource[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row): row is WorkbenchDonorResource => Boolean(
      row
      && typeof row === 'object'
      && typeof row.resourceId === 'string'
      && typeof row.name === 'string'
      && Array.isArray(row.capabilities),
    ));
  } catch {
    return [];
  }
}

function persist(resources: WorkbenchDonorResource[]) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(resources));
}

function mergeResources(existing: WorkbenchDonorResource[], incoming: WorkbenchDonorResource[]) {
  const merged = new Map(existing.map((resource) => [resource.resourceId, resource]));
  for (const resource of incoming) merged.set(resource.resourceId, resource);
  return [...merged.values()];
}

export const useWorkbenchDonorIntakeStore = create<WorkbenchDonorIntakeState>((set) => ({
  resources: [],
  hydrated: false,
  hydrate: () => set((state) => state.hydrated ? state : { resources: readStoredResources(), hydrated: true }),
  addResources: (incoming) => set((state) => {
    const resources = mergeResources(state.resources, incoming);
    persist(resources);
    return { resources, hydrated: true };
  }),
  clearResources: () => {
    persist([]);
    set({ resources: [], hydrated: true });
  },
}));
