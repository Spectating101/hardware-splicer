'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle2,
  FileUp,
  FolderPlus,
  LoaderCircle,
  PauseCircle,
  PlayCircle,
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

type JsonRecord = Record<string, unknown>;
type ProjectResponse = { ok?: boolean; project?: JsonRecord };
type SnapshotResponse = { ok?: boolean; project?: JsonRecord };
type SessionResponse = {
  ok?: boolean;
  revision?: number;
  session?: JsonRecord;
  complete?: boolean;
  received_chunk_count?: number;
};
type FinalizeResponse = {
  ok?: boolean;
  revision?: number;
  session?: JsonRecord;
  ingestion?: JsonRecord;
};

const MAX_FILE_BYTES = 16 * 1024 * 1024;
const DEFAULT_CHUNK_BYTES = 1024 * 1024;

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

async function sha256(value: Blob) {
  const digest = await crypto.subtle.digest('SHA-256', await value.arrayBuffer());
  return `sha256:${Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

export default function ResumableEngineeringUploadsPage() {
  usePageTitle('Resumable Uploads | Hardware Splicer');
  const fileInput = useRef<HTMLInputElement>(null);
  const activeRequest = useRef<XMLHttpRequest | null>(null);
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState('');
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState<'project' | 'hash' | 'upload' | 'finalize' | 'session' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ingestion, setIngestion] = useState<JsonRecord | null>(null);

  const receivedChunks = rows(session?.received_chunks);
  const receivedIndexes = useMemo(
    () => new Set(receivedChunks.map((row) => Number(row.chunk_index))),
    [receivedChunks],
  );
  const chunkCount = Number(session?.chunk_count || 0);
  const chunkSize = Number(session?.chunk_size_bytes || DEFAULT_CHUNK_BYTES);
  const sessionStatus = text(session?.status, 'not created');

  async function createProject() {
    const id = projectId.trim();
    if (!id) return setError('Enter a project ID.');
    setBusy('project');
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
            source: 'resumable_upload_workspace',
            automatic_authorization: false,
            physical_authority_unchanged: true,
          },
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<SnapshotResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not create the project.'));
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
    if (!id) return setError('Enter a project ID.');
    setBusy('project');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not load the project.'));
      }
      const envelope = record((payload as ProjectResponse).project);
      const nextRevision = Number(envelope.revision);
      if (!Number.isInteger(nextRevision) || nextRevision < 1) throw new Error('Project returned no valid revision.');
      setRevision(nextRevision);
      setProjectName(text(record(envelope.snapshot).projectName, id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusy(null);
    }
  }

  async function createSession() {
    if (!revision) return setError('Create or load a revisioned project first.');
    if (!file) return setError('Select a file first.');
    if (file.size < 1 || file.size > MAX_FILE_BYTES) return setError('File must be between 1 byte and 16 MiB.');
    setBusy('hash');
    setError(null);
    setIngestion(null);
    try {
      const contentHash = await sha256(file);
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            total_size_bytes: file.size,
            expected_revision: revision,
            declared_media_type: file.type || null,
            authority_ceiling: 'declared',
            expected_content_hash: contentHash,
            metadata: {
              browser_last_modified_ms: file.lastModified,
              browser_file_type: file.type || null,
              upload_workspace: 'resumable',
            },
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not create the upload session.'));
      }
      const nextSession = record((payload as SessionResponse).session);
      const nextSessionId = text(nextSession.session_id, '');
      setSession(nextSession);
      setSessionId(nextSessionId);
      setProgress(0);
      localStorage.setItem(`hs-upload-session:${projectId.trim()}`, nextSessionId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Session creation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function loadSession() {
    if (!projectId.trim() || !sessionId.trim()) return setError('Enter the project and session IDs.');
    setBusy('session');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions/${encodeURIComponent(sessionId.trim())}`,
        { cache: 'no-store' },
      );
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not load the upload session.'));
      }
      const nextSession = record((payload as SessionResponse).session);
      setSession(nextSession);
      const received = rows(nextSession.received_chunks).reduce((sum, row) => sum + Number(row.size_bytes || 0), 0);
      setProgress(Math.round((received / Number(nextSession.total_size_bytes || 1)) * 100));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Session load failed.');
    } finally {
      setBusy(null);
    }
  }

  function validateSelectedFile() {
    if (!file || !session) throw new Error('Select the original file before resuming.');
    if (file.name !== text(session.filename, '')) throw new Error('Selected filename does not match the session.');
    if (file.size !== Number(session.total_size_bytes)) throw new Error('Selected file size does not match the session.');
  }

  function uploadChunk(index: number, blob: Blob, chunkHash: string, baseBytes: number, totalBytes: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      activeRequest.current = xhr;
      xhr.open(
        'PUT',
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions/${encodeURIComponent(sessionId.trim())}/chunks/${index}`,
      );
      xhr.setRequestHeader('content-type', 'application/octet-stream');
      xhr.setRequestHeader('x-chunk-sha256', chunkHash);
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        setProgress(Math.min(99, Math.round(((baseBytes + event.loaded) / totalBytes) * 100)));
      };
      xhr.onerror = () => reject(new Error(`Chunk ${index} network upload failed.`));
      xhr.onabort = () => reject(new DOMException('Chunk upload cancelled.', 'AbortError'));
      xhr.onload = () => {
        let payload: JsonRecord;
        try {
          payload = JSON.parse(xhr.responseText || '{}') as JsonRecord;
        } catch {
          reject(new Error(`Chunk ${index} returned invalid JSON.`));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300 || payload.ok === false) {
          const detail = record(payload.detail);
          reject(new Error(text(detail.message, `Chunk ${index} failed (${xhr.status}).`)));
          return;
        }
        resolve();
      };
      xhr.send(blob);
    });
  }

  async function uploadMissingChunks() {
    try {
      validateSelectedFile();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'File mismatch.');
      return;
    }
    if (!file || !session) return;
    setBusy('upload');
    setError(null);
    try {
      let confirmedBytes = receivedChunks.reduce((sum, row) => sum + Number(row.size_bytes || 0), 0);
      for (let index = 0; index < Number(session.chunk_count); index += 1) {
        if (receivedIndexes.has(index)) continue;
        const start = index * Number(session.chunk_size_bytes);
        const end = Math.min(file.size, start + Number(session.chunk_size_bytes));
        const blob = file.slice(start, end);
        const chunkHash = await sha256(blob);
        await uploadChunk(index, blob, chunkHash, confirmedBytes, file.size);
        confirmedBytes += blob.size;
        setProgress(Math.round((confirmedBytes / file.size) * 100));
        await loadSessionQuietly();
      }
      await loadSessionQuietly();
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') {
        setError('Active chunk upload cancelled. The completed chunks remain resumable.');
      } else {
        setError(caught instanceof Error ? caught.message : 'Chunk upload failed.');
      }
    } finally {
      activeRequest.current = null;
      setBusy(null);
    }
  }

  async function loadSessionQuietly() {
    const response = await fetch(
      `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions/${encodeURIComponent(sessionId.trim())}`,
      { cache: 'no-store' },
    );
    const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
    if (!response.ok || isProxyFailure(payload)) {
      throw new Error(getProxyErrorMessage(payload, 'Could not refresh the upload session.'));
    }
    setSession(record((payload as SessionResponse).session));
  }

  async function finalizeSession() {
    if (!session) return;
    setBusy('finalize');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions/${encodeURIComponent(sessionId.trim())}/finalize`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: Number(session.expected_revision) }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<FinalizeResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not finalize the upload session.'));
      }
      setSession(record((payload as FinalizeResponse).session));
      setIngestion(record((payload as FinalizeResponse).ingestion));
      setRevision(Number((payload as FinalizeResponse).revision));
      setProgress(100);
      localStorage.removeItem(`hs-upload-session:${projectId.trim()}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Session finalization failed.');
    } finally {
      setBusy(null);
    }
  }

  async function abandonSession() {
    if (!sessionId.trim()) return;
    setBusy('session');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/source-upload-sessions/${encodeURIComponent(sessionId.trim())}`,
        { method: 'DELETE', cache: 'no-store' },
      );
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not abandon the upload session.'));
      }
      setSession(record((payload as SessionResponse).session));
      localStorage.removeItem(`hs-upload-session:${projectId.trim()}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Session abandonment failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1450px]">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/uploads" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering Uploads
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-violet-300/20 bg-violet-300/10 p-3 text-violet-200"><PauseCircle className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Resumable Uploads</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">Pin one project revision, upload exact 1 MiB chunks, resume missing chunks, reconcile the whole-file hash, then commit one source revision.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/source-lab"><Button variant="outline">Source Lab</Button></Link>
            <Link href="/engineering/project-preflight"><Button variant="outline">Project plan</Button></Link>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
            <input value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="project-id" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white" />
            <input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Project name" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white" />
            <Button variant="outline" onClick={loadProject} disabled={busy !== null}><RefreshCw className="mr-2 h-4 w-4" />Load</Button>
            <Button onClick={createProject} disabled={busy !== null}><FolderPlus className="mr-2 h-4 w-4" />Create</Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Project revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">1 MiB chunks</span>
            <span className="rounded-full border border-white/10 px-3 py-1">16 MiB file ceiling</span>
            <span className="rounded-full border border-white/10 px-3 py-1">No project mutation before finalize</span>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>Chunks are temporary transport state. Only final SHA reconciliation and optimistic project commit register a source. No upload session authorizes physical action.</div>
        </div>

        {error ? <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="space-y-5 rounded-3xl border border-white/10 bg-[#07111f] p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-200">1 · Select original file</div>
              <input ref={fileInput} type="file" className="hidden" onChange={(event) => setFile(event.target.files?.[0] || null)} />
              <Button className="mt-4" variant="outline" onClick={() => fileInput.current?.click()}><FileUp className="mr-2 h-4 w-4" />Select file</Button>
              <div className="mt-3 text-sm text-slate-400">{file ? `${file.name} · ${formatBytes(file.size)}` : 'No file selected.'}</div>
              <Button className="mt-4" onClick={createSession} disabled={!revision || !file || busy !== null}>
                {busy === 'hash' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                Hash and create session
              </Button>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-200">2 · Resume session</div>
              <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="upload-session-id" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white" />
                <Button variant="outline" onClick={loadSession} disabled={busy !== null}><RefreshCw className="mr-2 h-4 w-4" />Load session</Button>
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-200">3 · Upload missing chunks</div>
                <div className="text-xs text-slate-400">{progress}%</div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5"><div className="h-full bg-current text-violet-300 transition-[width]" style={{ width: `${progress}%` }} /></div>
              <div className="mt-3 text-xs text-slate-400">{receivedChunks.length} / {chunkCount || '—'} chunks confirmed</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={uploadMissingChunks} disabled={!session || sessionStatus !== 'open' || busy !== null}><UploadCloud className="mr-2 h-4 w-4" />Upload missing chunks</Button>
                {busy === 'upload' ? <Button variant="outline" onClick={() => activeRequest.current?.abort()}><PauseCircle className="mr-2 h-4 w-4" />Cancel active chunk</Button> : null}
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-200">4 · Finalize one project revision</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={finalizeSession} disabled={!session || receivedChunks.length !== chunkCount || sessionStatus !== 'open' || busy !== null}>
                  {busy === 'finalize' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                  Reconcile and finalize
                </Button>
                <Button variant="outline" onClick={abandonSession} disabled={!session || sessionStatus !== 'open' || busy !== null}><Trash2 className="mr-2 h-4 w-4" />Abandon session</Button>
              </div>
            </div>
          </section>

          <aside className="space-y-5">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="text-sm font-semibold text-white">Session truth</div>
              <div className="mt-4 space-y-2 text-xs text-slate-400">
                <div>Status: <span className="text-slate-200">{sessionStatus}</span></div>
                <div>Session: <span className="break-all font-mono text-[10px] text-slate-300">{sessionId || '—'}</span></div>
                <div>Pinned revision: <span className="text-slate-200">{text(session?.expected_revision)}</span></div>
                <div>Expected hash: <span className="break-all font-mono text-[10px] text-slate-300">{text(session?.expected_content_hash)}</span></div>
                <div>Expires: <span className="text-slate-200">{text(session?.expires_at)}</span></div>
              </div>
            </section>
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="text-sm font-semibold text-white">Final source</div>
              {!ingestion ? <div className="mt-4 text-sm leading-6 text-slate-500">Finalize the session to register one source.</div> : <pre className="mt-4 max-h-[480px] overflow-auto rounded-2xl border border-white/10 bg-[#040b14] p-4 text-[11px] leading-5 text-slate-300">{JSON.stringify(ingestion, null, 2)}</pre>}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
