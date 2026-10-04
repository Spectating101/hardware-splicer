'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { FileCheck2, GitCompareArrows, Microscope, ScanLine, Waypoints } from 'lucide-react';

const modes = [
  { id: 'review', label: 'Review', href: '/engineering/evidence', icon: ScanLine },
  { id: 'compare', label: 'Compare', href: '/engineering/evidence/compare', icon: GitCompareArrows },
  { id: 'verify', label: 'Verify', href: '/engineering/evidence/verify', icon: FileCheck2 },
  { id: 'bringup', label: 'Bring-up', href: '/engineering/evidence/bringup', icon: Microscope },
] as const;

export function EvidenceWorkspaceNav() {
  const pathname = usePathname();
  const search = useSearchParams();
  const project = search.get('project') || '';
  const suffix = project ? `?project=${encodeURIComponent(project)}` : '';

  return (
    <nav className="flex h-9 shrink-0 items-center border-b border-stone-200 bg-[#f7f7f5] px-3 text-xs">
      <div className="flex items-center gap-1">
        {modes.map((mode) => {
          const Icon = mode.icon;
          const active = mode.href === '/engineering/evidence'
            ? pathname === mode.href
            : pathname.startsWith(mode.href);
          return (
            <Link
              key={mode.id}
              href={`${mode.href}${suffix}`}
              className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 font-medium transition ${active ? 'bg-white text-stone-950 shadow-sm ring-1 ring-stone-200' : 'text-stone-500 hover:bg-white/70 hover:text-stone-800'}`}
            >
              <Icon className="h-3.5 w-3.5" />{mode.label}
            </Link>
          );
        })}
      </div>
      <div className="ml-auto flex items-center gap-2">
        <span className="hidden text-[10px] text-stone-400 md:inline">Evidence / release-assurance workspace</span>
        <Link href={`/engineering/visual${suffix}`} className="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 font-medium text-stone-400 hover:bg-white/70 hover:text-stone-700"><Waypoints className="h-3.5 w-3.5" />Deep inspect</Link>
      </div>
    </nav>
  );
}