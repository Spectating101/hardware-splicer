import Link from 'next/link';

export default function ReuseMissionNotFound() {
  return (
    <main className="min-h-screen bg-[#040811] px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-2xl rounded-xl border border-white/10 bg-white/[0.02] p-5">
        <div className="text-sm font-semibold text-white">Reuse mission not found.</div>
        <Link href="/workbench" className="mt-4 inline-flex rounded-lg border border-cyan-300/15 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-300/[0.05]">Open engineering workbench</Link>
      </div>
    </main>
  );
}
