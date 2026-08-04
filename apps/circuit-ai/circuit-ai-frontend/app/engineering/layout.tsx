import type { ReactNode } from 'react';
import Link from 'next/link';
import { ClipboardCheck, Cpu, FileSearch, Network, Route, UploadCloud } from 'lucide-react';
import { EngineeringExecutionCapabilityPanel } from '@/components/engineering-execution-capability-panel';

export default function EngineeringLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <div className="fixed left-1/2 top-3 z-[95] flex -translate-x-1/2 items-center gap-1 rounded-full border border-white/10 bg-[#07111f]/95 p-1 shadow-xl shadow-black/30 backdrop-blur-xl">
        <Link href="/engineering/preflight" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-cyan-100 hover:bg-cyan-300/10">
          <ClipboardCheck className="h-3.5 w-3.5" /> Preflight
        </Link>
        <Link href="/engineering/sources" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/5 hover:text-white">
          <UploadCloud className="h-3.5 w-3.5" /> Sources
        </Link>
        <Link href="/engineering/source-lab" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/5 hover:text-white">
          <FileSearch className="h-3.5 w-3.5" /> Source lab
        </Link>
        <Link href="/engineering/project-preflight" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/5 hover:text-white">
          <Route className="h-3.5 w-3.5" /> Project plan
        </Link>
        <Link href="/engineering" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/5 hover:text-white">
          <Network className="h-3.5 w-3.5" /> Project inspector
        </Link>
      </div>
      {children}
      <details className="group fixed bottom-4 right-4 z-[90] w-[min(24rem,calc(100vw-2rem))] rounded-[1.35rem] border border-cyan-300/20 bg-[#07111f]/95 shadow-2xl shadow-black/50 backdrop-blur-xl">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
          <span className="inline-flex items-center gap-2"><Cpu className="h-4 w-4" />Execution host truth</span>
          <span className="text-[10px] text-slate-500 group-open:hidden">Open</span>
          <span className="hidden text-[10px] text-slate-500 group-open:inline">Close</span>
        </summary>
        <div className="max-h-[70vh] overflow-y-auto border-t border-white/8 p-3">
          <EngineeringExecutionCapabilityPanel />
        </div>
      </details>
    </div>
  );
}
