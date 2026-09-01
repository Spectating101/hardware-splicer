'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Boxes,
  Camera,
  CheckCircle2,
  CircleDot,
  Cpu,
  DraftingCompass,
  Gauge,
  GitBranch,
  Hammer,
  Layers3,
  PackageCheck,
  Recycle,
  Ruler,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import { usePageTitle } from '@/components/use-page-title';

const stages = [
  { label: 'Inventory', copy: 'Capture owned, salvaged, procurable and designed resources without erasing uncertainty.', icon: Boxes },
  { label: 'Goal', copy: 'Describe the machine, budget and constraints instead of beginning from an empty CAD canvas.', icon: CircleDot },
  { label: 'Candidates', copy: 'Compare architectures by reuse, missing capabilities, additional spend and engineering risk.', icon: GitBranch },
  { label: 'Resolve', copy: 'Turn abstract blockers into concrete measurements, identifications, documents and geometry tasks.', icon: ScanSearch },
  { label: 'Verify', copy: 'Use exact geometry, interface evidence and instrument-backed observations before raising authority.', icon: ShieldCheck },
  { label: 'Build', copy: 'Export the parts, evidence and remaining caveats needed to turn the selected architecture into hardware.', icon: PackageCheck },
];

const examples = [
  {
    title: 'Cyberdeck',
    copy: 'Reuse an existing display, compute board, keyboard, battery and enclosure hardware; fabricate only the adapters the assembly actually needs.',
    icon: Cpu,
  },
  {
    title: 'Inspection rover',
    copy: 'Compose donor motors, a camera, controller and chassis under a spending limit while keeping power and interface unknowns visible.',
    icon: Gauge,
  },
  {
    title: 'Lab & field tools',
    copy: 'Turn parts-bin hardware into test fixtures, instrument enclosures, portable consoles and one-off engineering equipment.',
    icon: Wrench,
  },
];

const engineering = [
  'Declared rigid assembly placement with live 3D move/rotate controls and deterministic precision nudges.',
  'STEP source identity, hash-bound project bindings and exact CadQuery/OCCT BREP display geometry.',
  'Exact surface anchors, mating geometry, insertion-path checks and adaptive transition refinement.',
  'Bounded adapter synthesis that generates real STEP and immediately checks contact/penetration against both parent solids.',
  'Operator claims, calibrated bench measurements and release authority kept as separate evidence classes.',
];

const boundaries = [
  'A photo-derived identification is provisional until stronger evidence closes the claim.',
  'A STEP envelope is not metrology and an exact mesh is not structural or fabrication proof.',
  'A generated adapter can pass bounded geometry while material, retention, tolerance and strength remain unresolved.',
  'Electrical compatibility, power-on, motion and release remain blocked until their own evidence is satisfied.',
];

export default function HomePage() {
  usePageTitle('Hardware Splicer | Build useful machines from what you have');

  return (
    <div className="min-h-screen bg-[#040811] text-slate-100">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#040811]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.07] text-cyan-100">
              <Layers3 className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">Hardware Splicer</div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">reuse-first physical systems synthesis</div>
            </div>
          </Link>
          <nav className="ml-auto hidden items-center gap-1 md:flex">
            <Link href="/workbench/mission" className="rounded-md px-3 py-2 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white">Mission</Link>
            <Link href="/workbench" className="rounded-md px-3 py-2 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white">Workbench</Link>
            <Link href="/review" className="rounded-md px-3 py-2 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white">Review</Link>
            <Link href="/docs" className="rounded-md px-3 py-2 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white">Docs</Link>
          </nav>
          <Link href="/workbench/mission" className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-cyan-300/25 bg-cyan-300/[0.08] px-3.5 py-2 text-xs font-semibold text-cyan-100 md:ml-2">
            Start with hardware <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden border-b border-white/10">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(34,211,238,0.13),transparent_38%),radial-gradient(circle_at_80%_22%,rgba(245,158,11,0.09),transparent_35%),radial-gradient(circle_at_55%_100%,rgba(139,92,246,0.08),transparent_42%)]" />
          <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
              <Recycle className="h-3.5 w-3.5" /> Waste → inventory → goal → new machine
            </div>
            <h1 className="mt-6 max-w-5xl text-5xl font-semibold leading-[1.03] tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
              Build useful machines
              <br />
              <span className="bg-gradient-to-r from-cyan-200 via-sky-300 to-amber-200 bg-clip-text text-transparent">from hardware you already have.</span>
            </h1>
            <p className="mt-6 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
              Hardware Splicer starts from real resources instead of an empty design. Give it salvaged parts, your parts bin, existing CAD and a goal; it helps decide what can be reused, what is missing, what must be measured, and what geometry can actually be defended before you build.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/workbench/mission" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100">
                <Camera className="h-4 w-4" /> Start from my hardware
              </Link>
              <Link href="/workbench" className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/[0.08]">
                <DraftingCompass className="h-4 w-4" /> Open engineering workbench
              </Link>
            </div>

            <div className="mt-14 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">Resource model</div>
                <div className="mt-2 text-sm font-semibold text-white">Owned · salvaged · procurable · designed</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">Different origins; one constrained synthesis problem.</div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">Engineering model</div>
                <div className="mt-2 text-sm font-semibold text-white">AI proposes · evidence constrains</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">Unknowns survive instead of being converted into confident-looking CAD.</div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">Output</div>
                <div className="mt-2 text-sm font-semibold text-white">A defensible build candidate</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">Reuse decisions, missing parts, generated geometry, evidence and remaining risks.</div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-[#06101a]">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="max-w-3xl">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">One product loop</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">Inventory → Goal → Candidates → Resolve → Verify → Build</h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">The advanced CAD/BREP tooling stays underneath this workflow. Users enter through the decision they are trying to make, then descend into exact engineering only when the candidate actually requires it.</p>
            </div>
            <div className="mt-9 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {stages.map((stage, index) => {
                const Icon = stage.icon;
                return (
                  <div key={stage.label} className="rounded-2xl border border-white/8 bg-black/15 p-5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-300/15 bg-cyan-300/[0.05] text-cyan-200"><Icon className="h-4 w-4" /></div>
                      <div><span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-600">0{index + 1}</span><div className="text-sm font-semibold text-white">{stage.label}</div></div>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-500">{stage.copy}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="border-b border-white/10">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-end justify-between gap-5">
              <div className="max-w-3xl">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300">Not limited to recycling</div>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">Use the same engine for salvage, DIY and custom tools.</h2>
              </div>
              <Link href="/workbench/mission" className="inline-flex items-center gap-1.5 text-sm font-semibold text-cyan-200">Try a mission <ArrowRight className="h-4 w-4" /></Link>
            </div>
            <div className="mt-8 grid gap-4 lg:grid-cols-3">
              {examples.map((example) => {
                const Icon = example.icon;
                return (
                  <div key={example.title} className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
                    <Icon className="h-5 w-5 text-amber-200" />
                    <h3 className="mt-4 text-lg font-semibold text-white">{example.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{example.copy}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-[#06101a]">
          <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_1fr] lg:px-8">
            <div>
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300"><Zap className="h-3.5 w-3.5" /> Fundamental engineering firepower</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">The niche is not an excuse to be weak.</h2>
              <div className="mt-6 space-y-3">
                {engineering.map((row) => (
                  <div key={row} className="flex gap-3 rounded-xl border border-white/8 bg-black/15 p-3.5 text-sm leading-6 text-slate-400">
                    <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-300" /> {row}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300"><Ruler className="h-3.5 w-3.5" /> Evidence boundaries</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">Powerful without pretending.</h2>
              <p className="mt-3 text-sm leading-6 text-slate-500">Hardware Splicer separates what the AI inferred, what the user observed, what geometry proved, what instruments measured and what a human has actually authorized.</p>
              <div className="mt-6 space-y-3">
                {boundaries.map((row) => (
                  <div key={row} className="flex gap-3 rounded-xl border border-amber-300/10 bg-amber-300/[0.025] p-3.5 text-sm leading-6 text-slate-400">
                    <Sparkles className="mt-1 h-4 w-4 shrink-0 text-amber-300" /> {row}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-5xl px-4 py-20 text-center sm:px-6 lg:px-8">
            <Hammer className="mx-auto h-7 w-7 text-cyan-200" />
            <h2 className="mt-5 text-3xl font-semibold tracking-tight text-white sm:text-4xl">What can you build with what you already have?</h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-slate-500">Start with the hardware. Hardware Splicer will keep the candidate, the missing pieces and the engineering evidence in the same loop.</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link href="/workbench/mission" className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950"><Recycle className="h-4 w-4" /> Start a reuse mission</Link>
              <Link href="/workbench" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white"><DraftingCompass className="h-4 w-4" /> Open workbench</Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}