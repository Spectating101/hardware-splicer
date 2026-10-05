'use client';

import { useCallback, useEffect, useState } from 'react';
import { BadgeCheck, Bot, CheckCircle2, CircleDot, LoaderCircle, MapPin, MessageSquare, RotateCcw, User, X } from 'lucide-react';
import type { PlacedPin, ViewerPin } from '@/components/engineering/viewer-overlay';

type AuthorKind = 'human' | 'agent' | 'system';

type ThreadEvent = {
  seq: number;
  type: 'comment' | 'resolve' | 'reopen';
  author: { kind: AuthorKind; id: string };
  author_verified?: boolean;
  verified_by?: string;
  body: string;
  created_at: string;
};

type Thread = {
  thread_id: string;
  anchor: {
    revision: number;
    object_id?: string | null;
    finding_ref?: string | null;
    artifact?: { relative: string; kind: string } | null;
    position?: { x_mm: number; y_mm: number } | null;
  };
  status: 'open' | 'resolved';
  comment_count: number;
  events?: ThreadEvent[];
};

const AUTHOR_KEY = 'hs-review-author';
// Session storage on purpose: the token is a credential and should not outlive the browser tab.
const TOKEN_KEY = 'hs-operator-token';

function readStoredAuthor() {
  try {
    return window.localStorage.getItem(AUTHOR_KEY) || '';
  } catch {
    return '';
  }
}

function readStoredToken() {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

function errorMessage(payload: unknown, fallback: string) {
  const record = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const detail = record.detail as Record<string, unknown> | string | undefined;
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
  if (typeof detail === 'string') return detail;
  if (typeof record.error === 'string') return record.error;
  if (typeof record.message === 'string') return record.message;
  return fallback;
}

async function request(url: string, init?: RequestInit, token = '') {
  const headers = new Headers(init?.headers);
  if (token) headers.set('x-hs-operator-token', token);
  const response = await fetch(url, { cache: 'no-store', ...init, headers });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  // The UI proxy reports upstream failures as HTTP 200 with {ok: false, status, error}; treat both shapes as failure.
  const proxied = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  if (!response.ok || proxied.ok === false) {
    const status = typeof proxied.status === 'number' ? proxied.status : response.status;
    throw new Error(errorMessage(payload, `Request failed (${status})`));
  }
  return payload as Record<string, unknown>;
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function AuthorBadge({ author, verified }: { author: ThreadEvent['author']; verified: boolean }) {
  const Icon = author.kind === 'agent' ? Bot : User;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-800">
      <Icon className="h-3 w-3 text-stone-400" aria-hidden="true" />
      {author.id}
      <span className="rounded bg-stone-100 px-1 py-px text-[10px] font-normal text-stone-500">{author.kind}</span>
      {verified ? (
        <span className="inline-flex items-center gap-0.5 text-[10px] font-normal text-emerald-700" title="This author held an operator token issued by whoever controls the registry. It is still only a comment.">
          <BadgeCheck className="h-3 w-3" aria-hidden="true" />verified
        </span>
      ) : (
        <span className="text-[10px] font-normal text-stone-400" title="The name was typed in and is not verified.">unverified</span>
      )}
    </span>
  );
}

export function ReviewThreadsPanel({
  projectId,
  revision,
  objectId,
  objectLabel,
  activeArtifact = null,
  pendingPin = null,
  onRequestPin,
  onClearPin,
  onPinsChange,
}: {
  projectId: string;
  revision: number | null;
  objectId: string;
  objectLabel: string;
  activeArtifact?: { relative: string; kind: string } | null;
  pendingPin?: PlacedPin | null;
  onRequestPin?: () => void;
  onClearPin?: () => void;
  onPinsChange?: (pins: ViewerPin[]) => void;
}) {
  const base = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/threads`;
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [author, setAuthor] = useState('');
  const [token, setToken] = useState('');
  const [draft, setDraft] = useState('');
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');

  useEffect(() => {
    setAuthor(readStoredAuthor());
    setToken(readStoredToken());
  }, []);

  const load = useCallback(async () => {
    if (!projectId || !objectId) return;
    setLoading(true);
    setError('');
    try {
      const list = await request(`${base}?object_id=${encodeURIComponent(objectId)}`, undefined, token);
      const summaries = (Array.isArray(list.threads) ? list.threads : []) as Thread[];
      const full = await Promise.all(summaries.map(async (summary) => {
        const detail = await request(`${base}/${encodeURIComponent(summary.thread_id)}`, undefined, token);
        return detail.thread as Thread;
      }));
      setThreads(full);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Discussion could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [base, objectId, projectId, token]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const pins: ViewerPin[] = threads
      .filter((thread) => thread.anchor.position && thread.anchor.artifact)
      .map((thread) => ({
        id: thread.thread_id,
        relative: thread.anchor.artifact!.relative,
        x_mm: thread.anchor.position!.x_mm,
        y_mm: thread.anchor.position!.y_mm,
        label: thread.events?.[0]?.body || 'Comment',
        tone: thread.status === 'resolved' ? 'resolved' : 'open',
      }));
    onPinsChange?.(pins);
    return () => onPinsChange?.([]);
  }, [threads, onPinsChange]);

  function pinNumber(thread: Thread) {
    if (!thread.anchor.position || !thread.anchor.artifact) return null;
    const relative = thread.anchor.artifact.relative;
    const same = threads.filter((item) => item.anchor.position && item.anchor.artifact?.relative === relative);
    return same.findIndex((item) => item.thread_id === thread.thread_id) + 1;
  }

  function rememberAuthor(value: string) {
    setAuthor(value);
    try {
      window.localStorage.setItem(AUTHOR_KEY, value);
    } catch {
      // Remembering the name is a convenience only.
    }
  }

  function rememberToken(value: string) {
    setToken(value);
    try {
      if (value) window.sessionStorage.setItem(TOKEN_KEY, value);
      else window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // The token then lasts only until the panel unmounts.
    }
  }

  async function submit(key: string, url: string, body: Record<string, unknown>) {
    setBusy(key);
    setError('');
    try {
      await request(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }, token);
      await load();
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The request failed.');
      return false;
    } finally {
      setBusy('');
    }
  }

  // With an operator token the server decides who is speaking, so no typed name is needed or sent.
  const verifiedMode = token.trim().length > 0;
  const authorReady = verifiedMode || author.trim().length > 0;
  const authorField = verifiedMode ? {} : { author: { kind: 'human', id: author.trim() } };

  async function startThread() {
    if (!authorReady || !draft.trim() || revision === null) return;
    const ok = await submit('new', base, {
      anchor: pendingPin
        ? { revision, object_id: objectId, artifact: { relative: pendingPin.relative, kind: pendingPin.kind }, position: { x_mm: pendingPin.x_mm, y_mm: pendingPin.y_mm } }
        : { revision, object_id: objectId },
      ...authorField,
      body: draft.trim(),
    });
    if (ok) {
      setDraft('');
      onClearPin?.();
    }
  }

  async function addEvent(thread: Thread, type: ThreadEvent['type'], body = '') {
    if (!authorReady) return;
    const lastSeq = thread.events?.length ?? 0;
    const ok = await submit(`${thread.thread_id}:${type}`, `${base}/${encodeURIComponent(thread.thread_id)}/events`, {
      type,
      ...authorField,
      body,
      expected_event_seq: lastSeq,
    });
    if (ok && type === 'comment') setReplies((current) => ({ ...current, [thread.thread_id]: '' }));
  }

  return (
    <div data-testid="review-threads">
      <h2 className="text-sm font-semibold text-stone-900">Discussion on {objectLabel}</h2>
      <p className="mt-1 text-[11px] leading-4 text-stone-500">
        Comments never change findings, evidence or authority. Names are self-declared and not verified.
      </p>

      {error ? <div role="alert" className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div> : null}

      {verifiedMode ? (
        <div className="mt-4 flex items-center justify-between gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-[11px] text-emerald-900">
          <span className="inline-flex items-center gap-1"><BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />Commenting with an operator token</span>
          <button type="button" onClick={() => rememberToken('')} className="font-medium underline">Remove</button>
        </div>
      ) : (
        <>
          <label className="mt-4 block text-[11px] font-medium text-stone-500">
            Your name
            <input
              value={author}
              onChange={(event) => rememberAuthor(event.target.value)}
              maxLength={120}
              placeholder="Who is commenting"
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-900 outline-none focus:border-stone-500"
            />
          </label>
          <details className="mt-2 text-[11px] text-stone-500">
            <summary className="cursor-pointer select-none">Have an operator token?</summary>
            <input
              type="password"
              autoComplete="off"
              aria-label="Operator token"
              placeholder="Paste it to comment as a verified operator"
              onChange={(event) => rememberToken(event.target.value.trim())}
              className="mt-1.5 w-full rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-900 outline-none focus:border-stone-500"
            />
            <p className="mt-1 leading-4">Kept for this browser tab only. The name then comes from the server&apos;s operator list.</p>
          </details>
        </>
      )}

      <div className="mt-4 space-y-3">
        {loading && !threads.length ? <div className="flex items-center gap-2 text-xs text-stone-500"><LoaderCircle className="h-3.5 w-3.5 animate-spin" />Loading discussion</div> : null}
        {!loading && !threads.length && !error ? <div className="rounded-md border border-dashed border-stone-300 p-3 text-xs text-stone-500">No discussion on this object yet.</div> : null}

        {threads.map((thread) => {
          const resolved = thread.status === 'resolved';
          const stale = revision !== null && thread.anchor.revision !== revision;
          return (
            <section key={thread.thread_id} className={`rounded-md border ${resolved ? 'border-stone-200 bg-stone-50' : 'border-stone-300 bg-white'}`}>
              <header className="flex items-center justify-between gap-2 border-b border-stone-100 px-3 py-2">
                <span className="inline-flex items-center gap-1.5 text-[11px] text-stone-500">
                  {resolved ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" /> : <CircleDot className="h-3.5 w-3.5 text-amber-600" aria-hidden="true" />}
                  {resolved ? 'Resolved' : 'Open'}
                </span>
                {pinNumber(thread) ? <span className="inline-flex items-center gap-1 text-[10px] text-stone-500"><MapPin className="h-3 w-3" aria-hidden="true" />Pin {pinNumber(thread)} · {thread.anchor.position!.x_mm}, {thread.anchor.position!.y_mm} mm</span> : null}
                <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${stale ? 'bg-amber-50 text-amber-700' : 'bg-stone-100 text-stone-500'}`} title={stale ? 'Written against an earlier revision' : 'Written against this revision'}>
                  Rev {thread.anchor.revision}{stale ? ' · earlier' : ''}
                </span>
              </header>
              <ol className="m-0 list-none divide-y divide-stone-100 p-0">
                {(thread.events || []).map((event) => (
                  <li key={event.seq} className="px-3 py-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                      <AuthorBadge author={event.author} verified={event.author_verified === true} />
                      <time className="text-[10px] text-stone-400" dateTime={event.created_at}>{formatTime(event.created_at)}</time>
                    </div>
                    {event.type === 'comment' ? (
                      <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-stone-700">{event.body}</p>
                    ) : (
                      <p className="mt-1 text-xs italic leading-5 text-stone-500">{event.type === 'resolve' ? 'Marked resolved' : 'Reopened'}{event.body ? `: ${event.body}` : ''}</p>
                    )}
                  </li>
                ))}
              </ol>
              <footer className="space-y-2 border-t border-stone-100 px-3 py-2.5">
                <textarea
                  value={replies[thread.thread_id] || ''}
                  onChange={(event) => setReplies((current) => ({ ...current, [thread.thread_id]: event.target.value }))}
                  rows={2}
                  maxLength={4000}
                  placeholder="Reply"
                  aria-label={`Reply to thread ${thread.thread_id}`}
                  className="w-full resize-y rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-900 outline-none focus:border-stone-500"
                />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={!authorReady || !(replies[thread.thread_id] || '').trim() || busy !== ''}
                    onClick={() => void addEvent(thread, 'comment', (replies[thread.thread_id] || '').trim())}
                    className="inline-flex h-7 items-center gap-1 rounded-md bg-stone-900 px-2.5 text-xs font-medium text-white hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-300"
                  >
                    <MessageSquare className="h-3 w-3" aria-hidden="true" />Reply
                  </button>
                  <button
                    type="button"
                    disabled={!authorReady || busy !== ''}
                    onClick={() => void addEvent(thread, resolved ? 'reopen' : 'resolve')}
                    className="inline-flex h-7 items-center gap-1 rounded-md border border-stone-300 px-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400"
                  >
                    {resolved ? <><RotateCcw className="h-3 w-3" aria-hidden="true" />Reopen</> : <><CheckCircle2 className="h-3 w-3" aria-hidden="true" />Resolve</>}
                  </button>
                </div>
              </footer>
            </section>
          );
        })}
      </div>

      <div className="mt-5 border-t border-stone-200 pt-4">
        <label className="block text-[11px] font-medium text-stone-500" htmlFor="new-thread-body">Start a thread{revision !== null ? ` on Rev ${revision}` : ''}</label>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {pendingPin ? (
            <span className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-900">
              <MapPin className="h-3 w-3" aria-hidden="true" />Pinned at {pendingPin.x_mm}, {pendingPin.y_mm} mm
              <button type="button" onClick={onClearPin} aria-label="Remove the pin" className="ml-1 rounded hover:bg-amber-100"><X className="h-3 w-3" /></button>
            </span>
          ) : (
            <button
              type="button"
              onClick={onRequestPin}
              disabled={!activeArtifact || !onRequestPin}
              title={activeArtifact ? `Pin this comment to a location on ${activeArtifact.relative}` : 'No artifact is loaded'}
              className="inline-flex h-7 items-center gap-1 rounded-md border border-stone-300 px-2 text-[11px] font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400"
            >
              <MapPin className="h-3 w-3" aria-hidden="true" />Pin to artifact
            </button>
          )}
        </div>
        <textarea
          id="new-thread-body"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          maxLength={4000}
          placeholder={`What should a reviewer know about ${objectLabel}?`}
          className="mt-1 w-full resize-y rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-900 outline-none focus:border-stone-500"
        />
        <button
          type="button"
          disabled={!authorReady || !draft.trim() || revision === null || busy !== ''}
          onClick={() => void startThread()}
          className="mt-2 inline-flex h-8 items-center gap-1.5 rounded-md bg-stone-900 px-3 text-xs font-medium text-white hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-300"
        >
          {busy === 'new' ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : <MessageSquare className="h-3 w-3" aria-hidden="true" />}Start thread
        </button>
        {!authorReady ? <p className="mt-2 text-[11px] text-stone-500">Enter your name above to comment.</p> : null}
      </div>
    </div>
  );
}
