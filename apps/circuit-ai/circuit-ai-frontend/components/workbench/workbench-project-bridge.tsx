'use client';

import { useEffect } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import {
  type ProjectSourceDescriptor,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function candidateId(value: unknown): ConstructorCandidateId | undefined {
  return value === 'balanced' || value === 'max-reuse' || value === 'low-risk'
    ? value
    : undefined;
}

function projectSources(snapshot: Record<string, unknown>): ProjectSourceDescriptor[] {
  const rows = Array.isArray(snapshot.engineeringSources) ? snapshot.engineeringSources : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const sourceId = typeof row.source_id === 'string' ? row.source_id : '';
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    if (!sourceId || !/^sha256:[0-9a-f]{64}$/.test(contentHash)) return [];
    const metadata = record(row.metadata);
    const workbenchCandidateId = candidateId(metadata.workbench_candidate_id);
    const resourceId = typeof metadata.workbench_resource_id === 'string' && metadata.workbench_resource_id.trim()
      ? metadata.workbench_resource_id.trim()
      : undefined;
    const entityId = typeof metadata.workbench_entity_id === 'string' && metadata.workbench_entity_id.trim()
      ? metadata.workbench_entity_id.trim()
      : undefined;
    const parserRoute = typeof metadata.parser_route === 'string' ? metadata.parser_route : undefined;
    return [{
      sourceId,
      contentHash,
      originalFilename: typeof metadata.original_filename === 'string' ? metadata.original_filename : undefined,
      parserRoute,
      candidateId: workbenchCandidateId,
      resourceId,
      entityId,
      modelId: parserRoute === 'step_geometry' ? sourceId : undefined,
    }];
  });
}

export function WorkbenchProjectBridge() {
  const beginProjectLoad = useWorkbenchProjectSourceStore((state) => state.beginProjectLoad);
  const bindProject = useWorkbenchProjectSourceStore((state) => state.bindProject);
  const failProjectLoad = useWorkbenchProjectSourceStore((state) => state.failProjectLoad);
  const clearProject = useWorkbenchProjectSourceStore((state) => state.clearProject);

  useEffect(() => {
    const projectId = new URLSearchParams(window.location.search).get('project')?.trim() ?? '';
    if (!projectId) {
      clearProject();
      return;
    }

    let cancelled = false;
    beginProjectLoad(projectId);

    void (async () => {
      try {
        const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}`, {
          cache: 'no-store',
        });
        const payload = record(await response.json());
        if (!response.ok || payload.ok === false) {
          const detail = record(payload.detail);
          throw new Error(String(detail.message || payload.error || `project HTTP ${response.status}`));
        }
        const project = Object.keys(record(payload.project)).length > 0 ? record(payload.project) : payload;
        const snapshot = Object.keys(record(project.snapshot)).length > 0 ? record(project.snapshot) : project;
        const revision = Number(project.revision);
        if (!Number.isInteger(revision) || revision < 1) {
          throw new Error('Project response did not include a valid durable revision.');
        }
        if (cancelled) return;
        bindProject(projectId, revision, projectSources(snapshot));
      } catch (error: unknown) {
        if (cancelled) return;
        failProjectLoad(projectId, error instanceof Error ? error.message : String(error));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [beginProjectLoad, bindProject, clearProject, failProjectLoad]);

  return null;
}
