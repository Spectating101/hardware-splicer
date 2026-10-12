'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowRight, BrainCircuit } from 'lucide-react';

/**
 * Floating entry point for pages outside the engineering workspace (e.g. the maker tools).
 * The front door and every /engineering page carry their own navigation, so it stays out of their way.
 */
export function ProjectStudioLauncher() {
  const pathname = usePathname();
  if (pathname === '/' || pathname.startsWith('/engineering')) return null;

  return (
    <Link
      href="/engineering/studio"
      className="fixed bottom-4 left-4 z-[80] inline-flex items-center gap-3 rounded-lg border border-stone-300 bg-white/95 px-4 py-3 text-sm font-semibold text-stone-900 shadow-lg shadow-stone-950/10 backdrop-blur transition hover:border-stone-400 hover:bg-stone-50"
      aria-label="Open Hardware Splicer Project Studio"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-stone-100 text-stone-700">
        <BrainCircuit className="h-4 w-4" />
      </span>
      <span>
        <span className="block text-[10px] font-medium uppercase tracking-[0.12em] text-stone-500">Start here</span>
        <span className="block">Project Studio</span>
      </span>
      <ArrowRight className="h-4 w-4 text-stone-400" />
    </Link>
  );
}
