'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

type StudioRuntimeState = {
  artifactName: string | null;
  analysisMode: string | null;
  detectionCount: number | null;
  focusedComponent: string | null;
  focusedProject: string | null;
};

type StudioRuntimeContextValue = {
  state: StudioRuntimeState;
  setArtifactName: (artifactName: string | null) => void;
  setAnalysisMode: (analysisMode: string | null) => void;
  setDetectionCount: (detectionCount: number | null) => void;
  setFocusedComponent: (focusedComponent: string | null) => void;
  setFocusedProject: (focusedProject: string | null) => void;
  resetRuntime: () => void;
};

const STORAGE_KEY = 'circuit-ai-studio-runtime';

const initialState: StudioRuntimeState = {
  artifactName: null,
  analysisMode: null,
  detectionCount: null,
  focusedComponent: null,
  focusedProject: null,
};

const StudioRuntimeContext = createContext<StudioRuntimeContextValue | null>(null);

export function StudioRuntimeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StudioRuntimeState>(initialState);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      const parsed = JSON.parse(saved) as Partial<StudioRuntimeState>;
      setState({ ...initialState, ...parsed });
    } catch (error) {
      console.error('Failed to restore studio runtime', error);
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      console.error('Failed to persist studio runtime', error);
    }
  }, [state]);

  const setRuntimeField = useCallback(
    <K extends keyof StudioRuntimeState>(key: K, value: StudioRuntimeState[K]) => {
      setState((current) => {
        if (current[key] === value) return current;
        return { ...current, [key]: value };
      });
    },
    [],
  );

  const setArtifactName = useCallback(
    (artifactName: string | null) => setRuntimeField('artifactName', artifactName),
    [setRuntimeField],
  );
  const setAnalysisMode = useCallback(
    (analysisMode: string | null) => setRuntimeField('analysisMode', analysisMode),
    [setRuntimeField],
  );
  const setDetectionCount = useCallback(
    (detectionCount: number | null) => setRuntimeField('detectionCount', detectionCount),
    [setRuntimeField],
  );
  const setFocusedComponent = useCallback(
    (focusedComponent: string | null) => setRuntimeField('focusedComponent', focusedComponent),
    [setRuntimeField],
  );
  const setFocusedProject = useCallback(
    (focusedProject: string | null) => setRuntimeField('focusedProject', focusedProject),
    [setRuntimeField],
  );
  const resetRuntime = useCallback(() => {
    setState((current) => {
      const hasState = Object.values(current).some((value) => value !== null);
      return hasState ? initialState : current;
    });
  }, []);

  const value = useMemo<StudioRuntimeContextValue>(
    () => ({
      state,
      setArtifactName,
      setAnalysisMode,
      setDetectionCount,
      setFocusedComponent,
      setFocusedProject,
      resetRuntime,
    }),
    [resetRuntime, setAnalysisMode, setArtifactName, setDetectionCount, setFocusedComponent, setFocusedProject, state],
  );

  return <StudioRuntimeContext.Provider value={value}>{children}</StudioRuntimeContext.Provider>;
}

export function useStudioRuntime() {
  const context = useContext(StudioRuntimeContext);

  if (!context) {
    throw new Error('useStudioRuntime must be used inside StudioRuntimeProvider');
  }

  return context;
}
