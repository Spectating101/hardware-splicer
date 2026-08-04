'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Braces,
  CheckCircle2,
  FileSearch,
  LoaderCircle,
  RefreshCw,
  Save,
  ShieldCheck,
  Wrench,
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
type MutationResponse = {
  ok?: boolean;
  revision?: number;
  parser_run?: JsonRecord;
  source?: JsonRecord;
};

type SourceDraft = {
  sourceType: string;
  authority: string;
  note: string;
};

const sourceTypes = [
  'repository',
  'release',
  'cad',
  'drawing',
  'schematic',
  'pcb',
  'bom',
  'datasheet',
  'manual',
  'paper',
  'service_note',
  'issue',
  'video',
  'photo',
  'measurement',
  'telemetry',
  'test_log',
  'project_snapshot',
  'operator_observation',
  'user_requirement',
  'donor_inventory',
  'other',
];

const authorityOrder = ['unknown', 'proposed', 'declared'];

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

function authorityOptions(current: string) {
  const index = authorityOrder.indexOf(current);
  return index < 0 ? ['unknown'] : authorityOrder.slice(0, index + 1);
}

export default function EngineeringSourceLabPage() {
  usePageTitle('Source Lab | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [drafts, setDrafts] = useState<Record<string, SourceDraft>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastParserRun, setLastParserRun] = useState<JsonRecord | null>(null);

  const sources = rows(snapshot?.engineeringSources);
  const parserRuns = rows(snapshot?.engineeringSourceParserRuns);
  const parsedSources = rows(snapshot?.engineeringParsedSources);
  const runsBySource = useMemo(() => {
    const result = new Map<string, JsonRecord>();
    parserRuns.forEach((run) => result.set(text(run.source_id, ''), run));
    return result;
  }, [parserRuns]);

  function hydrateDrafts(nextSources: JsonRecord[]) {
    const next: Record<string, SourceDraft> = {};
    nextSources.forEach((source) => {
      const sourceId = text(source.source_id, '');
      next[sourceId] = {
        sourceType: text(source.source_type, 'other'),
        authority: text(source.authority_ceiling, 'declared'),
        note: '',
      };
    });
    setDrafts(next);
  }

  async function loadProject() {
    const id = projectId.trim();
    if (!id) {
      setError('Enter a project ID.');
      return;
    }
    setBusyKey('load');
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
      const nextSnapshot = record(envelope.snapshot);
      const nextRevision = Number(envelope.revision);
      if (!Number.isInteger(nextRevision) || nextRevision < 1) {
        throw new Error('The project returned no valid revision.');
      }
      setRevision(nextRevision);
      setSnapshot(nextSnapshot);
      hydrateDrafts(rows(nextSnapshot.engineeringSources));
      setLastParserRun(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function runParser(sourceId: string) {
    if (!revision) return;
    setBusyKey(`parse:${sourceId}`);
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/sources/${encodeURIComponent(sourceId)}/parse`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: revision }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<MutationResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The bounded parser could not run.'));
      }
      const nextRevision = Number((payload as MutationResponse).revision || revision);
      setLastParserRun(record((payload as MutationResponse).parser_run));
      setRevision(nextRevision);
      await loadProjectAfterMutation(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Parser execution failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function applyRole(sourceId: string) {
    if (!revision) return;
    const draft = drafts[sourceId];
    if (!draft) return;
    setBusyKey(`role:${sourceId}`);
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/sources/${encodeURIComponent(sourceId)}/role`,
        {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: revision,
            source_type: draft.sourceType,
            authority_ceiling: draft.authority,
            note: draft.note,
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<MutationResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The source role could not be corrected.'));
      }
      const nextRevision = Number((payload as MutationResponse).revision);
      setRevision(nextRevision);
      await loadProjectAfterMutation(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Source role correction failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function loadProjectAfterMutation(expectedRevision: number) {
    const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}`, {
      cache: 'no-store',
    });
    const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
    if (!response.ok || isProxyFailure(payload)) {
      throw new Error(getProxyErrorMessage(payload, 'The updated project could not be reloaded.'));
    }
    const envelope = record((payload as ProjectResponse).project);
    const nextSnapshot = record(envelope.snapshot);
    const actualRevision = Number(envelope.revision);
    if (actualRevision < expectedRevision) {
      throw new Error('The project reload returned an older revision.');
    }
    setRevision(actualRevision);
    setSnapshot(nextSnapshot);
    hydrateDrafts(rows(nextSnapshot.engineeringSources));
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/sources" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering Sources
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-violet-300/20 bg-violet-300/10 p-3 text-violet-200">
                <FileSearch className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Source Lab</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
                  Re-verify stored bytes, run bounded parsers, inspect derived records, and correct source roles without increasing evidence authority.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/project-preflight"><Button variant="outline">Project plan</Button></Link>
            <Link href="/engineering"><Button variant="outline">Project inspector</Button></Link>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="project-id"
              className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-violet-300/40"
            />
            <Button onClick={loadProject} disabled={busyKey === 'load'}>
              {busyKey === 'load' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Load project
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{sources.length} registered sources</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{parserRuns.length} parser runs</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{parsedSources.length} derived sources</span>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            Parsing can establish bounded design structure only. It cannot authorize fabrication, flashing, power-on, motion, or release. STEP remains hash-verified inventory until a callable bounded parser exists.
          </div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="space-y-4">
            {!sources.length ? (
              <div className="rounded-3xl border border-dashed border-white/10 bg-[#07111f] p-10 text-center text-sm text-slate-500">
                Load a project with registered sources.
              </div>
            ) : sources.map((source) => {
              const sourceId = text(source.source_id, 'unknown-source');
              const metadata = record(source.metadata);
              const run = runsBySource.get(sourceId);
              const draft = drafts[sourceId] || {
                sourceType: text(source.source_type, 'other'),
                authority: text(source.authority_ceiling, 'declared'),
                note: '',
              };
              const parserRoute = text(metadata.parser_route, 'inventory-only');
              const parserStatus = text(run?.status, text(record(metadata.latest_parser_run).status, 'not run'));
              return (
                <article key={sourceId} className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-100">{parserRoute}</span>
                        <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-400">{parserStatus}</span>
                      </div>
                      <h2 className="mt-3 break-all text-base font-semibold text-white">{sourceId}</h2>
                      <div className="mt-2 break-all font-mono text-[11px] text-slate-500">{text(source.content_hash)}</div>
                      <div className="mt-3 text-xs text-slate-400">{text(metadata.original_filename)} · {text(metadata.media_type)}</div>
                    </div>
                    <Button
                      onClick={() => runParser(sourceId)}
                      disabled={!revision || busyKey === `parse:${sourceId}`}
                    >
                      {busyKey === `parse:${sourceId}` ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Braces className="mr-2 h-4 w-4" />}
                      Run bounded parser
                    </Button>
                  </div>

                  <div className="mt-5 grid gap-3 border-t border-white/10 pt-5 md:grid-cols-2">
                    <label className="text-xs text-slate-400">
                      Source role
                      <select
                        value={draft.sourceType}
                        onChange={(event) => setDrafts((current) => ({
                          ...current,
                          [sourceId]: { ...draft, sourceType: event.target.value },
                        }))}
                        className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white"
                      >
                        {sourceTypes.map((value) => <option key={value} value={value}>{value}</option>)}
                      </select>
                    </label>
                    <label className="text-xs text-slate-400">
                      Authority ceiling
                      <select
                        value={draft.authority}
                        onChange={(event) => setDrafts((current) => ({
                          ...current,
                          [sourceId]: { ...draft, authority: event.target.value },
                        }))}
                        className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white"
                      >
                        {authorityOptions(text(source.authority_ceiling, 'declared')).map((value) => (
                          <option key={value} value={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
                    <input
                      value={draft.note}
                      onChange={(event) => setDrafts((current) => ({
                        ...current,
                        [sourceId]: { ...draft, note: event.target.value },
                      }))}
                      placeholder="Reason for role correction"
                      className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white"
                    />
                    <Button
                      variant="outline"
                      onClick={() => applyRole(sourceId)}
                      disabled={!revision || busyKey === `role:${sourceId}`}
                    >
                      {busyKey === `role:${sourceId}` ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Apply role
                    </Button>
                  </div>
                </article>
              );
            })}
          </section>

          <aside className="space-y-5">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white"><Wrench className="h-4 w-4" /> Latest parser result</div>
              {!lastParserRun ? (
                <div className="mt-4 text-sm leading-6 text-slate-500">Run a parser to inspect its bounded output.</div>
              ) : (
                <div className="mt-4 space-y-3">
                  <div className={`flex items-center gap-2 text-sm ${lastParserRun.status === 'parsed' ? 'text-emerald-200' : 'text-amber-200'}`}>
                    {lastParserRun.status === 'parsed' ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                    {text(lastParserRun.status)} · {text(lastParserRun.parser_route)}
                  </div>
                  <pre className="max-h-[520px] overflow-auto rounded-2xl border border-white/10 bg-[#040b14] p-4 text-[11px] leading-5 text-slate-300">
                    {JSON.stringify(lastParserRun, null, 2)}
                  </pre>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5 text-xs leading-6 text-slate-400">
              <div className="font-semibold text-white">Fail-closed rules</div>
              <div className="mt-3">Role correction may preserve or lower authority, never raise it.</div>
              <div>Source ID, hash, revision, URI, and blob identity remain immutable.</div>
              <div>Parser output stays candidate design evidence until separate verification exists.</div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
