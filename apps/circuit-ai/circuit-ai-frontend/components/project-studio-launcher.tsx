'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BrainCircuit, ArrowRight, Waypoints } from 'lucide-react';

export function ProjectStudioLauncher() {
  const pathname = usePathname();
  if (pathname.startsWith('/engineering/visual')) return null;

  const insideStudio = pathname.startsWith('/engineering/studio');
  const href = insideStudio ? '/engineering/visual' : '/engineering/studio';
  const eyebrow = insideStudio ? 'Open the artifact' : 'Start here';
  const label = insideStudio ? 'Visual Workbench' : 'Project Studio';
  const Icon = insideStudio ? Waypoints : BrainCircuit;

  return (
    <Link
      href={href}
      className="fixed bottom-4 left-4 z-[80] inline-flex items-center gap-3 rounded-2xl border border-cyan-300/25 bg-[#07111f]/95 px-4 py-3 text-sm font-semibold text-white shadow-[0_18px_60px_rgba(2,6,23,0.55)] backdrop-blur transition hover:border-cyan-200/45 hover:bg-[#0a1a2d]"
      aria-label={`Open Hardware Splicer ${label}`}
    >
      <span className="rounded-xl border border-cyan-300/20 bg-cyan-300/10 p-2 text-cyan-100">
        <Icon className="h-4 w-4" />
      </span>
      <span>
        <span className="block text-[10px] uppercase tracking-[0.18em] text-cyan-300">{eyebrow}</span>
        <span className="block">{label}</span>
      </span>
      <ArrowRight className="h-4 w-4 text-slate-400" />
    </Link>
  );
}
