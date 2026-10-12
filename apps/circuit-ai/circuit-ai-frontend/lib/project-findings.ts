'use client';

import { useEffect, useState } from 'react';
import type { ProjectFinding } from '@/components/engineering/provenance-chip';

export type UnmatchedLink = { evidence_id: string; finding_id: string };

/**
 * Loads the backend's findings projection for a project. It is read-only labelling: when it cannot be loaded the
 * page still works and every finding reads as "Provenance not recorded".
 */
export function useProjectFindings(projectId: string) {
  const [state, setState] = useState<{ findings: ProjectFinding[]; unmatched: UnmatchedLink[] }>({ findings: [], unmatched: [] });

  useEffect(() => {
    if (!projectId) {
      setState({ findings: [], unmatched: [] });
      return;
    }
    let cancelled = false;
    fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/findings`, { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (cancelled) return;
        setState({
          findings: Array.isArray(body?.findings) ? body.findings : [],
          unmatched: Array.isArray(body?.unmatched_links) ? body.unmatched_links : [],
        });
      })
      .catch(() => { if (!cancelled) setState({ findings: [], unmatched: [] }); });
    return () => { cancelled = true; };
  }, [projectId]);

  return state;
}
