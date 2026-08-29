'use client';

import { create } from 'zustand';

export type WorkbenchLens = 'authority' | 'interfaces' | 'provenance' | 'constraints';
export type WorkbenchBottomTab = 'evidence' | 'interfaces' | 'constraints' | 'verification' | 'history';
export type WorkbenchView = 'assembly' | 'pcb';
export type WorkbenchCameraPreset = 'iso' | 'top' | 'front' | 'right';

export type MachineWorkbenchState = {
  selectedEntityId: string;
  activeLens: WorkbenchLens;
  activeBottomTab: WorkbenchBottomTab;
  activeView: WorkbenchView;
  isolatedEntityId: string | null;
  exploded: boolean;
  xray: boolean;
  cameraPreset: WorkbenchCameraPreset;
  frameRequest: number;
  setSelectedEntityId: (id: string) => void;
  setActiveLens: (lens: WorkbenchLens) => void;
  setActiveBottomTab: (tab: WorkbenchBottomTab) => void;
  setActiveView: (view: WorkbenchView) => void;
  setIsolatedEntityId: (id: string | null) => void;
  setCameraPreset: (preset: WorkbenchCameraPreset) => void;
  requestFrameSelection: () => void;
  toggleExploded: () => void;
  toggleXray: () => void;
  resetViewState: () => void;
};

export const useMachineWorkbenchStore = create<MachineWorkbenchState>((set) => ({
  selectedEntityId: 'deck-001',
  activeLens: 'authority',
  activeBottomTab: 'evidence',
  activeView: 'assembly',
  isolatedEntityId: null,
  exploded: false,
  xray: false,
  cameraPreset: 'iso',
  frameRequest: 0,
  setSelectedEntityId: (selectedEntityId) => set({ selectedEntityId }),
  setActiveLens: (activeLens) => set({ activeLens }),
  setActiveBottomTab: (activeBottomTab) => set({ activeBottomTab }),
  setActiveView: (activeView) => set({ activeView }),
  setIsolatedEntityId: (isolatedEntityId) => set({ isolatedEntityId }),
  setCameraPreset: (cameraPreset) => set({ cameraPreset }),
  requestFrameSelection: () => set((state) => ({ frameRequest: state.frameRequest + 1 })),
  toggleExploded: () => set((state) => ({ exploded: !state.exploded })),
  toggleXray: () => set((state) => ({ xray: !state.xray })),
  resetViewState: () =>
    set((state) => ({
      activeLens: 'authority',
      activeBottomTab: 'evidence',
      activeView: 'assembly',
      isolatedEntityId: null,
      exploded: false,
      xray: false,
      cameraPreset: 'iso',
      frameRequest: state.frameRequest + 1,
    })),
}));
