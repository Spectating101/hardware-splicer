'use client';

import { create } from 'zustand';

const STORAGE_KEY = 'hardware-splicer.workbench-donor-evidence.v1';

export type DonorCondition = 'unknown' | 'appears_usable' | 'damaged';

export type WorkbenchDonorEvidence = {
  resourceId: string;
  identityLabel: string;
  condition: DonorCondition;
  dimensionsNote: string;
  connectorNote: string;
  powerNote: string;
  evidenceUri: string;
  notes: string;
  recordedAt: string;
  authority: 'operator_claim';
};

type WorkbenchDonorEvidenceState = {
  records: Record<string, WorkbenchDonorEvidence>;
  hydrated: boolean;
  hydrate: () => void;
  saveEvidence: (record: WorkbenchDonorEvidence) => void;
  clearEvidence: (resourceId: string) => void;
};

function validRecord(value: unknown): value is WorkbenchDonorEvidence {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<WorkbenchDonorEvidence>;
  return Boolean(
    typeof row.resourceId === 'string'
    && typeof row.identityLabel === 'string'
    && typeof row.dimensionsNote === 'string'
    && typeof row.connectorNote === 'string'
    && typeof row.powerNote === 'string'
    && typeof row.evidenceUri === 'string'
    && typeof row.notes === 'string'
    && typeof row.recordedAt === 'string'
    && row.authority === 'operator_claim'
    && ['unknown', 'appears_usable', 'damaged'].includes(String(row.condition)),
  );
}

function readStored(): Record<string, WorkbenchDonorEvidence> {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, value]) => validRecord(value))) as Record<string, WorkbenchDonorEvidence>;
  } catch {
    return {};
  }
}

function persist(records: Record<string, WorkbenchDonorEvidence>) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(records));
}

export const useWorkbenchDonorEvidenceStore = create<WorkbenchDonorEvidenceState>((set) => ({
  records: {},
  hydrated: false,
  hydrate: () => set((state) => state.hydrated ? state : { records: readStored(), hydrated: true }),
  saveEvidence: (record) => set((state) => {
    const records = { ...state.records, [record.resourceId]: record };
    persist(records);
    return { records, hydrated: true };
  }),
  clearEvidence: (resourceId) => set((state) => {
    const records = { ...state.records };
    delete records[resourceId];
    persist(records);
    return { records, hydrated: true };
  }),
}));
