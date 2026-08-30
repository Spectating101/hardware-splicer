'use client';

import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type SessionStepSource = {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
  content: string;
};

// Raw STEP text is deliberately session-local and non-reactive. It never enters the
// canonical workbench evidence/store projection, browser persistence, or project
// snapshot. Canonical projects should use the registered-source BREP route, which
// reopens content-addressed blobs server-side. This cache exists only so the
// self-contained /workbench upload flow can request an exact pair check after the
// bounded parser has already established the canonical content hash.
const sourcesByCandidate = new Map<ConstructorCandidateId, Map<string, SessionStepSource>>();

export function cacheSessionStepSource(source: SessionStepSource) {
  const candidate = sourcesByCandidate.get(source.candidateId) ?? new Map<string, SessionStepSource>();
  candidate.set(source.resourceId, source);
  sourcesByCandidate.set(source.candidateId, candidate);
}

export function getSessionStepSource(candidateId: ConstructorCandidateId, resourceId: string) {
  return sourcesByCandidate.get(candidateId)?.get(resourceId) ?? null;
}

export function clearSessionStepSource(candidateId: ConstructorCandidateId, resourceId: string) {
  const candidate = sourcesByCandidate.get(candidateId);
  if (!candidate) return;
  candidate.delete(resourceId);
  if (candidate.size === 0) sourcesByCandidate.delete(candidateId);
}
