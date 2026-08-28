import { create } from 'zustand';

export type WorkbenchLens = 'authority' | 'interfaces' | 'provenance' | 'constraints';
export type WorkbenchBottomTab = 'evidence' | 'interfaces' | 'constraints' | 'verification' | 'history';
export type WorkbenchView = 'assembly' | 'pcb';

export type WorkbenchState = {
  selectedEntityId: string;
  activeLens: WorkbenchLens;
  activeBottomTab: WorkbenchBottomTab;
  activeView: WorkbenchView;
  isolatedEntityId: string | null;
  exploded: boolean;
  setSelectedEntityId: (id: string) => void;
  setActiveLens: (lens: WorkbenchLens) => void;
  setActiveBottomTab: (tab: WorkbenchBottomTab) => void;
  setActiveView: (view: WorkbenchView) => void;
  setIsolatedEntityId: (id: string | null) => void;
  toggleExploded: () => void;
  resetViewState: () => void;
};

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  selectedEntityId: 'deck-001',
  activeLens: 'authority',
  activeBottomTab: 'evidence',
  activeView: 'assembly',
  isolatedEntityId: null,
  exploded: false,
  setSelectedEntityId: (selectedEntityId) => set({ selectedEntityId }),
  setActiveLens: (activeLens) => set({ activeLens }),
  setActiveBottomTab: (activeBottomTab) => set({ activeBottomTab }),
  setActiveView: (activeView) => set({ activeView }),
  setIsolatedEntityId: (isolatedEntityId) => set({ isolatedEntityId }),
  toggleExploded: () => set((state) => ({ exploded: !state.exploded })),
  resetViewState: () =>
    set({
      activeLens: 'authority',
      activeBottomTab: 'evidence',
      activeView: 'assembly',
      isolatedEntityId: null,
      exploded: false,
    }),
}));
