'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Check, FileCheck2, GitCompareArrows, Keyboard, Link2, Microscope, ScanLine, Waypoints } from 'lucide-react';

const modes = [
  { id: 'review', label: 'Review', href: '/engineering/evidence', icon: ScanLine },
  { id: 'compare', label: 'Compare', href: '/engineering/evidence/compare', icon: GitCompareArrows },
  { id: 'verify', label: 'Verify', href: '/engineering/evidence/verify', icon: FileCheck2 },
  { id: 'bringup', label: 'Bring-up', href: '/engineering/evidence/bringup', icon: Microscope },
] as const;

const shortcuts = [
  ['1 – 4', 'Switch between Review, Compare, Verify and Bring-up'],
  ['j / k', 'Next / previous object (Review)'],
  ['/', 'Search objects (Review)'],
  ['?', 'Show or hide this list'],
] as const;

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName);
}

export function EvidenceWorkspaceNav() {
  const pathname = usePathname();
  const router = useRouter();
  const search = useSearchParams();
  const project = search.get('project') || '';
  const suffix = project ? `?project=${encodeURIComponent(project)}` : '';
  const [helpOpen, setHelpOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const copiedTimer = useRef<number | null>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      const mode = ['1', '2', '3', '4'].indexOf(event.key);
      if (mode >= 0) {
        event.preventDefault();
        router.push(`${modes[mode].href}${suffix}`);
      } else if (event.key === '?') {
        event.preventDefault();
        setHelpOpen((open) => !open);
      } else if (event.key === 'Escape') {
        setHelpOpen(false);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [router, suffix]);

  useEffect(() => () => {
    if (copiedTimer.current) window.clearTimeout(copiedTimer.current);
  }, []);

  const copyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      if (copiedTimer.current) window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be blocked (insecure context, permissions); the address bar still works.
    }
  }, []);

  const iconButton = 'inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 font-medium text-stone-500 hover:bg-white/70 hover:text-stone-800';

  return (
    <nav aria-label="Evidence workspace" className="relative flex h-9 shrink-0 items-center overflow-x-auto whitespace-nowrap [scrollbar-width:none] border-b border-stone-200 bg-[#f7f7f5] px-3 text-xs">
      <div className="flex shrink-0 items-center gap-1">
        {modes.map((mode) => {
          const Icon = mode.icon;
          const active = mode.href === '/engineering/evidence'
            ? pathname === mode.href
            : pathname.startsWith(mode.href);
          return (
            <Link
              key={mode.id}
              href={`${mode.href}${suffix}`}
              aria-current={active ? 'page' : undefined}
              className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 font-medium transition ${active ? 'bg-white text-stone-950 shadow-sm ring-1 ring-stone-200' : 'text-stone-500 hover:bg-white/70 hover:text-stone-800'}`}
            >
              <Icon className="h-3.5 w-3.5" />{mode.label}
            </Link>
          );
        })}
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1 pl-2">
        <button type="button" onClick={copyLink} className={iconButton} aria-label="Copy a link to this exact view" title="Copy a link to this exact view">
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Link2 className="h-3.5 w-3.5" />}
          <span aria-live="polite">{copied ? 'Link copied' : 'Copy link'}</span>
        </button>
        <button
          type="button"
          onClick={() => setHelpOpen((open) => !open)}
          aria-expanded={helpOpen}
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (?)"
          className={iconButton}
        >
          <Keyboard className="h-3.5 w-3.5" />
        </button>
        <Link href={`/engineering/visual${suffix}`} className={iconButton}><Waypoints className="h-3.5 w-3.5" />Deep inspect</Link>
      </div>
      {helpOpen ? (
        <div role="dialog" aria-label="Keyboard shortcuts" className="fixed right-3 top-11 z-[110] w-80 whitespace-normal rounded-lg border border-stone-200 bg-white p-3 text-xs shadow-lg shadow-stone-950/10">
          <div className="mb-2 font-semibold text-stone-900">Keyboard shortcuts</div>
          <dl className="space-y-2">
            {shortcuts.map(([keys, label]) => (
              <div key={keys} className="flex items-start gap-3">
                <dt className="w-12 shrink-0"><kbd className="rounded border border-stone-300 bg-stone-50 px-1.5 py-0.5 font-mono text-[10px] text-stone-700">{keys}</kbd></dt>
                <dd className="text-stone-600">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </nav>
  );
}
