'use client';

import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type WorkbenchProjectBinding = {
  projectId: string;
  revision: number;
};

export type ImportedWorkbenchStepSource = {
  durable: boolean;
  projectId: string;
  revision: number | null;
  sourceId: string;
  modelId: string;
  contentHash: string;
  content: string | null;
  mechanicalGeometry: Record<string, unknown>;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function errorMessage(payload: Record<string, unknown>, fallback: string) {
  const detail = record(payload.detail);
  return String(detail.message || payload.error || fallback);
}

function canonicalHash(value: unknown) {
  const resolved = String(value || '');
  if (!/^sha256:[0-9a-f]{64}$/.test(resolved)) {
    throw new Error('HS source transaction did not return a canonical sha256 content hash.');
  }
  return resolved;
}

function positiveRevision(value: unknown, label: string) {
  const resolved = Number(value);
  if (!Number.isInteger(resolved) || resolved < 1) {
    throw new Error(`${label} did not return a valid project revision.`);
  }
  return resolved;
}

export async function importWorkbenchStepSource({
  file,
  candidateId,
  resourceId,
  entityId,
  projectBinding,
}: {
  file: File;
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  projectBinding: WorkbenchProjectBinding | null;
}): Promise<ImportedWorkbenchStepSource> {
  const requestedModelId = `${candidateId}-${resourceId}`;

  if (!projectBinding) {
    const content = await file.text();
    const response = await fetch('/api/proxy/engineering/mechanical/geometry/parse', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        project_id: 'deck-001',
        sources: [{
          source_id: file.name,
          model_id: requestedModelId,
          content,
        }],
        mounts: [],
      }),
      cache: 'no-store',
    });
    const payload = record(await response.json());
    if (!response.ok || payload.ok !== true) {
      throw new Error(errorMessage(payload, `mechanical geometry HTTP ${response.status}`));
    }
    const geometry = record(payload.mechanical_geometry);
    const models = Array.isArray(geometry.models) ? geometry.models : [];
    const model = record(models[0]);
    return {
      durable: false,
      projectId: 'deck-001',
      revision: null,
      sourceId: String(model.source_id || file.name),
      modelId: String(model.model_id || requestedModelId),
      contentHash: canonicalHash(model.content_hash),
      content,
      mechanicalGeometry: geometry,
    };
  }

  const form = new FormData();
  form.append('file', file, file.name);
  form.append('expected_revision', String(projectBinding.revision));
  form.append('authority_ceiling', 'declared');
  form.append('metadata_json', JSON.stringify({
    workbench_candidate_id: candidateId,
    workbench_resource_id: resourceId,
    workbench_entity_id: entityId,
    workbench_source_role: 'mechanical_step',
  }));

  const ingestResponse = await fetch(
    `/api/proxy/engineering/projects/${encodeURIComponent(projectBinding.projectId)}/sources/ingest-file`,
    {
      method: 'POST',
      body: form,
      cache: 'no-store',
    },
  );
  const ingestPayload = record(await ingestResponse.json());
  if (!ingestResponse.ok || ingestPayload.ok !== true) {
    throw new Error(errorMessage(ingestPayload, `project STEP ingestion HTTP ${ingestResponse.status}`));
  }
  const ingestion = record(ingestPayload.ingestion);
  const sourceDescriptor = record(ingestion.source_descriptor);
  const descriptorMetadata = record(sourceDescriptor.metadata);
  const sourceId = String(sourceDescriptor.source_id || ingestion.source_id || '');
  const contentHash = canonicalHash(sourceDescriptor.content_hash || ingestion.content_hash);
  const ingestRevision = positiveRevision(ingestPayload.revision, 'Project STEP ingestion');
  if (!sourceId) throw new Error('Project STEP ingestion did not return a registered source_id.');
  if (descriptorMetadata.parser_route !== 'step_geometry') {
    throw new Error(`Registered source parser route is ${String(descriptorMetadata.parser_route || 'unavailable')}; STEP geometry is required.`);
  }
  if (record(ingestion.metadata).raw_bytes_in_response === true) {
    throw new Error('Project STEP ingestion violated the no-raw-bytes response boundary.');
  }

  const parseResponse = await fetch(
    `/api/proxy/engineering/projects/${encodeURIComponent(projectBinding.projectId)}/sources/${encodeURIComponent(sourceId)}/parse`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ expected_revision: ingestRevision }),
      cache: 'no-store',
    },
  );
  const parsePayload = record(await parseResponse.json());
  if (!parseResponse.ok || parsePayload.ok !== true) {
    throw new Error(errorMessage(parsePayload, `stored STEP parser HTTP ${parseResponse.status}`));
  }
  const parserRun = record(parsePayload.parser_run);
  const parsedOutput = record(parserRun.parsed_output);
  const geometry = record(parsedOutput.mechanical_geometry);
  const stepModel = record(parsedOutput.step_model);
  const parseRevision = positiveRevision(parsePayload.revision, 'Stored STEP parser');

  if (String(parserRun.source_id || '') !== sourceId || canonicalHash(parserRun.content_hash) !== contentHash) {
    throw new Error('Stored STEP parser identity disagrees with the registered project source.');
  }
  if (String(stepModel.source_id || '') !== sourceId || canonicalHash(stepModel.content_hash) !== contentHash) {
    throw new Error('Stored STEP model identity disagrees with the registered project source.');
  }
  if (parserRun.status !== 'parsed' || parserRun.parser_route !== 'step_geometry') {
    throw new Error(`Registered STEP source parser status is ${String(parserRun.status || 'unknown')}.`);
  }
  if (parserRun.raw_bytes_returned !== false || parserRun.automatic_authorization !== false) {
    throw new Error('Stored parser violated the no-raw-bytes / no-automatic-authorization contract.');
  }
  if (!Object.keys(geometry).length) {
    throw new Error('Stored STEP parser returned no mechanical geometry report.');
  }

  return {
    durable: true,
    projectId: projectBinding.projectId,
    revision: parseRevision,
    sourceId,
    modelId: String(stepModel.model_id || sourceId),
    contentHash,
    content: null,
    mechanicalGeometry: geometry,
  };
}

export type WorkbenchStepImportResult = {
  geometry: Record<string, unknown>;
  mode: 'session_inline' | 'registered_project';
  sessionContent?: string;
  projectRevision?: number;
  registeredSource?: {
    sourceId: string;
    modelId: string;
    contentHash: string;
  };
};

// Compatibility wrapper for the earlier constructor helper contract. New workbench
// code should use importWorkbenchStepSource so project/source provenance remains explicit.
export async function importWorkbenchStepFile(args: {
  file: File;
  candidateId: string;
  resourceId: string;
  projectId: string | null;
  projectRevision: number | null;
}): Promise<WorkbenchStepImportResult> {
  const imported = await importWorkbenchStepSource({
    file: args.file,
    candidateId: args.candidateId as ConstructorCandidateId,
    resourceId: args.resourceId,
    entityId: args.resourceId,
    projectBinding: args.projectId && Number.isInteger(args.projectRevision) && Number(args.projectRevision) >= 1
      ? { projectId: args.projectId, revision: Number(args.projectRevision) }
      : null,
  });
  return imported.durable
    ? {
        geometry: imported.mechanicalGeometry,
        mode: 'registered_project',
        projectRevision: imported.revision ?? undefined,
        registeredSource: {
          sourceId: imported.sourceId,
          modelId: imported.modelId,
          contentHash: imported.contentHash,
        },
      }
    : {
        geometry: imported.mechanicalGeometry,
        mode: 'session_inline',
        sessionContent: imported.content ?? undefined,
      };
}
