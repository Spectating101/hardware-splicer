'use client';

export default function ReuseMissionError({ reset }: { reset: () => void }) {
  return (
    <main className="min-h-screen bg-[#040811] px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-2xl rounded-xl border border-red-300/15 bg-red-300/[0.035] p-5">
        <div className="text-sm font-semibold text-red-200">Reuse mission could not be rendered.</div>
        <p className="mt-2 text-sm text-slate-400">The canonical engineering workbench remains separate and unchanged.</p>
        <button type="button" onClick={reset} className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/5">Retry mission view</button>
      </div>
    </main>
  );
}
