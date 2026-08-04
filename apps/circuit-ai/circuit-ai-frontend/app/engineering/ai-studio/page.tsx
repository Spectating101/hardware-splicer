'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  BrainCircuit,
  Check,
  CirclePlay,
  FileCheck2,
  FileSearch,
  GitBranch,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
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
type SessionResponse = { ok?: boolean; revision?: number; session?: JsonRecord };
type ActionResponse = { ok?: boolean; revision?: number; action?: JsonRecord };
type PreviewResponse = ActionResponse & { tool_result?: JsonRecord; idempotent?: boolean };
type Decision = 'accepted' | 'rejected';
type ModelProfile = 'fast_draft' | 'deep_synthesis' | 'design_repair';

const previewActions = new Set(['run_guided_plan', 'run_compose']);

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

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((row) => String(row || '')).filter(Boolean) : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function closedGate(value: unknown) {
  return value === false ? 'closed' : 'not proven closed';
}

function compactJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return '{}';
  }
}

export default function AIStudioPage() {
  usePageTitle('AI Studio | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [mission, setMission] = useState('');
  const [constraintsText, setConstraintsText] = useState('{}');
  const [modelProfile, setModelProfile] = useState<ModelProfile>('deep_synthesis');
  const [sessionId, setSessionId] = useState('');
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sources = rows(snapshot?.engineeringSources);
  const parserRuns = rows(snapshot?.engineeringSourceParserRuns);
  const requirements = rows(session?.requirements);
  const candidates = rows(session?.architecture_candidates);
  const actions = rows(session?.actions);
  const openQuestions = strings(session?.open_questions);
  const proposedCount = useMemo(
    () => actions.filter((action) => text(action.status, '') === 'proposed').length,
    [actions],
  );

  function replaceAction(actionId: string, updatedAction: JsonRecord) {
    setSession((current) => current ? {
      ...current,
      actions: rows(current.actions).map((action) => (
        text(action.action_id, '') === actionId ? updatedAction : action
      )),
    } : current);
  }

  async function loadProject() {
    const id = projectId.trim();
    if (!id) return setError('Enter a project ID.');
    setBusyKey('project');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load the project.'));
      }
      const envelope = record((payload as ProjectResponse).project);
      const nextRevision = Number(envelope.revision);
      if (!Number.isInteger(nextRevision) || nextRevision < 1) throw new Error('The project returned no valid revision.');
      const nextSnapshot = record(envelope.snapshot);
      setRevision(nextRevision);
      setSnapshot(nextSnapshot);
      setSession(null);
      setSessionId('');
      if (!mission.trim()) setMission(text(nextSnapshot.mission, text(nextSnapshot.name, '')));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusyKey(null);
    }
  }

  function parsedConstraints(): JsonRecord {
    let parsed: unknown;
    try {
      parsed = JSON.parse(constraintsText || '{}');
    } catch {
      throw new Error('Constraints must be a valid JSON object.');
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Constraints must be one JSON object.');
    }
    return parsed as JsonRecord;
  }

  async function createSession() {
    const id = projectId.trim();
    if (!id || !revision) return setError('Load a revisioned project first.');
    if (!mission.trim()) return setError('Describe the engineering mission.');
    setBusyKey('create');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id)}/ai-sessions`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          mission: mission.trim(),
          expected_revision: revision,
          constraints: parsedConstraints(),
          model_profile: modelProfile,
          max_actions: 8,
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The AI project session could not be created.'));
      }
      const body = payload as SessionResponse;
      const nextSession = record(body.session);
      const nextRevision = Number(body.revision);
      if (!nextSession.session_id || !Number.isInteger(nextRevision)) {
        throw new Error('The orchestrator returned no valid session or revision.');
      }
      setSession(nextSession);
      setSessionId(text(nextSession.session_id, ''));
      setRevision(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'AI session creation failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function loadSession() {
    const id = projectId.trim();
    const selectedSession = sessionId.trim();
    if (!id || !selectedSession) return setError('Enter both a project ID and session ID.');
    setBusyKey('session');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(id)}/ai-sessions/${encodeURIComponent(selectedSession)}`,
        { cache: 'no-store' },
      );
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The AI project session could not be loaded.'));
      }
      const body = payload as SessionResponse;
      setSession(record(body.session));
      const nextRevision = Number(body.revision);
      if (Number.isInteger(nextRevision)) setRevision(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'AI session load failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function decideAction(actionId: string, decision: Decision) {
    if (!revision || !sessionId.trim()) return;
    setBusyKey(`${decision}:${actionId}`);
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/ai-sessions/${encodeURIComponent(sessionId.trim())}/actions/${encodeURIComponent(actionId)}/decision`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: revision,
            decision,
            reviewer: 'human',
            note: decision === 'accepted'
              ? 'Accepted as a proposal only. Software preview requires a separate action.'
              : 'Rejected by the project reviewer.',
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<ActionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The proposal decision could not be recorded.'));
      }
      const body = payload as ActionResponse;
      replaceAction(actionId, record(body.action));
      const nextRevision = Number(body.revision);
      if (Number.isInteger(nextRevision)) setRevision(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Proposal decision failed.');
    } finally {
      setBusyKey(null);
    }
  }

  async function executePreview(actionId: string) {
    if (!revision || !sessionId.trim()) return;
    setBusyKey(`preview:${actionId}`);
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/ai-sessions/${encodeURIComponent(sessionId.trim())}/actions/${encodeURIComponent(actionId)}/execute-preview`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: revision }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<PreviewResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The accepted software preview could not run.'));
      }
      const body = payload as PreviewResponse;
      replaceAction(actionId, record(body.action));
      const nextRevision = Number(body.revision);
      if (Number.isInteger(nextRevision)) setRevision(nextRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Software preview failed.');
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1600px]">
        <header className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/project-preflight" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Project plan
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
                <BrainCircuit className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-white">AI Project Studio</h1>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">
                  Build revision-pinned engineering proposals, review them, and run only explicitly accepted software previews. Physical authority remains separate and closed.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/source-lab"><Button variant="outline"><FileSearch className="mr-2 h-4 w-4" />Source Lab</Button></Link>
            <Link href="/engineering"><Button variant="outline"><GitBranch className="mr-2 h-4 w-4" />Inspector</Button></Link>
          </div>
        </header>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <input value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="project-id" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-fuchsia-300/40" />
            <Button onClick={loadProject} disabled={busyKey === 'project'}>
              {busyKey === 'project' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Load project
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{sources.length} sources</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{parserRuns.length} parser runs</span>
          </div>
        </section>

        <section className="mt-5 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Engineering mission</label>
              <textarea value={mission} onChange={(event) => setMission(event.target.value)} rows={4} placeholder="Describe what the project must build, modify, repair, or verify." className="mt-2 w-full rounded-2xl border border-white/10 bg-[#040b14] px-4 py-3 text-sm leading-6 text-white outline-none focus:border-fuchsia-300/40" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Model profile</label>
              <select value={modelProfile} onChange={(event) => setModelProfile(event.target.value as ModelProfile)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none">
                <option value="fast_draft">Fast draft</option>
                <option value="deep_synthesis">Deep synthesis</option>
                <option value="design_repair">Design repair</option>
              </select>
              <Button className="mt-4 w-full" onClick={createSession} disabled={busyKey === 'create' || !revision}>
                {busyKey === 'create' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}Generate proposals
              </Button>
            </div>
          </div>
          <details className="mt-4 rounded-2xl border border-white/10 bg-[#040b14] p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-300">Structured constraints</summary>
            <textarea value={constraintsText} onChange={(event) => setConstraintsText(event.target.value)} rows={6} spellCheck={false} className="mt-3 w-full rounded-xl border border-white/10 bg-[#02070d] px-3 py-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-fuchsia-300/40" />
          </details>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
            <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="ai-session-id" className="rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-fuchsia-300/40" />
            <Button variant="outline" onClick={loadSession} disabled={busyKey === 'session'}>
              {busyKey === 'session' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Load session
            </Button>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>Proposal acceptance and preview execution are separate revisions. Previews are software evidence only; fabrication, flashing, power-on, motion, operation, and release remain unauthorized.</div>
        </div>

        {error ? <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_440px]">
          <aside className="space-y-4">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <h2 className="text-sm font-semibold text-white">Project truth</h2>
              <div className="mt-4 space-y-3 text-xs text-slate-400">
                <div className="flex justify-between gap-4"><span>Project</span><span className="text-slate-200">{projectId || '—'}</span></div>
                <div className="flex justify-between gap-4"><span>Revision</span><span className="text-slate-200">{revision ?? '—'}</span></div>
                <div className="flex justify-between gap-4"><span>Sources</span><span className="text-slate-200">{sources.length}</span></div>
                <div className="flex justify-between gap-4"><span>Parser runs</span><span className="text-slate-200">{parserRuns.length}</span></div>
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
                ].map(([label, value]) => <div key={String(label)} className="flex justify-between rounded-xl border border-white/8 bg-[#040b14] px-3 py-2"><span className="text-slate-400">{String(label)}</span><span className="text-emerald-200">{closedGate(value)}</span></div>)}
              </div>
            </section>
          </aside>

          <section className="space-y-5">
            {!session ? <div className="rounded-3xl border border-dashed border-white/10 bg-[#07111f] p-12 text-center"><BrainCircuit className="mx-auto h-10 w-10 text-slate-600" /><p className="mt-4 text-sm text-slate-500">Load a project and generate one revision-pinned AI session.</p></div> : <>
              <article className="rounded-3xl border border-fuchsia-300/20 bg-fuchsia-300/5 p-5">
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-fuchsia-200">{text(session.model_profile, 'profile')} · {text(session.provider, 'provider')} · {text(session.model, 'model')}</div>
                <h2 className="mt-3 text-lg font-semibold text-white">Session summary</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{text(session.summary)}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400"><span className="rounded-full border border-white/10 px-3 py-1">{requirements.length} requirements</span><span className="rounded-full border border-white/10 px-3 py-1">{candidates.length} candidates</span><span className="rounded-full border border-white/10 px-3 py-1">{proposedCount} proposed actions</span></div>
              </article>

              <article className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
                <h2 className="text-sm font-semibold text-white">Proposed requirements</h2>
                <div className="mt-4 space-y-3">{requirements.length ? requirements.map((requirement) => <div key={text(requirement.id)} className="rounded-2xl border border-white/8 bg-[#040b14] p-4"><div className="text-xs font-semibold text-cyan-200">{text(requirement.id)}</div><p className="mt-2 text-sm leading-6 text-slate-300">{text(requirement.statement)}</p><div className="mt-2 text-xs text-slate-500">Sources: {strings(requirement.source_ids).join(', ') || 'none declared'}</div></div>) : <p className="text-sm text-slate-500">No requirements returned.</p>}</div>
              </article>

              <article className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
                <h2 className="text-sm font-semibold text-white">Architecture candidates</h2>
                <div className="mt-4 space-y-4">{candidates.length ? candidates.map((candidate) => <div key={text(candidate.id)} className="rounded-2xl border border-cyan-300/15 bg-cyan-300/5 p-4"><div className="flex items-start justify-between gap-4"><div><div className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">{text(candidate.id)}</div><h3 className="mt-1 font-semibold text-white">{text(candidate.title)}</h3></div><span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2.5 py-1 text-[10px] text-amber-100">proposed</span></div><p className="mt-3 text-sm leading-6 text-slate-300">{text(candidate.summary)}</p><div className="mt-3 space-y-1 text-xs text-slate-400">{strings(candidate.tradeoffs).map((tradeoff) => <div key={tradeoff}>• {tradeoff}</div>)}</div></div>) : <p className="text-sm text-slate-500">No architecture candidates returned.</p>}</div>
              </article>

              {openQuestions.length ? <article className="rounded-3xl border border-amber-300/20 bg-amber-300/5 p-5"><h2 className="flex items-center gap-2 text-sm font-semibold text-amber-100"><AlertTriangle className="h-4 w-4" />Open questions</h2><div className="mt-3 space-y-2 text-sm text-amber-50/80">{openQuestions.map((question) => <div key={question}>• {question}</div>)}</div></article> : null}
            </>}
          </section>

          <aside>
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center justify-between gap-4"><h2 className="text-sm font-semibold text-white">Actions and previews</h2><span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-400">Explicit only</span></div>
              <div className="mt-4 space-y-4">{actions.length ? actions.map((action) => {
                const actionId = text(action.action_id, '');
                const actionType = text(action.action_type, '');
                const actionStatus = text(action.status, 'proposed');
                const toolResult = record(action.tool_result);
                const resultSummary = record(toolResult.summary);
                const artifact = record(toolResult.artifact);
                const decisionBusy = busyKey?.endsWith(`:${actionId}`) ?? false;
                const previewBusy = busyKey === `preview:${actionId}`;
                const canPreview = actionStatus === 'accepted' && previewActions.has(actionType) && !action.tool_result;
                return <article key={actionId} className="rounded-2xl border border-white/8 bg-[#040b14] p-4">
                  <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-fuchsia-200">{actionType}</div><h3 className="mt-1 text-sm font-semibold text-white">{text(action.title)}</h3></div><span className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-slate-300">{actionStatus}</span></div>
                  <p className="mt-3 text-xs leading-5 text-slate-400">{text(action.rationale)}</p>
                  <div className="mt-3 rounded-xl border border-white/8 bg-[#02070d] p-3 text-[11px] text-slate-500">Authority effect: {text(action.authority_effect, 'none')} · Automatic execution: false</div>

                  {actionStatus === 'proposed' ? <div className="mt-4 grid grid-cols-2 gap-2"><Button size="sm" onClick={() => decideAction(actionId, 'accepted')} disabled={decisionBusy}>{decisionBusy ? <LoaderCircle className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Check className="mr-2 h-3.5 w-3.5" />}Accept</Button><Button size="sm" variant="outline" onClick={() => decideAction(actionId, 'rejected')} disabled={decisionBusy}><X className="mr-2 h-3.5 w-3.5" />Reject</Button></div> : null}

                  {canPreview ? <Button className="mt-4 w-full" size="sm" onClick={() => executePreview(actionId)} disabled={previewBusy}>{previewBusy ? <LoaderCircle className="mr-2 h-3.5 w-3.5 animate-spin" /> : <CirclePlay className="mr-2 h-3.5 w-3.5" />}Run software preview</Button> : null}

                  {actionStatus === 'accepted' && !previewActions.has(actionType) ? <div className="mt-4 text-xs text-amber-200">Accepted proposal; this action type is not executable in the current preview boundary.</div> : null}

                  {actionStatus === 'rejected' ? <div className="mt-4 flex items-center gap-2 text-xs text-rose-200"><X className="h-3.5 w-3.5" />Rejected without execution.</div> : null}

                  {action.tool_result ? <div className={`mt-4 rounded-2xl border p-4 ${text(toolResult.status, '') === 'succeeded' ? 'border-emerald-300/20 bg-emerald-300/5' : 'border-rose-300/20 bg-rose-300/5'}`}>
                    <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2 text-xs font-semibold text-white"><FileCheck2 className="h-4 w-4" />Software preview</div><span className="text-[10px] uppercase tracking-[0.14em] text-slate-300">{text(toolResult.status)}</span></div>
                    <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-white/8 bg-[#02070d] p-3 text-[10px] leading-5 text-slate-300">{compactJson(resultSummary)}</pre>
                    <div className="mt-3 space-y-1 break-all text-[10px] text-slate-500"><div>Artifact: {text(artifact.project_relative_path)}</div><div>SHA-256: {text(artifact.sha256)}</div><div>Bytes: {text(artifact.size_bytes)}</div></div>
                    <div className="mt-3 text-[10px] text-emerald-200">Software evidence only · physical authority unchanged</div>
                  </div> : null}
                </article>;
              }) : <p className="text-sm text-slate-500">No actions available.</p>}</div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
