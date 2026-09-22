import type { ReactNode } from 'react';
import { EvidenceWorkspaceNav } from '@/components/engineering/evidence-workspace-nav';

export default function EvidenceWorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-[100] flex flex-col overflow-hidden bg-stone-100">
      <EvidenceWorkspaceNav />
      <div className="min-h-0 flex-1 overflow-auto">
        {children}
      </div>
    </div>
  );
}
