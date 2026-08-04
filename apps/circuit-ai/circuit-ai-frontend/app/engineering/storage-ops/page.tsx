'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Database,
  FileWarning,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
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
type AuditResponse = {
  ok?: boolean;
  project_revision?: number;
  audit?: JsonRecord;
};
type CleanupResponse = AuditResponse & { cleanup?: JsonRecord };

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

function formatBytes(value: unknown) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

export default function SourceStorageOperationsPage() {
  usePageTitle('Storage Ops | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [projectRevision, setProjectRevision] = useState<number | null>(null);
  const [audit, setAudit] = useState<JsonRecord | null>(null);
  const [cleanup, setCleanup] = useState<JsonRecord | null>(null);
  const [minimumAgeHours, setMinimumAgeHours] = useState('24');
  const [includeCorrupt, setIncludeCorrupt] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState<'audit' | 'dry-run' | 'apply' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const summary = record(audit?.summary);
  const blobs = rows(audit?.blobs);
  const sessions = rows(audit?.sessions);
  const orphanBlobs = useMemo(() => blobs.filter((row) => row.orphan === true), [blobs]);
  const expiredSessions = useMemo(() => sessions.filter((row) => row.expired === true), [sessions]);

  async function loadAudit() {
    const id = projectId.trim();
    if (!id) return setError('Enter a project ID.');
    setBusy('audit');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}/source-storage/audit`,
        { cache: 'no-store' },
      );
      const payload = await readJsonPayload<AuditResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not audit project source storage.'));
      }
      setAudit(record((payload as AuditResponse).audit));
      setProjectRevision(Number((payload as AuditResponse).project_revision));
      setCleanup(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Storage audit failed.');
    } finally {
      setBusy(null);
    }
  }

  async function runCleanup(dryRun: boolean) {
    const id = projectId.trim();
    if (!id) return setError('Enter a project ID.');
    if (!dryRun && confirmation !== id) {
      return setError('Type the exact project ID before destructive cleanup.');
    }
    const minimumAge = Number(minimumAgeHours);
    if (!Number.isFinite(minimumAge) || minimumAge < 1) {
      return setError('Minimum age must be at least one hour.');
    }
    setBusy(dryRun ? 'dry-run' : 'apply');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}/source-storage/cleanup`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            dry_run: dryRun,
            minimum_age_hours: minimumAge,
            delete_orphan_blobs: true,
            clean_expired_session_chunks: true,
            include_corrupt_orphans: includeCorrupt,
            confirm_project_id: dryRun ? '' : confirmation,
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<CleanupResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Could not execute source storage cleanup.'));
      }
      setCleanup(record((payload as CleanupResponse).cleanup));
      setAudit(record((payload as CleanupResponse).audit));
      setProjectRevision(Number((payload as CleanupResponse).project_revision));
      if (!dryRun) setConfirmation('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Storage cleanup failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering workspace
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-amber-300/20 bg-amber-300/10 p-3 text-amber-200"><Database className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Source Storage Ops</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">Audit project blob reachability and temporary upload sessions. Preview cleanup first; destructive apply requires the exact project ID.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/resumable-uploads"><Button variant="outline">Resumable uploads</Button></Link>
            <Link href="/engineering/source-lab"><Button variant="outline">Source Lab</Button></Link>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <input value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="project-id" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white" />
            <Button onClick={loadAudit} disabled={busy !== null}>{busy === 'audit' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Audit storage</Button>
          </div>
          <div className="mt-3 text-xs text-slate-400">Project revision {projectRevision ?? '—'} · audit and cleanup do not create a project revision</div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>Referenced blobs are never cleanup candidates. Corrupt orphans remain report-only unless explicitly included. Automatic deletion is disabled.</div>
        </div>

        {error ? <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            ['Stored blobs', summary.stored_blob_count, formatBytes(summary.stored_blob_bytes)],
            ['Orphan blobs', summary.orphan_blob_count, formatBytes(summary.orphan_blob_bytes)],
            ['Corrupt blobs', summary.corrupt_blob_count, 'report boundary'],
            ['Temporary chunks', summary.session_count, formatBytes(summary.temporary_chunk_bytes)],
          ].map(([label, value, note]) => (
            <div key={String(label)} className="rounded-2xl border border-white/10 bg-[#07111f] p-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</div>
              <div className="mt-2 text-2xl font-semibold text-white">{text(value, '0')}</div>
              <div className="mt-1 text-xs text-slate-400">{note}</div>
            </div>
          ))}
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_430px]">
          <section className="space-y-5">
            <div className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center justify-between"><div className="text-sm font-semibold text-white">Blob audit</div><div className="text-xs text-slate-500">{blobs.length} records</div></div>
              <div className="mt-4 space-y-3">
                {blobs.length === 0 ? <div className="text-sm text-slate-500">No source blobs found.</div> : blobs.map((blob) => (
                  <div key={text(blob.blob_ref)} className="rounded-2xl border border-white/10 bg-[#040b14] p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      {blob.referenced ? <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2 py-1 text-[10px] text-emerald-200">referenced</span> : <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-1 text-[10px] text-amber-200">orphan</span>}
                      {blob.corrupt ? <span className="rounded-full border border-rose-300/20 bg-rose-300/10 px-2 py-1 text-[10px] text-rose-200">corrupt</span> : null}
                      <span className="text-xs text-slate-500">{formatBytes(blob.size_bytes)} · {Number(blob.age_hours || 0).toFixed(1)}h</span>
                    </div>
                    <div className="mt-2 break-all font-mono text-[10px] text-slate-300">{text(blob.blob_ref)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center justify-between"><div className="text-sm font-semibold text-white">Upload sessions</div><div className="text-xs text-slate-500">{sessions.length} records</div></div>
              <div className="mt-4 space-y-3">
                {sessions.length === 0 ? <div className="text-sm text-slate-500">No upload sessions found.</div> : sessions.map((session) => (
                  <div key={text(session.session_id)} className="rounded-2xl border border-white/10 bg-[#040b14] p-4">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-semibold text-white">{text(session.status)}</span>{session.expired ? <span className="rounded-full border border-amber-300/20 px-2 py-1 text-[10px] text-amber-200">expired</span> : null}<span className="text-xs text-slate-500">{formatBytes(session.chunk_bytes)}</span></div>
                    <div className="mt-2 break-all font-mono text-[10px] text-slate-400">{text(session.session_id)}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <aside className="space-y-5">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white"><Trash2 className="h-4 w-4" />Cleanup controls</div>
              <label className="mt-4 block text-xs text-slate-400">Minimum candidate age in hours<input value={minimumAgeHours} onChange={(event) => setMinimumAgeHours(event.target.value)} type="number" min="1" className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white" /></label>
              <label className="mt-4 flex items-start gap-3 text-xs leading-5 text-slate-400"><input type="checkbox" checked={includeCorrupt} onChange={(event) => setIncludeCorrupt(event.target.checked)} className="mt-1" /><span>Include corrupt unreferenced files. Keep this off unless the audit has been reviewed.</span></label>
              <Button className="mt-5 w-full" variant="outline" onClick={() => runCleanup(true)} disabled={!audit || busy !== null}>{busy === 'dry-run' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FileWarning className="mr-2 h-4 w-4" />}Preview cleanup</Button>

              <div className="mt-6 border-t border-white/10 pt-5">
                <label className="text-xs text-slate-400">Type exact project ID<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={projectId || 'project-id'} className="mt-2 w-full rounded-xl border border-rose-300/20 bg-[#040b14] px-3 py-2.5 text-sm text-white" /></label>
                <Button className="mt-4 w-full" onClick={() => runCleanup(false)} disabled={!audit || confirmation !== projectId.trim() || busy !== null}>{busy === 'apply' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}Apply confirmed cleanup</Button>
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="text-sm font-semibold text-white">Latest cleanup result</div>
              {!cleanup ? <div className="mt-4 text-sm leading-6 text-slate-500">Run a dry-run preview before applying cleanup.</div> : <div className="mt-4 space-y-3 text-xs text-slate-400"><div>Mode: <span className="text-slate-200">{cleanup.dry_run ? 'dry run' : 'applied'}</span></div><div>Blob candidates: <span className="text-slate-200">{rows(cleanup.candidate_blob_refs).length || (Array.isArray(cleanup.candidate_blob_refs) ? cleanup.candidate_blob_refs.length : 0)}</span></div><div>Session candidates: <span className="text-slate-200">{Array.isArray(cleanup.candidate_session_ids) ? cleanup.candidate_session_ids.length : 0}</span></div><div>Reclaimable: <span className="text-slate-200">{formatBytes(cleanup.bytes_reclaimable)}</span></div><div>Reclaimed: <span className="text-slate-200">{formatBytes(cleanup.bytes_reclaimed)}</span></div></div>}
            </section>

            {(orphanBlobs.length > 0 || expiredSessions.length > 0) ? <div className="flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-xs leading-5 text-amber-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />Review {orphanBlobs.length} orphan blobs and {expiredSessions.length} expired sessions before applying cleanup.</div> : null}
          </aside>
        </div>
      </div>
    </main>
  );
}
