'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Boxes,
  Camera,
  CircuitBoard,
  Cpu,
  Lightbulb,
  Recycle,
  Scissors,
  ShieldAlert,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { usePageTitle } from '@/components/use-page-title';

const killerFlows = [
  {
    icon: Camera,
    eyebrow: 'Scan',
    title: 'Point your phone at any board.',
    copy: 'Upload a photo or capture from your camera. Circuit.AI identifies every chip, passive, and connector — then tells you in plain English what each section actually does.',
    cta: 'Open Scan',
    href: '/scan',
    accent: 'from-cyan-500/20 to-sky-500/10',
    stroke: 'border-cyan-300/50',
  },
  {
    icon: Scissors,
    eyebrow: 'Salvage',
    title: 'Cut and reuse modules from anything.',
    copy: 'Got a dead router, microwave, or vape? We decompose the board into functional modules and show you exactly where to cut to reuse the parts that still work.',
    cta: 'See salvage plans',
    href: '/scan?mode=salvage',
    accent: 'from-amber-500/20 to-orange-500/10',
    stroke: 'border-amber-300/50',
  },
  {
    icon: Wrench,
    eyebrow: 'Build',
    title: 'Wire it up without knowing electronics.',
    copy: 'Drop salvaged modules onto a virtual breadboard. Jarvis wires them into a working project, explains every connection, and flags anything dangerous before you power it on.',
    cta: 'Open Build',
    href: '/build',
    accent: 'from-violet-500/20 to-fuchsia-500/10',
    stroke: 'border-violet-300/50',
  },
];

const beliefs = [
  {
    icon: Recycle,
    title: 'E-waste is a parts bin.',
    copy: 'A broken microwave has a perfectly good transformer. A dead router has a Wi-Fi module worth salvaging. We help you see it that way.',
  },
  {
    icon: Lightbulb,
    title: 'You do not need to be an EE.',
    copy: 'We answer the questions forums make you feel stupid for asking. What is this chip? Will it blow up if I connect it to 9V? What can I actually build with this stuff?',
  },
  {
    icon: ShieldAlert,
    title: 'Safety first, always.',
    copy: 'Mains voltage, lithium cells, and bulk capacitors kill people. Every plan runs through a safety classifier — scary stuff is gated behind clear warnings and capability checks.',
  },
  {
    icon: Cpu,
    title: 'Graduate into real tools.',
    copy: 'When you outgrow the breadboard, export a real KiCad project and send it to a fab. The AI grows with you — beginner mode to professional output.',
  },
];

const projectExamples = [
  { title: 'Weather station', parts: 'ESP32 + DHT22 + OLED', difficulty: 'Beginner' },
  { title: 'Salvaged speaker amp', parts: 'Old radio amp + 5V buck + any speaker', difficulty: 'Beginner' },
  { title: 'Smart lamp', parts: 'ESP32 + relay module + wall bulb', difficulty: 'Intermediate' },
  { title: 'Router Wi-Fi repeater', parts: 'Old router Wi-Fi module + USB-C 5V + antenna', difficulty: 'Intermediate' },
  { title: 'Battery bank from laptop cells', parts: '18650 cells + BMS + buck/boost', difficulty: 'Advanced' },
  { title: 'Retro game handheld', parts: 'Raspberry Pi + screen + old Gameboy shell', difficulty: 'Advanced' },
];

export default function HomePage() {
  usePageTitle('Circuit.AI | Build Electronics From Anything');

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-slate-100">
      <SiteHeader />

      <main>
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-white/5">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(34,211,238,0.15),transparent_40%),radial-gradient(circle_at_80%_20%,rgba(249,115,22,0.12),transparent_40%),radial-gradient(circle_at_50%_90%,rgba(167,139,250,0.10),transparent_40%)]" />
          <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.24em] text-cyan-300/90"
            >
              <Sparkles className="h-3.5 w-3.5" />
              AI copilot for makers, tinkerers, repair folks
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05 }}
              className="max-w-4xl text-5xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-7xl"
            >
              Build electronics
              <br />
              <span className="bg-gradient-to-r from-cyan-300 via-violet-300 to-amber-300 bg-clip-text text-transparent">
                from anything.
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              className="mt-6 max-w-2xl text-lg leading-8 text-slate-300"
            >
              Point your phone at a dead gadget and we&apos;ll tell you what&apos;s salvageable. Drop those parts
              on a virtual breadboard and we&apos;ll wire them into something that works. You don&apos;t need to
              know what a capacitor does. Jarvis handles that — you bring the curiosity.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.25 }}
              className="mt-8 flex flex-wrap items-center gap-3"
            >
              <Button asChild size="lg" className="rounded-full bg-white text-slate-900 hover:bg-slate-100">
                <Link href="/scan">
                  <Camera className="mr-2 h-5 w-5" />
                  Scan a board
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="rounded-full border-white/20 bg-white/5 text-white hover:bg-white/10">
                <Link href="/build">
                  <Wrench className="mr-2 h-5 w-5" />
                  Start building
                </Link>
              </Button>
              <Link href="/parts" className="ml-1 inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors">
                <Boxes className="h-4 w-4" />
                I already have a parts bin
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>

            {/* Mini stat row */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="mt-14 grid gap-4 sm:grid-cols-3"
            >
              {[
                ['Photo in', '~5s average identification'],
                ['Modules mapped', '200+ common parts preloaded'],
                ['Safety gated', 'Mains & lithium always flagged'],
              ].map(([title, copy]) => (
                <div key={title} className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{title}</div>
                  <div className="mt-1 text-sm font-medium text-slate-200">{copy}</div>
                </div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* Three killer flows */}
        <section className="border-b border-white/5 bg-[#070b14]">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
            <div className="mb-12 max-w-3xl">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-400/80">What it does</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Three flows. One product. Zero EE degree required.
              </h2>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              {killerFlows.map((flow) => {
                const Icon = flow.icon;
                return (
                  <Link
                    key={flow.eyebrow}
                    href={flow.href}
                    className={`group relative overflow-hidden rounded-3xl border ${flow.stroke} bg-gradient-to-br ${flow.accent} p-6 transition-transform hover:-translate-y-1`}
                  >
                    <div className="absolute inset-0 bg-[#0a0f1a]/70" />
                    <div className="relative">
                      <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-white">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="text-xs font-semibold uppercase tracking-[0.24em] text-white/60">
                        {flow.eyebrow}
                      </div>
                      <h3 className="mt-2 text-xl font-semibold text-white">{flow.title}</h3>
                      <p className="mt-3 text-sm leading-6 text-slate-300">{flow.copy}</p>
                      <div className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-white">
                        {flow.cta}
                        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        {/* What we believe */}
        <section className="border-b border-white/5">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
            <div className="mb-12 max-w-3xl">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-400/80">The point</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Electronics should feel like Lego, not like a textbook.
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-400">
                Every other tool in this space assumes you&apos;re already an engineer. We&apos;re building for
                everyone else — the kids hacking gameboys, the artists embedding LEDs, the repair folks
                who don&apos;t want to throw things out, the Arduino owners who never graduated past blinking.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {beliefs.map((b) => {
                const Icon = b.icon;
                return (
                  <div key={b.title} className="rounded-2xl border border-white/5 bg-white/[0.02] p-6">
                    <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/10 to-white/5 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="text-base font-semibold text-white">{b.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-400">{b.copy}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Project examples */}
        <section className="border-b border-white/5 bg-[#070b14]">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
            <div className="mb-10 flex items-end justify-between gap-4 flex-wrap">
              <div className="max-w-2xl">
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-400/80">What you can build</div>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  Projects our users start with.
                </h2>
              </div>
              <Button asChild variant="outline" className="rounded-full border-white/20 bg-white/5 text-white hover:bg-white/10">
                <Link href="/parts">
                  <Boxes className="mr-2 h-4 w-4" />
                  What can I build from my parts?
                </Link>
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projectExamples.map((p) => (
                <div key={p.title} className="group rounded-2xl border border-white/5 bg-white/[0.02] p-5 hover:border-white/15 transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-base font-medium text-white">{p.title}</h3>
                    <span className={`text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 ${
                      p.difficulty === 'Beginner' ? 'bg-emerald-400/15 text-emerald-300' :
                      p.difficulty === 'Intermediate' ? 'bg-amber-400/15 text-amber-300' :
                      'bg-rose-400/15 text-rose-300'
                    }`}>{p.difficulty}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{p.parts}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Advanced escape hatch / developer surfaces */}
        <section>
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="rounded-3xl border border-white/5 bg-white/[0.02] p-8">
              <div className="flex items-start gap-4 flex-wrap">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/30 to-violet-500/30 text-white">
                  <CircuitBoard className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">For developers and power users</div>
                  <h3 className="mt-2 text-xl font-semibold text-white">You&apos;re past beginner? We&apos;ve got you covered too.</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                    Full KiCad project import/export. Real PCB validation with DRC. SPICE simulation. BOM pricing
                    and fab package generation. Public API with Python + JS SDKs. Graduate into the full stack
                    whenever you&apos;re ready — the canvas and the AI travel with you.
                  </p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <Link href="/cad" className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                      <Zap className="h-3.5 w-3.5" />
                      Advanced / KiCad
                    </Link>
                    <Link href="/docs" className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                      API Docs
                    </Link>
                    <Link href="/playground" className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                      Playground
                    </Link>
                    <Link href="/dashboard/keys" className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                      API Keys
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
