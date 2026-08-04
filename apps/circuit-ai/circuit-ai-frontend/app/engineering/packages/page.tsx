'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Archive,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Download,
  FileArchive,
  FileCheck2,
  Fingerprint,
  GitBranch,
  LoaderCircle,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
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
type PackageListResponse = {
  ok?: boolean;
  revision?: number;
  packages?: JsonRecord[];
  package_count?: number;
};
type PackageCreateResponse = {
  ok?: boolean;
  revision?: number;
  package?: JsonRecord;
  idempotent?: boolean;
};

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

function closedGate(value: unknown) {
  return value === false ? 'closed' : 'not proven closed';
}

function formatBytes(value: unknown) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

export default function EngineeringPackageWorkspacePage() {
  usePageTitle('Engineering Packages | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [packages, setPackages] = useState<JsonRecord[]>([]);
  const [busy, setBusy] = useState<'load' | 'create' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const orderedPackages = useMemo(
    () => [...packages].sort((left, right) => Number(right.source_revision || 0) - Number(left.source_revision || 0)),
    [packages],
  );

  async function loadWorkspace() {
    const id = projectId.trim();
    if (!id) {
      setError('Enter a project ID.');
      return;
    }
    setBusy('load');
    setError(null);
    setNotice(null);
    try {
      const projectResponse = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}`,
        { cache: 'no-store' },
      );
      const projectPayload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(projectResponse);
      if (!projectResponse.ok || isProxyFailure(projectPayload)) {
        throw new Error(getProxyErrorMessage(projectPayload, 'Hardware Splicer could not load the project.'));
      }
      const envelope = record((projectPayload as ProjectResponse).project);
      const projectRevision = Number(envelope.revision);
      if (!Number.isInteger(projectRevision) || projectRevision < 1) {
        throw new Error('The project returned no valid revision.');
      }

      const packageResponse = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}/engineering-packages`,
        { cache: 'no-store' },
      );
      const packagePayload = await readJsonPayload<PackageListResponse | ProxyErrorPayload>(packageResponse);
      if (!packageResponse.ok || isProxyFailure(packagePayload)) {
        throw new Error(getProxyErrorMessage(packagePayload, 'Hardware Splicer could not list Engineering Packages.'));
      }
      const listed = packagePayload as PackageListResponse;
      const packageRevision = Number(listed.revision);
      setSnapshot(record(envelope.snapshot));
      setPackages(rows(listed.packages));
      setRevision(Number.isInteger(packageRevision) ? packageRevision : projectRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Package workspace load failed.');
    } finally {
      setBusy(null);
    }
  }

  async function createPackage() {
    const id = projectId.trim();
    if (!id || !revision) {
      setError('Load a revisioned project first.');
      return;
    }
    setBusy('create');
    setError(null);
    setNotice(null);
    try {
      const sourceRevision = revision;
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}/engineering-packages`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: sourceRevision }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<PackageCreateResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not create the Engineering Package.'));
      }
      const body = payload as PackageCreateResponse;
      const packageRecord = record(body.package);
      const nextRevision = Number(body.revision);
      if (!packageRecord.package_id || !Number.isInteger(nextRevision)) {
        throw new Error('The export route returned no valid package or project revision.');
      }
      setRevision(nextRevision);
      setPackages((current) => {
        const packageId = text(packageRecord.package_id, '');
        const withoutDuplicate = current.filter((row) => text(row.package_id, '') !== packageId);
        return [...withoutDuplicate, packageRecord];
      });
      setNotice(body.idempotent
        ? `Verified existing package for source revision ${sourceRevision}.`
        : `Created deterministic package from source revision ${sourceRevision}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Engineering Package export failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <header className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/jarvis" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> JARVIS Console
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-3 text-emerald-100">
                <FileArchive className="h-7 w-7" />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">Revisioned engineering handoff</div>
                <h1 className="mt-1 text-3xl font-semibold text-white">Engineering Packages</h1>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">
                  Export one exact project revision as a deterministic, content-addressed ZIP with source hashes, decisions, previews, repairs, JARVIS briefings, blockers, and authority state.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/jarvis"><Button variant="outline"><Bot className="mr-2 h-4 w-4" />JARVIS</Button></Link>
            <Link href="/engineering/ai-studio"><Button variant="outline"><PackageCheck className="mr-2 h-4 w-4" />AI Studio</Button></Link>
            <Link href="/engineering"><Button variant="outline"><GitBranch className="mr-2 h-4 w-4" />Inspector</Button></Link>
          </div>
        </header>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
            <input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="project-id"
              className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
            />
            <Button onClick={loadWorkspace} disabled={busy === 'load'} variant="outline">
              {busy === 'load' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Load project
            </Button>
            <Button onClick={createPackage} disabled={busy === 'create' || !revision}>
              {busy === 'create' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
              Export revision {revision ?? '—'}
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Current revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{packages.length} package records</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Raw source bytes excluded</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Authority effect none</span>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            A package records project state; it does not authorize fabrication, flashing, power-on, motion, operation, or release. Downloads are served only after backend size and SHA-256 verification.
          </div>
        </div>

        {notice ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {notice}
          </div>
        ) : null}
        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <h2 className="text-sm font-semibold text-white">Project boundary</h2>
              <div className="mt-4 space-y-3 text-xs text-slate-400">
                <div className="flex justify-between gap-3"><span>Project</span><span className="text-right text-slate-200">{projectId || '—'}</span></div>
                <div className="flex justify-between gap-3"><span>Revision</span><span className="text-right text-slate-200">{revision ?? '—'}</span></div>
                <div className="flex justify-between gap-3"><span>Sources</span><span className="text-right text-slate-200">{rows(snapshot?.engineeringSources).length}</span></div>
                <div className="flex justify-between gap-3"><span>AI sessions</span><span className="text-right text-slate-200">{rows(snapshot?.engineeringAiSessions).length}</span></div>
              </div>
            </section>
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <h2 className="text-sm font-semibold text-white">Physical gates</h2>
              <div className="mt-4 space-y-2 text-xs">
                {[
                  ['Fabrication', snapshot?.fabrication_authorized],
                  ['Flashing', snapshot?.firmware_flash_authorized],
                  ['Power-on', snapshot?.power_on_authorized],
                  ['Motion', snapshot?.motion_authorized],
                  ['Release', snapshot?.release_authorized],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex justify-between rounded-xl border border-white/8 bg-[#040b14] px-3 py-2">
                    <span className="text-slate-400">{String(label)}</span>
                    <span className="text-emerald-200">{closedGate(value)}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>

          <section>
            {!orderedPackages.length ? (
              <div className="rounded-3xl border border-dashed border-white/10 bg-[#07111f] p-12 text-center">
                <FileArchive className="mx-auto h-10 w-10 text-slate-600" />
                <p className="mt-4 text-sm text-slate-500">Load a project, then export its current revision or inspect prior package records.</p>
              </div>
            ) : (
              <div className="space-y-5">
                {orderedPackages.map((packageRecord) => {
                  const packageId = text(packageRecord.package_id, '');
                  const downloadHref = `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/engineering-packages/${encodeURIComponent(packageId)}/download`;
                  return (
                    <article key={packageId} className="rounded-3xl border border-emerald-300/15 bg-[#07111f] p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-100">Source revision {text(packageRecord.source_revision)}</span>
                            <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-400">{text(packageRecord.file_count)} files</span>
                            <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-400">{formatBytes(packageRecord.zip_size_bytes)}</span>
                          </div>
                          <h2 className="mt-3 break-all font-mono text-sm font-semibold text-white">{packageId}</h2>
                          <div className="mt-3 grid gap-3 text-[11px] text-slate-400 md:grid-cols-2">
                            <div className="rounded-xl border border-white/8 bg-[#040b14] p-3">
                              <div className="flex items-center gap-2 text-slate-300"><Fingerprint className="h-3.5 w-3.5" />Snapshot SHA-256</div>
                              <div className="mt-2 break-all font-mono">{text(packageRecord.snapshot_sha256)}</div>
                            </div>
                            <div className="rounded-xl border border-white/8 bg-[#040b14] p-3">
                              <div className="flex items-center gap-2 text-slate-300"><FileCheck2 className="h-3.5 w-3.5" />Manifest SHA-256</div>
                              <div className="mt-2 break-all font-mono">{text(packageRecord.manifest_sha256)}</div>
                            </div>
                            <div className="rounded-xl border border-white/8 bg-[#040b14] p-3 md:col-span-2">
                              <div className="flex items-center gap-2 text-slate-300"><PackageCheck className="h-3.5 w-3.5" />ZIP SHA-256</div>
                              <div className="mt-2 break-all font-mono">{text(packageRecord.zip_sha256)}</div>
                            </div>
                          </div>
                        </div>
                        <a href={downloadHref} className="shrink-0" download>
                          <Button><Download className="mr-2 h-4 w-4" />Verified ZIP</Button>
                        </a>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2 text-[10px] text-slate-400">
                        <span className="rounded-full border border-white/10 px-2.5 py-1">Raw source bytes: excluded</span>
                        <span className="rounded-full border border-white/10 px-2.5 py-1">Authority effect: {text(packageRecord.package_authority_effect, 'none')}</span>
                        <span className="rounded-full border border-white/10 px-2.5 py-1">Physical authority unchanged</span>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
