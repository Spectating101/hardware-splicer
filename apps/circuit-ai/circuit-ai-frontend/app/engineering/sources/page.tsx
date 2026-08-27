'use client';

import { useMemo, useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleOff,
  Download,
  FileArchive,
  FileCheck2,
  FileUp,
  FolderOpen,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UploadCloud,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

const MAX_FILE_BYTES = 16 * 1024 * 1024;

type JsonRecord = Record<string, unknown>;
type UploadState = 'queued' | 'reading' | 'uploading' | 'complete' | 'failed' | 'cancelled';
type UploadResult = {
  source_id?: string;
  original_filename?: string;
  content_hash?: string;
  size_bytes?: number;
  blob_ref?: string;
  duplicate_blob?: boolean;
  classification?: {
    kind?: string;
    media_type?: string;
    parser_disposition?: string;
    parser_route?: string | null;
    structured_format?: string | null;
    limitations?: string[];
  };
  source_descriptor?: JsonRecord;
};
type UploadRow = {
  id: string;
  file: File;
  state: UploadState;
  progress: number;
  error?: string;
  result?: UploadResult;
};
type ProjectEnvelope = {
  project_id?: string;
  revision?: number;
  saved_at?: string;
  snapshot?: JsonRecord;
};
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type IngestionResponse = {
  ok?: boolean;
  registered?: boolean;
  project_id?: string;
  revision?: number;
  ingestion?: UploadResult;
};

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function fileToBase64(file: File, onProgress: (progress: number) => void) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    reader.onerror = () => reject(reader.error || new Error('The browser could not read this file.'));
    reader.onabort = () => reject(new DOMException('File reading was cancelled.', 'AbortError'));
    reader.onload = () => {
      const value = String(reader.result || '');
      const comma = value.indexOf(',');
      if (comma < 0) reject(new Error('The browser returned an invalid file encoding.'));
      else resolve(value.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

function xhrMessage(value: unknown, fallback: string) {
  const payload = record(value);
  const detail = record(payload.detail);
  return String(detail.message || payload.message || payload.error || fallback);
}

function sendUpload(
  url: string,
  payload: JsonRecord,
  onProgress: (progress: number) => void,
  onReady: (request: XMLHttpRequest) => void,
) {
  return new Promise<IngestionResponse>((resolve, reject) => {
    const request = new XMLHttpRequest();
    onReady(request);
    request.open('POST', url);
    request.setRequestHeader('content-type', 'application/json');
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onerror = () => reject(new Error('The upload connection failed.'));
    request.onabort = () => reject(new DOMException('Upload cancelled.', 'AbortError'));
    request.onload = () => {
      let parsed: unknown = {};
      try {
        parsed = JSON.parse(request.responseText || '{}');
      } catch {
        parsed = {};
      }
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(xhrMessage(parsed, `Upload failed with HTTP ${request.status}.`)));
        return;
      }
      resolve(parsed as IngestionResponse);
    };
    request.send(JSON.stringify(payload));
  });
}

function stateLabel(state: UploadState) {
  if (state === 'queued') return 'Queued';
  if (state === 'reading') return 'Reading';
  if (state === 'uploading') return 'Uploading';
  if (state === 'complete') return 'Registered';
  if (state === 'cancelled') return 'Cancelled';
  return 'Failed';
}

export default function EngineeringSourcesPage() {
  usePageTitle('Engineering Sources | Hardware Splicer');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeRequests = useRef(new Map<string, XMLHttpRequest>());
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [projectReady, setProjectReady] = useState(false);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [registeredSources, setRegisteredSources] = useState<JsonRecord[]>([]);
  const [projectBusy, setProjectBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completedCount = uploads.filter((row) => row.state === 'complete').length;
  const failedCount = uploads.filter((row) => row.state === 'failed').length;
  const queuedCount = uploads.filter((row) => ['queued', 'failed', 'cancelled'].includes(row.state)).length;
  const registeredManifest = useMemo(() => ({
    schema_version: 'hardware_splicer.engineering_source_manifest.v1',
    project_id: projectId,
    revision,
    engineering_sources: registeredSources,
    authority_raised: false,
  }), [projectId, registeredSources, revision]);

  function patchUpload(id: string, patch: Partial<UploadRow>) {
    setUploads((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row));
  }

  function addFiles(files: File[]) {
    const additions = files.map((file, index): UploadRow => ({
      id: `${file.name}-${file.lastModified}-${file.size}-${Date.now()}-${index}`,
      file,
      state: file.size > MAX_FILE_BYTES ? 'failed' : 'queued',
      progress: 0,
      error: file.size > MAX_FILE_BYTES ? 'File exceeds the current 16 MiB ingestion limit.' : undefined,
    }));
    setUploads((current) => [...current, ...additions]);
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files || []));
    event.target.value = '';
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    addFiles(Array.from(event.dataTransfer.files || []));
  }

  async function createProject() {
    setProjectBusy(true);
    setError(null);
    try {
      if (!projectId.trim()) throw new Error('Project ID is required.');
      if (!projectName.trim()) throw new Error('Project name is required.');
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/snapshot`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          expected_revision: 0,
          snapshot: {
            snapshot_schema_version: 'hardware_splicer.engineering_project_snapshot.v1',
            projectId: projectId.trim(),
            projectName: projectName.trim(),
            mode: 'greenfield',
            currentStage: 'source_intake',
            engineeringSourceUploads: [],
            engineeringSources: [],
            engineeringReadiness: {
              status: 'blocked',
              fabrication_authorized: false,
              flash_authorized: false,
              power_on_authorized: false,
              motion_authorized: false,
              release_authorized: false,
            },
          },
          metadata: {
            source: 'engineering_sources_workspace',
            physical_authority_unchanged: true,
          },
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not create the project.'));
      }
      const envelope = (payload as ProjectResponse).project || {};
      setRevision(Number(envelope.revision || 1));
      setProjectReady(true);
      setRegisteredSources([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project creation failed.');
    } finally {
      setProjectBusy(false);
    }
  }

  async function loadProject() {
    setProjectBusy(true);
    setError(null);
    try {
      if (!projectId.trim()) throw new Error('Project ID is required.');
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load the project.'));
      }
      const envelope = (payload as ProjectResponse).project || {};
      const snapshot = record(envelope.snapshot);
      setProjectName(String(snapshot.projectName || snapshot.projectId || projectId.trim()));
      setRevision(Number(envelope.revision || 0));
      setRegisteredSources(rows(snapshot.engineeringSources));
      setProjectReady(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project loading failed.');
    } finally {
      setProjectBusy(false);
    }
  }

  async function uploadPending() {
    if (!projectReady || revision === null) {
      setError('Create or load a revisioned project before uploading files.');
      return;
    }
    const pending = uploads.filter((row) => ['queued', 'failed', 'cancelled'].includes(row.state) && row.file.size <= MAX_FILE_BYTES);
    if (!pending.length) return;
    setUploading(true);
    setError(null);
    let nextRevision = revision;

    for (const row of pending) {
      try {
        patchUpload(row.id, { state: 'reading', progress: 0, error: undefined, result: undefined });
        const contentBase64 = await fileToBase64(row.file, (progress) => {
          patchUpload(row.id, { progress: Math.round(progress * 30) });
        });
        patchUpload(row.id, { state: 'uploading', progress: 30 });
        const payload = await sendUpload(
          `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/sources/ingest`,
          {
            filename: row.file.name,
            content_base64: contentBase64,
            declared_media_type: row.file.type || null,
            authority_ceiling: 'declared',
            expected_revision: nextRevision,
            metadata: {
              browser_last_modified_ms: row.file.lastModified,
              browser_relative_path: row.file.webkitRelativePath || null,
            },
          },
          (progress) => patchUpload(row.id, { progress: 30 + Math.round(progress * 70) }),
          (request) => activeRequests.current.set(row.id, request),
        );
        activeRequests.current.delete(row.id);
        if (!payload.ok || !payload.ingestion) throw new Error('Hardware Splicer returned no ingestion result.');
        nextRevision = Number(payload.revision || nextRevision);
        setRevision(nextRevision);
        const descriptor = record(payload.ingestion.source_descriptor);
        if (Object.keys(descriptor).length) {
          setRegisteredSources((current) => current.some((source) => source.source_id === descriptor.source_id)
            ? current
            : [...current, descriptor]);
        }
        patchUpload(row.id, { state: 'complete', progress: 100, result: payload.ingestion });
      } catch (caught) {
        activeRequests.current.delete(row.id);
        const cancelled = caught instanceof DOMException && caught.name === 'AbortError';
        patchUpload(row.id, {
          state: cancelled ? 'cancelled' : 'failed',
          error: caught instanceof Error ? caught.message : 'Upload failed.',
        });
        if (!cancelled && caught instanceof Error && caught.message.toLowerCase().includes('revision')) {
          setError('The project revision changed during upload. Reload the project before retrying remaining files.');
          break;
        }
      }
    }
    setUploading(false);
  }

  function cancelUpload(id: string) {
    activeRequests.current.get(id)?.abort();
    patchUpload(id, { state: 'cancelled', error: 'Cancelled by the operator.' });
  }

  return (
    <main className="min-h-screen bg-[#040b14] text-slate-100">
      <div className="mx-auto max-w-[1450px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/preflight" className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> HS Preflight
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200"><UploadCloud className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Engineering Sources</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">Create or load a revisioned project, attach real files, and inspect the server-computed identity and bounded parser disposition.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => downloadJson(`${projectId || 'hardware-splicer'}-source-manifest.json`, registeredManifest)} disabled={!registeredSources.length}>
              <Download className="mr-2 h-4 w-4" />Download manifest
            </Button>
            <Button onClick={uploadPending} disabled={!projectReady || uploading || queuedCount === 0}>
              {uploading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FileUp className="mr-2 h-4 w-4" />}
              Upload pending
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /><div>{error}</div>
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]">
          <section className="space-y-5 rounded-3xl border border-white/10 bg-[#07111f] p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Project boundary</div>
              <label className="mt-4 block text-xs font-medium text-slate-300">Project ID</label>
              <input value={projectId} onChange={(event) => { setProjectId(event.target.value); setProjectReady(false); setRevision(null); }} placeholder="inspection-rover-r1" className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40" />
              <label className="mt-4 block text-xs font-medium text-slate-300">Project name</label>
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Indoor inspection rover" className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40" />
              <div className="mt-4 flex gap-2">
                <Button onClick={createProject} disabled={projectBusy} className="flex-1">{projectBusy ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}Create</Button>
                <Button variant="outline" onClick={loadProject} disabled={projectBusy} className="flex-1"><FolderOpen className="mr-2 h-4 w-4" />Load</Button>
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Current state</div>
                  <div className="mt-2 text-sm text-white">{projectReady ? projectName || projectId : 'No project loaded'}</div>
                </div>
                <div className={`rounded-full border px-3 py-1 text-xs ${projectReady ? 'border-emerald-300/20 bg-emerald-300/10 text-emerald-100' : 'border-white/10 text-slate-500'}`}>Revision {revision ?? '—'}</div>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-xl font-semibold text-white">{completedCount}</div><div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">Registered</div></div>
                <div className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-xl font-semibold text-white">{queuedCount}</div><div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">Pending</div></div>
                <div className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-xl font-semibold text-white">{failedCount}</div><div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">Failed</div></div>
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="flex items-start gap-3 rounded-2xl border border-amber-300/15 bg-amber-300/[0.06] p-4">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" />
                <div className="text-xs leading-5 text-slate-300">Uploads enter no higher than declared authority. Hashing and storage do not authorize fabrication, flashing, power-on, motion or release.</div>
              </div>
              <div className="mt-3 text-[11px] leading-5 text-slate-500">Current transport is bounded base64, one file per request, up to 16 MiB. Archives are retained but not extracted.</div>
            </div>
          </section>

          <section className="min-w-0 rounded-3xl border border-white/10 bg-[#07111f] p-5">
            <input ref={fileInputRef} type="file" multiple onChange={handleFiles} className="hidden" />
            <div
              onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              className={`flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed px-6 text-center transition ${dragActive ? 'border-cyan-300/50 bg-cyan-300/10' : 'border-white/15 bg-[#040b14] hover:border-cyan-300/30'}`}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="h-9 w-9 text-cyan-200" />
              <div className="mt-4 text-base font-semibold text-white">Drop engineering files here</div>
              <div className="mt-2 text-sm text-slate-400">URDF, SDF, MJCF, STEP, KiCad, firmware, PDF, image, video, JSON, CSV or unknown binary.</div>
            </div>

            <div className="mt-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Upload queue</h2>
                <p className="mt-1 text-xs text-slate-500">Files are processed sequentially so every registration uses the latest optimistic revision.</p>
              </div>
              <button type="button" onClick={() => setUploads((current) => current.filter((row) => row.state === 'complete'))} className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white"><Trash2 className="h-3.5 w-3.5" />Clear pending</button>
            </div>

            <div className="mt-4 space-y-3">
              {uploads.length ? uploads.map((row) => {
                const classification = row.result?.classification;
                const complete = row.state === 'complete';
                const failed = row.state === 'failed';
                return (
                  <div key={row.id} className="rounded-2xl border border-white/10 bg-[#040b14] p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          {complete ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-200" /> : failed ? <AlertTriangle className="h-4 w-4 shrink-0 text-rose-200" /> : row.state === 'cancelled' ? <CircleOff className="h-4 w-4 shrink-0 text-slate-400" /> : <FileArchive className="h-4 w-4 shrink-0 text-cyan-200" />}
                          <div className="truncate text-sm font-medium text-white">{row.file.name}</div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{formatBytes(row.file.size)} · {row.file.type || 'unknown media type'}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${complete ? 'border-emerald-300/20 bg-emerald-300/10 text-emerald-100' : failed ? 'border-rose-300/20 bg-rose-300/10 text-rose-100' : 'border-white/10 text-slate-400'}`}>{stateLabel(row.state)}</span>
                        {row.state === 'uploading' ? <button type="button" onClick={() => cancelUpload(row.id)} className="text-xs text-rose-200 hover:text-white">Cancel</button> : null}
                        {['queued', 'failed', 'cancelled'].includes(row.state) ? <button type="button" onClick={() => setUploads((current) => current.filter((item) => item.id !== row.id))} className="text-slate-500 hover:text-rose-200"><Trash2 className="h-4 w-4" /></button> : null}
                      </div>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5"><div className="h-full bg-cyan-200 transition-all" style={{ width: `${row.progress}%` }} /></div>
                    {row.error ? <div className="mt-3 text-xs leading-5 text-rose-200">{row.error}</div> : null}
                    {classification ? (
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <div className="rounded-xl border border-white/10 p-3">
                          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Classification</div>
                          <div className="mt-2 text-sm text-white">{classification.kind || 'unknown'}</div>
                          <div className="mt-1 text-xs text-slate-500">{classification.media_type || 'unknown'} · {classification.parser_disposition || 'inventory_only'}</div>
                        </div>
                        <div className="rounded-xl border border-white/10 p-3">
                          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Identity</div>
                          <div className="mt-2 break-all font-mono text-[11px] text-cyan-100">{row.result?.content_hash || '—'}</div>
                          <div className="mt-1 break-all text-[11px] text-slate-500">{row.result?.blob_ref || '—'}</div>
                        </div>
                        {classification.limitations?.length ? <div className="md:col-span-2 rounded-xl border border-amber-300/15 bg-amber-300/[0.05] p-3 text-xs leading-5 text-amber-100">{classification.limitations.join(' ')}</div> : null}
                      </div>
                    ) : null}
                  </div>
                );
              }) : (
                <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-white/8 bg-black/10 px-6 text-center">
                  <FileUp className="h-8 w-8 text-slate-600" />
                  <div className="mt-4 text-sm font-medium text-slate-300">No files queued</div>
                  <div className="mt-2 max-w-lg text-xs leading-5 text-slate-500">Create or load a project, then add the files that define the real engineering source boundary.</div>
                </div>
              )}
            </div>

            {projectReady ? (
              <div className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-5">
                <Link href="/engineering/preflight"><Button variant="outline"><RefreshCw className="mr-2 h-4 w-4" />Return to Preflight</Button></Link>
                <Link href="/engineering"><Button variant="outline">Open Project inspector</Button></Link>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}
