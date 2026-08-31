'use client';

import { useEffect } from 'react';
import { constructorResources } from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore, type ConstructorCandidateId } from '@/lib/machine-workbench-store';

const candidateIds = new Set<ConstructorCandidateId>(['balanced', 'max-reuse', 'low-risk']);

export function WorkbenchStageBridge() {
  const setPhase = useMachineWorkbenchStore((state) => state.setPhase);
  const setConstructorDockTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setActiveCandidateId = useMachineWorkbenchStore((state) => state.setActiveCandidateId);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const setActiveView = useMachineWorkbenchStore((state) => state.setActiveView);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const candidate = searchParams.get('candidate') as ConstructorCandidateId | null;
    if (candidate && candidateIds.has(candidate)) setActiveCandidateId(candidate);

    const resourceId = searchParams.get('resource');
    if (resourceId) {
      setSelectedResourceId(resourceId);
      const resource = constructorResources.find((row) => row.id === resourceId);
      if (resource?.mappedEntityId) {
        setSelectedEntityId(resource.mappedEntityId);
        window.setTimeout(requestFrameSelection, 0);
      }
    }

    const stage = searchParams.get('stage');
    if (!stage) return;

    if (stage === 'inventory' || stage === 'resolve') {
      setPhase('construct');
      setConstructorDockTab('resources');
      setActiveView('assembly');
      return;
    }

    if (stage === 'goal' || stage === 'candidates') {
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
  }, [requestFrameSelection, setActiveBottomTab, setActiveCandidateId, setActiveView, setConstructorDockTab, setPhase, setSelectedEntityId, setSelectedResourceId]);

  return null;
}
