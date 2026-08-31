'use client';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function errorMessage(payload: Record<string, unknown>, fallback: string) {
  const detail = record(payload.detail);
  return String(detail.message || payload.error || fallback);
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

export async function importWorkbenchStepFile(args: {
  file: File;
  candidateId: string;
  resourceId: string;
  projectId: string | null;
  projectRevision: number | null;
}): Promise<WorkbenchStepImportResult> {
  const modelId = `${args.candidateId}-${args.resourceId}`;

  if (!args.projectId) {
    const content = await args.file.text();
    const response = await fetch('/api/proxy/engineering/mechanical/geometry/parse', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        project_id: 'deck-001',
        sources: [{
          source_id: args.file.name,
          model_id: modelId,
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
    return {
      geometry: record(payload.mechanical_geometry),
      mode: 'session_inline',
      sessionContent: content,
    };
  }

  if (!Number.isInteger(args.projectRevision) || Number(args.projectRevision) < 1) {
    throw new Error('Durable project binding has no valid revision; refusing to register STEP source.');
  }

  const form = new FormData();
  form.set('expected_revision', String(args.projectRevision));
  form.set('authority_ceiling', 'declared');
  form.set('metadata_json', JSON.stringify({
    workbench_resource_id: args.resourceId,
    workbench_candidate_id: args.candidateId,
  }));
  form.set('file', args.file);

  const ingestResponse = await fetch(
    `/api/proxy/engineering/projects/${encodeURIComponent(args.projectId)}/sources/ingest-file`,
    {
      method: 'POST',
      body: form,
      cache: 'no-store',
    },
  );
  const ingestPayload = record(await ingestResponse.json());
  if (!ingestResponse.ok || ingestPayload.ok !== true) {
    throw new Error(errorMessage(ingestPayload, `registered STEP ingest HTTP ${ingestResponse.status}`));
  }

  const ingestion = record(ingestPayload.ingestion);
  const descriptor = record(ingestion.source_descriptor);
  const metadata = record(descriptor.metadata);
  const sourceId = String(descriptor.source_id || ingestion.source_id || '');
  const contentHash = String(descriptor.content_hash || ingestion.content_hash || '');
  const ingestRevision = Number(ingestPayload.revision);
  if (!sourceId || !/^sha256:[0-9a-f]{64}$/.test(contentHash)) {
    throw new Error('Registered source response did not return canonical source_id + sha256 content_hash.');
  }
  if (metadata.parser_route !== 'step_geometry') {
    throw new Error(`Registered source parser route is ${String(metadata.parser_route || 'unavailable')}; STEP geometry is required.`);
  }
  if (!Number.isInteger(ingestRevision) || ingestRevision < 1) {
    throw new Error('Registered source response did not return a valid project revision.');
  }

  const parseResponse = await fetch(
    `/api/proxy/engineering/projects/${encodeURIComponent(args.projectId)}/sources/${encodeURIComponent(sourceId)}/parse`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ expected_revision: ingestRevision }),
      cache: 'no-store',
    },
  );
  const parsePayload = record(await parseResponse.json());
  if (!parseResponse.ok || parsePayload.ok !== true) {
    throw new Error(errorMessage(parsePayload, `stored STEP parse HTTP ${parseResponse.status}`));
  }

  const parserRun = record(parsePayload.parser_run);
  const parsedOutput = record(parserRun.parsed_output);
  const stepModel = record(parsedOutput.step_model);
  const geometry = record(parsedOutput.mechanical_geometry);
  const parsedRevision = Number(parsePayload.revision);
  if (parserRun.status !== 'parsed' || parserRun.parser_route !== 'step_geometry') {
    throw new Error('Stored source parser did not produce STEP geometry evidence.');
  }
  if (parserRun.raw_bytes_returned !== false || parserRun.automatic_authorization !== false) {
    throw new Error('Stored parser violated the no-raw-bytes / no-automatic-authorization contract.');
  }
  if (String(parserRun.source_id || '') !== sourceId || String(parserRun.content_hash || '') !== contentHash) {
    throw new Error('Stored parser source identity disagrees with the registered descriptor.');
  }
  if (String(stepModel.source_id || '') !== sourceId || String(stepModel.content_hash || '') !== contentHash) {
    throw new Error('Stored STEP model identity disagrees with the registered descriptor.');
  }
  if (!Number.isInteger(parsedRevision) || parsedRevision < ingestRevision) {
    throw new Error('Stored parser response did not return a valid monotonic project revision.');
  }
  if (!Object.keys(geometry).length) {
    throw new Error('Stored STEP parser returned no mechanical geometry report.');
  }

  return {
    geometry,
    mode: 'registered_project',
    projectRevision: parsedRevision,
    registeredSource: {
      sourceId,
      modelId: String(stepModel.model_id || sourceId),
      contentHash,
    },
  };
}
