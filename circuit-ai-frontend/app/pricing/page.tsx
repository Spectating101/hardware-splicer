'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Check, Coins, Factory, KeyRound, PlayCircle, ShieldCheck, Star } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

const planCopy = [
  {
    name: 'Free',
    description: 'For proving the contract and testing with small files.',
    price: { monthly: 0, annual: 0 },
    features: ['50 requests / month', 'Basic analysis surface', 'Docs and playground access', 'Best for validation and demos'],
    buttonText: 'Create demo key',
    href: '/dashboard/keys',
    popular: false,
  },
  {
    name: 'Pro',
    description: 'For teams turning analysis into an actual workflow.',
    price: { monthly: 99, annual: 990 },
    features: ['Unlimited requests', 'Streaming and richer telemetry', 'Priority support', 'Best fit for active integrations'],
    buttonText: 'Open playground',
    href: '/playground',
    popular: true,
  },
  {
    name: 'Enterprise',
    description: 'For backend-heavy deployments that need explicit operating boundaries.',
    price: { monthly: 'Custom', annual: 'Custom' },
    features: ['Dedicated infrastructure', 'Custom deployment targets', 'Operational support', 'Best fit for fabrication or ops programs'],
    buttonText: 'Review status',
    href: '/status',
    popular: false,
  },
];

const fitNotes = [
  { icon: KeyRound, title: 'Free tier is for trust', copy: 'Use it to verify auth, request shape, and frontend wiring before you scale complexity.' },
  { icon: PlayCircle, title: 'Pro is for iteration', copy: 'Use it when the frontend needs to keep pace with real backend behavior and operator feedback.' },
  { icon: Factory, title: 'Enterprise is for workflow ownership', copy: 'Use it when your backend and operations model matter more than a generic feature checklist.' },
];

export default function PricingPage() {
  usePageTitle('Pricing | Circuit.AI');
  const [isAnnual, setIsAnnual] = useState(false);

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Pricing and fit"
          title="Pricing should describe operating mode, not just request volume."
          description="This stack is more than a basic PCB API. The right pricing surface needs to make room for trust-building, iteration, and full operational ownership."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/dashboard/keys">
                  <KeyRound className="mr-2 h-4 w-4" />
                  Create a key
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/playground">
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Validate a request
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Commercial posture</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  Frontend rule
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Never imply a fully productized workflow when the actual deployment still depends on backend reachability, proxy wiring, or operator review.
                </p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Coins className="h-4 w-4 text-orange-600" />
                  Buyer signal
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Users spending real money need the UI to feel grounded in the system’s true depth, not generic SaaS pricing theater.
                </p>
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Plan view</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Choose based on workflow depth.</h2>
            </div>
            <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 shadow-sm">
              <button
                onClick={() => setIsAnnual(false)}
                className={`rounded-full px-4 py-2 text-sm font-medium ${!isAnnual ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'}`}
              >
                Monthly
              </button>
              <button
                onClick={() => setIsAnnual(true)}
                className={`rounded-full px-4 py-2 text-sm font-medium ${isAnnual ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'}`}
              >
                Annual
              </button>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            {planCopy.map((plan, index) => (
              <motion.div key={plan.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: index * 0.08 }}>
                <Card className={`h-full rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_50px_rgba(15,23,42,0.06)] ${plan.popular ? 'ring-2 ring-cyan-300' : ''}`}>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="text-2xl text-slate-950">{plan.name}</CardTitle>
                        <CardDescription className="mt-2 text-base leading-7 text-slate-600">{plan.description}</CardDescription>
                      </div>
                      {plan.popular ? (
                        <div className="inline-flex items-center gap-1 rounded-full bg-cyan-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800">
                          <Star className="h-3.5 w-3.5" />
                          Fit for active work
                        </div>
                      ) : null}
                    </div>
                    <div className="pt-4">
                      {typeof plan.price.monthly === 'number' ? (
                        <div className="flex items-end gap-2">
                          <span className="text-5xl font-semibold tracking-tight text-slate-950">
                            ${isAnnual ? (plan.price.annual as number) / 12 : (plan.price.monthly as number)}
                          </span>
                          <span className="pb-2 text-sm text-slate-500">/ month</span>
                        </div>
                      ) : (
                        <div className="text-5xl font-semibold tracking-tight text-slate-950">{plan.price.monthly}</div>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <Button asChild className={`w-full rounded-full ${plan.popular ? 'bg-slate-900 text-white hover:bg-slate-800' : ''}`} variant={plan.popular ? 'default' : 'outline'}>
                      <Link href={plan.href}>
                        {plan.buttonText}
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Link>
                    </Button>
                    <div className="space-y-3">
                      {plan.features.map((feature) => (
                        <div key={feature} className="flex gap-3 text-sm leading-6 text-slate-600">
                          <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
                          <span>{feature}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </section>

        <section className="border-y border-slate-200/80 bg-white/70">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
            <div className="grid gap-6 lg:grid-cols-3">
              {fitNotes.map((note) => {
                const Icon = note.icon;
                return (
                  <Card key={note.title} className="rounded-[1.75rem] border-slate-200/80 bg-white/85 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
                    <CardHeader>
                      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-900">
                        <Icon className="h-5 w-5" />
                      </div>
                      <CardTitle className="text-xl text-slate-950">{note.title}</CardTitle>
                      <CardDescription className="text-base leading-7 text-slate-600">{note.copy}</CardDescription>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
