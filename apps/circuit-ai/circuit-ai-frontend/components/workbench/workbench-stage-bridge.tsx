'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useMachineWorkbenchStore, type ConstructorCandidateId } from '@/lib/machine-workbench-store';

const candidateIds = new Set<ConstructorCandidateId>(['balanced', 'max-reuse', 'low-risk']);

export function WorkbenchStageBridge() {
  const searchParams = useSearchParams();
  const setPhase = useMachineWorkbenchStore((state) => state.setPhase);
  const setConstructorDockTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setActiveCandidateId = useMachineWorkbenchStore((state) => state.setActiveCandidateId);
  const setActiveView = useMachineWorkbenchStore((state) => state.setActiveView);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);

  useEffect(() => {
    const candidate = searchParams.get('candidate') as ConstructorCandidateId | null;
    if (candidate && candidateIds.has(candidate)) setActiveCandidateId(candidate);

    const stage = searchParams.get('stage');
    if (!stage) return;

    if (stage === 'inventory') {
      setPhase('construct');
      setConstructorDockTab('resources');
      setActiveView('assembly');
      return;
    }

    if (stage === 'goal' || stage === 'candidates' || stage === 'resolve') {
      setPhase('construct');
      setConstructorDockTab('target');
      setActiveView('assembly');
      return;
    }

    if (stage === 'verify') {
      setPhase('inspect');
      setActiveView('assembly');
      setActiveBottomTab('verification');
    }
  }, [searchParams, setActiveBottomTab, setActiveCandidateId, setActiveView, setConstructorDockTab, setPhase]);

  return null;
}
