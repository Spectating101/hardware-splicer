'use client';

import { useCallback, useEffect, useState } from 'react';
import type { KicadChange } from '@/lib/artifact-diff';
import { PROJECT_CHANGE_EVENT, type LiveChange } from '@/lib/project-live';

export type EditOp = Record<string, string | number | boolean>;
export type ProposalInput = { ops: EditOp[] } | { autoroute: { max_passes?: number; keep_existing_tracks?: boolean } };
export type RoutingCapability = { available: boolean; reason: string | null; components?: Record<string, { ok: boolean; version: string | null }> };

export type CheckSide = { errors: number; warnings: number; total: number; by_type?: Record<string, number> };
export type CandidateChecks = {
  engine?: string;
  available?: boolean;
  version?: string | null;
  ran?: boolean;
  reason?: string | null;
  before?: CheckSide | null;
  after?: CheckSide | null;
  new_violations?: number | null;
};

export type Candidate = {
  candidate_id: string;
  project_id: string;
  base_revision: number;
  kind: 'schematic' | 'pcb';
  review_id: string;
  created_by: string;
  verified: boolean;
  created_at: string;
  applied?: { op?: string; target?: { ref?: string | null; uuid?: string | null }; detail?: string }[];
  warnings?: string[];
  diff?: { summary?: { added: number; removed: number; changed: number; unchanged: number }; changes?: KicadChange[] };
  checks?: CandidateChecks | null;
  authority?: { state: string; note: string };
};

const AUTHOR_KEY = 'hs-review-author';
const TOKEN_KEY = 'hs-operator-token';

function stored(storage: 'local' | 'session', key: string) {
  try {
    return (storage === 'local' ? window.localStorage : window.sessionStorage).getItem(key) || '';
  } catch {
    return '';
  }
}

function errorText(body: unknown, fallback: string) {
  const record = (body && typeof body === 'object' ? body : {}) as { error?: unknown; detail?: { message?: unknown } };
  const message = record.detail?.message ?? record.error;
  return typeof message === 'string' && message ? message : fallback;
}

/** Proposals for a project, newest first. A proposal is only ever a pending suggestion; the list never applies one. */
export function useCandidates(projectId: string) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const base = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/candidates`;

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const response = await fetch(base, { cache: 'no-store' });
      const body = await response.json();
      if (response.ok && body?.ok !== false && Array.isArray(body?.candidates)) setCandidates(body.candidates);
    } catch {
      // Keep the last list; the panel still works without it.
    } finally {
      setLoading(false);
    }
  }, [base, projectId]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    function onChange(event: Event) {
      const changes = ((event as CustomEvent).detail || []) as LiveChange[];
      if (changes.some((change) => change.type === 'review.opened')) void load();
    }
    window.addEventListener(PROJECT_CHANGE_EVENT, onChange);
    return () => window.removeEventListener(PROJECT_CHANGE_EVENT, onChange);
  }, [load]);

  const propose = useCallback(async (input: { baseRevision: number | null; kind: 'schematic' | 'pcb'; note: string } & ProposalInput) => {
    const token = stored('session', TOKEN_KEY);
    const name = stored('local', AUTHOR_KEY).trim();
    const response = await fetch(base, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(token ? { 'x-hs-operator-token': token } : {}) },
      body: JSON.stringify({ base_revision: input.baseRevision, kind: input.kind, ...('ops' in input ? { ops: input.ops } : { autoroute: input.autoroute }), author: name || 'Reviewer', note: input.note }),
      cache: 'no-store',
    });
    const body = await response.json().catch(() => null);
    if (!response.ok || body?.ok === false) throw new Error(errorText(body, 'The proposal could not be created.'));
    await load();
    return body.candidate as Candidate;
  }, [base, load]);

  return { candidates, loading, reload: load, propose };
}

/** Whether this server can autoroute. Asked once per project; a failure reads as unavailable, never as available. */
export function useRoutingCapability(projectId: string, enabled: boolean) {
  const [capability, setCapability] = useState<RoutingCapability | null>(null);

  useEffect(() => {
    if (!projectId || !enabled) return;
    let cancelled = false;
    fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/routing`, { cache: 'no-store' })
      .then((response) => response.json())
      .then((body) => {
        if (cancelled) return;
        const routing = body?.routing;
        setCapability(body?.ok !== false && routing && typeof routing === 'object'
          ? { available: Boolean(routing.available), reason: typeof routing.reason === 'string' ? routing.reason : null, components: routing.components }
          : { available: false, reason: 'The routing service could not be reached.' });
      })
      .catch(() => { if (!cancelled) setCapability({ available: false, reason: 'The routing service could not be reached.' }); });
    return () => { cancelled = true; };
  }, [projectId, enabled]);

  return capability;
}

/** The proposed file as text, for previewing in the viewer. Nothing here writes. */
export async function fetchCandidateFile(projectId: string, candidateId: string, kind: 'schematic' | 'pcb') {
  const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/candidates/${encodeURIComponent(candidateId)}/files/${kind}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('The proposed file could not be loaded.');
  return response.text();
}
