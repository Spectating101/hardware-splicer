'use client';

import { useEffect, useRef, useState } from 'react';

export type Participant = {
  client_id: string;
  name: string;
  object_id?: string | null;
  mode?: string;
  verified?: boolean;
  seen_seconds_ago?: number;
};

export type LiveChange = { type: string; id: string; seq?: number | null };

export const PROJECT_CHANGE_EVENT = 'hs-project-change';

/** The Review page tells presence which object it is looking at without threading props through the layout. */
const focus: { objectId: string } = { objectId: '' };
export function setPresenceFocus(objectId: string) {
  focus.objectId = objectId;
}

const AUTHOR_KEY = 'hs-review-author';
const TOKEN_KEY = 'hs-operator-token';
const CLIENT_KEY = 'hs-client-id';
const HEARTBEAT_MS = 15000;

function safeGet(storage: 'local' | 'session', key: string) {
  try {
    return (storage === 'local' ? window.localStorage : window.sessionStorage).getItem(key) || '';
  } catch {
    return '';
  }
}

function clientId() {
  const existing = safeGet('session', CLIENT_KEY);
  if (/^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing;
  const bytes = new Uint8Array(12);
  window.crypto.getRandomValues(bytes);
  const fresh = Array.from(bytes, (b) => b.toString(36).padStart(2, '0')).join('').slice(0, 24);
  try {
    window.sessionStorage.setItem(CLIENT_KEY, fresh);
  } catch {
    // Without session storage the id lasts for this page load only.
  }
  return fresh;
}

/**
 * Live view of a project: who else is looking, and what changed. Everything here is information only. Failures
 * leave the page working exactly as it did before; nothing depends on the stream being up.
 */
export function useProjectLive(projectId: string, mode: string) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [connected, setConnected] = useState(false);
  const idRef = useRef('');

  useEffect(() => {
    if (!projectId || typeof window === 'undefined') return;
    const me = (idRef.current = idRef.current || clientId());
    const base = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}`;
    let stopped = false;

    async function heartbeat() {
      const name = safeGet('local', AUTHOR_KEY);
      const token = safeGet('session', TOKEN_KEY);
      try {
        await fetch(`${base}/presence`, {
          method: 'POST',
          headers: { 'content-type': 'application/json', ...(token ? { 'x-hs-operator-token': token } : {}) },
          body: JSON.stringify({ client_id: me, ...(name ? { name } : {}), ...(focus.objectId ? { object_id: focus.objectId } : {}), mode }),
          cache: 'no-store',
        });
      } catch {
        // Presence is best effort.
      }
    }

    async function refresh() {
      try {
        const response = await fetch(`${base}/presence`, { cache: 'no-store' });
        const body = await response.json();
        if (!stopped && body?.ok !== false && Array.isArray(body?.participants)) setParticipants(body.participants);
      } catch {
        // Keep the last known list.
      }
    }

    void heartbeat().then(refresh);
    const timer = window.setInterval(() => { void heartbeat().then(refresh); }, HEARTBEAT_MS);

    let source: EventSource | null = null;
    try {
      source = new EventSource(`${base}/events`);
      source.addEventListener('hello', () => setConnected(true));
      source.addEventListener('change', (event) => {
        try {
          const body = JSON.parse((event as MessageEvent).data) as { changes?: LiveChange[] };
          if (body.changes?.length) window.dispatchEvent(new CustomEvent(PROJECT_CHANGE_EVENT, { detail: body.changes }));
        } catch {
          // A malformed frame is ignored.
        }
        void refresh();
      });
      source.onerror = () => setConnected(false);
    } catch {
      setConnected(false);
    }

    const leave = () => {
      void fetch(`${base}/presence/${me}`, { method: 'DELETE', keepalive: true }).catch(() => undefined);
    };
    window.addEventListener('pagehide', leave);

    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener('pagehide', leave);
      source?.close();
      leave();
    };
  }, [projectId, mode]);

  const others = participants.filter((item) => item.client_id !== idRef.current);
  return { participants: others, connected };
}
