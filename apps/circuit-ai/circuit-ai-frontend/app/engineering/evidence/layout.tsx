import type { ReactNode } from 'react';

export default function EvidenceWorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-[100] overflow-auto bg-stone-100">
      {children}
    </div>
  );
}
