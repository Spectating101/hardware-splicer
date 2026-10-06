'use client';

import { useCallback, useEffect, useState } from 'react';

// Session storage on purpose: the token is a credential and should not outlive the browser tab.
const TOKEN_KEY = 'hs-operator-token';
const CHANGE_EVENT = 'hs-operator-token-change';

function read() {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

/** The operator token for this tab, shared by every panel that acts as a verified operator. */
export function useOperatorToken() {
  const [token, setTokenState] = useState('');

  useEffect(() => {
    setTokenState(read());
    const sync = () => setTokenState(read());
    window.addEventListener(CHANGE_EVENT, sync);
    return () => window.removeEventListener(CHANGE_EVENT, sync);
  }, []);

  const setToken = useCallback((value: string) => {
    try {
      if (value) window.sessionStorage.setItem(TOKEN_KEY, value);
      else window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // The token then lasts only until this page is closed.
    }
    setTokenState(value);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  return { token, setToken };
}
