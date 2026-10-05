'use client';

import { useEffect, useState } from 'react';
import type { ViewerHighlight } from '@/components/engineering/viewer-overlay';

export type KicadChange = {
  change: 'added' | 'removed' | 'changed';
  item_type: string;
  ref: string | null;
  uuid: string | null;
  label: string;
  position: { x_mm: number; y_mm: number } | null;
  bbox_mm: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  details: string[];
};

export type ArtifactDiff =
  | {
      available: true;
      kind: 'schematic' | 'pcb';
      artifact?: { base?: { relative?: string }; candidate?: { relative?: string } };
      summary: { added: number; removed: number; changed: number; unchanged: number };
      changes: KicadChange[];
      limits?: { truncated?: boolean; max_changes?: number };
    }
  | { available: false; reason: string };

export type ArtifactDiffs = { schematic: ArtifactDiff | null; pcb: ArtifactDiff | null; loading: boolean };

async function fetchDiff(projectId: string, base: number, candidate: number, kind: 'schematic' | 'pcb'): Promise<ArtifactDiff> {
  const url = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/artifact-diff?base=${base}&candidate=${candidate}&kind=${kind}`;
  try {
    const response = await fetch(url, { cache: 'no-store' });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body?.detail?.message || body?.error || `The comparison could not be loaded (${response.status}).`;
      return { available: false, reason: String(detail) };
    }
    if (body?.available === false) return { available: false, reason: String(body.reason || 'The artifact for one revision was not retained.') };
    return {
      available: true,
      kind,
      artifact: body.artifact,
      summary: body.diff?.summary || { added: 0, removed: 0, changed: 0, unchanged: 0 },
      changes: Array.isArray(body.diff?.changes) ? body.diff.changes : [],
      limits: body.diff?.limits,
    };
  } catch {
    return { available: false, reason: 'The comparison service could not be reached.' };
  }
}

/** Loads the retained-artifact diff for both artifact kinds. Missing artifacts are reported, never guessed. */
export function useArtifactDiffs(projectId: string, base: number | null, candidate: number | null): ArtifactDiffs {
  const [state, setState] = useState<ArtifactDiffs>({ schematic: null, pcb: null, loading: false });

  useEffect(() => {
    if (!projectId || !base || !candidate || base === candidate) {
      setState({ schematic: null, pcb: null, loading: false });
      return;
    }
    let cancelled = false;
    setState({ schematic: null, pcb: null, loading: true });
    Promise.all([
      fetchDiff(projectId, base, candidate, 'schematic'),
      fetchDiff(projectId, base, candidate, 'pcb'),
    ]).then(([schematic, pcb]) => {
      if (!cancelled) setState({ schematic, pcb, loading: false });
    });
    return () => { cancelled = true; };
  }, [projectId, base, candidate]);

  return state;
}

const HALF_MARK_MM = 1.6;

/** One stable key per change, shared by the list rows and the overlay boxes so they can point at each other. */
export function changeKey(change: KicadChange, index: number) {
  return `${index}-${change.uuid || change.ref || change.label}`;
}

/** Map diff changes to overlay boxes. A change with only a point gets a small box so it can be seen. */
export function changesToHighlights(diff: ArtifactDiff | null, relative: string): ViewerHighlight[] {
  if (!diff || !diff.available) return [];
  return diff.changes.flatMap((change, index) => {
    const box = change.bbox_mm
      || (change.position
        ? { min_x: change.position.x_mm - HALF_MARK_MM, min_y: change.position.y_mm - HALF_MARK_MM, max_x: change.position.x_mm + HALF_MARK_MM, max_y: change.position.y_mm + HALF_MARK_MM }
        : null);
    if (!box) return [];
    return [{
      id: changeKey(change, index),
      relative,
      bbox: box,
      tone: change.change,
      label: `${change.change[0].toUpperCase()}${change.change.slice(1)}: ${change.label}`,
    }];
  });
}
