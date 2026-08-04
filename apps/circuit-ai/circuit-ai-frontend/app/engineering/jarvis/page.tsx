'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  BrainCircuit,
  CheckCircle2,
  FileSearch,
  GitBranch,
  Link2,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
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
type TurnResponse = SessionResponse & {
  turn?: JsonRecord;
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

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((row) => String(row || '')).filter(Boolean)
    : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function closedGate(value: unknown) {
  return value === false ? 'closed' : 'not proven closed';
}

function requestIdentity() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `jarvis-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function JarvisEngineeringConsolePage() {
  usePageTitle('JARVIS | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<'load' | 'turn' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const turns = rows(session?.conversationTurns);
  const actions = rows(session?.actions);
  const requirements = rows(session?.requirements);
  const candidates = rows(session?.architecture_candidates);
  const sources = rows(snapshot?.engineeringSources);
  const parserRuns = rows(snapshot?.engineeringSourceParserRuns);
  const pendingActions = useMemo(
    () => actions.filter((action) => text(action.status, '') === 'proposed'),
    [actions],
  );

  async function loadWorkspace() {
    const project = projectId.trim();
    const selectedSession = sessionId.trim();
    if (!project || !selectedSession) {
      setError('Enter both a project ID and AI session ID.');
      return;
    }
    setBusy('load');
    setError(null);
    try {
      const projectResponse = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(project)}`,
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

      const sessionResponse = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(project)}/ai-sessions/${encodeURIComponent(selectedSession)}`,
        { cache: 'no-store' },
      );
      const sessionPayload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(sessionResponse);
      if (!sessionResponse.ok || isProxyFailure(sessionPayload)) {
        throw new Error(getProxyErrorMessage(sessionPayload, 'Hardware Splicer could not load the AI session.'));
      }
      const loadedSession = record((sessionPayload as SessionResponse).session);
      const sessionRevision = Number((sessionPayload as SessionResponse).revision);
      setSnapshot(record(envelope.snapshot));
      setSession(loadedSession);
      setSessionId(text(loadedSession.session_id, selectedSession));
      setRevision(Number.isInteger(sessionRevision) ? sessionRevision : projectRevision);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'JARVIS workspace load failed.');
    } finally {
      setBusy(null);
    }
  }

  async function askJarvis() {
    const question = message.trim();
    if (!question) {
      setError('Ask one concrete project question.');
      return;
    }
    if (!revision || !projectId.trim() || !sessionId.trim()) {
      setError('Load a revisioned project session first.');
      return;
    }
    setBusy('turn');
    setError(null);
    const clientRequestId = requestIdentity();
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/ai-sessions/${encodeURIComponent(sessionId.trim())}/turns`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: revision,
            message: question,
            client_request_id: clientRequestId,
            max_proposals: 2,
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<TurnResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'JARVIS could not answer from the current project revision.'));
      }
      const body = payload as TurnResponse;
      const updatedSession = record(body.session);
      const nextRevision = Number(body.revision);
      if (!updatedSession.session_id || !Number.isInteger(nextRevision)) {
        throw new Error('The conversation route returned no valid session or revision.');
      }
      setSession(updatedSession);
      setSessionId(text(updatedSession.session_id, sessionId));
      setRevision(nextRevision);
      setMessage('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'JARVIS turn failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#030812] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1700px]">
        <header className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/ai-studio" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> AI Project Studio
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-300/25 bg-cyan-300/10 p-3 text-cyan-100">
                <Bot className="h-7 w-7" />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-300">Revision-aware engineering interface</div>
                <h1 className="mt-1 text-3xl font-semibold text-white">JARVIS Console</h1>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">
                  Ask questions against one exact project revision. Answers cite persisted evidence, expose blockers, and turn any suggested change into a reviewable proposal.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/engineering/ai-studio"><Button variant="outline"><BrainCircuit className="mr-2 h-4 w-4" />Review actions</Button></Link>
            <Link href="/engineering/source-lab"><Button variant="outline"><FileSearch className="mr-2 h-4 w-4" />Sources</Button></Link>
            <Link href="/engineering"><Button variant="outline"><GitBranch className="mr-2 h-4 w-4" />Inspector</Button></Link>
          </div>
        </header>

        <section className="mt-6 rounded-3xl border border-white/10 bg-[#07111f] p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
            <input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="project-id"
              className="rounded-xl border border-white/10 bg-[#030812] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40"
            />
            <input
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              placeholder="ai-session-id"
              className="rounded-xl border border-white/10 bg-[#030812] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40"
            />
            <Button onClick={loadWorkspace} disabled={busy === 'load'}>
              {busy === 'load' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Load project session
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Revision {revision ?? '—'}</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{sources.length} sources</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{parserRuns.length} parser runs</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{turns.length} persisted turns</span>
            <span className="rounded-full border border-white/10 px-3 py-1">{pendingActions.length} proposals awaiting review</span>
          </div>
        </section>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            JARVIS is guidance, not project truth. A recommendation becomes a proposed action only; human review, deterministic preview, physical evidence, and authority remain separate.
          </div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_400px]">
          <aside className="space-y-4">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <h2 className="text-sm font-semibold text-white">Project boundary</h2>
              <div className="mt-4 space-y-3 text-xs text-slate-400">
                <div className="flex justify-between gap-3"><span>Project</span><span className="text-right text-slate-200">{projectId || '—'}</span></div>
                <div className="flex justify-between gap-3"><span>Session</span><span className="break-all text-right text-slate-200">{sessionId || '—'}</span></div>
                <div className="flex justify-between gap-3"><span>Kind</span><span className="text-right text-slate-200">{text(session?.session_kind, 'project proposal')}</span></div>
                <div className="flex justify-between gap-3"><span>Model</span><span className="text-right text-slate-200">{text(session?.model, '—')}</span></div>
                <div className="flex justify-between gap-3"><span>Requirements</span><span className="text-right text-slate-200">{requirements.length}</span></div>
                <div className="flex justify-between gap-3"><span>Candidates</span><span className="text-right text-slate-200">{candidates.length}</span></div>
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
                  <div key={String(label)} className="flex justify-between rounded-xl border border-white/8 bg-[#030812] px-3 py-2">
                    <span className="text-slate-400">{String(label)}</span>
                    <span className="text-emerald-200">{closedGate(value)}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>

          <section className="space-y-5">
            <section className="rounded-3xl border border-cyan-300/20 bg-cyan-300/5 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-cyan-100">
                <MessageSquareText className="h-4 w-4" /> Ask JARVIS
              </div>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={4}
                placeholder="What failed, what is still unknown, and what should we do next?"
                className="mt-4 w-full rounded-2xl border border-white/10 bg-[#030812] px-4 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/40"
              />
              <div className="mt-3 flex items-center justify-between gap-4">
                <div className="text-xs text-slate-500">One question creates one revisioned answer and zero or more proposed actions.</div>
                <Button onClick={askJarvis} disabled={busy === 'turn' || !session || !revision}>
                  {busy === 'turn' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Ask from revision {revision ?? '—'}
                </Button>
              </div>
            </section>

            {!session ? (
              <div className="rounded-3xl border border-dashed border-white/10 bg-[#07111f] p-12 text-center">
                <Bot className="mx-auto h-10 w-10 text-slate-600" />
                <p className="mt-4 text-sm text-slate-500">Load a revisioned AI session to begin the grounded conversation.</p>
              </div>
            ) : turns.length ? (
              <div className="space-y-5">
                {turns.map((turn) => {
                  const evidence = rows(turn.evidence_refs);
                  const blockers = strings(turn.blockers);
                  const recommendedActionId = text(turn.recommended_action_id, '');
                  return (
                    <article key={text(turn.turn_id)} className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
                      <div className="rounded-2xl border border-white/8 bg-[#030812] p-4">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">You · revision {text(turn.project_revision)}</div>
                        <p className="mt-2 text-sm leading-6 text-slate-200">{text(turn.user_message)}</p>
                      </div>
                      <div className="mt-4 rounded-2xl border border-cyan-300/15 bg-cyan-300/5 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-100"><Bot className="h-4 w-4" />JARVIS</div>
                          <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-slate-300">{text(turn.answer_kind)}</span>
                        </div>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200">{text(turn.assistant_answer)}</p>
                      </div>

                      <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        <div className="rounded-2xl border border-white/8 bg-[#030812] p-4">
                          <h3 className="flex items-center gap-2 text-xs font-semibold text-white"><Link2 className="h-3.5 w-3.5" />Evidence references</h3>
                          <div className="mt-3 space-y-3">
                            {evidence.map((item, index) => (
                              <div key={`${text(item.kind)}-${text(item.id)}-${index}`} className="rounded-xl border border-white/8 p-3">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200">{text(item.kind)} · {text(item.id)}</div>
                                <div className="mt-1 text-xs leading-5 text-slate-400">{text(item.reason)}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-white/8 bg-[#030812] p-4">
                          <h3 className="flex items-center gap-2 text-xs font-semibold text-white"><AlertTriangle className="h-3.5 w-3.5" />Blockers and next action</h3>
                          <div className="mt-3 space-y-2 text-xs leading-5 text-amber-100/80">
                            {blockers.length ? blockers.map((blocker) => <div key={blocker}>• {blocker}</div>) : <div className="text-slate-500">No blocker declared in this answer.</div>}
                          </div>
                          {recommendedActionId ? (
                            <div className="mt-4 rounded-xl border border-fuchsia-300/20 bg-fuchsia-300/5 p-3 text-xs text-fuchsia-100">
                              Recommended proposal: <span className="break-all font-mono">{recommendedActionId}</span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-[#07111f] p-12 text-center">
                <Sparkles className="mx-auto h-10 w-10 text-slate-600" />
                <p className="mt-4 text-sm text-slate-500">No persisted turns yet. Ask a concrete question about evidence, blockers, or the next decision.</p>
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-white">Proposal queue</h2>
                <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-400">{pendingActions.length} pending</span>
              </div>
              <div className="mt-4 space-y-3">
                {pendingActions.length ? pendingActions.map((action) => (
                  <article key={text(action.action_id)} className="rounded-2xl border border-fuchsia-300/15 bg-fuchsia-300/5 p-4">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-fuchsia-200">{text(action.action_type)}</div>
                    <h3 className="mt-1 text-sm font-semibold text-white">{text(action.title)}</h3>
                    <p className="mt-2 text-xs leading-5 text-slate-400">{text(action.rationale)}</p>
                    {action.origin_turn_id ? <div className="mt-3 break-all text-[10px] text-slate-500">From turn: {text(action.origin_turn_id)}</div> : null}
                    <div className="mt-3 flex items-center gap-2 text-[10px] text-amber-100"><AlertTriangle className="h-3 w-3" />Awaiting human review</div>
                  </article>
                )) : <div className="rounded-2xl border border-dashed border-white/10 p-6 text-center text-xs text-slate-500">No proposed actions awaiting review.</div>}
              </div>
              <Link href="/engineering/ai-studio" className="mt-4 block">
                <Button className="w-full" variant="outline"><CheckCircle2 className="mr-2 h-4 w-4" />Review in AI Studio</Button>
              </Link>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <h2 className="text-sm font-semibold text-white">Session summary</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">{text(session?.summary, 'Load a session to inspect its current engineering summary.')}</p>
              <div className="mt-4 space-y-2 text-xs text-slate-500">
                <div>{requirements.length} requirements</div>
                <div>{candidates.length} architecture candidates</div>
                <div>{actions.length} total actions</div>
                <div>{turns.length} persisted conversation turns</div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
