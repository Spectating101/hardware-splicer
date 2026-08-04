'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle2,
  FileUp,
  FolderPlus,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
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

type JsonRecord = Record<string, unknown>;
type ProjectResponse = { ok?: boolean; project?: JsonRecord };
type SnapshotResponse = { ok?: boolean; project?: JsonRecord };
type UploadResponse = {
  ok?: boolean;
  registered?: boolean;
  revision?: number;
  ingestion?: JsonRecord;
  error?: string;
  detail?: unknown;
};

type QueueStatus = 'pending' | 'uploading' | 'uploaded' | 'failed' | 'cancelled';

type QueueItem = {
  id: string;
  file: File;
  status: QueueStatus;
  progress: number;
  error?: string;
  result?: JsonRecord;
};

const MAX_FILE_BYTES = 16 * 1024 * 1024;

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function fileId(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}:${crypto.randomUUID()}`;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

export default function EngineeringUploadsPage() {
  usePageTitle('Engineering Uploads | Hardware Splicer');
  const fileInput = useRef<HTMLInputElement>(null);
  const activeRequest = useRef<XMLHttpRequest | null>(null);
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [busy, setBusy] = useState<'create' | 'load' | 'upload' | null>(null);
  const [error, setError] = useState<string | null>(null);

  function setItem(id: string, update: Partial<QueueItem>) {
    setQueue((current) => current.map((item) => item.id === id ? { ...item, ...update } : item));
  }

  function addFiles(files: File[]) {
    const next = files.map((file): QueueItem => ({
      id: fileId(file),
      file,
      status: file.size > MAX_FILE_BYTES ? 'failed' : 'pending',
      progress: 0,
      error: file.size > MAX_FILE_BYTES
        ? 'File exceeds the current 16 MiB multipart limit.'
        : undefined,
    }));
    setQueue((current) => [...current, ...next]);
  }

  async function createProject() {
    const id = projectId.trim();
    if (!id) {
      setError('Enter a project ID.');
      return;
    }
    setBusy('create');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id)}/snapshot`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          expected_revision: 0,
          snapshot: {
            projectId: id,
            projectName: projectName.trim() || id,
            mode: 'greenfield',
            currentStage: 'source_intake',
            engineeringSources: [],
            engineeringSourceUploads: [],
            engineeringSourceParserRuns: [],
            engineeringParsedSources: [],
            engineeringReadiness: {
              fabrication_authorized: false,
              flash_authorized: false,
              power_on_authorized: false,
              motion_authorized: false,
              release_authorized: false,
            },
          },
          metadata: {
            source: 'engineering_multipart_upload_workspace',
            automatic_authorization: false,
            physical_authority_unchanged: true,
          },
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<SnapshotResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not create the project.'));
      }
      const envelope = record((payload as SnapshotResponse).project);
      setRevision(Number(envelope.revision));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project creation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function loadProject() {
    const id = projectId.trim();
    if (!id) {
      setError('Enter a project ID.');
      return;
    }
    setBusy('load');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id)}`, {
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load the project.'));
      }
      const envelope = record((payload as ProjectResponse).project);
      const nextRevision = Number(envelope.revision);
      if (!Number.isInteger(nextRevision) || nextRevision < 1) {
        throw new Error('The project returned no valid revision.');
      }
      setRevision(nextRevision);
      const snapshot = record(envelope.snapshot);
      setProjectName(text(snapshot.projectName, id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusy(null);
    }
  }

  function uploadOne(item: QueueItem, expectedRevision: number): Promise<number> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      activeRequest.current = xhr;
      const form = new FormData();
      form.append('file', item.file, item.file.name);
      form.append('expected_revision', String(expectedRevision));
      form.append('authority_ceiling', 'declared');
      form.append('captured_at', '');
      form.append('metadata_json', JSON.stringify({
        browser_last_modified_ms: item.file.lastModified,
        browser_file_type: item.file.type || null,
        upload_workspace: 'multipart',
      }));

      xhr.open(
        'POST',
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/sources/ingest-file`,
      );
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        setItem(item.id, {
          status: 'uploading',
          progress: Math.min(99, Math.round((event.loaded / event.total) * 100)),
        });
      };
      xhr.onerror = () => reject(new Error('Network upload failed.'));
      xhr.onabort = () => reject(new DOMException('Upload cancelled.', 'AbortError'));
      xhr.onload = () => {
        let payload: UploadResponse;
        try {
          payload = JSON.parse(xhr.responseText || '{}') as UploadResponse;
        } catch {
          reject(new Error(`Upload returned invalid JSON (${xhr.status}).`));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300 || payload.ok === false) {
          const detail = record(payload.detail);
          reject(new Error(text(detail.message, payload.error || `Upload failed (${xhr.status}).`)));
          return;
        }
        const nextRevision = Number(payload.revision || expectedRevision);
        setItem(item.id, {
          status: 'uploaded',
          progress: 100,
          result: record(payload.ingestion),
          error: undefined,
        });
        resolve(nextRevision);
      };
      setItem(item.id, { status: 'uploading', progress: 1, error: undefined });
      xhr.send(form);
    });
  }

  async function uploadPending() {
    if (!revision) {
      setError('Create or load a revisioned project first.');
      return;
    }
    const pending = queue.filter((item) => item.status === 'pending' || item.status === 'failed' || item.status === 'cancelled')
      .filter((item) => item.file.size <= MAX_FILE_BYTES);
    if (!pending.length) return;
    setBusy('upload');
    setError(null);
    let nextRevision = revision;
    try {
      for (const item of pending) {
        try {
          nextRevision = await uploadOne(item, nextRevision);
          setRevision(nextRevision);
        } catch (caught) {
          if (caught instanceof DOMException && caught.name === 'AbortError') {
            setItem(item.id, { status: 'cancelled', error: 'Upload cancelled.' });
            break;
          }
          const message = caught instanceof Error ? caught.message : 'Upload failed.';
          setItem(item.id, { status: 'failed', error: message });
          if (message.toLowerCase().includes('revision')) {
            setError('Project revision changed. Reload the project before retrying.');
            break;
          }
        } finally {
          activeRequest.current = null;
        }
      }
    } finally {
      setBusy(null);
    }
  }

  function cancelUpload() {
    activeRequest.current?.abort();
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1450px]">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering workspace
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200"><UploadCloud className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Engineering Uploads</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
                  Send real project files through bounded multipart transport with server hashing, optimistic revisions, network progress and cancellation.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/sources"><Button variant="outline">Legacy source intake</Button></Link>
            <Link href="/engineering/source-lab"><Button variant="outline">Source Lab</Button></Link>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
            <input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="project-id"
              className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white"
            />
            <input
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="Project name"
              className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white"
            />
            <Button variant="outline" onClick={loadProject} disabled={busy !== null}>
              {busy === 'load' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Load
            </Button>
            <Button onClick={createProject} disabled={busy !== null}>
              {busy === 'create' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FolderPlus className="mr-2 h-4 w-4" />}
              Create
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Multipart transport</span>
            <span className="rounded-full border border-white/10 px-3 py-1">16 MiB per file</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Declared maximum authority</span>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>Upload proves byte identity and retention only. It does not authorize fabrication, flashing, power-on, motion, or release.</div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        ) : null}

        <section
          className="mt-6 rounded-3xl border border-dashed border-cyan-300/25 bg-cyan-300/[0.04] p-8 text-center"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            addFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <FileUp className="mx-auto h-9 w-9 text-cyan-200" />
          <div className="mt-3 text-base font-semibold text-white">Drop engineering files here</div>
          <div className="mt-2 text-sm text-slate-400">Files are sent directly as multipart bytes. The browser does not base64-encode them.</div>
          <input
            ref={fileInput}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => {
              addFiles(Array.from(event.target.files || []));
              event.target.value = '';
            }}
          />
          <Button className="mt-5" variant="outline" onClick={() => fileInput.current?.click()}>
            Select files
          </Button>
        </section>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          {busy === 'upload' ? (
            <Button variant="outline" onClick={cancelUpload}><X className="mr-2 h-4 w-4" />Cancel active upload</Button>
          ) : null}
          <Button onClick={uploadPending} disabled={!revision || busy !== null || !queue.length}>
            {busy === 'upload' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <UploadCloud className="mr-2 h-4 w-4" />}
            Upload pending
          </Button>
        </div>

        <section className="mt-6 space-y-3">
          {queue.map((item) => {
            const classification = record(item.result?.classification);
            return (
              <article key={item.id} className="rounded-2xl border border-white/10 bg-[#07111f] p-4">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {item.status === 'uploaded' ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : item.status === 'failed' ? <XCircle className="h-4 w-4 text-rose-300" /> : <FileUp className="h-4 w-4 text-slate-400" />}
                      <div className="truncate text-sm font-semibold text-white">{item.file.name}</div>
                      <span className="text-xs text-slate-500">{formatBytes(item.file.size)}</span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5">
                      <div className="h-full bg-current text-cyan-300 transition-[width]" style={{ width: `${item.progress}%` }} />
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      {item.error || `${item.status} · ${item.progress}%`}
                    </div>
                    {item.result ? (
                      <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:grid-cols-4">
                        <div>Kind: <span className="text-slate-200">{text(classification.kind)}</span></div>
                        <div>Parser: <span className="text-slate-200">{text(classification.parser_disposition)}</span></div>
                        <div>Hash: <span className="break-all font-mono text-[10px] text-slate-300">{text(item.result.content_hash)}</span></div>
                        <div>Blob: <span className="break-all font-mono text-[10px] text-slate-300">{text(item.result.blob_ref)}</span></div>
                      </div>
                    ) : null}
                  </div>
                  <div className="flex gap-2">
                    {(item.status === 'failed' || item.status === 'cancelled') ? (
                      <Button variant="outline" size="sm" onClick={() => setItem(item.id, { status: 'pending', progress: 0, error: undefined })}>
                        <RotateCcw className="mr-2 h-3.5 w-3.5" />Retry
                      </Button>
                    ) : null}
                    {item.status !== 'uploading' ? (
                      <Button variant="ghost" size="sm" onClick={() => setQueue((current) => current.filter((row) => row.id !== item.id))}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    ) : null}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
