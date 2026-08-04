'use client';

import dynamic from 'next/dynamic';

const HsPreflightWorkbench = dynamic(
  () => import('@/components/hs-preflight-workbench').then((module) => module.HsPreflightWorkbench),
  {
    ssr: false,
    loading: () => (
      <main className="flex min-h-screen items-center justify-center bg-[#040b14] text-sm text-slate-400">
        Loading HS Preflight…
      </main>
    ),
  },
);

export default function EngineeringPreflightPage() {
  return <HsPreflightWorkbench />;
}
