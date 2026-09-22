'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowRight, BrainCircuit, FileCheck2 } from 'lucide-react';

export function ProjectStudioLauncher() {
  const pathname = usePathname();
  if (pathname.startsWith('/engineering/visual') || pathname.startsWith('/engineering/evidence')) return null;

  const insideStudio = pathname.startsWith('/engineering/studio');
  const href = insideStudio ? '/engineering/evidence' : '/engineering/studio';
  const eyebrow = insideStudio ? 'Review current state' : 'Start here';
  const label = insideStudio ? 'Project Evidence' : 'Project Studio';
  const Icon = insideStudio ? FileCheck2 : BrainCircuit;

  return (
    <Link
      href={href}
      className="fixed bottom-4 left-4 z-[80] inline-flex items-center gap-3 rounded-lg border border-stone-300 bg-white/95 px-4 py-3 text-sm font-semibold text-stone-900 shadow-lg shadow-stone-950/10 backdrop-blur transition hover:border-stone-400 hover:bg-stone-50"
      aria-label={`Open Hardware Splicer ${label}`}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-stone-100 text-stone-700">
        <Icon className="h-4 w-4" />
      </span>
      <span>
        <span className="block text-[10px] font-medium uppercase tracking-[0.12em] text-stone-500">{eyebrow}</span>
        <span className="block">{label}</span>
      </span>
      <ArrowRight className="h-4 w-4 text-stone-400" />
    </Link>
  );
}
