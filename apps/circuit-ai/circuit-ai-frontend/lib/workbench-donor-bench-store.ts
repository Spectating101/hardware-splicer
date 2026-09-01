'use client';

import { create } from 'zustand';

const STORAGE_KEY = 'hardware-splicer.workbench-donor-bench.v1';

export type BenchMeasurementKind = 'resistance' | 'continuity' | 'voltage' | 'current' | 'thermal';
export type BenchCalibrationStatus = 'valid' | 'unknown' | 'expired';
export type BenchMeasurementStatus = 'pass' | 'failed' | 'recorded';

export type WorkbenchBenchMeasurement = {
  measurementId: string;
  kind: BenchMeasurementKind;
  target: string;
  value: string;
  unit: string;
  status: BenchMeasurementStatus;
  instrumentId: string;
  instrumentType: string;
  calibrationStatus: BenchCalibrationStatus;
  evidenceUri: string;
  notes: string;
};

export type WorkbenchDonorBenchCapture = {
  resourceId: string;
  captureId: string;
  operatorId: string;
  recordedAt: string;
  measurements: WorkbenchBenchMeasurement[];
  updatedAt: string;
  schemaVersion: 'bench_topology_capture.v1';
};

type WorkbenchDonorBenchState = {
  captures: Record<string, WorkbenchDonorBenchCapture>;
  hydrated: boolean;
  hydrate: () => void;
  saveCapture: (capture: WorkbenchDonorBenchCapture) => void;
  clearCapture: (resourceId: string) => void;
};

function validMeasurement(value: unknown): value is WorkbenchBenchMeasurement {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<WorkbenchBenchMeasurement>;
  return Boolean(
    typeof row.measurementId === 'string'
    && ['resistance', 'continuity', 'voltage', 'current', 'thermal'].includes(String(row.kind))
    && typeof row.target === 'string'
    && typeof row.value === 'string'
    && typeof row.unit === 'string'
    && ['pass', 'failed', 'recorded'].includes(String(row.status))
    && typeof row.instrumentId === 'string'
    && typeof row.instrumentType === 'string'
    && ['valid', 'unknown', 'expired'].includes(String(row.calibrationStatus))
    && typeof row.evidenceUri === 'string'
    && typeof row.notes === 'string',
  );
}

function validCapture(value: unknown): value is WorkbenchDonorBenchCapture {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<WorkbenchDonorBenchCapture>;
  return Boolean(
    typeof row.resourceId === 'string'
    && typeof row.captureId === 'string'
    && typeof row.operatorId === 'string'
    && typeof row.recordedAt === 'string'
    && typeof row.updatedAt === 'string'
    && row.schemaVersion === 'bench_topology_capture.v1'
    && Array.isArray(row.measurements)
    && row.measurements.every(validMeasurement),
  );
}

function readStored() {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, value]) => validCapture(value))) as Record<string, WorkbenchDonorBenchCapture>;
  } catch {
    return {};
  }
}

function persist(captures: Record<string, WorkbenchDonorBenchCapture>) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(captures));
}

export const useWorkbenchDonorBenchStore = create<WorkbenchDonorBenchState>((set) => ({
  captures: {},
  hydrated: false,
  hydrate: () => set((state) => state.hydrated ? state : { captures: readStored(), hydrated: true }),
  saveCapture: (capture) => set((state) => {
    const captures = { ...state.captures, [capture.resourceId]: capture };
    persist(captures);
    return { captures, hydrated: true };
  }),
  clearCapture: (resourceId) => set((state) => {
    const captures = { ...state.captures };
    delete captures[resourceId];
    persist(captures);
    return { captures, hydrated: true };
  }),
}));
