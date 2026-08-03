import type { ReactNode } from 'react';
import { Cpu } from 'lucide-react';
import { EngineeringExecutionCapabilityPanel } from '@/components/engineering-execution-capability-panel';

export default function EngineeringLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
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
