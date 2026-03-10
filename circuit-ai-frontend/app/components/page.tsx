'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { BookOpen, CircuitBoard, Cpu, LoaderCircle, RefreshCcw, ShieldCheck, Sparkles, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudioShell } from '@/components/studio-shell';
import { usePageTitle } from '@/components/use-page-title';

type ComponentResponse = {
  total_components?: number;
  component_types?: string[];
};

type EducationalResponse = {
  total_content?: number;
  content?: Array<{
    title?: string;
    difficulty?: string;
    component_type?: string;
    estimated_time?: string;
  }>;
};

type RepairResponse = {
  total_guides?: number;
  guides?: Array<{
    component_type?: string;
    issue?: string;
    difficulty?: string;
    success_rate?: number;
  }>;
};

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/cad', label: 'CAD' },
];

const fallbackTypes = ['ic_chip', 'capacitor', 'resistor', 'connector', 'transformer', 'diode'];

function panelHeading(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
}

export default function ComponentsPage() {
  usePageTitle('Component Intelligence | Circuit.AI');
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [componentData, setComponentData] = useState<ComponentResponse | null>(null);
  const [educationData, setEducationData] = useState<EducationalResponse | null>(null);
  const [repairData, setRepairData] = useState<RepairResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setErrorMessage(null);

      try {
        const [componentsRes, educationRes, repairRes] = await Promise.all([
          fetch(`${apiBaseUrl}/components`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/educational`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/repair`, { cache: 'no-store' }),
        ]);

        const [componentsJson, educationJson, repairJson] = await Promise.all([
          componentsRes.ok ? componentsRes.json() : Promise.resolve({}),
          educationRes.ok ? educationRes.json() : Promise.resolve({}),
          repairRes.ok ? repairRes.json() : Promise.resolve({}),
        ]);

        if (!active) return;
        setComponentData(componentsJson);
        setEducationData(educationJson);
        setRepairData(repairJson);

        if (!componentsRes.ok && !educationRes.ok && !repairRes.ok) {
          setErrorMessage(`Live component intelligence is unavailable at ${apiBaseUrl}. Fallback summary loaded.`);
        }
      } catch (error) {
        if (!active) return;
        console.error('Failed to load component intelligence', error);
        setErrorMessage(`Live component intelligence is unavailable at ${apiBaseUrl}. Fallback summary loaded.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const componentTypes = useMemo(
    () => componentData?.component_types?.length ? componentData.component_types : fallbackTypes,
    [componentData],
  );
  const educationalItems = educationData?.content || [];
  const repairGuides = repairData?.guides || [];

  return (
    <StudioShell
      eyebrow="Workbench"
      title="Browse component intelligence in a docked reference layout."
      description="The parts grid sits in the center, source context lives on the left, and education plus repair guidance stay in the inspector rather than being pushed below the fold."
      status={loading ? 'Refreshing part intelligence' : `${componentData?.total_components || componentTypes.length} component types indexed`}
      activeHref="/components"
      navItems={navItems}
      actions={
        <>
          <Button asChild className="rounded-full bg-white text-slate-950 hover:bg-slate-100">
            <Link href="/analyze">
              <CircuitBoard className="mr-2 h-4 w-4" />
              Back to analyze
            </Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/projects">
              <Sparkles className="mr-2 h-4 w-4" />
              Project planning
            </Link>
          </Button>
        </>
      }
      left={
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Source', 'Workspace feed')}
            <div className="text-sm leading-6 text-slate-400">
              Pulls from <span className="text-white">/components</span>, <span className="text-white">/educational</span>, and <span className="text-white">/repair</span> when available.
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Counts', 'Reference stats')}
            <div className="grid gap-3">
              {[
                ['Tracked types', loading ? '...' : String(componentData?.total_components || componentTypes.length)],
                ['Educational overlays', String(educationData?.total_content || educationalItems.length || 0)],
                ['Repair guides', String(repairData?.total_guides || repairGuides.length || 0)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                  <div className="mt-2 text-lg font-semibold text-white">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {errorMessage ? (
            <div className="rounded-[1.5rem] border border-amber-400/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
              {errorMessage}
            </div>
          ) : null}
        </div>
      }
      main={
        <div className="grid h-full gap-px bg-white/5 lg:grid-rows-[72px_minmax(0,1fr)]">
          <div className="flex items-center justify-between bg-[#0d1628] px-5">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Parts matrix</div>
              <div className="mt-1 text-sm font-semibold text-white">Known component types</div>
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {loading ? 'Syncing' : 'Studio reference view'}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto bg-[#09111f] p-4">
            <div className="grid gap-5 xl:grid-cols-2 2xl:grid-cols-3">
              {componentTypes.map((type) => (
                <div key={type} className="rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,#0f1b35,#091423)] p-5 transition-all hover:-translate-y-0.5 hover:border-cyan-300/30 hover:bg-[linear-gradient(180deg,#122244,#0b1730)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-400/10 text-cyan-200 shadow-[0_14px_30px_rgba(34,211,238,0.12)]">
                        <Cpu className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-base font-semibold text-white">{type.replaceAll('_', ' ')}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-[0.22em] text-slate-500">reference node</div>
                      </div>
                    </div>
                    <div className="rounded-full border border-white/10 bg-[#081423] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                      active
                    </div>
                  </div>
                  <p className="mt-5 text-sm leading-6 text-slate-300">
                    Candidate anchor for overlays, part intelligence, reuse pathways, and focused repair guidance.
                  </p>
                  <div className="mt-5 grid gap-2">
                    {['Overlay annotations', 'Reuse signal', 'Repair lookup'].map((label) => (
                      <div key={label} className="rounded-xl border border-white/8 bg-[#081423] px-3 py-2 text-xs font-medium text-slate-300">
                        {label}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      }
      right={
        <div className="space-y-4">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <BookOpen className="h-4 w-4 text-cyan-300" />
              Education dock
            </div>
            <div className="space-y-3">
              {educationalItems.length ? educationalItems.slice(0, 5).map((item, index) => (
                <div key={`${item.title || 'educational'}-${index}`} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-sm font-semibold text-white">{item.title || 'Untitled content'}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">
                    {item.component_type ? item.component_type.replaceAll('_', ' ') : 'Component-focused material'}
                    {item.estimated_time ? ` • ${item.estimated_time}` : ''}
                  </div>
                </div>
              )) : (
                <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3 text-sm leading-6 text-slate-400">
                  No educational items loaded for this session.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <RefreshCcw className="h-4 w-4 text-cyan-300" />
              Repair dock
            </div>
            <div className="space-y-3">
              {repairGuides.length ? repairGuides.slice(0, 5).map((guide, index) => (
                <div key={`${guide.component_type || 'repair'}-${guide.issue || index}`} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-sm font-semibold text-white">
                    {guide.component_type ? guide.component_type.replaceAll('_', ' ') : 'Component'}
                  </div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">
                    {guide.issue || 'Repair path unavailable'}
                    {guide.success_rate !== undefined ? ` • ${Math.round(guide.success_rate * 100)}%` : ''}
                  </div>
                </div>
              )) : (
                <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3 text-sm leading-6 text-slate-400">
                  No repair guidance loaded for this session.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldCheck className="h-4 w-4 text-cyan-300" />
              Flow note
            </div>
            <div className="text-sm leading-6 text-slate-400">
              The center stays focused on the parts matrix while the right dock holds interpretation. This is the visual direction the whole product should follow.
            </div>
          </div>
        </div>
      }
    />
  );
}
