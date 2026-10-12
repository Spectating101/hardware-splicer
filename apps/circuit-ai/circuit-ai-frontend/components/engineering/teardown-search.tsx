'use client';

import { useRef, useState } from 'react';
import { LoaderCircle, Search } from 'lucide-react';
import { getProxyErrorMessage, isProxyFailure } from '@/lib/proxy-client';

type Result = { title: string; url: string; type: string; summary: string };
type Answer = { available: boolean; results: Result[]; note: string | null; attribution: string };

const IFIXIT = /^https:\/\/www\.ifixit\.com\/[A-Za-z0-9\-._~%/+?=&:@!$,;()*]{0,300}$/;

/** Looks for iFixit teardowns of the device a board came from. Only links come back: the content stays on iFixit, with their credit. */
export function TeardownSearch() {
  const [query, setQuery] = useState('');
  const [state, setState] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; answer?: Answer; message?: string }>({ status: 'idle' });
  const controller = useRef<AbortController | null>(null);

  const search = async () => {
    const text = query.trim();
    if (text.length < 3) { setState({ status: 'error', message: 'Type at least 3 characters.' }); return; }
    controller.current?.abort();
    const mine = new AbortController();
    controller.current = mine;
    setState({ status: 'loading' });
    try {
      const response = await fetch(`/api/proxy/engineering/teardowns/search?q=${encodeURIComponent(text)}`, { cache: 'no-store', signal: mine.signal });
      const body: unknown = await response.json();
      if (!body || isProxyFailure(body)) throw new Error(getProxyErrorMessage(body, 'The search failed.'));
      setState({ status: 'ready', answer: body as Answer });
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') return;
      setState({ status: 'error', message: caught instanceof Error ? caught.message : 'The search failed.' });
    }
  };

  const answer = state.answer;
  return (
    <section className="rounded-xl border border-stone-800 bg-stone-900/50 p-4" data-testid="teardown-search">
      <h2 className="text-sm font-semibold text-stone-100">Where did the board come from?</h2>
      <p className="mt-1 text-xs leading-5 text-stone-400">A teardown of the device often names the chips on its board. Search by the device&apos;s model name.</p>
      <form className="mt-2 flex gap-1.5" onSubmit={(event) => { event.preventDefault(); void search(); }}>
        <input data-testid="teardown-query" aria-label="Device name" value={query} maxLength={60} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Roku Streaming Stick" className="min-w-0 flex-1 rounded border border-stone-700 bg-stone-950 px-2 py-1 text-xs text-stone-100" />
        <button type="submit" data-testid="teardown-go" disabled={state.status === 'loading'} className="inline-flex items-center gap-1 rounded border border-stone-700 px-2 py-1 text-xs text-stone-200 hover:bg-stone-800 disabled:opacity-50">
          {state.status === 'loading' ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Search className="h-3 w-3" aria-hidden="true" />}Search
        </button>
      </form>
      {state.status === 'error' ? <p role="alert" className="mt-2 text-xs text-red-300" data-testid="teardown-error">{state.message}</p> : null}
      {answer ? (
        <div className="mt-2" data-testid="teardown-results">
          {!answer.available || answer.note ? <p className="text-xs leading-5 text-stone-400">{answer.note}</p> : null}
          <ul className="space-y-1.5">
            {answer.results.filter((r) => IFIXIT.test(r.url)).map((r) => (
              <li key={r.url} className="text-xs leading-4">
                <a href={r.url} target="_blank" rel="noreferrer noopener" className="font-medium text-sky-300 underline-offset-2 hover:underline">{r.title}</a>
                <span className="ml-1 text-stone-500">{r.type}</span>
                {r.summary ? <div className="text-stone-500">{r.summary}</div> : null}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] leading-4 text-stone-600">{answer.attribution}</p>
        </div>
      ) : null}
    </section>
  );
}
